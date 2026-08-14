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

Phase 5 is a **whole-roll fallback**, not a per-frame one: docs/53 §4.2.1
traced the call sites and found the blind path fires "only when the first
framed zero pictures". So phases 2-4 only run when phase 1 found something,
and phase 5 only runs when it did not. That asymmetry is deliberate here.

The acceptance window in phase 1 is the vendor's, not invented.
``FN_iFramingCreateOnesArray`` (``0x10006289``-``0x100062eb``, docs/53 §4.2.1)
bins run lengths against ``pitch*95/100`` and ``pitch*115/100`` — which are
exactly the ``LoLim`` and ``HiLim`` columns the vendor prints into
``DXCode.txt`` beside ``Target`` (docs/56 §2.3, §2.9):

    LoLim  Target HiLim  Actual Variance  LeftEdge  RightEdge

Asymmetric: 5% under, 15% over. Over-tolerance is wider because the failure
that matters is two frames merging when their gap is missed.

The input signal is the vendor's too. docs/53 §4.2.1: framing reduces each
scanline to a **single scalar** ``(R+G+B)/3`` and never sees per-column data.
So this module works on a 1-D trace, deliberately, even though we have the
full strip.

WHAT IS *NOT* THE VENDOR'S
--------------------------
One thing. The threshold that turns the 1-D trace into the binary "ones"
array is still unrecovered (docs/56 §7.4). Kodak's binarisation is inside
``TLB.dll`` and nobody has traced it. This module uses Otsu's method over the
film-present region, which needs no magic number and adapts per strip. It is
marked ``INFERRED`` everywhere it appears and is overridable with
``--ones-threshold``.

Everything else — the phases, their order, the window, the fallback rule, the
1-D input, the provenance encoding — is the vendor's.

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

    @property
    def lines(self) -> int:
        return self.stop - self.start

    def as_dict(self) -> dict:
        return {"start": self.start, "stop": self.stop, "lines": self.lines,
                "phase": self.phase.vendor_name,
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

    So the two routes now agree, and framing still prefers the measurement:
    it needs neither the sidecar nor the anchor, only the fact that 35 mm
    frames are 38 mm apart. Pass ``--pitch-lines`` to force a value, or
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

    if pitch_lines is not None:
        pitch, pitch_source = float(pitch_lines), "given"
    else:
        measured = estimate_pitch(ones)
        if measured is not None:
            pitch, pitch_source = measured, "measured"
        elif lines_per_mm is not None:
            pitch, pitch_source = FRAME_PITCH_MM * lines_per_mm, "geometry"
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
    all_runs = [(a, b) for a, b in _runs(ones) if b - a >= 0.4 * target]
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
                cand = Frame(int(s), int(e), phase)
                if _overlap(cand, placed) <= 0.1 * width:
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

    counts = {p.vendor_name: sum(1 for f in frames if f.phase is p) for p in Phase}
    report = {
        "counts": counts,
        "total": len(frames),
        "lo_lim": round(lo_lim, 1),
        "target": round(target, 1),
        "hi_lim": round(hi_lim, 1),
        "pitch": round(pitch, 1),
        "pitch_source": pitch_source,
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
        print(json.dumps({"report": report,
                          "frames": [f.as_dict() for f in frames]}, indent=2))
        return 0

    print(f"{args.capture}: {strip.shape[0]} lines, "
          f"film {report['film_start']}..{report['film_stop']}")
    print(f"window {report['lo_lim']}..{report['hi_lim']} around "
          f"{report['target']}, pitch {report['pitch']} ({report['pitch_source']}), "
          f"ones<{report['ones_threshold']}")
    if report["pitch_source"] == "measured" and report["lines_per_mm_geometry"]:
        print(f"  note: geometry predicts {report['lines_per_mm_geometry']} lines/mm, "
              f"data implies {report['lines_per_mm_implied']}")
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
