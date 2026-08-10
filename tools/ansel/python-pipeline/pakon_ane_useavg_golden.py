#!/usr/bin/env python3
"""Golden Ane ``useAvg≠0`` leaves vs PakonIMAu.dll (Unicorn).

* Correlation score FPU body inside ``0x102a8950`` (``0x102a8b40…``)
  — FCW ``0x027F`` (MSVC 53-bit PC) for float64 bit-exact
* ``color_correlation_mask`` ``0x102a8950`` — stubbed dims / plane rows /
  knot ``0x104dda30`` / mask zero+write
* Masked dens-hist accum ``0x102a8600`` — stubbed dims / plane / mask /
  hist-map; dens-hist ``inc`` via host leaf (same as 84d0 harness)
* Host ``ane_build_noise_table_e9d0(..., use_avg=True)`` smoke

Run::

    /Users/guy/.pyenv/versions/3.10.13/bin/python3 \\
        tools/ansel/pakon_ane_useavg_golden.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import numpy as np
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_EBP,
    UC_X86_REG_EBX,
    UC_X86_REG_ECX,
    UC_X86_REG_EDI,
    UC_X86_REG_EDX,
    UC_X86_REG_EIP,
    UC_X86_REG_ESI,
    UC_X86_REG_ESP,
)

import pakon_ane_order as ane

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x100000
HEAP_ADDR = 0x20000000
HEAP_SIZE = 0x200000
# MSVC default precision control (53-bit) — matches host float64
FCW_MSVC_53 = 0x027F
VA_CORR_SCORE = 0x102A8B40
VA_CORR_SCORE_AFTER_MUL = 0x102A8B9E  # after ``fmul`` 1/3
VA_DDA30 = 0x104DDA30
VA_ZERO_MASK = 0x101593E0
VA_MASK_PLANE = 0x1014CEB0
VA_IMG_HEIGHT = 0x104D4520
VA_IMG_WIDTH = 0x104D4530
VA_IMG_NCH = 0x104D4540
VA_PLANE_ROW = 0x101ED810
VA_HIST_MAP_GET = 0x104EAB20
VA_HIST_ACCUM_TRAMP = 0x104EA370
VA_PLANE_HIST_A8 = 0x104EA370  # same tramp; 8600 also hits +0xa8/+0xb0
VA_MASK_PLANE_7990 = 0x102A7990
DEFAULT_IMAU = (
    "/Users/guy/Downloads/Pakon Update 3/fx35install/"
    "program files/Pakon/F-X35 COM SERVER/PakonIMAu.dll"
)


def _load_dll(path: Path) -> bytes:
    return path.read_bytes()


def _map_text(uc: Uc, dll: bytes) -> None:
    e = struct.unpack_from("<I", dll, 0x3C)[0]
    nsec = struct.unpack_from("<H", dll, e + 6)[0]
    optsz = struct.unpack_from("<H", dll, e + 0x14)[0]
    soff = e + 0x18 + optsz
    for i in range(nsec):
        o = soff + i * 40
        name = dll[o : o + 8].split(b"\0")[0]
        vsize, va, rawsize, rawptr = struct.unpack_from("<IIII", dll, o + 8)
        if name not in (b".text", b".rdata"):
            continue
        end = (va + max(vsize, rawsize) + 0xFFF) & ~0xFFF
        for p in range(va & ~0xFFF, end, 0x1000):
            try:
                uc.mem_map(IMAGE_BASE + p, 0x1000)
            except UcError:
                pass
        uc.mem_write(
            IMAGE_BASE + va, dll[rawptr : rawptr + min(rawsize, max(vsize, rawsize))]
        )


def _save_regs(uc: Uc) -> dict[int, int]:
    # Preserve callee-saved only — do not clobber EAX return from hooks.
    return {
        UC_X86_REG_EBX: uc.reg_read(UC_X86_REG_EBX),
        UC_X86_REG_EDX: uc.reg_read(UC_X86_REG_EDX),
        UC_X86_REG_ESI: uc.reg_read(UC_X86_REG_ESI),
        UC_X86_REG_EDI: uc.reg_read(UC_X86_REG_EDI),
        UC_X86_REG_EBP: uc.reg_read(UC_X86_REG_EBP),
    }


def _restore_regs(uc: Uc, saved: dict[int, int]) -> None:
    for reg, val in saved.items():
        uc.reg_write(reg, val)


def _ret_imm(uc: Uc, value: int, *, stdcall_nargs: int = 0) -> None:
    esp = uc.reg_read(UC_X86_REG_ESP)
    ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
    uc.reg_write(UC_X86_REG_EAX, int(value) & 0xFFFFFFFF)
    uc.reg_write(UC_X86_REG_ESP, esp + 4 + 4 * stdcall_nargs)
    uc.reg_write(UC_X86_REG_EIP, ret)


def run_corr_score_fpu(
    dll: bytes,
    r0: int,
    r1: int,
    r2: int,
    k0: float,
    k1: float,
    k2: float,
) -> float:
    """Unicorn FPU score body ``0x102a8b40…`` → double (FCW 53-bit)."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    _map_text(uc, dll)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    esp = STACK_ADDR + 0x8000
    out = STACK_ADDR + 0x9000
    kb_addr = STACK_ADDR + 0x9100
    fcw_addr = STACK_ADDR + 0x9300
    stub = STACK_ADDR + 0x9200
    uc.mem_write(esp + 0x10, struct.pack("<d", float(k0)))
    uc.mem_write(esp + 0x18, struct.pack("<d", float(k1)))
    uc.mem_write(esp + 0x38, struct.pack("<h", int(r2)) + b"\x00\x00")
    uc.mem_write(esp + 0x3c, struct.pack("<h", int(r1)) + b"\x00\x00")
    uc.mem_write(esp + 0x40, struct.pack("<h", int(r0)) + b"\x00\x00")
    uc.mem_write(kb_addr, struct.pack("<d", float(k2)))
    uc.mem_write(fcw_addr, struct.pack("<H", FCW_MSVC_53))
    code = bytearray()
    code += b"\xD9\x2D" + struct.pack("<I", fcw_addr)  # fldcw
    code += b"\xDD\x05" + struct.pack("<I", kb_addr)  # fld k2
    code += b"\xBC" + struct.pack("<I", esp)  # mov esp
    jmp_at = stub + len(code)
    code += b"\xE9" + struct.pack("<i", VA_CORR_SCORE - (jmp_at + 5))
    uc.mem_write(stub, bytes(code))
    try:
        uc.mem_protect(0x102A8000, 0x1000, 7)
    except UcError:
        pass
    # After fmul 1/3: fstp [out]; int3
    uc.mem_write(
        VA_CORR_SCORE_AFTER_MUL,
        b"\xDD\x1D" + struct.pack("<I", out) + b"\xCC",
    )
    try:
        uc.emu_start(
            stub,
            VA_CORR_SCORE_AFTER_MUL + 7,
            timeout=1_000_000,
            count=500,
        )
    except UcError:
        pass
    return struct.unpack("<d", uc.mem_read(out, 8))[0]


def _make_plane_img(
    uc: Uc,
    alloc,
    planes: list[np.ndarray],
    *,
    elem_size: int,
) -> int:
    """Build wrap → image with ``+0x20`` plane slots (ed810 / 4ceb0 layout)."""
    n_planes = len(planes)
    h, w = planes[0].shape
    slots = alloc(n_planes * 8)
    for p in range(n_planes):
        rows = []
        for y in range(h):
            row = alloc(w * elem_size)
            if elem_size == 2:
                uc.mem_write(
                    row,
                    struct.pack(
                        f"<{w}h",
                        *[int(planes[p][y, x]) for x in range(w)],
                    ),
                )
            else:
                uc.mem_write(
                    row,
                    bytes(int(planes[p][y, x]) & 0xFF for x in range(w)),
                )
            rows.append(row)
        arr = alloc(h * 4)
        uc.mem_write(arr, struct.pack(f"<{h}I", *rows))
        desc = alloc(0x20)
        uc.mem_write(desc + 0x18, struct.pack("<I", arr))
        uc.mem_write(slots + p * 8, struct.pack("<II", 0, desc))
    image_obj = alloc(0x28)
    uc.mem_write(image_obj + 0x20, struct.pack("<I", slots))
    wrap = alloc(8)
    uc.mem_write(wrap, struct.pack("<II", 0x1057B10C, image_obj))
    return wrap


def run_corr_mask_8950(
    dll: bytes,
    sample_planes: list[np.ndarray],
    residual_planes: list[np.ndarray],
    plane_doubles: list[list[float]],
    *,
    pixel_offset: int,
    bin_divisor: int,
    max_bin: int,
    tau: float,
) -> tuple[list[np.ndarray], float]:
    """Unicorn ``0x102a8950`` → mask planes + filled ratio."""
    h, w = sample_planes[0].shape
    n_bins = int(max_bin) + 1
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    _map_text(uc, dll)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(HEAP_ADDR, HEAP_SIZE)
    bump = [HEAP_ADDR + 0x10000]

    def alloc(n: int) -> int:
        a = bump[0]
        bump[0] = (a + n + 15) & ~15
        uc.mem_write(a, b"\x00" * n)
        return a

    sample_img = _make_plane_img(uc, alloc, sample_planes, elem_size=2)
    residual_img = _make_plane_img(uc, alloc, residual_planes, elem_size=2)
    mask_zeros = [np.zeros((h, w), dtype=np.uint8) for _ in range(3)]
    mask_img = _make_plane_img(uc, alloc, mask_zeros, elem_size=1)

    # Knot doubles: flat storage + ecx tags for dda30
    knot_base = alloc(3 * n_bins * 8)
    for p in range(3):
        for b in range(n_bins):
            uc.mem_write(
                knot_base + (p * n_bins + b) * 8,
                struct.pack("<d", float(plane_doubles[p][b])),
            )
    container = alloc(0x20)
    # dda30 hooked: ecx → plane via these addresses
    vec0, vec1, vec2 = container + 8, container + 0x10, container + 0x18
    plane_of_vec = {vec0: 0, vec1: 1, vec2: 2}

    ane_obj = alloc(0xA0)
    uc.mem_write(ane_obj + 0x20, struct.pack("<d", float(tau)))
    uc.mem_write(ane_obj + 0x34, struct.pack("<i", int(pixel_offset)))
    uc.mem_write(ane_obj + 0x3C, struct.pack("<i", int(bin_divisor)))
    uc.mem_write(ane_obj + 0x44, struct.pack("<i", int(max_bin)))
    uc.mem_write(ane_obj + 0x78, struct.pack("<I", container))
    uc.mem_write(ane_obj + ane.ANE_OBJ_CORR_RATIO_OFF, struct.pack("<d", 0.0))

    fcw_addr = alloc(2)
    uc.mem_write(fcw_addr, struct.pack("<H", FCW_MSVC_53))

    def hook_height(uc: Uc, address: int, size: int, user: object) -> None:
        _ret_imm(uc, h)

    def hook_width(uc: Uc, address: int, size: int, user: object) -> None:
        _ret_imm(uc, w)

    def hook_nch(uc: Uc, address: int, size: int, user: object) -> None:
        _ret_imm(uc, 3)

    def hook_plane_i16(uc: Uc, address: int, size: int, user: object) -> None:
        saved = _save_regs(uc)
        esp = uc.reg_read(UC_X86_REG_ESP)
        plane = struct.unpack("<I", uc.mem_read(esp + 4, 4))[0]
        img = uc.reg_read(UC_X86_REG_ECX)
        slots = struct.unpack("<I", uc.mem_read(img + 0x20, 4))[0]
        # Return slot address (caller does [eax+4] → desc)
        _ret_imm(uc, slots + plane * 8, stdcall_nargs=1)
        _restore_regs(uc, saved)

    def hook_dda30(uc: Uc, address: int, size: int, user: object) -> None:
        saved = _save_regs(uc)
        esp = uc.reg_read(UC_X86_REG_ESP)
        idx = struct.unpack("<I", uc.mem_read(esp + 4, 4))[0]
        vec = uc.reg_read(UC_X86_REG_ECX)
        p = plane_of_vec.get(vec, 0)
        ptr = knot_base + (p * n_bins + int(idx)) * 8
        _ret_imm(uc, ptr, stdcall_nargs=1)
        _restore_regs(uc, saved)

    def hook_zero_mask(uc: Uc, address: int, size: int, user: object) -> None:
        # Zero all three mask planes (matches 593e0 fill-0 loop).
        saved = _save_regs(uc)
        img = uc.reg_read(UC_X86_REG_ECX)
        slots = struct.unpack("<I", uc.mem_read(img + 0x20, 4))[0]
        for p in range(3):
            desc = struct.unpack("<I", uc.mem_read(slots + p * 8 + 4, 4))[0]
            rows = struct.unpack("<I", uc.mem_read(desc + 0x18, 4))[0]
            for y in range(h):
                row = struct.unpack("<I", uc.mem_read(rows + y * 4, 4))[0]
                uc.mem_write(row, b"\x00" * w)
        _ret_imm(uc, img, stdcall_nargs=1)
        _restore_regs(uc, saved)

    uc.hook_add(UC_HOOK_CODE, hook_height, begin=VA_IMG_HEIGHT, end=VA_IMG_HEIGHT + 1)
    uc.hook_add(UC_HOOK_CODE, hook_width, begin=VA_IMG_WIDTH, end=VA_IMG_WIDTH + 1)
    uc.hook_add(UC_HOOK_CODE, hook_nch, begin=VA_IMG_NCH, end=VA_IMG_NCH + 1)
    uc.hook_add(UC_HOOK_CODE, hook_plane_i16, begin=VA_PLANE_ROW, end=VA_PLANE_ROW + 1)
    uc.hook_add(UC_HOOK_CODE, hook_plane_i16, begin=VA_MASK_PLANE, end=VA_MASK_PLANE + 1)
    uc.hook_add(UC_HOOK_CODE, hook_dda30, begin=VA_DDA30, end=VA_DDA30 + 1)
    uc.hook_add(UC_HOOK_CODE, hook_zero_mask, begin=VA_ZERO_MASK, end=VA_ZERO_MASK + 1)

    # Entry: thiscall ecx=ane; push mask, resid, sample
    esp = STACK_ADDR + 0x8000
    ret_addr = STACK_ADDR + 0x100
    uc.mem_write(ret_addr, b"\xcc")
    # fldcw before call
    prologue = STACK_ADDR + 0x9400
    code = bytearray()
    code += b"\xD9\x2D" + struct.pack("<I", fcw_addr)
    code += b"\xB9" + struct.pack("<I", ane_obj)  # mov ecx, ane
    code += b"\x68" + struct.pack("<I", mask_img)
    code += b"\x68" + struct.pack("<I", residual_img)
    code += b"\x68" + struct.pack("<I", sample_img)
    code += b"\x68" + struct.pack("<I", ret_addr)
    call_at = prologue + len(code)
    code += b"\xE9" + struct.pack("<i", ane.ANE_ANALYZE_CORR_MASK - (call_at + 5))
    uc.mem_write(prologue, bytes(code))
    uc.reg_write(UC_X86_REG_ESP, esp)
    try:
        uc.emu_start(
            prologue,
            ret_addr,
            timeout=5_000_000,
            count=500_000,
        )
    except UcError:
        pass

    masks: list[np.ndarray] = []
    mask_obj = struct.unpack("<I", uc.mem_read(mask_img + 4, 4))[0]
    slots = struct.unpack("<I", uc.mem_read(mask_obj + 0x20, 4))[0]
    for p in range(3):
        desc = struct.unpack("<I", uc.mem_read(slots + p * 8 + 4, 4))[0]
        rows = struct.unpack("<I", uc.mem_read(desc + 0x18, 4))[0]
        m = np.zeros((h, w), dtype=np.uint8)
        for y in range(h):
            row = struct.unpack("<I", uc.mem_read(rows + y * 4, 4))[0]
            m[y, :] = list(uc.mem_read(row, w))
        masks.append(m)
    ratio = struct.unpack(
        "<d", uc.mem_read(ane_obj + ane.ANE_OBJ_CORR_RATIO_OFF, 8)
    )[0]
    return masks, ratio


def run_accum_8600(
    dll: bytes,
    sample_planes: list[np.ndarray],
    residual_planes: list[np.ndarray],
    mask_planes: list[np.ndarray],
    *,
    pixel_offset: int,
    bin_divisor: int,
    max_bin: int,
    hist_offset: float,
    hist_divisor: float,
    n_res_bins: int,
) -> list[list[list[int]]]:
    """Unicorn ``0x102a8600`` → dens-hist counts ``[plane][code_bin]``."""
    n_planes = len(sample_planes)
    h, w = sample_planes[0].shape
    n_code = int(max_bin) + 1
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    _map_text(uc, dll)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(HEAP_ADDR, HEAP_SIZE)
    bump = [HEAP_ADDR + 0x10000]

    def alloc(n: int) -> int:
        a = bump[0]
        bump[0] = (a + n + 15) & ~15
        uc.mem_write(a, b"\x00" * n)
        return a

    sample_img = _make_plane_img(uc, alloc, sample_planes, elem_size=2)
    residual_img = _make_plane_img(uc, alloc, residual_planes, elem_size=2)
    mask_img = _make_plane_img(uc, alloc, mask_planes, elem_size=1)

    def make_hist() -> tuple[int, int]:
        bins = alloc(n_res_bins * 4)
        hobj = alloc(0x40)
        blob = bytearray(0x40)
        struct.pack_into("<I", blob, 0x0C, n_res_bins)
        struct.pack_into("<d", blob, 0x10, float(hist_offset))
        struct.pack_into("<d", blob, 0x28, float(hist_divisor))
        struct.pack_into("<I", blob, 0x38, bins)
        uc.mem_write(hobj, bytes(blob))
        wrap = alloc(8)
        uc.mem_write(wrap, struct.pack("<II", 0, hobj))
        return wrap, bins

    a4_wraps: list[int] = []
    a4_bins: list[int] = []
    for _ in range(n_planes * n_code):
        ww, bb = make_hist()
        a4_wraps.append(ww)
        a4_bins.append(bb)
    # Dummy +0xa8 / +0xb0 hists (inc'd always / when masked)
    a8_wraps = [make_hist()[0] for _ in range(n_planes)]
    b0_wraps = [make_hist()[0] for _ in range(n_planes)]

    a4_arr = alloc(n_planes * n_code * 4)
    uc.mem_write(a4_arr, struct.pack(f"<{n_planes * n_code}I", *a4_wraps))
    a4_holder = alloc(8)
    uc.mem_write(a4_holder, struct.pack("<II", 0, a4_arr))
    a4_map = alloc(0x10)
    uc.mem_write(a4_map + 0x0C, struct.pack("<I", a4_holder))
    a4_map_wrap = alloc(8)
    uc.mem_write(a4_map_wrap, struct.pack("<II", 0, a4_map))

    def embed_plane_map(wraps: list[int]) -> int:
        arr = alloc(n_planes * 4)
        uc.mem_write(arr, struct.pack(f"<{n_planes}I", *wraps))
        holder = alloc(8)
        uc.mem_write(holder, struct.pack("<II", 0, arr))
        mobj = alloc(0x10)
        uc.mem_write(mobj + 0x0C, struct.pack("<I", holder))
        # Embedded wrap at ane+off: [0]=vtbl, [4]=mobj — lea ecx,[ane+off]
        return mobj

    a8_mobj = embed_plane_map(a8_wraps)
    b0_mobj = embed_plane_map(b0_wraps)

    ane_obj = alloc(0xC0)
    uc.mem_write(ane_obj + 0x34, struct.pack("<i", int(pixel_offset)))
    uc.mem_write(ane_obj + 0x3C, struct.pack("<i", int(bin_divisor)))
    uc.mem_write(ane_obj + 0x40, struct.pack("<i", n_code))
    uc.mem_write(ane_obj + 0x44, struct.pack("<i", int(max_bin)))
    uc.mem_write(ane_obj + 0xA4, struct.pack("<I", a4_map_wrap))
    # Embedded maps: 8600 uses lea ecx,[ebp+0xa8] / +0xb0 with
    # [ecx+4] = hist map obj (same as wrap+4).
    uc.mem_write(ane_obj + 0xA8, struct.pack("<II", 0, a8_mobj))
    uc.mem_write(ane_obj + 0xB0, struct.pack("<II", 0, b0_mobj))

    def hook_height(uc: Uc, address: int, size: int, user: object) -> None:
        _ret_imm(uc, h)

    def hook_width(uc: Uc, address: int, size: int, user: object) -> None:
        _ret_imm(uc, w)

    def hook_nch(uc: Uc, address: int, size: int, user: object) -> None:
        _ret_imm(uc, n_planes)

    def hook_plane(uc: Uc, address: int, size: int, user: object) -> None:
        saved = _save_regs(uc)
        esp = uc.reg_read(UC_X86_REG_ESP)
        plane = struct.unpack("<I", uc.mem_read(esp + 4, 4))[0]
        img = uc.reg_read(UC_X86_REG_ECX)
        slots = struct.unpack("<I", uc.mem_read(img + 0x20, 4))[0]
        _ret_imm(uc, slots + plane * 8, stdcall_nargs=1)
        _restore_regs(uc, saved)

    def hook_map_get(uc: Uc, address: int, size: int, user: object) -> None:
        saved = _save_regs(uc)
        esp = uc.reg_read(UC_X86_REG_ESP)
        slot = struct.unpack("<I", uc.mem_read(esp + 4, 4))[0]
        map_wrap = uc.reg_read(UC_X86_REG_ECX)
        map_obj = struct.unpack("<I", uc.mem_read(map_wrap + 4, 4))[0]
        holder = struct.unpack("<I", uc.mem_read(map_obj + 0x0C, 4))[0]
        arr = struct.unpack("<I", uc.mem_read(holder + 4, 4))[0]
        hist_wrap = struct.unpack("<I", uc.mem_read(arr + slot * 4, 4))[0]
        _ret_imm(uc, hist_wrap, stdcall_nargs=1)
        _restore_regs(uc, saved)

    def hook_accum(uc: Uc, address: int, size: int, user: object) -> None:
        saved = _save_regs(uc)
        wrap = uc.reg_read(UC_X86_REG_ECX)
        hist = struct.unpack("<I", uc.mem_read(wrap + 4, 4))[0]
        esp = uc.reg_read(UC_X86_REG_ESP)
        value = struct.unpack("<i", uc.mem_read(esp + 4, 4))[0]
        ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
        n = struct.unpack("<I", uc.mem_read(hist + ane.ANE_HIST_N_OFF, 4))[0]
        off = struct.unpack(
            "<d", uc.mem_read(hist + ane.ANE_HIST_OFFSET_OFF, 8)
        )[0]
        div = struct.unpack(
            "<d", uc.mem_read(hist + ane.ANE_HIST_DIVISOR_OFF, 8)
        )[0]
        bins_addr = struct.unpack(
            "<I", uc.mem_read(hist + ane.ANE_HIST_BINS_OFF, 4)
        )[0]
        bins = list(struct.unpack(f"<{n}i", uc.mem_read(bins_addr, n * 4)))
        ane.ane_dens_hist_accum(bins, value, offset=off, divisor=div, n=n)
        uc.mem_write(bins_addr, struct.pack(f"<{n}i", *bins))
        uc.reg_write(UC_X86_REG_ESP, esp + 8)
        uc.reg_write(UC_X86_REG_EIP, ret)
        _restore_regs(uc, saved)

    uc.hook_add(UC_HOOK_CODE, hook_height, begin=VA_IMG_HEIGHT, end=VA_IMG_HEIGHT + 1)
    uc.hook_add(UC_HOOK_CODE, hook_width, begin=VA_IMG_WIDTH, end=VA_IMG_WIDTH + 1)
    uc.hook_add(UC_HOOK_CODE, hook_nch, begin=VA_IMG_NCH, end=VA_IMG_NCH + 1)
    uc.hook_add(UC_HOOK_CODE, hook_plane, begin=VA_PLANE_ROW, end=VA_PLANE_ROW + 1)
    uc.hook_add(
        UC_HOOK_CODE, hook_plane, begin=VA_MASK_PLANE_7990, end=VA_MASK_PLANE_7990 + 1
    )
    uc.hook_add(UC_HOOK_CODE, hook_map_get, begin=VA_HIST_MAP_GET, end=VA_HIST_MAP_GET + 1)
    uc.hook_add(
        UC_HOOK_CODE, hook_accum, begin=VA_HIST_ACCUM_TRAMP, end=VA_HIST_ACCUM_TRAMP + 1
    )

    esp = STACK_ADDR + 0x8000
    ret_addr = STACK_ADDR + 0x100
    uc.mem_write(ret_addr, b"\xcc")
    # thiscall: push mask, resid, sample; ecx=ane
    uc.mem_write(
        esp,
        struct.pack(
            "<IIII",
            ret_addr,
            sample_img,
            residual_img,
            mask_img,
        ),
    )
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_ECX, ane_obj)
    try:
        uc.emu_start(
            ane.ANE_ANALYZE_ACCUM_8600,
            ret_addr,
            timeout=5_000_000,
            count=500_000,
        )
    except UcError:
        pass

    out: list[list[list[int]]] = []
    for p in range(n_planes):
        row: list[list[int]] = []
        for b in range(n_code):
            addr = a4_bins[p * n_code + b]
            row.append(
                list(struct.unpack(f"<{n_res_bins}i", uc.mem_read(addr, n_res_bins * 4)))
            )
        out.append(row)
    return out


def main() -> int:
    dll_path = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IMAU)
    if not dll_path.is_file():
        print(f"DLL not found: {dll_path}", file=sys.stderr)
        return 2
    dll = _load_dll(dll_path)
    fail = 0
    print(
        f"ANE useAvg golden  CORR_MASK={ane.ANE_ANALYZE_CORR_MASK_PORTED} "
        f"ACCUM_8600={ane.ANE_ANALYZE_ACCUM_8600_PORTED}"
    )

    # --- score FPU leaf ---
    score_cases = [
        (1, 2, 3, 4.0, 5.0, 6.0),
        (-2, 3, -1, 1.5, 2.5, 3.5),
        (10, -5, 7, 0.1, 0.2, 0.3),
        (4, 4, 4, 2.0, 2.0, 2.0),
        (0, 1, -1, 3.0, 4.0, 5.0),
    ]
    for r0, r1, r2, k0, k1, k2 in score_cases:
        host = ane.ane_corr_score_8950(r0, r1, r2, k0, k1, k2)
        ref = run_corr_score_fpu(dll, r0, r1, r2, k0, k1, k2)
        ok = host == ref and struct.pack("<d", host) == struct.pack("<d", ref)
        print(
            f"  corr_score r=({r0},{r1},{r2}) k=({k0},{k1},{k2}): "
            f"host={host!r} dll={ref!r} {'OK' if ok else 'FAIL'}"
        )
        if not ok:
            fail += 1

    # --- full mask ---
    n_bins = 4
    doubles = [
        [1.0, 2.0, 3.0, 4.0],
        [1.5, 2.5, 3.5, 4.5],
        [2.0, 3.0, 4.0, 5.0],
    ]
    # 2×2 RGB; divisor=100 → bins from sample codes
    s0 = np.array([[50, 150], [250, 350]], dtype=np.int16)
    s1 = np.array([[60, 160], [260, 360]], dtype=np.int16)
    s2 = np.array([[70, 170], [270, 370]], dtype=np.int16)
    r0 = np.array([[1, 2], [3, 4]], dtype=np.int16)
    r1 = np.array([[2, -1], [1, 2]], dtype=np.int16)
    r2 = np.array([[-1, 1], [2, -2]], dtype=np.int16)
    tau = 1.0
    host_m, host_ratio = ane.ane_color_correlation_mask_8950(
        [s0, s1, s2],
        [r0, r1, r2],
        doubles,
        pixel_offset=0,
        bin_divisor=100,
        max_bin=n_bins - 1,
        tau=tau,
    )
    dll_m, dll_ratio = run_corr_mask_8950(
        dll,
        [s0, s1, s2],
        [r0, r1, r2],
        doubles,
        pixel_offset=0,
        bin_divisor=100,
        max_bin=n_bins - 1,
        tau=tau,
    )
    ok_m = all(np.array_equal(host_m[p], dll_m[p]) for p in range(3))
    ok_r = host_ratio == dll_ratio
    print(
        f"  corr_mask 2x2: matches={int(host_m[0].sum())} "
        f"ratio host={host_ratio} dll={dll_ratio} "
        f"mask={'OK' if ok_m else 'FAIL'} ratio={'OK' if ok_r else 'FAIL'}"
    )
    if not ok_m or not ok_r:
        fail += 1
        for p in range(3):
            if not np.array_equal(host_m[p], dll_m[p]):
                print(f"    plane{p} host=\n{host_m[p]}\n    dll=\n{dll_m[p]}")

    # Tight tau → fewer matches
    tau2 = 0.05
    host_m2, host_r2 = ane.ane_color_correlation_mask_8950(
        [s0, s1, s2],
        [r0, r1, r2],
        doubles,
        pixel_offset=0,
        bin_divisor=100,
        max_bin=n_bins - 1,
        tau=tau2,
    )
    dll_m2, dll_r2 = run_corr_mask_8950(
        dll,
        [s0, s1, s2],
        [r0, r1, r2],
        doubles,
        pixel_offset=0,
        bin_divisor=100,
        max_bin=n_bins - 1,
        tau=tau2,
    )
    ok2 = all(np.array_equal(host_m2[p], dll_m2[p]) for p in range(3)) and (
        host_r2 == dll_r2
    )
    print(
        f"  corr_mask tau={tau2}: matches={int(host_m2[0].sum())} "
        f"{'OK' if ok2 else 'FAIL'}"
    )
    if not ok2:
        fail += 1

    # --- masked accum 8600 ---
    res_max = 8
    hist_off, hist_div, n_res = ane.ane_residual_hist_params(res_max)
    mask = host_m  # from tau=1.0 case
    host_h = ane.ane_empty_plane_dens_hists(3, n_bins, n_res)
    ane.ane_accumulate_masked_8600(
        host_h,
        [s0, s1, s2],
        [r0, r1, r2],
        mask,
        pixel_offset=0,
        bin_divisor=100,
        max_bin=n_bins - 1,
        hist_offset=hist_off,
        hist_divisor=hist_div,
    )
    dll_h = run_accum_8600(
        dll,
        [s0, s1, s2],
        [r0, r1, r2],
        mask,
        pixel_offset=0,
        bin_divisor=100,
        max_bin=n_bins - 1,
        hist_offset=hist_off,
        hist_divisor=hist_div,
        n_res_bins=n_res,
    )
    ok_h = host_h == dll_h
    nonzero = sum(c for p in host_h for b in p for c in b)
    print(
        f"  accum_8600: nonzero={nonzero} host==dll={ok_h} "
        f"{'OK' if ok_h else 'FAIL'}"
    )
    if not ok_h:
        fail += 1
        for p in range(3):
            for b in range(n_bins):
                if host_h[p][b] != dll_h[p][b]:
                    print(
                        f"    p{p}b{b} host={host_h[p][b]} dll={dll_h[p][b]}"
                    )

    # --- e9d0 use_avg smoke ---
    nt = ane.ane_build_noise_table_e9d0(
        [([s0, s1, s2], [r0, r1, r2])],
        n=16,
        code_value_min=0,
        code_value_max=399,
        code_value_bins=n_bins,
        res_max=res_max,
        tau=tau,
        use_masking=False,
        use_avg=True,
        merge_min_count=0,
        merge_max_radius=0,
    )
    ok_nt = nt.n == 16 and nt.n_channels == 2 and nt.dens.shape == (2, 16)
    print(
        f"  e9d0 use_avg=True → NoiseTable n={nt.n} ch={nt.n_channels} "
        f"{'OK' if ok_nt else 'FAIL'}"
    )
    if not ok_nt:
        fail += 1

    print(f"{'PASS' if fail == 0 else f'FAIL ({fail})'}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
