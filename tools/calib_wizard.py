#!/usr/bin/env python3
"""Calibrate an unknown scanner from the hardware alone, without being asked.

    python3 tools/calib_wizard.py status     what would happen. Touches nothing.
    python3 tools/calib_wizard.py plan       the ordered steps, and why each
    python3 tools/calib_wizard.py run        do it (HARDWARE)
    python3 tools/calib_wizard.py selftest   the state machine, no hardware

WHY THIS EXISTS
---------------
Every piece needed to calibrate an F-135 from nothing already existed in this
project. None of them had ever been joined up, so in practice a second owner
could not calibrate at all: this unit only has working numbers because its
Windows registry happened to survive on an old VM disk image, and nobody else
gets that. In particular the lamp values -- ``Current_*``, ``DutyCycle_*``,
``DutyCycleOpenGate_*`` -- and the AFE ``Offset_*`` values are **not on the
EEPROM at any offset** (docs/69 s5.4). They are Calibration Wizard output that
lives only in the registry. Searching for them against the scanner's own
response is therefore not one way to get them; it is the only way.

IT SHOULD NOT NEED A WIZARD, AND MOSTLY IT DOES NOT
---------------------------------------------------
The one genuinely manual step looks like "take the film out". It is not, because
the machine can tell. So the common case has no prompt and no button:

    known serial          -> silent lookup, zero device traffic, forever
    unknown + gate empty  -> calibrate, unattended, report progress
    unknown + film loaded -> one sentence, then carry on by itself

WHAT "THE MACHINE CAN TELL" ACTUALLY MEANS -- read this before changing it
--------------------------------------------------------------------------
There are two signals and they are not symmetric.

**The DX board's film sensors** (status nibble bits 0x20 entry / 0x10 exit) are
a direct hardware measurement and are trusted absolutely when they speak. They
do not always speak. The board's status nibble rides on record 0 of a DX packet,
and with no film moving there are no records -- so an idle transport produces no
status at all. Measured, on this unit, from the owner's own back-to-back pair on
2026-08-12:

    captures/vf_bright.scan.json   film loaded   available True  present True
                                                 status_reports 244
    captures/vf_bright2.scan.json  empty gate    available False present None
                                                 status_reports 0

So ``film_sense.available == False`` is **the normal reading for an empty
gate**, not a fault and not a reason to nag. Treating "no sensor opinion" as
"ask the human" would put a prompt in front of the exact case that is supposed
to be silent. Treating it as "assume empty" would calibrate against film. It is
neither: it is *undetermined*, and something else has to decide.

**pakon_gate.Gate** is what decides. It classifies CLEAR / FILM / DARK from a
flat field, and on the same pair it is unambiguous -- ``clear_run 19712,
film_lines 0, state clear`` on the empty gate against ``film_lines 9984, state
film`` on the loaded one. It needs a flat field to classify with, which an
uncalibrated scanner does not have; it borrows the repo reference for this one
coarse yes/no, which is legitimate because a 70 %-of-swing threshold does not
care whose unit measured the swing, and it is labelled ``borrowed`` wherever it
is reported.

Hence the order in :meth:`Wizard.check_gate`:

  1. A no-motion DX poll first. If it positively says film, nothing starts --
     the motor never turns.
  2. Otherwise a short lamp-on probe, which the search needs anyway. Its live
     ``window`` events are the gate classifier, and its own DX polling is the
     film sensors again with the transport actually moving.
  3. FILM from either one aborts before anything is stored, and the run resumes
     by itself once the gate reads clear.

Calibrating with film in the gate is the one outcome that must be impossible.
It fails silently -- the flat field simply bakes in the film's density -- and
poisons that serial's stored tables for good.

THE ORDER OF THE SEARCHES, AND WHY THE BLACK LEVEL IS FIRST
------------------------------------------------------------
The black level is searched before the lamp, because every measurement the lamp
search makes is a number *above* the black level, and if the black level is
clipped at ADC code 0 then those numbers are lower bounds on quantities nobody
can see. docs/72 is the record: a 33,226-line base-8 dark reference in which
every single sample was exactly 0, caused by the AD9826's 9-bit
sign-magnitude offset register being written as two's complement, so a
requested -19 reached the part as -237. Fixed in
``pakon_commands.afe_offset_word``.

That bug is fixed, and the black level still has to be searched, because the
value that is right for one configuration is not right for another -- which is
exactly why the vendor stores ``Offset_R/G/B`` per DpiBase x film mode rather
than once per machine.

NOTHING HERE WRITES INTO calibration/
--------------------------------------
Each candidate exposure is written to its own directory under the store and
handed to ``pakon_scan.py run --cal-dir``. The repo's ``calibration/`` is read
for the borrowed gate reference and is never modified, by this or by anything
it calls. The finished tables are stored per serial, append-only, on the same
never-delete/timestamp convention as every other calibration artefact in this
project.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(HERE))
REPO = HERE.parent

import build_calibration as bcal        # noqa: E402
import calib_profile as cprof           # noqa: E402
import calib_resolve as cres            # noqa: E402
import calib_store as cs                # noqa: E402
import pakon_commands as pc             # noqa: E402

# --------------------------------------------------------------------------
# states -- what the operator is told, and what the app renders
# --------------------------------------------------------------------------

READY = "ready"                  # calibrated. Nothing to do, nothing touched.
NEEDS_CALIBRATION = "needs-calibration"   # unknown scanner, gate not yet judged
FILM_IN_GATE = "film-in-gate"    # the ONE sentence a person ever sees
AMBIGUOUS = "ambiguous"          # several units stored; calib_resolve decides
RUNNING = "running"
UNREACHABLE = "unreachable"      # the target cannot be met on this hardware
FAILED = "failed"
DONE = "done"

#: What the operator is shown at each state. One sentence each, on purpose.
HEADLINES = {
    READY: "This scanner is calibrated. Nothing needs to be read or measured.",
    NEEDS_CALIBRATION: "Setting this scanner up. This runs by itself.",
    FILM_IN_GATE: "Remove the film to finish setup.",
    AMBIGUOUS: "More than one scanner has been calibrated on this computer. "
               "Which one is plugged in?",
    RUNNING: "Calibrating. This runs by itself and takes a few minutes.",
    UNREACHABLE: "This scanner's lamp cannot reach the exposure the "
                 "calibration needs.",
    FAILED: "Calibration stopped.",
    DONE: "Calibrated. This scanner will not need to do that again.",
}

# --------------------------------------------------------------------------
# the steps
# --------------------------------------------------------------------------

STEP_GATE = "gate"
STEP_EEPROM = "eeprom"
STEP_BLACK = "black-level"
STEP_DUTY = "lamp-duty"
STEP_DARK = "dark-reference"
STEP_BRIGHT = "bright-reference"
STEP_BUILD = "build"
STEP_STORE = "store"

STEPS = (STEP_GATE, STEP_EEPROM, STEP_BLACK, STEP_DUTY, STEP_DARK,
         STEP_BRIGHT, STEP_BUILD, STEP_STORE)

STEP_TEXT = {
    STEP_GATE: "Checking the film gate is empty",
    STEP_EEPROM: "Reading the scanner's memory (once, ever)",
    STEP_BLACK: "Setting the black level",
    STEP_DUTY: "Setting the lamp brightness",
    STEP_DARK: "Measuring the sensor with the lamp off",
    STEP_BRIGHT: "Measuring the sensor with the lamp on",
    STEP_BUILD: "Building this scanner's correction tables",
    STEP_STORE: "Saving them under this scanner's serial number",
}

STEP_WHY = {
    STEP_GATE: (
        "A flat field measured through film is a flat field with that film's "
        "density baked into it. It looks fine and is wrong for every scan "
        "afterwards, so this is checked before anything moves."),
    STEP_EEPROM: (
        "The colour matrices and the serial number are on the scanner's "
        "EEPROM. This hardware returns good bytes on the first read after a "
        "power cycle and corrupted bytes on every read after that, while "
        "reporting success throughout -- so it is read exactly once and "
        "never re-read to 'check'."),
    STEP_BLACK: (
        "The AFE's black level has to sit above the ADC's bottom code before "
        "anything above it can be measured. It is a per-configuration "
        "calibration output -- the vendor stores Offset_R/G/B per DpiBase x "
        "film mode -- and it is not on the EEPROM. docs/72."),
    STEP_DUTY: (
        "The lamp duty cycles are not on the EEPROM either. They exist only "
        "in the Windows registry of a machine that ran the vendor software, "
        "so for any scanner but this project's own they can only be found by "
        "searching against the scanner's own response. This is what the "
        "vendor's FN_bCalibrateFindLedCurrent does."),
    STEP_DARK: (
        "Per-pixel dark offset. Lamp off, empty gate."),
    STEP_BRIGHT: (
        "Per-pixel gain: sensor PRNU, lens falloff and the illumination "
        "profile together. Lamp on, empty gate, and NOTHING about the "
        "configuration may change between this and the dark reference."),
    STEP_BUILD: (
        "dark_2000x3 and gain_2000x3, plus a record of the exact exposure "
        "they are valid for."),
    STEP_STORE: (
        "Stored against this scanner's serial number, so every later launch "
        "is a lookup with no device traffic at all."),
}

# --------------------------------------------------------------------------
# tuning -- every one of these is a bound, not a preference
# --------------------------------------------------------------------------

#: DPI base to calibrate at. 16 is the only base with a committed reference in
#: this repo, and holding the ON-COUNT constant is what carries an exposure
#: across bases (see ScanConfig.from_calibration's derive path), so calibrating
#: at one base is not a restriction to it.
DEFAULT_BASE = 16

#: Bytes per capture. One 3-channel line is 6000 words = 12,000 bytes.
PROBE_BYTES = 24_000_000            # ~2,000 lines. Enough to measure a level.
DARK_BYTES = 180_000_000            # ~15,000 lines
BRIGHT_BYTES = 96_000_000           # ~8,000 lines

#: How many rounds each search may take before it gives up and says so. The
#: duty search halves on a clipped probe, so it converges from any overshoot in
#: log2(overshoot) rounds; six is far more than the two a 4x overshoot needs.
MAX_BLACK_ROUNDS = 4
MAX_DUTY_ROUNDS = 6

#: How close to the target counts as landed.
BLACK_TOLERANCE = 350.0             # wire counts
DUTY_TOLERANCE = 0.03               # fraction of target

#: The no-motion film-sense pre-check. Bounded, because on an empty gate it is
#: expected to return nothing at all and must not hang waiting for an opinion
#: the board has no reason to offer.
FILM_PRECHECK_S = 2.0
FILM_PRECHECK_INTERVAL = 0.02

#: How long to keep looking after film is found, before reporting again.
FILM_RECHECK_S = 3.0

#: IR-off level clamps (fcn.100203c0). Raising Current_* is the legitimate
#: response to an unreachable target; these are the ceilings it may be raised
#: to, and they are the reason a target can be genuinely unreachable.
LEVEL_CLAMPS_IR_OFF = {"R": 4, "G": 20, "B": 20}


class WizardRefused(Exception):
    """Refused before anything was sent to the scanner."""


# --------------------------------------------------------------------------
# assessment -- pure disk, no device anywhere in reach
# --------------------------------------------------------------------------

def flatfield_state(store: cs.CalibrationStore,
                    serial: int | None) -> dict:
    """Does this serial have a flat field of its own? Disk only."""
    if serial is None:
        return {"have": False, "serial": None, "source": None}
    ff = store.flatfield(int(serial)) if hasattr(store, "flatfield") else None
    if not ff:
        return {"have": False, "serial": int(serial), "source": None}
    return {"have": True, "serial": int(serial),
            "source": ff.get("dir"), "stamp": ff.get("stamp"),
            "config": (ff.get("meta") or {}).get("config")}


def assess(store: cs.CalibrationStore | Path | str | None = None) -> dict:
    """What this computer knows, and therefore what would happen.

    NO DEVICE IS REACHABLE FROM HERE. Same structural rule as calib_resolve and
    calib_profile: this function imports no transport, takes no transport, and
    every branch is a function of bytes already on disk. It is safe to call on
    every render.
    """
    st = store if isinstance(store, cs.CalibrationStore) \
        else cs.CalibrationStore(store)
    rep = cres.resolve(st)
    serial = rep.get("serial")
    ff = flatfield_state(st, serial)

    out = {
        "state": NEEDS_CALIBRATION,
        "serial": serial,
        "resolution": rep,
        "flatfield": ff,
        "steps": plan(rep, ff),
        "may_auto_read": False,
        "device_read_performed": False,
        "warnings": list(rep.get("warnings") or []),
    }

    if rep["state"] == cres.AMBIGUOUS:
        out["state"] = AMBIGUOUS
    elif rep["state"] == cres.READY and ff["have"]:
        out["state"] = READY
    out["headline"] = HEADLINES[out["state"]]
    out["automatic"] = out["state"] == NEEDS_CALIBRATION
    return out


def plan(resolution: dict, ff: dict) -> list[dict]:
    """The ordered steps, each marked needed or already done. Disk only."""
    have_read = resolution.get("state") == cres.READY
    done = {
        STEP_GATE: False,
        STEP_EEPROM: bool(have_read),
        STEP_BLACK: False,
        STEP_DUTY: False,
        STEP_DARK: False,
        STEP_BRIGHT: False,
        STEP_BUILD: bool(ff.get("have")),
        STEP_STORE: bool(ff.get("have")),
    }
    return [{"step": s, "text": STEP_TEXT[s], "why": STEP_WHY[s],
             "needed": not done[s], "hardware": s != STEP_BUILD}
            for s in STEPS]


# --------------------------------------------------------------------------
# what the gate says
# --------------------------------------------------------------------------

@dataclass
class GateVerdict:
    """Film in the gate: yes, no, or nobody has said.

    ``present`` is deliberately tri-state. See this module's docstring: on this
    hardware an empty gate produces no sensor opinion at all, so ``None`` is
    the ordinary reading and must not be collapsed into either answer.
    """
    present: bool | None = None
    source: str = "none"
    sensors_available: bool = False
    at_entry: bool | None = None
    at_exit: bool | None = None
    status_reports: int = 0
    gate_state: str | None = None
    gate_borrowed: bool = False
    detail: str = ""

    def to_json(self) -> dict:
        return dict(self.__dict__)


def film_precheck(link, seconds: float = FILM_PRECHECK_S) -> GateVerdict:
    """Ask the film sensors, without moving anything.

    Register reads on the light board only: no motor, no lamp, no acquire, no
    image endpoint. Bounded by ``seconds`` because the honest outcome on an
    empty gate is silence, and a poll that waits for an answer that is not
    coming would put a delay in front of the case that is meant to be
    invisible.

    Returns ``present=True`` only on a status nibble that actually arrived.
    Everything else is ``None`` -- undetermined -- and the caller goes on to the
    probe, which is a positive measurement.
    """
    import dx_read as dxr

    reader = dxr.DxReader(link.xfer, log_path=None, gate=False,
                          interval=FILM_PRECHECK_INTERVAL)
    v = GateVerdict(source="film-sensors")
    deadline = time.monotonic() + float(seconds)
    while time.monotonic() < deadline:
        pkt = reader.poll()
        if pkt is None or not getattr(pkt, "status_valid", False):
            time.sleep(FILM_PRECHECK_INTERVAL)
            continue
        v.status_reports += 1
        v.sensors_available = True
        v.at_entry = pkt.film_at_entry
        v.at_exit = pkt.film_at_exit
        if pkt.film_at_entry or pkt.film_at_exit:
            v.present = True
            v.detail = ("the film sensors report film in the transport "
                        f"(entry={pkt.film_at_entry}, exit={pkt.film_at_exit})")
            return v
        v.present = False
        v.detail = "the film sensors report the transport clear"
    if not v.sensors_available:
        v.detail = (
            "the film sensors said nothing in "
            f"{seconds:.0f} s. That is the ordinary reading for an empty gate "
            "-- the DX board's status nibble rides on a queued event and an "
            "idle transport queues none -- so it is undetermined here, not "
            "'clear'. The probe capture settles it.")
    return v


def verdict_from_run(result: dict, trust_classifier: bool = True) -> GateVerdict:
    """The gate verdict a completed capture already contains.

    ``run_scan`` polls the film sensors and classifies every window through
    ``pakon_gate`` as a matter of course, so a probe capture answers the
    question without a single extra transaction. The sensors win when they
    spoke; the classifier is the positive determination when they did not --
    UNLESS ``trust_classifier=False``, in which case the classifier's opinion
    is not consulted at all and an unopinionated sensor read stays
    undetermined (``present=None``, not a film verdict).

    Why that escape hatch exists: ``pakon_gate``'s classifier compares the
    live capture against a *borrowed* reference (this repo's existing
    calibration/, built at whatever exposure it happened to be captured at).
    That comparison is only meaningful when the live capture's own exposure is
    close to the borrowed reference's. During ``step_duty``'s search, it is
    not -- on-counts sweep from near-saturation down to a fraction of the
    borrowed reference's own duty -- and a genuinely empty gate at one of
    those intermediate exposures reads dimmer than the reference's clear_cut
    for the capture's *entire* duration, not just a noisy window or two.
    Confirmed on hardware: 1792/1792 lines read "film" at on-counts
    [160,145,127] with the gate independently confirmed empty, reproducing
    identically across repeated runs. Trusting the classifier here does not
    add safety, since it is not detecting film -- it is detecting "this
    exposure differs from the borrowed reference's," which is true by
    construction mid-search and stops the run whether or not film is present.
    """
    fs = result.get("film_sense") or {}
    # ScanResult calls it `run`; the capture sidecar calls the same dict
    # `run_detector`. Accept either, so this works on a live NDJSON `done`
    # event and on a sidecar read back off disk.
    rd = result.get("run_detector") or result.get("run") or {}
    v = GateVerdict(
        sensors_available=bool(fs.get("available")),
        at_entry=fs.get("at_entry"),
        at_exit=fs.get("at_exit"),
        status_reports=int(fs.get("status_reports") or 0),
        gate_state=rd.get("state"),
        gate_borrowed=True,
    )
    if v.sensors_available and fs.get("present") is not None:
        v.present = bool(fs.get("present"))
        v.source = "film-sensors"
        v.detail = (f"the film sensors reported {v.status_reports} times and "
                    f"say the transport is "
                    f"{'loaded' if v.present else 'clear'}")
        return v

    if not trust_classifier:
        v.present = None
        v.detail = ("the film sensors said nothing, and the gate classifier's "
                    "borrowed reference is not valid at this un-converged "
                    "search exposure -- not consulted")
        return v
    film_lines = int(rd.get("film_lines") or 0)
    clear_run = int(rd.get("clear_run") or 0)
    v.source = "gate-classifier"
    if film_lines > 0 or rd.get("state") == "film":
        v.present = True
        v.detail = (f"the film sensors said nothing, and the gate classifier "
                    f"saw {film_lines} lines of film")
    elif clear_run > 0 or rd.get("state") == "clear":
        v.present = False
        v.detail = (f"the film sensors said nothing -- normal for an empty "
                    f"gate -- and the gate classifier read CLEAR for "
                    f"{clear_run} lines")
    else:
        v.present = None
        v.detail = (f"neither signal reached a verdict "
                    f"(classifier state {rd.get('state')!r})")
    return v


# --------------------------------------------------------------------------
# the run
# --------------------------------------------------------------------------

class FilmInGate(Exception):
    """The one outcome that needs a person, raised the moment it is seen."""

    def __init__(self, verdict: GateVerdict):
        super().__init__(verdict.detail)
        self.verdict = verdict


class Unreachable(Exception):
    """The target cannot be met on this hardware. Reported, never clamped."""

    def __init__(self, info: dict):
        super().__init__(info["reason"])
        self.info = info


@dataclass
class Progress:
    """Everything the UI needs, and nothing it has to interpret."""
    state: str = RUNNING
    step: str = ""
    text: str = ""
    detail: str = ""
    fraction: float = 0.0
    round: int = 0
    warnings: list = field(default_factory=list)
    measurements: list = field(default_factory=list)

    def to_json(self) -> dict:
        d = dict(self.__dict__)
        d["headline"] = HEADLINES.get(self.state, "")
        return d


class Wizard:
    """The unattended calibration. One instance per attempt.

    Every capture goes out through ``pakon_scan.py run`` as a subprocess, the
    same way the app's own scan supervisor does it, for the same reason: the
    USB handle belongs to one process and a calibration that crashes must not
    take the backend's handle with it. It also means every guard in ``cmd_run``
    -- the film-path refusal, the stale-marker recovery, the safe stop on every
    path -- applies unchanged to a calibration capture.
    """

    def __init__(self, store: cs.CalibrationStore | None = None, *,
                 base: int = DEFAULT_BASE,
                 target: float = bcal.VENDOR_TARGET_LEVEL,
                 metric: str = bcal.DEFAULT_METRIC,
                 black_target: float = bcal.BLACK_TARGET_WIRE,
                 progress=None,
                 dry_run: bool = False,
                 workdir: Path | None = None) -> None:
        self.store = store or cs.CalibrationStore()
        self.base = int(base)
        self.target = float(target)
        self.metric = metric
        self.black_target = float(black_target)
        self._progress = progress or (lambda p: None)
        self.dry_run = bool(dry_run)
        self.stamp = time.strftime(cs.STAMP_FMT, time.gmtime())
        self.workdir = Path(workdir) if workdir else (
            self.store.root / "wizard" / self.stamp)
        self.p = Progress()
        self.serial: int | None = None
        self.captures: dict[str, Path] = {}
        self.config: dict = {}

    # ---- reporting ----
    def emit(self, step: str = "", detail: str = "", fraction: float | None = None,
             state: str | None = None) -> None:
        if step:
            self.p.step = step
            self.p.text = STEP_TEXT.get(step, step)
        if detail:
            self.p.detail = detail
        if fraction is not None:
            self.p.fraction = float(fraction)
        if state:
            self.p.state = state
        self._progress(self.p)

    def warn(self, text: str) -> None:
        if text and text not in self.p.warnings:
            self.p.warnings.append(text)
        self._progress(self.p)

    def measured(self, what: str, **kw) -> None:
        self.p.measurements.append({"what": what, **kw})
        self._progress(self.p)

    # ---- candidate exposures ----
    def candidate_dir(self, label: str) -> Path:
        """A directory holding one candidate README.json.

        NEVER ``calibration/``. ``pakon_scan.py run --cal-dir`` reads the
        exposure from here, so a search can drive the scanner at values that
        are not installed and may never be.
        """
        d = self.workdir / label
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_candidate(self, label: str, config: dict) -> Path:
        d = self.candidate_dir(label)
        (d / "README.json").write_text(json.dumps({
            "unit": f"calibration wizard candidate, serial "
                    f"{self.serial if self.serial is not None else 'unknown'}",
            "captured": time.strftime("%Y-%m-%d"),
            "generated_by": "tools/calib_wizard.py",
            "note": "CANDIDATE ONLY. Not a calibration. Written so that "
                    "pakon_scan.py run --cal-dir can drive the scanner at "
                    "these values without touching calibration/.",
            "config": config,
            "domain": "wire_u16",
        }, indent=2) + "\n")
        return d

    # ---- the starting exposure ----
    def seed_config(self) -> dict:
        """Where the search starts. Borrowed, and labelled as borrowed.

        A search needs a first point, and the only per-unit numbers on this
        computer belong to a different machine. Borrowing them as a *starting
        point* is safe in a way that borrowing them as a calibration is not:
        they are inside the hardware's own clamps, and every number here is
        replaced by a measurement before anything is stored.
        """
        prof = cprof.profile(self.store, serial_hint=self.serial)
        cfg = dict(prof.config or {})
        if not cfg:
            raise WizardRefused(
                "there is no exposure to start the search from -- no per-unit "
                "overlay, and no calibration/README.json in this checkout. "
                "The search needs one starting point; it does not need it to "
                "be correct.")
        if prof.config_source == cprof.FROM_BORROWED:
            self.warn(
                "the search is starting from another scanner's exposure "
                f"(serial {cprof.REFERENCE_SERIAL}). That is a starting point, "
                f"not a calibration: every value in it is replaced by a "
                f"measurement from this scanner before anything is stored.")
        from pakon_scan import EXPOSURE_INTEGRATION
        integ = EXPOSURE_INTEGRATION.get(self.base)
        if integ:
            cfg["integration_0x82_idx6"] = integ
            cfg["lamp_pwm_N"] = int(integ * 0.24)
        cfg["dpi_base"] = f"DpiBase{self.base}_35"
        return cfg

    # ---- capture ----
    def capture(self, label: str, config: dict, *, lamp: bool,
                max_bytes: int, check_film: bool = True) -> dict:
        """One ``pakon_scan.py run``. Returns its ``done`` record.

        ``check_film=False`` skips the LIVE per-window abort below (not the
        film sensors, and not the caller's own post-hoc ``verdict_from_run``
        check on the completed ``done`` record -- both still apply). Use this
        only for throwaway probe captures at a candidate exposure that has not
        converged yet, e.g. ``step_duty``'s search rounds. The live abort
        classifies each ~256-line window against ``pakon_gate``'s *borrowed*
        reference (this repo's existing calibration/, captured at whatever
        exposure it happened to be built at) with zero tolerance -- a single
        window is enough to kill the capture. That is fine once the search has
        converged near the target exposure, where the borrowed reference's
        absolute thresholds are close to valid. Mid-search, on-counts can be a
        fraction of the borrowed reference's own exposure, so a genuinely empty
        gate can read dimmer than that reference's clear_cut and trip a false
        positive -- confirmed reproducing deterministically on this hardware
        (same round, twice, gate independently confirmed empty both times).
        The whole-capture ``verdict_from_run`` check the caller runs on the
        returned ``done`` is not this fragile: it prefers the real DX film
        sensors when they have an opinion, and falls back to pakon_gate's
        *aggregate* state over the whole run rather than one window snapshot.

        THE LIVE FILM ABORT ONLY APPLIES WITH THE LAMP ON. ``pakon_gate``
        classifies by how much light reaches the sensor, so with the lamp off
        every window is dark by construction and its FILM/CLEAR opinion means
        nothing -- a lamp-off capture that happened to land between the dark
        and clear thresholds would abort a perfectly good black-level
        measurement and report film that is not there. The lamp-off captures
        are covered by the lamp-on ones on either side of them: the gate is
        judged before the black-level search starts and again on the bright
        reference, and nothing moves in between.
        """
        d = self.write_candidate(label, config)
        out = self.workdir / f"{label}.bin"
        argv = [sys.executable, str(HERE / "pakon_scan.py"), "run", str(out),
                "--cal-dir", str(d), "--base", str(self.base),
                "--max-bytes", str(int(max_bytes)), "--json", "--force"]
        if not lamp:
            argv.append("--no-lamp")
        if self.dry_run:
            argv.append("--dry-run")

        done: dict = {}
        errors: list[str] = []
        aborted = False
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, bufsize=1)
        try:
            for line in proc.stdout:
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(ev, dict):
                    continue
                t = ev.get("t")
                if t == "done":
                    done = ev
                elif t == "warn":
                    self.warn(str(ev.get("message") or ""))
                elif t == "error":
                    errors.append(str(ev.get("message") or ""))
                elif t == "window" and not aborted:
                    w = ev.get("window") or {}
                    r = ev.get("run") or {}
                    self.emit(detail=f"{r.get('lines', 0):,} lines, "
                                     f"gate {w.get('state', '?')}")
                    # Stop the moment film is seen. Do not wait for the run to
                    # finish: the point is not to measure through film, and a
                    # completed capture is a capture somebody might use. SIGTERM
                    # rather than kill, because pakon_scan's signal handler is
                    # what stops the transport and turns the lamp off -- killing
                    # it outright would leave the motor running.
                    if check_film and lamp and (w.get("state") == "film"
                                 or (r.get("film_lines") or 0)):
                        aborted = True
                        proc.terminate()
        finally:
            # Drain rather than close: closing the pipe under a child that is
            # still writing gives it EPIPE, which turns a clean cancellation
            # into a crash and loses the stop it was in the middle of making.
            try:
                proc.stdout.read()
            except Exception:                               # noqa: BLE001
                pass
            try:
                proc.stdout.close()
            except Exception:                               # noqa: BLE001
                pass
            code = proc.wait()
            try:
                err = (proc.stderr.read() or "")[-1200:]
                proc.stderr.close()
            except Exception:                               # noqa: BLE001
                err = ""
        done["_exit"] = code
        done["_errors"] = errors
        done["_stderr"] = err
        done["_path"] = str(out)
        done["_aborted_film"] = aborted
        if aborted:
            raise FilmInGate(GateVerdict(
                present=True, source="gate-classifier", gate_state="film",
                gate_borrowed=True,
                detail="film appeared in the gate during the "
                       f"{label} capture; it was stopped rather than "
                       "measured through"))
        if not out.is_file() or (code != 0 and not done.get("path")):
            raise WizardRefused(
                f"the {label} capture did not complete (exit {code}). "
                + (errors[0] if errors else
                   err.strip().splitlines()[-1] if err.strip()
                   else "no reason was reported."))
        self.captures[label] = out
        return done

    def load(self, label: str, role: str) -> bcal.Capture:
        return bcal.Capture(self.captures[label], role)

    # ---- the steps ----
    def step_gate(self, link=None) -> GateVerdict:
        self.emit(STEP_GATE, fraction=0.02)
        if link is not None:
            v = film_precheck(link)
            if v.present is True:
                self.emit(state=FILM_IN_GATE, detail=v.detail)
                return v
            self.emit(detail=v.detail)
            return v
        return GateVerdict(detail="no pre-check link was supplied")

    def step_eeprom(self) -> int | None:
        """One read per power cycle, or none at all if one is already stored.

        Every guard in ``calib_read.do_read`` applies unchanged and none is
        weakened here: the read-once marker, the power-cycle guard, the lock,
        the pinned firmware hash, bytes-to-disk-before-interpretation, and the
        refusal to re-read. In particular this NEVER re-reads to check a value,
        which is the instinct the whole subsystem exists to suppress.
        """
        self.emit(STEP_EEPROM, fraction=0.08)
        rep = cres.resolve(self.store)
        if rep.get("state") == cres.READY and rep.get("serial") is not None:
            self.serial = int(rep["serial"])
            self.emit(detail=f"already read; this is scanner {self.serial}. "
                             f"Nothing was sent to the scanner.")
            return self.serial

        import calib_device as cd
        import calib_read as cread
        transport = cd.UsbTransport()
        guard = cd.PowerCycleGuard(transport, self.store.root / "journal")
        res = cread.do_read(self.store, transport, guard, source="calib_wizard")
        rec = res["record"]
        self.serial = rec.serial
        if self.serial is None:
            raise WizardRefused(
                "the read completed but the page did not pass the structural "
                "checks, so its serial number cannot be trusted. A corrupt u32 "
                "makes a convincing-looking serial, and attributing this "
                "calibration to the wrong unit is worse than not storing it. "
                "The bytes are saved either way: " + str(rec.path))
        self.emit(detail=f"scanner {self.serial}, read {rec.stamp}. "
                         f"This will not be read again.")
        return self.serial

    def step_black(self, config: dict) -> dict:
        """Search the AFE offsets until the black level clears the floor.

        Measured, not modelled. The first round establishes where the black
        level is; a second round at a deliberately different offset establishes
        what the register is worth; from there it solves. The direction is
        never assumed -- see :func:`build_calibration.solve_offset`.
        """
        self.emit(STEP_BLACK, fraction=0.16)
        cfg = dict(config)
        caps: list[bcal.Capture] = []
        for rnd in range(1, MAX_BLACK_ROUNDS + 1):
            self.p.round = rnd
            label = f"black{rnd}"
            self.capture(label, cfg, lamp=False, max_bytes=PROBE_BYTES)
            cap = self.load(label, "dark")
            caps.append(cap)
            black = cap.channel_means()
            self.measured("black-level", round=rnd,
                          afe_offsets=list(cfg.get("afe_offsets") or []),
                          black=[round(float(v), 1) for v in black],
                          floored=cap.is_floored())
            self.emit(detail=f"black level {[round(float(v)) for v in black]} "
                             f"at offsets {cfg.get('afe_offsets')}")

            landed = (not cap.is_floored()
                      and all(bcal.BLACK_MIN_WIRE <= v <= bcal.BLACK_MAX_WIRE
                              for v in black))
            if landed:
                self.emit(detail=f"black level settled at "
                                 f"{[round(float(v)) for v in black]}")
                return cfg

            s = bcal.solve_offset(caps, self.black_target)
            if s["solvable"]:
                cfg = dict(cfg, afe_offsets=s["offsets_new"])
                continue
            # Not solvable yet: move every channel by a deliberate step so the
            # next round has two distinct settings to measure a slope from. The
            # direction is chosen to raise the black level if it is low and
            # lower it if it is high, using the sign the committed calibration
            # exhibits -- and if that turns out to be the wrong direction, the
            # NEXT round measures the true slope and corrects it, which is
            # exactly why this is a step and not an extrapolation.
            low = float(np.mean(black)) < self.black_target
            step = -6 if low else 6
            cur = [int(v) for v in (cfg.get("afe_offsets") or (0, 0, 0))]
            cfg = dict(cfg, afe_offsets=[int(v + step) for v in cur])
            self.emit(detail=f"probing the offset register's authority: "
                             f"{cur} -> {cfg['afe_offsets']}")
        raise WizardRefused(
            f"the black level did not settle in {MAX_BLACK_ROUNDS} rounds. "
            f"Last measurement {[round(float(v), 1) for v in black]} at "
            f"offsets {cfg.get('afe_offsets')}. Nothing has been stored. "
            f"docs/72 has what this step is doing and why.")

    def step_duty(self, config: dict, dark_cap: bcal.Capture) -> dict:
        """Search the lamp on-counts to the vendor's target.

        The target is a MAXIMUM, not a mean: docs/15 records that the vendor's
        check compares the maximum pixel of an averaged CCD line. Aiming the
        mean at 64000 on this unit pins about three quarters of the illuminated
        field at the rail -- measured, which is how it was found.
        """
        self.emit(STEP_DUTY, fraction=0.32)
        cfg = dict(config)
        dark_level = dark_cap.channel_means()
        dark_pixels = dark_cap.pixel_mean()
        for rnd in range(1, MAX_DUTY_ROUNDS + 1):
            self.p.round = rnd
            label = f"duty{rnd}"
            # check_film=False: this is a throwaway probe at a candidate
            # exposure that has not converged yet, where the live per-window
            # abort's borrowed reference is not valid (see capture()'s own
            # docstring). Safety is not weakened -- verdict_from_run below
            # still runs on the completed capture, preferring the real DX
            # film sensors and falling back to pakon_gate's aggregate state
            # over the whole run rather than a single window.
            done = self.capture(label, cfg, lamp=True, max_bytes=PROBE_BYTES,
                                check_film=False)

            # trust_classifier=False: the borrowed reference is not valid at
            # this un-converged search exposure (see verdict_from_run's own
            # docstring). Real DX film sensors still gate this -- they are
            # the primary signal and are not skipped, only the light-level
            # fallback is.
            v = verdict_from_run(done, trust_classifier=False)
            if v.present is True:
                self.emit(state=FILM_IN_GATE, detail=v.detail)
                raise FilmInGate(v)

            cap = self.load(label, "bright")
            got = cap.channel_metric(self.metric)
            self.measured("lamp", round=rnd,
                          on_counts=list(cfg.get("on_counts_R_G_B") or []),
                          measured=[round(float(x), 1) for x in got],
                          metric=self.metric, clipped=cap.is_clipped())
            self.emit(detail=f"{self.metric} {[round(float(x)) for x in got]} "
                             f"at on-counts {cfg.get('on_counts_R_G_B')}")

            s = bcal.solve_duty(cap, dark_level, self.target, self.metric,
                                dark_pixels)
            if not s["clipped"]:
                err = max(abs(float(x) - self.target) for x in got) / self.target
                if err <= DUTY_TOLERANCE:
                    self.emit(detail=f"lamp settled: {self.metric} "
                                     f"{[round(float(x)) for x in got]} "
                                     f"against a target of {self.target:.0f}")
                    return cfg
                if s["clamped"]:
                    raise Unreachable(self._unreachable(s, got, cfg))
                cfg = dict(cfg, on_counts_R_G_B=list(s["on_new"]))
                continue
            back = bcal._reprobe_on_counts(s, s.get("dark_at", dark_level))
            self.warn(f"round {rnd} clipped; a saturated reading carries "
                      f"almost no scale information, so the search bisects "
                      f"rather than solving: on-counts -> {back}")
            cfg = dict(cfg, on_counts_R_G_B=list(back))
        raise WizardRefused(
            f"the lamp did not settle on the {self.target:.0f} target in "
            f"{MAX_DUTY_ROUNDS} rounds. Nothing has been stored.")

    def _unreachable(self, s: dict, got, cfg: dict) -> dict:
        names = "".join("RGB"[i] for i in s["clamped"])
        levels = list(cfg.get("levels_R_G_B_Ir") or [])
        raisable = {c: LEVEL_CLAMPS_IR_OFF[c] for c in names
                    if c in LEVEL_CLAMPS_IR_OFF}
        return {
            "channels": names,
            "on_max": s["on_max"],
            "target": self.target,
            "metric": self.metric,
            "measured": [round(float(x), 1) for x in got],
            "levels": levels,
            "clamps_ir_off": LEVEL_CLAMPS_IR_OFF,
            "headroom": raisable,
            "reason": (
                f"channel(s) {names} are already at the PWM ceiling of N-2 = "
                f"{s['on_max']} and still short of the {self.target:.0f} "
                f"target. The lamp cannot be driven for longer than the line "
                f"period, so more duty is not available.\n\n"
                f"This is what an aged LED looks like, and it is not a "
                f"failure of the search. The legitimate response is to raise "
                f"the LED CURRENT for those channels -- levels_R_G_B_Ir, the "
                f"vendor's Current_* -- which raises the peak the duty is a "
                f"fraction of. With IR off the hardware clamps them at "
                f"R<={LEVEL_CLAMPS_IR_OFF['R']}, "
                f"G<={LEVEL_CLAMPS_IR_OFF['G']}, "
                f"B<={LEVEL_CLAMPS_IR_OFF['B']} (fcn.100203c0), and the "
                f"current levels are {levels}.\n\n"
                f"Nothing has been stored and nothing has been clamped "
                f"silently. Calibrating at a lower target is also valid -- the "
                f"gain table is a ratio and normalises out -- it simply uses "
                f"less of the ADC range."),
        }

    def step_references(self, config: dict) -> tuple[bcal.Capture, bcal.Capture]:
        """Dark then bright, at one settled configuration, back to back.

        NOTHING about the configuration changes between them. The only
        difference is the lamp. A dark and a bright reference from different
        setups produce a table that is silently wrong rather than noisy, which
        is why ``build_calibration.check_config`` compares the two sidecars and
        refuses on any disagreement -- and why both are captured here from one
        `config` dict that is not touched in between.
        """
        self.emit(STEP_DARK, fraction=0.55)
        self.capture("ref_dark", config, lamp=False, max_bytes=DARK_BYTES)
        dark = self.load("ref_dark", "dark")

        self.emit(STEP_BRIGHT, fraction=0.72)
        done = self.capture("ref_bright", config, lamp=True,
                            max_bytes=BRIGHT_BYTES)
        v = verdict_from_run(done)
        if v.present is True:
            self.emit(state=FILM_IN_GATE, detail=v.detail)
            raise FilmInGate(v)
        bright = self.load("ref_bright", "bright")
        return dark, bright

    def step_build(self, dark: bcal.Capture, bright: bcal.Capture) -> Path:
        self.emit(STEP_BUILD, fraction=0.88)
        bcal.check_config(dark, bright)
        for w in bcal.check_dark_floor(dark):
            self.warn(w)
        for w in bcal.check_clipping(bright, self.target, self.metric):
            self.warn(w)
        tables, gain, stats = bcal.build_tables(dark, bright)

        out = self.workdir / "tables"
        out.mkdir(parents=True, exist_ok=True)
        np.save(out / "dark_2000x3.npy", tables.astype(np.float32))
        np.save(out / "gain_2000x3.npy", gain.astype(np.float32))
        (out / "dark_2000x3.csv").write_text(
            bcal.csv_text(tables, bcal.DARK_CSV_HEADER, bcal.DARK_CSV_FMT))
        (out / "gain_2000x3.csv").write_text(
            bcal.csv_text(gain, bcal.GAIN_CSV_HEADER, bcal.GAIN_CSV_FMT))
        meta = bcal.build_readme(
            dark, bright, stats,
            unit=f"Kodak Pakon F-135 Plus, serial {self.serial}",
            target=self.target, metric=self.metric,
            notes={"generated_by": "tools/calib_wizard.py",
                   "unit_serial": self.serial,
                   "wizard_stamp": self.stamp,
                   "searched": ["afe_offsets", "on_counts_R_G_B"],
                   "search_note": (
                       "The AFE offsets and the lamp on-counts in config were "
                       "SEARCHED against this scanner's own response, not "
                       "copied. Neither is recoverable from the EEPROM at any "
                       "offset (docs/69 s5.4), so for any unit without a "
                       "surviving Windows registry this is the only way they "
                       "can exist.")})
        (out / "README.json").write_text(json.dumps(meta, indent=2) + "\n")

        # The second consumer has to accept the set or it is not installable,
        # whatever the numbers look like.
        k = float(np.asarray(stats["swing_means"]).mean())
        import pakon_gate as pgate
        pgate.Gate(tables.astype(np.float32), gain.astype(np.float32), k,
                   source=str(out))
        self.measured("tables",
                      dark_means=[round(float(v), 1)
                                  for v in stats["dark_means"]],
                      bright_means=[round(float(v), 1)
                                    for v in stats["bright_means"]],
                      level=round(float(stats["level"]), 1))
        return out

    def step_store(self, tables: Path) -> dict:
        """Under this scanner's serial. Append-only, nothing overwritten."""
        self.emit(STEP_STORE, fraction=0.97)
        meta = json.loads((tables / "README.json").read_text())
        rec = self.store.save_flatfield(
            self.serial, tables, meta=meta,
            source="calib_wizard", stamp=self.stamp)
        self.store.save_overlay(
            self.serial, meta.get("config") or {},
            source="calib_wizard",
            provenance=(
                f"searched on this scanner at DpiBase{self.base}_35 on "
                f"{self.stamp}. The AFE offsets and lamp on-counts are "
                f"measurements from this unit, not borrowed values."))
        return rec

    # ---- the whole thing ----
    def run(self, link=None) -> dict:
        """Every step, in order. Returns a report; never leaves a half-set."""
        self.workdir.mkdir(parents=True, exist_ok=True)
        try:
            v = self.step_gate(link)
            if v.present is True:
                return self.report(FILM_IN_GATE, gate=v.to_json())
            # step_gate is the only step that uses the precheck link -- every
            # later step (step_black, step_duty, step_references, ...) drives
            # the scanner through its own `pakon_scan.py run` subprocess, each
            # of which claims the USB interface itself. Holding this link
            # claimed past this point makes every one of those subprocesses
            # fail with "Access denied" (macOS libusb: interface already
            # claimed by another process). Close() is idempotent, so this is
            # safe even though cmd_run's own finally also closes it.
            if link is not None:
                link.close()

            self.step_eeprom()
            cfg = self.seed_config()
            cfg = self.step_black(cfg)
            dark_probe = self.load(
                sorted(k for k in self.captures if k.startswith("black"))[-1],
                "dark")
            cfg = self.step_duty(cfg, dark_probe)
            self.config = cfg
            dark, bright = self.step_references(cfg)
            tables = self.step_build(dark, bright)
            rec = self.step_store(tables)
            self.emit(state=DONE, fraction=1.0,
                      detail=f"scanner {self.serial} is calibrated")
            return self.report(DONE, stored=rec, tables=str(tables))
        except FilmInGate as e:
            return self.report(FILM_IN_GATE, gate=e.verdict.to_json())
        except Unreachable as e:
            self.emit(state=UNREACHABLE, detail=e.info["reason"].split("\n")[0])
            return self.report(UNREACHABLE, unreachable=e.info)
        except Exception as e:                              # noqa: BLE001
            self.emit(state=FAILED, detail=str(e))
            return self.report(FAILED, error=str(e))

    def report(self, state: str, **kw) -> dict:
        self.p.state = state
        return {"state": state, "headline": HEADLINES[state],
                "serial": self.serial, "workdir": str(self.workdir),
                "progress": self.p.to_json(),
                "config": self.config,
                "warnings": list(self.p.warnings),
                "measurements": list(self.p.measurements), **kw}


# numpy is only needed by the steps that build tables; importing it at the top
# would make `status` (pure disk, called on every render) pay for it.
import numpy as np                                          # noqa: E402


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _fmt_status(a: dict) -> str:
    out = [f"state    {a['state']}", f"         {a['headline']}"]
    if a["serial"] is not None:
        out.append(f"scanner  {a['serial']}")
    ff = a["flatfield"]
    out.append(f"tables   {'stored: ' + str(ff.get('source')) if ff['have'] else 'none for this scanner'}")
    out.append("")
    out.append("steps")
    for s in a["steps"]:
        mark = "todo" if s["needed"] else "done"
        out.append(f"  [{mark}] {s['text']}")
    for w in a["warnings"]:
        out.append(f"\nwarning: {w}")
    return "\n".join(out)


def cmd_status(args) -> int:
    a = assess(args.store)
    print(json.dumps(a, indent=2, default=str) if args.json else _fmt_status(a))
    return 0


def cmd_plan(args) -> int:
    a = assess(args.store)
    print(f"{a['headline']}\n")
    for s in a["steps"]:
        print(f"{'NEEDED' if s['needed'] else '  done'}  {s['text']}")
        for line in s["why"].split(". "):
            if line.strip():
                print(f"          {line.strip().rstrip('.')}.")
        print()
    return 0


def cmd_run(args) -> int:
    a = assess(args.store)
    if a["state"] == READY and not args.force:
        print(a["headline"])
        print("Nothing was sent to the scanner. --force to calibrate anyway.")
        return 0
    if a["state"] == AMBIGUOUS:
        print(a["headline"])
        print("Choose a unit first:  python3 tools/calib_resolve.py use <serial>")
        return 2

    def show(p: Progress) -> None:
        print(f"  [{p.fraction * 100:5.1f}%] {p.text}"
              + (f" -- {p.detail}" if p.detail else ""), flush=True)

    link = None
    try:
        if not args.no_precheck:
            from pakon_scan import Link
            link = Link.open()
    except Exception as e:                                  # noqa: BLE001
        print(f"note: no film-sense pre-check ({e}); the probe capture will "
              f"settle the gate instead")

    w = Wizard(cs.CalibrationStore(args.store), base=args.base,
               target=args.target, metric=args.metric, progress=show,
               dry_run=args.dry_run)
    try:
        rep = w.run(link)
    finally:
        if link is not None:
            link.close()

    print(f"\n{rep['headline']}")
    if rep["state"] == UNREACHABLE:
        print("\n" + rep["unreachable"]["reason"])
    elif rep["state"] == FAILED:
        print(f"\n{rep['error']}")
    for x in rep["warnings"]:
        print(f"\nwarning: {x}")
    if args.json:
        print("\n" + json.dumps(rep, indent=2, default=str))
    return 0 if rep["state"] == DONE else 1


def cmd_selftest(_a) -> int:
    import test_calib
    return test_calib.main()


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--store", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status", help="what would happen. Touches nothing.")
    s.add_argument("--json", action="store_true")

    sub.add_parser("plan", help="the ordered steps, and why each one exists")

    r = sub.add_parser("run", help="calibrate this scanner (HARDWARE)")
    r.add_argument("--base", type=int, default=DEFAULT_BASE, choices=(4, 8, 16))
    r.add_argument("--target", type=float, default=bcal.VENDOR_TARGET_LEVEL)
    r.add_argument("--metric", choices=bcal.METRICS,
                   default=bcal.DEFAULT_METRIC)
    r.add_argument("--force", action="store_true",
                   help="calibrate even though this scanner already has "
                        "tables. The existing set is kept -- nothing in this "
                        "project is ever overwritten or deleted.")
    r.add_argument("--dry-run", action="store_true",
                   help="build every capture command and send nothing")
    r.add_argument("--no-precheck", action="store_true",
                   help="skip the no-motion film-sense poll")
    r.add_argument("--json", action="store_true")

    sub.add_parser("selftest", help="the state machine, no hardware")

    a = ap.parse_args()
    try:
        return {"status": cmd_status, "plan": cmd_plan, "run": cmd_run,
                "selftest": cmd_selftest}[a.cmd](a)
    except WizardRefused as e:
        print(f"\nREFUSED: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
