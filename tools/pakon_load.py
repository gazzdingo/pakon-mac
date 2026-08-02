#!/usr/bin/env python3
"""Two-stage firmware loader for Pakon F-135/235/335 scanners on macOS.

Replaces the Windows F235Ldr.sys ("ezusb") kernel driver entirely.

Why two stages: the FX2 boot loader can only write internal RAM (0x0000-0x3FFF)
but the firmware images extend to 0x47AC/0x492E, which lives in external SRAM.
Request 0xA3 is serviced by firmware, not hardware, so it cannot be used before
firmware runs. Instead we stage the high payload in an unused internal-RAM gap
and run a tiny 8051 copier (stage1_copier.c) that MOVXs it into external SRAM.

Nothing is written permanently -- FX2 RAM is volatile and a power cycle restores
the unloaded state.

  ./pakon_load.py --auto --fw-dir "/path/to/Pakon Update 2"
  ./pakon_load.py --auto --fw-dir ... --verbose
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import usb.core
import usb.util

from pakon_hex import FX2_CPUCS, FX2_INTERNAL_RAM_END, HexImage
from pakon_fw import (LOADED, UNLOADED, VENDOR_OUT, ANCHOR_LOAD_INTERNAL,
                      find_loaded, find_unloaded)

VENDOR_IN = 0xC0

# Staging area.
#
# The images leave two gaps in internal RAM: 0x0056-0x0FFF and 0x10BE-0x1FFF.
# Stage in the FIRST gap, after the copier (which occupies 0x0100-0x0241).
#
# Do NOT stage in the second gap. It sits immediately after the USB descriptor
# block at 0x1000-0x10BD, and leaving 2 KB of stale firmware bytes adjacent to
# the descriptors is a plausible way to corrupt enumeration. Staging low keeps
# everything well clear of the descriptors, and scrub() wipes it afterwards.
STAGE_SRC = 0x0300
STAGE_MAX = 0x1000 - STAGE_SRC          # 3328 bytes
COPIER_LO, COPIER_HI = 0x0100, 0x0300

# Mailbox and status locations, mirrored from stage1_copier.c
MB_BASE = 0xE010
ST_MARK, ST_VERIFY = 0xE001, 0xE004
ST_FAILLO, ST_FAILHI, ST_GOTLO, ST_WANTLO = 0xE005, 0xE006, 0xE007, 0xE008
MARK_DONE, VERIFY_OK = 0x77, 0xA5


class Fx2:
    def __init__(self, dev):
        self.dev = dev

    def write(self, addr: int, data: bytes) -> None:
        n = self.dev.ctrl_transfer(VENDOR_OUT, ANCHOR_LOAD_INTERNAL,
                                   addr, 0, data, 5000)
        if n != len(data):
            raise usb.core.USBError(f"short write at {addr:#06x}: {n}/{len(data)}")

    def read(self, addr: int, length: int) -> bytes:
        return bytes(self.dev.ctrl_transfer(VENDOR_IN, ANCHOR_LOAD_INTERNAL,
                                            addr, 0, length, 5000))

    def halt(self) -> None:
        self.write(FX2_CPUCS, b"\x01")
        time.sleep(0.05)

    def run(self) -> None:
        self.write(FX2_CPUCS, b"\x00")


def load_copier() -> HexImage:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "stage1_copier.hex")
    if not os.path.exists(path):
        raise SystemExit(
            f"missing {path}\n"
            "build it with:\n"
            "  sdcc -mmcs51 --code-loc 0x0100 --xram-loc 0xE100 --xram-size 0x80 "
            "--iram-size 0x80 --no-xinit-opt stage1_copier.c\n"
            "  packihx stage1_copier.ihx > stage1_copier.hex")
    return HexImage.load(path)


def copy_chunk(fx2: Fx2, copier: HexImage, dst: int, payload: bytes,
               verbose: bool) -> None:
    """Move one chunk into external SRAM using the stage-1 copier."""
    fx2.halt()

    fx2.write(STAGE_SRC, payload)
    fx2.write(MB_BASE, bytes([
        STAGE_SRC & 0xFF, STAGE_SRC >> 8,
        dst & 0xFF, dst >> 8,
        len(payload) & 0xFF, len(payload) >> 8,
    ]))
    # clear status bytes so we can tell the copier actually ran
    fx2.write(ST_MARK, b"\x00")
    fx2.write(ST_VERIFY, b"\x00\x00\x00\x00\x00")

    for addr, data in copier.chunked(1024):
        fx2.write(addr, data)
    fx2.write(0x0000, bytes([0x02, 0x01, 0x00]))   # LJMP 0x0100

    fx2.run()
    time.sleep(0.4 + len(payload) / 20000.0)
    fx2.halt()

    # NOTE: the FX2 boot loader's 0xA0 upload does not honour odd start
    # addresses -- a 1-byte read at 0xE001 returns the byte at 0xE000. Always
    # read an aligned block and index into it.
    st = fx2.read(0xE000, 16)
    mark = st[ST_MARK - 0xE000]
    verify = st[ST_VERIFY - 0xE000]
    if mark != MARK_DONE:
        raise SystemExit(
            f"stage-1 copier did not complete (mark={mark:#04x}, expected "
            f"{MARK_DONE:#04x}). The 8051 did not run, or hung.")
    if verify != VERIFY_OK:
        off = st[ST_FAILLO - 0xE000] | (st[ST_FAILHI - 0xE000] << 8)
        got = st[ST_GOTLO - 0xE000]
        want = st[ST_WANTLO - 0xE000]
        raise SystemExit(
            f"external SRAM verify FAILED at offset {off} of this chunk "
            f"(address {dst + off:#06x}): read {got:#04x}, expected {want:#04x}")
    if verbose:
        print(f"    chunk {dst:#06x} +{len(payload)} copied and verified")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--auto", action="store_true",
                    help="pick the image matching the attached device")
    ap.add_argument("--hex", help="explicit Intel HEX image")
    ap.add_argument("--fw-dir", default=".", help="where to search for images")
    ap.add_argument("--timeout", type=float, default=20.0,
                    help="seconds to wait for re-enumeration")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

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
        for root, _d, files in os.walk(args.fw_dir):
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
    fx2 = Fx2(dev)

    internal = [(a, d) for a, d in img.chunked(1024) if a < FX2_INTERNAL_RAM_END]
    ext_segs = [(a, d) for a, d in img.segments() if a + len(d) > FX2_INTERNAL_RAM_END]

    print(f"device   {dev.idVendor:04x}:{dev.idProduct:04x} "
          f"bcdDevice={dev.bcdDevice:04x}")
    print(f"firmware {path} ({img.total_bytes()} bytes)")

    # ---- stage 1: external SRAM ---------------------------------------
    ext_total = 0
    if ext_segs:
        copier = load_copier()
        print("stage 1: populating external SRAM via 8051 copier")
        for addr, data in ext_segs:
            skip = max(0, FX2_INTERNAL_RAM_END - addr)
            addr, data = addr + skip, data[skip:]
            off = 0
            while off < len(data):
                take = min(STAGE_MAX, len(data) - off)
                copy_chunk(fx2, copier, addr + off, data[off:off + take],
                           args.verbose)
                off += take
                ext_total += take
        print(f"  {ext_total} byte(s) written to external SRAM and verified")
    else:
        print("stage 1: not needed (image fits in internal RAM)")

    # ---- stage 2: internal RAM ----------------------------------------
    print("stage 2: loading internal RAM")
    fx2.halt()
    for addr, data in internal:
        fx2.write(addr, data)
    print(f"  {sum(len(d) for _a, d in internal)} byte(s) written")

    print("releasing 8051...")
    fx2.run()

    print("waiting for re-enumeration...")
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        new = find_loaded()
        if new is not None:
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
        time.sleep(0.3)

    print("device did not re-enumerate", file=sys.stderr)
    print("power-cycle the scanner before retrying", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
