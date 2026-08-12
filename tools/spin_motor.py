#!/usr/bin/env python3
"""Briefly drive the film transport, to prove the repaired PICM actually works.

The presence probe (tools/probe_picm_alive.py) shows U34 answering on the bus.
This goes one step further and asks it to DO something, which is the only test
that exercises the motor control path rather than just the I2C link.

WHY THIS EXISTS RATHER THAN LIFTING THE INTERLOCK
-------------------------------------------------
tools/WRITES_LOCKED refuses to run pakon_cmd.py and ten other tools. Its stated
concern is anything that "WRITES, ERASES, PROGRAMS, or MODE-SWITCHES" -- that
is, non-volatile state we could not get back.

Spinning the motor is none of those. It writes one volatile speed register and
issues a run command; nothing survives a power cycle. So rather than delete the
interlock and re-arm flash_picm.py, eeprom_repair.py and friends, this tool
does the one transient thing and cannot do anything else.

THE SEQUENCE, from docs/12-command-protocol.md section 5(b), which decoded it
out of FN_bDriveMotorAdvanceFilm = fcn.1000b6d0:

    02 05 44 02 A5 <lo> <hi>    set speed register 0xA5 (u16 LE). Does NOT move.
    04 03 44 00 A0              drive forward   (0xA1 would be reverse)
    04 03 44 00 A2              stop

All three expect `07 02 44 00`. Legal speed range for the Plus motor board is
0x03E8..0x7FFE (1000..32766); this defaults to the bottom of it.

SAFETY
------
* speed is clamped to the documented legal range and defaults to the minimum;
* run time is capped at MAX_SECONDS and defaults to well under it;
* the stop packet is sent from a finally: block, so it goes out even on
  KeyboardInterrupt, a USB error, or an unhandled exception;
* reverse is available but never the default;
* command bytes 0xA0/0xA1/0xA2 have bits 3 and 2 clear, so none of them fall in
  the 0x0C-0x0F range the bootloader dispatches as a row erase -- and they go to
  0x44, the application, which contains no TBLWT and cannot write flash at all.
"""
from __future__ import annotations

import argparse
import sys
import time

try:
    import usb.core
    import usb.util
except ImportError:
    sys.exit("pyusb is required:  pip install pyusb")

VID, PID = 0x0F05, 0xF135
EP_CMD_OUT, EP_CMD_IN = 0x01, 0x81
MOTOR = 0x44                      # AD_PICM_PLUS -- docs/03-protocol.md:117
HOST = 0x10

SPEED_MIN, SPEED_MAX = 0x03E8, 0x7FFE
MAX_SECONDS = 5.0

#: --long raises the cap to this. The 5 s default exists because this tool's
#: original job was a few seconds of "does the repaired PICM actually turn the
#: motor", where a runaway is pure downside. Respooling a roll is a different
#: job with a real reason to run longer, so it gets an explicit opt-in rather
#: than a quietly-raised default: the operator has to say they meant it, and
#: the stop still goes out from the finally: block on every exit path.
MAX_SECONDS_LONG = 60.0

CMD_FORWARD, CMD_REVERSE, CMD_STOP = 0xA0, 0xA1, 0xA2


def open_scanner():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        sys.exit(f"scanner {VID:#06x}:{PID:#06x} not found -- run "
                 "tools/pakon_load.py first")
    try:
        dev.set_configuration()
    except usb.core.USBError:
        pass
    usb.util.claim_interface(dev, 0)
    for ep in (EP_CMD_OUT, EP_CMD_IN):
        try:
            dev.clear_halt(ep)
        except usb.core.USBError:
            pass
    return dev


def send(dev, pkt, label, timeout=2000):
    print(f"  -> {pkt.hex(' ')}   {label}")
    try:
        dev.write(EP_CMD_OUT, pkt, timeout)
        resp = bytes(dev.read(EP_CMD_IN, 64, timeout))
    except usb.core.USBError as e:
        print(f"     USB error: {e}")
        return None
    ok = len(resp) > 3 and resp[0] == 7 and resp[3] == 0
    print(f"     <- {resp.hex(' ')}   {'ok' if ok else 'ERROR'}")
    return resp if ok else None


def clear_fault(dev):
    for _ in range(8):
        try:
            dev.write(EP_CMD_OUT, bytes([0x01, 0x03, HOST, 0x02, 0x03]), 2000)
            r = bytes(dev.read(EP_CMD_IN, 64, 2000))
        except usb.core.USBError:
            return False
        if len(r) > 3 and not (r[3] & 0x20):
            return True
        try:
            dev.write(EP_CMD_OUT, bytes([0x04, 0x03, HOST, 0x00, 0x85]), 2000)
            dev.read(EP_CMD_IN, 64, 2000)
        except usb.core.USBError:
            return False
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--speed", type=lambda s: int(s, 0), default=SPEED_MIN,
                    help=f"speed register 0xA5, {SPEED_MIN}..{SPEED_MAX}")
    ap.add_argument("--seconds", type=float, default=1.0,
                    help=f"how long to run (hard cap {MAX_SECONDS})")
    ap.add_argument("--reverse", action="store_true", help="drive reverse")
    ap.add_argument("--long", action="store_true",
                    help=f"raise the run-time cap from {MAX_SECONDS:.0f}s to "
                         f"{MAX_SECONDS_LONG:.0f}s. For respooling film, where "
                         f"a longer continuous run is the point. Watch the "
                         f"machine.")
    ap.add_argument("--speed-only", action="store_true",
                    help="write the speed register and stop there -- nothing moves")
    args = ap.parse_args()

    speed = max(SPEED_MIN, min(SPEED_MAX, args.speed))
    cap = MAX_SECONDS_LONG if args.long else MAX_SECONDS
    secs = max(0.0, min(cap, args.seconds))
    if speed != args.speed:
        print(f"speed clamped to legal range: {args.speed} -> {speed}")

    dev = open_scanner()
    print(f"scanner open: {VID:#06x}:{PID:#06x}")
    clear_fault(dev)

    print(f"\nset speed = {speed} ({speed:#06x})")
    if send(dev, bytes([0x02, 0x05, MOTOR, 0x02, 0xA5,
                        speed & 0xFF, (speed >> 8) & 0xFF]),
            "set speed register 0xA5 -- nothing moves yet") is None:
        return 1

    if args.speed_only:
        print("\n--speed-only: stopping here. The motor was never commanded.")
        return 0

    cmd = CMD_REVERSE if args.reverse else CMD_FORWARD
    print(f"\nrunning for {secs}s -- watch and listen")
    try:
        if send(dev, bytes([0x04, 0x03, MOTOR, 0x00, cmd]),
                f"{'REVERSE' if args.reverse else 'FORWARD'}") is None:
            return 1
        time.sleep(secs)
    finally:
        # Unconditional: this must go out on KeyboardInterrupt and on any error.
        print("\nstopping")
        send(dev, bytes([0x04, 0x03, MOTOR, 0x00, CMD_STOP]), "STOP")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
