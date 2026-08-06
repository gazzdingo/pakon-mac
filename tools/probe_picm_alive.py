#!/usr/bin/env python3
"""Ask PICM (0x44) and PICL (0x40) whether they are answering. READ ONLY.

Written for one question, on the day U34's erased flash row was repaired: does
the PICM application come up and answer on the I2C bus again?

WHY NOT pakon_cmd.py
--------------------
That tool can send arbitrary packets, so the write interlock refuses to run it
-- correctly. Rather than lift the interlock to ask a read-only question, this
sends exactly one packet shape and cannot be talked into anything else.

WHY THIS CANNOT ERASE ANYTHING
------------------------------
Two independent reasons, either sufficient:

1. It refuses to address 0x42 or 0x46. Those are the PICL/PICM BOOTLOADER
   addresses, and the bootloader is the only code on either chip that can erase
   or write flash. A 2-byte type-4 packet to 0x46 whose command byte has bits
   3+2 set (0x0C-0x0F) is dispatched as a row erase at the latched address --
   that is the mechanism that most likely destroyed 0x0D00 in the first place.
   See docs/34-repair-procedure.md section 2.

2. The addresses it does allow, 0x40 and 0x44, are the APPLICATION addresses.
   The application image contains no TBLWT instruction anywhere and never sets
   EECON1.EEPGD, so it has no flash-write capability to invoke. Nothing sent
   to 0x44 can modify flash even in principle.

THE PACKET is the vendor's own presence criterion, lifted from
FN_bDrvFindPicController: clear the fault latch, then send

    04 03 <board> 00 00

and accept a type-7 response whose status byte[3] is 0 or 8. Two attempts, as
the vendor does. Note the command byte is 0x00 -- bits 3 and 2 are clear, so it
is not in the 0x0C-0x0F range the bootloader dispatches as a row erase, and it
is not addressed to a bootloader in any case.

A bare type-3 packet (`03 01 44`) is NOT a presence test: it returns status 9,
bus error, from a known-good chip. The control target below exists so that
mistake cannot be made silently again.
"""
from __future__ import annotations

import sys

try:
    import usb.core
    import usb.util
except ImportError:
    sys.exit("pyusb is required:  pip install pyusb")

VID, PID = 0x0F05, 0xF135
EP_CMD_OUT, EP_CMD_IN = 0x01, 0x81
RESPONSE_TYPE = 7

# Application addresses only. The bootloader addresses 0x42 and 0x46 are
# deliberately absent and are rejected below rather than merely omitted.
# docs/03-protocol.md:116 and docs/02-firmware.md:168 --
#   0x40 AD_PICL_PLUS  light controller  (U11 application)
#   0x42                                  U11 bootloader
#   0x44 AD_PICM_PLUS  motor controller  (U34 application)
#   0x46                                  U34 bootloader
TARGETS = {0x44: "PICM / motor board (U34 -- repaired today)",
           0x40: "PICL / light board (U11 -- known good control)"}
FORBIDDEN = {0x42: "PICL bootloader", 0x46: "PICM bootloader"}


HOST = 0x10


def build(address: int) -> bytes:
    if address in FORBIDDEN:
        raise SystemExit(f"REFUSING: {address:#04x} is the {FORBIDDEN[address]}"
                         " -- it can erase flash. This tool never addresses it.")
    if address not in TARGETS:
        raise SystemExit(f"REFUSING: {address:#04x} is not an allowed target.")
    return bytes([0x04, 0x03, address, 0x00, 0x00])


def open_scanner():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        return None
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


def send(dev, pkt, timeout=2000, show=True):
    if show:
        print(f"  -> {pkt.hex(' ')}")
    try:
        dev.write(EP_CMD_OUT, pkt, timeout)
        resp = bytes(dev.read(EP_CMD_IN, 64, timeout))
    except usb.core.USBError:
        if show:
            print("     no response")
        return None
    if show:
        print(f"     <- {len(resp)}B: {resp.hex(' ')}")
    return resp


def clear_fault(dev):
    """FN_bFirmware fault-latch clear, as flash_picm.py does before probing."""
    for _ in range(8):
        r = send(dev, bytes([0x01, 0x03, HOST, 0x02, 0x03]), show=False)
        if isinstance(r, bytes) and len(r) > 3 and not (r[3] & 0x20):
            return True
        send(dev, bytes([0x04, 0x03, HOST, 0x00, 0x85]), show=False)
    return False


def probe(dev, address: int, timeout: int = 2000):
    pkt = build(address)
    print(f"\n{TARGETS[address]}")
    for attempt in (1, 2):
        clear_fault(dev)
        resp = send(dev, pkt, timeout)
        if resp and resp[0] == RESPONSE_TYPE:
            status = resp[3] if len(resp) > 3 else None
            if status in (0, 8):
                print(f"     type 7, status={status} -> *** ANSWERING ***")
                return True
            print(f"     type 7, status={status} -> error (attempt {attempt})")
        elif resp:
            print(f"     unexpected leading byte {resp[0]:#04x}")
    return False


def main() -> int:
    dev = open_scanner()
    if dev is None:
        sys.exit(f"scanner {VID:#06x}:{PID:#06x} not found -- is the firmware "
                 "loaded? run tools/pakon_load.py first")
    print(f"scanner open: {VID:#06x}:{PID:#06x}")
    results = {a: probe(dev, a) for a in (0x40, 0x44)}
    print("\n" + "=" * 52)
    for a, ok in results.items():
        print(f"  {a:#04x}  {TARGETS[a]:<44} {'YES' if ok else 'no'}")
    if results.get(0x44):
        print("\n  PICM ANSWERS. The repaired chip is on the bus.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
