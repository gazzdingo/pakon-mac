#!/usr/bin/env python3
"""Send command packets to a loaded Pakon scanner and read the responses.

Packet format, recovered from TLB.dll (the F-135 client library). The library
even carries the format string "Type %x, PktLen %x, Address %x":

    offset 0   Type      packet type
    offset 1   PktLen    number of bytes that follow
    offset 2   Address   destination board
    offset 3+  payload

Total bytes on the wire = PktLen + 2, taken straight from the call site
(`add edx, 2` feeding nInBufferSize). The response buffer is 64 bytes
(nOutBufferSize = 0x40).

IMPORTANT: the host computes NO checksum. Framing/checksums are added by the
FX2 firmware and the PIC link layer. Earlier guesses that the host had to build
one were wrong.

Transport is trivially simple -- IOCTL_PAKON_SEND_AND_RECEIVE_PACKET (0x222090)
is just a bulk write to EP 0x01 OUT followed by a bulk read from EP 0x81 IN:

    Ezusb_Read_Write_Direct(fdo, Irp, FALSE);   // write
    Ezusb_Read_Write_Direct(fdo, Irp, TRUE);    // read

RESPONSES have Type 7. TLB.dll checks resp[0] == 7, then treats resp[3] == 0
as success.

WARNING: sending an invalid packet type wedges the firmware. It stops draining
EP 0x01 OUT and stays wedged across USB resets, because the firmware lives in
RAM and a USB reset does not restart it. Recovery requires a scanner power
cycle. Only send types this tool knows about.
"""
from __future__ import annotations

import argparse
import sys
import time

import usb.core
import usb.util

EP_CMD_OUT, EP_CMD_IN, EP_DATA_IN = 0x01, 0x81, 0x86
RESPONSE_TYPE = 7

# Addresses. 0x10/0x20/0x40/0x44 are from Kaufman's write-up; 0x24 is inferred
# from the PL/PM/NL/NM firmware families documented in ReadmeF135.txt.
ADDRESSES = {
    "host": 0x10,
    "picl": 0x20,
    "picm": 0x24,
    "picl_plus": 0x40,     # F-135 Plus light controller
    "picm_plus": 0x44,     # F-135 Plus motor controller
}

# Packet templates observed in TLB.dll builders. Type 0 is NOT among them --
# do not send it.
#   fcn.10008d70  Type 3, PktLen 1: [addr]
#   fcn.100092f0  Type 3, PktLen 1: [addr]
#   fcn.10008ba0  Type 4, PktLen 3: [addr, 0, 0]
#   fcn.10009410  Type 1, PktLen 3: [addr, b, c]
#   fcn.1000a0c0  Type 1, PktLen 3: [addr, 2, c]
#   fcn.10008f80  Type 2, PktLen 6: [...]
KNOWN_TEMPLATES = {
    "ping": (3, [0x00]),           # Type 3, len 1 -- payload is just the address
    "query": (4, [0x00, 0, 0]),    # Type 4, len 3
}


def build(ptype: int, address: int, payload: bytes = b"") -> bytes:
    body = bytes([address]) + payload
    return bytes([ptype, len(body)]) + body


def exchange(dev, pkt: bytes, timeout: int = 2000, verbose: bool = True):
    if verbose:
        print(f"  -> {pkt.hex(' ')}  (Type {pkt[0]}, PktLen {pkt[1]}, "
              f"Address {pkt[2]:#04x})")
    try:
        dev.write(EP_CMD_OUT, pkt, timeout)
    except usb.core.USBError:
        if verbose:
            print("     WRITE TIMED OUT -- firmware is not draining EP1 OUT.")
            print("     It is probably wedged; power-cycle the scanner.")
        return None
    try:
        resp = bytes(dev.read(EP_CMD_IN, 64, timeout))
    except usb.core.USBError:
        if verbose:
            print("     no response on EP 0x81")
        return None
    if verbose:
        print(f"     <- {len(resp)}B: {resp.hex(' ')}")
        if resp and resp[0] == RESPONSE_TYPE:
            ok = len(resp) > 3 and resp[3] == 0
            print(f"     Type 7 response, status byte[3]="
                  f"{resp[3] if len(resp) > 3 else '?'} "
                  f"-> {'SUCCESS' if ok else 'error'}")
        elif resp:
            print(f"     unexpected leading byte {resp[0]:#04x} "
                  f"(expected {RESPONSE_TYPE})")
    return resp


def open_scanner():
    dev = usb.core.find(idVendor=0x0F05, idProduct=0xF135)
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--type", type=int, default=3, help="packet type (1-4)")
    ap.add_argument("--address", default="host",
                    help="board name or numeric address")
    ap.add_argument("--payload", default="",
                    help="extra payload bytes as hex, e.g. '0000'")
    ap.add_argument("--sweep-addresses", action="store_true",
                    help="try the ping template against every known address")
    ap.add_argument("--timeout", type=int, default=2000)
    args = ap.parse_args()

    if args.type not in (1, 2, 3, 4):
        print("refusing: only types 1-4 are known to be valid. Sending an "
              "unknown type wedges the firmware.", file=sys.stderr)
        return 2

    dev = open_scanner()
    if dev is None:
        print("no loaded Pakon scanner found (expected 0f05:f135). "
              "Run pakon_load.py first.", file=sys.stderr)
        return 1

    try:
        if args.sweep_addresses:
            print("sweeping ping (Type 3, PktLen 1) across known addresses:")
            for name, addr in ADDRESSES.items():
                print(f"  --- {name} ({addr:#04x}) ---")
                if exchange(dev, build(3, addr), args.timeout) is None:
                    print("  aborting sweep: endpoint is no longer accepting")
                    break
                time.sleep(0.2)
        else:
            addr = (ADDRESSES[args.address] if args.address in ADDRESSES
                    else int(args.address, 0))
            payload = bytes.fromhex(args.payload) if args.payload else b""
            exchange(dev, build(args.type, addr, payload), args.timeout)
    finally:
        usb.util.release_interface(dev, 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
