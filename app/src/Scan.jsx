// Scan — design/variants/console-scan.html.
//
// Same furniture as Review: settings rail left, machine rail right, the strip
// in the middle, the roll along the floor.
//
// Scan strip is now the primary action and it drives the transport. What that
// costs in this screen is honesty about state: while a scan runs the centre
// stops showing a picture of film and shows what is actually knowable —
// elapsed against the limit, data captured, sync integrity, what the sensor is
// reading (clear / film / dark), the lamp, and a Cancel that is always the
// largest thing on screen.
//
// There is still no Preview button, and there cannot be: a transport scanner
// feeds forwards, once. "Preview" in this app is a render quality.
import React from 'react';
import {
  Btn,
  Chip,
  Field,
  Filmstrip,
  Grp,
  Info,
  Rail,
  RailHead,
  Seg,
  Spinner,
  State,
  Toggle,
} from './components';
import * as api from './api';

const PERFS = Array.from({ length: 48 }, (_, i) => i);

/* ── why Scan strip cannot run, in the order the user would hit them ──────
 *
 * Each entry carries a `fix`: what the user can do about it from here. Where
 * that is "look again" the screen offers a live Recheck rather than a disabled
 * button — the machine being switched on is the single most likely thing to
 * change between one look and the next, and a button that cannot be pressed
 * cannot say so. */

function blockedReason(hw, scanJob) {
  if (!hw) return { title: 'Checking', why: 'The machine has not been probed yet.', fix: 'recheck' };
  if (scanJob?.status === 'running') return { title: 'Scanning', why: 'A scan is already running.', fix: null };
  if (hw.state === 'unreachable')
    return { title: 'Backend silent', why: hw.hint || 'The hardware probe stopped answering.', fix: 'recheck' };
  if (!hw.present)
    return { title: 'No scanner', why: 'Nothing at 0f05:f135 on USB.', fix: 'recheck' };
  if (hw.state === 'needs_firmware')
    return { title: 'No firmware', why: 'Load it with tools/pakon_load.py, then recheck.', fix: 'recheck' };
  if (hw.writes_locked)
    return {
      title: 'Writes locked',
      why: 'tools/WRITES_LOCKED refuses every register write. Lifting it is a deliberate act, and its own file says so.',
      fix: 'recheck',
    };
  if (!hw.calibration)
    return {
      title: 'No calibration',
      why: 'calibration/README.json is the only record of the exposure the dark and gain tables are valid for.',
      fix: null,
    };
  if (hw.state !== 'ready')
    return { title: 'Not answering', why: hw.hint || '', fix: 'recheck' };
  return null;
}

/* ── the live scan ──────────────────────────────────────────────────────── */

function Telem({ label, value, tone, info }) {
  return (
    <div>
      <span className="lbl" style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
        {label}
        {info ? <Info>{info}</Info> : null}
      </span>
      <b className={tone ? `st-${tone}` : ''} style={tone === 'bad' ? { color: 'var(--danger-ink)' } : tone === 'ok' ? { color: 'var(--ok-ink)' } : undefined}>
        {value}
      </b>
    </div>
  );
}

/** What happens after the transport stops.
 *
 *  The scan is the main path, so a finished scan does not end at a file on
 *  disk with an instruction to go and open it. When the capture is worth
 *  decoding the app is already decoding it and this reports progress; when it
 *  is not, this says why, and offers to decode it anyway rather than deciding
 *  on the owner's behalf that they may not look. */
function AfterScan({ job, open, onOpenAnyway, onDismiss }) {
  if (open && open.status === 'running')
    return (
      <div style={{ display: 'grid', gap: 8, justifyItems: 'center', width: '100%', maxWidth: 420 }}>
        <Spinner>{open.phase || 'Opening'}</Spinner>
        <div className="bar warnfill" style={{ width: '100%' }}>
          <i style={{ width: `${(open.progress || 0) * 100}%` }} />
        </div>
        <span className="quiet num" style={{ fontSize: 11 }}>{open.message || ''}</span>
      </div>
    );

  if (open && (open.status === 'error' || open.error))
    return (
      <div style={{ display: 'grid', gap: 10, justifyItems: 'center', maxWidth: '52ch' }}>
        <span style={{ color: 'var(--danger-ink)', fontSize: 13 }}>Decode failed</span>
        <span className="num quiet" style={{ fontSize: 11, textAlign: 'center' }}>
          {open.error || open.message}
        </span>
        <div style={{ display: 'flex', gap: 8 }}>
          <Btn variant="primary" onClick={onOpenAnyway}>Try again</Btn>
          <Btn variant="flat" onClick={onDismiss}>Dismiss</Btn>
        </div>
      </div>
    );

  return (
    <div style={{ display: 'flex', gap: 8 }}>
      {job.path && !job.openable ? (
        <>
          <Btn variant="primary" onClick={onOpenAnyway}>Decode anyway</Btn>
          <Info side="left">
            The capture was written, so it can be decoded. It is not opened
            automatically because the scan did not end cleanly — on a{' '}
            <span className="num">dark</span> stop the frames past that point are
            a failed lamp, not photographs.
          </Info>
        </>
      ) : null}
      <Btn variant="flat" onClick={onDismiss}>Dismiss</Btn>
    </div>
  );
}

function Live({ job, onCancel, busy, open, onOpenAnyway, onDismiss }) {
  const running = job.status === 'running';
  const w = job.window || {};
  const r = job.run || {};
  const l = job.lamp || {};
  const gate = api.GATE[w.state || 'unknown'] || api.GATE.unknown;
  const elapsed = job.elapsed ?? job.seconds ?? 0;
  const cap = job.max_seconds || 0;
  const pct = cap ? Math.min(100, (elapsed / cap) * 100) : 0;
  const breaks = job.sync_breaks || 0;
  const lines = r.lines || job.lines || 0;
  const clean = lines ? (100 * lines) / (lines + breaks) : null;
  const lampBad = l.ok === false;

  return (
    <main className="scanstage">
      <div className="stagehead">
        <span className="title">{running ? 'Scanning' : job.message || 'Scan ended'}</span>
        {/* No state chip here. The classification is already the largest thing
            on the screen and is in the capture lane as well; a third copy in a
            pill said nothing and rendered badly. Only the exceptional case
            gets a chip. */}
        {lampBad ? (
          <Chip tone="bad" dot>
            Lamp fault
          </Chip>
        ) : null}
        <span className="sp" />
        <span className="quiet">{gate.note}</span>
      </div>

      <div className="filmwrap" style={{ flexDirection: 'column', gap: 18, justifyContent: 'center' }}>
        <div
          style={{
            display: 'grid',
            placeItems: 'center',
            gap: 10,
            padding: '28px 0',
          }}
        >
          <div
            className="num"
            style={{
              fontSize: 58,
              lineHeight: 1,
              letterSpacing: '-0.02em',
              userSelect: 'none',
              color:
                w.state === 'dark'
                  ? 'var(--danger-ink)'
                  : w.state === 'clear'
                    ? 'var(--ok-ink)'
                    : 'var(--foreground)',
            }}
          >
            {gate.label.toUpperCase()}
          </div>
          <div className="quiet">
            {w.t == null ? '—' : `t ${Number(w.t).toFixed(4)} of the calibrated clear gate`}
          </div>
        </div>

        <div style={{ width: '100%', maxWidth: 560 }}>
          <div className={`bar${running ? ' warnfill' : ''}`} style={{ height: 8 }}>
            <i style={{ width: `${pct}%` }} />
          </div>
          <div style={{ display: 'flex', marginTop: 6 }}>
            <span className="quiet">{api.fmtClock(elapsed)}</span>
            <span className="sp" />
            <span className="quiet">limit {api.fmtClock(cap)}</span>
          </div>
        </div>

        {running ? (
          <Btn
            variant="danger big"
            disabled={busy}
            onClick={onCancel}
            style={{ maxWidth: 260, height: 46, fontSize: 15 }}
          >
            {busy ? 'Stopping…' : 'Cancel scan'}
          </Btn>
        ) : (
          <div
            style={{
              maxWidth: '56ch',
              textAlign: 'center',
              display: 'grid',
              gap: 12,
              justifyItems: 'center',
            }}
          >
            {job.detail ? <p className="quiet">{job.detail}</p> : null}
            {job.transport_stopped === false ? (
              <p style={{ color: 'var(--danger-ink)', fontSize: 13 }}>
                The transport stop was not acknowledged. Power the scanner off.
              </p>
            ) : null}
            <AfterScan
              job={job}
              open={open}
              onOpenAnyway={onOpenAnyway}
              onDismiss={onDismiss}
            />
          </div>
        )}
      </div>

      <div className="telem">
        <Telem label="Elapsed" value={api.fmtClock(elapsed)} />
        <Telem label="Captured" value={api.fmtBytes(job.bytes)} />
        <Telem label="Lines" value={lines ? lines.toLocaleString() : '—'} />
        <Telem
          label="Sync"
          value={clean == null ? '—' : `${clean.toFixed(2)} %`}
          tone={breaks === 0 && lines ? 'ok' : breaks ? 'bad' : ''}
          info={
            <>
              Lines whose sync markers were exactly <span className="num">6000</span> words apart.
              Anything else is a FIFO break and is skipped rather than allowed to shear the strip.
            </>
          }
        />
        <Telem
          label="Lamp"
          value={
            l.temp_lb_c != null
              ? `${l.status_hex ?? '—'} · ${l.temp_lb_c.toFixed(1)} °C`
              : l.status_hex || '—'
          }
          tone={lampBad ? 'bad' : l.polls ? 'ok' : ''}
          info={
            <>
              Light board <span className="num">0x83</span> status and{' '}
              <span className="num">0x88</span> temperatures, once a second. Fault bits{' '}
              <span className="num">5</span> and <span className="num">6</span> abort.
              <br />
              <br />
              The vendor does not poll this during a scan — <span className="num">LAMP_WARNING</span>{' '}
              and <span className="num">LAMP_ERROR</span> are consumed but never produced anywhere in{' '}
              <span className="num">TLB.dll</span>.
            </>
          }
        />
        <Telem
          label={w.state === 'clear' ? 'Clear run' : 'Film'}
          value={
            w.state === 'clear'
              ? `${(r.clear_run || 0).toLocaleString()} lines`
              : `${(r.film_lines || 0).toLocaleString()} lines`
          }
          info={
            <>
              Roll end needs <span className="num">4000</span> unbroken clear lines — about 2.7 frame
              pitches — and cannot arm until film has been seen, so the leader cannot end a scan
              before the film arrives.
            </>
          }
        />
      </div>
    </main>
  );
}

/* ── the confirm sheet: the last moment before film moves ───────────────── */

function StartSheet({ open, hw, next, onClose, onStart }) {
  const cal = hw?.calibration;
  const speeds = hw?.limits?.speeds || {};
  const [base] = React.useState(16);
  const [speed, setSpeed] = React.useState(String(cal?.speed ?? speeds[16] ?? 5917));
  const [secs, setSecs] = React.useState(String(hw?.limits?.default_seconds ?? 360));
  const [refresh, setRefresh] = React.useState(true);
  const [name, setName] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState(null);

  React.useEffect(() => {
    if (open) {
      setSpeed(String(cal?.speed ?? speeds[16] ?? 5917));
      setSecs(String(hw?.limits?.default_seconds ?? 360));
      setRefresh(true);
      setErr(null);
      setBusy(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;
  const calSpeed = cal?.speed ?? speeds[base];
  const lo = hw?.limits?.speed_min ?? 1000;
  const hi = hw?.limits?.speed_max ?? 32766;
  const sN = Number(speed);
  const tN = Number(secs);
  const bad =
    !Number.isFinite(sN) || sN < lo || sN > hi || !Number.isFinite(tN) || tN <= 0;

  return (
    <div className="scrim" onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <div className="sheet">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
          <span className="title">Scan strip</span>
          <span className="sp" />
          <Chip tone="warn" dot>
            Film will move
          </Chip>
        </div>

        <div className="field" style={{ marginBottom: 12 }}>
          <span className="lbl">Roll name</span>
          <input
            className="inp"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="2026-08-07 A"
          />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
          <Field
            label="Transport speed"
            info={
              <>
                Register <span className="num">0xA5</span>. Default is{' '}
                <span className="num">MotorSpeedPlus</span> for{' '}
                <span className="num">DpiBase{base}_35</span> ={' '}
                <span className="num">{calSpeed}</span>, from the recovered hive. Legal range{' '}
                <span className="num">{lo}</span>–<span className="num">{hi}</span>; the physical
                units are unknown, so lower is slower and that is all that can be claimed.
              </>
            }
          >
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                className="inp"
                value={speed}
                inputMode="numeric"
                onChange={(e) => setSpeed(e.target.value.replace(/[^0-9]/g, ''))}
              />
              <Btn variant="flat" disabled={sN === calSpeed} onClick={() => setSpeed(String(calSpeed))}>
                Calibrated
              </Btn>
            </div>
          </Field>

          <Field
            label="Time limit"
            info={
              <>
                The backstop. It stops the transport whatever any detector believes. A 36-exposure
                roll runs about four minutes; the ceiling here is{' '}
                <span className="num">{Math.round((hw?.limits?.hard_seconds ?? 900) / 60)}</span>{' '}
                minutes and there is no unlimited.
              </>
            }
          >
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <input
                className="inp"
                value={secs}
                inputMode="numeric"
                onChange={(e) => setSecs(e.target.value.replace(/[^0-9]/g, ''))}
              />
              <span className="quiet">s</span>
            </div>
          </Field>
        </div>

        <div style={{ marginBottom: 12 }}>
          <Toggle
            on={refresh}
            onChange={setRefresh}
            info={
              <>
                The lamp has died at about <span className="num">60 s</span> twice, at the same
                point. This re-asserts the lamp drive every{' '}
                <span className="num">{hw?.limits?.lamp_refresh_s ?? 20}</span> s, which is what{' '}
                <span className="num">FN_bBeforeScan</span> appears to be doing when it calls{' '}
                <span className="num">LampOn</span> twice a second apart. It never sends lamp-off, so
                it cannot band the film. Turn it off to reproduce the failure.
              </>
            }
          >
            Lamp refresh
          </Toggle>
        </div>

        <div className="rows" style={{ marginBottom: 12, padding: '9px 11px', fontSize: 12 }}>
          <span className="quiet">
            Base {base} · integration <span className="num">{cal?.integration}</span> · lamp N{' '}
            <span className="num">{cal?.lamp_n}</span> · levels{' '}
            <span className="num">{(cal?.levels || []).slice(0, 3).join('/')}</span>
          </span>
        </div>

        {/* Restated, not re-asked. These come from the settings rail and are
            what the capture will be decoded as the moment the transport
            stops — the whole reason nobody has to open a file afterwards. */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            marginBottom: 12,
            padding: '9px 11px',
            fontSize: 12,
            background: 'var(--soft)',
            borderRadius: 'var(--r-sm)',
          }}
        >
          <span className="quiet" style={{ flex: 1 }}>
            Decodes as{' '}
            <span className="num">{next?.dx ? next.dx : next?.film_path || 'ColNeg'}</span>
            {next?.stock ? ` · ${next.stock.name}` : ''} · opens in Roll
          </span>
          <Info side="left">
            Unless the DX board reads a code off this roll, which outranks it —
            a measurement beats a typed setting. It usually reads nothing:{' '}
            <span className="num">dx_from_sidecar</span> only reports a code that
            passed parity and was unambiguous, and the decoder has never been
            validated against a real roll.
          </Info>
        </div>

        {err ? (
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
              {err}
            </span>
          </div>
        ) : null}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Btn variant="flat" disabled={busy} onClick={onClose}>
            Cancel
          </Btn>
          <Btn
            variant="primary"
            disabled={busy || bad}
            onClick={async () => {
              setBusy(true);
              setErr(null);
              try {
                await onStart({
                  base,
                  speed: sN,
                  max_seconds: tN,
                  name: name.trim(),
                  // Carried into the job record, so the capture decodes
                  // itself with what was chosen here.
                  film_path: next?.dx ? undefined : (next?.film_path || 'ColNeg'),
                  dx: next?.dx || undefined,
                  lamp_refresh: refresh ? (hw?.limits?.lamp_refresh_s ?? 20) : 0,
                  lamp_refresh_mode: refresh ? 'full' : 'off',
                });
                onClose();
              } catch (e) {
                setErr(String(e.message || e));
                setBusy(false);
              }
            }}
          >
            {busy ? 'Starting…' : 'Start'}
          </Btn>
        </div>
      </div>
    </div>
  );
}

/* ── screen ─────────────────────────────────────────────────────────────── */

export default function Scan({
  roll,
  sel,
  setSel,
  boot,
  machine,
  hw,
  hwBusy,
  scanJob,
  autoOpen,
  onOpen,
  onStartScan,
  onCancelScan,
  onRecheckHw,
  onDismissScan,
  onOpenScanResult,
}) {
  const cal = boot?.calibration?.readme;
  const cfg = cal?.config;
  const sync = roll?.sync;
  const [sheet, setSheet] = React.useState(false);
  const [stopping, setStopping] = React.useState(false);
  const blocked = blockedReason(hw, scanJob);
  const scanning = scanJob?.status === 'running';
  const live = scanJob && (scanJob.status === 'running' || scanJob.kind === 'scan');

  /* What the next scan will be decoded as.
     This rail is titled Capture settings and until now it fed the Open
     dialog — changing the film path opened a file picker, which is exactly
     backwards on the screen whose job is to make a capture. It is the next
     scan's settings, held here and handed to the scan, which carries them
     through to the decode. Seeded once from whatever is open so a second roll
     of the same stock needs no input at all. */
  const [next, setNext] = React.useState(() => ({
    film_path: roll?.film_path || 'ColNeg',
    dx: roll?.dx || '',
  }));
  const [stock, setStock] = React.useState(null);

  React.useEffect(() => {
    const dx = next.dx.trim();
    if (!dx) return setStock(null);
    let alive = true;
    api
      .lookupFilm(dx)
      .then((f) => alive && setStock(f.error ? null : f))
      .catch(() => alive && setStock(null));
    return () => {
      alive = false;
    };
  }, [next.dx]);

  React.useEffect(() => {
    if (scanJob?.status !== 'running') setStopping(false);
  }, [scanJob?.status]);

  /* Base 4 and 8 are not options this screen withholds — they are line
     lengths the decoder does not accept. `decodable_bases` is the backend's
     own list, so if that ever grows this control grows with it instead of
     needing to be remembered. */
  const bases = hw?.limits?.decodable_bases?.length
    ? hw.limits.decodable_bases.map(Number)
    : [16];
  const speeds = hw?.limits?.speeds || {};

  const window6 = roll
    ? roll.frames.slice(
        Math.max(0, Math.min(sel - 2, roll.frames.length - 6)),
        Math.max(6, Math.min(sel + 4, roll.frames.length)),
      )
    : [];

  return (
    <>
      <div className="body" style={{ gridTemplateColumns: '296px minmax(0,1fr) 292px' }}>
        {/* ── every parameter, visible before you commit ── */}
        <Rail side="l" aria-label="Capture settings">
          <RailHead title="Capture settings" />

          <Grp>
            <Field
              label="Film path"
              info={
                <>
                  What the capture this scan makes will be decoded as. No default is
                  assumed from the film: a capture carries no DX packets, so the
                  stock is stated here.
                </>
              }
            >
              <Seg
                ariaLabel="Film path"
                value={next.film_path}
                options={[
                  ['ColNeg', 'Colour neg'],
                  ['BnW', 'B&W'],
                  ['POSITIVE', 'Positive'],
                ]}
                onChange={(v) => setNext((n) => ({ ...n, film_path: v, dx: '' }))}
              />
            </Field>

            <Field
              label="DX"
              value={stock ? stock.path : next.dx.trim() ? 'no match' : null}
              info={
                <>
                  Typed, not read — it overrides the film path above when it
                  resolves. Captures carry no DX packets, and{' '}
                  <span className="num">tools/dx_decode.py</span> has never been validated against a
                  real roll.
                </>
              }
            >
              <input
                className="inp"
                value={next.dx}
                spellCheck={false}
                placeholder="78-13"
                onChange={(e) => setNext((n) => ({ ...n, dx: e.target.value }))}
              />
            </Field>

            {stock ? (
              <span className="quiet" style={{ fontSize: 12 }}>
                {stock.name}
                {stock.iso ? ` · ISO ${stock.iso}` : ''}
              </span>
            ) : null}
          </Grp>

          <Grp>
            <Field
              label="Resolution"
              value="2000 × 3000"
              info={
                <>
                  <b>Base 16 only.</b> The decoder accepts <span className="num">6000</span>-word
                  lines, and the committed calibration was captured at{' '}
                  <span className="num">{cfg?.dpi_base || 'DpiBase16_35'}</span>. Base 4 and 8 need
                  their own dark and gain references and a decoder that handles their line length,
                  so they are not offered rather than offered and refused.
                </>
              }
            >
              {bases.length > 1 ? (
                <Seg
                  ariaLabel="Resolution"
                  value="16"
                  options={bases.map((b) => [String(b), `Base ${b}`])}
                />
              ) : (
                <div className="inp">
                  Base {bases[0]}
                  <span className="sp" />
                  <span className="num" style={{ fontSize: 11, color: 'var(--mute)' }}>
                    {speeds[bases[0]] ?? hw?.calibration?.speed ?? '—'}
                  </span>
                </div>
              )}
            </Field>

            <Field
              label="Transport"
              value={hw?.calibration?.speed ?? '—'}
              info={
                <>
                  Register <span className="num">0xA5</span>, set when a scan starts, and adjustable
                  on the confirm sheet. Base 16 is the <b>slowest</b> of the three — highest
                  resolution, so the film crawls. <span className="num">docs/43</span> has this table
                  inverted; the recovered hive is the ground truth.
                </>
              }
            >
              <div className="inp">
                {hw?.calibration?.speed ?? '—'}
                <span className="sp" />
                <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--mute)' }}>
                  calibrated
                </span>
              </div>
            </Field>
          </Grp>

          {/* Premium colour path and Digital ICE used to sit here as toggles
              that could never move: the Ansel path cannot be switched off, and
              nothing applies ICE to pixels — the decoder takes 6000-word lines
              and a four-channel line is 8000. Neither is a capture setting, so
              neither is a control. Both facts are still reported, by the
              screens that own them: Diagnostics for the colour path
              (`pipeline ≠ Kodak`), docs/54 §2.5 for ICE. */}

          <div className="railfoot">
            {scanning ? (
              <Btn variant="flat big" disabled title="A scan is already running">
                Scanning…
              </Btn>
            ) : blocked ? (
              <>
                {/* Not a disabled Scan button. The reason is on screen and the
                    action is the one that can change it. */}
                <Btn
                  variant={blocked.fix === 'recheck' ? 'primary big' : 'flat big'}
                  disabled={hwBusy || blocked.fix !== 'recheck'}
                  onClick={onRecheckHw}
                >
                  {hwBusy ? 'Checking…' : 'Recheck scanner'}
                </Btn>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                  <span className="quiet" style={{ flex: 1, fontSize: 12 }}>
                    {blocked.title}
                  </span>
                  <Info side="left">{blocked.why}</Info>
                </div>
              </>
            ) : (
              <Btn variant="primary big" onClick={() => setSheet(true)}>
                Scan strip
              </Btn>
            )}
            <Btn variant="flat big" onClick={onOpen}>
              Open capture…
            </Btn>
          </div>
        </Rail>

        {/* ── the strip, or the scan ── */}
        {live ? (
          <Live
            job={scanJob}
            busy={stopping}
            open={autoOpen}
            onOpenAnyway={onOpenScanResult}
            onDismiss={onDismissScan}
            onCancel={() => {
              setStopping(true);
              onCancelScan();
            }}
          />
        ) : (
          <main className="scanstage">
            <div className="stagehead">
              <span className="title">{roll ? roll.name : 'Ready to scan'}</span>
              {blocked ? (
                <Chip tone="warn" dot>
                  {blocked.title}
                </Chip>
              ) : (
                <Chip tone="ok" dot>
                  {hw?.simulated ? 'Simulated scanner' : 'Scanner ready'}
                </Chip>
              )}
              <span className="sp" />
              <span className="quiet">Frames are found in the capture, not framed before it.</span>
            </div>

            <div className="filmwrap">
              <div className="film" role="img" aria-label="The strip as captured">
                <div className="perf t">
                  {PERFS.map((i) => (
                    <i key={i} />
                  ))}
                </div>
                <div className="perf b">
                  {PERFS.map((i) => (
                    <i key={i} />
                  ))}
                </div>
                <div className="frames">
                  {(window6.length ? window6 : PERFS.slice(0, 6)).map((f, i) =>
                    roll ? (
                      <span
                        key={f.index}
                        onClick={() => setSel(f.index)}
                        style={{ cursor: 'pointer' }}
                      >
                        <img
                          src={api.frameUrl(roll.id, f.index, 'thumb', f.version)}
                          alt=""
                          loading="lazy"
                        />
                        <b>{f.index + 1}</b>
                      </span>
                    ) : (
                      <span key={i} className="pending" />
                    ),
                  )}
                </div>
              </div>
            </div>

            <div className="telem">
              <div>
                <span className="lbl">Lines</span>
                <b>{roll ? roll.lines.toLocaleString() : '—'}</b>
              </div>
              <div>
                <span className="lbl">Size</span>
                <b>{api.fmtBytes(sync?.bytes)}</b>
              </div>
              <div>
                <span className="lbl">Sync losses</span>
                <b>{sync ? sync.losses : '—'}</b>
              </div>
              <div>
                <span className="lbl">Clean</span>
                <b>{sync ? `${sync.pct_clean} %` : '—'}</b>
              </div>
              <div>
                <span className="lbl">Frames</span>
                <b>{roll ? roll.frames.length : '—'}</b>
              </div>
            </div>
          </main>
        )}

        {/* ── the machine, always answerable ── */}
        <Rail side="r" aria-label="Machine state">
          {/* No Recheck button during a scan. The child process owns the USB
              handle and no button may take it away, so the rail says who has
              it rather than offering a control that would be refused. */}
          <RailHead title="Machine">
            {scanning ? (
              <span className="quiet" style={{ fontSize: 11 }}>held by the scan</span>
            ) : (
              <Btn
                style={{ height: 24, padding: '0 8px', fontSize: 12 }}
                disabled={hwBusy}
                onClick={onRecheckHw}
              >
                {hwBusy ? 'Checking…' : 'Recheck'}
              </Btn>
            )}
          </RailHead>

          <Grp title="Read now">
            <State rows={machine.read} />
          </Grp>

          <Grp title="Not wired">
            <State rows={machine.unwired} />
          </Grp>

          <Grp title="Calibration reference">
            <State
              rows={[
                ['Dark', cal ? `${cal.dark_source.lines.toLocaleString()} lines` : '—', cal ? 'good' : ''],
                ['Bright', cal ? `${cal.bright_source.lines.toLocaleString()} lines` : '—', cal ? 'good' : ''],
                ['Lamp PWM', cfg?.lamp_pwm_N ?? '—'],
                [
                  'Bright mean',
                  cal ? cal.bright_source.means[1].toFixed(0) : '—',
                  '',
                  <>
                    Deliberately near <span className="num">50 000</span>, not the vendor's{' '}
                    <span className="num">64 000</span> target, so no channel clips.
                  </>,
                ],
                ['Captured', cal?.captured ?? '—'],
              ]}
            />
          </Grp>
        </Rail>
      </div>

      {roll && !live ? (
        <Filmstrip roll={roll} selected={sel} onSelect={setSel}>
          <span className="lbl">This roll</span>
        </Filmstrip>
      ) : null}

      <StartSheet
        open={sheet}
        hw={hw}
        next={{ ...next, stock }}
        onClose={() => setSheet(false)}
        onStart={onStartScan}
      />
    </>
  );
}
