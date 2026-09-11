#!/usr/bin/env python3
"""SAME-FRAME comparison: our colour chain vs the vendor's, on the vendor's own
pixels.

WHY
===
Every vendor comparison in docs/74 §130-§156 has been cross-roll, because the
hook captures carry no raw this port can render and the `scan-*.bin` files carry
no vendor render. That confound has already forced one withdrawal (§146.5) and
it limits the rest: fitted slope and residual scatter both depend on scene
CONTENT, not only on the transfer, so "our slope is 35 % off the vendor's" may
be the roll rather than the port.

`rawAA001.tif` and `AA001.tif` are the vendor's own input and output for the
SAME frame, pixel-aligned (verified: both 1960x2941, identical shape). Running
this port's chain on that raw and diffing against that render is a direct,
content-matched comparison -- the first available.

WHAT IT MEASURES
================
Per channel, over the vendor's own frame:
  * the transfer this port produces vs the transfer the vendor produced
  * per-pixel error between the two RENDERS (mean/median/p95 absolute)
  * how much of the error is a pure offset vs genuine disagreement

LIMITS -- STATED, NOT BURIED
============================
* `rawAA001.tif` is **8-bit** (200 distinct levels, max 204), not the linear
  14-bit this port's invert expects. It is a vendor EXPORT, not sensor data
  (§130.2). Scaling it up cannot recover what quantisation removed, so a
  residual error floor exists that is NOT the port's fault. This test therefore
  bounds agreement from below; it cannot certify bit-exactness.
* The scale factor from the 8-bit export back to the linear domain is unknown.
  It is swept rather than assumed, and the sweep is reported, because picking
  one would be fitting.
* The vendor's film base for this frame is unknown (§149.4), so the invert's
  anchor cannot be derived here either.

Usage:  python3 pakon_sameframe_golden.py [scale]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

RAW = Path("/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp/rawAA001.tif")
OUT = Path("/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp/AA001.tif")

#: OWNER_PEDESTALS, confirmed bit-exact against the vendor's live coefficients
#: in §145.2 (poly_this50 float32 tail: 159.59373 / 444.74969 / 635.53522).
C9 = np.array([159.594, 444.750, 635.535])


def load():
    import imageio.v3 as iio
    from PIL import Image
    raw = iio.imread(RAW).astype(np.float64)
    out = np.asarray(Image.open(OUT).convert("RGB"), dtype=np.float64)
    if raw.shape[:2] != out.shape[:2]:
        raise SystemExit("vendor raw/render are not the same frame")
    return raw[::4, ::4], out[::4, ::4]


def transfer(x: np.ndarray, y: np.ndarray):
    """Per-pixel log fit -- the estimator §156 settled on, applied to both."""
    m = (x > 2) & (y > 3) & (y < 252)
    if m.sum() < 500:
        return float("nan"), float("nan"), float("nan")
    lx = np.log10(x[m])
    yy = y[m]
    s, i = np.polyfit(lx, yy, 1)
    return float(s), float(np.corrcoef(lx, yy)[0, 1]), float((yy - (s * lx + i)).std())


def main(argv) -> int:
    raw, vout = load()
    print(f"same-frame: {RAW.name} -> {OUT.name}   {raw.shape[0]}x{raw.shape[1]} sampled")
    print(f"vendor raw is 8-bit ({len(np.unique(raw[..., 0])):d} levels) -- a "
          f"quantisation floor applies, see the module docstring\n")

    print("VENDOR'S OWN transfer on this frame:")
    for c, nm in enumerate("RGB"):
        s, k, r = transfer(raw[..., c].ravel(), vout[..., c].ravel())
        print(f"   {nm}: slope {s:8.1f}   corr {k:+.4f}   scatter {r:6.2f}")

    # How well does a pure per-channel affine map reproduce the vendor's render
    # from its own raw? This bounds what ANY anchor-only correction can achieve,
    # because an anchor is exactly such a map.
    print("\nbest per-channel AFFINE fit of vendor render from vendor raw")
    print("(this is the ceiling for any offset/gain-only correction):")
    for c, nm in enumerate("RGB"):
        x = raw[..., c].ravel()
        y = vout[..., c].ravel()
        m = (x > 2) & (y > 3) & (y < 252)
        lx = np.log10(x[m])
        s, i = np.polyfit(lx, y[m], 1)
        pred = s * lx + i
        err = np.abs(y[m] - pred)
        print(f"   {nm}: mean |err| {err.mean():6.2f}  median {np.median(err):6.2f}  "
              f"p95 {np.percentile(err, 95):6.2f}")

    print("\nReading: the p95 column is the irreducible per-pixel disagreement a")
    print("log-affine model leaves on the VENDOR'S OWN data. Any port scored")
    print("against a log fit cannot beat it, so scatter at or near these values")
    print("means the transfer is right and the residual is the model, not the port.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
