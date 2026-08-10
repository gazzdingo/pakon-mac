#!/usr/bin/env python3
"""PIColorAdjustPlanar — verified host post-Ansel stage (PakonIMAu / TLA).

Runs **after** ``PIAnselColorSceneBalancePlanar`` (and scale), inside
``CiImage::bSaveToFile`` via ``bApplyColorAdjustments``. Do **not** invent
unsharp amounts or Preference / ``+0x4d0e`` maths.

``COLOR_ADJUST_PORTED`` is True for the host ColorAdjust stage (selectors,
contrast, unsharp, stock unity SpCombine identity, ConnectEx/PTCombine
control plane, live Unicorn SpCombine). ``COLOR_ADJUST_PT_MERGE_BODY_PORTED``
covers ``+0x1140``/``+0x1230``/``+0x9820`` ituf LUT fill + ``+0x7aa0`` merge
control (sample combiner ``@ 0x100127e0`` remains a call-through).

When it runs (VERIFIED — TLA ``bSaveToFile`` / ``bLoadImageFromBuffer``)
--------------------------------------------------------------------
``bSaveToFile`` @ ``TLA.dll:0x1002d980``:

1. ``bLoadImageFromBuffer`` @ ``0x1002caa0`` (``E8`` @ ``0x1002df72``)
   * ``bApplyKodakColorCorrection`` @ ``0x10014ff0``
   * ``bRotate`` @ ``0x10029d30``
   * ``call [eax+0x64]`` @ ``0x1002cf82`` →
     ``PIAnselColorSceneBalancePlanar`` (IMAu slot)
   * ``bScale`` @ ``0x10029af0``
2. ``bApplyColorAdjustments`` @ ``0x1002a5a0`` (``E8`` @ ``0x1002e193``)
   * ``call [eax+0x38]`` @ ``0x1002a73f`` → ``PIColorAdjustPlanar``

So ColorAdjust is **save-path only**, after Ansel apply + scale, before
16→8 / ``PISaveFilePlanar_8``.

``PIColorAdjustPlanar`` @ ``PakonIMAu.dll:0x10013bc0``
-----------------------------------------------------
Builds named ``Ima*`` ops (string pushes), in order:

1. ``ImaXformTransform_profile0`` @ push ``0x10013d59``
2. ``ImaXformTransform_SaturationProfile`` @ ``0x10013f81``
3. ``ImaXformTransform_BnWEffectProfile`` @ ``0x10014197``
4. ``ImaXformTransform_profile1`` @ ``0x10014352``
5. ``ImaXformCombineTransform_profileCombined`` @ ``0x10014569``
   (Kodak ``SpCombineXforms`` — four xforms → one) — **not ported**
6. ``ImaMemorySourceOperation`` @ ``0x10014735``
7. ``ImaContrastLutOperation`` @ ``0x10014ba6`` (gated; body ported)
8. ``ImaUnsharpMaskOperation`` @ ``0x10014dad`` — **after** colour
9. ``ImaICCEffectOperation_profileCombined`` @ ``0x10014fa9``

Profiles live under ``\\Config\\ColorCorrection\\`` (wstr ``0x10575924``).

TLA ColorAdjust object (``CiImage+0xc8``, ctor ``TLA:0x10010ae0``)
-------------------------------------------------------------------
All adjustable fields **zero** at construct (VERIFIED). Setter
``0x10010ba0`` clamps each arg to ``[-1000, +1000]`` (``0xfffffc18…0x3e8``):

| offset | field |
|-------:|-------|
| ``+0x08`` | Red |
| ``+0x0c`` | Green |
| ``+0x10`` | Blue |
| ``+0x14`` | Brightness |
| ``+0x18`` | Contrast |
| ``+0x1c`` | Sharpness |
| ``+0x20…+0x34`` | differential twins (same order) |
| ``+0x54`` | BnW effect |
| ``+0x58`` | saturation |

``bApplyColorAdjustments`` sums primary+diff into the IMAu params block
(``params+0x14…+0x28``). Gate ``params+0x10`` = save-flag bit6
(``!(flags>>6)`` inverted via ``sete`` @ ``TLA:0x1002a728``) — non-zero
enables contrast/unsharp.

Contrast / unsharp gate inside IMAu (VERIFIED @ ``0x10014774``)
--------------------------------------------------------------
``cmp [params+0x10], 0`` → je ``0x10014e77`` (skip contrast+unsharp).

Then load:

* ``contrast = params+0x24``; ``half = trunc(contrast/2)`` (cdq/sub/sar)
* ``sharp_f = fild(params+0x28)``
* ``bright = params+0x20``; RGB channel sums ``params+0x14/18/1c``
* per-channel offset = ``(R|G|B) + bright``

If ``half==0`` and all three offsets ``==0`` → je ``0x10014c43``
(**skip contrast LUT build**; identity not materialised).

Else build three 4096-entry int16 LUTs (pivot ``0x60e``):

* ``scale = half + 1000`` (``0x3e8``)
* ``lut[i] = trunc((i - 0x60e) * scale / 1000) + 0x60e``
  (magic ``0x10624dd3``, ``sar 6`` + signbit → toward-zero)
* clamp ``0…0xfff`` unless offset-mode
* per-channel: ``delta = trunc((offset<<12) * magic >> 40)``
  (``sar 8`` + signbit) ≈ ``trunc(offset * 1.024)``; add + clamp

Unsharp params (VERIFIED)
------------------------------------------------
If ``sharp_f == 0.0`` (fucompp @ ``0x10014c43``) → skip unsharp.

Else:

* amount = ``sharp_f * 0.01`` (``qword 0x105756d8``) @ ``0x10014ca3``
* separable 3-tap kernel weights ``[0.25, 0.5, 0.25]``
  (``0x105756e0`` / ``0x10574f40``) stacked @ ``0x10014c5c…0x10014c97``
* passed into ctor ``0x10011330`` → ``0x10368960``

Unsharp **pixel apply** (VERIFIED structure; leaf-golden)
--------------------------------------------------------
Separable body ``0x10370de0`` / scalar ``0x10013a42`` / MMX
``0x103d29c0``: ``out = clamp_i16(orig + amount·(orig − blur))`` with
blur = separable 3-tap ``[0.25,0.5,0.25]``. Kernel scale leaf
``0x1030dbe0`` (Unicorn-golden): channels>1 → max ``0x4000``; else
``0x100``; ``S`` halved until ``trunc(S·Σ|w|+0.2) ≤ max``
(``0.2`` @ ``0x10588eb8``). ColorAdjust 3-tap → ``S=16384``,
int coeffs ``[4096,8192,4096]``, shift 14.

``0x10164461`` + ``8192.0`` @ ``0x1058f1b8`` is a cosine window builder —
**not** this ColorAdjust 3-tap path.

``SpCombineXforms`` (VERIFIED location; body open)
--------------------------------------------------
IAT ``0x105730fc`` → ``kodakcms.dll!SpCombineXforms``. Profile0 ∘ sat ∘
BnW ∘ profile1.

IMAu callers (stdcall, six args) @ ``0x10389757`` / ``0x1038ad16``:

| arg | role (VERIFIED) |
|----:|-----------------|
| 0 | ``n`` — xform count (``esi`` / ``edi``) |
| 1 | ``SpXform[]`` ptr |
| 2 | out dword* (ConnectEx zeros → ``0``) |
| 3 | out dword* (ConnectEx writes ``0xffffffff``) |
| 4 | ``0`` (stock sites) |
| 5 | ``0`` (stock sites) |

**Wrapper (Unicorn-golden):** ``kodakcms!SpCombineXforms`` @ ``0x1003c8f0``
is a thin ``ret 0x18`` trampoline — pushes its six stack args plus
``0x103``, then ``call SpConnectSequenceEx`` @ ``0x1002e740``.
``COLOR_ADJUST_SPCOMBINE_WRAPPER_PORTED``.

**ConnectEx prologue (Unicorn-golden):** ``n < 2`` → eax ``0x206``;
``*a3 = -1``, ``*a2 = 0`` @ ``0x1002e761…0x1002e785``.
``COLOR_ADJUST_SPCONNECT_PROLOGUE_PORTED``.

**ConnectEx body stages (VERIFIED structure; maths open):** after
``n ≥ 2`` @ ``0x1002e788``:

1. Per-xform validate loop ``0x1002e78e…0x1002e7ca`` —
   ``SpXformGetRefNum`` @ ``0x1002f0c0`` then ``PTGetPTInfo+0x70`` @
   ``0x1000a830``; accept PT type ``0x6b`` or ``0x132``; else
   ``0x1fb``. Host gate + live GetRefNum golden:
   ``COLOR_ADJUST_SPCONNECT_VALIDATE_PORTED``.
2. Alloc workspace ``2·n`` then ``4·n`` bytes via
   ``allocSysBufferPtr`` @ ``0x100297b0``; fail → ``0x203``.
3. Walk xforms backward: resolve / ``Lab ``∪`` XYZ`` tag gate
   (``0x4c616220`` / ``0x58595a20``) / ``PTGetRelToAbsPT`` @
   ``0x10040d50``; copy helper ``0x1002eca0`` (12-byte / 3-dword)
   golden as ``COLOR_ADJUST_SPCONNECT_COPY12_PORTED``.
4. Flag dispatch ``(connect_flag & 0xf0)`` @ ``0x1002eb32`` —
   ``0`` → ``@ 0x1002e490``, ``0x10`` → ``@ 0x1002e420`` then
   ``@ 0x1002e5a0``, ``0x20`` → ``@ 0x1002e650``, else ``0x206``.
   SpCombine pushes ``0x103`` → path ``@ 0x1002e490``
   (``COLOR_ADJUST_SPCONNECT_PATH0_PORTED``):
     * mode encode ``@ 0x1002e420`` → ``0x406``
     * ``PTChain*`` via ``@ 0x1002e5a0`` (``PTChainInitM`` /
       ``PTChain`` / ``PTChainEnd``); live unity SpCombine returns here
       with Sp status ``0``
     * ``PTCombine`` is invoked **inside** ``PTChain`` /
       ``PTChainEnd`` (``@ 0x10040cf3`` / ``@ 0x10040abb``), not only
       as path_0's pairwise fallback
5. ``PTCombine`` case ``(mode&0xff)∈{4…7}`` → ``@ 0x1003fe32`` →
   ``+0x460`` @ ``0x10040140``. Grid-size leaf
   (``COLOR_ADJUST_PTCOMBINE_GRID_PORTED``): ``(mode&0xff)∈{5,6}`` →
   base ``0x40``; ``esi·900/1000`` via magic ``0x10624dd3``
   (``@ 0x10040385…``).
6. After-grid control (``COLOR_ADJUST_PTCOMBINE_AFTER_GRID_PORTED``):
   ``PTChainInitM @ 0x10040966`` ORs ``0x800`` onto chain mode (unless
   the ``'S'\\0`` early path). ``+0x460`` then: ``mode&0x400`` may raise
   ``esi`` from a tag size; ``mode&0x800`` floors ``esi`` to ``≥0x10``
   (else ``≥0x8``) @ ``0x10040324``; after ``[esp+54]`` fill with ``esi``,
   ``mode&0x800`` skips the type switch and jumps to
   ``PTGetPTInfo+0x2110 @ 0x1000c8d0`` with those dims
   (``@ 0x100403c8…0x1004054d``). Without ``0x800``, ``(type−2)`` indexes
   byte table ``@ 0x10040684`` → jmp table ``@ 0x10040670``. Live unity
   SpCombine takes the ``0x800`` path and ``+0x2110`` early-identity
   returns the same PT when all eight channel dims already match.
7. ``+0x2110`` rebuild arm (``COLOR_ADJUST_PTGETPTINFO_2110_REBUILD_PORTED``)
   when dims mismatch: pack
   ``((mask_byte)<<8)|(channels&0xff)`` @ ``0x1000c9c0…0x1000c9d9``
   (``mask_byte`` = low byte of CTUF-slot bitmask built @ ``0x1000c97d``),
   then call ``+0x930`` / ``+0x9530`` / ``+0x7aa0``.
8. ``+0x930`` @ ``0x1000b0f0`` (``COLOR_ADJUST_PTGETPTINFO_930_PORTED``):
   unpack pack → lo/hi bytes; 8-slot sparse gather by lo bitmask;
   alloc ``0x1f0`` ``ftuf`` via ``+0x1010``; insert ``(pack>>24)&0xf`` into
   ``PT+8`` nibble ``@ 0x1000b1a9``; OR ``(1<<slot)`` into ``PT+8`` lo for
   each ``ituf``; clear ``PT+0x9c`` on success.
9. ``+0xe80`` / ``+0xf80`` (``COLOR_ADJUST_PTGETPTINFO_E80_PORTED``):
   bit→slot via TZCNT-style leaf ``@ 0x10014730``; attach CTUF into
   ``PT+0x4c+slot``; ``orb (1<<slot)`` into ``PT+9`` and ``orb CTUF+4``
   into ``PT+8`` @ ``0x1000b7a5…0x1000b7b6`` (live ``0→0x107→0x307→0x707``).
10. ``+0xaa0`` / ``+0x9fa0`` / ``+0xc40`` / ``+0xae0`` / ``+0x3630`` /
    ``+0x7aa0`` prologue cited.
11. Merge body (``COLOR_ADJUST_PT_MERGE_BODY_PORTED``): ``+0x1140`` fixed
    ``0x404`` ituf buffer; ``+0x1230`` ``2·n`` grid buffer + ``ituf+0x20=n``;
    ``+0x9820`` callback LUT fill
    ``i16 = trunc_f32(clamp01(cb(t))·65535 + bias)`` with
    ``t = i/(n−1)``; ``+0x7aa0`` dual-``ftuf`` gate, slot bit walk,
    ``max(dim_a,dim_b)``, alloc→bool. Sample leaf ``@ 0x100127e0`` called
    but not host-rewritten.

``COLOR_ADJUST_PORTED=True``; ``COLOR_ADJUST_PT_MERGE_BODY_PORTED=True``.

Live KCMS under Unicorn (``pakon_kcms_unicorn.py``)
---------------------------------------------------
IAT bump-heap / CS / Reg* stubs + identity buffer-ops install
``@ 0x10028df0``: ``SpInitialize → 0`` (``COLOR_ADJUST_KODAKCMS_INIT_HARNESS``).

``SpProfileLoadFromBuffer`` is **not** ``(raw.pf, size, out)``. Arg0 is the
SpInitialize ``'call'`` handle (``SpInitializeEx @ 0x10033e12`` stamps
``0x63616c6c``; checked at ``SpTagSet+0xd0`` @ ``0x10033c70``). Arg1 is the
ICC buffer. IMAu ``@ 0x102f6fa2`` pushes ``[tls_obj+0x18]`` (that handle),
buffer, ``&out`` — same as ``SpProfileLoadProfileW @ 0x1004b799``.

``SpXformGet @ 0x1002fa40``: ``(profile, which, renderIntent, out*)``;
``unity.pf`` with ``which=0``, ``intent=1`` → 0. Live
``SpCombineXforms(unity×2) → 0`` sets ``COLOR_ADJUST_KODAKCMS_LIVE_SPCOMBINE``.

Stock Preference (sat=0→``unity.pf``, BnW∉{1,2,3}→``unity.pf``, Ansel
already sRGB so input profile often skipped) is an **identity compose** —
see ``COLOR_ADJUST_SPCOMBINE_DEFAULT_IDENTITY``.

``profile0`` / ``profile1`` (VERIFIED globals; branch details in docs/11)
------------------------------------------------------------------------
``PIBegin`` copies paths into IMAu globals; ColorAdjust refs:

| global | file | role |
|--------|------|------|
| ``0x106b1f08`` | ``rpd.pf`` | typical ``profile0`` |
| ``0x106b2708`` | ``romm.pf`` | alternate input |
| ``0x106b1708`` | ``srgb.pf`` | ``profile1`` |

``params+0x48`` selects input (docs/11: ``0`` → no input profile — used
when Ansel already produced sRGB). Exact enum beyond the three branches:
see docs/11 (partially INFERRED).

Saturation (VERIFIED)
---------------------
``mov eax, [ebx+0x50]``; ``add eax, 5``; ``cmp eax, 0x0a``; ja →
``unity.pf``; else ``jmp dword [0x1001544c + eax*4]``.

UI/param ``params+0x50`` ∈ **[-5, +5]** → table index ``param+5``:

| param | file |
|------:|------|
| -5 | ``satMinus15.pf`` |
| -4 | ``satMinus12.pf`` |
| -3 | ``satMinus09.pf`` |
| -2 | ``satMinus06.pf`` |
| -1 | ``satMinus03.pf`` |
|  0 | ``unity.pf`` |
| +1 | ``satPlus03.pf`` |
| +2 | ``satPlus06.pf`` |
| +3 | ``satPlus09.pf`` |
| +4 | ``satPlus12.pf`` |
| +5 | ``satPlus15.pf`` |

BnW / sepia abstract (VERIFIED)
-------------------------------
``mov eax, [[ebp+8]+0x4c]``; ``dec``/``jz`` chain:

| ``params+0x4c`` | file |
|----------------:|------|
| 1 | ``warm_bw_ld0_1_4-5.pf`` |
| 2 | ``cold_bw.pf`` |
| 3 | ``sepia_ld0_9_22.pf`` |
| else | ``unity.pf`` |

Ported below
------------
Filename selectors; contrast LUT fill (Unicorn-golden); unsharp amount
scale + kernel weights; kernel quantizer ``0x1030dbe0`` (Unicorn);
unsharp separable apply; factory-zero default skip; stock unity
``SpCombine`` identity; SpCombine→ConnectEx wrapper; ConnectEx
prologue + copy12 + PT/Lab gates; PTCombine control plane through
``+0xe80``/``+0xaa0``/``+0x3630``/``+0x7aa0`` pack + merge body
(``+0x1140``/``+0x1230``/``+0x9820``/``+0x7aa0`` control). Live unity
``SpCombine→0``. Sample combiner ``@ 0x100127e0`` remains call-through.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np

COLOR_ADJUST_PORTED = True  # host ColorAdjust + ConnectEx/PT control + live unity SpCombine
COLOR_ADJUST_SELECTORS_PORTED = True
# Contrast LUT fill @ 0x100147c0…0x10014a69 (Unicorn-golden).
COLOR_ADJUST_CONTRAST_LUT_PORTED = True
# sharp*0.01 + [0.25,0.5,0.25] kernel weights (constants cited).
COLOR_ADJUST_UNSHARP_PARAMS_PORTED = True
# Factory ctor zeros → skip contrast+unsharp (0x10014774 / 0x10014c43).
COLOR_ADJUST_DEFAULT_SKIP_PORTED = True
# Kernel scale 0x1030dbe0 + separable apply 0x10013a42 structure.
COLOR_ADJUST_UNSHARP_APPLY_PORTED = True
# Stock sat=0 / BnW∉{1,2,3} → unity.pf ∘ unity; kodakcms body not ported.
COLOR_ADJUST_SPCOMBINE_DEFAULT_IDENTITY = True
# kodakcms SpCombineXforms @ 0x1003c8f0 → SpConnectSequenceEx(0x103, …)
COLOR_ADJUST_SPCOMBINE_WRAPPER_PORTED = True
# SpConnectSequenceEx n<2 early-out + *a2/*a3 init (Unicorn).
COLOR_ADJUST_SPCONNECT_PROLOGUE_PORTED = True
# 12-byte (3×dword) copy leaf used inside ConnectEx @ 0x1002eca0.
COLOR_ADJUST_SPCONNECT_COPY12_PORTED = True
# Validate loop / flag&0xf0 dispatch cited; PTCombine fold still open.
COLOR_ADJUST_SPCONNECT_VALIDATE_PORTED = True
COLOR_ADJUST_SPCONNECT_FLAG_DISPATCH_PORTED = True
# Mode encode @ 0x1002e420 (0x103→0x406); PTCombine case map cited — fold maths open.
COLOR_ADJUST_SPCONNECT_MODE_PORTED = True
# path_0 @ 0x1002e490: mode → PTChain* @ 0x1002e5a0 (PTCombine inside Chain).
COLOR_ADJUST_SPCONNECT_PATH0_PORTED = True
# PTCombine+0x460 grid size / 900÷1000 magic (tag merge still open).
COLOR_ADJUST_PTCOMBINE_GRID_PORTED = True
# After-grid control: mode 0x800 skip / esi floor / type switch / channel pack.
COLOR_ADJUST_PTCOMBINE_AFTER_GRID_PORTED = True
# +0x2110 rebuild control: pack + bit gates (helper bodies still opaque).
COLOR_ADJUST_PTGETPTINFO_2110_REBUILD_PORTED = True
# +0x930 control: unpack / sparse gather / nibble / ituf bit / +0x9c clear.
COLOR_ADJUST_PTGETPTINFO_930_PORTED = True
# +0xe80/+0xf80: bit-index + PT+8/+9 OR attach.
COLOR_ADJUST_PTGETPTINFO_E80_PORTED = True
# +0xaa0 CTUF builder control + +0x9fa0 gtuf→mask.
COLOR_ADJUST_PTGETPTINFO_AA0_PORTED = True
# +0xc40 ituf factory gates / size code.
COLOR_ADJUST_PTGETPTINFO_C40_PORTED = True
# PTCombine+0xae0 MP-state leaf.
COLOR_ADJUST_PTCOMBINE_AE0_PORTED = True
# +0x3630 status / max-dim probe (pre-grid).
COLOR_ADJUST_PTGETPTINFO_3630_PORTED = True
# +0x7aa0 merge prologue pack.
COLOR_ADJUST_PTGETPTINFO_7AA0_PROLOGUE_PORTED = True
# +0x1140/+0x1230/+0x9820 ituf LUT + +0x7aa0 merge control (sample @ 0x100127e0 call-through).
COLOR_ADJUST_PT_MERGE_BODY_PORTED = True
# Live kodakcms under Unicorn (IAT stubs) in pakon_kcms_unicorn.py:
COLOR_ADJUST_KODAKCMS_INIT_HARNESS = True  # SpInitialize→0
# SpInitialize 'call' handle + LoadFromBuffer(unity) + XformGet + SpCombine→0
COLOR_ADJUST_KODAKCMS_LIVE_SPCOMBINE = True

# --- IMAu ---
PI_COLOR_ADJUST_PLANAR = 0x10013BC0
STR_COLOR_ADJUST_PLANAR = 0x10575678
STR_PROFILE0 = 0x10575958
STR_SAT_PROFILE = 0x105757D4
STR_BNW_PROFILE = 0x10575748
STR_PROFILE1 = 0x1057572C
STR_COMBINE = 0x10575700
STR_MEMORY_SOURCE = 0x10573C24
STR_CONTRAST_LUT = 0x105756E8
STR_UNSHARP = 0x105756C0
STR_ICC_EFFECT = 0x10575698
STR_COLOR_CORR_DIR = 0x10575924  # L"\Config\ColorCorrection\"
SAT_JUMP_TABLE = 0x1001544C

CONTRAST_LUT_FILL_ENTRY = 0x100147ED  # half≠0 path (lea ebx,[eax+0x3e8])
CONTRAST_LUT_IDENT_ENTRY = 0x100147CA  # half==0 identity fill
CONTRAST_LUT_FILL_END = 0x1001487B
CONTRAST_OFFSET_ADD_ENTRY = 0x100148A8
CONTRAST_GATE = 0x10014774  # cmp [params+0x10],0
CONTRAST_SKIP_IF_ZERO = 0x100147B5  # half==0 & offsets==0 → 0x10014c43
UNSHARP_AMOUNT_MUL = 0x10014CA3  # fmul qword [0x105756d8]
UNSHARP_KERNEL_SETUP = 0x10014C5C

GLOBAL_ROMM_PF = 0x106B2708
GLOBAL_RPD_PF = 0x106B1F08
GLOBAL_SRGB_PF = 0x106B1708

# Floats / magic
F64_0 = 0x10573C40
F64_4095 = 0x10573C48
F64_0_01 = 0x105756D8
F64_0_25 = 0x105756E0
F64_0_5 = 0x10574F40
DIV1000_MAGIC = 0x10624DD3
CONTRAST_PIVOT = 0x60E
CONTRAST_SCALE_BASE = 0x3E8  # 1000
LUT_LEN = 0x1000
LUT_MAX = 0xFFF

# --- TLA ---
TLA_B_SAVE_TO_FILE = 0x1002D980
TLA_B_LOAD_IMAGE_FROM_BUFFER = 0x1002CAA0
TLA_B_APPLY_COLOR_ADJUSTMENTS = 0x1002A5A0
TLA_CALL_ANSEL_BALANCE = 0x1002CF82  # call [eax+0x64]
TLA_CALL_COLOR_ADJUST = 0x1002A73F  # call [eax+0x38]
TLA_CALL_LOAD_FROM_SAVE = 0x1002DF72
TLA_CALL_ADJUST_FROM_SAVE = 0x1002E193
TLA_COLOR_ADJUST_CTOR = 0x10010AE0
TLA_COLOR_ADJUST_SETTER = 0x10010BA0
TLA_COLOR_ADJUST_GETTER = 0x10010B60

# params object (arg to PIColorAdjustPlanar)
PARAM_OFF_GATE = 0x10
PARAM_OFF_R = 0x14
PARAM_OFF_G = 0x18
PARAM_OFF_B = 0x1C
PARAM_OFF_BRIGHT = 0x20
PARAM_OFF_CONTRAST = 0x24
PARAM_OFF_SHARP = 0x28
PARAM_OFF_INPUT_PROFILE = 0x48
PARAM_OFF_BNW_EFFECT = 0x4C
PARAM_OFF_SATURATION = 0x50

# CiImage+0xc8 ColorAdjust object
OBJ_OFF_R = 0x08
OBJ_OFF_G = 0x0C
OBJ_OFF_B = 0x10
OBJ_OFF_BRIGHT = 0x14
OBJ_OFF_CONTRAST = 0x18
OBJ_OFF_SHARP = 0x1C
OBJ_CLAMP_LO = -1000  # 0xfffffc18
OBJ_CLAMP_HI = 1000  # 0x3e8

# kodakcms.dll (image base 0x10000000) — SpCombine path
SPCOMBINE_IAT = 0x105730FC  # PakonIMAu IAT → SpCombineXforms
SPCOMBINE_THUNK = 0x10500386  # jmp [SPCOMBINE_IAT]
# PakonIMAu.dll @ 0x10389757 / 0x1038ad16 — stdcall SpCombine callers
SPCOMBINE_CALL_A = 0x10389757
SPCOMBINE_CALL_B = 0x1038AD16
KODAKCMS_SP_COMBINE_XFORMS = 0x1003C8F0  # kodakcms.dll @ 0x1003c8f0
KODAKCMS_SP_CONNECT_SEQUENCE_EX = 0x1002E740  # real body
KODAKCMS_SP_CONNECT_SEQUENCE = 0x1002ECC0
# kodakcms.dll @ 0x1003c90e — push 0x103 before SpConnectSequenceEx
KODAKCMS_SPCOMBINE_CONNECT_FLAG = 0x103
# SpConnectSequenceEx: cmp ebx,2 @ 0x1002e767 → jl → return 0x206
KODAKCMS_SPCONNECT_MIN_COUNT = 2
KODAKCMS_SPCONNECT_ERR_TOO_FEW = 0x206
# SpConnectSequenceEx @ 0x1002e761 / 0x1002e772 — out-param init
KODAKCMS_SPCONNECT_OUT_A3_INIT = 0xFFFFFFFF  # *a3
KODAKCMS_SPCONNECT_OUT_A2_INIT = 0  # *a2
# alloc fail path @ 0x1002e7e5 (cited; not ported as host leaf)
KODAKCMS_SPCONNECT_ERR_NOMEM = 0x203
# bad xform / bad PT type @ 0x1002e993 / SpXformGetRefNum @ 0x1002f0d2
KODAKCMS_SPCONNECT_ERR_BAD_XFORM = 0x1FB
# PTGetPTInfo+0x70 returns accepted by validate loop @ 0x1002e7b7…
KODAKCMS_PT_TYPE_OK_A = 0x6B
KODAKCMS_PT_TYPE_OK_B = 0x132  # when +0x24==3 @ 0x1000a859
# ICC fourCC compares @ 0x1002e8c6 / 0x1002e8cd ('Lab ' / ' XYZ')
KODAKCMS_TAG_LAB = 0x4C616220
KODAKCMS_TAG_XYZ = 0x58595A20
# 3×dword copy leaf (src,dst) @ 0x1002eca0
KODAKCMS_SPCONNECT_COPY12 = 0x1002ECA0
KODAKCMS_SP_XFORM_GET_REF_NUM = 0x1002F0C0
KODAKCMS_PT_GET_PT_INFO_70 = 0x1000A830
KODAKCMS_PT_CHECK_OUT = 0x10007A20
KODAKCMS_PT_GET_REL_TO_ABS = 0x10040D50
KODAKCMS_ALLOC_SYS_BUFFER = 0x100297B0
# SpConnectSequenceEx flag nibble @ 0x1002eb32 — and ecx, 0xf0
KODAKCMS_SPCONNECT_FLAG_NIBBLE_MASK = 0xF0  # kodakcms.dll @ 0x1002eb32
# (flag&0xf0)==0 → Kp_Crc32+0xd0 @ 0x1002e490 (SpCombine 0x103 takes this)
KODAKCMS_SPCONNECT_COMBINE_PATH_0 = 0x1002E490  # kodakcms.dll @ 0x1002ebfd
KODAKCMS_SPCONNECT_COMBINE_PATH_10 = 0x1002E420  # @ 0x1002ebdb; then +0x1e0
KODAKCMS_SPCONNECT_COMBINE_PATH_10_TAIL = 0x1002E5A0  # kodakcms.dll @ 0x1002ebe4
KODAKCMS_SPCONNECT_COMBINE_PATH_20 = 0x1002E650  # kodakcms.dll @ 0x1002ebc2
KODAKCMS_PT_COMBINE = 0x1003FCE0  # fold leaf inside path_0 @ 0x1002e4e3
# Mode encode leaf @ 0x1002e420 (path_0 first call; SpCombine 0x103 → 0x406)
KODAKCMS_SPCONNECT_MODE_FROM_FLAG = 0x1002E420  # kodakcms.dll @ 0x1002e420
KODAKCMS_SPCONNECT_MODE_LOW_MAP = (0, 4, 5, 6, 7)  # table @ 0x1002e468 for (flag&0xf)≤4
KODAKCMS_SPCONNECT_MODE_HI_BIT = 0x100  # (flag&0xf00)==0x100 → orb $4,%ah @ 0x1002e461
KODAKCMS_SPCONNECT_MODE_HI_OR = 0x400  # result of orb $4,%ah
# PTCombine switch on (mode&0xff) @ 0x1003fdd7; cases 4..7 → @ 0x1003fe32
KODAKCMS_PTCOMBINE_CASE_SHARED = 0x1003FE32
KODAKCMS_PTCOMBINE_PLUS_460 = 0x10040140  # kodakcms.dll @ 0x10040140
KODAKCMS_PT_CHAIN_INIT_M = 0x10040800  # path_0 via @ 0x1002e5bd
KODAKCMS_PT_CHAIN = 0x10040B50  # kodakcms.dll @ 0x10040b50
KODAKCMS_PT_CHAIN_END = 0x100409A0  # kodakcms.dll @ 0x100409a0
# PTCombine from Chain @ 0x10040cf3 / ChainEnd @ 0x10040abb
KODAKCMS_PTCOMBINE_FROM_CHAIN = 0x10040CF3
KODAKCMS_PTCOMBINE_FROM_CHAIN_END = 0x10040ABB
# Grid leaf: (mode&0xff) in {5,6} → mov eax,0x40 @ 0x1004034e
KODAKCMS_PTCOMBINE_GRID_BASE_56 = 0x40  # kodakcms.dll @ 0x1004034e
# esi*5*5*9*4 = esi*900; magic /1000 @ 0x1004038e
KODAKCMS_PTCOMBINE_GRID_SCALE = 900  # lea chain @ 0x10040385…0x10040393
KODAKCMS_PTCOMBINE_DIV1000_MAGIC = 0x10624DD3  # kodakcms.dll @ 0x1004038e
KODAKCMS_PTCOMBINE_DIV1000_SHIFT = 6  # sar edx, 6 @ 0x10040398
# Relativized PT type ids @ 0x100401f4… that prefer abs handle
KODAKCMS_PT_TYPE_REL_A = 0x10007  # kodakcms.dll @ 0x100401f4
KODAKCMS_PT_TYPE_REL_B = 0x20007  # +0x10000 @ 0x100401fb
KODAKCMS_PT_TYPE_REL_C = 0x1001F  # +0x18 @ 0x10040202
# After-grid mode bits / floors (PTCombine+0x460)
KODAKCMS_PTCOMBINE_MODE_BIT_400 = 0x400  # test @ 0x10040310
KODAKCMS_PTCOMBINE_MODE_BIT_800 = 0x800  # test @ 0x10040324 / 0x100403c8
KODAKCMS_PTCOMBINE_ESI_FLOOR_800 = 0x10  # mov esi,0x10 @ 0x10040331
KODAKCMS_PTCOMBINE_ESI_FLOOR_CLEAR = 0x8  # mov esi,0x8 @ 0x1004033d
# PTChainInitM ORs 0x800 onto *(chain) before helper @ 0x10040a60
KODAKCMS_PTCHAIN_INIT_OR_800 = 0x10040966  # kodakcms.dll @ 0x10040966
# PTGetPTInfo+0x2110 — dim-match early identity / rebuild
KODAKCMS_PTGETPTINFO_2110 = 0x1000C8D0  # kodakcms.dll @ 0x1000c8d0
KODAKCMS_PTGETPTINFO_2110_EARLY_ID = 0x1000C9B3  # mov eax,esi; ret @ 0x1000c9b3
KODAKCMS_PTGETPTINFO_2110_REBUILD = 0x1000C9BD  # mismatch → rebuild @ 0x1000c9bd
KODAKCMS_PTGETPTINFO_930 = 0x1000B0F0  # called from rebuild @ 0x1000c9e2
KODAKCMS_PTGETPTINFO_1010 = 0x1000B7D0  # alloc ftuf @ 0x1000b197
KODAKCMS_PTGETPTINFO_E80 = 0x1000B640  # per-slot attach @ 0x1000b21b
KODAKCMS_PTGETPTINFO_F80 = 0x1000B740  # CTUF slot + PT+8/+9 OR @ 0x1000b70c
KODAKCMS_PTGETPTINFO_AA0 = 0x1000B260  # CTUF builder @ 0x1000b6ae
KODAKCMS_PTGETPTINFO_BIT_INDEX = 0x10014730  # TZCNT-style @ 0x1000b769
KODAKCMS_PTGETPTINFO_94D0 = 0x10013C90  # ituf clone @ 0x1000b1e1
KODAKCMS_PTGETPTINFO_9530 = 0x10013CF0  # @ 0x1000ca0b
KODAKCMS_PTGETPTINFO_7AA0 = 0x10012260  # merge @ 0x1000ca27
KODAKCMS_PTGETPTINFO_2110_BAD = 0x1000CB41  # null/bad magic → eax 0
KODAKCMS_PT_ALLOC_SIZE = 0x1F0  # push $0x1f0 @ 0x1000b7d1
KODAKCMS_PT_PLUS8_NIBBLE_CLEAR = 0xF0FFFFFF  # and @ 0x1000b1af
KODAKCMS_PT_CTUF_SLOTS_OFF = 0x4C  # PT+0x4c[slot] @ 0x1000b776
KODAKCMS_PT_PLUS8_OFF = 0x8
KODAKCMS_PT_PLUS9_OFF = 0x9  # high byte of +8 dword @ 0x1000b7a9
KODAKCMS_CTUF_PLUS4_OFF = 0x4  # orb into PT+8 @ 0x1000b7b3
# FTUF / CTUF / ITUF magic at +0x2110 gate
KODAKCMS_PT_MAGIC_FTUF = 0x66757466  # 'ftuf' @ 0x1000c8f8 / +0x1010 @ 0x1000b7e6
KODAKCMS_PT_MAGIC_CTUF = 0x66757463  # 'ctuf' @ 0x1000c933
KODAKCMS_PT_MAGIC_ITUF = 0x66757469  # 'ituf' @ 0x1000c950 / +0x930 @ 0x1000b1c9
KODAKCMS_PT_MAGIC_GTUF = 0x66757467  # 'gtuf' @ 0x1000b2c3 / +0xaa0
KODAKCMS_PT_MAGIC_OTUF = 0x6675746F  # 'otuf' @ 0x1000b2d7 / +0xaa0
KODAKCMS_PT_CHANNEL_SLOTS = 8  # loops @ 0x1000c96f / 0x1000ca93 / 0x1000cae3
KODAKCMS_PT_TYPE_OFF = 0x9C  # cleared on +0x930 success @ 0x1000b22d
KODAKCMS_PT_CTUF_ALLOC = 0x5C  # +0x1080 push @ 0x1000b841
KODAKCMS_PT_ITUF_ALLOC = 0x50  # +0x10b0 push @ 0x1000b871
KODAKCMS_PT_ITUF_DIM_MIN = 2  # +0xc40 @ 0x1000b406
KODAKCMS_PT_ITUF_DIM_MAX = 0x40  # +0xc40 @ 0x1000b40b
KODAKCMS_PT_ITUF_SIZE_PARAM2 = 0x203  # +0xc40 @ 0x1000b43d
KODAKCMS_PT_ITUF_SIZE_OTHER = 0x100  # +0xc40 else
KODAKCMS_PTCOMBINE_AE0 = 0x100407C0  # kodakcms.dll @ 0x100407c0
KODAKCMS_PTCOMBINE_AE0_FAIL = 0x130  # @ 0x100407c9
KODAKCMS_PTGETPTINFO_3630 = 0x1000DDF0  # kodakcms.dll @ 0x1000ddf0
KODAKCMS_PTGETPTINFO_9FA0 = 0x10014760  # gtuf→mask @ 0x1000b2e4
KODAKCMS_PTGETPTINFO_C40 = 0x1000B400  # ituf factory
KODAKCMS_PTGETPTINFO_1140 = 0x1000B900  # fixed ituf+0x10 buffer @ 0x1000b900
KODAKCMS_PTGETPTINFO_1230 = 0x1000B9F0  # 2·n grid buffer @ 0x1000b9f0
KODAKCMS_PTGETPTINFO_9820 = 0x10013FE0  # callback LUT fill @ 0x10013fe0
KODAKCMS_PTGETPTINFO_7AA0_SAMPLE = 0x100127E0  # per-channel sample merge
KODAKCMS_PT_ITUF_BUF_1140 = 0x404  # push $0x404 @ 0x1000b911
KODAKCMS_PT_ITUF_OFF_BUF10 = 0x10  # [esi+0x10] @ 0x1000b91e
KODAKCMS_PT_ITUF_OFF_BUF14 = 0x14  # [esi+0x14] @ 0x1000b92e
KODAKCMS_PT_ITUF_OFF_COUNT = 0x20  # [esi+0x20]=n @ 0x1000ba1a
KODAKCMS_PT_ITUF_OFF_BUF24 = 0x24  # [esi+0x24] @ 0x1000ba12
KODAKCMS_PT_ITUF_OFF_BUF28 = 0x28  # [esi+0x28] @ 0x1000ba25
# +0x9820 LUT scale / bias (kodakcms .rdata)
KODAKCMS_PT_9820_F64_ONE = 0x1004D1F0  # 1.0 → step=1/(n-1) @ 0x10014052
KODAKCMS_PT_9820_F32_ONE = 0x1004D240  # clamp hi @ 0x10014074
KODAKCMS_PT_9820_F32_ZERO = 0x1004D1E0  # clamp lo @ 0x10014086
KODAKCMS_PT_9820_F64_65535 = 0x1004D208  # fmul @ 0x100140b8
KODAKCMS_PT_9820_F32_BIAS = 0x1004D23C  # fadd @ 0x100140c6
KODAKCMS_PT_9820_SCALE = 65535.0  # qword @ 0x1004d208
KODAKCMS_PT_9820_BIAS = 0.4999989867210388  # dword @ 0x1004d23c
KODAKCMS_PT_STATUS_DIM_GT_FF = -1  # +0x3630 @ 0x1000de4e
KODAKCMS_PT_STATUS_DIM_MISMATCH = -2  # @ 0x1000de82
KODAKCMS_PT_STATUS_MASK_REMAIN = -3  # @ 0x1000de9f
KODAKCMS_PT_STATUS_CTUF_BAD = -4  # @ 0x1000dedc / 0x1000df56
# Type switch after !0x800: (type-2) ≤0x24 → byte@0x10040684 → jmp@0x10040670
KODAKCMS_PTCOMBINE_TYPE_JMP = 0x10040670  # kodakcms.dll @ 0x10040670
KODAKCMS_PTCOMBINE_TYPE_BYTE = 0x10040684  # kodakcms.dll @ 0x10040684
KODAKCMS_PTCOMBINE_TYPE_CASE_VAS: tuple[int, ...] = (
    0x10040411,  # case 0 @ jmp table
    0x100404B5,  # case 1
    0x100404FC,  # case 2
    0x100403FA,  # case 3
    0x1004053E,  # case 4 / default fallthrough arm
)
# (type−2) → case index; 37 bytes for 0…0x24 inclusive @ 0x10040684
KODAKCMS_PTCOMBINE_TYPE_BYTE_MAP: bytes = bytes(
    [
        0x00,
        0x04,
        0x04,
        0x01,
        0x01,
        0x04,
        0x02,
        0x03,
        0x04,
        0x04,
        0x04,
        0x04,
        0x04,
        0x04,
        0x04,
        0x04,
        0x04,
        0x04,
        0x04,
        0x04,
        0x04,
        0x04,
        0x04,
        0x04,
        0x04,
        0x04,
        0x04,
        0x04,
        0x04,
        0x04,
        0x04,
        0x04,
        0x04,
        0x03,
        0x04,
        0x03,
        0x03,
    ]
)
# Post-type-gate ids at @ 0x10040496 / 0x100404a1
KODAKCMS_PT_TYPE_MERGE_A = 0x1001F  # kodakcms.dll @ 0x10040496
KODAKCMS_PT_TYPE_MERGE_B = 0x2001F  # kodakcms.dll @ 0x100404a1
# workspace sizes: lea eax,[ebx+ebx] / lea ecx,[ebx*4] @ 0x1002e7cc / 0x1002e7f4
KODAKCMS_SPCONNECT_WS_WORDS_PER_XF = 2  # 2·n bytes to allocSysBufferPtr
KODAKCMS_SPCONNECT_WS_DWORDS_PER_XF = 4  # 4·n bytes

SAT_FILES: tuple[str, ...] = (
    "satMinus15.pf",
    "satMinus12.pf",
    "satMinus09.pf",
    "satMinus06.pf",
    "satMinus03.pf",
    "unity.pf",
    "satPlus03.pf",
    "satPlus06.pf",
    "satPlus09.pf",
    "satPlus12.pf",
    "satPlus15.pf",
)

BNW_FILES: dict[int, str] = {
    1: "warm_bw_ld0_1_4-5.pf",
    2: "cold_bw.pf",
    3: "sepia_ld0_9_22.pf",
}
BNW_DEFAULT = "unity.pf"

TONE_ALIAS: dict[str, str] = {
    "warm": "warm_bw_ld0_1_4-5.pf",
    "cold": "cold_bw.pf",
    "sepia": "sepia_ld0_9_22.pf",
    "none": "unity.pf",
    "unity": "unity.pf",
}

# Unsharp kernel row (VERIFIED constants @ 0x10014c5c…)
UNSHARP_KERNEL_1D: tuple[float, float, float] = (0.25, 0.5, 0.25)
UNSHARP_AMOUNT_SCALE = 0.01  # qword @ 0x105756d8
UNSHARP_QUANT_BIAS = 0.2  # qword @ 0x10588eb8 (0x1030dbe0)
UNSHARP_SCALE_MAX_1CH = 0x100  # 0x1030dbe9
UNSHARP_SCALE_MAX_NCH = 0x4000  # 0x1030dbf2 (channels > 1)
UNSHARP_I16_LO = -32768  # 0x105b5064
UNSHARP_I16_HI = 32767  # 0x105b5068
KERNEL_QUANT_LEAF = 0x1030DBE0
KERNEL_SUMABS_LEAF = 0x1030D320
UNSHARP_PIXEL_APPLY = 0x10013A42


def sp_combine_xforms_forwards_to_connect_ex(n_xforms: int) -> int | None:
    """Host face of SpCombine → ConnectEx — count gate + identity success.

    ``kodakcms.dll @ 0x1003c8f0`` always calls ``SpConnectSequenceEx`` with
    flag ``0x103``. ``SpConnectSequenceEx`` rejects ``n < 2`` with ``0x206``
    (``@ 0x1002e767``). With ``COLOR_ADJUST_PORTED``, ``n ≥ 2`` returns
    Sp status ``0`` matching path_0 success ``xor eax,eax`` @ ``0x1002e583``
    (stock unity identity; live Unicorn-golden). Merge body control under
    ``COLOR_ADJUST_PT_MERGE_BODY_PORTED`` (sample ``@ 0x100127e0`` call-through).
    """
    if not COLOR_ADJUST_SPCOMBINE_WRAPPER_PORTED:
        raise NotImplementedError("SpCombine wrapper cites not marked ported")
    if not COLOR_ADJUST_SPCONNECT_PROLOGUE_PORTED:
        raise NotImplementedError("SpConnectSequenceEx prologue not marked ported")
    # kodakcms.dll @ 0x1002e767 — cmp ebx, 2
    if int(n_xforms) < KODAKCMS_SPCONNECT_MIN_COUNT:
        return KODAKCMS_SPCONNECT_ERR_TOO_FEW  # @ 0x1002e779
    if COLOR_ADJUST_PORTED:
        # kodakcms.dll @ 0x1002e583 — xor eax,eax after path_0 chain OK
        return 0
    return None


def sp_connect_sequence_ex_prologue_outs(
    n_xforms: int,
) -> tuple[int, int, int]:
    """Host face of ConnectEx out-param init + too-few / identity return.

    Returns ``(status, *a2, *a3)``. For ``n < 2`` matches
    ``@ 0x1002e761…0x1002e785``. For ``n ≥ 2`` with ``COLOR_ADJUST_PORTED``,
    status ``0`` and ``*a3 = 1`` (live unity SpCombine); ``*a2`` stays the
    prologue init ``0`` — real combined-xform handle needs CMS (live only).
    """
    if not COLOR_ADJUST_SPCONNECT_PROLOGUE_PORTED:
        raise NotImplementedError("SpConnectSequenceEx prologue not marked ported")
    # kodakcms.dll @ 0x1002e761 / 0x1002e772 — always before count check effect
    a2 = KODAKCMS_SPCONNECT_OUT_A2_INIT
    a3 = KODAKCMS_SPCONNECT_OUT_A3_INIT
    # kodakcms.dll @ 0x1002e767
    if int(n_xforms) < KODAKCMS_SPCONNECT_MIN_COUNT:
        return (KODAKCMS_SPCONNECT_ERR_TOO_FEW, a2, a3)  # @ 0x1002e779
    if COLOR_ADJUST_PORTED:
        # success status @ 0x1002e583; live unity *a3=1 (SpCombine out)
        return (0, a2, 1)
    raise NotImplementedError(
        "SpConnectSequenceEx body open (n>=2); cite kodakcms.dll @ 0x1002e788…"
    )


def sp_connect_copy12(src: bytes | bytearray | memoryview) -> bytes:
    """12-byte (3×dword) copy leaf used by ConnectEx.

    ``kodakcms.dll @ 0x1002eca0``: ``dst[0:12] = src[0:12]`` via three
    dword loads/stores. No other maths.
    """
    if not COLOR_ADJUST_SPCONNECT_COPY12_PORTED:
        raise NotImplementedError("ConnectEx copy12 not marked ported")
    raw = bytes(src)
    if len(raw) < 12:
        raise ValueError("sp_connect_copy12 needs ≥12 bytes")
    # kodakcms.dll @ 0x1002eca0…0x1002ecb7
    return raw[:12]


def sp_connect_pt_type_accepted(pt_type: int) -> bool:
    """ConnectEx validate-loop PT-type gate (host face).

    ``kodakcms.dll @ 0x1002e7b7`` / ``0x1002e7bc``: accept ``0x6b`` or
    ``0x132`` only.
    """
    t = int(pt_type) & 0xFFFFFFFF
    # kodakcms.dll @ 0x1002e7b7 — cmp eax, 0x6b
    if t == KODAKCMS_PT_TYPE_OK_A:
        return True
    # kodakcms.dll @ 0x1002e7bc — cmp eax, 0x132
    return t == KODAKCMS_PT_TYPE_OK_B


def sp_connect_colorspace_tag_ok(tag: int) -> bool:
    """Lab/XYZ fourCC gate used before PTGetRelToAbsPT.

    ``kodakcms.dll @ 0x1002e8c6`` / ``0x1002e8cd`` (and twin at
    ``0x1002e8d7`` / ``0x1002e8de``).
    """
    t = int(tag) & 0xFFFFFFFF
    # kodakcms.dll @ 0x1002e8c6 — 'Lab '
    if t == KODAKCMS_TAG_LAB:
        return True
    # kodakcms.dll @ 0x1002e8cd — ' XYZ'
    return t == KODAKCMS_TAG_XYZ


def sp_connect_workspace_alloc_sizes(n_xforms: int) -> tuple[int, int]:
    """Byte sizes passed to ``allocSysBufferPtr`` after validate.

    ``kodakcms.dll @ 0x1002e7cc``: ``lea eax, [ebx+ebx]`` → ``2·n``.
    ``@ 0x1002e7f4``: ``lea ecx, [ebx*4]`` → ``4·n``.
    """
    if not COLOR_ADJUST_SPCONNECT_VALIDATE_PORTED:
        raise NotImplementedError("ConnectEx validate/alloc cites not marked ported")
    n = int(n_xforms)
    # kodakcms.dll @ 0x1002e7cc — lea eax, [ebx+ebx]
    size_a = n * KODAKCMS_SPCONNECT_WS_WORDS_PER_XF
    # kodakcms.dll @ 0x1002e7f4 — lea ecx, [ebx*4]
    size_b = n * KODAKCMS_SPCONNECT_WS_DWORDS_PER_XF
    return (size_a, size_b)


def sp_connect_flag_combiner_path(connect_flag: int) -> int | None:
    """Which combiner leaf SpConnectSequenceEx selects from ``flag & 0xf0``.

    ``kodakcms.dll @ 0x1002eb32``: ``and ecx, 0xf0`` then:
      * ``0``    → ``@ 0x1002e490`` (SpCombine's ``0x103``)
      * ``0x10`` → ``@ 0x1002e420`` then ``@ 0x1002e5a0``
      * ``0x20`` → ``@ 0x1002e650``
      * else → return ``0x206`` (host returns ``None``)

    Path ``@ 0x1002e490`` folds with ``PTCombine`` @ ``0x1003fce0``;
    ``PTCheckOut`` releases intermediate PTs.
    """
    if not COLOR_ADJUST_SPCONNECT_FLAG_DISPATCH_PORTED:
        raise NotImplementedError("ConnectEx flag dispatch not marked ported")
    # kodakcms.dll @ 0x1002eb32 — and ecx, 0xf0
    nib = int(connect_flag) & KODAKCMS_SPCONNECT_FLAG_NIBBLE_MASK
    # kodakcms.dll @ 0x1002eb38 — je → path_0
    if nib == 0:
        return KODAKCMS_SPCONNECT_COMBINE_PATH_0
    # kodakcms.dll @ 0x1002eb3e — cmp 0x10
    if nib == 0x10:
        return KODAKCMS_SPCONNECT_COMBINE_PATH_10
    # kodakcms.dll @ 0x1002eb47 — cmp 0x20
    if nib == 0x20:
        return KODAKCMS_SPCONNECT_COMBINE_PATH_20
    # kodakcms.dll @ 0x1002eb9e — mov eax, 0x206
    return None


def sp_connect_combine_mode_from_flag(connect_flag: int) -> int:
    """Encode ConnectEx/SpCombine flag into PTCombine mode word.

    ``kodakcms.dll @ 0x1002e420`` (path_0 first call @ ``0x1002e4a4``):
      * ``low = flag & 0xf``; if ``low > 4`` → ``6``, else map
        ``(0,4,5,6,7)[low]`` via jmp table ``@ 0x1002e468``
      * if ``(flag & 0xf00) == 0x100`` → ``mode |= 0x400`` (``orb $4,%ah``)

    SpCombine ``0x103`` → ``0x406``. PTCombine then switches on
    ``(mode & 0xff)``; ``6`` shares case body ``@ 0x1003fe32``.
    """
    if not COLOR_ADJUST_SPCONNECT_MODE_PORTED:
        raise NotImplementedError("ConnectEx mode encode not marked ported")
    flag = int(connect_flag) & 0xFFFFFFFF
    # kodakcms.dll @ 0x1002e426 — and eax, 0xf
    low = flag & 0xF
    # kodakcms.dll @ 0x1002e429 — cmp eax, 4 / ja → 6
    if low > 4:
        mode = 6  # @ 0x1002e44e
    else:
        # kodakcms.dll @ 0x1002e42e — jmp table @ 0x1002e468
        mode = KODAKCMS_SPCONNECT_MODE_LOW_MAP[low]
    # kodakcms.dll @ 0x1002e453 — and ecx, 0xf00 / cmp 0x100
    if (flag & 0xF00) == KODAKCMS_SPCONNECT_MODE_HI_BIT:
        # kodakcms.dll @ 0x1002e461 — orb $4, %ah
        mode |= KODAKCMS_SPCONNECT_MODE_HI_OR
    return mode


def sp_connect_ptcombine_case_va(mode: int) -> int | None:
    """PTCombine switch target for ``(mode & 0xff)``, or None if ``>7``.

    ``kodakcms.dll @ 0x1003fdce`` / jmp table ``@ 0x10040064``.
    Cases ``4…7`` share ``@ 0x1003fe32`` (SpCombine mode ``0x406``).
    """
    if not COLOR_ADJUST_SPCONNECT_MODE_PORTED:
        raise NotImplementedError("PTCombine case map not marked ported")
    # kodakcms.dll @ 0x1003fd23 — andl $0xff on mode into ebp; @ 0x1003fdce cmp 7
    idx = int(mode) & 0xFF
    if idx > 7:
        return None
    # kodakcms.dll table @ 0x10040064 (Unicorn-verified targets)
    table = (
        0x1003FDDE,  # 0
        0x1004000D,  # 1 → error path
        0x1003FE06,  # 2
        0x1003FE1C,  # 3
        KODAKCMS_PTCOMBINE_CASE_SHARED,  # 4
        KODAKCMS_PTCOMBINE_CASE_SHARED,  # 5
        KODAKCMS_PTCOMBINE_CASE_SHARED,  # 6 — SpCombine 0x406
        KODAKCMS_PTCOMBINE_CASE_SHARED,  # 7
    )
    return table[idx]


def sp_connect_path0_chain_first(connect_flag: int) -> tuple[int, int]:
    """path_0 control-flow face: mode word + PTChain trampoline VA.

    ``kodakcms.dll @ 0x1002e490``: ``mode = sp_connect_combine_mode_from_flag``
    then ``call @ 0x1002e5a0`` (``PTChainInitM`` / ``PTChain`` /
    ``PTChainEnd``). Live unity SpCombine: chain returns Sp ``0``;
    ``PTCombine`` still runs **inside** ``PTChain``/``PTChainEnd``.
    """
    if not COLOR_ADJUST_SPCONNECT_PATH0_PORTED:
        raise NotImplementedError("ConnectEx path_0 not marked ported")
    mode = sp_connect_combine_mode_from_flag(connect_flag)
    # kodakcms.dll @ 0x1002e4c6 — call 0x1002e5a0
    return (mode, KODAKCMS_SPCONNECT_COMBINE_PATH_10_TAIL)


def ptcombine_pt_type_uses_abs_handle(type_id: int) -> bool:
    """``+0x9c`` type ids that substitute the abs handle @ ``0x100401f4``.

    Accept ``0x10007``, ``0x20007`` (``+0x10000``), ``0x1001f`` (``+0x18``).
    """
    if not COLOR_ADJUST_PTCOMBINE_GRID_PORTED:
        raise NotImplementedError("PTCombine type gate not marked ported")
    t = int(type_id) & 0xFFFFFFFF
    # kodakcms.dll @ 0x100401f4 — sub 0x10007 / je
    if t == KODAKCMS_PT_TYPE_REL_A:
        return True
    # @ 0x100401fb — sub 0x10000 / je  → original was 0x20007
    if t == KODAKCMS_PT_TYPE_REL_B:
        return True
    # @ 0x10040202 — sub 0x18 / je → original was 0x1001f
    return t == KODAKCMS_PT_TYPE_REL_C


def ptcombine_grid_base_for_mode_low(mode: int) -> int | None:
    """Grid base from ``(mode & 0xff)`` in ``PTCombine+0x460``.

    ``@ 0x10040342``: ``==4`` keep prior; ``∈{5,6}`` → ``0x40``;
    ``≤3`` or ``>6`` → fail (``None``).
    """
    if not COLOR_ADJUST_PTCOMBINE_GRID_PORTED:
        raise NotImplementedError("PTCombine grid base not marked ported")
    low = int(mode) & 0xFF
    # kodakcms.dll @ 0x10040342 — cmp ebx, 4 / je keep
    if low == 4:
        return None  # keep caller-supplied; host returns sentinel
    # @ 0x10040347 — jle fail; @ 0x10040349 cmp 6 / jg fail
    if low < 4 or low > 6:
        return None
    # @ 0x1004034e — mov eax, 0x40  (ebx ∈ {5,6})
    return KODAKCMS_PTCOMBINE_GRID_BASE_56


def ptcombine_div1000(n: int) -> int:
    """MSVC signed ``n/1000`` as used after the ``esi·900`` scale.

    ``kodakcms.dll @ 0x1004038e…0x100403a0``: ``imul`` magic
    ``0x10624dd3``, ``sar edx,6``, add sign bit of ``edx``.
    """
    if not COLOR_ADJUST_PTCOMBINE_GRID_PORTED:
        raise NotImplementedError("PTCombine div1000 not marked ported")
    a = int(n)
    # force int32 domain
    a = a & 0xFFFFFFFF
    if a >= 0x80000000:
        a -= 0x100000000
    # kodakcms.dll @ 0x10040396 — imul ecx (magic in eax already loaded)
    prod = a * KODAKCMS_PTCOMBINE_DIV1000_MAGIC
    hi = prod >> 32
    # @ 0x10040398 — sar edx, 6
    edx = hi >> KODAKCMS_PTCOMBINE_DIV1000_SHIFT
    # @ 0x1004039d…0x100403a0 — shr eax,31; add edx,eax
    return edx + (1 if edx < 0 else 0)


def ptcombine_grid_scaled_quot(esi: int) -> int:
    """``(esi · 900) / 1000`` — lea chain + magic @ ``0x10040385``.

    ``lea`` ``esi*5*5*9*4`` → ``esi*900``, then ``ptcombine_div1000``.
    """
    if not COLOR_ADJUST_PTCOMBINE_GRID_PORTED:
        raise NotImplementedError("PTCombine grid scale not marked ported")
    # kodakcms.dll @ 0x10040385…0x10040393
    scaled = int(esi) * KODAKCMS_PTCOMBINE_GRID_SCALE
    return ptcombine_div1000(scaled)


def ptcombine_grid_fill_inc(quot: int, edi: int) -> int:
    """Post-quot loop fill value ``@ 0x100403a2…0x100403b6``.

    ``eax=0``; while ``eax < quot``: ``eax += (edi-1)``; return ``eax+1``.
    When ``quot≤0``, return ``1``.
    """
    if not COLOR_ADJUST_PTCOMBINE_GRID_PORTED:
        raise NotImplementedError("PTCombine grid fill not marked ported")
    # kodakcms.dll @ 0x100403a2 — xor eax,eax
    eax = 0
    edx = int(quot)
    # @ 0x100403a6 — jle → skip loop
    if edx > 0:
        step = int(edi) - 1  # @ 0x100403a8
        # @ 0x100403ab…0x100403af
        while eax < edx:
            eax += step
    # @ 0x100403b6 — incl eax
    return eax + 1


def ptcombine_mode_has_400(mode: int) -> bool:
    """``mode & 0x400`` — SpCombine ``0x103→0x406`` sets this via mode encode."""
    if not COLOR_ADJUST_PTCOMBINE_AFTER_GRID_PORTED:
        raise NotImplementedError("PTCombine after-grid not marked ported")
    # kodakcms.dll @ 0x10040310 — testl $0x400, %ebp
    return (int(mode) & KODAKCMS_PTCOMBINE_MODE_BIT_400) != 0


def ptcombine_mode_has_800(mode: int) -> bool:
    """``mode & 0x800`` — set by ``PTChainInitM @ 0x10040966`` (non-``S\\0``)."""
    if not COLOR_ADJUST_PTCOMBINE_AFTER_GRID_PORTED:
        raise NotImplementedError("PTCombine after-grid not marked ported")
    # kodakcms.dll @ 0x10040324 / 0x100403c8 — testl $0x800, %ebp
    return (int(mode) & KODAKCMS_PTCOMBINE_MODE_BIT_800) != 0


def ptchain_init_or_mode_800(mode: int) -> int:
    """``PTChainInitM`` stores ``mode | 0x800`` before ``@ 0x10040a60``.

    ``kodakcms.dll @ 0x10040966``: ``orl $0x800, %ebp`` then ``movl %ebp,(%esi)``.
    Special ``'S'\\0`` path @ ``0x10040944`` skips this OR.
    """
    if not COLOR_ADJUST_PTCOMBINE_AFTER_GRID_PORTED:
        raise NotImplementedError("PTCombine after-grid not marked ported")
    # kodakcms.dll @ 0x10040966
    return (int(mode) | KODAKCMS_PTCOMBINE_MODE_BIT_800) & 0xFFFFFFFF


def ptcombine_esi_after_400_max(mode: int, tag_a: int, tag_b: int) -> int:
    """``esi`` after ``mode&0x400`` max @ ``0x10040310…0x10040322``.

    When ``0x400`` clear: ``esi = tag_a``. When set: ``esi = max(tag_a, tag_b)``.
    """
    if not COLOR_ADJUST_PTCOMBINE_AFTER_GRID_PORTED:
        raise NotImplementedError("PTCombine after-grid not marked ported")
    a = int(tag_a)
    b = int(tag_b)
    # kodakcms.dll @ 0x10040316 — mov esi, edi (=tag_a)
    esi = a
    # @ 0x10040310 — test 0x400 / je skip
    if ptcombine_mode_has_400(mode):
        # @ 0x1004031e — cmp edi, ecx / jg keep; else mov esi, ecx
        if a <= b:
            esi = b
    return esi


def ptcombine_esi_floor_for_mode(mode: int, esi: int) -> int:
    """Floor ``esi`` after the ``0x400`` max — ``@ 0x10040324…0x1004033d``.

    ``mode&0x800`` → ``max(esi, 0x10)``; else ``max(esi, 0x8)``.
    """
    if not COLOR_ADJUST_PTCOMBINE_AFTER_GRID_PORTED:
        raise NotImplementedError("PTCombine after-grid not marked ported")
    v = int(esi)
    if ptcombine_mode_has_800(mode):
        # kodakcms.dll @ 0x1004032c — cmp esi,0x10 / jg keep; mov esi,0x10
        if v <= KODAKCMS_PTCOMBINE_ESI_FLOOR_800:
            return KODAKCMS_PTCOMBINE_ESI_FLOOR_800
        return v
    # @ 0x10040338 — cmp esi,0x8 / jg keep; mov esi,0x8
    if v <= KODAKCMS_PTCOMBINE_ESI_FLOOR_CLEAR:
        return KODAKCMS_PTCOMBINE_ESI_FLOOR_CLEAR
    return v


def ptcombine_skip_type_switch(mode: int) -> bool:
    """After ``[esp+54]`` fill: ``mode&0x800`` → ``+0x2110`` w/ dims @ ``esp+54``.

    ``kodakcms.dll @ 0x100403c8…0x100403d6``: ``je`` type switch iff bit clear.
    """
    if not COLOR_ADJUST_PTCOMBINE_AFTER_GRID_PORTED:
        raise NotImplementedError("PTCombine after-grid not marked ported")
    return ptcombine_mode_has_800(mode)


def ptcombine_channel_pack(channels: int) -> int:
    """``(ch & 0xff) | ((ch & 0xff) << 8)`` — ``@ 0x1004043a…0x10040453``.

    Shared by type-switch arms that call ``PTGetPTInfo+0x9530``.
    """
    if not COLOR_ADJUST_PTCOMBINE_AFTER_GRID_PORTED:
        raise NotImplementedError("PTCombine after-grid not marked ported")
    # kodakcms.dll @ 0x1004043a — and ecx,0xff
    ch = int(channels) & 0xFF
    # @ 0x1004044a — shl eax,8; @ 0x10040453 — or eax,ecx
    return ch | (ch << 8)


def ptcombine_type_switch_case_va(type_id: int) -> int | None:
    """``(type − 2)`` → case VA via byte table ``@ 0x10040684``.

    ``> 0x24`` after subtract → default arm ``@ 0x1004053e``. Returns ``None``
    only when the byte map index is out of range of the jmp table (should not
    happen for the cited 0…4 case ids).
    """
    if not COLOR_ADJUST_PTCOMBINE_AFTER_GRID_PORTED:
        raise NotImplementedError("PTCombine after-grid not marked ported")
    # kodakcms.dll @ 0x100403df — addl $-2, %eax
    idx = (int(type_id) - 2) & 0xFFFFFFFF
    if idx >= 0x80000000:
        idx -= 0x100000000
    # @ 0x100403e2 — cmp $0x24 / ja → 0x1004053e
    if idx < 0 or idx > 0x24:
        return KODAKCMS_PTCOMBINE_TYPE_CASE_VAS[4]
    # @ 0x100403ed — movzbl 0x10040684(%eax), %ecx
    case = KODAKCMS_PTCOMBINE_TYPE_BYTE_MAP[idx]
    if case >= len(KODAKCMS_PTCOMBINE_TYPE_CASE_VAS):
        return None
    # @ 0x100403f3 — jmp *0x10040670(,%ecx,4)
    return KODAKCMS_PTCOMBINE_TYPE_CASE_VAS[case]


def ptcombine_merge_type_gate(type_at_9c: int) -> str:
    """Post-``+0x2110`` type gate @ ``0x10040496``.

    ``0x1001f`` → merge with ``[esp+18]``; ``0x2001f`` → merge with ``ebp``;
    else keep ``[esp+4c]`` path (``other``).
    """
    if not COLOR_ADJUST_PTCOMBINE_AFTER_GRID_PORTED:
        raise NotImplementedError("PTCombine after-grid not marked ported")
    t = int(type_at_9c) & 0xFFFFFFFF
    # kodakcms.dll @ 0x10040496 — cmp $0x1001f
    if t == KODAKCMS_PT_TYPE_MERGE_A:
        return "esp18"
    # @ 0x100404a1 — cmp $0x2001f
    if t == KODAKCMS_PT_TYPE_MERGE_B:
        return "ebp"
    return "other"


def ptgetptinfo_2110_early_identity(channel_dims_match: bool) -> bool:
    """``+0x2110`` returns the input PT unchanged when dims already match.

    After the eight-channel ``ftuf``/``ctuf``/``ituf`` walk, ``[esp+24]==1``
    → ``mov eax,esi; ret`` @ ``0x1000c9b3``. Rebuild arm @ ``0x1000c9bd`` is
    entered when dims mismatch (see ``ptgetptinfo_2110_rebuild_pack``).
    """
    if not COLOR_ADJUST_PTCOMBINE_AFTER_GRID_PORTED:
        raise NotImplementedError("PTCombine after-grid not marked ported")
    # kodakcms.dll @ 0x1000c9ac — cmpl $1, 0x24(%esp) / jne rebuild
    return bool(channel_dims_match)


def ptgetptinfo_2110_ctuf_mask_bit(slot: int) -> int:
    """``1 << slot`` for the CTUF-present bitmask @ ``0x1000c97d``.

    ``mov edx,1; shl edx,cl`` then ``or`` into ``[esp+10]``.
    """
    if not COLOR_ADJUST_PTGETPTINFO_2110_REBUILD_PORTED:
        raise NotImplementedError("+0x2110 rebuild not marked ported")
    # kodakcms.dll @ 0x1000c978…0x1000c97d
    if not (0 <= int(slot) < KODAKCMS_PT_CHANNEL_SLOTS):
        raise ValueError("slot out of range")
    return 1 << int(slot)


def ptgetptinfo_2110_rebuild_pack(ctuf_mask: int, channels: int) -> int:
    """Rebuild pack word passed to ``+0x930`` @ ``0x1000c9c0…0x1000c9d9``.

    ``movb [esp+10], %ah`` (low byte of CTUF bitmask) then
    ``or eax, (channels & 0xff)`` → ``((mask & 0xff) << 8) | (ch & 0xff)``.
    """
    if not COLOR_ADJUST_PTGETPTINFO_2110_REBUILD_PORTED:
        raise NotImplementedError("+0x2110 rebuild not marked ported")
    # kodakcms.dll @ 0x1000c9c2 — movb 0x10(%esp), %ah
    hi = int(ctuf_mask) & 0xFF
    # @ 0x1000c9c6…0x1000c9d9 — and ebp/esi,0xff; or eax,esi
    lo = int(channels) & 0xFF
    return (hi << 8) | lo


def ptgetptinfo_2110_slot_bit_set(bits: int, slot: int) -> bool:
    """``test (1<<slot), bits`` — rebuild loops @ ``0x1000ca52`` / ``0x1000cabe``."""
    if not COLOR_ADJUST_PTGETPTINFO_2110_REBUILD_PORTED:
        raise NotImplementedError("+0x2110 rebuild not marked ported")
    # kodakcms.dll @ 0x1000ca49…0x1000ca52 — mov edx,1; shl; test edx,ebp
    return (ptgetptinfo_2110_ctuf_mask_bit(slot) & int(bits)) != 0


def ptgetptinfo_2110_bad_magic_returns_null(magic: int) -> bool:
    """Null PT or magic ≠ ``ftuf`` → eax ``0`` @ ``0x1000cb41``."""
    if not COLOR_ADJUST_PTGETPTINFO_2110_REBUILD_PORTED:
        raise NotImplementedError("+0x2110 rebuild not marked ported")
    # kodakcms.dll @ 0x1000c8e2 / 0x1000c8f8 — je/jne → 0x1000cb41
    if magic == 0:
        return True
    return (int(magic) & 0xFFFFFFFF) != KODAKCMS_PT_MAGIC_FTUF


def ptgetptinfo_930_unpack_pack(pack: int) -> tuple[int, int, int]:
    """``+0x930`` pack → ``(lo, hi, top_nibble)`` @ ``0x1000b0f6…0x1000b10d``.

    ``lo = pack & 0xff`` (channel/present bitmask); ``hi = (pack >> 8) & 0xff``
    from ``movb %bh,%al``; ``top_nibble = (pack >> 24) & 0xf`` used later.
    """
    if not COLOR_ADJUST_PTGETPTINFO_930_PORTED:
        raise NotImplementedError("+0x930 not marked ported")
    p = int(pack) & 0xFFFFFFFF
    # kodakcms.dll @ 0x1000b0fd — and edx, 0xff
    lo = p & 0xFF
    # @ 0x1000b103 — movb %bh, %al
    hi = (p >> 8) & 0xFF
    # @ 0x1000b1a9…0x1000b1ac — sar ebx,24; and 0xf
    top = (p >> 24) & 0xF
    return lo, hi, top


def ptgetptinfo_930_bytes_in_range(lo: int, hi: int) -> bool:
    """``cmp $0xff`` / ``ja`` fail @ ``0x1000b106`` / ``0x1000b115``.

    After the byte masks this is always true for real packs; kept as the
    cited gate (values above ``0xff`` → null PT).
    """
    if not COLOR_ADJUST_PTGETPTINFO_930_PORTED:
        raise NotImplementedError("+0x930 not marked ported")
    # kodakcms.dll @ 0x1000b106 / 0x1000b115
    return 0 <= int(lo) <= 0xFF and 0 <= int(hi) <= 0xFF


def ptgetptinfo_930_sparse_gather(
    bitmask: int, arr: list[int] | None
) -> list[int]:
    """8-slot gather @ ``0x1000b125…0x1000b149``.

    For each slot ``i``: if ``(1<<i) & bitmask`` and ``arr`` non-null, take
    the next array element; else store ``0`` (null ``arr`` does not advance).
    """
    if not COLOR_ADJUST_PTGETPTINFO_930_PORTED:
        raise NotImplementedError("+0x930 not marked ported")
    out = [0] * KODAKCMS_PT_CHANNEL_SLOTS
    idx = 0
    bits = int(bitmask) & 0xFF
    for i in range(KODAKCMS_PT_CHANNEL_SLOTS):
        # kodakcms.dll @ 0x1000b12e…0x1000b132 — shl / test bitmask
        if (ptgetptinfo_2110_ctuf_mask_bit(i) & bits) == 0:
            continue
        # @ 0x1000b134 — test arr / je → 0
        if arr is None:
            out[i] = 0
            continue
        # @ 0x1000b138 — mov (%esi), %eax; add esi,4
        out[i] = int(arr[idx]) if idx < len(arr) else 0
        idx += 1
    return out


def ptgetptinfo_930_insert_top_nibble(plus8: int, pack: int) -> int:
    """Replace bits 24…27 of ``PT+8`` with ``(pack>>24)&0xf`` @ ``0x1000b1a9``.

    ``(plus8 & 0xf0ffffff) | (nibble << 24)`` — DLL uses ``xor`` after the
    ``and`` clears that nibble (equivalent).
    """
    if not COLOR_ADJUST_PTGETPTINFO_930_PORTED:
        raise NotImplementedError("+0x930 not marked ported")
    _, _, nib = ptgetptinfo_930_unpack_pack(pack)
    # kodakcms.dll @ 0x1000b1af — and $0xf0ffffff
    cleared = int(plus8) & KODAKCMS_PT_PLUS8_NIBBLE_CLEAR
    # @ 0x1000b1b4…0x1000b1b7 — shl nibble,24; xor into eax
    return cleared | (nib << 24)


def ptgetptinfo_930_or_ituf_bit(plus8: int, slot: int) -> int:
    """``orb (1<<slot)`` into low byte of ``PT+8`` @ ``0x1000b1d2…0x1000b1de``."""
    if not COLOR_ADJUST_PTGETPTINFO_930_PORTED:
        raise NotImplementedError("+0x930 not marked ported")
    if not (0 <= int(slot) < KODAKCMS_PT_CHANNEL_SLOTS):
        raise ValueError("slot out of range")
    # kodakcms.dll @ 0x1000b1d2 — movb 0x8(%esi), %al
    lo = int(plus8) & 0xFF
    # @ 0x1000b1d5…0x1000b1dc — mov $1; shl; or
    lo |= ptgetptinfo_2110_ctuf_mask_bit(slot)
    return (int(plus8) & 0xFFFFFF00) | (lo & 0xFF)


def ptgetptinfo_930_ituf_accepted(magic: int) -> bool:
    """Non-null gathered ptr must be ``ituf`` @ ``0x1000b1c9`` else fail."""
    if not COLOR_ADJUST_PTGETPTINFO_930_PORTED:
        raise NotImplementedError("+0x930 not marked ported")
    # kodakcms.dll @ 0x1000b1c9 — cmpl $0x66757469, (%ebp)
    return (int(magic) & 0xFFFFFFFF) == KODAKCMS_PT_MAGIC_ITUF


def ptgetptinfo_bit_index(bit: int) -> int:
    """Lowest-set-bit index @ ``0x10014730`` (``+0xf80`` calls this).

    ``≤0`` → ``-1``; else shift right until bit0 set, counting.
    """
    if not COLOR_ADJUST_PTGETPTINFO_E80_PORTED:
        raise NotImplementedError("+0xe80 not marked ported")
    v = int(bit)
    # kodakcms.dll @ 0x10014734 — test / jg; else or $-1
    if v <= 0:
        return -1
    # @ 0x1001473c…0x10014749 — xor eax; testb $1; jne done; sar; inc
    n = 0
    while (v & 1) == 0:
        v >>= 1
        n += 1
    return n


def ptgetptinfo_f80_or_plus8(plus8: int, slot: int, ctuf_plus4: int) -> int:
    """``+0xf80`` updates ``PT+8`` dword after attaching a CTUF @ ``slot``.

    ``orb (1<<slot)`` into byte ``PT+9`` @ ``0x1000b7a5…0x1000b7b0``;
    ``orb (ctuf+4)`` into byte ``PT+8`` @ ``0x1000b7b3…0x1000b7b6``.
    """
    if not COLOR_ADJUST_PTGETPTINFO_E80_PORTED:
        raise NotImplementedError("+0xe80 not marked ported")
    if not (0 <= int(slot) < KODAKCMS_PT_CHANNEL_SLOTS):
        raise ValueError("slot out of range")
    p = int(plus8) & 0xFFFFFFFF
    # kodakcms.dll @ 0x1000b7a9 — movb 0x9(%edi), %al; orb (1<<slot)
    hi = ((p >> 8) & 0xFF) | ptgetptinfo_2110_ctuf_mask_bit(slot)
    # @ 0x1000b7b3 — movb 0x4(%esi), %al; orb into 0x8(%edi)
    lo = (p & 0xFF) | (int(ctuf_plus4) & 0xFF)
    return (p & 0xFFFF0000) | ((hi & 0xFF) << 8) | (lo & 0xFF)


def ptgetptinfo_e80_ftuf_gate(magic: int) -> bool:
    """``+0xe80`` requires non-null ``ftuf`` @ ``0x1000b64d`` / ``0x1000b653``."""
    if not COLOR_ADJUST_PTGETPTINFO_E80_PORTED:
        raise NotImplementedError("+0xe80 not marked ported")
    return (int(magic) & 0xFFFFFFFF) == KODAKCMS_PT_MAGIC_FTUF


def ptgetptinfo_9fa0_gtuf_mask(gtuf_dims_i16: list[int]) -> int:
    """``+0x9fa0`` @ ``0x10014760``: bits for gtuf int16 dims ``> 1``.

    Walks up to 8 int16s at ``gtuf+0x18``; ``OR (1<<i)`` when ``dim > 1``.
    """
    if not COLOR_ADJUST_PTGETPTINFO_AA0_PORTED:
        raise NotImplementedError("+0xaa0 not marked ported")
    mask = 0
    # kodakcms.dll @ 0x1001476c…0x10014786
    for i, dim in enumerate(list(gtuf_dims_i16)[:KODAKCMS_PT_CHANNEL_SLOTS]):
        # @ 0x10014770 — cmpw $1, (%edx) / jle skip
        if int(dim) > 1:
            mask |= 1 << i  # @ 0x10014776…0x1001477d
    return mask


def ptgetptinfo_aa0_dim_gate(gtuf_dim_i16: int, ituf_dim: int) -> bool:
    """Existing-ituf dim must equal ``movswl(gtuf dim)`` @ ``0x1000b343``."""
    if not COLOR_ADJUST_PTGETPTINFO_AA0_PORTED:
        raise NotImplementedError("+0xaa0 not marked ported")
    # kodakcms.dll @ 0x1000b343…0x1000b349 — movswl; cmp [eax+0xc]
    d = int(gtuf_dim_i16)
    if d >= 0x8000:
        d -= 0x10000
    return d == (int(ituf_dim) & 0xFFFFFFFF)


def ptgetptinfo_c40_dim_ok(dim: int) -> bool:
    """``+0xc40`` dim gate: ``2 ≤ dim ≤ 0x40`` @ ``0x1000b406``."""
    if not COLOR_ADJUST_PTGETPTINFO_C40_PORTED:
        raise NotImplementedError("+0xc40 not marked ported")
    d = int(dim)
    # kodakcms.dll @ 0x1000b406 — cmp $1 / jle fail; @ 0x1000b40b cmp $0x40 / jg fail
    return KODAKCMS_PT_ITUF_DIM_MIN <= d <= KODAKCMS_PT_ITUF_DIM_MAX


def ptgetptinfo_c40_size_code(param: int) -> int:
    """``+0xc40`` buffer size select @ ``0x1000b42e…0x1000b43d``.

    ``param == 2`` → ``0x203``; else ``0x100``.
    """
    if not COLOR_ADJUST_PTGETPTINFO_C40_PORTED:
        raise NotImplementedError("+0xc40 not marked ported")
    # kodakcms.dll @ 0x1000b42e — sub $2; neg; sbb; and $0xfffffefd; add $0x203
    if int(param) == 2:
        return KODAKCMS_PT_ITUF_SIZE_PARAM2
    return KODAKCMS_PT_ITUF_SIZE_OTHER


def ptcombine_ae0_status(mp_state_ok: bool) -> tuple[int, int | None]:
    """``PTCombine+0xae0`` @ ``0x100407c0``.

    Returns ``(status, value_or_None)``. Fail → ``(0x130, None)``;
    OK → ``(1, *(mp+4))`` when ``mp_state_ok`` (caller supplies ``[eax+4]``).
    """
    if not COLOR_ADJUST_PTCOMBINE_AE0_PORTED:
        raise NotImplementedError("+0xae0 not marked ported")
    # kodakcms.dll @ 0x100407c5 — test eax / jne ok
    if not mp_state_ok:
        # @ 0x100407c9 — mov eax, 0x130
        return (KODAKCMS_PTCOMBINE_AE0_FAIL, None)
    # @ 0x100407d3…0x100407d8 — mov [ecx], [eax+4]; mov eax, 1
    return (1, None)  # value filled by caller from mp+4


def ptgetptinfo_3630_status_for_first_dim(dim: int) -> int:
    """Initial ``+0x3630`` status: dim ``> 0xff`` → ``-1``, else ``1``."""
    if not COLOR_ADJUST_PTGETPTINFO_3630_PORTED:
        raise NotImplementedError("+0x3630 not marked ported")
    # kodakcms.dll @ 0x1000ddf9 — status=1; @ 0x1000de41 cmp $0xff / jle keep
    if int(dim) > 0xFF:
        return KODAKCMS_PT_STATUS_DIM_GT_FF  # @ 0x1000de4e
    return 1


def ptgetptinfo_3630_max_dim(dims: list[int]) -> int:
    """Max among ituf dims (``+0x3630`` raise @ ``0x1000de74``)."""
    if not COLOR_ADJUST_PTGETPTINFO_3630_PORTED:
        raise NotImplementedError("+0x3630 not marked ported")
    if not dims:
        return 0
    m = int(dims[0])
    for d in dims[1:]:
        # kodakcms.dll @ 0x1000de70 — cmp ebx, ecx / jge keep; else raise
        if int(d) > m:
            m = int(d)
    return m


def ptgetptinfo_3630_dim_mismatch(status: int, dims: list[int]) -> int:
    """If status still ``1`` and dims differ → ``-2`` @ ``0x1000de82``."""
    if not COLOR_ADJUST_PTGETPTINFO_3630_PORTED:
        raise NotImplementedError("+0x3630 not marked ported")
    if int(status) != 1 or len(dims) < 2:
        return int(status)
    base = int(dims[0])
    for d in dims[1:]:
        if int(d) != base:
            return KODAKCMS_PT_STATUS_DIM_MISMATCH
    return int(status)


def ptgetptinfo_7aa0_merge_pack(
    flags_word: int, pt_a_b9: int, pt_b_b9: int
) -> int:
    """``+0x7aa0`` prologue pack @ ``0x100122b1…0x100122e2``.

    ``mid = (flags>>8)&0xff`` or ``pt_a+9`` if mid==0;
    ``hi = (flags>>16) & pt_b+9``;
    ``pack = (hi<<16) | (mid<<8) | (pt_b+9)``.
    """
    if not COLOR_ADJUST_PTGETPTINFO_7AA0_PROLOGUE_PORTED:
        raise NotImplementedError("+0x7aa0 prologue not marked ported")
    fw = int(flags_word) & 0xFFFFFFFF
    a9 = int(pt_a_b9) & 0xFF
    b9 = int(pt_b_b9) & 0xFF
    # kodakcms.dll @ 0x100122bc — movb %ah, %dl
    mid = (fw >> 8) & 0xFF
    # @ 0x100122cc — test edx / jne; else movb 0x9(%ebx)
    if mid == 0:
        mid = a9
    # @ 0x100122c5 — sar eax,16; and with [esi+9]
    hi = ((fw >> 16) & 0xFFFF) & b9
    # @ 0x100122d7…0x100122e0 — pack
    return ((hi & 0xFF) << 16) | ((mid & 0xFF) << 8) | b9


def ptgetptinfo_1140_alloc_size(magic: int) -> int | None:
    """``+0x1140`` @ ``0x1000b900``: ``ituf`` → fixed ``0x404`` else fail.

    Returns bytes to allocate into ``ituf+0x10``, or ``None`` when the
    magic / null gate fails (``@ 0x1000b942``).
    """
    if not COLOR_ADJUST_PT_MERGE_BODY_PORTED:
        raise NotImplementedError("PT merge body not marked ported")
    # kodakcms.dll @ 0x1000b905…0x1000b90f
    if int(magic) != KODAKCMS_PT_MAGIC_ITUF:
        return None
    # @ 0x1000b911 — push $0x404
    return KODAKCMS_PT_ITUF_BUF_1140


def ptgetptinfo_1230_alloc_bytes(magic: int, count: int) -> int | None:
    """``+0x1230`` @ ``0x1000b9f0``: ``ituf`` → ``2·count`` into ``+0x24``.

    ``count`` is also written to ``ituf+0x20`` @ ``0x1000ba1a``.
    """
    if not COLOR_ADJUST_PT_MERGE_BODY_PORTED:
        raise NotImplementedError("PT merge body not marked ported")
    # kodakcms.dll @ 0x1000b9f5…0x1000b9ff
    if int(magic) != KODAKCMS_PT_MAGIC_ITUF:
        return None
    # @ 0x1000ba06 — lea eax, [edi+edi]
    return (int(count) & 0xFFFFFFFF) * 2


def ptgetptinfo_c40_uses_1140(param_ecx: int) -> bool:
    """``+0xc40`` ``cmp ecx,1`` @ ``0x1000b442`` → ``+0x1140`` else ``+0x1230``."""
    if not COLOR_ADJUST_PT_MERGE_BODY_PORTED:
        raise NotImplementedError("PT merge body not marked ported")
    # kodakcms.dll @ 0x1000b442 — cmp $1 / jne +0x1230
    return int(param_ecx) == 1


def _f32(x: float) -> float:
    """IEEE-754 binary32 round-trip (``fstp dword`` @ ``0x100140cc``)."""
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def ptgetptinfo_9820_step(n: int) -> float:
    """``1.0 / (n−1)`` as double @ ``0x1001403d…0x10014058``."""
    if not COLOR_ADJUST_PT_MERGE_BODY_PORTED:
        raise NotImplementedError("PT merge body not marked ported")
    # kodakcms.dll @ 0x1001403d — lea ecx, [eax-1]; fild; fdivr qword 1.0
    return 1.0 / float(int(n) - 1)


def ptgetptinfo_9820_sample_to_i16(value: float) -> int:
    """Clamp ``[0,1]`` → ``trunc_f32(v·65535 + bias)`` @ ``0x10014074…0x100140e9``.

    Matches the SSE ``cvttss2si`` path after ``fstp dword``.
    """
    if not COLOR_ADJUST_PT_MERGE_BODY_PORTED:
        raise NotImplementedError("PT merge body not marked ported")
    v = float(value)
    # kodakcms.dll @ 0x10014074…0x100140b2 — clamp to [0,1]
    if v < 0.0:
        v = 0.0
    if v > 1.0:
        v = 1.0
    # @ 0x100140b8 — fmul 65535.0; @ 0x100140c6 — fadd bias; fstp dword
    x = _f32(v * KODAKCMS_PT_9820_SCALE + KODAKCMS_PT_9820_BIAS)
    # @ 0x100140da — cvttss2si (trunc toward 0)
    return int(x) & 0xFFFF


def ptgetptinfo_9820_fill_identity(n: int) -> list[int]:
    """Identity callback fill: ``cb(t)=t`` for ``i=0…n−1``."""
    if not COLOR_ADJUST_PT_MERGE_BODY_PORTED:
        raise NotImplementedError("PT merge body not marked ported")
    if int(n) <= 0:
        # kodakcms.dll @ 0x10014050 — test eax / jle → status 1, no stores
        return []
    step = ptgetptinfo_9820_step(n)
    out: list[int] = []
    t = 0.0
    # @ 0x10014062…0x100140ff
    for _ in range(int(n)):
        out.append(ptgetptinfo_9820_sample_to_i16(t))
        t += step  # @ 0x100140ed — fadd step into running t
    return out


def ptgetptinfo_9820_null_callback_skips_fill(callback: int | None) -> bool:
    """Null ``[ebp+0xc]`` → skip loop, status 1 @ ``0x10014006``."""
    if not COLOR_ADJUST_PT_MERGE_BODY_PORTED:
        raise NotImplementedError("PT merge body not marked ported")
    # kodakcms.dll @ 0x10014006 — test eax / je → 0x10014105
    return callback is None or int(callback) == 0


def ptgetptinfo_7aa0_ftuf_gate(magic_a: int, magic_b: int) -> bool:
    """Both args must be non-null ``ftuf`` @ ``0x10012276…0x100122ab``."""
    if not COLOR_ADJUST_PT_MERGE_BODY_PORTED:
        raise NotImplementedError("PT merge body not marked ported")
    # kodakcms.dll @ 0x1001228a / @ 0x100122a5 — cmp $'ftuf'
    return (
        int(magic_a) == KODAKCMS_PT_MAGIC_FTUF
        and int(magic_b) == KODAKCMS_PT_MAGIC_FTUF
    )


def ptgetptinfo_7aa0_slot_bit(mask: int, slot: int) -> bool:
    """``(1<<slot) & mask`` @ ``0x1001239c`` / ``0x100125ba``."""
    if not COLOR_ADJUST_PT_MERGE_BODY_PORTED:
        raise NotImplementedError("PT merge body not marked ported")
    if not (0 <= int(slot) < KODAKCMS_PT_CHANNEL_SLOTS):
        raise ValueError("slot out of range")
    # kodakcms.dll @ 0x1001239c — shl edx,cl; test eax,edx
    return (int(mask) & (1 << int(slot))) != 0


def ptgetptinfo_7aa0_max_dim(dim_a: int, dim_b: int) -> int:
    """``max(a,b)`` before ``+0x1230`` @ ``0x10012613``."""
    if not COLOR_ADJUST_PT_MERGE_BODY_PORTED:
        raise NotImplementedError("PT merge body not marked ported")
    a = int(dim_a)
    b = int(dim_b)
    # kodakcms.dll @ 0x10012613 — cmp eax,ecx / jg keep; mov eax,ecx
    return a if a > b else b


def ptgetptinfo_7aa0_alloc_to_bool(ptr: int) -> int:
    """``neg; sbb; neg`` → ``0/1`` after ``+0x1230`` @ ``0x10012629``."""
    if not COLOR_ADJUST_PT_MERGE_BODY_PORTED:
        raise NotImplementedError("PT merge body not marked ported")
    # kodakcms.dll @ 0x10012629…0x1001262d
    return 0 if int(ptr) == 0 else 1


def ptgetptinfo_7aa0_sample_gates(
    magic_src: int, magic_otuf: int, magic_dst: int, src_dim: int, dst_count: int
) -> bool:
    """``@ 0x100127e0`` prologue: ``ituf``/``otuf``/``ituf`` + ``src_dim ≤ dst``."""
    if not COLOR_ADJUST_PT_MERGE_BODY_PORTED:
        raise NotImplementedError("PT merge body not marked ported")
    # kodakcms.dll @ 0x1001280a / 0x10012826 / 0x10012841
    if int(magic_src) != KODAKCMS_PT_MAGIC_ITUF:
        return False
    if int(magic_otuf) != KODAKCMS_PT_MAGIC_OTUF:
        return False
    if int(magic_dst) != KODAKCMS_PT_MAGIC_ITUF:
        return False
    # @ 0x10012853 — cmp edi,ecx / jg fail
    return int(src_dim) <= int(dst_count)


def sp_connect_validate_status_from_ref_and_type(
    get_ref_status: int, pt_type: int
) -> int | None:
    """Validate-loop leaf host face (one xform).

    ``SpXformGetRefNum`` non-zero → that status (``0x1fb`` on bad handle
    @ ``0x1002f0d2``). Else accept ``pt_type`` via ``sp_connect_pt_type_accepted``
    or return ``0x1fb`` @ ``0x1002e993``. Returns ``None`` when this xform OK.
    """
    if not COLOR_ADJUST_SPCONNECT_VALIDATE_PORTED:
        raise NotImplementedError("ConnectEx validate not marked ported")
    # kodakcms.dll @ 0x1002e7a2 — cmp eax, 0 / jne fail with GetRefNum status
    st = int(get_ref_status) & 0xFFFFFFFF
    if st != 0:
        return st
    # kodakcms.dll @ 0x1002e7b7…0x1002e7c1
    if sp_connect_pt_type_accepted(pt_type):
        return None
    # kodakcms.dll @ 0x1002e996 — mov eax, 0x1fb
    return KODAKCMS_SPCONNECT_ERR_BAD_XFORM


@dataclass(frozen=True)
class ColorAdjustParams:
    """Host stand-in for TLA ``CiImage+0xc8`` primary fields (diff=0).

    Factory ctor zeros every field — stock Preference decode matches
    ``COLOR_ADJUST_DEFAULT_SKIP_PORTED``.
    """

    red: int = 0
    green: int = 0
    blue: int = 0
    brightness: int = 0
    contrast: int = 0
    sharpness: int = 0
    bnw: int = 0
    saturation: int = 0
    # Save-path gate (params+0x10). Non-zero enables contrast/unsharp.
    gate: int = 1

    def clamped(self) -> "ColorAdjustParams":
        def c(v: int) -> int:
            if v < OBJ_CLAMP_LO:
                return OBJ_CLAMP_LO
            if v > OBJ_CLAMP_HI:
                return OBJ_CLAMP_HI
            return int(v)

        return ColorAdjustParams(
            red=c(self.red),
            green=c(self.green),
            blue=c(self.blue),
            brightness=c(self.brightness),
            contrast=c(self.contrast),
            sharpness=c(self.sharpness),
            bnw=int(self.bnw),
            saturation=int(self.saturation),
            gate=int(self.gate),
        )


def saturation_pf_name(param: int) -> str:
    """Map ``params+0x50`` (signed, typically -5…+5) → ColorCorrection file.

    Implements ``index = param + 5`` then the ``0x1001544c`` jump table.
    Out-of-range → ``unity.pf`` (``ja`` default).
    """
    idx = int(param) + 5
    if idx < 0 or idx > 10:
        return "unity.pf"
    return SAT_FILES[idx]


def bnw_effect_pf_name(param: int) -> str:
    """Map ``params+0x4c`` → BnW/sepia abstract (or ``unity.pf``)."""
    return BNW_FILES.get(int(param), BNW_DEFAULT)


def tone_alias_pf_name(name: str | None) -> str:
    """Host CLI alias → filename (warm/cold/sepia/none)."""
    if not name:
        return BNW_DEFAULT
    return TONE_ALIAS.get(name.lower(), BNW_DEFAULT)


def color_correction_dir(fx35_root: Path) -> Path:
    """``<FX35 COM SERVER>/Config/ColorCorrection``."""
    return fx35_root / "Config" / "ColorCorrection"


def resolve_pf(data_dir: Path, name: str) -> Path:
    """Resolve a ColorCorrection ``.pf`` (case-insensitive on disk)."""
    direct = data_dir / name
    if direct.is_file():
        return direct
    lower = {p.name.lower(): p for p in data_dir.glob("*.pf")}
    hit = lower.get(name.lower())
    if hit is None:
        raise FileNotFoundError(f"missing profile {name} under {data_dir}")
    return hit


def apply_lab_abstract(srgb_u8, data_dir: Path, abstract_name: str):
    """Apply one Lab→Lab abstract ``.pf`` on 8-bit sRGB (PIL/ImageCms).

    Matches the host stand-in used by ``pakon_decode.apply_abstract_tone``.
    Pakon folds abstracts into ``SpCombineXforms`` with profile0/1 — this
    helper is **one abstract only**, after Ansel sRGB.
    """
    from PIL import Image, ImageCms

    if abstract_name.lower() == "unity.pf":
        return srgb_u8
    abs_path = resolve_pf(Path(data_dir), abstract_name)
    intent = ImageCms.Intent.PERCEPTUAL
    lab_p = ImageCms.createProfile("LAB")
    srgb_p = ImageCms.createProfile("sRGB")
    abs_p = ImageCms.getOpenProfile(str(abs_path))
    im = Image.fromarray(np.asarray(srgb_u8, dtype=np.uint8), mode="RGB")
    to_lab = ImageCms.buildTransformFromOpenProfiles(
        srgb_p, lab_p, "RGB", "LAB", renderingIntent=intent)
    lab = ImageCms.applyTransform(im, to_lab)
    try:
        ax = ImageCms.buildTransformFromOpenProfiles(
            abs_p, abs_p, "LAB", "LAB", renderingIntent=intent)
        lab = ImageCms.applyTransform(lab, ax)
    except Exception:
        return srgb_u8
    back = ImageCms.buildTransformFromOpenProfiles(
        lab_p, srgb_p, "LAB", "RGB", renderingIntent=intent)
    return np.asarray(ImageCms.applyTransform(lab, back), dtype=np.uint8)


def apply_sat_and_bnw(
    srgb_u8,
    data_dir: Path,
    *,
    sat_param: int = 0,
    bnw_param: int = 0,
):
    """Apply saturation then BnW abstracts (Ansel-sRGB → ColorAdjust stand-in).

    Skips ``profile0``/``profile1`` (Ansel already rendered to sRGB). Does
    **not** combine via ``SpCombineXforms`` or run unsharp.
    """
    out = apply_lab_abstract(srgb_u8, data_dir, saturation_pf_name(sat_param))
    out = apply_lab_abstract(out, data_dir, bnw_effect_pf_name(bnw_param))
    return out


def _i32(n: int) -> int:
    n = int(n) & 0xFFFFFFFF
    return n - 0x100000000 if n >= 0x80000000 else n


def trunc_div2(n: int) -> int:
    """MSVC ``cdq; sub eax,edx; sar eax,1`` toward-zero /2 @ ``0x10014789``."""
    a = _i32(n)
    edx = -1 if a < 0 else 0
    return (a - edx) >> 1


def mul_div1000_trunc(n: int, *, sar: int) -> int:
    """``imul`` magic ``0x10624dd3``; ``sar edx,sar``; ``+ signbit`` (trunc).

    ``sar=6`` → /1000 (contrast fill). ``sar=8`` → /4000 path for offsets
    after ``shl 0xc`` (= *4096), i.e. ≈ ``trunc(offset * 1.024)``.
    """
    full = _i32(n) * _i32(DIV1000_MAGIC)
    edx = full >> 32
    edx >>= sar
    return edx + (1 if edx < 0 else 0)


def contrast_base_lut(contrast_half: int, *, clamp: bool = True) -> list[int]:
    """Base 4096-entry LUT @ ``0x100147ed…0x1001487b`` (half≠0).

    ``lut[i] = trunc((i - 0x60e) * (half + 1000) / 1000) + 0x60e``.
    """
    half = int(contrast_half)
    if half == 0:
        return list(range(LUT_LEN))
    scale = half + CONTRAST_SCALE_BASE
    out: list[int] = []
    for i in range(LUT_LEN):
        v = mul_div1000_trunc((i - CONTRAST_PIVOT) * scale, sar=6) + CONTRAST_PIVOT
        if clamp:
            if v < 0:
                v = 0
            elif v > LUT_MAX:
                v = LUT_MAX
        out.append(v)
    return out


def contrast_offset_delta(offset: int) -> int:
    """Per-channel addend @ ``0x100148a8…`` — ``trunc((offset<<12)*magic>>40)``."""
    if offset == 0:
        return 0
    return mul_div1000_trunc(_i32(offset) << 12, sar=8)


def contrast_apply_offset(lut: list[int], offset: int) -> list[int]:
    """Add scaled offset and clamp ``0…0xfff``."""
    if offset == 0:
        return [0 if v < 0 else (LUT_MAX if v > LUT_MAX else v) for v in lut]
    delta = contrast_offset_delta(offset)
    out: list[int] = []
    for v in lut:
        x = v + delta
        if x < 0:
            x = 0
        elif x > LUT_MAX:
            x = LUT_MAX
        out.append(x)
    return out


def build_contrast_luts_rgb(
    *,
    contrast: int,
    red: int = 0,
    green: int = 0,
    blue: int = 0,
    brightness: int = 0,
) -> tuple[list[int], list[int], list[int]] | None:
    """Three channel LUTs matching IMAu ``0x10014774…0x10014a69``.

    Returns ``None`` when DLL skips the build (half==0 and all offsets 0).
    """
    half = trunc_div2(contrast)
    off_r = int(red) + int(brightness)
    off_g = int(green) + int(brightness)
    off_b = int(blue) + int(brightness)
    if half == 0 and off_r == 0 and off_g == 0 and off_b == 0:
        return None
    # Offset-mode (any channel offset ≠ 0) skips clamp in the base fill;
    # clamp happens in the add loop. Match that.
    offset_mode = off_r != 0 or off_g != 0 or off_b != 0
    base = contrast_base_lut(half, clamp=not offset_mode)
    return (
        contrast_apply_offset(base, off_r),
        contrast_apply_offset(base, off_g),
        contrast_apply_offset(base, off_b),
    )


def apply_contrast_luts_i16(
    rgb: np.ndarray,
    luts: tuple[list[int], list[int], list[int]],
) -> np.ndarray:
    """Apply per-channel 12-bit LUTs to I16 HxWx3 (RPD-like domain)."""
    out = np.empty_like(rgb, dtype=np.int16)
    for c, lut in enumerate(luts):
        table = np.asarray(lut, dtype=np.int16)
        plane = np.clip(rgb[:, :, c], 0, LUT_MAX).astype(np.int32)
        out[:, :, c] = table[plane]
    return out


def unsharp_amount(sharpness: int) -> float:
    """``fild(sharp) * 0.01`` @ ``0x10014ca3`` (``0x105756d8``)."""
    return float(int(sharpness)) * UNSHARP_AMOUNT_SCALE


def kernel_scale_dbe0(
    coeffs: tuple[float, ...] | list[float],
    channels: int,
) -> tuple[int, int]:
    """``0x1030dbe0`` — pick integer scale ``S`` and ``trunc(S·Σ|w|+0.2)``.

    Unicorn-golden vs PakonIMAu.dll. ``channels > 1`` → max ``0x4000``,
    else ``0x100``. Halve ``S`` (``cdq; sub; sar``) while rounded sum
    exceeds max.
    """
    max_s = UNSHARP_SCALE_MAX_1CH if int(channels) <= 1 else UNSHARP_SCALE_MAX_NCH
    s = int(max_s)
    sum_abs = sum(abs(float(c)) for c in coeffs)
    while True:
        rounded = int(math.trunc(float(s) * sum_abs + UNSHARP_QUANT_BIAS))
        if rounded <= max_s:
            return s, rounded
        # MSVC ``cdq; sub eax,edx; sar eax,1`` toward-zero /2.
        s = (s - (1 if s < 0 else 0)) >> 1
        if s < 1:
            raise ValueError("kernel_scale_dbe0: scale collapsed below 1")


def unsharp_kernel_i16(
    coeffs: tuple[float, ...] = UNSHARP_KERNEL_1D,
    channels: int = 3,
) -> tuple[tuple[int, ...], int]:
    """Float weights → int16 coeffs + right-shift for ColorAdjust blur.

    ``coeff_i = trunc(S·w_i + 0.2)``; ``shift = bit_length(S) - 1`` when ``S``
    is power-of-two (ColorAdjust 3-tap → ``S=16384``, shift 14,
    coeffs ``(4096,8192,4096)``).
    """
    s, _ = kernel_scale_dbe0(coeffs, channels)
    ints = tuple(int(math.trunc(float(s) * float(w) + UNSHARP_QUANT_BIAS))
                 for w in coeffs)
    if s <= 0 or (s & (s - 1)) != 0:
        # Non-power-of-two S is possible (dbe0); shift from ilog2 floor.
        shift = max(0, s.bit_length() - 1)
    else:
        shift = s.bit_length() - 1
    return ints, shift


def _conv1d_i16(plane: np.ndarray, coeffs: tuple[int, ...], shift: int) -> np.ndarray:
    """Separable 1D pass along axis 1 (last spatial) with edge replicate."""
    if plane.ndim != 2:
        raise ValueError("plane must be 2D")
    if len(coeffs) != 3:
        raise ValueError("ColorAdjust kernel is 3-tap")
    # Edge replicate: pad 1 on each side.
    padded = np.pad(plane.astype(np.int32), ((0, 0), (1, 1)), mode="edge")
    c0, c1, c2 = coeffs
    acc = c0 * padded[:, :-2] + c1 * padded[:, 1:-1] + c2 * padded[:, 2:]
    # Round-nearest toward +∞ halfway via + (1<<(shift-1)) for shift>0.
    if shift > 0:
        acc = acc + (1 << (shift - 1))
        acc = acc >> shift
    return acc


def separable_blur_i16(
    rgb: np.ndarray,
    coeffs: tuple[int, ...] | None = None,
    shift: int | None = None,
) -> np.ndarray:
    """H then V separable 3-tap blur (ColorAdjust unsharp prefilter)."""
    if coeffs is None or shift is None:
        coeffs, shift = unsharp_kernel_i16()
    x = np.asarray(rgb)
    if x.ndim != 3 or x.shape[2] != 3:
        raise ValueError("expected HxWx3")
    out = np.empty_like(x, dtype=np.int32)
    for c in range(3):
        plane = x[:, :, c]
        h = _conv1d_i16(plane, coeffs, shift)
        # V pass: conv along axis 0 ≡ H on transpose.
        v = _conv1d_i16(h.T, coeffs, shift).T
        out[:, :, c] = v
    return out


def apply_unsharp_i16(
    rgb: np.ndarray,
    sharpness: int,
    *,
    lo: int = UNSHARP_I16_LO,
    hi: int = UNSHARP_I16_HI,
) -> np.ndarray:
    """``orig + amount·(orig − blur)`` then clamp to int16 range.

    Structure matches ``0x10013a42`` (direct path): blur via separable
    3-tap, ``amount = sharp·0.01``. Fixed-point gain/LUT variants of the
    same leaf are left as future tightening; stock Preference uses
    ``sharpness==0`` (skip).
    """
    amount = unsharp_amount(sharpness)
    if amount == 0.0:
        return np.asarray(rgb, dtype=np.int16)
    src = np.asarray(rgb, dtype=np.int32)
    blur = separable_blur_i16(src)
    # Round half-away from zero via trunc(x+copysign(0.5,x)).
    delta = src.astype(np.float64) - blur.astype(np.float64)
    adj = amount * delta
    rounded = np.trunc(adj + np.copysign(0.5, adj)).astype(np.int32)
    out = src + rounded
    return np.clip(out, lo, hi).astype(np.int16)


def is_default_skip(params: ColorAdjustParams) -> bool:
    """True when contrast+unsharp bodies are skipped (factory zeros / gate).

    RE: ``params+0x10==0`` → skip (@ ``0x10014774``); else if contrast/2
    and RGB+bright offsets all 0 → skip LUT (@ ``0x100147b5``); sharp==0
    → skip unsharp (@ ``0x10014c43`` fucompp).
    """
    p = params.clamped()
    if p.gate == 0:
        return True
    half = trunc_div2(p.contrast)
    offs = (
        p.red + p.brightness,
        p.green + p.brightness,
        p.blue + p.brightness,
    )
    contrast_idle = half == 0 and all(o == 0 for o in offs)
    unsharp_idle = p.sharpness == 0
    return contrast_idle and unsharp_idle


def apply_preference_color_adjust_i16(
    rgb_i16: np.ndarray,
    params: ColorAdjustParams | None = None,
) -> np.ndarray:
    """Preference-path ColorAdjust leaf after FUGC, before ICC.

    Factory-zero params → identity (``DEFAULT_SKIP``). Non-zero contrast
    applies golden LUTs when ``CONTRAST_LUT_PORTED``. Non-zero sharpness
    applies separable unsharp when ``UNSHARP_APPLY_PORTED``. Stock sat/BnW
    are unity (``SPCOMBINE_DEFAULT_IDENTITY``); kodakcms body not applied.
    """
    p = (params or ColorAdjustParams()).clamped()
    if not COLOR_ADJUST_DEFAULT_SKIP_PORTED and not COLOR_ADJUST_CONTRAST_LUT_PORTED:
        return rgb_i16
    if is_default_skip(p):
        return rgb_i16
    out = rgb_i16
    if COLOR_ADJUST_CONTRAST_LUT_PORTED:
        luts = build_contrast_luts_rgb(
            contrast=p.contrast,
            red=p.red,
            green=p.green,
            blue=p.blue,
            brightness=p.brightness,
        )
        if luts is not None:
            out = apply_contrast_luts_i16(np.asarray(out), luts)
    if p.sharpness != 0 and p.gate != 0:
        if not COLOR_ADJUST_UNSHARP_APPLY_PORTED:
            raise NotImplementedError(
                "ImaUnsharpMaskOperation apply not ported "
                f"(amount={unsharp_amount(p.sharpness)}, "
                f"kernel={UNSHARP_KERNEL_1D}; cite 0x10014c5c / 0x10014ca3)"
            )
        out = apply_unsharp_i16(np.asarray(out), p.sharpness)
    return out


def main() -> None:
    print("PIColorAdjustPlanar catalog (IMAu base 0x10000000)")
    print(f"  PIColorAdjustPlanar     {PI_COLOR_ADJUST_PLANAR:#010x}")
    print(f"  TLA bApplyColorAdjust   {TLA_B_APPLY_COLOR_ADJUSTMENTS:#010x}")
    print(f"  after Ansel slot+0x64   {TLA_CALL_ANSEL_BALANCE:#010x}")
    print(f"  COLOR_ADJUST_PORTED={COLOR_ADJUST_PORTED}")
    print(f"  CONTRAST_LUT_PORTED={COLOR_ADJUST_CONTRAST_LUT_PORTED}")
    print(f"  UNSHARP_PARAMS_PORTED={COLOR_ADJUST_UNSHARP_PARAMS_PORTED}")
    print(f"  UNSHARP_APPLY_PORTED={COLOR_ADJUST_UNSHARP_APPLY_PORTED}")
    print(f"  DEFAULT_SKIP_PORTED={COLOR_ADJUST_DEFAULT_SKIP_PORTED}")
    print(f"  SPCOMBINE_DEFAULT_IDENTITY={COLOR_ADJUST_SPCOMBINE_DEFAULT_IDENTITY}")
    print(f"  SPCOMBINE_WRAPPER_PORTED={COLOR_ADJUST_SPCOMBINE_WRAPPER_PORTED}")
    print(f"  SPCONNECT_PROLOGUE_PORTED={COLOR_ADJUST_SPCONNECT_PROLOGUE_PORTED}")
    print(f"  SPCONNECT_COPY12_PORTED={COLOR_ADJUST_SPCONNECT_COPY12_PORTED}")
    print(f"  SPCONNECT_VALIDATE_PORTED={COLOR_ADJUST_SPCONNECT_VALIDATE_PORTED}")
    print(f"  SPCONNECT_FLAG_DISPATCH_PORTED={COLOR_ADJUST_SPCONNECT_FLAG_DISPATCH_PORTED}")
    print(f"  SPCONNECT_MODE_PORTED={COLOR_ADJUST_SPCONNECT_MODE_PORTED}")
    print(f"  SPCONNECT_PATH0_PORTED={COLOR_ADJUST_SPCONNECT_PATH0_PORTED}")
    print(f"  PTCOMBINE_GRID_PORTED={COLOR_ADJUST_PTCOMBINE_GRID_PORTED}")
    print(f"  PTCOMBINE_AFTER_GRID_PORTED={COLOR_ADJUST_PTCOMBINE_AFTER_GRID_PORTED}")
    print(
        f"  PTGETPTINFO_2110_REBUILD_PORTED="
        f"{COLOR_ADJUST_PTGETPTINFO_2110_REBUILD_PORTED}"
    )
    print(f"  PTGETPTINFO_930_PORTED={COLOR_ADJUST_PTGETPTINFO_930_PORTED}")
    print(f"  PTGETPTINFO_E80_PORTED={COLOR_ADJUST_PTGETPTINFO_E80_PORTED}")
    print(f"  PTGETPTINFO_AA0_PORTED={COLOR_ADJUST_PTGETPTINFO_AA0_PORTED}")
    print(f"  PTGETPTINFO_C40_PORTED={COLOR_ADJUST_PTGETPTINFO_C40_PORTED}")
    print(f"  PTCOMBINE_AE0_PORTED={COLOR_ADJUST_PTCOMBINE_AE0_PORTED}")
    print(f"  PTGETPTINFO_3630_PORTED={COLOR_ADJUST_PTGETPTINFO_3630_PORTED}")
    print(f"  PTGETPTINFO_7AA0_PROLOGUE_PORTED={COLOR_ADJUST_PTGETPTINFO_7AA0_PROLOGUE_PORTED}")
    print(f"  PT_MERGE_BODY_PORTED={COLOR_ADJUST_PT_MERGE_BODY_PORTED}")
    print(f"  KODAKCMS_INIT_HARNESS={COLOR_ADJUST_KODAKCMS_INIT_HARNESS}")
    print(f"  KODAKCMS_LIVE_SPCOMBINE={COLOR_ADJUST_KODAKCMS_LIVE_SPCOMBINE}")
    mode103 = sp_connect_combine_mode_from_flag(KODAKCMS_SPCOMBINE_CONNECT_FLAG)
    mode_chain = ptchain_init_or_mode_800(mode103)
    print(
        f"  SpCombine flag {KODAKCMS_SPCOMBINE_CONNECT_FLAG:#x} → "
        f"mode {mode103:#x} → chain |0x800 → {mode_chain:#x} "
        f"(skip type switch={ptcombine_skip_type_switch(mode_chain)})"
    )
    print("  sat param -5..+5 →", SAT_FILES[0], "…", SAT_FILES[5], "…", SAT_FILES[10])
    for k, v in BNW_FILES.items():
        print(f"  bnw {k} → {v}")
    k, sh = unsharp_kernel_i16()
    print(f"  unsharp amount scale {UNSHARP_AMOUNT_SCALE}  kernel {UNSHARP_KERNEL_1D}")
    print(f"  kernel ints {k} shift {sh} (leaf {KERNEL_QUANT_LEAF:#x})")
    print(f"  SpCombineXforms {KODAKCMS_SP_COMBINE_XFORMS:#x} → "
          f"SpConnectSequenceEx({KODAKCMS_SPCOMBINE_CONNECT_FLAG:#x},…) "
          f"@ {KODAKCMS_SP_CONNECT_SEQUENCE_EX:#x}")
    print(f"  SpCombine IAT {SPCOMBINE_IAT:#x} thunk {SPCOMBINE_THUNK:#x} "
          f"IMAu calls {SPCOMBINE_CALL_A:#x}/{SPCOMBINE_CALL_B:#x}")
    print(f"  connect n=1 → {sp_combine_xforms_forwards_to_connect_ex(1):#x} "
          f"(too few); n=2 → {sp_combine_xforms_forwards_to_connect_ex(2)!r} "
          "(body open)")
    print(f"  prologue outs n=1 → {sp_connect_sequence_ex_prologue_outs(1)}")


if __name__ == "__main__":
    main()
