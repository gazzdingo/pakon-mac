#!/usr/bin/env python3
"""Append-only store for scanner calibration reads. Nothing here deletes.

THE RULE, FROM THE OWNER
------------------------
    "never delete a calibration always keep them on disk just timestamp them
     and use the latest timestamp -- the user can then override by selecting
     another one"

So: every read becomes a NEW timestamped directory. Nothing is overwritten,
nothing is removed -- not on re-read, not on reinstall, not on cleanup. The
newest is used by default and the user may select an older one instead.

WHY THIS IS THE RIGHT SHAPE FOR THIS DATA SPECIFICALLY
------------------------------------------------------
The known failure mode of these EEPROMs is that a later read is WORSE than an
earlier one -- they degrade on every read after the first in a power cycle,
silently, with the I2C status still reporting "ok". An append-only store
inverts the danger completely:

  * a degraded re-read cannot destroy the good copy, because it lands beside
    it rather than on top of it;
  * the good earlier read stays selectable forever;
  * so the existence of a "read calibration" control stops being dangerous,
    which is most of why the control was frightening in the first place.

That is the entire argument for append-only here, and it is why this module
contains no delete path at all. There is no unlink, no rmtree, no truncate,
no "w" mode on an existing file. Saved images are additionally chmod'ed to
read-only (0444) so that a later bug in some other tool cannot rewrite them
either. Making the wrong thing impossible beats remembering not to do it.

LAYOUT
------
    <store>/reads/<UTC timestamp>/eeprom_5N.bin   one per device that answered
    <store>/reads/<UTC timestamp>/read.json       metadata + structural verdicts
    <store>/SHA256SUMS                            append-only manifest
    <store>/selected.json                         the user's override, if any
    <store>/active-unit.json                      which SCANNER is in force
    <store>/units/<serial>/overlay/<stamp>.json   per-unit values not on the
                                                  page we can read (see
                                                  calib_profile.py)

WHY THERE IS A SERIAL INDEX AS WELL AS A TIMESTAMP INDEX
--------------------------------------------------------
The timestamp answers "which read", which is the right question while one
scanner is involved. As soon as a second scanner has ever been read on the same
machine it is the wrong question, because the newest read may belong to the
other unit and applying it would mean rendering someone's film through another
scanner's colour matrix -- wrong in a way that looks plausible.

So reads are also grouped by the serial number their calibration page carries,
and only a GOOD read's serial is believed: a degraded page's serial field is
just four corrupted bytes, and treating it as an identity would invent scanners
that do not exist. See ReadRecord.serial.

This index adds queries only. It deletes nothing, it rewrites nothing, and the
pointer files it introduces (active-unit.json) name a serial rather than
containing calibration, so losing one costs a click and never data.

<store> defaults to the platform application-data directory (matching
pakon_app.py's _app_dir) and can be overridden with $PAKON_CALIBRATION_DIR.
It is deliberately NOT the repo's backups/ directory: backups/ holds the
owner's own irreplaceable copies and this software must never write there.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calib_verify as cv   # noqa: E402

STAMP_FMT = "%Y-%m-%dT%H-%M-%SZ"
STAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z(-\d+)?$")
MANIFEST = "SHA256SUMS"
SELECTED = "selected.json"
ACTIVE_UNIT = "active-unit.json"
UNITS_DIR = "units"


def default_store() -> Path:
    env = os.environ.get("PAKON_CALIBRATION_DIR")
    if env:
        return Path(env).expanduser()
    home = Path.home()
    if sys.platform == "darwin":
        base = home / "Library" / "Application Support" / "PakonScan"
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or home) / "PakonScan" / "data"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or home / ".local/share") / "PakonScan"
    return base / "calibration"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _freeze(p: Path) -> None:
    """Drop write permission. A saved calibration is finished business."""
    try:
        p.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    except OSError:
        pass


class CalibrationStore:
    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else default_store()
        self.reads_dir = self.root / "reads"

    # -- writing ---------------------------------------------------------
    def save_read(self, devices: dict[int, bytes], *, source: str,
                  session: dict | None = None,
                  stamp: str | None = None) -> "ReadRecord":
        """Persist one power cycle's read. Called BEFORE anything else looks
        at the data -- that ordering is the requirement, not a nicety.

        `devices` maps 7-bit I2C address -> exactly the bytes that came off
        the wire. Bytes hit the disk first; verdicts are computed afterwards
        and written to read.json. If this process dies midway the images
        still exist and the manifest still names them.
        """
        self.reads_dir.mkdir(parents=True, exist_ok=True)
        stamp = stamp or time.strftime(STAMP_FMT, time.gmtime())

        # Never reuse a directory. If one exists, make a new name -- do not
        # even consider writing into it.
        d = self.reads_dir / stamp
        n = 0
        while d.exists():
            n += 1
            d = self.reads_dir / f"{stamp}-{n}"
        d.mkdir(parents=True)

        # 1. the bytes, first, before any interpretation
        written = []
        for addr in sorted(devices):
            data = devices[addr]
            path = d / f"eeprom_{addr:02x}.bin"
            with open(path, "xb") as fh:      # "x" -- refuses to clobber
                fh.write(data)
            _freeze(path)
            written.append((path, _sha256(data)))
        self._append_manifest(written)

        # 2. only now interpret it
        entries = {}
        for addr in sorted(devices):
            r = cv.verify(devices[addr], addr7=addr)
            entries[f"{addr:02x}"] = {
                "addr7": addr,
                "file": f"eeprom_{addr:02x}.bin",
                "bytes": len(devices[addr]),
                "sha256": _sha256(devices[addr]),
                "state": r["state"],
                "kind": r["kind"],
                "summary": r["summary"],
                "stats": r["stats"],
                "checks": r["checks"],
                "serial": r["info"].get("serial"),
                "crc": r["crc"],
            }
        meta = {
            "cross_page": cv.cross_page_checks(devices),
            "stamp": d.name,
            "saved_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": source,
            "session": session or {},
            "devices": entries,
            "unit": self._fingerprint(entries),
            "tool": "calib_store/1",
        }
        mp = d / "read.json"
        with open(mp, "x") as fh:
            json.dump(meta, fh, indent=2, sort_keys=True)
        self._append_manifest([(mp, _sha256(mp.read_bytes()))])
        _freeze(mp)
        return ReadRecord(d, meta)

    def _append_manifest(self, items: list[tuple[Path, str]]) -> None:
        """Append-only, sha256sum format -- same as backups/*/SHA256SUMS."""
        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.root / MANIFEST, "a") as fh:
            for path, digest in items:
                fh.write(f"{digest}  {path.relative_to(self.root)}\n")

    @staticmethod
    def _fingerprint(entries: dict) -> dict:
        """Identity of the scanner this read came from.

        Recorded so a later read can be COMPARED against it, not so that
        anything is prevented -- there is no identifier readable from this
        hardware before you read the EEPROM (see docs/60).
        """
        cal = next((e for e in entries.values()
                    if e["kind"] == cv.KIND_CALIBRATION
                    and e["state"] == cv.GOOD), None)
        if not cal:
            return {"known": False}
        return {"known": True, "serial": cal["serial"],
                "sha256": cal["sha256"], "addr7": cal["addr7"]}

    # -- reading ---------------------------------------------------------
    def list_reads(self) -> list["ReadRecord"]:
        """Newest first."""
        if not self.reads_dir.is_dir():
            return []
        out = []
        for d in self.reads_dir.iterdir():
            if not d.is_dir() or not STAMP_RE.match(d.name):
                continue
            meta_path = d / "read.json"
            meta = {}
            if meta_path.is_file():
                try:
                    meta = json.loads(meta_path.read_text())
                except (OSError, json.JSONDecodeError):
                    meta = {}
            out.append(ReadRecord(d, meta))
        out.sort(key=lambda r: r.stamp, reverse=True)
        return out

    def get(self, stamp: str) -> "ReadRecord | None":
        return next((r for r in self.list_reads() if r.stamp == stamp), None)

    # -- selection -------------------------------------------------------
    def select(self, stamp: str) -> None:
        """User override. Writing this never removes anything."""
        if self.get(stamp) is None:
            raise KeyError(stamp)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / SELECTED).write_text(
            json.dumps({"stamp": stamp,
                        "set_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                 time.gmtime())}, indent=2))

    def clear_selection(self) -> None:
        """Return to 'use the newest'. The override file is emptied, not the
        calibration -- no read is ever removed."""
        p = self.root / SELECTED
        if p.is_file():
            p.write_text(json.dumps({"stamp": None}))

    def selection(self) -> dict:
        """Which calibration is in force, and is that a problem?

        Default is the newest, exactly as the owner specified. When the newest
        is unusable and an older one is good, this reports it loudly and names
        the better one -- but does NOT silently switch, because silently using
        something other than what the list says is in force is its own trap.
        """
        reads = self.list_reads()
        if not reads:
            return {"stamp": None, "reason": "no calibration has been read yet",
                    "reads": [], "needs_attention": False}

        newest = reads[0]
        chosen, reason, override = newest, "newest read", False
        sel_path = self.root / SELECTED
        if sel_path.is_file():
            try:
                want = json.loads(sel_path.read_text()).get("stamp")
            except (OSError, json.JSONDecodeError):
                want = None
            if want:
                picked = next((r for r in reads if r.stamp == want), None)
                if picked is not None:
                    chosen, reason, override = picked, "chosen by you", True
                else:
                    reason = ("your chosen calibration is not in the store; "
                              "using the newest")

        best_good = next((r for r in reads if r.is_good), None)
        out = {
            "stamp": chosen.stamp,
            "dir": str(chosen.path),
            "reason": reason,
            "user_override": override,
            "usable": chosen.is_usable,
            "good": chosen.is_good,
            "needs_attention": False,
            "message": "",
            "reads": [r.summary() for r in reads],
        }
        if not chosen.is_good and best_good is not None:
            out["needs_attention"] = True
            out["better_available"] = best_good.stamp
            out["message"] = (
                f"The calibration in force ({chosen.stamp}) does not pass the "
                f"structural checks: {chosen.worst_summary}. An earlier read "
                f"({best_good.stamp}) does pass. Nothing has been changed for "
                f"you -- select that earlier read if you want it used. Both "
                f"are kept; neither is ever deleted.")
        elif not chosen.is_good:
            out["needs_attention"] = True
            out["message"] = (
                f"The calibration in force ({chosen.stamp}) does not pass the "
                f"structural checks: {chosen.worst_summary}. There is no "
                f"better read stored. Do NOT re-read hoping to improve it -- "
                f"on this hardware a second read is worse than the first. See "
                f"docs/60-calibration-safety.md.")
        return out

    def has_calibration(self) -> bool:
        return any(r.is_good for r in self.list_reads())

    # -- the serial index ------------------------------------------------
    #
    # Every method below is a query over reads that are already on disk. None
    # of them opens USB, none of them writes a calibration, and none of them
    # can cause a read: this half of the file is as inert as calib_verify.
    def units(self) -> dict[int, dict]:
        """Group the stored reads by the scanner they came from.

        Keyed by serial number, newest read first within each unit. Only GOOD
        reads carry a serial (see ReadRecord.serial), so a degraded page's four
        corrupted bytes never conjure a phantom scanner into this index.

        Reads whose serial is unknown are NOT dropped -- they appear under
        ``unattributed`` in :meth:`unit_index`, because a read that exists and
        cannot be attributed is a thing a person needs to see, not a thing to
        quietly omit.
        """
        out: dict[int, dict] = {}
        for r in self.list_reads():          # already newest-first
            s = r.serial
            if s is None:
                continue
            u = out.setdefault(s, {"serial": s, "reads": [], "best": None})
            u["reads"].append(r)
            if u["best"] is None and r.is_good:
                u["best"] = r
        return out

    def unit_index(self) -> dict:
        """The serial index in plain data, for the app and the CLI."""
        units = self.units()
        attributed = {stamp
                      for u in units.values() for stamp in
                      (x.stamp for x in u["reads"])}
        unattributed = [r.summary() for r in self.list_reads()
                        if r.stamp not in attributed]
        return {
            "serials": sorted(units),
            "units": {str(s): {"serial": s,
                               "best": u["best"].stamp if u["best"] else None,
                               "reads": [x.summary() for x in u["reads"]]}
                      for s, u in units.items()},
            "unattributed": unattributed,
            "active": self.active_unit(),
        }

    def records_for_serial(self, serial: int) -> list["ReadRecord"]:
        """Every stored read attributed to this scanner, newest first."""
        return list(self.units().get(int(serial), {}).get("reads", []))

    def best_for_serial(self, serial: int) -> "ReadRecord | None":
        """The newest GOOD read for this scanner, or None.

        "Newest good" rather than "newest" on purpose: within one unit the
        append-only store may hold a later, degraded read taken in a power
        cycle that had already been used up, and that read is evidence of what
        happened, not a calibration to render with.
        """
        return self.units().get(int(serial), {}).get("best")

    def has_calibration_for(self, serial: int) -> bool:
        return self.best_for_serial(serial) is not None

    # -- which scanner is in force ---------------------------------------
    def select_unit(self, serial: int | None) -> None:
        """Record which scanner the user says is connected.

        This is needed because nothing on this hardware announces which unit it
        is before its EEPROM has been read (docs/01: every F-135 reports the
        same iSerialNumber ``010-203-04``, baked into the firmware image, so
        USB cannot tell two units apart). With one unit in the store there is
        nothing to disambiguate; with two there is, and guessing would silently
        apply the wrong scanner's calibration.

        Writes a pointer, never calibration. Passing None returns to "decide
        automatically" and still removes nothing from disk.
        """
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / ACTIVE_UNIT).write_text(json.dumps(
            {"serial": (int(serial) if serial is not None else None),
             "set_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
            indent=2))

    def active_unit(self) -> int | None:
        p = self.root / ACTIVE_UNIT
        if not p.is_file():
            return None
        try:
            v = json.loads(p.read_text()).get("serial")
        except (OSError, json.JSONDecodeError):
            return None
        return int(v) if v is not None else None

    # -- per-unit overlays -----------------------------------------------
    #
    # The 256-byte page we can read holds the colour matrices and the serial.
    # It does NOT hold the exposure triad, the lamp currents and duty cycles,
    # the AFE gains and offsets or the motor constants -- those live on pages
    # of the same device that nothing has yet read (docs/37). Until a
    # multi-page read exists they have to come from somewhere else, per unit,
    # and this is where that "somewhere else" is kept so it is never confused
    # with bytes that came off the device.
    def unit_dir(self, serial: int) -> Path:
        return self.root / UNITS_DIR / str(int(serial))

    def overlays(self, serial: int) -> list[tuple[str, dict]]:
        """Every overlay written for this unit, newest first. Append-only."""
        d = self.unit_dir(serial) / "overlay"
        if not d.is_dir():
            return []
        out = []
        for p in sorted(d.glob("*.json"), reverse=True):
            try:
                out.append((p.stem, json.loads(p.read_text())))
            except (OSError, json.JSONDecodeError):
                continue
        return out

    def overlay(self, serial: int) -> dict | None:
        """The newest overlay for this unit, or None."""
        o = self.overlays(serial)
        return o[0][1] if o else None

    def save_overlay(self, serial: int, config: dict, *, source: str,
                     provenance: str = "", stamp: str | None = None) -> Path:
        """Add an overlay. Never replaces one -- the old file stays readable.

        Same append-only rule as the reads, for the same reason: the value of
        an old record is that it is still there when the new one turns out to
        be wrong.
        """
        d = self.unit_dir(serial) / "overlay"
        d.mkdir(parents=True, exist_ok=True)
        stamp = stamp or time.strftime(STAMP_FMT, time.gmtime())
        p = d / f"{stamp}.json"
        n = 0
        while p.exists():
            n += 1
            p = d / f"{stamp}-{n}.json"
        body = {
            "serial": int(serial),
            "written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": source,
            "provenance": provenance,
            "config": config,
            "tool": "calib_store/1",
        }
        with open(p, "x") as fh:
            json.dump(body, fh, indent=2, sort_keys=True)
        self._append_manifest([(p, _sha256(p.read_bytes()))])
        _freeze(p)
        return p


    # -- per-unit flat fields ---------------------------------------------
    #
    # dark_2000x3 / gain_2000x3 are MEASURED on one scanner's own CCD, lamp and
    # optics. They are not on the EEPROM and no amount of reading it produces
    # them (docs/69 s8.1). So they are per-serial, exactly like the overlay,
    # and stored the same way: append-only, never replaced, so the previous set
    # is still there when the new one turns out to be wrong.
    FLATFIELD_FILES = ("dark_2000x3.npy", "dark_2000x3.csv",
                       "gain_2000x3.npy", "gain_2000x3.csv", "README.json")

    def flatfields(self, serial: int) -> list[dict]:
        """Every flat field stored for this unit, newest first."""
        d = self.unit_dir(serial) / "flatfield"
        if not d.is_dir():
            return []
        out = []
        for p in sorted((x for x in d.iterdir() if x.is_dir()), reverse=True):
            meta_p = p / "README.json"
            if not (p / "dark_2000x3.npy").is_file() or not meta_p.is_file():
                continue
            try:
                meta = json.loads(meta_p.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            out.append({"stamp": p.name, "dir": str(p), "meta": meta})
        return out

    def flatfield(self, serial: int) -> dict | None:
        """The newest complete flat field for this unit, or None."""
        f = self.flatfields(serial)
        return f[0] if f else None

    def has_flatfield_for(self, serial: int) -> bool:
        return self.flatfield(serial) is not None

    def save_flatfield(self, serial: int, src: Path | str, *,
                       meta: dict | None = None,
                       source: str = "", stamp: str | None = None) -> dict:
        """Copy a built table set in under this serial. Replaces nothing.

        The whole set moves together or not at all: a directory holding a new
        dark table beside an old gain table is not a partial calibration, it is
        a wrong one, and it would load without complaint.
        """
        src = Path(src)
        missing = [n for n in self.FLATFIELD_FILES if not (src / n).is_file()]
        if missing:
            raise FileNotFoundError(
                f"{src} is not a complete table set; missing "
                f"{', '.join(missing)}. Refusing to store part of one.")
        d = self.unit_dir(serial) / "flatfield"
        d.mkdir(parents=True, exist_ok=True)
        stamp = stamp or time.strftime(STAMP_FMT, time.gmtime())
        dest = d / stamp
        n = 0
        while dest.exists():
            n += 1
            dest = d / f"{stamp}-{n}"
        # Assemble beside the destination and rename, so a crash mid-copy
        # cannot leave a half set that the loader would happily read. The
        # partial directory gets a unique name rather than being cleared:
        # this module has no delete path at all, and tools/test_calib.py
        # enforces that by reading this file's own source for the names of
        # every deleting call in the standard library. A leftover ".partial"
        # costs disk; a delete path in here costs somebody's calibration.
        # flatfields() ignores dot-directories, so a leftover is never loaded.
        tmp = d / f".{dest.name}.partial"
        i = 0
        while tmp.exists():
            i += 1
            tmp = d / f".{dest.name}.partial-{i}"
        tmp.mkdir(parents=True)
        items = []
        for name in self.FLATFIELD_FILES:
            data = (src / name).read_bytes()
            (tmp / name).write_bytes(data)
            items.append((dest / name, _sha256(data)))
        if meta is not None:
            body = dict(meta)
            body.setdefault("unit_serial", int(serial))
            body["stored_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                               time.gmtime())
            body["stored_by"] = source or "calib_store"
            text = json.dumps(body, indent=2, default=str) + "\n"
            (tmp / "README.json").write_text(text)
            items = [(p, h) for p, h in items if p.name != "README.json"]
            items.append((dest / "README.json",
                          _sha256(text.encode("utf-8"))))
        tmp.rename(dest)
        for p in sorted(dest.iterdir()):
            _freeze(p)
        self._append_manifest(items)
        return {"serial": int(serial), "stamp": dest.name, "dir": str(dest),
                "files": list(self.FLATFIELD_FILES)}


class ReadRecord:
    def __init__(self, path: Path, meta: dict):
        self.path = path
        self.meta = meta or {}
        self.stamp = self.meta.get("stamp") or path.name

    @property
    def devices(self) -> dict:
        return self.meta.get("devices", {})

    @property
    def calibration_device(self) -> dict | None:
        cands = [e for e in self.devices.values()
                 if e.get("kind") == cv.KIND_CALIBRATION]
        if not cands:
            return None
        return max(cands, key=lambda e: cv._ORDER.get(e.get("state"), 0))

    @property
    def is_good(self) -> bool:
        c = self.calibration_device
        return bool(c and c.get("state") == cv.GOOD)

    @property
    def serial(self) -> int | None:
        """Which scanner this read came from -- believed only when it is safe to.

        A serial is trusted only from a read whose calibration page passed the
        structural checks. The serial lives at offset 0x0F of the same page
        that degrades; on a degraded read those four bytes are corruption, and
        a corrupt u32 makes a perfectly convincing-looking serial number. An
        index built from those would attribute reads to scanners that have
        never existed, and -- far worse -- could attribute a good read to the
        wrong unit. So: good reads only, and unknown otherwise.
        """
        u = self.meta.get("unit") or {}
        if not u.get("known") or not self.is_good:
            return None
        s = u.get("serial")
        return int(s) if isinstance(s, (int, float)) and s == int(s) else None

    @property
    def claimed_serial(self) -> int | None:
        """What the page's serial field says, trusted or not. Display only."""
        c = self.calibration_device or {}
        s = c.get("serial")
        return int(s) if isinstance(s, (int, float)) and s == int(s) else None

    @property
    def is_usable(self) -> bool:
        c = self.calibration_device
        return bool(c and cv.is_usable(c.get("state", "")))

    @property
    def worst_summary(self) -> str:
        c = self.calibration_device
        if c:
            return c.get("summary", c.get("state", "unknown"))
        if not self.devices:
            return "no device answered on the bus"
        # Nothing in this read looks like calibration at all. Say what WAS
        # seen -- "no calibration device" tells a user nothing actionable.
        worst = min(self.devices.values(),
                    key=lambda e: cv._ORDER.get(e.get("state"), 0))
        others = len(self.devices) - 1
        tail = f" (and {others} other device{'s' if others != 1 else ''})" if others else ""
        return (f"nothing in this read parses as calibration; "
                f"0x{worst.get('addr7', 0):02x} is {worst.get('state')}{tail}")

    def data(self, addr7: int) -> bytes:
        return (self.path / f"eeprom_{addr7:02x}.bin").read_bytes()

    def summary(self) -> dict:
        """Everything the Calibration screen needs to let a person judge it.

        A degraded read must be VISIBLY degraded in the list, not silently
        selected because it happens to be newest.
        """
        devs = []
        for key in sorted(self.devices):
            e = self.devices[key]
            devs.append({
                "addr7": e.get("addr7"),
                "label": f"0x{e.get('addr7', 0):02x}",
                "state": e.get("state"),
                "kind": e.get("kind"),
                "summary": e.get("summary"),
                "ff": e.get("stats", {}).get("ff"),
                "ff_fraction": e.get("stats", {}).get("ff_fraction"),
                "entropy": e.get("stats", {}).get("entropy"),
                "bytes": e.get("stats", {}).get("bytes"),
                "checks_passed": sum(1 for c in e.get("checks", []) if c.get("ok")),
                "checks_total": len(e.get("checks", [])),
                "crc_checked": e.get("crc", {}).get("checked", False),
            })
        return {
            "stamp": self.stamp,
            "dir": str(self.path),
            "saved_utc": self.meta.get("saved_utc"),
            "source": self.meta.get("source"),
            "good": self.is_good,
            "usable": self.is_usable,
            "headline": self.worst_summary,
            "serial": (self.meta.get("unit") or {}).get("serial"),
            # Additive, for the serial index: `serial` above is the trusted
            # one and is None on anything but a good read; `claimed_serial` is
            # what the bytes say so a person can see why a read went
            # unattributed without opening the file.
            "claimed_serial": self.claimed_serial,
            "devices": devs,
        }


# --------------------------------------------------------------------------
# CLI -- inspection and selection only. This file cannot read a scanner.
# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Inspect and select stored calibrations. Never touches "
                    "the scanner and never deletes anything.")
    ap.add_argument("--store", type=Path, default=None)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list")
    p = sub.add_parser("use"); p.add_argument("stamp")
    sub.add_parser("auto")
    sub.add_parser("status")
    a = ap.parse_args()

    store = CalibrationStore(a.store)
    if a.cmd == "use":
        try:
            store.select(a.stamp)
        except KeyError:
            print(f"no stored calibration named {a.stamp}", file=sys.stderr)
            return 1
        print(f"using {a.stamp}")
        return 0
    if a.cmd == "auto":
        store.clear_selection()
        print("using the newest read")
        return 0

    sel = store.selection()
    print(f"store {store.root}")
    if not sel["reads"]:
        print("\n  no calibration has been read yet.")
        return 0
    print(f"\nin force: {sel['stamp']}  ({sel['reason']})")
    if sel["message"]:
        print(f"\n  ** {sel['message']}\n")
    print(f"\n{len(sel['reads'])} stored read(s), newest first "
          f"-- none is ever deleted:\n")
    for r in sel["reads"]:
        mark = "->" if r["stamp"] == sel["stamp"] else "  "
        flag = "good" if r["good"] else ("usable" if r["usable"] else "BAD ")
        print(f" {mark} {r['stamp']}  [{flag}]  serial {r['serial']}")
        print(f"      {r['headline']}")
        for d in r["devices"]:
            print(f"        {d['label']}  {d['state']:<12} "
                  f"0xFF {d['ff']}/{d['bytes']}  "
                  f"checks {d['checks_passed']}/{d['checks_total']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
