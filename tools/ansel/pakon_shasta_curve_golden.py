#!/usr/bin/env python3
"""Golden Shasta curve log-ratio leaves vs PakonIMAu.dll (Unicorn).

Ports under test:
  ``0x10292c50`` → ``pakon_shasta.curve_log_ratio_c50``
  ``0x10292cb0`` → ``pakon_shasta.curve_log_ratio_cb0``

Usage
-----
``PYTHONPATH=tools/ansel python3 tools/ansel/pakon_shasta_curve_golden.py [dll]``
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_ESP

import pakon_shasta as shasta

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x100000
CODE_ADDR = 0x00100000
CODE_SIZE = 0x1000
OUT_ADDR = STACK_ADDR + 0x90000

VA_C50 = 0x10292C50
VA_CB0 = 0x10292CB0

DEFAULT_DLL = Path(
    "/Users/guy/Downloads/Pakon Update 3/fx35install/program files/"
    "Pakon/F-X35 COM SERVER/PakonIMAu.dll"
)

CASES_C50 = [
    (0.5, 1.0),
    (0.2, 1.0),
    (1.0, 2.0),
    (0.0, 1.0),
    (0.99, 1.0),
    (0.999, 1.0),
    (0.9990000001, 1.0),
    (1.5, 1.0),
    (-0.5, 1.0),
    (0.998, 1.0),
]

CASES_CB0 = [
    (0.5, 1.0),
    (0.69314718056, 1.0),
    (1.38629436112, 2.0),
    (0.0, 1.0),
    (4.60517018599, 1.0),
    (10.0, 1.0),
    (-1.0, 1.0),
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


def dll_call_2d(pe: bytes, entry: int, a: float, b: float) -> float:
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, pe)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(CODE_ADDR, CODE_SIZE)
    esp = STACK_ADDR + 0x80000
    uc.mem_write(esp, struct.pack("<dd", a, b))
    uc.reg_write(UC_X86_REG_ESP, esp)
    rel = entry - (CODE_ADDR + 5)
    code = (
        b"\xE8" + struct.pack("<i", rel)
        + b"\xDD\x1D" + struct.pack("<I", OUT_ADDR)
        + b"\xCC"
    )
    uc.mem_write(CODE_ADDR, code)
    try:
        uc.emu_start(CODE_ADDR, CODE_ADDR + len(code) - 1, timeout=5_000_000)
    except UcError:
        pass
    return struct.unpack("<d", uc.mem_read(OUT_ADDR, 8))[0]


def main() -> int:
    dll = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DLL
    pe = dll.read_bytes()
    print(f"DLL {dll}  SHASTA_CURVE_LOG_RATIO_PORTED="
          f"{shasta.SHASTA_CURVE_LOG_RATIO_PORTED}")
    bad = 0
    print("=== 0x10292c50 / curve_log_ratio_c50 ===")
    for a, b in CASES_C50:
        got = shasta.curve_log_ratio_c50(a, b)
        ref = dll_call_2d(pe, VA_C50, a, b)
        ok = abs(got - ref) < 1e-9
        bad += not ok
        print(f"  ({a:g},{b:g}) port={got:.12g} dll={ref:.12g} "
              f"{'OK' if ok else 'FAIL'}")
    print("=== 0x10292cb0 / curve_log_ratio_cb0 ===")
    for a, b in CASES_CB0:
        got = shasta.curve_log_ratio_cb0(a, b)
        ref = dll_call_2d(pe, VA_CB0, a, b)
        ok = abs(got - ref) < 1e-8
        bad += not ok
        print(f"  ({a:g},{b:g}) port={got:.12g} dll={ref:.12g} "
              f"{'OK' if ok else 'FAIL'}")
    if bad:
        print(f"FAILED {bad} case(s)")
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
