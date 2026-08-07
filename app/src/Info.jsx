// Diagnostics, Calibration and Scan.
//
// Technical output lives here, not among the photographs. Everything shown is
// a real value from this unit and this repo, or is explicitly marked as not
// yet available. Nothing here is illustrative.
import React, { useEffect, useState } from 'react';
import { Alert, Chip, Switch } from '@heroui/react';
import { KV, Plain, Rail, Section, StatusLine } from './components';
import * as api from './api';

function Card({ title, children, tone }) {
  return (
    <div className="border p-4" style={{ borderColor: tone || 'var(--rule)', background: 'var(--plate)' }}>
      <h3 className="text-[10px] tracking-[0.14em] uppercase font-semibold mb-3" style={{ color: 'var(--mute)' }}>
        {title}
      </h3>
      {children}
    </div>
  );
}

export function Diagnostics() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    api.diagnostics().then(setD).catch((e) => setErr(String(e.message || e)));
  }, []);

  if (err) return <div className="p-6 num text-[12px]" style={{ color: 'var(--halt)' }}>{err}</div>;
  if (!d) return <div className="p-6 text-[12px]" style={{ color: 'var(--mute)' }}>Reading…</div>;

  return (
    <div className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--void)' }}>
      <div className="max-w-[980px] mx-auto flex flex-col gap-4">
        <div>
          <div className="ledger text-[22px] mb-1">Diagnostics</div>
          <p className="text-[13px]" style={{ color: 'var(--mute)' }}>
            Capture integrity and pipeline facts for the rolls currently open.
          </p>
        </div>

        <Alert.Root color="warning" className="rounded-none">
          <Alert.Content>
            <Alert.Title className="text-[12px]">What is and is not verified</Alert.Title>
            <Alert.Description className="text-[11px] leading-relaxed">
              <b>Verified:</b> {d.verified.ui_matches_pipeline}
              <br />
              <b>Not verified:</b> {d.verified.pipeline_matches_kodak}
            </Alert.Description>
          </Alert.Content>
        </Alert.Root>

        {d.rolls.length === 0 ? (
          <Card title="Open rolls">
            <p className="text-[12px]" style={{ color: 'var(--mute)' }}>
              No roll open. Capture integrity is computed when a capture is opened.
            </p>
          </Card>
        ) : (
          d.rolls.map((r) => {
            const clean = (r.sync?.losses || 0) === 0;
            return (
              <Card key={r.id} title={`Capture integrity — ${r.name}`}>
                <div className="grid md:grid-cols-2 gap-6">
                  <KV
                    rows={[
                      ['Lines segmented', (r.sync?.lines ?? r.lines).toLocaleString()],
                      ['Sync markers', (r.sync?.markers || 0).toLocaleString()],
                      ['Losses', r.sync?.losses ?? '—'],
                      ['Clean', `${r.sync?.pct_clean ?? 0} %`],
                      ['Capture size', api.fmtBytes(r.sync?.bytes)],
                      ['Frames detected', r.frames],
                    ]}
                  />
                  <KV
                    rows={[
                      ['Auto offsets (RPD)', r.auto_offsets.join(' · ')],
                      ['Ansel roll scale', r.roll_scale.join(' · ')],
                      ['Words per line', r.ir?.words_per_line ?? '—'],
                      ['Channels', r.ir?.channels ?? '—'],
                      ['IR plane', r.ir?.has_ir ? 'present' : 'absent'],
                    ]}
                  />
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <Chip.Root color={clean ? 'success' : 'danger'} variant="bordered" className="rounded-none">
                    <Chip.Label className="text-[10px] tracking-[0.1em] uppercase">
                      {clean ? 'lossless capture' : `${r.sync.losses} lines lost`}
                    </Chip.Label>
                  </Chip.Root>
                  {!clean ? (
                    <span className="text-[11px]" style={{ color: 'var(--mute)' }}>
                      Short sync gaps were skipped so a bad line cannot shear the strip (docs/45).
                    </span>
                  ) : null}
                </div>
              </Card>
            );
          })
        )}

        <Card title="Pipeline constants">
          <KV
            rows={Object.entries(d.pipeline).map(([k, v]) => [
              k.replace(/_/g, ' '),
              typeof v === 'number' ? (Number.isInteger(v) ? v : v.toFixed(4)) : String(v),
            ])}
          />
        </Card>

        <Card title="Host">
          <KV
            rows={[
              ['Python', d.python],
              ['Render cache', api.fmtBytes(d.cache_bytes)],
            ]}
          />
        </Card>
      </div>
    </div>
  );
}

export function Calibration() {
  const [b, setB] = useState(null);
  useEffect(() => {
    api.bootstrap().then(setB).catch(() => {});
  }, []);
  const cal = b?.calibration;
  const cfg = cal?.readme?.config;

  return (
    <div className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--void)' }}>
      <div className="max-w-[980px] mx-auto flex flex-col gap-4">
        <div>
          <div className="ledger text-[22px] mb-1">Calibration</div>
          <p className="text-[13px]" style={{ color: 'var(--mute)' }}>
            Per-pixel dark and gain tables are applied to every decode. They are valid only for the
            exposure triad they were captured at — change one setting and all three must be redone.
          </p>
        </div>

        {!cal?.present ? (
          <Alert.Root color="danger" className="rounded-none">
            <Alert.Content>
              <Alert.Title>No calibration tables</Alert.Title>
              <Alert.Description>
                calibration/dark_2000x3.npy and gain_2000x3.npy are missing. Decode will run
                uncalibrated and column PRNU plus lamp falloff will dominate the image.
              </Alert.Description>
            </Alert.Content>
          </Alert.Root>
        ) : (
          <>
            <div className="grid md:grid-cols-2 gap-4">
              <Card title="Dark reference" tone="var(--rule)">
                <KV
                  rows={[
                    ['State', 'committed'],
                    ['Lines', cal.readme?.dark_source?.lines?.toLocaleString() ?? '—'],
                    ['Losses', cal.readme?.dark_source?.losses ?? '—'],
                    ['Means R·G·B', (cal.readme?.dark_source?.means || []).join(' · ')],
                    ['Table', api.fmtBytes(cal['dark_2000x3.npy']?.bytes)],
                  ]}
                />
              </Card>
              <Card title="Flat field / gain" tone="var(--rule)">
                <KV
                  rows={[
                    ['State', 'committed'],
                    ['Lines', cal.readme?.bright_source?.lines?.toLocaleString() ?? '—'],
                    ['Losses', cal.readme?.bright_source?.losses ?? '—'],
                    ['Means R·G·B', (cal.readme?.bright_source?.means || []).join(' · ')],
                    ['Table', api.fmtBytes(cal['gain_2000x3.npy']?.bytes)],
                  ]}
                />
              </Card>
            </div>

            <Card title="Configuration these tables are valid for">
              <div className="grid md:grid-cols-2 gap-6">
                <KV
                  rows={[
                    ['DPI base', cfg?.dpi_base],
                    ['Integration (0x82 idx6)', cfg?.integration_0x82_idx6],
                    ['Lamp PWM N', cfg?.lamp_pwm_N],
                    ['Line rate (0x91)', cfg?.line_rate_0x91],
                    ['FPGA control', cfg?.fpga_ctrl],
                  ]}
                />
                <KV
                  rows={[
                    ['Levels R·G·B·Ir', (cfg?.levels_R_G_B_Ir || []).join(' · ')],
                    ['LED on-counts', (cfg?.on_counts_R_G_B || []).join(' · ')],
                    ['AFE gains', (cfg?.afe_gains || []).join(' · ')],
                    ['AFE offsets', (cfg?.afe_offsets || []).join(' · ')],
                    ['Pixel offset / height', `${cfg?.pixel_offset} / ${cfg?.pixel_height}`],
                  ]}
                />
              </div>
              <p className="text-[11px] mt-3" style={{ color: 'var(--mute)' }}>
                {cal.readme?.usage} — {cal.readme?.bright_source?.note}
              </p>
            </Card>
          </>
        )}

        <Card title="Vendor colour data">
          <KV
            rows={[
              ['ColorCorrection', b?.vendor_data?.data_dir_ok ? 'found' : 'MISSING'],
              ['Ansel dataPathItems', b?.vendor_data?.ansel_root_ok ? 'found' : 'MISSING'],
            ]}
          />
          <p className="num text-[10px] mt-2 break-all" style={{ color: 'var(--mute)' }}>
            {b?.vendor_data?.data_dir}
            <br />
            {b?.vendor_data?.ansel_root}
          </p>
        </Card>

        <Alert.Root color="warning" className="rounded-none">
          <Alert.Content>
            <Alert.Title className="text-[12px]">Running a new calibration</Alert.Title>
            <Alert.Description className="text-[11px]">
              Not in this pass. Capturing new dark and bright references needs the scanner, and the
              tables committed here were made with it. The vendor regenerates once per session and
              invalidates after 60 minutes or on any change of DPI base, film colour, format or IR
              (docs/46 §7).
            </Alert.Description>
          </Alert.Content>
        </Alert.Root>
      </div>
    </div>
  );
}

export function Scan() {
  const [ir, setIr] = useState(false);
  return (
    <div className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--void)' }}>
      <div className="max-w-[880px] mx-auto flex flex-col gap-4">
        <div>
          <div className="ledger text-[22px] mb-1">Scan</div>
          <p className="text-[13px]" style={{ color: 'var(--mute)' }}>
            Capturing from the scanner is not wired up in this pass. Review, Frame and Export work
            entirely on existing captures and were built first, as agreed.
          </p>
        </div>

        <Alert.Root color="warning" className="rounded-none">
          <Alert.Content>
            <Alert.Title className="text-[12px]">Not implemented yet</Alert.Title>
            <Alert.Description className="text-[11px] leading-relaxed">
              The capture path exists and is proven — <span className="num">tools/pakon_session.py</span>{' '}
              reads EP 0x86 at 11.6 MB/s with zero losses, provided the FIFO is not reset inside the
              read loop (docs/45). Wiring it to this screen, with the live line count, throughput and
              sync-loss meters from the mockup, is the next piece of work.
            </Alert.Description>
          </Alert.Content>
        </Alert.Root>

        <Card title="Digital ICE / infrared cleaning">
          <div className="flex items-start gap-4">
            <Switch.Root isSelected={ir} onChange={setIr} isDisabled>
              <Switch.Control>
                <Switch.Thumb />
              </Switch.Control>
            </Switch.Root>
            <div className="flex-1">
              <div className="text-[12px] mb-1">Capture the infrared plane</div>
              <p className="text-[11px]" style={{ color: 'var(--mute)' }}>
                The hardware supports it — this unit has a calibrated{' '}
                <span className="num">Current_Ir = 4</span> and{' '}
                <span className="num">DutyCycle_Ir = 0.887</span>, and the AFE allows{' '}
                <span className="num">Ir ≤ 8</span> when enabled. A four-channel line is{' '}
                <span className="num">3n</span> interleaved RGB words followed by{' '}
                <span className="num">n</span> IR words, so the line length becomes{' '}
                <span className="num">8000</span> rather than <span className="num">6000</span>.
                <br />
                <br />
                It is <b>untested</b>: no IR capture exists yet and the decode path currently accepts
                6000-word lines only. The control is shown because the option is real, and disabled
                because nothing behind it has been exercised. Opening a capture reports its true
                channel count in Diagnostics.
              </p>
            </div>
          </div>
        </Card>

        <Card title="Capture settings the mockup shows">
          <p className="text-[11px]" style={{ color: 'var(--mute)' }}>
            DX detection with override, resolution base, and "scan again, same settings" (⇧⌘S) all
            belong here. Film selection already exists in the open-capture flow, because a{' '}
            <span className="num">.bin</span> carries no DX and the decode path refuses to assume
            one.
          </p>
        </Card>
      </div>
    </div>
  );
}
