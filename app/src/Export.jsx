// Export — the only moment files are written.
//
// Same Console furniture: settings rail left, the queue in the middle, the
// output options right, the roll along the floor. Each frame renders once at
// full quality (measured: 630 ms for 2878x2000) from the capture and its
// settings, writes its file, then frees memory.
import React, { useEffect, useMemo, useState } from 'react';
import { Btn, Chip, Field, Filmstrip, Grp, Info, Rail, RailHead, Seg, State } from './components';
import * as api from './api';

const FORMATS = [
  ['tiff', 'TIFF'],
  ['png', 'PNG'],
  ['jpeg', 'JPEG'],
];

export default function Export({ roll, setRoll, sel, setSel, onJob, onGoReview }) {
  const [format, setFormat] = useState('tiff');
  const [colour, setColour] = useState('linear');
  const [template, setTemplate] = useState('{roll}_{frame:02}_{stock}');
  const [dest, setDest] = useState('~/Pictures/Film');
  const [subfolder, setSubfolder] = useState(true);
  const [job, setJob] = useState(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    onJob?.(running || job?.status === 'done' ? job : null);
  }, [job, running, onJob]);

  const queue = useMemo(() => (roll ? roll.frames.filter((f) => !f.params?.rejected) : []), [roll]);
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
  const written = results.reduce((a, r) => a + (r.bytes || 0), 0);

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
      <div className="body" style={{ gridTemplateColumns: 'minmax(0,1fr)' }}>
        <div className="stage" style={{ flexDirection: 'column', gap: 12 }}>
          <span className="title">Nothing to export</span>
          <span className="quiet">Open a capture first.</span>
        </div>
      </div>
    );
  }

  const statusOf = (f) => {
    const r = results.find((x) => x.frame === f.index);
    if (r?.status === 'written') return ['written', 'var(--ok-ink)'];
    if (r?.status === 'error') return [r.error?.slice(0, 28) || 'error', 'var(--danger-ink)'];
    if (job?.current === f.index && running) return ['rendering', 'var(--warn-ink)'];
    if (f.params?.rejected) return ['skipped', 'var(--faint)'];
    return ['queued', 'var(--faint)'];
  };

  return (
    <>
      <div className="body" style={{ gridTemplateColumns: '280px minmax(0,1fr) 320px' }}>
        <Rail side="l" aria-label="Export summary">
          <RailHead title="This export" />
          <Grp>
            <State
              rows={[
                ['Queued', queue.length],
                ['Skipped', skipped],
                ['Written', done, done ? 'good' : ''],
                ['On disk', api.fmtBytes(written)],
                ['Depth', colour === 'linear' ? '16-bit' : '8-bit'],
              ]}
            />
          </Grp>
          <Grp title="Destination">
            <input className="inp" value={dest} onChange={(e) => setDest(e.target.value)} spellCheck={false} />
            <Btn
              variant="flat"
              onClick={async () => {
                const d = await window.pakon?.chooseFolder(dest);
                if (d) setDest(d);
              }}
            >
              Choose folder…
            </Btn>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12.5 }}>
              <input type="checkbox" checked={subfolder} onChange={(e) => setSubfolder(e.target.checked)} />
              Subfolder per roll
            </label>
            {job?.dest ? (
              <Btn variant="flat" onClick={() => window.pakon?.openPath(job.dest)}>
                Reveal
              </Btn>
            ) : null}
          </Grp>
          <div className="railfoot">
            <Btn variant="flat big" style={{ height: 34 }} onClick={onGoReview}>
              ← Review
            </Btn>
          </div>
        </Rail>

        <div className="centre">
          <div className="actbar">
            <span className="title">{roll.name}</span>
            <span className="quiet">
              <span className="num" style={{ fontSize: 12 }}>{queue.length}</span> frames
            </span>
            <span className="sp" />
            {job?.status === 'error' ? <Chip tone="bad" dot>{job.error?.slice(0, 60)}</Chip> : null}
            {done ? <Chip tone="ok">{done} written</Chip> : null}
          </div>

          <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', background: 'var(--background)', padding: '10px 16px 16px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
              <thead>
                <tr>
                  {['', 'Frame', 'File', 'Adjustments', 'Size', 'Status'].map((h, i) => (
                    <th
                      key={h + i}
                      className="lbl"
                      style={{ textAlign: 'left', padding: '6px 8px 6px 0', borderBottom: '1px solid var(--divider)' }}
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
                      onClick={() => setSel(f.index)}
                      style={{ borderBottom: '1px solid var(--soft)', opacity: rej ? 0.45 : 1, cursor: 'pointer' }}
                    >
                      <td style={{ padding: '5px 8px 5px 0', width: 48 }}>
                        <img
                          src={api.frameUrl(roll.id, f.index, 'thumb', f.version)}
                          alt=""
                          loading="lazy"
                          style={{ width: 40, height: 27, objectFit: 'cover', borderRadius: 2, display: 'block' }}
                        />
                      </td>
                      <td className="num" style={{ padding: '5px 8px 5px 0' }}>{f.index + 1}</td>
                      <td className="num" style={{ padding: '5px 8px 5px 0', textDecoration: rej ? 'line-through' : 'none' }}>
                        {rej
                          ? 'rejected'
                          : r?.path?.split('/').pop() ||
                            previewName.replace('01', String(f.index + 1).padStart(2, '0'))}
                      </td>
                      <td className="num" style={{ padding: '5px 8px 5px 0', color: f.adjusted ? 'var(--foreground)' : 'var(--faint)' }}>
                        {f.summary}
                      </td>
                      <td className="num" style={{ padding: '5px 8px 5px 0' }}>{r?.bytes ? api.fmtBytes(r.bytes) : '—'}</td>
                      <td className="num" style={{ padding: '5px 0', color: colr }}>{label}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <Rail side="r" aria-label="Output">
          <RailHead title="Output" />
          <Grp>
            <Field
              label="Colour"
              info={
                <>
                  The sRGB path ends in an <b>8-bit</b> ICC transform, so sRGB exports are 8-bit —
                  padding them into a 16-bit file would claim precision the pipeline does not
                  produce. Linear (scanner RPD) is genuinely 16-bit end to end and is the vendor's
                  "Save As Raw".
                </>
              }
            >
              <Seg
                ariaLabel="Colour"
                value={colour}
                onChange={setColour}
                options={[
                  ['srgb', 'sRGB · 8'],
                  ['linear', 'Linear · 16'],
                ]}
              />
            </Field>

            <Field
              label="Format"
              info={
                colour === 'linear' ? (
                  <>
                    Linear writes 16-bit TIFF only. Per-frame steps are not baked in — this file is
                    deliberately the data before display correction.
                  </>
                ) : null
              }
            >
              <Seg
                ariaLabel="Format"
                value={effectiveFormat}
                onChange={setFormat}
                options={colour === 'linear' ? [['tiff', 'TIFF']] : FORMATS}
              />
            </Field>
          </Grp>

          <Grp title="Naming">
            <input className="inp" value={template} onChange={(e) => setTemplate(e.target.value)} spellCheck={false} />
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {['{roll}', '{frame:02}', '{stock}', '{date}', '{iso}', '{count}'].map((t) => (
                <button
                  key={t}
                  type="button"
                  className="num"
                  onClick={() => setTemplate((s) => s + t)}
                  style={{
                    fontSize: 10,
                    padding: '2px 6px',
                    borderRadius: 5,
                    background: 'var(--content2)',
                    color: 'var(--mute)',
                  }}
                >
                  {t}
                </button>
              ))}
            </div>
            <div className="num" style={{ fontSize: 11, color: 'var(--primary-ink)' }}>
              → {previewName}
            </div>
          </Grp>

          <div className="railfoot">
            <Btn variant="primary big" disabled={running || !queue.length} onClick={run}>
              {running ? `Exporting ${done} / ${queue.length}` : `Export ${queue.length} frames`}
            </Btn>
          </div>
        </Rail>
      </div>

      <Filmstrip roll={roll} selected={sel} onSelect={setSel}>
        <span className="lbl">This roll</span>
      </Filmstrip>
    </>
  );
}
