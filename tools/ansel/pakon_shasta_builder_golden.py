#!/usr/bin/env python3
"""Golden Shasta builder ``0x10293ee0`` + ``0x10293d50`` vs PakonIMAu.dll.

Injects work-object fields (aims, blend dpi scalars, prep ints, mid codes).
Skips live dmin / AneOrder / ``0x102935d0``. Skips Cap ``+0x3e0`` export.

Usage
-----
``PYTHONPATH=tools/ansel python3 tools/ansel/pakon_shasta_builder_golden.py [dll]``
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_ECX,
    UC_X86_REG_EIP,
    UC_X86_REG_ESP,
)

import pakon_shasta as shasta

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x200000
WORK_ADDR = 0x0C100000
TONE_ADDR = 0x0C200000
BN_ADDR = 0x0C300000
CODE_ADDR = 0x00100000
VA_BUILDER = 0x10293EE0
VA_PREP = 0x1027B1C0
VA_93D50 = 0x10293D50
VA_VEC_FILL = 0x10246050

DEFAULT_DLL = Path(
    "/Users/guy/Downloads/Pakon Update 3/fx35install/program files/"
    "Pakon/F-X35 COM SERVER/PakonIMAu.dll"
)

N = 4096


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


def _pack_work(w: shasta.ToneLutBuilderWork) -> bytes:
    blob = bytearray(0x400)
    struct.pack_into("<i", blob, 0x48, w.code_48)
    struct.pack_into("<i", blob, 0x60, w.code_min)
    struct.pack_into("<i", blob, 0x64, w.code_max)
    struct.pack_into("<d", blob, 0x120, w.shadow_exp_blend)
    struct.pack_into("<d", blob, 0x128, w.highlight_exp_blend)
    struct.pack_into("<d", blob, 0x130, w.shadow_transition_ratio)
    struct.pack_into("<d", blob, 0x138, w.highlight_transition_ratio)
    struct.pack_into("<d", blob, 0x140, w.shadow_exp_sat_factor)
    struct.pack_into("<d", blob, 0x148, w.shadow_comp_sat_factor)
    struct.pack_into("<d", blob, 0x1D0, w.black_noise_std_dev)
    struct.pack_into("<d", blob, 0x1D8, w.min_black_offset)
    struct.pack_into("<d", blob, 0x1E0, w.max_white_offset)
    struct.pack_into("<d", blob, 0x220, w.highlight_delta_gain)
    struct.pack_into("<i", blob, 0x2B0, w.code_start)
    struct.pack_into("<i", blob, 0x2B4, w.mid_lo)
    struct.pack_into("<i", blob, 0x2B8, w.mid_hi)
    struct.pack_into("<i", blob, 0x2F4, w.code_2f4)
    struct.pack_into("<i", blob, 0x300, w.code_300)
    struct.pack_into("<i", blob, 0x328, w.off_328)
    struct.pack_into("<i", blob, 0x32C, w.code_32c)
    struct.pack_into("<i", blob, 0x330, w.code_330)
    struct.pack_into("<i", blob, 0x334, w.code_334)
    struct.pack_into("<i", blob, 0x338, w.code_338)
    struct.pack_into("<d", blob, 0x340, w.p340)
    struct.pack_into("<d", blob, 0x370, w.adj_370)
    struct.pack_into("<d", blob, 0x378, w.adj_378)
    # vector<object> @ +0x3ac / +0x3bc: begin at +4
    struct.pack_into("<III", blob, 0x3AC, 0, TONE_ADDR, TONE_ADDR + N * 4)
    struct.pack_into("<III", blob, 0x3BC, 0, BN_ADDR, BN_ADDR + N * 4)
    return bytes(blob)


def dll_93d50(
    pe: bytes,
    inp: shasta.BlackNoise93d50In,
    tone: list[int],
) -> list[int]:
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, pe)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(WORK_ADDR, 0x1000)
    uc.mem_map(TONE_ADDR, _align_up(N * 4))
    uc.mem_map(BN_ADDR, _align_up(N * 4))
    uc.mem_map(CODE_ADDR, 0x1000)

    # Stub 0x10246050 (stdcall ret 8) — zero-fill blackNoise[0:count]
    def _on_code(uc: Uc, address: int, size: int, _user: object) -> None:
        if address != VA_VEC_FILL:
            return
        esp = uc.reg_read(UC_X86_REG_ESP)
        ret, count, _fill = struct.unpack("<III", uc.mem_read(esp, 12))
        this = uc.reg_read(UC_X86_REG_ECX)
        begin = struct.unpack("<I", uc.mem_read(this + 4, 4))[0]
        if begin and count > 0:
            uc.mem_write(begin, b"\x00" * (count * 4))
        uc.reg_write(UC_X86_REG_ESP, esp + 12)
        uc.reg_write(UC_X86_REG_EIP, ret)

    uc.hook_add(UC_HOOK_CODE, _on_code, begin=VA_VEC_FILL, end=VA_VEC_FILL + 1)

    work = bytearray(0x400)
    struct.pack_into("<d", work, 0x1D0, inp.black_noise_std_dev)
    struct.pack_into("<d", work, 0x1D8, inp.min_black_offset)
    struct.pack_into("<d", work, 0x1E0, inp.max_white_offset)
    struct.pack_into("<i", work, 0x2B4, inp.mid_lo)
    struct.pack_into("<i", work, 0x2B8, inp.mid_hi)
    struct.pack_into("<i", work, 0x328, inp.off_328)
    struct.pack_into("<i", work, 0x64, inp.code_max)
    struct.pack_into("<III", work, 0x3AC, 0, TONE_ADDR, TONE_ADDR + N * 4)
    struct.pack_into("<III", work, 0x3BC, 0, BN_ADDR, BN_ADDR + N * 4)
    uc.mem_write(WORK_ADDR, bytes(work))
    uc.mem_write(TONE_ADDR, struct.pack(f"<{N}i", *tone))
    uc.mem_write(BN_ADDR, b"\x00" * (N * 4))
    esp = STACK_ADDR + 0x100000
    ret = CODE_ADDR + 0x100
    uc.mem_write(esp, struct.pack("<II", ret, inp.arg))
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_ECX, WORK_ADDR)
    uc.mem_write(ret, b"\xCC")
    try:
        uc.emu_start(VA_93D50, ret, timeout=200_000_000, count=80_000_000)
    except UcError:
        pass
    return list(struct.unpack(f"<{N}i", uc.mem_read(BN_ADDR, N * 4)))


def dll_builder(
    pe: bytes,
    w: shasta.ToneLutBuilderWork,
) -> tuple[list[int], list[int], float, float, float, float]:
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, pe)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(WORK_ADDR, 0x1000)
    uc.mem_map(TONE_ADDR, _align_up(N * 4))
    uc.mem_map(BN_ADDR, _align_up(N * 4))
    uc.mem_map(CODE_ADDR, 0x1000)

    def _skip_prep(uc: Uc, address: int, size: int, _user: object) -> None:
        esp = uc.reg_read(UC_X86_REG_ESP)
        ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
        uc.reg_write(UC_X86_REG_ESP, esp + 4)
        uc.reg_write(UC_X86_REG_EIP, ret)

    def _stub_vec_fill(uc: Uc, address: int, size: int, _user: object) -> None:
        esp = uc.reg_read(UC_X86_REG_ESP)
        ret, count, _fill = struct.unpack("<III", uc.mem_read(esp, 12))
        this = uc.reg_read(UC_X86_REG_ECX)
        begin = struct.unpack("<I", uc.mem_read(this + 4, 4))[0]
        if begin and count > 0:
            uc.mem_write(begin, b"\x00" * (count * 4))
        uc.reg_write(UC_X86_REG_ESP, esp + 12)
        uc.reg_write(UC_X86_REG_EIP, ret)

    uc.hook_add(UC_HOOK_CODE, _skip_prep, begin=VA_PREP, end=VA_PREP + 1)
    uc.hook_add(UC_HOOK_CODE, _stub_vec_fill, begin=VA_VEC_FILL, end=VA_VEC_FILL + 1)

    uc.mem_write(WORK_ADDR, _pack_work(w))
    uc.mem_write(TONE_ADDR, b"\x00" * (N * 4))
    uc.mem_write(BN_ADDR, b"\x00" * (N * 4))
    esp = STACK_ADDR + 0x100000
    ret = CODE_ADDR + 0x100
    arg = int(w.code_48) - int(w.code_start)
    uc.mem_write(esp, struct.pack("<II", ret, arg))
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_ECX, WORK_ADDR)
    uc.mem_write(ret, b"\xCC")
    try:
        uc.emu_start(VA_BUILDER, ret, timeout=500_000_000, count=200_000_000)
    except UcError as e:
        eip = uc.reg_read(UC_X86_REG_EIP)
        raise RuntimeError(f"builder emu failed eip={eip:#x}: {e}") from e
    tone = list(struct.unpack(f"<{N}i", uc.mem_read(TONE_ADDR, N * 4)))
    bn = list(struct.unpack(f"<{N}i", uc.mem_read(BN_ADDR, N * 4)))
    p18_hi = struct.unpack("<d", uc.mem_read(WORK_ADDR + 0x358, 8))[0]
    p38_hi = struct.unpack("<d", uc.mem_read(WORK_ADDR + 0x360, 8))[0]
    p18_lo = struct.unpack("<d", uc.mem_read(WORK_ADDR + 0x350, 8))[0]
    p38_lo = struct.unpack("<d", uc.mem_read(WORK_ADDR + 0x348, 8))[0]
    return tone, bn, p18_hi, p38_hi, p18_lo, p38_lo


def _sample_work() -> shasta.ToneLutBuilderWork:
    start = shasta.SHASTA_PARAMS_CTOR_METRIC_GRAY
    return shasta.ToneLutBuilderWork(
        code_start=start,
        code_min=0,
        code_max=3000,
        code_48=start + 200,
        off_328=100,
        code_32c=start - 400,
        code_330=start - 200,
        code_334=start + 450,
        code_338=start + 550,
        code_2f4=start - 350,
        code_300=start + 350,
        p340=1.0,
        adj_370=40.0,
        adj_378=50.0,
        shadow_exp_blend=0.5,
        highlight_exp_blend=0.5,
        shadow_transition_ratio=0.3,
        highlight_transition_ratio=0.3,
        shadow_exp_sat_factor=0.25,
        shadow_comp_sat_factor=0.25,
        highlight_delta_gain=1.0,
        mid_lo=800,
        mid_hi=1200,
        black_noise_std_dev=2.0,
        min_black_offset=10.0,
        max_white_offset=1.0,
    )


def main() -> int:
    dll = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DLL
    pe = dll.read_bytes()
    print(
        f"DLL {dll}\n"
        f"  FILL={shasta.SHASTA_CURVE_FILL_PORTED} "
        f"93D50={shasta.SHASTA_BLACK_NOISE_93D50_PORTED} "
        f"BUILDER={shasta.SHASTA_TONE_LUT_BUILDER_PORTED} "
        f"TONE_LUT={shasta.SHASTA_TONE_LUT_PORTED}"
    )
    bad = 0

    # --- 0x10293d50 ---
    tone_id = list(range(N))
    d50_cases = [
        shasta.BlackNoise93d50In(800, 1200, 2.0, 10.0, 1.0, 100, 3000, 50),
        shasta.BlackNoise93d50In(800, 1200, 2.0, 10.0, 0.5, 100, 3000, 50),
        shasta.BlackNoise93d50In(1550, 1800, 1.5, 5.0, 2.0, 200, 500, 100),
        shasta.BlackNoise93d50In(800, 800, 2.0, 10.0, 1.0, 100, 200, 50),
        shasta.BlackNoise93d50In(800, 1200, 0.0, 10.0, 1.0, 100, 200, 50),
    ]
    for inp in d50_cases:
        d_bn = dll_93d50(pe, inp, tone_id)
        h_bn = shasta.empty_tone_lut(N)
        h_tone = np_int32(tone_id)
        shasta.black_noise_fill_93d50(h_bn, h_tone, inp)
        mism = [i for i in range(inp.code_max) if int(h_bn[i]) != d_bn[i]]
        ok = not mism
        bad += not ok
        print(
            f"  93d50 mid={inp.mid_lo}/{inp.mid_hi} "
            f"std={inp.black_noise_std_dev} mism={len(mism)} "
            f"{'OK' if ok else 'FAIL'}"
        )
        for i in mism[:3]:
            print(f"    @{i} port={int(h_bn[i])} dll={d_bn[i]}")

    # --- builder 0x10293ee0 ---
    works = [
        _sample_work(),
        shasta.ToneLutBuilderWork(
            code_start=1618,
            code_min=0,
            code_max=2800,
            code_48=1800,
            off_328=80,
            code_32c=1200,
            code_330=1400,
            code_334=2000,
            code_338=2200,
            code_2f4=1100,
            code_300=1900,
            p340=0.8,
            adj_370=30.0,
            adj_378=-10.0,  # forces transition-ratio u0 on fill#1
            shadow_exp_blend=0.4,
            highlight_exp_blend=0.6,
            shadow_transition_ratio=0.2,
            highlight_transition_ratio=0.7,
            shadow_exp_sat_factor=0.1,
            shadow_comp_sat_factor=0.9,
            highlight_delta_gain=0.5,
            mid_lo=900,
            mid_hi=1300,
            black_noise_std_dev=1.25,
            min_black_offset=8.0,
            max_white_offset=1.5,
        ),
    ]
    for w in works:
        d_tone, d_bn, dp18h, dp38h, dp18l, dp38l = dll_builder(pe, w)
        h_tone = shasta.empty_tone_lut(N)
        h_bn = shasta.empty_tone_lut(N)
        # fresh copy — builder mutates work p18 fields
        w_h = shasta.ToneLutBuilderWork(**w.__dict__)
        shasta.tone_lut_builder_93ee0(h_tone, h_bn, w_h)
        hi = int(w.code_max)
        mism_t = [i for i in range(hi + 1) if int(h_tone[i]) != d_tone[i]]
        mism_b = [i for i in range(hi) if int(h_bn[i]) != d_bn[i]]
        # also shadow side below start
        mism_lo = [
            i
            for i in range(0, int(w.code_start) + 1)
            if int(h_tone[i]) != d_tone[i]
        ]
        def _close(a: float, b: float, eps: float = 1e-7) -> bool:
            return abs(a - b) <= eps * max(1.0, abs(b))

        slopes_ok = (
            _close(w_h.p18_hi, dp18h)
            and _close(w_h.p38_hi, dp38h, 1e-6)
            and _close(w_h.p18_lo, dp18l)
            and _close(w_h.p38_lo, dp38l, 1e-6)
        )
        ok = not mism_t and not mism_b and not mism_lo and slopes_ok
        bad += not ok
        print(
            f"  builder start={w.code_start} max={w.code_max} "
            f"mism_t={len(mism_t)} mism_b={len(mism_b)} "
            f"mism_lo={len(mism_lo)} slopes={'OK' if slopes_ok else 'FAIL'} "
            f"{'OK' if ok else 'FAIL'}"
        )
        for i in (mism_t[:2] + mism_lo[:2]):
            print(f"    tone@{i} port={int(h_tone[i])} dll={d_tone[i]}")
        for i in mism_b[:2]:
            print(f"    bn@{i} port={int(h_bn[i])} dll={d_bn[i]}")
        if not slopes_ok:
            print(
                f"    p18_hi {w_h.p18_hi:.8g}/{dp18h:.8g} "
                f"p38_hi {w_h.p38_hi:.8g}/{dp38h:.8g} "
                f"p18_lo {w_h.p18_lo:.8g}/{dp18l:.8g} "
                f"p38_lo {w_h.p38_lo:.8g}/{dp38l:.8g}"
            )

    if bad:
        print(f"FAILED {bad} case(s)")
        return 1
    print("ALL OK")
    return 0


def np_int32(xs: list[int]):
    import numpy as np

    return np.array(xs, dtype=np.int32)


if __name__ == "__main__":
    raise SystemExit(main())
