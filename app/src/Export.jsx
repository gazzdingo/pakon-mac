// Step 3 — export. The only moment files are written.
//
// Same Console furniture: settings rail left, the queue in the middle, the
// output options right, the roll along the floor. Each frame renders once at
// full quality (measured: 630 ms for 2878x2000) from the capture and its
// settings, writes its file, then frees memory.
//
// The job and the settings that make it are App's, not this screen's — see
// `runExport` in App.jsx. A running export has to go on running, and go on
// being visible in the step bar, when the user walks back to step 2.
import React, { useMemo } from 'react';
import { Btn, Chip, Field, Filmstrip, Grp, Info, Rail, RailHead, Seg, State } from './components';
import * as api from './api';

const FORMATS = [
  ['tiff', 'TIFF'],
  ['png', 'PNG'],
  ['jpeg', 'JPEG'],
];

/** What this export would destroy, and the ways out.
 *
 *  Both collisions get their own sentence, because they are different
 *  mistakes. Files already in the folder are a decision — replacing your own
 *  earlier export after a re-grade is a real and common intention. Frames
 *  colliding with each other is a broken naming template, and the fix is
 *  almost always to close this and put `{frame:02}` back rather than to pick
 *  any of these buttons. So that one says so. */
function CollisionSheet({ plan, busy, onCancel, onChoose }) {
  if (!plan) return null;
  const existing = plan.existing || [];
  const dups = plan.duplicates || [];

  return (
    <div className="scrim" onMouseDown={(e) => e.target === e.currentTarget && !busy && onCancel()}>
      <div className="sheet">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
          <span className="title">This export would replace files</span>
          <span className="sp" />
          <Info side="left">
            Export is the only act in this application that writes a file you
            keep, so it is the only one that can destroy one. The whole export
            is planned before any of it is rendered, and nothing is written
            until this is answered.
          </Info>
        </div>

        {existing.length ? (
          <>
            <p style={{ fontSize: 13, marginBottom: 8 }}>
              <b>{existing.length}</b> file{existing.length === 1 ? '' : 's'} already in{' '}
              <span className="num">{plan.dest}</span> would be replaced.
            </p>
            <div className="rows" style={{ marginBottom: 12, maxHeight: 150, overflowY: 'auto' }}>
              {existing.slice(0, 40).map((e) => (
                <div key={e.path} style={{ display: 'flex', gap: 8, padding: '3px 0' }}>
                  <span className="num" style={{ flex: 1, fontSize: 11.5 }}>
                    {e.path.split('/').pop()}
                  </span>
                  <span className="num" style={{ fontSize: 11, color: 'var(--faint)' }}>
                    {api.fmtBytes(e.bytes)}
                  </span>
                </div>
              ))}
            </div>
          </>
        ) : null}

        {dups.length ? (
          <div
            style={{
              background: 'var(--danger-flat)',
              color: 'var(--danger-ink)',
              borderRadius: 'var(--r-sm)',
              padding: '9px 11px',
              marginBottom: 12,
              fontSize: 12.5,
            }}
          >
            <b>{dups.length + 1} frames render to the same filename</b> and would overwrite each
            other.
            <br />
            The naming template does not tell them apart. Exporting anyway leaves one file in the
            folder where you expected {dups.length + 1}, and nothing in the folder afterwards says
            so. Cancel and put <span className="num">{'{frame:02}'}</span> back unless you meant
            this.
          </div>
        ) : null}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
          <Btn variant="flat" disabled={busy} onClick={onCancel}>
            Cancel
          </Btn>
          <Btn variant="flat" disabled={busy} onClick={() => onChoose('skip')}>
            Skip the {existing.length + dups.length} clashing
          </Btn>
          <Btn variant="primary" disabled={busy} onClick={() => onChoose('unique')}>
            Number the new ones
          </Btn>
          <Btn variant="flat" disabled={busy} onClick={() => onChoose('overwrite')}>
            Replace
          </Btn>
        </div>
      </div>
    </div>
  );
}

export default function Export({
  roll,
  sel,
  setSel,
  cfg,
  setCfg,
  job,
  running,
  collision,
  onRun,
  onCancelCollision,
  onGoReview,
}) {
  const { format, colour, template, dest, subfolder } = cfg;
  const put = (k, v) => setCfg((c) => ({ ...c, [k]: v }));

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

  if (!roll) {
    return (
      <div className="body" style={{ gridTemplateColumns: 'minmax(0,1fr)' }}>
        <div className="stage" style={{ flexDirection: 'column', gap: 12 }}>
          <span className="title">Nothing to export</span>
          <span className="quiet">Step 3 writes the frames step 2 made. There are none yet.</span>
        </div>
      </div>
    );
  }

  const statusOf = (f) => {
    const r = results.find((x) => x.frame === f.index);
    // "replaced" and "skipped" are outcomes the queue never used to have,
    // because overwriting was silent and skipping was impossible.
    if (r?.status === 'written') return [r.replaced ? 'replaced' : 'written', 'var(--ok-ink)'];
    if (r?.status === 'skipped') return ['skipped — already there', 'var(--warn-ink)'];
    if (r?.status === 'error') return [r.error?.slice(0, 28) || 'error', 'var(--danger-ink)'];
    if (job?.current === f.index && running) return ['rendering', 'var(--warn-ink)'];
    if (f.params?.rejected) return ['rejected', 'var(--faint)'];
    return ['queued', 'var(--faint)'];
  };

  return (
    <>
      <CollisionSheet
        plan={collision}
        busy={running}
        onCancel={onCancelCollision}
        onChoose={(answer) => onRun(answer)}
      />
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
            <input className="inp" value={dest} onChange={(e) => put('dest', e.target.value)} spellCheck={false} />
            <Btn
              variant="flat"
              onClick={async () => {
                const d = await window.pakon?.chooseFolder(dest);
                if (d) put('dest', d);
              }}
            >
              Choose folder…
            </Btn>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12.5 }}>
              <input type="checkbox" checked={subfolder} onChange={(e) => put('subfolder', e.target.checked)} />
              Subfolder per roll
            </label>
            {job?.dest ? (
              <Btn variant="flat" onClick={() => window.pakon?.openPath(job.dest)}>
                Reveal
              </Btn>
            ) : null}
          </Grp>
          {/* Back to step 2. Not a wizard: the export goes on running while
              you re-grade a frame, and the step bar keeps saying so. */}
          <div className="railfoot">
            <Btn variant="flat big" style={{ height: 34 }} onClick={onGoReview}>
              ← Edit
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
                  produce. Linear (scanner RPD) is genuinely 16-bit end to end in this app's own
                  pipeline, at the same stage as the vendor's "Save As Raw" — but the real vendor
                  software's own Save As Raw file is actually 8-bit (checked against a real export),
                  even though the scanner's sensor captures far more than 8 bits. This file keeps
                  what the vendor's own software throws away; it is not a copy of the vendor file's
                  depth.
                </>
              }
            >
              <Seg
                ariaLabel="Colour"
                value={colour}
                onChange={(v) => put('colour', v)}
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
                onChange={(v) => put('format', v)}
                options={colour === 'linear' ? [['tiff', 'TIFF']] : FORMATS}
              />
            </Field>
          </Grp>

          <Grp title="Naming">
            <input className="inp" value={template} onChange={(e) => put('template', e.target.value)} spellCheck={false} />
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {['{roll}', '{frame:02}', '{stock}', '{date}', '{iso}', '{count}'].map((t) => (
                <button
                  key={t}
                  type="button"
                  className="num"
                  onClick={() => setCfg((c) => ({ ...c, template: c.template + t }))}
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
            {/* Said here, before the export, rather than only in the sheet
                that stops it. This field is free text and the one edit that
                quietly destroys a whole roll — removing {frame} — looks like
                every other edit to it. */}
            {queue.length > 1 && !/\{frame/.test(template) ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Chip tone="bad" dot>
                  Every frame gets the same name
                </Chip>
                <Info side="left">
                  Without <span className="num">{'{frame}'}</span> all{' '}
                  {queue.length} frames render to one filename and overwrite each other, leaving a
                  single file. The export will stop and ask rather than let that happen quietly.
                </Info>
              </div>
            ) : null}
          </Grp>

          <div className="railfoot">
            {/* `() => onRun()` and not `onRun`: the click event is truthy, and
                as the first argument it would read as an on_exist answer and
                skip the collision check entirely. */}
            <Btn variant="primary big" disabled={running || !queue.length} onClick={() => onRun()}>
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
