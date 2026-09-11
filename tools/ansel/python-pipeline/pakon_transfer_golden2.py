#!/usr/bin/env python3
"""Transfer comparison against the vendor -- SAME estimator on BOTH sides.

WHY A SECOND ONE
================
docs/74 §155: `pakon_transfer_golden.py` cannot be satisfied by the vendor's own
output. Scored with its own `measure()`, the vendor's `rawAA001 -> AA001` gives
R -0.9523, G -0.9602, B -0.9431 against a `|corr| >= 0.97` threshold -- all
three fail. And its `VENDOR_SLOPE` constants (-248.42/-252.77/-229.31) reproduce
from the vendor's own data by neither a per-pixel nor a median-binned fit
(-225.4/-211.0/-157.7 and -187.1/-187.4/-142.5 respectively), while `measure()`
fits the PORT per-pixel and compares against a median-binned constant.

So the old test scores a port against unreproducible constants using an
estimator it applies to only one side. Tuning against it optimises an artefact.

WHAT THIS DOES INSTEAD
======================
Measures the vendor's own raw->rendered pair and this port's render with the
IDENTICAL estimator, and reports the port's deviation FROM THE VENDOR'S OWN
VALUES rather than from a constant.

Slope-per-decade is scale-invariant (`log10(k*x)` moves the intercept, not the
slope), which is what makes a cross-roll slope comparison legitimate. Absolute
LEVEL is not scale-invariant and is deliberately not compared here -- §146.5
withdrew a conclusion for exactly that reason. Use the black-point and
channel-separation comparisons (§133, §153) for level.

WHAT IT DOES NOT DO
===================
It does not claim the port is correct when it passes. It claims only that the
port's transfer slope and its scatter are within a stated distance of the
vendor's, measured identically. Correlation is reported as a DIFFERENCE from the
vendor's own correlation, because the vendor's is ~0.94-0.96 and an absolute
0.97 bar is unmeetable.

Usage:  python3 pakon_transfer_golden2.py <render_dir> [frame]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

#: how far the port's slope may sit from the vendor's OWN slope, same estimator
SLOPE_TOL_PCT = 10.0
#: how far the port's correlation may sit BELOW the vendor's own correlation
CORR_TOL = 0.03

VENDOR_RAW = Path("/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp/rawAA001.tif")
VENDOR_OUT = Path("/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp/AA001.tif")


def fit(x: np.ndarray, y: np.ndarray):
    """The one estimator, applied to both sides. Per-pixel, clipping excluded."""
    m = (x > 50) & (y > 3) & (y < 252)
    if m.sum() < 500:
        return float("nan"), float("nan"), float("nan")
    lx = np.log10(x[m])
    yy = y[m]
    slope, icept = np.polyfit(lx, yy, 1)
    corr = np.corrcoef(lx, yy)[0, 1]
    resid = yy - (slope * lx + icept)
    return float(slope), float(corr), float(resid.std())


def measure_pair(raw_path: Path, out_path: Path):
    import imageio.v3 as iio
    from PIL import Image
    raw = iio.imread(raw_path).astype(np.float64)[::3, ::3]
    out = np.asarray(Image.open(out_path).convert("RGB"),
                     dtype=np.float64)[::3, ::3]
    return {ch: fit(raw[..., i].ravel(), out[..., i].ravel())
            for i, ch in enumerate("RGB")}


def measure_render(render_dir: Path, frame: str):
    import imageio.v3 as iio
    from PIL import Image
    lin = iio.imread(render_dir / "frames" / f"{frame}_raw14.tiff"
                     ).astype(np.float64)[::3, ::3]
    out = np.asarray(Image.open(render_dir / "frames" / f"{frame}_srgb.png"
                                ).convert("RGB"), dtype=np.float64)[::3, ::3]
    return {ch: fit(lin[..., i].ravel(), out[..., i].ravel())
            for i, ch in enumerate("RGB")}


def main(argv) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    d = Path(argv[1])
    frame = argv[2] if len(argv) > 2 else "05"
    if not VENDOR_RAW.is_file() or not VENDOR_OUT.is_file():
        return int(print(f"vendor pair not found: {VENDOR_RAW}") or 2)

    vend = measure_pair(VENDOR_RAW, VENDOR_OUT)
    ours = measure_render(d, frame)

    print(f"render : {d.name}  frame {frame}")
    print(f"vendor : {VENDOR_RAW.name} -> {VENDOR_OUT.name}  (same estimator)")
    print()
    print(f"{'ch':>3} {'slope':>9} {'vendor':>9} {'err %':>7} "
          f"{'corr':>7} {'vendor':>8} {'d(corr)':>8} {'scatter':>8} {'vendor':>8}")
    npass = 0
    for ch in "RGB":
        s, c, r = ours[ch]
        vs, vc, vr = vend[ch]
        err = abs(s - vs) / abs(vs) * 100.0
        dc = abs(c) - abs(vc)
        ok = err <= SLOPE_TOL_PCT and dc >= -CORR_TOL
        npass += ok
        print(f"{ch:>3} {s:9.1f} {vs:9.1f} {err:7.1f} "
              f"{c:7.3f} {vc:8.3f} {dc:+8.3f} {r:8.2f} {vr:8.2f}"
              f"  {'PASS' if ok else ''}")
    print()
    print(f"{npass}/3 channels within {SLOPE_TOL_PCT:g}% of the vendor's own "
          f"slope and within {CORR_TOL} of its own correlation")
    print()
    print("NOTE: slope-per-decade is scale-invariant, so this cross-roll "
          "comparison is valid for SLOPE and SCATTER.")
    print("Absolute LEVEL is not compared here -- see §133 (black point) and "
          "§153 (channel separation) for that.")
    return 0 if npass == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
