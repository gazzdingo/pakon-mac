#!/usr/bin/env python3
"""Golden ``setShifts (1,2)`` against PakonIMAu.dll via Unicorn.

Maps the PE at image base ``0x10000000``, builds a minimal Cap→Impl→
``Ans3BandLutParams`` + planar LUT, enters the shipped branch at
``0x10100a37``, and stops at OUT write complete (``0x101010ac``).

Compares DLL OUT to ``pakon_sba_apply.setshifts_12``. This is byte-code
execution of the vendor fragment — not a re-derived check of our Python
against itself.

Usage
-----
``PYTHONPATH=tools/ansel python3 -m pakon_setshifts_golden [dll] [lut]``

Defaults look under the Update-3 install tree used for RE.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_EBP,
    UC_X86_REG_EBX,
    UC_X86_REG_ECX,
    UC_X86_REG_EDI,
    UC_X86_REG_EDX,
    UC_X86_REG_ESI,
    UC_X86_REG_ESP,
    UC_X86_REG_EIP,
)

from pakon_sba_apply import setshifts_12
from pakon_scp_lut import load_3band_lut_ascii

IMAGE_BASE = 0x10000000
ENTRY_12 = 0x10100A37
STOP_OUT = 0x101010AC  # after OUT[0..2] stores; before COM cleanup
GET_PARAMS = 0x10122150

STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x100000
HEAP_ADDR = 0x0C000000
HEAP_SIZE = 0x100000

DEFAULT_DLL = Path(
    "/Users/guy/Downloads/Pakon Update 3/fx35install/program files/"
    "Pakon/F-X35 COM SERVER/PakonIMAu.dll"
)
DEFAULT_LUT = Path(
    "/Users/guy/Downloads/Pakon Update 3/fx35install/program files/"
    "Pakon/F-X35 COM SERVER/anselinstalldir/dataPathItems/common/"
    "luts6_postROMM_equalRGBshort.lut"
)

CASES: list[tuple[tuple[int, int, int], tuple[int, int, int]]] = [
    ((0, 0, 0), (0, 0, 0)),
    ((100, 100, 100), (0, 0, 0)),
    ((100, 80, 60), (10, -5, 20)),
    ((50, 50, 50), (50, 50, 50)),
    ((-20, 30, -40), (5, 5, 5)),
    ((200, -100, 50), (-30, 40, -10)),
    ((1550, 1550, 1550), (0, 0, 0)),
    ((1, 2, 3), (4, 5, 6)),
]


def _align_up(n: int, a: int = 0x1000) -> int:
    return (n + a - 1) & ~(a - 1)


def load_pe_into_uc(uc: Uc, pe: bytes) -> None:
    e_lfanew = struct.unpack_from("<I", pe, 0x3C)[0]
    num_sec = struct.unpack_from("<H", pe, e_lfanew + 6)[0]
    opt_size = struct.unpack_from("<H", pe, e_lfanew + 20)[0]
    opt = e_lfanew + 24
    size_image = struct.unpack_from("<I", pe, opt + 56)[0]
    uc.mem_map(IMAGE_BASE, _align_up(size_image))
    # Headers
    uc.mem_write(IMAGE_BASE, pe[:0x1000])
    sec_off = opt + opt_size
    for i in range(num_sec):
        o = sec_off + i * 40
        vsz, va, rsz, raddr = struct.unpack_from("<IIII", pe, o + 8)
        if rsz == 0 or raddr == 0:
            continue
        data = pe[raddr : raddr + rsz]
        if len(data) < vsz:
            data = data + b"\x00" * (vsz - len(data))
        uc.mem_write(IMAGE_BASE + va, data[: max(vsz, rsz)])


def _as_i16(x: int) -> int:
    x &= 0xFFFF
    return x - 0x10000 if x >= 0x8000 else x


def _i16_bytes(r: int, g: int, b: int) -> bytes:
    return struct.pack("<hhh", _as_i16(r), _as_i16(g), _as_i16(b))


def run_dll_12(
    uc: Uc,
    shifts_a: tuple[int, int, int],
    shifts_b: tuple[int, int, int],
    *,
    cap_addr: int,
    out_addr: int,
    stack_top: int,
) -> tuple[int, int, int]:
    """Execute DLL ``(1,2)`` body; return OUT as signed int16 triple."""
    # Fresh stack frame: leave room below ESP for locals used as [esp+…]
    esp = stack_top - 0x200
    # Zero a generous local window
    uc.mem_write(esp, b"\x00" * 0x200)
    uc.mem_write(esp + 0x10, _i16_bytes(*shifts_a))
    uc.mem_write(esp + 0x1C, _i16_bytes(*shifts_b))
    uc.mem_write(esp + 0xBC, struct.pack("<I", out_addr))
    uc.mem_write(out_addr, b"\x00" * 8)

    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_EBP, cap_addr)
    uc.reg_write(UC_X86_REG_EAX, 2)  # ctd == 2 at cmp @ entry
    uc.reg_write(UC_X86_REG_EDI, 1)
    for reg in (UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_ESI):
        uc.reg_write(reg, 0)

    stop = {"hit": False}

    def _hook(uc_: Uc, address: int, size: int, _user: object) -> None:
        if address == STOP_OUT:
            stop["hit"] = True
            uc_.emu_stop()

    hh = uc.hook_add(UC_HOOK_CODE, _hook, begin=STOP_OUT, end=STOP_OUT + 1)
    try:
        uc.emu_start(ENTRY_12, STOP_OUT + 1, timeout=2_000_000, count=200_000)
    finally:
        uc.hook_del(hh)

    if not stop["hit"]:
        eip = uc.reg_read(UC_X86_REG_EIP)
        raise RuntimeError(f"did not reach OUT stop; eip={eip:#x}")

    raw = uc.mem_read(out_addr, 6)
    return struct.unpack("<hhh", raw)


def build_cap(uc: Uc, planar: tuple[int, ...], num_lut: int, num_bands: int = 3) -> int:
    """Cap → Impl → Params + planar int16 table on the unicorn heap."""
    heap = HEAP_ADDR
    # layout: params(8) | lut | cap(16) | impl(32) | out pad
    params = heap
    lut = heap + 0x40
    lut_bytes = struct.pack("<" + "h" * len(planar), *[x & 0xFFFF for x in planar])
    uc.mem_write(lut, lut_bytes)
    # Ans3BandLutParams: +0 NUM_LUT, +2 NUM_BANDS, +4 lut*
    uc.mem_write(params, struct.pack("<hhI", num_lut, num_bands, lut))

    impl = lut + _align_up(len(lut_bytes)) + 0x40
    cap = impl + 0x40
    uc.mem_write(impl, b"\x00" * 0x40)
    uc.mem_write(impl + 0x10, struct.pack("<I", params))
    uc.mem_write(cap, b"\x00" * 0x20)
    uc.mem_write(cap + 0x10, struct.pack("<I", impl))
    return cap


def main(argv: list[str]) -> int:
    dll_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_DLL
    lut_path = Path(argv[2]) if len(argv) > 2 else DEFAULT_LUT
    if not dll_path.is_file():
        print(f"DLL not found: {dll_path}", file=sys.stderr)
        return 2
    if not lut_path.is_file():
        print(f"LUT not found: {lut_path}", file=sys.stderr)
        return 2

    pe = dll_path.read_bytes()
    band = load_3band_lut_ascii(lut_path)

    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, pe)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(HEAP_ADDR, HEAP_SIZE)

    cap = build_cap(uc, band.planar, band.num_lut, band.num_bands)
    out_addr = HEAP_ADDR + HEAP_SIZE - 0x40
    stack_top = STACK_ADDR + STACK_SIZE - 0x10

    # Sanity: get-params thunk is present
    thunk = bytes(uc.mem_read(GET_PARAMS, 8))
    if thunk[:3] != b"\x8b\x49\x10":  # mov ecx, [ecx+0x10]
        print(f"unexpected get-params thunk: {thunk.hex()}", file=sys.stderr)
        return 2

    failures = 0
    print(f"DLL  {dll_path}")
    print(f"LUT  {lut_path.name}  NUM_LUT={band.num_lut}")
    print(f"entry {ENTRY_12:#x}  stop {STOP_OUT:#x}")
    print()
    for a, b in CASES:
        try:
            dll_out = run_dll_12(
                uc, a, b, cap_addr=cap, out_addr=out_addr, stack_top=stack_top
            )
        except (UcError, RuntimeError) as e:
            print(f"FAIL A={a} B={b}  emu: {e}")
            failures += 1
            continue
        py_out = setshifts_12(a, b, band.planar, band.num_lut)
        ok = dll_out == py_out
        tag = "OK" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"{tag:4} A={a} B={b}  dll={dll_out}  py={py_out}")

    print()
    if failures:
        print(f"{failures} mismatch(es) — SETSHIFTS_12_PORTED stays False")
        return 1
    print("all cases match DLL — safe to set SETSHIFTS_12_PORTED=True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
