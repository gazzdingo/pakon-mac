#!/usr/bin/env python3
"""``ColorNegativePath::analyzeAutoTone`` (``0x100fb730``) — the shell.

PakonIMAu.dll ImageBase ``0x10000000`` (file VAs == cited VAs), md5
``eea9dcf78ee21d4f7c515a6c2512242d``.  This file is to ``analyzeAutoTone`` what
``pakon_shasta.py`` is to Shasta: the orchestrator plus its ``*_PORTED`` flags.

WHAT IS IN HERE — AND WHAT IS DELIBERATELY NOT
==============================================
In: the **shell** — the seven capability lookups, the ``+0xc`` enable-byte
gating, the branch structure of the six live stages, the tone object threaded
through ``ctx+0x64d0``, the ``ctx+0x4bc`` scalar handed to toneHelper, the
``ctx+0x44`` scene-type fixups, and the byte-exact layout of every results
struct that crosses the boundary (``AUTOTONE_WORK_LAYOUT``).

Out: the six subsystems' own arithmetic.  Every subsystem entry point here is a
stub gated on a ``False`` flag that raises ``RuntimeError`` — Phase 2 fills
them in.  Nothing silently no-ops.

Residual set (``tools/re/reachability.py``, this session, ``aaa``)::

    walk(0x100fb730)                          166 fns / 68,323 B / 345 ind
    minus the 14 subsystem Impl bodies         20 fns /  8,533 B

and those 20 are exactly what this file models:

===========  ===================================================
 0x100fb730  analyzeAutoTone itself (5,311 B)
 0x10020a40  ColorNegativePath capability-set find thunk
 0x10028f70  AnsCapabilitySet::find (the real lookup)
 0x100f8030  AnsCnaParams default ctor
 0x10064d70  AnsToneHelperResults default ctor
 0x104ffdd6  __RTDynamicCast (CRT IAT thunk)
 14 more     the Cap-level wrappers, one per call site (table below)
===========  ===================================================

THREE CORRECTIONS TO THE SCOPING BRIEF, ALL PROVEN BELOW
=======================================================
1. ``analyzeAutoTone`` does **not** call ``AnsSceneContext::find``
   (``0x10022a40``).  It calls ``0x10020a40``, a 46-byte thiscall thunk onto
   ``AnsCapabilitySet::find`` (``0x10028f70``) at ``*(this+0xc) + 0x6028``.
   The two have different contracts — see ``CapabilitySet.find`` — so
   ``pakon_scene_context.SceneContextBag.find`` (a name->bytes blob bag, whose
   own docstring already says it is *not* a port of ``0x10022a40``) is **not**
   a base to build on.  Nothing here imports it.
2. ``pfd`` is looked up **sixth**, between ``ast`` and ``citras`` — not
   seventh.  (It *is* declared seventh; ``declareAutoTone`` and
   ``analyzeAutoTone`` disagree on the order of the last two.)
3. The addresses the brief calls each subsystem's ``analyze`` are the Impl
   behind its **acquire** call; the call the shell makes *second* is a fixed
   size ``rep movsd`` getter.  See ``CAP_CALLS``.

CAPABILITY LOOKUP — ``0x100fb730`` … ``0x100fbdf8``
==================================================
Seven identical blocks, in this order.  Each one:
``std::string name(lit)`` -> ``0x10020a40(&status, &name, &iface)`` ->
destroy string -> ``if (status != OK) log(line); return`` ->
``cap = __RTDynamicCast(iface, 0, AnsCapability, <target>, 0)`` ->
``if (!cap) throw("<Name> capability not found.", line)``.

======  ===========  ==========  ============  ===========================
 name    name lit     ebp slot    RTTI target   "not found" string / line
======  ===========  ==========  ============  ===========================
cna     0x10574108   -0x44       0x1069298c    0x1057aec0 / 845
dra     0x10574104   -0x28       0x1069296c    0x1057aea4 / 846
tone…   0x10574088   -0x24       0x1069276c    0x1057a3f8 / 847
contr…  0x10574074   -0x30       0x106926f8    0x1057a0e0 / 849
ast     0x10574114   -0x38       0x106929ac    0x1057aedc / 850
pfd     0x105740b0   -0xb0       0x106928a4    0x1057a8a8 / 851
citras  0x1057410c   -0xb4       0x106928c4    0x1057a8c4 / 852
======  ===========  ==========  ============  ===========================

(Line 848 is skipped by the compiler's own line table — not a missing stage.)
The RTTI target descriptors decode to ``.?AVAnsCnaCapability@@`` …
``.?AVAnsCitrasCapability@@``; the source type ``0x10692518`` is
``.?AVAnsCapability@@``.  Read straight out of the ``TypeDescriptor.name``
fields at ``+8``, not inferred.

THE ENABLE BYTE — ``cap+0xc``
=============================
``ColorNegativePath::declareAutoTone`` registers the same seven and then forces
``cap+0xc`` / ``cap+0xd``::

    cna        0x100f9723 / 0x100f972b   1 / 1
    dra        0x100f98ad / 0x100f98be   1 / 1
    toneHelper 0x100f9a37 / 0x100f9a3f   1 / 1
    contrast   0x100f9b0e / 0x100f9b16   1 / 1
    ast        0x100f9be5 / 0x100f9bed   1 / 1
    citras     0x100f9cd8 / 0x100f9ce0   1 / 1
    pfd        0x100f9da2 / 0x100f9dad   0 / 0     <-- dead

``analyzeAutoTone`` tests ``cap+0xc`` before every stage, so pfd's stage is
present in the code and never runs.  It is ported here (skipped, not omitted)
because the brief asked for it and because its absence would have changed
nothing about the layout either way — see ``PFD_STAGE_PORTED``.

THE SIX/SEVEN STAGES
====================
``ctx`` is ``[ebp+0x14]`` — the shared ColorNegativePath driver state, the same
object whose ``+0x4b6`` holds the flesh accumulator ``docs/64`` proved is not
read here.  ``ctx+0x64d0`` is seeded 0 at ``0x100fb787``, before any lookup.

``holder`` is ``[ebp+0xc]``, a by-value refcounted pointer (addref at ``+4``);
``arg2`` is ``[ebp+0x10]``, threaded verbatim into cna's acquire and, when the
edge histogram is null, into toneHelper's.

Stage 1 — cna (``0x100fbdf8``), gate ``cap[-0x44]+0xc``
    ``0x10132dc0(&st, holder, arg2)``                       err line 863
    default-construct ``AnsCnaResults`` (0x60 B) at ebp-0xac
    ``0x10132ed0(&st, &results)``  -- getResults            err line 869
    ``ctx+0x64d0 = results.ToneScaleLut``
    ``lut_size = 0x1000`` ; ``lum_hist = results.LuminanceHist``
    ``edge_hist = results.EdgeHist``
    default-construct ``AnsCnaParams`` (0x7c B) at ebp-0x140 via ``0x100f8030``
    ``0x10132ea0(&st, &params)``   -- getParams             err line 880
    ``elmo_occured = results.bElmoOccured``
    ``elmo_aggressiveness = params.elmoAggressiveness``

Stage 2 — dra (``0x100fc098``), gate ``cap[-0x28]+0xc``
    if ``ctx+0x64d0``:
        ``0x10131100(&st, holder, lum_hist, edge_hist, tone)``   err line 901
    else:
        ``0x10131020(&st, holder, arg2)``                        err line 909
    ``0x10131220(&st, &results)``  -- getResults (0x3c B)        err line 916
    ``lut_size = results.nSmallBins`` ; ``ctx+0x64d0 = results.DraLut``

Stage 3 — toneHelper (``0x100fc312``), gate ``cap[-0x24]+0xc``
    if ``ctx+0x64d0``:
        if ``edge_hist``:
            ``0x1010c3b0(&st, holder, lum_hist, edge_hist,
                          &ctx[0x4bc], tone)``                    err line 945
        else:
            ``0x1010c0f0(&st, holder, arg2, &ctx[0x4bc], tone)``  err line 953
    default-construct ``AnsToneHelperResults`` (0xbc B) via ``0x10064d70``
    ``0x1010c6a0(&st, &results)``  -- getResults                  err line 965
    ``tone_helper_value = results[+0xb4]``
    NOTE: this stage does **not** write ``ctx+0x64d0``.  The only four writers
    are the seed, cna, dra and contrast.

Between 3 and 4 (``0x100fc5cd``)
    if ``elmo_occured``: ``x = elmo_aggressiveness``;
                         if ``3 <= ctx+0x44 <= 6``: ``ctx+0x44 = 0``
    else:               ``x = tone_helper_value``

Stage 4 — contrast (``0x100fc5f3``), gate ``cap[-0x30]+0xc``
    ``0x1010a510(&st, holder, ctx+0x44, x, tone)``               err line 996
    default-construct ``AnsContrastAdjustResults`` (0x2c B) at ebp-0x78
    ``0x1010ad20(&st, &results)`` -- getResults                  err line 1002
    ``lut_size = results.lutSize`` ; ``ctx+0x64d0 = results.OutToneLut``

Stage 5 — ast (``0x100fc79e``), gate ``cap[-0x38]+0xc``
    ``0x1012f3f0(&st, holder, tone)``                            err line 1019
    single call; no results struct, no ``ctx+0x64d0`` write.

Stage 6 — pfd (``0x100fc901``), gate ``cap[-0xb0]+0xc`` -- always 0
    ``0x1012a550(&st, holder, lut_size, tone)``                  err line 1033

Stage 7 — citras (``0x100fc9c3``), gate ``cap[-0xb4]+0xc``
    ``0x1012c490(&st, holder, lut_size, tone)``                  err line 1047

Epilogue (``0x100fcb29``)
    ``if (ctx+0x44 == 1) ctx+0x64d0 = 0``  -- and that is the whole return.

``AUTOTONE_WORK_LAYOUT`` — PROVEN, NOT INFERRED
==============================================
There is no single vendor params-dump near ``0x100fb730`` the way Shasta has
``0x101280a0``.  There are **four**, one per struct, and they are the same kind
of artefact: an ``ostream`` field printer whose ``[obj + off]`` load, ``"  name
= "`` literal and typed ``operator<<`` import pair one-to-one.  The tables
below are read out of them:

    AnsCnaResults              dumper @ 0x10131b5c   header str 0x1058abf0
    AnsDraResults              dumper @ 0x1013003c   header str 0x1058a970
    AnsContrastAdjustResults   dumper @ 0x1012d6fc   header str 0x1058a4e4
    AnsCitrasResults           dumper @ 0x10166cfc   header str 0x1058f49c

Each struct's **size** is proven a second, independent way: every "getResults"
call is a fixed-length ``rep movsd`` out of the Impl, and the count matches the
last named field exactly::

    0x101320b0  cnaImpl      +0x88    0x18 dwords = 0x60   AnsCnaResults
    0x10132070  cnaImpl      +0x0c    0x1f dwords = 0x7c   AnsCnaParams
    0x10130390  draImpl      +0x1c88  0x0f dwords = 0x3c   AnsDraResults
    0x10109d70  contrastImpl +0x18c   0x0b dwords = 0x2c   AnsContrastAdjustResults
    0x1010bb40  toneHelpImpl +0x80    0x2f dwords = 0xbc   AnsToneHelperResults

and a third way for the two the shell default-constructs inline: the sentinel
pattern ``analyzeAutoTone`` writes (``-1`` into every ``i32``, ``-1.0f`` into
every ``f32``, ``0`` into every pointer and bool) lines up field-for-field with
the dumper's types across all 24 slots of ``AnsCnaResults`` and all 11 of
``AnsContrastAdjustResults``.  ``AnsCnaParams``' 0x100f8030 ctor defaults
likewise match ``vendor/ansel/anselinstalldir/dataPathItems/cna/
ansel-cna-default-default.dpi`` key for key (pivot 1550, minPivotPercentile
0.1, thresholdReductionFactor 0.949, elmoNeutralLimit 1500, elmoCriticalPercent
5.0 …).

The default-construct blocks are, strictly, dead stores — the getter memcpy
overwrites the whole struct immediately after.  They are ported anyway because
they are the layout proof and because a Phase-2 subsystem that returns early
would expose them.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
  tools/ansel/python-pipeline/pakon_autotone.py``
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Callable, Sequence

# ---------------------------------------------------------------------------
# flags
# ---------------------------------------------------------------------------

# The shell itself: seven lookups, the +0xc gating, all six live stage
# branches, the ctx+0x64d0 threading and the ctx+0x44 fixups.
# 0x100fb730 (5,311 B) + the 19 helpers listed in the docstring; residual set
# computed with tools/re/reachability.py this session:
#   walk(0x100fb730) = 166 fns / 68,323 B, minus the 14 subsystem Impls = 20.
# Verified bit-exact against the DLL by pakon_autotone_shell_golden.py.
AUTOTONE_SHELL_PORTED = True

# AnsCapabilitySet::find (0x10028f70) via the CN-path thunk 0x10020a40.
# Contract (miss -> null-capability singleton [0x106b5e98], status ALWAYS the
# OK sentinel [0x106b5bd4]) read directly off 0x10028f70; the red-black tree
# walk itself (0x10209820 / 0x101990c0) is a std::map<std::string,...>::find
# and is modelled by a Python dict, not emulated.
AUTOTONE_CAPABILITY_FIND_PORTED = True

# The five struct layouts below, each proven three ways (see docstring).
AUTOTONE_WORK_LAYOUT_PORTED = True

# __RTDynamicCast dispatch: the seven RTTI target TypeDescriptors and the
# not-found fallback shape (0x1001ed90 with "<Name> capability not found.").
AUTOTONE_RTTI_DISPATCH_PORTED = True

# pfd's stage: present in the code, gated off by declareAutoTone at
# 0x100f9da2/0x100f9dad. Ported as "acquire the capability, test +0xc, skip".
PFD_STAGE_PORTED = True

# ---- Phase 2: the six subsystems' own arithmetic. None of it is here. ------
# Reachability, this session (tools/re/reachability.py walk, aaa):
#   cna       acquire Impl 0x1022ea50   36 fns / 11,593 B /  22 indirect
#             getResults   0x101320b0    2 fns /     71 B (rep movsd, no math)
#             getParams    0x10132070    2 fns /     68 B (rep movsd, no math)
#   DONE, Phase 2a -- pakon_cna.py, verified by pakon_cna_golden.py.  The flag
#   is imported rather than restated so the two cannot drift.  Verification is
#   end to end across exactly this boundary: the golden runs the real Cap
#   wrapper 0x10132dc0 -> 0x1022ea50 -> the real 0x101320b0 getter and compares
#   the 0x60 bytes that come back, plus all 5000 ToneScaleLut entries, the
#   LuminanceHist and EdgeHist arrays, and cap+0xf.
#
#   The DLL names 0x1022ea50 itself: it pushes "AnsCnaCapabilityImpl::analyze"
#   (0x1059f94c) with ...\libCna.ansel\AnsCnaCapabilityImpl.cpp at its throw
#   site (0x1022eada).  So "the acquire Impl" and "analyze" are one function.
#
#   ONE CORRECTION to the Phase-2a brief, proven against the binary: the brief
#   said cna's acquire has TWO entry-point variants, 0x1022ea50 (with
#   histogram) and 0x1022b530 (without).  It does not.  An E8 scan of .text
#   finds 0x1022b530's sole caller at 0x1013115b, inside 0x10131100 -- which
#   CAP_CALLS above already records as **dra**.acquireHist, and which is
#   reached only from the dra stage at 0x100fc0dd.  cna's Cap wrapper
#   0x10132dc0 contains exactly one call into an Impl (0x10132e11 ->
#   0x1022ea50), and the shell calls it unconditionally with no fork.  The
#   with/without-histogram fork the brief describes is real, but it belongs to
#   dra (0x100fc0af) and toneHelper (0x100fc329); cna is the stage that
#   *produces* the histograms the other two fork on.  Phase 2b reached the same
#   conclusion about 0x1022b530 independently -- see its note below.
#
#   The shell's `arg2` ([ebp+0x10], threaded verbatim into cna's acquire) is
#   the **image descriptor**: 0x1022ea50 takes it as its fourth stack argument
#   and dereferences +0x0c/+0x10/+0x20 as width/height/pixels.  Established by
#   running the real function under Unicorn with sentinel arguments, not
#   assumed -- radare's stack-slot names are frame-relative and do not survive
#   the pushes.
#
#   NOTE FOR PHASE 2d/2f, about cap+0xe: 0x1022ea50 reads that third flag byte
#   (0x1022edae) and uses it for exactly one thing -- whether to call
#   freeScratch (0x1022d1a0) and drop its twelve working buffers.  It changes
#   no published result.  A data point for the CAP_FLAG_BYTE_E note below,
#   which flagged the byte as an unknown input to contrast.
from pakon_cna import CNA_ANALYZE_PORTED  # noqa: E402
#   dra       acquire+hist 0x1022b530   41 fns / 10,017 B /  40 indirect
#             acquire      0x1022af20   38 fns /  9,757 B /  45 indirect
#             getResults   0x10130390    2 fns /     71 B
#   Phase 2b landed a PARTIAL port in pakon_dra.py, Unicorn-verified by
#   pakon_dra_golden.py.  This flag stays False and is NOT imported from there,
#   because the subsystem is not bit-exact end to end: generateLut (0x1022ab50),
#   keepMidPtLut (0x102290b0) and the effective-bounds blend (0x10228cd0, whose
#   LIVE branch is the bDoAverage=true one, the shipped .dpi setting) are still
#   unported, so neither analyze overload can be run.  What IS ported and
#   verified against the real DLL: the .dpi/.ttc parsers, AnsDraResults' full
#   0x3c layout, the rebin 0x10228e00, the cumulative-percentile bounds
#   0x10228bc0, variant A's own luminance histogram (0x1022b191, lum =
#   (R+G+B+1)/3) and variant B's compose block (0x1022bb0f, out = draCurve o
#   toneLut) -- plus the find("lighting") branch at BOTH sites.
#
#   TWO CORRECTIONS to the Phase-2b brief, both proven against the binary:
#    1. dra's second entry point is 0x1022b530, NOT 0x101dd1b0.  0x101dd1b0 is
#       toneHelper's acquire-with-histograms Impl -- an E8 scan of .text finds
#       its only caller at 0x1010c412, inside toneHelper's Cap wrapper
#       0x1010c3b0..0x1010c667, which CAP_CALLS above already records as
#       th.acquireHist.  dra's two are 0x1022af20 (Cap 0x10131020, sole caller
#       0x10131071) and 0x1022b530 (Cap 0x10131100, sole caller 0x1013115b);
#       both push "AnsDraCapabilityImpl::analyze" (0x1059f73c) with
#       ...\libDra.ansel\AnsDraCapabilityImpl.cpp and are two overloads of it
#       (source lines 738 and 826).  reachability.py setops: 37 of 42 functions
#       shared.  The one real difference is that 0x1022af20 computes its own
#       luminance histogram from pixels and never composes, while 0x1022b530
#       takes both histograms in and composes onto the incoming tone LUT.
#    2. The guarded find("lighting") has TWO sites, not one.  The brief cites
#       only variant A's (0x1022b2e5 -> 0x1022b35b -> continue 0x1022b3b0);
#       variant B has a structurally identical one at 0x1022b99d -> 0x1022b9f9
#       -> continue 0x1022baa4.  "Miss CONTINUES" is implemented at both and
#       confirmed by executing the real DLL over a real empty scene-context
#       map: a miss lands the continue path at both sites AND yields lighting
#       0, which keepMidPtLut's dispatch (0x102290d6) maps to the Normal curve
#       pair -- which on this unit's shipped data is the identity curve.  So
#       the miss is numerically inert as well as non-fatal.  Only a genuine
#       INTERNAL find() error (value-size mismatch or allocation failure)
#       aborts.
#   DONE, Phase 2b continuation -- pakon_dra.py, verified end to end (both
#   overloads, run from their TRUE entry points 0x1022af20/0x1022b530 under
#   Unicorn, not a mid-function slice) by pakon_dra_golden.py's
#   check_analyze_image/check_analyze_hist, plus dedicated checks for every
#   piece the two overloads assemble (check_validate_params, check_alloc,
#   check_generate_lut, and the seven pre-existing leaf checks).  The flag
#   is imported rather than restated so the two cannot drift.
from pakon_dra import DRA_ANALYZE_PORTED  # noqa: E402
#   toneHelper acquire A   0x101dd1b0   37 fns / 13,691 B /  62 indirect
#             acquire B    0x101dcc50   49 fns / 19,920 B /  89 indirect
#             getResults   0x1010bb40    2 fns /     71 B
#   DONE (variant A only), Phase 2c -- pakon_toneHelper.py, verified by
#   pakon_toneHelper_core_golden.py and pakon_toneHelper_tree_golden.py.  The
#   flags are imported rather than restated so the two cannot drift.
#
#   The two acquires are two overloads of the same method, and which one the
#   shell picks is decided at 0x100fc334 on whether cna produced an edge
#   histogram.  Variant A (0x101dd1b0, reached through Cap 0x1010c3b0) takes
#   the histograms cna already built and never touches a pixel -- that is the
#   one that runs on CN-Enhanced, and it is ported end to end.  Variant B
#   (0x101dcc50, Cap 0x1010c0f0) is the no-edge-histogram fallback; it has to
#   build its own histograms with a Laplacian edge detector and an adaptive
#   threshold search (0x101dbc00, 36 fns / 8,885 B), which is NOT ported, so
#   TONEHELPER_ACQUIRE_IMAGE_PORTED stays False and that path still raises.
#
#   NOTE FOR ANYONE READING THE DATA FILES: toneHelper ships a decision tree
#   called deiTree1 and AnsDeiResults has a field called adjToneHelperDeiValue.
#   Neither is an input here.  The tree this path walks is `decisionTree` =
#   AllOnTree1 at impl+0x78; deiTree1 lives at impl+0x7c and is read only by
#   ColorNegativePath::CalcDei (0x101081e0), which the driver runs AFTER
#   analyzeAutoTone (0x10069aca vs 0x10069a1d).  Nothing in pakon_toneHelper
#   imports, reads or references dei.  See its module docstring and docs/64.
from pakon_toneHelper import (  # noqa: E402
    TONEHELPER_ACQUIRE_HIST_PORTED,
    TONEHELPER_ACQUIRE_IMAGE_PORTED,
)
#: True when *some* toneHelper entry point is live -- the shell's stage-3 gate
#: never needs both, because only one of the two branches runs per frame.
TONEHELPER_ANALYZE_PORTED = TONEHELPER_ACQUIRE_HIST_PORTED
#   contrast  acquire      0x101d8880   79 fns / 20,414 B / 104 indirect
#             getResults   0x10109d70    2 fns /     71 B
#   DONE, Phase 2d -- pakon_contrast.py, verified by pakon_contrast_lut_golden.py
#   (0x101d8240 build + mode dispatch + the 0x101d8880 front end) and
#   pakon_contrast_slope_golden.py (0x101d2eb0 constrainSlope standalone).
#   The 79 functions are almost all smart-pointer and std::map machinery: the
#   real arithmetic is 0x101d8240 plus three leaves (0x101d2ad0 ramp, 0x101d2c80
#   segment, 0x101d2eb0 constrainSlope), and analyze never touches image pixels
#   -- 4096 LUT entries in, 4096 out.  The DPI-registry walk behind selectParams
#   runs at library INITIALISATION, not here, so only the resolved params cross
#   this boundary; see CONTRAST_SELECT_DPI_TREE_PORTED in pakon_contrast.py.
CONTRAST_ANALYZE_PORTED = True
#   ast       single call  0x10227160   27 fns /  4,763 B /  16 indirect
#   DONE, Phase 2e -- pakon_ast.py, verified by pakon_ast_golden.py.  Imported
#   rather than restated so the two cannot drift.  All three arrays the real
#   0x10227160 produces (work[] Impl+0x38, the delete[]-d curve table, out[]
#   Impl+0x3c) are compared dword-for-dword under Unicorn over 6 parameter sets
#   x 10 tone LUTs, plus the 0x10225bb0 validator (21 cases), the null-tone
#   early-out and the cap+0xe teardown branch.  Note it writes only its own
#   Impl+0x3c: the stage-5 note below ("no ctx+0x64d0 write") is confirmed, so
#   within analyzeAutoTone ast's output is produced and never read again.
from pakon_ast import AST_ANALYZE_PORTED  # noqa: E402
#   citras    single call  0x10223a20   24 fns /  3,674 B /  17 indirect
#             (0x10223860, cited by an earlier pass, decodes mid-instruction
#              inside a neighbouring function and is not an entry point)
#   DONE, Phase 2f -- pakon_citras.py, verified by pakon_citras_golden.py.
#   The flag is imported rather than restated so the two cannot drift.  Note it
#   is citras's *analyze* only: the per-pixel apply path (ImaI16CitrasOp and
#   friends, 218 fns / 86,062 B) is pakon_citras.CITRAS_APPLY_PORTED, still
#   False, and is not reachable from analyzeAutoTone at all.
from pakon_citras import CITRAS_ANALYZE_PORTED  # noqa: E402
#   pfd       single call  0x10220650   24 fns /  3,726 B /  19 indirect
#             Unreachable at run time: enable byte forced 0 at 0x100f9da2.
PFD_ANALYZE_PORTED = False

# ---------------------------------------------------------------------------
# Phase 6.1 -- ASSEMBLED verification, strictly separate from Phase 6.2
# ---------------------------------------------------------------------------
# This is NOT the same thing as ``pakon_shasta.AUTO_TONE_PORTED`` (still
# False, and not touched here -- that flag flips only when Phase 6.2 swaps
# the render path, a later, separate, more consequential step).  This flag
# says: the assembled Python chain above (this module's ``analyze_auto_tone``
# driving a real, non-stub ``AutoToneSubsystems`` -- every ``*_acquire``/
# ``*_analyze`` method here calls straight into the real ported subsystem,
# not a pattern stub, once every ``*_PORTED`` flag above is True) has been
# run field-by-field against the REAL DLL's ``0x100fb730`` executing whole,
# start to finish, with NO subsystem entry points hooked -- the real Cap
# wrappers falling through into the real cna/dra/toneHelper/contrast/ast/
# citras Impl bodies for real, in one Unicorn call -- and everything
# compared (every ``AUTOTONE_WORK_LAYOUT`` scalar, plus every subsystem's own
# full result object and every LUT/histogram array, dword for dword) agreed,
# across 7 scenarios (flat/uniform, gradient, high-contrast banded, two
# pseudo-random images at realistic pixel counts, and two ``scene_type``
# variants).  See ``pakon_autotone_assembled_golden.py``.
#
# One real integration-class bug was found and fixed by this verification,
# in exactly the way this step exists to catch: neither subsystem's own
# leaf-level golden ever fed it a genuinely degenerate real-DLL-producible
# input, because each one's own synthetic test data was hand-shaped to avoid
# it.  A perfectly flat (edgeless) test image legitimately makes cna's real
# ``EdgeHist`` all-zero, and ``pakon_toneHelper.compute_metrics`` then divides
# by that histogram's total unconditionally -- the real DLL does not trap
# (FPCW 0x027f masks the x87 zero-divide exception and produces a
# correctly-signed infinity), but the port's plain Python ``/`` raised
# ``ZeroDivisionError``.  Fixed with an IEEE-754-shaped masked-division
# helper (``pakon_toneHelper._x87_div``, mirroring the same class of fix
# ``pakon_ast._x87_div`` already made once before on this project) at both
# risk sites in ``compute_metrics``.  The identical class of bug was also
# found and fixed the same way in ``pakon_cna.analyze_image``'s ``_half``
# (``pakon_cna._x87_div``), triggered by a pseudo-random image with an
# all-zero-in-places resampled bucket histogram.  Both fixes were re-verified
# against their own subsystem's full pre-existing golden suite (still 100%
# passing) before being counted here.
#
# A separate, real, reproducible divergence was investigated and NOT fixed:
# an unrealistically tiny (100-pixel, 46-edge-pixel) synthetic image drove
# cna's dark/light-half percentile-crossing search to land exactly at index
# 0, and the real DLL's ToneScaleLut came back perfectly flat where the port
# computed a real curve -- reproduced with cna's OWN standalone golden
# harness too, so it is not an artefact of the assembled wiring.  Re-run at
# every larger, still-"pseudo-random" size from 16x16 pixels up: zero
# divergence, every time.  A real scanned frame is millions of pixels, never
# ~100, so -- same standard as ``pakon_dra_golden.py``'s own documented
# out-of-range-pixel note -- this is recorded, not chased further or
# "fixed" by guessing at an untraced tie-break.
AUTOTONE_ASSEMBLED_VERIFIED = True

# ---------------------------------------------------------------------------
# addresses
# ---------------------------------------------------------------------------

ANALYZE_AUTO_TONE = 0x100FB730
DECLARE_AUTO_TONE_PFD_DISABLE = 0x100F9DA2   # mov byte [edx+0xc], 0
DECLARE_AUTO_TONE_PFD_DISABLE_D = 0x100F9DAD  # mov byte [eax+0xd], 0

CAP_FIND_THUNK = 0x10020A40      # ColorNegativePath -> capability set
CAP_SET_FIND = 0x10028F70        # AnsCapabilitySet::find
CAP_SET_MAP_FIND = 0x10209820    # std::map find inside it
CAP_SET_OFFSET = 0x6028          # *(holder+0xc) + 0x6028 == the set
RT_DYNAMIC_CAST = 0x104FFDD6     # CRT IAT thunk (unbound in the file)

STATUS_OK_GLOBAL = 0x106B5BD4    # the AnsStatus "no error" singleton
NULL_CAPABILITY_GLOBAL = 0x106B5E98  # what find() stores on a miss
LOG_STATUS_AND_RETURN = 0x1001F770   # status propagate + log
THROW_NOT_FOUND = 0x1001ED90         # "<Name> capability not found."

CNA_PARAMS_CTOR = 0x100F8030          # AnsCnaParams default ctor (0x7c B)
TONEHELPER_RESULTS_CTOR = 0x10064D70  # AnsToneHelperResults default ctor

SRC_FILE_STR = 0x10586844   # "\Atc\ansel\src\libPaths.ansel\cnMethods.cpp"
FUNC_NAME_STR = 0x10586A60  # "ColorNegativePath::analyzeAutoTone"

# ctx == [ebp+0x14], the shared ColorNegativePath driver state
CTX_SCENE_TYPE = 0x44     # tested ==7 by the driver, ==1 in the epilogue
CTX_TONEHELPER_SCALAR = 0x4BC   # &ctx[0x4bc] handed to toneHelper
CTX_TONE_OBJECT = 0x64D0        # the tone LUT threaded between stages

# ---------------------------------------------------------------------------
# the seven capabilities, in analyzeAutoTone's LOOKUP order
# (declareAutoTone's order differs: ... ast, citras, pfd)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CapabilitySpec:
    """One of the seven ``0x10020a40`` lookups."""

    key: str
    name: str                # the std::string literal pushed
    name_str_va: int
    slot: int                # ebp-relative slot the cap pointer lands in
    rtti_target: int         # __RTDynamicCast target TypeDescriptor
    rtti_class: str          # its decoded .?AV...@@ name
    not_found_str_va: int
    not_found_msg: str
    find_line: int           # source line quoted on a find-status failure
    declare_enable_va: int   # where declareAutoTone forces cap+0xc
    declare_enabled: int     # ... and to what


CAPABILITIES: tuple[CapabilitySpec, ...] = (
    CapabilitySpec("cna", "cna", 0x10574108, -0x44, 0x1069298C,
                   "AnsCnaCapability", 0x1057AEC0,
                   "Cna capability not found.", 845, 0x100F9723, 1),
    CapabilitySpec("dra", "dra", 0x10574104, -0x28, 0x1069296C,
                   "AnsDraCapability", 0x1057AEA4,
                   "Dra capability not found.", 846, 0x100F98AD, 1),
    CapabilitySpec("tone_helper", "toneHelper", 0x10574088, -0x24, 0x1069276C,
                   "AnsToneHelperCapability", 0x1057A3F8,
                   "ToneHelper capability not found.", 847, 0x100F9A37, 1),
    CapabilitySpec("contrast", "contrast", 0x10574074, -0x30, 0x106926F8,
                   "AnsContrastAdjustCapability", 0x1057A0E0,
                   "ContrastAdjust capability not found.", 849, 0x100F9B0E, 1),
    CapabilitySpec("ast", "ast", 0x10574114, -0x38, 0x106929AC,
                   "AnsAstCapability", 0x1057AEDC,
                   "Ast capability not found.", 850, 0x100F9BE5, 1),
    CapabilitySpec("pfd", "pfd", 0x105740B0, -0xB0, 0x106928A4,
                   "AnsPfdCapability", 0x1057A8A8,
                   "Pfd capability not found.", 851,
                   DECLARE_AUTO_TONE_PFD_DISABLE, 0),
    CapabilitySpec("citras", "citras", 0x1057410C, -0xB4, 0x106928C4,
                   "AnsCitrasCapability", 0x1057A8C4,
                   "Citras capability not found.", 852, 0x100F9CD8, 1),
)

LOOKUP_ORDER: tuple[str, ...] = tuple(c.name for c in CAPABILITIES)
#: ``declareAutoTone``'s registration order — citras and pfd are swapped.
DECLARE_ORDER: tuple[str, ...] = (
    "cna", "dra", "toneHelper", "contrast", "ast", "citras", "pfd",
)

CAP_ENABLE_BYTE = 0x0C   # tested before every stage
CAP_FLAG_BYTE_D = 0x0D   # set alongside it by declareAutoTone; unread here
#: A third flag byte. The shell never touches it, but the contrast Cap wrapper
#: reads it (``mov al, byte [edi+0xe]`` @ ``0x1010a568``) and forwards it to
#: ``0x101d8880``. ``declareAutoTone`` does NOT set it, so whatever the
#: capability's own constructor leaves there reaches contrast's analysis --
#: Phase 2f/2d needs to find that constructor before trusting contrast's input.
CAP_FLAG_BYTE_E = 0x0E
CAP_STATUS_BYTE_F = 0x0F  # each Cap wrapper writes (status == OK) here
CAP_IMPL_PTR = 0x10       # every Cap wrapper forwards to *(cap+0x10)

# ---------------------------------------------------------------------------
# the 14 Cap-level calls the shell makes — Cap entry -> Impl target
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CapCall:
    key: str
    cap_va: int
    impl_va: int
    n_stack_args: int     # including the hidden AnsStatus& sret
    call_site: int
    err_line: int
    what: str


CAP_CALLS: tuple[CapCall, ...] = (
    CapCall("cna.acquire",     0x10132DC0, 0x1022EA50, 3, 0x100FBE28, 863,
            "acquire(&st, holder, arg2)"),
    CapCall("cna.getResults",  0x10132ED0, 0x101320B0, 2, 0x100FBF37, 869,
            "getResults(&st, &AnsCnaResults) -- rep movsd 0x60 from impl+0x88"),
    CapCall("cna.getParams",   0x10132EA0, 0x10132070, 2, 0x100FBFF3, 880,
            "getParams(&st, &AnsCnaParams) -- rep movsd 0x7c from impl+0xc"),
    CapCall("dra.acquireHist", 0x10131100, 0x1022B530, 5, 0x100FC0DD, 901,
            "acquire(&st, holder, lumHist, edgeHist, tone)"),
    CapCall("dra.acquire",     0x10131020, 0x1022AF20, 3, 0x100FC17D, 909,
            "acquire(&st, holder, arg2)"),
    CapCall("dra.getResults",  0x10131220, 0x10130390, 2, 0x100FC209, 916,
            "getResults(&st, &AnsDraResults) -- rep movsd 0x3c from impl+0x1c88"),
    CapCall("th.acquireHist",  0x1010C3B0, 0x101DD1B0, 6, 0x100FC36A, 945,
            "acquire(&st, holder, lumHist, edgeHist, &ctx[0x4bc], tone)"),
    CapCall("th.acquire",      0x1010C0F0, 0x101DCC50, 5, 0x100FC424, 953,
            "acquire(&st, holder, arg2, &ctx[0x4bc], tone)"),
    CapCall("th.getResults",   0x1010C6A0, 0x1010BB40, 2, 0x100FC4CB, 965,
            "getResults(&st, &AnsToneHelperResults) -- rep movsd 0xbc from impl+0x80"),
    CapCall("contrast.acquire", 0x1010A510, 0x101D8880, 5, 0x100FC62A, 996,
            "acquire(&st, holder, sceneType, x, tone)"),
    CapCall("contrast.getResults", 0x1010AD20, 0x10109D70, 2, 0x100FC6FB, 1002,
            "getResults(&st, &AnsContrastAdjustResults) -- rep movsd 0x2c from impl+0x18c"),
    CapCall("ast.analyze",     0x1012F3F0, 0x10227160, 3, 0x100FC7D4, 1019,
            "analyze(&st, holder, tone)"),
    CapCall("pfd.analyze",     0x1012A550, 0x10220650, 4, 0x100FC940, 1033,
            "analyze(&st, holder, lutSize, tone)"),
    CapCall("citras.analyze",  0x1012C490, 0x10223A20, 4, 0x100FC9FF, 1047,
            "analyze(&st, holder, lutSize, tone)"),
)

CAP_CALL_BY_KEY = {c.key: c for c in CAP_CALLS}

# ---------------------------------------------------------------------------
# AUTOTONE_WORK_LAYOUT — (offset, name, kind) per struct.
#
# "kind" is the type the vendor dumper's operator<< overload proves:
#   i32/i16 = long/short, f32 = float, bool = bool, ptr = a printed container.
# "seed" is the value analyzeAutoTone's own inline default-ctor writes, where
# it writes one; None means the slot is not seeded (dra's struct is passed
# uninitialised, and toneHelper's is built by 0x10064d70 instead).
# ---------------------------------------------------------------------------

AUTOTONE_WORK_LAYOUT: dict[str, dict] = {
    # dumper 0x10131b5c; size 0x60 proven by 0x101320b0's 0x18-dword copy;
    # every seed below is a literal store in 0x100fbea8..0x100fbf37.
    "AnsCnaResults": {
        "size": 0x60,
        "getter": 0x101320B0,
        "impl_offset": 0x88,
        "dumper": 0x10131B5C,
        "ctor_site": 0x100FBEA8,
        "fields": (
            (0x00, "nPixels", "i32", -1),
            (0x04, None, "?", 0),
            (0x08, "LuminanceHist", "ptr", 0),
            (0x0C, None, "?", 0),
            (0x10, "threshold", "i32", -1),
            (0x14, "nEdgePixels", "i32", -1),
            (0x18, None, "?", 0),
            (0x1C, "EdgeHist", "ptr", 0),
            (0x20, "darkInSigma", "f32", -1.0),
            (0x24, "lightInSigma", "f32", -1.0),
            (0x28, "darkOutSigma", "f32", -1.0),
            (0x2C, "lightOutSigma", "f32", -1.0),
            (0x30, None, "?", 0),
            (0x34, None, "?", 0),
            (0x38, None, "?", 0),
            (0x3C, None, "?", 0),
            (0x40, None, "?", 0),
            (0x44, None, "?", 0),
            (0x48, None, "?", 0),
            (0x4C, None, "?", 0),
            (0x50, None, "?", 0),
            (0x54, "ToneScaleLut", "ptr", 0),
            (0x58, "elmoPercent", "f32", -1.0),
            (0x5C, "bElmoOccured", "bool", 0),
        ),
    },
    # dumper 0x1013003c; size 0x3c proven by 0x10130390's 0xf-dword copy.
    # NOT seeded by analyzeAutoTone -- 0x100fc1fb passes the raw stack slot.
    "AnsDraResults": {
        "size": 0x3C,
        "getter": 0x10130390,
        "impl_offset": 0x1C88,
        "dumper": 0x1013003C,
        "ctor_site": None,
        "fields": (
            (0x00, "nSmallBins", "i32", None),
            (0x0C, "nLargeBins", "i32", None),
            (0x10, "nLumPixels", "i32", None),
            (0x1C, "nEdgePixels", "i32", None),
            (0x2C, "lumMin", "i16", None),
            (0x2E, "lumMax", "i16", None),
            (0x30, "edgeMin", "i16", None),
            (0x32, "edgeMax", "i16", None),
            (0x34, "effMin", "i16", None),
            (0x36, "effMax", "i16", None),
            (0x38, "DraLut", "ptr", None),
        ),
    },
    # dumper 0x1012d6fc; size 0x2c proven by 0x10109d70's 0xb-dword copy;
    # seeds are literal stores in 0x100fc6b5..0x100fc6f8.
    "AnsContrastAdjustResults": {
        "size": 0x2C,
        "getter": 0x10109D70,
        "impl_offset": 0x18C,
        "dumper": 0x1012D6FC,
        "ctor_site": 0x100FC6B5,
        "fields": (
            (0x00, "lutSize", "i32", 0),
            (0x04, "lowSlope", "f32", -1.0),
            (0x08, "highSlope", "f32", -1.0),
            (0x0C, "lowerMinSlopeLimit", "f32", 0.0),
            (0x10, "lowerMaxSlopeLimit", "f32", 100.0),
            (0x14, "upperMinSlopeLimit", "f32", 0.0),
            (0x18, "upperMaxSlopeLimit", "f32", 100.0),
            (0x1C, None, "bool", 0),
            (0x1D, None, "bool", 0),
            (0x1E, None, "bool", 0),
            (0x1F, None, "bool", 0),
            (0x20, "CAdjLut", "ptr", 0),
            (0x24, "InToneLut", "ptr", 0),
            (0x28, "OutToneLut", "ptr", 0),
        ),
    },
    # No ostream dumper exists for this one (the "AnsToneHelperResults" string
    # at 0x1059a734 is a log tag, not a "<name>:" printer header). Size 0xbc
    # proven by 0x1010bb40's 0x2f-dword copy AND by 0x10064d70's ctor, whose
    # last store is +0xb8. Only +0xb4 crosses the shell boundary.
    "AnsToneHelperResults": {
        "size": 0xBC,
        "getter": 0x1010BB40,
        "impl_offset": 0x80,
        "dumper": None,
        "ctor_site": TONEHELPER_RESULTS_CTOR,
        "fields": (
            (0x00, None, "i32", -1),
            (0x10, None, "i32", -1),
            (0xA8, None, "f32", -1.0),
            (0xAC, None, "i32", -1),
            (0xB0, None, "i32", -1),
            (0xB4, "toneHelperValue", "i32", 0),  # the only field read here
            (0xB8, None, "i32", 2),
        ),
    },
    # dumper 0x10166cfc. analyzeAutoTone never materialises one, but the two
    # fields are exactly the pair it hands citras and pfd: (lutSize, tone).
    "AnsCitrasResults": {
        "size": 0x08,
        "getter": None,
        "impl_offset": None,
        "dumper": 0x10166CFC,
        "ctor_site": None,
        "fields": (
            (0x00, "lutSize", "i32", None),
            (0x04, "ToneLut", "ptr", None),
        ),
    },
    # 0x100f8030 default ctor; size 0x7c proven by 0x10132070's 0x1f-dword
    # copy. Values cross-check against ansel-cna-default-default.dpi.
    # Only +0x78 (elmoAggressiveness) crosses the shell boundary.
    "AnsCnaParams": {
        "size": 0x7C,
        "getter": 0x10132070,
        "impl_offset": 0x0C,
        "dumper": None,
        "ctor_site": CNA_PARAMS_CTOR,
        "fields": (
            (0x00, "redShift", "i16", 0),
            (0x02, "greenShift", "i16", 0),
            (0x04, "blueShift", "i16", 0),
            (0x08, "histSize", "i32", 5000),
            (0x0C, "bucketSize", "i32", 10),
            (0x10, None, "f32", 0.5),
            (0x14, None, "f32", 1.5),
            (0x18, "blend", "f32", 1.0),
            (0x1C, "pivot", "i16", 1550),
            (0x20, "minPivotPercentile", "f32", 0.1),
            (0x24, "maxPivotPercentile", "f32", 0.9),
            (0x28, "thresholdMultiplier", "f32", 1.5),
            (0x2C, "thresholdReductionFactor", "f32", 0.949),
            (0x30, "minPosThreshold", "i16", 4),
            (0x34, "minLapPixelRatio", "f32", 0.1),
            (0x38, "smoothingSizeFactor", "f32", 4.0),
            (0x3C, "laplacianHistSmoothingSigma", "f32", 10.0),
            (0x40, "coarseHistSmoothingSigma", "f32", 2.0),
            (0x44, "toneScaleSmoothingSigma", "f32", 4.0),
            (0x48, "darkMaxContrastGain", "f32", 1.3333300352096558),
            (0x4C, "lightMaxContrastGain", "f32", 1.3333300352096558),
            (0x50, None, "f32", 243.74998474121094),
            (0x54, None, "f32", 243.74998474121094),
            (0x58, None, "f32", 260.0),
            (0x5C, None, "f32", 84.5),
            (0x60, "minGaussSigma", "f32", 1.0),
            (0x64, "maxGaussSigma", "f32", 50.0),
            (0x68, "elmoNeutralLimit", "i16", 1500),
            (0x6A, "elmoRedLimit", "i16", 1600),
            (0x6C, "elmoGreenLimit", "i16", 1600),
            (0x6E, "elmoBlueLimit", "i16", 1600),
            (0x70, "elmoSatThreshold", "i16", 400),
            (0x74, "elmoCriticalPercent", "f32", 5.0),
            (0x78, "elmoAggressiveness", "i32", 1),
        ),
    },
}


def layout_offset(struct_name: str, field_name: str) -> int:
    """Offset of a named field, or raise — never guess at a call site."""
    for off, name, _kind, _seed in AUTOTONE_WORK_LAYOUT[struct_name]["fields"]:
        if name == field_name:
            return off
    raise KeyError(f"{struct_name} has no field {field_name!r}")


def default_construct(struct_name: str) -> bytearray:
    """The inline default ctor analyzeAutoTone runs before each getResults.

    ``AnsCnaResults`` @ ``0x100fbea8``, ``AnsContrastAdjustResults`` @
    ``0x100fc6b5``, ``AnsCnaParams`` @ ``0x100f8030``,
    ``AnsToneHelperResults`` @ ``0x10064d70``.  ``AnsDraResults`` has none —
    ``0x100fc1fb`` hands the getter a raw stack slot — so this returns zeros
    for it, which is what an untouched host buffer is.
    """
    spec = AUTOTONE_WORK_LAYOUT[struct_name]
    buf = bytearray(spec["size"])
    for off, _name, kind, seed in spec["fields"]:
        if seed is None:
            continue
        if kind == "f32":
            struct.pack_into("<f", buf, off, float(seed))
        elif kind == "i16":
            struct.pack_into("<h", buf, off, int(seed))
        elif kind == "bool":
            buf[off] = 1 if seed else 0
        else:
            struct.pack_into("<i", buf, off, int(seed))
    return buf


# ---------------------------------------------------------------------------
# AnsStatus / AnsCapabilitySet
# ---------------------------------------------------------------------------


class AnsStatus:
    """A status token.  ``AnsStatus.OK`` stands for the ``0x106b5bd4`` global.

    Every call in the shell is ``status = f(...)`` followed by
    ``if (status != OK) { log(file, line, "ColorNegativePath::analyzeAutoTone");
    return status; }`` — ``setne bl`` against ``[0x106b5bd4]`` at
    ``0x100fb804``, ``0x100fb900``, ``0x100fb9e2``, ``0x100fbac4``,
    ``0x100fbba6``, ``0x100fbc88``, ``0x100fbd6d`` and once per stage call.
    """

    __slots__ = ("message", "file", "line", "func")

    def __init__(self, message: str = "", file: str = "", line: int = 0,
                 func: str = "ColorNegativePath::analyzeAutoTone"):
        self.message = message
        self.file = file
        self.line = line
        self.func = func

    def __bool__(self) -> bool:          # truthy == an error occurred
        return self is not AnsStatus.OK

    def __repr__(self) -> str:
        if self is AnsStatus.OK:
            return "AnsStatus.OK"
        return f"AnsStatus({self.message!r}, line={self.line})"


AnsStatus.OK = AnsStatus("")   # type: ignore[attr-defined]

SRC_FILE = r"\Atc\ansel\src\libPaths.ansel\cnMethods.cpp"
FUNC_NAME = "ColorNegativePath::analyzeAutoTone"


class AutoToneError(RuntimeError):
    """What ``0x1001ed90`` raises: a "<Name> capability not found." throw."""


@dataclass
class Capability:
    """One entry of the capability set.

    ``+0xc`` enable byte, ``+0xd`` its companion, ``+0xf`` "last call was OK"
    (written by every Cap wrapper, e.g. ``0x10132e27``), ``+0x10`` the Impl.
    """

    name: str
    rtti_class: str
    enabled: bool = True
    flag_d: bool = True
    last_ok: bool = False
    impl: object | None = None


@dataclass
class CapabilitySet:
    """``AnsCapabilitySet::find`` (``0x10028f70``) — the exact contract.

    Reached from ``analyzeAutoTone`` only through the thunk ``0x10020a40``,
    which retargets ``this`` to ``*(holder+0xc) + 0x6028`` and forwards
    ``(sret, name, out)`` unchanged.

    Three things about it are load-bearing and are NOT what
    ``AnsSceneContext::find`` (``0x10022a40``) does:

    * a **miss is not an error**.  ``0x10028fc7`` compares the map iterator
      against ``this+0x28`` (end) and on a miss stores the global
      null-capability singleton ``[0x106b5e98]`` into ``*out``; the status
      written at ``0x10029034`` is unconditionally ``[0x106b5bd4]`` — OK.
      Absence is therefore detected downstream, by ``__RTDynamicCast``
      returning NULL, not by the status.
    * it is keyed by ``std::string`` on a ``std::map`` at ``this+0x24``
      (``0x10209820`` -> ``0x101990c0``), i.e. exact name match, no size or
      type-tag argument at all.
    * it hands back a **capability object**, refcounted at ``+4``, not a blob.

    ``AnsSceneContext::find`` by contrast takes an explicit byte size, copies a
    stored blob into a caller buffer with ``rep movsd``, and reports failure
    through the status.  The host bag in
    ``pakon_scene_context.SceneContextBag`` models *that* contract (and its own
    docstring already says it is not a faithful port even of that).  It is not
    usable here and is deliberately not imported.
    """

    items: dict[str, Capability] = field(default_factory=dict)

    #: The null-capability singleton ``[0x106b5e98]``.  Returned on a miss;
    #: fails every ``__RTDynamicCast``, which is how "not found" is detected.
    NULL_CAPABILITY = None

    def insert(self, cap: Capability) -> None:
        self.items[cap.name] = cap

    def find(self, name: str) -> tuple[AnsStatus, Capability | None]:
        """Returns ``(OK, cap-or-None)`` — the status is never an error."""
        return AnsStatus.OK, self.items.get(name, self.NULL_CAPABILITY)


def rt_dynamic_cast(cap: Capability | None, spec: CapabilitySpec):
    """``__RTDynamicCast(iface, 0, AnsCapability, <target>, 0)``.

    ``0x104ffdd6`` is an unbound IAT thunk in the shipped file, so there is no
    vendor code here to match instruction for instruction; the modelled
    behaviour is MSVC's: NULL in -> NULL out, wrong dynamic type -> NULL,
    otherwise the same pointer (all seven targets derive from AnsCapability at
    offset 0 — every COL found for them has ``offset == 0``).
    """
    if cap is None:
        return None
    return cap if cap.rtti_class == spec.rtti_class else None


# ---------------------------------------------------------------------------
# the driver state and the subsystem boundary
# ---------------------------------------------------------------------------


@dataclass
class AutoToneContext:
    """``[ebp+0x14]`` — the ColorNegativePath driver state, three fields deep.

    Nothing else in the object is touched by ``analyzeAutoTone``: the flesh
    accumulator at ``+0x4b6``..``+0x4bb`` (``docs/64``) is adjacent to
    ``tone_helper_scalar`` and provably never read here.
    """

    scene_type: int = 0          # +0x44
    tone_helper_scalar: int = 0  # +0x4bc, passed BY ADDRESS to toneHelper
    tone_object: int = 0         # +0x64d0 (a raw pointer, 0 == null)


@dataclass
class AutoToneTrace:
    """Every observable the golden harness compares against the DLL."""

    lookups: list[str] = field(default_factory=list)
    calls: list[tuple[str, tuple]] = field(default_factory=list)
    tone_after: list[tuple[str, object | None]] = field(default_factory=list)
    lut_size: int = 0
    lum_hist: object | None = None
    edge_hist: object | None = None
    elmo_occured: bool = False
    elmo_aggressiveness: int = 1
    tone_helper_value: int = 1
    not_found: str | None = None


class AutoToneSubsystems:
    """The Phase-2 boundary: one method per ``CAP_CALLS`` entry.

    Every method is gated on its ``*_PORTED`` flag and raises.  Subclass and
    override to plug a real subsystem in; the shell never inspects the
    returned structs except through ``AUTOTONE_WORK_LAYOUT``.
    """

    @staticmethod
    def _unported(flag: str, call: str) -> "NoReturn":  # noqa: F821
        c = CAP_CALL_BY_KEY[call]
        raise RuntimeError(
            f"{flag} is False: {call} ({c.cap_va:#x} -> Impl {c.impl_va:#x}, "
            f"{c.what}) is not ported. Phase 2 owns this; see "
            f"docs/64-pruned-tone-producers.md.")

    # -- cna ---------------------------------------------------------------
    #: Set by ``cna_acquire`` and read by the two getters, exactly as the real
    #: Impl keeps its results in ``impl+0x88`` between the Cap-level calls.
    _cna: object | None = None
    #: ``AnsCnaParams`` for the run.  ``None`` means the ``0x100f8030`` ctor
    #: defaults, i.e. ``ansel-cna-default-default.dpi``.
    cna_params: object | None = None

    def cna_acquire(self, holder, arg2) -> AnsStatus:
        """``0x10132dc0`` -> ``0x1022ea50``.

        ``arg2`` is the image descriptor -- see the Phase-2a note above -- so
        it is handed straight to ``pakon_cna.analyze_to_results``.  A caller
        that has not supplied a real image (the shell's own golden harness
        drives this with sentinels) gets the unported guard instead of a
        confusing ``AttributeError``.
        """
        if not CNA_ANALYZE_PORTED:
            self._unported("CNA_ANALYZE_PORTED", "cna.acquire")
        import pakon_cna
        if not isinstance(arg2, pakon_cna.CnaImage):
            raise TypeError(
                "cna.acquire: arg2 is analyzeAutoTone's [ebp+0x10] and reaches "
                f"0x1022ea50 as the image descriptor, but got {type(arg2)!r}. "
                "Pass a pakon_cna.CnaImage, or override cna_acquire.")
        self._cna = pakon_cna.analyze_to_results(arg2, self.cna_params)
        return AnsStatus.OK

    def cna_get_results(self) -> bytes:
        """``0x10132ed0`` -> ``0x101320b0``'s 0x18-dword ``rep movsd``."""
        if not CNA_ANALYZE_PORTED:
            self._unported("CNA_ANALYZE_PORTED", "cna.getResults")
        if self._cna is None:
            raise RuntimeError(
                "cna.getResults before cna.acquire -- the real 0x101320b0 "
                "would copy whatever AnsCnaResults window the Impl last left "
                "at impl+0x88.")
        return self._cna.raw

    def cna_get_params(self) -> bytes:
        """``0x10132ea0`` -> ``0x10132070``'s 0x1f-dword ``rep movsd``."""
        if not CNA_ANALYZE_PORTED:
            self._unported("CNA_ANALYZE_PORTED", "cna.getParams")
        import pakon_cna
        p = self.cna_params if self.cna_params is not None \
            else pakon_cna.default_params()
        return pakon_cna.params_to_bytes(p)

    # -- dra -----------------------------------------------------------
    #: Set by either acquire method and read by ``dra_get_results``, exactly
    #: as the real Impl keeps ``AnsDraResults`` at ``impl+0x1c88`` between
    #: the Cap-level calls.
    _dra: object | None = None
    #: ``AnsDraParams`` for the run.  ``None`` means the shipped
    #: ``ansel-dra-default-default.dpi`` (``pakon_dra.DraParams.load``).
    dra_params: object | None = None
    #: The int16 sequences behind the ``short*`` at
    #: ``lum_hist``/``edge_hist``/``tone`` -- each may be a sequence or a
    #: ``pointer -> sequence`` callable, same convention as
    #: ``tone_helper_lum_hist``/``.../tone_lut`` and ``ast_tone_lut``.
    dra_lum_hist = None
    dra_edge_hist = None
    dra_tone_lut = None
    #: The synthetic pointer value ``dra_get_results`` reports for DraLut.
    #: The shell only compares it against 0 and threads it onward as
    #: ``ctx.tone_object``; the real array is ``self._dra.DraLut``.  Kept
    #: distinct from ``contrast_out_lut_pointer`` (0x40000000) so the two
    #: tokens are never confusable if both ever show up in the same trace.
    dra_out_lut_pointer = 0x41000000

    @staticmethod
    def _dra_resolve(name: str, value, ptr):
        if callable(value):
            value = value(ptr)
        if value is None:
            raise RuntimeError(
                f"DRA_ANALYZE_PORTED is True but dra.acquireHist was handed "
                f"the opaque pointer {ptr!r} for {name} with no "
                f"AutoToneSubsystems.dra_{name} to read behind it. Set it "
                f"to the sequence (or a pointer->sequence callable), or "
                f"override dra_acquire_with_hist -- see pakon_dra.py.")
        return value

    def dra_acquire_with_hist(self, holder, lum_hist, edge_hist, tone):
        """``0x10131100`` -> ``0x1022b530`` -- the histograms-in overload.

        Reached whenever cna produced a tone object (``ctx.tone_object``,
        the ``tone`` argument here), which is the shipped colour-negative
        path.  ``lighting`` is hardcoded 0 (Normal): a real
        ``find("lighting")`` always MISSES for CN-Enhanced (``"lighting"``
        is never in its declared capability list) and a miss yields 0 --
        Unicorn-verified against the real DLL in
        ``pakon_dra_golden.check_lighting``, not assumed here.
        """
        if not DRA_ANALYZE_PORTED:
            self._unported("DRA_ANALYZE_PORTED", "dra.acquireHist")
        import pakon_dra as _dra_mod
        p = self.dra_params or _dra_mod.DraParams.load(_dra_mod.VENDOR_DRA_DIR)
        self._dra = _dra_mod.analyze_hist(
            p,
            self._dra_resolve("lum_hist", self.dra_lum_hist, lum_hist),
            self._dra_resolve("edge_hist", self.dra_edge_hist, edge_hist),
            self._dra_resolve("tone_lut", self.dra_tone_lut, tone),
            0)
        return AnsStatus.OK

    def dra_acquire(self, holder, arg2):
        """``0x10131020`` -> ``0x1022af20`` -- the no-tone-object overload.

        Only reached when cna produced no tone object, which does not
        happen on the shipped colour-negative path (mirrors
        ``tone_helper_acquire``'s own note on its equivalent branch).
        ``arg2`` is analyzeAutoTone's own ``[ebp+0x10]``, the same image
        descriptor ``cna_acquire`` receives -- a ``pakon_cna.CnaImage``.
        """
        if not DRA_ANALYZE_PORTED:
            self._unported("DRA_ANALYZE_PORTED", "dra.acquire")
        import pakon_cna
        import pakon_dra as _dra_mod
        if not isinstance(arg2, pakon_cna.CnaImage):
            raise TypeError(
                "dra.acquire: arg2 is analyzeAutoTone's [ebp+0x10] and "
                f"reaches 0x1022af20 as the image descriptor, but got "
                f"{type(arg2)!r}. Pass a pakon_cna.CnaImage, or override "
                "dra_acquire.")
        p = self.dra_params or _dra_mod.DraParams.load(_dra_mod.VENDOR_DRA_DIR)
        n = arg2.width * arg2.height
        pixels = struct.pack(f"<{3 * n}h", *arg2.pixels)
        self._dra = _dra_mod.analyze_image(p, pixels, arg2.width, arg2.height, 0)
        return AnsStatus.OK

    def dra_get_results(self) -> bytes:
        """``0x10131220`` -> ``0x10130390``'s ``rep movsd`` 0xf dwords."""
        if not DRA_ANALYZE_PORTED:
            self._unported("DRA_ANALYZE_PORTED", "dra.getResults")
        if self._dra is None:
            raise RuntimeError(
                "dra.getResults before dra.acquire(WithHist) -- the real "
                "0x10130390 would copy whatever AnsDraResults window the "
                "Impl last left at impl+0x1c88.")
        return self._dra.to_bytes(dra_lut_pointer=self.dra_out_lut_pointer)

    # -- toneHelper --------------------------------------------------------

    #: ``AnsToneHelperParams`` for this scan path.  ``None`` means
    #: ``pakon_toneHelper.load_params()``, i.e. the shipped
    #: ``toneHelper-default.dpi`` + ``AllOnTree1``, which is what
    #: ``toneHelper.map`` selects for CN-Enhanced.
    tone_helper_params = None
    #: The three buffers the shell passes as opaque pointers.  Each may be a
    #: sequence or a ``pointer -> sequence`` callable, same convention as
    #: ``contrast_tone_lut``.  ``lum_hist``/``edge_hist`` are cna's
    #: ``AnsCnaResults.LuminanceHist``/``.EdgeHist``; ``tone_lut`` is whatever
    #: ``ctx+0x64d0`` points at by stage 3.
    tone_helper_lum_hist = None
    tone_helper_edge_hist = None
    tone_helper_tone_lut = None
    #: The last ``AnsToneHelperResults``, kept between acquire and getResults.
    tone_helper_results = None

    @staticmethod
    def _resolve(name, value, ptr):
        if callable(value):
            value = value(ptr)
        if value is None:
            raise RuntimeError(
                f"TONEHELPER_ACQUIRE_HIST_PORTED is True but th.acquireHist "
                f"was handed the opaque pointer {ptr!r} for {name} with no "
                f"AutoToneSubsystems.tone_helper_{name} to read behind it. "
                f"Set it to the sequence (or a pointer->sequence callable), "
                f"or override tone_helper_acquire_with_hist -- see "
                f"pakon_toneHelper.py.")
        return value

    def tone_helper_acquire_with_hist(self, holder, lum_hist, edge_hist,
                                      ctx, tone):
        """``0x1010c3b0`` -> ``0x101dd1b0`` -- the histogram-fed overload.

        The Cap wrapper substitutes the capability object for ``holder``
        (``0x1010c406``) and forwards the rest unchanged, so the Impl sees
        ``(&status, cap, lumHist, edgeHist, &ctx[0x4bc], tone)``.  ``holder``
        is therefore dropped here: the only thing read off it downstream is
        byte ``+0xe``, and that gates a buffer free with no result effect.

        ``ctx`` is passed BY ADDRESS by the shell and lands at ``impl+0x128``
        as metric id 30, ``EXPOSURE``.  It is the only scalar input, and it
        comes from ``ctx+0x4bc`` -- **not** from dei.
        """
        if not TONEHELPER_ACQUIRE_HIST_PORTED:
            self._unported("TONEHELPER_ACQUIRE_HIST_PORTED", "th.acquireHist")
        import pakon_toneHelper as _th
        p = self.tone_helper_params or _th.load_params()
        exposure = getattr(ctx, "tone_helper_scalar", ctx)
        self.tone_helper_results = _th.analyze_with_histograms(
            p,
            self._resolve("lum_hist", self.tone_helper_lum_hist, lum_hist),
            self._resolve("edge_hist", self.tone_helper_edge_hist, edge_hist),
            self._resolve("tone_lut", self.tone_helper_tone_lut, tone),
            exposure)

    def tone_helper_acquire(self, holder, arg2, ctx, tone):
        """``0x1010c0f0`` -> ``0x101dcc50`` -- the image-fed overload.

        Only reached when cna produced no edge histogram (``0x100fc334``),
        which does not happen on the shipped colour-negative path.  Its
        orchestration is transcribed in
        ``pakon_toneHelper.analyze_from_image``'s docstring, but the histogram
        and Laplacian-edge builder it needs (``0x101dbc00``) is unported, so
        this raises rather than silently substituting variant A.
        """
        if not TONEHELPER_ACQUIRE_IMAGE_PORTED:
            self._unported("TONEHELPER_ACQUIRE_IMAGE_PORTED", "th.acquire")

    def tone_helper_get_results(self) -> bytes:
        """``0x1010c6a0`` -> ``0x1010bb40`` -- ``rep movsd`` 0x2f dwords.

        The shell reads only ``+0xb4``, but it memcpys all 0xbc bytes, so the
        whole window is serialised through ``pakon_toneHelper``'s own layout.
        The ten heap-pointer slots come back 0: they are real addresses in the
        DLL and meaningless to a host caller, and nothing reads them.
        """
        if not TONEHELPER_ACQUIRE_HIST_PORTED:
            self._unported("TONEHELPER_ACQUIRE_HIST_PORTED", "th.getResults")
        if self.tone_helper_results is None:
            raise RuntimeError("th.getResults before th.acquire")
        return self.tone_helper_results.to_bytes()

    # -- contrast ----------------------------------------------------------

    #: ``AnsContrastAdjustCapabilityImpl`` state, lazily created on first use.
    contrast_state = None
    #: The params ``selectParams`` resolved from the scene's DPI.  ``None``
    #: means ``AnsContrastAdjustParams``' constructor defaults; the shipped
    #: unit's are ``pakon_contrast.parse_dpi(contrast-CNEnhanced.dpi)``.
    contrast_params = None
    #: ``cap+0xe``, the third capability flag byte.  ``declareAutoTone`` never
    #: writes it and ``AnsContrastAdjustCapability``'s ctor sets it to 0
    #: (``0x10109fc0``), so the shipped default is False -- which makes analyze
    #: free its two intermediate LUTs and report CAdjLut/InToneLut as NULL.
    #: It does not affect OutToneLut, i.e. not the image.
    contrast_keep_intermediates = None
    #: The int16 sequence behind the ``short*`` at ``ctx+0x64d0``, or a callable
    #: ``pointer -> sequence`` -- same contract as ``ast_tone_lut``.
    contrast_tone_lut = None
    #: The synthetic pointer value ``contrast_get_results`` reports for
    #: ``OutToneLut``.  The shell only ever compares it against 0 and threads it
    #: onward, so any stable non-zero value works; the LUT itself is readable
    #: from ``contrast_state.results.OutToneLut``.  Kept below 0x80000000 so
    #: it round-trips identically through signed and unsigned readers.
    contrast_out_lut_pointer = 0x40000000

    def contrast_acquire(self, holder, scene_type, x, tone):
        """Stage 4, ``0x1010a510`` -> ``0x101d8880``.  See ``pakon_contrast``.

        ``holder`` is accepted and dropped: ``0x101d8880`` uses it only to
        resolve the scene it reads the DPI name from, which is modelled by
        ``contrast_params`` instead (the lookup is of an already-parsed table).
        ``scene_type`` picks the ``constrainSlope`` slope-limit band and ``x``
        breaks the tie for scene types outside ``[1, 6]``; ``tone`` is the
        shell's ``ctx+0x64d0``.
        """
        if not CONTRAST_ANALYZE_PORTED:
            self._unported("CONTRAST_ANALYZE_PORTED", "contrast.acquire")
        import pakon_contrast as _cx
        lut = self.contrast_tone_lut
        if callable(lut):
            lut = lut(tone)
        if lut is None and tone:
            raise RuntimeError(
                f"CONTRAST_ANALYZE_PORTED is True but contrast.acquire was "
                f"handed the opaque tone pointer {tone:#x} with no "
                f"contrast_tone_lut to read behind it. Set "
                f"AutoToneSubsystems.contrast_tone_lut to the int16 sequence "
                f"(or a pointer->sequence callable), or override "
                f"contrast_acquire -- see pakon_contrast.py.")
        if self.contrast_state is None:
            self.contrast_state = _cx.ContrastImpl()
            self.contrast_state.set_params(
                self.contrast_params or _cx.ContrastParams())
        keep = self.contrast_keep_intermediates
        if keep is None:
            keep = _cx.CONTRAST_KEEP_INTERMEDIATES_DEFAULT
        # tone == 0 reaches analyze as a NULL LUT, which only the two OVERRIDE
        # modes survive (0x101d82d5); every other mode returns OK having built
        # nothing.  That is the DLL's behaviour, not an error.
        self.contrast_state.analyze(None, scene_type, x,
                                    lut if tone else None,
                                    keep_intermediates=keep)

    def contrast_get_results(self) -> bytes:
        """``0x1010ad20`` -> ``0x10109d70`` -- ``rep movsd`` 0xb dwords.

        Serialised through ``AUTOTONE_WORK_LAYOUT``'s offsets, with the three
        LUT members reported as pointers because that is what the shell reads
        them as.  ``CAdjLut`` and ``InToneLut`` come back 0 unless
        ``contrast_keep_intermediates`` is set, exactly as ``cap+0xe == 0``
        makes the real ``0x101d8633`` free them.
        """
        if not CONTRAST_ANALYZE_PORTED:
            self._unported("CONTRAST_ANALYZE_PORTED", "contrast.getResults")
        if self.contrast_state is None:
            raise RuntimeError("contrast.getResults before contrast.acquire")
        r = self.contrast_state.results
        base = self.contrast_out_lut_pointer
        return r.to_bytes(
            ptr_adj=base + 0x10000 if r.CAdjLut is not None else 0,
            ptr_in=base + 0x20000 if r.InToneLut is not None else 0,
            ptr_out=base if r.OutToneLut is not None else 0)

    # -- ast / pfd / citras ------------------------------------------------

    #: ``AnsAstCapabilityImpl`` state (its ``+0x10``…``+0x3c``), lazily created.
    ast_state = None
    #: The int16 sequence behind the ``short*`` the shell threads, or a
    #: callable ``pointer -> sequence``.  See ``ast_analyze``.
    ast_tone_lut = None

    def ast_analyze(self, holder, tone):
        """Stage 5, ``0x1012f3f0`` -> ``0x10227160``.  See ``pakon_ast``.

        ``holder`` is accepted and dropped: the Impl only releases the smart
        pointer the Cap wrapper hands it (``0x102275a2``) and never reads
        through it.  ``tone`` is the shell's ``ctx+0x64d0`` — and unlike every
        other stage's, ast's copy of it is **read-only**; ast writes its float
        LUT into its own Impl at ``+0x3c`` and nothing in ``analyzeAutoTone``
        reads it back.

        The shell models ``tone`` as the raw pointer value it is, and this
        class has no memory behind it, so a caller that wants ast's arithmetic
        to actually run has to supply the LUT via ``ast_tone_lut`` (a sequence,
        or a callable taking the pointer).  With neither, this raises rather
        than quietly producing nothing — a shell-only caller that does not care
        about ast's output should override this method, the way
        ``pakon_autotone_shell_golden.PatternSubsystems`` does.
        """
        if not AST_ANALYZE_PORTED:
            self._unported("AST_ANALYZE_PORTED", "ast.analyze")
        import pakon_ast as _ast
        lut = self.ast_tone_lut
        if callable(lut):
            lut = lut(tone)
        if lut is None and tone:
            raise RuntimeError(
                f"AST_ANALYZE_PORTED is True but ast.analyze was handed the "
                f"opaque tone pointer {tone:#x} with no ast_tone_lut to read "
                f"behind it. Set AutoToneSubsystems.ast_tone_lut to the int16 "
                f"sequence (or a pointer->sequence callable), or override "
                f"ast_analyze -- see pakon_ast.py.")
        if self.ast_state is None:
            self.ast_state = _ast.AstSubsystem()
        # tone == 0 is the DLL's own early-out at 0x102271e8, not an error.
        self.ast_state.analyze(lut if tone else None)

    def pfd_analyze(self, holder, lut_size, tone):
        if not PFD_ANALYZE_PORTED:
            self._unported("PFD_ANALYZE_PORTED", "pfd.analyze")

    #: ``AnsCitrasCapabilityImpl`` state, lazily created on first use so the
    #: shell keeps working without one.  ``analyze`` is the object's only
    #: mutator, and it owns the LUT it copies.
    citras_state = None

    def citras_analyze(self, holder, lut_size, tone):
        """Stage 7, ``0x1012c490`` -> ``0x10223a20``.  See ``pakon_citras``.

        ``holder`` is accepted and dropped: the Impl only releases the smart
        pointer the Cap wrapper hands it (``0x10223c58``) and never reads
        through it.  ``tone`` is the shell's ``ctx+0x64d0``.
        """
        if not CITRAS_ANALYZE_PORTED:
            self._unported("CITRAS_ANALYZE_PORTED", "citras.analyze")
        import pakon_citras as _citras
        if self.citras_state is None:
            self.citras_state = _citras.CitrasState()
        return _citras.citras_analyze(self.citras_state, tone, lut_size)


# ---------------------------------------------------------------------------
# field readers over a raw results buffer
# ---------------------------------------------------------------------------


def _u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def _i32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<i", buf, off)[0]


def read_field(struct_name: str, buf: bytes, field_name: str):
    """Read one named field out of a raw results buffer via the layout table."""
    off = layout_offset(struct_name, field_name)
    for o, n, kind, _s in AUTOTONE_WORK_LAYOUT[struct_name]["fields"]:
        if n != field_name:
            continue
        if kind == "f32":
            return struct.unpack_from("<f", buf, o)[0]
        if kind == "i16":
            return struct.unpack_from("<h", buf, o)[0]
        if kind == "bool":
            return bool(buf[o])
        return _i32(buf, o)
    raise KeyError(field_name)   # pragma: no cover - layout_offset already threw


# ---------------------------------------------------------------------------
# the shell
# ---------------------------------------------------------------------------

CNA_LUT_SIZE_SEED = 0x1000   # mov dword [ebp-0x40], 0x1000 @ 0x100fbfd3


def analyze_auto_tone(
    ctx: AutoToneContext,
    capset: CapabilitySet,
    holder: object,
    arg2: object,
    subsystems: AutoToneSubsystems | None = None,
    *,
    trace: AutoToneTrace | None = None,
) -> AnsStatus:
    """``ColorNegativePath::analyzeAutoTone`` (``0x100fb730``), shell only.

    Args mirror the DLL's: ``holder`` is ``[ebp+0xc]``, ``arg2`` is
    ``[ebp+0x10]``, ``ctx`` is ``[ebp+0x14]``.  The hidden ``AnsStatus&``
    sret (``[ebp+8]``) is the return value here.

    Raises ``AutoToneError`` where the DLL calls ``0x1001ed90`` (a
    "<Name> capability not found." throw); returns a non-OK ``AnsStatus``
    where it calls ``0x1001f770`` and returns.
    """
    if not AUTOTONE_SHELL_PORTED:
        raise RuntimeError("AUTOTONE_SHELL_PORTED is False")
    subs = subsystems if subsystems is not None else AutoToneSubsystems()
    tr = trace if trace is not None else AutoToneTrace()

    # 0x100fb787 — `mov dword [eax+0x64d0], edi` with edi == 0, before any
    # lookup. Null is the integer 0 here, not None: it is compared with
    # `test eax, eax` and handed to citras/pfd as an argument verbatim.
    ctx.tone_object = 0
    lut_size = 0            # [ebp-0x40], 0x100fb78d
    lum_hist = None         # [ebp-0x34], 0x100fb790
    edge_hist = None        # [ebp-0x4c], 0x100fb793
    tone_helper_value = 1   # [ebp-0x3c], 0x100fb796 (ebx == 1)
    elmo_occured = False    # [ebp-0x29], 0x100fb799
    elmo_aggressiveness = 1  # [ebp-0x48], 0x100fb79d (ebx == 1)

    # -- phase 1: the seven lookups, in LOOKUP_ORDER -----------------------
    caps: dict[str, Capability] = {}
    for spec in CAPABILITIES:
        tr.lookups.append(spec.name)
        status, iface = capset.find(spec.name)
        if status:                                   # never, per 0x10029034
            return status
        cap = rt_dynamic_cast(iface, spec)
        if cap is None:
            tr.not_found = spec.not_found_msg
            raise AutoToneError(
                f"{spec.not_found_msg} [{FUNC_NAME}, {SRC_FILE}:"
                f"{spec.find_line}]")
        caps[spec.key] = cap

    def _fail(call_key: str) -> AnsStatus:
        c = CAP_CALL_BY_KEY[call_key]
        return AnsStatus(call_key, SRC_FILE, c.err_line, FUNC_NAME)

    # -- stage 1: cna, 0x100fbdf8 ------------------------------------------
    if caps["cna"].enabled:
        tr.calls.append(("cna.acquire", (holder, arg2)))
        if subs.cna_acquire(holder, arg2):
            return _fail("cna.acquire")
        res = bytearray(default_construct("AnsCnaResults"))   # 0x100fbea8
        tr.calls.append(("cna.getResults", ()))
        got = subs.cna_get_results()
        if isinstance(got, AnsStatus) and got:
            return _fail("cna.getResults")
        res[:len(got)] = got                                   # rep movsd 0x60
        ctx.tone_object = _u32(res, layout_offset(
            "AnsCnaResults", "ToneScaleLut"))                  # 0x100fbfc1
        lut_size = CNA_LUT_SIZE_SEED                           # 0x100fbfd3
        lum_hist = _u32(res, layout_offset(
            "AnsCnaResults", "LuminanceHist"))                 # 0x100fbfda
        edge_hist = _u32(res, layout_offset(
            "AnsCnaResults", "EdgeHist"))                      # 0x100fbfdd
        par = bytearray(default_construct("AnsCnaParams"))     # 0x100f8030
        tr.calls.append(("cna.getParams", ()))
        gotp = subs.cna_get_params()
        if isinstance(gotp, AnsStatus) and gotp:
            return _fail("cna.getParams")
        par[:len(gotp)] = gotp                                 # rep movsd 0x7c
        elmo_occured = bool(res[layout_offset(
            "AnsCnaResults", "bElmoOccured")])                 # 0x100fc084
        elmo_aggressiveness = _i32(par, layout_offset(
            "AnsCnaParams", "elmoAggressiveness"))             # 0x100fc087
    tr.tone_after.append(("cna", ctx.tone_object))

    # -- stage 2: dra, 0x100fc098 ------------------------------------------
    if caps["dra"].enabled:
        if ctx.tone_object:                                    # 0x100fc0af
            tr.calls.append(("dra.acquireHist",
                             (holder, lum_hist, edge_hist, ctx.tone_object)))
            if subs.dra_acquire_with_hist(holder, lum_hist, edge_hist,
                                          ctx.tone_object):
                return _fail("dra.acquireHist")
        else:
            tr.calls.append(("dra.acquire", (holder, arg2)))
            if subs.dra_acquire(holder, arg2):
                return _fail("dra.acquire")
        res = bytearray(default_construct("AnsDraResults"))    # not seeded
        tr.calls.append(("dra.getResults", ()))
        got = subs.dra_get_results()
        if isinstance(got, AnsStatus) and got:
            return _fail("dra.getResults")
        res[:len(got)] = got                                   # rep movsd 0x3c
        lut_size = _i32(res, layout_offset(
            "AnsDraResults", "nSmallBins"))                    # 0x100fc2fd
        ctx.tone_object = _u32(res, layout_offset(
            "AnsDraResults", "DraLut"))                        # 0x100fc30c
    tr.tone_after.append(("dra", ctx.tone_object))

    # -- stage 3: toneHelper, 0x100fc312 -----------------------------------
    if caps["tone_helper"].enabled:
        if ctx.tone_object:                                    # 0x100fc329
            if edge_hist:                                      # 0x100fc334
                tr.calls.append(("th.acquireHist",
                                 (holder, lum_hist, edge_hist,
                                  CTX_TONEHELPER_SCALAR, ctx.tone_object)))
                if subs.tone_helper_acquire_with_hist(
                        holder, lum_hist, edge_hist, ctx, ctx.tone_object):
                    return _fail("th.acquireHist")
            else:
                tr.calls.append(("th.acquire",
                                 (holder, arg2, CTX_TONEHELPER_SCALAR,
                                  ctx.tone_object)))
                if subs.tone_helper_acquire(holder, arg2, ctx,
                                            ctx.tone_object):
                    return _fail("th.acquire")
        res = bytearray(default_construct("AnsToneHelperResults"))  # 0x10064d70
        tr.calls.append(("th.getResults", ()))
        got = subs.tone_helper_get_results()
        if isinstance(got, AnsStatus) and got:
            return _fail("th.getResults")
        res[:len(got)] = got                                   # rep movsd 0xbc
        tone_helper_value = _i32(res, layout_offset(
            "AnsToneHelperResults", "toneHelperValue"))        # 0x100fc5c4
    tr.tone_after.append(("toneHelper", ctx.tone_object))

    # -- between 3 and 4: 0x100fc5cd ---------------------------------------
    if elmo_occured:
        x = elmo_aggressiveness                                # 0x100fc5dd
        if 3 <= ctx.scene_type <= 6:                           # 0x100fc5da/e2
            ctx.scene_type = 0                                 # 0x100fc5e7
    else:
        x = tone_helper_value                                  # 0x100fc5f0

    # -- stage 4: contrast, 0x100fc5f3 -------------------------------------
    if caps["contrast"].enabled:
        tr.calls.append(("contrast.acquire",
                         (holder, ctx.scene_type, x, ctx.tone_object)))
        if subs.contrast_acquire(holder, ctx.scene_type, x, ctx.tone_object):
            return _fail("contrast.acquire")
        res = bytearray(
            default_construct("AnsContrastAdjustResults"))     # 0x100fc6b5
        tr.calls.append(("contrast.getResults", ()))
        got = subs.contrast_get_results()
        if isinstance(got, AnsStatus) and got:
            return _fail("contrast.getResults")
        res[:len(got)] = got                                   # rep movsd 0x2c
        lut_size = _i32(res, layout_offset(
            "AnsContrastAdjustResults", "lutSize"))            # 0x100fc78c
        ctx.tone_object = _u32(res, layout_offset(
            "AnsContrastAdjustResults", "OutToneLut"))         # 0x100fc798
    tr.tone_after.append(("contrast", ctx.tone_object))

    # -- stage 5: ast, 0x100fc79e ------------------------------------------
    if caps["ast"].enabled:
        tr.calls.append(("ast.analyze", (holder, ctx.tone_object)))
        if subs.ast_analyze(holder, ctx.tone_object):
            return _fail("ast.analyze")

    # -- stage 6: pfd, 0x100fc901 (enable byte forced 0 at 0x100f9da2) -----
    if caps["pfd"].enabled:
        tr.calls.append(("pfd.analyze", (holder, lut_size, ctx.tone_object)))
        if subs.pfd_analyze(holder, lut_size, ctx.tone_object):
            return _fail("pfd.analyze")

    # -- stage 7: citras, 0x100fc9c3 ---------------------------------------
    if caps["citras"].enabled:
        tr.calls.append(("citras.analyze",
                         (holder, lut_size, ctx.tone_object)))
        if subs.citras_analyze(holder, lut_size, ctx.tone_object):
            return _fail("citras.analyze")

    # -- epilogue, 0x100fcb29 ----------------------------------------------
    if ctx.scene_type == 1:
        ctx.tone_object = 0

    tr.lut_size = lut_size
    tr.lum_hist = lum_hist
    tr.edge_hist = edge_hist
    tr.elmo_occured = elmo_occured
    tr.elmo_aggressiveness = elmo_aggressiveness
    tr.tone_helper_value = tone_helper_value
    return AnsStatus.OK


def make_default_capability_set(*, enable: Sequence[str] | None = None,
                                impl_factory: Callable[[str], object] | None = None
                                ) -> CapabilitySet:
    """The set ``declareAutoTone`` leaves behind: six on, pfd off."""
    cs = CapabilitySet()
    for spec in CAPABILITIES:
        on = bool(spec.declare_enabled) if enable is None \
            else spec.name in enable
        cs.insert(Capability(
            name=spec.name, rtti_class=spec.rtti_class, enabled=on,
            flag_d=bool(spec.declare_enabled),
            impl=impl_factory(spec.name) if impl_factory else None))
    return cs


def main() -> None:
    print(f"ColorNegativePath::analyzeAutoTone {ANALYZE_AUTO_TONE:#010x}")
    print(f"  shell residual: 20 fns / 8,533 B "
          f"(walk(0x100fb730) 166/68,323 minus 14 subsystem Impls)")
    print(f"  find thunk {CAP_FIND_THUNK:#010x} -> "
          f"AnsCapabilitySet::find {CAP_SET_FIND:#010x} "
          f"(NOT AnsSceneContext::find 0x10022a40)")
    print("  lookup order : " + ", ".join(LOOKUP_ORDER))
    print("  declare order: " + ", ".join(DECLARE_ORDER))
    print()
    for spec in CAPABILITIES:
        print(f"    {spec.name:<11} slot ebp{spec.slot:+#05x}  "
              f"rtti {spec.rtti_target:#x} {spec.rtti_class:<28} "
              f"+0xc={spec.declare_enabled} @ {spec.declare_enable_va:#x}")
    print()
    for name, spec in AUTOTONE_WORK_LAYOUT.items():
        named = [f for f in spec["fields"] if f[1]]
        print(f"    {name:<26} size {spec['size']:#05x}  "
              f"{len(named)} named / {len(spec['fields'])} slots  "
              f"getter {spec['getter'] and hex(spec['getter'])}")
    print()
    print(f"  AUTOTONE_SHELL_PORTED={AUTOTONE_SHELL_PORTED} "
          f"WORK_LAYOUT={AUTOTONE_WORK_LAYOUT_PORTED} "
          f"FIND={AUTOTONE_CAPABILITY_FIND_PORTED} "
          f"RTTI={AUTOTONE_RTTI_DISPATCH_PORTED} PFD_STAGE={PFD_STAGE_PORTED}")
    print(f"  subsystems: CNA={CNA_ANALYZE_PORTED} DRA={DRA_ANALYZE_PORTED} "
          f"TONEHELPER={TONEHELPER_ANALYZE_PORTED} "
          f"CONTRAST={CONTRAST_ANALYZE_PORTED} AST={AST_ANALYZE_PORTED} "
          f"CITRAS={CITRAS_ANALYZE_PORTED} PFD={PFD_ANALYZE_PORTED}")
    cs = make_default_capability_set()
    print("  default set  : " + ", ".join(
        f"{c.name}{'' if c.enabled else '(off)'}" for c in cs.items.values()))
    try:
        analyze_auto_tone(AutoToneContext(), cs, holder=None, arg2=None)
    except RuntimeError as exc:
        print(f"  unported guard fires as designed: {exc}")


if __name__ == "__main__":
    main()
