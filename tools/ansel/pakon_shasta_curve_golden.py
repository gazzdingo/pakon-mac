#!/usr/bin/env python3
"""Golden Shasta curve leaves vs PakonIMAu.dll (Unicorn).

Ports under test:
  ``0x10292c50`` → ``curve_log_ratio_c50``
  ``0x10292cb0`` → ``curve_log_ratio_cb0``
  ``0x10292d30`` → ``curve_exp_d30``
  ``0x10292d80`` → ``curve_exp_d80``
  ``0x10293330`` → ``curve_newton_330``
  ``0x10293410`` → ``curve_newton_410``
  ``0x10293510`` → ``curve_dispatch_93510``

Usage
-----
``PYTHONPATH=tools/ansel python3 tools/ansel/pakon_shasta_curve_golden.py [dll]``
"""
from __future__ import annotations

import math
import struct
import sys
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_EDX, UC_X86_REG_ESP

import pakon_shasta as shasta

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x100000
CODE_ADDR = 0x00100000
CODE_SIZE = 0x1000
OUT_ADDR = STACK_ADDR + 0x90000

VA_C50 = 0x10292C50
VA_CB0 = 0x10292CB0
VA_D30 = 0x10292D30
VA_D80 = 0x10292D80
VA_330 = 0x10293330
VA_410 = 0x10293410
VA_510 = 0x10293510

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

CASES_D30 = [
    (0.5, 0.0, 1.0),
    (1.0, 0.0, 2.0),
    (0.5, 0.5, 1.0),
    (2.0, 1.0, 3.0),
    (0.25, 0.1, 0.5),
]

CASES_D80 = [
    (0.5, 0.2, 1.0, 2.0),
    (0.5, 1.5, 1.0, 2.0),
    (2.0, 0.5, 1.0, 1.0),
    (1.0, 2.0, 1.0, 3.0),
    (0.5, 1.0, 1.0, 1.0),
    (0.5, 0.2, -1.0, 2.0),
    (0.5, -2.0, -1.0, 2.0),
]

CASES_330 = [
    (0.5, 0.5, 0.1),
    (1.0, 1.0, 0.1),
    (2.0, 1.0, 0.1),
    (1.0, 0.5, 0.1),
    (0.5, 1.0, 0.1),
]

CASES_410 = [
    (0.5, 0.5, 0.1, 0.1),
    (1.0, 0.5, 0.2, 0.1),
    (0.2, 0.5, 0.5, 0.1),
    (0.5, 0.2, 1.0, 0.1),
    (1.0, 1.0, 1.0, 0.1),
    (418.0, -182.0, 418.0, 0.1),
    (-1.0, -0.5, 0.5, 0.1),
]

CASES_510 = [
    (1.0, 0.5, 0.5),
    (1.0, 0.2, 0.5),
    (2.0, 1.0, 1.0),
    (1.0, 0.5, -0.5),
    (-1.0, -0.2, -0.5),
    (-1.0, -0.5, -0.5),
    (-418.0, 182.0, -418.0),
    (0.5, 0.5, 1.0),
    (0.5, 1.0, 2.0),
    (-2.0, -1.0, -1.0),
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


def dll_call(pe: bytes, entry: int, args: tuple[float, ...], edx: int | None = None) -> float:
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, pe)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(CODE_ADDR, CODE_SIZE)
    esp = STACK_ADDR + 0x80000
    uc.mem_write(esp, b"".join(struct.pack("<d", a) for a in args))
    uc.reg_write(UC_X86_REG_ESP, esp)
    if edx is not None:
        uc.reg_write(UC_X86_REG_EDX, edx)
    rel = entry - (CODE_ADDR + 5)
    code = (
        b"\xE8"
        + struct.pack("<i", rel)
        + b"\xDD\x1D"
        + struct.pack("<I", OUT_ADDR)
        + b"\xCC"
    )
    uc.mem_write(CODE_ADDR, code)
    try:
        uc.emu_start(CODE_ADDR, CODE_ADDR + len(code) - 1, timeout=50_000_000)
    except UcError:
        pass
    return struct.unpack("<d", uc.mem_read(OUT_ADDR, 8))[0]


def _ok(got: float, ref: float, rtol: float = 1e-6) -> bool:
    if not math.isfinite(got) or not math.isfinite(ref):
        return got == ref or (math.isnan(got) and math.isnan(ref))
    scale = max(1.0, abs(ref))
    return abs(got - ref) <= rtol * scale


def _run(label: str, cases, port_fn, entry, pe, edx=None, rtol=1e-6) -> int:
    print(f"=== {label} ===")
    bad = 0
    for args in cases:
        got = port_fn(*args)
        ref = dll_call(pe, entry, args, edx=edx)
        ok = _ok(got, ref, rtol=rtol)
        bad += not ok
        print(
            f"  {args} port={got:.12g} dll={ref:.12g} "
            f"{'OK' if ok else 'FAIL'}"
        )
    return bad


def main() -> int:
    dll = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DLL
    pe = dll.read_bytes()
    print(
        f"DLL {dll}\n"
        f"  LOG_RATIO={shasta.SHASTA_CURVE_LOG_RATIO_PORTED} "
        f"EXP={shasta.SHASTA_CURVE_EXP_PORTED} "
        f"DISPATCH={shasta.SHASTA_CURVE_DISPATCH_PORTED} "
        f"TONE_LUT={shasta.SHASTA_TONE_LUT_PORTED}"
    )
    bad = 0
    bad += _run(
        "0x10292c50 / curve_log_ratio_c50",
        CASES_C50,
        shasta.curve_log_ratio_c50,
        VA_C50,
        pe,
        rtol=1e-9,
    )
    bad += _run(
        "0x10292cb0 / curve_log_ratio_cb0",
        CASES_CB0,
        shasta.curve_log_ratio_cb0,
        VA_CB0,
        pe,
        rtol=1e-8,
    )
    bad += _run(
        "0x10292d30 / curve_exp_d30",
        CASES_D30,
        shasta.curve_exp_d30,
        VA_D30,
        pe,
        rtol=1e-9,
    )
    bad += _run(
        "0x10292d80 / curve_exp_d80",
        CASES_D80,
        shasta.curve_exp_d80,
        VA_D80,
        pe,
        rtol=1e-9,
    )
    bad += _run(
        "0x10293330 / curve_newton_330",
        CASES_330,
        shasta.curve_newton_330,
        VA_330,
        pe,
        edx=100,
        rtol=1e-6,
    )
    bad += _run(
        "0x10293410 / curve_newton_410",
        CASES_410,
        shasta.curve_newton_410,
        VA_410,
        pe,
        edx=100,
        rtol=1e-6,
    )
    bad += _run(
        "0x10293510 / curve_dispatch_93510",
        CASES_510,
        shasta.curve_dispatch_93510,
        VA_510,
        pe,
        rtol=1e-5,
    )
    if bad:
        print(f"FAILED {bad} case(s)")
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
