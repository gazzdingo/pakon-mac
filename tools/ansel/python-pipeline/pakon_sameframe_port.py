#!/usr/bin/env python3
"""Run THIS PORT's colour chain on the VENDOR'S OWN raw frame and diff the two
renders per-pixel.

WHY THIS IS DIFFERENT FROM EVERY EARLIER COMPARISON
===================================================
docs/74 §130-§156 all compare across rolls: this port renders roll X, the vendor
rendered roll Y, and the two are scored by a fitted transfer slope. That is the
only comparison the captures allowed, and it has a hard limit -- a fitted slope
and its residual scatter depend on scene CONTENT as well as on the transfer, so
"our slope is 25 % off" may be the roll, not the port. §146.5 already withdrew
one conclusion for exactly this reason.

`rawAA001.tif` and `AA001.tif` are the vendor's own input and output for ONE
frame, pixel-aligned. Feeding that raw through this port's chain gives a
content-matched, per-pixel comparison -- no fitting, no estimator, no roll
confound. The difference image IS the answer.

WHAT IS ASSUMED, AND WHY IT IS SWEPT
====================================
`rawAA001.tif` is an 8-bit export (195 distinct levels, max 204), not the linear
14-bit `render_rpd` consumes. The scale back to the linear domain is unknown and
matters, because the stage-2 polynomial subtracts a fixed pedestal
(OWNER_PEDESTALS, confirmed bit-exact in §145.2) and is therefore NOT
scale-invariant. Picking one scale would be fitting, so every plausible scale is
swept and the whole sweep is reported.

WHAT THIS CANNOT SHOW
=====================
* 8-bit quantisation is an error floor this test cannot see past. A small
  residual is not proof of bit-exactness.
* If the vendor's export applied any curve of its own before writing the 8-bit
  file, the "raw" is not linear and the sweep cannot correct for it. The sweep's
  SHAPE is diagnostic here: a clean minimum suggests a linear export, a flat or
  monotone sweep suggests it is not.

Usage:  python3 pakon_sameframe_port.py [--full]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

RAW = Path("/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp/rawAA001.tif")
OUT = Path("/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp/AA001.tif")

#: swept, not chosen -- see the module docstring
SCALES = [16.0, 24.0, 32.0, 48.0, 64.0, 80.0, 96.0, 128.0]


def load(step: int):
    import imageio.v3 as iio
    from PIL import Image
    raw = iio.imread(RAW)[::step, ::step]
    ref = np.asarray(Image.open(OUT).convert("RGB"))[::step, ::step]
    return raw, ref


def render_port(raw8: np.ndarray, scale: float) -> np.ndarray:
    """rawAA001 -> this port's sRGB, via the same calls pakon_render.py makes.

    Goes through `pakon_render.scene_rpd12`, NOT `pakon_decode.render_rpd`.
    That is load-bearing: on the F-135 path `render_rpd` is stage 2 only and
    preserves polarity (the poly diagonal is +0.289/+0.276/+0.278), so the
    logarithm in `f135_rom12_to_rpd12` is what turns the negative the right way
    up. `scene_rpd12`'s own docstring warns that a chain which skips it "emits
    the negative" and that nothing downstream notices. An earlier revision of
    this script skipped it and scored a perfectly inverted image (raw->rpd12
    correlation +1.000, port-vs-vendor -0.95).
    """
    import pakon_decode as dec
    import pakon_ansel as ansel
    import pakon_render as pr

    rgb14 = np.clip(raw8.astype(np.float64) * scale, 0, 16383).astype(np.uint16)
    eng = ansel.AnselEngine.load(dec.DEFAULT_ANSEL_ROOT,
                                 scene=ansel.SceneContext())
    eng.shasta_stand_in = True
    eng.rpd_max = 4095.0
    offset = np.zeros(3, dtype=np.float64)
    rpd12 = pr.scene_rpd12(rgb14, dec.DEFAULT_DATA_DIR, offset, "f135", eng)
    toned = eng.render_scene(rpd12, None)
    return np.asarray(eng.to_srgb(toned), dtype=np.uint8)


def score(ours: np.ndarray, ref: np.ndarray) -> dict:
    """Per-pixel agreement, plus the part a pure offset would explain."""
    d = ours.astype(np.float64) - ref.astype(np.float64)
    res = {}
    for i, ch in enumerate("RGB"):
        e = d[..., i].ravel()
        bias = float(e.mean())
        res[ch] = {
            "bias": bias,
            "mae": float(np.abs(e).mean()),
            "p95": float(np.percentile(np.abs(e), 95)),
            # what survives after removing a pure per-channel offset: this is
            # the part no anchor/pedestal correction can ever remove
            "resid": float(np.abs(e - bias).mean()),
        }
    return res


def main(argv) -> int:
    step = 1 if "--full" in argv else 3
    raw, ref = load(step)
    print(f"same-frame port test  {raw.shape[0]}x{raw.shape[1]} (step {step})")
    print(f"  vendor raw {RAW.name} -> vendor render {OUT.name}")
    print("  scale is SWEPT, not chosen -- see module docstring\n")
    print(f"{'scale':>7} | {'R bias':>7} {'R mae':>6} {'R res':>6} | "
          f"{'G bias':>7} {'G mae':>6} {'G res':>6} | "
          f"{'B bias':>7} {'B mae':>6} {'B res':>6} | {'tot res':>7}")
    print("-" * 96)

    best = None
    for s in SCALES:
        try:
            ours = render_port(raw, s)
        except Exception as exc:                       # noqa: BLE001
            print(f"{s:7.0f} | render failed: {type(exc).__name__}: {exc}")
            continue
        r = score(ours, ref)
        tot = sum(r[c]["resid"] for c in "RGB")
        row = " | ".join(
            f"{r[c]['bias']:+7.1f} {r[c]['mae']:6.1f} {r[c]['resid']:6.1f}"
            for c in "RGB")
        print(f"{s:7.0f} | {row} | {tot:7.1f}")
        if best is None or tot < best[1]:
            best = (s, tot, r)

    if best:
        s, tot, r = best
        print(f"\nlowest offset-removed residual at scale {s:g}: {tot:.1f} "
              f"(sum over RGB)")
        print("  'bias' is a pure per-channel offset -- an anchor CAN fix that.")
        print("  'res' is what remains after removing it -- an anchor CANNOT.")
        print("  Compare 'res' against the vendor's own irreducible p95 of ~20-24")
        print("  codes (pakon_sameframe_golden.py) before reading it as an error.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
