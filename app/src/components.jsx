// Shared pieces of the shell: top bar, rails, filmstrip, density trace.
// The arrangement is the approved one from design/review.html — 44 px top
// bar, session rail left, image stage on Void, one inspector right, filmstrip
// and density trace across the bottom.
import React, { useEffect, useRef, useState } from 'react';
import { Button, Chip, Tooltip } from '@heroui/react';
import { frameUrl } from './api';

export const MODES = [
  ['scan', 'Scan'],
  ['review', 'Review'],
  ['export', 'Export'],
  ['calibrate', 'Calibrate'],
  ['diagnostics', 'Diagnostics'],
];

export function Dot({ tone = 'idle' }) {
  const bg = { ok: 'var(--pass)', live: 'var(--filament)', bad: 'var(--halt)', idle: 'var(--rule)' }[
    tone
  ];
  return (
    <i
      className={`inline-block w-[7px] h-[7px] rounded-full shrink-0 ${tone === 'live' ? 'pulse' : ''}`}
      style={{ background: bg }}
    />
  );
}

export function TopBar({ mode, setMode, roll, chips }) {
  return (
    <header
      className="flex items-stretch h-11 shrink-0 border-b"
      style={{ background: 'var(--plate)', borderColor: 'var(--rule)' }}
    >
      <div
        className="flex flex-col justify-center px-4 border-r select-none"
        style={{ borderColor: 'var(--rule)', WebkitAppRegion: 'drag', paddingLeft: 88 }}
      >
        <b className="text-[12px] tracking-[0.18em] font-semibold">PAKON F-135 PLUS</b>
        <span className="text-[9px] tracking-[0.14em]" style={{ color: 'var(--mute)' }}>
          film scanner
        </span>
      </div>
      <nav className="flex items-stretch">
        {MODES.map(([id, label]) => (
          <button
            key={id}
            onClick={() => setMode(id)}
            className="px-[18px] text-[11px] tracking-[0.14em] border-r gate"
            style={{
              borderColor: 'var(--rule)',
              color: mode === id ? 'var(--ink)' : 'var(--mute)',
              boxShadow: mode === id ? 'inset 0 -2px 0 var(--ink)' : 'none',
              background: mode === id ? 'var(--plate2)' : 'transparent',
            }}
          >
            {label}
          </button>
        ))}
      </nav>

      {roll?.stock ? (
        <div
          className="flex items-center gap-[10px] ml-auto px-4 border-l"
          style={{ borderColor: 'var(--rule)' }}
        >
          <span className="lbl">{roll.dx ? `DX ${roll.dx}` : roll.film_path}</span>
          <span className="ledger text-[14px]">{roll.stock.name}</span>
          {roll.stock.iso ? <span className="lbl">ISO {roll.stock.iso}</span> : null}
        </div>
      ) : (
        <div
          className="flex items-center gap-[10px] ml-auto px-4 border-l"
          style={{ borderColor: 'var(--rule)' }}
        >
          <span className="lbl">Film</span>
          <span className="ledger text-[14px]" style={{ color: 'var(--mute)' }}>
            {roll?.film_path || (roll ? 'unset' : '—')}
          </span>
        </div>
      )}

      <div className="flex items-center gap-3 px-4 border-l" style={{ borderColor: 'var(--rule)' }}>
        {chips}
      </div>
    </header>
  );
}

export function Rail({ children, width = 232, side = 'left' }) {
  return (
    <aside
      className={`shrink-0 overflow-y-auto ${side === 'left' ? 'border-r' : 'border-l'}`}
      style={{ width, background: 'var(--plate)', borderColor: 'var(--rule)' }}
    >
      {children}
    </aside>
  );
}

export function Section({ title, children, action, grow }) {
  return (
    <section
      className={`px-4 py-[14px] border-b ${grow ? 'mt-auto' : ''}`}
      style={{ borderColor: 'var(--rule)' }}
    >
      {title ? (
        <div className="flex items-center justify-between mb-[10px]">
          <h2 className="text-[10px] tracking-[0.14em] uppercase font-semibold" style={{ color: 'var(--mute)' }}>
            {title}
          </h2>
          {action}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function KV({ rows }) {
  return (
    <dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 text-[12px]">
      {rows.map(([k, v]) => (
        <React.Fragment key={k}>
          <dt style={{ color: 'var(--mute)' }}>{k}</dt>
          <dd className="num text-right">{v}</dd>
        </React.Fragment>
      ))}
    </dl>
  );
}

export function Plain({ children, onPress, active, className = '', ...rest }) {
  return (
    <Button
      onPress={onPress}
      className={`w-full justify-center rounded-none border text-[11px] tracking-[0.1em] uppercase h-9 gate ${className}`}
      style={{
        borderColor: active ? 'var(--ink)' : 'var(--rule)',
        background: active ? 'var(--plate2)' : 'transparent',
        color: 'var(--ink)',
      }}
      {...rest}
    >
      {children}
    </Button>
  );
}

/** The roll as one set of frames. Thumbnails are rendered by the backend at
 *  1/8 scale, so a 37-frame roll costs about 40 ms per thumbnail once. */
export function Filmstrip({ roll, selected, onSelect }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current?.querySelector(`[data-i="${selected}"]`);
    el?.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' });
  }, [selected]);

  return (
    <div ref={ref} className="flex gap-[6px] px-4 pt-[10px] pb-1 overflow-x-auto">
      {roll.frames.map((f) => {
        const rejected = f.params?.rejected;
        return (
          <button
            key={f.index}
            data-i={f.index}
            onClick={() => onSelect(f.index)}
            title={`Frame ${f.index + 1} — ${f.summary}`}
            className="relative shrink-0 w-[76px] h-[52px] overflow-hidden border gate"
            style={{
              borderColor: selected === f.index ? 'var(--ink)' : 'var(--rule)',
              boxShadow: selected === f.index ? '0 0 0 1px var(--ink)' : 'none',
            }}
          >
            <img
              src={frameUrl(roll.id, f.index, 'thumb', f.version)}
              alt=""
              loading="lazy"
              className="w-full h-full object-cover"
              style={{ background: '#000' }}
            />
            <i
              className="absolute left-[3px] bottom-[1px] num text-[9px] not-italic"
              style={{ color: 'rgba(232,232,232,.85)', textShadow: '0 0 3px #000' }}
            >
              {f.index + 1}
            </i>
            {f.adjusted ? (
              <span
                className="absolute top-[2px] right-[3px] w-[5px] h-[5px]"
                style={{ background: 'var(--mute)' }}
                title="adjusted"
              />
            ) : null}
            {f.confidence === 'low' ? (
              <span
                className="absolute top-[2px] left-[3px] w-[5px] h-[5px]"
                style={{ background: 'var(--filament)' }}
                title="low boundary confidence"
              />
            ) : null}
            {rejected ? (
              <span
                className="absolute inset-0"
                style={{
                  background:
                    'repeating-linear-gradient(45deg,transparent 0 6px,rgba(11,11,11,.65) 6px 9px)',
                }}
              />
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

/** Per-frame mean density across the roll; the cursor marks the selection. */
export function DensityTrace({ trace, selected, onSelect }) {
  if (!trace?.length) return null;
  const W = 900;
  const H = 34;
  const lo = Math.min(...trace);
  const hi = Math.max(...trace);
  const span = hi - lo || 1;
  const step = trace.length > 1 ? W / (trace.length - 1) : W;
  const pts = trace
    .map((v, i) => `${(i * step).toFixed(1)},${(H - 4 - ((v - lo) / span) * (H - 10)).toFixed(1)}`)
    .join(' ');
  return (
    <div className="px-4 pb-2 h-[34px]" title="Per-frame mean density">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="w-full h-full block">
        <line x1="0" y1={H / 2} x2={W} y2={H / 2} stroke="var(--rule)" strokeWidth="1" />
        <polyline fill="none" stroke="var(--mute)" strokeWidth="1.25" points={pts} />
        {trace.map((_, i) => (
          <rect
            key={i}
            x={i * step - step / 2}
            y="0"
            width={step}
            height={H}
            fill="transparent"
            style={{ cursor: 'pointer' }}
            onClick={() => onSelect?.(i)}
          />
        ))}
        <line
          x1={selected * step}
          y1="2"
          x2={selected * step}
          y2={H - 2}
          stroke="var(--ink)"
          strokeWidth="1"
        />
      </svg>
    </div>
  );
}

export function StatusLine({ left, children, right }) {
  return (
    <div
      className="flex gap-6 items-center h-[26px] px-4 border-t num text-[11px]"
      style={{ borderColor: 'var(--rule)', color: 'var(--mute)' }}
    >
      {left ? <span style={{ color: 'var(--ink)' }}>{left}</span> : null}
      {children}
      <span className="flex-1" />
      {right}
    </div>
  );
}

/** Machine state is the only thing allowed to be gold. */
export function Working({ children }) {
  return (
    <span className="flex items-center gap-2 text-[11px] filament py-1.5">
      <span
        className="spin w-3 h-3 rounded-full shrink-0"
        style={{ border: '2px solid var(--rule)', borderTopColor: 'var(--filament)' }}
      />
      {children}
    </span>
  );
}

export function Empty({ title, children, action }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center px-8">
      <div className="ledger text-[22px]">{title}</div>
      <p className="text-[13px] max-w-[52ch]" style={{ color: 'var(--mute)' }}>
        {children}
      </p>
      {action}
    </div>
  );
}

export function useDebounced(value, ms) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}
