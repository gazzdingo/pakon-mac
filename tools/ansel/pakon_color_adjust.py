#!/usr/bin/env python3
"""PIColorAdjustPlanar — verified host post-Ansel stage (PakonIMAu / TLA).

Runs **after** ``PIAnselColorSceneBalancePlanar`` (and scale), inside
``CiImage::bSaveToFile`` via ``bApplyColorAdjustments``. Do **not** invent
unsharp amounts or Preference / ``+0x4d0e`` maths.
``COLOR_ADJUST_PORTED = False`` until combine + unsharp match Pakon.

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
   (Kodak ``SpCombineXforms`` — four xforms → one)
6. ``ImaContrastLutOperation`` @ ``0x10014ba6`` (gated; body UNKNOWN)
7. ``ImaUnsharpMaskOperation`` @ ``0x10014dad`` — **after** colour
8. ``ImaICCEffectOperation_profileCombined`` @ ``0x10014fa9``

Profiles live under ``\\Config\\ColorCorrection\\`` (wstr ``0x10575924``).

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

Unsharp (address pin only)
--------------------------
``ImaUnsharpMaskOperation`` constructed after the combined colour
xform. Amount / radius / threshold sources **UNKNOWN** (no trusted
constants isolated this pass).

Ported below
------------
Filename selectors + Lab-abstract apply helper (same approach as
``pakon_decode.apply_abstract_tone``). Full ``SpCombineXforms`` +
unsharp **not** ported.
"""
from __future__ import annotations

from pathlib import Path

COLOR_ADJUST_PORTED = False
COLOR_ADJUST_SELECTORS_PORTED = True

# --- IMAu ---
PI_COLOR_ADJUST_PLANAR = 0x10013BC0
STR_COLOR_ADJUST_PLANAR = 0x10575678
STR_PROFILE0 = 0x10575958
STR_SAT_PROFILE = 0x105757D4
STR_BNW_PROFILE = 0x10575748
STR_PROFILE1 = 0x1057572C
STR_COMBINE = 0x10575700
STR_CONTRAST_LUT = 0x105756E8
STR_UNSHARP = 0x105756C0
STR_ICC_EFFECT = 0x10575698
STR_COLOR_CORR_DIR = 0x10575924  # L"\Config\ColorCorrection\"
SAT_JUMP_TABLE = 0x1001544C

GLOBAL_ROMM_PF = 0x106B2708
GLOBAL_RPD_PF = 0x106B1F08
GLOBAL_SRGB_PF = 0x106B1708

# --- TLA ---
TLA_B_SAVE_TO_FILE = 0x1002D980
TLA_B_LOAD_IMAGE_FROM_BUFFER = 0x1002CAA0
TLA_B_APPLY_COLOR_ADJUSTMENTS = 0x1002A5A0
TLA_CALL_ANSEL_BALANCE = 0x1002CF82  # call [eax+0x64]
TLA_CALL_COLOR_ADJUST = 0x1002A73F  # call [eax+0x38]
TLA_CALL_LOAD_FROM_SAVE = 0x1002DF72
TLA_CALL_ADJUST_FROM_SAVE = 0x1002E193

# params object (arg to PIColorAdjustPlanar)
PARAM_OFF_INPUT_PROFILE = 0x48
PARAM_OFF_BNW_EFFECT = 0x4C
PARAM_OFF_SATURATION = 0x50

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
    import numpy as np
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


def main() -> None:
    print("PIColorAdjustPlanar catalog (IMAu base 0x10000000)")
    print(f"  PIColorAdjustPlanar     {PI_COLOR_ADJUST_PLANAR:#010x}")
    print(f"  TLA bApplyColorAdjust   {TLA_B_APPLY_COLOR_ADJUSTMENTS:#010x}")
    print(f"  after Ansel slot+0x64   {TLA_CALL_ANSEL_BALANCE:#010x}")
    print(f"  COLOR_ADJUST_PORTED={COLOR_ADJUST_PORTED}")
    print("  sat param -5..+5 →", SAT_FILES[0], "…", SAT_FILES[5], "…", SAT_FILES[10])
    for k, v in BNW_FILES.items():
        print(f"  bnw {k} → {v}")


if __name__ == "__main__":
    main()
