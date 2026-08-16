#!/usr/bin/env python3
"""Self-tests for the manual film-jog endpoint (`POST /api/app/motor`). No
scanner needed -- this is the "before you ever point it at real film" gate
for tools/pakon_app.py's `motor_jog`.

Run:  python3 tools/test_motor_jog.py

Real film moves in response to this endpoint, so what matters most is not
that a nudge works but that it CANNOT become unbounded: every path here
either sends a clamped, time-boxed command to tools/spin_motor.py or refuses
outright, and never touches the subprocess machinery when it refuses. That
last part is checked directly -- `subprocess.Popen` is monkeypatched to
raise, so any test that reaches it fails loudly instead of quietly passing.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest import mock

HERE = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(HERE))

import pakon_app as app          # noqa: E402

_fails: list[str] = []
_count = 0


def check(cond, label: str, detail: str = "") -> None:
    global _count
    _count += 1
    if cond:
        print(f"  ok    {label}")
    else:
        print(f"  FAIL  {label}   {detail}")
        _fails.append(label)


def section(name: str) -> None:
    print(f"\n{name}")


class _NoPopen:
    """Stands in for subprocess.Popen: any call is a test failure, since the
    tests that install this are exactly the ones asserting the motor is never
    reached at all."""

    def __call__(self, *a, **k):
        raise AssertionError(f"subprocess.Popen must not be called here: "
                              f"args={a} kwargs={k}")


def _ready_hw(**over):
    hw = {"present": True, "state": "ready", "simulated": None}
    hw.update(over)
    return hw


def _patched(**over):
    """Context manager stack: SCAN idle, no foreign scan, hardware ready,
    unless overridden. Every test uses this so the only thing that varies is
    the one fact under test."""
    hw = _ready_hw(**over.pop("hw", {}))
    return mock.patch.multiple(
        app,
        hardware_state=mock.Mock(return_value=hw),
        foreign_scan=mock.Mock(return_value=over.get("foreign", None)),
        **{},
    )


# --------------------------------------------------------------------------

def test_direction_validated_before_anything_else() -> None:
    section("direction is validated before any hardware is touched")
    with mock.patch.object(app.subprocess, "Popen", _NoPopen()), \
         mock.patch.object(app.SCAN, "running", return_value=False), \
         mock.patch.object(app, "foreign_scan", return_value=None), \
         mock.patch.object(app, "hardware_state", return_value=_ready_hw()):
        for bad in ("", "up", "backward", None, 123):
            r = app.motor_jog({"direction": bad})
            check(r["ok"] is False and "direction" in r.get("error", ""),
                  f"direction={bad!r} is refused", r)
        for good in ("forward", "reverse", "Forward", " REVERSE "):
            # These reach the clamp/refusal logic further down, not Popen —
            # confirmed by the fact none of them raise AssertionError.
            r = app.motor_jog({"direction": good, "seconds": 0})
            check("direction" not in r.get("error", ""),
                  f"direction={good!r} is accepted and normalised", r)


def test_seconds_are_clamped_to_the_short_cap_by_default() -> None:
    section("seconds: clamped to JOG_MAX_SECONDS unless long=True")
    calls = []

    def fake_popen(cmd, **kw):
        calls.append(cmd)
        p = mock.Mock()
        p.communicate.return_value = ("", "")
        p.returncode = 0
        p.poll.return_value = 0
        return p

    with mock.patch.object(app.subprocess, "Popen", side_effect=fake_popen), \
         mock.patch.object(app.SCAN, "running", return_value=False), \
         mock.patch.object(app, "foreign_scan", return_value=None), \
         mock.patch.object(app, "hardware_state", return_value=_ready_hw()), \
         mock.patch.object(app.cwiz, "film_precheck",
                           side_effect=RuntimeError("no link in this test")):
        r = app.motor_jog({"direction": "forward", "seconds": 9999})
        check(r["seconds"] == app.JOG_MAX_SECONDS,
              f"seconds=9999 without long clamps to {app.JOG_MAX_SECONDS}",
              r["seconds"])
        check("--seconds" in calls[-1] and
              calls[-1][calls[-1].index("--seconds") + 1] ==
              str(app.JOG_MAX_SECONDS),
              "the clamped value, not the requested one, reaches spin_motor.py")

        r = app.motor_jog({"direction": "forward", "seconds": 9999,
                           "long": True})
        check(r["seconds"] == app.JOG_MAX_SECONDS_LONG,
              f"seconds=9999 with long=True clamps to "
              f"{app.JOG_MAX_SECONDS_LONG}, not further", r["seconds"])

        r = app.motor_jog({"direction": "forward", "seconds": -5})
        check(r["seconds"] == 0.1,
              "a negative or zero request floors to 0.1s, never 0 or below",
              r["seconds"])

        r = app.motor_jog({"direction": "forward", "seconds": "not a number"})
        check(r["seconds"] == app.JOG_DEFAULT_SECONDS,
              "an unparsable seconds value falls back to the default, "
              "not an exception", r["seconds"])

        # The concrete, real-world number this feature is meant to send: a
        # single short discrete pulse, well under the hard cap.
        r = app.motor_jog({"direction": "forward", "seconds": 0.4})
        check(r["seconds"] == 0.4 and r["ok"] is True,
              "a 400ms pulse (this feature's actual UI request) passes "
              "through unclamped and succeeds", r)


def test_speed_is_clamped_to_the_documented_legal_range() -> None:
    section("speed: clamped to [JOG_SPEED_MIN, JOG_SPEED_MAX]")
    calls = []

    def fake_popen(cmd, **kw):
        calls.append(cmd)
        p = mock.Mock()
        p.communicate.return_value = ("", "")
        p.returncode = 0
        p.poll.return_value = 0
        return p

    with mock.patch.object(app.subprocess, "Popen", side_effect=fake_popen), \
         mock.patch.object(app.SCAN, "running", return_value=False), \
         mock.patch.object(app, "foreign_scan", return_value=None), \
         mock.patch.object(app, "hardware_state", return_value=_ready_hw()), \
         mock.patch.object(app.cwiz, "film_precheck",
                           side_effect=RuntimeError("no link in this test")):
        r = app.motor_jog({"direction": "forward", "speed": 999999})
        check(r["speed"] == app.JOG_SPEED_MAX,
              "an over-range speed clamps to JOG_SPEED_MAX", r["speed"])

        r = app.motor_jog({"direction": "forward", "speed": 1})
        check(r["speed"] == app.JOG_SPEED_MIN,
              "an under-range speed clamps to JOG_SPEED_MIN", r["speed"])

        r = app.motor_jog({"direction": "forward"})
        check(r["speed"] == app.JOG_SPEED_MIN,
              "omitting speed defaults to the documented minimum, "
              "not the maximum", r["speed"])


def test_refused_while_a_scan_owns_the_interface() -> None:
    section("refused outright when anything already owns the USB interface "
            "-- Popen must never be called")
    with mock.patch.object(app.subprocess, "Popen", _NoPopen()), \
         mock.patch.object(app.SCAN, "running", return_value=True), \
         mock.patch.object(app, "foreign_scan", return_value=None), \
         mock.patch.object(app, "hardware_state", return_value=_ready_hw()):
        r = app.motor_jog({"direction": "forward"})
        check(r["ok"] is False and r.get("refused"),
              "a scan running in this process refuses the jog", r)

    with mock.patch.object(app.subprocess, "Popen", _NoPopen()), \
         mock.patch.object(app.SCAN, "running", return_value=False), \
         mock.patch.object(app, "foreign_scan",
                           return_value={"pid": 4242, "info": {}}), \
         mock.patch.object(app, "hardware_state", return_value=_ready_hw()):
        r = app.motor_jog({"direction": "forward"})
        check(r["ok"] is False and r.get("refused"),
              "a foreign scan process refuses the jog", r)

    with mock.patch.object(app.subprocess, "Popen", _NoPopen()), \
         mock.patch.object(app.SCAN, "running", return_value=False), \
         mock.patch.object(app, "foreign_scan", return_value=None), \
         mock.patch.object(app, "hardware_state", return_value=_ready_hw()):
        app._JOG.update(active=True, direction="forward")
        try:
            r = app.motor_jog({"direction": "reverse"})
            check(r["ok"] is False and r.get("refused"),
                  "a jog already in flight refuses a second one", r)
        finally:
            app._JOG.update(active=False, direction=None, proc=None)


def test_refused_on_bad_hardware_state() -> None:
    section("refused when the hardware state itself says not-ready -- "
            "Popen must never be called")
    with mock.patch.object(app.subprocess, "Popen", _NoPopen()), \
         mock.patch.object(app.SCAN, "running", return_value=False), \
         mock.patch.object(app, "foreign_scan", return_value=None), \
         mock.patch.object(app, "hardware_state",
                           return_value=_ready_hw(present=False)):
        r = app.motor_jog({"direction": "forward"})
        check(r["ok"] is False and r.get("refused"),
              "no scanner present refuses the jog", r)

    with mock.patch.object(app.subprocess, "Popen", _NoPopen()), \
         mock.patch.object(app.SCAN, "running", return_value=False), \
         mock.patch.object(app, "foreign_scan", return_value=None), \
         mock.patch.object(app, "hardware_state",
                           return_value=_ready_hw(simulated="/tmp/fake.bin")):
        r = app.motor_jog({"direction": "forward"})
        check(r["ok"] is False and r.get("refused") and
              "simulated" in r.get("error", ""),
              "a simulated scanner refuses the jog -- there is no real "
              "motor for spin_motor.py to reach", r)

    for bad_state in ("needs_firmware", "loading_firmware", "unreachable",
                      "fault", "absent"):
        with mock.patch.object(app.subprocess, "Popen", _NoPopen()), \
             mock.patch.object(app.SCAN, "running", return_value=False), \
             mock.patch.object(app, "foreign_scan", return_value=None), \
             mock.patch.object(app, "hardware_state",
                               return_value=_ready_hw(state=bad_state)):
            r = app.motor_jog({"direction": "forward"})
            check(r["ok"] is False and r.get("refused"),
                  f"hardware state {bad_state!r} refuses the jog", r)


def test_stop_is_unconditional_on_overrun() -> None:
    section("an overrun is interrupted and stop_jog() is called -- the "
            "backstop is server-side, not just a UI promise")
    stop_calls = []

    def fake_stop_jog(*a, **k):
        stop_calls.append((a, k))
        return {"signalled": True, "exited": True}

    def fake_popen(cmd, **kw):
        p = mock.Mock()
        p.communicate.side_effect = app.subprocess.TimeoutExpired(cmd, 1)
        # second .communicate() call (post-stop) succeeds
        calls = {"n": 0}

        def comm(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise app.subprocess.TimeoutExpired(cmd, 1)
            return ("", "")
        p.communicate.side_effect = comm
        p.returncode = -2
        p.poll.return_value = None
        return p

    with mock.patch.object(app.subprocess, "Popen", side_effect=fake_popen), \
         mock.patch.object(app.SCAN, "running", return_value=False), \
         mock.patch.object(app, "foreign_scan", return_value=None), \
         mock.patch.object(app, "hardware_state", return_value=_ready_hw()), \
         mock.patch.object(app, "stop_jog", side_effect=fake_stop_jog), \
         mock.patch.object(app.cwiz, "film_precheck",
                           side_effect=RuntimeError("no link in this test")):
        r = app.motor_jog({"direction": "forward", "seconds": 1})
        check(len(stop_calls) == 1,
              "stop_jog() is invoked exactly once on a communicate() "
              "timeout", stop_calls)
        check(r.get("timed_out") is True and r["ok"] is False,
              "the response records the overrun and reports ok=False", r)
        check(app._JOG["active"] is False,
              "_JOG is cleared even after an overrun -- no stuck 'jogging' "
              "state that would block every future probe/jog")


def test_film_sense_is_attempted_and_never_raises_out() -> None:
    section("film sensor state is read after the pulse and is always a "
            "well-formed part of the response, success or failure")

    def fake_popen(cmd, **kw):
        p = mock.Mock()
        p.communicate.return_value = ("", "")
        p.returncode = 0
        p.poll.return_value = 0
        return p

    class FakeVerdict:
        def to_json(self):
            return {"present": True, "source": "film-sensors"}

    with mock.patch.object(app.subprocess, "Popen", side_effect=fake_popen), \
         mock.patch.object(app.SCAN, "running", return_value=False), \
         mock.patch.object(app, "foreign_scan", return_value=None), \
         mock.patch.object(app, "hardware_state", return_value=_ready_hw()), \
         mock.patch.object(app.scan.Link, "open",
                           return_value=mock.Mock(close=mock.Mock())), \
         mock.patch.object(app.cwiz, "film_precheck",
                           return_value=FakeVerdict()):
        r = app.motor_jog({"direction": "forward", "seconds": 0.3})
        check(r.get("film_sense", {}).get("present") is True,
              "a successful pulse carries the post-pulse sensor verdict", r)

    # And when the Link cannot be opened at all -- e.g. a transient USB hiccup
    # right after spin_motor.py released the interface -- the endpoint must
    # still return a clean, well-formed response rather than raising.
    with mock.patch.object(app.subprocess, "Popen", side_effect=fake_popen), \
         mock.patch.object(app.SCAN, "running", return_value=False), \
         mock.patch.object(app, "foreign_scan", return_value=None), \
         mock.patch.object(app, "hardware_state", return_value=_ready_hw()), \
         mock.patch.object(app.scan.Link, "open",
                           side_effect=RuntimeError("USB busy")):
        r = app.motor_jog({"direction": "forward", "seconds": 0.3})
        check(r["ok"] is True,
              "a failed post-pulse sensor read does not fail the jog "
              "itself -- the motor already stopped cleanly", r)
        check(r.get("film_sense", {}).get("available") is False and
              "error" in r.get("film_sense", {}),
              "the sensor-read failure is reported honestly, not silently "
              "dropped", r.get("film_sense"))


def test_scan_refuses_to_start_mid_jog() -> None:
    section("the other direction: ScanSupervisor.start() refuses while a "
            "jog holds the interface -- two processes must never claim it "
            "at once")
    app._JOG.update(active=True, direction="forward", at=time.time())
    try:
        with mock.patch.object(app.SCAN, "running", return_value=False), \
             mock.patch.object(app, "foreign_scan", return_value=None):
            try:
                app.SCAN.start("test-job", {})
                check(False, "SCAN.start() raises while a jog is active")
            except RuntimeError as e:
                check("jog" in str(e).lower(),
                      "SCAN.start() refuses with a jog-specific reason",
                      str(e))
    finally:
        app._JOG.update(active=False, direction=None, proc=None)

    # And the ordinary case is unaffected: idle jog state does not itself
    # block a scan (this would raise inside SCAN.start for an unrelated
    # reason -- a missing calibration record, no capture dir set up in this
    # test environment -- so it is enough that it does NOT raise "jog").
    with mock.patch.object(app.SCAN, "running", return_value=False), \
         mock.patch.object(app, "foreign_scan", return_value=None):
        try:
            app.SCAN.start("test-job-2", {})
        except RuntimeError as e:
            check("jog" not in str(e).lower(),
                  "an idle jog state never blocks a scan", str(e))
        except Exception:
            pass  # any other failure here is unrelated to this guard


def test_pulse_duration_is_a_sane_physical_distance() -> None:
    section("what a default pulse actually moves the film, in real units -- "
            "sanity-checked against this project's own transport constants")
    # speed_mm_per_s / MOTOR_SPEED_MIN_PLUS live in pakon_scan.py, the module
    # this project already treats as ground truth for transport speed.
    mm_per_s = app.scan.speed_mm_per_s(app.JOG_SPEED_MIN)
    check(abs(mm_per_s - 1.0) < 1e-9,
          "JOG_SPEED_MIN (the jog's default speed) is the documented "
          "MOTOR_SPEED_MIN_PLUS, i.e. 1.0 mm/s", mm_per_s)
    for pulse_s in (0.2, 0.3, 0.4, 0.5):
        distance_mm = mm_per_s * pulse_s
        check(0.05 <= distance_mm <= 2.0,
              f"a {pulse_s*1000:.0f}ms pulse moves {distance_mm:.2f}mm -- "
              f"small and non-zero, the point of a 'nudge'", distance_mm)
    check(app.JOG_MAX_SECONDS * app.scan.speed_mm_per_s(app.JOG_SPEED_MAX)
          < app.scan.NORMAL_ROLL_MM,
          "even the worst case this endpoint allows without --long (max "
          "speed x max seconds) moves less than one full roll's length")


def main() -> int:
    print("manual film-jog self-tests -- no scanner required")
    t0 = time.time()
    test_direction_validated_before_anything_else()
    test_seconds_are_clamped_to_the_short_cap_by_default()
    test_speed_is_clamped_to_the_documented_legal_range()
    test_refused_while_a_scan_owns_the_interface()
    test_refused_on_bad_hardware_state()
    test_stop_is_unconditional_on_overrun()
    test_film_sense_is_attempted_and_never_raises_out()
    test_scan_refuses_to_start_mid_jog()
    test_pulse_duration_is_a_sane_physical_distance()
    print(f"\n{_count - len(_fails)}/{_count} checks passed "
          f"({time.time() - t0:.2f}s)")
    if _fails:
        print("FAILED:")
        for f in _fails:
            print(f"  - {f}")
        return 1
    print("all good")
    return 0


if __name__ == "__main__":
    sys.exit(main())
