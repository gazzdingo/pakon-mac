#!/usr/bin/env python3
"""Determine whether EP 0x86 actually carries the CCD readout we configure.

Observed: the LED illuminator lights (operator-confirmed, bright blue) yet
EP 0x86 stays at a constant mean of ~1240 regardless of lamp state, LED level,
FPGA exposure window, or A/D programming.

If EP 0x86 were the readout of the CCD whose A/D we are programming, then
driving the A/D gain between its extremes must change the data -- dark level
and noise both scale with gain. If the data does not move, the stream is not
that sensor's output, and no amount of lamp or exposure work will ever show
light in it.

A/D register indices, recovered by emulating TLB.dll:
    reg 0x84 idx 0x02/0x03/0x04   gains   (R, G, B)
    reg 0x84 idx 0x05/0x06/0x07   offsets (R, G, B)
Only registers 0x82 and 0x84 are accepted; PutRegisterCcd rejects anything
else as `ucCommand`.

This tool only writes A/D gain and offset registers, which are settings rather
than actuators, and restores the default gain of 13 on exit.
"""
from __future__ import annotations

import os
import statistics
import struct
import sys

import usb.core
import usb.util

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from write_guard import require_writes_unlocked   # noqa: E402

EP_OUT, EP_IN, EP_DATA = 0x01, 0x81, 0x86
HOST, MOTOR = 0x10, 0x44
DEFAULT_GAIN = 13


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


def send(d, pkt, timeout=1200):
    try:
        d.write(EP_OUT, pkt, timeout)
    except usb.core.USBError:
        return None
    try:
        return bytes(d.read(EP_IN, 64, timeout))
    except usb.core.USBError:
        return None


def ccd(reg, idx, u16):
    return bytes([0x02, 0x06, MOTOR, 0x03, reg, idx, u16 & 0xFF, (u16 >> 8) & 0xFF])


def sample(d):
    """Flush the stale FIFO, then characterise a fresh block."""
    got = 0
    while got < 384 * 1024:
        try:
            got += len(d.read(EP_DATA, 32768, 250))
        except usb.core.USBError:
            break
    vals = []
    for _ in range(4):
        try:
            b = d.read(EP_DATA, 16384, 600)
        except usb.core.USBError:
            break
        vals.extend(struct.unpack("<%dH" % (len(b) // 2), bytes(b[:len(b) // 2 * 2])))
    if not vals:
        return None
    return {
        "n": len(vals),
        "mean": statistics.fmean(vals),
        "stdev": statistics.pstdev(vals),
        "min": min(vals),
        "max": max(vals),
    }


def main() -> int:
    # Interlock. This tool writes A/D gain/offset registers, and its
    # "restore default gain 13" write is the prime suspect for the stray
    # 0x0D expected at U11 internal EEPROM index 4.
    require_writes_unlocked("probe_sensor_path.py",
                            "writes CCD A/D gain and offset registers")
    d = open_dev()
    try:
        for _ in range(6):
            r = send(d, bytes([0x01, 0x03, HOST, 0x02, 0x03]))
            if isinstance(r, bytes) and len(r) > 3 and not (r[3] & 0x20):
                break
            send(d, bytes([0x04, 0x03, HOST, 0x00, 0x85]))

        print("Driving the CCD A/D gain across its range.")
        print("If EP 0x86 is this sensor's readout, mean and stdev MUST move.\n")
        print(f"  {'gain':>6}  {'mean':>9}  {'stdev':>8}  {'min':>6}  {'max':>6}")
        print(f"  {'-'*6}  {'-'*9}  {'-'*8}  {'-'*6}  {'-'*6}")
        rows = []
        for gain in (0, 1, 13, 64, 128, 255):
            for idx in (0x02, 0x03, 0x04):
                send(d, ccd(0x84, idx, gain))
            s = sample(d)
            if not s:
                print(f"  {gain:>6}   <no data>")
                continue
            rows.append((gain, s))
            print(f"  {gain:>6}  {s['mean']:9.1f}  {s['stdev']:8.2f}"
                  f"  {s['min']:6}  {s['max']:6}")

        print("\n  restoring default gain 13")
        for idx in (0x02, 0x03, 0x04):
            send(d, ccd(0x84, idx, DEFAULT_GAIN))

        if len(rows) >= 2:
            means = [r[1]["mean"] for r in rows]
            sds = [r[1]["stdev"] for r in rows]
            spread_mean = max(means) - min(means)
            spread_sd = max(sds) - min(sds)
            print(f"\n  mean spread across gains : {spread_mean:.2f}")
            print(f"  stdev spread across gains: {spread_sd:.2f}")
            if spread_mean < 5 and spread_sd < 2:
                print("\n  VERDICT: EP 0x86 is INDEPENDENT of the A/D we program.")
                print("  This stream is not the readout of the sensor being")
                print("  configured, so lamp and exposure work cannot make light")
                print("  appear in it. Find the real acquisition path first.")
            else:
                print("\n  VERDICT: EP 0x86 DOES track the A/D -- it is the")
                print("  configured sensor. The blockage is optical, not a data path.")
    finally:
        usb.util.release_interface(d, 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
