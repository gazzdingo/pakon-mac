#!/usr/bin/env python3
"""SBA p-code stage-2 interpreter — the vendor's bytecode VM (``PakonIMAu.dll``).

Port of ``fcn.102aadf0`` (``PakonIMAu.dll``, md5
``eea9dcf78ee21d4f7c515a6c2512242d``, 4423 bytes at image base ``0x10000000``),
the interpreter ``docs/74 §78.2`` found blocking the whole-function Unicorn run
of ``0x1028b8d0`` and ``§85`` proved is the *only* producer of ``orderFpo.Y``'s
``L`` term. Companion to ``pakon_sba_pcode.py``, which ports stage 1 of the same
file format (``SbaDecodePcode`` @ ``0x102884b0``) and explicitly left "bytes
after the ``0xFA`` terminator are the stage-2 program … not implemented here".
This module is that stage.

Evidence tier for everything below: **static disassembly** (``radare2`` 6.1.8 via
``r2pipe``, ``af``+``pdf`` at the real function boundary, never ``pD``) **plus
live hardware hook capture** — the two v27 captures
(``live_hooks_20260817-212408.jsonl`` md5 ``cf67eec3…``, roll A, and
``live_hooks_20260817-213026.jsonl`` md5 ``b7b02a79…``, roll B), 3168
``sba_vm_interp`` firings each. See ``docs/74 §88``.

What the machine is
===================
A 32-bit integer stack machine over a *spreadsheet*. The program store is not
one program but a fixed table of **264 short expression records** read verbatim
out of the shipped file
``vendor/ansel/anselinstalldir/dataPathItems/sba/Pcode/pcode-dls_1.7``.
Each record is ``(index, tag, nwords, words…)``; record *k* evaluates an
expression and stores the result into variable slot *k*. The whole table is
re-run per scene against a per-scene input vector.

Interpreter signature (0-based stack args, ``cdecl``)::

    int fcn_102aadf0(void *machine /* ebx */, Record *rec /* ebp */, ...)
        ebx = dword [esp+0x40] @ 0x102aae0b   (arg 0)
        ebp = dword [esp+0x3c] @ 0x102aadf5   (arg 1)
        edi = dword [ebp+4]    @ 0x102aadfb   (the program words)

Machine fields the reached opcodes touch (all relative to ``ebx``)::

    ebx+0x30   Record[] base      == sba_obj+0x168   (16-byte records)
    ebx+0x54   the operand stack object {base, top, limit}
    ebx+0x64   int32 in[]  base   == sba_obj+0x19c

and ``ebx == sba_obj + 0x138``, with ``sba_obj`` = ``0x1028b8d0``'s arg 6.
Both identities are confirmed live, 12/12 machines on both rolls: the captured
``arg6_big`` dump has ``arg6+0x160 == 264`` (the record count) and
``arg6+0x168`` equal to the address the interpreter is handed as its arg 1 on
the first of that machine's 264 calls.

Record layout in memory (16 bytes), confirmed 3168/3168 on **both** rolls
against the pcode file::

    +0x00  int32  nwords     == the file record's declared length
    +0x04  int32  words*     -> the program
    +0x08  int32  value      <- STORE writes here; PUSH t3 reads here
    +0x0c  int32  tag        == the file record's type field (0 or 1)

Dispatch (0x102aae15…0x102aae2b), two stage::

    movsx eax, ax ; dec eax ; cmp eax, 0xfd ; ja default
    movzx eax, byte [eax + 0x102ac018]        ; 254-byte opcode-1 -> handler
    jmp dword [eax*4 + 0x102abf4c]            ; 51-entry handler table

The 254 opcodes collapse to 51 handler indices; index 50 (``0x102abf2d``,
``return -110``) covers 203 of them and is the invalid-opcode case, so there are
**50 real handlers**. Of those, **19 opcodes are actually reached by the 264
real records** — see ``OPCODES`` below for exactly which, and
``UNIMPLEMENTED`` for what is deliberately left out and why.

Instruction encoding (derived from the handlers' own ``add edi`` on each path,
then cross-checked by requiring all 264 records to decode exactly to their
``0xff`` halt — 264/264)::

    opcode 1  (PUSH)   3 words, or 4 words when its type operand is 4
    opcode 2  (STORE)  2 words
    every other opcode 1 word
    opcode 255         halt

``§86.4``'s reading of the same three worked examples was wrong and is
superseded: it read ``4,2,3`` as "``op4`` with operands ``(2,3)``" when it is
three separate instructions ``SUB ; STORE 3``. Nothing but ``PUSH`` and
``STORE`` carries an operand at all.

Where ``L`` is
==============
``§76.6`` established ``L`` = ``((int32*)&buf_m258)[22]``, the 23rd value
``fcn.102ac310`` extracts from the record array, taking records whose ``+0xc``
is 1 in order (``0x102ac3e8``: ``cmp dword [eax+0xc], 1``). In the shipped
table exactly 130 records carry tag 1 — records 134…263, contiguous — so the
23rd of them is **record 156**, whose entire program is::

      0: PUSH v133
      3: STORE v156
      5: HALT

Therefore ``L == vars[133]``. ``L_SLOT`` / ``L_RECORD`` / ``L_EXTRACT_INDEX``
below record that chain.

What this module CANNOT do yet (stated plainly)
===============================================
``vars[133]``'s dependency closure is 105 records reading **88 distinct
``in[]`` indices** (counting both arms of every conditional; 103 records / 85
indices on the fall-through arms alone), the highest index being 732.
``in[]`` is ``sba_obj+0x19c``, set by ``fcn.102ac310`` from
its own 4th argument, which ``0x1028bf9c`` supplies as ``lea eax, [esi+0x3c]``
— i.e. ``arg11 + 0x3c`` of ``0x1028b8d0``. Every capture in hand hooks
``0x1028b8d0`` at **entry**, and ``arg11+0x3c`` is still mostly zeroed then
(56 of ~740 int32 non-zero); it is filled later in the same call, before the
``fcn.102ac310`` call at ``0x1028bfa8``. So **the six/twelve real ``L`` values
are not reproducible from the data in hand** — not because the VM is
unported, but because its per-scene *input vector* has never been captured.

The capture that closes it is one row: ``sba_order_fpo_helper`` is already
hooked at ``0x1028ae00``, which runs *after* ``0x1028bfa8``, and its arg 1 is
the same ``arg11`` (``§76.4``'s argument table). Dumping ``arg1 + 0x3c`` for
``0xb80`` bytes on that existing hook yields the filled ``in[]`` for all 12
machines, and this module then produces ``L`` directly.
"""
from __future__ import annotations

import math
import os
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = [
    "VmError", "Record", "Machine",
    "load_pcode", "decode", "format_program",
    "run_record", "run_all", "extract_tagged",
    "L_SLOT", "L_RECORD", "L_EXTRACT_INDEX",
    "OPCODES", "UNIMPLEMENTED", "PCODE_DIR", "DEFAULT_PCODE",
]

# ---------------------------------------------------------------- constants

HALT = 0xFF
NOP_WORD = 0xFE                      # opcodes 253/254 -> h49, `add edi,2` only
LABEL_WORD = 0x23E7                  # 9191, the branch-target marker
ENDLABEL_WORD = 0x244C               # 9292, opcode 54's terminator marker

#: ``254, 9191, 254`` is the label triple both skip opcodes scan for
#: (``0x102abd52…0x102abd81`` / ``0x102abda6…0x102abdbf``).

# vendor return codes seen on the interpreter's own error exits
ERR_INVALID_OPCODE = -110            # 0xffffff92, 0x102abf42 (handler 50)
ERR_DIVIDE_BY_ZERO = -101            # 0xffffff9b, 0x102abe17
ERR_BAD_COUNT = -105                 # 0xffffff97, 0x102abe37/be5b/be7f
ERR_STACK_EMPTY = -106               # 0xffffff96, 0x102abed3
ERR_PROGRAM_END = -100               # 0xffffff9c, 0x102abdf3 (inner default)

#: ``fmul dword [0x105a0800]`` then ``fmul dword [0x105a882c]`` around
#: ``_CItanh`` — both float32 constants, read from the DLL, not chosen.
TANH_SCALE_IN = struct.unpack("<f", struct.pack("<I", 0x3A83126F))[0]   # ~1e-3
TANH_SCALE_OUT = struct.unpack("<f", struct.pack("<I", 0x447A0000))[0]  # 1000.0

PCODE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))),
    "vendor", "ansel", "anselinstalldir", "dataPathItems", "sba", "Pcode")
DEFAULT_PCODE = os.path.join(PCODE_DIR, "pcode-dls_1.7")

#: ``L`` = ``orderFpo.Y``'s per-frame delta (``docs/74 §76.3``).
L_EXTRACT_INDEX = 22     # index into fcn.102ac310's tag==1 output list (§76.6)
L_RECORD = 156           # the record that occupies that slot in pcode-dls_1.7
L_SLOT = 133             # …and its whole body is `PUSH v133 ; STORE v156`

STACK_LIMIT = 0x190      # calloc(0x190, 4) @ 0x102ac358 -> 400 dwords

# ------------------------------------------------------------------- errors


class VmError(Exception):
    """A vendor error exit, carrying the DLL's own return code."""

    def __init__(self, msg: str, code: Optional[int] = None,
                 record: Optional[int] = None, offset: Optional[int] = None):
        super().__init__(msg)
        self.code = code
        self.record = record
        self.offset = offset


# ------------------------------------------------------------- 32-bit maths

_M32 = 0xFFFFFFFF


def _s32(v: int) -> int:
    v &= _M32
    return v - (1 << 32) if v >= (1 << 31) else v


def _s16(v: int) -> int:
    """``movsx eax, word [edi]`` — every index operand is sign-extended."""
    v &= 0xFFFF
    return v - (1 << 16) if v >= 0x8000 else v


def _idiv(a: int, b: int) -> int:
    """x86 ``idiv``: truncate toward zero, not Python's floor."""
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def _ftol(x: float) -> int:
    """``fcn.104ffe44`` = MSVC ``_ftol``: round-to-nearest ``fistp`` then
    corrected back toward zero — i.e. plain truncation toward zero."""
    return int(x)


# --------------------------------------------------------------- the record

@dataclass(frozen=True)
class Record:
    """One stage-2 record: ``(index, tag, nwords, words)`` from the file."""
    index: int
    tag: int
    words: Tuple[int, ...]

    @property
    def nwords(self) -> int:
        return len(self.words)


def load_pcode(path: str = DEFAULT_PCODE) -> List[Record]:
    """Read the stage-2 record table out of a shipped ``pcode-*`` file.

    The file is a stream of **big-endian** u16 on disk (``pakon_sba_pcode``'s
    stage-1 note: word 0 is ``0x00FB`` only when read big-endian, and the
    decoder byte-swaps on a little-endian host). The stage-2 section is a
    record count followed by that many ``(index, tag, nwords, words…)``
    records, with ``index`` running 0..count-1 — which is what anchors the
    section without having to re-walk stage 1.
    """
    raw = open(path, "rb").read()
    n = len(raw) // 2
    w = struct.unpack(">%dH" % n, raw[:2 * n])

    # Anchor on the record count: the only offset at which `count` records of
    # (index, tag, nwords, words…) parse with `index` running 0..count-1 AND
    # the parse lands at the end of the file (a lone 0x00ff trailer). Both
    # halves are needed -- a short table parses "successfully" almost anywhere.
    start = None
    for i in range(len(w) - 4):
        count = w[i]
        if not (1 < count < 4096) or w[i + 1] != 0 or w[i + 2] != 0:
            continue
        j, k = i + 1, 0
        while k < count and j + 3 <= len(w):
            idx, _tag, ln = w[j], w[j + 1], w[j + 2]
            if idx != k or ln <= 0 or j + 3 + ln > len(w):
                break
            j += 3 + ln
            k += 1
        if k == count and len(w) - j <= 2:
            start = i
            break
    if start is None:
        raise VmError("no stage-2 record table found in %s" % path)

    recs: List[Record] = []
    j = start + 1
    for _ in range(w[start]):
        idx, tag, ln = w[j], w[j + 1], w[j + 2]
        recs.append(Record(idx, tag, tuple(w[j + 3:j + 3 + ln])))
        j += 3 + ln
    return recs


# ------------------------------------------------------------- disassembler

#: opcode -> (mnemonic, operand words after the opcode)
OPCODES: Dict[int, Tuple[str, int]] = {
    1: ("PUSH", -1),    # 2 or 3, decided by the type operand (see `_ilen`)
    2: ("STORE", 1),
    3: ("ADD", 0), 4: ("SUB", 0), 5: ("MUL", 0), 6: ("DIV", 0), 7: ("NEG", 0),
    16: ("TANH", 0),
    27: ("SUMN", 0), 28: ("MEANN", 0), 29: ("MAXN", 0), 30: ("MINN", 0),
    31: ("SEL_GT", 0), 32: ("SEL_LT", 0), 33: ("SEL_EQ", 0),
    34: ("SEL_GE", 0), 35: ("SEL_LE", 0), 36: ("SEL_NE", 0),
    47: ("HYPOT", 0), 48: ("NEGABS", 0), 49: ("DUP", 0), 50: ("SWAP", 0),
    54: ("SKIP", 0), 55: ("CSKIP", 0),
    56: ("GT", 0), 57: ("LT", 0), 58: ("EQ", 0), 59: ("GE", 0),
    60: ("LE", 0), 61: ("NE", 0), 62: ("AND", 0), 63: ("OR", 0),
    64: ("NOT", 0), 68: ("BAND", 0), 69: ("BOR", 0),
    253: ("NOP", 0), 254: ("NOP", 0),
    HALT: ("HALT", 0),
}

#: Opcodes with a real handler that this module does NOT implement, with the
#: machine sub-object each one needs. **None of these is reached by any of the
#: 264 records in any shipped ``pcode-*`` file**, so leaving them out costs
#: nothing today; each would need an object model nobody has captured.
UNIMPLEMENTED: Dict[int, str] = {
    37: "h18 0x102ab893 — calls 0x102aa990 on ebx+0x38 records (stride 20)",
    38: "h19 0x102ab8bd — calls 0x102aa9c0 on ebx+0x38 records",
    39: "h20 0x102ab97e — calls 0x102aa9f0 on ebx+0x38 records",
    40: "h21 0x102aba1f — calls 0x102aab90 on ebx+0x38 records",
    41: "h22 0x102ab9dc — calls 0x102aaaf0 on ebx+0x38 records",
    42: "h23 0x102ab19b — RGB->Y/C1/C2 transform; pure, but its four stack "
        "slots are aliased across three pushes and were not resolved to a "
        "single unambiguous reading, so it is left out rather than guessed",
    43: "h24 0x102ab278 — same family as 42, same reason",
    44: "h25 0x102abaa5 — allocates and sorts through ebx+0x50",
    45: "h26 0x102aba51 — reads ebx+0x48",
    46: "h27 0x102abbba — pure, a long piecewise ratio classifier; unused",
    51: "h32 0x102ab91d — reads ebx+0x38 records",
    52: "h33 0x102ab8e7 — reads ebx+0x38 records (gain/offset apply)",
    53: "h34 0x102ab954 — calls 0x102aaaa0 on ebx+0x38 records",
    67: "h46 0x102ab9b2 — calls 0x102aaa60 on ebx+0x38 records",
}

#: PUSH type selector -> source (inner 7-case table at ``0x102ac118``).
PUSH_SOURCES = {
    0: "ebx+0x24[i].0x14 (stride 0x28)",
    1: "ebx+0x24[i].0x18",
    2: "ebx+0x24[i].0x1c",
    3: "vars[i]  (ebx+0x30 + i*16 + 8)",
    4: "int32 immediate, high word first",
    5: "ebx+0x1c[i].0x08 (stride 0x28)",
    6: "in[i]   (*(ebx+0x64) + i*4)",
}
#: The 264 real records only ever use types 3, 4 and 6.
PUSH_IMPLEMENTED = (3, 4, 6)


def _ilen(words: Sequence[int], i: int) -> int:
    op = words[i]
    if op == 1:
        return 4 if (i + 1 < len(words) and words[i + 1] == 4) else 3
    if op == 2:
        return 2
    return 1


def decode(words: Sequence[int]) -> List[Tuple[int, int, Tuple[int, ...]]]:
    """Linear decode: ``[(word_offset, opcode, operands), …]``.

    Linear decode is *not* execution: the two skip opcodes jump over label
    triples, so the words between a ``CSKIP`` and its label are decoded here
    but only one arm of them ever runs.
    """
    out, i = [], 0
    while i < len(words):
        k = _ilen(words, i)
        if i + k > len(words):
            raise VmError("operand overruns the record at word %d" % i)
        out.append((i, words[i], tuple(words[i + 1:i + k])))
        if words[i] == HALT:
            break
        i += k
    return out


def format_program(words: Sequence[int]) -> List[str]:
    """Human-readable disassembly, one line per instruction."""
    lines = []
    for off, op, a in decode(words):
        if op == 1:
            if a[0] == 4:
                txt = "PUSH #%d" % _s32((a[1] << 16) | a[2])
            elif a[0] == 3:
                txt = "PUSH v%d" % _s16(a[1])
            elif a[0] == 6:
                txt = "PUSH in[%d]" % _s16(a[1])
            else:
                txt = "PUSH t%d[%d]" % (a[0], _s16(a[1]))
        elif op == 2:
            txt = "STORE v%d" % _s16(a[0])
        elif op == LABEL_WORD:
            txt = ".label"
        elif op == ENDLABEL_WORD:
            txt = ".endlabel"
        else:
            txt = OPCODES.get(op, ("op%d" % op, 0))[0]
        lines.append("%4d: %s" % (off, txt))
    return lines


# ------------------------------------------------------------- the machine

@dataclass
class Machine:
    """One VM instance: the variable file plus the per-scene input vector.

    ``vars`` is the ``+8`` field of the 16-byte record array at ``ebx+0x30``;
    it is ``calloc``-ed, hence zero-initialised. ``inputs`` is the int32 array
    at ``*(ebx+0x64)``.
    """
    inputs: Sequence[int]
    nvars: int = 264
    vars: List[int] = field(default_factory=list)
    stack: List[int] = field(default_factory=list)

    def __post_init__(self):
        if not self.vars:
            self.vars = [0] * self.nvars

    # the operand stack object at ebx+0x54 = {base, top, limit}
    def push(self, v: int) -> None:
        if len(self.stack) >= STACK_LIMIT:
            raise VmError("operand stack overflow", -24)
        self.stack.append(_s32(v))

    def pop(self) -> int:
        if not self.stack:
            # fcn.102a8c50 longjmps with -23 when top == base
            raise VmError("operand stack underflow", -23)
        return self.stack.pop()


def _scan_labels(words: Sequence[int], i: int, nskip: int,
                 stop_on_endlabel: bool) -> int:
    """The shared marker scan of opcodes 54/55.

    Transcribed from ``0x102abd52…0x102abd81`` (opcode 54) and
    ``0x102abda6…0x102abdbf`` (opcode 55): a counter starts at ``-1``, a word
    equal to ``9191`` **whose neighbours on both sides are ``254``** increments
    it, the cursor advances one word per iteration, and the loop ends once the
    counter reaches ``nskip``. Opcode 54 additionally stops dead on a ``9292``
    triple, leaving the cursor *on* that word — which the fetch then rejects as
    an invalid opcode. That is what the code does; it is not smoothed over
    here.
    """
    c = -1
    while True:
        if i >= len(words):
            raise VmError(
                "label scan ran past the end of the record — the vendor would "
                "keep scanning into the adjacent p-code image", ERR_PROGRAM_END)
        cw = words[i]
        neighbours = (i > 0 and words[i - 1] == NOP_WORD
                      and i + 1 < len(words) and words[i + 1] == NOP_WORD)
        if stop_on_endlabel and cw == ENDLABEL_WORD and neighbours:
            return i
        if cw == LABEL_WORD and neighbours:
            c += 1
        i += 1
        if c >= nskip:
            return i


def run_record(rec: Record, m: Machine) -> None:
    """Execute one record on ``m``. Raises :class:`VmError` on a vendor error."""
    w = rec.words
    i = 0
    steps = 0
    while True:
        steps += 1
        if steps > 1_000_000:
            raise VmError("interpreter did not terminate", record=rec.index)
        if i >= len(w):
            raise VmError("ran off the end of the record",
                          ERR_PROGRAM_END, rec.index, i)
        op = w[i]

        if op == HALT:
            return

        if op == 1:                                   # h0 @ 0x102aae32
            t = w[i + 1]
            if t == 4:
                m.push(_s32((w[i + 2] << 16) | w[i + 3]))
                i += 4
                continue
            if t not in PUSH_IMPLEMENTED:
                raise VmError(
                    "PUSH source type %d (%s) not ported — no shipped record "
                    "uses it" % (t, PUSH_SOURCES.get(t, "invalid")),
                    record=rec.index, offset=i)
            idx = _s16(w[i + 2])
            if t == 3:
                if not 0 <= idx < len(m.vars):
                    raise VmError("vars[%d] out of range" % idx,
                                  record=rec.index, offset=i)
                m.push(m.vars[idx])
            else:                                     # t == 6
                if not 0 <= idx < len(m.inputs):
                    raise VmError("in[%d] out of range (have %d)"
                                  % (idx, len(m.inputs)),
                                  record=rec.index, offset=i)
                m.push(m.inputs[idx])
            i += 3
            continue

        if op == 2:                                   # h1 @ 0x102aaf41
            idx = _s16(w[i + 1])
            if not 0 <= idx < len(m.vars):
                raise VmError("STORE v%d out of range" % idx,
                              record=rec.index, offset=i)
            m.vars[idx] = m.pop()
            i += 2
            continue

        if op in (54, 55):                            # h35/h36
            if op == 54:
                nskip = m.pop()
            else:
                # 0x102abd94 `neg/sbb/inc`: 1 when the condition is zero.
                nskip = 1 if m.pop() == 0 else 0
            i += 1
            if nskip <= -1:
                continue
            i = _scan_labels(w, i, nskip, stop_on_endlabel=(op == 54))
            continue

        # ---- everything below is a fixed-arity operand-stack op, 1 word
        if op == 3:                                   # h2  ADD
            b = m.pop(); a = m.pop(); m.push(a + b)
        elif op == 4:                                 # h3  SUB
            b = m.pop(); a = m.pop(); m.push(a - b)
        elif op == 5:                                 # h4  MUL
            b = m.pop(); a = m.pop(); m.push(a * b)
        elif op == 6:                                 # h5  DIV
            b = m.pop(); a = m.pop()
            if b == 0:
                raise VmError("divide by zero", ERR_DIVIDE_BY_ZERO,
                              rec.index, i)
            m.push(_idiv(a, b))
        elif op == 7:                                 # h6  NEG
            m.push(-m.pop())
        elif op == 16:                                # h7  TANH
            x = m.pop()
            m.push(_ftol(math.tanh(x * TANH_SCALE_IN) * TANH_SCALE_OUT))
        elif op in (27, 28):                          # h8/h9  SUMN / MEANN
            n = m.pop()
            if n < 1:
                raise VmError("SUMN/MEANN count %d < 1" % n, ERR_BAD_COUNT,
                              rec.index, i)
            s = 0
            for _ in range(n):
                s = _s32(s + m.pop())
            m.push(s if op == 27 else _idiv(s, n))
        elif op in (29, 30):                          # h10/h11  MAXN / MINN
            n = m.pop()
            if n < 1:
                raise VmError("MAXN/MINN count %d < 1" % n, ERR_BAD_COUNT,
                              rec.index, i)
            acc = m.pop()
            for _ in range(n - 1):
                x = m.pop()
                if (x > acc) if op == 29 else (x < acc):
                    acc = x
            m.push(acc)
        elif op in (31, 32, 33, 34, 35, 36):          # h12..h17  select
            # pushed A,B,C,D -> popped v1=D v2=C v3=B v4=A
            d = m.pop(); c = m.pop(); b = m.pop(); a = m.pop()
            cond = {31: a > b, 32: a < b, 33: a == b,
                    34: a >= b, 35: a <= b, 36: a != b}[op]
            m.push(c if cond else d)
        elif op == 47:                                # h28  HYPOT
            b = m.pop(); a = m.pop()
            m.push(_ftol(math.sqrt(float(_s32(a * a + b * b)))))
        elif op == 48:                                # h29
            # 0x102ab121: `test eax,eax; jge -> neg`. Non-negative inputs are
            # negated, negative ones pass through: this is -|x|, not |x|.
            x = m.pop()
            m.push(-x if x >= 0 else x)
        elif op == 49:                                # h30  DUP
            x = m.pop(); m.push(x); m.push(x)
        elif op == 50:                                # h31  SWAP
            a = m.pop(); b = m.pop(); m.push(a); m.push(b)
        elif op in (56, 57, 58, 59, 60, 61):          # h37..h42  compare
            b = m.pop(); a = m.pop()
            r = {56: a > b, 57: a < b, 58: a == b,
                 59: a >= b, 60: a <= b, 61: a != b}[op]
            m.push(1 if r else 0)
        elif op == 62:                                # h43  logical AND
            b = m.pop(); a = m.pop(); m.push(1 if (a and b) else 0)
        elif op == 63:                                # h44  logical OR
            b = m.pop(); a = m.pop(); m.push(1 if (a or b) else 0)
        elif op == 64:                                # h45  logical NOT
            m.push(0 if m.pop() else 1)
        elif op == 68:                                # h47  bitwise AND
            b = m.pop(); a = m.pop(); m.push(_s32((a & b) & _M32))
        elif op == 69:                                # h48  bitwise OR
            b = m.pop(); a = m.pop(); m.push(_s32((a | b) & _M32))
        elif op in (253, 254):                        # h49  NOP
            pass
        elif op in UNIMPLEMENTED:
            raise VmError("opcode %d not ported: %s" % (op, UNIMPLEMENTED[op]),
                          record=rec.index, offset=i)
        else:
            # 203 of the 254 opcodes land on handler 50, which returns -110.
            raise VmError("invalid opcode %d" % op, ERR_INVALID_OPCODE,
                          rec.index, i)
        i += 1


def run_all(records: Sequence[Record], inputs: Sequence[int]) -> Machine:
    """Run the whole table in file order, as ``fcn.102ac140`` does.

    Verified live: the interpreter fires exactly ``len(records)`` times per
    machine, in index order, with arg 1 walking the record array by 16 bytes
    (3156 of 3167 consecutive deltas are +16 across a capture; the other 11 are
    the jumps between the 12 machines). No record reads a slot at or above its
    own index, so one forward pass is sufficient and no fixpoint is needed.
    """
    m = Machine(inputs=inputs, nvars=max(len(records), 264))
    for rec in records:
        run_record(rec, m)
    return m


def extract_tagged(records: Sequence[Record], m: Machine,
                   tag: int = 1) -> List[int]:
    """``fcn.102ac310``'s output list (``0x102ac3e0…0x102ac402``): the ``+8``
    value of every record whose ``+0xc`` equals ``tag``, in record order."""
    return [m.vars[r.index] for r in records if r.tag == tag]


def l_term(records: Sequence[Record], inputs: Sequence[int]) -> int:
    """``orderFpo.Y``'s per-frame delta ``L`` (``docs/74 §76.3``)."""
    m = run_all(records, inputs)
    return extract_tagged(records, m)[L_EXTRACT_INDEX]


# ------------------------------------------------------------- self-check

def _selfcheck(path: str = DEFAULT_PCODE) -> int:
    import collections
    import random

    recs = load_pcode(path)
    print("%s: %d records" % (os.path.basename(path), len(recs)))
    tags = collections.Counter(r.tag for r in recs)
    print("  tags: %s" % dict(tags))

    used = collections.Counter()
    ptypes = collections.Counter()
    bad = 0
    for r in recs:
        try:
            ins = decode(r.words)
        except VmError as e:
            print("  record %d: %s" % (r.index, e))
            bad += 1
            continue
        if ins[-1][1] != HALT:
            print("  record %d: does not decode to a halt" % r.index)
            bad += 1
        for _off, op, a in ins:
            used[op] += 1
            if op == 1:
                ptypes[a[0]] += 1
    print("  decode to halt: %d/%d" % (len(recs) - bad, len(recs)))
    print("  opcodes present: %s" % sorted(used))
    print("  PUSH source types: %s" % dict(ptypes))
    unported = sorted(o for o in used
                      if o not in OPCODES and o not in (LABEL_WORD,
                                                        ENDLABEL_WORD))
    print("  opcodes with no mnemonic: %s" % (unported or "none"))

    t1 = [r for r in recs if r.tag == 1]
    if len(t1) > L_EXTRACT_INDEX:
        lr = t1[L_EXTRACT_INDEX]
        print("  extract[%d] (= L) is record %d:" % (L_EXTRACT_INDEX, lr.index))
        for line in format_program(lr.words):
            print("      " + line)

    # Execute the whole table. There is no captured input vector (see the
    # module docstring), so this uses a synthetic one: it proves every record
    # runs to its halt through implemented opcodes only, nothing more.
    rng = random.Random(20260817)
    inputs = [rng.randrange(-5000, 5000) or 7 for _ in range(1024)]
    fails = collections.Counter()
    m = Machine(inputs=inputs, nvars=max(len(recs), 264))
    for r in recs:
        try:
            run_record(r, m)
        except VmError as e:
            fails[str(e).split("—")[0].strip()] += 1
    print("  synthetic run: %d/%d records completed" %
          (len(recs) - sum(fails.values()), len(recs)))
    for k, v in fails.items():
        print("      %-46s x%d" % (k, v))
    return bad


if __name__ == "__main__":
    import glob
    import sys

    paths = sys.argv[1:] or sorted(glob.glob(os.path.join(PCODE_DIR, "pcode-*")))
    rc = 0
    for p in paths:
        rc |= _selfcheck(p)
        print()
    sys.exit(1 if rc else 0)
