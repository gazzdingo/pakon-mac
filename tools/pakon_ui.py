#!/usr/bin/env python3
"""Pakon Scan — local scanning app backend (HTTP + UI).

Orchestrates existing tools; does not reimplement colour or USB protocols.

  Offline / demo: pick captures/*.bin → pakon_decode.py --color --icc → gallery
  Live (when hardware present): detect → (optional load/init via guarded tools)
                                → pakon_session.capture_ep86 → same decode path

    python3 tools/pakon_ui.py
    -> http://127.0.0.1:8135

    cd app && npm start          # Electron shell around the same backend

Decode writes only under captures/decoded/ (gitignored). Never touches
hardware unless you explicitly start a live capture while a loaded scanner
is present. CCD arming still requires removing tools/WRITES_LOCKED and
running init_ccd / pakon_load yourself or via the gated API actions.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
CAPDIR = ROOT / "captures"
DECODE_OUT = CAPDIR / "decoded" / "ui"
PORT = 8135

sys.path.insert(0, str(TOOLS))
import pakon_filmstock as film  # noqa: E402
import pakon_session as session  # noqa: E402

# Keep the quick raw preview helpers for "inspect wire" mode.
try:
    import numpy as np
except ImportError:
    sys.exit("numpy required:  pip install numpy")

LINE_WORDS = 6000
_cache: dict[str, tuple] = {}
_cache_lock = threading.Lock()
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


# ---------------------------------------------------------------- raw preview (unchanged math)

def load_lines(path):
    with _cache_lock:
        if path in _cache:
            return _cache[path]
    w = np.fromfile(path, dtype="<u2")
    m = np.flatnonzero(w & 1)
    d = np.diff(m)
    keep = d == LINE_WORDS
    starts = m[:-1][keep]
    idx = np.flatnonzero(keep)
    prev_bad = np.zeros(len(starts), bool)
    prev_bad[1:] = (idx[1:] - idx[:-1]) > 1
    L = w[starts[:, None] + np.arange(LINE_WORDS)]
    P = np.stack([L[:, k::3] for k in range(3)], -1).astype(np.float32)
    stats = {"markers": int(len(m)), "clean": int(len(starts)),
             "losses": int((~keep).sum()),
             "pct": round(100.0 * len(starts) / max(1, len(d)), 2)}
    with _cache_lock:
        _cache[path] = (P, prev_bad, stats)
    return _cache[path]


def phase_lock(P, prev_bad):
    sub = P[:, ::13, :]
    sub = sub - sub.mean(1, keepdims=True)
    n = len(P)
    phase = np.zeros(n, int)
    cur = 0
    prev = sub[0]
    for i in range(1, n):
        if prev_bad[i]:
            best_r, best_v = cur, -9e18
            for r in range(3):
                v = float((np.roll(sub[i], -r, axis=1) * prev).sum())
                if v > best_v:
                    best_v, best_r = v, r
            cur = best_r
        phase[i] = cur
        prev = np.roll(sub[i], -cur, axis=1)
    out = np.empty_like(P)
    for r in range(3):
        s = phase == r
        if s.any():
            out[s] = np.roll(P[s], -r, axis=2)
    return out, int((np.diff(phase) != 0).sum())


def render(P, a, b, opts):
    seg = P[a:b]
    if opts["shift"]:
        s = opts["shift"]
        seg = seg.copy()
        seg[:-s, :, 0] = seg[s:, :, 0]
    white = np.maximum(np.percentile(P, 99.5, axis=0), 1200)
    S = seg / white
    out = np.zeros(seg.shape, np.uint8)
    lo_p, hi_p = opts["lo"], opts["hi"]
    for k in range(3):
        c = S[:, :, k]
        lo, hi = np.percentile(c, lo_p), np.percentile(c, hi_p)
        t = np.clip((c - lo) / max(1e-6, hi - lo), 0, 1)
        if opts["invert"]:
            t = 1.0 - t
        g = opts["gamma"]
        if g != 1.0:
            t = t ** g
        out[:, :, k] = (255 * t).astype(np.uint8)
    rot = opts["rot"]
    if rot == 1:
        out = np.transpose(out, (1, 0, 2))[:, ::-1]
    elif rot == 2:
        out = out[::-1, ::-1]
    elif rot == 3:
        out = np.transpose(out, (1, 0, 2))[::-1]
    if opts["flipx"]:
        out = out[:, ::-1]
    if opts["flipy"]:
        out = out[::-1]
    step = max(1, opts["step"])
    return out[::step, ::step]


def to_png(arr):
    import struct
    import zlib
    h, w = arr.shape[0], arr.shape[1]
    rows = b"".join(bytes([0]) + arr[y].tobytes() for y in range(h))

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 4))
            + chunk(b"IEND", b""))


# ---------------------------------------------------------------- jobs / decode

def _job_set(jid: str, **kw):
    with _jobs_lock:
        j = _jobs.setdefault(jid, {"id": jid, "log": []})
        j.update(kw)


def _job_log(jid: str, line: str):
    with _jobs_lock:
        j = _jobs.setdefault(jid, {"id": jid, "log": []})
        j.setdefault("log", []).append(line)
        if len(j["log"]) > 400:
            j["log"] = j["log"][-400:]


def _job_get(jid: str) -> dict | None:
    with _jobs_lock:
        j = _jobs.get(jid)
        return dict(j) if j else None


def list_captures() -> list[str]:
    if not CAPDIR.is_dir():
        return []
    return sorted(p.name for p in CAPDIR.glob("*.bin"))


def list_prior_decodes() -> list[dict]:
    root = CAPDIR / "decoded"
    if not root.is_dir():
        return []
    out = []
    for d in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        products = []
        for name in ("strip_srgb.png", "strip_rpd.png", "strip_raw14.png",
                     "strip_ansel_rpd.png"):
            if (d / name).is_file():
                products.append(name)
        frames = sorted((d / "frames").glob("*_srgb.png")) if (d / "frames").is_dir() else []
        if not products and not frames:
            # also accept frame_XX.png from older runs
            frames = sorted(d.glob("frame_*.png"))
        out.append({
            "id": d.name,
            "path": str(d.relative_to(CAPDIR)),
            "products": products,
            "frames": len(frames),
            "mtime": int(d.stat().st_mtime),
        })
    return out[:40]


def film_lookup(dx: str | None) -> dict | None:
    if not dx:
        return None
    try:
        p1, p2 = film.parse_dx(dx)
        s = film.lookup(p1, p2)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e), "dx": dx}
    return {
        "dx": f"{s.dx_part1}" + (f"-{s.dx_part2}" if s.dx_part2 is not None else ""),
        "name": s.name,
        "manufacturer": s.manufacturer,
        "path": s.path,
        "iso": s.iso,
        "sba_override": s.sba_override,
    }


def run_decode_job(jid: str, opts: dict):
    """Spawn tools/pakon_decode.py strip … --color --icc (Ansel path)."""
    capture = Path(opts["file"])
    if not capture.is_file():
        capture = CAPDIR / os.path.basename(opts["file"])
    if not capture.is_file():
        _job_set(jid, status="error", error=f"capture not found: {opts['file']}")
        return

    out_dir = DECODE_OUT / f"{capture.stem}_{jid}"
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, str(TOOLS / "pakon_decode.py"), "strip",
        str(capture), str(out_dir),
        "--color", "--icc",
    ]
    if opts.get("frames", True):
        cmd.append("--frames")
    if opts.get("all"):
        cmd.append("--all")
    if opts.get("dx"):
        cmd.extend(["--dx", str(opts["dx"])])
    if opts.get("tone") and opts["tone"] != "none":
        cmd.extend(["--tone", str(opts["tone"])])
    if opts.get("balance"):
        cmd.append("--balance")
    if opts.get("max_lines"):
        cmd.extend(["--max-lines", str(int(opts["max_lines"]))])
    # defaults for --data-dir / --ansel-root live in pakon_decode.py

    _job_set(jid, status="running", phase="decode", cmd=cmd,
             out_dir=str(out_dir), capture=str(capture), started=time.time())
    _job_log(jid, " ".join(cmd))

    try:
        proc = subprocess.Popen(
            cmd, cwd=str(ROOT),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            _job_log(jid, line.rstrip())
        rc = proc.wait()
    except Exception as e:  # noqa: BLE001
        _job_set(jid, status="error", error=str(e))
        _job_log(jid, f"ERROR: {e}")
        return

    products = []
    for name in ("strip_srgb.png", "strip_ansel_rpd.png", "strip_rpd.png",
                 "strip_raw14.png", "strip_cc_srgb.png",
                 "strip_warm.png", "strip_cold.png", "strip_sepia.png"):
        if (out_dir / name).is_file():
            products.append(name)
    frames = []
    fdir = out_dir / "frames"
    if fdir.is_dir():
        for p in sorted(fdir.glob("*_srgb.png")):
            frames.append(f"frames/{p.name}")
        if not frames:
            for p in sorted(fdir.glob("*.png")):
                if "_" not in p.stem or p.stem.endswith("_srgb"):
                    frames.append(f"frames/{p.name}")

    if rc != 0:
        _job_set(jid, status="error", error=f"decode exited {rc}",
                 products=products, frames=frames, finished=time.time())
        return
    _job_set(jid, status="done", phase="done", products=products,
             frames=frames, finished=time.time(),
             film=film_lookup(opts.get("dx")))
    _job_log(jid, f"done → {out_dir}")


def run_capture_job(jid: str, opts: dict):
    st = session.probe_status()
    if st["mode"] != "live":
        _job_set(jid, status="error",
                 error=st["hint"] or "scanner not live")
        return
    seconds = float(opts.get("seconds", 3))
    name = opts.get("name") or f"live_{time.strftime('%Y%m%d_%H%M%S')}.bin"
    path = CAPDIR / os.path.basename(name)
    if not str(path).endswith(".bin"):
        path = path.with_suffix(".bin")

    _job_set(jid, status="running", phase="capture", capture=str(path),
             started=time.time())
    _job_log(jid, f"capturing EP 0x86 → {path} ({seconds}s)")
    _job_log(jid, "note: does not arm CCD/lamp/motor — use init_ccd first")

    def prog(p):
        if p.get("phase") == "capture":
            _job_set(jid, bytes=p.get("bytes", 0),
                     transfers=p.get("transfers", 0),
                     errors=p.get("errors", 0))

    try:
        stats = session.capture_ep86(path, seconds=seconds, progress=prog)
    except Exception as e:  # noqa: BLE001
        _job_set(jid, status="error", error=str(e))
        _job_log(jid, f"ERROR: {e}")
        return

    _job_log(jid, f"captured {stats['bytes']} bytes @ {stats['mib_s']} MiB/s")
    if not stats["bytes"]:
        _job_set(jid, status="error", error="no data on EP 0x86 — is acquire armed?")
        return

    # chain Ansel decode
    decode_opts = {
        "file": str(path),
        "dx": opts.get("dx"),
        "tone": opts.get("tone"),
        "frames": opts.get("frames", True),
        "all": opts.get("all", False),
        "balance": opts.get("balance", False),
    }
    _job_log(jid, "starting Ansel decode (--color --icc)…")
    run_decode_job(jid, decode_opts)


def ansel_paths_ok() -> dict:
    # Import defaults from decode module without running CLI
    sys.path.insert(0, str(TOOLS))
    import pakon_decode as dec  # noqa: E402
    data = Path(dec.DEFAULT_DATA_DIR)
    ansel = Path(dec.DEFAULT_ANSEL_ROOT)
    return {
        "data_dir": str(data),
        "data_dir_ok": data.is_dir(),
        "ansel_root": str(ansel),
        "ansel_root_ok": ansel.is_dir(),
    }


# ---------------------------------------------------------------- UI

PAGE = r"""<!doctype html>
<meta charset=utf-8>
<title>Pakon Scan</title>
<style>
:root{
  --bg:#12141a; --panel:#1a1e27; --ink:#e9ecf1; --dim:#8b93a1;
  --line:#2a3140; --accent:#c4a574; --good:#6fbf8a; --warn:#d4a15c;
  --bad:#d67b7b; --chip:#242a36;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:14px/1.45 "IBM Plex Sans",ui-sans-serif,system-ui,sans-serif}
header{display:flex;align-items:center;gap:16px;padding:12px 20px;
  border-bottom:1px solid var(--line);background:linear-gradient(180deg,#171b24,#12141a)}
.brand{font-family:"IBM Plex Serif",Georgia,serif;font-size:20px;letter-spacing:.02em}
.brand span{color:var(--accent)}
.badges{display:flex;gap:8px;flex-wrap:wrap;margin-left:auto}
.chip{background:var(--chip);border:1px solid var(--line);border-radius:999px;
  padding:4px 10px;font-size:11px;color:var(--dim)}
.chip.on{color:var(--good);border-color:#2f5a40}
.chip.warn{color:var(--warn);border-color:#5a4528}
.chip.off{color:var(--bad);border-color:#5a3030}
main{display:grid;grid-template-columns:320px 1fr;min-height:calc(100vh - 54px)}
aside{background:var(--panel);border-right:1px solid var(--line);padding:16px;
  overflow:auto}
section{padding:16px 20px;overflow:auto}
h2{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--dim);
  margin:18px 0 8px;font-weight:600}
h2:first-child{margin-top:0}
label{display:block;margin:10px 0 4px;font-size:12px;color:var(--dim)}
select,input[type=text],input[type=number]{width:100%;background:#12151c;color:var(--ink);
  border:1px solid var(--line);border-radius:6px;padding:8px 10px}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.row label{margin:0;color:var(--ink);font-size:12px}
button{background:var(--accent);color:#1a140c;border:0;border-radius:6px;
  padding:9px 12px;font-weight:650;cursor:pointer;width:100%;margin-top:8px}
button.secondary{background:#2a3140;color:var(--ink)}
button:disabled{opacity:.45;cursor:not-allowed}
button:hover:not(:disabled){filter:brightness(1.06)}
.hint{font-size:11px;color:var(--dim);margin-top:6px;line-height:1.4}
.film{background:#12151c;border:1px solid var(--line);border-radius:6px;
  padding:8px 10px;font-size:12px;min-height:52px;color:var(--dim)}
.log{background:#0e1015;border:1px solid var(--line);border-radius:8px;
  padding:10px 12px;font:12px/1.4 ui-monospace,Menlo,monospace;color:#b7c0cc;
  max-height:180px;overflow:auto;white-space:pre-wrap}
.gallery{display:flex;flex-wrap:wrap;gap:12px;margin-top:12px}
figure{margin:0;background:var(--panel);border:1px solid var(--line);
  border-radius:8px;padding:8px;width:min(100%,320px)}
figure.wide{width:100%}
figure img{display:block;width:100%;border-radius:4px;background:#000}
figcaption{font-size:11px;color:var(--dim);margin-top:6px}
.tabs{display:flex;gap:6px;margin-bottom:12px}
.tab{flex:0;padding:6px 12px;border-radius:999px;border:1px solid var(--line);
  background:transparent;color:var(--dim);cursor:pointer;width:auto;margin:0;font-weight:500}
.tab.active{background:var(--accent);color:#1a140c;border-color:transparent}
.panel{display:none}.panel.active{display:block}
a.dl{color:var(--accent);font-size:12px}
</style>
<header>
  <div class=brand>Pakon <span>Scan</span></div>
  <div class=badges>
    <span class=chip id=modeChip>…</span>
    <span class=chip id=lockChip>…</span>
    <span class=chip id=anselChip>…</span>
  </div>
</header>
<main>
<aside>
  <h2>Session</h2>
  <button class=secondary id=btnRefresh>Refresh scanner</button>
  <div class=hint id=statusHint>Checking USB…</div>

  <h2>Film</h2>
  <label>DX code</label>
  <input type=text id=dx placeholder="78-13  (optional)">
  <div class=film id=filmInfo>No DX — Ansel uses default ColNeg maps.</div>
  <label>Tone (B&amp;W / abstract)</label>
  <select id=tone>
    <option value=none>None</option>
    <option value=warm>Warm</option>
    <option value=cold>Cold</option>
    <option value=sepia>Sepia</option>
  </select>
  <div class=row style=margin-top:10px>
    <label><input type=checkbox id=frames checked> frames</label>
    <label><input type=checkbox id=all> --all products</label>
    <label><input type=checkbox id=balance> balance</label>
  </div>

  <h2>Source</h2>
  <div class=tabs>
    <button class="tab active" data-tab=offline>Offline</button>
    <button class=tab data-tab=live>Live capture</button>
    <button class=tab data-tab=wire>Wire preview</button>
  </div>

  <div class="panel active" id=panel-offline>
    <label>Capture (.bin)</label>
    <select id=file></select>
    <label>Or prior decode</label>
    <select id=prior><option value="">—</option></select>
    <button id=btnDecode>Decode with Ansel</button>
    <button class=secondary id=btnOpenPrior>Open prior decode</button>
    <div class=hint>Runs <code>pakon_decode.py strip … --color --icc</code> (map-selected SBA/Shasta/FUGC → sRGB).</div>
  </div>

  <div class=panel id=panel-live>
    <label>Capture seconds</label>
    <input type=number id=secs value=3 min=0.5 max=60 step=0.5>
    <button id=btnCapture>Capture EP 0x86 + decode</button>
    <div class=hint id=liveHint>Live path needs a loaded scanner and an armed CCD (init_ccd). Capture itself only reads EP 0x86.</div>
  </div>

  <div class=panel id=panel-wire>
    <label>Capture</label>
    <select id=wireFile></select>
    <label>Pitch / offset</label>
    <div class=row>
      <input type=number id=pitch value=1460 style=width:48%>
      <input type=number id=off value=1249 style=width:48%>
    </div>
    <button id=btnWire>Quick wire render</button>
    <div class=hint>Raw stretch preview — not Ansel colour.</div>
  </div>

  <h2>Export</h2>
  <div class=hint id=exportHint>Decode to populate export paths.</div>
  <button class=secondary id=btnReveal disabled>Copy output folder path</button>
</aside>
<section>
  <h2 style=margin-top:0>Progress</h2>
  <div class=log id=log>Ready.</div>
  <h2>Strip</h2>
  <div id=strip></div>
  <h2>Frames</h2>
  <div class=gallery id=frames></div>
</section>
</main>
<script>
const $=id=>document.getElementById(id);
let status=null, jobId=null, outDir=null, pollTimer=null;

document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));
  t.classList.add('active');
  $('panel-'+t.dataset.tab).classList.add('active');
});

async function api(path, opts){
  const r=await fetch(path, opts);
  const t=r.headers.get('content-type')||'';
  if(t.includes('json')) return r.json();
  return r.text();
}

function setChip(el, text, cls){
  el.textContent=text; el.className='chip '+cls;
}

async function refreshStatus(){
  status=await api('/api/status');
  const m=status.mode||'offline';
  setChip($('modeChip'),
    m==='live'?'Scanner loaded':m==='needs_load'?'Needs firmware':'Offline / demo',
    m==='live'?'on':m==='needs_load'?'warn':'off');
  setChip($('lockChip'),
    status.writes_locked?'Writes locked':'Writes unlocked',
    status.writes_locked?'warn':'on');
  const a=status.ansel||{};
  setChip($('anselChip'),
    (a.ansel_root_ok&&a.data_dir_ok)?'Ansel data OK':'Ansel data missing',
    (a.ansel_root_ok&&a.data_dir_ok)?'on':'off');
  $('statusHint').textContent=status.hint||'';
  $('liveHint').textContent=status.hint||$('liveHint').textContent;
  $('btnCapture').disabled = m!=='live';
}

async function refreshFiles(){
  const f=await api('/api/files');
  const opts=f.map(x=>`<option value="${x}">${x}</option>`).join('');
  $('file').innerHTML=opts;
  $('wireFile').innerHTML=opts;
  const prior=await api('/api/decodes');
  $('prior').innerHTML='<option value="">—</option>'+prior.map(d=>
    `<option value="${d.path}">${d.id} · ${d.frames||0} frames · ${d.products.join(', ')||'no srgb'}</option>`
  ).join('');
}

async function lookupFilm(){
  const dx=$('dx').value.trim();
  if(!dx){ $('filmInfo').textContent='No DX — Ansel uses default ColNeg maps.'; return; }
  const s=await api('/api/film?dx='+encodeURIComponent(dx));
  if(s.error){ $('filmInfo').textContent='DX error: '+s.error; return; }
  $('filmInfo').innerHTML=`<b style=color:var(--ink)>${s.name}</b><br>${s.manufacturer} · path ${s.path}`+
    (s.iso!=null?` · ISO ${s.iso}`:'')+(s.sba_override?` · SBA ${s.sba_override}`:'');
}
$('dx').addEventListener('change',lookupFilm);
$('dx').addEventListener('keyup',e=>{ if(e.key==='Enter') lookupFilm(); });

function decodeBody(){
  return {
    file: $('file').value,
    dx: $('dx').value.trim()||null,
    tone: $('tone').value,
    frames: $('frames').checked,
    all: $('all').checked,
    balance: $('balance').checked,
  };
}

function showJob(j){
  $('log').textContent=(j.log||[]).join('\n') || j.error || j.status;
  $('log').scrollTop=$('log').scrollHeight;
  if(j.out_dir) outDir=j.out_dir;
  if(j.status==='done'){
    renderProducts(j);
    $('btnReveal').disabled=!outDir;
    $('exportHint').textContent=outDir?('Output: '+outDir):'';
  }
  if(j.status==='error'){
    $('exportHint').textContent=j.error||'Decode failed';
  }
}

function jobUrl(rel){
  return '/api/job/'+jobId+'/file?name='+encodeURIComponent(rel);
}

function renderProducts(j){
  const strip=$('strip'); const frames=$('frames');
  strip.innerHTML=''; frames.innerHTML='';
  const prefer=['strip_srgb.png','strip_ansel_rpd.png','strip_rpd.png','strip_raw14.png'];
  const hit=(j.products||[]).find(p=>prefer.includes(p)) || (j.products||[])[0];
  if(hit){
    strip.innerHTML=`<figure class=wide><img src="${jobUrl(hit)}"><figcaption>${hit}</figcaption></figure>`;
  }
  const list=j.frames||[];
  frames.innerHTML=list.map((f,i)=>
    `<figure><img src="${jobUrl(f)}" loading=lazy><figcaption>${f}</figcaption></figure>`
  ).join('') || '<div class=hint>No frame files — try enabling frames.</div>';
}

async function poll(){
  if(!jobId) return;
  const j=await api('/api/job/'+jobId);
  showJob(j);
  if(j.status==='running'){ pollTimer=setTimeout(poll, 700); }
  else { pollTimer=null; }
}

async function startDecode(){
  if(pollTimer) clearTimeout(pollTimer);
  $('log').textContent='Starting Ansel decode…';
  $('strip').innerHTML=''; $('frames').innerHTML='';
  const j=await api('/api/decode',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(decodeBody())});
  jobId=j.id; outDir=null; poll();
}

async function startCapture(){
  if(pollTimer) clearTimeout(pollTimer);
  $('log').textContent='Starting live capture…';
  const body={...decodeBody(), seconds:+$('secs').value};
  delete body.file;
  const j=await api('/api/capture',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(body)});
  jobId=j.id; poll();
}

async function openPrior(){
  const path=$('prior').value; if(!path) return;
  const j=await api('/api/open_decode',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({path})});
  jobId=j.id; showJob(await api('/api/job/'+jobId));
}

async function wireRender(){
  const p=new URLSearchParams({
    file:$('wireFile').value,pitch:$('pitch').value,off:$('off').value,
    count:4,rot:0,flipx:0,flipy:0,invert:1,lo:1,hi:99,gamma:1,shift:3,step:3});
  $('frames').innerHTML='';
  for(let i=0;i<4;i++){
    $('frames').innerHTML+=`<figure><img src="/frame?${p}&i=${i}"><figcaption>wire frame ${i}</figcaption></figure>`;
  }
  $('strip').innerHTML='<div class=hint>Wire preview (not Ansel).</div>';
}

$('btnRefresh').onclick=refreshStatus;
$('btnDecode').onclick=startDecode;
$('btnCapture').onclick=startCapture;
$('btnOpenPrior').onclick=openPrior;
$('btnWire').onclick=wireRender;
$('btnReveal').onclick=async()=>{
  if(!outDir) return;
  await navigator.clipboard.writeText(outDir);
  $('exportHint').textContent='Copied: '+outDir;
};

refreshStatus(); refreshFiles();
</script>
"""


# Fix accidental CSS typo from draft - I left broken CSS in :root. Let me fix in the write.
# Actually I need to fix the PAGE string - I had a typo with `--bad:#d pen`. I'll fix via search_replace after write.

def _json(handler, obj, code=200):
    body = json.dumps(obj).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _bin(handler, body: bytes, ctype: str, code=200):
    handler.send_response(code)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler) -> dict:
    n = int(handler.headers.get("Content-Length") or 0)
    raw = handler.rfile.read(n) if n else b"{}"
    try:
        return json.loads(raw.decode() or "{}")
    except json.JSONDecodeError:
        return {}


def _safe_job_file(jid: str, name: str) -> Path | None:
    j = _job_get(jid)
    if not j or not j.get("out_dir"):
        return None
    root = Path(j["out_dir"]).resolve()
    # allow opening prior decodes under captures/decoded
    target = (root / name).resolve()
    if not str(target).startswith(str(root) + os.sep) and target != root:
        return None
    if not target.is_file():
        return None
    return target


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        path = u.path

        if path == "/":
            return _bin(self, PAGE.encode(), "text/html; charset=utf-8")

        if path == "/api/status":
            st = session.probe_status()
            st["ansel"] = ansel_paths_ok()
            st["captures_dir"] = str(CAPDIR)
            return _json(self, st)

        if path == "/api/files":
            return _json(self, list_captures())

        if path == "/api/decodes":
            return _json(self, list_prior_decodes())

        if path == "/api/film":
            dx = (q.get("dx") or [""])[0]
            info = film_lookup(dx)
            return _json(self, info or {"error": "missing dx"})

        if path.startswith("/api/job/") and path.endswith("/file"):
            # /api/job/<id>/file?name=
            parts = path.strip("/").split("/")
            if len(parts) >= 3:
                jid = parts[2]
                name = unquote((q.get("name") or [""])[0])
                fp = _safe_job_file(jid, name)
                if not fp:
                    return _json(self, {"error": "not found"}, 404)
                data = fp.read_bytes()
                ctype = "image/png" if fp.suffix.lower() == ".png" else "application/octet-stream"
                return _bin(self, data, ctype)
            return _json(self, {"error": "bad path"}, 400)

        if path.startswith("/api/job/"):
            jid = path.rsplit("/", 1)[-1]
            j = _job_get(jid)
            if not j:
                return _json(self, {"error": "unknown job"}, 404)
            return _json(self, j)

        # legacy wire preview
        if path in ("/files",):
            return _json(self, list_captures())
        if path in ("/meta", "/frame"):
            o = {
                "pitch": int((q.get("pitch") or ["1460"])[0]),
                "off": int((q.get("off") or ["1249"])[0]),
                "rot": int((q.get("rot") or ["0"])[0]),
                "flipx": (q.get("flipx") or ["0"])[0] == "1",
                "flipy": (q.get("flipy") or ["0"])[0] == "1",
                "invert": (q.get("invert") or ["1"])[0] == "1",
                "lo": float((q.get("lo") or ["1"])[0]),
                "hi": float((q.get("hi") or ["99"])[0]),
                "gamma": float((q.get("gamma") or ["1"])[0]),
                "shift": int((q.get("shift") or ["3"])[0]),
                "step": int((q.get("step") or ["3"])[0]),
                "file": (q.get("file") or [""])[0],
            }
            fpath = CAPDIR / os.path.basename(o["file"])
            if not fpath.is_file():
                return _json(self, {"error": "no such capture"}, 404)
            P, prev_bad, stats = load_lines(str(fpath))
            Pc, switches = phase_lock(P, prev_bad)
            if path == "/meta":
                return _json(self, {**stats, "switches": switches})
            i = int((q.get("i") or ["0"])[0])
            a = o["off"] + i * o["pitch"]
            b = a + o["pitch"]
            if b > len(Pc):
                return _bin(self, to_png(np.zeros((8, 8, 3), np.uint8)), "image/png")
            return _bin(self, to_png(render(Pc, a, b, o)), "image/png")

        return _bin(self, b"not found", "text/plain", 404)

    def do_POST(self):
        u = urlparse(self.path)
        body = _read_json(self)

        if u.path == "/api/decode":
            jid = uuid.uuid4().hex[:10]
            _job_set(jid, status="queued", phase="queued", log=[])
            threading.Thread(target=run_decode_job, args=(jid, body),
                             daemon=True).start()
            return _json(self, {"id": jid})

        if u.path == "/api/capture":
            jid = uuid.uuid4().hex[:10]
            _job_set(jid, status="queued", phase="queued", log=[])
            threading.Thread(target=run_capture_job, args=(jid, body),
                             daemon=True).start()
            return _json(self, {"id": jid})

        if u.path == "/api/open_decode":
            rel = body.get("path") or ""
            # path relative to captures/, e.g. decoded/ansel_v1
            root = (CAPDIR / rel).resolve()
            if not str(root).startswith(str(CAPDIR.resolve()) + os.sep):
                return _json(self, {"error": "path escapes captures/"}, 400)
            if not root.is_dir():
                return _json(self, {"error": "not a directory"}, 404)
            jid = uuid.uuid4().hex[:10]
            products = [p.name for p in root.iterdir()
                        if p.suffix.lower() == ".png" and p.name.startswith("strip_")]
            frames = []
            fdir = root / "frames"
            if fdir.is_dir():
                frames = [f"frames/{p.name}" for p in sorted(fdir.glob("*_srgb.png"))]
                if not frames:
                    frames = [f"frames/{p.name}" for p in sorted(fdir.glob("*.png"))
                              if p.name.endswith(".png") and p.stem.count("_") == 0]
            # older ansel_v1 layout: frame_00.png at root
            if not frames:
                frames = [p.name for p in sorted(root.glob("frame_*.png"))]
            prefer = ["strip_srgb.png", "strip_ansel_rpd.png", "strip_rpd.png",
                      "strip_raw14.png"]
            products = sorted(products,
                              key=lambda n: prefer.index(n) if n in prefer else 99)
            _job_set(jid, status="done", phase="done", out_dir=str(root),
                     products=products, frames=frames,
                     log=[f"opened {root}"])
            return _json(self, {"id": jid})

        return _json(self, {"error": "not found"}, 404)


def main():
    CAPDIR.mkdir(parents=True, exist_ok=True)
    DECODE_OUT.mkdir(parents=True, exist_ok=True)

    st = session.probe_status()
    ansel = ansel_paths_ok()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"Pakon Scan  →  http://127.0.0.1:{PORT}")
    print(f"  mode: {st['mode']}  writes_locked={st['writes_locked']}")
    print(f"  ansel: {'OK' if ansel['ansel_root_ok'] else 'MISSING'}  "
          f"colorcorr: {'OK' if ansel['data_dir_ok'] else 'MISSING'}")
    print(f"  hint: {st['hint']}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
