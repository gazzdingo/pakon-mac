#!/usr/bin/env python3
"""Golden Ane collectData leaves ``0x1027fc80`` / ``0x102804e0`` + host orch.

Also covers ``collectData`` @ ``0x101ee590`` host face (pick / Cap→dispatch /
named portfolio structure). Runtime COM QI insert is not unicorn'd.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import numpy as np
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_EBP,
    UC_X86_REG_EBX,
    UC_X86_REG_ECX,
    UC_X86_REG_EDI,
    UC_X86_REG_EDX,
    UC_X86_REG_ESI,
    UC_X86_REG_ESP,
)

import pakon_ane_collect as col

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x20000000
STACK_SIZE = 0x200000
HEAP_ADDR = 0x30000000
HEAP_SIZE = 0x200000

DEFAULT_DLL = Path(
    "/Users/guy/Downloads/Pakon Update 3/fx35install/program files/"
    "Pakon/F-X35 COM SERVER/PakonIMAu.dll"
)


def _map_pe(uc: Uc, dll: bytes, size: int = 0x700000) -> None:
    try:
        uc.mem_map(IMAGE_BASE, size)
    except UcError:
        pass
    uc.mem_write(IMAGE_BASE, dll[: min(len(dll), size)])


def _cstr_at(dll: bytes, va: int) -> str:
    off = va - IMAGE_BASE
    end = dll.index(b"\x00", off)
    return dll[off:end].decode("ascii")


def run_fc80_pixel_dll(
    dll: bytes,
    window5: np.ndarray,
    *,
    avg_flag: bool = False,
    pitch: int = 32,
) -> tuple[int, int]:
    """Unicorn pixel body with padded pitch so DLL byte offsets stay in-bounds."""
    if window5.shape != (5, 5):
        raise ValueError("window5 must be 5×5")
    P = int(pitch)
    if P < 5:
        raise ValueError("pitch must be ≥ 5")
    buf = np.zeros((5, P), dtype=np.int16)
    buf[:, :5] = window5

    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    _map_pe(uc, dll)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(HEAP_ADDR, HEAP_SIZE)

    src = HEAP_ADDR + 0x1000
    samp = HEAP_ADDR + 0x8000
    resid = HEAP_ADDR + 0x8100
    uc.mem_write(src, buf.tobytes())
    uc.mem_write(samp, b"\x00\x00")
    uc.mem_write(resid, b"\x00\x00")

    # Place center at col 2 within the 5-wide window starting at col 0.
    # ecx = &buf[2][0] (center is at +2 samples = +4 bytes)
    ecx = src + (2 * P + 0) * 2
    tl = src + (0 * P + 0) * 2  # (-2,-2) relative to center at [2][2]

    o = {
        0x84: 8,
        0x54: -4 * P,
        0x70: 4 - 2 * P,
        0x88: 2 * P + 4,
        0x90: 4 * P + 4,
        0x8C: 6 - 2 * P,
        0x80: 2 - 2 * P,
        0x5C: 2 * P + 2,
        0x98: 2 * P + 6,
        0x68: 4 * P,
        0xA4: 4,
        0xA8: 4 * P + 8,
        0x74: 2,
        0x7C: 6,
    }

    esp = STACK_ADDR + 0x10000
    # Zero a large stack frame; write needed slots.
    uc.mem_write(esp, b"\x00" * 0x600)
    for off, val in o.items():
        uc.mem_write(esp + off, struct.pack("<i", int(val)))
    uc.mem_write(esp + 0x14, struct.pack("<I", tl))
    uc.mem_write(esp + 0x18, struct.pack("<I", samp))
    uc.mem_write(esp + 0x9C, struct.pack("<i", resid - samp))
    uc.mem_write(esp + 0x4F0, struct.pack("<B", 1 if avg_flag else 0))

    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_ECX, ecx)
    uc.reg_write(UC_X86_REG_EBP, samp)
    uc.reg_write(UC_X86_REG_EDI, 4)
    uc.reg_write(UC_X86_REG_EBX, 2)
    uc.reg_write(UC_X86_REG_EDX, 6)
    uc.reg_write(UC_X86_REG_ESI, 0)
    uc.reg_write(UC_X86_REG_EAX, 0)

    try:
        uc.emu_start(
            col.ANE_SAMPLE_RESIDUAL_PIXEL,
            col.ANE_SAMPLE_RESIDUAL_PIXEL_END,
            timeout=500_000,
            count=400,
        )
    except UcError as e:
        raise RuntimeError(f"unicorn fc80 pixel: {e}") from e

    s = struct.unpack("<h", uc.mem_read(samp, 2))[0]
    r = struct.unpack("<h", uc.mem_read(resid, 2))[0]
    return int(s), int(r)


def run_804e0_pixel_dll(
    dll: bytes,
    window5: np.ndarray,
    *,
    filter_size: int = 5,
    avg_flag: bool = False,
) -> tuple[int, int]:
    """Unicorn box pixel body ``0x10280800…0x102808f1`` on a 5×5 window.

    Offset table at ``esp+0x5c`` is indices ``0…24`` into the flat 5×5;
    ``ebp=12`` is the center (cite setup ``0x10280720…`` / ``esp+0x8c``).
    """
    if window5.shape != (5, 5):
        raise ValueError("window5 must be 5×5")
    buf = np.asarray(window5, dtype=np.int16)

    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    _map_pe(uc, dll)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(HEAP_ADDR, HEAP_SIZE)

    src = HEAP_ADDR + 0x1000
    samp = HEAP_ADDR + 0x8000
    resid = HEAP_ADDR + 0x8100
    uc.mem_write(src, buf.tobytes())
    uc.mem_write(samp, b"\x00\x00")
    uc.mem_write(resid, b"\x00\x00")

    esp = STACK_ADDR + 0x10000
    uc.mem_write(esp, b"\x00" * 0x600)
    # 25 absolute sample indices for the 5×5 window (pitch = 5).
    for i in range(25):
        uc.mem_write(esp + 0x5C + 4 * i, struct.pack("<i", i))
    uc.mem_write(esp + 0x14, struct.pack("<i", 1))  # one pixel then exit
    uc.mem_write(esp + 0x48, struct.pack("<i", resid - samp))
    uc.mem_write(esp + 0x4E0, struct.pack("<i", int(filter_size)))
    uc.mem_write(esp + 0x4E4, struct.pack("<B", 1 if avg_flag else 0))
    uc.mem_write(esp + 0x4D4, struct.pack("<i", 1))  # x_step if advanced

    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_ECX, src)
    uc.reg_write(UC_X86_REG_EBP, 12)  # center index
    uc.reg_write(UC_X86_REG_EDI, samp)
    uc.reg_write(UC_X86_REG_EBX, resid - samp)
    uc.reg_write(UC_X86_REG_ESI, 0)
    uc.reg_write(UC_X86_REG_EAX, 0)
    uc.reg_write(UC_X86_REG_EDX, 0)

    try:
        uc.emu_start(
            col.ANE_SAMPLE_RESIDUAL_804E0_PIXEL,
            col.ANE_SAMPLE_RESIDUAL_804E0_PIXEL_END,
            timeout=500_000,
            count=800,
        )
    except UcError as e:
        raise RuntimeError(f"unicorn 804e0 pixel: {e}") from e

    s = struct.unpack("<h", uc.mem_read(samp, 2))[0]
    r = struct.unpack("<h", uc.mem_read(resid, 2))[0]
    return int(s), int(r)


def _fc80_cases() -> list[tuple[str, np.ndarray, bool]]:
    flat = np.full((5, 5), 1000, dtype=np.int16)
    hgrad = np.array([[100 * c for c in range(5)] for _ in range(5)], dtype=np.int16)
    vgrad = np.array([[100 * r for c in range(5)] for r in range(5)], dtype=np.int16)
    rng = np.random.default_rng(0)
    noise = rng.integers(-2000, 2000, size=(5, 5), dtype=np.int16)
    peak = np.full((5, 5), 500, dtype=np.int16)
    peak[2, 2] = 2000
    out: list[tuple[str, np.ndarray, bool]] = []
    for name, w in (
        ("flat", flat),
        ("hgrad", hgrad),
        ("vgrad", vgrad),
        ("noise", noise),
        ("peak", peak),
    ):
        out.append((name, w, False))
        out.append((f"{name}_avg", w, True))
    return out


def _804e0_cases() -> list[tuple[str, np.ndarray, int, bool]]:
    flat = np.full((5, 5), 1000, dtype=np.int16)
    hgrad = np.array([[100 * c for c in range(5)] for _ in range(5)], dtype=np.int16)
    rng = np.random.default_rng(1)
    noise = rng.integers(0, 3000, size=(5, 5), dtype=np.int16)
    peak = np.full((5, 5), 500, dtype=np.int16)
    peak[2, 2] = 2500
    # Negative residual path (sum may be negative for signed taps).
    neg = np.full((5, 5), -400, dtype=np.int16)
    neg[2, 2] = -100
    out: list[tuple[str, np.ndarray, int, bool]] = []
    for name, w in (
        ("flat", flat),
        ("hgrad", hgrad),
        ("noise", noise),
        ("peak", peak),
        ("neg", neg),
    ):
        for fs in (3, 5):
            out.append((f"{name}_fs{fs}", w, fs, False))
            out.append((f"{name}_fs{fs}_avg", w, fs, True))
    return out


def _check_collect_data_host(dll: bytes) -> int:
    """Structure / orch golden for ``0x101ee590`` host face (no COM insert)."""
    failed = 0

    # String + layout constants vs DLL rdata / cited immediates.
    for va, expect in (
        (col.STR_ANE_SAMPLED_IMAGE, col.ANE_QI_NAME_SAMPLED),
        (col.STR_ANE_RESIDUAL_IMAGE, col.ANE_QI_NAME_RESIDUAL),
    ):
        got = _cstr_at(dll, va)
        ok = got == expect
        mark = "OK" if ok else "FAIL"
        print(f"  {mark} str@{va:#x}={got!r}")
        if not ok:
            failed += 1

    if col.ANE_QI_ENTRY_SIZE != 0x44:
        print(f"  FAIL QI size {col.ANE_QI_ENTRY_SIZE:#x} != 0x44")
        failed += 1
    else:
        print("  OK QI entry size 0x44")
    if col.ANE_QI_PAYLOAD_OFF != 0x20 or col.ANE_QI_PAYLOAD_DWORDS != 9:
        print("  FAIL QI payload off/dwords")
        failed += 1
    else:
        print("  OK QI payload +0x20 × 9 dwords")

    # major-dim / pick leaf (cite 0x101ee650…)
    if col.ane_collect_image_major_dim(100, 200) != 200:
        print("  FAIL major_dim")
        failed += 1
    cand = [(100, 100), (800, 900), (2000, 100), (1800, 1800), (1600, 50)]
    # thresh 1500: idx1 max=900 skip; idx2=2000; idx3=1800 kept? 1800<=2000 skip;
    # idx4=1600 skip. Best = 2.
    i = col.ane_collect_pick_best_source(cand, 1500)
    if i != 2:
        print(f"  FAIL pick_best got {i} want 2")
        failed += 1
    else:
        print("  OK pick_best under minMajorDim")
    if col.ane_collect_pick_best_source([(10, 10)], 1500) is not None:
        print("  FAIL pick empty expected")
        failed += 1
    else:
        print("  OK pick none below gate")

    # planar bases (cite 0x101ee78d…)
    b0, b1, b2 = col.ane_collect_planar_plane_bases(0x1000, 10, 20)
    if (b0, b1, b2) != (0x1000, 0x1000 + 400, 0x1000 + 800):
        print(f"  FAIL planar bases {(b0, b1, b2)}")
        failed += 1
    else:
        print("  OK planar plane bases")

    # dispatch Cap+0x7c
    if not col.ane_collect_dispatch_uses_laplacian(0):
        print("  FAIL laplacian dispatch null")
        failed += 1
    if col.ane_collect_dispatch_uses_laplacian(0xDEAD):
        print("  FAIL box dispatch non-null")
        failed += 1
    else:
        print("  OK Cap+0x7c dispatch")

    if col.ane_collect_needs_image_convert(2):
        print("  FAIL type==2 should skip convert")
        failed += 1
    if not col.ane_collect_needs_image_convert(0):
        print("  FAIL type!=2 needs convert")
        failed += 1
    else:
        print("  OK image type gate")

    # QI name ctor / image vtable / payload / insert-or-replace
    assert col.ANE_COLLECT_QI_INSERT_PORTED
    if col.ane_qi_name_ctor_vtbl() != 0x1057C008:
        print("  FAIL name-ctor vtbl")
        failed += 1
    else:
        print("  OK QI name-ctor vtbl 0x1057c008")
    if col.ane_qi_image_vtbl_after_payload() != 0x10583EB0:
        print("  FAIL image vtbl")
        failed += 1
    else:
        print("  OK QI image vtbl 0x10583eb0")
    pl = col.ane_qi_pack_payload([1, 2, 3])
    if len(pl) != 36 or struct.unpack("<9I", pl)[:3] != (1, 2, 3):
        print(f"  FAIL pack_payload {pl!r}")
        failed += 1
    else:
        print("  OK QI payload 9 dwords")
    port = col.AneQiPortfolio()
    e1 = col.ane_qi_build_entry(
        col.ANE_QI_NAME_SAMPLED, (np.zeros((1, 1), np.int16),) * 3, [9] * 9
    )
    if not col.ane_qi_insert(port, e1) or col.ane_qi_insert(port, None):
        print("  FAIL insert null/ok")
        failed += 1
    e1b = col.ane_qi_build_entry(
        col.ANE_QI_NAME_SAMPLED, (np.ones((1, 1), np.int16),) * 3, [8] * 9
    )
    if not col.ane_qi_insert(port, e1b) or port.replaced != [col.ANE_QI_NAME_SAMPLED]:
        print(f"  FAIL replace {port.replaced}")
        failed += 1
    else:
        print("  OK QI insert-or-replace by name")
    if port.by_name[col.ANE_QI_NAME_SAMPLED].payload[0] != 8:
        print("  FAIL replace payload")
        failed += 1

    # type≠2 convert / planar factory leaves
    assert col.ANE_COLLECT_CONVERT_PORTED
    if col.ane_collect_convert_stamp_type() != 2:
        print("  FAIL convert stamp")
        failed += 1
    else:
        print("  OK convert stamps type=2")
    if col.ane_collect_convert_same_type_bytes(10, 20, 3) != 2 * 10 * 3 * 20:
        print("  FAIL convert memcpy size")
        failed += 1
    else:
        print("  OK convert same-type byte count")
    if not col.ane_collect_convert_same_type_ok(2, 0) or col.ane_collect_convert_same_type_ok(
        2, 1
    ):
        print("  FAIL convert same-type gate")
        failed += 1
    else:
        print("  OK convert same-type gate")
    if (
        col.ane_collect_planar_factory_size() != 0x24
        or col.ane_collect_planar_factory_vtbl() != 0x1057B10C
    ):
        print("  FAIL planar factory")
        failed += 1
    else:
        print("  OK planar factory 0x24 / vtbl")

    # Orch: small image below minMajorDim → empty
    tiny = np.zeros((64, 64, 3), dtype=np.int16)
    r = col.ane_collect_data([tiny], cap=col.AneCollectCapParams(min_major_dim=1500))
    if r.entries or r.source_index is not None:
        print(f"  FAIL tiny orch {r}")
        failed += 1
    else:
        print("  OK orch rejects below minMajorDim")

    # Cap with min_major_dim=0 so 9×9 qualifies; step=1 Laplacian
    plane = np.arange(9 * 9, dtype=np.int16).reshape(9, 9) * 3
    rgb = np.stack([plane, plane + 1, plane + 2], axis=-1)
    cap = col.AneCollectCapParams(
        min_major_dim=0,
        col_sampling=1,
        row_sampling=1,
        correct_for_filter=False,
        filter_mode_ptr=0,
    )
    r = col.ane_collect_data([rgb], cap=cap, image_types=[2])
    if len(r.entries) != 2:
        print(f"  FAIL orch entry count {len(r.entries)}")
        failed += 1
    else:
        ok = (
            r.entries[0].name == col.ANE_QI_NAME_SAMPLED
            and r.entries[1].name == col.ANE_QI_NAME_RESIDUAL
            and r.used_laplacian
            and r.source_index == 0
        )
        # Planes match direct leaf
        s0, r0 = col.ane_fc80_planes(plane, x_step=1, y_step=1, avg_flag=False)
        match = (
            np.array_equal(r.entries[0].planes[0], s0)
            and np.array_equal(r.entries[1].planes[0], r0)
        )
        mark = "OK" if ok and match else "FAIL"
        print(f"  {mark} orch Named Sampled/Residual + leaf planes")
        if not (ok and match):
            failed += 1
        if r.portfolio is None or set(r.portfolio.by_name) != {
            col.ANE_QI_NAME_SAMPLED,
            col.ANE_QI_NAME_RESIDUAL,
        }:
            print(f"  FAIL portfolio map {r.portfolio}")
            failed += 1
        else:
            print("  OK portfolio map after insert")
        # Second orch into same portfolio → replace both names
        r_again = col.ane_collect_data([rgb], cap=cap, image_types=[2], portfolio=r.portfolio)
        if len(r_again.portfolio.replaced) < 2:
            print(f"  FAIL re-insert replace {r_again.portfolio.replaced}")
            failed += 1
        else:
            print("  OK re-insert replaces Sampled+Residual")

    # Multi-source: pick largest major dim
    small = np.zeros((100, 100, 3), dtype=np.int16)
    big = np.arange(200 * 180 * 3, dtype=np.int16).reshape(180, 200, 3)
    mid = np.zeros((160, 160, 3), dtype=np.int16)
    cap2 = col.AneCollectCapParams(
        min_major_dim=150, col_sampling=32, row_sampling=32, correct_for_filter=True
    )
    r2 = col.ane_collect_data([small, mid, big], cap=cap2, image_types=[2, 2, 2])
    if r2.source_index != 2:
        print(f"  FAIL multi pick {r2.source_index}")
        failed += 1
    else:
        print("  OK multi-source pick")

    # Box Cap path (non-null filter ptr)
    cap_box = col.AneCollectCapParams(
        min_major_dim=0,
        col_sampling=1,
        row_sampling=1,
        filter_mode_ptr=1,
        filter_size=3,
        correct_for_filter=False,
    )
    r3 = col.ane_collect_data([rgb], cap=cap_box, image_types=[2])
    if r3.used_laplacian or len(r3.entries) != 2:
        print(f"  FAIL box orch lap={r3.used_laplacian} n={len(r3.entries)}")
        failed += 1
    else:
        s_b, r_b = col.ane_804e0_planes(
            plane, filter_size=3, x_step=1, y_step=1, avg_flag=False
        )
        match = np.array_equal(r3.entries[0].planes[0], s_b) and np.array_equal(
            r3.entries[1].planes[0], r_b
        )
        mark = "OK" if match else "FAIL"
        print(f"  {mark} orch box filterSize=3 planes")
        if not match:
            failed += 1

    return failed


def main() -> int:
    dll_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DLL
    dll = dll_path.read_bytes()
    print(f"dll={dll_path}")
    print(f"ANE_COLLECT_FC80_PORTED={col.ANE_COLLECT_FC80_PORTED}")
    print(f"ANE_COLLECT_804E0_PORTED={col.ANE_COLLECT_804E0_PORTED}")
    print(f"ANE_COLLECT_DATA_PORTED={col.ANE_COLLECT_DATA_PORTED}")
    print(f"ANE_COLLECT_QI_INSERT_PORTED={col.ANE_COLLECT_QI_INSERT_PORTED}")
    print(f"ANE_COLLECT_CONVERT_PORTED={col.ANE_COLLECT_CONVERT_PORTED}")

    failed = 0
    for name, window, avg in _fc80_cases():
        host_s, host_r = col.ane_fc80_pixel(
            window.ravel(), 5, 2, 2, avg_flag=avg
        )
        dll_s, dll_r = run_fc80_pixel_dll(dll, window, avg_flag=avg)
        ok = host_s == dll_s and host_r == dll_r
        mark = "OK" if ok else "FAIL"
        print(
            f"  {mark} fc80 {name}: host=({host_s},{host_r}) dll=({dll_s},{dll_r})"
        )
        if not ok:
            failed += 1

    # Plane-level smoke: steps=1 on 9×9
    plane = np.arange(9 * 9, dtype=np.int16).reshape(9, 9) * 3
    samp, res = col.ane_fc80_planes(plane, x_step=1, y_step=1, avg_flag=False)
    print(f"  plane smoke sampled={samp.shape} residual={res.shape} "
          f"mid=({samp[2,2]},{res[2,2]})")

    # Magic-div vs Python trunc toward 0
    for n in (-100, -25, -9, -1, 0, 1, 8, 9, 10, 24, 25, 26, 100, 999):
        if col.ane_signed_div9(n) != int(n / 9):
            print(f"  FAIL div9 n={n}: {col.ane_signed_div9(n)} != {int(n / 9)}")
            failed += 1
        if col.ane_signed_div25(n) != int(n / 25):
            print(f"  FAIL div25 n={n}: {col.ane_signed_div25(n)} != {int(n / 25)}")
            failed += 1

    for name, window, fs, avg in _804e0_cases():
        host_s, host_r = col.ane_804e0_pixel(
            window.ravel(), 5, 2, 2, filter_size=fs, avg_flag=avg
        )
        dll_s, dll_r = run_804e0_pixel_dll(
            dll, window, filter_size=fs, avg_flag=avg
        )
        ok = host_s == dll_s and host_r == dll_r
        mark = "OK" if ok else "FAIL"
        print(
            f"  {mark} 804e0 {name}: host=({host_s},{host_r}) "
            f"dll=({dll_s},{dll_r})"
        )
        if not ok:
            failed += 1

    box3, box3r = col.ane_804e0_planes(
        plane, filter_size=3, x_step=1, y_step=1, avg_flag=False
    )
    print(f"  804e0 fs3 plane smoke sampled={box3.shape} residual={box3r.shape}")

    print("--- collectData host orch ---")
    failed += _check_collect_data_host(dll)

    if failed:
        print(f"FAILED {failed} cases")
        return 1
    print("all fc80 + 804e0 pixel + collectData orch cases OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
