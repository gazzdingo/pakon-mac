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
export const job = (id) => get(`/api/app/job/${id}`);
export const openCapture = (body) => post('/api/app/open', body);
export const setParams = (id, i, params) => post(`/api/app/roll/${id}/frame/${i}`, { params });
export const resetFrame = (id, i) => post(`/api/app/roll/${id}/frame/${i}`, { reset: true });
export const applyToRoll = (id, from, keys) =>
  post(`/api/app/roll/${id}/apply-to-roll`, { from, keys });
export const boundary = (id, body) => post(`/api/app/roll/${id}/boundary`, body);
export const renameRoll = (id, name) => post(`/api/app/roll/${id}/rename`, { name });
export const closeRoll = (id) => post(`/api/app/roll/${id}/close`, {});
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

export const fmtClock = (s) => {
  if (s == null) return '—';
  const t = Math.max(0, Math.floor(s));
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`;
};

/** CLEAR / FILM / DARK, and the tone each carries. DARK is not a warning —
 *  it is the state that stops the transport. */
export const GATE = {
  clear: { label: 'Clear', tone: 'ok', note: 'No film in the path' },
  film: { label: 'Film', tone: 'info', note: 'Film in the path, lit' },
  dark: { label: 'Dark', tone: 'bad', note: 'Lamp failed or path blocked' },
  unknown: { label: '—', tone: '', note: '' },
};

/** URL for one frame. `version` is the parameter hash, so changing a
 *  parameter changes the URL and the browser cache cannot serve a stale one. */
export function frameUrl(rollId, index, scale, version, maxEdge) {
  const q = new URLSearchParams({ scale, v: version || '0' });
  if (maxEdge) q.set('max', String(maxEdge));
  return `${BASE}/api/app/roll/${rollId}/frame/${index}?${q}`;
}

export const histUrl = (rollId, index) => `/api/app/roll/${rollId}/hist/${index}`;

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
