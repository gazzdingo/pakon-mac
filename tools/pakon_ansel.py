#!/usr/bin/env python3
"""Byte-faithful Ansel colour from shipped Pakon data files.

Pakon (docs/11 §5, PakonIMAu strings): stage-2 RPD stays **I16** through
Shasta/SBA (`Only I16 data type is supported by ImaShastaOp`), then
Rpd2Pcs→Srgb. Shasta exports tone LUTs; we do not yet decode pcode binaries,
but the install ships the exact 12-bit tables Ansel uses for metric tone:

  common/common-sraFwdLut-metric-default.lut   — SRA forward (RPD/RIM)
      Probed: SRA[200]≈1512 ≈ sba neutralBalancePoint 1550 / metricGray 1618.
      This is the missing step that lifts stage-2 codes (~200) into the ICC
      domain without inventing a percentile stretch.
  fugc/fugc-generic*.lut                       — FUGC 1D (fugc-lutMap)
  sba/SbaDPI/sba-CN-default.dpi                — neutralBalancePoint, …
  shasta/shasta-rpd.dpi                        — white / metricGray aims
  profile/Rpd2Pcs_HR200_QS_v5s10.pf            — mft2, n_in=4096 (12-bit)
  profile/Srgb_v2.pf

Pipeline implemented here (I16 codes 0..4095 throughout until ICC):

  RPD12 → channel balance (SBA) → SRA fwd lut → FUGC → median→1550
        → Rpd2Pcs→Srgb (U8 encode = code·255/4095 for 4096-entry tables)

DPI / LUT selection uses the vendor ``.map`` files (see pakon_ansel_maps).
Full AnsOrder / SbaDecodePcode is still NOT ported.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

import pakon_ansel_maps as maps
import pakon_sba_pcode as sba_pcode

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
    white: float = 3000.0
    metric_gray: float = 1618.0
    max_value: float = 4095.0
    shadow_percent: float = 1.0
    highlight_percent: float = 99.0
    code_values_per_button: float = 75.0

    @classmethod
    def load(cls, path: Path) -> "ShastaParams":
        d = parse_dpi(path)
        return cls(
            white=float(d.get("white", 3000)),
            metric_gray=float(d.get("metricGray", 1618)),
            max_value=float(d.get("maxValue", 4095)),
            shadow_percent=float(d.get("shadowPercent", 1.0)),
            highlight_percent=float(d.get("highlightPercent", 99.0)),
            code_values_per_button=float(d.get("codeValuesPerButton", 75)),
        )


@dataclass
class SbaParams:
    neutral_balance_point: float = 1550.0
    min_dmin: tuple[float, float, float] = (180.0, 550.0, 700.0)
    neu: tuple[float, float, float] = (975.0, 975.0, 975.0)
    neo: tuple[float, float, float] = (1010.0, 1010.0, 1010.0)
    fpo: tuple[float, float, float] = (879.0, 1250.0, 1386.0)
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
        return cls(
            neutral_balance_point=float(d.get("neutralBalancePoint", 1550)),
            min_dmin=(md[0], md[1], md[2]),
            neu=(neu[0], neu[1], neu[2]),
            neo=(neo[0], neo[1], neo[2]),
            fpo=(fpo[0], fpo[1], fpo[2]),
            key=d.get("key", path.stem),
            pcode_name=d.get("pcode", "pcode-dls_1.7"),
            sfs_table_name=d.get("sfsTable", "sfsTable35"),
            dpi_path=path,
        )


def load_sra_fwd_lut(path: Path) -> np.ndarray:
    """Load common-sraFwdLut-metric-*.lut → (4096,) int table.

    File is `SRA_NUM_FORWARDLUT = 4096` then one integer per line (often 4095
    values in practice). Index = RPD code. Verified: [200]→1512, [1550]→3021.
    """
    rows: list[int] = []
    for ln in path.read_text(errors="replace").splitlines():
        s = ln.strip()
        if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
            rows.append(int(s))
    table = np.zeros(4096, dtype=np.int32)
    n = min(len(rows), 4096)
    table[:n] = rows[:n]
    if n and n < 4096:
        table[n:] = rows[n - 1]
    return table


def load_fugc_lut(path: Path) -> np.ndarray:
    """Load fugc-generic*.lut → (4096, 3) table (identity fill)."""
    table = np.arange(4096, dtype=np.int32)[:, None].repeat(3, axis=1)
    for raw in path.read_text(errors="replace").splitlines():
        parts = raw.split()
        if len(parts) < 4 or not parts[0].lstrip("-").isdigit():
            continue
        i, r, g, b = (int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))
        if 0 <= i < 4096:
            table[i] = (r, g, b)
    return table


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
    """Coarse SBA: equalise channels (pcode not decoded yet)."""
    x = rpd12.astype(np.float64)
    if mode == "highlight":
        refs = np.array([np.percentile(x[:, :, c], 99.0) for c in range(3)])
    else:
        # median of pixels above the 5th percentile (skip empty gate)
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


def aim_medians(rpd12: np.ndarray, aim: float) -> np.ndarray:
    x = rpd12.astype(np.float64)
    for c in range(3):
        med = float(np.median(x[:, :, c]))
        if med > 1.0:
            x[:, :, c] *= aim / med
    return np.clip(x, 0, SHASTA_MAX)


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
    sfs_rows: list[tuple[int, int, int, int]] = field(default_factory=list)
    _icc_cache: object = field(default=None, repr=False)

    @classmethod
    def load(cls, ansel_root: Path | str = DEFAULT_ANSEL_ROOT,
             iso: int | None = None,
             scene: SceneContext | None = None) -> "AnselEngine":
        root = Path(ansel_root)
        if scene is None:
            scene = SceneContext(iso=iso)
        elif iso is not None and scene.iso is None:
            scene = replace(scene, iso=iso)

        sel = maps.select_ansel_files(root, scene)
        shasta = ShastaParams.load(sel.shasta_dpi)
        sba = SbaParams.load(sel.sba_dpi)
        sra = load_sra_fwd_lut(sel.sra_lut)
        fugc = load_fugc_lut(sel.fugc_lut)

        pcode = None
        sfs_rows: list[tuple[int, int, int, int]] = []
        pcode_path = root / "sba" / "Pcode" / sba.pcode_name
        sfs_path = root / "sba" / "Sfs" / sba.sfs_table_name
        if pcode_path.is_file():
            pcode = sba_pcode.load_pcode(pcode_path)
        if sfs_path.is_file():
            sfs_rows = sba_pcode.parse_sfs_table(sfs_path)

        print(
            f"  Ansel map: path={scene.ansel_path} src={scene.source_type} "
            f"DX={scene.product_code}"
            f"{'-' + str(scene.gen_code) if scene.gen_code is not None else ''} "
            f"ISO={scene.iso} metric={scene.metric}"
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
        if pcode is not None:
            print(
                f"  SBA pcode: {pcode.name} decoded "
                f"(program_words={len(pcode.program)}, "
                f"sfs={sba.sfs_table_name} rows={len(sfs_rows)}; "
                f"analyze/getShifts NOT ported — median balance still used)"
            )
        else:
            print(f"  SBA pcode: missing {pcode_path}")
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
            sfs_rows=sfs_rows,
        )

    def render_scene(self, rpd12: np.ndarray,
                     roll_scale: np.ndarray | None = None) -> np.ndarray:
        """I16 RPD12 → toned I16 using vendor SRA + FUGC tables."""
        x = rpd12.astype(np.float64)
        if roll_scale is not None:
            x = x * roll_scale.reshape(1, 1, 3)
        x = channel_balance(x, mode="median")
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
                     return_toned: bool = False):
        rpd12_full = rpd16_to_rpd12(rpd16)
        scenes = [rpd12_full[a:b] for a, b in spans if b > a]
        roll_scale = self.analyze_roll_scales(scenes) if scenes else None
        if not quiet and roll_scale is not None:
            print(f"  Ansel roll channel scales = {roll_scale.round(3)}")

        n = rpd16.shape[0]
        out = np.zeros((n, rpd16.shape[1], 3), dtype=np.uint8)
        toned_full = np.zeros((n, rpd16.shape[1], 3), dtype=np.float64)
        covered = np.zeros(n, dtype=bool)

        def _run(a: int, b: int, scale):
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
                    max_gap: int = 350) -> list[tuple[int, int]]:
    """Frame split: only *short* bright/flat runs count as inter-frame gaps."""
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
    return final
