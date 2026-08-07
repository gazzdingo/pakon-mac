#!/usr/bin/env python3
"""Shasta path (PakonIMAu.dll) — verified fragments only.

Do **not** invent scene ``toneLut`` maths. Shasta analyze builds LUTs from
the analysis image; shipped ``common-sraFwdLut-*.lut`` is a **different**
capability (``AnsCommonSraFwdLutDPI`` / SRA). See relationship section.

VERIFIED (image base ``0x10000000``)
====================================

Capability surface
------------------
* ``AnsShastaCapabilityImpl::analyze`` @ ``0x101e5250``.
* ``export`` impl ~``0x101e5ca0``; ``generateOtherLuts`` @ ``0x101e2030``.
* ``getToneLut`` @ ``0x101e4670`` (string ``0x1059ab38``): copies
  CapabilityImpl ``vector<int32>`` at ``this+0x3e0/+0x3e4`` → caller
  ``int16[]`` (``mov dx, word [base+eax*4]``).
* ``setToneLut`` @ ``0x101e48d0`` (string ``0x1059ab5c``): int16 → dword
  at CapabilityImpl ``+0x3e0`` (vector obj @ ``+0x3dc``). Sole direct
  Cap ``+0x3e0`` writer found; wrapper ``0x1010d1b0`` ←
  ``shastaMethods.cpp`` sites ``0x1011678d`` / ``0x101169c8``.
* Path glue: ``analyzeWithShastaTriage`` / ``genShastaImages``.
* ``ImaShastaOp`` I16-only (``0x1057c848``).

Analyze → toneLut call chain (cited)
------------------------------------
1. ``AnsShastaCapabilityImpl::analyze`` @ ``0x101e5250``
2. calls ``0x1027be10`` @ ``0x101e584d`` (stores aim codes, runs image
   helpers), then generate @ ``0x101e5960`` → ``0x10245ed0``
   (``ShastaGenerate.cpp``, dumps ``toneLut.lut`` @ ``0x10245f57``)
3. generate calls toneLut builder ``0x10293ee0`` (sole caller ``0x10245f2b``)
4. builder first calls breakpoint prep ``0x1027b1c0``, then curve helpers
   ``0x10293960`` (×2) and ``0x10293d50``, then a clamp loop on the LUT

Working Generate/Shasta object layout (stack @ analyze ``ebp-0x770``)
--------------------------------------------------------------------
* ``toneLut`` ``vector<int32>`` @ ``+0x3ac`` / begin ``+0x3b0/+0x3b4``
  (stride 4; dump ``toneLut.lut``).
* ``blackNoiseLut`` @ ``+0x3c0`` (dump ``blackNoiseLut.lut``).
* On the **same** Generate object, ``+0x3e0`` is **not** Cap toneLut:
  ``0x102460a0`` dumps it as ``slopeLut.lut`` with ``sar …, 3`` (8-byte
  elems). Sibling dumps: ``shadowDesatLut`` @ ``+0x3d0``, ``astLut`` @
  ``+0x3f0``, ``ataLut`` @ ``+0x400``.
* Integer codes ``+0x2b0/+0x2b4/+0x2b8/+0x2bc``: stored by ``0x1027be10``
  from analyze args; seed ``toneLut[code]=code`` uses ``+0x2b0``
  (@ ``0x102940d9``).
* ``+0x58``: scale in ``0x1027b1c0`` (dpi ``codeValuesPerButton`` role —
  offset↔dpi map not fully proven).
* Prep ``0x1027b1c0`` (verified arithmetic):

  ``fist(q[+0xd8]*q[+0xb0]*q[+0x58] + 0.5)`` → ``+0x2c0``;
  ``[+0x48] - that`` → ``+0x328``;
  similarly ``+0xe0/+0xb8`` → ``+0x2c4`` / ``+0x32c`` (vs ``+0x2b0``);
  ``+0xe8/+0xc0`` → ``+0x2c8`` / ``+0x330``; …

* Before curve fill, ``0x10293ee0`` clamps many doubles to ``[0.0, 1.0]``
  (consts ``0x10573c40`` / ``0x10574f50``).

How analysis image relates to ``+0x2b0`` (VERIFIED call site)
------------------------------------------------------------
* ``0x1027be10`` (caller ``0x101e584d``):

  - Optional debug dumps ``"sampled"`` / ``"blockAvg"`` via vtable
    ``[+0x38]`` on ``this+8``.
  - **Stores** ``[ebp+0x10/+0x14/+0x18/+0x1c]`` →
    ``this+0x2b0/+0x2b4/+0x2b8/+0x2bc`` (analyze forwards
    ``[ebp+0x1c…+0x28]``).
  - Then ``0x1027b1c0`` (prep), ``0x1027b970`` (sampled/blockAvg),
    ``0x1027b3c0``, then ``0x102935d0``.
  - Also computes ``+0x308 = ((+0x2ec-+0x2e4-+0x2e8)+(+0x2f0))/2 / (+0x58*2.5)``
    style (const ``2.5`` @ ``0x105a5a20``) — image-derived side fields
    (``+0x2e4…+0x2f0``), **not** the four aim codes.

* Aim-arg call chain (cited):

  ``AnsCnPremiumPath::CnPremium_analyzeSceneSpecific`` ``0x10054800``
  (2nd caller ``0x1006fa90``) → ``analyzeWithShastaTriage`` ``0x10116040``
  @ ``0x10057111`` / ``0x100739a3`` → ``0x10114a50`` @ ``0x101162d8`` /
  ``0x1011661d`` → wrapper ``0x1010d8b0`` @ ``0x10114ade`` →
  ``AnsShastaCapabilityImpl::analyze`` ``0x101e5250`` @ ``0x1010d941`` →
  ``0x1027be10`` store.

* Triage stack args that become the four work codes (VA-proven):

  - CnPremium builds ShastaParams @ ``ebp-0x3fc`` (ctor ``0x100543b0`` /
    ``0x10054780``): ``+0x38=metricGray``, ``+0x3c=black``, ``+0x40=white``
    (dump ``0x101280a0…``; ctor defaults ``1550/600/2358``; overwritten by
    ``AnsShastaCapabilityImpl::selectParams`` ``0x101e4f50`` via
    ``0x1008e970`` copy from dpi-selected params).
  - Triage keeps a live ShastaParams @ ``ebp-0x4d8`` after its own
    ``selectParams`` (``0x10116150``); ``0x10114a50`` reads
    ``[params+0x38]`` → analyze → work ``+0x2b0``.
  - CnPremium ``[ebp+0x10]`` / ``[ebp+0x14]`` to triage = ``avg2largest``
    ``0x1004f690`` of two processed RGB int16 triples; those become
    work ``+0x2b4`` / ``+0x2b8``.
  - CnPremium pushes ``params+0x40`` (``white``) as triage ``[ebp+0x18]`` →
    work ``+0x2bc``.

  Store map (``0x1027be10``):

  ==========  =========================  ==============================
  work off    source                     cite
  ==========  =========================  ==============================
  ``+0x2b0``  ShastaParams ``metricGray``  triage local ``+0x38``
  ``+0x2b4``  ``avg2largest(dmin RGB)``    triage ``[ebp+0x10]``
  ``+0x2b8``  ``avg2largest(dmin+dens)``   triage ``[ebp+0x14]``
  ``+0x2bc``  ShastaParams ``white``       triage ``[ebp+0x18]``
  ==========  =========================  ==============================

* RGB mid-aim closed form (CnPremium ``0x10056663…0x100570b3``, core
  path when float-LUT flag ``[obj+0xc]==0`` — skip ``0x10056c61…``):

  1. Seed ``[ebp-0x34…]`` from ``params+0x3c`` (``black``), then overwrite
     via ``AnsSceneContext::find`` @ ``0x10022a40`` name ``"dmin"``
     (``0x105737c8``), size 6 (RGB int16). CnPremium call
     ``0x100566ac``. Insert writers: ``bAddScene`` ``0x10002523``
     (desc ``+0x54/+0x58/+0x5c``); ScpLutBalance ``0x100fdaa8`` after
     LUT-remap of ``path+0x3c`` (``0x100fd984``). Host bag I/O ported
     (``pakon_scene_context``). Live frame RGB via TLA FindDmin
     ``0x10009250`` → ``+0x6cac`` + ColNeg 1px remap
     (``FRAME_DMIN_RGB_PORTED`` / ``ADDSCENE_COLNEG_REMAP_PORTED``).
  2. Dens via ``NoiseMethods::getNoiseTable`` @ ``0x10112980`` (string
     ``0x105879f4``; CnPremium ``0x10056863``): QI ``"aneOrder"`` → Cap
     ``getResults`` ``0x10110830`` / Impl ``0x101ebe90``. Returned object
     ``+0x44=n``, ``+0x48`` advance, ``+0x4c=float*`` (ctor
     ``0x10195070`` / alloc ``0x102560a0``, ``n*ch*4``). Per channel
     ``i∈{0,1,2}`` @ ``0x100569a1…``:

     ``idx = clamp(dmin[i], 0, n-1)``;
     ``dens_i = ftol2(table[idx] * params+0x1c0)``
     (``blackNoiseSigmaMult``, dump ``0x1012896a``; ctor default ``2.0``
     @ ``0x10574f48``; stack alias ``[ebp-0x23c]``);
     ``dmin_dens[i] = int16(dmin[i] + dens_i)`` (16-bit wrap);
     advance ``table`` by ``n`` floats while ``i+1 < +0x48``.

     Layout ported (``pakon_ane_order.NoiseTable``); dens **fill** from
     curve rows ported (``get_results_fill_dens`` /
     ``ANE_GET_RESULTS_FILL_PORTED``). Analyze hist **bin-index** +
     dens-hist ``inc`` + neighbor merge + finalize knot/adjust +
     curve-row leaves ported (``ANE_ANALYZE_BIN_INDEX_PORTED`` /
     ``ANE_ANALYZE_HIST_ACCUM_PORTED`` /
     ``ANE_ANALYZE_NEIGHBOR_MERGE_PORTED`` /
     ``ANE_ANALYZE_FINALIZE_KNOT_PORTED`` /
     ``ANE_ANALYZE_FINALIZE_ADJUST_PORTED`` /
     ``ANE_CURVE_ROWS_FROM_DOUBLES_PORTED``); build orch ``0x1027e9d0``
     still WALL.
  3. Master LUT = global ``AnsLut`` @ ``0x106b5f74`` built by CRT init
     ``0x1056a470`` → ctor ``0x100f42a0(0xc, 0, 0xfff)``. Data pointer
     ``[0x106b5f7c] = alloc+0x10000`` (signed-int16 index 0). Fill:
     ``code<0 → 0``; ``0…4095 → identity``; ``>4095 → 4095``.
  4. Add scene setShifts OUT ``+0x4b6/+0x4b8/+0x4ba`` (int16) to both
     triples; remap each channel through master LUT (@ ``0x10056a0a…``).
  5. If any remapped dmin channel ``> params+0x38`` (``metricGray``),
     replace both triples (@ ``0x10056aab…``):

     ``dmin'[c] = lut[black + shift[c]]``;
     ``dmin_dens'[c] = lut[black + dens_i + shift[c]]``.
  6. Optional contrast remap if ``scene+0x30`` non-null and
     ``[+0xc]`` set (``0x10119060`` + plane stride ``0x1000`` @
     ``0x10589834``) — **not** host-ported.
  7. Optional float-table remap via ``0x1004f7b0`` (pointer =
     ``obj+4→+0x2c→+0x38 + idx*4``) + ``ftol2`` when flag set —
     **not** on the core path; **not** host-ported.
  8. ``0x1004f690`` on each triple → triage ``[ebp+0x10/+0x14]``.

* Dump names ``extShadowAim`` / ``cumExtShadowPt`` @ ``0x10589630…`` are
  **ShastaParams/Results fields** (``0x10128d20`` / ``0x10128033``), not
  the triage stack slots themselves. Input codes are
  ``metricGray`` / processed-dmin avgs / ``white``.

* Mid-aim **arithmetic** is host-ported (``cn_premium_mid_aim_rgb``;
  ``SHASTA_AIM_MID_RGB_PORTED``). Input **path** + ScpLut remap +
  ``getResults`` dens fill + AddScene desc pack + getCnContext path
  load + Ane hist leaves ported (``SHASTA_AIM_INPUT_PATH_PORTED`` /
  ``SCPLUT_DMIN_REMAP_PORTED`` / ``ANE_GET_RESULTS_FILL_PORTED`` /
  ``BADDSCENE_DMIN_PACK_PORTED`` / ``ADDSCENE_DESC_PACK_PORTED`` /
  ``PATH_DMIN_FROM_BAG_PORTED`` / ``ANE_ANALYZE_BIN_INDEX_PORTED`` /
  ``ANE_ANALYZE_HIST_ACCUM_PORTED`` / ``ANE_ANALYZE_NEIGHBOR_MERGE_PORTED`` /
  ``ANE_ANALYZE_FINALIZE_KNOT_PORTED`` / ``ANE_ANALYZE_FINALIZE_ADJUST_PORTED`` /
  ``ANE_CURVE_ROWS_FROM_DOUBLES_PORTED``). Host dens-hist→finalize→
  ``getResults`` compose is wired when dens-hists are supplied.
  **WALL for ``ANALYZE``:** live ``AneSampledImage`` /
  ``AneResidualImage`` producers (``collectData``); ``ANE_ORDER``
  shipped ``useAvg=0`` orch is ported. Contrast / float-LUT side
  paths. Do **not** invent
  percentile tone from dpi ``shadowPercent`` / ``highlightPercent``.

CapabilityImpl ``+0x3e0`` vs working ``+0x3b0`` (VERIFIED facts)
---------------------------------------------------------------
* Cap ``getToneLut`` / ``setToneLut`` use Cap ``+0x3e0`` as **int32**
  toneLut (``sar 2``).
* Generate object ``+0x3b0`` is the analyze-built toneLut; Generate
  ``+0x3e0`` is **slopeLut** (different meaning).
* Analyze body ``0x101e5250…0x101e5ca0`` has **no** ``+0x3ac/+0x3b0/
  +0x3dc/+0x3e0`` references. After generate it POD-copies ~``0x48``
  bytes ``Cap+0x2e0 ← work+0x2b0`` via ``0x1008e530``, optionally calls
  ``0x102460a0`` on the **stack** object, clears Cap ``+0x3c0/+0x3d0/
  +0x3f0``, then destroys the stack object — **no** verified
  ``Cap+0x3e0 ← work+0x3b0`` assign in that path.
* Export builds ``AnsShastaOperand`` (``0x100d0860``) from Cap ``+0x2e0``
  scalars (``0x1008ec40`` copies through ~``+0x2c8``) — not the toneLut
  vector.
* Therefore automatic Cap ``+0x3e0`` population from working ``+0x3b0``
  remains **UNKNOWN**.

Curve helpers — status
----------------------
* ``0x10292c50`` / ``0x10292cb0``: **ported + Unicorn-golden** (see
  ``curve_log_ratio_c50`` / ``curve_log_ratio_cb0``). Consts ``0.999`` @
  ``0x105a3c08``, clamps ``±2000`` @ ``0x105a77b0`` / ``0x105a77a8``.
* ``0x10292d30`` / ``0x10292d80``: **ported + Unicorn-golden**
  (``curve_exp_d30`` / ``curve_exp_d80``). ``d30(a,b,c) =
  c·exp(b/c)·(1−exp(−a/c))``; ``d80`` branches on ``b`` vs ``c``
  (sign of ``c`` flips the inequality) to ``d30(a,c,d)`` or
  ``d·(1−exp(−a/d))``. Const ``−1.0`` @ ``0x10574f58``.
* ``0x10293330`` / ``0x10293410`` / dispatcher ``0x10293510``:
  **ported + Unicorn-golden** (``curve_newton_330`` / ``410`` /
  ``curve_dispatch_93510``). Seed ``1.1`` @ ``0x10579a80``,
  tol ``0.1`` @ ``0x105a77a0``, ``edx=100``. Newton-330 damp on
  ``r < 0`` is ``err_prev > tol`` (DLL ``0x102933b8…c2``; earlier host
  ``<=`` was wrong at fill-scale args).
* ``0x10293960`` (~994 B): **ported + Unicorn-golden**
  (``tone_lut_fill_93960`` / ``SHASTA_CURVE_FILL_PORTED``).

* Builder ``0x10293ee0`` (~992 B, ret ``0x102942bf``): **ported +
  Unicorn-golden** with injected work fields
  (``tone_lut_builder_93ee0`` / ``SHASTA_TONE_LUT_BUILDER_PORTED``).
  Sole caller generate ``0x10245f2b`` pushes ``(+0x48−+0x2b0)``. Still
  Cap publish via ``setToneLut`` / ``assemble_tone_lut``.

  Flow (cited): prep ``0x1027b1c0`` → clamp blend doubles ``[0,1]`` →
  seed ``toneLut[+0x2b0]=+0x2b0`` → **fill#1** (up to ``+0x64``) →
  **fill#2** (down to ``0``) → ``0x10293d50(arg)`` → clamp loop.

  Fill param←work (stack blob @ builder; fill ``this``/``eax``):

  ==========  ==============================  ========================
  param off   fill#1 (highlight↑)             fill#2 (shadow↓)
  ==========  ==============================  ========================
  ``+0``      ``+0x334``                      ``+0x330``
  ``+4``      ``ftol2(+0x378)``                ``ftol2(+0x370)``
  ``+0x10``   ``+0x128`` if ``+0x378≥0`` else   ``+0x120`` if ``+0x370≥0`` else
              ``+0x138``                      ``+0x130``
  ``+0x20``   ``+0x148``                      ``+0x140``
  ``+0x28``   ``+0x338``                      ``+0x32c``
  ``+0x2c``   ``+0x300``                      ``+0x2f4``
  ``+0x30``   ``+0x340``                      ``+0x220``
  start/end   ``+0x2b0`` / ``+0x64``           ``+0x2b0`` / ``0``
  ==========  ==============================  ========================

  Guard (fill#1, ``code_end`` vs start): if ``+0x334 ≤ +0x2b0`` →
  ``code_end=start+1``, ``adj=0``; if ``code_28 ≤ code_end`` → both
  ``code_28/2c = code_end+1``; if ``code_2c ≤ start`` → ``code_2c =
  code_28``. Fill#2 mirrors with ``≥`` / ``start−1``. After fills:
  ``p18/p38`` → work ``+0x358/+0x360`` (↑) and ``+0x350/+0x348`` (↓).

  Dpi names on **ShastaParams** dump ``0x10128033`` (same early layout
  on the work object for these doubles):

  ==========  ==============================
  work off    dpi key (Params dump)
  ==========  ==============================
  ``+0x120``  ``shadowExpBlend``
  ``+0x128``  ``highlightExpBlend``
  ``+0x130``  ``shadowTransitionRatio``
  ``+0x138``  ``highlightTransitionRatio``
  ``+0x140``  ``shadowExpSatFactor``
  ``+0x148``  ``shadowCompSatFactor``
  ``+0x220``  ``highlightDeltaGain``
  ``+0x1d0``  ``blackNoiseStdDev``
  ``+0x1d8``  ``minBlackOffset``
  ``+0x1e0``  ``maxWhiteOffset``
  ==========  ==============================

  Prep ints ``+0x2c0…+0x338`` from buttons/aggr × ``+0x58`` (cite
  ``0x1027b1c0``). Image-derived ``+0x2f4/+0x300/+0x340/+0x370/+0x378``
  come from ``0x1027be10`` / ``0x102935d0`` (inject for golden; not
  dpi). Work ``+0x48/+0x60/+0x64`` are int clamp/size codes on the
  Generate object (not Params ``codeValuesPerButton`` @ Params``+0x48``).

* ``0x10293d50`` (~395 B): **ported + Unicorn-golden**
  (``black_noise_fill_93d50`` / ``SHASTA_BLACK_NOISE_93D50_PORTED``).
  Mid aims ``+0x2b4/+0x2b8`` feed this — **not** the ``0x10293960``
  fills. ``t = (+0x2b8−+0x2b4)/+0x1d0`` when ``+0x1d0>0`` else ``0``;
  ``index = ftol2(t+0.5)+(+0x2b4)``; ``sample =
  max(0, toneLut[index]−(+0x328)+arg)``; ``scale = t·(+0x1e0)``. If
  ``scale==0``: blackNoise ← 0 (DLL ``0x10246050``). Else for
  ``i∈[0,+0x64)``: weight ``1`` if ``i≤index`` else
  ``exp(−0.5·((i−index)/scale)²)``; store
  ``ftol2(weight·(+0x1d8)·sample+0.5)``. Builder then
  ``toneLut[i] += arg − blackNoise[i]`` and clamps to ``[+0x60,+0x64]``
  for ``i∈[0,+0x64]`` inclusive.

``ImaShastaOp`` apply
--------------------
* Type dispatch ``0x1014de50``: I16 → ``0x1014dcc0``, float →
  ``0x1014dd20``; other types throw (string ``0x1057c848`` I16-only).
* I16 loop @ ``0x1014dcf1``:
  ``out = (int16)(*(int16*)&toneLut[(uint16)in])`` — table is int32[],
  low word taken (``mov bx, word [table + code*4]``).
* Float loop @ ``0x1014dd60``: ``out = (float)toneLut[fist(in)]``.
* Table pointer from aggregate slot ``[+4]`` (vector begin). Host
  ``ima_shasta_op_apply`` matches I16 dispatch → ``SHASTA_APPLY_PORTED``.

Image sampling → ``935d0`` inputs (cited)
-----------------------------------------
* ``0x1027b970`` (sampled/blockAvg): hist percentile leaf ``0x104ea6c0``
  (``percent·0.01·sum`` → first bin with cum≥target → identity
  bin→code ``0x104f5710``). Generate work doubles ``+0x80/+0x88/+0x90/
  +0x98`` = dpi ``extShadow/shadow/highlight/extHighlight`` percents
  (Params dump those at ``+0x70…+0x88``; Generate slots differ).
  Writes ``+0x2e4…+0x2f0``; optional highlightDiff adjust from blockAvg
  ``+0x2e0`` via work ``+0xa0/+0xa8`` (dpi ``highlightDiffMult/Limit``);
  clamp lo to mid ``+0x2b4``, hi to white ``+0x2bc``.
* ``0x1027b3c0``: among pixels with **plane0** in
  ``[+0x2ec,+0x2f0]``, accumulate plane1/plane2 means → ``+0x310/+0x318``,
  ``+0x320=hypot``; ``+0x340`` white-pt ratio from work ``+0x208`` flag +
  ``+0x210/+0x218``·``+0x58`` (dpi ``bUseWhitePtCompression`` /
  ``whiteSatLower/Upper`` · ``codeValuesPerButton``).
* ``0x1027be10`` seed: ``+0x2f4…+0x300 ← +0x2e4…+0x2f0``;
  ``+0x308 = ((+0x2ec-+0x2e4-+0x2e8)+(+0x2f0))/2 / (+0x58·2.5)``.

DPI
---
* ``AnsShastaDpi::readAscii`` / ``ShastaDpiReader::scanOneLine``
  (``0x105a59e0`` / ``0x105a584c``). Loader below reads ASCII scalars.

Relationship to SRA forward LUT
-------------------------------
* Shipped ``common-sraFwdLut-metric-*.lut`` = ``AnsCommonSraFwdLutDPI``
  (``0x105954a0``) — **not** Shasta ``toneLut``. See ``pakon_sra.py``.
* Engine SRA apply remains an explicit **stand-in**.

UNKNOWN / blockers (honest)
---------------------------
* Mid-aim **upstream producers**: ScpLut remap + dens fill + bAddScene
  pack + AddScene desc pack + getCnContext ``path+0x3c`` bag load +
  Ane bin-index + dens-hist ``inc`` + neighbor merge ``0x102a82a0`` +
  finalize knot/adjust + curve rows + frame FindDmin ``+0x6cac`` +
  ColNeg 1px remap closed (Unicorn-golden). Host dens-hist→
  ``getResults`` compose wired. Still need Ane build orch
  ``0x1027e9d0`` (sample/residual → dens-hist). Contrast
  (``0x10119060``) / float-table (``0x1004f7b0``) side paths open.
  ``ANALYZE`` stays False.
* Cap ``+0x3e0`` automatic assign from analyze still UNKNOWN; host
  publishes via cited ``setToneLut`` ``0x101e48d0`` (``SHASTA_CAP_TONE_LUT_PORTED``).
* Iem hist fill ``0x104ea940`` from plane list not ported — host builds
  int32 counts from I16 plane0 (same plane ``0x1027b3c0`` keys on).
* ``SHASTA_TONE_LUT_PORTED=True`` (assemble golden). Image→codes via
  ``0x1027b970`` + ``0x1027b3c0`` + ``0x1027be10`` seed ported
  (``SHASTA_IMAGE_PERCENTILE_7B970_PORTED`` /
  ``SHASTA_IMAGE_SAMPLE_7B3C0_PORTED``). ``SHASTA_APPLY_PORTED=True``:
  I16 Op dispatch ``0x1014de50``→``0x1014dcc0`` + Preference assemble.
  ``ANALYZE`` stays False until live aim producers land.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

# Explicit markers — do not invent analyze → toneLut.
SHASTA_ANALYZE_PORTED = False
# Table assemble (935d0 + builder + Cap setToneLut) Unicorn-golden.
SHASTA_TONE_LUT_PORTED = True
# ImaShastaOp I16 type-dispatch + Preference assemble→apply wired.
SHASTA_APPLY_PORTED = True
# Fragments below are cited but insufficient for a scene toneLut.
SHASTA_TONE_LUT_FRAGMENTS = True
# avg2largest 0x1004f690 + dpi metricGray/white → +0x2b0/+0x2bc mapped.
SHASTA_AIM_AVG2_PORTED = True
# CnPremium mid-aim arithmetic (dens+setShifts+master clip+avg2) ported;
# live dmin/AneOrder knot *values* still WALL → ANALYZE stays False.
SHASTA_AIM_MID_RGB_PORTED = True
# find/insert/getNoiseTable provenance + bag/layout helpers ported.
SHASTA_AIM_INPUT_PATH_PORTED = True
# Unicorn-golden closed forms for 0x10292c50 / 0x10292cb0 (not full curve).
SHASTA_CURVE_LOG_RATIO_PORTED = True
# Unicorn-golden 0x10292d30 / 0x10292d80.
SHASTA_CURVE_EXP_PORTED = True
# Unicorn-golden 0x10293510 + 0x10293330 / 0x10293410.
SHASTA_CURVE_DISPATCH_PORTED = True
# Unicorn-golden 0x10293960 fill (injected aims/param). Full toneLut still open.
SHASTA_CURVE_FILL_PORTED = True
# Unicorn-golden 0x10293d50 blackNoise fill (injected mids/scales).
SHASTA_BLACK_NOISE_93D50_PORTED = True
# Unicorn-golden builder 0x10293ee0 (both fills + 93d50 + clamp; injected work).
SHASTA_TONE_LUT_BUILDER_PORTED = True
# Unicorn-golden 0x102935d0 (+ helpers 0x10292e00/1e0/170/230).
SHASTA_IMAGE_FIELDS_935D0_PORTED = True
# Cap setToneLut 0x101e48d0 int16→int32 @ +0x3e0 (sole Cap writer found).
SHASTA_CAP_TONE_LUT_PORTED = True
# Hist percentile leaf 0x104ea6c0 (+ identity bin→code 0x104f5710).
SHASTA_HIST_PERCENTILE_PORTED = True
# 0x1027b970 sampled-hist → +0x2e4…+0x2f0 (injected/host hist counts).
SHASTA_IMAGE_PERCENTILE_7B970_PORTED = True
# 0x1027b3c0 highlight-range means → +0x310/+0x318/+0x320/+0x340.
SHASTA_IMAGE_SAMPLE_7B3C0_PORTED = True

# ShastaParams early scalars (ctor 0x100543b0 / dump 0x101280a0)
SHASTA_PARAMS_METRIC_GRAY_OFF = 0x38
SHASTA_PARAMS_BLACK_OFF = 0x3C
SHASTA_PARAMS_WHITE_OFF = 0x40
SHASTA_PARAMS_BLACK_NOISE_SIGMA_MULT_OFF = 0x1C0  # dump 0x1012896a
# Ctor defaults before selectParams (erimm-shaped: black=600, white=2358)
SHASTA_PARAMS_CTOR_METRIC_GRAY = 0x60E  # 1550
SHASTA_PARAMS_CTOR_BLACK = 0x258  # 600
SHASTA_PARAMS_CTOR_WHITE = 0x936  # 2358
SHASTA_PARAMS_CTOR_BLACK_NOISE_SIGMA_MULT = 2.0  # 0x10574f48

# Global AnsLut @ 0x106b5f74 (CRT 0x1056a470 → ctor 0x100f42a0(0xc,0,0xfff))
MASTER_LUT_OBJ = 0x106B5F74
MASTER_LUT_DATA_PTR = 0x106B5F7C  # obj+8 = alloc+0x10000 (signed index 0)
MASTER_LUT_MAX = 0xFFF  # 4095 — identity high clamp
SCENE_SETSHIFTS_OUT_OFF = 0x4B6  # +0x4b8/+0x4ba siblings (int16)

# CapabilityImpl getToneLut / setToneLut (int32 toneLut)
CAP_TONE_LUT_VEC_OFF = 0x3E0  # begin; end +0x3e4; int32 stride
TONE_LUT_EXPORT_ELEM = "int16"

# Working Generate/Shasta object (builder 0x10293ee0 / dump 0x10245f57)
WORK_TONE_LUT_VEC_OFF = 0x3B0
WORK_BLACK_NOISE_LUT_OFF = 0x3C0
WORK_SLOPE_LUT_OFF = 0x3E0  # Generate object only — NOT Cap toneLut
WORK_CODE_OFF = 0x2B0  # seed index; +0x2b4/+0x2b8/+0x2bc siblings

# .rdata
F64_0 = 0.0  # 0x10573c40
F64_1 = 1.0  # 0x10574f50
F64_2 = 2.0  # 0x10574f48 — blackNoiseSigmaMult ctor default
F64_HALF = 0.5  # 0x10574f40
F64_NEG_1 = -1.0  # 0x10574f58 — exp leaves / Newton
F64_0_95 = 0.95  # 0x105800a8 — curve helper 0x10293960
F64_0_75 = 0.75  # 0x1057a3e8 — curve helper 0x10293960
F64_0_1 = 0.1  # 0x105a77a0 — dispatcher 0x10293510
F64_1_1 = 1.1  # 0x10579a80 — Newton seed factor 0x10293330/410
F64_2_5 = 2.5  # 0x105a5a20 — 0x1027be10 side field
F64_0_999 = 0.999  # 0x105a3c08 — log-ratio clamps in 0x10292c50/cb0
F64_NEG_HALF = -0.5  # 0x1057ae70 — blackNoise gauss 0x10293d50
F64_CLAMP_POS = 2000.0  # 0x105a77b0
F64_CLAMP_NEG = -2000.0  # 0x105a77a8
CURVE_LOG_RATIO_ITERS = 100  # edx seed in dispatcher 0x10293510
CURVE_NEWTON_ITERS = 100  # edx at 0x10293514

# ShastaParams dump 0x10128033 — blend / blackNoise scalars used by builder
WORK_SHADOW_EXP_BLEND_OFF = 0x120
WORK_HIGHLIGHT_EXP_BLEND_OFF = 0x128
WORK_SHADOW_TRANSITION_RATIO_OFF = 0x130
WORK_HIGHLIGHT_TRANSITION_RATIO_OFF = 0x138
WORK_SHADOW_EXP_SAT_FACTOR_OFF = 0x140
WORK_SHADOW_COMP_SAT_FACTOR_OFF = 0x148
WORK_HIGHLIGHT_DELTA_GAIN_OFF = 0x220
WORK_BLACK_NOISE_STD_DEV_OFF = 0x1D0
WORK_MIN_BLACK_OFFSET_OFF = 0x1D8
WORK_MAX_WHITE_OFFSET_OFF = 0x1E0
# 0x102935d0 / helpers — Params dump names (0x10128033)
WORK_HIGHLIGHT_EXP_SCALE_OFF = 0x100  # clamped [0,1] in 0x10292e00
WORK_SHADOW_MAX_EXP_SLOPE_OFF = 0x108
WORK_HIGHLIGHT_MAX_EXP_SLOPE_OFF = 0x110  # min-clamped to 1.0 in 92e00
WORK_SHADOW_COMP_BLEND_OFF = 0x118  # min-clamped to 1.0 in 92e00
WORK_MAX_EXP_DELTA_OFF = 0x1E8  # 0x102931e0
WORK_MAX_COMP_DELTA_OFF = 0x1F0  # 0x10293170
WORK_ADJ_CLAMP_LO_SRC_OFF = 0x1F8  # qword load in 0x10293230 (overlaps bool in Params)
WORK_ADJ_CLAMP_HI_SRC_OFF = 0x200  # whiteSatLowerLimit dump; 93230 hi
WORK_ADJ_SCALE_370_OFF = 0x228  # post-935d0 multiply in 0x1027be10
WORK_ADJ_SCALE_378_OFF = 0x230


def parse_dpi_scalars(path: Path) -> dict[str, str]:
    """ASCII ``key = value`` lines (``AnsShastaDpi`` / generic dpi surface)."""
    out: dict[str, str] = {}
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _num(d: dict[str, str], key: str, default: float) -> float:
    if key not in d:
        return default
    s = d[key].strip()
    if s.lower() in ("true", "false"):
        return 1.0 if s.lower() == "true" else 0.0
    return float(s)


def _bool(d: dict[str, str], key: str, default: bool) -> bool:
    if key not in d:
        return default
    return d[key].strip().lower() in ("true", "1", "yes")


def clamp01(x: float) -> float:
    """``0x10293ee0`` style clamp to ``[0.0, 1.0]`` (consts cited)."""
    if x < F64_0:
        return F64_0
    if x > F64_1:
        return F64_1
    return x


def curve_log_ratio_c50(a: float, b: float) -> float:
    """``0x10292c50`` closed form (Unicorn-golden vs PakonIMAu.dll).

    ``-b·log(1 − a/b)`` with two-sided clamp vs ``0.999·b`` (cite
    ``0x10292c50…ca7``): ``a ≥ 0`` and ``0.999·b < a`` → ``+2000``;
    ``a < 0`` and ``0.999·b > a`` → ``−2000``. Used by fill
    ``0x10293960`` — not a toneLut by itself.
    """
    thresh = F64_0_999 * b
    if a >= F64_0:
        if thresh < a:
            return F64_CLAMP_POS
    elif thresh > a:
        return F64_CLAMP_NEG
    return -b * math.log(1.0 - a / b)


def curve_log_ratio_cb0(a: float, b: float) -> float:
    """``0x10292cb0`` closed form (Unicorn-golden vs PakonIMAu.dll).

    ``t = b·exp(a/b)``; then ``-b·log(1 − a/t)`` with the same two-sided
    clamp vs ``0.999·t`` as ``c50`` (cite ``0x10292cb0…d2b``). Fill
    selects ``cb0`` when param adj ``< 0`` (``0x10293a3e``).
    """
    t = b * math.exp(a / b)
    thresh = F64_0_999 * t
    if a >= F64_0:
        if thresh < a:
            return F64_CLAMP_POS
    elif thresh > a:
        return F64_CLAMP_NEG
    return -b * math.log(1.0 - a / t)


def curve_exp_d30(a: float, b: float, c: float) -> float:
    """``0x10292d30`` closed form (Unicorn-golden).

    ``c · exp(b/c) · (1 − exp(−a/c))``. Uses ``−1.0`` @ ``0x10574f58``
    in the DLL exp path.
    """
    return c * math.exp(b / c) * (1.0 - math.exp(-a / c))


def curve_exp_d80(a: float, b: float, c: float, d: float) -> float:
    """``0x10292d80`` (Unicorn-golden).

    If ``c ≥ 0``: ``d30(a,c,d)`` when ``b < c``, else ``d·(1−exp(−a/d))``.
    If ``c < 0``: inequality flips (``b > c`` → ``d30``) — MSVC
    ``test ah,0x41; jp`` on the ``b`` vs ``c`` compare.
    """
    use_d30 = (b < c) if c >= F64_0 else (b > c)
    if use_d30:
        return curve_exp_d30(a, c, d)
    return d * (1.0 - math.exp(-a / d))


def curve_newton_330(
    a: float,
    target: float,
    tol: float = F64_0_1,
    n: int = CURVE_NEWTON_ITERS,
) -> float:
    """``0x10293330`` iterative leaf (Unicorn-golden).

    Starts ``S = target``, factor ``x = 1.1``. Residual
    ``r = target − S·(1 − exp(−a/S))``. On ``r > 0`` multiply ``S`` by
    ``x``; else divide. Damp ``x ← (x+1)/2`` when
    ``err_prev < −tol`` (``r ≥ 0``) or ``err_prev > tol`` (``r < 0``;
    cite ``0x102933b8…c2`` — not ``<=``).
    """
    if n <= 0:
        return target
    x = F64_1_1
    err_prev = F64_0
    s = float(target)
    for _ in range(n):
        r = target - s * (1.0 - math.exp(-a / s))
        if r >= F64_0:
            if r <= tol:
                return s
            if err_prev < -tol:
                x = (x + F64_1) * F64_HALF
        else:
            if -r <= tol:
                return s
            if err_prev > tol:
                x = (x + F64_1) * F64_HALF
        s = s * x if r > F64_0 else s / x
        err_prev = r
    return s


def curve_newton_410(
    a: float,
    b: float,
    target: float,
    tol: float = F64_0_1,
    n: int = CURVE_NEWTON_ITERS,
) -> float:
    """``0x10293410`` iterative leaf (Unicorn-golden on dispatcher paths).

    Starts ``S = a``. Residual uses ``curve_exp_d30``:
    ``d30(b,a,S)`` when ``b ≥ 0``, else ``d30(a,b,S)`` (negative-``b``
    domain matches DLL; asm field order is ``d30(b,a,S)`` for ``b ≥ 0``).
    Shrink ``S`` on ``r > 0``. If ``a < 0``, recurse on ``(−a, b, target)``
    and negate (matches ``fchs`` wrappers from ``0x10293510``).
    """
    if a < F64_0:
        return -curve_newton_410(-a, b, target, tol, n)
    if n <= 0:
        return a
    x = F64_1_1
    err_prev = F64_0
    s = float(a)
    for _ in range(n):
        try:
            fx = (
                curve_exp_d30(b, a, s)
                if b >= F64_0
                else curve_exp_d30(a, b, s)
            )
        except OverflowError:
            return s
        r = target - fx
        if not math.isfinite(r):
            return s
        if r >= F64_0:
            if r <= tol:
                return s
            if err_prev < -tol:
                x = (x + F64_1) * F64_HALF
        else:
            if -r <= tol:
                return s
            if err_prev > tol:
                x = (x + F64_1) * F64_HALF
        s = s / x if r > F64_0 else s * x
        err_prev = r
    return s


def curve_dispatch_93510(
    a: float,
    b: float,
    c: float,
    tol: float = F64_0_1,
    n: int = CURVE_NEWTON_ITERS,
) -> float:
    """``0x10293510`` dispatcher (Unicorn-golden).

    ``c ≥ 0``: ``b < c`` → ``curve_newton_410(a,b,c)``; else
    ``curve_newton_330(b,c)``.
    ``c < 0``: ``b > c`` → ``−410(−a,−b,−c)``; else ``−330(−b,−c)``
    (``test ah,0x41; jp`` ⇒ greater → 410 path).
    """
    if c >= F64_0:
        if b < c:
            return curve_newton_410(a, b, c, tol, n)
        return curve_newton_330(b, c, tol, n)
    if b > c:
        return -curve_newton_410(-a, -b, -c, tol, n)
    return -curve_newton_330(-b, -c, tol, n)


def fist_round(x: float) -> int:
    """Approx MSVC ``fistp`` via ``0x104ffe44`` (nearest)."""
    return int(round(x))


def prep_breakpoint_pair(
    stops: float,
    aggr: float,
    code_values_per_button: float,
    ref_code: int,
    base_code: int,
) -> tuple[int, int]:
    """One channel of ``0x1027b1c0``:

    ``a = fist(stops * aggr * codeValuesPerButton + 0.5)``;
    ``b = ref_code - a`` (or ``base_code - a`` depending on site).

    Callers must pass the exact field roles; full field←dpi map UNKNOWN.
    """
    a = fist_round(stops * aggr * code_values_per_button + F64_HALF)
    return a, ref_code - a


def _sx16(x: int) -> int:
    x = int(x) & 0xFFFF
    return x - 0x10000 if x >= 0x8000 else x


def _sar_div2(x: int) -> int:
    """MSVC ``cdq; sub eax, edx; sar eax, 1`` on a signed 32-bit value."""
    x = int(x)
    if x < -0x80000000 or x > 0x7FFFFFFF:
        x = ((x + 0x80000000) & 0xFFFFFFFF) - 0x80000000
    edx = -1 if x < 0 else 0
    return (x - edx) >> 1


def avg2largest_i16(a: int, b: int, c: int) -> int:
    """``0x1004f690`` — average of the two largest of three int16 codes.

    ``(a + b + c − min(a,b,c)) / 2`` with MSVC signed ``sar`` rounding.
    Used by ``CnPremium_analyzeSceneSpecific`` on the dmin RGB triple and
    the dmin+dens triple before pushing triage ``[ebp+0x10/+0x14]``.
    """
    a16, b16, c16 = _sx16(a), _sx16(b), _sx16(c)
    return _sar_div2(a16 + b16 + c16 - min(a16, b16, c16))


def ftol2_chop(x: float) -> int:
    """``0x104ffe44`` — trunc toward zero (dens scale path @ ``0x100569c9``)."""
    return int(math.trunc(x))


def master_lut_clip_i16(code: int, lo: int = 0, hi: int = MASTER_LUT_MAX) -> int:
    """Global master LUT lookup (``[0x106b5f7c]``, ctor ``0x100f42a0``).

    Signed-int16 index into identity/clip table: ``<lo → lo``,
    ``lo…hi → identity``, ``>hi → hi``. Static init uses ``lo=0``,
    ``hi=0xfff``.
    """
    c = int(code)
    if c < lo:
        return int(lo)
    if c > hi:
        return int(hi)
    return c


def _i16_add(a: int, b: int) -> int:
    """16-bit wrapping add (``add ax, …``)."""
    return _sx16((int(a) + int(b)) & 0xFFFF)


def ane_dens_contrib(
    dmin_rgb: tuple[int, int, int] | list[int],
    dens_table: np.ndarray,
    scale: float,
    n_channels: int = 1,
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """AneOrder dens add @ ``0x100569a1…`` (before setShifts / master LUT).

    ``dens_table`` is ``(n,)`` when ``n_channels==1`` (shared), or
    ``(n_channels, n)`` when per-channel tables advance (``+0x48``).
    Returns ``(dens_i int32×3, dmin_dens int16×3)``.
    """
    tbl = np.asarray(dens_table, dtype=np.float32)
    if tbl.ndim == 1:
        planes = [tbl, tbl, tbl]
        n = int(tbl.shape[0])
    elif tbl.ndim == 2:
        if tbl.shape[0] < 3:
            raise ValueError("per-channel dens_table needs ≥3 planes")
        planes = [tbl[0], tbl[1], tbl[2]]
        n = int(tbl.shape[1])
    else:
        raise ValueError("dens_table must be 1-D or 2-D")
    if n <= 0:
        raise ValueError("dens_table length is 0")
    dens_i: list[int] = []
    dmin_dens: list[int] = []
    for i in range(3):
        code = _sx16(dmin_rgb[i])
        idx = 0 if code < 0 else (n - 1 if code > n - 1 else code)
        plane = planes[i if n_channels > 1 else 0]
        di = ftol2_chop(float(plane[idx]) * float(scale))
        dens_i.append(di)
        dmin_dens.append(_i16_add(code, di))
    return (dens_i[0], dens_i[1], dens_i[2]), (
        dmin_dens[0],
        dmin_dens[1],
        dmin_dens[2],
    )


def cn_premium_mid_aim_rgb(
    dmin_rgb: tuple[int, int, int] | list[int],
    dens_table: np.ndarray,
    setshifts_out: tuple[int, int, int] | list[int],
    *,
    black: int = SHASTA_PARAMS_CTOR_BLACK,
    metric_gray: int = SHASTA_PARAMS_CTOR_METRIC_GRAY,
    black_noise_sigma_mult: float = SHASTA_PARAMS_CTOR_BLACK_NOISE_SIGMA_MULT,
    dens_n_channels: int = 1,
    master_lo: int = 0,
    master_hi: int = MASTER_LUT_MAX,
) -> tuple[int, int]:
    """Core CnPremium mid aims → triage ``+0x2b4/+0x2b8`` (no contrast/float).

    Cite: ``0x100569a1…0x100570b3``. Caller supplies dmin RGB (from
    ``SceneContextBag.find_dmin`` / writers) and dens floats (from
    ``NoiseTable`` after ``getResults`` fill — analyze knots still WALL).
    """
    dens_i, dmin_dens = ane_dens_contrib(
        dmin_rgb, dens_table, black_noise_sigma_mult, dens_n_channels
    )
    shifts = (_sx16(setshifts_out[0]), _sx16(setshifts_out[1]), _sx16(setshifts_out[2]))
    dmin = (_sx16(dmin_rgb[0]), _sx16(dmin_rgb[1]), _sx16(dmin_rgb[2]))

    remapped_dmin = [
        master_lut_clip_i16(_i16_add(dmin[c], shifts[c]), master_lo, master_hi)
        for c in range(3)
    ]
    remapped_dens = [
        master_lut_clip_i16(_i16_add(dmin_dens[c], shifts[c]), master_lo, master_hi)
        for c in range(3)
    ]

    thr = int(metric_gray)
    if any(remapped_dmin[c] > thr for c in range(3)):
        b = int(black)
        remapped_dmin = [
            master_lut_clip_i16(b + shifts[c], master_lo, master_hi) for c in range(3)
        ]
        remapped_dens = [
            master_lut_clip_i16(b + dens_i[c] + shifts[c], master_lo, master_hi)
            for c in range(3)
        ]

    return (
        avg2largest_i16(remapped_dmin[0], remapped_dmin[1], remapped_dmin[2]),
        avg2largest_i16(remapped_dens[0], remapped_dens[1], remapped_dens[2]),
    )


def cn_premium_mid_aim_from_bag(
    bag: Any,
    noise_table: Any,
    setshifts_out: tuple[int, int, int] | list[int],
    **kwargs: Any,
) -> tuple[int, int] | None:
    """Compose bag dmin + ``NoiseTable`` → ``cn_premium_mid_aim_rgb``.

    Returns ``None`` if ``dmin`` is missing (matches CnPremium abort when
    ``find`` fails). ``noise_table`` must expose ``n_channels`` and
    ``planes_for_mid_aim()`` (see ``pakon_ane_order.NoiseTable``).
    """
    dmin = bag.find_dmin()
    if dmin is None:
        return None
    planes = noise_table.planes_for_mid_aim()
    return cn_premium_mid_aim_rgb(
        dmin,
        planes,
        setshifts_out,
        dens_n_channels=int(noise_table.n_channels),
        **kwargs,
    )


def store_aim_codes(
    code_2b0: int,
    code_2b4: int,
    code_2b8: int,
    code_2bc: int,
) -> tuple[int, int, int, int]:
    """``0x1027be10`` store of analyze args → ``+0x2b0…+0x2bc``.

    Provenance (see module doc): ``metricGray``, ``avg2largest(dmin RGB)``,
    ``avg2largest(dmin+dens)``, ``white``. Mid codes: use
    ``cn_premium_mid_aim_rgb`` when dmin + AneOrder dens are known.
    """
    return int(code_2b0), int(code_2b4), int(code_2b8), int(code_2bc)


def aim_codes_from_dpi_ends(
    dpi: "ShastaDpi",
    avg_dmin_rgb: int,
    avg_dmin_dens_rgb: int,
) -> tuple[int, int, int, int]:
    """Aim tuple: dpi ``metricGray``/``white`` + mid avgs from caller.

    Matches store map ``+0x2b0/+0x2bc`` ← ShastaParams (selectParams/dpi)
    and ``+0x2b4/+0x2b8`` ← ``avg2largest`` results (e.g. from
    ``cn_premium_mid_aim_rgb``).
    """
    return store_aim_codes(
        int(round(dpi.metric_gray)),
        int(avg_dmin_rgb),
        int(avg_dmin_dens_rgb),
        int(round(dpi.white)),
    )


def tone_lut_seed_identity(lut: np.ndarray, code: int) -> None:
    """``0x102940d9``: ``toneLut[code] = code`` (int32 vector).

    Builder seeds before ``0x10293960``; fill overwrites ``start±1…end``.
    """
    if lut.dtype != np.int32:
        raise TypeError("toneLut fragment expects int32")
    if not (0 <= code < len(lut)):
        raise ValueError(f"code {code} out of range for lut len {len(lut)}")
    lut[code] = np.int32(code)


@dataclass
class ToneLutFillParam:
    """Param blob for ``0x10293960`` (builder ``0x10293ee0`` stack object).

    Offsets match the DLL ``this``/``eax`` struct. Work-object sources are
    documented on the type; dpi←field for ``+0x128/+0x148/+0x300…`` is only
    partially mapped — inject cited or synthetic values for golden fills.
    """

    code_end: int  # +0 ← work +0x334
    adj: int  # +4 ← ftol2(work +0x378)
    u0: float  # +0x10 ← work +0x128 or +0x138
    p20: float  # +0x20 ← work +0x148
    code_28: int  # +0x28 ← work +0x338
    code_2c: int  # +0x2c ← work +0x300
    p30: float  # +0x30 ← work +0x340
    p18: float = 0.0  # +0x18 written by fill
    p38: float = 0.0  # +0x38 written by fill


def _fill_sub0(d2c: float, p20: float, span: int) -> float:
    """``0x10293a77…abc``: ``(1−p20)·d2c``, or ``d2c∓1`` at the boundary."""
    raw = (F64_1 - float(p20)) * float(d2c)
    if span >= 0:
        return raw if raw < d2c else d2c - F64_1
    return raw if raw > d2c else d2c + F64_1


def tone_lut_fill_93960(
    lut: np.ndarray,
    start: int,
    end: int,
    param: ToneLutFillParam,
) -> ToneLutFillParam:
    """``0x10293960`` toneLut curve fill (Unicorn-golden vs PakonIMAu.dll).

    Writes ``lut[start±1 … end]`` (inclusive end). Seeds ``lut[start]``
    separately via ``tone_lut_seed_identity`` (builder ``0x102940d9``).
    Returns ``param`` with ``p18`` / ``p38`` filled.

    ``start`` is work ``+0x2b0`` (metricGray aim) on the first builder call.
    Does **not** run ``0x10293d50`` or Cap export — see ``assemble_tone_lut``.
    """
    if lut.dtype != np.int32:
        raise TypeError("toneLut fill expects int32")
    span = int(param.code_end) - int(start)
    d2c = float(int(param.code_2c) - int(start))
    d28 = float(int(param.code_28) - int(start))
    adj = int(param.adj)
    lim = ftol2_chop(float(span) * F64_0_95)
    if span >= 0:
        if adj > lim:
            adj = lim
        span_adj = span - adj
    else:
        lim = -lim
        if adj > lim:
            adj = lim
        span_adj = adj + span
    span_f = float(span)
    s1 = curve_dispatch_93510(span_f, span_f, float(span_adj))
    s2 = curve_dispatch_93510(d28, d2c, d28)
    # Log-ratio leaf keyed on adj sign (DLL ``test eax,eax`` at
    # ``0x10293a3e`` loads param ``+4``), not on span sign.
    lr = (
        curve_log_ratio_c50(span_f, s1)
        if adj >= 0
        else curve_log_ratio_cb0(span_f, s1)
    )
    d75 = d2c * F64_0_75
    sub0 = _fill_sub0(d2c, param.p20, span)
    denom = d2c - sub0
    r1 = curve_exp_d80(d75, lr, span_f, s1)
    p18 = r1 / d75
    r2 = curve_exp_d80(d2c, d2c, d28, s2)
    r3 = curve_exp_d80(sub0, lr, span_f, s1)
    p38 = (r2 - r3) / denom if denom != 0.0 else F64_0
    param.p18 = p18
    param.p38 = p38

    if end >= start:
        i, i_end, step = start + 1, end + 1, 1
    else:
        i, i_end, step = start - 1, end - 1, -1
    u0 = float(param.u0)
    p30 = float(param.p30)
    while i != i_end:
        if not (0 <= i < len(lut)):
            i += step
            continue
        offset = float(i - start)
        u = (offset - sub0) / denom if denom != 0.0 else F64_0
        u = clamp01(u)
        alpha = u * p30
        lo = float(start) + offset * p18
        hi = curve_exp_d80(offset, lr, span_f, s1) + float(start)
        if alpha < F64_1:
            if u0 == F64_0:
                base = hi
            elif u0 < F64_1:
                base = (F64_1 - u0) * hi + u0 * lo
            else:
                base = lo
            if alpha > F64_0:
                up = curve_exp_d80(offset, d2c, d28, s2) + float(start)
                out = alpha * up + (F64_1 - alpha) * base
            else:
                out = base
        else:
            out = curve_exp_d80(offset, d2c, d28, s2) + float(start)
        lut[i] = np.int32(ftol2_chop(out + F64_HALF))
        i += step
    return param


def curve_index_from_span(
    code_lo: int,
    code_hi: int,
    scale_1d0: float,
) -> int:
    """Index fragment of ``0x10293d50`` when ``+0x1d0 > 0``:

    ``ftol2((code_hi - code_lo) / scale_1d0 + 0.5) + code_lo``.
    """
    if scale_1d0 == 0.0:
        raise ValueError("scale_1d0 is 0")
    return ftol2_chop((code_hi - code_lo) / scale_1d0 + F64_HALF) + code_lo


def tone_lut_adjust_sample(
    tone_lut: np.ndarray,
    index: int,
    off_328: int,
    arg_ebp8: int,
) -> int:
    """Sample fragment of ``0x10293d50``:
    ``toneLut[index] - (+0x328) + [ebp+8]`` (pre-clamp).
    """
    if tone_lut.dtype != np.int32:
        raise TypeError("toneLut fragment expects int32")
    return int(tone_lut[index]) - int(off_328) + int(arg_ebp8)


@dataclass
class BlackNoise93d50In:
    """Work fields for ``0x10293d50`` (dpi names from Params dump)."""

    mid_lo: int  # +0x2b4
    mid_hi: int  # +0x2b8
    black_noise_std_dev: float  # +0x1d0
    min_black_offset: float  # +0x1d8
    max_white_offset: float  # +0x1e0
    off_328: int  # +0x328 (prep)
    code_max: int  # +0x64 — loop runs i∈[0, code_max)
    arg: int  # builder [ebp+8] = generate (+0x48−+0x2b0)


def black_noise_fill_93d50(
    black_noise: np.ndarray,
    tone_lut: np.ndarray,
    inp: BlackNoise93d50In,
) -> int:
    """``0x10293d50`` blackNoiseLut fill (Unicorn-golden vs PakonIMAu.dll).

    Writes ``black_noise[0 … code_max)``. Returns the sample index.
    When ``scale == 0``, fills zeros (DLL ``0x10246050`` resize/fill path).
    """
    if black_noise.dtype != np.int32 or tone_lut.dtype != np.int32:
        raise TypeError("blackNoise/toneLut expect int32")
    if inp.black_noise_std_dev > F64_0:
        t = (int(inp.mid_hi) - int(inp.mid_lo)) / float(inp.black_noise_std_dev)
    else:
        t = F64_0
    index = ftol2_chop(t + F64_HALF) + int(inp.mid_lo)
    if not (0 <= index < len(tone_lut)):
        raise IndexError(f"93d50 index {index} out of toneLut range")
    sample = float(tone_lut_adjust_sample(tone_lut, index, inp.off_328, inp.arg))
    if sample < F64_0:
        sample = F64_0
    scale = t * float(inp.max_white_offset)
    n = int(inp.code_max)
    if n < 0:
        n = 0
    if scale == F64_0:
        black_noise[:n] = 0
        if n < len(black_noise):
            # leave the rest untouched (DLL only touches sized range)
            pass
        return index
    for i in range(n):
        if i <= index:
            w = F64_1
        else:
            u = (float(i) - float(index)) / scale
            w = math.exp(F64_NEG_HALF * u * u)
        black_noise[i] = np.int32(
            ftol2_chop(w * float(inp.min_black_offset) * sample + F64_HALF)
        )
    return index


@dataclass
class ToneLutBuilderWork:
    """Injected Generate/work snapshot for ``0x102935d0`` + ``0x10293ee0``.

    Image codes ``+0x2f4…+0x300`` come from ``0x1027be10`` after
    ``0x1027b970`` (percents) + ``0x1027b3c0`` (``+0x340``). Prefer
    ``seed_image_fields_from_analysis`` over inject when a plane hist /
    analysis image is available.
    """

    code_start: int  # +0x2b0
    code_min: int  # +0x60 clamp lo
    code_max: int  # +0x64 clamp hi / fill#1 end
    code_48: int  # +0x48 — generate arg = code_48 − code_start
    # prep outputs (or run prep_breakpoint_pair yourself)
    off_328: int = 0
    code_32c: int = 0  # +0x32c
    code_330: int = 0  # +0x330
    code_334: int = 0  # +0x334
    code_338: int = 0  # +0x338
    # image-derived (0x1027be10 store / 0x102935d0 adjust)
    code_2f4: int = 0  # +0x2f4
    code_2f8: int = 0  # +0x2f8
    code_2fc: int = 0  # +0x2fc
    code_300: int = 0  # +0x300
    p340: float = 1.0  # +0x340 (from 0x1027b3c0; inject)
    adj_368: float = 0.0  # +0x368
    adj_370: float = 0.0  # +0x370
    adj_378: float = 0.0  # +0x378
    adj_380: float = 0.0  # +0x380
    # 935d0 helper scalars (Params dump)
    code_values_per_button: float = 75.0  # +0x58 role on work object
    highlight_exp_scale: float = 0.5  # +0x100
    shadow_max_exp_slope: float = 0.5  # +0x108
    highlight_max_exp_slope: float = 0.5  # +0x110
    shadow_comp_blend: float = 0.5  # +0x118
    max_exp_delta: float = 2.0  # +0x1e8
    max_comp_delta: float = 2.0  # +0x1f0
    adj_clamp_lo_src: float = 50.0  # +0x1f8 qword in 93230
    adj_clamp_hi_src: float = 100.0  # +0x200
    adj_scale_370: float = 1.0  # +0x228 post-935d0 in 0x1027be10
    adj_scale_378: float = 1.0  # +0x230
    # dpi blend scalars (Params dump names)
    shadow_exp_blend: float = 0.5  # +0x120
    highlight_exp_blend: float = 0.5  # +0x128
    shadow_transition_ratio: float = 0.5  # +0x130
    highlight_transition_ratio: float = 0.5  # +0x138
    shadow_exp_sat_factor: float = 0.25  # +0x140
    shadow_comp_sat_factor: float = 0.25  # +0x148
    highlight_delta_gain: float = 1.0  # +0x220
    # blackNoise scales
    mid_lo: int = 0  # +0x2b4
    mid_hi: int = 0  # +0x2b8
    code_white: int = 0  # +0x2bc (93170 guard)
    black_noise_std_dev: float = 2.0  # +0x1d0
    min_black_offset: float = 10.0  # +0x1d8
    max_white_offset: float = 1.0  # +0x1e0
    # written by builder (optional readback)
    p18_hi: float = 0.0  # +0x358
    p38_hi: float = 0.0  # +0x360
    p18_lo: float = 0.0  # +0x350
    p38_lo: float = 0.0  # +0x348


def slope_adjust_92e00(work: ToneLutBuilderWork) -> ToneLutBuilderWork:
    """``0x10292e00`` — clamp slope dpi scalars and reseat ``+0x2f4…+0x300``.

    Unicorn-golden vs PakonIMAu.dll. Called from ``0x102935d0``.
    """
    s100 = float(work.highlight_exp_scale)
    s108 = float(work.shadow_max_exp_slope)
    s110 = float(work.highlight_max_exp_slope)
    s118 = float(work.shadow_comp_blend)
    # min-clamp +0x110/+0x118 to 1.0; clamp +0x100/+0x108 to [0,1]
    if s118 < F64_1:
        s118 = F64_1
    if s110 < F64_1:
        s110 = F64_1
    s100 = clamp01(s100)
    s108 = clamp01(s108)
    work.highlight_exp_scale = s100
    work.shadow_max_exp_slope = s108
    work.highlight_max_exp_slope = s110
    work.shadow_comp_blend = s118

    start = int(work.code_start)
    d32c = int(work.code_32c) - start
    d2f4 = int(work.code_2f4) - start
    d330 = int(work.code_330) - start
    d2f8 = int(work.code_2f8) - start
    d334 = int(work.code_334) - start
    d2fc = int(work.code_2fc) - start
    d338 = int(work.code_338) - start
    d300 = int(work.code_300) - start
    orig_gap = d300 - d2fc

    if d2f8 > d330:
        a = ftol2_chop((F64_1 - s100) * (d2f8 - d330) + F64_HALF)
        b = ftol2_chop((d2f4 - d32c) * (F64_1 - s100) + F64_HALF)
        d2f8 -= a
        d2f4 -= b
        slope350 = d330 / float(d2f8) if d2f8 else F64_0
        if slope350 > s110:
            d2f8 = ftol2_chop(d330 / s110 + F64_HALF)
        work.code_2f4 = d2f4 + start
        work.code_2f8 = d2f8 + start

    if d2fc < d334:
        a = ftol2_chop((d334 - d2fc) * (F64_1 - s108) + F64_HALF)
        d2fc += a
        slope358 = d334 / float(d2fc) if d2fc else F64_0
        if slope358 > s118:
            d2fc = ftol2_chop(d334 / s118 + F64_HALF)

    if d300 < d338:
        a = ftol2_chop(F64_HALF * (F64_1 - s108) * (d338 - d300) + F64_HALF)
        d300 += a
        slope360 = d338 / float(d300) if d300 else F64_0
        if slope360 > s118:
            d300 = ftol2_chop(d338 / s118 + F64_HALF)

    min_300 = orig_gap + d2fc
    if d300 < min_300:
        d300 = min_300
    work.code_2fc = d2fc + start
    work.code_300 = d300 + start
    return work


def _guard_mid_lo_931e0(work: ToneLutBuilderWork) -> None:
    """``0x102931e0`` — floor ``+0x2f8/+0x2f4`` from mid_lo + maxExpDelta."""
    thr = (
        ftol2_chop(
            float(work.max_exp_delta)
            * float(work.code_values_per_button)
            * F64_2_5
            + F64_HALF
        )
        + int(work.mid_lo)
    )
    if int(work.code_2f8) < thr:
        work.code_2f8 = thr
        work.code_2f4 = int(work.mid_lo)
    if int(work.code_2f4) < int(work.mid_lo):
        work.code_2f4 = int(work.mid_lo)


def _guard_white_93170(work: ToneLutBuilderWork) -> None:
    """``0x10293170`` — cap ``+0x300/+0x2fc`` vs white + maxCompDelta."""
    white = int(work.code_white)
    if white <= 0:
        return
    span = ftol2_chop(
        float(work.max_comp_delta)
        * float(work.code_values_per_button)
        * F64_2_5
        + F64_HALF
    )
    if int(work.code_300) > white:
        work.code_300 = white
    if int(work.code_300) > int(work.code_2fc) + span:
        work.code_300 = int(work.code_2fc) + span
    if int(work.code_2fc) >= int(work.code_300):
        work.code_2fc = int(work.code_300) - 1


def _clamp_adjs_93230(work: ToneLutBuilderWork) -> None:
    """``0x10293230`` — clamp ``+0x368…+0x380`` to ``[lo,hi]`` code deltas."""
    scale = float(work.code_values_per_button)
    hi = float(ftol2_chop(float(work.adj_clamp_hi_src) * scale))
    lo = float(ftol2_chop(-(float(work.adj_clamp_lo_src) * scale)))

    def _c(v: float) -> float:
        if v < lo:
            return lo
        if v > hi:
            return hi
        return v

    work.adj_368 = _c(float(work.adj_368))
    work.adj_370 = _c(float(work.adj_370))
    work.adj_378 = _c(float(work.adj_378))
    work.adj_380 = _c(float(work.adj_380))


def image_derived_fields_935d0(work: ToneLutBuilderWork) -> ToneLutBuilderWork:
    """``0x102935d0`` image-derived builder fields (Unicorn-golden).

    Reseats ``+0x2f4…+0x300`` when ill-ordered, runs ``0x10292e00`` /
    ``0x102931e0`` / ``0x10293170``, writes adj doubles ``+0x368…+0x380``
    via dispatch ``0x10293510`` + exp ``0x10292d80``, then ``0x10293230``
    clamp. Caller ``0x1027be10`` then multiplies ``+0x370/+0x378`` by
    ``+0x228/+0x230`` — use ``scale_adjs_after_935d0``.
    """
    c2f4 = int(work.code_2f4)
    c2f8 = int(work.code_2f8)
    c2fc = int(work.code_2fc)
    c300 = int(work.code_300)
    start = int(work.code_start)
    work.adj_368 = F64_0
    work.adj_370 = F64_0
    work.adj_378 = F64_0
    work.adj_380 = F64_0

    well = c2f4 < c2f8 and c2f8 < start and start < c2fc and c2fc < c300
    if not well:
        half = _sar_div2(c2fc - c2f8)
        if not (c2f8 < start < c2fc):
            if c2f8 >= start:
                c2f8 = int(work.code_330) if half <= 0 else start - half
                c2f4 = int(work.code_32c)
            if start >= c2fc:
                c2fc = int(work.code_334) if half <= 0 else start + half
                c300 = int(work.code_338)
        if c2f4 >= c2f8:
            c2f4 = c2f8 - 1
        if c2fc >= c300:
            c300 = c2fc + 1
        work.code_2f4 = c2f4
        work.code_2f8 = c2f8
        work.code_2fc = c2fc
        work.code_300 = c300

    slope_adjust_92e00(work)
    _guard_mid_lo_931e0(work)
    _guard_white_93170(work)

    start = int(work.code_start)
    S = int(work.code_334) - start
    T = int(work.code_330) - start
    d_2f4 = int(work.code_2f4) - start
    d_2f8 = int(work.code_2f8) - start
    d_2fc = int(work.code_2fc) - start
    d_300 = int(work.code_300) - start
    d_32c = int(work.code_32c) - start
    d_338 = int(work.code_338) - start

    disp = curve_dispatch_93510(float(S), float(d_2fc), float(S))
    work.adj_378 = float(
        S
        - ftol2_chop(
            curve_exp_d80(float(S), float(d_2fc), float(S), disp) + F64_HALF
        )
    )
    disp = curve_dispatch_93510(float(d_338), float(d_300), float(d_338))
    work.adj_380 = float(
        S
        - ftol2_chop(
            curve_exp_d80(float(S), float(d_300), float(d_338), disp) + F64_HALF
        )
    )
    disp = curve_dispatch_93510(float(T), float(d_2f8), float(T))
    work.adj_370 = float(
        ftol2_chop(
            curve_exp_d80(float(T), float(d_2f8), float(T), disp) + F64_HALF
        )
        - T
    )
    disp = curve_dispatch_93510(float(d_32c), float(d_2f4), float(d_32c))
    work.adj_368 = float(
        ftol2_chop(
            curve_exp_d80(float(T), float(d_2f4), float(d_32c), disp) + F64_HALF
        )
        - T
    )
    # 0x1029390d…: if d_2f8 < 0 and adj_368 < d_2f8 → adj_368 = d_2f8
    if d_2f8 < 0 and work.adj_368 < float(d_2f8):
        work.adj_368 = float(d_2f8)

    _clamp_adjs_93230(work)
    return work


def scale_adjs_after_935d0(work: ToneLutBuilderWork) -> ToneLutBuilderWork:
    """``0x1027be10`` after ``0x102935d0``: ``+0x370*=+0x228``, ``+0x378*=+0x230``."""
    work.adj_370 = float(work.adj_370) * float(work.adj_scale_370)
    work.adj_378 = float(work.adj_378) * float(work.adj_scale_378)
    return work


def cap_set_tone_lut_from_i16(src_i16: np.ndarray) -> np.ndarray:
    """``setToneLut`` @ ``0x101e48d0`` — int16 → Cap ``+0x3e0`` int32 (``movsx``).

    Sole direct Cap ``+0x3e0`` writer found (wrapper ``0x1010d1b0``).
    """
    return np.asarray(src_i16, dtype=np.int16).astype(np.int32)


def publish_work_tone_lut_to_cap(work_tone: np.ndarray) -> np.ndarray:
    """Cap ``+0x3e0`` ← working ``+0x3b0`` via the ``setToneLut`` element path.

    Analyze has no automatic assign; host publishes through the cited Cap
    API (int16 low-word → sign-extended int32).
    """
    if work_tone.dtype != np.int32:
        raise TypeError("work toneLut expects int32")
    # Match getToneLut low-word then setToneLut movsx round-trip.
    return cap_set_tone_lut_from_i16((work_tone & 0xFFFF).astype(np.int16))


def assemble_tone_lut(
    work: ToneLutBuilderWork,
    *,
    run_935d0: bool = True,
    scale_adjs: bool = True,
    run_prep: bool = False,
    prep_inputs: tuple[tuple[float, float], ...] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build work ``toneLut`` + Cap publish vector from cited aims/fields.

    Runs ``0x102935d0`` (optional) → post-scale → builder ``0x10293ee0`` →
    Cap ``setToneLut`` publish. Returns ``(tone_i32, black_noise_i32, cap_i32)``.
    """
    w = ToneLutBuilderWork(**work.__dict__)
    if run_935d0:
        image_derived_fields_935d0(w)
        if scale_adjs:
            scale_adjs_after_935d0(w)
    n = max(int(w.code_max) + 1, 1)
    tone = empty_tone_lut(n)
    bn = empty_tone_lut(n)
    tone_lut_builder_93ee0(
        tone,
        bn,
        w,
        run_prep=run_prep,
        prep_inputs=prep_inputs,
        code_values_per_button=float(w.code_values_per_button),
    )
    cap = publish_work_tone_lut_to_cap(tone)
    # write back adj/codes the caller may want
    work.code_2f4 = w.code_2f4
    work.code_2f8 = w.code_2f8
    work.code_2fc = w.code_2fc
    work.code_300 = w.code_300
    work.adj_368 = w.adj_368
    work.adj_370 = w.adj_370
    work.adj_378 = w.adj_378
    work.adj_380 = w.adj_380
    work.p18_hi = w.p18_hi
    work.p38_hi = w.p38_hi
    work.p18_lo = w.p18_lo
    work.p38_lo = w.p38_lo
    return tone, bn, cap


def _builder_clamp_blends(w: ToneLutBuilderWork) -> None:
    """``0x10293ee0`` clamps cited blend doubles to ``[0,1]`` in place."""
    w.highlight_exp_blend = clamp01(w.highlight_exp_blend)
    w.highlight_transition_ratio = clamp01(w.highlight_transition_ratio)
    w.shadow_exp_blend = clamp01(w.shadow_exp_blend)
    w.shadow_transition_ratio = clamp01(w.shadow_transition_ratio)
    w.p340 = clamp01(w.p340)
    w.highlight_delta_gain = clamp01(w.highlight_delta_gain)
    w.shadow_comp_sat_factor = clamp01(w.shadow_comp_sat_factor)
    w.shadow_exp_sat_factor = clamp01(w.shadow_exp_sat_factor)



def apply_prep_7b1c0(
    work: ToneLutBuilderWork,
    prep_inputs: tuple[tuple[float, float], ...],
    *,
    code_values_per_button: float | None = None,
) -> ToneLutBuilderWork:
    """``0x1027b1c0`` breakpoint prep → ``off_328`` / ``code_32c…338``.

    Runs in ``0x1027be10`` before sampling/``935d0``, and again at the
    start of builder ``0x10293ee0``.
    """
    if len(prep_inputs) != 5:
        raise ValueError("prep needs five (stops, aggr) pairs")
    cv = (
        float(work.code_values_per_button)
        if code_values_per_button is None
        else float(code_values_per_button)
    )
    _a0, b0 = prep_breakpoint_pair(
        prep_inputs[0][0], prep_inputs[0][1], cv, work.code_48, work.code_48
    )
    work.off_328 = b0
    start = int(work.code_start)
    _a1, b1 = prep_breakpoint_pair(
        prep_inputs[1][0], prep_inputs[1][1], cv, start, start
    )
    work.code_32c = b1
    _a2, b2 = prep_breakpoint_pair(
        prep_inputs[2][0], prep_inputs[2][1], cv, start, start
    )
    work.code_330 = b2
    a3, _ = prep_breakpoint_pair(
        prep_inputs[3][0], prep_inputs[3][1], cv, start, start
    )
    work.code_334 = start + a3
    a4, _ = prep_breakpoint_pair(
        prep_inputs[4][0], prep_inputs[4][1], cv, start, start
    )
    work.code_338 = start + a4
    if work.code_330 >= start:
        work.code_330 = start - 1
    if work.code_32c >= work.code_330:
        work.code_32c = work.code_330 - 1
    if work.code_334 <= start:
        work.code_334 = start + 1
    if work.code_338 <= work.code_334:
        work.code_338 = work.code_334 + 1
    return work


def tone_lut_builder_93ee0(
    tone_lut: np.ndarray,
    black_noise: np.ndarray,
    work: ToneLutBuilderWork,
    *,
    run_prep: bool = False,
    prep_inputs: tuple[tuple[float, float], ...] | None = None,
    code_values_per_button: float = 75.0,
) -> ToneLutBuilderWork:
    """``0x10293ee0`` toneLut builder (Unicorn-golden with injected work).

    Reuses ``tone_lut_fill_93960`` twice + ``black_noise_fill_93d50`` +
    the post clamp/add loop. Cap publish is ``publish_work_tone_lut_to_cap``
    / ``assemble_tone_lut`` (not this leaf).

    If ``run_prep``, requires ``prep_inputs`` as five ``(stops, aggr)``
    pairs for ``0x1027b1c0`` channels (shadowAggr…highlightExpScale
    order as in prep); writes ``off_328`` / ``code_32c…338``.
    """
    if tone_lut.dtype != np.int32 or black_noise.dtype != np.int32:
        raise TypeError("toneLut/blackNoise expect int32")
    if run_prep:
        if prep_inputs is None:
            raise ValueError("run_prep needs five (stops, aggr) pairs")
        apply_prep_7b1c0(
            work, prep_inputs, code_values_per_button=code_values_per_button
        )

    _builder_clamp_blends(work)
    start = int(work.code_start)
    tone_lut_seed_identity(tone_lut, start)
    arg = int(work.code_48) - start

    # Fill #1 — highlight upward (end = +0x64)
    code_end = int(work.code_334)
    adj = ftol2_chop(float(work.adj_378))
    u0 = (
        float(work.highlight_exp_blend)
        if float(work.adj_378) >= F64_0
        else float(work.highlight_transition_ratio)
    )
    c28 = int(work.code_338)
    c2c = int(work.code_300)
    if code_end <= start:
        code_end = start + 1
        adj = 0
    if c28 <= code_end:
        c28 = code_end + 1
        c2c = c28
    if c2c <= start:
        c2c = c28
    p1 = ToneLutFillParam(
        code_end=code_end,
        adj=adj,
        u0=u0,
        p20=float(work.shadow_comp_sat_factor),
        code_28=c28,
        code_2c=c2c,
        p30=float(work.p340),
    )
    tone_lut_fill_93960(tone_lut, start, int(work.code_max), p1)
    work.p18_hi = p1.p18
    work.p38_hi = p1.p38

    # Fill #2 — shadow downward (end = 0)
    code_end = int(work.code_330)
    adj = ftol2_chop(float(work.adj_370))
    u0 = (
        float(work.shadow_exp_blend)
        if float(work.adj_370) >= F64_0
        else float(work.shadow_transition_ratio)
    )
    c28 = int(work.code_32c)
    c2c = int(work.code_2f4)
    if code_end >= start:
        code_end = start - 1
        adj = 0
    if c28 >= code_end:
        c28 = code_end - 1
        c2c = c28
    if c2c >= start:
        c2c = c28
    p2 = ToneLutFillParam(
        code_end=code_end,
        adj=adj,
        u0=u0,
        p20=float(work.shadow_exp_sat_factor),
        code_28=c28,
        code_2c=c2c,
        p30=float(work.highlight_delta_gain),
    )
    tone_lut_fill_93960(tone_lut, start, 0, p2)
    work.p18_lo = p2.p18
    work.p38_lo = p2.p38

    bn_in = BlackNoise93d50In(
        mid_lo=int(work.mid_lo),
        mid_hi=int(work.mid_hi),
        black_noise_std_dev=float(work.black_noise_std_dev),
        min_black_offset=float(work.min_black_offset),
        max_white_offset=float(work.max_white_offset),
        off_328=int(work.off_328),
        code_max=int(work.code_max),
        arg=arg,
    )
    black_noise_fill_93d50(black_noise, tone_lut, bn_in)

    # Post loop 0x10294266…b7: toneLut[i] += arg − blackNoise[i], clamp
    lo = int(work.code_min)
    hi = int(work.code_max)
    if hi >= 0:
        for i in range(hi + 1):
            v = int(tone_lut[i]) + arg - int(black_noise[i])
            if v < lo:
                v = lo
            elif v > hi:
                v = hi
            tone_lut[i] = np.int32(v)
    return work


@dataclass
class ImagePercentileCodes:
    """Generate ``+0x2e4…+0x2f0`` from ``0x1027b970``."""

    code_2e4: int  # extShadow
    code_2e8: int  # shadow
    code_2ec: int  # highlight
    code_2f0: int  # extHighlight


@dataclass
class ImageRangeMeans:
    """``0x1027b3c0`` outputs ``+0x310/+0x318/+0x320/+0x340``."""

    mean_310: float  # plane1 mean in range
    mean_318: float  # plane2 mean in range
    hypot_320: float
    p340: float


def hist_counts_from_plane0(
    plane: np.ndarray,
    n_bins: int = 4096,
) -> np.ndarray:
    """Host hist counts for percentile leaf (Iem ``0x104ea940`` not ported).

    Uses plane0 samples clipped to ``[0, n_bins)`` — same plane
    ``0x1027b3c0`` keys on.
    """
    p = np.asarray(plane).astype(np.int32, copy=False).ravel()
    p = np.clip(p, 0, n_bins - 1)
    return np.bincount(p, minlength=n_bins).astype(np.int32)


def hist_percentile_ea6c0(
    counts: np.ndarray,
    percent: float,
    *,
    origin: float = 0.0,
    scale: float = 1.0,
) -> int:
    """``0x104ea6c0`` + identity bin→code ``0x104f5710`` (Unicorn-golden).

    ``target = ftol2(percent * 0.01 * sum(counts))``; first bin with
    cumulative ≥ target; ``code = ftol2(bin * scale + origin)``.
    """
    c = np.asarray(counts, dtype=np.int32)
    total = int(c.sum())
    if total <= 0:
        return ftol2_chop(origin)
    target = ftol2_chop(float(percent) * 0.01 * float(total))
    cum = 0
    bin_i = 0
    n = int(c.shape[0])
    while bin_i < n:
        cum += int(c[bin_i])
        if cum >= target:
            break
        bin_i += 1
        if bin_i >= n:
            bin_i = n - 1
            break
    return ftol2_chop(float(bin_i) * float(scale) + float(origin))


def image_percentile_codes_7b970(
    sampled_counts: np.ndarray,
    *,
    ext_shadow_percent: float,
    shadow_percent: float,
    highlight_percent: float,
    ext_highlight_percent: float,
    mid_lo: int,
    code_white: int,
    blockavg_counts: np.ndarray | None = None,
    highlight_diff_mult: float = 0.0,
    highlight_diff_limit: float = 0.0,
    code_values_per_button: float = 75.0,
) -> ImagePercentileCodes:
    """``0x1027b970`` core: hist percents → ``+0x2e4…+0x2f0``.

    Generate work slots ``+0x80/+0x88/+0x90/+0x98`` carry the four dpi
    percent fields (see module doc). Optional blockAvg hist adjusts
    ``+0x2f0`` when ``highlightDiffMult > 0``.
    """
    c2e4 = hist_percentile_ea6c0(sampled_counts, ext_shadow_percent)
    c2e8 = hist_percentile_ea6c0(sampled_counts, shadow_percent)
    c2ec = hist_percentile_ea6c0(sampled_counts, highlight_percent)
    c2f0 = hist_percentile_ea6c0(sampled_counts, ext_highlight_percent)

    if (
        blockavg_counts is not None
        and float(highlight_diff_mult) > F64_0
    ):
        # Second image: same +0x80 / +0x98 → +0x2dc / +0x2e0 (cite DLL).
        _c2dc = hist_percentile_ea6c0(blockavg_counts, ext_shadow_percent)
        c2e0 = hist_percentile_ea6c0(blockavg_counts, ext_highlight_percent)
        delta = ftol2_chop(
            float(c2e0 - c2f0) * float(highlight_diff_mult) + F64_HALF
        )
        lim = ftol2_chop(
            float(highlight_diff_limit)
            * float(code_values_per_button)
            * F64_2_5
            + F64_HALF
        )
        if delta > lim:
            delta = lim
        if delta > 0:
            c2f0 = int(c2f0) + int(delta)
        if c2f0 > c2e0:
            c2f0 = int(c2e0)
        del _c2dc

    if c2e4 < int(mid_lo):
        c2e4 = int(mid_lo)
    if c2e8 < int(mid_lo):
        c2e8 = int(mid_lo)
    if c2ec > int(code_white):
        c2ec = int(code_white)
    if c2f0 > int(code_white):
        c2f0 = int(code_white)
    return ImagePercentileCodes(c2e4, c2e8, c2ec, c2f0)


def white_pt_ratio_7b3c0(
    hypot_320: float,
    *,
    use_white_pt: bool,
    white_sat_lower: float,
    white_sat_upper: float,
    code_values_per_button: float,
) -> float:
    """``0x1027b3c0`` ``+0x340`` from ``+0x320`` and sat limits."""
    if not use_white_pt:
        return F64_1
    lo = float(white_sat_lower) * float(code_values_per_button)
    hi = float(white_sat_upper) * float(code_values_per_button)
    h = float(hypot_320)
    if lo <= F64_0 or hi <= lo or h <= lo:
        return F64_1
    if h >= hi:
        return F64_0
    return (hi - h) / (hi - lo)


def image_range_means_7b3c0(
    rgb_i16: np.ndarray,
    lo: int,
    hi: int,
    *,
    use_white_pt: bool = True,
    white_sat_lower: float = 0.33,
    white_sat_upper: float = 0.8,
    code_values_per_button: float = 75.0,
) -> ImageRangeMeans:
    """``0x1027b3c0`` planar means for plane0 in ``[lo, hi]``.

    ``rgb_i16`` is HxWx3 (or 3xH rows of plane pointers flattened as
    channels last). Keys on channel 0; accumulates channels 1 and 2.
    """
    img = np.asarray(rgb_i16)
    if img.ndim != 3 or img.shape[2] < 3:
        raise ValueError("0x1027b3c0 expects HxWx3 I16")
    p0 = img[:, :, 0].astype(np.int32, copy=False).ravel()
    p1 = img[:, :, 1].astype(np.int32, copy=False).ravel()
    p2 = img[:, :, 2].astype(np.int32, copy=False).ravel()
    mask = (p0 >= int(lo)) & (p0 <= int(hi))
    n = int(mask.sum())
    if n <= 0:
        return ImageRangeMeans(F64_0, F64_0, F64_0, F64_1)
    m1 = float(p1[mask].sum()) / float(n)
    m2 = float(p2[mask].sum()) / float(n)
    hyp = math.sqrt(m1 * m1 + m2 * m2)
    p340 = white_pt_ratio_7b3c0(
        hyp,
        use_white_pt=use_white_pt,
        white_sat_lower=white_sat_lower,
        white_sat_upper=white_sat_upper,
        code_values_per_button=code_values_per_button,
    )
    return ImageRangeMeans(m1, m2, hyp, p340)


def seed_image_fields_7be10(
    work: ToneLutBuilderWork,
    codes: ImagePercentileCodes,
    *,
    p340: float | None = None,
) -> ToneLutBuilderWork:
    """``0x1027be10`` after sampling: ``+0x2f4…+0x300`` + ``+0x308``.

    ``+0x308 = ((+0x2ec-+0x2e4-+0x2e8)+(+0x2f0))/2 / (+0x58·2.5)``.
    """
    work.code_2f4 = int(codes.code_2e4)
    work.code_2f8 = int(codes.code_2e8)
    work.code_2fc = int(codes.code_2ec)
    work.code_300 = int(codes.code_2f0)
    if p340 is not None:
        work.p340 = float(p340)
    num = _sar_div2(
        int(codes.code_2ec)
        - int(codes.code_2e4)
        - int(codes.code_2e8)
        + int(codes.code_2f0)
    )
    den = float(work.code_values_per_button) * F64_2_5
    # stored at +0x308 (not on ToneLutBuilderWork); side-effect free here
    _ = float(num) / den if den else F64_0
    return work


def seed_image_fields_from_analysis(
    work: ToneLutBuilderWork,
    rgb_i16: np.ndarray,
    dpi: "ShastaDpi",
    *,
    blockavg_rgb: np.ndarray | None = None,
) -> ToneLutBuilderWork:
    """Inject-free ``+0x2f4…+0x300`` / ``+0x340`` from analysis image.

    Runs ``0x1027b970`` + ``0x1027b3c0`` + ``0x1027be10`` seed maths.
    """
    n_bins = int(round(dpi.max_value)) + 1
    plane0 = np.asarray(rgb_i16)[:, :, 0]
    sampled = hist_counts_from_plane0(plane0, n_bins)
    block = None
    if blockavg_rgb is not None:
        block = hist_counts_from_plane0(
            np.asarray(blockavg_rgb)[:, :, 0], n_bins
        )
    codes = image_percentile_codes_7b970(
        sampled,
        ext_shadow_percent=dpi.ext_shadow_percent,
        shadow_percent=dpi.shadow_percent,
        highlight_percent=dpi.highlight_percent,
        ext_highlight_percent=dpi.ext_highlight_percent,
        mid_lo=int(work.mid_lo),
        code_white=int(work.code_white) if work.code_white else int(round(dpi.white)),
        blockavg_counts=block,
        highlight_diff_mult=dpi.highlight_diff_mult,
        highlight_diff_limit=dpi.highlight_diff_limit,
        code_values_per_button=dpi.code_values_per_button,
    )
    means = image_range_means_7b3c0(
        rgb_i16,
        codes.code_2ec,
        codes.code_2f0,
        use_white_pt=dpi.use_white_pt_compression,
        white_sat_lower=dpi.white_sat_lower_limit,
        white_sat_upper=dpi.white_sat_upper_limit,
        code_values_per_button=dpi.code_values_per_button,
    )
    return seed_image_fields_7be10(work, codes, p340=means.p340)


def tone_lut_work_from_dpi(
    dpi: "ShastaDpi",
    *,
    mid_lo: int | None = None,
    mid_hi: int | None = None,
) -> ToneLutBuilderWork:
    """Builder/935d0 work from shipped dpi. Mids default black/metricGray."""
    start = int(round(dpi.metric_gray))
    white = int(round(dpi.white))
    lo = int(round(dpi.black)) if mid_lo is None else int(mid_lo)
    hi = start if mid_hi is None else int(mid_hi)
    return ToneLutBuilderWork(
        code_start=start,
        code_min=int(round(dpi.min_value)),
        code_max=int(round(dpi.max_value)),
        code_48=start + int(round(dpi.code_values_per_button)),
        code_values_per_button=float(dpi.code_values_per_button),
        mid_lo=lo,
        mid_hi=hi,
        code_white=white,
        shadow_exp_blend=float(dpi.shadow_exp_blend),
        highlight_exp_blend=float(dpi.highlight_exp_blend),
        shadow_transition_ratio=float(dpi.shadow_transition_ratio),
        highlight_transition_ratio=float(dpi.highlight_transition_ratio),
        shadow_exp_sat_factor=float(dpi.shadow_exp_sat_factor),
        shadow_comp_sat_factor=float(dpi.shadow_comp_sat_factor),
        highlight_delta_gain=float(dpi.highlight_delta_gain),
        black_noise_std_dev=float(dpi.black_noise_std_dev),
        min_black_offset=float(dpi.min_black_offset),
        max_white_offset=float(dpi.max_white_offset),
        highlight_exp_scale=float(dpi.highlight_exp_scale),
        shadow_max_exp_slope=float(dpi.shadow_max_exp_slope),
        highlight_max_exp_slope=float(dpi.highlight_max_exp_slope),
        shadow_comp_blend=float(dpi.shadow_comp_blend),
        max_exp_delta=float(dpi.max_exp_delta),
        max_comp_delta=float(dpi.max_comp_delta),
        adj_clamp_lo_src=float(dpi.white_sat_lower_limit)
        * float(dpi.code_values_per_button),
        adj_clamp_hi_src=float(dpi.white_sat_upper_limit)
        * float(dpi.code_values_per_button),
    )


def dpi_prep_inputs(dpi: "ShastaDpi") -> tuple[tuple[float, float], ...]:
    """Five ``(buttons, aggr)`` pairs for ``0x1027b1c0``."""
    return (
        (dpi.shadow_buttons, dpi.shadow_aggr),
        (dpi.ext_shadow_buttons, dpi.ext_shadow_aggr),
        (dpi.black_buttons, dpi.black_aggr),
        (dpi.highlight_buttons, dpi.highlight_aggr),
        (dpi.ext_highlight_buttons, dpi.ext_highlight_aggr),
    )


def assemble_scene_tone_lut(
    dpi: "ShastaDpi",
    rgb_i16: np.ndarray,
    *,
    mid_lo: int | None = None,
    mid_hi: int | None = None,
    blockavg_rgb: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, ToneLutBuilderWork]:
    """Preference-path assemble: live ``7b970``/``7b3c0`` → ``935d0`` → Cap."""
    if not SHASTA_TONE_LUT_PORTED:
        raise RuntimeError("SHASTA_TONE_LUT_PORTED is False")
    work = tone_lut_work_from_dpi(dpi, mid_lo=mid_lo, mid_hi=mid_hi)
    prep = dpi_prep_inputs(dpi)
    apply_prep_7b1c0(work, prep)
    seed_image_fields_from_analysis(
        work, rgb_i16, dpi, blockavg_rgb=blockavg_rgb
    )
    tone, bn, cap = assemble_tone_lut(
        work,
        run_935d0=True,
        scale_adjs=True,
        run_prep=True,
        prep_inputs=prep,
    )
    return tone, bn, cap, work


def ima_shasta_apply_i16(
    plane: np.ndarray,
    tone_lut: np.ndarray,
) -> np.ndarray:
    """Verified I16 apply fragment @ ``0x1014dcf1``.

    ``out[i] = low16(toneLut[in[i]])`` with ``toneLut`` as int32[].
    No bounds clamp in the cited loop — caller must ensure indices are
    valid.
    """
    if plane.dtype not in (np.int16, np.uint16):
        raise TypeError("I16 apply fragment expects int16/uint16 plane")
    if tone_lut.dtype != np.int32:
        raise TypeError("toneLut must be int32")
    codes = plane.astype(np.int32, copy=False)
    # Match DLL: movsx from I16, then word load from int32 slot.
    return (tone_lut[codes] & 0xFFFF).astype(np.int16)


def ima_shasta_apply_f32(
    plane: np.ndarray,
    tone_lut: np.ndarray,
) -> np.ndarray:
    """Verified float apply fragment @ ``0x1014dd60``.

    ``out = (float)toneLut[fist(in)]``. No clamp in the cited loop.
    """
    if plane.dtype != np.float32:
        plane = plane.astype(np.float32)
    if tone_lut.dtype != np.int32:
        raise TypeError("toneLut must be int32")
    idx = np.vectorize(fist_round, otypes=[np.int64])(plane)
    return tone_lut[idx].astype(np.float32)


def ima_shasta_op_apply(
    image: np.ndarray,
    tone_lut: np.ndarray,
) -> np.ndarray:
    """``ImaShastaOp`` type dispatch ``0x1014de50`` (I16 path).

    DLL supports I16 only (``0x1057c848``). ``image`` is HxW or HxWxC
    int16; applies the cited in-place LUT-index loop per plane.
    """
    if not SHASTA_APPLY_PORTED:
        raise RuntimeError("SHASTA_APPLY_PORTED is False")
    if tone_lut.dtype != np.int32:
        raise TypeError("toneLut must be int32")
    img = np.asarray(image)
    if img.dtype not in (np.int16, np.uint16):
        raise TypeError(
            "Only I16 data type is supported by ImaShastaOp (0x1057c848)"
        )
    n = len(tone_lut)
    if img.ndim == 2:
        plane = np.clip(img, 0, n - 1).astype(np.int16, copy=False)
        return ima_shasta_apply_i16(plane, tone_lut)
    if img.ndim != 3:
        raise ValueError("ImaShastaOp expects HxW or HxWxC")
    planes = []
    for c in range(img.shape[2]):
        plane = np.clip(img[:, :, c], 0, n - 1).astype(np.int16, copy=False)
        planes.append(ima_shasta_apply_i16(plane, tone_lut))
    return np.stack(planes, axis=-1)


def empty_tone_lut(n: int = 4096) -> np.ndarray:
    """Allocate working toneLut storage (size typically 4096 / maxValue+1)."""
    return np.zeros(n, dtype=np.int32)


@dataclass
class ShastaDpi:
    """Scalars from a shipped ``shasta-*.dpi`` (aims / policy — not toneLut)."""

    path: Path
    key: str = ""
    raw: dict[str, str] = field(default_factory=dict)

    analysis_image_dim: int = 64
    black: float = 0.0
    white: float = 3000.0
    metric_gray: float = 1618.0
    max_value: float = 4095.0
    min_value: float = 0.0
    code_values_per_button: float = 75.0
    shadow_percent: float = 1.0
    highlight_percent: float = 99.0
    ext_shadow_percent: float = 0.1
    ext_highlight_percent: float = 99.9
    highlight_diff_mult: float = 0.0
    highlight_diff_limit: float = 0.0
    filter_policy: int = 3
    use_white_pt_compression: bool = True
    white_sat_lower_limit: float = 0.33
    white_sat_upper_limit: float = 0.8
    black_noise_supp_stops: float = 0.75
    black_noise_sigma_mult: float = 2.0
    black_noise_std_dev: float = 1.0
    min_black_offset: float = 0.62
    max_white_offset: float = 3.0
    shadow_exp_blend: float = 0.5
    highlight_exp_blend: float = 0.5
    shadow_transition_ratio: float = 0.5
    highlight_transition_ratio: float = 0.5
    shadow_exp_sat_factor: float = 0.25
    shadow_comp_sat_factor: float = 0.0
    highlight_delta_gain: float = 1.0
    highlight_exp_scale: float = 0.5
    shadow_max_exp_slope: float = 2.0
    highlight_max_exp_slope: float = 2.0
    shadow_comp_blend: float = 0.5
    max_exp_delta: float = 4.0
    max_comp_delta: float = 4.0
    shadow_buttons: float = 6.67
    shadow_aggr: float = 0.75
    ext_shadow_buttons: float = 9.28
    ext_shadow_aggr: float = 0.7
    black_buttons: float = 10.466
    black_aggr: float = 1.0
    highlight_buttons: float = 3.67
    highlight_aggr: float = 1.1
    ext_highlight_buttons: float = 7.68
    ext_highlight_aggr: float = 1.25
    row_portion: float = 0.875
    col_portion: float = 0.875

    @classmethod
    def load(cls, path: Path) -> "ShastaDpi":
        d = parse_dpi_scalars(path)
        return cls(
            path=path,
            key=d.get("key", path.stem),
            raw=d,
            analysis_image_dim=int(_num(d, "analysisImageDim", 64)),
            black=_num(d, "black", 0.0),
            white=_num(d, "white", 3000.0),
            metric_gray=_num(d, "metricGray", 1618.0),
            max_value=_num(d, "maxValue", 4095.0),
            min_value=_num(d, "minValue", 0.0),
            code_values_per_button=_num(d, "codeValuesPerButton", 75.0),
            shadow_percent=_num(d, "shadowPercent", 1.0),
            highlight_percent=_num(d, "highlightPercent", 99.0),
            ext_shadow_percent=_num(d, "extShadowPercent", 0.1),
            ext_highlight_percent=_num(d, "extHighlightPercent", 99.9),
            highlight_diff_mult=_num(d, "highlightDiffMult", 0.0),
            highlight_diff_limit=_num(d, "highlightDiffLimit", 0.0),
            filter_policy=int(_num(d, "filterPolicy", 3)),
            use_white_pt_compression=_bool(d, "bUseWhitePtCompression", True),
            white_sat_lower_limit=_num(d, "whiteSatLowerLimit", 0.33),
            white_sat_upper_limit=_num(d, "whiteSatUpperLimit", 0.8),
            black_noise_supp_stops=_num(d, "blackNoiseSuppStops", 0.75),
            black_noise_sigma_mult=_num(
                d, "blackNoiseSigmaMult", SHASTA_PARAMS_CTOR_BLACK_NOISE_SIGMA_MULT
            ),
            black_noise_std_dev=_num(d, "blackNoiseStdDev", 1.0),
            min_black_offset=_num(d, "minBlackOffset", 0.62),
            max_white_offset=_num(d, "maxWhiteOffset", 3.0),
            shadow_exp_blend=_num(d, "shadowExpBlend", 0.5),
            highlight_exp_blend=_num(d, "highlightExpBlend", 0.5),
            shadow_transition_ratio=_num(d, "shadowTransitionRatio", 0.5),
            highlight_transition_ratio=_num(d, "highlightTransitionRatio", 0.5),
            shadow_exp_sat_factor=_num(d, "shadowExpSatFactor", 0.25),
            shadow_comp_sat_factor=_num(d, "shadowCompSatFactor", 0.0),
            highlight_delta_gain=_num(d, "highlightDeltaGain", 1.0),
            highlight_exp_scale=_num(d, "highlightExpScale", 0.5),
            shadow_max_exp_slope=_num(d, "shadowMaxExpSlope", 2.0),
            highlight_max_exp_slope=_num(d, "highlightMaxExpSlope", 2.0),
            shadow_comp_blend=_num(d, "shadowCompBlend", 0.5),
            max_exp_delta=_num(d, "maxExpDelta", 4.0),
            max_comp_delta=_num(d, "maxCompDelta", 4.0),
            shadow_buttons=_num(d, "shadowButtons", 6.67),
            shadow_aggr=_num(d, "shadowAggr", 0.75),
            ext_shadow_buttons=_num(d, "extShadowButtons", 9.28),
            ext_shadow_aggr=_num(d, "extShadowAggr", 0.7),
            black_buttons=_num(d, "blackButtons", 10.466),
            black_aggr=_num(d, "blackAggr", 1.0),
            highlight_buttons=_num(d, "highlightButtons", 3.67),
            highlight_aggr=_num(d, "highlightAggr", 1.1),
            ext_highlight_buttons=_num(d, "extHighlightButtons", 7.68),
            ext_highlight_aggr=_num(d, "extHighlightAggr", 1.25),
            row_portion=_num(d, "rowPortion", 0.875),
            col_portion=_num(d, "colPortion", 0.875),
        )

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dpi", type=Path, nargs="?")
    args = ap.parse_args()
    if not args.dpi:
        root = Path(
            "/Users/guy/Downloads/Pakon Update 2/fx35install/"
            "program files/Pakon/F-X35 COM SERVER/anselinstalldir/"
            "dataPathItems/shasta"
        )
        args.dpi = root / "shasta-rpd.dpi"
    dpi = ShastaDpi.load(args.dpi)
    print(f"{args.dpi.name}: key={dpi.key}")
    print(
        f"  white={dpi.white:g} metricGray={dpi.metric_gray:g} "
        f"maxValue={dpi.max_value:g} cv/button={dpi.code_values_per_button:g}"
    )
    # Fragment demo only — not a real toneLut
    lut = empty_tone_lut(int(dpi.max_value) + 1)
    code = int(round(dpi.metric_gray))
    tone_lut_seed_identity(lut, code)
    print(f"  seed fragment: toneLut[{code}]={int(lut[code])} (identity only)")
    a, b = prep_breakpoint_pair(3.67, 1.1, dpi.code_values_per_button, code, code)
    print(f"  prep fragment example (highlightButtons*aggr): a={a} b={b}")
    # Synthetic dens table + zero shifts — demos mid-aim maths only.
    dens = np.zeros(4096, dtype=np.float32)
    dens[code] = 10.0
    mid_lo, mid_hi = cn_premium_mid_aim_rgb(
        (code, code, code),
        dens,
        (0, 0, 0),
        black=int(round(dpi.black)),
        metric_gray=int(round(dpi.metric_gray)),
        black_noise_sigma_mult=dpi.black_noise_sigma_mult,
    )
    codes = aim_codes_from_dpi_ends(dpi, mid_lo, mid_hi)
    print(
        f"  aim ends: metricGray→+0x2b0={codes[0]} white→+0x2bc={codes[3]} "
        f"mids={codes[1]},{codes[2]} (synthetic dens; not scene dmin)"
    )
    print(
        f"  avg2largest(1,2,3)={avg2largest_i16(1, 2, 3)} "
        f"(0x1004f690; AIM_AVG2={SHASTA_AIM_AVG2_PORTED} "
        f"MID_RGB={SHASTA_AIM_MID_RGB_PORTED} "
        f"INPUT_PATH={SHASTA_AIM_INPUT_PATH_PORTED})"
    )
    print(
        f"  master_lut_clip(-1)={master_lut_clip_i16(-1)} "
        f"4096→{master_lut_clip_i16(4096)} "
        f"ftol2(2.5*2)={ftol2_chop(5.0)}"
    )
    # Synthetic fill demo (injected aims/param — not scene analyze).
    end = int(round(dpi.white))
    fill_param = ToneLutFillParam(
        code_end=min(code + 450, end),
        adj=50,
        u0=0.5,
        p20=0.25,
        code_28=code + 250,
        code_2c=code + 350,
        p30=1.0,
    )
    tone_lut_fill_93960(lut, code, end, fill_param)
    mid = (code + end) // 2
    print(
        f"  fill 0x10293960 (injected): p18={fill_param.p18:.6g} "
        f"p38={fill_param.p38:.6g} lut[{mid}]={int(lut[mid])} "
        f"FILL={SHASTA_CURVE_FILL_PORTED}"
    )
    bn = empty_tone_lut(int(dpi.max_value) + 1)
    work = ToneLutBuilderWork(
        code_start=code,
        code_min=0,
        code_max=end,
        code_48=code + 200,
        off_328=100,
        code_32c=code - 400,
        code_330=code - 200,
        code_334=min(code + 450, end),
        code_338=min(code + 550, end),
        code_2f4=code - 350,
        code_300=code + 350,
        p340=1.0,
        adj_370=40.0,
        adj_378=50.0,
        mid_lo=codes[1],
        mid_hi=codes[2],
    )
    tone_lut_builder_93ee0(lut, bn, work)
    print(
        f"  builder 0x10293ee0 (injected): p18_hi={work.p18_hi:.6g} "
        f"p18_lo={work.p18_lo:.6g} bn[{code}]={int(bn[code])} "
        f"BUILDER={SHASTA_TONE_LUT_BUILDER_PORTED} "
        f"93D50={SHASTA_BLACK_NOISE_93D50_PORTED}"
    )
    plane = np.array([code], dtype=np.int16)
    out = ima_shasta_apply_i16(plane, lut)
    print(f"  I16 apply fragment: in={code} out={int(out[0])}")
    print(
        f"  SHASTA_TONE_LUT_PORTED={SHASTA_TONE_LUT_PORTED} "
        f"ANALYZE_PORTED={SHASTA_ANALYZE_PORTED} "
        f"APPLY_PORTED={SHASTA_APPLY_PORTED} "
        f"7B970={SHASTA_IMAGE_PERCENTILE_7B970_PORTED} "
        f"7B3C0={SHASTA_IMAGE_SAMPLE_7B3C0_PORTED} "
        f"FRAGMENTS={SHASTA_TONE_LUT_FRAGMENTS} "
        f"LOG_RATIO={SHASTA_CURVE_LOG_RATIO_PORTED} "
        f"EXP={SHASTA_CURVE_EXP_PORTED} "
        f"DISPATCH={SHASTA_CURVE_DISPATCH_PORTED} "
        f"FILL={SHASTA_CURVE_FILL_PORTED} "
        f"BUILDER={SHASTA_TONE_LUT_BUILDER_PORTED} "
        f"93D50={SHASTA_BLACK_NOISE_93D50_PORTED} "
        f"935D0={SHASTA_IMAGE_FIELDS_935D0_PORTED} "
        f"CAP={SHASTA_CAP_TONE_LUT_PORTED}"
    )
    print(
        f"  log-ratio: c50(0.5,1)={curve_log_ratio_c50(0.5, 1.0):.6g} "
        f"cb0(0.5,1)={curve_log_ratio_cb0(0.5, 1.0):.6g}"
    )
    print(
        "  assemble+sample+I16 Op ported (APPLY=True); "
        "ANALYZE still WALL on live aim producers"
    )


if __name__ == "__main__":
    main()
