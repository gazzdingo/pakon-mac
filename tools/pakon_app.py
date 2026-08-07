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
import hashlib
import json
import os
import shutil
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
sys.path.insert(0, str(_TOOLS / "ansel"))

import numpy as np                      # noqa: E402
import pakon_render as pr               # noqa: E402
import pakon_decode as dec              # noqa: E402

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
CAPTURES = _ROOT / "captures"
WORKSPACE.mkdir(parents=True, exist_ok=True)
SIDECARS.mkdir(parents=True, exist_ok=True)


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
    for r in S.rolls.values():
        adj = [f.index + 1 for f in r.frames if pr.is_adjusted(f.params)]
        exp = sum(1 for f in r.frames if f.exported)
        adjusted += len(adj)
        exported += exp
        rolls.append({"id": r.id, "name": r.name, "adjusted": adj,
                      "exported": exp, "frames": len(r.frames)})
    return {
        "rolls": rolls,
        "adjusted_frames": adjusted,
        "exported_frames": exported,
        "workspace_bytes": dir_size(WORKSPACE),
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
    return {
        "path": str(WORKSPACE),
        "sidecars": str(SIDECARS),
        "rolls": entries,
        "total_bytes": sum(e["bytes"] for e in entries),
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
    """
    try:
        with open(path, "rb") as fh:
            buf = fh.read(8 * 1024 * 1024)
        w = np.frombuffer(buf[: (len(buf) // 2) * 2], dtype="<u2")
        m = np.flatnonzero(w & 1)
        if m.size < 4:
            return {"words_per_line": None, "channels": None, "has_ir": False}
        gaps = np.diff(m)
        modal = int(np.bincount(gaps).argmax())
    except (OSError, ValueError):
        return {"words_per_line": None, "channels": None, "has_ir": False}
    ch = {6000: 3, 8000: 4}.get(modal)
    return {
        "words_per_line": modal,
        "channels": ch,
        "has_ir": ch == 4,
        "decodable": modal == dec.WORDS_PER_LINE,
    }


def list_captures() -> list[dict]:
    out = []
    if CAPTURES.is_dir():
        for p in sorted(CAPTURES.glob("*.bin")):
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
            out.append(info)
    return out


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
            alt = CAPTURES / os.path.basename(path)
            if alt.is_file():
                src = alt
            else:
                raise FileNotFoundError(f"capture not found: {path}")

        ch = probe_channels(src)
        if ch.get("words_per_line") and not ch.get("decodable"):
            raise ValueError(
                f"line length {ch['words_per_line']} words "
                f"({ch.get('channels') or '?'}-channel). The decode path "
                f"handles {dec.WORDS_PER_LINE}-word 3-channel lines only.")

        roll_id = uuid.uuid4().hex[:8]

        def prog(phase, frac, msg):
            S.job_set(jid, phase=phase, progress=float(frac), message=msg)

        roll = pr.open_capture(
            src, WORKSPACE, roll_id,
            name=body.get("name"),
            dx=body.get("dx") or None,
            film_path=body.get("film_path") or None,
            sba_key=body.get("sba_key") or None,
            sba_default=bool(body.get("sba_default")),
            max_lines=int(body.get("max_lines") or 0),
            progress=prog,
        )
        roll.ir = ch
        restored = apply_sidecar(roll)
        (Path(roll.workspace) / "roll.json").write_text(
            json.dumps(roll.to_json(), indent=1))
        save_sidecar(roll)
        with S.lock:
            S.rolls[roll.id] = roll
        S.job_set(jid, status="done", progress=1.0, phase="done",
                  message=f"{len(roll.frames)} frames"
                          + (f", {restored} restored" if restored else ""),
                  roll=roll.id)
    except Exception as e:                                  # noqa: BLE001
        S.job_set(jid, status="error", error=f"{e}",
                  trace=traceback.format_exc()[-2000:])


def job_export(jid: str, body: dict) -> None:
    try:
        roll = S.rolls.get(body.get("roll"))
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
        results = []
        total = len(idxs)
        for k, i in enumerate(idxs):
            S.job_set(jid, progress=k / max(1, total), phase="rendering",
                      message=f"frame {i + 1} of {total}", current=i,
                      results=list(results))
            try:
                r = pr.export_frame(roll, i, dest, fmt=fmt, colour=colour,
                                    template=template)
                r["status"] = "written"
            except Exception as e:                          # noqa: BLE001
                r = {"frame": i, "status": "error", "error": str(e)}
            results.append(r)
        save_sidecar(roll)
        with S.lock:
            S.exports.extend(r for r in results if r.get("status") == "written")
        S.job_set(jid, status="done", progress=1.0, phase="done",
                  results=results, dest=str(dest),
                  message=f"{sum(1 for r in results if r.get('status') == 'written')}"
                          f" of {total} written")
    except Exception as e:                                  # noqa: BLE001
        S.job_set(jid, status="error", error=f"{e}",
                  trace=traceback.format_exc()[-2000:])


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
                "unavailable_controls": pr.UNAVAILABLE_CONTROLS,
                "calibration": calibration_info(),
                "vendor_data": {
                    "data_dir": pr.dec.DEFAULT_DATA_DIR,
                    "data_dir_ok": Path(pr.dec.DEFAULT_DATA_DIR).is_dir(),
                    "ansel_root": pr.dec.DEFAULT_ANSEL_ROOT,
                    "ansel_root_ok": Path(pr.dec.DEFAULT_ANSEL_ROOT).is_dir(),
                },
                "film_paths": ["ColNeg", "BnW", "POSITIVE", "IMPORTED"],
            })

        if route == "captures":
            return _json(self, list_captures())

        if route == "workspace":
            return _json(self, workspace_state())

        if route == "session":
            return _json(self, unexported_summary())

        if route == "rolls":
            return _json(self, [roll_json(r) for r in S.rolls.values()])

        if route == "diagnostics":
            return _json(self, diagnostics())

        if route.startswith("job/"):
            j = S.job_get(route[4:])
            return _json(self, j or {"error": "unknown job"},
                         200 if j else 404)

        parts = route.split("/")
        if parts[0] == "roll" and len(parts) >= 2:
            roll = S.rolls.get(parts[1])
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
        f = roll.frames[index]
        key = f"{roll.id}:{index}:{scale}:{max_edge}:{_pv(f.params)}"
        hit = S.cache_get(key)
        if hit is None:
            t0 = time.perf_counter()
            img = pr.render_frame(roll, index, None, scale=scale,
                                  max_edge=max_edge)
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

        if route == "export":
            jid = S.job_new("export")
            threading.Thread(target=job_export, args=(jid, body),
                             daemon=True).start()
            return _json(self, {"id": jid})

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

        parts = route.split("/")
        if parts[0] == "roll" and len(parts) >= 3:
            roll = S.rolls.get(parts[1])
            if roll is None:
                return _json(self, {"error": "unknown roll"}, 404)

            if parts[2] == "frame" and len(parts) >= 4:
                i = int(parts[3])
                f = roll.frames[i]
                if body.get("reset"):
                    f.params = {}
                else:
                    f.params = pr.merged_params({**(f.params or {}),
                                                 **(body.get("params") or {})})
                S.cache_drop(f"{roll.id}:{i}:")
                save_sidecar(roll)
                return _json(self, roll_json(roll))

            if parts[2] == "apply-to-roll":
                src = roll.frames[int(body.get("from", 0))]
                keys = body.get("keys") or ["density", "red", "green", "blue"]
                base = pr.merged_params(src.params)
                for f in roll.frames:
                    if f.index == src.index:
                        continue
                    f.params = pr.merged_params(
                        {**(f.params or {}), **{k: base[k] for k in keys}})
                    S.cache_drop(f"{roll.id}:{f.index}:")
                save_sidecar(roll)
                return _json(self, roll_json(roll))

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


def edit_boundary(roll, body: dict) -> dict:
    """Move / split / merge frame boundaries. The strip is continuous and the
    frames are found afterwards — review.html exposes that honestly, so the
    user has to be able to correct it."""
    op = body.get("op")
    frames = roll.frames
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
        strip = roll.attach()
        blk = dec.apply_unit_calibration(np.asarray(strip[:]),
                                         roll._dark, roll._gain)
        spans = dec.find_frames(blk)
        keep = {f.index: f.params for f in frames}
        roll.frames = [pr.Frame(index=k, a=int(a), b=int(b))
                       for k, (a, b) in enumerate(spans)]
        for f in roll.frames:
            f.params = keep.get(f.index, {})
        del blk
    for k, f in enumerate(roll.frames):
        f.index = k
    pr._flag_confidence(roll)
    S.cache_drop(f"{roll.id}:")
    save_sidecar(roll)
    return roll_json(roll)


def purge(body: dict) -> dict:
    """Delete workspace directories. Never touches sidecars or exports."""
    ids = body.get("ids")
    if body.get("all"):
        ids = [d.name for d in WORKSPACE.glob("*") if d.is_dir()]
    freed = 0
    for rid in ids or []:
        d = WORKSPACE / rid
        if not d.is_dir() or ".." in rid or "/" in rid:
            continue
        freed += dir_size(d)
        with S.lock:
            S.rolls.pop(rid, None)
        S.cache_drop(f"{rid}:")
        shutil.rmtree(d, ignore_errors=True)
    return {"freed": freed, "workspace": workspace_state()}


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


def diagnostics() -> dict:
    """Capture integrity and pipeline facts. Technical output lives here, not
    among the photographs (design/index.html)."""
    rolls = []
    for r in S.rolls.values():
        rolls.append({
            "id": r.id, "name": r.name, "capture": r.capture,
            "lines": r.lines, "frames": len(r.frames), "sync": r.sync,
            "auto_offsets": [round(v, 2) for v in r.auto_offsets],
            "roll_scale": [round(v, 4) for v in r.roll_scale],
            "ir": getattr(r, "ir", {}),
        })
    return {
        "rolls": rolls,
        "calibration": calibration_info(),
        "pipeline": {
            "words_per_line": dec.WORDS_PER_LINE,
            "pixels_per_line": dec.PIXELS_PER_LINE,
            "raw14_max": dec.RAW14_MAX,
            "transport_scale": dec.DEFAULT_TRANSPORT_SCALE,
            "rpd_per_density": pr.RPD_PER_DENSITY,
        },
        "verified": {
            "ui_matches_pipeline": "tools/pakon_render.py verify — byte-for-byte "
                                   "equal to pakon_decode.py strip on "
                                   "strip_cal.bin",
            "pipeline_matches_kodak": "NOT verified. The Ansel stage is a "
                                      "stand-in (SETSHIFTS_12_PORTED=False); "
                                      "owned by the colour task.",
        },
        "cache_bytes": S.cache_bytes,
        "python": sys.version.split()[0],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8136)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    srv = ThreadingHTTPServer((a.host, a.port), H)
    print(f"pakon-app  http://{a.host}:{a.port}")
    print(f"  workspace {WORKSPACE}")
    print(f"  sidecars  {SIDECARS}")
    print(f"  pakon_ui  {'mounted' if _HAVE_UI else 'unavailable'}")
    sys.stdout.flush()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
