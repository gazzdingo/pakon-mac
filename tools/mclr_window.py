#!/usr/bin/env python3
"""Catch U11's bootloader in its power-on window by resetting ONLY the PIC.

READ ONLY. Nothing is written to any device on the I2C bus, and nothing
persistent is written anywhere.

THE GAP
-------
Every probe ever run on this scanner happened seconds after power-on, because
the FX2 has to enumerate and then the host has to download firmware. A
PIC18F452 at 40 MHz boots in milliseconds. If U11's bootloader listens on I2C
for a window before handing off to the application, we have missed it every
time -- including the 128-address scan that found U11 silent everywhere.

WHY IT DECIDES THINGS
---------------------
The bootloader (0x0000-0x03FF) and the application share the same MSSP
peripheral and the same two pins:

  * bootloader ANSWERS in the window -> the MSSP hardware works, and the
    application is failing to arm it. Firmware problem: reflashable, no chip
    swap, no rework, no money.
  * bootloader SILENT too -> peripheral or pins genuinely dead. Hardware.

That is the exact fork the whole project is stuck on, and this resolves it
without the programmer.

WHAT YOU DO
-----------
This loads a continuous probe loop into the FX2 and leaves it running. While
it runs, briefly short JM11 pin 1 (MCLR) to ground. That resets ONLY U11 --
the FX2 keeps running with the probe loop already live, so it is watching
before the PIC executes its first instruction.

Pulling MCLR low is a plain reset; it is exactly what a programmer does to
enter programming mode. Nothing is written and there is no state to get stuck
in. If the short is clumsy, nothing is harmed -- just run it again.

    ./mclr_window.py                # 30-second watch window
    ./mclr_window.py --seconds 60

Run tools/i2c_raw_scan.py first as a positive control: it must report the
light board at 0x20 and the EEPROM at 0x51/0x52. That proves the probe path
works, so a zero-hit result here means something real.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import usb.core

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pakon_load import Fx2, HexImage   # noqa: E402

VENDOR_IN = 0xC0
ANCHOR_LOAD_INTERNAL = 0xA0
HITS, MARKER, NHIT, TICK = 0x0400, 0x0480, 0x0500, 0x0504
MAXHIT = 48
UNLOADED = ((0x04B4, 0x8613), (0x0F05, 0xF235), (0x0547, 0x1002))
LOADED = (0x0F05, 0xF135)
FW = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir,
                  "fx2", "mclr_window.ihx")

NAME = {0x22: "PICM APPLICATION", 0x23: "PICM BOOTLOADER"}


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
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seconds", type=float, default=30.0,
                    help="how long to watch before halting and reporting")
    args = ap.parse_args()

    if usb.core.find(idVendor=LOADED[0], idProduct=LOADED[1]) is not None:
        sys.exit("The Pakon firmware is loaded, so request 0xA0 is no longer\n"
                 "served. Power-cycle the scanner and run this first.")
    dev = find_unloaded()
    if dev is None:
        sys.exit("No unloaded scanner found. Power-cycle it and try again.")
    if not os.path.exists(FW):
        sys.exit(f"firmware not built: {FW}")

    print(f"device {dev.idVendor:04x}:{dev.idProduct:04x}")
    image = HexImage.load(FW)
    print(f"probe loop: {image.total_bytes()} bytes")

    fx2 = Fx2(dev)
    fx2.reset_8051(True)
    fx2.download(image, False)
    fx2.reset_8051(False)
    time.sleep(0.3)

    mk = read_ram(dev, MARKER, 4)
    if mk != bytes([0xC0, 0xDE, 0xF1, 0x35]):
        print(f"  warning: probe loop marker is {mk.hex(' ')}, expected "
              f"c0 de f1 35 -- it may not be running")

    print("\n" + "=" * 68)
    print("  PROBE LOOP IS RUNNING. Now, briefly short JM11 pin 1 (MCLR)")
    print("  to ground -- a tap is enough. That resets ONLY U11.")
    print("")
    print("  JM11 is the 5-pin header beside U11, the 44-pin TQFP marked")
    print("  125507A 2208. Ground: any shield, or U11 pins 6/29.")
    print("")
    print("  Do it two or three times during the window; more attempts")
    print("  cost nothing and only improve the odds of catching it.")
    print("=" * 68)

    # NOTE: do not read the hit count while the 8051 is running. Vendor
    # request 0xA0 reads RAM without any coherency guarantee against the
    # running CPU, and an early version displayed pure garbage here (values
    # like 58928 when the true count was 0). Results are only read AFTER the
    # CPU is halted, below.
    deadline = time.time() + args.seconds
    while time.time() < deadline:
        left = deadline - time.time()
        print(f"\r  watching... {left:4.0f}s left   "
              f"(count is read after halt, not live)      ",
              end="", flush=True)
        time.sleep(0.5)
    print("\n")

    fx2.reset_8051(True)
    n = int.from_bytes(read_ram(dev, NHIT, 2), "little")
    # 32-bit: a 16-bit counter wraps in ~4s at ~15,700 passes/sec.
    tick = int.from_bytes(read_ram(dev, TICK, 4), "little")
    raw = read_ram(dev, HITS, MAXHIT * 4)

    rate = tick / args.seconds if args.seconds else 0
    print(f"\nprobe loop completed {tick} passes ({tick * 2} probes) "
          f"at ~{rate:.0f} passes/sec")
    print(f"  -> one probe pair every ~{1e6 / rate:.0f} us"
          if rate else "")
    if tick == 0:
        print("  *** The loop never ran. Nothing below is meaningful. ***")
        return 1

    print(f"hits recorded: {n}\n")
    if n == 0:
        print("  NO RESPONSE from 0x22 or 0x23 at any point, including")
        print("  immediately after reset.")
        print("")
        print("  If i2c_raw_scan.py showed the light board and EEPROM, the")
        print("  probe path is proven good, and this is strong evidence that")
        print("  U11's I2C is dead at the hardware level -- the bootloader")
        print("  cannot answer either, and it shares the MSSP peripheral and")
        print("  the same two pins with the application.")
        print("")
        print("  That points at chip replacement rather than a reflash.")
        print("  Tomorrow's ICSP read still decides it; this narrows it.")
        return 0

    print("  *** SOMETHING ANSWERED ***\n")
    for i in range(min(n, MAXHIT)):
        a, st, th, tl = raw[i * 4:i * 4 + 4]
        t = (th << 8) | tl
        print(f"    pass {t:5}  7-bit {a:#04x}  status {st:#04x}  "
              f"{NAME.get(a, '?')}")
    first = (raw[2] << 8) | raw[3]
    print(f"\n  First response at pass {first} of {tick}.")
    if first < tick // 10:
        print("  That is EARLY in the watch -- consistent with a boot window")
        print("  that closes quickly.")
    print("")
    print("  This means U11's MSSP peripheral WORKS. The chip can acknowledge")
    print("  on I2C. The fault is therefore in the application failing to arm")
    print("  it, not in dead silicon.")
    print("  -> Reflashable. No chip swap. Read the flash tomorrow, diff it,")
    print("     and reflash per the MERGED-IMAGE RULE in docs/27 section 7.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
