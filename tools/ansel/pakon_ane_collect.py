#!/usr/bin/env python3
"""AneSampledImage / AneResidualImage producers — collectData leaf.

PakonIMAu.dll base ``0x10000000``.

``AnsAneCapabilityImpl::collectData`` @ ``0x101ee590`` (string
``0x1059b55c``) builds portfolio entries named ``AneSampledImage`` /
``AneResidualImage`` (``0x1059b2e8`` / ``0x1059b2d4``). Pixel fill is
dispatched by ``0x10280bd0``:

* ``this+0x7c == 0`` → directional residual ``0x1027fc80`` (this module).
* ``this+0x7c != 0`` → box-average residual ``0x102804e0`` (this module).

Shipped ``ane-*.dpi`` uses ``filterMode=Laplacian`` → null ``+0x7c`` →
fc80. Box ``804e0`` is ported for honesty when ``filterSize`` is 3 or 5
(``this+0x7c`` non-null).

``0x1027fc80`` (ported leaf — sample + residual int16 planes)
--------------------------------------------------------------
For each output pixel at source center ``C`` (margin 2 in rows/cols),
evaluate four axis predictors of the form::

    pred = 4·(inner₀ + inner₁) − outer₀ − outer₁
    err  = |6·C − pred|

Axes (relative to ``C``):

* H:  (±1,0) inners, (±2,0) outers
* V:  (0,±1) / (0,±2)
* D1: (−1,−1)/(+1,+1) / (−2,−2)/(+2,+2)
* D2: (−1,+1)/(+1,−1) / (−2,+2)/(+2,−2)

Keep the ``pred`` with smallest ``err`` (ties keep earlier axis;
cite ``jge`` / final ``jl`` @ ``0x1028009d…0x10280199``). Then::

    approx    = (pred · 0x555 + 0x1000) >> 13   # ≈ pred/6
    residual  = i16(approx − C)
    sample    = C                                 # when avg flag clear
    sample    = i16(signed_div17(C + Σ₁₆))        # when flag set

``Σ₁₆`` = sum of the 16 axis neighbors (all four axes' inners+outers).
``signed_div17`` = MSVC ``imul 0x78787879; sar 3; +sign`` @
``0x102801cf…``.

Subsample: output grid uses ``x_step`` / ``y_step`` (Cap ``+0xb0`` /
``+0xb4``); source walks start at ``(col0−2, row0−2)`` for the 5-tap
window (cite ``0x1027fe9a…0x1027feb9``).

``0x102804e0`` (ported leaf — box average residual)
---------------------------------------------------
Pixel body @ ``0x10280800…0x102808f1`` (cite DLL):

* ``filterSize == 3`` (@ ``esp+0x4e0``): sum 3×3; MSVC
  ``imul 0x38e38e39; sar edx,1`` + signbit → trunc ``/9``.
* else (5): sum 5×5 (25 taps); ``imul 0x51eb851f; sar edx,3`` +
  signbit → trunc ``/25``.
* ``residual = i16(avg − C)``; ``sample = avg`` if correctForFilter
  flag (@ ``esp+0x4e4``) else ``C``.
* Margin: 1 for size 3, 2 for size 5 (cite ``0x10280578…0x10280587``).

Flags
-----
* ``ANE_COLLECT_FC80_PORTED`` — directional leaf (Unicorn-golden).
* ``ANE_COLLECT_804E0_PORTED`` — box leaf (Unicorn-golden).
* Full ``collectData`` COM/portfolio wrap still open
  (``ANE_COLLECT_DATA_PORTED=False``).
"""
from __future__ import annotations

import struct
from typing import Sequence, Tuple

import numpy as np

ANE_COLLECT_FC80_PORTED = True
ANE_COLLECT_804E0_PORTED = True
ANE_COLLECT_DATA_PORTED = False  # full collectData + portfolio insert

ANE_COLLECT_DATA = 0x101EE590
ANE_COLLECT_DISPATCH = 0x10280BD0
ANE_SAMPLE_RESIDUAL_FC80 = 0x1027FC80
ANE_SAMPLE_RESIDUAL_804E0 = 0x102804E0
ANE_SAMPLE_RESIDUAL_PIXEL = 0x10280030  # fc80 inner pixel body
ANE_SAMPLE_RESIDUAL_PIXEL_END = 0x102801E4  # after optional avg store
ANE_SAMPLE_RESIDUAL_804E0_PIXEL = 0x10280800  # box pixel body
ANE_SAMPLE_RESIDUAL_804E0_PIXEL_END = 0x102808F1  # after sample/resid stores

STR_COLLECT_DATA = 0x1059B55C
STR_ANE_SAMPLED_IMAGE = 0x1059B2E8
STR_ANE_RESIDUAL_IMAGE = 0x1059B2D4


def _i16(x: int) -> int:
    x = int(x) & 0xFFFF
    return x - 0x10000 if x >= 0x8000 else x


def _sar32(x: int, n: int) -> int:
    return int(np.int32(x) >> n)


def ane_pred_div6(pred: int) -> int:
    """``(pred * 0x555 + 0x1000) >> 13`` @ ``0x102801a1…`` (signed)."""
    lo = (int(np.int32(pred)) * 0x555) & 0xFFFFFFFF
    if lo >= 0x80000000:
        lo -= 0x100000000
    return _sar32(lo + 0x1000, 13)


def ane_signed_div17(n: int) -> int:
    """MSVC signed ``n/17`` @ ``0x102801cf…0x102801de``."""
    magic = struct.unpack("<i", struct.pack("<I", 0x78787879))[0]
    prod = int(np.int32(n)) * magic
    edx = _sar32(prod >> 32, 3)
    return edx + ((edx >> 31) & 1)


def ane_signed_div9(n: int) -> int:
    """MSVC signed ``n/9`` @ ``0x10280871…0x102808d4`` (``0x38e38e39; sar 1``)."""
    magic = struct.unpack("<i", struct.pack("<I", 0x38E38E39))[0]
    prod = int(np.int32(n)) * magic
    edx = _sar32(prod >> 32, 1)
    return edx + ((edx >> 31) & 1)


def ane_signed_div25(n: int) -> int:
    """MSVC signed ``n/25`` @ ``0x102808bf…0x102808d4`` (``0x51eb851f; sar 3``)."""
    magic = struct.unpack("<i", struct.pack("<I", 0x51EB851F))[0]
    prod = int(np.int32(n)) * magic
    edx = _sar32(prod >> 32, 3)
    return edx + ((edx >> 31) & 1)


def ane_804e0_pixel(
    plane: Sequence[int],
    pitch: int,
    cy: int,
    cx: int,
    *,
    filter_size: int = 5,
    avg_flag: bool = False,
) -> Tuple[int, int]:
    """Box-average sample/residual for one center ``(cy, cx)``.

    Cite pixel body ``0x10280800…0x102808f1``. ``filter_size`` 3 → 3×3 /9;
    else 5×5 /25. Returns ``(sample, residual)`` int16-range ints.
    """
    pitch = int(pitch)
    fs = 3 if int(filter_size) == 3 else 5
    rad = 1 if fs == 3 else 2

    def p(dr: int, dc: int) -> int:
        return int(plane[(cy + dr) * pitch + (cx + dc)])

    c = p(0, 0)
    total = 0
    for dr in range(-rad, rad + 1):
        for dc in range(-rad, rad + 1):
            total += p(dr, dc)
    avg = ane_signed_div9(total) if fs == 3 else ane_signed_div25(total)
    residual = _i16(avg - c)
    sample = _i16(avg) if avg_flag else _i16(c)
    return sample, residual


def ane_fc80_pixel(
    plane: Sequence[int],
    pitch: int,
    cy: int,
    cx: int,
    *,
    avg_flag: bool = False,
) -> Tuple[int, int]:
    """Directional sample/residual for one center ``(cy, cx)``.

    ``plane`` is row-major int16 samples with row stride ``pitch``.
    Requires ``cy,cx`` in ``[2, h-3]`` / ``[2, pitch-3]`` for the window.
    Returns ``(sample, residual)`` as Python ints in int16 range.
    """
    pitch = int(pitch)

    def p(dr: int, dc: int) -> int:
        return int(plane[(cy + dr) * pitch + (cx + dc)])

    c = p(0, 0)
    axes = (
        (p(0, -1), p(0, 1), p(0, -2), p(0, 2)),
        (p(-1, 0), p(1, 0), p(-2, 0), p(2, 0)),
        (p(-1, -1), p(1, 1), p(-2, -2), p(2, 2)),
        (p(-1, 1), p(1, -1), p(-2, 2), p(2, -2)),
    )
    best_pred = 0
    best_err = 0xFFFF
    neigh = 0
    for ia, ib, oa, ob in axes:
        pred = 4 * (ia + ib) - oa - ob
        err = abs(6 * c - pred)
        neigh += ia + ib + oa + ob
        if err < best_err:
            best_err = err
            best_pred = pred
    approx = ane_pred_div6(best_pred)
    residual = _i16(approx - c)
    if avg_flag:
        sample = _i16(ane_signed_div17(c + neigh))
    else:
        sample = _i16(c)
    return sample, residual


# Shipped ``ane-default.dpi`` / ``ane-CN-Fps.dpi`` (cite install tree)
ANE_DPI_COL_SAMPLING = 32  # Cap ``+0xb0`` → fc80 x_step
ANE_DPI_ROW_SAMPLING = 32  # Cap ``+0xb4`` → fc80 y_step
ANE_DPI_CORRECT_FOR_FILTER = True  # Cap ``+0x7a`` avg-flag (dpi = 1)
ANE_DPI_FILTER_MODE_LAPLACIAN = True  # → ``0x1027fc80`` (not box ``804e0``)


def ane_fc80_planes(
    plane: np.ndarray,
    *,
    x_step: int = 1,
    y_step: int = 1,
    avg_flag: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """Build sample + residual int16 planes for one channel (``0x1027fc80``).

    ``plane`` is 2-D int16. Output size matches DLL: from starts aligned so
    the last center stays ≥2 from borders (cite ``0x1027fd3c…0x1027fd96``).
    Host uses the same margin/step arithmetic for parity.
    """
    if plane.ndim != 2:
        raise ValueError("plane must be 2-D")
    h, w = plane.shape
    xs = max(1, int(x_step))
    ys = max(1, int(y_step))
    # DLL: start at 1+step (while start < 2), end trimmed by −3 margin.
    x0 = 1
    while x0 < 2:
        x0 += xs
    y0 = 1
    while y0 < 2:
        y0 += ys
    # last center ≤ dim-3
    def n_out(dim: int, start: int, step: int) -> int:
        if start > dim - 3:
            return 0
        return (dim - 3 - start) // step + 1

    nw = n_out(w, x0, xs)
    nh = n_out(h, y0, ys)
    if nh == 0 or nw == 0:
        return (
            np.zeros((0, 0), dtype=np.int16),
            np.zeros((0, 0), dtype=np.int16),
        )
    flat = plane.astype(np.int16, copy=False).ravel()
    pitch = w
    sampled = np.empty((nh, nw), dtype=np.int16)
    residual = np.empty((nh, nw), dtype=np.int16)
    for oy in range(nh):
        cy = y0 + oy * ys
        for ox in range(nw):
            cx = x0 + ox * xs
            s, r = ane_fc80_pixel(flat, pitch, cy, cx, avg_flag=avg_flag)
            sampled[oy, ox] = s
            residual[oy, ox] = r
    return sampled, residual


def ane_fc80_rgb_sample_residual(
    rgb_i16: np.ndarray,
    *,
    col_sampling: int = ANE_DPI_COL_SAMPLING,
    row_sampling: int = ANE_DPI_ROW_SAMPLING,
    correct_for_filter: bool = ANE_DPI_CORRECT_FOR_FILTER,
) -> Tuple[list[np.ndarray], list[np.ndarray]]:
    """Per-channel ``0x1027fc80`` planes for HxWx3 int16 RGB.

    Returns ``(sample_planes, residual_planes)`` each length 3. Empty when
    the source is smaller than the 5-tap + step grid.
    """
    img = np.asarray(rgb_i16)
    if img.ndim != 3 or img.shape[2] < 3:
        raise ValueError("rgb_i16 must be HxWx≥3")
    samples: list[np.ndarray] = []
    residuals: list[np.ndarray] = []
    for c in range(3):
        s, r = ane_fc80_planes(
            img[:, :, c],
            x_step=col_sampling,
            y_step=row_sampling,
            avg_flag=correct_for_filter,
        )
        samples.append(s)
        residuals.append(r)
    return samples, residuals


def ane_noise_table_from_rgb_fc80(
    rgb_i16: np.ndarray,
    n: int,
    *,
    col_sampling: int = ANE_DPI_COL_SAMPLING,
    row_sampling: int = ANE_DPI_ROW_SAMPLING,
    correct_for_filter: bool = ANE_DPI_CORRECT_FOR_FILTER,
    code_value_bins: int = 32,
    **e9d0_kwargs,
):
    """``collectData`` Laplacian leaf → ``0x1027e9d0`` ``NoiseTable``.

    One scene / one RGB image (shipped path builds portfolio then analyze).
    Defaults match ``ane-CN-Fps.dpi`` bins=32 when ``code_value_bins`` omitted.
    Raises ``ValueError`` if the sample grid is empty.
    """
    from pakon_ane_order import ane_build_noise_table_e9d0

    samples, residuals = ane_fc80_rgb_sample_residual(
        rgb_i16,
        col_sampling=col_sampling,
        row_sampling=row_sampling,
        correct_for_filter=correct_for_filter,
    )
    if samples[0].size == 0:
        raise ValueError(
            "fc80 sample grid empty (need image larger than step+margin)"
        )
    return ane_build_noise_table_e9d0(
        [(samples, residuals)],
        int(n),
        code_value_bins=int(code_value_bins),
        **e9d0_kwargs,
    )


def _box_margin(filter_size: int) -> int:
    """Border margin for box filter (cite ``0x10280578…0x10280587``)."""
    return 1 if int(filter_size) == 3 else 2


def ane_804e0_planes(
    plane: np.ndarray,
    *,
    filter_size: int = 5,
    x_step: int = 1,
    y_step: int = 1,
    avg_flag: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """Build sample + residual int16 planes for one channel (``0x102804e0``).

    Margin 1 for ``filter_size==3``, else 2 (cite setup ``0x10280578…``).
    Step alignment matches the DLL ``start=1; while start < margin: +step``.
    """
    if plane.ndim != 2:
        raise ValueError("plane must be 2-D")
    h, w = plane.shape
    xs = max(1, int(x_step))
    ys = max(1, int(y_step))
    margin = _box_margin(filter_size)
    # last center ≤ dim - (margin+1); same as dim-3 when margin=2
    last_lim = margin + 1

    x0 = 1
    while x0 < margin:
        x0 += xs
    y0 = 1
    while y0 < margin:
        y0 += ys

    def n_out(dim: int, start: int, step: int) -> int:
        if start > dim - last_lim:
            return 0
        return (dim - last_lim - start) // step + 1

    nw = n_out(w, x0, xs)
    nh = n_out(h, y0, ys)
    if nh == 0 or nw == 0:
        return (
            np.zeros((0, 0), dtype=np.int16),
            np.zeros((0, 0), dtype=np.int16),
        )
    flat = plane.astype(np.int16, copy=False).ravel()
    pitch = w
    sampled = np.empty((nh, nw), dtype=np.int16)
    residual = np.empty((nh, nw), dtype=np.int16)
    for oy in range(nh):
        cy = y0 + oy * ys
        for ox in range(nw):
            cx = x0 + ox * xs
            s, r = ane_804e0_pixel(
                flat,
                pitch,
                cy,
                cx,
                filter_size=filter_size,
                avg_flag=avg_flag,
            )
            sampled[oy, ox] = s
            residual[oy, ox] = r
    return sampled, residual


def ane_collect_planes(
    plane: np.ndarray,
    *,
    filter_mode_laplacian: bool = ANE_DPI_FILTER_MODE_LAPLACIAN,
    filter_size: int = 5,
    x_step: int = 1,
    y_step: int = 1,
    avg_flag: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """Dispatch helper: Laplacian → fc80 else box ``804e0`` (``0x10280bd0``).

    Shipped dpi is Laplacian → fc80. Pass ``filter_mode_laplacian=False``
    with ``filter_size`` 3 or 5 for the box path.
    """
    if filter_mode_laplacian:
        return ane_fc80_planes(
            plane, x_step=x_step, y_step=y_step, avg_flag=avg_flag
        )
    return ane_804e0_planes(
        plane,
        filter_size=filter_size,
        x_step=x_step,
        y_step=y_step,
        avg_flag=avg_flag,
    )
