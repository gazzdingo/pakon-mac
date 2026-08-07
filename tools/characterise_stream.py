#!/usr/bin/env python3
"""Characterise the EP 0x86 CCD stream. READ ONLY -- no register is written.

The oldest blocker in this project is `docs/06`'s finding that EP 0x86 carries
data that does not respond to illumination, mean pinned near 1242. That was
recorded while U34 -- the motor PIC, which drives CCD timing -- had an erased
flash row and hung on every cold boot. U34 is now repaired, and the stream looks
different (mean ~2531 with a real distribution).

This asks three questions, all without writing anything:

  1. IS IT STRUCTURED?  Autocorrelate for a repeating line length. A line-scan
     CCD clocking out fixed-length lines should show a strong periodic peak.
     Noise will not.

  2. DOES IT RESPOND TO LIGHT?  Capture, let the operator change the
     illumination, capture again, compare means. This is `docs/06`'s own
     light-meter test, re-run against repaired hardware. If the mean moves, the
     sensor path is live and the blocker is gone.

  3. IS IT STABLE?  Repeated captures under unchanged conditions, to separate a
     real signal from drift.

FLUSH FIRST: `docs/06:139` -- the FIFO free-runs and stalls full of stale data.
Every measurement here discards buffers before sampling, and the stale buffer is
reported separately so it cannot be silently averaged in.
"""
from __future__ import annotations

import argparse
import statistics
import sys

try:
    import usb.core
    import usb.util
except ImportError:
    sys.exit("pyusb is required:  pip install pyusb")

VID, PID = 0x0F05, 0xF135
EP_IMAGE = 0x86
DARK_BASELINE = 1242              # docs/06-roadmap.md:161


def open_scanner():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        sys.exit(f"scanner {VID:#06x}:{PID:#06x} not found -- run "
                 "tools/pakon_load.py first")
    try:
        dev.set_configuration()
    except usb.core.USBError:
        pass
    usb.util.claim_interface(dev, 0)
    try:
        dev.clear_halt(EP_IMAGE)
    except usb.core.USBError:
        pass
    return dev


def grab(dev, size, timeout=3000):
    try:
        return bytes(dev.read(EP_IMAGE, size, timeout))
    except usb.core.USBError:
        return None


def flushed(dev, size, flush=8):
    for _ in range(flush):
        grab(dev, size)
    return grab(dev, size)


def u16(buf):
    return [int.from_bytes(buf[i:i + 2], "little") for i in range(0, len(buf) - 1, 2)]


def describe(vals):
    return (f"n={len(vals):6d}  mean={statistics.mean(vals):9.1f}  "
            f"sd={statistics.pstdev(vals):8.1f}  "
            f"min={min(vals):6d}  max={max(vals):6d}")


def autocorr_period(vals, lo=3, hi=20000, stride=11):
    """Normalised autocorrelation: r(lag) = sum(d[i]d[i+lag]) / ((n-lag)*var).

    Normalising by the OVERLAP (n-lag) and the variance is what keeps r in
    [-1, 1]. An earlier version here divided by the full-length sum of squares
    while sub-sampling with a stride, which produced r > 1 and a false
    "structured" verdict on what was really slow drift. If you see |r| > 1, the
    normalisation is wrong -- do not report the result.

    Real structure shows as discrete peaks at INTEGER MULTIPLES of a
    fundamental. Drift shows as a smooth monotonic decline with no harmonics.
    Check which you have before believing a period.
    """
    import statistics as _s
    n = len(vals)
    hi = min(hi, n // 3)
    if hi <= lo:
        return []
    mu = _s.mean(vals)
    var = _s.pvariance(vals) or 1.0
    dev = [x - mu for x in vals]
    out = []
    for lag in range(lo, hi):
        m = n - lag
        acc = 0.0
        for i in range(0, m, stride):
            acc += dev[i] * dev[i + lag]
        out.append(((acc * stride) / (m * var), lag))
    out.sort(reverse=True)
    return out[:12]


def fundamental(peaks, tol=0.02):
    """Smallest lag of which the top peaks are integer multiples."""
    if not peaks:
        return None
    lags = sorted(l for _, l in peaks)
    for cand in lags:
        if all(abs(round(l / cand) - l / cand) < tol for l in lags):
            return cand
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--size", type=lambda s: int(s, 0), default=0x20000,
                    help="bytes per capture (default 131072)")
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--label", default="", help="tag for this run, e.g. 'torch on'")
    ap.add_argument("--no-autocorr", action="store_true")
    args = ap.parse_args()

    dev = open_scanner()
    tag = f"  [{args.label}]" if args.label else ""
    print(f"scanner {VID:#06x}:{PID:#06x}  EP {EP_IMAGE:#04x}{tag}\n")

    stale = grab(dev, args.size)
    if stale:
        print("stale (pre-flush):  " + describe(u16(stale)))

    means = []
    last = None
    for i in range(args.repeat):
        buf = flushed(dev, args.size)
        if not buf:
            print(f"  capture {i}: NO DATA")
            continue
        v = u16(buf)
        last = v
        means.append(statistics.mean(v))
        print(f"  capture {i}:       " + describe(v))

    if not means:
        print("\nno data on EP 0x86 -- the stream is not running.")
        return 1

    m = statistics.mean(means)
    spread = max(means) - min(means)
    print(f"\nmean of means: {m:.1f}   spread across captures: {spread:.1f}")
    print(f"documented dark baseline: ~{DARK_BASELINE}")

    if not args.no_autocorr and last:
        print("\nautocorrelation -- looking for a repeating line length:")
        top = autocorr_period(last)
        if not top:
            print("  buffer too small")
        else:
            for score, lag in top[:5]:
                bar = "#" * max(0, min(40, int(score * 40)))
                print(f"  lag {lag:5d} samples ({lag*2:6d} B)  r={score:+.3f} {bar}")
            best, bestlag = top[0]
            if best > 0.30:
                print(f"\n  STRUCTURED: strong period at {bestlag} samples "
                      f"({bestlag*2} bytes). Consistent with a fixed line length.")
            elif best > 0.12:
                print(f"\n  weak periodicity at {bestlag} samples -- suggestive, "
                      "not conclusive. Try a larger --size.")
            else:
                print("\n  NO clear period. Either unstructured, or the line "
                      "length exceeds the search window.")

    print(f"\nread only -- nothing written, no acquisition started.")
    print("To test light response: run with --label, change the illumination, "
          "run again, and compare the means.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
