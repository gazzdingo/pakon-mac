#!/usr/bin/env python3
"""Decode Pakon EP 0x86 strip dumps into coloured frames.

Host-side pipeline (docs/58) — scanner sends raw; we render:

  raw strip → sync/unpack → unit dark×gain (calibration/) → 14-bit
            → stage 2 (default F-135 / TLB 3×10 poly; opt. F-235 LUT+3×4)
            → Ansel stand-in (tools/ansel/):
                 roll FPO → per-scene SBA/Shasta → FUGC lut → Rpd2Pcs→sRGB

Per-pixel dark/gain is mandatory before colour (docs/46-handover-ansel.md).
Tables are valid only for the locked exposure triad in calibration/README.json.

Film / SBA dpi selection (required for ``--icc`` — no silent CN-default):

  --dx PART1[-PART2]   DX → film-products.json → path/ISO → ``sba.map``
  --film-path ColNeg|BnW|POSITIVE|IMPORTED   path only (CN-default unless DX)
  --sba-key ansel-sba-78-13   bypass map for SBA dpi only
  --sba-default              explicit opt-in to ``ansel-sba-CN-default``

Ansel DPI/LUT files otherwise follow vendor ``.map`` selectors (shasta/fugc/
profile) from path + DX + ISO + metric. Preference ``fpo``/``fpa``/… come from
the **selected** ``sba-*.dpi``. Full AnsOrder/pcode is NOT ported.
ColorCorrection / anselinstalldir stay outside the repo — --data-dir /
--ansel-root.

Usage:
  # Every product type (raw14, rpd, ansel_rpd, srgb, cc_srgb, tones) + frames:
  ./pakon_decode.py strip captures/strip_cal.bin out/ --all --sba-default
  ./pakon_decode.py strip captures/strip_cal.bin out/ --color --icc --frames --dx 78-13
  # Transport geometry: pass the capture's motor speed (or rely on *.scan.json).
  # gold400.bin was at 11467 → square; legacy strips at 25802 get ~2.25× stretch.
  ./pakon_decode.py strip captures/gold400.bin out/ --motor-speed 11467 --frames
  # Photographic viewing land (tag working-images-v1) until Preference/Shasta aims exist:
  ./pakon_decode.py strip captures/roll.bin out/ --color --icc --frames --dx 96-1 --legacy-tone --max-frames 12
  ./pakon_decode.py strip captures/test_nofifo.bin out/ --color --icc --sba-default
  ./pakon_decode.py verify-lut

Eyeball ``*_srgb.png`` (ICC output). ``*_rpd.png`` / ``*_ansel_rpd.png`` are
percentile / code previews — not photo finishes. ``*_raw14.png`` is uninverted.

Products (--all):
  strip_raw14.png          linear 14-bit preview
  strip_rpd.png            stage-2 RPD (percentile preview)
  strip_rpd16.tiff         stage-2 RPD 16-bit
  strip_ansel_rpd.png      after SBA/Shasta/FUGC (preview)
  strip_ansel_rpd16.tiff   toned RPD 16-bit
  strip_srgb.png           Ansel Rpd2Pcs→Srgb_v2
  strip_cc_srgb.png        ColorCorrection rpd.pf→srgb.pf
  strip_{warm,cold,sepia}.png   Lab abstract tones
  frames/NN_{raw14,rpd,ansel_rpd,srgb,…}.png

Images stay under captures/ (gitignored). Never commit them.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

# tools/ for colour+filmstock; tools/ansel/ for Ansel/SBA host post-process
_TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(_TOOLS))
sys.path.insert(0, str(_TOOLS / "ansel" / "python-pipeline"))
import pakon_color as pc  # noqa: E402
import pakon_filmstock as film  # noqa: E402
import pakon_ansel as ansel  # noqa: E402
import pakon_color_adjust as color_adjust  # noqa: E402
import pakon_scene_context as scene_ctx  # noqa: E402

WORDS_PER_LINE = 6000          # 2000 px × 3 channels — DpiBase16
PIXELS_PER_LINE = 2000
CHANNELS = 3
RAW14_MAX = 16383
_REPO_ROOT = _TOOLS.parent
DEFAULT_CALIBRATION_DIR = _REPO_ROOT / "calibration"
_FX35 = ("/Users/guy/Downloads/Pakon Update 2/fx35install/"
         "program files/Pakon/F-X35 COM SERVER")
DEFAULT_DATA_DIR = f"{_FX35}/Config/ColorCorrection"
DEFAULT_ANSEL_ROOT = f"{_FX35}/anselinstalldir/dataPathItems"


# --------------------------------------------------------------------------
# wire → 14-bit lines
# --------------------------------------------------------------------------

def load_u16(path: str | Path) -> np.ndarray:
    data = Path(path).read_bytes()
    if len(data) & 1:
        data = data[:-1]
    return np.frombuffer(data, dtype="<u2")


def segment_lines(words: np.ndarray, expect: int = WORDS_PER_LINE) -> np.ndarray:
    """Return (n_lines, expect) u16 array of raw wire words, sync-aligned.

    Vendor searches every word for bit 0 set. Gaps of `expect` are clean lines;
    shorter/longer gaps (FIFO glitches) are skipped so a bad line cannot shear
    the whole strip.
    """
    sync = np.flatnonzero(words & 1)
    if sync.size == 0:
        raise SystemExit(
            "no line-sync markers (bit 0 set). FIFO not reset, or not a raw "
            "EP 0x86 dump. See docs/42-port-remaining-work.md."
        )
    lines = []
    n = words.size
    for i, s in enumerate(sync):
        s = int(s)
        if i + 1 < sync.size:
            end = int(sync[i + 1])
        else:
            end = s + expect
        if end - s != expect or end > n:
            continue
        lines.append(words[s:end])
    if not lines:
        # Fall back: accept the modal gap length if close to expect
        gaps = np.diff(sync)
        if gaps.size == 0:
            raise SystemExit("only one sync marker — capture too short")
        mode = int(np.bincount(gaps).argmax())
        print(f"warning: no exact {expect}-word lines; using modal gap {mode}",
              file=sys.stderr)
        for i, s in enumerate(sync[:-1]):
            s = int(s)
            if int(sync[i + 1]) - s == mode and s + expect <= n:
                seg = np.asarray(words[s:s + mode], dtype=np.uint16)
                if mode < expect:
                    seg = np.pad(seg, (0, expect - mode))
                lines.append(seg[:expect])
    if not lines:
        raise SystemExit("could not segment any scan lines")
    return np.stack(lines, axis=0)


def to_rgb14(lines: np.ndarray) -> np.ndarray:
    """(n, 6000) wire words → (n, 2000, 3) uint16 in the 14-bit domain.

    AD9826 MUX order is R, G, B (docs/42). Bit 0 is the sync flag, so the
    sample lives in bits 15:1; >> 2 folds that into 0..16383 exactly at the
    legal rail 0xFFFE.
    """
    v = (lines.astype(np.uint32) >> 2).astype(np.uint16)
    n = v.shape[0]
    rgb = v.reshape(n, PIXELS_PER_LINE, CHANNELS)
    return np.clip(rgb, 0, RAW14_MAX).astype(np.uint16)


# --------------------------------------------------------------------------
# trilinear CCD deskew
# --------------------------------------------------------------------------

# The sensor senses R, G and B on three physically separate pixel rows, so each
# channel crosses a given point on the film at a different time and the three
# records land on different scan lines. docs/30 has the sensor as trilinear
# [VERIFIED — F-135 Service Manual p.7] but records the row spacing as UNKNOWN;
# docs/46 asks whether a +3 line shift is real. Measured on out_test it is
# +8 / 0 / -8 relative to G, unanimous across frames 02…08 (peak correlations
# 0.91…0.998). Uncorrected, every vertical edge carries rainbow fringing.
#
# The value is in scan lines, so it depends on transport speed and line rate —
# it is not a constant of the sensor. Measure rather than assume: "auto" does.
CCD_LINE_OFFSETS_DEFAULT = (8, 0, -8)
CCD_DESKEW_PORTED = False  # measured here, not read from a vendor table


def measure_ccd_line_offsets(rgb14: np.ndarray,
                             search: int = 24) -> tuple[int, int, int]:
    """Cross-correlate R and B against G along the line axis (axis 0).

    Works in log space so the large per-channel gain differences of a colour
    negative do not dominate the correlation.
    """
    x = np.log(np.clip(rgb14.astype(np.float64), 1, None))
    # a detail-rich middle slab; blank leader correlates on noise
    n = x.shape[0]
    a, b = n // 4, max(n // 4 + 1, 3 * n // 4)
    x = x[a:b]
    x = x - x.mean(axis=(0, 1))
    g = x[:, :, 1]
    out = [0, 0, 0]
    for c in (0, 2):
        ch = x[:, :, c]
        best = None
        for d in range(-search, search + 1):
            s = np.roll(ch, d, axis=0)[search + 1:-(search + 1)]
            gv = g[search + 1:-(search + 1)]
            den = np.sqrt((gv * gv).sum() * (s * s).sum())
            if den <= 0:
                continue
            corr = float((gv * s).sum() / den)
            if best is None or corr > best[0]:
                best = (corr, d)
        if best is not None:
            out[c] = best[1]
    return (out[0], 0, out[2])


def ccd_deskew(rgb14: np.ndarray,
               offsets: tuple[int, int, int]) -> np.ndarray:
    """Shift each channel along the line axis to put the three records back
    on the same piece of film."""
    if not any(offsets):
        return rgb14
    out = rgb14.copy()
    for c, d in enumerate(offsets):
        if d:
            out[:, :, c] = np.roll(rgb14[:, :, c], d, axis=0)
    return out


def average_profile(path: str | Path, max_lines: int = 64) -> np.ndarray:
    """Mean (2000, 3) profile from a short calibration capture."""
    words = load_u16(path)
    lines = segment_lines(words)
    rgb = to_rgb14(lines[:max_lines])
    return rgb.astype(np.float64).mean(axis=0)


def apply_flatfield(rgb: np.ndarray, dark: np.ndarray, empty: np.ndarray,
                    scale: float = 16000.0) -> np.ndarray:
    """Legacy per-column (raw - dark) / (empty - dark) * scale.

    Prefer ``apply_unit_calibration`` with committed ``calibration/*.npy``.
    """
    num = rgb.astype(np.float64) - dark
    den = np.maximum(empty - dark, 1.0)
    out = num / den * scale
    return np.clip(out, 0, RAW14_MAX).astype(np.uint16)


def load_unit_calibration(
    cal_dir: str | Path | None = None,
) -> tuple[np.ndarray, np.ndarray, Path]:
    """Load committed per-pixel dark/gain for post-``to_rgb14`` maths.

    Files: ``dark_2000x3.npy``, ``gain_2000x3.npy`` under ``calibration/``.
    Valid only for the exposure triad in that directory's ``README.json``.

    Domain (cite ``tools/pakon_gate.py`` header + ``calibration/README.json``):
    the committed ``.npy`` tables are in the **EP 0x86 wire** u16 domain
    (``ref_dark.bin`` mean ≈ 1120/1443/1161). ``to_rgb14`` does ``>> 2``, so
    subtractable dark here is ``dark_wire / 4``. Gain is unchanged:

        ((raw_w − dark_w) · gain) / 4  ≡  (raw14 − dark_w/4) · gain
    """
    root = Path(cal_dir) if cal_dir is not None else DEFAULT_CALIBRATION_DIR
    dark_p = root / "dark_2000x3.npy"
    gain_p = root / "gain_2000x3.npy"
    if not dark_p.is_file() or not gain_p.is_file():
        raise FileNotFoundError(
            f"unit calibration missing under {root} "
            f"(need dark_2000x3.npy + gain_2000x3.npy)"
        )
    dark_wire = np.load(dark_p)
    gain = np.load(gain_p)
    if dark_wire.shape != (PIXELS_PER_LINE, CHANNELS):
        raise ValueError(f"{dark_p}: expected {(PIXELS_PER_LINE, CHANNELS)}, "
                         f"got {dark_wire.shape}")
    if gain.shape != (PIXELS_PER_LINE, CHANNELS):
        raise ValueError(f"{gain_p}: expected {(PIXELS_PER_LINE, CHANNELS)}, "
                         f"got {gain.shape}")
    # Wire → 14-bit dark. Leave .npy on disk in wire domain for pakon_gate.
    dark14 = dark_wire.astype(np.float64) * 0.25
    return dark14, gain.astype(np.float64, copy=False), root


def apply_unit_calibration(
    rgb: np.ndarray,
    dark: np.ndarray,
    gain: np.ndarray,
) -> np.ndarray:
    """``corrected = (raw - dark) * gain``, clamp to 14-bit.

    ``raw`` / ``dark`` are in the post-``to_rgb14`` domain. ``dark`` must
    come from ``load_unit_calibration`` (wire/4), not the raw ``.npy``.
    Cite: ``calibration/README.json``, ``docs/46-handover-ansel.md``,
    ``tools/pakon_gate.py`` (domain note).
    """
    out = (rgb.astype(np.float64) - dark) * gain
    return np.clip(out, 0, RAW14_MAX).astype(np.uint16)


# --------------------------------------------------------------------------
# colour: vectorised vendor kernel
# --------------------------------------------------------------------------

def load_true_lut(data_dir: str) -> np.ndarray:
    """Load `_ClientColNegLut.txt` exactly as the kernel uses it.

    The file is float text; TLA.dll's generator stores int32 via `_ftol`
    (truncate toward zero). The MMX path indexes that table with
    `and eax, 0x3fff` / `dword [lut+eax*4]`.
    """
    path = os.path.join(data_dir, "_ClientColNegLut.txt")
    if not os.path.exists(path):
        raise SystemExit(
            f"missing {path}\n"
            "Need the vendor ColorCorrection dir (not shipped in this repo)."
        )
    floats = pc.load_vendor_lut(path)
    if len(floats) != pc.LUT_SIZE:
        raise SystemExit(f"{path}: expected {pc.LUT_SIZE} entries, got {len(floats)}")
    # MSVC _ftol: truncate toward zero. All vendor values are >= 0.
    lut = np.array([int(v) for v in floats], dtype=np.int32)
    print(f"  LUT: {path}")
    print(f"       entries={lut.size}  "
          f"[0]={lut[0]}  [1]={lut[1]}  [16383]={lut[16383]}")
    return lut


def render_rpd(rgb14: np.ndarray, data_dir: str,
               offsets: str = "dmin",
               model: str = pc.DEFAULT_MODEL,
               source: str = "auto") -> np.ndarray:
    """(n, w, 3) uint14 → (n, w, 3) uint16 scaled from 12-bit RPD.

    Stage 2 depends on scanner family (docs/58):

      f135 (default) — TLB.dll ``fcn.1000d880`` 3×10 float poly → clamp 0..4095
      f235           — density LUT + 3×4 matrix → clamp 0..4092 (TLA / docs/11)

    F-235 offset column (``offsets``) is ignored on the F-135 path:

      dmin      — rebuild from measured film-base Dmin (flat-fielded strips)
      template  — verbatim `_ClientColNegMat.txt` column 3
    """
    if model == "f135":
        # TLB.dll @ 0x1000d880 — F-135 colour-negative stage 2
        coeffs = pc.load_unit_matrix(source)
        print(f"  model: f135 (TLB 3×10 poly, source={source})")
        print(f"  coeffs diagonal "
              f"{coeffs[0]:.6f} {coeffs[11]:.6f} {coeffs[22]:.6f}")
        rpd12 = pc.poly_hwc(rgb14, coeffs, film_class=1)
        rpd_max = pc.RPD_MAX_BY_MODEL["f135"]
        print(f"  RPD mean RGB = {rpd12.mean(axis=(0, 1)).round(1)}  "
              f"max = {rpd12.max(axis=(0, 1))}")
        return (rpd12 * (65535.0 / rpd_max)).astype(np.uint16)

    # F-235 / F-335 path (PakonIMAu MMX + TLA LUT/matrix)
    lut = load_true_lut(data_dir)
    mat_path = os.path.join(data_dir, "_ClientColNegMat.txt")
    if not os.path.exists(mat_path):
        raise SystemExit(f"missing {mat_path}")
    matrix = pc.load_vendor_matrix(mat_path)
    coeff, template_offset = pc.quantise_matrix(matrix)
    coeff = np.asarray(coeff, dtype=np.float64)
    print(f"  model: f235 (LUT + 3×4)")
    print(f"  matrix: {mat_path}")

    idx = rgb14.astype(np.int32) & 0x3FFF
    d = lut[idx].astype(np.float64)
    acc = np.einsum("...c,ic->...i", d, coeff) / (pc.COEFF_FIXED * 8.0)

    if offsets == "template":
        offset = np.asarray(template_offset, dtype=np.float64)
        print(f"  offsets: template {offset}")
    else:
        # offset ≈ −(M₃ₓ₃ · Dmin)/8 so clear film base → RPD ≈ 0
        dmin = np.empty(3, dtype=np.float64)
        for c in range(3):
            hi = np.percentile(rgb14[:, :, c], 99.0)
            dmin[c] = float(lut[int(hi) & 0x3FFF])
        m33 = np.asarray([[matrix[i][c] for c in range(3)] for i in range(3)],
                         dtype=np.float64)
        offset = -(m33 @ dmin) / 8.0
        print(f"  offsets: from Dmin {dmin.round(1)} → {offset.round(1)}")

    rpd = np.clip(np.rint(acc + offset), 0, pc.RPD_MAX)
    print(f"  RPD mean RGB = {rpd.mean(axis=(0, 1)).round(1)}  "
          f"max = {rpd.max(axis=(0, 1)).round(1)}")
    return (rpd * (65535.0 / pc.RPD_MAX)).astype(np.uint16)


def rpd_preview_u8(rpd16: np.ndarray) -> np.ndarray:
    """8-bit preview with per-channel percentile stretch (stand-in for Ansel).

    Fine for eyeballing strip_rpd.png — NOT valid ICC input.
    """
    out = np.empty(rpd16.shape, dtype=np.uint8)
    for c in range(3):
        ch = rpd16[:, :, c].astype(np.float64)
        lo, hi = np.percentile(ch, (1.0, 99.0))
        if hi <= lo:
            hi = lo + 1.0
        out[:, :, c] = np.clip((ch - lo) * 255.0 / (hi - lo), 0, 255).astype(np.uint8)
    return out


def roll_balance_rpd(rpd16: np.ndarray) -> np.ndarray:
    """Simple roll-level channel balance on stored RPD (pre-Ansel)."""
    out = rpd16.astype(np.float64)
    his = np.array([np.percentile(out[:, :, c], 99.0) for c in range(3)])
    target = float(his.max()) if his.max() > 0 else 1.0
    for c in range(3):
        if his[c] > 0:
            out[:, :, c] *= target / his[c]
    return np.clip(out, 0, 65535).astype(np.uint16)


# BnW abstracts — selectors from PIColorAdjustPlanar (pakon_color_adjust)
TONE_PROFILES = {
    k: v for k, v in color_adjust.TONE_ALIAS.items()
    if k in ("cold", "warm", "sepia")
}


def toning_profile_for_path(path: str, tone: str | None) -> str | None:
    """Pick a ColorCorrection abstract .pf for B&W toning."""
    if path != film.PATH_BNW:
        if tone in (None, "none"):
            return None
    tone = tone or "warm"
    return TONE_PROFILES.get(tone)


def apply_abstract_tone(srgb_u8: np.ndarray, data_dir: str,
                        abstract: str) -> np.ndarray:
    """Lab→Lab abstract (warm/cold/sepia) on 8-bit sRGB."""
    try:
        return color_adjust.apply_lab_abstract(
            srgb_u8, Path(data_dir), abstract)
    except FileNotFoundError as e:
        raise SystemExit(str(e)) from e


def raw14_preview_u8(rgb14: np.ndarray) -> np.ndarray:
    return (rgb14.astype(np.uint32) * 255 // 16383).astype(np.uint8)


def rpd12_preview_u8(rpd12: np.ndarray) -> np.ndarray:
    """Percentile preview of 12-bit Ansel-toned RPD (not ICC)."""
    out = np.empty(rpd12.shape, dtype=np.uint8)
    for c in range(3):
        ch = rpd12[:, :, c].astype(np.float64)
        lo, hi = np.percentile(ch, (1.0, 99.0))
        if hi <= lo:
            hi = lo + 1.0
        out[:, :, c] = np.clip((ch - lo) * 255.0 / (hi - lo), 0, 255).astype(
            np.uint8)
    return out


def rpd12_to_u16(rpd12: np.ndarray) -> np.ndarray:
    return np.clip(
        np.rint(rpd12 * (65535.0 / ansel.SHASTA_MAX)), 0, 65535
    ).astype(np.uint16)


# --------------------------------------------------------------------------
# F-135 negative → positive (docs/58 §3.5 / §15.1)
# --------------------------------------------------------------------------

# No DLL call site computes what f135_rom12_to_rpd12 computes. docs/58 §3.5 is
# [VERIFIED] that no density LUT is applied between fcn.1000d880 and Ansel, and
# where the F-135 inverts is still open (docs/58 §16). Every constant used below
# is the vendor's; the arrangement is ours. Rendered F-135 colour is provisional.
F135_INVERT_PORTED = False

def _film_base_code(plane: np.ndarray, n_bins: int = 4096) -> int:
    """FindDmin on one plane, histogrammed with numpy for strip-sized data.

    The walk itself is the vendor's — ``find_dmin_code_from_hist`` @
    ``0x100093f0…0x1000941f``, high side down, ``thr = n // 1000``.
    """
    v = np.clip(plane, 0, n_bins - 1).astype(np.int64).ravel()
    counts = np.bincount(v, minlength=n_bins).tolist()
    thr = scene_ctx.find_dmin_thr_n_pixels(v.size)
    return scene_ctx.find_dmin_code_from_hist(counts, thr, n_bins=n_bins)


def f135_rom12_to_rpd12(lin12: np.ndarray,
                        pedestal: tuple[float, float, float],
                        fpo: tuple[float, float, float],
                        setshifts: tuple[int, int, int] | None,
                        quiet: bool = False) -> np.ndarray:
    """(h, w, 3) linear 12-bit poly output → (h, w, 3) RPD12 positive.

    Nothing ahead of this inverts: ``fcn.1000d880``'s diagonal on this unit is
    +0.289 / +0.276 / +0.278, so the polynomial preserves polarity (docs/58
    §12). As on the F-235 path, the logarithm is what turns a negative the
    right way up (docs/58 §3.5, §5).

        rpd12 = fpo + 1000 * ( log10(filmBase - c9) - log10(lin - c9) )

    This no longer applies the SRA forward LUT. That is a binary result, not
    taste: ``AnsSraCapabilityImpl::analyze`` (PakonIMAu.dll:0x101a7080) always
    finishes by composing the forward table (dpi+0x68) with the *backward*
    table (dpi+0x64) — ``0x101a3ce0`` at ``0x101a751b`` / ``0x101a7540`` /
    ``0x101a7566`` — and the pair round-trips to within 3 codes, so the
    finished SRA operator is metric-preserving. The vendor never applies the
    forward table on its own. docs/58 §16.

    ``c9`` is the polynomial's own per-channel constant (159.59 / 444.75 /
    635.54 on this unit): a pedestal in the LINEAR domain, which has to come
    off before the log or the channel contrasts come out wrong. With it off,
    the channel density spans reproduce the negative's own to about 2 %.

    ``filmBase`` is FindDmin, which walks the histogram from the high side and
    so returns maximum transmission — the clear film base. It is placed on the
    DPI's ``fpo`` (the orange-mask aim), because the SBA balance that runs next
    is sized to carry it from there to the neutral balance point:
    fpo + setShifts = 1567 / 1542 / 1516 against nbp 1550.
    """
    lin = np.asarray(lin12, dtype=np.float64)
    ped = np.asarray(pedestal, dtype=np.float64)
    base = np.array([_film_base_code(lin[:, :, c]) for c in range(3)],
                    dtype=np.float64)
    base_log = np.log10(np.maximum(base - ped, 1.0))
    dens = 1000.0 * (base_log - np.log10(np.maximum(lin - ped, 1.0)))
    out = np.clip(np.asarray(fpo, dtype=np.float64) + dens, 0, ansel.SHASTA_MAX)
    if not quiet:
        ss = np.array(setshifts if setshifts is not None else (0, 0, 0),
                      dtype=np.float64)
        print(f"  F-135 invert: film base (linear 12-bit) = {base.round(0)}  "
              f"poly pedestal c9 = {ped.round(2)}")
        print(f"  F-135 invert: base lands on fpo{np.asarray(fpo).round(0)}, "
              f"setShifts{ss.round(0)} carries it to {(np.asarray(fpo) + ss).round(0)}")
        print(f"  F-135 invert: RPD12 mean = {out.mean(axis=(0, 1)).round(1)}")
    return out


# --------------------------------------------------------------------------
# frame split (heuristic; vendor uses DetectFilm_G / DetectWhite_G)
# --------------------------------------------------------------------------

def find_frames(rgb14: np.ndarray, min_gap: int = 50,
                min_frame: int = 900) -> list[tuple[int, int]]:
    """Split strip into frames (bright/flat gaps; split oversized merges)."""
    return ansel.find_frames_rpd(rgb14, min_frame=min_frame, min_gap=min_gap)


# --------------------------------------------------------------------------
# I/O
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Transport geometry (square pixels)
# --------------------------------------------------------------------------
#
# Pakon does not hardcode a resample factor. It pairs MotorSpeedPlus with the
# exposure line clock so raw lines are already square for the selected DpiBase.
# Offline we recover the same relation:
#
#   across  = CCD_px / film_height_mm          (sensor, fixed for a geometry)
#   along   ∝ line_rate / motor_speed          (transport)
#   scale   = across / along                   (PIL stretch on the line axis)
#
# Register 0xA5 units are unknown (docs/12); light-board 0x91 is the line-rate
# register in our calibration triad. Absolute Hz/mm/s drop out if we anchor the
# relation at one speed where the along-film sampling is independently known.
#
# WHERE THE ANCHOR COMES FROM  (this used to be wrong by 1.938×)
# --------------------------------------------------------------
# Our exposure triad is *locked* — integration 4093 / lamp N 982 / 0x91 = 60 —
# and calibration/README.json records which base it was measured at:
#
#     "dpi_base": "DpiBase16_35"
#
# So the triad is DpiBase16's. The vendor's own frame size for that base is
# FRAME_SIZES_000: HR_HEIGHT_BASE16_35 = 2000, HR_WIDTH_BASE16_35 = 3000
# (docs/56 §2.7, and docs/30's table agrees). 3000 lines over the 36 mm exposed
# length is 83.333 lines/mm — equal to 2000 px over 24 mm across. Square.
#
# DpiBase16's MotorSpeedPlus is 5917. Therefore, with our triad held at
# DpiBase16's values, **speed 5917 at line_rate 60 is the square-pixel point**,
# and scale is 1.0 there. Not 11467.
#
# The old anchor was MOTOR_SPEED[8] = 11467, taken from "~1380 brightness-gap
# lines at speed 25802 map to ~3000". That inference assumed the undocumented
# early captures ran at 25802, and their own data does not support it (see
# ``geometry`` below). The vendor's frame-size table needs no such assumption.
#
# CHECK, AGAINST DATA, WITH NO SCANNER
# ------------------------------------
#   lines/mm(speed, lr) = 83.333 * (5917 / speed) * (lr / 60)
#
#   captures/gold400.bin — sidecar says speed 11467, line_rate 60
#     predicted   83.333 * 5917/11467      = 43.00 lines/mm
#                 * 38 mm frame pitch      = 1634 lines
#     measured    frame pitch              = 1656 lines   (+1.3 %)
#
# 1656 is also what docs/54 (~1014, ~1324) and docs/46 (~1460) were seeing:
# every measured pitch in this repo is in the 1300–1900 band, and none of them
# is anywhere near the 3167 the old anchor predicted for gold400.
#
# ``python3 tools/pakon_decode.py geometry [capture.bin ...]`` re-runs the
# derivation and, given a capture, measures its pitch and reports the residual.
#
# Same class of bug as the integration/N/line-rate triad: values that are
# really one matched setting, split across three registers.
#
# STILL NEEDS A MACHINE
# ---------------------
# * ACROSS_PX_PER_MM rests on the vendor's frame-size table, not on our data:
#   no film edge falls inside the 2000-px window (the leader region is uniform
#   right across it), so the sensor's mm-per-pixel is not measurable from any
#   capture we hold. A scan of a target with known across-film spacing would
#   settle it.
# * Whether the vendor also changes the line clock per base. It must, since
#   the hive speeds 25802/11467/5917 are not in the 4:3:2 ratio that the
#   1000×1500 / 1500×2250 / 2000×3000 output sizes require at a fixed clock.
#   That does not affect us — we never change the triad — but it is why the
#   hive's *other* two speeds cannot be used to cross-check this anchor.

CCD_ACROSS_PX = 2000
FILM_ACROSS_MM = 24.0
ACROSS_PX_PER_MM = CCD_ACROSS_PX / FILM_ACROSS_MM  # ≈ 83.333

FRAME_PITCH_MM = 38.0   # 8 perforations; == pakon_framing.FRAME_PITCH_MM
FRAME_IMAGE_MM = 36.0   # exposed length

# Hive MotorSpeedPlus (HKLM\…\DpiBase<N>_35) — same table as pakon_scan.
MOTOR_SPEED = {4: 25802, 8: 11467, 16: 5917}
REF_LINE_RATE = 60
# Square-pixel motor for our locked (DpiBase16) exposure triad. See above.
SQUARE_MOTOR_SPEED = MOTOR_SPEED[16]

# Kept as a named constant because pakon_scan and the app refer to it, but it
# is NO LONGER a silent fallback: see resolve_transport_scale. The claim that
# the undocumented early captures ran here is contradicted by their own pitch
# (strip_cal implies ~13900, roll implies ~9900 — both nearer 11467 than
# 25802, and 25802 would need pitches near 726 lines, not 1349 and 1891).
LEGACY_DEFAULT_MOTOR_SPEED = MOTOR_SPEED[4]

TARGET_LINES_PER_FRAME = 3000  # DpiBase16 vendor frame along-travel samples


def transport_scale(speed: float,
                    line_rate: float = REF_LINE_RATE) -> float:
    """Resample factor so transport pixels match across-CCD mm spacing.

    ``scale = (across_px/mm) / (along_lines/mm)`` with
    ``along ∝ line_rate / speed``, anchored so
    ``transport_scale(SQUARE_MOTOR_SPEED, REF_LINE_RATE) == 1``.
    """
    if speed <= 0 or line_rate <= 0:
        raise ValueError(f"speed and line_rate must be > 0 (got {speed}, {line_rate})")
    return (float(speed) / SQUARE_MOTOR_SPEED) * (REF_LINE_RATE / float(line_rate))


def along_lines_per_mm(speed: float,
                       line_rate: float = REF_LINE_RATE) -> float:
    """Lines per millimetre of film travel at this transport setting."""
    return ACROSS_PX_PER_MM / transport_scale(speed, line_rate)


def transport_scale_from_pitch(pitch_lines: float,
                               pitch_mm: float = FRAME_PITCH_MM) -> float:
    """Square-pixel factor from a *measured* frame pitch, no speed needed.

    This is the more direct route: it needs neither the sidecar nor the
    anchor, only the knowledge that consecutive 35 mm frames are 38 mm apart.
    ``pakon_framing.estimate_pitch`` produces the input.
    """
    if pitch_lines <= 0 or pitch_mm <= 0:
        raise ValueError(f"pitch must be > 0 (got {pitch_lines}, {pitch_mm})")
    return ACROSS_PX_PER_MM / (float(pitch_lines) / float(pitch_mm))


def implied_motor_speed(pitch_lines: float,
                        line_rate: float = REF_LINE_RATE,
                        pitch_mm: float = FRAME_PITCH_MM) -> float:
    """The transport speed a measured pitch implies. Inverse of the above."""
    lpm = float(pitch_lines) / float(pitch_mm)
    return SQUARE_MOTOR_SPEED * (ACROSS_PX_PER_MM / lpm) * (float(line_rate) / REF_LINE_RATE)


# No sidecar and no measurement means we do not know the transport speed. The
# honest factor then is 1.0 — leave the geometry alone and say so — rather than
# a guessed speed. resolve_transport_scale returns a source string that makes
# the difference visible; the app surfaces it.
DEFAULT_TRANSPORT_SCALE = 1.0


def load_capture_sidecar(capture: Path | str) -> dict | None:
    """Read ``*.scan.json`` next to a ``.bin`` (written by pakon_scan)."""
    p = Path(capture)
    for cand in (p.with_suffix(".scan.json"),
                 Path(str(p) + ".scan.json"),
                 p.with_suffix(".json")):
        if not cand.is_file() or cand == p:
            continue
        try:
            data = json.loads(cand.read_text())
        except (OSError, json.JSONDecodeError, UnicodeError):
            continue
        if isinstance(data, dict):
            return data
    return None


def resolve_transport_scale(
        *,
        transport_scale_override: float | None = None,
        motor_speed: int | float | None = None,
        dpi_base: int | None = None,
        line_rate: int | float | None = None,
        capture: Path | str | None = None,
        measured_pitch_lines: float | None = None,
) -> tuple[float, str]:
    """Pick the unsquash factor, and say where it came from.

    Order: override > explicit speed/base > capture sidecar > measured frame
    pitch > 1.0 with an "unknown" note. There is deliberately no guessed
    speed at the end of that chain — see DEFAULT_TRANSPORT_SCALE.

    When both a sidecar speed and a measured pitch are available the sidecar
    wins (it is a recorded fact, not an estimate) but the residual between the
    two is appended to the source string. That residual is the only offline
    check we have that the anchor is right, so it is always reported.
    """
    if transport_scale_override is not None:
        return float(transport_scale_override), "explicit --transport-scale"

    lr = float(line_rate) if line_rate is not None else float(REF_LINE_RATE)
    speed: float | None = float(motor_speed) if motor_speed is not None else None
    note = ""

    if dpi_base is not None:
        if dpi_base not in MOTOR_SPEED:
            raise ValueError(f"dpi_base must be one of {tuple(MOTOR_SPEED)}")
        speed = float(MOTOR_SPEED[dpi_base])
        note = f"DpiBase{dpi_base} MotorSpeedPlus"

    if speed is None and capture is not None:
        meta = load_capture_sidecar(capture)
        if meta:
            cfg = meta.get("config") if isinstance(meta.get("config"), dict) else {}
            raw_speed = meta.get("speed", cfg.get("speed"))
            raw_lr = (meta.get("line_rate_0x91")
                      or cfg.get("line_rate_0x91")
                      or meta.get("line_rate"))
            if raw_speed is not None:
                speed = float(raw_speed)
                note = f"sidecar {Path(capture).name}"
            if raw_lr is not None and line_rate is None:
                lr = float(raw_lr)

    if speed is None:
        if measured_pitch_lines:
            ts = transport_scale_from_pitch(measured_pitch_lines)
            return ts, (f"measured frame pitch {measured_pitch_lines:.0f} lines "
                        f"over {FRAME_PITCH_MM:g} mm → scale={ts:.4f} "
                        f"(implies speed ≈ "
                        f"{implied_motor_speed(measured_pitch_lines, lr):.0f}; "
                        f"no sidecar — run pakon_scan to record one)")
        return DEFAULT_TRANSPORT_SCALE, (
            "transport speed UNKNOWN — no --motor-speed/--dpi-base, no "
            ".scan.json sidecar, no measured pitch. Leaving geometry "
            "unchanged (scale=1.0) rather than guessing a speed.")

    ts = transport_scale(speed, lr)
    src = (f"{note + '; ' if note else ''}"
           f"speed={int(speed) if speed == int(speed) else speed} "
           f"line_rate={int(lr) if lr == int(lr) else lr} "
           f"→ scale={ts:.4f} "
           f"(square @{SQUARE_MOTOR_SPEED}/{REF_LINE_RATE})")
    if measured_pitch_lines:
        pred = along_lines_per_mm(speed, lr) * FRAME_PITCH_MM
        err = (measured_pitch_lines - pred) / pred * 100.0
        src += (f"; predicts {pred:.0f}-line pitch, measured "
                f"{measured_pitch_lines:.0f} ({err:+.1f} %)")
    return ts, src


def unsquash_transport(rgb: np.ndarray, scale: float = DEFAULT_TRANSPORT_SCALE) -> np.ndarray:
    """Resample the line (transport) axis so pixels are square.

    `rgb` is (n_lines, ccd, 3). After this, a full frame is ~3000×2000 and
    aspect 3:2 when the capture was at the matched Pakon speed/line-rate pair.
    Mismatched transport (too fast) compresses the travel axis; scale > 1
    stretches it back.
    """
    if abs(scale - 1.0) < 1e-6:
        return rgb
    from PIL import Image
    n_lines, ccd, _ = rgb.shape
    new_lines = max(1, int(round(n_lines * scale)))
    # PIL resize takes (W, H) = (ccd, lines)
    if rgb.dtype == np.uint8:
        im = Image.fromarray(rgb, mode="RGB")
        return np.asarray(im.resize((ccd, new_lines), Image.Resampling.LANCZOS))
    out = np.empty((new_lines, ccd, 3), dtype=np.uint16)
    for c in range(3):
        plane = Image.fromarray(rgb[:, :, c].astype(np.uint32), mode="I")
        plane = plane.resize((ccd, new_lines), Image.Resampling.LANCZOS)
        out[:, :, c] = np.clip(np.asarray(plane), 0, 65535).astype(np.uint16)
    return out


# The scanner's lens inverts the image it projects onto the CCD, so the
# capture is upside-down and back-to-front relative to the scene — a 180°
# rotation, not a mirror. docs/46 §5 listed orientation as open ("six variants
# tried, all judged wrong"; "a lens inverts the image; a flip may be required
# that I never applied"). It is settled now, from legible text: frame 04 of
# captures/strip_cal.bin carries shop signage that reads as upright, correct
# (un-mirrored) words only after a 180° rotation of what rot90(k=1) produced.
#
# rot90(k=1) followed by 180° is exactly rot90(k=-1), so the fix is the sign
# of the single rotation the decoder already did — no extra resample, no
# mirror, and the array stays C-contiguous.
#
# ORDER MATTERS, AND IT IS FIXED HERE: ccd_deskew runs on the capture's own
# (n_lines, ccd) axes, before this function, so its offsets stay in capture
# scan lines and keep their measured sign (R +8 / G 0 / B −8). Anything that
# deskews *after* this rotation — the Go pipeline reads the raw14 TIFF this
# writes — is looking at an axis that now runs backwards, and must negate
# them. See analysis/pipeline/main.go's deskew block.
ROTATE_180_FOR_LENS = True


def to_frame_image(rgb: np.ndarray,
                   transport_scale: float = DEFAULT_TRANSPORT_SCALE) -> np.ndarray:
    """(n_lines, ccd, 3) → display image, square pixels, transport axis on x.

    1. Resample transport axis (fix squashed pixels from fast motor)
    2. rot90 CW — the strip reads along x, and the scene is the right way up
       because the lens inverted it (see ROTATE_180_FOR_LENS above)
    """
    rgb = unsquash_transport(rgb, transport_scale)
    k = -1 if ROTATE_180_FOR_LENS else 1
    return np.ascontiguousarray(np.rot90(rgb, k=k))


def write_png(path: Path, rgb_u8: np.ndarray,
              transport_scale: float = DEFAULT_TRANSPORT_SCALE) -> None:
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(to_frame_image(rgb_u8, transport_scale), mode="RGB").save(path)


def write_tiff16(path: Path, rgb16: np.ndarray,
                 transport_scale: float = DEFAULT_TRANSPORT_SCALE) -> None:
    """Write 16-bit RGB TIFF via pakon_color (PIL has no RGB uint16 array mode)."""
    import pakon_color as _pc
    framed = to_frame_image(rgb16, transport_scale)
    h, w, _ = framed.shape
    path.parent.mkdir(parents=True, exist_ok=True)
    _pc.write_tiff(str(path), w, h, np.ascontiguousarray(framed).astype("<u2").tobytes())


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_strip(args: argparse.Namespace) -> int:
    want_all = bool(args.all)
    want_color = bool(args.color or want_all)
    want_icc = bool(args.icc or want_all)
    want_frames = bool(args.frames or want_all)
    want_tiff = bool(args.tiff or want_all)

    sba_key_override = getattr(args, "sba_key", None)
    film_path = getattr(args, "film_path", None)
    sba_default = bool(getattr(args, "sba_default", False))
    if want_icc and not (
        args.dx or film_path or sba_key_override or sba_default
    ):
        print(
            "error: --icc requires an explicit film/SBA selection "
            "(--dx, --film-path, --sba-key, or --sba-default). "
            "Captures do not carry DX; do not silently assume CN-default.",
            file=sys.stderr,
        )
        return 2

    words = load_u16(args.input)
    print(f"{args.input}: {words.size} words, "
          f"{100.0 * (words & 1).sum() / words.size:.3f}% sync")
    lines = segment_lines(words)
    if args.max_lines:
        lines = lines[:args.max_lines]
    print(f"segmented {lines.shape[0]} lines × {PIXELS_PER_LINE} px")

    rgb = to_rgb14(lines)
    for c, name in enumerate("RGB"):
        ch = rgb[:, :, c]
        print(f"  {name}: mean={ch.mean():.0f}  "
              f"p01={np.percentile(ch, 1):.0f}  p99={np.percentile(ch, 99):.0f}")

    if args.dark and args.empty:
        dark = average_profile(args.dark)
        empty = average_profile(args.empty)
        print(f"legacy flat-field from {args.dark} / {args.empty}")
        rgb = apply_flatfield(rgb, dark, empty)
    elif not args.no_calibration:
        try:
            dark, gain, cal_root = load_unit_calibration(args.calibration)
        except (FileNotFoundError, ValueError) as e:
            print(f"warning: unit calibration skipped ({e})", file=sys.stderr)
        else:
            print(f"unit calibration {cal_root}  "
                  f"dark_wire/4→14-bit mean={dark.mean(0).round(1)}  "
                  f"(raw-dark)*gain → clamp {RAW14_MAX}")
            rgb = apply_unit_calibration(rgb, dark, gain)
            for c, name in enumerate("RGB"):
                ch = rgb[:, :, c]
                print(f"  {name} cal: mean={ch.mean():.0f}  "
                      f"p01={np.percentile(ch, 1):.0f}  "
                      f"p99={np.percentile(ch, 99):.0f}")

    # Trilinear CCD deskew — before any colour, since it is a registration
    # fault: the three channel records are of different pieces of film.
    spec = str(getattr(args, "ccd_deskew", "auto")).strip().lower()
    if spec in ("off", "none", "0"):
        print("CCD deskew: off")
    else:
        if spec == "auto":
            offs = measure_ccd_line_offsets(rgb)
            print(f"CCD deskew: measured R {offs[0]:+d} / G {offs[1]:+d} / "
                  f"B {offs[2]:+d} scan lines")
        else:
            try:
                parts = [int(p) for p in spec.split(",")]
            except ValueError:
                raise SystemExit(f"--ccd-deskew: bad value {spec!r}")
            if len(parts) != 3:
                raise SystemExit("--ccd-deskew: want R,G,B or auto or off")
            offs = (parts[0], parts[1], parts[2])
            print(f"CCD deskew: R {offs[0]:+d} / G {offs[1]:+d} / "
                  f"B {offs[2]:+d} scan lines")
        rgb = ccd_deskew(rgb, offs)

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    frames_dir = out / "frames"

    # Measure the pitch before asking for the scale. The capture's own frame
    # spacing is the one input that needs neither a sidecar nor the speed
    # anchor — only that 35 mm frames are 38 mm apart — so for the many
    # captures that predate pakon_scan's sidecar it is the whole answer, and
    # resolve_transport_scale no longer has to log "no measured pitch" and
    # leave the geometry alone.
    pitch, pitch_detail = measure_pitch_from_strip(rgb)
    if pitch:
        print(f"frame pitch {pitch:.0f} lines ({pitch_detail})")
    else:
        print(f"frame pitch: not measured ({pitch_detail})")

    ts, ts_src = resolve_transport_scale(
        transport_scale_override=args.transport_scale,
        motor_speed=getattr(args, "motor_speed", None),
        dpi_base=getattr(args, "dpi_base", None),
        line_rate=getattr(args, "line_rate", None),
        capture=args.input,
        measured_pitch_lines=pitch,
    )
    print(f"transport scale {ts:.4f}  ({ts_src})")

    stock = None
    if args.dx:
        p1, p2 = film.parse_dx(args.dx)
        stock = film.lookup(p1, p2)
        print(f"film: {stock.name} ({stock.manufacturer})  "
              f"path={stock.path}  ISO={stock.iso}  SBA={stock.sba_override}  "
              f"(from --dx {args.dx})")
    elif film_path:
        print(f"film: path={film_path} (from --film-path; no DX)")
    elif sba_key_override:
        print(f"film: SBA key override {sba_key_override} (from --sba-key)")
    elif sba_default:
        print("film: explicit --sba-default → ansel-sba-CN-default "
              "(no DX / stock id)")

    # --- product: raw14 ---
    raw_u8 = raw14_preview_u8(rgb)
    write_png(out / "strip_raw14.png", raw_u8, ts)
    print(f"wrote {out / 'strip_raw14.png'}")
    if want_tiff:
        write_tiff16(out / "strip_raw14.tiff", rgb, ts)
        print(f"wrote {out / 'strip_raw14.tiff'}")

    rpd = None
    rpd_u8 = None
    if want_color:
        model = getattr(args, "model", pc.DEFAULT_MODEL)
        print(f"colour-correcting model={model} "
              f"{'(unit EEPROM/registry poly)' if model == 'f135' else args.data_dir}"
              f" …")
        rpd = render_rpd(
            rgb, args.data_dir, offsets=args.offsets, model=model,
        )
        if args.balance:
            print("  pre-Ansel channel balance")
            rpd = roll_balance_rpd(rpd)
        rpd_u8 = rpd_preview_u8(rpd)
        write_png(out / "strip_rpd.png", rpd_u8, ts)
        print(f"wrote {out / 'strip_rpd.png'}")
        if want_tiff:
            write_tiff16(out / "strip_rpd16.tiff", rpd, ts)
            print(f"wrote {out / 'strip_rpd16.tiff'}")

    spans = find_frames(rgb)
    max_frames = int(getattr(args, "max_frames", 0) or 0)
    if max_frames > 0:
        spans = spans[:max_frames]
        print(f"detected frames (using first {len(spans)} "
              f"via --max-frames {max_frames})")
    else:
        print(f"detected {len(spans)} frames")

    srgb = None
    toned12 = None
    cc_srgb = None
    tones: dict[str, np.ndarray] = {}

    if want_color and want_icc and rpd is not None:
        if stock:
            scene = ansel.scene_from_filmstock(
                path=stock.path,
                dx_part1=stock.dx_part1,
                dx_part2=stock.dx_part2,
                iso=stock.iso,
            )
        elif film_path:
            metric = ansel.maps.METRIC_ROM12 if args.model == "f135" else ansel.maps.METRIC_PD12
            scene = ansel.scene_from_filmstock(path=film_path, metric=metric)
        else:
            # --sba-default or --sba-key: CN-Premium / Neg35 scene for
            # Shasta/FUGC maps; SBA dpi comes from override or CN-default key.
            scene = ansel.SceneContext()
        # --sba-default without an explicit key: force CN-default dpi via
        # override so the log reason is unambiguous (not a silent map fallthrough).
        force_key = sba_key_override
        if sba_default and not force_key and not stock and not film_path:
            force_key = "ansel-sba-CN-default"
        engine = ansel.AnselEngine.load(
            args.ansel_root,
            scene=scene,
            sba_key_override=force_key,
        )
        # F-135 negative → positive. Nothing between the polynomial and here
        # inverts (docs/58 §3.5), so the logarithm has to (docs/58 §16).
        # Roll-level film base: it is a property of the stock, not the frame,
        # and the vendor estimates it at roll level too (orderFpo* in the
        # sba dpi / AnalyseRoll).
        if args.model == "f135":
            _c = pc.load_unit_matrix("auto")
            rpd12_pos = f135_rom12_to_rpd12(
                ansel.rpd16_to_rpd12(rpd),
                (_c[9], _c[19], _c[29]),
                engine.sba.fpo,
                engine.setshifts_out,
            )
            rpd = rpd12_to_u16(rpd12_pos)
            # AnsShastaCapabilityImpl::analyze is not ported, so the assembled
            # toneLut has no scene aims to hit. Use the two-anchor stand-in
            # built from the selected shasta dpi.
            engine.shasta_stand_in = True
            print("  F-135 tone: shasta two-anchor stand-in "
                  f"(shadowPercent {engine.shasta.shadow_percent} → black, "
                  f"median → metricGray {engine.shasta.metric_gray})")

        legacy = bool(getattr(args, "legacy_tone", False))
        print(f"  Ansel {'legacy-v1' if legacy else 'two-pass'} on "
              f"{len(spans)} scenes ({rpd.shape[0]} lines) …")
        srgb, toned12 = engine.render_strip(
            rpd, spans, return_toned=True, legacy_tone=legacy,
        )
        write_png(out / "strip_srgb.png", srgb, ts)
        print(f"wrote {out / 'strip_srgb.png'}")

        ansel_prev = rpd12_preview_u8(toned12)
        write_png(out / "strip_ansel_rpd.png", ansel_prev, ts)
        print(f"wrote {out / 'strip_ansel_rpd.png'}")
        if want_tiff:
            write_tiff16(out / "strip_ansel_rpd16.tiff",
                         rpd12_to_u16(toned12), ts)
            print(f"wrote {out / 'strip_ansel_rpd16.tiff'}")

        if want_all:
            # ColorCorrection profile pair on Ansel-toned RPD
            print("  ColorCorrection rpd.pf → srgb.pf …")
            cc_srgb = np.empty_like(srgb)
            chunk = 1500
            for a in range(0, toned12.shape[0], chunk):
                b = min(toned12.shape[0], a + chunk)
                cc_srgb[a:b] = engine.to_cc_srgb(toned12[a:b])
            write_png(out / "strip_cc_srgb.png", cc_srgb, ts)
            print(f"wrote {out / 'strip_cc_srgb.png'}")

        # B&W / tone abstracts
        tone_names: list[str] = []
        if want_all:
            tone_names = list(TONE_PROFILES)
        elif args.tone and args.tone != "none":
            tone_names = [args.tone]
        elif stock and stock.path == film.PATH_BNW:
            tone_names = [args.tone or "warm"]

        for name in tone_names:
            pf = TONE_PROFILES[name]
            print(f"  tone abstract {pf} …")
            tones[name] = apply_abstract_tone(srgb, args.data_dir, pf)
            write_png(out / f"strip_{name}.png", tones[name], ts)
            print(f"wrote {out / f'strip_{name}.png'}")

    if want_frames:
        frames_dir.mkdir(parents=True, exist_ok=True)
        for i, (a, b) in enumerate(spans):
            n = b - a
            prefix = frames_dir / f"{i:02d}"
            write_png(Path(str(prefix) + "_raw14.png"), raw_u8[a:b], ts)
            if want_tiff:
                write_tiff16(Path(str(prefix) + "_raw14.tiff"), rgb[a:b], ts)
            if rpd_u8 is not None:
                write_png(Path(str(prefix) + "_rpd.png"), rpd_u8[a:b], ts)
            if want_tiff and rpd is not None:
                write_tiff16(Path(str(prefix) + "_rpd16.tiff"), rpd[a:b], ts)
            if toned12 is not None:
                write_png(Path(str(prefix) + "_ansel_rpd.png"),
                          rpd12_preview_u8(toned12[a:b]), ts)
                if want_tiff:
                    write_tiff16(Path(str(prefix) + "_ansel_rpd16.tiff"),
                                 rpd12_to_u16(toned12[a:b]), ts)
            if srgb is not None:
                write_png(Path(str(prefix) + "_srgb.png"), srgb[a:b], ts)
            if cc_srgb is not None:
                write_png(Path(str(prefix) + "_cc_srgb.png"), cc_srgb[a:b], ts)
            for name, img in tones.items():
                write_png(Path(str(prefix) + f"_{name}.png"), img[a:b], ts)
            # convenience: primary view
            primary = (srgb if srgb is not None else
                       rpd_u8 if rpd_u8 is not None else raw_u8)
            write_png(Path(str(prefix) + ".png"), primary[a:b], ts)
            print(f"  frame {i:02d}: lines {a}..{b} ({n}) → "
                  f"{int(round(n * ts))}×{PIXELS_PER_LINE}  ({prefix.name}_*)")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    return pc.verify_lut(args.data_dir)


def measure_pitch_lines(capture: Path | str) -> float | None:
    """Measure a capture's frame pitch, streaming, without loading it whole.

    Delegates the estimator to pakon_framing so there is exactly one of them.
    Returns None when the strip has too little structure to measure.
    """
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    import pakon_framing as pf                                   # noqa: PLC0415

    raw = np.memmap(str(capture), dtype="<u2", mode="r")
    n_lines = raw.size // WORDS_PER_LINE
    if n_lines < 3:
        return None
    px = WORDS_PER_LINE // 3
    trace = np.empty(n_lines, dtype=np.float64)
    green = np.empty(n_lines, dtype=np.float64)
    step = 20000
    for i in range(0, n_lines, step):
        j = min(n_lines, i + step)
        blk = np.asarray(raw[i * WORDS_PER_LINE:j * WORDS_PER_LINE]
                         ).reshape(j - i, px, 3).astype(np.float64)
        trace[i:j] = blk.mean(axis=(1, 2))
        green[i:j] = blk[:, :, 1].mean(axis=1)
        del blk
    present = pf.film_present(green, pf.DEFAULT_CLEAR_LEVEL)
    idx = np.flatnonzero(present)
    lo, hi = (int(idx[0]), int(idx[-1]) + 1) if idx.size else (0, n_lines)
    ones = np.zeros(n_lines, dtype=bool)
    ones[lo:hi] = trace[lo:hi] < pf._otsu(trace[lo:hi])
    return pf.estimate_pitch(ones)


def measure_pitch_from_strip(rgb: np.ndarray) -> tuple[float | None, str]:
    """Measure the frame pitch of a strip that is already segmented in memory.

    Same estimator as ``measure_pitch_lines`` (pakon_framing owns it), but on
    the array we are actually about to apply the geometry to, which matters
    for two reasons:

    * ``measure_pitch_lines`` streams the ``.bin`` at a fixed 6000-word
      stride. On a capture taken before the FIFO fix that stride is a lie:
      ``segment_lines`` drops the glitched lines, so line index and film
      travel stop agreeing and the apparent pitch comes out SHORT. On
      ``captures/strip_cal.bin`` the whole-file number is 1349 lines against
      1454 over the clean prefix — a 7 % geometry error, in the direction of
      making the frame too wide.
    * ``--max-lines`` / calibration have already been applied here, so what is
      measured is what is rendered.

    Returns (pitch_lines, detail). The detail carries the per-frame spread,
    because a wide spread is the signature of exactly the dropped-line damage
    above and is the operator's cue to decode a clean prefix instead.
    """
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    import pakon_framing as pf                                   # noqa: PLC0415

    trace = pf.framing_trace(rgb)
    green = pf.green_trace(rgb)
    present = pf.film_present(green, pf.DEFAULT_CLEAR_LEVEL)
    idx = np.flatnonzero(present)
    lo, hi = (int(idx[0]), int(idx[-1]) + 1) if idx.size else (0, trace.size)
    ones = np.zeros(trace.size, dtype=bool)
    if hi > lo:
        ones[lo:hi] = trace[lo:hi] < pf._otsu(trace[lo:hi])
    pitch = pf.estimate_pitch(ones)
    if pitch is None:
        return None, "no measurable frame structure"

    starts = np.array([a for a, b in pf._runs(ones) if b - a >= 200],
                      dtype=np.float64)
    deltas = np.diff(starts)
    # Only whole-pitch gaps: a missed frame doubles, a torn one halves.
    keep = deltas[np.abs(deltas - pitch) <= 0.3 * pitch]
    if keep.size < 2:
        return float(pitch), f"{keep.size} usable frame gap(s)"
    spread = float(keep.std() / keep.mean() * 100.0)
    detail = (f"{keep.size} frame gaps, spread {spread:.1f} %"
              + ("" if spread < 5.0 else
                 " — WIDE: consistent with dropped lines (pre-FIFO-fix "
                 "capture); decode a clean prefix with --max-lines"))
    return float(pitch), detail


def cmd_geometry(args: argparse.Namespace) -> int:
    """Re-derive the transport geometry, and check it against real captures.

    No scanner required. This is the offline proof for the anchor change; see
    the comment block above CCD_ACROSS_PX for the argument it checks.
    """
    print("Anchor")
    print(f"  across            {CCD_ACROSS_PX} px over {FILM_ACROSS_MM:g} mm "
          f"= {ACROSS_PX_PER_MM:.3f} px/mm   [vendor FRAME_SIZES_000, docs/56 §2.7]")
    print(f"  along @ base16    {TARGET_LINES_PER_FRAME} lines over "
          f"{FRAME_IMAGE_MM:g} mm = "
          f"{TARGET_LINES_PER_FRAME / FRAME_IMAGE_MM:.3f} lines/mm   [same table]")
    print(f"  square speed      {SQUARE_MOTOR_SPEED} (DpiBase16 MotorSpeedPlus) "
          f"at line_rate {REF_LINE_RATE}")
    print(f"  triad             calibration/README.json says DpiBase16_35, "
          f"which is what ties the two together")
    ok = abs(ACROSS_PX_PER_MM - TARGET_LINES_PER_FRAME / FRAME_IMAGE_MM) < 1e-6
    print(f"  square?           {'yes' if ok else 'NO — the anchor is inconsistent'}")
    print()
    print("Predicted pitch (38 mm) per hive speed, at our locked line_rate 60")
    for base, sp in sorted(MOTOR_SPEED.items()):
        lpm = along_lines_per_mm(sp)
        print(f"  DpiBase{base:<3} speed {sp:>6}  "
              f"scale {transport_scale(sp):6.4f}  "
              f"{lpm:6.2f} lines/mm  pitch {lpm * FRAME_PITCH_MM:7.0f} lines")
    print()

    if not args.captures:
        print("Pass captures to check the prediction against measured pitch, e.g.")
        print("  python3 tools/pakon_decode.py geometry captures/gold400.bin")
        return 0 if ok else 1

    worst = 0.0
    checked = 0
    print(f"{'capture':<34}{'pitch':>8}{'speed src':>12}{'predicted':>11}"
          f"{'resid':>9}")
    for cap in args.captures:
        p = Path(cap)
        pitch = measure_pitch_lines(p)
        meta = load_capture_sidecar(p) or {}
        sp = meta.get("speed", (meta.get("config") or {}).get("speed"))
        if pitch is None:
            print(f"{p.name:<34}{'—':>8}{'':>12}   no measurable frame structure")
            continue
        if sp:
            pred = along_lines_per_mm(float(sp)) * FRAME_PITCH_MM
            resid = (pitch - pred) / pred * 100.0
            worst = max(worst, abs(resid))
            checked += 1
            print(f"{p.name:<34}{pitch:>8.0f}{int(sp):>12}{pred:>11.0f}"
                  f"{resid:>8.1f}%")
        else:
            print(f"{p.name:<34}{pitch:>8.0f}{'no sidecar':>12}"
                  f"{'—':>11}  implies speed ≈ "
                  f"{implied_motor_speed(pitch):.0f}")
    if checked:
        print()
        print(f"worst residual on a capture with a recorded speed: {worst:.1f} %")
        limit = args.tolerance
        if worst > limit:
            print(f"FAIL — over the {limit:g} % tolerance. The derivation and "
                  f"the film disagree; do not paper over it with a fudge factor.")
            return 1
        print(f"PASS — within {limit:g} %.")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("strip", help="decode an EP 0x86 strip dump")
    s.add_argument("input")
    s.add_argument("output", help="output directory")
    s.add_argument("--all", action="store_true",
                   help="write every product type + frames + 16-bit TIFFs")
    s.add_argument("--ccd-deskew", default="auto", metavar="R,G,B|auto|off",
                   help="trilinear CCD row spacing in scan lines. 'auto' "
                        "measures it from the strip (default); out_test "
                        "measures 8,0,-8. 'off' leaves the channels skewed.")
    s.add_argument("--color", action="store_true",
                   help="stage-2 colour → 12-bit RPD (default F-135 poly; "
                        "see --model)")
    s.add_argument("--model", choices=pc.MODELS, default=pc.DEFAULT_MODEL,
                   help="stage-2 family: f135 = TLB 3×10 poly (this scanner), "
                        "f235 = TLA LUT + 3×4 matrix (default: f135)")
    s.add_argument("--icc", action="store_true",
                   help="Ansel stand-in (SBA/Shasta/FUGC) + Rpd2Pcs→sRGB")
    s.add_argument("--legacy-tone", action="store_true",
                   help="viewing path from tag working-images-v1: ColNeg + "
                        "highlight balance + linked percentile + "
                        "median→metricGray + ICC (skips Preference/Shasta/"
                        "FUGC apply; use until FOS/Shasta aims exist)")
    s.add_argument("--max-frames", type=int, default=0,
                   help="export only the first N detected frames (0=all)")
    s.add_argument("--balance", action="store_true",
                   help="extra pre-Ansel channel balance on stage-2 RPD")
    s.add_argument("--dx", default=None,
                   help="DX film code PART1, PART1-PART2, or composite "
                        "(selects ColNeg/BnW/POSITIVE path + sba.map stock dpi)")
    s.add_argument("--film-path",
                   choices=("ColNeg", "BnW", "POSITIVE", "IMPORTED"),
                   default=None,
                   help="Ansel path without DX (sba.map → CN-default for "
                        "Neg35 unless --sba-key). Required alternative to "
                        "--dx for --icc when stock is unknown.")
    s.add_argument("--sba-key", default=None,
                   help="Force SBA dpi key (e.g. ansel-sba-78-13); bypasses "
                        "sba.map for SBA only. Preference fpo/fpa/… from "
                        "that dpi.")
    s.add_argument("--sba-default", action="store_true",
                   help="Explicit opt-in to ansel-sba-CN-default when DX/"
                        "stock is unknown (required for --icc without "
                        "--dx/--film-path/--sba-key)")
    s.add_argument("--tone", choices=("warm", "cold", "sepia", "none"),
                   default=None,
                   help="B&W toning abstract (with --all: all three tones)")
    s.add_argument("--offsets", choices=("dmin", "template"), default="dmin",
                   help="matrix offset column: dmin (default, for flat-fielded "
                        "strips) or template (verbatim ColNegMat)")
    s.add_argument("--frames", action="store_true",
                   help="split strip into per-type frame files under frames/")
    s.add_argument("--tiff", action="store_true",
                   help="also write 16-bit TIFF (RPD / Ansel-toned RPD)")
    s.add_argument("--calibration", default=str(DEFAULT_CALIBRATION_DIR),
                   help="dir with dark_2000x3.npy + gain_2000x3.npy "
                        f"(default {DEFAULT_CALIBRATION_DIR})")
    s.add_argument("--no-calibration", action="store_true",
                   help="skip committed unit dark/gain tables")
    s.add_argument("--dark",
                   help="legacy: dark-frame capture (with --empty; overrides "
                        "unit calibration)")
    s.add_argument("--empty",
                   help="legacy: open-gate capture (with --dark; overrides "
                        "unit calibration)")
    s.add_argument("--max-lines", type=int, default=0)
    s.add_argument("--transport-scale", type=float, default=None,
                   help="explicit resample factor for square pixels "
                        "(overrides --motor-speed; 1.0 disables). "
                        "Default: derive from speed/line-rate")
    s.add_argument("--motor-speed", type=int, default=None,
                   help="transport register 0xA5 used when the strip was "
                        f"captured (hive: 4→{MOTOR_SPEED[4]}, "
                        f"8→{MOTOR_SPEED[8]}, 16→{MOTOR_SPEED[16]}). "
                        f"gold400.bin was 11467. Default without sidecar: "
                        f"{LEGACY_DEFAULT_MOTOR_SPEED}")
    s.add_argument("--dpi-base", type=int, choices=(4, 8, 16), default=None,
                   help="use hive MotorSpeedPlus for this DpiBase as the "
                        "capture speed (same table as pakon_scan)")
    s.add_argument("--line-rate", type=int, default=None,
                   help="light-board 0x91 line-rate register at capture "
                        f"(default {REF_LINE_RATE} from calibration triad)")
    s.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    s.add_argument("--ansel-root", default=DEFAULT_ANSEL_ROOT,
                   help="anselinstalldir/dataPathItems (shasta/sba/fugc/profile)")
    s.set_defaults(func=cmd_strip)

    g = sub.add_parser("geometry",
                       help="re-derive the transport scale and check it "
                            "against measured frame pitch (no scanner)")
    g.add_argument("captures", nargs="*",
                   help="captures to measure; sidecar speeds are used when present")
    g.add_argument("--tolerance", type=float, default=5.0,
                   help="max %% residual before this fails (default 5)")
    g.set_defaults(func=cmd_geometry)

    v = sub.add_parser("verify-lut", help="check LUT against vendor table")
    v.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    v.set_defaults(func=cmd_verify)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
