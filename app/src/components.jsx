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

/** The product, in the order it happens. One roll of film goes scan → edit →
 *  export, and these were three unrelated screens reached from a mode switcher
 *  that put Diagnostics between Config and Export as though they were peers. */
export const STEPS = [
  ['scan', 'Scan'],
  ['review', 'Edit'],
  ['export', 'Export'],
];

/** Not steps. Reference screens about the machine and the pipeline, reachable
 *  at any point and part of no sequence — so they sit in the top bar, away
 *  from the three. Calibration had no way in at all before this. */
export const TOOLS = [
  ['config', 'Config'],
  ['diagnostics', 'Diagnostics'],
  ['calibration', 'Calibration'],
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

export const Grp = ({ title, children }) => (
  <div className="grp">
    {title ? (
      <span className="lbl" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {title}
      </span>
    ) : null}
    {children}
  </div>
);

/** Label, control, value. No subtext. */
export const Field = ({ label, children, value }) => (
  <div className="field">
    {label ? (
      <span className="lbl" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {label}
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

export function Toggle({ on, disabled, onChange, children }) {
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
      </span>
    </label>
  );
}

/** One row per subsystem: name, verdict. `tone` is good | warn | bad | na. */
export function State({ rows }) {
  return (
    <dl style={{ display: 'flex', flexDirection: 'column' }}>
      {rows.map(([name, value, tone]) => (
        <div className="st" key={name}>
          <dt>
            {name}
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

/** The roll's identity, and the way out to the reference screens. Both persist
 *  across all three steps: which roll you are working on is the one fact that
 *  is true on Scan, Edit and Export alike, so it does not move. */
export function TopBar({ mode, setMode, roll, dark, setDark }) {
  return (
    <header className="top">
      <span
        className="brand"
        style={{ WebkitAppRegion: 'drag', paddingLeft: window.pakon?.platform === 'darwin' ? 62 : 0 }}
      >
        PAKON&nbsp;F&#8209;135&nbsp;PLUS
      </span>
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
      <nav className="modes" aria-label="Reference">
        {TOOLS.map(([id, label]) => (
          <button key={id} type="button" className={`mode${mode === id ? ' on' : ''}`} onClick={() => setMode(id)}>
            {label}
          </button>
        ))}
      </nav>
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

/** What came back from the panic stop, in one line. */
function stopNote(r) {
  if (!r) return null;
  if (r.error) return { tone: 'bad', text: String(r.error).slice(0, 90) };
  if (r.absent) return { tone: '', text: 'No scanner on USB — nothing to stop.' };
  if (r.motor)
    return {
      tone: 'ok',
      text: `Transport stopped${r.lamp ? ', lamp off' : ''}${
        r.foreign?.signalled ? ` (pid ${r.foreign.owner_pid})` : ''
      }.`,
    };
  return {
    tone: 'bad',
    text: (r.errors && r.errors[0]) || 'The stop was not acknowledged.',
  };
}

/** The three steps, and where each one is up to.
 *
 *  This replaces the twin capture/export lanes rather than sitting beside
 *  them. Those lanes were already two thirds of this bar — capture is step 1's
 *  progress and export is step 3's — with the one step nobody could see a lane
 *  for (edit) missing between them, and a mode switcher above that listed the
 *  three alongside Config and Diagnostics as though all five were peers. One
 *  bar now says which step you are on, what each step is doing, and — for a
 *  step that cannot be reached yet — what it is waiting for, in place, rather
 *  than greying out and saying nothing.
 *
 *  Rows come from `stepRows` in App.jsx. This draws them and owns nothing but
 *  the stop.
 *
 *  STOP IS NOT PART OF THE NAVIGATION. It lives in step 1's cell and is
 *  therefore on screen from all three steps, always enabled, exactly as it was
 *  in the capture lane. Gating it behind being on the Scan step would put it
 *  back where it was before it was un-gated: unreachable at the moment it
 *  matters most.
 */
export function Steps({ mode, setMode, rows, onStopScan }) {
  const [stopping, setStopping] = useState(false);
  const [stopped, setStopped] = useState(null);
  const scanning = !!rows.find((r) => r.id === 'scan')?.running;
  // A new scan replaces the last stop's verdict; it is no longer the truth.
  useEffect(() => {
    if (scanning) setStopped(null);
  }, [scanning]);
  const note = stopNote(stopped);

  return (
    <nav className="steps" aria-label="Steps">
      {rows.map((r, i) => {
        const current = mode === r.id;
        /* The step you are standing on is never shut, even if what it needs
           has gone away underneath you. Being unable to leave the screen you
           are already on is not a state this bar may create. */
        const shut = !r.ok && !current;
        const isScan = r.id === 'scan';
        const showNote = isScan && !scanning && (stopping || !!note);
        const text = showNote ? (stopping ? 'Stopping…' : note.text) : r.state;
        return (
          <div key={r.id} className={`step${current ? ' on' : ''}${shut ? ' shut' : ''}`}>
            <button
              type="button"
              className="stepgo"
              disabled={shut || undefined}
              aria-current={current ? 'step' : undefined}
              onClick={() => setMode(r.id)}
            >
              <span className="stepno">{i + 1}</span>
              <span className="what">
                <span className="lbl">{r.label}</span>
                <b className={showNote ? (note.tone === 'bad' ? 'bad' : '') : r.tone || ''}>
                  {text}
                </b>
              </span>
              <span className={`bar${r.warn ? ' warnfill' : ''}`}>
                <i style={{ width: `${r.pct || 0}%` }} />
              </span>
              <span className="pc">{r.pc ?? '—'}</span>
            </button>

            {isScan ? (
              <>
                <Btn
                  variant={scanning ? 'danger' : ''}
                  onClick={async () => {
                    setStopping(true);
                    setStopped(null);
                    try {
                      setStopped((await onStopScan?.()) || {});
                    } finally {
                      setStopping(false);
                    }
                  }}
                >
                  {stopping ? 'Stopping…' : 'Stop'}
                </Btn>
              </>
            ) : null}

            {r.id === 'export' ? (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                <Btn disabled>Cancel</Btn>
                <Info side="left">
                  <b>Coming soon</b>
                </Info>
              </span>
            ) : null}
          </div>
        );
      })}
    </nav>
  );
}

/* ── the roll, along the floor ──────────────────────────────────────────── */

export function Filmstrip({ roll, selected, onSelect, onOpenFraming, onOpenContactSheet, children }) {
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
        {onOpenFraming ? (
          <button
            type="button"
            className="action-circle-btn"
            style={{ width: 28, height: 28 }}
            onClick={onOpenFraming}
          >
            <svg viewBox="0 0 24 24"><path d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none"/></svg>
          </button>
        ) : null}
        {onOpenContactSheet ? (
          <button
            type="button"
            className="action-circle-btn"
            style={{ width: 28, height: 28 }}
            onClick={onOpenContactSheet}
          >
            <svg viewBox="0 0 24 24"><path d="M4 4h4v4H4V4zm8 0h4v4h-4V4zm8 0h4v4h-4V4zM4 12h4v4H4v-4zm8 0h4v4h-4v-4zm8 0h4v4h-4v-4zM4 20h4v4H4v-4zm8 0h4v4h-4v-4zm8 0h4v4h-4v-4z" fill="currentColor"/></svg>
          </button>
        ) : null}
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
            className={`th${selected === f.index ? ' on' : ''}${f.params?.rejected ? ' no' : ''}`}
            onClick={() => onSelect(f.index)}
          >
            <img src={frameUrl(roll.id, f.index, 'thumb', f.version)} alt="" loading="lazy" />
            <b>{f.index + 1}</b>
            {f.adjusted ? <i className="mark adj" /> : null}
            {f.confidence === 'low' ? <i className="mark" /> : null}
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

export function AdjustmentSlider({ label, value, min, max, step = 1, onInput, onCommit, disabled, zeroValue = 0 }) {
  const ref = useRef(null);

  const clamp = (v) => Math.max(min, Math.min(max, v));

  const from = useCallback(
    (clientX) => {
      const r = ref.current.getBoundingClientRect();
      const raw = min + ((clientX - r.left) / r.width) * (max - min);
      return clamp(Math.round(raw / step) * step);
    },
    [min, max, step]
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
    <div className="adj-slider" style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
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

/* ── the last line ──────────────────────────────────────────────────────── */

/** Catch a render throw and show it, instead of unmounting the application.
 *
 *  React unmounts the whole tree when a render throws and there is no boundary
 *  above it. There was none — `createRoot(...).render(<App/>)` and nothing
 *  else — so one bad shape from the backend took the window to blank. The one
 *  that did it: apply-to-roll's `needs_confirm` payload assigned to `roll`,
 *  then `roll.frames.find(...)` on an object that has no `frames`. The error
 *  went to a devtools console nobody had open.
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
