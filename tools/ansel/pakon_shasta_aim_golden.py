#!/usr/bin/env python3
"""Golden Shasta aim fragments vs PakonIMAu.dll (Unicorn).

* ``avg2largest_i16`` (``0x1004f690``) — Unicorn
* ``ftol2_chop`` (``0x104ffe44``) — same leaf as Preference golden
  (``pakon_sba_preference.ftol2_104ffe44``); host trunc checks only here
* Host closed-form checks for master clip LUT + ``cn_premium_mid_aim_rgb``
  (master LUT ctor ``0x100f42a0`` / CRT ``0x1056a470`` cited)
* SceneContext dmin bag + ``NoiseTable`` layout; Unicorn
  ``0x10256102`` dens-alloc ``n*ch*4``

ShastaParams ctor defaults for ``metricGray``/``black``/``white`` /
``blackNoiseSigmaMult`` are sanity-checked against cited immediates —
not a full analyze golden.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import numpy as np
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_EBX,
    UC_X86_REG_EDI,
    UC_X86_REG_ESP,
)

import pakon_ane_order as ane
import pakon_scene_context as sc
import pakon_shasta as shasta

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x100000
VA_AVG2 = 0x1004F690
# dens alloc size: mov eax,ebx; imul eax,edi; shl eax,2 @ 0x10256102
VA_NOISE_ALLOC_IMUL = 0x10256102
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
    esp = STACK_ADDR + STACK_SIZE - 0x100
    ret_addr = STACK_ADDR + 0x100
    uc.mem_write(ret_addr, b"\xcc")
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.mem_write(esp, struct.pack("<I", ret_addr))
    uc.reg_write(UC_X86_REG_EAX, TRIPLE_ADDR)
    try:
        uc.emu_start(VA_AVG2, ret_addr, timeout=1_000_000, count=200)
    except UcError:
        pass
    return int(uc.reg_read(UC_X86_REG_EAX))


def run_noise_alloc_size(dll: bytes, n: int, n_channels: int) -> int:
    """Unicorn ``mov eax,ebx; imul eax,edi; shl eax,2`` @ ``0x10256102``."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    _map_text(uc, dll)
    end_va = 0x1025610A  # after shl eax, 2 (before push)
    uc.reg_write(UC_X86_REG_EBX, n & 0xFFFFFFFF)
    uc.reg_write(UC_X86_REG_EDI, n_channels & 0xFFFFFFFF)
    try:
        uc.emu_start(VA_NOISE_ALLOC_IMUL, end_va, timeout=100_000, count=8)
    except UcError:
        pass
    return int(uc.reg_read(UC_X86_REG_EAX)) & 0xFFFFFFFF


def _sx32(v: int) -> int:
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


def main() -> int:
    dll_path = Path(
        sys.argv[1]
        if len(sys.argv) > 1
        else "/Users/guy/Downloads/Pakon Update 3/fx35install/"
        "program files/Pakon/F-X35 COM SERVER/PakonIMAu.dll"
    )
    dll = _load_dll(dll_path)
    fail = 0

    cases = [
        (1, 2, 3),
        (10, 10, 10),
        (5, 1, 9),
        (600, 600, 600),
        (100, 200, 300),
        (-3, -1, -2),
        (0, -5, 7),
    ]
    for a, b, c in cases:
        got = shasta.avg2largest_i16(a, b, c)
        ref = _sx32(run_avg2(dll, a, b, c))
        ok = got == ref
        print(f"  avg2({a},{b},{c}): host={got} dll={ref} {'OK' if ok else 'FAIL'}")
        if not ok:
            fail += 1

    # ftol2 already Unicorn-golden via Preference; host trunc contract only.
    for x, expect in [(0.5, 0), (2.5, 2), (-0.5, 0), (-2.5, -2), (20.0, 20)]:
        got = shasta.ftol2_chop(x)
        ok = got == expect
        print(f"  ftol2_chop({x}): {got} (expect {expect}) {'OK' if ok else 'FAIL'}")
        if not ok:
            fail += 1

    # Master clip LUT closed form (ctor 0x100f42a0 fill loops)
    for code, expect in [(-1, 0), (0, 0), (100, 100), (4095, 4095), (4096, 4095)]:
        got = shasta.master_lut_clip_i16(code)
        ok = got == expect
        print(f"  master_lut({code}): {got} (expect {expect}) {'OK' if ok else 'FAIL'}")
        if not ok:
            fail += 1

    # Mid-aim: zero dens + zero shifts → avg2(dmin) twice
    dens = np.zeros(4096, dtype=np.float32)
    dmin = (100, 200, 300)
    m0, m1 = shasta.cn_premium_mid_aim_rgb(dmin, dens, (0, 0, 0))
    expect = shasta.avg2largest_i16(*dmin)
    ok = m0 == expect == m1
    print(f"  mid_aim zero-dens: {m0},{m1} (expect {expect},{expect}) {'OK' if ok else 'FAIL'}")
    if not ok:
        fail += 1

    # dens[200]=10, scale=2 → dens_i=20 on G; dmin_dens=(100,220,300)
    dens[200] = 10.0
    m0, m1 = shasta.cn_premium_mid_aim_rgb(
        dmin, dens, (0, 0, 0), black_noise_sigma_mult=2.0
    )
    expect0 = shasta.avg2largest_i16(100, 200, 300)
    expect1 = shasta.avg2largest_i16(100, 220, 300)
    ok = m0 == expect0 and m1 == expect1
    print(
        f"  mid_aim dens: {m0},{m1} (expect {expect0},{expect1}) "
        f"{'OK' if ok else 'FAIL'}"
    )
    if not ok:
        fail += 1

    # setShifts + clip: dmin+(500,0,0) stays in range
    m0, m1 = shasta.cn_premium_mid_aim_rgb(
        (100, 100, 100), np.zeros(64, dtype=np.float32), (50, -20, 0)
    )
    expect = shasta.avg2largest_i16(150, 80, 100)
    ok = m0 == m1 == expect
    print(f"  mid_aim shifts: {m0},{m1} (expect {expect}) {'OK' if ok else 'FAIL'}")
    if not ok:
        fail += 1

    # metricGray threshold alternate: remapped dmin > thr → lut[black+shift]
    m0, m1 = shasta.cn_premium_mid_aim_rgb(
        (2000, 2000, 2000),
        np.zeros(4096, dtype=np.float32),
        (10, 20, 30),
        black=600,
        metric_gray=1550,
    )
    expect = shasta.avg2largest_i16(610, 620, 630)
    ok = m0 == m1 == expect
    print(
        f"  mid_aim threshold: {m0},{m1} (expect {expect}) {'OK' if ok else 'FAIL'}"
    )
    if not ok:
        fail += 1

    assert shasta.SHASTA_PARAMS_CTOR_METRIC_GRAY == 0x60E
    assert shasta.SHASTA_PARAMS_CTOR_BLACK == 0x258
    assert shasta.SHASTA_PARAMS_CTOR_WHITE == 0x936
    assert shasta.SHASTA_PARAMS_CTOR_BLACK_NOISE_SIGMA_MULT == 2.0
    print(
        f"  params ctor defaults: metricGray={shasta.SHASTA_PARAMS_CTOR_METRIC_GRAY} "
        f"black={shasta.SHASTA_PARAMS_CTOR_BLACK} "
        f"white={shasta.SHASTA_PARAMS_CTOR_WHITE} "
        f"sigmaMult={shasta.SHASTA_PARAMS_CTOR_BLACK_NOISE_SIGMA_MULT}"
    )

    # Scene-context dmin bag (find/insert contract; host model)
    bag = sc.SceneContextBag()
    ok = bag.find_dmin() is None
    print(f"  bag empty find: {bag.find_dmin()} {'OK' if ok else 'FAIL'}")
    if not ok:
        fail += 1
    blob = sc.baddscene_pack_dmin_from_desc(100, 200, 300)
    expect_blob = bytes([0x64, 0x00, 0xC8, 0x00, 0x2C, 0x01])  # LE int16
    ok = (
        blob == expect_blob
        and blob == sc.pack_dmin_rgb(100, 200, 300)
        and sc.unpack_dmin_rgb(blob) == (100, 200, 300)
    )
    print(f"  dmin pack/unpack: {blob.hex()} {'OK' if ok else 'FAIL'}")
    if not ok:
        fail += 1
    bag.insert_dmin((100, 200, 300))
    got = bag.find_dmin()
    ok = got == (100, 200, 300)
    print(f"  bag roundtrip: {got} {'OK' if ok else 'FAIL'}")
    if not ok:
        fail += 1

    # NoiseTable layout + alloc size (0x102560a0 formula)
    for n, ch, expect_nb in [(64, 1, 256), (100, 3, 1200), (0, 1, 0)]:
        nb = ane.noise_table_alloc_nbytes(n, ch)
        ok = nb == expect_nb
        print(f"  noise_alloc({n},{ch})={nb} (expect {expect_nb}) {'OK' if ok else 'FAIL'}")
        if not ok:
            fail += 1
    # Unicorn: run imul/shl fragment with eax=n, edi=ch → eax=nbytes
    for n, ch in [(64, 1), (100, 3), (4096, 1)]:
        ref = run_noise_alloc_size(dll, n, ch)
        host = ane.noise_table_alloc_nbytes(n, ch)
        ok = ref == host
        print(
            f"  noise_alloc unicorn n={n} ch={ch}: host={host} dll={ref} "
            f"{'OK' if ok else 'FAIL'}"
        )
        if not ok:
            fail += 1

    nt = ane.NoiseTable.zeros(4096, 1)
    nt.dens[0, 200] = 10.0
    m = shasta.cn_premium_mid_aim_from_bag(
        bag, nt, (0, 0, 0), black_noise_sigma_mult=2.0
    )
    expect0 = shasta.avg2largest_i16(100, 200, 300)
    expect1 = shasta.avg2largest_i16(100, 220, 300)
    ok = m == (expect0, expect1)
    print(
        f"  mid_aim from bag+NoiseTable: {m} (expect {(expect0, expect1)}) "
        f"{'OK' if ok else 'FAIL'}"
    )
    if not ok:
        fail += 1

    print(
        f"  SHASTA_AIM_AVG2_PORTED={shasta.SHASTA_AIM_AVG2_PORTED} "
        f"MID_RGB={shasta.SHASTA_AIM_MID_RGB_PORTED} "
        f"INPUT_PATH={shasta.SHASTA_AIM_INPUT_PATH_PORTED} "
        f"ANALYZE={shasta.SHASTA_ANALYZE_PORTED} "
        f"TONE_LUT={shasta.SHASTA_TONE_LUT_PORTED} "
        f"SCENE_DMIN={sc.SCENE_CONTEXT_DMIN_PORTED} "
        f"NOISE_LAYOUT={ane.ANE_NOISE_TABLE_LAYOUT_PORTED} "
        f"ANE_ORDER={ane.ANE_ORDER_PORTED}"
    )
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
