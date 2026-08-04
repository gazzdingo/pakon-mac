#!/usr/bin/env python3
"""Raw I2C bus scan using the FX2's own I2C controller. READ ONLY.

WHY THIS IS DIFFERENT FROM EVERY SWEEP WE HAVE ALREADY RUN
----------------------------------------------------------
All previous address sweeps went through the vendor packet protocol. That has
two blind spots, and this tool exists to cover both:

1. The FX2 firmware handles board byte 0x10 itself -- it is the host's own
   address, answered internally and never placed on the wire. 7-bit address
   0x08 has therefore never been physically probed on this bus.

2. Far more important: the vendor's presence test requires a COMPLETE,
   well-formed response packet (resp[0]==7 and resp[3]==0). A chip that
   acknowledges its address but then fails later in the transaction reads as
   ABSENT -- indistinguishable from a chip that is not there at all.

A raw scan only needs the address ACK. That is a much lower bar and a much
more sensitive test of "is anything alive here". If U11 is ACKing but failing
downstream, this finds it and the vendor sweep could not have.

SAFETY -- PRECISE ACCOUNTING
----------------------------
"Read only" deserves an exact answer rather than a reassuring one. This tool
does write three things, and none of them are persistent:

  1. FX2 internal RAM -- the scanner code itself. Volatile; gone at power-off.
     Unavoidable, since running code on the FX2 is the whole method.
  2. The FX2 CPUCS reset register. Volatile.
  3. On the I2C bus: START, device address with the R/W bit SET (read
     direction), STOP.

Point 3 is the one that matters, and it is read-only in the strict sense.
A read-direction address declares read intent on the wire, and NO DATA BYTE IS
EVER TRANSMITTED -- the source contains exactly one write to I2DAT and it is
the address. A 24Cxx EEPROM requires address byte(s) AND data before a write
commits, so this physically cannot repeat the boot-EEPROM damage.

Nothing persistent is written anywhere: not to EEPROM, not to flash, not to
any device on the bus. The scanner runs on the FX2 in place of the Pakon
firmware, so recovery is simply: power cycle, then run pakon_load.py.

HOW IT WORKS
------------
Vendor request 0xA0 is implemented by the EZ-USB core itself and reads/writes
internal RAM while the 8051 is held in reset. So:

    hold 8051 in reset -> download scanner -> release -> wait -> hold again
    -> read results straight out of RAM

No USB enumeration from our own code is needed, which keeps the firmware tiny.

USAGE
-----
Power-cycle the scanner first so it is in the UNLOADED state, then:

    ./i2c_raw_scan.py

Do NOT run pakon_load.py first -- once the Pakon firmware owns the FX2,
request 0xA0 is no longer served by the core.
"""
from __future__ import annotations

import os
import sys
import time

import usb.core
import usb.util

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pakon_load import Fx2, HexImage   # noqa: E402

VENDOR_IN = 0xC0
ANCHOR_LOAD_INTERNAL = 0xA0
RESULTS, MARKER = 0x0400, 0x0480
UNLOADED = ((0x04B4, 0x8613), (0x0F05, 0xF235), (0x0547, 0x1002))
LOADED = (0x0F05, 0xF135)
FW = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir,
                  "fx2", "i2c_scan.ihx")

# Status bits from the FX2 I2CS register.
ST_ACK, ST_BERR, ST_DONE = 0x02, 0x04, 0x01

# Addresses we already understand, so anything else stands out.
KNOWN = {0x08: "host/FX2 self (board 0x10) -- NEVER probed until now",
         0x20: "light board (board 0x40)",
         0x21: "light board alt (board 0x42)",
         0x22: "PICM application (board 0x44)  <-- the missing one",
         0x23: "PICM bootloader (board 0x46)   <-- the missing one",
         0x51: "boot EEPROM (board 0xA2)",
         0x52: "boot EEPROM (board 0xA4)"}


def find_unloaded():
    for vid, pid in UNLOADED:
        d = usb.core.find(idVendor=vid, idProduct=pid)
        if d is not None:
            return d
    return None


def read_ram(dev, addr, length):
    return bytes(dev.ctrl_transfer(VENDOR_IN, ANCHOR_LOAD_INTERNAL,
                                   addr, 0, length, 5000))


def main() -> int:
    if usb.core.find(idVendor=LOADED[0], idProduct=LOADED[1]) is not None:
        sys.exit("The Pakon firmware is already loaded, so request 0xA0 is no\n"
                 "longer served. Power-cycle the scanner and run this FIRST,\n"
                 "before pakon_load.py.")

    dev = find_unloaded()
    if dev is None:
        sys.exit("No unloaded scanner found. Power-cycle it and try again.")
    print(f"found unloaded device {dev.idVendor:04x}:{dev.idProduct:04x}")

    if not os.path.exists(FW):
        sys.exit(f"scanner firmware not built: {FW}\n"
                 f"  build with: sdcc -mmcs51 --code-loc 0x0000 "
                 f"--code-size 0x0400 --xram-loc 0x0500 --xram-size 0x0300 "
                 f"--iram-size 0x80 --model-small -o i2c_scan.ihx i2c_scan.c")
    image = HexImage.load(FW)
    print(f"scanner firmware: {image.total_bytes()} bytes")

    fx2 = Fx2(dev)
    fx2.reset_8051(True)
    fx2.download(image, False)
    print("downloaded, releasing 8051 ...")
    fx2.reset_8051(False)

    # 128 probes, each bounded by two 30000-iteration timeouts. Generous.
    time.sleep(3.0)

    fx2.reset_8051(True)
    print("8051 halted, reading results out of RAM\n")

    marker = read_ram(dev, MARKER, 4)
    done = marker == bytes([0xC0, 0xDE, 0xF1, 0x35])
    print(f"completion marker: {marker.hex(' ')}  "
          f"{'SCAN COMPLETED' if done else 'DID NOT COMPLETE'}")
    if not done:
        print("  The scan did not run to completion. Results below are partial")
        print("  and 0xEE means that address was never probed.\n")

    data = read_ram(dev, RESULTS, 128)

    found, berr, quiet = [], [], 0
    for a, st in enumerate(data):
        if st == 0xEE:
            continue
        if st & ST_BERR:
            berr.append(a)
        elif st & ST_ACK:
            found.append(a)
        else:
            quiet += 1

    print(f"\nprobed {128 - list(data).count(0xEE)} addresses  "
          f"({quiet} silent)\n")
    print("ACKNOWLEDGED (something is alive at these addresses):")
    if not found:
        print("    none -- nothing on the bus acknowledged at all.")
        print("    That would mean even the light board and boot EEPROM are")
        print("    silent, which contradicts everything else. Suspect the")
        print("    scan itself rather than the hardware.")
    for a in found:
        board = a << 1
        tag = KNOWN.get(a, "*** UNEXPECTED -- NOT ACCOUNTED FOR ***")
        print(f"    7-bit {a:#04x}   (board byte {board:#04x})   {tag}")

    if berr:
        print("\nBUS ERROR reported at:")
        for a in berr:
            print(f"    7-bit {a:#04x}  (board byte {a << 1:#04x})")

    print("\n" + "=" * 66)
    missing = [a for a in (0x22, 0x23) if a not in found]
    if not missing:
        print("*** U11 ACKNOWLEDGED. It is alive on the bus and the fault is")
        print("*** downstream of address recognition -- NOT dead silicon.")
        print("    The vendor sweep could not have seen this, because it")
        print("    requires a complete well-formed response packet.")
    elif found:
        print("U11 did not acknowledge at 0x22 or 0x23, on a raw probe that")
        print("only needs an address ACK. Other devices on the same two wires")
        print("did answer, so the bus and this scanner both work.")
        print("That is the strongest evidence yet that U11 genuinely cannot")
        print("respond -- and it was obtained without the programmer.")
        unexpected = [a for a in found if a not in KNOWN]
        if unexpected:
            print(f"\nBut note the unexpected address(es): "
                  f"{', '.join(hex(a) for a in unexpected)}")
            print("If U11's address literal was corrupted, this is where it")
            print("would show up. Worth chasing before concluding anything.")

    print("\nNothing was written. Power-cycle and run pakon_load.py to return")
    print("the scanner to normal operation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
