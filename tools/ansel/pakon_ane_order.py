#!/usr/bin/env python3
"""AneOrder / NoiseMethods — dens table layout + getResults fill.

PakonIMAu.dll base ``0x10000000``. Catalog + host layout for the float
table CnPremium indexes at mid-aim. ``getResults`` dens **fill** from
Impl curve rows is ported; AneOrder **analyze** (who builds those rows)
remains WALL.

VERIFIED call chain
===================

Order-wide analyze
------------------
* Path ``ColorNegativePath::analyzeAneOrder`` @ ``0x100fad90``
* Cap ``AnsAneOrderCapability::analyze`` @ ``0x10110540``
* Impl analyze @ ``0x101ed3a0``
* Cap ``getResults`` @ ``0x10110830`` → Impl ``0x101ebe90``
  (string ``0x1059b3a4``)

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

``ANE_GET_RESULTS_FILL_PORTED = True``. AneOrder analyze that produces
the curve rows is still open → ``ANE_ORDER_PORTED = False``.

OrderOrientation (separate)
---------------------------
* Cap ``0x101218c0`` / Impl ``0x102101d0`` — from ``analyzeAttributes``
  ``0x100fb576``, **not** AneOrder dens.

Flags
-----
* ``ANE_NOISE_TABLE_LAYOUT_PORTED = True`` — host ``NoiseTable`` layout +
  alloc size + plane view for ``ane_dens_contrib``.
* ``ANE_GET_RESULTS_FILL_PORTED = True`` — dens fill from cited curve rows.
* ``ANE_ORDER_PORTED = False`` — analyze / residual maths still open.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

ANE_ORDER_PORTED = False
ANE_NOISE_TABLE_LAYOUT_PORTED = True
ANE_GET_RESULTS_FILL_PORTED = True

PATH_ANALYZE_ANE_ORDER = 0x100FAD90
ANE_ORDER_CAP_ANALYZE = 0x10110540
ANE_ORDER_IMPL_ANALYZE = 0x101ED3A0
ANE_ORDER_CAP_GET_RESULTS = 0x10110830
ANE_ORDER_IMPL_GET_RESULTS = 0x101EBE90
ANE_ORDER_GET_RESULTS_FILL = 0x101EC10A
ORDER_ORIENTATION_CAP_ANALYZE = 0x101218C0

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
    print(f"  ctor/alloc        {NOISE_TABLE_CTOR:#010x} / {NOISE_TABLE_ALLOC:#010x}")
    print(
        f"  LAYOUT_PORTED={ANE_NOISE_TABLE_LAYOUT_PORTED} "
        f"FILL_PORTED={ANE_GET_RESULTS_FILL_PORTED} "
        f"ANE_ORDER_PORTED={ANE_ORDER_PORTED}"
    )
    nt = NoiseTable.zeros(64, 1)
    print(f"  sample alloc nbytes={noise_table_alloc_nbytes(nt.n, nt.n_channels)}")
    sample = get_results_fill_dens([(5.0, 2.0), (15.0, 12.0)], 20, 1)
    print(f"  sample fill[0,:8]={sample[0, :8]}")


if __name__ == "__main__":
    main()
