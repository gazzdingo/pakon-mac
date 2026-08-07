#!/usr/bin/env python3
"""AneOrder / NoiseMethods — dens table layout for CnPremium mid-aims.

PakonIMAu.dll base ``0x10000000``. Catalog + host layout for the float
table CnPremium indexes at mid-aim. Do **not** invent ``getResults``
interpolation maths — dens **values** remain WALL.

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
* ``getResults`` fill @ ``0x101ec10a…`` interpolates into ``+0x4c`` from
  Impl ``+0x180`` curve vectors — **equations UNKNOWN**
  (``ANE_ORDER_PORTED=False``).

OrderOrientation (separate)
---------------------------
* Cap ``0x101218c0`` / Impl ``0x102101d0`` — from ``analyzeAttributes``
  ``0x100fb576``, **not** AneOrder dens.

Flags
-----
* ``ANE_NOISE_TABLE_LAYOUT_PORTED = True`` — host ``NoiseTable`` layout +
  alloc size + plane view for ``ane_dens_contrib``.
* ``ANE_ORDER_PORTED = False`` — analyze / ``getResults`` dens fill open.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

ANE_ORDER_PORTED = False
ANE_NOISE_TABLE_LAYOUT_PORTED = True

PATH_ANALYZE_ANE_ORDER = 0x100FAD90
ANE_ORDER_CAP_ANALYZE = 0x10110540
ANE_ORDER_IMPL_ANALYZE = 0x101ED3A0
ANE_ORDER_CAP_GET_RESULTS = 0x10110830
ANE_ORDER_IMPL_GET_RESULTS = 0x101EBE90
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


def noise_table_alloc_nbytes(n: int, n_channels: int) -> int:
    """``0x102560a0`` — ``n * n_channels * sizeof(float)``."""
    if n < 0 or n_channels < 0:
        raise ValueError("n and n_channels must be ≥ 0")
    return int(n) * int(n_channels) * 4


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
    print(f"  ctor/alloc        {NOISE_TABLE_CTOR:#010x} / {NOISE_TABLE_ALLOC:#010x}")
    print(
        f"  LAYOUT_PORTED={ANE_NOISE_TABLE_LAYOUT_PORTED} "
        f"ANE_ORDER_PORTED={ANE_ORDER_PORTED}"
    )
    nt = NoiseTable.zeros(64, 1)
    print(f"  sample alloc nbytes={noise_table_alloc_nbytes(nt.n, nt.n_channels)}")


if __name__ == "__main__":
    main()
