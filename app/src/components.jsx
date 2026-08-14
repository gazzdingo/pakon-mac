// The Console — shared furniture.
//
// One page, tabs across the top, no wizard. Every class used here is defined
// in theme.css. A control gets a label, a value and a state — nothing here
// explains itself; there is no disclosure affordance left to explain into.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { frameUrl } from './api';

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

/* ── rails (used by the frame editor's tone bench) ──────────────────────── */

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

export const Grp = ({ title, children }) => (
  <div className="grp">
    {title ? <span className="lbl">{title}</span> : null}
    {children}
  </div>
);

/** Segmented control. An option may be disabled. */
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

export function ThemeSwitch({ dark, setDark }) {
  return (
    <button
      type="button"
      className="themeswap"
      aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
      onClick={() => setDark(!dark)}
    >
      {SUN}
      {MOON}
    </button>
  );
}

/* ── the roll, along the floor of the frame editor ──────────────────────── */

export function FilmBand({ roll, selected, onSelect }) {
  const ref = useRef(null);
  useEffect(() => {
    ref.current?.querySelector(`[data-i="${selected}"]`)?.scrollIntoView({
      block: 'nearest',
      inline: 'center',
      behavior: 'smooth',
    });
  }, [selected]);

  if (!roll) return null;

  return (
    <div className="thumbs" ref={ref} role="listbox" aria-label="Frames in this roll" style={{ padding: '9px 16px 11px', borderTop: '1px solid var(--divider)', background: 'var(--content1)' }}>
      {roll.frames.map((f) => (
        <button
          key={f.index}
          type="button"
          data-i={f.index}
          role="option"
          aria-selected={selected === f.index}
          aria-label={`Frame ${f.index + 1}`}
          className={`th${selected === f.index ? ' on' : ''}${f.params?.rejected ? ' no' : ''}`}
          onClick={() => onSelect(f.index)}
        >
          <img src={frameUrl(roll.id, f.index, 'thumb', f.version)} alt="" loading="lazy" />
          <b>{f.index + 1}</b>
          {f.adjusted ? <i className="mark adj" title="adjusted" /> : null}
        </button>
      ))}
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

/** A slider whose zero (or, for a 0-200 gain, its centre at 100) is marked
 *  with a detent, same as StepTrack — used for the fuller Brightness /
 *  Contrast / Saturation / Highlights / Shadows / Sharpening bench, which
 *  StepTrack's fixed −8…+8 range doesn't fit. */
export function AdjustmentSlider({ label, value, min, max, step = 1, onInput, onCommit, disabled, zeroValue = 0 }) {
  const ref = useRef(null);

  const clamp = (v) => Math.max(min, Math.min(max, v));

  const from = useCallback(
    (clientX) => {
      const r = ref.current.getBoundingClientRect();
      const raw = min + ((clientX - r.left) / r.width) * (max - min);
      return clamp(Math.round(raw / step) * step);
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

  const at = ((value - min) / (max - min)) * 100;
  const zero = ((zeroValue - min) / (max - min)) * 100;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span className="lbl">{label}</span>
        <span className="num" style={{ fontSize: 11, color: 'var(--mute)' }}>
          {typeof value === 'number' ? value.toFixed(step < 1 ? 2 : 0) : value}
        </span>
      </div>
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
        <span className="detent" style={{ left: `${zero}%` }} />
        <span
          className="fill"
          style={{ left: `${Math.min(zero, at)}%`, width: `${Math.abs(at - zero)}%` }}
        />
        <span className="knob" style={{ left: `${at}%` }} />
      </div>
    </div>
  );
}

/* ── the last line ──────────────────────────────────────────────────────── */

/** Catch a render throw and show it, instead of unmounting the application.
 *
 *  React unmounts the whole tree when a render throws and there is no boundary
 *  above it. There was none — `createRoot(...).render(<App/>)` and nothing
 *  else — so one bad shape from the backend took the window to blank.
 *
 *  This does not pretend to recover. It says what broke, keeps the stack where
 *  it can be copied, and offers the ways out. The work is in the backend and
 *  the sidecars, not in this tree, so a reload costs nothing but the
 *  selection — and saying so is most of the value of the screen. */
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null, info: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // main.js forwards renderer console errors to the terminal, so this is
    // also how the crash reaches anyone running the app from a shell.
    console.error('renderer crashed', error, info?.componentStack);
    this.setState({ info });
  }

  render() {
    const { error, info } = this.state;
    if (!error) return this.props.children;
    return (
      <div className="app" style={{ display: 'grid', placeItems: 'center', padding: 24 }}>
        <div style={{ maxWidth: '78ch', width: '100%' }}>
          <div className="title" style={{ color: 'var(--danger-ink)', marginBottom: 8 }}>
            The window stopped rendering
          </div>
          <p className="quiet" style={{ marginBottom: 12 }}>
            Your work is not in this window. Frame adjustments live in the
            backend and are written to sidecars outside the workspace, so
            reloading loses nothing but which frame was selected.
          </p>
          <pre
            className="num"
            style={{
              fontSize: 11,
              color: 'var(--mute)',
              background: 'var(--content2)',
              borderRadius: 'var(--r-sm)',
              padding: '10px 12px',
              maxHeight: 260,
              overflow: 'auto',
              whiteSpace: 'pre-wrap',
              marginBottom: 12,
            }}
          >
            {String(error?.stack || error)}
            {info?.componentStack || ''}
          </pre>
          <div style={{ display: 'flex', gap: 8 }}>
            <Btn variant="primary" onClick={() => window.location.reload()}>
              Reload the window
            </Btn>
            <Btn variant="flat" onClick={() => this.setState({ error: null, info: null })}>
              Try to carry on
            </Btn>
            <Btn
              variant="flat"
              onClick={() =>
                navigator.clipboard?.writeText(
                  `${error?.stack || error}\n${info?.componentStack || ''}`,
                )
              }
            >
              Copy the error
            </Btn>
          </div>
        </div>
      </div>
    );
  }
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
