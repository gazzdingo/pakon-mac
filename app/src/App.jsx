import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Modal, Select, ListBoxItem, Spinner } from '@heroui/react';
import { Dot, Plain, StatusLine, TopBar, Working } from './components';
import Review from './Review';
import ExportScreen from './Export';
import { Calibration, Diagnostics, Scan } from './Info';
import * as api from './api';

const FILM_PATHS = [
  ['ColNeg', 'Colour negative (C-41)'],
  ['BnW', 'Black and white'],
  ['POSITIVE', 'Positive / slide (E-6)'],
  ['IMPORTED', 'Imported'],
];

/** Open-capture flow. A .bin carries no DX, and the decode path refuses to
 *  assume a stock, so the film choice is asked here rather than guessed. */
function OpenDialog({ open, onClose, onOpened, captures }) {
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
    api
      .lookupFilm(dx.trim())
      .then((f) => alive && setFilm(f.error ? null : f))
      .catch(() => alive && setFilm(null));
    return () => {
      alive = false;
    };
  }, [dx]);

  async function go() {
    setError(null);
    try {
      const { id } = await api.openCapture({
        path,
        name: name.trim() || undefined,
        film_path: dx.trim() ? undefined : filmPath,
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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,.72)' }}
      onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}
    >
      <div
        className="border w-[600px] max-w-[92vw] p-6"
        style={{ background: 'var(--plate)', borderColor: 'var(--rule)' }}
      >
        <div className="ledger text-[19px] mb-1">Open capture</div>
        <p className="text-[12px] mb-4" style={{ color: 'var(--mute)' }}>
          The capture stays where it is. A render cache is built in the temporary workspace; your
          adjustments are saved separately and survive it.
        </p>

        <label className="lbl block mb-1">Capture file</label>
        <div className="flex gap-2 mb-3">
          <input
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="/path/to/capture.bin"
            spellCheck={false}
            className="flex-1 px-2 py-[7px] text-[12px] num border outline-none"
            style={{ background: 'var(--void)', borderColor: 'var(--rule)', color: 'var(--ink)' }}
          />
          <Plain
            className="!w-auto px-4"
            onPress={async () => {
              const p = await window.pakon?.openCapture();
              if (p) {
                setPath(p);
                if (!name) setName(p.split('/').pop().replace(/\.bin$/, ''));
              }
            }}
          >
            Browse…
          </Plain>
        </div>

        {captures?.length ? (
          <div className="mb-3 max-h-[132px] overflow-y-auto border" style={{ borderColor: 'var(--rule)' }}>
            {captures.map((c) => (
              <button
                key={c.path}
                onClick={() => {
                  setPath(c.path);
                  if (!name) setName(c.saved_name || c.name.replace(/\.bin$/, ''));
                }}
                className="flex w-full justify-between items-baseline px-3 py-[6px] text-[12px] gate"
                style={{ background: path === c.path ? 'var(--plate2)' : 'transparent' }}
              >
                <span className="num">{c.name}</span>
                <span className="num text-[11px]" style={{ color: 'var(--mute)' }}>
                  {api.fmtBytes(c.bytes)} · ~{c.approx_lines.toLocaleString()} lines
                  {c.has_sidecar ? ` · ${c.adjusted} saved` : ''}
                </span>
              </button>
            ))}
          </div>
        ) : null}

        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label className="lbl block mb-1">Roll name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="2026-08-07 A"
              className="w-full px-2 py-[7px] text-[12px] border outline-none ledger"
              style={{ background: 'var(--void)', borderColor: 'var(--rule)', color: 'var(--ink)' }}
            />
          </div>
          <div>
            <label className="lbl block mb-1">DX code (optional)</label>
            <input
              value={dx}
              onChange={(e) => setDx(e.target.value)}
              placeholder="78-13"
              spellCheck={false}
              className="w-full px-2 py-[7px] text-[12px] num border outline-none"
              style={{ background: 'var(--void)', borderColor: 'var(--rule)', color: 'var(--ink)' }}
            />
          </div>
        </div>

        {dx.trim() ? (
          <div className="text-[12px] mb-3 px-3 py-2 border" style={{ borderColor: 'var(--rule)' }}>
            {film ? (
              <>
                <b className="ledger">{film.name}</b>{' '}
                <span style={{ color: 'var(--mute)' }}>
                  · {film.manufacturer} · path {film.path}
                  {film.iso ? ` · ISO ${film.iso}` : ''}
                </span>
              </>
            ) : (
              <span style={{ color: 'var(--mute)' }}>No stock matches that DX code.</span>
            )}
          </div>
        ) : (
          <div className="mb-3">
            <label className="lbl block mb-1">Film type</label>
            <div className="grid grid-cols-2 gap-[6px]">
              {FILM_PATHS.map(([id, label]) => (
                <button
                  key={id}
                  onClick={() => setFilmPath(id)}
                  className="border px-2 py-[7px] text-left text-[12px] gate"
                  style={{
                    borderColor: filmPath === id ? 'var(--ink)' : 'var(--rule)',
                    background: filmPath === id ? 'var(--plate2)' : 'transparent',
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            <p className="text-[11px] mt-2" style={{ color: 'var(--mute)' }}>
              A capture carries no DX code, so the film has to be stated. The decode path refuses to
              silently assume a colour-negative default.
            </p>
          </div>
        )}

        {error ? (
          <Alert.Root color="danger" className="rounded-none mb-3">
            <Alert.Content>
              <Alert.Description className="num text-[11px]">{error}</Alert.Description>
            </Alert.Content>
          </Alert.Root>
        ) : null}

        {busy ? (
          <div className="mb-3">
            <Working>
              {job.phase} — {job.message}
            </Working>
            <div className="h-[3px] mt-1" style={{ background: 'var(--rule)' }}>
              <div
                className="h-full gate"
                style={{ width: `${(job.progress || 0) * 100}%`, background: 'var(--filament)' }}
              />
            </div>
          </div>
        ) : null}

        <div className="flex gap-2 justify-end">
          <Plain className="!w-auto px-5" isDisabled={busy} onPress={onClose}>
            Cancel
          </Plain>
          <Plain className="!w-auto px-5" isDisabled={!path || busy} onPress={go}>
            {busy ? 'Opening…' : 'Open'}
          </Plain>
        </div>
      </div>
    </div>
  );
}

/** housekeeping.html state A — leftovers from a previous session. */
function CleanupDialog({ state, onDone }) {
  const [sel, setSel] = useState(() => new Set(state.rolls.map((r) => r.id)));
  const [busy, setBusy] = useState(false);
  const chosen = state.rolls.filter((r) => sel.has(r.id));
  const bytes = chosen.reduce((a, r) => a + r.bytes, 0);
  const atRisk = chosen.filter((r) => r.adjusted > r.exported);

  async function purge(ids) {
    setBusy(true);
    try {
      await api.purge({ ids });
    } finally {
      setBusy(false);
      onDone();
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,.72)' }}>
      <div className="border w-[680px] max-w-[92vw] p-6" style={{ background: 'var(--plate)', borderColor: 'var(--rule)' }}>
        <div className="ledger text-[19px] mb-1">Scans from a previous session are still here</div>
        <p className="text-[12px] mb-4" style={{ color: 'var(--mute)' }}>
          The app didn't get to clean up last time (it may have been force-quit). Keep the scans to
          carry on with them, or delete them now.
        </p>

        <div className="border mb-3 max-h-[280px] overflow-y-auto" style={{ borderColor: 'var(--rule)' }}>
          {state.rolls.map((r) => (
            <label
              key={r.id}
              className="flex items-center gap-3 px-3 py-[9px] border-b text-[12px]"
              style={{ borderColor: '#1c1c1c' }}
            >
              <input
                type="checkbox"
                checked={sel.has(r.id)}
                onChange={(e) => {
                  const n = new Set(sel);
                  e.target.checked ? n.add(r.id) : n.delete(r.id);
                  setSel(n);
                }}
              />
              <span className="ledger flex-1">{r.name}</span>
              {r.adjusted > r.exported ? (
                <span className="text-[11px] filament">
                  ▲ {r.adjusted} adjusted, {r.exported} exported
                </span>
              ) : null}
              <span className="num text-[11px]" style={{ color: 'var(--mute)' }}>
                {api.fmtDate(r.mtime)}
              </span>
              <span className="num text-[11px] w-[72px] text-right">{api.fmtBytes(r.bytes)}</span>
            </label>
          ))}
        </div>

        <div className="flex justify-between items-baseline text-[12px] mb-4">
          <span style={{ color: 'var(--mute)' }}>Selected</span>
          <b className="num">
            {chosen.length} roll{chosen.length === 1 ? '' : 's'} · {api.fmtBytes(bytes)}
          </b>
        </div>

        {atRisk.length ? (
          <Alert.Root color="warning" className="rounded-none mb-3">
            <Alert.Content>
              <Alert.Description className="text-[11px]">
                {atRisk.length} of these has adjustments that were never exported. The adjustments
                themselves are kept — they live outside the workspace and re-apply when you reopen
                the same capture. Deleting removes the bulk capture cache only.
              </Alert.Description>
            </Alert.Content>
          </Alert.Root>
        ) : null}

        <div className="flex gap-2 justify-end">
          <Plain className="!w-auto px-5" isDisabled={busy} onPress={onDone}>
            Keep everything
          </Plain>
          <Plain
            className="!w-auto px-5"
            isDisabled={busy || !chosen.length}
            onPress={() => purge(chosen.map((r) => r.id))}
          >
            Delete selected ({api.fmtBytes(bytes)})
          </Plain>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [ready, setReady] = useState(false);
  const [fatal, setFatal] = useState(null);
  const [mode, setMode] = useState('review');
  const [boot, setBoot] = useState(null);
  const [rolls, setRolls] = useState([]);
  const [roll, setRoll] = useState(null);
  const [openDlg, setOpenDlg] = useState(false);
  const [cleanup, setCleanup] = useState(null);

  const refreshRolls = useCallback(async (preferId) => {
    const rs = await api.rolls();
    setRolls(rs);
    const pick = rs.find((r) => r.id === preferId) || rs.find((r) => r.id === roll?.id) || rs[0];
    setRoll(pick || null);
    return pick;
  }, [roll?.id]);

  useEffect(() => {
    (async () => {
      try {
        await api.initApi();
        const b = await api.bootstrap();
        setBoot(b);
        // Rolls already live in the backend (a reattached session) belong on
        // screen immediately, not only after the next open.
        const rs = await api.rolls();
        setRolls(rs);
        if (rs.length) setRoll(rs[0]);
        setReady(true);
        // Only offer cleanup for workspace dirs that are not currently open.
        const stale = b.workspace.rolls.filter((r) => !rs.some((x) => x.id === r.id));
        if (stale.length) setCleanup({ ...b.workspace, rolls: stale });
      } catch (e) {
        setFatal(String(e.message || e));
      }
    })();
  }, []);

  if (fatal)
    return (
      <div className="h-full flex items-center justify-center p-10">
        <div className="max-w-[60ch]">
          <div className="ledger text-[20px] mb-2" style={{ color: 'var(--halt)' }}>
            Cannot reach the backend
          </div>
          <p className="num text-[12px]" style={{ color: 'var(--mute)' }}>
            {fatal}
          </p>
        </div>
      </div>
    );

  if (!ready)
    return (
      <div className="h-full flex items-center justify-center">
        <Working>Starting…</Working>
      </div>
    );

  const chips = (
    <>
      <span className="flex items-center gap-[6px] lbl">
        <Dot tone={boot?.vendor_data?.ansel_root_ok ? 'ok' : 'bad'} />
        Colour data
      </span>
      <span className="flex items-center gap-[6px] lbl">
        <Dot tone={boot?.calibration?.present ? 'ok' : 'bad'} />
        Calibration
      </span>
      <span className="flex items-center gap-[6px] lbl">
        <Dot tone="idle" />
        Workspace {api.fmtBytes(boot?.workspace?.total_bytes)}
      </span>
    </>
  );

  return (
    <div className="flex flex-col h-full">
      <TopBar mode={mode} setMode={setMode} roll={roll} chips={chips} />

      {mode === 'review' ? (
        <Review
          roll={roll}
          setRoll={(r) => {
            setRoll(r);
            setRolls((rs) => rs.map((x) => (x.id === r.id ? r : x)));
          }}
          rolls={rolls}
          onPickRoll={(id) => api.roll(id).then(setRoll)}
          onOpen={() => setOpenDlg(true)}
          onGoExport={() => setMode('export')}
        />
      ) : mode === 'export' ? (
        <ExportScreen roll={roll} setRoll={setRoll} onGoReview={() => setMode('review')} />
      ) : mode === 'diagnostics' ? (
        <Diagnostics />
      ) : mode === 'calibrate' ? (
        <Calibration />
      ) : (
        <Scan />
      )}

      <OpenDialog
        open={openDlg}
        onClose={() => setOpenDlg(false)}
        captures={boot?.captures}
        onOpened={async (id) => {
          await refreshRolls(id);
          setMode('review');
          api.bootstrap().then(setBoot).catch(() => {});
        }}
      />

      {cleanup ? (
        <CleanupDialog
          state={cleanup}
          onDone={() => {
            setCleanup(null);
            api.bootstrap().then(setBoot).catch(() => {});
          }}
        />
      ) : null}
    </div>
  );
}
