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
