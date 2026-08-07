#!/usr/bin/env python3
"""Verified SBA balance-shift *apply* (PakonIMAu.dll) — not wired by default.

VERIFIED
--------
* ``AnsAreaCapabilityImpl::applyBalanceShifts`` @ ``0x1019a0c0`` builds three
  4096-entry LUTs via ``0x1006c4f0`` on singleton ``0x106b5f74``.
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
* ``PREFERENCE_SHIFTS_PORTED`` stays False; host still uses median
  ``channel_balance`` until Preference→A/B + apply wiring.
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

    Golden vs DLL (``pakon_setshifts_golden``). Not wired into host apply.
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


def apply_balance_shifts(rpd12: np.ndarray, shifts: tuple[int, int, int]) -> np.ndarray:
    """Pakon apply: ``out = clamp(code + shift, 0, 4095)`` per channel.

    ``shifts`` must be the three int16 values that reach
    ``applyBalanceShifts`` (setShifts **OUT**, not raw ``+0x3a38`` for
    shipped CN). Host default path does not call this.
    """
    x = np.asarray(rpd12, dtype=np.int32)
    out = np.empty_like(x)
    for c, s in enumerate(shifts):
        out[:, :, c] = np.clip(x[:, :, c] + int(s), 0, MASTER_MAX)
    return out.astype(rpd12.dtype, copy=False)
