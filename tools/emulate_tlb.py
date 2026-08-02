#!/usr/bin/env python3
"""Emulate TLB.dll to recover the packet sequences the vendor driver sends.

Rather than reverse-engineering each routine by hand, load the vendor's own
x86 code into a CPU emulator, fabricate enough state for it to run, and trap
the packet-transmit function to log exactly what it wants to put on the wire.

That yields the real command sequences -- effectively a USB capture generated
from the vendor's logic -- without Windows, a PC, or an emulator for 32-bit
x86 on Apple Silicon.

What this can and cannot give you:

  CAN  the packet SEQUENCE and structure: which registers are written, in what
       order, with what widths. Read sequences are fully usable, because a read
       does not depend on values the host doesn't have.
  CANNOT invent per-unit calibration VALUES. Those live in the scanner or in a
       populated config structure; emulating with a zeroed config yields zeros.
       Use the recovered READ sequence against real hardware to obtain them.

Usage:
    ./emulate_tlb.py --list
    ./emulate_tlb.py --call 0x1002d190      # FN_bDrvInitLampTemperatures
    ./emulate_tlb.py --call 0x1002c5f0 --args 1 0 0 0 0 0 0
"""
from __future__ import annotations

import argparse
import struct
import sys

try:
    import pefile
    from unicorn import (Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE,
                         UC_HOOK_MEM_UNMAPPED, UcError)
    from unicorn.x86_const import (UC_X86_REG_ESP, UC_X86_REG_EIP, UC_X86_REG_ECX,
                                   UC_X86_REG_EAX, UC_X86_REG_EDX, UC_X86_REG_EBP)
except ImportError:
    sys.exit("need: python3 -m pip install unicorn pefile")

DLL = ("/Users/guy/Downloads/Pakon Update 2/fx35install/program files/Pakon/"
       "F-X35 COM SERVER/TLB.dll")

IMAGE_BASE = 0x10000000
STACK_BASE = 0x70000000
STACK_SIZE = 0x100000
HEAP_BASE  = 0x60000000
HEAP_SIZE  = 0x200000
# Driver object ("this") and the global config structure the code dereferences.
THIS_OBJ   = 0x61000000
GLOBAL_CFG = 0x62000000
OBJ_SIZE   = 0x2000

# Known packet emitters, all of which funnel into fcn.10008530.
PACKET_SEND   = 0x10008530     # the DeviceIoControl wrapper
GLOBAL_CFG_PTR = 0x10075554    # holds the pointer to the global config

# Fields of the driver object that the code reads, discovered by disassembly.
OBJ_FIELDS = {
    0x130: 0x44,   # motor / main board address
    0x131: 0x40,   # light board address
    0x2f9: 0x40,   # board address used by lamp routines
}


class Emu:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.packets = []
        self.pe = pefile.PE(DLL)
        self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self._map_image()
        self._map_scratch()
        self._hooks()

    def _map_image(self):
        size = (self.pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF
        self.uc.mem_map(IMAGE_BASE, size)
        self.uc.mem_write(IMAGE_BASE, self.pe.get_memory_mapped_image(
            ImageBase=IMAGE_BASE))
        self.image_size = size

    def _map_scratch(self):
        for base, sz in ((STACK_BASE, STACK_SIZE), (HEAP_BASE, HEAP_SIZE),
                         (THIS_OBJ, OBJ_SIZE * 8), (GLOBAL_CFG, OBJ_SIZE * 8)):
            self.uc.mem_map(base, (sz + 0xFFF) & ~0xFFF)
            self.uc.mem_write(base, b"\x00" * sz)
        # point the global config pointer at our fabricated structure
        self.uc.mem_write(GLOBAL_CFG_PTR, struct.pack("<I", GLOBAL_CFG))
        for off, val in OBJ_FIELDS.items():
            self.uc.mem_write(THIS_OBJ + off, bytes([val]))

    def _hooks(self):
        self.uc.hook_add(UC_HOOK_CODE, self._on_code)
        self.uc.hook_add(UC_HOOK_MEM_UNMAPPED, self._on_unmapped)

    def _on_unmapped(self, uc, access, address, size, value, user):
        """Map anything the code touches, so imports and stray pointers don't
        abort the run. Emulation fidelity matters less than reaching the
        packet-send calls."""
        page = address & ~0xFFF
        try:
            uc.mem_map(page, 0x1000)
            uc.mem_write(page, b"\x00" * 0x1000)
        except UcError:
            pass
        return True

    def _on_code(self, uc, address, size, user):
        if address == PACKET_SEND:
            self._capture_packet(uc)
            # return 1 (success) to the caller without executing the real body
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
            # the wrapper is stdcall with 0x28 bytes of args
            uc.reg_write(UC_X86_REG_ESP, esp + 4 + 0x28)
            uc.reg_write(UC_X86_REG_EAX, 1)
            uc.reg_write(UC_X86_REG_EIP, ret)

    def _capture_packet(self, uc):
        """At fcn.10008530 the packet buffer is the 2nd stdcall argument."""
        esp = uc.reg_read(UC_X86_REG_ESP)
        try:
            args = struct.unpack("<10I", uc.mem_read(esp + 4, 40))
        except UcError:
            return
        for cand in args:
            if not cand:
                continue
            try:
                hdr = uc.mem_read(cand, 2)
            except UcError:
                continue
            ptype, plen = hdr[0], hdr[1]
            if ptype in (1, 2, 3, 4) and 0 < plen <= 40:
                try:
                    pkt = bytes(uc.mem_read(cand, plen + 2))
                except UcError:
                    continue
                self.packets.append(pkt)
                print(f"    PACKET  {pkt.hex(' ')}"
                      f"   (Type {pkt[0]}, PktLen {pkt[1]}, Addr {pkt[2]:#04x})")
                return

    def call(self, addr, args=(), this=THIS_OBJ):
        esp = STACK_BASE + STACK_SIZE - 0x1000
        # return address sentinel we can stop on
        stop = 0x7FFFF000
        try:
            self.uc.mem_map(stop & ~0xFFF, 0x1000)
        except UcError:
            pass
        payload = b"".join(struct.pack("<I", a) for a in reversed(args))
        esp -= len(payload)
        self.uc.mem_write(esp, payload)
        esp -= 4
        self.uc.mem_write(esp, struct.pack("<I", stop))
        self.uc.reg_write(UC_X86_REG_ESP, esp)
        self.uc.reg_write(UC_X86_REG_EBP, esp)
        self.uc.reg_write(UC_X86_REG_ECX, this)   # thiscall
        print(f"  calling {addr:#010x} with {len(args)} arg(s)")
        try:
            self.uc.emu_start(addr, stop, timeout=10_000_000, count=2_000_000)
        except UcError as exc:
            print(f"  emulation stopped: {exc}")
        return self.packets


TARGETS = {
    0x1002d190: "FN_bDrvInitLampTemperatures",
    0x1002c5f0: "FN_bDrvLampOn",
    0x1000c4d0: "FN_bDrvLampOff",
    0x1002d5c0: "FN_bDrvInitCcd",
    0x1000b100: "FN_bInit2",
    0x1000a370: "FN_bDrvGetDevInfo",
    0x10020dc0: "light-setup orchestrator",
    0x10021590: "per-film light setup",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--call", help="function address, e.g. 0x1002d190")
    ap.add_argument("--args", nargs="*", default=[], help="integer arguments")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()

    if a.list or not a.call:
        print("known targets:")
        for addr, name in sorted(TARGETS.items()):
            print(f"  {addr:#010x}  {name}")
        if not a.call:
            return 0

    addr = int(a.call, 0)
    args = tuple(int(x, 0) for x in a.args)
    print(f"=== emulating {TARGETS.get(addr, 'unknown')} at {addr:#010x} ===")
    emu = Emu(a.verbose)
    pkts = emu.call(addr, args)
    print(f"\n  {len(pkts)} packet(s) captured")
    return 0


if __name__ == "__main__":
    sys.exit(main())
