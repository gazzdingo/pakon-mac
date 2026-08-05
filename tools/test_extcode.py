#!/usr/bin/env python3
"""Decisive test: can the FX2 FETCH CODE from external SRAM, or only read data?

Background
----------
We proved the Pakon USB board has external SRAM at 0x4000 that the 8051 can
WRITE via MOVX. But MOVX uses the RD/WR strobes, whereas instruction fetch uses
PSEN. A board can wire external SRAM as data-only. If external SRAM is not
mapped as CODE memory, the firmware runs its internal portion, calls into
0x4000, fetches garbage and crashes -- which matches the observed behaviour
(USB drops ~60ms after 8051 release and never returns).

Method
------
1. Use the stage-1 copier to place an 8-byte program into external SRAM at
   0x4000 that writes a marker to scratch RAM and halts.
2. Point the reset vector at 0x4000 (LJMP 0x4000).
3. Release the 8051, wait, halt.
4. Read the marker back from scratch RAM.

   marker present -> external SRAM IS executable; the crash has another cause
   marker absent  -> external SRAM is DATA ONLY; the firmware can never run
                     from it and the whole loading strategy needs rethinking

As a control, the same program is also run from INTERNAL RAM first, proving
the marker mechanism itself works.

Everything here is volatile; a power cycle restores the scanner.
"""
from __future__ import annotations

import os
import sys
import time

import usb.core

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pakon_hex import HexImage
from write_guard import require_writes_unlocked   # noqa: E402

VO, VI = 0x40, 0xC0
HALT, RUN = 0x03, 0x02          # preserve CLKOE (bit 1); bit 0 = 8051RES
STAGE = 0x0300
MARK_ADDR = 0xE00A

# MOV DPTR,#0xE00A / MOV A,#imm / MOVX @DPTR,A / SJMP $
def marker_program(value: int) -> bytes:
    return bytes([0x90, (MARK_ADDR >> 8) & 0xFF, MARK_ADDR & 0xFF,
                  0x74, value, 0xF0, 0x80, 0xFE])


def main() -> int:
    # Interlock: loads and executes test code on the FX2 -- the I2C bus
    # master. RAM-only, but nothing executes on the bus master by accident
    # while the read-everything-first lock is engaged.
    require_writes_unlocked("test_extcode.py",
                            "loads and runs test code on the FX2 bus master")
    d = usb.core.find(idVendor=0x0F05, idProduct=0xF235)
    if d is None:
        print("no unloaded Pakon scanner on the bus", file=sys.stderr)
        return 1

    def w(a, b): d.ctrl_transfer(VO, 0xA0, a, 0, bytes(b), 5000)
    def r(a, n): return bytes(d.ctrl_transfer(VI, 0xA0, a, 0, n, 5000))

    print(f"device {d.idVendor:04x}:{d.idProduct:04x} rev{d.bcdDevice:04x}")

    # ---- control: run the marker program from INTERNAL RAM ---------------
    print("\n[control] execute marker program from INTERNAL RAM at 0x0800")
    w(0xE600, [HALT]); time.sleep(0.1)
    w(0xE000, [0] * 16)
    w(0x0800, marker_program(0xC7))
    w(0x0000, [0x02, 0x08, 0x00])            # LJMP 0x0800
    w(0xE600, [RUN]); time.sleep(0.6); w(0xE600, [HALT]); time.sleep(0.2)
    got = r(0xE000, 16)[MARK_ADDR - 0xE000]
    print(f"  marker = {got:#04x} (expect 0xc7) -> "
          f"{'internal execution OK' if got == 0xC7 else 'CONTROL FAILED'}")
    if got != 0xC7:
        print("  control failed; cannot trust the external result", file=sys.stderr)
        return 1

    # ---- test: run the same program from EXTERNAL SRAM -------------------
    print("\n[test] place marker program in EXTERNAL SRAM at 0x4000 via copier")
    cop = HexImage.load("stage1_copier.hex")
    prog = marker_program(0xE1)
    w(0xE600, [HALT]); time.sleep(0.1)
    w(STAGE, prog)
    w(0xE010, [STAGE & 0xFF, STAGE >> 8, 0x00, 0x40, len(prog), 0x00, 0])
    w(0xE000, [0] * 16)
    for a, dd in cop.chunked(1024):
        w(a, dd)
    w(0x0000, [0x02, 0x01, 0x00])             # LJMP copier
    w(0xE600, [RUN]); time.sleep(0.8); w(0xE600, [HALT]); time.sleep(0.2)
    st = r(0xE000, 16)
    if st[1] != 0x77 or st[4] != 0xA5:
        print(f"  copier failed (mark={st[1]:#04x} verify={st[4]:#04x})",
              file=sys.stderr)
        return 1
    print("  program written to external SRAM and verified")

    print("\n[test] point reset vector at 0x4000 and release")
    w(0xE000, [0] * 16)
    w(0x0000, [0x02, 0x40, 0x00])             # LJMP 0x4000
    w(0xE600, [RUN]); time.sleep(0.8); w(0xE600, [HALT]); time.sleep(0.2)
    got = r(0xE000, 16)[MARK_ADDR - 0xE000]
    print(f"  marker = {got:#04x} (expect 0xe1)")

    print()
    if got == 0xE1:
        print("RESULT: external SRAM IS EXECUTABLE.")
        print("        Code fetch from 0x4000 works, so the firmware crash has")
        print("        another cause. Investigate the firmware's own init path.")
    else:
        print("RESULT: external SRAM is NOT EXECUTABLE (data only).")
        print("        PSEN is not wired to the external SRAM, so the 8051")
        print("        cannot fetch instructions from 0x4000. The firmware")
        print("        image therefore cannot run the way we are loading it --")
        print("        the real driver must place that code somewhere else, or")
        print("        the board maps code memory differently than assumed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
