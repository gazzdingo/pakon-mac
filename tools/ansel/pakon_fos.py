#!/usr/bin/env python3
"""FOS (film-order statistics) — verified fragments (PakonIMAu.dll).

Invoked from ``ColorNegativePath::analyzeBalanceOrder`` **between** SBA
``analyzePass1`` and ``analyzePass2``. Do **not** invent dens / R² /
slope maths beyond cited closed forms.

``FOS_ANALYZE_PORTED = True`` — host ``fos_calc_results`` composes all
golden leaves (helper Δ included). ``FOS_ROLL_CALLER_PORTED`` wires
frame dens/mask/C banks → OUT (helper then paxel).
``FOS_TO_PREFERENCE_FPO_EDGE = False`` — **VERIFIED** no static copy of
FOS OUT into nested Preference ``fpo`` (``docs/48``); opening RGB stays
dpi-``fpo``. Cap/Impl COM wrappers are thin and unported on host.

Full binary report: ``docs/47-sba-fos-binary.md``.

Call chain (VERIFIED)
=====================
* Cap ``AnsFosCapability::analyze`` @ ``0x1013cb30``
  (string ``0x1058bbe0``).
  - Sets Cap ``+0xf = 1`` (analyzed flag).
  - Forwards scene smart-ptr ``[ebp+0xc]`` to Impl via Cap ``+0x14``.
* Impl ``AnsFosCapabilityImpl::analyze()`` @ ``0x1023ff80``
  (string ``0x105a0d10``; also hosts ``analyzeThis`` string
  ``0x105a0c90`` in the same body).
* ``SbaCalcFosResults`` @ ``0x1028f570`` — sole ``E8`` from Impl @
  ``0x1024087c`` (fail format ``0x105a0b88``). Returns ``0`` on success;
  non-zero error codes (below).

balanceOrder relation (VERIFIED order; Preference opening = dpi ``fpo``)
-------------------------------------------------------------
``pass1`` → **FOS analyze** → ``pass2`` → path ``setShifts``.

* FOS requires an SBA capability on the scene (error
  ``Sba capability is NULL for scene.``).
* FOS writes **OUT** at ``Impl+0x18`` only. It does **not** write
  ``scene+0x3a38`` or Preference nested opening RGB
  (``scene+0x4d0e``). Nested opening writers = dpi ctor /
  ``readAscii`` / assign (``docs/48``).
* FOS OUT → nested ``fpo``: **VERIFIED absent** static edge
  (``FOS_TO_PREFERENCE_FPO_EDGE=False``; ``docs/48``). Cap ``Impl+0x3c``
  is a dump tag only. Preference opening RGB = dpi ``fpo``.

Critical correction — ``esi`` is OUT, not Preference RGB
--------------------------------------------------------
Dens / R² stores use ``esi`` = OUT = ``&Impl+0x18`` (``SbaFOSResults``,
36 bytes), **not** the scene nested object at ``scene+0x4cf0``.

Cap dump ``0x1013c210…`` names:

* ``+0x1e`` = ``numPixels`` (store ``0x102903e6``)
* ``+0x20`` = ``gmRSquare`` (store ``0x102903a4``)
* ``+0x22`` = ``illRSquare`` (store ``0x102903ef``)

Scene nested ``+0x1e/+0x20/+0x22`` (= ``scene+0x4d0e``) are Preference
opening RGB — same offsets, **different object**. FOS is not their
runtime writer.

``SbaCalcFosResults`` args (cdecl, ``add esp, 0x28`` = 10 args)
--------------------------------------------------------------
Call site ``0x1024085a…`` (Impl ``ebx``):

| # | value |
|---|--------|
| 0 | ``[ebp-0x48]`` (word compared ``>= 1`` at entry) |
| 1 | ``0`` |
| 2 | ``&Impl+0x40`` (3×int16 RGB words at ``+0/+2/+4``) |
| 3 | ``[Impl+0x68]`` (ptr; used as ``ptr+0xdc``, word @ ``+0x18``) |
| 4 | ``0`` |
| 5 | ``0`` |
| 6 | ``[Impl+0xc]`` (``frame+0x1a`` ptr array) |
| 7 | ``[Impl+0x10]`` (``frame+0x388c`` ptr array) |
| 8 | ``[Impl+0x14]`` (``frame+0x290c`` ptr array) |
| 9 | ``&Impl+0x18`` (**OUT** ``SbaFOSResults``, 36 bytes) |

Early errors (VERIFIED): ``0x18a5`` (arg0 word ``< 1``), ``0x18a4``
(null OUT), ``0x18a1`` / ``0x18a6`` / ``0x18a7`` (null ``+0xc/+0x14/+0x10``).
Discriminant fail: ``0x189d`` @ ``0x1029006b``.

OUT layout (``SbaFOSResults`` / Cap dump names)
----------------------------------------------
| off | field |
|-----|--------|
| ``+0x00`` | ``orderFpo`` (3×i16) |
| ``+0x06`` | ``fosOrderAvg`` (3×i16) |
| ``+0x0c`` | ``fosDmin`` (3×i16) |
| ``+0x12`` | ``gmSlope`` |
| ``+0x14`` | ``gmOffset`` |
| ``+0x16`` | ``illSlope`` |
| ``+0x18`` | ``illOffset`` |
| ``+0x1a`` | ``theta`` (not stored by calc) |
| ``+0x1c`` | ``ofpoMethod`` (not stored by calc) |
| ``+0x1e`` | ``numPixels`` |
| ``+0x20`` | ``gmRSquare`` |
| ``+0x22`` | ``illRSquare`` |

Opening transform on arg2 RGB (VERIFIED @ ``0x1028f608…``)
----------------------------------------------------------
Same ``×0x186a0`` family as ``Sba()`` / ``createAlgData`` /
path ``setShifts`` (see ``pakon_sba_core.py``):

* ``Y  ~ (R+G+B)*0x186a0`` → magic ``0x306e8227``, ``sar 0xf``, bias
  ``±0x1524a``
* ``C1 ~ (2G−B−R)*0x186a0`` → magic ``0x111f883d``, ``sar 0xe``, bias
  ``±0x1de6a``
* ``C2 ~ (B−R)*0x186a0`` → magic ``0x3b510a6f``, ``sar 0xf``, bias
  ``±0x11436``

Also: ``(word[arg3+0xdc+0x18])²`` into a local (sizing).

Dens / regression
-----------------------------------------------------------
Paxel walk @ ``0x1028f980`` (host ``fos_paxel_*``; ``FOS_PAXEL_WALK_PORTED``):
dens @ arg6/``frame+0x1a``, mask @ arg8/``frame+0x290c+0xc20``, skip if
``byte[arg7+4]==1``. Accept = mask==1 AND ``(V−Δ1)²+(W−Δ2)² < R²``.
Products ``sar 5``. Frame merge if ``N_frame >= word[arg3+0xdc+0x2e]``.

Covariance ``Cov = 32·P − (Σa·Σb)/N`` (UV R² @ ``0x1029034a``; RGB eigen
also ``fchs`` — see ``cov_numer_from_scaled``), then R² / slopes.

**Ported dens leaves:** paxel walk + covariance + R² + orderAvg +
slopes/offsets + RGB max-eigen unit + helper ``orderFpo`` Δ
@ ``0x1028f250`` + host ``fos_calc_results`` compose
(``FOS_ANALYZE_PORTED``). Host roll: ``fos_analyze_roll``
(``FOS_ROLL_CALLER_PORTED``). Preference nested ``fpo``: no static FOS
edge (``FOS_TO_PREFERENCE_FPO_EDGE=False``; ``docs/48``).


Impl result / history (VERIFIED fragments)
------------------------------------------
* ``Impl+0x18`` … ``+0x3b``: ``SbaFOSResults`` / history block.
  - History path: ``rep movsd`` from stack → ``+0x18``; ``+0x3c = 1``.
  - Calc success: ``+0x3c = 0``; OUT filled via ``esi=&+0x18``.
* Post-calc packs ``word[+0x9c/+0x9e/+0xa0]`` + ``+0x18`` block via
  ``0x1023fd20``.
* ``+0xa0`` preset: ``0`` if name at ``+0x70`` equals ``"sba"``, else
  ``1`` (@ ``0x102405d9``).
* Flags ``+0x94/+0x95`` gate history vs calc.

Ported below
------------
Arg validation + RGB opening three-axis + ``fosDmin`` + dens paxel
walk (Σ/P) + covariance + R² + ``fosOrderAvg`` + slopes/offsets +
RGB max-eigen unit + helper Δ + full OUT compose
(``fos_calc_results`` / ``FOS_ANALYZE_PORTED``).
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass, fields

FOS_ANALYZE_PORTED = True  # PakonIMAu.dll SbaCalcFosResults host compose
FOS_ANALYZE_PARTIAL_PORTED = True  # PakonIMAu.dll leaves wired; Δ injected
FOS_ROLL_CALLER_PORTED = True  # PakonIMAu.dll host roll → OUT (helper then paxel)
# Nested Preference fpo — docs/48: VERIFIED no static OUT → scene+0x4d0e
FOS_TO_PREFERENCE_FPO_EDGE = False  # Cap Impl+0x3c dump tag only; dpi fpo writers
FOS_OPENING_TRANSFORM_PORTED = True  # PakonIMAu.dll @ 0x1028f608 fragment
FOS_RSQUARE_PORTED = True  # PakonIMAu.dll @ 0x10290332 (gm/ill R²)
FOS_ORDER_AVG_PORTED = True  # PakonIMAu.dll @ 0x10290290 (fosOrderAvg)
FOS_SLOPES_OFFSETS_PORTED = True  # PakonIMAu.dll @ 0x10290216 (slopes+offsets)
FOS_EIGEN_PORTED = True  # PakonIMAu.dll @ 0x1028fe61 → unit max-eigen
FOS_PAXEL_WALK_PORTED = True  # PakonIMAu.dll @ 0x1028f980…fe55 (Unicorn @ 0x1028f9a8)
FOS_ORDER_FPO_COMPOSE_PORTED = True  # PakonIMAu.dll @ 0x1028f890 open+Δ→i16
FOS_ORDER_FPO_HELPER_PORTED = True  # PakonIMAu.dll @ 0x1028f250 means→Δ (Unicorn)
FOS_POSTFILL_C_PORTED = True  # PakonIMAu.dll @ 0x102b7440 idiv C banks (+0x4c/50/7bc/7c0/9cc)

# PakonIMAu.dll code VAs (base 0x10000000)
CAP_ANALYZE = 0x1013CB30  # PakonIMAu.dll AnsFosCapability::analyze
IMPL_ANALYZE = 0x1023FF80  # PakonIMAu.dll AnsFosCapabilityImpl::analyze
SBA_CALC_FOS_RESULTS = 0x1028F570  # PakonIMAu.dll SbaCalcFosResults
SBA_CALC_FOS_CALL_SITE = 0x1024087C  # PakonIMAu.dll E8 → calc from Impl
IMPL_PACK_RESULT = 0x1023FD20  # PakonIMAu.dll post-calc pack
CAP_DUMP_FOS_RESULTS = 0x1013C210  # PakonIMAu.dll Cap dump field names

# Impl layout (CapabilityImpl) — PakonIMAu.dll offsets on Impl*
IMPL_PTR_0C = 0x0C  # PakonIMAu.dll frame+0x1a ptr array
IMPL_PTR_10 = 0x10  # PakonIMAu.dll frame+0x388c ptr array
IMPL_PTR_14 = 0x14  # PakonIMAu.dll frame+0x290c ptr array
IMPL_RESULT_BLOCK = 0x18  # PakonIMAu.dll SbaFOSResults OUT / history
IMPL_RESULT_FLAG = 0x3C  # PakonIMAu.dll 1=history, 0=after calc
IMPL_RGB40 = 0x40  # PakonIMAu.dll 3×int16 calc arg2
IMPL_PTR_68 = 0x68  # PakonIMAu.dll +0xdc size-word subobject

# Cap — PakonIMAu.dll AnsFosCapability
CAP_ANALYZED_FLAG = 0x0F  # PakonIMAu.dll Cap+0xf analyzed
CAP_IMPL_PTR = 0x14  # PakonIMAu.dll Cap → Impl*

# OUT / SbaFOSResults — PakonIMAu.dll Cap dump @ 0x1013c210
FOS_OFF_ORDER_FPO = 0x00  # PakonIMAu.dll OUT+0x00 orderFpo 3×i16
FOS_OFF_ORDER_AVG = 0x06  # PakonIMAu.dll OUT+0x06 fosOrderAvg 3×i16
FOS_OFF_DMIN = 0x0C  # PakonIMAu.dll OUT+0x0c fosDmin 3×i16
FOS_OFF_GM_SLOPE = 0x12  # PakonIMAu.dll OUT+0x12 gmSlope store @ 0x102902f4
FOS_OFF_GM_OFFSET = 0x14  # PakonIMAu.dll OUT+0x14 gmOffset store @ 0x10290312
FOS_OFF_ILL_SLOPE = 0x16  # PakonIMAu.dll OUT+0x16 illSlope store @ 0x1029031d
FOS_OFF_ILL_OFFSET = 0x18  # PakonIMAu.dll OUT+0x18 illOffset store @ 0x10290336
FOS_OFF_THETA = 0x1A  # PakonIMAu.dll OUT+0x1a (not stored by calc body)
FOS_OFF_OFPO_METHOD = 0x1C  # PakonIMAu.dll OUT+0x1c ofpoMethod — helper @ 0x1028f28a/4d3/4fa
FOS_OFF_NUM_PIXELS = 0x1E  # PakonIMAu.dll OUT+0x1e store @ 0x102903e6
FOS_OFF_GM_RSQUARE = 0x20  # PakonIMAu.dll OUT+0x20 store @ 0x102903a4
FOS_OFF_ILL_RSQUARE = 0x22  # PakonIMAu.dll OUT+0x22 store @ 0x102903ef
FOS_RESULTS_SIZE = 0x24  # PakonIMAu.dll sizeof SbaFOSResults

# Shared with Sba / createAlgData / setShifts — PakonIMAu.dll opening @ 0x1028f608
RGB_SCALE = 0x186A0  # PakonIMAu.dll ×100000 in opening axes
MAGIC_Y = 0x306E8227  # PakonIMAu.dll Y magic @ opening
MAGIC_C1 = 0x111F883D  # PakonIMAu.dll C1 magic @ opening
MAGIC_C2 = 0x3B510A6F  # PakonIMAu.dll C2 magic @ opening
BIAS_Y = 0x1524A  # PakonIMAu.dll Y bias ±
BIAS_C1 = 0x1DE6A  # PakonIMAu.dll C1 bias ±
BIAS_C2 = 0x11436  # PakonIMAu.dll C2 bias ±

# Dens / R² / slope rdata — PakonIMAu.dll .rdata qword VAs
F64_32 = 32.0  # PakonIMAu.dll @ 0x105a7280
F64_1000 = 1000.0  # PakonIMAu.dll @ 0x105a3c18 — R² scale
F64_10000 = 10000.0  # PakonIMAu.dll @ 0x105a7258 — slope scale
# Not exact 1/√n — qword bits from PakonIMAu.dll (DLL ≠ math.sqrt)
F64_INV_SQRT3 = struct.unpack("<d", bytes.fromhex("d8f3ea46a779e23f"))[0]  # PakonIMAu.dll @ 0x105a6f38
F64_INV_SQRT6 = struct.unpack("<d", bytes.fromhex("ac32b477bd20da3f"))[0]  # PakonIMAu.dll @ 0x105a6f30
F64_INV_SQRT2 = struct.unpack("<d", bytes.fromhex("4e88655c9ea0e63f"))[0]  # PakonIMAu.dll @ 0x105a6f28
F64_ONE = 1.0  # PakonIMAu.dll @ 0x10574f50
# Eigen trig cubic rdata — PakonIMAu.dll
F64_THREE = 3.0  # PakonIMAu.dll @ 0x10578468
F64_ONE_NINTH = struct.unpack("<d", bytes.fromhex("1cc7711cc771bc3f"))[0]  # PakonIMAu.dll @ 0x1058f6c0
F64_ONE_54 = struct.unpack("<d", bytes.fromhex("682fa1bd84f6923f"))[0]  # PakonIMAu.dll @ 0x105a7270 = 1/54
F64_27 = 27.0  # PakonIMAu.dll @ 0x105a7278
F64_9 = 9.0  # PakonIMAu.dll @ 0x10578968
F64_ONE_THIRD = struct.unpack("<d", bytes.fromhex("555555555555d53f"))[0]  # PakonIMAu.dll @ 0x105943c0
F64_NEG_TWO = -2.0  # PakonIMAu.dll @ 0x10578470
F64_NEG_HALF = -0.5  # PakonIMAu.dll @ 0x1057ae70
F64_SQRT3_2 = struct.unpack("<d", bytes.fromhex("912b50e67ab6eb3f"))[0]  # PakonIMAu.dll @ 0x105a7268
F64_NEG_SQRT3_2 = struct.unpack("<d", bytes.fromhex("912b50e67ab6ebbf"))[0]  # PakonIMAu.dll @ 0x105a7260
RSQUARE_ENTRY = 0x10290332  # PakonIMAu.dll gmRSquare leaf entry
ORDER_AVG_ENTRY = 0x10290290  # PakonIMAu.dll fosOrderAvg leaf entry
SLOPES_OFFSETS_ENTRY = 0x10290216  # PakonIMAu.dll Y/C1/C2→slopes (FPU st0=dG,st1=dB,st2=dR)
EIGEN_ENTRY = 0x1028FE61  # PakonIMAu.dll RGB dens cov → unit max-eigen
SIGN_FLIP_ENTRY = 0x102901B3  # PakonIMAu.dll force d_R ≥ 0
EIGEN_AFTER_SIGN = 0x102901E0  # PakonIMAu.dll after sign; FPU st0=dG,st1=dB,st2=dR
ACOS_THUNK = 0x105001D2  # PakonIMAu.dll jmp [IAT _CIacos]
ACOS_IAT = 0x1057349C  # PakonIMAu.dll IAT slot for _CIacos
FTOL2 = 0x104FFE44  # PakonIMAu.dll MSVC _ftol2 (R² round / dens chop)
PAXEL_ENTRY = 0x1028F980  # PakonIMAu.dll dens frame walk (arg arrays)
PAXEL_FRAME_INIT = 0x1028F9A8  # PakonIMAu.dll zero frame Σ/P; row/col walk
PAXEL_AFTER_FRAME = 0x1028FCCC  # PakonIMAu.dll N_frame vs word[arg3+0xdc+0x2e]
PAXEL_MERGE = 0x1028FCE3  # PakonIMAu.dll add frame Σ/P into global
HELPER_ORDER_FPO = 0x1028F250  # PakonIMAu.dll orderFpo Δ helper
HELPER_ISQRT = 0x1028F1B0  # PakonIMAu.dll nested weight/isqrt for helper
POSTFILL_C = 0x102B7440  # PakonIMAu.dll Sba postfill C banks
POSTFILL_IDIV = 0x102B7669  # PakonIMAu.dll cdq; idiv ebp
DIV1000_MAGIC = 0x10624DD3  # PakonIMAu.dll @ 0x1028f523 — /1000 (sar 6)
ORDER_FPO_DELTA0_BIAS = 0x498  # PakonIMAu.dll @ 0x1028f509 add edx,0x498
ERR_HELPER = 0x18A7  # PakonIMAu.dll helper null-*[arg1] @ 0x1028f432
OUT290C_OFF_C1 = 0x4C  # PakonIMAu.dll low C1
OUT290C_OFF_C2 = 0x50  # PakonIMAu.dll low C2
OUT290C_OFF_C1_HI = 0x7BC  # PakonIMAu.dll alt C1
OUT290C_OFF_C2_HI = 0x7C0  # PakonIMAu.dll alt C2
OUT290C_OFF_GATE = 0x9CC  # PakonIMAu.dll dword ← sx(OUT+6)
STATS_OFF_C1 = 0x40  # PakonIMAu.dll stats Σ low C1
STATS_OFF_C2 = 0x44  # PakonIMAu.dll stats Σ low C2
STATS_OFF_C1_HI = 0x820  # PakonIMAu.dll stats Σ high C1
STATS_OFF_C2_HI = 0x824  # PakonIMAu.dll stats Σ high C2
COUNTS_OFF_N0 = 0x00  # PakonIMAu.dll counts N0
COUNTS_OFF_NHI = 0x1C  # PakonIMAu.dll counts N_hi
POSTFILL_FORCE_N = 0x360  # PakonIMAu.dll @ 0x102b75e7
DC_OFF_GATE = 0x0E  # PakonIMAu.dll dc+0xe
# Helper dc / weight-table words — PakonIMAu.dll @ 0x1028f250 / 0x1028f1b0
DC_OFF_W_GM = 0x1C  # PakonIMAu.dll dc+0x1c → blend w for Δ1
DC_OFF_W_ILL = 0x1E  # PakonIMAu.dll dc+0x1e → blend w for Δ2
DC_OFF_RADIUS = 0x20  # PakonIMAu.dll dc+0x20 → R; R² = R·R
DC_OFF_THRESH_N = 0x2C  # PakonIMAu.dll dc+0x2c → unweighted count thresh
DC_OFF_PAXEL_R = 0x18  # PakonIMAu.dll dc+0x18 → paxel R; R² at calc entry
DC_OFF_PAXEL_N = 0x2E  # PakonIMAu.dll dc+0x2e → frame N merge thresh
# Weight LUT on helper arg3 (= calc arg2 / &Impl+0x40) — PakonIMAu.dll @ 0x1028f1b0
WTAB_OFF_LO = 0x1C  # PakonIMAu.dll ebx≤lo → return hi_w
WTAB_OFF_MID = 0x1E  # PakonIMAu.dll ebx≥mid → return mid_w
WTAB_OFF_MID_W = 0x20  # PakonIMAu.dll return when ebx≥mid
WTAB_OFF_HI_W = 0x22  # PakonIMAu.dll return when ebx≤lo
WTAB_OFF_ENABLE = 0x24  # PakonIMAu.dll ≠0 enables weighted Σ path
# frame+0x290c object (helper) — PakonIMAu.dll @ 0x1028f2f7…
OBJ290C_OFF_FID = 0x04  # PakonIMAu.dll byte[388c_obj+4]==1 → skip
DMIN_OPEN_OFF_R = 0x00  # PakonIMAu.dll Δ0 base
DMIN_OPEN_OFF_C1 = 0x10  # PakonIMAu.dll centre / blend C1
DMIN_OPEN_OFF_C2 = 0x14  # PakonIMAu.dll centre / blend C2

# Dens paxel walk constants — PakonIMAu.dll @ 0x1028f9a8…fcc6
PAXEL_IDX0 = 0x25  # PakonIMAu.dll @ 0x1028f9a8 row/col base index
PAXEL_ROW_STEP = 0x24  # PakonIMAu.dll @ 0x1028fcb7 add ecx,0x24
PAXEL_ROW_END = 0x33D  # PakonIMAu.dll @ 0x1028fcba cmp cx,0x33d
PAXEL_NCOLS = 0x22  # PakonIMAu.dll @ 0x1028fa39 mov …,0x22
# Planes: [eax+edi*2+disp] — disp is BYTES (`0x1028fa4e`); 0x6c0 B = 0x360 words = 36×24
PAXEL_PLANE_BYTES = 0x6C0  # PakonIMAu.dll byte stride between planes
PAXEL_PLANE_WORDS = 0x360  # PakonIMAu.dll PAXEL_PLANE_BYTES // 2
PAXEL_MASK_OFF = 0xC20  # PakonIMAu.dll @ 0x1028fab7 byte [edi+mask+0xc20]
# Word offsets from dens base (arg6 / frame+0x1a) — PakonIMAu.dll @ 0x1028fa4e…
PAXEL_OFF_R = 0x0
PAXEL_OFF_G = 0x360  # +0x6c0 bytes
PAXEL_OFF_B = 0x6C0  # +0xd80 bytes
PAXEL_OFF_U = 0xA20  # +0x1440 bytes
PAXEL_OFF_V = 0xD80  # +0x1b00 bytes
PAXEL_OFF_W = 0x10E0  # +0x21c0 bytes

# SbaCalcFosResults errors — PakonIMAu.dll eax codes
ERR_ARG0 = 0x18A5  # PakonIMAu.dll arg0 word < 1
ERR_NULL_OUT = 0x18A4  # PakonIMAu.dll null OUT
ERR_NULL_0C = 0x18A1  # PakonIMAu.dll null Impl+0xc
ERR_NULL_14 = 0x18A6  # PakonIMAu.dll null Impl+0x14
ERR_NULL_10 = 0x18A7  # PakonIMAu.dll null Impl+0x10
ERR_DISC = 0x189D  # PakonIMAu.dll FPU discriminant fail @ 0x1029006b

STR_CAP_ANALYZE = 0x1058BBE0  # PakonIMAu.dll Cap::analyze name
STR_IMPL_ANALYZE = 0x105A0D10  # PakonIMAu.dll Impl::analyze name
STR_CALC_FAIL = 0x105A0B88  # PakonIMAu.dll calc-fail format
STR_AFTER_SCP_LUT_FOS = 0x10574134  # PakonIMAu.dll afterSCPLutFos string


def _i16(x: int) -> int:
    x &= 0xFFFF
    return x - 0x10000 if x >= 0x8000 else x


def _i32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x >= 0x80000000 else x


def _msvc_magic_div(value: int, magic: int, sar: int) -> int:
    """``imul magic; sar edx,N; add (edx>>31)`` — PakonIMAu.dll @ ``0x1028f64d``…"""
    a = _i32(value)
    b = _i32(magic)
    prod = a * b
    edx = prod >> 32
    edx = edx >> sar  # PakonIMAu.dll sar edx,N
    return int(edx + ((edx >> 31) & 1))  # PakonIMAu.dll add (edx>>31)


def _biased_scale(rgb_term: int, bias: int) -> int:
    t = int(rgb_term) * RGB_SCALE  # PakonIMAu.dll ×0x186a0
    return t + bias if t >= 0 else t - bias  # PakonIMAu.dll ±bias


def fos_opening_axes(r: int, g: int, b: int) -> tuple[int, int, int]:
    """``SbaCalcFosResults`` opening — PakonIMAu.dll @ ``0x1028f608``.

    Inputs are the three ``int16`` words at calc ``arg2`` (``Impl+0x40``).
    Does **not** include dens/FPU body or slope/R² fill.
    """
    r, g, b = _i16(r), _i16(g), _i16(b)
    # PakonIMAu.dll @ 0x1028f608… — Y / C1 / C2
    y = _msvc_magic_div(_biased_scale(r + g + b, BIAS_Y), MAGIC_Y, 0xF)
    c1 = _msvc_magic_div(_biased_scale(2 * g - b - r, BIAS_C1), MAGIC_C1, 0xE)
    c2 = _msvc_magic_div(_biased_scale(b - r, BIAS_C2), MAGIC_C2, 0xF)
    return y, c1, c2


def _axis_to_code(axis: int, bias: int, magic: int, sar: int, scale: int = RGB_SCALE) -> int:
    """setShifts merge — PakonIMAu.dll @ ``0x10100651`` family."""
    t = int(axis) * int(scale)
    return _msvc_magic_div(t + bias if t >= 0 else t - bias, magic, sar)


def fos_opening_axes_inverse(y: int, c1: int, c2: int) -> tuple[int, int, int]:
    """Integer inverse of ``fos_opening_axes`` — PakonIMAu.dll setShifts @ ``0x10100651``….

    Exact on many triples; magic division can leave ±1 LSB on round-trip.
    Reconstruct (VERIFIED):

    * ``R = Yc − C1c − C2c``
    * ``G = Yc + magic_c1(C1·0x30d40 ± bias)``
    * ``B = Yc − C1c + C2c``
    """
    yc = _axis_to_code(y, BIAS_Y, MAGIC_Y, 0xF)  # PakonIMAu.dll @ 0x10100651…
    c1c = _axis_to_code(c1, BIAS_C1, MAGIC_C1, 0xE)
    c2c = _axis_to_code(c2, BIAS_C2, MAGIC_C2, 0xF)
    c1x2 = _axis_to_code(c1, BIAS_C1, MAGIC_C1, 0xE, scale=0x30D40)
    r = yc - c1c - c2c
    g = yc + c1x2
    b = yc - c1c + c2c
    return r, g, b


def fos_dmin_min(
    frame_rgb_triples: list[tuple[int, int, int]],
) -> tuple[int, int, int]:
    """OUT ``+0xc`` ``fosDmin`` — PakonIMAu.dll @ ``0x1028f6d8…740``.

    First frame copy, then component-wise min if ``arg0 > 1``.
    Inputs are the 3×i16 at each ``frame+0x290c``.
    """
    if not frame_rgb_triples:
        raise ValueError("fos_dmin_min requires at least one frame")
    # PakonIMAu.dll @ 0x1028f6d8…740 — component-wise min
    r = min(t[0] for t in frame_rgb_triples)
    g = min(t[1] for t in frame_rgb_triples)
    b = min(t[2] for t in frame_rgb_triples)
    return r, g, b


def fos_dmin_minus_open(
    fos_dmin: tuple[int, int, int],
    open_rgb: tuple[int, int, int],
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """dmin−open RGB + Y/C1/C2 — PakonIMAu.dll @ ``0x1028f750…864``.

    Returns ``((dR,dG,dB), (Y,C1,C2))``. Helper Δ0 uses ``dR``; blend /
    fallback centres use ``C1/C2``.
    """
    # PakonIMAu.dll @ 0x1028f750…76f — word sub then movsx
    dr = _i16(_i16(fos_dmin[0]) - _i16(open_rgb[0]))
    dg = _i16(_i16(fos_dmin[1]) - _i16(open_rgb[1]))
    db = _i16(_i16(fos_dmin[2]) - _i16(open_rgb[2]))
    axes = fos_opening_axes(dr, dg, db)  # PakonIMAu.dll @ 0x1028f772…864
    return (dr, dg, db), axes


def fos_cov(sum_a: int, sum_b: int, p_ab_sar5: int, n: int) -> float:
    """Dens cov — PakonIMAu.dll UV R² path @ ``0x1029034a`` (no ``fchs``).

    ``Cov(A,B) = 32·P − (ΣA·ΣB)/N`` where ``P`` is the ``sar 5`` product
    accumulator. Equals ``Σ(a−ā)(b−ḃ)`` when ``P = Σ(ab)/32``.
    """
    if n == 0:
        raise ZeroDivisionError("fos_cov: n == 0")
    # PakonIMAu.dll @ 0x1029034a — fmul 32; fsub (ΣΣ)/N
    return F64_32 * float(p_ab_sar5) - (float(sum_a) * float(sum_b)) / float(n)


def cov_numer_from_scaled(
    sum_a: int, sum_b: int, sum_ab_div32: int, n: int
) -> float:
    """RGB eigen path — PakonIMAu.dll @ ``0x1028fe7f…`` (``fmul 32``, ``fsubp``, ``fchs``).

    Returns ``(ΣA·ΣB)/N − 32·P`` = ``−fos_cov(...)``. Prefer ``fos_cov`` for
    R²; keep this name for older call sites.
    """
    return -fos_cov(sum_a, sum_b, sum_ab_div32, n)  # PakonIMAu.dll fchs after cov


def round_msvc_104ffe44(x: float) -> int:
    """PakonIMAu.dll ``_ftol2`` @ ``0x104ffe44`` on dens R² — round-nearest.

    OrderAvg / slopes / offsets use the same VA via ``ftol2_chop``
    (trunc toward zero); do not reuse this for those leaves.
    """
    if not math.isfinite(x):
        return -0x80000000
    # PakonIMAu.dll @ 0x104ffe44 — R² path matches round-nearest
    return int(math.floor(x + 0.5)) if x >= 0.0 else int(math.ceil(x - 0.5))


def ftol2_chop(x: float) -> int:
    """PakonIMAu.dll MSVC ``_ftol2`` chop toward zero @ ``0x104ffe44`` (orderAvg/slopes)."""
    if not math.isfinite(x):
        return -0x80000000
    return int(x)  # PakonIMAu.dll @ 0x104ffe44 — trunc toward 0


def fos_order_avg(
    open_rgb: tuple[int, int, int],
    mean_dens: tuple[float, float, float],
) -> tuple[int, int, int]:
    """OUT ``+0x06`` ``fosOrderAvg`` — PakonIMAu.dll @ ``0x10290290…02de``.

    ``fosOrderAvg[ch] = trunc(openRGB[ch] + mean_d[ch])``.
    """
    # PakonIMAu.dll @ 0x10290290 — fild open; fadd mean; call 0x104ffe44; mov [esi+6/8/a]
    return tuple(
        ftol2_chop(float(o) + float(m)) for o, m in zip(open_rgb, mean_dens)
    )  # type: ignore[return-value]


def fos_fix_eigen_sign(
    d_r: float, d_g: float, d_b: float
) -> tuple[float, float, float]:
    """Max-eigen unit vector sign — PakonIMAu.dll @ ``0x102901b3…01d7``."""
    if d_r < 0.0:  # PakonIMAu.dll @ 0x102901b3 — fcomp 0; test ah,5
        return -d_r, -d_g, -d_b  # PakonIMAu.dll fchs on dR/dG/dB
    return d_r, d_g, d_b


def fos_rgb_cov_matrix(
    n: int,
    sum_r: int,
    sum_g: int,
    sum_b: int,
    p_rg: int,
    p_rb: int,
    p_gb: int,
    p_rr: int,
    p_gg: int,
    p_bb: int,
) -> tuple[float, float, float, float, float, float]:
    """True RGB dens Cov — PakonIMAu.dll @ ``0x1028fe7f…`` (ignore off-diag ``fchs``).

    Returns ``(C_RR, C_GG, C_BB, C_RG, C_RB, C_GB)`` with
    ``C(a,b) = 32·P − (Σa·Σb)/N``.
    """
    # PakonIMAu.dll @ 0x1028fe7f — fmul 32; fsub (ΣΣ)/N; diag keep +, off fchs store only
    c_rr = fos_cov(sum_r, sum_r, p_rr, n)
    c_gg = fos_cov(sum_g, sum_g, p_gg, n)
    c_bb = fos_cov(sum_b, sum_b, p_bb, n)
    c_rg = fos_cov(sum_r, sum_g, p_rg, n)
    c_rb = fos_cov(sum_r, sum_b, p_rb, n)
    c_gb = fos_cov(sum_g, sum_b, p_gb, n)
    return c_rr, c_gg, c_bb, c_rg, c_rb, c_gb


def fos_rgb_max_eigen_unit(
    n: int,
    sum_r: int,
    sum_g: int,
    sum_b: int,
    p_rg: int,
    p_rb: int,
    p_gb: int,
    p_rr: int,
    p_gg: int,
    p_bb: int,
) -> tuple[float, float, float]:
    """Unit max-eigen vector — PakonIMAu.dll @ ``0x1028fe61…01e0``.

    Trig cubic via ``_CIacos`` (IAT ``0x1057349c``); pick ``min(tr−λ)`` =
    ``λ_max``; free ``B=1``; normalize; force ``d_R ≥ 0``.
    Raises ``ValueError`` with ``ERR_DISC`` when discriminant fails
    (PakonIMAu.dll @ ``0x1029006b`` → ``eax=0x189d``).
    """
    if n == 0:
        raise ZeroDivisionError("fos_rgb_max_eigen_unit: n == 0")
    c_rr, c_gg, c_bb, c_rg, c_rb, c_gb = fos_rgb_cov_matrix(
        n, sum_r, sum_g, sum_b, p_rg, p_rb, p_gb, p_rr, p_gg, p_bb
    )
    tr = c_rr + c_gg + c_bb  # PakonIMAu.dll @ 0x1028ff65…
    i2 = (
        c_rr * c_gg
        + c_rr * c_bb
        + c_gg * c_bb
        - (c_rg * c_rg + c_rb * c_rb + c_gb * c_gb)
    )  # PakonIMAu.dll @ 0x1028ff78…ffba
    i3 = (
        c_rr * (c_gg * c_bb - c_gb * c_gb)
        - c_rg * (c_rg * c_bb - c_gb * c_rb)
        + c_rb * (c_rg * c_gb - c_gg * c_rb)
    )  # PakonIMAu.dll I₃ mix @ 0x1028ffdb…003e → det(C)
    # p = I₂ − tr²/3 ; q = −I₃ + (−2 tr³ + 9 tr I₂)/27
    # DLL: +0x154 = −p/3 ; +0x48 = −q/2  (PakonIMAu.dll @ 0x1028ffbc…003e)
    minus_p_over_3 = (tr * tr - F64_THREE * i2) * F64_ONE_NINTH
    # −q/2 from DLL *1/54 path; closed: −q/2 = I₃/2 − (−2 tr³ + 9 tr I₂)/54
    minus_q_over_2 = 0.5 * i3 - (-2.0 * (tr**3) + F64_9 * tr * i2) * F64_ONE_54
    # Disc: (−q/2)² > (−p/3)³ → ERR_DISC — PakonIMAu.dll @ 0x10290044…06b
    if minus_q_over_2 * minus_q_over_2 > minus_p_over_3 * minus_p_over_3 * minus_p_over_3:
        raise ValueError(f"fos eigen disc fail {ERR_DISC:#x}")
    r = math.sqrt(minus_p_over_3)  # PakonIMAu.dll @ 0x1029009c fsqrt (−p/3)
    cos_th = minus_q_over_2 / (r * r * r)  # PakonIMAu.dll @ 0x1029007e fdivr
    cos_th = max(-1.0, min(1.0, cos_th))
    theta = math.acos(cos_th)  # PakonIMAu.dll @ 0x10290082 → _CIacos
    phi = theta * F64_ONE_THIRD  # PakonIMAu.dll @ 0x102900a8 * (1/3)
    c_phi = math.cos(phi)  # PakonIMAu.dll @ 0x102900b0 fcos
    s_phi = math.sin(phi)  # PakonIMAu.dll @ 0x102900b6 fsin
    # cos(φ), cos(φ±120°) — PakonIMAu.dll @ 0x102900bc…0e2
    # cos(φ+120)=−½cos−(√3/2)sin ; cos(φ−120)=−½cos+(√3/2)sin
    cos0 = c_phi
    cos1 = F64_NEG_HALF * c_phi - F64_SQRT3_2 * s_phi
    cos2 = F64_NEG_HALF * c_phi + F64_SQRT3_2 * s_phi
    # σ_k = (−2 R)·cos_k − (−2 tr/3) = −2 R cos + 2 tr/3 — PakonIMAu.dll @ 0x102900cc…0f0
    two_tr_over_3 = -F64_NEG_TWO * tr * F64_ONE_THIRD
    sigs = [F64_NEG_TWO * r * ck + two_tr_over_3 for ck in (cos0, cos1, cos2)]
    sigma = min(sigs)  # PakonIMAu.dll @ 0x102900f2…118 — min σ → λ_max
    lam = tr - sigma  # PakonIMAu.dll λ = tr − σ
    d_rr = lam - c_rr  # PakonIMAu.dll @ 0x10290125 → esp+0x10
    d_gg = lam - c_gg  # PakonIMAu.dll @ 0x1029011f → esp+0x30
    denom = d_rr * d_gg - c_rg * c_rg  # PakonIMAu.dll @ 0x10290131…139
    inv = F64_ONE / denom  # PakonIMAu.dll @ 0x10290140 fdivr 1.0
    # free B=1 — PakonIMAu.dll @ 0x1029014a…170
    d_r = (c_rg * c_gb - (c_gg - lam) * c_rb) * inv
    d_g = (c_rb * c_rg - (c_rr - lam) * c_gb) * inv
    d_b = 1.0
    nrm = math.sqrt(d_r * d_r + d_g * d_g + d_b * d_b)  # PakonIMAu.dll @ 0x1029017b…18b
    scale = F64_ONE / nrm  # PakonIMAu.dll @ 0x1029018d…195
    d_r *= scale
    d_g *= scale
    d_b = scale
    return fos_fix_eigen_sign(d_r, d_g, d_b)  # PakonIMAu.dll @ 0x102901b3


def fos_yc1c2_from_rgb(d_r: float, d_g: float, d_b: float) -> tuple[float, float, float]:
    """Float Y/C1/C2 — PakonIMAu.dll @ ``0x10290216…28a`` (rdata ``0x105a6f38/30/28``).

    ``Y  = (R+G+B)·k3``, ``C1 = (2G−B−R)·k6``, ``C2 = (B−R)·k2``.
    """
    y = (d_r + d_g + d_b) * F64_INV_SQRT3  # PakonIMAu.dll @ 0x10290216
    c1 = (2.0 * d_g - d_b - d_r) * F64_INV_SQRT6  # PakonIMAu.dll @ 0x10290229
    c2 = (d_b - d_r) * F64_INV_SQRT2  # PakonIMAu.dll @ 0x1029023c fsubrp; 0x10290283 for means
    return y, c1, c2


def fos_gm_ill_slopes_offsets(
    eigen_rgb: tuple[float, float, float],
    mean_dens: tuple[float, float, float],
    *,
    apply_sign: bool = True,
) -> tuple[int, int, int, int]:
    """OUT ``+0x12…+0x18`` gm/ill slope+offset — PakonIMAu.dll @ ``0x102902d1…0336``.

    ``eigen_rgb`` is the unit max-eigen vector ``(d_R, d_G, d_B)``.
    Sign flip (``d_R >= 0``) applied when ``apply_sign``.

    ::

        gmSlope  = trunc(10000 · C1_e)
        illSlope = trunc(10000 · C2_e)
        gmOffset = trunc(C1_m − (C1_e / Y_e) · Y_m)
        illOffset = trunc(C2_m − (C2_e / Y_e) · Y_m)
    """
    dr, dg, db = eigen_rgb
    if apply_sign:
        dr, dg, db = fos_fix_eigen_sign(dr, dg, db)  # PakonIMAu.dll @ 0x102901b3
    y_e, c1_e, c2_e = fos_yc1c2_from_rgb(dr, dg, db)  # PakonIMAu.dll @ 0x10290216
    mr, mg, mb = mean_dens
    y_m, c1_m, c2_m = fos_yc1c2_from_rgb(mr, mg, mb)  # PakonIMAu.dll @ 0x10290244…28a
    gm_slope = ftol2_chop(F64_10000 * c1_e)  # PakonIMAu.dll @ 0x102902d1 → esi+0x12
    ill_slope = ftol2_chop(F64_10000 * c2_e)  # PakonIMAu.dll @ 0x1029030a → esi+0x16
    inv_ye = F64_ONE / y_e  # PakonIMAu.dll @ 0x102902e7 fld1; fdiv Y_e
    gm_off = ftol2_chop(c1_m - (c1_e * inv_ye) * y_m)  # PakonIMAu.dll @ 0x102902f8…305
    ill_off = ftol2_chop(c2_m - (c2_e * inv_ye) * y_m)  # PakonIMAu.dll @ 0x1029031b…325
    return gm_slope, gm_off, ill_slope, ill_off


def fos_rsquare(
    sum_u: int,
    sum_v: int,
    p_uv: int,
    p_uu: int,
    p_vv: int,
    n: int,
) -> int:
    """Shared R² — PakonIMAu.dll @ ``0x10290332…a4`` (Unicorn-golden).

    ``round(1000 · Cov(U,V)² / (Var(U)·Var(V)))``.
    """
    if n == 0:
        return 0
    cov = fos_cov(sum_u, sum_v, p_uv, n)  # PakonIMAu.dll @ 0x1029034a
    var_u = fos_cov(sum_u, sum_u, p_uu, n)
    var_v = fos_cov(sum_v, sum_v, p_vv, n)
    if var_u == 0.0 or var_v == 0.0:
        return 0
    # PakonIMAu.dll @ 0x10290332… — *1000; / (var·var); call 0x104ffe44
    return round_msvc_104ffe44(F64_1000 * (cov * cov) / (var_u * var_v))


def fos_gm_rsquare(
    sum_u: int,
    sum_v: int,
    p_uv: int,
    p_uu: int,
    p_vv: int,
    n: int,
) -> int:
    """OUT ``+0x20`` ``gmRSquare`` — PakonIMAu.dll store @ ``0x102903a4`` (Cov U,V)."""
    return fos_rsquare(sum_u, sum_v, p_uv, p_uu, p_vv, n)


def fos_ill_rsquare(
    sum_u: int,
    sum_w: int,
    p_uw: int,
    p_uu: int,
    p_ww: int,
    n: int,
) -> int:
    """OUT ``+0x22`` ``illRSquare`` — PakonIMAu.dll store @ ``0x102903ef`` (Cov U,W)."""
    return fos_rsquare(sum_u, sum_w, p_uw, p_uu, p_ww, n)


def _sar5(prod: int) -> int:
    """Arithmetic ``sar 5`` — PakonIMAu.dll @ ``0x1028fb6a`` family."""
    return int(prod) >> 5  # PakonIMAu.dll sar ebx,5


def _i16_sub_u16(dens_u16: int, open_i16: int) -> int:
    """``mov dens; sub word open; movsx`` — PakonIMAu.dll @ ``0x1028fa4e…fb11``.

    Dens word is uint16; open low 16 bits subtract with wrap; result
    sign-extended to i32 for Σ/P.
    """
    return _i16(((dens_u16 & 0xFFFF) - (open_i16 & 0xFFFF)) & 0xFFFF)


@dataclass
class FosPaxelAcc:
    """Σ/P buckets — frame locals @ ``0x1028f9ad`` / globals @ ``0x1028f8de``.

    Global ESP @ eigen ``0x1028fe61``: ``+0x50`` N; ``+0x6c/70/74`` ΣRGB;
    ``+0x54/58/5c`` ΣUVW; ``+0x78…8c`` P_RG…BB; ``+0x60/64/68/90/94`` P_UU….
    """

    n: int = 0
    sum_r: int = 0
    sum_g: int = 0
    sum_b: int = 0
    sum_u: int = 0
    sum_v: int = 0
    sum_w: int = 0
    p_rg: int = 0
    p_rb: int = 0
    p_gb: int = 0
    p_rr: int = 0
    p_gg: int = 0
    p_bb: int = 0
    p_uv: int = 0
    p_uw: int = 0
    p_uu: int = 0
    p_vv: int = 0
    p_ww: int = 0

    def add_pixel(self, r: int, g: int, b: int, u: int, v: int, w: int) -> None:
        """Accept body — PakonIMAu.dll @ ``0x1028fafe…fc6c``."""
        self.sum_r += r  # PakonIMAu.dll @ 0x1028fb14 → +0xe4
        self.sum_g += g  # PakonIMAu.dll @ 0x1028fb20 → +0xe8
        self.sum_b += b  # PakonIMAu.dll @ 0x1028fb30 → +0xec
        self.sum_u += u  # PakonIMAu.dll @ 0x1028fb3e → +0xcc
        self.sum_v += v  # PakonIMAu.dll @ 0x1028fb47 → +0xd0
        self.sum_w += w  # PakonIMAu.dll @ 0x1028fb55 → +0xd4
        self.p_rg += _sar5(g * r)  # PakonIMAu.dll @ 0x1028fb67…f6d → +0xf0
        self.p_rb += _sar5(b * r)  # PakonIMAu.dll @ 0x1028fb6f…f74 → +0xf4
        self.p_gb += _sar5(b * g)  # PakonIMAu.dll @ 0x1028fb87…f8c → +0xf8
        self.p_uv += _sar5(u * v)  # PakonIMAu.dll @ 0x1028fb9f…fb7 → +0xdc
        self.p_uw += _sar5(u * w)  # PakonIMAu.dll @ 0x1028fbbc…bcf → +0xe0
        self.p_rr += _sar5(r * r)  # PakonIMAu.dll @ 0x1028fbd4…fc09 → +0xfc
        self.p_gg += _sar5(g * g)  # PakonIMAu.dll @ 0x1028fbd9…fc15 → +0x100
        self.p_bb += _sar5(b * b)  # PakonIMAu.dll @ 0x1028fbde…fbea → +0x104
        self.p_uu += _sar5(u * u)  # PakonIMAu.dll @ 0x1028fbf6…fc2f → +0xd8
        self.p_vv += _sar5(v * v)  # PakonIMAu.dll @ 0x1028fc42…fc4e → +0x108
        self.p_ww += _sar5(w * w)  # PakonIMAu.dll @ 0x1028fc58…fc5f → +0x10c
        self.n += 1  # PakonIMAu.dll @ 0x1028fc6b → +0xc8

    def merge_from(self, frame: "FosPaxelAcc") -> None:
        """Global += frame — PakonIMAu.dll @ ``0x1028fce3…fe2b``."""
        for f in fields(self):
            setattr(self, f.name, getattr(self, f.name) + getattr(frame, f.name))


def fos_paxel_indices() -> list[int]:
    """Row/col linear indices — PakonIMAu.dll @ ``0x1028fa32…fcc6``.

    ``row_base = 0x25, 0x25+0x24, …`` while ``row_base < 0x33d``; each
    row ``0x22`` consecutive cols. Byte plane stride ``0x6c0`` ⇒
    ``0x360`` words = **36×24**.
    """
    out: list[int] = []
    row = PAXEL_IDX0  # PakonIMAu.dll @ 0x1028f9a8
    while row < PAXEL_ROW_END:  # PakonIMAu.dll @ 0x1028fcba
        for col in range(PAXEL_NCOLS):  # PakonIMAu.dll @ 0x1028fa39 / fc9a
            out.append(row + col)
        row += PAXEL_ROW_STEP  # PakonIMAu.dll @ 0x1028fcb7
    return out


def fos_paxel_accept(
    mask_byte: int,
    v: int,
    w: int,
    delta1: int,
    delta2: int,
    radius_sq: int,
) -> bool:
    """Per-pixel accept — PakonIMAu.dll @ ``0x1028fab7…faf8``.

    ``mask_byte == 1`` (@ ``0x1028fab7``) AND
    ``(v−Δ1)² + (w−Δ2)² < radius_sq`` (@ ``0x1028facc…faf8``; reject if
    ``jge``). ``radius_sq = (word[arg3+0xdc+0x18])²`` (@ ``0x1028f58a``).
    Centres ``Δ1/Δ2`` = helper OUT ``[esp+0xac/+0xb0]`` (@ ``0x1028facc``).
    """
    if (mask_byte & 0xFF) != 1:  # PakonIMAu.dll @ 0x1028fab7
        return False
    dv = int(v) - int(delta1)  # PakonIMAu.dll @ 0x1028fada…fadf
    dw = int(w) - int(delta2)  # PakonIMAu.dll @ 0x1028fad3…fad8
    r2 = dv * dv + dw * dw  # PakonIMAu.dll @ 0x1028fae1…faeb
    return r2 < int(radius_sq)  # PakonIMAu.dll @ 0x1028faed jge reject


def fos_paxel_sample_deltas(
    dens_words: list[int] | memoryview,
    index: int,
    open_rgb: tuple[int, int, int],
    open_c1: int,
    open_c2: int,
) -> tuple[int, int, int, int, int, int]:
    """Dens − open → ``(R,G,B,U,V,W)`` i32 — PakonIMAu.dll @ ``0x1028fa4e…faaf``.

    ``dens_words`` is planar uint16 storage with stride ``0x360`` words
    (``0x6c0`` bytes — DLL displacement @ ``0x1028fa4e``). Fake layout:
    ``6 * 0x360`` words. U uses ``open_B`` (@ ``0x1028faa0``).
    """
    o_r, o_g, o_b = open_rgb
    # PakonIMAu.dll dens word loads @ 0x1028fa4e…faaf
    r = _i16_sub_u16(int(dens_words[index + PAXEL_OFF_R]), o_r)
    g = _i16_sub_u16(int(dens_words[index + PAXEL_OFF_G]), o_g)
    b = _i16_sub_u16(int(dens_words[index + PAXEL_OFF_B]), o_b)
    u = _i16_sub_u16(int(dens_words[index + PAXEL_OFF_U]), o_b)  # −openB
    v = _i16_sub_u16(int(dens_words[index + PAXEL_OFF_V]), open_c1)
    w = _i16_sub_u16(int(dens_words[index + PAXEL_OFF_W]), open_c2)
    return r, g, b, u, v, w


def fos_paxel_accumulate_frame(
    dens_words: list[int] | memoryview,
    mask_bytes: bytes | bytearray | memoryview,
    *,
    open_rgb: tuple[int, int, int],
    open_c1: int,
    open_c2: int,
    delta1: int,
    delta2: int,
    radius_sq: int,
) -> FosPaxelAcc:
    """One-frame dens paxel — PakonIMAu.dll @ ``0x1028f9a8…fcc6``.

    ``mask_bytes[index]`` mirrors ``byte[arg8_ptr + 0xc20 + index]``
    (@ ``0x1028fab7``) when the host buffer starts at the mask plane.
    Does **not** apply ``N_frame`` threshold — see
    ``fos_paxel_frame_meets_threshold`` + ``merge_from``.
    """
    acc = FosPaxelAcc()
    for idx in fos_paxel_indices():
        m = int(mask_bytes[idx])  # PakonIMAu.dll @ 0x1028fab7
        if (m & 0xFF) != 1:  # PakonIMAu.dll @ 0x1028fabf jne skip
            continue
        r, g, b, u, v, w = fos_paxel_sample_deltas(
            dens_words, idx, open_rgb, open_c1, open_c2
        )
        if not fos_paxel_accept(m, v, w, delta1, delta2, radius_sq):
            continue
        acc.add_pixel(r, g, b, u, v, w)
    return acc


def fos_paxel_frame_meets_threshold(n_frame: int, thresh_word: int) -> bool:
    """``N_frame >= sx(word[arg3+0xdc+0x2e])`` — PakonIMAu.dll @ ``0x1028fcd0``.

    ``jl`` skips merge (@ ``0x1028fcdd``). Same subobject as R² word
    ``+0x18`` (@ ``0x1028f586``): ``arg3 = Impl+0x68``.
    """
    return int(n_frame) >= _i16(thresh_word)  # PakonIMAu.dll @ 0x1028fcdb


def fos_paxel_skip_frame_fiduciary(fid_ptr: int | None, fid_byte4: int) -> bool:
    """Skip frame if ``arg7`` non-null and ``byte[+4]==1`` — @ ``0x1028f994…9a2``.

    ``fid_ptr`` is ``*[arg7]`` (``frame+0x388c``). Null → do **not** skip
    (@ ``0x1028f99c`` je process).
    """
    if fid_ptr is None or fid_ptr == 0:  # PakonIMAu.dll @ 0x1028f996
        return False
    return (fid_byte4 & 0xFF) == 1  # PakonIMAu.dll @ 0x1028f99e je skip


def fos_paxel_accumulate_roll(
    frames: list[
        tuple[
            list[int] | memoryview,
            bytes | bytearray | memoryview,
            int | None,
            int,
        ]
    ],
    *,
    open_rgb: tuple[int, int, int],
    open_c1: int,
    open_c2: int,
    delta1: int,
    delta2: int,
    radius_sq: int,
    n_thresh_word: int,
) -> FosPaxelAcc:
    """Multi-frame accumulate — PakonIMAu.dll @ ``0x1028f980…fe55``.

    Each frame: ``(dens_words, mask_bytes, fid_ptr, fid_byte4)``.
    Dens = six planar uint16 planes (``6*0x360`` words /
    ``0x6c0``-byte stride) from ``frame+0x1a``; mask plane indexed like
    ``frame+0x290c+0xc20``.
    """
    glob = FosPaxelAcc()
    for dens, mask, fid_ptr, fid_b4 in frames:
        if fos_paxel_skip_frame_fiduciary(fid_ptr, fid_b4):
            continue  # PakonIMAu.dll @ 0x1028f9a2 → 0x1028fe3f
        frame = fos_paxel_accumulate_frame(
            dens,
            mask,
            open_rgb=open_rgb,
            open_c1=open_c1,
            open_c2=open_c2,
            delta1=delta1,
            delta2=delta2,
            radius_sq=radius_sq,
        )
        if fos_paxel_frame_meets_threshold(frame.n, n_thresh_word):
            glob.merge_from(frame)  # PakonIMAu.dll @ 0x1028fce3
    return glob


def fos_paxel_fake_planes(
    *,
    fill: int = 0,
) -> tuple[list[int], bytearray]:
    """Minimal host/Unicorn layout: ``6*0x360`` dens words + mask bytes.

    Host ``mask_bytes[edi]`` ≡ DLL ``byte[arg8 + 0xc20 + edi]`` when the
    buffer is the mask plane only (DLL offset folded away).
    """
    dens = [fill & 0xFFFF] * (6 * PAXEL_PLANE_WORDS)
    mask = bytearray(PAXEL_PLANE_WORDS)
    return dens, mask


def fos_div1000_trunc(n: int) -> int:
    """``imul 0x10624dd3; sar edx,6; +signbit`` — PakonIMAu.dll @ ``0x1028f523``."""
    full = _i32(n) * _i32(DIV1000_MAGIC)  # PakonIMAu.dll imul
    edx = full >> 32
    edx >>= 6  # PakonIMAu.dll sar edx,6
    return int(edx + (1 if edx < 0 else 0))  # PakonIMAu.dll add (edx>>31)


def fos_order_fpo_compose(
    open_axes: tuple[int, int, int],
    delta: tuple[int, int, int],
) -> tuple[int, int, int]:
    """OUT ``orderFpo`` — PakonIMAu.dll @ ``0x1028f890…8da``.

    ``orderFpo[i] = int16(open_axes[i] + Δ[i])`` — plain i32 add, store
    low 16 (no ``ftol``). ``open_axes`` = Y/C1/C2 @ ESP ``+0x120/124/128``;
    ``delta`` = helper OUT @ ``+0xa8/ac/b0`` (or fallback).
    """
    # PakonIMAu.dll @ 0x1028f8ac / 0x8b5 / 0x8d3 — add; mov word [esi+…]
    return tuple(_i16(int(o) + int(d)) for o, d in zip(open_axes, delta))


def fos_order_fpo_delta0(dmin_minus_open_r: int) -> int:
    """Helper Δ[0] — PakonIMAu.dll @ ``0x1028f503…50f``.

    ``Δ0 = (dminR−openR) + 0x498``. Written even on method-2; caller
    fallback does **not** overwrite Δ0 (@ ``0x1028f878`` only touches
    ``+0xac/+0xb0``).
    """
    return int(dmin_minus_open_r) + ORDER_FPO_DELTA0_BIAS  # PakonIMAu.dll @ 0x1028f509


def fos_order_fpo_blend_c_delta(
    mean_c: int,
    dmin_open_c: int,
    weight: int,
) -> int:
    """Helper Δ[1]/Δ[2] final blend — PakonIMAu.dll @ ``0x1028f511…55f``.

    ``Δ = trunc_div1000( w·mean + (1000−w)·dminOpenC )`` with
    ``w = word[dc+0x1c]`` (C1) or ``+0x1e`` (C2). ``mean`` from
    ``fos_order_fpo_helper`` (in-radius / weighted).
    """
    w = _i16(weight)  # PakonIMAu.dll ebx/ebp from dc+0x1c/+0x1e
    # PakonIMAu.dll @ 0x1028f511…521 — (1000-w)*dminOpenC + w*mean
    num = w * int(mean_c) + (1000 - w) * int(dmin_open_c)
    return fos_div1000_trunc(num)  # PakonIMAu.dll @ 0x1028f523…532


def fos_order_fpo_fallback_delta(
    delta0: int,
    dmin_open_c1: int,
    dmin_open_c2: int,
) -> tuple[int, int, int]:
    """Caller fallback when helper ``eax==-1`` — PakonIMAu.dll @ ``0x1028f878``.

    Keeps helper Δ0; replaces Δ1/Δ2 with dmin−open C1/C2 (``edi``/``esi``
    after dmin−open axes @ ``0x1028f7f4`` / ``0x1028f864``).
    """
    return (int(delta0), int(dmin_open_c1), int(dmin_open_c2))


def fos_idiv_i32(numer: int, denom: int) -> int:
    """Signed ``cdq; idiv`` trunc toward 0 — PakonIMAu.dll helper means."""
    d = _i32(denom)
    if d == 0:
        raise ZeroDivisionError("fos_idiv_i32: denom == 0")
    n = _i32(numer)
    q = abs(n) // abs(d)  # PakonIMAu.dll cdq; idiv
    return -q if (n < 0) ^ (d < 0) else q


def fos_half_round_div(numer: int, denom: int) -> int:
    """``±half(denom)`` then ``idiv`` — PakonIMAu.dll @ ``0x1028f480…4a6``."""
    n = _i32(numer)
    d = _i32(denom)
    if d == 0:
        raise ZeroDivisionError("fos_half_round_div: denom == 0")
    # PakonIMAu.dll @ 0x1028f480: mov eax,ecx; cdq; sub eax,edx; sar eax,1
    half = (d - (-1 if d < 0 else 0)) >> 1
    if (n < 0) == (d < 0):  # PakonIMAu.dll same-sign → add @ 0x1028f489
        return fos_idiv_i32(n + half, d)
    return fos_idiv_i32(n - half, d)  # PakonIMAu.dll @ 0x1028f4a3 sub


def fos_isqrt_u32(n: int) -> int:
    """Integer isqrt — PakonIMAu.dll @ ``0x1028f362…393`` (ecx in/out)."""
    ecx = n & 0xFFFFFFFF
    if ecx < 2:  # PakonIMAu.dll @ 0x1028f362 cmp ecx,2; jl
        return ecx
    eax = 0x60000000  # PakonIMAu.dll @ 0x1028f367
    esi = 0x8000  # PakonIMAu.dll @ 0x1028f36e
    if (eax & ecx) == 0:  # PakonIMAu.dll @ 0x1028f36c
        while True:
            eax = (eax >> 2) & 0xFFFFFFFF  # PakonIMAu.dll sar eax,2 (≥0)
            esi >>= 1  # PakonIMAu.dll sar esi,1
            if (ecx & eax) != 0:  # PakonIMAu.dll @ 0x1028f37a
                break
            if esi == 0:  # PakonIMAu.dll @ 0x1028f37e
                return 0  # PakonIMAu.dll @ 0x1028f393 mov ecx,esi
    while True:
        q = fos_idiv_i32(ecx, esi)  # PakonIMAu.dll @ 0x1028f382 cdq; idiv
        ebx = esi  # PakonIMAu.dll @ 0x1028f387
        esi = (q + esi + 1) & 0xFFFFFFFF  # PakonIMAu.dll lea esi,[eax+esi+1]
        if esi >= 0x80000000:
            esi = ((esi - 0x100000000) >> 1) & 0xFFFFFFFF
        else:
            esi >>= 1  # PakonIMAu.dll sar esi,1
        if esi == ebx:  # PakonIMAu.dll @ 0x1028f38f
            break
    return esi


def fos_helper_weight(isqrt_r: int, wtab: tuple[int, int, int, int]) -> int:
    """Weight from isqrt(r²) — PakonIMAu.dll @ ``0x1028f1b0``.

    ``wtab = (lo, mid, mid_w, hi_w)`` = words at ``arg3+0x1c/1e/20/22``.
    """
    lo, mid, mid_w, hi_w = (_i16(x) for x in wtab)
    ebx = int(isqrt_r)
    if ebx <= lo:  # PakonIMAu.dll @ 0x1028f1c5
        return hi_w  # PakonIMAu.dll @ 0x1028f1ca
    if ebx >= mid:  # PakonIMAu.dll @ 0x1028f1d3
        return mid_w  # PakonIMAu.dll @ 0x1028f23e eax=sx(+0x20)
    # PakonIMAu.dll @ 0x1028f1da…23c interpolate
    # numer = ((hi_w-mid_w)*ebx + 100*((mid_w*lo)-mid)) * 1000
    numer = (hi_w - mid_w) * ebx + 100 * ((mid_w * lo) - mid)  # @ 0x1028f1dd…ea
    numer *= 1000  # PakonIMAu.dll @ 0x1028f1ec
    denom = (lo - mid) * 1000  # PakonIMAu.dll @ 0x1028f1f2…1fc
    return fos_half_round_div(numer, denom)


@dataclass
class FosHelperFrame:
    """One roll frame for helper ``0x1028f250`` — 388c + 290c fields."""

    skip_fiduciary: bool = False  # PakonIMAu.dll byte[388c+4]==1
    c1_lo: int = 0  # PakonIMAu.dll +0x4c
    c2_lo: int = 0  # PakonIMAu.dll +0x50
    c1_hi: int = 0  # PakonIMAu.dll +0x7bc
    c2_hi: int = 0  # PakonIMAu.dll +0x7c0
    gate_9cc: int = 0  # PakonIMAu.dll +0x9cc


@dataclass
class FosHelperResult:
    """Helper OUT — PakonIMAu.dll @ ``0x1028f250`` return + Δ + ofpoMethod."""

    eax: int  # 0 ok, -1 method-2, or ERR_HELPER
    delta: tuple[int, int, int]
    ofpo_method: int


def fos_order_fpo_helper(
    frames: list[FosHelperFrame],
    *,
    dc_gate: int,
    dc_radius: int,
    dc_w_gm: int,
    dc_w_ill: int,
    dc_thresh_n: int,
    dmin_open_r: int,
    dmin_open_c1: int,
    dmin_open_c2: int,
    wtab_enable: int = 0,
    wtab: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> FosHelperResult:
    """Means → Δ — PakonIMAu.dll helper @ ``0x1028f250``.

    Call args (cdecl×9): ``arg0/1`` = 290c/388c ptr arrays, ``arg2`` = dc,
    ``arg3`` = weight table (&Impl+0x40), ``arg5`` = n, ``arg6`` = dminOpen,
    ``arg7`` = Δ OUT, ``arg8`` = &ofpoMethod.
    """
    if not FOS_ORDER_FPO_HELPER_PORTED:
        raise RuntimeError("FOS_ORDER_FPO_HELPER_PORTED is False")
    n = len(frames)
    r = _i16(dc_radius)
    r2 = r * r  # PakonIMAu.dll @ 0x1028f266…268
    w_gm = _i16(dc_w_gm)  # PakonIMAu.dll @ 0x1028f25c
    w_ill = _i16(dc_w_ill)  # PakonIMAu.dll @ 0x1028f261
    gate = _i16(dc_gate)  # PakonIMAu.dll @ 0x1028f2f7
    thresh = _i16(dc_thresh_n)  # PakonIMAu.dll word[dc+0x2c] @ compare
    enable_w = _i16(wtab_enable)  # PakonIMAu.dll word[arg3+0x24]

    sum_c1 = sum_c2 = 0  # PakonIMAu.dll esp+0x10/14
    count_in = 0  # PakonIMAu.dll esp+0x1c
    wsum_c1 = wsum_c2 = wsum_w = 0  # PakonIMAu.dll esp+0x20/24/18

    for fr in frames:  # PakonIMAu.dll @ 0x1028f2e0…3e7
        if fr.skip_fiduciary:  # PakonIMAu.dll @ 0x1028f2ed
            continue
        # PakonIMAu.dll @ 0x1028f2fb — gate selects hi/lo C banks
        if fr.gate_9cc > gate:
            c1, c2 = int(fr.c1_hi), int(fr.c2_hi)  # @ 0x1028f303
        else:
            c1, c2 = int(fr.c1_lo), int(fr.c2_lo)  # @ 0x1028f311
        # Distance always uses *lo* C vs dminOpen C — PakonIMAu.dll @ 0x1028f317
        dx = int(fr.c1_lo) - int(dmin_open_c1)  # @ 0x1028f321…324
        dy = int(fr.c2_lo) - int(dmin_open_c2)  # @ 0x1028f31e
        dist2 = dx * dx + dy * dy  # PakonIMAu.dll @ 0x1028f329…32f
        if dist2 < r2:  # PakonIMAu.dll @ 0x1028f331
            sum_c1 += c1  # PakonIMAu.dll @ 0x1028f33d
            sum_c2 += c2
            count_in += 1  # PakonIMAu.dll @ 0x1028f349
        if enable_w != 0:  # PakonIMAu.dll @ 0x1028f352
            if dist2 < 0:  # PakonIMAu.dll @ 0x1028f35a jl → return -1
                return FosHelperResult(eax=-1, delta=(0, 0, 0), ofpo_method=0)
            ir = fos_isqrt_u32(dist2)  # PakonIMAu.dll @ 0x1028f362
            w = fos_helper_weight(ir, wtab)  # PakonIMAu.dll call @ 0x1028f39b
            wsum_c1 += c1 * w  # PakonIMAu.dll @ 0x1028f3a0
            wsum_c2 += c2 * w
            wsum_w += w  # PakonIMAu.dll @ 0x1028f3b6

    ofpo = 0  # PakonIMAu.dll @ 0x1028f28a
    ret_eax = 0  # PakonIMAu.dll esp+0x34
    # Means slots start as unweighted Σ — PakonIMAu.dll esp+0x10/14
    mean_c1 = sum_c1
    mean_c2 = sum_c2
    if count_in > thresh:  # PakonIMAu.dll @ 0x1028f401 cmp di,ax; jle
        mean_c1 = fos_idiv_i32(sum_c1, count_in)  # @ 0x1028f40a
        mean_c2 = fos_idiv_i32(sum_c2, count_in)  # @ 0x1028f418
    else:
        # PakonIMAu.dll @ 0x1028f43c — need wsum_w > thresh*100 and enable
        if wsum_w > thresh * 100 and enable_w != 0:  # @ 0x1028f43f…450
            # PakonIMAu.dll @ 0x1028f456…4cb — means from weighted Σ×1000
            numer1 = wsum_c1 * 1000  # @ 0x1028f45a
            denom = wsum_w * 1000  # @ 0x1028f464 / 476
            mean_c1 = fos_half_round_div(numer1, denom)
            numer2 = wsum_c2 * 1000  # @ 0x1028f4ac
            mean_c2 = fos_half_round_div(numer2, denom)
            ofpo = 1  # PakonIMAu.dll @ 0x1028f4d3
        else:
            ret_eax = -1  # PakonIMAu.dll @ 0x1028f4f2
            ofpo = 2  # PakonIMAu.dll @ 0x1028f4fa
            # leave mean_* = raw Σ (method2 still blends them @ 0x1028f4ff)

    d0 = fos_order_fpo_delta0(dmin_open_r)  # PakonIMAu.dll @ 0x1028f503
    d1 = fos_order_fpo_blend_c_delta(mean_c1, dmin_open_c1, w_gm)  # @ 0x1028f511
    d2 = fos_order_fpo_blend_c_delta(mean_c2, dmin_open_c2, w_ill)  # @ 0x1028f537
    return FosHelperResult(eax=ret_eax, delta=(d0, d1, d2), ofpo_method=ofpo)


def fos_idiv_trunc(numer: int, denom_i16: int) -> int:
    """Signed ``cdq; idiv`` trunc toward 0 — PakonIMAu.dll @ ``0x102b7669`` family."""
    d = _i16(denom_i16)
    if d == 0:
        raise ZeroDivisionError("fos_idiv_trunc: denom == 0")
    n = _i32(numer)
    # PakonIMAu.dll cdq; idiv — trunc toward 0 (not Python //)
    q = abs(n) // abs(d)
    return -q if (n < 0) ^ (d < 0) else q


def fos_postfill_gate_9cc(out_word6: int) -> int:
    """OUT ``+0x9cc`` — PakonIMAu.dll @ ``0x102b7cf6`` ``movsx`` of ``word[OUT+6]``."""
    return _i16(out_word6)  # PakonIMAu.dll @ 0x102b7cf6 → dword[+0x9cc]


def fos_postfill_c_low(
    stats_c1: int,
    stats_c2: int,
    count_n0: int,
    *,
    flags0_nonzero: bool = True,
) -> tuple[int, int] | None:
    """OUT ``+0x4c/+0x50`` — PakonIMAu.dll @ ``0x102b7660…769d``.

    ``C = idiv(stats[+0x40/+0x44], i16(counts[+0]))`` when ``flags[0]≠0``;
    else ``None`` (DLL skips store @ ``0x102b7639``).
    """
    if not flags0_nonzero:  # PakonIMAu.dll @ 0x102b7634 je skip
        return None
    c1 = fos_idiv_trunc(stats_c1, count_n0)  # PakonIMAu.dll @ 0x102b7660 → +0x4c
    c2 = fos_idiv_trunc(stats_c2, count_n0)  # PakonIMAu.dll → +0x50
    return c1, c2


def fos_postfill_c_high(
    stats_c1_lo: int,
    stats_c2_lo: int,
    stats_c1_hi: int,
    stats_c2_hi: int,
    count_n0: int,
    count_n_hi: int,
    out_word6: int,
    dc_word_e: int,
    *,
    flags_word_e_nonzero: bool = True,
) -> tuple[int, int] | None:
    """OUT ``+0x7bc/+0x7c0`` — PakonIMAu.dll @ ``0x102b77d0…7b11``.

    If ``flags.word[+0xe]==0``: skip. Else if ``OUT+6 > dc+0xe``: idiv high
    stats ``+0x820/+0x824`` by ``counts+0x1c``; else same as low pair /
    ``counts+0``.
    """
    if not flags_word_e_nonzero:  # PakonIMAu.dll @ 0x102b7ccc path skip
        return None
    if _i16(out_word6) > _i16(dc_word_e):  # PakonIMAu.dll @ 0x102b751a
        c1 = fos_idiv_trunc(stats_c1_hi, count_n_hi)  # PakonIMAu.dll @ 0x102b77f0 → +0x7bc
        c2 = fos_idiv_trunc(stats_c2_hi, count_n_hi)  # → +0x7c0
    else:
        c1 = fos_idiv_trunc(stats_c1_lo, count_n0)  # PakonIMAu.dll @ 0x102b7ac9…
        c2 = fos_idiv_trunc(stats_c2_lo, count_n0)
    return c1, c2


@dataclass
class SbaFOSResults:
    """OUT ``SbaFOSResults`` — PakonIMAu.dll Cap dump @ ``0x1013c210`` / ``Impl+0x18``."""

    order_fpo: tuple[int, int, int] = (0, 0, 0)  # PakonIMAu.dll OUT+0x00
    order_avg: tuple[int, int, int] = (0, 0, 0)  # PakonIMAu.dll OUT+0x06
    fos_dmin: tuple[int, int, int] = (0, 0, 0)  # PakonIMAu.dll OUT+0x0c
    gm_slope: int = 0  # PakonIMAu.dll OUT+0x12
    gm_offset: int = 0  # PakonIMAu.dll OUT+0x14
    ill_slope: int = 0  # PakonIMAu.dll OUT+0x16
    ill_offset: int = 0  # PakonIMAu.dll OUT+0x18
    theta: int = 0  # PakonIMAu.dll OUT+0x1a — not stored by calc
    ofpo_method: int = 0  # PakonIMAu.dll OUT+0x1c — helper writes
    num_pixels: int = 0  # PakonIMAu.dll OUT+0x1e @ 0x102903e6
    gm_rsquare: int = 0  # PakonIMAu.dll OUT+0x20 @ 0x102903a4
    ill_rsquare: int = 0  # PakonIMAu.dll OUT+0x22 @ 0x102903ef

    def to_bytes(self) -> bytes:
        """Pack 36-byte OUT — PakonIMAu.dll ``FOS_RESULTS_SIZE``."""
        parts = [
            struct.pack("<hhh", *(_i16(x) for x in self.order_fpo)),
            struct.pack("<hhh", *(_i16(x) for x in self.order_avg)),
            struct.pack("<hhh", *(_i16(x) for x in self.fos_dmin)),
            struct.pack(
                "<hhhh",
                _i16(self.gm_slope),
                _i16(self.gm_offset),
                _i16(self.ill_slope),
                _i16(self.ill_offset),
            ),
            struct.pack("<hh", _i16(self.theta), _i16(self.ofpo_method)),
            struct.pack(
                "<hhh",
                _i16(self.num_pixels),
                _i16(self.gm_rsquare),
                _i16(self.ill_rsquare),
            ),
        ]
        out = b"".join(parts)
        assert len(out) == FOS_RESULTS_SIZE
        return out


def fos_calc_results_partial(
    *,
    open_rgb: tuple[int, int, int],
    frame_dmin_rgbs: list[tuple[int, int, int]],
    paxel_acc: FosPaxelAcc,
    order_fpo_delta: tuple[int, int, int],
    ofpo_method: int = 0,
) -> SbaFOSResults:
    """Partial ``SbaCalcFosResults`` with injected Δ — PakonIMAu.dll body.

    Prefer ``fos_calc_results`` (helper Δ). Kept for leaf tests that inject
    Δ directly.
    """
    if not FOS_ANALYZE_PARTIAL_PORTED:
        raise RuntimeError("FOS_ANALYZE_PARTIAL_PORTED is False")
    open_axes = fos_opening_axes(*open_rgb)  # PakonIMAu.dll @ 0x1028f608
    dmin = fos_dmin_min(frame_dmin_rgbs)  # PakonIMAu.dll @ 0x1028f6d8
    order_fpo = fos_order_fpo_compose(open_axes, order_fpo_delta)  # @ 0x1028f890

    n = int(paxel_acc.n)
    if n == 0:
        # PakonIMAu.dll still writes earlier OUT fields; dens leaves see N=0
        return SbaFOSResults(
            order_fpo=order_fpo,
            fos_dmin=dmin,
            ofpo_method=_i16(ofpo_method),
            num_pixels=0,
        )

    mean = (
        float(paxel_acc.sum_r) / float(n),  # PakonIMAu.dll @ 0x102901e0…
        float(paxel_acc.sum_g) / float(n),
        float(paxel_acc.sum_b) / float(n),
    )
    order_avg = fos_order_avg(open_rgb, mean)  # PakonIMAu.dll @ 0x10290290

    eigen = fos_rgb_max_eigen_unit(  # PakonIMAu.dll @ 0x1028fe61
        n,
        paxel_acc.sum_r,
        paxel_acc.sum_g,
        paxel_acc.sum_b,
        paxel_acc.p_rg,
        paxel_acc.p_rb,
        paxel_acc.p_gb,
        paxel_acc.p_rr,
        paxel_acc.p_gg,
        paxel_acc.p_bb,
    )
    gm_s, gm_o, ill_s, ill_o = fos_gm_ill_slopes_offsets(
        eigen, mean, apply_sign=True
    )  # PakonIMAu.dll @ 0x10290216

    gm_r2 = fos_gm_rsquare(  # PakonIMAu.dll @ 0x10290332
        paxel_acc.sum_u,
        paxel_acc.sum_v,
        paxel_acc.p_uv,
        paxel_acc.p_uu,
        paxel_acc.p_vv,
        n,
    )
    ill_r2 = fos_ill_rsquare(
        paxel_acc.sum_u,
        paxel_acc.sum_w,
        paxel_acc.p_uw,
        paxel_acc.p_uu,
        paxel_acc.p_ww,
        n,
    )

    return SbaFOSResults(
        order_fpo=order_fpo,
        order_avg=order_avg,
        fos_dmin=dmin,
        gm_slope=gm_s,
        gm_offset=gm_o,
        ill_slope=ill_s,
        ill_offset=ill_o,
        ofpo_method=_i16(ofpo_method),
        num_pixels=_i16(n),  # PakonIMAu.dll @ 0x102903e6
        gm_rsquare=gm_r2,
        ill_rsquare=ill_r2,
    )


def fos_calc_results(
    *,
    open_rgb: tuple[int, int, int],
    frame_dmin_rgbs: list[tuple[int, int, int]],
    paxel_acc: FosPaxelAcc,
    helper_frames: list[FosHelperFrame],
    dc_gate: int,
    dc_radius: int,
    dc_w_gm: int,
    dc_w_ill: int,
    dc_thresh_n: int,
    wtab_enable: int = 0,
    wtab: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> tuple[int, SbaFOSResults]:
    """Full ``SbaCalcFosResults`` host wire — PakonIMAu.dll @ ``0x1028f570``.

    DLL order: opening → ``fosDmin`` → dmin−open → helper Δ → compose
    ``orderFpo`` → dens Σ/P (caller) → orderAvg / eigen / slopes / R².

    Returns ``(eax, OUT)`` — ``eax==0`` on success (method-2 uses fallback
    Δ1/Δ2 @ ``0x1028f878`` and still succeeds). Non-zero: helper error or
    ``ERR_DISC``.
    """
    if not FOS_ANALYZE_PORTED:
        raise RuntimeError("FOS_ANALYZE_PORTED is False")
    open_axes = fos_opening_axes(*open_rgb)  # PakonIMAu.dll @ 0x1028f608
    dmin = fos_dmin_min(frame_dmin_rgbs)  # PakonIMAu.dll @ 0x1028f6d8
    (dmin_open_r, _dg, _db), dmin_open_axes = fos_dmin_minus_open(
        dmin, open_rgb
    )  # PakonIMAu.dll @ 0x1028f750
    dmin_open_c1 = dmin_open_axes[1]  # PakonIMAu.dll C1 @ 0x1028f7f4
    dmin_open_c2 = dmin_open_axes[2]  # PakonIMAu.dll C2 @ 0x1028f864

    helper = fos_order_fpo_helper(  # PakonIMAu.dll @ 0x1028f86b → 0x1028f250
        helper_frames,
        dc_gate=dc_gate,
        dc_radius=dc_radius,
        dc_w_gm=dc_w_gm,
        dc_w_ill=dc_w_ill,
        dc_thresh_n=dc_thresh_n,
        dmin_open_r=dmin_open_r,
        dmin_open_c1=dmin_open_c1,
        dmin_open_c2=dmin_open_c2,
        wtab_enable=wtab_enable,
        wtab=wtab,
    )
    if helper.eax == ERR_HELPER:  # PakonIMAu.dll @ 0x1028f432
        return ERR_HELPER, SbaFOSResults(fos_dmin=dmin)
    if helper.eax != 0 and helper.eax != -1:  # PakonIMAu.dll @ 0x1028f888
        return int(helper.eax), SbaFOSResults(fos_dmin=dmin)

    if helper.eax == -1:  # PakonIMAu.dll @ 0x1028f873…878
        delta = fos_order_fpo_fallback_delta(
            helper.delta[0], dmin_open_c1, dmin_open_c2
        )
    else:
        delta = helper.delta

    try:
        out = fos_calc_results_partial(
            open_rgb=open_rgb,
            frame_dmin_rgbs=frame_dmin_rgbs,
            paxel_acc=paxel_acc,
            order_fpo_delta=delta,
            ofpo_method=helper.ofpo_method,
        )
    except ValueError as e:
        # PakonIMAu.dll @ 0x1029006b → eax=0x189d
        if f"{ERR_DISC:#x}" in str(e) or str(ERR_DISC) in str(e):
            return ERR_DISC, SbaFOSResults(
                order_fpo=fos_order_fpo_compose(open_axes, delta),
                fos_dmin=dmin,
                ofpo_method=_i16(helper.ofpo_method),
            )
        raise
    return 0, out


@dataclass
class FosRollFrame:
    """One roll frame for host FOS — dens + mask + dmin RGB + helper C banks.

    Dens/mask feed paxel @ ``0x1028f980``; ``dmin_rgb`` = words at
    ``frame+0x290c+0/+2/+4`` for ``fosDmin``; C banks feed helper
    ``0x1028f250``.
    """

    dens_words: list[int] | memoryview
    mask_bytes: bytes | bytearray | memoryview
    dmin_rgb: tuple[int, int, int]
    c1_lo: int = 0  # PakonIMAu.dll +0x4c
    c2_lo: int = 0  # PakonIMAu.dll +0x50
    c1_hi: int = 0  # PakonIMAu.dll +0x7bc
    c2_hi: int = 0  # PakonIMAu.dll +0x7c0
    gate_9cc: int = 0  # PakonIMAu.dll +0x9cc
    skip_fiduciary: bool = False  # PakonIMAu.dll byte[388c+4]==1


def fos_analyze_roll(
    frames: list[FosRollFrame],
    *,
    open_rgb: tuple[int, int, int],
    dc_gate: int,
    dc_helper_radius: int,
    dc_w_gm: int,
    dc_w_ill: int,
    dc_thresh_n: int,
    dc_paxel_radius: int,
    dc_paxel_n_thresh: int,
    wtab_enable: int = 0,
    wtab: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> tuple[int, SbaFOSResults]:
    """Host roll → ``SbaFOSResults`` — PakonIMAu.dll calc order @ ``0x1028f570``.

    DLL order (cited): opening → ``fosDmin`` → helper Δ → ``orderFpo`` →
    dens paxel (centres = Δ1/Δ2 @ ``0x1028fac5``) → orderAvg / eigen /
    slopes / R².

    Returns ``(eax, OUT)``. Requires ``FOS_ROLL_CALLER_PORTED``.
    """
    if not FOS_ROLL_CALLER_PORTED:
        raise RuntimeError("FOS_ROLL_CALLER_PORTED is False")
    if not frames:
        return ERR_ARG0, SbaFOSResults()

    open_axes = fos_opening_axes(*open_rgb)  # PakonIMAu.dll @ 0x1028f608
    dmin_rgbs = [fr.dmin_rgb for fr in frames]
    dmin = fos_dmin_min(dmin_rgbs)  # PakonIMAu.dll @ 0x1028f6d8
    (dmin_open_r, _dg, _db), dmin_open_axes = fos_dmin_minus_open(
        dmin, open_rgb
    )  # PakonIMAu.dll @ 0x1028f750
    dmin_open_c1 = dmin_open_axes[1]
    dmin_open_c2 = dmin_open_axes[2]

    helper_frames = [
        FosHelperFrame(
            skip_fiduciary=fr.skip_fiduciary,
            c1_lo=fr.c1_lo,
            c2_lo=fr.c2_lo,
            c1_hi=fr.c1_hi,
            c2_hi=fr.c2_hi,
            gate_9cc=fr.gate_9cc,
        )
        for fr in frames
    ]
    helper = fos_order_fpo_helper(  # PakonIMAu.dll @ 0x1028f86b
        helper_frames,
        dc_gate=dc_gate,
        dc_radius=dc_helper_radius,
        dc_w_gm=dc_w_gm,
        dc_w_ill=dc_w_ill,
        dc_thresh_n=dc_thresh_n,
        dmin_open_r=dmin_open_r,
        dmin_open_c1=dmin_open_c1,
        dmin_open_c2=dmin_open_c2,
        wtab_enable=wtab_enable,
        wtab=wtab,
    )
    if helper.eax == ERR_HELPER:
        return ERR_HELPER, SbaFOSResults(fos_dmin=dmin)
    if helper.eax != 0 and helper.eax != -1:
        return int(helper.eax), SbaFOSResults(fos_dmin=dmin)

    if helper.eax == -1:  # PakonIMAu.dll @ 0x1028f878
        delta = fos_order_fpo_fallback_delta(
            helper.delta[0], dmin_open_c1, dmin_open_c2
        )
    else:
        delta = helper.delta

    # Paxel accept centres = helper Δ1/Δ2 — PakonIMAu.dll @ 0x1028fac5/acc
    delta1 = int(delta[1])
    delta2 = int(delta[2])
    r_paxel = _i16(dc_paxel_radius)
    radius_sq = r_paxel * r_paxel  # PakonIMAu.dll @ 0x1028f586 (dc+0x18)²

    paxel_frames = [
        (
            fr.dens_words,
            fr.mask_bytes,
            1 if fr.skip_fiduciary else None,
            1 if fr.skip_fiduciary else 0,
        )
        for fr in frames
    ]
    open_c1 = open_axes[1]
    open_c2 = open_axes[2]
    acc = fos_paxel_accumulate_roll(  # PakonIMAu.dll @ 0x1028f980
        paxel_frames,
        open_rgb=open_rgb,
        open_c1=open_c1,
        open_c2=open_c2,
        delta1=delta1,
        delta2=delta2,
        radius_sq=radius_sq,
        n_thresh_word=dc_paxel_n_thresh,
    )

    try:
        out = fos_calc_results_partial(
            open_rgb=open_rgb,
            frame_dmin_rgbs=dmin_rgbs,
            paxel_acc=acc,
            order_fpo_delta=delta,
            ofpo_method=helper.ofpo_method,
        )
    except ValueError as e:
        if f"{ERR_DISC:#x}" in str(e) or str(ERR_DISC) in str(e):
            return ERR_DISC, SbaFOSResults(
                order_fpo=fos_order_fpo_compose(open_axes, delta),
                fos_dmin=dmin,
                ofpo_method=_i16(helper.ofpo_method),
            )
        raise
    return 0, out


def validate_calc_args(
    arg0: int,
    out_ptr_ok: bool,
    ptr_0c_ok: bool,
    ptr_10_ok: bool,
    ptr_14_ok: bool,
) -> int | None:
    """Early errors — PakonIMAu.dll ``SbaCalcFosResults`` entry @ ``0x1028f570``."""
    if _i16(arg0) < 1:
        return ERR_ARG0  # PakonIMAu.dll → 0x18a5
    if not out_ptr_ok:
        return ERR_NULL_OUT  # PakonIMAu.dll → 0x18a4
    if not ptr_0c_ok:
        return ERR_NULL_0C  # PakonIMAu.dll → 0x18a1
    if not ptr_14_ok:
        return ERR_NULL_14  # PakonIMAu.dll → 0x18a6
    if not ptr_10_ok:
        return ERR_NULL_10  # PakonIMAu.dll → 0x18a7
    return None


def main() -> None:
    print("FOS (base 0x10000000)")
    print(f"  Cap::analyze          {CAP_ANALYZE:#010x}")
    print(f"  Impl::analyze         {IMPL_ANALYZE:#010x}")
    print(f"  SbaCalcFosResults     {SBA_CALC_FOS_RESULTS:#010x}")
    print(f"  FOS_ANALYZE_PORTED={FOS_ANALYZE_PORTED}")
    print(f"  FOS_OPENING_TRANSFORM_PORTED={FOS_OPENING_TRANSFORM_PORTED}")
    print(f"  FOS_RSQUARE_PORTED={FOS_RSQUARE_PORTED}")
    print(f"  FOS_ORDER_AVG_PORTED={FOS_ORDER_AVG_PORTED}")
    print(f"  FOS_SLOPES_OFFSETS_PORTED={FOS_SLOPES_OFFSETS_PORTED}")
    print(f"  FOS_EIGEN_PORTED={FOS_EIGEN_PORTED}")
    print(f"  FOS_PAXEL_WALK_PORTED={FOS_PAXEL_WALK_PORTED}")
    print(f"  FOS_ORDER_FPO_COMPOSE_PORTED={FOS_ORDER_FPO_COMPOSE_PORTED}")
    print(f"  FOS_ORDER_FPO_HELPER_PORTED={FOS_ORDER_FPO_HELPER_PORTED}")
    print(f"  FOS_ROLL_CALLER_PORTED={FOS_ROLL_CALLER_PORTED}")
    print(f"  FOS_TO_PREFERENCE_FPO_EDGE={FOS_TO_PREFERENCE_FPO_EDGE}")
    print(f"  FOS_RESULTS_SIZE={FOS_RESULTS_SIZE:#x}")
    print(f"  opening axes (1000,1100,900) = {fos_opening_axes(1000, 1100, 900)}")
    print(f"  fos_dmin_min sample = {fos_dmin_min([(100, 200, 300), (90, 210, 250)])}")
    print(
        f"  gmRSquare sample = "
        f"{fos_gm_rsquare(1000, 2000, 24000, 12000, 48000, 100)}"
    )
    print(
        f"  orderAvg sample = "
        f"{fos_order_avg((1000, 1100, 900), (12.5, -3.25, 8.0))}"
    )
    print(
        f"  slopes/offsets sample = "
        f"{fos_gm_ill_slopes_offsets((0.8, 0.4, 0.2), (10.0, 20.0, 15.0))}"
    )
    print(
        f"  eigen unit sample = "
        f"{fos_rgb_max_eigen_unit(100, 1000, 2000, 1500, 24000, 18000, 27000, 12000, 48000, 27000)}"
    )
    dens, mask = fos_paxel_fake_planes(fill=0x100)
    for i in fos_paxel_indices():
        mask[i] = 1
    open_y, open_c1, open_c2 = fos_opening_axes(1000, 1100, 900)
    fr = fos_paxel_accumulate_frame(
        dens,
        mask,
        open_rgb=(1000, 1100, 900),
        open_c1=open_c1,
        open_c2=open_c2,
        delta1=0,
        delta2=0,
        radius_sq=0x7FFFFFFF,
    )
    print(f"  paxel sample N={fr.n} ΣRGB=({fr.sum_r},{fr.sum_g},{fr.sum_b})")
    partial = fos_calc_results_partial(
        open_rgb=(1000, 1100, 900),
        frame_dmin_rgbs=[(1000, 1100, 900), (900, 1000, 800)],
        paxel_acc=fr,
        order_fpo_delta=(0, 0, 0),
    )
    print(
        f"  partial OUT orderAvg={partial.order_avg} "
        f"N={partial.num_pixels} gmR2={partial.gm_rsquare} "
        f"packed={len(partial.to_bytes())}"
    )
    eax, full = fos_calc_results(
        open_rgb=(1000, 1100, 900),
        frame_dmin_rgbs=[(1000, 1100, 900), (900, 1000, 800)],
        paxel_acc=fr,
        helper_frames=[
            FosHelperFrame(c1_lo=10, c2_lo=-5, gate_9cc=0),
            FosHelperFrame(c1_lo=20, c2_lo=-8, gate_9cc=0),
        ],
        dc_gate=10,
        dc_radius=5000,
        dc_w_gm=1000,
        dc_w_ill=1000,
        dc_thresh_n=0,
    )
    print(
        f"  full OUT eax={eax} orderFpo={full.order_fpo} "
        f"ofpo={full.ofpo_method} packed={len(full.to_bytes())}"
    )


if __name__ == "__main__":
    main()
