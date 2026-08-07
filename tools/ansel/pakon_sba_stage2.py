#!/usr/bin/env python3
"""Byte-faithful SBA stage-2 program parser (PakonIMAu.dll @ 0x102a8f40).

VERIFIED against ``PakonIMAu.dll`` (image base 0x10000000):

* Called from ``SbaDecodePcode`` @ ``0x10288a99`` with state at pcode
  struct ``+0x138`` and second arg ``0``. Cursor is set to the word after
  ``0xFA`` and the following skipped word (``lea edx,[edi+esi*2+4]``).
* Loop: ``movsx`` current word; ``0xFD`` → version word must be ``9``;
  ``0xFF`` → success return ``0``; ``>0xFD`` and not ``0xFF`` → error;
  ``0..0x12`` via jump table at ``0x102a9838`` / map ``0x102a9860``.
* Opcodes ``8..15`` → error ``0xFFFFFFFA``; ``16..18`` skip 4 bytes.
* This module **parses** the trailing program into Python structures that
  mirror the calloc'd arrays the DLL fills. It does **not** resolve the
  function-pointer table at state ``+0x6c`` (DLL ``[esi+0x6c]``), used by
  opcodes 3 and 5 — those entries keep the raw selector index.

NOT implemented here (full AnalyseRoll / pass1–2 still open):

* ``Makesfs`` / ``AnsSfsTableDPI`` (``0x102ac820`` / ``0x102b7280``)
* ``AnsSbaCapabilityImpl::analyzePass1`` (``0x10218110``)
* ``AnsSbaCapabilityImpl::analyzePass2`` (``0x102159c0``) — host uses
  Preference dpi fragment instead (``pakon_sba_preference``)
* Balance apply path is ported elsewhere: Preference → ``setshifts_12`` →
  ``apply_balance_shifts`` (``pakon_sba_apply`` / ``pakon_ansel``)
"""
from __future__ import annotations

import argparse
import struct
from dataclasses import dataclass, field
from pathlib import Path

from pakon_sba_pcode import DecodedPcode, load_pcode, _sx16

STAGE2_OK = 0
STAGE2_ERR_VERSION = 0xFFFFFFF6  # -10
STAGE2_ERR_BAD_OP = 0xFFFFFFFA  # -6
STAGE2_VERSION = 9

# Jump-map (DLL 0x102a9860): opcode → case id
_OP_CASE = bytes([
    0, 1, 2, 3, 4, 5, 6, 7, 9, 9, 9, 9, 9, 9, 9, 9, 8, 8, 8,
])


def _u16(w: int) -> int:
    return w & 0xFFFF


@dataclass
class Op1Entry:
    """40-byte (0x28) record from opcode 1 (DLL helper 0x102a8ed0)."""
    index: int
    kind: int  # 0, 1, or 2
    fields: tuple[int, ...] = ()  # signed words; layout depends on kind
    # kind 0: (f0xc, f0x10, f0x14, f0x18, f0x8) — five words then pad to 20 words
    # kind 2: (f0x4,)
    # kind 1: five words selected by stage2 arg (always 0 from SbaDecodePcode)


@dataclass
class Op2Entry:
    """20-byte (0x14) record from opcode 2."""
    index: int
    count: int
    words: tuple[int, ...]  # `count` signed words (calloc count*2)


@dataclass
class Op3Entry:
    """36-byte (0x24) record from opcode 3."""
    index: int
    words: tuple[int, ...]  # seven signed ints at +0..+0x14, +0x20
    selector: int  # raw index into [state+0x6c] table (pointer NOT resolved)


@dataclass
class Op4Entry:
    """28-byte (0x1c) record from opcode 4 — float vector → int arrays."""
    index: int
    n: int
    floats: tuple[float, ...]  # n floats (first word is n in DLL via fld path)


@dataclass
class Op5Entry:
    """20-byte (0x14) record from opcode 5."""
    index: int
    words: tuple[int, ...]  # four signed ints at +0..+0xc
    selector: int  # raw [+0xc] → resolved via +0x6c (not resolved here)


@dataclass
class Op6Entry:
    """40-byte (0x28) record from opcode 6 — variable-length word packet."""
    index: int
    words: tuple[int, ...]  # packed stream words as consumed by DLL


@dataclass
class Op7Entry:
    """16-byte (0x10) record from opcode 7."""
    index: int
    flag: int  # at +0xc; if ==1 increments state counter +0x2c
    count: int
    words: tuple[int, ...]  # `count` signed words


@dataclass
class Stage2Program:
    """Parsed stage-2 state (fields relative to DLL state at pcode+0x138)."""
    version_ok: bool = False
    # opcode 0 → +0x04,+0x08,+0x0c,+0x0e,+0x14
    dim_a: int = 0
    dim_b: int = 0
    word_c: int = 0
    word_d: int = 0
    product: int = 0
    op1: list[Op1Entry] = field(default_factory=list)
    op2: list[Op2Entry] = field(default_factory=list)
    op3: list[Op3Entry] = field(default_factory=list)
    op4: list[Op4Entry] = field(default_factory=list)
    op5: list[Op5Entry] = field(default_factory=list)
    op6: list[Op6Entry] = field(default_factory=list)
    op7: list[Op7Entry] = field(default_factory=list)
    op7_flag1_count: int = 0  # DLL [esi+0x2c]
    return_code: int = STAGE2_OK
    words_consumed: int = 0
    name: str = ""


class _Cursor:
    def __init__(self, words: list[int]):
        self.words = words
        self.i = 0

    def remaining(self) -> int:
        return len(self.words) - self.i

    def peek(self) -> int:
        if self.i >= len(self.words):
            raise ValueError("stage-2 cursor past end")
        return self.words[self.i]

    def take(self) -> int:
        w = self.peek()
        self.i += 1
        return w

    def take_sx(self) -> int:
        return _sx16(self.take())

    def skip_bytes(self, n: int) -> None:
        """Advance cursor by n bytes (DLL ``add dword [esi], n``)."""
        if n % 2:
            raise ValueError(f"odd byte skip {n}")
        self.i += n // 2


def parse_stage2(
    program: list[int],
    *,
    table_select: int = 0,
    name: str = "",
) -> Stage2Program:
    """Parse stage-2 word list (post-FA program from ``decode_pcode``).

    ``table_select`` is the second arg to ``0x102a8f40`` (always ``0`` from
    ``SbaDecodePcode``). Used when opcode-1 ``kind==1`` picks a 5-word slice
    inside a 20-word padded record (offsets 0 / 5 / 10 / 15).
    """
    out = Stage2Program(name=name)
    if table_select not in (0, 1, 2, 3):
        # DLL ja → default error path for the inner switch; treat as bad.
        out.return_code = STAGE2_ERR_BAD_OP
        return out

    # kind==1 slice base (DLL 0x102a9095 cases)
    slice_base = (0, 10, 5, 15)[table_select]

    cur = _Cursor(program)
    try:
        while cur.remaining() > 0:
            op = cur.take_sx()
            if op == 0xFD:
                ver = cur.take_sx()
                if ver != STAGE2_VERSION:
                    out.return_code = STAGE2_ERR_VERSION
                    out.words_consumed = cur.i
                    return out
                out.version_ok = True
                continue
            if op > 0xFD:
                if op == 0xFF:
                    out.return_code = STAGE2_OK
                    out.words_consumed = cur.i
                    return out
                out.return_code = STAGE2_ERR_BAD_OP
                out.words_consumed = cur.i
                return out
            if op < 0 or op > 0x12:
                out.return_code = STAGE2_ERR_BAD_OP
                out.words_consumed = cur.i
                return out
            case = _OP_CASE[op]
            if case == 8:
                # opcodes 16..18: add eax,4
                cur.skip_bytes(4)
                continue
            if case == 9:
                out.return_code = STAGE2_ERR_BAD_OP
                out.words_consumed = cur.i
                return out
            if case == 0:
                out.dim_a = cur.take_sx()
                out.dim_b = cur.take_sx()
                out.word_c = _u16(cur.take())
                out.word_d = _u16(cur.take())
                out.product = out.dim_a * out.dim_b
                continue
            if case == 1:
                n = cur.take_sx()
                for _ in range(max(n, 0)):
                    idx = cur.take_sx()
                    kind = cur.take_sx()
                    if kind == 2:
                        f4 = cur.take_sx()
                        # DLL reads f4 without advancing then add 0x28 from
                        # cursor-at-f4; we already consumed f4, so skip 0x28-2.
                        cur.skip_bytes(0x28 - 2)
                        out.op1.append(Op1Entry(idx, kind, (f4,)))
                    elif kind == 0:
                        # five words at cursor+0..8, then add 0x28 from start
                        base = cur.i
                        five = tuple(_sx16(cur.words[base + j]) for j in range(5))
                        cur.skip_bytes(0x28)
                        # DLL stores: +0xc,+0x10,+0x14,+0x18,+0x8
                        out.op1.append(Op1Entry(idx, kind, five))
                    else:
                        # kind 1 (and any other non-0/2): type:=1, five words
                        # from cursor + slice_base
                        base = cur.i
                        five = tuple(
                            _sx16(cur.words[base + slice_base + j]) for j in range(5)
                        )
                        cur.skip_bytes(0x28)
                        out.op1.append(Op1Entry(idx, 1, five))
                continue
            if case == 2:
                # VERIFIED 0x102a9157: index, count(+4), calloc(count,2) left
                # zero-filled, then two scalars at +8 and +0xc. Buffer is NOT
                # filled from the stream in this handler.
                n = cur.take_sx()
                for _ in range(max(n, 0)):
                    idx = cur.take_sx()
                    count = cur.take_sx()
                    w8 = cur.take_sx()
                    wc = cur.take_sx()
                    out.op2.append(Op2Entry(idx, count, (w8, wc)))
                continue
            if case == 3:
                n = cur.take_sx()
                for _ in range(max(n, 0)):
                    idx = cur.take_sx()
                    # seven signed words → +0,+4,+8,+0xc,+0x10,+0x14,+0x20
                    ws = tuple(cur.take_sx() for _ in range(7))
                    out.op3.append(Op3Entry(idx, ws, selector=ws[6]))
                continue
            if case == 4:
                n = cur.take_sx()
                for _ in range(max(n, 0)):
                    idx = cur.take_sx()
                    nfloat = cur.take_sx()
                    # DLL reads pairs of u16 as float32 (fld dword)
                    floats: list[float] = []
                    for _j in range(max(nfloat, 0)):
                        w0 = cur.take() & 0xFFFF
                        w1 = cur.take() & 0xFFFF
                        raw = struct.pack("<HH", w0, w1)
                        floats.append(struct.unpack("<f", raw)[0])
                    out.op4.append(Op4Entry(idx, nfloat, tuple(floats)))
                continue
            if case == 5:
                n = cur.take_sx()
                for _ in range(max(n, 0)):
                    idx = cur.take_sx()
                    ws = tuple(cur.take_sx() for _ in range(4))
                    out.op5.append(Op5Entry(idx, ws, selector=ws[3]))
                continue
            if case == 6:
                n = cur.take_sx()
                for _ in range(max(n, 0)):
                    idx = cur.take_sx()
                    # DLL: store word at +0 (as u16), type at +4, then
                    # conditionally more words based on type in {4,5,6,8,11}
                    w0 = _u16(cur.take())
                    w_type = _u16(cur.take())
                    words: list[int] = [w0, w_type]
                    # optional +6 for types 4,5,6,8,11
                    if w_type in (4, 5, 6, 8, 0xB):
                        words.append(_u16(cur.take()))
                    # optional +8,+0xa for types 5,8,11
                    if w_type in (5, 8, 0xB):
                        words.append(_u16(cur.take()))
                        words.append(_u16(cur.take()))
                    # optional +0xc for types 5,8,11
                    if w_type in (5, 8, 0xB):
                        words.append(_u16(cur.take()))
                    # optional +0xe for types 5,11
                    if w_type in (5, 0xB):
                        words.append(_u16(cur.take()))
                    # optional +0x10,+0x12 for type 5
                    if w_type == 5:
                        words.append(_u16(cur.take()))
                        words.append(_u16(cur.take()))
                    out.op6.append(Op6Entry(idx, tuple(words)))
                continue
            if case == 7:
                n = cur.take_sx()
                for _ in range(max(n, 0)):
                    idx = cur.take_sx()
                    flag = cur.take_sx()
                    if flag == 1:
                        out.op7_flag1_count += 1
                    count = cur.take_sx()
                    words = tuple(cur.take_sx() for _ in range(max(count, 0)))
                    out.op7.append(Op7Entry(idx, flag, count, words))
                continue
            out.return_code = STAGE2_ERR_BAD_OP
            out.words_consumed = cur.i
            return out
    except (ValueError, IndexError) as e:
        out.return_code = STAGE2_ERR_BAD_OP
        out.words_consumed = cur.i
        out.name = f"{name} ({e})"
        return out

    # Fell off end without 0xFF
    out.return_code = STAGE2_ERR_BAD_OP
    out.words_consumed = cur.i
    return out


def parse_decoded(dec: DecodedPcode, table_select: int = 0) -> Stage2Program:
    return parse_stage2(dec.program, table_select=table_select, name=dec.name)


def verify_all(pcode_dir: Path) -> int:
    ok = 0
    for path in sorted(pcode_dir.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        dec = load_pcode(path)
        st = parse_decoded(dec)
        status = "OK" if st.return_code == STAGE2_OK and st.version_ok else "FAIL"
        if status == "OK":
            ok += 1
        print(
            f"{status:4} {path.name}: rc=0x{st.return_code & 0xFFFFFFFF:x} "
            f"dim={st.dim_a}x{st.dim_b} product={st.product} "
            f"op1={len(st.op1)} op2={len(st.op2)} op3={len(st.op3)} "
            f"op4={len(st.op4)} op5={len(st.op5)} op6={len(st.op6)} "
            f"op7={len(st.op7)} consumed={st.words_consumed}/{len(dec.program)}"
        )
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", type=Path, help="pcode file or Pcode directory")
    args = ap.parse_args()
    if args.path.is_dir():
        n = verify_all(args.path)
        print(f"{n} file(s) stage-2 OK")
        return 0 if n else 1
    dec = load_pcode(args.path)
    st = parse_decoded(dec)
    print(
        f"{dec.name}: rc=0x{st.return_code & 0xFFFFFFFF:x} version_ok={st.version_ok} "
        f"dim={st.dim_a}x{st.dim_b} product={st.product}"
    )
    print(
        f"  counts op1..7 = "
        f"{len(st.op1)},{len(st.op2)},{len(st.op3)},{len(st.op4)},"
        f"{len(st.op5)},{len(st.op6)},{len(st.op7)}"
    )
    return 0 if st.return_code == STAGE2_OK else 1


if __name__ == "__main__":
    raise SystemExit(main())
