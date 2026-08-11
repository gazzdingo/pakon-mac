#!/usr/bin/env python3
"""Golden ``0x102935d0`` + Cap publish / assemble vs PakonIMAu.dll.

Injects image codes + prep ints + dpi scalars. Skips live ``0x1027b3c0``
sampling. Cap path matches ``setToneLut`` ``0x101e48d0`` (int16→int32).
Assemble = host ``935d0`` + scale + builder, checked against DLL builder
with the same post-``935d0`` fields (builder leaf already golden).

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 tools/ansel/python-pipeline/pakon_shasta_tone_lut_golden.py [dll]``
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import (
    UC_X86_REG_ECX,
    UC_X86_REG_EIP,
    UC_X86_REG_ESP,
)

import numpy as np
import pakon_shasta as shasta
import pakon_shasta_builder_golden as builder_golden

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x200000
WORK_ADDR = 0x0C100000
CODE_ADDR = 0x00100000
VA_935D0 = 0x102935D0

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


def _pack_935d0(w: shasta.ToneLutBuilderWork) -> bytes:
    blob = bytearray(0x400)
    struct.pack_into("<d", blob, 0x58, w.code_values_per_button)
    struct.pack_into("<d", blob, 0x100, w.highlight_exp_scale)
    struct.pack_into("<d", blob, 0x108, w.shadow_max_exp_slope)
    struct.pack_into("<d", blob, 0x110, w.highlight_max_exp_slope)
    struct.pack_into("<d", blob, 0x118, w.shadow_comp_blend)
    struct.pack_into("<d", blob, 0x1E8, w.max_exp_delta)
    struct.pack_into("<d", blob, 0x1F0, w.max_comp_delta)
    struct.pack_into("<d", blob, 0x1F8, w.adj_clamp_lo_src)
    struct.pack_into("<d", blob, 0x200, w.adj_clamp_hi_src)
    struct.pack_into("<i", blob, 0x2B0, w.code_start)
    struct.pack_into("<i", blob, 0x2B4, w.mid_lo)
    struct.pack_into("<i", blob, 0x2BC, w.code_white)
    struct.pack_into("<i", blob, 0x2F4, w.code_2f4)
    struct.pack_into("<i", blob, 0x2F8, w.code_2f8)
    struct.pack_into("<i", blob, 0x2FC, w.code_2fc)
    struct.pack_into("<i", blob, 0x300, w.code_300)
    struct.pack_into("<i", blob, 0x32C, w.code_32c)
    struct.pack_into("<i", blob, 0x330, w.code_330)
    struct.pack_into("<i", blob, 0x334, w.code_334)
    struct.pack_into("<i", blob, 0x338, w.code_338)
    return bytes(blob)


def dll_935d0(
    pe: bytes, w: shasta.ToneLutBuilderWork
) -> tuple[tuple[int, ...], tuple[float, ...]]:
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, pe)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(WORK_ADDR, 0x1000)
    uc.mem_map(CODE_ADDR, 0x1000)
    uc.mem_write(WORK_ADDR, _pack_935d0(w))
    uc.mem_write(CODE_ADDR, b"\xc3")
    esp = STACK_ADDR + STACK_SIZE - 0x100
    uc.mem_write(esp, struct.pack("<I", CODE_ADDR))
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_ECX, WORK_ADDR)
    try:
        uc.emu_start(VA_935D0, CODE_ADDR, timeout=5_000_000, count=10_000_000)
    except UcError as e:
        raise RuntimeError(
            f"935d0 emu failed eip={uc.reg_read(UC_X86_REG_EIP):#x}: {e}"
        ) from e
    out = uc.mem_read(WORK_ADDR, 0x400)
    codes = struct.unpack_from("<iiii", out, 0x2F4)
    adjs = struct.unpack_from("<dddd", out, 0x368)
    return codes, adjs


def _sample(start: int = 1550, **kw: object) -> shasta.ToneLutBuilderWork:
    d: dict[str, object] = dict(
        code_start=start,
        code_min=0,
        code_max=3000,
        code_48=start + 200,
        off_328=100,
        code_32c=start - 500,
        code_330=start - 250,
        code_334=start + 450,
        code_338=start + 550,
        code_2f4=start - 400,
        code_2f8=start - 200,
        code_2fc=start + 200,
        code_300=start + 400,
        p340=1.0,
        mid_lo=800,
        mid_hi=1200,
        code_white=3000,
        adj_scale_370=1.0,
        adj_scale_378=1.0,
    )
    d.update(kw)
    return shasta.ToneLutBuilderWork(**d)  # type: ignore[arg-type]


def main() -> int:
    dll = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DLL
    pe = dll.read_bytes()
    print(
        f"DLL {dll}\n"
        f"  935D0={shasta.SHASTA_IMAGE_FIELDS_935D0_PORTED} "
        f"CAP={shasta.SHASTA_CAP_TONE_LUT_PORTED} "
        f"BUILDER={shasta.SHASTA_TONE_LUT_BUILDER_PORTED} "
        f"TONE_LUT={shasta.SHASTA_TONE_LUT_PORTED}"
    )
    bad = 0

    cases = [
        _sample(),
        _sample(code_2f4=1000, code_2f8=1200, code_2fc=1800, code_300=2100),
        _sample(code_2f4=1600, code_2f8=1400, code_2fc=1700, code_300=1900),
        _sample(highlight_exp_scale=0.2, shadow_max_exp_slope=0.8),
        _sample(max_exp_delta=0.5, max_comp_delta=3.0, mid_lo=900, code_white=2500),
        _sample(adj_clamp_lo_src=10.0, adj_clamp_hi_src=20.0),
        _sample(
            code_start=1618,
            code_2f4=1200,
            code_2f8=1400,
            code_2fc=1800,
            code_300=2000,
            code_32c=1100,
            code_330=1300,
            code_334=1900,
            code_338=2100,
            mid_lo=900,
            code_white=2800,
            code_max=2800,
            code_48=1818,
        ),
        _sample(adj_scale_370=0.5, adj_scale_378=1.5),
    ]
    for i, w in enumerate(cases):
        d_codes, d_adjs = dll_935d0(pe, w)
        h = shasta.ToneLutBuilderWork(**w.__dict__)
        shasta.image_derived_fields_935d0(h)
        h_codes = (h.code_2f4, h.code_2f8, h.code_2fc, h.code_300)
        h_adjs = (h.adj_368, h.adj_370, h.adj_378, h.adj_380)
        ok = h_codes == d_codes and all(
            abs(a - b) <= 1e-9 * max(1.0, abs(b)) for a, b in zip(h_adjs, d_adjs)
        )
        bad += not ok
        print(
            f"  935d0[{i}] codes={h_codes} "
            f"adjs=({h.adj_368:.4g},{h.adj_370:.4g},{h.adj_378:.4g},{h.adj_380:.4g}) "
            f"{'OK' if ok else 'FAIL'}"
        )
        if not ok:
            print(f"    dll codes={d_codes} adjs={d_adjs}")

    src = np.array([0, 1, -2, 3000, 0x7FFF], dtype=np.int16)
    cap = shasta.cap_set_tone_lut_from_i16(src)
    ok = list(cap) == list(src.astype(np.int32))
    bad += not ok
    print(f"  setToneLut movsx {'OK' if ok else 'FAIL'}")

    # assemble = 935d0 + scale + builder; DLL check = builder on post-935d0 fields
    for i, w in enumerate(cases[:4]):
        h = shasta.ToneLutBuilderWork(**w.__dict__)
        h_tone, h_bn, h_cap = shasta.assemble_tone_lut(
            h, run_935d0=True, scale_adjs=True
        )
        # Rebuild work snapshot matching what assemble fed the builder
        w_dll = shasta.ToneLutBuilderWork(**w.__dict__)
        shasta.image_derived_fields_935d0(w_dll)
        shasta.scale_adjs_after_935d0(w_dll)
        d_tone, d_bn, *_ = builder_golden.dll_builder(pe, w_dll)
        hi = int(w.code_max)
        mism_t = [j for j in range(hi + 1) if int(h_tone[j]) != d_tone[j]]
        mism_b = [j for j in range(hi) if int(h_bn[j]) != d_bn[j]]
        cap_ok = all(int(h_cap[j]) == int(h_tone[j]) for j in range(hi + 1))
        ok = not mism_t and not mism_b and cap_ok
        bad += not ok
        print(
            f"  assemble[{i}] mism_t={len(mism_t)} mism_b={len(mism_b)} "
            f"cap={'OK' if cap_ok else 'FAIL'} {'OK' if ok else 'FAIL'}"
        )
        for j in mism_t[:2]:
            print(f"    tone@{j} port={int(h_tone[j])} dll={d_tone[j]}")

    if bad:
        print(f"FAILED {bad} case(s)")
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
