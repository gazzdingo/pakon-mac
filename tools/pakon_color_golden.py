#!/usr/bin/env python3
"""Golden reference for the F-135's stage-2 colour polynomial.

Emulates `TLB.dll:fcn.1000d880` under Unicorn so that `pakon_color.py`'s pure
Python implementation can be checked against the vendor's own instructions
rather than against a reading of them. Same pattern as `tools/ansel/*_golden.py`.

Two questions this exists to answer, both flagged [INFERRED] in
`docs/58-colour-pipeline.md` §4.2 and §14.5:

  1. Which of the six quadratic terms each of c3..c8 multiplies. Settled by six
     runs with a one-hot coefficient array and inputs (R,G,B) = (2,3,5): the
     outputs 4 / 9 / 25 / 6 / 15 / 10 identify R^2 / G^2 / B^2 / RG / GB / RB
     uniquely.
  2. Whether the intermediates are float32 throughout. They are not -- see
     `pakon_color.poly_pixel`. The `random` subcommand is what proves it: it
     fuzzes the Python model against the emulator and reports any mismatch.

Requires the vendor DLL, which is not in the repo:
    python3 -m pip install unicorn pefile
    ./pakon_color_golden.py term-order
    ./pakon_color_golden.py vectors
    ./pakon_color_golden.py random --count 4000
"""
from __future__ import annotations

import argparse
import os
import random
import struct
import sys

try:
    import pefile
    from unicorn import (Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_MEM_UNMAPPED,
                         UcError)
    from unicorn.x86_const import (UC_X86_REG_ESP, UC_X86_REG_EBP,
                                   UC_X86_REG_ECX)
except ImportError:                                            # pragma: no cover
    sys.exit("need: python3 -m pip install unicorn pefile")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pakon_color                                             # noqa: E402

DLL = ("/Users/guy/Downloads/Pakon Update 2/fx35install/program files/Pakon/"
       "F-X35 COM SERVER/TLB.dll")
DLL_MD5 = "193d9b2ce0a4b77ae9b78262bd06c0fc"

IMAGE_BASE = 0x10000000
COLOR_CORRECT = 0x1000D880      # fcn.1000d880, the 3x10 polynomial
MATRIX_COLNEG = 0x50            # this + 0x50, film classes 1/4/8
MATRIX_COLREV = 0xC8            # this + 0xc8, film class 2

STACK_BASE = 0x70000000
STACK_SIZE = 0x00100000
THIS_OBJ = 0x61000000
IMAGE_BUF = 0x62000000
BUF_SIZE = 0x00100000
STOP = 0x7FFFF000

# MSVC's CRT default: round to nearest, 53-bit (double) precision control.
# Not 64-bit extended -- that difference is observable in the last bit.
FPU_CONTROL_WORD = 0x027F


class PolyGolden:
    """Runs the vendor's own colour-correction function on chosen pixels."""

    def __init__(self, dll: str = DLL):
        self.pe = pefile.PE(dll, fast_load=True)
        self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        size = (self.pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF
        self.uc.mem_map(IMAGE_BASE, size)
        self.uc.mem_write(IMAGE_BASE,
                          self.pe.get_memory_mapped_image(ImageBase=IMAGE_BASE))
        for base, sz in ((STACK_BASE, STACK_SIZE), (THIS_OBJ, 0x10000),
                         (IMAGE_BUF, BUF_SIZE), (STOP & ~0xFFF, 0x1000),
                         (0, 0x1000)):
            try:
                self.uc.mem_map(base, (sz + 0xFFF) & ~0xFFF)
            except UcError:
                pass
        self.uc.hook_add(UC_HOOK_MEM_UNMAPPED, self._on_unmapped)

    @staticmethod
    def _on_unmapped(uc, access, address, size, value, user):
        try:
            uc.mem_map(address & ~0xFFF, 0x1000)
        except UcError:
            pass
        return True

    def _set_fpu_control_word(self) -> None:
        """Execute `fldcw` in-guest; Unicorn's default is 64-bit extended."""
        word_at = STACK_BASE + 0x100
        code_at = STACK_BASE + 0x200
        self.uc.mem_write(word_at, struct.pack("<H", FPU_CONTROL_WORD))
        code = b"\xd9\x2d" + struct.pack("<I", word_at)      # fldcw [word_at]
        self.uc.mem_write(code_at, code)
        self.uc.emu_start(code_at, code_at + len(code), count=1)

    def run(self, coeffs, pixels, film_class: int = 1):
        """coeffs: 30 floats, row-major 3x10. pixels: [(r,g,b), ...] 14-bit."""
        if len(coeffs) != 30:
            raise ValueError("need exactly 30 coefficients")
        off = MATRIX_COLREV if film_class == 2 else MATRIX_COLNEG
        self.uc.mem_write(THIS_OBJ + off, struct.pack("<30f", *coeffs))

        n = len(pixels)
        planes = [bytearray(), bytearray(), bytearray()]
        for px in pixels:
            for c in range(3):
                planes[c] += struct.pack("<H", px[c] & 0xFFFF)
        self.uc.mem_write(IMAGE_BUF, bytes(planes[0] + planes[1] + planes[2]))

        # thiscall, ret 0x14: (unused, image, filmClass, width, height)
        args = (0, IMAGE_BUF, film_class, n, 1)
        esp = STACK_BASE + STACK_SIZE - 0x2000
        self._set_fpu_control_word()
        # arg1 lowest: [ret][arg1][arg2]... -- not reversed
        payload = b"".join(struct.pack("<I", a) for a in args)
        esp -= len(payload)
        self.uc.mem_write(esp, payload)
        esp -= 4
        self.uc.mem_write(esp, struct.pack("<I", STOP))
        self.uc.reg_write(UC_X86_REG_ESP, esp)
        self.uc.reg_write(UC_X86_REG_EBP, esp)
        self.uc.reg_write(UC_X86_REG_ECX, THIS_OBJ)
        self.uc.emu_start(COLOR_CORRECT, STOP, count=40_000_000)

        raw = self.uc.mem_read(IMAGE_BUF, n * 6)
        out = []
        for i in range(n):
            out.append(tuple(
                struct.unpack_from("<H", raw, (c * n + i) * 2)[0]
                for c in range(3)))
        return out


# --------------------------------------------------------------------------
# subcommands
# --------------------------------------------------------------------------

# docs/58 §14.5: with R=2, G=3, B=5 each quadratic term has a distinct value.
PRODUCT_OF = {4: "R*R", 9: "G*G", 25: "B*B", 6: "R*G", 15: "G*B", 10: "R*B"}


def cmd_term_order(g: PolyGolden) -> int:
    """Six one-hot runs settle the permutation of coefficients 3..8."""
    print("driving fcn.1000d880 with a one-hot coefficient array, "
          "inputs R=2 G=3 B=5\n")
    print("  c[k]   raw out   product   term")
    resolved = {}
    for k in range(10):
        coeffs = [0.0] * 30
        coeffs[k] = 1.0                      # row 0 only; rows 1,2 stay zero
        out = g.run(coeffs, [(2, 3, 5)])[0][0]
        # the function adds 0.5 then truncates, so an exact integer survives
        if k == 9:
            note = "constant"
        elif k < 3:
            note = {0: "R", 1: "G", 2: "B"}[k]
        else:
            note = PRODUCT_OF.get(out, "UNEXPECTED")
            resolved[k] = note
        print(f"   c{k}     {out:>5}     {out:>5}   {note}")
    print()
    order = [resolved.get(k, "?") for k in range(3, 9)]
    print("  => c3..c8 = " + ", ".join(order))
    expected = ["R*R", "G*G", "B*B", "R*G", "R*B", "G*B"]
    ok = order == expected
    print(f"  => {'MATCHES' if ok else 'DIFFERS FROM'} pakon_color.poly_pixel "
          f"({', '.join(expected)})")
    return 0 if ok else 1


def cmd_vectors(g: PolyGolden) -> int:
    """docs/58 §14.5's R=G=B table, against emulator and Python side by side."""
    coeffs = pakon_color.load_unit_matrix()
    print("this unit's coefficients, R=G=B sweep\n")
    print("   input     emulator          pakon_color       ")
    bad = 0
    for v in (0, 1000, 4000, 8000, 12000, 16383):
        emu = g.run(coeffs, [(v, v, v)])[0]
        ours = pakon_color.poly_pixel((v, v, v), coeffs)
        flag = "" if emu == ours else "   <-- MISMATCH"
        bad += (emu != ours)
        print(f"  {v:>6}   {str(list(emu)):<18}{str(list(ours)):<18}{flag}")
    print(f"\n  => {'all agree' if not bad else f'{bad} mismatches'}")
    return 0 if not bad else 1


def cmd_random(g: PolyGolden, count: int, seed: int) -> int:
    """Fuzz the Python model against the emulator on independent channels."""
    rng = random.Random(seed)
    coeffs = pakon_color.load_unit_matrix()
    pixels = [(rng.randrange(16384), rng.randrange(16384), rng.randrange(16384))
              for _ in range(count)]
    # include the corners, which is where clamping and rounding diverge
    pixels += [(0, 0, 0), (16383, 16383, 16383), (0, 16383, 0), (16383, 0, 0),
               (0, 0, 16383), (1, 1, 1), (8192, 0, 16383)]
    emu = g.run(coeffs, pixels)
    bad = []
    for px, got in zip(pixels, emu):
        ours = pakon_color.poly_pixel(px, coeffs)
        if ours != got:
            bad.append((px, got, ours))
    print(f"fuzzed {len(pixels)} pixels through emulator and pakon_color")
    for px, got, ours in bad[:12]:
        print(f"  {px}: vendor {got}  ours {ours}")
    if len(bad) > 12:
        print(f"  ... and {len(bad) - 12} more")
    print(f"  => {len(bad)} mismatches out of {len(pixels)}")
    return 0 if not bad else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dll", default=DLL)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("term-order", help="settle the six quadratic terms")
    sub.add_parser("vectors", help="docs/58 §14.5 reference vectors")
    r = sub.add_parser("random", help="fuzz Python against the emulator")
    r.add_argument("--count", type=int, default=2000)
    r.add_argument("--seed", type=int, default=20260807)
    args = ap.parse_args()

    if not os.path.exists(args.dll):
        print(f"missing {args.dll}", file=sys.stderr)
        print("this subcommand needs the vendor DLL, which is not in the repo",
              file=sys.stderr)
        return 2
    g = PolyGolden(args.dll)
    if args.cmd == "term-order":
        return cmd_term_order(g)
    if args.cmd == "vectors":
        return cmd_vectors(g)
    return cmd_random(g, args.count, args.seed)


if __name__ == "__main__":
    sys.exit(main())
