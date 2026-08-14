#!/usr/bin/env python3
"""``AnsCnaCapabilityImpl`` — the ``cna`` tone subsystem of ``analyzeAutoTone``.

PakonIMAu.dll ImageBase ``0x10000000`` (file VAs == cited VAs), sha256
``0ede8d9813af4ee95dddd85e5adc495a27f014a8fd4817cfbc3b3b1e107f511f``.  This
file is to ``cna`` what ``pakon_autotone.py`` is to the ``analyzeAutoTone``
shell: the subsystem plus its ``*_PORTED`` flags.  Every flag that is ``False``
raises ``RuntimeError`` when its function is called — nothing silently no-ops
(the pattern at ``pakon_shasta.py:2404-2405``).

THE BRIEF'S "TWO ENTRY-POINT VARIANTS" IS WRONG — PROVEN BELOW
=============================================================
Phase 2a was briefed that ``cna``'s acquire-Impl has two variants, ``0x1022ea50``
(with histogram) and ``0x1022b530`` (without).  **``0x1022b530`` is not cna's.**
A full ``E8 rel32`` scan of ``.text`` (7,598,080-byte image, ``.text`` only,
every direct call and jmp) finds exactly one direct caller for each of the three
addresses in question::

    0x1022b530  <- 0x1013115b   inside 0x10131100 = dra's Cap acquire+hist
    0x1022af20  <- 0x10131071   inside 0x10131020 = dra's Cap acquire
    0x1022ea50  <- 0x10132e11   inside 0x10132dc0 = cna's Cap acquire

and ``0x10131100`` / ``0x10131020`` are reached only from ``0x100fc0dd`` /
``0x100fc17d``, which are the **dra** stage of ``analyzeAutoTone``
(``pakon_autotone.CAP_CALLS`` already records exactly this).  ``0x1022b530``
therefore belongs to the concurrent ``dra`` port, not here, and porting it in
this file would have duplicated another agent's subsystem.

``cna``'s Cap wrapper ``0x10132dc0`` contains **one** call into an Impl —
``call 0x1022ea50`` at ``0x10132e11``, with ``ecx = *(cap+0x10)`` — and the
shell calls that wrapper unconditionally, with no histogram fork
(``0x100fbe28``; see ``pakon_autotone``'s "Stage 1 — cna").  The with/without
histogram fork the brief describes is real, but it is **dra's and toneHelper's**
(``0x100fc0af`` and ``0x100fc329``), not cna's.  cna is the stage that
*produces* the histograms the other two fork on.

The DLL names the function itself: ``0x1022ea50`` pushes
``"AnsCnaCapabilityImpl::analyze"`` (``0x1059f94c``) and
``"\\Atc\\ansel\\src\\libCna.ansel\\AnsCnaCapabilityImpl.cpp"`` (``0x1059f8cc``)
at its throw site (``0x1022eada``).  So the address earlier scoping called
"analyze" and Phase 1 called "acquire Impl" are the same function, and its real
name is ``analyze``.

REACHABILITY (``tools/re/reachability.py walk``, ``aaa``, this session)
======================================================================
``walk(0x1022ea50)`` = **36 functions / 11,593 bytes (realsz) / 22 indirect call
sites / 71 IAT call sites / 119 direct call sites** — byte-identical to the
figure ``pakon_autotone.py`` already cites for cna.  Of those 36, 20 are CRT /
smart-pointer / ostream plumbing; the 16 that carry cna's own arithmetic are the
ones ported below.

THE OBJECT — ``AnsCnaCapabilityImpl``
====================================
``ecx`` at ``0x1022ea50`` is the Impl.  Two windows of it cross the shell
boundary, and ``pakon_autotone.AUTOTONE_WORK_LAYOUT`` already names both:

* ``impl+0x0c`` .. ``+0x87``  — ``AnsCnaParams``, 0x7c bytes, copied out by
  ``0x10132070``.  Phase 1 proved its ctor defaults (``0x100f8030``) match
  ``vendor/ansel/anselinstalldir/dataPathItems/cna/ansel-cna-default-default.dpi``
  key for key; that finding is **reused**, not re-derived — this file imports
  the table rather than restating it (``params_from_impl``).
* ``impl+0x88`` .. ``+0xe7`` — ``AnsCnaResults``, 0x60 bytes, copied out by
  ``0x101320b0``.

The results window is **independently confirmed here**, by a second artefact
Phase 1 did not have: ``AnsCnaCapabilityImpl::allocateMemory`` (``0x1022d970``)
seeds it with a 0x18-dword ``rep movsd`` from a stack template built at
``0x1022d9a7``..``0x1022da0a``, and that template is field-for-field the same
seed pattern ``analyzeAutoTone``'s own inline ctor writes at ``0x100fbea8``
(``-1`` per i32, ``0xbf800000`` per f32, ``0`` per pointer/bool, byte ``0`` at
``+0x5c``).  Two independent writers agreeing on all 24 slots.

What the shell's layout calls unnamed slots ``+0x30``..``+0x50`` are the working
buffers ``allocateMemory`` hangs off the object; naming them here (they never
leave the subsystem, but the port needs them):

=========  ===================  =============================================
 impl off   AnsCnaResults off    what
=========  ===================  =============================================
 +0x88      +0x00  nPixels       W*H
 +0x8c      +0x04  --            luminance plane, int16 x nPixels
 +0x90      +0x08  LuminanceHist int32 x histSize
 +0x94      +0x0c  --            laplacian plane, int16 x nPixels
 +0x98      +0x10  threshold     the surviving edge threshold
 +0x9c      +0x14  nEdgePixels   sum(EdgeHist)
 +0xa0      +0x18  --            (never allocated; stays 0)
 +0xa4      +0x1c  EdgeHist      int32 x histSize
 +0xa8      +0x20  darkInSigma   f32
 +0xac      +0x24  lightInSigma  f32
 +0xb0      +0x28  darkOutSigma  f32
 +0xb4      +0x2c  lightOutSigma f32
 +0xb8      +0x30  --            gauss padded scratch
 +0xbc      +0x34  --            gauss kernel scratch
 +0xc0      +0x38  --            resample scratch (float)
 +0xc4      +0x3c  --            int scratch A
 +0xc8      +0x40  --            bucketed edge histogram, int32 x nBuckets
 +0xcc      +0x44  --            float scratch
 +0xd0      +0x48  --            float scratch
 +0xd4      +0x4c  --            float scratch
 +0xd8      +0x50  --            float scratch
 +0xdc      +0x54  ToneScaleLut  int16 x histSize  <- the one the shell threads
 +0xe0      +0x58  elmoPercent   f32
 +0xe4      +0x5c  bElmoOccured  bool
=========  ===================  =============================================

``ToneScaleLut`` landing at ``AnsCnaResults+0x54`` is what makes the shell's
``ctx+0x64d0 = results.ToneScaleLut`` (``0x100fbfc1``) pick up this file's
output; ``analyze_to_results`` returns a 0x60-byte buffer with that offset
filled, so the shell needs no change beyond being handed one.

THE ELMO FORK — cna's half
==========================
``bElmoOccured`` (``+0xe4``) and ``elmoPercent`` (``+0xe0``) are written at
``0x1022e874``..``0x1022e9a9``, inside ``analyzeImage``.  cna's half of the
fork ``docs``/Phase 1 describe is exactly this: seed ``elmoPercent = -1.0f`` and
``bElmoOccured = 0`` (both **before** either gate is evaluated), then run the
per-pixel saturation count only if ``lightInSigma > lightOutSigma``
(``0x1022e865``, comparing ``results+0x24`` against ``results+0x2c`` -- the
light half's own input sigma against its clamped target, i.e. "the highlight
spread had to be compressed") **and** ``elmoCriticalPercent < 100.0f``
(``0x1022e890``, a disable switch; the shipped DPI value is 5.0, so it is live).
If it runs, ``elmoPercent = count*100.0f/nPixels`` and ``bElmoOccured =
elmoPercent > elmoCriticalPercent`` -- **strictly** greater (``0x1022e9a4``'s
``test ah,0x41; jne`` skips the store on equal as well as on less; the golden
carries an exact-equality case for precisely this, because a port using ``>=``
passes without one).

The other half — ``x = elmoAggressiveness`` with the ``3 <= ctx+0x44 <= 6 -> 0``
reset versus ``x = toneHelperResults[+0xb4]`` — is the shell's
(``0x100fc5cd``), is already ported in ``pakon_autotone``, and is not
duplicated here.

FLOATING POINT
==============
Every float in this subsystem is stored as ``float32`` and computed on the x87
stack.  ``0x104ffe44`` is ``_ftol2`` — truncation toward zero — and the vendor's
rounding idiom throughout is ``fadd qword [0x10574f40] (0.5); call 0x104ffe44``,
i.e. ``trunc(x + 0.5)``.  The port keeps register values in Python ``float``
(binary64) and applies ``f32()`` at exactly the points the vendor does a
``fst``/``fstp dword``.  That is faithful when the x87 precision-control field
is 53-bit, which is what MSVC's CRT sets on Win32 (``CW = 0x027f``); the golden
harness sets ``FPCW`` to ``0x027f`` for the same reason, and also reports
whether the default ``0x037f`` (64-bit) changes any answer.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
  tools/ansel/python-pipeline/pakon_cna.py``
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from typing import Sequence



def _at():
    """Phase 1's layout tables (``pakon_autotone``), imported lazily.

    ``pakon_autotone`` imports **this** module to pick up
    ``CNA_ANALYZE_PORTED``, so a module-level ``import pakon_autotone`` here
    would be a cycle: whichever of the two is imported first would find the
    other half-initialised, and ``from pakon_cna import CNA_ANALYZE_PORTED``
    would raise.  Every use of the tables is inside a function, so importing on
    demand removes the cycle without restating a single offset -- the point of
    reusing Phase 1's table rather than re-deriving it.
    """
    import pakon_autotone
    return pakon_autotone


# ---------------------------------------------------------------------------
# addresses
# ---------------------------------------------------------------------------

CNA_ANALYZE = 0x1022EA50           # AnsCnaCapabilityImpl::analyze
CNA_VALIDATE_PARAMS = 0x1022CEB0   # params sanity check -> "Bad field(#N)"
CNA_ALLOCATE_MEMORY = 0x1022D970   # AnsCnaCapabilityImpl::allocateMemory
CNA_ANALYZE_IMAGE = 0x1022DDC0     # the whole tone analysis
CNA_FREE_SCRATCH = 0x1022D1A0      # frees 12 of the 15 buffers
CNA_FREE_ALL = 0x1022D2E0          # freeScratch + LuminanceHist/EdgeHist/Lut
CNA_LAPLACIAN = 0x1022C340         # 5-point laplacian, int16 wraparound
CNA_GAUSS_SMOOTH = 0x1022C8F0      # 1-D gaussian convolution with edge clamp
CNA_PEAK_SEARCH = 0x1022C3E0       # argmax of f[i-2]+f[i+2]-2f[i]
CNA_HIST_RESAMPLE = 0x1022CA80     # moments + smooth + resample
CNA_MAP_DOWN = 0x1022C520          # inverse map, descending half
CNA_MAP_UP = 0x1022C630            # inverse map, ascending half
CNA_TONE_LUT_BUILD = 0x1022C740    # bucket curve -> int16 ToneScaleLut

CRT_FTOL2 = 0x104FFE44             # truncation toward zero (edx:eax)
CRT_NEW_ARRAY = 0x104FFD78         # jmp -> 0x104ffd53, operator new
CRT_DELETE_ARRAY = 0x104FFE3E      # operator delete[]

#: The Cap-level wrapper Phase 1 already ported.  One call into one Impl.
CNA_CAP_ACQUIRE = 0x10132DC0
CNA_CAP_GET_RESULTS = 0x10132ED0
CNA_CAP_GET_PARAMS = 0x10132EA0
CNA_IMPL_GET_RESULTS = 0x101320B0
CNA_IMPL_GET_PARAMS = 0x10132070

#: The address the brief mis-attributed to cna.  Recorded so the next reader
#: does not have to re-run the scan.  Sole direct caller 0x1013115b.
NOT_CNA_DRA_ACQUIRE_HIST = 0x1022B530

SRC_FILE = r"\Atc\ansel\src\libCna.ansel\AnsCnaCapabilityImpl.cpp"
FUNC_ANALYZE = "AnsCnaCapabilityImpl::analyze"
FUNC_ALLOCATE = "AnsCnaCapabilityImpl::allocateMemory"
BAD_FIELD_LINE = 0x4BB             # 1211, pushed at 0x1022eacb
BAD_FIELD_CODE = 0x69              # 105, pushed at 0x1022eae3
ALLOC_FAIL_LINE = 0x5C5            # 1477, pushed at 0x1022dbfe
ALLOC_FAIL_CODE = 0xCA             # 202, pushed at 0x1022dc15

#: float/double literals the subsystem reads out of .rdata.
K_HALF = 0.5                       # qword 0x10574f40
K_MINUS_HALF = -0.5                # qword 0x1057ae70
K_INV_SQRT_2PI = 0.3989423241103187  # qword 0x1059a858 -- NOT exactly
#                                     1/sqrt(2*pi) (0.3989422804014327); the
#                                     shipped constant is used verbatim.
K_ZERO_F32 = 0.0                   # dword 0x10575674
K_ZERO_F64 = 0.0                   # qword 0x10573c40
K_ONE_F32 = 1.0                    # dword 0x1058d4c0
K_HUNDRED_F32 = 100.0              # dword 0x1059bea8
K_LUT_MAX = 0x0FFF                 # clamp used by the luminance and LUT paths

# ---------------------------------------------------------------------------
# flags
# ---------------------------------------------------------------------------

#: ``0x104ffe44``.  `fld st(0); fst dword; fistp qword; fild qword` then a
#: carry-flag fixup that turns round-to-nearest into truncate-toward-zero.
#: Verified over a boundary sweep by ``pakon_cna_golden.py``.
CNA_FTOL2_PORTED = True

#: ``0x1022c340``.  `lap = left + right + up + down - 4*centre` on the interior,
#: computed in **16-bit** registers (`shl bx,2` / `sub bp,bx` / `add bp,word`),
#: so it wraps rather than saturating.  Verified bit-exact.
CNA_LAPLACIAN_PORTED = True

#: ``0x1022c8f0``.  Kernel `exp(-i^2/(2*sigma^2)) * 0.3989423241103187/sigma`
#: over `i in [-d, d]`, `d = trunc(sigma*smoothingSizeFactor + 0.5)`, input
#: edge-clamped into a `n + 2d` scratch, then a plain dot product per output.
#: Verified bit-exact.
CNA_GAUSS_SMOOTH_PORTED = True

#: ``0x1022c3e0``.  argmax over `j in [start, limit]` of
#: `f[j-2] + f[j+2] - 2*f[j]`, strictly-greater wins.  Verified bit-exact.
CNA_PEAK_SEARCH_PORTED = True

#: ``0x1022ca80``.  First and second moments of an int histogram, sigma, a
#: gaussian smooth of the normalised copy, then a resample into an int array.
#: Verified bit-exact, including the resample loop's int32 store truncation
#: (``0x1022ce98``) that a real scanned roll's NaN-sigma case exposed --
#: live-DLL-confirmed against that exact real histogram, see the resample
#: loop's own comment.
CNA_HIST_RESAMPLE_PORTED = True

#: ``0x1022c520`` / ``0x1022c630`` — the descending and ascending halves of the
#: tone curve.  One mirrored routine; verified bit-exact in both directions.
CNA_CONTRAST_MAP_PORTED = True

#: ``0x1022c740`` — bucket curve to the int16 ToneScaleLut, including both
#: extrapolated tails and the 0x0fff fill.  Verified bit-exact.
CNA_TONE_LUT_BUILD_PORTED = True

#: ``0x1022d970`` — buffer sizes only (no arithmetic on image data).  The port
#: computes the same sizes; the buffers themselves are Python lists.
CNA_ALLOCATE_MEMORY_PORTED = True

#: ``0x1022ddc0`` — the whole tone analysis, entry to return, including the
#: pivot percentile, the bucketing, both dark/light halves, both curve halves,
#: the elmo test, the LUT expansion and the pivot normalisation.  Verified
#: bit-exact against the real function's own AnsCnaResults and ToneScaleLut.
CNA_ANALYZE_IMAGE_PORTED = True

#: ``0x1022e865``..``0x1022e9a9`` — the ELMO test, i.e. cna's half of the
#: ``bElmoOccured`` fork the shell resolves at ``0x100fc5cd``.  Verified
#: bit-exact by running the real ``0x1022ddc0`` and driving its two gate inputs
#: (``lightInSigma`` / ``lightOutSigma``) from the harness.
CNA_ELMO_PORTED = True

#: ``0x1022ddc0``'s first half — luminance plane, luminance histogram,
#: laplacian, laplacian histogram, peak search, threshold relaxation loop and
#: the identity-LUT early return.  Verified bit-exact end to end.
CNA_ANALYZE_IMAGE_THRESHOLD_PORTED = True

#: ``0x1022ceb0`` — the AnsCnaParams field validator behind
#: "Bad field(#N) in AnsCnaParams structure!".  22 field checks; verified
#: against the DLL over the shipped params and one perturbation per check.
CNA_VALIDATE_PARAMS_PORTED = True

#: ``0x1022ea50`` — ``AnsCnaCapabilityImpl::analyze``, the entry the shell's
#: Cap wrapper ``0x10132dc0`` calls.  Verified end to end **through the real
#: Cap wrapper and the real 0x101320b0 getter**, i.e. across exactly the
#: boundary ``pakon_autotone`` models.
CNA_ANALYZE_PORTED = True


def _unported(flag: str, va: int, what: str):
    raise RuntimeError(
        f"{flag} is False: {what} ({va:#x}) is not ported. See "
        f"tools/ansel/python-pipeline/pakon_cna.py and "
        f"docs/64-pruned-tone-producers.md.")


# ---------------------------------------------------------------------------
# float32 / x87 helpers
# ---------------------------------------------------------------------------

def f32(x: float) -> float:
    """One ``fst``/``fstp dword`` — round a register value to float32."""
    return struct.unpack("<f", struct.pack("<f", x))[0]


#: x87's "real indefinite" QNaN, sign bit set (``0xffc00000`` as float32) --
#: what a masked-exception 0.0/0.0 produces under FPCW 0x027f.  Same constant
#: ``pakon_ast.X87_INDEFINITE`` / ``pakon_toneHelper.X87_INDEFINITE``
#: document; duplicated here rather than cross-imported so this file stays
#: self-contained, matching this file's own ``f32`` (also duplicated per
#: subsystem rather than shared).
X87_INDEFINITE = -math.nan


def _x87_div(num: float, den: float) -> float:
    """``fdiv``/``fdivr`` under FPCW ``0x027f``'s masked exceptions.

    Found by Phase 6.1's assembled run (``docs/66``): ``analyze_image``'s
    ``_half`` normalises ``bucket[i]/sum(bucket)`` and ``r.out[i]/sum(r.out)``
    unconditionally, and a real (pseudo-random, not hand-crafted) test image
    can legitimately leave one of those sums at 0 -- e.g. every edge-histogram
    bucket landing empty.  No leaf-level ``pakon_cna_golden.py`` case happened
    to construct that degenerate a bucket array.  The real DLL does not trap:
    it masks the zero-divide exception and produces a correctly-signed
    infinity (0.0/0.0 instead yields the "real indefinite" QNaN above).
    Python's ``/`` raises ``ZeroDivisionError`` on both -- the same class of
    bug already fixed once in this project, in ``pakon_ast._x87_div``.
    """
    if den == 0.0:
        if num == 0.0:
            return X87_INDEFINITE
        return math.copysign(math.inf, num) * math.copysign(1.0, den)
    return num / den


def i16(x: int) -> int:
    """One 16-bit register write (``mov word``), two's complement."""
    x &= 0xFFFF
    return x - 0x10000 if x & 0x8000 else x


def i32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


def idiv(a: int, b: int) -> int:
    """x86 ``idiv`` — quotient truncated toward zero."""
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def ftol2(x: float) -> int:
    """``0x104ffe44`` — ``_ftol2``: truncate toward zero, 64-bit result.

    The vendor implementation is ``fistp qword`` (round-to-nearest-even, the
    default control word) followed by a carry-flag correction that subtracts 1
    when the rounded value overshot a positive input and adds 1 when it
    overshot a negative one.  The observable behaviour is exactly C's
    ``(long long)x``; the port asserts that against the real code rather than
    assuming it (``pakon_cna_golden.py``, boundary sweep).
    """
    if not CNA_FTOL2_PORTED:
        _unported("CNA_FTOL2_PORTED", CRT_FTOL2, "_ftol2")
    if math.isnan(x) or math.isinf(x):
        return -(1 << 63)
    return math.trunc(x)


def round_half_up(x: float) -> int:
    """The vendor's ubiquitous ``fadd 0.5; call _ftol2``.

    Note this is **not** ``round()``: it is ``trunc(x + 0.5)``, so it rounds
    half away from zero for positives and toward zero for negatives, and the
    ``+0.5`` happens on the x87 stack at register precision, before any float32
    store.
    """
    return ftol2(x + K_HALF)


# ---------------------------------------------------------------------------
# AnsCnaParams — read straight off the Impl, using Phase 1's proven table
# ---------------------------------------------------------------------------

#: Impl offset of the params block.  ``0x10132070`` copies 0x1f dwords from
#: here; every ``[esi+N]`` in the subsystem with ``0x0c <= N < 0x88`` is
#: ``params + (N - 0x0c)``.
PARAMS_AT = 0x0C
RESULTS_AT = 0x88


@dataclass
class CnaParams:
    """``AnsCnaParams`` (0x7c B), by the names ``AUTOTONE_WORK_LAYOUT`` proves.

    Defaults are ``0x100f8030``'s, i.e. ``ansel-cna-default-default.dpi``.
    Reused from Phase 1's table, not re-derived.
    """

    redShift: int = 0
    greenShift: int = 0
    blueShift: int = 0
    histSize: int = 5000
    bucketSize: int = 10
    lowClamp: float = 0.5              # +0x10, unnamed by the dumper
    highClamp: float = 1.5             # +0x14, unnamed by the dumper
    blend: float = 1.0
    pivot: int = 1550
    minPivotPercentile: float = 0.1
    maxPivotPercentile: float = 0.9
    thresholdMultiplier: float = 1.5
    thresholdReductionFactor: float = 0.949
    minPosThreshold: int = 4
    minLapPixelRatio: float = 0.1
    smoothingSizeFactor: float = 4.0
    laplacianHistSmoothingSigma: float = 10.0
    coarseHistSmoothingSigma: float = 2.0
    toneScaleSmoothingSigma: float = 4.0
    darkMaxContrastGain: float = 1.3333300352096558
    lightMaxContrastGain: float = 1.3333300352096558
    darkScale: float = 243.74998474121094   # +0x50, unnamed
    lightScale: float = 243.74998474121094  # +0x54, unnamed
    unk58: float = 260.0
    unk5c: float = 84.5
    minGaussSigma: float = 1.0
    maxGaussSigma: float = 50.0
    elmoNeutralLimit: int = 1500
    elmoRedLimit: int = 1600
    elmoGreenLimit: int = 1600
    elmoBlueLimit: int = 1600
    elmoSatThreshold: int = 400
    elmoCriticalPercent: float = 5.0
    elmoAggressiveness: int = 1


#: ``AnsCnaParams`` offset -> (attribute, struct code).  The offsets and the
#: named fields come from ``pakon_autotone.AUTOTONE_WORK_LAYOUT["AnsCnaParams"]``
#: (Phase 1, DPI-cross-checked); only the four slots the dumper leaves unnamed
#: get local names here.
PARAM_FIELDS: tuple[tuple[int, str, str], ...] = (
    (0x00, "redShift", "<h"),
    (0x02, "greenShift", "<h"),
    (0x04, "blueShift", "<h"),
    (0x08, "histSize", "<i"),
    (0x0C, "bucketSize", "<i"),
    (0x10, "lowClamp", "<f"),
    (0x14, "highClamp", "<f"),
    (0x18, "blend", "<f"),
    (0x1C, "pivot", "<h"),
    (0x20, "minPivotPercentile", "<f"),
    (0x24, "maxPivotPercentile", "<f"),
    (0x28, "thresholdMultiplier", "<f"),
    (0x2C, "thresholdReductionFactor", "<f"),
    (0x30, "minPosThreshold", "<h"),
    (0x34, "minLapPixelRatio", "<f"),
    (0x38, "smoothingSizeFactor", "<f"),
    (0x3C, "laplacianHistSmoothingSigma", "<f"),
    (0x40, "coarseHistSmoothingSigma", "<f"),
    (0x44, "toneScaleSmoothingSigma", "<f"),
    (0x48, "darkMaxContrastGain", "<f"),
    (0x4C, "lightMaxContrastGain", "<f"),
    (0x50, "darkScale", "<f"),
    (0x54, "lightScale", "<f"),
    (0x58, "unk58", "<f"),
    (0x5C, "unk5c", "<f"),
    (0x60, "minGaussSigma", "<f"),
    (0x64, "maxGaussSigma", "<f"),
    (0x68, "elmoNeutralLimit", "<h"),
    (0x6A, "elmoRedLimit", "<h"),
    (0x6C, "elmoGreenLimit", "<h"),
    (0x6E, "elmoBlueLimit", "<h"),
    (0x70, "elmoSatThreshold", "<h"),
    (0x74, "elmoCriticalPercent", "<f"),
    (0x78, "elmoAggressiveness", "<i"),
)


def params_from_bytes(buf: bytes) -> CnaParams:
    """Decode a 0x7c-byte ``AnsCnaParams`` image (what ``0x10132070`` copies)."""
    p = CnaParams()
    for off, name, code in PARAM_FIELDS:
        setattr(p, name, struct.unpack_from(code, buf, off)[0])
    return p


def params_to_bytes(p: CnaParams) -> bytes:
    buf = bytearray(_at().AUTOTONE_WORK_LAYOUT["AnsCnaParams"]["size"])
    for off, name, code in PARAM_FIELDS:
        struct.pack_into(code, buf, off, getattr(p, name))
    return bytes(buf)


def default_params() -> CnaParams:
    """``0x100f8030``'s defaults, via Phase 1's already-verified seed table."""
    return params_from_bytes(bytes(_at().default_construct("AnsCnaParams")))


# ---------------------------------------------------------------------------
# the image the subsystem is handed
# ---------------------------------------------------------------------------


@dataclass
class CnaImage:
    """What ``0x1022ddc0`` reads out of its second argument.

    ``mov ebx,[eax+0x20]`` / ``mov ecx,[eax+0x0c]`` / ``mov eax,[eax+0x10]`` at
    ``0x1022ddc8``..``0x1022ddd2`` — and nothing else in the descriptor is
    touched.  ``pixels`` is an interleaved R,G,B ``int16`` buffer, three shorts
    per pixel, ``width*height`` pixels, row-major with no padding (the luminance
    loop walks it with a flat ``add ebx,2`` x3 per pixel).
    """

    width: int              # +0x0c
    height: int             # +0x10
    pixels: Sequence[int]   # +0x20, 3*width*height int16


# ---------------------------------------------------------------------------
# 0x1022c340 -- the laplacian
# ---------------------------------------------------------------------------


def laplacian(lum: Sequence[int], width: int, height: int) -> list[int]:
    """``0x1022c340`` — 5-point laplacian over the interior, in **int16**.

    ``lap = left + right + up + down - 4*centre``.  The vendor computes it
    entirely in 16-bit registers::

        mov  bx, word [centre]     ; 0x1022c374
        mov  bp, word [left]
        shl  bx, 2                 ; *4, 16-bit -- wraps
        sub  bp, bx
        add  bp, word [up]
        add  bp, word [down]
        add  bp, word [right]
        mov  word [out], bp

    so every intermediate wraps modulo 2**16.  With the 12-bit luminance the
    subsystem actually feeds it that never matters, but a caller handing it
    unclamped values (the ``shiftSum == 0`` luminance branch does not clamp)
    would see the wrap, so the port reproduces it rather than widening.

    Output is dense: ``(height-2) * (width-2)`` entries, row-major.  Returns an
    empty list when either dimension is <= 2 (the vendor's ``jle`` guards).
    """
    if not CNA_LAPLACIAN_PORTED:
        _unported("CNA_LAPLACIAN_PORTED", CNA_LAPLACIAN, "laplacian")
    out: list[int] = []
    if height <= 2:
        return out
    for r in range(height - 2):
        if width > 2:
            base = (r + 1) * width
            for c in range(1, width - 1):
                centre = lum[base + c]
                v = i16(lum[base + c - 1] - i16(centre * 4))
                v = i16(v + lum[base - width + c])
                v = i16(v + lum[base + width + c])
                v = i16(v + lum[base + c + 1])
                out.append(v)
    return out


# ---------------------------------------------------------------------------
# 0x1022c8f0 -- 1-D gaussian convolution
# ---------------------------------------------------------------------------


def gauss_half_width(sigma: float, smoothing_size_factor: float) -> int:
    """``d`` = ``trunc(sigma * smoothingSizeFactor + 0.5)`` (``0x1022c8f4``)."""
    return round_half_up(f32(sigma) * f32(smoothing_size_factor))


def gauss_kernel(sigma: float, smoothing_size_factor: float) -> list[float]:
    """The ``2d+1`` tap kernel built at ``0x1022c940``..``0x1022c96f``.

    ``k[j] = exp(i*i * (-0.5/sigma**2)) * (0.3989423241103187/sigma)`` for
    ``i = -d .. d``.  The vendor evaluates ``exp`` with the x87
    ``fldl2e/f2xm1/fscale`` sequence and stores each tap as float32; the port
    uses ``math.exp`` and rounds at the same point.  Note ``i*i`` is formed in
    **integer** registers (``imul ebx, eax``) and reloaded with ``fild``, so it
    is exact.

    The two scale factors are computed once, before the loop, at register
    precision: ``0.3989423241103187 / sigma`` (``fdivr`` of the qword at
    ``0x1059a858``) and ``-0.5 / (sigma*sigma)`` (``fdivr`` of the qword at
    ``0x1057ae70``, with ``sigma*sigma`` itself rounded to float32 first because
    it comes from ``fld dword; fmul dword``).
    """
    if not CNA_GAUSS_SMOOTH_PORTED:
        _unported("CNA_GAUSS_SMOOTH_PORTED", CNA_GAUSS_SMOOTH, "gauss_kernel")
    s = f32(sigma)
    d = gauss_half_width(s, smoothing_size_factor)
    amp = K_INV_SQRT_2PI / s                       # 0x1022c90e, register-wide
    expk = K_MINUS_HALF / (s * s)                  # 0x1022c931, register-wide
    n = 2 * d + 1
    out: list[float] = []
    for j in range(n):
        i = -d + j
        out.append(f32(math.exp(f32(float(i * i)) * expk) * amp))
    return out


def gauss_smooth(src: Sequence[float], n: int, sigma: float,
                 smoothing_size_factor: float) -> list[float]:
    """``0x1022c8f0`` — convolve ``src[0:n]`` with the gaussian above.

    Edge handling is **clamp**, done by materialising a ``n + 2d`` scratch
    (``results+0x30``, i.e. ``impl+0xb8``): ``d`` copies of ``src[0]``, then
    ``src``, then ``d`` copies of ``src[n-1]``.  ``0x1022c986``/``0x1022c9be``
    write the two pads with ``rep stosd``; ``0x1022c9a3`` copies the body.

    Each output is a straight dot product of the padded window against the
    kernel (``0x1022ca14``, unrolled by four, then a tail at ``0x1022ca47``),
    accumulated **at register precision** and stored once as float32.

    The unrolled body's x87 shuffle looks like it might reassociate — it
    computes ``k1*x1 + (k0*x0 + acc)`` before folding in taps 2 and 3 — but
    ``a + (b + c)`` with ``b + c`` evaluated first is bit-identical to
    ``(c + b) + a`` for IEEE addition, so it reduces to plain left-to-right
    accumulation.  The transcription below keeps the vendor's shape; a naive
    ``sum(k[i]*w[i])`` was checked against it and is bit-identical on every
    case the golden harness runs, so this is documentation, not a subtlety.

    Returns a fresh list; the vendor writes in place when ``in`` and ``out``
    alias, which both call sites do.
    """
    if not CNA_GAUSS_SMOOTH_PORTED:
        _unported("CNA_GAUSS_SMOOTH_PORTED", CNA_GAUSS_SMOOTH, "gauss_smooth")
    d = gauss_half_width(sigma, smoothing_size_factor)
    kern = gauss_kernel(sigma, smoothing_size_factor)
    taps = 2 * d + 1
    pad: list[float] = []
    if n > 0:
        pad = [f32(src[0])] * d + [f32(v) for v in src[:n]] + [f32(src[n - 1])] * d
    else:
        pad = [0.0] * (2 * d)
    out: list[float] = []
    for b in range(n):
        acc = 0.0
        w = pad[b:b + taps]
        i = 0
        # 0x1022ca14: unrolled by four, in the vendor's association order.
        while taps - i >= 4:
            acc = (kern[i + 1] * w[i + 1]) + ((kern[i] * w[i]) + acc)
            acc = acc + (kern[i + 2] * w[i + 2])
            acc = acc + (kern[i + 3] * w[i + 3])
            i += 4
        while i < taps:                              # 0x1022ca47 tail
            acc = acc + (kern[i] * w[i])
            i += 1
        out.append(f32(acc))
    return out


# ---------------------------------------------------------------------------
# 0x1022c3e0 -- peak of the second difference
# ---------------------------------------------------------------------------


def peak_second_difference(f: Sequence[float], start: int, limit: int) -> int:
    """``0x1022c3e0`` — argmax over ``j in [start, limit]`` of the 2-step second
    difference ``f[j-2] + f[j+2] - 2*f[j]``.

    ``eax`` on entry is ``start``, ``ecx`` is the array, the first stack
    argument is ``limit`` and the second is where the index is written.  The
    seed value is the difference **at** ``start`` with ``bestIdx = start``
    (``0x1022c3e1``..``0x1022c3fa``), and the comparison is
    ``fcomp; test ah,0x41; jne keep`` — i.e. a candidate replaces the incumbent
    only when it is **strictly greater** (``0x1022c430``), so ties keep the
    lower index.  The scan runs ``j = start+1 .. limit`` inclusive
    (``cmp edx, ebp; jle`` at ``0x1022c4b4`` and ``cmp edx, eax; jle`` at
    ``0x1022c4f1``).

    Each candidate is stored to a float32 stack slot before the compare
    (``fst dword [esp+0x10]``), so the comparison is between float32 values,
    not register-precision ones.
    """
    if not CNA_PEAK_SEARCH_PORTED:
        _unported("CNA_PEAK_SEARCH_PORTED", CNA_PEAK_SEARCH,
                  "peak_second_difference")

    def d2(j: int) -> float:
        return f32((f32(f[j + 2]) + f32(f[j - 2])) - (f32(f[j]) + f32(f[j])))

    best_idx = start
    best = d2(start)
    j = start + 1
    while j <= limit:
        cur = d2(j)
        if cur > best:
            best = cur
            best_idx = j
        j += 1
    return best_idx


# ---------------------------------------------------------------------------
# 0x1022ca80 -- histogram moments, smooth, resample
# ---------------------------------------------------------------------------


@dataclass
class HistResample:
    """What ``0x1022ca80`` writes back through its two out-pointers."""

    in_sigma: float = 0.0    # *A7 -- results.darkInSigma / .lightInSigma
    out_sigma: float = 0.0   # *A8 -- results.darkOutSigma / .lightOutSigma
    out: list[int] = field(default_factory=list)   # A9, n ints


def hist_resample(params: CnaParams, hist: Sequence[int], n: int, pivot: int,
                  scale: float, max_contrast_gain: float) -> HistResample:
    """``0x1022ca80`` — the shared dark/light half of the tone analysis.

    Called twice from ``0x1022ddc0``: at ``0x1022e434`` with
    ``(darkScale/bucketSize, darkMaxContrastGain, &darkInSigma, &darkOutSigma)``
    and at ``0x1022e669`` with the ``light`` triple.  Ten stack arguments; the
    second is a **float** pushed by the ``push ecx; fstp dword [esp]`` idiom at
    ``0x1022e42b``/``0x1022e430``.

    Steps, in the vendor's order:

    1. ``sum = sum(hist)``, ``S1 = sum(i*hist[i])``, ``S2 = sum(i*i*hist[i])``
       — the products are formed in **integer** registers and reloaded with
       ``fild``, so they are exact up to 32-bit wrap; the two float sums are
       accumulated at register precision (``S1``) and through a float32 memory
       slot (``S2``, ``fstp dword [esp+0x14]`` every step).
    2. ``mean = S1/sum``, ``sigma = sqrt(S2/sum - mean*mean)``  (``0x1022cbb0``)
       written to ``*A7``.
    3. ``outSigma = clamp(sigma*blend, minGaussSigma, maxGaussSigma)``
       (``0x1022cbe6``..``0x1022cc11``).
    4. Normalise ``hist/sum`` into a ``n + 2d`` scratch padded with zeros
       (**not** edge-clamped -- ``0x1022cc40``/``0x1022cc59`` write zeros), then
       ``gauss_smooth`` it and multiply back by ``sum``.
    5. Find the index where the running sum of the smoothed array crosses
       ``sum(hist[0..pivot])/sum`` of its own total (``0x1022cdd2``).
    6. ``outVal = sigma < scale/gain ? sigma*gain : scale`` -> ``*A8``;
       ``step = sigma/outVal * sqrt((outSigma**2 + sigma**2)/sigma**2)``;
       resample ``out[k] = trunc(step * padded[clamp(trunc(base + (k+1)*step +
       0.5))] + 0.5)`` (``0x1022ce60``).
    """
    if not CNA_HIST_RESAMPLE_PORTED:
        _unported("CNA_HIST_RESAMPLE_PORTED", CNA_HIST_RESAMPLE,
                  "hist_resample")
    res = HistResample()

    # -- 1. moments -------------------------------------------------------
    # The vendor's loop is software-pipelined and unrolled by four
    # (0x1022cab6..0x1022cb6d), and the two float accumulators do NOT stay in
    # registers: each one is spilled to a float32 stack slot twice per group of
    # four.  That rounding is observable in the last bits of `sigma`, so the
    # spill points are reproduced exactly rather than summed in one pass.
    #
    #   A (sum of i*hist[i]) : reg += i0 ; f32-spill += i1 ; f32-spill += i2 ;
    #                          reg += i3        (0x1022cac8/cb02/cb26/cb54)
    #   B (sum of i*i*hist)  : reg += i0 ; reg += i1 ; f32-spill += i2 ;
    #                          f32-spill += i3  (0x1022cadc/cb00/cb32/cb65)
    #
    # The integer products themselves are formed with 32-bit `imul` and
    # reloaded with `fild`, so they are exact modulo 2**32.
    total = 0
    acc_a = 0.0             # st0 at the loop head
    acc_b = 0.0             # the float32 slot [esp+0x14]
    i = 0
    while n - i >= 4:
        x0, x1, x2, x3 = (hist[i], hist[i + 1], hist[i + 2], hist[i + 3])
        total = i32(total + x0 + x1 + x2 + x3)
        acc_a = acc_a + float(i32(x0 * i))
        acc_b = acc_b + float(i32(i32(x0 * i) * i))
        acc_b = acc_b + float(i32(i32(x1 * (i + 1)) * (i + 1)))
        acc_a = f32(float(i32(x1 * (i + 1))) + acc_a)
        acc_a = f32(float(i32(x2 * (i + 2))) + acc_a)
        acc_b = f32(float(i32(i32(x2 * (i + 2)) * (i + 2))) + acc_b)
        acc_a = float(i32(x3 * (i + 3))) + acc_a
        acc_b = f32(float(i32(i32(x3 * (i + 3)) * (i + 3))) + acc_b)
        i += 4
    while i < n:                                       # 0x1022cb80 tail
        x = hist[i]
        total = i32(total + x)
        acc_a = acc_a + float(i32(x * i))
        acc_b = f32(float(i32(i32(x * i) * i)) + acc_b)
        i += 1

    # -- 2. mean / sigma (0x1022cbb0) -------------------------------------
    # `fst dword [esp+0x18]` stores 1/sum as float32 but does not pop, so the
    # mean is formed with the **register** reciprocal and the second moment
    # with the **float32** one.  sigma likewise stays at register precision in
    # st0 -- only the copy written through A7 is rounded.
    fsum = f32(float(total))
    inv_reg = K_ONE_F32 / fsum
    inv_f32 = f32(inv_reg)
    mean = acc_a * inv_reg
    m2 = inv_f32 * acc_b
    var = m2 - mean * mean
    sigma = math.sqrt(var) if var >= 0.0 else float("nan")
    res.in_sigma = f32(sigma)

    # -- 3. outSigma (0x1022cbe6) -----------------------------------------
    # The low clamp compares the register value; the high clamp compares the
    # float32 spill.  Both write the float32 slot, which is what the gaussian
    # and the ratio below then read.
    blended = sigma * params.blend
    out_sigma = f32(blended)
    if not (blended >= params.minGaussSigma):
        out_sigma = params.minGaussSigma
    elif out_sigma > params.maxGaussSigma:
        out_sigma = params.maxGaussSigma

    # -- 4. normalise into a ZERO-padded scratch, smooth, rescale ---------
    # 0x1022cc40 / 0x1022cc59 write zeros into the two pads.  Note this is a
    # different edge policy from gauss_smooth's own internal padding, which
    # clamps -- the zeros here are the caller's, and they are what makes the
    # smoothed tails decay instead of plateauing.
    d = gauss_half_width(out_sigma, params.smoothingSizeFactor)
    npad = n + 2 * d
    padded = [0.0] * npad
    for i in range(n):
        padded[d + i] = f32(float(hist[i]) / fsum)
    padded = gauss_smooth(padded, npad, out_sigma, params.smoothingSizeFactor)
    padded = [f32(v * fsum) for v in padded]

    # -- 5. crossing index (0x1022cd6b) -----------------------------------
    below = 0
    if pivot >= 0:
        for i in range(pivot + 1):
            below = i32(below + hist[i])
    frac = float(below) / fsum
    acc = 0.0
    for v in padded:
        acc = acc + v
    target = frac * acc
    #: When the walk never crosses, ``[esp+0x2c]`` keeps the ``AnsCnaResults``
    #: pointer the slot held on entry and ``fild`` reads *that* as the index --
    #: a genuine vendor quirk with no sane value.  It cannot happen for a
    #: non-negative histogram with ``frac <= 1``; the port raises rather than
    #: inventing an answer.
    cross = None
    for k, v in enumerate(padded):
        target = target - v
        if not (target > 0.0):
            cross = k
            break
    if cross is None:
        raise RuntimeError(
            f"{CNA_HIST_RESAMPLE:#x}: running sum never crossed "
            f"{frac!r}*total; the vendor would read the AnsCnaResults pointer "
            "out of [esp+0x2c] as the index here")

    # -- 6. resample (0x1022cdef) -----------------------------------------
    # 0x1022cdf5..0x1022ce07 is a raw `fdivrp`/`fsqrt` with no zero-guard
    # anywhere in the disassembly, and 0x1022ce33..0x1022ce3d (the `step`
    # divide two lines down) is likewise a raw `fdiv st(1)` -- both confirmed
    # by direct disassembly, not inferred. `sig32` (== `res.in_sigma`) is
    # exactly the same class of "can legitimately be 0.0, or already NaN from
    # a negative-variance histogram" value the module docstring's `_x87_div`
    # was written for; unlike the `src[i]`/`den[i]` normalisation that
    # originally motivated it, neither divide here was wrapped, so a
    # `sig32 == 0.0` histogram (a real, reachable degenerate shape -- e.g. a
    # bucket histogram whose float32-rounded second moment lands exactly on
    # `mean**2`) raised Python's `ZeroDivisionError` instead of the real
    # DLL's masked-exception infinity/NaN. `math.sqrt` is safe here without
    # extra guarding: `ratio` is a sum of squares over a sum of squares, so it
    # is never negative -- only 0, positive, +inf or NaN -- and
    # `math.sqrt(nan)`/`math.sqrt(inf)` both return the input unchanged.
    sig32 = res.in_sigma                       # fld dword [ecx] -- reloaded
    ratio = _x87_div((out_sigma * out_sigma) + (sig32 * sig32),
                     sig32 * sig32)
    root = math.sqrt(ratio)
    if sig32 < f32(scale) / f32(max_contrast_gain):
        out_val = sig32 * f32(max_contrast_gain)     # register precision
    else:
        out_val = f32(scale)
    res.out_sigma = f32(out_val)
    step = f32(_x87_div(sig32, out_val) * root)       # fstp dword [esp+0x30]
    cur = float(cross) - float(pivot + 1) * step
    for _ in range(n):
        cur = cur + step
        k = round_half_up(cur)
        if k < 0:
            k = 0
        elif k >= npad:
            k = npad - 1
        # 0x1022ce98: `mov dword [edx+esi*4], eax` -- only the LOW 32 bits of
        # _ftol2's 64-bit edx:eax result are ever stored here; edx is loaded
        # (as the output pointer) but never combined with the truncation's own
        # edx half, which is silently discarded. Every call site in this
        # function that consumes an _ftol2 result (this store, and the `k`
        # clamp two lines up) reads EAX alone -- confirmed by direct
        # disassembly of 0x1022ce60..0x1022ce9e, not inferred. For ordinary
        # in-range values this narrowing is a no-op (`i32(v) == v`), which is
        # why it went unnoticed against every prior golden/assembled case: it
        # only diverges when the *value being truncated* itself doesn't fit in
        # 32 bits.
        #
        # That happens for real: a real scanned roll's dark-half histogram
        # legitimately drove `sigma`'s variance negative (`m2 - mean*mean` <
        # 0, a genuine x87 rounding outcome, not a port bug), producing
        # `in_sigma = NaN` -- live-Unicorn-confirmed against the real DLL with
        # the exact real histogram (`sqrt` of a masked-invalid negative
        # operand is the x87 "real indefinite" QNaN under FPCW 0x027f, same
        # class as `_x87_div`'s zero-divide case above). NaN then propagates
        # through `step`, so every `_ftol2` call in this loop hits the masked-
        # invalid-operation path and returns the 64-bit "integer indefinite"
        # pattern 0x8000000000000000 -- LOW 32 bits zero. Storing the full
        # (unbounded) Python int here instead of its low 32 bits turned that
        # into -2**63 per entry, which is what made every downstream
        # cumulative-sum crossing search in `analyze_image._half` diverge
        # without bound instead of landing on 0 immediately, the real DLL's
        # own behaviour (live-verified: real `out` comes back all zeros for
        # this exact real histogram, and the i32-truncated port matches it
        # exactly, 0/500 mismatches). See `pakon_cna_golden.py`'s
        # `resample_cases` list (section 6, "near-spike n=500 (NaN sigma)")
        # for the synthetic regression case built from this real histogram's
        # shape (values, not the frame itself).
        res.out.append(i32(round_half_up(step * padded[k])))
    return res


# ---------------------------------------------------------------------------
# 0x1022d970 -- allocateMemory (sizes only)
# ---------------------------------------------------------------------------


def buffer_sizes(p: CnaParams, n_pixels: int) -> dict[str, int]:
    """``0x1022d970`` — the element counts of all 15 working buffers.

    Two half-widths are pre-computed from the params: ``hw1`` from
    ``maxGaussSigma`` alone (``0x1022d99e``) and ``hw2`` from the largest of
    ``laplacianHistSmoothingSigma``, ``coarseHistSmoothingSigma``,
    ``toneScaleSmoothingSigma`` and ``maxGaussSigma`` (``0x1022da3b``..
    ``0x1022da7d``).  Both are ``trunc(sigma*smoothingSizeFactor + 0.5)``.

    Sizes are returned in **elements**, with the element type in the key's
    suffix, rather than the vendor's byte counts.
    """
    if not CNA_ALLOCATE_MEMORY_PORTED:
        _unported("CNA_ALLOCATE_MEMORY_PORTED", CNA_ALLOCATE_MEMORY,
                  "allocateMemory")
    n_bins = p.histSize
    n_buckets = idiv(n_bins, p.bucketSize)
    hw1 = round_half_up(f32(p.maxGaussSigma) * f32(p.smoothingSizeFactor))
    m = max(p.laplacianHistSmoothingSigma, p.coarseHistSmoothingSigma)
    if m < p.toneScaleSmoothingSigma:
        m = p.toneScaleSmoothingSigma
    if m < p.maxGaussSigma:
        m = p.maxGaussSigma
    hw2 = round_half_up(f32(m) * f32(p.smoothingSizeFactor))
    padded = n_bins + 2 * hw1
    return {
        "lum_i16": n_pixels,            # +0x8c
        "lum_hist_i32": n_bins,         # +0x90
        "lap_i16": n_pixels,            # +0x94
        "edge_hist_i32": n_bins,        # +0xa4
        "gauss_pad_f32": 2 * hw2 + padded,   # +0xb8
        "gauss_kern_f32": 2 * hw2 + 1,       # +0xbc
        "resample_f32": padded,         # +0xc0
        "scratch_c4_i32": n_bins,       # +0xc4
        "bucket_hist_i32": n_buckets,   # +0xc8
        "scratch_cc_f32": n_bins,       # +0xcc
        "scratch_d0_f32": n_bins,       # +0xd0
        "scratch_d4_f32": n_bins,       # +0xd4
        "scratch_d8_f32": n_bins,       # +0xd8
        "tone_lut_i16": n_bins,         # +0xdc
        "_hw1": hw1,
        "_hw2": hw2,
    }


# ---------------------------------------------------------------------------
# 0x1022ddc0 -- the first half of analyzeImage
# ---------------------------------------------------------------------------


@dataclass
class ThresholdStage:
    """Everything ``0x1022ddc0`` has decided by ``0x1022e23e``."""

    n_pixels: int = 0
    lum: list[int] = field(default_factory=list)
    lum_hist: list[int] = field(default_factory=list)
    lap: list[int] = field(default_factory=list)
    lap_hist: list[int] = field(default_factory=list)
    half: int = 0
    peak_index: int = 0
    #: ``results.threshold`` (``impl+0x98``) — the threshold of the last pass
    #: that actually ran, published at ``0x1022e1e6``.
    threshold: int = 0
    #: The value ``ebx`` was reduced to after the last pass.  The vendor keeps
    #: it in a register and never publishes it; it is exposed here only because
    #: it is what ``minPosThreshold`` is compared against.
    reduced_threshold: int | None = None
    min_lap_pixels: int = 0
    edge_hist: list[int] = field(default_factory=list)
    n_edge: int = 0
    #: True when the relaxation loop ran out of threshold and ``0x1022e21c``
    #: wrote the identity LUT and returned OK.
    gave_up: bool = False
    tone_lut: list[int] = field(default_factory=list)


def luminance_plane(img: CnaImage, p: CnaParams) -> list[int]:
    """``0x1022deb5``/``0x1022df0f`` — the per-pixel luminance.

    ``lum = (R + G + B + 1 + redShift + greenShift + blueShift) / 3``, with the
    division being x86 signed ``/3`` (``imul 0x55555556``, truncate toward
    zero).  The ``+1`` is a literal ``inc eax`` on the red term, not a rounding
    of the mean.

    There are **two** copies of this loop and they are not equivalent: when the
    three shifts sum to zero (``test ebp,ebp`` at ``0x1022dea3``) the result is
    stored raw as int16; otherwise it is first clamped to ``[0, 0xfff]``
    (``0x1022deea``..``0x1022def7``).  The port keeps both, because the
    unclamped branch is what lets an out-of-range value reach the histogram
    index at ``0x1022df80`` — an unchecked ``inc dword [edi + eax*4]``.
    """
    shift = p.redShift + p.greenShift + p.blueShift
    px = img.pixels
    n = img.width * img.height
    out: list[int] = []
    if shift != 0:
        for i in range(n):
            s = px[3 * i] + 1 + px[3 * i + 1] + px[3 * i + 2] + shift
            v = idiv(s, 3)
            if v < 0:
                v = 0
            elif v > K_LUT_MAX:
                v = K_LUT_MAX
            out.append(i16(v))
    else:
        for i in range(n):
            s = px[3 * i] + 1 + px[3 * i + 1] + px[3 * i + 2]
            out.append(i16(idiv(s, 3)))
    return out


def _interior_indices(width: int, height: int):
    """The ``(height-2) x (width-2)`` walk both histogram loops perform."""
    if height <= 2 or width <= 2:
        return
    for r in range(1, height - 1):
        for c in range(1, width - 1):
            yield r * width + c


def analyze_image_threshold(img: CnaImage, p: CnaParams) -> ThresholdStage:
    """``0x1022ddc0`` from entry to ``0x1022e23e`` — the threshold search.

    This is everything cna does before it splits into its dark and light
    halves, and it is the part that decides whether the frame gets a real tone
    scale at all: if the relaxation loop drives ``threshold`` below
    ``minPosThreshold`` the function writes an **identity** ToneScaleLut
    (``ToneScaleLut[i] = i``, ``0x1022e230``) and returns OK, which is the
    subsystem's own "this frame has no usable edge structure" answer.

    Order of operations:

    1. ``results.nPixels = width*height`` (``0x1022dddc``).
    2. luminance plane (``luminance_plane``).
    3. luminance histogram over the interior only (``0x1022df80``), indexed by
       the raw luminance with **no bounds check**.
    4. laplacian over the interior (``0x1022c340``).
    5. laplacian histogram, centred on ``half = histSize/2`` and windowed to
       ``[-half, histSize-half-1]`` (``0x1022e010``).
    6. int->float, gaussian smooth with ``laplacianHistSmoothingSigma``, then
       ``peak_second_difference`` over ``[half+1, histSize-3]``
       (``0x1022e0d1``/``0x1022e0e4``).
    7. ``threshold = trunc((peak-half) * thresholdMultiplier + 0.5)`` and
       ``minLapPixels = trunc(nLapPixels * minLapPixelRatio + 0.5)``.
    8. Relaxation loop (``0x1022e130``): count edge pixels whose laplacian is
       outside ``[-threshold, threshold]``, histogram their luminance; if the
       count is below ``minLapPixels``, shrink the threshold by
       ``thresholdReductionFactor`` (through an **int16** narrowing at
       ``0x1022e200``, and forced strictly down at ``0x1022e20b``) and retry.
    """
    if not CNA_ANALYZE_IMAGE_THRESHOLD_PORTED:
        _unported("CNA_ANALYZE_IMAGE_THRESHOLD_PORTED", CNA_ANALYZE_IMAGE,
                  "analyzeImage (threshold stage)")
    st = ThresholdStage()
    w, h = img.width, img.height
    n_bins = p.histSize
    st.n_pixels = w * h

    st.lum = luminance_plane(img, p)

    st.lum_hist = [0] * n_bins
    for k in _interior_indices(w, h):
        st.lum_hist[st.lum[k]] = i32(st.lum_hist[st.lum[k]] + 1)

    st.lap = laplacian(st.lum, w, h)
    n_lap = len(st.lap)

    half = idiv(n_bins, 2)
    st.half = half
    st.lap_hist = [0] * n_bins
    lo, hi = i16(-half), i16(n_bins - half - 1)
    for v in st.lap:
        if lo <= v <= hi:
            st.lap_hist[half + v] = i32(st.lap_hist[half + v] + 1)

    smoothed = gauss_smooth([float(v) for v in st.lap_hist], n_bins,
                            p.laplacianHistSmoothingSigma,
                            p.smoothingSizeFactor)
    st.peak_index = peak_second_difference(smoothed, half + 1, n_bins - 3)

    threshold = round_half_up(f32(float(st.peak_index - half))
                              * f32(p.thresholdMultiplier))
    st.min_lap_pixels = round_half_up(f32(float(n_lap))
                                      * f32(p.minLapPixelRatio))

    while True:
        st.edge_hist = [0] * n_bins
        k = 0
        for idx in _interior_indices(w, h):
            v = st.lap[k]
            k += 1
            if v > threshold or v < -threshold:
                j = st.lum[idx]
                st.edge_hist[j] = i32(st.edge_hist[j] + 1)
        n_edge = 0
        for v in st.edge_hist:
            n_edge = i32(n_edge + v)
        st.n_edge = n_edge
        # 0x1022e1e0 / 0x1022e1e6 publish nEdgePixels and threshold for the
        # pass that just ran, BEFORE the sufficiency test -- so on the bail-out
        # path ``results.threshold`` keeps the last *tried* value, not the
        # reduced one that failed ``minPosThreshold``.  Writing the reduced
        # value here is an off-by-one the golden harness catches.
        st.threshold = threshold
        if n_edge >= st.min_lap_pixels:
            return st
        nxt = i16(round_half_up(f32(float(threshold))
                                * f32(p.thresholdReductionFactor)))
        threshold = nxt if nxt < threshold else threshold - 1
        st.reduced_threshold = threshold
        if threshold < p.minPosThreshold:
            st.gave_up = True
            st.tone_lut = [i16(i) for i in range(n_bins)]
            return st


# ---------------------------------------------------------------------------
# 0x1022e865 .. 0x1022e9b0 -- elmo detection (cna's half of the shell's fork)
# ---------------------------------------------------------------------------


@dataclass
class ElmoResult:
    """``AnsCnaResults+0x58`` / ``+0x5c`` — what the shell reads at ``0x100fc084``."""

    elmo_percent: float = -1.0
    b_elmo_occured: bool = False
    #: Number of pixels that tripped the saturation test.  Internal; the vendor
    #: keeps it in the ``[esp+0x78]`` argument slot and never publishes it.
    count: int = 0
    #: False when one of the two gates declined to run the count at all, in
    #: which case ``elmoPercent`` stays at its ``-1.0f`` seed.
    ran: bool = False


def elmo_detect(p: CnaParams, img: CnaImage, light_in_sigma: float,
                light_out_sigma: float) -> ElmoResult:
    """``0x1022e865``..``0x1022e9a9`` — the ELMO ("electronic flash") test.

    This is **cna's half** of the fork ``analyzeAutoTone`` takes at
    ``0x100fc5cd``: cna decides ``bElmoOccured``, and the shell then chooses
    between ``elmoAggressiveness`` (with the ``3 <= ctx+0x44 <= 6 -> 0`` scene
    reset) and ``toneHelperResults[+0xb4]`` on the strength of it.  The shell's
    half is already ported in ``pakon_autotone``; only the decision is here.

    Two gates, both of which leave ``elmoPercent`` at its ``-1.0f`` seed and
    ``bElmoOccured`` at 0 when they decline (``0x1022e874``/``0x1022e87e`` write
    the seeds *before* either gate is evaluated):

    * ``lightInSigma > lightOutSigma`` (``0x1022e865``, ``jne`` on ``C3|C0``,
      i.e. skip when ``<=``).  This is the "the light half of the histogram had
      to be compressed" condition -- ``lightOutSigma`` is the clamped target
      sigma ``hist_resample`` produced, so the test fires only when the frame's
      own highlight spread exceeded what the contrast gain allows.
    * ``elmoCriticalPercent < 100.0f`` (``0x1022e890``), a disable switch: the
      shipped DPI value is 5.0, so it is live.

    The count itself walks **every** pixel (not the interior the histograms
    use).  Per pixel, with the raw int16 R, G, B:

        lum = (R + G + B + 1) / 3           -- the same /3 as luminance_plane
        u   = (2*G + 2 - R - B) / 4         -- signed, truncating
        v   = (B - R + 1) / 2               -- signed, truncating

    and the pixel counts when **all** of:

    * at least one of ``R > elmoRedLimit``, ``G > elmoGreenLimit``,
      ``B > elmoBlueLimit`` -- compared as **16-bit** signed values
      (``cmp word``, ``0x1022e93b``);
    * ``lum < elmoNeutralLimit``, also a 16-bit compare (``cmp bp, word``);
    * ``u*u + v*v > elmoSatThreshold**2``, with ``u`` and ``v`` first narrowed
      to int16 (``movsx``, ``0x1022e95e``/``0x1022e963``).

    Finally ``elmoPercent = count * 100.0f / nPixels`` (an ``fidiv`` by the
    integer pixel count) and ``bElmoOccured = elmoPercent > elmoCriticalPercent``
    -- **strictly** greater; ``0x1022e9a4``'s ``test ah,0x41; jne`` skips the
    store on equal as well as less.
    """
    if not CNA_ELMO_PORTED:
        _unported("CNA_ELMO_PORTED", CNA_ANALYZE_IMAGE, "elmo_detect")
    r = ElmoResult(elmo_percent=-1.0, b_elmo_occured=False)
    if not (light_in_sigma > light_out_sigma):        # 0x1022e88a
        return r
    if not (p.elmoCriticalPercent < K_HUNDRED_F32):   # 0x1022e8a1
        return r
    r.ran = True
    sat2 = i32(p.elmoSatThreshold * p.elmoSatThreshold)
    n = img.width * img.height
    px = img.pixels
    count = 0
    for i in range(n):
        red, grn, blu = px[3 * i], px[3 * i + 1], px[3 * i + 2]
        lum = idiv(red + grn + blu + 1, 3)
        # 0x1022e91d/0x1022e923 and 0x1022e932/0x1022e939 are the compiler's
        # `cdq; and edx,3; add; sar 2` and `cdq; sub; sar 1` idioms -- signed
        # division truncating toward zero, not an arithmetic shift.
        u = idiv(2 * grn + 2 - red - blu, 4)
        v = idiv(blu - red + 1, 2)
        if not (i16(red) > p.elmoRedLimit
                or i16(grn) > p.elmoGreenLimit
                or i16(blu) > p.elmoBlueLimit):
            continue
        if i16(lum) >= p.elmoNeutralLimit:
            continue
        if i32(i16(u) * i16(u)) + i32(i16(v) * i16(v)) > sat2:
            count += 1
    r.count = count
    r.elmo_percent = f32(float(count) * K_HUNDRED_F32 / float(n))
    r.b_elmo_occured = r.elmo_percent > p.elmoCriticalPercent
    return r


# ---------------------------------------------------------------------------
# the pieces that are NOT ported
# ---------------------------------------------------------------------------


def _contrast_map(params: CnaParams, src: Sequence[float],
                  ratio_den: Sequence[float], out: list[float],
                  pivot: int, idx: int, limit: int, *, ascending: bool) -> None:
    """``0x1022c630`` (ascending) and ``0x1022c520`` (descending), in place.

    The two are the same routine mirrored, so they are one function here with
    the differences parameterised.  Both walk away from ``pivot`` one bucket at
    a time, carrying a float accumulator that starts at ``idx`` and moves by a
    **clamped local ratio** each step; the accumulator, rounded, is the source
    bucket that bucket ``i`` maps from.

    Per step (``0x1022c575`` / ``0x1022c687``):

    1. clamp the running ratio to ``[params.lowClamp, params.highClamp]`` --
       the two floats ``AnsCnaParams+0x10``/``+0x14`` the vendor dumper leaves
       unnamed, 0.5 and 1.5 in the shipped DPI.  The low compare tests the
       **register** value; on either clamp the running value becomes the
       float32 parameter.
    2. ``acc -= ratio`` descending / ``acc += ratio`` ascending, stored through
       a float32 slot (``0x1022c59f`` / ``0x1022c6b1``).
    3. ``k = clamp(trunc(acc + 0.5), 0, limit-1)``.
    4. ``out[i] = clamp(k - (idx - pivot), 0, limit-1)``, stored as a float.
    5. next ratio = ``ratio_den[k] == 0 ? 1.0f : src[i] / ratio_den[k]``.  The
       zero test is an ``fucompp`` against the **qword** 0.0 at ``0x10573c40``
       (``0x1022c5f8``), so it catches -0.0 as well.

    ``out[pivot]`` is seeded with ``(float)pivot`` before either walk
    (``0x1022c539`` / ``0x1022c648``) -- that is what joins the two halves.
    """
    if not CNA_CONTRAST_MAP_PORTED:
        _unported("CNA_CONTRAST_MAP_PORTED",
                  CNA_MAP_UP if ascending else CNA_MAP_DOWN, "contrast map")
    out[pivot] = f32(float(pivot))
    den = ratio_den[idx]
    ratio = f32(src[pivot]) / f32(den)          # register precision
    acc = f32(float(idx))
    delta = idx - pivot
    lo, hi = params.lowClamp, params.highClamp
    order = range(pivot + 1, limit) if ascending else range(pivot - 1, -1, -1)
    for i in order:
        if not (ratio >= lo):                   # 0x1022c57b / 0x1022c68d
            ratio = lo
        elif ratio > hi:
            ratio = hi
        acc = f32(acc + ratio) if ascending else f32(acc - ratio)
        k = round_half_up(acc)
        if k < 0:
            k = 0
        elif k >= limit:
            k = limit - 1
        j = k - delta
        if j < 0:
            j = 0
        elif j >= limit:
            j = limit - 1
        out[i] = f32(float(j))
        den = ratio_den[k]
        ratio = K_ONE_F32 if den == 0.0 else f32(src[i]) / f32(den)


def contrast_map_down(params, src, ratio_den, out, pivot, idx, limit) -> None:
    """``0x1022c520`` — ``pivot-1`` down to 0, accumulator decreasing."""
    _contrast_map(params, src, ratio_den, out, pivot, idx, limit,
                  ascending=False)


def contrast_map_up(params, src, ratio_den, out, pivot, idx, limit) -> None:
    """``0x1022c630`` — ``pivot+1`` up to ``limit-1``, accumulator increasing."""
    _contrast_map(params, src, ratio_den, out, pivot, idx, limit,
                  ascending=True)


#: ``0x1059f880`` — the value the high tail refuses to extrapolate past.
K_TONE_MAX_F32 = 4095.0


def build_tone_lut(curve: Sequence[float], n_buckets: int,
                   n_bins: int) -> list[int]:
    """``0x1022c740`` — expand a per-bucket curve into a per-bin int16 LUT.

    ``step = n_bins / n_buckets`` bins per bucket.  The body writes the
    ``n_buckets - 1`` interior buckets starting at bin ``step/2``
    (``0x1022c75d``), leaving half a bucket unwritten at each end for the tails
    to fill.  Within a bucket the accumulator starts at ``curve[j] * step`` and
    advances by ``curve[j+1] - curve[j]`` per bin -- **not** by that difference
    scaled to bins, which is what a linear interpolation would do.  That
    asymmetry is the vendor's; it is reproduced verbatim and the golden harness
    pins it.

    The two tails extrapolate rather than clamp:

    * **low** (``0x1022c7e2``): slope ``lut[h+2] - lut[h+1]`` with
      ``h = step/2 - 1``, walked down from ``lut[h+1]``, writing each value
      until one goes **negative**; everything below that is zeroed
      (``0x1022c880``).
    * **high** (``0x1022c838``): slope ``lut[e-1] - lut[e-2]`` with
      ``e = n_bins - (step+1)/2``, walked up from ``lut[e-1]``, writing until a
      value exceeds ``4095.0f`` (``0x1059f880``); the remainder is filled with
      ``0x0fff`` by a ``rep stosd`` of ``0x0fff0fff`` (``0x1022c8d2``).

    Every store is ``mov word``, so an out-of-range value wraps rather than
    saturating; the ``0x0fff`` fill is the only clamp in the function.
    """
    if not CNA_TONE_LUT_BUILD_PORTED:
        _unported("CNA_TONE_LUT_BUILD_PORTED", CNA_TONE_LUT_BUILD,
                  "build_tone_lut")
    lut = [0] * n_bins
    step = idiv(n_bins, n_buckets)
    half = idiv(step, 2)
    pos = half
    for j in range(n_buckets - 1):               # 0x1022c774 .. 0x1022c7da
        delta = f32(f32(curve[j + 1]) - f32(curve[j]))
        acc = f32(curve[j]) * float(step)        # register precision
        lut[pos] = i16(round_half_up(acc))
        pos += 1
        if step > 1:
            for _ in range(step - 1):            # 0x1022c7b0
                acc = acc + delta
                lut[pos] = i16(round_half_up(acc))
                pos += 1

    # -- low tail (0x1022c7e2) --------------------------------------------
    i = half - 1
    slope = f32(float(lut[i + 2]) - float(lut[i + 1]))
    acc = float(lut[i + 1])
    while i >= 0:
        acc = acc - slope
        if acc < 0.0:                            # 0x1022c81c, jnp on C0
            while i >= 0:                        # 0x1022c880 zero-fill
                lut[i] = 0
                i -= 1
            break
        lut[i] = i16(round_half_up(acc))
        i -= 1

    # -- high tail (0x1022c838) -------------------------------------------
    e = n_bins - idiv(step + 1, 2)
    slope = f32(float(lut[e - 1]) - float(lut[e - 2]))
    acc = float(lut[e - 1])
    i = e
    while i < n_bins:
        acc = acc + slope
        if acc > K_TONE_MAX_F32:                 # 0x1022c894
            for k in range(i, n_bins):           # 0x1022c8d2 rep stosd 0xfff
                lut[k] = K_LUT_MAX
            break
        lut[i] = i16(round_half_up(acc))
        i += 1
    return lut


@dataclass
class CnaAnalysis:
    """Everything ``0x1022ddc0`` leaves in ``AnsCnaResults``, plus its workings."""

    threshold_stage: ThresholdStage | None = None
    pivot: int = 0                 # possibly re-derived from the percentiles
    pivot_bucket: int = 0
    n_buckets: int = 0
    percentile: float = 0.0        # the [E-0x50] slot both halves reuse
    bucket_hist: list[int] = field(default_factory=list)
    dark: HistResample | None = None
    light: HistResample | None = None
    cross_dark: int = 0
    cross_light: int = 0
    curve: list[float] = field(default_factory=list)
    elmo: ElmoResult | None = None
    tone_lut: list[int] = field(default_factory=list)
    n_pixels: int = 0
    n_edge: int = 0
    threshold: int = 0


def analyze_image(img: CnaImage, p: CnaParams) -> CnaAnalysis:
    """``0x1022ddc0`` — ``AnsCnaCapabilityImpl``'s whole per-frame analysis.

    Entry to ``0x1022e23e`` is ``analyze_image_threshold``.  From there:

    1. **Pivot percentile** (``0x1022e23e``).  ``pivot`` starts at
       ``params.pivot``.  If the fraction of edge pixels below it falls outside
       ``[minPivotPercentile, maxPivotPercentile]``, the pivot is re-derived as
       the bin where the cumulative edge histogram first reaches the violated
       bound.  The bound that was used stays in a stack slot and is reused
       twice later, so it is returned as ``percentile``.
       **The original ``params.pivot`` is kept in a separate slot** (``E-0x04``,
       written once at ``0x1022e24f``) and is what step 8 normalises against --
       the re-derived pivot is used only for the bucketing.
    2. **Bucketing** (``0x1022e2e8``): ``nBuckets = histSize / bucketSize``
       sums of ``bucketSize`` consecutive edge-histogram bins, a gaussian
       smooth with ``coarseHistSmoothingSigma``, and a round back to int.
    3. **Dark half** (``0x1022e402``): ``hist_resample`` with
       ``darkScale/bucketSize`` and ``darkMaxContrastGain``, writing
       ``darkInSigma`` / ``darkOutSigma``.
    4. Normalise both the bucket histogram and the resampled array, find where
       the resampled cumulative crosses ``percentile``, and run
       ``contrast_map_down`` from the pivot bucket to 0.
    5. **Light half** (``0x1022e634``): the same with the ``light`` triple, then
       ``contrast_map_up`` from the pivot bucket upwards.
    6. **Elmo** (``0x1022e865``), gated on ``lightInSigma > lightOutSigma``.
    7. Smooth the joined curve with ``toneScaleSmoothingSigma`` and expand it
       to a per-bin int16 LUT (``build_tone_lut``).
    8. **Normalise** (``0x1022e9e3``): shift the whole LUT by
       ``params.pivot - lut[params.pivot]`` and clamp to ``[0, 0xfff]``, so the
       tone scale is the identity at the pivot density.

    When the threshold loop bails out none of this runs: ``0x1022e21c`` writes
    the identity LUT and jumps to the return, so ``elmoPercent`` and
    ``bElmoOccured`` keep their ``-1.0f`` / 0 seeds and the four sigmas keep
    theirs.
    """
    if not CNA_ANALYZE_IMAGE_PORTED:
        _unported("CNA_ANALYZE_IMAGE_PORTED", CNA_ANALYZE_IMAGE, "analyzeImage")
    a = CnaAnalysis()
    st = analyze_image_threshold(img, p)
    a.threshold_stage = st
    a.n_pixels = st.n_pixels
    a.n_edge = st.n_edge
    a.threshold = st.threshold
    n_bins = p.histSize
    if st.gave_up:
        a.tone_lut = list(st.tone_lut)
        a.elmo = ElmoResult(elmo_percent=-1.0, b_elmo_occured=False)
        return a

    # -- 1. pivot percentile (0x1022e23e) ---------------------------------
    pivot_orig = p.pivot
    pivot = pivot_orig
    below = 0
    if pivot_orig >= 0:
        for i in range(pivot_orig + 1):
            below = i32(below + st.edge_hist[i])
    n_edge_f = float(st.n_edge)
    pct = f32(float(below) / n_edge_f)
    if not (pct >= p.minPivotPercentile) or not (pct <= p.maxPivotPercentile):
        pct = (p.minPivotPercentile if not (pct >= p.minPivotPercentile)
               else p.maxPivotPercentile)
        want = round_half_up(n_edge_f * pct)
        c = 0
        for i in range(n_bins):
            want -= st.edge_hist[i]
            if want <= 0:
                pivot = c
                break
            c += 1
    a.pivot = pivot
    a.percentile = pct

    # -- 2. bucketing (0x1022e2e8) ----------------------------------------
    n_buckets = idiv(n_bins, p.bucketSize)
    a.n_buckets = n_buckets
    bucket = [0] * n_buckets
    k = 0
    for j in range(n_buckets):
        s = 0
        for _ in range(max(p.bucketSize, 0)):
            s = i32(s + st.edge_hist[k])
            k += 1
        bucket[j] = s
    pivot_bucket = idiv(pivot, p.bucketSize)
    a.pivot_bucket = pivot_bucket
    sm = gauss_smooth([float(v) for v in bucket], n_buckets,
                      p.coarseHistSmoothingSigma, p.smoothingSizeFactor)
    bucket = [round_half_up(v) for v in sm]
    a.bucket_hist = list(bucket)

    curve = [0.0] * n_buckets
    src = [0.0] * n_buckets
    den = [0.0] * n_buckets

    def _half(scale_num: float, gain: float):
        """One of the two symmetric halves (``0x1022e402`` / ``0x1022e634``)."""
        r = hist_resample(p, bucket, n_buckets, pivot_bucket,
                          f32(f32(scale_num) / float(p.bucketSize)), gain)
        tot = 0
        for v in r.out:
            tot = i32(tot + v)
        ftot = f32(float(tot))
        want = round_half_up(float(tot) * pct)
        cross = None
        for i in range(n_bins):
            if i >= n_buckets:
                # 0x1022e473 loads this loop's real bound from [esp+0x14],
                # which 0x1022de0c proves (live-disassembly-confirmed, not
                # inferred) is `params.histSize` itself (n_bins), reused from
                # the same register the function's very first idiv used to
                # derive n_buckets -- so the vendor genuinely does walk past
                # bucket n_buckets into memory this port has no buffer for
                # (whatever real allocation sits after `bucket_hist_i32` in
                # the Impl's layout). That part of the original comment here
                # was correct.
                #
                # What was NOT correct: the belief that this "cannot happen
                # for a non-degenerate histogram". A real scanned roll's
                # dark-half histogram reliably drives `hist_resample`'s
                # `in_sigma` to NaN (a genuine x87 negative-variance rounding
                # outcome, live-DLL-confirmed against the real histogram, see
                # `hist_resample`'s own comment on its resample-store fix),
                # and NaN is very much a "degenerate" histogram in exactly the
                # sense this comment meant -- yet on real photographic data it
                # is the COMMON case, not a rare one (100% of frames on one
                # real test roll hit it before the store-width fix below).
                # The actual reason the walk now converges well inside
                # n_buckets even for that degenerate case is `hist_resample`'s
                # own fix: once `r.out` is correctly narrowed to what the real
                # `mov dword [edx+esi*4], eax` store keeps (int32, not the
                # raw unbounded `_ftol2` result), a NaN-cascaded `r.out` comes
                # back all zeros -- live-DLL-confirmed -- and `want` (itself
                # `round_half_up(tot*pct)` with `tot == 0`) is already 0, so
                # the walk finds `want <= 0` at `i == 0` and never gets close
                # to `n_buckets`, let alone `n_bins`. This guard therefore
                # stays as a loud failure for whatever combination would still
                # defeat that convergence, rather than a value this port can
                # honestly invent -- but it is not expected to fire on real
                # data anymore, and the fix that stopped it firing was in
                # `hist_resample`, not here.
                raise RuntimeError(
                    f"{CNA_ANALYZE_IMAGE:#x}: the crossing walk ran past "
                    f"bucket {n_buckets} into the uninitialised tail of the "
                    "resample scratch; the vendor reads it, but there is no "
                    "defined value to model")
            want -= r.out[i]
            if want <= 0:
                cross = i
                break
        if cross is None:
            cross = tot          # the slot's prior value -- see 0x1022e442
        sum_bucket = 0
        for v in bucket:
            sum_bucket = i32(sum_bucket + v)
        fsb = float(sum_bucket)
        for i in range(n_buckets):
            src[i] = f32(_x87_div(float(bucket[i]), fsb))
            den[i] = f32(_x87_div(float(r.out[i]), ftot))
        return r, cross

    # -- 3/4. dark half ---------------------------------------------------
    a.dark, a.cross_dark = _half(p.darkScale, p.darkMaxContrastGain)
    contrast_map_down(p, src, den, curve, pivot_bucket, a.cross_dark, n_buckets)

    # -- 5. light half ----------------------------------------------------
    a.light, a.cross_light = _half(p.lightScale, p.lightMaxContrastGain)
    contrast_map_up(p, src, den, curve, pivot_bucket, a.cross_light, n_buckets)
    a.curve = list(curve)

    # -- 6. elmo ----------------------------------------------------------
    a.elmo = elmo_detect(p, img, a.light.in_sigma, a.light.out_sigma)

    # -- 7. smooth and expand ---------------------------------------------
    smoothed = gauss_smooth(curve, n_buckets, p.toneScaleSmoothingSigma,
                            p.smoothingSizeFactor)
    lut = build_tone_lut(smoothed, n_buckets, n_bins)

    # -- 8. normalise at the ORIGINAL pivot (0x1022e9e3) ------------------
    delta = pivot_orig - lut[pivot_orig]
    for i in range(n_bins):
        v = lut[i] + delta
        if v < 0:
            v = 0
        elif v > K_LUT_MAX:
            v = K_LUT_MAX
        lut[i] = i16(v)
    a.tone_lut = lut
    return a


# ---------------------------------------------------------------------------
# 0x1022ceb0 -- the AnsCnaParams validator
# ---------------------------------------------------------------------------

#: Bound constants the validator reads out of ``.rdata``.
K_BLEND_MIN = 0.10000000149011612    # dword 0x10598cac
K_BLEND_MAX = 9.0                    # dword 0x10598cb0
K_MIN_POS_THRESHOLD = 4              # word  0x10598cb4
K_SIZE_FACTOR_MIN = 1.0              # dword 0x10598cb8
K_SIZE_FACTOR_MAX = 10.0             # dword 0x10598cbc
K_SIGMA_MIN = 1.0                    # dword 0x10598cc0
K_SIGMA_MAX = 50.0                   # dword 0x10598cc4
K_ONE_F64 = 1.0                      # qword 0x10574f50


class CnaBadFieldError(RuntimeError):
    """What ``0x1022eada`` throws: "Bad field(#N) in AnsCnaParams structure!"."""

    def __init__(self, field: int):
        self.field = field
        super().__init__(
            f"Bad field(#{field}) in AnsCnaParams structure! "
            f"[{FUNC_ANALYZE}, {SRC_FILE}:{BAD_FIELD_LINE}] "
            f"(code {BAD_FIELD_CODE})")


def validate_params(p: CnaParams) -> int | None:
    """``0x1022ceb0`` — returns the failing field index, or ``None`` if valid.

    ``ecx`` is the **params** base (``impl+0xc``, from ``lea ecx,[esi+0xc]`` at
    ``0x1022ea7f``); ``ebx`` points at the int the field index is written to;
    the return is 0 for valid and -1 for invalid.

    The field numbers are DPI key positions, not the order of the checks -- 9,
    0x14..0x19 and 0x1f are never emitted, so a gap in this table is not a
    missing check.

    Three x87 idioms decide the strictness and they do not read the way they
    look.  ``test ah,0x41; jp`` jumps when ``st0 > src`` (both C3 and C0 clear);
    ``test ah,5; jp`` jumps when ``st0 >= src``; and ``test ah,1; je``
    (``0x1022cfc1``, used only for ``thresholdReductionFactor``'s upper bound)
    tests C0 alone and therefore rejects ``>= 1.0`` rather than ``> 1.0``.

    Every check passes on the shipped ``ansel-cna-default-default.dpi`` values,
    so this is a guard rather than live behaviour -- but a caller that edits the
    DPI hits it, and the shell then sees a throw rather than a status.
    """
    if not CNA_VALIDATE_PARAMS_PORTED:
        _unported("CNA_VALIDATE_PARAMS_PORTED", CNA_VALIDATE_PARAMS,
                  "validate_params")
    if not p.histSize > K_LUT_MAX:                                # 0x1022ceb0
        return 4
    if p.bucketSize < 1:                                          # 0x1022cec6
        return 5
    if idiv(p.histSize, p.bucketSize) * p.bucketSize != p.histSize:
        return 5                                                  # 0x1022cee2
    if not p.lowClamp > 0.0:                                      # 0x1022cef3
        return 6
    if not p.highClamp > p.lowClamp:                              # 0x1022cf0c
        return 7
    if not (p.blend >= K_BLEND_MIN) or p.blend > K_BLEND_MAX:     # 0x1022cf28
        return 8
    if not p.minPivotPercentile >= 0.0:                           # 0x1022cf50
        return 0xA
    if (not p.maxPivotPercentile > p.minPivotPercentile
            or p.maxPivotPercentile > K_ONE_F64):                 # 0x1022cf69
        return 0xB
    if not p.thresholdMultiplier > 0.0:                           # 0x1022cf91
        return 0xC
    if (not p.thresholdReductionFactor > 0.0
            or p.thresholdReductionFactor >= K_ONE_F64):          # 0x1022cfad
        return 0xD
    if i16(p.minPosThreshold) < K_MIN_POS_THRESHOLD:              # 0x1022cfce
        return 0xE
    if not (p.minLapPixelRatio >= 0.0) or p.minLapPixelRatio > K_ONE_F64:
        return 0xF                                                # 0x1022cfee
    if (not (p.smoothingSizeFactor >= K_SIZE_FACTOR_MIN)
            or p.smoothingSizeFactor > K_SIZE_FACTOR_MAX):        # 0x1022d016
        return 0x10
    for idx, val in ((0x11, p.laplacianHistSmoothingSigma),       # 0x1022d03e
                     (0x12, p.coarseHistSmoothingSigma),          # 0x1022d066
                     (0x13, p.toneScaleSmoothingSigma)):          # 0x1022d08e
        if not (val >= K_SIGMA_MIN) or val > K_SIGMA_MAX:
            return idx
    for idx, val in ((0x1A, p.elmoNeutralLimit),                  # 0x1022d0ab
                     (0x1B, p.elmoRedLimit),
                     (0x1C, p.elmoGreenLimit),
                     (0x1D, p.elmoBlueLimit),
                     (0x1E, p.elmoSatThreshold)):
        if i16(val) < 0 or i16(val) > K_LUT_MAX:
            return idx
    if p.elmoAggressiveness not in (0, 1):                        # 0x1022d0fd
        return 0x20
    return None


# ---------------------------------------------------------------------------
# 0x1022ea50 -- AnsCnaCapabilityImpl::analyze
# ---------------------------------------------------------------------------


@dataclass
class CnaResults:
    """A host-side ``AnsCnaResults`` plus the arrays its pointers stand for.

    ``raw`` is the 0x60 bytes ``0x101320b0`` would ``rep movsd`` out of
    ``impl+0x88`` -- byte-for-byte what
    ``pakon_autotone.AutoToneSubsystems.cna_get_results`` has to return, with
    ``ToneScaleLut`` at ``+0x54`` so ``0x100fbfc1`` picks it up.  The three
    pointer fields cannot be real addresses here, so they carry non-zero
    **handles**; the shell only tests them for non-null and passes them on to
    dra and toneHelper, which take the matching arrays from the fields below.
    """

    raw: bytes = b""
    luminance_hist: list[int] = field(default_factory=list)
    edge_hist: list[int] = field(default_factory=list)
    tone_scale_lut: list[int] = field(default_factory=list)
    analysis: "CnaAnalysis | None" = None


#: Handles the shell sees in place of the three real pointers.  Any non-zero
#: value works -- the shell's only test is ``test eax, eax``.
HANDLE_LUMINANCE_HIST = 0x0C4A0008
HANDLE_EDGE_HIST = 0x0C4A001C
HANDLE_TONE_SCALE_LUT = 0x0C4A0054


def analyze(img: CnaImage, p: CnaParams | None = None, *,
            cap_flag_e: int = 0) -> CnaAnalysis:
    """``0x1022ea50`` — ``AnsCnaCapabilityImpl::analyze``.

    The real signature, established by running the function under Unicorn with
    sentinel arguments and watching which slots it reads (radare's stack-slot
    names are frame-relative and do not survive the pushes)::

        AnsStatus* analyze(AnsStatus* sret, <holder>,
                           AnsCnaCapability* cap, ImageDesc* img)   ; ecx = impl

    * ``sret`` (``[esp+4]``) receives the status -- ``0x1022eb61``.
    * ``[esp+8]`` is the refcounted holder the Cap wrapper builds; this function
      only addrefs and releases it.
    * ``cap`` (``[esp+0xc]``) is read for **one** thing: its ``+0xe`` flag byte,
      at ``0x1022edae``.  That is the same third flag byte ``pakon_autotone``
      records as ``CAP_FLAG_BYTE_E`` and notes ``declareAutoTone`` never sets --
      here it decides only whether the scratch buffers survive the call, and it
      changes no published result.  Worth knowing before Phase 2f trusts the
      same byte in contrast.
    * ``img`` (``[esp+0x10]``) is the image descriptor.

    Body (``0x1022ea50``..``0x1022ee3b``):

    1. ``validate_params`` on ``impl+0xc``.  On failure, format
       ``"Bad field(#" + N + ") in AnsCnaParams structure!"`` and throw through
       ``0x10020ad0`` with code 105 at ``cpp:1211`` -- ``CnaBadFieldError``.
    2. ``freeAll`` (``0x1022d2e0``), then ``allocateMemory`` (``0x1022d970``)
       with ``(width, height)`` out of the descriptor.  A failed allocation
       throws "Failed in 'new'." (code 202, ``cpp:1477``).
    3. ``analyzeImage`` (``0x1022ddc0``); on a non-OK status, ``freeAll`` again
       and propagate.
    4. ``if (cap == 0 || cap[0xe] == 0) freeScratch(impl)`` (``0x1022d1a0``) --
       the twelve working buffers go and ``LuminanceHist``, ``EdgeHist`` and
       ``ToneScaleLut`` stay, which is exactly the three the shell reads.

    The port owns its buffers in Python, so ``cap_flag_e`` changes nothing
    observable; it is accepted and recorded for fidelity.
    """
    if not CNA_ANALYZE_PORTED:
        _unported("CNA_ANALYZE_PORTED", CNA_ANALYZE,
                  "AnsCnaCapabilityImpl::analyze")
    p = p if p is not None else default_params()
    bad = validate_params(p)
    if bad is not None:
        raise CnaBadFieldError(bad)
    return analyze_image(img, p)


def analyze_to_results(img: CnaImage, p: CnaParams | None = None,
                       *, cap_flag_e: int = 0) -> CnaResults:
    """``analyze`` plus the ``0x101320b0`` getter, as the shell consumes them.

    The shell's stage 1 is ``acquire`` then a fixed 0x18-dword ``rep movsd``
    out of ``impl+0x88``; this returns exactly that window, so
    ``pakon_autotone.AutoToneSubsystems.cna_get_results`` can hand it straight
    back and ``ctx+0x64d0 = results.ToneScaleLut`` lands on the LUT built here.
    """
    if not CNA_ANALYZE_PORTED:
        _unported("CNA_ANALYZE_PORTED", CNA_ANALYZE, "analyze_to_results")
    p = p if p is not None else default_params()
    a = analyze(img, p, cap_flag_e=cap_flag_e)
    buf = bytearray(_at().AUTOTONE_WORK_LAYOUT["AnsCnaResults"]["size"])
    struct.pack_into("<i", buf, 0x00, a.n_pixels)
    struct.pack_into("<I", buf, 0x08, HANDLE_LUMINANCE_HIST)
    struct.pack_into("<i", buf, 0x10, a.threshold)
    struct.pack_into("<i", buf, 0x14, a.n_edge)
    struct.pack_into("<I", buf, 0x1C, HANDLE_EDGE_HIST)
    struct.pack_into("<f", buf, 0x20, a.dark.in_sigma if a.dark else -1.0)
    struct.pack_into("<f", buf, 0x24, a.light.in_sigma if a.light else -1.0)
    struct.pack_into("<f", buf, 0x28, a.dark.out_sigma if a.dark else -1.0)
    struct.pack_into("<f", buf, 0x2C, a.light.out_sigma if a.light else -1.0)
    struct.pack_into("<I", buf, 0x54, HANDLE_TONE_SCALE_LUT)
    struct.pack_into("<f", buf, 0x58, a.elmo.elmo_percent if a.elmo else -1.0)
    buf[0x5C] = 1 if (a.elmo and a.elmo.b_elmo_occured) else 0
    return CnaResults(raw=bytes(buf),
                      luminance_hist=list(a.threshold_stage.lum_hist),
                      edge_hist=list(a.threshold_stage.edge_hist),
                      tone_scale_lut=list(a.tone_lut), analysis=a)


# ---------------------------------------------------------------------------


def main() -> None:
    p = default_params()
    print(f"AnsCnaCapabilityImpl::analyze {CNA_ANALYZE:#010x}")
    print("  walk(0x1022ea50) = 36 fns / 11,593 B / 22 indirect "
          "(tools/re/reachability.py, aaa)")
    print(f"  NOT cna: {NOT_CNA_DRA_ACQUIRE_HIST:#010x} is dra's acquire+hist "
          "(sole caller 0x1013115b, inside 0x10131100)")
    print()
    print("  params (0x100f8030 == ansel-cna-default-default.dpi):")
    for name in ("histSize", "bucketSize", "pivot", "minPivotPercentile",
                 "thresholdReductionFactor", "elmoNeutralLimit",
                 "elmoCriticalPercent", "elmoAggressiveness"):
        print(f"    {name:<26} {getattr(p, name)}")
    print()
    sizes = buffer_sizes(p, 1000 * 1500)
    print("  buffer element counts for a 1000x1500 frame:")
    for k, v in sizes.items():
        print(f"    {k:<20} {v}")
    print()
    print(f"  FTOL2={CNA_FTOL2_PORTED} LAPLACIAN={CNA_LAPLACIAN_PORTED} "
          f"GAUSS={CNA_GAUSS_SMOOTH_PORTED} PEAK={CNA_PEAK_SEARCH_PORTED}")
    print(f"  HIST_RESAMPLE={CNA_HIST_RESAMPLE_PORTED} "
          f"ALLOCATE={CNA_ALLOCATE_MEMORY_PORTED} "
          f"THRESHOLD_STAGE={CNA_ANALYZE_IMAGE_THRESHOLD_PORTED}")
    print(f"  CONTRAST_MAP={CNA_CONTRAST_MAP_PORTED} "
          f"TONE_LUT_BUILD={CNA_TONE_LUT_BUILD_PORTED} "
          f"VALIDATE_PARAMS={CNA_VALIDATE_PARAMS_PORTED}")
    print(f"  ANALYZE_IMAGE={CNA_ANALYZE_IMAGE_PORTED} "
          f"ANALYZE={CNA_ANALYZE_PORTED}")
    print()
    img = CnaImage(width=12, height=9,
                   pixels=[((i * 37) % 3000) + 200 for i in range(12 * 9 * 3)])
    res = analyze_to_results(img, p)
    lut = res.tone_scale_lut
    print(f"  12x9 frame: ToneScaleLut[0]={lut[0]} "
          f"[{p.pivot}]={lut[p.pivot]} [-1]={lut[-1]}  "
          f"elmoOccured={bool(res.raw[0x5C])}")
    bad = params_from_bytes(params_to_bytes(p))
    bad.thresholdReductionFactor = 1.0
    try:
        analyze(img, bad)
    except CnaBadFieldError as exc:
        print(f"  validator throws as the DLL does: {exc}")


if __name__ == "__main__":
    main()
