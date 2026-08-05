#!/usr/bin/env python3
"""Light the Pakon lamp and leave it on, so a human can confirm visually.

The EP 0x86 sensor stream does not register the illumination (it sits at a
constant mean regardless), so the operator is a more reliable detector than the
CCD data. This tool runs the lamp bring-up and then holds the lamp on until
interrupted, printing the sensor level periodically for comparison.

Sequence and encodings are from FN_bDrvLampOn (TLB.dll fcn.1002c5f0):

    reg 0x80  1 B   lamp enable bitmask (bit0 visible, bit1 IR)
    reg 0x81  5 B   LED levels        slot order [B, Ir, R, 0, G]
    reg 0x82 12 B   LED PWM, six LE u16 [on_B, on_Ir, on_R, 0, on_G, N]

Hardware level clamps (fcn.100203c0): R<=8, G<=24, B<=24, Ir<=8.
Order is 0x80=off -> 0x82 -> 0x81 -> 0x80=on, so the drive registers are never
in flux while the lamp is enabled.

  ./lamp_on.py                 # all visible channels, max legal levels
  ./lamp_on.py --off           # turn the lamp off
  ./lamp_on.py --channel G     # single channel
"""
from __future__ import annotations

import argparse
import os
import struct
import sys
import time

import usb.core
import usb.util

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from write_guard import require_writes_unlocked   # noqa: E402

EP_CMD_OUT, EP_CMD_IN, EP_DATA = 0x01, 0x81, 0x86
LIGHT_BOARD = 0x40
HOST = 0x10

# exposure 1549 -> N = round(1549 * 0.6); duty 0.5 -> on = N // 2
EXPOSURE = 1549
N = round(EXPOSURE * 0.6)
ON = N // 2

CLAMP = {"R": 8, "G": 24, "B": 24, "Ir": 8}


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


def send(d, pkt, label="", quiet=False):
    try:
        d.write(EP_CMD_OUT, pkt, 1500)
    except usb.core.USBError:
        print(f"  {label}: WRITE TIMEOUT")
        return None
    try:
        r = bytes(d.read(EP_CMD_IN, 64, 1500))
        if not quiet:
            print(f"  {label:<26}{pkt.hex(' '):<38} -> {r.hex(' ')}")
        return r
    except usb.core.USBError:
        print(f"  {label}: no response")
        return None


def clear_fault(d):
    for _ in range(6):
        r = send(d, bytes([0x01, 0x03, HOST, 0x02, 0x03]), quiet=True)
        if r and len(r) > 3 and not (r[3] & 0x20):
            return
        send(d, bytes([0x04, 0x03, HOST, 0x00, 0x85]), quiet=True)


def level_packet(B=0, Ir=0, R=0, G=0):
    return bytes([0x02, 0x08, LIGHT_BOARD, 0x05, 0x81,
                  min(B, CLAMP["B"]), min(Ir, CLAMP["Ir"]),
                  min(R, CLAMP["R"]), 0, min(G, CLAMP["G"])])


def pwm_packet(on_B=0, on_Ir=0, on_R=0, on_G=0):
    body = struct.pack("<6H", on_B, on_Ir, on_R, 0, on_G, N)
    return bytes([0x02, 0x0F, LIGHT_BOARD, 0x0C, 0x82]) + body


def sensor_level(d):
    got = 0
    while got < 256 * 1024:                      # flush the stale FIFO first
        try:
            got += len(d.read(EP_DATA, 32768, 300))
        except usb.core.USBError:
            break
    vals = []
    for _ in range(3):
        try:
            b = d.read(EP_DATA, 16384, 600)
        except usb.core.USBError:
            break
        vals.extend(struct.unpack("<%dH" % (len(b) // 2), bytes(b[:len(b) // 2 * 2])))
    return (max(vals), sum(vals) / len(vals)) if vals else (0, 0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--off", action="store_true", help="turn the lamp off and exit")
    ap.add_argument("--channel", choices=["R", "G", "B", "all"], default="all")
    ap.add_argument("--ir", action="store_true", help="enable the IR channel too")
    ap.add_argument("--hold", type=float, default=45.0,
                    help="seconds to hold the lamp on")
    args = ap.parse_args()

    # Interlock: writes light-board LED level and PWM registers.
    require_writes_unlocked("lamp_on.py",
                            "writes light-board LED level/PWM registers")

    d = open_dev()
    try:
        if args.off:
            send(d, bytes([0x02, 0x04, LIGHT_BOARD, 0x01, 0x80, 0x00]), "lamp OFF")
            return 0

        clear_fault(d)
        mx, mn = sensor_level(d)
        print(f"dark baseline: max={mx} mean={mn:.0f}\n")

        ch = args.channel
        lv = dict(B=0, Ir=0, R=0, G=0)
        on = dict(on_B=0, on_Ir=0, on_R=0, on_G=0)
        for name in (["R", "G", "B"] if ch == "all" else [ch]):
            lv[name] = CLAMP[name]
            on[f"on_{name}"] = ON
        if args.ir:
            lv["Ir"] = CLAMP["Ir"]
            on["on_Ir"] = ON

        mask = 0x03 if args.ir else 0x01
        print(f"lighting: channels={ch}{' +IR' if args.ir else ''} "
              f"N={N} on={ON}\n")
        send(d, bytes([0x02, 0x04, LIGHT_BOARD, 0x01, 0x80, 0x00]), "1. lamp off")
        send(d, pwm_packet(**on), "2. reg 0x82 PWM")
        send(d, level_packet(**lv), "3. reg 0x81 levels")
        send(d, bytes([0x02, 0x04, LIGHT_BOARD, 0x01, 0x80, mask]), "4. lamp ENABLE")

        print(f"\n>>> LAMP SHOULD BE ON NOW -- holding {args.hold:.0f}s <<<\n")
        t0 = time.time()
        while time.time() - t0 < args.hold:
            mx, mn = sensor_level(d)
            print(f"   t+{time.time()-t0:5.1f}s  sensor max={mx:5} mean={mn:6.0f}")
            time.sleep(3)
        send(d, bytes([0x02, 0x04, LIGHT_BOARD, 0x01, 0x80, 0x00]), "lamp off")
    finally:
        usb.util.release_interface(d, 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
