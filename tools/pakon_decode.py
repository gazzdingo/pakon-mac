#!/usr/bin/env python3
"""Decode Pakon EP 0x86 strip dumps into coloured frames.

Host-side pipeline (docs/11) — scanner sends raw; we render:

  raw strip → sync/unpack → density LUT + 3×4 matrix → 12-bit RPD
            → (optional) simple roll balance
            → Shasta tone stand-in (white=3000) + ICC Rpd2Pcs → sRGB
            → optional B&W toning abstract profile

DX / film-product selection via --dx (tools/pakon_filmstock.py +
research/film-products.json). Full Kodak Ansel analyseOrder is NOT ported;
Shasta aims from shasta-rpd.dpi. ColorCorrection / anselinstalldir stay
outside the repo (legal) — pass --data-dir / --ansel-dir.

Usage:
  # Continuous full roll (keeps inter-frame gaps). Always written as strip_*.png
  ./pakon_decode.py strip captures/strip_cal.bin out/ --color --icc
  # Also split individual frames (cropped to image area):
  ./pakon_decode.py strip captures/strip_cal.bin out/ --color --icc --frames
  ./pakon_decode.py strip captures/strip_cal.bin out/ --color --icc --dx 78-13
  ./pakon_decode.py verify-lut

Note: strip_*.png is the continuous roll. Sprocket holes / edge printing /
cassette DX barcodes are NOT in these dumps — the CCD readout window is the
24 mm image track only (FPGA offset 62, height 2000). DX is a separate optical
sensor. Widening the window needs a new capture with different PIXEL_OFFSET /
PIXEL_END (experimental).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np

# Allow `import pakon_color` when run from repo root or tools/
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pakon_color as pc  # noqa: E402
import pakon_filmstock as film  # noqa: E402

WORDS_PER_LINE = 6000          # 2000 px × 3 channels — DpiBase16
PIXELS_PER_LINE = 2000
CHANNELS = 3
_FX35 = ("/Users/guy/Downloads/Pakon Update 2/fx35install/"
         "program files/Pakon/F-X35 COM SERVER")
DEFAULT_DATA_DIR = f"{_FX35}/Config/ColorCorrection"
DEFAULT_ANSEL_DIR = f"{_FX35}/anselinstalldir/dataPathItems/profile"


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
    return np.clip(rgb, 0, 16383).astype(np.uint16)


def average_profile(path: str | Path, max_lines: int = 64) -> np.ndarray:
    """Mean (2000, 3) profile from a short calibration capture."""
    words = load_u16(path)
    lines = segment_lines(words)
    rgb = to_rgb14(lines[:max_lines])
    return rgb.astype(np.float64).mean(axis=0)


def apply_flatfield(rgb: np.ndarray, dark: np.ndarray, empty: np.ndarray,
                    scale: float = 16000.0) -> np.ndarray:
    """Per-column (raw - dark) / (empty - dark) * scale, matching the open-gate
    calibration the vendor walks to ~64000 on the wire (→ 16000 in 14-bit).
    """
    num = rgb.astype(np.float64) - dark
    den = np.maximum(empty - dark, 1.0)
    out = num / den * scale
    return np.clip(out, 0, 16383).astype(np.uint16)


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
               offsets: str = "dmin") -> np.ndarray:
    """(n, w, 3) uint14 → (n, w, 3) uint16 scaled from 12-bit RPD.

    Stage-2 kernel (docs/11 §2):

        and 0x3fff → density LUT → 3×4 matrix → clamp 0..4092

    LUT + 3×3 always come from the shipped vendor files. Offset column:

      dmin      (default) — rebuild from measured film-base Dmin of this
                  strip. Needed for already flat-fielded captures like
                  strip_cal.bin; the template −83/−587/−708 assumes raw
                  orange-mask data and crushes G/B to zero on balanced strips.
      template  — verbatim `_ClientColNegMat.txt` column 3.
    """
    lut = load_true_lut(data_dir)
    mat_path = os.path.join(data_dir, "_ClientColNegMat.txt")
    if not os.path.exists(mat_path):
        raise SystemExit(f"missing {mat_path}")
    matrix = pc.load_vendor_matrix(mat_path)
    coeff, template_offset = pc.quantise_matrix(matrix)
    coeff = np.asarray(coeff, dtype=np.float64)
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


# From anselinstalldir/.../shasta/shasta-rpd.dpi — Ansel's RPD code-value aims.
# Probe of Rpd2Pcs→Srgb: code 0→black, ~1618→mid gray, ~3000→white.
SHASTA_WHITE = 3000
SHASTA_GRAY = 1618
SHASTA_MAX = 4095
SHASTA_SHADOW_PCT = 1.0
SHASTA_HIGHLIGHT_PCT = 99.0


def rpd16_to_rpd12(rpd16: np.ndarray) -> np.ndarray:
    """Stored full-scale u16 → 12-bit RPD codes (0..RPD_MAX)."""
    return rpd16.astype(np.float64) * (pc.RPD_MAX / 65535.0)


def rpd12_to_icc_u8(rpd12: np.ndarray) -> np.ndarray:
    """12-bit RPD codes → U8 for ICC mft2 (4096-entry input tables).

    index ≈ u8·4095/255, so u8 = code·255/4095 puts code on the table index.
    profile-Rpd2Srgb.dpi's dataType=U8 / max=255 is the *output* description
    (sRGB); input to Ansel stays 12-bit (shasta maxValue=4095).
    """
    return np.clip(
        np.rint(rpd12.astype(np.float64) * (255.0 / SHASTA_MAX)), 0, 255
    ).astype(np.uint8)


def ansel_shasta_tone_rpd12(rpd12: np.ndarray,
                            balance_channels: bool = True) -> np.ndarray:
    """Stand-in for Ansel Shasta / auto-tone before Rpd2Pcs→sRGB.

    Full AnsOrder::analyzeOrder is not ported. Mirrors shasta-rpd.dpi aims
    (highlight→white=3000). Tone curve is *linked* across RGB (same slope /
    offset) so the stage-2 matrix ratios survive into Rpd2Pcs — independent
    per-channel stretch + ICC double-corrects and neon-casts.

    Optional coarse SBA: scale channels so highlight percentiles match before
    the linked curve (roll/scene balance stand-in).
    """
    x = rpd12.astype(np.float64).copy()
    if balance_channels:
        his = np.array([np.percentile(x[:, :, c], SHASTA_HIGHLIGHT_PCT)
                        for c in range(3)])
        target = float(his.max()) if his.max() > 0 else 1.0
        for c in range(3):
            if his[c] > 0:
                x[:, :, c] *= target / his[c]

    # Linked luminance curve → place highlights at shasta white.
    y = x.mean(axis=2)
    lo = float(np.percentile(y, SHASTA_SHADOW_PCT))
    hi = float(np.percentile(y, SHASTA_HIGHLIGHT_PCT))
    if hi <= lo:
        hi = lo + 1.0
    scale = SHASTA_WHITE / (hi - lo)
    x = (x - lo) * scale

    # Aim channel medians at metricGray=1618 (shasta-rpd.dpi). Without this,
    # stage-2 RPD is B-weak and Rpd2Pcs renders everything yellow.
    for c in range(3):
        med = float(np.median(x[:, :, c]))
        if med > 1.0:
            x[:, :, c] *= SHASTA_GRAY / med
    return np.clip(x, 0, SHASTA_MAX)


def roll_balance_rpd(rpd16: np.ndarray) -> np.ndarray:
    """Simple roll-level channel balance on stored RPD.

    Not Kodak Ansel (docs/11 §5 — AnalyseRoll is two-pass and data-driven).
    Scales each channel so its 99th percentile matches — coarse SBA.
    """
    out = rpd16.astype(np.float64)
    his = np.array([np.percentile(out[:, :, c], 99.0) for c in range(3)])
    target = float(his.max()) if his.max() > 0 else 1.0
    for c in range(3):
        if his[c] > 0:
            out[:, :, c] *= target / his[c]
    return np.clip(out, 0, 65535).astype(np.uint16)


def _contiguous_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Return [start, end) runs where mask is True."""
    if not mask.any():
        return []
    idx = np.flatnonzero(mask)
    runs = []
    a = int(idx[0])
    prev = a
    for j in range(1, len(idx)):
        cur = int(idx[j])
        if cur != prev + 1:
            runs.append((a, prev + 1))
            a = cur
        prev = cur
    runs.append((a, prev + 1))
    return runs


def apply_icc_rpd_to_srgb_chunked(rgb16: np.ndarray, ansel_dir: str,
                                  data_dir: str,
                                  abstract: str | None = None,
                                  spans: list[tuple[int, int]] | None = None,
                                  chunk_lines: int = 1500) -> np.ndarray:
    """Apply tone+ICC per scene (Pakon: per-scene transform after AnalyseRoll).

    Prefer `spans` from find_frames — strip-wide Shasta percentiles mix
    indoor/outdoor scenes and wreck the code-value aims.
    """
    n = rgb16.shape[0]
    out = np.zeros((n, rgb16.shape[1], 3), dtype=np.uint8)
    covered = np.zeros(n, dtype=bool)

    if spans:
        regions = list(spans)
    else:
        regions = [(a, min(n, a + chunk_lines))
                   for a in range(0, n, chunk_lines)]

    for i, (a, b) in enumerate(regions):
        if b <= a:
            continue
        out[a:b] = apply_icc_rpd_to_srgb(
            rgb16[a:b], ansel_dir, data_dir, abstract, quiet=(i > 0))
        covered[a:b] = True

    for a, b in _contiguous_runs(~covered):
        out[a:b] = apply_icc_rpd_to_srgb(
            rgb16[a:b], ansel_dir, data_dir, abstract, quiet=True)
    return out


def apply_icc_rpd_to_srgb(rgb16: np.ndarray, ansel_dir: str,
                          data_dir: str,
                          abstract: str | None = None,
                          quiet: bool = False) -> np.ndarray:
    """Stage-2 RPD → Ansel tone stand-in → Rpd2Pcs→sRGB (docs/11 §0, §5).

    Pakon order: LUT+matrix → (roll) Ansel SBA/tone including RPD→PCS→sRGB.
    Shasta aims (shasta-rpd.dpi): white=3000, metricGray=1618, maxValue=4095.
    ICC probe: those codes are brightness-like (0→black, 3000→white), so raw
    stage-2 means ~200 crush to black if fed to the profile without tone map.

    Preferred profiles (profile-Rpd2Srgb.dpi):
        Rpd2Pcs_HR200_QS_v5s10.pf → Srgb_v2.pf (perceptual)
    Fallback: ColorCorrection rpd.pf → srgb.pf
    """
    from PIL import Image, ImageCms

    ansel = Path(ansel_dir)
    data = Path(data_dir)
    p_rpd2pcs = ansel / "Rpd2Pcs_HR200_QS_v5s10.pf"
    p_srgb_v2 = ansel / "Srgb_v2.pf"
    if p_rpd2pcs.is_file() and p_srgb_v2.is_file():
        src_p, dst_p = p_rpd2pcs, p_srgb_v2
        if not quiet:
            print(f"  ICC: {p_rpd2pcs.name} → {p_srgb_v2.name} (Ansel)")
    else:
        src_p = data / "rpd.pf"
        dst_p = data / "srgb.pf"
        if not src_p.is_file() or not dst_p.is_file():
            raise SystemExit(f"no ICC profiles in {ansel_dir} or {data_dir}")
        if not quiet:
            print(f"  ICC: {src_p.name} → {dst_p.name} (ColorCorrection fallback)")

    rpd12 = rpd16_to_rpd12(rgb16)
    toned = ansel_shasta_tone_rpd12(rpd12)
    if not quiet:
        print(f"  Shasta stand-in: p{SHASTA_SHADOW_PCT:g}..p{SHASTA_HIGHLIGHT_PCT:g} "
              f"→ 0..{SHASTA_WHITE}  (mean RPD {toned.mean(axis=(0, 1)).round(0)})")
    u8 = rpd12_to_icc_u8(toned)

    src = ImageCms.getOpenProfile(str(src_p))
    dst = ImageCms.getOpenProfile(str(dst_p))
    intent = ImageCms.Intent.PERCEPTUAL

    im = Image.fromarray(u8, mode="RGB")
    xform = ImageCms.buildTransformFromOpenProfiles(
        src, dst, "RGB", "RGB", renderingIntent=intent)
    im = ImageCms.applyTransform(im, xform)

    if abstract:
        abs_path = data / abstract
        if not abs_path.is_file():
            raise SystemExit(f"missing abstract profile {abs_path}")
        if not quiet:
            print(f"  ICC abstract: {abstract}")
        # Abstract Lab→Lab: convert sRGB→Lab, apply, Lab→sRGB
        lab_p = ImageCms.createProfile("LAB")
        srgb_p = ImageCms.createProfile("sRGB")
        abs_p = ImageCms.getOpenProfile(str(abs_path))
        to_lab = ImageCms.buildTransformFromOpenProfiles(
            srgb_p, lab_p, "RGB", "LAB", renderingIntent=intent)
        lab = ImageCms.applyTransform(im, to_lab)
        # Evidence profiles: apply abstract as input=output Lab
        try:
            ax = ImageCms.buildTransformFromOpenProfiles(
                abs_p, abs_p, "LAB", "LAB", renderingIntent=intent)
            lab = ImageCms.applyTransform(lab, ax)
        except Exception as e:
            if not quiet:
                print(f"  warning: abstract apply failed ({e}); skipping toning")
        back = ImageCms.buildTransformFromOpenProfiles(
            lab_p, srgb_p, "LAB", "RGB", renderingIntent=intent)
        im = ImageCms.applyTransform(lab, back)

    return np.asarray(im, dtype=np.uint8)


def toning_profile_for_path(path: str, tone: str | None) -> str | None:
    """Pick a ColorCorrection abstract .pf for B&W toning."""
    if path != film.PATH_BNW:
        if tone in (None, "none"):
            return None
    tone = tone or "warm"
    return {
        "cold": "cold_bw.pf",
        "warm": "warm_bw_ld0_1_4-5.pf",
        "sepia": "sepia_ld0_9_22.pf",
        "none": None,
    }.get(tone, "warm_bw_ld0_1_4-5.pf")


# --------------------------------------------------------------------------
# frame split (heuristic; vendor uses DetectFilm_G / DetectWhite_G)
# --------------------------------------------------------------------------

def find_frames(rgb14: np.ndarray, min_gap: int = 80,
                min_frame: int = 400) -> list[tuple[int, int]]:
    """Split a continuous strip into frames by detecting bright inter-frame
    gaps (open gate / film edge) on the green channel.
    """
    # Mean green along each line; high = little density = gap / base
    g = rgb14[:, :, 1].astype(np.float64).mean(axis=1)
    # Adaptive threshold: gaps sit near the top of the distribution
    thr = np.percentile(g, 85)
    is_gap = g >= thr
    # Morphological close of small holes
    from numpy.lib.stride_tricks import sliding_window_view
    if is_gap.size >= 5:
        win = sliding_window_view(is_gap.astype(np.uint8), 5).mean(axis=1)
        is_gap = np.concatenate([[is_gap[0]], win >= 0.6, [is_gap[-1]]])

    frames = []
    in_frame = False
    start = 0
    for i, gap in enumerate(is_gap):
        if not in_frame and not gap:
            in_frame = True
            start = i
        elif in_frame and gap:
            if i - start >= min_frame:
                frames.append((start, i))
            in_frame = False
    if in_frame and len(is_gap) - start >= min_frame:
        frames.append((start, len(is_gap)))

    # Merge frames separated by tiny gaps
    merged = []
    for a, b in frames:
        if merged and a - merged[-1][1] < min_gap:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return merged


# --------------------------------------------------------------------------
# I/O
# --------------------------------------------------------------------------

# DpiBase16 full frame is 3000 transport samples × 2000 CCD (docs/30).
# strip_cal.bin only gets ~1380 lines/frame — motor was ~2.17× too fast
# relative to line rate — so the transport axis is spatially compressed.
TARGET_LINES_PER_FRAME = 3000
DEFAULT_TRANSPORT_SCALE = TARGET_LINES_PER_FRAME / 1380.0  # ≈ 2.174


def unsquash_transport(rgb: np.ndarray, scale: float = DEFAULT_TRANSPORT_SCALE) -> np.ndarray:
    """Resample the line (transport) axis so pixels are square.

    `rgb` is (n_lines, ccd, 3). After this, a full frame is ~3000×2000 and
    aspect 3:2. Without it the picture looks squashed along the film advance.
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


def to_frame_image(rgb: np.ndarray,
                   transport_scale: float = DEFAULT_TRANSPORT_SCALE) -> np.ndarray:
    """(n_lines, ccd, 3) → display image, square pixels, transport left→right.

    1. Resample transport axis (fix squashed pixels from fast motor)
    2. rot90 CCW so the strip reads left→right
    """
    rgb = unsquash_transport(rgb, transport_scale)
    return np.ascontiguousarray(np.rot90(rgb, k=1))


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
        print(f"flat-field from {args.dark} / {args.empty}")
        rgb = apply_flatfield(rgb, dark, empty)

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    ts = args.transport_scale
    print(f"transport scale {ts:.4f} "
          f"({ts:.3f}× along film → square pixels at DpiBase16)")

    stock = None
    abstract = None
    if args.dx:
        p1, p2 = film.parse_dx(args.dx)
        stock = film.lookup(p1, p2)
        print(f"film: {stock.name} ({stock.manufacturer})  "
              f"path={stock.path}  ISO={stock.iso}  SBA={stock.sba_override}")
        abstract = toning_profile_for_path(stock.path, args.tone)
    elif args.tone and args.tone != "none":
        abstract = toning_profile_for_path(film.PATH_BNW, args.tone)

    if args.color:
        print(f"colour-correcting via {args.data_dir} …")
        rpd = render_rpd(rgb, args.data_dir, offsets=args.offsets)
        if args.balance:
            print("  roll balance (stand-in for Ansel AnalyseRoll)")
            rpd = roll_balance_rpd(rpd)
        preview = rpd_preview_u8(rpd)
        write_png(out / "strip_rpd.png", preview, ts)
        if args.tiff:
            write_tiff16(out / "strip_rpd.tiff", rpd, ts)
        print(f"wrote {out / 'strip_rpd.png'}")
        work = rpd
        preview_for_frames = preview

        if args.icc:
            # Full continuous roll; tone+ICC per detected frame (Pakon
            # per-scene transform), gaps handled locally.
            spans = find_frames(rgb)
            print(f"  ICC on full strip ({rpd.shape[0]} lines, "
                  f"{len(spans)} scenes) …")
            srgb_strip = apply_icc_rpd_to_srgb_chunked(
                rpd, args.ansel_dir, args.data_dir, abstract, spans=spans)
            write_png(out / "strip_srgb.png", srgb_strip, ts)
            print(f"wrote {out / 'strip_srgb.png'}  "
                  f"(continuous roll — not frame-cropped)")
    else:
        preview = (rgb.astype(np.uint32) * 255 // 16383).astype(np.uint8)
        write_png(out / "strip_raw.png", preview, ts)
        print(f"wrote {out / 'strip_raw.png'}  "
              f"(continuous roll — not frame-cropped)")
        work = rgb
        preview_for_frames = preview

    if args.frames:
        spans = find_frames(rgb)
        print(f"detected {len(spans)} frames")
        for i, (a, b) in enumerate(spans):
            n = b - a
            if args.color and args.icc:
                srgb = apply_icc_rpd_to_srgb(
                    work[a:b], args.ansel_dir, args.data_dir, abstract)
                write_png(out / f"frame_{i:02d}.png", srgb, ts)
            else:
                write_png(out / f"frame_{i:02d}.png",
                          preview_for_frames[a:b], ts)
            if args.color and args.tiff:
                write_tiff16(out / f"frame_{i:02d}.tiff", work[a:b], ts)
            print(f"  frame {i:02d}: lines {a}..{b} ({n}) → "
                  f"{int(round(n * ts))}×{PIXELS_PER_LINE} after unsquash")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    return pc.verify_lut(args.data_dir)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("strip", help="decode an EP 0x86 strip dump")
    s.add_argument("input")
    s.add_argument("output", help="output directory")
    s.add_argument("--color", action="store_true",
                   help="apply density LUT + 3×4 matrix → 12-bit RPD")
    s.add_argument("--icc", action="store_true",
                   help="Rpd2Pcs→sRGB ICC (Ansel output profiles)")
    s.add_argument("--balance", action="store_true",
                   help="simple roll channel balance before ICC "
                        "(stand-in for Ansel AnalyseRoll)")
    s.add_argument("--dx", default=None,
                   help="DX film code PART1, PART1-PART2, or composite "
                        "(selects ColNeg/BnW/POSITIVE path)")
    s.add_argument("--tone", choices=("warm", "cold", "sepia", "none"),
                   default=None,
                   help="B&W toning abstract profile (default warm if path=BnW)")
    s.add_argument("--offsets", choices=("dmin", "template"), default="dmin",
                   help="matrix offset column: dmin (default, for flat-fielded "
                        "strips) or template (verbatim ColNegMat)")
    s.add_argument("--frames", action="store_true",
                   help="split strip into frames")
    s.add_argument("--tiff", action="store_true",
                   help="also write 16-bit TIFF")
    s.add_argument("--dark", help="dark-frame capture for flat-field")
    s.add_argument("--empty", help="open-gate capture for flat-field")
    s.add_argument("--max-lines", type=int, default=0)
    s.add_argument("--transport-scale", type=float, default=DEFAULT_TRANSPORT_SCALE,
                   help="resample transport axis for square pixels "
                        f"(default {DEFAULT_TRANSPORT_SCALE:.3f} = 3000/1380; "
                        "use 1.0 to disable)")
    s.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    s.add_argument("--ansel-dir", default=DEFAULT_ANSEL_DIR,
                   help="anselinstalldir/.../profile with Rpd2Pcs + Srgb_v2")
    s.set_defaults(func=cmd_strip)

    v = sub.add_parser("verify-lut", help="check LUT against vendor table")
    v.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    v.set_defaults(func=cmd_verify)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
