#!/usr/bin/env python3
"""Golden Ane collectData leaves ``0x1027fc80`` / ``0x102804e0`` vs PakonIMAu.dll."""
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


def main() -> int:
    dll_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DLL
    dll = dll_path.read_bytes()
    print(f"dll={dll_path}")
    print(f"ANE_COLLECT_FC80_PORTED={col.ANE_COLLECT_FC80_PORTED}")
    print(f"ANE_COLLECT_804E0_PORTED={col.ANE_COLLECT_804E0_PORTED}")

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

    if failed:
        print(f"FAILED {failed} cases")
        return 1
    print("all fc80 + 804e0 pixel cases OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
