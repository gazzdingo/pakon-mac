#!/usr/bin/env python3
"""Replay the vendor's captured light-board sequence, byte for byte.

Every value here was captured off THIS unit's wire while PSI drove it
(docs/59). Nothing is invented, and each one was checked against the clamp
table that docs/40 derived independently from FN_bDrvLampOn:

    IR off:  R<=4  G<=20  B<=20  Ir<=0        captured: 3, 11, 7, 0
    on_ch <= N-2                              captured max 938, N-2 = 980

Channel order on the wire is B, Ir, R, -, G -- NOT R,G,B. Byte 3 of 0x81 and
u16 slot 3 of 0x82 are hard zeros. Getting this order wrong drives the wrong
emitter, which is why it is spelled out at every construction site below.

Two deliberate departures from the capture, both toward safety:

  * The vendor asserts enable (step 16) and THEN zeroes drive (step 17). If the
    board holds stale duty, that is a flash at an unknown level. We program
    drive first, then enable. Same end state, no pulse.
  * Default level is the capture's step-82 calibration drive (duty .16/.67/.38),
    not step-100's scan drive (.82/.93/.96). --full opts into the latter.

Dry run by default. --commit is required to put anything on the wire.

Usage:
    ./lamp_replay_vendor.py                 # print the packets, send nothing
    ./lamp_replay_vendor.py --commit        # light at calibration drive, 5 s
    ./lamp_replay_vendor.py --commit --full # light at full scan drive, 5 s
    ./lamp_replay_vendor.py --commit --hold 20

Only reg 0x81 and reg 0x82 are per-unit; the rest of the sequence is protocol or
firmware constants and transfers to any F-135 Plus (docs/59). For a different
scanner, override those two from that unit's CiConfigLight registry values:

    ./lamp_replay_vendor.py --levels 11,4,5,20 --duty 163,0,646,373
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
LIGHT = 0x40
HOST = 0x10

# ---------------------------------------------------------------- captured --
# docs/59. Channel order B, Ir, R, -, G.
LEVELS = (7, 0, 3, 11)              # B, Ir, R, G          <- reg 0x81
N_PERIOD = 982                      # exposure 4093, DpiBase16_35 non-IR
DRIVE_CAL = (156, 0, 654, 374)      # B, Ir, R, G   step 82
DRIVE_FULL = (804, 0, 912, 938)     # B, Ir, R, G   step 100

# reg -> 4-byte payload, exactly as captured (steps 9-12). Monitor thresholds,
# not TEC commands; docs/40 proved only 0x8E is gated, and 0x8E is never sent.
THRESHOLDS = [
    (0x8F, bytes((0xE8, 0xFF, 0x18, 0x00))),   # [ -24,  24]
    (0x8C, bytes((0xE0, 0xFF, 0x20, 0x00))),   # [ -32,  32]
    (0x8B, bytes((0xF0, 0x00, 0x20, 0x03))),   # [ 240, 800]
    (0x8D, bytes((0xA0, 0x00, 0x70, 0x03))),   # [ 160, 880]
]

# Clamp ceilings, docs/40 fcn.100203c0, selected by [this+0x2f8]==0x44.
CLAMP_IR_OFF = {"R": 4, "G": 20, "B": 20, "Ir": 0}
CLAMP_IR_ON = {"R": 8, "G": 24, "B": 24, "Ir": 8}


def check_safe(levels, drive, n):
    """Refuse anything the firmware's own clamps would reject.

    The captured values pass this; the point is that a future edit that does
    not pass cannot reach the wire.
    """
    b, ir, r, g = levels
    clamp = CLAMP_IR_OFF if ir == 0 else CLAMP_IR_ON
    bad = []
    for ch, v in (("R", r), ("G", g), ("B", b), ("Ir", ir)):
        if v > clamp[ch]:
            bad.append(f"level {ch}={v} exceeds ceiling {clamp[ch]}")
    for ch, v in zip(("B", "Ir", "R", "G"), drive):
        if v > n - 2:
            bad.append(f"on-count {ch}={v} exceeds N-2={n - 2}")
    if n <= 2 or n > 0xFFFF:
        bad.append(f"period N={n} out of range")
    return bad


def pkt_write(reg, payload):
    payload = bytes(payload)
    return bytes((0x02, len(payload) + 3, LIGHT, len(payload), reg)) + payload


def pkt_read(reg, length):
    return bytes((0x01, 0x03, LIGHT, length, reg))


def pkt_cmd(reg):
    return bytes((0x04, 0x03, LIGHT, 0x00, reg))


def enc_levels(levels):
    """reg 0x81, 5 B: [level_B, level_Ir, level_R, 0x00, level_G]."""
    b, ir, r, g = levels
    return bytes((b, ir, r, 0x00, g))


def enc_drive(drive, n):
    """reg 0x82, 12 B: six LE u16 [on_B][on_Ir][on_R][0x0000][on_G][N]."""
    b, ir, r, g = drive
    out = bytearray()
    for v in (b, ir, r, 0, g, n):
        out += bytes((v & 0xFF, (v >> 8) & 0xFF))
    return bytes(out)


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


def send(dev, pkt, timeout=2000):
    try:
        dev.write(EP_CMD_OUT, pkt, timeout)
        return bytes(dev.read(EP_CMD_IN, 64, timeout))
    except usb.core.USBError as exc:
        return exc


def step(dev, label, pkt, commit):
    hexs = " ".join(f"{b:02X}" for b in pkt)
    if not commit:
        print(f"  [dry] {label:34} {hexs}")
        return None
    resp = send(dev, pkt)
    if isinstance(resp, Exception):
        print(f"  [ERR] {label:34} {hexs}   {resp}")
        return None
    rhex = " ".join(f"{b:02X}" for b in resp[:8])
    ok = "ok" if len(resp) >= 4 and resp[0] == 0x07 and resp[3] == 0x00 else "?"
    print(f"  [{ok:>3}] {label:34} {hexs}   -> {rhex}")
    return resp


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--commit", action="store_true",
                    help="actually send. Without this nothing touches the bus.")
    ap.add_argument("--full", action="store_true",
                    help="use the step-100 scan drive instead of step-82 calibration drive")
    ap.add_argument("--hold", type=float, default=5.0,
                    help="seconds to hold the lamp lit (default 5, as WaitForLamp)")
    # The only two per-unit writes. Everything else in the sequence is protocol
    # or a firmware constant and transfers to any F-135 Plus -- docs/59.
    ap.add_argument("--levels", metavar="B,Ir,R,G",
                    help="override reg 0x81 for a different unit, e.g. 11,4,5,20 "
                         "(this unit's registry values). Order is B,Ir,R,G.")
    ap.add_argument("--duty", metavar="B,Ir,R,G",
                    help="override reg 0x82 PWM on-counts. Order is B,Ir,R,G.")
    ap.add_argument("--exposure", type=int, default=4093,
                    help="exposure for N = trunc(exposure*1e6/(2*2083333.3)). "
                         "4093 = DpiBase16_35 non-IR, which is what was captured.")
    args = ap.parse_args()

    def parse4(s, what):
        try:
            v = tuple(int(x) for x in s.split(","))
        except ValueError:
            sys.exit(f"--{what} must be four integers B,Ir,R,G")
        if len(v) != 4:
            sys.exit(f"--{what} must be four integers B,Ir,R,G -- got {len(v)}")
        return v

    levels = parse4(args.levels, "levels") if args.levels else LEVELS
    n_period = int(args.exposure * 1e6 / (2 * 2083333.3))
    if args.duty:
        drive, which = parse4(args.duty, "duty"), "override"
    else:
        drive = DRIVE_FULL if args.full else DRIVE_CAL
        which = "step-100 SCAN" if args.full else "step-82 calibration"
        if n_period != N_PERIOD:
            sys.exit(f"--exposure {args.exposure} gives N={n_period}, but the "
                     f"captured drive values are on-counts for N={N_PERIOD}. "
                     f"Pass --duty as well, or leave --exposure alone.")

    bad = check_safe(levels, drive, n_period)
    if bad:
        print("REFUSING -- values violate the firmware clamps from docs/40:")
        for b in bad:
            print(f"  {b}")
        return 1

    b, ir, r, g = levels
    db, dir_, dr, dg = drive
    print(f"vendor lamp replay -- docs/59      drive set: {which}")
    print(f"  levels   B={b} Ir={ir} R={r} G={g}      (ceilings "
          f"{CLAMP_IR_OFF if ir == 0 else CLAMP_IR_ON})")
    print(f"  drive    B={db} Ir={dir_} R={dr} G={dg}   N={n_period}   "
          f"duty {db / n_period:.3f}/{dr / n_period:.3f}/{dg / n_period:.3f}")
    print(f"  clamp check: PASS")
    if not args.commit:
        print("\nDRY RUN -- nothing will be sent. Re-run with --commit.\n")

    dev = open_scanner() if args.commit else None

    try:
        print("\n-- init (capture steps 5-15) --")
        step(dev, "board select 0x03", pkt_write(0x03, b"\x01"), args.commit)
        step(dev, "FIFO/DX reset 0x8A", pkt_cmd(0x8A), args.commit)
        for reg, pay in THRESHOLDS:
            step(dev, f"threshold 0x{reg:02X}", pkt_write(reg, pay), args.commit)
        step(dev, "0xD0", pkt_write(0xD0, b"\x00"), args.commit)
        step(dev, "0xD1", pkt_write(0xD1, b"\x01"), args.commit)
        step(dev, "0x87", pkt_write(0x87, b"\x00\x00"), args.commit)

        # Departure from the capture: drive BEFORE enable, so there is no
        # pulse from whatever the board happened to be holding.
        print("\n-- program drive, then enable (steps 81,82,80 reordered) --")
        step(dev, "levels 0x81", pkt_write(0x81, enc_levels(levels)), args.commit)
        step(dev, "drive 0x82", pkt_write(0x82, enc_drive(drive, n_period)),
             args.commit)
        step(dev, "ENABLE visible 0x80=01", pkt_write(0x80, b"\x01"), args.commit)

        if args.commit:
            print(f"\n-- lamp should be LIT. holding {args.hold}s --")
            deadline = time.time() + args.hold
            while time.time() < deadline:
                time.sleep(0.5)
                st = send(dev, pkt_read(0x83, 1))
                tp = send(dev, pkt_read(0x84, 2))
                if isinstance(st, bytes) and isinstance(tp, bytes) and len(tp) >= 6:
                    temp = tp[4] | tp[5] << 8
                    print(f"     status={st[4] if len(st) > 4 else '??':<4} "
                          f"temp={temp:5} raw ({temp / 16.0:.1f} degC if 1/16)")
        else:
            print("\n  [dry] hold, polling 0x83 status and 0x84 temperature")
            step(dev, "read status 0x83", pkt_read(0x83, 1), args.commit)
            step(dev, "read temp 0x84", pkt_read(0x84, 2), args.commit)
    finally:
        print("\n-- lamp off --")
        step(dev, "DISABLE 0x80=00", pkt_write(0x80, b"\x00"), args.commit)
        if args.commit:
            step(dev, "drive to zero 0x82", pkt_write(0x82, enc_drive((0, 0, 0, 0),
                                                                     n_period)),
                 args.commit)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
