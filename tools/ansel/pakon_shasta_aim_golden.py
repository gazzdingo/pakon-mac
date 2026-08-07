#!/usr/bin/env python3
"""Golden ``avg2largest_i16`` (``0x1004f690``) vs PakonIMAu.dll (Unicorn).

Also sanity-checks ShastaParams ctor defaults for ``metricGray``/``black``/
``white`` (``+0x38/+0x3c/+0x40``) against the cited immediates — not a full
analyze golden.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_ESP,
)

import pakon_shasta as shasta

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x100000
VA_AVG2 = 0x1004F690
TRIPLE_ADDR = STACK_ADDR + 0x80000


def _load_dll(path: Path) -> bytes:
    return path.read_bytes()


def _map_text(uc: Uc, dll: bytes) -> None:
    # PE .text at file/VA offset 0x1000, size 0x572000 (Update 3 layout).
    text_off = 0x1000
    text_va = IMAGE_BASE + text_off
    text_size = 0x572000
    uc.mem_map(text_va & ~0xFFF, text_size + 0x1000)
    uc.mem_write(text_va, dll[text_off : text_off + text_size])


def run_avg2(dll: bytes, a: int, b: int, c: int) -> int:
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    _map_text(uc, dll)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    triple = struct.pack("<hhh", a, b, c)
    uc.mem_write(TRIPLE_ADDR, triple)
    # stdcall/cdecl leaf: eax = &triple; ret
    esp = STACK_ADDR + STACK_SIZE - 0x100
    ret_addr = STACK_ADDR + 0x100
    uc.mem_write(ret_addr, b"\xcc")
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.mem_write(esp, struct.pack("<I", ret_addr))
    uc.reg_write(UC_X86_REG_EAX, TRIPLE_ADDR)
    try:
        uc.emu_start(VA_AVG2, ret_addr, timeout=1_000_000, count=200)
    except UcError:
        # int3 at ret_addr stops emulation — read eax anyway
        pass
    return int(uc.reg_read(UC_X86_REG_EAX))


def main() -> int:
    dll_path = Path(
        sys.argv[1]
        if len(sys.argv) > 1
        else "/Users/guy/Downloads/Pakon Update 3/fx35install/"
        "program files/Pakon/F-X35 COM SERVER/PakonIMAu.dll"
    )
    dll = _load_dll(dll_path)
    cases = [
        (1, 2, 3),
        (10, 10, 10),
        (5, 1, 9),
        (600, 600, 600),
        (100, 200, 300),
        (-3, -1, -2),
        (0, -5, 7),
    ]
    fail = 0
    for a, b, c in cases:
        got = shasta.avg2largest_i16(a, b, c)
        ref = run_avg2(dll, a, b, c)
        # DLL returns AX (movsx already in eax from sar path)
        ref16 = ref & 0xFFFFFFFF
        if ref16 >= 0x80000000:
            ref16 -= 0x100000000
        ok = got == ref16
        print(f"  avg2({a},{b},{c}): host={got} dll={ref16} {'OK' if ok else 'FAIL'}")
        if not ok:
            fail += 1
    assert shasta.SHASTA_PARAMS_CTOR_METRIC_GRAY == 0x60E
    assert shasta.SHASTA_PARAMS_CTOR_BLACK == 0x258
    assert shasta.SHASTA_PARAMS_CTOR_WHITE == 0x936
    print(
        f"  params ctor defaults: metricGray={shasta.SHASTA_PARAMS_CTOR_METRIC_GRAY} "
        f"black={shasta.SHASTA_PARAMS_CTOR_BLACK} "
        f"white={shasta.SHASTA_PARAMS_CTOR_WHITE}"
    )
    print(
        f"  SHASTA_AIM_AVG2_PORTED={shasta.SHASTA_AIM_AVG2_PORTED} "
        f"ANALYZE={shasta.SHASTA_ANALYZE_PORTED} "
        f"TONE_LUT={shasta.SHASTA_TONE_LUT_PORTED}"
    )
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
