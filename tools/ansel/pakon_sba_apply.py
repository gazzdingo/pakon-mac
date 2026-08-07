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

setShifts control words (VERIFIED — ``docs/52``)
------------------------------------------------
* Filled from **AnsSCPLutCapability** Cap ``+0x10+0x18`` via ``0x10122a70``
  → ``0x10122190``: ``ntdChoice`` / ``ctdChoice`` at ``+0x38`` / ``+0x3a``.
* Dump ``0x101d0050`` names those fields on ``AnsSCPLutDPI``.
* Shipped CN dpi: ``ntd=ANS_LUT_FIRST_PASS``, ``ctd=ANS_SECOND_PASS`` →
  **``(1, 2)``** — **not** ``(0, 0)`` passthrough.
* ``(0, 0)`` → copy Preference/getShifts buffer A → OUT.
* ``(2, 2)`` → copy getShifts buffer B → OUT (not the ``0x60e`` path).
* ``(1, 2)`` → ``0x60e − ch`` + Cap LUT ``0x10122150`` + ``×0x186a0``
  three-axis path — maths **UNKNOWN** / not ported.
* ``AnsLightingAdjust`` ctor ``+0x38=0`` and ``ans_*_pass`` strings are
  **not** this control source (pass tokens are SCPLut DPI only).

UNKNOWN / not wired
-------------------
* Preference FPU → ``+0x3a38`` is mapped (``docs/49``), but CN auto
  ``setShifts`` **transforms** those words on ``(1, 2)``. Keep median
  ``channel_balance`` until that transform and a golden are closed.
  ``PREFERENCE_SHIFTS_PORTED`` stays False.
"""
from __future__ import annotations

import numpy as np

MASTER_MAX = 0xFFF  # 4095

# setShifts pivot (CN (1,2) and related branches) — cite docs/52
SETSHIFTS_PIVOT_0x60E = 0x60E  # 1550
SETSHIFTS_SCALE_0x186A0 = 0x186A0
PATH_SET_SHIFTS = 0x10100260
# Shipped SCPLut dpi control words after readAscii
SHIPPED_CN_SETSHIFTS_CTRL = (1, 2)  # ntd=lut_first, ctd=second


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
