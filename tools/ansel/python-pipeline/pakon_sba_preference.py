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
* **CORRECTED — the live mode is 0, not ``0x11``.** An earlier reading of
  ``0x10216356`` / ``0x1021640e`` concluded common pass2 forces hi→``0x10``
  and lo→``1``.  It does not on the shipped CN path: **all 882 captured
  ``sba_preference`` calls across 23 scans pass ``mode = 0``**
  (``scene+0x5074``; ``pakon_preference_shift_golden``).  Mode 0 takes
  ``aimY`` from ``pref_data+0`` and ``aimU``/``aimV`` from
  ``pref_data+2``/``+4``, so ``dU``/``dV`` are non-zero and the ``0x11``
  collapse to ``dY=dU=dV=0`` never happens live.  Use
  :func:`preference_full`; the ``0x11`` helpers below are kept for the
  fragments docs/49 walked, not as a model of the live call.

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

Apply helper: ``tools/ansel/python-pipeline/pakon_sba_apply.py``.
"""
from __future__ import annotations

import math
import struct
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
PREFERENCE_HI_UV_PORTED = True
SBA_CORE_PORTED = False

#: ``preference_full`` — the WHOLE of ``fcn.1028c780`` from its raw inputs
#: (``pref_data``, ``blob``, ``mode``), verified bit-exact against the real
#: DLL under Unicorn and against the vendor's own captured output words.
#: Harness: ``pakon_preference_shift_golden.py``.  See §PREF-FULL below.
PREFERENCE_FULL_PORTED = True


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


def preference_aim_uv(
    hi: int,
    opening_u: float,
    opening_v: float,
    *,
    neu: Sequence[int] = (975, 975, 975),
    lo42: float = 0.0,
    hi44: float = 0.0,
    fpo: Sequence[int] = (0, 0, 0),
    arg1_2: int = 0,
    arg1_4: int = 0,
    param_uv: Sequence[int] = (0, 0),
    param_0x0c: Sequence[int] | None = None,
    param_0x42: Sequence[int] | None = None,
) -> tuple[float, float]:
    """High-nibble ``aimU``, ``aimV`` @ ``0x1028c98e``.

    Cite: docs/49-preference-fpu-binary.md.

    The ``hi=0`` else-branch reads ``arg1[2]/arg1[4]`` (the *param* struct
    ``[ebp+8]``, i.e. ``scene+0x38a2`` — live = per-frame FOS orderFpo U/V),
    **not** the blob ``fpo`` — see docs/74 sec68. ``param_uv`` carries those
    two words.

    **Two branches corrected, tier 1.**  The ``hi=0x20`` and ``hi=0x40``
    branches previously read the DPI ``neu`` triple and the blob clamp limits.
    Both are wrong: ``0x1028c9ae`` reads ``pref_data+0x0c/+0x0e/+0x10`` and
    ``0x1028ca15`` reads ``pref_data+0x42/+0x44``.  The divergence was first
    recorded (not patched) by the ``preference_full`` pass; it is now settled
    against the real DLL under Unicorn on real captured buffers, forcing each
    mode in turn — ``preference_full`` reproduces the DLL 12/12 on
    ``0x20``/``0x21`` and 12/12 on ``0x40``/``0x41``, while this function's old
    reading matched 0/24.  (``0x40`` needed a non-NULL ``arg1`` to reach at
    all: the entry guard at ``0x1028c7c8`` fires first, and ``arg1`` is NULL on
    every captured live call, which is why the first pass could not decide it.)
    ``hi=0x00``/``0x10``/``0x30`` were checked the same way and agree 24/24.

    Neither corrected branch is reachable on the live CN path — all 882
    captured calls are ``mode = 0`` — so no shipped render changes.
    ``param_0x0c``/``param_0x42`` carry the correct sources; when they are not
    supplied the old (wrong) substitutes are kept rather than silently
    inventing values, and callers that need those modes should prefer
    :func:`preference_full`, which takes the real buffers.
    """
    hi_n = hi & 0xF0
    if hi_n == 0x10:
        return opening_u, opening_v
    if hi_n == 0x20:                                  # 0x1028c9ae
        src = param_0x0c if param_0x0c is not None else neu
        opp = preference_rgb_to_opponent(int(src[0]), int(src[1]), int(src[2]))
        return opp.u, opp.v
    if hi_n == 0x30:
        return float(int(arg1_2)), float(int(arg1_4))
    if hi_n == 0x40:                                  # 0x1028ca15
        src = param_0x42 if param_0x42 is not None else (lo42, hi44)
        return float(int(src[0])), float(int(src[1]))
    # else (hi=0): arg1[2]/arg1[4] = param struct +0x02/+0x04
    return float(int(param_uv[0])), float(int(param_uv[1]))


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


def preference_shifts_hiNN(
    fpo: Sequence[int],
    fpa: Sequence[int],
    *,
    hi: int,
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
    arg1_2: int = 0,
    arg1_4: int = 0,
    param_uv: Sequence[int] = (0, 0),
    param_0x0c: Sequence[int] | None = None,
    param_0x42: Sequence[int] | None = None,
) -> tuple[int, int, int]:
    """Preference shifts for arbitrary ``hi`` and ``lo`` modes.
    
    Includes non-zero ``dU``/``dV`` UV aim computation for ``hi≠0x10``.
    Cite: docs/49-preference-fpu-binary.md.

    ``param_uv`` = the param struct's ``+0x02/+0x04`` words (``scene+0x38a2``
    live, i.e. the per-frame FOS orderFpo U/V) — the ``hi=0`` else-branch aim
    (docs/74 sec68).
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
    aim_u, aim_v = preference_aim_uv(
        hi,
        opening.u,
        opening.v,
        neu=neu,
        lo42=lo42,
        hi44=hi44,
        fpo=fpo,
        arg1_2=arg1_2,
        arg1_4=arg1_4,
        param_uv=param_uv,
        param_0x0c=param_0x0c,
        param_0x42=param_0x42,
    )
    w1e = float(int(pcls))
    d_y = w1e + aim_y - opening.y
    d_u = aim_u - opening.u
    d_v = aim_v - opening.v
    
    helper_rgb = neo if d_y > 0.0 else neu
    helper = helper_1028c540(
        int(helper_rgb[0]), int(helper_rgb[1]), int(helper_rgb[2])
    )
    scale = float(int(non_flash_adj)) * SCALE_0_001
    combined = preference_combine_yuv(
        opening, fpa_opp, d_y, d_u, d_v, helper, scale
    )
    return preference_shifts_from_combined(
        combined, w1e, lim46, lo42, hi44
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


# ---------------------------------------------------------------------------
# §PREF-FULL — the whole of ``fcn.1028c780`` from its raw captured inputs
# ---------------------------------------------------------------------------
#
# The helpers above take *derived* scalars (``fpo``, ``fpa``, ``lim46`` …) and
# cover only the mode combinations docs/49 walked.  ``preference_full`` below
# takes the two raw structures the vendor actually passes — ``pref_data``
# (arg 0, ``scene+0x38a2``, the per-frame ``orderFpo`` block) and ``blob``
# (arg 3, the DPI-derived parameter block) — plus ``mode`` (arg 4), and
# reproduces BOTH words the function writes:
#
#   ``arg2+0x02`` (``scene+0x3a32``)  the anchor triple
#   ``arg2+0x08`` (``scene+0x3a38``)  the shift triple
#
# Two divergences from the derived-scalar helpers above, found by reading the
# full body at its own ``af``/``pdf`` boundary and confirmed by execution:
#
#   * ``hi == 0x20`` reads ``pref_data+0x0c/+0x0e/+0x10`` (``0x1028c9ae``),
#     NOT the DPI ``neu`` triple that ``preference_aim_uv`` substitutes.
#   * ``hi == 0x40`` reads ``pref_data+0x42/+0x44`` (``0x1028ca15``), NOT the
#     blob clamp limits ``+0x42/+0x44`` that ``preference_aim_uv`` substitutes.
#
# Neither is reachable on the live CN path — every one of the 1,323 captured
# live calls across 23 scans passes ``mode = 0`` — so nothing shipped changes;
# the divergences are recorded rather than silently corrected in place.
#
# Float association order below is the DLL's, instruction by instruction, not
# algebraically tidied: ``fadd``/``fmul`` are not associative and the results
# are truncated by ``_ftol``, so a re-ordered sum can land on the other side of
# an integer boundary.


#: Every ``blob`` word ``preference_full`` reads, and the shipped ``sba-*.dpi``
#: key it comes from.  Established tier 2: a live blob dumped at
#: ``sba_preference`` entry was compared word-by-word against
#: ``sba-CN-default.dpi`` over the whole 0x48-byte structure, and every
#: non-zero word matches a dpi key --
#:
#:   +0x00 fpo   +0x06 fpa   +0x0c neu   +0x12 neo   +0x18 dmd   +0x1e pcls
#:   +0x20 pcwf  +0x22 ix_pcwf +0x24 nonFlashAdj +0x26 fmt +0x28/+0x2a 50/83
#:   +0x2c a POINTER (the only words that vary across the 882 captured calls,
#:         and read by nothing in this function)
#:   +0x30 cmm   +0x32 fog   +0x34 fxr   +0x36 blk   +0x38 bxr   +0x3a ll1
#:   +0x3c ll2   +0x3e 140   +0x40 mff   +0x42/+0x44 clamp  +0x46 lim46
#:
#: so the blob is roll-static and fully derivable from the dpi.  The per-frame
#: variation lives entirely in ``pref_data``.
BLOB_IS_DPI_STATIC = True


def build_preference_blob(
    *,
    fpo: Sequence[int] | Sequence[float],
    fpa: Sequence[int] | Sequence[float],
    neu: Sequence[int] | Sequence[float] = (975, 975, 975),
    neo: Sequence[int] | Sequence[float] = (1010, 1010, 1010),
    pcls: int | float = 0,
    cmm: int | float = 1000,
    neutral_balance_point: int | float = 1550,
    neutral_button: int | float = 130,
    under_constraint: float = -16.0,
    over_constraint: float = 16.0,
) -> bytes:
    """The 0x48-byte ``blob`` (arg 3) that ``preference_full`` reads.

    Only the words the function actually loads are filled; the rest is zero,
    which is sound because ``preference_full`` never reads them (see the
    offset table above).  ``lim46``/``+0x42``/``+0x44`` use the same fill-path
    rounding as ``lim46_from_neutral_balance_point`` /
    ``clamp_limits_from_neutral_button`` (``0x10215048…84``).
    """
    b = bytearray(0x48)

    def put(off: int, v: int) -> None:
        struct.pack_into("<h", b, off, _i16(int(v)))

    for i in range(3):
        put(0x00 + 2 * i, int(fpo[i]))
        put(0x06 + 2 * i, int(fpa[i]))
        put(0x0C + 2 * i, int(neu[i]))
        put(0x12 + 2 * i, int(neo[i]))
    put(0x1E, int(pcls))
    put(0x30, int(cmm))
    lo42, hi44 = clamp_limits_from_neutral_button(
        int(neutral_button), under_constraint, over_constraint
    )
    put(0x42, lo42)
    put(0x44, hi44)
    put(0x46, lim46_from_neutral_balance_point(int(neutral_balance_point)))
    return bytes(b)


def build_preference_pref_data(order_fpo: Sequence[int]) -> bytes:
    """The 0x48-byte ``pref_data`` (arg 0) for a **mode-0** call.

    Mode 0 reads exactly four words: ``+0/+2/+4`` (the per-frame ``orderFpo``
    Y/U/V aim triple) and ``+0x3e`` (copied to ``arg2+0``, not an aim).  The
    ``+0x3e`` fill is 0 because that word is an output passthrough and is 0 on
    all 882 captured live calls.
    """
    pd = bytearray(0x48)
    for i in range(3):
        struct.pack_into("<h", pd, 2 * i, _i16(int(order_fpo[i])))
    return bytes(pd)


def static_order_fpo_from_blob(blob: bytes) -> tuple[int, int, int]:
    """The zero-delta ``orderFpo`` stand-in: the blob ``fpo``'s own axes.

    With no per-frame FOS analysis there is no ``orderFpo`` delta to add, so
    the aim triple is the opening triple's own opponent transform.  Rounding
    to nearest guarantees ``|aim - opponent| <= 0.5 < 1``, and
    ``preference_full`` truncates every delta with ``_ftol`` *before* using it,
    so ``i_dy = i_du = i_dv = 0`` **identically** -- which is precisely the
    mode-``0x11`` fragment's collapse.  So a mode-0 call built this way
    reproduces the old ``preference_shifts_mode_0x11`` triple bit-for-bit, for
    every dpi and not merely the shipped one.  This is a provable identity,
    not a fitted agreement.
    """
    v0, v1, v2 = (struct.unpack_from("<h", blob, o)[0] for o in (0, 2, 4))
    op_y = ((float(v2) + v1) + v0) * INV_SQRT3
    op_u = ((2.0 * v1 - v0) - v2) * INV_SQRT6
    op_v = (float(v2) - v0) * INV_SQRT2
    return int(round(op_y)), int(round(op_u)), int(round(op_v))


def _w(buf, off: int) -> int:
    """``movsx r32, word [buf + off]``."""
    return int(struct.unpack_from("<h", buf, off)[0])


def _i16(v: int) -> int:
    """``mov word [dst], ax`` — the store truncates the ``_ftol`` result."""
    v &= 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


def preference_full(
    pref_data: bytes,
    blob: bytes,
    mode: int,
    arg1: bytes | None = None,
) -> tuple[tuple[int, int, int], tuple[int, int, int], int] | None:
    """Whole-function port of ``Preference`` (``fcn.1028c780``).

    Returns ``(anchor, shift, out0)`` where ``anchor`` is the triple stored at
    ``arg2+0x02``, ``shift`` the triple at ``arg2+0x08``, and ``out0`` the
    single word copied to ``arg2+0x00`` from ``pref_data+0x3e``
    (``0x1028cc23``/``0x1028cc29`` — this is why a 6-byte dump taken at
    ``arg2+0`` reads one word "early", docs/74 §160.3).

    Returns ``None`` for the entry guard at ``0x1028c7c3`` (vendor error
    ``0x18a4``): ``arg1`` NULL while the mode selects an ``arg1`` aim.

    ``pref_data`` must be at least 0x44 bytes, ``blob`` at least 0x48.
    """
    if len(blob) < 0x48:
        raise ValueError(f"blob needs >= 0x48 bytes, got {len(blob):#x}")
    if len(pref_data) < 0x44:
        raise ValueError(
            f"pref_data needs >= 0x44 bytes, got {len(pref_data):#x}")
    lo = mode & 0x0F
    hi = mode & 0xF0
    if (lo in (3, 4) or hi in (0x30, 0x40)) and not arg1:
        return None                                   # 0x1028c7c8: eax=0x18a4

    # 0x1028c7d4…0x1028c8a5 — opponent transform of the opening triple
    # blob[0]/[2]/[4].
    v0, v1, v2 = _w(blob, 0), _w(blob, 2), _w(blob, 4)
    op_y = ((float(v2) + v1) + v0) * INV_SQRT3
    op_u = ((2.0 * v1 - v0) - v2) * INV_SQRT6
    op_v = (float(v2) - v0) * INV_SQRT2

    # 0x1028c92f — aim Y, selected by the mode's low nibble.
    if lo == 1:
        aim_y = op_y                                  # 0x1028c939 fld st(0)
    elif lo == 2:
        aim_y = _w(pref_data, 0x12) * SQRT3           # 0x1028c943
    elif lo == 3:
        aim_y = float(_w(arg1, 0))                    # 0x1028c95d
    elif lo == 4:
        aim_y = float(_w(pref_data, 0x40)) + op_y     # 0x1028c973
    else:
        aim_y = float(_w(pref_data, 0))               # 0x1028c983

    # 0x1028c98e — aim chroma, selected by the high nibble.
    if hi == 0x10:
        aim_u, aim_v = op_u, op_v                     # 0x1028c998
    elif hi == 0x20:                                  # 0x1028c9ae
        c, d, a = (_w(pref_data, 0x0C), _w(pref_data, 0x0E),
                   _w(pref_data, 0x10))
        aim_u = ((2.0 * d - c) - a) * INV_SQRT6
        aim_v = (float(a) - c) * INV_SQRT2
    elif hi == 0x30:                                  # 0x1028c9f2
        aim_u, aim_v = float(_w(arg1, 2)), float(_w(arg1, 4))
    elif hi == 0x40:                                  # 0x1028ca15
        aim_u, aim_v = (float(_w(pref_data, 0x42)),
                        float(_w(pref_data, 0x44)))
    else:                                             # 0x1028ca2f
        aim_u, aim_v = float(_w(pref_data, 2)), float(_w(pref_data, 4))

    # 0x1028ca47…0x1028ca79 — deltas, and the neu/neo selector.
    d_u = aim_u - op_u
    d_v = aim_v - op_v
    w1e = _w(blob, 0x1E)                              # pcls
    # 0x1028ca6b `fst dword` — the value re-read at 0x1028cbb1 is the FLOAT32
    # round-trip of w1e, not the double.
    w1e_f32 = struct.unpack("<f", struct.pack("<f", float(w1e)))[0]
    d_y = (w1e + aim_y) - op_y
    # 0x1028ca7b fcomp 0.0 / test ah,0x41: <= 0 takes blob+0x0c (neu).
    h0, h1, h2 = helper_1028c540(
        _w(blob, 0x12 if d_y > 0.0 else 0x0C),
        _w(blob, 0x14 if d_y > 0.0 else 0x0E),
        _w(blob, 0x16 if d_y > 0.0 else 0x10),
    )
    scale = _w(blob, 0x30) * SCALE_0_001              # 0x1028caa7/0x1028cac2

    # 0x1028cad0…0x1028cb23 — opponent transform of blob[+6]/[+8]/[+0xa].
    p0, p1, p2 = _w(blob, 6), _w(blob, 8), _w(blob, 0x0A)
    a_y = ((float(p2) + p1) + p0) * INV_SQRT3
    a_u = ((2.0 * p1 - p0) - p2) * INV_SQRT6
    a_v = (float(p2) - p0) * INV_SQRT2

    # 0x1028cb27…0x1028cbad — the combine.  Each delta goes through _ftol
    # BEFORE it is used, so a delta of 0.9 contributes nothing.
    i_dy = float(ftol2_104ffe44(d_y))
    y_r = ((h0 * i_dy) + a_y) + op_y
    i_du = float(ftol2_104ffe44(d_u))
    u_r = (((i_du * scale) + (i_dy * h1)) + a_u) + op_u
    i_dv = float(ftol2_104ffe44(d_v))
    v_r = (((i_dv * scale) + (i_dy * h2)) + a_v) + op_v

    # 0x1028cbb1…0x1028cc1b — clamp.  lim46 = blob+0x46 = round(NBP·√3).
    lim46 = float(_w(blob, 0x46))
    s_prime = clamp_preference_s_prime(
        y_r - w1e_f32, lim46, float(_w(blob, 0x42)), float(_w(blob, 0x44)))
    t_prime = lim46 - s_prime

    anchor = preference_opponent_to_rgb(t_prime, u_r, v_r)      # 0x1028cc33
    shift = preference_opponent_to_rgb(s_prime, -u_r, -v_r)     # 0x1028cc79
    return (
        tuple(_i16(ftol2_104ffe44(x)) for x in anchor),
        tuple(_i16(ftol2_104ffe44(x)) for x in shift),
        _w(pref_data, 0x3E),
    )
