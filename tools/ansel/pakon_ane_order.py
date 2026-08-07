#!/usr/bin/env python3
"""AneOrder / NoiseMethods — dens table layout + getResults fill.

PakonIMAu.dll base ``0x10000000``. Catalog + host layout for the float
table CnPremium indexes at mid-aim. ``getResults`` dens **fill** from
Impl curve rows is ported; analyze **bin-index** / dens-hist **accum**
ported; finalize knot leaf ``0x102a7a30`` + adjust ``0x102a78c0`` +
curve-row pack ``0x1027e840`` ported. Neighbor-hist merge ``0x102a82a0``
and full sample/residual → knots orchestration still open →
``ANE_ORDER_PORTED = False``.

VERIFIED call chain
===================

Order-wide analyze
------------------
* Path ``ColorNegativePath::analyzeAneOrder`` @ ``0x100fad90``
* Cap ``AnsAneOrderCapability::analyze`` @ ``0x10110540``
* Impl analyze @ ``0x101ed3a0`` (string ``0x1059b428``):

  1. Walk scenes; QI portfolio names ``AneSampledImage`` /
     ``AneResidualImage`` (``0x1059b2e8`` / ``0x1059b2d4``).
  2. Wrap each via ``0x101ed1b0``; push into vectors (``0x101ed330``).
  3. On non-empty equal-length vectors: ``0x1027e9d0`` on
     Impl ``+0xc0`` (``Ane.cpp`` — mismatch →
     ``"Empty or mismatched sample/residual vectors."``).
  4. ``0x1027e9d0`` drives hist accumulate leaves ``0x102a84d0`` /
     ``0x102a8600`` / ``0x102a8950`` and finalize ``0x102a8770``.

* Cap ``getResults`` @ ``0x10110830`` → Impl ``0x101ebe90``
  (string ``0x1059b3a4``)

Analyze bin-index leaf @ ``0x102a8555…`` (PORTED)
------------------------------------------------
Shared by accumulate helpers (``edi``/``ebp``/``ebx`` = Ane object):

* ``bin = (pixel − [obj+0x34]) / [obj+0x3c]`` — MSVC ``idiv`` (trunc
  toward 0); clamp to ``[0, obj+0x44]``.
* ``slot = [obj+0x40] * plane + bin`` (``imul`` + ``add``).

``ANE_ANALYZE_BIN_INDEX_PORTED = True``.

Dens-hist accumulate leaf @ ``0x104f56e0`` (PORTED + Unicorn)
------------------------------------------------------------
Called from accumulate ``0x102a84d0`` after bin-index slot lookup
(``0x104eab20`` → hist*; ``0x104ea370`` → this leaf):

* ``bin = ftol2((value − [hist+0x10]) / [hist+0x28])`` (doubles;
  ``0x104ffe44`` chop).
* Clamp ``bin`` to ``[0, [hist+0xc])`` (``n-1`` max).
* ``inc dword [[hist+0x38] + bin*4]``.

``ANE_ANALYZE_HIST_ACCUM_PORTED = True``.

Finalize ``0x102a8770`` → knot doubles (leaves PORTED)
-----------------------------------------------------
Per ``(plane, bin)``: neighbor merge ``0x102a82a0`` (COM; open) then
knot leaf ``0x102a7a30`` (PORTED + Unicorn) writes a ``double`` into
the ``+0x78`` plane vectors. Optional adjust ``0x102a78c0`` (PORTED)
when finalize flag set and ``[obj+0x2c]==0``. Scale pass ``0x104ee9c0``
multiplies plane vectors when arg ≠ 1.

Knot leaf ``0x102a7a30`` (hist counts → double):

* Early-out ``0.0`` when ``sum(counts) < min_count``.
* ``mid = n//2`` (MSVC sar); each side (high/low) accumulates
  ``sum_c`` / ``sum_c·Δ`` / ``sum_c·Δ²`` with ``Δ = i−mid``, stopping
  after **2** zero bins (total, not reset); each side's ``sum_c``
  seeds with ``counts[mid]//2``.
* ``rms_high`` / ``rms_low`` = ``√(ΣcΔ² / Σc)`` per side; ``mean`` =
  combined ``ΣcΔ / Σc``.
* Windowed core RMS inside ``±scale·rms_{high|low}`` (same zero stop);
  blend ``(1−t)·r_neg + t·r_pos`` with ``t`` from mean (cite DLL).

``ANE_ANALYZE_FINALIZE_KNOT_PORTED = True``.
``ANE_ANALYZE_FINALIZE_ADJUST_PORTED = True``.

Curve rows from plane doubles @ ``0x1027e840`` (PORTED)
------------------------------------------------------
``getResults`` copies ``+0x78`` doubles → float rows: plane0 → ``x``,
planes ``1…`` → ``y[p]``; ``n_channels = n_planes − 1`` (cite
``0x101ebff8``). Host ``curve_knots_from_plane_doubles``.

``ANE_CURVE_ROWS_FROM_DOUBLES_PORTED = True``.

Neighbor merge ``0x102a82a0`` + full build orchestration still open →
``ANE_ORDER_PORTED = False``.

``NoiseMethods::getNoiseTable`` @ ``0x10112980``
-----------------------------------------------
* String ``0x105879f4`` / ``noiseMethods.cpp`` ``0x10587994``.
* Looks up capability name ``"aneOrder"`` ``0x1057a024``, QI, then
  Cap ``getResults`` @ ``0x10112aab``.
* Also references ``"noiseTable"`` ``0x105740d0`` via Cap map
  ``0x10020a40``.
* **Sole CnPremium mid-aim caller** @ ``0x10056863`` (after dmin
  ``find``). On success reads returned object:

  | off       | role                            | cite           |
  |-----------|---------------------------------|----------------|
  | ``+0x44`` | ``n`` (table length per plane)  | ``0x10056990`` |
  | ``+0x48`` | advance / plane count           | ``0x10056993`` |
  | ``+0x4c`` | ``float*`` dens base            | ``0x10056996`` |

  Per channel ``i∈{0,1,2}`` @ ``0x100569a1…``: clamp dmin[i] into
  ``[0,n)``, ``dens_i = ftol2(table[idx] * blackNoiseSigmaMult)``,
  advance ``table += n`` while ``i+1 < +0x48``.

Results object ctor / alloc
---------------------------
* Ctor ``0x10195070`` (``ret 0xc``): stores arg1→``+0x44``, arg2→``+0x48``,
  ``+0x4c=0``, then ``0x102560a0``.
* Alloc ``0x102560a0``: ``nbytes = n * n_channels * 4``; on success
  ``+0x4c = ptr``, re-stores ``+0x44/+0x48`` (``0x102561f2``).
* getResults ctor args (@ ``0x101ebff8…``): ``+0x44 ← Impl+0xf8`` (n),
  ``+0x48 ← curve_inner+0x14 − 1`` (n_channels).

``getResults`` dens fill @ ``0x101ec10a…`` (PORTED)
--------------------------------------------------
When Impl ``+0x180`` is null, builds a results object and fills
``+0x4c`` from the curve container copied out of Impl ``+0xc0``
(``0x1027e840`` → wrapper ``ebp-0x44`` / inner ``+0x18`` = row ptrs,
``+0x10`` = n_segs).

Per plane ``p`` (``p < +0x48``), continuous dens pointer (not reset):

1. ``Yp ← rows[0].y[p]`` (``float`` at row ``+4+p*4``); ``i=0``;
   ``x_prev=0``.
2. For each segment ``seg``: loop head ``fstp Yp`` from FPU (after the
   first segment, ``Yp`` becomes previous ``y_k``).
3. ``x_k = rows[seg].x`` (``+0``); ``y_k = rows[seg].y[p]``.
4. ``dx = x_k − x_prev``. If ``dx ≤ FLT_EPSILON`` @ ``0x1059b344``
   (≈ ``1.192e-7``): skip fill; ``x_prev = x_k``; ``Yp ← y_k``.
5. Else ``slope = (y_k − Yp) / dx``; ``running = Yp``; while
   ``float(i) ≤ x_k`` (MSVC ``test ah,0x41; jp`` exits only when
   ``i > x_k``): ``running += slope``; store; ``i++``. Note: **no**
   ``i < n`` guard — when ``x_k ≥ n`` the write can bleed one sample
   into the next plane's slot (DLL behaviour; Unicorn-golden).
6. After segments: pad with final ``Yp`` while ``i < n``.

``ANE_GET_RESULTS_FILL_PORTED = True``. Neighbor merge + full analyze
orchestration still open → ``ANE_ORDER_PORTED = False``.

OrderOrientation (separate)
---------------------------
* Cap ``0x101218c0`` / Impl ``0x102101d0`` — from ``analyzeAttributes``
  ``0x100fb576``, **not** AneOrder dens.

Flags
-----
* ``ANE_NOISE_TABLE_LAYOUT_PORTED = True`` — host ``NoiseTable`` layout +
  alloc size + plane view for ``ane_dens_contrib``.
* ``ANE_GET_RESULTS_FILL_PORTED = True`` — dens fill from cited curve rows.
* ``ANE_ANALYZE_BIN_INDEX_PORTED = True`` — hist bin/slot leaf (Unicorn).
* ``ANE_ANALYZE_HIST_ACCUM_PORTED = True`` — dens-hist ``inc`` leaf (Unicorn).
* ``ANE_ANALYZE_FINALIZE_KNOT_PORTED = True`` — hist→knot ``0x102a7a30``.
* ``ANE_ANALYZE_FINALIZE_ADJUST_PORTED = True`` — adjust ``0x102a78c0``.
* ``ANE_CURVE_ROWS_FROM_DOUBLES_PORTED = True`` — ``0x1027e840`` pack.
* ``ANE_ORDER_PORTED = False`` — ``0x102a82a0`` merge + full build open.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import MutableSequence, Sequence

import numpy as np

ANE_ORDER_PORTED = False
ANE_NOISE_TABLE_LAYOUT_PORTED = True
ANE_GET_RESULTS_FILL_PORTED = True
ANE_ANALYZE_BIN_INDEX_PORTED = True
ANE_ANALYZE_HIST_ACCUM_PORTED = True
ANE_ANALYZE_FINALIZE_KNOT_PORTED = True
ANE_ANALYZE_FINALIZE_ADJUST_PORTED = True
ANE_CURVE_ROWS_FROM_DOUBLES_PORTED = True

PATH_ANALYZE_ANE_ORDER = 0x100FAD90
ANE_ORDER_CAP_ANALYZE = 0x10110540
ANE_ORDER_IMPL_ANALYZE = 0x101ED3A0
ANE_ORDER_CAP_GET_RESULTS = 0x10110830
ANE_ORDER_IMPL_GET_RESULTS = 0x101EBE90
ANE_ORDER_GET_RESULTS_FILL = 0x101EC10A
ANE_ANALYZE_BUILD_CURVES = 0x1027E9D0  # Ane.cpp from Impl+0xc0
ANE_ANALYZE_BIN_INDEX = 0x102A8555  # leaf inside 0x102a84d0 accumulate
ANE_ANALYZE_BIN_INDEX_END = 0x102A857C  # before call 0x101ed810
ANE_ANALYZE_HIST_ACCUM = 0x104F56E0  # dens-hist bin + inc
ANE_ANALYZE_HIST_ACCUM_END = 0x104F570B  # after ret 4 prologue target
ANE_ANALYZE_FINALIZE = 0x102A8770
ANE_ANALYZE_FINALIZE_KNOT = 0x102A7A30  # hist counts → knot double
ANE_ANALYZE_FINALIZE_ADJUST = 0x102A78C0  # optional knot adjust
ANE_ANALYZE_NEIGHBOR_MERGE = 0x102A82A0  # open (COM smart-ptr hist merge)
ANE_CURVE_ROWS_FROM_DOUBLES = 0x1027E840  # +0x78 doubles → float rows
ORDER_ORIENTATION_CAP_ANALYZE = 0x101218C0

# 0x102a78c0 piecewise tables (cite rdata @ listed VAs)
_ANE_78C0_THRESH = (0.03, 0.06, 0.125, 0.25, 0.5, 1.0, 10.0)
_ANE_78C0_A8760 = (-1.523, -1.222, -0.903, -0.602, -0.301, 0.0, 1.0)
_ANE_78C0_A8730 = (3.322, 3.137, 3.322, 3.322, 3.322, 1.0, -1.523)
_ANE_78C0_A8700 = (-0.012, -0.131, -0.034, -0.001, 0.012, 0.018, 3.322)
_ANE_78C0_A86C8 = (0.212, 0.2, 0.069, 0.035, 0.034, 0.046, 0.064)
_ANE_78C0_A8698 = (0.005, 0.111, 0.076, 0.061, 0.034, 0.009, 0.212)
_ANE_78C0_A8660 = (0.321, 0.326, 0.437, 0.513, 0.574, 0.608, 0.617)
_ANE_78C0_LO_A = 0.212  # st0 when ecx==0
_ANE_78C0_LO_B = 0.321
_ANE_78C0_HI_A = 0.064  # st0 when ecx==6
_ANE_78C0_HI_B = 0.617
_ANE_78C0_POS_STANDIN = 1000.0  # @ 0x105a3c18 when lim ≤ 0

# Ane object fields used by bin-index leaf (cite 0x102a854e…)
ANE_OBJ_PIXEL_OFFSET_OFF = 0x34
ANE_OBJ_BIN_DIVISOR_OFF = 0x3C
ANE_OBJ_PLANE_STRIDE_OFF = 0x40
ANE_OBJ_BIN_MAX_OFF = 0x44

# Dens-hist object fields used by 0x104f56e0 (cite leaf)
ANE_HIST_N_OFF = 0x0C
ANE_HIST_OFFSET_OFF = 0x10  # double
ANE_HIST_DIVISOR_OFF = 0x28  # double
ANE_HIST_BINS_OFF = 0x38  # int*

NOISE_METHODS_GET_NOISE_TABLE = 0x10112980
CN_PREMIUM_GET_NOISE_TABLE_CALL = 0x10056863
STR_ANE_ORDER = 0x1057A024
STR_GET_NOISE_TABLE = 0x105879F4
STR_NOISE_TABLE = 0x105740D0
STR_EXPORT_NOISE = 0x105879C4

NOISE_TABLE_CTOR = 0x10195070
NOISE_TABLE_ALLOC = 0x102560A0
NOISE_TABLE_N_OFF = 0x44
NOISE_TABLE_N_CHANNELS_OFF = 0x48
NOISE_TABLE_DENS_OFF = 0x4C

# FLT_EPSILON at 0x1059b344 (fcomp gate on dx)
ANE_FILL_FLT_EPSILON = 1.1920928955078125e-07


def noise_table_alloc_nbytes(n: int, n_channels: int) -> int:
    """``0x102560a0`` — ``n * n_channels * sizeof(float)``."""
    if n < 0 or n_channels < 0:
        raise ValueError("n and n_channels must be ≥ 0")
    return int(n) * int(n_channels) * 4


def ane_bin_index(pixel: int, offset: int, divisor: int, max_bin: int) -> int:
    """Analyze hist bin @ ``0x102a8555…`` — ``idiv`` + clamp (Unicorn-golden).

    ``bin = trunc_toward_0((pixel - offset) / divisor)`` then
    ``clamp(bin, 0, max_bin)``. ``divisor`` must be non-zero (DLL ``idiv``).
    """
    d = int(divisor)
    if d == 0:
        raise ValueError("divisor must be non-zero (DLL idiv)")
    # MSVC idiv truncates toward 0; Python int(a/b) on floats does too.
    q = int((int(pixel) - int(offset)) / d)
    if q < 0:
        return 0
    hi = int(max_bin)
    return hi if q > hi else q


def ane_hist_slot(
    pixel: int,
    offset: int,
    divisor: int,
    max_bin: int,
    plane_stride: int,
    plane: int,
) -> int:
    """``slot = plane_stride * plane + bin`` after ``ane_bin_index``."""
    return int(plane_stride) * int(plane) + ane_bin_index(
        pixel, offset, divisor, max_bin
    )



def ane_dens_hist_bin(value: int, offset: float, divisor: float, n: int) -> int:
    """Dens-hist bin @ ``0x104f56e0…`` before ``inc`` (Unicorn-golden).

    ``bin = ftol2((value − offset) / divisor)`` then clamp to ``[0, n-1]``.
    ``n`` is ``[hist+0xc]``; ``divisor`` must be non-zero.
    """
    d = float(divisor)
    if d == 0.0:
        raise ValueError("divisor must be non-zero")
    # Same trunc-toward-0 leaf as ``0x104ffe44`` / ``pakon_shasta.ftol2_chop``.
    q = int(math.trunc((float(int(value)) - float(offset)) / d))
    if q < 0:
        return 0
    hi = int(n) - 1
    if hi < 0:
        return 0
    return hi if q > hi else q


def ane_dens_hist_accum(
    bins: MutableSequence[int],
    value: int,
    *,
    offset: float,
    divisor: float,
    n: int | None = None,
) -> int:
    """Dens-hist ``inc`` leaf @ ``0x104f56e0`` (Unicorn-golden).

    Increments ``bins[bin]`` and returns the bin index. When ``n`` is
    omitted, uses ``len(bins)`` as ``[hist+0xc]``.
    """
    nn = int(n) if n is not None else len(bins)
    if nn <= 0:
        raise ValueError("n must be > 0")
    if len(bins) < nn:
        raise ValueError(f"bins length {len(bins)} < n={nn}")
    b = ane_dens_hist_bin(value, offset, divisor, nn)
    bins[b] = int(bins[b]) + 1
    return b


def _msvc_sar_half(x: int) -> int:
    """``cdq; sub eax,edx; sar eax,1`` for signed ``x``."""
    x = int(x)
    return (x - (-1 if x < 0 else 0)) >> 1


def _ane_side_accum(
    counts: Sequence[int], mid: int, direction: int
) -> tuple[float, float, float]:
    """One side of ``0x102a7a30`` mass / moment accum (stop after 2 zeros)."""
    n = len(counts)
    sum_c = sum_cd = sum_cd2 = 0.0
    zeros = 0
    indices = range(mid + 1, n) if direction > 0 else range(mid - 1, -1, -1)
    for i in indices:
        c = int(counts[i])
        if c == 0:
            zeros += 1
            if zeros >= 2:
                break
        d = float(i - mid)
        sum_c += float(c)
        sum_cd += float(c) * d
        sum_cd2 += float(c) * d * d
    return sum_c, sum_cd, sum_cd2


def _ane_window_rms(
    counts: Sequence[int],
    mid: int,
    mid_half: float,
    lo: float,
    hi: float,
    direction: int,
) -> float:
    """Windowed core RMS inside finalize knot leaf (cite ``0x102a7e4e…``)."""
    n = len(counts)
    sc = float(mid_half)
    scd2 = 0.0
    zeros = 0
    indices = range(mid + 1, n) if direction > 0 else range(mid - 1, -1, -1)
    for i in indices:
        d = float(i - mid)
        if direction > 0:
            if d > hi:
                continue
        elif d < lo:
            continue
        c = int(counts[i])
        if c == 0:
            zeros += 1
            if zeros >= 2:
                break
        sc += float(c)
        scd2 += float(c) * d * d
    if sc == 0.0:
        return 0.0
    return math.sqrt(scd2 / sc)


def ane_finalize_knot_7a30(
    counts: Sequence[int],
    scale: float = 1.0,
    min_count: int = 0,
) -> float:
    """Finalize hist→knot double @ ``0x102a7a30`` (Unicorn-golden).

    ``scale`` is the ``double`` at finalize ``[ebp+0xc]`` (from Ane
    ``+0x10`` / ``+0x18``). ``min_count`` is ``[ebp+0x14]`` (usually 0).
    """
    c = [int(x) for x in counts]
    n = len(c)
    if n <= 0 or sum(c) < int(min_count):
        return 0.0
    mid = _msvc_sar_half(n)
    mh = float(_msvc_sar_half(c[mid])) if 0 <= mid < n else 0.0
    hc, hcd, hcd2 = _ane_side_accum(c, mid, +1)
    lc, lcd, lcd2 = _ane_side_accum(c, mid, -1)
    c_h = mh + hc
    c_l = mh + lc
    rms_high = math.sqrt(hcd2 / c_h) if c_h else 0.0
    rms_low = math.sqrt(lcd2 / c_l) if c_l else 0.0
    sum_c = c_h + c_l
    mean = ((hcd + lcd) / sum_c) if sum_c else 0.0
    r_pos = _ane_window_rms(c, mid, mh, 0.0, float(scale) * rms_high, +1)
    r_neg = _ane_window_rms(
        c, mid, mh, -float(scale) * rms_low, 0.0, -1
    )
    if mean < 0.0:
        # Path ``0x102a823f``: t = (mean + r_neg) / (2·r_neg)
        if r_neg == 0.0:
            t = 1.0
        else:
            t = (mean + r_neg) / (2.0 * r_neg)
            t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
        return (1.0 - t) * r_pos + t * r_neg
    # Path ``0x102a81db``: t = (r_pos − mean) / (2·r_pos)
    if r_pos == 0.0:
        t = 1.0
    else:
        t = (r_pos - mean) / (2.0 * r_pos)
        t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return (1.0 - t) * r_neg + t * r_pos


def ane_finalize_adjust_78c0(value: float, limit: float) -> float:
    """Optional finalize adjust @ ``0x102a78c0`` (Unicorn-golden).

    ``value`` = current knot double; ``limit`` = Ane ``+0x20`` (second
    finalize arg path). Returns 0 when ``value < a`` for the band.
    """
    v = float(value)
    y = float(limit)
    if y <= 0.0:
        y = _ANE_78C0_POS_STANDIN
    ecx = 6
    while ecx > 0 and y < _ANE_78C0_THRESH[ecx]:
        ecx -= 1
    if ecx == 0:
        a, b = _ANE_78C0_LO_A, _ANE_78C0_LO_B
    elif ecx == 6:
        a, b = _ANE_78C0_HI_A, _ANE_78C0_HI_B
    else:
        lg = math.log10(y)
        t = (lg - _ANE_78C0_A8760[ecx]) * _ANE_78C0_A8730[ecx]
        a = t * _ANE_78C0_A8700[ecx] + _ANE_78C0_A86C8[ecx]
        b = t * _ANE_78C0_A8698[ecx] + _ANE_78C0_A8660[ecx]
    if v < a:
        return 0.0
    return (v - a) / b


def curve_knots_from_plane_doubles(
    plane_doubles: Sequence[Sequence[float]],
) -> list[tuple[float, ...]]:
    """``0x1027e840`` — plane doubles → getResults knot rows.

    ``plane_doubles[0][i]`` → knot ``x``; ``plane_doubles[1+][i]`` →
    ``y[p]``. All planes must share the same length (n_segs).
    """
    if not plane_doubles:
        raise ValueError("plane_doubles must be non-empty")
    n_planes = len(plane_doubles)
    n_segs = len(plane_doubles[0])
    for p, row in enumerate(plane_doubles):
        if len(row) != n_segs:
            raise ValueError(
                f"plane {p} length {len(row)} != plane0 length {n_segs}"
            )
    knots: list[tuple[float, ...]] = []
    for i in range(n_segs):
        knots.append(tuple(float(plane_doubles[p][i]) for p in range(n_planes)))
    return knots


def get_results_fill_dens(
    knots: Sequence[Sequence[float]],
    n: int,
    n_channels: int = 1,
    *,
    eps: float = ANE_FILL_FLT_EPSILON,
) -> np.ndarray:
    """Impl ``getResults`` dens fill @ ``0x101ec10a…`` (Unicorn-golden).

    ``knots[seg][0]`` = ``x``; ``knots[seg][1+plane]`` = ``y[plane]``.
    Returns ``float32`` shape ``(n_channels, n)`` matching the DLL's
    continuous dens pointer (plane0 may bleed one sample into plane1
    when a knot ``x ≥ n``).
    """
    if n < 0 or n_channels < 0:
        raise ValueError("n and n_channels must be ≥ 0")
    if not knots:
        raise ValueError("knots must be non-empty (row0 supplies Yp)")
    # Extra room for DLL bleed when x_k >= n on a non-final plane.
    flat = np.zeros(n * n_channels + n + 8, dtype=np.float32)
    esi = 0
    for plane in range(n_channels):
        if len(knots[0]) < 2 + plane:
            raise ValueError(f"row0 missing y for plane {plane}")
        yp = float(knots[0][1 + plane])
        x_prev = 0.0
        i = 0
        for vals in knots:
            if len(vals) < 2 + plane:
                raise ValueError("knot row too short for plane")
            x_k = float(vals[0])
            y_k = float(vals[1 + plane])
            dx = x_k - x_prev
            if dx > eps:
                slope = (y_k - yp) / dx
                running = yp
                # Continue while i <= x_k (exit only when i > x_k).
                while not (float(i) > x_k):
                    running = running + slope
                    flat[esi] = running
                    esi += 1
                    i += 1
            x_prev = x_k
            yp = y_k
        while i < n:
            flat[esi] = yp
            esi += 1
            i += 1
    return flat[: n * n_channels].reshape(n_channels, n)


def noise_table_from_knots(
    knots: Sequence[Sequence[float]],
    n: int,
    n_channels: int = 1,
) -> "NoiseTable":
    """Fill dens from curve knots → ``NoiseTable`` for mid-aim."""
    dens = get_results_fill_dens(knots, n, n_channels)
    return NoiseTable(n=n, n_channels=n_channels, dens=dens)


@dataclass
class NoiseTable:
    """Host view of getResults / getNoiseTable dens object (+0x44/+0x48/+0x4c)."""

    n: int
    n_channels: int
    dens: np.ndarray  # float32, shape (n_channels, n) or flat n*n_channels

    def __post_init__(self) -> None:
        arr = np.asarray(self.dens, dtype=np.float32)
        need = self.n * self.n_channels
        if arr.size != need:
            raise ValueError(
                f"dens size {arr.size} != n*n_channels ({self.n}*{self.n_channels})"
            )
        if arr.ndim == 1:
            self.dens = arr.reshape(self.n_channels, self.n)
        elif arr.ndim == 2:
            if arr.shape != (self.n_channels, self.n):
                raise ValueError(
                    f"dens shape {arr.shape} != ({self.n_channels}, {self.n})"
                )
            self.dens = arr
        else:
            raise ValueError("dens must be 1-D or 2-D")

    @classmethod
    def zeros(cls, n: int, n_channels: int = 1) -> "NoiseTable":
        return cls(n=n, n_channels=n_channels, dens=np.zeros(n * n_channels, dtype=np.float32))

    def planes_for_mid_aim(self) -> np.ndarray:
        """Array accepted by ``pakon_shasta.ane_dens_contrib`` / mid-aim."""
        if self.n_channels == 1:
            return self.dens[0]
        return self.dens


def main() -> None:
    print("AneOrder / NoiseMethods dens layout (base 0x10000000)")
    print(f"  getNoiseTable     {NOISE_METHODS_GET_NOISE_TABLE:#010x}")
    print(f"  CnPremium call    {CN_PREMIUM_GET_NOISE_TABLE_CALL:#010x}")
    print(f"  Cap getResults    {ANE_ORDER_CAP_GET_RESULTS:#010x}")
    print(f"  Impl getResults   {ANE_ORDER_IMPL_GET_RESULTS:#010x}")
    print(f"  dens fill         {ANE_ORDER_GET_RESULTS_FILL:#010x}")
    print(f"  analyze build     {ANE_ANALYZE_BUILD_CURVES:#010x}")
    print(f"  bin-index leaf    {ANE_ANALYZE_BIN_INDEX:#010x}")
    print(f"  dens-hist accum   {ANE_ANALYZE_HIST_ACCUM:#010x}")
    print(f"  finalize          {ANE_ANALYZE_FINALIZE:#010x}")
    print(f"  finalize knot     {ANE_ANALYZE_FINALIZE_KNOT:#010x}")
    print(f"  finalize adjust   {ANE_ANALYZE_FINALIZE_ADJUST:#010x}")
    print(f"  neighbor merge    {ANE_ANALYZE_NEIGHBOR_MERGE:#010x} (open)")
    print(f"  curve rows        {ANE_CURVE_ROWS_FROM_DOUBLES:#010x}")
    print(f"  ctor/alloc        {NOISE_TABLE_CTOR:#010x} / {NOISE_TABLE_ALLOC:#010x}")
    print(
        f"  LAYOUT_PORTED={ANE_NOISE_TABLE_LAYOUT_PORTED} "
        f"FILL_PORTED={ANE_GET_RESULTS_FILL_PORTED} "
        f"BIN_INDEX_PORTED={ANE_ANALYZE_BIN_INDEX_PORTED} "
        f"HIST_ACCUM_PORTED={ANE_ANALYZE_HIST_ACCUM_PORTED} "
        f"FINALIZE_KNOT_PORTED={ANE_ANALYZE_FINALIZE_KNOT_PORTED} "
        f"FINALIZE_ADJUST_PORTED={ANE_ANALYZE_FINALIZE_ADJUST_PORTED} "
        f"CURVE_ROWS_PORTED={ANE_CURVE_ROWS_FROM_DOUBLES_PORTED} "
        f"ANE_ORDER_PORTED={ANE_ORDER_PORTED}"
    )
    nt = NoiseTable.zeros(64, 1)
    print(f"  sample alloc nbytes={noise_table_alloc_nbytes(nt.n, nt.n_channels)}")
    sample = get_results_fill_dens([(5.0, 2.0), (15.0, 12.0)], 20, 1)
    print(f"  sample fill[0,:8]={sample[0, :8]}")
    print(f"  sample bin slot={ane_hist_slot(100, 50, 2, 100, 128, 1)}")
    hist = [0] * 16
    b = ane_dens_hist_accum(hist, 25, offset=5.0, divisor=2.0)
    print(f"  sample dens-hist bin={b} counts={hist[b]}")
    k = ane_finalize_knot_7a30([1, 2, 3, 4, 5, 6, 5, 4, 3, 2, 1], 1.0)
    print(f"  sample finalize knot={k}")
    rows = curve_knots_from_plane_doubles([[0.0, 10.0], [1.0, 2.0]])
    print(f"  sample curve rows={rows}")


if __name__ == "__main__":
    main()
