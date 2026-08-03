#!/usr/bin/env python3
"""Find what starts real CCD acquisition on EP 0x86.

Established: EP 0x86 is live but does NOT carry the readout of the sensor we
program. Driving the CCD A/D gain from 0 to 255 moves the data by 0.37 in mean
and 0.20 in stdev -- i.e. not at all. The lamp lights (operator-confirmed) and
never appears in the data either.

So acquisition is not running. This sweeps the host board (0x10 -- the FX2
itself, which owns the EP 0x86 FIFO) looking for a command that changes the
character of the stream.

Detector: after each command, compare the stream's statistics against baseline.
Acquisition starting should change mean, spread, or both, markedly. A secondary
check re-tests A/D gain responsiveness, which is the definitive signal that the
stream has become the configured sensor's output.

Host board Type 4 commands already known: 0x85 = host clear/ack.
"""
from __future__ import annotations

import argparse
import statistics
import struct
import sys

import usb.core
import usb.util

EP_OUT, EP_IN, EP_DATA = 0x01, 0x81, 0x86
HOST, LIGHT, MOTOR = 0x10, 0x40, 0x44


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


def stats(d, bursts=3):
    got = 0
    while got < 256 * 1024:
        try:
            got += len(d.read(EP_DATA, 32768, 250))
        except usb.core.USBError:
            break
    vals = []
    for _ in range(bursts):
        try:
            b = d.read(EP_DATA, 16384, 500)
        except usb.core.USBError:
            break
        vals.extend(struct.unpack("<%dH" % (len(b) // 2), bytes(b[:len(b) // 2 * 2])))
    if not vals:
        return None
    return statistics.fmean(vals), statistics.pstdev(vals), max(vals)


def gain_responsive(d):
    """Definitive check: does the stream track the A/D gain?"""
    out = []
    for g in (0, 255):
        for idx in (0x02, 0x03, 0x04):
            send(d, bytes([0x02, 0x06, MOTOR, 0x03, 0x84, idx, g, 0x00]))
        s = stats(d, bursts=2)
        out.append(s[0] if s else 0)
    for idx in (0x02, 0x03, 0x04):
        send(d, bytes([0x02, 0x06, MOTOR, 0x03, 0x84, idx, 13, 0x00]))
    return abs(out[0] - out[1]) > 5


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--board", default="0x10")
    args = ap.parse_args()
    board = int(args.board, 0)

    d = open_dev()
    try:
        for _ in range(6):
            r = send(d, bytes([0x01, 0x03, HOST, 0x02, 0x03]))
            if isinstance(r, bytes) and len(r) > 3 and not (r[3] & 0x20):
                break
            send(d, bytes([0x04, 0x03, HOST, 0x00, 0x85]))

        base = stats(d)
        if not base:
            sys.exit("no data on EP 0x86 at all")
        print(f"baseline: mean={base[0]:.1f} stdev={base[1]:.2f} max={base[2]}")
        print(f"sweeping Type 4 commands on board {board:#04x}\n")

        hits = []
        for cmd in range(0x100):
            r = send(d, bytes([0x04, 0x03, board, 0x00, cmd]))
            if r == "WEDGED":
                print(f"  cmd {cmd:#04x}: endpoint stopped draining -- stopping")
                break
            if not isinstance(r, bytes) or len(r) < 4 or r[3] not in (0, 8):
                continue
            s = stats(d)
            if not s:
                print(f"  cmd {cmd:#04x}: accepted, stream STOPPED")
                continue
            dmean = abs(s[0] - base[0])
            dsd = abs(s[1] - base[1])
            marker = ""
            if dmean > 20 or dsd > 10:
                marker = "   *** STREAM CHANGED ***"
                hits.append((cmd, s))
            print(f"  cmd {cmd:#04x}: accepted  mean={s[0]:8.1f} "
                  f"stdev={s[1]:7.2f} max={s[2]:5}{marker}")
            if marker:
                print("     checking whether it now tracks the A/D gain...")
                if gain_responsive(d):
                    print("     *** YES -- ACQUISITION IS RUNNING ***")
                    break
                print("     no; stream changed but is still not the sensor")

        print()
        if hits:
            for c, s in hits:
                print(f"  candidate: cmd {c:#04x} -> mean {s[0]:.1f} stdev {s[1]:.2f}")
        else:
            print(f"  no command on board {board:#04x} altered the stream")
    finally:
        usb.util.release_interface(d, 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
