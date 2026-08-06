#!/usr/bin/env python3
"""Read the CCD stream off EP 0x86 and report levels. READ ONLY.

EP 0x86 is a bulk IN endpoint carrying 3-channel 16-bit CCD data at roughly
30 MB/s (docs/06-roadmap.md:27, :233). Reading it is a read: no register is
written, no acquisition is started, nothing is enabled. Whatever the sensor
path is already producing is what shows up here.

WHY FLUSH FIRST
---------------
docs/06-roadmap.md:139 -- the FIFO is free-running and stalls full of stale
data. A first read returns whatever was sitting in it, which may be minutes
old. So this discards several buffers before measuring, and reports the
before/after separately so a stale first buffer is visible rather than silently
averaged in.

REFERENCE POINT
---------------
docs/06-roadmap.md:111, :161 record a dark baseline mean of about 1242-1244,
and a genuine illumination event showing as a jump above it. With the lamp off
-- which it is, see tools/lamp_status.py for why it stays off until the unit's
calibrated LED values are recovered -- a mean near that baseline means the
sensor path is alive and reading dark, which is the expected healthy result.

A flat zero, a pinned maximum, or no data at all would each mean something is
wrong. Distinguishing those is the point of this tool.
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


def grab(dev, size, timeout):
    try:
        return bytes(dev.read(EP_IMAGE, size, timeout))
    except usb.core.USBError:
        return None


def stats(buf):
    if not buf or len(buf) < 2:
        return None
    vals = [int.from_bytes(buf[i:i + 2], "little")
            for i in range(0, len(buf) - 1, 2)]
    return {"n": len(vals), "mean": statistics.mean(vals),
            "min": min(vals), "max": max(vals)}


def show(label, buf):
    s = stats(buf)
    if s is None:
        print(f"  {label:<10} no data")
        return None
    print(f"  {label:<10} {len(buf):6d} B  n={s['n']:6d}  "
          f"mean={s['mean']:9.1f}  min={s['min']:6d}  max={s['max']:6d}")
    return s


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--size", type=lambda s: int(s, 0), default=0x4000,
                    help="bytes per read (default 16384)")
    ap.add_argument("--flush", type=int, default=8,
                    help="buffers to discard before measuring")
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=3000)
    args = ap.parse_args()

    dev = open_scanner()
    print(f"scanner open: {VID:#06x}:{PID:#06x}   EP {EP_IMAGE:#04x}\n")

    first = grab(dev, args.size, args.timeout)
    print("before flush (may be stale FIFO contents):")
    show("stale", first)

    for _ in range(args.flush):
        grab(dev, args.size, args.timeout)

    print("\nafter flush:")
    got = []
    for i in range(args.samples):
        s = show(f"sample {i}", grab(dev, args.size, args.timeout))
        if s:
            got.append(s)

    if not got:
        print("\nNo data on EP 0x86 -- the stream is not running.")
        return 1

    mean = statistics.mean(s["mean"] for s in got)
    print(f"\nmean across samples: {mean:.1f}   "
          f"(documented dark baseline ~{DARK_BASELINE})")
    if abs(mean - DARK_BASELINE) < 200:
        print("  -> consistent with the documented DARK baseline: the sensor "
              "path is alive and reading dark, as expected with the lamp off.")
    elif mean == 0:
        print("  -> flat zero: nothing is driving the stream.")
    else:
        print("  -> off the documented baseline; worth investigating rather "
              "than assuming either way.")
    print("\nread only -- no register was written and no acquisition started.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
