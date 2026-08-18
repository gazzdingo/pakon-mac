#!/usr/bin/env python3
"""Back up every EEPROM, using the stage-1 loader and the vendor's parameters.

Two things have to be right, and this project got both wrong before.

1. The request is only serviced by the stage-1 loader. The bare FX2 ROM
   implements 0xA0 (RAM download) and nothing else, so 0xA9 times out before
   stage 1 runs. The application firmware (Pakon7.hex) answers 0xA9 with a
   fixed buffer that is identical for every device address -- convincing, and
   completely bogus.

2. The parameters matter. `pakon_load.py` issues 0xA9 with wValue=0, wIndex=0
   and treats the result as a "personality" blob. The vendor instead sends,
   per fcn.100160a0 in TLB.dll:

       bRequest  0xA9  read      (0xA2 write)
       wValue    ((n | 0x50) << 1) | readBit        n <= 7
       wIndex    0x1234

   `(n | 0x50) << 1` is a 7-bit I2C address in the 0x50-0x57 serial-EEPROM
   range shifted into 8-bit form, bit 0 being R/W. Reading with wValue=0 and
   wIndex=0 is not addressing any EEPROM at all, which is very likely why a
   healthy part has been read back as garbage in this project.

Read-only. Nothing is ever written. Each device is read twice and compared,
and the results are cross-checked against each other -- if every address
returns identical bytes, the read is not addressing anything.

Run it with the scanner power-cycled and NOT yet loaded (04b4:8613).
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time

import usb.core

import pakon_usb_guard as guard
import usb.util

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pakon_load import Fx2, HexImage, find_unloaded   # noqa: E402

VENDOR_IN = 0xC0
READ = 0xA9
WINDEX = 0x1234


def read_one(dev, n, length, wvalue=None, windex=WINDEX, timeout=4000):
    if wvalue is None:
        wvalue = ((n | 0x50) << 1) | 1
    try:
        return bytes(guard.ctrl_transfer(dev, VENDOR_IN, READ, wvalue,
                                         windex, length, timeout))
    except usb.core.USBError as exc:
        return f"ERROR: {exc}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.expanduser("~/pakon-eeprom-backup"))
    ap.add_argument("--length", type=int, default=256)
    ap.add_argument("--stage1", default=None)
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    stage1_path = args.stage1 or os.path.join(here, os.pardir, "vendor",
                                              "stage1_vendor.hex")
    if not os.path.exists(stage1_path):
        sys.exit(f"stage-1 loader not found at {stage1_path}")

    dev = find_unloaded()
    if dev is None:
        sys.exit("no unloaded scanner (04b4:8613) found -- power-cycle it and "
                 "do NOT load firmware first")

    print(f"device {dev.idVendor:04x}:{dev.idProduct:04x}")
    fx2 = Fx2(dev)
    print("uploading stage-1 loader (RAM only, no EEPROM write)")
    fx2.reset_8051(True)
    fx2.download(HexImage.load(stage1_path), False)
    fx2.reset_8051(False)
    time.sleep(0.4)

    os.makedirs(args.out, exist_ok=True)
    digests, results = {}, {}
    print(f"\nreading with the vendor's parameters (wIndex {WINDEX:#06x}):")
    for n in range(8):
        i2c7 = n | 0x50
        first = read_one(dev, n, args.length)
        if isinstance(first, str):
            print(f"  n={n} I2C {i2c7:#04x}: {first}")
            continue
        time.sleep(0.05)
        second = read_one(dev, n, args.length)
        stable = isinstance(second, bytes) and second == first
        md5 = hashlib.md5(first).hexdigest()
        digests.setdefault(md5, []).append(n)
        results[n] = first
        print(f"  n={n} I2C {i2c7:#04x}: {len(first)}B  "
              f"{'stable' if stable else 'UNSTABLE'}  md5 {md5[:12]}  "
              f"distinct {len(set(first))}")
        print(f"      {first[:16].hex(' ')}")

    if not results:
        print("\n  nothing read.")
        return 1

    if len(digests) == 1 and len(results) > 1:
        print("\n  WARNING: every address returned identical bytes.")
        print("  That means the read is not addressing individual devices;")
        print("  do NOT treat these files as a backup.")
        suffix = ".SUSPECT"
    else:
        print(f"\n  {len(digests)} distinct content(s) across {len(results)} "
              f"address(es) -- addressing is working.")
        suffix = ""

    for n, data in results.items():
        path = os.path.join(args.out, f"eeprom_n{n}_i2c{(n | 0x50):02x}.bin{suffix}")
        with open(path, "wb") as fh:
            fh.write(data)
        print(f"  saved {path}")
    print("\n  Nothing was written to the scanner.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
