#!/usr/bin/env python3
"""Start CCD acquisition by setting bit 0 of CCD control register 0x82.

Recovered from TLB.dll by symbolicating the vendor logger. Each function
passes its own enum to the logger, and the enum->name table lives in
fcn.100170b0, so `push <enum>` immediately before the log handle identifies
the function. Enum 82 = FN_bDrvCcdAcquireControl = fcn.10029810, a thin
wrapper over fcn.10029770:

    mov si, word [edi + 0x358]     ; host-side shadow of the register
    and eax, 0x3ff                 ; 10-bit mask
    set:   new = shadow |  mask
    clear: new = shadow & ~mask
    push 0x82                      ; CCD register 0x82
    call fcn.1000a5d0              ; PutRegisterCcd
    mov word [edi + 0x358], si     ; shadow updated only on success

Bit masks seen at the call sites:
    0x001  bit 0     FN_bDrvCcdAcquireControl -- master acquire enable
    0x002  bit 1     fcn.1002c340
    0x060  bits 5,6  fcn.1002c340 (set together)
    0x100  bit 8     fcn.10029860

Why this matters: EP 0x86 has always delivered a constant mean of ~1240 that
ignores the lamp and ignores the A/D gain across its whole 0..255 range. That
is what an un-armed acquisition looks like. Register 0x84 (gains/offsets) has
been written many times in this project; register 0x82 never has.

The test needs no lamp and no film -- the CCD dark level and its noise both
scale with A/D gain, so gain responsiveness alone proves the stream has become
the sensor's readout.

Safety: one 16-bit control register, written and then restored to 0. No motor,
no lamp, no EEPROM, no blind sweeping.
"""
from __future__ import annotations

import argparse
import statistics
import struct
import sys

import usb.core
import usb.util

EP_OUT, EP_IN, EP_DATA = 0x01, 0x81, 0x86
HOST, MOTOR = 0x10, 0x44
REG_ACQ_CONTROL, REG_AD = 0x82, 0x84
BIT_ACQUIRE = 0x0001
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


def accepted(r):
    """Type 7 with status 0 only. Status 1 is a NAK, 2 is unsupported."""
    return bool(r) and len(r) > 3 and r[0] == 0x07 and r[3] == 0x00


def put_ccd(d, reg, idx, u16):
    """PutRegisterCcd: 02 06 44 03 <reg> <idx> <lo> <hi>

    Returns the response only when the board actually accepted it.
    """
    r = send(d, bytes([0x02, 0x06, MOTOR, 0x03, reg, idx,
                       u16 & 0xFF, (u16 >> 8) & 0xFF]))
    return r if accepted(r) else None


def clear_fault(d):
    for _ in range(6):
        r = send(d, bytes([0x01, 0x03, HOST, 0x02, 0x03]))
        if isinstance(r, bytes) and len(r) > 3 and not (r[3] & 0x20):
            return
        send(d, bytes([0x04, 0x03, HOST, 0x00, 0x85]))


def sample(d, bursts=4):
    got = 0
    while got < 384 * 1024:                      # drop the stale FIFO first
        try:
            got += len(d.read(EP_DATA, 32768, 250))
        except usb.core.USBError:
            break
    vals = []
    for _ in range(bursts):
        try:
            b = d.read(EP_DATA, 16384, 600)
        except usb.core.USBError:
            break
        vals.extend(struct.unpack("<%dH" % (len(b) // 2), bytes(b[:len(b) // 2 * 2])))
    if not vals:
        return None
    return {"mean": statistics.fmean(vals), "stdev": statistics.pstdev(vals),
            "min": min(vals), "max": max(vals)}


def show(tag, s):
    if not s:
        print(f"  {tag:<22} <no data>")
        return
    print(f"  {tag:<22} mean={s['mean']:8.1f}  stdev={s['stdev']:7.2f}"
          f"  min={s['min']:5}  max={s['max']:5}")


def gain_sweep(d, label):
    """Dark level and noise must both scale with A/D gain if this is the CCD."""
    print(f"\n  A/D gain sweep {label}:")
    print(f"    {'gain':>5}  {'mean':>9}  {'stdev':>8}")
    rows = []
    for g in (0, 13, 128, 255):
        for idx in (0x02, 0x03, 0x04):
            put_ccd(d, REG_AD, idx, g)
        s = sample(d, bursts=2)
        if s:
            rows.append((g, s))
            print(f"    {g:>5}  {s['mean']:9.1f}  {s['stdev']:8.2f}")
    for idx in (0x02, 0x03, 0x04):
        put_ccd(d, REG_AD, idx, DEFAULT_GAIN)
    if len(rows) < 2:
        return 0.0, 0.0
    means = [r[1]["mean"] for r in rows]
    sds = [r[1]["stdev"] for r in rows]
    return max(means) - min(means), max(sds) - min(sds)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bits", default="0x001",
                    help="mask to set in register 0x82 (default 0x001, acquire)")
    ap.add_argument("--keep", action="store_true",
                    help="leave the bit set on exit instead of restoring 0")
    args = ap.parse_args()
    mask = int(args.bits, 0) & 0x3FF

    d = open_dev()
    try:
        clear_fault(d)

        print("CCD acquire control -- register 0x82\n")
        before = sample(d)
        show("before (reg82=0x000)", before)
        m0, s0 = gain_sweep(d, "with acquisition OFF")

        print(f"\n  setting reg 0x82 = {mask:#05x}")
        r = put_ccd(d, REG_ACQ_CONTROL, 0x00, mask)
        print(f"  response: {r.hex(' ') if r else '<none>'}")

        after = sample(d)
        print()
        show("after  (reg82 set)", after)
        m1, s1 = gain_sweep(d, "with acquisition ON")

        if not args.keep:
            print("\n  restoring reg 0x82 = 0x000")
            put_ccd(d, REG_ACQ_CONTROL, 0x00, 0x0000)

        print("\n  ---------------- verdict ----------------")
        print(f"  gain response, acquisition OFF : mean spread {m0:.2f}, stdev spread {s0:.2f}")
        print(f"  gain response, acquisition ON  : mean spread {m1:.2f}, stdev spread {s1:.2f}")
        if before and after:
            print(f"  stream mean {before['mean']:.1f} -> {after['mean']:.1f}"
                  f"   stdev {before['stdev']:.2f} -> {after['stdev']:.2f}")
        if m1 > 5 or s1 > 2:
            print("\n  ACQUISITION IS RUNNING -- EP 0x86 now tracks the A/D.")
            print("  The stream is the CCD readout. Lamp and film are next.")
        elif before and after and (abs(after["mean"] - before["mean"]) > 20
                                   or abs(after["stdev"] - before["stdev"]) > 10):
            print("\n  Stream changed but still does not track the A/D.")
            print("  Bit 0 does something; more of register 0x82 is needed")
            print("  (bits 1, 5, 6, 8 are used by the vendor driver).")
        else:
            print("\n  No change. Bit 0 alone does not arm acquisition;")
            print("  try --bits 0x063 (bits 0,1,5,6) or 0x163.")
    finally:
        usb.util.release_interface(d, 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
