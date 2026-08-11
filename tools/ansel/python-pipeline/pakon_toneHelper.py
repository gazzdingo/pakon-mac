#!/usr/bin/env python3
r"""``toneHelper`` — stage 3 of ``ColorNegativePath::analyzeAutoTone``.

PakonIMAu.dll ImageBase ``0x10000000`` (file VAs == cited VAs), md5
``eea9dcf78ee21d4f7c515a6c2512242d``, sha256 ``0ede8d98…``.  This file is to the
``toneHelper`` subsystem what ``pakon_autotone.py`` is to the shell: Phase 1
built the shell and stubbed the six subsystems behind ``*_PORTED`` flags; this
is Phase 2c, the largest of the six by function count.

READ THIS FIRST — ``dei`` IS **NOT** AN INPUT HERE
==================================================
``toneHelper``'s shipped DPI (``toneHelper-default.dpi``) carries **two**
decision-tree keys::

    decisionTree    = AllOnTree1
    decisionTreeDei = deiTree1

and ``AnsDeiResults`` has a field literally named ``adjToneHelperDeiValue``.
That is suggestive and it has now cost this project two separate
investigations.  **It is not a dependency of this code path.**  Written down
here so nobody re-adds one:

* The tree actually walked by the two entry points ported in this file is the
  one at ``impl+0x78``, loaded from the ``decisionTree`` key — ``AllOnTree1``.
  ``deiTree1`` is loaded into a *different* member for a *different* caller.
* Of ``AnsToneHelperCapability::acquire``'s five call sites (``0x1010c6a0``
  xrefs: ``0x100fc4cb``, ``0x10104f9c``, ``0x101098c0``, ``0x1010cea0``,
  ``0x10116468``), the one at ``0x101098c0`` is inside
  ``ColorNegativePath::CalcDei`` (``0x101081e0``).  *That* is the caller the
  ``Dei`` naming describes — a separate CnPremium/Shasta route.  The call site
  this file models is ``0x100fc4cb``, inside ``analyzeAutoTone``.
* Execution order settles it independently: the scene driver ``fcn.10069490``
  calls ``analyzeAutoTone`` at ``0x10069a1d`` and ``CalcDei`` at ``0x10069aca``
  — dei runs **after**, so it structurally cannot be an input.
* Full decompilation of all four previously-unread callees (``0x101db020``,
  ``0x101dbc00``, ``0x101dabe0``, ``0x101db890``) finds zero reads of dei data.
  The only metric this file's tree evaluator can read that is *not* computed
  from the histograms is ``EXPOSURE`` (metric id 30, ``impl+0x128``), and its
  value comes from ``analyzeAutoTone``'s own ``&ctx[0x4bc]`` argument
  (``0x101dd2fd``/``0x101dce52``), not from dei.

**Nothing in this file imports, reads, models or references dei data.**
See ``docs/64-pruned-tone-producers.md`` §"Both remaining open questions".

TWO ENTRY-POINT VARIANTS (and which one is live)
================================================
The shell picks between them on whether cna produced an edge histogram
(``pakon_autotone.analyze_auto_tone`` stage 3, ``0x100fc334``)::

    Cap wrapper   Impl         args (after the hidden AnsStatus& sret)
    ------------  -----------  --------------------------------------------
    0x1010c3b0    0x101dd1b0   holder, lumHist, edgeHist, &ctx[0x4bc], tone
    0x1010c0f0    0x101dcc50   holder, arg2,               &ctx[0x4bc], tone

``0x101dd1b0`` is the **histogram-fed** variant: cna already built the
luminance and edge histograms, so it copies them straight in and never touches
a pixel.  ``0x101dcc50`` is the **image-fed** fallback: it has to build both
histograms itself, which is what the 1,803-byte ``0x101dbc00`` (Laplacian edge
detector + adaptive threshold search) does.

An earlier note had these two the other way round.  Settled by disassembly:
``0x101dcc50`` is reached only from ``0x1010c0f0`` (its single CALL xref) and
``0x1010c0f0`` is the ``arg2`` / no-edge-histogram wrapper; ``0x101dcc50``
self-names as ``"AnsToneHelperCapabilityImpl::analyze"`` at line 105
(``0x1059a938`` pushed at ``0x101dccec``) and ``0x101dd1b0`` self-names
identically at ``0x101dd3xx`` — they are two overloads of the same method.

**On the shipped CN-Enhanced path the histogram-fed variant is the live one**,
because cna's ``AnsCnaResults.EdgeHist`` is non-null.  That is the variant this
file ports end to end.  The image-fed variant's *orchestration* is ported;
its histogram/edge builder (``0x101dbc00``) is **not** — see
``TONEHELPER_IMAGE_HISTOGRAM_PORTED``.

WHAT THE SUBSYSTEM ACTUALLY COMPUTES
====================================
It is a **scene classifier**, not a curve builder.  It writes no LUT and — see
``pakon_autotone`` stage 3 — it does not write ``ctx+0x64d0``.  The one number
that leaves it is ``AnsToneHelperResults+0xb4``, which the shell hands to
``contrast`` as ``x`` when cna reported no ELMO event.  That number is 1 or 2.

    lumHist, edgeHist, toneLut, exposure
      -> AnsHistogram::calcStats  x2   (count, average, avgDev, stdDev, skew,
                                        kurtosis of each histogram)
      -> AnsHistogram::calcWork   x8   (tone-mapping "work" in each of the four
                                        tone bands, per histogram)
      -> AnsHistogram::calcDistance x2 (histogram displacement under the LUT)
      -> 29 float metrics at impl+0xb4..impl+0x128
      -> walk AllOnTree1 (0x101db890)
      -> terminal class c in {2,3,4}
      -> results+0xb4 = 1 if c < 3 else 2 ; results+0xb8 = c if c < 3 else 3

WHAT THE SHIPPED TREE ACTUALLY DOES — READ THIS BEFORE TUNING ANYTHING
=====================================================================
``AllOnTree1`` (the tree ``toneHelper-default.dpi`` selects, i.e. the one
CN-Enhanced uses) has its ``285.044`` root **commented out** in the shipped
file, and the live root immediately below it is::

    0    LUM_STDDEV              1.000        1          24     4

A luminance histogram with a standard deviation below one code value is a
frame that is essentially a single flat tone.  For any real scan the root
therefore takes its *greater* edge straight to node 24 — a TERMINAL of class
4, which the walker clamps — so::

    results+0xb4 (toneHelperValue) == 2      on every real frame
    results+0xb8 (sceneClass)      == 3

and nodes 12..23 of that file are unreachable no matter what the metrics are.
This is not an inference: the ``0x101dd1b0`` end-to-end cases in
``pakon_toneHelper_core_golden.py`` reach node 24 on every broad histogram and
node 2 only on a deliberately degenerate two-bin one, and the DLL agrees with
the port on both.

The consequence for the caller: ``analyzeAutoTone`` hands this number to
``contrast`` as ``x`` whenever cna reports no ELMO event
(``pakon_autotone`` stage 3/4, ``0x100fc5f0``), so in practice
``contrast`` receives a constant ``2`` from this route.  The 25-node tree is
real, it is verified, and it is doing almost nothing on this scan path — worth
knowing before anyone attributes tone behaviour to it.  ``dTree1``
(CN-Premium) keeps the ``285.044`` root live and does use its whole depth.

RESIDUAL / REACHABILITY (``tools/re/reachability.py walk``, this session)
========================================================================
======================  ======  ==========  ========
seed                     fns    realsz B     indirect
======================  ======  ==========  ========
0x101dd1b0 (hist-fed)       37      13,691        62
0x101dcc50 (image-fed)      49      19,920        89
0x101db020 (metrics)        27       8,757        34
0x101dbc00 (edge build)     36       8,885        36
0x101dabe0 (allocate)       24       3,390        10
0x101db890 (tree walk)      23       4,964        25
0x101da6b0 (validate)        1         325         0
======================  ======  ==========  ========

The ``0x101dd1b0`` walk (37 fns) minus ``0x101dbc00``'s exclusive part is what
this file models; the two goldens together run every one of those functions
that does arithmetic.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
  tools/ansel/python-pipeline/pakon_toneHelper.py``
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

# ---------------------------------------------------------------------------
# flags
# ---------------------------------------------------------------------------

#: The 30-way decision-tree walker ``AnsToneHelperParams::<tree walk>``
#: (``0x101db890``, 751 B) plus its verifier ``0x101da3b0`` -> ``0x101d9db0``.
#: Node stride 0x14, switch table at ``0x101dbb80`` (30 cases, ids 1..0x1e).
#: Verified bit-exact against the DLL by ``pakon_toneHelper_tree_golden.py``,
#: including cases that take both branch directions at multiple depths.
TONEHELPER_DECISION_TREE_PORTED = True

#: The ASCII decision-tree file parser (``AllOnTree1`` / ``dTree1``) and the
#: 31-entry metric-name table at ``0x106993a0``.  See ``METRIC_NAMES``.
TONEHELPER_TREE_FILE_PORTED = True

#: ``toneHelper-*.dpi`` -> ``AnsToneHelperParams`` (impl+0x0c..impl+0x7f).
TONEHELPER_DPI_PORTED = True

#: ``AnsToneHelperParams`` field validation (``0x101da6b0``) — the seven bound
#: checks and the "Bad field(#N) in AnsToneHelperParams structure!" indices.
TONEHELPER_PARAM_CHECK_PORTED = True

#: ``AnsToneHelperCapabilityImpl::allocateMemory`` (``0x101dabe0``) — the
#: results-window zeroing and the buffer size table.
TONEHELPER_ALLOCATE_PORTED = True

#: ``AnsHistogram::calcStats`` / ``::calcWork`` / ``::calcDistance``
#: (``0x10278730`` / ``0x10278df0`` / ``0x102781d0``).  Modelled in float64
#: with an ``f32()`` at every ``fst``/``fstp dword`` -- see the precision block
#: above for why float64 is the right model and why the goldens have to set
#: FPCW themselves.  ``calcStats``' 4x-unrolled loop rounds a *different*
#: subset of its four accumulators in each of its four slots; that table is in
#: ``AnsHistogram.calc_stats``' docstring and it is transcribed, not inferred.
TONEHELPER_HISTOGRAM_PORTED = True

#: The metric producer ``0x101db020`` — three AnsHistogram objects, two passes
#: (luminance then edge), the four calcWork bands, calcDistance, and the two
#: asymmetric normalisation blocks at ``0x101db4c6`` and ``0x101db596``.
TONEHELPER_METRICS_PORTED = True

#: ``AnsToneHelperResults`` layout (impl+0x80, 0x2f dwords) and the
#: ``rep movsd`` getter ``0x1010bb40`` behind Cap ``0x1010c6a0``.
TONEHELPER_RESULTS_LAYOUT_PORTED = True

#: The histogram-fed entry point ``0x101dd1b0`` (Cap ``0x1010c3b0``) end to
#: end.  **This is the variant that runs on the shipped CN-Enhanced path.**
TONEHELPER_ACQUIRE_HIST_PORTED = True

#: The image-fed fallback ``0x101dcc50`` (Cap ``0x1010c0f0``).  Its
#: orchestration is ported and verified; the histogram/edge *builder* it needs
#: is not — see the flag below.  False because the entry point as a whole
#: cannot run without that builder.
TONEHELPER_ACQUIRE_IMAGE_PORTED = False

#: ``0x101dbc00`` — the image-side histogram + Laplacian edge builder with the
#: adaptive threshold search (``thresholdMultiplier`` / ``thresholdReduction
#: Factor`` / ``minEdgeThreshold`` / ``minEdgeRatio``).  36 fns / 8,885 B.
#: Only reachable from ``0x101dcc50``, i.e. only when cna produced no edge
#: histogram, which does not happen on the shipped colour-negative path.
#: NOT PORTED — nothing here fakes it, the entry point raises instead.
TONEHELPER_IMAGE_HISTOGRAM_PORTED = False

# ---------------------------------------------------------------------------
# addresses
# ---------------------------------------------------------------------------

CAP_ACQUIRE_HIST = 0x1010C3B0        # AnsToneHelperCapability::acquire (hist)
CAP_ACQUIRE_IMAGE = 0x1010C0F0       # ... (image)
CAP_GET_RESULTS = 0x1010C6A0         # ... ::getResults trampoline
IMPL_GET_RESULTS = 0x1010BB40        # rep movsd 0x2f dwords from impl+0x80

IMPL_ANALYZE_HIST = 0x101DD1B0       # AnsToneHelperCapabilityImpl::analyze
IMPL_ANALYZE_IMAGE = 0x101DCC50      # ... the arg2/image overload

PARAM_CHECK = 0x101DA6B0             # -> "Bad field(#N)…"
RESET_BUFFERS = 0x101DA800           # frees impl+0x84,0x8c,0x94,0x9c,0xa0,0xa4,0xa8
RESET_ALL = 0x101DA8C0               # RESET_BUFFERS + impl+0x88,0x98,0xac
ALLOCATE_MEMORY = 0x101DABE0         # AnsToneHelperCapabilityImpl::allocateMemory
BUILD_HISTOGRAMS = 0x101DBC00        # image-side builder (NOT ported)
COMPUTE_METRICS = 0x101DB020         # the 29 metrics
WALK_TREE = 0x101DB890               # the 30-way decision-tree walker
VERIFY_TREE = 0x101DA3B0             # AnsToneHelperParams::verifyDecisionTree
CHECK_TREE_NODES = 0x101D9DB0        # its worker

HIST_CTOR = 0x10278140               # AnsHistogram::AnsHistogram
HIST_CALC_STATS = 0x10278730         # AnsHistogram::calcStats
HIST_CALC_WORK = 0x10278DF0          # AnsHistogram::calcWork
HIST_CALC_DISTANCE = 0x102781D0      # AnsHistogram::calcDistance

TREE_SWITCH_TABLE = 0x101DBB80       # 30 entries, indexed by (metricId - 1)
METRIC_NAME_TABLE = 0x106993A0       # 31 char* entries, ids 0..0x1e
STATUS_OK_GLOBAL = 0x106B5BD4        # the AnsStatus "no error" singleton (0)

#: Float constants the arithmetic uses, read out of ``.rdata``.
K_ONE = 0x1058D4C0                   # 1.0f
K_ZERO = 0x10575674                  # 0.0f
K_THREE = 0x1059CC08                 # 3.0f  (the kurtosis "- 3" term)
K_ZERO_2 = 0x10573C40                # 0.0f  (the variance != 0 guard)

SRC_FILE_IMPL = r"\Atc\ansel\src\libToneHelper.ansel\AnsToneHelperCapabilityImpl.cpp"
SRC_FILE_PARAMS = r"\Atc\ansel\src\libToneHelper.ansel\AnsToneHelperParams.cpp"
SRC_FILE_HIST = r"\Atc\ansel\src\libToneHelper.ansel\AnsHistogram.cpp"

#: Shipped data, vendored.  ``toneHelper.map`` selects per scan path:
#: ``CN-Enhanced -> ansel-toneHelper-default``, i.e. ``toneHelper-default.dpi``
#: with ``decisionTree = AllOnTree1``.  (``CN-Premium`` selects
#: ``toneHelper-CNPremium.dpi``, whose only difference is
#: ``decisionTree = dTree1``.)
DATA_DIR = (Path(__file__).resolve().parents[3]
            / "vendor/ansel/anselinstalldir/dataPathItems/toneHelper")
DEFAULT_DPI = "toneHelper-default.dpi"
DEFAULT_TREE = "AllOnTree1"


class ToneHelperError(RuntimeError):
    """What ``0x1001ed90`` raises out of this subsystem."""


def _unported(flag: str, what: str, va: int):  # -> NoReturn
    raise RuntimeError(
        f"{flag} is False: {what} ({va:#x}) is not ported. "
        f"See pakon_toneHelper.py's flag block.")


# ---------------------------------------------------------------------------
# x87 PRECISION — THE LOAD-BEARING BIT
#
# Every accumulator in AnsHistogram lives in ST(0) across its loop and is only
# narrowed on an explicit ``fst``/``fstp dword``.  Reproducing the results
# therefore needs the FPU's *precision control* to be right, not just the
# formula.
#
# Windows initialises the x87 control word to ``0x027f`` — round-to-nearest-
# even, PC = 10b = **53-bit** — and MSVC 7.1's CRT keeps it there.  53-bit
# significand with round-to-nearest-even is exactly a Python ``float``, so
# every "ST(0)" value below is modelled as a plain double and every documented
# ``fst dword`` as ``f32()``.  No 80-bit emulation is needed *provided the
# control word is actually 0x027f*.
#
# That proviso is not theoretical.  Unicorn reports ``FPCW == 0x0000`` on a
# fresh ``Uc`` and its behaviour with the register left alone is 64-bit
# extended, while writing ``0x007f`` gives 24-bit single -- measured, not
# assumed: dividing 1.0 by 3 and storing ``fstp tbyte`` yields significand
# 0xaaaa_aaaa_aaaa_aaab (64-bit) untouched, 0xaaaa_aaaa_aaaa_a800 (53-bit) at
# 0x027f and 0xaaaa_ab00_0000_0000 (24-bit) at 0x007f.  Both goldens therefore
# set ``0x027f`` explicitly and re-run at ``0x037f`` to report whether any
# output moves -- the same convention ``pakon_ast_golden.py`` established.
# ---------------------------------------------------------------------------

#: Windows' x87 control word: round-to-nearest-even, 53-bit precision control.
FPCW_WINDOWS = 0x027F
#: 64-bit extended -- the sensitivity check the goldens run, not the model.
FPCW_EXTENDED = 0x037F


def f32(v) -> float:
    """Round a host double to float32 — one ``fst``/``fstp dword``."""
    return struct.unpack("<f", struct.pack("<f", float(v)))[0]


# ---------------------------------------------------------------------------
# the metric enum — the 31-entry char* table at 0x106993a0
#
# Read straight out of .data: each entry is a pointer into .rdata, and the
# ``decisionTree`` files name metrics by exactly these strings.  The walker's
# jump table (0x101dbb80, 30 entries) is indexed by ``metricId - 1``, so the
# ids below are the table indices and NONE (0) has no case.
# ---------------------------------------------------------------------------

METRIC_NAMES: tuple[str, ...] = (
    "NONE",                # 0  -- no switch case; leaves ST(0) unchanged
    "TERMINAL",            # 1  -- 0x101dbaf4, the only exit
    "LUM_WORK_LOW",        # 2  impl+0xb4
    "LUM_WORK_MIDLOW",     # 3  impl+0xb8
    "LUM_WORK_SUMLOW",     # 4  impl+0xbc
    "LUM_WORK_MIDHIGH",    # 5  impl+0xc0
    "LUM_WORK_HIGH",       # 6  impl+0xc4
    "LUM_WORK_SUMHIGH",    # 7  impl+0xc8
    "LUM_WORK_TOTAL",      # 8  impl+0xcc
    "LUM_DISTANCE",        # 9  impl+0xd0
    "LUM_INTERSECTION",    # 10 impl+0xd4
    "LUM_AVERAGE",         # 11 impl+0xd8
    "LUM_AVGDEV",          # 12 impl+0xdc
    "LUM_STDDEV",          # 13 impl+0xe0
    "LUM_SKEW",            # 14 impl+0xe4
    "LUM_KURTOSIS",        # 15 impl+0xe8
    "EDGE_WORK_LOW",       # 16 impl+0xf0   <-- note the 8-byte step here
    "EDGE_WORK_MIDLOW",    # 17 impl+0xf4
    "EDGE_WORK_SUMLOW",    # 18 impl+0xf8
    "EDGE_WORK_MIDHIGH",   # 19 impl+0xfc
    "EDGE_WORK_HIGH",      # 20 impl+0x100
    "EDGE_WORK_SUMHIGH",   # 21 impl+0x104
    "EDGE_WORK_TOTAL",     # 22 impl+0x108
    "EDGE_DISTANCE",       # 23 impl+0x10c
    "EDGE_INTERSECTION",   # 24 impl+0x110
    "EDGE_AVERAGE",        # 25 impl+0x114
    "EDGE_AVGDEV",         # 26 impl+0x118
    "EDGE_STDDEV",         # 27 impl+0x11c
    "EDGE_SKEW",           # 28 impl+0x120
    "EDGE_KURTOSIS",       # 29 impl+0x124
    "EXPOSURE",            # 30 impl+0x128
)

METRIC_ID = {name: i for i, name in enumerate(METRIC_NAMES)}
METRIC_TERMINAL = 1
METRIC_NONE = 0


def metric_impl_offset(metric_id: int) -> int:
    """Impl offset the walker's ``fld dword`` reads for ``metric_id``.

    Straight off the 30 switch arms at ``0x101db98a``..``0x101dbad4``: ids
    2..15 are ``0xb4 + 4*(id-2)`` and ids 16..30 are ``0xf0 + 4*(id-16)``.
    The 8-byte step between id 15 (``0xe8``) and id 16 (``0xf0``) is the
    ``count`` int at the head of the EDGE metric group (``impl+0xec``); the
    LUM group's own count sits at ``impl+0xb0``, before id 2.
    """
    if 2 <= metric_id <= 15:
        return 0xB4 + 4 * (metric_id - 2)
    if 16 <= metric_id <= 30:
        return 0xF0 + 4 * (metric_id - 16)
    raise KeyError(f"metric id {metric_id} has no switch arm")


#: The two ``AnsHistogram`` metric groups, 0x3c bytes each.  Field names come
#: from the vendor's own ostream printer literals (``"    kurtosis = "`` …
#: ``0x1059a350``..``0x1059a3e0``); the offsets come from which out-parameter
#: 0x101db020 passes where.
METRIC_GROUP_FIELDS: tuple[tuple[int, str, str], ...] = (
    (0x00, "count", "i32"),          # calcStats out #1
    (0x04, "workLow", "f32"),        # calcWork lowToneRange
    (0x08, "workMidLow", "f32"),     # calcWork midLowToneRange
    (0x0C, "workSumLow", "f32"),     # low + midLow
    (0x10, "workMidHigh", "f32"),    # calcWork midHighToneRange
    (0x14, "workHigh", "f32"),       # calcWork highToneRange
    (0x18, "workSumHigh", "f32"),    # midHigh + high
    (0x1C, "workTotal", "f32"),      # sumHigh + sumLow
    (0x20, "distance", "f32"),       # calcDistance out #1
    (0x24, "intersection", "f32"),   # calcDistance out #2
    (0x28, "average", "f32"),        # calcStats out #2
    (0x2C, "avgDev", "f32"),         # calcStats out #3
    (0x30, "stdDev", "f32"),         # calcStats out #4
    (0x34, "skew", "f32"),           # calcStats out #5
    (0x38, "kurtosis", "f32"),       # calcStats out #6
)

LUM_GROUP_OFFSET = 0xB0     # 0x101db0d1  lea eax, [edi + 0xb0]
EDGE_GROUP_OFFSET = 0xEC    # 0x101db0bb  lea ebp, [edi + 0xec]


# ---------------------------------------------------------------------------
# AnsToneHelperParams — impl+0x0c .. impl+0x7f (sizeof 0x74)
#
# Read out of the params ostream printer ``0x101d92f0``, whose ``"  <name> = "``
# literal and ``[ebx + off]`` load pair one-to-one, exactly the vendor pattern
# ``pakon_autotone``'s AUTOTONE_WORK_LAYOUT uses.  ``impl+0x0c == params+0x00``
# is fixed by 0x101dcc92 (``lea ecx, [ebx+0xc]`` feeding the validator) and by
# the DPI reader, which writes every field at ``dpi+0x2c + params_off``.
#
# Independently cross-checked three ways: the validator 0x101da6b0's own
# offsets, 0x101db020's ``movsx word [edi+0x60..0x6e]`` feeding calcWork's
# band limits, and 0x101db890's ``mov eax,[esi+0x70]`` / ``mov ebp,[esi+0x78]``.
# ---------------------------------------------------------------------------

PARAMS_BASE = 0x0C          # AnsToneHelperParams lives at impl+0x0c
PARAMS_SIZE = 0x74          # ... and ends exactly where the results begin

TONEHELPER_PARAMS_FIELDS: tuple[tuple[int, str, str], ...] = (
    (0x0C, "key", "std::string"),          # 0x1c bytes
    (0x28, "version", "std::string"),      # 0x1c bytes
    (0x44, "maxValue", "i16"),
    (0x48, "thresholdMultiplier", "f32"),
    (0x4C, "thresholdReductionFactor", "f32"),
    (0x50, "minEdgeThreshold", "i16"),
    (0x54, "minEdgeRatio", "f32"),
    (0x58, "smoothingSizeFactor", "f32"),
    (0x5C, "smoothingSigma", "f32"),
    (0x60, "lowToneRangeLo", "i16"),
    (0x62, "lowToneRangeHi", "i16"),
    (0x64, "midLowToneRangeLo", "i16"),
    (0x66, "midLowToneRangeHi", "i16"),
    (0x68, "midHighToneRangeLo", "i16"),
    (0x6A, "midHighToneRangeHi", "i16"),
    (0x6C, "highToneRangeLo", "i16"),
    (0x6E, "highToneRangeHi", "i16"),
    (0x70, "nDecisionTreeNodes", "i32"),
    # +0x74 / +0x7c are the dei tree's count and array.  They are filled by
    # AnsToneHelperDpi from the `decisionTreeDei` key and read ONLY by
    # 0x101dc310 (``mov ebp,[esi+0x7c]; mov eax,[esi+0x74]``), which is not on
    # this file's call path.  Listed for layout completeness, never read here.
    (0x74, "nDecisionTreeNodesDei", "i32"),
    (0x78, "decisionTree", "ptr"),
    (0x7C, "deiDecisionTree", "ptr"),
)

PARAMS_OFFSET = {n: o for o, n, _k in TONEHELPER_PARAMS_FIELDS}

#: DPI key -> (params field(s)).  Order is the shipped file's own order.
DPI_KEYS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("maxValue", ("maxValue",), "i16"),
    ("thresholdMultiplier", ("thresholdMultiplier",), "f32"),
    ("thresholdReductionFactor", ("thresholdReductionFactor",), "f32"),
    ("minEdgeThreshold", ("minEdgeThreshold",), "i16"),
    ("minEdgeRatio", ("minEdgeRatio",), "f32"),
    ("smoothingSizeFactor", ("smoothingSizeFactor",), "f32"),
    ("smoothingSigma", ("smoothingSigma",), "f32"),
    ("lowToneRange", ("lowToneRangeLo", "lowToneRangeHi"), "i16"),
    ("midLowToneRange", ("midLowToneRangeLo", "midLowToneRangeHi"), "i16"),
    ("midHighToneRange", ("midHighToneRangeLo", "midHighToneRangeHi"), "i16"),
    ("highToneRange", ("highToneRangeLo", "highToneRangeHi"), "i16"),
    ("decisionTree", ("decisionTree",), "str"),
    ("decisionTreeDei", ("decisionTreeDei",), "str"),
)


@dataclass
class ToneHelperParams:
    """``AnsToneHelperParams`` — the fields this port actually consumes."""

    maxValue: int = 4095
    thresholdMultiplier: float = 1.5
    thresholdReductionFactor: float = 0.949
    minEdgeThreshold: int = 4
    minEdgeRatio: float = 0.1
    smoothingSizeFactor: float = 4.0
    smoothingSigma: float = 10.0
    lowToneRange: tuple[int, int] = (600, 1149)
    midLowToneRange: tuple[int, int] = (1150, 1549)
    midHighToneRange: tuple[int, int] = (1550, 1849)
    highToneRange: tuple[int, int] = (1850, 2449)
    #: ``decisionTree`` — the tree the two entry points ported here walk.
    decisionTree: str = DEFAULT_TREE
    #: ``decisionTreeDei`` — loaded by the DPI, walked by a DIFFERENT caller
    #: (``ColorNegativePath::CalcDei``).  Recorded so the parser is faithful to
    #: the file; **never read by anything in this module**.  Do not wire it in.
    decisionTreeDei: str = "deiTree1"
    #: The parsed ``decisionTree`` nodes, i.e. params+0x64/+0x6c.
    nodes: tuple["DecisionNode", ...] = ()

    def band(self, which: str) -> tuple[int, int]:
        return getattr(self, which + "ToneRange")


def parse_toneHelper_dpi(text: str) -> ToneHelperParams:
    """``AnsToneHelperDpi::readAscii`` — ``key = value`` lines, ``#`` comments.

    The shipped ``toneHelper-default.dpi`` sets every key in ``DPI_KEYS``; the
    ``key``/``version`` header lines are metadata (``key`` must also appear in
    ``toneHelper.map`` to be selectable) and are returned to the caller only
    through ``parse_toneHelper_dpi_raw``.
    """
    if not TONEHELPER_DPI_PORTED:
        _unported("TONEHELPER_DPI_PORTED", "AnsToneHelperDpi::readAscii", 0)
    raw = parse_toneHelper_dpi_raw(text)
    p = ToneHelperParams()
    for key, fields, kind in DPI_KEYS:
        if key not in raw:
            continue
        toks = raw[key].split()
        if kind == "str":
            setattr(p, key, toks[0])
        elif len(fields) == 2:
            setattr(p, key, (int(toks[0]), int(toks[1])))
        elif kind == "i16":
            setattr(p, key, int(toks[0]))
        else:
            setattr(p, key, f32(float(toks[0])))
    return p


def parse_toneHelper_dpi_raw(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


# ---------------------------------------------------------------------------
# the decision tree
# ---------------------------------------------------------------------------

NODE_STRIDE = 0x14          # 0x101db970  lea ecx,[eax+eax*4]; lea edx,[ebp+ecx*4]

#: Node field offsets, from the walker's own loads.
NODE_METRIC = 0x00          # 0x101db977  mov ecx, dword [edx]
NODE_THRESHOLD = 0x04       # 0x101dbada  fcom dword [edx + 4]
NODE_LESS_EQUAL = 0x08      # 0x101dbae4  mov eax, dword [edx + 8]
NODE_GREATER = 0x0C         # 0x101dbaec  mov eax, dword [edx + 0xc]
NODE_CLASS = 0x10           # 0x101dbafc  mov ecx, dword [edx + 0x10]


@dataclass(frozen=True)
class DecisionNode:
    """One 20-byte node of a ``decisionTree`` file."""

    metric: int          # index into METRIC_NAMES
    threshold: float     # stored and compared as float32
    less_equal: int      # node index taken when metric <  threshold
    greater: int         # node index taken when metric >= threshold
    cls: int             # only read on TERMINAL

    def pack(self) -> bytes:
        return struct.pack("<ifiii", self.metric, self.threshold,
                           self.less_equal, self.greater, self.cls)


def parse_decision_tree(text: str) -> tuple[DecisionNode, ...]:
    """``AnsToneHelperDpi::readDecisionTree`` on ``AllOnTree1``/``dTree1``.

    File shape (both shipped trees)::

        # free-form comment lines
        # nNodes =
        25
        # node   metric        threshold  lessEqual  greater  class
           0  LUM_STDDEV          1.000       1        24       4
           …

    ``#`` lines are comments — note ``AllOnTree1`` carries a *commented-out*
    node 0 (``LUM_STDDEV 285.044 1 12 2``) directly above the live one, which
    is why the live root threshold is 1.000 and not 285.044.  The first
    non-comment line is the node count; each subsequent line is
    ``index metric threshold lessEqual greater class``.  The leading index
    column is positional only — the walker indexes the array, so a file whose
    indices are not 0..n-1 in order would be mis-walked; both shipped trees
    are in order and this parser asserts it.
    """
    if not TONEHELPER_TREE_FILE_PORTED:
        _unported("TONEHELPER_TREE_FILE_PORTED",
                  "AnsToneHelperDpi::readDecisionTree", 0)
    rows: list[list[str]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        rows.append(s.split())
    if not rows:
        raise ToneHelperError("decision tree file has no data lines")
    n = int(rows[0][0])
    if len(rows) - 1 != n:
        raise ToneHelperError(
            f"decision tree claims {n} nodes, file has {len(rows) - 1}")
    nodes: list[DecisionNode] = []
    for i, row in enumerate(rows[1:]):
        idx, name, thr, le, gt, cls = row[:6]
        if int(idx) != i:
            raise ToneHelperError(
                f"node index column {idx} != position {i}; the walker indexes "
                f"the array, so out-of-order files would be mis-walked")
        if name not in METRIC_ID:
            raise ToneHelperError(f"unknown metric name {name!r}")
        nodes.append(DecisionNode(METRIC_ID[name], f32(float(thr)),
                                  int(le), int(gt), int(cls)))
    return tuple(nodes)


def verify_decision_tree(nodes: Sequence[DecisionNode],
                         node_count: int | None = None) -> None:
    """``AnsToneHelperParams::verifyDecisionTree`` (``0x101da3b0``).

    ``0x101db890`` calls it at ``0x101db8cf`` with ``(&status, *(impl+0x70),
    *(impl+0x78))`` — the node **count** and the node **array** — and bails on
    a non-OK status before walking a single node.  A NULL array or a zero
    count is rejected outright with ``"A NULL decision tree is invalid."``
    (``0x101da410``, ``AnsToneHelperParams.cpp:316``); everything else is
    ``AnsToneHelperParams::checkDecisionNode`` (``0x101d9db0``), which
    recurses from node 0 down both children (``0x101d9fc1``/``0x101da015``)
    and enforces, per node:

    * ``metric == 1`` (TERMINAL) -> both gotos must be ``-1``, else
      ``", the TERMINAL node gotos are not -1."`` (line 343, ``0x101d9e26``).
    * otherwise ``1 <= metric <= 0x1e`` (``0x101d9f7b  jl`` /
      ``0x101d9f81  cmp ecx, 0x1e ; jg``), else ``", metric N is not
      supported."`` (line 357).  **Metric 0 / NONE is rejected**, which is why
      the walker's ``default`` arm (ST(0) left unchanged) is unreachable for
      any tree that got past this check.
    * ``index < lessEqualGoto < nNodes`` (``0x101d9f8d  cmp ecx, eax ; jle``
      and ``0x101d9f9c  cmp ecx, edi ; jge``), else ``", the lessEqualGoto
      value (N) is out of range."`` (line 372); same pair for
      ``greaterGoto`` at ``0x101d9fa7``/``0x101d9faf``, reported at line 385
      (``0x101da0c5``, ``", the greaterGoto value ("``).

    The strict ``> index`` half is load-bearing: it makes the tree a
    forward-only DAG, which is the guarantee that the walker's unbounded
    ``while`` loop terminates.
    """
    n = len(nodes) if node_count is None else node_count
    if not nodes or n == 0:
        raise ToneHelperError(
            f"A NULL decision tree is invalid. "
            f"[AnsToneHelperParams::verifyDecisionTree, {SRC_FILE_PARAMS}:316]")

    def check(i: int) -> None:
        nd = nodes[i]
        if nd.metric == METRIC_TERMINAL:
            if nd.less_equal != -1 or nd.greater != -1:
                raise ToneHelperError(
                    f"In node number {i}, the TERMINAL node gotos are not -1. "
                    f"[AnsToneHelperParams::checkDecisionNode, "
                    f"{SRC_FILE_PARAMS}:343]")
            return
        if not 1 <= nd.metric <= 30:
            raise ToneHelperError(
                f"In node number {i}, metric {nd.metric} is not supported. "
                f"[AnsToneHelperParams::checkDecisionNode, "
                f"{SRC_FILE_PARAMS}:357]")
        for label, tgt, line in (("lessEqualGoto", nd.less_equal, 372),
                                 ("greaterGoto", nd.greater, 385)):
            if not i < tgt < n:
                raise ToneHelperError(
                    f"In node number {i}, the {label} value ({tgt}) is out of "
                    f"range. [AnsToneHelperParams::checkDecisionNode, "
                    f"{SRC_FILE_PARAMS}:{line}]")
        check(nd.less_equal)
        check(nd.greater)

    check(0)


@dataclass
class TreeWalkResult:
    """What ``0x101db890`` writes back into the Impl."""

    terminal_node: int   # impl+0x12c  (results+0xac)
    tone_value: int      # impl+0x134  (results+0xb4) -- 1 or 2
    scene_class: int     # impl+0x138  (results+0xb8) -- 2, 3 or clamped 3
    path: tuple[int, ...] = ()   # visited node indices, harness aid only


def walk_decision_tree(nodes: Sequence[DecisionNode],
                       metrics: dict[int, float]) -> TreeWalkResult:
    """``0x101db890`` — the 30-way walker.

    ``metrics`` maps a metric id to the float32 already sitting at
    ``impl + metric_impl_offset(id)``.

    Exactly what the assembly does, in order:

    * ``0x101db964``  ``fld dword [0x10575674]`` — ST(0) starts at **0.0f**.
    * ``0x101db970``  ``node = base + i*0x14`` ; ``id = node[0]``.
    * ``0x101db97a``  ``cmp ecx, 0x1d ; ja default`` after ``dec ecx``, so
      ids 1..0x1e dispatch and **anything else (including 0/NONE) falls
      through to the compare with ST(0) unchanged** — i.e. it re-uses the
      previous node's metric value.  Modelled, not smoothed over.
    * ids 2..0x1e  ``fstp st(0) ; fld dword [esi + off]`` — replace ST(0).
    * ``0x101dbada``  ``fcom dword [edx+4] ; fnstsw ax ; test ah,5 ; jp``.
      ``test ah,5`` masks C0 (bit 0) and C2 (bit 2); PF is set when an even
      number of those bits is set.  For an ordered compare C2 is 0, so
      ``jp`` is taken exactly when C0 == 0, i.e. **metric >= threshold takes
      ``[edx+0xc]`` (greater) and metric < threshold takes ``[edx+8]``
      (lessEqual)**.  Equality goes to *greater* — the file's column name
      "lessEqual" is off by the boundary case and the assembly wins.
    * ``0x101dbaf4``  TERMINAL: ``impl+0x12c = i`` (the node index, not the
      class), then ``class >= 3 -> (impl+0x134, impl+0x138) = (2, 3)`` else
      ``(1, class)``.  ``0x101dbaff  mov eax, 3`` then ``cmp ecx, eax ; jl``
      is where the 3 comes from; the clamp is why a class-4 terminal reports
      3 rather than 4.
    """
    if not TONEHELPER_DECISION_TREE_PORTED:
        _unported("TONEHELPER_DECISION_TREE_PORTED", "tree walk", WALK_TREE)
    verify_decision_tree(nodes)
    st0 = 0.0                                    # 0x101db964
    i = 0
    path: list[int] = []
    seen = 0
    while True:
        path.append(i)
        seen += 1
        if seen > 4 * len(nodes) + 8:
            raise ToneHelperError("decision tree walk does not terminate")
        nd = nodes[i]
        if nd.metric == METRIC_TERMINAL:
            cls = nd.cls
            if cls >= 3:                          # 0x101dbb04  cmp ecx, 3
                return TreeWalkResult(i, 2, 3, tuple(path))
            return TreeWalkResult(i, 1, cls, tuple(path))
        if 2 <= nd.metric <= 30:
            st0 = metrics[nd.metric]
        # metric id 0 (NONE) or anything above 30: ST(0) is left alone.
        i = nd.greater if st0 >= nd.threshold else nd.less_equal


# ---------------------------------------------------------------------------
# AnsHistogram
# ---------------------------------------------------------------------------


@dataclass
class AnsHistogram:
    """``0x10278140``'s object: ``{nBins, _, min, max, uninit, data, base}``.

    The ctor only initialises when ``data != 0 and minValue < maxValue``;
    otherwise ``uninit`` stays 1 and every method throws
    ``"Histogram was not initialized."``.  ``base`` (``+0x18``) is
    ``data - 4*minValue``, i.e. the value-indexed view — reproduced here by
    indexing ``bins`` with the raw value and keeping ``min_value`` around.
    """

    n_bins: int
    bins: list[int]
    min_value: int
    max_value: int

    @property
    def initialised(self) -> bool:
        return bool(self.bins) and self.min_value < self.max_value

    def _range(self, frm: int, to: int) -> tuple[int, int]:
        """The shared ``from >= to -> use [m_minValue, m_maxValue]`` rule."""
        if frm < to:
            if frm < self.min_value:
                raise ToneHelperError(
                    f"The parameter 'from' is less than m_minValue. "
                    f"[{SRC_FILE_HIST}]")
            if to > self.max_value:
                raise ToneHelperError(
                    f"The parameter 'to' is greater than m_maxValue. "
                    f"[{SRC_FILE_HIST}]")
            return frm, to
        return self.min_value, self.max_value

    # -- 0x10278df0 --------------------------------------------------------
    def calc_work(self, lut: Sequence[int], frm: int, to: int
                  ) -> tuple[int, float]:
        """``AnsHistogram::calcWork`` -> ``(count, work)``.

        ``work = sum(bins[v] * abs(lut[v] - v) for v in from..to)`` and
        ``count = sum(bins[v] ...)``.

        The absolute value is not an ``fabs``: the loop forms the signed
        int32 product ``bins[v] * (lut[v] - v)`` and then picks ``fisub``
        (``0x10278fab``) or ``fiadd`` (``0x1027907f``) on the sign of
        ``lut[v] - v``, which is the same thing for a non-negative bin count.
        ``lut`` is read with ``movsx ... word`` (``0x10278f91``), i.e. as
        **signed** int16.

        Every addend is an int32 pushed through ``fiadd``/``fisub`` and the
        accumulator never leaves ST(0) between ``0x10278f6e``'s
        ``fld [0x10575674]`` (0.0f) and ``0x10279161``'s ``fstp dword [eax]``,
        so there is exactly one rounding, at the end.  ``count`` is an integer
        register (EBP), not an FPU value.
        """
        if not TONEHELPER_HISTOGRAM_PORTED:
            _unported("TONEHELPER_HISTOGRAM_PORTED", "calcWork",
                      HIST_CALC_WORK)
        if not self.initialised:
            raise ToneHelperError(
                f"Histogram was not initialized. [{SRC_FILE_HIST}:458]")
        frm, to = self._range(frm, to)
        count = 0
        work = 0.0
        for v in range(frm, to + 1):
            b = self.bins[v]
            d = _i16(lut[v]) - v
            count += b
            work += float(_i32(b * d)) if d >= 0 else float(-_i32(b * d))
        return _i32(count), f32(work)

    # -- 0x102781d0 --------------------------------------------------------
    def calc_distance(self, lut: Sequence[int], out: "AnsHistogram",
                      frm: int, to: int) -> tuple[float, float]:
        """``AnsHistogram::calcDistance`` -> ``(distance, intersection)``.

        Maps this histogram through ``lut`` into ``out`` and measures how far
        it moved::

            out[from..to] = 0
            for v in from..to:  out[lut[v]] += self[v]
            distance     = sum(  abs(out[v] - self[v]) )
            intersection = sum( max(out[v] - self[v], 0) )

        Both accumulators are integers pushed through ``fiadd``/``fisub`` and
        stay in ST(0) until the two ``fstp dword`` stores, exactly as in
        ``calcWork``.  Note the second accumulator is only fed on the
        non-negative side — that asymmetry is what makes it an *intersection*
        (mass gained) rather than a signed total, which is always 0.
        """
        if not TONEHELPER_HISTOGRAM_PORTED:
            _unported("TONEHELPER_HISTOGRAM_PORTED", "calcDistance",
                      HIST_CALC_DISTANCE)
        if not self.initialised:
            raise ToneHelperError(
                f"The input histogram was not initialized. "
                f"[{SRC_FILE_HIST}:199]")
        if not out.initialised:
            raise ToneHelperError(
                f"The output histogram was not initialized. "
                f"[{SRC_FILE_HIST}:207]")
        if (self.min_value != out.min_value
                or self.max_value != out.max_value):
            raise ToneHelperError(
                "The input and output histograms have different ranges. "
                f"[{SRC_FILE_HIST}:232]")
        frm, to = self._range(frm, to)
        for v in range(frm, to + 1):
            out.bins[v] = 0
        for v in range(frm, to + 1):
            out.bins[_i16(lut[v])] = _i32(out.bins[_i16(lut[v])]
                                          + self.bins[v])
        dist = 0.0
        inter = 0.0
        for v in range(frm, to + 1):
            d = _i32(out.bins[v] - self.bins[v])
            if d < 0:
                dist -= float(d)
            else:
                dist += float(d)
                inter += float(d)
        return f32(dist), f32(inter)

    # -- 0x10278730 --------------------------------------------------------
    def calc_stats(self, frm: int, to: int) -> tuple[int, float, float,
                                                     float, float, float]:
        """``AnsHistogram::calcStats`` -> ``(count, average, avgDev, stdDev,
        skew, kurtosis)`` — the six out-parameters in the order
        ``0x101db020`` passes them.

        THIS ONE IS NOT UNIFORM AND THE ASYMMETRY IS REAL
        =================================================
        The moment loop is 4x unrolled and the compiler spilled different
        quantities to different-width slots in each of the four positions.
        Transcribed instruction by instruction from ``0x10278b5a``..
        ``0x10278c76``; the stack slots are (raw ``esp`` displacements, with
        ``asm.var`` off, because r2's synthetic ``var_NNh`` names alias here)::

            [esp+0x10]  mean, float32       [esp+0x50]  M2, float32 slot
            [esp+0x14]  v / d scratch       [esp+0x54]  A  (mean-dev), f32 slot
            [esp+0x18]  m4, float32 slot    [esp+0x2c]  (float)count
            [esp+0x1c]  sum1 then scratch   [esp+0x38]  1/(float)count, f32
            [esp+0x20]  m3, float32 slot    [esp+0x30]  stdDev

        Prologue::

            sum1  = sum(bins[v] * v)          ST(0), int addends, ONE rounding
                                              (fst dword [esp+0x1c])
            count = sum(bins[v])              integer register (EDI)
            if count < 2:  average = f32(sum1); every other output = 0.0f
            nf    = f32(count)                        fild ; fstp dword
            invN  = 1.0f / nf                         ST(0), then fst -> f32
            mean  = f32(invN_unrounded * f32(sum1))   fmul ; fst dword [esp+0x10]
            mi    = (int)mean            _ftol, truncation toward zero
            if (float)mi > mean: mi -= 1              -> floor(mean)

        Then A, M2, m3, m4 accumulate over ``from..to``, with ``d = v - mean``
        and ``A`` **subtracting** while ``v <= mi`` and **adding** after (that
        is the mean-absolute-deviation split, done branchlessly by running two
        separate loops).  The rounding per unrolled slot:

        ===========  ==========  ======  ======  =========  =========
        slot          d           A       M2      m3         m4
        ===========  ==========  ======  ======  =========  =========
        0 (v+0)      float32     f32     f32     ST(0)      ST(0)*
        1 (v+1)      ST(0)       f32     f32     float32    ST(0)
        2 (v+2)      ST(0)       f32     f32     float32    float32
        3 (v+3)      float32     f32     f32     ST(0)      float32
        ===========  ==========  ======  ======  =========  =========

        (* slot 0's ``m4`` term is formed from the **float32-rounded**
        ``c*d^3`` reloaded at ``0x101db9b``/``0x10278b9b``, not from the
        register copy — so it is ``f32(c*d^3) * d`` there and ``c*d^3 * d`` in
        slots 1 and 2.  Slot 3 does the same reload trick.)

        The two remainder loops (``0x10278c93`` for ``v <= mi`` and
        ``0x10278cd1`` for ``v > mi``) keep **all four** accumulators in
        ST(0..3) with no rounding at all.

        Epilogue::

            avgDev   = f32(invN_f32 * A)
            var      = M2 / (float)(count - 1)          ST(0)
            if var == 0:  stdDev = 0; skew = m3; kurtosis = last m4 spill
            else:
              stdDev   = f32(sqrt(var))
              skew     = ((nf * f32(stdDev)) * var)  divided into m3
              kurtosis = ((nf * var) * var)          divided into m4, minus 3.0f

        The ``var == 0`` branch (``0x10278d32  jnp 0x10278d66``) leaves the
        raw third moment in ST(0) as "skew" and whatever the loop last spilled
        to ``[esp+0x18]`` as "kurtosis".  It is a degenerate-histogram path,
        but it is modelled rather than zeroed because guessing here is exactly
        how a port silently diverges.
        """
        if not TONEHELPER_HISTOGRAM_PORTED:
            _unported("TONEHELPER_HISTOGRAM_PORTED", "calcStats",
                      HIST_CALC_STATS)
        if not self.initialised:
            raise ToneHelperError(
                f"Histogram was not initialized. [{SRC_FILE_HIST}:310]")
        frm, to = self._range(frm, to)

        count = 0
        sum1 = 0.0
        for v in range(frm, to + 1):
            b = self.bins[v]
            count += b
            sum1 += float(_i32(b * v))
        count = _i32(count)
        sum1 = f32(sum1)                       # 0x10278958  fst dword [esp+0x1c]

        if count < 2:                          # 0x10278ac7  cmp edi, 1 ; jle
            return count, sum1, 0.0, 0.0, 0.0, 0.0

        nf = f32(count)                        # 0x10278af8/afc
        inv_n = 1.0 / nf                       # ST(0), 0x10278b00/06
        inv_n_f32 = f32(inv_n)                 # 0x10278b0a  fst dword [esp+0x38]
        mean = f32(inv_n * sum1)               # 0x10278b0e/12
        mi = int(mean)                         # 0x10278b16  _ftol (truncate)
        if float(mi) > mean:                   # 0x10278b25..b31
            mi -= 1

        a = 0.0        # [esp+0x54], always via memory
        m2 = 0.0       # [esp+0x50], always via memory
        m3 = 0.0       # ST(1) across the unrolled loop, [esp+0x20] within it
        # m4 needs TWO variables.  ``fst dword [esp+0x18]`` at 0x10278c72
        # writes the rounded copy but leaves the unrounded value in ST(0);
        # the next unrolled iteration discards ST(0) (0x10278b5a ``fstp st(0)``)
        # and re-reads the rounded memory copy, but on the *last* iteration
        # the loop falls through and the two remainder loops keep accumulating
        # into the UNROUNDED register value.  Collapsing the two costs exactly
        # one float32 ulp of kurtosis on a broad histogram -- found by this
        # file's own gauss case, not reasoned about in advance.
        m4_reg = 0.0   # ST(0)
        m4_mem = 0.0   # [esp+0x18]

        v = frm
        # ---- 0x10278b5a: 4x unrolled, only over [from .. mi] --------------
        if mi - frm + 1 >= 4:
            while v <= mi - 3:
                # slot 0 -- d float32; m4 re-read from memory, m3 from ST(1)
                d = f32(v - mean)
                c = float(self.bins[v])
                a = f32(a - c * d)
                m2 = f32(m2 + c * d * d)
                t = f32(c * d * d * d)          # fst dword [esp+0x1c]
                m3 = m3 + c * d * d * d         # faddp st(1) -- unrounded
                m4_reg = m4_mem + t * d         # fadd dword [esp+0x18]
                # slot 1 -- d stays in ST(0); m3 spills to float32
                d = (v + 1) - mean
                c = float(self.bins[v + 1])
                a = f32(a - c * d)
                m2 = f32(m2 + c * d * d)
                m3 = f32(m3 + c * d * d * d)    # fstp dword [esp+0x20]
                m4_reg = m4_reg + c * d * d * d * d
                # slot 2 -- both m3 and m4 spill; m4's register copy is popped
                d = (v + 2) - mean
                c = float(self.bins[v + 2])
                a = f32(a - c * d)
                m2 = f32(m2 + c * d * d)
                m3 = f32(m3 + c * d * d * d)
                m4_mem = f32(m4_reg + c * d * d * d * d)   # fstp -> memory only
                m4_reg = m4_mem
                # slot 3 -- d float32 again; m3 back into ST(0) unrounded,
                # m4 written to memory but kept unrounded in ST(0)
                d = f32((v + 3) - mean)
                c = float(self.bins[v + 3])
                a = f32(a - c * d)
                m2 = f32(m2 + c * d * d)
                t = f32(c * d * d * d)
                m3 = m3 + c * d * d * d         # fadd dword [esp+0x20]
                m4_reg = m4_mem + t * d         # fadd dword [esp+0x18]
                m4_mem = f32(m4_reg)            # fst  dword [esp+0x18]
                v += 4
        # ---- 0x10278c84: A and M2 come back from their float32 slots ------
        a = f32(a)
        m2 = f32(m2)
        m4 = m4_reg
        # ---- 0x10278c93: the rest of [from .. mi], nothing rounded -------
        if v <= mi:
            while v <= mi:
                d = v - mean
                c = float(self.bins[v])
                a = a - c * d
                m2 = m2 + c * d * d
                m3 = m3 + c * d * d * d
                m4 = m4 + c * d * d * d * d
                v += 1
            m4_mem = f32(m4)               # 0x10278cc4  fst dword [esp+0x18]
        # ---- 0x10278cd1: (mi .. to], A now ADDS --------------------------
        if v <= to:
            while v <= to:
                d = v - mean
                c = float(self.bins[v])
                a = a + c * d
                m2 = m2 + c * d * d
                m3 = m3 + c * d * d * d
                m4 = m4 + c * d * d * d * d
                v += 1
            m4_mem = f32(m4)               # 0x10278d00  fst dword [esp+0x18]

        # ---- 0x10278d06 --------------------------------------------------
        avg_dev = f32(inv_n_f32 * a)
        var = m2 / float(count - 1)
        if var == 0.0:                     # 0x10278d2b  fucompp ; jnp
            return count, mean, avg_dev, 0.0, f32(m3), m4_mem
        std = f32(math.sqrt(var))
        skew = f32(m3 / ((nf * std) * var))
        kurt = f32(m4 / ((nf * var) * var) - f32(3.0))
        return count, mean, avg_dev, std, skew, kurt


def _i32(v: int) -> int:
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


def _i16(v: int) -> int:
    v &= 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


# ---------------------------------------------------------------------------
# AnsToneHelperResults — impl+0x80, 0x2f dwords (0xbc bytes)
# ---------------------------------------------------------------------------

#: ``(results offset, impl offset, name, kind)``.  The heap-pointer slots are
#: named for what ``allocateMemory`` puts there and what ``0x101da800`` /
#: ``0x101da8c0`` free; they are raw addresses in the DLL and meaningless to a
#: host caller, but they are inside the 0xbc bytes the getter copies out, so
#: they are part of the layout whether or not anyone reads them.
TONEHELPER_RESULTS_FIELDS: tuple[tuple[int, str, str], ...] = (
    (0x00, "nPixels", "i32"),            # impl+0x80, width*height (image path)
    (0x04, "_imageBuf", "ptr"),          # impl+0x84
    (0x08, "_lumHist", "ptr"),           # impl+0x88   (n+1) * int32
    (0x0C, "_lapBuf", "ptr"),            # impl+0x8c
    (0x10, "threshold", "i32"),          # impl+0x90   edge threshold used
    (0x14, "_scratch14", "ptr"),         # impl+0x94
    (0x18, "_edgeHist", "ptr"),          # impl+0x98   (n+1) * int32
    (0x1C, "_scratch1c", "ptr"),         # impl+0x9c
    (0x20, "_scratch20", "ptr"),         # impl+0xa0
    (0x24, "_distHist", "ptr"),          # impl+0xa4   (n+1) * int32
    (0x28, "_scratch28", "ptr"),         # impl+0xa8
    (0x2C, "_toneLut", "ptr"),           # impl+0xac   (n+1) * int16
    (0x30, "lum", "group"),              # impl+0xb0   0x3c-byte metric group
    (0x6C, "edge", "group"),             # impl+0xec   0x3c-byte metric group
    (0xA8, "exposure", "f32"),           # impl+0x128  metric id 30
    (0xAC, "terminalNode", "i32"),       # impl+0x12c
    (0xB0, "_unused_b0", "i32"),         # impl+0x130
    (0xB4, "toneHelperValue", "i32"),    # impl+0x134  <-- crosses the shell
    (0xB8, "sceneClass", "i32"),         # impl+0x138
)

RESULTS_SIZE = 0xBC
RESULTS_IMPL_OFFSET = 0x80
RESULTS_TONE_VALUE_OFFSET = 0xB4      # what pakon_autotone reads


@dataclass
class ToneHelperResults:
    """The 0xbc bytes ``0x1010bb40`` rep-movsd's into the shell's buffer."""

    nPixels: int = 0
    threshold: int = 0
    lum: dict[str, float] = field(default_factory=dict)
    edge: dict[str, float] = field(default_factory=dict)
    exposure: float = 0.0
    terminalNode: int = 0
    toneHelperValue: int = 0
    sceneClass: int = 2
    #: The heap pointers are not modelled as addresses; the sizes allocateMemory
    #: would have used are recorded instead, for the golden to compare against.
    buffer_sizes: dict[str, int] = field(default_factory=dict)

    def to_bytes(self) -> bytes:
        """Pack exactly as the getter would see it (pointers as 0).

        ``pakon_autotone`` only reads ``+0xb4``, but it memcpys the whole
        0xbc, and ``AUTOTONE_WORK_LAYOUT['AnsToneHelperResults']`` names four
        more offsets, so the packing has to be right at all of them.
        """
        if not TONEHELPER_RESULTS_LAYOUT_PORTED:
            _unported("TONEHELPER_RESULTS_LAYOUT_PORTED", "getResults",
                      IMPL_GET_RESULTS)
        b = bytearray(RESULTS_SIZE)
        struct.pack_into("<i", b, 0x00, _i32(self.nPixels))
        struct.pack_into("<i", b, 0x10, _i32(self.threshold))
        for base, group in ((0x30, self.lum), (0x6C, self.edge)):
            for off, name, kind in METRIC_GROUP_FIELDS:
                if name not in group:
                    continue
                if kind == "i32":
                    struct.pack_into("<i", b, base + off, int(group[name]))
                else:
                    struct.pack_into("<f", b, base + off, f32(group[name]))
        struct.pack_into("<f", b, 0xA8, f32(self.exposure))
        struct.pack_into("<i", b, 0xAC, _i32(self.terminalNode))
        struct.pack_into("<i", b, 0xB4, _i32(self.toneHelperValue))
        struct.pack_into("<i", b, 0xB8, _i32(self.sceneClass))
        return bytes(b)


# ---------------------------------------------------------------------------
# AnsToneHelperCapabilityImpl
# ---------------------------------------------------------------------------

#: ``0x101da6b0``'s seven bound checks, in the order it makes them.
#: ``(field, low, high, badFieldIndex)``; ``high is None`` marks the two int16
#: fields, which get a lower bound only (``cmp ax, word [...]; jge ok``).
#: Every bound is the literal at the cited ``.rdata`` address, decoded:
#:
#:   0x1059a2f8 = 0      (i16)   0x1059a300/04 = 1.0f / 2.0f
#:   0x1059a30c/10 = 0.5f / 0x3f7fbe77   0x1059a318 = 0 (i16)
#:   0x1059a320/24 = 0.0f / 1.0f         0x1059a32c/30 = 1.0f / 10.0f
#:   0x1059a338/3c = 1.0f / 50.0f
#:
#: ``0x3f7fbe77`` is the float32 nearest 0.999; it is spelled as the exact bit
#: pattern here because 0.999 as a Python float is a *different* number and the
#: comparison is an inclusive ``fcomp`` against the float32.
FLT_0_999 = struct.unpack("<f", struct.pack("<I", 0x3F7FBE77))[0]

PARAM_CHECKS: tuple[tuple[str, float, float | None, int], ...] = (
    ("maxValue", 0, None, 1),
    ("thresholdMultiplier", 1.0, 2.0, 2),
    ("thresholdReductionFactor", 0.5, FLT_0_999, 3),
    ("minEdgeThreshold", 0, None, 4),
    ("minEdgeRatio", 0.0, 1.0, 5),
    ("smoothingSizeFactor", 1.0, 10.0, 6),
    ("smoothingSigma", 1.0, 50.0, 7),
)


def check_params(p: ToneHelperParams) -> int:
    """``0x101da6b0`` — returns 0, or raises with the bad-field index.

    The vendor returns ``-1`` and stores the 1-based field index through its
    out-parameter; ``0x101dd1b0``/``0x101dcc50`` then throw
    ``"Bad field(#N) in AnsToneHelperParams structure!"``
    (``AnsToneHelperCapabilityImpl.cpp:105``).  The bounds themselves are the
    immediates at ``0x1059a2f8``..``0x1059a33c`` and are listed in
    ``PARAM_CHECKS``; every shipped ``toneHelper-*.dpi`` passes.
    """
    if not TONEHELPER_PARAM_CHECK_PORTED:
        _unported("TONEHELPER_PARAM_CHECK_PORTED", "param check", PARAM_CHECK)
    for name, lo, hi, idx in PARAM_CHECKS:
        v = getattr(p, name)
        if hi is None:
            bad = v < lo
        else:
            bad = not (f32(lo) <= f32(v) <= f32(hi))
        if bad:
            raise ToneHelperError(
                f"Bad field(#{idx}) in AnsToneHelperParams structure! "
                f"[AnsToneHelperCapabilityImpl::analyze, {SRC_FILE_IMPL}:105]")
    return 0


def allocate_memory(p: ToneHelperParams, width: int, height: int
                    ) -> dict[str, int]:
    """``AnsToneHelperCapabilityImpl::allocateMemory`` (``0x101dabe0``).

    Two things matter to a host port:

    1. It **zeroes exactly 0x2f dwords starting at impl+0x80** — the whole
       ``AnsToneHelperResults`` window — at ``0x101dac..``.  That is why a
       results struct out of an early-failing analyze is all zeros rather than
       stale, and why ``nPixels``/``threshold`` are 0 on the histogram-fed
       path (nothing there ever sets them).
    2. The buffer sizes, as a function of ``n = maxValue + 1``.  The
       ``width < 1 || height < 1`` branch — which is exactly what the
       histogram-fed entry point takes, since ``0x101dd254`` passes
       ``(-1, -1)`` — allocates only the four value-indexed buffers and skips
       every image-sized one.

    Returns the size table; no memory is actually reserved here, the Python
    side keeps lists.
    """
    if not TONEHELPER_ALLOCATE_PORTED:
        _unported("TONEHELPER_ALLOCATE_PORTED", "allocateMemory",
                  ALLOCATE_MEMORY)
    n = p.maxValue + 1
    sizes = {
        "_lumHist": n * 4,     # impl+0x88
        "_edgeHist": n * 4,    # impl+0x98
        "_distHist": n * 4,    # impl+0xa4
        "_toneLut": n * 2,     # impl+0xac
    }
    if width >= 1 and height >= 1:
        sizes.update({
            "_imageBuf": width * height * 2,   # impl+0x84
            "_lapBuf": width * height * 2,     # impl+0x8c
        })
    return sizes


# ---------------------------------------------------------------------------
# 0x101db020 — the metric producer
# ---------------------------------------------------------------------------


def compute_metrics(p: ToneHelperParams, lum_hist: Sequence[int],
                    edge_hist: Sequence[int], tone_lut: Sequence[int]
                    ) -> tuple[dict[str, float], dict[str, float]]:
    """``0x101db020`` -> ``(lumGroup, edgeGroup)`` as name->value dicts.

    Structure, straight off the disassembly:

    * ``0x101db088``/``0x101db0a1``/``0x101db0c1`` construct three
      ``AnsHistogram`` objects, all ``(nBins = maxValue+1, min = 0,
      max = maxValue)``: over ``impl+0x88`` (luminance), ``impl+0x98`` (edge)
      and ``impl+0xa4`` (the calcDistance scratch output).
    * ``0x101db100`` loops twice — ``var_2ch`` steps 0, 4 and exits at 8
      (``0x101db59f  cmp eax, 8 ; jl``).  Pass 0 pairs the luminance histogram
      with the metric group at ``impl+0xb0``, pass 1 the edge histogram with
      ``impl+0xec``.
    * per pass: ``calcStats(0, 0, …)`` — the two zeros make it use the
      histogram's own full range — then four ``calcWork`` calls over
      ``lowToneRange``, ``midLowToneRange``, ``midHighToneRange``,
      ``highToneRange``, then ``calcDistance``.
    * the two normalisation blocks, which are deliberately **asymmetric** and
      are transcribed literally below.
    """
    if not TONEHELPER_METRICS_PORTED:
        _unported("TONEHELPER_METRICS_PORTED", "compute metrics",
                  COMPUTE_METRICS)
    n_bins = p.maxValue + 1
    scratch = AnsHistogram(n_bins, [0] * n_bins, 0, p.maxValue)
    out: list[dict[str, float]] = []

    for bins in (lum_hist, edge_hist):
        h = AnsHistogram(n_bins, list(bins), 0, p.maxValue)
        g: dict[str, float] = {}

        (g["count"], g["average"], g["avgDev"], g["stdDev"], g["skew"],
         g["kurtosis"]) = h.calc_stats(0, 0)

        c_low, w_low = h.calc_work(tone_lut, *p.lowToneRange)
        c_mlo, w_mlo = h.calc_work(tone_lut, *p.midLowToneRange)
        c_mhi, w_mhi = h.calc_work(tone_lut, *p.midHighToneRange)
        c_hi, w_hi = h.calc_work(tone_lut, *p.highToneRange)
        total = _i32(c_low + c_mlo + c_mhi + c_hi)   # ebp, 0x101db4be

        # ---- 0x101db4c6 .. 0x101db530 -----------------------------------
        # scale = 1.0f / (float)total, in ST(0) (fild dword ; fdivr [1.0f]).
        # `total` is the sum of the four calcWork counts, accumulated in EBP
        # (0x101db289, 0x101db361, 0x101db403, 0x101db4be) -- an integer.
        scale = f32(1.0) / float(total)
        e_low = scale * w_low                        # fmul dword [esi+4]
        e_mlo = scale * w_mlo                        # fmul dword [esi+8]
        e_mhi = scale * w_mhi                        # fmul dword [esi+0x10]
        e_hi = scale * w_hi                          # fmul dword [ebx]
        g["workLow"] = f32(e_low)                    # fst  dword [esi+4]
        g["workMidLow"] = f32(e_mlo)                 # fst  dword [esi+8]
        g["workMidHigh"] = f32(e_mhi)                # fstp dword [esi+0x10]
        g["workHigh"] = f32(e_hi)                    # fstp dword [ebx]
        # sumLow adds the UNROUNDED products still on the FPU stack
        # (faddp st(1) at 0x101db50a) ...
        sum_low = e_low + e_mlo
        g["workSumLow"] = f32(sum_low)               # fst dword [esi+0xc]
        # ... whereas sumHigh reloads the two float32 spills the code made at
        # 0x101db4f5 / 0x101db500 (fld dword [esp+0x2c]; fadd dword [...]),
        # so it adds the ROUNDED values.  Not a typo -- the asymmetry is real
        # and it is the kind of thing only the disassembly can tell you.
        sum_high = g["workMidHigh"] + g["workHigh"]
        g["workSumHigh"] = f32(sum_high)             # fst dword [esi+0x18]
        # workTotal adds the two still-unrounded sums (fadd st(1), 0x101db52b).
        g["workTotal"] = f32(sum_high + sum_low)

        # ---- calcDistance, 0x101db532 -----------------------------------
        dist, inter = h.calc_distance(tone_lut, scratch, 0, 0)

        # ---- 0x101db596 .. 0x101db5b6 -----------------------------------
        # scale2 = 1.0f / (float)count, `count` being calcStats' own
        # out-parameter at [esi] (fild dword [esi]), NOT the calcWork total.
        scale2 = f32(1.0) / float(g["count"])
        g["distance"] = f32(scale2 * dist)
        g["intersection"] = f32(scale2 * inter)

        out.append(g)

    return out[0], out[1]


def metrics_by_id(lum: dict[str, float], edge: dict[str, float],
                  exposure: float) -> dict[int, float]:
    """Lay the two groups out the way the walker's switch arms read them."""
    name_for = {
        "LUM_WORK_LOW": ("lum", "workLow"),
        "LUM_WORK_MIDLOW": ("lum", "workMidLow"),
        "LUM_WORK_SUMLOW": ("lum", "workSumLow"),
        "LUM_WORK_MIDHIGH": ("lum", "workMidHigh"),
        "LUM_WORK_HIGH": ("lum", "workHigh"),
        "LUM_WORK_SUMHIGH": ("lum", "workSumHigh"),
        "LUM_WORK_TOTAL": ("lum", "workTotal"),
        "LUM_DISTANCE": ("lum", "distance"),
        "LUM_INTERSECTION": ("lum", "intersection"),
        "LUM_AVERAGE": ("lum", "average"),
        "LUM_AVGDEV": ("lum", "avgDev"),
        "LUM_STDDEV": ("lum", "stdDev"),
        "LUM_SKEW": ("lum", "skew"),
        "LUM_KURTOSIS": ("lum", "kurtosis"),
    }
    for k, v in list(name_for.items()):
        name_for["EDGE" + k[3:]] = ("edge", v[1])
    groups = {"lum": lum, "edge": edge}
    ids = {}
    for mid in range(2, 31):
        name = METRIC_NAMES[mid]
        if name == "EXPOSURE":
            ids[mid] = f32(exposure)
        else:
            grp, fld = name_for[name]
            ids[mid] = f32(groups[grp][fld])
    return ids


# ---------------------------------------------------------------------------
# the two entry points
# ---------------------------------------------------------------------------


def analyze_with_histograms(p: ToneHelperParams, lum_hist: Sequence[int],
                            edge_hist: Sequence[int], tone_lut: Sequence[int],
                            exposure: float | int | None) -> ToneHelperResults:
    """``AnsToneHelperCapabilityImpl::analyze`` (``0x101dd1b0``).

    Reached through Cap ``0x1010c3b0`` from ``analyzeAutoTone``'s
    ``th.acquireHist`` call site (``0x100fc36a``).  This is the variant that
    runs on the shipped CN-Enhanced path.

    Order of operations, with the VAs:

    ===========  ==========================================================
    0x101dd201   ``check_params`` -> "Bad field(#N)…" on failure
    0x101dd2f0   ``0x101da8c0`` — free every buffer, reset
    0x101dd2fa   ``allocateMemory(-1, -1)`` — the no-image branch
    0x101dd2fd   ``impl+0x128 = *exposureArg`` (or 0 when the pointer is NULL)
    0x101dd3xx   three ``rep movsd``: lumHist -> impl+0x88 (n+1 dwords),
                 edgeHist -> impl+0x98 (n+1 dwords), tone -> impl+0xac
                 (2*(n+1) bytes)
    0x101dd43d   ``0x101db020`` — the 29 metrics
    0x101dd4xx   ``0x101db890`` — the tree walk
    0x101dd556   ``0x101da800`` when the capability's ``+0xe`` flag is 0 —
                 frees the image-side buffers again; no result effect
    ===========  ==========================================================

    ``exposure`` is ``&ctx[0x4bc]`` from the shell — pass ``None`` to model a
    NULL pointer, which the code turns into 0.
    """
    if not TONEHELPER_ACQUIRE_HIST_PORTED:
        _unported("TONEHELPER_ACQUIRE_HIST_PORTED", "analyze(hist)",
                  IMPL_ANALYZE_HIST)
    check_params(p)
    n = p.maxValue + 1
    res = ToneHelperResults()
    res.buffer_sizes = allocate_memory(p, -1, -1)
    res.exposure = 0.0 if exposure is None else f32(exposure)

    lum = list(lum_hist[:n]) + [0] * max(0, n - len(lum_hist))
    edge = list(edge_hist[:n]) + [0] * max(0, n - len(edge_hist))
    lut = list(tone_lut[:n]) + [0] * max(0, n - len(tone_lut))

    if p.nodes:
        nodes = p.nodes
    else:
        nodes = load_tree(p.decisionTree)

    lum_g, edge_g = compute_metrics(p, lum, edge, lut)
    res.lum, res.edge = lum_g, edge_g
    metrics = metrics_by_id(lum_g, edge_g, res.exposure)
    walk = walk_decision_tree(nodes, metrics)
    res.terminalNode = walk.terminal_node
    res.toneHelperValue = walk.tone_value
    res.sceneClass = walk.scene_class
    return res


def analyze_from_image(p: ToneHelperParams, image, tone_lut, exposure):
    """``AnsToneHelperCapabilityImpl::analyze`` (``0x101dcc50``) — NOT ported.

    The orchestration is understood and transcribed in this docstring, but it
    cannot run without ``0x101dbc00``, which is the piece that is missing:

    ===========  ==========================================================
    0x101dcca3   ``check_params``
    0x101dcdbf   ``0x101da8c0`` reset
    0x101dcdd5   ``allocateMemory(width, height)`` — the image branch, which
                 additionally takes ``impl+0x84`` and ``impl+0x8c`` at
                 ``width*height*2`` bytes each
    0x101dce5b   ``impl+0x128 = *exposureArg`` (or 0)
    0x101dce74   ``0x101dbc00`` — build the luminance histogram, run the
                 Laplacian, then search downward for an edge threshold that
                 keeps at least ``minEdgeRatio`` of pixels, scaling by
                 ``thresholdMultiplier`` / ``thresholdReductionFactor`` and
                 stopping at ``minEdgeThreshold``.  Writes ``impl+0x80``
                 (nPixels) and ``impl+0x90`` (the threshold it settled on),
                 and sets ``impl+0x12c = -1`` if it bottomed out.
    0x101dcf11   ``rep movsd`` the tone LUT into ``impl+0xac``
    0x101dcf34   ``if (impl+0x90 < minEdgeThreshold)``: skip the tree
                 entirely and publish ``(impl+0x134, impl+0x138) = (1, 2)``
    0x101dcfab   otherwise ``0x101db020`` then ``0x101db890`` as usual
    ===========  ==========================================================

    This branch is unreachable on the shipped colour-negative path: the shell
    only calls it when cna produced no edge histogram (``0x100fc334``), and
    cna always does.  Rather than ship a plausible-looking edge detector that
    nobody has checked against the DLL, this raises.
    """
    _unported("TONEHELPER_IMAGE_HISTOGRAM_PORTED",
              "the image-side histogram/edge builder", BUILD_HISTOGRAMS)


def get_results(res: ToneHelperResults) -> bytes:
    """``0x1010c6a0`` -> ``0x1010bb40`` — ``rep movsd 0x2f`` from impl+0x80."""
    return res.to_bytes()


# ---------------------------------------------------------------------------
# shipped data
# ---------------------------------------------------------------------------


def load_params(name: str = DEFAULT_DPI) -> ToneHelperParams:
    """Parse a vendored ``toneHelper-*.dpi`` and attach its decision tree."""
    p = parse_toneHelper_dpi((DATA_DIR / name).read_text())
    p.nodes = load_tree(p.decisionTree)
    return p


def load_tree(name: str = DEFAULT_TREE) -> tuple[DecisionNode, ...]:
    return parse_decision_tree((DATA_DIR / name).read_text())


def main() -> None:
    print("toneHelper — analyzeAutoTone stage 3")
    print(f"  Cap acquire (hist)  {CAP_ACQUIRE_HIST:#010x} -> Impl "
          f"{IMPL_ANALYZE_HIST:#010x}   [LIVE on CN-Enhanced]")
    print(f"  Cap acquire (image) {CAP_ACQUIRE_IMAGE:#010x} -> Impl "
          f"{IMPL_ANALYZE_IMAGE:#010x}")
    print(f"  Cap getResults      {CAP_GET_RESULTS:#010x} -> Impl "
          f"{IMPL_GET_RESULTS:#010x}  ({RESULTS_SIZE:#x} B @ impl+0x80)")
    print()
    p = load_params()
    print(f"  {DEFAULT_DPI}: maxValue={p.maxValue} "
          f"bands={p.lowToneRange}/{p.midLowToneRange}/"
          f"{p.midHighToneRange}/{p.highToneRange}")
    print(f"  decisionTree={p.decisionTree} ({len(p.nodes)} nodes)  "
          f"decisionTreeDei={p.decisionTreeDei} (NOT read here)")
    check_params(p)
    print("  param check: OK")
    print()
    print("  flags: "
          f"TREE={TONEHELPER_DECISION_TREE_PORTED} "
          f"TREE_FILE={TONEHELPER_TREE_FILE_PORTED} "
          f"DPI={TONEHELPER_DPI_PORTED} "
          f"CHECK={TONEHELPER_PARAM_CHECK_PORTED} "
          f"ALLOC={TONEHELPER_ALLOCATE_PORTED}")
    print("         "
          f"HIST={TONEHELPER_HISTOGRAM_PORTED} "
          f"METRICS={TONEHELPER_METRICS_PORTED} "
          f"RESULTS={TONEHELPER_RESULTS_LAYOUT_PORTED} "
          f"ACQUIRE_HIST={TONEHELPER_ACQUIRE_HIST_PORTED} "
          f"ACQUIRE_IMAGE={TONEHELPER_ACQUIRE_IMAGE_PORTED} "
          f"IMAGE_HIST={TONEHELPER_IMAGE_HISTOGRAM_PORTED}")


if __name__ == "__main__":
    main()
