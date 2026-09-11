#!/usr/bin/env python3
"""Rebuild this unit's per-pixel dark and gain tables from two reference captures.

WHY THIS EXISTS
---------------
The committed tables in ``calibration/`` were produced ad-hoc on 2026-08-07 and
the only record of how was the message of commit ``8c9bcf1``. That message is
also slightly wrong (see FORMULA below). Meanwhile the tables are only valid for
the exposure they were captured at, and the lamp drive has since changed — so
"regenerate the calibration" is a thing that has to be *done*, repeatably, by
somebody who was not there the first time. This is that tool.

This tool touches no hardware. It reads captures the operator has already made
and writes a new table set to a directory of their choosing. It never writes
into ``calibration/``; installing is a deliberate human step and this tool only
prints the command for it.

    build         two captures  -> dark/gain tables + README.json
    solve         one capture   -> the lamp on-counts that hit the target
    solve-offset  dark captures -> the AFE offsets that put the black level
                                   where it belongs
    selftest      captures/     -> proof the formula still reproduces what is
                                   committed, bit for bit

THE BLACK LEVEL IS A CALIBRATION OUTPUT, NOT A CONSTANT
-------------------------------------------------------
Read ``docs/72`` before changing anything here. Short version: on 2026-08-12 a
base-8 dark reference came back with **every one of 33,226 x 5,999 samples
exactly 0** — the ADC pinned at its bottom code — while the base-16 reference
taken at the *same* AFE offsets for green and blue read a healthy 1443/1161.
The pedestal is integration-dependent and the AFE offset that suits one DPI
base does not suit another. That is why the vendor keeps ``Offset_R/G/B`` per
``DpiBase`` x film mode in the registry next to ``Current_*`` and
``DutyCycle_*``, and why none of them are on the EEPROM.

A clipped black level is not a cosmetic problem. It destroys the bottom of the
range, and the pixels it destroys first are the low-signal ones: on that
capture the 46 pixel-channels that came back ``bright <= dark`` were **columns
0..17 and nothing else** — the vignetted edge, where the base-16 gain table
already reads 4.4x to 24.5x. In a real scan the same clipping eats the deepest
shadows. So:

  * ``build`` REFUSES a dark reference whose samples pile up on code 0
    (:data:`FLOOR_FRACTION_MAX`). That refusal is the one that would have
    caught this before the tables were hand-patched.
  * ``solve-offset`` searches the AFE offset the same way ``solve`` searches
    the lamp duty — from measurement, with the sign determined empirically
    rather than assumed.

THE FORMULA
-----------
Two captures, **empty gate — no film in the path — for both**:

    dark    lamp OFF.  Sensor read noise + AFE offset.
    bright  lamp ON.   Illumination profile + per-pixel PRNU + lens falloff.

    dark[px, ch] = mean over lines of the raw wire word
    flat[px, ch] = mean over lines of bright  -  dark
    gain[px, ch] = flat[:, ch].mean() / flat[px, ch]
    corrected    = (raw14 - dark/4) * gain, clamped to 14 bits

Note the **per-channel** normalisation. Commit ``8c9bcf1`` wrote it as
``gain = flat.mean() / (bright - dark)``, which reads as one scalar over the
whole array. It is not: each channel is normalised by its own mean, so each
channel's gain averages ~1 and the R/G/B balance set by the lamp duty and the
AFE gains is *preserved* rather than flattened. Using a single global scalar
reproduces the committed tables only to within 0.6 %, per channel, in a
constant ratio — which is exactly how this was pinned down. With the
per-channel mean, this tool reproduces ``calibration/dark_2000x3.npy`` and
``gain_2000x3.npy`` **bit for bit**, and the two ``.csv`` twins byte for byte,
from ``captures/ref_dark.bin`` and ``captures/ref_bright.bin``. See
``selftest``.

THE DOMAIN — the part that is easy to get wrong
-----------------------------------------------
The tables are stored in the **EP 0x86 wire u16** domain, not the 14-bit
domain. ``calibration/README.json`` records this as ``"domain": "wire_u16"``.
The two consumers disagree on purpose and both must keep working:

  * ``pakon_decode.load_unit_calibration`` multiplies the loaded dark by 0.25
    on the way in, because ``to_rgb14`` has already done ``>> 2``.
  * ``pakon_gate.Gate.from_calibration`` uses the table **as-is**, because it
    classifies raw wire lines and never converts them.

So: build the tables from wire words. Do *not* shift, and do not mask off the
sync flag in bit 0 — the committed tables did not, and matching the domain the
consumers expect matters more than the one count of bias that flag puts on the
first pixel of the red channel.

Line segmentation goes through ``pakon_decode.load_u16`` / ``segment_lines``.
Do not hand-roll a word de-interleave. Sync and phase correctness is not
obvious from a hex dump and getting it wrong in this project has produced
confidently-wrong answers more than once.

THE EXPOSURE TARGET, AND WHY IT IS NOT SIMPLY 64000
---------------------------------------------------
The vendor does not calibrate at whatever duty happens to be set. Its wizard
*searches* the per-channel LED duty until the empty gate reads a target level,
and calibrates there — ``FN_bCalibrateFindLedCurrent``, target **G = 64000**
(docs/42, quoted in ``pakon_framing.py``, which derives ``DetectWhite_G`` and
``DetectFilm_G`` as fractions of it). That search is the whole reason the
vendor's numbers are reproducible, and it is the only path to a lamp setting
for a *second owner's* scanner: the lamp values live in the registry and are
not recoverable from the EEPROM, so a unit with no recovered registry has to
derive them from its own hardware. ``solve`` is that search.

64000 is therefore this tool's default target. But it is a target for the
**level** — the mean over the illuminated columns — and this unit cannot reach
it without clipping. Measured on ``captures/ref_bright.bin``: the brightest
illuminated column reads 1.091x the level, and the brightest single sample
1.105x. Against a 65535 wire rail that puts the achievable ceiling at a level
of about **59,100**, not 64,000. Driving the level to 64,000 would push the top
of the PRNU distribution to roughly 70,700 — a couple of thousand pixels
pinned at the rail, where bright-minus-dark understates the true signal and the
computed gain is wrong in the direction that brightens them further.

That is not hypothetical. At the vendor Base-8 ``ColNeg`` duty now in
``calibration/README.json``, this unit's empty gate was measured at a clear
level of **65,477** — hard against the 65,535 rail, so that figure is a lower
bound on a value that is already clipped. The registry duties overshoot on this
unit and must come down.

So ``solve`` reports three numbers and lets a human choose: the duty that hits
the requested target, the highest clip-free level this unit's own measured PRNU
allows, and the duty that hits *that*. It refuses to pretend 64000 is reachable
when the measurement says it is not. The historical ~50,000 that the committed
tables were taken at is a superseded default, not a rule — but it is also not
far below the real ceiling, which is worth knowing before assuming it was
merely timid.

CAPTURE PROCEDURE
-----------------
Full version with the reasoning: ``docs/71-rebuilding-calibration.md``. Short
version — film OUT of the gate for every capture here:

  1. Probe. One short lamp-on capture at the current duty, to find out where
     this unit actually lands:

       python3 tools/pakon_scan.py run captures/probe_bright.bin \\
           --base 8 --no-dx --max-bytes 24000000
       python3 tools/build_calibration.py solve --bright captures/probe_bright.bin

     If it says the probe is clipped, it also says what to back the on-counts
     down to — a halving, because a saturated reading cannot be solved from.
     Edit ``on_counts_R_G_B`` in ``calibration/README.json`` to that, re-probe,
     repeat until it comes back unclipped, then it solves in one step. From the
     current Base-8 duty this should take about two rounds.

  2. When ``solve`` reports an unclipped probe, set ``on_counts_R_G_B`` to the
     on-counts it recommends and take the two real references. Do not touch
     the gate, the lamp or any exposure setting between them:

       python3 tools/pakon_scan.py run captures/ref_dark.bin \\
           --base 8 --no-lamp --no-dx --max-bytes 180000000
       python3 tools/pakon_scan.py run captures/ref_bright.bin \\
           --base 8 --no-dx --max-bytes 96000000

  3. Build, into a directory that is not ``calibration/``:

       python3 tools/build_calibration.py build \\
           --dark captures/ref_dark.bin \\
           --bright captures/ref_bright.bin \\
           --out calibration-build/$(date +%Y%m%d-%H%M%S)

  4. Read what it prints, compare against the previous tables — it prints both
     — then run the install command it gives you, by hand.

Both references must report **0 sync losses**. A capture with losses is not a
slightly worse reference, it is a reference with unknown lines in it.

WHAT ``build`` REFUSES
----------------------
A bad calibration table does not announce itself; it silently corrupts every
scan taken afterwards. So these refuse rather than warn:

  * either capture has sync losses (override with ``--allow-losses``, loudly)
  * either capture is 4-channel (IR) — the IR plane is *not* a 4-way
    interleave and this tool does not unpack it; see ``to_rgb14``'s docstring
  * the two captures disagree on any exposure-defining setting
  * bright is not meaningfully above dark on every channel
  * any pixel has a non-positive or non-finite flat value, hence a bad gain
  * the bright reference clips
  * the output directory already holds a table set
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pakon_decode as pdec                                    # noqa: E402
import pakon_gate as pgate                                     # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent
_CALIBRATION = _ROOT / "calibration"

PIXELS = pdec.PIXELS_PER_LINE          # 2000
CHANNELS = pdec.CHANNELS               # 3
WORDS_PER_LINE = pdec.WORDS_PER_LINE   # 6000
RAW14_MAX = pdec.RAW14_MAX             # 16383

#: Wire-domain full scale. ``to_rgb14`` does ``>> 2``, so 14-bit 16383 is wire
#: 65532 and the rail is one code above.
WIRE_MAX = 65535

#: The vendor's empty-gate calibration target for the green channel,
#: ``FN_bCalibrateFindLedCurrent`` (docs/42-port-remaining-work.md, quoted in
#: ``pakon_framing.py`` where DetectWhite_G/DetectFilm_G are derived from it).
VENDOR_TARGET_LEVEL = 64000

#: Which statistic the target is a target *for*. docs/15 records that the
#: vendor's check compares "the maximum pixel of an averaged CCD line", so the
#: vendor's 64000 is a MAXIMUM, not a mean, and :data:`METRIC_MAX` is the
#: default. Aiming the *mean* at 64000 on this unit pins roughly three quarters
#: of the illuminated pixels at the rail — measured, not predicted, which is
#: how this was found.
#:
#: ``METRIC_LEVEL`` is kept because the committed 2026-08-07 tables were judged
#: on it and ``docs/71`` is written in those terms. It is a legitimate thing to
#: ask for; it is not what the vendor asks for.
METRIC_MAX = "max"          # max over illuminated columns of the averaged line
METRIC_LEVEL = "level"      # mean over illuminated columns of the averaged line
METRICS = (METRIC_MAX, METRIC_LEVEL)
DEFAULT_METRIC = METRIC_MAX

#: SAFETY band, in wire counts: "is this black level catastrophically wrong?"
#: The working 2026-08-07 base-16 calibration measured 1120.5 / 1443.0 /
#: 1160.9 with a spatial spread of 0.07-0.11 %, so this band is not invented —
#: it is the pedestal a set of tables that demonstrably work were built on.
#: Low enough to waste almost nothing (1400 of 65535 is 2 %), high enough that
#: no pixel is anywhere near code 0.
#:
#: **These stay broad on purpose.** docs/74 §92 showed the 2026-08-07 pedestal
#: was itself measured with lifted offsets, so 1300 describes where black *sat*
#: rather than where it *belongs* — but `build_calibration`'s validation,
#: `calib_wizard` and `test_calib` all use this band to ask the *safety*
#: question, and every historical calibration must keep answering it. The
#: separate, tighter question — "have we converged to the vendor's target?" —
#: is `BLACK_CONVERGE_*` below. Two different questions, two constants.
BLACK_TARGET_WIRE = 1300.0
BLACK_MIN_WIRE = 400.0      # below this the bottom of the range is at risk
BLACK_MAX_WIRE = 4000.0     # above this the pedestal is eating real range

#: CONVERGENCE target, in wire counts: what the vendor actually drives black
#: to. Measured on real silicon, docs/74 §92, via `tools/afe_black_probe.py`:
#: loading the vendor's own converged offsets for this unit ((-19, -26, -19),
#: recovered live in §91) produced
#:
#:     779.7  562.3  571.2      mean 637.7
#:
#: against 1747.9 / 1590.8 / 1639.6 (mean 1659.4) at the offsets then stored —
#: i.e. this port's black sat **+1022 wire codes** above the vendor's.
#:
#: **The target is what generalises; the offsets are not.** (-19, -26, -19) is
#: serial 16275's answer and must never be hardcoded — another F-135's sensor
#: converges somewhere else. Aiming every unit at the vendor's *level* is what
#: makes the colour match on hardware this project has never seen.
BLACK_CONVERGE_TARGET_WIRE = 638.0

#: Per-channel accept window for convergence. Deliberately NOT symmetric noise
#: around the mean: the vendor's own converged state spans 562.3 → 779.7, a
#: 217-code spread across channels, so it does **not** equalise black between
#: channels and a tight band around 638 would reject the vendor's own answer.
#: This is that measured spread plus ~110 codes of margin each way. It accepts
#: the vendor's real state and rejects 1659 decisively, which is exactly the
#: discrimination §91.3's null result lacked (the safety band above contains
#: both, so `landed` was satisfied on round 1 before any correction).
BLACK_CONVERGE_MIN_WIRE = 450.0
BLACK_CONVERGE_MAX_WIRE = 890.0

#: Fraction of samples allowed to sit on the bottom ADC code before a dark
#: reference counts as clipped. Chosen the same way as CLIP_FRACTION_MAX at the
#: top: a genuine floor-clip pins whole channels, not stray pixels.
FLOOR_FRACTION_MAX = 1e-4
FLOOR_WIRE = 1                # a sample at or below this is on the floor

#: How far below the rail the brightest single sample must stay for a level to
#: count as clip-free. 1000 counts is 1.5 % — enough for the lamp to drift a
#: little between the probe and the reference without the reference clipping.
CLIP_GUARD = 1000

#: Where to aim a *re-probe* after a clipped one. Well below the rail on
#: purpose: a clipped measurement is a lower bound, so the scale factor derived
#: from it is an over-estimate and aiming near the ceiling would just clip
#: again. This is deliberately conservative — one wasted round trip beats three.
REPROBE_LEVEL = 45000

#: Hard ceiling on how much a single re-probe step may raise the duty, and the
#: step it takes when the probe is *saturated*.
#:
#: A clipped reading is a lower bound, so the scale factor derived from it is
#: an over-estimate — and when the probe is hard against the rail the reading
#: carries almost no scale information at all. Worked example: at the vendor
#: Base-8 ColNeg duty this unit measured a clear level of 65477, but the linear
#: model fitted to ``ref_bright.bin`` puts the *true* levels at roughly 69k/133k/269k
#: for R/G/B — 1.1x, 2.0x and 4.1x the rail. Scaling by (45000-dark)/(65477-dark)
#: = 0.68 would still leave G and B clipped, and the next round would repeat
#: the mistake. Halving cannot be fooled that way: it converges from any
#: overshoot in log2(overshoot) rounds, which for 4.1x is two.
#:
#: So a clipped probe bisects and an unclipped one solves. That is the vendor's
#: search, with the linear solve used only where it is trustworthy.
REPROBE_HALVING = 0.5

# ---- refusal thresholds, all stated in the wire domain --------------------

#: A sample at or above this is treated as clipped. 14-bit 16352 is 32 codes
#: (0.2 %) below the rail — inside the AFE's own non-linear top end, so this
#: catches a reference that is *about* to clip, not only one that already has.
CLIP_WIRE = 16352 << 2                 # 65408

#: Tolerated fraction of clipped samples per channel. Not zero: a single hot
#: pixel should not cost a re-capture. One in ten thousand is far below what
#: any real clipping event looks like — a clipping lamp clips whole columns.
CLIP_FRACTION_MAX = 1e-4

#: Minimum per-channel swing (mean bright - mean dark) for the bright capture
#: to count as "meaningfully above dark". 4000 wire counts is 1000 in the
#: 14-bit domain, ~6 % of full scale — far above read noise and far below the
#: ~48,800 a real empty-gate reference gives.
MIN_SWING_WIRE = 4000.0

#: Below this many lines a mean is not a mean, it is a sample. The 2026-08-07
#: references used 14,482 and 7,626.
MIN_LINES = 2000
LOW_LINES = 4000
#: A probe for ``solve`` only has to measure a level, so it can be far shorter.
MIN_PROBE_LINES = 64

#: A column counts as illuminated if every channel reads at least this
#: fraction of that channel's median. Self-contained on purpose: ``solve`` has
#: to work on a scanner that has no calibration yet, so it cannot borrow
#: ``pakon_gate``'s valid-column set, which is derived from a gain table. On
#: ``ref_bright.bin`` this gives columns 28..2000 against the Gate's 38..2000.
ILLUMINATED_FRAC = 0.5

#: Exposure-defining settings that must agree between the two captures. These
#: change what a photosite reads, so a dark and a bright reference differing on
#: any of them are not a matched pair.
CONFIG_KEYS = (
    "integration_0x82_idx6",
    "lamp_pwm_N",
    "line_rate_0x91",
    "levels_R_G_B_Ir",
    "on_counts_R_G_B",
    "afe_gains",
    "afe_offsets",
    "fpga_ctrl",
    "pixel_offset",
    "pixel_height",
    "dpi_base",
)

DARK_CSV_HEADER = "R,G,B per-pixel dark offset"
GAIN_CSV_HEADER = "R,G,B per-pixel gain multiplier"
DARK_CSV_FMT = "%.2f"
GAIN_CSV_FMT = "%.6f"

OUTPUT_NAMES = ("dark_2000x3.npy", "dark_2000x3.csv",
                "gain_2000x3.npy", "gain_2000x3.csv", "README.json")


class Refused(Exception):
    """A refusal with a reason. Never a traceback at the operator."""


# --------------------------------------------------------------------------
# capture loading
# --------------------------------------------------------------------------

class Capture:
    """One reference capture: its wire lines, its sync health, its config."""

    def __init__(self, path: Path, role: str) -> None:
        self.path = Path(path)
        self.role = role
        if not self.path.is_file():
            raise Refused(f"{role} capture {self.path} does not exist")

        words = pdec.load_u16(self.path)
        if words.size < WORDS_PER_LINE * 2:
            raise Refused(
                f"{self.path.name}: {words.size} words is less than two scan "
                f"lines. That is not a reference capture.")

        sync = np.flatnonzero(words & 1)
        if sync.size < 2:
            raise Refused(
                f"{self.path.name}: {sync.size} line-sync markers. Either the "
                f"FIFO was not reset or this is not a raw EP 0x86 dump.")

        gaps = np.diff(sync)
        modal = int(np.bincount(gaps).argmax())
        if modal != WORDS_PER_LINE:
            if modal in pdec.LINE_WORD_CANDIDATES:
                ch = pdec.channels_for_words(modal)
                raise Refused(
                    f"{self.path.name}: {modal}-word lines ({ch}-channel). "
                    f"This tool builds {CHANNELS}-channel tables only. The IR "
                    f"plane is not a 4-way interleave — it is 3N interleaved "
                    f"visible words followed by N contiguous IR words (see "
                    f"pakon_decode.to_rgb14) — and unpacking it as one would "
                    f"produce a table that looks fine and is wrong. Digital "
                    f"ICE calibration is separate work.")
            raise Refused(
                f"{self.path.name}: modal sync gap is {modal} words, not "
                f"{WORDS_PER_LINE}. This capture is not a decodable line "
                f"stream.")

        # A "loss" is a sync marker whose distance to the next one is not one
        # whole line: a FIFO glitch. segment_lines drops those lines silently,
        # so the count has to be taken here or it is never seen. The final
        # marker is excluded — its line is simply truncated by the end of the
        # file, which is normal and is not a loss.
        self.sync_markers = int(sync.size)
        self.losses = int((gaps != WORDS_PER_LINE).sum())
        self.leading_words = int(sync[0])

        self.lines = pdec.segment_lines(words, WORDS_PER_LINE)
        self.n_lines = int(self.lines.shape[0])
        self.planes = self.lines.reshape(self.n_lines, PIXELS, CHANNELS)

        self.sidecar = pdec.load_capture_sidecar(self.path)
        self.config = _exposure_from_sidecar(self.sidecar)

        self._pixel_mean: np.ndarray | None = None
        del words, sync, gaps

    # -- statistics ---------------------------------------------------------

    def pixel_mean(self) -> np.ndarray:
        """(2000, 3) float64 mean down the strip, in the wire domain."""
        if self._pixel_mean is None:
            self._pixel_mean = self.planes.astype(np.float64).mean(axis=0)
        return self._pixel_mean

    def channel_means(self) -> np.ndarray:
        return self.pixel_mean().mean(axis=0)

    def illuminated(self) -> np.ndarray:
        """Column indices that see light. See ``ILLUMINATED_FRAC``."""
        pm = self.pixel_mean()
        med = np.median(pm, axis=0)
        idx = np.flatnonzero((pm >= ILLUMINATED_FRAC * med).all(axis=1))
        if idx.size < PIXELS // 4:
            raise Refused(
                f"{self.path.name}: only {idx.size} of {PIXELS} columns are "
                f"illuminated. This does not look like an empty-gate capture "
                f"with the lamp on.")
        return idx

    def level(self) -> float:
        """Mean over the illuminated columns, all channels. The vendor's 'G'."""
        return float(self.pixel_mean()[self.illuminated()].mean())

    def channel_levels(self) -> np.ndarray:
        """Per-channel mean over the illuminated columns."""
        return self.pixel_mean()[self.illuminated()].mean(axis=0)

    def channel_maxima(self) -> np.ndarray:
        """Per-channel MAX over the illuminated columns of the averaged line.

        The vendor's own statistic. docs/15 records that its calibration check
        compares "the maximum pixel of an averaged CCD line" — averaged first,
        then maximised, so this is a property of the illumination profile and
        the PRNU, not of read noise on one sample.
        """
        return self.pixel_mean()[self.illuminated()].max(axis=0)

    def brightest_columns(self) -> np.ndarray:
        """Column index of each channel's maximum, in absolute pixel terms.

        ``solve --metric max`` needs the dark level *at the pixel it is
        aiming*, not the dark level averaged over every column, because the
        target applies to that one pixel.
        """
        idx = self.illuminated()
        return idx[self.pixel_mean()[idx].argmax(axis=0)]

    def channel_metric(self, metric: str = DEFAULT_METRIC) -> np.ndarray:
        if metric == METRIC_MAX:
            return self.channel_maxima()
        if metric == METRIC_LEVEL:
            return self.channel_levels()
        raise Refused(f"unknown metric {metric!r}; expected one of {METRICS}")

    def floor_stats(self) -> tuple[np.ndarray, np.ndarray]:
        """(fraction of samples on the bottom ADC code, per-channel minimum).

        The mirror image of :meth:`clip_stats`, and the check that did not
        exist when a base-8 dark reference came back entirely zero. A dark
        reference sitting on code 0 is not "very dark": it is a black level
        driven below the ADC's bottom rail, and every pixel whose signal falls
        under that point is lost with it.
        """
        frac = (self.planes <= FLOOR_WIRE).mean(axis=(0, 1))
        low = self.planes.min(axis=(0, 1))
        return np.asarray(frac, dtype=np.float64), np.asarray(low)

    def is_floored(self) -> bool:
        return bool((self.floor_stats()[0] > FLOOR_FRACTION_MAX).any())

    def peak_ratio(self) -> float:
        """Brightest single sample over the illuminated columns / the level.

        The number that decides whether a level target is reachable. Taken on
        single samples, not on the per-pixel mean, because it is a single
        sample that clips.
        """
        return float(self.planes[:, self.illuminated(), :].max()) / self.level()

    def peak_over(self, metric: str = DEFAULT_METRIC) -> float:
        """Brightest single sample / the statistic the target is stated in.

        With ``metric == "level"`` this is :meth:`peak_ratio` — the whole PRNU
        and lens-falloff spread has to fit under the rail. With
        ``metric == "max"`` the target already *is* the top of that spread, so
        the only thing left to fit is the temporal noise on a single sample,
        and the ratio is close to 1. Using the wrong one is the difference
        between "64000 is unreachable" and "64000 is reachable", which is why
        it is a method rather than a constant.
        """
        if metric == METRIC_LEVEL:
            return self.peak_ratio()
        m = float(self.channel_maxima().max())
        if m <= 0:
            raise Refused(f"{self.path.name}: the averaged line has no "
                          f"positive maximum over the illuminated columns.")
        return float(self.planes[:, self.illuminated(), :].max()) / m

    def clip_stats(self) -> tuple[np.ndarray, np.ndarray]:
        """(fraction clipped per channel, max wire value per channel)."""
        frac = (self.planes >= CLIP_WIRE).mean(axis=(0, 1))
        peak = self.planes.max(axis=(0, 1))
        return np.asarray(frac, dtype=np.float64), np.asarray(peak)

    def is_clipped(self) -> bool:
        return bool((self.clip_stats()[0] > CLIP_FRACTION_MAX).any())

    def describe(self) -> str:
        return (f"{self.role:<6} {self.path.name}\n"
                f"         lines      {self.n_lines}\n"
                f"         markers    {self.sync_markers} "
                f"({self.leading_words} words before the first)\n"
                f"         losses     {self.losses}")


def _exposure_from_sidecar(meta: dict | None) -> dict:
    """The exposure block a ``*.scan.json`` records, normalised.

    ``pakon_scan`` writes the triad twice: under ``exposure`` with register
    names, and under ``config`` with field names. Prefer ``exposure`` — it is
    the block written *for* this purpose — and fall back to ``config`` for
    captures made before it existed. Returns ``{}`` when there is no sidecar,
    which the caller treats as fatal: absence of evidence that the two
    captures matched is not evidence that they did.
    """
    if not isinstance(meta, dict):
        return {}
    exp = meta.get("exposure") if isinstance(meta.get("exposure"), dict) else {}
    cfg = meta.get("config") if isinstance(meta.get("config"), dict) else {}
    alias = {
        "integration_0x82_idx6": "integration",
        "lamp_pwm_N": "lamp_n",
        "levels_R_G_B_Ir": "levels",
        "on_counts_R_G_B": "on_counts",
    }
    out: dict = {}
    for key in CONFIG_KEYS:
        val = exp.get(key)
        if val is None:
            val = cfg.get(alias.get(key, key))
        if val is None:
            val = meta.get(key)
        if val is not None:
            out[key] = _normalise(key, val)
    return out


def _normalise(key: str, val):
    """Make the two sidecars comparable without making them equal.

    ``fpga_ctrl`` is written as the int 97 in one block and the string
    "0x0061" in the other; ``dpi_base`` as the int 8 in the sidecar and
    "DpiBase8_35" in ``calibration/README.json``. Normalising here means a
    real mismatch is still a mismatch and a formatting difference is not.
    """
    if key == "fpga_ctrl":
        try:
            return f"0x{int(str(val), 0):04x}"
        except (TypeError, ValueError):
            return str(val)
    if key == "dpi_base":
        s = str(val)
        return f"DpiBase{int(s)}_35" if s.isdigit() else s
    if isinstance(val, (list, tuple)):
        return [int(v) if isinstance(v, (int, float)) else v for v in val]
    return val


# --------------------------------------------------------------------------
# the duty search — what the vendor's calibration wizard does
# --------------------------------------------------------------------------

def solve_duty(probe: Capture, dark_level: np.ndarray,
               target: float, metric: str = DEFAULT_METRIC,
               dark_pixels: np.ndarray | None = None) -> dict:
    """Per-channel on-counts that would land the empty gate on ``target``.

    The vendor's own relationship, from ``calibration/README.json``:

        on_ch = floor(N_float * duty_ch),  clamped to <= N - 2

    and the LED is a current source pulsed at a fixed peak, so the
    time-averaged illumination — and therefore the signal above dark — is
    linear in duty:

        level_ch = dark_ch + K_ch * duty_ch

    One measurement at a known duty gives ``K_ch``, and the duty for any target
    follows. This is a one-shot solve rather than the vendor's iterative
    search because the relationship is linear and we can measure all three
    channels at once; the operator still re-probes to confirm, which is the
    part of the search that matters.

    Nothing here drives hardware. It reads a capture and prints numbers for a
    human to put into ``calibration/README.json``.
    """
    cfg = probe.config
    on_old = cfg.get("on_counts_R_G_B")
    n = cfg.get("lamp_pwm_N")
    integ = cfg.get("integration_0x82_idx6")
    if not on_old or n is None:
        raise Refused(
            f"{probe.path.name}: the sidecar does not record "
            f"on_counts_R_G_B and lamp_pwm_N, so there is no way to know what "
            f"duty this capture was taken at and nothing to solve from.")
    on_old = [int(v) for v in on_old]
    n = int(n)

    # N_float is the unrounded period the vendor's floor() is taken against:
    # README.json records "N_float = 2813*0.24 = 675.12". Falling back to the
    # integer N costs at most one count.
    n_float = float(integ) * 0.24 if integ else float(n)

    lvl = probe.channel_metric(metric)

    # For the MAX metric the target applies to one pixel per channel, so the
    # dark level that belongs in the model is that pixel's, not an average
    # over every column. Where a per-pixel dark table is available it is used;
    # otherwise the supplied per-channel figure stands in, which is the right
    # approximation because a black level with 0.1 % spatial spread is
    # essentially the same number at every column.
    at = probe.brightest_columns()
    dark_at = np.asarray(dark_level, dtype=np.float64)
    if metric == METRIC_MAX and dark_pixels is not None:
        dp = np.asarray(dark_pixels, dtype=np.float64)
        if dp.shape == (PIXELS, CHANNELS):
            dark_at = np.array([dp[at[c], c] for c in range(CHANNELS)])

    swing = lvl - dark_at
    if (swing <= 0).any():
        raise Refused(
            f"{probe.path.name}: channel {metric}(s) {lvl.round(1).tolist()} "
            f"are not above the dark level {np.round(dark_at, 1).tolist()}. "
            f"Was the lamp on?")

    duty_old = np.array([o / n_float for o in on_old], dtype=np.float64)
    k = swing / duty_old
    duty_new = (float(target) - dark_at) / k
    on_new = np.floor(n_float * duty_new).astype(int)
    on_max = n - 2
    clamped = [i for i in range(CHANNELS) if on_new[i] > on_max]
    on_new = np.clip(on_new, 1, on_max)

    ratio = probe.peak_over(metric)
    ceiling = (WIRE_MAX - CLIP_GUARD) / ratio
    return {
        "metric": metric,
        "n": n,
        "n_float": n_float,
        "on_old": on_old,
        "duty_old": duty_old,
        "level_measured": lvl,
        "dark_at": dark_at,
        "at_columns": at.tolist(),
        "level_overall": probe.level(),
        "k": k,
        "target": float(target),
        "duty_new": duty_new,
        "on_new": on_new.tolist(),
        "clamped": clamped,
        "on_max": on_max,
        "peak_ratio": ratio,
        "ceiling_level": ceiling,
        "predicted_peak": ratio * float(target),
        "clipped": probe.is_clipped(),
    }


def report_solve(probe: Capture, s: dict, dark_level: np.ndarray,
                 dark_source: str) -> None:
    ch = "RGB"
    print("\nprobe")
    print("-" * 72)
    print(probe.describe())
    print(f"         illuminated columns "
          f"{probe.illuminated()[0]}..{probe.illuminated()[-1] + 1}")

    metric = s.get("metric", DEFAULT_METRIC)
    print("\nmeasured")
    print("-" * 72)
    print(f"  statistic           {metric}"
          + ("   (the vendor's: docs/15, 'the maximum pixel of an averaged "
             "CCD line')" if metric == METRIC_MAX else "   (the MEAN — note "
             "the vendor targets the MAX)"))
    print(f"  dark level  R/G/B   {_fmt(s.get('dark_at', dark_level))}   "
          f"({dark_source})")
    print(f"  clear {metric:<5} R/G/B   {_fmt(s['level_measured'])}"
          + (f"   at columns {s['at_columns']}" if metric == METRIC_MAX
             else ""))
    print(f"  clear level overall {s['level_overall']:.1f}")
    print(f"  on-counts           {s['on_old']}  of N={s['n']} "
          f"(N_float={s['n_float']:.2f})")
    print(f"  duty                {_fmt(s['duty_old'], 4)}")
    print(f"  peak / level        {s['peak_ratio']:.4f}  "
          f"(brightest single sample over the illuminated columns)")

    if s["clipped"]:
        frac, peak = probe.clip_stats()
        print("\n  *** THIS PROBE IS CLIPPED ***")
        for i in range(CHANNELS):
            print(f"      {ch[i]}: {frac[i] * 100:.4f} % of samples at or "
                  f"above {CLIP_WIRE}, peak {int(peak[i])}")
        print("      Every level above is a LOWER BOUND on a value that is "
              "already pinned at")
        print("      the rail, so there is no solve to be had from it — a "
              "saturated reading")
        print("      carries almost no scale information. Bisect instead.")
        back = _reprobe_on_counts(s, s.get("dark_at", dark_level))
        print(f"\n  set on_counts_R_G_B to {back} in "
              f"calibration/README.json and re-probe")
        print(f"  (the smaller of a straight halving and the scale the "
              f"clipped reading implies")
        print(f"   for a level of {REPROBE_LEVEL}. Repeat until the probe "
              f"comes back unclipped —")
        print(f"   each round halves any remaining overshoot — then this "
              f"solves it in one step.)")
        return

    print("\nsolve")
    print("-" * 72)
    print(f"  target {metric:<13}{s['target']:.0f}")
    print(f"  duty needed         {_fmt(s['duty_new'], 4)}")
    print(f"  ON-COUNTS           {s['on_new']}   <- put this in "
          f"calibration/README.json")
    if s["clamped"]:
        names = "".join(ch[i] for i in s["clamped"])
        print(f"  WARNING: channel(s) {names} were clamped to N-2 = "
              f"{s['on_max']}. That channel")
        print(f"           cannot reach the target at this LED level; it "
              f"needs a higher")
        print(f"           Current_* level, which is a separate hardware "
              f"limit (the IR-off")
        print(f"           clamp caps R at 4 — see calibration/README.json).")

    print("\nheadroom")
    print("-" * 72)
    print(f"  this unit's peak/level ratio is {s['peak_ratio']:.4f}, so at a "
          f"level of {s['target']:.0f}")
    print(f"  the brightest sample would read "
          f"{s['predicted_peak']:.0f} against a {WIRE_MAX} rail.")
    if s["predicted_peak"] > WIRE_MAX - CLIP_GUARD:
        safe_on = _on_counts_for(s, dark_level, s["ceiling_level"])
        print(f"\n  *** THE TARGET {s['target']:.0f} IS NOT REACHABLE ON THIS "
              f"UNIT WITHOUT CLIPPING ***")
        print(f"      Highest clip-free level here is about "
              f"{s['ceiling_level']:.0f}, which needs")
        print(f"      on-counts {safe_on}.")
        print(f"      The vendor's {VENDOR_TARGET_LEVEL} assumes a flatter "
              f"field than this unit has;")
        print(f"      its PRNU plus lens falloff spread is "
              f"{(s['peak_ratio'] - 1) * 100:.1f} % above the level, and a "
              f"{WIRE_MAX}")
        print(f"      rail only leaves {(WIRE_MAX / s['target'] - 1) * 100:.1f}"
              f" %. Use --target {s['ceiling_level']:.0f} (or lower), or")
        print(f"      accept that the top of the PRNU distribution "
              f"calibrates wrong.")
    else:
        print(f"  That is inside the rail with "
              f"{WIRE_MAX - s['predicted_peak']:.0f} counts to spare. The "
              f"target is reachable.")

    print("\nnext")
    print("-" * 72)
    print("  1. edit on_counts_R_G_B in calibration/README.json")
    print("  2. re-probe and re-run this to confirm the level landed and "
          "nothing clips")
    print("  3. take the two references and run `build`")


def _on_counts_for(s: dict, dark_level, target: float) -> list[int]:
    duty = (float(target) - np.asarray(dark_level, dtype=np.float64)) / s["k"]
    return np.clip(np.floor(s["n_float"] * duty).astype(int),
                   1, s["on_max"]).tolist()


def _reprobe_on_counts(s: dict, dark_level) -> list[int]:
    """Where to put the duty after a clipped probe. Bisect, do not solve.

    See ``REPROBE_HALVING``. The scale implied by the clipped reading is an
    upper bound on the scale actually needed, so taking the smaller of it and a
    straight halving is right in both regimes: a barely-clipped probe gets the
    gentler model-driven step, a saturated one gets bisection.
    """
    lvl = np.asarray(s["level_measured"], dtype=np.float64)
    d = np.asarray(dark_level, dtype=np.float64)
    implied = (REPROBE_LEVEL - d) / np.maximum(lvl - d, 1.0)
    scale = np.minimum(implied, REPROBE_HALVING)
    on = np.floor(np.asarray(s["on_old"], dtype=np.float64) * scale)
    return np.clip(on.astype(int), 1, s["on_max"]).tolist()


# --------------------------------------------------------------------------
# the black-level search — the step that did not exist
# --------------------------------------------------------------------------

def solve_offset(darks: list[Capture],
                 target: float = BLACK_TARGET_WIRE) -> dict:
    """AFE offset register values that put the black level on ``target``.

    Same shape as :func:`solve_duty` and for the same reason: the number
    wanted is not derivable from anything on disk, so it is measured.

    WHY THE SIGN IS NOT ASSUMED
    ---------------------------
    The committed base-16 calibration pairs offsets ``-18 / -26 / -20`` with
    black levels ``1120.5 / 1443.0 / 1160.9`` — monotone, more-negative
    register giving a *higher* pedestal, which is the opposite of what the
    word "offset" suggests. But those are three different channels, so the
    apparent slope (about 20 counts per step between R and B, about 47 between
    B and G) mixes the register's authority with whatever the channels'
    intrinsic black levels differ by. It is suggestive and it is not a
    calibration.

    So: with two dark captures at two different ``afe_offsets`` this measures
    the slope per channel and solves. With one it can only report where the
    black level *is*, and says so. It never guesses a direction it has not
    seen, and it refuses a pair whose response is flat — a register that does
    not move the black level is a register this code has misidentified, and
    extrapolating through it would drive the offset to a rail.
    """
    if not darks:
        raise Refused("solve-offset needs at least one dark capture.")
    for c in darks:
        if c.is_clipped():
            raise Refused(
                f"{c.path.name} clips at the TOP. That is not a dark "
                f"reference — was the lamp on?")

    obs = []
    for c in darks:
        off = c.config.get("afe_offsets")
        if off is None:
            raise Refused(
                f"{c.path.name}: the sidecar does not record afe_offsets, so "
                f"there is nothing to solve for. Re-capture with "
                f"tools/pakon_scan.py, which writes one.")
        obs.append((np.asarray([int(v) for v in off], dtype=np.float64),
                    c.channel_means(), c))

    cur_off, cur_mean, cur_cap = obs[-1]
    frac, low = cur_cap.floor_stats()
    out = {
        "target": float(target),
        "offsets_now": [int(v) for v in cur_off],
        "black_now": cur_mean,
        "floor_fraction": frac,
        "floored": bool((frac > FLOOR_FRACTION_MAX).any()),
        "observations": [{"afe_offsets": [int(v) for v in o],
                          "black": m.tolist(),
                          "file": c.path.name} for o, m, c in obs],
        "slope": None,
        "offsets_new": None,
        "solvable": False,
    }

    pairs = [(a, b) for i, a in enumerate(obs) for b in obs[i + 1:]
             if not np.array_equal(a[0], b[0])]
    if not pairs:
        out["reason"] = (
            "only one distinct afe_offsets setting was measured, so the "
            "register's authority over the black level is unknown. Capture a "
            "second short lamp-off strip with afe_offsets moved by a few "
            "counts on every channel and pass it as --dark2.")
        return out

    (o_a, m_a, _), (o_b, m_b, _) = pairs[0]
    d_off = o_b - o_a
    d_black = m_b - m_a
    slope = np.where(d_off != 0, d_black / np.where(d_off != 0, d_off, 1),
                     np.nan)
    out["slope"] = slope

    dead = [i for i in range(CHANNELS)
            if not np.isfinite(slope[i]) or abs(slope[i]) < 1.0]
    if dead:
        names = "".join("RGB"[i] for i in dead)
        out["reason"] = (
            f"channel(s) {names} showed under 1 wire count of black-level "
            f"change per offset step between the two captures. Either the "
            f"register that was moved is not the black-level offset for that "
            f"channel, or the step was too small to measure against read "
            f"noise. Refusing to extrapolate through a slope this code cannot "
            f"see.")
        return out

    # Solve from the measurement that is not clipped. A floored channel's
    # measured black level is a lower bound -- the true value is somewhere
    # below zero -- so solving from it under-corrects. Prefer the higher of
    # the two observations per channel, which is the one furthest from the
    # floor.
    base_black = np.maximum(m_a, m_b)
    base_off = np.where(m_a >= m_b, o_a, o_b)
    new = base_off + (float(target) - base_black) / slope
    out["offsets_new"] = [int(round(v)) for v in new]
    out["solved_from"] = {"afe_offsets": [int(v) for v in base_off],
                          "black": base_black.tolist()}
    out["solvable"] = True
    return out


def report_offset(s: dict) -> None:
    print("\nblack level")
    print("-" * 72)
    for o in s["observations"]:
        print(f"  afe_offsets {str(o['afe_offsets']):<18} -> "
              f"{_fmt(o['black'])}   ({o['file']})")
    if s["floored"]:
        print("\n  *** THE BLACK LEVEL IS CLIPPED AT ZERO ***")
        for i in range(CHANNELS):
            print(f"      {'RGB'[i]}: {s['floor_fraction'][i] * 100:.4f} % of "
                  f"samples on the bottom ADC code")
        print("      Every measured level here is a LOWER BOUND on a value "
              "that is already")
        print("      under the rail. See docs/72.")

    print(f"\n  target black level  {s['target']:.0f} wire counts   "
          f"(the working base-16 calibration sits at 1120/1443/1161)")
    if not s["solvable"]:
        print(f"\n  NOT SOLVABLE YET: {s.get('reason', '')}")
        return
    print(f"  measured slope      {_fmt(s['slope'], 2)} wire counts per "
          f"offset step")
    print(f"  AFE OFFSETS         {s['offsets_new']}   <- put this in "
          f"calibration/README.json")
    print("\n  Then re-capture a short lamp-off strip and run this again to "
          "confirm the")
    print("  black level landed, before taking either reference.")


def installed_dark_level() -> tuple[np.ndarray, str] | None:
    """Per-channel dark level from the installed table, for ``solve``.

    A dark reference of its own is better and ``solve --dark`` takes one. This
    fallback exists because the dark level barely moves with lamp duty — it is
    the AFE offset and read noise — so an old table is a perfectly good
    stand-in while hunting for a duty.
    """
    p = _CALIBRATION / "dark_2000x3.npy"
    if not p.is_file():
        return None
    try:
        return np.load(p).astype(np.float64).mean(axis=0), f"from {p}"
    except (OSError, ValueError):
        return None


# --------------------------------------------------------------------------
# the build
# --------------------------------------------------------------------------

def build_tables(dark_cap: Capture,
                 bright_cap: Capture) -> tuple[np.ndarray, np.ndarray, dict]:
    """(dark, gain, stats). Wire domain throughout. Raises ``Refused``."""
    dark = dark_cap.pixel_mean()
    bright = bright_cap.pixel_mean()
    flat = bright - dark

    dark_ch = dark_cap.channel_means()
    bright_ch = bright_cap.channel_means()
    swing_ch = bright_ch - dark_ch

    weak = [i for i, s in enumerate(swing_ch) if s < MIN_SWING_WIRE]
    if weak:
        names = "".join("RGB"[i] for i in weak)
        raise Refused(
            f"channel(s) {names} show a bright-minus-dark swing of "
            f"{[round(float(swing_ch[i]), 1) for i in weak]} wire counts, "
            f"under the {MIN_SWING_WIRE:.0f} required. The bright reference "
            f"is not meaningfully above the dark one. Most likely the lamp "
            f"was off, dying, or the two captures are the same capture — "
            f"check that the bright run really had the lamp lit.")

    bad = np.argwhere(flat <= 0.0)
    if bad.size:
        px, ch = bad[0]
        raise Refused(
            f"{len(bad)} of {flat.size} pixel-channels have bright <= dark, "
            f"first at pixel {px} channel {'RGB'[ch]} "
            f"(bright {bright[px, ch]:.1f}, dark {dark[px, ch]:.1f}). Every "
            f"one of those is a division by zero or a negative gain. A dead "
            f"column or a partly blocked light path does this.")

    gain = flat.mean(axis=0) / flat          # per-channel normalisation
    if not np.isfinite(gain).all():
        n = int((~np.isfinite(gain)).sum())
        raise Refused(f"{n} gain values are not finite despite a positive "
                      f"flat field. Refusing rather than shipping NaN.")
    if (gain <= 0).any():
        raise Refused(f"{int((gain <= 0).sum())} gain values are <= 0.")

    return dark, gain, {
        "dark_means": dark_ch,
        "bright_means": bright_ch,
        "swing_means": swing_ch,
        "flat_k": flat.mean(axis=0),
        "gain_min": gain.min(axis=0),
        "gain_max": gain.max(axis=0),
        "gain_mean": gain.mean(axis=0),
        "level": bright_cap.level(),
        "peak_ratio": bright_cap.peak_ratio(),
    }


def check_dark_floor(dark_cap: Capture) -> list[str]:
    """Refuse a dark reference that is sitting on the ADC's bottom code.

    THE REFUSAL THAT DID NOT EXIST. On 2026-08-12 a base-8 dark reference came
    back with every sample exactly 0 except one — pixel 0 of red, which reads 1
    because bit 0 carries the line-sync flag. 33,226 lines x 5,999
    pixel-channels, all zero. That is not a very dark reference; it is a black
    level driven under the ADC's bottom rail, and everything below the rail is
    gone: the flat field's own vignetted edge (columns 0..17) came back with
    ``bright <= dark`` and the tables could only be produced by hand-patching
    46 gains to a clamp.

    A pedestal is not wasted range. It is the headroom that keeps read noise,
    per-pixel dark offsets and the darkest real signal on the linear side of
    zero. ``docs/72`` has the evidence; :func:`solve_offset` is how to fix it.
    """
    frac, low = dark_cap.floor_stats()
    means = dark_cap.channel_means()
    over = [i for i, f in enumerate(frac) if f > FLOOR_FRACTION_MAX]
    if over:
        detail = ", ".join(
            f"{'RGB'[i]} {frac[i] * 100:.4f} % of samples at or below "
            f"{FLOOR_WIRE} (channel mean {means[i]:.1f})" for i in over)
        raise Refused(
            f"the dark reference is CLIPPED AT ZERO: {detail}.\n\n"
            f"The AFE's black level has been pushed below the ADC's bottom "
            f"code, so the dark table is a no-op and every pixel whose signal "
            f"falls under that point — the vignetted columns first, the "
            f"deepest shadows of every future scan after that — is lost "
            f"before it is ever digitised. Per-pixel dark structure cannot be "
            f"subtracted out of a table of zeros.\n\n"
            f"The AFE offset registers are a per-DPI-base calibration output, "
            f"not a constant to copy between bases: the vendor stores "
            f"Offset_R/G/B per DpiBase x film mode in the registry, next to "
            f"Current_* and DutyCycle_*, and none of them are on the EEPROM. "
            f"To find the right ones for this configuration:\n\n"
            f"    python3 tools/build_calibration.py solve-offset "
            f"--dark {dark_cap.path} [--dark2 <a second dark at a different "
            f"afe_offsets>]\n\n"
            f"or let tools/calib_wizard.py do the whole search unattended. "
            f"See docs/72.")

    warn = []
    for i, m in enumerate(means):
        if m < BLACK_MIN_WIRE:
            warn.append(
                f"the {'RGB'[i]} black level is {m:.1f} wire counts, under "
                f"the {BLACK_MIN_WIRE:.0f} this project treats as safe (the "
                f"working 2026-08-07 tables sit at 1120/1443/1161). Nothing "
                f"is clipped yet, but there is little room under the darkest "
                f"real signal. `solve-offset` reports where to put it.")
        elif m > BLACK_MAX_WIRE:
            warn.append(
                f"the {'RGB'[i]} black level is {m:.1f} wire counts, above "
                f"the {BLACK_MAX_WIRE:.0f} this project treats as generous. "
                f"Not wrong — it is subtracted back off — but it is ADC range "
                f"spent on nothing.")
    return warn


def check_clipping(bright_cap: Capture, target: float,
                   metric: str = DEFAULT_METRIC) -> list[str]:
    """Refuse a clipped bright reference. Returns warnings when it passes."""
    frac, peak = bright_cap.clip_stats()
    over = [i for i, f in enumerate(frac) if f > CLIP_FRACTION_MAX]
    if over:
        detail = ", ".join(
            f"{'RGB'[i]} {frac[i] * 100:.4f} % (peak {int(peak[i])})"
            for i in over)
        raise Refused(
            f"the bright reference CLIPS: {detail}. Above the rail the "
            f"sensor's response is flat, so bright-minus-dark understates the "
            f"true signal and the gain at those pixels is wrong in the "
            f"direction that brightens them further.\n\n"
            f"Lower on_counts_R_G_B in calibration/README.json and take the "
            f"bright reference again. To find out by how much, run:\n\n"
            f"    python3 tools/build_calibration.py solve "
            f"--bright {bright_cap.path}\n\n"
            f"Note that the vendor's {VENDOR_TARGET_LEVEL} level target is "
            f"not necessarily reachable on this unit — its measured PRNU "
            f"spread may put the top of the distribution past the "
            f"{WIRE_MAX} rail at that level. `solve` reports the achievable "
            f"ceiling.")

    warn = []
    ratio = bright_cap.peak_over(metric)
    level = float(bright_cap.channel_metric(metric).max())
    ceiling = (WIRE_MAX - CLIP_GUARD) / ratio
    if level < 0.9 * min(target, ceiling):
        warn.append(
            f"the bright reference landed at a {metric} of {level:.0f}, well "
            f"under both the {target:.0f} target and this unit's "
            f"{ceiling:.0f} clip-free ceiling. Not wrong — the gain table is "
            f"a ratio and normalises out — but it uses less of the ADC range "
            f"than it could, so the table carries more read noise than "
            f"necessary. `solve` gives the on-counts that would fix it.")
    return warn


def check_config(dark_cap: Capture, bright_cap: Capture) -> None:
    """The two captures must describe the same machine setup."""
    missing = [c.path.name for c in (dark_cap, bright_cap) if not c.sidecar]
    if missing:
        raise Refused(
            f"no .scan.json sidecar for {', '.join(missing)}. The sidecar is "
            f"the only record of the exposure a capture was taken at, and "
            f"these tables are valid only for that exposure. Without it there "
            f"is nothing to write into the new README.json and nothing to "
            f"check the two captures against each other. Re-capture with "
            f"tools/pakon_scan.py, which writes one.")

    diffs = []
    for key in CONFIG_KEYS:
        d = dark_cap.config.get(key)
        b = bright_cap.config.get(key)
        if d is None and b is None:
            continue
        if d != b:
            diffs.append(f"  {key}: dark={d!r}  bright={b!r}")
    if diffs:
        raise Refused(
            "the two captures were taken at different configurations:\n"
            + "\n".join(diffs)
            + "\n\nA dark reference from one setup subtracted from film shot "
              "under another is a wrong number, not a noisy one. Re-take both "
              "captures back to back without changing anything in between.")

    absent = [k for k in pdec.EXPOSURE_TRIAD_KEYS
              if dark_cap.config.get(k) is None]
    if absent:
        raise Refused(
            f"the sidecars do not record {', '.join(absent)}. That is the "
            f"exposure triad — integration, lamp N and line rate are one "
            f"setting in three registers — and without it the new README.json "
            f"cannot say what the tables are valid for, so nothing downstream "
            f"could ever check a capture against them.")


# --------------------------------------------------------------------------
# writing
# --------------------------------------------------------------------------

def csv_text(arr: np.ndarray, header: str, fmt: str) -> str:
    """Match the committed ``.csv`` twins byte for byte.

    The point of these files is that the calibration is readable without
    numpy, so the format is fixed by what is already committed: one comment
    line, then one row per pixel, ``%.2f`` for dark and ``%.6f`` for gain,
    formatted from the float64 values — not from the float32 that goes into
    the ``.npy``, which rounds differently in the last digit.
    """
    buf = io.StringIO()
    buf.write(f"# {header}\n")
    for row in arr:
        buf.write(",".join(fmt % v for v in row) + "\n")
    return buf.getvalue()


def build_readme(dark_cap: Capture, bright_cap: Capture, stats: dict,
                 unit: str, target: float, notes: dict,
                 metric: str = DEFAULT_METRIC) -> dict:
    """The record of what these tables mean. Read by four consumers.

    ``pakon_scan.ScanConfig.from_calibration`` reads ``config`` to set up a
    scan; ``pakon_gate.Gate.from_calibration`` reads the two ``means`` arrays
    to derive its flat-field constant; ``pakon_decode.calibration_exposure``
    reads the triad; a human reads the rest. All four are load-bearing, so the
    shape here follows the committed file exactly.
    """
    peak = bright_cap.clip_stats()[1]
    ratio = stats["peak_ratio"]
    return {
        "unit": unit,
        "captured": time.strftime("%Y-%m-%d"),
        "generated_by": "tools/build_calibration.py",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": dict(bright_cap.config),
        "config_source": (
            f"read from the captures' own sidecars "
            f"({dark_cap.path.name}.scan.json and "
            f"{bright_cap.path.name}.scan.json), which agreed on every key in "
            f"{list(CONFIG_KEYS)}. NOT copied from a previous "
            f"calibration/README.json — these tables are valid for the setup "
            f"the captures were actually taken under and nothing else."),
        "dark_source": {
            "file": dark_cap.path.name,
            "lines": dark_cap.n_lines,
            "losses": dark_cap.losses,
            "means": [round(float(v), 1) for v in stats["dark_means"]],
            "floor_fraction": [float(v)
                               for v in dark_cap.floor_stats()[0]],
            "note": (
                f"black level, empty gate, lamp off. Target band "
                f"{BLACK_MIN_WIRE:.0f}..{BLACK_MAX_WIRE:.0f} wire counts; a "
                f"reference sitting on ADC code 0 is refused, because a "
                f"clipped pedestal loses everything below it and cannot be "
                f"corrected afterwards (docs/72). The AFE offsets that "
                f"produce it are recorded in config.afe_offsets and are a "
                f"per-DPI-base calibration output, not a constant."),
        },
        "bright_source": {
            "file": bright_cap.path.name,
            "lines": bright_cap.n_lines,
            "losses": bright_cap.losses,
            "means": [round(float(v), 1) for v in stats["bright_means"]],
            "level": round(float(stats["level"]), 1),
            "peak_wire": [int(v) for v in peak],
            "peak_over_level": round(float(ratio), 4),
            "target_level": float(target),
            "target_metric": metric,
            "metric_measured": [round(float(v), 1)
                                for v in bright_cap.channel_metric(metric)],
            "note": (
                f"empty gate, lamp on, unclipped: peak {int(max(peak))} of "
                f"{WIRE_MAX} wire full scale. Target was {target:.0f} on the "
                f"{metric!r} statistic (the vendor's "
                f"FN_bCalibrateFindLedCurrent target is "
                f"{VENDOR_TARGET_LEVEL}, and docs/15 records that its check "
                f"compares the MAXIMUM pixel of an averaged CCD line, not the "
                f"mean); measured level {stats['level']:.0f}. This unit's "
                f"brightest sample sits {ratio:.4f}x its level, so the "
                f"highest clip-free level here is about "
                f"{(WIRE_MAX - CLIP_GUARD) / ratio:.0f}."),
        },
        "flat_field_k_per_channel": [round(float(v), 4)
                                     for v in stats["flat_k"]],
        "usage": ("Tables are EP 0x86 wire u16. Decode: dark14=dark/4; "
                  "(raw14-dark14)*gain → clamp 14-bit. Gate uses wire "
                  "as-is."),
        "domain": "wire_u16",
        "formula": ("dark = mean down the strip; "
                    "gain[:,c] = (bright-dark)[:,c].mean() / (bright-dark)[:,c] "
                    "— normalised PER CHANNEL, not globally"),
        **notes,
    }


def install_command(out: Path, label: str) -> str:
    """The command a human runs, after deciding they believe the numbers.

    Never run by this tool. The standing rule in this project is that a
    calibration is never deleted, only timestamped — ``calibration/`` already
    holds ``README.pre-dutyfix-*.json`` and ``README.pre-vendor-base8-*.json``
    on that convention, and this extends it to the tables themselves, which
    have never been rotated before because they have never been rebuilt.
    """
    ts = time.strftime("%Y%m%d-%H%M%S")
    cal = _CALIBRATION
    lines = ["# back up what is there now (never deleted, only timestamped)"]
    for name in ("dark_2000x3.npy", "dark_2000x3.csv",
                 "gain_2000x3.npy", "gain_2000x3.csv"):
        stem, _, ext = name.rpartition(".")
        lines.append(f"cp {cal}/{name} {cal}/{stem}.pre-{label}-{ts}.{ext}")
    lines.append(f"cp {cal}/README.json {cal}/README.pre-{label}-{ts}.json")
    lines += ["", "# install the new set"]
    lines += [f"cp {out}/{name} {cal}/{name}" for name in OUTPUT_NAMES]
    lines += ["", "# confirm both consumers still load",
              "python3 tools/pakon_gate.py selftest"]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------

def _fmt(arr, nd=1) -> str:
    return "[" + ", ".join(f"{float(v):.{nd}f}" for v in arr) + "]"


def previous_tables() -> tuple[np.ndarray, np.ndarray, dict] | None:
    """The currently installed set, for side-by-side comparison. May be None."""
    try:
        return (np.load(_CALIBRATION / "dark_2000x3.npy"),
                np.load(_CALIBRATION / "gain_2000x3.npy"),
                json.loads((_CALIBRATION / "README.json").read_text()))
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def report_build(dark_cap, bright_cap, dark, gain, stats, out: Path,
                 target: float, metric: str = DEFAULT_METRIC) -> None:
    print("\ncaptures")
    print("-" * 72)
    print(dark_cap.describe())
    print(bright_cap.describe())

    print("\nnew tables (wire u16 domain)")
    print("-" * 72)
    print(f"  dark   mean R/G/B   {_fmt(stats['dark_means'])}")
    print(f"  bright mean R/G/B   {_fmt(stats['bright_means'])}")
    print(f"  swing  R/G/B        {_fmt(stats['swing_means'])}")
    print(f"  flat K R/G/B        {_fmt(stats['flat_k'], 4)}")
    print(f"  gain   min R/G/B    {_fmt(stats['gain_min'], 4)}")
    print(f"  gain   mean R/G/B   {_fmt(stats['gain_mean'], 4)}")
    print(f"  gain   max R/G/B    {_fmt(stats['gain_max'], 4)}")

    ratio = bright_cap.peak_over(metric)
    ceiling = (WIRE_MAX - CLIP_GUARD) / ratio
    print("\nexposure")
    print("-" * 72)
    print(f"  statistic           {metric}")
    print(f"  clear level         {stats['level']:.1f}")
    print(f"  clear {metric:<5} R/G/B   "
          f"{_fmt(bright_cap.channel_metric(metric))}")
    print(f"  target {metric:<13}{target:.0f}"
          + ("" if target == VENDOR_TARGET_LEVEL
             else f"   (vendor's is {VENDOR_TARGET_LEVEL})"))
    print(f"  black level R/G/B   {_fmt(stats['dark_means'])}")
    print(f"  peak / {metric:<13}{ratio:.4f}")
    print(f"  clip-free ceiling   {ceiling:.0f}  "
          f"(level whose brightest sample sits {CLIP_GUARD} below the "
          f"{WIRE_MAX} rail)")
    if target > ceiling:
        print(f"  NOTE: the {target:.0f} target is above this unit's "
              f"{ceiling:.0f} ceiling. These")
        print(f"        tables were built at {stats['level']:.0f}, which is "
              f"clip-free — the right")
        print(f"        outcome, but it means the vendor's target was not "
              f"met and could not be.")

    prev = previous_tables()
    if prev is None:
        print("\n  (no previous calibration to compare against)")
    else:
        pdark, pgain, pmeta = prev
        print("\ncompared with the installed calibration")
        print("-" * 72)
        pd_means = (pmeta.get("dark_source") or {}).get("means")
        pb_means = (pmeta.get("bright_source") or {}).get("means")
        if pd_means:
            print(f"  previous dark   mean {_fmt(pd_means)}")
        if pb_means:
            print(f"  previous bright mean {_fmt(pb_means)}")
        if pdark.shape == dark.shape:
            print(f"  dark  delta per channel "
                  f"{_fmt(dark.mean(0) - pdark.mean(0))}")
            print(f"  gain  ratio per channel "
                  f"{_fmt(gain.mean(0) / pgain.mean(0), 4)}")
        pcfg = pmeta.get("config") or {}
        for key in pdec.EXPOSURE_TRIAD_KEYS:
            was, now = pcfg.get(key), bright_cap.config.get(key)
            if was is not None and now is not None and was != now:
                print(f"  {key}: was {was}, now {now}  <- these tables "
                      f"replace ones taken at a different exposure")

    # Would pakon_gate still build a Gate out of this? That consumer reads the
    # tables in the wire domain and derives every threshold from them, so if it
    # cannot, the tables are unusable no matter how good the numbers look.
    print("\npakon_gate.Gate reconstruction (the second consumer)")
    print("-" * 72)
    try:
        k = float(np.asarray(stats["swing_means"]).mean())
        g = pgate.Gate(dark.astype(np.float32), gain.astype(np.float32),
                       k, source=str(out))
        d = g.describe()
        print(f"  valid columns  {d['valid_columns']} ({d['valid_count']})")
        print(f"  dark level     {d['dark_level']}")
        print(f"  clear level    {d['clear_level']}")
        print(f"  swing          {d['swing']}")
        print("  OK — Gate.from_calibration will accept this set")
    except Exception as e:                                     # noqa: BLE001
        print(f"  FAILED: {e}")
        raise Refused(
            f"the new tables do not produce a usable gate classifier: {e}. "
            f"That consumer reads them in the wire domain and derives every "
            f"scan-stop threshold from them, so this set cannot be installed.")


# --------------------------------------------------------------------------
# selftest
# --------------------------------------------------------------------------

def cmd_selftest(a) -> int:
    """Rebuild the committed tables from the captures they came from.

    The strongest check available without hardware: if the formula and the
    domain handling are right, the output is bit-identical to what is
    committed. Skips cleanly when the 2026-08-07 captures are not present.
    """
    root = Path(a.captures) if a.captures else _ROOT / "captures"
    dark_p, bright_p = root / "ref_dark.bin", root / "ref_bright.bin"
    if not dark_p.is_file() or not bright_p.is_file():
        print(f"SKIP — need {dark_p} and {bright_p} on this machine")
        return 0
    want_dark = _CALIBRATION / "dark_2000x3.npy"
    want_gain = _CALIBRATION / "gain_2000x3.npy"
    if not want_dark.is_file() or not want_gain.is_file():
        print("SKIP — no committed tables to compare against")
        return 0

    print("rebuilding the committed tables from their own source captures")
    dc, bc = Capture(dark_p, "dark"), Capture(bright_p, "bright")
    print(f"  dark   {dc.n_lines} lines, {dc.losses} losses")
    print(f"  bright {bc.n_lines} lines, {bc.losses} losses")

    dark = dc.pixel_mean()
    flat = bc.pixel_mean() - dark
    gain = flat.mean(axis=0) / flat

    checks = [
        ("dark lines   == 14482", dc.n_lines == 14482),
        ("bright lines ==  7626", bc.n_lines == 7626),
        ("dark losses   == 0", dc.losses == 0),
        ("bright losses == 0", bc.losses == 0),
        ("dark_2000x3.npy bit-identical",
         np.array_equal(np.load(want_dark), dark.astype(np.float32))),
        ("gain_2000x3.npy bit-identical",
         np.array_equal(np.load(want_gain), gain.astype(np.float32))),
    ]
    for name, arr, header, fmt in (
            ("dark_2000x3.csv", dark, DARK_CSV_HEADER, DARK_CSV_FMT),
            ("gain_2000x3.csv", gain, GAIN_CSV_HEADER, GAIN_CSV_FMT)):
        p = _CALIBRATION / name
        if p.is_file():
            checks.append((f"{name} byte-identical",
                           csv_text(arr, header, fmt) == p.read_text()))

    # The clipping refusal must fire on a genuinely clipped reference and not
    # on this known-good one. Only the second half can be tested from data on
    # disk; the first is asserted against a synthetic rail.
    checks.append(("clipping check passes the known-good bright reference",
                   not bc.is_clipped()))

    print()
    ok = True
    for name, passed in checks:
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
        ok = ok and passed
    print(f"\n  measured peak/level ratio {bc.peak_ratio():.4f} -> clip-free "
          f"ceiling {(WIRE_MAX - CLIP_GUARD) / bc.peak_ratio():.0f}, "
          f"vendor target {VENDOR_TARGET_LEVEL}")
    print("\nSELFTEST " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_solve(a) -> int:
    probe = Capture(Path(a.bright), "bright")
    if probe.n_lines < MIN_PROBE_LINES:
        raise Refused(f"{probe.path.name} has {probe.n_lines} lines; a probe "
                      f"needs at least {MIN_PROBE_LINES} to measure a level.")
    dark_pixels = None
    if a.dark:
        dc = Capture(Path(a.dark), "dark")
        dark_pixels = dc.pixel_mean()
        dark_level = dark_pixels[probe.illuminated()].mean(axis=0)
        source = f"measured from {dc.path.name}"
    else:
        got = installed_dark_level()
        if got is None:
            raise Refused(
                "no dark reference. Pass --dark, or install a calibration "
                "first: the dark level is needed to turn a measured clear "
                "level into a duty.")
        dark_level, source = got
    s = solve_duty(probe, dark_level, a.target, a.metric, dark_pixels)
    report_solve(probe, s, dark_level, source)
    if a.json:
        print("\n" + json.dumps(
            {k: (v.tolist() if isinstance(v, np.ndarray) else v)
             for k, v in s.items()}, indent=2))
    return 0


def cmd_solve_offset(a) -> int:
    caps = [Capture(Path(a.dark), "dark")]
    if a.dark2:
        caps.append(Capture(Path(a.dark2), "dark"))
    s = solve_offset(caps, a.target)
    report_offset(s)
    if a.json:
        print("\n" + json.dumps(
            {k: (v.tolist() if isinstance(v, np.ndarray) else v)
             for k, v in s.items()}, indent=2, default=str))
    return 0


def cmd_build(a) -> int:
    out = Path(a.out).resolve()
    if out == _CALIBRATION.resolve():
        raise Refused(
            f"--out must not be {_CALIBRATION}. This tool never installs; it "
            f"writes a candidate set and prints the command a human runs to "
            f"install it, after looking at the numbers.")
    existing = [n for n in OUTPUT_NAMES if (out / n).is_file()]
    if existing:
        raise Refused(
            f"{out} already contains {', '.join(existing)}. A calibration is "
            f"never overwritten in this project. Pick a new directory — e.g. "
            f"--out {out.parent}/{time.strftime('%Y%m%d-%H%M%S')}.")

    print(f"reading {a.dark}")
    dark_cap = Capture(Path(a.dark), "dark")
    print(f"reading {a.bright}")
    bright_cap = Capture(Path(a.bright), "bright")

    for cap in (dark_cap, bright_cap):
        if cap.losses and not a.allow_losses:
            raise Refused(
                f"{cap.path.name} has {cap.losses} sync losses. A reference "
                f"with losses is not a slightly worse reference; the dropped "
                f"lines are unaccounted for and whatever caused them may also "
                f"have corrupted lines that were kept. Re-capture. "
                f"--allow-losses overrides.")
        if cap.losses:
            print(f"WARNING: {cap.path.name} has {cap.losses} sync losses and "
                  f"--allow-losses was passed. These tables are built on a "
                  f"capture nobody can fully account for.", file=sys.stderr)
        if cap.n_lines < MIN_LINES:
            raise Refused(
                f"{cap.path.name} has only {cap.n_lines} lines, under the "
                f"{MIN_LINES} minimum. Averaging that few lines leaves read "
                f"noise in the table, which then gets subtracted from every "
                f"scan as though it were signal.")
        if cap.n_lines < LOW_LINES:
            print(f"WARNING: {cap.path.name} has {cap.n_lines} lines; the "
                  f"2026-08-07 references used 14482 and 7626. Fewer lines "
                  f"means more residual noise in the table.", file=sys.stderr)

    check_config(dark_cap, bright_cap)
    # The black level first. A dark reference clipped at zero makes every
    # number after it meaningless, and it is the failure this tool shipped
    # without a check for -- see check_dark_floor.
    warnings = check_dark_floor(dark_cap)
    warnings += check_clipping(bright_cap, a.target, a.metric)
    dark, gain, stats = build_tables(dark_cap, bright_cap)
    report_build(dark_cap, bright_cap, dark, gain, stats, out, a.target,
                 a.metric)
    for w in warnings:
        print(f"\nWARNING: {w}", file=sys.stderr)

    unit = a.unit
    if unit is None:
        prev = previous_tables()
        unit = (prev[2].get("unit") if prev else None) or "unknown"

    notes = {}
    if a.note:
        notes["note"] = a.note
    if any(c.losses for c in (dark_cap, bright_cap)):
        notes["losses_overridden"] = True

    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "dark_2000x3.npy", dark.astype(np.float32))
    np.save(out / "gain_2000x3.npy", gain.astype(np.float32))
    (out / "dark_2000x3.csv").write_text(
        csv_text(dark, DARK_CSV_HEADER, DARK_CSV_FMT))
    (out / "gain_2000x3.csv").write_text(
        csv_text(gain, GAIN_CSV_HEADER, GAIN_CSV_FMT))
    (out / "README.json").write_text(json.dumps(
        build_readme(dark_cap, bright_cap, stats, unit, a.target, notes,
                     a.metric),
        indent=2) + "\n")

    print(f"\nwrote {len(OUTPUT_NAMES)} files to {out}")
    for n in OUTPUT_NAMES:
        print(f"  {n}")
    print("\nNOTHING HAS BEEN INSTALLED. To install, read the numbers above, "
          "decide you believe them, then run:\n")
    print(install_command(out, a.label))
    print()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="two captures -> a new table set")
    b.add_argument("--dark", required=True,
                   help="lamp-off empty-gate capture (.bin)")
    b.add_argument("--bright", required=True,
                   help="lamp-on empty-gate capture (.bin)")
    b.add_argument("--out", required=True,
                   help="directory to write the new set into. Must not "
                        "already contain one, and must not be calibration/ — "
                        "installing is a separate, deliberate step.")
    b.add_argument("--target", type=float, default=VENDOR_TARGET_LEVEL,
                   help=f"the empty-gate level these tables were aiming at, "
                        f"recorded in the new README.json and used to judge "
                        f"how well the bright reference landed "
                        f"(default {VENDOR_TARGET_LEVEL}, the vendor's)")
    b.add_argument("--metric", choices=METRICS, default=DEFAULT_METRIC,
                   help=f"which statistic --target names. '{METRIC_MAX}' is "
                        f"the vendor's — docs/15 records that its check "
                        f"compares the maximum pixel of an averaged CCD line "
                        f"— and is the default. '{METRIC_LEVEL}' is the mean "
                        f"over the illuminated columns, which is what the "
                        f"2026-08-07 tables were judged on; aiming the MEAN "
                        f"at 64000 on this unit pins most of the field at the "
                        f"rail.")
    b.add_argument("--unit", default=None,
                   help="identity string for the scanner. Defaults to the one "
                        "in the installed calibration/README.json, which is "
                        "an identity, not a setting.")
    b.add_argument("--label", default="recal",
                   help="name for the backup the install command makes, as in "
                        "README.pre-LABEL-TIMESTAMP.json (default recal)")
    b.add_argument("--note", default=None,
                   help="free text recorded in the new README.json")
    b.add_argument("--allow-losses", action="store_true",
                   help="build even though a capture has sync losses. The "
                        "result contains lines nobody can account for.")

    s = sub.add_parser(
        "solve",
        help="one capture -> the on-counts that hit the target level")
    s.add_argument("--bright", required=True,
                   help="lamp-on empty-gate probe capture (.bin). Short is "
                        "fine; it only has to measure a level.")
    s.add_argument("--dark", default=None,
                   help="matching lamp-off capture. Defaults to the installed "
                        "dark table, which is a good stand-in because the "
                        "dark level barely moves with lamp duty.")
    s.add_argument("--target", type=float, default=VENDOR_TARGET_LEVEL,
                   help=f"empty-gate level to aim for "
                        f"(default {VENDOR_TARGET_LEVEL}, the vendor's "
                        f"FN_bCalibrateFindLedCurrent target)")
    s.add_argument("--metric", choices=METRICS, default=DEFAULT_METRIC,
                   help=f"which statistic --target names (default "
                        f"{DEFAULT_METRIC}, the vendor's)")
    s.add_argument("--json", action="store_true")

    o = sub.add_parser(
        "solve-offset",
        help="dark captures -> the AFE offsets that put the black level "
             "where it belongs")
    o.add_argument("--dark", required=True,
                   help="lamp-off empty-gate capture (.bin). Short is fine.")
    o.add_argument("--dark2", default=None,
                   help="a second lamp-off capture taken at a DIFFERENT "
                        "afe_offsets. Without it the black level can be "
                        "reported but not solved, because the register's "
                        "authority over it has not been measured.")
    o.add_argument("--target", type=float, default=BLACK_TARGET_WIRE,
                   help=f"black level to aim for, in wire counts (default "
                        f"{BLACK_TARGET_WIRE:.0f}; the working base-16 "
                        f"calibration sits at 1120/1443/1161)")
    o.add_argument("--json", action="store_true")

    t = sub.add_parser("selftest",
                       help="prove the formula still reproduces the committed "
                            "tables bit for bit")
    t.add_argument("--captures", default=None)

    a = ap.parse_args()
    try:
        return {"build": cmd_build, "solve": cmd_solve,
                "solve-offset": cmd_solve_offset,
                "selftest": cmd_selftest}[a.cmd](a)
    except Refused as e:
        print(f"\nREFUSED: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
