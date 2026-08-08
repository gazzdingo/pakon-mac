#!/usr/bin/env python3
"""PIColorAdjustPlanar — verified host post-Ansel stage (PakonIMAu / TLA).

Runs **after** ``PIAnselColorSceneBalancePlanar`` (and scale), inside
``CiImage::bSaveToFile`` via ``bApplyColorAdjustments``. Do **not** invent
unsharp amounts or Preference / ``+0x4d0e`` maths.

``COLOR_ADJUST_PORTED`` stays False until kodakcms ``SpCombineXforms`` is
ported. Unsharp *apply* + stock unity compose are flagged separately below.

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

``SpCombineXforms`` (VERIFIED location; port open)
--------------------------------------------------
IAT ``0x105730fc`` → ``kodakcms.dll!SpCombineXforms``. Profile0 ∘ sat ∘
BnW ∘ profile1. Stock Preference (sat=0→``unity.pf``, BnW∉{1,2,3}→
``unity.pf``, Ansel already sRGB so input profile often skipped) is an
**identity compose** — see ``COLOR_ADJUST_SPCOMBINE_DEFAULT_IDENTITY``.

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
``SpCombine`` identity. Full ``kodakcms!SpCombineXforms`` still open →
``COLOR_ADJUST_PORTED=False``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

COLOR_ADJUST_PORTED = False  # kodakcms SpCombineXforms still open
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
SPCOMBINE_IAT = 0x105730FC  # kodakcms.dll!SpCombineXforms


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
    print("  sat param -5..+5 →", SAT_FILES[0], "…", SAT_FILES[5], "…", SAT_FILES[10])
    for k, v in BNW_FILES.items():
        print(f"  bnw {k} → {v}")
    k, sh = unsharp_kernel_i16()
    print(f"  unsharp amount scale {UNSHARP_AMOUNT_SCALE}  kernel {UNSHARP_KERNEL_1D}")
    print(f"  kernel ints {k} shift {sh} (leaf {KERNEL_QUANT_LEAF:#x})")
    print(f"  SpCombine IAT {SPCOMBINE_IAT:#x} → kodakcms.dll")


if __name__ == "__main__":
    main()
