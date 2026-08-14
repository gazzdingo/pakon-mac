// The only screen that writes files. Every frame is selected by default
// (rejects excluded) — pick your destination and format and go.
import React, { useEffect, useState } from 'react';
import { Btn, Seg } from './components';
import * as api from './api';

const FORMATS = [
  ['jpeg', 'JPEG'],
  ['tiff', 'TIFF'],
  ['png', 'PNG'],
];

/** What this export would destroy, and the ways out. Unchanged from before:
 *  the whole export is planned before anything is rendered, and nothing is
 *  written until this is answered. */
function CollisionSheet({ plan, busy, onCancel, onChoose }) {
  if (!plan) return null;
  const existing = plan.existing || [];
  const dups = plan.duplicates || [];

  return (
    <div className="scrim on" onMouseDown={(e) => e.target === e.currentTarget && !busy && onCancel()}>
      <div className="sheet">
        <div style={{ marginBottom: 14 }}>
          <span className="title">This export would replace files</span>
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
                  <span className="num" style={{ flex: 1, fontSize: 11.5 }}>{e.path.split('/').pop()}</span>
                  <span className="num" style={{ fontSize: 11, color: 'var(--faint)' }}>{api.fmtBytes(e.bytes)}</span>
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
            <b>{dups.length + 1} frames render to the same filename</b> and would overwrite each other. Put{' '}
            <span className="num">{'{frame:02}'}</span> back in the naming pattern unless you meant this.
          </div>
        ) : null}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
          <Btn variant="flat" disabled={busy} onClick={onCancel}>Cancel</Btn>
          <Btn variant="flat" disabled={busy} onClick={() => onChoose('skip')}>
            Skip the {existing.length + dups.length} clashing
          </Btn>
          <Btn variant="flat" disabled={busy} onClick={() => onChoose('unique')}>Number the new ones</Btn>
          <Btn variant="primary" disabled={busy} onClick={() => onChoose('overwrite')}>Replace</Btn>
        </div>
      </div>
    </div>
  );
}

export default function ExportModal({ open, onClose, roll, cfg, setCfg, job, running, collision, onRun, onCancelCollision }) {
  const [selected, setSelected] = useState(() => new Set());
  const [showNaming, setShowNaming] = useState(false);

  useEffect(() => {
    if (open && roll) {
      setSelected(new Set(roll.frames.filter((f) => !f.params?.rejected).map((f) => f.index)));
      setShowNaming(false);
    }
  }, [open, roll]);

  if (!open || !roll) return null;

  const { format, colour, template, dest, subfolder } = cfg;
  const put = (k, v) => setCfg((c) => ({ ...c, [k]: v }));
  const effectiveFormat = colour === 'linear' ? 'tiff' : format;

  const toggle = (i) => {
    setSelected((s) => {
      const n = new Set(s);
      n.has(i) ? n.delete(i) : n.add(i);
      return n;
    });
  };

  const results = job?.results || [];
  const done = results.filter((r) => r.status === 'written').length;

  return (
    <>
      <div className="scrim on" onMouseDown={(e) => e.target === e.currentTarget && !running && onClose()}>
        <div className="sheet wide" style={{ width: 680 }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 14 }}>
            <span className="title" style={{ fontSize: 17 }}>Export {roll.name}</span>
            <span className="sp" />
            <span className="quiet">{selected.size} of {roll.frames.length} selected</span>
          </div>

          <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
            <Btn
              variant="flat"
              style={{ height: 28, padding: '0 10px', fontSize: 12 }}
              onClick={() => setSelected(new Set(roll.frames.map((f) => f.index)))}
            >
              Select all
            </Btn>
            <Btn
              variant="flat"
              style={{ height: 28, padding: '0 10px', fontSize: 12 }}
              onClick={() => setSelected(new Set())}
            >
              Select none
            </Btn>
          </div>

          <div
            className="contact-sheet-grid"
            style={{ padding: 0, background: 'none', gridTemplateColumns: 'repeat(6, 1fr)', maxHeight: 260, marginBottom: 16 }}
          >
            {roll.frames.map((f) => (
              <div
                key={f.index}
                className={`expcell${selected.has(f.index) ? ' sel' : ''}`}
                onClick={() => toggle(f.index)}
              >
                <img src={api.frameUrl(roll.id, f.index, 'thumb', f.version)} alt="" loading="lazy" />
                <span className="num-badge">{f.index + 1}</span>
                <span className="check">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 6 9 17l-5-5" />
                  </svg>
                </span>
              </div>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 10, marginBottom: 12 }}>
            <div className="field" style={{ marginBottom: 0 }}>
              <span className="lbl">Save to</span>
              <div style={{ display: 'flex', gap: 6 }}>
                <input className="inp" value={dest} onChange={(e) => put('dest', e.target.value)} spellCheck={false} />
                <Btn
                  variant="flat"
                  onClick={async () => {
                    const d = await window.pakon?.chooseFolder(dest);
                    if (d) put('dest', d);
                  }}
                >
                  Browse…
                </Btn>
              </div>
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, whiteSpace: 'nowrap' }}>
              <input type="checkbox" checked={subfolder} onChange={(e) => put('subfolder', e.target.checked)} />
              Subfolder per roll
            </label>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
            <div className="field" style={{ marginBottom: 0 }}>
              <span className="lbl">Format</span>
              <Seg
                ariaLabel="Format"
                value={effectiveFormat}
                onChange={(v) => put('format', v)}
                options={colour === 'linear' ? [['tiff', 'TIFF']] : FORMATS}
              />
            </div>
            <div className="field" style={{ marginBottom: 0 }}>
              <span className="lbl">Colour</span>
              <Seg
                ariaLabel="Colour"
                value={colour}
                onChange={(v) => put('colour', v)}
                options={[
                  ['srgb', 'sRGB · 8-bit'],
                  ['linear', 'Linear · 16-bit'],
                ]}
              />
            </div>
          </div>

          {showNaming ? (
            <div className="field" style={{ marginBottom: 14 }}>
              <span className="lbl">Rename pattern</span>
              <input className="inp" value={template} onChange={(e) => put('template', e.target.value)} spellCheck={false} />
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
                {['{roll}', '{frame:02}', '{stock}', '{date}', '{iso}', '{count}'].map((t) => (
                  <button
                    key={t}
                    type="button"
                    className="num"
                    onClick={() => setCfg((c) => ({ ...c, template: c.template + t }))}
                    style={{ fontSize: 10, padding: '2px 6px', borderRadius: 5, background: 'var(--content2)', color: 'var(--mute)' }}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <button
              type="button"
              className="quiet"
              onClick={() => setShowNaming(true)}
              style={{ marginBottom: 14, textAlign: 'left' }}
            >
              Rename pattern…
            </button>
          )}

          {job?.status === 'error' ? (
            <div
              style={{
                background: 'var(--danger-flat)',
                color: 'var(--danger-ink)',
                borderRadius: 'var(--r-sm)',
                padding: '9px 11px',
                marginBottom: 14,
                fontSize: 12,
              }}
            >
              {job.error}
            </div>
          ) : null}

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <Btn variant="flat" disabled={running} onClick={onClose}>
              {done && job?.status === 'done' ? 'Done' : 'Cancel'}
            </Btn>
            <Btn
              variant="primary big"
              style={{ width: 'auto', padding: '0 20px' }}
              disabled={running || !selected.size}
              onClick={() => onRun(Array.from(selected))}
            >
              {running ? `Exporting ${done} / ${selected.size}` : `Export ${selected.size} frame${selected.size === 1 ? '' : 's'}`}
            </Btn>
          </div>
        </div>
      </div>

      <CollisionSheet
        plan={collision}
        busy={running}
        onCancel={onCancelCollision}
        onChoose={(answer) => onRun(Array.from(selected), answer)}
      />
    </>
  );
}
