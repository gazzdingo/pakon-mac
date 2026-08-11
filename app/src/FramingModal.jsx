// Fine framing alignment.
//
// The primary button here was labelled "Auto Alignment", was enabled, styled
// as the most important control on the panel — and had no onClick at all. It
// did nothing, silently, forever.
//
// There is a real operation behind that name. The strip is one continuous
// capture and the frame boundaries are found afterwards, so re-running the
// detection cascade IS "align the frames automatically". So it is wired to
// that, named for what it actually does, and asks first — because it replaces
// every boundary on the roll and can change the frame count, which is not
// something to trigger by brushing a button. The backend snapshots it, so the
// way back is one Undo in the correction bench.
import React from 'react';
import { frameUrl } from './api';

export default function FramingModal({ open, onClose, roll, sel, onStep, onRedetect, busy }) {
  const [confirm, setConfirm] = React.useState(false);

  React.useEffect(() => {
    if (!open) setConfirm(false);
  }, [open]);

  if (!open || !roll) return null;

  const currentFrame = roll.frames[sel] || roll.frames[0];
  const prevFrame = roll.frames[Math.max(0, sel - 1)];
  const nextFrame = roll.frames[Math.min(roll.frames.length - 1, sel + 1)];

  return (
    <div className="modal-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-card">
        <div className="modal-header">
          <button className="circle-action-icon" onClick={onClose} aria-label="Close">
            <svg viewBox="0 0 24 24" width="16" height="16"><path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2"/></svg>
          </button>
          <span className="modal-title">Frame: {sel + 1}</span>
          <button className="circle-action-icon confirm" onClick={onClose} aria-label="Confirm">
            <svg viewBox="0 0 24 24" width="16" height="16"><path d="M5 13l4 4L19 7" stroke="currentColor" strokeWidth="2" fill="none"/></svg>
          </button>
        </div>

        <div className="framing-viewer">
          <div className="film-strip-continuous">
            {prevFrame && prevFrame !== currentFrame ? (
              <div className="strip-frame-container adjacent">
                <img src={frameUrl(roll.id, prevFrame.index, 'thumb', prevFrame.version)} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              </div>
            ) : null}

            <div className="strip-frame-container active-frame">
              <img src={frameUrl(roll.id, currentFrame.index, 'full', currentFrame.version)} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            </div>

            {nextFrame && nextFrame !== currentFrame ? (
              <div className="strip-frame-container adjacent">
                <img src={frameUrl(roll.id, nextFrame.index, 'thumb', nextFrame.version)} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              </div>
            ) : null}
          </div>
        </div>

        <div className="framing-controls">
          {onRedetect ? (
            confirm ? (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 12.5, color: 'var(--danger-ink)' }}>
                  Re-detect replaces all {roll.frames.length} boundaries?
                </span>
                <button
                  type="button"
                  className="btn primary"
                  style={{ borderRadius: 20, padding: '4px 16px' }}
                  disabled={busy || undefined}
                  onClick={async () => {
                    await onRedetect();
                    setConfirm(false);
                  }}
                >
                  {busy ? 'Detecting…' : 'Re-detect'}
                </button>
                <button type="button" className="btn" onClick={() => setConfirm(false)}>
                  Cancel
                </button>
              </span>
            ) : (
              <button
                type="button"
                className="btn primary"
                style={{ borderRadius: 20, padding: '4px 16px' }}
                disabled={busy || undefined}
                onClick={() => setConfirm(true)}
                title="Re-run the frame detection cascade over the whole strip"
              >
                Re-detect frames
              </button>
            )
          ) : null}

          <span className="num" style={{ color: 'var(--mute)', fontSize: 12.5 }}>
            Position: {Math.round(((sel + 1) / roll.frames.length) * 100)}%
          </span>

          <div style={{ display: 'flex', gap: 12, fontSize: 16 }}>
            <button type="button" className="btn" onClick={() => onStep(0)} title="First Frame">&vert;&lt;</button>
            <button type="button" className="btn" onClick={() => onStep(Math.max(0, sel - 1))} title="Previous Frame">&lt;</button>
            <button type="button" className="btn" onClick={() => onStep(Math.min(roll.frames.length - 1, sel + 1))} title="Next Frame">&gt;</button>
            <button type="button" className="btn" onClick={() => onStep(roll.frames.length - 1)} title="Last Frame">&gt;&vert;</button>
          </div>
        </div>
      </div>
    </div>
  );
}
