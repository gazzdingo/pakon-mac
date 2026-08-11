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
* ``kodakcms!SpCombineXforms`` @ ``0x1003c8f0`` → ``SpConnectSequenceEx``
  with flag ``0x103`` (wrapper Unicorn)
* ``SpConnectSequenceEx`` prologue ``n<2 → 0x206`` + out-param init
  (Unicorn)
* ConnectEx ``0x1002eca0`` 12-byte copy leaf (Unicorn)
* ConnectEx PT-type ``0x6b|0x132`` + ``Lab ``/`` XYZ`` tag gates (host face)
* ConnectEx ``flag & 0xf0`` dispatch + workspace ``2·n``/``4·n`` sizes
* Live ``SpXformGetRefNum`` validate → ``0`` on unity xform / ``0x1fb`` on null
  (``COLOR_ADJUST_SPCONNECT_VALIDATE_PORTED``)

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 tools/ansel/python-pipeline/pakon_color_adjust_golden.py [imau.dll]``
``# optional kodakcms path via env KODAKCMS_DLL``
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
    assert ca.COLOR_ADJUST_KODAKCMS_INIT_HARNESS
    assert ca.COLOR_ADJUST_KODAKCMS_LIVE_SPCOMBINE
    assert ca.COLOR_ADJUST_SPCONNECT_VALIDATE_PORTED
    assert ca.COLOR_ADJUST_SPCONNECT_FLAG_DISPATCH_PORTED
    assert ca.COLOR_ADJUST_SPCONNECT_MODE_PORTED
    assert ca.COLOR_ADJUST_SPCONNECT_PATH0_PORTED
    assert ca.COLOR_ADJUST_PTCOMBINE_GRID_PORTED
    assert ca.COLOR_ADJUST_PORTED
    assert ca.COLOR_ADJUST_PT_MERGE_BODY_PORTED

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

    # kodakcms SpCombineXforms thin wrapper → SpConnectSequenceEx(0x103, …)
    import os

    cms_path = Path(
        os.environ.get(
            "KODAKCMS_DLL",
            "/Users/guy/Downloads/Pakon Update 3/fx35install/System32/kodakcms.dll",
        )
    )
    if not cms_path.is_file():
        print(f"  SpCombine wrapper: SKIP (no {cms_path})")
        fails += 1
    else:
        cms = cms_path.read_bytes()
        probe = verify_spcombine_wrapper(cms)
        ok = (
            probe.get("entered") is True
            and probe.get("flag") == ca.KODAKCMS_SPCOMBINE_CONNECT_FLAG
            and probe.get("args") == (0x1111, 0x2222, 0x3333, 0x4444, 0x5555, 0x6666)
        )
        print(
            f"  SpCombine wrapper → ConnectEx flag={probe.get('flag')!r} "
            f"args={probe.get('args')} {'OK' if ok else 'FAIL'} "
            f"(WRAPPER_PORTED={ca.COLOR_ADJUST_SPCOMBINE_WRAPPER_PORTED})"
        )
        if not ok:
            fails += 1

    # host face of SpConnectSequenceEx early-out (always; no invented body)
    if ca.sp_combine_xforms_forwards_to_connect_ex(1) != ca.KODAKCMS_SPCONNECT_ERR_TOO_FEW:
        print("  SpCombine too-few host face: FAIL")
        fails += 1
    else:
        print("  SpCombine too-few host (n<2 → 0x206): OK")
    if ca.sp_combine_xforms_forwards_to_connect_ex(2) != 0:
        print("  SpCombine n>=2 identity status 0: FAIL")
        fails += 1
    else:
        print("  SpCombine n>=2 host status 0 (PORTED): OK")

    # SpConnectSequenceEx prologue Unicorn (n=0/1 → 0x206, *a2=0, *a3=-1)
    if cms_path.is_file():
        cms = cms_path.read_bytes()
        for n in (0, 1):
            probe = verify_spconnect_too_few(cms, n)
            host = ca.sp_connect_sequence_ex_prologue_outs(n)
            ok = (
                probe.get("eax") == ca.KODAKCMS_SPCONNECT_ERR_TOO_FEW
                and probe.get("a2") == ca.KODAKCMS_SPCONNECT_OUT_A2_INIT
                and probe.get("a3") == ca.KODAKCMS_SPCONNECT_OUT_A3_INIT
                and host == (
                    ca.KODAKCMS_SPCONNECT_ERR_TOO_FEW,
                    ca.KODAKCMS_SPCONNECT_OUT_A2_INIT,
                    ca.KODAKCMS_SPCONNECT_OUT_A3_INIT,
                )
            )
            print(
                f"  SpConnectEx n={n}: eax={probe.get('eax')!r} "
                f"*a2={probe.get('a2')!r} *a3={probe.get('a3')!r} "
                f"{'OK' if ok else 'FAIL'}"
            )
            if not ok:
                fails += 1
        host2 = ca.sp_connect_sequence_ex_prologue_outs(2)
        if host2 != (0, ca.KODAKCMS_SPCONNECT_OUT_A2_INIT, 1):
            print(f"  SpConnectEx n=2 host {host2}: FAIL")
            fails += 1
        else:
            print("  SpConnectEx n>=2 host status 0 *a3=1 (PORTED): OK")

        # copy12 leaf @ 0x1002eca0
        src = bytes(range(12)) + b"\xaa\xbb"
        dll_out = run_copy12(cms, src[:12])
        host_out = ca.sp_connect_copy12(src)
        ok = dll_out == host_out == src[:12]
        print(f"  SpConnect copy12: {'OK' if ok else 'FAIL'} {dll_out.hex()}")
        if not ok:
            fails += 1

        # PT / tag gates (host face of cited cmp)
        assert ca.sp_connect_pt_type_accepted(ca.KODAKCMS_PT_TYPE_OK_A)
        assert ca.sp_connect_pt_type_accepted(ca.KODAKCMS_PT_TYPE_OK_B)
        assert not ca.sp_connect_pt_type_accepted(0)
        assert ca.sp_connect_colorspace_tag_ok(ca.KODAKCMS_TAG_LAB)
        assert ca.sp_connect_colorspace_tag_ok(ca.KODAKCMS_TAG_XYZ)
        assert not ca.sp_connect_colorspace_tag_ok(0)
        print("  SpConnect PT-type / Lab|XYZ gates: OK")

        # flag&0xf0 dispatch + workspace sizes (host face of cited lea/and)
        assert ca.sp_connect_workspace_alloc_sizes(2) == (4, 8)
        assert ca.sp_connect_workspace_alloc_sizes(3) == (6, 12)
        assert (
            ca.sp_connect_flag_combiner_path(ca.KODAKCMS_SPCOMBINE_CONNECT_FLAG)
            == ca.KODAKCMS_SPCONNECT_COMBINE_PATH_0
        )
        assert ca.sp_connect_flag_combiner_path(0x103) == ca.KODAKCMS_SPCONNECT_COMBINE_PATH_0
        assert ca.sp_connect_flag_combiner_path(0x10) == ca.KODAKCMS_SPCONNECT_COMBINE_PATH_10
        assert ca.sp_connect_flag_combiner_path(0x20) == ca.KODAKCMS_SPCONNECT_COMBINE_PATH_20
        assert ca.sp_connect_flag_combiner_path(0x30) is None
        assert ca.sp_connect_validate_status_from_ref_and_type(0, 0x6B) is None
        assert (
            ca.sp_connect_validate_status_from_ref_and_type(0, 0)
            == ca.KODAKCMS_SPCONNECT_ERR_BAD_XFORM
        )
        assert (
            ca.sp_connect_validate_status_from_ref_and_type(0x1FB, 0x6B)
            == ca.KODAKCMS_SPCONNECT_ERR_BAD_XFORM
        )
        # mode encode @ 0x1002e420 — host vs Unicorn
        mode_ok = True
        for flag, expect in (
            (0, 0),
            (1, 4),
            (2, 5),
            (3, 6),
            (4, 7),
            (5, 6),
            (0x103, 0x406),
            (0x100, 0x400),
            (0x104, 0x407),
        ):
            host_m = ca.sp_connect_combine_mode_from_flag(flag)
            dll_m = run_combine_mode_from_flag(cms, flag)
            if host_m != expect or dll_m != expect:
                mode_ok = False
                print(f"  mode flag={flag:#x}: host={host_m:#x} dll={dll_m:#x} want={expect:#x} FAIL")
        assert ca.sp_connect_ptcombine_case_va(0x406) == ca.KODAKCMS_PTCOMBINE_CASE_SHARED
        assert ca.sp_connect_ptcombine_case_va(0x106) == ca.KODAKCMS_PTCOMBINE_CASE_SHARED
        assert ca.sp_connect_ptcombine_case_va(0) == 0x1003FDDE
        assert ca.sp_connect_ptcombine_case_va(8) is None

        # path_0 + PTCombine+0x460 grid leaves
        mode, chain_va = ca.sp_connect_path0_chain_first(0x103)
        assert mode == 0x406
        assert chain_va == ca.KODAKCMS_SPCONNECT_COMBINE_PATH_10_TAIL
        assert ca.ptcombine_pt_type_uses_abs_handle(0x10007)
        assert ca.ptcombine_pt_type_uses_abs_handle(0x20007)
        assert ca.ptcombine_pt_type_uses_abs_handle(0x1001F)
        assert not ca.ptcombine_pt_type_uses_abs_handle(0)
        assert ca.ptcombine_grid_base_for_mode_low(0x406) == 0x40
        assert ca.ptcombine_grid_base_for_mode_low(0x405) == 0x40
        assert ca.ptcombine_grid_base_for_mode_low(0x404) is None
        assert ca.ptcombine_grid_base_for_mode_low(0x403) is None
        grid_ok = True
        for esi, want_q in ((8, 7), (16, 14), (64, 57), (0x40, 57)):
            q = ca.ptcombine_grid_scaled_quot(esi)
            if q != want_q:
                grid_ok = False
                print(f"  grid quot esi={esi}: {q} want {want_q} FAIL")
        assert ca.ptcombine_grid_fill_inc(7, 8) == 8
        assert ca.ptcombine_grid_fill_inc(14, 8) == 15
        assert ca.ptcombine_grid_fill_inc(0, 8) == 1
        assert ca.ptcombine_div1000(900) == 0
        assert ca.ptcombine_div1000(1000) == 1
        assert ca.ptcombine_div1000(1999) == 1

        # After-grid control leaves (@ 0x100403b6…)
        assert ca.COLOR_ADJUST_PTCOMBINE_AFTER_GRID_PORTED
        assert ca.ptcombine_mode_has_400(0x406)
        assert not ca.ptcombine_mode_has_800(0x406)
        assert ca.ptchain_init_or_mode_800(0x406) == 0xC06
        assert ca.ptcombine_mode_has_800(0xC06)
        assert ca.ptcombine_skip_type_switch(0xC06)
        assert not ca.ptcombine_skip_type_switch(0x406)
        assert ca.ptcombine_esi_after_400_max(0x406, 19, 8) == 19
        assert ca.ptcombine_esi_after_400_max(0x406, 8, 19) == 19
        assert ca.ptcombine_esi_after_400_max(0x006, 8, 19) == 8
        assert ca.ptcombine_esi_floor_for_mode(0xC06, 8) == 0x10
        assert ca.ptcombine_esi_floor_for_mode(0xC06, 19) == 19
        assert ca.ptcombine_esi_floor_for_mode(0x406, 4) == 8
        assert ca.ptcombine_channel_pack(3) == 0x0303
        assert ca.ptcombine_channel_pack(0x103) == 0x0303
        assert ca.ptcombine_type_switch_case_va(2) == 0x10040411  # idx0 → case0
        assert ca.ptcombine_type_switch_case_va(5) == 0x100404B5  # idx3 → case1
        assert ca.ptcombine_type_switch_case_va(8) == 0x100404FC  # idx6 → case2
        assert ca.ptcombine_type_switch_case_va(9) == 0x100403FA  # idx7 → case3
        assert ca.ptcombine_type_switch_case_va(3) == 0x1004053E  # idx1 → case4
        assert ca.ptcombine_type_switch_case_va(0x100) == 0x1004053E  # >0x24
        assert ca.ptcombine_merge_type_gate(0x1001F) == "esp18"
        assert ca.ptcombine_merge_type_gate(0x2001F) == "ebp"
        assert ca.ptcombine_merge_type_gate(0) == "other"
        assert ca.ptgetptinfo_2110_early_identity(True)
        assert not ca.ptgetptinfo_2110_early_identity(False)
        # +0x2110 rebuild control leaves
        assert ca.COLOR_ADJUST_PTGETPTINFO_2110_REBUILD_PORTED
        assert ca.ptgetptinfo_2110_ctuf_mask_bit(0) == 1
        assert ca.ptgetptinfo_2110_ctuf_mask_bit(2) == 4
        assert ca.ptgetptinfo_2110_rebuild_pack(7, 7) == 0x707
        assert ca.ptgetptinfo_2110_rebuild_pack(0x1F, 3) == 0x1F03
        assert ca.ptgetptinfo_2110_slot_bit_set(7, 0)
        assert ca.ptgetptinfo_2110_slot_bit_set(7, 2)
        assert not ca.ptgetptinfo_2110_slot_bit_set(7, 3)
        assert ca.ptgetptinfo_2110_bad_magic_returns_null(0)
        assert ca.ptgetptinfo_2110_bad_magic_returns_null(0x1234)
        assert not ca.ptgetptinfo_2110_bad_magic_returns_null(ca.KODAKCMS_PT_MAGIC_FTUF)
        # +0x930 control leaves
        assert ca.COLOR_ADJUST_PTGETPTINFO_930_PORTED
        assert ca.ptgetptinfo_930_unpack_pack(0x707) == (7, 7, 0)
        assert ca.ptgetptinfo_930_unpack_pack(0x1F000307) == (7, 3, 0xF)
        assert ca.ptgetptinfo_930_unpack_pack(0x05000000) == (0, 0, 5)
        assert ca.ptgetptinfo_930_bytes_in_range(7, 7)
        assert not ca.ptgetptinfo_930_bytes_in_range(0x100, 0)
        assert ca.ptgetptinfo_930_sparse_gather(0x7, [0xA, 0xB, 0xC]) == [
            0xA,
            0xB,
            0xC,
            0,
            0,
            0,
            0,
            0,
        ]
        assert ca.ptgetptinfo_930_sparse_gather(0x5, [0xA, 0xB]) == [
            0xA,
            0,
            0xB,
            0,
            0,
            0,
            0,
            0,
        ]
        assert ca.ptgetptinfo_930_sparse_gather(0x7, None) == [0] * 8
        assert ca.ptgetptinfo_930_insert_top_nibble(0, 0x707) == 0
        assert ca.ptgetptinfo_930_insert_top_nibble(0, 0x05000000) == 0x05000000
        assert ca.ptgetptinfo_930_insert_top_nibble(0x0A000000, 0x03000000) == 0x03000000
        assert ca.ptgetptinfo_930_or_ituf_bit(0, 0) == 1
        assert ca.ptgetptinfo_930_or_ituf_bit(1, 1) == 3
        assert ca.ptgetptinfo_930_or_ituf_bit(0x700, 2) == 0x704
        assert ca.ptgetptinfo_930_ituf_accepted(ca.KODAKCMS_PT_MAGIC_ITUF)
        assert not ca.ptgetptinfo_930_ituf_accepted(ca.KODAKCMS_PT_MAGIC_FTUF)
        # +0xe80 / +0xf80 attach leaves
        assert ca.COLOR_ADJUST_PTGETPTINFO_E80_PORTED
        assert ca.ptgetptinfo_bit_index(1) == 0
        assert ca.ptgetptinfo_bit_index(2) == 1
        assert ca.ptgetptinfo_bit_index(4) == 2
        assert ca.ptgetptinfo_bit_index(0x80) == 7
        assert ca.ptgetptinfo_bit_index(0) == -1
        assert ca.ptgetptinfo_bit_index(-3) == -1
        assert ca.ptgetptinfo_f80_or_plus8(0, 0, 7) == 0x107
        assert ca.ptgetptinfo_f80_or_plus8(0x107, 1, 7) == 0x307
        assert ca.ptgetptinfo_f80_or_plus8(0x307, 2, 7) == 0x707
        assert ca.ptgetptinfo_e80_ftuf_gate(ca.KODAKCMS_PT_MAGIC_FTUF)
        assert not ca.ptgetptinfo_e80_ftuf_gate(0)
        # +0xaa0 / +0xc40 / +0xae0 / +0x3630 / +0x7aa0 prologue
        assert ca.COLOR_ADJUST_PTGETPTINFO_AA0_PORTED
        assert ca.COLOR_ADJUST_PTGETPTINFO_C40_PORTED
        assert ca.COLOR_ADJUST_PTCOMBINE_AE0_PORTED
        assert ca.COLOR_ADJUST_PTGETPTINFO_3630_PORTED
        assert ca.COLOR_ADJUST_PTGETPTINFO_7AA0_PROLOGUE_PORTED
        assert ca.ptgetptinfo_9fa0_gtuf_mask([0, 1, 2, 19, 0, 0, 0, 0]) == 0xC
        assert ca.ptgetptinfo_aa0_dim_gate(19, 19)
        assert not ca.ptgetptinfo_aa0_dim_gate(17, 19)
        assert ca.ptgetptinfo_c40_dim_ok(2)
        assert ca.ptgetptinfo_c40_dim_ok(0x40)
        assert not ca.ptgetptinfo_c40_dim_ok(1)
        assert not ca.ptgetptinfo_c40_dim_ok(0x41)
        assert ca.ptgetptinfo_c40_size_code(2) == 0x203
        assert ca.ptgetptinfo_c40_size_code(0) == 0x100
        assert ca.ptcombine_ae0_status(False) == (0x130, None)
        assert ca.ptcombine_ae0_status(True)[0] == 1
        assert ca.ptgetptinfo_3630_status_for_first_dim(19) == 1
        assert ca.ptgetptinfo_3630_status_for_first_dim(0x100) == -1
        assert ca.ptgetptinfo_3630_max_dim([8, 19, 12]) == 19
        assert ca.ptgetptinfo_3630_dim_mismatch(1, [19, 19, 19]) == 1
        assert ca.ptgetptinfo_3630_dim_mismatch(1, [19, 17]) == -2
        assert ca.ptgetptinfo_7aa0_merge_pack(0, 0x07, 0x07) == 0x0707
        assert ca.ptgetptinfo_7aa0_merge_pack(0x00000500, 0x07, 0x07) == 0x0507
        assert ca.ptgetptinfo_7aa0_merge_pack(0x00010500, 0x07, 0x07) == 0x010507
        # +0x1140 / +0x1230 / +0x9820 / +0x7aa0 merge-body control
        assert ca.COLOR_ADJUST_PT_MERGE_BODY_PORTED
        assert ca.ptgetptinfo_1140_alloc_size(ca.KODAKCMS_PT_MAGIC_ITUF) == 0x404
        assert ca.ptgetptinfo_1140_alloc_size(ca.KODAKCMS_PT_MAGIC_FTUF) is None
        assert ca.ptgetptinfo_1230_alloc_bytes(ca.KODAKCMS_PT_MAGIC_ITUF, 19) == 38
        assert ca.ptgetptinfo_1230_alloc_bytes(0, 19) is None
        assert ca.ptgetptinfo_c40_uses_1140(1)
        assert not ca.ptgetptinfo_c40_uses_1140(0)
        assert abs(ca.ptgetptinfo_9820_step(5) - 0.25) < 1e-15
        assert ca.ptgetptinfo_9820_null_callback_skips_fill(0)
        assert not ca.ptgetptinfo_9820_null_callback_skips_fill(0x1000)
        id5 = ca.ptgetptinfo_9820_fill_identity(5)
        assert id5 == [0, 16384, 32768, 49151, 65535]
        assert ca.ptgetptinfo_7aa0_ftuf_gate(
            ca.KODAKCMS_PT_MAGIC_FTUF, ca.KODAKCMS_PT_MAGIC_FTUF
        )
        assert not ca.ptgetptinfo_7aa0_ftuf_gate(
            ca.KODAKCMS_PT_MAGIC_ITUF, ca.KODAKCMS_PT_MAGIC_FTUF
        )
        assert ca.ptgetptinfo_7aa0_slot_bit(0x05, 0)
        assert not ca.ptgetptinfo_7aa0_slot_bit(0x05, 1)
        assert ca.ptgetptinfo_7aa0_slot_bit(0x05, 2)
        assert ca.ptgetptinfo_7aa0_max_dim(17, 19) == 19
        assert ca.ptgetptinfo_7aa0_max_dim(19, 17) == 19
        assert ca.ptgetptinfo_7aa0_alloc_to_bool(0) == 0
        assert ca.ptgetptinfo_7aa0_alloc_to_bool(0x3000) == 1
        assert ca.ptgetptinfo_7aa0_sample_gates(
            ca.KODAKCMS_PT_MAGIC_ITUF,
            ca.KODAKCMS_PT_MAGIC_OTUF,
            ca.KODAKCMS_PT_MAGIC_ITUF,
            17,
            19,
        )
        assert not ca.ptgetptinfo_7aa0_sample_gates(
            ca.KODAKCMS_PT_MAGIC_ITUF,
            ca.KODAKCMS_PT_MAGIC_OTUF,
            ca.KODAKCMS_PT_MAGIC_ITUF,
            20,
            19,
        )
        try:
            import pakon_kcms_unicorn as kcms

            path_ok = _golden_live_path0_chain(kcms)
            after_ok = _golden_live_after_grid_800(kcms)
            rebuild_ok = _golden_live_2110_rebuild(kcms)
            p930_ok = _golden_live_930(kcms)
            e80_ok = _golden_live_e80(kcms)
            p9820_ok = _golden_live_9820_identity(kcms)
        except Exception as e:
            path_ok = False
            after_ok = False
            rebuild_ok = False
            p930_ok = False
            e80_ok = False
            p9820_ok = False
            print(f"  path0/after/rebuild/930/e80/9820 live: SKIP ({e})")
        print(
            f"  SpConnect flag/mode/path0/grid/after/rebuild/930/e80/9820: "
            f"{'OK' if mode_ok and grid_ok and path_ok and after_ok and rebuild_ok and p930_ok and e80_ok and p9820_ok else 'FAIL'} "
            f"(mode={mode_ok} grid={grid_ok} path0={path_ok} "
            f"after={after_ok} rebuild={rebuild_ok} 930={p930_ok} e80={e80_ok} "
            f"9820={p9820_ok})"
        )
        if not (
            mode_ok
            and grid_ok
            and path_ok
            and after_ok
            and rebuild_ok
            and p930_ok
            and e80_ok
            and p9820_ok
        ):
            fails += 1

        # Live GetRefNum on unity xform (requires kodakcms IAT harness)
        try:
            import pakon_kcms_unicorn as kcms

            live_ok = _golden_live_validate_refnum(kcms)
            print(
                f"  SpConnect live GetRefNum validate: "
                f"{'OK' if live_ok else 'FAIL'}"
            )
            if not live_ok:
                fails += 1
        except Exception as e:
            print(f"  SpConnect live GetRefNum validate: SKIP ({e})")
    else:
        print("  SpConnectEx prologue Unicorn: SKIP")
        fails += 1

    assert ca.COLOR_ADJUST_CONTRAST_LUT_PORTED
    assert ca.COLOR_ADJUST_UNSHARP_PARAMS_PORTED
    assert ca.COLOR_ADJUST_UNSHARP_APPLY_PORTED
    assert ca.COLOR_ADJUST_DEFAULT_SKIP_PORTED
    assert ca.COLOR_ADJUST_SPCOMBINE_DEFAULT_IDENTITY
    assert ca.COLOR_ADJUST_SPCOMBINE_WRAPPER_PORTED
    assert ca.COLOR_ADJUST_SPCONNECT_PROLOGUE_PORTED
    assert ca.COLOR_ADJUST_SPCONNECT_COPY12_PORTED
    assert ca.COLOR_ADJUST_SPCONNECT_VALIDATE_PORTED
    assert ca.COLOR_ADJUST_SPCONNECT_FLAG_DISPATCH_PORTED
    assert ca.COLOR_ADJUST_SPCONNECT_MODE_PORTED
    assert ca.COLOR_ADJUST_SPCONNECT_PATH0_PORTED
    assert ca.COLOR_ADJUST_PTCOMBINE_GRID_PORTED
    assert ca.COLOR_ADJUST_PTCOMBINE_AFTER_GRID_PORTED
    assert ca.COLOR_ADJUST_PTGETPTINFO_2110_REBUILD_PORTED
    assert ca.COLOR_ADJUST_PTGETPTINFO_930_PORTED
    assert ca.COLOR_ADJUST_PTGETPTINFO_E80_PORTED
    assert ca.COLOR_ADJUST_PTGETPTINFO_AA0_PORTED
    assert ca.COLOR_ADJUST_PTGETPTINFO_C40_PORTED
    assert ca.COLOR_ADJUST_PTCOMBINE_AE0_PORTED
    assert ca.COLOR_ADJUST_PTGETPTINFO_3630_PORTED
    assert ca.COLOR_ADJUST_PTGETPTINFO_7AA0_PROLOGUE_PORTED
    assert ca.COLOR_ADJUST_PT_MERGE_BODY_PORTED
    assert ca.COLOR_ADJUST_KODAKCMS_LIVE_SPCOMBINE
    assert ca.COLOR_ADJUST_PORTED

    if fails:
        print(f"FAILED ({fails})")
        return 1
    print(
        "ColorAdjust contrast / unsharp / SpCombine-wrapper / "
        "SpConnect-prologue / copy12 golden: ALL OK"
    )
    return 0


def verify_spcombine_wrapper(cms: bytes) -> dict:
    """Unicorn: SpCombineXforms @ 0x1003c8f0 forwards to ConnectEx with 0x103."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, cms)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    hit: dict = {"entered": False}

    def on_code(u: Uc, address: int, size: int, _user: object) -> None:
        if address != ca.KODAKCMS_SP_CONNECT_SEQUENCE_EX:
            return
        esp = u.reg_read(UC_X86_REG_ESP)
        # after CALL: [esp]=ret, [esp+4]=0x103, [esp+8…]=six SpCombine args
        flag = struct.unpack_from("<I", u.mem_read(esp + 4, 4))[0]
        args = struct.unpack_from("<6I", u.mem_read(esp + 8, 24))
        hit["entered"] = True
        hit["flag"] = flag
        hit["args"] = args
        u.emu_stop()

    uc.hook_add(UC_HOOK_CODE, on_code)
    esp = STACK_ADDR + 0x80000
    args = (0x1111, 0x2222, 0x3333, 0x4444, 0x5555, 0x6666)
    stop = STUB_ADDR
    uc.mem_map(STUB_ADDR, 0x1000)
    uc.mem_write(STUB_ADDR, b"\xcc")
    # stack layout for call: [ret][a0][a1][a2][a3][a4][a5]
    payload = struct.pack("<I", stop) + struct.pack("<6I", *args)
    esp -= len(payload)
    uc.mem_write(esp, payload)
    uc.reg_write(UC_X86_REG_ESP, esp)
    try:
        uc.emu_start(ca.KODAKCMS_SP_COMBINE_XFORMS, stop, count=200)
    except UcError:
        pass
    return hit


def verify_spconnect_too_few(cms: bytes, n: int) -> dict:
    """Unicorn: SpConnectSequenceEx @ 0x1002e740 with n<2 → eax 0x206."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, cms)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(STUB_ADDR, 0x1000)
    uc.mem_write(STUB_ADDR, b"\xc3")  # ret
    buf = 0x20000000
    uc.mem_map(buf, 0x1000)
    xforms = buf
    a2 = buf + 0x100
    a3 = buf + 0x104
    uc.mem_write(a2, b"\xee\xee\xee\xee")
    uc.mem_write(a3, b"\xee\xee\xee\xee")
    esp = STACK_ADDR + 0x80000
    # stdcall: flag + a0..a5; ret 0x1c
    args = (
        ca.KODAKCMS_SPCOMBINE_CONNECT_FLAG,
        int(n),
        xforms,
        a2,
        a3,
        0,
        0,
    )
    payload = struct.pack("<I", STUB_ADDR) + struct.pack("<7I", *args)
    esp -= len(payload)
    uc.mem_write(esp, payload)
    uc.reg_write(UC_X86_REG_ESP, esp)
    try:
        uc.emu_start(ca.KODAKCMS_SP_CONNECT_SEQUENCE_EX, STUB_ADDR, count=500)
    except UcError as e:
        return {"error": str(e)}
    return {
        "eax": uc.reg_read(UC_X86_REG_EAX),
        "a2": struct.unpack("<I", bytes(uc.mem_read(a2, 4)))[0],
        "a3": struct.unpack("<I", bytes(uc.mem_read(a3, 4)))[0],
    }


def _golden_live_path0_chain(kcms: object) -> bool:
    """Live unity SpCombine: path_0 → PTChain* → PTCombine inside Chain.

    Confirms ``@ 0x1002e490`` then ``@ 0x1002e5a0`` / ``PTChainInitM`` /
    ``PTChain`` / ``PTChainEnd``, with ``PTCombine`` entered from Chain
    (not requiring path_0 pairwise fallback), and Sp status ``0``.
    """
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_EAX

    pe = kcms.DEFAULT_CMS.read_bytes()
    unity = kcms.DEFAULT_UNITY.read_bytes()
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    kcms.load_pe(uc, pe)
    uc.mem_map(kcms.STACK_ADDR, kcms.STACK_SIZE)
    uc.mem_map(kcms.HEAP_ADDR, kcms.HEAP_SIZE)
    uc.mem_map(kcms.PROFILE_BUF, kcms._align_up(len(unity) + 0x1000))
    uc.mem_write(kcms.PROFILE_BUF, unity)
    host = kcms.KcmsHost(uc)
    kcms.install_iat(uc, host)
    kcms.call_stdcall(uc, kcms.BUF_OPS_INSTALL)
    out_init = host.alloc(4)
    uc.mem_write(out_init, b"\x00" * 4)
    kcms.patch_spinitialize_out_write(uc, out_init)
    if kcms.call_stdcall(uc, kcms.SP_INITIALIZE, 0, 0, out_init) != 0:
        return False
    call_h = struct.unpack("<I", uc.mem_read(out_init, 4))[0]
    out_prof = host.alloc(4)
    uc.mem_write(out_prof, b"\x00" * 4)
    if (
        kcms.call_stdcall(
            uc, kcms.SP_PROFILE_LOAD_FROM_BUFFER, call_h, kcms.PROFILE_BUF, out_prof
        )
        != 0
    ):
        return False
    prof = struct.unpack("<I", uc.mem_read(out_prof, 4))[0]
    out_xf = host.alloc(4)
    uc.mem_write(out_xf, b"\x00" * 4)
    if kcms.call_stdcall(uc, kcms.SP_XFORM_GET, prof, 0, 1, out_xf) != 0:
        return False
    xf = struct.unpack("<I", uc.mem_read(out_xf, 4))[0]
    hits: dict[str, int] = {
        "path0": 0,
        "chain5a0": 0,
        "chaininit": 0,
        "ptchain": 0,
        "chainend": 0,
        "ptcombine": 0,
    }

    def on_code(u, address, size, _user):
        if address == ca.KODAKCMS_SPCONNECT_COMBINE_PATH_0:
            hits["path0"] += 1
        elif address == ca.KODAKCMS_SPCONNECT_COMBINE_PATH_10_TAIL:
            hits["chain5a0"] += 1
        elif address == ca.KODAKCMS_PT_CHAIN_INIT_M:
            hits["chaininit"] += 1
        elif address == ca.KODAKCMS_PT_CHAIN:
            hits["ptchain"] += 1
        elif address == ca.KODAKCMS_PT_CHAIN_END:
            hits["chainend"] += 1
        elif address == ca.KODAKCMS_PT_COMBINE:
            hits["ptcombine"] += 1

    for a in (
        ca.KODAKCMS_SPCONNECT_COMBINE_PATH_0,
        ca.KODAKCMS_SPCONNECT_COMBINE_PATH_10_TAIL,
        ca.KODAKCMS_PT_CHAIN_INIT_M,
        ca.KODAKCMS_PT_CHAIN,
        ca.KODAKCMS_PT_CHAIN_END,
        ca.KODAKCMS_PT_COMBINE,
    ):
        uc.hook_add(UC_HOOK_CODE, on_code, begin=a, end=a + 1)

    arr = host.alloc(8)
    uc.mem_write(arr, struct.pack("<II", xf, xf))
    a2 = host.alloc(4)
    a3 = host.alloc(4)
    st = kcms.call_stdcall(
        uc, ca.KODAKCMS_SP_COMBINE_XFORMS, 2, arr, a2, a3, 0, 0
    )
    return (
        st == 0
        and hits["path0"] >= 1
        and hits["chain5a0"] >= 1
        and hits["chaininit"] >= 1
        and hits["ptchain"] >= 1
        and hits["chainend"] >= 1
        and hits["ptcombine"] >= 1
    )


def _golden_live_after_grid_800(kcms: object) -> bool:
    """Live unity SpCombine: ``PTChainInitM`` OR ``0x800`` → skip type switch.

    ``+0x460`` receives mode ``0xc06``; takes ``@ 0x100403d2`` (not the type
    switch); ``PTGetPTInfo+0x2110`` early-identity ``@ 0x1000c9b3``.
    """
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI

    pe = kcms.DEFAULT_CMS.read_bytes()
    unity = kcms.DEFAULT_UNITY.read_bytes()
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    kcms.load_pe(uc, pe)
    uc.mem_map(kcms.STACK_ADDR, kcms.STACK_SIZE)
    uc.mem_map(kcms.HEAP_ADDR, kcms.HEAP_SIZE)
    uc.mem_map(kcms.PROFILE_BUF, kcms._align_up(len(unity) + 0x1000))
    uc.mem_write(kcms.PROFILE_BUF, unity)
    host = kcms.KcmsHost(uc)
    kcms.install_iat(uc, host)
    kcms.call_stdcall(uc, kcms.BUF_OPS_INSTALL)
    out_init = host.alloc(4)
    uc.mem_write(out_init, b"\x00" * 4)
    kcms.patch_spinitialize_out_write(uc, out_init)
    if kcms.call_stdcall(uc, kcms.SP_INITIALIZE, 0, 0, out_init) != 0:
        return False
    call_h = struct.unpack("<I", uc.mem_read(out_init, 4))[0]
    out_prof = host.alloc(4)
    uc.mem_write(out_prof, b"\x00" * 4)
    if (
        kcms.call_stdcall(
            uc, kcms.SP_PROFILE_LOAD_FROM_BUFFER, call_h, kcms.PROFILE_BUF, out_prof
        )
        != 0
    ):
        return False
    prof = struct.unpack("<I", uc.mem_read(out_prof, 4))[0]
    out_xf = host.alloc(4)
    uc.mem_write(out_xf, b"\x00" * 4)
    if kcms.call_stdcall(uc, kcms.SP_XFORM_GET, prof, 0, 1, out_xf) != 0:
        return False
    xf = struct.unpack("<I", uc.mem_read(out_xf, 4))[0]
    hits: dict[str, int] = {
        "or800": 0,
        "plus460": 0,
        "skip800": 0,
        "typeswitch": 0,
        "early_id": 0,
        "rebuild": 0,
        "mode": 0,
    }

    def on_code(u, address, size, _user):
        if address == ca.KODAKCMS_PTCHAIN_INIT_OR_800:
            hits["or800"] += 1
        elif address == ca.KODAKCMS_PTCOMBINE_PLUS_460:
            hits["plus460"] += 1
            esp = u.reg_read(UC_X86_REG_ESP)
            # cdecl args after ret: [esp+4]=ptA … mode is 5th → +20
            hits["mode"] = struct.unpack("<I", bytes(u.mem_read(esp + 4 + 16, 4)))[0]
        elif address == 0x100403D2:
            hits["skip800"] += 1
        elif address == 0x100403DB:
            hits["typeswitch"] += 1
        elif address == ca.KODAKCMS_PTGETPTINFO_2110_EARLY_ID:
            hits["early_id"] += 1
            hits["early_esi"] = u.reg_read(UC_X86_REG_ESI)
        elif address == 0x1000C9BD:
            hits["rebuild"] += 1

    for a in (
        ca.KODAKCMS_PTCHAIN_INIT_OR_800,
        ca.KODAKCMS_PTCOMBINE_PLUS_460,
        0x100403D2,
        0x100403DB,
        ca.KODAKCMS_PTGETPTINFO_2110_EARLY_ID,
        0x1000C9BD,
    ):
        uc.hook_add(UC_HOOK_CODE, on_code, begin=a, end=a + 1)

    arr = host.alloc(8)
    uc.mem_write(arr, struct.pack("<II", xf, xf))
    a2 = host.alloc(4)
    a3 = host.alloc(4)
    st = kcms.call_stdcall(
        uc, ca.KODAKCMS_SP_COMBINE_XFORMS, 2, arr, a2, a3, 0, 0
    )
    return (
        st == 0
        and hits["or800"] >= 1
        and hits["plus460"] >= 1
        and hits["mode"] == 0xC06
        and ca.ptcombine_skip_type_switch(hits["mode"])
        and hits["skip800"] >= 1
        and hits["typeswitch"] == 0
        and hits["early_id"] >= 1
        and hits["rebuild"] == 0
        and ca.ptgetptinfo_2110_early_identity(True)
    )


def _golden_live_2110_rebuild(kcms: object) -> bool:
    """Force dim mismatch inside live ``+0x2110`` → rebuild pack ``0x707``.

    Patches the dims buffer at ``+0x2110`` entry from ``19``→``17`` so unity
    SpCombine takes ``@ 0x1000c9bd``; host pack must match DLL eax.
    """
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_ESP

    pe = kcms.DEFAULT_CMS.read_bytes()
    unity = kcms.DEFAULT_UNITY.read_bytes()
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    kcms.load_pe(uc, pe)
    uc.mem_map(kcms.STACK_ADDR, kcms.STACK_SIZE)
    uc.mem_map(kcms.HEAP_ADDR, kcms.HEAP_SIZE)
    uc.mem_map(kcms.PROFILE_BUF, kcms._align_up(len(unity) + 0x1000))
    uc.mem_write(kcms.PROFILE_BUF, unity)
    host = kcms.KcmsHost(uc)
    kcms.install_iat(uc, host)
    kcms.call_stdcall(uc, kcms.BUF_OPS_INSTALL)
    out_init = host.alloc(4)
    uc.mem_write(out_init, b"\x00" * 4)
    kcms.patch_spinitialize_out_write(uc, out_init)
    if kcms.call_stdcall(uc, kcms.SP_INITIALIZE, 0, 0, out_init) != 0:
        return False
    call_h = struct.unpack("<I", uc.mem_read(out_init, 4))[0]
    out_prof = host.alloc(4)
    uc.mem_write(out_prof, b"\x00" * 4)
    if (
        kcms.call_stdcall(
            uc, kcms.SP_PROFILE_LOAD_FROM_BUFFER, call_h, kcms.PROFILE_BUF, out_prof
        )
        != 0
    ):
        return False
    prof = struct.unpack("<I", uc.mem_read(out_prof, 4))[0]
    out_xf = host.alloc(4)
    uc.mem_write(out_xf, b"\x00" * 4)
    if kcms.call_stdcall(uc, kcms.SP_XFORM_GET, prof, 0, 1, out_xf) != 0:
        return False
    xf = struct.unpack("<I", uc.mem_read(out_xf, 4))[0]
    hits: dict = {
        "patched": False,
        "early": 0,
        "rebuild": 0,
        "pack": None,
        "mask": None,
        "ch": None,
        "call930": 0,
        "call9530": 0,
        "call7aa0": 0,
    }

    def on_code(u, address, size, _user):
        if address == ca.KODAKCMS_PTGETPTINFO_2110:
            if hits["patched"]:
                return
            esp = u.reg_read(UC_X86_REG_ESP)
            dims = struct.unpack("<I", bytes(u.mem_read(esp + 8, 4)))[0]
            u.mem_write(dims, struct.pack("<8I", *([17] * 8)))
            hits["patched"] = True
        elif address == ca.KODAKCMS_PTGETPTINFO_2110_EARLY_ID:
            hits["early"] += 1
        elif address == ca.KODAKCMS_PTGETPTINFO_2110_REBUILD:
            hits["rebuild"] += 1
        elif address == 0x1000C9DE:
            hits["pack"] = u.reg_read(UC_X86_REG_EAX)
            hits["ch"] = u.reg_read(UC_X86_REG_EBP) & 0xFF
            # four args already pushed; original [esp+0x10] → [esp+0x20]
            esp = u.reg_read(UC_X86_REG_ESP)
            hits["mask"] = struct.unpack("<I", bytes(u.mem_read(esp + 0x20, 4)))[0]
        elif address == ca.KODAKCMS_PTGETPTINFO_930:
            hits["call930"] += 1
        elif address == ca.KODAKCMS_PTGETPTINFO_9530:
            hits["call9530"] += 1
        elif address == ca.KODAKCMS_PTGETPTINFO_7AA0:
            hits["call7aa0"] += 1

    for a in (
        ca.KODAKCMS_PTGETPTINFO_2110,
        ca.KODAKCMS_PTGETPTINFO_2110_EARLY_ID,
        ca.KODAKCMS_PTGETPTINFO_2110_REBUILD,
        0x1000C9DE,
        ca.KODAKCMS_PTGETPTINFO_930,
        ca.KODAKCMS_PTGETPTINFO_9530,
        ca.KODAKCMS_PTGETPTINFO_7AA0,
    ):
        uc.hook_add(UC_HOOK_CODE, on_code, begin=a, end=a + 1)

    arr = host.alloc(8)
    uc.mem_write(arr, struct.pack("<II", xf, xf))
    a2 = host.alloc(4)
    a3 = host.alloc(4)
    st = kcms.call_stdcall(
        uc, ca.KODAKCMS_SP_COMBINE_XFORMS, 2, arr, a2, a3, 0, 0
    )
    if hits["pack"] is None or hits["mask"] is None or hits["ch"] is None:
        return False
    host_pack = ca.ptgetptinfo_2110_rebuild_pack(hits["mask"], hits["ch"])
    return (
        st == 0
        and hits["patched"]
        and hits["rebuild"] >= 1
        and hits["early"] == 0
        and hits["pack"] == host_pack
        and hits["pack"] == 0x707
        and hits["call930"] >= 1
        and hits["call9530"] >= 1
        and hits["call7aa0"] >= 1
        and not ca.ptgetptinfo_2110_early_identity(False)
    )


def _golden_live_930(kcms: object) -> bool:
    """Forced-mismatch SpCombine: first ``+0x930`` pack ``0x707`` → ``ftuf``.

    Host unpack / nibble / ``+0x9c`` clear must match DLL exit state.
    """
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ESP

    pe = kcms.DEFAULT_CMS.read_bytes()
    unity = kcms.DEFAULT_UNITY.read_bytes()
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    kcms.load_pe(uc, pe)
    uc.mem_map(kcms.STACK_ADDR, kcms.STACK_SIZE)
    uc.mem_map(kcms.HEAP_ADDR, kcms.HEAP_SIZE)
    uc.mem_map(kcms.PROFILE_BUF, kcms._align_up(len(unity) + 0x1000))
    uc.mem_write(kcms.PROFILE_BUF, unity)
    host = kcms.KcmsHost(uc)
    kcms.install_iat(uc, host)
    kcms.call_stdcall(uc, kcms.BUF_OPS_INSTALL)
    out_init = host.alloc(4)
    uc.mem_write(out_init, b"\x00" * 4)
    kcms.patch_spinitialize_out_write(uc, out_init)
    if kcms.call_stdcall(uc, kcms.SP_INITIALIZE, 0, 0, out_init) != 0:
        return False
    call_h = struct.unpack("<I", uc.mem_read(out_init, 4))[0]
    out_prof = host.alloc(4)
    uc.mem_write(out_prof, b"\x00" * 4)
    if (
        kcms.call_stdcall(
            uc, kcms.SP_PROFILE_LOAD_FROM_BUFFER, call_h, kcms.PROFILE_BUF, out_prof
        )
        != 0
    ):
        return False
    prof = struct.unpack("<I", uc.mem_read(out_prof, 4))[0]
    out_xf = host.alloc(4)
    uc.mem_write(out_xf, b"\x00" * 4)
    if kcms.call_stdcall(uc, kcms.SP_XFORM_GET, prof, 0, 1, out_xf) != 0:
        return False
    xf = struct.unpack("<I", uc.mem_read(out_xf, 4))[0]
    hits: dict = {"patched": False, "first": None}

    def on_code(u, address, size, _user):
        if address == ca.KODAKCMS_PTGETPTINFO_2110 and not hits["patched"]:
            esp = u.reg_read(UC_X86_REG_ESP)
            dims = struct.unpack("<I", bytes(u.mem_read(esp + 8, 4)))[0]
            u.mem_write(dims, struct.pack("<8I", *([17] * 8)))
            hits["patched"] = True
        elif address == ca.KODAKCMS_PTGETPTINFO_930 and hits["first"] is None:
            esp = u.reg_read(UC_X86_REG_ESP)
            pack = struct.unpack("<I", bytes(u.mem_read(esp + 4, 4)))[0]
            hits["first"] = {"pack": pack, "ret_pt": None}
        elif address == 0x1000B237 and hits["first"] is not None:
            if hits["first"]["ret_pt"] is None:
                # instruction is `mov eax,esi` — hook fires before it; use ESI
                from unicorn.x86_const import UC_X86_REG_ESI

                pt = u.reg_read(UC_X86_REG_ESI)
                if pt == 0:
                    return
                hits["first"]["ret_pt"] = pt
                hits["first"]["magic"] = struct.unpack(
                    "<I", bytes(u.mem_read(pt, 4))
                )[0]
                hits["first"]["plus8"] = struct.unpack(
                    "<I", bytes(u.mem_read(pt + 8, 4))
                )[0]
                hits["first"]["plus9c"] = struct.unpack(
                    "<I", bytes(u.mem_read(pt + ca.KODAKCMS_PT_TYPE_OFF, 4))
                )[0]

    for a in (
        ca.KODAKCMS_PTGETPTINFO_2110,
        ca.KODAKCMS_PTGETPTINFO_930,
        0x1000B237,
    ):
        uc.hook_add(UC_HOOK_CODE, on_code, begin=a, end=a + 1)

    arr = host.alloc(8)
    uc.mem_write(arr, struct.pack("<II", xf, xf))
    st = kcms.call_stdcall(
        uc, ca.KODAKCMS_SP_COMBINE_XFORMS, 2, arr, host.alloc(4), host.alloc(4), 0, 0
    )
    first = hits["first"]
    if first is None or first["ret_pt"] is None:
        return False
    lo, hi, top = ca.ptgetptinfo_930_unpack_pack(first["pack"])
    return (
        st == 0
        and first["pack"] == 0x707
        and (lo, hi, top) == (7, 7, 0)
        and ca.ptgetptinfo_930_bytes_in_range(lo, hi)
        and first["magic"] == ca.KODAKCMS_PT_MAGIC_FTUF
        and first["plus9c"] == 0
        and ca.ptgetptinfo_930_insert_top_nibble(0, first["pack"]) == 0
        and ca.ptgetptinfo_930_sparse_gather(lo, None) == [0] * 8
    )


def _golden_live_9820_identity(kcms: object) -> bool:
    """``+0x9820`` identity callback LUT vs host ``ptgetptinfo_9820_fill_identity``.

    Forces the SSE ``cvttss2si`` path (``word [0x10054ae6]≠0``) so Unicorn
    matches the host ``trunc_f32`` formula without needing ``_ftol``.
    """
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
    from unicorn.x86_const import UC_X86_REG_ESP

    pe = kcms.DEFAULT_CMS.read_bytes()
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    kcms.load_pe(uc, pe)
    uc.mem_map(kcms.STACK_ADDR, kcms.STACK_SIZE)
    uc.mem_map(kcms.HEAP_ADDR, kcms.HEAP_SIZE)
    host = kcms.KcmsHost(uc)
    kcms.install_iat(uc, host)
    kcms.call_stdcall(uc, kcms.BUF_OPS_INSTALL)
    # kodakcms.dll @ 0x100140be — cmpw $0, 0x10054ae6
    uc.mem_write(0x10054AE6, struct.pack("<H", 1))
    n = 5
    ituf = host.alloc(0x50)
    buf = host.alloc(2 * n + 16)
    uc.mem_write(ituf, b"\x00" * 0x50)
    uc.mem_write(ituf, struct.pack("<I", ca.KODAKCMS_PT_MAGIC_ITUF))
    uc.mem_write(ituf + 0x20, struct.pack("<I", n))
    uc.mem_write(ituf + 0x24, struct.pack("<I", buf))
    stub = kcms.STUB_PAGE + 0x800
    # fld qword [esp+4]; ret — identity on t
    uc.mem_write(stub, bytes([0xDD, 0x44, 0x24, 0x04, 0xC3]))
    stop = kcms.STUB_PAGE
    uc.mem_write(stop, b"\xc3")
    esp = kcms.STACK_ADDR + kcms.STACK_SIZE - 0x2000
    # cdecl: retaddr, ituf, cb, userdata
    uc.mem_write(esp, struct.pack("<4I", stop, ituf, stub, 0))
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.emu_start(ca.KODAKCMS_PTGETPTINFO_9820, stop, timeout=5_000_000)
    words = list(struct.unpack(f"<{n}H", bytes(uc.mem_read(buf, 2 * n))))
    return words == ca.ptgetptinfo_9820_fill_identity(n)


def _golden_live_e80(kcms: object) -> bool:
    """Forced mismatch: first PT’s ``+0xf80`` chain builds ``+8`` → ``0x707``.

    Host ``ptgetptinfo_f80_or_plus8`` / ``bit_index`` must track DLL.
    """
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EDI, UC_X86_REG_ESP

    pe = kcms.DEFAULT_CMS.read_bytes()
    unity = kcms.DEFAULT_UNITY.read_bytes()
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    kcms.load_pe(uc, pe)
    uc.mem_map(kcms.STACK_ADDR, kcms.STACK_SIZE)
    uc.mem_map(kcms.HEAP_ADDR, kcms.HEAP_SIZE)
    uc.mem_map(kcms.PROFILE_BUF, kcms._align_up(len(unity) + 0x1000))
    uc.mem_write(kcms.PROFILE_BUF, unity)
    host = kcms.KcmsHost(uc)
    kcms.install_iat(uc, host)
    kcms.call_stdcall(uc, kcms.BUF_OPS_INSTALL)
    out_init = host.alloc(4)
    uc.mem_write(out_init, b"\x00" * 4)
    kcms.patch_spinitialize_out_write(uc, out_init)
    if kcms.call_stdcall(uc, kcms.SP_INITIALIZE, 0, 0, out_init) != 0:
        return False
    call_h = struct.unpack("<I", uc.mem_read(out_init, 4))[0]
    out_prof = host.alloc(4)
    uc.mem_write(out_prof, b"\x00" * 4)
    if (
        kcms.call_stdcall(
            uc, kcms.SP_PROFILE_LOAD_FROM_BUFFER, call_h, kcms.PROFILE_BUF, out_prof
        )
        != 0
    ):
        return False
    prof = struct.unpack("<I", uc.mem_read(out_prof, 4))[0]
    out_xf = host.alloc(4)
    uc.mem_write(out_xf, b"\x00" * 4)
    if kcms.call_stdcall(uc, kcms.SP_XFORM_GET, prof, 0, 1, out_xf) != 0:
        return False
    xf = struct.unpack("<I", uc.mem_read(out_xf, 4))[0]
    hits: dict = {"patched": False, "first_pt": None, "steps": []}

    def on_code(u, address, size, _user):
        if address == ca.KODAKCMS_PTGETPTINFO_2110 and not hits["patched"]:
            esp = u.reg_read(UC_X86_REG_ESP)
            dims = struct.unpack("<I", bytes(u.mem_read(esp + 8, 4)))[0]
            u.mem_write(dims, struct.pack("<8I", *([17] * 8)))
            hits["patched"] = True
        elif address == ca.KODAKCMS_PTGETPTINFO_F80:
            esp = u.reg_read(UC_X86_REG_ESP)
            pt, pack, ctuf = struct.unpack(
                "<3I", bytes(u.mem_read(esp + 4, 12))
            )
            if hits["first_pt"] is None:
                hits["first_pt"] = pt
            if pt != hits["first_pt"] or len(hits["steps"]) >= 3:
                return
            before = struct.unpack("<I", bytes(u.mem_read(pt + 8, 4)))[0]
            bit = (pack >> 8) & 0xFF
            ctuf4 = struct.unpack(
                "<I", bytes(u.mem_read(ctuf + ca.KODAKCMS_CTUF_PLUS4_OFF, 4))
            )[0] & 0xFF
            hits["steps"].append(
                {"pack": pack, "bit": bit, "before": before, "ctuf4": ctuf4}
            )
        elif address == 0x1000B7B9:
            if hits["first_pt"] is None or len(hits["steps"]) == 0:
                return
            step = hits["steps"][-1]
            if "after" in step:
                return
            edi = u.reg_read(UC_X86_REG_EDI)
            if edi != hits["first_pt"]:
                return
            step["after"] = struct.unpack("<I", bytes(u.mem_read(edi + 8, 4)))[0]
            step["slot"] = ca.ptgetptinfo_bit_index(step["bit"])

    for a in (
        ca.KODAKCMS_PTGETPTINFO_2110,
        ca.KODAKCMS_PTGETPTINFO_F80,
        0x1000B7B9,
    ):
        uc.hook_add(UC_HOOK_CODE, on_code, begin=a, end=a + 1)

    arr = host.alloc(8)
    uc.mem_write(arr, struct.pack("<II", xf, xf))
    st = kcms.call_stdcall(
        uc, ca.KODAKCMS_SP_COMBINE_XFORMS, 2, arr, host.alloc(4), host.alloc(4), 0, 0
    )
    if st != 0 or len(hits["steps"]) < 3:
        return False
    want = (0x107, 0x307, 0x707)
    cur = 0
    for i, step in enumerate(hits["steps"][:3]):
        if "after" not in step or step["slot"] < 0:
            return False
        host_after = ca.ptgetptinfo_f80_or_plus8(
            step["before"], step["slot"], step["ctuf4"]
        )
        if (
            host_after != step["after"]
            or step["after"] != want[i]
            or ca.ptgetptinfo_bit_index(step["bit"]) != i
        ):
            return False
        cur = step["after"]
    return cur == 0x707 and ca.ptgetptinfo_e80_ftuf_gate(ca.KODAKCMS_PT_MAGIC_FTUF)


def _golden_live_validate_refnum(kcms: object) -> bool:
    """Live SpXformGetRefNum + PT type via kodakcms IAT harness.

    unity.pf xform → GetRefNum status 0; null handle → 0x1fb
    (``kodakcms.dll @ 0x1002f0d2``). Host validate face must match.
    """
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32

    pe = kcms.DEFAULT_CMS.read_bytes()
    unity = kcms.DEFAULT_UNITY.read_bytes()
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    kcms.load_pe(uc, pe)
    uc.mem_map(kcms.STACK_ADDR, kcms.STACK_SIZE)
    uc.mem_map(kcms.HEAP_ADDR, kcms.HEAP_SIZE)
    uc.mem_map(kcms.PROFILE_BUF, kcms._align_up(len(unity) + 0x1000))
    uc.mem_write(kcms.PROFILE_BUF, unity)
    host = kcms.KcmsHost(uc)
    kcms.install_iat(uc, host)
    kcms.call_stdcall(uc, kcms.BUF_OPS_INSTALL)
    out_init = host.alloc(4)
    uc.mem_write(out_init, b"\x00" * 4)
    kcms.patch_spinitialize_out_write(uc, out_init)
    if kcms.call_stdcall(uc, kcms.SP_INITIALIZE, 0, 0, out_init) != 0:
        return False
    call_h = struct.unpack("<I", uc.mem_read(out_init, 4))[0]
    out_prof = host.alloc(4)
    uc.mem_write(out_prof, b"\x00" * 4)
    if (
        kcms.call_stdcall(
            uc, kcms.SP_PROFILE_LOAD_FROM_BUFFER, call_h, kcms.PROFILE_BUF, out_prof
        )
        != 0
    ):
        return False
    prof = struct.unpack("<I", uc.mem_read(out_prof, 4))[0]
    out_xf = host.alloc(4)
    uc.mem_write(out_xf, b"\x00" * 4)
    if kcms.call_stdcall(uc, kcms.SP_XFORM_GET, prof, 0, 1, out_xf) != 0:
        return False
    xf = struct.unpack("<I", uc.mem_read(out_xf, 4))[0]
    out_ref = host.alloc(4)
    uc.mem_write(out_ref, b"\x00" * 4)
    # SpXformGetRefNum(xform, out*) stdcall @ 0x1002f0c0
    st_ok = kcms.call_stdcall(uc, ca.KODAKCMS_SP_XFORM_GET_REF_NUM, xf, out_ref)
    ref = struct.unpack("<I", uc.mem_read(out_ref, 4))[0]
    st_bad = kcms.call_stdcall(uc, ca.KODAKCMS_SP_XFORM_GET_REF_NUM, 0, out_ref)
    # PT type on ref (cdecl push; callee add esp,4)
    pt_type = 0
    if st_ok == 0 and ref != 0:
        stop = kcms.STUB_PAGE
        uc.mem_write(stop, b"\xc3")
        esp = kcms.STACK_ADDR + 0x100000
        payload = struct.pack("<II", stop, ref)
        esp -= len(payload)
        uc.mem_write(esp, payload)
        uc.reg_write(UC_X86_REG_ESP, esp)
        uc.emu_start(ca.KODAKCMS_PT_GET_PT_INFO_70, stop, count=5_000_000, timeout=5_000_000)
        pt_type = uc.reg_read(UC_X86_REG_EAX) & 0xFFFFFFFF
    host_ok = ca.sp_connect_validate_status_from_ref_and_type(st_ok, pt_type)
    host_bad = ca.sp_connect_validate_status_from_ref_and_type(st_bad, 0)
    return (
        st_ok == 0
        and host_ok is None
        and ca.sp_connect_pt_type_accepted(pt_type)
        and st_bad == ca.KODAKCMS_SPCONNECT_ERR_BAD_XFORM
        and host_bad == ca.KODAKCMS_SPCONNECT_ERR_BAD_XFORM
    )


def run_combine_mode_from_flag(cms: bytes, flag: int) -> int:
    """Unicorn: kodakcms @ 0x1002e420 mode encode from SpCombine/ConnectEx flag."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, cms)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(STUB_ADDR, 0x1000)
    uc.mem_write(STUB_ADDR, b"\xc3")
    esp = STACK_ADDR + 0x80000
    payload = struct.pack("<II", STUB_ADDR, int(flag) & 0xFFFFFFFF)
    esp -= len(payload)
    uc.mem_write(esp, payload)
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.emu_start(ca.KODAKCMS_SPCONNECT_MODE_FROM_FLAG, STUB_ADDR, count=200)
    return uc.reg_read(UC_X86_REG_EAX) & 0xFFFFFFFF


def run_copy12(cms: bytes, src12: bytes) -> bytes:
    """Unicorn: kodakcms @ 0x1002eca0 copies 12 bytes src→dst."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe_into_uc(uc, cms)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(STUB_ADDR, 0x1000)
    uc.mem_write(STUB_ADDR, b"\xc3")
    buf = 0x20000000
    uc.mem_map(buf, 0x1000)
    src = buf
    dst = buf + 0x40
    uc.mem_write(src, src12)
    uc.mem_write(dst, b"\xff" * 12)
    esp = STACK_ADDR + 0x80000
    # leaf: [esp+4]=src, [esp+8]=dst after call (cdecl)
    payload = struct.pack("<III", STUB_ADDR, src, dst)
    esp -= len(payload)
    uc.mem_write(esp, payload)
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.emu_start(ca.KODAKCMS_SPCONNECT_COPY12, STUB_ADDR, count=50)
    return bytes(uc.mem_read(dst, 12))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
