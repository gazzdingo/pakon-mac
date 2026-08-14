// Diagnostics and Calibration.
//
// Technical output lives here, not among the photographs. Everything is a real
// value from this unit and this repo, or is marked as unavailable. Nothing is
// illustrative. Reasoning sits behind <Info>, not in the page body.
import React, { useEffect, useState } from 'react';
import { Chip, Info, State } from './components';
import * as api from './api';

const Card = ({ title, info, children }) => (
  <div className="card">
    <span className="lbl" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      {title}
      {info ? <Info side="left">{info}</Info> : null}
    </span>
    {children}
  </div>
);

export function Diagnostics() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    api.diagnostics().then(setD).catch((e) => setErr(String(e.message || e)));
  }, []);

  if (err)
    return (
      <div className="doc">
        <span className="num" style={{ color: 'var(--danger-ink)' }}>
          {err}
        </span>
      </div>
    );
  if (!d)
    return (
      <div className="doc">
        <span className="quiet">Reading…</span>
      </div>
    );

  return (
    <div className="doc">
      <div className="docwrap">
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <span className="title">Diagnostics</span>
          <span className="sp" />
          <Chip tone="ok">UI = pipeline</Chip>
          <Chip tone="warn" dot>
            pipeline ≠ Kodak
          </Chip>
          <Info side="left">
            <b>Verified:</b> {d.verified.ui_matches_pipeline}
            <br />
            <br />
            <b>Not verified:</b> {d.verified.pipeline_matches_kodak}
          </Info>
        </div>

        {d.rolls.length === 0 ? (
          <Card title="Open rolls">
            <span className="quiet">No roll open. Integrity is computed when a capture is opened.</span>
          </Card>
        ) : (
          d.rolls.map((r) => (
            <Card key={r.id} title={`Capture — ${r.name}`}>
              <div className="cols">
                <State
                  rows={[
                    ['Lines', (r.sync?.lines ?? r.lines).toLocaleString()],
                    ['Sync markers', (r.sync?.markers || 0).toLocaleString()],
                    ['Losses', r.sync?.losses ?? '—', (r.sync?.losses || 0) === 0 ? 'good' : 'bad'],
                    ['Clean', `${r.sync?.pct_clean ?? 0} %`],
                    ['Size', api.fmtBytes(r.sync?.bytes)],
                    ['Frames', r.frames],
                  ]}
                />
                <State
                  rows={[
                    ['Auto offsets', r.auto_offsets.join(' · ')],
                    ['Roll scale', r.roll_scale.join(' · ')],
                    ['Words per line', r.ir?.words_per_line ?? '—'],
                    ['Channels', r.ir?.channels ?? '—'],
                    ['IR plane', r.ir?.has_ir ? 'present' : 'absent', r.ir?.has_ir ? 'good' : 'na'],
                  ]}
                />
              </div>
            </Card>
          ))
        )}

        <Card title="Pipeline">
          <div className="cols">
            <State
              rows={Object.entries(d.pipeline).map(([k, v]) => [
                k.replace(/_/g, ' '),
                typeof v === 'number' ? (Number.isInteger(v) ? v : v.toFixed(4)) : String(v),
              ])}
            />
            <State
              rows={[
                ['Python', d.python],
                ['Render cache', api.fmtBytes(d.cache_bytes)],
              ]}
            />
          </div>
        </Card>

        <Card
          title="Render timing"
          info={
            <>
              Measured on this machine with{' '}
              <span className="num">tools/pakon_render.py check</span> against a{' '}
              <span className="num">694 MB</span> / <span className="num">57 900</span>-line capture
              of <span className="num">47</span> frames. Open is dominated by the per-frame scene
              balance (<span className="num">20 s</span> of it), not by decoding.
            </>
          }
        >
          <State
            rows={[
              ['Open capture', '≈ 26 s'],
              ['Thumb 361×250', '12 ms'],
              ['Preview 720×500', '39 ms'],
              ['Display 1439×1000', '147 ms'],
              ['Full 2878×2000', '630 ms'],
            ]}
          />
        </Card>
      </div>
    </div>
  );
}

/** This scanner's own setup: what is stored, what is being measured, and the
 *  one thing that ever needs a person.
 *
 *  There is no button to start a calibration and that is deliberate. A scanner
 *  the software has never seen sets itself up the moment this screen can see
 *  it, because the only genuinely manual step — "is there film in the gate" —
 *  is something the hardware already reports. See tools/calib_wizard.py for
 *  why the film sensors and the gate classifier are not symmetric signals, and
 *  in particular why "the sensors said nothing" is the *normal* reading for an
 *  empty gate and must not be turned into a question.
 *
 *  The only control here is the one for the case the machine genuinely cannot
 *  resolve on its own: two scanners calibrated on one computer, nothing on the
 *  wire to tell them apart. */
function Setup({ boot }) {
  const setup = boot?.calibration_store?.setup;
  const units = boot?.calibration_store?.units?.units;
  const [job, setJob] = useState(null);
  const started = React.useRef(false);

  const state = job?.state || setup?.state;
  const meta = api.SETUP[state] || {};
  const headline = job?.headline || job?.message || setup?.headline;
  const warnings = [...(setup?.warnings || []), ...(job?.warnings || [])];

  // Start by itself, once, when there is something to do and nobody has to be
  // asked. Calling twice is harmless — the backend refuses a second
  // calibration — but the ref keeps it from happening on every render.
  useEffect(() => {
    if (started.current || !setup?.automatic) return;
    started.current = true;
    api
      .calibrationRun({})
      .then((r) => (r?.id ? api.pollJob(r.id, setJob) : setJob(r)))
      .catch((e) => setJob({ state: 'failed', headline: String(e.message || e) }));
  }, [setup?.automatic]);

  if (!setup) return null;

  const rows = [['Status', meta.label || state || '—', meta.tone || 'na']];
  if (setup.serial != null) rows.push(['Scanner', String(setup.serial), 'good']);
  if (job?.status === 'running') {
    rows.push([job.message || 'Working', job.detail || `${Math.round((job.progress || 0) * 100)}%`, 'info']);
  }
  (setup.steps || []).forEach((st) =>
    rows.push([st.text, st.needed ? 'to do' : 'done', st.needed ? 'na' : 'good']),
  );

  return (
    <Card
      title="This scanner's calibration"
      info={
        <>
          Colour matrices and the serial number come off the scanner's own memory, read exactly once
          because a second read in the same power cycle returns corrupted bytes while still reporting
          success. Everything else — the black level, the lamp duty cycles and the per-pixel dark and
          gain tables — is <em>measured</em>, because none of it is on that memory at any offset. It
          exists only in the Windows registry of a machine that ran the vendor software, so for any
          scanner without one, searching against the scanner's own response is the only way it can
          exist at all. docs/72.
        </>
      }
    >
      {headline ? <p className="muted" style={{ marginBottom: 8 }}>{headline}</p> : null}
      <State rows={rows} />

      {state === 'film-in-gate' ? (
        <p style={{ marginTop: 8 }}>
          <button
            className="btn"
            onClick={() => {
              started.current = false;
              setJob(null);
            }}
          >
            I have taken the film out
          </button>
        </p>
      ) : null}

      {state === 'ambiguous' && units ? (
        <div style={{ marginTop: 8 }}>
          {Object.keys(units).map((srl) => (
            <button
              key={srl}
              className="btn"
              style={{ marginRight: 6 }}
              onClick={() => api.calibrationSelect({ serial: Number(srl) }).then(() => window.location.reload())}
            >
              Scanner {srl}
            </button>
          ))}
        </div>
      ) : null}

      {state === 'unreachable' && job?.report?.unreachable ? (
        <pre className="muted" style={{ whiteSpace: 'pre-wrap', marginTop: 8 }}>
          {job.report.unreachable.reason}
        </pre>
      ) : null}

      {warnings.map((w) => (
        <p key={w} className="muted" style={{ marginTop: 8 }}>
          {w}
        </p>
      ))}
    </Card>
  );
}

export function Calibration({ boot }) {
  const [b, setB] = useState(boot || null);
  useEffect(() => {
    if (!b) api.bootstrap().then(setB).catch(() => {});
  }, [b]);
  const cal = b?.calibration;
  const cfg = cal?.readme?.config;

  return (
    <div className="doc">
      <div className="docwrap">
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <span className="title">Calibration</span>
          <span className="sp" />
          {cal?.present ? <Chip tone="ok">committed</Chip> : <Chip tone="bad" dot>missing</Chip>}
          <Info side="left">
            Per-pixel dark and gain tables are applied to every decode:{' '}
            <span className="num">{cal?.readme?.usage}</span>. They are valid only for the exposure
            triad they were captured at — change one setting and all three must be redone.
          </Info>
        </div>

        {!cal?.present ? (
          <Card title="No tables">
            <span className="quiet">
              calibration/dark_2000x3.npy and gain_2000x3.npy are missing. Decode runs uncalibrated.
            </span>
          </Card>
        ) : (
          <>
            <div className="cols">
              <Card title="Dark reference">
                <State
                  rows={[
                    ['Lines', cal.readme?.dark_source?.lines?.toLocaleString() ?? '—'],
                    ['Losses', cal.readme?.dark_source?.losses ?? '—', 'good'],
                    ['Means R·G·B', (cal.readme?.dark_source?.means || []).join(' · ')],
                    ['Table', api.fmtBytes(cal['dark_2000x3.npy']?.bytes)],
                  ]}
                />
              </Card>
              <Card
                title="Flat field / gain"
                
              >
                <State
                  rows={[
                    ['Lines', cal.readme?.bright_source?.lines?.toLocaleString() ?? '—'],
                    ['Losses', cal.readme?.bright_source?.losses ?? '—', 'good'],
                    ['Means R·G·B', (cal.readme?.bright_source?.means || []).join(' · ')],
                    ['Table', api.fmtBytes(cal['gain_2000x3.npy']?.bytes)],
                  ]}
                />
              </Card>
            </div>

            <Card title="Valid for">
              <div className="cols">
                <State
                  rows={[
                    ['DPI base', cfg?.dpi_base],
                    ['Integration 0x82', cfg?.integration_0x82_idx6],
                    ['Lamp PWM', cfg?.lamp_pwm_N],
                    ['Line rate 0x91', cfg?.line_rate_0x91],
                    ['FPGA control', cfg?.fpga_ctrl],
                  ]}
                />
                <State
                  rows={[
                    ['Levels R·G·B·Ir', (cfg?.levels_R_G_B_Ir || []).join(' · ')],
                    ['LED on-counts', (cfg?.on_counts_R_G_B || []).join(' · ')],
                    ['AFE gains', (cfg?.afe_gains || []).join(' · ')],
                    ['AFE offsets', (cfg?.afe_offsets || []).join(' · ')],
                    ['Pixel offset / height', `${cfg?.pixel_offset} / ${cfg?.pixel_height}`],
                  ]}
                />
              </div>
            </Card>
          </>
        )}

        <Card
          title="Vendor colour data"
          info={
            <>
              <span className="num" style={{ wordBreak: 'break-all' }}>{b?.vendor_data?.data_dir}</span>
              <br />
              <br />
              <span className="num" style={{ wordBreak: 'break-all' }}>{b?.vendor_data?.ansel_root}</span>
            </>
          }
        >
          <State
            rows={[
              [
                'ColorCorrection',
                b?.vendor_data?.data_dir_ok ? 'found' : 'missing',
                b?.vendor_data?.data_dir_ok ? 'good' : 'bad',
              ],
              [
                'Ansel dataPathItems',
                b?.vendor_data?.ansel_root_ok ? 'found' : 'missing',
                b?.vendor_data?.ansel_root_ok ? 'good' : 'bad',
              ],
            ]}
          />
        </Card>

        <Setup boot={b} />
      </div>
    </div>
  );
}
