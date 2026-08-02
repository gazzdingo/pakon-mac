#!/usr/bin/env python3
"""Firmware loader for Pakon F-135/235/335 scanners on macOS.

Reimplements the vendor's two-stage EZ-USB load sequence in userspace, replacing
the Windows F235Ldr.sys kernel driver. No kext or DriverKit driver is required.

THE SEQUENCE (as implemented by the vendor driver):

    1. hold the 8051 in reset
    2. download a STAGE-1 LOADER into internal RAM via 0xA0
    3. release the 8051                    -> stage-1 runs, and it services 0xA3
    4. vendor request 0xA9 PAKON_GET_PERSONALITY -> EEPROM type + VID/PID/rev
    5. choose the firmware image from that identity
    6. download the real firmware IN TWO PASSES:
         pass 1: records with address >  0x1B3F  via 0xA3, CPU STILL RUNNING
         pass 2: hold reset, then address <= 0x1B3F via 0xA0
       Pass 1 must come first: pass 2 overwrites the stage-1 loader that is
       servicing 0xA3.
    7. reset and release -> the real firmware runs and re-enumerates

WHY 0x1B3F: that is MAX_INTERNAL_ADDRESS for the AN2131Q. The vendor driver
applies it to every model, including FX2 parts whose internal RAM actually runs
to 0x3FFF. So on an FX2, addresses 0x1B40-0x3FFF go over 0xA3 even though 0xA0
would also reach them.

THE STAGE-1 LOADER is not included here. It is embedded as an INTEL_HEX_RECORD
array in FX35Loader/Loader.c of the FX35 driver project:

    https://github.com/ktkaufman03/FX35

Obtain it yourself and convert it with tools/extract_stage1.py. This tool looks
for it at vendor/stage1_vendor.hex.

Nothing written here is permanent: EZ-USB RAM is volatile and a power cycle
restores the scanner to its unloaded state.
"""
from __future__ import annotations

import argparse
import os
import struct
import sys
import time

import usb.core
import usb.util

from pakon_hex import HexImage

VENDOR_OUT, VENDOR_IN = 0x40, 0xC0

ANCHOR_LOAD_INTERNAL = 0xA0     # implemented by the EZ-USB core
ANCHOR_LOAD_EXTERNAL = 0xA3     # implemented by stage-1 firmware, not hardware
PAKON_GET_PERSONALITY = 0xA9    # Pakon-specific

MAX_INTERNAL_ADDRESS = 0x1B3F
CPUCS_EZUSB, CPUCS_FX2 = 0x7F92, 0xE600

# Records are sent one per control transfer, matching the vendor driver's
# MAX_INTEL_HEX_RECORD_LENGTH. The stage-1 loader's 0xA3 handler is not known to
# accept more.
RECORD_LEN = 16

LOADED = {
    (0x0F05, 0xF135): "F-135 / F-135 Plus",
    (0x0F05, 0x35F2): "F-235",
    (0x0F05, 0xF335): "F-235 / F-335",
}

# Registry map from the vendor INF, [WDGTLDR.AddServiceReg]. The key is
# "%4.4X_%4.4X" % (wProductId, wRevision).
FIRMWARE_BY_PERSONALITY = {
    "F235_AA05": "Pakon5.hex",
    "F235_AA07": "Pakon7.hex",
    "F235_AA08": "Pakon8.hex",
}


class Fx2:
    def __init__(self, dev):
        self.dev = dev

    def vendor_out(self, request: int, addr: int, data: bytes) -> None:
        n = self.dev.ctrl_transfer(VENDOR_OUT, request, addr, 0, data, 5000)
        if n != len(data):
            raise usb.core.USBError(
                f"short write at {addr:#06x}: {n}/{len(data)}")

    def reset_8051(self, hold: bool) -> None:
        """Mirror the vendor's Ezusb_8051Reset: try the AN2131 CPUCS then the
        FX2 CPUCS. Whichever the part does not implement simply fails."""
        payload = bytes([1 if hold else 0])
        ok = False
        for reg in (CPUCS_EZUSB, CPUCS_FX2):
            try:
                self.vendor_out(ANCHOR_LOAD_INTERNAL, reg, payload)
                ok = True
            except usb.core.USBError:
                pass
        if not ok:
            raise usb.core.USBError("could not write either CPUCS register")
        time.sleep(0.05)

    def personality(self, attempts: int = 4) -> dict:
        """Query 0xA9 PAKON_GET_PERSONALITY.

        The leading EEPROM-type byte is NOT reliable immediately after the
        stage-1 loader starts: the same F-135 has returned 0xC0 and 0x5c on
        successive runs, with the remaining seven bytes identical. Read it a
        few times and prefer a result whose id is a documented EEPROM type.
        Never select firmware on this byte alone -- see main().
        """
        last = None
        for i in range(attempts):
            time.sleep(0.15 * (i + 1))
            raw = bytes(self.dev.ctrl_transfer(VENDOR_IN, PAKON_GET_PERSONALITY,
                                               0, 0, 8, 5000))
            pid_, vid, prod, rev, unk = struct.unpack("<BHHHB", raw)
            last = {"raw": raw, "id": pid_, "vid": vid,
                    "pid": prod, "rev": rev, "unk": unk, "settled": False}
            if pid_ in (0xC0, 0xC2):
                last["settled"] = True
                return last
        return last

    def download(self, img: HexImage, verbose: bool = False) -> None:
        """Two-pass download, external first. See module docstring."""
        records = []
        for addr, data in img.segments():
            for off in range(0, len(data), RECORD_LEN):
                records.append((addr + off, data[off:off + RECORD_LEN]))

        ext = [(a, d) for a, d in records if a > MAX_INTERNAL_ADDRESS]
        internal = [(a, d) for a, d in records if a <= MAX_INTERNAL_ADDRESS]

        # Pass 1 -- external, with the 8051 running the stage-1 loader.
        for a, d in ext:
            self.vendor_out(ANCHOR_LOAD_EXTERNAL, a, d)
        if verbose:
            print(f"    pass 1: {sum(len(d) for _a, d in ext)} byte(s) "
                  f"via 0xA3 ({len(ext)} records)")

        # Pass 2 -- internal, with the 8051 halted. This clobbers stage-1.
        self.reset_8051(True)
        for a, d in internal:
            self.vendor_out(ANCHOR_LOAD_INTERNAL, a, d)
        if verbose:
            print(f"    pass 2: {sum(len(d) for _a, d in internal)} byte(s) "
                  f"via 0xA0 ({len(internal)} records)")


def find_unloaded():
    for dev in usb.core.find(find_all=True):
        if (dev.idVendor, dev.idProduct) in ((0x0F05, 0xF235), (0x04B4, 0x8613),
                                             (0x0547, 0x1002), (0x4705, 0x0211)):
            return dev
    return None


def find_loaded():
    for dev in usb.core.find(find_all=True):
        if (dev.idVendor, dev.idProduct) in LOADED:
            return dev
    return None


def locate(name: str, root: str) -> str | None:
    for base, _dirs, files in os.walk(root):
        for f in files:
            if f.lower() == name.lower():
                return os.path.join(base, f)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fw-dir", default=".", help="directory holding the .hex images")
    ap.add_argument("--stage1", default=None, help="stage-1 loader hex")
    ap.add_argument("--hex", default=None, help="override the firmware image")
    ap.add_argument("--timeout", type=float, default=25.0)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    stage1_path = args.stage1 or os.path.join(here, os.pardir,
                                              "vendor", "stage1_vendor.hex")
    if not os.path.exists(stage1_path):
        print(f"stage-1 loader not found at {stage1_path}\n"
              "Obtain it from https://github.com/ktkaufman03/FX35 and convert\n"
              "with tools/extract_stage1.py -- see this file's docstring.",
              file=sys.stderr)
        return 2

    if find_loaded() is not None:
        print("scanner is already loaded; power-cycle it to reload firmware")
        return 0

    dev = find_unloaded()
    if dev is None:
        print("no unloaded Pakon scanner found", file=sys.stderr)
        return 1

    fx2 = Fx2(dev)
    print(f"device   {dev.idVendor:04x}:{dev.idProduct:04x} "
          f"bcdDevice={dev.bcdDevice:04x}")

    # ---- stage 1 -------------------------------------------------------
    print("stage 1: downloading loader")
    stage1 = HexImage.load(stage1_path)
    fx2.reset_8051(True)
    fx2.download(stage1, args.verbose)
    fx2.reset_8051(False)
    time.sleep(0.3)

    # ---- identity ------------------------------------------------------
    try:
        p = fx2.personality()
    except usb.core.USBError as exc:
        print(f"PAKON_GET_PERSONALITY (0xA9) failed: {exc}", file=sys.stderr)
        print("the stage-1 loader is not responding -- it did not start",
              file=sys.stderr)
        return 1

    key = f"{p['pid']:04X}_{p['rev']:04X}"
    print(f"personality: id={p['id']:#04x} vid={p['vid']:04x} "
          f"pid={p['pid']:04x} rev={p['rev']:04x} -> key {key}")
    print(f"             raw={p['raw'].hex(' ')}")

    # Firmware selection.
    #
    # The USB identity of the UNLOADED device is authoritative: the INF maps
    # PID_REV directly to an image (F235_AA07 -> Pakon7.hex), and that mapping
    # cannot be wrong for a device that enumerated with those IDs.
    #
    # The 0xA9 personality query is only a cross-check. It is NOT reliable
    # enough to select firmware on its own: observed returning something other
    # than 0xC0 on an otherwise healthy F-135, which sent an earlier version of
    # this code down the PknInit.hex path and loaded *F-235* firmware onto an
    # F-135. The scanner lit a fault LED. Never let that happen again.
    usb_key = f"{dev.idProduct:04X}_{dev.bcdDevice:04X}"

    if args.hex:
        fw_path = args.hex
    elif p["id"] == 0xC2:
        print("EEPROM type C2: firmware is already resident, nothing to load")
        return 0
    elif usb_key in FIRMWARE_BY_PERSONALITY:
        name = FIRMWARE_BY_PERSONALITY[usb_key]
        if key != usb_key:
            print(f"  note: personality key {key} disagrees with USB identity "
                  f"{usb_key}; trusting USB identity")
        fw_path = locate(name, args.fw_dir)
    elif key in FIRMWARE_BY_PERSONALITY:
        fw_path = locate(FIRMWARE_BY_PERSONALITY[key], args.fw_dir)
    else:
        # Deliberately do NOT fall back to PknInit.hex. It carries the F-235
        # descriptor, so loading it onto another model produces a scanner that
        # enumerates as the wrong device and faults.
        print(f"refusing to guess: USB identity {usb_key} and personality "
              f"{key} both unrecognised.\n"
              f"Known: {', '.join(sorted(FIRMWARE_BY_PERSONALITY))}.\n"
              f"Use --hex to force a specific image.", file=sys.stderr)
        return 1

    if not fw_path or not os.path.exists(fw_path):
        print(f"firmware image not found under {args.fw_dir}", file=sys.stderr)
        return 2

    # ---- stage 2 -------------------------------------------------------
    img = HexImage.load(fw_path)
    print(f"stage 2: {fw_path} ({img.total_bytes()} bytes)")
    fx2.download(img, args.verbose)

    print("resetting to start firmware...")
    fx2.reset_8051(True)
    fx2.reset_8051(False)

    print("waiting for re-enumeration...")
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        new = find_loaded()
        if new is not None:
            # Sanity check: the loaded PID must match the image we chose.
            # Loading e.g. PknInit.hex (F-235) onto an F-135 makes the scanner
            # enumerate as an F-235 and raises a fault LED on the unit.
            expected = {"pakon5.hex": 0x35F2, "pknInit.hex".lower(): 0x35F2,
                        "pakon7.hex": 0xF135, "pakon8.hex": 0xF335}
            want = expected.get(os.path.basename(fw_path).lower())
            if want is not None and new.idProduct != want:
                print(f"WARNING: loaded {os.path.basename(fw_path)} but the "
                      f"device came up as {new.idProduct:04x}, expected "
                      f"{want:04x}.", file=sys.stderr)
                print("         This is a MODEL MISMATCH. Power-cycle the "
                      "scanner before using it.", file=sys.stderr)
                return 1
            print(f"SUCCESS  {new.idVendor:04x}:{new.idProduct:04x} "
                  f"bcdDevice={new.bcdDevice:04x}  "
                  f"{LOADED[(new.idVendor, new.idProduct)]}")
            try:
                print(f"         manufacturer="
                      f"{usb.util.get_string(new, new.iManufacturer)!r} "
                      f"product={usb.util.get_string(new, new.iProduct)!r}")
            except usb.core.USBError:
                pass
            return 0
        time.sleep(0.25)

    print("device did not re-enumerate", file=sys.stderr)
    print("power-cycle the scanner before retrying", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
