// Chrome-style tabs — one per open roll, plus the in-flight scan if there is
// one. A tab whose scan is still running shows a spinner ring instead of a
// close button; the scan itself lives in App state and keeps running no
// matter which tab is on screen.
import React from 'react';
import logo from './icons/pakon_frosty_transparent_final.png';

export default function TabStrip({ rolls, activeTab, onSelect, onClose, scanning, onNewScan }) {
  return (
    <div className="tabstrip" role="tablist" aria-label="Open rolls">
      <img
        src={logo}
        alt=""
        style={{ width: 22, height: 22, objectFit: 'contain', margin: '0 6px 6px 4px', flex: 'none' }}
      />
      {scanning ? (
        <div
          className={`tab${activeTab === 'new' ? ' on' : ''}`}
          role="tab"
          aria-selected={activeTab === 'new'}
          onClick={() => onSelect('new')}
        >
          <span className="ring" />
          <span className="name">New scan</span>
        </div>
      ) : null}
      {rolls.map((r) => (
        <div
          key={r.id}
          className={`tab${activeTab === r.id ? ' on' : ''}`}
          role="tab"
          aria-selected={activeTab === r.id}
          onClick={() => onSelect(r.id)}
        >
          <span className="name">{r.name}</span>
          <span
            className="x"
            title="Close"
            onClick={(e) => {
              e.stopPropagation();
              onClose(r.id);
            }}
          >
            <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </span>
        </div>
      ))}
      <button className="tabnew" title="Scan a roll" onClick={onNewScan}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
          <path d="M12 5v14M5 12h14" />
        </svg>
      </button>
    </div>
  );
}
