#!/usr/bin/env python3
"""``dra`` — stage 2 of ``ColorNegativePath::analyzeAutoTone``.

PakonIMAu.dll ImageBase ``0x10000000`` (file VAs == cited VAs), sha256
``0ede8d9813af4ee95dddd85e5adc495a27f014a8fd4817cfbc3b3b1e107f511f``.  This
file is to ``dra`` what ``pakon_shasta.py`` is to Shasta: the subsystem plus its
``*_PORTED`` flags.  Phase 1's shell (``pakon_autotone.py``) calls into here.

WHICH TWO FUNCTIONS ``dra`` ACTUALLY HAS — A CORRECTION TO THE BRIEF
====================================================================
The Phase-2b brief said ``dra``'s two acquire-Impl entry points are
``0x1022af20`` and ``0x101dd1b0``.  **``0x101dd1b0`` is not ``dra``.**  It is
``toneHelper``'s acquire-with-histograms Impl and belongs to Phase 2c.  Proven
three independent ways against the DLL:

* **Callers.**  A full ``E8 rel32`` scan of ``.text`` finds exactly one direct
  caller for each: ``0x1022af20`` <- ``0x10131071`` (inside dra's Cap wrapper
  ``0x10131020``), ``0x1022b530`` <- ``0x1013115b`` (inside dra's Cap wrapper
  ``0x10131100``), and ``0x101dd1b0`` <- ``0x1010c412``, which is inside
  ``0x1010c3b0``..``0x1010c667`` — **toneHelper's** Cap wrapper, the one
  ``pakon_autotone.CAP_CALLS`` already lists as ``th.acquireHist``.
* **Self-naming.**  Both ``0x1022af20`` and ``0x1022b530`` push
  ``"AnsDraCapabilityImpl::analyze"`` (``0x1059f73c``) together with
  ``"\\Atc\\ansel\\src\\libDra.ansel\\AnsDraCapabilityImpl.cpp"``
  (``0x1059f65c``) at their log and throw sites.  They are two **overloads** of
  the same C++ method — the source lines quoted differ (738 / ``0x2e2`` vs
  826 / ``0x33a``) but the file does not.
* **Reachability** (``tools/re/reachability.py walk``, this session, ``aaa``),
  which reproduces Phase 1's own table exactly::

      0x1022af20   38 fns /  9,757 B / 45 indirect     (Phase 1: "acquire")
      0x1022b530   41 fns / 10,017 B / 40 indirect     (Phase 1: "acquire+hist")
      0x101dd1b0   37 fns / 13,691 B / 62 indirect     (Phase 1: "toneHelper A")
      0x10130390    2 fns /     71 B /  0 indirect     (getResults, rep movsd)

  ``setops`` over the two dra walks: **37 of 42 functions are shared**.
  ``0x1022af20`` alone adds only itself; ``0x1022b530`` adds itself plus
  ``0x10001560``, ``0x10199680``, ``0x1022a210``.  They are near-identical
  siblings, not two different algorithms.

WHAT ACTUALLY DIFFERS BETWEEN THE TWO VARIANTS
==============================================
Verified by reading both bodies, not assumed.  **The difference is where the
histograms come from, and whether the result is composed onto an incoming tone
LUT.**

``0x1022af20`` — ``analyze(&st, cap, imageData)``, ``ret 0x10``
    Reached via Cap ``0x10131020`` when the shell's ``ctx+0x64d0`` is **null**
    (cna produced no tone object).  It **computes the luminance histogram
    itself** from raw pixels, at ``0x1022b1a0``::

        n    = imageData[+0x0c] * imageData[+0x10]      # 0x1022b17f/0x1022b182
        px   = imageData[+0x20]                          # int16 R,G,B triples
        lum  = (R + G + B + 1) / 3                       # signed, trunc-to-zero
        hist[lum] += 1

    It has **no** incoming tone LUT, so it never composes: it builds the dra
    LUT into ``impl+0x1cc0`` and returns.

``0x1022b530`` — ``analyze(&st, cap, lumHist, edgeHist, toneLut)``, ``ret 0x18``
    Reached via Cap ``0x10131100`` when ``ctx+0x64d0`` is non-null.  It
    **receives** both histograms and ``rep movsd``-copies them in (0x1022b873:
    lumHist -> ``impl+0x1c8c``, edgeHist -> ``impl+0x1c90``), throwing
    ``"No analysis data was provided!."`` (line 842 / ``0x34a``) if both are
    null.  After the LUT is built it **composes** onto the incoming tone LUT,
    at ``0x1022bb0f``::

        memcpy(impl+0x1cb0, impl+0x1cc0, n*2)            # scratch <- draLut
        for i in range(n):
            draLut[i] = scratch[toneLut[i]]              # 0x1022bb41..0x1022bb50

    i.e. ``out = draCurve o toneLut`` — the composition every stage of the tone
    chain does.  ``0x1022af20`` has no equivalent block.

Everything else — parameter validation (``0x10228e40``), buffer allocation
(``0x1022a820``), the scene-context fetch (``0x10021730``), the guarded
``find("lighting")``, ``generateLut`` (``0x1022ab50``) and its leaves — is
shared, which is exactly why the reachable sets overlap 37/42.

THE ``find("lighting")`` BRANCH — "MISS CONTINUES", IN **BOTH** VARIANTS
=======================================================================
This behaviour was previously mis-documented as "miss is fatal".  That was
**wrong**.  It was corrected by live Unicorn execution against the real DLL
(``pakon_dra_lighting_golden.py``; mirrored notes in
``tools/ansel/pipeline/shasta.go`` and ``tools/ansel/python-pipeline/
pakon_shasta.py``).  The corrected finding, implemented here from the start:

* A **miss CONTINUES** to the LUT-building path.  ``"lighting"`` is never in
  CN-Enhanced's declared capability list, so this fires on **every real
  negative**, and it is a harmless no-op — not an abort.
* The branch flag does **not** encode found-vs-not-found.  It encodes whether
  ``AnsSceneContext::find`` raised an **internal** error (a value-size mismatch
  or a heap-allocation failure).  A clean miss and a clean size-matching hit
  take the **same** continue path; only a genuine internal error aborts.

The brief cites one site.  There are **two** — the second was found this
session and is structurally identical, so a port that guards only the first
would still be half-broken::

    variant      key str      find call    setne     test/je      -> continue
    0x1022af20   0x1022b2e5   0x1022b314   0x1022b327   0x1022b35b   0x1022b3b0
    0x1022b530   0x1022b99d   0x1022b9cf   0x1022b9e2   0x1022b9f9   0x1022baa4

    abort target 0x1022b383 (line 792 / 0x318) and 0x1022ba08 (line 886 /
    0x376), both "Failed in AnsSceneContext::find(...).".

Both sites call ``0x10022a40`` as ``find(&st, &name, &outSlot, 2, 1)`` — a
**2-byte** value, count 1 — and both then do the same null-fixup before use::

    if (outSlot == NULL) lightingValue = 0;      # 0x1022b3b0 / 0x1022baa4

so a miss is not merely non-fatal, it is *defined*: it yields lighting **0**.

WHAT LIGHTING 0/1/2 SELECT — AND WHY THE MISS IS NUMERICALLY INERT HERE
=======================================================================
``generateLut`` (``0x1022ab50``, self-named ``AnsDraCapabilityImpl::generateLut``
at ``0x1059f6d8``) hands the value to ``keepMidPtLut`` (``0x102290b0``), whose
first act is a three-way dispatch on it (``0x102290d6``/``0x10229136``)
selecting a **pair** of tone-transfer-curve blocks in the params object:

    ======  ==================  =================  ===================
    value    low block           high block         .dpi key pair
    ======  ==================  =================  ===================
    1        params+0x9a8        params+0xe5c       low/highBacklitTTC
    2        params+0x1310       params+0x17c4      low/highFrontlitTTC
    else     params+0x40         params+0x4f4       low/highNormalTTC
    ======  ==================  =================  ===================

(offsets relative to ``generateLut``'s params pointer, ``impl+0x10``; see
``DRA_PARAMS_LAYOUT``.)  So **0 = Normal, 1 = Backlit, 2 = Frontlit**, and the
"lighting" miss lands on Normal.

The block stride is ``0x4b4`` = 1204 B = one ``int32`` count plus three
``float32[100]`` arrays, and it is confirmed twice over: the six ``*TTC`` keys
in the parser land at params+0x6c, +0x520, +0x9d4, +0xe88, +0x133c, +0x17f0 —
each exactly ``0x4b4`` apart — and those minus the ``0x2c`` base skew are
``generateLut``'s +0x40, +0x4f4, +0x9a8, +0xe5c, +0x1310, +0x17c4.

**On this unit's shipped data the selected pair is the identity curve.**
``vendor/ansel/anselinstalldir/dataPathItems/dra/lowNormal.ttc`` and
``highNormal.ttc`` are both the 3-point identity ``0 0 / 1 1 / 10 10``; five of
the six shipped ``.ttc`` files are identity and only ``lowBacklit.ttc`` carries
a real transform.  That is an independent, numerical corroboration of the
"harmless no-op" finding: on a real negative the miss selects Normal, and
Normal is identity.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
  tools/ansel/python-pipeline/pakon_dra.py``
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# addresses
# ---------------------------------------------------------------------------

#: ``AnsDraCapabilityImpl::analyze`` overload A — computes its own histogram.
#: ``0x1022af20``..``0x1022b527``, 1,543 B, 96 bbs, ``ret 0x10``.
DRA_ANALYZE_IMAGE = 0x1022AF20
#: ``AnsDraCapabilityImpl::analyze`` overload B — takes histograms + tone LUT.
#: ``0x1022b530``..``0x1022bbc7``, 1,687 B, 83 bbs, ``ret 0x18``.
DRA_ANALYZE_HIST = 0x1022B530

#: Cap-level wrappers, already ported by Phase 1 — listed for provenance only.
DRA_CAP_ACQUIRE = 0x10131020        # -> DRA_ANALYZE_IMAGE at 0x10131071
DRA_CAP_ACQUIRE_HIST = 0x10131100   # -> DRA_ANALYZE_HIST  at 0x1013115b
DRA_CAP_GET_RESULTS = 0x10131220    # -> 0x10130390, rep movsd 0x3c

DRA_GET_RESULTS_IMPL = 0x10130390   # rep movsd 0xf dwords from impl+0x1c88
DRA_GENERATE_LUT = 0x1022AB50       # AnsDraCapabilityImpl::generateLut
DRA_KEEP_MIDPT_LUT = 0x102290B0     # "keepMidPtLut", the lighting dispatch
DRA_REBIN = 0x10228E00              # small bins -> large bins
DRA_CUM_BOUNDS = 0x10228BC0         # cumulative-percentile min/max
DRA_EFF_BOUNDS = 0x10228CD0         # lum/edge -> effective min/max
DRA_ALLOC_BUFFERS = 0x1022A820      # histogram/LUT allocation
DRA_VALIDATE_PARAMS = 0x10228E40    # returns 1-based bad-parameter index
DRA_PARSE_DPI = 0x102283A0          # the .dpi text parser (1,868 B)
DRA_RELEASE_CTX = 0x102294D0        # scene-context release
DRA_RELEASE_CTX_AND_LUT = 0x1022A210  # release + free impl+0x1cc0

SCENE_CONTEXT_FIND = 0x10022A40     # AnsSceneContext::find
GET_SCENE_CONTEXT = 0x10021730
STATUS_OK_GLOBAL = 0x106B5BD4       # the AnsStatus "no error" singleton

#: The two guarded ``find("lighting")`` sites, in call order per variant.
#: ``(key_push, find_call, setne, test_je, continue_target, abort_target, line)``
DRA_LIGHTING_SITES: dict[int, tuple[int, int, int, int, int, int, int]] = {
    DRA_ANALYZE_IMAGE: (0x1022B2E5, 0x1022B314, 0x1022B327, 0x1022B35B,
                        0x1022B3B0, 0x1022B383, 792),
    DRA_ANALYZE_HIST: (0x1022B99D, 0x1022B9CF, 0x1022B9E2, 0x1022B9F9,
                       0x1022BAA4, 0x1022BA08, 886),
}

STR_LIGHTING = 0x10574048           # "lighting"
STR_SRC_FILE = 0x1059F65C           # ...\libDra.ansel\AnsDraCapabilityImpl.cpp
STR_FUNC_ANALYZE = 0x1059F73C       # "AnsDraCapabilityImpl::analyze"
STR_FUNC_GENERATE_LUT = 0x1059F6D8  # "AnsDraCapabilityImpl::generateLut"
STR_FIND_FAILED = 0x1059F714        # "Failed in AnsSceneContext::find(...)."
STR_NO_DATA = 0x1059F75C            # "No analysis data was provided!."
STR_NO_SCENE_CTX = 0x1058526C       # "Can't get scene context."
STR_KEEP_MIDPT_FAILED = 0x1059F6FC  # "Failed in keepMidPtLut."

SRC_FILE = r"\Atc\ansel\src\libDra.ansel\AnsDraCapabilityImpl.cpp"
FUNC_ANALYZE = "AnsDraCapabilityImpl::analyze"
FUNC_GENERATE_LUT = "AnsDraCapabilityImpl::generateLut"

#: ``find(&st, &name, &out, 2, 1)`` — the literal size/count immediates pushed
#: at ``0x1022b2fa``/``0x1022b2f8`` and ``0x1022b9b2``/``0x1022b9b0``.
LIGHTING_VALUE_SIZE = 2
LIGHTING_VALUE_COUNT = 1

# .rdata constants used by the leaves
F32_PERCENT = 0.009999999776482582   # 0x1059f5f0, the 1/100 in 0x10228bc0
F64_HALF = 0.5                       # 0x10574f40, the round-to-nearest bias

# ---------------------------------------------------------------------------
# flags
# ---------------------------------------------------------------------------

# The two entry points' identity, their one real difference, and the shared
# 37/42-function body — established by caller scan, self-naming strings and
# tools/re/reachability.py walk/setops (numbers in the docstring).
DRA_ENTRY_POINTS_PORTED = True

# The guarded find("lighting") semantics at BOTH sites: miss continues, the
# flag encodes internal-error-only, and a miss is defined as lighting 0.
# Verified by executing the real DLL bytes under Unicorn — the real
# AnsSceneContext::find over a real empty std::map — in pakon_dra_golden.py.
DRA_LIGHTING_BRANCH_PORTED = True

# The 0/1/2 -> Normal/Backlit/Frontlit dispatch in keepMidPtLut (0x102290d6,
# 0x10229136, 0x10229186) and the params block addresses it selects.
DRA_LIGHTING_DISPATCH_PORTED = True

# ansel-dra-default-default.dpi: 25 keys -> DRA_PARAMS_LAYOUT.
#
# WAS tier-3 only (the key/offset/format triples were read off the parser
# 0x102283a0's repe-cmpsb + sscanf chain by eye).  NOW Unicorn-verified: the
# real per-line body 0x102283d5..0x10228965 is executed on real line text
# with the CCRT sscanf import hooked, and the 0x40-byte scalar params image
# the real code writes at ebp+0x2c is diffed BYTE-FOR-BYTE against the
# port's own image, per line.  See pakon_dra_golden.check_parse_dpi.
#
# That verification found TWO REAL DIVERGENCES in this port, both now fixed
# (they are why this was worth doing rather than trusting the static read):
#
#   1. The three bools are NOT strcmp(value, "true").  The DLL does
#      sscanf(value, "%c", &c) then `cmp byte, 0x74 ; sete` -- a single
#      LOWERCASE 't' on the first character only (0x102285c4/0x102285d8 and
#      its two twins).  "True"/"TRUE" are FALSE to the real DLL; the old
#      port made them False too but by accident, and made "t" False where
#      the DLL makes it True.
#   2. The line tokeniser is sscanf("%s = %s"), not a split on '='.  A
#      "key=value" line with no surrounding spaces returns 1 conversion and
#      is REJECTED by 0x10228423; the old split-based port accepted it.
#      Likewise the comment test at 0x102283d5 is a FIRST-CHARACTER test,
#      not "strip from the first '#'".
#
# On the shipped ansel-dra-default-default.dpi every key is written in the
# canonical "key = value" form with a lowercase "true"/"false", so NEITHER
# divergence changes any currently-loaded value.  This fix is correctness of
# the port against the vendor, not a behaviour change to the render path --
# stated plainly so nobody reads it as a found-and-fixed render bug.
#
# NOT covered: the CRT sscanf itself is hooked, not emulated (it is MSVCR71,
# not vendor code), and the six *TTC arms (0x102287e8..0x1022894b) are
# outside the verified slice because they need live MSVCP71 std::string
# rfind/substr; their key->block-offset mapping remains tier-3.
DRA_DPI_PARSE_PORTED = True

# The .ttc control-point files and the 0x4b4-stride params block they land in.
DRA_TTC_PARSE_PORTED = True

# AnsDraResults, 0x3c B at impl+0x1c88. Phase 1 proved size and four field
# names from the dumper 0x1013003c; every remaining slot is confirmed here by
# its use inside generateLut (see DRA_RESULTS_LAYOUT).
DRA_RESULTS_LAYOUT_PORTED = True

# 0x10228e00 — small-bin -> large-bin decimation. Unicorn-verified.
DRA_REBIN_PORTED = True

# 0x1022b1a0 — variant A's own luminance histogram. Unicorn-verified.
DRA_LUM_HISTOGRAM_PORTED = True

# 0x1022bb0f — variant B's compose-onto-tone-LUT block. Unicorn-verified.
DRA_COMPOSE_TONE_PORTED = True

# 0x10228bc0 — cumulative-percentile min/max scan. Unicorn-verified.
DRA_CUM_BOUNDS_PORTED = True

# ---- Phase 2b-continuation additions, Unicorn-verified below. -------------

# 0x10228cd0 — effective min/max. Both branches ported: the bDoAverage==false
# clamp (min/max of lum vs edge, clamped to paperMin/paperMax) and the LIVE
# bDoAverage==true weighted lumWeighting/edgeWeighting blend at 0x10228d34.
# 76 cases (both branches x random + hand-picked crossing cases) all pass in
# pakon_dra_golden.check_eff_bounds against the real DLL.
DRA_EFF_BOUNDS_PORTED = True

# 0x102290b0 — keepMidPtLut. The lighting dispatch at its head IS ported (see
# DRA_LIGHTING_DISPATCH_PORTED); the ~280 instructions of x87 curve
# construction after it are now ported too (see keep_midpt_lut). 5 cases
# (identity curves, shaped curves, all three lighting values, both eff/paper
# clamp branches live) pass in pakon_dra_golden.check_keep_midpt_lut against
# the real DLL under FPCW=0x027f. NOTE: an FPCW negative control was
# attempted (400+ synthetic cases across several targeted strategies) and did
# NOT find a case where 0x027f and 0x037f diverge for this function -- unlike
# toneHelper's iterative statistics, this function's arithmetic is short
# chains (one divide, one multiply-add) whose search-loop comparisons mostly
# operate on already-float32-narrowed memory operands, so the negative
# control does not have confirmed teeth here. FPCW=0x027f is still applied
# (it is the documented, structurally-justified Windows/MSVC default used by
# every sibling harness in this project), but that specific claim -- "getting
# FPCW right measurably changes this function's output" -- is UNPROVEN, not
# proven, for keepMidPtLut specifically.
DRA_KEEP_MIDPT_LUT_PORTED = True

# 0x10227c60's slope-computation snippet (0x10227e93..0x10227eab): the .ttc
# parser's third float32[100] array (segment slope, keepMidPtLut's own
# interpolation input) is DERIVED, not read from the file -- the previous
# state of this repo's port only had x/y. 10 cases Unicorn-verified against
# the real snippet in pakon_dra_golden.check_ttc_slopes.
DRA_TTC_SLOPE_PORTED = True

# ---- Phase 2b-continuation, part 2: the remaining assembly. ---------------
#
# 0x1022ab50 (generateLut orchestration), 0x10228e40 (validate_params),
# 0x1022a820 (alloc) and both 0x1022af20/0x1022b530 analyze() overloads are
# now assembled below, each Unicorn-verified against the real DLL bytes in
# pakon_dra_golden.py before its flag was flipped True. See that file's
# check_validate_params / check_alloc / check_generate_lut /
# check_analyze_image / check_analyze_hist for the evidence.

# 0x10228e40 — returns 0 (valid) or a 1-based bad-parameter index (1..19).
# The bad-index -> field mapping and every range's exact inclusive bounds
# were NOT hand-decoded from the x87 flag bytes (that reasoning was tried
# and, per this project's own repeated experience with x87 parity idioms,
# is exactly the kind of static reading that gets flag polarity backwards
# -- see keep_midpt_lut's docstring for a worked example of that failure
# mode elsewhere in this file). Instead every bound below was read off the
# real DLL: a known-valid baseline (the shipped ansel-dra-default-default.dpi
# values) plus ~35 single-field perturbations, each executed under Unicorn
# and its (pass/fail, bad-index) result recorded. See
# check_validate_params for the full calibration table.
DRA_VALIDATE_PARAMS_PORTED = True

# 0x1022a820 — AnsDraCapabilityImpl::allocateMemory. ABI (ecx=impl; stack:
# &outStorage, nSmallBins, allocLum, allocEdge; ret 0x10) established by
# reading the real call site bytes at both Cap wrappers, not guessed.
# Unicorn-verified: operator new (0x104ffd78) hooked to the emulator's own
# bump allocator, and the resulting results-struct field pointers/sizes
# compared against the port for the (allocLum, allocEdge) in
# {(T,F),(F,T),(T,T)} combinations real dra ever uses.
DRA_ALLOC_PORTED = True

# 0x1022ab50 — generateLut's orchestration: the toneLut-gated small-bin
# histogram remap (0x1022abaf/0x1022acbe, only present in variant B's
# call), rebin, cumulative sum, cum_bounds, and the three-way eff-bounds
# merge (edge absent -> copy lum; lum absent -> copy edge; both present ->
# the already-verified eff_bounds()) discovered by direct disassembly of
# 0x1022adc1..0x1022ae12 (not previously documented), then keepMidPtLut.
# Unicorn-verified end to end against the real 0x1022ab50 bytes across the
# lum-only / edge-only / both / toneLut-remap-live configurations.
DRA_GENERATE_LUT_PORTED = True

# The two analyze overloads end to end, run from their TRUE entry points
# (0x1022af20 / 0x1022b530) under Unicorn -- not a mid-function slice. The
# entry-time register/stack contract (ecx=impl; stack args &outStorage,
# <unused>, cap, imageData for the image overload; the histogram/toneLut
# equivalents for the hist overload) was read off the REAL, compiled Cap
# wrapper call sites (0x10131020 -> 0x1022af20 at 0x10131071, 0x10131100 ->
# 0x1022b530 at 0x1013115b), not guessed or probed. See
# check_analyze_image / check_analyze_hist.
DRA_ANALYZE_IMAGE_PORTED = True
DRA_ANALYZE_HIST_PORTED = True

# Umbrella flag consumed by pakon_autotone.py's shell -- both overloads plus
# every piece they assemble (validate_params, alloc, generate_lut) are
# independently verified above, so this simply reflects that the whole
# subsystem is done. Kept as a real module-level flag (not just restated in
# pakon_autotone.py) so the two files can't drift.
DRA_ANALYZE_PORTED = True


def _unported(flag: str, va: int, what: str) -> "NoReturn":  # noqa: F821
    raise RuntimeError(
        f"{flag} is False: {what} ({va:#x}) is not ported. See "
        f"tools/ansel/python-pipeline/pakon_dra.py for what is and is not "
        f"covered by Phase 2b.")


# ---------------------------------------------------------------------------
# lighting
# ---------------------------------------------------------------------------

LIGHTING_NORMAL = 0
LIGHTING_BACKLIT = 1
LIGHTING_FRONTLIT = 2

#: value -> (low .dpi key, high .dpi key, low block off, high block off).
#: Offsets are relative to ``generateLut``'s params pointer (``impl+0x10``).
LIGHTING_DISPATCH: dict[int, tuple[str, str, int, int]] = {
    LIGHTING_BACKLIT: ("lowBacklitTTC", "highBacklitTTC", 0x9A8, 0xE5C),
    LIGHTING_FRONTLIT: ("lowFrontlitTTC", "highFrontlitTTC", 0x1310, 0x17C4),
    LIGHTING_NORMAL: ("lowNormalTTC", "highNormalTTC", 0x40, 0x4F4),
}


def lighting_curve_keys(lighting: int) -> tuple[str, str]:
    """``keepMidPtLut``'s head, ``0x102290d6``..``0x102291c8``.

    ``cmp dx,1`` / ``cmp dx,2`` and *everything else* — including the 0 a
    ``find("lighting")`` miss produces — falls through to the Normal pair.
    """
    if not DRA_LIGHTING_DISPATCH_PORTED:
        _unported("DRA_LIGHTING_DISPATCH_PORTED", DRA_KEEP_MIDPT_LUT,
                  "keepMidPtLut lighting dispatch")
    lo, hi, _, _ = LIGHTING_DISPATCH.get(
        lighting, LIGHTING_DISPATCH[LIGHTING_NORMAL])
    return lo, hi


def lighting_from_find(found: bool, raw_value: int = 0,
                       internal_error: bool = False) -> int:
    """The guarded ``find("lighting")`` at both sites, as one function.

    ``found`` is whether the scene context had the key; ``internal_error`` is
    the *only* thing the branch flag encodes (a value-size mismatch or an
    allocation failure inside ``0x10022a40``).

    Returns the lighting value to hand ``keepMidPtLut``.  Raises only on a
    genuine internal error — **a miss continues**, yielding 0 (Normal), which
    is the path every real colour negative takes.
    """
    if not DRA_LIGHTING_BRANCH_PORTED:
        _unported("DRA_LIGHTING_BRANCH_PORTED", DRA_ANALYZE_IMAGE,
                  'the guarded find("lighting")')
    if internal_error:
        # 0x1022b35b / 0x1022b9f9 fall through to 0x1022b383 / 0x1022ba08.
        raise DraError("Failed in AnsSceneContext::find(...).")
    if not found:
        # 0x1022b3b0 / 0x1022baa4: `if (outSlot == NULL) value = 0`.
        return LIGHTING_NORMAL
    return int(raw_value)


class DraError(RuntimeError):
    """What ``0x1001ed90`` raises from inside dra."""


# ---------------------------------------------------------------------------
# AnsDraParams — ansel-dra-default-default.dpi
#
# Offsets are relative to GENERATELUT'S params pointer (impl+0x10), i.e. the
# parser's own base minus 0x2c. Both are given because the parser's chain is
# the evidence and generateLut's is what the arithmetic uses.
# ---------------------------------------------------------------------------

DRA_PARAMS_BASE_SKEW = 0x2C   # parser ebp+0x2c == generateLut eax+0x00

#: ``(dpi key, generateLut offset, kind)`` in parser order (``0x102283a0``).
#: ``kind`` is the sscanf format the parser uses: ``%hd`` -> i16, ``%ld`` ->
#: i32, float -> f32, and the three bools are ``strcmp(value, "true")``.
DRA_PARAMS_LAYOUT: tuple[tuple[str, int, str], ...] = (
    ("maxValue", 0x00, "i16"),
    ("lowFixedPoint", 0x02, "i16"),
    ("highFixedPoint", 0x04, "i16"),
    ("paperMin", 0x06, "i16"),
    ("paperMax", 0x08, "i16"),
    ("minSlope", 0x0C, "f32"),
    ("maxSlope", 0x10, "f32"),
    ("binFactor", 0x14, "i32"),
    ("bDoAverage", 0x18, "bool"),
    ("lumWeighting", 0x1C, "f32"),
    ("edgeWeighting", 0x20, "f32"),
    ("bIsBacklit", 0x24, "bool"),
    ("bIsFlash", 0x25, "bool"),
    ("flashFraction", 0x28, "f32"),
    ("backlitFraction", 0x2C, "f32"),
    ("startingMinCumPoint", 0x30, "f32"),
    ("cumPctBelowMin", 0x34, "f32"),
    ("startingMaxCumPoint", 0x38, "f32"),
    ("cumPctAboveMax", 0x3C, "f32"),
    ("lowNormalTTC", 0x40, "ttc"),
    ("highNormalTTC", 0x4F4, "ttc"),
    ("lowBacklitTTC", 0x9A8, "ttc"),
    ("highBacklitTTC", 0xE5C, "ttc"),
    ("lowFrontlitTTC", 0x1310, "ttc"),
    ("highFrontlitTTC", 0x17C4, "ttc"),
)

#: One TTC block: ``int32 nPoints`` then three ``float32[100]`` arrays.
#: Stride proven by the six ``*TTC`` parser offsets being exactly this apart.
TTC_BLOCK_STRIDE = 0x4B4
TTC_MAX_POINTS = 100
TTC_ARRAY_BYTES = TTC_MAX_POINTS * 4    # 0x190

#: The four cumulative-percentile params, in the order ``0x10228bc0`` reads
#: them (``[edi+0x30]``, ``+0x34``, ``+0x38``, ``+0x3c``).
CUM_PARAM_OFFSETS = (0x30, 0x34, 0x38, 0x3C)


#: The per-.ttc-file point-scan-and-slope-build leaf, ``0x10227c60``, called
#: once per ``*TTC`` key from inside the ``.dpi`` parser's strcmp chain
#: (``0x1022894b``).  It reads ``"%f %f"`` pairs into the params block's ``x``
#: and ``y`` float32[100] arrays and, on every point after the first, ALSO
#: computes the THIRD array (the one this file's docstring calls
#: ``lo_slope``/``hi_slope``) as the plain finite-difference segment slope::
#:
#:     slope[i] = f32((y[i+1] - y[i]) / (x[i+1] - x[i]))     for i in [0, n-2)
#:
#: (``0x10227e93``..``0x10227eab``: ``fsub`` y's then x's, ``fdivp``, ``fstp``
#: float32).  ``keepMidPtLut`` (``0x102290b0``) only ever *reads* this array
#: (``fmul dword[slope_ptr + 4*i - 4]`` at ``0x10229336``/``0x10229456``) — it
#: is never computed there, which is why a port that only parsed ``x``/``y``
#: from the ``.ttc`` file (the previous state of this function) was silently
#: incomplete for anything downstream of ``keepMidPtLut``.  Unicorn-verified
#: against ``0x10227c60`` directly, not just inferred from the read sites.
DRA_TTC_SLOPE_LEAF = 0x10227C60


@dataclass
class DraTtc:
    """One ``.ttc`` tone-transfer curve: whitespace ``in out`` pairs.

    ``slope[i]`` is the params block's third float32[100] array — computed by
    the parser's leaf ``0x10227c60``, not read from the file — and is what
    ``keepMidPtLut`` actually interpolates with.  See ``DRA_TTC_SLOPE_LEAF``.
    """

    name: str
    x: list[float] = field(default_factory=list)
    y: list[float] = field(default_factory=list)
    slope: list[float] = field(default_factory=list)

    @property
    def n_points(self) -> int:
        return len(self.x)

    @property
    def is_identity(self) -> bool:
        return all(a == b for a, b in zip(self.x, self.y))


def _f32(v: float) -> float:
    return struct.unpack("<f", struct.pack("<f", v))[0]


def build_ttc_slopes(x: list[float], y: list[float]) -> list[float]:
    """``0x10227e93``..``0x10227eab`` — the per-segment finite-difference
    slope the ``.ttc`` parser leaf (``0x10227c60``) computes alongside each
    point, one segment behind the point just read.  Float32 in, float32 out,
    intermediate division at the Windows CRT's 53-bit x87 precision (matches
    Python ``float`` under the project's usual FPCW=0x027f convention).
    """
    if not DRA_TTC_SLOPE_PORTED:
        _unported("DRA_TTC_SLOPE_PORTED", DRA_TTC_SLOPE_LEAF,
                  ".ttc parser's slope computation")
    n = len(x)
    slopes = [0.0] * max(n - 1, 0)
    for i in range(n - 1):
        dy = _f32(y[i + 1]) - _f32(y[i])
        dx = _f32(x[i + 1]) - _f32(x[i])
        slopes[i] = _f32(dy / dx)
    return slopes


def parse_ttc(path: Path) -> DraTtc:
    """Parse a ``.ttc``: ``#`` comments, then whitespace-separated ``x y``.

    The shipped files end with a ``10 10`` sentinel far outside the [0,1]
    domain — an extrapolation guard, kept verbatim, not stripped.  The
    ``slope`` array is derived, not parsed — see ``build_ttc_slopes``.
    """
    if not DRA_TTC_PARSE_PORTED:
        _unported("DRA_TTC_PARSE_PORTED", DRA_PARSE_DPI, ".ttc parsing")
    curve = DraTtc(name=path.name)
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        curve.x.append(_f32(float(parts[0])))
        curve.y.append(_f32(float(parts[1])))
    if curve.n_points > TTC_MAX_POINTS:
        raise DraError(
            f"{path.name}: {curve.n_points} points exceeds the "
            f"{TTC_MAX_POINTS}-point block ({TTC_ARRAY_BYTES} B) the params "
            f"object reserves")
    curve.slope = build_ttc_slopes(curve.x, curve.y)
    return curve


# ---------------------------------------------------------------------------
# the .dpi per-line body — 0x102283d5..0x10228965
#
# The CRT's own ``sscanf`` is what does the tokenising and every numeric
# conversion here (``call ebx`` at 0x1022841e and at each key's arm; ``ebx``
# is loaded with the ``MSVCR71!sscanf`` import once, outside the loop).  The
# helpers below reproduce sscanf's semantics for exactly the five conversion
# specifiers this function uses, because the DIFFERENCE between them and a
# naive ``str.split`` is observable and real — see ``parse_dpi_line``.
# ---------------------------------------------------------------------------

#: The five format strings ``0x102283a0`` passes to ``sscanf``, by .rdata VA.
DPI_FMT_KV = 0x105858AC        # "%s = %s"   — 0x10228418
DPI_FMT_I16 = 0x10576D70       # "%hd"       — 0x1022844b et al
DPI_FMT_I32 = 0x10582F8C       # "%ld"       — 0x10228594
DPI_FMT_F32 = 0x1058A580       # "%f"        — 0x10228536 et al
DPI_FMT_CHAR = 0x10593964      # "%c"        — 0x102285c4 / 0x10228666 /
                               #               0x102286aa (the three bools)

#: ``strstr(key, "TTC")`` at ``0x102287f2`` — the gate on the whole curve
#: branch.  A key with no ``"TTC"`` substring falls straight to the loop
#: bottom (``je 0x10228965``) and is a silent no-op.
DPI_TTC_MARKER = "TTC"

_C_WS = " \t\n\r\v\f"


def _sscanf_token(s: str, i: int) -> tuple[str | None, int]:
    """One ``%s``: skip leading whitespace, then take up to the next.

    Returns ``(None, i)`` when the input is exhausted first — i.e. the
    conversion FAILS and sscanf stops, which is what makes the surrounding
    ``cmp eax,2`` at ``0x10228423`` reject the line.
    """
    while i < len(s) and s[i] in _C_WS:
        i += 1
    start = i
    while i < len(s) and s[i] not in _C_WS:
        i += 1
    if i == start:
        return None, i
    return s[start:i], i


def sscanf_kv(line: str) -> tuple[str, str] | None:
    """``sscanf(line, "%s = %s", key, value)``, returning ``None`` unless it
    reports exactly the 2 conversions ``0x10228423`` demands.

    The literal ``'='`` in the format has to MATCH A REAL ``'='`` in the
    input, and the two ``%s`` are whitespace-delimited, so a ``key=value``
    line with no spaces is **rejected outright** by the real DLL: the first
    ``%s`` swallows ``"key=value"`` whole, the format then wants ``'='`` and
    the input is exhausted, so sscanf returns 1 and the line is silently
    skipped.  A naive ``line.split("=", 1)`` accepts it — a real divergence,
    Unicorn-confirmed in ``check_parse_dpi``.
    """
    key, i = _sscanf_token(line, 0)
    if key is None:
        return None
    while i < len(line) and line[i] in _C_WS:
        i += 1
    if i >= len(line) or line[i] != "=":
        return None
    i += 1
    val, _ = _sscanf_token(line, i)
    if val is None:
        return None
    return key, val


def _sscanf_int(tok: str, bits: int) -> int | None:
    """``%hd`` / ``%ld``: an optional sign then a maximal digit run.

    Trailing junk is ignored (``"4095abc"`` converts to 4095) and a token
    with no digits at all fails, leaving the destination field UNWRITTEN —
    modelled here by returning ``None`` and by the caller not storing.
    """
    i = 0
    if i < len(tok) and tok[i] in "+-":
        i += 1
    d0 = i
    while i < len(tok) and tok[i].isdigit():
        i += 1
    if i == d0:
        return None
    v = int(tok[:i])
    if bits == 16:
        return _s16(v & 0xFFFF)
    return _s32(v & 0xFFFFFFFF)


def _sscanf_float(tok: str) -> float | None:
    """``%f``: sign, digits/point, optional exponent; narrowed to float32
    because the destination is a ``float``, not a ``double``."""
    i = 0
    if i < len(tok) and tok[i] in "+-":
        i += 1
    d0 = i
    while i < len(tok) and (tok[i].isdigit() or tok[i] == "."):
        i += 1
    if i < len(tok) and tok[i] in "eE":
        j = i + 1
        if j < len(tok) and tok[j] in "+-":
            j += 1
        k = j
        while k < len(tok) and tok[k].isdigit():
            k += 1
        if k > j:
            i = k
    if i == d0:
        return None
    try:
        return _f32(float(tok[:i]))
    except ValueError:
        return None


def _sscanf_bool(tok: str) -> bool | None:
    """The three bools, ``0x102285b8``..``0x102285e0`` and its two twins.

    NOT ``strcmp(value, "true")`` — this file used to say that and it was
    **wrong**.  The DLL does ``sscanf(value, "%c", &c)`` and then
    ``cmp byte, 0x74 ; sete`` — a single lowercase ``'t'`` on the FIRST
    character.  So ``"true"``, ``"t"`` and ``"tomato"`` are all TRUE while
    ``"True"`` and ``"TRUE"`` are FALSE.  Confirmed bit-exact against the
    real bytes in ``check_parse_dpi``, not read off the disassembly alone.
    """
    if not tok:
        return None
    return tok[0] == "t"


#: scalar key -> (generateLut-relative offset, kind), in the DLL's own test
#: order.  Derived from DRA_PARAMS_LAYOUT so the two cannot drift.
_DPI_SCALARS: dict[str, tuple[int, str]] = {
    k: (off, kind) for k, off, kind in DRA_PARAMS_LAYOUT if kind != "ttc"
}
_DPI_TTC_KEYS: tuple[str, ...] = tuple(
    k for k, _off, kind in DRA_PARAMS_LAYOUT if kind == "ttc")


def parse_dpi_line(line: str, values: dict) -> None:
    """``0x102283d5``..``0x10228965`` — the parser's whole per-line body.

    Mutates ``values`` in place.  A key whose conversion fails, or whose line
    is rejected, leaves ``values`` untouched, exactly as the DLL leaves the
    params field unwritten.

    1. ``0x102283d5``..``0x102283fe`` — reject the line outright if its
       **first** character is ``'#'``, ``'*'``, CR, LF or NUL.  Note this is
       a first-character test only: it is *not* "strip everything after a
       ``#``", which is what this port used to do.  A leading-whitespace
       comment (``"  # x"``) is therefore NOT caught here — it is caught one
       step later, by the 2-conversion requirement.
    2. ``0x10228404``..``0x10228426`` — ``sscanf(line, "%s = %s", …)``,
       requiring exactly 2 (see ``sscanf_kv``).
    3. ``0x1022842c``..``0x102287e3`` — a ``repe cmpsb`` chain over the 19
       scalar keys, each arm re-invoking ``sscanf`` on the *value* with that
       key's own format and destination offset.
    4. ``0x102287e8``..``0x102287fd`` — anything unmatched is passed to
       ``strstr(key, "TTC")``; no match means the line is a silent no-op.
    """
    if not DRA_DPI_PARSE_PORTED:
        _unported("DRA_DPI_PARSE_PORTED", DRA_PARSE_DPI, ".dpi parsing")
    if not line or line[0] in "#*\r\n\0":
        return
    kv = sscanf_kv(line)
    if kv is None:
        return
    key, val = kv
    ent = _DPI_SCALARS.get(key)
    if ent is not None:
        _off, kind = ent
        if kind == "i16":
            v = _sscanf_int(val, 16)
        elif kind == "i32":
            v = _sscanf_int(val, 32)
        elif kind == "f32":
            v = _sscanf_float(val)
        else:
            v = _sscanf_bool(val)
        if v is not None:
            values[key] = v
        return
    if DPI_TTC_MARKER not in key:
        return
    if key in _DPI_TTC_KEYS:
        values[key] = val


def parse_dpi(path: Path) -> dict[str, object]:
    """``ansel-dra-default-default.dpi`` -> the typed params dict.

    Runs ``parse_dpi_line`` over every line, in file order, so a repeated key
    legitimately wins last — the DLL has no "already seen" guard.

    Scalars come back already converted to their destination C type (``int``
    for ``%hd``/``%ld``, float32-narrowed ``float`` for ``%f``, ``bool`` for
    the three ``%c`` fields); the six ``*TTC`` keys come back as the raw
    filename token, which the caller resolves against the ``.dpi``'s own
    directory — the DLL does exactly that at ``0x102288bf``..``0x1022894b``:
    ``dpiPath.rfind('\\\\')``, then ``substr(0, idx+1) + value``.  (If the
    ``.dpi`` path contains **no** backslash at all, ``rfind`` returns
    ``npos`` and ``0x102288ea`` jumps *past* the ``0x10227c60`` call — the
    curve is silently never loaded.  Not reachable here, where paths are
    always absolute, but it is the DLL's real behaviour.)

    Note this file carries **no** ``key =`` line, so the repo's key-indexed
    resolvers cannot find it — it is opened by path, like ``cna``'s.
    """
    if not DRA_DPI_PARSE_PORTED:
        _unported("DRA_DPI_PARSE_PORTED", DRA_PARSE_DPI, ".dpi parsing")
    out: dict[str, object] = {}
    for line in path.read_text().splitlines():
        parse_dpi_line(line, out)
    return out


@dataclass
class DraParams:
    """The parsed params object, laid out as ``DRA_PARAMS_LAYOUT``."""

    values: dict[str, object] = field(default_factory=dict)
    curves: dict[str, DraTtc] = field(default_factory=dict)

    def __getitem__(self, key: str):
        return self.values[key]

    @classmethod
    def load(cls, dra_dir: Path,
             dpi_name: str = "ansel-dra-default-default.dpi") -> "DraParams":
        raw = parse_dpi(dra_dir / dpi_name)
        p = cls()
        for key, _off, kind in DRA_PARAMS_LAYOUT:
            if key not in raw:
                continue
            v = raw[key]
            if kind == "ttc":
                # 0x102288bf..0x1022894b: the .ttc is resolved against the
                # .dpi's OWN directory, which is dra_dir here.
                p.values[key] = v
                p.curves[key] = parse_ttc(dra_dir / str(v))
            else:
                # Already converted by parse_dpi_line, through the same
                # sscanf specifier the DLL's own arm uses.
                p.values[key] = v
        return p

    def curve_pair(self, lighting: int) -> tuple[DraTtc, DraTtc]:
        """The (low, high) curve pair ``keepMidPtLut`` selects."""
        lo_key, hi_key = lighting_curve_keys(lighting)
        return self.curves[lo_key], self.curves[hi_key]


# ---------------------------------------------------------------------------
# AnsDraResults — 0x3c B at impl+0x1c88, getter 0x10130390 (0xf dwords)
#
# Phase 1 proved the size and named nSmallBins/nLargeBins/nLumPixels/
# nEdgePixels/lumMin/lumMax/edgeMin/edgeMax/effMin/effMax/DraLut from the
# vendor dumper 0x1013003c. Every previously-unnamed slot below is confirmed
# here by its use inside generateLut, which is why the two agree exactly.
# ---------------------------------------------------------------------------

DRA_RESULTS_IMPL_OFFSET = 0x1C88
DRA_RESULTS_SIZE = 0x3C

DRA_RESULTS_LAYOUT: tuple[tuple[int, int, str, str], ...] = (
    # (struct off, impl VA off, name, evidence)
    (0x00, 0x1C88, "nSmallBins", "loop bound in generateLut 0x1022abd8"),
    (0x04, 0x1C8C, "LumHist", "rep movsd target 0x1022b87b (variant B)"),
    (0x08, 0x1C90, "EdgeHist", "rep movsd target 0x1022b88d (variant B)"),
    (0x0C, 0x1C94, "nLargeBins", "rebin count, tested 0x1022ac32"),
    (0x10, 0x1C98, "nLumPixels", "running total 0x1022ac52"),
    (0x14, 0x1C9C, "LumLargeHist", "rebin dst 0x1022ab7b/0x1022ac12"),
    (0x18, 0x1CA0, "LumCumHist", "cumulative dst 0x1022ac5e"),
    (0x1C, 0x1CA4, "nEdgePixels", "running total 0x1022ad6c"),
    (0x20, 0x1CA8, "EdgeLargeHist", "rebin dst 0x1022ab87/0x1022ad30"),
    (0x24, 0x1CAC, "EdgeCumHist", "cumulative dst 0x1022ad72"),
    (0x28, 0x1CB0, "Scratch", "remap accumulator 0x1022abb5; compose 0x1022bb13"),
    (0x2C, 0x1CB4, "lumMin", "0x10228bc0 out 0x1022ac70"),
    (0x2E, 0x1CB6, "lumMax", "0x10228bc0 out 0x1022ac69"),
    (0x30, 0x1CB8, "edgeMin", "0x10228bc0 out 0x1022ad8e"),
    (0x32, 0x1CBA, "edgeMax", "0x10228bc0 out 0x1022ad87"),
    (0x34, 0x1CBC, "effMin", "0x10228cd0 out / 0x1022add7"),
    (0x36, 0x1CBE, "effMax", "0x10228cd0 out / 0x1022adde"),
    (0x38, 0x1CC0, "DraLut", "freed 0x1022b098; composed 0x1022bb19"),
)

DRA_RESULTS_OFFSET_BY_NAME = {n: o for o, _v, n, _e in DRA_RESULTS_LAYOUT}


def results_offset(name: str) -> int:
    """Offset of a named ``AnsDraResults`` field, or raise."""
    if not DRA_RESULTS_LAYOUT_PORTED:
        _unported("DRA_RESULTS_LAYOUT_PORTED", DRA_GET_RESULTS_IMPL,
                  "AnsDraResults layout")
    return DRA_RESULTS_OFFSET_BY_NAME[name]


# ---------------------------------------------------------------------------
# the ported leaves
# ---------------------------------------------------------------------------

_I32 = 0xFFFFFFFF


def _s32(v: int) -> int:
    v &= _I32
    return v - (1 << 32) if v & 0x80000000 else v


def _s16(v: int) -> int:
    v &= 0xFFFF
    return v - (1 << 16) if v & 0x8000 else v


def _idiv(a: int, b: int) -> int:
    """x86 ``idiv`` — truncation toward zero, not Python floor."""
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def lum_histogram(pixels: bytes, n_pixels: int, n_bins: int) -> list[int]:
    """Variant A's own luminance histogram — ``0x1022b191``..``0x1022b1d4``.

    ``pixels`` is interleaved ``int16`` R,G,B (6 bytes per pixel), the buffer
    at ``imageData+0x20``; ``n_pixels`` is ``imageData[+0x0c] *
    imageData[+0x10]``.  The histogram is ``rep stosd``-zeroed to ``n_bins``
    dwords first (``0x1022b191``).

    The bin is ``(R + G + B + 1) / 3`` where the ``+1`` is the literal ``inc
    ecx`` at ``0x1022b1ae``, the divide is the ``0x55555556`` magic-multiply
    at ``0x1022b1b6`` (i.e. signed truncation toward zero, **not** floor), and
    the quotient is narrowed through ``movsx edx, cx`` at ``0x1022b1c4``
    before indexing — a 16-bit wrap that this port reproduces.
    """
    if not DRA_LUM_HISTOGRAM_PORTED:
        _unported("DRA_LUM_HISTOGRAM_PORTED", DRA_ANALYZE_IMAGE,
                  "variant A's luminance histogram")
    hist = [0] * n_bins
    off = 0
    for _ in range(n_pixels):
        r, g, b = struct.unpack_from("<hhh", pixels, off)
        off += 6
        idx = _s16(_idiv(r + g + b + 1, 3))
        hist[idx] += 1
    return hist


def compose_tone(dra_lut: list[int], tone_lut: list[int],
                 n: int) -> list[int]:
    """Variant B's compose block — ``0x1022bb0f``..``0x1022bb50``.

    ``memcpy(scratch, draLut, n*2)`` then ``draLut[i] = scratch[toneLut[i]]``,
    i.e. ``out = draCurve o toneLut``.  Both are ``int16``; the index is
    ``movsx``-widened at ``0x1022bb41``.  Variant A has no equivalent block —
    this is the single behavioural difference between the two overloads.
    """
    if not DRA_COMPOSE_TONE_PORTED:
        _unported("DRA_COMPOSE_TONE_PORTED", DRA_ANALYZE_HIST,
                  "variant B's tone composition")
    scratch = list(dra_lut)
    out = list(dra_lut)
    for i in range(n):
        out[i] = scratch[_s16(tone_lut[i])]
    return out


def rebin(small: list[int], n_small: int, bin_factor: int) -> list[int]:
    """``0x10228e00`` — sum every ``bin_factor`` small bins into a large bin.

    ``nLarge = nSmall / binFactor`` (x86 ``idiv``, ``0x10228e04``); each output
    is the plain sum of ``binFactor`` consecutive inputs.  A ``binFactor`` of
    1 or less short-circuits the inner loop (``cmp esi,1; jle`` at
    ``0x10228e15``), copying one input per output.
    """
    if not DRA_REBIN_PORTED:
        _unported("DRA_REBIN_PORTED", DRA_REBIN, "small->large rebin")
    n_large = _idiv(n_small, bin_factor)
    out: list[int] = []
    src = 0
    for _ in range(max(n_large, 0)):
        acc = small[src]
        src += 1
        if bin_factor > 1:
            for _ in range(bin_factor - 1):
                acc = _s32(acc + small[src])
                src += 1
        out.append(_s32(acc))
    return out


def _ftol_round(x: float) -> int:
    """``fadd 0.5`` then ``0x104ffe44`` (``__ftol``) — truncate after biasing.

    Not ``round()``: the DLL adds the ``0x10574f40`` 0.5 in **double**
    precision and then truncates toward zero, so negatives bias the other way.
    """
    return int(x + F64_HALF)


def cum_bounds(cum_hist: list[int], large_hist: list[int], n_large: int,
               total: int, params: dict) -> tuple[int, int]:
    """``0x10228bc0`` — cumulative-percentile min/max, in small-bin units.

    Four thresholds are formed as ``ftol(total * p * 0.01 + 0.5)`` with ``p``
    read from ``params+0x30``/``+0x34``/``+0x38``/``+0x3c``
    (``startingMinCumPoint``, ``cumPctBelowMin``, ``startingMaxCumPoint``,
    ``cumPctAboveMax``) and the ``0.01`` being ``0x1059f5f0``.

    The min scan walks the cumulative histogram up to the first bin at or
    above the 1st threshold, then walks **back** while any of the three
    trailing raw large-bin counts still exceeds the 2nd; the max scan is its
    mirror.  Both indices are finally multiplied by ``binFactor``
    (``imul dx, cx`` against ``[edi+0x14]`` at ``0x10228c65``/``0x10228cb2``)
    to return to small-bin units.
    """
    if not DRA_CUM_BOUNDS_PORTED:
        _unported("DRA_CUM_BOUNDS_PORTED", DRA_CUM_BOUNDS,
                  "cumulative-percentile bounds")
    t = float(total)
    a = _ftol_round(t * params["startingMinCumPoint"] * F32_PERCENT)
    b = _ftol_round(t * params["cumPctBelowMin"] * F32_PERCENT)
    c = _ftol_round(t * params["startingMaxCumPoint"] * F32_PERCENT)
    d = _ftol_round(t * params["cumPctAboveMax"] * F32_PERCENT)
    bin_factor = int(params["binFactor"])

    # --- min side, 0x10228c27..0x10228c5d ---------------------------------
    ecx = 0
    if cum_hist[0] < a:
        while True:
            ecx += 1
            if cum_hist[ecx] >= a:
                break
        if ecx > 2:
            while ecx > 2:
                if (large_hist[ecx] > b or large_hist[ecx - 1] > b
                        or large_hist[ecx - 2] > b):
                    ecx -= 1
                else:
                    break
    lo = _s16(bin_factor * ecx)

    # --- max side, 0x10228c70..0x10228cb2 ---------------------------------
    ecx = n_large - 1
    if cum_hist[n_large - 1] > c:
        while True:
            ecx -= 1
            if cum_hist[ecx] <= c:
                break
    limit = n_large - 3
    if ecx < limit:
        while ecx < limit:
            if (large_hist[ecx] > d or large_hist[ecx - 1] > d
                    or large_hist[ecx - 2] > d):
                ecx += 1
            else:
                break
    hi = _s16(bin_factor * ecx)
    return lo, hi


def eff_bounds(lum_min: int, lum_max: int, edge_min: int, edge_max: int,
              paper_min: int, paper_max: int, lum_weighting: float,
              edge_weighting: float, do_average: bool) -> tuple[int, int]:
    """``0x10228cd0`` — lum/edge histograms' bounds -> the effective bounds.

    Two independent branches on ``params.bDoAverage`` (``eax+0x18``); the
    shipped ``.dpi`` sets it ``true``, so the weighted-blend branch below is
    the *live* one, but both are ported and Unicorn-verified.

    ``bDoAverage == false`` (``0x10228d01``..``0x10228d33``) — plain
    clamped min/max, no weighting::

        effMin = max(min(lumMin, edgeMin), paperMin)
        effMax = min(max(lumMax, edgeMax), paperMax)

    ``bDoAverage == true`` (``0x10228d34``..``0x10228dfe``, LIVE) — a
    weighted blend of the two bounds, with a special case when the paper
    bound lies *between* them (``imul`` sign test at ``0x10228d49``/
    ``0x10228da9``: product of the two paper-relative offsets)::

        # MIN: the smaller of (a, b) keeps its own weight; paperMin borrows
        # the other's weight.
        a, b, p = lumMin, edgeMin, paperMin
        if (a - p) * (b - p) >= 0:          # p not between a and b
            effMin = ftol(a * lumWeighting + b * edgeWeighting + 0.5)
        elif a < b:
            effMin = ftol(a * lumWeighting + p * edgeWeighting + 0.5)
        else:
            effMin = ftol(b * edgeWeighting + p * lumWeighting + 0.5)

        # MAX: the LARGER of (a, b) keeps its own weight -- the opposite of
        # MIN's split, confirmed by Unicorn, not assumed symmetric.
        a, b, p = lumMax, edgeMax, paperMax
        if (a - p) * (b - p) >= 0:
            effMax = ftol(a * lumWeighting + b * edgeWeighting + 0.5)
        elif a < b:
            effMax = ftol(b * edgeWeighting + p * lumWeighting + 0.5)
        else:
            effMax = ftol(a * lumWeighting + p * edgeWeighting + 0.5)

    Both ``ftol``-rounded results are then narrowed to int16 (``movsx ax``,
    ``0x10228d98``/``0x10228dec`` region).
    """
    if not DRA_EFF_BOUNDS_PORTED:
        _unported("DRA_EFF_BOUNDS_PORTED", DRA_EFF_BOUNDS,
                  "effective min/max bounds")
    lum_min, lum_max = _s16(lum_min), _s16(lum_max)
    edge_min, edge_max = _s16(edge_min), _s16(edge_max)
    paper_min, paper_max = _s16(paper_min), _s16(paper_max)

    if not do_average:
        eff_min = max(min(lum_min, edge_min), paper_min)
        eff_max = min(max(lum_max, edge_max), paper_max)
        return _s16(eff_min), _s16(eff_max)

    # NOTE the min/max asymmetry, confirmed by Unicorn (not assumed): for the
    # min blend, whichever of (a, b) is SMALLER keeps its own weight and
    # paperMin borrows the other weight (0x10228d59..0x10228d7f); for the max
    # blend it is the LARGER of (a, b) that keeps its own weight
    # (0x10228db9..0x10228ddf) -- i.e. the branch condition is the same
    # ``a < b`` shape both times, but which term gets which weight flips.
    def _blend(a: int, b: int, p: int, *, larger_keeps_own: bool) -> int:
        if (a - p) * (b - p) >= 0:
            r = a * lum_weighting + b * edge_weighting
        elif a < b:
            r = (b * edge_weighting + p * lum_weighting) if larger_keeps_own \
                else (a * lum_weighting + p * edge_weighting)
        else:
            r = (a * lum_weighting + p * edge_weighting) if larger_keeps_own \
                else (b * edge_weighting + p * lum_weighting)
        return _s16(_ftol_round(r))

    eff_min = _blend(lum_min, edge_min, paper_min, larger_keeps_own=False)
    eff_max = _blend(lum_max, edge_max, paper_max, larger_keeps_own=True)
    return eff_min, eff_max


def keep_midpt_lut(lighting: int, low: "DraTtc", high: "DraTtc",
                   max_value: int, low_fixed_point: int, high_fixed_point: int,
                   paper_min: int, paper_max: int, flash_fraction: float,
                   eff_min: int, eff_max: int) -> list[int]:
    """``0x102290b0`` — the curve-construction body of ``keepMidPtLut``.

    Builds the ``[0, maxValue]`` output LUT from the (already-dispatched, see
    ``lighting_curve_keys``) low/high tone-transfer curves.  Three regions:

    * **High** (indices ``highFixedPoint+1`` .. ``maxValue``, inclusive):
      while the index is below an ``effMax``-derived bound (``hiBound``, ==
      ``effMax`` unadjusted, or the Frontlit-only (``lighting == 2``)
      ``flashFraction``-adjusted ``effMax`` when ``effMax > paperMax`` --
      ``0x10229234``..``0x1022925e``), it is linearly mapped to a fraction of
      ``effMax - highFixedPoint`` (or the adjusted equivalent), looked up by
      linear scan against ``high.x``/``high.slope`` (clamped flat beyond the
      curve's own domain), scaled and re-based at ``highFixedPoint``
      (``0x1022933e``..``0x10229353``).  Once the index reaches ``hiBound``
      the loop *keeps running* to ``maxValue`` but switches to plain linear
      extrapolation (``eax = edi``, an affine function of the index) instead
      of curve lookup — this is not a one-off boundary write, it is a
      per-iteration branch inside the same loop (confirmed by Unicorn
      register tracing across many iterations of ``0x10229358``, correcting
      an earlier reading that treated it as executing once).
    * **Low** (indices ``lowFixedPoint - 1`` down to 0): the mirror
      computation against ``low.x``/``low.slope`` and ``effMin``/
      ``paperMin``, and below ``effMin`` a plain ramp — re-reading the
      already-written neighbour above and subtracting 1 — in place of curve
      lookup (``0x10229480``).  There is **no** neighbour-relative
      monotonicity clamp here (an earlier reading invented one from a
      register that turned out, via live tracing, to be a stale ``maxValue``
      constant held over the whole loop, not a per-iteration comparison).
    * **Midpoint band** ``[lowFixedPoint, highFixedPoint]``: always filled
      with the identity, unconditionally, after the high-side loop finishes
      or is skipped for lack of room (``0x1022938a``/``0x1022938e`` is a
      fallthrough, not an "else" of the high loop) — this is what the
      function's name means: the midpoint is *kept* as-is.

    Both the high and low sides finish with the same two-sided clamp to
    ``[0, maxValue]`` (``0x1022935a``../``0x10229473``..; see
    ``two_sided_clamp`` below) — not the asymmetric "write raw on overflow"
    behaviour an earlier reading assumed.

    x87 control word matters here: the FPU intermediates (interpolation
    fraction, the weighted blend of low/high segment position) are computed
    at the Windows CRT's 53-bit precision.  Python ``float`` already models
    that; the ``_f32``-narrowing after every value that the DLL stores back
    through an ``fstp dword`` is what keeps this port aligned with it.
    """
    if not DRA_KEEP_MIDPT_LUT_PORTED:
        _unported("DRA_KEEP_MIDPT_LUT_PORTED", DRA_KEEP_MIDPT_LUT,
                  "keepMidPtLut curve construction")
    max_value = _s16(max_value)
    low_fp = _s16(low_fixed_point)
    high_fp = _s16(high_fixed_point)
    paper_min = _s16(paper_min)
    paper_max = _s16(paper_max)
    eff_min = _s16(eff_min)
    eff_max = _s16(eff_max)

    out = [0] * (max_value + 2)   # +1 slack: the boundary write can land on
                                   # esi==max_value+1 in edge cases; sliced
                                   # back to max_value+1 entries on return.

    def clamp0(v: int) -> int:
        return v if v >= 0 else 0

    def search(curve: "DraTtc", t: float) -> float:
        """The linear scan + clamp/interpolate, ``0x102292c4``..``0x1022933a``
        (and its low-side mirror ``0x102293e6``..``0x1022945a``)."""
        n = curve.n_points
        x, y, sl = curve.x, curve.y, curve.slope
        if n == 0:
            return 0.0
        if t < x[0]:
            return y[0]
        if t > x[n - 1]:
            return y[n - 1]
        if n <= 1:
            return y[0]
        i = 1
        while i < n:
            if not (t < x[i - 1]) and t <= x[i]:
                return y[i - 1] + sl[i - 1] * (t - x[i - 1])
            i += 1
        return y[n - 1]

    # ---- high side, 0x1022920a..0x10229384 --------------------------------
    hi_gap_base = _s32(eff_max - high_fp)          # 0x102291ed / 0x1022920x
    eff_max_adj, paper_max_adj = eff_max, paper_max
    denom = float(hi_gap_base)
    # 0x10229232: when effMax<=paperMax (no clamp needed), S(0x40) -- the
    # multiplier the final fmul uses -- stays effMax-highFP, i.e. IDENTICAL
    # to the fraction's own denominator (0x10229271: `mov [esp+0x40],esi`).
    # Only in the clamp-needed branch does it become paperMax(Adj)-highFP
    # (0x10229262..0x1022926d), confirmed by Unicorn (an identity curve with
    # effMax<paperMax must reproduce an identity LUT, which only holds when
    # gap==denom here).
    hi_gap = hi_gap_base
    hi_rebase = eff_max     # what "edx" is at the 0x10229275 merge point --
                            # feeds the loop-exhausted boundary write below.
    if eff_max > paper_max:
        adj = _ftol_round(float(hi_gap_base) * flash_fraction)
        if lighting == 2:
            eff_max_adj = _s16(_s32(eff_max - adj))
            paper_max_adj = _s16(_s32(paper_max - adj))
            denom = _f32(float(hi_gap_base) - float(adj))
        hi_gap = _s32(paper_max_adj - high_fp)
        hi_rebase = paper_max_adj
    hi_bound = eff_max_adj

    def two_sided_clamp(val: int) -> int:
        # 0x1022935a..0x10229384 (high) / 0x10229473..0x102294a5 (low):
        # `cmp eax, maxValue; jg/jle` branches to either write the STALE
        # `ecx` (which was loaded as maxValue and never reassigned along the
        # overflow path) or, on the non-overflow path, the branchless
        # ``max(val, 0)`` pattern (`setl`/`dec`/`and`).  A plain two-sided
        # clamp to ``[0, maxValue]`` -- corrected from an earlier reading
        # that had the overflow arm backwards (thought it wrote `val`
        # unclamped) and, on the low side, invented a neighbour-based
        # "monotonicity" that Unicorn register tracing disproved: `ecx`
        # there is the SAME stale maxValue constant the whole loop, not a
        # per-iteration comparison against the neighbour.
        return max_value if val > max_value else clamp0(val)

    # 0x10229285 `jg 0x1022938e` only skips the whole loop below when there
    # is no room at all; either way, execution FALLS THROUGH into the
    # identity-fill of [lowFixedPoint, highFixedPoint] further down
    # (0x1022938a/0x1022938e is reached both by that jg AND by simply
    # running off the bottom of the loop at 0x10229384) -- it is not an
    # "else" of the loop, it is unconditional.  This is what the function's
    # name means: the midpoint band between the two fixed points is always
    # kept as the identity, regardless of whether the high/low curves had
    # room to run.
    #
    # The loop itself runs esi from highFixedPoint+1 to maxValue INCLUSIVE
    # (0x1022937e/0x10229384: `cmp esi, maxValue; jle top`) -- NOT just up to
    # hiBound as the earlier reading of the "eax=edi" block assumed.  Inside
    # each iteration there is a SECOND, inner check (0x102292b0: `cmp esi,
    # hiBound; jge`) that switches from real curve interpolation to a plain
    # linear extrapolation once esi reaches hiBound, using the same "edi"
    # value the earlier (wrong) reading thought was a one-off boundary case:
    # edi tracks (esi - effMaxAdj + hiRebase) in lockstep with esi from setup
    # onward, so it is simply that affine function evaluated at the current
    # esi, every iteration, once esi >= hiBound.  Confirmed by Unicorn
    # register tracing (0x102292a6 hit repeatedly, and 0x10229358 hit once
    # per esi >= hiBound, not once total) -- not the original static read.
    idx0 = high_fp + 1
    if idx0 <= max_value:
        num = 1
        esi = idx0
        while esi <= max_value:
            if esi < hi_bound:
                t = _f32(float(num) / denom) if denom != 0 else 0.0
                y = search(high, t)
                val = _ftol_round(y * hi_gap + high_fp)
            else:
                val = esi - eff_max_adj + hi_rebase
            out[esi] = _s16(two_sided_clamp(_s16(val)))
            esi += 1
            num += 1

    if low_fp <= high_fp:
        for v in range(low_fp, high_fp + 1):
            out[v] = _s16(v)

    # ---- low side, 0x102293ad..0x102294b7 ----------------------------------
    # 0x102291de/0x1022920a: loGap uses max(effMin,paperMin) for the FINAL
    # rebase (S(0x48)) but the fraction's own denominator/numerator
    # (S(0x58)/S(0x2c), set at 0x102293b4-0x102293c4) use plain effMin,
    # unclamped by paperMin -- an asymmetry with the high side's own
    # adj-vs-unadjusted split, confirmed by the raw esp-offsets, not assumed.
    lo_gap = _s32(low_fp - max(eff_min, paper_min))
    denom_lo = _f32(float(_s32(low_fp - eff_min)))
    esi = low_fp - 1
    while esi >= 0:
        if esi >= eff_min:
            num = _s32(esi - eff_min)
            t = _f32(float(num) / denom_lo) if denom_lo != 0 else 0.0
            y = search(low, t)
            newv = _s16(_ftol_round(y * lo_gap + max(eff_min, paper_min)))
        else:
            # 0x10229480 -- below effMin: stop interpolating, ramp the
            # already-written neighbour above down by 1 per step (a fresh
            # re-read of outLut[esi+1], not a cached register).
            neighbour_raw = out[esi + 1] if esi + 1 <= max_value else 0
            newv = _s16(neighbour_raw - 1)
        out[esi] = _s16(two_sided_clamp(newv))
        esi -= 1

    return out[:max_value + 1]


# ---------------------------------------------------------------------------
# validate_params — 0x10228e40
# ---------------------------------------------------------------------------

#: ``(field, bad-index)`` in the exact order ``0x10228e40`` checks them.
#: Every bound is INCLUSIVE on both ends (empirically confirmed: boundary
#: values pass) -- see ``check_validate_params`` for the calibration table
#: this was read off, not guessed from the x87 comparison bytes.
VALIDATE_BAD_MAX_VALUE = 1
VALIDATE_BAD_LOW_FP = 2
VALIDATE_BAD_HIGH_FP = 3
VALIDATE_BAD_PAPER = 4
VALIDATE_BAD_SLOPE = 6
VALIDATE_BAD_BIN_FACTOR = 8
VALIDATE_BAD_WEIGHTS = 10
VALIDATE_BAD_FLASH_FRACTION = 14
VALIDATE_BAD_BACKLIT_FRACTION = 15
VALIDATE_BAD_STARTING_MIN_CUM = 16
VALIDATE_BAD_CUM_BELOW_MIN = 17
VALIDATE_BAD_STARTING_MAX_CUM = 18
VALIDATE_BAD_CUM_ABOVE_MAX = 19


def validate_params(p: "DraParams") -> int:
    """``0x10228e40`` — ``0`` if valid, else the 1-based bad-parameter index.

    Field-by-field bounds, in check order (all inclusive both ends; not
    hand-decoded from x87 comparison flags but read off the real DLL --
    see ``check_validate_params``)::

        1  maxValue > 0
        2  0 <= lowFixedPoint <= maxValue
        3  lowFixedPoint <= highFixedPoint <= maxValue
        4  0 <= paperMin <= paperMax <= maxValue
        6  0 <= minSlope <= maxSlope
        8  binFactor >= 1 and (maxValue + 1) % binFactor == 0
        10 lumWeighting + edgeWeighting == 1.0 (exact)
        14 0 <= flashFraction <= 1
        15 0 <= backlitFraction <= 1
        16 0 <= startingMinCumPoint <= 50
        17 0 <= cumPctBelowMin <= 25
        18 50 <= startingMaxCumPoint <= 100
        19 0 <= cumPctAboveMax <= 25

    Codes 5, 7, 9, 11-13 are never produced by this function -- gaps in the
    DLL's own numbering, not a port omission (confirmed: the calibration
    sweep never lands on them either).
    """
    if not DRA_VALIDATE_PARAMS_PORTED:
        _unported("DRA_VALIDATE_PARAMS_PORTED", DRA_VALIDATE_PARAMS,
                  "AnsDraCapabilityImpl parameter validation")
    max_value = _s16(int(p["maxValue"]))
    if not (max_value > 0):
        return VALIDATE_BAD_MAX_VALUE
    low_fp = _s16(int(p["lowFixedPoint"]))
    if not (0 <= low_fp <= max_value):
        return VALIDATE_BAD_LOW_FP
    high_fp = _s16(int(p["highFixedPoint"]))
    if not (low_fp <= high_fp <= max_value):
        return VALIDATE_BAD_HIGH_FP
    paper_min = _s16(int(p["paperMin"]))
    paper_max = _s16(int(p["paperMax"]))
    if not (0 <= paper_min <= paper_max <= max_value):
        return VALIDATE_BAD_PAPER
    min_slope = float(p["minSlope"])
    max_slope = float(p["maxSlope"])
    if not (0.0 <= min_slope <= max_slope):
        return VALIDATE_BAD_SLOPE
    bin_factor = int(p["binFactor"])
    if bin_factor < 1 or (max_value + 1) % bin_factor != 0:
        return VALIDATE_BAD_BIN_FACTOR
    if float(p["lumWeighting"]) + float(p["edgeWeighting"]) != 1.0:
        return VALIDATE_BAD_WEIGHTS
    ff = float(p["flashFraction"])
    if not (0.0 <= ff <= 1.0):
        return VALIDATE_BAD_FLASH_FRACTION
    bf = float(p["backlitFraction"])
    if not (0.0 <= bf <= 1.0):
        return VALIDATE_BAD_BACKLIT_FRACTION
    smcp = float(p["startingMinCumPoint"])
    if not (0.0 <= smcp <= 50.0):
        return VALIDATE_BAD_STARTING_MIN_CUM
    cpbm = float(p["cumPctBelowMin"])
    if not (0.0 <= cpbm <= 25.0):
        return VALIDATE_BAD_CUM_BELOW_MIN
    smxcp = float(p["startingMaxCumPoint"])
    if not (50.0 <= smxcp <= 100.0):
        return VALIDATE_BAD_STARTING_MAX_CUM
    cpam = float(p["cumPctAboveMax"])
    if not (0.0 <= cpam <= 25.0):
        return VALIDATE_BAD_CUM_ABOVE_MAX
    return 0


# ---------------------------------------------------------------------------
# AnsDraResults + alloc — 0x1022a820
# ---------------------------------------------------------------------------


@dataclass
class DraResults:
    """The ``AnsDraResults`` struct, ``impl+0x1c88``.  See ``DRA_RESULTS_LAYOUT``.

    Buffers are ``None`` exactly when ``alloc()``'s corresponding gate
    (``allocLum``/``allocEdge``) was false -- generateLut's null checks on
    the real pointers (``0x1022ab9d``, ``0x1022acaa``) become ``is None``
    checks here.
    """

    nSmallBins: int = 0
    LumHist: list[int] | None = None
    EdgeHist: list[int] | None = None
    nLargeBins: int = 0
    nLumPixels: int = 0
    LumLargeHist: list[int] | None = None
    LumCumHist: list[int] | None = None
    nEdgePixels: int = 0
    EdgeLargeHist: list[int] | None = None
    EdgeCumHist: list[int] | None = None
    Scratch: list[int] | None = None
    lumMin: int = 0
    lumMax: int = 0
    edgeMin: int = 0
    edgeMax: int = 0
    effMin: int = 0
    effMax: int = 0
    DraLut: list[int] | None = None

    def to_bytes(self, *, dra_lut_pointer: int = 0) -> bytes:
        """Serialises to the ``0x3c``-byte ``AnsDraResults`` layout
        (``DRA_RESULTS_LAYOUT``), for a shell that needs the same window the
        real ``0x10130390`` getter ``rep movsd``s out of ``impl+0x1c88``.

        The seven internal heap-pointer fields (``LumHist``, ``EdgeHist``,
        the two large/cum histogram pairs, ``Scratch``) are always ``0`` —
        they are real DLL addresses, meaningless to a host caller, and
        nothing downstream reads them (matches ``pakon_toneHelper``'s own
        results serialisation, whose docstring makes the same point).
        ``DraLut`` is the one pointer field a caller can usefully populate:
        pass ``dra_lut_pointer`` for whatever opaque token the caller wants
        threaded onward (``self.DraLut`` itself holds the real array).
        """
        buf = bytearray(DRA_RESULTS_SIZE)
        struct.pack_into("<i", buf, 0x00, self.nSmallBins)
        struct.pack_into("<i", buf, 0x0C, self.nLargeBins)
        struct.pack_into("<i", buf, 0x10, self.nLumPixels)
        struct.pack_into("<i", buf, 0x1C, self.nEdgePixels)
        struct.pack_into("<h", buf, 0x2C, _s16(self.lumMin))
        struct.pack_into("<h", buf, 0x2E, _s16(self.lumMax))
        struct.pack_into("<h", buf, 0x30, _s16(self.edgeMin))
        struct.pack_into("<h", buf, 0x32, _s16(self.edgeMax))
        struct.pack_into("<h", buf, 0x34, _s16(self.effMin))
        struct.pack_into("<h", buf, 0x36, _s16(self.effMax))
        struct.pack_into("<I", buf, 0x38, dra_lut_pointer & 0xFFFFFFFF)
        return bytes(buf)


def alloc(n_small_bins: int, alloc_lum: bool, alloc_edge: bool,
          bin_factor: int) -> DraResults:
    """``0x1022a820`` — ``AnsDraCapabilityImpl::allocateMemory``.

    ABI read off the real Cap-wrapper call sites (``0x10131020``'s call to
    ``0x1022a820`` and its ``0x10131100`` sibling): ``ecx`` = impl, stack =
    ``(&outStorage, nSmallBins, allocLum, allocEdge)``, ``ret 0x10``.
    ``nLargeBins = nSmallBins // binFactor`` (x86 ``idiv`` truncation --
    ``validate_params`` already guarantees this divides evenly for real
    inputs, but truncation is reproduced regardless of that guarantee).
    ``Scratch`` and ``DraLut`` are allocated unconditionally; the six
    lum/edge histogram buffers only per their gate, matching real ``operator
    new`` calls 1:1 (Unicorn-verified via a hook on ``0x104ffd78``).
    """
    if not DRA_ALLOC_PORTED:
        _unported("DRA_ALLOC_PORTED", DRA_ALLOC_BUFFERS,
                  "AnsDraCapabilityImpl::allocateMemory")
    r = DraResults()
    r.nSmallBins = n_small_bins
    n_large = _idiv(n_small_bins, bin_factor)
    r.nLargeBins = n_large
    if alloc_lum:
        r.LumHist = [0] * max(n_small_bins, 0)
        r.LumLargeHist = [0] * max(n_large, 0)
        r.LumCumHist = [0] * max(n_large, 0)
    if alloc_edge:
        r.EdgeHist = [0] * max(n_small_bins, 0)
        r.EdgeLargeHist = [0] * max(n_large, 0)
        r.EdgeCumHist = [0] * max(n_large, 0)
    r.Scratch = [0] * max(n_small_bins, 0)
    r.DraLut = [0] * max(n_small_bins, 0)
    return r


# ---------------------------------------------------------------------------
# generateLut — 0x1022ab50
# ---------------------------------------------------------------------------


def remap_hist(hist: list[int], tone_lut: list[int], n: int) -> list[int]:
    """``0x1022abaf``..``0x1022ac19`` / ``0x1022acbe``..``0x1022ad26`` —
    generateLut's own toneLut-gated small-bin histogram remap.

    Only reached when generateLut is given a non-null third argument (the
    incoming tone LUT — variant B only, when composing dra onto an existing
    tone curve).  For each small bin ``i``: ``scratch[toneLut[i]] +=
    hist[i]``, then the small-bin histogram is replaced by ``scratch``
    wholesale (the DLL's own ``rep movsd`` copy-back).  This is the
    histogram-side counterpart to ``compose_tone``'s curve-side remap — the
    two are easy to conflate but are different blocks at different times:
    this one runs *inside* generateLut, *before* rebin; ``compose_tone`` runs
    *after* generateLut returns, on the finished LUT.
    """
    scratch = [0] * n
    for i in range(n):
        idx = _s16(tone_lut[i])
        scratch[idx] = _s32(scratch[idx] + hist[i])
    return scratch


def _cumsum32(large: list[int]) -> tuple[list[int], int]:
    """``0x1022ac38``..``0x1022ac69`` / ``0x1022ad2c``..``0x1022ad7d`` — the
    running cumulative sum over the large-bin histogram, plus its final
    total (``nLumPixels``/``nEdgePixels``)."""
    cum: list[int] = []
    total = 0
    for v in large:
        total = _s32(total + v)
        cum.append(total)
    return cum, total


def generate_lut(results: DraResults, params: "DraParams", lighting: int,
                 tone_lut: list[int] | None) -> list[int]:
    """``0x1022ab50`` — ``AnsDraCapabilityImpl::generateLut``.

    Mutates ``results`` in place (nLargeBins, the two large/cum histograms
    and pixel counts, lumMin/Max, edgeMin/Max, effMin/Max, DraLut) and
    returns the built LUT.  Four stages, each already independently
    Unicorn-verified; this is their assembly, itself Unicorn-verified
    end-to-end against the real ``0x1022ab50`` bytes (see
    ``check_generate_lut``):

    1. Per side (lum, edge), only if that side's large-histogram buffer
       exists (``alloc()``'s gate): optionally remap the small-bin
       histogram through ``tone_lut`` (``remap_hist``, variant B only),
       then ``rebin`` -> cumulative sum -> ``cum_bounds``.  A side whose
       buffer does not exist gets the DLL's own ``-1`` sentinel for its
       min/max (``0x1022ac93``/``0x1022adab``), not a call to ``cum_bounds``.
    2. The three-way merge that picks ``effMin``/``effMax``
       (``0x1022adc1``..``0x1022ae12``, disassembled directly for this
       session — not previously documented): if the edge side is the ``-1``
       sentinel, effMin/effMax are copied from lum; if lum is the sentinel
       (and edge is not), they are copied from edge; only when BOTH sides
       are real is ``eff_bounds()`` actually called.
    3. ``keepMidPtLut`` (``keep_midpt_lut``) builds the final curve from the
       lighting-selected TTC pair and the resolved eff bounds.

    WHAT THIS ACTUALLY DOES TO PIXELS
    ---------------------------------
    Asserted against the real DLL, not reasoned out of the port — see
    ``pakon_dra_golden.check_lut_behaviour``.  With the shipped
    ``ansel-dra-default-default.dpi`` (paperMin 1200, paperMax 2000, both
    fixed points 1550) and the shipped Normal ``.ttc`` pair (both the
    3-point identity ``0 0 / 1 1 / 10 10``):

    * **If ``[effMin, effMax]`` lies inside ``[paperMin, paperMax]``, the
      DraLut is EXACTLY the identity** — all 4096 entries, ``lut[i] == i``.
      dra does nothing whatsoever to such a frame.
    * **Only a range that spills outside the paper range is touched**, and
      then the offending side is *compressed inward*, pivoting on the fixed
      point 1550: highs map ``[1550, effMax] -> [1550, paperMax]`` and then
      continue at unit slope; lows map ``[effMin, 1550] -> [paperMin,
      1550]`` and then ramp down by 1 per step.  The two sides are
      independent — one can be compressed while the other stays identity.
    * **There is no expansion branch at all.**  Nothing here stretches a
      narrow ``[effMin, effMax]`` out to fill ``[paperMin, paperMax]``.  dra
      is a one-way clamp-and-compress, not an auto-level.

    So dra's contribution to overall brightness is zero for an in-range
    frame and NEGATIVE-going (a pull toward 1550) for a frame whose
    highlights exceed paperMax.  It only shifts a frame brighter when that
    frame is shadow-clipped (``effMin`` well below ``paperMin``).

    ``minSlope`` and ``maxSlope`` (params +0x0c/+0x10) are **dead here**
    despite their names: ``0x1022ab50`` contains no x87 instructions at all,
    and ``0x102290b0`` reads only params +0x00/+0x02/+0x04/+0x06/+0x08/+0x28
    and the six ``.ttc`` blocks.  Confirmed positively rather than by that
    absence: sweeping both across their whole valid range leaves the real
    DLL's DraLut byte-identical on a frame where dra is genuinely working
    (``check_lut_behaviour`` case (c)).  Their only consumer is
    ``validate_params``' range check (bad-index 6).
    """
    if not DRA_GENERATE_LUT_PORTED:
        _unported("DRA_GENERATE_LUT_PORTED", DRA_GENERATE_LUT,
                  "AnsDraCapabilityImpl::generateLut")
    n_small = results.nSmallBins
    bin_factor = int(params["binFactor"])
    n_large = _idiv(n_small, bin_factor)
    results.nLargeBins = n_large

    if results.LumLargeHist is not None:
        lum_small = results.LumHist
        if tone_lut is not None and lum_small is not None:
            lum_small = remap_hist(lum_small, tone_lut, n_small)
            results.LumHist = lum_small
        large = rebin(lum_small, n_small, bin_factor)
        results.LumLargeHist = large
        cum, total = _cumsum32(large)
        results.LumCumHist = cum
        results.nLumPixels = total
        results.lumMin, results.lumMax = cum_bounds(
            cum, large, n_large, total, params.values)
    else:
        results.lumMin = results.lumMax = -1

    if results.EdgeLargeHist is not None:
        edge_small = results.EdgeHist
        if tone_lut is not None and edge_small is not None:
            edge_small = remap_hist(edge_small, tone_lut, n_small)
            results.EdgeHist = edge_small
        large = rebin(edge_small, n_small, bin_factor)
        results.EdgeLargeHist = large
        cum, total = _cumsum32(large)
        results.EdgeCumHist = cum
        results.nEdgePixels = total
        results.edgeMin, results.edgeMax = cum_bounds(
            cum, large, n_large, total, params.values)
    else:
        results.edgeMin = results.edgeMax = -1

    if results.edgeMin < 0:
        results.effMin, results.effMax = results.lumMin, results.lumMax
    elif results.lumMin < 0:
        results.effMin, results.effMax = results.edgeMin, results.edgeMax
    else:
        results.effMin, results.effMax = eff_bounds(
            results.lumMin, results.lumMax, results.edgeMin, results.edgeMax,
            params["paperMin"], params["paperMax"], params["lumWeighting"],
            params["edgeWeighting"], params["bDoAverage"])

    low, high = params.curve_pair(lighting)
    dra_lut = keep_midpt_lut(
        lighting, low, high, params["maxValue"], params["lowFixedPoint"],
        params["highFixedPoint"], params["paperMin"], params["paperMax"],
        params["flashFraction"], results.effMin, results.effMax)
    results.DraLut = dra_lut
    return dra_lut


# ---------------------------------------------------------------------------
# the two analyze overloads
# ---------------------------------------------------------------------------


def analyze_image(params: "DraParams", pixels: bytes, width: int,
                  height: int, lighting: int) -> DraResults:
    """``0x1022af20`` — the no-incoming-tone-LUT overload.

    Builds its own luminance histogram from raw pixel data (no edge side —
    ``alloc(..., alloc_lum=True, alloc_edge=False, ...)``, so
    ``generate_lut`` always takes the "edge absent -> eff = lum" branch),
    and never composes (no incoming ``tone_lut``, matching the docstring's
    "0x1022af20 has no equivalent [compose] block").  ``lighting`` is the
    already-resolved value (0/1/2) from the guarded
    ``find("lighting")`` — see ``lighting_from_find``, ported and verified
    separately; this function does not re-derive it, since that means
    modelling a live ``AnsSceneContext``, which is exactly what
    ``lighting_from_find`` already abstracts.
    """
    if not DRA_ANALYZE_IMAGE_PORTED:
        _unported("DRA_ANALYZE_IMAGE_PORTED", DRA_ANALYZE_IMAGE,
                  "AnsDraCapabilityImpl::analyze (image overload)")
    bad = validate_params(params)
    if bad:
        raise DraError(f"Parameter #{bad} is invalid.")
    n_small = _s16(int(params["maxValue"])) + 1
    results = alloc(n_small, True, False, int(params["binFactor"]))
    n_pixels = width * height
    results.LumHist = lum_histogram(pixels, n_pixels, n_small)
    generate_lut(results, params, lighting, None)
    return results


def analyze_hist(params: "DraParams", lum_hist: list[int] | None,
                 edge_hist: list[int] | None, tone_lut: list[int] | None,
                 lighting: int) -> DraResults:
    """``0x1022b530`` — the histograms-in / compose-out overload.

    ``lum_hist``/``edge_hist`` gate ``alloc()``'s two buffer sets
    independently (either or both may be provided; both ``None`` raises,
    matching the DLL's ``"No analysis data was provided!."`` at line 842).
    When ``tone_lut`` is provided, ``generate_lut`` remaps the incoming
    small-bin histograms through it (``remap_hist``, inside generateLut,
    *before* rebin) **and**, separately, the finished curve is composed onto
    it afterward (``compose_tone``, *after* generateLut returns) — two
    different uses of the same array, both real, confirmed by reading the
    real call site (``0x1022babf``: ``generateLut(&out, lighting,
    piStack_14)`` where ``piStack_14`` is the very pointer the compose block
    at ``0x1022bb0f`` also gates on).
    """
    if not DRA_ANALYZE_HIST_PORTED:
        _unported("DRA_ANALYZE_HIST_PORTED", DRA_ANALYZE_HIST,
                  "AnsDraCapabilityImpl::analyze (histogram overload)")
    bad = validate_params(params)
    if bad:
        raise DraError(f"Parameter #{bad} is invalid.")
    if lum_hist is None and edge_hist is None:
        raise DraError("No analysis data was provided!.")
    n_small = _s16(int(params["maxValue"])) + 1
    results = alloc(n_small, lum_hist is not None, edge_hist is not None,
                    int(params["binFactor"]))
    if lum_hist is not None:
        results.LumHist = list(lum_hist)
    if edge_hist is not None:
        results.EdgeHist = list(edge_hist)
    generate_lut(results, params, lighting, tone_lut)
    if tone_lut is not None:
        results.DraLut = compose_tone(results.DraLut, tone_lut, n_small)
    return results


# ---------------------------------------------------------------------------

VENDOR_DRA_DIR = (Path(__file__).resolve().parents[3] / "vendor" / "ansel"
                  / "anselinstalldir" / "dataPathItems" / "dra")


def main() -> None:
    print(f"dra — stage 2 of analyzeAutoTone")
    print(f"  analyze(image) {DRA_ANALYZE_IMAGE:#010x}  "
          f"38 fns /  9,757 B / 45 indirect   (Cap {DRA_CAP_ACQUIRE:#x})")
    print(f"  analyze(hist)  {DRA_ANALYZE_HIST:#010x}  "
          f"41 fns / 10,017 B / 40 indirect   (Cap {DRA_CAP_ACQUIRE_HIST:#x})")
    print(f"  shared 37 of 42 functions; the second entry point is NOT "
          f"0x101dd1b0 (that is toneHelper's)")
    print()
    print("  find(\"lighting\") sites — miss CONTINUES at both:")
    for va, s in DRA_LIGHTING_SITES.items():
        print(f"    {va:#010x}: key {s[0]:#x} find {s[1]:#x} flag {s[2]:#x} "
              f"test {s[3]:#x} -> continue {s[4]:#x} "
              f"(abort {s[5]:#x}, line {s[6]})")
    print()
    print("  lighting dispatch (keepMidPtLut 0x102290d6):")
    for val in (LIGHTING_NORMAL, LIGHTING_BACKLIT, LIGHTING_FRONTLIT):
        lo, hi, lo_off, hi_off = LIGHTING_DISPATCH[val]
        print(f"    {val} -> {lo:<16} params+{lo_off:#06x}   "
              f"{hi:<17} params+{hi_off:#06x}")
    print()
    if VENDOR_DRA_DIR.is_dir():
        p = DraParams.load(VENDOR_DRA_DIR)
        print(f"  {VENDOR_DRA_DIR.name}/ansel-dra-default-default.dpi "
              f"— {len(p.values)} keys")
        for key, _off, kind in DRA_PARAMS_LAYOUT:
            if kind == "ttc":
                c = p.curves[key]
                print(f"    {key:<20} {p.values[key]:<18} {c.n_points} pts  "
                      f"{'identity' if c.is_identity else 'SHAPED'}")
            else:
                print(f"    {key:<20} {p.values[key]}")
        lo, hi = p.curve_pair(LIGHTING_NORMAL)
        print(f"\n  a find(\"lighting\") MISS selects lighting 0 -> "
              f"({lo.name}, {hi.name})")
        print(f"    both identity: {lo.is_identity and hi.is_identity} "
              f"— the miss is numerically inert on this unit's shipped data")
    print()
    print(f"  ENTRY_POINTS={DRA_ENTRY_POINTS_PORTED} "
          f"LIGHTING_BRANCH={DRA_LIGHTING_BRANCH_PORTED} "
          f"LIGHTING_DISPATCH={DRA_LIGHTING_DISPATCH_PORTED}")
    print(f"  DPI={DRA_DPI_PARSE_PORTED} TTC={DRA_TTC_PARSE_PORTED} "
          f"RESULTS_LAYOUT={DRA_RESULTS_LAYOUT_PORTED}")
    print(f"  REBIN={DRA_REBIN_PORTED} LUM_HIST={DRA_LUM_HISTOGRAM_PORTED} "
          f"COMPOSE={DRA_COMPOSE_TONE_PORTED} "
          f"CUM_BOUNDS={DRA_CUM_BOUNDS_PORTED}")
    print(f"  EFF_BOUNDS={DRA_EFF_BOUNDS_PORTED} "
          f"KEEP_MIDPT_LUT={DRA_KEEP_MIDPT_LUT_PORTED} "
          f"TTC_SLOPE={DRA_TTC_SLOPE_PORTED}")
    print(f"  GENERATE_LUT={DRA_GENERATE_LUT_PORTED} "
          f"ALLOC={DRA_ALLOC_PORTED} VALIDATE_PARAMS={DRA_VALIDATE_PARAMS_PORTED} "
          f"ANALYZE_IMAGE={DRA_ANALYZE_IMAGE_PORTED} "
          f"ANALYZE_HIST={DRA_ANALYZE_HIST_PORTED}")
    if VENDOR_DRA_DIR.is_dir():
        params = DraParams.load(VENDOR_DRA_DIR)
        pixels = struct.pack("<hhh", 100, 100, 100) * 4
        results = analyze_image(params, pixels, 2, 2, LIGHTING_NORMAL)
        print(f"\n  analyze_image(2x2 uniform pixels, lighting=Normal) -> "
              f"DraLut[:6]={results.DraLut[:6]}  "
              f"(n={results.nSmallBins}, effMin={results.effMin}, "
              f"effMax={results.effMax})")


if __name__ == "__main__":
    main()
