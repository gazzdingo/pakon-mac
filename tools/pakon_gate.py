#!/usr/bin/env python3
"""Three-state gate classifier: CLEAR / FILM / DARK, and the run detector.

WHY THIS EXISTS
---------------
An overnight roll scan ran seven minutes. The lamp died about two minutes in
and the transport kept running for five more with the sensor reading darkness.
The roll-end detector never fired because it tested one boundary only — "is
this bright enough to be a clear gate" — and darkness is not bright, so
darkness read as *film present* and the film kept moving past a dead lamp.

The lesson is that a detector reasoning about one boundary is not a detector.
Every capture window is therefore classified into three states, not two:

    CLEAR   near the clear-gate level. Nothing in the film path.
    FILM    a plausible middle band. Film is in the path and lit.
    DARK    at or near the dark reference. The lamp has failed or the path is
            blocked. Continuing achieves nothing while film keeps moving, so
            DARK stops the transport.

WHERE EVERY THRESHOLD COMES FROM
--------------------------------
Nothing here is a number somebody remembered. Both reference levels are read
out of the committed calibration in ``calibration/``:

  * ``dark_2000x3.npy`` **is** the DARK reference — the per-pixel CCD level
    with the lamp off, 14,482 lines, zero sync losses. Measured mean over the
    valid columns is 1241.3 counts, which is the "~1275 on this unit" figure
    from the field notes.

  * ``gain_2000x3.npy`` **contains** the CLEAR reference. The flat field is
    ``gain = K / (bright - dark)`` for a single normalisation constant K, so
    the empty-gate level is recoverable exactly as ``clear = dark + K/gain``.
    K is ``mean(bright_source.means - dark_source.means)`` from
    ``calibration/README.json`` = 48786.2 counts. Reconstructing the clear
    reference this way reproduces the measured ``captures/ref_bright.bin``
    per-pixel profile with a mean error of -0.15 counts on 50,000 and a worst
    case of 316 counts (0.6 %). See ``pakon_gate.py selftest``.

  * The valid column window is derived the same way: a column whose committed
    gain exceeds ``EDGE_GAIN_LIMIT`` saw less than 2/3 of nominal light in the
    empty-gate reference, i.e. it is vignetted or dead. On this unit that
    excludes columns 0..37 and keeps 38..1999.

THE DOMAIN, WHICH IS EASY TO GET WRONG
--------------------------------------
The committed tables are in the **raw wire domain** — the u16 as it leaves
EP 0x86, *not* the 14-bit domain that ``pakon_decode.to_rgb14`` produces by
shifting right two. ``dark_2000x3.npy`` has mean 1120.5/1443.0/1160.9 and
``captures/ref_dark.bin`` read raw has mean 1120.7/1443.1/1161.0; the same
file through ``to_rgb14`` reads 279.9/360.5/290.0. This module works in the
raw wire domain, which is both where the calibration lives and the cheapest
domain for a live capture loop — no shift, no reshape beyond the line split.

Decode path fix: ``pakon_decode.load_unit_calibration`` converts
``dark_wire/4`` for post-``to_rgb14`` maths and leaves gain unchanged
(``((w−d)·g)/4 ≡ (w>>2 − d/4)·g``). These ``.npy`` files stay wire-domain
so this gate module keeps reading them without a shift.

THE SECOND AXIS, AND WHY ONE NUMBER IS NOT ENOUGH
-------------------------------------------------
Level alone nearly works: on ``captures/roll.bin`` the dead-lamp half sits at
t = 0.0006 and ordinary film runs t = 0.047..0.33. But the exposed film tongue
at the head of a roll is genuinely almost opaque and measures t = 0.0062 —
only ten times the dead-lamp level. So a second, independent axis is used.

``struct`` is the spatial standard deviation of the window's column-mean
profile after the per-pixel dark table is subtracted. With the lamp lit, the
illumination has strong column structure and PRNU — that is exactly what the
gain table corrects, and why its values run 0.90..24.5. With the lamp dead
there is no illumination to have structure, and the dark table removes the
CCD's own fixed pattern, leaving only noise. Measured:

    ref_dark.bin (lamp off)          struct   0.9
    roll.bin, dead-lamp half         struct   5.6 .. 12.3
    roll.bin, opaque film tongue     struct   164
    roll.bin, ordinary film          struct   1380 .. 8460
    ref_bright.bin (empty gate)      struct   2045

A thirteen-fold gap between the worst true dark and the densest real film.

    python3 tools/pakon_gate.py selftest
    python3 tools/pakon_gate.py classify captures/roll.bin
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent

WORDS_PER_LINE = 6000          # DpiBase16, 2000 px x 3 channels
PIXELS_PER_LINE = 2000
CHANNELS = 3
BYTES_PER_LINE = WORDS_PER_LINE * 2

CLEAR, FILM, DARK, UNKNOWN = "clear", "film", "dark", "unknown"

# --------------------------------------------------------------------------
# thresholds — every one of them a fraction of a quantity read from
# calibration/, so changing the calibration changes the thresholds with it.
# --------------------------------------------------------------------------

#: A column whose committed gain exceeds this saw under 2/3 of nominal light in
#: the empty-gate reference: vignetted or dead. Excludes 0..37 on this unit.
EDGE_GAIN_LIMIT = 1.5

#: Fractions of the calibrated dark->clear swing (48,786 counts on this unit).
#:
#: DARK_HARD    unconditional dark. Measured: dead lamp 0.00057..0.00075,
#:              densest real film 0.0065. 0.002 sits 2.7x above the worst
#:              observed dark and 3.2x below the densest film.
#: DARK_SOFT    dark when the window also has no spatial structure. Wider, so
#:              a dark that drifted further off the reference is still caught.
#: DARK_STRUCT  struct ceiling for the soft rule, as a fraction of the swing.
#:              Measured: dead lamp 0.00025, densest film 0.0034.
#: CLEAR        open-ended above. Measured: clear gate 1.000..1.268 (a lamp
#:              brighter than the calibration reads above 1), brightest film
#:              window 0.327. 0.70 sits 1.4x under the dimmest clear and 2.1x
#:              over the brightest film.
DARK_HARD_FRAC = 0.002
DARK_SOFT_FRAC = 0.010
DARK_STRUCT_FRAC = 0.001
CLEAR_FRAC = 0.70

#: Lines per classification window. 256 lines is ~3.0 MB, about 0.26 s at the
#: measured 11.6 MB/s, and averages 256 x 1962 x 3 samples — enough that the
#: window mean is noise-free to four decimal places in t.
WINDOW_LINES = 256

#: Run lengths, in lines. Frame pitch on this unit measures ~1460 lines and an
#: inter-frame gap is a few hundred, so roll-end needs substantially more than
#: one frame to be a roll end rather than a gap or a blank frame.
DARK_CONFIRM_LINES = 512        # ~0.53 s. Two windows, so a splice cannot stop a roll.
ROLL_END_LINES = 4000           # ~2.7 frame pitches, ~4.1 s.
LEADER_FILM_LINES = 2000        # film must have been seen before roll-end can arm.


def _swing_fraction(counts: float, swing: float) -> float:
    return counts / swing if swing else 0.0


# --------------------------------------------------------------------------
# the calibration-derived references
# --------------------------------------------------------------------------

@dataclass
class Verdict:
    """One classification window."""
    state: str = UNKNOWN
    lines: int = 0
    level: float = 0.0          # raw wire counts, mean over valid columns
    t: float = 0.0              # 0 = dark reference, 1 = calibrated clear gate
    struct: float = 0.0         # spatial std of the dark-subtracted profile
    struct_frac: float = 0.0
    sync_lines: int = 0
    sync_breaks: int = 0
    reason: str = ""

    def to_json(self) -> dict:
        return {
            "state": self.state, "lines": self.lines,
            "level": round(self.level, 1), "t": round(self.t, 5),
            "struct": round(self.struct, 1),
            "struct_frac": round(self.struct_frac, 6),
            "sync_lines": self.sync_lines, "sync_breaks": self.sync_breaks,
            "reason": self.reason,
        }


class Gate:
    """CLEAR / FILM / DARK from the committed per-pixel calibration.

    Construct with :meth:`from_calibration`; it raises if the tables are not
    there, because a scan must not run with the classifier guessing.
    """

    def __init__(self, dark: np.ndarray, gain: np.ndarray, k: float,
                 source: str = "") -> None:
        if dark.shape != (PIXELS_PER_LINE, CHANNELS):
            raise ValueError(f"dark table is {dark.shape}, "
                             f"expected {(PIXELS_PER_LINE, CHANNELS)}")
        if gain.shape != (PIXELS_PER_LINE, CHANNELS):
            raise ValueError(f"gain table is {gain.shape}, "
                             f"expected {(PIXELS_PER_LINE, CHANNELS)}")
        self.source = source
        self.k = float(k)
        self.dark_ref = dark.astype(np.float64, copy=False)
        # gain = K / (bright - dark)  =>  bright = dark + K/gain
        self.clear_ref = self.dark_ref + self.k / np.maximum(gain, 1e-6)

        # Valid columns, derived from the gain table rather than assumed.
        col_gain = gain.mean(axis=1)
        self.valid = np.flatnonzero(col_gain <= EDGE_GAIN_LIMIT)
        if self.valid.size < PIXELS_PER_LINE // 4:
            raise ValueError(
                f"only {self.valid.size} usable columns in {source}: the gain "
                f"table does not look like an empty-gate flat field")

        self._dark_win = self.dark_ref[self.valid]
        self._clear_win = self.clear_ref[self.valid]
        self.dark_level = float(self._dark_win.mean())
        self.clear_level = float(self._clear_win.mean())
        self.swing = self.clear_level - self.dark_level
        if self.swing <= 0:
            raise ValueError("clear reference is not above the dark reference")

        # Thresholds in absolute counts, so they can be printed and argued with.
        self.dark_hard = self.dark_level + DARK_HARD_FRAC * self.swing
        self.dark_soft = self.dark_level + DARK_SOFT_FRAC * self.swing
        self.dark_struct = DARK_STRUCT_FRAC * self.swing
        self.clear_cut = self.dark_level + CLEAR_FRAC * self.swing

    # ---------------------------------------------------------------- build
    @classmethod
    def from_calibration(cls, cal_dir: str | Path | None = None) -> "Gate":
        root = Path(cal_dir) if cal_dir else _ROOT / "calibration"
        dark_p, gain_p, readme_p = (root / "dark_2000x3.npy",
                                    root / "gain_2000x3.npy",
                                    root / "README.json")
        missing = [p.name for p in (dark_p, gain_p, readme_p) if not p.is_file()]
        if missing:
            raise FileNotFoundError(
                f"cannot classify without the committed calibration: "
                f"{', '.join(missing)} missing under {root}")
        meta = json.loads(readme_p.read_text())
        try:
            bright = np.asarray(meta["bright_source"]["means"], dtype=np.float64)
            darkm = np.asarray(meta["dark_source"]["means"], dtype=np.float64)
        except (KeyError, TypeError) as e:
            raise ValueError(f"{readme_p}: no dark/bright source means ({e})")
        k = float((bright - darkm).mean())
        if not np.isfinite(k) or k <= 0:
            raise ValueError(f"{readme_p}: implausible flat-field constant {k}")
        return cls(np.load(dark_p), np.load(gain_p), k, source=str(root))

    # ------------------------------------------------------------- describe
    def describe(self) -> dict:
        return {
            "source": self.source,
            "valid_columns": [int(self.valid[0]), int(self.valid[-1]) + 1],
            "valid_count": int(self.valid.size),
            "flat_field_k": round(self.k, 1),
            "dark_level": round(self.dark_level, 1),
            "clear_level": round(self.clear_level, 1),
            "swing": round(self.swing, 1),
            "dark_hard": round(self.dark_hard, 1),
            "dark_soft": round(self.dark_soft, 1),
            "dark_struct": round(self.dark_struct, 1),
            "clear_cut": round(self.clear_cut, 1),
            "window_lines": WINDOW_LINES,
            "dark_confirm_lines": DARK_CONFIRM_LINES,
            "roll_end_lines": ROLL_END_LINES,
        }

    # ------------------------------------------------------------- classify
    def classify_lines(self, lines: np.ndarray, sync_breaks: int = 0) -> Verdict:
        """Classify a block of complete wire lines, shape (n, 6000) u16."""
        n = int(lines.shape[0])
        if n == 0:
            return Verdict(state=UNKNOWN, reason="no complete lines")
        win = lines.reshape(n, PIXELS_PER_LINE, CHANNELS)[:, self.valid, :]
        win = win.astype(np.float64)
        level = float(win.mean())
        # Column profile with the per-pixel dark table removed. What is left
        # under a working lamp is illumination structure; under a dead lamp,
        # only noise.
        profile = win.mean(axis=0) - self._dark_win
        struct = float(profile.std())

        v = Verdict(lines=n, level=level, struct=struct,
                    t=(level - self.dark_level) / self.swing,
                    struct_frac=_swing_fraction(struct, self.swing),
                    sync_lines=n, sync_breaks=sync_breaks)

        if level <= self.dark_hard:
            v.state = DARK
            v.reason = (f"level {level:.0f} at the dark reference "
                        f"({self.dark_level:.0f}, cut {self.dark_hard:.0f})")
        elif level <= self.dark_soft and struct <= self.dark_struct:
            v.state = DARK
            v.reason = (f"level {level:.0f} near dark and no illumination "
                        f"structure (struct {struct:.1f} <= "
                        f"{self.dark_struct:.1f})")
        elif level >= self.clear_cut:
            v.state = CLEAR
            v.reason = (f"level {level:.0f} at the clear gate "
                        f"({self.clear_level:.0f}, cut {self.clear_cut:.0f})")
        else:
            v.state = FILM
            v.reason = f"level {level:.0f} between dark and clear"
        return v


# --------------------------------------------------------------------------
# splitting a raw EP 0x86 stream into lines
# --------------------------------------------------------------------------

def split_lines(buf: bytes | bytearray, phase: int = 0
                ) -> tuple[np.ndarray, int, int, int]:
    """(lines, consumed_bytes, complete, breaks) from a raw EP 0x86 buffer.

    Bit 0 of a word is the line-start flag, so a clean stream has markers
    exactly ``WORDS_PER_LINE`` apart. Anything else is a FIFO break and is
    skipped rather than allowed to shear the block — the same rule
    ``pakon_decode.segment_lines`` uses, kept here so the live loop does not
    depend on the decode path.
    """
    mv = memoryview(buf)[phase:]
    n_words = len(mv) // 2
    if n_words < WORDS_PER_LINE + 1:
        return np.empty((0, WORDS_PER_LINE), dtype=np.uint16), 0, 0, 0
    words = np.frombuffer(mv[: n_words * 2], dtype="<u2")
    marks = np.flatnonzero(words & 1)
    if marks.size < 2:
        return np.empty((0, WORDS_PER_LINE), dtype=np.uint16), 0, 0, 0
    gaps = np.diff(marks)
    good = gaps == WORDS_PER_LINE
    starts = marks[:-1][good]
    breaks = int((~good).sum())
    if starts.size == 0:
        # Nothing usable; drop everything before the last marker so the caller
        # does not grow its buffer without bound.
        return (np.empty((0, WORDS_PER_LINE), dtype=np.uint16),
                phase + int(marks[-1]) * 2, 0, breaks)
    idx = starts[:, None] + np.arange(WORDS_PER_LINE)[None, :]
    lines = words[idx]
    consumed = phase + (int(starts[-1]) + WORDS_PER_LINE) * 2
    return lines, consumed, int(starts.size), breaks


def find_phase(buf: bytes | bytearray) -> int:
    """Byte phase (0 or 1) that yields 6000-word sync gaps.

    A capture that begins mid-word shifts every u16 by a byte and no marker
    lands where it should. This only affects *classification*; the raw stream
    is written to disk untouched either way.
    """
    best, best_n = 0, -1
    for phase in (0, 1):
        _l, _c, n, _b = split_lines(buf, phase)
        if n > best_n:
            best, best_n = phase, n
    return best


# --------------------------------------------------------------------------
# the run detector — hysteresis over the window verdicts
# --------------------------------------------------------------------------

STOP_DARK = "dark"
STOP_ROLL_END = "roll_end"


@dataclass
class RunState:
    """What the detector believes, in a form the UI can render directly."""
    state: str = UNKNOWN
    lines: int = 0
    film_lines: int = 0
    clear_run: int = 0
    dark_run: int = 0
    film_run: int = 0
    seen_film: bool = False
    leader: bool = True
    stop: str | None = None
    stop_detail: str = ""
    history: list = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "state": self.state, "lines": self.lines,
            "film_lines": self.film_lines, "clear_run": self.clear_run,
            "dark_run": self.dark_run, "film_run": self.film_run,
            "seen_film": self.seen_film, "leader": self.leader,
            "stop": self.stop, "stop_detail": self.stop_detail,
        }


class RunDetector:
    """Turns a stream of window verdicts into one decision: keep going, or stop.

    Two ways to stop, and they are not symmetric.

    **DARK stops at once.** ``DARK_CONFIRM_LINES`` is two windows, about half a
    second, which is only long enough that a single splice or dropout cannot
    end a roll. It is not a "wait and see".

    **Roll end has to earn it.** ``ROLL_END_LINES`` of *continuous* CLEAR is
    about 2.7 frame pitches, so an inter-frame gap (a few hundred lines) and a
    blank frame (one pitch) both fail it. And it does not arm until
    ``LEADER_FILM_LINES`` of film have gone past, so the clear leader at the
    head of a roll cannot stop a scan before the film arrives.

    ``dark_stops=False`` exists for exactly one caller: the deliberate
    lamp-off experiment, where the lamp is *known* to be off, every window is
    therefore DARK by definition, and there is no lamp failure left to detect.
    Classification is unaffected — the windows still read DARK and still say so
    — only the stop is withheld, and the hard time limit becomes the sole
    bound. Never set it for a scan carrying film.
    """

    def __init__(self, dark_confirm: int = DARK_CONFIRM_LINES,
                 roll_end: int = ROLL_END_LINES,
                 leader_film: int = LEADER_FILM_LINES,
                 history: int = 512,
                 dark_stops: bool = True) -> None:
        self.dark_confirm = int(dark_confirm)
        self.roll_end = int(roll_end)
        self.leader_film = int(leader_film)
        self.max_history = int(history)
        self.dark_stops = bool(dark_stops)
        self.s = RunState()

    def feed(self, v: Verdict) -> RunState:
        s = self.s
        n = max(0, int(v.lines))
        s.lines += n
        s.state = v.state
        if len(s.history) < self.max_history:
            s.history.append((s.lines, v.state, round(v.t, 5)))

        if v.state == DARK:
            s.dark_run += n
            s.clear_run = 0
            s.film_run = 0
        elif v.state == CLEAR:
            s.clear_run += n
            s.dark_run = 0
            s.film_run = 0
        elif v.state == FILM:
            s.film_run += n
            s.film_lines += n
            s.dark_run = 0
            s.clear_run = 0
            if s.film_lines >= self.leader_film:
                s.seen_film = True
                s.leader = False
        else:
            # UNKNOWN — no complete lines. Do not reset the runs; an unreadable
            # window is not evidence that anything changed.
            return s

        if s.stop is None:
            if s.dark_run >= self.dark_confirm and self.dark_stops:
                s.stop = STOP_DARK
                s.stop_detail = (
                    f"{s.dark_run} lines at the dark reference — "
                    f"{v.reason}. The lamp has failed or the path is blocked.")
            elif s.seen_film and s.clear_run >= self.roll_end:
                s.stop = STOP_ROLL_END
                s.stop_detail = (
                    f"{s.clear_run} lines of clear gate after "
                    f"{s.film_lines} lines of film.")
        return s


# --------------------------------------------------------------------------
# offline: run the classifier over a capture file
# --------------------------------------------------------------------------

def classify_file(path: str | Path, gate: Gate | None = None,
                  window_lines: int = WINDOW_LINES,
                  max_windows: int = 0,
                  detector: RunDetector | None = None,
                  on_window=None) -> dict:
    """Stream a .bin through the classifier exactly as the live loop does.

    Reads sequentially in the same chunk size the capture loop uses, so this
    is a genuine rehearsal of the online path, not a different implementation
    that happens to agree.
    """
    gate = gate or Gate.from_calibration()
    det = detector if detector is not None else RunDetector()
    p = Path(path)
    counts = {CLEAR: 0, FILM: 0, DARK: 0, UNKNOWN: 0}
    windows = 0
    breaks = 0
    lines_seen = 0
    first_stop = None
    first_stop_line = 0
    phase = None
    buf = bytearray()
    need = window_lines * BYTES_PER_LINE + BYTES_PER_LINE
    with p.open("rb") as fh:
        while True:
            chunk = fh.read(1 << 20)
            if not chunk:
                break
            buf += chunk
            if phase is None and len(buf) >= 4 * BYTES_PER_LINE:
                phase = find_phase(buf[: 8 * BYTES_PER_LINE])
            if phase is None or len(buf) < need:
                continue
            lines, consumed, n, brk = split_lines(buf, phase)
            if consumed:
                del buf[:consumed]
                phase = 0
            breaks += brk
            if n == 0:
                continue
            for a in range(0, n, window_lines):
                blk = lines[a:a + window_lines]
                if blk.shape[0] < window_lines // 2:
                    break
                v = gate.classify_lines(blk, sync_breaks=brk)
                counts[v.state] += 1
                windows += 1
                lines_seen += v.lines
                st = det.feed(v)
                if on_window:
                    on_window(v, st)
                if st.stop and first_stop is None:
                    first_stop, first_stop_line = st.stop, st.lines
                if max_windows and windows >= max_windows:
                    break
            if max_windows and windows >= max_windows:
                break
    total = max(1, windows)
    return {
        "path": str(p),
        "windows": windows,
        "lines": lines_seen,
        "sync_breaks": breaks,
        "counts": counts,
        "fractions": {k: round(v / total, 4) for k, v in counts.items()},
        "verdict": max(counts, key=counts.get) if windows else UNKNOWN,
        "stop": first_stop,
        "stop_line": first_stop_line,
        "run": det.s.to_json(),
        "gate": gate.describe(),
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def cmd_thresholds(_a) -> int:
    print(json.dumps(Gate.from_calibration().describe(), indent=2))
    return 0


def cmd_classify(a) -> int:
    gate = Gate.from_calibration()
    rows: list = []

    def tick(v, st):
        if a.verbose:
            rows.append((st.lines, v.state, v.t, v.struct, v.level))

    r = classify_file(a.path, gate=gate, window_lines=a.window,
                      max_windows=a.max_windows, on_window=tick)
    if a.verbose:
        for line, state, t, struct, level in rows:
            print(f"  line {line:>9}  {state:<5}  t={t:+.5f}  "
                  f"struct={struct:9.1f}  level={level:9.1f}")
    r.pop("gate", None)
    print(json.dumps(r, indent=2))
    return 0


def cmd_selftest(a) -> int:
    """Regression test with data we already have. Exit non-zero on failure."""
    root = Path(a.captures or (_ROOT / "captures"))
    gate = Gate.from_calibration()
    print("gate thresholds (all derived from calibration/):")
    for k, v in gate.describe().items():
        print(f"  {k:<20} {v}")

    # 1. The clear reference reconstructed from the gain table must match the
    #    measured empty-gate capture, if that capture is on this machine.
    print("\nreconstruction of the clear reference from gain_2000x3.npy:")
    bright_p = root / "ref_bright.bin"
    if bright_p.is_file():
        with bright_p.open("rb") as fh:
            buf = fh.read(64 << 20)
        lines, _c, n, _b = split_lines(buf, find_phase(buf[: 8 * BYTES_PER_LINE]))
        meas = lines.reshape(n, PIXELS_PER_LINE, CHANNELS).astype(np.float64).mean(axis=0)
        err = gate.clear_ref - meas
        print(f"  {n} lines of {bright_p.name}: mean error {err.mean():+.2f} "
              f"counts on {meas.mean():.0f}, worst {np.abs(err).max():.0f} "
              f"({100*np.abs(err).max()/meas.mean():.2f} %)")
        if abs(err.mean()) > 50:
            print("  FAIL: reconstruction is biased")
            return 1
    else:
        print(f"  skipped — {bright_p} not on this machine")

    # 2. Known files, known verdicts. roll.bin is the regression that matters:
    #    it is a real lamp failure, 30 % film then 70 % dark.
    cases = [
        ("ref_dark.bin", DARK, STOP_DARK,
         "lamp off, acquisition running — must read DARK"),
        ("ref_bright.bin", CLEAR, None,
         "empty gate, lamp on — must read CLEAR, and must not stop, "
         "because roll end cannot arm before film is seen"),
        ("test_nofifo.bin", CLEAR, None,
         "clean 60 s empty-gate run, lamp brighter than the calibration"),
        ("roll.bin", None, STOP_DARK,
         "REAL LAMP FAILURE: ~30 % film then ~70 % dark. Must stop on DARK."),
    ]
    ok = True
    print("\ncaptures:")
    for name, expect_majority, expect_stop, why in cases:
        p = root / name
        if not p.is_file():
            print(f"  {name:<18} skipped — not on this machine")
            continue
        r = classify_file(p, gate=gate, window_lines=a.window)
        c = r["counts"]
        print(f"  {name:<18} {r['windows']:>5} windows  "
              f"clear={c[CLEAR]:<5} film={c[FILM]:<5} dark={c[DARK]:<5}  "
              f"stop={r['stop']}  ({why})")
        if expect_majority and r["verdict"] != expect_majority:
            print(f"     FAIL: majority verdict {r['verdict']!r}, "
                  f"expected {expect_majority!r}")
            ok = False
        if expect_stop and r["stop"] != expect_stop:
            print(f"     FAIL: stopped {r['stop']!r}, expected {expect_stop!r}")
            ok = False
        if expect_stop is None and r["stop"] is not None:
            print(f"     FAIL: stopped {r['stop']!r}, expected no stop")
            ok = False
        if name == "roll.bin":
            # It must see film first, then stop on dark — not stop immediately.
            if r["counts"][FILM] < 20:
                print(f"     FAIL: only {r['counts'][FILM]} film windows; the "
                      f"first third of this roll is real film")
                ok = False
            if r["stop"] == STOP_DARK and r["stop_line"] < 20000:
                print(f"     FAIL: stopped at line {r['stop_line']}, before "
                      f"the film had gone past")
                ok = False
            if r["stop_line"]:
                print(f"     stopped at line {r['stop_line']} of {r['lines']} "
                      f"({100*r['stop_line']/max(1,r['lines']):.1f} % in)")

    print("\nSELFTEST " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("thresholds", help="print the calibration-derived cuts")

    c = sub.add_parser("classify", help="classify a capture file offline")
    c.add_argument("path")
    c.add_argument("--window", type=int, default=WINDOW_LINES)
    c.add_argument("--max-windows", type=int, default=0)
    c.add_argument("-v", "--verbose", action="store_true")

    s = sub.add_parser("selftest", help="regression test against known captures")
    s.add_argument("--captures", default=None)
    s.add_argument("--window", type=int, default=WINDOW_LINES)

    a = ap.parse_args()
    if a.cmd == "thresholds":
        return cmd_thresholds(a)
    if a.cmd == "classify":
        return cmd_classify(a)
    if a.cmd == "selftest":
        return cmd_selftest(a)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
