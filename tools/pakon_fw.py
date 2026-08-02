#!/usr/bin/env python3
"""Download EZ-USB firmware into a Pakon scanner's USB bridge, on macOS.

Replaces the Windows F235Ldr.sys ("ezusb") kernel driver with userspace libusb.

The firmware lives in volatile 8051 RAM. Nothing is written permanently; a
power cycle restores the device to its unloaded state.

  ./pakon_fw.py --list
  ./pakon_fw.py --auto --fw-dir "/path/to/Pakon Update 2"
  ./pakon_fw.py --hex Pakon7.hex
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import usb.core
import usb.util

from pakon_hex import FX2_CPUCS, FX2_INTERNAL_RAM_END, HexImage

# EZ-USB vendor requests.
ANCHOR_LOAD_INTERNAL = 0xA0   # handled by the chip's hardwired boot loader
ANCHOR_LOAD_EXTERNAL = 0xA3   # handled by already-running firmware

VENDOR_OUT = 0x40  # host->device | vendor | device

# Unloaded identities -> firmware image, from F235usb2.inf [WDGTLDR.AddServiceReg]
UNLOADED = {
    (0x0F05, 0xF235, 0xAA05): "Pakon5.hex",
    (0x0F05, 0xF235, 0xAA07): "Pakon7.hex",
    (0x0F05, 0xF235, 0xAA08): "Pakon8.hex",
    (0x0F05, 0xF235, 0x3A05): "Pakon5.hex",   # INF's "REV_::05" spelling
    (0x0F05, 0xF235, 0x3A07): "Pakon7.hex",
    (0x0F05, 0xF235, 0x3A08): "Pakon8.hex",
    (0x04B4, 0x8613, None):   "PknInit.hex",  # bare Cypress FX2
    (0x0547, 0x1002, None):   "PknInit.hex",  # bare Anchor EZ-USB
    (0x4705, 0x0211, None):   "PknInit.hex",  # development board
}

# Loaded identities, from the descriptors embedded in each image.
LOADED = {
    (0x0F05, 0xF135): "F-135 / F-135 Plus",
    (0x0F05, 0x35F2): "F-235",
    (0x0F05, 0xF335): "F-235 / F-335",
}


def find_unloaded():
    for dev in usb.core.find(find_all=True):
        for (vid, pid, rev), fw in UNLOADED.items():
            if dev.idVendor == vid and dev.idProduct == pid:
                if rev is None or dev.bcdDevice == rev:
                    return dev, fw
    return None, None


def find_loaded():
    for dev in usb.core.find(find_all=True):
        if (dev.idVendor, dev.idProduct) in LOADED:
            return dev
    return None


def list_devices() -> int:
    dev = find_loaded()
    if dev is not None:
        print(f"LOADED    {dev.idVendor:04x}:{dev.idProduct:04x} "
              f"bcdDevice={dev.bcdDevice:04x}  {LOADED[(dev.idVendor, dev.idProduct)]}")
        print("          already running scanner firmware - nothing to do")
        return 0
    dev, fw = find_unloaded()
    if dev is not None:
        print(f"UNLOADED  {dev.idVendor:04x}:{dev.idProduct:04x} "
              f"bcdDevice={dev.bcdDevice:04x}  needs {fw}")
        return 0
    print("no Pakon scanner found on the USB bus")
    return 1


def cpu_reset(dev, hold: bool, timeout: int = 2000) -> None:
    """Assert (hold=True) or release the 8051 reset line via CPUCS."""
    dev.ctrl_transfer(VENDOR_OUT, ANCHOR_LOAD_INTERNAL, FX2_CPUCS, 0,
                      bytes([1 if hold else 0]), timeout)


def download(dev, img: HexImage, chunk: int, force_internal: bool,
             verbose: bool) -> tuple[int, int]:
    ok = failed = 0
    for addr, data in img.chunked(chunk):
        req = ANCHOR_LOAD_INTERNAL
        if not force_internal and addr >= FX2_INTERNAL_RAM_END:
            req = ANCHOR_LOAD_EXTERNAL
        try:
            n = dev.ctrl_transfer(VENDOR_OUT, req, addr, 0, data, 5000)
            if n != len(data):
                raise usb.core.USBError(f"short write {n}/{len(data)}")
            ok += 1
            if verbose:
                print(f"  0x{addr:04X} +{len(data):<5d} req=0x{req:02X} ok")
        except usb.core.USBError as exc:
            failed += 1
            print(f"  0x{addr:04X} +{len(data):<5d} req=0x{req:02X} FAILED: {exc}",
                  file=sys.stderr)
    return ok, failed


def wait_for_reenumeration(timeout: float = 15.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        dev = find_loaded()
        if dev is not None:
            return dev
        time.sleep(0.4)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="show scanner state and exit")
    ap.add_argument("--auto", action="store_true",
                    help="pick the firmware image matching the attached device")
    ap.add_argument("--hex", help="explicit Intel HEX image to download")
    ap.add_argument("--fw-dir", default=".",
                    help="directory to search for firmware images (--auto)")
    ap.add_argument("--chunk", type=int, default=1024, help="max bytes per transfer")
    ap.add_argument("--force-internal", action="store_true",
                    help="use request 0xA0 for every block, even above 0x4000")
    ap.add_argument("--dry-run", action="store_true",
                    help="parse and plan, but send nothing")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if args.list:
        return list_devices()

    if find_loaded() is not None:
        print("scanner is already loaded; power-cycle it to reload firmware")
        return 0

    dev, auto_fw = find_unloaded()
    if dev is None:
        print("no unloaded Pakon scanner found", file=sys.stderr)
        return 1

    path = args.hex
    if path is None:
        if not args.auto:
            print("specify --hex FILE or --auto", file=sys.stderr)
            return 2
        for root, _dirs, files in os.walk(args.fw_dir):
            for f in files:
                if f.lower() == auto_fw.lower():
                    path = os.path.join(root, f)
                    break
            if path:
                break
        if path is None:
            print(f"could not find {auto_fw} under {args.fw_dir}", file=sys.stderr)
            return 2

    img = HexImage.load(path)
    blocks = img.chunked(args.chunk)
    ext = sum(1 for a, _ in blocks if a >= FX2_INTERNAL_RAM_END)

    print(f"device   {dev.idVendor:04x}:{dev.idProduct:04x} bcdDevice={dev.bcdDevice:04x}")
    print(f"firmware {path}")
    print(f"         {img.total_bytes()} bytes in {len(blocks)} block(s)"
          f"; {ext} above FX2 internal RAM")
    if args.dry_run:
        for a, d in blocks:
            req = 0xA0 if (args.force_internal or a < FX2_INTERNAL_RAM_END) else 0xA3
            print(f"  would send 0x{a:04X} +{len(d)} via 0x{req:02X}")
        return 0

    try:
        print("holding 8051 in reset...")
        cpu_reset(dev, True)
        print("downloading...")
        ok, failed = download(dev, img, args.chunk, args.force_internal, args.verbose)
        print(f"  {ok} block(s) accepted, {failed} failed")
        print("releasing 8051 reset...")
        cpu_reset(dev, False)
    except usb.core.USBError as exc:
        print(f"USB error: {exc}", file=sys.stderr)
        if "Access" in str(exc) or "permission" in str(exc).lower():
            print("hint: try running with sudo", file=sys.stderr)
        return 1

    print("waiting for re-enumeration...")
    new = wait_for_reenumeration()
    if new is None:
        print("device did not re-enumerate as a loaded scanner", file=sys.stderr)
        print("power-cycle the scanner before retrying", file=sys.stderr)
        return 1

    print(f"SUCCESS  {new.idVendor:04x}:{new.idProduct:04x} "
          f"bcdDevice={new.bcdDevice:04x}  {LOADED[(new.idVendor, new.idProduct)]}")
    try:
        print(f"         manufacturer={usb.util.get_string(new, new.iManufacturer)!r} "
              f"product={usb.util.get_string(new, new.iProduct)!r}")
    except usb.core.USBError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
