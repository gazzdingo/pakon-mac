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
(ctx, board, command, dataPtr, dataLen). The command set is read/write/
erase/exit:

    command 1, dataLen 3    read 16 bytes at a 24-bit LE address
    command 2, dataLen 19   write: <24-bit LE address> + 16 bytes
    command 4, dataLen 3    ERASE the 64-byte row at a 24-bit LE address
    command 8, dataLen 0    finalise / reset into the application

FN_bLoadPicLarge (fcn.1001bb10, enum 238) makes TWO passes over the image:

    pass 1  0x1001bb62-0x1001bc4b   command 4 per 64-byte row, Sleep(1)
                                     (address += 0x40, index += 4)
    pass 2  0x1001bc4d-0x1001bd90   command 2 per 16 bytes, 10 ms apart
                                     (never issues command 4)

Command 4 cannot be "set address": command 2 carries its own address, and
pass 2 works without it. A 3-byte address at exactly 64-byte granularity,
emitted only for rows about to be written and only before any write, is an
erase -- PIC18 erases in 64-byte rows.

FN_bVerifyPicLarge (fcn.1001bdf0) then reads every block back with command 1
and applies, at 0x1001bea2:

    (actual & expected) == expected  ? rewrite and retry : abort

A bit needing 1->0 can be fixed by rewriting; a bit needing 0->1 needs an
erase that has already been spent, so it aborts. That rule only makes sense
on freshly erased flash, which is further proof the erase pass is mandatory.

Only after every block verifies does FN_bUpdate send command 8. Note that the
0xbb8 seen near these calls is a progress value passed to a client callback
(fcn.10032580), not a delay.

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
* Erases every affected 64-byte row before writing, as the vendor does.
  Writing unerased PIC flash is AND-only and silently corrupts it.
* Reads every block back and compares. Command 8 is sent only if all of them
  verify, because command 8 resets the PIC into whatever is in flash.
* Aborts on the FIRST rejected or unanswered packet. Status 0 is the only
  success; 1 is a NAK, 2 a format error, 3 a checksum error.

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

CMD_READ, CMD_WRITE, CMD_ERASE, CMD_FINALISE = 1, 2, 4, 8
CHUNK = 16                      # bytes per command 2 packet
ROW = 64                        # PIC18 erase row, and command 4's granularity
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
    return {0: "ok", 1: "NAK", 2: "format error",
            3: "checksum error"}.get(r[3], f"status {r[3]}")


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


def erase_rows(chunks, row=ROW):
    """The 64-byte-aligned rows touched by the write set.

    Mirrors pass 1 of FN_bLoadPicLarge, which walks the image in 64-byte
    steps and erases a row only when one of its four 16-byte blocks carries
    data.
    """
    return sorted({base - (base % row) for base, _ in chunks})


def read_block(d, board, addr):
    """Command 1: read 16 bytes at a 24-bit LE address.

    The response payload offset is not proven from the binary, so the caller
    must confirm it against a known block before any comparison is trusted.
    """
    r = put_program_data(d, board, CMD_READ, struct.pack("<I", addr)[:3])
    if not r or len(r) < 4 or r[0] != 0x01:
        return None, r
    return bytes(r[4:4 + CHUNK]), r


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
        rows = erase_rows(todo)

        # ---- pass 1: erase, exactly as FN_bLoadPicLarge does first --------
        print(f"\npass 1 -- erasing {len(rows)} row(s) of {ROW} bytes")
        for i, addr in enumerate(rows):
            r = put_program_data(d, board, CMD_ERASE,
                                 struct.pack("<I", addr)[:3])
            if not accepted(r):
                sys.exit(f"  {addr:#08x}: {status_text(r)}\n"
                         f"  ABORT -- erase failed. Nothing has been written, "
                         f"so the board is no worse than before.")
            if i % 32 == 0:
                print(f"  {addr:#08x}  erased  ({i + 1}/{len(rows)})")
            time.sleep(0.001)
        print(f"  all {len(rows)} row(s) erased")

        # ---- pass 2: write -------------------------------------------------
        print(f"\npass 2 -- writing {len(todo)} chunk(s) of {CHUNK} bytes")
        for i, (base, blk) in enumerate(todo):
            r = put_program_data(d, board, CMD_WRITE,
                                 struct.pack("<I", base)[:3] + blk)
            if not accepted(r):
                sys.exit(f"  {base:#08x}: {status_text(r)}\n"
                         f"  ABORT -- write failed at chunk {i + 1}. Command 8 "
                         f"has NOT been sent, so the PIC stays in its "
                         f"bootloader and can be reflashed.")
            if i % 64 == 0:
                print(f"  {base:#08x}  written  ({i + 1}/{len(todo)})")
            time.sleep(0.010)
        print(f"  all {len(todo)} chunk(s) written")

        # ---- pass 3: verify, as FN_bVerifyPicLarge does --------------------
        print(f"\npass 3 -- verifying {len(todo)} chunk(s)")
        probe, raw = read_block(d, board, todo[0][0])
        if probe is None:
            sys.exit(f"  read-back returned {status_text(raw)}\n"
                     f"  ABORT -- cannot verify, so command 8 will not be sent. "
                     f"The PIC stays in its bootloader.")
        print(f"  read-back of {todo[0][0]:#08x}: {raw[:8].hex(' ')} ...")
        if probe != todo[0][1]:
            print(f"    expected {todo[0][1].hex(' ')}")
            print(f"    got      {probe.hex(' ')}")
            sys.exit("  ABORT -- first block does not match. Either the write "
                     "failed or the read payload offset is wrong; either way "
                     "command 8 will not be sent.")

        bad = 0
        for i, (base, blk) in enumerate(todo):
            got, raw = read_block(d, board, base)
            if got is None or got != blk:
                bad += 1
                print(f"  {base:#08x} MISMATCH")
                print(f"    expected {blk.hex(' ')}")
                print(f"    got      {got.hex(' ') if got else status_text(raw)}")
                if bad > 3:
                    sys.exit("  ABORT -- too many mismatches; command 8 not sent.")
            elif i % 64 == 0:
                print(f"  {base:#08x}  verified  ({i + 1}/{len(todo)})")
        if bad:
            sys.exit(f"\n  {bad} block(s) failed to verify. Command 8 NOT sent; "
                     f"the PIC remains in its bootloader and can be reflashed.")
        print(f"  all {len(todo)} chunk(s) verified")

        # ---- finalise ------------------------------------------------------
        if args.limit:
            print("\n  --limit was used, so this is a partial image. NOT "
                  "sending command 8.")
            return 0
        print("\nfinalise -- command 8 resets the PIC into the application")
        r = put_program_data(d, board, CMD_FINALISE)
        print(f"  command 8: {status_text(r)}"
              + (f"   response {r[:6].hex(' ')}" if r else ""))
        print("\n  Power-cycle the scanner, then check whether 0x44 answers.")
    finally:
        usb.util.release_interface(d, 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
