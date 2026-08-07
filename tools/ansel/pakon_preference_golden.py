#!/usr/bin/env python3
"""Golden Preference FPU (@ ``0x1028c780``) against PakonIMAu.dll via Unicorn.

Builds a minimal blob + output block, enters Preference, reads shifts at
``out+0x3a38−0x3a30`` (= ``out+8``). Compares to
``pakon_sba_preference.preference_shifts_hi10`` / mode-``0x11``.

Usage
-----
``PYTHONPATH=tools/ansel python3 tools/ansel/pakon_preference_golden.py [dll]``
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_EBP,
    UC_X86_REG_ESP,
    UC_X86_REG_EIP,
)

import pakon_sba_preference as pref

IMAGE_BASE = 0x10000000
PREF_ENTRY = 0x1028C780
PREF_RET = 0x1028CD02

STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x100000
HEAP_ADDR = 0x0C000000
HEAP_SIZE = 0x200000

DEFAULT_DLL = Path(
    "/Users/guy/Downloads/Pakon Update 3/fx35install/program files/"
    "Pakon/F-X35 COM SERVER/PakonIMAu.dll"
)

# CN-default dpi-ish scalars (sba-CN-default)
CN_DEFAULT = dict(
    fpo=(879, 1250, 1386),
    fpa=(-70, -55, -45),
    neu=(975, 975, 975),
    neo=(1010, 1010, 1010),
    pcls=0,
    non_flash_adj=0,
    nbp=1550,
    neutral_button=130,
    under=-16.0,
    over=16.0,
)


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


def build_blob(
    *,
    fpo: tuple[int, int, int],
    fpa: tuple[int, int, int],
    neu: tuple[int, int, int],
    neo: tuple[int, int, int],
    pcls: int,
    non_flash_adj: int,
    lim46: int,
    lo42: int,
    hi44: int,
) -> bytes:
    """Preference input blob (``0x10214f20`` fill layout)."""
    b = bytearray(0x80)
    struct.pack_into("<hhh", b, 0x00, *fpo)
    struct.pack_into("<hhh", b, 0x06, *fpa)
    struct.pack_into("<hhh", b, 0x0C, *neu)
    struct.pack_into("<hhh", b, 0x12, *neo)
    struct.pack_into("<h", b, 0x1E, pcls)
    struct.pack_into("<h", b, 0x30, non_flash_adj)
    struct.pack_into("<h", b, 0x42, lo42)
    struct.pack_into("<h", b, 0x44, hi44)
    struct.pack_into("<h", b, 0x46, lim46)
    return bytes(b)


def build_param(
    *,
    param0: int = 0,
    param_0x12: int = 0,
    param_0x40: int = 0,
) -> bytes:
    b = bytearray(0x80)
    struct.pack_into("<h", b, 0x00, param0)
    struct.pack_into("<h", b, 0x12, param_0x12)
    struct.pack_into("<h", b, 0x40, param_0x40)
    return bytes(b)


def build_arg1(*, arg1_0: int = 0) -> bytes:
    b = bytearray(0x20)
    struct.pack_into("<h", b, 0x00, arg1_0)
    return bytes(b)


def run_preference(
    uc: Uc,
    *,
    mode: int,
    blob: bytes,
    param: bytes | None = None,
    arg1: bytes | None = None,
    heap: int = HEAP_ADDR,
) -> tuple[int, tuple[int, int, int]]:
    """Execute Preference; return ``(eax, shifts_at_out+8)``."""
    blob_addr = heap
    out_addr = heap + 0x200
    param_addr = heap + 0x800
    arg1_addr = heap + 0xC00
    uc.mem_write(blob_addr, blob)
    uc.mem_write(out_addr, b"\x00" * 0x200)
    uc.mem_write(param_addr, (param or b"\x00" * 0x80))
    if arg1 is not None:
        uc.mem_write(arg1_addr, arg1)

    # cdecl call frame
    ret_stub = heap + 0x1000
    uc.mem_write(ret_stub, b"\xcc")  # int3 — stop
    esp = STACK_ADDR + STACK_SIZE - 0x100
    # cdecl: ret, param, arg1, out, blob, mode
    frame = struct.pack(
        "<IIIIII",
        ret_stub,
        param_addr,
        arg1_addr if arg1 is not None else 0,
        out_addr,
        blob_addr,
        mode & 0xFFFFFFFF,
    )
    uc.mem_write(esp, frame)
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_EBP, 0)
    uc.reg_write(UC_X86_REG_EAX, 0)

    stop = {"hit": False}

    def _hook(uc_: Uc, address: int, size: int, _user: object) -> None:
        if address == ret_stub:
            stop["hit"] = True
            uc_.emu_stop()

    hh = uc.hook_add(UC_HOOK_CODE, _hook, begin=ret_stub, end=ret_stub + 1)
    try:
        uc.emu_start(PREF_ENTRY, ret_stub + 1, timeout=5_000_000, count=500_000)
    finally:
        uc.hook_del(hh)

    if not stop["hit"]:
        eip = uc.reg_read(UC_X86_REG_EIP)
        raise RuntimeError(f"Preference did not return; eip={eip:#x}")

    eax = uc.reg_read(UC_X86_REG_EAX) & 0xFFFFFFFF
    raw = bytes(uc.mem_read(out_addr + 8, 6))
    shifts = struct.unpack("<hhh", raw)
    return eax, shifts


def py_hi10(case: dict) -> tuple[int, int, int]:
    lim46 = pref.lim46_from_neutral_balance_point(case["nbp"])
    lo42, hi44 = pref.clamp_limits_from_neutral_button(
        case["neutral_button"], case["under"], case["over"]
    )
    return pref.preference_shifts_hi10(
        case["fpo"],
        case["fpa"],
        lo=case.get("lo", 1),
        lim46=lim46,
        lo42=lo42,
        hi44=hi44,
        pcls=case["pcls"],
        neu=case["neu"],
        neo=case["neo"],
        non_flash_adj=case["non_flash_adj"],
        param0=case.get("param0", 0),
        param_0x12=case.get("param_0x12", 0),
        param_0x40=case.get("param_0x40", 0),
        arg1_0=case.get("arg1_0", 0),
    )


CASES_0x11: list[dict] = [
    dict(CN_DEFAULT),
    dict(CN_DEFAULT, fpo=(930, 1260, 1470), fpa=(0, 0, 0)),
    dict(CN_DEFAULT, fpo=(100, 200, 300), fpa=(-10, -20, -30)),
    dict(CN_DEFAULT, pcls=50),
    dict(CN_DEFAULT, nbp=1400, neutral_button=100),
    dict(CN_DEFAULT, fpo=(0, 0, 0), fpa=(0, 0, 0)),
    dict(CN_DEFAULT, fpo=(2000, 1800, 1600), fpa=(100, -50, 25)),
]

# hi=0x10, lo≠1 — aimY from param/arg1 (docs/49 @ 0x1028c92f)
CASES_HI10_LO: list[dict] = [
    dict(CN_DEFAULT, lo=0, param0=1000),
    dict(CN_DEFAULT, lo=2, param_0x12=800),
    dict(CN_DEFAULT, lo=3, arg1_0=1500),
    dict(CN_DEFAULT, lo=4, param_0x40=-100, arg1_0=0),  # arg1 required non-null
    dict(CN_DEFAULT, lo=0, param0=500, pcls=25),
    dict(CN_DEFAULT, lo=2, param_0x12=900, fpo=(100, 200, 300), fpa=(0, 0, 0)),
]


def main(argv: list[str]) -> int:
    dll_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_DLL
    if not dll_path.is_file():
        print(f"DLL not found: {dll_path}", file=sys.stderr)
        return 2

    pe = dll_path.read_bytes()
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, pe)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(HEAP_ADDR, HEAP_SIZE)

    print(f"DLL  {dll_path}")
    print(f"entry {PREF_ENTRY:#x}")
    print(f"PREFERENCE_SHIFTS_PORTED={pref.PREFERENCE_SHIFTS_PORTED}")
    print()

    failures = 0
    all_cases: list[tuple[str, dict]] = [
        *(("0x11", dict(c, lo=1)) for c in CASES_0x11),
        *(("hi10", c) for c in CASES_HI10_LO),
    ]
    for i, (tag, case) in enumerate(all_cases):
        lim46 = pref.lim46_from_neutral_balance_point(case["nbp"])
        lo42, hi44 = pref.clamp_limits_from_neutral_button(
            case["neutral_button"], case["under"], case["over"]
        )
        blob = build_blob(
            fpo=case["fpo"],
            fpa=case["fpa"],
            neu=case["neu"],
            neo=case["neo"],
            pcls=case["pcls"],
            non_flash_adj=case["non_flash_adj"],
            lim46=lim46,
            lo42=lo42,
            hi44=hi44,
        )
        lo = case.get("lo", 1)
        mode = 0x10 | (lo & 0xF)
        need_arg1 = lo in (3, 4)
        param = build_param(
            param0=case.get("param0", 0),
            param_0x12=case.get("param_0x12", 0),
            param_0x40=case.get("param_0x40", 0),
        )
        arg1 = build_arg1(arg1_0=case.get("arg1_0", 0)) if need_arg1 else None
        try:
            eax, dll_out = run_preference(
                uc, mode=mode, blob=blob, param=param, arg1=arg1
            )
        except (UcError, RuntimeError) as e:
            print(f"FAIL[{i}] emu: {e}")
            failures += 1
            continue
        py_out = py_hi10(case)
        ok = eax == 0 and dll_out == py_out
        status = "OK" if ok else "FAIL"
        if not ok:
            failures += 1
        print(
            f"{status:4}[{i}] {tag} mode={mode:#x} lo={lo} fpo={case['fpo']} "
            f"fpa={case['fpa']} pcls={case['pcls']}  "
            f"dll={dll_out}  py={py_out}  eax={eax}"
        )

    print()
    if failures:
        print(f"{failures} mismatch(es) — PREFERENCE_SHIFTS_PORTED stays False")
        return 1
    print(
        "all hi=0x10 cases (lo∈{0,1,2,3,4}) match DLL — "
        "safe to keep PREFERENCE_SHIFTS_PORTED=True"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
