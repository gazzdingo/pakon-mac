#!/usr/bin/env python3
"""Ask the PICM's bootloader to exit and run its application.

This is a MODE SWITCH, not a firmware operation. It is worth trying before any
flashing, because if the PICM still holds its application firmware and was
merely switched into bootloader mode, this single packet brings it back.

How this unit most likely got here: `tools/find_light_path.py` walked the
entire Type 4 command space of board 0x44 hunting for the lamp -- 256 blind
commands to the live PICM. Commands 0x01-0x0d were accepted and their effects
were never established. A mode switch would look exactly like that.

ENTERING the bootloader is two steps, both aimed at the APPLICATION address:

    02 05 44 02 0a 00 55     register 0x0a, {00,0x55}
    04 03 44 00 01           Type 4 command 1

That second packet is what tools/find_light_path.py sent while walking all 256
Type 4 commands at board 0x44 hunting for the lamp. It was logged as
"accepted" and nothing more, because the tool only watched EP 0x86 for light.
So this is a deliberate vendor mode change, precisely reproducible, not damage.

LEAVING the bootloader is three steps, and an earlier version of this tool got
all three wrong. Confirmed independently from both TLB.dll and
FirmwareLoaderCom.dll:

    1.  04 03 46 00 08          Type 4 command 8 to the BOOTLOADER address:
                                exit and run the application
    2.  wait 8 x 1000 ms        the settling loop at TLB.dll 0x1001cc20,
                                sent unconditionally on the success path
    3.  02 05 44 02 0a 00 aa    register 0x0a {00,0xAA} to the APPLICATION
                                address: the post-restart hand-off

The earlier attempt sent step 3's payload as a register write to 0x46 with no
command 8 and no wait, which is why it was accepted (status 0) yet did
nothing.

Why this is safe to try:

* it is a mode switch -- no erase, no program write, nothing is overwritten
* if the firmware is intact, the PICM returns to 0x44 and the scanner works
* if the firmware really is gone, the PIC has nothing to run and stays in the
  bootloader, which is where it already is
* the counterpart {0x00, 0x55} switches back, so it is reversible

Why this is worth trying before flashing: a comparison of the register backup
against the vendor image showed a 93.2% firmware-word match, against 2.31% for
a blank comparison. That indicates the application flash is still PROGRAMMED,
so this is most likely still only a mode problem.

    ./picm_run_app.py              # report state only, send nothing
    ./picm_run_app.py --run        # the full three-step restart
    ./picm_run_app.py --enter      # deliberately re-enter the bootloader
"""
from __future__ import annotations

import argparse
import sys
import time

import usb.core
import usb.util

EP_OUT, EP_IN = 0x01, 0x81
HOST = 0x10
PICM_APP, PICM_BOOT = 0x44, 0x46
CONTROLS = (0x48, 0x4A, 0x60, 0x62, 0x50, 0x52)
REG_MODE = 0x0A
EXIT_BOOTLOADER = (0x00, 0xAA)
ENTER_BOOTLOADER = (0x00, 0x55)


def open_dev():
    d = usb.core.find(idVendor=0x0F05, idProduct=0xF135)
    if d is None:
        sys.exit("scanner not loaded -- run pakon_load.py first")
    try:
        d.set_configuration()
    except usb.core.USBError:
        pass
    usb.util.claim_interface(d, 0)
    return d


def send(d, pkt, timeout=1500):
    try:
        d.write(EP_OUT, pkt, timeout)
    except usb.core.USBError:
        return None
    try:
        return bytes(d.read(EP_IN, 64, timeout))
    except usb.core.USBError:
        return None


def accepted(r):
    return bool(r) and len(r) > 3 and r[0] == 0x07 and r[3] == 0x00


def status_text(r):
    if not r:
        return "no response"
    if len(r) < 4:
        return f"short {r.hex(' ')}"
    if r[0] != 0x07:
        return f"type {r[0]} {r[:4].hex(' ')}"
    return {0: "ok", 1: "NAK", 2: "format error",
            3: "checksum error"}.get(r[3], f"status {r[3]}") + f"  {r[:4].hex(' ')}"


def clear_fault(d):
    for _ in range(8):
        r = send(d, bytes([0x01, 0x03, HOST, 0x02, 0x03]))
        if isinstance(r, bytes) and len(r) > 3 and not (r[3] & 0x20):
            return
        send(d, bytes([0x04, 0x03, HOST, 0x00, 0x85]))


def present(d, board):
    """FN_bDrvFindPicController's criterion: resp[0]==7 and resp[3]==0."""
    for _ in range(2):
        clear_fault(d)
        if accepted(send(d, bytes([0x04, 0x03, board, 0x00, 0x00]))):
            return True
    return False


def report(d, tag):
    app = present(d, PICM_APP)
    boot = present(d, PICM_BOOT)
    bad = [c for c in CONTROLS if present(d, c)]
    print(f"  {tag}")
    print(f"    {PICM_APP:#04x} application : {'PRESENT' if app else 'absent'}")
    print(f"    {PICM_BOOT:#04x} bootloader  : {'PRESENT' if boot else 'absent'}")
    print(f"    controls          : "
          f"{'all absent (bus discriminates)' if not bad else 'ACKING: ' + ', '.join(hex(c) for c in bad)}")
    return app, boot, bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="store_true",
                    help="send {00,0xAA}: exit the bootloader and run the app")
    ap.add_argument("--enter", action="store_true",
                    help="send {00,0x55}: go back into the bootloader")
    ap.add_argument("--board", default=hex(PICM_BOOT))
    args = ap.parse_args()
    board = int(args.board, 0)

    d = open_dev()
    try:
        print("state before:")
        app, boot, bad = report(d, "")
        if bad:
            sys.exit("\n  refusing: control addresses ACK, so ACKs here mean "
                     "nothing (floating bus)")
        if not boot and not args.enter:
            sys.exit(f"\n  the bootloader at {board:#04x} does not answer; "
                     f"nothing to do")
        if app and not args.enter:
            print("\n  note: the application already answers at 0x44.")

        if not (args.run or args.enter):
            print("\n  Report only -- nothing sent.")
            print("  --run would send, in order:")
            print(f"      04 03 {PICM_BOOT:02x} 00 08          exit bootloader, run app")
            print( "      (wait 8 x 1000 ms)")
            print(f"      02 05 {PICM_APP:02x} 02 0a 00 aa    post-restart hand-off")
            print("  --enter would send:")
            print(f"      02 05 {PICM_APP:02x} 02 0a 00 55    arm")
            print(f"      04 03 {PICM_APP:02x} 00 01          enter bootloader")
            return 0

        if args.enter:
            # The vendor's two-step entry, both aimed at the application.
            for pkt, what in ((bytes([0x02, 0x05, PICM_APP, 0x02, REG_MODE,
                                      *ENTER_BOOTLOADER]), "arm {00,0x55}"),
                              (bytes([0x04, 0x03, PICM_APP, 0x00, 0x01]),
                               "Type 4 command 1")):
                print(f"\n  {what}: {pkt.hex(' ')}")
                print(f"  -> {status_text(send(d, pkt))}")
                time.sleep(0.1)
        else:
            # Step 1 -- Type 4 command 8 to the BOOTLOADER address.
            pkt = bytes([0x04, 0x03, board, 0x00, 0x08])
            print(f"\n  step 1  exit bootloader, run app: {pkt.hex(' ')}")
            r = send(d, pkt)
            print(f"          -> {status_text(r)}")
            if not accepted(r):
                sys.exit("          the bootloader did not accept command 8; "
                         "stopping.")

            # Step 2 -- the settling loop at TLB.dll 0x1001cc20.
            print("  step 2  settling wait, 8 x 1000 ms")
            for i in range(8):
                time.sleep(1.0)
                print(f"          {i + 1}/8", end="\r", flush=True)
            print("          done   ")

            # Step 3 -- hand-off, to the APPLICATION address.
            pkt = bytes([0x02, 0x05, PICM_APP, 0x02, REG_MODE, *EXIT_BOOTLOADER])
            print(f"  step 3  hand-off to {PICM_APP:#04x}: {pkt.hex(' ')}")
            print(f"          -> {status_text(send(d, pkt))}")
            time.sleep(1.0)

        print("\nstate after:")
        app2, boot2, _ = report(d, "")

        print()
        if app2 and not app:
            print("  *** THE APPLICATION IS RUNNING -- 0x44 now answers. ***")
            print("  The PICM never lost its firmware; it was only in the")
            print("  bootloader. No flashing is needed.")
        elif args.enter and boot2 and not app2:
            print("  back in the bootloader, as asked.")
        elif not app2:
            print("  0x44 still does not answer.")
            print("  Try a power cycle and re-run the report: the restart may")
            print("  only take effect on reset. If it still does not answer,")
            print("  read the flash back with picm_read_flash.py before")
            print("  considering flash_picm.py -- a 93% word match against the")
            print("  vendor image would mean the firmware is present and the")
            print("  problem is the restart, not the contents.")
    finally:
        usb.util.release_interface(d, 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
