#!/usr/bin/env python3
"""Byte-faithful SbaDecodePcode stage-1 (PakonIMAu.dll @ 0x102884b0).

Verified against ``PakonIMAu.dll`` (PE image base 0x10000000) and all nine
shipped ``anselinstalldir/dataPathItems/sba/Pcode/pcode-*`` files:

* File is a stream of little-endian u16 on disk. The decoder checks word0;
  if it is not ``0x00FB``, every word is byte-swapped (LE host path). After
  that the logical stream always starts with ``0xFB``.
* Stage-1 walks opcodes ``word - 11`` in ``[0..48]`` (opcodes 11..59).
  Unknown / opcode 45: skip ``1 + word[1]`` words then the common ``inc``.
  Table opcodes 11..15 copy 22 words into a 0x1A8-byte struct (no extra inc).
  Opcodes 16/33 derive two scaled fields (``×864``, round÷100).
  Other opcodes store the word at ``esi+2`` at a fixed struct offset, then
  ``esi += 3`` from the opcode index.
* Loop stops when the low byte of the current word is ``0xFA``. Success
  requires the full word ``== 0xFA``. Bytes after that are the stage-2
  program (parsed by ``0x102a8f40``, not implemented here).
* Error code on failure: ``0x18A8`` (matches DLL return).

Stage-2 VM, ``Makesfs``, ``analyzePass1/2``, and ``getShifts`` are NOT
ported yet — those are what produce per-scene balance shifts.
"""
from __future__ import annotations

import argparse
import struct
from dataclasses import dataclass, field
from pathlib import Path

SBA_DECODE_ERR = 0x18A8
STRUCT_SIZE = 0x1A8
TABLE_LEN = 22

# Opcode → struct offset for simple scalar stores (DLL cases 17..32, 34..44, 46..58)
_SCALAR_OFF = {
    17: 0xE4, 18: 0xE6, 19: 0xE8, 20: 0xEA, 21: 0xEC, 22: 0xEE,
    23: 0xF0, 24: 0xF2, 25: 0xF4, 26: 0xF6, 27: 0xF8, 28: 0xFA,
    29: 0xFC, 30: 0xFE, 31: 0x100, 32: 0x102,
    34: 0x104, 35: 0x106, 36: 0x108, 37: 0x10A, 38: 0x10C, 39: 0x10E,
    40: 0x110, 41: 0x112, 42: 0x114, 43: 0x116, 44: 0x118,
    46: 0x11A, 47: 0x11C, 48: 0x11E, 49: 0x120, 50: 0x122, 51: 0x124,
    52: 0x126, 53: 0x128, 54: 0x12A, 55: 0x12C, 56: 0x12E, 57: 0x130,
    58: 0x132,
}
_TABLE_BASE = {11: 0x00, 12: 0x2C, 13: 0x58, 14: 0x84, 15: 0xB0}


def _sx16(w: int) -> int:
    return w if w < 0x8000 else w - 0x10000


def _round_div100(n: int) -> int:
    """Match MSVC path: bias ±50, imul 0x51EB851F, sar edx,5, add signbit."""
    x = n + 50 if n >= 0 else n - 50
    # signed 32 × signed 32 → high 32
    a = ctypes_int32(x)
    prod = a * ctypes_int32(0x51EB851F)
    edx = ctypes_int32((prod >> 32) & 0xFFFFFFFF)
    edx >>= 5
    return edx + (1 if edx < 0 else 0)


def ctypes_int32(v: int) -> int:
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


@dataclass
class DecodedPcode:
    """Stage-1 decode result (DLL calloc 0x1A8 + trailing program words)."""
    struct: bytes
    program: list[int] = field(default_factory=list)
    name: str = ""

    def table(self, index: int) -> tuple[int, ...]:
        """One of five 22-word tables at struct offsets 0, 0x2C, 0x58, 0x84, 0xB0."""
        if not 0 <= index < 5:
            raise IndexError(index)
        base = (0x00, 0x2C, 0x58, 0x84, 0xB0)[index]
        return struct.unpack_from(f"<{TABLE_LEN}H", self.struct, base)

    def u16(self, offset: int) -> int:
        return struct.unpack_from("<H", self.struct, offset)[0]


def decode_pcode(data: bytes, name: str = "") -> DecodedPcode:
    """Decode pcode bytes → struct + stage-2 program. Raises on failure."""
    if len(data) < 2:
        raise ValueError(f"SbaDecodePcode failed, return code {SBA_DECODE_ERR}")
    n = len(data) // 2
    words = list(struct.unpack("<" + "H" * n, data[: n * 2]))
    if words[0] != 0xFB:
        words = [((w & 0xFF) << 8) | (w >> 8) for w in words]
        if words[0] != 0xFB:
            raise ValueError(f"SbaDecodePcode failed, return code {SBA_DECODE_ERR}")

    buf = bytearray(STRUCT_SIZE)

    def put(off: int, val: int) -> None:
        struct.pack_into("<H", buf, off, val & 0xFFFF)

    esi = 0
    nwords = len(words)
    while esi < nwords:
        op = words[esi]
        key = _sx16(op) - 11
        if key < 0 or key > 48 or op == 45:
            skip = _sx16(words[esi + 1]) if esi + 1 < nwords else 0
            esi = esi + 1 + skip
            esi += 1
        elif op in _TABLE_BASE:
            base = _TABLE_BASE[op]
            esi += 2
            for i in range(TABLE_LEN):
                if esi >= nwords:
                    break
                put(base + i * 2, words[esi])
                esi += 1
        elif op in (16, 33):
            b = _sx16(words[esi + 2]) if esi + 2 < nwords else 0
            esi += 2
            off1, off2 = (0xDC, 0xDE) if op == 16 else (0xE0, 0xE2)
            put(off1, _round_div100(b * 0x360))
            a = _sx16(words[esi]) if esi < nwords else 0
            probe = (100 - a) * 0x360
            basec = 0x151B2 if probe >= 0 else 0x1514E
            val = _round_div100(basec - a * 0x360)
            if val == 0:
                val = 1
            put(off2, val)
            esi += 1
        elif op == 59:
            put(0x134, words[esi + 2] if esi + 2 < nwords else 0)
            esi += 2
            esi += 1
        elif op in _SCALAR_OFF:
            put(_SCALAR_OFF[op], words[esi + 2] if esi + 2 < nwords else 0)
            esi += 2
            esi += 1
        else:
            raise ValueError(f"unhandled pcode opcode {op} at word {esi}")

        if esi >= nwords:
            break
        if (words[esi] & 0xFF) == 0xFA:
            break

    if esi >= nwords or words[esi] != 0xFA:
        raise ValueError(f"SbaDecodePcode failed, return code {SBA_DECODE_ERR}")

    return DecodedPcode(
        struct=bytes(buf),
        program=list(words[esi + 2:]),
        name=name,
    )


def load_pcode(path: Path) -> DecodedPcode:
    return decode_pcode(path.read_bytes(), name=path.name)


def parse_sfs_table(path: Path) -> list[tuple[int, int, int, int]]:
    """Parse ``sfsTable35``-style ASCII: four ints per line, ends with 0 0 0 0."""
    rows: list[tuple[int, int, int, int]] = []
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        row = tuple(int(float(p)) for p in parts[:4])
        rows.append(row)  # type: ignore[arg-type]
        if row == (0, 0, 0, 0):
            break
    return rows


def verify_all(pcode_dir: Path) -> int:
    ok = 0
    for path in sorted(pcode_dir.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        try:
            dec = load_pcode(path)
        except ValueError as e:
            print(f"FAIL {path.name}: {e}")
            continue
        print(
            f"OK   {path.name}: struct=0x{len(dec.struct):x} "
            f"program_words={len(dec.program)} "
            f"t0[0]={dec.table(0)[0]} dc={dec.u16(0xDC)}/{dec.u16(0xDE)}"
        )
        ok += 1
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "path",
        nargs="?",
        type=Path,
        help="pcode file, or directory to verify all",
    )
    ap.add_argument(
        "--pcode-dir",
        type=Path,
        default=None,
        help="directory of pcode-* files (default: verify arg if dir)",
    )
    args = ap.parse_args()
    if args.path is None and args.pcode_dir is None:
        ap.error("pass a pcode file or directory")
    target = args.pcode_dir or args.path
    assert target is not None
    if target.is_dir():
        n = verify_all(target)
        print(f"{n} file(s) decoded")
        return 0 if n else 1
    dec = load_pcode(target)
    print(f"{dec.name}: program_words={len(dec.program)}")
    for i in range(5):
        print(f"  table[{i}]={dec.table(i)[:8]}…")
    print(f"  0xDC..E2={[dec.u16(o) for o in (0xDC, 0xDE, 0xE0, 0xE2)]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
