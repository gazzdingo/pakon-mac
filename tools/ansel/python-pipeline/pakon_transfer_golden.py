#!/usr/bin/env python3
"""INTEGRATION golden: this port's end-to-end transfer vs the vendor's, measured.

WHY THIS FILE EXISTS
--------------------
There are 36 `*_golden.py` files in this directory and every one of them
verifies a *component* bit-exact against the real DLL — including
`pakon_autotone_assembled_golden.py`, which runs the real `analyzeAutoTone`
with no subsystem stubbed. The tone chain, `orderFpo`, the VM, `fos_opening_axes`
and the balance shift are all confirmed.

And the render is still visibly wrong (docs/74 §116: ~62 % of the vendor's
contrast slope). **Every component is golden and the composition is not**, which
is precisely the failure no per-component test can catch, and which cost §109
through §118 a long sequence of substitutions that each made things worse.

This closes that gap. It does not emulate anything: it measures what the port
actually produces, end to end, against what the vendor actually produced, and
fails when they diverge.

THE GROUND TRUTH
----------------
`rawAA001.tif` … `rawAA006.tif` and `AA001.tif` … are the vendor's own input and
output for the SAME frames — same dimensions, pixel-aligned (docs/74 §116).
Fitting `out = m·log10(raw) + c` per channel over median-per-input-value gives

    R  -248.42   G  -252.77   B  -229.31      (corr -0.99 on every channel)

Slope per decade is scale-invariant — `log10(k·x)` moves the intercept, not the
slope — so a 14-bit port linear and an 8-bit vendor export are directly
comparable. That is what makes this test possible at all.

WHAT IT ASSERTS
---------------
1. The port's transfer is log-shaped   (|corr| >= LOG_CORR_MIN)
2. Its slope is within SLOPE_TOL_PCT of the vendor's, per channel

Both are currently FAILING, by design: this test states the target, and its
failure output is the metric to work against. docs/74 §117 records that
`PAKON_UNIFORM_ANCHOR=975` moves G and B onto the vendor's slope and fixes R's
shape — run with it set to see the current best.

Usage::

    python3 pakon_transfer_golden.py <render_dir> [frame]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

#: docs/74 §116.1 — fitted per-pixel from the vendor's own raw/output pair.
VENDOR_SLOPE = {"R": -248.42, "G": -252.77, "B": -229.31}

#: A port whose transfer is not log-shaped cannot be corrected by any gain
#: (docs/74 §116.3 — baseline R manages only -0.62).
LOG_CORR_MIN = 0.97

#: Per-channel slope tolerance. 10 % is loose; the baseline is ~38 % out.
SLOPE_TOL_PCT = 10.0


def measure(render_dir: Path, frame: str = "05"):
    import imageio.v3 as iio
    from PIL import Image

    lin = iio.imread(render_dir / "frames" / f"{frame}_raw14.tiff")
    out = np.asarray(Image.open(
        render_dir / "frames" / f"{frame}_srgb.png").convert("RGB"))
    lin = lin.astype(np.float64)[::3, ::3]
    out = out.astype(np.float64)[::3, ::3]

    res = {}
    for i, ch in enumerate("RGB"):
        x = lin[..., i].ravel()
        y = out[..., i].ravel()
        m = (x > 50) & (y > 3) & (y < 252)
        if m.sum() < 500:
            res[ch] = (float("nan"), float("nan"))
            continue
        lx = np.log10(x[m])
        slope, _ = np.polyfit(lx, y[m], 1)
        corr = np.corrcoef(lx, y[m])[0, 1]
        res[ch] = (float(slope), float(corr))
    return res


def main(argv) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    d = Path(argv[1])
    frame = argv[2] if len(argv) > 2 else "05"
    got = measure(d, frame)

    print(f"render : {d.name}  frame {frame}")
    print(f"{'ch':>3} {'slope':>10} {'vendor':>10} {'err %':>8} "
          f"{'log corr':>10}   verdict")
    fails = 0
    for ch in "RGB":
        slope, corr = got[ch]
        ref = VENDOR_SLOPE[ch]
        err = abs(slope - ref) / abs(ref) * 100.0
        bad = []
        if not (abs(corr) >= LOG_CORR_MIN):
            bad.append(f"shape |corr| {abs(corr):.2f} < {LOG_CORR_MIN}")
        if not (err <= SLOPE_TOL_PCT):
            bad.append(f"slope off {err:.1f}% > {SLOPE_TOL_PCT}%")
        fails += bool(bad)
        print(f"{ch:>3} {slope:10.1f} {ref:10.1f} {err:8.1f} {corr:10.2f}   "
              f"{'PASS' if not bad else '; '.join(bad)}")

    print(f"\n{3 - fails}/3 channels within tolerance")
    if fails:
        print("FAIL — this is the washed-out defect, stated as a number.\n"
              "docs/74 §117: PAKON_UNIFORM_ANCHOR=975 is the current best.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
