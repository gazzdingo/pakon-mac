#!/usr/bin/env python3
"""Pakon stage-2 colour correction, for both scanner families.

READ THIS FIRST: there are two pipelines, and this scanner uses the second.

`TLA.dll`, `TLB.dll` and `TLC.dll` are three per-model builds of the same COM
server. `TLA` serves the F-235/F-335; **`TLB` serves the F-135**, which is the
machine this repo drives. They share every stage except stage 2, and stage 2 is
where all the colour arithmetic lives. See `docs/58-colour-pipeline.md`.

    F-235 / F-335  (TLA, `--model f235`)
        16384-entry log density LUT  ->  3x4 int16 matrix  ->  clamp 0..4092
        applied by the MMX kernel in PakonIMAu.dll:0x1001c470
        `PIColorCorrectColNegPlanarScan` / `...Save`

    F-135          (TLB, `--model f135`, the default)
        3x10 float32 second-order polynomial, per pixel, clamp 0..4095
        applied by TLB.dll:fcn.1000d880 itself -- PakonImau is not involved
        for colour negative at all

        out_k = c0*R + c1*G + c2*B
              + c3*R^2 + c4*G^2 + c5*B^2 + c6*RG + c7*RB + c8*GB
              + c9                                 clamp 0..4095, +0.5, truncate

TLB *builds* both density LUTs and then never applies them to colour-negative
data: `PIColorCorrectColNegPlanarScan/Save` are resolved by TLB but have no call
site. So on the F-135 the polynomial reads raw 14-bit LINEAR planes and its
12-bit output is what Ansel receives. Where -- or whether -- a log-density
conversion happens on this model is still [UNKNOWN] (`docs/58` §3.5, §15.1);
this module therefore assumes linear in, and says so, rather than inserting a
LUT the binary does not call.

The negative-to-positive inversion on the TLA path is inherent in the logarithm
(`LUT[i] = -S*log10(i/16383)`); there is no separate invert step in either
pipeline. On the F-135 path the inversion is folded into the fitted polynomial:
this unit's diagonal is positive (~0.28), so the polynomial alone does NOT
invert, which is a further reason to think a density conversion happens
somewhere downstream.

The coefficients are per-unit calibration, not per-film-stock. `defaults.ini`
selects no matrix and no LUT for any film (`docs/58` §9). Two sources, and they
do NOT agree to the last bit -- see `load_unit_matrix`.

Term order (c3..c8) and the float32/double split in `poly_pixel` were settled by
emulating the vendor's own instructions; run `pakon_color_golden.py term-order`
and `... random` to re-check them against TLB.dll.

Scene balance is deliberately not implemented here: it is a roll-level two-pass
analysis (`docs/58` §7), so applying it per frame would not reproduce the look.

Usage:
    ./pakon_color.py verify [--data-dir DIR]      six graded checkpoints
    ./pakon_color.py matrix [--model f135|f235]
    ./pakon_color.py render raw.bin out.tiff --width 3000 [--model f135]
"""
from __future__ import annotations

import argparse
import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

LUT_SIZE = 16384              # 14-bit input, direct-indexed, no interpolation

# Both CiConfigColorKodak constructors set member +0x20 = 3500 (TLA 0x1001263a,
# TLB 0x1000cd12). TLA's generator then multiplies by member +0x24 = 2; TLB's
# does not. So the *effective* scale differs by 2x between the models even
# though the stored constant is the same.
LUT_SCALE_BASE = 3500.0
LUT_SCALE = {"f135": 3500.0, "f235": 7000.0}
LUT_ZERO = {"f135": 16383, "f235": 32766}

# Stage-2 output clamp. The F-135 clamps in float to 0..4095 (TLB 0x1000da11);
# the TLA path clamps in MMX to 0..4092 (paddusw 0x7003 / psubusw 0xF003).
RPD_MAX = {"f135": 4095, "f235": 4092}

COEFF_FIXED = 8192            # TLA int16 coefficient scale, cfg+0x28
OFFSET_SCALE = 1              # TLA offset scale, cfg+0x2c

MODELS = ("f135", "f235")
DEFAULT_MODEL = "f135"

DEFAULT_DATA_DIR = ("/Users/guy/Downloads/Pakon Update 2/fx35install/"
                    "program files/Pakon/F-X35 COM SERVER/Config/ColorCorrection")
ANSEL_PROFILE_DIR = ("/Users/guy/Downloads/Pakon Update 2/fx35install/"
                     "program files/Pakon/F-X35 COM SERVER/anselinstalldir/"
                     "dataPathItems/profile")
EEPROM_PATH = os.path.join(REPO, "backups", "eeprom-i2c", "eeprom_52.bin")
REGISTRY_PATH = os.path.join(REPO, "research", "windows-registry",
                             "pakon_registry_full.txt")

# Offsets of the 3x10 float32 matrices inside the 0x52 calibration EEPROM.
# The page is a float array based at byte offset 1; NegMatrix is elements 9..38
# and PosMatrix elements 39..68. See `eeprom_matrix_offsets` for the evidence.
EEPROM_FLOAT_BASE = 1
EEPROM_NEG_INDEX = 9
EEPROM_POS_INDEX = 39


# --------------------------------------------------------------------------
# vendor arithmetic primitives
#
# Every one of these exists because a natural Python spelling of the same idea
# differs from the vendor by at least one LSB.
# --------------------------------------------------------------------------

def ftol(x: float) -> int:
    """MSVC `_ftol` (TLA 0x10051644, TLB 0x10048e9c): truncate toward zero.

    NOT `round()` and NOT `floor()`. `int()` on a Python float is exactly this.
    """
    return int(x)


def f32(x: float) -> float:
    """Round a Python double to float32, as `fstp dword [mem]` does."""
    return struct.unpack("<f", struct.pack("<f", x))[0]


def sat_sub_u16(a: int, b: int) -> int:
    """`psubusw` -- unsigned saturating subtract, floor at 0."""
    v = a - b
    return v if v > 0 else 0


def sat_add_u16(a: int, b: int) -> int:
    """`paddusw` -- unsigned saturating add, ceiling at 0xFFFF."""
    v = a + b
    return v if v < 0xFFFF else 0xFFFF


def add_w16(a: int, b: int) -> int:
    """`paddw` -- plain wrapping 16-bit add."""
    return (a + b) & 0xFFFF


def to_s16(v: int) -> int:
    """Reinterpret the low 16 bits as a signed int16."""
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def pmulhw(a: int, b: int) -> int:
    """`pmulhw` -- SIGNED multiply, keep the high word.

    `(int16)(((int32)a * (int32)b) >> 16)`. The shift is arithmetic, so this
    FLOORS toward negative infinity; it does not truncate toward zero. Summing
    the products and dividing once at the end is a different function.
    """
    return to_s16((to_s16(a) * to_s16(b)) >> 16)


def paddsw(a: int, b: int) -> int:
    """`paddsw` -- signed saturating 16-bit add."""
    v = a + b
    if v > 32767:
        return 32767
    if v < -32768:
        return -32768
    return v


# --------------------------------------------------------------------------
# stage 0 -- sensor correction, TLB.dll:fcn.100246d0
#
# Included because it is checkpoint 1 and because stage 2's input is defined by
# its output: 14-bit, 0..0x3FFF.
# --------------------------------------------------------------------------

def sensor_correct(raw: int, dark: int = 0, smear_q16: int = 0,
                   gain_q16: int = 0x4000, acc: int = 0) -> int:
    """One pixel of dark -> smear -> gain -> 14-bit clamp.

    `gain_q16` is the Q16 value, i.e. the stored Q18 gain after `shr edi, 2`
    (TLB 0x100247a6). The uncalibrated default is Q18 0x10000 -> Q16 0x4000,
    which is exactly `raw / 4`.

    `acc` is the smear accumulator: 4 * mean(corrected14 of the previous line),
    zero on the first line. `smear_q16` is `SmearC * (1 - i/(n-1))`.

    Note the input word's bit 0 is the line-start flag and `fcn.100246d0` never
    masks it (TLB 0x1002ff12 searches for it instead).
    """
    d = sat_sub_u16(raw, dark)                    # psubusw, 0x10024be6
    s = (acc * smear_q16) >> 16                   # pmulhuw, 0x10024c09
    d = sat_sub_u16(d, s)                         # psubusw, 0x10024c25
    v = (d * gain_q16) >> 16                      # pmulhuw, 0x10024c2e
    # paddusw 0xC000 ; psubw 0xC000 -- a saturating clamp to 0x3FFF, not a
    # subtraction. 0x10024c50.
    return add_w16(sat_add_u16(v, 0xC000), -0xC000 & 0xFFFF)


# --------------------------------------------------------------------------
# the density LUT  (docs/58 section 3)
# --------------------------------------------------------------------------

INV_16383 = 6.103888176768602e-05     # the double at TLA 0x100665f0 / TLB 0x1005cab0


def build_density_lut(model: str = DEFAULT_MODEL, size: int = LUT_SIZE):
    """The generated table, as int32 -- which is what the vendor stores.

    TLB (F-135), fcn.1000dfc0:
        lut[0] = 0x3FFF
        lut[i] = _ftol(-3500 * log10(i * 1/16383))
    TLA (F-235/335), fcn.10013730:
        lut[0] = 2 * 0x3FFF = 32766
        lut[i] = _ftol(-(2*3500) * log10(i * 1/16383))

    The 2x is applied BEFORE `_ftol`, so TLA's table is not simply twice TLB's:
    the two truncate independently and disagree at ~half the indices.

    A client `ClientColNegLut.txt` cannot change this. `bReadAllParams` installs
    the generated table unconditionally *after* any client LUT (TLA 0x10016e2a
    is reached from both branches), so only the client *matrix* survives.
    docs/58 section 3.3.
    """
    scale = LUT_SCALE[model]
    lut = [LUT_ZERO[model]]
    for i in range(1, size):
        lut.append(ftol(-scale * math.log10(i * INV_16383)))
    return lut


def lut_signed(lut):
    """What the MMX kernel actually sees: the low 16 bits, as signed int16.

    `movd` + `punpcklwd` at PakonIMAu 0x1001c586/0x1001c59e keep w0 only. TLA's
    table peaks at 32766, so it stays positive -- but only just, and any client
    scale that pushed `S_A*S_B` past 7787 would wrap the table negative.
    """
    return [to_s16(v) for v in lut]


def load_vendor_lut(path: str):
    """Parse `_ClientColNegLut.txt`: 16384 lines of 'index<TAB>value'.

    The index column is parsed and DISCARDED -- entries go in file order, not
    at dst[idx] (TLA 0x10013270). The data block is located by a literal
    strncmp against the six characters '0.0000', not by line number.
    """
    out = []
    started = False
    with open(path) as fh:
        for line in fh:
            if not started:
                if not line.startswith("0.0000"):
                    continue
                started = True
            parts = line.split()
            if len(parts) != 2:
                raise ValueError(f"unexpected line in {path}: {line!r}")
            out.append(float(parts[1]))
    return out


def convert_and_read_lut(values, scale: int):
    """`bConvertAndReadLut` (TLA 0x10013270, fn-ID 61) tail: dst[k] = _ftol(scale*val).

    `scale` is applied in SINGLE precision (`fstp dword [esp+0x38]`, 0x10013418)
    before `_ftol` truncates. The caller passes cfg+0x24 = 2 for colour negative.
    """
    return [ftol(f32(float(scale) * v)) for v in values]


# --------------------------------------------------------------------------
# stage 2, F-235/F-335 -- the 3x4 matrix and the MMX kernel (TLA path)
# --------------------------------------------------------------------------

def load_vendor_matrix(path: str):
    """Parse `_ClientColNegMat.txt`: 'coeff_<row>_<col>: value' -> 3x4."""
    m = [[0.0] * 4 for _ in range(3)]
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or ':' not in line:
                continue
            key, val = line.split(':', 1)
            key = key.strip()
            if not key.startswith('coeff_'):
                continue
            _, r, c = key.split('_')
            m[int(r)][int(c)] = float(val)
    return m


def quantise_matrix(matrix, coeff_scale: int = COEFF_FIXED,
                    offset_scale: int = OFFSET_SCALE, dmin=None):
    """`buildContext` -- TLA.dll:0x10012eb0. docs/58 section 5.2.

        dst = _ftol(scale * src + 0.5)

    `+0.5` then truncate-toward-zero is round-half-up for positives and
    ASYMMETRIC for negatives (trunc(-829.35) = -829, but trunc(-0.5+0.5)=0
    where round() would give 0 too -- they part company at exact halves and
    wherever the fraction lands below .5 on a negative). Do not substitute
    `round()`; `round()` is banker's rounding in Python and rounds away from
    zero in C, and neither is this.

    `dmin` is accepted because the vendor routine accepts it -- but all five
    call sites pass NULL (docs/58 section 5.3), so measured Dmin never reaches
    the colour matrix. It is consumed inside Ansel's scene context instead.
    """
    if dmin is None:
        dmin = (0.0, 0.0, 0.0)                    # 0x10012ec3-0x10012ee1
    cs = float(coeff_scale)
    os_ = float(offset_scale)
    coeff = [[ftol(cs * matrix[i][c] + 0.5) for c in range(3)] for i in range(3)]
    offset = [ftol((matrix[i][3] + dmin[i]) * os_ + 0.5) for i in range(3)]
    return coeff, offset


# The B&W context is built from the same 3x4 with the offset column perturbed.
# Doubles at TLA 0x10066f78 / 0x10066f70 / 0x10066f68.
BW_OFFSET_DELTA = (397.05, 12.08, -167.31)


def quantise_matrix_bw(matrix, coeff_scale: int = COEFF_FIXED,
                       offset_scale: int = OFFSET_SCALE):
    """`TLA.dll:0x100158f0` builds cfg+0x48 from cfg+0x200 with the offsets bumped."""
    bumped = [list(row) for row in matrix]
    for i in range(3):
        bumped[i][3] += BW_OFFSET_DELTA[i]
    return quantise_matrix(bumped, coeff_scale, offset_scale)


def mmx_clamp(v: int) -> int:
    """`paddw 0x8000 ; paddusw 0x7003 ; psubusw 0xF003` -> 0..4092."""
    v = add_w16(v, 0x8000)
    v = sat_add_u16(v, 0x7003)
    return sat_sub_u16(v, 0xF003)


def render_pixel_f235(raw, lut, coeff, offset):
    """One pixel of PakonIMAu.dll:0x1001c470 (scan) / 0x1001ca10 (save).

        out_k = clamp( SUM_c floor(c[k][c] * LUT[raw_c] / 65536) + offset_k, 0, 4092 )

    `pmulhw` floors EACH PRODUCT INDEPENDENTLY before they are summed. Summing
    first and dividing once is a different function -- see docs/58 section 14.4
    for the vector that separates them.

    Note `and 0x3fff` on the index (0x1001c57e): values above 14 bits FOLD,
    they are not clamped.

    The scalar tail at 0x1001c785 handles `(width mod 4) * height` samples in
    x87 with a different rounding path and can differ by 1 LSB from this. Not
    modelled here; a port that processes whole planes uses the MMX path for
    everything.
    """
    d = [lut[raw[c] & (LUT_SIZE - 1)] for c in range(3)]
    out = []
    for k in range(3):
        acc = 0
        for c in range(3):
            acc = paddsw(acc, pmulhw(coeff[k][c], d[c]))
        acc = paddsw(acc, offset[k])
        out.append(mmx_clamp(acc))
    return tuple(out)


# --------------------------------------------------------------------------
# stage 2, F-135 -- the 3x10 polynomial, TLB.dll:fcn.1000d880
# --------------------------------------------------------------------------

def eeprom_matrix_offsets():
    """Byte offsets of the two 3x10 float32 matrices in `eeprom_52.bin`.

    The page is a float32 array based at byte offset 1 (docs/35 section 3 found
    that alignment independently: 57/63 plausible values, best by a clear
    margin). Elements 9..38 are NegMatrix0..29 and 39..68 are PosMatrix0..29,
    which is what makes the three large constants land at 0x49 / 0x71 / 0x99 on
    exactly 40-byte centres -- they are each row's c9 -- and the three 0.25s at
    0x9d / 0xc9 / 0xf5 on 44-byte centres, which are PosMatrix 0, 11 and 22,
    the reversal diagonal.
    """
    neg = EEPROM_FLOAT_BASE + 4 * EEPROM_NEG_INDEX      # 0x25
    pos = EEPROM_FLOAT_BASE + 4 * EEPROM_POS_INDEX      # 0x9d
    return neg, pos


def load_matrix_eeprom(path: str = EEPROM_PATH, film_class: int = 1):
    """This unit's 3x10, read from the scanner's own calibration EEPROM.

    Returns (coeffs, note). PosMatrix runs past the end of the 256-byte page we
    have -- elements 24..29 are not present -- so they are zero-filled and the
    note says so. Element 22, the last diagonal entry, IS present, and every
    element from 12 to 23 reads exactly 0.0, so zero is the overwhelmingly
    likely value; it is still an assumption, not a read.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    neg_off, pos_off = eeprom_matrix_offsets()
    off = pos_off if film_class == 2 else neg_off
    avail = max(0, (len(data) - off) // 4)
    n = min(30, avail)
    vals = list(struct.unpack_from(f"<{n}f", data, off))
    note = ""
    if n < 30:
        note = (f"elements {n}..29 run past the end of the {len(data)}-byte "
                f"page and are assumed 0.0")
        vals += [0.0] * (30 - n)
    return vals, note


def load_matrix_registry(path: str = REGISTRY_PATH, film_class: int = 1):
    """The same 3x10 as recovered from the Windows hive.

    HKLM\\SOFTWARE\\Pakon\\TLB\\ColorKodak, NegMatrix0..29 / PosMatrix0..29 as
    REG_SZ decimal strings.

    These are the EEPROM floats printed with "%f" -- six decimal places -- so
    every coefficient below 1e-6 has been quantised to one significant figure or
    lost entirely (NegMatrix6 is the string "0.000000"; the EEPROM holds
    2.328e-07). The quadratic terms reach ~270 code values at full scale, so the
    rounding is worth 10-60 code values in the midtones. See `verify` checkpoint
    5. This is the vendor's own runtime source, so it reproduces what the
    machine did; the EEPROM reproduces what it was calibrated to.
    """
    key = "PosMatrix" if film_class == 2 else "NegMatrix"
    vals = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith(f'"{key}'):
                continue
            name, _, rest = line.partition("=")
            name = name.strip('"')
            if not name.startswith(key):
                continue
            idx = name[len(key):]
            if not idx.isdigit():
                continue
            _, _, val = rest.partition(":")
            vals[int(idx)] = float(val.strip())
    if len(vals) < 30:
        raise ValueError(f"{path}: found only {len(vals)} {key} values")
    return [vals[i] for i in range(30)]


def load_client_matrix_3x10(path: str):
    """`ClientColNegMat_3x10.txt` / `ClientColRevMat_3x10.txt`.

    TLB string at 0x1005cc00 / 0x1005cb98, reader FN_bReadMatrix_3x10 (fn-ID
    279). Neither ships in this install -- the templates carry a leading
    underscore and only the 3x4 forms are present -- so this parser follows the
    3x4 template's `coeff_<row>_<col>: value` convention and is [INFERRED].
    """
    m = [[0.0] * 10 for _ in range(3)]
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or ':' not in line:
                continue
            key, val = line.split(':', 1)
            key = key.strip()
            if not key.startswith('coeff_'):
                continue
            _, r, c = key.split('_')
            m[int(r)][int(c)] = float(val)
    return [v for row in m for v in row]


def load_unit_matrix(source: str = "auto", film_class: int = 1):
    """This unit's 30 coefficients, float32-rounded as the vendor stores them.

    source: 'eeprom' | 'registry' | 'auto'. 'auto' prefers the EEPROM, which is
    the scanner's own calibration and does not need a paired Windows install.
    """
    if source in ("auto", "eeprom") and os.path.exists(EEPROM_PATH):
        vals, _ = load_matrix_eeprom(film_class=film_class)
    elif source in ("auto", "registry"):
        vals = load_matrix_registry(film_class=film_class)
    else:
        raise FileNotFoundError(f"no coefficient source available for {source!r}")
    # The destination is 30 contiguous float32 at this+0x50, so whatever the
    # reader parsed into, this is what fcn.1000d880 multiplies by.
    return [f32(v) for v in vals]


POLY_MAX = 4095.0        # float32 at TLB 0x1005ca98
POLY_MIN = 0.0           # float32 at TLB 0x1005b864
POLY_HALF = 0.5          # float32 at TLB 0x1005ca9c


def poly_pixel(rgb, coeffs):
    """One pixel of TLB.dll:fcn.1000d880. docs/58 section 4.2.

        out_k = c0*R + c1*G + c2*B + c3*R^2 + c4*G^2 + c5*B^2
                                  + c6*RG  + c7*RB  + c8*GB + c9

    Two things here are not what a plain reading of the decompilation gives, and
    both were settled by emulating the function (`pakon_color_golden.py`):

    TERM ORDER. c7 is R*B and c8 is G*B, not the other way round. docs/58
    section 4.2 flagged its own reading as [INFERRED] and guessed c7=GB, c8=RB.
    Tracing the x87 stack gives RB then GB, and the six one-hot runs with
    (R,G,B) = (2,3,5) confirm it: c7 -> 10, c8 -> 15.

    PRECISION. The intermediates are NOT all float32. R^2 and G^2 stay on the
    x87 stack and keep full working precision; B^2, RG, RB and GB are spilled
    through `fstp dword [esp+0x30..0x3c]` (0x1000d96f..0x1000d987) and so are
    rounded to float32 first. Only the final accumulator is rounded to float32
    again, by `fstp dword [esp+0x10]` at 0x1000d9fc, and the two clamp compares
    read that float32 back. Rounding all six products to float32 -- or none of
    them -- disagrees with the vendor.

    The working precision is the x87 register precision, which under MSVC's
    default control word (0x027F) is 53-bit, i.e. exactly Python's float.
    """
    r, g, b = (int(v) & 0xFFFF for v in rgb)
    # 0x1000d95b-0x1000d96d: R*R and G*G are consumed from the stack.
    rr = float(r * r)
    gg = float(g * g)
    # 0x1000d96f-0x1000d987: these four go through memory as float32.
    bb = f32(float(b * b))
    rg = f32(float(r * g))
    rb = f32(float(r * b))
    gb = f32(float(g * b))

    out = []
    for k in range(3):
        c = coeffs[10 * k:10 * k + 10]
        acc = c[0] * r + c[1] * g          # fld/fmul/fld/fmul/faddp
        acc = acc + c[2] * b
        acc = acc + c[3] * rr
        acc = acc + c[4] * gg
        acc = acc + c[5] * bb
        acc = acc + c[6] * rg
        acc = acc + c[7] * rb
        acc = acc + c[8] * gb
        acc = acc + c[9]                   # 0x1000d9f3, the constant
        acc = f32(acc + POLY_HALF)         # 0x1000d9f6, then fstp dword
        if acc < POLY_MIN:                 # 0x1000da00
            acc = POLY_MIN
        elif acc > POLY_MAX:               # 0x1000da11
            acc = POLY_MAX
        out.append(ftol(acc))              # 0x1000da47, _ftol truncates
    return tuple(out)


# Film classes that reach the polynomial, from the case-index byte table at
# TLB 0x1000dbe4 and the jump table at 0x1000dbd8, read directly from the DLL:
#   filmClass 1, 4, 8 -> matrix at this+0x50   (colour negative, the two B&Ws)
#   filmClass 2       -> matrix at this+0xc8   (colour reversal)
#   filmClass 3,5,6,7 -> logged as error 0xf, buffer untouched
# docs/58 section 4.1 lists "case 1, 8"; case 4 is also present, exactly as the
# same document's section 5.1 corrects docs/11 for the TLA path.
POLY_CLASSES_COLNEG = (1, 4, 8)
POLY_CLASS_COLREV = 2


def poly_plane(planes, coeffs, film_class: int = 1):
    """Apply the polynomial in place over three equal-length planar lists."""
    if film_class not in POLY_CLASSES_COLNEG and film_class != POLY_CLASS_COLREV:
        return planes                      # error 0xf, buffer left alone
    r, g, b = planes
    for i in range(len(r)):
        r[i], g[i], b[i] = poly_pixel((r[i], g[i], b[i]), coeffs)
    return planes


# --------------------------------------------------------------------------
# ICC mft1/mft2 evaluation  (docs/58 section 6.1)
# --------------------------------------------------------------------------

def _table_lookup(table, v: float) -> float:
    """1-D table with linear interpolation at p = v*(n-1). Returns 0..1."""
    n = len(table)
    if n == 1:
        return table[0] / 65535.0
    p = min(max(v, 0.0), 1.0) * (n - 1)
    i = int(p)
    if i >= n - 1:
        return table[n - 1] / 65535.0
    f = p - i
    return (table[i] * (1.0 - f) + table[i + 1] * f) / 65535.0


def mft_eval(m, values):
    """Evaluate an ICC lut16Type/lut8Type A2B0 (or B2A0). Inputs/outputs 0..1.

    Order: input tables -> multilinear over the 2^i surrounding CLUT nodes ->
    output tables. The 3x3 matrix is skipped: it applies only when the input
    space is XYZ and it is the exact identity in all 76 profiles here.

    CLUT node address is channel 0 SLOWEST, last channel fastest:
        clut[(((c0*g + c1)*g + c2) * out_ch) + k]
    which is the single most common way to get an ICC CLUT wrong.
    """
    g = m.grid
    n_in = m.in_ch
    coords = []
    for c in range(n_in):
        t = _table_lookup(m.in_tables[c], values[c])
        q = min(max(t, 0.0), 1.0) * (g - 1)
        i = int(q)
        if i >= g - 1:
            i, fr = g - 2, 1.0
        else:
            fr = q - i
        coords.append((i, fr))

    acc = [0.0] * m.out_ch
    for corner in range(1 << n_in):
        w = 1.0
        idx = 0
        for c in range(n_in):
            i, fr = coords[c]
            if corner >> (n_in - 1 - c) & 1:
                w *= fr
                idx = idx * g + (i + 1)
            else:
                w *= (1.0 - fr)
                idx = idx * g + i
        if w == 0.0:
            continue
        base = idx * m.out_ch
        for k in range(m.out_ch):
            acc[k] += w * m.clut[base + k]

    return [_table_lookup(m.out_tables[k], acc[k] / 65535.0)
            for k in range(m.out_ch)]


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def render_raw(in_path: str, out_path: str, width: int, data_dir: str,
               model: str = DEFAULT_MODEL, source: str = "auto") -> int:
    """Render interleaved 16-bit RGB triplets through stage 2 of `model`."""
    print(f"model: {model} "
          f"({'F-135, TLB.dll 3x10 polynomial' if model == 'f135' else 'F-235/F-335, TLA.dll LUT + 3x4 matrix'})")

    if model == "f135":
        coeffs = load_unit_matrix(source)
        print(f"coefficients: {source} "
              f"(diagonal {coeffs[0]:.6f} {coeffs[11]:.6f} {coeffs[22]:.6f})")
        stage2 = lambda px: poly_pixel(px, coeffs)          # noqa: E731
    else:
        # The generated table, always -- a client LUT cannot survive
        # bReadAllParams (docs/58 section 3.3).
        lut = lut_signed(build_density_lut(model))
        mat_path = os.path.join(data_dir, "_ClientColNegMat.txt")
        if os.path.exists(mat_path):
            coeff, offset = quantise_matrix(load_vendor_matrix(mat_path))
            print(f"matrix: {mat_path}")
        else:
            coeff = [[COEFF_FIXED, 0, 0], [0, COEFF_FIXED, 0], [0, 0, COEFF_FIXED]]
            offset = [0, 0, 0]
            print("no vendor matrix found; using identity", file=sys.stderr)
        stage2 = lambda px: render_pixel_f235(px, lut, coeff, offset)   # noqa: E731

    rpd_max = RPD_MAX[model]
    data = open(in_path, 'rb').read()
    n = len(data) // 6
    words = struct.unpack(f'<{n * 3}H', data[:n * 6])
    height = n // width if width else 1
    print(f"{in_path}: {n} pixels, rendering {width}x{height}")

    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            i = (y * width + x) * 3
            for v in stage2((words[i], words[i + 1], words[i + 2])):
                # OUR choice, not the vendor's: the vendor takes 12-bit RPD on
                # into Ansel and leaves at 8 bits. This linear stretch to 16-bit
                # is the honest way to expose the last stage that still carries
                # more than 8 bits of signal (docs/58 section 11).
                row += struct.pack('<H', v * 65535 // rpd_max)
        rows.append(bytes(row))
    write_tiff(out_path, width, height, b"".join(rows))
    print(f"wrote {out_path}")
    return 0


def write_tiff(path: str, width: int, height: int, rgb16: bytes) -> None:
    """Minimal uncompressed 16-bit RGB TIFF, little-endian.

    Untagged, like the vendor's own output -- there is no ICC-embed path in
    TLA.dll's save (docs/58 section 10).
    """
    entries = [
        (256, 3, 1, width),        # ImageWidth
        (257, 3, 1, height),       # ImageLength
        (258, 3, 3, 0),            # BitsPerSample -> offset, filled below
        (259, 3, 1, 1),            # Compression = none
        (262, 3, 1, 2),            # Photometric = RGB
        (273, 4, 1, 0),            # StripOffsets -> filled below
        (277, 3, 1, 3),            # SamplesPerPixel
        (278, 3, 1, height),       # RowsPerStrip
        (279, 4, 1, len(rgb16)),   # StripByteCounts
    ]
    header = b'II\x2a\x00' + struct.pack('<I', 8)
    ifd_size = 2 + len(entries) * 12 + 4
    bits_off = 8 + ifd_size
    data_off = bits_off + 6
    out = bytearray(header)
    out += struct.pack('<H', len(entries))
    for tag, typ, cnt, val in entries:
        if tag == 258:
            val = bits_off
        elif tag == 273:
            val = data_off
        out += struct.pack('<HHI', tag, typ, cnt)
        out += struct.pack('<I', val) if not (typ == 3 and cnt == 1) \
            else struct.pack('<HH', val, 0)
    out += struct.pack('<I', 0)
    out += struct.pack('<HHH', 16, 16, 16)
    out += rgb16
    open(path, 'wb').write(bytes(out))


def show_matrix(data_dir: str, model: str, source: str) -> int:
    if model == "f135":
        for film_class, label in ((1, "NegMatrix (colour negative, film classes 1/4/8)"),
                                  (2, "PosMatrix (colour reversal, film class 2)")):
            try:
                coeffs = load_unit_matrix(source, film_class=film_class)
            except Exception as exc:
                print(f"{label}: unavailable ({exc})")
                continue
            print(f"\n{label} -- this unit's 3x10, source {source}")
            names = ["R", "G", "B", "R2", "G2", "B2", "RG", "RB", "GB", "const"]
            print("        " + "".join(f"{n:>12}" for n in names))
            for k, ch in enumerate("RGB"):
                row = coeffs[10 * k:10 * k + 10]
                print(f"  out {ch}: " + "".join(f"{v:>12.8g}" for v in row))
        print("\nThe diagonal ~0.28 maps 14-bit onto ~0..4700, which the 0..4095")
        print("clamp truncates. The constants are a per-channel pedestal. The")
        print("three diagonal values differ by ~5%, which is the signature of a")
        print("per-unit fit rather than a film-stock constant.")
        return 0

    path = os.path.join(data_dir, "_ClientColNegMat.txt")
    if not os.path.exists(path):
        print(f"missing {path}", file=sys.stderr)
        return 1
    m = load_vendor_matrix(path)
    coeff, offset = quantise_matrix(m)
    _, offset_bw = quantise_matrix_bw(m)
    print("colour-negative 3x4 matrix (vendor template, F-235/F-335):")
    for i, name in enumerate("RGB"):
        row = "  ".join(f"{m[i][c]:+.5f}" for c in range(3))
        print(f"  {name}: [{row}]  offset {m[i][3]:+.5f}")
    print("\nquantised int16 context (cs=8192, os=1), _ftol(cs*c + 0.5):")
    for i, name in enumerate("RGB"):
        row = "  ".join(f"{coeff[i][c]:+6d}" for c in range(3))
        print(f"  {name}: [{row}]  offset {offset[i]:+d}")
    print(f"\nblack-and-white context offsets: {offset_bw}")
    print("\nMeasured Dmin never modifies this matrix -- all five call sites of")
    print("buildContext pass NULL (docs/58 section 5.3). Dmin is consumed inside")
    print("Ansel's scene context instead.")
    return 0


# --------------------------------------------------------------------------
# verification -- docs/58 section 14, six graded checkpoints
# --------------------------------------------------------------------------

class Check:
    def __init__(self):
        self.results = []

    def case(self, name, got, want):
        ok = got == want
        self.results.append(ok)
        mark = "ok  " if ok else "FAIL"
        if ok:
            print(f"    {mark} {name}: {got}")
        else:
            print(f"    {mark} {name}: got {got}, want {want}")
        return ok

    def note(self, text):
        print(f"         {text}")

    @property
    def passed(self):
        return all(self.results)


def _checkpoint(n, title):
    print(f"\n[{n}] {title}")


def verify(data_dir: str, profile_dir: str) -> int:
    verdicts = {}

    # ---- 1: stage 0, sensor correction -------------------------------------
    _checkpoint(1, "stage 0 sensor correction  (docs/58 section 14.1)")
    c = Check()
    for raw, want in ((0xFFFE, 0x3FFF), (0x8000, 0x2000), (4, 1), (3, 0)):
        c.case(f"gain=0x4000 raw={raw:#06x}", sensor_correct(raw), want)
    c.note("raw=3 -> 1 would mean you rounded instead of truncating")
    c.case("gain=0xFFFF raw=0x4001 (clamp)",
           sensor_correct(0x4001, gain_q16=0xFFFF), 0x3FFF)
    c.case("dark and smear both subtract",
           sensor_correct(1000, dark=100, smear_q16=0x8000, acc=200,
                          gain_q16=0x10000), 800)
    verdicts[1] = c.passed

    # ---- 2: the integer density LUT ----------------------------------------
    _checkpoint(2, "density LUT, as an integer table  (docs/58 section 14.2)")
    c = Check()
    tlb = build_density_lut("f135")
    tla = build_density_lut("f235")
    for i, want in ((0, 16383), (1, 14750), (2, 13696), (3, 13080), (10, 11250),
                    (100, 7750), (1000, 4250), (4096, 2107), (8192, 1053),
                    (16382, 0), (16383, 0)):
        c.case(f"TLB[{i}]", tlb[i], want)
    for i, want in ((0, 32766), (1, 29500), (4096, 4214), (16382, 0)):
        c.case(f"TLA[{i}]", tla[i], want)
    diff = sum(1 for i in range(LUT_SIZE) if tla[i] != 2 * tlb[i])
    ok = diff > 0
    c.results.append(ok)
    print(f"    {'ok  ' if ok else 'FAIL'} indices where TLA[i] != 2*TLB[i]: {diff}")
    c.note("zero would mean you multiplied after truncating instead of before")

    path = os.path.join(data_dir, "_ClientColNegLut.txt")
    if os.path.exists(path):
        vendor = load_vendor_lut(path)
        c.case("_ClientColNegLut.txt line count", len(vendor), LUT_SIZE)
        # The shipped template is TLB's table exactly, to <=5.0e-05.
        worst = max(abs(v - t) for v, t in
                    zip(vendor[1:], (-3500.0 * math.log10(i * INV_16383)
                                     for i in range(1, LUT_SIZE))))
        ok = worst <= 5.0e-05
        c.results.append(ok)
        print(f"    {'ok  ' if ok else 'FAIL'} worst |file - TLB formula|: {worst:.6f}")
        # The file is a "%.4f" rendering, so it cannot always round-trip to the
        # generated integers: where the true value sits within 5e-05 BELOW an
        # integer, "%.4f" rounds up across it and _ftol then keeps the higher
        # integer. Exactly two indices do this. The generated table is the one
        # that matters -- bLoadDefaultLut overwrites any client LUT (docs/58
        # section 3.3), so the text file never reaches the kernel.
        mism = [i for i in range(1, LUT_SIZE) if ftol(vendor[i]) != tlb[i]]
        c.case("indices where _ftol(file) != generated TLB table", mism,
               [295, 2950])
        for i in mism:
            c.case(f"  file[{i}] rounded up across an integer",
                   (vendor[i], tlb[i]), (float(tlb[i] + 1), tlb[i]))
        c.note("this is the same 5.0e-05 the old `verify` reported as a formula "
               "residual: it is the text format's half-ULP, not an error")
        # And the scale-2 parse that TLA applies to a client file.
        scaled = convert_and_read_lut(vendor[:8], 2)
        c.case("bConvertAndReadLut(scale=2)[1]", scaled[1], ftol(f32(2.0 * vendor[1])))
    else:
        c.note(f"skipped file comparison: no {path}")
    verdicts[2] = c.passed

    # ---- 3: matrix quantisation (TLA path) ---------------------------------
    _checkpoint(3, "matrix quantisation, F-235/F-335  (docs/58 section 14.3)")
    c = Check()
    path = os.path.join(data_dir, "_ClientColNegMat.txt")
    if os.path.exists(path):
        m = load_vendor_matrix(path)
        coeff, offset = quantise_matrix(m)
        c.case("coeff", coeff, [[9165, -829, -94], [-1645, 9018, 958],
                                [-954, 396, 8870]])
        c.case("offset", offset, [-82, -586, -707])
        c.note("-830 for c01 would mean floor(); -83 for the R offset would "
               "mean rounding away from zero")
        _, offset_bw = quantise_matrix_bw(m)
        c.case("offset_bw", offset_bw, [314, -574, -874])
        c.case("dmin never reaches the matrix",
               quantise_matrix(m, dmin=(50.0, 50.0, 50.0))[1] != offset, True)
        c.note("(that case shows dmin WOULD change it -- the point is that all "
               "five vendor call sites pass NULL)")
    else:
        c.note(f"skipped: no {path}")
        verdicts[3] = None
    if verdicts.get(3, True) is not None:
        verdicts[3] = c.passed

    # ---- 4: the MMX kernel -------------------------------------------------
    _checkpoint(4, "MMX kernel floor semantics, F-235/F-335  (docs/58 section 14.4)")
    c = Check()
    ident = [[COEFF_FIXED, 0, 0], [0, COEFF_FIXED, 0], [0, 0, COEFF_FIXED]]
    zero = [0, 0, 0]
    for raw, lutv, want in ((0, 32766, 4092), (1, 29500, 3687), (16, 21071, 2633),
                            (4096, 4214, 526), (16383, 0, 0)):
        c.case(f"raw={raw} LUT={lutv}",
               render_pixel_f235((raw, raw, raw), tla, ident, zero)[0], want)
    c.note("4095 would mean you skipped the 0x7003/0xF003 clamp; 3688 would "
           "mean you rounded")
    # The vector that separates per-product floor from sum-then-divide.
    sep = [[16384, 16384, 0], [0, 0, 0], [0, 0, 0]]
    lut3 = [3] * LUT_SIZE
    got = render_pixel_f235((0, 0, 0), lut3, sep, zero)[0]
    c.case("c=[16384,16384,0] with L=3 (per-product floor)", got, 0)
    c.note("sum-then-divide gives floor(98304/65536) = 1 here; the vendor "
           "gives floor(49152/65536) twice = 0")
    c.case("pmulhw floors negatives toward -inf", pmulhw(-1, 1), -1)
    verdicts[4] = c.passed

    # ---- 5: the 3x10 polynomial (F-135) ------------------------------------
    _checkpoint(5, "the 3x10 polynomial, F-135  (docs/58 section 14.5)")
    c = Check()
    try:
        eeprom = load_unit_matrix("eeprom")
        registry = load_unit_matrix("registry")
    except Exception as exc:
        c.note(f"skipped: {exc}")
        verdicts[5] = None
        eeprom = registry = None
    if eeprom is not None:
        # Endpoints are independent of coefficient precision.
        c.case("R=G=B=0     (the constants c9, +0.5, truncated)",
               list(poly_pixel((0, 0, 0), eeprom)), [160, 445, 636])
        c.case("R=G=B=16383 (all three clamp)",
               list(poly_pixel((16383, 16383, 16383), eeprom)),
               [4095, 4095, 4095])
        # docs/58's midtone rows were computed from the 6-dp registry strings.
        c.case("R=G=B=4000, registry coefficients",
               list(poly_pixel((4000, 4000, 4000), registry)), [1304, 1585, 1760])
        c.case("R=G=B=8000, registry coefficients",
               list(poly_pixel((8000, 8000, 8000), registry)), [2417, 2853, 2821])
        # ...and the EEPROM's fuller precision moves them materially.
        c.case("R=G=B=4000, EEPROM coefficients",
               list(poly_pixel((4000, 4000, 4000), eeprom)), [1290, 1571, 1742])
        c.case("R=G=B=8000, EEPROM coefficients",
               list(poly_pixel((8000, 8000, 8000), eeprom)), [2360, 2798, 2747])
        c.note("the two sources differ by 14-57 code values in the midtones; "
               "that is the 1e-6 quadratic terms being printed as '%f'")
        # Term order: one-hot, inputs (2,3,5), per docs/58 section 14.5.
        onehot = []
        for k in range(3, 9):
            cf = [0.0] * 30
            cf[k] = 1.0
            onehot.append(poly_pixel((2, 3, 5), cf)[0])
        c.case("one-hot c3..c8 with (R,G,B)=(2,3,5)", onehot, [4, 9, 25, 6, 10, 15])
        c.note("4/9/25/6/10/15 = R2 G2 B2 RG RB GB -- confirmed against "
               "TLB.dll under Unicorn, see pakon_color_golden.py term-order")
        # Colour reversal is a plain 14->12 bit shift before PakonImau.
        rev = load_unit_matrix("eeprom", film_class=2)
        c.case("PosMatrix is 0.25 on the diagonal",
               [rev[0], rev[11], rev[22]], [0.25, 0.25, 0.25])
        c.case("colour reversal R=G=B=16380 -> 14->12 bit shift",
               list(poly_pixel((16380, 16380, 16380), rev)), [4095, 4095, 4095])
        c.case("colour reversal R=G=B=4000",
               list(poly_pixel((4000, 4000, 4000), rev)), [1000, 1000, 1000])
        verdicts[5] = c.passed

    # ---- 6: ICC CLUT addressing --------------------------------------------
    _checkpoint(6, "ICC mft2 evaluation and CLUT addressing  (docs/58 section 14.6)")
    c = Check()
    try:
        sys.path.insert(0, HERE)
        from pakon_profile import IccProfile
    except ImportError as exc:
        c.note(f"skipped: cannot import pakon_profile ({exc})")
        verdicts[6] = None
        IccProfile = None
    unity_path = os.path.join(data_dir, "unity.pf")
    rpd2pcs = os.path.join(profile_dir, "Rpd2Pcs_HR200_QS_v5s10.pf")
    if IccProfile is not None and os.path.exists(unity_path):
        u = IccProfile.load(unity_path).parse_mft2("A2B0")
        c.case("unity.pf grid", u.grid, 19)
        c.case("unity.pf CLUT[9,9,9]", list(u.clut_node(9, 9, 9)),
               [32640, 32768, 32768])
        c.note("(32768, 32768, 32768) would mean L is encoded 0..0xFFFF "
               "instead of the v2 legacy 0..0xFF00")
        # Bit-exact identity: encode Lab the v2 legacy way, round trip.
        worst = 0
        for lab in ((0, 0, 0), (50.0, 0.0, 0.0), (100.0, 0.0, 0.0),
                    (25.0, -60.0, 40.0), (75.0, 30.0, -90.0), (12.5, 100.0, 100.0)):
            enc = (lab[0] / 100.0 * 65280, (lab[1] + 128.0) / 255.0 * 65535,
                   (lab[2] + 128.0) / 255.0 * 65535)
            got = mft_eval(u, [enc[0] / 65535.0, enc[1] / 65535.0,
                               enc[2] / 65535.0])
            for k in range(3):
                worst = max(worst, abs(got[k] * 65535.0 - enc[k]))
        ok = worst <= 1.0
        c.results.append(ok)
        print(f"    {'ok  ' if ok else 'FAIL'} unity.pf round trip, worst error "
              f"{worst:.3f} of 65535 (<= 1 LSB)")
    else:
        c.note(f"skipped unity.pf: no {unity_path}")
    if IccProfile is not None and os.path.exists(rpd2pcs):
        r = IccProfile.load(rpd2pcs).parse_mft2("A2B0")
        c.case("Rpd2Pcs grid", r.grid, 31)
        c.case("Rpd2Pcs CLUT[0,0,0]", list(r.clut_node(0, 0, 0)), [0, 32902, 32900])
        c.case("Rpd2Pcs CLUT[15,15,15]", list(r.clut_node(15, 15, 15)),
               [27406, 32902, 32902])
        c.case("Rpd2Pcs CLUT[30,30,30]", list(r.clut_node(30, 30, 30)),
               [65535, 32902, 32902])
        swapped = r.clut_node(30, 0, 0) == r.clut_node(0, 0, 30)
        c.case("CLUT[30,0,0] and CLUT[0,0,30] are distinct", not swapped, True)
        c.note(f"CLUT[30,0,0]={r.clut_node(30, 0, 0)} "
               f"CLUT[0,0,30]={r.clut_node(0, 0, 30)}; equal or swapped values "
               "would mean the node stride order is reversed")
        # The input tables clip above RPD code 3000.
        c.case("input table clips above RPD code 3000",
               [r.in_tables[0][3000], r.in_tables[0][3500], r.in_tables[0][4095]],
               [65535, 65535, 65535])
    else:
        c.note(f"skipped Rpd2Pcs: no {rpd2pcs}")
    if verdicts.get(6, True) is not None:
        verdicts[6] = c.passed

    # ---- summary -----------------------------------------------------------
    titles = {
        1: "stage 0 sensor clamp",
        2: "integer density LUT tables",
        3: "matrix quantisation (TLA)",
        4: "MMX floor semantics (TLA)",
        5: "3x10 polynomial (F-135)",
        6: "ICC CLUT addressing",
    }
    print("\n" + "=" * 62)
    print("checkpoint summary")
    failed = 0
    for n in sorted(titles):
        v = verdicts.get(n)
        label = "PASS" if v else ("SKIP" if v is None else "FAIL")
        failed += (v is False)
        print(f"  [{n}] {label}  {titles[n]}")
    print("=" * 62)
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("verify", help="run the six graded checkpoints")
    v.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    v.add_argument("--profile-dir", default=ANSEL_PROFILE_DIR)

    m = sub.add_parser("matrix", help="show this model's stage-2 coefficients")
    m.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    m.add_argument("--model", choices=MODELS, default=DEFAULT_MODEL)
    m.add_argument("--source", choices=("auto", "eeprom", "registry"),
                   default="auto", help="f135 coefficient source")

    r = sub.add_parser("render", help="render raw interleaved RGB16 to TIFF")
    r.add_argument("input")
    r.add_argument("output")
    r.add_argument("--width", type=int, required=True)
    r.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    r.add_argument("--model", choices=MODELS, default=DEFAULT_MODEL)
    r.add_argument("--source", choices=("auto", "eeprom", "registry"),
                   default="auto")

    args = ap.parse_args()
    if args.cmd == "verify":
        return verify(args.data_dir, args.profile_dir)
    if args.cmd == "matrix":
        return show_matrix(args.data_dir, args.model, args.source)
    return render_raw(args.input, args.output, args.width, args.data_dir,
                      args.model, args.source)


if __name__ == "__main__":
    sys.exit(main())
