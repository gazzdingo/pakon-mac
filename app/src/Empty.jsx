// Nothing scanned or open yet. One primary action, one secondary escape
// hatch for a capture that already exists on disk.
import React from 'react';
import { Btn } from './components';
import logo from './icons/pakon_frosty_transparent_final.png';

export default function Empty({ onScan, onOpen }) {
  return (
    <div className="stage" style={{ flexDirection: 'column', gap: 18 }}>
      <div className="empty-card">
        <div className="empty-glyph">
          <img src={logo} alt="" />
        </div>
        <h1 className="title" style={{ fontSize: 20 }}>Nothing scanned yet</h1>
        <p className="quiet">
          Load a roll into the scanner and scan it. Every frame lands here as soon as the strip
          finishes.
        </p>
        <Btn variant="primary big" onClick={onScan}>
          Scan a roll
        </Btn>
        <Btn variant="flat" onClick={onOpen}>
          Open existing capture…
        </Btn>
      </div>
    </div>
  );
}
