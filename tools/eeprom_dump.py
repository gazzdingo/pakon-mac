#!/usr/bin/env python3
"""Read and save every EEPROM, using the vendor's own control-transfer path.

This does NOT use the raw I2C packet route. That route is what damaged this
unit's boot EEPROM earlier in the project: a sweep of blind writes across what
were assumed to be board addresses but were in fact I2C device addresses.

The vendor path, recovered from TLB.dll (fcn.10015d80, IOCTL 0x222059 =
IOCTL_EZUSB_VENDOR_OR_CLASS_REQUEST):

    bRequest  0xA9   read        0xA2   write
    wValue    ((n | 0x50) << 1) | readBit      n <= 7
    wIndex    0x1234

`(n | 0x50) << 1` is a 7-bit I2C address in the 0x50-0x57 serial-EEPROM range
shifted into 8-bit form, with bit 0 as the R/W flag. So n selects which EEPROM.

Read-only. This tool never writes. Each device is dumped to its own file and
verified by reading twice -- a stable second read is the difference between
real content and a floating bus.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import usb.core
import usb.util

import pakon_usb_guard as guard

VENDOR_READ = 0xA9
WINDEX = 0x1234
REQ_TYPE_IN = 0xC0            # device-to-host, vendor, device


def open_dev():
    d = usb.core.find(idVendor=0x0F05, idProduct=0xF135)
    if d is None:
        d = usb.core.find(idVendor=0x04B4, idProduct=0x8613)
    if d is None:
        sys.exit("no Pakon or bare-FX2 device found")
    return d


def read_eeprom(d, n, length, timeout=3000):
    """One EEPROM, selected by index n (0..7 -> I2C 0x50..0x57)."""
    wvalue = ((n | 0x50) << 1) | 1
    try:
        return bytes(guard.ctrl_transfer(d, REQ_TYPE_IN, VENDOR_READ,
                                         wvalue, WINDEX, length, timeout))
    except usb.core.USBError as exc:
        return f"ERROR: {exc}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.expanduser("~/pakon-eeprom-backup"),
                    help="directory to save dumps into")
    ap.add_argument("--length", type=int, default=256,
                    help="bytes to read per device (default 256)")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    d = open_dev()
    print(f"device {d.idVendor:04x}:{d.idProduct:04x}")
    print(f"saving to {args.out}\n")

    saved = 0
    for n in range(8):
        i2c7 = n | 0x50
        first = read_eeprom(d, n, args.length)
        if isinstance(first, str):
            print(f"  n={n} (I2C {i2c7:#04x}): {first}")
            continue
        time.sleep(0.05)
        second = read_eeprom(d, n, args.length)
        stable = isinstance(second, bytes) and second == first
        allsame = len(set(first)) <= 1

        path = os.path.join(args.out, f"eeprom_n{n}_i2c{i2c7:02x}.bin")
        with open(path, "wb") as fh:
            fh.write(first)
        saved += 1

        note = "stable" if stable else "UNSTABLE (re-read differs)"
        if allsame:
            note += f", all bytes {first[0]:#04x} -- probably absent"
        print(f"  n={n} (I2C {i2c7:#04x}): {len(first)} bytes, {note}")
        print(f"      first 16: {first[:16].hex(' ')}")
        print(f"      saved -> {path}")

    print(f"\n  {saved} dump(s) written to {args.out}")
    print("  Nothing was written to the scanner.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
