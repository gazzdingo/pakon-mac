#!/usr/bin/env python3
"""Backend for the Pakon scanning application (Electron front end).

Storage contract, from the owner's product rules:

  * One image per frame. Frames are rendered from (capture + parameters) on
    demand. There are no ``frame_03_v2.png`` intermediates anywhere.
  * Export is the only act that writes files the user keeps.
  * Everything else lives in a temp workspace, deleted on close. On startup we
    offer to clean up leftovers, showing scan count, dates and total size.
  * But creative work is never lost. The capture is bulk and regenerable; the
    per-frame parameters are tiny and are the actual work, so they are written
    to sidecars *outside* the workspace, keyed by capture identity, and
    restored when the same capture is reopened.

Relationship to ``tools/pakon_ui.py``: that file belongs to the colour task
and is its decode backend. This one **subclasses its request handler**, so
every endpoint it serves keeps working unchanged on the same port and this
module only adds ``/api/app/*``. Nothing in pakon_ui.py is edited or replaced.
If the import fails (it is under active development) we degrade to serving
only our own routes rather than failing to start.

    python3 tools/pakon_app.py [--port 8136]
"""
from __future__ import annotations

import argparse
import atexit
import copy
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
import uuid
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent
sys.path.insert(0, str(_TOOLS))
sys.path.insert(0, str(_TOOLS / "ansel" / "python-pipeline"))

import numpy as np                      # noqa: E402
import pakon_render as pr               # noqa: E402
import pakon_decode as dec              # noqa: E402
import pakon_color as pc                # noqa: E402
import pakon_scan as scan               # noqa: E402
import pakon_gate as pgate              # noqa: E402

# The colour task's backend. Optional on purpose — it is being edited live.
try:
    import pakon_ui                     # noqa: E402
    _BASE = pakon_ui.H
    _HAVE_UI = True
except Exception as _e:                 # noqa: BLE001
    print(f"note: pakon_ui unavailable ({_e.__class__.__name__}: {_e}); "
          f"serving /api/app/* only", file=sys.stderr)
    _BASE = BaseHTTPRequestHandler
    _HAVE_UI = False

try:
    import pakon_filmstock as film
except Exception:                       # noqa: BLE001
    film = None

# The calibration read/backup path. Imported defensively so that a problem
# here can never stop the app from opening someone's photographs -- but note
# that its own refusals are deliberate and must NOT be swallowed as errors.
try:
    import calib_read as calib          # noqa: E402
    import calib_store as calib_store   # noqa: E402
    import calib_device as calib_dev    # noqa: E402
    # Disk-only lookup and the unattended calibration. calib_profile and
    # calib_resolve cannot reach a device at all -- they import no transport
    # and take none, which tools/test_calib.py proves by launching a clean
    # interpreter and asserting neither `usb` nor calib_device was ever
    # imported -- so adding them here preserves the "no USB traffic"
    # property of calibration_store_state() rather than relying on care.
    import calib_profile as cprof       # noqa: E402
    import calib_resolve as cres        # noqa: E402
    import calib_wizard as cwiz         # noqa: E402
except Exception as _e:                 # noqa: BLE001
    print(f"note: calibration tools unavailable ({_e.__class__.__name__}: "
          f"{_e}); the scanner's calibration will not be read or backed up",
          file=sys.stderr)
    calib = calib_store = calib_dev = None
    cprof = cres = cwiz = None

import urllib.request
import urllib.error

def send_telemetry(event: str, error_type: str = None, error_message: str = None) -> None:
    if os.environ.get("PAKON_TELEMETRY_OPT_OUT") == "1":
        return
    
    # Scrub local file paths from error messages if present
    if error_message:
        import re
        error_message = re.sub(r'(/Users|C:\\Users|/home)[^\s"\']+', '[REDACTED_PATH]', error_message)
        
    data = {
        "os_platform": sys.platform,
        "app_version": "1.0.0",
        "event": event,
        "session_id": getattr(send_telemetry, "session_id", None),
        "timestamp": time.time(),
    }
    
    if not data.get("session_id"):
        data["session_id"] = send_telemetry.session_id = uuid.uuid4().hex
        
    if error_type:
        data["error_type"] = error_type
    if error_message:
        data["error_message"] = error_message
        
    req = urllib.request.Request(
        "https://langford-lee.com/pakon-mac/telemetry",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    def _send():
        try:
            urllib.request.urlopen(req, timeout=3.0)
        except Exception:
            pass # Fire and forget, don't crash the app if telemetry fails
            
    threading.Thread(target=_send, daemon=True).start()

# Send startup telemetry
send_telemetry("startup")

# Hook into global exceptions to report unhandled crashes
_orig_excepthook = sys.excepthook
def _telemetry_excepthook(exc_type, exc_value, exc_traceback):
    err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    send_telemetry("crash", error_type=exc_type.__name__, error_message=err_msg)
    _orig_excepthook(exc_type, exc_value, exc_traceback)
sys.excepthook = _telemetry_excepthook

_orig_thread_excepthook = getattr(threading, "excepthook", None)
if _orig_thread_excepthook:
    def _telemetry_thread_excepthook(args):
        err_msg = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        send_telemetry("thread_crash", error_type=args.exc_type.__name__, error_message=err_msg)
        _orig_thread_excepthook(args)
    threading.excepthook = _telemetry_thread_excepthook


# --------------------------------------------------------------------------
# where things live
# --------------------------------------------------------------------------

def _app_dir(kind: str) -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        base = (home / "Library" / "Caches" / "PakonScan" if kind == "cache"
                else home / "Library" / "Application Support" / "PakonScan")
    elif sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA") or str(home)
        base = Path(root) / "PakonScan" / ("cache" if kind == "cache" else "data")
    else:
        env = "XDG_CACHE_HOME" if kind == "cache" else "XDG_DATA_HOME"
        default = ".cache" if kind == "cache" else ".local/share"
        base = Path(os.environ.get(env) or home / default) / "PakonScan"
    base.mkdir(parents=True, exist_ok=True)
    return base


WORKSPACE = _app_dir("cache") / "workspace"
SIDECARS = _app_dir("data") / "sidecars"

#: Where a scan writes its capture, and the biggest single thing this
#: application creates — about 700 MB a roll, plus its .dx.json and .scan.json
#: sidecars.
#:
#: This used to be ``_ROOT / "captures"``, which was wrong twice.
#:
#: It broke the storage contract at the top of this file. "Everything else
#: lives in a temp workspace, deleted on close" is the owner's rule, and the
#: primary artefact of the main path was the one thing exempt from it: purge()
#: only ever walked WORKSPACE, so captures accumulated forever while two
#: dialogs told the user they had been deleted.
#:
#: And when packaged, ``_ROOT`` is ``process.resourcesPath`` — inside the
#: signed .app bundle. A scan would ``mkdir`` and write 700 MB into
#: ``Pakon Mac.app/Contents/Resources/captures``, which breaks the signature
#: and puts the owner's photographs somewhere an app update deletes.
#:
#: So captures live in the cache tree beside the workspace, and purge() reaches
#: them.
CAPTURES = _app_dir("cache") / "captures"

#: The repository's own ``captures/`` — the owner's existing photographs and
#: the research .bins the tools were built against. Read-only from here: it is
#: LISTED so that everything already on disk stays openable, and it is never
#: written to and never, under any circumstance, deleted. purge() proves that
#: rather than trusting it.
LEGACY_CAPTURES = _ROOT / "captures"

WORKSPACE.mkdir(parents=True, exist_ok=True)
SIDECARS.mkdir(parents=True, exist_ok=True)
CAPTURES.mkdir(parents=True, exist_ok=True)


def capture_dirs() -> list[Path]:
    """Everywhere a capture may be found, newest home first."""
    out = [CAPTURES]
    if LEGACY_CAPTURES.is_dir() and LEGACY_CAPTURES.resolve() != CAPTURES.resolve():
        out.append(LEGACY_CAPTURES)
    return out


def capture_key(path: str | Path) -> str:
    """Stable identity for a capture: path + size + mtime. Sidecars hang off
    this, so reopening the same .bin restores every adjustment."""
    p = Path(path)
    try:
        st = p.stat()
        raw = f"{p.resolve()}|{st.st_size}|{int(st.st_mtime)}"
    except OSError:
        raw = str(p)
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def dir_size(p: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(p):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


# --------------------------------------------------------------------------
# sidecars — the creative work, kept outside the disposable workspace
# --------------------------------------------------------------------------

def sidecar_path(key: str) -> Path:
    return SIDECARS / f"{key}.json"


def load_sidecar(key: str) -> dict:
    p = sidecar_path(key)
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save_sidecar(roll: "pr.Roll") -> None:
    key = capture_key(roll.capture)
    data = {
        "version": 1,
        "capture": roll.capture,
        "name": roll.name,
        "dx": roll.dx,
        "film_path": roll.film_path,
        "sba_key": roll.sba_key,
        "sba_default": roll.sba_default,
        "updated": time.time(),
        "frames": [
            {"index": f.index, "a": f.a, "b": f.b, "params": f.params,
             "exported": f.exported}
            for f in roll.frames
        ],
    }
    tmp = sidecar_path(key).with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(sidecar_path(key))


def apply_sidecar(roll: "pr.Roll") -> int:
    """Restore saved parameters. Boundaries are restored too when the frame
    count matches, since moving a boundary is creative work as well."""
    data = load_sidecar(capture_key(roll.capture))
    saved = data.get("frames") or []
    if not saved:
        return 0
    if len(saved) == len(roll.frames):
        for f, s in zip(roll.frames, saved):
            f.a, f.b = int(s.get("a", f.a)), int(s.get("b", f.b))
            f.params = s.get("params") or {}
            f.exported = s.get("exported")
        pr._flag_confidence(roll)
    else:
        # frame detection changed under us — keep parameters by index only
        for f, s in zip(roll.frames, saved):
            f.params = s.get("params") or {}
    if data.get("name"):
        roll.name = data["name"]
    return sum(1 for f in roll.frames if pr.is_adjusted(f.params))


# --------------------------------------------------------------------------
# session state
# --------------------------------------------------------------------------

class Session:
    def __init__(self) -> None:
        self.rolls: dict[str, pr.Roll] = {}
        self.jobs: dict[str, dict] = {}
        self.lock = threading.Lock()
        self.cache: OrderedDict[str, bytes] = OrderedDict()
        self.cache_bytes = 0
        self.cache_limit = 512 * 1024 * 1024
        self.exports: list[dict] = []
        #: roll id -> stack of {"label", "at", "frames"} snapshots, oldest
        #: first. See snapshot() for why this is cheap enough to be automatic.
        self.undo: dict[str, list[dict]] = {}
        #: roll id -> mtime of the roll.json this process last loaded that
        #: roll from. See get_roll() -- this is what lets an edit made to
        #: roll.json some other way (by hand, by a repair script) actually
        #: reach a roll this process already has cached in memory.
        self._roll_mtime: dict[str, float] = {}

    # ---- roll cache ----
    #
    # S.rolls only ever gets a fresh Roll object from a full re-decode (the
    # "open capture" job, pr.open_capture()). There was no cheap path back
    # from a roll.json changed some other way to the in-memory copy this
    # process actually serves renders from -- and reloading the app's own
    # window does not clear it either, since only the backend process
    # restarting did. That is a real staleness trap: fix a roll's metadata on
    # disk and every render still comes from the stale in-memory object until
    # someone thinks to quit and relaunch the whole app. get_roll() closes it
    # by comparing roll.json's mtime against the mtime this process last saw,
    # and reloading via Roll.from_json() (cheap: it does not touch rgb14.npy
    # or re-decode anything) whenever the file on disk is newer.
    def get_roll(self, roll_id: str) -> "pr.Roll | None":
        with self.lock:
            roll = self.rolls.get(roll_id)
        if roll is None:
            return None
        meta_path = Path(roll.workspace) / "roll.json"
        try:
            disk_mtime = meta_path.stat().st_mtime
        except OSError:
            return roll
        if disk_mtime <= self._roll_mtime.get(roll_id, 0.0):
            return roll
        try:
            fresh = pr.Roll.from_json(json.loads(meta_path.read_text()))
        except Exception:
            # A bad or half-written roll.json must not take an in-memory roll
            # that is working down with it -- serve the stale copy and try
            # the reload again on the next call instead of raising here.
            return roll
        with self.lock:
            self.rolls[roll_id] = fresh
        self._roll_mtime[roll_id] = disk_mtime
        return fresh

    def fresh_rolls(self) -> list:
        return [r for r in (self.get_roll(rid) for rid in list(self.rolls)) if r is not None]

    # ---- undo ----
    #
    # There was no undo anywhere in this app, and two operations
    # (apply-to-roll, redetect) rewrite every frame at once. The parametric
    # model makes the fix nearly free: a frame's whole editable state is a
    # handful of ints and a dict, so a snapshot of a 40-frame roll is a few
    # kilobytes. There is no reason not to take one before every destructive
    # edit, and that is what happens.
    #
    # Deliberately in memory and not in the sidecar. Undo is a property of
    # this editing session; persisting it would mean reasoning about undoing
    # past a reopen, past a redetect that changed the frame count, and past
    # another process having written the same sidecar.
    UNDO_DEPTH = 40

    @staticmethod
    def _snap_frames(roll) -> list[dict]:
        return [{"index": f.index, "a": f.a, "b": f.b,
                 "params": copy.deepcopy(f.params or {}),
                 "exported": f.exported, "confidence": f.confidence,
                 "phase": getattr(f, "phase", ""),
                 "framing_risk": getattr(f, "framing_risk", 0),
                 "scan_warning": getattr(f, "scan_warning", 0)}
                for f in roll.frames]

    def snapshot(self, roll, label: str) -> None:
        """Record the roll's frame state so the next edit can be undone."""
        with self.lock:
            st = self.undo.setdefault(roll.id, [])
            st.append({"label": label, "at": time.time(),
                       "frames": self._snap_frames(roll)})
            del st[:-self.UNDO_DEPTH]

    def undo_state(self, roll_id: str) -> dict:
        with self.lock:
            st = self.undo.get(roll_id) or []
            return {"available": bool(st), "depth": len(st),
                    "label": st[-1]["label"] if st else None}

    def undo_pop(self, roll) -> dict | None:
        with self.lock:
            st = self.undo.get(roll.id) or []
            return st.pop() if st else None

    # ---- render cache (memory only; never a file) ----
    def cache_get(self, k: str):
        with self.lock:
            if k in self.cache:
                self.cache.move_to_end(k)
                return self.cache[k]
        return None

    def cache_put(self, k: str, v: bytes) -> None:
        with self.lock:
            if k in self.cache:
                self.cache_bytes -= len(self.cache.pop(k))
            self.cache[k] = v
            self.cache_bytes += len(v)
            while self.cache_bytes > self.cache_limit and self.cache:
                _k, old = self.cache.popitem(last=False)
                self.cache_bytes -= len(old)

    def cache_drop(self, prefix: str) -> None:
        with self.lock:
            for k in [k for k in self.cache if k.startswith(prefix)]:
                self.cache_bytes -= len(self.cache.pop(k))

    # ---- jobs ----
    def job_new(self, kind: str) -> str:
        jid = uuid.uuid4().hex[:10]
        with self.lock:
            self.jobs[jid] = {"id": jid, "kind": kind, "status": "running",
                              "phase": "", "progress": 0.0, "message": "",
                              "started": time.time()}
        return jid

    def job_set(self, jid: str, **kw) -> None:
        with self.lock:
            j = self.jobs.setdefault(jid, {"id": jid})
            j.update(kw)

    def job_append(self, jid: str, field: str, value) -> None:
        """Add to a list field on a job, keeping every value.

        ``job_set`` overwrites, which is right for a phase or a byte count and
        wrong for a warning: FilmSense reports each mis-load condition exactly
        once, when it is first seen, so an overwritten warning is a warning
        the operator can never be shown.
        """
        if value is None:
            return
        with self.lock:
            j = self.jobs.setdefault(jid, {"id": jid})
            cur = j.get(field)
            if not isinstance(cur, list):
                cur = []
            if value not in cur:
                cur.append(value)
            j[field] = cur

    def job_get(self, jid: str):
        with self.lock:
            j = self.jobs.get(jid)
            return dict(j) if j else None


S = Session()


def unexported_summary() -> dict:
    """For the quit dialog. Distinguishes 'lose creative work' from
    'delete bulk data' — housekeeping.html states B."""
    rolls = []
    adjusted = exported = 0
    for r in S.fresh_rolls():
        adj = [f.index + 1 for f in r.frames if pr.is_adjusted(f.params)]
        exp = sum(1 for f in r.frames if f.exported)
        adjusted += len(adj)
        exported += exp
        rolls.append({"id": r.id, "name": r.name, "adjusted": adj,
                      "exported": exp, "frames": len(r.frames)})
    # Three figures, not one. The quit dialog said "the raw captures (X MB) are
    # deleted" while X was dir_size(WORKSPACE) — which held rgb14.npy and
    # roll.json and no captures at all, and the captures were not deleted
    # either. Both halves of that sentence were wrong. Now each thing is
    # measured separately and the dialog can name what it is actually about to
    # remove.
    ws, caps = dir_size(WORKSPACE), dir_size(CAPTURES)
    return {
        "rolls": rolls,
        "adjusted_frames": adjusted,
        "exported_frames": exported,
        "workspace_bytes": ws,          # the render cache: rgb14.npy, roll.json
        "capture_bytes": caps,          # the raw .bin scans and their sidecars
        "temp_bytes": ws + caps,        # everything purge(all=True) removes
        "captures": len(list(CAPTURES.glob("*.bin"))),
        "sidecar_bytes": dir_size(SIDECARS),
        "has_unexported_work": adjusted > 0 and exported < adjusted,
    }


def workspace_state() -> dict:
    """Leftovers from a previous session — housekeeping.html state A."""
    entries = []
    for d in sorted(WORKSPACE.glob("*")):
        if not d.is_dir():
            continue
        meta_p = d / "roll.json"
        meta = {}
        if meta_p.is_file():
            try:
                meta = json.loads(meta_p.read_text())
            except (OSError, json.JSONDecodeError):
                meta = {}
        size = dir_size(d)
        key = capture_key(meta.get("capture", "")) if meta.get("capture") else ""
        side = load_sidecar(key) if key else {}
        adj = sum(1 for f in (side.get("frames") or [])
                  if pr.is_adjusted(f.get("params")))
        exported = sum(1 for f in (side.get("frames") or []) if f.get("exported"))
        entries.append({
            "id": d.name,
            "name": meta.get("name") or d.name,
            "capture": meta.get("capture"),
            "frames": len(meta.get("frames") or []),
            "bytes": size,
            "mtime": d.stat().st_mtime,
            "adjusted": adj,
            "exported": exported,
            "live": d.name in S.rolls,
        })
    try:
        du = shutil.disk_usage(WORKSPACE)
        disk = {"total": du.total, "used": du.used, "free": du.free}
    except OSError:
        disk = {}
    caps = capture_entries()
    return {
        "path": str(WORKSPACE),
        "captures_path": str(CAPTURES),
        "legacy_captures_path": (str(LEGACY_CAPTURES)
                                 if LEGACY_CAPTURES.is_dir() else None),
        "sidecars": str(SIDECARS),
        "rolls": entries,
        # Leftover raw scans. These are the 700 MB items, and until now the
        # housekeeping screens could not see them at all, so a crash left them
        # on disk for good with nothing offering to clear them.
        "captures": caps,
        "capture_bytes": sum(c["bytes"] for c in caps),
        "total_bytes": sum(e["bytes"] for e in entries)
                       + sum(c["bytes"] for c in caps),
        "workspace_bytes": sum(e["bytes"] for e in entries),
        "sidecar_bytes": dir_size(SIDECARS),
        "disk": disk,
    }


# --------------------------------------------------------------------------
# capture discovery
# --------------------------------------------------------------------------

def probe_channels(path: Path) -> dict:
    """Modal sync-marker gap tells us the line length, and so the channel
    count. A 3-channel line is 6000 words; a 4-channel (IR) line is 8000.

    IR is untested on this unit — the hardware supports it (Current_Ir = 4,
    DutyCycle_Ir = 0.887) but no IR capture exists yet, so this reports what
    it finds rather than promising the pipeline can use it.

    Two separate answers, because they stopped being the same question when
    the decoder learned 8000-word lines (docs/70):

      ``unpackable``  ``pakon_decode`` can sync-segment and unpack this
                      geometry into planes. True for 6000 and 8000.
      ``decodable``   the *rendering* path can make a picture out of it. Still
                      3-channel only: ``rgb14.npy``, the committed
                      ``dark_2000x3``/``gain_2000x3`` tables and the Go TIFF
                      hand-off are all RGB, and there is no infrared dark or
                      gain reference in ``calibration/`` to flat-field a fourth
                      plane with. A 4-channel capture is therefore recognised
                      and named rather than mis-segmented — which is what would
                      have happened before — but still refused at open.
    """
    unknown = {"words_per_line": None, "channels": None, "has_ir": False,
               "unpackable": False, "decodable": False}
    try:
        with open(path, "rb") as fh:
            buf = fh.read(8 * 1024 * 1024)
        w = np.frombuffer(buf[: (len(buf) // 2) * 2], dtype="<u2")
        m = np.flatnonzero(w & 1)
        if m.size < 4:
            return dict(unknown)
        gaps = np.diff(m)
        modal = int(np.bincount(gaps).argmax())
    except (OSError, ValueError):
        return dict(unknown)
    ch = {n: n // dec.PIXELS_PER_LINE for n in dec.LINE_WORD_CANDIDATES
          }.get(modal)
    return {
        "words_per_line": modal,
        "channels": ch,
        "has_ir": ch == dec.CHANNELS_IR,
        "unpackable": modal in dec.LINE_WORD_CANDIDATES,
        "decodable": ch == dec.CHANNELS,
    }


def dx_sidecar(path: str | Path) -> dict:
    """The ``<capture>.dx.json`` pakon_scan writes when the DX board answered.

    Absent for every capture taken before the DX read path existed, and absent
    for any scan where the board said nothing — so this returns {} far more
    often than not, and callers must cope with that rather than assume a stock.
    """
    p = Path(path).with_suffix(".dx.json")
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def dx_from_sidecar(path: str | Path) -> str | None:
    """``"96-1"`` from the DX sidecar, or None. Never a guess.

    dx_read only fills in ``product``/``specifier`` when a code word passed
    parity *and* was unambiguous under exactly one byte window; anything less
    leaves them null and this returns None, which is the correct answer.
    """
    s = (dx_sidecar(path).get("summary") or {})
    p1, p2 = s.get("product"), s.get("specifier")
    if p1 is None or p2 is None:
        return None
    return f"{int(p1)}-{int(p2)}"


def film_from_sidecar(path: str | Path) -> dict:
    """What the scan that made this capture recorded the film as.

    THE POINT OF RECORDING IT. Before ``ScanConfig`` carried a film field the
    operator's answer lived only in ``S.jobs``, so a capture opened from a
    later launch of the app — or a year later — had nobody left to ask. This
    reads it back, and it is the reason a capture is now self-describing.

    Returns ``{}`` for a capture with no sidecar or an older one.
    """
    try:
        meta = dec.load_capture_sidecar(path) or {}
    except Exception:                                       # noqa: BLE001
        return {}
    f = meta.get("film")
    return f if isinstance(f, dict) else {}


def refuse_film_choice(film_path: str | None, dx: str | None) -> None:
    """Refuse a film selection that cannot be decoded, before anything is spent.

    Both halves used to fail late and quietly:

    * ``POSITIVE`` maps to ``POLY_CLASS_COLREV``, which
      ``dec.check_film_class`` refuses because the F-135 reversal branch is not
      ported — but only when the capture was *opened*, i.e. after the whole
      roll had already gone past the sensor and the auto-open failed.
    * a DX that does not resolve used to be swallowed into ``stock = None``,
      and because the client dropped ``film_path`` whenever a DX was typed, the
      roll reached the colour default with neither.

    Raised from the scan start and from open, so the answer is the same
    wherever it is asked.
    """
    if film_path:
        try:
            dec.check_film_class(pc.film_class_for_path(film_path),
                                 pc.DEFAULT_MODEL)
        except dec.FilmClassNotPorted as e:
            raise ValueError(str(e)) from e
    if dx and film is not None:
        try:
            p1, p2 = film.parse_dx(dx)
            film.lookup(p1, p2)
        except Exception as e:                              # noqa: BLE001
            raise ValueError(
                f"DX {dx!r} does not resolve to a film stock ({e}). Correct "
                f"it, or clear it and choose a film path — a DX that cannot "
                f"be looked up is not a film selection, and carrying on would "
                f"mean rendering this roll as a default nobody chose."
            ) from e


def list_captures() -> list[dict]:
    """Every capture that can be opened, from both homes.

    ``temporary`` is the fact the UI needs: a capture in the cache tree is
    deleted when the workspace is cleared, and one in the repository's own
    ``captures/`` never is. They look identical in a file list otherwise, and
    the difference is 700 MB of the owner's photographs.
    """
    out, seen = [], set()
    for d in capture_dirs():
        temporary = d.resolve() == CAPTURES.resolve()
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.bin")):
            rp = p.resolve()
            if rp in seen:
                continue
            seen.add(rp)
            try:
                info = pr.probe_capture(p)
            except OSError:
                continue
            key = capture_key(p)
            side = load_sidecar(key)
            info["has_sidecar"] = bool(side)
            info["adjusted"] = sum(
                1 for f in (side.get("frames") or [])
                if pr.is_adjusted(f.get("params")))
            info["saved_name"] = side.get("name")
            info["dx_read"] = dx_from_sidecar(p)
            # What the scan recorded, and where each part came from. `dx_read`
            # above is the DX board's own reading; these are the operator's
            # selection. They are different claims and the UI now says which.
            recorded = film_from_sidecar(p)
            info["recorded_film_path"] = recorded.get("film_path")
            info["recorded_dx"] = recorded.get("dx")
            info["dx_source"] = (
                recorded.get("dx_source")
                or ("board" if info["dx_read"] else "none"))
            info["temporary"] = temporary
            info["dir"] = str(d)
            out.append(info)
    return out


def capture_entries() -> list[dict]:
    """The temp captures, as the housekeeping screens need them: what it is,
    how big, when, and whether its adjustments have been exported."""
    entries = []
    for p in sorted(CAPTURES.glob("*.bin")):
        try:
            st = p.stat()
        except OSError:
            continue
        side = load_sidecar(capture_key(p))
        frames = side.get("frames") or []
        # The .dx.json / .scan.json sidecars go with it; counting them keeps
        # the "you will free N" figure honest.
        extra = sum(q.stat().st_size for q in CAPTURES.glob(f"{p.stem}.*")
                    if q != p and q.is_file())
        entries.append({
            "name": p.name,
            "path": str(p),
            "bytes": st.st_size + extra,
            "mtime": st.st_mtime,
            "adjusted": sum(1 for f in frames if pr.is_adjusted(f.get("params"))),
            "exported": sum(1 for f in frames if f.get("exported")),
        })
    return entries


# --------------------------------------------------------------------------
# jobs: open, export
# --------------------------------------------------------------------------

def job_open(jid: str, body: dict) -> None:
    try:
        path = body.get("path")
        if not path:
            raise ValueError("no capture path")
        src = Path(path)
        if not src.is_file():
            # A bare name, or a path from before captures moved out of the
            # repository. Look in both homes before giving up.
            for d in capture_dirs():
                alt = d / os.path.basename(path)
                if alt.is_file():
                    src = alt
                    break
            else:
                raise FileNotFoundError(f"capture not found: {path}")

        ch = probe_channels(src)
        if ch.get("words_per_line") and not ch.get("decodable"):
            if ch.get("has_ir"):
                # Say the true reason. The blocker is no longer the decoder —
                # it unpacks this — it is that nothing downstream has an
                # infrared dark/gain reference or a defect operator. docs/70.
                raise ValueError(
                    f"line length {ch['words_per_line']} words (4-channel, "
                    f"infrared present). The decoder can unpack it, but the "
                    f"colour path is RGB-only: calibration/ has no "
                    f"dark_2000x4/gain_2000x4 reference and Digital ICE is "
                    f"not ported (pakon_decode.ICE_PORTED is False).")
            raise ValueError(
                f"line length {ch['words_per_line']} words "
                f"({ch.get('channels') or '?'}-channel). The decode path "
                f"handles {dec.WORDS_PER_LINE}-word 3-channel lines only.")

        roll_id = uuid.uuid4().hex[:8]

        def prog(phase, frac, msg):
            S.job_set(jid, phase=phase, progress=float(frac), message=msg)

        # WHAT FILM IS THIS, AND WHO SAID SO.
        #
        # Precedence, and the provenance that goes with it — see
        # `pakon_scan.DX_PRECEDENCE` for why it is this way round. In short:
        # a typed DX is the operator's deliberate statement about the roll in
        # the gate, while the board's reading is `tools/dx_decode.py`, which
        # has never been validated against a real roll. Both are kept; the
        # source says which was used, and no screen could tell them apart
        # before this existed.
        #
        #   1. typed here (the Open dialog, or carried from the scan)
        #   2. recorded by the scan that made this capture (its .scan.json)
        #   3. read off the DX board during that scan (its .dx.json)
        #
        # Film path follows the same idea: fall back to what the scan recorded
        # rather than letting the render reach a colour-negative default that
        # nobody chose. That is the whole reason it is in the sidecar.
        recorded = film_from_sidecar(src)
        dx_spec = (body.get("dx") or "").strip() or None
        dx_source = "typed" if dx_spec else ""
        if not dx_spec and recorded.get("dx"):
            dx_spec = recorded["dx"]
            dx_source = f"sidecar:{recorded.get('dx_source') or 'unknown'}"
        if not dx_spec:
            dx_spec = dx_from_sidecar(src)
            dx_source = "board" if dx_spec else ""

        film_path = (body.get("film_path") or "").strip() or None
        film_source = "typed" if film_path else ""
        if not film_path and recorded.get("film_path"):
            film_path = recorded["film_path"]
            film_source = "sidecar"

        # The same refusal the scan start makes, so a capture opened by hand
        # gets the same answer as one opened straight off a scan.
        refuse_film_choice(film_path, dx_spec if dx_source == "typed" else None)

        roll = pr.open_capture(
            src, WORKSPACE, roll_id,
            name=body.get("name"),
            dx=dx_spec,
            dx_source=dx_source,
            film_path=film_path,
            sba_key=body.get("sba_key") or None,
            sba_default=bool(body.get("sba_default")),
            max_lines=int(body.get("max_lines") or 0),
            progress=prog,
        )
        if film_source == "sidecar":
            roll.warnings.append(
                f"film path {film_path} was not chosen here — it is what the "
                f"scan that made this capture recorded in its sidecar. Nothing "
                f"was guessed, but nothing was re-confirmed either.")
        roll.ir = ch
        restored = apply_sidecar(roll)
        meta_path = Path(roll.workspace) / "roll.json"
        meta_path.write_text(json.dumps(roll.to_json(), indent=1))
        save_sidecar(roll)
        with S.lock:
            S.rolls[roll.id] = roll
        S._roll_mtime[roll.id] = meta_path.stat().st_mtime
        S.job_set(jid, status="done", progress=1.0, phase="done",
                  message=f"{len(roll.frames)} frames"
                          + (f", {restored} restored" if restored else ""),
                  roll=roll.id)
    except Exception as e:                                  # noqa: BLE001
        S.job_set(jid, status="error", error=f"{e}",
                  trace=traceback.format_exc()[-2000:])


def export_request(body: dict) -> tuple:
    """Everything both the plan and the write need, worked out exactly once.

    The plan and the write agreeing is the whole safety property here, so the
    destination, the frame list and the template are derived in one place and
    handed to both. Working them out twice is how a plan comes to describe an
    export that did something else.
    """
    roll = S.get_roll(body.get("roll"))
    if roll is None:
        raise ValueError("unknown roll")
    dest = Path(os.path.expanduser(body.get("dest") or "~/Pictures/Film"))
    if body.get("subfolder", True):
        dest = dest / roll.name
    fmt = body.get("format") or "tiff"
    colour = body.get("colour") or "linear"
    template = body.get("template") or "{roll}_{frame:02}_{stock}"
    idxs = body.get("frames")
    if not idxs:
        idxs = [f.index for f in roll.frames
                if not pr.merged_params(f.params)["rejected"]]
    on_exist = body.get("on_exist") or "ask"
    if on_exist not in pr.ON_EXIST:
        raise ValueError(f"on_exist must be one of {pr.ON_EXIST}")
    return roll, dest, fmt, colour, template, list(idxs), on_exist


def plan_for_export(roll, idxs, dest, fmt, colour, template,
                    on_exist) -> dict:
    """``pr.plan_export``, with its one unusable mode routed around.

    ``plan_export(on_exist="unique")`` raises ``FileNotFoundError`` whenever a
    target already exists — which is the only situation "unique" is for. It
    rebinds ``out`` to the free name and then the ``elif exists:`` branch,
    which is still true because ``exists`` was computed from the *original*
    path, calls ``out.stat()`` on the new name that by construction does not
    exist yet. ``ask``, ``skip`` and ``overwrite`` never rebind and are fine.

    ``tools/pakon_render.py`` belongs to another task and is not edited from
    here, so this asks for the plan in a mode that cannot hit the bug and then
    resolves the free names with the planner's own ``unique_path`` — the
    detection stays in one place and only the naming is done here. The upstream
    one-line fix is to stat the pre-rename path.
    """
    if on_exist != "unique":
        return pr.plan_export(roll, idxs, dest, fmt=fmt, colour=colour,
                              template=template, on_exist=on_exist)
    plan = pr.plan_export(roll, idxs, dest, fmt=fmt, colour=colour,
                          template=template, on_exist="skip")
    taken: set = set()
    for it in plan["items"]:
        p = Path(it["path"])
        if it["action"] == "skip" or p in taken:
            p = pr.unique_path(p, taken)
            it["path"] = str(p)
        it["action"] = "write"
        taken.add(p)
    plan.update(on_exist="unique", needs_confirm=False,
                will_write=len(plan["items"]), will_skip=0)
    return plan


def export_plan(body: dict) -> dict:
    """What this export would write, before a byte of it is written."""
    roll, dest, fmt, colour, template, idxs, on_exist = export_request(body)
    plan = plan_for_export(roll, idxs, dest, fmt, colour, template, on_exist)
    plan["roll"] = roll.id
    plan["frames"] = idxs
    plan["message"] = export_collision_message(plan) if plan["needs_confirm"] else ""
    return plan


def job_export(jid: str, body: dict) -> None:
    """Export, through the planner that has been sitting there uncalled.

    ``pakon_render.plan_export`` was written with ``existing``, ``duplicates``,
    ``needs_confirm``, ``on_exist`` and ``unique_path``, and nothing ever
    called it — so export opened a path and wrote, and there were two live ways
    to lose work by it:

      * exporting a roll twice to the same folder replaced the first export's
        TIFFs with no prompt;
      * the naming template is a free-text field, so deleting ``{frame:02}``
        from it renders all 36 frames to one filename, each overwriting the
        last. That one is invisible: the destination folder ends up holding a
        single file and nothing said so.

    The refusal lives HERE and not only in the UI. A plan that needs
    confirmation ends the job before anything is rendered, so no future caller
    — a retry, a script, a screen that forgets to ask — can overwrite by
    omission. Each frame is then written to the exact path the plan named,
    which is what ``export_frame(out=…)`` exists for.
    """
    try:
        roll, dest, fmt, colour, template, idxs, on_exist = export_request(body)
        plan = plan_for_export(roll, idxs, dest, fmt, colour, template,
                               on_exist)
        if plan["needs_confirm"]:
            S.job_set(
                jid, status="error", phase="blocked", progress=0.0,
                needs_confirm=True, plan=plan, dest=str(dest),
                error=export_collision_message(plan),
                message=export_collision_message(plan))
            return

        by_frame = {it["frame"]: it for it in plan["items"]}
        results = []
        total = len(idxs)
        replaced = 0
        for k, i in enumerate(idxs):
            # k is the position in the queue, i is the frame's own number.
            # The lane reads "3 of 12", so it needs the position; naming the
            # frame here produced "frame 4 of 2" when a subset was exported.
            S.job_set(jid, progress=k / max(1, total), phase="rendering",
                      message=f"frame {i + 1} — {k + 1} of {total}", current=i,
                      results=list(results))
            item = by_frame.get(i) or {}
            if item.get("action") == "skip":
                results.append({"frame": i, "status": "skipped",
                                "path": item.get("path"),
                                "reason": "a file of that name is already there"})
                continue
            try:
                r = pr.export_frame(roll, i, dest, fmt=fmt, colour=colour,
                                    template=template,
                                    out=Path(item["path"]) if item.get("path")
                                    else None)
                r["status"] = "written"
                if item.get("action") == "overwrite":
                    r["replaced"] = True
                    replaced += 1
            except Exception as e:                          # noqa: BLE001
                r = {"frame": i, "status": "error", "error": str(e)}
            results.append(r)
        save_sidecar(roll)
        with S.lock:
            S.exports.extend(r for r in results if r.get("status") == "written")
        written = sum(1 for r in results if r.get("status") == "written")
        skipped = sum(1 for r in results if r.get("status") == "skipped")
        msg = f"{written} of {total} written"
        if replaced:
            msg += f", {replaced} replaced"
        if skipped:
            msg += f", {skipped} skipped"
        S.job_set(jid, status="done", progress=1.0, phase="done",
                  results=results, dest=str(dest), plan=plan,
                  replaced=replaced, skipped=skipped, message=msg)
    except Exception as e:                                  # noqa: BLE001
        S.job_set(jid, status="error", error=f"{e}",
                  trace=traceback.format_exc()[-2000:])


def export_collision_message(plan: dict) -> str:
    """Name what would be destroyed, in the words that make someone stop.

    The two collisions need different sentences. Files already in the folder
    are "you will replace work you have"; two frames rendering to one name is
    "your template does not tell these frames apart" — and that second one is
    a bug in what the user typed, not a decision they are making.
    """
    ex, dup = plan.get("existing") or [], plan.get("duplicates") or []
    bits = []
    if ex:
        names = ", ".join(Path(e["path"]).name for e in ex[:4])
        bits.append(f"{len(ex)} file{'' if len(ex) == 1 else 's'} already in "
                    f"that folder would be replaced ({names}"
                    f"{'…' if len(ex) > 4 else ''})")
    if dup:
        frames = ", ".join(str(d["frame"] + 1) for d in dup[:6])
        bits.append(f"{len(dup)} frame{'' if len(dup) == 1 else 's'} would "
                    f"overwrite each other — the naming template does not "
                    f"tell them apart, so frames {frames}"
                    f"{'…' if len(dup) > 6 else ''} all render to the same "
                    f"filename")
    return "; ".join(bits) or "this export would replace existing files"


# --------------------------------------------------------------------------
# scanning — supervising a process that can move the owner's film
# --------------------------------------------------------------------------
#
# The backend deliberately never opens the scanner to run a scan. It starts
# `pakon_scan.py run` as a child and talks to it over pipes, for one reason:
# if a process holding the USB interface is killed, nothing it intended to do
# in a `finally` happens, and the transport keeps running. Keeping the handle
# in a separate, disposable process means the interface is free the moment
# that process dies, and this one can then stop the machine itself.
#
# Cancel is the closing of the child's stdin, not a signal. A closed pipe
# reaches the child even if this process is SIGKILLed, so the same mechanism
# covers "the user pressed Cancel" and "the app was force-quit".

#: The cross-process interlock, which had a writer and a reader but no refusal.
#:
#: ``pakon_scan`` has always written ``~/.pakon-scan-in-flight.json`` while a
#: scan is in flight, and ``probe()`` has always reported ``in_flight``. But
#: nothing ever refused on it, and ``ScanSupervisor``'s own guard is a lock
#: object in *this* interpreter's memory — it says nothing about a second
#: backend. That second backend is reachable: force-quit the window mid-scan
#: and the backend outlives it with its scan child still driving the transport;
#: relaunch, and a fresh backend starts, sees its own supervisor idle, and
#: opens the device.
#:
#: What happens then, on macOS, is worse than a refusal. libusb's darwin
#: backend opens the *device* with ``USBDeviceOpenSeize`` and, per its own
#: source, ignores ``kIOReturnExclusiveAccess`` there and carries on;
#: ``set_configuration`` is then a device-wide IOKit ``SetConfiguration``,
#: which — again per libusb's own comment, "setting configuration will
#: invalidate the interface" — tears down the interfaces of every client,
#: including the one streaming EP 0x86. ``Link.open`` swallows that USBError.
#: Only the ``claim_interface`` that follows is genuinely refused
#: (``USBInterfaceOpen`` → ``kIOReturnExclusiveAccess`` →
#: ``LIBUSB_ERROR_ACCESS``), and by then the damage is done. The kernel's
#: exclusion is real but it arrives one call too late to be an interlock, so
#: the interlock has to be ours and it has to be consulted before we open
#: anything at all.


def _pid_is_scan(pid: int) -> bool:
    """Is this pid actually a pakon scan, or just *a* live pid?

    ``os.kill(pid, 0)`` only answers "something with this number exists". Pids
    are recycled, and a marker left behind by a scan that died without clearing
    it will eventually name an unrelated process. Two things then go wrong, and
    the second is much worse than the first: the app refuses to probe forever
    because it believes a scan is running, and the panic stop SIGTERMs
    somebody else's process.

    So the owner is confirmed by its command line before it is either believed
    or signalled. A ``ps`` that fails is treated as "yes, it is a scan",
    because refusing to touch the machine is the safe direction to be wrong in
    — and the Stop button clears the marker, so that is never a dead end.
    """
    try:
        r = subprocess.run(["ps", "-p", str(pid), "-o", "command="],
                           capture_output=True, text=True, timeout=3)
    except Exception:                                       # noqa: BLE001
        return True
    if r.returncode != 0:
        return False                    # no such process
    return "pakon_scan" in (r.stdout or "")


def scan_marker_state() -> dict:
    """Who, if anyone, is driving the machine — across processes."""
    out = {"present": False, "pid": None, "alive": False, "mine": False,
           "stale_pid": False, "info": {}}
    try:
        if not scan.MARKER.is_file():
            return out
        out["present"] = True
        try:
            info = json.loads(scan.MARKER.read_text())
        except (OSError, json.JSONDecodeError):
            info = {}
        out["info"] = info
        pid = int(info.get("pid") or 0)
        out["pid"] = pid or None
        if not pid:
            return out
        # Our own scan child is not a conflict with us.
        child = SCAN.child_pid()
        out["mine"] = pid in (os.getpid(), child) if child else pid == os.getpid()
        try:
            os.kill(pid, 0)
            out["alive"] = True
        except OSError:
            out["alive"] = False
        if out["alive"] and not out["mine"] and not _pid_is_scan(pid):
            # The number is in use, but not by a scan. The marker outlived its
            # owner and the pid has been recycled.
            out["alive"] = False
            out["stale_pid"] = True
    except Exception:                                       # noqa: BLE001
        return out
    return out


def foreign_scan() -> dict | None:
    """A scan in flight owned by a live process that is not ours. Anything
    about to open the device must ask this first and take no for an answer."""
    st = scan_marker_state()
    return st if (st["alive"] and not st["mine"]) else None


def foreign_scan_refusal(st: dict) -> str:
    started = st.get("info", {}).get("started")
    when = (f", started {time.strftime('%H:%M:%S', time.localtime(started))}"
            if started else "")
    return (f"another process (pid {st.get('pid')}) is scanning{when}. Film is "
            f"moving and that process owns the USB interface; opening the "
            f"scanner now would take the transport out from under it. Stop "
            f"that scan first — the Stop button will do it.")


def stop_foreign_scan(timeout: float = 6.0) -> dict:
    """Ask the process that owns the transport to stop, and wait for it.

    ``scan.emergency_stop`` opens the device from scratch, so it cannot get
    through while another process still holds the interface: it burns its six
    retries and reports failure. The owner's pid is in the marker and
    ``pakon_scan`` stops the transport on SIGTERM, so the panic path asks the
    owner first and only takes the device once that process is gone.
    """
    st = scan_marker_state()
    out = {"owner_pid": st["pid"], "signalled": False, "exited": False,
           "mine": st["mine"], "stale_pid": st["stale_pid"]}
    # `alive` is already "alive AND is a pakon scan" — see _pid_is_scan. A
    # recycled pid must never be signalled: the panic button stops scanners,
    # not whatever else happens to hold that number.
    if not st["alive"] or st["mine"] or not st["pid"]:
        return out
    try:
        os.kill(st["pid"], signal.SIGTERM)
        out["signalled"] = True
    except OSError as e:
        out["error"] = str(e)
        return out
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            os.kill(st["pid"], 0)
        except OSError:
            out["exited"] = True
            break
        time.sleep(0.1)
    if not out["exited"]:
        try:
            os.kill(st["pid"], signal.SIGKILL)
            out["killed"] = True
        except OSError:
            pass
        time.sleep(0.5)
    return out


class ScanSupervisor:
    """At most one scan, at any time, with a stop on every way out."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.proc: subprocess.Popen | None = None
        self.job: str | None = None
        self.cancelled = False

    # ---- state ----
    def running(self) -> bool:
        with self.lock:
            return self.proc is not None and self.proc.poll() is None

    def current(self) -> str | None:
        with self.lock:
            return self.job if (self.proc and self.proc.poll() is None) else None

    def child_pid(self) -> int | None:
        """Our scan child's pid, for as long as we own it.

        Deliberately not gated on ``poll()``. Between the child exiting and
        ``_pump`` reaping it the pid is a zombie, and ``os.kill(pid, 0)`` on a
        zombie succeeds — so a poll-gated answer would briefly report our own
        just-finished scan as a *foreign* one and refuse to probe. The pid is
        ours until we drop the handle, which ``_pump`` does in its finally.
        """
        with self.lock:
            return self.proc.pid if self.proc else None

    # ---- start ----
    def start(self, jid: str, body: dict) -> dict:
        # Two guards, because they answer different questions. This one is
        # "am I already scanning"; the next is "is anything, anywhere,
        # already scanning" — and only the second survives a force-quit.
        if self.running():
            raise RuntimeError("a scan is already running")
        other = foreign_scan()
        if other:
            raise RuntimeError("Refusing to start a scan: "
                               + foreign_scan_refusal(other))

        base = int(body.get("base") or 16)
        seconds = scan.clamp_seconds(
            float(body.get("max_seconds") or scan.DEFAULT_MAX_SECONDS))
        # Default to the calibrated MotorSpeedPlus for the base rather
        # than leaving it None, so the job record and the UI show the
        # speed the capture will actually be taken at.
        speed = int(body.get("speed")
                    or scan.MOTOR_SPEED.get(base, scan.MOTOR_SPEED[16]))
        name = (body.get("name") or "").strip()
        stem = "".join(c for c in name if c.isalnum() or c in "-_ ").strip()
        stem = stem.replace(" ", "-") or time.strftime("scan-%Y%m%d-%H%M%S")
        out = CAPTURES / f"{stem}.bin"
        n = 1
        while out.exists():
            n += 1
            out = CAPTURES / f"{stem}-{n}.bin"

        cmd = [sys.executable, str(_TOOLS / "pakon_scan.py"), "run", str(out),
               "--json", "--watch-parent", "--base", str(base),
               "--max-seconds", str(seconds)]
        # Base 4/8 have no calibration of their own, so pakon_scan.py already
        # derives their exposure automatically -- this flag is only for
        # forcing the same derivation on base 16, to cross-check the
        # committed on-counts against the vendor formula instead of a fresh
        # scan silently trusting whichever one this call happened to use.
        if body.get("derive_exposure"):
            cmd += ["--derive-exposure"]
        if speed:
            cmd += ["--speed", str(int(speed))]
        if body.get("force"):
            cmd += ["--force"]
        # The lamp has died at ~60 s twice; the refresh is the experiment that
        # tests why, so it is a per-scan choice rather than a constant.
        if body.get("lamp_refresh") is not None:
            cmd += ["--lamp-refresh", str(float(body["lamp_refresh"]))]
        mode = body.get("lamp_refresh_mode")
        if mode in scan.LAMP_REFRESH_MODES:
            cmd += ["--lamp-refresh-mode", mode]

        # What the capture this scan is about to make should be decoded as.
        #
        # The scan is the main path, so nobody should have to answer "which
        # film is this" twice — once to start the scan and again to a file
        # dialog afterwards. It is recorded on the job rather than held in the
        # window that started it, because the scan outlives that window: a
        # relaunched app adopting a scan in flight has to be able to finish
        # the job properly, and that includes knowing how to open the result.
        #
        # Not `dx`: the child emits a `dx` event carrying the DX *board's*
        # reading, and a typed lookup must never be able to overwrite a
        # measurement under the same name.
        #
        # AND the same two facts go to the child on the command line, so they
        # reach the capture's own sidecar. `open_with` is a key in `S.jobs`, an
        # in-memory dict that dies with this backend; a capture that outlives
        # the process it was made by used to carry no statement at all of what
        # film the operator said it was. The sidecar is the durable copy.
        film_path = (body.get("film_path") or "").strip() or None
        dx_typed = (body.get("dx") or "").strip() or None
        refuse_film_choice(film_path, dx_typed)
        if film_path:
            cmd += ["--film-path", film_path]
        if dx_typed:
            cmd += ["--dx", dx_typed]
        open_with = {"film_path": film_path,
                     "dx": dx_typed,
                     "name": name or None}
        S.job_set(jid, kind="scan", status="running", phase="starting",
                  progress=0.0, message="starting the scan process",
                  path=str(out), base=base, max_seconds=seconds,
                  started=time.time(), lamp={}, lamp_duty=None,
                  window={}, run={},
                  bytes=0, lines=0, windows=0, sync_breaks=0,
                  stopped={}, cancellable=True, speed=speed,
                  open_with=open_with,
                  lamp_refresh={"mode": mode or "full",
                                "every_s": body.get("lamp_refresh")})
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, bufsize=1, text=True)
        with self.lock:
            self.proc, self.job, self.cancelled = proc, jid, False
        threading.Thread(target=self._pump, args=(jid, proc, out),
                         daemon=True).start()
        return {"id": jid, "path": str(out), "max_seconds": seconds}

    # ---- the child's progress stream ----
    def _pump(self, jid: str, proc: subprocess.Popen, out: Path) -> None:
        done: dict = {}
        try:
            for line in proc.stdout:
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(ev, dict):
                    continue
                kind = ev.get("t")
                if kind == "phase":
                    S.job_set(jid, phase=ev.get("phase") or "",
                              message=ev.get("message") or "")
                    if ev.get("phase") == "lamp":
                        # lamp_on() runs at the open-gate (dim) duty (docs/59);
                        # this is the real "warming up" moment. Advanced to
                        # "with-film" by the lamp_duty_switch event below, the
                        # instant the film sensors report film present.
                        S.job_set(jid, lamp_duty="open-gate")
                elif kind == "lamp":
                    # A lamp health poll: one right after the warm-up settle,
                    # before anything else has happened, and then one every
                    # LAMP_POLL_S for the rest of the run. This USED TO stamp
                    # the job "scanning" unconditionally -- which fired on the
                    # very first poll, seconds before the CCD was configured,
                    # the transport speed was set, or the motor had moved at
                    # all. That is why the UI jumped straight from "starting"
                    # to "Scanning" with no visible lamp warm-up/init lead-in:
                    # the real phase events below were being overwritten
                    # before the browser ever polled the job. `kind ==
                    # "window"` is the real "scanning" signal -- it only fires
                    # once actual image data is flowing.
                    S.job_set(jid, lamp=ev)
                elif kind == "lamp_duty_switch":
                    # docs/59: FN_bBeforeScan switches the lamp from the
                    # open-gate duty to the with-film duty the instant film is
                    # sensed in the gate -- the real "bright for the scan"
                    # transition. Surfaced so the UI can show it rather than
                    # silently drop it, which is what happened before this
                    # `elif` existed (the event has no other handler above).
                    S.job_set(jid, lamp_duty=ev.get("to") or "with-film",
                              lamp_duty_switch=ev)
                elif kind == "dx":
                    # One record, at the end of the scan. Carries the whole DX
                    # summary including product/specifier, which are null
                    # unless a code word was read unambiguously.
                    S.job_set(jid, dx=ev)
                elif kind == "window":
                    w, r = ev.get("window") or {}, ev.get("run") or {}
                    S.job_set(
                        jid, phase="scanning", window=w, run=r,
                        bytes=ev.get("bytes", 0), elapsed=ev.get("elapsed", 0),
                        lines=r.get("lines", 0),
                        state=w.get("state"),
                        message=f"{r.get('lines', 0):,} lines · "
                                f"{w.get('state', '')}")
                elif kind == "warn":
                    # ACCUMULATED, NOT OVERWRITTEN. This was a single scalar,
                    # so each warning replaced the last and a scan that warned
                    # about a mis-load and later about anything else kept only
                    # the second. The mis-load warnings are the ones that most
                    # need to survive: FilmSense warns once per condition, at
                    # the moment it is first seen, and never repeats it.
                    S.job_append(jid, "warnings", ev.get("message"))
                    S.job_set(jid, warning=ev.get("message"))
                elif kind == "error":
                    S.job_set(jid, error=ev.get("message"))
                elif kind == "done":
                    done = ev
                elif kind == "stop":
                    S.job_set(jid, stopped=ev)
        except Exception as e:                              # noqa: BLE001
            S.job_set(jid, error=f"progress stream lost: {e}")
        finally:
            try:
                err = (proc.stderr.read() or "")[-2000:]
            except Exception:                               # noqa: BLE001
                err = ""
            code = proc.wait()
            self._finish(jid, code, done, out, err)
            with self.lock:
                if self.proc is proc:
                    self.proc, self.job = None, None

    def _finish(self, jid: str, code: int, done: dict, out: Path,
                err: str) -> None:
        """Decide what happened, and make sure the machine is stopped.

        The one outcome that must never be reported as fine is "the scan
        process is gone and nobody confirmed the transport stopped". If the
        child did not say it stopped the motor, this process opens the device
        and stops it — which it can, because the child is dead and the kernel
        has released the interface.
        """
        stopped = done.get("stopped") or {}
        recovered = None
        if not stopped.get("motor"):
            recovered = scan.emergency_stop()
            scan.marker_clear()

        size = out.stat().st_size if out.is_file() else 0
        reason = done.get("reason") or ("killed" if code < 0 else "unknown")
        ok = bool(done.get("ok")) and size > 0
        lines = int(done.get("lines") or 0)
        # Whether the capture is worth decoding, decided here so that the one
        # rule lives in one place. A cancelled scan counts: the film that did
        # go past the sensor is real and the owner should see it rather than
        # be told to go and find the file. A scan stopped on DARK does not —
        # the lamp had failed, so the frames after that point are not
        # photographs of anything.
        openable = bool(ok and size and lines)
        # A scan that stopped on DARK is not a failure of this software — it is
        # the software working — but it is not a usable roll either.
        friendly = {
            "roll_end": "Roll end — the gate has been clear since the film ran out.",
            "dark": "Stopped: the sensor went dark. The lamp has failed or the "
                    "path is blocked.",
            "lamp_fault": "Stopped: the light board reported a fault.",
            "time_limit": "Stopped at the time limit.",
            "cancelled": "Cancelled.",
            "stalled": "Stopped: the sensor stopped delivering data.",
            "size_limit": "Stopped at the size limit.",
            "killed": "The scan process was killed.",
        }.get(reason, reason)
        # A scan refused before anything moved never emits a `done` event, so
        # `reason` is "unknown" and the lane read `unknown` — the least useful
        # word available for the most common outcome there is, a scanner that
        # is not plugged in. The child's own refusal text is right there.
        detail = done.get("detail") or err.strip()
        if reason == "unknown" and detail:
            friendly = detail.split("\n")[0][:160]

        S.job_set(
            jid,
            status="done" if (ok or reason in ("cancelled", "dark", "lamp_fault",
                                               "time_limit", "stalled"))
                   else "error",
            progress=1.0, phase="done", reason=reason, ok=ok,
            openable=openable,
            message=friendly, detail=detail,
            bytes=size, lines=lines,
            windows=done.get("windows", 0),
            sync_breaks=done.get("sync_breaks", 0),
            seconds=done.get("seconds", 0), mib_s=done.get("mib_s", 0),
            lamp=done.get("lamp") or {}, run=done.get("run") or {},
            lamp_refresh=done.get("lamp_refresh") or {},
            lamp_watchdog=done.get("lamp_watchdog") or {},
            # The machine's own film-position report, and the mis-load
            # warnings that go with it. Warnings, not errors: the vendor has no
            # abort path for tail-first or emulsion-down either (docs/53 s4.2).
            film_sense=done.get("film_sense") or {},
            metadata=done.get("metadata"),
            stopped=stopped or {}, recovered=recovered,
            transport_stopped=bool(stopped.get("motor")
                                   or (recovered or {}).get("motor")
                                   or (recovered or {}).get("absent")),
            exit_code=code, cancellable=False,
            path=str(out) if size else None,
            error=(None if (ok or reason in ("cancelled", "dark", "lamp_fault",
                                             "time_limit", "stalled"))
                   else (done.get("detail") or err.strip() or friendly)),
        )

    # ---- stop ----
    def cancel(self, jid: str | None = None) -> dict:
        """Close the pipe, then escalate. Must land inside a second."""
        with self.lock:
            proc, cur = self.proc, self.job
            self.cancelled = True
        if proc is None or proc.poll() is not None:
            return {"cancelled": False, "reason": "no scan is running"}
        if jid and cur and jid != cur:
            return {"cancelled": False, "reason": "that scan is not running"}
        S.job_set(cur, phase="cancelling", message="stopping the transport")
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()          # the child's watchdog sees EOF
        except (OSError, ValueError):
            pass
        try:
            proc.send_signal(signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # It is not shutting down and it is holding the USB handle, so take
            # the handle away from it and stop the machine ourselves.
            try:
                proc.kill()
            except (OSError, ProcessLookupError):
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            return {"cancelled": True, "escalated": "killed",
                    "stopped": scan.emergency_stop()}
        return {"cancelled": True}

    def shutdown(self) -> None:
        """Called on quit. Closing our end of the pipe is what the child is
        waiting on, so this works even from an interpreter that is dying."""
        if self.running():
            self.cancel()


SCAN = ScanSupervisor()


_HW_CACHE: dict = {"at": 0.0, "value": None}
_HW_TTL = 3.0

# Auto-load: when a live probe finds an unloaded scanner on the bus, load
# firmware onto it without waiting for someone to run tools/pakon_load.py by
# hand. This calls that exact script as a subprocess rather than reimplementing
# any of its logic -- its own safety checks (refuse to guess an unrecognised
# model, cross-check the 0xA9 personality against the USB identity, verify the
# re-enumerated PID matches the image that was sent) are what make firing it
# unattended safe, and they must not drift from the one place they're written.
_FW_LOAD: dict = {"active": False, "at": 0.0, "result": None}
_FW_LOAD_COOLDOWN = 15.0   # do not hammer a scanner that just failed to load


# Film transport jog: the operator moving film from the UI, to respool a roll
# or reposition it in the gate, without dropping to a terminal.
#
# Same reasoning as the firmware auto-load above. tools/spin_motor.py is run as
# a subprocess rather than reimplemented here, because the one thing that makes
# driving the motor safe lives in that file: the stop packet (04 03 44 00 A2) is
# sent from a `finally:` block, so it goes out on a clean finish, on a USB
# error, on an unhandled exception, and on the SIGTERM this module sends if the
# child overruns its deadline. The speed clamp is in the same place. A second
# copy of either here would be a second copy that can rot out of step with the
# audited one -- and the failure mode of a rotted copy is film still moving.
#
# The packets themselves are docs/12-command-protocol.md section 5(b), decoded
# from FN_bDriveMotorAdvanceFilm = fcn.1000b6d0, addressed to 0x44 (AD_MOTOR,
# the PICM_PLUS application, which contains no TBLWT and cannot write flash).
JOG_SPEED_MIN, JOG_SPEED_MAX = 0x03E8, 0x7FFE   # spin_motor.SPEED_MIN/MAX
JOG_MAX_SECONDS = 5.0                           # spin_motor.MAX_SECONDS
JOG_MAX_SECONDS_LONG = 60.0                     # spin_motor.MAX_SECONDS_LONG
JOG_DEFAULT_SECONDS = 1.0

#: One jog at a time, and nothing else may probe USB while one is in flight.
#: This is the same fact `SCAN.running()` records for a scan -- a process is
#: holding the interface -- kept here because a jog is ours, not a scan child's.
_JOG: dict = {"active": False, "at": 0.0, "direction": None, "seconds": 0.0,
              "proc": None}
_JOG_LOCK = threading.Lock()


def _auto_load_firmware() -> None:
    cmd = [sys.executable, str(_TOOLS / "pakon_load.py")]
    try:
        r = subprocess.run(cmd, cwd=str(_ROOT), capture_output=True,
                           text=True, timeout=40)
        _FW_LOAD["result"] = {"ok": r.returncode == 0,
                              "returncode": r.returncode,
                              "stdout": r.stdout[-2000:],
                              "stderr": r.stderr[-2000:]}
    except Exception as e:                                  # noqa: BLE001
        _FW_LOAD["result"] = {"ok": False, "error": str(e)}
    finally:
        _FW_LOAD["active"] = False
        _FW_LOAD["at"] = time.time()
        # The state this thread just changed on the wire is stale the moment
        # it's written -- force the next hardware_state() to probe for real
        # rather than hand back the pre-load "needs_firmware" cache entry.
        _HW_CACHE.update(at=0.0, value=None)


def _maybe_auto_load_firmware(p: dict) -> None:
    """Fire the loader in the background if, and only if, a live probe just
    found an unloaded scanner. Never called from the cached or scan-in-progress
    paths in hardware_state() -- those must not touch USB at all."""
    if p.get("state") != "needs_firmware" or _FW_LOAD["active"]:
        return
    if time.time() - _FW_LOAD["at"] < _FW_LOAD_COOLDOWN:
        return
    _FW_LOAD.update(active=True, at=time.time())
    threading.Thread(target=_auto_load_firmware, daemon=True).start()


def hardware_state(fresh: bool = False) -> dict:
    """One place the UI can ask what the machine is, without writing to it.

    Two guards. While a scan is running the child process owns the USB
    interface, so this must not try to claim it — it reports the last known
    state instead. And the probe is cached briefly, because several screens ask
    for it and each live probe is a USB round trip.

    ``fresh`` is the user pressing Recheck: it skips the cache but not the
    scan-in-progress guard, because no button may take the USB handle away
    from a running scan. Asked during a scan it says so — ``cached`` stays
    true and ``recheck_refused`` explains why — rather than quietly returning
    a stale answer to someone who just asked for a current one.

    The polled path is deliberately cheap and the on-demand path deliberately
    is not: a scanner that was switched off ten seconds ago should show as
    gone within one poll, and someone who has just plugged one in should not
    have to wait for one.
    """
    running = SCAN.running()
    # THE THIRD GUARD, and the one that was missing. `running` is this
    # process's own scan. A scan started by a backend that outlived its window
    # is just as real and just as fatal to probe past: scan.probe() ends in
    # Link.open(), and Link.open() does not survive contact with an interface
    # somebody else is streaming from. The marker is the only thing that knows.
    other = foreign_scan()
    # A jog is the same hazard in a smaller package: spin_motor.py has claimed
    # interface 0 for a few seconds, and a probe landing in the middle of it
    # would fail its claim -- reporting the machine as gone while it is in fact
    # turning. The 15 s hardware poll would otherwise walk straight into it.
    jogging = _JOG["active"]
    now = time.time()
    warm = bool(_HW_CACHE["value"]) and now - _HW_CACHE["at"] < _HW_TTL
    refused = fresh and (running or other or jogging)
    if running or other or jogging or (warm and not fresh):
        p = dict(_HW_CACHE["value"] or {"present": False, "state": "unknown",
                                        "hint": "not probed yet"})
        p["cached"] = True
    else:
        try:
            p = scan.probe()
        except Exception as e:                              # noqa: BLE001
            p = {"present": False, "state": "error", "hint": str(e)}
        p["cached"] = False
        _HW_CACHE.update(at=now, value=dict(p))
        _maybe_auto_load_firmware(p)
    p["probed_at"] = _HW_CACHE["at"] or None
    p["age_s"] = round(now - _HW_CACHE["at"], 2) if _HW_CACHE["at"] else None
    p["firmware_load"] = {"active": _FW_LOAD["active"],
                          "result": _FW_LOAD["result"]}
    if _FW_LOAD["active"] and p.get("state") == "needs_firmware":
        p["state"] = "loading_firmware"
        p["hint"] = "Firmware detected missing -- loading it automatically now."
    if refused:
        p["recheck_refused"] = (
            "the film transport is being jogged; the machine cannot be probed "
            "until it stops" if jogging and not (running or other) else
            "a scan owns the USB interface; the machine cannot be probed "
            "until it ends")
    if jogging:
        p["jog"] = {"active": True, "direction": _JOG["direction"],
                    "seconds": _JOG["seconds"], "started": _JOG["at"]}
    if other:
        # Deliberately NOT rewritten into `state`: the last known state is
        # still the truth about the machine, and `cached` already says it is
        # not current. This adds the one fact the UI cannot infer.
        p["foreign_scan"] = {"pid": other["pid"],
                             "started": other["info"].get("started"),
                             "path": other["info"].get("path")}
        p["hint"] = foreign_scan_refusal(other)
    p["scan_running"] = running or bool(other)
    p["scan_job"] = SCAN.current()
    p["limits"] = {
        "default_seconds": scan.DEFAULT_MAX_SECONDS,
        "lamp_refresh_s": scan.LAMP_REFRESH_S,
        "lamp_refresh_modes": list(scan.LAMP_REFRESH_MODES),
        "hard_seconds": scan.HARD_MAX_SECONDS,
        "min_seconds": scan.MIN_MAX_SECONDS,
        "speeds": scan.MOTOR_SPEED,
        "speed_min": scan.pc.MOTOR_SPEED_MIN_PLUS,
        "speed_max": scan.pc.MOTOR_SPEED_MAX_PLUS,
        "decodable_bases": list(scan.DECODABLE_BASES),
        "jog": {"default_seconds": JOG_DEFAULT_SECONDS,
                "max_seconds": JOG_MAX_SECONDS,
                "max_seconds_long": JOG_MAX_SECONDS_LONG,
                "speed_min": JOG_SPEED_MIN,
                "speed_max": JOG_SPEED_MAX},
    }
    return p


def emergency_stop_now() -> dict:
    """Stop the machine, from any state, whoever owns it.

    Four moves, in the only order that can work:

    1. Cancel our own scan child, which stops the transport properly — it
       still holds the interface and can talk to the board. A jog child, if
       one is running, goes the same way and for the same reason.
    2. If the marker names a *live foreign* owner, signal it and wait. This is
       the case ``emergency_stop`` alone cannot handle: it opens the device
       from scratch, so while another process holds the interface it burns all
       six retries on a claim that macOS refuses and reports failure. Asking
       the owner to stop is both faster and the only thing that actually stops
       the film.
    3. Then, and only then, open the device ourselves and stop it — for the
       case where the owner is already dead and the transport is still turning.

    The marker is cleared only once nothing live holds it and the stop was
    confirmed (or there is no scanner), so a panic press cannot leave the app
    permanently convinced someone else is scanning.
    """
    out: dict = {"cancelled": SCAN.cancel()}
    # A jog is film moving too, and it is ours — so it is stopped first and by
    # the same logic as step 2 below: the child holds the interface, so asking
    # it to stop is both faster and the only thing that reaches the board while
    # it does. Step 3 could not claim the device until this returns.
    if _JOG["active"]:
        out["jog"] = stop_jog()
    other = foreign_scan()
    if other:
        out["foreign"] = stop_foreign_scan()
    out.update(scan.emergency_stop())
    st = scan_marker_state()
    if st["present"] and not (st["alive"] and not st["mine"]):
        if out.get("motor") or out.get("absent"):
            scan.marker_clear()
            out["marker_cleared"] = True
    out["marker"] = scan_marker_state()
    return out


def jog_refusal() -> str | None:
    """Why the transport may not be jogged right now, in the operator's words.

    The same two questions ``ScanSupervisor.start`` and ``hardware_state`` ask,
    in the same order, because they have the same answer: something else is
    holding the USB interface and ``spin_motor.open_scanner`` -- which ends in
    ``usb.util.claim_interface`` -- does not survive contact with it.

      * ``SCAN.running()`` is this process's own scan child.
      * ``foreign_scan()`` is a scan owned by a backend that outlived its
        window. The on-disk marker is the only thing that knows, and this is
        the case that survives a force-quit.

    Then one of our own: two jogs at once would be two processes fighting for
    the interface, and the loser's ``finally:`` stop would land on a device it
    never opened.
    """
    if SCAN.running():
        return ("a scan is running in this window. It owns the USB interface "
                "and is already driving the transport; jogging now would take "
                "the film out from under it. Stop the scan first.")
    other = foreign_scan()
    if other:
        return foreign_scan_refusal(other)
    if _JOG["active"]:
        d = _JOG["direction"] or "forward"
        return (f"the transport is already jogging {d}. Wait for it to stop — "
                f"it stops on its own, and the Stop button reaches it too.")
    return None


def stop_jog(timeout: float = 6.0) -> dict:
    """Interrupt a jog in flight, by the one route that still sends the stop.

    SIGINT, not SIGTERM. Python's default SIGTERM disposition kills the process
    outright and no ``finally:`` block runs — which would leave the transport
    turning on the last command it was given, the exact failure this endpoint
    exists to make impossible. SIGINT raises KeyboardInterrupt inside the child,
    and spin_motor.py's stop packet is in a ``finally:`` that unwinds through
    it; its docstring names KeyboardInterrupt as a case it covers.

    SIGKILL is the last resort and never the first move, for the same reason.
    """
    out = {"active": _JOG["active"], "signalled": False, "exited": False}
    proc = _JOG.get("proc")
    if proc is None or proc.poll() is not None:
        return out
    try:
        proc.send_signal(signal.SIGINT)
        out["signalled"] = True
    except Exception as e:                                  # noqa: BLE001
        out["error"] = str(e)
        return out
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            out["exited"] = True
            break
        time.sleep(0.1)
    if not out["exited"]:
        try:
            proc.kill()
            out["killed"] = True
        except Exception:                                   # noqa: BLE001
            pass
    return out


def motor_jog(body: dict) -> dict:
    """Drive the film transport for a few seconds, forward or reverse.

    Runs tools/spin_motor.py as a subprocess; see the note on _JOG above for
    why that script and not an inline copy of its three packets.

    Everything the client sends is clamped again here. The UI's own limits are
    a convenience for the person using it, not a guarantee about what arrives
    on this socket: `seconds` is capped at JOG_MAX_SECONDS unless `long` is
    explicitly set, exactly as spin_motor.py's --long works, and `speed` is
    held inside the documented legal range for the Plus motor board.
    """
    direction = str(body.get("direction") or "").strip().lower()
    if direction not in ("forward", "reverse"):
        return {"ok": False, "error": "direction must be 'forward' or "
                                      f"'reverse', not {direction!r}"}

    long_run = bool(body.get("long"))
    cap = JOG_MAX_SECONDS_LONG if long_run else JOG_MAX_SECONDS
    try:
        seconds = float(body.get("seconds") or JOG_DEFAULT_SECONDS)
    except (TypeError, ValueError):
        seconds = JOG_DEFAULT_SECONDS
    seconds = max(0.1, min(cap, seconds))
    try:
        speed = int(body.get("speed") or JOG_SPEED_MIN)
    except (TypeError, ValueError):
        speed = JOG_SPEED_MIN
    speed = max(JOG_SPEED_MIN, min(JOG_SPEED_MAX, speed))

    # Who holds the interface, before anything else. Asked here as well as
    # under the lock below because during a scan `hardware_state()` answers
    # from a cache that may never have been filled — and "no scanner" is the
    # wrong sentence to hand someone whose scanner is busy scanning.
    why = jog_refusal()
    if why:
        return {"ok": False, "refused": True, "error": why}

    # Then presence, from the cache-or-probe path that already refuses to touch
    # USB during a scan, so this cannot be the thing that collides.
    hw = hardware_state()
    if hw.get("simulated"):
        return {"ok": False, "refused": True,
                "error": "this is a simulated scanner replaying a capture "
                         "file. There is no motor and no film to move."}
    if not hw.get("present"):
        return {"ok": False, "refused": True,
                "error": "no scanner at 0f05:f135 on USB."}
    if _FW_LOAD["active"] or hw.get("state") == "loading_firmware":
        return {"ok": False, "refused": True,
                "error": "firmware is being loaded onto the scanner right now, "
                         "and that loader owns the USB interface. It takes a "
                         "few seconds."}
    if hw.get("state") != "ready":
        return {"ok": False, "refused": True,
                "error": hw.get("hint") or f"the scanner is {hw.get('state')}; "
                                           f"the motor board at 0x44 answers "
                                           f"only once firmware is loaded."}

    with _JOG_LOCK:
        why = jog_refusal()
        if why:
            return {"ok": False, "refused": True, "error": why}
        _JOG.update(active=True, at=time.time(), direction=direction,
                    seconds=seconds)

    cmd = [sys.executable, str(_TOOLS / "spin_motor.py"),
           "--speed", str(speed), "--seconds", str(seconds)]
    if direction == "reverse":
        cmd.append("--reverse")
    if long_run:
        cmd.append("--long")

    out: dict = {"direction": direction, "seconds": seconds, "speed": speed,
                 "long": long_run}
    proc = None
    try:
        proc = subprocess.Popen(cmd, cwd=str(_ROOT), text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _JOG["proc"] = proc
        # The child's own sleep is `seconds`; the slack covers opening the
        # device and the three USB round trips. An overrun past that is handled
        # by stop_jog(), not by killing it — see that function for why the
        # signal matters.
        try:
            so, se = proc.communicate(timeout=seconds + 20)
        except subprocess.TimeoutExpired:
            out["overran"] = stop_jog()
            so, se = proc.communicate(timeout=10)
            out["timed_out"] = True
        rc = proc.returncode
        out.update(ok=rc == 0 and not out.get("timed_out"), returncode=rc,
                   stdout=(so or "")[-2000:], stderr=(se or "")[-2000:])
        if out.get("timed_out"):
            out["error"] = ("the jog overran its deadline and was interrupted. "
                            "The stop went out on the way through — look at the "
                            "transport before jogging again.")
        elif rc != 0:
            out["error"] = ((se or so or "").strip().splitlines() or
                            [f"spin_motor.py exited {rc}"])[-1]
    except Exception as e:                                  # noqa: BLE001
        # Nothing here can leave the child running: if it was started at all it
        # is either reaped above or interrupted here, and its own finally:
        # sends the stop either way.
        if proc is not None and proc.poll() is None:
            stop_jog()
        out.update(ok=False, error=f"{type(e).__name__}: {e}")
    finally:
        _JOG.update(active=False, at=time.time(), direction=None, seconds=0.0,
                    proc=None)
        # The device was opened and closed by another process; whatever this
        # one last cached about it is no longer a live answer.
        _HW_CACHE.update(at=0.0, value=None)
    return out


def scan_startup_check() -> dict:
    """A scan orphaned by a crash is still driving film. Look, at every start."""
    try:
        return scan.check_stale()
    except Exception as e:                                  # noqa: BLE001
        return {"stale": False, "error": str(e)}


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def _json(h, obj, code=200):
    body = json.dumps(obj).encode()
    h.send_response(code)
    h.send_header("Content-Type", "application/json")
    h.send_header("Content-Length", str(len(body)))
    h.send_header("Access-Control-Allow-Origin", "*")
    h.end_headers()
    h.wfile.write(body)


def _bin(h, body: bytes, ctype: str, code=200, cache=False):
    h.send_response(code)
    h.send_header("Content-Type", ctype)
    h.send_header("Content-Length", str(len(body)))
    h.send_header("Access-Control-Allow-Origin", "*")
    if cache:
        h.send_header("Cache-Control", "public, max-age=31536000, immutable")
    h.end_headers()
    h.wfile.write(body)


def _body(h) -> dict:
    n = int(h.headers.get("Content-Length") or 0)
    if not n:
        return {}
    try:
        return json.loads(h.rfile.read(n).decode() or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def roll_json(roll: "pr.Roll") -> dict:
    d = roll.to_json()
    d["frames"] = [{
        "index": f.index, "a": f.a, "b": f.b,
        "confidence": f.confidence,
        "params": pr.merged_params(f.params),
        "adjusted": pr.is_adjusted(f.params),
        "summary": pr.describe_params(f.params),
        "exported": f.exported,
        "version": _pv(f.params),
    } for f in roll.frames]
    d["ir"] = getattr(roll, "ir", {})
    d["unavailable_controls"] = pr.UNAVAILABLE_CONTROLS
    # Snapshots have been taken before every destructive edit since undo was
    # added, and POST roll/<id>/undo has served them, but no roll payload ever
    # carried the fact that one existed -- so no screen could offer it, and
    # apply-to-roll's own confirmation text promised "This can be undone"
    # beside no way to do it. This is the missing half.
    d["undo"] = S.undo_state(roll.id)
    cv = 75.0
    try:
        cv = float(roll.engine().shasta.code_values_per_button)
    except Exception:                                       # noqa: BLE001
        pass
    d["units"] = {
        "kind": "step",
        "code_values_per_button": cv,
        "note": "Corrections are applied to the toned RPD after the auto "
                "chain, in the vendor's own codeValuesPerButton unit "
                f"({cv:g} code values of {pr.ansel.SHASTA_MAX}). Not "
                "D-units: past the Shasta and FUGC tone LUTs the code values "
                "are no longer linear in density, so a D conversion would be "
                "invented.",
    }
    return d


def _pv(params) -> str:
    """Short hash of the parameters, used to bust the image cache."""
    return hashlib.sha1(
        json.dumps(pr.merged_params(params), sort_keys=True).encode()
    ).hexdigest()[:10]


class H(_BASE):                                     # type: ignore[misc,valid-type]
    server_version = "PakonApp/1.0"

    def log_message(self, *a):                      # noqa: A003
        pass

    def do_OPTIONS(self):                           # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    # ---------------------------------------------------------------- GET
    def do_GET(self):                               # noqa: N802
        u = urlparse(self.path)
        p, q = u.path, parse_qs(u.query)
        try:
            if p.startswith("/api/app/"):
                return self._app_get(p[len("/api/app/"):], q)
        except Exception as e:                      # noqa: BLE001
            return _json(self, {"error": str(e),
                                "trace": traceback.format_exc()[-1500:]}, 500)
        if _HAVE_UI:
            return super().do_GET()
        return _json(self, {"error": "not found"}, 404)

    def _app_get(self, route: str, q: dict):
        if route == "health":
            return _json(self, {"ok": True, "pid": os.getpid(),
                                "ui_backend": _HAVE_UI})

        if route == "bootstrap":
            return _json(self, {
                "workspace": workspace_state(),
                "captures": list_captures(),
                "captures_dir": str(CAPTURES),
                "legacy_captures_dir": (str(LEGACY_CAPTURES)
                                        if LEGACY_CAPTURES.is_dir() else None),
                "unavailable_controls": pr.UNAVAILABLE_CONTROLS,
                "calibration": calibration_info(),
                # Disk only -- this must not cause USB traffic on bootstrap.
                "calibration_store": calibration_store_state(),
                "vendor_data": {
                    "data_dir": pr.dec.DEFAULT_DATA_DIR,
                    "data_dir_ok": Path(pr.dec.DEFAULT_DATA_DIR).is_dir(),
                    "ansel_root": pr.dec.DEFAULT_ANSEL_ROOT,
                    "ansel_root_ok": Path(pr.dec.DEFAULT_ANSEL_ROOT).is_dir(),
                },
                "film_paths": ["ColNeg", "BnW", "POSITIVE", "IMPORTED"],
                "hardware": hardware_state(),
            })

        if route == "hardware":
            return _json(self, hardware_state(
                fresh=(q.get("fresh") or ["0"])[0] not in ("0", "", "false")))

        if route == "calibration":
            return _json(self, calibration_state())

        if route == "captures":
            return _json(self, list_captures())

        if route == "paths":
            # So the native file dialogs open where captures actually are.
            # main.js used to default to `repoRoot()/captures`, which when
            # packaged is inside the .app bundle.
            return _json(self, {
                "captures": str(CAPTURES),
                "legacy_captures": (str(LEGACY_CAPTURES)
                                    if LEGACY_CAPTURES.is_dir() else None),
                "workspace": str(WORKSPACE),
                "sidecars": str(SIDECARS),
            })

        if route == "workspace":
            return _json(self, workspace_state())

        if route == "session":
            return _json(self, unexported_summary())

        if route == "rolls":
            return _json(self, [roll_json(r) for r in S.fresh_rolls()])

        if route == "diagnostics":
            return _json(self, diagnostics())

        if route.startswith("job/"):
            j = S.job_get(route[4:])
            return _json(self, j or {"error": "unknown job"},
                         200 if j else 404)

        parts = route.split("/")
        if parts[0] == "roll" and len(parts) >= 2:
            roll = S.get_roll(parts[1])
            if roll is None:
                return _json(self, {"error": "unknown roll"}, 404)
            if len(parts) == 2:
                return _json(self, roll_json(roll))
            if parts[2] == "frame" and len(parts) >= 4:
                return self._frame_image(roll, int(parts[3]), q)
            if parts[2] == "hist" and len(parts) >= 4:
                return _json(self, pr.frame_histogram(roll, int(parts[3])))
        return _json(self, {"error": "not found"}, 404)

    def _frame_image(self, roll, index: int, q: dict):
        scale = (q.get("scale") or ["preview"])[0]
        if scale not in pr.SCALES:
            scale = "preview"
        max_edge = int((q.get("max") or [0])[0]) or None
        if index < 0 or index >= len(roll.frames):
            return _json(self, {"error": f"frame {index} of "
                                         f"{len(roll.frames)}"}, 404)
        f = roll.frames[index]
        key = f"{roll.id}:{index}:{scale}:{max_edge}:{_pv(f.params)}"
        hit = S.cache_get(key)
        if hit is None:
            t0 = time.perf_counter()
            try:
                img = pr.render_frame(roll, index, None, scale=scale,
                                      max_edge=max_edge)
            except pr.gocol.GoColourError as e:
                # A REFUSAL, not a crash. The colour engine declines to guess
                # — no film base, no film class, no stock — and it says why in
                # prose. app/src/api.js:frameError re-requests this URL when
                # the <img> fails and prints `.error`, so the operator reads
                # the engine's own words instead of an empty stage.
                #
                # 422, not 500: the request was understood and the render was
                # declined. A 500 would say the backend broke, which sends
                # whoever is holding it looking in the wrong place — that is
                # how this failure was first mistaken for a UI bug.
                # No Cache-Control: a refusal must not be cached, because the
                # operator's next action is usually to fix its cause.
                return _json(self, e.as_dict(), 422)
            except ValueError as e:
                # The Python-side refusals at the front door — no film
                # selected, no resolved film path, DX did not resolve. Same
                # shape, same status, so the UI has one thing to display.
                return _json(self, {"error": str(e), "engine": "python",
                                    "kind": "refused"}, 422)
            hit = pr.encode(img, "JPEG", quality=90)
            S.cache_put(key, hit)
            self._last_ms = (time.perf_counter() - t0) * 1000.0
        return _bin(self, hit, "image/jpeg", cache=True)

    # --------------------------------------------------------------- POST
    def do_POST(self):                              # noqa: N802
        u = urlparse(self.path)
        try:
            if u.path.startswith("/api/app/"):
                return self._app_post(u.path[len("/api/app/"):], _body(self))
        except Exception as e:                      # noqa: BLE001
            return _json(self, {"error": str(e),
                                "trace": traceback.format_exc()[-1500:]}, 500)
        if _HAVE_UI:
            return super().do_POST()
        return _json(self, {"error": "not found"}, 404)

    def _app_post(self, route: str, body: dict):
        if route == "open":
            jid = S.job_new("open")
            threading.Thread(target=job_open, args=(jid, body),
                             daemon=True).start()
            return _json(self, {"id": jid})

        if route == "resume":
            # "open" always mints a new roll id and re-decodes from the raw
            # capture -- there was no way back into an already-decoded
            # workspace (rgb14.npy + roll.json already on disk) without that
            # full redo, which a backend restart made unavoidable even for a
            # roll nothing about the capture itself required re-reading. This
            # loads the cached roll.json straight in, the same cheap path
            # get_roll() uses for an in-memory roll whose file changed underneath
            # it -- Roll.from_json() never touches rgb14.npy or the .bin.
            roll_id = (body.get("roll") or "").strip()
            if not roll_id:
                return _json(self, {"error": "no roll id"}, 400)
            meta_path = WORKSPACE / roll_id / "roll.json"
            if not meta_path.is_file():
                return _json(self, {"error": f"no workspace for {roll_id!r}"}, 404)
            try:
                roll = pr.Roll.from_json(json.loads(meta_path.read_text()))
            except Exception as e:                          # noqa: BLE001
                return _json(self, {"error": f"{type(e).__name__}: {e}"}, 500)
            with S.lock:
                S.rolls[roll.id] = roll
            S._roll_mtime[roll.id] = meta_path.stat().st_mtime
            return _json(self, roll_json(roll))

        if route == "export":
            jid = S.job_new("export")
            threading.Thread(target=job_export, args=(jid, body),
                             daemon=True).start()
            return _json(self, {"id": jid})

        if route == "export/plan":
            # Synchronous and read-only: it stats paths and renders nothing,
            # so the screen can ask before it commits without a job round trip.
            return _json(self, export_plan(body))

        if route == "film":
            if film is None:
                return _json(self, {"error": "filmstock unavailable"}, 503)
            try:
                p1, p2 = film.parse_dx(body.get("dx") or "")
                s = film.lookup(p1, p2)
            except Exception as e:                  # noqa: BLE001
                return _json(self, {"error": str(e)}, 400)
            return _json(self, {"name": s.name, "manufacturer": s.manufacturer,
                                "path": s.path, "iso": s.iso,
                                "sba_override": s.sba_override})

        if route == "workspace/purge":
            return _json(self, purge(body))

        # ---- calibration ----
        if route == "calibration/read":
            return _json(self, calibration_read(body))

        if route == "calibration/select":
            return _json(self, calibration_select(body))

        if route == "calibration/run":
            jid = S.job_new("calibration")
            started = calibration_run(jid, body)
            if "error" in started:
                return _json(self, started, 409)
            return _json(self, started)

        # ---- scanning ----
        if route == "scan":
            jid = S.job_new("scan")
            try:
                return _json(self, SCAN.start(jid, body))
            except Exception as e:                          # noqa: BLE001
                S.job_set(jid, status="error", error=str(e))
                return _json(self, {"error": str(e), "id": jid}, 409)

        if route == "scan/cancel":
            return _json(self, SCAN.cancel(body.get("id")))

        if route == "motor":
            # Synchronous: the answer is what the transport actually did, and
            # the caller is a person watching the machine. Bounded by the same
            # cap the child enforces, so it cannot hold the connection open
            # longer than the jog it asked for.
            res = motor_jog(body)
            return _json(self, res, 200 if res.get("ok") else 409)

        if route == "scan/stop":
            # The panic button. Always allowed, never queued, and it does not
            # care whether this process thinks a scan is running.
            return _json(self, emergency_stop_now())

        parts = route.split("/")
        if parts[0] == "roll" and len(parts) >= 3:
            roll = S.get_roll(parts[1])
            if roll is None:
                return _json(self, {"error": "unknown roll"}, 404)

            if parts[2] == "frame" and len(parts) >= 4:
                i = int(parts[3])
                f = roll.frames[i]
                if body.get("reset"):
                    S.snapshot(roll, f"reset frame {i + 1}")
                    f.params = {}
                else:
                    f.params = pr.merged_params({**(f.params or {}),
                                                 **(body.get("params") or {})})
                S.cache_drop(f"{roll.id}:{i}:")
                save_sidecar(roll)
                return _json(self, roll_json(roll))

            if parts[2] == "apply-to-roll":
                return _json(self, apply_to_roll(roll, body))

            if parts[2] == "undo":
                return _json(self, undo_roll(roll))

            if parts[2] == "boundary":
                return _json(self, edit_boundary(roll, body))

            if parts[2] == "rename":
                roll.name = (body.get("name") or roll.name).strip() or roll.name
                save_sidecar(roll)
                return _json(self, roll_json(roll))

            if parts[2] == "close":
                with S.lock:
                    S.rolls.pop(roll.id, None)
                S.cache_drop(f"{roll.id}:")
                return _json(self, {"ok": True})
        return _json(self, {"error": "not found"}, 404)


def _line_traces(roll) -> tuple[np.ndarray, np.ndarray]:
    """The two per-line scalars the framing cascade needs, read in chunks.

    The old redetect materialised the whole calibrated strip
    (``np.asarray(strip[:])``) — 1.5 GB on a 31k-line roll — where
    ``open_capture`` had always chunked at 4096 lines for the same data. This
    keeps the chunking and returns 0.5 MB.
    """
    strip = roll.attach()
    n = int(roll.lines)
    trace = np.empty(n, dtype=np.float64)
    green = np.empty(n, dtype=np.float64)
    CH = 4096
    for a0 in range(0, n, CH):
        b0 = min(n, a0 + CH)
        blk = dec.apply_unit_calibration(
            np.asarray(strip[a0:b0]), roll._dark, roll._gain)
        trace[a0:b0] = blk.mean(axis=(1, 2))
        green[a0:b0] = blk[:, :, 1].mean(axis=1)
        del blk
    return trace, green


APPLY_KEYS_DEFAULT = ["density", "red", "green", "blue"]


def apply_to_roll(roll, body: dict) -> dict:
    """Copy one frame's corrections onto every other frame.

    This is the most destructive control in the application: one click
    replaces the colour of an entire roll, and before this change it did so
    with no confirmation and no way back. Someone who had graded thirty frames
    by hand and then clicked it lost all thirty.

    Two things now stand between the click and the loss.

    First, it will not act without ``confirm``. Asked without it, it returns a
    ``needs_confirm`` payload that *names what will be lost* — how many frames
    change, and specifically which frames already carry hand adjustments that
    this would overwrite. A count of frames is not enough; "12 frames, 5 of
    them already adjusted" is the sentence that makes someone stop.

    Second, the prior state is snapshotted first, so the answer to "I clicked
    it anyway" is one undo rather than an evening's work.
    """
    src_i = int(body.get("from", 0))
    if not (0 <= src_i < len(roll.frames)):
        return {"error": f"no frame {src_i}"}
    src = roll.frames[src_i]
    keys = list(body.get("keys") or APPLY_KEYS_DEFAULT)
    base = pr.merged_params(src.params)
    values = {k: base[k] for k in keys if k in base}

    targets = [f for f in roll.frames if f.index != src.index]
    # "Would change" means the value actually differs. Repeating an apply
    # should not claim to overwrite anything.
    changing, overwriting = [], []
    for f in targets:
        cur = pr.merged_params(f.params)
        if any(cur.get(k) != v for k, v in values.items()):
            changing.append(f.index)
            if pr.is_adjusted(f.params):
                overwriting.append(f.index)

    if not body.get("confirm"):
        return {
            "needs_confirm": True,
            "op": "apply-to-roll",
            "from": src.index,
            "keys": keys,
            "values": values,
            "summary": pr.describe_params(src.params),
            "frames_total": len(roll.frames),
            "frames_changing": changing,
            "frames_overwriting_adjustments": overwriting,
            "undoable": True,
            "message": (
                f"Apply frame {src.index + 1}'s "
                f"{', '.join(keys)} to {len(changing)} other "
                f"{'frame' if len(changing) == 1 else 'frames'}"
                + (f", replacing hand adjustments on "
                   f"{len(overwriting)} of them "
                   f"({', '.join(str(i + 1) for i in overwriting[:8])}"
                   f"{'…' if len(overwriting) > 8 else ''})"
                   if overwriting else "")
                + ". This can be undone."),
            "roll": roll_json(roll),
        }

    S.snapshot(roll, f"apply frame {src.index + 1} to roll")
    for f in targets:
        f.params = pr.merged_params({**(f.params or {}), **values})
        S.cache_drop(f"{roll.id}:{f.index}:")
    save_sidecar(roll)
    out = roll_json(roll)
    out["applied"] = {"from": src.index, "keys": keys,
                      "frames_changed": len(changing)}
    return out


def undo_roll(roll) -> dict:
    """Restore the frame state from before the last destructive edit."""
    snap = S.undo_pop(roll)
    if snap is None:
        return {"error": "nothing to undo", "undo": S.undo_state(roll.id)}
    by_index = {s["index"]: s for s in snap["frames"]}
    roll.frames = [pr.Frame(index=s["index"], a=s["a"], b=s["b"],
                            confidence=s.get("confidence", "good"),
                            params=copy.deepcopy(s.get("params") or {}),
                            exported=s.get("exported"),
                            phase=s.get("phase", ""),
                            framing_risk=int(s.get("framing_risk") or 0),
                            scan_warning=int(s.get("scan_warning") or 0))
                   for s in snap["frames"]]
    for k, f in enumerate(roll.frames):
        f.index = k
    del by_index
    S.cache_drop(f"{roll.id}:")
    save_sidecar(roll)
    out = roll_json(roll)
    out["undone"] = {"label": snap["label"], "at": snap["at"]}
    return out


def edit_boundary(roll, body: dict) -> dict:
    """Move / split / merge frame boundaries. The strip is continuous and the
    frames are found afterwards — review.html exposes that honestly, so the
    user has to be able to correct it."""
    op = body.get("op")
    frames = roll.frames
    # Boundary edits are creative work too, and redetect throws all of them
    # away at once. Snapshot first; the frame list is small.
    S.snapshot(roll, {"move": "move a boundary", "split": "split a frame",
                      "merge": "merge two frames",
                      "redetect": "re-detect all frames"}.get(op, f"{op}"))
    if op == "move":
        i = int(body["index"])          # boundary between i and i+1
        line = max(0, min(int(body["line"]), roll.lines))
        if 0 <= i < len(frames) - 1:
            lo = frames[i].a + 64
            hi = frames[i + 1].b - 64
            line = max(lo, min(line, hi))
            frames[i].b = line
            frames[i + 1].a = line
    elif op == "split":
        i = int(body["index"])
        line = int(body["line"])
        f = frames[i]
        if f.a + 64 < line < f.b - 64:
            new = pr.Frame(index=0, a=line, b=f.b)
            f.b = line
            frames.insert(i + 1, new)
    elif op == "merge":
        i = int(body["index"])          # merge i with i+1
        if 0 <= i < len(frames) - 1:
            frames[i].b = frames[i + 1].b
            frames.pop(i + 1)
    elif op == "redetect":
        # Same cascade the open path runs, so a redetect cannot disagree with
        # the original detection for reasons other than the parameters given.
        # An operator threshold can be passed here: the binarisation level is
        # INFERRED (Otsu; the vendor's rule is untraced, docs/56 §7.4), so it
        # is the one knob worth exposing when detection goes wrong.
        if "ones_threshold" in body:
            t = body.get("ones_threshold")
            roll.ones_threshold = None if t in (None, "") else float(t)
        # Parameters follow the film, not the list position. Frames are keyed
        # by their midpoint line, which survives a boundary shift; the old
        # code re-keyed by index, which is wrong exactly when redetect is
        # worth running -- when the frame count changed.
        keep = [((f.a + f.b) // 2, f.params) for f in frames if f.params]
        trace, green = _line_traces(roll)
        pr._frame_roll(roll, trace, green, roll.capture)
        for mid, params in keep:
            for f in roll.frames:
                if f.a <= mid < f.b:
                    f.params = params
                    break
        del trace, green
    for k, f in enumerate(roll.frames):
        f.index = k
    pr._flag_confidence(roll)
    S.cache_drop(f"{roll.id}:")
    save_sidecar(roll)
    return roll_json(roll)


def purge(body: dict) -> dict:
    """Delete workspace directories. Never touches sidecars or exports.

    This is the only delete in the application, and the quit path calls it
    with ``all``. What it must never be able to reach is calibration: those
    tables are per-unit, they exist nowhere else, and on this machine a
    re-read is not always available to replace them. Two things keep that
    true — the calibration store is a different tree entirely
    (``Application Support`` versus this ``Caches`` workspace) and
    ``calib_store`` has no delete path at all, being append-only with its
    saved images chmod 0444.

    Neither of those is checked here, so this checks it: every path is
    resolved and proven to sit under the workspace before anything is
    removed. A name that escapes is skipped and reported rather than
    deleted. The cost is a stat; the thing it makes impossible is
    unrecoverable.
    """
    ids = body.get("ids")
    caps = body.get("captures")
    if body.get("all"):
        ids = [d.name for d in WORKSPACE.glob("*") if d.is_dir()]
        # Captures are temp data too, and the quit dialog has always claimed
        # they were deleted. Now they are — but only the ones in the cache
        # tree, never the repository's own.
        caps = [p.name for p in CAPTURES.glob("*.bin")]
    freed = 0
    refused: list[str] = []
    root = WORKSPACE.resolve()
    for rid in ids or []:
        d = WORKSPACE / rid
        if not d.is_dir() or ".." in rid or "/" in rid or "\\" in rid:
            continue
        try:
            if d.resolve().parent != root:
                refused.append(rid)
                continue
        except OSError:
            refused.append(rid)
            continue
        freed += dir_size(d)
        with S.lock:
            S.rolls.pop(rid, None)
        S.cache_drop(f"{rid}:")
        shutil.rmtree(d, ignore_errors=True)

    # Captures, under the same proof as the workspace above and one more
    # besides. These are irreplaceable — the film passes the sensor once — so
    # deleting one is only ever allowed inside the temp captures directory,
    # and a resolved path that lands anywhere else is refused and reported
    # rather than removed. LEGACY_CAPTURES is the owner's own photographs and
    # is unreachable from here by construction.
    croot = CAPTURES.resolve()
    for name in caps or []:
        if ".." in name or "/" in name or "\\" in name:
            refused.append(name)
            continue
        p = CAPTURES / name
        if not p.is_file():
            continue
        try:
            if p.resolve().parent != croot:
                refused.append(name)
                continue
        except OSError:
            refused.append(name)
            continue
        # The capture and the sidecars that describe it go together: a
        # .scan.json describing a .bin that is gone is worse than neither.
        for q in sorted(CAPTURES.glob(f"{p.stem}.*")):
            try:
                if q.is_file() and q.resolve().parent == croot:
                    freed += q.stat().st_size
                    q.unlink()
            except OSError:
                pass
    out = {"freed": freed, "workspace": workspace_state()}
    if refused:
        out["refused"] = refused
    return out


def calibration_info() -> dict:
    p = _ROOT / "calibration" / "README.json"
    out = {"dir": str(p.parent), "present": p.is_file()}
    if p.is_file():
        try:
            out["readme"] = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            pass
    for n in ("dark_2000x3.npy", "gain_2000x3.npy"):
        f = p.parent / n
        out[n] = {"present": f.is_file(),
                  "bytes": f.stat().st_size if f.is_file() else 0}
    return out


# --------------------------------------------------------------------------
# scanner calibration -- the per-unit data that exists nowhere else
#
# The user should never have to know any of this. On first connect we read it
# once, back it up, and say plainly what was saved and where; after that we
# never read it again. The rules and the reasons are in
# docs/60-calibration-safety.md; the enforcement is in tools/calib_device.py.
#
# Two things this layer must get right:
#   * store state is answered from DISK ONLY. Asking "do we have calibration?"
#     must never cause USB traffic, because the answer is on disk and the
#     question is asked on every bootstrap.
#   * nothing here probes USB while a scan is running -- the scan child owns
#     the interface, exactly as hardware_state() already documents.
# --------------------------------------------------------------------------

def calibration_store_state() -> dict:
    """Disk only. Safe to call as often as the UI likes.

    docs/69 s7.1. Everything added here is a pure disk read, so the "must
    never cause USB traffic" property of this function is preserved -- and it
    is now enforced structurally rather than by discipline, because
    calib_resolve, calib_profile and calib_wizard.assess cannot import a
    transport at all.

    INVARIANT: resolution.device_read_performed and resolution.may_auto_read
    are False in every response this returns. If either is ever true,
    something has been wired wrongly.
    """
    if calib is None:
        return {"available": False,
                "reason": "calibration tools unavailable"}
    try:
        store = calib_store.CalibrationStore()
        sel = store.selection()
        out = {"available": True, "store": str(store.root),
               "have_calibration": store.has_calibration(),
               "selection": sel}
        if cres is not None:
            out["resolution"] = cres.resolve(store)
            out["units"] = store.unit_index()
        if cprof is not None:
            out["profile"] = cprof.profile(store).to_json()
        if cwiz is not None:
            # What would happen if the scanner were plugged in right now.
            # No device is reachable from assess(): it is a function of bytes
            # already on disk, and it decides nothing -- `automatic` is a
            # statement about whether a person would be asked anything, not
            # permission to start.
            out["setup"] = cwiz.assess(store)
        return out
    except Exception as e:                                  # noqa: BLE001
        return {"available": False, "reason": str(e)}


def calibration_run(jid: str, body: dict) -> dict:
    """Start the unattended calibration as a background job.

    A job, not a synchronous call: the searches take minutes and a blocking
    POST would freeze the window. Progress is polled through GET job/<id>,
    exactly like opening a capture or exporting a roll -- no new mechanism.

    THE GUARDS, IN ORDER, AND WHY EACH ONE IS HERE
    ----------------------------------------------
    1. ``SCAN.running()`` -- a calibration needs the USB interface to itself.
    2. ``foreign_scan()`` -- so does another process's scan.
    3. one calibration at a time -- two searches driving the same lamp would
       each measure the other's setting.
    4. already calibrated -- refuses unless the caller explicitly asks again.
       The existing set is kept regardless; nothing here deletes.

    What it does NOT guard is "is there film in the gate", because that is not
    a question this layer can answer and not a question a person should be
    asked. The wizard measures it -- see calib_wizard's docstring for why the
    film sensors and the gate classifier are not symmetric signals -- and comes
    back in the ``film-in-gate`` state, which is one sentence on screen and no
    control.
    """
    if calib is None or cwiz is None:
        return {"error": "calibration tools unavailable"}
    if SCAN.running():
        return {"error": "A scan is running. Calibration needs the USB "
                         "interface to itself; try again when it ends."}
    foreign = scan_marker_state()
    if foreign.get("stale") or foreign.get("running"):
        return {"error": "Another process is using the scanner."}
    with S.lock:
        busy = [j for j in S.jobs.values()
                if j.get("kind") == "calibration" and j.get("status") == "running"]
    if busy:
        return {"error": "A calibration is already running."}

    store = calib_store.CalibrationStore()
    setup = cwiz.assess(store)
    if setup["state"] == cwiz.READY and not body.get("force"):
        return {"error": "This scanner is already calibrated. Nothing was "
                         "sent to it."}
    if setup["state"] == cwiz.AMBIGUOUS:
        return {"error": "More than one scanner has been calibrated here. "
                         "Choose which one is plugged in first."}

    S.job_set(jid, kind="calibration", status="running", progress=0.0,
              phase=cwiz.STEP_GATE, message=cwiz.HEADLINES[cwiz.RUNNING],
              state=cwiz.RUNNING, steps=setup["steps"], cancellable=False)
    threading.Thread(target=job_calibrate, args=(jid, body), daemon=True).start()
    return {"id": jid, "state": cwiz.RUNNING}


def job_calibrate(jid: str, body: dict) -> None:
    """The worker. Every state it can end in is one the UI can render."""
    link = None
    try:
        store = calib_store.CalibrationStore()

        def prog(p) -> None:
            S.job_set(jid, phase=p.step, progress=float(p.fraction),
                      message=p.text, detail=p.detail, state=p.state,
                      measurements=list(p.measurements))
            for w in p.warnings:
                S.job_append(jid, "warnings", w)

        # The no-motion film-sense pre-check needs a Link of its own. If it
        # cannot be opened the calibration still proceeds: the probe capture
        # is a positive measurement of the same question, and refusing to
        # start because a pre-check was unavailable would be a prompt in front
        # of the case that is meant to be silent.
        try:
            link = scan.Link.open()
        except Exception as e:                              # noqa: BLE001
            S.job_append(jid, "warnings",
                         f"no film-sense pre-check ({e}); the first probe "
                         f"capture will settle whether the gate is empty")

        w = cwiz.Wizard(store, base=int(body.get("base") or cwiz.DEFAULT_BASE),
                        progress=prog)
        rep = w.run(link)
        S.job_set(jid, state=rep["state"], headline=rep["headline"],
                  serial=rep.get("serial"), report=rep,
                  measurements=rep.get("measurements") or [],
                  status="done" if rep["state"] == cwiz.DONE else "error",
                  progress=1.0 if rep["state"] == cwiz.DONE else 0.0,
                  phase="done", message=rep["headline"],
                  error=None if rep["state"] == cwiz.DONE else rep["headline"],
                  calibration=calibration_store_state())
    except Exception as e:                                  # noqa: BLE001
        S.job_set(jid, status="error", state=cwiz.FAILED if cwiz else "failed",
                  error=f"{e}", trace=traceback.format_exc()[-2000:])
    finally:
        if link is not None:
            try:
                link.close()
            except Exception:                               # noqa: BLE001
                pass


def _calib_parts():
    transport = calib_dev.UsbTransport()
    store = calib_store.CalibrationStore()
    guard = calib_dev.PowerCycleGuard(transport, store.root / "journal")
    return store, transport, guard


def calibration_state() -> dict:
    """Store state, plus -- only when it could matter and only when the USB
    bus is free -- whether a first read is possible right now."""
    out = calibration_store_state()
    if not out.get("available"):
        return out
    out["scan_running"] = SCAN.running()
    # docs/69 s7.2. `have_calibration` is true when ANY scanner has been read,
    # so with two units stored the early-out below would return action "none"
    # and the UI would silently use whichever the selection happened to point
    # at. Guessing here means rendering someone's film through another
    # scanner's colour matrix and lamp calibration -- plausible-looking and
    # wrong. Choosing costs one click; being wrong costs every scan until
    # somebody notices. Still no USB touched.
    if (cres is not None and not out["scan_running"]
            and (out.get("resolution") or {}).get("state") == cres.AMBIGUOUS):
        out["action"] = "choose-unit"
        out["headline"] = (out["resolution"].get("headline")
                           or "Which scanner is plugged in?")
        return out
    if out.get("have_calibration") or out["scan_running"]:
        # Nothing to decide. Do not touch USB.
        out["action"] = "none" if out.get("have_calibration") else "busy"
        return out
    try:
        store, transport, guard = _calib_parts()
        out.update(calib.connect_report(store, transport, guard))
    except Exception as e:                                  # noqa: BLE001
        out["action"] = "unknown"
        out["error"] = str(e)
    return out


def calibration_read(_body: dict) -> dict:
    """Deliberate, user-initiated. Refuses far more often than it proceeds."""
    if calib is None:
        return {"error": "calibration tools unavailable"}
    if SCAN.running():
        return {"error": "A scan is running. The calibration read needs the "
                         "USB interface to itself; try again when it ends."}
    try:
        store, transport, guard = _calib_parts()
        res = calib.do_read(store, transport, guard,
                            force=bool(_body.get("force")), source="app")
    except calib_dev.ReadRefused as e:
        return {"refused": True, "reason": str(e),
                "state": calibration_store_state()}
    except calib_dev.UnsafeToolState as e:
        return {"refused": True, "unsafe": True, "reason": str(e)}
    except Exception as e:                                  # noqa: BLE001
        return {"error": str(e)}
    rec = res["record"]
    return {"saved": True, "salvaged": res["salvaged"],
            "stamp": rec.stamp, "dir": str(rec.path),
            "summary": rec.summary(), "state": calibration_store_state()}


def calibration_select(body: dict) -> dict:
    """Use an earlier stored calibration. Selecting never deletes anything."""
    if calib is None:
        return {"error": "calibration tools unavailable"}
    store = calib_store.CalibrationStore()
    # docs/69 s7.3. A serial names a UNIT; a stamp names a READ. Never create a
    # unit by naming it -- an unknown serial is an error, not an instruction --
    # and selecting deletes nothing either way.
    if "serial" in body:
        srl = body.get("serial")
        if srl is not None and not store.has_calibration_for(int(srl)):
            return {"error": f"no good stored calibration for scanner {srl}"}
        store.select_unit(None if srl is None else int(srl))
        return calibration_store_state()
    stamp = body.get("stamp")
    try:
        if stamp:
            store.select(stamp)
        else:
            store.clear_selection()
    except KeyError:
        return {"error": f"no stored calibration named {stamp}"}
    return calibration_store_state()


def diagnostics() -> dict:
    """Capture integrity and pipeline facts. Technical output lives here, not
    among the photographs (design/index.html)."""
    rolls = []
    for r in S.fresh_rolls():
        rolls.append({
            "id": r.id, "name": r.name, "capture": r.capture,
            "lines": r.lines, "frames": len(r.frames), "sync": r.sync,
            "auto_offsets": [round(v, 2) for v in r.auto_offsets],
            "roll_scale": [round(v, 4) for v in r.roll_scale],
            "ir": getattr(r, "ir", {}),
        })
    try:
        gate_desc = pgate.Gate.from_calibration().describe()
    except Exception as e:                                  # noqa: BLE001
        gate_desc = {"error": str(e)}
    # What the pipeline does with a capture that carries no speed at all: ask
    # the resolver, do not describe it from memory. See "transport_scale" below.
    ts_none, ts_none_src = dec.resolve_transport_scale()
    return {
        "rolls": rolls,
        "calibration": calibration_info(),
        "hardware": hardware_state(),
        "gate": gate_desc,
        "pipeline": {
            "words_per_line": dec.WORDS_PER_LINE,
            "pixels_per_line": dec.PIXELS_PER_LINE,
            "raw14_max": dec.RAW14_MAX,
            "transport_scale": ts_none,
            # Both the number and the sentence are what resolve_transport_scale
            # itself returns for a capture it knows nothing about — nothing here
            # restates DEFAULT_TRANSPORT_SCALE or re-derives a scale, so this row
            # cannot drift away from the resolver the renderer actually uses.
            # (It said "legacy default speed 25802 → 1.0000" once, which read as
            # though 1.0 were derived from that speed. transport_scale(25802) is
            # 4.3607; the 1.0 is the sentinel for "speed unknown".)
            "transport_scale_note": (
                f"{ts_none_src} Worked example, same resolver: "
                f"{dec.resolve_transport_scale(motor_speed=dec.MOTOR_SPEED[8])[1]}"
            ),
            "rpd_per_density": pr.RPD_PER_DENSITY,
        },
        "verified": {
            "ui_matches_pipeline": "tools/pakon_render.py verify — byte-for-byte "
                                   "equal to pakon_decode.py strip on "
                                   "strip_cal.bin",
            "pipeline_matches_kodak": "NOT verified. The Ansel stage is a "
                                      "stand-in (SETSHIFTS_12_PORTED=False); "
                                      "owned by the colour task.",
            "gate_classifier": "tools/pakon_gate.py selftest — flags "
                               "captures/roll.bin, a real lamp failure, as "
                               "DARK 29.9 % in.",
            "scan_stops": "tools/pakon_scan.py selftest — the transport stop "
                          "reaches the machine on cancel, SIGTERM, SIGINT, "
                          "parent death, SIGKILL and after a crash.",
        },
        "cache_bytes": S.cache_bytes,
        "python": sys.version.split()[0],
    }


def watch_parent(poll: float = 1.0) -> None:
    """Die when the process that started us does.

    This is the other half of the interlock. Refusing to open the machine
    while another process owns it is correct but it is still two backends, and
    the second one exists at all only because the first was allowed to outlive
    its window: Electron force-quit leaves no signal, no ``finally`` and no
    ``will-quit``, and a backend spawned with ``stdio: pipe`` simply keeps
    running with its scan child still driving film.

    ``os.getppid()`` becomes 1 (or the launchd reaper) the moment that happens,
    which needs no cooperation from the dying parent. Opt-in via
    ``--watch-parent`` so that a backend started by hand from a terminal, and
    attached to with ``PAKON_BACKEND_PORT``, is not affected.

    ``SCAN.shutdown()`` before exiting, so the scan child's control pipe is
    closed and the transport stops rather than being orphaned one level down.
    """
    start = os.getppid()
    while True:
        time.sleep(poll)
        if os.getppid() != start:
            print(f"parent {start} is gone; stopping the scan and exiting",
                  file=sys.stderr, flush=True)
            try:
                SCAN.shutdown()
            finally:
                os._exit(0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8136)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--watch-parent", action="store_true",
                    help="exit when the process that started this one exits. "
                         "The Electron app passes it; a hand-started backend "
                         "should not.")
    a = ap.parse_args()

    # Before anything else: if a previous run died mid-scan, the transport may
    # still be turning. This costs nothing when no scanner is attached.
    stale = scan_startup_check()
    if stale.get("stale"):
        print(f"  RECOVERED a scan orphaned by a crash: {stale}")
    other = foreign_scan()
    if other:
        # Not fatal — the rest of the application works offline — but every
        # path that would touch USB is now closed, and saying so once at
        # startup beats discovering it from a refusal later.
        print(f"  NOTE: {foreign_scan_refusal(other)}")

    if a.watch_parent:
        threading.Thread(target=watch_parent, daemon=True).start()

    # Every way this process can end, the child gets its pipe closed and stops.
    atexit.register(SCAN.shutdown)

    def _bye(sig, _frm):
        SCAN.shutdown()
        raise SystemExit(0)
    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        try:
            signal.signal(s, _bye)
        except (ValueError, OSError):
            pass

    srv = ThreadingHTTPServer((a.host, a.port), H)
    print(f"pakon-app  http://{a.host}:{a.port}")
    print(f"  workspace {WORKSPACE}")
    print(f"  sidecars  {SIDECARS}")
    print(f"  pakon_ui  {'mounted' if _HAVE_UI else 'unavailable'}")
    print(f"  scanner   {hardware_state().get('state')}")
    sys.stdout.flush()
    try:
        srv.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        SCAN.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
