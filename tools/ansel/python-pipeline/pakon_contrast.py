#!/usr/bin/env python3
r"""``AnsContrastAdjustCapabilityImpl::analyze`` — Phase 2d of the
``ColorNegativePath::analyzeAutoTone`` port.

WHAT THIS IS
============
``contrast`` is the largest of ``analyzeAutoTone``'s six subsystems (79
functions / 20,414 bytes / 104 indirect call sites), but almost none of that
is arithmetic.  ``analyze`` **never touches image pixels**: it takes one
4096-entry ``short`` tone LUT in and produces one 4096-entry ``short`` tone LUT
out, entirely in LUT index/value space.

The call chain from the shell is::

    ColorNegativePath::analyzeAutoTone            0x100fb730
      AnsContrastAdjustCapability::acquire        0x1010a510   (351 B shell)
        AnsContrastAdjustCapabilityImpl::acquire  0x101d8880   <- the port target
          AnsContrastAdjustCapabilityImpl::setParams  0x101d7e70
            AnsContrastAdjustParams::operator=       0x1010b450
            ...::validateParams                      0x101d3860
          AnsContrastAdjustCapabilityImpl::analyze    0x101d8240
            ...::constrainSlope                       0x101d2eb0
            <ramp builder>                            0x101d2ad0
            <piecewise-linear segment builder>        0x101d2c80
            <free the three scratch buffers>          0x101d2e50

``0x1010a510`` is the only caller of ``0x101d8880``, and ``0x101d8880`` is the
only path ``analyzeAutoTone`` uses to reach contrast.

THE SHELL'S ARGUMENT MARSHALLING (``0x1010a510``)
=================================================
The 351-byte Cap wrapper does exactly three interesting things::

    0x1010a568  mov  al, byte [edi + 0xe]     ; a THIRD capability flag byte
    0x1010a56c  mov  byte [ebp + 0x18], al    ; overwrites only the LOW byte of
    0x1010a56f  mov  ecx, dword [ebp + 0x18]  ; the `tone` arg slot, then reads
                                              ; the whole dword back -- so the
                                              ; upper 3 bytes handed down are
                                              ; stale `tone` pointer bits.  The
                                              ; callee only ever tests the low
                                              ; byte (`0x101d8633: mov al,
                                              ; byte [ebp+0x10]`), so this is
                                              ; harmless, but it is why the
                                              ; argument is modelled as a bool.
    0x1010a58a  mov  ecx, dword [edi + 0x10]  ; this = the Impl
    0x1010a591  call 0x101d8880

giving ``0x101d8880(&status, holder, capFlagE, sceneType, x, tone)`` with
``ret 0x18`` (6 stack args).

``cap+0xe`` — THE GATING BYTE THE DRIVER NEVER SETS
====================================================
``declareAutoTone`` writes ``cap+0xc`` and ``cap+0xd`` for every capability; it
never writes ``cap+0xe``.  ``AnsContrastAdjustCapability``'s own constructor
does, at ``0x10109fc0``::

    0x10109fb8  mov byte [esi + 0x0c], 1      ; enable      (declare sets this too)
    0x10109fbc  mov byte [esi + 0x0d], 1      ; companion   (declare sets this too)
    0x10109fc0  mov byte [esi + 0x0e], 0      ; <-- THIS ONE.  Default 0.
    0x10109fc4  mov byte [esi + 0x0f], 0      ; "last call OK"

so the real default is **0**, and nothing on the ``analyzeAutoTone`` path ever
changes it.  What it gates is *not* the LUT arithmetic — it is the retention of
the two intermediate buffers (``0x101d8633``)::

    if (capFlagE == 0) { delete[] impl+0x1ac; delete[] impl+0x1b0; }

i.e. with the shipped default the results struct comes back with
``CAdjLut == NULL`` and ``InToneLut == NULL`` and only ``OutToneLut`` live.
The tone LUT the shell threads into ``ctx+0x64d0`` is ``OutToneLut``, so the
final image is identical either way; the flag is a diagnostics switch.
:data:`CONTRAST_KEEP_INTERMEDIATES_DEFAULT` records the constructor's 0.

OBJECT LAYOUT
=============
``AnsContrastAdjustCapabilityImpl`` is ``0x1b8`` bytes (``0x10109fd4`` does
``push 0x1b8; call operator new``) laid out as::

    +0x000  vftable / refcount / status      (0xc bytes)
    +0x00c  AnsContrastAdjustParams          (0x180 bytes, embedded by value)
    +0x18c  AnsContrastAdjustResults         (0x2c bytes)

so every *params-relative* offset in the ``.dpi`` key table below is
``impl-relative - 0xc``, and every *results-relative* offset is
``impl-relative - 0x18c``.  ``0x10109d70`` (``getResults``) is a bare
``rep movsd`` of 0xb dwords from ``impl+0x18c``, which is what makes the
results offsets checkable from the Phase-1 shell harness.

VERIFIED, NOT ASSUMED
=====================
Everything in this file was read out of ``PakonIMAu.dll`` and is checked
bit-for-bit against the real functions running under Unicorn by

* ``pakon_contrast_lut_golden.py``   — ``0x101d8240`` (build + mode dispatch)
                                       and the ``0x101d8880`` front end
* ``pakon_contrast_slope_golden.py`` — ``0x101d2eb0`` (``constrainSlope``)
                                       as a standalone unit

FLOATING POINT
==============
Every float here is x87 at ``FPCW == 0x027f`` (53-bit mantissa, round-nearest)
— the Windows CRT default, which is bit-identical to a Python ``float``.
Stores the vendor makes to ``float`` memory are narrowed explicitly with
:func:`_f32`; nothing else is narrowed, because nothing else is stored.
``__ftol`` (``0x104ffe44``, real code in the image, not an IAT thunk) is
truncation toward zero, and every caller uses only its low 16 bits — see
:func:`_ftol16`.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field, replace as _dc_replace

# ---------------------------------------------------------------------------
# addresses
# ---------------------------------------------------------------------------

CAP_ACQUIRE = 0x1010A510        # AnsContrastAdjustCapability::acquire (the shell)
IMPL_ACQUIRE = 0x101D8880       # ...Impl::acquire -- resolves params, tail-calls
IMPL_ANALYZE = 0x101D8240       # ...Impl::analyze -- the LUT build
IMPL_SET_PARAMS = 0x101D7E70    # ...Impl::setParams
IMPL_GET_PARAMS = 0x1010B630    # ...Impl::getParams
IMPL_GET_RESULTS = 0x10109D70   # ...Impl::getResults (rep movsd 0xb dwords)
IMPL_CTOR = 0x101D5E60
PARAMS_CTOR = 0x1005DAB0
PARAMS_DTOR = 0x1005E0D0
PARAMS_ASSIGN = 0x1010B450
VALIDATE_PARAMS = 0x101D3860
CONSTRAIN_SLOPE = 0x101D2EB0
BUILD_RAMP = 0x101D2AD0         # <ramp from a midpoint out to an end index>
BUILD_SEGMENT = 0x101D2C80      # <one piecewise-linear segment between 2 points>
FREE_BUFFERS = 0x101D2E50
SELECT_PARAMS = 0x101D5D20      # AnsContrastAdjustCapabilityImpl::selectParams
SELECT_DPI = 0x101D5270         # AnsInitializeMapping::selectDpi<>
SCENE_CONTEXT_FIND = 0x10022A40
SCAN_ONE_LINE = 0x1012DF00      # AnsContrastAdjustParameterReader::scanOneLine
CAP_CTOR_FLAG_E_STORE = 0x10109FC0   # mov byte [esi+0xe], 0

OP_NEW = 0x104FFD53             # operator new  (operator new[] 0x104ffd78 jmps here)
OP_DELETE_ARR = 0x104FFE3E      # operator delete[] -- unbound IAT thunk
FTOL = 0x104FFE44               # __ftol (real code)
STATUS_OK_GLOBAL = 0x106B5BD4   # 0 in the shipped image
IMPL_VFTABLE = 0x1059A018

SRC_FILE = r"\Atc\ansel\src\libContrastAdjust.ansel\AnsContrastAdjustCapabilityImpl.cpp"
FUNC_ANALYZE = "AnsContrastAdjustCapabilityImpl::analyze"
FUNC_SET_PARAMS = "AnsContrastAdjustCapabilityImpl::setParams"

#: ``0x101d8880``'s two failure sites, by ``.cpp`` line.
LINE_HOLDER_FAILED = 176        # push 0xb0 @ 0x101d8919
LINE_SELECT_PARAMS_FAILED = 185  # push 0xb9 @ 0x101d8a55
#: ``0x101d8240``'s three ``Failed in 'new ansPixel_t'.`` sites.
LINE_ALLOC_OUT = 242            # push 0xf2  -> impl+0x1b4
LINE_ALLOC_ADJ = 251            # push 0xfb  -> impl+0x1ac
LINE_ALLOC_IN = 262             # push 0x106 -> impl+0x1b0
LINE_CONSTRAIN_FAILED = 279     # push 0x117

#: ``0x10589f10`` / ``0x10589f0c`` -- validateParams' slope bounds.
SLOPE_MIN = 0.10000000149011612
SLOPE_MAX = 10.0
#: ``0x10574f40`` -- the rounding constant, a *double*.
ROUND_HALF = 0.5
#: ``0x10575674`` -- the float 0.0 every slope-sign test compares against.
FZERO = 0.0

# ---------------------------------------------------------------------------
# port-status flags.  A False flag raises, it never silently degrades.
# ---------------------------------------------------------------------------

#: ``0x101d8240`` + ``0x101d2ad0`` + ``0x101d2c80`` + ``0x101d2e50``.
CONTRAST_LUT_BUILD_PORTED = True
#: ``0x101d2eb0`` -- also reached from the Shasta-triage path via
#: ``Capability::constrainSlope`` at ``0x1010a7f0``, hence a standalone unit.
CONTRAST_CONSTRAIN_SLOPE_PORTED = True
#: ``0x101d7e70`` + ``0x1010b450`` + ``0x101d3860``.
CONTRAST_SET_PARAMS_PORTED = True
#: ``0x101d8880``'s own body: holder resolve, params local, error lines.
CONTRAST_ACQUIRE_PORTED = True
#: ``0x1012df00`` -- the ``.dpi`` key table, including the vendor typo.
CONTRAST_DPI_PARSE_PORTED = True
#: ``0x101d5d20`` -> ``0x101d5270`` -> ``0x10022a40``: the *live* std::map /
#: ostringstream DPI-registry walk.  Not ported -- and not needed, because that
#: machinery runs at library *initialisation*; ``analyzeAutoTone`` only ever
#: performs the lookup of an already-parsed table.  :func:`select_params`
#: models the lookup's contract over a host-side registry instead.
CONTRAST_SELECT_DPI_TREE_PORTED = False

#: ``AnsContrastAdjustCapability``'s ctor default for ``cap+0xe`` (0x10109fc0).
CONTRAST_KEEP_INTERMEDIATES_DEFAULT = False


class ContrastError(RuntimeError):
    """What ``0x1001ed90`` raises out of this subsystem."""


def _unported(flag: str, what: str):
    raise RuntimeError(
        f"{flag} is False: {what} is not ported. See pakon_contrast.py.")


# ---------------------------------------------------------------------------
# float / integer primitives
# ---------------------------------------------------------------------------


def replace(p: "ContrastParams", **kw) -> "ContrastParams":
    """``dataclasses.replace`` with the mutable members deep-copied.

    Used by the golden harnesses to spin one params variant off another without
    the two sharing a ``points`` list or a slope array.
    """
    return _dc_replace(p.copy(), **kw)


def _f32(x: float) -> float:
    """Narrow to ``float`` — every ``fstp dword`` / ``float`` field store."""
    return struct.unpack("<f", struct.pack("<f", x))[0]


def _i16(v: int) -> int:
    """Sign-extend the low 16 bits, as every ``movsx r32, r/m16`` does."""
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


#: 2**63 — where ``fistp qword`` gives up and stores the "integer indefinite".
_INT64_LIMIT = 9223372036854775808.0


def _ftol16(x: float) -> int:
    """``call 0x104ffe44`` followed by a use of ``ax``.

    ``__ftol`` is the standard MSVC helper: ``fistp qword`` (round-to-nearest,
    the current mode) followed by an explicit correction back toward zero, i.e.
    C ``(long long)`` semantics.  Every call site in this subsystem consumes
    only ``ax`` (``0x101d2b62 cmp ax, bp``, ``0x101d32f9 test ax, ax``, ...),
    so the 64-bit result is then narrowed to a signed 16-bit value.

    NaN and anything outside ``int64`` make ``fistp`` store the indefinite
    ``0x8000000000000000``; ``0x104ffe63``'s ``test eax, eax`` then sees a zero
    *low* dword and skips the correction, so ``ax`` comes out **0**, not
    ``0x8000``.
    """
    if x != x or x >= _INT64_LIMIT or x < -_INT64_LIMIT:
        v = -1 << 63
    else:
        v = int(x)                   # Python int() truncates toward zero
    return _i16(v & 0xFFFF)


def _fdiv(num: float, den: float) -> float:
    """``fdivp`` with every exception masked, which is how the CRT leaves x87.

    A zero divisor is not an error on the FPU: ``0/0`` is the invalid operation
    and yields a QNaN, anything else over zero yields a signed infinity.  Both
    are reachable — a regression window with a single distinct sample abscissa
    (``csGranularity == csNSamples == 1``) makes the denominator exactly 0 —
    and both then flow through the limit comparisons as *unordered*, which the
    vendor's ``test ah, 5`` / ``test ah, 0x41`` pairs resolve to "neither too
    shallow nor too steep", i.e. no flag.  Python's ``/`` raises instead, so it
    cannot be used directly.
    """
    if den == 0.0:
        if num == 0.0 or num != num:
            return float("nan")
        return float("inf") if (num > 0.0) else float("-inf")
    return num / den


def _cdiv(a: int, b: int) -> int:
    """C ``idiv`` — truncation toward zero, not Python's floor."""
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


# ---------------------------------------------------------------------------
# AnsContrastAdjustParams -- 0x180 bytes, embedded at Impl+0xc
# ---------------------------------------------------------------------------

#: ``userInputMode``.  The five names are the literals ``0x1012dfbb`` onward
#: matches against; the numbers are the immediates it stores to ``params+0x40``.
MODE_NO_USER_INPUT = 0        # 0x1012dff4
MODE_COMBINE_WITH_SLOPE = 1   # 0x1012e01a
MODE_COMBINE_WITH_POINT = 2   # 0x1012e044
MODE_OVERRIDE_WITH_SLOPE = 3  # 0x1012e06e
MODE_OVERRIDE_WITH_POINT = 4  # 0x1012e098

MODE_NAMES = {
    "NO_USER_INPUT": MODE_NO_USER_INPUT,
    "COMBINE_WITH_SLOPE": MODE_COMBINE_WITH_SLOPE,
    "COMBINE_WITH_POINT": MODE_COMBINE_WITH_POINT,
    "OVERRIDE_WITH_SLOPE": MODE_OVERRIDE_WITH_SLOPE,
    "OVERRIDE_WITH_POINT": MODE_OVERRIDE_WITH_POINT,
}

#: Modes whose adjustment curve is two straight ramps through ``midpoint``.
MODES_WITH_SLOPE = (MODE_COMBINE_WITH_SLOPE, MODE_OVERRIDE_WITH_SLOPE)
#: Modes whose adjustment curve is the piecewise-linear ``points`` polyline.
MODES_WITH_POINT = (MODE_COMBINE_WITH_POINT, MODE_OVERRIDE_WITH_POINT)
#: Modes that *compose* the adjustment curve with the incoming tone LUT.
MODES_COMBINE = (MODE_COMBINE_WITH_SLOPE, MODE_COMBINE_WITH_POINT)
#: Modes that *replace* the incoming tone LUT with the adjustment curve.
#: These never read ``tone`` at all -- which is why ``0x101d82d5`` lets them
#: run with a NULL ``tone`` argument and every other mode bails out.
MODES_OVERRIDE = (MODE_OVERRIDE_WITH_SLOPE, MODE_OVERRIDE_WITH_POINT)

#: The four per-band slope-limit arrays are 16 entries wide in the struct
#: (0x40 bytes each) but the ctor only seeds ``[0x10589f14] == 7`` of them,
#: and the ``.dpi`` reader's shared ``"%f %f %f %f %f %f %f"`` also writes 7.
N_SLOPE_BANDS = 7
SLOPE_ARRAY_LEN = 16

#: ``0x1005dab0``'s literal seeds, read out of the image at the addresses in
#: the comments.  These are what a params object holds if no ``.dpi`` line
#: touches the field -- which is exactly how ``csUpperIndex`` always ends up
#: (see :data:`DPI_KEYS` and the ``csumpperixedindex`` note).
_DEF_LOWER_MIN = (0.8, 0.3, 0.8, 0.5, 0.4, 0.2, 0.0)   # 0x10589f18
_DEF_LOWER_MAX = (1.5, 6.0, 1.5, 2.5, 4.0, 6.0, 10.0)  # 0x10589f58
_DEF_UPPER_MIN = (0.8, 0.5, 0.8, 0.7, 0.6, 0.4, 0.0)   # 0x10589f98
_DEF_UPPER_MAX = (1.5, 6.0, 1.5, 2.5, 4.0, 6.0, 10.0)  # 0x10589fd8


def _slope_array(seed) -> list[float]:
    """The ctor's fill: ``N_SLOPE_BANDS`` real values, then (0, 100) padding.

    ``0x1005dbdd``: entries ``[n, 16)`` get ``min = 0`` and
    ``max = 0x42c80000 == 100.0f`` for both the lower and the upper pair.
    """
    out = [_f32(v) for v in seed]
    pad = 0.0 if seed in (_DEF_LOWER_MIN, _DEF_UPPER_MIN) else 100.0
    return out + [pad] * (SLOPE_ARRAY_LEN - len(out))


@dataclass
class ContrastParams:
    """``AnsContrastAdjustParams``.  Defaults are ``0x1005dab0``'s literals."""

    maxValue: int = 4095                  # +0x3a  i16   [0x10589ef8]
    lutSize: int = 4096                   # +0x3c  i32   [0x10589efc]
    userInputMode: int = MODE_COMBINE_WITH_SLOPE   # +0x40 i32, literal 1
    lowInitialSlope: float = 1.0          # +0x44  f32   [0x10589f00]
    highInitialSlope: float = 1.0         # +0x48  f32   [0x10589f00]
    midpointIn: int = 1550                # +0x4c  i16   [0x10589f04] low half
    midpointOut: int = 1550               # +0x4e  i16   [0x10589f04] high half
    lowIncr: float = 0.1                  # +0x50  f32   [0x10589f08]
    highIncr: float = 0.1                 # +0x54  f32   [0x10589f08]
    allIncr: float = 0.1                  # +0x58  f32   [0x10589f08]
    points: list = field(default_factory=list)     # +0x5c std::vector<(i16,i16)>
    bConstrainSlope: bool = False          # +0x6c  bool
    aLowerMinSlope: list = field(          # +0x70  f32[16]
        default_factory=lambda: _slope_array(_DEF_LOWER_MIN))
    aLowerMaxSlope: list = field(          # +0xb0
        default_factory=lambda: _slope_array(_DEF_LOWER_MAX))
    aUpperMinSlope: list = field(          # +0xf0
        default_factory=lambda: _slope_array(_DEF_UPPER_MIN))
    aUpperMaxSlope: list = field(          # +0x130
        default_factory=lambda: _slope_array(_DEF_UPPER_MAX))
    csGranularity: int = 20               # +0x170 i32   [0x1058a018]
    csNSamples: int = 5                   # +0x174 i32   [0x1058a01c]
    csLowerIndex: int = 51                # +0x178 i16   [0x1058a020]
    csFixedIndex: int = 1550              # +0x17a i16   [0x1058a024]
    csUpperIndex: int = 3999              # +0x17c i16   [0x1058a028]

    def copy(self) -> "ContrastParams":
        """``AnsContrastAdjustParams::operator=`` (``0x1010b450``) — a deep
        copy of both strings, the ``points`` vector and all four arrays."""
        return _dc_replace(
            self,
            points=list(self.points),
            aLowerMinSlope=list(self.aLowerMinSlope),
            aLowerMaxSlope=list(self.aLowerMaxSlope),
            aUpperMinSlope=list(self.aUpperMinSlope),
            aUpperMaxSlope=list(self.aUpperMaxSlope),
        )

    # -- the raw 0x180-byte image, for the Unicorn goldens ------------------
    def to_bytes(self, points_ptr: int = 0) -> bytes:
        """Serialise to the exact ``0x180``-byte struct the DLL reads.

        ``points_ptr`` is where the caller has placed the vector's element
        array; ``_First/_Last/_End`` land at ``+0x60/+0x64/+0x68`` (MSVC 7.1
        puts the empty allocator in the first 4 bytes of the vector at
        ``+0x5c``).  ``0x101d8578`` reads exactly those two pointers.
        """
        b = bytearray(0x180)
        struct.pack_into("<h", b, 0x3A, self.maxValue)
        struct.pack_into("<i", b, 0x3C, self.lutSize)
        struct.pack_into("<i", b, 0x40, self.userInputMode)
        struct.pack_into("<f", b, 0x44, self.lowInitialSlope)
        struct.pack_into("<f", b, 0x48, self.highInitialSlope)
        struct.pack_into("<hh", b, 0x4C, self.midpointIn, self.midpointOut)
        struct.pack_into("<f", b, 0x50, self.lowIncr)
        struct.pack_into("<f", b, 0x54, self.highIncr)
        struct.pack_into("<f", b, 0x58, self.allIncr)
        n = len(self.points)
        struct.pack_into("<III", b, 0x60, points_ptr if n else 0,
                         points_ptr + 4 * n if n else 0,
                         points_ptr + 4 * n if n else 0)
        b[0x6C] = 1 if self.bConstrainSlope else 0
        for off, arr in ((0x70, self.aLowerMinSlope), (0xB0, self.aLowerMaxSlope),
                         (0xF0, self.aUpperMinSlope), (0x130, self.aUpperMaxSlope)):
            for i in range(SLOPE_ARRAY_LEN):
                struct.pack_into("<f", b, off + 4 * i, arr[i])
        struct.pack_into("<i", b, 0x170, self.csGranularity)
        struct.pack_into("<i", b, 0x174, self.csNSamples)
        struct.pack_into("<hhh", b, 0x178, self.csLowerIndex,
                         self.csFixedIndex, self.csUpperIndex)
        return bytes(b)

    def points_bytes(self) -> bytes:
        """The vector's elements: one dword per point, ``in`` then ``out``."""
        return b"".join(struct.pack("<hh", a, o) for a, o in self.points)


# ---------------------------------------------------------------------------
# AnsContrastAdjustResults -- 0x2c bytes at Impl+0x18c
# ---------------------------------------------------------------------------


@dataclass
class ContrastResults:
    """``AnsContrastAdjustResults``.  Defaults are ``0x101d5e60``'s seeds."""

    lutSize: int = 0                      # +0x00 <- impl+0x18c
    lowSlope: float = -1.0                # +0x04 <- impl+0x190  (0xbf800000)
    highSlope: float = -1.0               # +0x08 <- impl+0x194
    lowerMinSlopeLimit: float = 0.0       # +0x0c <- impl+0x198
    lowerMaxSlopeLimit: float = 100.0     # +0x10 <- impl+0x19c  (0x42c80000)
    upperMinSlopeLimit: float = 0.0       # +0x14 <- impl+0x1a0
    upperMaxSlopeLimit: float = 100.0     # +0x18 <- impl+0x1a4
    bWasLowerMinLimitReached: bool = False   # +0x1c <- impl+0x1a8
    bWasLowerMaxLimitReached: bool = False   # +0x1d <- impl+0x1a9
    bWasUpperMinLimitReached: bool = False   # +0x1e <- impl+0x1aa
    bWasUpperMaxLimitReached: bool = False   # +0x1f <- impl+0x1ab
    CAdjLut: list | None = None           # +0x20 <- impl+0x1ac
    InToneLut: list | None = None         # +0x24 <- impl+0x1b0
    OutToneLut: list | None = None        # +0x28 <- impl+0x1b4

    def to_bytes(self, ptr_adj=0, ptr_in=0, ptr_out=0) -> bytes:
        b = bytearray(0x2C)
        struct.pack_into("<i", b, 0x00, self.lutSize)
        struct.pack_into("<ffffff", b, 0x04, self.lowSlope, self.highSlope,
                         self.lowerMinSlopeLimit, self.lowerMaxSlopeLimit,
                         self.upperMinSlopeLimit, self.upperMaxSlopeLimit)
        b[0x1C] = int(self.bWasLowerMinLimitReached)
        b[0x1D] = int(self.bWasLowerMaxLimitReached)
        b[0x1E] = int(self.bWasUpperMinLimitReached)
        b[0x1F] = int(self.bWasUpperMaxLimitReached)
        struct.pack_into("<III", b, 0x20, ptr_adj, ptr_in, ptr_out)
        return bytes(b)


# ---------------------------------------------------------------------------
# the .dpi key table -- AnsContrastAdjustParameterReader::scanOneLine 0x1012df00
# ---------------------------------------------------------------------------

#: **The vendor's own typo, replicated on purpose.**
#:
#: ``csUpperIndex``'s parse key is spelled ``csumpperixedindex`` in the binary's
#: string table.  Verified two ways: the literal sits at ``0x1058a500`` (hexdump
#: shows ``csumpperixedindex\0``, and it is the *only* reference to that address
#: in the whole image), and ``0x1012e576`` matches it with
#: ``mov edi, 0x1058a500 / mov ecx, 0x12 / repe cmpsb`` — 0x12 == 18 == the 17
#: characters plus the NUL, so the comparison is the full misspelled token.  On
#: a match, ``0x1012e590`` does ``add ecx, 0x17c`` and ``sscanf(..., "%hd", ...)``
#: into ``params+0x17c``, which is genuinely ``csUpperIndex``.
#:
#: Consequence: **no ``.dpi`` can ever set ``csUpperIndex``.**  A file writing
#: the correct ``csUpperIndex = ...`` falls through every key and is rejected;
#: the field keeps its constructor default of 3999 forever.  The shipped
#: ``contrast-CNEnhanced.dpi`` does not try, so behaviour is unaffected — but a
#: port that "fixed" the spelling would silently diverge from the real scanner
#: on any hypothetical file that did.  Do not correct this.
DPI_KEY_CS_UPPER_INDEX = "csumpperixedindex"
DPI_KEY_CS_UPPER_INDEX_STR_VA = 0x1058A500
DPI_KEY_CS_UPPER_INDEX_MATCH_VA = 0x1012E576

#: ``key -> (params attribute, params offset, scanf format)``, in the order
#: ``scanOneLine`` tests them.  Every key is compared lowercased.
DPI_KEYS: tuple[tuple[str, str, int, str], ...] = (
    (DPI_KEY_CS_UPPER_INDEX, "csUpperIndex", 0x17C, "%hd"),
    ("csfixedindex", "csFixedIndex", 0x17A, "%hd"),
    ("cslowerindex", "csLowerIndex", 0x178, "%hd"),
    ("csnsamples", "csNSamples", 0x174, "%d"),
    ("csgranularity", "csGranularity", 0x170, "%d"),
    ("allincr", "allIncr", 0x58, "%f"),
    ("highincr", "highIncr", 0x54, "%f"),
    ("lowincr", "lowIncr", 0x50, "%f"),
    ("highinitialslope", "highInitialSlope", 0x48, "%f"),
    ("lowinitialslope", "lowInitialSlope", 0x44, "%f"),
    ("lutsize", "lutSize", 0x3C, "%d"),
    ("maxvalue", "maxValue", 0x3A, "%hd"),
    ("auppermaxslope", "aUpperMaxSlope", 0x130, "%f %f %f %f %f %f %f"),
    ("aupperminslope", "aUpperMinSlope", 0x0F0, "%f %f %f %f %f %f %f"),
    ("alowermaxslope", "aLowerMaxSlope", 0x0B0, "%f %f %f %f %f %f %f"),
    ("alowerminslope", "aLowerMinSlope", 0x070, "%f %f %f %f %f %f %f"),
    ("userinputmode", "userInputMode", 0x40, "<enum>"),
    ("midpoint", "midpoint", 0x4C, "%hd %hd"),
    ("points", "points", 0x5C, "%hd %hd"),
    ("bconstrainslope", "bConstrainSlope", 0x6C, "<bool>"),
)

#: The four slope arrays all converge on one shared 7-float ``sscanf``
#: (``0x1058a5a8``), which is why ``N_SLOPE_BANDS`` is 7 and entries 7..15 keep
#: whatever the constructor put there.
DPI_SLOPE_KEYS = ("alowerminslope", "alowermaxslope",
                  "aupperminslope", "auppermaxslope")


def parse_dpi(text: str, base: ContrastParams | None = None) -> ContrastParams:
    """``AnsContrastAdjustParameterReader`` over one ``.dpi`` file's text.

    Runs at library *initialisation*, not during ``analyzeAutoTone`` — see
    :data:`CONTRAST_SELECT_DPI_TREE_PORTED`.  It is here so the shipped
    ``vendor/ansel/anselinstalldir/dataPathItems/contrast/*.dpi`` files resolve
    to exactly the params the real reader would have produced, and so the
    ``csumpperixedindex`` typo is exercised rather than described.
    """
    if not CONTRAST_DPI_PARSE_PORTED:
        _unported("CONTRAST_DPI_PARSE_PORTED", "scanOneLine (0x1012df00)")
    p = (base or ContrastParams()).copy()
    p.points = []
    seen_points = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().lower()
        value = value.strip()
        if key == "userinputmode":
            p.userInputMode = MODE_NAMES.get(value, None)
            if p.userInputMode is None:      # 0x1012e0aa: sscanf("%d") fallback
                p.userInputMode = int(value)
        elif key == "bconstrainslope":
            if value == "true":              # 0x1012e2be
                p.bConstrainSlope = True
            elif value == "false":           # 0x1012e317
                p.bConstrainSlope = False
            else:                            # 0x1012e2e3: sscanf("%d")
                p.bConstrainSlope = bool(int(value))
        elif key == "midpoint":
            a, b = value.split()[:2]
            p.midpointIn, p.midpointOut = _i16(int(a)), _i16(int(b))
        elif key == "points":
            if not seen_points:
                seen_points = True
            a, b = value.split()[:2]
            p.points.append((_i16(int(a)), _i16(int(b))))
        elif key in DPI_SLOPE_KEYS:
            vals = [_f32(float(v)) for v in value.split()[:N_SLOPE_BANDS]]
            arr = list(getattr(p, dict(
                alowerminslope="aLowerMinSlope", alowermaxslope="aLowerMaxSlope",
                aupperminslope="aUpperMinSlope", auppermaxslope="aUpperMaxSlope",
            )[key]))
            arr[:len(vals)] = vals
            setattr(p, dict(
                alowerminslope="aLowerMinSlope", alowermaxslope="aLowerMaxSlope",
                aupperminslope="aUpperMinSlope", auppermaxslope="aUpperMaxSlope",
            )[key], arr)
        else:
            for k, attr, _off, fmt in DPI_KEYS:
                if k != key:
                    continue
                if fmt == "%f":
                    setattr(p, attr, _f32(float(value)))
                elif fmt == "%hd":
                    setattr(p, attr, _i16(int(value)))
                else:
                    setattr(p, attr, int(value))
                break
            # Anything else -- including a correctly spelled "csupperindex" --
            # falls through every key and is rejected.  That is the typo's
            # whole practical effect; do not add a fallback here.
    if not seen_points:
        p.points = list((base or ContrastParams()).points)
    return p


def select_params(scene_dpi_key: str, registry: dict) -> ContrastParams:
    """``selectParams`` (``0x101d5d20``) -> ``selectDpi<>`` -> ``SceneContext::find``.

    The real chain pulls a DPI name out of the scene context, looks it up in a
    ``std::map`` of already-parsed parameter blocks built at initialisation
    (``0x106b6384`` / ``0x106b636c``), and assigns the hit onto the caller's
    params object.  Only the *lookup* happens during ``analyzeAutoTone``; the
    parse does not.  A miss propagates a failure status, which ``0x101d8880``
    logs at ``.cpp`` line 185 and returns without ever reaching the LUT build.
    """
    try:
        return registry[scene_dpi_key].copy()
    except KeyError:
        raise ContrastError(
            f"selectParams failed for {scene_dpi_key!r} "
            f"({SRC_FILE}:{LINE_SELECT_PARAMS_FAILED})") from None


# ---------------------------------------------------------------------------
# validateParams -- 0x101d3860
# ---------------------------------------------------------------------------


def validate_params(p: ContrastParams) -> str | None:
    """``0x101d3860``.  Returns ``None`` on success or an error summary.

    **It never mutates the params.**  Every ``mov [esi], eax`` inside it writes
    the hidden ``AnsStatus&`` sret (``esi`` is reloaded from ``[esp+0xc4]``),
    not ``this``.  That matters because ``0x101d8240`` *discards* the status
    ``setParams`` returns (``0x101d82a2`` releases it and falls through) — so
    the only way a validation failure can change the LUT is through
    ``setParams``' own rollback, which :meth:`ContrastImpl.set_params` models.
    """
    if p.userInputMode in MODES_WITH_POINT:
        # 0x101d3c06: at least two points, monotone non-decreasing in `in`,
        # every `in` in [0, lutSize), every `out` in [0, maxValue].
        if len(p.points) < 2:
            return "points: fewer than two"
        prev_in = None
        for i, (pi, po) in enumerate(p.points):
            if pi < 0 or pi >= p.lutSize:
                return f"points[{i}].in out of range"
            if po < 0 or po > p.maxValue:
                return f"points[{i}].out out of range"
            if prev_in is not None and pi < prev_in:
                return f"points[{i}].in decreases"
            prev_in = pi
        return None
    # 0x101d38bd: midpoint in range, then both initial slopes in [0.1, 10.0].
    if p.midpointIn < 0 or p.midpointIn >= p.lutSize:
        return "midpoint.in out of range"
    if p.midpointOut < 0 or p.midpointOut > p.maxValue:
        return "midpoint.out out of range"
    for name in ("lowInitialSlope", "highInitialSlope"):
        v = getattr(p, name)
        if v < SLOPE_MIN:
            return f"{name} < {SLOPE_MIN}"
        if v > SLOPE_MAX:
            return f"{name} > {SLOPE_MAX}"
    return None


# ---------------------------------------------------------------------------
# 0x101d2ad0 -- ramp from `midpoint` out to `end_index` at a fixed slope
# ---------------------------------------------------------------------------


def build_ramp(buf: list, max_value: int, mid_in: int, mid_out: int,
               end_index: int, slope: float) -> None:
    """``0x101d2ad0(midpointPacked, endIndex, slope, buf)``.

    Both directions are one loop: the running value is *accumulated* by
    repeated ``fadd slope``, never recomputed as ``mid_out + i*slope``, so the
    float error accumulates and must be reproduced step for step.

    The three slope-sign branches are asymmetric on purpose:

    * ``slope < 0``  — per-sample clamp **up** to ``maxValue``; once the value
      reaches ``<= 0`` the remaining entries are filled with 0 in one go
      (``0x101d2b82``).
    * ``slope == 0`` — the whole span is filled with ``mid_out``
      (``0x101d2bba``); no rounding at all.
    * ``slope > 0``  — per-sample clamp **down** to 0; once the value reaches
      ``>= maxValue`` the rest is filled with ``maxValue`` (``0x101d2c3e``).
    """
    slope = _f32(slope)
    buf[mid_in] = mid_out
    if _i16(mid_in) == _i16(end_index):        # 0x101d2af1
        return
    if _i16(mid_in) < _i16(end_index):         # ascending: 0x101d2afa
        i, last = mid_in, end_index
        val = float(mid_out) - slope
    else:                                      # descending: 0x101d2b0d
        i, last = end_index, mid_in
        val = float(_i16(end_index) - mid_in - 1) * slope + mid_out
    if _i16(i) > _i16(last):
        return
    if slope < FZERO:
        while True:
            val = val + slope
            if val <= FZERO:                   # 0x101d2b53 -> 0x101d2b82
                for k in range(i, last + 1):
                    buf[k] = 0
                return
            r = _ftol16(ROUND_HALF + val)
            buf[i] = max_value if r > max_value else r   # 0x101d2b62
            i += 1
            if _i16(i) > _i16(last):
                return
    if slope == FZERO:                         # 0x101d2bba
        for k in range(i, last + 1):
            buf[k] = mid_out
        return
    max_f = _f32(float(max_value))             # 0x101d2bf6: fild / fstp dword
    while True:
        val = val + slope
        if val >= max_f:                       # 0x101d2c0a -> 0x101d2c3e
            for k in range(i, last + 1):
                buf[k] = max_value
            return
        r = _ftol16(ROUND_HALF + val)
        buf[i] = r if r >= 0 else 0            # 0x101d2c1c
        i += 1
        if _i16(i) > _i16(last):
            return


# ---------------------------------------------------------------------------
# 0x101d2c80 -- one piecewise-linear segment between two `points` entries
# ---------------------------------------------------------------------------


def build_segment(buf: list, max_value: int, a_in: int, a_out: int,
                  b_in: int, b_out: int) -> None:
    """``0x101d2c80(ptA, ptB, buf)``.

    Same accumulate-by-``fadd`` shape as :func:`build_ramp`, but with two
    differences that are real, not cosmetic:

    * a flat segment (``a_out == b_out``) is a straight ``rep stos`` of
      ``a_out`` with no float arithmetic at all (``0x101d2cb2``);
    * the sloped loops do **no** per-sample clamping — only the terminal fills
      clamp, to 0 (``0x101d2da9``) or to ``maxValue`` (``0x101d2e27``).

    The slope is computed once, stored through a ``float`` (``0x101d2d4e``
    ``fstp dword``) and re-read each iteration, so it is float32-precise.
    """
    buf[a_in] = a_out
    if _i16(a_in) == _i16(b_in):               # 0x101d2ca7
        return
    if (a_out & 0xFFFF) == (b_out & 0xFFFF):   # 0x101d2cb2 -- flat
        lo, hi = (a_in, b_in) if _i16(a_in) < _i16(b_in) else (b_in, a_in)
        start = lo + 1
        if _i16(start) > _i16(hi):
            return
        for k in range(start, hi + 1):
            buf[k] = a_out
        return
    buf[b_in] = b_out                          # 0x101d2cff
    if _i16(a_in) < _i16(b_in):                # ascending: 0x101d2d08
        i, last = a_in, b_in
        slope = _f32((float(b_out) - float(a_out)) / float(b_in - a_in))
        val = float(a_out)
    else:                                      # descending: 0x101d2d2b
        i, last = b_in, a_in
        slope = _f32((float(a_out) - float(b_out)) / float(a_in - b_in))
        val = float(b_out)
    i += 1
    if _i16(i) > _i16(last):
        return
    if slope < FZERO:                          # 0x101d2d64
        while True:
            val = val + slope
            if val <= FZERO:                   # -> 0x101d2da9
                for k in range(i, last + 1):
                    buf[k] = 0
                return
            buf[i] = _ftol16(ROUND_HALF + val)
            i += 1
            if _i16(i) > _i16(last):
                return
    max_f = _f32(float(max_value))             # 0x101d2de3
    while True:
        val = val + slope
        if val >= max_f:                       # -> 0x101d2e27
            for k in range(i, last + 1):
                buf[k] = max_value
            return
        buf[i] = _ftol16(ROUND_HALF + val)
        i += 1
        if _i16(i) > _i16(last):
            return


# ---------------------------------------------------------------------------
# 0x101d2eb0 -- constrainSlope
# ---------------------------------------------------------------------------

#: ``0x101d33f4``: the 6-entry jump table on ``sceneType - 1``.  Slots 3..6 all
#: land on the shared body with ``eax`` still holding ``sceneType`` itself, so
#: they select bands 3..6; only slots 1 and 2 rewrite it.  Anything outside
#: ``[1, 6]`` takes the default at ``0x101d2f4d``, which picks band 1 when the
#: ``x`` argument is exactly 2 and band 0 otherwise.
SLOPE_BAND_BY_SCENE_TYPE = {1: 0, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6}


def slope_band(scene_type: int, x: int) -> int:
    """Which of the seven per-band slope-limit rows ``constrainSlope`` uses."""
    if scene_type in SLOPE_BAND_BY_SCENE_TYPE:
        return SLOPE_BAND_BY_SCENE_TYPE[scene_type]
    return 1 if x == 2 else 0                  # 0x101d2f4d


def _regress(in_lut: list, first: int, last: int, step: int,
             n: float) -> float:
    """The least-squares slope of ``0x101d3020`` / ``0x101d3184``.

    ``(Sxy - Sy*Sx/n) / (Sxx - Sx*Sx/n)``, with ``n`` the *nominal* sample
    count ``csNSamples`` — not the number of samples the window actually
    visited.  The four sums are accumulated in the FPU register file in the
    order ``Sxy, Sx, Sy, Sxx``, from ``int`` operands (``fiadd`` / ``fild``),
    so ``x*y`` and ``x*x`` are 32-bit integer products, not float ones.
    """
    sxy = sx = sy = sxx = 0.0
    i = first
    while i <= last:
        y = _i16(in_lut[i])
        sxy += float(i * y)
        sx += float(i)
        sy += float(y)
        sxx += float(i * i)
        i += step
    num = sxy - (sy * sx) / n                  # 0x101d3060..0x101d3066
    den = sxx - (sx * sx) / n                  # 0x101d3068..0x101d306e
    return _fdiv(num, den)                     # 0x101d3070 fdivp


def constrain_slope_sample_bounds(p: ContrastParams) -> tuple[int, int]:
    """The lowest and highest ``in_lut`` indices ``constrainSlope`` samples.

    Worth having explicitly, because **the vendor does not bounds-check this**.
    The upward pass keeps starting windows while ``windowStart <= csUpperIndex``
    and then samples up to ``windowStart + (csNSamples-1)*step + leftover/2``,
    so with ``csUpperIndex`` close to ``lutSize`` it reads off the end of the
    LUT — a real out-of-bounds read in ``0x101d3024``, not a porting artefact.

    It cannot happen on the shipped configuration: ``csUpperIndex`` is 3999,
    the sample overhang is 18, and ``lutSize`` is 4096, so the top sample lands
    at 4017.  And ``csUpperIndex`` is in fact *unsettable* from a ``.dpi`` at
    all — see :data:`DPI_KEY_CS_UPPER_INDEX` — so 3999 is the only value the
    real scanner ever uses.  The port therefore does not emulate the overrun;
    :func:`constrain_slope` raises on an index it cannot legitimately reach.
    """
    step = _cdiv(p.csGranularity, p.csNSamples)
    span = (p.csNSamples - 1) * step
    half = _cdiv(_i16(p.csGranularity - span), 2)
    last_off = span + half
    fixed, upper, lower = (_i16(p.csFixedIndex), _i16(p.csUpperIndex),
                           _i16(p.csLowerIndex))
    hi = fixed
    if fixed <= upper:
        n_up = (upper - fixed) // p.csGranularity
        hi = fixed + n_up * p.csGranularity + last_off
    lo = fixed
    ws = fixed - p.csGranularity
    if ws >= lower:
        n_dn = (ws - lower) // p.csGranularity
        lo = ws - n_dn * p.csGranularity + half
    return min(lo, 0 if fixed == 0 else lo), hi


def constrain_slope(p: ContrastParams, results: ContrastResults,
                    in_lut: list, out_lut: list,
                    scene_type: int, x: int) -> None:
    """``0x101d2eb0(&status, sceneType, x, inLut, outLut)``.

    Three phases, and the middle one is the part that reads oddly until you
    see it: **``out_lut`` doubles as the flag array**.  The two regression
    passes write ``-1`` / ``+1`` / ``0`` per LUT index straight into
    ``out_lut``, and the re-integration phase then reads those flags back out
    of ``out_lut`` while overwriting it with the final curve.  There is no
    separate flag buffer.

    1. ``out_lut`` is zeroed, then walked **upward** from ``csFixedIndex`` to
       ``csUpperIndex`` in windows of ``csGranularity``.  Each window is
       sampled at ``csNSamples`` points and least-squares regressed; if the
       slope is below ``aUpperMinSlope[band]`` the whole window is flagged
       ``-1`` and ``bWasUpperMinLimitReached`` is set, if above
       ``aUpperMaxSlope[band]`` it is flagged ``+1`` and
       ``bWasUpperMaxLimitReached`` is set.
    2. The same walk **downward** from ``csFixedIndex - csGranularity`` to
       ``csLowerIndex`` against the ``aLower*`` limits and the ``bWasLower*``
       bytes.
    3. Re-integration.  ``out[fixed] = in[fixed]``; walking outward in both
       directions a running value ``D`` either accumulates the clamped limit
       slope (flagged windows) or tracks ``in[i] + offset`` (unflagged), where
       ``offset`` is refreshed as ``D - in[i]`` -- **through a float32 store**
       -- on every flagged sample.  Each entry is ``clamp(trunc(D + 0.5), 0,
       maxValue)``.
    """
    if not CONTRAST_CONSTRAIN_SLOPE_PORTED:
        _unported("CONTRAST_CONSTRAIN_SLOPE_PORTED", "constrainSlope (0x101d2eb0)")
    lut_size = p.lutSize
    _lo, _hi = constrain_slope_sample_bounds(p)
    if _hi >= lut_size or _lo < 0:
        raise ContrastError(
            f"constrainSlope would sample in_lut[{_lo}..{_hi}] outside "
            f"[0, {lut_size}) — the vendor reads out of bounds here "
            f"(0x101d3024); see constrain_slope_sample_bounds()")
    max_value = p.maxValue
    for i in range(lut_size):                  # 0x101d2edf: memset(outLut, 0)
        out_lut[i] = 0

    gran = p.csGranularity
    n_samp = p.csNSamples
    step = _cdiv(gran, n_samp)                 # 0x101d2f03 idiv
    span = (n_samp - 1) * step
    half = _cdiv(_i16(gran - span), 2)         # 0x101d2f19..0x101d2f25
    last_off = span + half                     # 0x101d2f29
    n = float(n_samp)                          # 0x101d2fc4 fild [esp+0x2c]

    b = slope_band(scene_type, x)
    lower_min = _f32(p.aLowerMinSlope[b])      # 0x101d2f59  impl+0x7c
    lower_max = _f32(p.aLowerMaxSlope[b])      # 0x101d2f61  impl+0xbc
    upper_min = _f32(p.aUpperMinSlope[b])      # 0x101d2f6c  impl+0xfc
    upper_max = _f32(p.aUpperMaxSlope[b])      # 0x101d2f77  impl+0x13c

    fixed = _i16(p.csFixedIndex)
    upper = _i16(p.csUpperIndex)
    lower = _i16(p.csLowerIndex)

    # -- phase 1: upward -----------------------------------------------------
    results.upperMinSlopeLimit = upper_min     # 0x101d2f86  impl+0x1a0
    results.upperMaxSlopeLimit = upper_max     # 0x101d2f97  impl+0x1a4
    results.bWasUpperMinLimitReached = False   # 0x101d2fa8  impl+0x1aa
    results.bWasUpperMaxLimitReached = False   # 0x101d2faf  impl+0x1ab
    ws = fixed
    if ws <= upper:                            # 0x101d2fbe
        s_first = ws + half
        s_last = ws + last_off
        while True:
            we = ws + gran
            slope = _regress(in_lut, s_first, s_last, step, n)
            flag = 0
            if slope < upper_min:              # 0x101d3078
                results.bWasUpperMinLimitReached = True
                flag = -1
            elif slope > upper_max:            # 0x101d3097
                results.bWasUpperMaxLimitReached = True
                flag = 1
            if flag and ws < we:
                for k in range(ws, we):
                    out_lut[k] = flag & 0xFFFF
            ws += gran                         # 0x101d30c5
            s_first += gran
            s_last += gran
            if ws > upper:
                break

    # -- phase 2: downward ---------------------------------------------------
    results.lowerMinSlopeLimit = lower_min     # 0x101d3105  impl+0x198
    results.lowerMaxSlopeLimit = lower_max     # 0x101d310b  impl+0x19c
    results.bWasLowerMinLimitReached = False   # 0x101d311c  impl+0x1a8
    results.bWasLowerMaxLimitReached = False   # 0x101d3123  impl+0x1a9
    ws = fixed - gran
    if ws >= lower:                            # 0x101d312e
        s_first = ws + half
        s_last = ws + last_off
        while True:
            we = ws + gran
            slope = _regress(in_lut, s_first, s_last, step, n)
            flag = 0
            if slope < lower_min:              # 0x101d31dd
                results.bWasLowerMinLimitReached = True
                flag = -1
            elif slope > lower_max:            # 0x101d31fa
                results.bWasLowerMaxLimitReached = True
                flag = 1
            if flag and ws < we:
                for k in range(ws, we):
                    out_lut[k] = flag & 0xFFFF
            ws -= gran                         # 0x101d322a
            s_first -= gran
            s_last -= gran
            if ws < lower:
                break

    # -- phase 3: re-integration --------------------------------------------
    out_lut[fixed] = in_lut[fixed]             # 0x101d3272
    d = float(_i16(in_lut[fixed]))             # 0x101d327a fild
    offset = 0.0                               # 0x101d3283
    for i in range(fixed + 1, lut_size):       # 0x101d32a0
        f = _i16(out_lut[i])
        if f < 0:
            d = d + upper_min                  # 0x101d32ac
            offset = _f32(d - float(_i16(in_lut[i])))
        elif f > 0:
            d = d + upper_max                  # 0x101d32c6
            offset = _f32(d - float(_i16(in_lut[i])))
        else:
            d = float(_i16(in_lut[i])) + offset  # 0x101d32e4
        r = _ftol16(ROUND_HALF + d)             # 0x101d32ec
        out_lut[i] = 0 if r < 0 else (max_value if r > max_value else r)

    d = float(_i16(out_lut[fixed]))            # 0x101d332d
    offset = 0.0
    for i in range(fixed - 1, -1, -1):         # 0x101d3352
        f = _i16(out_lut[i])
        if f < 0:
            d = d - lower_min                  # 0x101d335e
            offset = _f32(d - float(_i16(in_lut[i])))
        elif f > 0:
            d = d - lower_max                  # 0x101d3378
            offset = _f32(d - float(_i16(in_lut[i])))
        else:
            d = float(_i16(in_lut[i])) + offset  # 0x101d3396
        r = _ftol16(ROUND_HALF + d)
        out_lut[i] = 0 if r < 0 else (max_value if r > max_value else r)


# ---------------------------------------------------------------------------
# the Impl object
# ---------------------------------------------------------------------------


@dataclass
class ContrastImpl:
    """``AnsContrastAdjustCapabilityImpl`` — 0x1b8 bytes, ctor ``0x101d5e60``."""

    params: ContrastParams = field(default_factory=ContrastParams)
    results: ContrastResults = field(default_factory=ContrastResults)

    # -- 0x101d2e50 ---------------------------------------------------------
    def free_buffers(self) -> None:
        """``0x101d2e50`` — ``delete[]`` all three scratch LUTs and NULL them."""
        self.results.CAdjLut = None            # impl+0x1ac
        self.results.InToneLut = None          # impl+0x1b0
        self.results.OutToneLut = None         # impl+0x1b4

    # -- 0x101d7e70 ---------------------------------------------------------
    def set_params(self, p: ContrastParams) -> str | None:
        """``0x101d7e70``.  Copy in, validate, roll back on failure.

        The order is exactly the vendor's and all three steps are observable:

        1. back the current params up (``getParams`` ``0x1010b630``);
        2. ``operator=`` the new ones in (``0x1010b450``);
        3. ``validateParams`` (``0x101d3860``) — **on failure the params are
           assigned straight back from the backup** (``0x101d7ff5``), so a bad
           ``.dpi`` silently reverts to whatever the object already had rather
           than erroring the analysis out;
        4. on success, reseed ``results.lowSlope`` / ``results.highSlope`` from
           the *new* initial slopes, but only if ``lowSlope < 0`` (a
           freshly-constructed Impl, ``-1.0f``) **or** both results still equal
           the *old* params' initial slopes (``0x101d800e``).  That second
           clause is what stops a params reload from throwing away a slope the
           user moved with ``changeContrast()``; ``analyzeAutoTone`` never
           calls that, so on this path the reseed always happens.
        """
        if not CONTRAST_SET_PARAMS_PORTED:
            _unported("CONTRAST_SET_PARAMS_PORTED", "setParams (0x101d7e70)")
        if p is self.params:                   # 0x101d7ed2: identity -> no-op
            return None
        old = self.params.copy()
        self.params = p.copy()
        err = validate_params(self.params)
        if err is not None:
            self.params = old                  # 0x101d7ff5 rollback
            return err
        r = self.results
        if (r.lowSlope < FZERO
                or (r.lowSlope == _f32(old.lowInitialSlope)
                    and r.highSlope == _f32(old.highInitialSlope))):
            r.lowSlope = _f32(self.params.lowInitialSlope)   # 0x101d8054
            r.highSlope = _f32(self.params.highInitialSlope)
        return None

    # -- 0x101d8240 ---------------------------------------------------------
    def analyze(self, params: ContrastParams | None, scene_type: int, x: int,
                tone_lut: list | None,
                keep_intermediates: bool = CONTRAST_KEEP_INTERMEDIATES_DEFAULT
                ) -> ContrastResults:
        """``0x101d8240(&status, holder, capFlagE, params, sceneType, x, tone)``.

        Pure LUT domain: ``lutSize`` shorts in, ``lutSize`` shorts out, no
        pixels anywhere.  ``params`` is the object ``0x101d8880`` resolved; when
        it is not already this Impl's embedded one, ``setParams`` copies it in
        first and its status is then **discarded** (``0x101d82a2``).
        """
        if not CONTRAST_LUT_BUILD_PORTED:
            _unported("CONTRAST_LUT_BUILD_PORTED", "analyze (0x101d8240)")
        if params is not None and params is not self.params:
            self.set_params(params)            # status deliberately dropped

        p = self.params
        r = self.results
        lut_size = p.lutSize
        mode = p.userInputMode

        # 0x101d82c5: a NULL tone LUT is only survivable in the two OVERRIDE
        # modes, which never read it.  Every other mode cleans up and returns
        # OK having built nothing at all.
        if tone_lut is None and mode not in MODES_OVERRIDE:
            self.free_buffers()
            return r

        self.free_buffers()                    # 0x101d82e3
        out_lut = [0] * lut_size               # impl+0x1b4, "new ansPixel_t"
        adj_lut = [0] * lut_size if mode != MODE_NO_USER_INPUT else None
        in_lut = None
        if mode not in MODES_OVERRIDE:         # 0x101d8445
            in_lut = list(tone_lut[:lut_size])  # impl+0x1b0 <- memcpy(tone)
            if p.bConstrainSlope:              # 0x101d84cb
                constrain_slope(p, r, in_lut, out_lut, scene_type, x)

        r.lutSize = lut_size                   # 0x101d855b impl+0x18c

        # -- the adjustment curve, into adj_lut ------------------------------
        if mode in MODES_WITH_SLOPE:           # 0x101d85b9
            build_ramp(adj_lut, p.maxValue, p.midpointIn, p.midpointOut,
                       0, r.lowSlope)
            build_ramp(adj_lut, p.maxValue, p.midpointIn, p.midpointOut,
                       lut_size - 1, r.highSlope)
        elif mode in MODES_WITH_POINT:         # 0x101d8578
            for i in range(lut_size):
                adj_lut[i] = 0
            for (a_in, a_out), (b_in, b_out) in zip(p.points, p.points[1:]):
                build_segment(adj_lut, p.maxValue, a_in, a_out, b_in, b_out)

        # -- compose -------------------------------------------------------
        # 0x101d85ef: the source for COMBINE is the *constrained* curve when
        # bConstrainSlope ran, otherwise the raw copy of the incoming LUT.
        src = out_lut if p.bConstrainSlope else in_lut
        if mode in MODES_COMBINE:              # 0x101d8697
            for i in range(lut_size):
                out_lut[i] = adj_lut[_i16(src[i])]
        elif mode in MODES_OVERRIDE:           # 0x101d8681
            out_lut[:] = adj_lut
        else:                                  # 0x101d8617, NO_USER_INPUT
            if src is not out_lut:
                out_lut[:] = src

        r.OutToneLut = out_lut
        r.CAdjLut = adj_lut
        r.InToneLut = in_lut
        if not keep_intermediates:             # 0x101d8633, cap+0xe == 0
            r.CAdjLut = None
            r.InToneLut = None
        return r


# ---------------------------------------------------------------------------
# 0x101d8880 -- the params-resolving front end
# ---------------------------------------------------------------------------


def acquire(impl: ContrastImpl, holder, cap_flag_e: bool, scene_type: int,
            x: int, tone_lut: list | None, *,
            registry: dict | None = None,
            scene_dpi_key: str | None = None) -> ContrastResults:
    """``0x101d8880(&status, holder, capFlagE, sceneType, x, tone)``.

    1. resolve the scene holder (``0x10021730``); on failure log ``.cpp``
       line 176 and return the status;
    2. default-construct a local ``AnsContrastAdjustParams`` (``0x1005dab0``)
       and hand it to ``selectParams`` (``0x101d5d20``) to be filled from the
       scene's DPI; on failure log line 185 and return;
    3. re-push its own six arguments with the resolved params spliced in as a
       seventh and tail-call the LUT builder ``0x101d8240``.
    """
    if not CONTRAST_ACQUIRE_PORTED:
        _unported("CONTRAST_ACQUIRE_PORTED", "acquire (0x101d8880)")
    if holder is None:
        raise ContrastError(f"holder failed ({SRC_FILE}:{LINE_HOLDER_FAILED})")
    if registry is not None and scene_dpi_key is not None:
        params = select_params(scene_dpi_key, registry)
    else:
        params = ContrastParams()              # 0x1005dab0's defaults
    return impl.analyze(params, scene_type, x, tone_lut,
                        keep_intermediates=cap_flag_e)


# ---------------------------------------------------------------------------
# the AutoToneSubsystems hook
# ---------------------------------------------------------------------------


class ContrastSubsystem:
    """Adapter for ``pakon_autotone.AutoToneSubsystems``' contrast pair.

    The shell calls ``contrast_acquire(holder, sceneType, x, tone)`` then
    ``contrast_get_results()`` and reads ``OutToneLut`` out of the returned
    0x2c-byte blob (``0x100fc6fb`` -> ``0x10109d70``, a bare ``rep movsd``).
    """

    def __init__(self, params: ContrastParams | None = None,
                 keep_intermediates: bool = CONTRAST_KEEP_INTERMEDIATES_DEFAULT):
        self.impl = ContrastImpl()
        self.impl.set_params(params or ContrastParams())
        self.keep_intermediates = keep_intermediates
        self.results: ContrastResults | None = None

    def acquire(self, holder, scene_type: int, x: int, tone_lut):
        self.results = self.impl.analyze(
            None, scene_type, x, tone_lut,
            keep_intermediates=self.keep_intermediates)
        return None                            # AnsStatus.OK

    def get_results(self) -> ContrastResults:
        if self.results is None:
            raise ContrastError("getResults before acquire")
        return self.results


__all__ = [
    "replace",
    "ContrastParams", "ContrastResults", "ContrastImpl", "ContrastSubsystem",
    "ContrastError", "parse_dpi", "select_params", "validate_params",
    "build_ramp", "build_segment", "constrain_slope", "slope_band", "acquire",
    "MODE_NO_USER_INPUT", "MODE_COMBINE_WITH_SLOPE", "MODE_COMBINE_WITH_POINT",
    "MODE_OVERRIDE_WITH_SLOPE", "MODE_OVERRIDE_WITH_POINT", "MODE_NAMES",
    "DPI_KEYS", "DPI_KEY_CS_UPPER_INDEX",
    "CONTRAST_KEEP_INTERMEDIATES_DEFAULT",
]
