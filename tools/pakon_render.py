#!/usr/bin/env python3
"""Parametric per-frame render engine for the Pakon scanning application.

One image per frame. Nothing on this path writes a file the user keeps —
frames are rendered from (capture + parameters) on demand, in memory, and
handed straight to the UI. Only ``export_frame`` writes, and only where the
user asked.

FIDELITY RULE
-------------
The image path adds **nothing** of its own. Every operation here is either a
call into ``pakon_decode`` / ``pakon_ansel`` / ``pakon_color``, or geometry
(rotate / flip / crop) which selects pixels without altering their values.
There is no tone curve, no saturation, no sharpening, no percentile stretch
and no white balance in this file — see ``UNAVAILABLE_CONTROLS`` for the
controls that were dropped for exactly that reason.

``render_frame(..., scale="full")`` with default parameters is intended to be
**byte-for-byte identical** to the corresponding ``frames/NN_srgb.png`` from
``pakon_decode.py strip --color --icc --frames``. ``pakon_render.py verify``
proves it on a real capture and prints the differing pixel count.

What that does and does not establish:

  verified here   the UI introduces zero deviation from the owned pipeline.
  NOT verified    that the owned pipeline equals Kodak's. The Ansel stage is
                  documented by its own authors as a stand-in
                  (``SETSHIFTS_12_PORTED = False``, "full AnsOrder/pcode is
                  NOT ported" — pakon_decode's docstring). Byte equality with
                  PSI/TLB cannot be claimed until that lands, and this module
                  must not be read as claiming it.

Ownership: this module *calls* the colour work in ``tools/pakon_decode.py``
and ``tools/ansel/`` — it does not modify or duplicate it. Stage 2 follows
``Roll.model`` (default ``f135`` = TLB 3×10 poly; ``f235`` = TLA LUT+3×4):

  * ``_rpd16`` (f135) — ``pakon_color.poly_hwc`` (TLB.dll @ 0x1000d880). The
    poly carries its own c9 pedestals; the Auto offset column is unused.
  * ``_rpd16`` (f235) — LUT + 3×4 with an explicit offset column so the UI can
    hold *roll* Dmin fixed while one frame's offsets move (docs/11 §5).
  * ``roll_offsets_from_hist`` — f235 only; f135 returns ``[0,0,0]``.

Pipeline per frame (docs/58; F-135 default):

    capture .bin
      → segment_lines → to_rgb14                     (once, cached as memmap)
      → apply_unit_calibration                       (per frame slice)
      → density LUT + 3x4 matrix + roll offsets + user offsets   → RPD 12-bit
      → AnselEngine.render_scene(roll_scale)         → toned
      → AnselEngine.to_srgb                          → sRGB u8
      → transport unsquash + rot90                   → square pixels
      → user geometry / tone / sharpening            → display or file

Measured on this repo's captures (Apple silicon, 2026-08-07), by
``pakon_render.py check`` on captures/test_nofifo.bin — 694.8 MB, 57 900
lines, 47 frames. Median of nine renders after one warm-up call:

    open capture ........................ ~26 s     (once per roll)
      reading + segmenting + unpacking ...   4.9 s
      caching the rgb14 memmap ..........    1.2 s
      roll histogram and boundaries .....    5.4 s
      per-frame scene balance ...........   20.4 s   <- dominates
    thumb     361 x 250  (1/8) ..........   12 ms
    preview   720 x 500  (1/4) ..........   39 ms
    display  1439 x 1000 (1/2) ..........  147 ms
    full     2878 x 2000 (1/1) ..........  630 ms

Two things follow, and the UI is built on both. A drag runs on the preview
path and settles to *display*, not to full: 39 ms is inside a drag budget and
147 ms is not perceptible on release, whereas 630 ms is. Full quality is an
export-only path and is never rendered interactively.

And an open is 26 seconds, not the 3.5 s this docstring claimed until
2026-08-07 — an error of about 7x that had propagated into the UI as well.
Nearly all of it is the per-frame Ansel scene balance (~0.43 s x 47 frames);
decoding 694 MB is only about 6 s of it. That is why opening shows a real
progress bar with a phase name rather than a spinner.
"""
from __future__ import annotations

import json
import math
import os
import sys
import threading
import time
from contextlib import redirect_stdout
from dataclasses import dataclass, field, asdict
from functools import lru_cache
from io import StringIO
from pathlib import Path

import numpy as np

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent
sys.path.insert(0, str(_TOOLS))
sys.path.insert(0, str(_TOOLS / "ansel" / "python-pipeline"))

import pakon_decode as dec      # noqa: E402  (theirs — call, do not modify)
import pakon_color as pc        # noqa: E402
import pakon_filmstock as film  # noqa: E402
import pakon_framing as pf      # noqa: E402
import pakon_gate as gate       # noqa: E402
import pakon_ansel as ansel     # noqa: E402
import pakon_colour_go as gocol  # noqa: E402  — the colour engine, see below

# --------------------------------------------------------------------------
# parameter model
# --------------------------------------------------------------------------

# Where user corrections enter, and in what unit.
#
# They are applied to the *toned* RPD, after AnselEngine.render_scene and
# before to_srgb. Fallback path: render_scene ends in aim_medians(NBP).
# Preference path: linked_percentile_tone STAND-IN for Shasta toneLut
# (working-images-v1; p1..p99→0..white) — not aim_medians (cancels
# Preference OUT). Corrections stay a single hook before to_srgb.
#
# The unit is the vendor's own: codeValuesPerButton from the shipped Shasta
# DPI file (75.0 for this stock; pakon_shasta.py:236 uses it as
# `a = fist(stops * aggr * codeValuesPerButton + 0.5)`). One UI step is one
# button, exactly as PSI's per-frame density/colour keys worked.
#
# Deliberately NOT expressed in D-units, which is what design/frame.html
# labels them: after the Shasta and FUGC tone LUTs the code values are no
# longer linear in density, so a D conversion here would be invented.
#
# With every offset at zero nothing is added at all, so the default render
# stays byte-for-byte the pipeline's own output.
RPD_PER_DENSITY = pc.LUT_SCALE / 8.0       # 437.5 counts per 1.00 D, pre-Ansel

#: render steps — decimation of both axes before the expensive colour stages.
SCALES = {"thumb": 8, "preview": 4, "display": 2, "full": 1}

DEFAULT_PARAMS: dict = {
    # --- colour: the vendor's per-frame control, in vendor button-steps.
    # PSI exposed exactly this shape (density + three colour offsets) and
    # docs/11 §5 keeps them as offsets on top of the roll balance, never a
    # replacement for it. Nothing else touches pixel values.
    "density": 0.0,       # steps, + is brighter (all three channels)
    "red": 0.0,           # steps, + red / - cyan
    "green": 0.0,         # steps, + green / - magenta
    "blue": 0.0,          # steps, + blue / - yellow
    # --- geometry: selects pixels, never alters them
    "rotate": 0,          # 0 / 90 / 180 / 270, clockwise
    "flip_h": False,
    "flip_v": False,
    "crop": None,         # [x, y, w, h] normalised to the rotated frame
    # --- bookkeeping, not image processing
    "rejected": False,
    "ice": False,         # IR dust removal; needs a 4-channel capture
}

#: Controls drawn in design/frame.html that are deliberately NOT implemented,
#: with the reason. The UI shows them disabled carrying this text rather than
#: silently omitting them or, worse, faking them with an invented curve.
UNAVAILABLE_CONTROLS: list[dict] = [
    {
        "key": "contrast",
        "label": "Contrast",
        "reason": "The vendor's contrast lives in the FUGC LUT selector "
                  "(AnselEngine picks fugc_contrast per film path). Exposing "
                  "it means choosing a different shipped LUT, not applying a "
                  "curve of ours — that selection is not ported yet.",
    },
    {
        "key": "saturation",
        "label": "Saturation",
        "reason": "No saturation operator has been traced in TLB.dll. Adding "
                  "one would put invented processing in the image path.",
    },
    {
        "key": "sharpen",
        "label": "Sharpening",
        "reason": "The vendor sharpens inside Ansel, not as a host-side "
                  "unsharp mask. Not ported; a host-side mask would not match.",
    },
]


def merged_params(p: dict | None) -> dict:
    out = dict(DEFAULT_PARAMS)
    if p:
        for k, v in p.items():
            if k in out:
                out[k] = v
    return out


def is_adjusted(p: dict | None) -> bool:
    """True when the frame carries creative work worth warning about."""
    if not p:
        return False
    m = merged_params(p)
    for k, v in DEFAULT_PARAMS.items():
        if k == "rejected":
            continue
        if k == "crop":
            if m[k] is not None:
                return True
        elif m[k] != v:
            return True
    return False


def describe_params(p: dict | None) -> str:
    """Short human summary for the export queue's Adjustments column."""
    if not is_adjusted(p):
        return "auto"
    m = merged_params(p)
    bits = []
    if m["density"]:
        bits.append(f"density {m['density']:+.2f}")
    for key, lbl in (("red", "R"), ("green", "G"), ("blue", "B")):
        if m[key]:
            bits.append(f"{lbl} {m[key]:+g}")
    if m["ice"]:
        bits.append("ICE")
    if m["rotate"]:
        bits.append(f"{m['rotate']}°")
    if m["flip_h"]:
        bits.append("flip H")
    if m["flip_v"]:
        bits.append("flip V")
    if m["crop"]:
        bits.append("cropped")
    return " · ".join(bits) or "auto"


# --------------------------------------------------------------------------
# cached vendor kernel pieces
# --------------------------------------------------------------------------

_kernel_lock = threading.Lock()
_kernel_cache: dict = {}
_engine_cache: dict = {}


def _quiet(fn, *a, **kw):
    """Run a chatty vendor-port function without polluting the job log."""
    sink = StringIO()
    with redirect_stdout(sink):
        return fn(*a, **kw)


def load_kernel(data_dir: str):
    """F-235 only: (lut, coeff, matrix3x3, template_offset) from vendor files."""
    with _kernel_lock:
        hit = _kernel_cache.get(data_dir)
        if hit is not None:
            return hit
    lut = np.asarray(_quiet(dec.load_true_lut, data_dir), dtype=np.float64)
    mat_path = os.path.join(data_dir, "_ClientColNegMat.txt")
    matrix = pc.load_vendor_matrix(mat_path)
    coeff, template_offset = pc.quantise_matrix(matrix)
    coeff = np.asarray(coeff, dtype=np.float64)
    m33 = np.asarray([[matrix[i][c] for c in range(3)] for i in range(3)],
                     dtype=np.float64)
    val = (lut, coeff, m33, np.asarray(template_offset, dtype=np.float64))
    with _kernel_lock:
        _kernel_cache[data_dir] = val
    return val


def load_poly_coeffs(source: str = "auto", film_class: int = 1):
    """F-135 3×10 matrix for this filmClass.

    ``film_class`` 1/4/8 → NegMatrix (TLB.dll @ 0x1000d880 destination
    ``this+0x50``); 2 → PosMatrix (``this+0xc8``).
    """
    key = ("poly", source, int(film_class))
    with _kernel_lock:
        hit = _kernel_cache.get(key)
        if hit is not None:
            return hit
    coeffs = pc.load_unit_matrix(source, film_class=film_class)
    with _kernel_lock:
        _kernel_cache[key] = coeffs
    return coeffs


def load_engine(ansel_root: str, scene_key: str, scene,
                sba_key: str | None = None) -> "ansel.AnselEngine":
    key = (ansel_root, scene_key)
    with _kernel_lock:
        hit = _engine_cache.get(key)
        if hit is not None:
            return hit
    try:
        eng = _quiet(ansel.AnselEngine.load, ansel_root, scene=scene,
                     sba_key_override=sba_key)
    except TypeError:
        # older signature without sba_key_override
        eng = _quiet(ansel.AnselEngine.load, ansel_root, scene=scene)
    with _kernel_lock:
        _engine_cache[key] = eng
    return eng


def _p99_linear(hist: np.ndarray, total: int) -> float:
    """numpy's ``percentile(x, 99, method='linear')`` from an exact histogram.

    Inputs are 14-bit integers, so a 16384-bin histogram loses nothing. This
    lets the roll Dmin be taken over the *whole* strip — matching what
    ``pakon_decode.cmd_strip`` does when it calls ``render_rpd`` once on the
    full array — without ever holding the full array in memory.
    """
    if total <= 0:
        return 0.0
    virt = 0.99 * (total - 1)
    lo_i, hi_i = int(np.floor(virt)), int(np.ceil(virt))
    cum = np.cumsum(hist)
    v_lo = float(np.searchsorted(cum, lo_i + 1))
    v_hi = float(np.searchsorted(cum, hi_i + 1))
    return v_lo + (virt - lo_i) * (v_hi - v_lo)


def roll_offsets_from_hist(hist: np.ndarray, total: int,
                           data_dir: str,
                           model: str = pc.DEFAULT_MODEL) -> np.ndarray:
    """F-235 Auto column: offset = -(M3x3 · Dmin)/8. F-135: zeros (poly c9).

    Same expression as ``pakon_decode.render_rpd(offsets="dmin", model=f235)``;
    taken once per roll and held fixed while a frame's offsets move.
    """
    if model == "f135":
        # TLB.dll @ 0x1000d880 — pedestal is poly c9; no separate Auto column
        return np.zeros(3, dtype=np.float64)
    lut, _coeff, m33, _tmpl = load_kernel(data_dir)
    dmin = np.array(
        [float(lut[int(_p99_linear(hist[c], total)) & 0x3FFF]) for c in range(3)],
        dtype=np.float64)
    return -(m33 @ dmin) / 8.0


def _rpd16(rgb14: np.ndarray, data_dir: str, offset: np.ndarray,
           model: str = pc.DEFAULT_MODEL,
           film_class: int = 1) -> np.ndarray:
    """14-bit → 16-bit-scaled 12-bit RPD (matches ``pakon_decode.render_rpd``).

    ``film_class`` is ``fcn.1000d880``'s matrix dispatch; it comes from the
    roll's film path via ``pakon_color.film_class_for_path``.
    """
    if model == "f135":
        # TLB.dll @ 0x1000d880 — F-135 ColNeg stage 2
        dec.check_film_class(film_class, model)
        coeffs = load_poly_coeffs(film_class=film_class)
        rpd12 = pc.poly_hwc(rgb14, coeffs, film_class=film_class)
        rpd_max = pc.RPD_MAX_BY_MODEL["f135"]
        # rint, not truncate — same expression as pakon_decode.render_rpd.
        return np.rint(rpd12 * (65535.0 / rpd_max)).astype(np.uint16)

    lut, coeff, _m33, _t = load_kernel(data_dir)
    idx = rgb14.astype(np.int32) & 0x3FFF
    d = lut[idx].astype(np.float64)
    acc = np.einsum("...c,ic->...i", d, coeff) / (pc.COEFF_FIXED * 8.0)
    rpd = np.clip(np.rint(acc + np.asarray(offset, dtype=np.float64)),
                  0, pc.RPD_MAX)
    return (rpd * (65535.0 / pc.RPD_MAX)).astype(np.uint16)


@lru_cache(maxsize=4)
def _rpd16_code_fold(model: str) -> np.ndarray:
    """u16 RPD → the 12-bit code ``pakon_decode._film_base_code`` histograms.

    Exactly ``rpd16_to_rpd12`` followed by ``clip(0, 4095).astype(int)``, i.e.
    a truncation, tabulated over the whole u16 domain so a chunk's histogram
    can be folded instead of its pixels converted.
    """
    v = ansel.rpd16_to_rpd12(np.arange(65536, dtype=np.uint16),
                             pc.RPD_MAX_BY_MODEL[model])
    return np.clip(v, 0, 4095).astype(np.intp)


def poly_pedestals() -> tuple[float, float, float]:
    """The polynomial's per-channel c9, the pedestal the F-135 invert removes."""
    c = load_poly_coeffs()
    return (float(c[9]), float(c[19]), float(c[29]))


#: docs/74 §170. The vendor's F-135 inversion, in closed form, as recovered
#: from the real table `fcn.10022a60` applies immediately before PolyPixel.
#:
#:     out = clamp(round(14750 - 3500 * log10(in)), 0, 16383),  out[0] = 16383
#:
#: Verified against the captured table entry-for-entry: max |err| 0.52 codes
#: over all 4095 non-zero indices, i.e. pure rounding. Index 0 is the ceiling
#: clamp because log10(0) is undefined.
VENDOR_INVERT_A = 14750.0
VENDOR_INVERT_B = 3500.0
VENDOR_INVERT_MAX = 16383


#: docs/74 §173.1: `lut_src`'s real range on live frames is 404..11681, and the
#: loop indexes `table + in[i]*4` with a FULL 16-bit `in[i]`. The v42 capture
#: dumped only 4096 entries, so §170 characterised a quarter of the table and
#: §172's first run clipped 22 % of pixels at index 4095 -- an artificial
#: ceiling of the dump, not of the vendor. 16384 covers 11681 with headroom.
VENDOR_INVERT_ENTRIES = 16384


#: The REAL vendor table, captured live (docs/74 §175). 16384 entries covering
#: the full observed index range (lut_src 470..11724). Preferred over the
#: closed form because no closed form is exact -- see the docstring below.
_VENDOR_INVERT_NPY = (Path(__file__).resolve().parent / "ansel" /
                      "python-pipeline" / "vendor_invert_table.npy")
_vendor_lut_cache: np.ndarray | None = None


def _vendor_invert_lut(n: int = VENDOR_INVERT_ENTRIES) -> np.ndarray:
    """The vendor's inversion table, real if available, closed form otherwise.

    THE REAL TABLE IS PREFERRED, and the reason is measured. Against the full
    16384-entry capture the closed form `round(14750 - 3500*log10(i))` is exact
    on only 14329/16384 (87.5 %), max |err| 1, and the error is ALWAYS +1 --
    never -1 -- uniformly ~12 % in every index decade. A fine search over
    A in 14749.0..14750.5 and B in 3499.6..3500.5 across three rounding modes
    tops out at 16001/16383 (97.7 %, A=14749.9). So the vendor does not compute
    this curve the way this formula does, and byte-exactness cannot come from
    any of them.

    The closed form remains as the fallback: it is within +/-1 everywhere, which
    is what §174's 2.5x MAE improvement rests on, and it extends to indices the
    capture never exercised.
    """
    global _vendor_lut_cache
    if _vendor_lut_cache is None and _VENDOR_INVERT_NPY.is_file():
        try:
            t = np.load(_VENDOR_INVERT_NPY).astype(np.int32)
            if t.size >= 4096:
                _vendor_lut_cache = t
        except Exception:                                  # noqa: BLE001
            _vendor_lut_cache = None
    if _vendor_lut_cache is not None and _vendor_lut_cache.size >= n:
        return _vendor_lut_cache
    idx = np.arange(n, dtype=np.float64)
    out = np.empty(n, dtype=np.int32)
    out[0] = VENDOR_INVERT_MAX
    out[1:] = np.clip(
        np.rint(VENDOR_INVERT_A - VENDOR_INVERT_B * np.log10(idx[1:])),
        0, VENDOR_INVERT_MAX,
    ).astype(np.int32)
    return out


def scene_rpd12(rgb14: np.ndarray, data_dir: str, offset: np.ndarray,
                model: str, eng, film_base=None,
                film_class: int = 1) -> np.ndarray:
    """14-bit block → the RPD12 ``render_scene`` expects. Stage 2 + F-135 invert.

    THE WHOLE POINT OF THIS FUNCTION is that the F-135 inversion is not
    optional and not somebody else's job. ``pakon_decode.cmd_strip`` runs it
    between stage 2 and Ansel; anything else that renders a frame has to run it
    too, or it emits the negative. There is nothing downstream that would
    notice: ``apply_correction`` is additive and ``render_scene``'s
    ``setshifts_out`` branch has no polarity-changing LUT, so a missing
    inversion is silent all the way to the exported file.

    ``film_base`` is the roll's, not this block's — see
    ``pakon_decode.f135_rom12_to_rpd12``.
    """
    # docs/74 §170 -- the VENDOR's own F-135 inversion, applied where the
    # vendor applies it: BEFORE stage 2, not after.
    #
    # Recovered from the live table fcn.10022a60 hands to its transfer loop
    # (v42 capture): out = clamp(round(14750 - 3500*log10(in)), 0, 16383),
    # exact to <=0.52 codes over all 4095 entries, R^2 1.00000, one FIXED
    # table for the whole roll. Note what it does NOT contain: no film base,
    # no Dmin, no pedestal (c9), no fpo. This port's own invert has all four
    # and runs after the polynomial instead of before it.
    #
    # The vendor's table is indexed 0..4095 (12-bit) and yields 0..16383
    # (14-bit), which is the domain PolyPixel then reads -- consistent with
    # the measured poly_input_r range (501..7084).
    #
    # Off by default: this changes the architecture of the front of the chain,
    # not a constant, and §170.4 states plainly it is one roll and one capture.
    if model == "f135" and os.environ.get("PAKON_VENDOR_INVERT") == "1":
        # NO >>2 here. That shift was inferred from the v42 dump having 4096
        # entries, i.e. "the index must be 12-bit" -- and §173.1 refutes it:
        # the loop indexes with a full 16-bit `in[i]` and lut_src's real range
        # is 404..11681. The 4096 was the dump's size, not the table's. With
        # the shift in place the index could never exceed 4095 no matter how
        # large the LUT, which is what made §172's clipping caveat look
        # intrinsic when it was an artefact of this line.
        lut = _vendor_invert_lut()
        idx = np.clip(np.asarray(rgb14, dtype=np.int32), 0, lut.size - 1)
        inv = lut[idx].astype(np.uint16)
        rpd16 = _rpd16(inv, data_dir, offset, model=model,
                       film_class=film_class)
        # the log already happened, upstream -- do NOT invert again
        return ansel.rpd16_to_rpd12(rpd16, pc.RPD_MAX_BY_MODEL[model])

    rpd16 = _rpd16(rgb14, data_dir, offset, model=model,
                   film_class=film_class)
    rpd12 = ansel.rpd16_to_rpd12(rpd16, pc.RPD_MAX_BY_MODEL[model])
    if model != "f135":
        return rpd12
    # docs/74 §162/§164: the vendor's data is ALREADY POSITIVE by the time it
    # reaches PolyPixel — signed corr(poly_input_r, vendor render) is +0.92 on
    # 38/38 frames, against -0.93 for the PSI "raw" export — so a chain fed
    # already-inverted input must NOT invert again. Measured end to end on the
    # vendor's own input/output pair (§164.2): skipping the invert beats
    # applying it on every frame, MAE 89.37 -> 24.68, correlation -0.930 ->
    # +0.923.
    #
    # Off by default: this port's OWN captures are genuine negatives and do
    # need the invert. The flag exists for chains fed vendor-domain data, and
    # for measuring the downstream segment in isolation.
    if os.environ.get("PAKON_NO_INVERT") == "1":
        return rpd12
    return dec.f135_rom12_to_rpd12(
        rpd12, poly_pedestals(), eng.sba.fpo, eng.setshifts_out,
        quiet=True, film_base=film_base,
    )


# --------------------------------------------------------------------------
# the roll
# --------------------------------------------------------------------------

@dataclass
class Frame:
    index: int
    a: int
    b: int
    confidence: str = "good"        # good | low
    params: dict = field(default_factory=dict)
    exported: str | None = None

    # --- framing provenance, from pakon_framing's five-phase cascade.
    # The vendor records which pass placed each frame precisely because not
    # all placements are equal, and the operator has to know which to check.
    # "" means the boundary did not come from the cascade at all — it was
    # hand-edited, restored from a sidecar, or found by the legacy detector.
    phase: str = ""                 # LookForNicePictures | ... | "" | manual
    framing_risk: int = 0           # TLXLib.FRAMING_RISK_000: 0 ok, 1 fair, 4 blind
    scan_warning: int = 0           # TLXLib.SCAN_WARNINGS_000 for this frame
    #: docs/74 §43 — pakon_framing.Frame.content_fraction, carried through:
    #: the share of [a, b) the cascade's own binarisation calls real
    #: photographic content rather than interframe gap. None when the
    #: cascade did not fill it in (the exception fallback path, or a roll
    #: opened before this field existed). Purely a diagnostic -- nothing
    #: reads it to change a boundary, an export, or a render.
    content_fraction: float | None = None


@dataclass
class Roll:
    id: str
    name: str
    capture: str                    # absolute path to the .bin (never copied)
    workspace: str                  # this roll's cache dir
    lines: int = 0
    frames: list = field(default_factory=list)
    stock: dict | None = None
    # Film selection. pakon_decode refuses --icc without one of these:
    # "Captures do not carry DX; do not silently assume CN-default." A .bin
    # has no DX in it, so the UI has to ask, and the answer is stored here.
    dx: str | None = None
    film_path: str | None = None      # ColNeg | BnW | POSITIVE | IMPORTED
    sba_key: str | None = None
    sba_default: bool = False
    sync: dict = field(default_factory=dict)
    auto_offsets: list = field(default_factory=list)
    #: F-135 only: the ROLL's clear-film-base code per channel, in the
    #: polynomial's linear 12-bit domain (FindDmin over the whole strip's film
    #: area — ``pakon_decode.film_base_window``, i.e. every frame but not the
    #: leader and not the gate edge outside the vendor's CCD window). The
    #: F-135 inversion anchors on it, and it is a property of the stock, so it
    #: is measured once here rather than per frame — otherwise the same
    #: negative renders differently depending on which frames you export.
    #: Empty means a workspace written before this existed; the inversion then
    #: falls back to the frame's own FindDmin, which is a different (smaller)
    #: population and can move the render. Re-open the capture to refresh it.
    film_base: list = field(default_factory=list)
    roll_scale: list = field(default_factory=list)
    trace: list = field(default_factory=list)
    created: float = 0.0
    data_dir: str = dec.DEFAULT_DATA_DIR
    ansel_root: str = dec.DEFAULT_ANSEL_ROOT
    # Stage-2 family: f135 = TLB 3×10 poly (this scanner); f235 = TLA LUT+3×4.
    model: str = pc.DEFAULT_MODEL
    transport_scale: float = dec.DEFAULT_TRANSPORT_SCALE
    #: how transport_scale was arrived at, in words. Shown in the UI, because
    #: "we do not know the speed" and "the sidecar says 11467" are different
    #: situations and the geometry is only trustworthy in the second.
    transport_source: str = ""
    #: (measured − predicted) frame pitch, as a percentage of predicted. The
    #: only offline check that the recorded speed is the speed the film
    #: actually travelled at. None = not checked (no pitch, or no speed).
    transport_residual_pct: float | None = None
    #: where ``dx`` came from: "typed" (the operator), "board" (the DX sensor
    #: board, via the capture's .dx.json), "sidecar" (recorded by the scan that
    #: made this capture) or "" for none. No screen could tell a typed DX from
    #: a measured one before this existed — Review said "Typed, not read" even
    #: when the value came off the board.
    dx_source: str = ""
    #: Things the owner needs to be told about this roll that are not fatal:
    #: an exposure triad the committed tables are not valid for, a frame pitch
    #: that disagrees with the recorded speed, a DX that did not resolve.
    #: Surfaced in the UI; a silent default is the failure this replaces.
    warnings: list = field(default_factory=list)
    #: pakon_framing's report for this roll: per-phase counts, the acceptance
    #: window, the pitch and where it came from, and the binarisation level.
    framing: dict = field(default_factory=dict)
    #: Operator override for the INFERRED binarisation threshold. None = Otsu.
    ones_threshold: float | None = None
    #: Per-roll multiplier on the committed calibration's gain table. 1.0 (the
    #: default) is the committed calibration, unchanged. Exists for a roll
    #: whose real content pushes past the digital 12-bit ceiling after the
    #: committed gain is applied -- confirmed on 2026-08-11 to be a pure
    #: post-capture amplification effect (the raw 14-bit data itself never
    #: reached the sensor's own ceiling), so backing off the gain in software,
    #: on the capture already in hand, is the correct fix, not a re-scan. Set
    #: once per roll at open time; applied every time ``attach()`` loads the
    #: gain table, so it survives a reload from ``roll.json``.
    gain_scale: float = 1.0

    #: What the Go colour engine's selections resolved to for this roll — the
    #: sba key, the shasta key, which lutMap and which FUGC LUT, the contrast
    #: class, the coefficient source, and the path each came from. Filled on
    #: the first render (``PakonColorOpen``) and shown in the UI, because "the
    #: frame went through some stock's tables" and "the frame went through
    #: NoShift_fugc-generic0225.lut" are different statements and only the
    #: second is checkable. Derived, so it is not serialised: it follows the
    #: film selection and a roll whose stock changes must re-resolve it.
    colour_selection: dict = field(default_factory=dict, repr=False,
                                   compare=False)

    # runtime only
    _rgb: object = field(default=None, repr=False, compare=False)
    _dark: object = field(default=None, repr=False, compare=False)
    _gain: object = field(default=None, repr=False, compare=False)
    _lock: object = field(default_factory=threading.Lock, repr=False,
                          compare=False)

    # -------------------------------------------------------------- storage
    @property
    def cache_path(self) -> Path:
        return Path(self.workspace) / "rgb14.npy"

    #: serialised fields, listed rather than derived — ``asdict`` would try to
    #: deep-copy the memmap and the lock.
    JSON_FIELDS = ("id", "name", "capture", "workspace", "lines", "stock",
                   "dx", "film_path", "sba_key", "sba_default", "sync",
                   "auto_offsets", "film_base", "roll_scale", "trace",
                   "created",
                   "data_dir", "ansel_root", "model", "transport_scale",
                   "transport_source", "transport_residual_pct",
                   "dx_source", "warnings", "framing", "ones_threshold",
                   "gain_scale")

    def to_json(self) -> dict:
        d = {k: getattr(self, k) for k in self.JSON_FIELDS}
        d["frames"] = [asdict(f) for f in self.frames]
        return d

    @classmethod
    def from_json(cls, d: dict) -> "Roll":
        frames = [Frame(**f) for f in d.pop("frames", [])]
        d.pop("_rgb", None)
        known = {f for f in cls.__dataclass_fields__ if not f.startswith("_")}
        r = cls(**{k: v for k, v in d.items() if k in known})
        r.frames = frames
        return r

    # -------------------------------------------------------------- pixels
    def attach(self) -> np.ndarray:
        """Memory-map the cached 14-bit strip (never loads it all at once)."""
        with self._lock:
            if self._rgb is None:
                self._rgb = np.load(self.cache_path, mmap_mode="r")
            if self._dark is None:
                self._dark, self._gain, _ = dec.load_unit_calibration()
                if self.gain_scale != 1.0:
                    self._gain = self._gain * self.gain_scale
        return self._rgb

    def slice14(self, a: int, b: int, step: int = 1) -> np.ndarray:
        """Calibrated 14-bit block for a line range, decimated by `step`."""
        rgb = self.attach()
        a = max(0, min(a, self.lines))
        b = max(a + 1, min(b, self.lines))
        raw = np.asarray(rgb[a:b:step, ::step])
        return dec.apply_unit_calibration(
            raw, self._dark[::step], self._gain[::step])

    def has_film(self) -> bool:
        return bool(self.dx or self.film_path or self.sba_key
                    or self.sba_default)

    def film_class(self) -> int:
        """``fcn.1000d880``'s matrix dispatch for this roll's film path.

        Derived, never stored: it follows the film selection, and a roll whose
        stock changes has to change matrix with it.
        """
        path = (self.stock or {}).get("path") if self.stock else self.film_path
        return pc.film_class_for_path(path)

    def engine(self):
        """Mirrors pakon_decode.cmd_strip's scene construction exactly."""
        if not self.has_film():
            raise ValueError(
                "no film selected. A capture carries no DX, so colour needs "
                "an explicit choice (dx, film_path, sba_key or sba_default) — "
                "pakon_decode refuses to assume CN-default and so does this.")
        sba_key = self.sba_key
        if self.stock:
            scene = ansel.scene_from_filmstock(
                path=self.stock.get("path"),
                dx_part1=self.stock.get("dx_part1"),
                dx_part2=self.stock.get("dx_part2"),
                iso=self.stock.get("iso"),
            )
        elif self.film_path:
            metric = (ansel.maps.METRIC_ROM12 if self.model == "f135"
                      else ansel.maps.METRIC_PD12)
            scene = ansel.scene_from_filmstock(path=self.film_path,
                                               metric=metric)
        else:
            scene = ansel.SceneContext()
        if self.sba_default and not sba_key and not self.stock \
                and not self.film_path:
            sba_key = "ansel-sba-CN-default"
        key = f"{self.dx}|{self.film_path}|{sba_key}|{self.sba_default}"
        eng = load_engine(self.ansel_root, key, scene, sba_key)
        if self.model == "f135":
            # Both of these are what pakon_decode.cmd_strip sets on the F-135
            # branch, and both have to be set wherever a frame is rendered —
            # the engine is shared and cached, so set them on every fetch.
            eng.rpd_max = ansel.SHASTA_MAX
            eng.shasta_stand_in = True
        return eng


# --------------------------------------------------------------------------
# opening a capture
# --------------------------------------------------------------------------

def probe_capture(path: str | Path) -> dict:
    """Cheap facts about a .bin without decoding it."""
    p = Path(path)
    size = p.stat().st_size
    return {
        "path": str(p),
        "name": p.name,
        "bytes": size,
        "mtime": p.stat().st_mtime,
        # 6000 words/line x 2 bytes
        "approx_lines": size // (dec.WORDS_PER_LINE * 2),
    }


def open_capture(path: str | Path, workspace: str | Path, roll_id: str,
                 name: str | None = None, dx: str | None = None,
                 progress=lambda *a: None,
                 data_dir: str | None = None,
                 ansel_root: str | None = None,
                 max_lines: int = 0,
                 film_path: str | None = None,
                 sba_key: str | None = None,
                 sba_default: bool = False,
                 dx_source: str = "",
                 gain_scale: float = 1.0) -> Roll:
    """Decode a capture into the workspace cache and detect its frames.

    Writes exactly one file — ``rgb14.npy`` in the roll's workspace dir — which
    is render cache, deleted with the workspace. The user's photographs are not
    written anywhere by this function.

    ``dx_source`` records where ``dx`` came from — "typed", "board",
    "sidecar" — because a screen cannot otherwise tell a value the operator
    entered from one a sensor read, and those are different claims.
    """
    src = Path(path).resolve()
    ws = Path(workspace) / roll_id
    ws.mkdir(parents=True, exist_ok=True)

    roll = Roll(
        id=roll_id,
        name=name or src.stem,
        capture=str(src),
        workspace=str(ws),
        dx=dx,
        film_path=film_path,
        sba_key=sba_key,
        sba_default=sba_default,
        created=time.time(),
        data_dir=data_dir or dec.DEFAULT_DATA_DIR,
        ansel_root=ansel_root or dec.DEFAULT_ANSEL_ROOT,
        dx_source=(dx_source or ("typed" if dx else "")),
        gain_scale=gain_scale,
    )

    # Resolve the stock first: it decides roll.film_class(), and stage 2 runs
    # below in pass A. Looking it up after the colour work is done is how the
    # film path stops reaching the matrix dispatch.
    #
    # A DX THAT DOES NOT RESOLVE IS AN ERROR, NOT A NULL. This used to be a
    # bare `except Exception: roll.stock = None`, and the client dropped
    # `film_path` whenever a DX was typed — so a mistyped code discarded BOTH
    # the stock and the film path, `has_film()` was still satisfied by the
    # unresolvable string, and the render walked straight through the refusal
    # that exists to stop exactly this and landed on `ansel-sba-CN-default`.
    # The owner's film was rendered as a stock nobody chose, silently.
    if dx:
        try:
            p1, p2 = film.parse_dx(dx)
            s = film.lookup(p1, p2)
            roll.stock = {
                "name": s.name, "manufacturer": s.manufacturer,
                "path": s.path, "iso": s.iso,
                "dx_part1": s.dx_part1, "dx_part2": s.dx_part2,
                "sba_override": s.sba_override,
            }
        except Exception as e:                              # noqa: BLE001
            roll.stock = None
            if not film_path:
                raise ValueError(
                    f"DX {dx!r} does not resolve to a film stock ({e}), and no "
                    f"film path was chosen either. Rendering it anyway would "
                    f"mean falling back to a colour-negative default nobody "
                    f"selected. Correct the DX, or clear it and choose a film "
                    f"path.") from e
            # A film path WAS chosen, so there is something real to render
            # with. Say so loudly rather than silently pretending the DX was
            # never entered.
            roll.dx_source = "unresolved"
            roll.warnings.append(
                f"DX {dx!r} does not resolve to a known film stock ({e}); "
                f"this roll is being rendered as {film_path} instead. The "
                f"stock-specific curves are not being used.")

    # WAS THIS CAPTURE EXPOSED THE WAY THE COMMITTED TABLES ASSUME?
    # `dec.load_unit_calibration` checks the arrays' shape and nothing else,
    # while its own docstring says they are valid only for the exposure triad
    # in calibration/README.json. `attach()` below applies them regardless, so
    # this is the only place the question gets asked. It warns rather than
    # refuses — the owner's photographs must stay reachable — but it warns
    # somewhere a screen can show it.
    roll.warnings.extend(dec.check_capture_exposure(src))

    progress("reading", 0.02, f"reading {src.name}")
    words = dec.load_u16(src)
    markers = int((words & 1).sum())

    progress("segmenting", 0.12, "finding line sync markers")
    lines = _quiet(dec.segment_lines, words)
    n_all = int(lines.shape[0])          # before any truncation
    if max_lines:
        lines = lines[:max_lines]
    n = int(lines.shape[0])
    roll.lines = n
    # docs/45: a clean capture has one marker per line and no short gaps. The
    # last marker never has a full line behind it, hence markers - 1.
    usable = max(1, markers - 1)
    roll.sync = {
        "markers": markers,
        "lines": n_all,
        "losses": max(0, usable - n_all),
        "pct_clean": round(100.0 * n_all / usable, 3),
        "bytes": int(src.stat().st_size),
        "truncated": bool(max_lines and n < n_all),
    }

    # Which lines are really film, for framing's "present" mask -- computed on
    # the RAW wire lines with the same live Gate classifier the scan itself
    # runs, not the broken clear_level-on-calibrated-data path below. Confirmed
    # 2026-08-11: pakon_framing.DEFAULT_CLEAR_LEVEL is a wire-domain constant
    # (~50000 scale), but open_capture()'s own trace_1d/green_1d are the
    # dark/gain-*calibrated* 14-bit domain (~16383 ceiling) -- comparing one
    # against the other means "gate empty" is never detected at all, so every
    # capture "found" zero real frames and blindly tiled the whole thing.
    # pakon_gate.Gate operates on these same raw wire lines, so there is no
    # domain mismatch to have, and it is independently verified: run against
    # real 2026-08-07 reference captures it reproduces the same FILM/CLEAR/DARK
    # split the live scan itself recorded.
    present = None
    try:
        gt = gate.Gate.from_calibration()
        W = gate.WINDOW_LINES
        present = np.zeros(n, dtype=bool)
        for a0 in range(0, n, W):
            b0 = min(n, a0 + W)
            v = gt.classify_lines(lines[a0:b0])
            present[a0:b0] = (v.state == gate.FILM)
    except Exception as e:                                    # noqa: BLE001
        roll.warnings.append(
            f"framing's film-present mask could not be computed from the raw "
            f"gate classifier ({type(e).__name__}: {e}); falling back to the "
            f"calibrated-domain estimate, which is known unreliable")

    progress("unpacking", 0.30, f"{n} lines x {dec.PIXELS_PER_LINE} px")
    rgb = dec.to_rgb14(lines)
    del words, lines

    # Trilinear CCD deskew, on the capture's own (n_lines, ccd) axes and before
    # the cache is written, so every consumer downstream -- frame slicing, the
    # Dmin histogram, the framing traces -- sees registered data. This is the
    # same stage and the same ordering as pakon_decode.cmd_strip; the app went
    # without it, and rendered channel-misregistered frames while the CLI did
    # not. The offsets stay in capture scan lines because nothing has rotated
    # yet -- see ROTATE_180_FOR_LENS in pakon_decode.
    progress("registering", 0.40, "measuring CCD channel offsets")
    ccd_offsets = dec.measure_ccd_line_offsets(rgb)
    rgb = dec.ccd_deskew(rgb, ccd_offsets)
    roll.sync["ccd_deskew"] = [int(v) for v in ccd_offsets]

    progress("caching", 0.45, "writing render cache")
    np.save(roll.cache_path, rgb)
    del rgb
    strip = roll.attach()

    # --- pass A: exact 14-bit histogram + the green plane, in chunks ---
    # Both are taken at FULL resolution because pakon_decode.cmd_strip takes
    # them at full resolution; decimating here would move frame boundaries and
    # the Dmin offsets, and the render would no longer match the pipeline.
    progress("analysing", 0.55, "roll Dmin and frame boundaries")
    hist = np.zeros((3, 1 << 14), dtype=np.int64)
    # The vendor's framing sees per-line scalars and nothing else (docs/53
    # §4.2.1), so these two arrays are the whole of its input. Accumulating
    # them here costs 0.5 MB for a 31k-line roll; the full green plane the old
    # detector needed cost 125 MB.
    trace_1d = np.empty(n, dtype=np.float64)
    green_1d = np.empty(n, dtype=np.float64)
    CH = 4096
    # The F-135 inversion's film base is FindDmin over the WHOLE strip, so its
    # histogram is accumulated in this pass alongside the 14-bit one. Doing it
    # per frame instead would make the same negative render differently
    # depending on which frames were exported.
    #
    # Whole strip, but not every pixel of it: FindDmin only means "the clear
    # film base" over film. dec.film_base_window is the same window
    # pakon_decode measures over — capture columns inside the vendor's CCD
    # aperture, and the lines that are not saturated leader / empty gate. It
    # narrows which PIXELS are film, never which frames, so the measurement
    # stays roll-level.
    lin_hist = (np.zeros((3, 4096), dtype=np.int64)
                if roll.model == "f135" else None)
    # docs/74 §41: the excluded (leader) side of the same per-line
    # saturation test, accumulated the same way as lin_hist. On a roll where
    # genuine clear leader saturates the poly ceiling hard enough that the
    # kept side no longer holds a usable near-Dmin population (docs/74
    # §31.2), this is frequently the only population left with real
    # clear-film information — see dec.film_base_combine.
    lin_hist_excl = (np.zeros((3, 4096), dtype=np.int64)
                     if roll.model == "f135" else None)
    lin_px_excl = 0
    lin_col0 = dec.film_base_col0(roll.capture)
    lin_px = 0
    lin_lines = 0
    fclass = roll.film_class()
    for a0 in range(0, n, CH):
        b0 = min(n, a0 + CH)
        blk = dec.apply_unit_calibration(
            np.asarray(strip[a0:b0]), roll._dark, roll._gain)
        for c in range(3):
            hist[c] += np.bincount(blk[:, :, c].ravel(), minlength=1 << 14)
        if lin_hist is not None:
            # Histogram the U16 and fold it, rather than materialising two f64
            # planes per chunk: the 12-bit code is a pure function of the
            # 16-bit one, so pushing a 65536-bin count through that function
            # is the same answer for a fraction of the memory traffic.
            r16 = _rpd16(blk, roll.data_dir, np.zeros(3),
                         model=roll.model, film_class=fclass)
            fold = _rpd16_code_fold(roll.model)
            # The u16 ceiling folds to 12-bit 4095 and nothing below it does,
            # so the saturation test is the same one dec runs on the 12-bit
            # codes — done here on the u16 to keep the fold's memory win.
            keep = dec.film_base_line_mask(r16, lin_col0, n_bins=1 << 16)
            win = r16[keep][:, lin_col0:]
            lin_px += int(win.shape[0]) * int(win.shape[1])
            lin_lines += int(keep.sum())
            for c in range(3):
                h16 = np.bincount(win[:, :, c].ravel(), minlength=65536)
                lin_hist[c] += np.bincount(
                    fold, weights=h16, minlength=4096).astype(np.int64)
            excl = r16[~keep][:, lin_col0:]
            lin_px_excl += int(excl.shape[0]) * int(excl.shape[1])
            for c in range(3):
                h16e = np.bincount(excl[:, :, c].ravel(), minlength=65536)
                lin_hist_excl[c] += np.bincount(
                    fold, weights=h16e, minlength=4096).astype(np.int64)
            del r16, win, excl
        trace_1d[a0:b0] = blk.mean(axis=(1, 2))
        green_1d[a0:b0] = blk[:, :, 1].mean(axis=1)
        progress("analysing", 0.55 + 0.12 * (b0 / n), f"line {b0} of {n}")
    del blk

    roll.auto_offsets = [float(v) for v in roll_offsets_from_hist(
        hist, n * dec.PIXELS_PER_LINE, roll.data_dir, model=roll.model)]

    if lin_hist is not None:
        # Same walk pakon_decode._film_base_code runs, from the same counts:
        # find_dmin_code_from_hist @ 0x100093f0…0x1000941f, thr = n // 1000.
        thr = ansel.scene_ctx.find_dmin_thr_n_pixels(lin_px)
        enough = (lin_px > 0 and lin_lines
                  >= dec.FILM_BASE_MIN_FILM_FRACTION * max(1, n))
        roll.film_base = [
            float(ansel.scene_ctx.find_dmin_code_from_hist(
                lin_hist[c].tolist(), thr, n_bins=4096))
            for c in range(3)
        ] if enough else [0.0, 0.0, 0.0]
        if enough:
            # docs/74 §41 — extend with the excluded/leader population; never
            # overrides a film-side refusal (dec.film_base_combine returns
            # the kept code unchanged whenever it is already <= 0).
            roll.film_base = [
                float(dec.film_base_combine(
                    roll.film_base[c], lin_hist_excl[c].tolist(),
                    lin_px_excl, n_bins=4096))
                for c in range(3)
            ]
        if any(v <= 0 for v in roll.film_base):
            # 0 is FindDmin's "no valid Dmin" sentinel. Say so here, where the
            # clipped fractions are still to hand; dec.check_film_base is what
            # actually refuses, per frame, at render time. Reaching this now
            # means the FILM clipped, not the leader — the window already
            # excluded that.
            npx = float(lin_px) or 1.0
            pct = [100.0 * float(lin_hist[c][4095]) / npx for c in range(3)]
            why = (f"only {lin_lines} of {n} lines are unsaturated across "
                   f"capture columns {lin_col0}.., which is not a leader on a "
                   f"roll of film but a capture with almost no film in it"
                   if not enough else
                   f"over the film area (columns {lin_col0}.., {lin_lines} of "
                   f"{n} unsaturated lines) {pct[0]:.3f}% / {pct[1]:.3f}% / "
                   f"{pct[2]:.3f}% of pixels are still at the 4095 ceiling, "
                   f"against FindDmin's 0.1% threshold")
            progress("analysing", 0.69,
                     f"WARNING: FindDmin found no film base "
                     f"{[int(v) for v in roll.film_base]} — {why}. Re-scan at "
                     f"a lower gain. Colour frames will refuse to render.")
        del lin_hist, lin_hist_excl

    progress("frames", 0.70, "framing (five-phase cascade)")
    _frame_roll(roll, trace_1d, green_1d, src, present=present)
    del trace_1d, green_1d

    # --- pass B: the Ansel roll pass, at full resolution, one frame at a time
    progress("balance", 0.78, "roll scene balance (Ansel pass 1)")
    eng = roll.engine()
    off = np.asarray(roll.auto_offsets, dtype=np.float64)
    acc = np.zeros(3, dtype=np.float64)
    trace: list[float] = []
    nf = max(1, len(roll.frames))
    # The median roll scale is the AnalyseRoll stand-in, and both
    # AnselEngine.render_strip and render_scene ignore it whenever Preference
    # setShifts are in play — they fight the setShifts R/G/B ratios. Not
    # computing it there is what the pipeline does, and it saves a
    # full-resolution stage-2 pass per frame.
    want_scale = eng.setshifts_out is None
    fb = tuple(roll.film_base) if roll.film_base else None
    for i, f in enumerate(roll.frames):
        seg = roll.slice14(f.a, f.b, 1)
        if want_scale:
            # analyze_roll_scales averages over the scenes it is given, so
            # calling it per scene and averaging here is the same number it
            # would return for the whole list — but bounded to one frame of
            # memory. It sees the same RPD12 render_scene will, inversion and
            # all.
            rpd12 = scene_rpd12(seg, roll.data_dir, off, roll.model, eng,
                                fb, roll.film_class())
            acc += eng.analyze_roll_scales([rpd12])
            del rpd12
        g = float(seg[:, :, 1].mean())
        trace.append(round(-pc.LUT_SCALE * math.log10(max(g, 1.0) / 16383.0)
                           / 1000.0, 4))
        del seg
        progress("balance", 0.78 + 0.20 * ((i + 1) / nf),
                 f"scene {i + 1} of {nf}")
    roll.roll_scale = [float(v) for v in (acc / nf)] if want_scale else []
    roll.trace = trace

    progress("done", 1.0, f"{len(roll.frames)} frames")
    return roll


def _frame_roll(roll: Roll, trace: np.ndarray, green: np.ndarray,
                capture: Path | str | None = None,
                present: np.ndarray | None = None) -> None:
    """Run the vendor's framing cascade and settle the roll's geometry.

    WHY THE CASCADE AND NOT ``dec.find_frames``
    -------------------------------------------
    ``dec.find_frames`` is one brightness-gap pass and its own comment says so.
    Kodak runs five passes and *records which one placed each frame*, because
    the placements are not equally trustworthy and the operator is expected to
    check the weak ones. Its last resort, ``FramingBlindlyPlacePictures``,
    gives up on detection entirely and spaces frames evenly — so wrong
    boundaries are a designed-for outcome here, not an edge case. Carrying the
    phase through to the UI is the whole point: without it every boundary
    looks equally confident and the operator has no idea where to look.

    Order matters. The transport scale wants the measured frame pitch, and the
    pitch comes out of framing, so framing runs first — and framing itself
    prefers its own measurement to the geometry (see
    ``pakon_framing.estimate_pitch``), which makes the dependency one-way.
    """
    n = int(trace.size)
    try:
        frames, report = pf.find_frames_traces(
            trace, green,
            speed=_sidecar_speed(capture),
            ones_threshold=roll.ones_threshold,
            present=present)
    except Exception as e:                                      # noqa: BLE001
        # Never lose a roll to a framing failure: fall back to the single-pass
        # detector on the 1-D trace, and say in the report that we did.
        spans = _fallback_spans(trace)
        roll.frames = [Frame(index=i, a=int(a), b=int(b), phase="fallback")
                       for i, (a, b) in enumerate(spans)]
        roll.framing = {"error": f"{type(e).__name__}: {e}",
                        "detector": "fallback (single-pass gap split)",
                        "total": len(roll.frames)}
        _flag_confidence(roll)
        return

    roll.frames = [Frame(index=i, a=int(f.start), b=int(f.stop),
                         phase=f.phase.vendor_name,
                         framing_risk=f.phase.risk,
                         scan_warning=int(f.phase),
                         content_fraction=f.content_fraction)
                   for i, f in enumerate(frames)]
    report["detector"] = "pakon_framing five-phase cascade"
    # The binarisation level is the one part of the cascade that is not the
    # vendor's (docs/56 §7.4 — untraced). Label it at every layer that shows
    # it, so nobody downstream mistakes it for recovered behaviour.
    report["ones_threshold_inferred"] = roll.ones_threshold is None
    report["ones_threshold_source"] = (
        "operator override" if roll.ones_threshold is not None
        else "Otsu over the film-present region [INFERRED — vendor's rule is "
             "untraced, docs/56 §7.4]")
    roll.framing = report
    _flag_confidence(roll)

    # Geometry, now that a measured pitch exists.
    pitch = report.get("pitch") if report.get("pitch_source") == "measured" else None
    ts, ts_src = dec.resolve_transport_scale(
        capture=capture, measured_pitch_lines=pitch)
    roll.transport_scale = float(ts)
    roll.transport_source = ts_src
    # The recorded speed against the film that actually went past the sensor.
    # resolve_transport_scale computes this and folds it into its prose; as a
    # number a screen can colour it, and a large one means the sidecar and the
    # film disagree about the geometry — which is worth saying out loud,
    # because the sidecar wins and would otherwise do so silently.
    resid = dec.transport_residual_pct(capture=capture,
                                       measured_pitch_lines=pitch)
    roll.transport_residual_pct = resid
    if resid is not None and abs(resid) > dec.TRANSPORT_RESIDUAL_WARN_PCT:
        roll.warnings.append(
            f"the recorded transport speed predicts a frame pitch {resid:+.1f} % "
            f"away from the {pitch:.0f} lines actually measured on this film. "
            f"The recorded speed is being used, so the geometry may be "
            f"stretched or squashed by about that much.")


def _sidecar_speed(capture: Path | str | None) -> float | None:
    """The recorded transport speed, or None. Never raises."""
    if capture is None:
        return None
    try:
        meta = dec.load_capture_sidecar(capture) or {}
        cfg = meta.get("config") if isinstance(meta.get("config"), dict) else {}
        raw = meta.get("speed", cfg.get("speed"))
        return float(raw) if raw is not None else None
    except Exception:                                           # noqa: BLE001
        return None


def _fallback_spans(trace: np.ndarray) -> list[tuple[int, int]]:
    """Last-ditch frame split from the 1-D trace alone.

    Only reached when the cascade itself raises. Deliberately crude: an even
    split of the film-present region at the median run pitch beats returning
    no frames, because a roll with no frames cannot be corrected by hand
    whereas a roll with wrong frames can.
    """
    n = int(trace.size)
    if n < 2:
        return [(0, max(1, n))]
    ones, _ = pf.ones_array(trace)
    runs = [(a, b) for a, b in pf._runs(ones) if b - a >= 200]
    if len(runs) >= 2:
        return runs
    return [(0, n)]


def _flag_confidence(roll: Roll) -> None:
    """Mark boundaries that look wrong so Review can annotate them (amber,
    never modal — design/index.html 'warnings that don't abort').

    Two signals now, and the stronger one wins. The framing phase is a direct
    statement from the detector about how the boundary was arrived at, so a
    frame the cascade extrapolated or placed blind is low-confidence however
    plausible its width is. The width heuristic still runs, because a frame
    can be placed by ``LookForNicePictures`` and still be a merge of two.
    """
    if not roll.frames:
        return
    widths = np.array([f.b - f.a for f in roll.frames], dtype=np.float64)
    med = float(np.median(widths))
    for f in roll.frames:
        w = f.b - f.a
        odd = med > 0 and abs(w - med) / med > 0.22
        f.confidence = "low" if (odd or int(f.framing_risk or 0) > 0) else "good"


# --------------------------------------------------------------------------
# rendering one frame
# --------------------------------------------------------------------------

def _apply_geometry(img: np.ndarray, p: dict) -> np.ndarray:
    rot = int(p.get("rotate") or 0) % 360
    if rot == 90:
        img = np.rot90(img, k=3)
    elif rot == 180:
        img = np.rot90(img, k=2)
    elif rot == 270:
        img = np.rot90(img, k=1)
    if p.get("flip_h"):
        img = img[:, ::-1]
    if p.get("flip_v"):
        img = img[::-1]
    crop = p.get("crop")
    if crop:
        h, w = img.shape[:2]
        x0 = int(round(max(0.0, min(1.0, crop[0])) * w))
        y0 = int(round(max(0.0, min(1.0, crop[1])) * h))
        x1 = int(round(max(0.0, min(1.0, crop[0] + crop[2])) * w))
        y1 = int(round(max(0.0, min(1.0, crop[1] + crop[3])) * h))
        if x1 - x0 >= 8 and y1 - y0 >= 8:
            img = img[y0:y1, x0:x1]
    return np.ascontiguousarray(img)


def correction_steps(p: dict) -> np.ndarray:
    """This frame's user correction, in vendor button-steps, per channel."""
    d = float(p.get("density") or 0.0)
    return np.array([float(p.get("red") or 0.0) + d,
                     float(p.get("green") or 0.0) + d,
                     float(p.get("blue") or 0.0) + d], dtype=np.float64)


def apply_correction(toned: np.ndarray, p: dict, eng) -> np.ndarray:
    """User steps on the toned RPD — after the auto chain, before the ICC hop.

    Returns ``toned`` untouched when every step is zero, which is what keeps
    the default render byte-identical to the pipeline.
    """
    steps = correction_steps(p)
    if not steps.any():
        return toned
    cv = float(getattr(eng.shasta, "code_values_per_button", 75.0))
    return np.clip(toned + (steps * cv).reshape(1, 1, 3), 0, ansel.SHASTA_MAX)


# --------------------------------------------------------------------------
# which colour engine
# --------------------------------------------------------------------------
#
# THE APP RENDERS THROUGH GO. Everything from the stage-2 polynomial onward —
# the F-135 inversion, SBA/balance, Shasta, FUGC, the ICC hop — is
# tools/ansel/pipeline, reached through a c-shared dylib by ctypes
# (tools/pakon_colour_go.py). This module keeps capture, calibration, CCD
# deskew, framing, frame slicing, transport geometry, the parameter model and
# every metadata refusal; it no longer owns any colour arithmetic.
#
# THE PYTHON COLOUR CHAIN IS DEPRECATED — present, working, and off. It is
# reached only by setting PAKON_COLOUR_ENGINE=python, which warns. It is kept
# rather than deleted for three reasons, in order: the Go engine is being
# actively corrected right now; the parity harness that would prove Go correct
# is only just being built; and there has to be a way back if Go regresses in
# the middle of a scanning session. It is not a place to add features — see
# the deprecation notice at the top of
# tools/ansel/python-pipeline/pakon_ansel.py.

COLOUR_ENGINE_ENV = "PAKON_COLOUR_ENGINE"

#: The three choices docs/62 §4.2 says must be explicit. They are stated here,
#: once, with the reason, rather than defaulted anywhere down the chain.
#:
#: coeffSource — docs/62 §2.11. "auto" is not a legal answer: the EEPROM is
#:   the higher-precision calibration store and the registry is what TLB
#:   actually read after its "%f" round-trip, and they differ by 14-57 RPD
#:   codes at (4000,4000,4000). eeprom is what this tree renders today
#:   (pakon_color.REGISTRY_PATH does not exist here, so "auto" already falls
#:   through to it); saying so out loud changes no pixel and removes the
#:   silent disagreement.
#: stageOrder — fugc-shasta, the vendor's, established from PakonIMAu.dll's
#:   AnsImaBuilder::getImaTransformGroup / AnsCnPremiumPath::exportParameterPack
#:   by the phase-1 work; see request.go:OrderFugcShasta. This is NOT the order
#:   pakon_ansel.render_scene uses, so it is a deliberate visible change.
#: iccInput — u12. The RPD-side profile's mft2 input table has 4096 entries;
#:   Python reaches 256 of them only because PIL has no 16-bit RGB mode.
COLOUR_DEFAULTS = {
    "coeffSource": os.environ.get("PAKON_COEFF_SOURCE") or "eeprom",
    "stageOrder": os.environ.get("PAKON_STAGE_ORDER") or "fugc-shasta",
    "iccInput": os.environ.get("PAKON_ICC_INPUT") or "u12",
}


def colour_engine() -> str:
    """``"go"`` (the product) or ``"python"`` (deprecated, explicit only)."""
    want = (os.environ.get(COLOUR_ENGINE_ENV) or "go").strip().lower()
    if want not in ("go", "python"):
        raise ValueError(
            f"{COLOUR_ENGINE_ENV}={want!r} is not 'go' or 'python'. There is "
            f"no third engine and no automatic choice: an engine that picks "
            f"itself is one you cannot attribute an image to.")
    return want


def _resolved_film_path(roll: Roll) -> str:
    """The roll's film path, resolved — not "one of four fields was truthy".

    ``Roll.has_film`` accepts a DX, a film path, an SBA key or the CN default,
    which was enough for the Python chain because ``scene_from_filmstock``
    could fall back. It is not enough now: ``check_film_class`` needs the
    actual path, ``filmPath`` has no wildcard cell in any vendor selector, and
    docs/62 §4.4 says the contract needs the resolved value. So this refuses in
    prose rather than letting Go refuse in Go's words.
    """
    path = (roll.stock or {}).get("path") if roll.stock else None
    path = path or roll.film_path
    if not path:
        raise ValueError(
            "no film path. The colour chain dispatches stage 2 on the film "
            "class (ColNeg / BnW / IMPORTED / POSITIVE) and there is no "
            "wildcard for it in any vendor selector, so it cannot be guessed "
            "from an SBA key or the CN default alone. Choose the film for "
            "this roll.")
    return str(path)


@lru_cache(maxsize=8)
def _code_values_per_button(dpi_path: str) -> float:
    """The vendor's button unit, from the Shasta DPI Go selected.

    The parameter model stays here (docs/62 §9) but the *selection* is Go's
    now, so the file is named by ``PakonColorOpen``'s resolved map and only
    read here. 75.0 is this stock's value and the documented fallback.
    """
    try:
        with open(dpi_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                k, _, v = line.partition("=")
                if k.strip() == "codeValuesPerButton":
                    return float(v.split("#")[0].strip())
    except Exception:                                           # noqa: BLE001
        pass
    return 75.0


def _go_request(roll: Roll, p: dict) -> "gocol.ColourRequest":
    """Everything that is not pixels, as the Go engine's request. docs/62 §4."""
    film_path = _resolved_film_path(roll)
    stock = roll.stock or {}
    dx1, dx2 = -1, -1
    if stock.get("dx_part1") is not None:
        dx1 = int(stock["dx_part1"])
        dx2 = int(stock.get("dx_part2") if stock.get("dx_part2") is not None else -1)
    elif roll.dx:
        parts = str(roll.dx).split("-")
        try:
            dx1 = int(parts[0])
            dx2 = int(parts[1]) if len(parts) > 1 else -1
        except ValueError:
            dx1, dx2 = -1, -1

    base = tuple(int(v) for v in (roll.film_base or ()))
    if len(base) != 3:
        # 0 is FindDmin's "no valid Dmin" sentinel, and the Go side refuses it
        # by name with the clipping numbers. Passing zeros rather than
        # inventing a base is what makes that refusal happen.
        base = (0, 0, 0)

    req = gocol.ColourRequest(
        model=roll.model,
        dxPart1=dx1, dxPart2=dx2,
        iso=int(stock.get("iso") or 0),
        filmPath=film_path,
        anselPath=ansel.maps.PATH_TO_ANSEL.get(film_path, "CN-Premium"),
        sourceType=1,
        sbaKeyOverride=roll.sba_key or "",
        coeffSource=COLOUR_DEFAULTS["coeffSource"],
        coeffPath=pc.EEPROM_PATH if COLOUR_DEFAULTS["coeffSource"] == "eeprom"
        else pc.REGISTRY_PATH,
        filmBase=base,
        stageOrder=COLOUR_DEFAULTS["stageOrder"],
        iccInput=COLOUR_DEFAULTS["iccInput"],
        fugcMode=1,
        # Python has already done both: the deskew is carried in the rgb14
        # cache and the lens 180° is applied by pakon_decode. Doing either
        # again would be worse than not at all.
        ccdDeskew=(0, 0, 0),
        rotate180=False,
        provenance={
            "dx": "roll.stock" if stock.get("dx_part1") is not None else "roll.dx",
            "filmPath": "roll.stock" if (roll.stock or {}).get("path") else "roll.film_path",
            "filmBase": "roll (FindDmin over the whole strip's film area)",
            "coeffSource": "pakon_render.COLOUR_DEFAULTS",
        },
    )

    # The operator's correction. The button model, the step semantics and the
    # decision that zero means "add nothing" all stay here; what crosses is
    # three resolved RPD-code offsets, applied by Go at the same seam
    # apply_correction uses.
    steps = correction_steps(p)
    if steps.any():
        sel = roll.colour_selection or {}
        cv = _code_values_per_button(sel.get("shastaFile", ""))
        req.userOffsets = tuple(float(v) for v in steps * cv)
    return req


def _render_colour_go(roll: Roll, seg: np.ndarray, p: dict) -> np.ndarray:
    """Calibrated 14-bit frame -> sRGB, through the Go engine."""
    req = _go_request(roll, p)
    if not roll.colour_selection:
        # Once per roll: warms the tables and records which stock's sba /
        # shasta / fugc files this roll's frames actually go through, so the
        # app can show it rather than asking the operator to trust it.
        roll.colour_selection = gocol.open_selection(req)
        if correction_steps(p).any():
            # The button unit comes from the Shasta DPI the selection just
            # named, so a corrected frame has to be re-described once.
            req = _go_request(roll, p)
    return gocol.render(seg, req)


def _render_colour_python(roll: Roll, seg: np.ndarray, p: dict) -> np.ndarray:
    """DEPRECATED. The Python colour chain, behind PAKON_COLOUR_ENGINE=python.

    Kept working, and kept off. See the block above ``colour_engine``.
    """
    import warnings
    warnings.warn(
        "The Python colour chain is deprecated: the app renders through the "
        "Go engine (tools/ansel/pipeline). This path is reached only because "
        f"{COLOUR_ENGINE_ENV}=python is set. It is kept so there is a way "
        "back if Go regresses mid-scan, and it must not gain features — fix "
        "colour in Go. See docs/62 §12.",
        DeprecationWarning, stacklevel=2)
    eng = roll.engine()
    # scene_rpd12, not _rpd16 alone: on F-135 stage 2 leaves the frame a
    # NEGATIVE and the inversion happens here. Everything after this point is
    # additive or a tone LUT and would export the negative without complaint.
    rpd12 = scene_rpd12(
        seg, roll.data_dir,
        np.asarray(roll.auto_offsets, dtype=np.float64),
        roll.model, eng,
        tuple(roll.film_base) if roll.film_base else None,
        roll.film_class(),
    )
    scale_v = (np.asarray(roll.roll_scale, dtype=np.float64)
               if roll.roll_scale else None)
    toned = _quiet(eng.render_scene, rpd12, scale_v)
    toned = apply_correction(toned, p, eng)
    return _quiet(eng.to_srgb, toned)


def render_frame(roll: Roll, index: int, params: dict | None = None,
                 scale: str = "preview",
                 max_edge: int | None = None) -> np.ndarray:
    """(capture + parameters) -> one sRGB image. No files, no intermediates.

    The colour stages run in Go (docs/62 phase 2). The 14-bit frame slice
    crosses in memory, on the capture's own grid — before ``unsquash_transport``
    and before ``rot90`` — and sRGB comes back; nothing is written on the way.
    """
    if index < 0 or index >= len(roll.frames):
        raise IndexError(f"frame {index} of {len(roll.frames)}")
    f = roll.frames[index]
    p = merged_params(params if params is not None else f.params)
    step = SCALES.get(scale, 4)

    seg = roll.slice14(f.a, f.b, step)
    if colour_engine() == "python":
        srgb = _render_colour_python(roll, seg, p)
    else:
        srgb = _render_colour_go(roll, seg, p)

    img = dec.to_frame_image(srgb, roll.transport_scale)
    img = _apply_geometry(img, p)

    b = float(p.get("brightness", 100)) / 100.0
    c = float(p.get("contrast", 100)) / 100.0
    s = float(p.get("saturation", 100)) / 100.0
    sh = float(p.get("sharpening", 0)) / 100.0
    
    if b != 1.0 or c != 1.0 or s != 1.0 or sh > 0.0:
        from PIL import Image, ImageEnhance, ImageFilter
        im = Image.fromarray(img, "RGB")
        if b != 1.0:
            im = ImageEnhance.Brightness(im).enhance(b)
        if c != 1.0:
            im = ImageEnhance.Contrast(im).enhance(c)
        if s != 1.0:
            im = ImageEnhance.Color(im).enhance(s)
        if sh > 0.0:
            im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=sh * 150, threshold=3))
        img = np.asarray(im, dtype=np.uint8)

    if max_edge:
        h, w = img.shape[:2]
        if max(h, w) > max_edge:
            from PIL import Image
            r = max_edge / float(max(h, w))
            img = np.asarray(
                Image.fromarray(img, "RGB").resize(
                    (max(1, int(w * r)), max(1, int(h * r))),
                    Image.Resampling.LANCZOS),
                dtype=np.uint8)
    return img


def frame_histogram(roll: Roll, index: int, params: dict | None = None) -> dict:
    """RGB histogram of the 14-bit source plus the facts frame.html shows."""
    f = roll.frames[index]
    seg = roll.slice14(f.a, f.b, 4)
    hist = {}
    for c, name in enumerate("rgb"):
        h, _ = np.histogram(seg[:, :, c], bins=64, range=(0, dec.RAW14_MAX))
        hist[name] = [int(v) for v in h]
    dmin = [float(np.percentile(seg[:, :, c], 99.0)) for c in range(3)]
    clipped = float((seg >= dec.RAW14_MAX - 1).mean() * 100.0)
    # Both ends, because the review plot reports both. On a negative the
    # "shadow" end of the *source* is the film's own base+fog floor, so this
    # is the count of samples that hit the sensor's bottom code, not a
    # statement about the print.
    floored = float((seg <= 1).mean() * 100.0)
    return {
        "hist": hist,
        "dmin": [round(v, 1) for v in dmin],
        "clipped_pct": round(clipped, 3),
        "clipped_shadow_pct": round(floored, 3),
        "lines": [f.a, f.b],
    }


# --------------------------------------------------------------------------
# encoding / export — the only writes the user keeps
# --------------------------------------------------------------------------

def encode(img: np.ndarray, fmt: str = "JPEG", quality: int = 88) -> bytes:
    from io import BytesIO
    from PIL import Image
    bio = BytesIO()
    Image.fromarray(img, "RGB").save(bio, fmt, quality=quality)
    return bio.getvalue()


def render_name(template: str, roll: Roll, index: int, ext: str) -> str:
    f = roll.frames[index]
    stock = (roll.stock or {}).get("name", "")
    slug = "".join(ch for ch in stock.lower().replace(" ", "")
                   if ch.isalnum()) or "film"
    fields = {
        "roll": roll.name.replace(" ", ""),
        "frame": index + 1,
        "stock": slug,
        "date": time.strftime("%Y-%m-%d", time.localtime(roll.created or time.time())),
        "iso": (roll.stock or {}).get("iso") or "",
        "count": len(roll.frames),
        "lines": f.b - f.a,
    }
    try:
        name = template.format(**fields)
    except (KeyError, ValueError, IndexError):
        name = f"{fields['roll']}_{index + 1:02d}"
    name = "".join(c for c in name if c not in '/\\:*?"<>|').strip() or "frame"
    return f"{name}.{ext}"


#: Which (format, colour) pairs can honestly carry more than 8 bits.
#:
#: The sRGB path ends in ``AnselEngine.to_srgb``, which calls
#: ``rpd12_to_icc_u8`` and runs the ICC transform on 8-bit RGB. Its output
#: therefore *is* 8-bit. Writing it into a 16-bit container by replicating
#: bytes would advertise depth that does not exist, so 16-bit is offered only
#: on the Linear/RPD path, which is genuinely 16-bit all the way through this
#: port's own pipeline. That is not a claim that the real vendor software
#: ever wrote a 16-bit file of its own — it measurably did not, even on this
#: same stage (see the "Save As Raw" comment in ``export_frame`` below for the
#: real vendor file this was checked against).
def depth_options(colour: str) -> list[int]:
    return [16, 8] if colour == "linear" else [8]


#: What to do when the file an export would write already exists.
#:
#: There used to be no such policy: export opened the path and wrote. A second
#: export of the same roll silently replaced the first, and — worse, because it
#: is invisible in the destination folder — any two frames whose template
#: renders to the same name overwrote each other *within a single export*, so a
#: 24-frame roll could quietly produce one file.
#:
#: "overwrite" stays available because replacing your own earlier export after
#: a re-grade is a real and common intention. It is just no longer the only
#: behaviour, and never the unasked-for one: the app plans the whole export
#: first, and will not start one that would destroy a file without being told
#: which of these to do.
ON_EXIST = ("ask", "skip", "overwrite", "unique")


def export_path(roll: Roll, index: int, dest: Path, fmt: str,
                colour: str, template: str) -> Path:
    """Where ``export_frame`` would write. Pure — touches no file."""
    ext = {"tiff": "tif", "jpeg": "jpg", "png": "png"}.get(fmt, "tif")
    out = dest / render_name(template, roll, index, ext)
    return out.with_suffix(".tif") if colour == "linear" else out


def unique_path(out: Path, taken: set | None = None) -> Path:
    """``name.tif`` → ``name-2.tif`` → ``name-3.tif``, first one free."""
    taken = taken or set()
    if not out.exists() and out not in taken:
        return out
    stem, suffix, parent = out.stem, out.suffix, out.parent
    n = 2
    while True:
        cand = parent / f"{stem}-{n}{suffix}"
        if not cand.exists() and cand not in taken:
            return cand
        n += 1


def plan_export(roll: Roll, indexes: list[int], dest: Path, fmt: str = "tiff",
                colour: str = "linear",
                template: str = "{roll}_{frame:02}_{stock}",
                on_exist: str = "ask") -> dict:
    """Work out every path this export would write, before writing any.

    Returns the plan plus the two kinds of collision, separately, because they
    need different words in the UI: ``existing`` is "you will replace files
    you already have", ``duplicates`` is "your filename template does not
    distinguish these frames and they will replace each other".
    """
    if on_exist not in ON_EXIST:
        raise ValueError(f"on_exist must be one of {ON_EXIST}")
    items, existing, duplicates = [], [], []
    seen: dict[Path, int] = {}
    taken: set = set()
    for i in indexes:
        out = export_path(roll, i, dest, fmt, colour, template)
        dup_of = seen.get(out)
        exists = out.exists()
        action = "write"
        if dup_of is not None or exists:
            if on_exist == "unique":
                out = unique_path(out, taken)
                action = "write"
            elif on_exist == "skip":
                action = "skip"
            elif on_exist == "overwrite":
                action = "overwrite"
            else:
                action = "blocked"
        if dup_of is not None:
            duplicates.append({"frame": i, "collides_with": dup_of,
                               "path": str(out)})
        elif exists:
            existing.append({"frame": i, "path": str(out),
                             "bytes": out.stat().st_size})
        seen.setdefault(out, i)
        taken.add(out)
        items.append({"frame": i, "path": str(out), "action": action,
                      "exists": exists, "duplicate_of": dup_of})
    return {
        "dest": str(dest),
        "items": items,
        "existing": existing,
        "duplicates": duplicates,
        "on_exist": on_exist,
        "needs_confirm": bool((existing or duplicates) and on_exist == "ask"),
        "will_write": sum(1 for it in items if it["action"] != "blocked"
                          and it["action"] != "skip"),
        "will_skip": sum(1 for it in items if it["action"] == "skip"),
    }


def export_frame(roll: Roll, index: int, dest: Path, fmt: str = "tiff",
                 depth: int = 16, colour: str = "linear",
                 template: str = "{roll}_{frame:02}_{stock}",
                 out: Path | None = None) -> dict:
    """Render at full quality and write one file — the only act that keeps a
    file (design/index.html: 'Export is the only moment files are written').

    The bytes written are the pipeline's output with nothing added. The only
    user operations that reach them are the matrix offset column (density and
    colour balance, which is the vendor's own per-frame control) and geometry,
    which selects pixels without altering their values.

    ``out`` overrides the destination path, and is how ``plan_export``'s
    decision reaches the write: the plan is made once, up front, for the whole
    batch, and each frame is then written exactly where the plan said. Working
    the path out again here would let the two disagree.
    """
    f = roll.frames[index]
    p = merged_params(f.params)
    dest.mkdir(parents=True, exist_ok=True)
    out = Path(out) if out is not None else export_path(
        roll, index, dest, fmt, colour, template)
    out.parent.mkdir(parents=True, exist_ok=True)
    replaced = out.is_file()

    if colour == "linear":
        # The vendor's "Save As Raw" STAGE (stage 2 only, no Ansel, no ICC
        # hop) — not its file format. The real PSI software's own Save As Raw
        # output is 8-bit, not 16: a real vendor export pulled down for
        # comparison, rawAA001.tif, has TIFF tag 258 (BitsPerSample) =
        # (8, 8, 8) and decodes to dtype uint8. That is not a sensor
        # limitation — a real EP 0x86 capture read straight off the wire
        # (pakon_decode.load_u16 + segment_lines + to_rgb14, no dark/gain/poly
        # correction applied) shows raw14 using its full range: 100% of pixels
        # exceed 255 on every channel, ~14-16k distinct code values used per
        # channel, matching RAW14_MAX = 16383. So the vendor's own software
        # throws 14-bit sensor data away down to 8 bits even on its most-
        # preserving export; the 16-bit TIFF written below keeps what the
        # vendor's own "raw" file discards, and is this port's own choice —
        # not a reproduction of the vendor file's actual depth.
        #
        # Per-frame steps are NOT baked in — they are a correction to the
        # rendered result, and this file is deliberately the data before that.
        # A "one step" equivalent in the RPD domain would be a made-up
        # conversion across the Shasta/FUGC LUTs, so it is not attempted.
        #
        # On F-135 this is the polynomial's LINEAR output (what the code calls
        # rom12), i.e. still a NEGATIVE for negative film — the inversion is
        # part of the render, and this export is defined as the data before
        # the render. It is not "16-bit RPD", which in this chain means the
        # positive density codes f135_rom12_to_rpd12 produces. Anyone reading
        # these .tif files needs to know which of the two they have.
        seg = roll.slice14(f.a, f.b, 1)
        rpd16 = _rpd16(seg, roll.data_dir,
                       np.asarray(roll.auto_offsets, dtype=np.float64),
                       model=roll.model, film_class=roll.film_class())
        img16 = _apply_geometry(
            dec.to_frame_image(rpd16, roll.transport_scale), p)
        out = out.with_suffix(".tif")
        h, w = img16.shape[:2]
        pc.write_tiff(str(out), w, h,
                      np.ascontiguousarray(img16).astype("<u2").tobytes())
    else:
        img = render_frame(roll, index, p, scale="full")   # 8-bit by nature
        from PIL import Image
        im = Image.fromarray(img, "RGB")
        if fmt == "jpeg":
            im.save(out, "JPEG", quality=95, subsampling=0)
        elif fmt == "png":
            im.save(out, "PNG")
        else:
            im.save(out, "TIFF", compression="tiff_deflate")

    size = out.stat().st_size if out.is_file() else 0
    f.exported = str(out)
    return {"path": str(out), "bytes": size, "frame": index,
            "depth": 16 if colour == "linear" else 8}


# --------------------------------------------------------------------------
# CLI — lets the engine be exercised without Electron
# --------------------------------------------------------------------------

def _open_cli(a) -> Roll:
    t0 = time.perf_counter()
    roll = open_capture(
        a.capture, a.workspace, "check", dx=a.dx, max_lines=a.max_lines,
        film_path=a.film_path, sba_key=a.sba_key, sba_default=a.sba_default,
        progress=lambda ph, f, m: print(f"  [{f:5.0%}] {ph}: {m}"))
    print(f"open: {time.perf_counter() - t0:.2f} s — {roll.lines} lines, "
          f"{len(roll.frames)} frames")
    print(f"  sync:         {roll.sync}")
    print(f"  auto offsets: {[round(v, 1) for v in roll.auto_offsets]}")
    print(f"  roll scale:   {[round(v, 3) for v in roll.roll_scale]}")
    return roll


def cmd_check(a) -> int:
    """Timing across the render scales — the number the UI is designed around."""
    roll = _open_cli(a)
    for scale in ("thumb", "preview", "display", "full"):
        t = time.perf_counter()
        img = render_frame(roll, a.frame, None, scale=scale)
        print(f"  render {scale:<8} {img.shape[1]:>5}x{img.shape[0]:<5} "
              f"{(time.perf_counter() - t) * 1000:8.1f} ms")
    if a.out:
        Path(a.out).write_bytes(
            encode(render_frame(roll, a.frame, None, scale=a.scale), "PNG"))
        print(f"wrote {a.out}")
    return 0


def cmd_verify(a) -> int:
    """Prove the UI adds nothing: our full-quality frame must equal
    ``pakon_decode.py strip --color --icc --frames`` byte for byte."""
    import subprocess
    import tempfile
    from PIL import Image

    tmp = Path(tempfile.mkdtemp(prefix="pakon-verify-"))
    cmd = [sys.executable, str(_TOOLS / "pakon_decode.py"), "strip",
           str(a.capture), str(tmp), "--color", "--icc", "--frames"]
    if a.max_lines:
        cmd += ["--max-lines", str(a.max_lines)]
    if a.dx:
        cmd += ["--dx", a.dx]
    if a.film_path:
        cmd += ["--film-path", a.film_path]
    if a.sba_key:
        cmd += ["--sba-key", a.sba_key]
    if a.sba_default:
        cmd += ["--sba-default"]
    print("reference: " + " ".join(cmd))
    t0 = time.perf_counter()
    r = subprocess.run(cmd, cwd=str(_ROOT), capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:])
        print(r.stderr[-3000:], file=sys.stderr)
        return 1
    print(f"  reference decode: {time.perf_counter() - t0:.1f} s")

    roll = _open_cli(a)
    refs = sorted((tmp / "frames").glob("*_srgb.png"))
    print(f"\ncomparing {len(refs)} reference frames against render_frame(full)")
    if len(refs) != len(roll.frames):
        print(f"  FAIL: frame count differs — reference {len(refs)}, "
              f"ours {len(roll.frames)}")
        return 1

    bad = 0
    for i, ref_path in enumerate(refs):
        ref = np.asarray(Image.open(ref_path).convert("RGB"), dtype=np.uint8)
        ours = render_frame(roll, i, None, scale="full")
        if ref.shape != ours.shape:
            print(f"  frame {i:02d}  SHAPE  ref {ref.shape} ours {ours.shape}")
            bad += 1
            continue
        diff = int((ref != ours).sum())
        total = ref.size
        if diff:
            worst = int(np.abs(ref.astype(int) - ours.astype(int)).max())
            print(f"  frame {i:02d}  {diff:>10} / {total} samples differ "
                  f"({100.0 * diff / total:.4f} %), max delta {worst}")
            bad += 1
        else:
            print(f"  frame {i:02d}  identical  {ours.shape[1]}x{ours.shape[0]}")

    print()
    if bad:
        print(f"RESULT: {bad} of {len(refs)} frames differ from the pipeline.")
        return 1
    print(f"RESULT: all {len(refs)} frames byte-for-byte identical to "
          f"pakon_decode.py. The UI adds nothing to the image path.")
    print("NOTE:   this verifies UI == pipeline. It does NOT verify "
          "pipeline == Kodak; the Ansel stage is still a stand-in "
          "(SETSHIFTS_12_PORTED=False).")
    return 0


def _cli() -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    def common(p):
        p.add_argument("capture")
        p.add_argument("--workspace", default="/tmp/pakon-render-check")
        p.add_argument("--max-lines", type=int, default=0)
        # same explicit film contract as pakon_decode.py
        p.add_argument("--dx", default=None)
        p.add_argument("--film-path", default=None,
                       choices=("ColNeg", "BnW", "POSITIVE", "IMPORTED"))
        p.add_argument("--sba-key", default=None)
        p.add_argument("--sba-default", action="store_true")

    c = sub.add_parser("check", help="open + render timing at every scale")
    common(c)
    c.add_argument("--frame", type=int, default=0)
    c.add_argument("--scale", default="preview", choices=list(SCALES))
    c.add_argument("--out", default=None, help="write a PNG here (test only)")
    c.set_defaults(fn=cmd_check)

    v = sub.add_parser("verify", help="byte-compare against pakon_decode.py")
    common(v)
    v.set_defaults(fn=cmd_verify)

    a = ap.parse_args()
    if not a.cmd:
        ap.print_help()
        return 2
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(_cli())
