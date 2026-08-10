#!/usr/bin/env python3
"""Drive a real scan: firmware -> lamp -> acquire -> transport -> capture.

This is the only code in the project that makes the owner's film move, so it
is written to stop rather than to finish.

    python3 tools/pakon_scan.py status          # what the machine says, no writes
    python3 tools/pakon_scan.py stop            # panic button: motor + lamp off
    python3 tools/pakon_scan.py run out.bin     # a scan, with every guard armed
    python3 tools/pakon_scan.py run --dry-run   # print the sequence, send nothing
    python3 tools/pakon_scan.py sensors         # DX photodiodes + film sense, no writes


WHAT THIS IS GUARDING AGAINST
=============================
An overnight roll scan ran seven minutes. The lamp died about two minutes in
and the transport kept running for five more with the sensor reading darkness.
Nothing was watching the lamp, and the roll-end detector tested one boundary
("bright enough to be a clear gate"), so darkness read as film present.

Six independent things now have to fail before that can happen again:

  0. THE MACHINE'S OWN FILM SENSORS. Every DX packet reports whether film is
     at the entry and exit sensors, and ``hardware_cb = 0xC0000000`` has been
     in every sidecar this project ever wrote while nothing read it. They are
     now the *primary* end-of-roll signal: sustained clear after film has been
     seen ends the roll, and film still present vetoes an optical roll-end —
     which is what stops a scan ending on the leader. See ``FilmSense``. They
     never veto the DARK stop.

  1. THREE-STATE CLASSIFICATION (``pakon_gate``). Every window is CLEAR, FILM
     or DARK, from levels derived out of ``calibration/``. DARK stops the motor
     within ~0.5 s. Regression-tested against ``captures/roll.bin``, which is
     the real lamp failure: it is flagged DARK 29.9 % in, where the lamp died.

  2. LAMP HEALTH POLLED DURING THE SCAN. Light-board ``0x83`` status and
     ``0x88`` temperatures, once a second, aborting on fault bits 5 and 6
     (docs/40 s12). The vendor does *not* do this — ``LAMP_WARNING`` and
     ``LAMP_ERROR`` are consumed but never produced anywhere in TLB.dll
     (docs/53 s4.5) — so this is new work, not parity. If the poll itself stops
     working we abort too, because "nothing was watching the lamp" is the exact
     failure being fixed.

  3. A HARD TIME LIMIT, ALWAYS. It stops the motor regardless of what any
     detector believes. A 36-exposure roll runs about four minutes, so the
     default is six and the ceiling is fifteen. There is no "unlimited".

  4. STOP ON EVERY EXIT PATH. ``safe_stop`` runs from ``finally``, from the
     signal handlers, from the parent when the child dies, and from the child
     when the parent dies. See THE DYING-PROCESS PROBLEM below.

  5. CANCEL THAT CANCELS. Closing the control pipe, a SIGTERM, or
     ``pakon_scan.py stop`` each halt the transport inside a second. The gap
     list found an export Cancel that was enabled and did nothing; this one is
     tested by killing the process mid-run.


THE DYING-PROCESS PROBLEM
=========================
If a process holding the USB interface is SIGKILLed, no Python runs, so no
``finally`` fires and no stop packet is sent — while the film keeps moving.
Hoping this does not happen is not a design, so both directions are handled:

  * The scan always runs in its own process. The application backend holds no
    USB handle at all, so the interface is free the instant the scan process
    dies for any reason.

  * PARENT DIES -> the child notices. The parent holds the write end of the
    child's stdin. When the parent exits, however violently, that pipe reaches
    EOF; the child's watchdog thread is blocked on exactly that read, and an
    EOF is treated as a cancel. This works for SIGKILL, for a crash, and for
    the user force-quitting the app.

  * CHILD DIES -> the parent notices. If the scan process exits without having
    reported a confirmed stop, the parent opens the device itself and sends
    motor-stop and lamp-off. The kernel released the interface when the child
    died, so this can actually get through.

  * BOTH DIE -> the next process to start cleans up. The child writes a marker
    file while a scan is in flight and removes it on a confirmed stop. A stale
    marker means a scan was interrupted without a stop being confirmed, and
    ``check_stale`` will send one. ``pakon_app`` calls this at startup.

  * And the child holds its own deadline, so an orphan still stops on time.


THE THREE NUMBERS THAT ARE ONE SETTING
======================================
FPGA integration 4093, lamp PWM N 982, light-board 0x91 speed 60. They are a
single exposure setting spread across three registers: N = trunc(4093 x 0.24)
and the 0x91 rate follows from the same exposure. Change one and all three must
be recomputed, and the committed dark/gain tables stop being valid. So they are
read from ``calibration/README.json`` — the record of what the tables were
captured at — and are not exposed as settings.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent
sys.path.insert(0, str(_TOOLS))

import pakon_commands as pc          # noqa: E402
import pakon_gate as gate            # noqa: E402
import dx_decode as dxd              # noqa: E402
import dx_read as dxr                # noqa: E402

VID, PID = 0x0F05, 0xF135
EP_CMD_OUT, EP_CMD_IN, EP_IMAGE = 0x01, 0x81, 0x86

LOCK_FILE = _TOOLS / "WRITES_LOCKED"
MARKER = Path.home() / ".pakon-scan-in-flight.json"
DEFAULT_OUT_DIR = _ROOT / "captures"

# --------------------------------------------------------------------------
# transport speed
# --------------------------------------------------------------------------

#: ``MotorSpeedPlus`` per DPI base, read out of the recovered Windows hive at
#: ``HKLM\SOFTWARE\Pakon\TLB\Scan\DpiBase<N>_35`` — see
#: ``research/windows-registry/pakon_registry_full.json``.
#:
#: NOTE THE DIRECTION. Base 16 is the *slowest*, not the fastest: it is the
#: highest resolution, so the film must crawl. ``docs/43-capture-architecture.md``
#: lines 24-26 and ``docs/37`` line 122 both have this table scrambled — 43 has
#: it exactly inverted. The hive is the ground truth and this is it:
#:
#:      DpiBase4_35   MotorSpeedPlus 25802   MotorSpeedPlus_Ir 19335
#:      DpiBase8_35   MotorSpeedPlus 11467   MotorSpeedPlus_Ir  7580
#:      DpiBase16_35  MotorSpeedPlus  5917   MotorSpeedPlus_Ir  4850
#:
#: Running base 16 at 25802 would drag the film past the sensor 4.4x faster
#: than anything on this machine is calibrated for.
MOTOR_SPEED = {4: 25802, 8: 11467, 16: 5917}
MOTOR_SPEED_IR = {4: 19335, 8: 7580, 16: 4850}

#: Only base 16 decodes: ``pakon_decode.WORDS_PER_LINE`` is 6000, and the
#: committed calibration was taken at ``DpiBase16_35``.
DECODABLE_BASES = (16,)

# --------------------------------------------------------------------------
# limits — all of them backstops, none of them adjustable to "off"
# --------------------------------------------------------------------------

# The vendor bounds a run by *distance*, not by elapsed time, and guards it
# with a no-progress watchdog. See docs/55-scan-timeouts.md for the addresses.
# TLB.dll validates iMaxFilmLength_mm to 24..6400 mm (0x1004174c / 0x10041751)
# and PSI supplies these two:
NORMAL_ROLL_MM = 1670            # NormalRollMaxFilmLength_mm, a 36-exposure roll
LONG_ROLL_MM = 3340              # LongRollMaxFilmLength_mm, exactly 2x
MAX_FILM_LENGTH_MM = 6400        # the API's own ceiling, 0x10041751

#: ``MotorSpeedPlus / 1000`` is millimetres per second. Reconciled from the
#: /1000 in FN_bBeforeScan (0x1002e687), the GUI's "tenths of mm/s, 10..355"
#: (docs/51 s220) against register 0xA5's legal 1000..32766 (docs/12 s476), and
#: the 1:2:4 DpiBase ratio. Strongly supported, not directly measured.
MM_PER_S_PER_SPEED_UNIT = 1.0 / 1000.0

#: Leader, trailer and start/stop transients on top of the nominal roll length.
SCAN_MARGIN = 1.25
#: The vendor's own LongRoll/Normal ratio. Past this, more film has gone by than
#: the vendor's long-roll mode itself permits.
SCAN_CEILING_FACTOR = LONG_ROLL_MM / NORMAL_ROLL_MM      # 2.0

MIN_MAX_SECONDS = 5.0


def speed_mm_per_s(speed: int) -> float:
    """Transport speed in mm/s for a ``MotorSpeedPlus`` register value."""
    return max(1, int(speed)) * MM_PER_S_PER_SPEED_UNIT


def scan_seconds_for(speed: int, film_mm: float = NORMAL_ROLL_MM) -> float:
    """How long ``film_mm`` of film takes to pass at ``speed``."""
    return float(film_mm) / speed_mm_per_s(speed)


def scan_limits_for(speed: int,
                    film_mm: float = NORMAL_ROLL_MM) -> tuple[float, float]:
    """``(default_cap, hard_ceiling)`` in seconds for one transport speed.

    A single constant cannot be right for three speeds that differ by 4.4x, so
    both numbers are derived from the distance the vendor bounds, not guessed.
    For a 36-exposure roll this gives 353/565 s at base 16, 182/291 s at base 8
    and 81/129 s at base 4.
    """
    expected = scan_seconds_for(speed, film_mm)
    return expected * SCAN_MARGIN, expected * SCAN_CEILING_FACTOR


#: Module-level fallbacks are the *slowest* speed, so they stay valid whatever
#: the run is configured for. Prefer ``scan_limits_for(cfg.speed)``.
DEFAULT_MAX_SECONDS, HARD_MAX_SECONDS = scan_limits_for(MOTOR_SPEED[16])
#: Absolute backstop at any speed: the API's 6400 mm at the slowest transport.
ABSOLUTE_MAX_SECONDS = scan_seconds_for(MOTOR_SPEED[16], MAX_FILM_LENGTH_MM)

#: Disk backstop. 11.6 MB/s x 360 s is 4.2 GB, so 8 GB cannot be reached by a
#: scan that is behaving.
DEFAULT_MAX_BYTES = 8 << 30

CHUNK = 256 * 1024               # the read size the lossless 60 s run used
#: ``ScanPacketReadyTimeOut``, the vendor's own value. Note that for the vendor
#: a timeout here is *not* fatal: 0x1002fe00 re-reads status 0x2b and downgrades
#: WAIT_TIMEOUT to WAIT_OBJECT_0 rather than failing. Ours must not abort on it
#: either -- the stall watchdog below is what ends a dead scan.
READ_TIMEOUT_MS = 3000
LAMP_POLL_S = 1.0
LAMP_POLL_FAIL_LIMIT = 5         # consecutive failures before we call it blind
LAMP_WARMUP_S = 5.0              # WaitForLamp default, hive-confirmed "5.000000"

#: How long the capture may see no image bytes before it gives up.
#:
#: Sized from ``i_uiNoFilmTimeOut``: seconds, validated 10..300 at
#: 0x10041485/0x1004148a, shipped at 120. It is proven to be seconds because it
#: is added straight to a ``time()`` return at 0x1002f9b7 and 0x1003115d.
#:
#: Note what that value means for the vendor, because it is not what this
#: constant means for us. The vendor's deadline is built once at scan start
#: (0x1002f9c9) and never re-armed, and it is only consulted once the *optical*
#: test has already said the frame is blank (0x10030447). So for the vendor it
#: is a **floor** on scan duration -- the scan may not end on the leader -- not
#: a watchdog on byte flow. The vendor's own byte-starvation timeout is
#: ScanPacketReadyTimeOut (3 s) and timing out there is explicitly *not* fatal
#: (0x1002fe00 downgrades WAIT_TIMEOUT to WAIT_OBJECT_0).
#:
#: We use 120 s as a stall limit because it is the vendor's own floor: below it
#: the vendor would not even entertain the idea that the film has ended. The
#: previous value here was 3.0 s, which is 40x more trigger-happy than that and
#: is the likeliest cause of a roll being cut short. docs/55 s5.2a, s7.3.
STALL_LIMIT_S = 120.0
STALL_LIMIT_MIN_S = 10.0         # i_uiNoFilmTimeOut's validated band, 0x10041485
STALL_LIMIT_MAX_S = 300.0        # 0x1004148a

#: docs/40 s12: 0x83 bit 5 and bit 6 are real faults; the vendor aborts
#: ``FN_bLampTemperatureStable`` on bit 5. Bit 1 is transient and self-clearing,
#: bit 3 means the temperature readings are valid.
LAMP_STATUS_FAULT_MASK = 0x60
LAMP_STATUS_BIT_TEMP_VALID = 0x08

#: Light-board temperatures, raw x 0.0625 degC (docs/53 s4.5, docs/40 s5).
#: ``0x88`` returns [TempLB u16][TempMB u16].
REG_LIGHT_TEMPS = 0x88
TEMP_UNITS_PER_C = 16.0
#: Plausibility band. Outside it the sensor, not the lamp, is what is wrong, so
#: it is reported and not treated as a lamp fault on its own.
TEMP_PLAUSIBLE_C = (0.0, 90.0)
#: docs/40 s10 measured this board holding 40.06-40.31 degC against a 40.0
#: setpoint. Fault if the lamp board leaves a generous band around that.
LAMP_TEMP_FAULT_C = (25.0, 60.0)


# --------------------------------------------------------------------------
# simulation — so the safety machinery can be tested without the owner's film
# --------------------------------------------------------------------------
#
# Set ``PAKON_SCAN_SIMULATE`` to a capture file and the whole module drives a
# fake scanner that acknowledges every packet and replays that capture over
# EP 0x86. It is not a toy: it exercises the real capture loop, the real
# classifier, the real stop paths and the real process supervision, and it
# records every packet it was sent to ``PAKON_SCAN_TRACE``.
#
# That trace is what makes "kill the process mid-scan and verify the motor
# stops" an actual test rather than a hope — including the case where the scan
# process is SIGKILLed and the *parent* has to issue the stop, because the
# parent inherits these variables and its recovery lands in the same trace.
ENV_SIMULATE = "PAKON_SCAN_SIMULATE"
ENV_TRACE = "PAKON_SCAN_TRACE"
ENV_SIM_RATE = "PAKON_SCAN_SIM_RATE"
#: Number of simulated DX packets after which the fake board stops reporting
#: film at its sensors — i.e. the strip leaves the transport. Lets the
#: film-sense end-of-roll path be run end to end without a scanner.
ENV_SIM_FILM_OUT = "PAKON_SCAN_SIM_FILM_OUT"
#: Comma-separated packet prefixes, as hex, that the simulated board answers
#: with a NAK — status byte 1, "no acknowledgement, board absent" — instead of
#: an acceptance. The board still *acts* on them, because that is the case
#: worth testing: the command arrived and the reply did not.
#:
#: There is no other way to reach the lost-acknowledgement paths without a
#: scanner, and those are the paths that decide whether the transport can be
#: left running with the marker deleted. ``04 03 44 00 a1`` is motor forward.
ENV_SIM_NAK = "PAKON_SCAN_SIM_NAK"


class FakeDev:
    """A scanner that answers packets and replays a capture over EP 0x86."""

    def __init__(self, source: str | Path, trace: str | Path | None = None,
                 rate: float = 11.6e6) -> None:
        self.path = Path(source)
        self.trace = Path(trace) if trace else None
        self.rate = float(rate)
        self.fh = self.path.open("rb") if self.path.is_file() else None
        self.opened = time.time()
        self.delivered = 0
        self.streaming = False           # only after acquire + motor forward
        self.acquire = False
        self.motor = False
        # A DX board that emits one half-frame code every 20 gate reads, so the
        # scan loop's DX poll is exercised for real. Product 96 specifier 1 is
        # "KODAK GOLD 400 GEN 9" in the vendor's own product table -- the roll
        # this is going to be validated against.
        self.dx_gate_reads = 0
        self.dx_frame = 0
        self.dx_ready = False
        # Film-sense state, so the film-position path can be exercised. The
        # board reports film at both sensors while the strip is in the
        # transport; ``film_out_after`` is how many DX packets that lasts.
        self.dx_status = dxd.DXSTAT_FILM_SENSE
        _out = os.environ.get(ENV_SIM_FILM_OUT)
        self.film_out_after: int | None = int(_out) if _out else None
        self.dx_packets = 0
        # Illuminator state, set by command 0x98.
        self.dx_illum = pc.DX_ILLUM_BOTH
        self.dx_illum_armed = True
        self.dx_illum_writes = 0
        # Packets this board acts on but refuses to acknowledge. See
        # ENV_SIM_NAK.
        self.nak = tuple(
            bytes.fromhex(p.strip().replace(" ", ""))
            for p in (os.environ.get(ENV_SIM_NAK) or "").split(",")
            if p.strip())

    def _dx_packet(self) -> bytes:
        """One 0x90 response: a code word and two perforations.

        Deliberately a *mixed* packet. A single-record packet cannot tell a
        correct variable-stride walk from the old fixed 5-byte one, and that is
        the bug this simulator now has to be able to catch.
        """
        import dx_decode as _dxd
        self.dx_packets += 1
        if (self.film_out_after is not None
                and self.dx_packets > self.film_out_after):
            self.dx_status = 0x00
        line = 1000 + 100 * self.dx_frame
        b0, b1, b2 = _dxd.encode_dx_full(96, 1, self.dx_frame)
        self.dx_frame += 1
        recs = [
            _dxd.encode_record(_dxd.EventType.DX_CODE_FULL, bytes([b0, b1, b2]),
                               flags=self.dx_status),
            _dxd.encode_record(_dxd.EventType.PERF_LEADING,
                               bytes([((line + 10) >> 8) & 0xFF, (line + 10) & 0xFF])),
            _dxd.encode_record(_dxd.EventType.PERF_TRAILING,
                               bytes([((line + 20) >> 8) & 0xFF, (line + 20) & 0xFF])),
        ]
        return _dxd.encode_packet(line, recs, pc.DX_RESPONSE_LEN)

    def _note(self, kind: str, pkt: bytes) -> None:
        if not self.trace:
            return
        try:
            with self.trace.open("a") as fh:
                fh.write(json.dumps({"pid": os.getpid(), "at": time.time(),
                                     "kind": kind, "pkt": pkt.hex(" ")}) + "\n")
        except OSError:
            pass

    def set_configuration(self):
        return None

    def clear_halt(self, _ep):
        return None

    def write(self, _ep, pkt, _timeout=0):
        pkt = bytes(pkt)
        self._pending = pkt
        kind = "other"
        if pkt[:1] == b"\x04" and len(pkt) >= 5:
            if pkt[2] == pc.AD_MOTOR and pkt[4] == pc.CMD_MOTOR_STOP:
                kind, self.motor = "MOTOR_STOP", False
            elif pkt[2] == pc.AD_MOTOR and pkt[4] in (pc.CMD_MOTOR_FORWARD,
                                                      pc.CMD_MOTOR_REVERSE):
                kind, self.motor = "MOTOR_RUN", True
        elif pkt[:5] == b"\x02\x04\x40\x01\x80":
            kind = "LAMP_ON" if pkt[5] else "LAMP_OFF"
        elif pkt[:5] == bytes([0x02, 0x04, pc.AD_LIGHT, 0x01, pc.REG_DX_ILLUM]):
            # Command 0x98. Handler 0x0DC6 sets the outputs from the mask AND
            # clears the arm bit unconditionally, so the simulated board does
            # both -- including disarming on a mask of zero.
            self.dx_illum = pkt[5]
            self.dx_illum_armed = False
            self.dx_illum_writes += 1
            kind = "DX_ILLUM_ON" if pkt[5] else "DX_ILLUM_OFF"
        elif pkt[:5] == bytes([0x04, 0x03, pc.AD_LIGHT, 0x00,
                               pc.CMD_LIGHT_DX_LAMP_RESTART]):
            self.dx_illum = pc.DX_ILLUM_BOTH
            self.dx_illum_armed = True          # 0x0882 re-arms it
            kind = "DX_LAMP_RESTART"
        elif pkt[:6] == b"\x02\x06\x44\x03\x82\x00":
            self.acquire = bool(pkt[6] & pc.FPGA_CTRL_ACQUIRE)
            kind = "ACQUIRE_ON" if self.acquire else "ACQUIRE_OFF"
        self.streaming = self.acquire and self.motor
        self._note(kind, pkt)
        return len(pkt)

    def _status_for(self, pkt: bytes) -> int:
        """0 = acknowledged, 1 = "no acknowledgement, board absent"."""
        return 1 if any(pkt.startswith(p) for p in self.nak) else 0

    def read(self, ep, size, _timeout=0):
        pkt = getattr(self, "_pending", b"\x00\x00\x00")
        if ep == EP_CMD_IN:
            board = pkt[2] if len(pkt) > 2 else 0
            status = self._status_for(pkt)
            if pkt[:1] == b"\x01":                      # a register read
                n = pkt[3] if len(pkt) > 3 else 1
                reg = pkt[4] if len(pkt) > 4 else 0
                if board == pc.AD_LIGHT and reg == pc.REG_LIGHT_INTERRUPT_STATUS:
                    self.dx_gate_reads += 1
                    self.dx_ready = (self.streaming
                                     and self.dx_gate_reads % 20 == 0)
                    body = bytes([pc.DX_GATE_DX if self.dx_ready else 0x00])
                elif board == pc.AD_LIGHT and reg == pc.REG_LIGHT_DX_CODE:
                    body = self._dx_packet() if self.dx_ready else bytes(n)
                    self.dx_ready = False
                elif board == pc.AD_LIGHT and reg == pc.REG_LIGHT_STATUS:
                    body = bytes([0x08])                # temps valid, no fault
                elif board == pc.AD_LIGHT and reg == REG_LIGHT_TEMPS:
                    t = int(40.06 * TEMP_UNITS_PER_C)
                    m = int(32.00 * TEMP_UNITS_PER_C)
                    body = (t.to_bytes(2, "little") + m.to_bytes(2, "little"))
                elif board == pc.AD_LIGHT and reg == pc.REG_DX_SENSORS:
                    # Four photodiodes that follow the illuminators, then the
                    # two digital sense inputs. The layout is INFERRED (see
                    # pakon_commands.REG_DX_SENSORS); this simulates the shape
                    # so the read path can be exercised, not the values.
                    lit = 0xC0 if self.dx_illum else 0x08
                    body = bytes([lit, lit, lit, lit,
                                  1 if self.dx_status else 0,
                                  1 if self.dx_status else 0])
                else:
                    body = bytes(n)
                return bytearray(bytes([0x07, 0x02, board, status]) + body)
            return bytearray(bytes([0x07, 0x02, board, status]))
        if ep == EP_IMAGE:
            if self.fh is None or not self.streaming:
                raise _SimTimeout("no data")
            allowed = int((time.time() - self.opened) * self.rate) - self.delivered
            if allowed < size:
                time.sleep(max(0.0, (size - allowed) / self.rate))
            data = self.fh.read(size)
            if not data:
                raise _SimTimeout("capture exhausted")
            self.delivered += len(data)
            return bytearray(data)
        raise _SimTimeout("unknown endpoint")

    def close(self):
        if self.fh:
            try:
                self.fh.close()
            except OSError:
                pass
            self.fh = None


class _SimTimeout(Exception):
    """Stands in for usb.core.USBError inside the simulation."""


def _simulating() -> str | None:
    return os.environ.get(ENV_SIMULATE) or None


class ScanAborted(RuntimeError):
    """Raised to unwind to the ``finally`` that stops the transport."""


class ScanRefused(RuntimeError):
    """Refused before anything was sent to the scanner."""


# --------------------------------------------------------------------------
# configuration, read from the committed calibration
# --------------------------------------------------------------------------

@dataclass
class ScanConfig:
    dpi_base: int = 16
    integration: int = 4093
    lamp_n: int = 982
    line_rate_0x91: int = 60
    levels: tuple = (4, 20, 11, 0)          # R, G, B, Ir
    on_counts: tuple = (492, 239, 104)      # R, G, B  (PWM on-counts, not duties)
    afe_gains: tuple = (13, 13, 13)
    afe_offsets: tuple = (-18, -26, -20)
    pixel_offset: int = 32
    pixel_height: int = 2000
    fpga_ctrl: int = 0x0061
    speed: int = MOTOR_SPEED[16]
    source: str = ""
    warnings: list = field(default_factory=list)

    @classmethod
    def from_calibration(cls, cal_dir: str | Path | None = None,
                         dpi_base: int = 16,
                         speed: int | None = None) -> "ScanConfig":
        """Read the exposure triad from the record of what the tables mean.

        ``calibration/README.json`` is the only statement anywhere of the
        configuration the committed dark and gain tables are valid for. Using
        anything else would silently invalidate them.
        """
        root = Path(cal_dir) if cal_dir else _ROOT / "calibration"
        p = root / "README.json"
        if not p.is_file():
            raise ScanRefused(
                f"no calibration record at {p}. A scan without one would be "
                f"exposed at values nothing on this machine can decode.")
        meta = json.loads(p.read_text())
        c = meta.get("config") or {}
        warn: list[str] = []

        base_name = str(c.get("dpi_base", ""))
        if base_name and f"DpiBase{dpi_base}_" not in base_name:
            warn.append(
                f"calibration was captured at {base_name}; scanning at base "
                f"{dpi_base} makes the committed dark and gain tables invalid")
        if dpi_base not in DECODABLE_BASES:
            warn.append(
                f"base {dpi_base} does not decode — pakon_decode accepts "
                f"{gate.WORDS_PER_LINE}-word lines only")

        levels = tuple(c.get("levels_R_G_B_Ir") or (4, 20, 11, 0))
        on = tuple(c.get("on_counts_R_G_B") or (492, 239, 104))
        n = int(c.get("lamp_pwm_N") or 982)
        integ = int(c.get("integration_0x82_idx6") or 4093)

        # The triad has to be self-consistent or the lamp pulses on one period
        # while the CCD integrates on another, which is what made exposure
        # unrepeatable before (docs/46 s3): N = trunc(exposure x 0.24).
        want_n = int(integ * 0.24)
        if abs(want_n - n) > 1:
            warn.append(
                f"lamp N {n} does not match integration {integ} "
                f"(trunc(exposure x 0.24) = {want_n}); exposure would beat")
        if max(on) >= n - 1:
            warn.append(f"PWM on-count {max(on)} is not <= N-2 ({n - 2})")

        return cls(
            dpi_base=dpi_base,
            integration=integ,
            lamp_n=n,
            line_rate_0x91=int(c.get("line_rate_0x91") or 60),
            levels=levels,
            on_counts=on,
            afe_gains=tuple(c.get("afe_gains") or (13, 13, 13)),
            afe_offsets=tuple(c.get("afe_offsets") or (-18, -26, -20)),
            pixel_offset=int(c.get("pixel_offset") or 32),
            pixel_height=int(c.get("pixel_height") or 2000),
            fpga_ctrl=int(str(c.get("fpga_ctrl") or "0x0061"), 0),
            speed=int(speed if speed is not None
                      else MOTOR_SPEED.get(dpi_base, MOTOR_SPEED[16])),
            source=str(p),
            warnings=warn,
        )

    def to_json(self) -> dict:
        d = {k: (list(v) if isinstance(v, tuple) else v)
             for k, v in self.__dict__.items()}
        d["speed_source"] = (
            f"MotorSpeedPlus for DpiBase{self.dpi_base}_35 "
            f"(default {MOTOR_SPEED.get(self.dpi_base)})")
        return d


def clamp_speed(v: int) -> int:
    return max(pc.MOTOR_SPEED_MIN_PLUS, min(pc.MOTOR_SPEED_MAX_PLUS, int(v)))


def clamp_seconds(v: float, speed: int | None = None) -> float:
    """Clamp a requested cap into the band the vendor's own bounds allow.

    With ``speed`` given the ceiling is that speed's own -- a base-4 run has no
    business asking for a base-16 run's budget. Without it the slowest speed's
    ceiling is used, which is the loosest of the three.
    """
    ceiling = scan_limits_for(speed)[1] if speed else HARD_MAX_SECONDS
    return max(MIN_MAX_SECONDS, min(ceiling, float(v)))


# --------------------------------------------------------------------------
# the USB link
# --------------------------------------------------------------------------

def acknowledged(r: bytes | None) -> bool:
    """Did the board *acknowledge*, as opposed to merely answer?

    A type-7 status-0 reply and nothing else. ``07 02 40 01`` is a response —
    it is the board saying "no acknowledgement, board absent" — and so is a
    truncated frame. ``Link.ack(required=False)`` hands back whatever came
    without judging it, so every caller that tested its return value with
    ``bool()`` was counting a NAK as a yes. That is the same mistake
    ``init_ccd.py`` made for a day of writes to a dead board, and it is the
    single expression this module now uses everywhere it asks the question.
    """
    return bool(r) and len(r) > 3 and r[0] == 0x07 and r[3] == 0x00


class Link:
    """Command and image endpoints. Every write goes through :meth:`ack`."""

    def __init__(self, dev, dry_run: bool = False, log=None,
                 simulated: bool = False) -> None:
        self.dev = dev
        self.dry_run = dry_run
        self.simulated = simulated
        self.log = log or (lambda *a, **k: None)
        self.sent: list[str] = []
        self.ctrl_shadow = 0
        #: Set once command 0x98 has turned the DX board's illuminators on.
        #: That command also disarms their 10 s auto-off, so nothing will turn
        #: them off again on its own and ``safe_stop`` has to. See
        #: :func:`lamp_watchdog_disarm`.
        self.dx_illuminator_on = False

    # ---- construction ----
    @classmethod
    def open(cls, dry_run: bool = False, log=None) -> "Link":
        if dry_run:
            return cls(None, dry_run=True, log=log)
        sim = _simulating()
        if sim:
            return cls(FakeDev(sim, os.environ.get(ENV_TRACE),
                               float(os.environ.get(ENV_SIM_RATE) or 11.6e6)),
                       log=log, simulated=True)
        import usb.core
        import usb.util
        dev = usb.core.find(idVendor=VID, idProduct=PID)
        if dev is None:
            raise ScanRefused(
                f"scanner {VID:#06x}:{PID:#06x} is not on the bus. If it is "
                f"powered on, its firmware is not loaded — run "
                f"tools/pakon_load.py first.")
        try:
            dev.set_configuration()
        except usb.core.USBError:
            pass
        usb.util.claim_interface(dev, 0)
        for ep in (EP_CMD_OUT, EP_CMD_IN, EP_IMAGE):
            try:
                dev.clear_halt(ep)
            except usb.core.USBError:
                pass
        return cls(dev, log=log)

    def close(self) -> None:
        if self.dev is None:
            return
        if self.simulated:
            self.dev.close()
            self.dev = None
            return
        try:
            import usb.util
            usb.util.release_interface(self.dev, 0)
            usb.util.dispose_resources(self.dev)
        except Exception:                                   # noqa: BLE001
            pass
        self.dev = None

    def read_image(self, size: int = CHUNK) -> bytes:
        """One bulk read of EP 0x86. Returns b'' on timeout rather than raising,
        because a timeout is normal at the head and tail of a strip."""
        try:
            return bytes(self.dev.read(EP_IMAGE, size, READ_TIMEOUT_MS))
        except self._usb_error():
            return b""

    def _usb_error(self):
        if self.simulated:
            return _SimTimeout
        import usb.core
        return usb.core.USBError

    # ---- primitives ----
    def _xfer(self, pkt: bytes, timeout: int = 2000) -> bytes | None:
        if self.dry_run:
            self.sent.append(pkt.hex(" "))
            return bytes([0x07, 0x02, pkt[2] if len(pkt) > 2 else 0, 0x00])
        try:
            self.dev.write(EP_CMD_OUT, pkt, timeout)
            return bytes(self.dev.read(EP_CMD_IN, 64, timeout))
        except self._usb_error():
            return None
        except Exception:                                   # noqa: BLE001
            return None

    def xfer(self, pkt: bytes, timeout: int = 2000) -> bytes | None:
        """One packet out, the whole raw response back, or None.

        Public because the DX poller (``tools/dx_read.py``) has to log the
        complete response — status byte included — not just the payload
        ``read_reg`` extracts. It sends reads only.
        """
        return self._xfer(pkt, timeout)

    def ack(self, pkt: bytes, label: str, required: bool = True) -> bytes:
        """Send a write/command packet and insist on a type-7 status-0 reply.

        Treating any response as success is what let a whole day of writes to a
        dead board be reported as working (``init_ccd.py``). A required packet
        that is not acknowledged aborts before the film moves.
        """
        r = self._xfer(pkt)
        ok = acknowledged(r)
        self.log("packet", label=label, pkt=pkt.hex(" "),
                 resp=(r.hex(" ") if r else None), ok=ok)
        if not ok and required:
            raise ScanAborted(
                f"{label}: scanner did not acknowledge "
                f"({pkt.hex(' ')} -> {r.hex(' ') if r else 'no response'})")
        return r or b""

    def read_reg(self, board: int, reg: int, count: int) -> bytes | None:
        r = self._xfer(pc.read_register(board, reg, count))
        if not r or len(r) < 4 + count:
            return None
        return r[4:4 + count]

    def clear_fault(self) -> bool:
        """Clear the FX2's sticky status bit 5 before anything else is sent."""
        for _ in range(8):
            r = self._xfer(pc.read_host_status())
            if r and len(r) > 3 and not (r[3] & 0x20):
                return True
            self._xfer(pc.host_clear())
        return False


# --------------------------------------------------------------------------
# lamp
# --------------------------------------------------------------------------

def lamp_init_thresholds(link: Link) -> None:
    """The monitor-threshold block. Not optional — see docs/40 s10.

    An otherwise identical bring-up without it produced no light and left
    ``0x83`` at ``0x00``. With it, ``0x83`` goes to ``0x02`` and the lamp
    lights. ``0x8E``, the one register that commands the TEC, is never sent:
    no per-unit ``LampTempWorking`` exists for this scanner and the vendor
    never sent it either. The board self-regulates to 40.0 degC on its own.
    """
    for reg, payload, label in (
        (0x8F, bytes((0xE8, 0xFF, 0x18, 0x00)), "0x8F warn band"),
        (0x8C, bytes((0xE0, 0xFF, 0x20, 0x00)), "0x8C fault band"),
        (0x8B, bytes((0xF0, 0x00, 0x20, 0x03)), "0x8B mainboard warn"),
        (0x8D, bytes((0xA0, 0x00, 0x70, 0x03)), "0x8D mainboard fault"),
    ):
        link.ack(pc.write_register(pc.AD_LIGHT, reg, payload), label)
    link.ack(pc.write_register_u8(pc.AD_LIGHT, pc.REG_LIGHT_TEMP_D0, 0), "0xD0 := 0")
    link.ack(pc.write_register_u8(pc.AD_LIGHT, pc.REG_LIGHT_TEMP_D1, 1), "0xD1 := 1")


def lamp_on(link: Link, cfg: ScanConfig) -> None:
    """Light the lamp at the calibrated levels and on-counts.

    Register order is off -> PWM -> levels -> enable, which is the order that
    was actually proven on this hardware (docs/40 s10). The vendor's own order
    is enable-first (docs/40 s12) and it works either way; this one has the
    property that the drive registers are never in flux while the lamp is
    enabled, which is the conservative choice for an LED array.

    Slot order in both registers is [B, Ir, R, -, G] with byte 3 a hard zero.
    """
    r_lvl, g_lvl, b_lvl, ir_lvl = (list(cfg.levels) + [0, 0, 0, 0])[:4]
    on_r, on_g, on_b = cfg.on_counts

    caps = pc.led_level_max(ir_on=False)
    for name, v in (("R", r_lvl), ("G", g_lvl), ("B", b_lvl)):
        cap = caps.get(name, 0)
        if v > cap:
            raise ScanRefused(
                f"lamp level {name}={v} exceeds the non-IR hardware clamp "
                f"{cap} (docs/40 s4). Refusing to overdrive the illuminant.")
    if ir_lvl:
        raise ScanRefused("IR is not scanned: a four-channel line is 8000 "
                          "words and the decoder takes 6000.")
    if max(on_r, on_g, on_b) > cfg.lamp_n - 2:
        raise ScanRefused(
            f"PWM on-count {max(on_r, on_g, on_b)} exceeds N-2 "
            f"({cfg.lamp_n - 2}); the driver clamps here and so do we.")

    link.ack(pc.lamp_off(), "lamp off (known state)")
    link.ack(pc.write_register(
        pc.AD_LIGHT, pc.REG_LIGHT_LED_DUTY,
        b"".join(v.to_bytes(2, "little")
                 for v in (on_b, 0, on_r, 0, on_g, cfg.lamp_n))),
        f"0x82 PWM on-counts B{on_b} R{on_r} G{on_g} N{cfg.lamp_n}")
    link.ack(pc.write_register(
        pc.AD_LIGHT, pc.REG_LIGHT_LED_LEVELS,
        bytes((b_lvl, 0, r_lvl, 0, g_lvl))),
        f"0x81 levels R{r_lvl} G{g_lvl} B{b_lvl}")
    link.ack(pc.lamp_set_mask(pc.LAMP_VISIBLE), "0x80 lamp ENABLE (visible)")


#: How many times ``lamp_off`` re-sends ``0x80 := 0`` before giving up. The
#: motor stop in ``safe_stop`` uses the same count for the same reason.
LAMP_OFF_ATTEMPTS = 4


def lamp_off(link: Link, attempts: int = LAMP_OFF_ATTEMPTS) -> bool:
    """Turn the lamp off, and return whether the board said it did.

    THIS RETURN VALUE IS PUBLISHED. ``safe_stop`` stores it as ``out["lamp"]``,
    which reaches the capture sidecar, the job record and the UI as a statement
    that the lamp is off. It used to be ``return True`` with the response never
    read: ``ack(required=False)`` does not raise on a NAK, and ``Link._xfer``
    swallows a USB error, a timeout and a dead handle alike and returns
    ``None``. So the one function whose job is "always turn the lamp off when
    done" reported success on every way of failing, in exactly the conditions —
    aborts, USB errors, a busy board — under which ``safe_stop`` is called.

    So it now does what the motor stop beside it has always done: read the
    acknowledgement, retry, and report the truth. A ``False`` here is not a
    reason to raise — the caller is already stopping — but it is a reason for
    everything downstream to say the lamp was NOT confirmed off.
    """
    attempts = max(1, attempts)
    for attempt in range(attempts):
        try:
            r = link.ack(pc.lamp_off(),
                         f"lamp off (attempt {attempt + 1}/{attempts})",
                         required=False)
        except Exception:                                   # noqa: BLE001
            r = None
        if acknowledged(r):
            return True
        if attempt + 1 < attempts:
            time.sleep(0.05)
    return False


LAMP_REFRESH_MODES = ("full", "drive", "enable", "off")
#: How often to re-assert the lamp drive during a scan. See lamp_refresh().
LAMP_REFRESH_S = 20.0

# --------------------------------------------------------------------------
# The DX board's auto-off, and what to do about it
# --------------------------------------------------------------------------
#
# THE MECHANISM IS DECODED. docs/57 section 6 disassembles it out of the DX
# board's PIC16F877: a 32-bit counter loaded with 0x0002FAF1 = 195 313 Timer0
# overflows, decremented once per overflow, switching off RC1 and RB0 when it
# reaches zero. At the 20 MHz clock docs/57 section 2.1 pins exactly, that is
# 10.0000 s. Command 0x98 (handler 0x0DC6) clears the arm bit outright, so a
# single packet ends it -- no refreshing. Command 0x08 puts it back.
#
# THREE REASONS NOT TO SIMPLY REPLACE THE REFRESH WITH IT:
#
#   1. 0x98 has never been sent to this machine. The mechanism is read, not
#      observed.
#   2. Nothing in the firmware names a pin. Whether RC1/RB0 drive the DX
#      emitters, the main scanning lamp or both is UNKNOWN (docs/57 sections
#      6, 9, 12). Our 20 s refresh writes the *light board's* 0x80/0x81/0x82,
#      which are a different set of registers; if those are the main lamp and
#      RC1/RB0 are not, then 0x98 will disarm a timer that was never the
#      problem and the lamp will die anyway.
#   3. The failure we are actually chasing does not fit. captures/roll.bin's
#      lamp died about two minutes in, not at ten seconds -- so either
#      something was already kicking this timer, or that failure is a
#      different one. docs/59 lists it as an open question, and it is.
#
# Against that, the refresh is the one thing that has been *measured*: 120 s
# stable with it, ~60 s without. So the default keeps it, and 0x98 is sent
# alongside as the decoded mechanism it is.
#
#   auto      send 0x98 once at scan start AND keep refreshing. The superset.
#             Costs one extra packet per scan and cannot be worse than today.
#   command   send 0x98 at start and again every refresh interval, INSTEAD of
#             the 0x81/0x82/0x80 triple -- but fall back to the refresh, for
#             the rest of the scan, the first time the board declines it. This
#             is the mode that tests the decoded mechanism without betting a
#             roll of the owner's film on it.
#   refresh   0x98 is never sent. Exactly the behaviour before this existed.
#   off       neither. The control, for reproducing the failure deliberately.
LAMP_WATCHDOG_MODES = ("auto", "command", "refresh", "off")
LAMP_WATCHDOG_DEFAULT = "auto"


def lamp_watchdog_disarm(link: Link, mask: int = pc.DX_ILLUM_BOTH) -> bool:
    """Send 0x98: set the DX illuminators and disarm their 10 s auto-off.

    Never required. A board that does not answer a write to register 0x98 is
    a board this project has learned nothing new about, not a reason to refuse
    to scan -- and the refresh is still there.

    Records on the link that the illuminators were commanded on, because the
    disarm is unconditional: once 0x98 has been sent they will not switch
    themselves off again, so ``safe_stop`` has to switch them off explicitly.

    THE FLAG IS SET BEFORE THE PACKET GOES OUT, and cleared only on an
    acknowledged off. The board acts on 0x98 when it receives it, not when we
    hear about it, so a lost acknowledgement is not evidence that the auto-off
    is still armed. Recording the disarm we did not get told about costs one
    extra off-mask packet at the stop; not recording one that happened leaves
    the illuminators on with nothing left in the system to switch them off.

    ``ok`` is a real acknowledgement, not "a response came back". A board
    NAKing every 0x98 used to read as acceptance here, which in
    ``--lamp-watchdog command`` mode kept ``LampWatchdog.fell_back`` false and
    so suppressed the 20 s refresh -- the only mechanism ever measured to keep
    the lamp alive -- for the whole run.
    """
    if mask:
        link.dx_illuminator_on = True
    try:
        r = link.ack(pc.dx_illuminator(mask),
                     f"0x98 DX illuminators 0x{mask:02X}, auto-off disarmed "
                     f"({pc.DX_WATCHDOG_S:.3f} s, docs/57 s6)",
                     required=False)
    except Exception:                                       # noqa: BLE001
        return False
    ok = acknowledged(r)
    if ok and not mask:
        link.dx_illuminator_on = False
    return ok


@dataclass
class LampWatchdog:
    """What the 0x98 path did, so the sidecar can say rather than imply."""

    mode: str = LAMP_WATCHDOG_DEFAULT
    sent: int = 0
    accepted: int = 0
    rejected: int = 0
    fell_back: bool = False
    note: str = ""

    @property
    def refresh_still_needed(self) -> bool:
        """Does the 0x81/0x82/0x80 refresh still have to run?

        Yes in ``auto`` (deliberately -- belt and braces), yes in ``refresh``,
        yes in ``command`` once the board has declined a 0x98, and no in
        ``command`` while 0x98 is being accepted. ``off`` runs nothing.
        """
        if self.mode == "off":
            return False
        if self.mode == "command":
            return self.fell_back
        return True

    def to_json(self) -> dict:
        return {
            "mode": self.mode,
            "sent": self.sent,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "fell_back_to_refresh": self.fell_back,
            "watchdog_seconds": round(pc.DX_WATCHDOG_S, 4),
            "register": f"0x{pc.REG_DX_ILLUM:02X}",
            "note": self.note or (
                "0x98 is a decoded mechanism (docs/57 s6) that has never been "
                "confirmed on hardware, and whether RC1/RB0 are the main lamp "
                "is unknown. The 20 s refresh is the measured one."),
        }

    def send(self, link: Link, mask: int = pc.DX_ILLUM_BOTH) -> bool:
        self.sent += 1
        ok = lamp_watchdog_disarm(link, mask)
        if ok:
            self.accepted += 1
        else:
            self.rejected += 1
            if self.mode == "command" and not self.fell_back:
                self.fell_back = True
                self.note = (
                    "the board did not acknowledge 0x98, so the 20 s "
                    "0x82/0x81/0x80 refresh took over for the rest of the run")
        return ok


def lamp_refresh(link: Link, cfg: "ScanConfig", mode: str = "full") -> bool:
    """Re-assert the lamp drive mid-scan, without ever turning it off.

    WHY THIS EXISTS. The lamp has now died at roughly sixty seconds, twice, at
    the same point, which caps every scan at about a minute. The leading
    hypothesis is a light-board safety timeout that expects the host to keep
    saying the lamp should be on.

    The evidence is a detail that never made sense as initialisation:
    ``FN_bBeforeScan`` calls ``LampOn`` **twice, a second apart**. A second
    ``FN_bDrvLampOn`` with an unchanged mask does not rewrite ``0x80`` — the
    mask is cached host-side and skipped (docs/40 s12) — so what the vendor's
    second call actually puts on the wire is ``0x81`` and ``0x82`` again, with
    identical values. As re-initialisation that is a no-op. As a watchdog kick
    it is not.

    So this sends the same bytes the vendor's second call does, plus the enable
    mask, because we do not yet know which of the two the board counts:

      ``full``    0x82 PWM, 0x81 levels, 0x80 mask — a superset, the default,
                  because the point is to settle the hypothesis in one run
      ``drive``   0x82 and 0x81 only — exactly the vendor's second LampOn
      ``enable``  0x80 only — the narrowest reading of the hypothesis
      ``off``     nothing, to reproduce the failure as a control

    What it never does is send ``0x80 = 0``. The lamp is not cycled: the proven
    bring-up order starts with an off, and doing that here would put a black
    band through the middle of the owner's roll.

    Values come from ``cfg``, so a refresh cannot drift the exposure away from
    the one the committed calibration is valid for.
    """
    if mode == "off":
        return True
    r_lvl, g_lvl, b_lvl, _ir = (list(cfg.levels) + [0, 0, 0, 0])[:4]
    on_r, on_g, on_b = cfg.on_counts
    ok = True
    try:
        if mode in ("full", "drive"):
            ok &= bool(link.ack(pc.write_register(
                pc.AD_LIGHT, pc.REG_LIGHT_LED_DUTY,
                b"".join(v.to_bytes(2, "little")
                         for v in (on_b, 0, on_r, 0, on_g, cfg.lamp_n))),
                "lamp refresh 0x82 PWM", required=False))
            ok &= bool(link.ack(pc.write_register(
                pc.AD_LIGHT, pc.REG_LIGHT_LED_LEVELS,
                bytes((b_lvl, 0, r_lvl, 0, g_lvl))),
                "lamp refresh 0x81 levels", required=False))
        if mode in ("full", "enable"):
            ok &= bool(link.ack(pc.lamp_set_mask(pc.LAMP_VISIBLE),
                                "lamp refresh 0x80 enable", required=False))
    except Exception:                                       # noqa: BLE001
        return False
    return ok


# --------------------------------------------------------------------------
# film position — what the machine reports, rather than what we infer
# --------------------------------------------------------------------------
#
# THE BITS HAVE BEEN ARRIVING ALL ALONG. Every DX packet's first record carries
# a status nibble, and hardware_cb = 0xC0000000 -- film sensed at entry AND at
# exit -- is in every scan sidecar this project has taken. Nothing read it.
#
# Meanwhile the optical end-of-roll detector has been wrong twice: once it read
# a dead lamp as film, once it stopped on the leader. Both are inferences from
# image brightness about a question the transport answers directly.
#
# So the sensors become the primary signal, in the two directions that are
# actually safe:
#
#   * film sensed, then sustained-clear  ->  the roll has ended. Stop.
#   * film sensed and still present      ->  VETO an optical roll-end. This is
#                                            the "stopped on the leader" bug,
#                                            and the veto is exactly what
#                                            prevents it.
#
# and in the direction that is not safe, it does nothing:
#
#   * the DARK stop is never vetoed. Film present plus a dark sensor is a lamp
#     that has died with the owner's film in the gate, which is the failure
#     this whole module exists for. docs/53 s4.5 records that the vendor would
#     have neither aborted nor warned; we abort.
#
# LIMITS, STATED PLAINLY. The status nibble only exists on packets that carry
# at least one record (the board ORs it into record 0's type byte and nowhere
# else, docs/57 s8.2). So when events stop arriving the sensors stop being
# readable, and a stale reading must not be allowed to veto anything -- hence
# FILM_SENSE_STALE_S. "Events stopped arriving" is itself a plausible
# end-of-roll signal (docs/57 s7.3 suggests counting lines since the last
# perforation) but that needs a lines-per-mm figure this file does not have,
# so it is not implemented and not pretended to be.

#: Both sensors must read clear for this long, continuously, before the roll is
#: called ended. Film presence does not flicker with image content the way the
#: optical detector's CLEAR does, so this can be far shorter than
#: ``gate.ROLL_END_LINES`` -- but it is long enough that a single mis-read
#: packet cannot end a roll. INFERRED: no vendor value corresponds to it.
FILM_SENSE_CLEAR_S = 2.0

#: After this long without a readable status nibble, the film sensors have no
#: current opinion: they cannot end a roll and they cannot veto the optical
#: detector. Without this, a DX board that went quiet while film was present
#: would veto every optical roll-end for the rest of the scan.
FILM_SENSE_STALE_S = 5.0


@dataclass
class FilmSense:
    """Film position and mis-load warnings, from the DX status nibble.

    Fed one :class:`dx_decode.DxPacket` at a time. Packets whose
    ``status_valid`` is false are ignored entirely -- an empty queue is not a
    report that the sensors are clear.
    """

    armed: bool = False                 # film has been sensed at least once
    present: bool | None = None         # the last state actually reported
    at_entry: bool = False
    at_exit: bool = False
    packets: int = 0                    # packets that carried a status nibble
    last_report: float = 0.0            # monotonic-ish time of that report
    clear_since: float | None = None
    ended: bool = False
    tail_first: bool = False
    emulsion_down: bool = False
    vetoed_optical: int = 0
    warnings: list = field(default_factory=list)
    pending: list = field(default_factory=list)   # drained by the caller

    def feed(self, pkt, now: float) -> str | None:
        """Absorb one packet. Returns a stop detail when the roll has ended."""
        if pkt is None or not getattr(pkt, "status_valid", False):
            return None
        self.packets += 1
        self.last_report = now
        self.at_entry = pkt.film_at_entry
        self.at_exit = pkt.film_at_exit
        self.present = bool(pkt.film_present)

        # Mis-load bits: warn, never abort. docs/53 s4.2 — "there is no code
        # path in TLB.dll that aborts a scan on emulsion-down or tail-first";
        # the bits are OR-ed into the hardware status word and the scan
        # proceeds with corrected geometry. Warning once is more than the
        # vendor's GUI does mid-scan and less than stopping the owner's roll.
        if pkt.tail_first and not self.tail_first:
            self.tail_first = True
            self._warn("FILM TAIL FIRST — the strip is going through backwards. "
                       "Scanning continues; frame numbering and the "
                       "perforation offsets run the other way.")
        if pkt.emulsion_down and not self.emulsion_down:
            self.emulsion_down = True
            self._warn("FILM EMULSION DOWN — the strip is upside down. "
                       "Scanning continues; the frames will be mirrored.")

        if self.present:
            if not self.armed:
                self.armed = True
                self._warn("film sensed in the transport; the film sensors are "
                           "now the primary end-of-roll signal", level="info")
            self.clear_since = None
            return None

        # Clear. Only meaningful once film has actually been seen -- before
        # that, "clear" is the empty transport before the leader arrives.
        if not self.armed:
            return None
        if self.clear_since is None:
            self.clear_since = now
            return None
        held = now - self.clear_since
        if held >= FILM_SENSE_CLEAR_S and not self.ended:
            self.ended = True
            return (f"both film sensors have read clear for {held:.1f} s after "
                    f"{self.packets} status reports. The machine says the film "
                    f"has left the transport.")
        return None

    def _warn(self, text: str, level: str = "warn") -> None:
        self.warnings.append(text)
        self.pending.append((level, text))

    def drain(self) -> list:
        out, self.pending = self.pending, []
        return out

    def fresh(self, now: float) -> bool:
        """Is there a current reading? A stale one must not decide anything."""
        return self.packets > 0 and (now - self.last_report) <= FILM_SENSE_STALE_S

    def vetoes_roll_end(self, now: float) -> bool:
        """Should an optical roll-end be ignored right now?

        Only when the machine is currently, freshly reporting film in the
        transport. Anything else -- never armed, gone quiet, or reporting
        clear -- and the optical detector has the floor.
        """
        return bool(self.armed and self.present and self.fresh(now))

    def veto(self, state, now: float) -> str | None:
        """Withdraw an optical roll-end that the sensors contradict.

        Mutates ``state`` (a :class:`pakon_gate.RunState`) in place, clearing
        the stop and resetting the clear run so the optical detector has to
        earn it again rather than re-firing on the next window. Returns the
        message to log, or None if there was nothing to veto.

        Only ``STOP_ROLL_END`` is ever withdrawn. ``STOP_DARK`` is not, and
        that asymmetry is the point: see the note above this class.
        """
        if state.stop != gate.STOP_ROLL_END or not self.vetoes_roll_end(now):
            return None
        self.vetoed_optical += 1
        msg = (f"the image has been clear for {state.clear_run} lines, but the "
               f"film sensors still report film in the transport "
               f"(entry={self.at_entry}, exit={self.at_exit}). Not ending the "
               f"roll on that.")
        state.stop = None
        state.stop_detail = ""
        state.clear_run = 0
        return msg

    def to_json(self) -> dict:
        return {
            "available": self.packets > 0,
            "armed": self.armed,
            "present": self.present,
            "at_entry": self.at_entry,
            "at_exit": self.at_exit,
            "status_reports": self.packets,
            "ended_roll": self.ended,
            "tail_first": self.tail_first,
            "emulsion_down": self.emulsion_down,
            "optical_roll_ends_vetoed": self.vetoed_optical,
            "warnings": list(self.warnings),
            "clear_seconds_required": FILM_SENSE_CLEAR_S,
            "stale_after_s": FILM_SENSE_STALE_S,
            "source": "DX status nibble bits 0x20 (entry) / 0x10 (exit), "
                      "docs/53 s4.1; HARDWARE_CB_FILM_SENSE_ENTRY 0x40000000 / "
                      "_EXIT 0x80000000",
        }


@dataclass
class LampHealth:
    ok: bool = True
    status: int | None = None
    temp_lb_c: float | None = None
    temp_mb_c: float | None = None
    temp_valid: bool = False
    fault: str = ""
    polls: int = 0
    failures: int = 0

    def to_json(self) -> dict:
        return {
            "ok": self.ok,
            "status": self.status,
            "status_hex": None if self.status is None else f"0x{self.status:02x}",
            "temp_lb_c": None if self.temp_lb_c is None else round(self.temp_lb_c, 2),
            "temp_mb_c": None if self.temp_mb_c is None else round(self.temp_mb_c, 2),
            "temp_valid": self.temp_valid,
            "fault": self.fault,
            "polls": self.polls,
            "failures": self.failures,
        }


def poll_lamp(link: Link, h: LampHealth) -> LampHealth:
    """One lamp health poll: status ``0x83`` and temperatures ``0x88``.

    The vendor polls the same two things from ``FN_bDrvGetHardwareStatusLamp``
    but never between the acquisition call and the end of the roll, which is
    why the overnight failure went unnoticed for five minutes. This is called
    once a second, inline in the capture loop.

    Inline, deliberately. A second thread doing USB while the bulk reads run
    would be faster, but the one hard-won lesson of this capture path is that
    interfering with the stream mid-loop destroys it (docs/45), and a control
    round trip once a second is 0.3 % of the loop's time. Correctness over
    throughput, in the code whose job is to stop things.
    """
    h.polls += 1
    st = link.read_reg(pc.AD_LIGHT, pc.REG_LIGHT_STATUS, 1)
    temps = link.read_reg(pc.AD_LIGHT, REG_LIGHT_TEMPS, 4)
    if st is None and temps is None:
        h.failures += 1
        if h.failures >= LAMP_POLL_FAIL_LIMIT:
            h.ok = False
            h.fault = (f"the light board stopped answering "
                       f"({h.failures} polls). Nothing is watching the lamp.")
        return h
    h.failures = 0

    if st is not None:
        h.status = st[0]
        h.temp_valid = bool(st[0] & LAMP_STATUS_BIT_TEMP_VALID)
        if st[0] & LAMP_STATUS_FAULT_MASK:
            bits = [str(b) for b in (5, 6) if st[0] & (1 << b)]
            h.ok = False
            h.fault = (f"light-board status 0x{st[0]:02x}: fault bit"
                       f"{'s' if len(bits) > 1 else ''} {', '.join(bits)} set "
                       f"(docs/40 s12)")
            return h

    if temps is not None and len(temps) >= 4:
        lb = int.from_bytes(temps[0:2], "little") / TEMP_UNITS_PER_C
        mb = int.from_bytes(temps[2:4], "little") / TEMP_UNITS_PER_C
        h.temp_lb_c, h.temp_mb_c = lb, mb
        lo, hi = TEMP_PLAUSIBLE_C
        if lo <= lb <= hi and not (LAMP_TEMP_FAULT_C[0] <= lb <= LAMP_TEMP_FAULT_C[1]):
            h.ok = False
            h.fault = (f"lamp board at {lb:.1f} degC, outside "
                       f"{LAMP_TEMP_FAULT_C[0]:.0f}-{LAMP_TEMP_FAULT_C[1]:.0f}")
    return h


# --------------------------------------------------------------------------
# CCD / FPGA
# --------------------------------------------------------------------------

def ccd_configure(link: Link, cfg: ScanConfig) -> None:
    """Geometry, integration and A/D, from FN_bDrvInitCcd (see init_ccd.py).

    Acquire is *not* enabled here. It is a separate act, immediately before
    the transport starts, so the sensor is never running longer than it needs.
    """
    put = lambda i, v, lab: link.ack(pc.fpga_write(i, v), lab)     # noqa: E731
    # idx5 is the END PIXEL, not the height. fcn.1002c340 asserts on
    # (offset + height) and docs/53 traced it explicitly. Writing the bare
    # height made the FPGA read out pixels offset..height -- 1968 instead of
    # 2000 -- so every sync gap came back 5904 words instead of 6000 and the
    # decoder rejected an otherwise perfect 720 MB capture.
    pixel_end = cfg.pixel_offset + cfg.pixel_height
    put(pc.FPGA_IDX_PIXEL_OFFSET, cfg.pixel_offset, "FPGA idx4 pixel offset")
    put(pc.FPGA_IDX_PIXEL_END, pixel_end,
        f"FPGA idx5 pixel end {pixel_end}"
        f" (= offset {cfg.pixel_offset} + height {cfg.pixel_height})")
    put(pc.FPGA_IDX_INTEGRATION_TIME, cfg.integration,
        f"FPGA idx6 integration {cfg.integration}")
    put(pc.FPGA_IDX_0B, 0, "FPGA idx11 := 0")
    for idx in (pc.FPGA_IDX_ZERO_1, pc.FPGA_IDX_ZERO_2, pc.FPGA_IDX_ZERO_3):
        put(idx, 0, f"FPGA idx{idx} := 0")
    put(pc.FPGA_IDX_0A, 0x400, "FPGA idx10 := 0x400")

    link.ack(pc.adc_write(pc.ADC_IDX_78, 0x78), "A/D idx0 := 0x78")
    link.ack(pc.adc_write(pc.ADC_IDX_80, 0x80), "A/D idx1 := 0x80")
    for idx, g in zip((pc.ADC_IDX_GAIN_R, pc.ADC_IDX_GAIN_G, pc.ADC_IDX_GAIN_B),
                      cfg.afe_gains):
        if not 0 <= g <= pc.ADC_GAIN_MAX:
            raise ScanRefused(f"A/D gain {g} outside 0..{pc.ADC_GAIN_MAX}")
        link.ack(pc.adc_write(idx, g), f"A/D gain idx{idx} := {g}")
    for idx, o in zip((pc.ADC_IDX_EXPOSURE_R, pc.ADC_IDX_EXPOSURE_G,
                       pc.ADC_IDX_EXPOSURE_B), cfg.afe_offsets):
        link.ack(pc.adc_write(idx, int(o) & 0xFFFF),
                 f"A/D offset idx{idx} := {o}")

    # The committed fpga_ctrl is 0x061 = MODE(0x060) | ACQUIRE(0x001): the
    # calibration references were captured with acquire already in the word.
    # Mask it out here so configuring the sensor does not start it. `acquire()`
    # ORs it back in as its own deliberate step, immediately before the film
    # moves, and the word that reaches the FPGA is then identical to 0x061.
    link.ctrl_shadow = (cfg.fpga_ctrl & pc.FPGA_CTRL_WIDTH_MASK
                        & ~pc.FPGA_CTRL_ACQUIRE)
    link.ack(pc.fpga_set_control(link.ctrl_shadow),
             f"FPGA control := 0x{link.ctrl_shadow:03x} "
             f"(acquire bit deliberately withheld)")


def acquire(link: Link, on: bool) -> None:
    """FPGA control bit 0 — the master acquire enable (docs/12, start_acquire.py)."""
    if on:
        link.ctrl_shadow |= pc.FPGA_CTRL_ACQUIRE
    else:
        link.ctrl_shadow &= ~pc.FPGA_CTRL_ACQUIRE
    link.ack(pc.fpga_set_control(link.ctrl_shadow & pc.FPGA_CTRL_WIDTH_MASK),
             f"acquire {'ON' if on else 'off'} "
             f"(control 0x{link.ctrl_shadow & 0x3ff:03x})",
             required=on)


def reset_fifos(link: Link) -> None:
    """Both halves of ``FN_bDrvResetFifos``.

    THIS IS CALLED EXACTLY TWICE, BEFORE THE SCAN, AND NEVER INSIDE THE READ
    LOOP. Resetting mid-stream discards whatever the FPGA has buffered since
    the last read, and that alone destroyed 5.2 % of every capture until it was
    found (docs/45). The vendor resets twice in ``BeforeScan`` and then streams
    the whole strip without touching it again.
    """
    for pkt in pc.reset_fifos():
        link.ack(pkt, "reset FIFOs", required=False)


# --------------------------------------------------------------------------
# the stop, which is the only part that absolutely must work
# --------------------------------------------------------------------------

def safe_stop(link: Link, log=None, dx_illuminators: bool | None = None) -> dict:
    """Motor first, then lamp, then acquire. Never raises.

    Order matters: film movement is the thing that damages film, so the stop
    packet goes out before anything else is attempted, and it is retried. The
    lamp and the sensor can wait a few milliseconds.

    EVERY FLAG IN THE RETURNED DICT IS A MEASUREMENT. ``motor`` and ``lamp``
    are true only when the board acknowledged, because this dict is what the
    sidecar, the job record and the UI quote when they tell the owner the
    machine is safe. ``acquire`` is the exception and says so: it records that
    the write was attempted without raising.

    ``dx_illuminators`` decides whether the 0x98 off-mask is sent:

      ``None``   ask this link -- it is the process that disarmed the auto-off,
                 so ``link.dx_illuminator_on`` is a real answer.
      ``True``   send it regardless. For a recovery process, whose Link is
                 fresh and whose flag is therefore always ``False`` even though
                 the dead process may well have disarmed the board.
      ``False``  never send it.
    """
    log = log or (lambda *a, **k: None)
    out = {"motor": False, "lamp": False, "acquire": False,
           "dx_illuminators": None, "errors": []}
    for attempt in range(4):
        try:
            r = link.ack(pc.motor_stop(), f"MOTOR STOP (attempt {attempt + 1})",
                         required=False)
            if acknowledged(r):
                out["motor"] = True
                break
        except Exception as e:                              # noqa: BLE001
            out["errors"].append(f"motor stop: {e}")
        time.sleep(0.05)
    try:
        out["lamp"] = lamp_off(link)
    except Exception as e:                                  # noqa: BLE001
        out["errors"].append(f"lamp off: {e}")
    # If 0x98 was sent, the DX board's 10 s auto-off is disarmed and its
    # illuminators will now stay on forever unless told otherwise. Sending
    # 0x98 with an empty mask is the only way back -- 0x08 would turn them on
    # again and re-arm the timer.
    #
    # A RECOVERY PROCESS CANNOT KNOW, SO IT SENDS IT ANYWAY. `dx_illuminator_on`
    # lives on the Link object, and `emergency_stop` opens a brand new one; the
    # flag there is False by construction, so this was skipped by every path
    # that runs after the scanning process is gone -- `pakon_scan.py stop`,
    # `check_stale` at app start, the parent's recovery and POST scan/stop. The
    # cost of sending it when nothing was disarmed is one packet that turns the
    # illuminators off and leaves them off; the cost of not sending it is
    # leaving them on indefinitely, and docs/57 s6/s9/s12 cannot yet rule out
    # that RC1/RB0 are the main lamp. Off is the state to fail into.
    if dx_illuminators is None:
        dx_illuminators = bool(getattr(link, "dx_illuminator_on", False))
    if dx_illuminators:
        try:
            out["dx_illuminators"] = lamp_watchdog_disarm(link, pc.DX_ILLUM_OFF)
        except Exception as e:                              # noqa: BLE001
            out["errors"].append(f"DX illuminators off: {e}")
    try:
        link.ack(pc.dx_stop(), "DX stop", required=False)
    except Exception:                                       # noqa: BLE001
        pass
    try:
        acquire(link, False)
        out["acquire"] = True
    except Exception as e:                                  # noqa: BLE001
        out["errors"].append(f"acquire off: {e}")
    log("stop", **out)
    return out


def emergency_stop(retries: int = 6, delay: float = 0.25) -> dict:
    """Open the device from scratch and stop it. For use by a *different*
    process from the one that was scanning.

    Retried, because if the scanning process was just killed the kernel may
    still be tearing down its claim on the interface; the handle frees within
    a moment and then this gets through.

    THE DX OFF-MASK IS UNCONDITIONAL HERE. This Link is new, so its
    ``dx_illuminator_on`` is False whatever the dead process did, and the
    marker file records only the path and the time limit. There is therefore no
    way for a recovery process to *learn* that the 10 s auto-off was disarmed
    -- and it is disarmed on every application-driven scan, because
    ``LAMP_WATCHDOG_DEFAULT`` is ``auto`` and ``pakon_app`` passes no override.
    So it is sent every time. See ``safe_stop``.
    """
    last = ""
    for i in range(retries):
        link = None
        try:
            link = Link.open()
            link.clear_fault()
            out = safe_stop(link, dx_illuminators=True)
            out["attempts"] = i + 1
            return out
        except ScanRefused as e:
            return {"motor": False, "lamp": False, "acquire": False,
                    "errors": [str(e)], "absent": True, "attempts": i + 1}
        except Exception as e:                              # noqa: BLE001
            last = f"{e.__class__.__name__}: {e}"
            time.sleep(delay)
        finally:
            if link is not None:
                link.close()
    return {"motor": False, "lamp": False, "acquire": False,
            "errors": [f"could not open the scanner to stop it: {last}"],
            "attempts": retries}


# ---- what the capture was taken at ----

def capture_metadata(out: Path, cfg: "ScanConfig", res: "ScanResult",
                     gate_desc: dict | None = None) -> dict:
    """Everything a decode needs that cannot be recovered from the .bin itself.

    THE TRANSPORT SPEED IS THE POINT OF THIS FILE. Lines-per-mm along the
    travel direction scales inversely with transport speed, so the resample
    factor that makes pixels square is a property of *this capture*, not a
    constant. ``pakon_decode.DEFAULT_TRANSPORT_SCALE`` is one number derived at
    one speed; a capture taken at any other speed decodes geometrically
    stretched, and nothing in the .bin records which speed that was. Tonight's
    ``gold400.bin`` ran at 11467 and is affected.

    So the speed and the line rate go in a sidecar next to the capture, and the
    decode can call ``pakon_decode.transport_scale(speed, line_rate)`` instead
    of assuming. Fixing the decode belongs to the colour task; making the
    information exist belongs here.

    The exposure triad is recorded for the same reason: it is what says which
    dark and gain tables the capture is decodable with at all.
    """
    meta = {
        "version": 1,
        "capture": str(out),
        # --- the contract pakon_decode.load_capture_sidecar reads. Top level,
        # by that function's own lookup order, and duplicated under "config"
        # because it accepts either. Do not rename these without changing it.
        "speed": cfg.speed,
        "line_rate_0x91": cfg.line_rate_0x91,
        "config": cfg.to_json(),
        "bytes": res.bytes,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "written_by": "tools/pakon_scan.py",
        "dpi_base": cfg.dpi_base,
        "transport": {
            "speed_reg_0xA5": cfg.speed,
            "line_rate_0x91": cfg.line_rate_0x91,
            "note": "lines/mm along travel goes as 1/speed, so the square-pixel "
                    "resample factor is a property of this capture. Do not use "
                    "a hardcoded scale.",
        },
        "exposure": {
            "integration_0x82_idx6": cfg.integration,
            "lamp_pwm_N": cfg.lamp_n,
            "levels_R_G_B_Ir": list(cfg.levels),
            "on_counts_R_G_B": list(cfg.on_counts),
            "afe_gains": list(cfg.afe_gains),
            "afe_offsets": list(cfg.afe_offsets),
            "pixel_offset": cfg.pixel_offset,
            "pixel_height": cfg.pixel_height,
            "fpga_ctrl": f"0x{cfg.fpga_ctrl:04x}",
            "note": "integration, N and 0x91 are one setting in three "
                    "registers; the committed dark/gain tables are valid only "
                    "for this triad.",
        },
        "calibration_source": cfg.source,
        "run_detector": res.run,
        "run": {
            "reason": res.reason,
            "detail": res.detail,
            "lines": res.lines,
            "windows": res.windows,
            "sync_breaks": res.sync_breaks,
            "seconds": res.seconds,
            "mib_s": res.mib_s,
            "ok": res.ok,
            "dark_stop_suppressed": res.dark_stop_suppressed,
        },
        "lamp": res.lamp,
        "lamp_refresh": res.lamp_refresh,
        "lamp_watchdog": res.lamp_watchdog,
        "film_sense": res.film_sense,
        "stopped": res.stopped,
        "gate": gate_desc or {},
        "dx": res.dx,
        "dx_log": res.dx_log,
        # Flattened for readers that only want the outcome.
        "lines": res.lines,
        "reason": res.reason,
        "ok": res.ok,
    }
    # Derived, and only if the decode module is importable. It is under active
    # development by another task, so a failure to import it must never cost us
    # the speed itself -- which is the part that cannot be recovered later.
    try:
        import pakon_decode as _dec
        meta["transport"]["transport_scale"] = round(
            _dec.transport_scale(cfg.speed, cfg.line_rate_0x91), 6)
        meta["transport"]["scale_source"] = (
            "pakon_decode.transport_scale(speed, line_rate)")
        meta["transport"]["square_motor_speed"] = _dec.SQUARE_MOTOR_SPEED
    except Exception as e:                                  # noqa: BLE001
        meta["transport"]["transport_scale"] = None
        meta["transport"]["scale_source"] = f"not computed: {e}"
    return meta


def write_capture_metadata(out: Path, cfg: "ScanConfig", res: "ScanResult",
                           gate_desc: dict | None = None) -> str | None:
    """Write ``<capture>.scan.json``. Never raises; a scan is not lost over it.

    One file, with the name ``pakon_decode.load_capture_sidecar`` already looks
    for. There were briefly two — a ``.meta.json`` from here and a
    ``.scan.json`` written afterwards from ``cmd_run`` — which is precisely the
    arrangement in which a decode later reads whichever it finds first and the
    two quietly disagree. Written from ``run_scan``'s ``finally`` so it also
    exists when a scan aborts, which the ``cmd_run`` version could not
    guarantee.
    """
    try:
        p = out.with_suffix(".scan.json")
        p.write_text(json.dumps(capture_metadata(out, cfg, res, gate_desc),
                                indent=1))
        return str(p)
    except Exception:                                       # noqa: BLE001
        return None


# ---- the marker, for when both processes die ----
#
# THE MARKER IS THE ONLY THING ONE PROCESS CAN TELL THE NEXT. It used to carry
# the capture path and the time limit, which is enough to say "a scan was in
# flight" and nothing at all about what state the machine was left in. In
# particular it could not say that command 0x98 had disarmed the DX board's
# 10 s illuminator auto-off -- which every application-driven scan does, since
# LAMP_WATCHDOG_DEFAULT is "auto" -- so the recovery paths had no way to know
# the illuminators would never switch themselves off again.
#
# `safe_stop(dx_illuminators=True)` in `emergency_stop` is what actually fixes
# that, because it does not need to know. This field exists so the recovery is
# explicable rather than blind: it says why the off-mask was warranted.

def marker_write(info: dict) -> None:
    try:
        MARKER.write_text(json.dumps({**info, "pid": os.getpid(),
                                      "started": time.time()}))
    except OSError:
        pass


def marker_clear() -> None:
    try:
        MARKER.unlink()
    except OSError:
        pass


def marker_should_clear(stopped: dict) -> bool:
    """May the in-flight marker be removed, given what the stop achieved?

    ONE RULE, IN ONE PLACE, BECAUSE THREE COPIES OF IT DISAGREED. ``run_scan``
    keeps the marker when the transport stop was not acknowledged -- that is
    the module docstring's "the next process to start cleans up" guarantee, and
    it is the only thing that makes a failed stop get retried. The recovery
    paths did the opposite: ``emergency_stop()`` followed by an unconditional
    ``marker_clear()``. So when a recovery exhausted its six attempts and
    stopped nothing, the marker was deleted anyway and no process would ever
    try again -- the one situation the marker exists for.

    Two things license removal:

      ``motor``   the board acknowledged the stop. The machine is stopped.
      ``absent``  the scanner is not on the bus at all, so there is nothing
                  left to stop and a marker would be retried forever.
    """
    return bool(stopped.get("motor") or stopped.get("absent"))


def marker_clear_if_stopped(stopped: dict) -> bool:
    """Apply :func:`marker_should_clear`. Returns whether it was removed."""
    if not marker_should_clear(stopped):
        return False
    marker_clear()
    return True


def check_stale(force: bool = False) -> dict:
    """A marker with no live owner means a scan died without a confirmed stop.

    Called at application start. Cheap, and the only thing standing between a
    hard crash mid-scan and a transport that is still running.
    """
    if not MARKER.is_file():
        return {"stale": False}
    try:
        info = json.loads(MARKER.read_text())
    except (OSError, json.JSONDecodeError):
        info = {}
    pid = int(info.get("pid") or 0)
    alive = False
    if pid and pid != os.getpid():
        try:
            os.kill(pid, 0)
            alive = True
        except OSError:
            alive = False
    if alive and not force:
        return {"stale": False, "owner_pid": pid, "running": True}
    out = emergency_stop()
    # Only if it worked. A recovery that stopped nothing has to leave the
    # marker behind, or the next process has no reason to try.
    cleared = marker_clear_if_stopped(out)
    return {"stale": True, "owner_pid": pid, "stopped": out, "marker": info,
            "marker_cleared": cleared,
            "retry_pending": not cleared}


# --------------------------------------------------------------------------
# the scan
# --------------------------------------------------------------------------

@dataclass
class ScanResult:
    path: str = ""
    bytes: int = 0
    lines: int = 0
    seconds: float = 0.0
    mib_s: float = 0.0
    sync_breaks: int = 0
    windows: int = 0
    reason: str = ""
    detail: str = ""
    stopped: dict = field(default_factory=dict)
    lamp: dict = field(default_factory=dict)
    run: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    packets: list = field(default_factory=list)
    dx: dict = field(default_factory=dict)
    dx_log: str = ""
    lamp_refresh: dict = field(default_factory=dict)
    lamp_watchdog: dict = field(default_factory=dict)
    film_sense: dict = field(default_factory=dict)
    dark_stop_suppressed: bool = False
    metadata: str | None = None
    ok: bool = False

    def to_json(self) -> dict:
        return dict(self.__dict__)


class Cancel:
    """A cancel that a signal handler, a watchdog thread and the main loop can
    all set, and that the loop checks between every read."""

    def __init__(self) -> None:
        self._e = threading.Event()
        self.reason = ""

    def set(self, reason: str) -> None:
        if not self._e.is_set():
            self.reason = reason
        self._e.set()

    def __bool__(self) -> bool:
        return self._e.is_set()


def watch_parent(cancel: Cancel) -> None:
    """Block on stdin. EOF means the parent process is gone.

    The parent holds the write end of this pipe for as long as it is alive. It
    does not have to send anything, and it does not have to exit cleanly: a
    SIGKILLed parent still has its file descriptors closed by the kernel, and
    that is what reaches us here.

    ``os.read`` on the raw descriptor, not ``sys.stdin.buffer.read``. This is a
    daemon thread that is normally still blocked here when the scan ends, and
    a daemon thread holding a BufferedReader's lock at interpreter shutdown
    makes CPython abort with SIGABRT ("could not acquire lock ... at
    interpreter shutdown"). It did, on the first end-to-end run: the stop had
    already gone out, but the process died on signal 6 instead of reporting
    its result. The raw descriptor takes no such lock.
    """
    try:
        while True:
            b = os.read(0, 1)
            if not b:
                cancel.set("the application that started this scan has gone")
                return
            if b in (b"q", b"c"):
                cancel.set("cancelled")
                return
    except (OSError, ValueError):
        cancel.set("control channel lost")


def run_scan(out_path: str | Path,
             cfg: ScanConfig,
             max_seconds: float | None = None,
             max_bytes: int = DEFAULT_MAX_BYTES,
             cancel: Cancel | None = None,
             log=None,
             dry_run: bool = False,
             skip_lamp_health: bool = False,
             read_dx: bool = True,
             dx_log: str | Path | None = None,
             lamp: bool = True,
             lamp_refresh_s: float = LAMP_REFRESH_S,
             lamp_refresh_mode: str = "full",
             lamp_watchdog: str = LAMP_WATCHDOG_DEFAULT) -> ScanResult:
    """One scan, start to finish, with every guard armed.

    ``read_dx`` adds the DX poll to the capture loop: pure reads of light-board
    registers 0x02 and 0x90, logged raw beside the capture as ``.dx.jsonl``.
    It cannot abort a scan and cannot move anything; if it fails it is noted
    and the scan continues.

    ``lamp=False`` is the DX-without-the-lamp experiment and nothing else. It
    leaves the lamp off, which necessarily means every window classifies DARK,
    so the DARK stop is suppressed for the duration — the hard time limit is
    what stops it. Do not use it to scan film: the capture will be black.

    ``lamp_watchdog`` chooses how the DX board's decoded 10 s auto-off is
    handled — see :data:`LAMP_WATCHDOG_MODES` for what each one sends and why
    the default is the one that does both.
    """
    log = log or (lambda *a, **k: None)
    # NOT `cancel or Cancel()`. Cancel defines __bool__ so the loop can write
    # `if cancel:`, which makes an un-set Cancel falsy — so `or` would throw
    # the caller's object away and replace it with a fresh one, and every
    # cancel would be delivered to an object nobody was reading. That is
    # precisely the "enabled and does nothing" Cancel this work exists to not
    # repeat, and the selftest caught it.
    if cancel is None:
        cancel = Cancel()
    # None means "use the cap this transport speed implies" rather than one
    # constant shared by three speeds that differ by 4.4x. docs/55 s7.
    if max_seconds is None:
        max_seconds = scan_limits_for(cfg.speed)[0]
    max_seconds = clamp_seconds(max_seconds, cfg.speed)
    if lamp_watchdog not in LAMP_WATCHDOG_MODES:
        raise ScanRefused(
            f"unknown lamp watchdog mode {lamp_watchdog!r}; "
            f"expected one of {', '.join(LAMP_WATCHDOG_MODES)}")
    wd = LampWatchdog(mode=lamp_watchdog if lamp else "off")
    if not lamp and lamp_watchdog != "off":
        wd.note = ("the lamp is deliberately off for this run, so nothing was "
                   "sent to the illuminators")
    res = ScanResult(path=str(out_path), config=cfg.to_json())

    g = gate.Gate.from_calibration()
    # With the lamp deliberately off every window is DARK by definition and
    # there is no lamp failure left to detect, so the DARK stop would end the
    # experiment in half a second. Classification still reports DARK; only the
    # stop is withheld, and the hard time limit becomes the sole bound.
    det = gate.RunDetector(dark_stops=bool(lamp))
    log("gate", **g.describe())

    if not dry_run and not _simulating() and LOCK_FILE.is_file():
        raise ScanRefused(
            f"the write interlock is engaged ({LOCK_FILE}). A scan writes the "
            f"lamp, CCD and transport registers. Lift it deliberately, as "
            f"tools/WRITES_LOCKED describes, or scan from a capture instead.")

    out = Path(out_path)
    if not dry_run:
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            raise ScanRefused(
                f"{out} already exists. A scan is not repeatable — the film "
                f"passes the sensor once — so this will not overwrite one.")

    link = Link.open(dry_run=dry_run, log=log)
    health = LampHealth()
    # Exists whether or not the DX poll runs. With no DX reader it simply never
    # has an opinion, and every decision falls back to the optical detector.
    film = FilmSense()
    started_motor = False
    fh = None
    dx = None
    try:
        marker_write({
            "path": str(out),
            "max_seconds": max_seconds,
            # Recorded BEFORE the 0x98 is sent, and from the mode rather than
            # from the result, for the same reason `lamp_watchdog_disarm` sets
            # its flag before the packet: this file exists precisely for the
            # case where this process does not survive to correct it, and a
            # 0x98 whose acknowledgement was lost still disarmed the board.
            "dx_auto_off_disarmed": bool(lamp) and wd.mode in ("auto", "command"),
            "lamp_watchdog_mode": wd.mode,
        })
        log("phase", phase="connecting", message="clearing FX2 fault state")
        link.clear_fault()

        if not lamp:
            log("warn", message="LAMP OFF: this is the DX-without-the-lamp "
                                "experiment. The capture will be black and "
                                "the DARK stop is suppressed.")
        else:
            log("phase", phase="lamp", message="light board thresholds")
            lamp_init_thresholds(link)
            lamp_on(link, cfg)

            # The decoded mechanism, sent once before the film moves. Best
            # effort: a board that will not take it costs us one rejected
            # packet and we carry on with the refresh, which is the mechanism
            # that has actually been measured working.
            if wd.mode in ("auto", "command"):
                wd.send(link)
                log("lamp_watchdog", **wd.to_json())

            # Warm-up, then a health poll BEFORE any film moves. If the lamp is
            # not healthy now, nothing else should happen at all.
            log("phase", phase="lamp", message=f"settling {LAMP_WARMUP_S:.0f} s")
            t_warm = time.time()
            warm = 0.2 if (dry_run or _simulating()) else LAMP_WARMUP_S
            while time.time() - t_warm < warm:
                if cancel:
                    raise ScanAborted(cancel.reason or "cancelled")
                time.sleep(0.1)
            if not skip_lamp_health:
                poll_lamp(link, health)
                log("lamp", **health.to_json())
                if not health.ok:
                    raise ScanAborted(f"lamp is not healthy before the scan: "
                                      f"{health.fault}")

        log("phase", phase="sensor", message="CCD geometry and A/D")
        ccd_configure(link, cfg)

        log("phase", phase="sensor", message="transport speed")
        speed = clamp_speed(cfg.speed)
        link.ack(pc.set_motor_speed(speed), f"transport speed {speed}")
        # PPB_START_DX_SCAN. The calibration record calls 0x91 the "line rate";
        # docs/53 s1.1 identifies it as the DX scan start, payload
        # [speed u16][format u8]. Both are true of the same write, and it is
        # part of the triad the committed tables were captured at, so it is
        # sent at the recorded value and is not a setting.
        link.ack(pc.dx_start(int(cfg.line_rate_0x91), pc.DX_FORMAT_DEFAULT),
                 f"0x91 DX/line rate {cfg.line_rate_0x91}", required=False)

        # The DX reader has been running on every scan this project has ever
        # made; nothing has ever read its events back. This does. Reads only —
        # it cannot abort the scan and cannot move anything.
        if read_dx and not dry_run:
            try:
                dx = dxr.DxReader(
                    link.xfer,
                    log_path=(dx_log if dx_log is not None
                              else out.with_suffix(".dx.jsonl")),
                    interval=dxr.DEFAULT_INTERVAL_S,
                    meta={"capture": str(out), "speed": speed,
                          "dpi_base": cfg.dpi_base, "lamp": bool(lamp),
                          "line_rate_0x91": cfg.line_rate_0x91})
                res.dx_log = str(dx_log if dx_log is not None
                                 else out.with_suffix(".dx.jsonl"))
                log("phase", phase="dx",
                    message=f"DX poll armed, logging to {res.dx_log}")
            except OSError as e:
                dx = None
                log("warn", message=f"DX log could not be opened: {e}")

        # Twice here, never again. docs/45.
        reset_fifos(link)
        reset_fifos(link)

        log("phase", phase="acquire", message="arming the sensor")
        acquire(link, True)

        if cancel:
            raise ScanAborted(cancel.reason or "cancelled")

        if not dry_run:
            fh = out.open("wb")
        log("phase", phase="transport", message=f"starting transport at {speed}")
        # BEFORE the acknowledgement, not after. `ack(required=True)` raises
        # ScanAborted when the reply is lost or refused, but the board acts on
        # a command when it receives it: a lost acknowledgement is not evidence
        # that the transport did not start. Setting the flag afterwards meant
        # that on exactly that failure the abort unwound, safe_stop's own
        # retries also failed, and the finally then read `not started_motor`
        # and cleared the marker -- motor possibly running, stop failed, and
        # nothing left to tell the next process. The flag records that the
        # command went out, which is the thing the marker is about.
        started_motor = True
        link.ack(pc.motor_forward(), f"TRANSPORT FORWARD at {speed}")

        # ---------------- the capture loop ----------------
        t0 = time.time()
        deadline = t0 + max_seconds
        next_lamp = t0 + LAMP_POLL_S
        refresh_every = max(0.0, float(lamp_refresh_s)) if lamp else 0.0
        # The periodic tick exists if *either* mechanism wants it: the register
        # refresh, or `command` mode's repeat of 0x98. `--lamp-refresh-mode off`
        # with `--lamp-watchdog command` is a legitimate combination — it is the
        # narrowest test of the decoded mechanism there is.
        do_refresh = lamp_refresh_mode != "off" and wd.refresh_still_needed
        wants_tick = bool(refresh_every) and (do_refresh or wd.mode == "command")
        next_refresh = (t0 + refresh_every) if wants_tick else None
        refreshes = 0
        refresh_fails = 0
        last_data = t0
        buf = bytearray()
        phase = None
        need = gate.WINDOW_LINES * gate.BYTES_PER_LINE + gate.BYTES_PER_LINE
        total = 0
        stop_reason = ""
        stop_detail = ""

        while True:
            now = time.time()

            if cancel:
                stop_reason, stop_detail = "cancelled", cancel.reason
                break
            if now >= deadline:
                stop_reason = "time_limit"
                stop_detail = (f"the {max_seconds:.0f} s limit was reached. "
                               f"This is the backstop, not a detector.")
                break
            if total >= max_bytes:
                stop_reason = "size_limit"
                stop_detail = f"{total} bytes written, cap {max_bytes}"
                break

            if next_refresh is not None and now >= next_refresh:
                next_refresh = now + refresh_every
                # In `command` mode the periodic kick is 0x98 itself rather
                # than the register triple: it is idempotent, it is one packet
                # instead of three, and re-sending it covers a board that reset
                # and re-armed its own timer. The moment the board declines it,
                # `wd.send` flips `fell_back` and the triple takes over below —
                # for the rest of the run, not just this tick.
                if wd.mode == "command" and not wd.fell_back:
                    wd.send(link)
                    log("lamp_watchdog", elapsed=round(now - t0, 2),
                        **wd.to_json())
                if lamp_refresh_mode != "off" and wd.refresh_still_needed:
                    if lamp_refresh(link, cfg, lamp_refresh_mode):
                        refreshes += 1
                    else:
                        refresh_fails += 1
                    log("lamp_refresh", mode=lamp_refresh_mode,
                        count=refreshes, failures=refresh_fails,
                        elapsed=round(now - t0, 2))

            if not skip_lamp_health and now >= next_lamp:
                next_lamp = now + LAMP_POLL_S
                poll_lamp(link, health)
                log("lamp", **health.to_json())
                if not health.ok:
                    stop_reason, stop_detail = "lamp_fault", health.fault
                    break

            if dry_run:
                stop_reason, stop_detail = "dry_run", "nothing was captured"
                break

            # DX events, between image reads. Reads only, rate-limited by the
            # reader itself, and wrapped because a DX fault must never be able
            # to stop a scan that is otherwise fine.
            #
            # The packet is no longer thrown away: its status nibble is the
            # machine's own answer to "is there film in the transport", which
            # is the signal the optical detector has twice got wrong.
            if dx is not None:
                try:
                    ended = film.feed(dx.poll_if_due(), now)
                except Exception as e:                      # noqa: BLE001
                    log("warn", message=f"DX poll failed, disabling: {e}")
                    dx.note(f"disabled after {e}")
                    dx = None
                    ended = None
                for level, text in film.drain():
                    log(level, message=text)
                if ended:
                    stop_reason, stop_detail = "roll_end", ended
                    break

            data = link.read_image(CHUNK)
            if data:
                fh.write(data)
                total += len(data)
                buf += data
                last_data = now
            elif now - last_data > STALL_LIMIT_S:
                stop_reason = "stalled"
                stop_detail = (f"no image data for {now - last_data:.1f} s. "
                               f"The sensor stopped delivering while the "
                               f"transport was running.")
                break

            if phase is None and len(buf) >= 4 * gate.BYTES_PER_LINE:
                phase = gate.find_phase(buf[: 8 * gate.BYTES_PER_LINE])
            if phase is None or len(buf) < need:
                continue

            lines, consumed, n, brk = gate.split_lines(buf, phase)
            if consumed:
                del buf[:consumed]
                phase = 0
            res.sync_breaks += brk
            if n == 0:
                continue
            for a in range(0, n, gate.WINDOW_LINES):
                blk = lines[a:a + gate.WINDOW_LINES]
                if blk.shape[0] < gate.WINDOW_LINES // 2:
                    break
                v = g.classify_lines(blk, sync_breaks=brk)
                res.windows += 1
                res.lines += v.lines
                st = det.feed(v)
                # Both dicts carry `state` and `lines`, so they are nested
                # rather than merged.
                log("window", window=v.to_json(), run=st.to_json(),
                    bytes=total, elapsed=round(now - t0, 2))
                if st.stop == gate.STOP_DARK and not lamp:
                    # Deliberate darkness. The whole point of the run.
                    st.stop = None
                    st.stop_detail = ""
                # The gate looks clear but the machine says film is still in
                # the transport. That combination is the leader, a long blank
                # run or a clear stock -- not the end of the roll. This is the
                # corroboration step, and it is the one that stops us ending a
                # scan on the leader again.
                vetoed = film.veto(st, now)
                if vetoed:
                    log("warn", message=vetoed)
                if st.stop:
                    stop_reason = st.stop
                    stop_detail = st.stop_detail
                    break
            if stop_reason:
                break

        res.seconds = round(time.time() - t0, 3)
        res.bytes = total
        res.reason = stop_reason or "ended"
        res.detail = stop_detail
        res.mib_s = round((total / (1024 * 1024)) / max(res.seconds, 1e-6), 2)
        res.ok = stop_reason in ("roll_end", "cancelled", "time_limit", "dry_run")
        res.lamp_refresh = {
            "mode": lamp_refresh_mode if lamp else "off (lamp not lit)",
            "every_s": refresh_every,
            "count": refreshes,
            "failures": refresh_fails,
            "superseded_by_0x98": (wd.mode == "command" and not wd.fell_back),
        }
        res.lamp_watchdog = wd.to_json()
        res.dark_stop_suppressed = not lamp
    except ScanAborted as e:
        res.reason = res.reason or "aborted"
        res.detail = res.detail or str(e)
        log("abort", message=str(e))
    finally:
        # Unconditional. This is the whole point of the module.
        try:
            res.stopped = safe_stop(link, log=log)
        except Exception as e:                              # noqa: BLE001
            res.stopped = {"motor": False, "errors": [str(e)]}
        if dx is not None:
            try:
                # Drain whatever the DX board queued between the last poll and
                # the stop. A packet carries 4 to 9 events depending on their
                # types (27 bytes of budget, records of 3 to 6), so three reads
                # clear a full queue.
                # Reads only, and the link is still open at this point.
                dx.interval = 0.0
                for _ in range(3):
                    dx.poll()
                res.dx = dx.close()
                log("dx", **res.dx)
            except Exception as e:                          # noqa: BLE001
                log("warn", message=f"DX summary failed: {e}")
        if fh is not None:
            try:
                fh.flush()
                os.fsync(fh.fileno())
                fh.close()
            except OSError:
                pass
        link.close()
        # BEFORE write_capture_metadata, not after. These were assembled at the
        # bottom of the finally, which meant the sidecar's "lamp" block was
        # written from a ScanResult that had not been filled in yet and came
        # out empty on every scan taken so far.
        res.lamp = health.to_json()
        res.run = det.s.to_json()
        # In the finally rather than after the loop, so a scan that aborted
        # during warm-up still records what the sensors said.
        res.film_sense = film.to_json()
        res.film_sense["ended_by"] = (
            "film sensors" if film.ended else
            "optical detector" if res.reason == "roll_end" else
            res.reason or "not the end of a roll")
        if not dry_run and started_motor:
            # After the fsync above, so the sidecar can never describe a file
            # that is still being written. Written even on an abort: a scan cut
            # short still produced a capture, and it is still the only record of
            # the speed it was taken at.
            res.metadata = write_capture_metadata(out, cfg, res, g.describe())
        # Nothing was ever commanded to move, or nothing was ever sent at all.
        if dry_run or not started_motor:
            marker_clear()
        elif marker_clear_if_stopped(res.stopped):
            pass
        else:
            log("warn", message="the transport stop was NOT acknowledged; "
                                "leaving the in-flight marker so the next "
                                "process retries it")
        if dry_run:
            res.packets = list(link.sent)
    return res


# --------------------------------------------------------------------------
# probing, without writing anything
# --------------------------------------------------------------------------

def probe() -> dict:
    """What can be said about the machine without sending it a write."""
    out: dict = {
        "writes_locked": LOCK_FILE.is_file(),
        "lock_path": str(LOCK_FILE),
        "marker": str(MARKER),
        "in_flight": MARKER.is_file(),
        "present": False,
        "state": "absent",
        "lamp": None,
        "hint": "",
        "simulated": None,
        "speeds": MOTOR_SPEED,
        "decodable_bases": list(DECODABLE_BASES),
    }
    try:
        out["calibration"] = ScanConfig.from_calibration().to_json()
    except Exception as e:                                  # noqa: BLE001
        out["calibration"] = None
        out["calibration_error"] = str(e)
    try:
        out["gate"] = gate.Gate.from_calibration().describe()
    except Exception as e:                                  # noqa: BLE001
        out["gate"] = None
        out["gate_error"] = str(e)

    # A simulated scanner is a scanner as far as every caller of this function
    # is concerned, and saying so here is what lets the application's own
    # scanner-present path be exercised end to end with no hardware on the
    # bus. It is reported as `simulated` rather than passed off as real: the
    # UI shows the distinction, because a run against a replayed capture
    # proves the software and proves nothing at all about the machine.
    sim = _simulating()
    if sim:
        out.update(present=True, state="ready", simulated=sim,
                   hint=f"Simulated scanner replaying {Path(sim).name}. "
                        f"Nothing is open on USB and nothing can move.")
    else:
        try:
            import usb.core
        except ImportError:
            out["hint"] = "pyusb is not installed (pip install pyusb)"
            return out

        try:
            loaded = usb.core.find(idVendor=VID, idProduct=PID)
            unloaded = (usb.core.find(idVendor=0x04B4, idProduct=0x8613)
                        or usb.core.find(idVendor=0x0F05, idProduct=0xF235))
        except Exception as e:                              # noqa: BLE001
            out["hint"] = f"USB probe failed: {e}"
            return out

        if loaded is None:
            if unloaded is not None:
                out.update(present=True, state="needs_firmware",
                           hint="Scanner present, firmware not loaded. Run "
                                "tools/pakon_load.py.")
            else:
                out["hint"] = ("No scanner on USB. Open an existing capture "
                               "instead — everything downstream works "
                               "offline.")
            return out
        out.update(present=True, state="ready")

    link = None
    try:
        link = Link.open()
        link.clear_fault()
        h = poll_lamp(link, LampHealth())
        out["lamp"] = h.to_json()
        if not sim:
            out["hint"] = "Scanner is loaded and answering."
    except Exception as e:                                  # noqa: BLE001
        out["hint"] = f"scanner present but not answering: {e}"
        out["state"] = "error"
    finally:
        if link is not None:
            link.close()
    if out["writes_locked"]:
        out["hint"] += (" The write interlock is engaged, so a scan will "
                        "refuse to start.")
    return out


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

_JSON_OUT = False


def _emit(kind: str, **kw) -> None:
    """One NDJSON record per event on stdout, for the parent process.

    Silent unless ``--json``, so that the human-readable result stays parseable
    as a single document.
    """
    if not _JSON_OUT:
        return
    try:
        sys.stdout.write(json.dumps({"t": kind, **kw}) + "\n")
        sys.stdout.flush()
    except (OSError, ValueError):
        pass


def cmd_run(a) -> int:
    global _JSON_OUT
    _JSON_OUT = bool(a.json)
    cancel = Cancel()

    def on_signal(sig, _frm):
        cancel.set(f"signal {signal.Signals(sig).name}")
    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        try:
            signal.signal(s, on_signal)
        except (ValueError, OSError):
            pass

    if a.watch_parent:
        threading.Thread(target=watch_parent, args=(cancel,), daemon=True).start()

    try:
        cfg = ScanConfig.from_calibration(dpi_base=a.base, speed=a.speed)
    except Exception as e:                                  # noqa: BLE001
        _emit("error", message=str(e))
        print(f"refused: {e}", file=sys.stderr)
        return 2
    for w in cfg.warnings:
        _emit("warn", message=w)
        print(f"warning: {w}", file=sys.stderr)
    if cfg.warnings and not a.force:
        msg = ("refusing: the requested configuration does not match the "
               "committed calibration (see warnings). --force to override.")
        _emit("error", message=msg)
        print(msg, file=sys.stderr)
        return 2

    out = Path(a.output) if a.output else (
        DEFAULT_OUT_DIR / time.strftime("scan-%Y%m%d-%H%M%S.bin"))
    try:
        res = run_scan(out, cfg, max_seconds=a.max_seconds,
                       max_bytes=a.max_bytes, cancel=cancel,
                       log=_emit if a.json else (lambda *x, **k: None),
                       dry_run=a.dry_run,
                       skip_lamp_health=a.no_lamp_health or a.no_lamp,
                       read_dx=not a.no_dx,
                       dx_log=a.dx_log,
                       lamp=not a.no_lamp,
                       lamp_refresh_s=a.lamp_refresh,
                       lamp_refresh_mode=a.lamp_refresh_mode,
                       lamp_watchdog=a.lamp_watchdog)
    except ScanRefused as e:
        _emit("error", message=str(e))
        print(f"refused: {e}", file=sys.stderr)
        return 2
    except Exception as e:                                  # noqa: BLE001
        _emit("error", message=f"{e.__class__.__name__}: {e}")
        print(f"error: {e}", file=sys.stderr)
        # Nothing here is trusted to have stopped the transport, so try again
        # from a clean handle before giving up.
        _emit("stop", **emergency_stop())
        return 1

    _emit("done", **res.to_json())
    if a.dry_run:
        print("the packets this scan would send, in order:", file=sys.stderr)
        for i, p in enumerate(res.packets, 1):
            print(f"  {i:>3}  {p}", file=sys.stderr)
        print(f"  ({len(res.packets)} packets; nothing was sent)",
              file=sys.stderr)
    elif res.path and not a.dry_run:
        # The capture sidecar is written by run_scan's finally (see
        # write_capture_metadata) so that it exists on aborts too. It used to be
        # written again here, which meant two files describing one capture and
        # a decode reading whichever it found first.
        if res.metadata and not a.json:
            print(f"wrote sidecar {res.metadata}", file=sys.stderr)
        # The DX result on its own, next to the capture, so the app can pick a
        # film stock without parsing the whole scan record.
        try:
            if res.dx:
                dxside = Path(res.path).with_suffix(".dx.json")
                stock = dxr.film_stock(res.dx.get("product"),
                                       res.dx.get("specifier"))
                dxside.write_text(json.dumps(
                    {"capture": res.path, "log": res.dx_log,
                     "summary": res.dx, "film_stock": stock},
                    indent=2, default=str) + "\n")
                if not a.json:
                    print(f"wrote DX sidecar {dxside}", file=sys.stderr)
        except (OSError, TypeError, ValueError) as e:
            print(f"warning: could not write .dx.json sidecar: {e}",
                  file=sys.stderr)
    if not a.json:
        # In --json mode the `done` record above already carries all of this,
        # and a second pretty-printed document would break the NDJSON stream.
        print(json.dumps(res.to_json(), indent=2))
    # The exit code is about the machine, not about the photographs.
    #   0  stopped, and the scan ended the way a scan should
    #   3  stopped, but the scan was aborted (dark, lamp fault, stall)
    #   1  THE TRANSPORT STOP WAS NOT CONFIRMED — the only dangerous outcome
    if not (res.stopped.get("motor") or a.dry_run):
        return 1
    return 0 if res.ok else 3


def cmd_stop(_a) -> int:
    out = emergency_stop()
    # Same rule as run_scan's finally and check_stale: a stop that was not
    # acknowledged leaves the marker, so the next process retries it.
    out["marker_cleared"] = marker_clear_if_stopped(out)
    out["retry_pending"] = not out["marker_cleared"]
    print(json.dumps(out, indent=2))
    return 0 if marker_should_clear(out) else 1


def cmd_sensors(a) -> int:
    """The two cheap experiments docs/57 asks for, with no film in the machine.

    Register 0x93 returns the DX board's four live photodiode values and its
    two digital sense inputs (docs/57 s8.3). Reading it repeatedly answers
    "do the digital inputs track film?"; reading it while toggling the
    illuminator bits with command 0x98 answers "are RC1 and RB0 the main lamp,
    the DX emitters, or both?" — which the firmware cannot say, because
    nothing in the image names a pin.

    ``--toggle`` is the only part that writes, and what it writes is the
    illuminator mask and nothing else. It restores both illuminators on the
    way out. NOTE that command 0x98 also disarms the board's 10 s auto-off
    permanently, so after this runs the illuminators will stay in whatever
    state they were left in until something re-arms it — which is why the last
    thing it sends is a deliberate one.
    """
    link = None
    try:
        link = Link.open()
        link.clear_fault()
    except Exception as e:                                  # noqa: BLE001
        print(f"cannot reach the scanner: {e}", file=sys.stderr)
        if link is not None:
            link.close()
        return 2

    def read_sensors() -> list | None:
        r = link.read_reg(pc.AD_LIGHT, pc.REG_DX_SENSORS, pc.DX_SENSORS_LEN)
        return list(r) if r else None

    out: dict = {"register": f"0x{pc.REG_DX_SENSORS:02X}",
                 "layout_note": "four photodiodes then two digital inputs; "
                                "the order within the six is INFERRED "
                                "(docs/57 s8.3 does not spell it out)",
                 "samples": [], "toggle": []}
    try:
        for i in range(max(1, a.samples)):
            v = read_sensors()
            out["samples"].append(v)
            if v is None and i == 0:
                out["error"] = (
                    f"register 0x{pc.REG_DX_SENSORS:02X} did not answer. "
                    f"docs/03 records this light board answering only "
                    f"registers 0 and 1, so this may simply not be exposed.")
                break
            if a.samples > 1:
                time.sleep(max(0.0, a.interval))

        if a.toggle:
            from write_guard import require_writes_unlocked
            require_writes_unlocked(
                "pakon_scan.py sensors --toggle",
                "writes light-board register 0x98, the DX illuminator mask")
            for mask in (pc.DX_ILLUM_OFF, pc.DX_ILLUM_RC1, pc.DX_ILLUM_RB0,
                         pc.DX_ILLUM_BOTH):
                acked = lamp_watchdog_disarm(link, mask)
                time.sleep(0.2)
                out["toggle"].append({"mask": f"0x{mask:02X}",
                                      "acknowledged": acked,
                                      "sensors": read_sensors()})
    finally:
        # Whatever happened, leave the board in the state it boots into.
        try:
            if a.toggle:
                lamp_watchdog_disarm(link, pc.DX_ILLUM_BOTH)
        except Exception:                                   # noqa: BLE001
            pass
        link.close()

    print(json.dumps(out, indent=2))
    return 0 if out.get("samples") and out["samples"][0] is not None else 1


def cmd_status(a) -> int:
    p = probe()
    if a.json:
        print(json.dumps(p, indent=2))
        return 0
    print(f"scanner        {p['state']}  ({p['hint']})")
    print(f"writes locked  {p['writes_locked']}")
    print(f"in flight      {p['in_flight']}  ({p['marker']})")
    if p.get("lamp"):
        L = p["lamp"]
        print(f"lamp           status={L['status_hex']} "
              f"TempLB={L['temp_lb_c']} TempMB={L['temp_mb_c']} ok={L['ok']}")
    if p.get("calibration"):
        c = p["calibration"]
        print(f"exposure       integration={c['integration']} N={c['lamp_n']} "
              f"0x91={c['line_rate_0x91']}  levels={c['levels']} "
              f"on={c['on_counts']}")
        print(f"transport      {c['speed']}  ({c['speed_source']})")
        for w in c.get("warnings") or []:
            print(f"  warning: {w}")
    if p.get("gate"):
        g = p["gate"]
        print(f"gate           dark<={g['dark_hard']}  clear>={g['clear_cut']} "
              f"of swing {g['swing']}")
    return 0


def cmd_check_stale(a) -> int:
    print(json.dumps(check_stale(force=a.force), indent=2))
    return 0


# --------------------------------------------------------------------------
# selftest — the safety machinery, exercised rather than asserted
# --------------------------------------------------------------------------

def _sim_env(trace: Path, capture: Path, rate: float) -> dict:
    e = dict(os.environ)
    e[ENV_SIMULATE] = str(capture)
    e[ENV_TRACE] = str(trace)
    e[ENV_SIM_RATE] = str(rate)
    return e


def _trace_events(trace: Path) -> list[dict]:
    if not trace.is_file():
        return []
    out = []
    for line in trace.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def _stop_after_run(events: list[dict]) -> bool:
    """Did a MOTOR_STOP arrive after the last MOTOR_RUN?"""
    last_run = last_stop = -1
    for i, e in enumerate(events):
        if e.get("kind") == "MOTOR_RUN":
            last_run = i
        elif e.get("kind") == "MOTOR_STOP":
            last_stop = i
    return last_run >= 0 and last_stop > last_run


def _selftest_logic() -> int:
    """The decision logic, offline: no scanner, no capture, no subprocesses.

    Everything here is a rule that decides whether the owner's film keeps
    moving, so each one is executed rather than asserted in a comment.
    """
    fails = 0

    def check(label: str, got, want) -> None:
        nonlocal fails
        if got != want:
            print(f"  FAIL {label}: got {got!r}, want {want!r}")
            fails += 1

    def pkt(status: int, records: int = 1):
        """A DX packet whose first record carries `status`, or an empty one."""
        b0, b1, b2 = dxd.encode_dx_full(96, 1, 3)
        recs = [dxd.encode_record(dxd.EventType.DX_CODE_FULL,
                                  bytes([b0, b1, b2]), flags=status)
                for _ in range(min(records, 1))]
        recs += [dxd.encode_record(dxd.EventType.PERF_LEADING, bytes([0, i]))
                 for i in range(records - 1)]
        return dxd.DxStream().feed(dxd.encode_packet(100, recs))

    PRESENT = dxd.DXSTAT_FILM_SENSE
    ENTRY_ONLY = dxd.DXSTAT_FILM_SENSE_ENTRY

    # An empty packet says nothing. It must not arm, and must not end a roll.
    f = FilmSense()
    check("empty packet does not arm", f.feed(pkt(0, records=0), 0.0), None)
    check("...and leaves no reading", f.packets, 0)
    check("...so it cannot veto", f.vetoes_roll_end(0.0), False)

    # Clear before any film has been seen is the empty transport, not the end
    # of a roll. This is the "stopped on the leader" failure in miniature.
    f = FilmSense()
    for t in range(0, 20):
        check(f"clear at t={t} before film never ends a roll",
              f.feed(pkt(0x00), float(t)), None)
    check("never armed", f.armed, False)

    # Film sensed, then sustained clear, ends the roll -- but not before
    # FILM_SENSE_CLEAR_S has actually elapsed.
    f = FilmSense()
    f.feed(pkt(PRESENT), 0.0)
    check("armed by a film report", f.armed, True)
    check("entry and exit both", (f.at_entry, f.at_exit), (True, True))
    check("still present, no stop", f.feed(pkt(PRESENT), 1.0), None)
    check("clear starts the clock", f.feed(pkt(0x00), 2.0), None)
    check("under the hold time", f.feed(pkt(0x00), 2.0 + FILM_SENSE_CLEAR_S / 2),
          None)
    ended = f.feed(pkt(0x00), 2.0 + FILM_SENSE_CLEAR_S)
    check("held long enough ends the roll", bool(ended), True)
    check("and says so once", f.feed(pkt(0x00), 30.0), None)
    check("ended is recorded", f.ended, True)

    # A single clear packet in the middle of a roll must not end it, and the
    # clock must restart when film comes back.
    f = FilmSense()
    f.feed(pkt(PRESENT), 0.0)
    f.feed(pkt(0x00), 1.0)
    f.feed(pkt(PRESENT), 1.5)
    check("a blip resets the clear clock", f.clear_since, None)
    check("no stop after the blip", f.feed(pkt(0x00), 2.0), None)

    # One sensor is enough to mean film is present.
    f = FilmSense()
    f.feed(pkt(ENTRY_ONLY), 0.0)
    check("entry alone is film present", f.present, True)
    check("and it vetoes", f.vetoes_roll_end(0.0), True)

    # A stale reading decides nothing. A DX board that went quiet with film in
    # the gate must not veto optical roll-ends for the rest of the scan.
    f = FilmSense()
    f.feed(pkt(PRESENT), 100.0)
    check("fresh reading vetoes", f.vetoes_roll_end(100.0 + FILM_SENSE_STALE_S / 2),
          True)
    check("stale reading does not",
          f.vetoes_roll_end(100.0 + FILM_SENSE_STALE_S + 0.1), False)

    # Mis-load bits warn and only warn.
    f = FilmSense()
    stop = f.feed(pkt(PRESENT | dxd.DXSTAT_TAIL_FIRST
                      | dxd.DXSTAT_EMULSION_DOWN), 0.0)
    check("mis-load does not stop a scan", stop, None)
    check("tail first latched", f.tail_first, True)
    check("emulsion down latched", f.emulsion_down, True)
    warned = " ".join(t for _l, t in f.pending)
    check("tail-first is surfaced", "TAIL FIRST" in warned, True)
    check("emulsion-down is surfaced", "EMULSION DOWN" in warned, True)
    f.drain()
    f.feed(pkt(PRESENT | dxd.DXSTAT_TAIL_FIRST), 1.0)
    check("warned once, not every packet", f.drain(), [])

    # The veto, against a real RunState. An optical roll-end is withdrawn while
    # film is sensed; a DARK stop never is; and the clear run is reset so the
    # detector has to earn it again instead of re-firing next window.
    f = FilmSense()
    f.feed(pkt(PRESENT), 0.0)
    st = gate.RunState(stop=gate.STOP_ROLL_END, stop_detail="d", clear_run=9000)
    msg = f.veto(st, 0.0)
    check("optical roll-end withdrawn", st.stop, None)
    check("...detail cleared", st.stop_detail, "")
    check("...clear run reset", st.clear_run, 0)
    check("...counted", f.vetoed_optical, 1)
    check("...and explained", "still report film" in (msg or ""), True)

    dark = gate.RunState(stop=gate.STOP_DARK, stop_detail="lamp", dark_run=9000)
    check("DARK is never vetoed", f.veto(dark, 0.0), None)
    check("...and still stops", dark.stop, gate.STOP_DARK)

    # No film sensed and no reading: the optical detector has the floor.
    quiet = gate.RunState(stop=gate.STOP_ROLL_END, stop_detail="d")
    check("nothing to veto with", FilmSense().veto(quiet, 0.0), None)
    check("...so the optical stop stands", quiet.stop, gate.STOP_ROLL_END)

    # Film sensed but the board has gone quiet: a stale reading cannot veto.
    stale = gate.RunState(stop=gate.STOP_ROLL_END, stop_detail="d")
    check("a stale reading cannot veto",
          f.veto(stale, FILM_SENSE_STALE_S + 1.0), None)
    check("...so the optical stop stands", stale.stop, gate.STOP_ROLL_END)

    # The bits that have been in every sidecar: 0xC0000000 is both sensors.
    p = pkt(PRESENT)
    check("hardware_cb of a film-present packet", p.hardware_cb, 0xC0000000)
    check("...is entry | exit",
          dxd.HARDWARE_CB_FILM_SENSE_ENTRY | dxd.HARDWARE_CB_FILM_SENSE_EXIT,
          0xC0000000)

    # The lamp watchdog modes have to differ in the one way that matters:
    # whether the measured refresh keeps running.
    check("auto keeps refreshing", LampWatchdog(mode="auto").refresh_still_needed,
          True)
    check("refresh keeps refreshing",
          LampWatchdog(mode="refresh").refresh_still_needed, True)
    check("off does nothing", LampWatchdog(mode="off").refresh_still_needed,
          False)
    w = LampWatchdog(mode="command")
    check("command replaces the refresh", w.refresh_still_needed, False)
    w.fell_back = True
    check("...until the board declines 0x98", w.refresh_still_needed, True)

    class _Deaf:
        """A link whose every write is rejected, like a board without 0x98."""
        dx_illuminator_on = False

        def ack(self, _pkt, _label, required=True):
            return b""

    w = LampWatchdog(mode="command")
    check("a rejected 0x98 reports failure", w.send(_Deaf()), False)
    check("...and falls back", w.fell_back, True)
    check("...and says why", "did not acknowledge" in w.note, True)

    class _Live:
        dx_illuminator_on = False

        def ack(self, _pkt, _label, required=True):
            return bytes([0x07, 0x02, pc.AD_LIGHT, 0x00])

    live = _Live()
    w = LampWatchdog(mode="command")
    check("an accepted 0x98 reports success", w.send(live), True)
    check("...does not fall back", w.fell_back, False)
    check("...and marks the link so the stop turns them off again",
          live.dx_illuminator_on, True)

    # ---- the stop reports what happened, not what was attempted ----
    #
    # `lamp_off` used to `return True` without reading the response, so the
    # sidecar, the job record and the UI all stated the lamp was off after a
    # NAK, a timeout or a dead USB handle -- the exact conditions under which
    # `safe_stop` runs. These run the failure rather than trusting the fix.
    ACK = bytes([0x07, 0x02, pc.AD_LIGHT, 0x00])
    NAK = bytes([0x07, 0x02, pc.AD_LIGHT, 0x01])   # "no ack, board absent"

    class _FakeLink:
        """A link whose answer to every packet is scripted."""

        def __init__(self, answer):
            self.answer = answer
            self.sent: list[bytes] = []
            self.dx_illuminator_on = False
            self.ctrl_shadow = 0

        def ack(self, pkt, label, required=True):
            self.sent.append(bytes(pkt))
            r = self.answer(bytes(pkt))
            if required and not acknowledged(r):
                raise ScanAborted(f"{label}: not acknowledged")
            return r or b""

    check("a NAK is not an acknowledgement", acknowledged(NAK), False)
    check("no response at all is not an acknowledgement", acknowledged(None),
          False)
    check("a truncated frame is not an acknowledgement",
          acknowledged(b"\x07\x02"), False)
    check("a type-7 status-0 reply is", acknowledged(ACK), True)

    check("lamp off on a NAKing board reports failure",
          lamp_off(_FakeLink(lambda p: NAK), attempts=2), False)
    check("lamp off through a dead USB handle reports failure",
          lamp_off(_FakeLink(lambda p: None), attempts=2), False)
    check("lamp off on a live board reports success",
          lamp_off(_FakeLink(lambda p: ACK)), True)
    deaf_lamp = _FakeLink(lambda p: NAK)
    lamp_off(deaf_lamp, attempts=3)
    check("...and it retried instead of believing the first try",
          len(deaf_lamp.sent), 3)
    once = _FakeLink(lambda p: ACK)
    lamp_off(once)
    check("an acknowledged lamp off is sent once", len(once.sent), 1)

    dead = safe_stop(_FakeLink(lambda p: NAK))
    check("a stop that reached nothing does not claim the motor stopped",
          dead["motor"], False)
    check("...and does not claim the lamp is off", dead["lamp"], False)
    alive = safe_stop(_FakeLink(lambda p: ACK))
    check("a stop the board acknowledged says so", alive["motor"], True)
    check("...for the lamp too", alive["lamp"], True)

    # ---- the DX auto-off, and the process that did not disarm it ----
    #
    # 0x98 clears the arm bit on receipt, so what we heard back afterwards
    # cannot tell us whether the board is now disarmed. The flag therefore
    # follows the packet, not the reply.
    d = _FakeLink(lambda p: NAK)
    check("a NAKed 0x98 is not an acceptance", lamp_watchdog_disarm(d), False)
    check("...but the disarm is recorded, because the board acted on receipt",
          d.dx_illuminator_on, True)
    d = _FakeLink(lambda p: None)
    lamp_watchdog_disarm(d)
    check("a 0x98 whose reply was lost still records the disarm",
          d.dx_illuminator_on, True)
    d = _FakeLink(lambda p: ACK)
    lamp_watchdog_disarm(d)
    check("an accepted 0x98 records it too", d.dx_illuminator_on, True)
    check("...and an acknowledged off-mask clears it",
          (lamp_watchdog_disarm(d, pc.DX_ILLUM_OFF), d.dx_illuminator_on),
          (True, False))
    d = _FakeLink(lambda p: NAK)
    d.dx_illuminator_on = True
    lamp_watchdog_disarm(d, pc.DX_ILLUM_OFF)
    check("an off-mask that was not acknowledged leaves it set, so the next "
          "stop tries again", d.dx_illuminator_on, True)

    # A recovery process opens a fresh Link, so `dx_illuminator_on` is False
    # there whatever the dead process did, and the marker cannot tell it
    # either. It sends the off-mask regardless; the scanning process, which
    # knows, still only sends it when it applies.
    OFF98 = pc.dx_illuminator(pc.DX_ILLUM_OFF)
    own = _FakeLink(lambda p: ACK)
    safe_stop(own)
    check("a stop by the process that disarmed nothing sends no off-mask",
          OFF98 in own.sent, False)
    recovery = _FakeLink(lambda p: ACK)
    safe_stop(recovery, dx_illuminators=True)
    check("a recovery stop sends the 0x98 off-mask on a link that never "
          "disarmed anything", OFF98 in recovery.sent, True)

    # ---- the marker survives a stop that did not work ----
    #
    # check_stale, `pakon_scan.py stop` and the app's post-mortem all used to
    # delete the marker unconditionally, so a recovery that exhausted its six
    # attempts and stopped nothing left no reason for anything to try again.
    check("an acknowledged stop releases the marker",
          marker_should_clear({"motor": True, "lamp": True}), True)
    check("a stop that reached nothing keeps it",
          marker_should_clear({"motor": False, "lamp": False,
                               "errors": ["could not open the scanner"]}),
          False)
    check("...even when the lamp went off",
          marker_should_clear({"motor": False, "lamp": True}), False)
    check("a scanner that is not on the bus releases it, or it is retried "
          "forever", marker_should_clear({"motor": False, "absent": True}),
          True)

    # The decoded interval, end to end through pakon_commands.
    check("watchdog is ten seconds", round(pc.DX_WATCHDOG_S, 3), 10.0)
    check("0x98 both on", pc.dx_illuminator().hex(" "), "02 04 40 01 98 03")
    check("0x98 all off", pc.dx_illuminator(pc.DX_ILLUM_OFF).hex(" "),
          "02 04 40 01 98 00")

    print(f"  {'decision-logic':<22} {'ok   ' if not fails else 'FAIL '} "
          f"film sensing, the roll-end veto, the mis-load warnings and the "
          f"0x98 fallback, offline")
    print("      no scanner, no capture and no subprocess — these are the "
          "rules that decide whether the film keeps moving")
    return fails


def cmd_selftest(a) -> int:
    """Run the dangerous exit paths for real, against a simulated scanner.

    Every case here is a way the last seven-minute run could have been cut
    short and was not. They are executed as separate processes, killed the way
    a user or an operating system would kill them, and judged on what the
    scanner actually received — not on what this module believes it sent.
    """
    import subprocess
    import tempfile

    capture = Path(a.capture or (_ROOT / "captures" / "roll.bin"))
    if not capture.is_file():
        print(f"selftest needs a capture to replay; {capture} is not here",
              file=sys.stderr)
        return 2
    tmp = Path(tempfile.mkdtemp(prefix="pakon-scan-selftest-"))
    ok = True
    marker_backup = None
    if MARKER.is_file():
        marker_backup = MARKER.read_text()

    def run_case(name: str, why: str, rate: float, args: list[str],
                 kill_after: float | None = None, kill_sig=signal.SIGTERM,
                 close_stdin_after: float | None = None,
                 expect_stop: bool = True, expect_reason: str | None = None,
                 extra_env: dict | None = None,
                 expect_in_detail: str | None = None):
        nonlocal ok
        trace = tmp / f"{name}.ndjson"
        out = tmp / f"{name}.bin"
        env = _sim_env(trace, capture, rate)
        env.update(extra_env or {})
        cmd = [sys.executable, str(_TOOLS / "pakon_scan.py"), "run",
               str(out), "--json"] + args
        t0 = time.time()
        p = subprocess.Popen(cmd, env=env, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        killed_at = None
        try:
            if close_stdin_after is not None:
                time.sleep(close_stdin_after)
                p.stdin.close()
                p.stdin = None          # communicate() must not flush it again
                killed_at = time.time()
            if kill_after is not None:
                time.sleep(kill_after)
                p.send_signal(kill_sig)
                killed_at = time.time()
            sout, _serr = p.communicate(timeout=90)
        except subprocess.TimeoutExpired:
            p.kill()
            sout, _serr = p.communicate()
            print(f"  {name:<22} FAIL: did not exit within 90 s")
            ok = False
            return
        finally:
            try:
                if p.stdin and not p.stdin.closed:
                    p.stdin.close()
            except (OSError, ValueError):
                pass

        # A SIGKILLed scan cannot stop anything itself. The parent has to, and
        # that is the whole point of the exercise: do it here exactly as
        # pakon_app does it.
        recovered = False
        events = _trace_events(trace)
        if not _stop_after_run(events) and expect_stop:
            env2 = _sim_env(trace, capture, rate)
            subprocess.run([sys.executable, str(_TOOLS / "pakon_scan.py"),
                            "stop"], env=env2, capture_output=True, timeout=30)
            events = _trace_events(trace)
            recovered = True

        stopped = _stop_after_run(events)
        elapsed = None
        if killed_at:
            for e in events:
                if e.get("kind") == "MOTOR_STOP" and e.get("at", 0) >= killed_at:
                    elapsed = e["at"] - killed_at
                    break
        reason = None
        detail = ""
        for line in (sout or b"").decode(errors="replace").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(r, dict) and r.get("t") == "done":
                reason = r.get("reason")
                detail = r.get("detail") or ""

        bad = []
        if expect_stop and not stopped:
            bad.append("the transport was never stopped")
        if expect_reason and reason != expect_reason:
            bad.append(f"reason {reason!r}, expected {expect_reason!r}")
        if expect_in_detail and expect_in_detail not in detail:
            bad.append(f"detail {detail!r} does not mention "
                       f"{expect_in_detail!r}")
        if elapsed is not None and elapsed > 1.0:
            bad.append(f"stop took {elapsed:.2f} s, over the 1 s budget")
        tail = (f"stop {'via parent recovery' if recovered else 'by the scan'}"
                + (f" in {elapsed*1000:.0f} ms" if elapsed is not None else "")
                + (f", reason={reason}" if reason else "")
                + f", exit={p.returncode}, {time.time()-t0:.1f} s")
        if bad:
            ok = False
            print(f"  {name:<22} FAIL: {'; '.join(bad)}  ({tail})")
        else:
            print(f"  {name:<22} ok    {tail}")
        print(f"      {why}")

    print("safety selftest — a simulated scanner replaying "
          f"{capture.name}\n")
    if _selftest_logic():
        ok = False
    try:
        run_case("dark-stops",
                 "the regression: the lamp dies 30 % in and the scan stops "
                 "instead of running on", 600e6,
                 ["--max-seconds", "120"], expect_reason="dark")

        run_case("time-limit",
                 "the backstop fires even though the film is fine", 40e6,
                 ["--max-seconds", "6"], expect_reason="time_limit")

        run_case("film-sense-roll-end",
                 "the machine says the film has left the transport, and that "
                 "ends the roll — no inference from image brightness at all",
                 40e6, ["--max-seconds", "60"],
                 extra_env={ENV_SIM_FILM_OUT: "5"},
                 expect_reason="roll_end",
                 expect_in_detail="film sensors have read clear")

        run_case("sigterm",
                 "a polite kill; the finally must reach the motor", 20e6,
                 ["--max-seconds", "120"], kill_after=4.0,
                 kill_sig=signal.SIGTERM, expect_reason="cancelled")

        run_case("sigint",
                 "ctrl-C from a terminal", 20e6,
                 ["--max-seconds", "120"], kill_after=4.0,
                 kill_sig=signal.SIGINT, expect_reason="cancelled")

        run_case("parent-gone",
                 "the application quit or crashed: EOF on the control pipe "
                 "is a cancel", 20e6,
                 ["--max-seconds", "120", "--watch-parent"],
                 close_stdin_after=4.0, expect_reason="cancelled")

        run_case("sigkill",
                 "THE HARD ONE: the scan process is killed outright, so no "
                 "finally runs and the stop has to come from outside", 20e6,
                 ["--max-seconds", "120"], kill_after=4.0,
                 kill_sig=signal.SIGKILL)

        # After a SIGKILL the marker is left behind on purpose. A fresh process
        # must notice and stop the machine without being told.
        trace = tmp / "stale.ndjson"
        marker_write({"path": "selftest", "max_seconds": 1})
        os.environ[ENV_SIMULATE] = str(capture)
        os.environ[ENV_TRACE] = str(trace)
        st = check_stale(force=True)
        ev = _trace_events(trace)
        kinds = {e.get("kind") for e in ev}
        got = "MOTOR_STOP" in kinds
        # The lamp and the DX illuminators, not just the transport. The
        # off-mask is the one the recovery paths never used to send, because
        # `dx_illuminator_on` lives on a Link this process did not have.
        lamp_out = "LAMP_OFF" in kinds
        dx_out = "DX_ILLUM_OFF" in kinds
        good = got and lamp_out and dx_out and st.get("stale")
        print(f"  {'stale-marker':<22} {'ok   ' if good else 'FAIL '} "
              f"a marker left by a killed scan makes the next process stop the "
              f"machine (stale={st.get('stale')}, motor stop={got}, "
              f"lamp off={lamp_out}, DX illuminators off={dx_out})")
        if not good:
            ok = False
        print("      pakon_app calls this at startup, so a crash mid-scan "
              "cannot leave the transport running past the next launch")

        # ...and the other half of that: a recovery that could NOT stop the
        # machine must leave the marker behind. Deleting it there is the one
        # case where nothing ever retries, so it is run rather than reasoned
        # about. The stop is replaced wholesale because the simulated scanner
        # acknowledges everything and there is no hardware to fail against.
        marker_write({"path": "selftest-failed-stop", "max_seconds": 1})
        _real_stop = globals()["emergency_stop"]
        globals()["emergency_stop"] = lambda *a, **k: {
            "motor": False, "lamp": False, "acquire": False, "attempts": 6,
            "errors": ["selftest: the scanner could not be opened to stop it"]}
        try:
            st2 = check_stale(force=True)
        finally:
            globals()["emergency_stop"] = _real_stop
        kept = MARKER.is_file()
        good2 = kept and st2.get("retry_pending") and not st2.get("marker_cleared")
        print(f"  {'failed-stop-retries':<22} {'ok   ' if good2 else 'FAIL '} "
              f"a recovery that stopped nothing leaves the marker for the next "
              f"process (marker kept={kept}, "
              f"retry_pending={st2.get('retry_pending')})")
        if not good2:
            ok = False
        print("      deleting it here was the one failure with no second "
              "chance: transport possibly running, stop failed, marker gone")
        marker_clear()
    finally:
        os.environ.pop(ENV_SIMULATE, None)
        os.environ.pop(ENV_TRACE, None)
        marker_clear()
        if marker_backup is not None:
            MARKER.write_text(marker_backup)
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print("\nSELFTEST " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status", help="probe the machine; sends no writes")
    s.add_argument("--json", action="store_true")

    sub.add_parser("stop", help="panic button: stop the transport and lamp")

    c = sub.add_parser("check-stale", help="stop a scan orphaned by a crash")
    c.add_argument("--force", action="store_true")

    n = sub.add_parser("sensors",
                       help="read the DX board's raw sensors (register 0x93). "
                            "Reads only unless --toggle.")
    n.add_argument("--samples", type=int, default=1)
    n.add_argument("--interval", type=float, default=0.5,
                   help="seconds between samples")
    n.add_argument("--toggle", action="store_true",
                   help="WRITES 0x98: step the illuminator mask through "
                        "off/RC1/RB0/both and sample after each, to find out "
                        "which output is which lamp. Also disarms the board's "
                        "10 s auto-off, permanently.")

    t = sub.add_parser("selftest",
                       help="exercise every stop path against a simulated "
                            "scanner, including SIGKILL")
    t.add_argument("--capture", default=None)

    r = sub.add_parser("run", help="run a scan")
    r.add_argument("output", nargs="?", default=None)
    r.add_argument("--base", type=int, default=16, choices=(4, 8, 16))
    r.add_argument("--speed", type=int, default=None,
                   help="transport speed register 0xA5; defaults to the "
                        "calibrated MotorSpeedPlus for the base")
    r.add_argument("--max-seconds", type=float, default=None,
                   help="hard time limit; default is derived from the "
                        "transport speed and the vendor's 1670 mm roll bound "
                        f"({scan_limits_for(MOTOR_SPEED[16])[0]:.0f} s at base "
                        f"16, {scan_limits_for(MOTOR_SPEED[4])[0]:.0f} s at "
                        f"base 4). Clamped to {MIN_MAX_SECONDS} s .. that "
                        "speed's ceiling")
    r.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    r.add_argument("--dry-run", action="store_true",
                   help="build and print the sequence; send nothing")
    r.add_argument("--json", action="store_true", help="NDJSON progress on stdout")
    r.add_argument("--watch-parent", action="store_true",
                   help="treat EOF on stdin as a cancel (the app uses this)")
    r.add_argument("--force", action="store_true",
                   help="scan even though the configuration does not match "
                        "the committed calibration")
    r.add_argument("--lamp-refresh", type=float, default=LAMP_REFRESH_S,
                   metavar="SECONDS",
                   help="re-assert the lamp drive this often (0 disables). "
                        "The lamp has died at ~60 s twice; the hypothesis is a "
                        "light-board timeout the host is meant to kick.")
    r.add_argument("--lamp-refresh-mode", default="full",
                   choices=LAMP_REFRESH_MODES,
                   help="full = 0x82+0x81+0x80 (default), drive = the vendor's "
                        "own second LampOn, enable = 0x80 only, off = control")
    r.add_argument("--lamp-watchdog", default=LAMP_WATCHDOG_DEFAULT,
                   choices=LAMP_WATCHDOG_MODES,
                   help="what to do about the DX board's decoded "
                        f"{pc.DX_WATCHDOG_S:.0f} s illuminator auto-off "
                        "(docs/57 s6). auto = send 0x98 once AND keep "
                        "refreshing (default); command = send 0x98 instead of "
                        "refreshing, falling back to the refresh if the board "
                        "declines it; refresh = never send 0x98; off = neither")
    r.add_argument("--no-lamp-health", action="store_true",
                   help="do not poll the lamp. Only for bench work; this is "
                        "the check the overnight failure needed.")
    r.add_argument("--no-dx", action="store_true",
                   help="do not poll the DX board. The poll is reads only and "
                        "on by default.")
    r.add_argument("--dx-log", default=None,
                   help="where to write the raw DX log "
                        "(default: <output>.dx.jsonl)")
    r.add_argument("--no-lamp", action="store_true",
                   help="EXPERIMENT ONLY: run the transport with the lamp "
                        "off, to find out whether the DX board needs it. The "
                        "capture will be black and the DARK stop is "
                        "suppressed, so keep --max-seconds short.")

    a = ap.parse_args()
    return {"status": cmd_status, "stop": cmd_stop, "run": cmd_run,
            "check-stale": cmd_check_stale, "selftest": cmd_selftest,
            "sensors": cmd_sensors}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
