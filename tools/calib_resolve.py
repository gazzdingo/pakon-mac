#!/usr/bin/env python3
"""Decide WHICH scanner's calibration is in force, without touching a scanner.

    python3 tools/calib_resolve.py               what would be loaded, and why
    python3 tools/calib_resolve.py units         the serial index
    python3 tools/calib_resolve.py use 16275     say which scanner is connected
    python3 tools/calib_resolve.py auto          go back to deciding by itself

WHAT THIS FILE IS FOR
---------------------
The vendor's model, from the F-135 Service Manual (quoted in
backups/eeprom-i2c/README.md):

    "The motherboard has an EEPROM chip built into it to store calibration
     information. The Calibration Wizard program writes all calibration data to
     this EEPROM chip. When the scanner interface software is launched, this
     calibration data in the EEPROM is written to the Windows registry."

So the EEPROM is the source of truth and the registry is a cache. This project
keeps the same shape with one difference that the hardware forces on us: the
vendor refreshes its cache at every launch, and we must not, because on this
hardware every read after the first of a power cycle returns corruption while
still reporting success (backups/eeprom-i2c/README.md, docs/60). Our cache is
therefore filled ONCE, in a scanner's lifetime with this software, and every
launch after that is a pure lookup -- which is exactly what this module does.

THE HARD PART, STATED HONESTLY
------------------------------
Ideally a connected scanner would announce which unit it is, and we would fetch
that unit's stored calibration by serial. It does not. There is no per-unit
identifier readable from this hardware before its EEPROM has been read:

  * every F-135 reports iSerialNumber "010-203-04" -- the string is baked into
    the firmware image, identical across PknInit/Pakon5/Pakon7/Pakon8, so it
    identifies the MODEL and not the machine (docs/01-usb-layer.md);
  * the vendor's own piScannerSerialNumber (docs/04-api-surface.md) is fed from
    the registry, which was fed from the EEPROM -- the vendor has no
    pre-read identity either, it simply re-reads;
  * the serial itself lives at offset 0x0F of the very page we are trying to
    avoid re-reading.

So "look up this scanner by its serial" cannot be completed by asking the
scanner. What CAN be done, and is what this module does, is to make the
question decidable from the store in every case where it has one answer, and
to refuse to guess in the one case where it does not:

  no reads stored          -> PROMPT to read. Never read automatically.
  one unit stored          -> that is the calibration. Load it, no read.
  several units stored     -> ask which scanner is connected, once, and
                              remember. Do not guess: guessing means rendering
                              someone's film through another unit's matrix,
                              which looks plausible and is wrong.
  reads stored, none good  -> say so. Do NOT offer a re-read as the remedy;
                              on this hardware a second read is worse than the
                              first, which is the whole lesson of docs/60.

"One unit stored" is the overwhelmingly common case -- one person, one scanner
-- and it resolves with no device traffic at all, which is the goal.

WHY THIS FILE CANNOT CAUSE A READ
---------------------------------
Structurally, not by discipline. This module imports ``calib_store`` and the
standard library. It does not import ``usb``, it does not import
``calib_device``, and it takes no transport argument, so there is no object
here through which a control transfer could be issued -- the same property
calib_verify.py has, enforced by a test in tools/test_calib.py that reads this
file's own source. If you are tempted to pass a Transport in here to "just
check the serial", that check is a device read, and it is the accident this
whole subsystem exists to prevent.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calib_store as cs        # noqa: E402

# States, in the order a person meets them.
NO_CALIBRATION = "no-calibration"       # nothing stored; a read is needed
UNUSABLE = "unusable"                   # reads exist, none passes the checks
AMBIGUOUS = "ambiguous"                 # several units; which one is plugged in?
UNKNOWN_UNIT = "unknown-unit"           # a serial we have never read
READY = "ready"                         # resolved; use it

# What the app should offer. Note that no value here is ever "read
# automatically" -- ACTION_READ is a prompt for a person to press, and the
# press still lands in calib_read.do_read behind the power-cycle guard.
ACTION_NONE = "none"
ACTION_READ = "prompt-read"
ACTION_CHOOSE = "choose-unit"
ACTION_ATTENTION = "attention"


def resolve(store: cs.CalibrationStore | Path | str | None = None,
            serial_hint: int | None = None) -> dict:
    """Which stored calibration applies, and how confident is that?

    ``serial_hint`` is for a caller that already knows the serial from
    somewhere that is not a device read -- the user typed it off the label on
    the scanner, or a read that just happened returned it. It is never obtained
    by asking the hardware, because asking the hardware IS the read.

    The returned dict always carries ``device_read_performed: False``. It is
    not decoration: it is the postcondition this function is for, and the test
    suite asserts it on every branch.
    """
    st = store if isinstance(store, cs.CalibrationStore) else cs.CalibrationStore(store)
    index = st.unit_index()
    serials = index["serials"]
    active = index["active"]

    out = {
        "store": str(st.root),
        "device_read_performed": False,
        "may_auto_read": False,
        "serials": serials,
        "active_unit": active,
        "unattributed": index["unattributed"],
        "serial": None,
        "stamp": None,
        "dir": None,
        "record": None,
        "reason": "",
        "warnings": [],
    }

    # 1. A caller that knows the serial gets a direct answer, right or wrong.
    if serial_hint is not None:
        rec = st.best_for_serial(int(serial_hint))
        if rec is None:
            out.update(
                state=UNKNOWN_UNIT, action=ACTION_READ, serial=int(serial_hint),
                headline=f"Scanner {int(serial_hint)} has no stored calibration.",
                reason=(
                    f"No good read in this store belongs to serial "
                    f"{int(serial_hint)}. "
                    + (f"The store holds {len(serials)} other unit(s): "
                       f"{', '.join(str(s) for s in serials)}. Their "
                       f"calibration describes their optics and lamps, not "
                       f"this one's, so none of it is applied."
                       if serials else
                       "This store is empty.")
                    + " Its calibration can be read once -- see "
                      "tools/calib_read.py -- and nothing will be read until "
                      "someone asks for it."))
            return out
        return _ready(out, st, rec, why=f"serial {int(serial_hint)} was supplied "
                                        f"by the caller")

    # 2. Nothing stored at all.
    if not serials:
        if index["unattributed"]:
            out.update(
                state=UNUSABLE, action=ACTION_ATTENTION,
                headline="Calibration has been read, but none of it is usable.",
                reason=(
                    f"{len(index['unattributed'])} read(s) are stored and none "
                    f"passes the structural checks, so none can be attributed "
                    f"to a scanner. Every one is kept -- nothing here is ever "
                    f"deleted -- and they are worth looking at by hand.\n\n"
                    f"Do NOT re-read hoping for a better result. On this "
                    f"hardware the second read of a power cycle is worse than "
                    f"the first and the status still says 'ok'. A genuine "
                    f"retry means powering the scanner off, powering it on, "
                    f"and reading as the FIRST transaction of that cycle."))
            return out
        out.update(
            state=NO_CALIBRATION, action=ACTION_READ,
            headline="This scanner's calibration has not been read yet.",
            reason=(
                "Nothing is stored. The scanner's own EEPROM holds the "
                "calibration the factory measured for it, and it can be read "
                "once, now, and then never again. Until that happens the "
                "software falls back on reference values that describe a "
                "different machine.\n\nNothing has been sent to any scanner, "
                "and nothing will be until this is asked for explicitly."))
        return out

    # 3. The user has named the connected unit.
    if active is not None:
        rec = st.best_for_serial(active)
        if rec is not None:
            r = _ready(out, st, rec, why="you said this is the scanner that is "
                                         "connected")
            if len(serials) > 1:
                r["warnings"].append(
                    f"{len(serials)} scanners have been read on this machine "
                    f"({', '.join(str(s) for s in serials)}) and nothing on "
                    f"this hardware says which one is plugged in now. Serial "
                    f"{active} is in use because it was chosen, not because it "
                    f"was detected. Change it with: calib_resolve.py use "
                    f"<serial>")
            return r
        out["warnings"].append(
            f"The scanner chosen earlier (serial {active}) has no good read in "
            f"this store any more. Falling back to deciding automatically.")

    # 4. Exactly one unit: no ambiguity to resolve, and no read to justify.
    if len(serials) == 1:
        rec = st.best_for_serial(serials[0])
        return _ready(out, st, rec,
                      why="it is the only scanner this store has ever read")

    # 5. More than one. This is the case where guessing is the wrong answer.
    out.update(
        state=AMBIGUOUS, action=ACTION_CHOOSE,
        headline=f"{len(serials)} scanners have been read here. "
                 f"Which one is connected?",
        reason=(
            f"Stored: {', '.join(str(s) for s in serials)}. Nothing readable "
            f"from a connected F-135 distinguishes one unit from another -- "
            f"they all report the same USB serial ('010-203-04', baked into "
            f"the firmware image), and the real serial only exists inside the "
            f"calibration page itself.\n\nSo this has to be answered by a "
            f"person, once. Guessing would mean rendering film through the "
            f"other scanner's colour matrix and lamp calibration, which "
            f"produces a plausible-looking and wrong picture. Choosing costs "
            f"one click; being wrong costs every scan until someone notices."))
    return out


def _ready(out: dict, st: cs.CalibrationStore, rec: cs.ReadRecord,
           why: str) -> dict:
    out.update(
        state=READY, action=ACTION_NONE, serial=rec.serial, stamp=rec.stamp,
        dir=str(rec.path), record=rec.summary(),
        headline=f"Using scanner {rec.serial}'s own calibration "
                 f"({rec.stamp}). No read is needed.",
        reason=f"Chosen because {why}. It passed the structural checks when it "
               f"was saved, and it is used from disk -- the scanner is not "
               f"touched.")
    # Provenance matters here in a way it usually does not. A record whose
    # source is a rehearsal carries real bytes only if the rehearsal was fed
    # real bytes, and a person deciding whether to trust a render should be
    # told rather than have to go and read read.json.
    src = str((rec.meta or {}).get("source") or "")
    if "simulate" in src or "sim" == src:
        out["warnings"].append(
            f"This record was written by a REHEARSAL ({src}), not by a live "
            f"read of the scanner. Its bytes are whatever the rehearsal was "
            f"given -- for this project that is the owner's own verified page "
            f"from backups/eeprom-i2c/, so the values are real, but the record "
            f"is not itself evidence that this scanner was read.")
    # Later reads that failed the checks are deliberately NOT described as
    # belonging to this scanner: a page that does not parse has no trustworthy
    # serial, so which unit it came from is exactly what is unknown about it.
    # What IS certain is that it is newer and is not being used, and that is
    # the thing a person would otherwise be surprised by.
    later = [r for r in st.list_reads() if r.stamp > rec.stamp and not r.is_good]
    if later:
        out["warnings"].append(
            f"{len(later)} later read(s) are stored that do not pass the "
            f"structural checks, so they cannot be attributed to any scanner "
            f"and none of them is in use -- the newest is {later[0].stamp}. "
            f"That is the append-only store doing its job: a degraded read "
            f"lands beside the good one instead of on top of it. Do not read "
            f"again to 'fix' this; on this hardware the second read of a power "
            f"cycle is the degraded one.")
    return out


# --------------------------------------------------------------------------

def _fmt(rep: dict) -> str:
    lines = [f"store    {rep['store']}",
             f"state    {rep['state']}    action  {rep['action']}",
             "",
             rep["headline"], "", rep["reason"]]
    for w in rep["warnings"]:
        lines += ["", f"  ** {w}"]
    if rep["serials"]:
        lines += ["", "scanners in this store: "
                      + ", ".join(str(s) for s in rep["serials"])]
    if rep["unattributed"]:
        lines += [f"unattributable reads:   {len(rep['unattributed'])} "
                  f"(kept; none is ever deleted)"]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Decide which stored calibration applies. Never opens USB, "
                    "never reads a scanner, never deletes anything.")
    ap.add_argument("--store", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("status")
    sub.add_parser("units")
    u = sub.add_parser("use"); u.add_argument("serial", type=int)
    sub.add_parser("auto")
    a = ap.parse_args()

    st = cs.CalibrationStore(a.store)
    cmd = a.cmd or "status"

    if cmd == "use":
        if not st.has_calibration_for(a.serial):
            print(f"no good stored calibration for scanner {a.serial}. "
                  f"Stored: {st.unit_index()['serials'] or 'nothing'}",
                  file=sys.stderr)
            return 1
        st.select_unit(a.serial)
        print(f"using scanner {a.serial}")
        return 0
    if cmd == "auto":
        st.select_unit(None)
        print("deciding automatically again")
        return 0
    if cmd == "units":
        idx = st.unit_index()
        if a.json:
            print(json.dumps(idx, indent=2, sort_keys=True))
            return 0
        print(f"store {st.root}\n")
        if not idx["serials"]:
            print("  no scanner has been identified from a stored read yet.")
        for s in idx["serials"]:
            u = idx["units"][str(s)]
            mark = "->" if idx["active"] == s else "  "
            print(f" {mark} scanner {s}   best {u['best']}")
            for r in u["reads"]:
                flag = "good" if r["good"] else ("usable" if r["usable"] else "BAD ")
                print(f"        {r['stamp']}  [{flag}]  {r['headline']}")
        if idx["unattributed"]:
            print(f"\n  {len(idx['unattributed'])} read(s) could not be "
                  f"attributed to a scanner (kept, never deleted):")
            for r in idx["unattributed"]:
                print(f"        {r['stamp']}  claims serial "
                      f"{r.get('claimed_serial')}  {r['headline']}")
        return 0

    rep = resolve(st)
    print(json.dumps(rep, indent=2, sort_keys=True) if a.json
          else "\n" + _fmt(rep) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
