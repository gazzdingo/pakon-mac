#!/usr/bin/env python3
"""Golden ScpLut analyze leaves vs PakonIMAu.dll (Unicorn).

Leaves
------
* ``0x1028c4e0`` opponent transform
* ``0x10212899`` slopeDist
* LUT index ``ftol2(s·i − o + 0.5)`` + clamp ``[0,0xfff]``

Usage
-----
``PYTHONPATH=tools/ansel python3 tools/ansel/pakon_scp_lut_golden.py [dll]``
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_EBP,
    UC_X86_REG_ESP,
)

import pakon_scp_lut as scp

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x100000
HEAP_ADDR = 0x0C000000
HEAP_SIZE = 0x100000

DEFAULT_DLL = Path(
    "/Users/guy/Downloads/Pakon Update 3/fx35install/program files/"
    "Pakon/F-X35 COM SERVER/PakonIMAu.dll"
)


def _load(dll: bytes) -> Uc:
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    # Map image in pages
    pe = dll
    e = struct.unpack_from("<I", pe, 0x3C)[0]
    size = struct.unpack_from("<I", pe, e + 0x50)[0]
    aligned = (max(size, len(pe)) + 0xFFF) & ~0xFFF
    uc.mem_map(IMAGE_BASE, aligned)
    uc.mem_write(IMAGE_BASE, pe[: min(len(pe), aligned)])
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(HEAP_ADDR, HEAP_SIZE)
    return uc


def _run_opponent(uc: Uc, r: float, g: float, b: float) -> tuple[float, float, float]:
    src = HEAP_ADDR + 0x100
    dst = HEAP_ADDR + 0x200
    stop = HEAP_ADDR + 0x300
    uc.mem_write(src, struct.pack("<3d", r, g, b))
    uc.mem_write(dst, b"\x00" * 24)
    uc.mem_write(stop, b"\xc3")
    esp = STACK_ADDR + STACK_SIZE - 0x40
    # cdecl: ret, src, dst
    uc.mem_write(esp, struct.pack("<3I", stop, src, dst))
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.emu_start(scp.SCP_IMPL_OPPONENT, stop, timeout=2_000_000)
    return struct.unpack("<3d", bytes(uc.mem_read(dst, 24)))


def _run_slope_dist(uc: Uc, r: float, g: float, b: float) -> float:
    """Inject slopes on FPU via fld then jump into ``0x10212899`` shell.

    Uses a stub that loads R,G,B as B,G,R stack order then calls leaf end.
    Simpler: host-only formula golden vs independent re-eval of cited math;
    DLL path checked by assembling mini stub that computes same ops.
    """
    # Direct FPU replicate via stub at HEAP:
    # fld qword R; fld G; fld B; then copy of slopeDist insns ending fstp result
    stub = HEAP_ADDR + 0x400
    out = HEAP_ADDR + 0x500
    stop = HEAP_ADDR + 0x600
    # Build: fld [R]; fld [G]; fld [B]; then bytes from 0x10212899..0x102128bd
    # but dest [esi+0xb0] → rewrite to store at `out`.
    pe = Path(DEFAULT_DLL).read_bytes() if False else None
    # Hand-assemble: load constants then inline truncated FPU block storing to out
    code = bytearray()
    # fld qword [imm] for R,G,B from heap+0x700
    base_rg = HEAP_ADDR + 0x700
    uc.mem_write(base_rg, struct.pack("<3d", r, g, b))
    # fld [base]; fld [base+8]; fld [base+10] → ST = B? Wait order fld R, fld G, fld B → top=B
    for off in (0, 8, 16):
        code += bytes([0xDD, 0x05]) + struct.pack("<I", base_rg + off)  # fld qword [abs]
    # now top=B,G,R — paste ops from DLL (relative fstp replaced)
    # Copy machine bytes 0x10212899..0x102128ba (before fstp)
    dll = open(
        "/Users/guy/Downloads/Pakon Update 3/fx35install/program files/"
        "Pakon/F-X35 COM SERVER/PakonIMAu.dll",
        "rb",
    ).read()
    block = dll[0x212899 : 0x2128BD]  # through fsqrt inclusive
    code += block
    # fstp qword [out]
    code += bytes([0xDD, 0x1D]) + struct.pack("<I", out)
    # fstp st(0); fstp st(0); ret
    code += bytes([0xDD, 0xD8, 0xDD, 0xD8, 0xC3])
    uc.mem_write(stub, bytes(code))
    uc.mem_write(out, b"\x00" * 8)
    uc.mem_write(stop, b"\xc3")
    esp = STACK_ADDR + STACK_SIZE - 0x20
    uc.mem_write(esp, struct.pack("<I", stop))
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.emu_start(stub, stop, timeout=2_000_000)
    return struct.unpack("<d", bytes(uc.mem_read(out, 8)))[0]


def main() -> int:
    dll_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DLL
    dll = dll_path.read_bytes()
    print(f"dll={dll_path}")
    assert scp.SCP_LUT_ANALYZE_LEAVES_PORTED
    assert not scp.SCP_LUT_BALANCE_PORTED
    uc = _load(dll)
    failed = 0

    for rgb in ((1.0, 1.0, 1.0), (0.5, 0.2, 0.8), (0.0, 0.0, 0.0), (2.0, 1.0, 0.5)):
        host = scp.scp_lut_opponent_transform(*rgb)
        dll_o = _run_opponent(uc, *rgb)
        ok = all(abs(a - b) < 1e-12 for a, b in zip(host, dll_o))
        mark = "OK" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"  {mark} opponent {rgb} host={host} dll={dll_o}")

    for rgb in ((1.0, 1.0, 1.0), (1.2, 0.9, 1.1), (0.5, 0.5, 2.0), (0.0, 0.0, 0.0)):
        host = scp.scp_lut_slope_dist(*rgb)
        dll_d = _run_slope_dist(uc, *rgb)
        ok = abs(host - dll_d) < 1e-12
        mark = "OK" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"  {mark} slopeDist {rgb} host={host} dll={dll_d}")

    # identity LUT first 8
    fill = scp.scp_lut_fill_channel(1.0, 0.0, 8)
    expect = list(range(8))
    if fill != expect:
        print(f"  FAIL fill identity {fill}")
        failed += 1
    else:
        print("  OK LUT fill identity 0…7")
    # clamp
    if scp.scp_lut_clamp_i16(-3) != 0 or scp.scp_lut_clamp_i16(0x2000) != 0xFFF:
        print("  FAIL clamp")
        failed += 1
    else:
        print("  OK LUT clamp")
    if not scp.scp_lut_analyze_gate(1, 1) or scp.scp_lut_analyze_gate(0, 1):
        print("  FAIL analyze gate")
        failed += 1
    else:
        print("  OK analyze gate")

    if failed:
        print(f"FAILED {failed}")
        return 1
    print("ScpLut analyze leaves golden: ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
