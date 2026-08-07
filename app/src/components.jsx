// The Console — shared furniture.
//
// Layout is design/variants/console-scan.html and console-review.html: two
// bars, three columns, the roll along the floor. Every class used here is
// defined in theme.css and carried from those files.
//
// Copy rule, from the owner: labels are titles, not sentences. A control gets
// a label, a value and a state. Anything that needs explaining — why Base 4
// and 8 are disabled, why a stage is unavailable — goes behind <Info>, which
// is closed until asked.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { frameUrl } from './api';

export const MODES = [
  ['scan', 'Scan'],
  ['review', 'Review'],
  ['export', 'Export'],
  ['calibrate', 'Calibrate'],
  ['diagnostics', 'Diagnostics'],
];

/* ── the info affordance ────────────────────────────────────────────────── */

/** A closed disclosure. The only place long-form reasoning is allowed. */
export function Info({ children, side = 'right', label = 'Why' }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const away = (e) => !ref.current?.contains(e.target) && setOpen(false);
    const esc = (e) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', away);
    document.addEventListener('keydown', esc);
    return () => {
      document.removeEventListener('mousedown', away);
      document.removeEventListener('keydown', esc);
    };
  }, [open]);

  return (
    <span className="infowrap" ref={ref}>
      <button
        type="button"
        className="info"
        aria-expanded={open}
        aria-label={label}
        onClick={(e) => {
          e.stopPropagation();
          e.preventDefault();
          setOpen((v) => !v);
        }}
      >
        i
      </button>
      {open ? <span className={`infopop${side === 'left' ? ' left' : ''}`}>{children}</span> : null}
    </span>
  );
}

/* ── small parts ────────────────────────────────────────────────────────── */

export function Chip({ tone, dot, children, className = '', ...rest }) {
  return (
    <span className={`chip${tone ? ` ${tone}` : ''} ${className}`} {...rest}>
      {dot ? <span className="dot" /> : null}
      {children}
    </span>
  );
}

export function Btn({ variant = '', children, onClick, disabled, ...rest }) {
  return (
    <button
      type="button"
      className={`btn ${variant}`}
      onClick={onClick}
      disabled={disabled || undefined}
      {...rest}
    >
      {children}
    </button>
  );
}

export function Num({ children, size }) {
  return (
    <span className="num" style={size ? { fontSize: size } : undefined}>
      {children}
    </span>
  );
}

/* ── rails ──────────────────────────────────────────────────────────────── */

export const Rail = ({ side = 'l', children, ...rest }) => (
  <aside className={`rail ${side}`} {...rest}>
    {children}
  </aside>
);

export const RailHead = ({ title, children }) => (
  <div className="railhead">
    <span className="lbl">{title}</span>
    <span className="sp" />
    {children}
  </div>
);

export const Grp = ({ title, info, children }) => (
  <div className="grp">
    {title ? (
      <span className="lbl" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {title}
        {info ? <Info>{info}</Info> : null}
      </span>
    ) : null}
    {children}
  </div>
);

/** Label, control, value. No subtext — that is what `info` is for. */
export const Field = ({ label, info, children, value }) => (
  <div className="field">
    {label ? (
      <span className="lbl" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {label}
        {info ? <Info>{info}</Info> : null}
        {value ? (
          <>
            <span className="sp" />
            <span className="num" style={{ fontSize: 11, color: 'var(--mute)' }}>
              {value}
            </span>
          </>
        ) : null}
      </span>
    ) : null}
    {children}
  </div>
);

/** Segmented control. An option may be disabled and carry its own reason. */
export function Seg({ options, value, onChange, ariaLabel }) {
  return (
    <div className="seg" role="radiogroup" aria-label={ariaLabel}>
      {options.map(([id, label, disabled]) => (
        <button
          key={id}
          type="button"
          role="radio"
          aria-checked={value === id}
          className={value === id ? 'on' : ''}
          disabled={disabled || undefined}
          onClick={() => !disabled && onChange?.(id)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export function Toggle({ on, disabled, onChange, children, info }) {
  return (
    <label className="sw">
      <span
        role="switch"
        aria-checked={!!on}
        aria-disabled={disabled || undefined}
        tabIndex={disabled ? -1 : 0}
        className={`kt${on ? ' on' : ''}${disabled ? ' off' : ''}`}
        onClick={() => !disabled && onChange?.(!on)}
        onKeyDown={(e) => e.key === ' ' && !disabled && onChange?.(!on)}
      />
      <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {children}
        {info ? <Info>{info}</Info> : null}
      </span>
    </label>
  );
}

/** One row per subsystem: name, verdict. `tone` is good | warn | bad | na. */
export function State({ rows }) {
  return (
    <dl style={{ display: 'flex', flexDirection: 'column' }}>
      {rows.map(([name, value, tone, info]) => (
        <div className="st" key={name}>
          <dt>
            {name}
            {info ? <Info>{info}</Info> : null}
          </dt>
          <dd className={tone || ''}>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/* ── shell bars ─────────────────────────────────────────────────────────── */

const SUN = (
  <svg className="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round">
    <circle cx="12" cy="12" r="4.2" />
    <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6L17 7M7 17l-1.4 1.4" />
  </svg>
);
const MOON = (
  <svg className="moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z" />
  </svg>
);

export function useTheme() {
  const [dark, setDark] = useState(
    () => document.documentElement.getAttribute('data-theme') === 'dark',
  );
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  }, [dark]);
  return [dark, setDark];
}

export function TopBar({ mode, setMode, roll, dark, setDark }) {
  return (
    <header className="top">
      <span
        className="brand"
        style={{ WebkitAppRegion: 'drag', paddingLeft: window.pakon?.platform === 'darwin' ? 62 : 0 }}
      >
        PAKON&nbsp;F&#8209;135&nbsp;PLUS
      </span>
      <nav className="modes" aria-label="Mode">
        {MODES.map(([id, label]) => (
          <button key={id} type="button" className={`mode${mode === id ? ' on' : ''}`} onClick={() => setMode(id)}>
            {label}
          </button>
        ))}
      </nav>
      <span className="sp" />
      {roll ? (
        <>
          <Chip>
            {roll.stock?.name || roll.film_path}
            {roll.stock?.iso ? <span className="num" style={{ fontSize: 11 }}>ISO {roll.stock.iso}</span> : null}
          </Chip>
          <Chip>
            Roll <span className="num" style={{ fontSize: 11 }}>{roll.name}</span>
          </Chip>
        </>
      ) : (
        <Chip>No roll open</Chip>
      )}
      <button
        type="button"
        className="themeswap"
        aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
        onClick={() => setDark(!dark)}
      >
        {SUN}
        {MOON}
      </button>
    </header>
  );
}

/** Twin lanes. `capture` is permanently idle in this build — the transport is
 *  not driven from here — and says so once, in the lane, behind an Info. */
export function Lanes({ exportJob, onCancelExport }) {
  const running = exportJob && exportJob.status === 'running';
  const pct = running || exportJob?.status === 'done' ? Math.round((exportJob.progress || 0) * 100) : null;
  return (
    <div className="lanes">
      <div className="lane">
        <span className="what">
          <span className="lbl" style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            Capture
            <Info side="left">
              <b>Not wired.</b> Driving the transport is proven in{' '}
              <span className="num">tools/pakon_session.py</span> — EP&nbsp;
              <span className="num">0x86</span> at <span className="num">11.6&nbsp;MB/s</span>, zero
              losses — and is not connected to this window. Rolls are opened from captures already on
              disk.
            </Info>
          </span>
          <b>Idle</b>
        </span>
        <div className="bar">
          <i style={{ width: '0%' }} />
        </div>
        <span className="pc">&mdash;</span>
        <Btn disabled>Stop</Btn>
      </div>
      <div className="lane">
        <span className="what">
          <span className="lbl">Export</span>
          <b>{exportJob ? exportJob.message || exportJob.phase || 'Working' : 'Idle'}</b>
        </span>
        <div className={`bar${running ? ' warnfill' : ''}`}>
          <i style={{ width: `${pct ?? 0}%` }} />
        </div>
        <span className="pc">{pct == null ? '—' : `${pct} %`}</span>
        <Btn disabled={!running} onClick={onCancelExport}>
          Cancel
        </Btn>
      </div>
    </div>
  );
}

/* ── the roll, along the floor ──────────────────────────────────────────── */

export function Filmstrip({ roll, selected, onSelect, children }) {
  const ref = useRef(null);
  useEffect(() => {
    ref.current?.querySelector(`[data-i="${selected}"]`)?.scrollIntoView({
      block: 'nearest',
      inline: 'center',
      behavior: 'smooth',
    });
  }, [selected]);

  if (!roll) return null;
  const accepted = roll.frames.filter((f) => !f.params?.rejected).length;
  const rejected = roll.frames.length - accepted;

  return (
    <div className="strip">
      <div className="striphead">
        {children}
        <span className="sp" />
        <Chip tone="ok">{accepted} accepted</Chip>
        {rejected ? <Chip>{rejected} rejected</Chip> : null}
      </div>
      <div className="thumbs" ref={ref} role="listbox" aria-label="Frames in this roll">
        {roll.frames.map((f) => (
          <button
            key={f.index}
            type="button"
            data-i={f.index}
            role="option"
            aria-selected={selected === f.index}
            aria-label={`Frame ${f.index + 1}`}
            title={`Frame ${f.index + 1} — ${f.summary}`}
            className={`th${selected === f.index ? ' on' : ''}${f.params?.rejected ? ' no' : ''}`}
            onClick={() => onSelect(f.index)}
          >
            <img src={frameUrl(roll.id, f.index, 'thumb', f.version)} alt="" loading="lazy" />
            <b>{f.index + 1}</b>
            {f.adjusted ? <i className="mark adj" title="adjusted" /> : null}
            {f.confidence === 'low' ? <i className="mark" title="low boundary confidence" /> : null}
          </button>
        ))}
      </div>
    </div>
  );
}

/* ── the vendor's button-step slider ────────────────────────────────────── */

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/** −8…+8 in quarter steps. Zero is the roll's own scene balance and is marked
 *  with a detent; the fill grows from it, not from the left end. */
export function StepTrack({ value, min = -8, max = 8, step = 0.25, onInput, onCommit, disabled }) {
  const ref = useRef(null);
  const pos = (v) => ((v - min) / (max - min)) * 100;
  const zero = pos(0);
  const at = pos(clamp(value, min, max));

  const from = useCallback(
    (clientX) => {
      const r = ref.current.getBoundingClientRect();
      const raw = min + ((clientX - r.left) / r.width) * (max - min);
      return clamp(Math.round(raw / step) * step, min, max);
    },
    [min, max, step],
  );

  const down = (e) => {
    if (disabled) return;
    e.preventDefault();
    ref.current.setPointerCapture(e.pointerId);
    onInput?.(from(e.clientX));
    const move = (ev) => onInput?.(from(ev.clientX));
    const up = (ev) => {
      ref.current?.releasePointerCapture?.(ev.pointerId);
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      onCommit?.(from(ev.clientX));
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };

  return (
    <div
      ref={ref}
      className="track"
      onPointerDown={down}
      role="slider"
      tabIndex={disabled ? -1 : 0}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuenow={value}
      aria-disabled={disabled || undefined}
      style={disabled ? { opacity: 0.45, cursor: 'not-allowed' } : undefined}
    >
      <span className="detent" />
      <span
        className="fill"
        style={{ left: `${Math.min(zero, at)}%`, width: `${Math.abs(at - zero)}%` }}
      />
      <span className="knob" style={{ left: `${at}%` }} />
    </div>
  );
}

export function Empty({ title, children, action }) {
  return (
    <div
      className="stage"
      style={{ flexDirection: 'column', gap: 14, textAlign: 'center' }}
    >
      <div className="title" style={{ fontSize: 21 }}>
        {title}
      </div>
      <p className="quiet" style={{ maxWidth: '46ch' }}>
        {children}
      </p>
      {action}
    </div>
  );
}

export function Spinner({ children }) {
  return (
    <span className="quiet" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span
        style={{
          width: 12,
          height: 12,
          borderRadius: '50%',
          border: '2px solid var(--content3)',
          borderTopColor: 'var(--primary)',
          animation: 'pkspin 0.8s linear infinite',
        }}
      />
      {children}
    </span>
  );
}
