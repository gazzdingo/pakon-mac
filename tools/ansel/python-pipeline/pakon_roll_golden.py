#!/usr/bin/env python3
"""Per-pixel comparison of this port against the vendor, on REAL 14-bit sensor
data, over a whole roll.

WHY THIS SUPERSEDES docs/74 §157
================================
§157 built the first content-matched comparison, but on `rawAA001.tif` -- the
PSI 8-bit "raw" TIFF export -- and only ONE such pair exists. It carried three
stated caveats: an 8-bit quantisation floor, a single frame, and no access to
real sensor data. §157.5/§157.10 both had to be qualified because of them, and
the conclusion was that lifting them needed hardware.

They can be lifted from data already on disk. The `tlb_polypixel` hook row
captures the raw 14-bit planar frame PolyPixel reads at ENTRY -- pre-poly,
pre-log, real sensor domain -- and was widened to 0x84000 bytes (docs/74 §60)
so a whole frame lands in one dump. `live_hooks_20260819-121153.jsonl` holds 78
distinct full frames, and they pair to the 39 vendor renders in `0new/` by
content at mean correlation 0.965 with a mean margin of 0.295 (38/39 above
corr 0.7 and margin 0.1).

So: real 14-bit input, the vendor's own render of the same frame, ~39 frames.

TWO TRAPS THIS AVOIDS, BOTH HIT DURING DEVELOPMENT
==================================================
1. `0new/AA001.tif` and the standalone `AA001.tif` are DIFFERENT IMAGES
   (per-pixel correlation +0.099). They are different rolls. A matcher control
   run against the wrong one failed and briefly "proved" the capture was an
   unrelated roll. The reference set here is `0new/` only.
2. The hook frames are 245x367 (aspect 1.498); the renders are 2941x1960
   (aspect 1.501). They correspond under a 90-degree ROTATION. A pairing pass
   that tried only flips scored 0.575 and looked like a different roll; adding
   rotations took it to 0.965. Orientation is searched, never assumed.

EVIDENCE TIER
=============
Tier 2 (live hardware hook capture) for the input, tier 4 (empirical against a
real vendor reference) for the comparison. NOT tier 1: this measures agreement,
it does not prove any stage bit-exact.

Usage:
    python3 pakon_roll_golden.py                # score the default config
    PAKON_PAPER_ALIGN=1 python3 pakon_roll_golden.py
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "re"))
sys.path.insert(0, str(HERE))

TMP = Path("/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp")
CAPTURE = TMP / "live_hooks_20260819-121153.jsonl"
VEND = TMP / "0new"

W, H = 245, 367
SIG = 24


def sig(a: np.ndarray) -> np.ndarray:
    im = Image.fromarray(np.ascontiguousarray(a, dtype=np.float32),
                         mode="F").resize((SIG, SIG), Image.BILINEAR)
    v = np.asarray(im, dtype=np.float64).ravel()
    v -= v.mean()
    return v / max(np.linalg.norm(v), 1e-9)


def load_raws() -> list[tuple[str, np.ndarray]]:
    from extract_poly_raw import find_hex, iter_rows
    out, seen = [], set()
    for row in iter_rows(CAPTURE):
        h, _ = find_hex(row)
        if not h:
            continue
        d = hashlib.md5(h.encode()).hexdigest()[:12]
        if d in seen:
            continue
        b = np.frombuffer(bytes.fromhex(h.strip()), dtype="<u2")
        if b.size < W * H * 3:
            continue
        seen.add(d)
        planes = [b[i * W * H:(i + 1) * W * H].reshape(H, W).astype(np.float64)
                  for i in range(3)]
        out.append((d, np.stack(planes, axis=-1)))
    return out


def render_ours(rgb_raw: np.ndarray) -> np.ndarray:
    """Real sensor planes -> this port's sRGB, via pakon_render.scene_rpd12.

    scene_rpd12 (not pakon_decode.render_rpd) is mandatory: on the F-135 path
    stage 2 preserves polarity and the log inside f135_rom12_to_rpd12 is what
    inverts the negative. A chain that skips it silently emits the negative.
    """
    import pakon_decode as dec
    import pakon_ansel as ansel
    import pakon_render as pr

    rgb14 = np.clip(rgb_raw, 0, 16383).astype(np.uint16)
    with contextlib.redirect_stdout(io.StringIO()):
        eng = ansel.AnselEngine.load(dec.DEFAULT_ANSEL_ROOT,
                                     scene=ansel.SceneContext())
        eng.shasta_stand_in = True
        eng.rpd_max = 4095.0
        rpd12 = pr.scene_rpd12(rgb14, dec.DEFAULT_DATA_DIR, np.zeros(3),
                               "f135", eng)
        out = eng.to_srgb(eng.render_scene(rpd12, None))
    return np.asarray(out, dtype=np.uint8)


def main(argv) -> int:
    raws = load_raws()
    vends = sorted(VEND.glob("AA0*.tif"))
    print(f"raw frames {len(raws)}   vendor renders {len(vends)}")
    if not raws or not vends:
        print("missing inputs")
        return 2

    # pair by content, searching orientation rather than assuming it
    rsigs = [(d, sig(np.rot90(a.mean(axis=2), 1))) for d, a in raws]
    lut = {d: a for d, a in raws}
    pairs = []
    for p in vends:
        v = np.asarray(Image.open(p).convert("RGB"), dtype=np.float64)
        vs = sig(v.mean(axis=2))
        sc = sorted(((abs(float(np.dot(vs, rs))), d) for d, rs in rsigs),
                    reverse=True)
        if sc[0][0] > 0.7 and (sc[0][0] - sc[1][0]) > 0.1:
            pairs.append((p, lut[sc[0][1]], sc[0][0]))
    print(f"confident pairs: {len(pairs)}/{len(vends)}\n")

    print(f"{'frame':8} {'R bias':>8} {'G bias':>8} {'B bias':>8} {'mae':>7}")
    print("-" * 44)
    rows = []
    for p, raw, c in pairs:
        try:
            ours = render_ours(raw)
        except Exception as exc:                       # noqa: BLE001
            print(f"{p.stem:8} render failed: {type(exc).__name__}")
            continue
        # bring the vendor render into the raw's geometry (rot90 of raw
        # matches the render's aspect), then compare per-pixel
        oh, ow = ours.shape[:2]
        v = np.asarray(Image.open(p).convert("RGB").resize(
            (ow, oh), Image.LANCZOS), dtype=np.float64)
        o = np.rot90(ours, 0).astype(np.float64)
        v = np.rot90(v, 0)
        # ours is portrait (HxW); rotate it to the render's orientation
        o = np.rot90(ours.astype(np.float64), 1)
        v = np.asarray(Image.open(p).convert("RGB").resize(
            (o.shape[1], o.shape[0]), Image.LANCZOS), dtype=np.float64)
        d = o - v
        b = [float(d[..., i].mean()) for i in range(3)]
        mae = float(np.abs(d).mean())
        rows.append((p.stem, b, mae))
        print(f"{p.stem:8} {b[0]:+8.1f} {b[1]:+8.1f} {b[2]:+8.1f} {mae:7.2f}")

    if rows:
        B = np.array([r[1] for r in rows])
        M = np.array([r[2] for r in rows])
        print("-" * 44)
        print(f"{'MEAN':8} {B[:,0].mean():+8.1f} {B[:,1].mean():+8.1f} "
              f"{B[:,2].mean():+8.1f} {M.mean():7.2f}")
        print(f"{'SD':8} {B[:,0].std():8.1f} {B[:,1].std():8.1f} "
              f"{B[:,2].std():8.1f} {M.std():7.2f}")
        print(f"\n{len(rows)} frames of REAL 14-bit sensor data.")
        print("Bias SD across frames is the number §157 could not measure: a")
        print("small SD means the offset is a CONSTANT (fixable by one term);")
        print("a large SD means it is scene-dependent and no constant fixes it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
