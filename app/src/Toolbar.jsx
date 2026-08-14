// The bar under the tabs: which roll, which view, and the two things you can
// always do to it — fix the frame boundaries, export. Nothing here is a
// setting; everything here is a place to go.
import React from 'react';
import { Btn, ThemeSwitch } from './components';

export default function Toolbar({ roll, view, setView, onExport, onFixFrames, dark, setDark }) {
  const queue = roll ? roll.frames.filter((f) => !f.params?.rejected).length : 0;

  return (
    <div className="toolbar">
      {roll ? (
        <>
          <span className="rollname title" style={{ fontSize: 15 }}>{roll.name}</span>
          <span className="quiet">
            <span className="num" style={{ fontSize: 12 }}>{roll.frames.length}</span> frames
            {roll.stock?.name ? ` · ${roll.stock.name}` : ''}
          </span>
          <span className="sp" />
          <div className="seg2" role="tablist" aria-label="View">
            <button className={view === 'contact' ? 'on' : ''} onClick={() => setView('contact')}>
              Contact sheet
            </button>
            <button className={view === 'editor' ? 'on' : ''} onClick={() => setView('editor')}>
              Frame
            </button>
          </div>
          <Btn variant="flat" onClick={onFixFrames}>
            Fix frames
          </Btn>
          <Btn variant="primary" disabled={!queue} onClick={onExport}>
            Export…
          </Btn>
        </>
      ) : (
        <span className="sp" />
      )}
      <ThemeSwitch dark={dark} setDark={setDark} />
    </div>
  );
}
