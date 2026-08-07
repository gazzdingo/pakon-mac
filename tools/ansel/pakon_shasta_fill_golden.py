#!/usr/bin/env python3
"""Golden Shasta toneLut fill ``0x10293960`` vs PakonIMAu.dll (Unicorn).

Injects synthetic / cited aim+param vectors (work ``+0x2b0`` role as
``start``, builder param map). Does not require live dmin / AneOrder.

Usage
-----
``PYTHONPATH=tools/ansel python3 tools/ansel/pakon_shasta_fill_golden.py [dll]``
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ESP

import pakon_shasta as shasta

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x200000
PARAM_ADDR = 0x0C100000
LUT_VEC_ADDR = 0x0C200000
LUT_DATA_ADDR = 0x0C210000
CODE_ADDR = 0x00100000
VA_FILL = 0x10293960

DEFAULT_DLL = Path(
    "/Users/guy/Downloads/Pakon Update 3/fx35install/program files/"
    "Pakon/F-X35 COM SERVER/PakonIMAu.dll"
)

# (start, end, code_end, adj, u0, p20, code_28, code_2c, p30)
CASES = [
    (1550, 2358, 2000, 50, 0.5, 0.25, 1800, 1900, 1.0),
    (1550, 2358, 2000, 50, 0.0, 0.25, 1800, 1900, 1.0),
    (1550, 2358, 2000, 50, 1.0, 0.25, 1800, 1900, 1.0),
    (1550, 2358, 2000, 50, 0.5, 0.25, 1800, 1900, 0.5),
    (1618, 3000, 2200, 40, 0.3, 0.1, 1900, 2100, 1.0),
    (1618, 3000, 2200, 40, 0.3, 0.0, 1900, 2100, 1.0),
    (1618, 3000, 2200, 40, 0.3, 0.9, 1900, 2100, 1.0),
    (1000, 800, 900, 10, 0.5, 0.25, 850, 880, 1.0),
    # dpi-shaped aims: metricGray / white ctor defaults
    (
        shasta.SHASTA_PARAMS_CTOR_METRIC_GRAY,
        shasta.SHASTA_PARAMS_CTOR_WHITE,
        2000,
        50,
        0.5,
        0.25,
        1800,
        1900,
        1.0,
    ),
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


def dll_fill(
    pe: bytes,
    start: int,
    end: int,
    param: shasta.ToneLutFillParam,
    n: int = 4096,
) -> tuple[float, float, list[int]]:
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, pe)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(PARAM_ADDR, 0x1000)
    uc.mem_map(LUT_VEC_ADDR, 0x1000)
    uc.mem_map(LUT_DATA_ADDR, _align_up(n * 4))
    uc.mem_map(CODE_ADDR, 0x1000)
    blob = bytearray(0x40)
    struct.pack_into("<ii", blob, 0, param.code_end, param.adj)
    struct.pack_into("<d", blob, 0x10, param.u0)
    struct.pack_into("<d", blob, 0x20, param.p20)
    struct.pack_into("<ii", blob, 0x28, param.code_28, param.code_2c)
    struct.pack_into("<d", blob, 0x30, param.p30)
    uc.mem_write(PARAM_ADDR, bytes(blob))
    uc.mem_write(
        LUT_VEC_ADDR,
        struct.pack("<III", 0, LUT_DATA_ADDR, LUT_DATA_ADDR + n * 4),
    )
    uc.mem_write(LUT_DATA_ADDR, b"\x00" * (n * 4))
    if 0 <= start < n:
        uc.mem_write(LUT_DATA_ADDR + start * 4, struct.pack("<i", start))
    esp = STACK_ADDR + 0x100000
    ret = CODE_ADDR + 0x100
    uc.mem_write(esp, struct.pack("<IIII", ret, start, end, LUT_VEC_ADDR))
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_EAX, PARAM_ADDR)
    uc.mem_write(ret, b"\xCC")
    try:
        uc.emu_start(VA_FILL, ret, timeout=200_000_000, count=80_000_000)
    except UcError:
        pass
    p18 = struct.unpack("<d", uc.mem_read(PARAM_ADDR + 0x18, 8))[0]
    p38 = struct.unpack("<d", uc.mem_read(PARAM_ADDR + 0x38, 8))[0]
    lut = list(struct.unpack(f"<{n}i", uc.mem_read(LUT_DATA_ADDR, n * 4)))
    return p18, p38, lut


def main() -> int:
    dll = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DLL
    pe = dll.read_bytes()
    print(
        f"DLL {dll}\n"
        f"  FILL={shasta.SHASTA_CURVE_FILL_PORTED} "
        f"TONE_LUT={shasta.SHASTA_TONE_LUT_PORTED} "
        f"DISPATCH={shasta.SHASTA_CURVE_DISPATCH_PORTED}"
    )
    bad = 0
    for case in CASES:
        start, end, code_end, adj, u0, p20, c28, c2c, p30 = case
        param = shasta.ToneLutFillParam(
            code_end=code_end,
            adj=adj,
            u0=u0,
            p20=p20,
            code_28=c28,
            code_2c=c2c,
            p30=p30,
        )
        dp18, dp38, dlut = dll_fill(pe, start, end, param)
        lut = shasta.empty_tone_lut(4096)
        shasta.tone_lut_seed_identity(lut, start)
        shasta.tone_lut_fill_93960(lut, start, end, param)
        lo, hi = min(start, end), max(start, end)
        mism = [i for i in range(lo, hi + 1) if int(lut[i]) != dlut[i]]
        p18_ok = abs(param.p18 - dp18) <= 1e-9 * max(1.0, abs(dp18))
        p38_ok = abs(param.p38 - dp38) <= 1e-7 * max(1.0, abs(dp38))
        ok = not mism and p18_ok and p38_ok
        bad += not ok
        print(
            f"  start={start} end={end} u0={u0} p20={p20} p30={p30} "
            f"p18={param.p18:.8g}/{dp18:.8g} "
            f"p38={param.p38:.8g}/{dp38:.8g} "
            f"mism={len(mism)} {'OK' if ok else 'FAIL'}"
        )
        if mism[:3]:
            for i in mism[:3]:
                print(f"    @{i} port={int(lut[i])} dll={dlut[i]}")
    if bad:
        print(f"FAILED {bad} case(s)")
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
