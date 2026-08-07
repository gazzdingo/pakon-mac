"""Pakon AnsKeySelector-style .map selection for Ansel dataPathItems.

Mirrors AnsInitializeMapping::selectDpi: walk mapping rules top-to-bottom,
first match wins. Tokens: ``any`` / ``X``, exact ints/strings, or open
ranges like ``(0,0.7)``.

Also parses ``fugc-lutMap.map`` (``film =`` / ``contrast =`` lines).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Scene-context enums from color.map / vendor headers
METRIC_UNKNOWN = 0
METRIC_PD12 = 1   # RPD
METRIC_RIM12 = 2
METRIC_ROM12 = 3

# Source types used in sba.map comments
SRC_NEGATIVE_35 = 1
SRC_NEGATIVE_APS = 2
SRC_NEGATIVE_120 = 9
SRC_NEGATIVE_110 = 11

# Filmstock path string → Ansel path name used in .map files
PATH_TO_ANSEL = {
    "ColNeg": "CN-Premium",
    "BnW": "CN-Premium",       # chromagenic B&W still uses CN SBA tables
    "POSITIVE": "CN-Premium",  # no dedicated slide path in these maps
    "IMPORTED": "CN-Premium",
}


@dataclass
class SceneContext:
    """Values AnsKeySelector matches against."""
    ansel_path: str = "CN-Premium"
    scanner_name: str = ""
    source_type: int = SRC_NEGATIVE_35
    product_code: int | None = None   # DX part1
    gen_code: int | None = None       # DX part2
    iso: int | None = None
    metric: int = METRIC_PD12
    tone_strategy: int | None = None  # 1 = low (shasta-*-low)
    tone_aggr: int | None = None
    image_size: float | None = None   # relative; (0,0.7) = small
    cap_name: str = "profileRpd2Srgb"

    def as_dict(self) -> dict[str, Any]:
        return {
            "_AnselPath_": self.ansel_path,
            "scannerName": self.scanner_name or None,
            "sourceType": self.source_type,
            "productCode": self.product_code,
            "genCode": self.gen_code,
            "metric": self.metric,
            "_AnselToneStrategy_": self.tone_strategy,
            "_AnselToneAggrSetting_": self.tone_aggr,
            "_AnselImageSize_": self.image_size,
            "_AnselCapName_": self.cap_name,
            "iso": self.iso,
        }


@dataclass
class MapRule:
    fields: list[str]
    result: str


@dataclass
class KeySelectorMap:
    """Parsed AnsKeySelector .map (header params + ordered rules)."""
    path: Path
    param_names: list[str] = field(default_factory=list)
    rules: list[MapRule] = field(default_factory=list)

    def select(self, ctx: dict[str, Any]) -> str | None:
        for rule in self.rules:
            if len(rule.fields) != len(self.param_names):
                continue
            if all(
                _token_matches(tok, ctx.get(name))
                for tok, name in zip(rule.fields, self.param_names)
            ):
                return rule.result
        return None


_PARAM_HEADER = re.compile(
    r"^((?:_?[A-Za-z][A-Za-z0-9_]*_?(?:\s+[ci]\d+|\s+float)?\s*)+)$"
)
_NAME_TYPE = re.compile(r"(_?[A-Za-z][A-Za-z0-9_]*_?)\s+(?:[ci]\d+|float)")


def _strip_comment(line: str) -> str:
    return line.split("#", 1)[0].strip()


def _parse_param_header(line: str) -> list[str] | None:
    """Parse ``_AnselPath_ c11 scannerName c64 …`` → names."""
    s = _strip_comment(line)
    if not s or "=" in s:
        return None
    names = _NAME_TYPE.findall(s)
    if len(names) >= 2:
        return names
    # bare names without types (rare)
    parts = s.split()
    if parts and all(re.match(r"^_?[A-Za-z]", p) for p in parts):
        return parts
    return None


def _is_result_token(tok: str) -> bool:
    return tok.startswith("ansel-") or tok.endswith(".dpi") or tok.endswith(".lut")


def parse_key_selector_map(path: Path) -> KeySelectorMap:
    text = path.read_text(errors="replace")
    lines = text.splitlines()
    in_mapping = False
    param_names: list[str] = []
    rules: list[MapRule] = []

    for raw in lines:
        line = _strip_comment(raw)
        if not line:
            continue
        if re.match(r"^mapping\s*=", line, re.I):
            in_mapping = True
            # rest of line after =
            rest = line.split("=", 1)[1].strip()
            if rest:
                hdr = _parse_param_header(rest)
                if hdr:
                    param_names = hdr
            continue
        if not in_mapping:
            continue
        if line.startswith("key") or line.startswith("version"):
            continue

        hdr = _parse_param_header(line)
        if hdr and not any(_is_result_token(p) for p in line.split()):
            param_names = hdr
            continue

        parts = line.split()
        if len(parts) < 2 or not param_names:
            continue
        # last token is result key / filename
        result = parts[-1]
        fields = parts[:-1]
        if len(fields) != len(param_names):
            # tolerate trailing junk / incomplete commented styles
            continue
        if not (_is_result_token(result) or result.endswith(".dpi")
                or result.endswith(".lut") or result.startswith("profile-")):
            continue
        rules.append(MapRule(fields=fields, result=result))

    return KeySelectorMap(path=path, param_names=param_names, rules=rules)


def _token_matches(token: str, value: Any) -> bool:
    t = token.strip()
    if t.lower() in ("any", "x"):
        return True
    if value is None:
        return False
    # open range (lo,hi) — exclusive ends per Pakon smallImage rules
    m = re.fullmatch(r"\(\s*([+-]?\d*\.?\d+)\s*,\s*([+-]?\d*\.?\d+)\s*\)", t)
    if m:
        try:
            v = float(value)
        except (TypeError, ValueError):
            return False
        lo, hi = float(m.group(1)), float(m.group(2))
        return lo < v < hi
    # numeric
    try:
        if isinstance(value, (int, float)) or (
            isinstance(value, str) and re.fullmatch(r"[+-]?\d+", value)
        ):
            return float(t) == float(value)
    except ValueError:
        pass
    return t == str(value)


@dataclass
class FugcLutMap:
    path: Path
    # (dx1|None, dx2|None, iso|None, contrast)
    film_rules: list[tuple[int | None, int | None, int | None, float]]
    contrast_to_lut: dict[float, str]

    def select_lut_name(
        self,
        product_code: int | None,
        gen_code: int | None,
        iso: int | None,
    ) -> tuple[float, str]:
        contrast = 2.25
        for dx1, dx2, rule_iso, c in self.film_rules:
            if dx1 is not None and product_code != dx1:
                continue
            if dx2 is not None and gen_code != dx2:
                continue
            if rule_iso is not None and iso != rule_iso:
                continue
            contrast = c
            break
        name = self.contrast_to_lut.get(contrast)
        if name is None:
            # nearest contrast key
            keys = sorted(self.contrast_to_lut)
            if not keys:
                return contrast, "fugc-generic0225.lut"
            best = min(keys, key=lambda k: abs(k - contrast))
            name = self.contrast_to_lut[best]
            contrast = best
        return contrast, name


def parse_fugc_lut_map(path: Path) -> FugcLutMap:
    film_rules: list[tuple[int | None, int | None, int | None, float]] = []
    contrast_to_lut: dict[float, str] = {}
    for raw in path.read_text(errors="replace").splitlines():
        line = _strip_comment(raw)
        if not line:
            continue
        if line.lower().startswith("film"):
            # film = Dx1 Dx2 Iso Contrast
            m = re.match(
                r"film\s*=\s*(\S+)\s+(\S+)\s+(\S+)\s+(\S+)",
                line, re.I,
            )
            if not m:
                continue

            def _opt_int(s: str) -> int | None:
                if s.upper() == "X":
                    return None
                return int(float(s))

            film_rules.append((
                _opt_int(m.group(1)),
                _opt_int(m.group(2)),
                _opt_int(m.group(3)),
                float(m.group(4)),
            ))
        elif line.lower().startswith("contrast"):
            m = re.match(
                r"contrast\s*=\s*(\S+)\s+(\S+)",
                line, re.I,
            )
            if m:
                contrast_to_lut[float(m.group(1))] = m.group(2)
    return FugcLutMap(path=path, film_rules=film_rules,
                      contrast_to_lut=contrast_to_lut)


def index_dpi_keys(search_roots: list[Path]) -> dict[str, Path]:
    """Map ``key = …`` values inside .dpi files → file path."""
    out: dict[str, Path] = {}
    for root in search_roots:
        if not root.is_dir():
            continue
        for p in root.rglob("*.dpi"):
            try:
                for raw in p.read_text(errors="replace").splitlines():
                    line = _strip_comment(raw)
                    if not line.lower().startswith("key"):
                        continue
                    if "=" not in line:
                        continue
                    key = line.split("=", 1)[1].strip()
                    if key and key not in out:
                        out[key] = p
                    break
            except OSError:
                continue
    return out


def resolve_dpi_key(key: str, index: dict[str, Path],
                    fallback_dir: Path | None = None) -> Path | None:
    if key in index:
        return index[key]
    # result may already be a filename
    if key.endswith(".dpi") and fallback_dir is not None:
        p = fallback_dir / key
        if p.is_file():
            return p
        for p in fallback_dir.rglob(key):
            return p
    return None


def sra_fwd_lut_name(metric: int) -> str:
    """Pick common-sraFwdLut by metric (no .map; from color.map notes)."""
    if metric == METRIC_ROM12:
        return "common-sraFwdLut-metric-rom12.lut"
    if metric == METRIC_RIM12:
        return "common-sraFwdLut-metric-rim12.lut"
    # PD12 / unknown → default (identical to rim12 in this install)
    return "common-sraFwdLut-metric-default.lut"


def scene_from_filmstock(
    path: str = "ColNeg",
    dx_part1: int | None = None,
    dx_part2: int | None = None,
    iso: int | None = None,
    source_type: int = SRC_NEGATIVE_35,
    metric: int = METRIC_PD12,
    ansel_path: str | None = None,
) -> SceneContext:
    return SceneContext(
        ansel_path=ansel_path or PATH_TO_ANSEL.get(path, "CN-Premium"),
        source_type=source_type,
        product_code=dx_part1,
        gen_code=dx_part2,
        iso=iso,
        metric=metric,
    )


@dataclass
class SelectedAnselFiles:
    sba_dpi: Path
    shasta_dpi: Path
    fugc_lut: Path
    sra_lut: Path
    profile_dpi: Path | None
    sba_key: str
    shasta_key: str
    fugc_contrast: float
    fugc_name: str
    sra_name: str
    profile_key: str


def select_ansel_files(
    root: Path,
    ctx: SceneContext,
) -> SelectedAnselFiles:
    """Run vendor maps and resolve dpi/lut paths under dataPathItems."""
    sba_map = parse_key_selector_map(root / "sba" / "SbaDPI" / "sba.map")
    shasta_map = parse_key_selector_map(root / "shasta" / "shasta.map")
    profile_map = parse_key_selector_map(root / "profile" / "profile.map")
    fugc_map = parse_fugc_lut_map(root / "fugc" / "fugc-lutMap.map")

    index = index_dpi_keys([
        root / "sba" / "SbaDPI",
        root / "shasta",
        root / "profile",
        root / "color",
        root / "contrast",
        root / "common",
    ])

    cdict = ctx.as_dict()
    sba_key = sba_map.select(cdict) or "ansel-sba-CN-default"
    shasta_key = shasta_map.select(cdict) or "ansel-shasta-rpd"
    profile_key = profile_map.select(cdict) or "profile-Rpd2Srgb.dpi"

    sba_dpi = resolve_dpi_key(
        sba_key, index, root / "sba" / "SbaDPI"
    )
    shasta_dpi = resolve_dpi_key(shasta_key, index, root / "shasta")
    profile_dpi = resolve_dpi_key(profile_key, index, root / "profile")

    if sba_dpi is None:
        sba_dpi = root / "sba" / "SbaDPI" / "sba-CN-default.dpi"
        sba_key = "ansel-sba-CN-default"
    if shasta_dpi is None:
        shasta_dpi = root / "shasta" / "shasta-rpd.dpi"
        shasta_key = "ansel-shasta-rpd"

    contrast, fugc_name = fugc_map.select_lut_name(
        ctx.product_code, ctx.gen_code, ctx.iso
    )
    fugc_lut = root / "fugc" / fugc_name
    if not fugc_lut.is_file():
        fugc_lut = root / "fugc" / "fugc-generic0225.lut"
        fugc_name = fugc_lut.name
        contrast = 2.25

    sra_name = sra_fwd_lut_name(ctx.metric)
    sra_lut = root / "common" / sra_name
    if not sra_lut.is_file():
        sra_lut = root / "common" / "common-sraFwdLut-metric-default.lut"
        sra_name = sra_lut.name

    return SelectedAnselFiles(
        sba_dpi=sba_dpi,
        shasta_dpi=shasta_dpi,
        fugc_lut=fugc_lut,
        sra_lut=sra_lut,
        profile_dpi=profile_dpi,
        sba_key=sba_key,
        shasta_key=shasta_key,
        fugc_contrast=contrast,
        fugc_name=fugc_name,
        sra_name=sra_name,
        profile_key=profile_key,
    )
