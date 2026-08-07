#!/usr/bin/env python3
"""Golden Shasta aim fragments vs PakonIMAu.dll (Unicorn).

* ``avg2largest_i16`` (``0x1004f690``) — Unicorn
* ``ftol2_chop`` (``0x104ffe44``) — same leaf as Preference golden
  (``pakon_sba_preference.ftol2_104ffe44``); host trunc checks only here
* Host closed-form checks for master clip LUT + ``cn_premium_mid_aim_rgb``
  (master LUT ctor ``0x100f42a0`` / CRT ``0x1056a470`` cited)
* SceneContext dmin bag + ``NoiseTable`` layout; Unicorn
  ``0x10256102`` dens-alloc ``n*ch*4``
* ScpLut dmin remap ``0x100fd984…``; AneOrder dens fill ``0x101ec10a…``
* bAddScene dmin pack ``0x100022e6…``; AneOrder analyze bin-index
  ``0x102a8555…``
* TLA AddScene desc pack ``0x1003f901…``; Ane dens-hist ``inc``
  ``0x104f56e0…``; getCnContext path-from-bag host contract
* TLA FindDmin high-side hist walk ``0x100093f0…`` (frame ``+0x6cac``);
  host ColNeg 1px remap contract (stage-2 closed form)

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
    UC_X86_REG_EBP,
    UC_X86_REG_ECX,
    UC_X86_REG_EDI,
    UC_X86_REG_EDX,
    UC_X86_REG_ESI,
    UC_X86_REG_ESP,
)

import pakon_ane_order as ane
import pakon_scene_context as sc
import pakon_shasta as shasta

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x100000
HEAP_ADDR = 0x20000000
HEAP_SIZE = 0x200000
VA_AVG2 = 0x1004F690
# dens alloc size: mov eax,ebx; imul eax,edi; shl eax,2 @ 0x10256102
VA_NOISE_ALLOC_IMUL = 0x10256102
VA_SCPLUT_REMAP = 0x100FD984
VA_SCPLUT_REMAP_END = 0x100FD9B7
VA_GET_RESULTS_FILL = 0x101EC10A
VA_GET_RESULTS_FILL_END = 0x101EC1D6
VA_BADDSCENE_PACK = 0x100022E6
VA_BADDSCENE_PACK_END = 0x10002309
VA_ANE_BIN_INDEX = 0x102A8555
VA_ANE_BIN_INDEX_END = 0x102A857C
VA_ANE_HIST_ACCUM = ane.ANE_ANALYZE_HIST_ACCUM
VA_ANE_HIST_ACCUM_END = ane.ANE_ANALYZE_HIST_ACCUM_END
VA_TLA_DESC_PACK = sc.TLA_DESC_PACK
VA_TLA_DESC_PACK_END = sc.TLA_DESC_PACK_END
VA_TLA_FIND_DMIN_WALK = sc.TLA_FIND_DMIN_HIST_WALK
VA_TLA_FIND_DMIN_WALK_END = sc.TLA_FIND_DMIN_HIST_WALK_END
TRIPLE_ADDR = STACK_ADDR + 0x80000
DEFAULT_IMAU = (
    "/Users/guy/Downloads/Pakon Update 3/fx35install/"
    "program files/Pakon/F-X35 COM SERVER/PakonIMAu.dll"
)
DEFAULT_TLA = (
    "/Users/guy/Downloads/Pakon Update 3/fx35install/"
    "program files/Pakon/F-X35 COM SERVER/TLA.dll"
)
DEFAULT_COLOR_DIR = (
    "/Users/guy/Downloads/Pakon Update 3/fx35install/"
    "program files/Pakon/F-X35 COM SERVER/Config/ColorCorrection"
)


def _load_dll(path: Path) -> bytes:
    return path.read_bytes()


def _map_region(uc: Uc, dll: bytes, va: int, size: int) -> None:
    page = va & ~0xFFF
    end = (va + size + 0xFFF) & ~0xFFF
    span = end - page
    try:
        uc.mem_map(page, span)
    except UcError:
        pass
    off = page - IMAGE_BASE
    uc.mem_write(page, dll[off : off + span])


def _map_text(uc: Uc, dll: bytes) -> None:
    # PE .text at file/VA offset 0x1000, size 0x572000 (Update 3 layout).
    _map_region(uc, dll, IMAGE_BASE + 0x1000, 0x572000)


def _map_tla_text(uc: Uc, tla: bytes) -> None:
    """Map TLA.dll .text (Update 3: VA/file ``0x1000``, size ``0x63000``)."""
    _map_region(uc, tla, IMAGE_BASE + 0x1000, 0x63000)


def _map_fill_deps(uc: Uc, dll: bytes) -> None:
    _map_text(uc, dll)
    _map_region(uc, dll, 0x1059B000, 0x2000)  # FLT_EPSILON + strings
    _map_region(uc, dll, 0x10577000, 0x2000)  # curve wrapper vtables


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


def run_scplut_remap(
    dll: bytes, lut: list[int], stride: int, r: int, g: int, b: int
) -> tuple[int, int, int]:
    """Unicorn ScpLut remap leaf ``0x100fd984…0x100fd9b7``."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    _map_text(uc, dll)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(HEAP_ADDR, HEAP_SIZE)
    path = HEAP_ADDR + 0x1000
    lut_addr = HEAP_ADDR + 0x2000
    for i, v in enumerate(lut):
        uc.mem_write(lut_addr + i * 2, struct.pack("<h", int(v)))
    uc.mem_write(path + 0x3C, struct.pack("<hhh", r, g, b))
    esp = STACK_ADDR + 0x8000
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.mem_write(esp + 0x20, struct.pack("<I", lut_addr))
    uc.mem_write(esp + 0x2C, struct.pack("<I", stride & 0xFFFFFFFF))
    uc.reg_write(UC_X86_REG_EDI, path)
    try:
        uc.emu_start(VA_SCPLUT_REMAP, VA_SCPLUT_REMAP_END, timeout=1_000_000, count=80)
    except UcError:
        pass
    return struct.unpack("<hhh", uc.mem_read(path + 0x3C, 6))


def run_get_results_fill(
    dll: bytes,
    knots: list[tuple[float, ...]],
    n: int,
    n_channels: int = 1,
) -> np.ndarray:
    """Unicorn dens fill ``0x101ec10a…0x101ec1d6`` with synthetic curve rows."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    _map_fill_deps(uc, dll)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(HEAP_ADDR, HEAP_SIZE)
    n_segs = len(knots)
    impl = HEAP_ADDR + 0x10000
    results = HEAP_ADDR + 0x11000
    dens = HEAP_ADDR + 0x12000
    curve_inner = HEAP_ADDR + 0x13000
    rows_ptr = HEAP_ADDR + 0x14000
    row_data = HEAP_ADDR + 0x15000
    uc.mem_write(dens, b"\x00" * (n * n_channels * 4 + 64))
    uc.mem_write(results + 0x44, struct.pack("<I", n))
    uc.mem_write(results + 0x48, struct.pack("<I", n_channels))
    uc.mem_write(results + 0x4C, struct.pack("<I", dens))
    uc.mem_write(impl + 0x180, struct.pack("<I", results))
    for i, vals in enumerate(knots):
        rd = row_data + i * 0x80
        uc.mem_write(rd, struct.pack("<" + "f" * len(vals), *vals))
        uc.mem_write(rows_ptr + i * 4, struct.pack("<I", rd))
    uc.mem_write(curve_inner + 0x10, struct.pack("<I", n_segs))
    uc.mem_write(curve_inner + 0x14, struct.pack("<I", n_channels + 1))
    uc.mem_write(curve_inner + 0x18, struct.pack("<I", rows_ptr))
    ebp = STACK_ADDR + 0x9000
    uc.mem_write(ebp - 0x44, struct.pack("<II", 0x10577BC0, curve_inner))
    uc.mem_write(ebp - 0x34, struct.pack("<I", n))
    uc.mem_write(ebp - 0x38, struct.pack("<I", impl))
    uc.reg_write(UC_X86_REG_EBP, ebp)
    uc.reg_write(UC_X86_REG_ESP, ebp - 0x100)
    uc.reg_write(UC_X86_REG_EBX, impl + 0x180)
    uc.reg_write(UC_X86_REG_EDI, impl)
    try:
        uc.emu_start(
            VA_GET_RESULTS_FILL,
            VA_GET_RESULTS_FILL_END,
            timeout=10_000_000,
            count=200_000,
        )
    except UcError:
        pass
    raw = uc.mem_read(dens, n * n_channels * 4)
    return np.frombuffer(bytes(raw), dtype=np.float32).reshape(n_channels, n)


def _sx32(v: int) -> int:
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


def run_baddscene_pack(
    dll: bytes, word_54: int, word_58: int, word_5c: int
) -> tuple[int, int, int]:
    """Unicorn bAddScene pack ``0x100022e6…0x10002309`` → ``ebp-0x38``."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    _map_text(uc, dll)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(HEAP_ADDR, HEAP_SIZE)
    desc = HEAP_ADDR + 0x1000
    uc.mem_write(desc + 0x54, struct.pack("<h", int(word_54)))
    uc.mem_write(desc + 0x58, struct.pack("<h", int(word_58)))
    uc.mem_write(desc + 0x5C, struct.pack("<h", int(word_5c)))
    ebp = STACK_ADDR + 0x8000
    uc.reg_write(UC_X86_REG_EBP, ebp)
    uc.reg_write(UC_X86_REG_EDI, desc)
    uc.reg_write(UC_X86_REG_ESP, ebp - 0x100)
    try:
        uc.emu_start(
            VA_BADDSCENE_PACK,
            VA_BADDSCENE_PACK_END,
            timeout=100_000,
            count=40,
        )
    except UcError:
        pass
    return struct.unpack("<hhh", uc.mem_read(ebp - 0x38, 6))


def run_ane_hist_slot(
    dll: bytes,
    pixel: int,
    offset: int,
    divisor: int,
    max_bin: int,
    plane_stride: int,
    plane: int,
) -> int:
    """Unicorn Ane analyze bin/slot leaf ``0x102a8555…0x102a857c``."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    _map_text(uc, dll)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(HEAP_ADDR, HEAP_SIZE)
    obj = HEAP_ADDR + 0x1000
    uc.mem_write(obj + ane.ANE_OBJ_PIXEL_OFFSET_OFF, struct.pack("<i", int(offset)))
    uc.mem_write(obj + ane.ANE_OBJ_BIN_DIVISOR_OFF, struct.pack("<i", int(divisor)))
    uc.mem_write(obj + ane.ANE_OBJ_PLANE_STRIDE_OFF, struct.pack("<i", int(plane_stride)))
    uc.mem_write(obj + ane.ANE_OBJ_BIN_MAX_OFF, struct.pack("<i", int(max_bin)))
    esp = STACK_ADDR + 0x8000
    dummy = HEAP_ADDR + 0x2000
    uc.mem_write(esp + 0x2C, struct.pack("<I", dummy))
    uc.mem_write(dummy, struct.pack("<II", 0, 0))
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_EDI, obj)
    uc.reg_write(UC_X86_REG_EBP, int(plane) & 0xFFFFFFFF)
    uc.reg_write(UC_X86_REG_EAX, int(pixel) & 0xFFFFFFFF)
    uc.reg_write(UC_X86_REG_EDX, int(offset) & 0xFFFFFFFF)
    try:
        uc.emu_start(
            VA_ANE_BIN_INDEX,
            VA_ANE_BIN_INDEX_END,
            timeout=100_000,
            count=40,
        )
    except UcError:
        pass
    return int(uc.reg_read(UC_X86_REG_ESI)) & 0xFFFFFFFF


def run_ane_dens_hist_accum(
    dll: bytes,
    value: int,
    *,
    offset: float,
    divisor: float,
    n: int,
    seed_bins: list[int] | None = None,
) -> tuple[int, list[int]]:
    """Unicorn dens-hist ``inc`` leaf ``0x104f56e0…`` → (bin, bins)."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    _map_text(uc, dll)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(HEAP_ADDR, HEAP_SIZE)
    hist = HEAP_ADDR + 0x1000
    bins_addr = HEAP_ADDR + 0x2000
    bins0 = list(seed_bins) if seed_bins is not None else [0] * int(n)
    if len(bins0) < int(n):
        raise ValueError("seed_bins shorter than n")
    raw = b"".join(struct.pack("<i", int(x)) for x in bins0[:n])
    uc.mem_write(bins_addr, raw)
    uc.mem_write(hist + ane.ANE_HIST_N_OFF, struct.pack("<i", int(n)))
    uc.mem_write(hist + ane.ANE_HIST_OFFSET_OFF, struct.pack("<d", float(offset)))
    uc.mem_write(hist + ane.ANE_HIST_DIVISOR_OFF, struct.pack("<d", float(divisor)))
    uc.mem_write(hist + ane.ANE_HIST_BINS_OFF, struct.pack("<I", bins_addr))
    esp = STACK_ADDR + 0x8000
    # cdecl: [esp]=ret, [esp+4]=value; leaf does ret 4.
    ret_addr = STACK_ADDR + 0x100
    uc.mem_write(ret_addr, b"\xcc")
    uc.mem_write(esp, struct.pack("<Ii", ret_addr, int(value)))
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_ECX, hist)
    try:
        uc.emu_start(
            VA_ANE_HIST_ACCUM,
            VA_ANE_HIST_ACCUM_END,
            timeout=1_000_000,
            count=200,
        )
    except UcError:
        pass
    out = list(struct.unpack(f"<{n}i", uc.mem_read(bins_addr, n * 4)))
    # Recover bin as the index that increased (or host formula on tie).
    host_bin = ane.ane_dens_hist_bin(value, offset, divisor, n)
    return host_bin, out


def run_tla_find_dmin_walk(
    tla: bytes, counts: list[int], thr: int
) -> int:
    """Unicorn FindDmin high-side walk ``0x100093f0…`` → dword code."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    _map_tla_text(uc, tla)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(HEAP_ADDR, HEAP_SIZE)
    hist = HEAP_ADDR + 0x1000
    out = HEAP_ADDR + 0x20000
    n = sc.TLA_FIND_DMIN_N_BINS
    raw = b"".join(struct.pack("<i", int(c)) for c in counts[:n])
    if len(raw) < n * 4:
        raw += b"\x00" * (n * 4 - len(raw))
    uc.mem_write(hist, raw)
    uc.mem_write(out, b"\x00" * 16)
    esp = STACK_ADDR + 0x8000
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.mem_write(esp + 0x30, struct.pack("<I", int(thr) & 0xFFFFFFFF))
    uc.mem_write(esp + 0x1C, struct.pack("<I", out))
    uc.reg_write(UC_X86_REG_EBX, hist)
    try:
        uc.emu_start(
            VA_TLA_FIND_DMIN_WALK,
            VA_TLA_FIND_DMIN_WALK_END,
            timeout=5_000_000,
            count=500_000,
        )
    except UcError:
        pass
    return int(struct.unpack("<I", uc.mem_read(out, 4))[0])


def run_tla_desc_pack(
    tla: bytes, case: int, r: int, g: int, b: int
) -> tuple[int, int, int, int]:
    """Unicorn TLA AddScene desc pack ``0x1003f901…`` → case + RGB words."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    _map_tla_text(uc, tla)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    esp = STACK_ADDR + 0x7000
    # Locals relative to esp at leaf entry (cite 0x1003f901).
    uc.mem_write(esp + 0x14, struct.pack("<I", int(case) & 0xFFFFFFFF))
    uc.mem_write(esp + 0x34, struct.pack("<H", int(r) & 0xFFFF))
    uc.mem_write(esp + 0x3C, struct.pack("<H", int(g) & 0xFFFF))
    uc.mem_write(esp + 0x44, struct.pack("<H", int(b) & 0xFFFF))
    # Desc buffer at esp+0x68 — leaf zeros 0x68 bytes then stores.
    uc.mem_write(esp + 0x68, b"\xcc" * sc.DESC_BYTES)
    uc.reg_write(UC_X86_REG_ESP, esp)
    # ebx used after stores for vtable call; leaf end is before call.
    uc.reg_write(UC_X86_REG_EBX, HEAP_ADDR)  # unused before END
    try:
        uc.mem_map(HEAP_ADDR, 0x1000)
    except UcError:
        pass
    try:
        uc.emu_start(
            VA_TLA_DESC_PACK,
            VA_TLA_DESC_PACK_END,
            timeout=100_000,
            count=80,
        )
    except UcError:
        pass
    desc = uc.mem_read(esp + 0x68, sc.DESC_BYTES)
    case_out = struct.unpack_from("<I", desc, sc.DESC_DMIN_CASE_OFF)[0]
    rgb = sc.addscene_desc_dmin_rgb(desc)
    return int(case_out), rgb[0], rgb[1], rgb[2]


def main() -> int:
    dll_path = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IMAU)
    tla_path = Path(sys.argv[2] if len(sys.argv) > 2 else DEFAULT_TLA)
    dll = _load_dll(dll_path)
    tla = _load_dll(tla_path)
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

    # ScpLut dmin remap leaf (0x100fd984)
    lut = [i + 1000 for i in range(400)]
    for stride, rgb in [(100, (5, 6, 7)), (64, (1, 2, 3)), (0, (10, 20, 30))]:
        host = sc.scplut_remap_dmin_rgb(lut, stride, *rgb)
        ref = run_scplut_remap(dll, lut, stride, *rgb)
        ok = host == ref
        print(
            f"  scplut_remap stride={stride} {rgb}: host={host} dll={ref} "
            f"{'OK' if ok else 'FAIL'}"
        )
        if not ok:
            fail += 1

    # getResults dens fill (0x101ec10a) — synthetic curve knots
    fill_cases: list[tuple[list[tuple[float, ...]], int, int]] = [
        ([(0.0, 1.0), (10.0, 1.0), (20.0, 11.0)], 20, 1),
        ([(5.0, 2.0), (15.0, 12.0)], 20, 1),
        ([(0.0, 1.0, 2.0), (8.0, 1.0, 4.0), (16.0, 9.0, 10.0)], 16, 2),
    ]
    for knots, n, ch in fill_cases:
        host = ane.get_results_fill_dens(knots, n, ch)
        ref = run_get_results_fill(dll, knots, n, ch)
        ok = np.allclose(host, ref, rtol=0, atol=1e-5)
        print(
            f"  dens_fill n={n} ch={ch} knots={len(knots)}: "
            f"maxdiff={float(np.max(np.abs(host - ref))):.3g} "
            f"{'OK' if ok else 'FAIL'}"
        )
        if not ok:
            fail += 1

    # Compose: remapped dmin → bag → mid-aim with filled dens
    remapped = sc.scplut_remap_dmin_rgb(lut, 100, 5, 6, 7)
    bag2 = sc.SceneContextBag()
    bag2.insert_dmin(remapped)
    nt2 = ane.noise_table_from_knots([(5.0, 2.0), (15.0, 12.0)], 20, 1)
    m2 = shasta.cn_premium_mid_aim_from_bag(bag2, nt2, (0, 0, 0))
    ok = m2 is not None
    print(
        f"  mid_aim from ScpLut+fill: dmin={remapped} mids={m2} "
        f"{'OK' if ok else 'FAIL'}"
    )
    if not ok:
        fail += 1

    # bAddScene dmin pack (0x100022e6) + case table
    for case, expect_pack in [(0, False), (1, True), (2, True), (3, True), (4, False)]:
        got = sc.baddscene_case_packs_dmin(case)
        ok = got is expect_pack
        print(f"  bAddScene case {case} packs_dmin={got} {'OK' if ok else 'FAIL'}")
        if not ok:
            fail += 1
    for rgb in [(100, 200, 300), (-1, 0, 1), (0x7FFF, -0x8000, 42)]:
        host = sc.unpack_dmin_rgb(sc.baddscene_pack_dmin_from_desc(*rgb))
        ref = run_baddscene_pack(dll, *rgb)
        ok = host == ref
        print(
            f"  bAddScene pack {rgb}: host={host} dll={ref} "
            f"{'OK' if ok else 'FAIL'}"
        )
        if not ok:
            fail += 1

    # AneOrder analyze bin-index / hist slot (0x102a8555)
    bin_cases = [
        (100, 0, 1, 255, 256, 0),
        (100, 50, 2, 100, 128, 1),
        (10, 50, 2, 100, 128, 2),
        (1000, 0, 3, 50, 64, 0),
        (-20, 0, 2, 10, 16, 0),
        (7, 0, 3, 10, 16, 1),
    ]
    for c in bin_cases:
        host = ane.ane_hist_slot(*c)
        ref = run_ane_hist_slot(dll, *c)
        ok = host == ref
        print(
            f"  ane_hist_slot {c}: host={host} dll={ref} "
            f"{'OK' if ok else 'FAIL'}"
        )
        if not ok:
            fail += 1

    # Ane dens-hist accum inc leaf (0x104f56e0)
    hist_cases = [
        (25, 5.0, 2.0, 16),
        (0, 0.0, 1.0, 8),
        (-10, 0.0, 2.0, 8),
        (100, 10.0, 3.0, 16),
        (7, 0.5, 1.5, 10),
    ]
    for value, off, div, n in hist_cases:
        host_bins = [0] * n
        host_bin = ane.ane_dens_hist_accum(
            host_bins, value, offset=off, divisor=div, n=n
        )
        _bin, dll_bins = run_ane_dens_hist_accum(
            dll, value, offset=off, divisor=div, n=n
        )
        ok = host_bins == dll_bins and host_bin == ane.ane_dens_hist_bin(
            value, off, div, n
        )
        print(
            f"  ane_dens_hist value={value} off={off} div={div}: "
            f"bin={host_bin} host={host_bins} dll={dll_bins} "
            f"{'OK' if ok else 'FAIL'}"
        )
        if not ok:
            fail += 1

    # TLA AddScene desc pack (0x1003f901) + getCnContext bag load
    for case, rgb in [
        (1, (100, 200, 300)),
        (2, (0, 0, 0)),
        (3, (-1, 42, 0x7FFF)),
    ]:
        host = sc.addscene_pack_desc(case, *rgb)
        host_t = (
            struct.unpack_from("<I", host, sc.DESC_DMIN_CASE_OFF)[0],
            *sc.addscene_desc_dmin_rgb(host),
        )
        ref = run_tla_desc_pack(tla, case, *rgb)
        ok = host_t == ref
        print(
            f"  tla_desc_pack case={case} {rgb}: host={host_t} dll={ref} "
            f"{'OK' if ok else 'FAIL'}"
        )
        if not ok:
            fail += 1
        # Compose: desc → bAddScene pack → bag → getCnContext path load
        blob = sc.baddscene_pack_dmin_from_desc(*sc.addscene_desc_dmin_rgb(host))
        bag3 = sc.SceneContextBag()
        bag3.insert("dmin", blob)
        path_rgb = sc.getcncontext_path_dmin_from_bag(bag3)
        ok = path_rgb == rgb
        print(
            f"  getCnContext path from desc {rgb}: {path_rgb} "
            f"{'OK' if ok else 'FAIL'}"
        )
        if not ok:
            fail += 1
    empty = sc.SceneContextBag()
    z = sc.getcncontext_path_dmin_from_bag(empty)
    ok = z == (0, 0, 0)
    print(f"  getCnContext empty → zero: {z} {'OK' if ok else 'FAIL'}")
    if not ok:
        fail += 1

    # TLA FindDmin high-side hist walk (frame +0x6cac producer leaf)
    for thr, peak, peak_count in [
        (3, 1000, 5),
        (10, 5000, 20),
        (1, 0x3FFF, 100),
        (5, 100, 10),
        (0, 50, 1),
    ]:
        counts = [0] * sc.TLA_FIND_DMIN_N_BINS
        counts[peak] = peak_count
        if peak < sc.TLA_FIND_DMIN_CODE_MAX - 1:
            counts[peak + 10] = 1
        host = sc.find_dmin_code_from_hist(counts, thr)
        ref = run_tla_find_dmin_walk(tla, counts, thr)
        ok = host == ref
        print(
            f"  find_dmin_walk thr={thr} peak={peak}: host={host} dll={ref} "
            f"{'OK' if ok else 'FAIL'}"
        )
        if not ok:
            fail += 1
    for n in (0, 999, 1000, 10000, 3097440):
        host = sc.find_dmin_thr_n_pixels(n)
        expect = n // 1000
        ok = host == expect
        print(f"  find_dmin_thr n={n}: {host} (expect {expect}) {'OK' if ok else 'FAIL'}")
        if not ok:
            fail += 1
    # Compose: samples → frame RGB → seed → (optional) ColNeg 1px
    planes = (
        [100] * 500 + [8000] * 500,
        [200] * 500 + [9000] * 500,
        [300] * 500 + [10000] * 500,
    )
    frame_rgb = sc.frame_dmin_rgb_from_planes(*planes)
    seeded = sc.addscene_seed_from_frame_dmin(*frame_rgb)
    ok = seeded == frame_rgb and all(0 <= c <= 0x3FFF for c in frame_rgb)
    print(f"  frame_dmin_rgb from planes: {frame_rgb} {'OK' if ok else 'FAIL'}")
    if not ok:
        fail += 1
    ok = sc.addscene_film_uses_colrev(0) is False and sc.addscene_film_uses_colrev(2) is True
    print(f"  film bit2 ColRev dispatch: {'OK' if ok else 'FAIL'}")
    if not ok:
        fail += 1
    color_dir = Path(DEFAULT_COLOR_DIR)
    lut_path = color_dir / "_ClientColNegLut.txt"
    mat_path = color_dir / "_ClientColNegMat.txt"
    if lut_path.is_file() and mat_path.is_file():
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import pakon_color as pc  # noqa: E402

        lut = [float(int(v)) for v in pc.load_vendor_lut(str(lut_path))]
        coeff, offset = pc.quantise_matrix(pc.load_vendor_matrix(str(mat_path)))
        remapped = sc.addscene_colneg_remap_dmin_rgb(*seeded, lut, coeff, offset)
        expect = pc.render_pixel(seeded, lut, coeff, offset)
        ok = remapped == expect
        print(
            f"  colneg_1px remap {seeded} → {remapped} (pakon_color={expect}) "
            f"{'OK' if ok else 'FAIL'}"
        )
        if not ok:
            fail += 1
        # ColRev bit skips host ColNeg remap (extra ColRev stages open)
        skipped = sc.addscene_dmin_rgb_from_frame(
            *frame_rgb, film_flags=2, lut=lut, coeff=coeff, offset=offset
        )
        ok = skipped == seeded
        print(f"  colrev bit skips ColNeg remap: {skipped} {'OK' if ok else 'FAIL'}")
        if not ok:
            fail += 1
        # Full seed→ColNeg→desc pack compose
        desc = sc.addscene_pack_desc(2, *remapped)
        ok = sc.addscene_desc_dmin_rgb(desc) == tuple(int(x) & 0xFFFF for x in remapped)
        print(f"  frame→ColNeg→desc pack: {sc.addscene_desc_dmin_rgb(desc)} {'OK' if ok else 'FAIL'}")
        if not ok:
            fail += 1
    else:
        print(f"  colneg_1px remap: SKIP (no ColorCorrection at {color_dir})")

    print(
        f"  SHASTA_AIM_AVG2_PORTED={shasta.SHASTA_AIM_AVG2_PORTED} "
        f"MID_RGB={shasta.SHASTA_AIM_MID_RGB_PORTED} "
        f"INPUT_PATH={shasta.SHASTA_AIM_INPUT_PATH_PORTED} "
        f"ANALYZE={shasta.SHASTA_ANALYZE_PORTED} "
        f"TONE_LUT={shasta.SHASTA_TONE_LUT_PORTED} "
        f"SCENE_DMIN={sc.SCENE_CONTEXT_DMIN_PORTED} "
        f"SCPLUT_REMAP={sc.SCPLUT_DMIN_REMAP_PORTED} "
        f"BADDSCENE_PACK={sc.BADDSCENE_DMIN_PACK_PORTED} "
        f"ADDSCENE_DESC={sc.ADDSCENE_DESC_PACK_PORTED} "
        f"PATH_FROM_BAG={sc.PATH_DMIN_FROM_BAG_PORTED} "
        f"FRAME_DMIN={sc.FRAME_DMIN_RGB_PORTED} "
        f"COLNEG_REMAP={sc.ADDSCENE_COLNEG_REMAP_PORTED} "
        f"NOISE_LAYOUT={ane.ANE_NOISE_TABLE_LAYOUT_PORTED} "
        f"GET_RESULTS_FILL={ane.ANE_GET_RESULTS_FILL_PORTED} "
        f"ANE_BIN_INDEX={ane.ANE_ANALYZE_BIN_INDEX_PORTED} "
        f"ANE_HIST_ACCUM={ane.ANE_ANALYZE_HIST_ACCUM_PORTED} "
        f"ANE_ORDER={ane.ANE_ORDER_PORTED}"
    )
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
