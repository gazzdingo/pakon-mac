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
* Host ``pakon_ansel`` applying the selected ``fugc-generic*.lut`` alone is
  therefore a **seed stand-in** (correct data file, missing analyze
  ``setLutInfo`` shift unless offset is 0).

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
  - If checks **pass**: copy ``[ebp+0x18]`` → ``+0x60ec…``.
  - If checks **fail**: copy Cap ``+0x12/+0x14/+0x16`` → ``+0x60ec…``.

* Cap ``+0x12/+0x14/+0x16``: copied from ``AnsFugcParamsDpi`` ``+0x12…``
  (@ ``0x10118380`` / ``0x101183cd``). Dpi key ``aFilmAimDmin`` cited
  (``fugc-defaultParams.dpi`` has ``500 1000 1000``); full ParamsDpi
  ``readAscii`` field↔offset table **partial**.

Path caller of Cap analyze (VERIFIED pointers; values open)
-----------------------------------------------------------
``ColorNegativePath::analyzeFugc`` @ ``0x100fed00`` site ``0x100feee0``
pushes (object ``edi``):

* Cap ``[ebp+0x14]`` = ``&obj+0x4b6`` (feeds ``+0x60f2``)
* Cap ``[ebp+0x18]`` = ``&obj+0x3c`` (feeds ``+0x60ec`` when policy passes)

``analyzeFugc`` itself is invoked from
``CnPremium_analyzeSceneSpecific`` (``0x10055ad1``, ``0x100697ee``),
**not** from OrderWide.

Static writer WALL (``+0x4b6`` / ``+0x3c``)
------------------------------------------
* Sole ``mov word`` stores to ``+0x4b6/+0x4b8/+0x4ba`` in imaging
  ``.text``: ``analyzeScpLutBalance`` @ ``0x100fd8be`` **zeroes** them.
* No ``mov word [r+0x3c]`` in cnMethods range ``0x100f8000…0x10110000``.
* ``analyzeArea`` receives ``&+0x4b6`` **after** ``analyzeFugc`` on the
  SceneSpecific path — cannot supply first-call aims.
* Non-zero fillers: **UNKNOWN** — dynamic RE / through-pointer chase.

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
  not ported.
* ``export`` @ ``0x101f9330`` tags ``"fugc-lut"``; operand wiring UNKNOWN.

UNKNOWN / blockers
------------------
* **Values** at ``obj+0x4b6`` / ``obj+0x3c`` — static writer wall (above).
* Full ParamsDpi ``aFilmAimDmin`` → ``+0x12`` byte map.
* ``generateHistogram`` / ``calcFugcMetrics`` maths (not ``setLutInfo`` aims).
* ``applyLut`` / export.
* ``FUGC_ANALYZE_PORTED = False``. See ``pakon_analyse_roll.py``.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

# Explicit markers
FUGC_ANALYZE_PORTED = False
FUGC_EXPORT_PORTED = False
FUGC_SET_LUT_INFO_PORTED = True  # fragment — needs Pakon aim words
FUGC_SEED_LUT_PORTED = True
FUGC_AIM_STORE_PORTED = True  # analyze field fill; not caller provenance

# Cited entry points
PATH_ANALYZE_FUGC = 0x100FED00
PATH_ANALYZE_FUGC_CAP_CALL = 0x100FEEE0  # Cap::analyze site
PATH_FUGC_AIM_EBP14 = 0x4B6  # &path → Cap [ebp+0x14]
PATH_FUGC_AIM_EBP18 = 0x3C  # &path → Cap [ebp+0x18]
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


def fill_setlutinfo_aim_words(
    *,
    a_table_dmin: tuple[int, int, int],
    arg_ebp14: tuple[int, int, int],
    arg_ebp18: tuple[int, int, int],
    cap_params_aim: tuple[int, int, int],
    use_arg_ebp18: bool,
) -> dict[str, tuple[int, int, int]]:
    """``0x101fc4a9…0x101fc511`` aim-word fill (not histogram).

    ``use_arg_ebp18``: True when the 0.2 size/policy checks **pass**
    (store ``[ebp+0x18]``); False → store Cap ``+0x12`` params aims.
    Does **not** re-derive the FPU branch — caller must know which path.
    """
    w60f8 = tuple(int(x) for x in a_table_dmin)
    w60f2 = tuple(int(x) for x in arg_ebp14)
    w60ec = (
        tuple(int(x) for x in arg_ebp18)
        if use_arg_ebp18
        else tuple(int(x) for x in cap_params_aim)
    )
    return {"60ec": w60ec, "60f2": w60f2, "60f8": w60f8}


def main() -> None:
    print("FUGC (PakonIMAu.dll base 0x10000000)")
    print(f"  setLutInfo {IMPL_SET_LUT_INFO:#010x}  analyze {IMPL_ANALYZE:#010x}")
    print(
        f"  ANALYZE_PORTED={FUGC_ANALYZE_PORTED} "
        f"AIM_STORE={FUGC_AIM_STORE_PORTED} "
        f"SET_LUT_INFO_FRAG={FUGC_SET_LUT_INFO_PORTED}"
    )
    print("  aim fields: analyze args + aTableDmin + params — NOT histogram")
    aims = fill_setlutinfo_aim_words(
        a_table_dmin=(500, 500, 500),
        arg_ebp14=(500, 1000, 1000),
        arg_ebp18=(500, 1000, 1000),
        cap_params_aim=(500, 1000, 1000),
        use_arg_ebp18=False,
    )
    offs = tuple(
        aim_offset(aims["60ec"][c], aims["60f8"][c], aims["60f2"][c])
        for c in range(3)
    )
    print(f"  example offsets (params path): {offs}")


if __name__ == "__main__":
    main()
