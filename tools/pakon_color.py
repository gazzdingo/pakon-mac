#!/usr/bin/env python3
"""Pakon colour-negative rendering, reimplemented for macOS.

Recovered from TLA.dll (the vendor's imaging library) by disassembly. The two
things everyone gets wrong about this pipeline:

  1. The so-called "inversion LUT" is a DENSITY LUT:

         LUT[i] = -S * log10(i / 16383)        with S = 3500

     Negative-to-positive inversion is INHERENT IN THE LOGARITHM. There is no
     separate invert step anywhere in the pipeline. This formula was recovered
     from the generator at TLA.dll:0x10013730 and reproduces the shipped
     _ClientColNegLut.txt exactly (see verify_lut()).

  2. The LUT is applied STRICTLY BEFORE the matrix, and the output is 12-BIT,
     not 16. The MMX kernel at TLA.dll:0x1001c563 does:
         and 0x3fff -> table lookup -> pmulhw 3x3 -> paddsw offset -> clamp
     with `paddusw 0x7003 / psubusw 0xF003` clamping to 0..4092. This matches
     the vendor UI string "Use Color Correction (12 bit RPD)".
     RPD = Reference Printing Density.

Per-pixel arithmetic:

    out[i] = ( SUM_c coeff[i][c] * LUT[raw_c] ) / 8 + offset[i]     clamped 0..4092

with coefficients stored as int16 = coeff * 8192. The 4th matrix column is the
film-base / orange-mask subtraction, in density code values.

Full vendor pipeline order, for context (this module implements steps 2 only):

    raw 14-bit planar RGB(+IR)
     -> DICE scratch removal (IR plane)
     -> [ density LUT -> 3x4 matrix -> clamp ]  => 12-bit RPD      <- HERE
     -> rotate
     -> roll-level scene balance (two-pass, NOT per-frame) -> sRGB
     -> scale
     -> combined CMS transform (input . saturation . bw/sepia . output)
     -> unsharp mask
     -> 16->8 bit -> save

Scene balance is deliberately NOT implemented here: it is a roll-level
two-pass analysis, so applying it per frame would not reproduce the look.

Usage:
    ./pakon_color.py verify --data-dir <ColorCorrection dir>
    ./pakon_color.py render raw.bin out.tiff --width 3000
"""
from __future__ import annotations

import argparse
import math
import os
import struct
import sys

LUT_SIZE = 16384          # 14-bit input
LUT_SCALE = 3500.0        # S, recovered from TLA.dll:0x10013730
RPD_MAX = 4092            # 12-bit clamp from the MMX kernel
COEFF_FIXED = 8192        # int16 = coeff * 8192


# --------------------------------------------------------------------------
# density LUT
# --------------------------------------------------------------------------

def build_density_lut(scale: float = LUT_SCALE, size: int = LUT_SIZE) -> list[float]:
    """LUT[i] = -scale * log10(i / (size-1)); LUT[0] clamped to the i=0 limit.

    The vendor stores index 0 as the maximum density (log10(0) is -inf), which
    lands at exactly (size-1) in the shipped table -- i.e. 16383.0.
    """
    top = size - 1
    lut = [float(top)]
    for i in range(1, size):
        lut.append(-scale * math.log10(i / top))
    return lut


def load_vendor_lut(path: str) -> list[float]:
    """Parse _ClientColNegLut.txt: 16384 lines of 'index<TAB>value'."""
    out = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 2:
                raise ValueError(f"unexpected line in {path}: {line!r}")
            out.append(float(parts[1]))
    return out


def load_vendor_matrix(path: str) -> list[list[float]]:
    """Parse _ClientColNegMat.txt: 'coeff_R_C: value' lines -> 3x4 matrix."""
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


# --------------------------------------------------------------------------
# the transform
# --------------------------------------------------------------------------

def quantise_matrix(matrix: list[list[float]]) -> tuple[list[list[int]], list[int]]:
    """Split a 3x4 float matrix into the vendor's fixed-point form.

    Columns 0..2 become int16 coefficients scaled by 8192; column 3 is the
    film-base/orange-mask offset, kept in density code values.
    """
    coeff = [[int(round(matrix[i][c] * COEFF_FIXED)) for c in range(3)]
             for i in range(3)]
    offset = [int(round(matrix[i][3])) for i in range(3)]
    return coeff, offset


def render_pixel(raw: tuple[int, int, int], lut: list[float],
                 coeff: list[list[int]], offset: list[int]) -> tuple[int, int, int]:
    """out[i] = (SUM_c coeff[i][c] * LUT[raw_c]) / 8 + offset[i], clamped."""
    d = [lut[raw[c] & (LUT_SIZE - 1)] for c in range(3)]
    out = []
    for i in range(3):
        acc = sum(coeff[i][c] * d[c] for c in range(3)) / COEFF_FIXED
        v = int(acc / 8.0 + offset[i])
        out.append(0 if v < 0 else (RPD_MAX if v > RPD_MAX else v))
    return tuple(out)


# --------------------------------------------------------------------------
# verification
# --------------------------------------------------------------------------

def verify_lut(data_dir: str) -> int:
    """Check the recovered formula against the vendor's shipped table."""
    path = os.path.join(data_dir, "_ClientColNegLut.txt")
    if not os.path.exists(path):
        print(f"missing {path}", file=sys.stderr)
        return 1
    vendor = load_vendor_lut(path)
    ours = build_density_lut()
    if len(vendor) != len(ours):
        print(f"length mismatch: vendor {len(vendor)}, ours {len(ours)}")
        return 1

    worst = 0.0
    worst_i = 0
    for i, (a, b) in enumerate(zip(vendor, ours)):
        diff = abs(a - b)
        if diff > worst:
            worst, worst_i = diff, i
    print(f"density LUT: {len(vendor)} entries compared")
    print(f"  formula: LUT[i] = -{LUT_SCALE:g} * log10(i/{LUT_SIZE - 1})")
    print(f"  worst absolute difference: {worst:.6f} at index {worst_i}")
    print(f"  vendor[{worst_i}]={vendor[worst_i]:.4f}  ours[{worst_i}]={ours[worst_i]:.4f}")
    for i in (0, 1, 2, 100, 1000, 8192, 16383):
        print(f"    i={i:<6} vendor={vendor[i]:>12.4f}  ours={ours[i]:>12.4f}")
    ok = worst < 0.01
    print(f"  => {'MATCH' if ok else 'MISMATCH'}")
    return 0 if ok else 1


def show_matrix(data_dir: str) -> int:
    path = os.path.join(data_dir, "_ClientColNegMat.txt")
    if not os.path.exists(path):
        print(f"missing {path}", file=sys.stderr)
        return 1
    m = load_vendor_matrix(path)
    coeff, offset = quantise_matrix(m)
    print("colour-negative 3x4 matrix (vendor template):")
    for i, name in enumerate("RGB"):
        row = "  ".join(f"{m[i][c]:+.5f}" for c in range(3))
        print(f"  {name}: [{row}]  offset {m[i][3]:+.5f}")
    print("\nvendor fixed-point form (int16 = coeff * 8192):")
    for i, name in enumerate("RGB"):
        row = "  ".join(f"{coeff[i][c]:+6d}" for c in range(3))
        print(f"  {name}: [{row}]  offset {offset[i]:+d}")
    print("\nThe offset column is the film-base / orange-mask subtraction,")
    print("in density code values. It is per-roll in a real scan: the API")
    print("exposes measured piDmin_R/G/B for exactly this purpose.")
    return 0


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def render_raw(in_path: str, out_path: str, width: int, data_dir: str) -> int:
    """Render interleaved 16-bit RGB triplets through the vendor transform."""
    lut = build_density_lut()
    mat_path = os.path.join(data_dir, "_ClientColNegMat.txt")
    if os.path.exists(mat_path):
        coeff, offset = quantise_matrix(load_vendor_matrix(mat_path))
    else:
        coeff = [[COEFF_FIXED, 0, 0], [0, COEFF_FIXED, 0], [0, 0, COEFF_FIXED]]
        offset = [0, 0, 0]
        print("no vendor matrix found; using identity", file=sys.stderr)

    data = open(in_path, 'rb').read()
    n = len(data) // 6           # 3 channels x 2 bytes
    words = struct.unpack(f'<{n * 3}H', data[:n * 6])
    height = n // width if width else 1
    print(f"{in_path}: {n} pixels, rendering {width}x{height}")

    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            i = (y * width + x) * 3
            r, g, b = render_pixel((words[i], words[i + 1], words[i + 2]),
                                   lut, coeff, offset)
            # scale 12-bit RPD to 16-bit for output
            for v in (r, g, b):
                row += struct.pack('<H', int(v * 65535 / RPD_MAX))
        rows.append(bytes(row))
    write_tiff(out_path, width, height, b"".join(rows))
    print(f"wrote {out_path}")
    return 0


def write_tiff(path: str, width: int, height: int, rgb16: bytes) -> None:
    """Minimal uncompressed 16-bit RGB TIFF, little-endian."""
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


DEFAULT_DATA_DIR = ("/Users/guy/Downloads/Pakon Update 2/fx35install/"
                    "program files/Pakon/F-X35 COM SERVER/Config/ColorCorrection")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify", help="check the LUT formula against vendor data")
    v.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    m = sub.add_parser("matrix", help="show the colour-negative matrix")
    m.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    r = sub.add_parser("render", help="render raw interleaved RGB16 to TIFF")
    r.add_argument("input")
    r.add_argument("output")
    r.add_argument("--width", type=int, required=True)
    r.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    args = ap.parse_args()

    if args.cmd == "verify":
        return verify_lut(args.data_dir)
    if args.cmd == "matrix":
        return show_matrix(args.data_dir)
    return render_raw(args.input, args.output, args.width, args.data_dir)


if __name__ == "__main__":
    sys.exit(main())
