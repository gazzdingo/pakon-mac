// Thin client for tools/pakon_app.py. Everything is loopback HTTP; the
// renderer never holds a full-resolution buffer — it points <img> at a frame
// URL and the backend renders and encodes.

let BASE = 'http://127.0.0.1:8136';

export async function initApi() {
  if (window.pakon?.backendPort) {
    const port = await window.pakon.backendPort();
    if (port) BASE = `http://127.0.0.1:${port}`;
  }
  return BASE;
}

export const base = () => BASE;

async function req(path, opts = {}) {
  const r = await fetch(BASE + path, {
    ...opts,
    headers: opts.body ? { 'Content-Type': 'application/json' } : undefined,
  });
  const text = await r.text();
  let data;
  try {
    data = JSON.parse(text || '{}');
  } catch {
    throw new Error(`bad response from backend: ${text.slice(0, 200)}`);
  }
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

export const get = (p) => req(p);
export const post = (p, body) => req(p, { method: 'POST', body: JSON.stringify(body ?? {}) });

export const bootstrap = () => get('/api/app/bootstrap');
/** `fresh` is the user pressing Recheck: skip the backend's 3 s probe cache.
 *  It still refuses to probe while a scan owns the USB handle, and says so in
 *  `recheck_refused` rather than returning a stale answer silently. */
export const hardware = (fresh) => get(`/api/app/hardware${fresh ? '?fresh=1' : ''}`);
export const workspace = () => get('/api/app/workspace');
export const sessionState = () => get('/api/app/session');
export const rolls = () => get('/api/app/rolls');
export const roll = (id) => get(`/api/app/roll/${id}`);
export const diagnostics = () => get('/api/app/diagnostics');
/** The per-unit calibration store, and — only when there is nothing stored
 *  yet and no scan is running — whether a first read is possible now.
 *
 *  NEVER call this on boot or as part of hardware detection. The scanner's
 *  EEPROM answers correctly only on the first read after a power cycle, so
 *  the one good read of a cycle is a resource that can be spent. This
 *  endpoint does not spend it — `connect_report` is USB enumeration and FX2
 *  RAM only, no I2C — but the read it reports on does, and the rule is
 *  cheapest to keep at the call site. User-initiated only. */
export const calibration = () => get('/api/app/calibration');

/** Read this scanner's EEPROM. Once, ever, per scanner.
 *
 *  Deliberate and user-initiated. Never call from a poll, a health check, a
 *  reconnect handler or a bootstrap, and never default `force` true: on this
 *  hardware the second read of a power cycle returns corrupted bytes while
 *  still reporting success, so a retry destroys what the first read got. */
export const calibrationRead = (body) => post('/api/app/calibration/read', body || {});

/** Say which scanner is plugged in (`{serial}`), or which stored read to use
 *  (`{stamp}`). Selecting never deletes anything, and naming a serial that has
 *  never been read is an error rather than an instruction. */
export const calibrationSelect = (body) => post('/api/app/calibration/select', body || {});

/** Calibrate this scanner. Returns `{id}` for pollJob.
 *
 *  Safe to call without asking the user first, and meant to be: the whole
 *  point is that a new scanner sets itself up. The backend refuses if a scan
 *  is running, if another calibration is running, or if this scanner is
 *  already calibrated, so a duplicate call is a no-op rather than a hazard.
 *  It never asks whether film is loaded — it measures. If film is in the gate
 *  the job comes back in state `film-in-gate`, which is one sentence on
 *  screen and no control, and it can simply be called again once the person
 *  has taken the film out. */
export const calibrationRun = (body) => post('/api/app/calibration/run', body || {});

export const job = (id) => get(`/api/app/job/${id}`);
export const openCapture = (body) => post('/api/app/open', body);
export const setParams = (id, i, params) => post(`/api/app/roll/${id}/frame/${i}`, { params });
export const resetFrame = (id, i) => post(`/api/app/roll/${id}/frame/${i}`, { reset: true });
/** Copy one frame's corrections onto the whole roll. Two calls, never one.
 *
 *  Without `confirm` the backend does not act: it returns a `needs_confirm`
 *  payload naming what would be lost — how many frames change and which of
 *  them already carry hand adjustments. That payload is NOT a roll (the roll
 *  is nested under `.roll`), and treating it as one is what used to blank the
 *  window: `roll.frames.find(...)` on a payload with no `frames`.
 *
 *  So the plan is a distinct call with a distinct return, and applying is the
 *  second call with `confirm: true`. Undo is taken by the backend first. */
export const planApplyToRoll = (id, from, keys) =>
  post(`/api/app/roll/${id}/apply-to-roll`, { from, keys });
export const applyToRoll = (id, from, keys) =>
  post(`/api/app/roll/${id}/apply-to-roll`, { from, keys, confirm: true });
/** Undo the last destructive edit — apply-to-roll, a boundary move, a
 *  redetect, a frame reset. In-memory and per session; `roll.undo` says
 *  whether there is anything to undo and what it was. */
export const undoRoll = (id) => post(`/api/app/roll/${id}/undo`, {});
export const boundary = (id, body) => post(`/api/app/roll/${id}/boundary`, body);
export const renameRoll = (id, name) => post(`/api/app/roll/${id}/rename`, { name });
export const closeRoll = (id) => post(`/api/app/roll/${id}/close`, {});
/** What an export would write, before it writes anything. Read-only — it stats
 *  paths and renders nothing — so it is cheap enough to ask on every run.
 *
 *  Two collisions, reported separately because they need different words:
 *  `existing` is "files you already have would be replaced"; `duplicates` is
 *  "your naming template does not tell these frames apart, so they would
 *  overwrite each other" — 36 frames into one filename, which is invisible in
 *  the destination folder afterwards. `on_exist` is the answer:
 *  ask | skip | overwrite | unique.
 *
 *  The backend refuses on its own if `on_exist` is still `ask` and there is a
 *  collision, so forgetting to call this cannot overwrite anything. */
export const planExport = (body) => post('/api/app/export/plan', body);
export const exportRoll = (body) => post('/api/app/export', body);
export const purge = (body) => post('/api/app/workspace/purge', body);
export const lookupFilm = (dx) => post('/api/app/film', { dx });

/* ── the scanner ─────────────────────────────────────────────────────────
 * startScan hands off to a separate process that owns the USB handle, so
 * cancelScan closing its control pipe is what actually stops the transport.
 * stopScanner is the panic button and does not care what state anything is in.
 */
export const startScan = (body) => post('/api/app/scan', body);
export const cancelScan = (id) => post('/api/app/scan/cancel', { id });
export const stopScanner = () => post('/api/app/scan/stop', {});

/** Jog the film transport, for respooling or repositioning film by hand.
 *
 *  The backend runs tools/spin_motor.py as a subprocess — the stop packet goes
 *  out from that script's `finally:` block, so it is sent on a clean finish, on
 *  a USB error, and if the backend has to terminate it. Nothing here holds the
 *  motor on; the run length is the whole contract.
 *
 *  This resolves only when the transport has stopped, so the request is open
 *  for as long as the jog lasts. It rejects (HTTP 409) with the real reason
 *  when the backend refuses — a scan running here or in another process, no
 *  scanner, firmware still loading — and those words are the backend's, not a
 *  guess made in the renderer.
 *
 *  `seconds` is capped at 5 unless `long` is set, which raises it to 60. Both
 *  caps are re-applied server-side; this argument is a convenience, not a
 *  guarantee. */
export const jogMotor = ({ direction, seconds, long }) =>
  post('/api/app/motor', { direction, seconds, long: !!long });

export const fmtClock = (s) => {
  if (s == null) return '—';
  const t = Math.max(0, Math.floor(s));
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`;
};

/** CLEAR / FILM / DARK, and the tone each carries. DARK is not a warning —
 *  it is the state that stops the transport. */
/** How each calibration-setup state reads on screen. The copy is the
 *  backend's (`setup.headline` / the job's `headline`); this is only the tone
 *  and whether anything is expected of the person. Exactly one state expects
 *  anything, and what it expects is one sentence. */
export const SETUP = {
  ready: { label: 'Calibrated', tone: 'ok', asks: false },
  'needs-calibration': { label: 'Setting up', tone: 'info', asks: false },
  running: { label: 'Calibrating', tone: 'info', asks: false },
  'film-in-gate': { label: 'Film in the gate', tone: 'warn', asks: true },
  ambiguous: { label: 'Which scanner?', tone: 'warn', asks: true },
  unreachable: { label: 'Lamp cannot reach the target', tone: 'bad', asks: true },
  failed: { label: 'Stopped', tone: 'bad', asks: true },
  done: { label: 'Calibrated', tone: 'ok', asks: false },
};

export const GATE = {
  clear: { label: 'Clear', tone: 'ok', note: 'No film in the path' },
  film: { label: 'Film', tone: 'info', note: 'Film in the path, lit' },
  dark: { label: 'Dark', tone: 'bad', note: 'Lamp failed or path blocked' },
  unknown: { label: '—', tone: '', note: '' },
};

/** What the backend's `job.phase` means, for the scan screen's headline.
 *
 *  The child process (`pakon_scan.py run`) walks a real sequence —
 *  `starting -> connecting -> lamp -> sensor -> acquire -> transport ->
 *  scanning` — that mirrors the vendor's own light-board/CCD bring-up
 *  (docs/59, docs/55): lamp thresholds, lamp on at the dim open-gate duty, a
 *  real ~5 s settle (`LAMP_WARMUP_S`, hive-confirmed `WaitForLamp`), CCD
 *  geometry/AFE, then the transport. `scanning` is only reached once actual
 *  image data is flowing — see the `window` event in pakon_app.py's `_pump`.
 *
 *  Collapsed here to the three stages the real hardware visibly shows: the
 *  lamp warming up (dim), everything else that has to happen before film
 *  moves, and the scan itself (bright). An unrecognised or empty phase falls
 *  back to `scanning` rather than something alarming, since by far the most
 *  common way to see one is a job whose phase has not reported yet. */
export const SCAN_PHASE = {
  starting: { label: 'Starting', stage: 'init' },
  connecting: { label: 'Connecting', stage: 'init' },
  lamp: { label: 'Warming up lamp', stage: 'warmup' },
  sensor: { label: 'Initializing scan', stage: 'init' },
  acquire: { label: 'Initializing scan', stage: 'init' },
  transport: { label: 'Initializing scan', stage: 'init' },
  scanning: { label: 'Scanning', stage: 'scan' },
  cancelling: { label: 'Stopping…', stage: 'scan' },
};

export function scanPhaseInfo(phase) {
  return SCAN_PHASE[phase] || SCAN_PHASE.scanning;
}

/** Why the scanner cannot run right now, in the order a user would hit them.
 *  `fix: 'recheck'` means pressing Recheck can change the answer; `fix: null`
 *  means nothing this window offers will. One line, no further explanation —
 *  the reason itself is the whole message. */
export function blockedReason(hw, scanJob) {
  if (!hw) return { title: 'Checking…', fix: 'recheck' };
  if (scanJob?.status === 'running') return { title: 'Scanning', fix: null };
  if (hw.foreign_scan) return { title: 'Scanning elsewhere', fix: null };
  if (hw.state === 'unreachable') return { title: 'Backend not answering', fix: 'recheck' };
  if (!hw.present) return { title: 'No scanner found', fix: 'recheck' };
  if (hw.state === 'loading_firmware') return { title: 'Loading firmware…', fix: null };
  if (hw.state === 'needs_firmware') return { title: 'No firmware loaded', fix: 'recheck' };
  if (hw.writes_locked) return { title: 'Writes locked', fix: 'recheck' };
  if (!hw.calibration) return { title: 'No calibration', fix: null };
  if (hw.state !== 'ready') return { title: 'Not answering', fix: 'recheck' };
  return null;
}

/** URL for one frame. `version` is the parameter hash, so changing a
 *  parameter changes the URL and the browser cache cannot serve a stale one. */
export function frameUrl(rollId, index, scale, version, maxEdge) {
  const q = new URLSearchParams({ scale, v: version || '0' });
  if (maxEdge) q.set('max', String(maxEdge));
  return `${BASE}/api/app/roll/${rollId}/frame/${index}?${q}`;
}

export const histUrl = (rollId, index) => `/api/app/roll/${rollId}/hist/${index}`;

/** Why a frame image would not load.
 *
 *  An <img> onError carries no reason, so a failed render left the stage simply
 *  empty — indistinguishable from "not decoded yet" when what it actually meant
 *  was that the backend refused (FindDmin finding no film base, say). Silence
 *  there sent us hunting a UI bug that was server-side. Re-request the same URL
 *  so the server's own words reach the screen. */
export async function frameError(rollId, index, scale, version) {
  try {
    const r = await fetch(frameUrl(rollId, index, scale, version));
    if (r.ok) return 'The image loaded but the browser could not display it.';
    const body = (await r.text()).trim();
    try {
      const j = JSON.parse(body);
      if (j && j.error) return String(j.error);
    } catch { /* not JSON — fall through to the raw body */ }
    return body.slice(0, 500) || `The render service returned ${r.status}.`;
  } catch (e) {
    return String((e && e.message) || e);
  }
}

/** Poll a job to completion. */
export async function pollJob(id, onTick, intervalMs = 400) {
  for (;;) {
    const j = await job(id);
    onTick?.(j);
    if (j.status === 'done' || j.status === 'error') return j;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}

export const fmtBytes = (n) => {
  if (!n) return '0 B';
  const u = ['B', 'kB', 'MB', 'GB', 'TB'];
  const i = Math.min(u.length - 1, Math.floor(Math.log10(n) / 3));
  return `${(n / 1000 ** i).toFixed(i ? 1 : 0)} ${u[i]}`;
};

export const fmtDate = (ts) =>
  new Date(ts * 1000).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
