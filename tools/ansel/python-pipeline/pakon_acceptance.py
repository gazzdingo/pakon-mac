#!/usr/bin/env python3
"""Acceptance test for the analyzeAutoTone render-path swap (docs/66 Phase 6).

Phase 6 calls for an acceptance test. This is it, and it can be built now
because the vendor's finished output is measurable without instrumenting the
DLL: PSI's RAW export and its finished render of the same frame are
PIXEL-REGISTERED, so the vendor's end-to-end transfer function can be derived
straight from the pair, per channel, per code value.

    baseline = median(vendor_render | raw bucket)      <- the target
    candidate = median(our_render   | raw bucket)      <- what we score

The score is the max absolute deviation between the two, per channel, in 8-bit
code values. Today, with shasta_two_anchor_tone standing in for the real chain,
it is around +144..+160 in the midtones-to-shadows. When Phase 6 swaps the real
analyzeAutoTone in, that number should collapse. If it does not, this says so
immediately and points at which part of the range is wrong.

WHY A BASELINE FILE AND NOT THE IMAGES
    The reference frames are the owner's own film and live outside this repo.
    The baseline is a derived tone curve -- a few hundred integers -- so the
    test runs anywhere without shipping anyone's photographs.

    Regenerate it (needs the pair):
        ./pakon_acceptance.py --derive RAW.tif RENDER.tif -o baseline.json

    Score a render against it:
        ./pakon_acceptance.py --baseline baseline.json \
            --raw RAW.tif --candidate ours.png

    Score whatever the engine currently produces, end to end:
        ./pakon_acceptance.py --baseline baseline.json --raw RAW.tif --render

REGISTRATION IS CHECKED, NOT ASSUMED
    A misaligned pair silently produces a meaningless curve. --derive refuses
    to write a baseline whose peak |correlation| is not at dy=dx=0.

CAVEAT INHERITED FROM THE INPUT
    PSI's RAW export is 8-bit and partly processed, not true RPD12. Driving the
    engine from it (--render) is an APPROXIMATION and its absolute numbers are
    not trustworthy: three separate 'findings' during development turned out
    to be artefacts of exactly this input mismatch. The BASELINE, however, is vendor-only: it
    is derived from two vendor outputs and is unaffected. Scoring a candidate
    that was rendered from real RPD12 against this baseline is sound.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

STEP = 8
MIN_BUCKET = 200


def _load(p: Path) -> np.ndarray:
    from PIL import Image
    return np.asarray(Image.open(p).convert("RGB"))


def best_shift(a: np.ndarray, b: np.ndarray):
    ga, gb = a.mean(2).astype(np.float64), b.mean(2).astype(np.float64)
    best = None
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            A = ga[20:-20, 20:-20]
            B = gb[20 + dy:gb.shape[0] - 20 + dy,
                   20 + dx:gb.shape[1] - 20 + dx]
            c = abs(np.corrcoef(A.ravel(), B.ravel())[0, 1])
            if best is None or c > best[0]:
                best = (c, dy, dx)
    return best


def curve(raw: np.ndarray, out: np.ndarray) -> dict:
    """{channel: {raw_bucket_centre: median_output}} plus bucket counts."""
    res = {}
    for c, name in enumerate("RGB"):
        s, d = raw[:, :, c].ravel(), out[:, :, c].ravel()
        pts = {}
        for lo in range(0, 256, STEP):
            m = (s >= lo) & (s < lo + STEP)
            n = int(m.sum())
            if n < MIN_BUCKET:
                continue
            pts[str(lo + STEP // 2)] = [float(np.median(d[m])), n]
        res[name] = pts
    return res


def score(baseline: dict, cand: dict) -> dict:
    """Max and mean |deviation| per channel, over buckets present in both."""
    out = {}
    for name in "RGB":
        b, c = baseline.get(name, {}), cand.get(name, {})
        shared = sorted(set(b) & set(c), key=int)
        if not shared:
            out[name] = {"max": None, "mean": None, "n": 0, "worst_at": None}
            continue
        devs = [(abs(b[k][0] - c[k][0]), int(k)) for k in shared]
        mx, at = max(devs)
        out[name] = {"max": mx, "mean": sum(d for d, _ in devs) / len(devs),
                     "n": len(shared), "worst_at": at}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--derive", nargs=2, metavar=("RAW", "RENDER"),
                    help="derive a baseline from a vendor raw/render pair")
    ap.add_argument("-o", "--out", type=Path, help="baseline path for --derive")
    ap.add_argument("--baseline", type=Path, help="baseline json to score against")
    ap.add_argument("--raw", type=Path, help="the vendor RAW, the common x-axis")
    ap.add_argument("--candidate", type=Path, help="an already-rendered image")
    ap.add_argument("--render", action="store_true",
                    help="render from --raw through the engine (APPROXIMATE input)")
    ap.add_argument("--fail-over", type=float, default=None,
                    help="exit 1 if any channel's max deviation exceeds this")
    args = ap.parse_args()

    if args.derive:
        raw, ven = (_load(Path(p)) for p in args.derive)
        if raw.shape != ven.shape:
            print(f"shape mismatch {raw.shape} vs {ven.shape}")
            return 1
        c, dy, dx = best_shift(raw, ven)
        print(f"registration: peak |corr| {c:.4f} at dy={dy} dx={dx}")
        if dy or dx:
            print("REFUSING: pair is not pixel-registered, the curve would be "
                  "meaningless. Check these are the same frame.")
            return 1
        data = {"source": [Path(args.derive[0]).name, Path(args.derive[1]).name],
                "step": STEP, "min_bucket": MIN_BUCKET,
                "registration_corr": round(float(c), 4),
                "curve": curve(raw, ven)}
        dest = args.out or Path("vendor_baseline.json")
        dest.write_text(json.dumps(data, indent=1, sort_keys=True))
        n = sum(len(v) for v in data["curve"].values())
        print(f"wrote {dest}  ({n} buckets across R/G/B)")
        return 0

    if not args.baseline or not args.raw:
        ap.error("need --baseline and --raw (or --derive)")
    base = json.loads(args.baseline.read_text())
    raw = _load(args.raw)

    if args.render:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        import pakon_ansel as A
        import pakon_decode as dec
        import pakon_render as pr
        eng = A.AnselEngine.load(scene=A.scene_from_filmstock(
            path="ColNeg", dx_part1=96, dx_part2=1, iso=400))
        # Match production. The dataclass default is False; pakon_decode and
        # pakon_render both set it True. Loading without setting it measures a
        # branch no real render takes.
        eng.shasta_stand_in = True
        neg = raw.astype(np.float64) * 16.0
        fb = tuple(float(dec._film_base_code(neg[:, :, c])) for c in range(3))
        pos = dec.f135_rom12_to_rpd12(neg, pr.poly_pedestals(), eng.sba.fpo,
                                      eng.setshifts_out, quiet=True,
                                      film_base=fb)
        cand = eng.to_srgb(eng.render_scene(pos))
        print("NOTE: rendered from the 8-bit vendor RAW. Approximate input; "
              "absolute scores carry that caveat.")
    elif args.candidate:
        cand = _load(args.candidate)
    else:
        ap.error("need --candidate or --render")

    if cand.shape != raw.shape:
        print(f"shape mismatch: raw {raw.shape} vs candidate {cand.shape}")
        return 1

    s = score(base["curve"], curve(raw, cand))
    print(f"\nbaseline: {base.get('source')}  "
          f"registration corr {base.get('registration_corr')}")
    print(f"\n{'ch':3}{'max dev':>10}{'mean dev':>11}{'worst at raw':>15}"
          f"{'buckets':>10}")
    print("-" * 49)
    worst = 0.0
    for name in "RGB":
        r = s[name]
        if r["n"] == 0:
            print(f"{name:3}{'no overlap':>10}")
            continue
        worst = max(worst, r["max"])
        print(f"{name:3}{r['max']:10.0f}{r['mean']:11.1f}"
              f"{r['worst_at']:15}{r['n']:10}")
    print(f"\nworst channel deviation: {worst:.0f} of 255")
    if args.fail_over is not None and worst > args.fail_over:
        print(f"FAIL: exceeds --fail-over {args.fail_over}")
        return 1
    if args.fail_over is not None:
        print(f"PASS: within --fail-over {args.fail_over}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
