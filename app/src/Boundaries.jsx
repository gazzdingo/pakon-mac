// Fix frames — drag a boundary to move it, split or merge a frame, or
// re-detect the whole strip. Tucked behind Toolbar's "Fix frames" button;
// most rolls never need it.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Btn } from './components';
import * as api from './api';

export default function Boundaries({ roll, selected, onSelect, onEdit, busy, onClose }) {
  const laneRef = useRef(null);
  const [drag, setDrag] = useState(null);
  const lo = 0;
  const hi = roll.lines;
  const span = Math.max(1, hi - lo);
  const pct = (v) => ((v - lo) / span) * 100;

  const lineAt = useCallback((clientX) => {
    const r = laneRef.current.getBoundingClientRect();
    return Math.round(lo + ((clientX - r.left) / r.width) * span);
  }, [span]);

  useEffect(() => {
    if (!drag) return undefined;
    const move = (e) => setDrag((d) => (d ? { ...d, line: lineAt(e.clientX) } : d));
    const up = (e) => {
      const line = lineAt(e.clientX);
      setDrag(null);
      onEdit({ op: 'move', index: drag.index, line });
    };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up, { once: true });
    return () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
    };
  }, [drag, lineAt, onEdit]);

  return (
    <div className="strip">
      <div className="striphead">
        <span className="lbl">Fix frames</span>
        <span className="quiet">drag a boundary to move it</span>
        <span className="sp" />
        <Btn
          disabled={busy}
          onClick={() =>
            onEdit({
              op: 'split',
              index: selected,
              line: Math.round((roll.frames[selected].a + roll.frames[selected].b) / 2),
            })
          }
        >
          Split
        </Btn>
        <Btn disabled={busy || selected >= roll.frames.length - 1} onClick={() => onEdit({ op: 'merge', index: selected })}>
          Merge
        </Btn>
        <Btn disabled={busy} onClick={() => onEdit({ op: 'redetect' })}>
          Re-detect
        </Btn>
        <Btn variant="flat" onClick={onClose}>
          Done
        </Btn>
      </div>
      <div
        ref={laneRef}
        className="relative select-none"
        style={{ height: 58, background: '#241a12', borderRadius: 3, overflow: 'hidden' }}
      >
        {roll.frames.map((f) => (
          <button
            key={f.index}
            type="button"
            onClick={() => onSelect(f.index)}
            className="absolute"
            style={{
              left: `${pct(f.a)}%`,
              width: `${((f.b - f.a) / span) * 100}%`,
              top: 5,
              bottom: 5,
              overflow: 'hidden',
              boxShadow: f.index === selected ? 'inset 0 0 0 2px var(--primary)' : 'none',
            }}
            title={`Frame ${f.index + 1}: lines ${f.a}–${f.b}`}
          >
            <img
              src={api.frameUrl(roll.id, f.index, 'thumb', f.version)}
              alt=""
              style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
            />
          </button>
        ))}
        {roll.frames.slice(0, -1).map((f) => {
          const line = drag?.index === f.index ? drag.line : f.b;
          return (
            <div
              key={`b${f.index}`}
              onMouseDown={() => setDrag({ index: f.index, line: f.b })}
              className="absolute"
              style={{ left: `${pct(line)}%`, top: 0, bottom: 0, width: 11, marginLeft: -5, cursor: 'col-resize' }}
              title={`Boundary ${f.index + 1}|${f.index + 2}`}
            >
              <span
                className="absolute"
                style={{
                  top: 0,
                  bottom: 0,
                  left: 4,
                  width: 2,
                  background: f.confidence === 'low' ? 'var(--warning)' : '#fff',
                  opacity: drag?.index === f.index ? 1 : 0.7,
                }}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
