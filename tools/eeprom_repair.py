#!/usr/bin/env python3
"""Repair the FX2 boot EEPROM with the vendor's exact F-135 personality.

Damage history on this unit:

    healthy (Kodak USB F135.bin)   c0 05 0f 35 f2 07 aa 04 02
    after a blind I2C write sweep  5c 05 0f 35 f2 07 aa 04
    after a failed repair attempt  5c b5 db 05 d9 47 d7 04

Byte 0 is the FX2 format signature. 0xC0 means "take VID/PID from this
EEPROM"; 0x5C is not valid, so the FX2 ignores the EEPROM and enumerates as
its hardwired default 04B4:8613. Hence `--hex` being required and the red
status LED.

The replacement content is not reconstructed. Kodak ships it as
`FirmwareLoader/Personalities/USB F135.bin`, and it matched this unit
byte-for-byte before the damage.

Method: the symmetric counterpart of the read that is known to work. The
stage-1 loader answers 0xA9 with wValue=0, wIndex=0 and returns the boot
EEPROM's first bytes; 0xA2 with the same parameters writes them. This is the
vendor's own path, NOT the raw I2C packet route that caused the damage.

The write is verified by reading back and comparing. Nothing is written unless
the current content is first read successfully.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import usb.core

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pakon_load import Fx2, HexImage, find_unloaded, find_loaded   # noqa: E402

VENDOR_IN, VENDOR_OUT = 0xC0, 0x40
READ, WRITE = 0xA9, 0xA2

HEALTHY = bytes([0xC0, 0x05, 0x0F, 0x35, 0xF2, 0x07, 0xAA, 0x04, 0x02])
VENDOR_FILE = ("/Users/guy/Downloads/Pakon Update 2/fx35install/program files/"
               "Pakon/FirmwareLoader/Personalities/USB F135.bin")


def read_personality(dev, length=8, tries=4):
    last = None
    for _ in range(tries):
        time.sleep(0.15)
        try:
            raw = bytes(dev.ctrl_transfer(VENDOR_IN, READ, 0, 0, length, 5000))
        except usb.core.USBError as exc:
            return f"ERROR: {exc}"
        if last is not None and raw != last:
            return f"UNSTABLE: {last.hex(' ')} then {raw.hex(' ')}"
        last = raw
    return last


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage1", default=None)
    ap.add_argument("--dry-run", action="store_true",
                    help="read and report, write nothing")
    args = ap.parse_args()

    if find_loaded() is not None:
        sys.exit("scanner is loaded; power-cycle it and run this before "
                 "loading firmware")

    here = os.path.dirname(os.path.abspath(__file__))
    stage1_path = args.stage1 or os.path.join(here, os.pardir, "vendor",
                                              "stage1_vendor.hex")
    if not os.path.exists(stage1_path):
        sys.exit(f"stage-1 loader not found at {stage1_path}")

    payload = HEALTHY
    if os.path.exists(VENDOR_FILE):
        with open(VENDOR_FILE, "rb") as fh:
            from_file = fh.read()
        if from_file != HEALTHY:
            sys.exit(f"vendor file disagrees with the expected bytes:\n"
                     f"  file     {from_file.hex(' ')}\n"
                     f"  expected {HEALTHY.hex(' ')}")
        payload = from_file
        print(f"payload verified against {os.path.basename(VENDOR_FILE)}")
    else:
        print("vendor file not found; using the documented bytes")

    dev = find_unloaded()
    if dev is None:
        sys.exit("no unloaded scanner (04b4:8613) found")

    fx2 = Fx2(dev)
    print("uploading stage-1 loader (RAM only)")
    fx2.reset_8051(True)
    fx2.download(HexImage.load(stage1_path), False)
    fx2.reset_8051(False)
    time.sleep(0.5)

    before = read_personality(dev)
    if isinstance(before, str):
        sys.exit(f"refusing to write -- could not read current content\n  {before}")
    print(f"\n  current : {before.hex(' ')}")
    print(f"  target  : {payload.hex(' ')}")

    if before[:8] == payload[:8]:
        print("\n  already correct; nothing to do.")
        return 0

    if args.dry_run:
        print("\n  dry run -- nothing written.")
        return 0

    print("\n  writing...")
    try:
        n = dev.ctrl_transfer(VENDOR_OUT, WRITE, 0, 0, payload, 8000)
        print(f"  wrote {n} byte(s)")
    except usb.core.USBError as exc:
        sys.exit(f"  write failed: {exc}\n  EEPROM unchanged as far as can be told; "
                 f"re-read before retrying")

    time.sleep(0.5)
    after = read_personality(dev)
    if isinstance(after, str):
        print(f"\n  read-back failed: {after}")
        return 1

    print(f"\n  read back: {after.hex(' ')}")
    if after[:8] == payload[:8]:
        print("\n  REPAIRED -- content matches the vendor personality.")
        print("  Power-cycle the scanner. It should now enumerate as")
        print("  0f05:f135 without --hex.")
        return 0
    print("\n  MISMATCH -- the write did not take effect.")
    print(f"    wanted {payload[:8].hex(' ')}")
    print(f"    got    {after[:8].hex(' ')}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
