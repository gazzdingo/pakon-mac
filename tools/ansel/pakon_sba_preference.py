#!/usr/bin/env python3
"""Preference / Sba shift-path notes (PakonIMAu.dll) — verified fragments only.

Do **not** treat this module as a complete shift producer. Preference FPU →
``scene+0x3a38`` is still **not** a default port
(``PREFERENCE_SHIFTS_PORTED=False``). Median ``channel_balance`` stays until
``setShifts`` ``(1,2)`` transform maths + golden vs DLL are closed
(``docs/52`` — control words closed; shipped CN is not passthrough).

See ``docs/49-preference-fpu-binary.md`` for the FPU map; ``docs/48`` for
opening RGB = dpi ``fpo``.

Opening RGB + ``w1e`` (Update 3) — SOLVED
=========================================
* Blob ``+0`` ← ``scene+0x4d0e`` = nested **``fpo``** (``+0x1e/+20/+22``).
* Blob ``+0x1e`` / ``w1e`` ← ``scene+0x4d14`` = nested **``pcls``**
  (``inner+0x24``). Dump ``0x102ae48f`` prints ``\\tpcls = \\t`` from
  ``[ebx+0x24]``; ``readAscii`` parses ``"pcls"`` @ ``0x102ad38d`` into
  ``obj+0x24``. **All shipped ``sba-*.dpi`` have ``pcls = 0``.**
* Host should load ``fpo``/``fpa``/``pcls``/clamp fields from dpi; do **not**
  wire into apply as default — shipped CN ``setShifts`` uses ``(1,2)``
  (``docs/52``), not Preference passthrough.

FOS OUT ``+0x1e/+20/+22`` are unrelated stats (``docs/47``).

VERIFIED (image base ``0x10000000``)
====================================

Call chain (analyzePass2)
-------------------------
* ``Preference`` @ ``0x1028c780`` from ``0x10216444`` with
  ``scene+0x38a2``, FOS-get arg1, ``scene+0x3a30``, blob, mode
  ``scene+0x5074``.
* External calls only: ``0x1028c540``, ``0x104ffe44`` (×5) — no soft walls.
* Shifts: ``add esi,8`` @ ``0x1028ccdf`` then ``fist`` stores →
  ``scene+0x3a38/+3a3a/+3a3c`` = ``inv(t', −U_r, −V_r)``.
* Common pass2 forces hi→``0x10`` (@ ``0x10216356``) and often lo→``1``
  (@ ``0x1021640e``, ``edi=1``) ⇒ mode ``0x11`` with ``pcls=0`` ⇒
  ``dY=dU=dV=0``.

Opponent + inverse (Preference)
-------------------------------
Forward @ ``0x1028c7f7`` (opening / ``fpa``):

* ``Y = (R+G+B) * (1/√3)``   ``0x105a6f38``
* ``U = (2G−R−B) * (1/√6)``  ``0x105a6f30``
* ``V = (B−R) * (1/√2)``     ``0x105a6f28``

Inverse @ ``0x1028cc33`` (store path):

* ``R = Y/√3 − U/√6 − V/√2``
* ``G = Y/√3 + U·√(2/3)``    ``√(2/3)`` @ ``0x105a6f40``
* ``B = Y/√3 − U/√6 + V/√2``

Core combine (``0x1028ca4c…cbad``)
---------------------------------
``dY/dU/dV`` from mode aims − opening; helper ``neu`` if ``dY≤0`` else ``neo``;
``Y_r = Y+Y2 + m·iDY`` etc. (see docs/49). Mode ``0x11`` + ``pcls=0``
collapses to ``opponent(fpo+fpa)`` then ``inv(t', −U, −V)``.

Apply path caution
------------------
``applyBalanceShifts`` @ ``0x1019a0c0`` feeds three int16s straight into
LUT build ``0x1006c4f0`` (``out[i]=master[i+shift]``). ``getShifts`` copies
``+0x3a38`` raw. ``setShifts`` @ ``0x10100260`` control words are SCPLut
``ntdChoice``/``ctdChoice``; shipped CN → ``(1, 2)`` transform
(``0x60e`` + LUT + ``×0x186a0``), **not** ``(0, 0)`` passthrough and **not**
``(2, 2)`` (that copies getShifts buffer B). See ``docs/52``. Do not enable
default host apply on Preference outputs yet.

Apply helper (when shifts known): ``tools/ansel/pakon_sba_apply.py``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

# DLL .rdata (verified)
INV_SQRT3 = 0.5773502717125849   # 0x105a6f38
INV_SQRT6 = 0.40824829759439285  # 0x105a6f30
INV_SQRT2 = 0.7071067623730956   # 0x105a6f28
SQRT_2_OVER_3 = 0.8164965951887857  # 0x105a6f40
SQRT3 = 1.7320508                # 0x105a69e0
SCALE_0_001 = 0.0010000000474974513  # 0x105a0800 float
ONE_THIRD = 1.0 / 3.0            # 0x105943c0

# Hardcodes from 0x10214f20
PREF_IN_PLUS_0x28 = 0x32  # 50
PREF_IN_PLUS_0x2A = 0x53  # 83
PREF_IN_PLUS_0x3E = 0x8C  # 140

# Nested opening RGB = AnsSbaDPI+0x80 fpo (docs/48)
# Ctor defaults @ 0x10289ad0/ad6/adc — overwritten by readAscii when dpi loads.
CTOR_DEFAULT_FPO = (930, 1260, 1470)
OPENING_RGB_IS_SBA_DPI_FPO = True  # cite: readAscii + dump 0x102ae437
# w1e = AnsSbaDPI pcls at inner+0x24 (scene+0x4d14); dump 0x102ae48f / parse 0x102ad38d
W1E_IS_SBA_DPI_PCLS = True
CTOR_DEFAULT_PCLS = 0
# Hardcoded in setShifts 0x60e branch (also default NBP)
SETSHIFTS_PIVOT_0x60E = 0x60E  # 1550

# Explicit non-implementation marker for callers / apply wiring.
PREFERENCE_SHIFTS_PORTED = False
SBA_CORE_PORTED = False


@dataclass(frozen=True)
class OpponentYUV:
    """Preference opening transform of integer R,G,B (not /1000)."""
    y: float
    u: float
    v: float


def opening_rgb_from_sba_fpo(fpo: Sequence[float] | Sequence[int]) -> tuple[int, int, int]:
    """Map loaded dpi ``fpo`` → Preference opening RGB int16s.

    Host already parses ``fpo`` in ``SbaParams`` (``pakon_ansel.py``). Cite:
    blob ``+0`` ← ``scene+0x4d0e`` = nested ``fpo`` (docs/48). Truncates
    toward zero like typical ``%hd`` load — not a claim about every writer.
    """
    if len(fpo) < 3:
        raise ValueError("fpo needs 3 components")
    return int(fpo[0]), int(fpo[1]), int(fpo[2])


def preference_rgb_to_opponent(r: int, g: int, b: int) -> OpponentYUV:
    """``0x1028c7f7``: Y/U/V from raw int16 channel codes."""
    rd, gd, bd = float(r), float(g), float(b)
    return OpponentYUV(
        y=(rd + gd + bd) * INV_SQRT3,
        u=(2.0 * gd - rd - bd) * INV_SQRT6,
        v=(bd - rd) * INV_SQRT2,
    )


def preference_opponent_to_rgb(y: float, u: float, v: float) -> tuple[float, float, float]:
    """Inverse @ ``0x1028cc33`` (Preference store path)."""
    ys = y * INV_SQRT3
    us = u * INV_SQRT6
    vs = v * INV_SQRT2
    r = ys - us - vs
    g = ys + u * SQRT_2_OVER_3
    b = ys - us + vs
    return r, g, b


def helper_1028c540(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Byte-faithful port of ``0x1028c540`` (scaled mean + chroma)."""
    m = (r + g + b) * SCALE_0_001 * ONE_THIRD
    out1 = (g * SCALE_0_001 - m) * INV_SQRT2
    out2 = (b * SCALE_0_001 - r * SCALE_0_001) * INV_SQRT6
    return m, out1, out2


def fist_round_i16(x: float) -> int:
    """Approx MSVC ``fistp`` / ``0x104ffe44`` toward nearest.

    Not claimed bit-identical for all edge cases (ties / extremes).
    """
    return int(round(x))


def clamp_preference_y(
    t: float,
    lim46: float,
    lo42: float,
    hi44: float,
) -> float:
    """Y clamp @ ``0x1028cbb1…cc1f``: ``t' = lim46 - clamp(lim46 - t, lo, hi)``."""
    s = lim46 - t
    if s < lo42:
        s = lo42
    elif s > hi44:
        s = hi44
    return lim46 - s


def preference_combine_yuv(
    opening: OpponentYUV,
    fpa_opp: OpponentYUV,
    d_y: float,
    d_u: float,
    d_v: float,
    helper_m_o1_o2: tuple[float, float, float],
    scale: float,
) -> OpponentYUV:
    """Combine @ ``0x1028cb27…cbad`` (after helper + ``fpa`` opponent)."""
    m, o1, o2 = helper_m_o1_o2
    i_dy = fist_round_i16(d_y)
    i_du = fist_round_i16(d_u)
    i_dv = fist_round_i16(d_v)
    return OpponentYUV(
        y=opening.y + fpa_opp.y + m * i_dy,
        u=opening.u + fpa_opp.u + scale * i_du + o1 * i_dy,
        v=opening.v + fpa_opp.v + scale * i_dv + o2 * i_dy,
    )


def preference_shifts_from_combined(
    combined: OpponentYUV,
    w1e: float,
    lim46: float,
    lo42: float,
    hi44: float,
) -> tuple[int, int, int]:
    """Final shift triple: ``round(inv(t', −U_r, −V_r))`` @ ``0x1028cce7``.

    Portable fragment only — callers must supply cited ``w1e``/clamp inputs.
    """
    t = combined.y - w1e
    t_prime = clamp_preference_y(t, lim46, lo42, hi44)
    r, g, b = preference_opponent_to_rgb(t_prime, -combined.u, -combined.v)
    return fist_round_i16(r), fist_round_i16(g), fist_round_i16(b)


def preference_shifts_mode_0x11_w1e0(
    fpo: Sequence[int],
    fpa: Sequence[int],
    *,
    lim46: float,
    lo42: float,
    hi44: float,
    pcls: int = 0,
) -> tuple[int, int, int]:
    """Cited reduction for mode lo=1, hi=0x10 (docs/49).

    With ``pcls`` (``w1e``) = 0 (all shipped dpi): ``dY=dU=dV=0`` →
    ``combined = opponent(fpo+fpa)`` (RGB sum), then ``inv(t', −U, −V)``.
    Non-zero ``pcls`` only affects the final Y clamp input
    (``t = Y_r − pcls``); helper ``neu``/``neo`` stays dead when ``dY=0``.

    Returns Preference ``+0x3a38`` words — **not** proven identical to the
    three int16s ``applyBalanceShifts`` eventually receives after
    ``setShifts``. ``PREFERENCE_SHIFTS_PORTED`` remains False.
    """
    rs = int(fpo[0]) + int(fpa[0])
    gs = int(fpo[1]) + int(fpa[1])
    bs = int(fpo[2]) + int(fpa[2])
    combined = preference_rgb_to_opponent(rs, gs, bs)
    return preference_shifts_from_combined(
        combined, float(int(pcls)), lim46, lo42, hi44
    )


def preference_shifts_from_dpi_fields(
    *,
    fpo: Sequence[int] | Sequence[float],
    fpa: Sequence[int] | Sequence[float],
    neutral_balance_point: int | float,
    neutral_button: int | float,
    under_constraint: float,
    over_constraint: float,
    pcls: int | float = 0,
) -> tuple[int, int, int]:
    """Mode-``0x11`` Preference fragment from shipped dpi scalars.

    Experimental / diagnostic only — does **not** set
    ``PREFERENCE_SHIFTS_PORTED``. Does not apply ``setShifts`` transforms.
    """
    fpo_i = opening_rgb_from_sba_fpo(fpo)
    fpa_i = (int(fpa[0]), int(fpa[1]), int(fpa[2]))
    lim46 = lim46_from_neutral_balance_point(int(neutral_balance_point))
    lo42, hi44 = clamp_limits_from_neutral_button(
        int(neutral_button), under_constraint, over_constraint
    )
    return preference_shifts_mode_0x11_w1e0(
        fpo_i, fpa_i, lim46=lim46, lo42=lo42, hi44=hi44, pcls=int(pcls)
    )


def lim46_from_neutral_balance_point(nbp: int) -> int:
    """Approx blob ``+0x46``: ``round(NBP · √3)`` (fill path ``0x10215084``).

    Integer magic is ``*0x2a495`` then reciprocal ``0x14f8b589``; this float
    form matches shipped defaults (e.g. 1550 → 2685) but is not bit-claimed.
    """
    return fist_round_i16(float(nbp) * math.sqrt(3.0))


def clamp_limits_from_neutral_button(
    neutral_button: int,
    under_constraint: float,
    over_constraint: float,
) -> tuple[int, int]:
    """Blob ``+0x42/+0x44``: ``fist(neutralButton · under/overConstraint)``.

    Cite: blob fill ``0x10215048…80`` with qwords at ``scene+0x4d40/48``.
    """
    return (
        fist_round_i16(neutral_button * under_constraint),
        fist_round_i16(neutral_button * over_constraint),
    )
