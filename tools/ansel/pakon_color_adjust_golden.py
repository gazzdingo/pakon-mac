#!/usr/bin/env python3
"""Golden ColorAdjust contrast LUT + unsharp kernel leaves vs PakonIMAu.dll.

Covers:

* identity fill ``0x100147ca…0x1001487b``
* contrast fill ``0x100147ed…0x1001487b`` (half ∈ samples)
* offset add ``0x100148a8…0x10014939``
* host ``build_contrast_luts_rgb`` skip / compose
* unsharp amount scale + kernel constants (rdata)
* kernel quantizer ``0x1030dbe0`` (Unicorn)
* separable unsharp apply host smoke (structure-cited)

Usage
-----
``PYTHONPATH=tools/ansel python3 tools/ansel/pakon_color_adjust_golden.py [dll]``
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_EBP,
    UC_X86_REG_EDI,
    UC_X86_REG_ESP,
)

import pakon_color_adjust as ca

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x100000
STUB_ADDR = 0x00100000

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


def _i16_list(raw: bytes) -> list[int]:
    return list(struct.unpack(f"<{len(raw) // 2}h", raw))


def run_fill(dll: bytes, contrast_half: int, *, clamp_mode: bool = True) -> list[int]:
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, dll)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    ebp = STACK_ADDR + 0x80000
    uc.reg_write(UC_X86_REG_EBP, ebp)
    uc.reg_write(UC_X86_REG_ESP, ebp - 0x7000)
    dest = ebp - 0x65AC
    uc.mem_write(ebp - 0x18, struct.pack("<I", 0 if clamp_mode else 1))
    uc.reg_write(UC_X86_REG_EAX, int(contrast_half))
    uc.reg_write(UC_X86_REG_EDI, dest)
    stop = ca.CONTRAST_LUT_FILL_END

    def hook(u: Uc, address: int, size: int, _user: object) -> None:
        if address == stop:
            u.emu_stop()

    uc.hook_add(UC_HOOK_CODE, hook, begin=stop, end=stop + 1)
    start = (
        ca.CONTRAST_LUT_IDENT_ENTRY
        if contrast_half == 0
        else ca.CONTRAST_LUT_FILL_ENTRY
    )
    try:
        uc.emu_start(start, 0, timeout=20_000_000)
    except UcError as e:
        raise RuntimeError(f"unicorn fill half={contrast_half}: {e}") from e
    return _i16_list(bytes(uc.mem_read(dest, ca.LUT_LEN * 2)))


def run_offset_add(dll: bytes, base: list[int], offset: int) -> list[int]:
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, dll)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    ebp = STACK_ADDR + 0x80000
    uc.reg_write(UC_X86_REG_EBP, ebp)
    uc.reg_write(UC_X86_REG_ESP, ebp - 0x7000)
    dest = ebp - 0x65AC
    uc.mem_write(dest, struct.pack(f"<{len(base)}h", *base))
    uc.reg_write(UC_X86_REG_EAX, int(offset))
    stop = 0x10014939

    def hook(u: Uc, address: int, size: int, _user: object) -> None:
        if address == stop:
            u.emu_stop()

    uc.hook_add(UC_HOOK_CODE, hook, begin=stop, end=stop + 1)
    try:
        uc.emu_start(ca.CONTRAST_OFFSET_ADD_ENTRY, 0, timeout=20_000_000)
    except UcError as e:
        raise RuntimeError(f"unicorn offset={offset}: {e}") from e
    return _i16_list(bytes(uc.mem_read(dest, ca.LUT_LEN * 2)))


def read_f64(dll: bytes, va: int) -> float:
    e_lfanew = struct.unpack_from("<I", dll, 0x3C)[0]
    num_sec = struct.unpack_from("<H", dll, e_lfanew + 6)[0]
    opt_size = struct.unpack_from("<H", dll, e_lfanew + 20)[0]
    opt = e_lfanew + 24
    sec_off = opt + opt_size
    rva = va - IMAGE_BASE
    for i in range(num_sec):
        o = sec_off + i * 40
        vsz, sva, rsz, raddr = struct.unpack_from("<IIII", dll, o + 8)
        if sva <= rva < sva + max(vsz, rsz):
            return struct.unpack_from("<d", dll, raddr + (rva - sva))[0]
    raise KeyError(hex(va))


def run_kernel_scale_dbe0(
    dll: bytes,
    coeffs: tuple[float, ...] | list[float],
    channels: int,
) -> tuple[int, int]:
    """Call ``0x1030dbe0(ptr, n, channels, out_S*, out_rounded*)``."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, dll)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(STUB_ADDR, 0x1000)
    arr = STACK_ADDR + 0x10000
    out_s = STACK_ADDR + 0x11000
    out_r = STACK_ADDR + 0x11004
    uc.mem_write(arr, b"".join(struct.pack("<d", float(c)) for c in coeffs))
    uc.mem_write(out_s, b"\0\0\0\0")
    uc.mem_write(out_r, b"\0\0\0\0")
    esp = STACK_ADDR + 0x80000
    # Args only — ``call`` pushes the return address.
    uc.mem_write(
        esp,
        struct.pack(
            "<IIIII",
            arr,
            len(coeffs),
            int(channels),
            out_s,
            out_r,
        ),
    )
    uc.reg_write(UC_X86_REG_ESP, esp)
    rel = ca.KERNEL_QUANT_LEAF - (STUB_ADDR + 5)
    stub = b"\xE8" + struct.pack("<i", rel) + b"\xCC"
    uc.mem_write(STUB_ADDR, stub)
    try:
        uc.emu_start(STUB_ADDR, STUB_ADDR + len(stub) - 1, timeout=50_000_000)
    except UcError as e:
        raise RuntimeError(f"unicorn dbe0 {coeffs}/{channels}: {e}") from e
    s = struct.unpack("<i", bytes(uc.mem_read(out_s, 4)))[0]
    r = struct.unpack("<i", bytes(uc.mem_read(out_r, 4)))[0]
    return s, r


def main(argv: list[str]) -> int:
    dll_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_DLL
    dll = dll_path.read_bytes()
    fails = 0

    assert ca.COLOR_ADJUST_CONTRAST_LUT_PORTED
    assert ca.COLOR_ADJUST_UNSHARP_PARAMS_PORTED
    assert ca.COLOR_ADJUST_UNSHARP_APPLY_PORTED
    assert ca.COLOR_ADJUST_DEFAULT_SKIP_PORTED
    assert ca.COLOR_ADJUST_SPCOMBINE_DEFAULT_IDENTITY
    assert not ca.COLOR_ADJUST_PORTED

    for half in (0, 100, -50, 500, 1):
        dll_lut = run_fill(dll, half, clamp_mode=True)
        host = ca.contrast_base_lut(half, clamp=True)
        ok = dll_lut == host
        print(
            f"  fill half={half}: {'OK' if ok else 'FAIL'} "
            f"dll[0]={dll_lut[0]} host[0]={host[0]} "
            f"[1550]={dll_lut[1550]}"
        )
        if not ok:
            fails += 1

    base = ca.contrast_base_lut(100, clamp=True)
    for off in (0, 100, -50, 250, -250):
        dll_o = run_offset_add(dll, base, off)
        host_o = ca.contrast_apply_offset(base, off)
        ok = dll_o == host_o
        print(
            f"  offset {off}: {'OK' if ok else 'FAIL'} "
            f"delta={ca.contrast_offset_delta(off)} "
            f"[1550] dll={dll_o[1550]} host={host_o[1550]}"
        )
        if not ok:
            fails += 1

    # Compose skip
    assert ca.build_contrast_luts_rgb(contrast=0) is None
    luts = ca.build_contrast_luts_rgb(contrast=200, red=100)
    assert luts is not None
    print(f"  compose contrast=200 red=100: OK lutR[1550]={luts[0][1550]}")

    # Default skip
    assert ca.is_default_skip(ca.ColorAdjustParams())
    assert not ca.is_default_skip(ca.ColorAdjustParams(contrast=200))
    assert not ca.is_default_skip(ca.ColorAdjustParams(sharpness=500))
    assert ca.is_default_skip(ca.ColorAdjustParams(contrast=200, gate=0))
    print("  default-skip gates: OK")

    # Unsharp constants from rdata
    assert abs(read_f64(dll, ca.F64_0_01) - ca.UNSHARP_AMOUNT_SCALE) < 1e-15
    assert abs(read_f64(dll, ca.F64_0_25) - 0.25) < 1e-15
    assert abs(read_f64(dll, ca.F64_0_5) - 0.5) < 1e-15
    assert abs(read_f64(dll, 0x10588EB8) - ca.UNSHARP_QUANT_BIAS) < 1e-15
    assert ca.unsharp_amount(500) == 5.0
    assert ca.UNSHARP_KERNEL_1D == (0.25, 0.5, 0.25)
    print("  unsharp params/consts: OK")

    # Kernel quantizer 0x1030dbe0
    for channels, coeffs in (
        (3, ca.UNSHARP_KERNEL_1D),
        (1, ca.UNSHARP_KERNEL_1D),
        (3, (1.0,)),
        (3, (2.0, 2.0, 2.0)),
        (1, (0.5, 0.5)),
    ):
        host_s, host_r = ca.kernel_scale_dbe0(coeffs, channels)
        dll_s, dll_r = run_kernel_scale_dbe0(dll, coeffs, channels)
        ok = (host_s, host_r) == (dll_s, dll_r)
        print(
            f"  dbe0 ch={channels} {coeffs}: "
            f"host=({host_s},{host_r}) dll=({dll_s},{dll_r}) "
            f"{'OK' if ok else 'FAIL'}"
        )
        if not ok:
            fails += 1

    k, sh = ca.unsharp_kernel_i16()
    assert k == (4096, 8192, 4096) and sh == 14
    print(f"  ColorAdjust kernel ints {k} shift {sh}: OK")

    # Preference helper identity on defaults
    import numpy as np

    img = np.arange(12, dtype=np.int16).reshape(2, 2, 3)
    out = ca.apply_preference_color_adjust_i16(img)
    assert np.array_equal(out, img)
    print("  preference default apply: OK")

    # Unsharp apply changes a mid-gray plate with a step edge (smoke)
    plate = np.full((8, 8, 3), 1000, dtype=np.int16)
    plate[:, 4:, :] = 2000
    sharp = ca.apply_preference_color_adjust_i16(
        plate, ca.ColorAdjustParams(sharpness=100)
    )
    assert sharp.dtype == np.int16
    assert not np.array_equal(sharp, plate)
    # Amount 1.0: edge pixels move away from blur (sharpen)
    assert int(sharp[3, 3, 0]) <= 1000 or int(sharp[3, 4, 0]) >= 2000
    print("  unsharp apply smoke: OK")

    if fails:
        print(f"FAILED ({fails})")
        return 1
    print("ColorAdjust contrast / unsharp golden: ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
