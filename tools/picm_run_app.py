#!/usr/bin/env python3
"""Ask the PICM's bootloader to exit and run its application.

This is a MODE SWITCH, not a firmware operation. It is worth trying before any
flashing, because if the PICM still holds its application firmware and was
merely switched into bootloader mode, this single packet brings it back.

How this unit most likely got here: `tools/find_light_path.py` walked the
entire Type 4 command space of board 0x44 hunting for the lamp -- 256 blind
commands to the live PICM. Commands 0x01-0x0d were accepted and their effects
were never established. A mode switch would look exactly like that.

Register 0x0a is the bootloader mode switch in TLB.dll:

    {0x00, 0x55}   enter bootloader    FN_bPicToBootLoaderState, fcn.1001b9b0
    {0x00, 0xAA}   exit, run the app   FN_bUpdate, 0x1001cc6d-0x1001cc72

The exit form, byte for byte from 0x1001cc60:

    push 0 ; push 2 ; push edx ; push 0xa ; push edi
    mov byte [esp + 0x4c], 0
    mov byte [esp + 0x4d], 0xaa
    call fcn.10009ae0

which on the wire is the ordinary register write:

    02 05 <board> 02 0a 00 aa

FN_bUpdate sends this after flashing, to boot the PIC into the firmware it has
just written.

Why this is safe to try:

* it is a mode switch -- no erase, no program write, nothing is overwritten
* if the firmware is intact, the PICM returns to 0x44 and the scanner works
* if the firmware really is gone, the PIC has nothing to run and stays in the
  bootloader, which is where it already is
* the counterpart {0x00, 0x55} switches back, so it is reversible

    ./picm_run_app.py              # report state only, send nothing
    ./picm_run_app.py --run        # send the exit-bootloader packet
    ./picm_run_app.py --enter      # send {00,0x55} instead, to go back
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
            print(f"  --run    would send  02 05 {board:02x} 02 0a 00 aa")
            print(f"  --enter  would send  02 05 {board:02x} 02 0a 00 55")
            return 0

        payload = ENTER_BOOTLOADER if args.enter else EXIT_BOOTLOADER
        what = "enter bootloader" if args.enter else "exit bootloader, run app"
        pkt = bytes([0x02, 0x05, board, 0x02, REG_MODE, payload[0], payload[1]])
        print(f"\n  sending {what}: {pkt.hex(' ')}")
        r = send(d, pkt)
        print(f"  -> {status_text(r)}")

        # FN_bPicToBootLoaderState sleeps 100 ms after the mode write.
        time.sleep(0.5)
        print("\nstate after:")
        app2, boot2, _ = report(d, "")

        print()
        if app2 and not app:
            print("  THE APPLICATION IS RUNNING -- 0x44 now answers.")
            print("  The PICM never lost its firmware; it was only in the")
            print("  bootloader. No flashing is needed.")
        elif args.enter and boot2:
            print("  back in the bootloader.")
        elif not app2:
            print("  0x44 still does not answer.")
            print("  Power-cycle and re-check: the switch may only take effect")
            print("  on reset. If it still does not answer after a power cycle,")
            print("  the application firmware really is gone and flashing")
            print("  (tools/flash_picm.py) is the remaining route.")
    finally:
        usb.util.release_interface(d, 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
