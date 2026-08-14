// Open capture — the manual escape hatch for a .bin that wasn't just scanned
// (recovering after a crash, reopening an old capture) — and the cleanup
// prompt for whatever a crashed session left behind.
import React, { useEffect, useState } from 'react';
import { Btn, Chip, Spinner } from './components';
import * as api from './api';

const FILM_PATHS = [
  ['ColNeg', 'Colour neg'],
  ['BnW', 'B&W'],
  ['POSITIVE', 'Positive', true],
  ['IMPORTED', 'Imported'],
];

export function OpenDialog({ open, onClose, onOpened, captures }) {
  const [path, setPath] = useState('');
  const [name, setName] = useState('');
  const [filmPath, setFilmPath] = useState('ColNeg');
  const [dx, setDx] = useState('');
  const [film, setFilm] = useState(null);
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const busy = job && job.status === 'running';

  useEffect(() => {
    if (!open) {
      setJob(null);
      setError(null);
    }
  }, [open]);

  useEffect(() => {
    if (!dx.trim()) return setFilm(null);
    let alive = true;
    api.lookupFilm(dx.trim()).then((f) => alive && setFilm(f.error ? null : f)).catch(() => alive && setFilm(null));
    return () => { alive = false; };
  }, [dx]);

  async function go() {
    setError(null);
    try {
      const { id } = await api.openCapture({
        path,
        name: name.trim() || undefined,
        film_path: filmPath,
        dx: dx.trim() || undefined,
      });
      const final = await api.pollJob(id, setJob, 300);
      if (final.status === 'error') {
        setError(final.error);
        setJob(null);
        return;
      }
      await onOpened(final.roll);
      onClose();
    } catch (e) {
      setError(String(e.message || e));
      setJob(null);
    }
  }

  if (!open) return null;

  return (
    <div className="scrim on" onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <div className="sheet">
        <div style={{ marginBottom: 14 }}>
          <span className="title">Open capture</span>
        </div>

        <div className="field" style={{ marginBottom: 12 }}>
          <span className="lbl">Capture</span>
          <div style={{ display: 'flex', gap: 6 }}>
            <input
              className="inp"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="/path/to/capture.bin"
              spellCheck={false}
            />
            <Btn
              variant="flat"
              onClick={async () => {
                const p = await window.pakon?.openCapture();
                if (p) {
                  setPath(p);
                  if (!name) setName(p.split('/').pop().replace(/\.bin$/, ''));
                }
              }}
            >
              Browse…
            </Btn>
          </div>
        </div>

        {captures?.length ? (
          <div className="rows" style={{ marginBottom: 12, maxHeight: 150, overflowY: 'auto' }}>
            {captures.map((c) => (
              <button
                key={c.path}
                type="button"
                className={path === c.path ? 'on' : ''}
                onClick={() => {
                  setPath(c.path);
                  if (!name) setName(c.saved_name || c.name.replace(/\.bin$/, ''));
                  if (c.recorded_dx) setDx(c.recorded_dx);
                  if (c.recorded_film_path) setFilmPath(c.recorded_film_path);
                }}
              >
                <span className="num" style={{ flex: 1, fontSize: 12 }}>{c.name}</span>
                {c.recorded_dx || c.recorded_film_path ? (
                  <Chip tone={c.dx_source === 'board' ? 'ok' : 'info'}>
                    {c.recorded_dx || c.recorded_film_path}
                    {c.dx_source === 'board' ? ' · read' : c.dx_source === 'typed' ? ' · typed' : ''}
                  </Chip>
                ) : c.dx_read ? (
                  <Chip tone="ok">{c.dx_read} · read</Chip>
                ) : null}
                {c.has_sidecar ? <Chip tone="info">{c.adjusted} saved</Chip> : null}
                <span className="num" style={{ fontSize: 11, color: 'var(--faint)' }}>{api.fmtBytes(c.bytes)}</span>
              </button>
            ))}
          </div>
        ) : null}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
          <div className="field">
            <span className="lbl">Roll name</span>
            <input className="inp" value={name} onChange={(e) => setName(e.target.value)} placeholder="2026-08-07 A" />
          </div>
          <div className="field">
            <span className="lbl">DX</span>
            <input className="inp" value={dx} onChange={(e) => setDx(e.target.value)} placeholder="78-13" spellCheck={false} />
          </div>
        </div>

        {dx.trim() ? (
          <div className="rows" style={{ marginBottom: 12, padding: '8px 11px', fontSize: 12 }}>
            {film ? (
              <>
                <b>{film.name}</b>
                <span style={{ color: 'var(--faint)' }}>
                  {' '}· {film.manufacturer} · {film.path}{film.iso ? ` · ISO ${film.iso}` : ''}
                </span>
              </>
            ) : (
              <span style={{ color: 'var(--danger-ink)' }}>No stock matches that DX.</span>
            )}
          </div>
        ) : (
          <div className="field" style={{ marginBottom: 12 }}>
            <span className="lbl">Film path</span>
            <div className="seg" role="radiogroup" aria-label="Film path">
              {FILM_PATHS.map(([id, label, disabled]) => (
                <button
                  key={id}
                  type="button"
                  role="radio"
                  aria-checked={filmPath === id}
                  className={filmPath === id ? 'on' : ''}
                  disabled={disabled || undefined}
                  onClick={() => !disabled && setFilmPath(id)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        )}

        {error ? (
          <div style={{ background: 'var(--danger-flat)', color: 'var(--danger-ink)', borderRadius: 'var(--r-sm)', padding: '9px 11px', marginBottom: 12, fontSize: 12 }}>
            {error}
          </div>
        ) : null}

        {busy ? (
          <div style={{ marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 5 }}>
              <Spinner>{job.phase}</Spinner>
            </div>
            <div className="bar warnfill">
              <i style={{ width: `${(job.progress || 0) * 100}%` }} />
            </div>
          </div>
        ) : null}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Btn variant="flat" disabled={busy} onClick={onClose}>Cancel</Btn>
          <Btn variant="primary" disabled={!path || busy || (!!dx.trim() && !film)} onClick={go}>
            {busy ? 'Opening…' : 'Open'}
          </Btn>
        </div>
      </div>
    </div>
  );
}

export function CleanupDialog({ state, onDone }) {
  const [sel, setSel] = useState(() => new Set(state.rolls.map((r) => r.id)));
  const [capSel, setCapSel] = useState(() => new Set());
  const [busy, setBusy] = useState(false);
  const captures = state.captures || [];
  const chosen = state.rolls.filter((r) => sel.has(r.id));
  const chosenCaps = captures.filter((c) => capSel.has(c.name));
  const bytes = chosen.reduce((a, r) => a + r.bytes, 0) + chosenCaps.reduce((a, c) => a + c.bytes, 0);

  const toggle = (set, put, key) => {
    const n = new Set(set);
    if (n.has(key)) n.delete(key);
    else n.add(key);
    put(n);
  };

  return (
    <div className="scrim on">
      <div className="sheet">
        <div style={{ marginBottom: 14 }}>
          <span className="title">Scans from a previous session</span>
        </div>

        {state.rolls.length ? (
          <>
            <span className="lbl">Render cache</span>
            <div className="rows" style={{ margin: '4px 0 12px', maxHeight: 190, overflowY: 'auto' }}>
              {state.rolls.map((r) => (
                <label key={r.id}>
                  <input type="checkbox" checked={sel.has(r.id)} onChange={() => toggle(sel, setSel, r.id)} />
                  <span style={{ flex: 1 }}>{r.name}</span>
                  {r.adjusted > r.exported ? (
                    <Chip tone="warn">{r.adjusted} adjusted, {r.exported} exported</Chip>
                  ) : null}
                  <span className="num" style={{ fontSize: 11, color: 'var(--faint)' }}>{api.fmtDate(r.mtime)}</span>
                  <span className="num" style={{ fontSize: 11, width: 72, textAlign: 'right' }}>{api.fmtBytes(r.bytes)}</span>
                </label>
              ))}
            </div>
          </>
        ) : null}

        {captures.length ? (
          <>
            <span className="lbl" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              Raw captures
              <Chip tone="warn">cannot be remade without rescanning</Chip>
            </span>
            <div className="rows" style={{ margin: '4px 0 12px', maxHeight: 190, overflowY: 'auto' }}>
              {captures.map((c) => (
                <label key={c.name}>
                  <input type="checkbox" checked={capSel.has(c.name)} onChange={() => toggle(capSel, setCapSel, c.name)} />
                  <span className="num" style={{ flex: 1, fontSize: 12 }}>{c.name}</span>
                  {c.adjusted > c.exported ? (
                    <Chip tone="warn">{c.adjusted} adjusted, {c.exported} exported</Chip>
                  ) : null}
                  <span className="num" style={{ fontSize: 11, color: 'var(--faint)' }}>{api.fmtDate(c.mtime)}</span>
                  <span className="num" style={{ fontSize: 11, width: 72, textAlign: 'right' }}>{api.fmtBytes(c.bytes)}</span>
                </label>
              ))}
            </div>
          </>
        ) : null}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Btn variant="flat" disabled={busy} onClick={onDone}>Keep everything</Btn>
          <Btn
            variant="primary"
            disabled={busy || !(chosen.length || chosenCaps.length)}
            onClick={async () => {
              setBusy(true);
              try {
                await api.purge({ ids: chosen.map((r) => r.id), captures: chosenCaps.map((c) => c.name) });
              } finally {
                setBusy(false);
                onDone();
              }
            }}
          >
            Delete {api.fmtBytes(bytes)}
          </Btn>
        </div>
      </div>
    </div>
  );
}
