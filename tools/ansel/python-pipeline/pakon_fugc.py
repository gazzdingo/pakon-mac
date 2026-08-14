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
  Else: ``out[0:offset] = offset`` (only when ``offset > 0``); for
  ``i in [max(offset,0), max(offset,0), min(offset+N,N))``:
  ``out[i] = clamp(seed[i-offset] + offset, 0, N-1)``; any tail
  ``i in [that upper bound, N)`` gets ``out[i] = i`` (identity) too --
  this is what a negative ``offset`` (or one ``<= -N``) hits, and it is a
  real, no-special-casing-needed path through the SAME clamp loop, not an
  unhandled one. Docstring above described only the ``offset >= 0`` shape
  until docs/66 Phase 6.2's "Track 1" pass live-Unicorn-verified the
  negative-offset case too (previously the port raised there, believing it
  "not covered" -- see ``set_lut_info_channel``'s own docstring).

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

Histogram / metrics (mode 2) — PORTED leaves
--------------------------------------------
* Mode ``+0x60e8 == 2`` (analyze ``0x101fc518…``): skip ``setLutInfo``;
  ``0x101f79b0`` → bias word ``+0x14174``; one-plane LUT fill @ ``0x101fc7e6…``;
  ``calcFugcMetrics`` @ ``0x101fa210`` (analyze site ``0x101fca5c``) →
  thresholds ``+0x14178…+0x1418c`` → ``generateHistogram`` @ ``0x101f8bc0``
  (sole caller ``0x101fa435``) → ``calcWorkMetrics`` @ ``0x101f8e80``.
* Bias ``0x101f79b0``: ``avg3(max(0, 60ec+arg_i)) − avg3(60f8)`` via
  signed ``/3`` magic ``0x55555556`` (store ``+0x14174``).
* Thresholds ``0x101fa269…0x101fa341``: Cap ``+0x40…+0x54`` + bias, clamp
  vs Cap ``+0x38/+0x3c`` (hist min/max). Band order → HIGH/MID/LOW
  (``+0x14158/+0x1415c/+0x14160`` after percent).
* Hist pixel leaf ``AnsHistogram::calcHistogram`` @ ``0x10279952…6d``:
  ``if min≤v≤max: total++; hist[v]++`` (absolute index; shipped min=0).
* Work %: ``100.0 * band_count / total`` @ ``0x101f9094`` / ``0x1059bea8``.
* Sole ``setLutInfo`` caller remains analyze ``0x101fc6cd`` (mode ≠ 2).

Analyze call chain (cited)
--------------------------
1. Aim/size branch → store ``+0x60ec…+0x60fc``; mode → ``+0x60e8``.
2. ``0x101fb140`` — select lutMap (neutral vs rgb).
3. ``setContrast`` @ ``0x101f9a00`` — load seed into embedded LutDpi.
4. Mode ≠ 2: ``setLutInfo`` → ``+0x6140``. Mode == 2: bias + metrics.

Apply / export
--------------
* ``applyLut`` @ ``0x101fa5b0`` (wrapper ``0x101186c0``); full pixel path
  not ported. Host Preference applies ``setLutInfo`` / mode-2 plane via
  ``apply_1d_lut``.
* ``export`` @ ``0x101f9330`` tags ``"fugc-lut"``; operand wiring UNKNOWN.

UNKNOWN / blockers
------------------
* COM image fetch ``0x100d9f90`` inside ``generateHistogram`` (ROI maths ported).
* Full ``AnsHistogram::calcWork`` weighted float (count→% is enough for
  ``FUGC_WORK_*`` percents).
* Full ParamsDpi ``readAscii`` field↔offset table beyond ``aFilmAimDmin`` /
  work-range Cap slots as cited from ``calcFugcMetrics``.
* ``applyLut`` full COM pixel path / export operand (type gate ported).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Tuple

import numpy as np

# Explicit markers
# Mode≠2 Preference compose: aims provenance + setLutInfo + host apply.
# Mode==2: bias + thresholds + hist leaf + work % (Unicorn golden).
FUGC_ANALYZE_PORTED = True
FUGC_EXPORT_PORTED = False
FUGC_SET_LUT_INFO_PORTED = True
FUGC_SEED_LUT_PORTED = True
FUGC_AIM_STORE_PORTED = True  # analyze field fill @ 0x101fc4a9…
FUGC_AIM_PROVENANCE_PORTED = True  # setShifts≡ebp14; dmin≡ebp18; params dpi
FUGC_WORK_BIAS_PORTED = True  # PakonIMAu.dll @ 0x101f79b0
FUGC_WORK_THRESHOLDS_PORTED = True  # PakonIMAu.dll @ 0x101fa269…0x101fa341
FUGC_GENERATE_HISTOGRAM_PORTED = True  # pixel leaf @ 0x10279952
# generateHistogram COM/ROI control @ 0x101f8bc0 (inset + desc offs + hist setup).
FUGC_HIST_COM_ROI_PORTED = True
# applyLut image-type gate @ 0x101fa5e5 (0 or 2 accepted; full COM open).
FUGC_APPLY_LUT_GATE_PORTED = True
FUGC_WORK_PERCENT_PORTED = True  # PakonIMAu.dll @ 0x101f9094… / 0x1059bea8
FUGC_MODE2_LUT_PORTED = True  # PakonIMAu.dll @ 0x101fc7e6…0x101fc8c6
FUGC_METRICS_PORTED = True  # compose: bias+thresholds+hist counts+percents

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
IMPL_GENERATE_HIST_ROI = 0x100D9F90  # COM image ROI helper
IMPL_HIST_SETUP = 0x10278140  # AnsHistogram range/ptr setup
IMPL_HIST_CALC_ROI = 0x10279710  # ROI → pixel leaf
IMPL_CALC_FUGC_METRICS = 0x101FA210
IMPL_CALC_WORK_METRICS = 0x101F8E80
IMPL_WORK_BIAS = 0x101F79B0
IMPL_SET_LUT_INFO = 0x101F82C0
IMPL_SET_CONTRAST = 0x101F9A00
IMPL_APPLY_LUT = 0x101FA5B0
IMPL_HIST_ACCUM_LEAF = 0x10279952  # AnsHistogram::calcHistogram pixel body
IMPL_HIST_CALC_WORK = 0x10278DF0
LUT_DPI_CTOR = 0x101F6910
LUT_DPI_COPY = 0x101F7B10
PARAMS_DPI_COPY_TO_CAP = 0x10118380  # copies +0x12/+0x14/+0x16
MAPPING_FIND = 0x101FEEA0
SELECT_LUT_MAP = 0x101FB140

# generateHistogram / applyLut layout (cite wrap)
FUGC_CAP_HIST_MIN_OFF = 0x38  # PakonIMAu.dll @ 0x101f8be8
FUGC_CAP_HIST_MAX_OFF = 0x3C  # PakonIMAu.dll @ 0x101f8beb
FUGC_IMG_DESC_WIDTH_OFF = 0xC  # PakonIMAu.dll @ 0x101f8bf5
FUGC_IMG_DESC_HEIGHT_OFF = 0x10  # PakonIMAu.dll @ 0x101f8bf8
FUGC_IMG_DESC_TYPE_OFF = 0x4  # applyLut @ 0x101fa5e2
FUGC_ROI_REQUEST_TYPE = 0xC  # PakonIMAu.dll @ 0x101f8c45
FUGC_ROI_INSET = 2  # add −2 each dim @ 0x101f8d1d / 0x101f8d3f
FUGC_APPLY_LUT_TYPE_OK = (0, 2)  # @ 0x101fa5e5 / 0x101fa5f5

# Layout (CapabilityImpl)
CAP_PARAMS_AIM = 0x12  # 3×int16 (from ParamsDpi; aFilmAimDmin role)
CAP_MODE_SELECT = 0xC  # mode auto: ==2 → +0x60e8=2 @ 0x101fc51a
CAP_HIST_MIN = 0x38  # dpi minValue role (calcFugcMetrics clamp)
CAP_HIST_MAX = 0x3C  # dpi maxValue role
CAP_HIGH_WORK_LO = 0x40  # highWorkRange from
CAP_HIGH_WORK_HI = 0x44
CAP_MID_WORK_LO = 0x48
CAP_MID_WORK_HI = 0x4C
CAP_LOW_WORK_LO = 0x50
CAP_LOW_WORK_HI = 0x54
CAP_LUTDPI_ATABLE_DMIN = 0xE0  # 3×int16
CAP_LUTDPI_SEED = 0xE6  # 3×4096 int16
CAP_AIM_60EC = 0x60EC
CAP_AIM_60F2 = 0x60F2
CAP_AIM_60F8 = 0x60F8
CAP_APPLY_LUT = 0x6140
CAP_MODE = 0x60E8
CAP_WORK_BIAS = 0x14174  # int16
CAP_WORK_FROM_HIGH = 0x14178
CAP_WORK_TO_HIGH = 0x1417C
CAP_WORK_FROM_MID = 0x14180
CAP_WORK_TO_MID = 0x14184
CAP_WORK_FROM_LOW = 0x14188
CAP_WORK_TO_LOW = 0x1418C
CAP_WORK_PCT_HIGH = 0x14158  # float FUGC_WORK_HIGH
CAP_WORK_PCT_MID = 0x1415C
CAP_WORK_PCT_LOW = 0x14160

FUGC_N = 4096  # 0x10589834
F64_SIZE_FRAC = 0.2  # 0x10588eb8
F32_WORK_PCT_SCALE = 100.0  # 0x1059bea8
SIGNED_DIV3_MAGIC = 0x55555556  # PakonIMAu.dll @ 0x101f7a08 / 0x101f7a38
# Shipped ``fugc-defaultParams.dpi`` aFilmAimDmin (Cap +0x12)
AFILM_AIM_DMIN_DEFAULT = (500, 1000, 1000)
# Shipped work ranges / hist domain (Cap +0x38…+0x54 roles)
HIST_MIN_DEFAULT = 0
HIST_MAX_DEFAULT = 4095
HIGH_WORK_RANGE_DEFAULT = (725, 849)
MID_WORK_RANGE_DEFAULT = (600, 724)
LOW_WORK_RANGE_DEFAULT = (400, 599)


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
    """One channel of ``setLutInfo`` @ ``0x101f82c0``.

    ``offset < 0`` was previously believed "not covered by the verified
    fragment" and raised. A parallel investigation (docs/66 Phase 6.2,
    "Track 1 -- FUGC/ColorAdjust golden coverage") found the real DLL
    fragment already handles negative offsets with no special-case branch of
    its own -- it is the SAME clamp-loop the positive-offset path uses, just
    with the prefix-fill (``out[:offset] = offset``) skipped because its own
    loop-trip check (``esi <= 0``) is naturally false, and the loop's end
    bound (``offset + n``, never clamped up to 0 by the DLL) falling below
    the start when ``offset <= -n`` -- which the DLL's own ``eax >= ecx``
    signed-compare loop guard turns into "zero real iterations, tail-fill
    the whole channel identity" for free, with no separate code path. Live
    Unicorn-verified bit-exact against ``PakonIMAu.dll`` 0x101f82c0 across
    offsets from -32768 (int16 min) to +5000, including the ``offset <= -n``
    all-identity edge -- see ``pakon_fugc_golden.py``'s
    ``check_set_lut_info``. Not yet confirmed to be
    reachable on any real frame this project has measured (this render
    path's own aim deltas have looked small/near-zero so far -- see
    docs/66's "FUGC is very close to a no-op for this specific file" note),
    but the port must not raise on a value the vendor DLL itself computes
    and handles without complaint.
    """
    out = np.empty(n, dtype=np.int32)
    if offset > n - 1:
        out[:] = np.arange(n, dtype=np.int32)
        return out
    if offset > 0:
        out[:offset] = offset
        lo = offset
    else:
        lo = 0
    hi = max(lo, min(offset + n, n))
    idx = np.arange(lo, hi, dtype=np.int32)
    vals = seed[idx - offset].astype(np.int32) + offset
    out[lo:hi] = np.clip(vals, 0, n - 1)
    if hi < n:
        out[hi:n] = np.arange(hi, n, dtype=np.int32)
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


def signed_div3(n: int) -> int:
    """Signed ``/3`` — PakonIMAu.dll ``imul 0x55555556`` @ ``0x101f7a08``."""
    a = np.int32(n)  # PakonIMAu.dll @ 0x101f7a0d
    magic = np.int32(SIGNED_DIV3_MAGIC)  # PakonIMAu.dll @ 0x101f7a08
    prod = np.int64(a) * np.int64(magic)  # PakonIMAu.dll @ 0x101f7a0d
    hi = np.int32(prod >> 32)  # PakonIMAu.dll EDX after imul
    return int(np.int32(hi + (np.int32(1) if int(hi) < 0 else np.int32(0))))  # @ 0x101f7a1f…


def fugc_work_bias(
    word_60ec: Sequence[int],
    word_60f8_dmin: Sequence[int],
    arg_ebp14: Sequence[int],
) -> int:
    """``0x101f79b0`` → Cap ``+0x14174`` (int16).

    ``avg3(max(0, 60ec_i + arg_i)) − avg3(60f8_i)`` with signed ``/3``.
    """
    sums: list[int] = []
    for i in range(3):
        v = int(np.int16(int(word_60ec[i]) + int(arg_ebp14[i])))  # @ 0x101f79b1…
        if v < 0:  # PakonIMAu.dll @ 0x101f79c0 / 0x101f79d2 / 0x101f79e4
            v = 0
        sums.append(v)
    avg_aim = signed_div3(sums[0] + sums[1] + sums[2] + 1)  # @ 0x101f7a04…0x101f7a24
    d0 = int(np.int16(word_60f8_dmin[0]))  # PakonIMAu.dll @ 0x101f7a2d
    d1 = int(np.int16(word_60f8_dmin[1]))  # PakonIMAu.dll @ 0x101f7a24
    d2 = int(np.int16(word_60f8_dmin[2]))  # PakonIMAu.dll @ 0x101f7a0f
    avg_dmin = signed_div3(d2 + d1 + d0 + 1)  # PakonIMAu.dll @ 0x101f7a34…0x101f7a4b
    return int(np.int16(avg_aim - avg_dmin))  # PakonIMAu.dll @ 0x101f7a4d → +0x14174


def fugc_work_thresholds(
    *,
    bias: int,
    hist_min: int,
    hist_max: int,
    high: tuple[int, int],
    mid: tuple[int, int],
    low: tuple[int, int],
) -> tuple[int, int, int, int, int, int]:
    """``calcFugcMetrics`` threshold fill+clamp @ ``0x101fa269…0x101fa341``.

    Returns ``(hi_lo, hi_hi, mid_lo, mid_hi, low_lo, low_hi)`` for Cap
    ``+0x14178…+0x1418c``.
    """
    b = int(np.int16(bias))  # PakonIMAu.dll @ 0x101fa269 movsx
    hi_lo = int(high[0]) + b  # Cap+0x40 @ 0x101fa291
    hi_hi = int(high[1]) + b  # Cap+0x44 @ 0x101fa293
    mid_lo = int(mid[0]) + b  # Cap+0x48 @ 0x101fa295
    mid_hi = int(mid[1]) + b  # Cap+0x4c @ 0x101fa27c
    low_lo = int(low[0]) + b  # Cap+0x50 @ 0x101fa27f…284
    low_hi = int(low[1]) + b  # Cap+0x54 @ 0x101fa297
    lim = int(hist_min)  # Cap+0x38 @ 0x101fa299
    # Initial stores @ 0x101fa29e…0x101fa2b6
    if hi_lo < lim:  # PakonIMAu.dll @ 0x101fa29c / 0x101fa2bc
        hi_lo = lim  # @ 0x101fa2c0
        if hi_hi <= lim:  # @ 0x101fa2be / 0x101fa2c6
            hi_hi = lim + 1  # @ 0x101fa2ca…0x101fa2cd
            if mid_lo < lim:  # @ 0x101fa2c8 / 0x101fa2d3
                mid_lo = lim  # @ 0x101fa2d7
                if mid_hi <= lim:  # @ 0x101fa2d5 / 0x101fa2dd
                    mid_hi = lim + 1  # @ 0x101fa2e3
                    if low_lo < lim:  # @ 0x101fa2df / 0x101fa2e9
                        low_lo = lim  # @ 0x101fa2ed
                        if low_hi <= lim:  # @ 0x101fa2eb / 0x101fa2f3
                            low_hi = lim + 1  # @ 0x101fa2f5
    else:
        lim = int(hist_max)  # Cap+0x3c @ 0x101fa2fd
        if low_hi > lim:  # @ 0x101fa300 / 0x101fa302
            low_hi = lim  # @ 0x101fa308
            if low_lo >= lim:  # @ 0x101fa304 / 0x101fa30e
                low_lo = lim - 1  # @ 0x101fa312…315
                if mid_hi > lim:  # @ 0x101fa310 / 0x101fa31b
                    mid_hi = lim  # @ 0x101fa31f
                    if mid_lo >= lim:  # @ 0x101fa31d / 0x101fa325
                        mid_lo = lim - 1  # @ 0x101fa329
                        if hi_hi > lim:  # @ 0x101fa327 / 0x101fa32f
                            hi_hi = lim  # @ 0x101fa333
                            if hi_lo >= lim:  # @ 0x101fa331 / 0x101fa339
                                hi_lo = lim - 1  # @ 0x101fa33b
    return hi_lo, hi_hi, mid_lo, mid_hi, low_lo, low_hi


def fugc_hist_accum_i16(
    plane: np.ndarray,
    hist: np.ndarray,
    *,
    hist_min: int = HIST_MIN_DEFAULT,
    hist_max: int = HIST_MAX_DEFAULT,
) -> int:
    """Pixel leaf ``0x10279952…0x1027996d`` — returns total increments.

    Absolute index ``hist[v]++`` when ``min ≤ v ≤ max`` (shipped min=0).
    """
    total = 0
    flat = np.asarray(plane, dtype=np.int16).ravel()
    hmin = int(hist_min)  # PakonIMAu.dll hist+0x8 @ 0x10279956
    hmax = int(hist_max)  # PakonIMAu.dll hist+0xc @ 0x1027995b
    for v in flat:
        iv = int(v)  # PakonIMAu.dll @ 0x10279952 movsx
        if iv < hmin or iv > hmax:  # PakonIMAu.dll @ 0x10279956…0x1027995e
            continue
        hist[iv] = int(hist[iv]) + 1  # PakonIMAu.dll @ 0x1027996d inc
        total += 1  # PakonIMAu.dll @ 0x10279969…6a
    return total


def fugc_hist_roi_inset(width: int, height: int) -> Tuple[int, int]:
    """``generateHistogram`` ROI size after ``add −2`` @ ``0x101f8d1d`` / ``0x101f8d3f``."""
    if not FUGC_HIST_COM_ROI_PORTED:
        raise NotImplementedError("FUGC hist COM/ROI not marked ported")
    # PakonIMAu.dll @ 0x101f8d1d — add edi, -2; @ 0x101f8d3f — add ebp, -2
    return int(width) - FUGC_ROI_INSET, int(height) - FUGC_ROI_INSET


def fugc_hist_setup_ok(hist_min: int, hist_max: int) -> bool:
    """``0x10278140``: range valid iff ``max > min`` (@ ``0x1027816b``)."""
    if not FUGC_HIST_COM_ROI_PORTED:
        raise NotImplementedError("FUGC hist COM/ROI not marked ported")
    # PakonIMAu.dll @ 0x1027816b — cmp esi, edx / jle empty
    return int(hist_max) > int(hist_min)


def fugc_hist_setup_base_adjust(hist_base: int, hist_min: int) -> int:
    """``hist+0x18 = base − 4·min`` @ ``0x1027817d`` (index via absolute v)."""
    if not FUGC_HIST_COM_ROI_PORTED:
        raise NotImplementedError("FUGC hist COM/ROI not marked ported")
    # PakonIMAu.dll @ 0x10278177 — shl edx,2; @ 0x1027817d — sub ecx,edx
    return int(hist_base) - (int(hist_min) * 4)


def fugc_generate_histogram_roi(
    plane: np.ndarray,
    hist: np.ndarray,
    *,
    hist_min: int = HIST_MIN_DEFAULT,
    hist_max: int = HIST_MAX_DEFAULT,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> int:
    """Host face of ``generateHistogram`` after COM ROI succeeds.

    Crops ``[1…h−2]×[1…w−2]`` (inset 2 → 1px margin), then pixel leaf.
    Returns ``0`` when setup range invalid (DLL empty hist object).
    """
    if not FUGC_HIST_COM_ROI_PORTED:
        raise NotImplementedError("FUGC hist COM/ROI not marked ported")
    if not fugc_hist_setup_ok(hist_min, hist_max):
        return 0
    img = np.asarray(plane, dtype=np.int16)
    if img.ndim != 2:
        raise ValueError("plane must be HxW")
    h = int(height) if height is not None else int(img.shape[0])
    w = int(width) if width is not None else int(img.shape[1])
    rw, rh = fugc_hist_roi_inset(w, h)
    if rw <= 0 or rh <= 0:
        return 0
    # 1px margin each side from full−2 inset
    y0, x0 = 1, 1
    crop = img[y0 : y0 + rh, x0 : x0 + rw]
    return fugc_hist_accum_i16(crop, hist, hist_min=hist_min, hist_max=hist_max)


def fugc_apply_lut_type_accepted(image_type: int) -> bool:
    """``applyLut`` accepts desc ``+4`` ∈ ``{0,2}`` @ ``0x101fa5e5…0x101fa5f8``."""
    if not FUGC_APPLY_LUT_GATE_PORTED:
        raise NotImplementedError("applyLut gate not marked ported")
    t = int(image_type)
    # PakonIMAu.dll @ 0x101fa5e5 — je ok (0); @ 0x101fa5f5 — cmp 2 / jne fail
    return t in FUGC_APPLY_LUT_TYPE_OK


def fugc_band_count(hist: np.ndarray, lo: int, hi: int) -> int:
    """Sum dens hist bins ``[lo, hi]`` (calcWork count half)."""
    lo_i = max(int(lo), 0)
    hi_i = min(int(hi), len(hist) - 1)
    if hi_i < lo_i:
        return 0
    return int(np.asarray(hist[lo_i : hi_i + 1], dtype=np.int64).sum())


def fugc_work_percent(band: int, total: int) -> float:
    """``100.0 * band / total`` — PakonIMAu.dll @ ``0x101f9094`` / ``0x1059bea8``."""
    if int(total) == 0:  # PakonIMAu.dll @ 0x101f908e cmp
        return 0.0
    return float(np.float32(F32_WORK_PCT_SCALE * (float(int(band)) / float(int(total)))))  # @ 0x101f9094…


def mode2_apply_lut_plane(
    seed: np.ndarray,
    bias: int,
    n: int = FUGC_N,
) -> np.ndarray:
    """Mode==2 one-plane LUT fill @ ``0x101fc7e6…0x101fc8c6`` (Cap ``+0x6140``).

    Prefix filled with ``seed[0]+bias`` (not bare ``bias``); then
    ``out[i]=seed[i-bias]+bias`` / negative-bias mirror; final clamp
    ``0…n-1``.
    """
    out = np.empty(n, dtype=np.int32)
    ax = int(np.int16(bias))  # PakonIMAu.dll @ 0x101fc7eb
    seed0 = int(np.int16(seed[0])) + ax  # PakonIMAu.dll @ 0x101fc7fa…801
    last = int(np.int16(seed[n - 1])) + ax  # PakonIMAu.dll @ 0x101fc812…81a
    if ax >= 0:  # PakonIMAu.dll @ 0x101fc81d / 0x101fc823
        for i in range(ax):  # @ 0x101fc827…837
            out[i] = seed0
        for i in range(ax, n):  # @ 0x101fc840…85e
            out[i] = int(np.int16(seed[i - ax])) + ax
    else:
        end = ax + n - 1  # PakonIMAu.dll @ 0x101fc860…863
        for i in range(end):  # @ 0x101fc870…88c
            out[i] = int(np.int16(seed[i - ax])) + ax
        for i in range(max(end, 0), n):  # @ 0x101fc890…89c
            out[i] = last
    for i in range(n):  # PakonIMAu.dll @ 0x101fc8a1…8c4 clamp
        v = int(out[i])
        if v < 0:
            out[i] = 0
        elif v > n - 1:
            out[i] = n - 1
    return out


def calc_fugc_metrics_from_hist(
    hist: np.ndarray,
    *,
    bias: int,
    hist_min: int = HIST_MIN_DEFAULT,
    hist_max: int = HIST_MAX_DEFAULT,
    high: tuple[int, int] = HIGH_WORK_RANGE_DEFAULT,
    mid: tuple[int, int] = MID_WORK_RANGE_DEFAULT,
    low: tuple[int, int] = LOW_WORK_RANGE_DEFAULT,
) -> dict[str, object]:
    """Mode==2 metrics compose (thresholds + band % from hist counts)."""
    thr = fugc_work_thresholds(
        bias=bias,
        hist_min=hist_min,
        hist_max=hist_max,
        high=high,
        mid=mid,
        low=low,
    )
    hi_lo, hi_hi, mid_lo, mid_hi, low_lo, low_hi = thr
    c_hi = fugc_band_count(hist, hi_lo, hi_hi)
    c_mid = fugc_band_count(hist, mid_lo, mid_hi)
    c_low = fugc_band_count(hist, low_lo, low_hi)
    total = c_hi + c_mid + c_low
    return {
        "thresholds": thr,
        "counts": (c_hi, c_mid, c_low, total),
        "pct": (
            fugc_work_percent(c_hi, total),
            fugc_work_percent(c_mid, total),
            fugc_work_percent(c_low, total),
        ),
    }


def build_mode2_apply_lut(
    seed_rgb: np.ndarray,
    *,
    a_table_dmin: tuple[int, int, int],
    arg_ebp14: tuple[int, int, int],
    arg_ebp18: tuple[int, int, int],
    cap_params_aim: tuple[int, int, int],
) -> tuple[np.ndarray, int, dict[str, tuple[int, int, int]]]:
    """Mode==2: aims → bias @ ``0x101f79b0`` → plane LUT @ ``0x101fc7e6``.

    Host stacks the Cap ``+0x6140`` plane across RGB for ``apply_1d_lut``.
    """
    aims = fill_setlutinfo_aim_words(
        a_table_dmin=a_table_dmin,
        arg_ebp14=arg_ebp14,
        arg_ebp18=arg_ebp18,
        cap_params_aim=cap_params_aim,
    )
    bias = fugc_work_bias(aims["60ec"], aims["60f8"], arg_ebp14)
    plane = mode2_apply_lut_plane(seed_rgb[:, 0], bias)
    out = np.empty_like(seed_rgb, dtype=np.int32)
    for c in range(3):
        out[:, c] = plane
    return out, bias, aims


def main() -> None:
    print("FUGC (PakonIMAu.dll base 0x10000000)")
    print(f"  setLutInfo {IMPL_SET_LUT_INFO:#010x}  analyze {IMPL_ANALYZE:#010x}")
    print(
        f"  ANALYZE_PORTED={FUGC_ANALYZE_PORTED} "
        f"AIM_PROVENANCE={FUGC_AIM_PROVENANCE_PORTED} "
        f"AIM_STORE={FUGC_AIM_STORE_PORTED} "
        f"SET_LUT_INFO={FUGC_SET_LUT_INFO_PORTED}"
    )
    print(
        f"  METRICS={FUGC_METRICS_PORTED} "
        f"HIST={FUGC_GENERATE_HISTOGRAM_PORTED} "
        f"HIST_ROI={FUGC_HIST_COM_ROI_PORTED} "
        f"APPLY_GATE={FUGC_APPLY_LUT_GATE_PORTED} "
        f"BIAS={FUGC_WORK_BIAS_PORTED} "
        f"MODE2_LUT={FUGC_MODE2_LUT_PORTED}"
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
    bias = fugc_work_bias(aims["60ec"], aims["60f8"], (100, 200, 300))
    thr = fugc_work_thresholds(
        bias=bias,
        hist_min=HIST_MIN_DEFAULT,
        hist_max=HIST_MAX_DEFAULT,
        high=HIGH_WORK_RANGE_DEFAULT,
        mid=MID_WORK_RANGE_DEFAULT,
        low=LOW_WORK_RANGE_DEFAULT,
    )
    print(f"  example bias={bias} thresholds={thr}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
