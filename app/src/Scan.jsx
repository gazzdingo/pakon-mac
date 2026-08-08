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
  State,
  Toggle,
} from './components';
import * as api from './api';

const PERFS = Array.from({ length: 48 }, (_, i) => i);

/* ── why Scan strip cannot run, in the order the user would hit them ────── */

function blockedReason(hw, scanJob) {
  if (!hw) return ['Checking', 'The machine has not been probed yet.'];
  if (scanJob?.status === 'running') return ['Scanning', 'A scan is already running.'];
  if (!hw.present) return ['No scanner', 'Nothing at 0f05:f135 on USB.'];
  if (hw.state === 'needs_firmware')
    return ['No firmware', 'Load it with tools/pakon_load.py.'];
  if (hw.writes_locked)
    return ['Writes locked', 'tools/WRITES_LOCKED refuses every register write. Lifting it is a deliberate act, and its own file says so.'];
  if (!hw.calibration)
    return ['No calibration', 'calibration/README.json is the only record of the exposure the dark and gain tables are valid for.'];
  if (hw.state !== 'ready') return ['Not answering', hw.hint || ''];
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

function Live({ job, onCancel, busy }) {
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
          <div style={{ maxWidth: '56ch', textAlign: 'center' }}>
            <p className="quiet">{job.detail || ''}</p>
            {job.transport_stopped === false ? (
              <p style={{ color: 'var(--danger-ink)', fontSize: 13, marginTop: 8 }}>
                The transport stop was not acknowledged. Power the scanner off.
              </p>
            ) : null}
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

function StartSheet({ open, hw, onClose, onStart }) {
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
  scanJob,
  onOpen,
  onStartScan,
  onCancelScan,
}) {
  const cal = boot?.calibration?.readme;
  const cfg = cal?.config;
  const sync = roll?.sync;
  const [sheet, setSheet] = React.useState(false);
  const [stopping, setStopping] = React.useState(false);
  const blocked = blockedReason(hw, scanJob);
  const live = scanJob && (scanJob.status === 'running' || scanJob.kind === 'scan');

  React.useEffect(() => {
    if (scanJob?.status !== 'running') setStopping(false);
  }, [scanJob?.status]);

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
                  No default. A capture carries no DX packets, so the stock is stated by hand and the
                  decode path refuses to assume colour negative.
                </>
              }
            >
              <Seg
                ariaLabel="Film path"
                value={roll?.film_path || 'ColNeg'}
                options={[
                  ['ColNeg', 'Colour neg'],
                  ['BnW', 'B&W'],
                  ['POSITIVE', 'Positive'],
                ]}
                onChange={() => onOpen()}
              />
            </Field>

            <Field
              label="DX"
              info={
                <>
                  Typed, not read. Captures carry no DX packets, and{' '}
                  <span className="num">tools/dx_decode.py</span> has never been validated against a
                  real roll.
                </>
              }
            >
              <div className="inp">
                {roll?.dx || '—'}
                <span className="sp" />
                <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--mute)' }}>
                  {roll?.stock?.name || roll?.film_path || 'not set'}
                </span>
              </div>
            </Field>
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
                  their own dark and gain references and a decoder that handles their line length.
                </>
              }
            >
              <Seg
                ariaLabel="Resolution"
                value="16"
                options={[
                  ['4', 'Base 4', true],
                  ['8', 'Base 8', true],
                  ['16', 'Base 16'],
                ]}
              />
            </Field>

            <Field
              label="Transport"
              value={hw?.calibration?.speed ?? '—'}
              info={
                <>
                  Register <span className="num">0xA5</span>, set when a scan starts. Base 16 is the{' '}
                  <b>slowest</b> of the three — highest resolution, so the film crawls.{' '}
                  <span className="num">docs/43</span> has this table inverted; the recovered hive is
                  the ground truth.
                </>
              }
            >
              <Seg
                ariaLabel="Transport speed"
                value="16"
                options={[
                  ['4', '25802', true],
                  ['8', '11467', true],
                  ['16', '5917'],
                ]}
              />
            </Field>

            <Toggle
              on
              disabled
              info={
                <>
                  The Ansel preference path. It is a <b>stand-in</b> —{' '}
                  <span className="num">SETSHIFTS_12_PORTED = False</span> — so its tone is not yet
                  Kodak's, and it cannot be switched off from here.
                </>
              }
            >
              Premium colour path
            </Toggle>

            <Toggle
              on={false}
              disabled
              info={
                <>
                  Calibrated on this unit — <span className="num">Ir 4</span>, duty{' '}
                  <span className="num">0.887</span>, clamp <span className="num">≤ 8</span> — and
                  never run. A four-channel line is <span className="num">8000</span> words; the
                  decoder takes <span className="num">6000</span>.
                </>
              }
            >
              Digital ICE
            </Toggle>
          </Grp>

          <div className="railfoot">
            {blocked ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Btn variant="flat big" disabled style={{ flex: 1 }}>
                  Scan strip
                </Btn>
                <Info side="left">
                  <b>{blocked[0]}.</b> {blocked[1]}
                </Info>
              </div>
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
            onCancel={() => {
              setStopping(true);
              onCancelScan();
            }}
          />
        ) : (
          <main className="scanstage">
            <div className="stagehead">
              <span className="title">{roll ? roll.name : 'No roll open'}</span>
              {hw?.state === 'ready' && !hw?.writes_locked ? (
                <Chip tone="ok" dot>
                  Scanner ready
                </Chip>
              ) : (
                <Chip tone="warn" dot>
                  {blocked ? blocked[0] : 'Scanner'}
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
          <RailHead title="Machine" />

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
        onClose={() => setSheet(false)}
        onStart={onStartScan}
      />
    </>
  );
}
