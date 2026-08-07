#!/usr/bin/env python3
"""Preference / Sba shift-path notes (PakonIMAu.dll) — verified fragments only.

``PREFERENCE_SHIFTS_PORTED=True`` for Unicorn-golden mode ``hi=0x10``
(``dU=dV=0``) with ``lo∈{0,1,2,3,4}`` → ``scene+0x3a38`` =
``ftol2(inv(s', −U, −V))``. Shipped CN still runs ``setShifts`` ``(1,2)``
before apply (``docs/52`` / ``SETSHIFTS_12_PORTED``) — Preference words are
not apply LUT inputs. ``hi≠0x10`` UV aims remain open.

See ``docs/49-preference-fpu-binary.md`` for the FPU map; ``docs/48`` for
opening RGB = dpi ``fpo``.

Opening RGB + ``w1e`` (Update 3) — SOLVED
=========================================
* Blob ``+0`` ← ``scene+0x4d0e`` = nested **``fpo``** (``+0x1e/+20/+22``).
* Blob ``+0x1e`` / ``w1e`` ← ``scene+0x4d14`` = nested **``pcls``**
  (``inner+0x24``). Dump ``0x102ae48f`` prints ``\\tpcls = \\t`` from
  ``[ebx+0x24]``; ``readAscii`` parses ``"pcls"`` @ ``0x102ad38d`` into
  ``obj+0x24``. **All shipped ``sba-*.dpi`` have ``pcls = 0``.**
* Host loads ``fpo``/``fpa``/``pcls``/clamp fields from dpi; CN apply uses
  ``setshifts_12(A, A)`` on Preference words (``docs/52``), not raw
  Preference passthrough.

FOS OUT ``+0x1e/+20/+22`` are unrelated stats (``docs/47``).

VERIFIED (image base ``0x10000000``)
====================================

Call chain (analyzePass2)
-------------------------
* ``Preference`` @ ``0x1028c780`` from ``0x10216444`` with
  ``scene+0x38a2``, FOS-get arg1, ``scene+0x3a30``, blob, mode
  ``scene+0x5074``.
* External calls only: ``0x1028c540``, ``0x104ffe44`` (×5) — no soft walls.
* Clamp @ ``0x1028cbbb…cc1f`` leaves **clamped** ``s'`` on the FPU.
* ``out+2`` (``scene+0x3a32``): first inv @ ``0x1028cc1f``/``cc27`` uses
  ``t' = lim46 − s'`` with **+U/+V**.
* Shifts: ``add esi,8`` @ ``0x1028ccdf`` then ``fist`` stores →
  ``scene+0x3a38/+3a3a/+3a3c`` = ``inv(s', −U_r, −V_r)`` (second inv @
  ``0x1028cc79`` multiplies remaining ``s'`` by ``INV_SQRT3``).
* Common pass2 forces hi→``0x10`` (@ ``0x10216356``) and often lo→``1``
  (@ ``0x1021640e``, ``edi=1``) ⇒ mode ``0x11`` with ``pcls=0`` ⇒
  ``dY=dU=dV=0``.

Opponent + inverse (Preference)
-------------------------------
Forward @ ``0x1028c7f7`` (opening / ``fpa``):

* ``Y = (R+G+B) * (1/√3)``   ``0x105a6f38``
* ``U = (2G−R−B) * (1/√6)``  ``0x105a6f30``
* ``V = (B−R) * (1/√2)``     ``0x105a6f28``

Inverse @ ``0x1028cc33`` / ``0x1028cc79`` (store path; ``Y`` arg is
``t'`` for ``+2``, ``s'`` for shifts):

* ``R = Y/√3 − U/√6 − V/√2``
* ``G = Y/√3 + U·√(2/3)``    ``√(2/3)`` @ ``0x105a6f40``
* ``B = Y/√3 − U/√6 + V/√2``

Core combine (``0x1028ca4c…cbad``)
---------------------------------
``dY/dU/dV`` from mode aims − opening; helper ``neu`` if ``dY≤0`` else ``neo``;
``Y_r = Y+Y2 + m·iDY`` etc. (see docs/49). Mode ``0x11`` + ``pcls=0``
collapses to ``opponent(fpo+fpa)`` then ``inv(s', −U, −V)`` for shifts.

Apply path caution
------------------
``applyBalanceShifts`` @ ``0x1019a0c0`` feeds three int16s straight into
LUT build ``0x1006c4f0`` (``out[i]=master[i+shift]``). ``getShifts`` copies
``+0x3a38`` raw. ``setShifts`` @ ``0x10100260`` control words are SCPLut
``ntdChoice``/``ctdChoice``; shipped CN → ``(1, 2)`` transform
(``0x60e`` + LUT + ``×0x186a0``), **not** ``(0, 0)`` passthrough and **not**
``(2, 2)`` (that copies getShifts buffer B). See ``docs/52``. Host default
applies ``setshifts_12(A, A)`` OUT (gated on ``PREFERENCE_SHIFTS_PORTED``
and ``SETSHIFTS_12_PORTED``); raw ``+0x3a38`` is never apply input for CN.

Apply helper: ``tools/ansel/pakon_sba_apply.py``.
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

# Golden vs DLL for hi=0x10 + lo∈{0,1,2,3,4} (pakon_preference_golden.py).
# Host apply still goes through setShifts (1,2); hi≠0x10 UV aims open.
PREFERENCE_SHIFTS_PORTED = True
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


def ftol2_104ffe44(x: float) -> int:
    """Byte-checked ``0x104ffe44``: C cast / chop toward zero → ``eax``.

    Unicorn probe: ``0.5→0``, ``2.5→2``, ``-0.5→0``, ``-2.5→-2``,
    ``1200.888→1200``. Not IEEE round-nearest.
    """
    return int(math.trunc(x))


def fist_round_i16(x: float) -> int:
    """Preference store / combine int conversion via ``0x104ffe44``."""
    return ftol2_104ffe44(x)


def clamp_preference_s_prime(
    t: float,
    lim46: float,
    lo42: float,
    hi44: float,
) -> float:
    """Clamp @ ``0x1028cbbb…cc1f``: ``s' = clamp(lim46 − t, lo, hi)``.

    Leaves ``s'`` on the FPU for the shift inv @ ``0x1028cc79``.
    """
    s = lim46 - t
    if s < lo42:
        return lo42
    if s > hi44:
        return hi44
    return s


def clamp_preference_t_prime(
    t: float,
    lim46: float,
    lo42: float,
    hi44: float,
) -> float:
    """``t' = lim46 − s'`` for the ``out+2`` inv @ ``0x1028cc1f``/``cc27``."""
    return lim46 - clamp_preference_s_prime(t, lim46, lo42, hi44)


# Back-compat alias: older call sites meant ``t'``; prefer the named helpers.
def clamp_preference_y(
    t: float,
    lim46: float,
    lo42: float,
    hi44: float,
) -> float:
    """Deprecated name for ``clamp_preference_t_prime`` (``out+2`` path)."""
    return clamp_preference_t_prime(t, lim46, lo42, hi44)


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


def preference_out_plus2_from_combined(
    combined: OpponentYUV,
    w1e: float,
    lim46: float,
    lo42: float,
    hi44: float,
) -> tuple[int, int, int]:
    """``out+2`` / ``scene+0x3a32``: ``ftol2(inv(t', +U_r, +V_r))``.

    Cite: first inv after clamp @ ``0x1028cc1f``/``cc27``.
    """
    t = combined.y - w1e
    t_prime = clamp_preference_t_prime(t, lim46, lo42, hi44)
    r, g, b = preference_opponent_to_rgb(t_prime, combined.u, combined.v)
    return ftol2_104ffe44(r), ftol2_104ffe44(g), ftol2_104ffe44(b)


def preference_shifts_from_combined(
    combined: OpponentYUV,
    w1e: float,
    lim46: float,
    lo42: float,
    hi44: float,
) -> tuple[int, int, int]:
    """Final shift triple: ``ftol2(inv(s', −U_r, −V_r))`` @ ``0x1028cce7``.

    ``s' = clamp(lim46 − (Y_r − w1e), lo, hi)`` — remaining FPU value after
    clamp @ ``0x1028cbbb…cc1f``; second inv @ ``0x1028cc79``.
    """
    t = combined.y - w1e
    s_prime = clamp_preference_s_prime(t, lim46, lo42, hi44)
    r, g, b = preference_opponent_to_rgb(s_prime, -combined.u, -combined.v)
    return ftol2_104ffe44(r), ftol2_104ffe44(g), ftol2_104ffe44(b)


def preference_aim_y(
    lo: int,
    opening_y: float,
    *,
    param0: int = 0,
    param_0x12: int = 0,
    param_0x40: int = 0,
    arg1_0: int = 0,
) -> float:
    """Low-nibble ``aimY`` @ ``0x1028c92f…98e``.

    Entry null-check @ ``0x1028c7a7…7d3`` also requires non-null arg1 when
    ``lo∈{3,4}`` (or hi∈{``0x30``,``0x40``}) even if lo=4 never reads arg1.
    """
    lo_n = lo & 0xF
    if lo_n == 1:
        return opening_y
    if lo_n == 2:
        return float(int(param_0x12)) * SQRT3
    if lo_n == 3:
        return float(int(arg1_0))
    if lo_n == 4:
        return float(int(param_0x40)) + opening_y
    return float(int(param0))  # lo==0 / else


def preference_shifts_hi10(
    fpo: Sequence[int],
    fpa: Sequence[int],
    *,
    lo: int,
    lim46: float,
    lo42: float,
    hi44: float,
    pcls: int = 0,
    neu: Sequence[int] = (975, 975, 975),
    neo: Sequence[int] = (1010, 1010, 1010),
    non_flash_adj: int = 0,
    param0: int = 0,
    param_0x12: int = 0,
    param_0x40: int = 0,
    arg1_0: int = 0,
) -> tuple[int, int, int]:
    """Preference shifts for ``hi=0x10`` (``dU=dV=0``) + any cited ``lo``.

    Unicorn-golden for ``lo∈{0,1,2,3,4}``. ``hi≠0x10`` not covered.
    """
    opening = preference_rgb_to_opponent(int(fpo[0]), int(fpo[1]), int(fpo[2]))
    fpa_opp = preference_rgb_to_opponent(int(fpa[0]), int(fpa[1]), int(fpa[2]))
    aim_y = preference_aim_y(
        lo,
        opening.y,
        param0=param0,
        param_0x12=param_0x12,
        param_0x40=param_0x40,
        arg1_0=arg1_0,
    )
    w1e = float(int(pcls))
    d_y = w1e + aim_y - opening.y
    helper_rgb = neo if d_y > 0.0 else neu
    helper = helper_1028c540(
        int(helper_rgb[0]), int(helper_rgb[1]), int(helper_rgb[2])
    )
    scale = float(int(non_flash_adj)) * SCALE_0_001
    combined = preference_combine_yuv(
        opening, fpa_opp, d_y, 0.0, 0.0, helper, scale
    )
    return preference_shifts_from_combined(
        combined, w1e, lim46, lo42, hi44
    )


def preference_shifts_mode_0x11(
    fpo: Sequence[int],
    fpa: Sequence[int],
    *,
    lim46: float,
    lo42: float,
    hi44: float,
    pcls: int = 0,
    neu: Sequence[int] = (975, 975, 975),
    neo: Sequence[int] = (1010, 1010, 1010),
    non_flash_adj: int = 0,
) -> tuple[int, int, int]:
    """Mode lo=1, hi=0x10 (docs/49): ``aimY=Y``, ``aimU/V=U/V``."""
    return preference_shifts_hi10(
        fpo,
        fpa,
        lo=1,
        lim46=lim46,
        lo42=lo42,
        hi44=hi44,
        pcls=pcls,
        neu=neu,
        neo=neo,
        non_flash_adj=non_flash_adj,
    )


def preference_shifts_mode_0x11_w1e0(
    fpo: Sequence[int],
    fpa: Sequence[int],
    *,
    lim46: float,
    lo42: float,
    hi44: float,
    pcls: int = 0,
    neu: Sequence[int] = (975, 975, 975),
    neo: Sequence[int] = (1010, 1010, 1010),
    non_flash_adj: int = 0,
) -> tuple[int, int, int]:
    """Alias of ``preference_shifts_mode_0x11`` (name kept for callers)."""
    return preference_shifts_mode_0x11(
        fpo,
        fpa,
        lim46=lim46,
        lo42=lo42,
        hi44=hi44,
        pcls=pcls,
        neu=neu,
        neo=neo,
        non_flash_adj=non_flash_adj,
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
    """Mode-``0x11`` Preference shifts from shipped dpi scalars.

    Does not apply ``setShifts`` transforms — caller must run ``(1,2)`` for CN.
    """
    fpo_i = opening_rgb_from_sba_fpo(fpo)
    fpa_i = (int(fpa[0]), int(fpa[1]), int(fpa[2]))
    lim46 = lim46_from_neutral_balance_point(int(neutral_balance_point))
    lo42, hi44 = clamp_limits_from_neutral_button(
        int(neutral_button), under_constraint, over_constraint
    )
    return preference_shifts_mode_0x11(
        fpo_i, fpa_i, lim46=lim46, lo42=lo42, hi44=hi44, pcls=int(pcls)
    )


def lim46_from_neutral_balance_point(nbp: int) -> int:
    """Approx blob ``+0x46``: ``round(NBP · √3)`` (fill path ``0x10215084``).

    Integer magic is ``*0x2a495`` then reciprocal ``0x14f8b589``; this float
    form matches shipped defaults (e.g. 1550 → 2685) but is not bit-claimed.
    Blob fill is **not** ``0x104ffe44`` (chop).
    """
    return int(round(float(nbp) * math.sqrt(3.0)))


def clamp_limits_from_neutral_button(
    neutral_button: int,
    under_constraint: float,
    over_constraint: float,
) -> tuple[int, int]:
    """Blob ``+0x42/+0x44``: ``fist(neutralButton · under/overConstraint)``.

    Cite: blob fill ``0x10215048…80`` with qwords at ``scene+0x4d40/48``.
    Uses nearest ``round`` (fill path), not Preference store ``0x104ffe44``.
    """
    return (
        int(round(neutral_button * under_constraint)),
        int(round(neutral_button * over_constraint)),
    )
