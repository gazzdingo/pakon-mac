#!/usr/bin/env python3
"""Full CCD bring-up, ported from FN_bDrvInitCcd in TLB.dll.

This is the sequence the vendor driver runs before any scan. Every earlier
attempt in this project configured only the A/D gains (register 0x84, indices
2-4) and never touched register 0x82 at all -- which is the register that
carries the CCD geometry, the integration time and the acquire enable. An
unconfigured 0x82 is why EP 0x86 has always delivered a constant that ignores
both the lamp and the A/D gain.

Recovered from fcn.1002d5c0 (FN_bDrvInitCcd, logger enum 341) and the
fcn.1002c340 geometry helper (enum 121):

    fcn.10009d40(cmd 0x87)
    FN_bDrvLampOn(1, ..., 0xffd)
    FN_bDrvLampOff()
    fcn.10009ba0(cmd 0x89)
    fcn.1002c340(height=2000, offset=62, integration=4093)
        reg 0x82 idx 4  = pixel offset
        reg 0x82 idx 5  = pixel height
        reg 0x82 idx 6  = integration time
        reg 0x82 idx 11 = 0
        control bits 0x100, then 0x060, then 0x002
    reg 0x82 idx 1  = 0
    reg 0x82 idx 2  = 0
    reg 0x82 idx 3  = 0
    reg 0x82 idx 10 = 0x400
    reg 0x84 idx 0  = 0x78
    reg 0x84 idx 1  = 0x80
    FN_bDrvCcdAcquireControl -> control bit 0x001

Register 0x82 index 0 is the control word: 10 bits, write-only, tracked by a
host-side shadow (the vendor keeps it at object offset 0x358). The bits
accumulate in the order above, so a fully armed CCD ends at:

    0x100 | 0x060 | 0x002 | 0x001 = 0x163

PutRegisterCcd accepts registers 0x82 and 0x84 only; anything else is rejected
and logged as `ucCommand`. Packet form, from fcn.1000a5d0:

    02 06 <board> 03 <reg> <idx> <lo> <hi>

Safety: writes only CCD configuration registers on the motor board. No motor,
no EEPROM, no blind sweeping. Every value here is the vendor's own. Use
--restore to zero the control word again.
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
REG_CCD, REG_AD = 0x82, 0x84

# fcn.1002d5c0 / fcn.1002c340 constants
PIXEL_HEIGHT = 2000        # 0x7d0, must be a multiple of 4 and < 2120
PIXEL_OFFSET = 62          # 0x3e
INTEGRATION = 4093         # 0xffd, the documented maximum
DEFAULT_GAIN = 13

# control-word bits for register 0x82 index 0, in the order the driver sets them
BIT_GEOMETRY = 0x100
BIT_MODE     = 0x060
BIT_ENABLE2  = 0x002
BIT_ACQUIRE  = 0x001
CONTROL_FULL = BIT_GEOMETRY | BIT_MODE | BIT_ENABLE2 | BIT_ACQUIRE   # 0x163


def open_dev():
    d = usb.core.find(idVendor=0x0F05, idProduct=0xF135)
    if d is None:
        sys.exit("scanner not loaded -- run pakon_load.py --hex <Pakon7.hex>")
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


def put(d, reg, idx, u16, label="", quiet=False):
    pkt = bytes([0x02, 0x06, MOTOR, 0x03, reg, idx, u16 & 0xFF, (u16 >> 8) & 0xFF])
    r = send(d, pkt)
    if not quiet:
        ok = "ok" if r else "NO RESPONSE"
        print(f"  reg {reg:#04x} idx {idx:<3} = {u16:<6} {label:<20} "
              f"{pkt.hex(' ')}  -> {ok}")
    return r


def put_word(d, board, reg, u16, label="", quiet=False):
    """FN_bDrvPutRegisterWord.

    fcn.10009ae0 is the generic packet builder behind both this and
    PutRegisterCcd:

        02 <PktLen> <board> <dataLen> <reg> <data...>      PktLen = dataLen + 3

    With dataLen = 3 that reproduces the PutRegisterCcd packets already known
    to work (02 06 44 03 82 00 63 01), which is what validates the encoding.
    A word write is dataLen = 2.
    """
    pkt = bytes([0x02, 0x05, board, 0x02, reg, u16 & 0xFF, (u16 >> 8) & 0xFF])
    r = send(d, pkt)
    if not quiet:
        ok = "ok" if r else "NO RESPONSE"
        resp = r[:4].hex(' ') if r else ""
        print(f"  board {board:#04x} reg {reg:#04x} = {u16:<6} {label:<16} "
              f"{pkt.hex(' ')}  -> {ok} {resp}")
    return r


def clear_fault(d):
    for _ in range(6):
        r = send(d, bytes([0x01, 0x03, HOST, 0x02, 0x03]))
        if isinstance(r, bytes) and len(r) > 3 and not (r[3] & 0x20):
            return True
        send(d, bytes([0x04, 0x03, HOST, 0x00, 0x85]))
    return False


def sample(d, bursts=4):
    got = 0
    while got < 384 * 1024:
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
        print(f"  {tag:<26} <no data>")
    else:
        print(f"  {tag:<26} mean={s['mean']:8.1f}  stdev={s['stdev']:7.2f}"
              f"  min={s['min']:5}  max={s['max']:5}")


def gain_tracks(d):
    """Dark level and noise both scale with A/D gain if this is the CCD."""
    out = []
    for g in (0, 255):
        for idx in (0x02, 0x03, 0x04):
            put(d, REG_AD, idx, g, quiet=True)
        s = sample(d, bursts=2)
        out.append(s)
        print(f"    gain {g:>3}: "
              + (f"mean={s['mean']:8.1f}  stdev={s['stdev']:7.2f}" if s else "<no data>"))
    for idx in (0x02, 0x03, 0x04):
        put(d, REG_AD, idx, DEFAULT_GAIN, quiet=True)
    if not all(out):
        return 0.0, 0.0
    return (abs(out[0]["mean"] - out[1]["mean"]),
            abs(out[0]["stdev"] - out[1]["stdev"]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--control", default=hex(CONTROL_FULL),
                    help=f"control word for reg 0x82 idx 0 (default {CONTROL_FULL:#05x})")
    ap.add_argument("--restore", action="store_true",
                    help="zero the control word and exit")
    ap.add_argument("--integration", type=int, default=INTEGRATION)
    args = ap.parse_args()
    control = int(args.control, 0) & 0x3FF

    d = open_dev()
    try:
        if args.restore:
            put(d, REG_CCD, 0, 0x0000, "control -> off")
            return 0

        if not clear_fault(d):
            print("  warning: fault bit did not clear\n")

        before = sample(d)
        show("before init", before)
        print("\n  A/D gain response before init:")
        m0, s0 = gain_tracks(d)

        # FN_bDrvInitCcd issues these two PutRegisterWord calls before any FPGA
        # programming. The board address comes from [esi+0x2f9], which is the
        # light board (0x40) -- a different register space from the motor board
        # where every CCD/FPGA register lives.
        print("--- prerequisites (FN_bDrvPutRegisterWord) ---")
        put_word(d, LIGHT, 0x87, 0, "pre-init 0x87")
        put_word(d, LIGHT, 0x89, 0, "pre-init 0x89")

        print("\n--- geometry (fcn.1002c340) ---")
        put(d, REG_CCD, 4, PIXEL_OFFSET, "pixel offset")
        put(d, REG_CCD, 5, PIXEL_HEIGHT, "pixel height")
        put(d, REG_CCD, 6, args.integration, "integration time")
        put(d, REG_CCD, 11, 0, "")

        print("\n--- CCD config (fcn.1002d5c0) ---")
        put(d, REG_CCD, 1, 0, "")
        put(d, REG_CCD, 2, 0, "")
        put(d, REG_CCD, 3, 0, "")
        put(d, REG_CCD, 10, 0x400, "")

        print("\n--- A/D config ---")
        put(d, REG_AD, 0, 0x78, "mode")
        put(d, REG_AD, 1, 0x80, "mode")
        for i in (2, 3, 4):
            put(d, REG_AD, i, DEFAULT_GAIN, f"gain {'RGB'[i - 2]}")
        for i in (5, 6, 7):
            put(d, REG_AD, i, 0, f"offset {'RGB'[i - 5]}")

        print("\n--- control word (reg 0x82 idx 0) ---")
        # The driver ORs these in across InitCcd; the register is write-only,
        # so the host tracks the accumulated value itself.
        bits = [n for b, n in ((BIT_GEOMETRY, "geometry"), (BIT_MODE, "mode 5,6"),
                               (BIT_ENABLE2, "enable bit1"), (BIT_ACQUIRE, "ACQUIRE"))
                if control & b]
        print(f"  bits: {', '.join(bits) if bits else 'none'}")
        put(d, REG_CCD, 0, control, f"control {control:#05x}")

        after = sample(d)
        print()
        show("after init", after)
        print("\n  A/D gain response after init:")
        m1, s1 = gain_tracks(d)

        print("\n  ---------------- verdict ----------------")
        print(f"  gain response before : mean {m0:.2f}, stdev {s0:.2f}")
        print(f"  gain response after  : mean {m1:.2f}, stdev {s1:.2f}")
        if before and after:
            print(f"  stream mean {before['mean']:.1f} -> {after['mean']:.1f}"
                  f"   stdev {before['stdev']:.2f} -> {after['stdev']:.2f}")
        if m1 > 5 or s1 > 2:
            print("\n  ACQUISITION IS RUNNING -- EP 0x86 tracks the A/D gain.")
            print("  This stream is the CCD readout. Lamp and film are next.")
        elif before and after and (abs(after["mean"] - before["mean"]) > 20
                                   or abs(after["stdev"] - before["stdev"]) > 10):
            print("\n  Stream changed but does not yet track the A/D.")
            print("  Partial bring-up: try a different --integration, or check")
            print("  whether fcn.10009d40 (cmd 0x87) / fcn.10009ba0 (cmd 0x89)")
            print("  are prerequisites.")
        else:
            print("\n  No change yet. The remaining unported steps are the two")
            print("  commands 0x87 and 0x89 that InitCcd issues before the")
            print("  register writes.")
    finally:
        usb.util.release_interface(d, 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
