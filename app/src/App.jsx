// The Console — shell.
//
// Two bars across the top (mode, then the twin capture/export lanes), three
// columns under them, the roll along the floor. The screens swap the centre
// and the right rail; the furniture does not move.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Btn, Chip, Info, Spinner, TopBar, Lanes, useTheme } from './components';
import Review from './Review';
import Scan from './Scan';
import ExportScreen from './Export';
import { Calibration, Diagnostics } from './Info';
import * as api from './api';

const FILM_PATHS = [
  ['ColNeg', 'Colour neg'],
  ['BnW', 'B&W'],
  ['POSITIVE', 'Positive'],
  ['IMPORTED', 'Imported'],
];

/** Machine state, split honestly: what the app reads now, and what is not
 *  wired. Every "not wired" row names the register the standalone tool uses,
 *  so the row is a fact rather than a promise.
 *
 *  WHERE THE LAMP READINGS COME FROM, WHICH IS THE WHOLE POINT OF THIS RAIL.
 *  Only one process can hold the USB interface, and during a scan that is the
 *  scan process — so this window cannot probe, and `hardware_state` serves the
 *  probe it took before the scan began.
 *
 *  Rendering that cache as if it were current made this rail say
 *  `Lamp —`, `Lamp temperature —` and `Lamp health idle` *while the lamp was
 *  being polled once a second*, with the readings sitting in the scan job the
 *  same screen was already showing. "Idle" was flatly untrue at the one moment
 *  the monitoring mattered, and it is the same shape of untruth as a Cancel
 *  button that is enabled and does nothing.
 *
 *  So: while a scan runs these rows read from the scan's own poll, which is
 *  the freshest data in the system. Otherwise they read from the probe, and if
 *  that probe was served from cache the row says `cached` rather than dressing
 *  a stale number up as a live one. */
export function machineRows(boot, roll, hw, scanJob) {
  const cal = boot?.calibration;
  const sync = roll?.sync;
  const scanning = scanJob?.status === 'running';
  // The scan process is the authority whenever it is running.
  const lamp = (scanning ? scanJob?.lamp : hw?.lamp) || null;
  const gate = scanning ? scanJob?.window?.state : null;
  const present = hw?.present && hw?.state === 'ready';
  const stale = !scanning && hw?.cached;
  const age = stale ? ' · cached' : '';
  return {
    read: [
      [
        'Scanner USB',
        scanning
          ? 'held by the scan'
          : present
            ? `0f05:f135${age}`
            : hw?.state === 'needs_firmware'
              ? 'no firmware'
              : 'absent',
        scanning || present ? 'good' : hw?.present ? 'warn' : 'na',
        <>
          A scan runs in its own process and owns the handle for its duration, so
          this window can neither probe nor be the thing that fails to let go of
          it.
        </>,
      ],
      [
        'Lamp',
        lamp?.status_hex ? `${lamp.status_hex}${lamp.ok === false ? ' fault' : ''}` : '—',
        lamp?.ok === false ? 'bad' : lamp?.status_hex ? 'good' : 'na',
        <>
          Register <span className="num">0x83</span>. Fault bits{' '}
          <span className="num">5</span> and <span className="num">6</span> abort a scan.
          {scanning ? ' Read by the scan process, once a second.' : null}
        </>,
      ],
      [
        'Lamp temperature',
        lamp?.temp_lb_c != null ? `${lamp.temp_lb_c.toFixed(2)} °C` : '—',
        lamp?.temp_lb_c != null ? 'good' : 'na',
        <>
          Register <span className="num">0x88</span>, raw × <span className="num">0.0625</span>.
          The board self-regulates to <span className="num">40.0</span> °C with the host sending
          nothing.
        </>,
      ],
      [
        'Lamp health',
        scanning
          ? lamp?.ok === false
            ? 'FAULT'
            : `polled · ${lamp?.polls ?? 0}`
          : present
            ? 'polled during a scan'
            : 'idle',
        scanning ? (lamp?.ok === false ? 'bad' : 'good') : present ? 'good' : 'na',
        <>
          Once a second while the transport runs. The vendor does not do this —{' '}
          <span className="num">LAMP_WARNING</span> and <span className="num">LAMP_ERROR</span> are
          consumed but never produced anywhere in <span className="num">TLB.dll</span> — so this is
          better than parity, not catching up to it.
        </>,
      ],
      [
        'Transport',
        scanning
          ? `running · ${scanJob?.speed ?? hw?.calibration?.speed ?? ''}`
          : hw?.calibration?.speed
            ? `reg 0xA5 · ${hw.calibration.speed}`
            : 'reg 0xA5',
        scanning ? 'warn' : present ? 'good' : 'na',
        <>
          <span className="num">MotorSpeedPlus</span> for{' '}
          <span className="num">DpiBase16_35</span>, from the recovered hive. Stopped on every exit
          path, including a killed process.
        </>,
      ],
      [
        'Roll end',
        gate
          ? { clear: 'clear gate', film: 'film', dark: 'DARK' }[gate] || gate
          : present
            ? 'clear / film / dark'
            : 'needs the scanner',
        gate === 'dark' ? 'bad' : gate ? 'good' : present ? 'good' : 'na',
        <>
          Three states, not two. The last detector tested only "bright enough to be a clear gate", so
          a dead lamp read as film present. <b>Dark stops the motor.</b> Levels come from{' '}
          <span className="num">calibration/</span>, and the classifier is regression-tested against
          the capture where the lamp actually died.
        </>,
      ],
      [
        'Writes',
        hw?.writes_locked ? 'locked' : 'unlocked',
        hw?.writes_locked ? 'warn' : 'good',
        <>
          <span className="num">tools/WRITES_LOCKED</span>. While it exists no register write is
          sent, so no scan can start.
        </>,
      ],
      [
        'Calibration',
        cal?.present ? 'loaded' : 'missing',
        cal?.present ? 'good' : 'bad',
        <>
          Per-pixel dark and gain tables from <span className="num">calibration/</span>. Valid only
          for the exposure triad they were captured at.
        </>,
      ],
      ['Capture intact', sync ? `${sync.pct_clean} %` : '—', sync?.losses === 0 ? 'good' : sync ? 'warn' : ''],
      ['Sync losses', sync ? sync.losses : '—', sync?.losses === 0 ? 'good' : sync ? 'bad' : ''],
      ['Words per line', boot ? '6000 · 3 ch' : '—'],
      [
        'Infrared plane',
        roll?.ir?.has_ir ? 'captured' : 'not in capture',
        roll?.ir?.has_ir ? 'good' : 'na',
      ],
      [
        'Colour data',
        boot?.vendor_data?.ansel_root_ok ? 'found' : 'missing',
        boot?.vendor_data?.ansel_root_ok ? 'good' : 'bad',
      ],
      ['Workspace', api.fmtBytes(boot?.workspace?.total_bytes)],
    ],
    unwired: [
      [
        'Film in guides',
        'no register',
        'na',
        <>
          There is no such register. The vendor cached film presence host-side and the writer has
          never been found, so no sensor is shown rather than one invented. The gate classification
          above is the closest real answer.
        </>,
      ],
      [
        'DX barcode',
        'not read',
        'na',
        <>
          Read by a dedicated sensor board, not from the CCD image.{' '}
          <span className="num">tools/dx_decode.py</span> has never been validated against a real
          roll.
        </>,
      ],
      [
        'Serial',
        'never read',
        'na',
        <>
          The only serial anyone has — <span className="num">16275</span> — belongs to a different
          scanner.
        </>,
      ],
    ],
  };
}

/* ── open capture ───────────────────────────────────────────────────────── */

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
    <div className="scrim" onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <div className="sheet">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
          <span className="title">Open capture</span>
          <span className="sp" />
          <Info side="left">
            The capture stays where it is. A render cache is built in a temporary workspace and
            deleted on quit; your adjustments live outside it and re-apply when the same capture is
            reopened.
          </Info>
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
                }}
              >
                <span className="num" style={{ flex: 1, fontSize: 12 }}>
                  {c.name}
                </span>
                {c.has_sidecar ? <Chip tone="info">{c.adjusted} saved</Chip> : null}
                <span className="num" style={{ fontSize: 11, color: 'var(--faint)' }}>
                  {api.fmtBytes(c.bytes)}
                </span>
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
            <span className="lbl" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              DX
              <Info side="left">
                Optional. Captures carry no DX packets and{' '}
                <span className="num">tools/dx_decode.py</span> has never been validated against a
                real roll, so this is a typed lookup, not a reading.
              </Info>
            </span>
            <input className="inp" value={dx} onChange={(e) => setDx(e.target.value)} placeholder="78-13" spellCheck={false} />
          </div>
        </div>

        {dx.trim() ? (
          <div className="rows" style={{ marginBottom: 12, padding: '8px 11px', fontSize: 12 }}>
            {film ? (
              <>
                <b>{film.name}</b>
                <span style={{ color: 'var(--faint)' }}>
                  {' '}
                  · {film.manufacturer} · {film.path}
                  {film.iso ? ` · ISO ${film.iso}` : ''}
                </span>
              </>
            ) : (
              <span className="quiet">No stock matches that DX.</span>
            )}
          </div>
        ) : (
          <div className="field" style={{ marginBottom: 12 }}>
            <span className="lbl">Film path</span>
            <div className="seg" role="radiogroup" aria-label="Film path">
              {FILM_PATHS.map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  role="radio"
                  aria-checked={filmPath === id}
                  className={filmPath === id ? 'on' : ''}
                  onClick={() => setFilmPath(id)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        )}

        {error ? (
          <div
            style={{
              background: 'var(--danger-flat)',
              color: 'var(--danger-ink)',
              borderRadius: 'var(--r-sm)',
              padding: '9px 11px',
              marginBottom: 12,
              fontSize: 12,
            }}
          >
            <span className="num" style={{ fontSize: 11 }}>
              {error}
            </span>
          </div>
        ) : null}

        {busy ? (
          <div style={{ marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 5 }}>
              <Spinner>{job.phase}</Spinner>
              <span className="sp" />
              <span className="num" style={{ fontSize: 11, color: 'var(--faint)' }}>
                {job.message}
              </span>
            </div>
            <div className="bar warnfill">
              <i style={{ width: `${(job.progress || 0) * 100}%` }} />
            </div>
            <p className="quiet" style={{ marginTop: 6 }}>
              A 694 MB capture takes about 26 s: decoding is 6 s and the per-frame scene balance is
              the rest.
            </p>
          </div>
        ) : null}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Btn variant="flat" disabled={busy} onClick={onClose}>
            Cancel
          </Btn>
          <Btn variant="primary" disabled={!path || busy} onClick={go}>
            {busy ? 'Opening…' : 'Open'}
          </Btn>
        </div>
      </div>
    </div>
  );
}

/* ── leftovers from a previous session ──────────────────────────────────── */

function CleanupDialog({ state, onDone }) {
  const [sel, setSel] = useState(() => new Set(state.rolls.map((r) => r.id)));
  const [busy, setBusy] = useState(false);
  const chosen = state.rolls.filter((r) => sel.has(r.id));
  const bytes = chosen.reduce((a, r) => a + r.bytes, 0);
  const atRisk = chosen.filter((r) => r.adjusted > r.exported);

  return (
    <div className="scrim">
      <div className="sheet">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
          <span className="title">Scans from a previous session</span>
          <span className="sp" />
          <Info side="left">
            The workspace holds raw captures and the render cache. It is regenerable from the capture
            files and is normally cleared on quit; the app was force-quit or crashed last time.
          </Info>
        </div>

        <div className="rows" style={{ marginBottom: 12, maxHeight: 280, overflowY: 'auto' }}>
          {state.rolls.map((r) => (
            <label key={r.id}>
              <input
                type="checkbox"
                checked={sel.has(r.id)}
                onChange={(e) => {
                  const n = new Set(sel);
                  if (e.target.checked) n.add(r.id);
                  else n.delete(r.id);
                  setSel(n);
                }}
              />
              <span style={{ flex: 1 }}>{r.name}</span>
              {r.adjusted > r.exported ? <Chip tone="warn">{r.adjusted} adjusted, {r.exported} exported</Chip> : null}
              <span className="num" style={{ fontSize: 11, color: 'var(--faint)' }}>
                {api.fmtDate(r.mtime)}
              </span>
              <span className="num" style={{ fontSize: 11, width: 72, textAlign: 'right' }}>
                {api.fmtBytes(r.bytes)}
              </span>
            </label>
          ))}
        </div>

        {atRisk.length ? (
          <p className="quiet" style={{ marginBottom: 12 }}>
            Adjustments are kept regardless — they live outside the workspace. Deleting removes the
            bulk capture cache only.
          </p>
        ) : null}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Btn variant="flat" disabled={busy} onClick={onDone}>
            Keep everything
          </Btn>
          <Btn
            variant="primary"
            disabled={busy || !chosen.length}
            onClick={async () => {
              setBusy(true);
              try {
                await api.purge({ ids: chosen.map((r) => r.id) });
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

/* ── app ────────────────────────────────────────────────────────────────── */

export default function App() {
  const [ready, setReady] = useState(false);
  const [fatal, setFatal] = useState(null);
  const [dark, setDark] = useTheme();
  const [mode, setMode] = useState('review');
  const [boot, setBoot] = useState(null);
  const [rolls, setRolls] = useState([]);
  const [roll, setRoll] = useState(null);
  const [sel, setSel] = useState(0);
  const [openDlg, setOpenDlg] = useState(false);
  const [cleanup, setCleanup] = useState(null);
  const [exportJob, setExportJob] = useState(null);
  const [hw, setHw] = useState(null);
  const [scanJob, setScanJob] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        await api.initApi();
        const b = await api.bootstrap();
        setBoot(b);
        if (b.hardware?.scan_job) {
          setScanJob({ id: b.hardware.scan_job, kind: 'scan', status: 'running',
                       phase: 'scanning' });
          setMode('scan');
        }
        setHw(b.hardware || null);
        const rs = await api.rolls();
        setRolls(rs);
        if (rs.length) setRoll(rs[0]);
        setReady(true);
        const stale = b.workspace.rolls.filter((r) => !rs.some((x) => x.id === r.id));
        if (stale.length) setCleanup({ ...b.workspace, rolls: stale });
      } catch (e) {
        setFatal(String(e.message || e));
      }
    })();
  }, []);

  /* The machine, polled. Fast while a scan runs because the classification and
     the lamp are the only things telling you it is safe to keep going; slowly
     otherwise, since each probe is a USB round trip.

     This is also how a scan already in flight is adopted. The scan lives in
     its own process, so it outlives this window: relaunching the app, or
     opening it while a scan started elsewhere is running, must show the scan
     and offer its Cancel rather than pretend the machine is idle. */
  const adopt = useCallback((h) => {
    setHw(h);
    if (h?.scan_job) {
      setScanJob((cur) =>
        cur && cur.id === h.scan_job && cur.status === 'running'
          ? cur
          : { id: h.scan_job, kind: 'scan', status: 'running', phase: 'scanning' });
    }
  }, []);

  useEffect(() => {
    if (!ready) return undefined;
    const scanning = scanJob?.status === 'running';
    const t = setInterval(() => {
      api.hardware().then(adopt).catch(() => {});
    }, scanning ? 4000 : 15000);
    return () => clearInterval(t);
  }, [ready, scanJob?.status, adopt]);

  /* The scan itself, polled hard. */
  useEffect(() => {
    if (scanJob?.status !== 'running') return undefined;
    let alive = true;
    const t = setInterval(async () => {
      try {
        const j = await api.job(scanJob.id);
        if (!alive) return;
        setScanJob(j);
        if (j.status !== 'running') {
          api.bootstrap().then((b) => { setBoot(b); setHw(b.hardware || null); }).catch(() => {});
        }
      } catch { /* the backend will be asked again in 500 ms */ }
    }, 500);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [scanJob?.status, scanJob?.id]);

  const startScan = useCallback(async (body) => {
    const r = await api.startScan(body);
    setScanJob({ id: r.id, status: 'running', kind: 'scan', phase: 'starting',
                 max_seconds: r.max_seconds, path: r.path });
    setMode('scan');
    return r;
  }, []);

  const cancelScan = useCallback(async () => {
    if (!scanJob?.id) return;
    try {
      await api.cancelScan(scanJob.id);
    } catch { /* the panic button below is the fallback */ }
  }, [scanJob?.id]);

  const stopScanner = useCallback(async () => {
    try {
      await api.stopScanner();
    } catch { /* nothing more this window can do; the child has its own limit */ }
  }, []);

  useEffect(() => {
    setSel((s) => Math.min(s, Math.max(0, (roll?.frames?.length ?? 1) - 1)));
  }, [roll?.id, roll?.frames?.length]);

  const updateRoll = useCallback((r) => {
    setRoll(r);
    setRolls((rs) => rs.map((x) => (x.id === r.id ? r : x)));
  }, []);

  const machine = useMemo(
    () => machineRows(boot, roll, hw, scanJob),
    [boot, roll, hw, scanJob],
  );

  if (fatal)
    return (
      <div className="app" style={{ display: 'grid', placeItems: 'center' }}>
        <div style={{ maxWidth: '58ch' }}>
          <div className="title" style={{ color: 'var(--danger-ink)', marginBottom: 8 }}>
            Cannot reach the backend
          </div>
          <p className="num" style={{ fontSize: 12, color: 'var(--mute)' }}>
            {fatal}
          </p>
        </div>
      </div>
    );

  if (!ready)
    return (
      <div className="app" style={{ display: 'grid', placeItems: 'center' }}>
        <Spinner>Starting</Spinner>
      </div>
    );

  return (
    <div className="app">
      <TopBar mode={mode} setMode={setMode} roll={roll} dark={dark} setDark={setDark} />
      <Lanes exportJob={exportJob} scanJob={scanJob} onStopScan={stopScanner} />

      {mode === 'review' ? (
        <Review
          roll={roll}
          setRoll={updateRoll}
          rolls={rolls}
          sel={sel}
          setSel={setSel}
          onPickRoll={(id) => api.roll(id).then(setRoll)}
          onOpen={() => setOpenDlg(true)}
          onGoExport={() => setMode('export')}
          machine={[...machine.read, ...machine.unwired]}
        />
      ) : mode === 'scan' ? (
        <Scan
          roll={roll}
          rolls={rolls}
          sel={sel}
          setSel={setSel}
          boot={boot}
          machine={machine}
          hw={hw}
          scanJob={scanJob}
          onOpen={() => setOpenDlg(true)}
          onStartScan={startScan}
          onCancelScan={cancelScan}
          onPickRoll={(id) => api.roll(id).then(setRoll)}
        />
      ) : mode === 'export' ? (
        <ExportScreen
          roll={roll}
          setRoll={updateRoll}
          sel={sel}
          setSel={setSel}
          onJob={setExportJob}
          onGoReview={() => setMode('review')}
        />
      ) : mode === 'diagnostics' ? (
        <Diagnostics />
      ) : (
        <Calibration boot={boot} />
      )}

      <OpenDialog
        open={openDlg}
        onClose={() => setOpenDlg(false)}
        captures={boot?.captures}
        onOpened={async (id) => {
          const rs = await api.rolls();
          setRolls(rs);
          setRoll(rs.find((r) => r.id === id) || rs[0] || null);
          setSel(0);
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
