#!/usr/bin/env python3
"""Flash the PICM (motor/main board) firmware through its bootloader.

WHY THIS EXISTS
---------------
This unit's PICM has lost its application firmware and sits in its bootloader.
Evidence, using the vendor's own presence criterion from
FN_bDrvFindPicController (resp[0]==7 and resp[3]==0):

    0x44  PICM application   absent    07 02 44 01
    0x46  PICM bootloader    PRESENT   07 02 46 00
    0x48/0x4a/0x60/0x62/0x50/0x52 (controls, must be empty)   all absent

Controls NAK while 0x46 ACKs, so 0x46 is a real device rather than a floating
bus. FN_bUpdate in TLB.dll is written to recover exactly this state.

PROTOCOL, recovered from TLB.dll
--------------------------------
The flash path reuses the ordinary packet transport
(FN_bFirmwareWritePacketNL, fcn.10008e30):

    data packet     02 <dataLen+3> <board> <dataLen> <cmd> <data...>
    command packet  04 3           <board> 0         <cmd>

FN_bFirmwarePutProgramData (fcn.10008ee0, enum 162) takes
(ctx, board, command, dataPtr, dataLen). Commands used by FN_bLoadPicLarge
(fcn.1001bb10, enum 238):

    command 4, dataLen 3    set address, 24-bit little-endian
    command 2, dataLen 19   <24-bit LE address> + <16 bytes of program data>

FN_bUpdate's control flow gives the whole sequence:

    FN_bLoadPicLarge        command 4, then a loop of command 2, 10 ms apart
    wait 3000 ms
    fcn.1001bdf0            verify
    command 8               finalise (its response byte is read and logged)

Command 8 runs *after* the write and verify, so it is not an erase, and no
separate erase command exists anywhere in the sequence.

SAFETY
------
* Writes only the application region. nm0506.HEX starts at 0x000400, so the
  bootloader occupying 0x0000-0x03FF is never touched. Addresses below
  BOOTLOADER_END are refused.
* Never writes the PIC configuration words at 0x300000 and above. Writing bad
  config can brick a PIC outright, and the image's config records are skipped.
* --dry-run is the default. Nothing reaches the scanner unless --write is
  given explicitly.
* Verifies the PICM is actually in its bootloader, and that the control
  addresses are empty, before writing anything.
* Every packet's status byte is checked. Status 0 is the only success;
  1 is a NAK and 2 is an unsupported packet type.

The PCB revision decides the image: nm0306 = PCB #125430A, nm0406 = #125430B,
nm0506 = #125430C. ReadmeF135.txt warns against using these on PCB #125039A.
"""
from __future__ import annotations

import argparse
import os
import struct
import sys
import time

import usb.core
import usb.util

EP_OUT, EP_IN = 0x01, 0x81
HOST = 0x10
PICM_APP, PICM_BOOT = 0x44, 0x46
CONTROLS = (0x48, 0x4A, 0x60, 0x62, 0x50, 0x52)

CMD_WRITE, CMD_SET_ADDR, CMD_FINALISE = 2, 4, 8
CHUNK = 16                      # bytes per command 2 packet
BOOTLOADER_END = 0x000400       # application starts here; never write below
CONFIG_BASE = 0x300000          # PIC config words; never write at or above

DEFAULT_HEX = ("/Users/guy/Downloads/Pakon Update 2/fx35install/program files/"
               "Pakon/F-X35 COM SERVER/Config/Firmware/nm0506.HEX")


# ---------------------------------------------------------------- transport

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


def send(d, pkt, timeout=2000):
    try:
        d.write(EP_OUT, pkt, timeout)
    except usb.core.USBError:
        return None
    try:
        return bytes(d.read(EP_IN, 64, timeout))
    except usb.core.USBError:
        return None


def accepted(r):
    """Only a Type 7 response with status 0 counts as success."""
    return bool(r) and len(r) > 3 and r[0] == 0x07 and r[3] == 0x00


def status_text(r):
    if not r:
        return "no response"
    if len(r) < 4:
        return f"short {r.hex(' ')}"
    if r[0] != 0x07:
        return f"type {r[0]} {r[:4].hex(' ')}"
    return {0: "ok", 1: "NAK", 2: "unsupported"}.get(r[3], f"status {r[3]}")


def put_program_data(d, board, command, data=b""):
    """FN_bFirmwarePutProgramData.

    dataLen 0 becomes a Type 4 command packet, anything else a Type 2 data
    packet, exactly as FN_bFirmwareWritePacketNL decides it.
    """
    n = len(data)
    if n == 0:
        pkt = bytes([0x04, 0x03, board, 0x00, command])
    else:
        pkt = bytes([0x02, n + 3, board, n, command]) + bytes(data)
    return send(d, pkt)


def clear_fault(d):
    for _ in range(8):
        r = send(d, bytes([0x01, 0x03, HOST, 0x02, 0x03]))
        if isinstance(r, bytes) and len(r) > 3 and not (r[3] & 0x20):
            return True
        send(d, bytes([0x04, 0x03, HOST, 0x00, 0x85]))
    return False


def present(d, board):
    """FN_bDrvFindPicController's criterion, two attempts as the vendor does."""
    for _ in range(2):
        clear_fault(d)
        r = send(d, bytes([0x04, 0x03, board, 0x00, 0x00]))
        if accepted(r):
            return True
    return False


# ---------------------------------------------------------------- hex image

def load_ihex(path):
    """Parse Intel HEX into {address: byte}. Handles record types 0, 1, 2, 4."""
    mem, ext = {}, 0
    with open(path) as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line or not line.startswith(":"):
                continue
            try:
                b = bytes.fromhex(line[1:])
            except ValueError:
                sys.exit(f"{path}:{lineno}: not valid hex")
            if len(b) < 5 or (sum(b) & 0xFF) != 0:
                sys.exit(f"{path}:{lineno}: bad record or checksum")
            n, addr, rtype = b[0], (b[1] << 8) | b[2], b[3]
            if rtype == 0:
                for i, v in enumerate(b[4:4 + n]):
                    mem[ext + addr + i] = v
            elif rtype == 1:
                break
            elif rtype == 2:
                ext = ((b[4] << 8) | b[5]) << 4
            elif rtype == 4:
                ext = ((b[4] << 8) | b[5]) << 16
    return mem


def writable_chunks(mem, chunk=CHUNK):
    """Aligned chunks of the application region only.

    Skips anything below BOOTLOADER_END or at/above CONFIG_BASE. Gaps are
    padded with 0xFF, which is erased flash.
    """
    addrs = [a for a in mem
             if BOOTLOADER_END <= a < CONFIG_BASE]
    if not addrs:
        return []
    lo, hi = min(addrs), max(addrs) + 1
    lo -= lo % chunk
    out = []
    for base in range(lo, hi, chunk):
        block = bytes(mem.get(base + i, 0xFF) for i in range(chunk))
        if any(mem.get(base + i) is not None for i in range(chunk)):
            out.append((base, block))
    return out


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hex", default=DEFAULT_HEX, help="PICM firmware image")
    ap.add_argument("--board", default=hex(PICM_BOOT),
                    help=f"bootloader address (default {PICM_BOOT:#04x})")
    ap.add_argument("--write", action="store_true",
                    help="actually write; without this it is a dry run")
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after N chunks (for a cautious first run)")
    args = ap.parse_args()
    board = int(args.board, 0)

    if not os.path.exists(args.hex):
        sys.exit(f"firmware not found: {args.hex}")
    mem = load_ihex(args.hex)
    chunks = writable_chunks(mem)
    app = [a for a in mem if BOOTLOADER_END <= a < CONFIG_BASE]
    boot = [a for a in mem if a < BOOTLOADER_END]
    cfg = [a for a in mem if a >= CONFIG_BASE]

    print(f"image        : {os.path.basename(args.hex)}")
    print(f"  total bytes in file      : {len(mem)}")
    print(f"  application (>= {BOOTLOADER_END:#06x})   : {len(app)}  -> {len(chunks)} chunks of {CHUNK}")
    print(f"  bootloader  (<  {BOOTLOADER_END:#06x})   : {len(boot)}  SKIPPED")
    print(f"  config      (>= {CONFIG_BASE:#08x}) : {len(cfg)}  SKIPPED")
    if chunks:
        print(f"  address range to write   : {chunks[0][0]:#08x} .. {chunks[-1][0] + CHUNK:#08x}")

    if not chunks:
        sys.exit("nothing to write")

    d = open_dev()
    try:
        print("\nchecking the PICM really is in its bootloader:")
        app_present = present(d, PICM_APP)
        boot_present = present(d, board)
        print(f"  {PICM_APP:#04x} application : {'present' if app_present else 'absent'}")
        print(f"  {board:#04x} bootloader  : {'PRESENT' if boot_present else 'absent'}")
        bad = [c for c in CONTROLS if present(d, c)]
        print(f"  controls {', '.join(hex(c) for c in CONTROLS)}: "
              f"{'all absent (good)' if not bad else 'ACKING: ' + ', '.join(hex(c) for c in bad)}")

        if not boot_present:
            sys.exit("\nrefusing: the bootloader address does not answer")
        if bad:
            sys.exit("\nrefusing: control addresses ACK, so ACKs here are not "
                     "trustworthy (floating bus)")
        if app_present:
            print("\nnote: the application address also answers; the PICM may "
                  "already be running its firmware.")

        if not args.write:
            print(f"\nDRY RUN -- nothing sent. {len(chunks)} chunks would be written.")
            print("  first 3:")
            for base, blk in chunks[:3]:
                print(f"    {base:#08x}  {blk.hex(' ')}")
            print("\n  re-run with --write to flash.")
            return 0

        todo = chunks[:args.limit] if args.limit else chunks
        print(f"\nwriting {len(todo)} chunk(s) to {board:#04x} ...")

        r = put_program_data(d, board, CMD_SET_ADDR,
                             struct.pack("<I", todo[0][0])[:3])
        print(f"  set address {todo[0][0]:#08x}: {status_text(r)}")
        if not accepted(r):
            sys.exit("  refusing to continue: set-address was not accepted")

        failed = 0
        for i, (base, blk) in enumerate(todo):
            payload = struct.pack("<I", base)[:3] + blk
            r = put_program_data(d, board, CMD_WRITE, payload)
            if not accepted(r):
                failed += 1
                print(f"  {base:#08x}: {status_text(r)}")
                if failed > 4:
                    sys.exit("  too many failures -- stopping")
            elif i % 32 == 0:
                print(f"  {base:#08x}  ok  ({i + 1}/{len(todo)})")
            time.sleep(0.010)

        print(f"\n  {len(todo) - failed}/{len(todo)} chunks accepted")
        print("  waiting 3 s as the vendor does ...")
        time.sleep(3.0)
        r = put_program_data(d, board, CMD_FINALISE)
        print(f"  finalise (command 8): {status_text(r)}"
              + (f"   response {r[:6].hex(' ')}" if r else ""))
        print("\n  power-cycle the scanner, then check whether 0x44 answers.")
    finally:
        usb.util.release_interface(d, 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
