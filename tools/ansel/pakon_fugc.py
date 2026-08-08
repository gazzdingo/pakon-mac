#!/usr/bin/env python3
"""FUGC path (PakonIMAu.dll) — verified fragments + address catalog.

Pakon-only: cite DLL / shipped files. Do **not** invent histogram→aim maths.

Relationship: shipped LUT vs analyze (VERIFIED)
==============================================

* ``fugc-lutMap.map`` (and neutral/rgb variants) maps film/ISO → **contrast**
  float, then ``contrast = …  fugc-generic*.lut`` → filename
  (``AnsFugcMapping`` / ``0x101fb140`` picks ``fugc-neutral-lutMap.map`` vs
  ``fugc-rgb-lutMap.map``; ``setContrast`` @ ``0x101f9a00`` →
  ``Mapping::find`` @ ``0x101feea0`` → load lut key).
* Shipped ``fugc-generic*.lut`` is the **seed** ``AnsFugcLutDpi`` table
  (3×4096 ``int16`` + ``aTableDmin``), not necessarily the final apply LUT.
* ``setLutInfo`` @ ``0x101f82c0`` builds Cap ``+0x6140`` apply LUT from seed
  at Cap ``+0xe6`` (= embedded LutDpi ``+0x6a``) using per-channel offsets
  from analyze-stored aims @ ``+0x60ec…+0x60fc``.
* Host ``pakon_ansel`` Preference path: after Shasta, runs ``setLutInfo``
  with Pakon aim words (setShifts OUT / FindDmin / aFilmAimDmin /
  aTableDmin) then ``apply_1d_lut``. Fallback (no Preference) may still
  apply the seed alone as a stand-in.

``setLutInfo`` maths (VERIFIED @ ``0x101f82c0``)
-----------------------------------------------
Global size ``N = 4096`` @ ``0x10589834``.

Per channel ``ch`` (seed/out advance by ``2*N`` bytes):

  ``offset = int16(w[0x60ec+2*ch] - w[0x60f8+2*ch] + w[0x60f2+2*ch])``

  If ``offset > N-1``: ``out[i] = i`` (identity).
  Else: ``out[0:offset] = offset``; for ``i in [offset,N)``:
  ``out[i] = clamp(seed[i-offset] + offset, 0, N-1)``.

Aim fields for ``setLutInfo`` — NOT from histogram (VERIFIED @ analyze)
----------------------------------------------------------------------
Filled in ``AnsFugcCapabilityImpl::analyze`` @ ``0x101fc370`` **before**
``setContrast`` / ``setLutInfo``. Histogram/metrics do **not** write these.

* ``+0x60f8/+0x60fa/+0x60fc`` ← Cap ``+0xe0/+0xe2/+0xe4`` =
  LutDpi ``aTableDmin`` (from seed lut / ``0x101f7b10`` install).
* ``+0x60f2/+0x60f4/+0x60f6`` ← analyze arg ``[ebp+0x14]`` (3×int16).
  Cap wrapper ``0x10118af0`` forwards caller ``[ebp+0x14]``.
* ``+0x60ec/+0x60ee/+0x60f0`` — size/policy branch (@ ``0x101fc3c4…``):

  - Compare analyze arg ``[ebp+0x18]`` (3×int16) vs Cap ``+0x12/+0x14/+0x16``
    using factor ``0.2`` @ ``0x10588eb8``.
  - Per channel (ALL must pass): ``0.2·params ≤ arg ≤ 2.0·params``
    (cite ``fcompp`` / ``test ah,5`` / ``test ah,0x41`` @ ``0x101fc3e4…``).
  - If checks **pass**: copy ``[ebp+0x18]`` → ``+0x60ec…``.
  - If checks **fail**: copy Cap ``+0x12/+0x14/+0x16`` → ``+0x60ec…``.

* Cap ``+0x12/+0x14/+0x16``: copied from ``AnsFugcParamsDpi`` ``+0x12…``
  (@ ``0x10118380`` / ``0x101183cd``). Dpi key ``aFilmAimDmin``
  (``fugc-defaultParams.dpi``: ``500 1000 1000``).

Path caller of Cap analyze (VERIFIED)
-------------------------------------
``ColorNegativePath::analyzeFugc`` @ ``0x100fed00`` site ``0x100feee0``
pushes (object ``edi``):

* Cap ``[ebp+0x14]`` = ``&obj+0x4b6`` — **same** field written by
  ``setShifts`` OUT on SceneSpecific (before ``analyzeFugc``).
* Cap ``[ebp+0x18]`` = ``&obj+0x3c`` — dmin from bag via
  ``getCnContext`` ``find("dmin")`` / FindDmin (``FRAME_DMIN_RGB_PORTED``).

``analyzeFugc`` itself is invoked from
``CnPremium_analyzeSceneSpecific`` (``0x10055ad1``, ``0x100697ee``),
**not** from OrderWide. ScpLut zeroes ``+0x4b6`` first @ ``0x100fd8be``;
setShifts then fills it before FUGC.

Histogram / metrics (separate — mode 2)
---------------------------------------
* Mode ``+0x60e8 == 2``: skips immediate ``setLutInfo``; calls ``0x101f79b0``,
  later ``calcFugcMetrics`` @ ``0x101fa210`` → ``generateHistogram`` @
  ``0x101f8bc0`` (sole caller ``0x101fa435``).
* Metrics write Cap ``+0x14178…+0x1418c`` (work-metric slots) — **not**
  ``+0x60ec/+0x60f2/+0x60f8``. Bodies UNKNOWN.
* Sole ``setLutInfo`` caller remains analyze ``0x101fc6cd`` (mode ≠ 2 path).

Analyze call chain (cited)
--------------------------
1. Aim/size branch → store ``+0x60ec…+0x60fc``; mode → ``+0x60e8``.
2. ``0x101fb140`` — select lutMap (neutral vs rgb).
3. ``setContrast`` @ ``0x101f9a00`` — load seed into embedded LutDpi.
4. Mode ≠ 2: ``setLutInfo`` → ``+0x6140``. Mode == 2: metrics path.

Apply / export
--------------
* ``applyLut`` @ ``0x101fa5b0`` (wrapper ``0x101186c0``); full pixel path
  not ported. Host Preference applies ``setLutInfo`` LUT via ``apply_1d_lut``.
* ``export`` @ ``0x101f9330`` tags ``"fugc-lut"``; operand wiring UNKNOWN.

UNKNOWN / blockers
------------------
* Mode ``== 2`` ``generateHistogram`` / ``calcFugcMetrics`` maths.
* Full ParamsDpi ``readAscii`` field↔offset table beyond ``aFilmAimDmin``.
* ``applyLut`` COM wrap / export.
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np

# Explicit markers
# Mode≠2 Preference compose: aims provenance + setLutInfo + host apply.
# Mode==2 metrics path still open.
FUGC_ANALYZE_PORTED = True
FUGC_EXPORT_PORTED = False
FUGC_SET_LUT_INFO_PORTED = True
FUGC_SEED_LUT_PORTED = True
FUGC_AIM_STORE_PORTED = True  # analyze field fill @ 0x101fc4a9…
FUGC_AIM_PROVENANCE_PORTED = True  # setShifts≡ebp14; dmin≡ebp18; params dpi

# Cited entry points
PATH_ANALYZE_FUGC = 0x100FED00
PATH_ANALYZE_FUGC_CAP_CALL = 0x100FEEE0  # Cap::analyze site
PATH_FUGC_AIM_EBP14 = 0x4B6  # &path → Cap [ebp+0x14] === setShifts OUT
PATH_FUGC_AIM_EBP18 = 0x3C  # &path → Cap [ebp+0x18] === bag dmin
PATH_EXPORT_FUGC = 0x100FF770
CAP_ANALYZE = 0x10118AF0
CAP_EXPORT = 0x10118DD0
IMPL_ANALYZE = 0x101FC370
IMPL_EXPORT = 0x101F9330
IMPL_GENERATE_HISTOGRAM = 0x101F8BC0
IMPL_CALC_FUGC_METRICS = 0x101FA210
IMPL_SET_LUT_INFO = 0x101F82C0
IMPL_SET_CONTRAST = 0x101F9A00
IMPL_APPLY_LUT = 0x101FA5B0
LUT_DPI_CTOR = 0x101F6910
LUT_DPI_COPY = 0x101F7B10
PARAMS_DPI_COPY_TO_CAP = 0x10118380  # copies +0x12/+0x14/+0x16
MAPPING_FIND = 0x101FEEA0
SELECT_LUT_MAP = 0x101FB140

# Layout (CapabilityImpl)
CAP_PARAMS_AIM = 0x12  # 3×int16 (from ParamsDpi; aFilmAimDmin role)
CAP_LUTDPI_ATABLE_DMIN = 0xE0  # 3×int16
CAP_LUTDPI_SEED = 0xE6  # 3×4096 int16
CAP_AIM_60EC = 0x60EC
CAP_AIM_60F2 = 0x60F2
CAP_AIM_60F8 = 0x60F8
CAP_APPLY_LUT = 0x6140
CAP_MODE = 0x60E8

FUGC_N = 4096  # 0x10589834
F64_SIZE_FRAC = 0.2  # 0x10588eb8
# Shipped ``fugc-defaultParams.dpi`` aFilmAimDmin (Cap +0x12)
AFILM_AIM_DMIN_DEFAULT = (500, 1000, 1000)


def load_fugc_seed_lut(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load shipped ``fugc-generic*.lut`` → seed ``(4096, 3) int32`` + dmin."""
    table = np.arange(FUGC_N, dtype=np.int32)[:, None].repeat(3, axis=1)
    dmin = np.array([500, 500, 500], dtype=np.int32)
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("atabledmin"):
            parts = line.split("=", 1)[1].split()
            if len(parts) >= 3:
                dmin = np.array(
                    [int(parts[0]), int(parts[1]), int(parts[2])],
                    dtype=np.int32,
                )
            continue
        parts = line.split()
        if len(parts) < 4 or not parts[0].lstrip("-").isdigit():
            continue
        i, r, g, b = (int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))
        if 0 <= i < FUGC_N:
            table[i] = (r, g, b)
    return table, dmin


def load_afilm_aim_dmin(path: Path | None = None) -> tuple[int, int, int]:
    """Load ``aFilmAimDmin`` from ``fugc-defaultParams.dpi`` (Cap ``+0x12``).

    Cite ``0x10118380`` copy into Cap. Defaults to shipped
    ``500 1000 1000`` when path missing / key absent.
    """
    if path is None or not Path(path).is_file():
        return AFILM_AIM_DMIN_DEFAULT
    for raw in Path(path).read_text(errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip().lower() == "afilmaimdmin":
            parts = v.split()
            if len(parts) >= 3:
                return int(parts[0]), int(parts[1]), int(parts[2])
    return AFILM_AIM_DMIN_DEFAULT


def set_lut_info_channel(
    seed: np.ndarray,
    offset: int,
    n: int = FUGC_N,
) -> np.ndarray:
    """One channel of ``setLutInfo`` @ ``0x101f82c0``."""
    out = np.empty(n, dtype=np.int32)
    if offset > n - 1:
        out[:] = np.arange(n, dtype=np.int32)
        return out
    if offset < 0:
        raise ValueError(f"offset {offset} < 0 not covered by verified fragment")
    if offset > 0:
        out[:offset] = offset
    idx = np.arange(offset, n, dtype=np.int32)
    vals = seed[idx - offset].astype(np.int32) + offset
    out[offset:] = np.clip(vals, 0, n - 1)
    return out


def set_lut_info(
    seed_rgb: np.ndarray,
    offsets: tuple[int, int, int],
    n: int = FUGC_N,
) -> np.ndarray:
    """Build 3-channel apply LUT (``+0x6140``) from seed (``+0xe6``)."""
    if seed_rgb.shape != (n, 3):
        raise ValueError(f"seed shape {seed_rgb.shape} != ({n}, 3)")
    out = np.empty((n, 3), dtype=np.int32)
    for c, off in enumerate(offsets):
        out[:, c] = set_lut_info_channel(seed_rgb[:, c], int(off), n=n)
    return out


def aim_offset(
    word_60ec: int,
    word_60f8_dmin: int,
    word_60f2_aim: int,
) -> int:
    """Per-channel ``setLutInfo`` offset (int16 arithmetic)."""
    v = np.int16(word_60ec) - np.int16(word_60f8_dmin) + np.int16(word_60f2_aim)
    return int(v)


def fugc_ebp18_policy_pass(
    arg: Sequence[int],
    params: Sequence[int],
    *,
    frac: float = F64_SIZE_FRAC,
) -> bool:
    """Size/policy checks @ ``0x101fc3c4…0x101fc484`` — ALL channels must pass.

    Pass when ``frac·params ≤ arg ≤ 2·params`` per channel (cite FPU
    ``fmul`` 0.2 @ ``0x10588eb8``, then ``fadd`` self for 2×). On fail,
    analyze stores Cap ``+0x12`` params into ``+0x60ec`` instead of arg.
    """
    if len(arg) < 3 or len(params) < 3:
        raise ValueError("need 3 channels for arg and params")
    for i in range(3):
        a = float(int(arg[i]))
        p = float(int(params[i]))
        lo = frac * p
        hi = p + p  # 2.0 * params (cite fld+fadd @ 0x101fc3fb…)
        if not (lo <= a <= hi):
            return False
    return True


def fill_setlutinfo_aim_words(
    *,
    a_table_dmin: tuple[int, int, int],
    arg_ebp14: tuple[int, int, int],
    arg_ebp18: tuple[int, int, int],
    cap_params_aim: tuple[int, int, int],
    use_arg_ebp18: bool | None = None,
) -> dict[str, tuple[int, int, int]]:
    """``0x101fc4a9…0x101fc511`` aim-word fill (not histogram).

    When ``use_arg_ebp18`` is None, derive from ``fugc_ebp18_policy_pass``.
    True → store ``[ebp+0x18]``; False → store Cap ``+0x12`` params aims.
    """
    if use_arg_ebp18 is None:
        use_arg_ebp18 = fugc_ebp18_policy_pass(arg_ebp18, cap_params_aim)
    w60f8 = tuple(int(x) for x in a_table_dmin)
    w60f2 = tuple(int(x) for x in arg_ebp14)
    w60ec = (
        tuple(int(x) for x in arg_ebp18)
        if use_arg_ebp18
        else tuple(int(x) for x in cap_params_aim)
    )
    return {"60ec": w60ec, "60f2": w60f2, "60f8": w60f8}


def build_setlutinfo_apply_lut(
    seed_rgb: np.ndarray,
    *,
    a_table_dmin: tuple[int, int, int],
    arg_ebp14: tuple[int, int, int],
    arg_ebp18: tuple[int, int, int],
    cap_params_aim: tuple[int, int, int],
) -> tuple[np.ndarray, tuple[int, int, int], dict[str, tuple[int, int, int]]]:
    """Analyze aim fill → ``setLutInfo`` apply LUT (mode ≠ 2 compose).

    Returns ``(apply_lut, offsets, aim_words)``.
    """
    aims = fill_setlutinfo_aim_words(
        a_table_dmin=a_table_dmin,
        arg_ebp14=arg_ebp14,
        arg_ebp18=arg_ebp18,
        cap_params_aim=cap_params_aim,
    )
    offs = tuple(
        aim_offset(aims["60ec"][c], aims["60f8"][c], aims["60f2"][c])
        for c in range(3)
    )
    return set_lut_info(seed_rgb, offs), offs, aims  # type: ignore[arg-type]


def main() -> None:
    print("FUGC (PakonIMAu.dll base 0x10000000)")
    print(f"  setLutInfo {IMPL_SET_LUT_INFO:#010x}  analyze {IMPL_ANALYZE:#010x}")
    print(
        f"  ANALYZE_PORTED={FUGC_ANALYZE_PORTED} "
        f"AIM_PROVENANCE={FUGC_AIM_PROVENANCE_PORTED} "
        f"AIM_STORE={FUGC_AIM_STORE_PORTED} "
        f"SET_LUT_INFO={FUGC_SET_LUT_INFO_PORTED}"
    )
    print("  ebp14 = setShifts OUT @ path+0x4b6; ebp18 = bag dmin @ +0x3c")
    # Policy table checks
    params = AFILM_AIM_DMIN_DEFAULT
    cases = [
        ((500, 1000, 1000), True, "exact params"),
        ((99, 1000, 1000), False, "R below 0.2*500"),
        ((100, 1000, 1000), True, "R at 0.2*500 inclusive"),
        ((1000, 2000, 2000), True, "at 2× inclusive"),
        ((1001, 1000, 1000), False, "R above 2×500"),
        ((500, 199, 1000), False, "G below 0.2*1000"),
    ]
    failed = 0
    for arg, expect, label in cases:
        got = fugc_ebp18_policy_pass(arg, params)
        mark = "OK" if got == expect else "FAIL"
        if got != expect:
            failed += 1
        print(f"  {mark} policy {label}: arg={arg} → {got} (expect {expect})")
    aims = fill_setlutinfo_aim_words(
        a_table_dmin=(500, 500, 500),
        arg_ebp14=(100, 200, 300),
        arg_ebp18=(500, 1000, 1000),
        cap_params_aim=params,
    )
    offs = tuple(
        aim_offset(aims["60ec"][c], aims["60f8"][c], aims["60f2"][c])
        for c in range(3)
    )
    print(f"  example offsets (policy pass, setShifts OUT): {offs}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
