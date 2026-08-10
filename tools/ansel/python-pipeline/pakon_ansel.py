#!/usr/bin/env python3
"""Ansel colour from shipped Pakon data files (host post-process).

Pakon (docs/11 §5, PakonIMAu strings): stage-2 RPD stays **I16** through
Shasta/SBA (`Only I16 data type is supported by ImaShastaOp`), then
Rpd2Pcs→Srgb.

**Shasta** (``pakon_shasta.py``): dpi aims + toneLut assemble + live image
sampling (``0x1027b970``/``0x1027b3c0``) + I16 ``ImaShastaOp`` apply are
ported (`SHASTA_TONE_LUT_PORTED` / `SHASTA_APPLY_PORTED`). Full analyze
aim producers closed (`SHASTA_ANALYZE_PORTED=True`; Ane Laplacian
collect ``0x1027fc80`` → dens orch). ColorAdjust: contrast LUT +
default-skip / unsharp apply / SpCombine wrapper+ConnectEx prologue leaves
ported; ``COLOR_ADJUST_PORTED=True``; ``PT_MERGE_BODY=True``.

**SRA** (``pakon_sra.py``): shipped ``common-sraFwdLut-metric-*.lut`` is
``AnsCommonSraFwdLutDPI`` — a real Pakon table, but **not** Shasta's
``toneLut``. Fallback path only (median balance) still uses it as a tone
stand-in. Preference path assembles ``engine.tone_lut`` from the scene
image when flags allow; else linked-percentile STAND-IN.

Also: FUGC seed + ``setLutInfo`` on Preference when
``FUGC_ANALYZE_PORTED`` / ``FUGC_METRICS_PORTED`` (``ebp+0x14`` = setShifts OUT @ ``scene+0x4b6``;
``ebp+0x18`` = FindDmin; ``aFilmAimDmin``; seed ``aTableDmin``). SBA:
Preference mode-``0x11`` fragment → ``setshifts_12(A, A)`` (CN second
pass; A≡B from same Sba Cap) → ``apply_balance_shifts``. Preference
hi=``0x10`` FPU is golden (``PREFERENCE_SHIFTS_PORTED``); ``hi≠0x10`` UV
aims still open.

Pipeline here (I16 0..4095 until ICC):

  Preference path (ports True):
    RPD12 → setshifts_12(A,A)+apply → assemble ``engine.tone_lut`` from
          scene (``7b970``/``7b3c0``→``935d0``→builder→Cap) when
          ``SHASTA_TONE_LUT_PORTED`` → ``ImaShastaOp`` I16 apply when
          ``SHASTA_APPLY_PORTED``, else linked percentile STAND-IN →
          FUGC ``setLutInfo``+apply (mode≠2) / metrics+bias LUT (mode==2) → ColorAdjust leaf
          (factory-zero → skip; contrast LUT if non-zero) → Rpd2Pcs→Srgb
    No SRA, no ``aim_medians`` / per-channel re-equalize
    (those cancelled Preference OUT or crushed contrast on Gold 400).

  Fallback (Preference→setShifts apply unavailable):
    RPD12 → median ``channel_balance`` → SRA fwd lut → FUGC seed
          → ``aim_medians(…, NBP)`` → Rpd2Pcs→Srgb

See ``docs/46-ansel-parity-checklist.md``.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

import pakon_color_adjust as color_adjust
import pakon_fugc as fugc_mod
import pakon_ansel_maps as maps
import pakon_sba_apply as sba_apply
import pakon_sba_pcode as sba_pcode
import pakon_sba_preference as sba_pref
import pakon_sba_stage2 as sba_stage2
import pakon_scp_lut as scp_lut
import pakon_scene_context as scene_ctx
import pakon_shasta as shasta_mod
import pakon_sra as sra_mod

RPD_MAX = 4092
SHASTA_MAX = 4095

_DEFAULT_FX35 = Path(
    "/Users/guy/Downloads/Pakon Update 2/fx35install/"
    "program files/Pakon/F-X35 COM SERVER"
)
DEFAULT_ANSEL_ROOT = _DEFAULT_FX35 / "anselinstalldir" / "dataPathItems"
DEFAULT_PROFILE_DIR = DEFAULT_ANSEL_ROOT / "profile"
DEFAULT_COLOR_DIR = _DEFAULT_FX35 / "Config" / "ColorCorrection"

SceneContext = maps.SceneContext
scene_from_filmstock = maps.scene_from_filmstock


def parse_dpi(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _floats(s: str) -> list[float]:
    return [float(x) for x in s.replace(",", " ").split()]


@dataclass
class ShastaParams:
    """Thin view of ``pakon_shasta.ShastaDpi`` aims (not scene toneLut)."""

    white: float = 3000.0
    metric_gray: float = 1618.0
    max_value: float = 4095.0
    shadow_percent: float = 1.0
    highlight_percent: float = 99.0
    code_values_per_button: float = 75.0
    dpi: shasta_mod.ShastaDpi | None = None

    @classmethod
    def load(cls, path: Path) -> "ShastaParams":
        dpi = shasta_mod.ShastaDpi.load(path)
        return cls(
            white=dpi.white,
            metric_gray=dpi.metric_gray,
            max_value=dpi.max_value,
            shadow_percent=dpi.shadow_percent,
            highlight_percent=dpi.highlight_percent,
            code_values_per_button=dpi.code_values_per_button,
            dpi=dpi,
        )


@dataclass
class SbaParams:
    neutral_balance_point: float = 1550.0
    min_dmin: tuple[float, float, float] = (180.0, 550.0, 700.0)
    neu: tuple[float, float, float] = (975.0, 975.0, 975.0)
    neo: tuple[float, float, float] = (1010.0, 1010.0, 1010.0)
    fpo: tuple[float, float, float] = (879.0, 1250.0, 1386.0)
    fpa: tuple[float, float, float] = (-70.0, -55.0, -45.0)
    pcls: float = 0.0  # Preference w1e; AnsSbaDPI+0x24 — all shipped dpi are 0
    neutral_button: float = 130.0
    neutral_under_constraint: float = -16.0
    neutral_over_constraint: float = 16.0
    key: str = "ansel-sba-CN-default"
    pcode_name: str = "pcode-dls_1.7"
    sfs_table_name: str = "sfsTable35"
    dpi_path: Path | None = None

    @classmethod
    def load(cls, path: Path) -> "SbaParams":
        d = parse_dpi(path)
        md = _floats(d["minDmin"]) if "minDmin" in d else [180, 550, 700]
        neu = _floats(d["neu"]) if "neu" in d else [975, 975, 975]
        neo = _floats(d["neo"]) if "neo" in d else [1010, 1010, 1010]
        fpo = _floats(d["fpo"]) if "fpo" in d else [879, 1250, 1386]
        fpa = _floats(d["fpa"]) if "fpa" in d else [-70, -55, -45]
        return cls(
            neutral_balance_point=float(d.get("neutralBalancePoint", 1550)),
            min_dmin=(md[0], md[1], md[2]),
            neu=(neu[0], neu[1], neu[2]),
            neo=(neo[0], neo[1], neo[2]),
            fpo=(fpo[0], fpo[1], fpo[2]),
            fpa=(fpa[0], fpa[1], fpa[2]),
            pcls=float(d.get("pcls", 0)),
            neutral_button=float(d.get("neutralButton", 130)),
            neutral_under_constraint=float(
                d.get("neutralUnderConstraint", -16.0)
            ),
            neutral_over_constraint=float(
                d.get("neutralOverConstraint", 16.0)
            ),
            key=d.get("key", path.stem),
            pcode_name=d.get("pcode", "pcode-dls_1.7"),
            sfs_table_name=d.get("sfsTable", "sfsTable35"),
            dpi_path=path,
        )


def load_sra_fwd_lut(path: Path) -> np.ndarray:
    """Load ``AnsCommonSraFwdLutDPI`` ASCII → (4096,) int table.

    Cite: ``pakon_sra.py`` / DLL ``0x105954a0``. Not Shasta ``toneLut``.
    """
    return sra_mod.load_sra_fwd_lut(path)


def load_fugc_lut(path: Path) -> np.ndarray:
    """Load shipped FUGC **seed** lut → (4096, 3).

    Cite: ``pakon_fugc.load_fugc_seed_lut`` / DLL LutDpi. Preference path
    builds the apply LUT via ``setLutInfo``; fallback still uses seed.
    """
    table, _dmin = fugc_mod.load_fugc_seed_lut(path)
    return table


def load_fugc_seed_and_dmin(path: Path) -> tuple[np.ndarray, tuple[int, int, int]]:
    """Seed table + LutDpi ``aTableDmin`` (Cap ``+0xe0`` / analyze ``+0x60f8``)."""
    table, dmin = fugc_mod.load_fugc_seed_lut(path)
    return table, (int(dmin[0]), int(dmin[1]), int(dmin[2]))


def apply_1d_lut(rpd12: np.ndarray, lut: np.ndarray) -> np.ndarray:
    """Apply (4096,) or (4096,3) lut to RPD codes."""
    idx = np.clip(np.rint(rpd12), 0, 4095).astype(np.int32)
    if lut.ndim == 1:
        return lut[idx].astype(np.float64)
    out = np.empty_like(rpd12, dtype=np.float64)
    for c in range(3):
        out[:, :, c] = lut[idx[:, :, c], c]
    return out


def rpd16_to_rpd12(rpd16: np.ndarray) -> np.ndarray:
    return rpd16.astype(np.float64) * (RPD_MAX / 65535.0)


def rpd12_to_icc_u8(rpd12: np.ndarray) -> np.ndarray:
    """Map I16 RPD codes into U8 for 4096-entry ICC input tables.

    index ≈ u8·4095/255 ⇒ u8 = code·255/4095.
    """
    return np.clip(
        np.rint(rpd12.astype(np.float64) * (255.0 / SHASTA_MAX)), 0, 255
    ).astype(np.uint8)


def channel_balance(rpd12: np.ndarray, mode: str = "median") -> np.ndarray:
    """Legacy median equalise — NOT Pakon SBA (kept for ``--balance`` / fallback)."""
    x = rpd12.astype(np.float64)
    if mode == "highlight":
        refs = np.array([np.percentile(x[:, :, c], 99.0) for c in range(3)])
    else:
        y = x.mean(axis=2)
        mask = y > np.percentile(y, 5.0)
        refs = np.array([
            np.median(x[:, :, c][mask]) if mask.any() else np.median(x[:, :, c])
            for c in range(3)
        ])
    usable = refs[refs > 1.0]
    target = float(usable.mean()) if usable.size else 1.0
    for c in range(3):
        if refs[c] > 1.0:
            x[:, :, c] *= target / refs[c]
    return np.clip(x, 0, SHASTA_MAX)


def preference_shift_words(sba: SbaParams) -> tuple[int, int, int]:
    """Mode-``0x11`` Preference fragment → ``+0x3a38`` words (docs/49)."""
    return sba_pref.preference_shifts_from_dpi_fields(
        fpo=sba.fpo,
        fpa=sba.fpa,
        neutral_balance_point=sba.neutral_balance_point,
        neutral_button=sba.neutral_button,
        under_constraint=sba.neutral_under_constraint,
        over_constraint=sba.neutral_over_constraint,
        pcls=sba.pcls,
    )


def cn_setshifts_apply_words(
    sba: SbaParams,
    planar_3band: tuple[int, ...] | list[int],
    num_lut: int = 4096,
) -> tuple[int, int, int]:
    """CN second-pass apply words: ``setshifts_12(A, A)`` (docs/52).

    VERIFIED: both getShifts Caps are the scene Sba Cap (same ``+0x3a38``),
    so buffer A ≡ B. OUT is written to ``scene+0x4b6`` on the afterSCPLut
    balanceOrder pass (ScpLut zeroes that cluster first).
    """
    a = preference_shift_words(sba)
    return sba_apply.setshifts_12(a, a, planar_3band, num_lut)


def aim_medians(rpd12: np.ndarray, aim: float) -> np.ndarray:
    """Per-channel median → aim (equalises R/G/B). Fallback path only."""
    x = rpd12.astype(np.float64)
    for c in range(3):
        med = float(np.median(x[:, :, c]))
        if med > 1.0:
            x[:, :, c] *= aim / med
    return np.clip(x, 0, SHASTA_MAX)


SHASTA_TWO_ANCHOR_PORTED = False  # shape is ours; only the aims are vendor


def shasta_two_anchor_tone(rpd12: np.ndarray,
                           shasta: "ShastaParams") -> np.ndarray:
    """Two-anchor stand-in for ``AnsShastaCapabilityImpl::analyze``.

    ``pakon_shasta.py`` carries the toneLut *assembly* but not the scene
    ``analyze`` that chooses its aims (``ANALYZE`` is False), so on the
    colour-negative path the assembled LUT does not land the scene on the
    dpi's aims.

    The vendor builds its curve from five measured statistics
    (``extShadowPercent`` 0.1, ``shadowPercent`` 1.0, the scene grey,
    ``highlightPercent`` 99.0, ``extHighlightPercent`` 99.9) moved toward
    aims placed in *buttons* either side of ``metricGray``
    (``blackButtons`` 10.466, ``shadowButtons`` 6.67, ``highlightButtons``
    3.67, ``extHighlightButtons`` 7.68, ``codeValuesPerButton`` 75.0) by
    per-knot aggressiveness factors, with exponential slope limits and
    white-point compression. None of that is reproduced here.

    This reproduces two anchors only — ``shadowPercent`` → ``black``,
    median → ``metricGray``, straight line between them, clamped to
    ``[minValue, maxValue]``. Constants are the dpi's; the shape is not.

    It also runs per channel, which a vendor tone scale does not. That is
    load-bearing here because the data reaching it does not have matched
    channel contrast: on ``08_raw14.tiff`` the negative's own optical
    density spans 0.894/1.061/1.185 decades, but after the polynomial and
    the SRA forward LUT the spans are 462/236/144 code values
    (R:G:B = 1.00:0.51:0.31). A per-channel stretch hides that. The real
    fix is upstream, in the unported ``AnsColorNegativePath`` /
    ``AnsSraCapabilityImpl::makeSRALUTS``.
    """
    x = rpd12.astype(np.float64)
    black = float(getattr(shasta.dpi, "black", 0.0) or 0.0)
    min_value = float(getattr(shasta.dpi, "min_value", 0.0) or 0.0)
    out = np.empty_like(x)
    for c in range(3):
        lo = float(np.percentile(x[:, :, c], shasta.shadow_percent))
        mid = float(np.median(x[:, :, c]))
        span = max(mid - lo, 1.0)
        scale = (shasta.metric_gray - black) / span
        out[:, :, c] = np.clip(
            (x[:, :, c] - lo) * scale + black, min_value, shasta.max_value
        )
    return out


def linked_percentile_tone(
    rpd12: np.ndarray,
    *,
    white: float = 3000.0,
    shadow_percent: float = 1.0,
    highlight_percent: float = 99.0,
    max_value: float = SHASTA_MAX,
) -> np.ndarray:
    """STAND-IN for Shasta ``toneLut`` (pending analyze→export→``ImaShastaOp``).

    Linked core from tag ``working-images-v1`` / ``c5f63c9``
    (``ansel_shasta_tone_rpd12`` in ``pakon_decode.py``): luminance
    ``p{shadow}..p{highlight}`` → ``0..white`` with the **same** offset and
    scale on R, G, B so stage-2 / Preference channel ratios survive into
    Rpd2Pcs.

    Deliberately omits the tag helper's optional highlight channel-balance
    and its post-tone per-channel median→``metricGray`` re-equalize — both
    fight DLL-correct Preference OUT (Gold 400 A=(746,350,189),
    OUT=(688,292,130)). Caller runs Preference/setShifts apply (or median
    ``channel_balance``) first. For the photographic viewing land that
    matched ``working-images-v1``, use ``working_images_v1_tone`` instead.
    """
    x = rpd12.astype(np.float64)
    y = x.mean(axis=2)
    lo = float(np.percentile(y, shadow_percent))
    hi = float(np.percentile(y, highlight_percent))
    if hi <= lo:
        hi = lo + 1.0
    scale = float(white) / (hi - lo)
    x = (x - lo) * scale
    return np.clip(x, 0, float(max_value))


def working_images_v1_tone(
    rpd12: np.ndarray,
    *,
    white: float = 3000.0,
    metric_gray: float = 1618.0,
    shadow_percent: float = 1.0,
    highlight_percent: float = 99.0,
    max_value: float = SHASTA_MAX,
    balance_channels: bool = True,
) -> np.ndarray:
    """Full ``working-images-v1`` / ``c5f63c9`` tone land (viewing path).

    1. Optional highlight p99 channel match (coarse SBA stand-in)
    2. Linked luminance percentile → ``0..white``
    3. Per-channel median → ``metricGray``

    Steps 1+3 are NOT Preference-faithful (they cancel setShifts OUT
    ratios) but are what made tag ``working-images-v1`` look photographic
    with ColNeg + ICC. Use via ``--legacy-tone`` until FOS opening /
    Shasta analyze produce scene-faithful aims.
    """
    x = rpd12.astype(np.float64).copy()
    if balance_channels:
        his = np.array([
            np.percentile(x[:, :, c], highlight_percent) for c in range(3)
        ])
        target = float(his.max()) if his.max() > 0 else 1.0
        for c in range(3):
            if his[c] > 0:
                x[:, :, c] *= target / his[c]
    x = linked_percentile_tone(
        x,
        white=white,
        shadow_percent=shadow_percent,
        highlight_percent=highlight_percent,
        max_value=max_value,
    )
    for c in range(3):
        med = float(np.median(x[:, :, c]))
        if med > 1.0:
            x[:, :, c] *= float(metric_gray) / med
    return np.clip(x, 0, float(max_value))

# Preference opening RGB source labels (docs/48). Host uses dpi fpo until a
# cited FOS→nested-fpo writer exists; do not invent dens maths.
OPENING_FPO_SOURCE_DPI = "dpi-fpo"
OPENING_FPO_SOURCE_FOS = "fos-orderFpo"  # test override only; no DLL edge


@dataclass
class AnselEngine:
    shasta: ShastaParams
    sba: SbaParams
    sra_lut: np.ndarray
    fugc_lut: np.ndarray
    profile_dir: Path
    color_dir: Path
    sra_name: str = ""
    fugc_name: str = ""
    scene: SceneContext | None = None
    selected: maps.SelectedAnselFiles | None = None
    pcode: sba_pcode.DecodedPcode | None = None
    stage2: sba_stage2.Stage2Program | None = None
    sfs_rows: list[tuple[int, int, int, int]] = field(default_factory=list)
    band3_lut: scp_lut.ThreeBandLut | None = None
    setshifts_out: tuple[int, int, int] | None = None
    preference_a: tuple[int, int, int] | None = None
    opening_fpo: tuple[int, int, int] | None = None
    opening_fpo_source: str = OPENING_FPO_SOURCE_DPI
    tone_lut: object = field(default=None, repr=False)  # np.int32 work/Cap table
    fugc_a_table_dmin: tuple[int, int, int] = (500, 500, 500)
    fugc_afilm_aim_dmin: tuple[int, int, int] = fugc_mod.AFILM_AIM_DMIN_DEFAULT
    # Cap +0x60e8: 2 → metrics path; else setLutInfo (analyze @ 0x101fc518…).
    fugc_mode: int = 1
    fugc_work_pct: tuple[float, float, float] | None = None
    # TLA CiImage+0xc8 ColorAdjust (ctor zeros) — UI sliders unset by default.
    color_adjust: color_adjust.ColorAdjustParams = field(
        default_factory=color_adjust.ColorAdjustParams
    )
    # F-135: use the two-anchor Shasta stand-in instead of the partially
    # ported toneLut (AnsShastaCapabilityImpl::analyze is not ported, so the
    # assembled LUT has no scene aims to hit). Set by pakon_decode.py for
    # --model f135. Off elsewhere — nothing else changes behaviour.
    shasta_stand_in: bool = False
    _icc_cache: object = field(default=None, repr=False)

    @classmethod
    def load(cls, ansel_root: Path | str = DEFAULT_ANSEL_ROOT,
             iso: int | None = None,
             scene: SceneContext | None = None,
             *,
             sba_key_override: str | None = None,
             opening_fpo_override: tuple[int, int, int] | None = None,
             opening_fpo_source: str | None = None) -> "AnselEngine":
        """Load map-selected Ansel tables for ``scene``.

        Preference blob fields (``fpo``/``fpa``/``pcls``/NBP/…) come from the
        **selected** ``sba-*.dpi`` (``sba.map`` or ``sba_key_override``), not a
        hardcoded CN-default. Nested opening RGB for Preference is dpi
        ``fpo`` (docs/48) unless ``opening_fpo_override`` is supplied — that
        path is a **test hook** only — DLL has no FOS→nested ``fpo`` edge
        (``FOS_TO_PREFERENCE_FPO_EDGE=False``; ``docs/48``).
        """
        root = Path(ansel_root)
        if scene is None:
            scene = SceneContext(iso=iso)
        elif iso is not None and scene.iso is None:
            scene = replace(scene, iso=iso)

        sel = maps.select_ansel_files(
            root, scene, sba_key_override=sba_key_override
        )
        shasta = ShastaParams.load(sel.shasta_dpi)
        sba = SbaParams.load(sel.sba_dpi)
        sra = load_sra_fwd_lut(sel.sra_lut)
        fugc, fugc_dmin = load_fugc_seed_and_dmin(sel.fugc_lut)
        params_dpi = root / "fugc" / "fugc-defaultParams.dpi"
        afilm_aim = fugc_mod.load_afilm_aim_dmin(params_dpi)

        # Opening RGB: selected dpi fpo, unless an explicit override is given.
        # FOS dens → orderFpo is not ported; do not invent a substitute.
        if opening_fpo_override is not None:
            fpo_i = (
                int(opening_fpo_override[0]),
                int(opening_fpo_override[1]),
                int(opening_fpo_override[2]),
            )
            fpo_src = opening_fpo_source or OPENING_FPO_SOURCE_FOS
            sba = replace(sba, fpo=(float(fpo_i[0]), float(fpo_i[1]), float(fpo_i[2])))
        else:
            fpo_i = sba_pref.opening_rgb_from_sba_fpo(sba.fpo)
            fpo_src = OPENING_FPO_SOURCE_DPI

        pcode = None
        stage2 = None
        sfs_rows: list[tuple[int, int, int, int]] = []
        pcode_path = root / "sba" / "Pcode" / sba.pcode_name
        sfs_path = root / "sba" / "Sfs" / sba.sfs_table_name
        if pcode_path.is_file():
            pcode = sba_pcode.load_pcode(pcode_path)
            stage2 = sba_stage2.parse_decoded(pcode)
        if sfs_path.is_file():
            sfs_rows = sba_pcode.parse_sfs_table(sfs_path)

        band3 = None
        setshifts_out = None
        preference_a = None
        lut_path = scp_lut.find_shipped_3band_lut(root)
        # Both fragments must be golden before Preference→(1,2)→apply is
        # the host default; either False falls back to median channel_balance.
        if (
            lut_path is not None
            and sba_apply.SETSHIFTS_12_PORTED
            and sba_pref.PREFERENCE_SHIFTS_PORTED
        ):
            band3 = scp_lut.load_3band_lut_ascii(lut_path)
            preference_a = preference_shift_words(sba)
            setshifts_out = sba_apply.setshifts_12(
                preference_a, preference_a, band3.planar, band3.num_lut
            )

        print(
            f"  Ansel map: path={scene.ansel_path} src={scene.source_type} "
            f"DX={scene.product_code}"
            f"{'-' + str(scene.gen_code) if scene.gen_code is not None else ''} "
            f"ISO={scene.iso} metric={scene.metric}"
        )
        print(
            f"  SBA select: {sel.sba_selection_reason}  "
            f"file={sel.sba_dpi.name}"
        )
        print(
            f"  Ansel(I16): SBA={sel.sba_key} ({sel.sba_dpi.name})  "
            f"Shasta={sel.shasta_key} ({sel.shasta_dpi.name})  "
            f"SRA={sel.sra_name}[200]={int(sra[200])}  "
            f"FUGC={sel.fugc_name} (contrast={sel.fugc_contrast:g})  "
            f"profile={sel.profile_key}  "
            f"neutral={sba.neutral_balance_point:g}  "
            f"gray/white={shasta.metric_gray:g}/{shasta.white:g}"
        )
        print(
            f"  Preference opening RGB: {fpo_src}={fpo_i} "
            f"({'dpi embed' if fpo_src == OPENING_FPO_SOURCE_DPI else 'override'}; "
            f"docs/48 — FOS→nested fpo VERIFIED absent)  "
            f"fpa={tuple(int(x) for x in sba.fpa)}  "
            f"pcls={int(sba.pcls)}  "
            f"NBP={sba.neutral_balance_point:g}  "
            f"neuBtn={sba.neutral_button:g}  "
            f"under/over={sba.neutral_under_constraint:g}/"
            f"{sba.neutral_over_constraint:g}"
        )
        if pcode is not None and stage2 is not None:
            print(
                f"  SBA pcode: {pcode.name} stage1+stage2 "
                f"(program_words={len(pcode.program)}, "
                f"dim={stage2.dim_a}x{stage2.dim_b}, "
                f"op7={len(stage2.op7)}, stage2_rc=0x{stage2.return_code & 0xffffffff:x}, "
                f"sfs={sba.sfs_table_name} rows={len(sfs_rows)}; "
                f"Preference FPU mapped (docs/49; pcls=w1e={sba.pcls:g}); "
                f"PREFERENCE_SHIFTS_PORTED="
                f"{sba_pref.PREFERENCE_SHIFTS_PORTED})"
            )
        else:
            print(f"  SBA pcode: missing {pcode_path}")
        if setshifts_out is not None and band3 is not None and preference_a is not None:
            print(
                f"  SBA Preference A (mode 0x11 / +0x3a38)={preference_a}  "
                f"setShifts(1,2) OUT={setshifts_out}  lut={band3.name} "
                f"(SETSHIFTS_12_PORTED={sba_apply.SETSHIFTS_12_PORTED})"
            )
        else:
            print(
                "  SBA setShifts(1,2): unavailable — median channel_balance "
                "fallback"
            )
        return cls(
            shasta=shasta,
            sba=sba,
            sra_lut=sra,
            fugc_lut=fugc,
            profile_dir=root / "profile",
            color_dir=DEFAULT_COLOR_DIR,
            sra_name=sel.sra_name,
            fugc_name=sel.fugc_name,
            scene=scene,
            selected=sel,
            pcode=pcode,
            stage2=stage2,
            sfs_rows=sfs_rows,
            band3_lut=band3,
            setshifts_out=setshifts_out,
            preference_a=preference_a,
            opening_fpo=fpo_i,
            opening_fpo_source=fpo_src,
            fugc_a_table_dmin=fugc_dmin,
            fugc_afilm_aim_dmin=afilm_aim,
        )

    def render_scene(self, rpd12: np.ndarray,
                     roll_scale: np.ndarray | None = None) -> np.ndarray:
        """I16 RPD12 → toned I16 (SBA + Shasta + FUGC + ColorAdjust leaf)."""
        preference_apply = self.setshifts_out is not None
        if preference_apply:
            # Preference OUT is the channel balance — skip median roll_scale
            # (it cancels R/G/B ratios from setShifts).
            x = rpd12.astype(np.float64)
            x = sba_apply.apply_balance_shifts(
                x.astype(np.int32), self.setshifts_out
            ).astype(np.float64)
            balanced = x
            # Assemble Cap toneLut from live image sampling when unset
            # (7b970/7b3c0 → 935d0 → builder → setToneLut). Mid-aims from
            # FindDmin + Laplacian collectData dens when ANALYZE is True.
            if self.shasta_stand_in:
                x = shasta_two_anchor_tone(x, self.shasta)
            elif (
                shasta_mod.SHASTA_TONE_LUT_PORTED
                and self.tone_lut is None
                and self.shasta.dpi is not None
            ):
                rgb16 = np.clip(x, 0, self.shasta.max_value).astype(np.int16)
                tone, _bn, _cap, _w = shasta_mod.assemble_scene_tone_lut(
                    self.shasta.dpi,
                    rgb16,
                    setshifts_out=self.setshifts_out,
                )
                self.tone_lut = tone
            if self.shasta_stand_in:
                pass  # already toned above
            elif (
                shasta_mod.SHASTA_TONE_LUT_PORTED
                and self.tone_lut is not None
            ):
                lut = self.tone_lut
                img = np.clip(x, 0, len(lut) - 1).astype(np.int16)
                if shasta_mod.SHASTA_APPLY_PORTED:
                    x = shasta_mod.ima_shasta_op_apply(img, lut).astype(
                        np.float64
                    )
                else:
                    planes = [
                        shasta_mod.ima_shasta_apply_i16(img[:, :, c], lut)
                        for c in range(3)
                    ]
                    x = np.stack(planes, axis=-1).astype(np.float64)
            else:
                x = linked_percentile_tone(
                    x,
                    white=self.shasta.white,
                    shadow_percent=self.shasta.shadow_percent,
                    highlight_percent=self.shasta.highlight_percent,
                    max_value=self.shasta.max_value,
                )
            # FUGC: ebp14 = setShifts OUT @ +0x4b6; ebp18 = FindDmin on
            # post-balance RPD (bag dmin stand-in). Mode≠2 → setLutInfo;
            # mode==2 → bias @ 0x101f79b0 + plane LUT + work metrics.
            if (
                fugc_mod.FUGC_AIM_PROVENANCE_PORTED
                and self.setshifts_out is not None
                and (
                    (
                        self.fugc_mode != 2
                        and fugc_mod.FUGC_SET_LUT_INFO_PORTED
                    )
                    or (
                        self.fugc_mode == 2
                        and fugc_mod.FUGC_METRICS_PORTED
                        and fugc_mod.FUGC_MODE2_LUT_PORTED
                    )
                )
            ):
                bal16 = np.clip(balanced, 0, SHASTA_MAX).astype(np.int16)
                ebp18 = scene_ctx.frame_dmin_rgb_from_planes(
                    bal16[:, :, 0].ravel(),
                    bal16[:, :, 1].ravel(),
                    bal16[:, :, 2].ravel(),
                )
                if self.fugc_mode == 2:
                    apply_lut, _bias, _aims = fugc_mod.build_mode2_apply_lut(
                        self.fugc_lut.astype(np.int32, copy=False),
                        a_table_dmin=self.fugc_a_table_dmin,
                        arg_ebp14=self.setshifts_out,
                        arg_ebp18=ebp18,
                        cap_params_aim=self.fugc_afilm_aim_dmin,
                    )
                    # Work % from R-plane dens hist (Cap work channel stand-in).
                    hist = np.zeros(fugc_mod.FUGC_N, dtype=np.int32)
                    fugc_mod.fugc_hist_accum_i16(bal16[:, :, 0], hist)
                    _metrics = fugc_mod.calc_fugc_metrics_from_hist(
                        hist, bias=_bias
                    )
                    self.fugc_work_pct = _metrics["pct"]  # type: ignore[assignment]
                else:
                    apply_lut, _offs, _aims = fugc_mod.build_setlutinfo_apply_lut(
                        self.fugc_lut.astype(np.int32, copy=False),
                        a_table_dmin=self.fugc_a_table_dmin,
                        arg_ebp14=self.setshifts_out,
                        arg_ebp18=ebp18,
                        cap_params_aim=self.fugc_afilm_aim_dmin,
                    )
                x = apply_1d_lut(x, apply_lut)
            # ColorAdjust after FUGC (IMAu save-path contrast/unsharp gate).
            # Factory-zero params → skip (DEFAULT_SKIP). Contrast LUT when
            # leaf ported + non-zero; unsharp apply still WALL.
            if (
                color_adjust.COLOR_ADJUST_DEFAULT_SKIP_PORTED
                or color_adjust.COLOR_ADJUST_CONTRAST_LUT_PORTED
            ):
                img16 = np.clip(x, 0, SHASTA_MAX).astype(np.int16)
                img16 = color_adjust.apply_preference_color_adjust_i16(
                    img16, self.color_adjust
                )
                x = img16.astype(np.float64)
        else:
            x = rpd12.astype(np.float64)
            if roll_scale is not None:
                x = x * roll_scale.reshape(1, 1, 3)
            x = channel_balance(x, mode="median")
            # SRA fwd lut = AnsCommonSraFwdLutDPI stand-in for Shasta toneLut
            x = apply_1d_lut(x, self.sra_lut)
            x = apply_1d_lut(x, self.fugc_lut)
            x = aim_medians(x, self.sba.neutral_balance_point)
        return np.clip(x, 0, SHASTA_MAX)

    def analyze_roll_scales(self, scenes: list[np.ndarray]) -> np.ndarray:
        """Roll-level channel scales from mean of per-scene median balances."""
        acc = np.zeros(3)
        for sc in scenes:
            y = sc.mean(axis=2)
            mask = y > np.percentile(y, 5.0)
            refs = np.array([
                np.median(sc[:, :, c][mask]) if mask.any()
                else np.median(sc[:, :, c])
                for c in range(3)
            ])
            usable = refs[refs > 1.0]
            target = float(usable.mean()) if usable.size else 1.0
            scale = np.array([target / r if r > 1 else 1.0 for r in refs])
            acc += scale
        return acc / max(len(scenes), 1)

    def to_srgb(self, rpd12_toned: np.ndarray) -> np.ndarray:
        from PIL import Image, ImageCms
        u8 = rpd12_to_icc_u8(rpd12_toned)
        if self._icc_cache is None:
            p1 = self.profile_dir / "Rpd2Pcs_HR200_QS_v5s10.pf"
            p2 = self.profile_dir / "Srgb_v2.pf"
            if not p1.is_file() or not p2.is_file():
                p1 = self.color_dir / "rpd.pf"
                p2 = self.color_dir / "srgb.pf"
            src = ImageCms.getOpenProfile(str(p1))
            dst = ImageCms.getOpenProfile(str(p2))
            self._icc_cache = ImageCms.buildTransformFromOpenProfiles(
                src, dst, "RGB", "RGB",
                renderingIntent=ImageCms.Intent.PERCEPTUAL)
            print(f"  ICC: {p1.name} → {p2.name} (12-bit→U8 encode)")
        im = ImageCms.applyTransform(
            Image.fromarray(u8, mode="RGB"), self._icc_cache)
        return np.asarray(im, dtype=np.uint8)

    def to_cc_srgb(self, rpd12_toned: np.ndarray) -> np.ndarray:
        from PIL import Image, ImageCms
        u8 = rpd12_to_icc_u8(rpd12_toned)
        p1 = self.color_dir / "rpd.pf"
        p2 = self.color_dir / "srgb.pf"
        src = ImageCms.getOpenProfile(str(p1))
        dst = ImageCms.getOpenProfile(str(p2))
        xform = ImageCms.buildTransformFromOpenProfiles(
            src, dst, "RGB", "RGB",
            renderingIntent=ImageCms.Intent.PERCEPTUAL)
        return np.asarray(
            ImageCms.applyTransform(Image.fromarray(u8, mode="RGB"), xform),
            dtype=np.uint8)

    def render_strip(self, rpd16: np.ndarray,
                     spans: list[tuple[int, int]],
                     quiet: bool = False,
                     return_toned: bool = False,
                     *,
                     legacy_tone: bool = False):
        rpd12_full = rpd16_to_rpd12(rpd16)
        scenes = [rpd12_full[a:b] for a, b in spans if b > a]
        # Median roll scales are a fallback AnalyseRoll stand-in only.
        # On the CN Preference path they fight setShifts OUT ratios.
        roll_scale = None
        if (
            not legacy_tone
            and self.setshifts_out is None
            and scenes
        ):
            roll_scale = self.analyze_roll_scales(scenes)
        if legacy_tone and not quiet:
            print(
                "  Ansel tone: working-images-v1 "
                "(highlight balance + linked + metricGray; "
                "skips Preference/Shasta/FUGC)"
            )
        elif not quiet and roll_scale is not None:
            print(f"  Ansel roll channel scales = {roll_scale.round(3)}")
        elif not quiet and self.setshifts_out is not None:
            print("  Ansel roll channel scales: skipped (Preference setShifts)")

        n = rpd16.shape[0]
        out = np.zeros((n, rpd16.shape[1], 3), dtype=np.uint8)
        toned_full = np.zeros((n, rpd16.shape[1], 3), dtype=np.float64)
        covered = np.zeros(n, dtype=bool)

        def _run(a: int, b: int, scale):
            if legacy_tone:
                toned = working_images_v1_tone(
                    rpd12_full[a:b],
                    white=self.shasta.white,
                    metric_gray=self.shasta.metric_gray,
                    shadow_percent=self.shasta.shadow_percent,
                    highlight_percent=self.shasta.highlight_percent,
                    max_value=self.shasta.max_value,
                )
            else:
                toned = self.render_scene(rpd12_full[a:b], scale)
            toned_full[a:b] = toned
            out[a:b] = self.to_srgb(toned)

        for i, (a, b) in enumerate(spans):
            if b <= a:
                continue
            _run(a, b, roll_scale)
            covered[a:b] = True
            if not quiet and i == 0:
                print(f"  Ansel scene[0] toned mean = "
                      f"{toned_full[a:b].mean(axis=(0, 1)).round(0)}")

        if (~covered).any():
            idx = np.flatnonzero(~covered)
            run_a = int(idx[0])
            prev = run_a
            runs = []
            for j in range(1, len(idx)):
                cur = int(idx[j])
                if cur != prev + 1:
                    runs.append((run_a, prev + 1))
                    run_a = cur
                prev = cur
            runs.append((run_a, prev + 1))
            for a, b in runs:
                _run(a, b, None)

        if return_toned:
            return out, toned_full
        return out


def find_frames_rpd(rgb14: np.ndarray,
                    min_frame: int = 900,
                    max_frame: int = 1600,
                    min_gap: int = 40,
                    max_gap: int = 350,
                    min_content_std: float = 40.0) -> list[tuple[int, int]]:
    """Frame split: only *short* bright/flat runs count as inter-frame gaps.

    Trailing empty / near-zero variance strip is dropped so flat-field
    trailers are not equal-sliced into dozens of blank ``*_srgb.png`` frames.
    """
    g = rgb14[:, :, 1].astype(np.float64)
    mean = g.mean(axis=1)
    std = g.std(axis=1)
    score = mean / (std + 30.0)
    k = 11
    score_s = np.convolve(score, np.ones(k) / k, mode="same")
    thr = np.percentile(score_s, 88)
    raw_gap = score_s >= thr

    is_gap = np.zeros(len(raw_gap), dtype=bool)
    i = 0
    n = len(raw_gap)
    while i < n:
        if not raw_gap[i]:
            i += 1
            continue
        j = i
        while j < n and raw_gap[j]:
            j += 1
        if min_gap <= (j - i) <= max_gap:
            is_gap[i:j] = True
        i = j

    frames: list[tuple[int, int]] = []
    in_f = False
    start = 0
    for i, gap in enumerate(is_gap):
        if not in_f and not gap:
            in_f = True
            start = i
        elif in_f and gap:
            if i - start >= min_frame:
                frames.append((start, i))
            in_f = False
    if in_f and n - start >= min_frame:
        frames.append((start, n))

    merged: list[tuple[int, int]] = []
    for a, b in frames:
        if merged and a - merged[-1][1] < min_gap:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))

    final: list[tuple[int, int]] = []
    for a, b in merged:
        if b - a <= max_frame:
            final.append((a, b))
            continue
        pos = a
        while b - pos > max_frame:
            window = score_s[pos + min_frame: min(b, pos + max_frame)]
            if window.size == 0:
                break
            cut = pos + min_frame + int(np.argmax(window))
            final.append((pos, cut))
            pos = cut
        if b - pos >= min_frame // 2:
            final.append((pos, b))
        elif final:
            final[-1] = (final[-1][0], b)

    # Drop blank / near-blank spans (leader flashes + trailer equal-slices).
    kept: list[tuple[int, int]] = []
    for a, b in final:
        if float(std[a:b].mean()) >= float(min_content_std):
            kept.append((a, b))
    return kept
