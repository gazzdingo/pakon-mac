#!/usr/bin/env python3
"""Read this scanner's calibration once, back it up, and never touch it again.

    python3 tools/calib_read.py status        what is stored, what is in force
    python3 tools/calib_read.py read          read (only if it is safe to)
    python3 tools/calib_read.py --simulate read     rehearse with no hardware
    python3 tools/calib_read.py use <stamp>   use an earlier stored read

--simulate is a REHEARSAL. It gets a simulated scanner and a scratch store in
a temporary directory, and the real store is not opened for writing at all. A
rehearsal record in the real store is not a cosmetic mistake: the store is
what decides whether a genuine read is still needed, so one simulated record
makes the software believe the job is done and blocks the real read.

WHAT IT DOES, AND WHY IN THIS ORDER
-----------------------------------
1. Refuse to run at all if a write-capable firmware has been un-quarantined,
   or if the pinned read-only firmware does not match its audited hash.
2. If a good calibration is already stored, STOP. Do not read. Say what is
   stored and where. Re-reading is never automatic, because on this hardware
   a second read is not a retry -- it destroys the thing it is checking.
3. Ask the scanner, via its own volatile RAM, whether this power cycle has
   already produced a read. Refuse unless a fresh cycle is positively seen.
   --force overrides step 2 and only step 2. It makes this step STRICTER, not
   weaker: an additional read must witness the scanner's RAM losing a marker
   we ourselves planted, because "no marker" alone is not evidence of a power
   cycle. If that cannot be shown, refuse and mark the scanner so that the
   next attempt, after a power cycle, can show it.
4. Load the pinned read-only firmware; stamp the read-once marker BEFORE the
   8051 is released, so the marker precedes any I2C transaction.
5. Read every device on the bus, 0x50-0x57, exactly once each.
6. Write the bytes to disk and to the manifest BEFORE anything interprets
   them. If this process dies afterwards, the data is already safe.
7. Only then verify -- by structure, never by reading again.

THE ONE THING TO UNDERSTAND
---------------------------
From backups/eeprom-i2c/README.md, established on this hardware: these
EEPROMs return good data on the FIRST transaction after a power cycle and
degrade on every read after it, while still reporting status "ok". A 7-pass
"is it stable?" run once declared 256 bytes of 0xFF trustworthy. Every
instinct that says "read it again to be sure" is, here, an instinct to
destroy irreplaceable data. See docs/60-calibration-safety.md.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(HERE))

import calib_device as cd       # noqa: E402
import calib_resolve as cres    # noqa: E402
import calib_store as cs        # noqa: E402
import calib_verify as cv       # noqa: E402


def _sim_transport() -> cd.SimTransport:
    """A stand-in scanner carrying the owner's real, verified page, so a
    rehearsal exercises the true structure rather than invented bytes."""
    repo = HERE.parent
    contents = {}
    p52 = repo / "backups/eeprom-i2c/eeprom_52.bin"
    p51 = repo / "backups/eeprom-i2c/eeprom_51.bin"
    if p52.is_file():
        contents[0x52] = p52.read_bytes()
    if p51.is_file():
        contents[0x51] = p51.read_bytes()
    if not contents:
        contents = {0x52: bytes(256)}
    return cd.SimTransport(contents)


def _same_path(a: Path, b: Path) -> bool:
    try:
        return Path(a).expanduser().resolve() == Path(b).expanduser().resolve()
    except OSError:
        return False


def open_store(explicit: Path | None, *,
               simulate: bool) -> tuple[cs.CalibrationStore, Path | None]:
    """Pick the store this run may write to. A rehearsal never gets the real one.

    Returns (store, scratch_dir_or_None).

    A --simulate run is a dry run and must be able to leave nothing behind in
    the real store, so it is given a fresh scratch directory instead. The
    reason this matters is specific rather than tidy-minded: the store is the
    thing do_read() consults to decide whether a genuine read is still needed
    (has_calibration), so a single simulated record there makes the software
    believe this scanner's calibration has already been captured and refuse
    the real read. That happened on 2026-08-08 on the owner's machine.

    Pointing --store at the real store while simulating is refused outright
    rather than quietly obeyed, because there is no honest reason to rehearse
    into the one place a rehearsal must not reach.
    """
    if not simulate:
        return cs.CalibrationStore(explicit), None
    real = cs.default_store()
    if explicit is not None:
        root = Path(explicit).expanduser()
        if _same_path(root, real):
            raise SystemExit(
                f"--simulate will not write to the real calibration store "
                f"({real}).\nA rehearsal record there would make the software "
                f"believe this scanner has already been read and stop it "
                f"taking the genuine read.\nDrop --store to rehearse in a "
                f"scratch directory, or point it somewhere disposable.")
        return cs.CalibrationStore(root), None
    scratch = Path(tempfile.mkdtemp(prefix="pakon-calib-rehearsal-"))
    return cs.CalibrationStore(scratch), scratch


def connect_report(store: cs.CalibrationStore, transport: cd.Transport,
                   guard: cd.PowerCycleGuard) -> dict:
    """What the app shows on connect. Causes no I2C traffic whatsoever.

    The scanner state comes from USB enumeration and the marker probe, which
    are 0xA0 requests answered by the FX2's USB core in hardware; the
    calibration half is a pure lookup in the store, done by calib_resolve. No
    branch of this function can reach I2C, and none of it decides to read --
    ``action`` is at most a suggestion for a button.
    """
    sel = store.selection()
    have = store.has_calibration()
    state = transport.state()
    res = cres.resolve(store)
    out = {
        "scanner": {"state": state, "id": transport.describe()},
        "have_calibration": have,
        "selection": sel,
        "resolution": res,
        "store": str(store.root),
    }
    if res["state"] == cres.AMBIGUOUS:
        # Several units in the store and nothing readable says which is
        # plugged in. Reading would answer it and is precisely what must not
        # happen automatically, so this asks the person instead.
        out["action"] = "choose-unit"
        out["headline"] = res["headline"]
        return out
    if have:
        out["action"] = "none"
        # Deliberately not "calibration for THIS scanner is saved". Nothing
        # here has established that the connected unit is the stored one --
        # every F-135 reports the same USB serial, and the real serial is
        # inside the page we are avoiding re-reading. Naming the serial lets
        # the owner check it against the label; claiming identity we have not
        # established would be a lie the software cannot back up.
        out["headline"] = (
            f"Using stored calibration for scanner {res['serial']} "
            f"({sel['stamp']}). Nothing will be read from the scanner."
            if res["serial"] is not None else
            f"A stored calibration is in force ({sel['stamp']}). It will not "
            f"be read again.")
    elif state == cd.DEVICE_ABSENT:
        out["action"] = "connect-scanner"
        out["headline"] = ("No calibration is stored yet, and no scanner is "
                           "connected.")
    else:
        chk = guard.check()
        out["guard"] = chk
        out["action"] = "read" if chk["may_read"] else "wait"
        out["headline"] = (
            "No calibration is stored for this scanner yet. It can be read "
            "now." if chk["may_read"] else
            f"No calibration is stored yet, and it cannot be read right now. "
            f"{chk['reason']}")
    return out


def do_read(store: cs.CalibrationStore, transport: cd.Transport,
            guard: cd.PowerCycleGuard, *, force: bool = False,
            source: str = "calib_read") -> dict:
    """The whole protected read. Returns a report; raises ReadRefused if not."""
    cd.assert_safe_installation()

    # A simulated scanner's bytes may not enter the real store, whoever asks.
    # open_store() keeps the CLI honest; this keeps every other caller honest
    # too, because the damage does not depend on which layer made the mistake:
    # a rehearsal record in the real store reads as "already captured" and
    # blocks the genuine read.
    if isinstance(transport, cd.SimTransport) and _same_path(store.root,
                                                             cs.default_store()):
        raise cd.ReadRefused(
            f"This is a simulated scanner and the store it was given is the "
            f"real calibration store ({store.root}). A simulated record there "
            f"would make the software believe this scanner's calibration has "
            f"already been read and refuse the genuine read. Nothing was "
            f"written, and nothing was sent to any scanner.")

    ok, why = cd.firmware_ok()
    if not ok:
        raise cd.ReadRefused(why)

    if store.has_calibration() and not force:
        sel = store.selection()
        raise cd.ReadRefused(
            f"A good calibration for this scanner is already saved "
            f"({sel['stamp']}, in {sel['dir']}).\n\n"
            f"It will not be read again. On this hardware a second read "
            f"returns corrupted data while still reporting success, so "
            f"re-reading risks the only copy that exists and gains nothing. "
            f"Nothing was sent to the scanner.\n\n"
            f"If you genuinely need another read -- a different scanner, or "
            f"to compare across power cycles -- pass --force. That does not "
            f"skip the power cycle: it still requires this software to SEE "
            f"the scanner's memory cleared before it will read. The existing "
            f"read is kept either way; nothing is ever overwritten or deleted.")

    # Everything from the decision to the stamp happens under one lock. Two
    # instances started together would otherwise both see a fresh cycle and
    # both read -- the second corrupting what the first captured.
    with cd.ReadLock(store.root / "journal" / "read.lock"):
        # --force overrides "one is already stored". It does NOT override the
        # power cycle, which is a fact about the hardware and not a policy:
        # forcing a read at the wrong moment is what produced 256 bytes of
        # 0xFF from 0x52 on 2026-08-08. Under force the freshness test gets
        # STRICTER, not weaker -- it must positively witness the cycle.
        chk = guard.check(require_power_cycle_witness=force)
        if not chk["may_read"]:
            # A read taken but never saved? Its bytes are still in FX2 RAM.
            if chk["code"] == "already-read" and guard.unsaved_nonce():
                return _salvage(store, transport, guard, source)
            if chk["code"] == "no-witness":
                raise cd.ReadRefused(
                    chk["reason"] + "\n\n" + _arm_for_force(guard, source))
            raise cd.ReadRefused(chk["reason"])

        nonce_box = {}

        def _stamp():
            nonce_box["nonce"] = guard.stamp()
            guard.note("read", nonce=nonce_box["nonce"], source=source)

        out = cd.read_bus(transport, before_run=_stamp)

        if not out["devices"]:
            guard.note("empty", nonce=nonce_box.get("nonce"),
                       status=out["status_raw"])
            raise cd.ReadRefused(
                "No device on the bus answered at any address from 0x50 to "
                "0x57.\n"
                + "\n".join(f"  0x{a:02x}: {r['text']}"
                            for a, r in sorted(out["results"].items()))
                + "\n\nNothing was written to the scanner. The read-once "
                  "marker is set for this power cycle, so power-cycle before "
                  "retrying.")

        # Bytes to disk BEFORE anything interprets them.
        rec = store.save_read(out["devices"], source=source,
                              session={"nonce": nonce_box.get("nonce"),
                                       "status": out["status_raw"],
                                       "complete": out["complete"],
                                       "salvaged": out.get("salvaged", False)})
        guard.note("saved", nonce=nonce_box.get("nonce"), stamp=rec.stamp,
                   dir=str(rec.path))
        return {"record": rec, "raw": out, "salvaged": False}


def _arm_for_force(guard: cd.PowerCycleGuard, source: str) -> str:
    """Leave the user able to satisfy the requirement, not merely refused.

    Freshness could not be established because there is no nonce of ours known
    to have been in this scanner's RAM. Put one there, so that after a power
    cycle its absence proves what an empty region cannot.
    """
    try:
        guard.arm(source=source)
    except Exception as e:                                  # noqa: BLE001
        return (f"A witness could not be placed in the scanner's memory "
                f"({e.__class__.__name__}: {e}), so the next attempt cannot "
                f"prove a power cycle either. Check the USB connection. "
                f"Nothing was sent to the scanner's EEPROM.")
    return ("A witness has now been placed in the scanner's volatile memory. "
            "That is one write to FX2 RAM: no I2C transaction happened, and "
            "nothing on any EEPROM was read, written or disturbed.\n\n"
            "Now power the scanner OFF, wait a few seconds, power it ON, and "
            "run the same command again. Its memory will have forgotten the "
            "witness, and that -- rather than an assumption -- is what will "
            "prove the power cycle. Do not load firmware or run any other "
            "tool in between; the read must be the first transaction of the "
            "new cycle.")


def _salvage(store: cs.CalibrationStore, transport: cd.Transport,
             guard: cd.PowerCycleGuard, source: str) -> dict:
    out = cd.salvage_from_ram(transport)
    if not out["devices"]:
        raise cd.ReadRefused(
            "This power cycle already produced a read that was never saved, "
            "and nothing usable remains in the scanner's RAM to recover. "
            "Power-cycle the scanner and read again. Nothing was sent to the "
            "scanner.")
    rec = store.save_read(out["devices"], source=f"{source} (salvaged from RAM)",
                          session={"salvaged": True,
                                   "status": out["status_raw"]})
    guard.note("saved", nonce=guard.unsaved_nonce(), stamp=rec.stamp,
               dir=str(rec.path), salvaged=True)
    return {"record": rec, "raw": out, "salvaged": True}


# --------------------------------------------------------------------------

def _print_record(rec: cs.ReadRecord, salvaged: bool) -> None:
    print("\n  Calibration saved."
          + ("  (recovered from the scanner's RAM -- no second read was "
             "made)" if salvaged else ""))
    print(f"  {rec.path}\n")
    for key in sorted(rec.devices):
        e = rec.devices[key]
        print(f"    0x{e['addr7']:02x}  {e['state']:<12} {e['summary']}")
    if rec.meta.get("unit", {}).get("known"):
        print(f"\n  Scanner serial {rec.meta['unit']['serial']}")
    print("\n  This will not be read again. Nothing was written to the "
          "scanner.")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--store", type=Path, default=None)
    ap.add_argument("--simulate", action="store_true",
                    help="rehearse against a simulated scanner; no hardware, "
                         "no USB, and a scratch store -- the real store is "
                         "never written to")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("status")
    r = sub.add_parser("read")
    r.add_argument("--force", action="store_true",
                   help="permit an additional read even though a calibration "
                        "is already stored. It does NOT skip the power cycle: "
                        "the read still waits until this software has "
                        "positively witnessed the scanner's memory being "
                        "cleared, which usually takes two runs -- one to mark "
                        "the scanner, then power-cycle, then this one again")
    u = sub.add_parser("use"); u.add_argument("stamp")
    sub.add_parser("auto")
    a = ap.parse_args()
    cmd = a.cmd or "status"

    store, scratch = open_store(a.store, simulate=a.simulate)
    journal = store.root / "journal"
    if a.simulate:
        print("\n  REHEARSAL. Simulated scanner, no USB.")
        print(f"  rehearsal store  {store.root}"
              + ("  (scratch, delete it whenever)" if scratch else ""))
        print(f"  real store       {cs.default_store()}  -- not touched")

    if cmd == "use":
        try:
            store.select(a.stamp)
        except KeyError:
            print(f"no stored calibration named {a.stamp}", file=sys.stderr)
            return 1
        print(f"using {a.stamp}")
        return 0
    if cmd == "auto":
        store.clear_selection()
        print("using the newest read")
        return 0

    try:
        cd.assert_safe_installation()
    except cd.UnsafeToolState as e:
        print(f"\nREFUSING TO RUN\n\n{e}\n", file=sys.stderr)
        return 2

    if a.simulate:
        transport: cd.Transport = _sim_transport()
    else:
        try:
            transport = cd.UsbTransport()
        except ImportError:
            print("pyusb is not installed; use --simulate to rehearse "
                  "without hardware.", file=sys.stderr)
            return 2
    guard = cd.PowerCycleGuard(transport, journal)

    if cmd == "status":
        rep = connect_report(store, transport, guard)
        print(f"\nscanner  {rep['scanner']['id']}  ({rep['scanner']['state']})")
        print(f"store    {rep['store']}")
        print(f"\n{rep['headline']}")
        for w in rep["resolution"]["warnings"]:
            print(f"\n  ** {w}")
        sel = rep["selection"]
        if sel["reads"]:
            if sel["message"]:
                print(f"\n  ** {sel['message']}")
            print(f"\n{len(sel['reads'])} stored read(s), newest first "
                  f"-- none is ever deleted:\n")
            for x in sel["reads"]:
                mark = "->" if x["stamp"] == sel["stamp"] else "  "
                flag = "good" if x["good"] else ("usable" if x["usable"] else "BAD ")
                print(f" {mark} {x['stamp']}  [{flag}]  serial {x['serial']}")
                print(f"      {x['headline']}")
                for dv in x["devices"]:
                    print(f"        {dv['label']}  {dv['state']:<12} "
                          f"0xFF {dv['ff']}/{dv['bytes']}  "
                          f"checks {dv['checks_passed']}/{dv['checks_total']}")
            print("\n  Select another with:  calib_read.py use <stamp>")
        print()
        return 0

    # read
    try:
        res = do_read(store, transport, guard, force=a.force,
                      source="calib_read --simulate" if a.simulate
                             else "calib_read")
    except cd.ReadRefused as e:
        print(f"\nNot reading.\n\n{e}\n")
        return 1
    except cd.UnsafeToolState as e:
        print(f"\nREFUSING TO RUN\n\n{e}\n", file=sys.stderr)
        return 2
    _print_record(res["record"], res["salvaged"])
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
