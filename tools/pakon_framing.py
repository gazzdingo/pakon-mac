#!/usr/bin/env python3
"""Frame splitting in the shape the vendor actually does it.

WHY THIS EXISTS
---------------
``pakon_decode.find_frames`` (via ``ansel.find_frames_rpd``) is a single-pass
brightness-gap heuristic, and its own comment says so:

    # frame split (heuristic; vendor uses DetectFilm_G / DetectWhite_G)

Kodak does not do one pass. It runs a **five-phase cascade** and records which
phase placed each frame, so that downstream code — and the operator — knows
which boundaries to trust. ``docs/56-managed-code.md`` recovered the cascade
from the decompiled COM contract; ``docs/53-edge-data.md`` recovered the same
five functions from ``TLB.dll`` with addresses. This module implements it.

THE CASCADE, AND WHERE EACH PIECE COMES FROM
--------------------------------------------
Phases, in the order ``TLB.dll`` runs them, with the ``SCAN_WARNINGS_000``
value the vendor OR-s into the scan result for each (docs/56 §2.2):

    1. LookForNicePictures          SCANW_FRAMING_GOOD          0
    2. FramingLookInBetweenEnds     SCANW_FRAMING_IN_MIDDLE   256
    3. LookAtEnd                    SCANW_FRAMING_AT_END      512
    4. LookAtBeginning              SCANW_FRAMING_AT_BEGINNING 1024
    5. FramingBlindlyPlacePictures  SCANW_FRAMING_BAD        2048

Phase 5 is a **whole-roll fallback**, not a per-frame one, and that is now
confirmed in the DLL's own control flow rather than inferred: ``fcn.10006e70``
runs phases 1-4 and bails to its own exit (0x1000709c) without touching
phases 3 or 4 if the running count is still zero, and its caller
``fcn.100079c0`` chooses between ``fcn.100072c0`` (the whole cascade) and
``fcn.10006720`` (blind) on its second argument, OR-ing ``0x800`` in at
0x10007b1b or 0x10007d35 — one site per frame-geometry model, and both are in
that function — when it takes the blind branch. So phases 2-4 only run when
phase 1 found something, and phase 5 only runs when it did not. That
asymmetry is deliberate here.

"Phase 5 only runs when phase 1 found nothing" is a policy that lives one
level higher again, in ``fcn.1002a900``: ``fcn.100079c0`` itself just obeys
the flag, and ``fcn.1002a900`` calls it a second time with the flag set when
the first call returns exactly zero (0x1002abae). See
``vendor_place_roll_pictures``.

The acceptance window in phase 1 is the vendor's, not invented — but the
citation it was taken from is wrong in two ways, both corrected below and
both load-bearing. docs/53 §4.2.1 gives ``FN_iFramingCreateOnesArray`` as
``0x10006289``-``0x100062eb``. That range is real code and it really does bin
run lengths against 95/100 and 115/100. It is **not a function**: it is the
tail of ``fcn.10006140`` (0x10006140-0x10006308), whose first two thirds
extract the runs the tail then bins. And the quantity binned is the **frame
width**, not the pitch — ``fcn.10006930`` computes the same two limits from
its own ``width`` argument (0x1000693d/0x1000694c), and ``fcn.100072c0``
prints them under the ``Target`` column, which is the width. This module's
own ``frame_cascade`` gets that right by accident (it derives ``target`` from
the pitch by the 36/38 ratio); the docstring did not.

Those limits are the ``LoLim`` and ``HiLim`` columns the vendor prints into
``DXCode.txt`` beside ``Target`` (docs/56 §2.3, §2.9):

    LoLim  Target HiLim  Actual Variance  LeftEdge  RightEdge

Asymmetric: 5% under, 15% over. Over-tolerance is wider because the failure
that matters is two frames merging when their gap is missed.

The input signal is the vendor's too. docs/53 §4.2.1: framing reduces each
scanline to a **single scalar** ``(R+G+B)/3`` and never sees per-column data.
So this module works on a 1-D trace, deliberately, even though we have the
full strip.

TWO CHAINS LIVE IN THIS MODULE — KNOW WHICH ONE RUNS
----------------------------------------------------
``find_frames`` / ``frame_cascade`` are **this port's own** heuristic
cascade: Otsu binarisation, this port's placement, this port's phase
attribution. That is what ``pakon_decode`` and the app call, and it is what
every frame boundary this project has ever produced came from.

``vendor_framing_entry`` and the ``vendor_*`` helpers are **the vendor's**,
ported from ``TLB.dll`` and proven bit-exact under Unicorn end to end
(``tools/ansel/python-pipeline/pakon_framing_golden.py``, 15 functions). It
is complete — trace reduction, histogram, both threshold rules, the ±2
threshold search, all four search phases, blind placement, the film-edge
validator, the warning word. **Nothing calls it.**

The one thing between them is a measurement, not a port:
``fcn.10006870`` consumes the object's **3-byte per-line RGB summary** at
``this+0x6c`` and reduces it to ``255 - (r+g+b)/3`` — 8-bit, and inverted, so
a bright film-base line reads LOW and an exposed line reads HIGH.
``framing_trace`` below is a float mean of calibrated 14-bit pixels and is not
inverted. Where the vendor's 8-bit summary comes from on a real F-135 scan is
still not established, and guessing the quantisation would silently move every
boundary — the golden harness could not catch it, because it feeds both sides
the same synthetic bytes. Capture that, and the vendor chain can be wired in
behind ``find_frames``; until then the two differ and this module says so.

Where they differ, concretely, all confirmed against the real DLL:

1. **Placement.** Phase 1 here emits the detected run; the vendor emits a
   *nominal-width* frame offset into it by one third of the slack, and splits
   a merged pair in phase 1 rather than deferring to phase 2.
2. **Binarisation.** Otsu here (``INFERRED``); the vendor uses a modal-peak
   rule with a 2nd-percentile fallback, then searches ±2 around it.
3. **The per-candidate validity test.** ``fcn.10006310`` zeroes a candidate
   that no pair of film-edge marks straddles. There is no equivalent in
   ``frame_cascade`` and no edge-mark signal to feed one.
4. **Phase attribution.** The vendor tags 1/2/4/3 for phases 1/2/3/4 (yes, in
   that order) and 9 for blind; ``Phase`` here is the SCAN_WARNINGS value.

The phases, their order, the 95/115 window, the SCAN_WARNINGS values and the
1-D input *are* the vendor's, and the warning values are confirmed against
the DLL's own ``or`` instructions rather than a decompiled header.

FILM PRESENCE IS A SEPARATE QUESTION, WITH A SEPARATE SIGNAL
------------------------------------------------------------
``DetectWhite_G`` / ``DetectFilm_G`` are *not* frame-gap thresholds. docs/56
§3.1 shows they are carried in and out of ``CalibrationGetLightLED`` /
``CalibrationPutLightLED`` alongside ``Gain_*``, ``Offset_*``, ``Current_*``
and ``DutyCycle_*`` — they belong to the **LED light calibration group**, so
they are absolute green levels tied to one calibrated light setting. They
answer "is the gate empty", i.e. start and end of film.

Against the vendor's own empty-gate calibration target of G = 64000
(``FN_bCalibrateFindLedCurrent``, docs/42-port-remaining-work.md):

    DetectWhite_G = 61000  ->  0.953 of the empty-gate level
    DetectFilm_G  = 54000  ->  0.844 of the empty-gate level

Those *fractions* transfer to this unit; the absolute counts do not. Our
bright reference was deliberately taken at ~50 000 so no channel clips
(docs/46 §2), giving ``pakon_gate``'s clear level of 50689.1. So here:

    white level ~ 0.953 * 50689 = 48 300      gate is empty above this
    film level  ~ 0.844 * 50689 = 42 800      film is present below this

with the band between them held at the previous state — a Schmitt trigger,
which is the shape ``pakon_gate.py``'s docstring says we needed after the
one-boundary detector let a roll run past a dead lamp.

USAGE
-----
    python3 tools/pakon_framing.py --self-test
    python3 tools/pakon_framing.py capture.bin
    python3 tools/pakon_framing.py capture.bin --speed 11467 --json

``tools/pakon_decode.py``, ``tools/pakon_ui.py``, ``tools/pakon_scan.py`` and
``tools/ansel/`` belong to other tasks and are not touched by this module.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

import numpy as np

# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------
#
# 35 mm still film, the F-135's only format (docs/53 §3.3: iFilmFormat != 1
# returns NULL and TLB carries only \DpiBase{4,8,16}_35).
#
#   image      24 x 36 mm
#   pitch      38 mm  = 8 perforations x 4.75 mm
#   gap        ~2 mm between exposed areas
#
# Cross-check against the vendor's own output size. FRAME_SIZES_000 gives
# HR_HEIGHT_BASE16_35 = 2000 and HR_WIDTH_BASE16_35 = 3000 (docs/56 §2.7).
# 2000 px across 24 mm = 83.33 px/mm; 3000 lines along 36 mm = 83.33 lines/mm.
# Square pixels, and the same 83.333 that pakon_decode.ACROSS_PX_PER_MM uses.

FRAME_IMAGE_MM = 36.0     # exposed width along the film -- phase 1 "Target"
FRAME_PITCH_MM = 38.0     # frame-to-frame spacing -- used by phases 2-5
FILM_ACROSS_MM = 24.0
CCD_ACROSS_PX = 2000
ACROSS_PX_PER_MM = CCD_ACROSS_PX / FILM_ACROSS_MM   # 83.333, == pakon_decode

# FN_iFramingCreateOnesArray, docs/53 §4.2.1
LO_LIM_FRAC = 0.95
HI_LIM_FRAC = 1.15

# This port's own approximation, not the vendor's -- there is no VA for it,
# because the vendor never estimates pitch at all (estimate_pitch's own
# docstring). estimate_pitch can be fooled by a single real photo whose
# internal brightness variation fragments its ones-run into pieces that are
# each still >= min_run: the deltas between fragment starts are then noise,
# not pitch, and the median can lock onto a spurious sub-pitch value.
#
# Measured on 2026-08-14 across every capture available (find_frames_traces'
# geometry vs. the "measured" pitch's implied lines/mm, i.e. pitch /
# FRAME_PITCH_MM, against ACROSS_PX_PER_MM-derived geometry):
#
#   well-behaved (most frames pass phase 1 as single clean runs):
#     scan-20260812-082437.bin        0.89 % off geometry
#     scan-20260812-085241.bin        0.77 % off geometry
#     gold400.bin                     1.35 % off geometry
#     vendor-duty-test-20260813-221801.bin   0.83 % off geometry
#     scan-20260807-181450.bin        0.49 % off geometry
#   fragmented (few or no frames pass phase 1 as single clean runs):
#     fresh-calibration-scan-20260814-065421.bin   29.32 % off geometry
#     scan-20260812-091633.bin        29.37 % off geometry
#     scan-20260812-094912.bin        28.73 % off geometry
#     vendor-duty-fixed-offset-20260813-225308.bin 28.54 % off geometry
#     roll.bin                        40.28 % off geometry (fell all the way
#                                      to FramingBlindlyPlacePictures)
#
# Worst well-behaved case 1.35 %, best fragmented case 28.54 % -- a clean
# order-of-magnitude gap. 0.15 sits with >10x margin on both sides; it is not
# reused from LO_LIM_FRAC/HI_LIM_FRAC (those are the vendor's, for a
# different quantity) even though the number happens to match.
PITCH_AGREEMENT_FRAC = 0.15

# DetectFilm_G / DetectWhite_G as fractions of the empty-gate level.
# docs/56 §3.1; absolute hive values 61000 / 54000 against a 64000 target.
DETECT_WHITE_FRAC = 61000.0 / 64000.0    # 0.9531
DETECT_FILM_FRAC = 54000.0 / 64000.0     # 0.8438

# pakon_gate.py, derived from calibration/: clear 50689.1, dark 1241.4.
DEFAULT_CLEAR_LEVEL = 50689.1
DEFAULT_DARK_LEVEL = 1241.4


class Phase(IntEnum):
    """Which pass placed a frame. Values are TLXLib.SCAN_WARNINGS_000."""

    NICE = 0            # SCANW_FRAMING_GOOD
    IN_BETWEEN = 256    # SCANW_FRAMING_IN_MIDDLE
    AT_END = 512        # SCANW_FRAMING_AT_END
    AT_BEGINNING = 1024  # SCANW_FRAMING_AT_BEGINNING
    BLIND = 2048        # SCANW_FRAMING_BAD

    @property
    def vendor_name(self) -> str:
        return {
            Phase.NICE: "LookForNicePictures",
            Phase.IN_BETWEEN: "FramingLookInBetweenEnds",
            Phase.AT_END: "LookAtEnd",
            Phase.AT_BEGINNING: "LookAtBeginning",
            Phase.BLIND: "FramingBlindlyPlacePictures",
        }[self]

    @property
    def risk(self) -> int:
        """TLXLib.FRAMING_RISK_000, per docs/53 §4.2.2.

        Coarser than the scan warning: all three middle passes collapse to 1.
        """
        return {Phase.NICE: 0, Phase.IN_BETWEEN: 1, Phase.AT_END: 1,
                Phase.AT_BEGINNING: 1, Phase.BLIND: 4}[self]


@dataclass
class Frame:
    """One placed frame. ``start``/``stop`` are line indices, stop exclusive."""

    start: int
    stop: int
    phase: Phase
    #: Fraction of this frame's own [start, stop) that the cascade's own
    #: "ones" (image-density) classification marked as real photographic
    #: content, rather than interframe gap/leader. ``None`` until
    #: ``frame_cascade`` fills it in (every real caller does).
    #:
    #: Exists because ``confidence``/``framing_risk`` (docs/74 §43) only say
    #: how a boundary was *placed* (which phase, how odd its width is) and
    #: say nothing about what is actually *inside* it. A phase-3/4
    #: (``LookAtEnd``/``LookAtBeginning``) placement snaps its start to a
    #: real detected run but then pads the far end out to the nominal frame
    #: width regardless of where that run actually ends -- when the real run
    #: is much shorter than nominal (a short/faint frame, or one crowding the
    #: roll's own end), the padded tail runs past it into brighter gap
    #: material, and this fraction drops well below 1.0 even though nothing
    #: downstream is told. Confirmed on two independent real captures (docs/74
    #: §43): a clean ``LookForNicePictures``/``LookAtBeginning`` frame reads
    #: 0.997-1.000; a diluted ``LookAtEnd`` frame reads 0.52-0.82.
    content_fraction: float | None = None

    @property
    def lines(self) -> int:
        return self.stop - self.start

    def as_dict(self) -> dict:
        return {"start": self.start, "stop": self.stop, "lines": self.lines,
                "phase": self.phase.vendor_name,
                "content_fraction": self.content_fraction,
                "scan_warning": int(self.phase),
                "framing_risk": self.phase.risk}


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------

# Hive MotorSpeedPlus per DpiBase (same table as pakon_decode / pakon_scan).
MOTOR_SPEED = {4: 25802, 8: 11467, 16: 5917}
REF_LINE_RATE = 60
# DpiBase16's MotorSpeedPlus. Our exposure triad is DpiBase16's
# (calibration/README.json) and the vendor's FRAME_SIZES_000 makes that base
# 2000 x 3000 over 24 x 36 mm -- square. See pakon_decode's geometry block.
# This was MOTOR_SPEED[8]; that is the 1.9x estimate_pitch used to warn about.
SQUARE_MOTOR_SPEED = MOTOR_SPEED[16]


def along_lines_per_mm(speed: float, line_rate: float = REF_LINE_RATE) -> float:
    """Lines of capture per mm of film travel at this transport setting.

    Mirrors ``pakon_decode.along_lines_per_mm`` exactly (that module is owned
    by another task, so the relation is restated rather than imported, to keep
    this tool importable on its own). If ``pakon_decode`` is importable its
    value is preferred -- see ``resolve_lines_per_mm``.
    """
    if speed <= 0 or line_rate <= 0:
        raise ValueError(f"speed and line_rate must be > 0 (got {speed}, {line_rate})")
    scale = (float(speed) / SQUARE_MOTOR_SPEED) * (REF_LINE_RATE / float(line_rate))
    return ACROSS_PX_PER_MM / scale


def resolve_lines_per_mm(speed: float | None,
                         line_rate: float = REF_LINE_RATE) -> float:
    """Prefer pakon_decode's geometry when it is importable."""
    if speed is None:
        speed = SQUARE_MOTOR_SPEED
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import pakon_decode  # type: ignore
        return pakon_decode.along_lines_per_mm(speed, line_rate)
    except Exception:
        return along_lines_per_mm(speed, line_rate)


# --------------------------------------------------------------------------
# Signals
# --------------------------------------------------------------------------

def framing_trace(strip: np.ndarray) -> np.ndarray:
    """Reduce a strip to the vendor's 1-D framing signal.

    docs/53 §4.2.1: ``fcn.10006870`` reduces each scanline to a single scalar
    ``(R+G+B)/3``. The framing pipeline never sees per-column data, so neither
    does this.

    Accepts (lines, px, 3), (lines, 3) or (lines,).
    """
    a = np.asarray(strip, dtype=np.float64)
    if a.ndim == 3:
        return a.mean(axis=(1, 2))
    if a.ndim == 2:
        return a.mean(axis=1)
    if a.ndim == 1:
        return a
    raise ValueError(f"cannot reduce array of shape {a.shape} to a line trace")


def green_trace(strip: np.ndarray) -> np.ndarray:
    """Per-line green level -- the channel DetectFilm_G / DetectWhite_G use."""
    a = np.asarray(strip, dtype=np.float64)
    if a.ndim == 3:
        return a[:, :, 1].mean(axis=1)
    if a.ndim == 2:
        return a[:, 1]
    if a.ndim == 1:
        return a
    raise ValueError(f"cannot reduce array of shape {a.shape} to a green trace")


def film_present(green: np.ndarray,
                 clear_level: float = DEFAULT_CLEAR_LEVEL) -> np.ndarray:
    """Schmitt-trigger film presence from the vendor's threshold pair.

    Above ``DetectWhite_G`` the gate is empty; below ``DetectFilm_G`` film is
    present; between them the previous state is held. See the module docstring
    for why one threshold is not enough -- a roll once ran past a dead lamp
    because darkness read as film.

    Returns a bool array, True where film is in the gate.
    """
    white = clear_level * DETECT_WHITE_FRAC
    film = clear_level * DETECT_FILM_FRAC
    out = np.zeros(green.shape[0], dtype=bool)
    state = False
    for i, g in enumerate(green):
        if g < film:
            state = True
        elif g > white:
            state = False
        out[i] = state
    return out


def _otsu(values: np.ndarray) -> float:
    """Otsu's threshold. INFERRED stand-in for the vendor's binarisation."""
    v = values[np.isfinite(values)]
    if v.size == 0:
        return 0.0
    hist, edges = np.histogram(v, bins=256)
    centres = (edges[:-1] + edges[1:]) / 2.0
    w = np.cumsum(hist)
    total = w[-1]
    if total == 0:
        return float(centres[0])
    s = np.cumsum(hist * centres)
    w0 = w
    w1 = total - w0
    valid = (w0 > 0) & (w1 > 0)
    if not valid.any():
        return float(np.median(v))
    m0 = np.where(w0 > 0, s / np.maximum(w0, 1), 0.0)
    m1 = np.where(w1 > 0, (s[-1] - s) / np.maximum(w1, 1), 0.0)
    between = w0 * w1 * (m0 - m1) ** 2
    between[~valid] = -1.0
    return float(centres[int(np.argmax(between))])


def ones_array(trace: np.ndarray,
               present: np.ndarray | None = None,
               threshold: float | None = None) -> tuple[np.ndarray, float]:
    """Binarise the framing trace: True where a line is image, not gap.

    The vendor calls the result the "ones" array -- ``TLB.dll`` logs a section
    header ``------------------ Framing Ones -----------------`` and
    ``FN_iFramingCreateOnesArray`` bins runs in it.

    Image is *denser* than the interframe gap, so image lines are the darker
    ones. The split level is Otsu over the film-present region: INFERRED, see
    the module docstring.
    """
    t = np.asarray(trace, dtype=np.float64)
    region = t if present is None else t[present]
    if threshold is None:
        threshold = _otsu(region) if region.size else float("inf")
    ones = t < threshold
    if present is not None:
        ones &= present
    return ones, float(threshold)


def estimate_pitch(ones: np.ndarray, min_run: int = 200) -> float | None:
    """Measure the frame pitch from the data instead of assuming it.

    WHY THIS IS NOT JUST BELT-AND-BRACES
    ------------------------------------
    The vendor never needs this: TLB knows its own calibrated DPI and motor
    speed, so ``pitch`` is a constant it looks up. We are not so lucky --
    nothing in a ``.bin`` records the transport speed, and captures taken
    before ``pakon_scan`` wrote sidecars have no record of it anywhere.

    This estimator also *found* the geometry bug it used to warn about. It
    measured ``captures/gold400.bin`` at 1656 lines where the old anchor
    (square at ``MotorSpeedPlus`` 11467) predicted 3167 -- a factor of 1.938,
    which is exactly 11467/5917. The anchor is now DpiBase16's 5917, the
    prediction is 1634, and the residual is 1.3 %. See ``pakon_decode``'s
    geometry comment block and ``pakon_decode.py geometry``.

    So the two routes usually agree, and framing prefers the measurement when
    they do -- it needs neither the sidecar nor the anchor, only the fact
    that 35 mm frames are 38 mm apart. But "usually" is not "always": this
    estimator has no notion of what a frame is supposed to look like, only of
    runs of ones at least ``min_run`` long. On a real photo whose brightness
    varies internally (a bright sky, a highlight), the Otsu split (still
    INFERRED, see the module docstring) can cut a single real frame into two
    or three ones-runs with small gaps of misclassified "gap" between them.
    Each fragment can still be >= 200 lines, so each fragment's start looks
    like a frame start to this function, and the deltas between fragment
    starts are noise, not pitch. ``frame_cascade`` cross-checks this
    estimate against geometry for exactly that reason -- see
    ``PITCH_AGREEMENT_FRAC``. Pass ``--pitch-lines`` to force a value, or
    ``--speed`` to derive one.

    Returns the estimated start-to-start pitch in lines, or None if there is
    not enough structure to measure.
    """
    runs = [(a, b) for a, b in _runs(ones) if b - a >= min_run]
    if len(runs) < 3:
        return None
    starts = np.array([a for a, _ in runs], dtype=np.float64)
    deltas = np.diff(starts)
    if deltas.size < 2:
        return None
    m0 = float(np.median(deltas))
    if m0 <= 0:
        return None
    # Fold multi-pitch gaps (a missed frame shows up as ~2x) back down.
    folded = []
    for d in deltas:
        k = max(1, int(round(d / m0)))
        if abs(d - k * m0) <= 0.3 * m0:
            folded.append(d / k)
    if len(folded) < 2:
        return None
    return float(np.median(folded))


# --------------------------------------------------------------------------
# The vendor's own arithmetic, ported from TLB.dll and verified bit-exact
# --------------------------------------------------------------------------
#
# TLB.dll md5 193d9b2ce0a4b77ae9b78262bd06c0fc, PE base 0x10000000, built
# 2007-04-18. Every address below was recovered with radare2 ``af`` + ``pdf``
# on a real function boundary and the full body read; see
# ``tools/ansel/python-pipeline/pakon_framing_golden.py`` for the Unicorn
# harness that proves each of these against the real DLL.
#
# CORRECTION TO THE CITATIONS THIS MODULE WAS BUILT FROM. The docstring above
# cites ``FN_iFramingCreateOnesArray`` at ``0x10006289``-``0x100062eb``. That
# range is real code and it really does bin run lengths against 95/115 percent
# --- but it is NOT a function. It is the *tail* of ``fcn.10006140``
# (0x10006140-0x10006308, 453 bytes, 39 basic blocks), which extracts the runs
# first and bins them second. Citing the tail as the whole hid the run
# extractor, which is where the real arithmetic lives.
#
# The five phase functions are real, and their strings really are in the DLL
# (file offsets 0x5b890/0x5b8b8/0x5b8d4/0x5b8ec/0x5b944). Their addresses:
#
#     fcn.100072c0   framing entry: allocate, threshold-search, log, cascade
#     fcn.10006870   per-line trace reduction   (docs/53's fcn.10006870: OK)
#     fcn.10005ce0   256-bin histogram of the trace over [first, last]
#     fcn.10005d20   pick a threshold and binarise into the "ones" array
#     fcn.10006140   ones -> run records + LoLim/HiLim bin counts
#     fcn.10006e70   the four-phase cascade driver (logs each phase)
#     fcn.10006930   phase 1  LookForNicePictures
#     fcn.100063d0   phase 2  FramingLookInBetweenEnds
#     fcn.10006ae0   phase 3  LookAtEnd
#     fcn.10006ca0   phase 4  LookAtBeginning
#     fcn.10006720   phase 5  FramingBlindlyPlacePictures
#     fcn.10006310   per-candidate validity test against film edge marks
#
# The SCAN_WARNINGS_000 values are confirmed in the DLL's own code, not just
# in a decompiled header: ``or eax, 0x100`` @ 0x1000708b (IN_MIDDLE),
# ``or eax, 0x200`` @ 0x10007193 (AT_END), ``or dword [ebp+0x6ca8], 0x400``
# @ 0x1000729f (AT_BEGINNING) and ``or edi, 0x800`` @ 0x10007b1b AND
# 0x10007d35 (BAD). The last one has TWO sites, not one — see
# ``vendor_place_roll_pictures``; an encoding search over the whole image
# finds no third.

#: Is the whole five-phase cascade bit-exact against TLB.dll? **Still no**, and
#: the reason has changed, so read this rather than assuming it is the old one.
#:
#: WHAT IS NOW TRUE. ``vendor_framing_entry`` is ``fcn.100072c0`` — the real
#: framing entry — and it is bit-exact against TLB.dll end to end: from a
#: per-line RGB summary through the trace reduction, the histogram, BOTH
#: threshold rules, the two-legged ±2 threshold search and all four search
#: phases, to the frame count and the ``SCAN_WARNINGS`` word. Fourteen vendor
#: functions underneath it are individually bit-exact too. So the arithmetic of
#: vendor framing is no longer the open question; it is ported.
#:
#: WHY THE FLAG IS STILL FALSE. Two things, both concrete:
#:
#:   1. **Nothing in this module calls it.** ``find_frames`` /
#:      ``frame_cascade`` — the entry points ``pakon_decode`` and the app use —
#:      are unchanged: still the Otsu binarisation (``INFERRED``), still this
#:      port's own placement, still this port's own phase attribution. The
#:      verified chain sits beside them, not under them.
#:   2. **Nothing can feed it yet.** ``fcn.100072c0`` consumes the object's own
#:      per-line **3-byte RGB summary** at ``this+0x6c``. This module's
#:      ``framing_trace`` is a float mean of calibrated 14-bit pixels and is not
#:      inverted. Where the vendor's 8-bit summary comes from on a real F-135
#:      scan is still not established, and it is not this port's to invent — a
#:      guessed quantisation would make every boundary wrong in a way the
#:      golden harness cannot see, because the harness feeds both sides the
#:      same synthetic bytes. This is the one remaining piece of real
#:      reverse-engineering between here and a true ``True``.
#:
#: The layer above — ``fcn.100079c0``, the roll-level caller — IS ported now
#: (``VENDOR_ROLL_PICTURES_PORTED``), and neither of the two reasons above is
#: affected by that: the caller consumes the same uncaptured 8-bit per-line RGB
#: summary, and nothing in this module calls it either.
FRAMING_PORTED = False

#: fcn.10006140 (0x10006140-0x10006308) — bit-exact, see the golden harness.
VENDOR_RUNS_PORTED = True
#: fcn.10006930 (0x10006930-0x10006ade) — bit-exact, see the golden harness.
VENDOR_NICE_PICTURES_PORTED = True
#: fcn.10005ce0 (0x10005ce0-0x10005d1b) — bit-exact, see the golden harness.
VENDOR_HISTOGRAM_PORTED = True
#: fcn.10006870 (0x10006870-0x10006922) — bit-exact, see the golden harness.
VENDOR_TRACE_PORTED = True
#: fcn.100063d0 (0x100063d0-0x100064ce) — bit-exact, see the golden harness.
VENDOR_IN_BETWEEN_PORTED = True
#: fcn.10006720 (0x10006720-0x10006860) — bit-exact, see the golden harness.
VENDOR_BLIND_PORTED = True
#: fcn.10006ae0 (0x10006ae0-0x10006c98) — bit-exact, see the golden harness.
VENDOR_AT_END_PORTED = True
#: fcn.10006ca0 (0x10006ca0-0x10006e60) — bit-exact, see the golden harness.
VENDOR_AT_BEGINNING_PORTED = True
#: fcn.10006310 (0x10006310-0x100063c4) — bit-exact, see the golden harness.
#: This closes the oldest open restriction in this module: phase 1's port was
#: documented as "the ``this+0xca4 == 0`` path only" because the film-edge
#: validity test was unported. It is ported now, and the ``dc == 0`` (marks
#: really consulted) path is exercised through phases 3 and 4.
VENDOR_EDGE_VALIDITY_PORTED = True
#: fcn.10006630 (0x10006630-0x10006712) — bit-exact, see the golden harness.
VENDOR_GAP_ADMISSIBLE_PORTED = True
#: fcn.100064e0 (0x100064e0-0x1000662d) — bit-exact, see the golden harness.
VENDOR_BEST_WINDOW_PORTED = True
#: fcn.10013960 (0x10013960-0x10013978) — bit-exact, see the golden harness.
VENDOR_EDGE_AT_PORTED = True
#: fcn.10006e70 (0x10006e70-0x100072b2) — bit-exact, see the golden harness.
#: This is the four-phase cascade as a WHOLE, not a part of it: phase order,
#: the bound scan between phases 1 and 2, the phase gates, the tag stamps and
#: the SCAN_WARNINGS accumulator, all compared end to end against TLB.dll.
VENDOR_CASCADE_DRIVER_PORTED = True
#: fcn.10005d20 (0x10005d20-0x1000613b) — bit-exact, see the golden harness.
#: Both threshold rules, including the x87 2nd-percentile branch, and the
#: binarisation. This retires the module's ``INFERRED`` Otsu stand-in as the
#: only available answer — ``ones_array`` still uses Otsu, but there is now a
#: verified vendor alternative to point it at.
VENDOR_THRESHOLD_PORTED = True
#: fcn.100072c0 (0x100072c0-0x100079ae) — bit-exact, see the golden harness.
#: The framing entry in full, threshold search included. See ``FRAMING_PORTED``
#: for why a verified entry is not yet a verified module.
VENDOR_ENTRY_PORTED = True
#: fcn.100079c0 (0x100079c0-0x10007f11) — bit-exact, see the golden harness.
#: The roll-level caller: slot-array sizing, the cascade-vs-blind branch and
#: both of its ``0x800`` warning sites, both frame-geometry models, and the
#: conversion of the cascade's slot array into the object's ``CiPicLoc`` list.
#: This is the last function in the framing chain; nothing above it in TLB.dll
#: is framing-specific. It does NOT make ``FRAMING_PORTED`` true — see that
#: flag's own comment, whose two reasons this does not touch.
VENDOR_ROLL_PICTURES_PORTED = True


def _cdiv(a: int, b: int) -> int:
    """C integer division: quotient truncated toward zero.

    The vendor never divides; MSVC turned every ``/100`` and ``/3`` in this
    subsystem into a multiply-high by 0x51EB851F / 0x55555556 plus the
    ``shr 31; add`` sign fixup, which is exactly truncation toward zero. Python
    ``//`` floors, so it disagrees for every negative numerator — and negative
    numerators DO occur here (``length - width`` in
    ``vendor_look_for_nice_pictures`` is negative for any run shorter than the
    nominal frame).
    """
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def vendor_limits(width: int) -> tuple[int, int]:
    """``(LoLim, HiLim)`` the vendor's way: ``w*95/100`` and ``w*115/100``.

    Integers, truncated, computed from the *frame width* — not from a pitch,
    and not in floating point. ``frame_cascade`` derives its own window from
    ``target * 0.95 / 1.15`` in float, which rounds differently at the
    boundary; and it compares with ``<=`` where the vendor compares with
    ``<`` (``jle``/``jge`` @ 0x100062d8/0x100062dc, 0x1000699e/0x100069a2).
    A run whose length is exactly ``LoLim`` or exactly ``HiLim`` is REJECTED
    by the vendor and ACCEPTED here.
    """
    return _cdiv(width * 95, 100), _cdiv(width * 115, 100)


def vendor_framing_trace(rgb_u8: np.ndarray, invert: bool = True) -> np.ndarray:
    """``fcn.10006870`` — the vendor's per-line framing scalar.

    Input is a ``(lines, 3)`` array of **bytes**: the vendor keeps a 3-byte
    per-line RGB summary at ``this+0x6c`` and framing never sees anything
    else. Output is ``255 - (r+g+b)//3`` — an unsigned average (the
    ``mul 0xAAAAAAAB; shr edx,1`` at 0x100068a5 is unsigned) subtracted from
    255, so the trace is a *density*: image lines read HIGH, gap lines LOW.

    ``invert=False`` is the ``[vtable+0x34] == 2`` branch (0x100068c2), which
    stores the plain average instead. Which mode a real F-135 scan takes is
    not established here; the caller must say.
    """
    a = np.asarray(rgb_u8)
    if a.ndim != 2 or a.shape[1] != 3:
        raise ValueError(f"expected (lines, 3) bytes, got {a.shape}")
    s = a.astype(np.int64).sum(axis=1)
    avg = s // 3
    return (255 - avg if invert else avg).astype(np.int32)


def vendor_line_histogram(trace: np.ndarray, first: int, last: int) -> np.ndarray:
    """``fcn.10005ce0`` — 256-bin histogram of ``trace[first .. last]``.

    Inclusive of both ends (``count = last - first + 1``, 0x10005d00). The
    vendor indexes ``hist[trace[i]]`` with no bounds check at all, which is
    only safe because ``fcn.10006870`` cannot produce a value outside 0..255.
    """
    t = np.asarray(trace, dtype=np.int64)
    hist = np.zeros(256, dtype=np.int64)
    if last < first:
        return hist
    np.add.at(hist, t[first:last + 1], 1)
    return hist


def _u32(v: int) -> int:
    return int(v) & 0xFFFFFFFF


def _mulhi_shr(a: int, m: int, shift: int) -> int:
    """MSVC's ``mul``+``shr`` constant-division idiom, unsigned and exact."""
    return (_u32(a) * m) >> shift


def _round_f32(num: int, den: int):
    """Round the exact non-negative rational ``num/den`` to float32, RNE.

    Returns an exact ``Fraction``, so the caller can compare against it
    without ever leaving exact arithmetic.

    WHY EXACT ARITHMETIC RATHER THAN ``np.float32(num / den)``: the vendor's
    ``fmul`` runs in the x87's 80-bit registers and only the ``fstp dword``
    rounds, so the reference is round-once. ``num`` here reaches 2**40 and the
    constant carries 24 mantissa bits, so the exact product needs up to 64
    bits — representable in 80-bit, but not in a float64 intermediate, which
    would round twice.

    NEGATIVE RESULT, recorded because it is worth as much as a positive one:
    that double rounding was **never observed to change the answer** for this
    particular constant. Three million random ``total`` values below 2**40,
    plus a targeted sweep constructed to land on float32 halfway points,
    produced zero disagreements between this exact path and
    ``np.float32(np.float64(total) * 0.02f)``. So the exact path is belt and
    braces, not a demonstrated necessity — it is kept because it is right by
    construction and costs nothing at one call per framing pass, not because a
    counter-example is known.
    """
    from fractions import Fraction
    if num == 0:
        return Fraction(0)
    v = Fraction(num, den)
    exp = 0
    while v >= (1 << 24):
        v /= 2
        exp += 1
    while v < (1 << 23):
        v *= 2
        exp -= 1
    m = v.numerator // v.denominator
    rem = v - m
    half = Fraction(1, 2)
    if rem > half or (rem == half and (m & 1)):
        m += 1
        if m == (1 << 24):
            m >>= 1
            exp += 1
    return Fraction(m) * Fraction(2) ** exp


#: ``fcn.10005d20``'s x87 constants, read straight out of ``.rdata``:
#: 0x1005b85c = 0.02f (0x3CA3D70A), 0x1005b860 = 4294967296.0f (the unsigned
#: fixup added after a ``fild`` of a negative int32), 0x1005b864 = 0.0f (the
#: accumulator seed).
_THRESH_PCT_NUM = 10737418      # 0x3CA3D70A's mantissa
_THRESH_PCT_DEN = 1 << 29       # ... over 2**29, i.e. exactly 0.02f


def vendor_pick_threshold(ones, hist, trace, first: int, last: int,
                          forced: int) -> int:
    """``fcn.10005d20`` — pick the "ones" threshold and binarise with it.

    ``__stdcall``, seven args, ``ret 0x1c``:

        fcn.10005d20(ones, hist, trace, UNUSED, first, last, forced)

    The fourth argument is never read anywhere in the 1054-byte body. The
    golden harness proves that rather than asserting it, by running the vendor
    twice with different values in that slot and requiring the same answer.

    Returns the threshold it chose and writes ``ones[i] = 1`` where
    ``(unsigned)trace[i] > (unsigned)threshold``, for ``i`` in
    ``first .. last`` inclusive (0x10006126, ``sbb``/``neg``, so it really is
    strictly-greater and really is unsigned). Note the direction: the "ones"
    array marks lines ABOVE the threshold, which is why ``fcn.10006870``'s
    ``255 - avg`` inversion has to be there — image has to read high.

    THREE MODES, chosen by the sign of ``forced``:

    * ``forced > 0`` — used as-is (0x10005d47). No histogram work at all.
    * ``forced < 0`` — the **2nd-percentile** rule (0x10005ec8-0x10006109),
      done in x87: total the 256 bins, take ``0.02 * total`` rounded to
      float32, then walk a RUNNING CUMULATIVE sum from bin 0 and return the
      first bin index whose cumulative total exceeds it. Bins are ``fild``-ed
      as signed and get ``+2**32`` when negative, so the arithmetic is
      unsigned.
    * ``forced == 0`` — the **modal-peak** rule (0x10005d53-0x10005ec3), all
      integer:

      1. Scan bins 0..249 for the largest, remembering its index. Once the
         running maximum exceeds ``(last-first+1) * 0x1B4E81B5 >> 36``, the
         scan aborts at the first bin below ``0.6 *`` that maximum — a
         "we are past the peak" early-out.
      2. Walk DOWN from the peak while bins are at least ``max/20``, giving a
         left skirt width ``skirt``.
      3. Walk UP from the peak, at most 50 bins and never past 255, while
         bins are at least ``max/10``; call the stop ``hi``.
      4. If ``hi - peak <= 4 * skirt`` the answer is ``hi + (hi-peak)/2``.
         Otherwise the peak is lopsided, and the answer is instead the first
         bin at or above ``peak`` (capped at 255) whose count is below
         ``max/2``.

    ``(count * 0x1B4E81B5) >> 36`` in step 1 is MSVC's unsigned ``count / 150``:
    ``0x1B4E81B5 == 458129845 == ceil(2**36 / 150)`` exactly, and the
    multiply-shift agrees with ``count // 150`` on every value in
    ``0 .. 2**22`` and on two million random ``count < 2**32`` — no
    disagreements. It is still coded here as the literal multiply-and-shift
    rather than as ``// 150``, because that is what the CPU does and the
    equivalence is a checked fact about this constant, not a licence to
    rewrite the next one by eye.
    """
    count = _u32(last - first + 1)
    if forced > 0:
        thr = forced
    elif forced != 0:
        thr = _pick_threshold_percentile(hist)
    else:
        thr = _pick_threshold_modal(hist, _mulhi_shr(count, 0x1B4E81B5, 36))
    if first <= last:
        for i in range(first, first + count):
            ones[i] = 1 if _u32(thr) < _u32(trace[i]) else 0
    return thr


def _pick_threshold_percentile(hist) -> int:
    total = sum(_u32(v) for v in hist[:256])
    limit = _round_f32(total * _THRESH_PCT_NUM, _THRESH_PCT_DEN)
    cum = 0
    for i in range(250):
        cum += _u32(hist[i])
        if cum > limit:
            return i
    return 250


def _pick_threshold_modal(hist, floor_count: int) -> int:
    peak_count = 0
    peak = 0
    for i in range(250):
        h = _u32(hist[i])
        if peak_count > floor_count and h < _mulhi_shr(3 * peak_count,
                                                       0xCCCCCCCD, 34):
            break
        if h > peak_count:
            peak_count = h
            peak = i

    twentieth = _mulhi_shr(peak_count, 0xCCCCCCCD, 36)
    lo = peak
    if peak != 0:
        while True:
            if twentieth > _u32(hist[lo]):
                break
            lo -= 1
            if lo == 0:
                break
    skirt = peak - lo

    tenth = _mulhi_shr(peak_count, 0xCCCCCCCD, 35)
    cap = peak + 50
    if _u32(cap) > 0xFF:
        cap = 255
    hi = peak
    if peak < cap:
        while True:
            if tenth > _u32(hist[hi]):
                break
            hi += 1
            if hi >= cap:
                break

    span = hi - peak
    if span <= 4 * skirt:
        return hi + _cdiv(span, 2)

    half = peak_count >> 1
    if peak >= 255:
        return peak
    j = peak
    while True:
        if half > _u32(hist[j]):
            return j
        j += 1
        if j >= 255:
            return j


def vendor_ones_runs(ones, first: int, last: int, width: int, bins=None,
                     pp=None):
    """``fcn.10006140`` — runs of ones, plus the LoLim/HiLim bin counts.

    Returns ``(n_runs, bins, records)``:

    * ``n_runs`` is the function's own return value. ``0`` means "refused"
      (see the quirk below), ``-1`` would be the allocation failure the
      vendor reports as error 0xb1/0x8d.
    * ``bins`` is the 3-int block the vendor writes through its third
      argument: ``[in-window, >= HiLim, <= LoLim]``. Note the asymmetry —
      ``<=`` for short and ``>=`` for long, so both limits are *exclusive*
      to the good bin.
    * ``records`` is the run table: ``[left, length, tag]`` per run, tag left
      at 0 for the cascade driver to stamp.

    THE QUIRK, WHICH IS THE VENDOR'S AND IS KEPT: at 0x10006183 the function
    compares its run count against ``ones[first]`` and returns 0 if they are
    equal. For ``ones[first] == 0`` that is the honest "no runs at all" case.
    For ``ones[first] == 1`` it means a strip whose *only* run is the one
    already in progress at ``first`` is reported as no runs at all.

    THE SECOND HALF OF THAT QUIRK, WHICH THIS PORT ORIGINALLY GOT WRONG: on
    that refusal the vendor returns at 0x10006187 **without writing either
    output** — the caller's ``bins`` block (arg2) and its ``*pp`` run-table
    pointer (arg1) keep whatever they held before the call. The port used to
    return a fresh ``[0, 0, 0]``, which is a different thing entirely for any
    caller that reuses one block across several calls — and ``fcn.100072c0``'s
    threshold search is exactly such a caller. The golden harness could not
    see the difference because it allocated a freshly-zeroed block per call;
    it now also drives a shared block across a refusing call.

    Pass ``bins`` (a 3-list) and ``pp`` (a 1-list holding the run table) to
    get the vendor's real in/out semantics. Omit them and they are created
    fresh, which is the old behaviour and is right for a one-shot call.
    """
    if bins is None:
        bins = [0, 0, 0]
    if pp is None:
        pp = [[]]
    o = [int(v) for v in np.asarray(ones).ravel()]
    n_runs = o[first]
    for i in range(first, last):
        if o[i] < o[i + 1]:
            n_runs += 1
    if o[first] == n_runs:
        return 0, bins, pp[0]

    recs = [[0, 0, 0] for _ in range(n_runs)]
    if n_runs > 0:
        recs[0][0] = first
    prev = o[first]
    j = 0
    cur = 1
    for i in range(first, last + 1):
        v = o[i]
        if v == prev:
            cur += 1
        else:
            prev = v
            if v == 0:
                recs[j][1] = cur
                j += 1
            else:
                recs[j][0] = i
            cur = 1
    if prev == 1 and n_runs > 0:
        recs[j][1] = cur

    lo, hi = vendor_limits(width)
    bins[0] = bins[1] = bins[2] = 0
    for k in range(n_runs):
        length = recs[k][1]
        if length <= lo:
            bins[2] += 1
        elif length >= hi:
            bins[1] += 1
        else:
            bins[0] += 1
    pp[0] = recs
    return n_runs, bins, recs


def vendor_look_for_nice_pictures(records, n_runs: int, pitch: int, width: int,
                                  left_bound: int, right_bound: int,
                                  check_edges: int = 0, edges=(),
                                  no_edge_data: int = 0):
    """``fcn.10006930`` — phase 1, ``LookForNicePictures``.

    Returns ``(placements, count)`` where ``placements`` maps a **slot index**
    to ``(left, width)`` and ``count`` is the number of pictures the vendor
    counts as found. The slot index is the vendor's own:
    ``(2 * left) / pitch``, truncated (0x100069c8) — the output is a sparse,
    position-indexed array, not a list, which is why the cascade driver walks
    it skipping entries whose left or width is zero (0x10006ed8-0x10006ee6).

    THREE THINGS THIS DOES THAT ``frame_cascade``'s PHASE 1 DOES NOT, all read
    off the real function body, none of them cosmetic:

    1. **It does not use the run's own bounds as the frame.** The frame starts
       at ``run.left + (run.length - width) / 3`` and is exactly ``width``
       long (0x100069a6-0x100069e5). One third of the slack goes in front,
       two thirds behind. ``frame_cascade`` emits the raw run, so on any run
       that is not exactly ``width`` long BOTH edges differ.
    2. **It splits a double frame in phase 1.** A run whose length lands in
       ``(LoLim + pitch, HiLim + pitch)`` — two frames with the gap between
       them missed — is placed as two frames right here, the second at
       ``run.left + pitch`` (0x100069ed-0x10006a9a). ``frame_cascade`` leaves
       that to phase 2 and marks the result ``IN_BETWEEN``, so the phase
       attribution differs as well as the boundary.
    3. **Both bounds are hard.** ``left`` is pushed to ``left_bound + 1`` if
       it would land at or before ``left_bound``; ``width`` is cut to
       ``right_bound - left - 1`` if the frame would reach ``right_bound``.

    ``check_edges`` is the vendor's ``this+0xca4``. Non-zero makes each
    placement run through ``fcn.10006310`` (0x10006a54 and 0x10006aa8, one per
    emit site); a rejection zeroes the slot AND suppresses the count
    increment, so a rejected candidate leaves a ``(0, 0)`` hole rather than
    disappearing. This used to be the module's documented "not modelled"
    restriction — ``vendor_candidate_valid`` closes it.
    """
    lo, hi = vendor_limits(width)
    out: dict[int, tuple[int, int]] = {}
    count = 0

    def _emit(left: int) -> None:
        nonlocal count
        if left <= left_bound:
            left = left_bound + 1
        idx = _cdiv(2 * left, pitch)
        w = width if (left + width) < right_bound else (right_bound - left - 1)
        if check_edges != 0:
            rec = [left, w, 0]
            if vendor_candidate_valid(rec, edges, no_edge_data) == 0:
                out[idx] = (rec[0], rec[1])
                return
        out[idx] = (left, w)
        count += 1

    for k in range(n_runs):
        left, length = records[k][0], records[k][1]
        if lo < length < hi:
            _emit(left + _cdiv(length - width, 3))
        elif (lo + pitch) < length < (hi + pitch):
            _emit(left + _cdiv(length - pitch - width, 3))
            _emit(left + pitch)
    return out, count


def vendor_look_in_between_ends(slots, pitch: int, width: int,
                                first: int, last: int) -> int:
    """``fcn.100063d0`` — phase 2, ``FramingLookInBetweenEnds``.

    ``__stdcall`` (``ret 0x18``, six args, **no** ``this``):

        fcn.100063d0(slots, pitch, width, &count, first_slot, last_slot)

    ``slots`` is the SAME slot-indexed array phase 1 writes — 12 bytes per
    entry, ``[left, width, tag]``, indexed by ``(2*left)/pitch``. This
    function reads it and writes back into it **in place**, so the port takes
    a mutable ``list[list[int]]`` and mutates it too. It returns the number of
    frames it placed (the vendor increments ``*arg3``; the register the vendor
    happens to leave in ``eax`` is not an answer and is not modelled).

    WHAT IT ACTUALLY DOES, off the real body:

    * It walks slot indices ``first+1 .. last`` and keeps a cursor ``p`` on
      the last slot that had **both** ``left != 0`` and ``width != 0``
      (0x10006410 / 0x1000641c). ``p`` starts at ``first`` unconditionally,
      valid or not.
    * For each such pair it takes the **centre-to-centre** distance
      ``span = (cl + cw/2) - (pl + pw/2)`` (0x10006429-0x10006447) — centres,
      not left edges, and each half-width truncated toward zero.
    * ``k = span / pitch``, then ``k -= 1`` when ``span % pitch < pitch/4``
      (0x1000645b-0x1000646e). So a remainder in the bottom quarter of a
      pitch does not buy another frame. All three divisions truncate toward
      zero.
    * If ``k > 0`` it lays ``k`` frames at ``pl + j*step`` for ``j = 1..k``,
      ``step = span / (k + 1)`` (0x10006473-0x100064a7) — evenly divided
      across the real gap, NOT stepped at the nominal pitch. Each lands in
      slot ``(2*left)/pitch`` and is stamped with the caller's ``width``.

    Note the ``p`` cursor advances to ``c`` whenever ``c`` was valid, even
    when ``k <= 0`` placed nothing (0x10006471 -> 0x100064b1).
    """
    count = 0
    if first + 1 > last:
        return count
    p = first
    for c in range(first + 1, last + 1):
        cl, cw = int(slots[c][0]), int(slots[c][1])
        if cl == 0 or cw == 0:
            continue
        pl, pw = int(slots[p][0]), int(slots[p][1])
        span = cl + _cdiv(cw, 2) - pl - _cdiv(pw, 2)
        k = _cdiv(span, pitch)
        if (span - k * pitch) < _cdiv(pitch, 4):
            k -= 1
        if k > 0:
            step = _cdiv(span, k + 1)
            left = pl + step
            for _ in range(k):
                idx = _cdiv(2 * left, pitch)
                slots[idx][0] = left
                slots[idx][1] = width
                count += 1
                left += step
        p = c
    return count


def vendor_blindly_place_pictures(slots, pitch: int, width: int,
                                  n_lines: int, count_in: int = 0) -> int:
    """``fcn.10006720`` — phase 5, ``FramingBlindlyPlacePictures``.

    ``__thiscall`` (``ret 0xc``): ``fcn.10006720(this; slots, pitch, width)``.
    ``n_lines`` is not an argument — the vendor fetches it through its own
    vtable slot ``[vt+0x20]`` (0x10006744), the same call ``fcn.10006870``
    makes. ``count_in`` is the running total already in ``this+0xc9c``, which
    this function increments rather than sets; the port returns the new total.

    Unlike phases 1-4 this writes the slot array **sequentially from index
    0**, not by ``(2*left)/pitch``. Blind placement has no measured left edge
    to index by.

    THE BODY, off the real function:

    * ``half = (pitch - width) / 2`` (0x1000672f-0x10006742), truncated toward
      zero — the frame is centred in its pitch.
    * ``remaining = n_lines - 1``. Nothing at all happens if that is ``<= 0``.
    * The main loop places ``(j*pitch + half, width)`` while
      ``remaining > pitch + 4``, decrementing ``remaining`` by ``pitch`` each
      time (0x1000674e-0x10006792). The ``+ 4`` is only in the loop guard:
      ``ebp`` is reloaded from the ``pitch`` argument at the top of every
      iteration (0x1000675f), so the ``add ebp, 4`` at 0x1000678a never
      compounds. A pitch that grows by 4 per frame would be a plausible
      misreading of this and it is not what the code does.
    * Then ONE trailing frame, placed only when ``width/2 < remaining``
      (0x10006794-0x100067a3): ``left = j*pitch + half`` and width
      ``(n_lines - 1) - left - 4`` — the leftover, minus four lines, so the
      last frame is short rather than nominal.
    * Finally every entry ``0 .. count-1`` with ``width > 0`` and ``tag == 0``
      is stamped ``tag = 9`` (0x10006828). That stamp is a real output: it is
      how the vendor marks a blind placement in the record itself, in addition
      to the ``0x800`` scan warning its caller ORs in at 0x10007b1b or
      0x10007d35.

    The three ``DXCode.txt`` log calls (0x10047fb6 / 0x10047efc / 0x10047eab)
    are pure side effect and are stubbed in the harness.
    """
    count = count_in
    half = _cdiv(pitch - width, 2)
    pos = 0
    placed = 0
    remaining = n_lines - 1
    if remaining > 0:
        if (pitch + 4) < remaining:
            while True:
                slots[placed][0] = pos + half
                slots[placed][1] = width
                remaining -= pitch
                count += 1
                pos += pitch
                placed += 1
                if not (remaining > pitch + 4):
                    break
        if _cdiv(width, 2) < remaining:
            pos += half
            slots[placed][0] = pos
            slots[placed][1] = (n_lines - 1) - pos - 4
            count += 1
    for k in range(count):
        if slots[k][1] > 0 and slots[k][2] == 0:
            slots[k][2] = 9
    return count


def vendor_edge_at(edges, i: int) -> int:
    """``fcn.10013960`` — the film-edge-mark accessor, 27 bytes, 3 blocks.

    Called as ``fcn.10013960(this + 0x78; i)``, so the container's own count
    lives at ``this+0x78+0x83c`` == ``this+0x8b4`` — the exact field
    ``fcn.10006310`` loads directly at 0x10006324, which is what ties the two
    readings together — and its ``int32`` data at ``this+0x8b8``.

    Out of range reads **0**, not an exception and not a clamp (0x1001396c).
    The test is ``count > i`` only: a negative index is not caught here and
    would index before the array. ``fcn.10006310`` never passes one.
    """
    return int(edges[i]) if i < len(edges) else 0


def vendor_candidate_valid(rec, edges, no_edge_data: int = 0) -> int:
    """``fcn.10006310`` — the per-candidate film-edge validity test.

    ``__thiscall``: ``fcn.10006310(this; &rec)``. ``rec`` is one 12-byte slot
    record ``[left, width, tag]`` and is **mutated**: on rejection the vendor
    zeroes ``left`` and ``width`` in place (0x100063a4/0x100063aa) before
    returning 0. That is the mechanism by which a rejected candidate vanishes
    from the slot array, and it is why phases 3 and 4 can write a record and
    then have it disappear.

    ``no_edge_data`` is ``this+0xdc``. Non-zero short-circuits to **accept**
    at 0x1000631b without reading the marks at all — the bypass the golden
    harness has always asserted for phase 1.

    Accept requires, for some mark index ``k``:

        rec.left <= edge[k]                                  (0x1000634f)
        edge[k]  <= rec.left + rec.width                     (0x10006359)
        edge[k]  <= rec.left + rec.width/4                   (0x10006368)
        rec.left + 3*rec.width/4 <= edge[k+1]                (0x1000638c)
        edge[k+1] <= rec.left + rec.width                    (0x10006392)

    i.e. one mark inside the first quarter of the frame and the next mark
    inside the last quarter — a perforation pair straddling the frame. Both
    quarter divisions truncate toward zero. ``edge[k+1]`` for the last ``k``
    reads 0 through ``vendor_edge_at``'s out-of-range rule, so the final
    iteration can only accept when ``rec.left + 3*rec.width/4 <= 0``.

    With no marks at all (``count <= 0``) the loop is skipped entirely and the
    record is zeroed (0x1000633a) — so an object with ``this+0xdc == 0`` and
    an empty mark list rejects **everything**.
    """
    if no_edge_data != 0:
        return 1
    n = len(edges)
    for k in range(n):
        c = vendor_edge_at(edges, k)
        left, width = int(rec[0]), int(rec[1])
        if left > c:
            continue
        if c > left + width:
            continue
        if c > left + _cdiv(width, 4):
            continue
        d = vendor_edge_at(edges, k + 1)
        if left + _cdiv(3 * width, 4) > d:
            continue
        if d <= left + width:
            return 1
    rec[0] = 0
    rec[1] = 0
    return 0


def vendor_gap_admissible(records, n_runs: int, a: int, b: int,
                          slack: int) -> int:
    """``fcn.10006630`` — the "is there really room out there" predicate.

    ``__stdcall`` (``ret 0x14``): ``fcn.10006630(records, n, a, b, slack)``.
    Phases 3 and 4 both call it *before* doing any search, and both abandon
    the whole phase when it answers 0 (0x10006b6d, 0x10006d20). It is a pure
    function of the run table; it touches nothing else.

    It has three limbs, chosen by ``b`` against ``a``:

    * ``b > a`` (looking forward, which is ``LookAtEnd``): find the first run
      whose right edge reaches ``a``. If none does, the answer is whether the
      LAST run's right edge reaches ``b``. Otherwise accept when that run
      starts within ``20*slack`` of ``a``; failing that, accept only when
      ``b - 10`` is still past that run's right edge (0x100066a2 — the
      constant really is a bare 10, added as ``0xfffffff6``).
    * ``b == a`` — always 0 (0x100066b5 ``jge``).
    * ``b < a`` (looking back, which is ``LookAtBeginning``): scan runs from
      the last one down for the first whose ``left + 2*slack`` is at or below
      ``a``. None -> 0. Otherwise accept when ``a - width - left <= 20*slack``;
      failing that, accept only when that run's ``left`` is past 10.

    NOT MODELLED, because the vendor does not guard it: with ``n_runs == 0``
    the ``b > a`` limb falls into its ``i == n`` limb and reads
    ``records[-1]`` — one record *before* the array. That is a real
    out-of-bounds read in TLB.dll, not a port omission; the harness keeps
    ``n_runs >= 1`` rather than pretend to reproduce it.
    """
    if b > a:
        i = 0
        if n_runs > 0:
            while True:
                if records[i][1] + records[i][0] >= a:
                    break
                i += 1
                if i >= n_runs:
                    break
        if i == n_runs:
            last = records[n_runs - 1]
            return 1 if (last[0] + last[1]) >= b else 0
        if 20 * slack >= records[i][0] - a:
            return 1
        right = records[i][0] + records[i][1]
        return 0 if (b - 10) <= right else 1
    if b == a:
        return 0
    i = n_runs - 1
    if i >= 0:
        while True:
            if a >= records[i][0] + 2 * slack:
                break
            i -= 1
            if i < 0:
                break
    if i == -1:
        return 0
    left, width = records[i][0], records[i][1]
    if 20 * slack >= a - width - left:
        return 1
    return 0 if left <= 10 else 1


def vendor_best_window(win: int, n: int, data, sums, start: int) -> int:
    """``fcn.100064e0`` — the sliding-window search phases 3 and 4 place with.

    ``__thiscall``, but ``this`` is touched only to report a malloc failure
    (0x1000652d), so the port takes none:

        fcn.100064e0(this; win, n, data, sums, start)

    For each of ``n`` candidate offsets it sums ``win`` consecutive entries of
    ``data`` starting at ``start + i``, writes that sum to ``sums[i]``
    (0x10006596-0x100065a8 — the caller's array is a real output, not scratch)
    and keeps the offset with the largest sum. Returns ``start + i`` for the
    winner, or ``start + n/2`` when every sum was zero (0x10006612).

    TWO THINGS THAT LOOK LIKE DETAIL AND ARE NOT:

    1. **The sums are compared UNSIGNED** — ``jb``/``ja`` at
       0x100065b6/0x100065b8, not ``jl``/``jg``. On the vendor's own "ones"
       data every sum is >= 0 so it never shows; on any signed input a single
       negative sum wins outright. Modelled here with an explicit mask rather
       than left to Python's arbitrary-precision ints.
    2. **Ties break toward the CENTRE.** The vendor builds a scratch array of
       ``|i - n/2|`` (0x10006580-0x1000658d, from a countdown and an
       up-counter, not an abs) and on an equal sum takes the new offset only
       when its distance is strictly smaller (0x100065c1 ``jge``). So a flat
       run of equal density resolves to the middle of the search span, and
       the FIRST such offset wins among equals at equal distance.
    """
    half = _cdiv(n, 2)
    best_sum = 0
    best_pos = 0
    best_w = half
    for i in range(n):
        w = (i - half) if i > half else (half - i)
        s = 0
        for j in range(win):
            s += int(data[start + i + j])
        s &= 0xFFFFFFFF
        sums[i] = s if s < 0x80000000 else s - 0x100000000
        if s > best_sum or (s == best_sum and w < best_w):
            best_sum = s
            best_pos = start + i
            best_w = w
    if best_sum == 0:
        return start + half
    return best_pos


#: Both phase 3 and phase 4 take eleven ``__stdcall`` arguments on top of
#: ``this``. r2's own ``arg_NNh`` names for these two functions are NOT usable
#: — it emits ``arg_28h`` and ``arg_28h_2`` for two different slots and
#: rebases inconsistently across the reused argument slots. Every offset in
#: the two ports below was recovered by tracking ``esp`` by hand from the
#: prologue and then confirmed bit-exact by the golden harness, which is the
#: only reason to believe any of it.
#:
#:     a0  slots        the phase-1-indexed output array, 12 bytes/entry
#:     a1  data         the "ones" array the window search sums
#:     a2  sums         the search's per-offset sum output (a real output)
#:     a3  records      the run table, for the fcn.10006630 pre-test
#:     a4  n_runs
#:     a5  pitch
#:     a6  width
#:     a7  &count
#:     a8  start        the already-placed edge to walk away from
#:     a9  bound        right bound (phase 3) / left bound (phase 4)
#:     a10 skip_gapok   NON-zero skips the fcn.10006630 pre-test entirely

def vendor_look_at_end(slots, data, sums, records, n_runs: int, pitch: int,
                       width: int, count, start: int, right_bound: int,
                       skip_gapok: int, edges=(), no_edge_data: int = 0) -> int:
    """``fcn.10006ae0`` — phase 3, ``LookAtEnd``.

    Walks forward from ``start`` placing one frame per pitch until it runs out
    of film. ``count`` is a one-element mutable (the vendor's ``int *``).
    Returns the vendor's own return value: 1 on every normal path, 0 only on
    the ``fcn.100064e0`` malloc failure, which the harness cannot reach.

    Each step:

    * Loop while ``pos < right_bound - width/2`` (0x10006b1f, and again at
      0x10006bfc). ``pos`` starts at ``start + (pitch - width)/2``.
    * Unless ``skip_gapok``, ``fcn.10006630(records, n, pos,
      min(pos+pitch, right_bound), pitch-width)`` must pass or the WHOLE phase
      stops — it does not skip one frame and carry on (0x10006b6d).
    * With ``right_bound - pos >= (pitch-width)/2 + pitch`` it searches:
      ``fcn.100064e0`` over ``pitch-width`` offsets of a ``width``-wide window
      starting at ``pos``. The winner goes in slot ``(2*best)/pitch``, width
      clipped to ``right_bound - best`` if it would overrun.
    * Otherwise ONE last frame, and only if ``right_bound - pos >=
      pitch/2 + (pitch-width)/2``: at ``pos + (pitch - width)`` — stepped, not
      searched — and then the phase ends regardless (0x10006c11-0x10006c72).
    * Every placement is passed through ``fcn.10006310``; a rejection zeroes
      the record and ends the phase.

    The next ``pos`` is ``rec.left + rec.width + (pitch-width)/2``, i.e. read
    back out of the record after any clipping, not tracked independently.
    """
    half = _cdiv(pitch - width, 2)
    pos = half + start
    limit = right_bound - _cdiv(width, 2)
    while pos < limit:
        b = pos + pitch if right_bound >= pos + pitch else right_bound
        if skip_gapok == 0:
            if vendor_gap_admissible(records, n_runs, pos, b,
                                     pitch - width) == 0:
                return 1
        if (right_bound - pos) >= (half + pitch):
            best = vendor_best_window(width, pitch - width, data, sums, pos)
            if best < 0:
                return 0
            rec = slots[_cdiv(2 * best, pitch)]
            rec[0] = best
            rec[1] = (width if (best + width) < right_bound
                      else right_bound - best)
            if vendor_candidate_valid(rec, edges, no_edge_data) == 0:
                return 1
            count[0] += 1
            pos = rec[1] + rec[0] + half
        else:
            if (right_bound - pos) < (_cdiv(pitch, 2) + half):
                return 1
            pos += pitch - width
            rec = slots[_cdiv(2 * pos, pitch)]
            rec[0] = pos
            rec[1] = (width if (pos + width) < right_bound
                      else right_bound - pos)
            if vendor_candidate_valid(rec, edges, no_edge_data) == 0:
                return 1
            count[0] += 1
            return 1
    return 1


def vendor_look_at_beginning(slots, data, sums, records, n_runs: int,
                             pitch: int, width: int, count, start: int,
                             left_bound: int, skip_gapok: int, edges=(),
                             no_edge_data: int = 0) -> int:
    """``fcn.10006ca0`` — phase 4, ``LookAtBeginning``.

    The mirror of ``vendor_look_at_end``, walking backwards, and NOT a
    reflection of it in two places that matter:

    1. **The searched placement is not width-clipped.** Phase 3 cuts a frame
       that would overrun ``right_bound`` (0x10006bc5); phase 4 writes the
       nominal ``width`` unconditionally (0x10006d71). Only its *final*
       stepped frame is ever shortened.
    2. **The final stepped frame has two forms** (0x10006dce). If
       ``pos - (pitch-width)/2 - width`` still clears ``left_bound`` it is
       placed there at full width; otherwise it is pinned to
       ``left_bound + 1`` and shortened to ``pos - (left_bound+1) -
       (pitch-width)/2`` when it would reach ``pos - (pitch-width)/2``.
       Phase 3 has no equivalent of the pin.

    ``pos`` starts at ``start - (pitch-width)/2`` and the loop runs while
    ``left_bound < pos``. The next ``pos`` is ``rec.left - (pitch-width)/2``.
    """
    half = _cdiv(pitch - width, 2)
    pos = start - half
    while left_bound < pos:
        b = pos - pitch if left_bound <= pos - pitch else left_bound
        if skip_gapok == 0:
            if vendor_gap_admissible(records, n_runs, pos, b,
                                     pitch - width) == 0:
                return 1
        if (pos - left_bound) >= (half + pitch):
            best = vendor_best_window(width, pitch - width, data, sums,
                                      pos - pitch)
            if best < 0:
                return 0
            rec = slots[_cdiv(2 * best, pitch)]
            rec[0] = best
            rec[1] = width
            if vendor_candidate_valid(rec, edges, no_edge_data) == 0:
                return 1
            count[0] += 1
            pos = rec[0] - half
        else:
            if (pos - left_bound) < (_cdiv(pitch, 2) + half):
                return 1
            cand = pos - half - width
            if left_bound >= cand:
                left = left_bound + 1
                rec = slots[_cdiv(2 * left, pitch)]
                rec[0] = left
                rec[1] = (width if (left + width) < (pos - half)
                          else pos - left - half)
            else:
                rec = slots[_cdiv(2 * cand, pitch)]
                rec[0] = cand
                rec[1] = width
            if vendor_candidate_valid(rec, edges, no_edge_data) == 0:
                return 1
            count[0] += 1
            return 1
    return 1


def vendor_framing_driver(slots, data, sums, records, n_runs: int,
                          left_bound: int, right_bound: int, n_slots: int,
                          pitch: int, width: int, skip_gapok: int, warn,
                          check_edges: int = 0, edges=(),
                          no_edge_data: int = 0) -> int:
    """``fcn.10006e70`` — the four-phase cascade driver.

    ``__thiscall``, eleven stdcall args, ``ret 0x2c``, in this order (again
    recovered by hand-tracking ``esp``; r2's ``arg_NNh`` names for this
    function are unusable):

        a0 data   a1 sums   a2 records  a3 n_runs   a4 left_bound
        a5 right_bound   a6 slots   a7 n_slots   a8 pitch   a9 width
        a10 skip_gapok

    ``warn`` is a one-element mutable standing in for ``this+0x6ca8``, the
    ``SCAN_WARNINGS_000`` accumulator. Returns the final frame count, or -1
    if phase 3 or 4 reported the ``fcn.100064e0`` allocation failure.

    THINGS THIS ESTABLISHES THAT WERE PREVIOUSLY INFERENCE:

    * **The phase tags are 1, 2, 4, 3 — not 1, 2, 3, 4.** ``LookAtEnd`` stamps
      ``tag = 4`` (0x10007158) and ``LookAtBeginning`` stamps ``tag = 3``
      (0x10007268). Phase 5 stamps 9 (0x10006828). Anything that read the tag
      as a phase ordinal would swap phases 3 and 4.
    * **The scan between phase 1 and phase 2 is what defines the working
      bounds.** It walks slots ``0 .. n_slots-1``, zeroing every ``tag`` on
      the way (0x10006ed8), and records the FIRST and LAST slot with both
      ``left != 0`` and ``width != 0``. Phase 3 then starts from the last
      one's RIGHT edge (``left + width``) and phase 4 from the first one's
      LEFT edge; if nothing is valid those default to the caller's
      ``right_bound`` and ``left_bound``.
    * **Phase 2 only runs with two or more frames already placed**
      (0x10006fab ``cmp esi, 2``), and phases 3 and 4 only run when the count
      after phase 2 is strictly positive (0x1000709c). The module docstring
      already claimed the latter; this is the code.
    * **The warning bit is set by comparing counts across each phase**, not
      by whether a phase ran: 0x100 if phase 2 raised the count, 0x200 if
      phase 3 did, 0x400 if phase 4 did.
    * **Each tag pass only stamps records whose tag is still 0** — except
      phase 1's, which stamps unconditionally because the scan just zeroed
      them all. So the earliest phase to place a frame owns its tag.
    * ``skip_gapok`` (a10) reaches ONLY phases 3 and 4. Phase 1's own
      edge-validity switch is ``this+0xca4``, a member, not this argument.

    ONE DELIBERATE DIVERGENCE, stated rather than hidden: the phase-1
    write-back below is bounds-checked against ``len(slots)``. The vendor is
    not — a slot index of ``(2*left)/pitch`` past the caller's array is an
    out-of-bounds write in TLB.dll, and a negative one would silently wrap in
    Python instead. The check exists so a bad caller gets nothing rather than
    corruption; it is never reached under the golden harness, whose corpora
    keep every index in range, so it is a guard and not a verified behaviour.
    """
    count = [0]
    placements, c = vendor_look_for_nice_pictures(
        records, n_runs, pitch, width, left_bound, right_bound,
        check_edges, edges, no_edge_data)
    for idx, (left, w) in placements.items():
        if 0 <= idx < len(slots):
            slots[idx][0] = left
            slots[idx][1] = w
    count[0] = c

    first, last = n_slots - 1, 0
    left_edge, right_edge = left_bound, right_bound
    for i in range(n_slots):
        left = slots[i][0]
        slots[i][2] = 0
        if left == 0:
            continue
        w = slots[i][1]
        if w == 0:
            continue
        if i <= first:
            first = i
            left_edge = left
        if i >= last:
            last = i
            right_edge = w + left

    if first <= last:
        for k in range(first, last + 1):
            if slots[k][1] > 0:
                slots[k][2] = 1

    prev = count[0]
    if count[0] >= 2:
        count[0] += vendor_look_in_between_ends(slots, pitch, width,
                                                first, last)
    if first <= last:
        for k in range(first, last + 1):
            if slots[k][1] > 0 and slots[k][2] == 0:
                slots[k][2] = 2
    if prev < count[0]:
        warn[0] |= 0x100
        prev = count[0]

    if count[0] <= 0:
        return count[0]

    if vendor_look_at_end(slots, data, sums, records, n_runs, pitch, width,
                          count, right_edge, right_bound, skip_gapok,
                          edges, no_edge_data) == 0:
        return -1
    if last < n_slots:
        for k in range(last, n_slots):
            if slots[k][1] > 0 and slots[k][2] == 0:
                slots[k][2] = 4
    if prev < count[0]:
        warn[0] |= 0x200
        prev = count[0]

    if vendor_look_at_beginning(slots, data, sums, records, n_runs, pitch,
                                width, count, left_edge, left_bound,
                                skip_gapok, edges, no_edge_data) == 0:
        return -1
    if first > 0:
        for k in range(0, first):
            if slots[k][1] > 0 and slots[k][2] == 0:
                slots[k][2] = 3
    if prev < count[0]:
        warn[0] |= 0x400
    return count[0]


def vendor_framing_entry(rgb_u8, slots, n_slots: int, pitch: int, width: int,
                         first: int, tail_margin: int, skip_gapok: int, warn,
                         invert: int = 1, check_edges: int = 0, edges=(),
                         no_edge_data: int = 0):
    """``fcn.100072c0`` — the whole framing entry, threshold search included.

    ``__thiscall``, seven stdcall args, ``ret 0x1c``:

        fcn.100072c0(this; skip_gapok, n_slots, slots, pitch, width, first,
                     tail_margin)

    ``rgb_u8`` stands in for the object's own per-line 3-byte RGB summary at
    ``this+0x6c``; the vendor's line count comes from ``[vt+0x20]``. Returns
    ``(retval, ones, threshold, n_runs)``: ``retval`` is the cascade's frame
    count, or -1 on any of the six error limbs.

    THE SHAPE, all of it read off the real body with ``esp`` tracked by hand:

    1. ``LoLim = width*95/100``, ``HiLim = width*115/100`` (0x100072d4) — for
       the log only; the binning is ``fcn.10006140``'s own.
    2. ``last = n_lines - tail_margin - 1``. Three ``VirtualAlloc`` +
       ``VirtualLock`` buffers of ``4*n_lines`` each: the trace, the ones
       array, and a scratch that later becomes the cascade's ``sums``.
    3. ``fcn.10006870`` fills the trace; ``fcn.10005ce0`` histograms it over
       ``[first, last]``.
    4. First threshold: ``fcn.10005d20`` with ``forced = 0`` (the modal-peak
       rule). Then ``fcn.10006140``. **If that finds fewer than two runs the
       whole threshold is recomputed with ``forced = -1``** — the
       2nd-percentile rule (0x10007570). So the two rules in
       ``vendor_pick_threshold`` are not alternatives a caller picks between:
       the percentile rule is the vendor's *fallback* when the modal rule
       fails to produce a usable binarisation.
    5. **The search, upward.** While ``t < 250`` and ``bins[1] > 0`` (long
       runs remain, i.e. frames are still merged) step ``t += 2``, re-binarise
       and re-extract. Keep the ``t`` with the largest in-window count
       ``bins[0]``; stop early if ``bins[0]`` falls below the last recorded
       plateau.
    6. **Then it goes back to the FIRST threshold** (0x10007672 re-runs
       ``fcn.10005d20`` with the *initial* ``t``, not the best one) and
       **searches downward** while ``t < 256`` and either ``bins[2] > 0``
       (short runs remain) or fewer than two runs were found, stepping
       ``t -= 2`` and stopping at ``t <= 25``. Same best/plateau bookkeeping,
       except the plateau tracker is reset at the turnaround and the best is
       NOT — so the downward leg has to beat the upward leg outright.
    7. A final re-binarise at the best ``t``, a final ``fcn.10006140``, the
       ``Framing Ones`` log block, then ``fcn.10006e70``.

    So the ``25..256`` bounds and the ``±2`` step are real, and so is the
    asymmetry: 250 caps the upward leg, 256 the downward one.

    ONE INPUT CLASS WHERE THE VENDOR HAS NO SINGLE ANSWER — worth knowing
    before anyone treats a vendor frame list as ground truth. The ``bins``
    block is a **stack local** of ``fcn.100072c0`` whose address is handed to
    ``fcn.10006140``, and ``fcn.10006140``'s refusal limb (0x10006185) returns
    without writing it. When the very FIRST extraction refuses — a flat or
    near-flat strip, where the modal threshold produces one run or none — the
    threshold search then steers on whatever the caller happened to leave on
    the stack. Measured under Unicorn on one such roll: 0, 11 and 12 frames on
    three otherwise identical runs, flipping as soon as one unrelated call had
    run first. This port computes the zero-initialised reading, and the golden
    harness zeroes the stack before every call so the comparison means
    something. On real hardware such a roll's framing is genuinely a function
    of what PSI did immediately beforehand.
    """
    n_lines = len(rgb_u8)
    trace = [int(v) for v in vendor_framing_trace(rgb_u8, invert=bool(invert))]
    # The vendor sizes these at exactly 4*n_lines bytes but reads past the end
    # of the ones array: ``fcn.100064e0``, driven by phase 3 near the film's
    # right bound, sums ``data[start + i + j]`` up to ``pitch`` int32s beyond
    # ``n_lines``. It gets away with it because ``VirtualAlloc(MEM_COMMIT)``
    # hands back whole zero-filled pages, so the overrun reads zeros. Model
    # that here rather than let Python raise (or, worse, wrap on a negative
    # index) — an overrun that reads zeros IS the vendor's behaviour, and two
    # rolls in the golden corpus depend on it.
    n_alloc = (((4 * n_lines) + 0xFFF) & ~0xFFF) // 4
    ones = [0] * n_alloc
    sums = [0] * n_alloc
    last = n_lines - tail_margin - 1
    hist = [int(v) for v in vendor_line_histogram(np.asarray(trace),
                                                  first, last)]
    bins = [0, 0, 0]
    pp = [[]]

    def extract():
        return vendor_ones_runs(ones, first, last, width, bins, pp)[0]

    def binarise(forced):
        return vendor_pick_threshold(ones, hist, trace, first, last, forced)

    t0 = binarise(0)
    n = extract()
    if n < 2:
        if n < 0:
            return -1, ones, t0, n
        t0 = binarise(-1)
    else:
        n = extract()
        if n == 0:
            return 0, ones, t0, n
        if n < 0:
            return -1, ones, t0, n

    best_t = t0
    best_bins0 = bins[0]
    plateau = bins[0]
    t = t0
    if t > 0:
        while True:                                   # upward leg
            if t >= 250 or bins[1] <= 0:
                break
            t = binarise(t + 2)
            n = extract()
            if n < 0:
                return -1, ones, t, n
            if bins[0] > best_bins0:
                best_bins0 = plateau = bins[0]
                best_t = t
            elif bins[0] < plateau:
                break
            if t <= 0:
                break

    t = binarise(t0)                                  # back to the start
    n = extract()
    if n < 0:
        return -1, ones, t, n
    plateau = bins[0]
    if t > 25:
        while True:                                   # downward leg
            if t >= 256:
                break
            if not (bins[2] > 0 or n <= 1):
                break
            t = binarise(t - 2)
            n = extract()
            if n < 0:
                return -1, ones, t, n
            if bins[0] > best_bins0:
                best_t = t
                best_bins0 = plateau = bins[0]
            elif bins[0] < plateau:
                break
            if t <= 25:
                break

    t = binarise(best_t)
    n_runs = extract()
    if n_runs < 0:
        return -1, ones, t, n_runs

    ret = vendor_framing_driver(slots, ones, sums, pp[0], n_runs, first, last,
                                n_slots, pitch, width, skip_gapok, warn,
                                check_edges, edges, no_edge_data)
    return ret, ones, t, n_runs


def _i32(v: int) -> int:
    """Truncate to a signed 32-bit register value."""
    v = int(v) & 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


def _udiv(a: int, b: int) -> int:
    """x86 ``div``: 32-bit unsigned quotient. Divide-by-zero is #DE, not 0."""
    return _u32(a) // _u32(b)


#: ``fcn.100245e0``'s switch at 0x1002461b, jump table at 0x10024650: the
#: ``CiPicLoc`` constructor maps its fifth argument — the framing phase tag —
#: onto a small ``obj+0x20`` grade. Tags 2..4 -> 1, 5..6 -> 2, 7..8 -> 3,
#: 9 -> 4, anything else (which for the framing cascade means tag 1, phase 1's
#: own stamp) -> 0. Since the cascade only ever stamps 1, 2, 3, 4 and 9, the
#: grades actually reachable are 0 (phase 1), 1 (phases 2/3/4) and 4 (blind).
_PICLOC_GRADE = {2: 1, 3: 1, 4: 1, 5: 2, 6: 2, 7: 3, 8: 3, 9: 4}


def vendor_picloc_grade(tag: int) -> int:
    """``fcn.100245e0``'s tag -> ``obj+0x20`` grade. See ``_PICLOC_GRADE``."""
    return _PICLOC_GRADE.get(_i32(tag), 0)


def vendor_place_roll_pictures(
        rgb_u8, warn, *,
        skip_gapok: int, place_blindly: int, no_tail_margin: int,
        n_lines: int, line_scale: int, image_rows: int, margin_units: int,
        pitch_raw: int, width_raw: int, margin_divisor: int,
        crop_top: int, crop_left: int, crop_bottom: int, crop_right: int,
        frame_bottom: int, end_anchored: int,
        pictures_in=(), count_in: int = 0,
        malloc_fails: bool = False, new_fails_at: int | None = None,
        invert: int = 1, check_edges: int = 0, edges=(),
        no_edge_data: int = 0):
    """``fcn.100079c0`` (0x100079c0-0x10007f11, 1362 bytes) — the roll caller.

    ``__thiscall``, three stdcall args, ``ret 0xc``:

        fcn.100079c0(this; skip_gapok, place_blindly, no_tail_margin)

    This is the top of the framing chain: the last function whose body is
    framing and nothing else. It sizes the slot array, decides whether to run
    the four-phase cascade (``fcn.100072c0``) or phase 5 blind placement
    (``fcn.10006720``), and then turns the resulting slot array into the
    object's ``CiPicLoc`` list at ``this+0x70``. Above it is
    ``fcn.1002a900``, a general per-strip scan driver that happens to hold the
    cascade-then-blind *policy* — see below — among a great deal else.

    THE DECISION, which is the thing this function exists to make. It is
    **not** a heuristic: **argument 2 alone** selects the branch, at BOTH
    0x10007b09 and 0x10007d27 —

        place_blindly != 0  ->  this->0x6ca8 |= 0x800 ; fcn.10006720
        place_blindly == 0  ->  fcn.100072c0, and -1 out on a negative return

    The *policy* lives one level up, in ``fcn.1002a900`` (the only caller,
    0x1002aba5 and 0x1002abb8): call it once with ``(this->0x380, 0, 0)``; if
    that returns **exactly zero** — cascade ran, found no frames — call it
    again with ``(1, 1, 0)``, i.e. blind. A negative return aborts the roll.
    So "cascade, and blindly place if the cascade found nothing" is a two-call
    protocol in the caller, not a fallback inside this function.

    A CORRECTION TO THE WARNING-SITE COUNT recorded in docs/74 §194.5 and in
    this module's own earlier comment, which said "four sites, three in
    ``fcn.10006e70``, the fourth 0x10007d35". Two things are wrong with that.
    There are **five** sites that OR into ``this+0x6ca8``, not four — and they
    do not all OR the same bit:

        0x1000708b  fcn.10006e70   or eax, 0x100      phase 2 placed something
        0x10007193  fcn.10006e70   or eax, 0x200      phase 3 placed something
        0x1000729f  fcn.10006e70   or [..], 0x400     phase 4 placed something
        0x10007b1b  fcn.100079c0   or edi, 0x800      blind, c98 == 0 model
        0x10007d35  fcn.100079c0   or edi, 0x800      blind, c98 != 0 model

    So **0x800 has exactly two sites and both are here**, one per geometry
    model, and 0x10007b1b — the one nobody had recorded — is the one a real
    F-135 takes whenever ``this->0xc98`` is zero. Verified by searching every
    ``or``-with-0x800 encoding across the whole image: the only other hit,
    0x1000bcbb, ORs a different word in ``fcn.1000b890`` and is not a framing
    warning at all.

    ARGUMENTS AND FIELDS, with esp tracked by hand off the raw body (r2 emits
    ``arg_48h``/``arg_4ch`` for the two *incoming* stack slots and is doubly
    misleading here: the vendor reuses ``[esp+0x48]`` and ``[esp+0x4c]`` — its
    own arguments 1 and 2 — as the collection loop's index and cursor):

    * ``line_scale``   ``[vt+0x24]``. Divides ``this->0xc70`` and
      ``this->0xc74`` into the ``pitch`` and ``width`` the cascade works in,
      and multiplies slot coordinates back into image rows.
    * ``n_lines``      ``[vt+0x20]``, the same slot ``fcn.10006870`` reads.
    * ``image_rows``   ``[vt+0x80]()->[vt+0x20]()``, the destination image's
      row count; every picture's bottom is clamped to ``image_rows - 1``.
    * ``margin_units`` ``[vt+0x10]``, scaled by ``* 0x6338 / this->0xc6c``
      into the head/tail margin. The arithmetic is confirmed; the *units* are
      not — 0x6338 is 25400, which is micrometres per inch, so ``this->0xc6c``
      reads like a micrometres-per-line pitch and ``[vt+0x10]`` like a length
      in inches. That is a plausible reading of two constants, nothing more:
      neither field has been observed on real hardware.
    * ``crop_*``       ``this->0xc88`` / ``0xc8c`` / ``0xc90`` / ``0xc94``.
      What is confirmed is only how they are USED: 0xc88/0xc90 supply a row
      offset and a height and are added to a scaled slot position, 0xc8c/0xc94
      are passed through untouched as the ``CiPicLoc``'s 2nd and 4th fields.
      Calling that a ``(top, left, bottom, right)`` crop rectangle is an
      inference from that use, not a captured fact.
    * ``frame_bottom`` ``this->0xc80``; only ``frame_bottom - crop_bottom`` is
      ever used, and only by the end-anchored model.
    * ``end_anchored`` ``this->0xc98``, which selects that model. It is set
      exactly once in the whole DLL — 0x10004e59, in the ``CiBufferStrip``
      constructor ``fcn.10004df0``, from one of that constructor's five
      arguments — and never written again. So it is a per-strip mode chosen
      when the object is built, not a state the framing code can move. Which
      real F-135 configuration passes what is not established here.

    THE BODY:

    1. ``pitch = this->0xc70 / line_scale``, ``width = this->0xc74 /
       line_scale``, both **unsigned** ``div`` (0x100079f5, 0x10007a0a).
    2. ``n_slots = (2 * n_lines) / pitch``, unsigned, on a ``2 * n_lines``
       that is allowed to wrap. **If that is <= 0 as a signed int the function
       returns 0 immediately** (0x10007a29) — without releasing the existing
       picture list and without zeroing ``this->0xc9c``. That is the one exit
       that leaves the object's previous roll intact.
    3. Otherwise the existing list at ``this+0x70`` is destroyed through
       ``[vt+8]`` and the head nulled, ``this->0xc9c = 0``, and ``12 *
       n_slots`` bytes are ``malloc``ed and zeroed. A failed ``malloc``
       reports error (0xaf, 0x8d) and returns -1.
    4. ``this->0xc98 == 0``: the head/tail margin is computed, but only if
       ``10 * pitch < n_lines`` (unsigned, 0x10007ae0) — on a strip shorter
       than ten frames both margins stay 0. ``first`` gets
       ``margin_units * 25400 / this->0xc6c``; ``tail`` gets the same value
       **only if argument 3 is zero** (0x10007aff). Both of the real call
       sites pass 0, so in production ``tail == first`` always, and argument 3
       is a dead knob that trims the head but not the tail.
       ``this->0xc98 != 0``: no margin is computed at all — the cascade is
       called with ``first = 0, tail = 0`` hardcoded (0x10007d57).
    5. Cascade or blind, per ``place_blindly``.
    6. The collection loop, once per slot, skipping any slot whose length or
       whose left edge is zero (0x10007b95/0x10007b9e, 0x10007dd6/0x10007de1
       — a slot placed at line 0 is discarded, not just an empty one). Each
       surviving slot becomes ``CiPicLoc(top, crop_left, bottom, crop_right,
       tag)`` appended at the tail of ``this+0x70`` (``fcn.100244d0``), and
       ``this->0xc9c`` is incremented. A failed ``operator new`` reports
       (0xaf, 0x8d), frees the slot array, destroys the partial list and
       returns -1.
    7. The slot array is freed and ``this->0xc9c`` returned.

    THE TWO GEOMETRY MODELS, with ``H = crop_bottom - crop_top + 1``:

    ``this->0xc98 == 0`` — start-anchored, and that is all it is::

        top    = line_scale * slot.left + crop_top
        bottom = top + H - 1                    (computed BEFORE the clamp)
        if top < 0:            top = 0
        if bottom >= image_rows: bottom = image_rows - 1

    ``this->0xc98 != 0`` — start-anchored too, except for a leading partial
    frame, and with a minimum height::

        if slot.length < width (UNSIGNED) and slot.left < 5:
            bottom = line_scale * (slot.left + slot.length)
                     - (frame_bottom - crop_bottom)
            top    = bottom - H
        else:
            top    = line_scale * slot.left + crop_top
            bottom = top + H - 1
        clamp as above, then
        if bottom - top < 16 * line_scale:
            if slot.left < 5: bottom = top + 16 * line_scale
            else:             top    = bottom - 16 * line_scale

    i.e. a run that is shorter than a nominal frame AND starts in the first
    five lines is treated as a frame clipped by the start of the strip, and is
    anchored on its *end* instead. Everything else is the same model as above.

    THE DOUBLE COUNT ON THE BLIND PATH IS REAL, and reproduced here rather
    than corrected. ``fcn.10006720`` increments ``this->0xc9c`` once per slot
    it places (0x100067bf), and this function then increments it again once
    per ``CiPicLoc`` it builds from those same slots. So the value returned
    after a blind placement is **twice** the number of pictures actually in
    the list. ``fcn.100072c0`` never touches ``this->0xc9c``, so the cascade
    path returns the honest count. ``fcn.1002a900`` only ever tests the first
    call's return against 0 and for negativity, so nothing downstream in
    TLB.dll notices; a port that consumes the count would.

    ``rgb_u8`` stands in for the object's per-line 3-byte RGB summary at
    ``this+0x6c``, exactly as in ``vendor_framing_entry`` — and it is the same
    uncaptured input, so this function being bit-exact moves ``FRAMING_PORTED``
    no closer to ``True``.

    ``pictures_in`` is the list already hanging off ``this+0x70``.
    ``malloc_fails`` / ``new_fails_at`` drive the two allocation-failure limbs;
    they are real vendor paths and the golden harness exercises them by
    failing the vendor's own allocator on the same call.

    Returns ``(retval, pictures, count_field, n_errors)``: ``pictures`` is the
    list at ``this+0x70`` afterwards, as ``(top, left, bottom, right, tag,
    grade)`` tuples; ``count_field`` is ``this->0xc9c``; ``n_errors`` is how
    many times ``fcn.1001acd0`` was called.
    """
    pictures = list(pictures_in)
    count = int(count_in)
    errors = 0

    pitch = _udiv(pitch_raw, line_scale)
    width = _udiv(width_raw, line_scale)
    n_slots = _udiv(_u32(2 * _u32(n_lines)), pitch)
    if _i32(n_slots) <= 0:                        # 0x10007a29
        return 0, pictures, count, errors

    pictures = []                                 # 0x10007a50-0x10007a5b
    count = 0                                     # 0x10007a63
    if malloc_fails:                              # 0x10007a7d
        return -1, pictures, count, errors + 1

    slots = [[0, 0, 0] for _ in range(n_slots)]
    n_new = 0

    def build(top, bottom, tag):
        """``operator new`` + ``fcn.100245e0`` + ``fcn.100244d0``."""
        nonlocal n_new
        k, n_new = n_new, n_new + 1
        if new_fails_at is not None and k == new_fails_at:
            return False
        pictures.append((_i32(top), _i32(crop_left), _i32(bottom),
                         _i32(crop_right), _i32(tag),
                         vendor_picloc_grade(tag)))
        return True

    if not end_anchored:
        first = tail = 0
        if _u32(10 * pitch) < _u32(n_lines):      # 0x10007ae0, unsigned
            first = _udiv(_u32(margin_units * 0x6338), margin_divisor)
            if not no_tail_margin:                # 0x10007aff
                tail = first
    else:
        first = tail = 0                          # hardcoded at 0x10007d57

    if place_blindly:                             # 0x10007b09 / 0x10007d27
        warn[0] = _i32(_u32(warn[0]) | 0x800)     # 0x10007b1b / 0x10007d35
        count = vendor_blindly_place_pictures(slots, pitch, width, n_lines,
                                              count)
    else:
        rc = vendor_framing_entry(rgb_u8, slots, n_slots, pitch, width, first,
                                  tail, skip_gapok, warn, invert=invert,
                                  check_edges=check_edges, edges=edges,
                                  no_edge_data=no_edge_data)[0]
        if rc < 0:                                # 0x10007c1a / 0x10007d69
            return -1, pictures, count, errors + 1

    height = _i32(crop_bottom - crop_top + 1)
    bottom_margin = _i32(frame_bottom - crop_bottom)
    span = _i32(line_scale << 4)

    for left, length, tag in slots:
        if length == 0 or left == 0:
            continue
        if end_anchored and _u32(length) < _u32(width) and _i32(left) < 5:
            bottom = _i32(_i32(line_scale * _i32(left + length))
                          - bottom_margin)
            top = _i32(bottom - height)
        else:
            top = _i32(line_scale * left + crop_top)
            bottom = _i32(top + height - 1)
        if top < 0:
            top = 0
        if not _i32(image_rows) > bottom:
            bottom = _i32(image_rows - 1)
        if end_anchored and not _i32(bottom - top) >= span:
            if _i32(left) < 5:
                bottom = _i32(top + span)
            else:
                top = _i32(bottom - span)
        if not build(top, bottom, tag):            # 0x10007c67 / 0x10007eab
            return -1, [], count, errors + 1
        count = _i32(count + 1)

    return count, pictures, count, errors


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Contiguous True runs as (start, stop) with stop exclusive."""
    if mask.size == 0:
        return []
    d = np.diff(mask.astype(np.int8))
    starts = list(np.flatnonzero(d == 1) + 1)
    stops = list(np.flatnonzero(d == -1) + 1)
    if mask[0]:
        starts.insert(0, 0)
    if mask[-1]:
        stops.append(mask.size)
    return list(zip(starts, stops))


# --------------------------------------------------------------------------
# The cascade
# --------------------------------------------------------------------------

def frame_cascade(trace: np.ndarray,
                  lines_per_mm: float | None = None,
                  present: np.ndarray | None = None,
                  ones_threshold: float | None = None,
                  variance_floor: float = 0.0,
                  pitch_lines: float | None = None) -> tuple[list[Frame], dict]:
    """Run the vendor's five-phase framing cascade.

    ``pitch_lines`` wins if given; otherwise the pitch is measured from the
    data (``estimate_pitch``); otherwise it falls back to
    ``FRAME_PITCH_MM * lines_per_mm``. See ``estimate_pitch`` for why measuring
    is the default.

    Returns ``(frames, report)``. ``report`` mirrors what the vendor writes
    into ``DXCode.txt``: a per-phase count plus the phase-1 acceptance window.
    """
    trace = np.asarray(trace, dtype=np.float64)
    n = trace.size
    if present is None:
        present = np.ones(n, dtype=bool)

    ones, thr = ones_array(trace, present, ones_threshold)

    pitch_measured = None
    pitch_rejected_reason = None
    if pitch_lines is not None:
        pitch, pitch_source = float(pitch_lines), "given"
    else:
        pitch_measured = estimate_pitch(ones)
        geometry_pitch = (FRAME_PITCH_MM * lines_per_mm
                          if lines_per_mm is not None else None)
        # Cross-check the measurement against geometry when both exist.
        # estimate_pitch has no notion of a frame's expected size and can
        # lock onto a fragment-spacing artifact instead of the real pitch --
        # see PITCH_AGREEMENT_FRAC for the real-capture evidence this
        # tolerance is based on. Geometry is not vendor-derived here either
        # (pakon_decode's transport scale, itself once 1.9x off -- docs/56
        # §8 -- before the MotorSpeedPlus anchor fix), but it is independent
        # of the same ones-array noise that can fool the measurement, which
        # is what matters for a cross-check.
        if (pitch_measured is not None and geometry_pitch is not None and
                abs(pitch_measured - geometry_pitch) >
                PITCH_AGREEMENT_FRAC * geometry_pitch):
            pitch_rejected_reason = (
                f"measured {pitch_measured:.1f} vs geometry {geometry_pitch:.1f} "
                f"({abs(pitch_measured - geometry_pitch) / geometry_pitch:.1%} "
                f"off, over the {PITCH_AGREEMENT_FRAC:.0%} tolerance)")
            pitch, pitch_source = geometry_pitch, "geometry"
        elif pitch_measured is not None:
            pitch, pitch_source = pitch_measured, "measured"
        elif geometry_pitch is not None:
            pitch, pitch_source = geometry_pitch, "geometry"
        else:
            raise ValueError("no pitch: pass pitch_lines or lines_per_mm, "
                             "or give a strip with measurable frame structure")

    # The vendor's Target is the exposed width, which is FRAME_IMAGE_MM of the
    # FRAME_PITCH_MM pitch. Keeping the ratio means the acceptance window is
    # the vendor's regardless of how the pitch was obtained.
    target = pitch * (FRAME_IMAGE_MM / FRAME_PITCH_MM)
    lo_lim = target * LO_LIM_FRAC
    hi_lim = target * HI_LIM_FRAC
    width = int(round(target))

    film_runs = _runs(present)
    if film_runs:
        film_start = film_runs[0][0]
        film_stop = film_runs[-1][1]
    else:
        film_start, film_stop = 0, n

    frames: list[Frame] = []

    # Candidate edges for phases 2-4 to snap to. Those phases are named
    # "Look..." rather than "Place...": they are searches near a predicted
    # position, not blind extrapolation. Blind extrapolation is phase 5, and
    # the vendor gives it a different name and a worse warning for a reason.
    #
    # The cutoff only needs to separate real (if short) frame content from
    # binarisation noise -- it is not the phase-1 acceptance test, so it must
    # not require anything close to a full frame. It used to (0.4 * target,
    # i.e. needing 40% of a frame before a run was even considered). On a real
    # short-strip capture (vendor-duty-fixed-offset-20260813-225308.bin) that
    # excluded a genuine 801-line frame (37.7% of a 2123-line target) sitting
    # right next to nothing but sensor-noise blips topping out at 225 lines
    # (10.6%) -- both figures measured on that capture. Phase 2 then had no
    # real candidate to snap to and filled the gap by blind interpolation
    # instead, which does not know the real run is there and guessed a
    # position 366 lines off it. 0.15 keeps a wide margin over the observed
    # noise ceiling while staying well under any plausible partial frame.
    all_runs = [(a, b) for a, b in _runs(ones) if b - a >= 0.15 * target]
    run_starts = np.array([a for a, _ in all_runs], dtype=np.float64)

    def _overlap(a: Frame, others: list[Frame]) -> int:
        return max((min(a.stop, o.stop) - max(a.start, o.start) for o in others),
                   default=0)

    def place(predicted: float, phase: Phase, placed: list[Frame]) -> Frame:
        """Search near ``predicted`` for a real run; fall back to the pitch.

        A snap is only taken if it does not collide with a frame already
        placed -- otherwise a single strong run can attract two predictions
        and produce overlapping frames.
        """
        raw = Frame(int(round(predicted)), int(round(predicted)) + width, phase)
        if run_starts.size:
            i = int(np.argmin(np.abs(run_starts - predicted)))
            if abs(run_starts[i] - predicted) <= 0.25 * pitch:
                s, e = all_runs[i]
                if not (lo_lim <= e - s <= hi_lim):
                    e = s + width
                # Padding a too-short run out to nominal width extends past
                # what was actually detected, and can run into a frame placed
                # earlier in this same cascade pass -- observed on the capture
                # above, where a genuine 801-line run padded out to 2123 lines
                # reached 593 lines into the next NICE frame. Clip to that
                # neighbour instead of discarding the whole candidate: the
                # *start* s is still real, detected evidence, and is worth
                # keeping even when the padded end is not. This is the same
                # rule the final overlap trim below applies roll-wide; doing
                # it here too means a real start does not lose to a blind
                # guess just because its pad collided with a neighbour.
                for o in placed:
                    if s < o.start < e:
                        e = o.start
                cand = Frame(int(s), int(e), phase)
                if cand.lines > 0 and _overlap(cand, placed) <= 0.1 * width:
                    return cand
        return raw

    # -- phase 1: LookForNicePictures -------------------------------------
    # A run of ones whose length is inside [LoLim, HiLim] and whose content
    # carries enough variance to be a real photograph rather than a blank.
    for start, stop in _runs(ones):
        length = stop - start
        if not (lo_lim <= length <= hi_lim):
            continue
        if variance_floor > 0.0:
            if float(np.var(trace[start:stop])) < variance_floor:
                continue
        frames.append(Frame(start, stop, Phase.NICE))

    if frames:
        # -- phase 2: FramingLookInBetweenEnds ----------------------------
        # Between two confident frames, if the spacing is a near-integer
        # multiple of the pitch, the missing frames sit at that pitch.
        filled: list[Frame] = []
        for a, b in zip(frames, frames[1:]):
            span = b.start - a.start
            k = int(round(span / pitch))
            if k < 2:
                continue
            if abs(span - k * pitch) > 0.5 * pitch:
                continue
            step = span / k
            for j in range(1, k):
                filled.append(place(a.start + j * step, Phase.IN_BETWEEN,
                                    frames + filled))
        frames.extend(filled)
        frames.sort(key=lambda f: f.start)

        taken = {f.start for f in frames}

        # -- phase 3: LookAtEnd -------------------------------------------
        s = frames[-1].start + pitch
        while s + width <= film_stop:
            f = place(s, Phase.AT_END, frames)
            if f.start not in taken:
                frames.append(f)
                taken.add(f.start)
            s = f.start + pitch

        # -- phase 4: LookAtBeginning -------------------------------------
        head = min(f.start for f in frames if f.phase is not Phase.AT_END)
        s = head - pitch
        while s >= film_start:
            f = place(s, Phase.AT_BEGINNING, frames)
            if f.start not in taken:
                frames.append(f)
                taken.add(f.start)
            s = f.start - pitch
    else:
        # -- phase 5: FramingBlindlyPlacePictures -------------------------
        # docs/53 §4.2.1: fires only when the first pass framed zero pictures.
        # No detection at all -- tile the film region at the nominal pitch.
        s = float(film_start)
        while s + width <= film_stop:
            frames.append(Frame(int(round(s)), int(round(s)) + width, Phase.BLIND))
            s += pitch

    frames.sort(key=lambda f: f.start)

    # Frames cannot overlap on film. A snapped run that came out shorter than
    # the acceptance window gets padded to the nominal width, which can push
    # its tail into the next frame's slot; trim rather than let that stand.
    for a, b in zip(frames, frames[1:]):
        if a.stop > b.start:
            a.stop = b.start
    frames = [f for f in frames if f.lines > 0]

    # docs/74 §43: how much of each FINAL window (after the overlap trim
    # above, which can shorten a padded tail) is real "ones" content, not
    # gap. Cheap -- `ones` is already in hand -- and the only place that can
    # see the true per-frame answer, since a frame's own window is not known
    # until the whole cascade (including phases 2-4's snapping and the trim)
    # has run.
    for f in frames:
        f.content_fraction = (float(ones[f.start:f.stop].mean())
                              if f.lines > 0 else 0.0)

    counts = {p.vendor_name: sum(1 for f in frames if f.phase is p) for p in Phase}
    report = {
        "counts": counts,
        "total": len(frames),
        "lo_lim": round(lo_lim, 1),
        "target": round(target, 1),
        "hi_lim": round(hi_lim, 1),
        "pitch": round(pitch, 1),
        "pitch_source": pitch_source,
        "pitch_measured": (round(pitch_measured, 1)
                           if pitch_measured is not None else None),
        "pitch_rejected_reason": pitch_rejected_reason,
        "lines_per_mm_geometry": (round(lines_per_mm, 4)
                                  if lines_per_mm is not None else None),
        "lines_per_mm_implied": round(pitch / FRAME_PITCH_MM, 4),
        "ones_threshold": round(thr, 1),
        "film_start": int(film_start),
        "film_stop": int(film_stop),
        "scan_warnings": int(np.bitwise_or.reduce(
            [int(f.phase) for f in frames]) if frames else 0),
    }
    return frames, report


# --------------------------------------------------------------------------
# Wiring the DLL-ported cascade into the app (docs/74: FRAMING_PORTED gap)
# --------------------------------------------------------------------------
#
# ``frame_cascade`` above is this port's own Otsu heuristic. The ``vendor_*``
# helpers are the bit-exact port of TLB.dll's framing. This block is the
# BRIDGE that lets the app run the vendor helpers on a real 14-bit roll,
# opt-in via ``PAKON_VENDOR_FRAMING=1``.
#
# WHAT IS PROVEN vs WHAT IS APPROXIMATE (read before trusting this):
#   * The cascade (``vendor_framing_entry`` -> the four-phase driver) is
#     bit-exact against TLB.dll, and — on the 2026-08-22 v51 live capture —
#     reproduces the scanner's OWN placed ``framing_slots`` EXACTLY when fed
#     the scanner's OWN captured 8-bit line array (``this+0x6c``): 6 frames at
#     lines 11/409/806/1202/1601/2000, width 375, threshold 119, invert=1.
#     That is a real-hardware end-to-end check of the cascade, not a synthetic
#     golden.
#   * ``fcn.10006870`` (the reduce) is ``255 - (r+g+b)//3`` over a 3-byte
#     per-line RGB array whose length is ``[vtable+0x20]`` — confirmed by
#     disassembly and by that same reproduction.
#   * WHAT IS NOT PINNED: how the scanner builds that 8-bit RGB summary from
#     the raw scan (the resolution-tier downsample ``fcn.100040b0`` picks —
#     ``line_scale`` in {1,2,4,8}, =8 for 35mm HR — plus the per-line column
#     reduction and the 14->8 quantisation). That fill happens line-by-line
#     DURING the scan and is NOT in the v51 capture (its earliest buffer is
#     the framing object itself). So ``vendor_frames_from_trace`` DERIVES the
#     summary from the app's own 14-bit per-line trace with the natural ``>>6``
#     quantisation; the polarity (image dark / base bright) matches the
#     scanner's, but the exact 8-bit values are this port's choice, not a
#     captured fact. This is why ``FRAMING_PORTED`` stays False.

#: ``fcn.10006e70``'s tag stamps -> this module's ``Phase``. The driver stamps
#: 1 for phase 1 (NICE), 2 for phase 2 (IN_BETWEEN), 4 for phase 3 (LookAtEnd),
#: 3 for phase 4 (LookAtBeginning) and 9 for blind — see
#: ``vendor_framing_driver``.
_VENDOR_TAG_PHASE = {1: Phase.NICE, 2: Phase.IN_BETWEEN, 4: Phase.AT_END,
                     3: Phase.AT_BEGINNING, 9: Phase.BLIND}

#: The resolution tier ``fcn.100040b0`` selects for 35mm at HR (3000x2000 frame
#: image): the framing summary is the scan downsampled by 8 along the film.
VENDOR_FRAMING_LINE_SCALE = 8


def use_vendor_framing() -> bool:
    """Whether the app should run the DLL-ported cascade instead of Otsu.

    Opt-in, default off, for the reason in ``FRAMING_PORTED``'s comment: the
    cascade is verified but the line-array *derivation* below is not.
    """
    return os.environ.get("PAKON_VENDOR_FRAMING") == "1"


def vendor_frames_from_trace(
        trace: np.ndarray,
        present: np.ndarray | None = None,
        *,
        lines_per_mm: float | None = None,
        pitch_lines: float | None = None,
        line_scale: int = VENDOR_FRAMING_LINE_SCALE,
        invert: int = 1) -> tuple[list[Frame], dict]:
    """Run the bit-exact vendor cascade on a real 14-bit per-line trace.

    ``trace`` is the app's own per-line ``(R+G+B)/3`` on the calibrated 14-bit
    scale (``pakon_render.open_capture``'s ``trace_1d``). This function derives
    the scanner's downsampled 8-bit RGB line summary from it, runs
    ``vendor_framing_entry`` (bit-exact vs TLB.dll ``fcn.100072c0``), and maps
    the placed slots back to full-resolution line spans.

    See the block comment above for exactly what is proven and what is
    approximate. Returns ``(frames, report)`` in the same shape
    ``frame_cascade`` does, so callers do not care which cascade ran.
    """
    trace = np.asarray(trace, dtype=np.float64).reshape(-1)
    n = trace.size
    ls = int(line_scale)
    n8 = n // ls
    if n8 < 4:
        raise ValueError(f"trace too short for vendor framing: {n} lines")

    # Downsample along-film by averaging groups of `line_scale` scan lines.
    ds = trace[:n8 * ls].reshape(n8, ls).mean(axis=1)
    # 14-bit -> 8-bit, the natural RAW14_MAX(16383) >> 6. Image content is DARK
    # (low) and interframe base is BRIGHT (high) in this domain, the same
    # polarity the scanner's own summary carries, so the reduce's `255 - avg`
    # makes image lines read high — exactly what the cascade's "ones" want.
    avg8 = np.clip(ds / 64.0, 0, 255).astype(np.uint8)
    rgb8 = np.stack([avg8, avg8, avg8], axis=1)

    if pitch_lines is not None:
        pitch_full = float(pitch_lines)
        pitch_source = "given"
    elif lines_per_mm is not None:
        pitch_full = FRAME_PITCH_MM * lines_per_mm
        pitch_source = "geometry"
    else:
        raise ValueError("vendor_frames_from_trace needs pitch_lines or "
                         "lines_per_mm")
    pitch = max(1, int(round(pitch_full / ls)))
    width = max(1, int(round(pitch * (FRAME_IMAGE_MM / FRAME_PITCH_MM))))
    n_slots = (2 * n8) // pitch
    if n_slots <= 0:
        raise ValueError(f"degenerate slot count {n_slots}")

    slots = [[0, 0, 0] for _ in range(n_slots)]
    warn = [0]
    _ret, ones, thr, _n_runs = vendor_framing_entry(
        rgb8, slots, n_slots=n_slots, pitch=pitch, width=width,
        first=0, tail_margin=0, skip_gapok=0, warn=warn, invert=invert)

    # Collect placed slots, mapping downsampled coords back to full-res lines.
    # The roll caller (``vendor_place_roll_pictures``) discards a slot whose
    # left edge or length is zero (0x10007b95); mirror that here.
    frames: list[Frame] = []
    for left, w, tag in slots:
        if w <= 0 or left <= 0:
            continue
        frames.append(Frame(start=int(left) * ls, stop=int(left + w) * ls,
                            phase=_VENDOR_TAG_PHASE.get(int(tag), Phase.NICE)))
    frames.sort(key=lambda f: f.start)
    for a, b in zip(frames, frames[1:]):        # frames cannot overlap on film
        if a.stop > b.start:
            a.stop = b.start
    frames = [f for f in frames if f.lines > 0]

    ones8 = np.asarray(ones[:n8], dtype=np.float64)
    for f in frames:
        s8 = f.start // ls
        e8 = max(s8 + 1, f.stop // ls)
        seg = ones8[s8:e8]
        f.content_fraction = float(seg.mean()) if seg.size else 0.0

    lo8, hi8 = vendor_limits(width)
    report = {
        "counts": {p.vendor_name: sum(1 for f in frames if f.phase is p)
                   for p in Phase},
        "total": len(frames),
        "lo_lim": float(lo8 * ls),
        "target": float(width * ls),
        "hi_lim": float(hi8 * ls),
        "pitch": round(pitch * ls, 1),
        "pitch_source": pitch_source,
        "pitch_measured": None,
        "pitch_rejected_reason": None,
        "lines_per_mm_geometry": (round(lines_per_mm, 4)
                                  if lines_per_mm is not None else None),
        "ones_threshold": int(thr),
        "line_scale": ls,
        "n_framing_lines": int(n8),
        "scan_warnings": int(np.bitwise_or.reduce(
            [int(f.phase) for f in frames]) if frames else 0),
        "detector_arch": (
            "vendor_framing_entry (TLB.dll fcn.100072c0, bit-exact); 8-bit "
            "line summary DERIVED from the 14-bit trace by >>6 [APPROX — the "
            "scanner's own raw-scan-to-summary quantisation is uncaptured]"),
    }
    return frames, report


def find_frames_traces(trace: np.ndarray,
                       green: np.ndarray,
                       speed: float | None = None,
                       line_rate: float = REF_LINE_RATE,
                       clear_level: float = DEFAULT_CLEAR_LEVEL,
                       ones_threshold: float | None = None,
                       pitch_lines: float | None = None,
                       present: np.ndarray | None = None) -> tuple[list[Frame], dict]:
    """The cascade from two precomputed 1-D traces.

    This is the entry point for callers that already hold the strip on disk
    and cannot afford to materialise it: the vendor's framing only ever sees
    per-line scalars (docs/53 §4.2.1), so a caller that can produce
    ``(R+G+B)/3`` and the green mean per line -- chunked, as
    ``pakon_render.open_capture`` already does for its histogram -- never needs
    the pixels here at all. A 31 000-line capture costs 0.5 MB this way rather
    than 1.5 GB.

    ``trace`` and ``green`` must be per-line and the same length, and must be
    on the *calibrated* scale, because ``clear_level`` is an absolute level.

    ``present``, if given, is used as-is and ``clear_level``/``film_present``
    are skipped entirely. Pass this when ``green`` is not on the scale
    ``DEFAULT_CLEAR_LEVEL`` was measured on (``pakon_render.open_capture``'s
    own ``trace_1d``/``green_1d`` are the dark/gain-*calibrated* 14-bit domain,
    not the raw wire domain the constant is calibrated for -- confirmed
    2026-08-11: this silently made ``film_present`` never see "gate empty" at
    all, so every capture "found" zero real frames and blindly tiled the
    whole thing). ``pakon_gate.Gate``, run on the RAW wire lines, is the
    correct-domain source for this -- it is the same classifier the live scan
    itself runs, verified against real reference captures the same day.
    """
    trace = np.asarray(trace, dtype=np.float64).reshape(-1)
    green = np.asarray(green, dtype=np.float64).reshape(-1)
    if trace.size != green.size:
        raise ValueError(f"trace and green differ in length: "
                         f"{trace.size} vs {green.size}")
    lines_per_mm = resolve_lines_per_mm(speed, line_rate)
    if present is None:
        present = film_present(green, clear_level)
    else:
        present = np.asarray(present, dtype=bool).reshape(-1)
        if present.size != trace.size:
            raise ValueError(f"present and trace differ in length: "
                             f"{present.size} vs {trace.size}")
    if use_vendor_framing():
        # The DLL-ported cascade, opt-in. If the derivation degenerates on a
        # given roll, do NOT lose the roll: fall through to the Otsu cascade.
        try:
            return vendor_frames_from_trace(
                trace, present, lines_per_mm=lines_per_mm,
                pitch_lines=pitch_lines)
        except Exception:                                       # noqa: BLE001
            pass
    return frame_cascade(trace, lines_per_mm, present,
                         ones_threshold, pitch_lines=pitch_lines)


def find_frames(strip: np.ndarray,
                speed: float | None = None,
                line_rate: float = REF_LINE_RATE,
                clear_level: float = DEFAULT_CLEAR_LEVEL,
                ones_threshold: float | None = None,
                pitch_lines: float | None = None) -> tuple[list[Frame], dict]:
    """Top level: strip in, vendor-shaped frame list out."""
    return find_frames_traces(framing_trace(strip), green_trace(strip),
                              speed=speed, line_rate=line_rate,
                              clear_level=clear_level,
                              ones_threshold=ones_threshold,
                              pitch_lines=pitch_lines)


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------

def _synth(n_frames: int, lines_per_mm: float, *, drop_gaps: tuple[int, ...] = (),
           leader_mm: float = 20.0, blank: bool = False,
           rng: np.random.Generator | None = None) -> np.ndarray:
    """Build a synthetic (lines, 3) strip with known frame positions."""
    rng = rng or np.random.default_rng(7)
    clear = DEFAULT_CLEAR_LEVEL
    pitch = FRAME_PITCH_MM * lines_per_mm
    image = FRAME_IMAGE_MM * lines_per_mm
    lead = int(round(leader_mm * lines_per_mm))
    total = lead * 2 + int(round(n_frames * pitch))

    # gap level: film base, well below the empty gate but above image
    gap_level = clear * 0.80
    img_level = clear * 0.45

    g = np.full(total, clear * 1.02)                    # empty gate outside film
    film_lo, film_hi = lead, total - lead
    g[film_lo:film_hi] = gap_level                      # film base everywhere

    for i in range(n_frames):
        s = int(round(lead + i * pitch))
        e = s + int(round(image))
        if i in drop_gaps:
            e = int(round(lead + (i + 1) * pitch)) + int(round(image))
        if blank:
            continue
        g[s:e] = img_level + rng.normal(0, clear * 0.02, max(0, e - s))

    g = np.clip(g, 0, 65535)
    strip = np.stack([g * 0.98, g, g * 1.01], axis=1)
    return strip


def self_test() -> int:
    lpm = resolve_lines_per_mm(MOTOR_SPEED[8])
    failures = []

    def check(name, cond, detail=""):
        print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
        if not cond:
            failures.append(name)

    print(f"geometry: {lpm:.3f} lines/mm, "
          f"target {FRAME_IMAGE_MM * lpm:.0f}, pitch {FRAME_PITCH_MM * lpm:.0f} lines")

    print("\n1. clean strip, 6 frames -- all should be NICE")
    strip = _synth(6, lpm)
    frames, rep = find_frames(strip, speed=MOTOR_SPEED[8])
    check("found 6 frames", len(frames) == 6, f"got {len(frames)}")
    check("all phase NICE", all(f.phase is Phase.NICE for f in frames),
          str(rep["counts"]))
    check("scan warning GOOD", rep["scan_warnings"] == 0, hex(rep["scan_warnings"]))

    print("\n2. one missed gap -- merged run is out of tolerance, filled IN_BETWEEN")
    strip = _synth(6, lpm, drop_gaps=(2,))
    frames, rep = find_frames(strip, speed=MOTOR_SPEED[8])
    got = rep["counts"]
    check("some frames recovered by interpolation",
          got["FramingLookInBetweenEnds"] >= 1, str(got))
    check("IN_MIDDLE flagged", rep["scan_warnings"] & int(Phase.IN_BETWEEN) != 0,
          hex(rep["scan_warnings"]))
    check("no overlapping frames",
          all(a.stop <= b.start for a, b in zip(frames, frames[1:])))
    check("frames are ordered and non-empty",
          all(f.lines > 0 for f in frames) and
          all(a.start < b.start for a, b in zip(frames, frames[1:])))

    print("\n3. blank film -- no ones runs, must fall back to BLIND")
    strip = _synth(6, lpm, blank=True)
    frames, rep = find_frames(strip, speed=MOTOR_SPEED[8])
    check("frames placed blindly", len(frames) > 0 and
          all(f.phase is Phase.BLIND for f in frames), str(rep["counts"]))
    check("scan warning BAD", rep["scan_warnings"] == int(Phase.BLIND),
          hex(rep["scan_warnings"]))

    print("\n4. vendor invariants")
    check("acceptance window is 0.95/1.15 of target",
          abs(rep["lo_lim"] / rep["target"] - 0.95) < 1e-6 and
          abs(rep["hi_lim"] / rep["target"] - 1.15) < 1e-6,
          f"{rep['lo_lim']}..{rep['hi_lim']} around {rep['target']}")
    check("FRAMING_FAIR is the OR of the three middle passes",
          int(Phase.IN_BETWEEN) | int(Phase.AT_END) | int(Phase.AT_BEGINNING) == 1792)
    # At square pixels the along-film sampling equals the across-film
    # sampling, so a 36 mm frame is 36 * 2000/24 = 3000 lines -- which is
    # exactly TLXLib.FRAME_SIZES_000.FRAME_SIZES_HR_WIDTH_BASE16_35 (docs/56
    # §2.7). Our geometry constants are validated against the vendor's own
    # published output size, independently of any capture.
    vendor_hr_width_base16_35 = 3000
    vendor_hr_height_base16_35 = 2000
    check("36 mm at square pixels == FRAME_SIZES_HR_WIDTH_BASE16_35",
          abs(FRAME_IMAGE_MM * ACROSS_PX_PER_MM - vendor_hr_width_base16_35) < 0.5,
          f"{FRAME_IMAGE_MM * ACROSS_PX_PER_MM:.1f} vs {vendor_hr_width_base16_35}")
    check("24 mm across == FRAME_SIZES_HR_HEIGHT_BASE16_35",
          abs(FILM_ACROSS_MM * ACROSS_PX_PER_MM - vendor_hr_height_base16_35) < 0.5,
          f"{FILM_ACROSS_MM * ACROSS_PX_PER_MM:.1f} vs {vendor_hr_height_base16_35}")
    check("DetectFilm_G / DetectWhite_G ratio matches the hive",
          abs(DETECT_FILM_FRAC / DETECT_WHITE_FRAC - 54000 / 61000) < 1e-9)

    print("\n5. film presence hysteresis")
    clear = DEFAULT_CLEAR_LEVEL
    g = np.array([clear * 1.02] * 5 + [clear * 0.90] * 5 +
                 [clear * 0.50] * 5 + [clear * 0.90] * 5 + [clear * 1.02] * 5)
    p = film_present(g, clear)
    check("empty gate before film", not p[0:5].any())
    check("band alone does not latch film on", not p[5:10].any(),
          "0.90 is between the two thresholds")
    check("film detected below DetectFilm_G", p[10:15].all())
    check("film stays present in the band on the way out", p[15:20].all(),
          "hysteresis")
    check("empty gate after film", not p[20:25].any())

    print("\n6. the vendor helpers (values captured from TLB.dll under Unicorn)")
    # These are regression pins, not a substitute for the real thing: the
    # authority is tools/ansel/python-pipeline/pakon_framing_golden.py, which
    # executes TLB.dll itself. This group exists so a change to _cdiv or to
    # the acceptance test fails here too, on a machine with no DLL.
    check("FRAMING_PORTED is honestly False", FRAMING_PORTED is False)
    check("vendor_limits(190) == (180, 218)", vendor_limits(190) == (180, 218),
          str(vendor_limits(190)))
    check("vendor_limits truncates, never rounds",
          vendor_limits(3000) == (2850, 3450) and vendor_limits(7) == (6, 8),
          f"{vendor_limits(3000)} {vendor_limits(7)}")
    check("_cdiv truncates toward zero on negatives",
          (_cdiv(-48, 3), _cdiv(-47, 3), _cdiv(47, 3)) == (-16, -15, 15),
          str((_cdiv(-48, 3), _cdiv(-47, 3), _cdiv(47, 3))))
    o = np.zeros(1400, dtype=np.int32)
    for k in range(6):
        o[40 + 200 * k: 40 + 200 * k + 190] = 1
    n_runs, bins, recs = vendor_ones_runs(o, 0, 1399, 190)
    check("vendor_ones_runs finds 6 clean runs", n_runs == 6, str(n_runs))
    check("vendor bins put all six in the good bin", bins == [6, 0, 0],
          str(bins))
    check("vendor run records are (left, length)",
          [tuple(r[:2]) for r in recs] == [(40 + 200 * k, 190) for k in range(6)],
          str([tuple(r[:2]) for r in recs]))
    pl, count = vendor_look_for_nice_pictures(recs, n_runs, 200, 190, -1, 5000)
    check("vendor phase 1 places all six", count == 6, str(count))
    check("vendor phase 1 keys slots by (2*left)/pitch",
          sorted(pl) == [0, 2, 4, 6, 8, 10], str(sorted(pl)))
    check("vendor phase 1 emits nominal width, not the run's",
          {v[1] for v in pl.values()} == {190},
          str({v[1] for v in pl.values()}))
    # the double-frame branch, which frame_cascade has no equivalent for
    dbl, dcount = vendor_look_for_nice_pictures([[100, 385, 0]], 1, 200, 190,
                                                -1, 5000)
    check("vendor phase 1 splits a merged pair in phase 1", dcount == 2,
          str(dcount))
    check("the second half lands at run.left + pitch",
          sorted(dbl.values()) == [(99, 190), (300, 190)],
          str(sorted(dbl.values())))
    check("vendor_framing_trace inverts: 255 - (r+g+b)//3",
          list(vendor_framing_trace(np.array([[0, 0, 0], [255, 255, 255],
                                              [1, 1, 2]], dtype=np.uint8)))
          == [255, 0, 254],
          str(list(vendor_framing_trace(np.array([[0, 0, 0], [255, 255, 255],
                                                  [1, 1, 2]], dtype=np.uint8)))))

    print("\n5. the vendor chain end to end (tier 1 lives in the golden "
          "harness;\n   these only pin the invariants a caller depends on)")
    # a synthetic roll in the vendor's own domain: 8-bit, dark frames on a
    # bright base, so 255-avg makes the frames read high
    lines = 1500
    g = np.full(lines, 205, dtype=np.int32)
    for k in range(6):
        g[100 + 200 * k: 100 + 200 * k + 190] = 60
    rgb = np.stack([g, g, g], axis=1).astype(np.uint8)
    n_slots = 2 * (lines - 1) // 200 + 8
    slots = [[0, 0, 0] for _ in range(n_slots)]
    warn = [0]
    ret, ones, thr, n_runs = vendor_framing_entry(
        rgb, slots, n_slots, 200, 190, 0, 0, 1, warn)
    check("vendor entry places all six frames", ret == 6, str(ret))
    check("vendor entry found six runs to place them from", n_runs == 6,
          str(n_runs))
    check("vendor entry picked a threshold inside the 8-bit trace range",
          0 < thr < 256, str(thr))
    check("a clean roll needs no phase 2/3/4, so no warning bits",
          warn[0] == 0, hex(warn[0]))
    placed = [s for s in slots if s[0] or s[1]]
    check("every placed frame is tagged phase 1 (tag == 1)",
          all(s[2] == 1 for s in placed), str(sorted({s[2] for s in placed})))
    check("vendor entry places nominal-width frames",
          sorted({s[1] for s in placed}) == [190],
          str(sorted({s[1] for s in placed})))
    # the tag numbering really is 1,2,4,3,9 -- not 1,2,3,4,5
    check("blind placement stamps tag 9, not 5",
          (lambda sl: (vendor_blindly_place_pictures(sl, 200, 190, 1500),
                       sl[0][2])[1])(
              [[0, 0, 0] for _ in range(40)]) == 9)
    check("the ones array is 1 where the trace exceeds the threshold",
          all((ones[i] == 1) == (int(255 - (3 * int(g[i])) // 3) > thr)
              for i in range(0, lines, 37)))
    check("FRAMING_PORTED is still False and find_frames still uses Otsu",
          FRAMING_PORTED is False and VENDOR_ENTRY_PORTED is True)

    # --- fcn.100079c0, the roll caller ---------------------------------
    roll_kw = dict(skip_gapok=1, no_tail_margin=0, n_lines=lines,
                   line_scale=2, image_rows=2 * lines, margin_units=1,
                   pitch_raw=400, width_raw=380, margin_divisor=2540,
                   crop_top=6, crop_left=40, crop_bottom=6 + 380 - 12,
                   crop_right=940, frame_bottom=6 + 380 - 12 + 5)
    w = [0]
    ret, pics, cnt, errs = vendor_place_roll_pictures(
        rgb, w, place_blindly=0, end_anchored=0, **roll_kw)
    check("roll caller turns the cascade's six slots into six CiPicLocs",
          (ret, len(pics), cnt, errs) == (6, 6, 6, 0),
          str((ret, len(pics), cnt, errs)))
    check("roll caller leaves the cascade's warning word alone",
          w[0] == 0, hex(w[0]))
    # top = line_scale*slot.left + crop_top; bottom = top + H - 1, with
    # H = crop_bottom - crop_top + 1 = 369. The first frame sits at line 100.
    check("a cascade picture is (top, left, bottom, right, tag, grade)",
          pics[0] == (206, 40, 206 + 369 - 1, 940, 1, 0), str(pics[0]))
    check("phase-1 tag 1 grades as 0 (it misses fcn.100245e0's switch)",
          vendor_picloc_grade(1) == 0 and vendor_picloc_grade(2) == 1
          and vendor_picloc_grade(9) == 4,
          str([vendor_picloc_grade(t) for t in range(11)]))
    w = [0x100]
    bret, bpics, bcnt, _ = vendor_place_roll_pictures(
        rgb, w, place_blindly=1, end_anchored=0, **roll_kw)
    check("argument 2 alone selects blind placement, and it ORs 0x800",
          w[0] == 0x900, hex(w[0]))
    check("every blindly placed picture is tagged 9 and grades 4",
          all(p[4] == 9 and p[5] == 4 for p in bpics) and len(bpics) > 0,
          str(sorted({(p[4], p[5]) for p in bpics})))
    # the vendor's own double count: fcn.10006720 bumps this->0xc9c per slot
    # and the caller bumps it again per CiPicLoc built from that slot
    check("the blind path returns TWICE the pictures it placed — vendor bug, "
          "reproduced", (bret, bcnt) == (2 * len(bpics), 2 * len(bpics)),
          str((bret, bcnt, len(bpics))))
    # the one exit that leaves the object's previous roll alone
    keep = [(1, 2, 3, 4, 2, 1)]
    nret, npics, ncnt, _ = vendor_place_roll_pictures(
        rgb, [0], place_blindly=0, end_anchored=0,
        **{**roll_kw, "pitch_raw": 40 * lines, "width_raw": 39 * lines},
        pictures_in=keep, count_in=99)
    check("n_slots <= 0 returns 0 and keeps the previous list and count",
          (nret, npics, ncnt) == (0, keep, 99), str((nret, npics, ncnt)))

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S): {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

WORDS_PER_LINE = 6000   # base-16: 2000 px x 3 channels, as pakon_decode


def _sidecar(capture: Path) -> dict | None:
    """Read ``*.scan.json`` next to a capture. Same lookup as pakon_decode."""
    for cand in (capture.with_suffix(".scan.json"),
                 Path(str(capture) + ".scan.json")):
        if not cand.is_file() or cand == capture:
            continue
        try:
            data = json.loads(cand.read_text())
        except (OSError, json.JSONDecodeError, UnicodeError):
            continue
        if isinstance(data, dict):
            return data
    return None


#: 4-channel (Digital ICE) line length, for the guard in ``_load`` only. This
#: module does not decode IR captures; it refuses them, which is the point.
WORDS_PER_LINE_IR = 8000


def _load(path: Path, words_per_line: int = WORDS_PER_LINE) -> np.ndarray:
    raw = np.fromfile(path, dtype="<u2")
    n = raw.size // words_per_line
    if n == 0:
        raise SystemExit(f"{path}: too short for {words_per_line}-word lines")
    # This reader strides blindly — it never looks at a sync marker — so a
    # capture with a different line length comes out as plausible-looking
    # nonsense rather than an error. Check the marker spacing once, over a few
    # lines' worth, before believing the stride. A 4-channel IR capture is
    # 8000 words with the IR run at the end (docs/70 §2) and would otherwise
    # shear every frame boundary this module computes.
    head = raw[: words_per_line * 8]
    marks = np.flatnonzero(head & 1)
    if marks.size >= 3:
        modal = int(np.bincount(np.diff(marks)).argmax())
        if modal != words_per_line and modal in (WORDS_PER_LINE,
                                                 WORDS_PER_LINE_IR):
            raise SystemExit(
                f"{path}: {modal}-word lines ({modal // 2000}-channel), not "
                f"{words_per_line}. Framing does not handle this geometry.")
    a = raw[: n * words_per_line].reshape(n, words_per_line // 3, 3)
    return a.astype(np.float64)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("capture", nargs="?", type=Path)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--speed", type=float, default=None,
                    help=f"MotorSpeedPlus (default {SQUARE_MOTOR_SPEED})")
    ap.add_argument("--line-rate", type=float, default=REF_LINE_RATE)
    ap.add_argument("--clear-level", type=float, default=DEFAULT_CLEAR_LEVEL)
    ap.add_argument("--ones-threshold", type=float, default=None,
                    help="override the INFERRED Otsu binarisation level")
    ap.add_argument("--pitch-lines", type=float, default=None,
                    help="force the frame pitch in lines (default: measure it; "
                         "see estimate_pitch for why geometry is not trusted)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    if args.capture is None:
        ap.error("give a capture, or --self-test")

    speed = args.speed
    line_rate = args.line_rate
    if speed is None:
        # pakon_scan writes "speed" and "line_rate_0x91", top level and under
        # "config" -- see pakon_scan.capture_metadata, which calls those keys a
        # contract. This used to look for "motor_speed" under "scan", which no
        # sidecar has ever contained, so --speed was silently ignored.
        meta = _sidecar(args.capture)
        if meta:
            cfg = meta.get("config") if isinstance(meta.get("config"), dict) else {}
            raw = meta.get("speed", cfg.get("speed"))
            if raw is not None:
                speed = float(raw)
            raw_lr = (meta.get("line_rate_0x91") or cfg.get("line_rate_0x91"))
            if raw_lr is not None and args.line_rate == REF_LINE_RATE:
                line_rate = float(raw_lr)

    strip = _load(args.capture)
    frames, report = find_frames(strip, speed=speed, line_rate=line_rate,
                                 clear_level=args.clear_level,
                                 ones_threshold=args.ones_threshold,
                                 pitch_lines=args.pitch_lines)

    if args.json:
        def _json_default(o):
            if isinstance(o, np.integer):
                return int(o)
            if isinstance(o, np.floating):
                return float(o)
            if isinstance(o, np.bool_):
                return bool(o)
            if isinstance(o, np.ndarray):
                return o.tolist()
            raise TypeError(f"Object of type {o.__class__.__name__} "
                            f"is not JSON serializable")
        print(json.dumps({"report": report,
                          "frames": [f.as_dict() for f in frames]},
                         indent=2, default=_json_default))
        return 0

    print(f"{args.capture}: {strip.shape[0]} lines, "
          f"film {report['film_start']}..{report['film_stop']}")
    print(f"window {report['lo_lim']}..{report['hi_lim']} around "
          f"{report['target']}, pitch {report['pitch']} ({report['pitch_source']}), "
          f"ones<{report['ones_threshold']}")
    if report["pitch_source"] == "measured" and report["lines_per_mm_geometry"]:
        print(f"  note: geometry predicts {report['lines_per_mm_geometry']} lines/mm, "
              f"data implies {report['lines_per_mm_implied']}")
    if report.get("pitch_rejected_reason"):
        print(f"  note: measured pitch rejected in favour of geometry -- "
              f"{report['pitch_rejected_reason']}")
    for name, count in report["counts"].items():
        if count:
            print(f"  {name} {count}")
    print(f"  total {report['total']}, "
          f"scan warnings 0x{report['scan_warnings']:X}")
    for i, f in enumerate(frames):
        print(f"  {i:3d} {f.start:7d}..{f.stop:<7d} {f.lines:5d}  "
              f"{f.phase.vendor_name} (risk {f.phase.risk})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
