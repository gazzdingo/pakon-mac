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
export const workspace = () => get('/api/app/workspace');
export const sessionState = () => get('/api/app/session');
export const rolls = () => get('/api/app/rolls');
export const roll = (id) => get(`/api/app/roll/${id}`);
export const diagnostics = () => get('/api/app/diagnostics');
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
