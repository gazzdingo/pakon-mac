#!/usr/bin/env python3
"""SCPLut balance — verified catalog + DPI parse (PakonIMAu.dll).

OrderWide stage between the two ``analyzeBalanceOrder`` calls. Do **not**
invent slope/offset / ``scpLutWork`` maths. ``SCP_LUT_BALANCE_PORTED =
False`` until Cap→Impl analyze is complete.

Call chain (VERIFIED)
=====================
* Path ``ColorNegativePath::analyzeScpLutBalance`` @ ``0x100fd190``
  (string ``0x10586b18``).
* Cap lookup name ``"scpLut"`` @ ``0x1057a038`` via ``0x10020a40``.
* Cap ``AnsSCPLutCapability::analyze`` @ ``0x101226c0`` (path
  ``E8`` @ ``0x100fd93e``); sets Cap ``+0xf = 1`` @ ``0x1012286b``.
* Cap → Impl ``AnsSCPLutCapabilityImpl::analyze`` @ ``0x102128f0``
  (``E8`` @ ``0x10122777``; string ``0x1059da00``).
* Cap ``acquire`` @ ``0x10122b10``; Impl ``initialize`` @ ``0x10212130``
  (opens ``dataPathItems`` / ``SCPLut`` directory; errors
  ``Error opening the AnsSCPLut directory`` /
  ``Error reading first file from SCPLut directory``).

Path sequence inside ``analyzeScpLutBalance`` (VERIFIED order)
--------------------------------------------------------------
1. Find Cap ``"scpLut"`` (fail → ``SCPLut capability not found.``).
2. Find Cap ``"sba"`` / ``"fos"`` (fail → capability-not-found logs).
3. Fos helpers on the Fos Cap (``edi``):
   * ``0x1013c4e0`` → thunk ``0x1023fc70``: if Impl ``+0x88`` set,
     return ``&Impl+0x18`` (results block); else ``NULL``.
   * ``0x1013c200``: dump ``SbaFOSResults:`` / ``orderFpo =``.
4. **SBA/FOS-disabled log strings** (informational — not Cap unregister):
   * If ``[ebp+0xc]==0`` and ``[ebx+0xc]==0``: log
     ``SBA disabled with SCPLut enabled`` (``0x10586af4``, line
     ``0x4ec``).
   * Else call ``0x1013c4d0`` → ``0x1023fc10``
     (``mov al, [Impl+0x94]; ret``); under further flag tests log
     ``FOS disabled with SCPLut enabled`` (``0x10586ad0``, line
     ``0x4f0``). Shared log call ``0x1001ed90``.
5. **Zero FUGC aim words** @ ``0x100fd8be``:
   ``xor eax,eax``; ``mov word [ebx+0x4b6/+0x4b8/+0x4ba], ax``.
6. Cap ``analyze`` ``0x101226c0``; helpers ``0x10122a70`` /
   ``0x10122150`` → Impl copy path ``0x102120fd`` (3×int16 from
   ``Impl+0x10``).
7. Scene-context glue ``0x10021730``; ``ret`` @ ``~0x100fd9ea``.

Relation to balanceOrder (VERIFIED; coupling UNKNOWN)
-----------------------------------------------------
* OrderWide: ``analyzeBalanceOrder`` → **this** → ``analyzeBalanceOrder``
  again.
* Second pass Cap names ``afterSCPLutSba`` / ``afterSCPLutFos``
  (``0x10574124`` / ``0x10574134``; pushes @ ``0x10101282`` /
  ``0x101012a3``) vs first-pass ``"sba"`` / ``"fos"``.
* Whether SCPLut slopes/offsets rewrite SBA shifts / FOS FPO:
  **UNKNOWN** (no static edge into ``scene+0x3a38`` found).

What it builds (VERIFIED names; maths UNKNOWN)
----------------------------------------------
Dump / result surface (``AnsSCPLutResults:`` @ ``0x1059db0c``;
``scpLutWork`` @ ``0x1059da60``):

* ``redSlope`` / ``greenSlope`` / ``blueSlope``
* ``redOffset`` / ``greenOffset`` / ``blueOffset``
* ``slopeDist`` / ``slopeLimiter`` / ``visualGamma``

Impl analyze body (~KB, FPU / image walk) is a **soft wall** — not
ported. Balance **analyze** product is the slope/offset result block
above (DPI-driven). Separately, SCPLut Impl owns ``Ans3BandLutParams``
at ``+0x10`` (ctor ``0x10213123``) and setShifts ``(1,2)`` indexes that
planar table (shipped ``luts6_postROMM_equalRGBshort.lut`` via
``common-3BandLuts.dpi``) — see ``docs/52`` / ``load_3band_lut_ascii``.

Shipped data (VERIFIED)
-----------------------
Under ``anselinstalldir/dataPathItems/SCPLut/``:

* Sole file:
  ``SCPLut-scanner-prod-gen-default-default-default.dpi``
* Selector stem string ``SCPLut-scanner-prod-gen`` @ ``0x10599324``.
* **No** ``scpLut.map`` / ``.lut`` beside that dpi in the Update-2
  tree.

``AnsSCPLutDPI::readAscii`` @ ``0x101d03b0`` (string ``0x10599620``)
accepts the dpi keys below; range errors for
``slopeDeltaThreshold`` / ``proportionalCorrection`` not in ``[0,2]``.

``ntdChoice`` / ``ctdChoice`` → int16 ``+0x38`` / ``+0x3a`` (VERIFIED)
--------------------------------------------------------------------
``_stricmp`` tokens ``ans_first_pass`` / ``ans_lut_first_pass`` /
``ans_second_pass`` → ``0`` / ``1`` / ``2`` (@ ``0x101d07f4…`` /
``0x101d088f…``). Dump ``0x101d0050`` names ``m_ntdChoice`` /
``m_ctdChoice``. These are **``setShifts`` control words** via SCPLut
Cap ``+0x10+0x18`` (``docs/52``). Shipped dpi → ``(1, 2)``.

Ported below
------------
DPI ASCII parse + enum/bool normalization matching ``readAscii``
tokens / range checks only; ``pass_choice_to_word`` for ntd/ctd;
3-band LUT ASCII → planar (for setShifts ``(1,2)``). Analyze worker
``0x10287eb0`` leaves: opponent ``0x1028c4e0``, slopeDist, LUT index
clamp (``SCP_LUT_ANALYZE_LEAVES_PORTED``). Full
``SCP_LUT_BALANCE_PORTED`` still False until worker end-to-end golden.
setShifts ``(1,2)`` is DLL-golden in ``pakon_sba_apply`` /
``pakon_setshifts_golden`` (``SETSHIFTS_12_PORTED=True``).
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SCP_LUT_BALANCE_PORTED = False
SCP_LUT_DPI_PARSE_PORTED = True  # ASCII surface only
THREE_BAND_LUT_ASCII_PORTED = True  # file → planar only
# Opponent / slopeDist / LUT index+clamp leaves of 0x10287eb0 / 0x10212899
SCP_LUT_ANALYZE_LEAVES_PORTED = True

SHIPPED_3BAND_LUT_NAME = "luts6_postROMM_equalRGBshort.lut"
SHIPPED_3BAND_INDEX_DPI = "common-3BandLuts.dpi"
# Ans3BandLutParams / SCPLut Impl+0x10 (docs/52)
SCP_GET_3BAND_PARAMS = 0x10122150  # → 0x10212100
SCP_IMPL_PARAMS_STORE = 0x10213123  # mov [esi+0x10], eax
STR_ANS_3BAND_PARAMS = 0x105A4210

# setShifts control-word path (docs/52)
SCP_DPI_NTD_OFF = 0x38
SCP_DPI_CTD_OFF = 0x3A
SCP_CAP_COPY_FROM_SCENE_PLUS_0x18 = 0x10122A70
SCP_DPI_DUMP = 0x101D0050
STR_ANS_FIRST_PASS = 0x10599574
STR_ANS_LUT_FIRST_PASS = 0x10599560
STR_ANS_SECOND_PASS = 0x10599550

# --- Path / Cap / Impl ---
PATH_ANALYZE_SCP_LUT_BALANCE = 0x100FD190
PATH_SCP_ZERO_FUGC_AIMS = 0x100FD8BE
PATH_SCP_CAP_ANALYZE_CALL = 0x100FD93E
PATH_SCP_RET = 0x100FD9EA

SCP_CAP_ANALYZE = 0x101226C0
SCP_CAP_ANALYZE_TO_IMPL = 0x10122777
SCP_CAP_SET_ANALYZED = 0x1012286B  # mov byte [ebx+0xf], 1
SCP_CAP_ACQUIRE = 0x10122B10
SCP_IMPL_INITIALIZE = 0x10212130
SCP_IMPL_ANALYZE = 0x102128F0
SCP_IMPL_ANALYZE_WORKER = 0x102127D0  # packs args → 0x10287eb0
SCP_IMPL_CORE = 0x10287EB0  # slopes/offsets + LUT fill
SCP_IMPL_OPPONENT = 0x1028C4E0  # RGB→opponent (Preference consts)
SCP_IMPL_SLOPE_DIST = 0x10212899  # sqrt(R²+G²+B²−RG−RB−GB)
SCP_DPI_READ_ASCII = 0x101D03B0

# Layout / constants (cite core)
SCP_IMPL_FLAG_4C = 0x4C  # gate byte @ 0x10212937
SCP_CHANNEL_COUNT = 0x1000  # push $0x1000 @ 0x10212965
SCP_LUT_CLAMP_MAX = 0xFFF  # cmp ax,0xfff @ 0x10288256
SCP_F64_0 = 0.0  # 0x10573c40
SCP_F64_1 = 1.0  # 0x10574f50
SCP_F64_0_5 = 0.5  # 0x10574f40
SCP_F64_1E_4 = 0.0001  # 0x105a69e8
SCP_F64_SQRT3 = 1.7320508  # 0x105a69e0
# visual-gamma weights when mode word == 1 @ 0x10288065…
SCP_F64_VG_R = 0.414  # 0x105a69d8
SCP_F64_VG_G = 0.079  # 0x105a69d0
SCP_F64_VG_B = 0.507  # 0x105a69c8
# opponent matrix (same rdata as Preference)
SCP_INV_SQRT3 = 0.5773502717125849  # 0x105a6f38
SCP_INV_SQRT6 = 0.40824829759439285  # 0x105a6f30
SCP_INV_SQRT2 = 0.7071067623730956  # 0x105a6f28
SCP_SQRT_2_OVER_3 = 0.8164965951887857  # 0x105a6f40
# Result store offs on Impl after worker (@ 0x10212848…)
SCP_RES_RED_SLOPE = 0x68
SCP_RES_GREEN_SLOPE = 0x70
SCP_RES_BLUE_SLOPE = 0x78
SCP_RES_RED_OFFSET = 0x80
SCP_RES_GREEN_OFFSET = 0x88
SCP_RES_BLUE_OFFSET = 0x90
SCP_RES_SLOPE_DIST = 0xB0

# Fos Cap helpers used by the disable-log / dump prelude
FOS_CAP_GET_RESULTS_PTR = 0x1013C4E0  # → 0x1023fc70
FOS_CAP_FLAG_0x94 = 0x1013C4D0  # → 0x1023fc10
FOS_DUMP_SBA_FOS_RESULTS = 0x1013C200
FOS_IMPL_GET_RESULTS_PTR = 0x1023FC70
FOS_IMPL_READ_FLAG_0x94 = 0x1023FC10

# --- Strings ---
STR_PATH = 0x10586B18
STR_CAP_NAME = 0x1057A038  # "scpLut"
STR_SBA_DISABLED = 0x10586AF4
STR_FOS_DISABLED = 0x10586AD0
STR_CAP_NOT_FOUND = 0x1057A488
STR_CAP_ANALYZE = 0x105887E0
STR_IMPL_ANALYZE = 0x1059DA00
STR_IMPL_INIT = 0x1059D970
STR_DPI_READ_ASCII = 0x10599620
STR_DPI_STEM = 0x10599324  # SCPLut-scanner-prod-gen
STR_AFTER_SBA = 0x10574124  # afterSCPLutSba
STR_AFTER_FOS = 0x10574134  # afterSCPLutFos
STR_RESULTS = 0x1059DB0C

# readAscii tokens (lowercase compares in DLL)
OFFSET_OPTIONS = (
    "ANS_SCPLUT_ZERO_PIVOT",
    "ANS_SCPLUT_DMIN_PIVOT",
    "ANS_SCPLUT_SCP_OFFSET",
)
PASS_CHOICES = (
    "ANS_FIRST_PASS",
    "ANS_LUT_FIRST_PASS",
    "ANS_SECOND_PASS",
)
# readAscii int16 encoding (case-insensitive token match)
PASS_CHOICE_WORD = {
    "ANS_FIRST_PASS": 0,
    "ANS_LUT_FIRST_PASS": 1,
    "ANS_SECOND_PASS": 2,
}

SHIPPED_DPI_NAME = "SCPLut-scanner-prod-gen-default-default-default.dpi"
# After readAscii on shipped file (ntd=lut_first, ctd=second)
SHIPPED_SETSHIFTS_CTRL = (1, 2)


@dataclass(frozen=True)
class ScpLutDpi:
    """Shipped ``AnsSCPLutDPI`` ASCII fields (no analyze maths)."""

    offset_option: str
    modify_dmin: bool
    use_scp_lut: bool
    visual_weighting: bool
    run_scp_after_lut: bool
    proportional_correction: float
    slope_delta_threshold: float
    ntd_choice: str
    ctd_choice: str
    path: Path | None = None


def parse_dpi_scalars(path: Path) -> dict[str, str]:
    """ASCII ``key = value`` (generic dpi surface)."""
    out: dict[str, str] = {}
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _bool(d: dict[str, str], key: str, default: bool) -> bool:
    if key not in d:
        return default
    return d[key].strip().lower() in ("true", "1", "yes")


def _norm_token(s: str) -> str:
    return s.strip().upper()


def scp_lut_analyze_gate(impl_flag_4c: int, arg_flag: int) -> bool:
    """Impl analyze uses live args when both flags non-zero @ ``0x10212937…47``.

    Else pushes seven zeros before ``0x102127d0`` (@ ``0x1021299c``).
    """
    if not SCP_LUT_ANALYZE_LEAVES_PORTED:
        raise NotImplementedError("ScpLut analyze leaves not marked ported")
    # PakonIMAu.dll @ 0x10212937 / @ 0x10212942
    return int(impl_flag_4c) != 0 and int(arg_flag) != 0


def scp_lut_opponent_transform(
    r: float, g: float, b: float
) -> tuple[float, float, float]:
    """``0x1028c4e0`` — Preference-const opponent from RGB doubles.

    ``o0 = R·INV_√3 − G·INV_√6 − B·INV_√2``;
    ``o1 = R·INV_√3 + G·√(2/3)``;
    ``o2 = R·INV_√3 − G·INV_√6 + B·INV_√2``.
    """
    if not SCP_LUT_ANALYZE_LEAVES_PORTED:
        raise NotImplementedError("ScpLut analyze leaves not marked ported")
    # PakonIMAu.dll @ 0x1028c4e4…0x1028c53c
    o0 = r * SCP_INV_SQRT3 - g * SCP_INV_SQRT6 - b * SCP_INV_SQRT2
    o1 = r * SCP_INV_SQRT3 + g * SCP_SQRT_2_OVER_3
    o2 = r * SCP_INV_SQRT3 - g * SCP_INV_SQRT6 + b * SCP_INV_SQRT2
    return o0, o1, o2


def scp_lut_slope_dist(red: float, green: float, blue: float) -> float:
    """``sqrt(R²+G²+B² − RG − RB − GB)`` @ ``0x10212899…0x102128bb``."""
    if not SCP_LUT_ANALYZE_LEAVES_PORTED:
        raise NotImplementedError("ScpLut analyze leaves not marked ported")
    r, g, b = float(red), float(green), float(blue)
    # PakonIMAu.dll @ 0x10212899…0x102128bb
    return math.sqrt(r * r + g * g + b * b - r * g - r * b - g * b)


def scp_lut_ftol2(x: float) -> int:
    """``0x104ffe44`` chop toward zero (same as Preference)."""
    # PakonIMAu.dll @ 0x104ffe44 — C cast / trunc toward 0
    return int(float(x))  # Python trunc toward 0 for finite floats


def scp_lut_index_sample(slope: float, offset: float, i: int) -> int:
    """One channel sample ``ftol2(slope·i − offset + 0.5)`` @ ``0x102881fa…``."""
    if not SCP_LUT_ANALYZE_LEAVES_PORTED:
        raise NotImplementedError("ScpLut analyze leaves not marked ported")
    # PakonIMAu.dll @ 0x102881fa — fmul i; @ 0x10288200 fsub offset; @ 0x10288204 fadd 0.5
    return scp_lut_ftol2(float(slope) * float(i) - float(offset) + SCP_F64_0_5)


def scp_lut_clamp_i16(v: int) -> int:
    """Clamp to ``[0, 0xfff]`` @ ``0x10288249…0x10288296``."""
    if not SCP_LUT_ANALYZE_LEAVES_PORTED:
        raise NotImplementedError("ScpLut analyze leaves not marked ported")
    x = int(v)
    if x < 0:  # @ 0x1028824c
        return 0
    if x > SCP_LUT_CLAMP_MAX:  # @ 0x10288256
        return SCP_LUT_CLAMP_MAX
    return x


def scp_lut_fill_channel(
    slope: float, offset: float, n: int = SCP_CHANNEL_COUNT
) -> list[int]:
    """``0x102881e6…0x102882af`` host face for one output plane."""
    if not SCP_LUT_ANALYZE_LEAVES_PORTED:
        raise NotImplementedError("ScpLut analyze leaves not marked ported")
    out: list[int] = []
    for i in range(int(n)):
        out.append(scp_lut_clamp_i16(scp_lut_index_sample(slope, offset, i)))
    return out


def scp_lut_visual_gamma_scale(r: float, g: float, b: float) -> float:
    """``1 / (0.414·R + 0.079·G + 0.507·B)`` when mode word==1 @ ``0x10288065``."""
    if not SCP_LUT_ANALYZE_LEAVES_PORTED:
        raise NotImplementedError("ScpLut analyze leaves not marked ported")
    # PakonIMAu.dll @ 0x10288065…0x10288085 — fdivr 1.0
    den = SCP_F64_VG_R * float(r) + SCP_F64_VG_G * float(g) + SCP_F64_VG_B * float(b)
    return SCP_F64_1 / den if den != 0.0 else 0.0


def pass_choice_to_word(token: str) -> int:
    """Map dpi ``ntdChoice``/``ctdChoice`` token → int16 (``readAscii``).

    Cite: ``0x101d07f4`` / ``0x101d0810`` / ``0x101d0834`` (ntd) and
    ``0x101d088f`` / ``0x101d08ab`` / ``0x101d08cf`` (ctd). Unknown
    tokens raise ``ValueError`` — DLL logs and leaves prior value.
    """
    key = _norm_token(token)
    if key not in PASS_CHOICE_WORD:
        raise ValueError(f"unknown SCPLut pass choice {token!r}")
    return PASS_CHOICE_WORD[key]


def setshifts_ctrl_from_dpi(dpi: ScpLutDpi) -> tuple[int, int]:
    """``(ntdChoice, ctdChoice)`` words consumed by ``setShifts``.

    Opt-in diagnostic helper — does **not** run the ``(1,2)`` transform.
    """
    return pass_choice_to_word(dpi.ntd_choice), pass_choice_to_word(dpi.ctd_choice)


def load_scp_lut_dpi(path: Path) -> ScpLutDpi:
    """Parse shipped SCPLut dpi; enforce ``readAscii`` ``[0,2]`` ranges.

    Raises ``ValueError`` on out-of-range floats (same messages' ranges
    as DLL). Does **not** run Cap initialize / analyze.
    """
    d = parse_dpi_scalars(path)
    prop = float(d.get("proportionalCorrection", "0"))
    slope = float(d.get("slopeDeltaThreshold", "0"))
    if not 0.0 <= prop <= 2.0:
        raise ValueError("proportionalCorrection not in range [0,2].")
    if not 0.0 <= slope <= 2.0:
        raise ValueError("slopeDeltaThreshold not in range [0,2].")
    off = _norm_token(d.get("offsetOption", "ANS_SCPLUT_ZERO_PIVOT"))
    ntd = _norm_token(d.get("ntdChoice", "ANS_LUT_FIRST_PASS"))
    ctd = _norm_token(d.get("ctdChoice", "ANS_SECOND_PASS"))
    return ScpLutDpi(
        offset_option=off,
        modify_dmin=_bool(d, "modifyDmin", False),
        use_scp_lut=_bool(d, "useSCPLut", False),
        visual_weighting=_bool(d, "visualWeighting", False),
        run_scp_after_lut=_bool(d, "runSCPAfterLut", False),
        proportional_correction=prop,
        slope_delta_threshold=slope,
        ntd_choice=ntd,
        ctd_choice=ctd,
        path=path,
    )


def find_shipped_dpi(ansel_root: Path) -> Path | None:
    """``<ansel_root>/dataPathItems/SCPLut/<SHIPPED_DPI_NAME>`` if present."""
    p = ansel_root / "dataPathItems" / "SCPLut" / SHIPPED_DPI_NAME
    return p if p.is_file() else None


@dataclass(frozen=True)
class ThreeBandLut:
    """Planar ``Ans3BandLutParams`` table (setShifts indexing)."""

    name: str
    num_lut: int
    num_bands: int
    planar: tuple[int, ...]  # len == num_lut * num_bands, band-major


def load_3band_lut_ascii(path: Path) -> ThreeBandLut:
    """Load shipped interleaved ``index R G B`` lut into planar int16s.

    File surface matches ``luts6_postROMM_equalRGBshort.lut``
    (``NUM_LUT`` / ``NUM_BANDS`` / ``LUT_DATA``). Runtime layout used by
    setShifts ``(1,2)`` is planar with stride ``NUM_LUT`` (``docs/52``).
    Missing index 0 rows stay 0.
    """
    name = path.name
    num_lut = 4096
    num_bands = 3
    rows: dict[int, tuple[int, int, int]] = {}
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            key = k.strip().upper()
            val = v.strip()
            if key == "LUT_NAME":
                name = val.split()[0]
            elif key == "NUM_LUT":
                num_lut = int(val.split()[0])
            elif key == "NUM_BANDS":
                num_bands = int(val.split()[0])
            continue
        parts = line.split()
        if len(parts) == 4:
            idx, r, g, b = (int(x) for x in parts)
            rows[idx] = (r, g, b)
    if num_bands < 3:
        raise ValueError(f"NUM_BANDS={num_bands} too small for RGB planar")
    planar = [0] * (num_lut * num_bands)
    for idx, (r, g, b) in rows.items():
        if 0 <= idx < num_lut:
            planar[idx] = r
            planar[idx + num_lut] = g
            planar[idx + 2 * num_lut] = b
    return ThreeBandLut(
        name=name,
        num_lut=num_lut,
        num_bands=num_bands,
        planar=tuple(planar),
    )


def find_shipped_3band_lut(ansel_root: Path) -> Path | None:
    """Locate shipped 3-band lut under anselinstalldir or dataPathItems."""
    root = Path(ansel_root)
    candidates = (
        root / "common" / SHIPPED_3BAND_LUT_NAME,  # dataPathItems root
        root / "dataPathItems" / "common" / SHIPPED_3BAND_LUT_NAME,
        root / "anselinstalldir" / "dataPathItems" / "common" / SHIPPED_3BAND_LUT_NAME,
    )
    for p in candidates:
        if p.is_file():
            return p
    return None


def main() -> None:
    print("ScpLutBalance catalog (base 0x10000000)")
    print(f"  Path::analyzeScpLutBalance {PATH_ANALYZE_SCP_LUT_BALANCE:#010x}")
    print(f"  Cap::analyze               {SCP_CAP_ANALYZE:#010x}")
    print(f"  Impl::analyze              {SCP_IMPL_ANALYZE:#010x}")
    print(f"  core 0x10287eb0            {SCP_IMPL_CORE:#010x}")
    print(f"  ANALYZE_LEAVES={SCP_LUT_ANALYZE_LEAVES_PORTED} BALANCE={SCP_LUT_BALANCE_PORTED}")
    print(f"  zero +0x4b6/4b8/4ba        {PATH_SCP_ZERO_FUGC_AIMS:#010x}")
    print(f"  DPI readAscii              {SCP_DPI_READ_ASCII:#010x}")
    # leaf smoke
    o = scp_lut_opponent_transform(1.0, 1.0, 1.0)
    print(f"  opponent(1,1,1)={o}")
    print(f"  slopeDist(1,1,1)={scp_lut_slope_dist(1,1,1)}")
    print(f"  fill identity mid={scp_lut_fill_channel(1.0, 0.0, 8)}")

    print(f"  SCP_LUT_BALANCE_PORTED={SCP_LUT_BALANCE_PORTED}")
    print(f"  SCP_LUT_DPI_PARSE_PORTED={SCP_LUT_DPI_PARSE_PORTED}")


if __name__ == "__main__":
    main()
