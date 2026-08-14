// The Console — shell.
//
// ONE PAGE, THREE STEPS: scan → edit → export, in the order a roll of film
// actually goes through them. They used to be three screens off a mode
// switcher that also carried Config and Diagnostics, which made one linear
// process read as five unrelated places.
//
// Two bars across the top (the roll's identity and the reference screens, then
// the three steps), three columns under them, the roll along the floor. A step
// swaps the centre and the rails; the furniture does not move.
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Btn, Chip, Info, Spinner, TopBar, Steps, useTheme } from './components';
import Review from './Review';
import Scan, { blockedReason } from './Scan';
import ExportScreen from './Export';
import ConfigScreen from './Config';
import FramingModal from './FramingModal';
import ContactSheetModal from './ContactSheetModal';
import { Calibration, Diagnostics } from './Info';
import * as api from './api';

/* Third element = why this one cannot be chosen. `POSITIVE` maps to
   filmClass 2, whose stage-2 branch is not ported (F135_REVERSAL_PORTED =
   false), so `dec.check_film_class` refuses it — and used to do so only once
   the capture was already being opened. Offered-and-refused is worse than not
   offered, so it is shown disabled with the reason attached. */
const FILM_PATHS = [
  ['ColNeg', 'Colour neg'],
  ['BnW', 'B&W'],
  ['POSITIVE', 'Positive', 'colour reversal is not ported — F135_REVERSAL_PORTED = false'],
  ['IMPORTED', 'Imported'],
];

/** Which STEP the application opens on.
 *
 *  This used to be the constant `'review'`, which made the product's primary
 *  entry point a text field you typed `/path/to/capture.bin` into. Scanning a
 *  roll — the thing the machine is for — was a side door. The step the app
 *  lands on should be decided by whether there is a machine to scan with, and
 *  by whether there is already work waiting.
 *
 *  A scan already in flight always wins: it outlives this window, so a
 *  relaunch has to show it rather than an idle step with a Scan button.
 *
 *  `present` and not `state === 'ready'` on purpose. A scanner that is plugged
 *  in but has no firmware, or is plugged in and not answering, still belongs
 *  on step 1 — that step is the only place that says what is wrong with it and
 *  offers a recheck. Sending it to step 2 would hide the one fact the user
 *  needs.
 *
 *  With no scanner and no capture the app still opens on step 1, because that
 *  is where the absence is stated, where Recheck is live, and where
 *  `Open capture…` sits. Sending someone to step 2 to be told it needs a
 *  capture would state the same absence one step further from the thing that
 *  can fix it. With no scanner but a roll already open, step 2 is where the
 *  work is and there is nothing to gain by making them press it. */
export function bootMode(hw, hasRoll) {
  if (hw?.scan_job) return 'scan';
  if (hw?.present) return 'scan';
  return hasRoll ? 'review' : 'scan';
}

/** The three steps, as they are right now: what each is doing, how far along,
 *  and — for one that cannot be reached — what it is waiting for.
 *
 *  These are facts, not tab labels. Step 2 needs a capture and step 3 needs
 *  frames, and both say so in the words of whatever is actually missing rather
 *  than greying out and leaving it to be guessed. Step 1 is always reachable:
 *  re-scanning is not a restart, and the machine's own trouble is reported on
 *  the step itself, where Recheck is.
 *
 *  Progress belongs to the step, not to the screen. The scan job, the decode
 *  that follows it and the export job all live in App state, so all three keep
 *  running and keep being visible while the user is standing somewhere else. */
export function stepRows(hw, scanJob, autoOpen, exportJob, exporting, roll) {
  const scanning = scanJob?.status === 'running';
  const elapsed = scanJob?.elapsed ?? (scanJob?.seconds || 0);
  const cap = scanJob?.max_seconds || 0;
  const gate = api.GATE[scanJob?.window?.state || 'unknown'] || api.GATE.unknown;
  const blocked = blockedReason(hw, scanJob);

  const decoding = autoOpen?.status === 'running';
  const frames = roll?.frames || [];
  const adjusted = frames.filter((f) => f.adjusted).length;
  const queue = frames.filter((f) => !f.params?.rejected).length;

  const results = exportJob?.results || [];
  const written = results.filter((r) => r.status === 'written').length;
  const epct = exportJob ? Math.round((exportJob.progress || 0) * 100) : null;

  /* Step 1. The machine's verdict is `blockedReason`'s — the same sentence the
     Scan step's own footer shows, from the same function, so the bar and the
     screen can never disagree about why film is not moving. */
  const scan = {
    id: 'scan',
    label: 'Scan',
    ok: true,
    running: scanning,
    state: scanning
      ? `${api.fmtClock(elapsed)} · ${gate.label} · ${api.fmtBytes(scanJob.bytes)}`
      : scanJob && scanJob.status !== 'running'
        ? scanJob.message || (scanJob.status === 'error' ? 'Scan failed' : 'Scan ended')
        : blocked
          ? blocked.title
          : hw?.simulated
            ? 'Simulated scanner'
            : 'Ready',
    tone: scanning
      ? ''
      : scanJob?.status === 'error'
        ? 'bad'
        : scanJob?.status === 'done'
          ? ''
          : blocked
            ? 'warn'
            : 'ok',
    warn: scanning,
    pct: scanning && cap ? Math.min(100, (elapsed / cap) * 100) : 0,
    pc: scanning ? api.fmtClock(Math.max(0, cap - elapsed)) : null,
  };

  /* Step 2 needs a capture. The decode that turns one into frames is step 2's
     own progress and is reported here, so the 26 s wait is not a screen with a
     spinner you have to stay on. */
  const why2 = decoding ? null : scanning ? 'Scanning' : 'Needs a capture';
  const review = {
    id: 'review',
    label: 'Edit',
    ok: !!roll,
    state: decoding
      ? autoOpen.message || autoOpen.phase || 'Decoding'
      : roll
        ? `${frames.length} frame${frames.length === 1 ? '' : 's'}${
            adjusted ? ` · ${adjusted} adjusted` : ''
          }`
        : why2,
    tone: roll || decoding ? '' : 'quiet',
    warn: decoding,
    pct: decoding ? (autoOpen.progress || 0) * 100 : 0,
    pc: decoding ? `${Math.round((autoOpen.progress || 0) * 100)} %` : null,
  };

  /* Step 3 needs frames. Not "a roll" — a roll every frame of which has been
     rejected has nothing to write, and saying `Needs a capture` there would be
     the wrong sentence. */
  const exp = {
    id: 'export',
    label: 'Export',
    ok: queue > 0,
    running: exporting,
    state: exporting
      ? exportJob?.message || exportJob?.phase || 'Working'
      : exportJob?.status === 'error'
        ? exportJob.error?.slice(0, 60) || 'Export failed'
        : written
          ? `${written} written`
          : !roll
            ? 'Needs frames'
            : queue
              ? `${queue} ready`
              : 'Every frame rejected',
    tone: exportJob?.status === 'error' ? 'bad' : queue || exporting ? '' : 'quiet',
    warn: exporting,
    pct: exporting || exportJob?.status === 'done' ? epct : 0,
    pc: epct == null || (!exporting && exportJob?.status !== 'done') ? null : `${epct} %`,
  };

  return [scan, review, exp];
}

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
/* Where `roll.transport_scale` came from, in one word, from the prose
   `resolve_transport_scale` returns. The full sentence is in the row's Info;
   this is what has to be readable at a glance beside the number, because a
   scale of 1.0000 means two completely different things depending on it. */
export function scaleKind(roll) {
  const s = roll?.transport_source || '';
  if (!s) return 'unrecorded';
  if (s.includes('UNKNOWN')) return 'UNKNOWN';
  if (s.startsWith('explicit')) return 'explicit';
  if (s.startsWith('sidecar')) return 'sidecar';
  if (s.startsWith('measured')) return 'measured pitch';
  if (s.startsWith('DpiBase')) return 'DpiBase default';
  return 'derived';
}

export function machineRows(boot, roll, hw, scanJob, calState) {
  const cal = boot?.calibration;
  /* The scanner's own EEPROM calibration, as distinct from the exposure
     tables in `calibration/` above. Answered from disk — `calibration_store`
     comes in on bootstrap and causes no USB traffic — plus, when the user has
     pressed Recheck, the live verdict from /api/app/calibration.

     Never fetched automatically. The EEPROM answers correctly only on the
     FIRST read after a power cycle, so the good read of a cycle is a resource
     that can be spent; nothing that runs on connect may spend it. */
  const store = calState?.available === false ? null : (calState || boot?.calibration_store);
  const haveUnit = store?.have_calibration;
  const unitSel = store?.selection;
  const unitAction = calState?.action;
  const sync = roll?.sync;
  const scanning = scanJob?.status === 'running';
  // The scan process is the authority whenever it is running.
  const lamp = (scanning ? scanJob?.lamp : hw?.lamp) || null;
  const gate = scanning ? scanJob?.window?.state : null;
  const present = hw?.present && hw?.state === 'ready';
  const stale = !scanning && hw?.cached;
  const age = stale ? ' · cached' : '';
  // `unreachable` outranks `simulated`: once the probe has stopped answering,
  // "simulated" would be a claim about a machine we can no longer see, and the
  // whole point of this rail is that it does not dress a stale reading as a
  // live one.
  const lost = hw?.state === 'unreachable';
  const sim = !!hw?.simulated && !lost;
  return {
    read: [
      [
        'Scanner USB',
        scanning
          ? 'held by the scan'
          : lost
            ? 'unknown'
            : sim
              ? 'simulated'
              : present
                ? `0f05:f135${age}`
                : hw?.state === 'loading_firmware'
                  ? 'loading firmware…'
                  : hw?.state === 'needs_firmware'
                    ? 'no firmware'
                    : hw?.state === 'error'
                      ? 'not answering'
                      : 'absent',
        scanning ? 'good' : lost ? 'warn' : sim ? 'warn' : present ? 'good' : hw?.present ? 'warn' : 'na',
        <>
          A scan runs in its own process and owns the handle for its duration, so
          this window can neither probe nor be the thing that fails to let go of
          it.
          {sim ? (
            <>
              <br />
              <br />
              <b>Simulated.</b> <span className="num">PAKON_SCAN_SIMULATE</span> is
              set, so every reading below comes from a replayed capture. Nothing
              is on the bus and nothing can move.
            </>
          ) : null}
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
      [
        'Unit calibration',
        haveUnit
          ? unitSel?.needs_attention
            ? 'saved · check'
            : 'saved'
          : unitAction === 'wait'
            ? 'power-cycle first'
            : hw?.present
              ? 'not read'
              : 'not read',
        haveUnit ? (unitSel?.needs_attention ? 'warn' : 'good') : hw?.present ? 'warn' : 'na',
        <>
          <b>Per scanner, not per install.</b> These are this machine's own EEPROM
          tables and exist nowhere else — <b>a different F-135 needs its own read</b>
          {' '}before it can be scanned with.
          <br />
          <br />
          Read once, deliberately, and never automatically: the EEPROM answers
          correctly only on the <b>first read after a power cycle</b>, so a refusal
          asking you to power the scanner off and on is the normal path and not a
          fault. Nothing on connect reads it, because doing so would spend that one
          good read.
          <br />
          <br />
          Every read is kept. The store is append-only and its saved images are
          read-only, so a later degraded read lands beside the good one rather than
          on top of it — <b>no calibration is ever deleted or overwritten</b>.
          {unitSel?.stamp ? (
            <>
              <br />
              <br />
              In use: <span className="num">{unitSel.stamp}</span>
              {unitSel.reason ? ` · ${unitSel.reason}` : ''}
              {unitSel.reads?.length ? ` · ${unitSel.reads.length} kept` : ''}
            </>
          ) : null}
          {calState?.headline ? (
            <>
              <br />
              <br />
              {calState.headline}
            </>
          ) : null}
        </>,
      ],
      ['Capture intact', sync ? `${sync.pct_clean} %` : '—', sync?.losses === 0 ? 'good' : sync ? 'warn' : ''],
      ['Sync losses', sync ? sync.losses : '—', sync?.losses === 0 ? 'good' : sync ? 'bad' : ''],
      /* THE GEOMETRY, AND WHETHER IT IS KNOWN.
         `roll.transport_source` has existed and been serialised all along with
         no consumer at all, and its own field comment says why it should have
         one: "we do not know the speed" and "the sidecar says 11467" are
         different situations. On screen they were identical — scale 1.0000
         either way — so a capture with no sidecar looked exactly like one
         whose recorded speed happened to be the square one. */
      [
        'Transport scale',
        roll ? `${(roll.transport_scale ?? 1).toFixed(4)} · ${scaleKind(roll)}` : '—',
        roll ? (scaleKind(roll) === 'UNKNOWN' ? 'warn' : 'good') : 'na',
        <>
          The resample factor that makes pixels square. Lines per mm along the
          travel direction go as <span className="num">1/speed</span>, so this is a
          property of <b>this capture</b>, not a constant.
          {roll?.transport_source ? (
            <>
              <br />
              <br />
              <span className="num">{roll.transport_source}</span>
            </>
          ) : null}
          <br />
          <br />
          <b>UNKNOWN is not 1.0.</b> With no recorded speed and no measured
          pitch the geometry is left alone and said to be unknown, rather than a
          speed being guessed — which is why the source is shown next to the
          number and not instead of it.
        </>,
      ],
      [
        'Pitch residual',
        roll?.transport_residual_pct == null
          ? 'not checked'
          : `${roll.transport_residual_pct >= 0 ? '+' : ''}${roll.transport_residual_pct.toFixed(1)} %`,
        roll?.transport_residual_pct == null
          ? 'na'
          : Math.abs(roll.transport_residual_pct) > 5 ? 'warn' : 'good',
        <>
          The recorded speed predicts a frame pitch; the framing cascade measures
          one over <span className="num">38</span> mm of real film. This is the
          difference, and it is the <b>only offline check</b> that the speed in the
          sidecar is the speed the film actually travelled at.
          <br />
          <br />
          The sidecar wins when they disagree — it is a recorded fact, not an
          estimate — so a large residual is worth seeing rather than being
          resolved silently. Over <span className="num">5 %</span> is flagged.
          <br />
          <br />
          <span className="num">not checked</span> means one half was missing: no
          measured pitch, or no recorded speed. It never means they agree.
        </>,
      ],
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
        /* BOTH, always — see the auto-open below. A DX that fails to look up
           used to take the film path with it, and the roll then satisfied
           `has_film()` with an unresolvable string and rendered as a default
           nobody chose. The DX still wins when it resolves. */
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
    <div className="scrim" onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <div className="sheet">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
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
          <div className="rows" style={{ marginBottom: 16, maxHeight: 180, overflowY: 'auto' }}>
            {captures.map((c) => (
              <button
                key={c.path}
                type="button"
                className={path === c.path ? 'on' : ''}
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px' }}
                onClick={() => {
                  setPath(c.path);
                  if (!name) setName(c.saved_name || c.name.replace(/\.bin$/, ''));
                  if (c.recorded_dx) setDx(c.recorded_dx);
                  if (c.recorded_film_path) setFilmPath(c.recorded_film_path);
                }}
              >
                <span className="num" style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginRight: 8 }}>
                  {c.name}
                </span>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                  {c.recorded_dx || c.recorded_film_path ? (
                    <Chip tone={c.dx_source === 'board' ? 'ok' : 'info'}>
                      {c.recorded_dx || c.recorded_film_path}
                      {c.dx_source === 'board' ? ' · read' : c.dx_source === 'typed' ? ' · typed' : ''}
                    </Chip>
                  ) : c.dx_read ? (
                    <Chip tone="ok">{c.dx_read} · read</Chip>
                  ) : null}
                  {c.has_sidecar ? <Chip tone="info">{c.adjusted} saved</Chip> : null}
                  <span className="num" style={{ fontSize: 12, color: 'var(--faint)', marginLeft: 8, width: 64, textAlign: 'right' }}>
                    {api.fmtBytes(c.bytes)}
                  </span>
                </div>
              </button>
            ))}
          </div>
        ) : null}

        <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
          <div className="field" style={{ flex: 1 }}>
            <span className="lbl">Roll name</span>
            <input className="inp" value={name} onChange={(e) => setName(e.target.value)} placeholder="2026-08-07 A" />
          </div>
          <div className="field" style={{ flex: 1 }}>
            <span className="lbl">DX</span>
            <input className="inp" value={dx} onChange={(e) => setDx(e.target.value)} placeholder="78-13" spellCheck={false} />
          </div>
        </div>

        {dx.trim() ? (
          <div className="rows" style={{ marginBottom: 16 }}>
            <div style={{ padding: '10px 12px', fontSize: 13, background: film ? 'var(--bg)' : 'var(--danger-flat)', borderRadius: 'var(--r-sm)' }}>
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
                <span style={{ color: 'var(--danger-ink)' }}>
                  No matching film stock found.
                </span>
              )}
            </div>
          </div>
        ) : (
          <div className="field" style={{ marginBottom: 12 }}>
            <span className="lbl">Film path</span>
            <div className="seg" role="radiogroup" aria-label="Film path">
              {FILM_PATHS.map(([id, label, disabledWhy]) => (
                <button
                  key={id}
                  type="button"
                  role="radio"
                  aria-checked={filmPath === id}
                  className={filmPath === id ? 'on' : ''}
                  disabled={disabledWhy ? true : undefined}
                  title={disabledWhy || undefined}
                  onClick={() => !disabledWhy && setFilmPath(id)}
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
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 5 }}>
              <Spinner>{job.phase}</Spinner>
              <span className="sp" />
              <span className="num" style={{ fontSize: 12, color: 'var(--faint)' }}>
                {job.message}
              </span>
            </div>
            <div className="bar fill">
              <i style={{ width: `${(job.progress || 0) * 100}%` }} />
            </div>
          </div>
        ) : null}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Btn variant="flat" disabled={busy} onClick={onClose}>
            Cancel
          </Btn>
          {/* A DX that matches nothing is refused by the backend as well; this
              is the same refusal said before the click rather than after it. */}
          <Btn variant="primary" disabled={!path || busy || (!!dx.trim() && !film)} onClick={go}>
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
  // Raw captures are NOT selected by default. A render cache is regenerable
  // and a capture is not, so the two halves of this dialog do not deserve the
  // same default.
  const [capSel, setCapSel] = useState(() => new Set());
  const [busy, setBusy] = useState(false);
  const captures = state.captures || [];
  const chosen = state.rolls.filter((r) => sel.has(r.id));
  const chosenCaps = captures.filter((c) => capSel.has(c.name));
  const bytes =
    chosen.reduce((a, r) => a + r.bytes, 0) + chosenCaps.reduce((a, c) => a + c.bytes, 0);
  const atRisk = chosen.filter((r) => r.adjusted > r.exported);

  const toggle = (set, put, key) => {
    const n = new Set(set);
    if (n.has(key)) n.delete(key);
    else n.add(key);
    put(n);
  };

  return (
    <div className="scrim">
      <div className="sheet">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
          <span className="title">Scans from a previous session</span>
          <span className="sp" />
          <Info side="left">
            {/* This used to read "The workspace holds raw captures and the
                render cache", which was false in both directions: the
                workspace holds rgb14.npy and roll.json, and the captures were
                somewhere else entirely and were never cleared at all. */}
            Two different things, listed separately because they are not equally
            replaceable. The <b>render cache</b> holds{' '}
            <span className="num">rgb14.npy</span> and{' '}
            <span className="num">roll.json</span> and is rebuilt from a capture
            on demand. A <b>raw capture</b> is the scan itself — the film passed
            the sensor once to make it, and deleting it means running the roll
            through again.
            <br />
            <br />
            Both are normally cleared on quit; the app was force-quit or crashed
            last time, so they are still here.
          </Info>
        </div>

        {state.rolls.length ? (
          <>
            <span className="lbl">Render cache</span>
            <div className="rows" style={{ margin: '4px 0 12px', maxHeight: 190, overflowY: 'auto' }}>
              {state.rolls.map((r) => (
                <label key={r.id}>
                  <input
                    type="checkbox"
                    checked={sel.has(r.id)}
                    onChange={() => toggle(sel, setSel, r.id)}
                  />
                  <span style={{ flex: 1 }}>{r.name}</span>
                  {r.adjusted > r.exported ? (
                    <Chip tone="warn">
                      {r.adjusted} adjusted, {r.exported} exported
                    </Chip>
                  ) : null}
                  <span className="num" style={{ fontSize: 11, color: 'var(--faint)' }}>
                    {api.fmtDate(r.mtime)}
                  </span>
                  <span className="num" style={{ fontSize: 11, width: 72, textAlign: 'right' }}>
                    {api.fmtBytes(r.bytes)}
                  </span>
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
                  <input
                    type="checkbox"
                    checked={capSel.has(c.name)}
                    onChange={() => toggle(capSel, setCapSel, c.name)}
                  />
                  <span className="num" style={{ flex: 1, fontSize: 12 }}>
                    {c.name}
                  </span>
                  {c.adjusted > c.exported ? (
                    <Chip tone="warn">
                      {c.adjusted} adjusted, {c.exported} exported
                    </Chip>
                  ) : null}
                  <span className="num" style={{ fontSize: 11, color: 'var(--faint)' }}>
                    {api.fmtDate(c.mtime)}
                  </span>
                  <span className="num" style={{ fontSize: 11, width: 72, textAlign: 'right' }}>
                    {api.fmtBytes(c.bytes)}
                  </span>
                </label>
              ))}
            </div>
          </>
        ) : null}

        {atRisk.length ? (
          <p className="quiet" style={{ marginBottom: 12 }}>
            Adjustments are kept regardless — they live outside the workspace, keyed to the capture.
            They re-apply if that capture is reopened, so keeping the capture is what keeps them
            useful.
          </p>
        ) : null}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Btn variant="flat" disabled={busy} onClick={onDone}>
            Keep everything
          </Btn>
          <Btn
            variant="primary"
            disabled={busy || !(chosen.length || chosenCaps.length)}
            onClick={async () => {
              setBusy(true);
              try {
                await api.purge({
                  ids: chosen.map((r) => r.id),
                  captures: chosenCaps.map((c) => c.name),
                });
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
  // Provisional only: bootMode() replaces it from the hardware probe before
  // anything renders, because `ready` gates the whole tree below.
  const [mode, setMode] = useState('review');
  const [boot, setBoot] = useState(null);
  const [rolls, setRolls] = useState([]);
  const [roll, setRoll] = useState(null);
  const [sel, setSel] = useState(0);
  const [openDlg, setOpenDlg] = useState(false);
  const [framingOpen, setFramingOpen] = useState(false);
  const [framingBusy, setFramingBusy] = useState(false);
  const [contactOpen, setContactOpen] = useState(false);
  const [cleanup, setCleanup] = useState(null);
  /* THE EXPORT, HELD HERE AND NOT IN THE EXPORT STEP.
     It used to be React state inside the Export screen, which meant leaving
     the screen unmounted the component that was polling the job: the progress
     vanished from the bar, the poll's last `setJob` landed on a dead
     component, and coming back showed an idle export that was in fact still
     writing files. In a one-page flow, walking back to step 2 mid-export is a
     normal thing to do, so the job — and the settings that produced it — live
     above the steps. */
  const [exportJob, setExportJob] = useState(null);
  const [exporting, setExporting] = useState(false);
  const [collision, setCollision] = useState(null);
  const [exportCfg, setExportCfg] = useState({
    format: 'tiff',
    colour: 'linear',
    template: '{roll}_{frame:02}_{stock}',
    dest: '~/Pictures/Film',
    subfolder: true,
  });
  const [hw, setHw] = useState(null);
  const [hwBusy, setHwBusy] = useState(false);
  const [scanJob, setScanJob] = useState(null);
  const [calState, setCalState] = useState(null);
  const [autoOpen, setAutoOpen] = useState(null);
  //: scan job ids whose capture this window has already tried to open, so a
  //  poll that re-delivers a finished job cannot decode it twice.
  const opened = useRef(new Set());

  useEffect(() => {
    (async () => {
      try {
        await api.initApi();
        const b = await api.bootstrap();
        setBoot(b);
        if (b.hardware?.scan_job) {
          setScanJob({ id: b.hardware.scan_job, kind: 'scan', status: 'running',
                       phase: 'scanning' });
        }
        setHw(b.hardware || null);
        const rs = await api.rolls();
        setRolls(rs);
        if (rs.length) setRoll(rs[0]);
        // After the rolls, not before: which step to open on depends on
        // whether there is already work waiting as well as on the machine.
        setMode(bootMode(b.hardware, rs.length > 0));
        setReady(true);
        // Leftovers a previous session should have cleared. Raw captures count
        // too now: they are the 700 MB items, and until they lived in the temp
        // tree nothing could see them, so a crash left them on disk for good.
        const stale = b.workspace.rolls.filter((r) => !rs.some((x) => x.id === r.id));
        const staleCaps = b.workspace.captures || [];
        if (stale.length || staleCaps.length)
          setCleanup({ ...b.workspace, rolls: stale, captures: staleCaps });
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

  /* A probe that fails is a fact, not a non-event. The scanner being switched
     off or unplugged mid-session is the normal way this happens, and the old
     `.catch(() => {})` left the last successful probe on screen for the rest
     of the session — a rail reading `0f05:f135 · good` beside a machine that
     was no longer plugged in. One blip is tolerated, because a probe races the
     3 s cache and USB; two in a row is the machine, and is reported. */
  useEffect(() => {
    if (!ready) return undefined;
    const scanning = scanJob?.status === 'running';
    let alive = true;
    let fails = 0;
    const t = setInterval(() => {
      api
        .hardware()
        .then((h) => {
          if (!alive) return;
          fails = 0;
          adopt(h);
        })
        .catch((e) => {
          if (!alive || ++fails < 2) return;
          setHw((cur) => ({
            ...(cur || {}),
            present: false,
            state: 'unreachable',
            lamp: null,
            simulated: null,
            cached: true,
            hint: `The backend stopped answering the hardware probe: ${e.message || e}`,
          }));
        });
    }, scanning ? 4000 : 15000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [ready, scanJob?.status, adopt]);

  /* Ask now, because someone pressed Recheck.
     The calibration verdict rides along, because "is there a machine" and
     "does this machine have its calibration" are one question to whoever
     just plugged something in. It is fetched HERE and nowhere else — never on
     boot, never on a timer — since it is the only calibration call the app
     makes and the rule that it must be user-initiated is easiest to keep
     when there is exactly one call site. It reports; it does not read. */
  const recheckHw = useCallback(async () => {
    setHwBusy(true);
    api.calibration().then(setCalState).catch(() => {});
    try {
      adopt(await api.hardware(true));
    } catch (e) {
      setHw((cur) => ({
        ...(cur || {}),
        present: false,
        state: 'unreachable',
        lamp: null,
        simulated: null,
        hint: String(e.message || e),
      }));
    } finally {
      setHwBusy(false);
    }
  }, [adopt]);

  /* The scan itself, polled hard.
     A scan whose job record cannot be read is over as far as this window is
     concerned. Without that the UI wedged: `status: 'running'` is what puts
     the live panel on screen and disables the start button, so a backend
     restart mid-scan left a Cancel that could never land and no way back to
     the rest of the application. Four seconds of silence ends it here; the
     transport is not this window's to stop anyway — the scan process has its
     own hard limit and its own EOF-on-pipe cancel, and both outlive us. */
  useEffect(() => {
    if (scanJob?.status !== 'running') return undefined;
    const id = scanJob.id;
    let alive = true;
    let fails = 0;
    const t = setInterval(async () => {
      try {
        const j = await api.job(id);
        if (!alive) return;
        fails = 0;
        setScanJob(j);
        if (j.status !== 'running') {
          api.bootstrap().then((b) => { setBoot(b); setHw(b.hardware || null); }).catch(() => {});
        }
      } catch (e) {
        if (!alive || ++fails < 8) return;
        setScanJob((cur) =>
          cur && cur.id === id && cur.status === 'running'
            ? { ...cur, status: 'error', phase: 'lost', cancellable: false,
                openable: false,
                message: 'Lost contact with the scan',
                detail: `The backend stopped answering for this job: ${e.message || e}. `
                        + 'The scan process stops the transport on its own time '
                        + 'limit and on losing its parent, so the machine is not '
                        + 'waiting on this window.' }
            : cur);
      }
    }, 500);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [scanJob?.status, scanJob?.id]);

  const startScan = useCallback(async (body) => {
    const r = await api.startScan(body);
    opened.current.delete(r.id);
    setScanJob({ id: r.id, status: 'running', kind: 'scan', phase: 'starting',
                 max_seconds: r.max_seconds, path: r.path,
                 open_with: { film_path: body.film_path, dx: body.dx,
                              name: body.name } });
    setMode('scan');
    return r;
  }, []);

  /* ── scan → decode → review, with nobody picking a file ──────────────────
     The capture a scan just made is the roll the user wants to look at. There
     is no other reason they pressed Scan. So when the scan process is done and
     the backend says the result is worth decoding, this opens it — with the
     film path and DX that were chosen before the scan started, carried on the
     job record so that a window which adopted a scan in flight has them too.

     `openable` is the backend's decision, not this window's, so the rule lives
     in one place: film that went past the sensor is a roll (a cancel counts),
     film scanned after the lamp died is not.

     Not automatic when it failed. A scan that stopped on DARK leaves a file on
     disk and the Scan screen says so; decoding it and dropping the user into
     Review would present a lamp failure as a roll of photographs. Open capture
     is still there for anyone who wants to look. */
  useEffect(() => {
    if (!scanJob || scanJob.status === 'running') return;
    if (opened.current.has(scanJob.id)) return;
    opened.current.add(scanJob.id);
    if (!scanJob.openable || !scanJob.path) return;

    let alive = true;
    (async () => {
      const w = scanJob.open_with || {};
      setAutoOpen({ status: 'running', phase: 'opening', progress: 0,
                    message: 'decoding the capture' });
      try {
        const { id } = await api.openCapture({
          path: scanJob.path,
          name: w.name || undefined,
          /* Same precedence as the Open dialog — a DX code resolves the film
             path — but BOTH are sent. Dropping `film_path` whenever a DX was
             typed meant a DX that failed to look up discarded the film path
             as well: the backend swallowed the failed lookup into
             `stock = null`, `has_film()` was still satisfied by the
             unresolvable string, and the roll walked through the refusal that
             exists to stop exactly that and rendered as a colour-negative
             default nobody chose. They cannot disagree, because the DX wins
             when it resolves and the film path is only the floor when it does
             not. */
          film_path: w.film_path || undefined,
          dx: w.dx || undefined,
        });
        const final = await api.pollJob(id, (j) => alive && setAutoOpen(j), 300);
        if (!alive) return;
        if (final.status === 'error') return setAutoOpen(final);
        const rs = await api.rolls();
        if (!alive) return;
        setRolls(rs);
        setRoll(rs.find((r) => r.id === final.roll) || rs[0] || null);
        setSel(0);
        setAutoOpen(null);
        // The finished job is deliberately kept. The capture lane keeps
        // reading `Roll end — …` instead of snapping back to `Idle`, which is
        // the only trace left of how the roll on screen got there.
        setMode('review');
        api.bootstrap().then(setBoot).catch(() => {});
      } catch (e) {
        if (alive) setAutoOpen({ status: 'error', error: String(e.message || e) });
      }
    })();
    return () => {
      alive = false;
    };
  }, [scanJob]);

  const cancelScan = useCallback(async () => {
    if (!scanJob?.id) return;
    try {
      await api.cancelScan(scanJob.id);
    } catch { /* the panic button below is the fallback */ }
  }, [scanJob?.id]);

  /* The panic button. Returns its verdict instead of swallowing it: the one
     press that most needs an answer is the one made when nothing else on
     screen is responding, and "did that reach the motor" is not a question the
     user should have to infer from a lane that goes on saying Idle. */
  const stopScanner = useCallback(async () => {
    try {
      const r = await api.stopScanner();
      // The stop can change what the machine is, and does clear the in-flight
      // marker, so re-read rather than wait for the next 15 s poll.
      api.hardware().then(setHw).catch(() => {});
      return r;
    } catch (e) {
      return { error: `The backend did not answer the stop: ${e.message || e}` };
    }
  }, []);

  /* Put the last scan's result away. Only ever reachable once the job has
     ended — there is no dismissing a running scan, because the panel it is on
     carries the Cancel. */
  const dismissScan = useCallback(() => {
    setAutoOpen(null);
    setScanJob((cur) => (cur && cur.status === 'running' ? cur : null));
  }, []);

  /* Decode a capture the scan left behind after all — the manual counterpart
     of the automatic path, for the outcomes that path deliberately declines
     (a DARK stop, or an open that errored and can be retried). */
  const openScanResult = useCallback(() => {
    if (!scanJob?.path) return;
    opened.current.delete(scanJob.id);
    setScanJob((cur) => (cur ? { ...cur, openable: true } : cur));
  }, [scanJob?.id, scanJob?.path]);

  useEffect(() => {
    setSel((s) => Math.min(s, Math.max(0, (roll?.frames?.length ?? 1) - 1)));
  }, [roll?.id, roll?.frames?.length]);

  const updateRoll = useCallback((r) => {
    setRoll(r);
    setRolls((rs) => rs.map((x) => (x.id === r.id ? r : x)));
  }, []);

  /* Run the export, from here, so it survives being navigated away from.
   *
   * `onExist` is the answer to a collision — ask | skip | overwrite | unique.
   * Without one this plans first and hands the plan back as a sheet: the
   * backend refuses a collision on its own when the answer is still `ask`, so
   * the sheet is the polite path and not the safety. */
  const runExport = useCallback(
    async (onExist) => {
      if (!roll) return;
      const cfg = exportCfg;
      const format = cfg.colour === 'linear' ? 'tiff' : cfg.format;
      const body = {
        roll: roll.id,
        frames: roll.frames.filter((f) => !f.params?.rejected).map((f) => f.index),
        format,
        colour: cfg.colour,
        template: cfg.template,
        dest: cfg.dest,
        subfolder: cfg.subfolder,
      };
      if (!onExist) {
        try {
          const plan = await api.planExport(body);
          if (plan.needs_confirm) return setCollision(plan);
        } catch (e) {
          // A plan that cannot be made is not a reason to export blind: the
          // backend refuses a collision anyway, so fall through and let it.
          console.error('export plan failed', e);
        }
      }
      setCollision(null);
      setExporting(true);
      setExportJob(null);
      try {
        const { id } = await api.exportRoll({ ...body, ...(onExist ? { on_exist: onExist } : {}) });
        const final = await api.pollJob(id, setExportJob, 350);
        setExportJob(final);
        // A refusal comes back as a job, not a throw. Put the sheet up rather
        // than showing the raw message in the error chip.
        if (final.needs_confirm && final.plan) setCollision(final.plan);
        updateRoll(await api.roll(roll.id));
      } catch (e) {
        setExportJob({ status: 'error', error: String(e.message || e) });
      } finally {
        setExporting(false);
      }
    },
    [roll, exportCfg, updateRoll],
  );

  /* Re-run the frame detection cascade over the whole strip — what the
     framing panel's "Auto Alignment" button was named for and never did. The
     backend snapshots the boundaries first, so Undo in the correction bench
     is the way back. */
  const redetectFrames = useCallback(async () => {
    if (!roll?.id) return;
    setFramingBusy(true);
    try {
      updateRoll(await api.boundary(roll.id, { op: 'redetect' }));
    } finally {
      setFramingBusy(false);
    }
  }, [roll?.id, updateRoll]);

  const machine = useMemo(
    () => machineRows(boot, roll, hw, scanJob, calState),
    [boot, roll, hw, scanJob, calState],
  );

  const steps = useMemo(
    () => stepRows(hw, scanJob, autoOpen, exportJob, exporting, roll),
    [hw, scanJob, autoOpen, exportJob, exporting, roll],
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
      <Steps mode={mode} setMode={setMode} rows={steps} onStopScan={stopScanner} />

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
          onOpenFraming={() => setFramingOpen(true)}
          onOpenContactSheet={() => setContactOpen(true)}
          onGoScan={() => setMode('scan')}
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
          hwBusy={hwBusy}
          scanJob={scanJob}
          autoOpen={autoOpen}
          onOpen={() => setOpenDlg(true)}
          onStartScan={startScan}
          onCancelScan={cancelScan}
          onRecheckHw={recheckHw}
          onDismissScan={dismissScan}
          onOpenScanResult={openScanResult}
          onPickRoll={(id) => api.roll(id).then(setRoll)}
        />
      ) : mode === 'config' ? (
        <ConfigScreen
          boot={boot}
          hw={hw}
          hwBusy={hwBusy}
          onRecheckHw={recheckHw}
          scanJob={scanJob}
        />
      ) : mode === 'export' ? (
        <ExportScreen
          roll={roll}
          sel={sel}
          setSel={setSel}
          cfg={exportCfg}
          setCfg={setExportCfg}
          job={exportJob}
          running={exporting}
          collision={collision}
          onRun={runExport}
          onCancelCollision={() => setCollision(null)}
          onGoReview={() => setMode('review')}
        />
      ) : mode === 'diagnostics' ? (
        <Diagnostics />
      ) : (
        <Calibration boot={boot} />
      )}

      <FramingModal
        open={framingOpen}
        onClose={() => setFramingOpen(false)}
        roll={roll}
        sel={sel}
        onStep={setSel}
        busy={framingBusy}
        onRedetect={redetectFrames}
      />

      <ContactSheetModal
        open={contactOpen}
        onClose={() => setContactOpen(false)}
        roll={roll}
        onSelectFrame={setSel}
      />

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
