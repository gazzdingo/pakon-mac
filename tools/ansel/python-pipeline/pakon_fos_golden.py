#!/usr/bin/env python3
"""Golden FOS dens leaves vs PakonIMAu.dll (Unicorn).

Leaves (all in PakonIMAu.dll, base ``0x10000000``)
--------------------------------------------------
* R² @ ``0x10290332`` — injected Σ/P → ``gmRSquare``/``illRSquare``
* orderAvg @ ``0x10290290`` — open RGB + mean dens → ``fosOrderAvg``
* slopes+offsets @ ``0x10290216`` — unit eigen on FPU + means + open
  → ``fosOrderAvg`` + ``gmSlope``/``gmOffset``/``illSlope``/``illOffset``
* RGB max-eigen @ ``0x1028fe61`` → ``0x102901e0`` — Σ/P → unit ``(dR,dG,dB)``
  (IAT ``_CIacos`` stubbed)
* dens paxel @ ``0x1028f9a8`` → ``0x1028fccc`` — fake planes → frame Σ/P

Usage
-----
``PYTHONPATH=tools/ansel python3 tools/ansel/pakon_fos_golden.py [dll]``
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_EBX,
    UC_X86_REG_EBP,
    UC_X86_REG_EDI,
    UC_X86_REG_EDX,
    UC_X86_REG_ESI,
    UC_X86_REG_ESP,
)

import pakon_fos as fos

IMAGE_BASE = 0x10000000  # PakonIMAu.dll preferred load base
STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x100000
STUB_ADDR = 0x0BE00000

DEFAULT_DLL = Path(
    "/Users/guy/Downloads/Pakon Update 3/fx35install/program files/"
    "Pakon/F-X35 COM SERVER/PakonIMAu.dll"
)

# (N, ΣU, ΣV, ΣW, P_UV, P_UW, P_UU, P_VV, P_WW) — slots at PakonIMAu.dll @ 0x10290332
RSQUARE_CASES: list[tuple[int, ...]] = [
    (100, 1000, 2000, 1500, 24000, 18000, 12000, 48000, 27000),
    (50, 100, 80, 60, 200, 150, 300, 250, 200),
    (10, 5, -3, 2, 1, 0, 4, 3, 2),
    (200, 0, 0, 0, 0, 0, 1, 1, 1),
    (25, -40, 30, -10, -50, 20, 80, 90, 60),
]

# (open_rgb, mean_dens) — ESP +0x114… / +0xa8… at PakonIMAu.dll @ 0x10290290
ORDER_AVG_CASES: list[tuple[tuple[int, int, int], tuple[float, float, float]]] = [
    ((1000, 1100, 900), (12.5, -3.25, 8.0)),
    ((0, 0, 0), (0.0, 0.0, 0.0)),
    ((-50, 20, 100), (1.9, -0.7, 2.4)),
    ((5000, -200, 300), (-10.9, 0.1, 99.99)),
]

# (eigen_rgb, mean_dens, open_rgb) — FPU + means → PakonIMAu.dll @ 0x10290216
SLOPE_CASES: list[
    tuple[tuple[float, float, float], tuple[float, float, float], tuple[int, int, int]]
] = [
    ((0.8, 0.4, 0.2), (10.0, 20.0, 15.0), (1000, 1100, 900)),
    ((-0.6, 0.5, 0.3), (5.0, -2.0, 1.0), (200, 250, 180)),
    ((0.0, 0.707106781, 0.707106781), (100.0, 100.0, 100.0), (0, 0, 0)),
    ((0.577350269, 0.577350269, 0.577350269), (1.5, 2.5, 3.5), (-10, 0, 10)),
]

# (N, ΣR, ΣG, ΣB, P_RG, P_RB, P_GB, P_RR, P_GG, P_BB) — PakonIMAu.dll @ 0x1028fe61
EIGEN_CASES: list[tuple[int, ...]] = [
    (100, 1000, 2000, 1500, 24000, 18000, 27000, 12000, 48000, 27000),
    (50, 100, 80, 60, 200, 150, 180, 300, 250, 200),
    (200, 10, -5, 8, 20, -10, 5, 80, 90, 70),
    (25, -40, 30, -10, -50, 20, -15, 80, 90, 60),
]


def _make_paxel_case_uniform(
    *,
    dens_fill: int,
    mask_ones: bool,
    open_rgb: tuple[int, int, int],
    delta: tuple[int, int],
    radius_sq: int,
) -> tuple[str, list[int], bytearray, tuple[int, int, int], tuple[int, int], int]:
    dens, mask = fos.fos_paxel_fake_planes(fill=dens_fill)
    if mask_ones:
        for i in fos.fos_paxel_indices():
            mask[i] = 1
    return ("uniform", dens, mask, open_rgb, delta, radius_sq)


def _make_paxel_case_sparse() -> tuple[
    str, list[int], bytearray, tuple[int, int, int], tuple[int, int], int
]:
    """Few masked pixels with distinct plane values — PakonIMAu.dll walk stress."""
    dens, mask = fos.fos_paxel_fake_planes(fill=0)
    open_rgb = (100, 200, 150)
    idxs = fos.fos_paxel_indices()
    for k, i in enumerate(idxs[::50]):  # every 50th candidate
        mask[i] = 1
        dens[i + fos.PAXEL_OFF_R] = 300 + k
        dens[i + fos.PAXEL_OFF_G] = 400 + k
        dens[i + fos.PAXEL_OFF_B] = 250 + k
        dens[i + fos.PAXEL_OFF_U] = 260 + k  # U plane
        dens[i + fos.PAXEL_OFF_V] = 210 + k
        dens[i + fos.PAXEL_OFF_W] = 160 + k
    return ("sparse", dens, mask, open_rgb, (0, 0), 0x7FFFFFFF)


PAXEL_CASES = [
    _make_paxel_case_uniform(
        dens_fill=0x120,
        mask_ones=True,
        open_rgb=(1000, 1100, 900),
        delta=(0, 0),
        radius_sq=0x7FFFFFFF,
    ),
    _make_paxel_case_uniform(
        dens_fill=0x80,
        mask_ones=False,  # N=0
        open_rgb=(500, 500, 500),
        delta=(0, 0),
        radius_sq=0x7FFFFFFF,
    ),
    _make_paxel_case_sparse(),
    _make_paxel_case_uniform(
        dens_fill=0x200,
        mask_ones=True,
        open_rgb=(100, 100, 100),
        delta=(50, -50),
        radius_sq=100,  # tight radius — few accepts
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


def _hook_stop(stop: int):
    def hook(u: Uc, address: int, size: int, _user: object) -> None:
        if address == stop:
            u.emu_stop()

    return hook


def run_idiv_leaf(pe: bytes, numer: int, denom: int) -> int:
    """PakonIMAu.dll @ ``0x102b7669`` ``cdq; idiv ebp`` — eax = trunc quot."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, pe)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    esp = STACK_ADDR + 0x70000
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_EAX, int(numer) & 0xFFFFFFFF)
    uc.reg_write(UC_X86_REG_EBP, int(fos._i16(denom)) & 0xFFFFFFFF)  # noqa: SLF001
    # PakonIMAu.dll @ 0x102b7669 cdq; @ 0x102b766a idiv ebp; next insn @ 0x102b766c
    stop = 0x102B766C
    uc.hook_add(UC_HOOK_CODE, _hook_stop(stop), begin=stop, end=stop + 1)
    try:
        uc.emu_start(fos.POSTFILL_IDIV, 0, timeout=5_000_000)
    except UcError as e:
        raise RuntimeError(f"unicorn idiv leaf: {e}") from e
    return struct.unpack("<i", struct.pack("<I", uc.reg_read(UC_X86_REG_EAX)))[0]


def run_helper_leaf(
    pe: bytes,
    frames: list[fos.FosHelperFrame],
    *,
    dc_gate: int,
    dc_radius: int,
    dc_w_gm: int,
    dc_w_ill: int,
    dc_thresh_n: int,
    dmin_open_r: int,
    dmin_open_c1: int,
    dmin_open_c2: int,
    wtab_enable: int = 0,
    wtab: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> fos.FosHelperResult:
    """PakonIMAu.dll helper @ ``0x1028f250`` — inject frames → Δ + ofpoMethod."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, pe)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    heap = STACK_ADDR + 0x80000
    # Layout on heap: arrays, objects, dc, wtab, dminOpen, Δ out, ofpo
    n = len(frames)
    arr388 = heap
    arr290 = heap + 0x100
    objs = heap + 0x200
    dc = heap + 0x8000
    wtab_p = heap + 0x8100
    dmin = heap + 0x8200
    delta_out = heap + 0x8300
    ofpo_out = heap + 0x8400

    uc.mem_write(heap, b"\0" * 0x9000)
    # Pack frame objects (388c small + 290c large)
    for i, fr in enumerate(frames):
        o388 = objs + i * 0x20
        o290 = objs + 0x1000 + i * 0x1000
        uc.mem_write(arr388 + i * 4, struct.pack("<I", o388))
        uc.mem_write(arr290 + i * 4, struct.pack("<I", o290))
        uc.mem_write(o388 + fos.OBJ290C_OFF_FID, bytes([1 if fr.skip_fiduciary else 0]))
        uc.mem_write(o290 + fos.OUT290C_OFF_C1, struct.pack("<i", int(fr.c1_lo)))
        uc.mem_write(o290 + fos.OUT290C_OFF_C2, struct.pack("<i", int(fr.c2_lo)))
        uc.mem_write(o290 + fos.OUT290C_OFF_C1_HI, struct.pack("<i", int(fr.c1_hi)))
        uc.mem_write(o290 + fos.OUT290C_OFF_C2_HI, struct.pack("<i", int(fr.c2_hi)))
        uc.mem_write(o290 + fos.OUT290C_OFF_GATE, struct.pack("<i", int(fr.gate_9cc)))

    uc.mem_write(dc + fos.DC_OFF_GATE, struct.pack("<h", int(dc_gate)))
    uc.mem_write(dc + fos.DC_OFF_W_GM, struct.pack("<h", int(dc_w_gm)))
    uc.mem_write(dc + fos.DC_OFF_W_ILL, struct.pack("<h", int(dc_w_ill)))
    uc.mem_write(dc + fos.DC_OFF_RADIUS, struct.pack("<h", int(dc_radius)))
    uc.mem_write(dc + fos.DC_OFF_THRESH_N, struct.pack("<h", int(dc_thresh_n)))
    lo, mid, mid_w, hi_w = wtab
    uc.mem_write(wtab_p + fos.WTAB_OFF_LO, struct.pack("<h", int(lo)))
    uc.mem_write(wtab_p + fos.WTAB_OFF_MID, struct.pack("<h", int(mid)))
    uc.mem_write(wtab_p + fos.WTAB_OFF_MID_W, struct.pack("<h", int(mid_w)))
    uc.mem_write(wtab_p + fos.WTAB_OFF_HI_W, struct.pack("<h", int(hi_w)))
    uc.mem_write(wtab_p + fos.WTAB_OFF_ENABLE, struct.pack("<h", int(wtab_enable)))
    uc.mem_write(dmin + fos.DMIN_OPEN_OFF_R, struct.pack("<i", int(dmin_open_r)))
    uc.mem_write(dmin + fos.DMIN_OPEN_OFF_C1, struct.pack("<i", int(dmin_open_c1)))
    uc.mem_write(dmin + fos.DMIN_OPEN_OFF_C2, struct.pack("<i", int(dmin_open_c2)))
    uc.mem_write(delta_out, b"\0" * 12)
    uc.mem_write(ofpo_out, b"\0\0")

    esp = STACK_ADDR + 0x70000
    # cdecl push arg8…arg0 then call — set stack as at function entry (ret already "pushed")
    # [esp]=ret, [esp+4]=arg0 …
    ret_addr = STUB_ADDR
    uc.mem_map(STUB_ADDR, 0x1000)
    uc.mem_write(STUB_ADDR, b"\xcc")  # int3
    args = [
        arr290,  # arg0 = 290c array — PakonIMAu.dll
        arr388,  # arg1 = 388c array
        dc,  # arg2
        wtab_p,  # arg3
        0,  # arg4 unused
        n,  # arg5
        dmin,  # arg6
        delta_out,  # arg7
        ofpo_out,  # arg8
    ]
    raw = struct.pack("<I", ret_addr) + struct.pack("<" + "I" * 9, *args)
    uc.mem_write(esp, raw)
    uc.reg_write(UC_X86_REG_ESP, esp)

    def hook_ret(u: Uc, address: int, size: int, _user: object) -> None:
        if address == STUB_ADDR:
            u.emu_stop()

    uc.hook_add(UC_HOOK_CODE, hook_ret, begin=STUB_ADDR, end=STUB_ADDR + 1)
    try:
        uc.emu_start(fos.HELPER_ORDER_FPO, 0, timeout=80_000_000)
    except UcError as e:
        raise RuntimeError(f"unicorn helper leaf: {e}") from e

    eax = struct.unpack("<i", struct.pack("<I", uc.reg_read(UC_X86_REG_EAX)))[0]
    d0, d1, d2 = struct.unpack("<iii", bytes(uc.mem_read(delta_out, 12)))
    ofpo = struct.unpack("<h", bytes(uc.mem_read(ofpo_out, 2)))[0]
    return fos.FosHelperResult(eax=eax, delta=(d0, d1, d2), ofpo_method=ofpo)


def run_rsquare_leaf(
    pe: bytes,
    n: int,
    sum_u: int,
    sum_v: int,
    sum_w: int,
    p_uv: int,
    p_uw: int,
    p_uu: int,
    p_vv: int,
    p_ww: int,
) -> tuple[int, int, int]:
    """Inject ESP slots and run ``0x10290332`` → after illRSquare store."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, pe)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    esp = STACK_ADDR + 0x70000
    out = STACK_ADDR + 0x90000
    uc.mem_write(out, b"\0" * fos.FOS_RESULTS_SIZE)

    def put_i32(off: int, val: int) -> None:
        uc.mem_write(esp + off, struct.pack("<i", int(val)))

    put_i32(0x50, n)  # PakonIMAu.dll ESP+0x50 = N
    put_i32(0x54, sum_u)  # PakonIMAu.dll ESP+0x54 = ΣU
    put_i32(0x58, sum_v)  # PakonIMAu.dll ESP+0x58 = ΣV
    put_i32(0x5C, sum_w)  # PakonIMAu.dll ESP+0x5c = ΣW
    put_i32(0x60, p_uu)  # PakonIMAu.dll ESP+0x60 = P_UU
    put_i32(0x64, p_uv)  # PakonIMAu.dll ESP+0x64 = P_UV
    put_i32(0x68, p_uw)  # PakonIMAu.dll ESP+0x68 = P_UW
    put_i32(0x90, p_vv)  # PakonIMAu.dll ESP+0x90 = P_VV
    put_i32(0x94, p_ww)  # PakonIMAu.dll ESP+0x94 = P_WW
    uc.mem_write(esp + 0x28, struct.pack("<d", float(n)))  # PakonIMAu.dll ESP+0x28 N as f64

    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_ESI, out)  # PakonIMAu.dll esi = OUT (SbaFOSResults)
    uc.reg_write(UC_X86_REG_EDI, int(n))

    stop = 0x102903F0  # PakonIMAu.dll after illRSquare store
    uc.hook_add(UC_HOOK_CODE, _hook_stop(stop), begin=stop, end=stop + 1)
    try:
        uc.emu_start(fos.RSQUARE_ENTRY, 0, timeout=80_000_000)  # PakonIMAu.dll @ 0x10290332
    except UcError as e:
        raise RuntimeError(f"unicorn R² leaf: {e}") from e

    gm = struct.unpack("<h", bytes(uc.mem_read(out + fos.FOS_OFF_GM_RSQUARE, 2)))[0]
    ill = struct.unpack("<h", bytes(uc.mem_read(out + fos.FOS_OFF_ILL_RSQUARE, 2)))[0]
    npix = struct.unpack("<h", bytes(uc.mem_read(out + fos.FOS_OFF_NUM_PIXELS, 2)))[0]
    return gm, ill, npix


def run_order_avg_leaf(
    pe: bytes,
    open_rgb: tuple[int, int, int],
    mean_dens: tuple[float, float, float],
) -> tuple[int, int, int]:
    """Enter PakonIMAu.dll @ ``0x10290290``; stop after last ``fosOrderAvg`` store."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, pe)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    esp = STACK_ADDR + 0x70000
    out = STACK_ADDR + 0x90000
    uc.mem_write(out, b"\0" * fos.FOS_RESULTS_SIZE)

    for off, val in zip((0x114, 0x118, 0x11C), open_rgb):  # PakonIMAu.dll open R/G/B
        uc.mem_write(esp + off, struct.pack("<i", int(val)))
    for off, val in zip((0xA8, 0xB0, 0xB8), mean_dens):  # PakonIMAu.dll mean dens R/G/B
        uc.mem_write(esp + off, struct.pack("<d", float(val)))

    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_ESI, out)

    # PakonIMAu.dll after mov word [esi+0xa], ax @ 0x102902de
    stop = 0x102902E2
    uc.hook_add(UC_HOOK_CODE, _hook_stop(stop), begin=stop, end=stop + 1)
    try:
        uc.emu_start(fos.ORDER_AVG_ENTRY, 0, timeout=80_000_000)  # PakonIMAu.dll @ 0x10290290
    except UcError as e:
        raise RuntimeError(f"unicorn orderAvg leaf: {e}") from e

    return struct.unpack("<hhh", bytes(uc.mem_read(out + fos.FOS_OFF_ORDER_AVG, 6)))


def run_slopes_offsets_leaf(
    pe: bytes,
    eigen_rgb: tuple[float, float, float],
    mean_dens: tuple[float, float, float],
    open_rgb: tuple[int, int, int],
) -> tuple[tuple[int, int, int], tuple[int, int, int, int]]:
    """Stub → PakonIMAu.dll @ ``0x10290216`` (fninit; fld dR; fld dB; fld dG).

    Applies host sign-flip (PakonIMAu.dll @ ``0x102901b3``) first so entry
    has ``d_R >= 0``.
    """
    dr, dg, db = fos.fos_fix_eigen_sign(*eigen_rgb)

    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, pe)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(STUB_ADDR, 0x1000)
    esp = STACK_ADDR + 0x70000
    out = STACK_ADDR + 0x90000
    floats = STACK_ADDR + 0x91000
    uc.mem_write(out, b"\0" * fos.FOS_RESULTS_SIZE)
    # Load order: fld dR; fld dB; fld dG → FPU st0=dG,st1=dB,st2=dR (PakonIMAu.dll entry)
    uc.mem_write(
        floats,
        struct.pack("<ddd", float(dr), float(db), float(dg)),
    )

    for off, val in zip((0x114, 0x118, 0x11C), open_rgb):
        uc.mem_write(esp + off, struct.pack("<i", int(val)))
    for off, val in zip((0xA8, 0xB0, 0xB8), mean_dens):
        uc.mem_write(esp + off, struct.pack("<d", float(val)))

    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_ESI, out)

    stub = bytearray()
    stub += b"\xDB\xE3"  # fninit
    for i in range(3):
        stub += b"\xDD\x05" + struct.pack("<I", floats + i * 8)  # fld qword
    rel = fos.SLOPES_OFFSETS_ENTRY - (STUB_ADDR + len(stub) + 5)  # PakonIMAu.dll @ 0x10290216
    stub += b"\xE9" + struct.pack("<i", rel)

    uc.mem_write(STUB_ADDR, bytes(stub))
    stop = 0x1029033A  # PakonIMAu.dll after illOffset mov [esi+0x18]
    uc.hook_add(UC_HOOK_CODE, _hook_stop(stop), begin=stop, end=stop + 1)
    try:
        uc.emu_start(STUB_ADDR, 0, timeout=80_000_000)
    except UcError as e:
        raise RuntimeError(f"unicorn slopes leaf: {e}") from e

    avg = struct.unpack("<hhh", bytes(uc.mem_read(out + fos.FOS_OFF_ORDER_AVG, 6)))
    slopes = struct.unpack(
        "<hhhh",
        bytes(uc.mem_read(out + fos.FOS_OFF_GM_SLOPE, 8)),
    )
    return avg, slopes


def _install_acos_stub(uc: Uc) -> None:
    """Patch PakonIMAu.dll IAT ``0x1057349c`` → host acos (CRT ``_CIacos`` ABI)."""
    scratch = STUB_ADDR + 0x800
    acos_stub = STUB_ADDR + 0x100
    # fstp [scratch]; fld [scratch]; ret — hook rewrites scratch with acos between
    stub = (
        b"\xDD\x1D" + struct.pack("<I", scratch)
        + b"\xDD\x05" + struct.pack("<I", scratch)
        + b"\xC3"
    )
    uc.mem_write(acos_stub, stub)
    uc.mem_write(fos.ACOS_IAT, struct.pack("<I", acos_stub))  # PakonIMAu.dll IAT

    def acos_hook(u: Uc, address: int, size: int, _user: object) -> None:
        if address == acos_stub + 6:  # after fstp, before fld
            import math

            x = struct.unpack("<d", bytes(u.mem_read(scratch, 8)))[0]
            x = max(-1.0, min(1.0, x))
            u.mem_write(scratch, struct.pack("<d", math.acos(x)))

    uc.hook_add(UC_HOOK_CODE, acos_hook, begin=acos_stub + 6, end=acos_stub + 7)


def run_eigen_leaf(pe: bytes, case: tuple[int, ...]) -> tuple[float, float, float]:
    """PakonIMAu.dll @ ``0x1028fe61`` → after sign @ ``0x102901e0``; dump FPU unit vector."""
    n, sr, sg, sb, prg, prb, pgb, prr, pgg, pbb = case
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, pe)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(STUB_ADDR, 0x1000)
    _install_acos_stub(uc)

    esp = STACK_ADDR + 0x70000
    out = STACK_ADDR + 0x90000
    vec_out = STACK_ADDR + 0x91000
    dump_stub = STUB_ADDR + 0x200
    uc.mem_write(out, b"\0" * fos.FOS_RESULTS_SIZE)

    def put_i32(off: int, val: int) -> None:
        uc.mem_write(esp + off, struct.pack("<i", int(val)))

    # PakonIMAu.dll dens Σ/P slots @ eigen entry 0x1028fe61
    put_i32(0x50, n)
    put_i32(0x6C, sr)
    put_i32(0x70, sg)
    put_i32(0x74, sb)
    put_i32(0x78, prg)
    put_i32(0x7C, prb)
    put_i32(0x80, pgb)
    put_i32(0x84, prr)
    put_i32(0x88, pgg)
    put_i32(0x8C, pbb)

    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_ESI, out)

    stop = fos.EIGEN_AFTER_SIGN  # PakonIMAu.dll @ 0x102901e0
    uc.hook_add(UC_HOOK_CODE, _hook_stop(stop), begin=stop, end=stop + 1)
    try:
        uc.emu_start(fos.EIGEN_ENTRY, 0, timeout=200_000_000)  # PakonIMAu.dll @ 0x1028fe61
    except UcError as e:
        raise RuntimeError(f"unicorn eigen leaf: {e}") from e

    # FPU st0=dG, st1=dB, st2=dR — fstp dump (PakonIMAu.dll handoff order)
    dump = bytearray()
    for i in range(3):
        dump += b"\xDD\x1D" + struct.pack("<I", vec_out + i * 8)
    dump += b"\xCC"
    uc.mem_write(dump_stub, bytes(dump))

    def dump_stop(u: Uc, address: int, size: int, _user: object) -> None:
        if address == dump_stub + len(dump) - 1:
            u.emu_stop()

    uc.hook_add(UC_HOOK_CODE, dump_stop, begin=dump_stub + len(dump) - 1, end=dump_stub + len(dump))
    try:
        uc.emu_start(dump_stub, 0, timeout=1_000_000)
    except UcError as e:
        raise RuntimeError(f"unicorn eigen dump: {e}") from e

    d_g, d_b, d_r = struct.unpack("<ddd", bytes(uc.mem_read(vec_out, 24)))
    return d_r, d_g, d_b


def run_paxel_frame_leaf(
    pe: bytes,
    dens_words: list[int],
    mask_bytes: bytes | bytearray,
    open_rgb: tuple[int, int, int],
    delta: tuple[int, int],
    radius_sq: int,
) -> fos.FosPaxelAcc:
    """PakonIMAu.dll @ ``0x1028f9a8`` → ``0x1028fccc`` — one-frame Σ/P locals."""
    open_y, open_c1, open_c2 = fos.fos_opening_axes(*open_rgb)
    o_r, o_g, o_b = open_rgb

    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, pe)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    dens_addr = STACK_ADDR + 0x10000
    # DLL: byte [edi + mask_base + 0xc20]; fold offset into mask_base
    mask_plane = STACK_ADDR + 0x20000
    mask_base = mask_plane - fos.PAXEL_MASK_OFF  # PakonIMAu.dll @ 0x1028fab7
    dens_bytes = b"".join(struct.pack("<H", w & 0xFFFF) for w in dens_words)
    uc.mem_write(dens_addr, dens_bytes)
    uc.mem_write(mask_plane, bytes(mask_bytes))

    esp = STACK_ADDR + 0x70000

    def put_i32(off: int, val: int) -> None:
        uc.mem_write(esp + off, struct.pack("<i", int(val)))

    put_i32(0x28, dens_addr)  # PakonIMAu.dll saved dens @ +0x28
    put_i32(0x98, mask_base)  # PakonIMAu.dll mask base @ +0x98
    put_i32(0x10, radius_sq)  # PakonIMAu.dll R² @ +0x10
    put_i32(0xAC, delta[0])  # PakonIMAu.dll Δ1 @ +0xac
    put_i32(0xB0, delta[1])  # PakonIMAu.dll Δ2 @ +0xb0
    put_i32(0x114, o_r)  # PakonIMAu.dll open R
    put_i32(0x118, o_g)  # PakonIMAu.dll open G
    put_i32(0x11C, o_b)  # PakonIMAu.dll open B (also ebx)
    put_i32(0x124, open_c1)  # PakonIMAu.dll open C1
    put_i32(0x128, open_c2)  # PakonIMAu.dll open C2

    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_EAX, dens_addr)  # PakonIMAu.dll dens @ walk
    uc.reg_write(UC_X86_REG_EBX, int(o_b))  # PakonIMAu.dll openB in ebx (full i32)
    uc.reg_write(UC_X86_REG_EBP, 0)  # PakonIMAu.dll zero frame Σ/P via ebp

    stop = fos.PAXEL_AFTER_FRAME  # PakonIMAu.dll @ 0x1028fccc
    uc.hook_add(UC_HOOK_CODE, _hook_stop(stop), begin=stop, end=stop + 1)
    try:
        uc.emu_start(fos.PAXEL_FRAME_INIT, 0, timeout=500_000_000)  # @ 0x1028f9a8
    except UcError as e:
        raise RuntimeError(f"unicorn paxel frame: {e}") from e

    def get_i32(off: int) -> int:
        return struct.unpack("<i", bytes(uc.mem_read(esp + off, 4)))[0]

    # Frame locals — PakonIMAu.dll @ 0x1028f9ad… / docs/47 table
    return fos.FosPaxelAcc(
        n=get_i32(0xC8),
        sum_r=get_i32(0xE4),
        sum_g=get_i32(0xE8),
        sum_b=get_i32(0xEC),
        sum_u=get_i32(0xCC),
        sum_v=get_i32(0xD0),
        sum_w=get_i32(0xD4),
        p_rg=get_i32(0xF0),
        p_rb=get_i32(0xF4),
        p_gb=get_i32(0xF8),
        p_rr=get_i32(0xFC),
        p_gg=get_i32(0x100),
        p_bb=get_i32(0x104),
        p_uu=get_i32(0xD8),
        p_uv=get_i32(0xDC),
        p_uw=get_i32(0xE0),
        p_vv=get_i32(0x108),
        p_ww=get_i32(0x10C),
    )


def main(argv: list[str]) -> int:
    dll_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_DLL
    pe = dll_path.read_bytes()
    assert fos.FOS_RSQUARE_PORTED
    assert fos.FOS_ORDER_AVG_PORTED
    assert fos.FOS_SLOPES_OFFSETS_PORTED
    assert fos.FOS_EIGEN_PORTED
    assert fos.FOS_PAXEL_WALK_PORTED
    assert fos.FOS_ANALYZE_PARTIAL_PORTED
    assert fos.FOS_ANALYZE_PORTED
    assert fos.FOS_ORDER_FPO_HELPER_PORTED

    def f64(va: int) -> float:
        return struct.unpack_from("<d", pe, va - IMAGE_BASE)[0]

    assert abs(f64(0x105A7280) - fos.F64_32) < 1e-15
    assert abs(f64(0x105A3C18) - fos.F64_1000) < 1e-15
    assert abs(f64(0x105A7258) - fos.F64_10000) < 1e-15
    assert abs(f64(0x105A6F38) - fos.F64_INV_SQRT3) < 1e-15
    assert abs(f64(0x105A6F30) - fos.F64_INV_SQRT6) < 1e-15
    assert abs(f64(0x105A6F28) - fos.F64_INV_SQRT2) < 1e-15
    assert abs(f64(0x10574F50) - fos.F64_ONE) < 1e-15
    assert abs(f64(0x105A7268) - fos.F64_SQRT3_2) < 1e-15
    assert abs(f64(0x105A7260) - fos.F64_NEG_SQRT3_2) < 1e-15

    print(f"DLL {dll_path}")
    print(
        f"  RSQUARE={fos.FOS_RSQUARE_PORTED} ORDER_AVG={fos.FOS_ORDER_AVG_PORTED} "
        f"SLOPES={fos.FOS_SLOPES_OFFSETS_PORTED} EIGEN={fos.FOS_EIGEN_PORTED} "
        f"PAXEL={fos.FOS_PAXEL_WALK_PORTED} PARTIAL={fos.FOS_ANALYZE_PARTIAL_PORTED} "
        f"ANALYZE={fos.FOS_ANALYZE_PORTED}"
    )

    fails = 0

    print("--- R² ---")
    for case in RSQUARE_CASES:
        n, su, sv, sw, puv, puw, puu, pvv, pww = case
        dll = run_rsquare_leaf(pe, *case)
        host_gm = fos.fos_gm_rsquare(su, sv, puv, puu, pvv, n)
        host_ill = fos.fos_ill_rsquare(su, sw, puw, puu, pww, n)
        ok = dll == (host_gm, host_ill, n)
        print(
            f"  N={n} dll={dll} host=({host_gm},{host_ill},{n}) "
            f"{'OK' if ok else 'FAIL'}"
        )
        if not ok:
            fails += 1
    assert fos.fos_gm_rsquare(1000, 2000, 24000, 12000, 48000, 100) == 1000

    print("--- orderAvg ---")
    for open_rgb, mean in ORDER_AVG_CASES:
        dll = run_order_avg_leaf(pe, open_rgb, mean)
        host = fos.fos_order_avg(open_rgb, mean)
        ok = dll == host
        print(f"  open={open_rgb} mean={mean} dll={dll} host={host} "
              f"{'OK' if ok else 'FAIL'}")
        if not ok:
            fails += 1

    print("--- slopes+offsets (+ orderAvg) ---")
    for eigen, mean, open_rgb in SLOPE_CASES:
        dll_avg, dll_sl = run_slopes_offsets_leaf(pe, eigen, mean, open_rgb)
        host_avg = fos.fos_order_avg(open_rgb, mean)
        host_sl = fos.fos_gm_ill_slopes_offsets(eigen, mean, apply_sign=True)
        ok = dll_avg == host_avg and dll_sl == host_sl
        print(
            f"  eigen={eigen} dll_avg={dll_avg} host_avg={host_avg} "
            f"dll_sl={dll_sl} host_sl={host_sl} {'OK' if ok else 'FAIL'}"
        )
        if not ok:
            fails += 1

    print("--- RGB max-eigen unit ---")
    for case in EIGEN_CASES:
        dll = run_eigen_leaf(pe, case)
        host = fos.fos_rgb_max_eigen_unit(*case)
        err = max(abs(a - b) for a, b in zip(dll, host))
        ok = err < 1e-9
        print(
            f"  N={case[0]} dll={dll} host={host} err={err:.3e} "
            f"{'OK' if ok else 'FAIL'}"
        )
        if not ok:
            fails += 1

    print("--- dens paxel frame ---")
    assert fos.FOS_PAXEL_WALK_PORTED
    for label, dens, mask, open_rgb, delta, r2 in PAXEL_CASES:
        dll = run_paxel_frame_leaf(pe, dens, mask, open_rgb, delta, r2)
        open_y, open_c1, open_c2 = fos.fos_opening_axes(*open_rgb)
        host = fos.fos_paxel_accumulate_frame(
            dens,
            mask,
            open_rgb=open_rgb,
            open_c1=open_c1,
            open_c2=open_c2,
            delta1=delta[0],
            delta2=delta[1],
            radius_sq=r2,
        )
        ok = dll == host
        print(
            f"  {label} dll.n={dll.n} host.n={host.n} "
            f"dll.ΣRGB=({dll.sum_r},{dll.sum_g},{dll.sum_b}) "
            f"host.ΣRGB=({host.sum_r},{host.sum_g},{host.sum_b}) "
            f"{'OK' if ok else 'FAIL'}"
        )
        if not ok:
            print(f"    dll={dll}")
            print(f"    host={host}")
            fails += 1

    print("--- orderFpo compose / blend / fallback (host) ---")
    assert fos.FOS_ORDER_FPO_COMPOSE_PORTED
    assert fos.FOS_ORDER_FPO_HELPER_PORTED
    # PakonIMAu.dll @ 0x1028f890 — i16(open+Δ)
    assert fos.fos_order_fpo_compose((100, 200, -50), (3, -4, 10)) == (103, 196, -40)
    assert fos.fos_order_fpo_compose((32767, 0, 0), (1, 0, 0)) == (-32768, 0, 0)  # wrap
    # PakonIMAu.dll @ 0x1028f509 — Δ0 = dminOpenR + 0x498
    assert fos.fos_order_fpo_delta0(100) == 100 + fos.ORDER_FPO_DELTA0_BIAS
    # PakonIMAu.dll @ 0x1028f511 — blend; w=1000 → Δ=mean; w=0 → Δ=dminOpenC
    assert fos.fos_order_fpo_blend_c_delta(500, 100, 1000) == 500
    assert fos.fos_order_fpo_blend_c_delta(500, 100, 0) == 100
    # PakonIMAu.dll @ 0x1028f878 — fallback keeps Δ0; replaces C deltas
    assert fos.fos_order_fpo_fallback_delta(42, 11, 22) == (42, 11, 22)
    print("  compose/blend/fallback host asserts OK")

    print("--- orderFpo helper means→Δ ---")
    helper_kw = dict(
        dc_gate=10,
        dc_radius=1000,  # huge R → all in radius
        dc_w_gm=1000,
        dc_w_ill=1000,
        dc_thresh_n=0,
        dmin_open_r=50,
        dmin_open_c1=0,
        dmin_open_c2=0,
        wtab_enable=0,
    )
    helper_cases: list[tuple[str, list[fos.FosHelperFrame]]] = [
        (
            "unweighted-2",
            [
                fos.FosHelperFrame(c1_lo=100, c2_lo=200, gate_9cc=0),
                fos.FosHelperFrame(c1_lo=300, c2_lo=400, gate_9cc=0),
            ],
        ),
        (
            "skip-fid",
            [
                fos.FosHelperFrame(skip_fiduciary=True, c1_lo=999, c2_lo=999),
                fos.FosHelperFrame(c1_lo=10, c2_lo=20, gate_9cc=0),
            ],
        ),
        (
            "hi-bank",
            [
                fos.FosHelperFrame(
                    c1_lo=1, c2_lo=2, c1_hi=1000, c2_hi=2000, gate_9cc=100
                ),
            ],
        ),
        (
            "method2-empty",
            [],
        ),
        (
            "weighted",
            [
                # at dminOpen centre → dist2=0 → hi_w; count=2≤thresh=2
                fos.FosHelperFrame(c1_lo=0, c2_lo=0, gate_9cc=0),
                fos.FosHelperFrame(c1_lo=0, c2_lo=0, gate_9cc=0),
            ],
        ),
    ]
    for label, frames in helper_cases:
        kw = dict(helper_kw)
        if label == "method2-empty":
            kw["dc_thresh_n"] = 0
        if label == "weighted":
            # count_in=2 <= thresh=2 → weighted; wsum=2000 > 2*100
            kw["dc_thresh_n"] = 2
            kw["wtab_enable"] = 1
            kw["wtab"] = (0, 10000, 100, 1000)  # lo, mid, mid_w, hi_w
            # give distinct C for mean (distance still 0 via lo==centre)
            frames = [
                fos.FosHelperFrame(c1_lo=0, c2_lo=0, c1_hi=100, c2_hi=200, gate_9cc=100),
                fos.FosHelperFrame(c1_lo=0, c2_lo=0, c1_hi=300, c2_hi=400, gate_9cc=100),
            ]
        dll = run_helper_leaf(pe, frames, **kw)
        host = fos.fos_order_fpo_helper(frames, **kw)
        ok = dll == host
        print(
            f"  {label} dll={dll} host={host} {'OK' if ok else 'FAIL'}"
        )
        if not ok:
            fails += 1

    print("--- postfill idiv C banks ---")
    assert fos.FOS_POSTFILL_C_PORTED
    for numer, denom in (
        (1000, 10),
        (-1000, 10),
        (1000, -10),
        (-1000, -10),
        (7, 3),
        (-7, 3),
        (0x123456, 0x360),
    ):
        dll_q = run_idiv_leaf(pe, numer, denom)
        host_q = fos.fos_idiv_trunc(numer, denom)
        ok = dll_q == host_q
        print(f"  idiv {numer}/{denom} dll={dll_q} host={host_q} {'OK' if ok else 'FAIL'}")
        if not ok:
            fails += 1
    assert fos.fos_postfill_gate_9cc(42) == 42
    assert fos.fos_postfill_gate_9cc(-1) == -1
    low = fos.fos_postfill_c_low(1000, 2000, 10)
    assert low == (100, 200)
    hi = fos.fos_postfill_c_high(1000, 2000, 9000, 8000, 10, 100, out_word6=50, dc_word_e=10)
    assert hi == (90, 80)  # high path: OUT+6 > dc+0xe
    hi2 = fos.fos_postfill_c_high(1000, 2000, 9000, 8000, 10, 100, out_word6=5, dc_word_e=10)
    assert hi2 == (100, 200)  # fallback = low
    print("  postfill C bank host+Unicorn OK")

    print("--- fos_calc_results host compose ---")
    dens, mask = fos.fos_paxel_fake_planes(fill=0x120)
    for i in fos.fos_paxel_indices():
        mask[i] = 1
    open_rgb = (1000, 1100, 900)
    open_y, open_c1, open_c2 = fos.fos_opening_axes(*open_rgb)
    acc = fos.fos_paxel_accumulate_frame(
        dens,
        mask,
        open_rgb=open_rgb,
        open_c1=open_c1,
        open_c2=open_c2,
        delta1=0,
        delta2=0,
        radius_sq=0x7FFFFFFF,
    )
    dmin_rgb = (900, 1000, 800)
    helper_frames = [
        fos.FosHelperFrame(c1_lo=50, c2_lo=-20, gate_9cc=0),
        fos.FosHelperFrame(c1_lo=70, c2_lo=-10, gate_9cc=0),
    ]
    eax, out = fos.fos_calc_results(
        open_rgb=open_rgb,
        frame_dmin_rgbs=[dmin_rgb, (950, 1050, 850)],
        paxel_acc=acc,
        helper_frames=helper_frames,
        dc_gate=10,
        dc_radius=5000,
        dc_w_gm=1000,
        dc_w_ill=1000,
        dc_thresh_n=0,
    )
    assert eax == 0
    assert out.num_pixels == acc.n
    assert out.fos_dmin == fos.fos_dmin_min([dmin_rgb, (950, 1050, 850)])
    # Recompute Δ via helper + compose path
    (_rgb, axes) = fos.fos_dmin_minus_open(out.fos_dmin, open_rgb)
    h = fos.fos_order_fpo_helper(
        helper_frames,
        dc_gate=10,
        dc_radius=5000,
        dc_w_gm=1000,
        dc_w_ill=1000,
        dc_thresh_n=0,
        dmin_open_r=_rgb[0],
        dmin_open_c1=axes[1],
        dmin_open_c2=axes[2],
    )
    assert h.eax == 0
    expect_fpo = fos.fos_order_fpo_compose(fos.fos_opening_axes(*open_rgb), h.delta)
    assert out.order_fpo == expect_fpo
    assert out.ofpo_method == h.ofpo_method
    assert len(out.to_bytes()) == fos.FOS_RESULTS_SIZE
    print(
        f"  compose eax=0 n={out.num_pixels} orderFpo={out.order_fpo} "
        f"orderAvg={out.order_avg} OK"
    )

    print("--- fos_analyze_roll host caller ---")
    assert fos.FOS_ROLL_CALLER_PORTED
    dens2, mask2 = fos.fos_paxel_fake_planes(fill=0x120)
    for i in fos.fos_paxel_indices():
        mask2[i] = 1
    roll_frames = [
        fos.FosRollFrame(
            dens_words=dens2,
            mask_bytes=mask2,
            dmin_rgb=dmin_rgb,
            c1_lo=50,
            c2_lo=-20,
        ),
        fos.FosRollFrame(
            dens_words=dens2,
            mask_bytes=mask2,
            dmin_rgb=(950, 1050, 850),
            c1_lo=70,
            c2_lo=-10,
        ),
    ]
    eax_r, out_r = fos.fos_analyze_roll(
        roll_frames,
        open_rgb=open_rgb,
        dc_gate=10,
        dc_helper_radius=5000,
        dc_w_gm=1000,
        dc_w_ill=1000,
        dc_thresh_n=0,
        dc_paxel_radius=0x7FFF,  # huge → radius_sq still large
        dc_paxel_n_thresh=0,
    )
    assert eax_r == 0
    assert out_r.order_fpo == out.order_fpo
    assert out_r.ofpo_method == out.ofpo_method
    assert out_r.fos_dmin == out.fos_dmin
    # Roll uses helper Δ as paxel centres — N may differ from Δ=0 compose leaf
    assert out_r.num_pixels >= 0
    assert len(out_r.to_bytes()) == fos.FOS_RESULTS_SIZE
    print(
        f"  roll eax=0 n={out_r.num_pixels} orderFpo={out_r.order_fpo} "
        f"orderAvg={out_r.order_avg} OK"
    )

    if fails:
        print(f"FAILED {fails}")
        return 1
    print("FOS dens golden: ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
