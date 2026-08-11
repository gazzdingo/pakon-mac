#!/usr/bin/env python3
"""``AnsAstCapabilityImpl::analyze`` (``0x10227160``) — the ``ast`` tone stage.

PakonIMAu.dll ImageBase ``0x10000000`` (file VAs == cited VAs), md5
``eea9dcf78ee21d4f7c515a6c2512242d``.  This is Phase 2e of the
``ColorNegativePath::analyzeAutoTone`` port: the fifth of the six live tone
subsystems the shell in ``pakon_autotone.py`` gates.  It is the smallest —
27 functions / 4,763 bytes / 16 indirect call sites — and the only one with no
histogram, no pixel loop and no ``dataPathItems`` file behind it.

Verified bit-exact against the DLL by ``pakon_ast_golden.py``: the real
``0x10227160`` runs under Unicorn on every case and every one of the three
arrays it produces (the ``int32`` slope-index array, the ``float`` curve table
and the ``float`` output LUT) is compared dword-for-dword against this file.

WHAT ``ast`` ACTUALLY IS
========================
A **LUT-domain slope compressor**.  It reads the tone LUT the previous stages
built (``ctx+0x64d0``, a ``short*`` of ``maxValue+1`` entries), measures the
local slope of that LUT at every index with a symmetric finite difference,
and maps each slope through a fixed response curve.  It writes a
``maxValue+1``-entry **float** LUT into its own Impl at ``+0x3c``.

With the shipped constants the response curve is exactly::

    x < 1.0 :  y = 0.5x + 0.5          (a gentle lift of flat regions)
    x >= 1.0:  y = 2x / (1 + x)        (a hard roll-off of steep regions)

continuous at the knee ``x == 1``, asymptotic to 2.0.  ``x`` is the measured
absolute slope; ``y`` is what the downstream apply stage does with it.

THREE CORRECTIONS TO THE PHASE-2E BRIEF, ALL PROVEN BELOW
========================================================
1. **``ast`` does NOT write ``ctx+0x64d0``** — the brief asked this be
   confirmed, expecting ``toneHelper`` to be the sole exception.  It is not the
   sole exception: ``ast`` does not write it either.  ``0x10227160``'s only
   array store is ``mov dword [ecx + eax*4], edx`` at ``0x1022752c`` with
   ``ecx = [ebx+0x3c]`` — its **own Impl**, loaded at ``0x102273c9``.  The
   tone LUT it is handed is read-only (one ``rep movsd`` out of it at
   ``0x102273c0``, never back into it).  ``pakon_autotone.py``'s stage-5 note
   ("single call; no results struct, no ``ctx+0x64d0`` write") was already
   right, and the four writers of ``ctx+0x64d0`` remain seed / cna / dra /
   contrast.  Consequence: **inside ``analyzeAutoTone`` ``ast``'s output is not
   consumed at all** — it is stashed in the Impl for the later
   ``AnsAstCapabilityImpl::export`` (``0x1059f0c8``) apply-time path.  ``ast``
   cannot be the shadow-crush bug.
2. **``maxValue`` is a 16-bit field**, not a 32-bit one.  Both readers sign-
   extend a word: ``movsx eax, word [edi]`` at ``0x10227325`` (analyze) and
   ``mov dx, word [ecx]`` at ``0x10225bb1`` (validator).  The ctor copies it
   with ``mov cx, word [0x1059ee4c]`` / ``mov word [ebx+0x10], cx``
   (``0x1022652f``), i.e. **two bytes**, not four.
3. **The ctor does not memcpy a 32-byte blob** in the default case.  It copies
   one word plus seven dwords, field by field, from ``0x1059ee4c``
   (``0x1022652f`` … ``0x10226577``).  The 32-byte ``rep movsd ecx=8`` at
   ``0x102265b9`` is the *other* path — taken only when the ctor's trailing
   ``AnsAstParams*`` argument (``[esp+0x10c]``) is non-null, and followed
   immediately by the validator at ``0x102265c1``.  So a 32-byte copy does
   happen, but only for caller-supplied params.

THE BUILT-IN CONSTANTS — ``0x1059ee4c``, 32 bytes
=================================================
Read straight out of ``.rdata``; there is no ``ast/`` dataPathItems directory
in a real install, so these are the only values this stage ever sees unless an
``AnsAstDPI`` overrides them::

    0x1059ee4c  0000 0fff  -> maxValue           4095   (word)
    0x1059ee50  3f800000   -> nominalSlope        1.0f
    0x1059ee54  0000000a   -> slopeDelta            10   (int32)
    0x1059ee58  c1000000   -> minSlope           -8.0f
    0x1059ee5c  41000000   -> maxSlope           +8.0f
    0x1059ee60  3f000000   -> lowSlopeResponse    0.5f
    0x1059ee64  3f000000   -> highSlopeResponse   0.5f
    0x1059ee68  43fa0000   -> slopeFactor       500.0f

Only five of the eight are DPI keys — ``AnsAstDPI::readAscii``'s literals at
``0x1059ef80``…``0x1059efc0`` are ``slopeFactor``, ``highSlopeResponse``,
``lowSlopeResponse``, ``slopeDelta``, ``nominalSlope``.  ``maxValue``,
``minSlope`` and ``maxSlope`` have no DPI key at all.

THE VALIDATOR — ``0x10225bb0``
==============================
``__thiscall`` on the params block (``Impl+0x10``) with the bad-field code
returned through **``esi``**, which the *caller* sets (``lea esi, [var_1ch]``
at ``0x1022726d``); ``eax`` is ``0`` on success, ``-1`` on failure.  Six codes
for eight fields — the last two share code 6, which looks like a vendor
copy-paste slip but is what the binary does (``0x10225c7d`` and ``0x10225c8d``
both branch to the code-6 block at ``0x10225c93``)::

    1  maxValue          > 0                              (jg, signed word)
    2  nominalSlope      0 <= v <= (float)maxValue
    3  slopeDelta        1 <= v <= 100
    4  minSlope          < 0   and   maxSlope == -minSlope
    5  lowSlopeResponse  0 <= v <= 1.0
    6  highSlopeResponse 0 <= v <= 1.0
    6  slopeFactor       0 <= v  and  v * maxSlope <= (float)maxValue

The compared literals are real: ``[0x10575674] == 0.0f`` and
``[0x1058d4c0] == 1.0f``.  Note what field 6's product test buys: it is exactly
the guarantee that ``work[i]``, which the DLL uses as an **unchecked** array
index at ``0x10227529``, cannot run off the end of the curve table.

THE ALGORITHM — ``0x102273af`` … ``0x10227532``
===============================================
``n = maxValue + 1`` (``movsx``/``inc`` at ``0x10227325``), three buffers from
``AnsAstCapabilityImpl::allocateMemory`` (``0x10226ef0``): ``+0x34`` a ``2n``
byte int16 copy of the input LUT, ``+0x38`` an ``n``-entry int32 array,
``+0x3c`` the ``n``-entry float output.  A fourth, the curve table, is an
``n``-entry float scratch from ``0x10226380`` that is ``delete[]``-d before
return (``0x10227553``).

Step 1 — local slope -> index (``0x10227410``)::

    for i in delta .. n-delta-1:
        s = (padded[i+delta] - padded[i-delta]) / (2*delta)   # fild/fild/fdiv
        if s < minSlope: s = minSlope                         # fcom st(2)
        elif s > maxSlope: s = maxSlope                       # fcom st(1)
        if s < 0.0: s = -s                                    # fcom [0.0]; fchs
        work[i] = ftol(s * slopeFactor + 0.5)                 # 0x104ffe44

  The ``[0x10573c40]`` the ``fcom`` at ``0x10227453`` tests against is
  ``0.0`` (a *double*), so the ``fchs`` sequence is plain ``abs()``.  The
  ``[0x10574f40]`` added at ``0x10227465`` is ``0.5`` (also a double).
  ``0x104ffe44`` is MSVC ``_ftol``: it does ``fistp`` (round-to-nearest, the
  current mode) then subtracts and conditionally corrects by 1 in whichever
  direction moves the result **toward zero**, i.e. it truncates.  So the
  ``+ 0.5`` is a deliberate round-half-up, not a rounding-mode artefact.

  With the **shipped** constants that rounding never fires: ``slopeFactor /
  (2 * slopeDelta)`` is ``500 / 20 == 25`` exactly, so ``s * slopeFactor`` is
  always the integer ``diff * 25`` (and the clamped case is ``8 * 500 ==
  4000``).  ``+ 0.5`` then truncates straight back.  It only becomes
  observable under non-default parameters — the golden harness's
  ``round-half-even`` negative control is caught on exactly 1 of its 60
  cases for that reason, and that one is a non-default parameter set.

Step 2 — edge replication (``0x102274a0``).  Not "mirror" padding: the DLL
copies the two *edge values* outward::

    first = work[delta]; last = work[n-delta-1]
    for c in 0 .. delta-1:  work[c] = first;  work[n-1-c] = last

Step 3 — the response curve, n floats (``0x102274da``)::

    for j in 0 .. n-1:
        x = j / slopeFactor
        curve[j] = (x >= K) ? (K*x) / ((K-x)*highSlopeResponse + x)
                            : (x-K)*lowSlopeResponse + K

Step 4 — compose (``0x10227521``)::

    out[i] = curve[work[i]]          # a raw dword copy of the float bits

Step 5 — teardown (``0x10227532``).  ``mov cl, byte [eax+0xe]`` with
``eax = [ebp+0x10]``: the **capability** object's third flag byte, the same
``CAP_FLAG_BYTE_E`` ``pakon_autotone.py`` flags as unset by
``declareAutoTone``.  If it is zero the int32 ``work`` array is freed and
``+0x38`` nulled; if it is set the array is kept.  It is a debug-retention
flag and does not affect ``out``.

CALLING CONVENTION
==================
The shell calls ``ast.analyze(&st, holder, tone)`` (3 args) on the Cap wrapper
``0x1012f3f0``; the wrapper inserts the capability pointer **third** and
forwards four to the Impl (``ret 0x10``)::

    0x10227160(this=Impl)  ( AnsStatus& sret,   [ebp+0x08]
                             holder,            [ebp+0x0c]  refcounted, unused
                             AnsAstCapability*, [ebp+0x10]  only byte +0xe read
                             short* toneLut )   [ebp+0x14]

``[ebp+0x14]`` is tested against NULL at ``0x102271e8`` **before** anything
else: a null tone LUT frees the three buffers, zeroes ``+0x30`` and returns OK.
MSVC then reuses that same argument slot as the ``nominalSlope`` local
(``mov dword [ebp+0x14], edx`` at ``0x102273db``) — after the ``rep movsd`` at
``0x102273c0`` has already consumed it.

FLOATING POINT — WHY PYTHON DOUBLES ARE THE RIGHT MODEL
======================================================
Every step above is x87.  Windows initialises the x87 control word to
``0x027f``, i.e. **53-bit precision control**, so each x87 op rounds its
significand to exactly what a Python ``float`` holds; the only narrowing is the
``fstp dword`` that stores each curve entry as ``float32``.  This file
therefore computes in Python doubles and rounds explicitly at the two places
the DLL does (``_f32`` on the curve store, ``_ftol`` on the index).
``pakon_ast_golden.py`` pins this down rather than assuming it: it runs the
same cases at CW ``0x027f`` and CW ``0x037f`` (64-bit precision) and reports
whether any of the 4096 outputs move.  It also has to set the CW at all —
Unicorn's default is ``0x0000``, which is 24-bit *single* precision and gives
visibly wrong answers.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
  tools/ansel/python-pipeline/pakon_ast.py``
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# flags
# ---------------------------------------------------------------------------

#: ``AnsAstCapabilityImpl::analyze`` (``0x10227160``, 1,146 B) end to end: the
#: three buffers, the slope loop, the edge replication, the response curve and
#: the compose loop.  Verified bit-exact (every dword of ``work``, ``curve``
#: and ``out``) against the real DLL under Unicorn by ``pakon_ast_golden.py``.
AST_ANALYZE_PORTED = True

#: The eight built-in constants at ``0x1059ee4c`` and the ctor's field-by-field
#: copy into ``Impl+0x10`` (``0x102264d0`` @ ``0x1022652f``…``0x10226577``),
#: including ``maxValue`` being a 16-bit field.
AST_PARAMS_PORTED = True

#: ``0x10225bb0``, all six bad-field codes and both shared-code-6 branches.
#: Verified against the real function over a table of accept/reject cases.
AST_VALIDATOR_PORTED = True

#: MSVC ``_ftol`` (``0x104ffe44``) — truncate toward zero.  Modelled, not
#: emulated: the DLL's fistp-then-correct dance is only there because x87 has
#: no truncating store in the default rounding mode.
AST_FTOL_PORTED = True

#: ``AnsAstDPI`` (``0x102253e0`` ctor, ``0x1059ef80``… keys) — the file-driven
#: override of five of the eight constants.  No ``ast/`` dataPathItems
#: directory exists in a real install, so nothing ever drives it on this unit;
#: not ported, and not needed to reproduce shipped behaviour.
AST_DPI_PORTED = False

#: ``AnsAstCapabilityImpl::export`` (``0x1059f0c8``) — the apply-time consumer
#: of the float LUT this file produces.  Out of Phase 2e's scope: the LUT never
#: leaves the Impl during ``analyzeAutoTone``.
AST_EXPORT_PORTED = False

# ---------------------------------------------------------------------------
# addresses
# ---------------------------------------------------------------------------

AST_ANALYZE_IMPL = 0x10227160         # AnsAstCapabilityImpl::analyze, 1,146 B
AST_ANALYZE_CAP = 0x1012F3F0          # the Cap wrapper the shell calls
AST_ACQUIRE_CAP = 0x1012F4D0          # NOT the analyze wrapper -- naming fix
AST_IMPL_CTOR = 0x102264D0            # copies the defaults into Impl+0x10
AST_DPI_CTOR = 0x102253E0             # copies them into AnsAstDPI+0x2c
AST_VALIDATE = 0x10225BB0             # __thiscall(params), bad field via esi
AST_ALLOCATE_MEMORY = 0x10226EF0      # the three Impl buffers
AST_CURVE_ALLOC = 0x10226380          # new float[n] into a scoped holder
AST_DEFAULTS_VA = 0x1059EE4C          # the 32-byte constant blob

FTOL = 0x104FFE44                     # MSVC _ftol -- truncate toward zero
OP_NEW = 0x104FFD53                   # operator new
OP_NEW_ARR = 0x104FFD78               # operator new[] -> jmp operator new
OP_DELETE_ARR = 0x104FFE3E            # operator delete[]

FCONST_ZERO_F64 = 0x10573C40          # 0.0  -- the fchs/abs test at 0x10227453
FCONST_HALF_F64 = 0x10574F40          # 0.5  -- the round-half-up at 0x10227465
FCONST_ZERO_F32 = 0x10575674          # 0.0  -- the validator's lower bounds
FCONST_ONE_F32 = 0x1058D4C0           # 1.0  -- the validator's response bounds

SRC_FILE = r"\Atc\ansel\src\libAst.ansel\AnsAstCapabilityImpl.cpp"
FUNC_NAME = "AnsAstCapabilityImpl::analyze"

#: Impl field offsets.  ``+0x10``…``+0x2c`` is the params block the validator
#: takes as its ``this``; ``+0x30``…``+0x3c`` is the working set.
IMPL_PARAMS = 0x10          # -> AstParams, 32 bytes
IMPL_MAX_VALUE = 0x10       # int16
IMPL_NOMINAL_SLOPE = 0x14   # f32
IMPL_SLOPE_DELTA = 0x18     # int32
IMPL_MIN_SLOPE = 0x1C       # f32
IMPL_MAX_SLOPE = 0x20       # f32
IMPL_LOW_RESPONSE = 0x24    # f32
IMPL_HIGH_RESPONSE = 0x28   # f32
IMPL_SLOPE_FACTOR = 0x2C    # f32
IMPL_LENGTH = 0x30          # int32   n == maxValue + 1
IMPL_PADDED = 0x34          # int16*  the copy of the input tone LUT
IMPL_WORK = 0x38            # int32*  the slope-index array
IMPL_OUT = 0x3C             # float*  the output LUT

#: ``analyzeAutoTone``'s ``cap+0xe``.  Read at ``0x10227535``; when clear, the
#: int32 work array is freed and ``Impl+0x38`` nulled before return.
CAP_KEEP_WORK_BYTE = 0x0E

# ---------------------------------------------------------------------------
# the constants
# ---------------------------------------------------------------------------

#: The literal 32 bytes at ``0x1059ee4c``.
AST_DEFAULTS_BLOB = bytes.fromhex(
    "ff0f0000"      # maxValue           4095 (word at +0, +2 is padding)
    "0000803f"      # nominalSlope        1.0f
    "0a000000"      # slopeDelta            10
    "000000c1"      # minSlope           -8.0f
    "00000041"      # maxSlope           +8.0f
    "0000003f"      # lowSlopeResponse    0.5f
    "0000003f"      # highSlopeResponse   0.5f
    "0000fa43"      # slopeFactor       500.0f
)

#: The five keys ``AnsAstDPI::readAscii`` recognises (``0x1059ef80``…).  The
#: other three constants have no file representation at all.
AST_DPI_KEYS = ("slopeFactor", "highSlopeResponse", "lowSlopeResponse",
                "slopeDelta", "nominalSlope")

# ---------------------------------------------------------------------------
# float helpers
# ---------------------------------------------------------------------------


def _f32(x: float) -> float:
    """``fstp dword`` — round a 53-bit value to ``float32``, ties to even.

    Overflow saturates to +/-inf, which is what the x87 store does with the
    default (all-masked) control word rather than raising.
    """
    try:
        return struct.unpack("<f", struct.pack("<f", x))[0]
    except OverflowError:
        return math.inf if x > 0 else -math.inf


def _ftol(x: float) -> int:
    """``0x104ffe44`` — MSVC ``_ftol``, truncation toward zero.

    The DLL gets there the long way (``fistp`` in round-to-nearest, then
    ``fild`` it back, subtract, and ``sbb``/``adc`` 1 off the 64-bit result
    when the residue has the sign that means the round went away from zero).
    The net effect is C's float-to-int conversion, and ``int()`` is that.
    """
    return int(x)


def _i16(v: int) -> int:
    """``movsx eax, word`` / ``mov dx, word`` — take the low word, signed.

    Both readers of ``maxValue`` sign-extend a 16-bit load (``0x10227325``,
    ``0x10225bb1``), so a stored 0x8000 is -32768 to this stage, not 32768.
    """
    return struct.unpack("<h", struct.pack("<H", int(v) & 0xFFFF))[0]


#: x87's "real indefinite" — the QNaN an invalid operation produces with the
#: exception masked.  Its **sign bit is set** (``0xffc00000`` as ``float32``),
#: unlike Python's ``math.nan`` (``0x7fc00000``).  The golden harness caught
#: exactly this: the DLL stored ``0000c0ff`` where the port stored ``0000c07f``.
X87_INDEFINITE = -math.nan


def _x87_div(num: float, den: float) -> float:
    """``fdivp`` with all exceptions masked — no Python ``ZeroDivisionError``.

    Reachable: ``nominalSlope == 0`` is a value the validator **accepts** (its
    test is ``0 <= v <= maxValue``), and it makes the ``j == 0`` curve entry
    ``0.0 / 0.0`` — invalid operation, which x87 answers with
    ``X87_INDEFINITE``.  ``k / 0.0`` is instead a masked divide-by-zero, which
    gives a correctly-signed infinity.  Python raises on both.
    """
    if den == 0.0:
        if num == 0.0:
            return X87_INDEFINITE
        return math.copysign(math.inf, num) * math.copysign(1.0, den)
    return num / den


# ---------------------------------------------------------------------------
# the params block
# ---------------------------------------------------------------------------


@dataclass
class AstParams:
    """``Impl+0x10``, 32 bytes — the validator's ``this``.

    ``max_value`` is deliberately typed as the 16-bit field it is; everything
    that reads it sign-extends a word.
    """

    max_value: int = 4095          # +0x00  int16
    nominal_slope: float = 1.0     # +0x04  f32
    slope_delta: int = 10          # +0x08  int32
    min_slope: float = -8.0        # +0x0c  f32
    max_slope: float = 8.0         # +0x10  f32
    low_slope_response: float = 0.5   # +0x14  f32
    high_slope_response: float = 0.5  # +0x18  f32
    slope_factor: float = 500.0    # +0x1c  f32

    @classmethod
    def from_bytes(cls, blob: bytes) -> "AstParams":
        """Decode the 32-byte layout — ``h`` for maxValue, then ``f i 5f``."""
        (mv,) = struct.unpack_from("<h", blob, 0x00)
        nom, delta, lo, hi, lores, hires, fac = struct.unpack_from(
            "<f i f f f f f", blob, 0x04)
        return cls(mv, nom, delta, lo, hi, lores, hires, fac)

    def to_bytes(self) -> bytes:
        """Re-encode; ``+0x02`` is padding the ctor's ``mov word`` never sets."""
        return (struct.pack("<Hh", self.max_value & 0xFFFF, 0)
                + struct.pack("<f i f f f f f",
                              self.nominal_slope, self.slope_delta,
                              self.min_slope, self.max_slope,
                              self.low_slope_response,
                              self.high_slope_response, self.slope_factor))

    @classmethod
    def defaults(cls) -> "AstParams":
        """The compiled-in constants at ``0x1059ee4c``."""
        if not AST_PARAMS_PORTED:
            raise RuntimeError("AST_PARAMS_PORTED is False")
        return cls.from_bytes(AST_DEFAULTS_BLOB)


class AstParamsInvalid(ValueError):
    """What ``0x10227160`` turns a non-zero ``0x10225bb0`` into.

    The DLL builds ``"Bad field(#N) in AnsAstParameter structure!"`` at
    ``0x10227276`` (the ctor uses the near-identical ``"... in AnsAstParams
    structure!"`` at ``0x102265f4``) and returns it as an ``AnsStatus``, line
    ``0x69`` of ``AnsAstCapabilityImpl.cpp``.
    """

    def __init__(self, field: int):
        self.field = field
        super().__init__(
            f"Bad field(#{field}) in AnsAstParameter structure! "
            f"[{FUNC_NAME}, {SRC_FILE}:105]")


def validate_params(p: AstParams) -> int:
    """``0x10225bb0`` — returns the bad-field code, or ``0`` if it accepts.

    The DLL returns ``-1``/``0`` in ``eax`` and the code through ``esi``; the
    two carry the same one bit of information, so this returns the code.

    Every comparison below is a ``float32`` one in the DLL (``fld dword`` /
    ``fcomp dword``), and ``(float)maxValue`` is materialised by ``fild`` then
    ``fstp dword`` at ``0x10225bde``/``0x10225be1`` — i.e. it really is rounded
    to ``float32`` before the comparison, which matters once ``maxValue``
    exceeds 2**24.  It cannot here (it is an int16), but the ``_f32`` is kept
    because the same rounded value is reused by the field-6 product test.
    """
    if not AST_VALIDATOR_PORTED:
        raise RuntimeError("AST_VALIDATOR_PORTED is False")

    # 1  0x10225bb1: mov dx, word [ecx]; test dx, dx; jg
    mv = _i16(p.max_value)
    if not mv > 0:
        return 1

    max_value_f = _f32(float(mv))          # 0x10225bde fild / 0x10225be1 fstp

    # 2  0x10225bc4: 0 <= nominalSlope <= (float)maxValue
    nom = _f32(p.nominal_slope)
    if not nom >= 0.0:
        return 2
    if not nom <= max_value_f:
        return 2

    # 3  0x10225bf5: 1 <= slopeDelta <= 100
    if p.slope_delta < 1 or p.slope_delta > 100:
        return 3

    # 4  0x10225c0a: minSlope < 0 and maxSlope == -minSlope
    lo = _f32(p.min_slope)
    hi = _f32(p.max_slope)
    if not lo < 0.0:
        return 4
    if not -lo == hi:                      # fchs then fucompp
        return 4

    # 5  0x10225c2f: 0 <= lowSlopeResponse <= 1.0
    lores = _f32(p.low_slope_response)
    if not (0.0 <= lores <= 1.0):
        return 5

    # 6  0x10225c4f: 0 <= highSlopeResponse <= 1.0
    hires = _f32(p.high_slope_response)
    if not (0.0 <= hires <= 1.0):
        return 6

    # 6  0x10225c6f: 0 <= slopeFactor, and slopeFactor*maxSlope <= maxValue.
    #    Shares code 6 with the field above -- 0x10225c7d and 0x10225c8d both
    #    branch to the same block at 0x10225c93.  Kept as the binary has it.
    fac = _f32(p.slope_factor)
    if not fac >= 0.0:
        return 6
    if not _f32(fac * hi) <= max_value_f:
        return 6

    return 0


# ---------------------------------------------------------------------------
# the analysis
# ---------------------------------------------------------------------------


@dataclass
class AstResult:
    """Everything ``0x10227160`` leaves behind in the Impl, plus the scratch.

    ``curve`` is the ``n``-entry float table ``0x10226380`` allocates and
    ``0x10227553`` frees before returning — it never reaches the Impl, but it
    is the numerically delicate part of the stage, so it is returned here and
    the golden harness snapshots the DLL's copy at ``0x1022751c`` to compare.
    """

    length: int                 # Impl+0x30
    padded: list[int]           # Impl+0x34, int16
    work: list[int]             # Impl+0x38, int32 -- None-ed if keep_work=False
    out: list[float]            # Impl+0x3c, float32
    curve: list[float]          # the freed scratch table
    work_freed: bool = False    # cap+0xe was clear

    def out_bytes(self) -> bytes:
        """The exact ``4n`` bytes at ``Impl+0x3c`` — for bit-exact diffing."""
        return b"".join(struct.pack("<f", v) for v in self.out)

    def curve_bytes(self) -> bytes:
        return b"".join(struct.pack("<f", v) for v in self.curve)


def ast_analyze(params: AstParams, tone_lut, *,
                keep_work: bool = True) -> AstResult | None:
    """``AnsAstCapabilityImpl::analyze`` (``0x10227160``).

    ``tone_lut`` is the ``short*`` the shell threads through ``ctx+0x64d0`` —
    a sequence of at least ``maxValue+1`` int16 values, or ``None`` for the
    null-pointer case.  ``keep_work`` is the capability's ``+0xe`` byte.

    Returns ``None`` for the null-tone early-out (``0x102271e8``), which the
    DLL reports as a plain OK status with ``Impl+0x30`` left at 0 and all three
    buffers freed.  Raises ``AstParamsInvalid`` where the DLL returns the
    "Bad field" status.
    """
    if not AST_ANALYZE_PORTED:
        raise RuntimeError("AST_ANALYZE_PORTED is False")

    # 0x102271ab..0x102271eb -- free the three buffers, Impl+0x30 = 0. Then
    # 0x102271ee: a null tone LUT is not an error, it is a no-op return.
    if tone_lut is None:
        return None

    # 0x10227261: validate before anything is allocated.
    bad = validate_params(params)
    if bad:
        raise AstParamsInvalid(bad)

    # 0x10227325: movsx eax, word [edi] ; inc eax
    n = _i16(params.max_value) + 1
    delta = params.slope_delta

    # 0x10227336 -> 0x10226ef0: new short[n] (2n bytes), new int[n], new float[n]
    # 0x102273c0: rep movsd -- 2n bytes out of the caller's LUT into Impl+0x34.
    padded = [int(v) for v in tone_lut[:n]]
    if len(padded) < n:
        raise ValueError(
            f"tone LUT has {len(padded)} entries, analyze copies {n}")

    two_delta = float(2 * delta)              # fild dword [ebp-0x30]
    min_slope = _f32(params.min_slope)        # fld dword [ebx+0x1c]
    max_slope = _f32(params.max_slope)        # fld dword [ebx+0x20]
    factor = _f32(params.slope_factor)        # [ebx+0x2c] -> var_30h
    nominal = _f32(params.nominal_slope)      # [ebx+0x14] -> the [ebp+0x14] slot
    low_resp = _f32(params.low_slope_response)    # [ebx+0x24] -> var_3ch
    high_resp = _f32(params.high_slope_response)  # [ebx+0x28] -> var_40h

    # -- step 1: local slope -> index, 0x10227410 --------------------------
    work = [0] * n
    for i in range(delta, n - delta):
        diff = padded[i + delta] - padded[i - delta]   # movsx/movsx/sub
        s = diff / two_delta                           # fild ; fdiv st(3)
        if s < min_slope:                              # fcom st(2)
            s = min_slope
        elif s > max_slope:                            # fcom st(1)
            s = max_slope
        if s < 0.0:                                    # fcom [0x10573c40]
            s = -s                                     # fchs
        work[i] = _ftol(s * factor + 0.5)              # fmul ; fadd ; _ftol

    # -- step 2: edge replication, 0x102274a0 ------------------------------
    # Not mirroring: the two edge values are copied outward unchanged.
    if n - delta - 1 >= delta:
        first = work[delta]                   # mov ecx, [edi + esi*4]
        last = work[n - delta - 1]            # mov ecx, [edi + edx*4 - 4]
        for c in range(delta):
            work[c] = first
            work[n - 1 - c] = last

    # -- step 3: the response curve, 0x102274da ----------------------------
    curve = [0.0] * n
    for j in range(n):
        x = _x87_div(float(j), factor)                 # fild ; fdiv
        if x < nominal:                                # fcom [ebp+0x14]
            v = (x - nominal) * low_resp + nominal
        else:
            v = _x87_div(nominal * x,
                         (nominal - x) * high_resp + x)
        curve[j] = _f32(v)                             # fstp dword

    # -- step 4: compose, 0x10227521 ---------------------------------------
    # `mov edx, [esi + edx*4]` is unchecked. The validator's field-6 product
    # test (slopeFactor * maxSlope <= maxValue) is what keeps it in range;
    # anything that got past it and still overruns is a real DLL memory bug,
    # so raise rather than silently wrap the way Python's negative indices do.
    out = [0.0] * n
    for i in range(n):
        idx = work[i]
        if not 0 <= idx < n:
            raise IndexError(
                f"work[{i}] == {idx} indexes outside the {n}-entry curve "
                f"table; the DLL reads out of bounds here (0x10227529)")
        out[i] = curve[idx]

    # -- step 5: teardown, 0x10227532 --------------------------------------
    return AstResult(length=n, padded=padded,
                     work=work if keep_work else None,
                     out=out, curve=curve, work_freed=not keep_work)


# ---------------------------------------------------------------------------
# the shell hookup
# ---------------------------------------------------------------------------


class AstSubsystem:
    """The object ``pakon_autotone.AutoToneSubsystems.ast_analyze`` delegates to.

    Holds what the DLL holds in ``Impl+0x30``…``+0x3c`` across calls, so a
    caller can read the LUT back the way ``AnsAstCapabilityImpl::export``
    would.  ``analyzeAutoTone`` itself never reads it.
    """

    def __init__(self, params: AstParams | None = None, *,
                 keep_work: bool = True):
        self.params = params if params is not None else AstParams.defaults()
        self.keep_work = keep_work
        self.result: AstResult | None = None

    def analyze(self, tone_lut) -> AstResult | None:
        self.result = ast_analyze(self.params, tone_lut,
                                  keep_work=self.keep_work)
        return self.result


def main() -> None:
    print(f"AnsAstCapabilityImpl::analyze {AST_ANALYZE_IMPL:#010x}  (1,146 B)")
    print(f"  Cap wrapper  {AST_ANALYZE_CAP:#010x}   "
          f"acquire {AST_ACQUIRE_CAP:#010x} (NOT the analyze wrapper)")
    print(f"  constants    {AST_DEFAULTS_VA:#010x}  32 B, compiled in "
          f"(no ast/ dataPathItems directory exists)")
    print(f"  validator    {AST_VALIDATE:#010x}   "
          f"allocate {AST_ALLOCATE_MEMORY:#010x}  curve {AST_CURVE_ALLOC:#010x}")
    print()
    p = AstParams.defaults()
    for name in ("max_value", "nominal_slope", "slope_delta", "min_slope",
                 "max_slope", "low_slope_response", "high_slope_response",
                 "slope_factor"):
        print(f"    {name:<20} {getattr(p, name)!r}")
    print(f"    validate_params -> {validate_params(p)} (0 == accepted)")
    print()
    print(f"  ANALYZE={AST_ANALYZE_PORTED} PARAMS={AST_PARAMS_PORTED} "
          f"VALIDATOR={AST_VALIDATOR_PORTED} FTOL={AST_FTOL_PORTED} "
          f"DPI={AST_DPI_PORTED} EXPORT={AST_EXPORT_PORTED}")
    print()

    n = p.max_value + 1
    for label, lut in (
        ("identity ramp   ", [i for i in range(n)]),
        ("flat            ", [1000] * n),
        ("descending      ", [n - 1 - i for i in range(n)]),
        ("4x (steep)      ", [min(32767, 4 * i) for i in range(n)]),
    ):
        r = ast_analyze(p, lut)
        print(f"    {label} work[{n//2}]={r.work[n//2]:>5}  "
              f"out[0]={r.out[0]:.6f}  out[{n//2}]={r.out[n//2]:.6f}  "
              f"out[{n-1}]={r.out[n-1]:.6f}")
    print()
    print("    curve: knee at x == nominalSlope; "
          f"curve[0]={ast_analyze(p, [0]*n).curve[0]:.6f} "
          f"curve[500]={ast_analyze(p, [0]*n).curve[500]:.6f} "
          f"curve[4000]={ast_analyze(p, [0]*n).curve[4000]:.6f}")


if __name__ == "__main__":
    main()
