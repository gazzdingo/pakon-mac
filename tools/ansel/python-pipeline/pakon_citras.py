#!/usr/bin/env python3
r"""``AnsCitrasCapabilityImpl::analyze`` (``0x10223a20``) — Phase 2f.

PakonIMAu.dll ImageBase ``0x10000000`` (file VAs == cited VAs).  This is the
sixth and smallest of the six ``ColorNegativePath::analyzeAutoTone`` subsystems:
stage 7 of the shell in ``pakon_autotone.py``, reached through the Cap wrapper
``0x1012c490``.

SCOPE — ANALYZE ONLY, NOT APPLY
==============================
The flag in here is ``CITRAS_ANALYZE_PORTED``, deliberately not a bare
``CITRAS_PORTED``, because citras has two entirely separate halves and only one
of them is here:

* **analyze** (this file).  ``0x10223a20``, 627 bytes; with its two callees and
  the CRT/refcount helpers behind them, 24 functions / 3,674 bytes.  It
  validates the capability's eight built-in scalar parameters, allocates a
  ``short[lutSize]``, and ``memcpy``s the shell's tone LUT into it.  There is no
  arithmetic in it at all — not one add, multiply or table lookup on pixel or
  LUT data.  It is a validated store.
* **apply** — an entirely separate file, ``pakon_citras_apply.py``, not this
  one.  That is the per-pixel operator (``ImaCitrasOperationBase`` ->
  ``ImaCitrasOperationT<short int>`` -> ``ImaCitrasOpBase`` -> ``ImaI16CitrasOp``
  plus ``AnsImaCitrasAggregate`` and ``AnsCitrasOperand``), dispatched from a
  different call graph than ``analyzeAutoTone``'s and containing the genuine
  unnamed math.  Phase 3.  ``CITRAS_APPLY_PORTED`` below is imported straight
  from ``pakon_citras_apply``'s own umbrella flag (the same pattern
  ``pakon_autotone.py`` uses for ``pakon_dra.DRA_ANALYZE_PORTED``) — this file
  does not restate or duplicate it.  As of this writing five of that file's
  six real pieces are ported and Unicorn-verified (object layout, setToneLut,
  tone-compose, avoidance-blend, luminance); ``validate()`` is the one
  still-``False`` piece blocking the umbrella — see
  ``pakon_citras_apply.CITRAS_APPLY_VALIDATE_PORTED``'s own comment for
  exactly why.

An earlier pass cited ``analyze`` as ``0x10223860``.  That address decodes
mid-instruction inside the neighbouring ``allocateMemory`` (``0x10223810``) and
is not an entry point.  ``0x10223a20`` is the entry: valid ``push ebp; mov ebp,
esp`` + SEH prologue, ``ret 0x10`` matching the Cap wrapper's four pushed args,
and it is the function that names itself ``"AnsCitrasCapabilityImpl::analyze"``
(``0x1059ed5c``).

THERE IS NO DPI FILE
====================
Unlike cna / fugc / dtt, ``citras`` has no ``dataPathItems/citras/`` directory
in a real install, and nothing in ``analyze``'s reachable set opens one.  The
eight parameters are compiled-in constants: the impl's constructor
(``0x10223310``) copies them out of the static block at ``0x1058f458`` at
``0x1022336f``..``0x102233c3`` — an ``fld``/``fstp`` pair for the double and
seven word/byte moves — straight into ``impl+0x10``.  The ``default`` column
of ``CITRAS_PARAMS_LAYOUT`` below is that block, read out of the image and
re-checked by running the ctor's own copy loop under Unicorn.

(``0x1059ecac`` does hold the string ``"citras-default-default"``, which looks
like a ``.dpi`` stem.  It is the *name* the capability registers under; no code
reachable from ``analyze`` turns it into a path or opens it.)

THE OBJECT — ``AnsCitrasCapabilityImpl``
========================================
``this`` is ``*(cap+0x10)``, forwarded by the Cap wrapper at ``0x1012c4dd``::

    +0x00  vftable
    +0x04  (zeroed by the ctor)
    +0x08  AnsStatus            refcounted, the impl's own last status
    +0x0c  (name/vftable-ish literal, 0x1059ec90)
    +0x10  AnsCitrasParams      the eight scalars -- CITRAS_PARAMS_LAYOUT
    +0x28  AnsCitrasResults     {lutSize, ToneLut} -- the pair analyzeAutoTone
    +0x2c                       already models in AUTOTONE_WORK_LAYOUT
    +0x30  (zeroed by the ctor)

``+0x28``/``+0x2c`` are exactly ``AnsCitrasResults`` as
``pakon_autotone.AUTOTONE_WORK_LAYOUT`` records it — proven a second way here by
the vendor ``ostream`` dumper at ``0x10166cd0``, which prints ``"  lutSize = "``
(``0x1057c354``) from ``[obj+0]`` and ``"  ToneLut = "`` (``0x1058f48c``) from
``[obj+4]``, walks ``lutSize`` entries at ``mov dx, word [ecx + edi*2]``
(``0x10166dbb``) and prints ``"NULL"`` when the pointer is null.  **That
``word``, and the ``lea ecx, [edi+edi]`` byte count at ``0x10223c01``, are what
prove the LUT is 16-bit**, not 8 or 32.

WHAT ``analyze`` ACTUALLY DOES — ``0x10223a20``..``0x10223c93``
==============================================================
``analyze(AnsStatus& sret, holder, int lutSize, const unsigned short* tone)``,
thiscall, ``ret 0x10``::

    0x10223a64  if (this->ToneLut) { delete[] this->ToneLut;
                                     this->ToneLut = NULL; }
    0x10223a7e  this->lutSize = 0;
    0x10223a7b  if (tone == NULL) return OK;              // <- 0x10223a83
    0x10223b09  st = this->validateParameters(            // 0x10223180
                        "AnsCitrasCapabilityImpl::analyze", __FILE__, 183);
    0x10223b84  if (st != OK) return st;
    0x10223b90  this->lutSize = lutSize;
    0x10223b93  st = this->allocateMemory(lutSize);       // 0x10223810
    0x10223bdc  if (st != OK) return st;
    0x10223c0c  memcpy(this->ToneLut, tone, lutSize * 2); // rep movsd + movsb
    0x10223c24  return OK;

Three details that are easy to get wrong and are all modelled:

* the ``delete[]`` and the ``lutSize = 0`` happen **before** the null test and
  before validation, so *every* failure path — including a parameter that fails
  validation — still leaves the object with no LUT and ``lutSize == 0``.
* ``this->lutSize`` is written **before** ``allocateMemory`` is called
  (``0x10223b90``), and ``allocateMemory`` puts it back to 0 only on an
  allocation failure (``0x10223886``).
* the copy is a byte copy of ``lutSize * 2`` bytes: ``rep movsd`` over
  ``(lutSize*2) >> 2`` dwords then ``rep movsb`` over ``(lutSize*2) & 3``, i.e.
  an odd ``lutSize`` leaves a real two-byte ``movsb`` tail.  Modelled, and
  covered by the golden.

``validateParameters`` — ``0x10223180``
=======================================
Eight checks, in this exact order, short-circuiting on the first failure.  Every
one of them reports through ``0x1001ed90(&sret, 0x69, func, msg, file, line)``
with the **caller's** name/file/line — so a bad parameter surfaces as
``AnsCitrasCapabilityImpl::analyze`` line 183, not as the validator's own.  The
messages are the image's own literals; see ``CITRAS_PARAM_CHECKS``.

The ``sigma`` test is ``fld [this+0x10]; fcomp [0x10573c40]; fnstsw; test ah,
0x41; jp ok``.  ``[0x10573c40]`` is the double ``0.0``.  The ``jp`` form passes
on *greater* **and on unordered** — a NaN sigma is accepted by the DLL.  The
port reproduces that by failing only on ``sigma <= 0.0`` (False for NaN), not by
asserting ``sigma > 0.0``.

``allocateMemory`` — ``0x10223810``
===================================
``this->ToneLut = new unsigned short[lutSize]`` (``operator new[]``
``0x104ffd78`` -> ``0x104ffd53``, size ``lutSize + lutSize``).  On success,
returns OK and nothing else changes.  On a null return it sets
``this->lutSize = 0`` and builds ``"Failed in 'new'."`` (``0x10576a24``) with
code ``0xca`` at ``AnsCitrasCapabilityImpl::allocateMemory`` line 303.

Verification
------------
``pakon_citras_golden.py`` runs the real ``0x10223a20`` under Unicorn against
this file, case for case: the object's ``lutSize``/``ToneLut``, the copied
bytes, which allocations and frees happened, and the exact
``(code, func, message, file, line)`` of every failure status.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
  tools/ansel/python-pipeline/pakon_citras.py``
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# flags
# ---------------------------------------------------------------------------

# AnsCitrasCapabilityImpl::analyze (0x10223a20, 627 B) end to end: the free,
# the null-tone short circuit, validateParameters (0x10223180), the lutSize
# write, allocateMemory (0x10223810) and the lutSize*2 byte copy.  Reachability
# for the whole thing is 24 fns / 3,674 B / 17 indirect (tools/re/reachability.py
# walk 0x10223a20); the 21 not named here are the CRT allocator, the AnsStatus
# refcount helpers (0x100065e0 / 0x100012e0 / 0x10001530 / 0x10001560 /
# 0x10001580) and the 0x1001ed90 status builder.
# Verified against the DLL by pakon_citras_golden.py.
CITRAS_ANALYZE_PORTED = True

# The eight compiled-in scalars and their defaults, copied out of 0x1058f458 by
# the impl ctor at 0x1022336f..0x102233c3.  No .dpi file exists for citras.
CITRAS_PARAMS_DEFAULTS_PORTED = True

# The eight validation checks of 0x10223180, in order, with their literal
# messages, error code 0x69 and the caller-attributed file/line.
CITRAS_PARAMS_VALIDATE_PORTED = True

# AnsCitrasCapabilityImpl::allocateMemory (0x10223810): new unsigned short
# [lutSize], and the "Failed in 'new'." status (code 0xca, line 303) it builds
# when the allocator returns null.
CITRAS_ALLOCATE_MEMORY_PORTED = True

# CITRAS_APPLY_PORTED used to be a hardcoded `False` here, restating (and,
# once pakon_citras_apply.py's own umbrella started moving, silently at risk
# of disagreeing with) that file's own flag of the same name -- the same
# "duplicated instead of imported" bug pakon_autotone.py once had for
# pakon_dra.DRA_ANALYZE_PORTED, fixed there by importing rather than
# restating.  Fixed the same way here, defined just below CitrasStatus
# rather than up here or at the top of the file -- see that definition's own
# comment for exactly why the placement (and a companion fix on the
# pakon_citras_apply.py side) matters and isn't just cosmetic.

# ---------------------------------------------------------------------------
# addresses
# ---------------------------------------------------------------------------

CITRAS_ANALYZE = 0x10223A20          # AnsCitrasCapabilityImpl::analyze
CITRAS_VALIDATE_PARAMETERS = 0x10223180   # ...::validateParameters
CITRAS_ALLOCATE_MEMORY = 0x10223810       # ...::allocateMemory
CITRAS_IMPL_CTOR = 0x10223310             # installs CITRAS_PARAMS_DEFAULTS
CITRAS_CAP_WRAPPER = 0x1012C490           # the Cap entry analyzeAutoTone calls

CITRAS_PARAMS_DEFAULT_BLOCK = 0x1058F458  # the static the ctor copies from
CITRAS_PARAMS_DUMPER = 0x10166B50         # ostream printer, names the 8 fields
CITRAS_RESULTS_DUMPER = 0x10166CD0        # ostream printer for {lutSize,ToneLut}

OP_NEW_ARRAY = 0x104FFD78        # operator new[]  -> jmp operator new
OP_DELETE_ARRAY = 0x104FFE3E     # operator delete[]
MAKE_STATUS = 0x1001ED90         # (sret, code, func, msg, file, line)
FCOMP_ZERO = 0x10573C40          # the double 0.0 sigma is compared against

#: Impl-relative offsets.
IMPL_STATUS = 0x08
IMPL_PARAMS = 0x10
IMPL_LUT_SIZE = 0x28      # AnsCitrasResults.lutSize
IMPL_TONE_LUT = 0x2C      # AnsCitrasResults.ToneLut
IMPL_SIZE = 0x34

SRC_FILE = r"\Atc\ansel\src\libCitras.ansel\AnsCitrasCapabilityImpl.cpp"
FUNC_ANALYZE = "AnsCitrasCapabilityImpl::analyze"
FUNC_ALLOCATE_MEMORY = "AnsCitrasCapabilityImpl::allocateMemory"

#: `push 0xb7` at 0x10223af4 — the line analyze attributes validation errors to.
ANALYZE_VALIDATE_LINE = 0xB7            # 183
#: `push 0x12f` at 0x10223865.
ALLOCATE_MEMORY_FAIL_LINE = 0x12F       # 303
#: `push 0x69` / `push 0xca` — the AnsStatus code each site builds.
VALIDATE_ERROR_CODE = 0x69              # 105
ALLOCATE_ERROR_CODE = 0xCA              # 202

TONE_LUT_ENTRY_BYTES = 2   # `lea ecx, [edi+edi]` @ 0x10223c01

# ---------------------------------------------------------------------------
# AnsCitrasParams — impl+0x10, 0x18 bytes
#
# Offsets are read off the vendor dumper 0x10166b50, which pairs each
# `[obj + off]` load with its own "  name = " literal and a typed operator<<:
#
#     +0x00  fld qword [ebx]        "  sigma = "                 0x1057c258
#     +0x08  mov ax,  [ebx+8]       "  blockSize = "             0x1057c248
#     +0x0a  movzx edx, byte [ebx+0xa] "  minAvoidance = "       0x1057c234
#     +0x0c  mov cx,  [ebx+0xc]     "  maxGradient = "           0x1057c220
#     +0x0e  mov ax,  [ebx+0xe]     "  lowGradientThreshold = "  0x1057c204
#     +0x10  mov dx,  [ebx+0x10]    "  highGradientThreshold = " 0x1057c1e8
#     +0x12  mov cx,  [ebx+0x12]    "  minValue = "              0x1057c1d8
#     +0x14  mov ax,  [ebx+0x14]    "  maxValue = "              0x1057c1c8
#
# and confirmed a second time by validateParameters (0x10223180) touching the
# same eight slots at the same widths, and a third time by the ctor's copy out
# of 0x1058f458.  `minAvoidance` is the only unsigned one -- both the dumper
# (`movzx`) and the check (`cmp byte [ecx+0x1a], 0x64; jbe`) treat it unsigned.
# ---------------------------------------------------------------------------

#: (offset, name, kind, default).  Defaults are the image bytes at
#: CITRAS_PARAMS_DEFAULT_BLOCK, in the order the ctor copies them.
CITRAS_PARAMS_LAYOUT: tuple[tuple[int, str, str, object], ...] = (
    (0x00, "sigma", "f64", 8.25),                 # <- 0x1058f458
    (0x08, "blockSize", "i16", 8),                # <- 0x1058f460
    (0x0A, "minAvoidance", "u8", 70),             # <- 0x1058f462
    (0x0C, "maxGradient", "i16", 4095),           # <- 0x1058f464
    (0x0E, "lowGradientThreshold", "i16", -1),    # <- 0x1058f468
    (0x10, "highGradientThreshold", "i16", -1),   # <- 0x1058f46c
    (0x12, "minValue", "i16", 0),                 # <- 0x1058f470
    (0x14, "maxValue", "i16", 4095),              # <- 0x1058f474
)

CITRAS_PARAMS_SIZE = 0x18   # 0x16 used, padded to the double's alignment

#: The source offsets inside CITRAS_PARAMS_DEFAULT_BLOCK, which is NOT packed
#: the same way the object is: the ctor reads 0x460/0x462/0x464 then strides by
#: four for the last four words (0x468, 0x46c, 0x470, 0x474).
CITRAS_PARAMS_DEFAULT_SOURCE: tuple[tuple[str, int], ...] = (
    ("sigma", 0x00), ("blockSize", 0x08), ("minAvoidance", 0x0A),
    ("maxGradient", 0x0C), ("lowGradientThreshold", 0x10),
    ("highGradientThreshold", 0x14), ("minValue", 0x18), ("maxValue", 0x1C),
)

#: struct format per ``CITRAS_PARAMS_LAYOUT`` kind.
CITRAS_PARAM_FORMATS = {"f64": "<d", "i16": "<h", "u8": "<B"}


@dataclass
class CitrasParams:
    """``AnsCitrasParams`` at ``impl+0x10``, defaults as the ctor installs them."""

    sigma: float = 8.25
    blockSize: int = 8
    minAvoidance: int = 70
    maxGradient: int = 4095
    lowGradientThreshold: int = -1
    highGradientThreshold: int = -1
    minValue: int = 0
    maxValue: int = 4095

    def pack(self) -> bytearray:
        buf = bytearray(CITRAS_PARAMS_SIZE)
        for off, name, kind, _default in CITRAS_PARAMS_LAYOUT:
            struct.pack_into(CITRAS_PARAM_FORMATS[kind], buf, off, getattr(self, name))
        return buf

    @classmethod
    def unpack(cls, buf: bytes) -> "CitrasParams":
        kw = {name: struct.unpack_from(CITRAS_PARAM_FORMATS[kind], buf, off)[0]
              for off, name, kind, _default in CITRAS_PARAMS_LAYOUT}
        return cls(**kw)


def default_params() -> CitrasParams:
    """The eight values ``0x1022336f``..``0x102233c3`` copies from the image."""
    return CitrasParams(**{name: default
                           for _off, name, _kind, default in CITRAS_PARAMS_LAYOUT})


# ---------------------------------------------------------------------------
# AnsStatus, as this subsystem builds it
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CitrasStatus:
    """One ``0x1001ed90(&sret, code, func, msg, file, line)`` construction.

    OK is ``None`` — the ``[0x106b5bd4]`` singleton, which is null in the
    shipped image, exactly as ``pakon_autotone`` and its golden model it.  Every
    caller here is ``if (status != OK) return status``, so truthiness is the
    whole contract and this object is deliberately truthy.
    """

    code: int
    func: str
    message: str
    file: str = SRC_FILE
    line: int = 0

    def __bool__(self) -> bool:
        return True

    def __str__(self) -> str:
        return f"{self.message} [{self.func}, {self.file}:{self.line}] ({self.code})"


# CITRAS_APPLY_PORTED -- the real, single source of truth is
# pakon_citras_apply.CITRAS_APPLY_PORTED; imported here (not restated) per
# the pakon_autotone.py / pakon_dra.DRA_ANALYZE_PORTED precedent. A plain
# top-of-file `from pakon_citras_apply import CITRAS_APPLY_PORTED` used to
# deadlock in one import order (pakon_citras_apply.py itself did `from
# pakon_citras import CitrasStatus` at ITS OWN module level -- a genuine
# circular import, confirmed by actually triggering it: `import
# pakon_citras_apply` alone, in a fresh interpreter, raised ImportError
# before this was fixed). Fixed on the OTHER side instead of by reordering
# this import: pakon_citras_apply.apply_set_tone_lut now imports
# CitrasStatus lazily (at call time, not module load time), so this module
# no longer needs to import pakon_citras_apply at all before that; kept
# below CitrasStatus rather than moved to the top purely to keep this
# explanatory comment next to the class it's about. Both import orders
# verified directly (`import pakon_citras` first, and `import
# pakon_citras_apply` first, each in a fresh interpreter).
from pakon_citras_apply import CITRAS_APPLY_PORTED  # noqa: E402


CITRAS_OK: None = None


# ---------------------------------------------------------------------------
# validateParameters — 0x10223180
# ---------------------------------------------------------------------------

def _chk_sigma(p: CitrasParams) -> bool:
    # fld [this+0x10]; fcomp [0x10573c40] (0.0); fnstsw; test ah, 0x41; jp ok.
    # `jp` is taken for "greater" (ah&0x41 == 0x00) AND for "unordered"
    # (ah&0x41 == 0x41) -- both have even parity.  So NaN passes; only an
    # ordered <= fails, which is what `sigma <= 0.0` is (False for NaN).
    return not (p.sigma <= 0.0)


def _chk_block_size(p: CitrasParams) -> bool:
    return p.blockSize > 0                       # cmp word [ecx+0x18], 0; jg


def _chk_min_avoidance(p: CitrasParams) -> bool:
    return (p.minAvoidance & 0xFF) <= 0x64       # cmp byte [ecx+0x1a],0x64; jbe


def _chk_max_gradient(p: CitrasParams) -> bool:
    return p.maxGradient >= 0                    # cmp word [ecx+0x1c], 0; jge


def _chk_low_threshold(p: CitrasParams) -> bool:
    return p.lowGradientThreshold >= -1          # cmp ax, 0xffff; jge


def _chk_high_threshold(p: CitrasParams) -> bool:
    return p.highGradientThreshold >= -1         # cmp dx, -1; jge


def _chk_threshold_order(p: CitrasParams) -> bool:
    # 0x10223278: `cmp ax, 0xffff; jle ok` then `cmp ax, dx; jl ok`.
    # i.e. low == -1 (or anything below) is exempt; otherwise low < high.
    if p.lowGradientThreshold <= -1:
        return True
    return p.lowGradientThreshold < p.highGradientThreshold


def _chk_value_range(p: CitrasParams) -> bool:
    # 0x102232a8: cmp word [ecx+0x22], word [ecx+0x24]; jl ok
    return p.minValue < p.maxValue


#: (predicate, message literal VA, message) in the order 0x10223180 tests them.
CITRAS_PARAM_CHECKS: tuple[tuple[object, int, str], ...] = (
    (_chk_sigma, 0x1058DD80,
     "sigma must be greater than 0."),
    (_chk_block_size, 0x1058DD5C,
     "blockSize must be greater than 0."),
    (_chk_min_avoidance, 0x1058DD2C,
     "minAvoidance must be less than or equal to 100."),
    (_chk_max_gradient, 0x1058DCFC,
     "maxGradient must be greater than or equal to 0."),
    (_chk_low_threshold, 0x1058DCC8,
     "lowGradientThreshold must be -1 or non-negative."),
    (_chk_high_threshold, 0x1058DC94,
     "highGradientThreshold must be -1 or non-negative."),
    (_chk_threshold_order, 0x1058DC50,
     "lowGradientThreshold must be -1 or less than highGradientThreshold."),
    (_chk_value_range, 0x1058DC24,
     "minValue must be less than maxValue."),
)


def validate_parameters(params: CitrasParams, *, func: str = FUNC_ANALYZE,
                        file: str = SRC_FILE,
                        line: int = ANALYZE_VALIDATE_LINE):
    """``AnsCitrasCapabilityImpl::validateParameters`` (``0x10223180``).

    Returns ``CITRAS_OK`` (``None``) or the first failing check's status.  The
    ``func``/``file``/``line`` are the *caller's* — ``analyze`` pushes
    ``0x1059ed5c`` / ``0x1059ecf8`` / ``0xb7`` at ``0x10223af4``, so validation
    failures are attributed to ``analyze`` line 183.
    """
    if not CITRAS_PARAMS_VALIDATE_PORTED:
        raise RuntimeError(
            "CITRAS_PARAMS_VALIDATE_PORTED is False: "
            f"{CITRAS_VALIDATE_PARAMETERS:#x} is not ported.")
    for predicate, _msg_va, message in CITRAS_PARAM_CHECKS:
        if not predicate(params):
            return CitrasStatus(VALIDATE_ERROR_CODE, func, message, file, line)
    return CITRAS_OK


# ---------------------------------------------------------------------------
# the impl's mutable state — impl+0x28, i.e. AnsCitrasResults
# ---------------------------------------------------------------------------


@dataclass
class CitrasState:
    """``AnsCitrasCapabilityImpl``, only the parts ``analyze`` touches.

    ``lut_size``/``tone_lut`` are ``impl+0x28``/``impl+0x2c``, which is exactly
    ``AnsCitrasResults`` as ``pakon_autotone.AUTOTONE_WORK_LAYOUT`` records it.
    ``tone_lut`` is a ``list[int]`` of unsigned 16-bit entries, or ``None`` for
    the null pointer.
    """

    params: CitrasParams = field(default_factory=default_params)
    lut_size: int = 0
    tone_lut: list[int] | None = None

    #: Every ``new[]``/``delete[]`` the object performed, so a harness can prove
    #: the free at 0x10223a6f and the allocation at 0x1022384e really happened.
    allocations: list[int] = field(default_factory=list)
    frees: int = 0

    #: Set by ``allocate_memory`` to force the ``0x1022385f`` null-return branch.
    fail_allocation: bool = False


def allocate_memory(state: CitrasState, lut_size: int):
    """``AnsCitrasCapabilityImpl::allocateMemory`` (``0x10223810``).

    ``this->ToneLut = new unsigned short[lutSize]`` — literally ``push
    lutSize+lutSize; call operator new[]`` at ``0x10223843``..``0x10223852``,
    stored to ``[edi+0x2c]`` before the null test.  A null return zeroes
    ``this->lutSize`` (``0x10223886``) and returns the ``"Failed in 'new'."``
    status; a success returns OK and touches nothing else.
    """
    if not CITRAS_ALLOCATE_MEMORY_PORTED:
        raise RuntimeError(
            "CITRAS_ALLOCATE_MEMORY_PORTED is False: "
            f"{CITRAS_ALLOCATE_MEMORY:#x} is not ported.")
    n_bytes = (lut_size + lut_size) & 0xFFFFFFFF
    if state.fail_allocation or n_bytes >= 0x80000000:
        # `push ecx; call 0x104ffd78` returned 0.  (A negative lutSize reaches
        # operator new[] as a ~4 GB request, which is the same branch.)
        state.tone_lut = None
        state.lut_size = 0
        return CitrasStatus(ALLOCATE_ERROR_CODE, FUNC_ALLOCATE_MEMORY,
                            "Failed in 'new'.", SRC_FILE,
                            ALLOCATE_MEMORY_FAIL_LINE)
    state.allocations.append(n_bytes)
    state.tone_lut = [0] * lut_size       # uninitialised in the DLL
    return CITRAS_OK


# ---------------------------------------------------------------------------
# analyze — 0x10223a20
# ---------------------------------------------------------------------------


def citras_analyze(state: CitrasState, tone, lut_size: int):
    """``AnsCitrasCapabilityImpl::analyze`` (``0x10223a20``), the whole body.

    ``tone`` is the shell's ``ctx+0x64d0`` tone LUT: ``None``/``0`` for the null
    pointer, otherwise a sequence of at least ``lut_size`` unsigned 16-bit
    entries.  Returns ``CITRAS_OK`` (``None``) or a ``CitrasStatus``; the shell
    tests it with ``if (status != OK) return status``, which is why OK is falsy.
    """
    if not CITRAS_ANALYZE_PORTED:
        raise RuntimeError(
            f"CITRAS_ANALYZE_PORTED is False: {CITRAS_ANALYZE:#x} is not "
            "ported. See docs/64-pruned-tone-producers.md.")

    # 0x10223a64 — the free and the lutSize reset happen FIRST, before the null
    # test and before validation, so every failure path below still leaves the
    # object empty.
    if state.tone_lut is not None:
        state.tone_lut = None                        # delete[] @ 0x10223a70
        state.frees += 1
    state.lut_size = 0                               # 0x10223a7e

    # 0x10223a7b — `cmp [ebp+0x14], edi` : a null tone LUT is not an error.
    if tone is None or (isinstance(tone, int) and tone == 0):
        return CITRAS_OK                             # 0x10223a83

    if isinstance(tone, int):
        raise RuntimeError(
            "citras.analyze got an opaque non-null tone pointer "
            f"({tone:#x}). The shell hands citras whatever produced "
            "ctx+0x64d0 (cna / dra / contrast); until one of those is ported "
            "there is no real LUT to copy. Pass a sequence of unsigned 16-bit "
            "entries.")

    # 0x10223b09 — validateParameters, attributed to analyze's own line 183.
    status = validate_parameters(state.params)
    if status:                                       # 0x10223b84
        return status

    state.lut_size = lut_size                        # 0x10223b90, BEFORE alloc
    status = allocate_memory(state, lut_size)        # 0x10223b93
    if status:                                       # 0x10223bdc
        return status

    # 0x10223c01..0x10223c13 — memcpy(this->ToneLut, tone, lutSize * 2):
    # `lea ecx,[edi+edi]` bytes, `rep movsd` over ecx>>2 then `rep movsb` over
    # ecx&3 (which is 2 whenever lutSize is odd).
    if len(tone) < lut_size:
        raise RuntimeError(
            f"citras.analyze: tone LUT has {len(tone)} entries but lutSize is "
            f"{lut_size}; the DLL would read {lut_size * 2} bytes out of it.")
    state.tone_lut = [int(v) & 0xFFFF for v in tone[:lut_size]]
    return CITRAS_OK                                 # 0x10223c24


def tone_lut_bytes(state: CitrasState) -> bytes:
    """``this->ToneLut`` as the ``lutSize*2`` raw bytes the DLL holds."""
    if state.tone_lut is None:
        return b""
    return struct.pack(f"<{len(state.tone_lut)}H", *state.tone_lut)


# ---------------------------------------------------------------------------


def main() -> None:
    print(f"AnsCitrasCapabilityImpl::analyze {CITRAS_ANALYZE:#010x}  "
          f"(627 B; 24 fns / 3,674 B / 17 indirect reachable)")
    print(f"  Cap wrapper        {CITRAS_CAP_WRAPPER:#010x} "
          f"-> impl = *(cap+0x10)")
    print(f"  validateParameters {CITRAS_VALIDATE_PARAMETERS:#010x}  "
          f"code {VALIDATE_ERROR_CODE:#x}, reported at "
          f"{FUNC_ANALYZE}:{ANALYZE_VALIDATE_LINE}")
    print(f"  allocateMemory     {CITRAS_ALLOCATE_MEMORY:#010x}  "
          f"code {ALLOCATE_ERROR_CODE:#x}, line {ALLOCATE_MEMORY_FAIL_LINE}")
    print(f"  results            impl+{IMPL_LUT_SIZE:#x} lutSize / "
          f"impl+{IMPL_TONE_LUT:#x} ToneLut  (== AnsCitrasResults)")
    print()
    print("  AnsCitrasParams (impl+0x10) — no .dpi file exists for citras;")
    print(f"  the ctor {CITRAS_IMPL_CTOR:#x} copies these from "
          f"{CITRAS_PARAMS_DEFAULT_BLOCK:#x}:")
    for off, name, kind, default in CITRAS_PARAMS_LAYOUT:
        print(f"    +{off:#04x}  {name:<24} {kind:<4} = {default}")
    print()
    print("  validateParameters checks, in order:")
    for _pred, va, msg in CITRAS_PARAM_CHECKS:
        print(f"    {va:#010x}  {msg}")
    print()
    print(f"  CITRAS_ANALYZE_PORTED={CITRAS_ANALYZE_PORTED} "
          f"DEFAULTS={CITRAS_PARAMS_DEFAULTS_PORTED} "
          f"VALIDATE={CITRAS_PARAMS_VALIDATE_PORTED} "
          f"ALLOC={CITRAS_ALLOCATE_MEMORY_PORTED}")
    print(f"  CITRAS_APPLY_PORTED={CITRAS_APPLY_PORTED}  "
          f"<- Phase 3, imported from pakon_citras_apply.py, not this file")
    print()

    st = CitrasState()
    lut = [(i * 7) & 0xFFF for i in range(0x1000)]
    print(f"  analyze(tone=NULL)      -> {citras_analyze(st, None, 0x1000)}"
          f"  lutSize={st.lut_size} ToneLut={st.tone_lut}")
    print(f"  analyze(tone, 0x1000)   -> {citras_analyze(st, lut, 0x1000)}"
          f"  lutSize={st.lut_size} first 4 = {st.tone_lut[:4]}")
    bad = CitrasState(params=CitrasParams(minValue=4095, maxValue=0))
    print(f"  analyze(bad minValue)   -> {citras_analyze(bad, lut, 0x1000)}")
    print(f"                             lutSize={bad.lut_size} "
          f"ToneLut={bad.tone_lut}  (freed even though validation failed)")


if __name__ == "__main__":
    main()
