#!/usr/bin/env python3
"""Golden image-sample leaves + I16 Op vs PakonIMAu.dll (Unicorn).

* ``0x104ea6c0`` + identity ``0x104f5710`` hist percentile (bin capture)
* ``0x1027b3c0`` white-pt ratio / planar means (cited closed form)
* ``0x1014dcf1`` I16 LUT-index apply fragment

Full planar Iem bodies for ``0x1027b970`` / ``0x1027b3c0`` use host hist
counts (Iem fill ``0x104ea940`` not ported).

Usage
-----
``PYTHONPATH=tools/ansel python3 tools/ansel/pakon_shasta_sample_golden.py [dll]``
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_EBX,
    UC_X86_REG_ECX,
    UC_X86_REG_EDX,
    UC_X86_REG_EBP,
    UC_X86_REG_ESP,
)

import numpy as np
import pakon_shasta as shasta

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x200000
HEAP_ADDR = 0x0C100000
HEAP_SIZE = 0x200000
VA_EA6C0 = 0x104EA6C0
VA_I16_APPLY = 0x1014DCF1
VA_I16_APPLY_END = 0x1014DD0A

DEFAULT_DLL = Path(
    "/Users/guy/Downloads/Pakon Update 3/fx35install/program files/"
    "Pakon/F-X35 COM SERVER/PakonIMAu.dll"
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


def _map_text(uc: Uc, pe: bytes) -> None:
    load_pe_into_uc(uc, pe)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(HEAP_ADDR, HEAP_SIZE)


def dll_hist_percentile(pe: bytes, counts: list[int], percent: float) -> int:
    """Unicorn ``0x104ea6c0`` — capture bin at ``0x104ea739``, identity code."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    _map_text(uc, pe)
    n = len(counts)
    counts_addr = HEAP_ADDR + 0x1000
    hist = HEAP_ADDR + 0x8000
    wrap = HEAP_ADDR + 0x9000
    uc.mem_write(counts_addr, struct.pack(f"<{n}i", *counts))
    blob = bytearray(0x40)
    struct.pack_into("<i", blob, 0x0C, n)
    struct.pack_into("<d", blob, 0x10, 0.0)
    struct.pack_into("<d", blob, 0x28, 1.0)
    struct.pack_into("<I", blob, 0x38, counts_addr)
    uc.mem_write(hist, bytes(blob))
    uc.mem_write(wrap, struct.pack("<II", 0, hist))

    bin_box: list[int] = [-1]

    def on_code(uc_: Uc, address: int, size: int, _user: object) -> None:
        if address == 0x104EA739:
            bin_box[0] = int(uc_.reg_read(UC_X86_REG_EBX)) & 0xFFFFFFFF

    uc.hook_add(UC_HOOK_CODE, on_code, begin=0x104EA739, end=0x104EA73A)
    esp = STACK_ADDR + 0x8000
    ret_stub = HEAP_ADDR + 0xF000
    uc.mem_write(ret_stub, b"\xc3")
    uc.mem_write(esp, struct.pack("<I", ret_stub))
    uc.mem_write(esp + 4, struct.pack("<I", wrap))
    uc.mem_write(esp + 8, struct.pack("<d", float(percent)))
    uc.reg_write(UC_X86_REG_ESP, esp)
    try:
        uc.emu_start(VA_EA6C0, ret_stub, timeout=2_000_000, count=50_000)
    except UcError:
        pass
    if bin_box[0] < 0:
        raise RuntimeError("percentile hook missed bin")
    return shasta.ftol2_chop(float(bin_box[0]))


def dll_i16_apply_word(pe: bytes, code: int, table_word: int) -> int:
    """One iteration of ``0x1014dcf1``: ``out = low16(table[code])``."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    _map_text(uc, pe)
    table = HEAP_ADDR + 0x2000
    plane = HEAP_ADDR + 0x100
    uc.mem_write(table + code * 4, struct.pack("<i", int(table_word)))
    uc.mem_write(plane, struct.pack("<h", int(code) & 0xFFFF))
    agg = HEAP_ADDR + 0x3000
    uc.mem_write(agg + 4, struct.pack("<I", table))
    esp = STACK_ADDR + 0x8000
    uc.mem_write(esp + 0x18, struct.pack("<I", agg))
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_EDX, plane)
    uc.reg_write(UC_X86_REG_ECX, 0)
    uc.reg_write(UC_X86_REG_EAX, 1)
    uc.reg_write(UC_X86_REG_EBP, 0)
    uc.reg_write(UC_X86_REG_EBX, 0)
    try:
        uc.emu_start(
            VA_I16_APPLY, VA_I16_APPLY_END, timeout=100_000, count=40
        )
    except UcError:
        pass
    return int(struct.unpack("<h", uc.mem_read(plane, 2))[0])


def main() -> int:
    dll = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DLL
    pe = dll.read_bytes()
    print(
        f"DLL {dll}\n"
        f"  HIST={shasta.SHASTA_HIST_PERCENTILE_PORTED} "
        f"7B970={shasta.SHASTA_IMAGE_PERCENTILE_7B970_PORTED} "
        f"7B3C0={shasta.SHASTA_IMAGE_SAMPLE_7B3C0_PORTED} "
        f"APPLY={shasta.SHASTA_APPLY_PORTED} "
        f"TONE_LUT={shasta.SHASTA_TONE_LUT_PORTED}"
    )
    bad = 0

    counts = [1] * 100
    for pct in (0.0, 1.0, 25.0, 50.0, 99.0, 100.0):
        host = shasta.hist_percentile_ea6c0(np.asarray(counts, np.int32), pct)
        ref = dll_hist_percentile(pe, counts, pct)
        ok = host == ref
        bad += not ok
        print(f"  ea6c0 pct={pct}: host={host} dll={ref} {'OK' if ok else 'FAIL'}")

    counts2 = [0] * 50 + [10] * 10 + [0] * 40
    for pct in (10.0, 50.0, 90.0):
        host = shasta.hist_percentile_ea6c0(np.asarray(counts2, np.int32), pct)
        ref = dll_hist_percentile(pe, counts2, pct)
        ok = host == ref
        bad += not ok
        print(
            f"  ea6c0 skew pct={pct}: host={host} dll={ref} "
            f"{'OK' if ok else 'FAIL'}"
        )

    cases = [
        (False, 100.0, 0.33, 0.8, 75.0, 1.0),
        (True, 10.0, 0.33, 0.8, 75.0, 1.0),
        (True, 1000.0, 0.33, 0.8, 75.0, 0.0),
        (True, 40.0, 0.33, 0.8, 75.0, None),
    ]
    for use, hyp, lo, hi, cv, expect in cases:
        got = shasta.white_pt_ratio_7b3c0(
            hyp,
            use_white_pt=use,
            white_sat_lower=lo,
            white_sat_upper=hi,
            code_values_per_button=cv,
        )
        if expect is None:
            lo_v = lo * cv
            hi_v = hi * cv
            expect = (hi_v - hyp) / (hi_v - lo_v)
        ok = abs(got - expect) < 1e-12
        bad += not ok
        print(
            f"  white_pt hyp={hyp} use={use}: {got:.6g} "
            f"{'OK' if ok else 'FAIL'}"
        )

    rgb = np.zeros((4, 4, 3), dtype=np.int16)
    rgb[:, :, 0] = 2000
    rgb[:, :, 1] = 100
    rgb[:, :, 2] = 200
    rgb[0, 0, 0] = 100
    m = shasta.image_range_means_7b3c0(rgb, 1500, 2500, use_white_pt=False)
    ok = (
        abs(m.mean_310 - 100.0) < 1e-9
        and abs(m.mean_318 - 200.0) < 1e-9
        and abs(m.p340 - 1.0) < 1e-9
    )
    bad += not ok
    print(
        f"  7b3c0 means: 310={m.mean_310:.4g} 318={m.mean_318:.4g} "
        f"320={m.hypot_320:.4g} 340={m.p340:.4g} {'OK' if ok else 'FAIL'}"
    )

    for code, word in [(0, 0), (100, 1234), (2000, 0x12345678)]:
        lut = np.zeros(4096, dtype=np.int32)
        lut[code] = np.int32(word)
        host = int(
            shasta.ima_shasta_apply_i16(np.array([code], np.int16), lut)[0]
        )
        expect = int(np.int16(word & 0xFFFF))
        ref = dll_i16_apply_word(pe, code, word)
        ok = host == expect == ref
        bad += not ok
        print(
            f"  i16 apply code={code} word={word:#x}: "
            f"host={host} dll={ref} {'OK' if ok else 'FAIL'}"
        )

    counts3 = np.bincount(
        np.linspace(500, 2500, 1000).astype(np.int32), minlength=4096
    ).astype(np.int32)
    codes = shasta.image_percentile_codes_7b970(
        counts3,
        ext_shadow_percent=1.0,
        shadow_percent=5.0,
        highlight_percent=95.0,
        ext_highlight_percent=99.0,
        mid_lo=400,
        code_white=3000,
    )
    ok = (
        codes.code_2e4
        <= codes.code_2e8
        <= codes.code_2ec
        <= codes.code_2f0
        and codes.code_2e4 >= 400
        and codes.code_2f0 <= 3000
    )
    bad += not ok
    print(
        f"  7b970 codes={codes.code_2e4},{codes.code_2e8},"
        f"{codes.code_2ec},{codes.code_2f0} {'OK' if ok else 'FAIL'}"
    )

    if bad:
        print(f"FAILED {bad} case(s)")
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
