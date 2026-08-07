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
                info={cal.readme?.bright_source?.note}
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

        <Card
          title="New calibration"
          info={
            <>
              Not in this build. Capturing new dark and bright references needs the scanner, and the
              tables committed here were made with it. The vendor regenerates once per session and
              invalidates after 60 minutes or on any change of DPI base, film colour, format or IR
              (docs/46 §7).
            </>
          }
        >
          <State rows={[['Run calibration', 'not implemented', 'na']]} />
        </Card>
      </div>
    </div>
  );
}
