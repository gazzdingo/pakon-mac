#!/usr/bin/env python3
"""Local web UI for reviewing Pakon captures. No hardware required.

Decodes a raw EP 0x86 capture into frames and serves them in a browser, with
the decode parameters exposed as controls so they can be tuned by eye instead
of by re-running scripts. Everything it needs is already on disk.

    python3 tools/pakon_ui.py
    -> http://127.0.0.1:8135

WHY THIS EXISTS
---------------
The decode has a handful of parameters that were, until now, edited in a script
and re-run: frame pitch, phase offset, orientation, per-channel stretch. Several
evenings were lost to rendering a variant, looking at it, and changing one
number. This makes that loop immediate.

WHAT IT DOES NOT DO
-------------------
It does not talk to the scanner and it never writes to `captures/`. Read-only
over the raw files, PNGs rendered in memory. Nothing here can affect hardware.

DECODE, as established (docs/42, docs/45)
-----------------------------------------
  * 6000 words per line, u16 LE, bit 0 is the line-start flag
  * accept only markers exactly 6000 words apart
  * plane_k = line[k::3]   (per-pixel R,G,B interleave)
  * phase may only change where a non-6000 gap occurred
  * per-column flat field, per-frame stretch, invert
"""
from __future__ import annotations

import io
import json
import os
import struct
import sys
import threading
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

try:
    import numpy as np
except ImportError:
    sys.exit("numpy required:  pip install numpy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPDIR = os.path.join(ROOT, "captures")
PORT = 8135
LINE_WORDS = 6000
ACROSS = 2000

_cache: dict[str, tuple] = {}
_lock = threading.Lock()


# ---------------------------------------------------------------- decode

def load_lines(path):
    """Return (planes, prev_bad) for a raw capture. Cached — decoding is slow."""
    with _lock:
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
    with _lock:
        _cache[path] = (P, prev_bad, stats)
    return _cache[path]


def phase_lock(P, prev_bad):
    """Channel rotation may only change where the data actually jumped.

    Re-evaluating on every line produces false switches in low-contrast areas,
    which paint a hard band across an otherwise clean frame. See docs/45.
    """
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
    h, w = arr.shape[0], arr.shape[1]
    rows = b"".join(bytes([0]) + arr[y].tobytes() for y in range(h))

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 4))
            + chunk(b"IEND", b""))


# ---------------------------------------------------------------- server

PAGE = """<!doctype html><meta charset=utf-8><title>Pakon capture review</title>
<style>
:root{--bg:#14161a;--panel:#1c1f26;--ink:#e8eaed;--dim:#8b93a1;--line:#2a2f39;--accent:#d98b5f}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 ui-sans-serif,system-ui,-apple-system,sans-serif}
header{padding:14px 20px;border-bottom:1px solid var(--line);display:flex;gap:20px;align-items:baseline}
h1{font-size:15px;margin:0;font-weight:600;letter-spacing:.02em}
.stat{color:var(--dim);font-size:12px;font-variant-numeric:tabular-nums}
main{display:grid;grid-template-columns:280px 1fr;min-height:calc(100vh - 52px)}
aside{background:var(--panel);border-right:1px solid var(--line);padding:16px;overflow:auto}
section{padding:16px;overflow:auto}
label{display:block;margin:12px 0 4px;font-size:12px;color:var(--dim)}
select,input[type=range],input[type=number]{width:100%}
input[type=range]{accent-color:var(--accent)}
.row{display:flex;gap:8px;align-items:center}
.row input[type=number]{width:80px}
button{background:var(--accent);color:#14161a;border:0;border-radius:5px;padding:8px 12px;font-weight:600;cursor:pointer;margin-top:14px;width:100%}
button:hover{filter:brightness(1.08)}
.frames{display:flex;flex-wrap:wrap;gap:12px}
figure{margin:0;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:8px}
figure img{display:block;max-width:100%;border-radius:3px}
figcaption{font-size:11px;color:var(--dim);margin-top:6px;font-variant-numeric:tabular-nums}
.hint{font-size:11px;color:var(--dim);margin-top:4px}
.val{color:var(--ink);font-variant-numeric:tabular-nums}
</style>
<header>
  <h1>Pakon capture review</h1>
  <span class=stat id=stats>—</span>
</header>
<main>
<aside>
  <label>Capture</label>
  <select id=file></select>

  <label>Frame pitch <span class=val id=pitchv></span> lines</label>
  <input type=range id=pitch min=800 max=3200 step=10 value=1460>

  <label>Start offset <span class=val id=offv></span></label>
  <input type=range id=off min=0 max=4000 step=1 value=1249>

  <label>Frames to show</label>
  <input type=number id=count value=4 min=1 max=12>

  <label>Rotation</label>
  <select id=rot>
    <option value=0>0&deg;</option><option value=1>90&deg; CCW</option>
    <option value=2>180&deg;</option><option value=3>90&deg; CW</option>
  </select>

  <div class=row style=margin-top:10px>
    <label style=margin:0><input type=checkbox id=flipx> flip X</label>
    <label style=margin:0><input type=checkbox id=flipy> flip Y</label>
    <label style=margin:0><input type=checkbox id=invert checked> invert</label>
  </div>

  <label>Black / white point <span class=val id=lohiv></span></label>
  <div class=row>
    <input type=number id=lo value=1 min=0 max=20 step=0.5>
    <input type=number id=hi value=99 min=80 max=100 step=0.5>
  </div>

  <label>Gamma <span class=val id=gv></span></label>
  <input type=range id=gamma min=0.4 max=2 step=0.05 value=1>

  <label>Channel-0 line shift <span class=val id=shv></span></label>
  <input type=range id=shift min=0 max=8 step=1 value=3>
  <div class=hint>Trilinear CCD row separation. 3 was measured by correlation.</div>

  <label>Downsample</label>
  <input type=range id=step min=1 max=6 step=1 value=3>

  <button id=go>Render</button>
</aside>
<section><div class=frames id=out></div></section>
</main>
<script>
const $=id=>document.getElementById(id);
const sync=()=>{
  $('pitchv').textContent=$('pitch').value; $('offv').textContent=$('off').value;
  $('gv').textContent=(+$('gamma').value).toFixed(2); $('shv').textContent=$('shift').value;
  $('lohiv').textContent=$('lo').value+' / '+$('hi').value;
};
['pitch','off','gamma','shift','lo','hi'].forEach(k=>$(k).addEventListener('input',sync));
sync();

fetch('/files').then(r=>r.json()).then(f=>{
  $('file').innerHTML=f.map(x=>`<option>${x}</option>`).join('');
  if(f.length) render();
});

function render(){
  const p=new URLSearchParams({
    file:$('file').value,pitch:$('pitch').value,off:$('off').value,
    count:$('count').value,rot:$('rot').value,
    flipx:$('flipx').checked?1:0,flipy:$('flipy').checked?1:0,
    invert:$('invert').checked?1:0,lo:$('lo').value,hi:$('hi').value,
    gamma:$('gamma').value,shift:$('shift').value,step:$('step').value});
  $('out').innerHTML='<p style=color:#8b93a1>decoding…</p>';
  fetch('/meta?'+p).then(r=>r.json()).then(mt=>{
    $('stats').textContent=`${mt.clean.toLocaleString()} clean lines · ${mt.losses} losses · ${mt.pct}% intact · ${mt.switches} phase switches`;
    let h='';
    for(let i=0;i<+$('count').value;i++)
      h+=`<figure><img src="/frame?${p}&i=${i}"><figcaption>frame ${i}</figcaption></figure>`;
    $('out').innerHTML=h;
  });
}
$('go').onclick=render;
</script>
"""


def opts_from(q):
    g = lambda k, d: q.get(k, [d])[0]
    return {"pitch": int(g("pitch", 1460)), "off": int(g("off", 1249)),
            "rot": int(g("rot", 0)), "flipx": g("flipx", "0") == "1",
            "flipy": g("flipy", "0") == "1", "invert": g("invert", "1") == "1",
            "lo": float(g("lo", 1)), "hi": float(g("hi", 99)),
            "gamma": float(g("gamma", 1)), "shift": int(g("shift", 3)),
            "step": int(g("step", 3)), "file": g("file", "")}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype, code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/":
            return self._send(PAGE.encode(), "text/html; charset=utf-8")
        if u.path == "/files":
            f = sorted(x for x in os.listdir(CAPDIR) if x.endswith(".bin")) if os.path.isdir(CAPDIR) else []
            return self._send(json.dumps(f).encode(), "application/json")
        o = opts_from(q)
        path = os.path.join(CAPDIR, os.path.basename(o["file"]))
        if not os.path.isfile(path):
            return self._send(b'{"error":"no such capture"}', "application/json", 404)
        P, prev_bad, stats = load_lines(path)
        Pc, switches = phase_lock(P, prev_bad)
        if u.path == "/meta":
            return self._send(json.dumps({**stats, "switches": switches}).encode(),
                              "application/json")
        if u.path == "/frame":
            i = int(q.get("i", ["0"])[0])
            a = o["off"] + i * o["pitch"]
            b = a + o["pitch"]
            if b > len(Pc):
                return self._send(to_png(np.zeros((8, 8, 3), np.uint8)), "image/png")
            return self._send(to_png(render(Pc, a, b, o)), "image/png")
        self._send(b"not found", "text/plain", 404)


def main():
    if not os.path.isdir(CAPDIR):
        sys.exit(f"no captures directory at {CAPDIR}")
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"Pakon capture review  ->  http://127.0.0.1:{PORT}")
    print("read-only; never writes to captures/ and never touches hardware")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
