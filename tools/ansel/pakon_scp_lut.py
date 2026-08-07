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
3-band LUT ASCII → planar (for setShifts ``(1,2)``). Analyze /
``SCP_LUT_BALANCE_PORTED`` still False. setShifts closed form lives in
``pakon_sba_apply`` / ``docs/52`` (``SETSHIFTS_12_PORTED=False``).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SCP_LUT_BALANCE_PORTED = False
SCP_LUT_DPI_PARSE_PORTED = True  # ASCII surface only
THREE_BAND_LUT_ASCII_PORTED = True  # file → planar only

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
SCP_DPI_READ_ASCII = 0x101D03B0

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
    """``<ansel_root>/dataPathItems/common/<SHIPPED_3BAND_LUT_NAME>``."""
    p = ansel_root / "dataPathItems" / "common" / SHIPPED_3BAND_LUT_NAME
    return p if p.is_file() else None


def main() -> None:
    print("ScpLutBalance catalog (base 0x10000000)")
    print(f"  Path::analyzeScpLutBalance {PATH_ANALYZE_SCP_LUT_BALANCE:#010x}")
    print(f"  Cap::analyze               {SCP_CAP_ANALYZE:#010x}")
    print(f"  Impl::analyze              {SCP_IMPL_ANALYZE:#010x}")
    print(f"  zero +0x4b6/4b8/4ba        {PATH_SCP_ZERO_FUGC_AIMS:#010x}")
    print(f"  DPI readAscii              {SCP_DPI_READ_ASCII:#010x}")
    print(f"  setShifts ctrl (shipped)   {SHIPPED_SETSHIFTS_CTRL}")
    print(f"  SCP_LUT_BALANCE_PORTED={SCP_LUT_BALANCE_PORTED}")
    print(f"  SCP_LUT_DPI_PARSE_PORTED={SCP_LUT_DPI_PARSE_PORTED}")


if __name__ == "__main__":
    main()
