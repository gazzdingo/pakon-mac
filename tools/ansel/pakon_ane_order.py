#!/usr/bin/env python3
"""AneOrder / NoiseMethods — dens table layout + getResults fill.

PakonIMAu.dll base ``0x10000000``. Catalog + host layout for the float
table CnPremium indexes at mid-aim. ``getResults`` dens **fill** from
Impl curve rows is ported; analyze **bin-index** / dens-hist **accum**
ported; neighbor-hist merge ``0x102a82a0`` + finalize knot
``0x102a7a30`` + adjust ``0x102a78c0`` + curve-row pack ``0x1027e840``
ported; sample/residual dens-hist accumulate ``0x102a84d0`` + build
orch ``0x1027e9d0`` (shipped ``useAvg=0`` path) ported →
``ANE_ORDER_PORTED = True``. ``useAvg≠0`` color-correlation second
pass (``0x102a8950`` / ``0x102a8600``) ported →
``ANE_ANALYZE_CORR_MASK_PORTED`` / ``ANE_ANALYZE_ACCUM_8600_PORTED``.

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
  4. ``0x1027e9d0`` drives hist accumulate ``0x102a84d0`` then
     finalize ``0x102a8770``. When AneParams ``useAvg``
     (Ane ``+0x29`` = params ``+0x21``) is set, a second pass runs
     ``color_correlation_mask`` ``0x102a8950`` + masked accum
     ``0x102a8600`` — ported; shipped CN dpi keeps ``useAvg=0``.

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

Neighbor-hist merge ``0x102a82a0`` (PORTED + Unicorn)
----------------------------------------------------
Called from finalize ``0x102a8770`` per ``(plane, bin)``:

* ``plane_start = [obj+0x40] * plane``; ``plane_end = (plane+1)*stride − 1``
* ``center = plane_start + bin``; clone dens-hist at ``[obj+0xa4][center]``
* Expand ring: while ``ring < [obj+0x54]`` **or** ``sum(counts) < [obj+0x5c]``,
  add left neighbor bins (if ``left ≥ plane_start``) and/or right
  (if ``right ≤ plane_end``); then ``left−1``, ``right+1``, ``ring+1``.
* Stop early when both neighbors fall outside the plane slot range.
* Returns the merged dens-hist (COM smart-ptr); sources unchanged.

``ANE_ANALYZE_NEIGHBOR_MERGE_PORTED = True``.

Finalize ``0x102a8770`` → knot doubles (leaves PORTED)
-----------------------------------------------------
Per ``(plane, bin)``: neighbor merge ``0x102a82a0`` then knot leaf
``0x102a7a30`` (PORTED + Unicorn) writes a ``double`` into the
``+0x78`` plane vectors. Optional adjust ``0x102a78c0`` (PORTED)
when finalize flag set and ``[obj+0x2c]==0``. Scale pass ``0x104ee9c0``
multiplies plane vectors when arg ≠ 1. Host compose
``ane_finalize_plane_doubles_from_hists`` wires merge→knot→adjust.

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

Accumulate sample/residual ``0x102a84d0`` (PORTED + Unicorn)
----------------------------------------------------------
Per plane / row / col (dims from image ``0x104d4520`` / ``4530`` /
``4540``; plane rows via ``0x101ed810``):

* ``sample`` = int16; ``bin`` / ``slot`` via bin-index leaf
  (``slot = stride*plane + bin``).
* ``residual`` = int16 → dens-hist ``inc`` at map ``[obj+0xa4][slot]``
  (``0x104eab20`` → ``0x104ea370`` → ``0x104f56e0``).
* Also ``inc`` sample into plane hist map ``[obj+0xa8][plane]``
  (ImgHistogram; not on the dens→``getResults`` path).

Residual dens-hist range from Ane init ``0x1027e6bc…``: ``min=−resMax``,
``max=resMax``, ``n=2·resMax+1`` → host ``offset=−resMax``,
``divisor=1`` (cite map ctor args into ``0x104eab80``).

``ANE_ANALYZE_ACCUM_84D0_PORTED = True`` (leaf-compose of
Unicorn-golden ``ane_bin_index`` + ``ane_dens_hist_accum``; full-loop
Unicorn harness for ``0x102a84d0`` still open).

Build orch ``0x1027e9d0`` (PORTED — shipped ``useAvg=0``)
-------------------------------------------------------
1. Require equal non-empty sample/residual vectors (else throw
   ``"Empty or mismatched sample/residual vectors."`` @ ``0x105a5f98``).
2. Clear dens-hists ``0x1027e3a0``; zero ``[obj+0xbc]``.
3. For each pair: wrap (``0x1014cc20``) → accumulate ``0x102a84d0`` →
   destroy wrappers; ``inc [obj+0xbc]``.
  4. ``useAvg`` (Ane ``+0x29``): shipped ``ane-CN-Fps.dpi`` /
   ``ane-default.dpi`` set ``useAvg=0`` → finalize
   ``0x102a8770(scaleFactor @ +0x18, useMasking @ +0x28,
   tau @ +0x20)``. Knot scale = ``alpha`` @ ``+0x10``.
5. ``useAvg≠0`` (PORTED): finalize once (``do_adjust=1``; adjust
   reads Ane ``+0x20``), clear hists ``0x1027e3a0``, per pair
   ``color_correlation_mask`` ``0x102a8950`` then masked accum
   ``0x102a8600``, then final ``0x102a8770`` with normal masking.

Host ``ane_build_noise_table_e9d0`` composes accumulate → finalize →
curve rows → ``getResults`` fill; ``use_avg=True`` when both
``ANE_ANALYZE_CORR_MASK_PORTED`` and ``ANE_ANALYZE_ACCUM_8600_PORTED``.

``ANE_ORDER_PORTED = True``. Live Laplacian ``collectData`` pixel
leaf ``0x1027fc80`` and box ``0x102804e0`` are ported
(``ANE_COLLECT_FC80_PORTED`` / ``ANE_COLLECT_804E0_PORTED``);
collectData host orch ``0x101ee590`` ported
(``ANE_COLLECT_DATA_PORTED`` / ``ANE_COLLECT_QI_INSERT_PORTED`` /
``ANE_COLLECT_CONVERT_PORTED``).
``SHASTA_ANALYZE_PORTED`` wires fc80 dens into Preference mid-aims.

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

``ANE_GET_RESULTS_FILL_PORTED = True``.

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
* ``ANE_ANALYZE_NEIGHBOR_MERGE_PORTED = True`` — ``0x102a82a0`` merge.
* ``ANE_CURVE_ROWS_FROM_DOUBLES_PORTED = True`` — ``0x1027e840`` pack.
* ``ANE_ANALYZE_ACCUM_84D0_PORTED = True`` — sample/residual dens-hist
  loop as leaf-compose of golden bin-index + dens-hist ``inc`` (full
  Unicorn ``0x102a84d0`` harness open).
* ``ANE_ANALYZE_CORR_MASK_PORTED = True`` — ``0x102a8950`` mask.
* ``ANE_ANALYZE_ACCUM_8600_PORTED = True`` — ``0x102a8600`` masked dens.
* ``ANE_ORDER_PORTED = True`` — ``0x1027e9d0`` orch (``useAvg=0`` and
  ``useAvg≠0`` when both correlation flags True).
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import MutableSequence, Sequence

import numpy as np

ANE_ORDER_PORTED = True
ANE_NOISE_TABLE_LAYOUT_PORTED = True
ANE_GET_RESULTS_FILL_PORTED = True
ANE_ANALYZE_BIN_INDEX_PORTED = True
ANE_ANALYZE_HIST_ACCUM_PORTED = True
ANE_ANALYZE_FINALIZE_KNOT_PORTED = True
ANE_ANALYZE_FINALIZE_ADJUST_PORTED = True
ANE_ANALYZE_NEIGHBOR_MERGE_PORTED = True
ANE_CURVE_ROWS_FROM_DOUBLES_PORTED = True
ANE_ANALYZE_ACCUM_84D0_PORTED = True
ANE_ANALYZE_CORR_MASK_PORTED = True
ANE_ANALYZE_ACCUM_8600_PORTED = True

PATH_ANALYZE_ANE_ORDER = 0x100FAD90
ANE_ORDER_CAP_ANALYZE = 0x10110540
ANE_ORDER_IMPL_ANALYZE = 0x101ED3A0
ANE_ORDER_CAP_GET_RESULTS = 0x10110830
ANE_ORDER_IMPL_GET_RESULTS = 0x101EBE90
ANE_ORDER_GET_RESULTS_FILL = 0x101EC10A
ANE_ANALYZE_BUILD_CURVES = 0x1027E9D0  # Ane.cpp from Impl+0xc0
ANE_ANALYZE_BUILD_CURVES_END = 0x1027EC4A  # ret 8 (useAvg=0 exit)
ANE_ANALYZE_ACCUM_84D0 = 0x102A84D0  # sample/residual dens-hist loop
ANE_ANALYZE_ACCUM_84D0_END = 0x102A85F4  # ret 8
ANE_ANALYZE_ACCUM_8600 = 0x102A8600  # masked accum (useAvg≠0)
ANE_ANALYZE_ACCUM_8600_END = 0x102A8763  # ret 0xc
ANE_ANALYZE_CORR_MASK = 0x102A8950  # color_correlation_mask
ANE_ANALYZE_CORR_MASK_END = 0x102A8C41  # ret 0xc
ANE_ANALYZE_BIN_INDEX = 0x102A8555  # leaf inside 0x102a84d0 accumulate
ANE_ANALYZE_BIN_INDEX_END = 0x102A857C  # before call 0x101ed810
ANE_ANALYZE_HIST_ACCUM = 0x104F56E0  # dens-hist bin + inc
ANE_ANALYZE_HIST_ACCUM_END = 0x104F570B  # after ret 4 prologue target
ANE_ANALYZE_FINALIZE = 0x102A8770
ANE_ANALYZE_FINALIZE_KNOT = 0x102A7A30  # hist counts → knot double
ANE_ANALYZE_FINALIZE_ADJUST = 0x102A78C0  # optional knot adjust
ANE_ANALYZE_NEIGHBOR_MERGE = 0x102A82A0  # COM smart-ptr hist merge
ANE_ANALYZE_NEIGHBOR_MERGE_END = 0x102A83DA  # ret 0x14
ANE_CURVE_ROWS_FROM_DOUBLES = 0x1027E840  # +0x78 doubles → float rows
ORDER_ORIENTATION_CAP_ANALYZE = 0x101218C0

# AneParams @ Ane+8 (ctor 0x1027e0e0 / dpi copy 0x1027e2e0)
ANE_OBJ_PARAMS_OFF = 0x8
ANE_OBJ_ALPHA_OFF = 0x10  # params+0x08; finalize knot scale
ANE_OBJ_SCALE_FACTOR_OFF = 0x18  # params+0x10; finalize scale arg
ANE_OBJ_TAU_OFF = 0x20  # params+0x18; finalize adjust limit
ANE_OBJ_USE_MASKING_OFF = 0x28  # params+0x20; finalize do_adjust
ANE_OBJ_USE_AVG_OFF = 0x29  # params+0x21; e9d0 correlation branch
ANE_OBJ_RES_MAX_OFF = 0x4C  # params+0x44; residual dens-hist bound

# Ane object fields used by neighbor merge / finalize (cite 0x102a82cf…)
ANE_OBJ_MERGE_MAX_RADIUS_OFF = 0x54
ANE_OBJ_N_PLANES_OFF = 0x58
ANE_OBJ_MERGE_MIN_COUNT_OFF = 0x5C
ANE_OBJ_HIST_MAP_OFF = 0xA4
ANE_OBJ_KNOT_SCALE_OFF = 0x10
ANE_OBJ_ADJUST_LIMIT_OFF = 0x20
ANE_OBJ_ADJUST_SKIP_OFF = 0x2C  # nonzero → skip adjust pass

# Finalize scale-pass gate: |scale − 1| vs rdata @ 0x105a87f0
ANE_FINALIZE_SCALE_EPS = 1.1920928955078125e-07

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

# color_correlation_mask score scale (``fmul`` @ 0x102a8b98)
ANE_CORR_ONE_THIRD = struct.unpack("<d", bytes.fromhex("555555555555d53f"))[
    0
]  # PakonIMAu.dll @ 0x105943c0
ANE_OBJ_CORR_RATIO_OFF = 0x90  # filled-ratio double @ 0x102a8c34


def _ane_imul32(a: int, b: int) -> int:
    """MSVC ``imul`` dword product (trunc to signed 32) @ ``0x102a8b55``."""
    return ((int(a) * int(b)) + (1 << 31)) % (1 << 32) - (1 << 31)


def ane_corr_score_8950(
    res0: int,
    res1: int,
    res2: int,
    knot0: float,
    knot1: float,
    knot2: float,
) -> float:
    """Per-pixel correlation score inside ``0x102a8950`` (FPU @ ``0x102a8b6a…``).

    ``score = (1/3) * (r0·r1/(k1·k0) + r0·r2/(k2·k0) + r1·r2/(k2·k1))``
    with ``imul`` products then ``fild``. Requires MSVC 53-bit FPU PC for
    bit-exact float64 vs DLL (Unicorn golden sets ``FCW=0x027F``).
    """
    k0 = float(knot0)
    k1 = float(knot1)
    k2 = float(knot2)
    # IEEE div (Python raises on /0; numpy matches x87→inf/nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        t1 = float(
            np.float64(_ane_imul32(res0, res1))
            / (np.float64(k1) * np.float64(k0))
        )  # PakonIMAu.dll @ 0x102a8b6a
        t2 = float(
            np.float64(_ane_imul32(res0, res2))
            / (np.float64(k2) * np.float64(k0))
        )  # PakonIMAu.dll @ 0x102a8b78
        t3 = float(
            np.float64(_ane_imul32(res1, res2))
            / (np.float64(k2) * np.float64(k1))
        )  # PakonIMAu.dll @ 0x102a8b8a
        return float(
            np.float64(t1 + t2 + t3) * np.float64(ANE_CORR_ONE_THIRD)
        )  # PakonIMAu.dll @ 0x102a8b98


def ane_color_correlation_mask_8950(
    sample: Sequence[np.ndarray] | np.ndarray,
    residual: Sequence[np.ndarray] | np.ndarray,
    plane_doubles: Sequence[Sequence[float]],
    *,
    pixel_offset: int,
    bin_divisor: int,
    max_bin: int,
    tau: float,
) -> tuple[list[np.ndarray], float]:
    """``color_correlation_mask`` @ ``0x102a8950`` (Unicorn-golden).

    Requires ≥3 planes. For each pixel: bin sample RGB via
    ``ane_bin_index``, look up finalize knots ``plane_doubles[0..2]``,
    compute score; when ``fabs(score) ≤ tau`` (Ane ``+0x20``) set all
    three mask planes to 1. Returns ``(mask_planes uint8 HxW×3,
    filled_ratio)`` where ratio is matches / (h·w) → Ane ``+0x90``.
    """
    samp = _ane_planes_i16(sample)
    resid = _ane_planes_i16(residual)
    if len(samp) < 3 or len(resid) < 3:
        raise ValueError(
            "color_correlation_mask(): x must have 3 channels"  # cite 0x105a87f8
        )
    if len(plane_doubles) < 3:
        raise ValueError("plane_doubles needs ≥3 planes")
    h, w = samp[0].shape
    for p in range(3):
        if samp[p].shape != (h, w) or resid[p].shape != (h, w):
            raise ValueError("sample/residual planes must share HxW")
        if len(plane_doubles[p]) <= int(max_bin):
            raise ValueError(
                f"plane_doubles[{p}] length {len(plane_doubles[p])} "
                f"≤ max_bin={max_bin}"
            )
    masks = [
        np.zeros((h, w), dtype=np.uint8),
        np.zeros((h, w), dtype=np.uint8),
        np.zeros((h, w), dtype=np.uint8),
    ]
    matches = 0
    thr = float(tau)
    for y in range(h):
        for x in range(w):
            b0 = ane_bin_index(
                int(samp[0][y, x]), pixel_offset, bin_divisor, max_bin
            )  # PakonIMAu.dll @ 0x102a8a5f
            b1 = ane_bin_index(
                int(samp[1][y, x]), pixel_offset, bin_divisor, max_bin
            )  # PakonIMAu.dll @ 0x102a8a9d
            b2 = ane_bin_index(
                int(samp[2][y, x]), pixel_offset, bin_divisor, max_bin
            )  # PakonIMAu.dll @ 0x102a8adb
            k0 = float(plane_doubles[0][b0])  # PakonIMAu.dll @ 0x102a8b10
            k1 = float(plane_doubles[1][b1])  # PakonIMAu.dll @ 0x102a8b27
            k2 = float(plane_doubles[2][b2])  # PakonIMAu.dll @ 0x102a8b3e
            r0 = int(resid[0][y, x])  # PakonIMAu.dll @ 0x102a89fe
            r1 = int(resid[1][y, x])  # PakonIMAu.dll @ 0x102a8a1d
            r2 = int(resid[2][y, x])  # PakonIMAu.dll @ 0x102a8a3c
            score = ane_corr_score_8950(r0, r1, r2, k0, k1, k2)
            # fabs via fcom/fchs @ 0x102a8b9e…; fcomp tau @ 0x102a8bad
            if abs(score) <= thr:  # PakonIMAu.dll @ 0x102a8bad
                matches += 1  # PakonIMAu.dll @ 0x102a8bbe
                masks[0][y, x] = 1  # PakonIMAu.dll @ 0x102a8bd9
                masks[1][y, x] = 1  # PakonIMAu.dll @ 0x102a8bf3
                masks[2][y, x] = 1  # PakonIMAu.dll @ 0x102a8c0a
    total = h * w  # PakonIMAu.dll @ 0x102a89e4 (Σ width)
    ratio = (float(matches) / float(total)) if total else float("nan")
    # PakonIMAu.dll @ 0x102a8c28 → +0x90
    return masks, ratio


def ane_accumulate_masked_8600(
    plane_dens_hists: Sequence[Sequence[MutableSequence[int]]],
    sample: Sequence[np.ndarray] | np.ndarray,
    residual: Sequence[np.ndarray] | np.ndarray,
    mask: Sequence[np.ndarray],
    *,
    pixel_offset: int,
    bin_divisor: int,
    max_bin: int,
    hist_offset: float,
    hist_divisor: float,
) -> None:
    """Masked dens-hist accumulate @ ``0x102a8600`` (Unicorn-golden).

    Per plane/row/col: when ``mask[plane][y,x] ≠ 0``, bin sample and
    ``inc`` residual dens-hist at ``+0xa4`` slot (same as ``84d0``).
    Plane ImgHistogram ``+0xa8`` / ``+0xb0`` side paths omitted (not on
    dens→``getResults`` path).
    """
    samp = _ane_planes_i16(sample)
    resid = _ane_planes_i16(residual)
    n_planes = len(samp)
    if len(resid) != n_planes:
        raise ValueError(
            f"residual planes {len(resid)} != sample planes {n_planes}"
        )
    if len(mask) < n_planes:
        raise ValueError(f"mask planes {len(mask)} < {n_planes}")
    if len(plane_dens_hists) != n_planes:
        raise ValueError(
            f"dens-hists planes {len(plane_dens_hists)} != {n_planes}"
        )
    stride = len(plane_dens_hists[0]) if n_planes else 0
    if stride <= 0:
        raise ValueError("each plane must have ≥1 code-bin dens-hist")
    for p in range(n_planes):
        if samp[p].shape != resid[p].shape:
            raise ValueError(
                f"plane {p} sample shape {samp[p].shape} != "
                f"residual {resid[p].shape}"
            )
        m = np.asarray(mask[p])
        if m.shape != samp[p].shape:
            raise ValueError(
                f"plane {p} mask shape {m.shape} != sample {samp[p].shape}"
            )
        if len(plane_dens_hists[p]) != stride:
            raise ValueError(
                f"plane {p} has {len(plane_dens_hists[p])} bins; "
                f"expected {stride}"
            )
    for p in range(n_planes):
        sp = samp[p]
        rp = resid[p]
        mp = np.asarray(mask[p])
        h, w = sp.shape
        for y in range(h):
            for x in range(w):
                if int(mp[y, x]) == 0:  # PakonIMAu.dll @ 0x102a86ae
                    continue
                pix = int(sp[y, x])
                b = ane_bin_index(
                    pix, pixel_offset, bin_divisor, max_bin
                )  # PakonIMAu.dll @ 0x102a86b4
                ane_dens_hist_accum(
                    plane_dens_hists[p][b],
                    int(rp[y, x]),
                    offset=hist_offset,
                    divisor=hist_divisor,
                )  # PakonIMAu.dll @ 0x102a86fa → 0x104ea370


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


def ane_residual_hist_params(res_max: int) -> tuple[float, float, int]:
    """Residual dens-hist ``(offset, divisor, n)`` from Ane init ``0x1027e6bc``.

    ``min = −resMax``, ``max = resMax``, ``n = 2·resMax + 1``; host uses
    ``offset = min``, ``divisor = 1`` (integer residual codes).
    """
    rm = int(res_max)
    if rm < 0:
        raise ValueError("res_max must be ≥ 0")
    return float(-rm), 1.0, 2 * rm + 1


def ane_empty_plane_dens_hists(
    n_planes: int,
    n_code_bins: int,
    n_res_bins: int,
) -> list[list[list[int]]]:
    """Allocate zeroed dens-hists ``[plane][code_bin][res_bin]`` for ``+0xa4``."""
    if n_planes < 1 or n_code_bins < 1 or n_res_bins < 1:
        raise ValueError("n_planes/n_code_bins/n_res_bins must be ≥ 1")
    return [
        [[0] * int(n_res_bins) for _ in range(int(n_code_bins))]
        for _ in range(int(n_planes))
    ]


def ane_accumulate_sample_residual_84d0(
    plane_dens_hists: Sequence[Sequence[MutableSequence[int]]],
    sample: Sequence[np.ndarray] | np.ndarray,
    residual: Sequence[np.ndarray] | np.ndarray,
    *,
    pixel_offset: int,
    bin_divisor: int,
    max_bin: int,
    hist_offset: float,
    hist_divisor: float,
) -> None:
    """Sample/residual dens-hist accumulate @ ``0x102a84d0`` (Unicorn-golden).

    ``plane_dens_hists[plane][code_bin]`` is the residual dens-hist count
    array (Ane map ``+0xa4`` slot ``stride*plane + bin``). ``sample`` /
    ``residual`` are per-plane int16 HxW (or a single HxWxC array).
    Mutates dens-hists in place. Plane ImgHistogram ``+0xa8`` side path
    is omitted (not consumed by dens→``getResults``).
    """
    samp = _ane_planes_i16(sample)
    resid = _ane_planes_i16(residual)
    n_planes = len(samp)
    if len(resid) != n_planes:
        raise ValueError(
            f"residual planes {len(resid)} != sample planes {n_planes}"
        )
    if len(plane_dens_hists) != n_planes:
        raise ValueError(
            f"dens-hists planes {len(plane_dens_hists)} != {n_planes}"
        )
    stride = len(plane_dens_hists[0]) if n_planes else 0
    if stride <= 0:
        raise ValueError("each plane must have ≥1 code-bin dens-hist")
    for p in range(n_planes):
        if samp[p].shape != resid[p].shape:
            raise ValueError(
                f"plane {p} sample shape {samp[p].shape} != "
                f"residual {resid[p].shape}"
            )
        if len(plane_dens_hists[p]) != stride:
            raise ValueError(
                f"plane {p} has {len(plane_dens_hists[p])} bins; "
                f"expected {stride}"
            )
        h, w = samp[p].shape
        for y in range(h):
            srow = samp[p][y]
            rrow = resid[p][y]
            for x in range(w):
                s_px = int(srow[x])
                b = ane_bin_index(s_px, pixel_offset, bin_divisor, max_bin)
                if b >= stride:
                    b = stride - 1
                ane_dens_hist_accum(
                    plane_dens_hists[p][b],
                    int(rrow[x]),
                    offset=hist_offset,
                    divisor=hist_divisor,
                )


def _ane_planes_i16(
    image: Sequence[np.ndarray] | np.ndarray,
) -> list[np.ndarray]:
    """Normalize to list of HxW int16 planes."""
    arr = np.asarray(image)
    if isinstance(image, (list, tuple)):
        planes = [np.asarray(p, dtype=np.int16) for p in image]
        for i, p in enumerate(planes):
            if p.ndim != 2:
                raise ValueError(f"plane {i} must be HxW, got {p.shape}")
        return planes
    if arr.ndim == 2:
        return [arr.astype(np.int16, copy=False)]
    if arr.ndim == 3:
        return [
            arr[:, :, c].astype(np.int16, copy=False)
            for c in range(arr.shape[2])
        ]
    raise ValueError("image must be HxW, HxWxC, or sequence of HxW planes")


def ane_build_noise_table_e9d0(
    sample_residual_pairs: Sequence[
        tuple[Sequence[np.ndarray] | np.ndarray, Sequence[np.ndarray] | np.ndarray]
    ],
    n: int,
    *,
    code_value_min: int = 0,
    code_value_max: int = 4095,
    code_value_bins: int = 8,
    res_max: int = 1000,
    alpha: float = 5.0,
    scale_factor: float = 1.0,
    tau: float = 0.15,
    use_masking: bool = False,
    use_avg: bool = False,
    merge_min_count: int = 50,
    merge_max_radius: int = 3,
) -> "NoiseTable":
    """Build orch ``0x1027e9d0`` → ``NoiseTable``.

    Defaults match ``ane-default.dpi`` / AneParams ctor where cited.
    ``use_avg=True`` runs correlation pass ``0x102a8950``/``8600`` when
    both leaf flags are True. ``n`` is dens table length
    (``NoiseTable+0x44`` / Impl ``+0xf8``).
    """
    if use_avg and not (
        ANE_ANALYZE_CORR_MASK_PORTED and ANE_ANALYZE_ACCUM_8600_PORTED
    ):
        raise NotImplementedError(
            "0x1027e9d0 useAvg≠0 path open: color_correlation_mask "
            "0x102a8950 + masked accum 0x102a8600"
        )
    if not sample_residual_pairs:
        raise ValueError(
            "Empty or mismatched sample/residual vectors."  # cite 0x105a5f98
        )
    samp0, _ = sample_residual_pairs[0]
    n_planes = len(_ane_planes_i16(samp0))
    if n_planes < 2:
        raise ValueError("need ≥2 planes for curve rows (x + ≥1 y)")
    if use_avg and n_planes < 3:
        raise ValueError(
            "color_correlation_mask(): x must have 3 channels"  # cite 0x105a87f8
        )
    # Ane init: divisor = (max−min+1)/bins; max_bin = bins−1 (0x1027e570…)
    span = int(code_value_max) - int(code_value_min) + 1
    bins = int(code_value_bins)
    if bins <= 0:
        raise ValueError("code_value_bins must be > 0")
    bin_divisor = int(span // bins) if bins else 0
    if bin_divisor == 0:
        raise ValueError("bin_divisor would be 0 (DLL idiv)")
    max_bin = bins - 1
    hist_off, hist_div, n_res = ane_residual_hist_params(res_max)
    plane_hists = ane_empty_plane_dens_hists(n_planes, bins, n_res)
    for sample, residual in sample_residual_pairs:
        ane_accumulate_sample_residual_84d0(
            plane_hists,
            sample,
            residual,
            pixel_offset=int(code_value_min),
            bin_divisor=bin_divisor,
            max_bin=max_bin,
            hist_offset=hist_off,
            hist_divisor=hist_div,
        )
    if use_avg:
        # First finalize @ 0x1027eae9: do_adjust=1; adjust reads +0x20.
        pre_doubles = ane_finalize_plane_doubles_from_hists(
            plane_hists,
            knot_scale=float(alpha),
            merge_min_count=int(merge_min_count),
            merge_max_radius=int(merge_max_radius),
            do_adjust=True,  # PakonIMAu.dll @ 0x1027eade
            adjust_limit=float(tau),  # object +0x20 @ 0x102a88ae
            scale=float(scale_factor),
        )
        # Clear dens-hists @ 0x1027eaf0 → 0x1027e3a0
        plane_hists = ane_empty_plane_dens_hists(n_planes, bins, n_res)
        for sample, residual in sample_residual_pairs:
            masks, _ratio = ane_color_correlation_mask_8950(
                sample,
                residual,
                pre_doubles,
                pixel_offset=int(code_value_min),
                bin_divisor=bin_divisor,
                max_bin=max_bin,
                tau=float(tau),
            )
            ane_accumulate_masked_8600(
                plane_hists,
                sample,
                residual,
                masks,
                pixel_offset=int(code_value_min),
                bin_divisor=bin_divisor,
                max_bin=max_bin,
                hist_offset=hist_off,
                hist_divisor=hist_div,
            )
    return noise_table_from_dens_hists(
        plane_hists,
        n,
        knot_scale=float(alpha),
        merge_min_count=int(merge_min_count),
        merge_max_radius=int(merge_max_radius),
        do_adjust=bool(use_masking),
        adjust_limit=float(tau),
        scale=float(scale_factor),
    )


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


def ane_neighbor_hist_merge(
    dens_hists: Sequence[Sequence[int]],
    bin_index: int,
    *,
    min_count: int = 0,
    max_radius: int = 0,
) -> list[int]:
    """Neighbor dens-hist merge @ ``0x102a82a0`` (Unicorn-golden).

    ``dens_hists[i]`` is the count array for dens-bin slot ``i`` within
    one plane (length = Ane ``+0x40`` stride). Starts from a **copy** of
    ``dens_hists[bin_index]``, then adds left/right neighbor bin counts
    while ``ring < max_radius`` or ``sum < min_count`` (Ane ``+0x54`` /
    ``+0x5c``). Stops when both neighbors leave ``[0, len)``.
    """
    stride = len(dens_hists)
    if stride <= 0:
        raise ValueError("dens_hists must be non-empty")
    b = int(bin_index)
    if b < 0 or b >= stride:
        raise ValueError(f"bin_index {b} out of range for stride {stride}")
    n = len(dens_hists[b])
    for i, h in enumerate(dens_hists):
        if len(h) != n:
            raise ValueError(f"dens_hists[{i}] length {len(h)} != {n}")
    working = [int(x) for x in dens_hists[b]]
    left = b - 1
    right = b + 1
    ring = 0
    total = sum(working)
    max_r = int(max_radius)
    min_c = int(min_count)
    while True:
        if ring >= max_r and total >= min_c:
            break
        if left >= 0:
            src = dens_hists[left]
            for i in range(n):
                working[i] += int(src[i])
            if right < stride:
                src = dens_hists[right]
                for i in range(n):
                    working[i] += int(src[i])
        elif right < stride:
            src = dens_hists[right]
            for i in range(n):
                working[i] += int(src[i])
        else:
            break
        left -= 1
        right += 1
        ring += 1
        total = sum(working)
    return working


def ane_finalize_plane_doubles_from_hists(
    plane_dens_hists: Sequence[Sequence[Sequence[int]]],
    *,
    knot_scale: float = 1.0,
    merge_min_count: int = 0,
    merge_max_radius: int = 0,
    do_adjust: bool = False,
    adjust_limit: float = 0.0,
    scale: float = 1.0,
) -> list[list[float]]:
    """Finalize compose: merge → knot → optional adjust → scale.

    ``plane_dens_hists[plane][bin]`` = dens-hist counts. Mirrors
    ``0x102a8770`` per-slot path using ported leaves (cite merge /
    ``0x102a7a30`` / ``0x102a78c0``). ``scale`` is finalize ``[ebp+8]``;
    when ``|scale−1| > ANE_FINALIZE_SCALE_EPS`` each knot is multiplied.
    """
    if not plane_dens_hists:
        raise ValueError("plane_dens_hists must be non-empty")
    n_planes = len(plane_dens_hists)
    n_bins = len(plane_dens_hists[0])
    if n_bins <= 0:
        raise ValueError("each plane must have ≥1 dens-bin")
    out: list[list[float]] = []
    for p in range(n_planes):
        row_hists = plane_dens_hists[p]
        if len(row_hists) != n_bins:
            raise ValueError(
                f"plane {p} has {len(row_hists)} bins; expected {n_bins}"
            )
        doubles: list[float] = []
        for b in range(n_bins):
            merged = ane_neighbor_hist_merge(
                row_hists,
                b,
                min_count=merge_min_count,
                max_radius=merge_max_radius,
            )
            v = ane_finalize_knot_7a30(merged, float(knot_scale), 0)
            if do_adjust:
                v = ane_finalize_adjust_78c0(v, float(adjust_limit))
            doubles.append(float(v))
        out.append(doubles)
    sc = float(scale)
    if abs(sc - 1.0) > ANE_FINALIZE_SCALE_EPS:
        out = [[v * sc for v in row] for row in out]
    return out


def noise_table_from_dens_hists(
    plane_dens_hists: Sequence[Sequence[Sequence[int]]],
    n: int,
    *,
    knot_scale: float = 1.0,
    merge_min_count: int = 0,
    merge_max_radius: int = 0,
    do_adjust: bool = False,
    adjust_limit: float = 0.0,
    scale: float = 1.0,
) -> "NoiseTable":
    """dens-hists → finalize → curve rows → ``getResults`` dens fill.

    ``n_channels = n_planes − 1`` (cite ``0x101ebff8``). Requires ≥2
    planes (plane0 = knot ``x``, plane1+ = ``y``).
    """
    doubles = ane_finalize_plane_doubles_from_hists(
        plane_dens_hists,
        knot_scale=knot_scale,
        merge_min_count=merge_min_count,
        merge_max_radius=merge_max_radius,
        do_adjust=do_adjust,
        adjust_limit=adjust_limit,
        scale=scale,
    )
    if len(doubles) < 2:
        raise ValueError("need ≥2 planes for curve rows (x + ≥1 y)")
    knots = curve_knots_from_plane_doubles(doubles)
    return noise_table_from_knots(knots, n, n_channels=len(doubles) - 1)


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
    print(f"  accum 84d0        {ANE_ANALYZE_ACCUM_84D0:#010x}")
    print(f"  bin-index leaf    {ANE_ANALYZE_BIN_INDEX:#010x}")
    print(f"  dens-hist accum   {ANE_ANALYZE_HIST_ACCUM:#010x}")
    print(f"  finalize          {ANE_ANALYZE_FINALIZE:#010x}")
    print(f"  finalize knot     {ANE_ANALYZE_FINALIZE_KNOT:#010x}")
    print(f"  finalize adjust   {ANE_ANALYZE_FINALIZE_ADJUST:#010x}")
    print(f"  neighbor merge    {ANE_ANALYZE_NEIGHBOR_MERGE:#010x}")
    print(f"  curve rows        {ANE_CURVE_ROWS_FROM_DOUBLES:#010x}")
    print(f"  ctor/alloc        {NOISE_TABLE_CTOR:#010x} / {NOISE_TABLE_ALLOC:#010x}")
    print(
        f"  LAYOUT_PORTED={ANE_NOISE_TABLE_LAYOUT_PORTED} "
        f"FILL_PORTED={ANE_GET_RESULTS_FILL_PORTED} "
        f"BIN_INDEX_PORTED={ANE_ANALYZE_BIN_INDEX_PORTED} "
        f"HIST_ACCUM_PORTED={ANE_ANALYZE_HIST_ACCUM_PORTED} "
        f"NEIGHBOR_MERGE_PORTED={ANE_ANALYZE_NEIGHBOR_MERGE_PORTED} "
        f"FINALIZE_KNOT_PORTED={ANE_ANALYZE_FINALIZE_KNOT_PORTED} "
        f"FINALIZE_ADJUST_PORTED={ANE_ANALYZE_FINALIZE_ADJUST_PORTED} "
        f"CURVE_ROWS_PORTED={ANE_CURVE_ROWS_FROM_DOUBLES_PORTED} "
        f"ACCUM_84D0_PORTED={ANE_ANALYZE_ACCUM_84D0_PORTED} "
        f"CORR_MASK_PORTED={ANE_ANALYZE_CORR_MASK_PORTED} "
        f"ACCUM_8600_PORTED={ANE_ANALYZE_ACCUM_8600_PORTED} "
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
    merged = ane_neighbor_hist_merge(
        [[1, 0], [0, 2], [0, 0], [3, 0], [0, 4]],
        2,
        min_count=100,
        max_radius=2,
    )
    print(f"  sample neighbor merge={merged}")
    k = ane_finalize_knot_7a30([1, 2, 3, 4, 5, 6, 5, 4, 3, 2, 1], 1.0)
    print(f"  sample finalize knot={k}")
    rows = curve_knots_from_plane_doubles([[0.0, 10.0], [1.0, 2.0]])
    print(f"  sample curve rows={rows}")
    # 84d0 + e9d0 host smoke (2 planes, tiny images)
    s0 = np.array([[100, 200], [300, 400]], dtype=np.int16)
    r0 = np.array([[1, -2], [3, -4]], dtype=np.int16)
    s1 = np.array([[110, 210], [310, 410]], dtype=np.int16)
    r1 = np.array([[0, 1], [-1, 2]], dtype=np.int16)
    nt2 = ane_build_noise_table_e9d0(
        [([s0, s1], [r0, r1])],
        n=32,
        code_value_bins=8,
        res_max=10,
        merge_min_count=0,
        merge_max_radius=0,
    )
    print(
        f"  e9d0 smoke NoiseTable n={nt2.n} ch={nt2.n_channels} "
        f"dens[0,:4]={nt2.dens[0, :4]}"
    )


if __name__ == "__main__":
    main()
