#!/usr/bin/env python3
"""Verified SBA balance-shift *apply* (PakonIMAu.dll).

VERIFIED
--------
* ``AnsAreaCapabilityImpl::applyBalanceShifts`` @ ``0x1019a0c0`` builds three
  4096-entry LUTs via ``0x1006c4f0`` on singleton ``0x106b5f74``.
* It is **not** the builder that runs on a real F-135 analysis pass. In
  ``live_hooks_20260819-121153.jsonl`` all 117 ``area_image_apply_lut``
  (``0x100d9340``) calls carry one of two return addresses:
  ``0x100fe87a`` (39, one per frame, the per-frame shifts) and ``0x101b291d``
  (78, every one the exact identity). ``0x100fe87a`` is inside
  ``ColorNegativePath::analyzePostBalance`` (``fcn.100fe4f0``, from its own
  string table), which calls the same ``0x1006c4f0`` at ``0x100fe807`` and
  reads its shift triple from a pointer argument. Neither ``0x1019a0c0`` nor
  ``balanceAreaImage`` (``0x10102b20``) appears as a caller on any of the 117.
  Tier 2 (live hardware hook capture, retaddr attribution).
* The three tables it hands ``area_image_apply_lut`` are reproduced
  bit-exactly by ``shift_luts`` below — tier 1, real DLL under Wine
  (``pakon_shift_luts_golden.py``).
* Master table fill: ctor ``0x100f42a0`` called from ``0x1056a470`` as
  ``(bits=0xc, floor=0, max=0xfff)``:
  - alloc ``0x20002`` bytes; usable pointer at ``obj+8`` = alloc+``0x10000``
    (signed index ``-0x8000..0x7fff``);
  - ``master[i] = 0`` for ``i <= 0``;
  - ``master[i] = i`` for ``1..0xfff``;
  - ``master[i] = 0xfff`` for ``i > 0xfff``.
* LUT build loop @ ``0x1006c582``: ``out[i] = master[i + shift]`` (int16),
  so for in-range codes this is ``clamp(i + shift, 0, 4095)``.
* ``getShifts`` @ ``0x10124000`` copies 3×int16 from
  ``*(AnsSbaCapability+0x10) + 0x3a38``.
* Those three words are written by ``Preference`` @ ``0x1028c780``
  (analyzePass2 @ ``0x10216433`` passes ``scene+0x3a30``; after
  ``add esi, 8`` @ ``0x1028ccdf`` the loop @ ``0x1028cce7`` stores three
  ``fist``-rounded int16s into ``scene+0x3a38/+3a3a/+3a3c``).
* Only two ``.text`` imm32 refs to ``0x3a38``: ``getShifts`` copy and
  Preference blob read ``0x10215308``. **No alternate writer** of
  ``+0x3a38`` found — Preference remains required.
* ``ColorNegativePath::setShifts`` @ ``0x10100260`` **reads** via
  ``getShifts`` and writes a 3×int16 **OUT** buffer — it does **not**
  populate ``+0x3a38``.

setShifts control words + ``(1,2)`` (VERIFIED — ``docs/52``)
------------------------------------------------------------
* Filled from **AnsSCPLutCapability** Cap ``+0x10+0x18`` via ``0x10122a70``
  → ``0x10122190``: ``ntdChoice`` / ``ctdChoice`` at ``+0x38`` / ``+0x3a``.
* Shipped CN dpi → **``(1, 2)``** — not passthrough.
* ``(0, 0)`` → copy A; ``(2, 2)`` → copy B.
* ``(1, 2)`` closed form (fragment below): LUT(Y from A') + chroma(B')
  → reconstruct → ``OUT = 0x60e − RGB``. See ``docs/52``.
* ``SETSHIFTS_12_PORTED = True`` — Unicorn golden vs DLL ``(1,2)`` body
  (``pakon_setshifts_golden.py``).
* CN call site: getShifts A≡B (same Sba Cap ``+0x3a38``); OUT =
  ``scene+0x4b6``. Host: ``pakon_ansel.cn_setshifts_apply_words`` →
  ``apply_balance_shifts`` when both ``SETSHIFTS_12_PORTED`` and
  ``PREFERENCE_SHIFTS_PORTED`` (hi=``0x10`` FPU; ``docs/49``).
"""
from __future__ import annotations

import numpy as np

from pakon_fos import (
    fos_opening_axes,
    fos_opening_axes_inverse,
)

MASTER_MAX = 0xFFF  # 4095

SETSHIFTS_PIVOT_0x60E = 0x60E  # 1550
SETSHIFTS_SCALE_0x186A0 = 0x186A0
PATH_SET_SHIFTS = 0x10100260
PATH_SET_SHIFTS_12 = 0x10100A37
SHIPPED_CN_SETSHIFTS_CTRL = (1, 2)  # ntd=lut_first, ctd=second

# Closed form + Unicorn golden vs PakonIMAu.dll (1,2) fragment
SETSHIFTS_12_PORTED = True


def _i16(x: int) -> int:
    x &= 0xFFFF
    return x - 0x10000 if x >= 0x8000 else x


def _pivot(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    p = SETSHIFTS_PIVOT_0x60E
    return _i16(p - rgb[0]), _i16(p - rgb[1]), _i16(p - rgb[2])


def lookup_3band_planar(
    idx_rgb: tuple[int, int, int],
    planar: list[int] | tuple[int, ...],
    num_lut: int,
) -> tuple[int, int, int]:
    """Planar index as setShifts ``(1,*)`` (@ ``0x10100a8f``).

    ``planar`` length ``num_bands * num_lut``; band ``b`` at
    ``planar[i + b * num_lut]``.
    """
    r_i, g_i, b_i = (_i16(x) for x in idx_rgb)
    return (
        _i16(planar[r_i]),
        _i16(planar[g_i + num_lut]),
        _i16(planar[b_i + 2 * num_lut]),
    )


def setshifts_12(
    shifts_a: tuple[int, int, int],
    shifts_b: tuple[int, int, int],
    planar_lut: list[int] | tuple[int, ...],
    num_lut: int = 4096,
) -> tuple[int, int, int]:
    """CN shipped ``(ntd,ctd)=(1,2)`` @ ``0x10100a37`` → OUT 3×int16.

    * ``Y = axis_y(lut[0x60e − A])`` (planar 3-band)
    * ``C1,C2 = axis_c*(0x60e − B)``
    * ``OUT = 0x60e − inverse(Y, C1, C2)``

    Golden vs DLL (``pakon_setshifts_golden``). Host CN path:
    ``pakon_ansel.cn_setshifts_apply_words`` → ``apply_balance_shifts``.
    """
    a_p = _pivot(shifts_a)
    lut_rgb = lookup_3band_planar(a_p, planar_lut, num_lut)
    y, _, _ = fos_opening_axes(*lut_rgb)
    b_p = _pivot(shifts_b)
    _, c1, c2 = fos_opening_axes(*b_p)
    rec = fos_opening_axes_inverse(y, c1, c2)
    return _pivot(rec)


def setshifts_02(
    shifts_a: tuple[int, int, int],
    shifts_b: tuple[int, int, int],
) -> tuple[int, int, int]:
    """``(ntd,ctd)=(0,2)`` @ ``0x10100510`` — same combine, Y from ``A'`` (no LUT)."""
    a_p = _pivot(shifts_a)
    y, _, _ = fos_opening_axes(*a_p)
    b_p = _pivot(shifts_b)
    _, c1, c2 = fos_opening_axes(*b_p)
    return _pivot(fos_opening_axes_inverse(y, c1, c2))


SHIFT_LUTS_PORTED = True  # tier 1: pakon_shift_luts_golden vs the real DLL


def shift_luts(
    shifts: tuple[int, int, int], count: int = 4096
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The three transfer tables ``area_image_apply_lut`` is handed.

    Port of ``fcn.1006c4f0`` (PakonIMAu.dll md5
    ``eea9dcf78ee21d4f7c515a6c2512242d``), the vendor's shift-LUT builder,
    whose whole body is ``out[i] = master[i + shift]`` over the singleton at
    ``0x106b5f74``. That master table is a clamped identity ramp spanning
    signed index ``-0x8000..0x7fff``, so the tables reduce to

        ``lut[i] = clip(i + shift, 0, 4095)``

    which is the same arithmetic ``apply_balance_shifts`` performs directly on
    pixels. Both forms are kept because the vendor's own call graph uses the
    table form at ``area_image_apply_lut`` and the direct form elsewhere; a
    disagreement between them would be a real bug, and the golden harness
    checks the table form against the DLL rather than against this file.

    Verified bit-exact against the real DLL running under Wine --
    ``pakon_shift_luts_golden.py``. NOT verified by Unicorn: the master table
    lives in uninitialised ``.data`` and is built by the DLL's own
    initialisers, so an emulator would have to be handed a fabricated table.
    """
    idx = np.arange(int(count), dtype=np.int32)
    return tuple(  # type: ignore[return-value]
        np.clip(idx + int(s), 0, MASTER_MAX).astype("<i2") for s in shifts
    )


import ctypes
import os

HERE = os.path.dirname(os.path.abspath(__file__))
_LIB_ANSEL = None
try:
    _dylib_path = os.path.join(HERE, "libpakon_ansel.dylib")
    if not os.path.exists(_dylib_path):
        _dylib_path = os.path.join(HERE, "libpakon_ansel.so")
    if os.path.exists(_dylib_path):
        _LIB_ANSEL = ctypes.CDLL(_dylib_path)
        _LIB_ANSEL.pakon_apply_balance_shifts_c.argtypes = [
            ctypes.POINTER(ctypes.c_int32),
            ctypes.POINTER(ctypes.c_int32),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int16),
        ]
        _LIB_ANSEL.pakon_apply_balance_shifts_c.restype = None
except Exception:
    _LIB_ANSEL = None


def apply_balance_shifts(rpd12: np.ndarray, shifts: tuple[int, int, int]) -> np.ndarray:
    """Pakon apply: ``out = clamp(code + shift, 0, 4095)`` per channel.

    ``shifts`` must be the three int16 values that reach
    ``applyBalanceShifts`` (setShifts **OUT**, not raw ``+0x3a38`` for
    shipped CN). Host CN default calls this with ``setshifts_12(A, A)``.
    """
    x = np.ascontiguousarray(rpd12, dtype=np.int32)
    out = np.empty_like(x)
    shifts_i16 = (ctypes.c_int16 * 3)(int(shifts[0]), int(shifts[1]), int(shifts[2]))

    if _LIB_ANSEL is not None:
        num_pixels = x.shape[0] * x.shape[1]
        _LIB_ANSEL.pakon_apply_balance_shifts_c(
            x.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
            out.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
            ctypes.c_int(num_pixels),
            shifts_i16,
        )
        return out.astype(rpd12.dtype, copy=False)

    for c, s in enumerate(shifts):
        out[:, :, c] = np.clip(x[:, :, c] + int(s), 0, MASTER_MAX)
    return out.astype(rpd12.dtype, copy=False)
