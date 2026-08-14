// Every frame from the roll, at a glance. The default view once a roll has
// been scanned or opened — click a frame to edit it.
import React from 'react';
import { frameUrl } from './api';

export default function ContactSheet({ roll, onSelectFrame }) {
  if (!roll) return null;

  return (
    <div className="contact-sheet-grid" style={{ flex: 1, minHeight: 0, maxHeight: 'none' }}>
      {roll.frames.map((f) => (
        <div
          key={f.index}
          className={`contact-cell${f.params?.rejected ? ' rejected' : ''}`}
          onClick={() => onSelectFrame(f.index)}
          title={`Frame ${f.index + 1}`}
        >
          <img src={frameUrl(roll.id, f.index, 'thumb', f.version)} alt="" loading="lazy" />
          <span className="contact-cell-num">{f.index + 1}</span>
        </div>
      ))}
    </div>
  );
}
