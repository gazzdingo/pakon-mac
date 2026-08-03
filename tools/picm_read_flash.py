#!/usr/bin/env python3
"""Read the PICM's application flash back through its bootloader. READ ONLY.

This answers two questions without writing anything:

1. Is the application flash actually blank? If every word reads 0xFF, the
   firmware really is gone and flashing is the route. If it reads back real
   PIC code, something else is wrong and flashing would be the wrong move.
2. Where does the payload sit in the 64-byte response? The verify pass in
   tools/flash_picm.py assumes the 16 data bytes start at response[4]. That
   assumption is unproven from the binary, and proving it here removes the
   last unknown before any flash write.

Command 1 is the bootloader's read, recovered from fcn.10008f80 (behind
FN_bFirmwareGetProgramWords8) and confirmed by the command table:

    1  read 16 bytes at a 24-bit LE address
    2  write 16 bytes
    4  erase a 64-byte row
    8  finalise / run the application

On the wire, using the same packet family as every other register operation:

    02 06 <board> 03 01 <addr lo> <addr mid> <addr hi>

Nothing here writes, erases, or changes any mode. The worst outcome is that
the bootloader does not answer the read.

    ./picm_read_flash.py                  # read a few blocks, show raw responses
    ./picm_read_flash.py --addr 0x400     # a specific address
    ./picm_read_flash.py --scan           # sample across the whole app region
"""
from __future__ import annotations

import argparse
import struct
import sys

import usb.core
import usb.util

EP_OUT, EP_IN = 0x01, 0x81
HOST = 0x10
PICM_APP, PICM_BOOT = 0x44, 0x46
CMD_READ = 1
APP_START, APP_END = 0x000400, 0x002D80

VENDOR_HEX = ("/Users/guy/Downloads/Pakon Update 2/fx35install/program files/"
              "Pakon/F-X35 COM SERVER/Config/Firmware/nm0506.HEX")


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


def clear_fault(d):
    for _ in range(8):
        r = send(d, bytes([0x01, 0x03, HOST, 0x02, 0x03]))
        if isinstance(r, bytes) and len(r) > 3 and not (r[3] & 0x20):
            return
        send(d, bytes([0x04, 0x03, HOST, 0x00, 0x85]))


def read_flash(d, board, addr, length=16):
    """Command 1 is TWO packets, not one.

    First set the address, then fetch. The fetch is a Type 1 read whose
    payload lands at response offset 4. The address auto-increments, so
    contiguous reads can skip the first packet. Read length is a free
    parameter and the response buffer is 64 bytes, so up to ~60 is safe;
    the vendor uses 16.

        02 06 <board> 03 01 <addr lo> <addr mid> <addr hi>     set address
        01 03 <board> <length> 07                              fetch
    """
    clear_fault(d)
    setup = bytes([0x02, 0x06, board, 0x03, CMD_READ]) + struct.pack("<I", addr)[:3]
    r1 = send(d, setup)
    if not (r1 and len(r1) > 3 and r1[0] == 0x07 and r1[3] == 0x00):
        return setup, r1
    fetch = bytes([0x01, 0x03, board, length, 0x07])
    return fetch, send(d, fetch)


def load_expected():
    """The vendor image, so a non-blank read can be compared against truth."""
    mem, ext = {}, 0
    try:
        fh = open(VENDOR_HEX)
    except OSError:
        return {}
    with fh:
        for line in fh:
            line = line.strip()
            if not line.startswith(":"):
                continue
            b = bytes.fromhex(line[1:])
            n, a, t = b[0], (b[1] << 8) | b[2], b[3]
            if t == 0:
                for i, v in enumerate(b[4:4 + n]):
                    mem[ext + a + i] = v
            elif t == 4:
                ext = ((b[4] << 8) | b[5]) << 16
            elif t == 1:
                break
    return mem


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--board", default=hex(PICM_BOOT))
    ap.add_argument("--addr", default=None, help="single address to read")
    ap.add_argument("--scan", action="store_true",
                    help="sample across the whole application region")
    args = ap.parse_args()
    board = int(args.board, 0)

    expected = load_expected()
    d = open_dev()
    try:
        clear_fault(d)
        r = send(d, bytes([0x04, 0x03, board, 0x00, 0x00]))
        ok = bool(r) and len(r) > 3 and r[0] == 0x07 and r[3] == 0x00
        print(f"bootloader at {board:#04x}: {'present' if ok else 'NOT PRESENT'}"
              f"   {r[:4].hex(' ') if r else ''}")
        if not ok:
            sys.exit("refusing: the bootloader does not answer")

        if args.addr:
            addrs = [int(args.addr, 0)]
        elif args.scan:
            addrs = list(range(APP_START, APP_END, 0x400))
        else:
            addrs = [0x000400, 0x000410, 0x000800, 0x001000, 0x002000]

        print(f"\nreading {len(addrs)} block(s) with: "
              f"02 06 {board:02x} 03 01 <addr LE24>\n")
        blank = nonblank = noresp = 0
        for a in addrs:
            pkt, r = read_flash(d, board, a)
            if not r:
                print(f"  {a:#08x}  no response   (sent {pkt.hex(' ')})")
                noresp += 1
                continue
            head = r[:24].hex(' ')
            exp = bytes(expected.get(a + i, 0xFF) for i in range(16)) if expected else None
            print(f"  {a:#08x}  resp: {head}")
            if exp:
                print(f"             vendor image expects: {exp.hex(' ')}")
                for off in range(2, 9):
                    if len(r) >= off + 16 and bytes(r[off:off + 16]) == exp:
                        print(f"             *** payload matches vendor image "
                              f"at response offset {off} ***")
            body = r[4:20] if len(r) >= 20 else b""
            if body and all(v == 0xFF for v in body):
                blank += 1
            elif body:
                nonblank += 1

        print(f"\n  blank-looking (0xFF at resp[4:20]): {blank}")
        print(f"  non-blank                          : {nonblank}")
        print(f"  no response                        : {noresp}")
        print("\n  Nothing was written. This was a read-only probe.")
        if noresp == len(addrs):
            print("\n  The bootloader did not answer command 1 at all, so either")
            print("  the read command differs or reads are not supported. The")
            print("  flasher's verify pass would abort cleanly in that case.")
        elif blank and not nonblank:
            print("\n  The application region reads blank, consistent with the")
            print("  firmware being erased. Flashing is the route.")
        elif nonblank:
            print("\n  Some blocks are not blank. Check the offset line above:")
            print("  if a payload matched the vendor image, that offset is the")
            print("  correct one for the flasher's verify pass.")
    finally:
        usb.util.release_interface(d, 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
