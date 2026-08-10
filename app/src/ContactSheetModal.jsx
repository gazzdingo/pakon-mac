import React from 'react';
import { frameUrl } from './api';

export default function ContactSheetModal({ open, onClose, roll, onSelectFrame }) {
  if (!open || !roll) return null;

  return (
    <div className="modal-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-card" style={{ width: 880, maxHeight: '85vh' }}>
        <div className="modal-header">
          <button className="circle-action-icon" onClick={onClose} aria-label="Close">
            <svg viewBox="0 0 24 24" width="16" height="16"><path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2"/></svg>
          </button>
          <div style={{ textAlign: 'center' }}>
            <div className="modal-title">Contact Sheet</div>
            <div className="num" style={{ fontSize: 11.5, color: 'var(--faint)' }}>
              {roll.name} &bull; {roll.frames.length} frames
            </div>
          </div>
          <div style={{ width: 32 }} />
        </div>

        <div className="contact-sheet-grid">
          {roll.frames.map((f, i) => (
            <div
              key={f.index}
              className="contact-cell"
              onClick={() => {
                onSelectFrame(f.index);
                onClose();
              }}
              title={`Frame ${f.index + 1}`}
            >
              <img
                src={frameUrl(roll.id, f.index, 'thumb', f.version)}
                alt=""
                style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
              />
              <span className="contact-cell-num">&#9654;{i + 1}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
