#!/usr/bin/env python3
"""Self-tests for the calibration read-and-backup path. No scanner needed.

Run:  python3 tools/test_calib.py

The important tests are the ones that try to cause the accident: reading twice
in one power cycle, reading after a restart, reading a scanner that has been
up, and letting a degraded read displace a good one. Each of those is an
attempt to reproduce the failure that would destroy someone's calibration, and
each must fail to reproduce it.

The simulated scanner reproduces the measured degradation curve (first read
good, second read 180/256 bytes wrong, third onwards all 0xFF, status "ok"
throughout), so these tests exercise the real danger rather than a friendly
stand-in.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(HERE))

import calib_device as cd       # noqa: E402
import calib_store as cs        # noqa: E402
import calib_verify as cv       # noqa: E402

REPO = HERE.parent
GOOD52 = (REPO / "backups/eeprom-i2c/eeprom_52.bin").read_bytes()
ERASED51 = (REPO / "backups/eeprom-i2c/eeprom_51.bin").read_bytes()

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


def sim(**kw) -> cd.SimTransport:
    return cd.SimTransport({0x51: ERASED51, 0x52: GOOD52}, **kw)


# --------------------------------------------------------------------------

def test_verify() -> None:
    section("structural verification (no re-reading)")
    r = cv.verify(GOOD52)
    check(r["state"] == cv.GOOD, "the real calibration page reads GOOD",
          r["summary"])
    check(r["kind"] == cv.KIND_CALIBRATION, "recognised as calibration")
    check(r["info"]["serial"] == 16275, "serial decodes at 0x0F")
    check(all(c["ok"] for c in r["checks"]), "all structural checks pass")

    check(cv.verify(b"\xff" * 256)["state"] == cv.ERASED,
          "all-0xFF reads ERASED, never GOOD")
    check(cv.verify(bytes(256))["state"] == cv.BLANK, "all-0x00 reads BLANK")
    check(cv.verify(b"\xee" * 256)["state"] == cv.NOT_READ,
          "the firmware's 0xEE sentinel reads NOT-READ")

    # The documented second-read failure: 180 of 256 bytes differ.
    import random
    rng = random.Random(7)
    dego = bytearray(GOOD52)
    for i in rng.sample(range(256), 180):
        dego[i] = rng.randrange(256)
    d = cv.verify(bytes(dego))
    check(d["state"] != cv.GOOD,
          "a 180/256-corrupted page never reads GOOD", d["state"])

    check(not cv.verify(b"\xff" * 256)["crc"]["checked"],
          "CRC is reported unchecked rather than faked")


def test_read_once_guarantee() -> None:
    section("read-once-per-power-cycle, across process restarts")
    t = sim()
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)

        g1 = cd.PowerCycleGuard(t, d)
        check(g1.check()["may_read"], "fresh power cycle permits a read")

        out = cd.read_bus(t)
        check(out["complete"], "firmware ran to completion")
        check(set(out["devices"]) == {0x51, 0x52},
              "only devices that ACKed are returned",
              str(sorted(out["devices"])))
        check(out["devices"][0x52] == GOOD52,
              "the first read returns the true contents")
        nonce = g1.stamp()
        g1.note("read", nonce=nonce)

        check(not g1.check()["may_read"],
              "same object refuses a second read in one power cycle")
        check(g1.check()["code"] == "already-read", "refusal names the reason")

        # THE point: a completely fresh guard, as a new process would build.
        g2 = cd.PowerCycleGuard(t, d)
        check(not g2.check()["may_read"],
              "a NEW process still refuses -- the witness is in FX2 RAM, "
              "not in memory")

        # And a third, with a different journal directory entirely, proving
        # the guarantee does not depend on our own files surviving.
        with tempfile.TemporaryDirectory() as tmp2:
            g3 = cd.PowerCycleGuard(t, Path(tmp2))
            check(not g3.check()["may_read"],
                  "refuses even with the on-disk journal deleted")

        # Power cycle: the marker must NOT survive it.
        t.power_cycle()
        g4 = cd.PowerCycleGuard(t, d)
        check(g4.check()["may_read"],
              "a real power cycle permits a read again")


def test_second_witness() -> None:
    section("second witness: resident firmware")
    t = sim()
    with tempfile.TemporaryDirectory() as tmp:
        g = cd.PowerCycleGuard(t, Path(tmp))
        cd.read_bus(t)
        g.stamp()
        # Something wipes the marker but the power was never cycled.
        t.ram_write(cd.MARKER_ADDR, b"\x00" * cd.MARKER_LEN)
        check(g.marker() is None, "marker really was cleared")
        r = g.check()
        check(not r["may_read"],
              "still refuses -- the resident firmware gives it away")
        check(r["code"] == "ram-not-clear", "refusal cites resident RAM",
              r["code"])


def test_probe_failure_fails_closed() -> None:
    section("a failed RAM probe refuses (fail closed, never fail open)")
    t = sim()

    def boom(addr, length):
        raise IOError("simulated USB failure")
    t.ram_read = boom
    with tempfile.TemporaryDirectory() as tmp:
        r = cd.PowerCycleGuard(t, Path(tmp)).check()
        check(not r["may_read"],
              "cannot read the scanner's RAM -> refuses to read the EEPROM")
        check(r["code"] == "probe-failed", "refusal cites the failed probe",
              r["code"])
        check("already been read" in r["reason"],
              "and explains that guessing could destroy the calibration")


def test_loaded_scanner_refused() -> None:
    section("a scanner that has been up is refused")
    t = sim(loaded=True)
    with tempfile.TemporaryDirectory() as tmp:
        r = cd.PowerCycleGuard(t, Path(tmp)).check()
        check(not r["may_read"], "loaded scanner refused")
        check(r["code"] == "loaded", "refusal cites the loaded firmware")
    t2 = sim(present=False)
    with tempfile.TemporaryDirectory() as tmp:
        r = cd.PowerCycleGuard(t2, Path(tmp)).check()
        check(not r["may_read"] and r["code"] == "absent",
              "absent scanner refused cleanly")


def test_degradation_is_real() -> None:
    section("the simulated hardware really does degrade (the danger is modelled)")
    t = sim()
    first = cd.read_bus(t)["devices"][0x52]
    check(first == GOOD52, "read 1 is the truth")
    # Deliberately bypass the guard to show what it is protecting against.
    t.reset_8051(False)
    second = t.ram_read(cd.BUF_BASE + 2 * cd.BUF_STRIDE, 256)
    check(second != GOOD52, "read 2 is corrupted")
    check(cv.verify(second)["state"] != cv.GOOD,
          "and the verifier catches it")
    t.reset_8051(False)
    third = t.ram_read(cd.BUF_BASE + 2 * cd.BUF_STRIDE, 256)
    check(third == b"\xff" * 256, "read 3 is all 0xFF")
    st = t.ram_read(cd.STATUS_ADDR, cd.STATUS_LEN)
    check(st[2] == 0,
          "and the I2C status still says 'ok' -- which is exactly the trap")


def test_no_writes() -> None:
    section("writes are structurally impossible")
    t = sim()
    cd.read_bus(t)
    check(t.i2c_writes == 0, "no I2C write ever occurred")

    # Structural, not textual: walk the AST and confirm that EVERY USB
    # control transfer the read path makes uses ANCHOR_LOAD_INTERNAL (0xA0,
    # FX2 RAM) as its bRequest. The vendor's EEPROM-write request 0xA2 and
    # the personality request 0xA9 are therefore not merely absent from the
    # text -- there is no call site that could carry them.
    import ast
    tree = ast.parse((HERE / "calib_device.py").read_text())
    requests, bad = [], []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "ctrl_transfer"):
            if len(node.args) < 2:
                bad.append("ctrl_transfer with too few args")
                continue
            req = node.args[1]
            name = req.id if isinstance(req, ast.Name) else ast.dump(req)
            requests.append(name)
            if name != "ANCHOR_LOAD_INTERNAL":
                bad.append(name)
    check(bool(requests) and not bad,
          f"every USB control transfer ({len(requests)}) uses "
          f"ANCHOR_LOAD_INTERNAL only", str(bad))
    check(cd.ANCHOR_LOAD_INTERNAL == 0xA0,
          "ANCHOR_LOAD_INTERNAL is 0xA0, the FX2 RAM request")
    calls = {n.func.attr for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    check("personality" not in calls,
          "the read path never calls Fx2.personality (which would send 0xA9)")

    fw = (REPO / "fx2/eeprom_dump_bus.c").read_text()
    check(fw.count("I2DAT =") == 3,
          "firmware has exactly 3 I2DAT stores (two addresses + read addr)",
          str(fw.count("I2DAT =")))

    ok, why = cd.firmware_ok()
    check(ok, "pinned firmware matches its audited hash", why)

    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / "tampered.ihx"
        bad.write_bytes((REPO / "fx2/eeprom_dump_bus.ihx").read_bytes() + b"\n")
        ok2, _ = cd.firmware_ok(bad)
        check(not ok2, "a tampered firmware image is refused")

    check((REPO / "tools/i2c_eeprom.hex.DANGEROUS-WRITES").exists()
          and not (REPO / "tools/i2c_eeprom.hex").exists(),
          "the write-capable firmware is still quarantined")
    try:
        cd.assert_safe_installation()
        check(True, "installation safety check passes")
    except cd.UnsafeToolState as e:
        check(False, "installation safety check passes", str(e))


def test_full_bus() -> None:
    section("every device on the bus is read, not just 0x52")
    contents = {a: bytes(((a * 7 + i) % 256) for i in range(256))
                for a in range(0x50, 0x58)}
    contents[0x52] = GOOD52
    t = cd.SimTransport(contents)
    out = cd.read_bus(t)
    check(set(out["devices"]) == set(range(0x50, 0x58)),
          "all eight addresses captured when all eight answer",
          str(sorted(hex(a) for a in out["devices"])))
    check(all(out["devices"][a] == contents[a] for a in contents),
          "each address returns its own distinct contents")

    # An intact FX2 boot personality elsewhere on the bus must be recognised.
    boot = bytes((0xC0, 0x05, 0x0F, 0x35, 0xF2, 0x07, 0xAA, 0x04)) + b"\xff" * 248
    r = cv.verify(boot)
    check(r["kind"] == cv.KIND_FX2_BOOT and r["state"] == cv.GOOD,
          "an intact FX2 boot personality is recognised and kept", r["summary"])


def test_store_append_only() -> None:
    section("the store is append-only and prefers nothing silently")
    tmp = Path(tempfile.mkdtemp())
    try:
        st = cs.CalibrationStore(tmp)
        st.save_read({0x51: ERASED51, 0x52: GOOD52}, source="cycle A",
                     stamp="2026-08-08T10-00-00Z")
        check(st.has_calibration(), "a good calibration is recorded")

        st.save_read({0x51: b"\xff" * 256, 0x52: b"\xff" * 256},
                     source="cycle B", stamp="2026-08-08T11-00-00Z")
        check(len(st.list_reads()) == 2, "both reads kept; nothing overwritten")

        sel = st.selection()
        check(sel["stamp"] == "2026-08-08T11-00-00Z",
              "newest is in force by default, as specified")
        check(sel["needs_attention"] and
              sel.get("better_available") == "2026-08-08T10-00-00Z",
              "a good earlier read is named when the newest is bad")

        st.select("2026-08-08T10-00-00Z")
        check(st.selection()["stamp"] == "2026-08-08T10-00-00Z",
              "the user can select an earlier calibration")
        check(st.selection()["user_override"], "override is reported as such")

        st.clear_selection()
        check(st.selection()["stamp"] == "2026-08-08T11-00-00Z",
              "clearing the override returns to newest")

        img = st.get("2026-08-08T10-00-00Z").path / "eeprom_52.bin"
        check(img.read_bytes() == GOOD52, "stored bytes are exactly what came in")
        try:
            with open(img, "wb") as fh:
                fh.write(b"x")
            check(False, "a stored calibration cannot be overwritten")
        except (PermissionError, OSError):
            check(True, "a stored calibration cannot be overwritten")

        manifest = (tmp / cs.MANIFEST).read_text().splitlines()
        check(len(manifest) == 6, "manifest names every file written",
              str(len(manifest)))
        import hashlib
        digest = hashlib.sha256(GOOD52).hexdigest()
        check(any(line.startswith(digest) for line in manifest),
              "manifest digest matches the real backup's SHA256SUMS entry")

        src = (HERE / "calib_store.py").read_text()
        for bad in ("os.remove", "shutil.rmtree", "unlink("):
            check(bad not in src, f"store contains no {bad} call")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_save_before_interpret() -> None:
    section("bytes are saved before anything interprets them")
    tmp = Path(tempfile.mkdtemp())
    try:
        st = cs.CalibrationStore(tmp)
        rec = st.save_read({0x52: GOOD52}, source="ordering",
                           stamp="2026-08-08T12-00-00Z")
        files = sorted(p.name for p in rec.path.iterdir())
        check("eeprom_52.bin" in files and "read.json" in files,
              "image and metadata both present")
        lines = (tmp / cs.MANIFEST).read_text().splitlines()
        check(lines[0].endswith("eeprom_52.bin"),
              "the image is manifested before read.json", lines[0])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_orchestration() -> None:
    section("orchestration: refuse when stored, salvage instead of re-reading")
    import calib_read as cr
    tmp = Path(tempfile.mkdtemp())
    try:
        t = sim()
        store = cs.CalibrationStore(tmp)
        guard = cd.PowerCycleGuard(t, tmp / "journal")

        res = cr.do_read(store, t, guard, source="test")
        check(res["record"].is_good, "first read succeeds and is good")
        check(t.reads[0x52] == 1, "0x52 was read exactly once")

        # Second attempt, same installation. Must refuse on the store alone.
        try:
            cr.do_read(store, t, guard, source="test")
            check(False, "a second read is refused when one is stored")
        except cd.ReadRefused:
            check(True, "a second read is refused when one is stored")
        check(t.reads[0x52] == 1, "and no further I2C read happened")

        # Connect report must not read either.
        rep = cr.connect_report(store, t, guard)
        check(rep["action"] == "none" and rep["have_calibration"],
              "connect reports the stored calibration and takes no action")
        check(t.reads[0x52] == 1, "connect caused no I2C traffic")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # A crash between reading and saving must NOT lead to a second read.
    tmp = Path(tempfile.mkdtemp())
    try:
        t = sim()
        store = cs.CalibrationStore(tmp)
        guard = cd.PowerCycleGuard(t, tmp / "journal")

        # Read, stamp, journal -- then "crash" before save_read.
        def _stamp():
            guard.note("read", nonce=guard.stamp(), source="test")
        cd.read_bus(t, before_run=_stamp)
        check(t.reads[0x52] == 1, "the interrupted run read 0x52 once")
        check(guard.unsaved_nonce() is not None, "journal shows an unsaved read")

        # New process picks up the pieces.
        guard2 = cd.PowerCycleGuard(t, tmp / "journal")
        store2 = cs.CalibrationStore(tmp)
        res = cr.do_read(store2, t, guard2, source="test")
        check(res["salvaged"], "recovery salvaged from RAM rather than re-reading")
        check(t.reads[0x52] == 1,
              "CRUCIALLY: still exactly one I2C read of 0x52",
              f"reads={t.reads[0x52]}")
        check(res["record"].data(0x52) == GOOD52,
              "the salvaged bytes are the good first read, not a degraded one")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_concurrent_read_locked() -> None:
    section("two processes cannot both decide the cycle is fresh")
    import calib_read as cr
    tmp = Path(tempfile.mkdtemp())
    try:
        t = sim()
        store = cs.CalibrationStore(tmp)
        guard = cd.PowerCycleGuard(t, tmp / "journal")
        lock_path = tmp / "journal" / "read.lock"

        # Hold the lock as a second instance would, then try to read.
        with cd.ReadLock(lock_path):
            try:
                cr.do_read(store, t, guard, source="test")
                check(False, "a concurrent read is refused")
            except cd.ReadRefused as e:
                check("same time" in str(e), "a concurrent read is refused",
                      str(e)[:60])
            check(t.reads.get(0x52, 0) == 0,
                  "and the scanner was never touched")

        # Once released, the read proceeds normally.
        res = cr.do_read(store, t, guard, source="test")
        check(res["record"].is_good, "the read succeeds once the lock is free")
        check(t.reads[0x52] == 1, "exactly one I2C read in total")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _listing(root: Path) -> dict:
    """Every file under root, with its exact bytes. Byte-identical or not."""
    import hashlib
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            b = p.read_bytes()
            out[str(p.relative_to(root))] = (len(b), hashlib.sha256(b).hexdigest())
    return out


def test_simulate_never_touches_the_real_store() -> None:
    section("a rehearsal cannot write into the real store (2026-08-08 bug)")
    import subprocess
    import calib_read as cr

    real = Path(tempfile.mkdtemp())
    try:
        # A real store with a real read in it, exactly as an owner would have.
        st = cs.CalibrationStore(real)
        st.save_read({0x51: ERASED51, 0x52: GOOD52}, source="genuine read",
                     stamp="2026-08-08T15-27-44Z")
        before = _listing(real)

        env = dict(os.environ, PAKON_CALIBRATION_DIR=str(real))
        proc = subprocess.run(
            [sys.executable, str(HERE / "calib_read.py"), "--simulate", "read"],
            capture_output=True, text=True, env=env)
        after = _listing(real)
        check(after == before,
              "the real store is byte-identical before and after a rehearsal",
              f"changed: {sorted(set(after) ^ set(before)) or 'contents differ'}")
        check(len(cs.CalibrationStore(real).list_reads()) == 1,
              "no rehearsal record was added to the real store")
        check("REHEARSAL" in proc.stdout,
              "the rehearsal says so, and names the scratch store it used",
              proc.stdout[:200])
        check("not touched" in proc.stdout,
              "and says plainly that the real store was left alone")

        # status must not touch it either.
        before2 = _listing(real)
        subprocess.run([sys.executable, str(HERE / "calib_read.py"),
                        "--simulate", "status"],
                       capture_output=True, text=True, env=env)
        check(_listing(real) == before2, "nor does a simulated status")

        # And the structural half: do_read itself refuses a simulated
        # transport pointed at the real store, whoever the caller is -- with
        # --force too, which is the combination that would otherwise get past
        # the "already stored" refusal.
        old = os.environ.get("PAKON_CALIBRATION_DIR")
        os.environ["PAKON_CALIBRATION_DIR"] = str(real)
        try:
            for forced in (False, True):
                try:
                    cr.do_read(cs.CalibrationStore(real), sim(),
                               cd.PowerCycleGuard(sim(), real / "journal"),
                               force=forced, source="test")
                    check(False, f"do_read refuses a simulated read into the "
                                 f"real store (force={forced})")
                except cd.ReadRefused as e:
                    check("simulated scanner" in str(e),
                          f"do_read refuses a simulated read into the real "
                          f"store (force={forced})", str(e)[:80])
        finally:
            if old is None:
                del os.environ["PAKON_CALIBRATION_DIR"]
            else:
                os.environ["PAKON_CALIBRATION_DIR"] = old
        check(_listing(real) == before, "and that refusal wrote nothing")

        # Pointing --store at the real store while simulating is refused.
        proc = subprocess.run(
            [sys.executable, str(HERE / "calib_read.py"), "--simulate",
             "--store", str(real), "read"],
            capture_output=True, text=True, env=env)
        check(proc.returncode != 0 and _listing(real) == before,
              "--simulate --store <the real store> is refused outright",
              proc.stderr[:120])

        # The rehearsal must still be a genuine rehearsal: it does save,
        # somewhere disposable, so the exercise is the real code path.
        with tempfile.TemporaryDirectory() as scratch:
            proc = subprocess.run(
                [sys.executable, str(HERE / "calib_read.py"), "--simulate",
                 "--store", scratch, "read"],
                capture_output=True, text=True, env=env)
            reads = cs.CalibrationStore(Path(scratch)).list_reads()
            check(proc.returncode == 0 and len(reads) == 1 and reads[0].is_good,
                  "a rehearsal still exercises the whole path, in scratch",
                  proc.stdout[-200:] + proc.stderr[-200:])
    finally:
        shutil.rmtree(real, ignore_errors=True)


def main() -> int:
    print("calibration read/backup self-tests -- no scanner required")
    test_verify()
    test_read_once_guarantee()
    test_second_witness()
    test_probe_failure_fails_closed()
    test_loaded_scanner_refused()
    test_degradation_is_real()
    test_no_writes()
    test_full_bus()
    test_store_append_only()
    test_save_before_interpret()
    test_orchestration()
    test_concurrent_read_locked()
    test_simulate_never_touches_the_real_store()
    print(f"\n{_count - len(_fails)}/{_count} checks passed")
    if _fails:
        print("FAILED:")
        for f in _fails:
            print(f"  - {f}")
        return 1
    print("all good")
    return 0


if __name__ == "__main__":
    sys.exit(main())
