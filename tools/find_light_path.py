#!/usr/bin/env python3
"""Find what is blocking the optical path, with the lamp confirmed lit.

Established by direct observation: the LED illuminator lights (bright blue,
operator-confirmed) yet EP 0x86 stays at a constant mean of ~1240. So light is
being produced but is not reaching the sensor, or the sensor readout on EP 0x86
is not the illuminated one.

The F-135 has a filter wheel -- `FN_bDrvMoveFilterWheel`,
`EC_MotorFault_FilterWheel` and the enum value
`FILM_COLOR_FILTER_WHEEL_BLOCKED` all exist in TLB.dll. A wheel parked in the
blocked position produces exactly these observations.

Strategy: light the lamp, then walk the motor board's Type 4 command space
watching the sensor. If a command opens the path, the level jumps immediately
and unambiguously.

Only Type 4 commands are used. They are the vendor's own command form, and the
board rejects unknown ones with status 2 rather than acting on them. Known
commands are skipped by default so film transport is not driven unnecessarily.

  ./find_light_path.py                 # sweep motor board 0x44
  ./find_light_path.py --board 0x40    # sweep light board instead
  ./find_light_path.py --include-motor # also send the known transport commands
"""
from __future__ import annotations

import argparse
import struct
import sys
import time

import usb.core
import usb.util

EP_OUT, EP_IN, EP_DATA = 0x01, 0x81, 0x86
HOST, LIGHT, MOTOR = 0x10, 0x40, 0x44

# Commands whose effect is already known; skipped unless --include-motor.
KNOWN_MOTOR = {0x00, 0xA0, 0xA1, 0xA2}

EXPOSURE = 1549
N = round(EXPOSURE * 0.6)
ON = N // 2


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


def send(d, pkt, timeout=900):
    try:
        d.write(EP_OUT, pkt, timeout)
    except usb.core.USBError:
        return "WEDGED"
    try:
        return bytes(d.read(EP_IN, 64, timeout))
    except usb.core.USBError:
        return None


def flush(d, nbytes=256 * 1024):
    got = 0
    while got < nbytes:
        try:
            got += len(d.read(EP_DATA, 32768, 250))
        except usb.core.USBError:
            break


def level(d, bursts=3):
    flush(d)
    vals = []
    for _ in range(bursts):
        try:
            b = d.read(EP_DATA, 16384, 500)
        except usb.core.USBError:
            break
        vals.extend(struct.unpack("<%dH" % (len(b) // 2), bytes(b[:len(b) // 2 * 2])))
    return (max(vals), sum(vals) / len(vals)) if vals else (0, 0)


def clear_fault(d):
    for _ in range(6):
        r = send(d, bytes([0x01, 0x03, HOST, 0x02, 0x03]))
        if isinstance(r, bytes) and len(r) > 3 and not (r[3] & 0x20):
            return
        send(d, bytes([0x04, 0x03, HOST, 0x00, 0x85]))


def lamp_on(d):
    send(d, bytes([0x02, 0x04, LIGHT, 0x01, 0x80, 0x00]))
    send(d, bytes([0x02, 0x0F, LIGHT, 0x0C, 0x82]) +
         struct.pack("<6H", ON, 0, ON, 0, ON, N))
    send(d, bytes([0x02, 0x08, LIGHT, 0x05, 0x81, 24, 0, 8, 0, 24]))
    send(d, bytes([0x02, 0x04, LIGHT, 0x01, 0x80, 0x01]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--board", default="0x44")
    ap.add_argument("--include-motor", action="store_true",
                    help="also send the known film-transport commands")
    ap.add_argument("--threshold", type=float, default=1.5,
                    help="level multiple counting as 'path opened'")
    args = ap.parse_args()
    board = int(args.board, 0)

    d = open_dev()
    try:
        clear_fault(d)
        print("lighting the lamp (operator has confirmed this works)...")
        lamp_on(d)
        time.sleep(0.8)
        mx, base = level(d)
        print(f"baseline with lamp ON: max={mx} mean={base:.0f}")
        print(f"trigger threshold: mean > {base * args.threshold:.0f}\n")
        print(f"sweeping Type 4 commands on board {board:#04x}:")

        found = []
        for cmd in range(0x100):
            if board == MOTOR and cmd in KNOWN_MOTOR and not args.include_motor:
                continue
            r = send(d, bytes([0x04, 0x03, board, 0x00, cmd]))
            if r == "WEDGED":
                print(f"  cmd {cmd:#04x}: endpoint stopped draining -- stopping")
                break
            if not isinstance(r, bytes) or len(r) < 4:
                continue
            st = r[3]
            if st not in (0, 8):
                continue
            mx, mn = level(d)
            flag = ""
            if mn > base * args.threshold:
                flag = "   *** LIGHT PATH OPENED ***"
                found.append((cmd, mn, mx))
            print(f"  cmd {cmd:#04x}: accepted  mean={mn:7.0f} max={mx:5}{flag}")
            if flag:
                print("\n  stopping -- found a command that admits light")
                break

        send(d, bytes([0x02, 0x04, LIGHT, 0x01, 0x80, 0x00]))
        print("\nlamp off")
        if found:
            for c, mn, mx in found:
                print(f"  RESULT: command {c:#04x} on board {board:#04x} "
                      f"-> mean {mn:.0f}, max {mx}")
        else:
            print("  RESULT: no command on this board admitted light")
    finally:
        usb.util.release_interface(d, 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
