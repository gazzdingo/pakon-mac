// Export — the only moment files are written.
//
// Each frame renders once at full quality from the capture and its settings,
// writes its file, then frees memory. Bit depth is honest: see DEPTH_NOTE.
import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Chip, ProgressBar } from '@heroui/react';
import { KV, Plain, Rail, Section, StatusLine } from './components';
import * as api from './api';

const FORMATS = [
  ['tiff', 'TIFF', 'archival'],
  ['png', 'PNG', 'lossless'],
  ['jpeg', 'JPEG', 'share'],
];

const COLOURS = [
  ['srgb', 'sRGB', 'display-ready, 8-bit'],
  ['linear', 'Linear', 'scanner RPD, 16-bit'],
];

// Why there is no "16-bit sRGB": AnselEngine.to_srgb calls rpd12_to_icc_u8
// and runs the ICC transform on 8-bit RGB, so its output *is* 8-bit. Writing
// it into a 16-bit container would advertise depth that does not exist.
const DEPTH_NOTE =
  'The sRGB path ends in an 8-bit ICC transform, so sRGB exports are 8-bit — ' +
  'padding them into a 16-bit file would claim precision the pipeline does ' +
  'not produce. Linear (scanner RPD) is genuinely 16-bit end to end and is ' +
  "the vendor's 'Save As Raw' escape hatch.";

function Seg({ options, value, onChange }) {
  return (
    <div className="grid gap-[6px]" style={{ gridTemplateColumns: `repeat(${options.length},1fr)` }}>
      {options.map(([id, label, sub]) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          className="border px-2 py-[7px] text-left gate"
          style={{
            borderColor: value === id ? 'var(--ink)' : 'var(--rule)',
            background: value === id ? 'var(--plate2)' : 'transparent',
          }}
        >
          <span className="block text-[11px] tracking-[0.1em] uppercase">{label}</span>
          <small className="block text-[10px]" style={{ color: 'var(--mute)' }}>
            {sub}
          </small>
        </button>
      ))}
    </div>
  );
}

export default function Export({ roll, setRoll, onGoReview }) {
  const [format, setFormat] = useState('tiff');
  const [colour, setColour] = useState('linear');
  const [template, setTemplate] = useState('{roll}_{frame:02}_{stock}');
  const [dest, setDest] = useState('~/Pictures/Film');
  const [subfolder, setSubfolder] = useState(true);
  const [job, setJob] = useState(null);
  const [running, setRunning] = useState(false);

  const queue = useMemo(
    () => (roll ? roll.frames.filter((f) => !f.params?.rejected) : []),
    [roll],
  );
  const skipped = roll ? roll.frames.length - queue.length : 0;

  const effectiveFormat = colour === 'linear' ? 'tiff' : format;
  const ext = { tiff: 'tif', jpeg: 'jpg', png: 'png' }[effectiveFormat];

  const previewName = useMemo(() => {
    if (!roll) return '';
    const stock = (roll.stock?.name || 'film').toLowerCase().replace(/[^a-z0-9]/g, '');
    return (
      template
        .replace('{roll}', roll.name.replace(/\s+/g, ''))
        .replace(/\{frame:02\}/, '01')
        .replace('{frame}', '1')
        .replace('{stock}', stock)
        .replace('{date}', new Date().toISOString().slice(0, 10))
        .replace('{iso}', roll.stock?.iso ?? '')
        .replace('{count}', roll.frames.length) + `.${ext}`
    );
  }, [template, roll, ext]);

  const results = job?.results || [];
  const done = results.filter((r) => r.status === 'written').length;

  async function run() {
    setRunning(true);
    setJob(null);
    try {
      const { id } = await api.exportRoll({
        roll: roll.id,
        frames: queue.map((f) => f.index),
        format: effectiveFormat,
        colour,
        template,
        dest,
        subfolder,
      });
      const final = await api.pollJob(id, setJob, 350);
      setJob(final);
      setRoll(await api.roll(roll.id));
    } catch (e) {
      setJob({ status: 'error', error: String(e.message || e) });
    } finally {
      setRunning(false);
    }
  }

  if (!roll) {
    return (
      <div className="flex flex-1 items-center justify-center" style={{ background: 'var(--void)' }}>
        <div className="text-center">
          <div className="ledger text-[22px] mb-2">Nothing to export</div>
          <p className="text-[13px]" style={{ color: 'var(--mute)' }}>
            Open a capture in Review first.
          </p>
        </div>
      </div>
    );
  }

  const statusOf = (f) => {
    const r = results.find((x) => x.frame === f.index);
    if (r?.status === 'written') return ['● written', 'var(--pass)'];
    if (r?.status === 'error') return [`× ${r.error?.slice(0, 30)}`, 'var(--halt)'];
    if (job?.current === f.index && running) return ['◐ rendering', 'var(--filament)'];
    if (f.params?.rejected) return ['× skipped', 'var(--mute)'];
    return ['○ queued', 'var(--mute)'];
  };

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="flex flex-1 min-h-0">
        <Rail>
          <Section title="This export">
            <KV
              rows={[
                ['Frames queued', queue.length],
                ['Skipped (rejected)', skipped],
                ['Done', done],
                ['Format', `${effectiveFormat.toUpperCase()} ${colour === 'linear' ? '16-bit' : '8-bit'}`],
              ]}
            />
          </Section>
          <Section title="Where files go">
            <p className="text-[11px]" style={{ color: 'var(--mute)' }}>
              Exports are the only files this app leaves on disk. The workspace (raw captures,
              render cache) is cleared when you quit.
            </p>
            {job?.dest ? (
              <Plain className="mt-2" onPress={() => window.pakon?.openPath(job.dest)}>
                Reveal destination
              </Plain>
            ) : null}
          </Section>
        </Rail>

        <main className="flex-1 min-w-0 flex flex-col" style={{ background: 'var(--void)' }}>
          <div className="flex items-baseline gap-[14px] px-5 pt-3 pb-2">
            <span className="ledger text-[19px]">{roll.name}</span>
            <span className="lbl" style={{ color: running ? 'var(--filament)' : 'var(--ink)' }}>
              {running ? `Exporting — ${done} of ${queue.length}` : `${queue.length} frames ready`}
            </span>
            <span className="text-[12px] ml-auto" style={{ color: 'var(--mute)' }}>
              full-quality render per frame · capture + settings → file
            </span>
          </div>

          {job?.status === 'error' ? (
            <div className="px-5 pb-2">
              <Alert.Root color="danger" className="rounded-none">
                <Alert.Content>
                  <Alert.Title>Export failed</Alert.Title>
                  <Alert.Description className="num text-[11px]">{job.error}</Alert.Description>
                </Alert.Content>
              </Alert.Root>
            </div>
          ) : null}

          {running ? (
            <div className="px-5 pb-2">
              <ProgressBar.Root value={(job?.progress || 0) * 100} className="w-full">
                <ProgressBar.Track className="h-[3px] rounded-none" style={{ background: 'var(--rule)' }}>
                  <ProgressBar.Fill className="rounded-none" style={{ background: 'var(--filament)' }} />
                </ProgressBar.Track>
              </ProgressBar.Root>
            </div>
          ) : null}

          <div className="flex-1 overflow-y-auto px-5 pb-4">
            <table className="w-full text-[12px] border-collapse">
              <thead>
                <tr className="lbl">
                  {['', 'Frame', 'File name', 'Adjustments', 'Size', 'Status'].map((h, i) => (
                    <th
                      key={h + i}
                      className="text-left font-semibold py-[6px] border-b"
                      style={{ borderColor: 'var(--rule)' }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {roll.frames.map((f) => {
                  const [label, colr] = statusOf(f);
                  const r = results.find((x) => x.frame === f.index);
                  const rej = f.params?.rejected;
                  return (
                    <tr
                      key={f.index}
                      className="border-b"
                      style={{ borderColor: '#1c1c1c', opacity: rej ? 0.5 : 1 }}
                    >
                      <td className="py-[6px] w-[44px]">
                        <img
                          src={api.frameUrl(roll.id, f.index, 'thumb', f.version)}
                          alt=""
                          loading="lazy"
                          className="w-[38px] h-[26px] object-cover border"
                          style={{ borderColor: 'var(--rule)' }}
                        />
                      </td>
                      <td className="num">{f.index + 1}</td>
                      <td className="num" style={{ textDecoration: rej ? 'line-through' : 'none' }}>
                        {rej ? 'rejected in review' : r?.path?.split('/').pop() || previewName.replace('01', String(f.index + 1).padStart(2, '0'))}
                      </td>
                      <td className="num" style={{ color: f.adjusted ? 'var(--ink)' : 'var(--mute)' }}>
                        {f.summary}
                      </td>
                      <td className="num">{r?.bytes ? api.fmtBytes(r.bytes) : '—'}</td>
                      <td className="num" style={{ color: colr }}>
                        {label}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </main>

        <Rail side="right" width={320}>
          <Section title="Colour">
            <Seg options={COLOURS} value={colour} onChange={setColour} />
            <p className="text-[11px] mt-2" style={{ color: 'var(--mute)' }}>
              {DEPTH_NOTE}
            </p>
          </Section>

          <Section title="Format">
            <Seg
              options={colour === 'linear' ? [['tiff', 'TIFF', '16-bit RPD']] : FORMATS}
              value={effectiveFormat}
              onChange={setFormat}
            />
            {colour === 'linear' ? (
              <p className="text-[11px] mt-2" style={{ color: 'var(--mute)' }}>
                Linear writes 16-bit TIFF only. Per-frame steps are not baked in — this file is
                deliberately the data before display correction.
              </p>
            ) : null}
          </Section>

          <Section title="Naming">
            <input
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              spellCheck={false}
              className="w-full px-2 py-[7px] text-[12px] num border outline-none"
              style={{ background: 'var(--void)', borderColor: 'var(--rule)', color: 'var(--ink)' }}
            />
            <div className="flex flex-wrap gap-1 mt-2">
              {['{roll}', '{frame:02}', '{stock}', '{date}', '{iso}', '{count}'].map((t) => (
                <button
                  key={t}
                  onClick={() => setTemplate((s) => s + t)}
                  className="num text-[10px] px-[5px] py-[2px] border gate"
                  style={{ borderColor: 'var(--rule)', color: 'var(--mute)' }}
                >
                  {t}
                </button>
              ))}
            </div>
            <div className="num text-[11px] mt-2 filament">→ {previewName}</div>
          </Section>

          <Section title="Destination">
            <input
              value={dest}
              onChange={(e) => setDest(e.target.value)}
              spellCheck={false}
              className="w-full px-2 py-[7px] text-[12px] num border outline-none mb-2"
              style={{ background: 'var(--void)', borderColor: 'var(--rule)', color: 'var(--ink)' }}
            />
            <Plain
              className="mb-2"
              onPress={async () => {
                const d = await window.pakon?.chooseFolder(dest);
                if (d) setDest(d);
              }}
            >
              Choose folder…
            </Plain>
            <label className="flex gap-2 items-center text-[12px]">
              <input type="checkbox" checked={subfolder} onChange={(e) => setSubfolder(e.target.checked)} />
              Subfolder per roll
            </label>
          </Section>

          <Section grow>
            <Plain className="mb-[6px]" isDisabled={running || !queue.length} onPress={run}>
              {running ? 'Exporting…' : `Export ${queue.length} frames`}
            </Plain>
            <Plain onPress={onGoReview}>← Back to review</Plain>
            <p className="text-[11px] mt-2" style={{ color: 'var(--mute)' }}>
              Each frame renders once at full quality from the capture and your settings, writes its
              file, then frees memory.
            </p>
          </Section>
        </Rail>
      </div>

      <StatusLine left={running ? 'EXPORTING' : 'EXPORT'}>
        <span>
          {job?.message || `${queue.length} queued · ${skipped} skipped`}
        </span>
        <span style={{ marginLeft: 'auto' }}>
          {results.length
            ? `${api.fmtBytes(results.reduce((a, r) => a + (r.bytes || 0), 0))} written`
            : 'nothing written yet'}
        </span>
      </StatusLine>
    </div>
  );
}
