#!/usr/bin/env python3
"""FOS (film-order statistics) — verified fragments (PakonIMAu.dll).

Invoked from ``ColorNegativePath::analyzeBalanceOrder`` **between** SBA
``analyzePass1`` and ``analyzePass2``. Do **not** invent dens / R² /
slope maths. ``FOS_ANALYZE_PORTED = False`` until those closed forms
are pinned.

Full binary report: ``docs/47-sba-fos-binary.md``.

Call chain (VERIFIED)
=====================
* Cap ``AnsFosCapability::analyze`` @ ``0x1013cb30``
  (string ``0x1058bbe0``).
  - Sets Cap ``+0xf = 1`` (analyzed flag).
  - Forwards scene smart-ptr ``[ebp+0xc]`` to Impl via Cap ``+0x14``.
* Impl ``AnsFosCapabilityImpl::analyze()`` @ ``0x1023ff80``
  (string ``0x105a0d10``; also hosts ``analyzeThis`` string
  ``0x105a0c90`` in the same body).
* ``SbaCalcFosResults`` @ ``0x1028f570`` — sole ``E8`` from Impl @
  ``0x1024087c`` (fail format ``0x105a0b88``). Returns ``0`` on success;
  non-zero error codes (below).

balanceOrder relation (VERIFIED order; data coupling UNKNOWN)
-------------------------------------------------------------
``pass1`` → **FOS analyze** → ``pass2`` → path ``setShifts``.

* FOS requires an SBA capability on the scene (error
  ``Sba capability is NULL for scene.``).
* FOS writes **OUT** at ``Impl+0x18`` only. It does **not** write
  ``scene+0x3a38`` or Preference nested opening RGB
  (``scene+0x4d0e``). Preference remains **BLOCKED** on the UNKNOWN
  runtime writer of that nested field.
* Whether FOS OUT (``fosOrderAvg`` / ``fosDmin`` / …) feeds pass2 /
  Preference: **UNKNOWN** (no static edge found).

Critical correction — ``esi`` is OUT, not Preference RGB
--------------------------------------------------------
Dens / R² stores use ``esi`` = OUT = ``&Impl+0x18`` (``SbaFOSResults``,
36 bytes), **not** the scene nested object at ``scene+0x4cf0``.

Cap dump ``0x1013c210…`` names:

* ``+0x1e`` = ``numPixels`` (store ``0x102903e6``)
* ``+0x20`` = ``gmRSquare`` (store ``0x102903a4``)
* ``+0x22`` = ``illRSquare`` (store ``0x102903ef``)

Scene nested ``+0x1e/+0x20/+0x22`` (= ``scene+0x4d0e``) are Preference
opening RGB — same offsets, **different object**. FOS is not their
runtime writer.

``SbaCalcFosResults`` args (cdecl, ``add esp, 0x28`` = 10 args)
--------------------------------------------------------------
Call site ``0x1024085a…`` (Impl ``ebx``):

| # | value |
|---|--------|
| 0 | ``[ebp-0x48]`` (word compared ``>= 1`` at entry) |
| 1 | ``0`` |
| 2 | ``&Impl+0x40`` (3×int16 RGB words at ``+0/+2/+4``) |
| 3 | ``[Impl+0x68]`` (ptr; used as ``ptr+0xdc``, word @ ``+0x18``) |
| 4 | ``0`` |
| 5 | ``0`` |
| 6 | ``[Impl+0xc]`` (``frame+0x1a`` ptr array) |
| 7 | ``[Impl+0x10]`` (``frame+0x388c`` ptr array) |
| 8 | ``[Impl+0x14]`` (``frame+0x290c`` ptr array) |
| 9 | ``&Impl+0x18`` (**OUT** ``SbaFOSResults``, 36 bytes) |

Early errors (VERIFIED): ``0x18a5`` (arg0 word ``< 1``), ``0x18a4``
(null OUT), ``0x18a1`` / ``0x18a6`` / ``0x18a7`` (null ``+0xc/+0x14/+0x10``).
Discriminant fail: ``0x189d`` @ ``0x1029006b``.

OUT layout (``SbaFOSResults`` / Cap dump names)
----------------------------------------------
| off | field |
|-----|--------|
| ``+0x00`` | ``orderFpo`` (3×i16) |
| ``+0x06`` | ``fosOrderAvg`` (3×i16) |
| ``+0x0c`` | ``fosDmin`` (3×i16) |
| ``+0x12`` | ``gmSlope`` |
| ``+0x14`` | ``gmOffset`` |
| ``+0x16`` | ``illSlope`` |
| ``+0x18`` | ``illOffset`` |
| ``+0x1a`` | ``theta`` (not stored by calc) |
| ``+0x1c`` | ``ofpoMethod`` (not stored by calc) |
| ``+0x1e`` | ``numPixels`` |
| ``+0x20`` | ``gmRSquare`` |
| ``+0x22`` | ``illRSquare`` |

Opening transform on arg2 RGB (VERIFIED @ ``0x1028f608…``)
----------------------------------------------------------
Same ``×0x186a0`` family as ``Sba()`` / ``createAlgData`` /
path ``setShifts`` (see ``pakon_sba_core.py``):

* ``Y  ~ (R+G+B)*0x186a0`` → magic ``0x306e8227``, ``sar 0xf``, bias
  ``±0x1524a``
* ``C1 ~ (2G−B−R)*0x186a0`` → magic ``0x111f883d``, ``sar 0xe``, bias
  ``±0x1de6a``
* ``C2 ~ (B−R)*0x186a0`` → magic ``0x3b510a6f``, ``sar 0xf``, bias
  ``±0x11436``

Also: ``(word[arg3+0xdc+0x18])²`` into a local (sizing).

Dens / regression (structure VERIFIED; closed forms UNKNOWN)
-----------------------------------------------------------
Paxel walk over ``+0x388c``/``+0x290c`` planes (stride ``0x6c0``),
``sar 5`` product buckets, covariance-shaped temps
``(A*B)/N - 32*P``, acos path, then slope/R² FPU → OUT.
**Do not claim a full dens port** — equations UNKNOWN (see
``docs/47``). Portable fragments below: ``fos_dmin_min``,
``cov_numer_from_scaled``.

Impl result / history (VERIFIED fragments)
------------------------------------------
* ``Impl+0x18`` … ``+0x3b``: ``SbaFOSResults`` / history block.
  - History path: ``rep movsd`` from stack → ``+0x18``; ``+0x3c = 1``.
  - Calc success: ``+0x3c = 0``; OUT filled via ``esi=&+0x18``.
* Post-calc packs ``word[+0x9c/+0x9e/+0xa0]`` + ``+0x18`` block via
  ``0x1023fd20``.
* ``+0xa0`` preset: ``0`` if name at ``+0x70`` equals ``"sba"``, else
  ``1`` (@ ``0x102405d9``).
* Flags ``+0x94/+0x95`` gate history vs calc.

Ported below
------------
Arg validation + RGB opening three-axis + ``fosDmin`` component-wise
min + covariance numerator shape. Not a full analyze.
"""
from __future__ import annotations

import math

FOS_ANALYZE_PORTED = False
FOS_OPENING_TRANSFORM_PORTED = True  # fragment only

CAP_ANALYZE = 0x1013CB30
IMPL_ANALYZE = 0x1023FF80
SBA_CALC_FOS_RESULTS = 0x1028F570
SBA_CALC_FOS_CALL_SITE = 0x1024087C
IMPL_PACK_RESULT = 0x1023FD20
CAP_DUMP_FOS_RESULTS = 0x1013C210  # Cap dump names for OUT fields

# Impl layout (CapabilityImpl)
IMPL_PTR_0C = 0x0C
IMPL_PTR_10 = 0x10
IMPL_PTR_14 = 0x14
IMPL_RESULT_BLOCK = 0x18  # SbaFOSResults OUT / history
IMPL_RESULT_FLAG = 0x3C  # 1=history copy, 0=after calc
IMPL_RGB40 = 0x40  # 3×int16 fed as calc arg2
IMPL_PTR_68 = 0x68  # +0xdc subobject for size word

# Cap
CAP_ANALYZED_FLAG = 0x0F
CAP_IMPL_PTR = 0x14

# OUT / SbaFOSResults (Cap dump 0x1013c210…)
FOS_OFF_ORDER_FPO = 0x00  # 3×i16
FOS_OFF_ORDER_AVG = 0x06  # 3×i16
FOS_OFF_DMIN = 0x0C  # 3×i16
FOS_OFF_GM_SLOPE = 0x12
FOS_OFF_GM_OFFSET = 0x14
FOS_OFF_ILL_SLOPE = 0x16
FOS_OFF_ILL_OFFSET = 0x18
FOS_OFF_THETA = 0x1A  # not written by calc
FOS_OFF_OFPO_METHOD = 0x1C  # not written by calc
FOS_OFF_NUM_PIXELS = 0x1E
FOS_OFF_GM_RSQUARE = 0x20
FOS_OFF_ILL_RSQUARE = 0x22
FOS_RESULTS_SIZE = 0x24

# Shared with Sba / createAlgData / setShifts
RGB_SCALE = 0x186A0  # 100000
MAGIC_Y = 0x306E8227
MAGIC_C1 = 0x111F883D
MAGIC_C2 = 0x3B510A6F
BIAS_Y = 0x1524A
BIAS_C1 = 0x1DE6A
BIAS_C2 = 0x11436

# SbaCalcFosResults errors
ERR_ARG0 = 0x18A5
ERR_NULL_OUT = 0x18A4
ERR_NULL_0C = 0x18A1
ERR_NULL_14 = 0x18A6
ERR_NULL_10 = 0x18A7
ERR_DISC = 0x189D  # FPU discriminant @ 0x1029006b

STR_CAP_ANALYZE = 0x1058BBE0
STR_IMPL_ANALYZE = 0x105A0D10
STR_CALC_FAIL = 0x105A0B88
STR_AFTER_SCP_LUT_FOS = 0x10574134


def _i16(x: int) -> int:
    x &= 0xFFFF
    return x - 0x10000 if x >= 0x8000 else x


def _i32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x >= 0x80000000 else x


def _msvc_magic_div(value: int, magic: int, sar: int) -> int:
    """``imul magic; sar edx,N; add (edx>>31)`` (@ ``0x1028f64d`` etc.)."""
    a = _i32(value)
    b = _i32(magic)
    prod = a * b
    edx = prod >> 32
    edx = edx >> sar  # arithmetic
    return int(edx + ((edx >> 31) & 1))


def _biased_scale(rgb_term: int, bias: int) -> int:
    t = int(rgb_term) * RGB_SCALE
    return t + bias if t >= 0 else t - bias


def fos_opening_axes(r: int, g: int, b: int) -> tuple[int, int, int]:
    """``SbaCalcFosResults`` opening @ ``0x1028f608`` → three signed axes.

    Inputs are the three ``int16`` words at calc ``arg2`` (``Impl+0x40``).
    Does **not** include dens/FPU body or slope/R² fill.
    """
    r, g, b = _i16(r), _i16(g), _i16(b)
    y = _msvc_magic_div(_biased_scale(r + g + b, BIAS_Y), MAGIC_Y, 0xF)
    c1 = _msvc_magic_div(_biased_scale(2 * g - b - r, BIAS_C1), MAGIC_C1, 0xE)
    c2 = _msvc_magic_div(_biased_scale(b - r, BIAS_C2), MAGIC_C2, 0xF)
    return y, c1, c2


def _axis_to_code(axis: int, bias: int, magic: int, sar: int, scale: int = RGB_SCALE) -> int:
    """setShifts merge: ``magic(axis·scale ± bias)`` (@ ``0x10100651`` family)."""
    t = int(axis) * int(scale)
    return _msvc_magic_div(t + bias if t >= 0 else t - bias, magic, sar)


def fos_opening_axes_inverse(y: int, c1: int, c2: int) -> tuple[int, int, int]:
    """Integer inverse of ``fos_opening_axes`` used by setShifts (@ ``0x10100651``…).

    Exact on many triples; magic division can leave ±1 LSB on round-trip.
    Reconstruct (VERIFIED):

    * ``R = Yc − C1c − C2c``
    * ``G = Yc + magic_c1(C1·0x30d40 ± bias)``
    * ``B = Yc − C1c + C2c``
    """
    yc = _axis_to_code(y, BIAS_Y, MAGIC_Y, 0xF)
    c1c = _axis_to_code(c1, BIAS_C1, MAGIC_C1, 0xE)
    c2c = _axis_to_code(c2, BIAS_C2, MAGIC_C2, 0xF)
    c1x2 = _axis_to_code(c1, BIAS_C1, MAGIC_C1, 0xE, scale=0x30D40)
    r = yc - c1c - c2c
    g = yc + c1x2
    b = yc - c1c + c2c
    return r, g, b


def fos_dmin_min(
    frame_rgb_triples: list[tuple[int, int, int]],
) -> tuple[int, int, int]:
    """OUT ``+0xc`` ``fosDmin``: component-wise min across frames.

    Mirrors ``0x1028f6d8…740`` (first frame copy, then min if
    ``arg0 > 1``). Inputs are the 3×i16 at each ``frame+0x290c``.
    """
    if not frame_rgb_triples:
        raise ValueError("fos_dmin_min requires at least one frame")
    r = min(t[0] for t in frame_rgb_triples)
    g = min(t[1] for t in frame_rgb_triples)
    b = min(t[2] for t in frame_rgb_triples)
    return r, g, b


def cov_numer_from_scaled(
    sum_a: int, sum_b: int, sum_ab_div32: int, n: int
) -> float:
    """Covariance numerator shape @ ``0x1028fe7f…`` (÷32-scaled products).

    Matches ``(A*B)/N - 32*P`` after ``fmul 32``, ``fsubp``, ``fchs``.
    Does **not** claim the full R² / slope closed form.
    """
    if n == 0:
        raise ZeroDivisionError("cov_numer_from_scaled: n == 0")
    return (sum_a * sum_b) / float(n) - 32.0 * sum_ab_div32


def round_msvc_104ffe44(x: float) -> int:
    """Approx of helper ``0x104ffe44`` (round-to-nearest → ``eax``).

    Prefer verifying against DLL fixtures; not claimed bit-identical
    for all edge cases.
    """
    return int(math.floor(x + 0.5)) if x >= 0 else int(math.ceil(x - 0.5))


def validate_calc_args(
    arg0: int,
    out_ptr_ok: bool,
    ptr_0c_ok: bool,
    ptr_10_ok: bool,
    ptr_14_ok: bool,
) -> int | None:
    """Return early error code or ``None`` if checks pass (entry fragment)."""
    if _i16(arg0) < 1:
        return ERR_ARG0
    if not out_ptr_ok:
        return ERR_NULL_OUT
    if not ptr_0c_ok:
        return ERR_NULL_0C
    if not ptr_14_ok:
        return ERR_NULL_14
    if not ptr_10_ok:
        return ERR_NULL_10
    return None


def main() -> None:
    print("FOS (base 0x10000000)")
    print(f"  Cap::analyze          {CAP_ANALYZE:#010x}")
    print(f"  Impl::analyze         {IMPL_ANALYZE:#010x}")
    print(f"  SbaCalcFosResults     {SBA_CALC_FOS_RESULTS:#010x}")
    print(f"  FOS_ANALYZE_PORTED={FOS_ANALYZE_PORTED}")
    print(f"  FOS_OPENING_TRANSFORM_PORTED={FOS_OPENING_TRANSFORM_PORTED}")
    print(f"  FOS_RESULTS_SIZE={FOS_RESULTS_SIZE:#x}")
    print(f"  opening axes (1000,1100,900) = {fos_opening_axes(1000, 1100, 900)}")
    print(f"  fos_dmin_min sample = {fos_dmin_min([(100, 200, 300), (90, 210, 250)])}")


if __name__ == "__main__":
    main()
