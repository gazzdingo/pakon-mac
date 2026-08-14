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

import json
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


def test_force_still_requires_a_proven_power_cycle() -> None:
    section("--force does not skip the power cycle (2026-08-08 bug)")
    import calib_read as cr
    tmp = Path(tempfile.mkdtemp())
    try:
        t = sim()
        store = cs.CalibrationStore(tmp)
        guard = cd.PowerCycleGuard(t, tmp / "journal")

        # The owner's machine at 15:28:46. A calibration is already stored, so
        # only --force can get past it; the scanner has already given up its
        # one good read of this power cycle; and nothing in its RAM says so,
        # because whatever read it left the witness region clean. Absence of a
        # marker is therefore absence of information, not evidence of freshness.
        store.save_read({0x51: ERASED51, 0x52: GOOD52}, source="earlier read",
                        stamp="2026-08-08T15-27-44Z")
        cd.read_bus(t)                        # this cycle's one good read
        t.ram = bytearray(0x2000)             # RAM wiped; power NOT cycled
        check(t.reads[0x52] == 1, "this power cycle's good read is spent")
        check(cd.PowerCycleGuard(t, tmp / "journal").check()["may_read"],
              "and the ordinary check cannot tell -- it sees a clean RAM")

        try:
            cr.do_read(store, t, guard, force=True, source="test")
            check(False, "--force refuses when the power cycle is unproven")
        except cd.ReadRefused as e:
            check("power" in str(e).lower(),
                  "--force refuses when the power cycle is unproven",
                  str(e)[:90])
        check(t.reads[0x52] == 1,
              "CRUCIALLY: --force took no second I2C read",
              f"reads={t.reads[0x52]}")
        check(len(store.list_reads()) == 1,
              "and stored no all-0xFF record beside the good one")

        # It must also leave the user able to satisfy it, so it marks the
        # scanner -- and must then hold that line while the mark is still there.
        check(guard.marker() is not None, "the scanner was marked for next time")
        check(any(e["event"] == "armed" for e in guard.entries()),
              "and the journal says so")
        try:
            cr.do_read(store, t, guard, force=True, source="test")
            check(False, "refuses again while its own mark is still in RAM")
        except cd.ReadRefused as e:
            check("has NOT been cycled" in str(e),
                  "refuses again while its own mark is still in RAM",
                  str(e)[:90])
        check(t.reads[0x52] == 1, "still no second read")

        # The power cycle actually happens. Now the mark is gone from RAM,
        # which is the positive evidence, and the read is allowed.
        t.power_cycle()
        chk = cd.PowerCycleGuard(t, tmp / "journal").check(
            require_power_cycle_witness=True)
        check(chk["may_read"] and chk.get("witnessed"),
              "a witnessed power cycle permits the forced read", str(chk))
        res = cr.do_read(store, t, guard, force=True, source="test")
        check(res["record"].is_good,
              "the forced read is now the first transaction of a fresh cycle")
        check(res["record"].data(0x52) == GOOD52, "and returns the true bytes")
        check(t.reads[0x52] == 1, "exactly one I2C read in the new cycle")
        check(len(store.list_reads()) == 2,
              "both reads kept -- the store still deletes nothing")

        # A witness from the other world proves nothing about this one.
        import json
        with tempfile.TemporaryDirectory() as j:
            g = cd.PowerCycleGuard(sim(), Path(j))
            Path(j).mkdir(parents=True, exist_ok=True)
            (Path(j) / "read-journal.jsonl").write_text(
                json.dumps({"event": "read", "nonce": "de" * 16,
                            "utc": "2026-08-08T15:27:44Z"}) + "\n")
            check(g.last_witness() is None,
                  "a real scanner's nonce is not a witness for a simulated one")
            check(not g.check(require_power_cycle_witness=True)["may_read"],
                  "so a forced read is still refused")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # What the refusal prevented, on a throwaway simulator: the read --force
    # used to take in that state is the degraded one, and the hardware says
    # "ok" while returning it.
    t2 = sim()
    cd.read_bus(t2)
    t2.ram = bytearray(0x2000)
    out = cd.read_bus(t2)
    got = out["devices"][0x52]
    check(cv.verify(got)["state"] != cv.GOOD,
          "what --force used to do in that state returns a corrupt page",
          cv.verify(got)["state"])
    check(out["results"][0x52]["text"] == "ok",
          "while the I2C status still reports 'ok'")


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


def _page_with_serial(serial: int) -> bytes:
    """The owner's real page with a different serial written into 0x0F.

    A synthetic second unit, used only inside temporary stores. The matrices
    stay valid so the page still passes the structural checks -- what is being
    tested is the index and the resolution, not the decode.
    """
    b = bytearray(GOOD52)
    b[cv.SERIAL_OFF:cv.SERIAL_OFF + 4] = int(serial).to_bytes(4, "little")
    return bytes(b)


def test_serial_index() -> None:
    section("reads are grouped by the scanner they came from")
    import calib_resolve as crs
    tmp = Path(tempfile.mkdtemp())
    try:
        st = cs.CalibrationStore(tmp)

        # Nothing stored: a prompt, never an automatic read.
        r = crs.resolve(st)
        check(r["state"] == crs.NO_CALIBRATION and r["action"] == crs.ACTION_READ,
              "an empty store asks to read rather than reading", r["state"])
        check(r["may_auto_read"] is False and r["device_read_performed"] is False,
              "and says in the report that it did not and may not read")

        # A read that does not parse must not invent a scanner.
        st.save_read({0x52: b"\xff" * 256}, source="bad cycle",
                     stamp="2026-08-08T09-00-00Z")
        r = crs.resolve(st)
        check(r["state"] == crs.UNUSABLE and r["action"] == crs.ACTION_ATTENTION,
              "a store of only-degraded reads reports it and does not re-read",
              r["state"])
        check(st.unit_index()["serials"] == [],
              "a degraded page's serial field is never believed")
        check(len(r["unattributed"]) == 1,
              "but the unusable read is still listed, not hidden")

        # One unit: resolves with no choice to make.
        st.save_read({0x51: ERASED51, 0x52: GOOD52}, source="cycle A",
                     stamp="2026-08-08T10-00-00Z")
        r = crs.resolve(st)
        check(r["state"] == crs.READY and r["serial"] == cv.OWNER_SERIAL,
              "one stored unit resolves straight to that unit", str(r["serial"]))
        check(r["stamp"] == "2026-08-08T10-00-00Z" and r["action"] == crs.ACTION_NONE,
              "and needs no action at all")

        # A later degraded read of the SAME unit must not displace the good one.
        st.save_read({0x52: b"\xff" * 256}, source="cycle A second read",
                     stamp="2026-08-08T10-30-00Z")
        r = crs.resolve(st)
        check(r["stamp"] == "2026-08-08T10-00-00Z",
              "a later degraded read does not displace the good one")
        check(any("degraded" in w or "do not pass" in w or "structural" in w
                  for w in r["warnings"]),
              "and the degraded read is mentioned rather than silently ignored",
              str(r["warnings"]))

        # Two units: the one case where guessing is the wrong answer.
        st.save_read({0x52: _page_with_serial(20001)}, source="cycle B",
                     stamp="2026-08-08T11-00-00Z")
        r = crs.resolve(st)
        check(r["state"] == crs.AMBIGUOUS and r["action"] == crs.ACTION_CHOOSE,
              "two stored scanners produce a question, not a guess", r["state"])
        check(r["serial"] is None and r["stamp"] is None,
              "and nothing is applied while the question is open")
        check(sorted(r["serials"]) == sorted([cv.OWNER_SERIAL, 20001]),
              "both scanners are offered", str(r["serials"]))

        # Answering it sticks, and stays honest about what it is.
        st.select_unit(20001)
        r = crs.resolve(st)
        check(r["state"] == crs.READY and r["serial"] == 20001,
              "the chosen scanner is used")
        check(any("chosen, not because it was detected" in w
                  for w in r["warnings"]),
              "and the report says the identity was chosen, not detected",
              str(r["warnings"]))
        st.select_unit(None)
        check(crs.resolve(st)["state"] == crs.AMBIGUOUS,
              "clearing the choice returns to asking")

        # A serial we have never read is an explicit prompt, not a fallback.
        r = crs.resolve(st, serial_hint=99999)
        check(r["state"] == crs.UNKNOWN_UNIT and r["action"] == crs.ACTION_READ,
              "an unknown scanner prompts to read", r["state"])
        check(r["stamp"] is None,
              "CRUCIALLY: an unknown scanner is not given another unit's read")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_profile_sources() -> None:
    section("a profile never passes off one unit's numbers as another's")
    import calib_profile as cp
    tmp = Path(tempfile.mkdtemp())
    try:
        st = cs.CalibrationStore(tmp)
        st.save_read({0x52: GOOD52}, source="cycle A",
                     stamp="2026-08-08T10-00-00Z")

        p = cp.profile(st)
        check(p.serial == cv.OWNER_SERIAL and p.matrix_source == cp.FROM_DEVICE,
              "the colour matrix comes from this scanner's own page")
        d = [p.neg_matrix[0], p.neg_matrix[11], p.neg_matrix[22]]
        check(all(0.05 < v < 1.0 for v in d),
              "and decodes to the negative scale triple",
              "  ".join(f"{v:.6f}" for v in d))
        check(all(abs(a - b) < 1e-3
                  for a, b in zip(p.pedestals, cv.OWNER_PEDESTALS)),
              "pedestals match the values verified against the owner's page",
              str(p.pedestals))
        check(p.pos_truncated_from == 24,
              "the reversal matrix is reported truncated at 24/30, not padded "
              "silently", str(p.pos_truncated_from))
        check(p.config_source == cp.FROM_REFERENCE,
              "the owner's own unit takes the repo reference as its own",
              p.config_source)

        # A DIFFERENT scanner must never be handed the reference as its own.
        st2 = cs.CalibrationStore(Path(tempfile.mkdtemp()))
        try:
            st2.save_read({0x52: _page_with_serial(20001)}, source="cycle B",
                          stamp="2026-08-08T10-00-00Z")
            q = cp.profile(st2)
            check(q.serial == 20001 and q.matrix_source == cp.FROM_DEVICE,
                  "a second scanner gets ITS OWN colour matrix")
            check(q.config_source == cp.FROM_BORROWED,
                  "and its exposure is labelled BORROWED, not calibrated",
                  q.config_source)
            check(q.is_this_units_own_exposure is False,
                  "is_this_units_own_exposure is false for borrowed values")
            check(any("BORROWED" in w for w in q.warnings),
                  "with a warning a UI can put in front of a person")

            # Attaching that unit's own values makes it its own again.
            cp.adopt_reference(st2, 20001)
            q2 = cp.profile(st2)
            check(q2.config_source == cp.FROM_UNIT_OVERLAY,
                  "an adopted overlay becomes the unit's own source",
                  q2.config_source)
            check(q2.config == q.config,
                  "and carries the same values it was given")
            check(len(st2.overlays(20001)) == 1, "one overlay is recorded")
            cp.adopt_reference(st2, 20001)
            check(len(st2.overlays(20001)) == 2,
                  "a second overlay is appended, never replacing the first")
        finally:
            shutil.rmtree(st2.root, ignore_errors=True)

        # No reference file at all: refuse to invent one.
        r = cp.profile(st, reference=tmp / "does-not-exist.json")
        check(r.config_source == cp.FROM_NOTHING and not r.config,
              "with no reference available the config is empty, not guessed",
              r.config_source)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_lookup_cannot_reach_a_device() -> None:
    section("the lookup path cannot reach a scanner, structurally")
    import ast
    import json
    import subprocess

    # Read the import statements themselves rather than grepping the text --
    # these files DISCUSS calib_device at length in their docstrings, and a
    # test that cannot tell an explanation from an import would either fail
    # here or, worse, be silenced by deleting the explanation.
    forbidden = {"usb", "calib_device", "pakon_load", "pakon_scan"}
    for name in ("calib_resolve.py", "calib_profile.py"):
        tree = ast.parse((HERE / name).read_text(), filename=name)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        check(not (imported & forbidden),
              f"{name} imports nothing that can open a device",
              f"offending: {sorted(imported & forbidden)}")
        check("Transport" not in {a.arg for fn in ast.walk(tree)
                                  if isinstance(fn, ast.FunctionDef)
                                  for a in fn.args.args},
              f"{name} takes no transport argument anywhere")

    # The strong form: import the lookup path in a clean interpreter, use it,
    # and prove neither usb nor the device module was ever pulled in. A file
    # that cannot name a transport cannot issue one.
    prog = (
        "import sys, json, tempfile, os;"
        "sys.path.insert(0, %r);"
        "import calib_profile as cp;"
        "d = tempfile.mkdtemp();"
        "p = cp.profile(d);"
        "print(json.dumps({'usb': 'usb' in sys.modules,"
        " 'dev': 'calib_device' in sys.modules,"
        " 'state': p.state}))" % str(HERE))
    proc = subprocess.run([sys.executable, "-c", prog], capture_output=True,
                          text=True)
    try:
        got = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:                                       # noqa: BLE001
        got = {"usb": True, "dev": True, "state": proc.stderr[:200]}
    check(got["usb"] is False,
          "resolving a profile never imports pyusb", str(got))
    check(got["dev"] is False,
          "resolving a profile never imports calib_device", str(got))
    check(got["state"] == "no-calibration",
          "and an empty store resolves to 'ask', with no device in reach",
          str(got))


def test_afe_offset_encoding() -> None:
    """The bug that made a dark reference read all zeros. docs/72.

    AD9826 offsets are 9-bit SIGN-MAGNITUDE with the sign in bit 8. This port
    sent two's complement until 2026-08-12, so the vendor's Offset_R = -19 went
    out as 0xFFED and the part read it as magnitude 237, sign set: it was asked
    for -237. That drove the black level under the ADC's bottom code and a
    33,226-line dark reference came back with every sample exactly 0.
    """
    import pakon_commands as pc

    section("the AD9826 offset encoding (docs/72)")

    # The exact table in docs/42-ccd-analog-front-end.md, derived from the
    # binary; it is the ground truth this encoder has to match.
    for value, want in ((-18, 0x112), (-26, 0x11A), (-20, 0x114)):
        check(pc.afe_offset_word(value) == want,
              f"offset {value} encodes to 0x{want:03X}",
              f"got 0x{pc.afe_offset_word(value):03X}")

    check(all(pc.afe_offset_value(pc.afe_offset_word(v)) == v
              for v in range(-254, 256)),
          "every representable offset round-trips")

    # The failure itself, stated as a test so it cannot come back.
    two_c = -19 & 0xFFFF
    check(pc.afe_offset_value(two_c) == -237,
          "two's complement -19 would have been read as -237",
          f"got {pc.afe_offset_value(two_c)}")
    check(pc.afe_offset_word(-19) != (two_c & 0x1FF),
          "and the encoder does not produce that")

    # The vendor's own asymmetry: clamp at the top, refuse at the bottom.
    check(pc.afe_offset_word(300) == pc.afe_offset_word(255),
          "values at or above +255 clamp, as the vendor's encoder does")
    try:
        pc.afe_offset_word(-255)
        check(False, "-255 is refused rather than wrapped")
    except ValueError:
        check(True, "-255 is refused rather than wrapped")

    src = (REPO / "tools/pakon_scan.py").read_text()
    check("afe_offset_word" in src,
          "pakon_scan.ccd_configure uses the encoder")
    check("pc.adc_write(idx, int(o) & 0xFFFF)" not in src,
          "and no longer sends two's complement to the offset registers")


def test_dark_floor_refusal() -> None:
    """A dark reference sitting on ADC code 0 must be refused, not built on."""
    import numpy as np

    import build_calibration as bcal

    section("a black level clipped at zero is refused")

    zeros = np.zeros((64, 2000, 3), dtype=np.uint16)
    zeros[:, 0, 0] = 1              # the line-sync flag, and nothing else

    class _Cap:
        path = Path("synthetic-dark.bin")
        planes = zeros
        floor_stats = bcal.Capture.floor_stats
        is_floored = bcal.Capture.is_floored

        def channel_means(self):
            return self.planes.astype(float).mean(axis=(0, 1))

    c = _Cap()
    check(c.is_floored(), "an all-zero dark reference is detected as floored")
    try:
        bcal.check_dark_floor(c)
        check(False, "and check_dark_floor refuses it")
    except bcal.Refused as e:
        check("CLIPPED AT ZERO" in str(e), "and check_dark_floor refuses it")
        check("solve-offset" in str(e),
              "naming the tool that fixes it, not just the symptom")

    good = np.full((64, 2000, 3), 1200, dtype=np.uint16)
    good[:, 0, 0] |= 1
    _Cap.planes = good
    check(not _Cap().is_floored(),
          "a healthy pedestal is not mistaken for a floored one")
    check(bcal.check_dark_floor(_Cap()) == [], "and produces no warning")


def test_vendor_target_is_a_maximum() -> None:
    """docs/15: the vendor compares the MAXIMUM pixel of an averaged line."""
    import numpy as np

    import build_calibration as bcal

    section("the 64000 target is a maximum, not a mean")

    check(bcal.DEFAULT_METRIC == bcal.METRIC_MAX,
          "the default metric is the vendor's max, not the mean")

    prof = np.ones((2000, 3)) * 50000.0
    prof[900:1100] = 55000.0        # a hot band, as PRNU produces

    class _Cap:
        path = Path("synthetic-bright.bin")
        planes = prof[None, :, :].astype(np.uint16)
        illuminated = bcal.Capture.illuminated
        channel_levels = bcal.Capture.channel_levels
        channel_maxima = bcal.Capture.channel_maxima
        channel_metric = bcal.Capture.channel_metric

        def pixel_mean(self):
            return prof

    c = _Cap()
    lvl = float(c.channel_metric(bcal.METRIC_LEVEL)[0])
    mx = float(c.channel_metric(bcal.METRIC_MAX)[0])
    check(mx > lvl, "the max metric is above the level metric",
          f"max {mx} level {lvl}")
    check(abs(mx - 55000.0) < 1.0,
          "and it is the maximum of the averaged line", f"{mx}")
    check(64000.0 * (mx / lvl) > bcal.WIRE_MAX,
          "aiming the MEAN at 64000 would push the brightest pixels past the "
          "rail", f"{64000.0 * (mx / lvl):.0f} against {bcal.WIRE_MAX}")


def test_flatfield_store_is_append_only() -> None:
    """Per-serial measured tables, stored the way every other artefact is."""
    section("per-unit flat fields")

    root = Path(tempfile.mkdtemp())
    try:
        store = cs.CalibrationStore(root / "store")
        src = root / "built"
        src.mkdir()
        for n in cs.CalibrationStore.FLATFIELD_FILES:
            (src / n).write_text("{}" if n.endswith(".json") else "x")

        check(not store.has_flatfield_for(16275),
              "a scanner with no measured tables reports none")

        a = store.save_flatfield(16275, src, meta={"config": {"k": 1}},
                                 source="test", stamp="2026-01-01T00-00-00Z")
        check(store.has_flatfield_for(16275), "storing one makes it findable")
        check(store.flatfield(16275)["dir"] == a["dir"],
              "and it is the one that comes back")
        check(json.loads(Path(a["dir"], "README.json").read_text())
              ["unit_serial"] == 16275,
              "the stored record names the serial it belongs to")

        b = store.save_flatfield(16275, src, meta={"config": {"k": 2}},
                                 source="test", stamp="2026-02-02T00-00-00Z")
        check(Path(a["dir"]).is_dir(),
              "a second set does not replace the first")
        check(store.flatfield(16275)["dir"] == b["dir"],
              "and the newest is the one in force")
        check(len(store.flatfields(16275)) == 2, "both are still listed")
        check(not store.has_flatfield_for(20001),
              "CRUCIALLY: another scanner is not given these tables")

        partial = root / "partial"
        partial.mkdir()
        (partial / "dark_2000x3.npy").write_text("x")
        try:
            store.save_flatfield(16275, partial)
            check(False, "an incomplete table set is refused")
        except FileNotFoundError:
            check(True, "an incomplete table set is refused")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_wizard_states() -> None:
    """The states an operator can be in, and the one that needs a person."""
    import calib_wizard as cw

    section("the calibration wizard's state machine")

    root = Path(tempfile.mkdtemp())
    try:
        store = cs.CalibrationStore(root / "store")
        a = cw.assess(store)
        check(a["state"] == cw.NEEDS_CALIBRATION,
              "an unknown scanner needs calibrating")
        check(a["automatic"] is True,
              "and it happens automatically -- no button, no prompt")
        check(a["may_auto_read"] is False
              and a["device_read_performed"] is False,
              "assessing never reads a device")
        check(all(s["needed"] for s in a["steps"]),
              "every step is outstanding")

        store.save_read({0x52: GOOD52}, source="test")
        a = cw.assess(store)
        check(a["serial"] == 16275, "the stored read names the scanner")
        check(a["state"] == cw.NEEDS_CALIBRATION,
              "a read alone is not a calibration -- the tables are measured, "
              "and they are not on the EEPROM")
        steps = {s["step"]: s for s in a["steps"]}
        check(not steps[cw.STEP_EEPROM]["needed"],
              "and the read step is not repeated")
        check(steps[cw.STEP_BLACK]["needed"] and steps[cw.STEP_DUTY]["needed"],
              "while the searches still are")

        src = root / "built"
        src.mkdir()
        for n in cs.CalibrationStore.FLATFIELD_FILES:
            (src / n).write_text("{}" if n.endswith(".json") else "x")
        store.save_flatfield(16275, src, meta={"config": {}}, source="test")
        a = cw.assess(store)
        check(a["state"] == cw.READY,
              "with both halves stored the scanner is ready")
        check(a["automatic"] is False,
              "and nothing further is attempted -- zero device traffic")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_film_in_gate_is_the_only_prompt() -> None:
    """Film loaded is the one outcome that must never be calibrated through."""
    import calib_wizard as cw

    section("film in the gate")

    # The measured asymmetry, from the owner's own 2026-08-12 pair: an empty
    # gate produces NO sensor opinion at all, so "unavailable" cannot mean
    # "ask" -- that would put a prompt in front of the silent case.
    empty = cw.verdict_from_run({
        "film_sense": {"available": False, "present": None,
                       "status_reports": 0},
        "run_detector": {"state": "clear", "clear_run": 19712,
                         "film_lines": 0}})
    check(empty.present is False,
          "an empty gate is determined by the classifier when the sensors "
          "say nothing")
    check(empty.source == "gate-classifier",
          "and the verdict records which signal decided")

    loaded = cw.verdict_from_run({
        "film_sense": {"available": True, "present": True, "at_entry": True,
                       "at_exit": True, "status_reports": 244},
        "run_detector": {"state": "film", "clear_run": 0,
                         "film_lines": 9984}})
    check(loaded.present is True,
          "film is detected when the sensors report it")
    check(loaded.source == "film-sensors",
          "and the sensors are preferred over the classifier")

    conflict = cw.verdict_from_run({
        "film_sense": {"available": True, "present": True,
                       "status_reports": 12},
        "run_detector": {"state": "clear", "clear_run": 5000,
                         "film_lines": 0}})
    check(conflict.present is True and conflict.source == "film-sensors",
          "a direct sensor reading beats the classifier when they disagree")

    blind = cw.verdict_from_run({"film_sense": {"available": False},
                                 "run_detector": {}})
    check(blind.present is None,
          "and with neither signal the answer is 'undetermined', not 'clear'")

    check(cw.HEADLINES[cw.FILM_IN_GATE] == "Remove the film to finish setup.",
          "the one sentence a person ever sees is one sentence")


def test_wizard_never_writes_repo_calibration() -> None:
    """calibration/ is never modified by an automated step."""
    section("the wizard never writes into calibration/")

    import calib_wizard as cw

    # Behavioural, not a grep: build a wizard and look at where it would
    # actually put things. A text search would be satisfied by renaming a
    # variable, and would trip over the module merely discussing calibration/.
    root = Path(tempfile.mkdtemp())
    try:
        w = cw.Wizard(cs.CalibrationStore(root / "store"))
        repo_cal = (REPO / "calibration").resolve()
        targets = [Path(w.workdir).resolve(),
                   Path(w.candidate_dir("probe")).resolve()]
        check(all(repo_cal not in (t, *t.parents) for t in targets),
              "every directory the wizard writes to is outside calibration/",
              str(targets))
        check(all(Path(w.store.root).resolve() in t.parents for t in targets),
              "and inside the calibration store, which is append-only")
        before = sorted(p.name for p in repo_cal.iterdir())
        w.write_candidate("probe", {"integration_0x82_idx6": 4093})
        after = sorted(p.name for p in repo_cal.iterdir())
        check(before == after,
              "writing a candidate exposure changes nothing in calibration/")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    src = (REPO / "tools/calib_wizard.py").read_text()
    check("--cal-dir" in src,
          "candidate exposures go to pakon_scan.py run --cal-dir instead")

    ps = (REPO / "tools/pakon_scan.py").read_text()
    check('cal_dir=getattr(a, "cal_dir", None)' in ps,
          "and pakon_scan.py run honours --cal-dir")


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
    test_force_still_requires_a_proven_power_cycle()
    test_simulate_never_touches_the_real_store()
    test_serial_index()
    test_profile_sources()
    test_lookup_cannot_reach_a_device()
    test_afe_offset_encoding()
    test_dark_floor_refusal()
    test_vendor_target_is_a_maximum()
    test_flatfield_store_is_append_only()
    test_wizard_states()
    test_film_in_gate_is_the_only_prompt()
    test_wizard_never_writes_repo_calibration()
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
