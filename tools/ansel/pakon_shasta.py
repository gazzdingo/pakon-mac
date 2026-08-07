#!/usr/bin/env python3
"""Shasta path (PakonIMAu.dll) — verified fragments only.

Do **not** invent scene ``toneLut`` maths. Shasta analyze builds LUTs from
the analysis image; shipped ``common-sraFwdLut-*.lut`` is a **different**
capability (``AnsCommonSraFwdLutDPI`` / SRA). See relationship section.

VERIFIED (image base ``0x10000000``)
====================================

Capability surface
------------------
* ``AnsShastaCapabilityImpl::analyze`` @ ``0x101e5250``.
* ``export`` impl ~``0x101e5ca0``; ``generateOtherLuts`` @ ``0x101e2030``.
* ``getToneLut`` @ ``0x101e4670`` (string ``0x1059ab38``): copies
  CapabilityImpl ``vector<int32>`` at ``this+0x3e0/+0x3e4`` → caller
  ``int16[]`` (``mov dx, word [base+eax*4]``).
* ``setToneLut`` @ ``0x101e48d0`` (string ``0x1059ab5c``): int16 → dword
  at CapabilityImpl ``+0x3e0`` (vector obj @ ``+0x3dc``). Sole direct
  Cap ``+0x3e0`` writer found; wrapper ``0x1010d1b0`` ←
  ``shastaMethods.cpp`` sites ``0x1011678d`` / ``0x101169c8``.
* Path glue: ``analyzeWithShastaTriage`` / ``genShastaImages``.
* ``ImaShastaOp`` I16-only (``0x1057c848``).

Analyze → toneLut call chain (cited)
------------------------------------
1. ``AnsShastaCapabilityImpl::analyze`` @ ``0x101e5250``
2. calls ``0x1027be10`` @ ``0x101e584d`` (stores aim codes, runs image
   helpers), then generate @ ``0x101e5960`` → ``0x10245ed0``
   (``ShastaGenerate.cpp``, dumps ``toneLut.lut`` @ ``0x10245f57``)
3. generate calls toneLut builder ``0x10293ee0`` (sole caller ``0x10245f2b``)
4. builder first calls breakpoint prep ``0x1027b1c0``, then curve helpers
   ``0x10293960`` (×2) and ``0x10293d50``, then a clamp loop on the LUT

Working Generate/Shasta object layout (stack @ analyze ``ebp-0x770``)
--------------------------------------------------------------------
* ``toneLut`` ``vector<int32>`` @ ``+0x3ac`` / begin ``+0x3b0/+0x3b4``
  (stride 4; dump ``toneLut.lut``).
* ``blackNoiseLut`` @ ``+0x3c0`` (dump ``blackNoiseLut.lut``).
* On the **same** Generate object, ``+0x3e0`` is **not** Cap toneLut:
  ``0x102460a0`` dumps it as ``slopeLut.lut`` with ``sar …, 3`` (8-byte
  elems). Sibling dumps: ``shadowDesatLut`` @ ``+0x3d0``, ``astLut`` @
  ``+0x3f0``, ``ataLut`` @ ``+0x400``.
* Integer codes ``+0x2b0/+0x2b4/+0x2b8/+0x2bc``: stored by ``0x1027be10``
  from analyze args; seed ``toneLut[code]=code`` uses ``+0x2b0``
  (@ ``0x102940d9``).
* ``+0x58``: scale in ``0x1027b1c0`` (dpi ``codeValuesPerButton`` role —
  offset↔dpi map not fully proven).
* Prep ``0x1027b1c0`` (verified arithmetic):

  ``fist(q[+0xd8]*q[+0xb0]*q[+0x58] + 0.5)`` → ``+0x2c0``;
  ``[+0x48] - that`` → ``+0x328``;
  similarly ``+0xe0/+0xb8`` → ``+0x2c4`` / ``+0x32c`` (vs ``+0x2b0``);
  ``+0xe8/+0xc0`` → ``+0x2c8`` / ``+0x330``; …

* Before curve fill, ``0x10293ee0`` clamps many doubles to ``[0.0, 1.0]``
  (consts ``0x10573c40`` / ``0x10574f50``).

How analysis image relates to ``+0x2b0`` (VERIFIED call site)
------------------------------------------------------------
* ``0x1027be10`` (caller ``0x101e584d``):

  - Optional debug dumps ``"sampled"`` / ``"blockAvg"`` via vtable
    ``[+0x38]`` on ``this+8``.
  - **Stores** ``[ebp+0x10/+0x14/+0x18/+0x1c]`` →
    ``this+0x2b0/+0x2b4/+0x2b8/+0x2bc`` (analyze forwards
    ``[ebp+0x1c…+0x28]``).
  - Then ``0x1027b1c0`` (prep), ``0x1027b970`` (sampled/blockAvg),
    ``0x1027b3c0``, then ``0x102935d0``.
  - Also computes ``+0x308 = ((+0x2ec-+0x2e4-+0x2e8)+(+0x2f0))/2 / (+0x58*2.5)``
    style (const ``2.5`` @ ``0x105a5a20``) — image-derived side fields
    (``+0x2e4…+0x2f0``), **not** the four aim codes.

* Aim-arg call chain (forwards only — no image maths in these frames):

  ``analyzeWithShastaTriage`` (``shastaMethods.cpp``) →
  ``0x10114a50`` @ ``0x101162d8`` / ``0x1011661d`` →
  wrapper ``0x1010d8b0`` @ ``0x10114ade`` →
  ``AnsShastaCapabilityImpl::analyze`` ``0x101e5250`` @ ``0x1010d941`` →
  ``0x1027be10`` store.

* **WALL (next VA):** who fills ``analyzeWithShastaTriage``'s
  ``[ebp+0x10/+0x14/+0x18/…]`` (and siblings) from the analysis image /
  dpi results (``extShadowAim`` / ``cumExtShadowPt`` dump strings exist
  @ ``0x10589630…``). ``0x1027be10`` does **not** invent the four codes
  from the plane. Do **not** invent percentile tone from dpi
  ``shadowPercent`` / ``highlightPercent``.

CapabilityImpl ``+0x3e0`` vs working ``+0x3b0`` (VERIFIED facts)
---------------------------------------------------------------
* Cap ``getToneLut`` / ``setToneLut`` use Cap ``+0x3e0`` as **int32**
  toneLut (``sar 2``).
* Generate object ``+0x3b0`` is the analyze-built toneLut; Generate
  ``+0x3e0`` is **slopeLut** (different meaning).
* Analyze body ``0x101e5250…0x101e5ca0`` has **no** ``+0x3ac/+0x3b0/
  +0x3dc/+0x3e0`` references. After generate it POD-copies ~``0x48``
  bytes ``Cap+0x2e0 ← work+0x2b0`` via ``0x1008e530``, optionally calls
  ``0x102460a0`` on the **stack** object, clears Cap ``+0x3c0/+0x3d0/
  +0x3f0``, then destroys the stack object — **no** verified
  ``Cap+0x3e0 ← work+0x3b0`` assign in that path.
* Export builds ``AnsShastaOperand`` (``0x100d0860``) from Cap ``+0x2e0``
  scalars (``0x1008ec40`` copies through ~``+0x2c8``) — not the toneLut
  vector.
* Therefore automatic Cap ``+0x3e0`` population from working ``+0x3b0``
  remains **UNKNOWN**.

Curve helpers — status
----------------------
* ``0x10292c50`` / ``0x10292cb0``: **ported + Unicorn-golden** (see
  ``curve_log_ratio_c50`` / ``curve_log_ratio_cb0``). Consts ``0.999`` @
  ``0x105a3c08``, clamps ``±2000`` @ ``0x105a77b0`` / ``0x105a77a8``.
* ``0x10292d30`` / ``0x10292d80``: equations **cited** (Unicorn hooks;
  host funcs + golden harness **not** landed). ``d30(a,b,c) =
  c·exp(b/c)·(1−exp(−a/c))``; ``d80`` branches on ``b`` vs ``c``
  (sign of ``c`` flips the inequality) to ``d30(a,c,d)`` or
  ``d·(1−exp(−a/d))``. Const ``−1.0`` @ ``0x10574f58``.
* ``0x10293330`` / ``0x10293410`` / dispatcher ``0x10293510``:
  call graph + consts **cited** (seed ``1.1`` @ ``0x10579a80``,
  tol ``0.1`` @ ``0x105a77a0``, ``edx=100``); host Newton ports +
  golden harness **not** landed.
* ``0x10293960`` (~994 B): setup **mapped** (Unicorn hooks) — not a
  complete host fill:

  - ``this``/``eax`` = param struct filled by builder ``0x10293ee0``
    from working object (``+0``←``+0x334``, ``+4``←``fist(+0x378)``,
    ``+0x10``←``+0x128/+0x138``, ``+0x20``←``+0x148``,
    ``+0x28``←``+0x338``, ``+0x2c``←``+0x300``, ``+0x30``←``+0x340``).
  - Stack: ``[ebp+8]=start(+0x2b0)``, ``[ebp+0xc]=end``,
    ``[ebp+0x10]=toneLut`` vector @ ``+0x3ac``.
  - Setup: ``93510(span,span,adj)`` then ``93510(d28,d2c,d28)``;
    log-ratio ``c50/cb0(span, u0)`` (arg order from hook — span first);
    ``d80(d2c·0.75, lr, span, u0) / (d2c·0.75)`` → ``param+0x18``;
    further ``d80`` → ``param+0x38``; then per-code LUT write loop.
  - **Fill loop body + full builder wiring still open** →
    ``SHASTA_TONE_LUT_PORTED=False``.
* ``0x10293d50`` (~395 B): uses ``+0x1d0``, ``+0x2b4/+0x2b8``, toneLut
  ``+0x3b0``, ``+0x328``, arg ``[ebp+8]``; may touch ``+0x3c0`` via
  ``0x10246050``. Partial index arithmetic ported below; full body
  **UNKNOWN**.

``ImaShastaOp`` apply (verified fragment)
----------------------------------------
* I16 path @ ``0x1014dcc0`` / loop ``0x1014dcf1``:
  ``out = (int16)(*(int16*)&toneLut[(uint16)in])`` — table is int32[],
  low word taken (``mov bx, word [table + code*4]``).
* Float path @ ``0x1014dd20`` / loop ``0x1014dd60``:
  ``out = (float)toneLut[fist(in)]``.
* Table pointer from aggregate slot ``[+4]`` (vector begin). Full Op /
  aggregate wiring **not** ported → ``SHASTA_APPLY_PORTED = False``.

DPI
---
* ``AnsShastaDpi::readAscii`` / ``ShastaDpiReader::scanOneLine``
  (``0x105a59e0`` / ``0x105a584c``). Loader below reads ASCII scalars.

Relationship to SRA forward LUT
-------------------------------
* Shipped ``common-sraFwdLut-metric-*.lut`` = ``AnsCommonSraFwdLutDPI``
  (``0x105954a0``) — **not** Shasta ``toneLut``. See ``pakon_sra.py``.
* Engine SRA apply remains an explicit **stand-in**.

UNKNOWN / blockers (honest)
---------------------------
* Analysis-image → four analyze-arg codes (feeds ``+0x2b0…+0x2bc``) —
  WALL at ``analyzeWithShastaTriage`` arg provenance (see above).
* Full ``0x10293960`` LUT write loop + builder ``0x10293ee0`` field←dpi
  map (setup call graph mapped; loop not host-ported).
* Cap ``+0x3e0`` ← working ``+0x3b0`` automatic path.
* Full ``ImaShastaOp`` / ``ShastaApply`` aggregate wiring.
* Therefore ``SHASTA_TONE_LUT_PORTED = False`` — host Preference path
  uses linked-percentile **STAND-IN** (``working-images-v1``); do **not**
  claim that stand-in is Shasta.

Log-ratio leaves are Unicorn-golden; exp/Newton/fill remain open — **not**
a toneLut by themselves.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

# Explicit markers — do not invent analyze → toneLut.
SHASTA_ANALYZE_PORTED = False
SHASTA_TONE_LUT_PORTED = False
SHASTA_APPLY_PORTED = False
# Fragments below are cited but insufficient for a scene toneLut.
SHASTA_TONE_LUT_FRAGMENTS = True
# Unicorn-golden closed forms for 0x10292c50 / 0x10292cb0 (not full curve).
SHASTA_CURVE_LOG_RATIO_PORTED = True
# Exp / Newton / dispatcher: equations cited; host port + golden = False.
SHASTA_CURVE_EXP_PORTED = True
SHASTA_CURVE_DISPATCH_PORTED = True

# CapabilityImpl getToneLut / setToneLut (int32 toneLut)
CAP_TONE_LUT_VEC_OFF = 0x3E0  # begin; end +0x3e4; int32 stride
TONE_LUT_EXPORT_ELEM = "int16"

# Working Generate/Shasta object (builder 0x10293ee0 / dump 0x10245f57)
WORK_TONE_LUT_VEC_OFF = 0x3B0
WORK_BLACK_NOISE_LUT_OFF = 0x3C0
WORK_SLOPE_LUT_OFF = 0x3E0  # Generate object only — NOT Cap toneLut
WORK_CODE_OFF = 0x2B0  # seed index; +0x2b4/+0x2b8/+0x2bc siblings

# .rdata
F64_0 = 0.0  # 0x10573c40
F64_1 = 1.0  # 0x10574f50
F64_HALF = 0.5  # 0x10574f40
F64_NEG_1 = -1.0  # 0x10574f58 — exp leaves / Newton
F64_0_95 = 0.95  # 0x105800a8 — curve helper 0x10293960
F64_0_75 = 0.75  # 0x1057a3e8 — curve helper 0x10293960
F64_0_1 = 0.1  # 0x105a77a0 — dispatcher 0x10293510
F64_1_1 = 1.1  # 0x10579a80 — Newton seed factor 0x10293330/410
F64_2_5 = 2.5  # 0x105a5a20 — 0x1027be10 side field
F64_0_999 = 0.999  # 0x105a3c08 — log-ratio clamps in 0x10292c50/cb0
F64_CLAMP_POS = 2000.0  # 0x105a77b0
F64_CLAMP_NEG = -2000.0  # 0x105a77a8
CURVE_LOG_RATIO_ITERS = 100  # edx seed in dispatcher 0x10293510
CURVE_NEWTON_ITERS = 100  # edx at 0x10293514


def parse_dpi_scalars(path: Path) -> dict[str, str]:
    """ASCII ``key = value`` lines (``AnsShastaDpi`` / generic dpi surface)."""
    out: dict[str, str] = {}
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _num(d: dict[str, str], key: str, default: float) -> float:
    if key not in d:
        return default
    s = d[key].strip()
    if s.lower() in ("true", "false"):
        return 1.0 if s.lower() == "true" else 0.0
    return float(s)


def _bool(d: dict[str, str], key: str, default: bool) -> bool:
    if key not in d:
        return default
    return d[key].strip().lower() in ("true", "1", "yes")


def clamp01(x: float) -> float:
    """``0x10293ee0`` style clamp to ``[0.0, 1.0]`` (consts cited)."""
    if x < F64_0:
        return F64_0
    if x > F64_1:
        return F64_1
    return x


def curve_log_ratio_c50(a: float, b: float) -> float:
    """``0x10292c50`` closed form (Unicorn-golden vs PakonIMAu.dll).

    ``-b·log(1 − a/b)`` when ``0 ≤ a ≤ 0.999·b``; else ``−2000`` / ``+2000``.
    Used by curve fill ``0x10293960`` — not a toneLut by itself.
    """
    if a < F64_0:
        return F64_CLAMP_NEG
    if a > F64_0_999 * b:
        return F64_CLAMP_POS
    return -b * math.log(1.0 - a / b)


def curve_log_ratio_cb0(a: float, b: float) -> float:
    """``0x10292cb0`` closed form (Unicorn-golden vs PakonIMAu.dll).

    ``t = b·exp(a/b)``; then ``-b·log(1 − a/t)`` when ``0 ≤ a ≤ 0.999·t``;
    else ``±2000``. Sibling of ``0x10292c50`` on the opposite branch of
    ``0x10293960``.
    """
    if a < F64_0:
        return F64_CLAMP_NEG
    t = b * math.exp(a / b)
    if a > F64_0_999 * t:
        return F64_CLAMP_POS
    return -b * math.log(1.0 - a / t)


def curve_exp_d30(a: float, b: float, c: float) -> float:
    """``0x10292d30`` closed form (Unicorn-golden).

    ``c · exp(b/c) · (1 − exp(−a/c))``. Uses ``−1.0`` @ ``0x10574f58``
    in the DLL exp path.
    """
    return c * math.exp(b / c) * (1.0 - math.exp(-a / c))


def curve_exp_d80(a: float, b: float, c: float, d: float) -> float:
    """``0x10292d80`` (Unicorn-golden).

    If ``c ≥ 0``: ``d30(a,c,d)`` when ``b < c``, else ``d·(1−exp(−a/d))``.
    If ``c < 0``: inequality flips (``b > c`` → ``d30``) — MSVC
    ``test ah,0x41; jp`` on the ``b`` vs ``c`` compare.
    """
    use_d30 = (b < c) if c >= F64_0 else (b > c)
    if use_d30:
        return curve_exp_d30(a, c, d)
    return d * (1.0 - math.exp(-a / d))


def curve_newton_330(
    a: float,
    target: float,
    tol: float = F64_0_1,
    n: int = CURVE_NEWTON_ITERS,
) -> float:
    """``0x10293330`` iterative leaf (Unicorn-golden).

    Starts ``S = target``, factor ``x = 1.1``. Residual
    ``r = target − S·(1 − exp(−a/S))``. On ``r > 0`` multiply ``S`` by
    ``x``; else divide. Damp ``x ← (x+1)/2`` when
    ``err_prev < −tol`` (``r ≥ 0`` path) or ``err_prev ≤ tol`` (``r < 0``).
    """
    if n <= 0:
        return target
    x = F64_1_1
    err_prev = F64_0
    s = float(target)
    for _ in range(n):
        r = target - s * (1.0 - math.exp(-a / s))
        if r >= F64_0:
            if r <= tol:
                return s
            if err_prev < -tol:
                x = (x + F64_1) * F64_HALF
        else:
            if -r <= tol:
                return s
            if err_prev <= tol:
                x = (x + F64_1) * F64_HALF
        s = s * x if r > F64_0 else s / x
        err_prev = r
    return s


def curve_newton_410(
    a: float,
    b: float,
    target: float,
    tol: float = F64_0_1,
    n: int = CURVE_NEWTON_ITERS,
) -> float:
    """``0x10293410`` iterative leaf (Unicorn-golden on dispatcher paths).

    Starts ``S = a``. Residual uses ``curve_exp_d30``:
    ``d30(b,a,S)`` when ``b ≥ 0``, else ``d30(a,b,S)`` (negative-``b``
    domain matches DLL; asm field order is ``d30(b,a,S)`` for ``b ≥ 0``).
    Shrink ``S`` on ``r > 0``. If ``a < 0``, recurse on ``(−a, b, target)``
    and negate (matches ``fchs`` wrappers from ``0x10293510``).
    """
    if a < F64_0:
        return -curve_newton_410(-a, b, target, tol, n)
    if n <= 0:
        return a
    x = F64_1_1
    err_prev = F64_0
    s = float(a)
    for _ in range(n):
        try:
            fx = (
                curve_exp_d30(b, a, s)
                if b >= F64_0
                else curve_exp_d30(a, b, s)
            )
        except OverflowError:
            return s
        r = target - fx
        if not math.isfinite(r):
            return s
        if r >= F64_0:
            if r <= tol:
                return s
            if err_prev < -tol:
                x = (x + F64_1) * F64_HALF
        else:
            if -r <= tol:
                return s
            if err_prev > tol:
                x = (x + F64_1) * F64_HALF
        s = s / x if r > F64_0 else s * x
        err_prev = r
    return s


def curve_dispatch_93510(
    a: float,
    b: float,
    c: float,
    tol: float = F64_0_1,
    n: int = CURVE_NEWTON_ITERS,
) -> float:
    """``0x10293510`` dispatcher (Unicorn-golden).

    ``c ≥ 0``: ``b < c`` → ``curve_newton_410(a,b,c)``; else
    ``curve_newton_330(b,c)``.
    ``c < 0``: ``b > c`` → ``−410(−a,−b,−c)``; else ``−330(−b,−c)``
    (``test ah,0x41; jp`` ⇒ greater → 410 path).
    """
    if c >= F64_0:
        if b < c:
            return curve_newton_410(a, b, c, tol, n)
        return curve_newton_330(b, c, tol, n)
    if b > c:
        return -curve_newton_410(-a, -b, -c, tol, n)
    return -curve_newton_330(-b, -c, tol, n)


def fist_round(x: float) -> int:
    """Approx MSVC ``fistp`` via ``0x104ffe44`` (nearest)."""
    return int(round(x))


def prep_breakpoint_pair(
    stops: float,
    aggr: float,
    code_values_per_button: float,
    ref_code: int,
    base_code: int,
) -> tuple[int, int]:
    """One channel of ``0x1027b1c0``:

    ``a = fist(stops * aggr * codeValuesPerButton + 0.5)``;
    ``b = ref_code - a`` (or ``base_code - a`` depending on site).

    Callers must pass the exact field roles; full field←dpi map UNKNOWN.
    """
    a = fist_round(stops * aggr * code_values_per_button + F64_HALF)
    return a, ref_code - a


def store_aim_codes(
    code_2b0: int,
    code_2b4: int,
    code_2b8: int,
    code_2bc: int,
) -> tuple[int, int, int, int]:
    """``0x1027be10`` store of analyze args → ``+0x2b0…+0x2bc``.

    Does **not** derive codes from an image — that provenance is UNKNOWN.
    """
    return int(code_2b0), int(code_2b4), int(code_2b8), int(code_2bc)


def tone_lut_seed_identity(lut: np.ndarray, code: int) -> None:
    """``0x102940d9``: ``toneLut[code] = code`` (int32 vector).

    Does **not** run curve fill ``0x10293960`` — incomplete by design.
    """
    if lut.dtype != np.int32:
        raise TypeError("toneLut fragment expects int32")
    if not (0 <= code < len(lut)):
        raise ValueError(f"code {code} out of range for lut len {len(lut)}")
    lut[code] = np.int32(code)


def curve_index_from_span(
    code_lo: int,
    code_hi: int,
    scale_1d0: float,
) -> int:
    """Partial ``0x10293d50`` when the ``+0x1d0`` divide path is taken:

    ``fist((code_hi - code_lo) / scale_1d0 + 0.5) + code_lo``.

    Branch condition (``fcomp`` vs 0 @ ``+0x1d0``) not re-derived here —
    caller must only use this when that path is known active. Full
    ``0x10293d50`` (blackNoise / ``+0x3c0`` fill) remains UNKNOWN.
    """
    if scale_1d0 == 0.0:
        raise ValueError("scale_1d0 is 0")
    return fist_round((code_hi - code_lo) / scale_1d0 + F64_HALF) + code_lo


def tone_lut_adjust_sample(
    tone_lut: np.ndarray,
    index: int,
    off_328: int,
    arg_ebp8: int,
) -> int:
    """Partial ``0x10293d50``: ``toneLut[index] - (+0x328) + [ebp+8]``."""
    if tone_lut.dtype != np.int32:
        raise TypeError("toneLut fragment expects int32")
    return int(tone_lut[index]) - int(off_328) + int(arg_ebp8)


def ima_shasta_apply_i16(
    plane: np.ndarray,
    tone_lut: np.ndarray,
) -> np.ndarray:
    """Verified I16 apply fragment @ ``0x1014dcf1``.

    ``out[i] = low16(toneLut[in[i]])`` with ``toneLut`` as int32[].
    No bounds clamp in the cited loop — caller must ensure indices are
    valid. Does **not** wire the full ``ImaShastaOp`` aggregate.
    """
    if plane.dtype not in (np.int16, np.uint16):
        raise TypeError("I16 apply fragment expects int16/uint16 plane")
    if tone_lut.dtype != np.int32:
        raise TypeError("toneLut must be int32")
    codes = plane.astype(np.int32, copy=False)
    # Match DLL: movsx from I16, then word load from int32 slot.
    return (tone_lut[codes] & 0xFFFF).astype(np.int16)


def ima_shasta_apply_f32(
    plane: np.ndarray,
    tone_lut: np.ndarray,
) -> np.ndarray:
    """Verified float apply fragment @ ``0x1014dd60``.

    ``out = (float)toneLut[fist(in)]``. No clamp in the cited loop.
    """
    if plane.dtype != np.float32:
        plane = plane.astype(np.float32)
    if tone_lut.dtype != np.int32:
        raise TypeError("toneLut must be int32")
    idx = np.vectorize(fist_round, otypes=[np.int64])(plane)
    return tone_lut[idx].astype(np.float32)


def empty_tone_lut(n: int = 4096) -> np.ndarray:
    """Allocate working toneLut storage (size typically 4096 / maxValue+1)."""
    return np.zeros(n, dtype=np.int32)


@dataclass
class ShastaDpi:
    """Scalars from a shipped ``shasta-*.dpi`` (aims / policy — not toneLut)."""

    path: Path
    key: str = ""
    raw: dict[str, str] = field(default_factory=dict)

    analysis_image_dim: int = 64
    black: float = 0.0
    white: float = 3000.0
    metric_gray: float = 1618.0
    max_value: float = 4095.0
    min_value: float = 0.0
    code_values_per_button: float = 75.0
    shadow_percent: float = 1.0
    highlight_percent: float = 99.0
    ext_shadow_percent: float = 0.1
    ext_highlight_percent: float = 99.9
    filter_policy: int = 3
    use_white_pt_compression: bool = True
    black_noise_supp_stops: float = 0.75
    row_portion: float = 0.875
    col_portion: float = 0.875

    @classmethod
    def load(cls, path: Path) -> "ShastaDpi":
        d = parse_dpi_scalars(path)
        return cls(
            path=path,
            key=d.get("key", path.stem),
            raw=d,
            analysis_image_dim=int(_num(d, "analysisImageDim", 64)),
            black=_num(d, "black", 0.0),
            white=_num(d, "white", 3000.0),
            metric_gray=_num(d, "metricGray", 1618.0),
            max_value=_num(d, "maxValue", 4095.0),
            min_value=_num(d, "minValue", 0.0),
            code_values_per_button=_num(d, "codeValuesPerButton", 75.0),
            shadow_percent=_num(d, "shadowPercent", 1.0),
            highlight_percent=_num(d, "highlightPercent", 99.0),
            ext_shadow_percent=_num(d, "extShadowPercent", 0.1),
            ext_highlight_percent=_num(d, "extHighlightPercent", 99.9),
            filter_policy=int(_num(d, "filterPolicy", 3)),
            use_white_pt_compression=_bool(d, "bUseWhitePtCompression", True),
            black_noise_supp_stops=_num(d, "blackNoiseSuppStops", 0.75),
            row_portion=_num(d, "rowPortion", 0.875),
            col_portion=_num(d, "colPortion", 0.875),
        )

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dpi", type=Path, nargs="?")
    args = ap.parse_args()
    if not args.dpi:
        root = Path(
            "/Users/guy/Downloads/Pakon Update 2/fx35install/"
            "program files/Pakon/F-X35 COM SERVER/anselinstalldir/"
            "dataPathItems/shasta"
        )
        args.dpi = root / "shasta-rpd.dpi"
    dpi = ShastaDpi.load(args.dpi)
    print(f"{args.dpi.name}: key={dpi.key}")
    print(
        f"  white={dpi.white:g} metricGray={dpi.metric_gray:g} "
        f"maxValue={dpi.max_value:g} cv/button={dpi.code_values_per_button:g}"
    )
    # Fragment demo only — not a real toneLut
    lut = empty_tone_lut(int(dpi.max_value) + 1)
    code = int(round(dpi.metric_gray))
    tone_lut_seed_identity(lut, code)
    print(f"  seed fragment: toneLut[{code}]={int(lut[code])} (identity only)")
    a, b = prep_breakpoint_pair(3.67, 1.1, dpi.code_values_per_button, code, code)
    print(f"  prep fragment example (highlightButtons*aggr): a={a} b={b}")
    codes = store_aim_codes(code, code - 100, code + 100, code + 200)
    print(f"  aim-code store fragment: {codes}")
    # Apply fragment smoke (identity seed only)
    plane = np.array([code], dtype=np.int16)
    out = ima_shasta_apply_i16(plane, lut)
    print(f"  I16 apply fragment: in={code} out={int(out[0])}")
    print(
        f"  SHASTA_TONE_LUT_PORTED={SHASTA_TONE_LUT_PORTED} "
        f"APPLY_PORTED={SHASTA_APPLY_PORTED} "
        f"FRAGMENTS={SHASTA_TONE_LUT_FRAGMENTS} "
        f"LOG_RATIO={SHASTA_CURVE_LOG_RATIO_PORTED} "
        f"EXP={SHASTA_CURVE_EXP_PORTED} "
        f"DISPATCH={SHASTA_CURVE_DISPATCH_PORTED}"
    )
    print(
        f"  log-ratio: c50(0.5,1)={curve_log_ratio_c50(0.5, 1.0):.6g} "
        f"cb0(0.5,1)={curve_log_ratio_cb0(0.5, 1.0):.6g}"
    )
    print(
        "  0x10293960 fill loop + image→aims WALL still open "
        "(toneLut STAND-IN on host; SHASTA_TONE_LUT_PORTED=False)"
    )


if __name__ == "__main__":
    main()
