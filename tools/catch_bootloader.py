#!/usr/bin/env python3
"""Catch the PICM bootloader in its listening window at power-on.

THE IDEA
--------
Most PIC bootloaders listen for a host command for a fixed period after reset,
then jump to the application if nothing arrives. If this one does, there is a
window on every power-up during which board 0x46 answers -- and after which it
never will again.

Every previous timing test here started probing several seconds after power-on,
because loading FX2 firmware takes that long. A window of a few hundred
milliseconds would have been missed every single time. That is consistent with
everything observed: the bootloader answered readily while the application was
invalid (it had nowhere to jump, so it stayed resident forever), and has never
answered since the vectors were restored.

So: pre-stage everything, load firmware the moment the device appears, and put
the first probe on the wire as early as physically possible.

WHAT IT DOES
------------
1. Waits for the unloaded device (04b4:8613 or 0f05:f235) to appear -- that is
   the moment of power-on, give or take enumeration.
2. Downloads the firmware image immediately, with the HEX pre-parsed before
   the wait so no time is lost to file I/O or parsing.
3. The instant the loaded device (0f05:f135) enumerates, hammers 0x46 and 0x44
   with the vendor presence probe, back to back, with no fault-clear packets in
   between and the shortest timeout that still works.
4. Timestamps everything relative to the appearance of the unloaded device, so
   we learn how early the first probe lands as well as whether it answers.

Read-only: the only packets sent are `04 03 <board> 00 00`, the vendor's own
discovery command from FN_bDrvFindPicController.

USAGE
-----
    ./catch_bootloader.py            # then power-cycle the scanner
    ./catch_bootloader.py --seconds 90

Start it FIRST, with the scanner OFF, then switch the scanner on.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import usb.core
import usb.util

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pakon_load import Fx2, HexImage   # noqa: E402

EP_OUT, EP_IN = 0x01, 0x81
PICM_APP, PICM_BOOT = 0x44, 0x46
UNLOADED = ((0x04B4, 0x8613), (0x0F05, 0xF235), (0x0547, 0x1002))
LOADED = (0x0F05, 0xF135)

FW = ("/Users/guy/Downloads/Pakon Update 2/fx35install/program files/Pakon/"
      "F-135/F135Driver/Pakon7.hex")
STAGE1 = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir,
                      "vendor", "stage1_vendor.hex")


def find_unloaded():
    for vid, pid in UNLOADED:
        d = usb.core.find(idVendor=vid, idProduct=pid)
        if d is not None:
            return d
    return None


def probe(d, board, timeout=60):
    """The vendor presence packet. Present iff resp[0]==7 and resp[3]==0."""
    try:
        d.write(EP_OUT, bytes([0x04, 0x03, board, 0x00, 0x00]), timeout)
        r = bytes(d.read(EP_IN, 64, timeout))
    except usb.core.USBError:
        return None
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seconds", type=float, default=60.0,
                    help="how long to keep probing after firmware loads")
    ap.add_argument("--hex", default=FW)
    args = ap.parse_args()

    # Pre-parse both images NOW so not a millisecond is spent on it later.
    print("pre-staging firmware images ...")
    stage1 = HexImage.load(STAGE1)
    image = HexImage.load(args.hex)
    print(f"  stage 1: {stage1.total_bytes()} bytes")
    print(f"  image  : {image.total_bytes()} bytes  ({os.path.basename(args.hex)})")

    if find_unloaded() is not None or usb.core.find(idVendor=LOADED[0],
                                                   idProduct=LOADED[1]) is not None:
        print("\n  A scanner is already present. Turn it OFF now; I will wait.")
        while find_unloaded() is not None or usb.core.find(
                idVendor=LOADED[0], idProduct=LOADED[1]) is not None:
            time.sleep(0.05)
        print("  gone.")

    print("\n>>> POWER THE SCANNER ON NOW <<<\n")
    while True:
        dev = find_unloaded()
        if dev is not None:
            break
        time.sleep(0.002)
    t0 = time.time()
    print(f"  t+{0.0:6.3f}s  unloaded device appeared "
          f"({dev.idVendor:04x}:{dev.idProduct:04x})")

    fx2 = Fx2(dev)
    fx2.reset_8051(True)
    fx2.download(stage1, False)
    fx2.reset_8051(False)
    print(f"  t+{time.time()-t0:6.3f}s  stage-1 loader running")
    time.sleep(0.5)                      # the loader needs to boot before 0xA3

    # The stage-1 loader must be RUNNING to service the external (0xA3)
    # transfers, so the 8051 is deliberately not held in reset here.
    for attempt in range(5):
        try:
            fx2.download(image, False)
            break
        except usb.core.USBError:
            if attempt == 4:
                raise
            time.sleep(0.25)
    fx2.reset_8051(False)
    print(f"  t+{time.time()-t0:6.3f}s  image downloaded, resetting")

    d = None
    while d is None and time.time() - t0 < 25:
        d = usb.core.find(idVendor=LOADED[0], idProduct=LOADED[1])
        if d is None:
            time.sleep(0.002)
    if d is None:
        sys.exit("  firmware did not enumerate")
    try:
        d.set_configuration()
    except usb.core.USBError:
        pass
    try:
        usb.util.claim_interface(d, 0)
    except usb.core.USBError:
        pass
    t_ready = time.time() - t0
    print(f"  t+{t_ready:6.3f}s  LOADED -- first probe going out now\n")

    hits = []
    n = 0
    deadline = time.time() + args.seconds
    last_report = 0.0
    try:
        while time.time() < deadline:
            for board in (PICM_BOOT, PICM_APP):
                r = probe(d, board)
                n += 1
                if r and len(r) > 3 and r[0] == 0x07 and r[3] == 0x00:
                    dt = time.time() - t0
                    hits.append((dt, board, r[:4].hex(" ")))
                    print(f"  t+{dt:6.3f}s  *** {board:#04x} ANSWERED: "
                          f"{r[:4].hex(' ')} ***")
            dt = time.time() - t0
            if dt - last_report >= 5.0:
                last_report = dt
                print(f"  t+{dt:6.3f}s  {n} probes, no answer yet")
    finally:
        try:
            usb.util.release_interface(d, 0)
        except Exception:
            pass

    print(f"\n  {n} probes over {args.seconds:.0f}s")
    print(f"  first probe landed t+{t_ready:.3f}s after the device appeared")
    if hits:
        print("\n  ANSWERED:")
        for dt, b, raw in hits:
            print(f"    t+{dt:6.3f}s  {b:#04x}  {raw}")
        print("\n  There IS a window. Note the earliest time above -- anything")
        print("  that must reach the PICM has to happen before it closes.")
    else:
        print("\n  No answer at any point.")
        print(f"  If a window exists it closes before t+{t_ready:.3f}s, which is")
        print("  how long the FX2 firmware download takes. Getting under that")
        print("  needs the FX2 running our code at power-on -- i.e. a C2-format")
        print("  boot EEPROM -- rather than waiting for a host download.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
