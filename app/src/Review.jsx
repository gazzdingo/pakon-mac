// Step 2 — edit and view the roll. design/variants/console-review.html.
//
// Same furniture as Scan with the centre swapped: settings rail left, the
// photograph on a neutral ground in the middle, the correction bench right,
// the roll along the floor. This is where the time goes, so it gets the
// widest centre of the three steps and the whole filmstrip along the floor.
//
// Two-tier render, from measurement on this machine (tools/pakon_render.py
// check, 694 MB / 57 900 lines / 47 frames): quarter-res preview 39 ms,
// half-res display 147 ms. A drag runs on the preview path and settles to
// display when it stops. Full quality (630 ms) is an export-only path — it is
// never rendered interactively.
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Btn,
  Chip,
  Field,
  Filmstrip,
  Grp,
  Info,
  Rail,
  RailHead,
  Seg,
  Spinner,
  State,
  StepTrack,
  Toggle,
} from './components';
import * as api from './api';

const CHANNELS = [
  ['red', 'R–C', 'R', 'Cyan −8', '+8 Red'],
  ['green', 'G–M', 'G', 'Magenta −8', '+8 Green'],
  ['blue', 'B–Y', 'B', 'Yellow −8', '+8 Blue'],
  ['density', 'Density', 'D', 'Darker −8', '+8 Lighter'],
];

const fmt = (v) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v || 0).toFixed(2);

/* Where a roll's DX came from. No screen distinguished a typed DX from a
   measured one — this field's own info text said "Typed, not read" even when
   the value had come off the DX board — and `list_captures` has been computing
   `dx_read` all along with nothing consuming it. Keyed by `roll.dx_source`,
   which pakon_render now records. */
const DX_SOURCES = {
  typed: {
    short: 'typed',
    long: (
      <>
        <b>Typed by the operator</b>, for this open. A deliberate statement about
        the roll that was in the gate.
      </>
    ),
  },
  board: {
    short: 'read by the board',
    long: (
      <>
        <b>Read by the DX sensor board</b> during the scan, from the capture's{' '}
        <span className="num">.dx.json</span>. Only a code word that passed parity
        and was unambiguous counts as a reading at all, so this is rare.
      </>
    ),
  },
  'sidecar:typed': {
    short: 'typed at scan time',
    long: (
      <>
        <b>Typed by the operator when the scan was started</b>, and recorded in
        the capture's <span className="num">.scan.json</span>. Nobody had to
        remember it: it was written down before the transport moved.
      </>
    ),
  },
  'sidecar:board': {
    short: 'board, at scan time',
    long: (
      <>
        <b>Read by the DX board during the scan</b> and recorded in the capture's{' '}
        <span className="num">.scan.json</span>. Nothing was typed for this roll.
      </>
    ),
  },
  'sidecar:none': {
    short: 'sidecar, source unstated',
    long: (
      <>
        Recorded in the capture's <span className="num">.scan.json</span>, which
        does not say whether it was typed or read.
      </>
    ),
  },
  'sidecar:unknown': {
    short: 'sidecar, source unstated',
    long: (
      <>
        Recorded in the capture's <span className="num">.scan.json</span> by a
        version of the scan tool that did not record where it came from.
      </>
    ),
  },
  unresolved: {
    short: 'DOES NOT RESOLVE',
    long: (
      <>
        <b>This DX does not match any known film stock.</b> The film path is being
        used instead — see the notice below. It used to be swallowed silently,
        taking the film path with it.
      </>
    ),
  },
};

/* ── the plot: histogram of the 14-bit source, and nothing invented ─────── */

function Plot({ hist, channel }) {
  const W = 1000;
  const H = 620;
  const path = useMemo(() => {
    if (!hist) return null;
    const ch = ['r', 'g', 'b'];
    const max = Math.max(1, ...ch.flatMap((c) => hist.hist[c]));
    const line = (arr) =>
      arr
        .map((v, i) => `${((i / (arr.length - 1)) * W).toFixed(1)},${(H - (v / max) * H).toFixed(1)}`)
        .join(' ');
    const sum = hist.hist.r.map((_, i) => hist.hist.r[i] + hist.hist.g[i] + hist.hist.b[i]);
    const smax = Math.max(1, ...sum);
    const area =
      sum
        .map((v, i) => `${((i / (sum.length - 1)) * W).toFixed(1)},${(H - (v / smax) * H).toFixed(1)}`)
        .join(' ') + ` ${W},${H} 0,${H}`;
    return { line, area };
  }, [hist]);

  if (!hist || !path) return <div className="plotbox" />;

  const shown = channel === 'rgb' ? ['r', 'g', 'b'] : [channel];
  const col = { r: 'var(--chR)', g: 'var(--chG)', b: 'var(--chB)' };

  return (
    <svg
      className="plotbox"
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      role="img"
      aria-label="RGB histogram of the frame's 14-bit source"
    >
      <g stroke="var(--grid)" strokeWidth="1" vectorEffect="non-scaling-stroke">
        <path d={`M250,0V${H}M500,0V${H}M750,0V${H}M0,155H${W}M0,310H${W}M0,465H${W}`} />
      </g>
      {channel === 'rgb' ? <polygon points={path.area} fill="var(--mass)" /> : null}
      {shown.map((c) => (
        <polyline
          key={c}
          points={path.line(hist.hist[c])}
          fill="none"
          stroke={col[c]}
          strokeWidth="1.4"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      ))}
    </svg>
  );
}

/* ── boundary editor — opened from the flag, closed by default ──────────── */

function Boundaries({ roll, selected, onSelect, onEdit, busy, onClose }) {
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
        <span className="lbl">Boundaries</span>
        <span className="quiet">drag to move · the two frames re-render on release</span>
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

/* ── apply to roll: the confirmation, which is the whole point of it ─────── */

/** The backend plans this operation before it does it, and names what will be
 *  lost. A count of frames is not enough — "12 frames, 5 of them already
 *  adjusted" is the sentence that makes someone stop — so the plan's own
 *  numbers are shown rather than a generic "are you sure". */
function ApplySheet({ plan, busy, onCancel, onConfirm }) {
  if (!plan) return null;
  const changing = plan.frames_changing || [];
  const overwriting = plan.frames_overwriting_adjustments || [];

  return (
    <div className="scrim" onMouseDown={(e) => e.target === e.currentTarget && !busy && onCancel()}>
      <div className="sheet">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
          <span className="title">Apply to roll</span>
          <span className="sp" />
          <Info side="left">
            This replaces the colour of every other frame in the roll. It is
            snapshotted first, so Undo puts it back — but only for this
            session, and only until another destructive edit pushes it off the
            stack.
          </Info>
        </div>

        <p style={{ marginBottom: 12, fontSize: 13 }}>{plan.message}</p>

        <div className="rows" style={{ marginBottom: 12, padding: '9px 11px', fontSize: 12.5 }}>
          <div style={{ display: 'flex', gap: 8 }}>
            <span style={{ flex: 1 }}>From frame</span>
            <span className="num">{(plan.from ?? 0) + 1}</span>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <span style={{ flex: 1 }}>Copying</span>
            <span className="num">{(plan.keys || []).join(', ')}</span>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <span style={{ flex: 1 }}>Frames changed</span>
            <span className="num">
              {changing.length} of {(plan.frames_total ?? 1) - 1}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <span style={{ flex: 1, color: overwriting.length ? 'var(--danger-ink)' : undefined }}>
              Hand adjustments replaced
            </span>
            <span className="num" style={{ color: overwriting.length ? 'var(--danger-ink)' : undefined }}>
              {overwriting.length}
            </span>
          </div>
        </div>

        {overwriting.length ? (
          <div
            style={{
              background: 'var(--danger-flat)',
              color: 'var(--danger-ink)',
              borderRadius: 'var(--r-sm)',
              padding: '9px 11px',
              marginBottom: 12,
              fontSize: 12,
            }}
          >
            Frames{' '}
            <span className="num">
              {overwriting.slice(0, 12).map((i) => i + 1).join(', ')}
              {overwriting.length > 12 ? ` +${overwriting.length - 12} more` : ''}
            </span>{' '}
            have been graded by hand. Their density and colour will be replaced.
          </div>
        ) : null}

        {!changing.length ? (
          <p className="quiet" style={{ marginBottom: 12 }}>
            Nothing would change — every other frame already carries these values.
          </p>
        ) : null}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Btn variant="flat" disabled={busy} onClick={onCancel}>
            Cancel
          </Btn>
          <Btn variant="primary" disabled={busy || !changing.length} onClick={onConfirm}>
            {busy ? 'Applying…' : `Apply to ${changing.length} frames`}
          </Btn>
        </div>
      </div>
    </div>
  );
}

/* ── screen ─────────────────────────────────────────────────────────────── */

export default function Review({
  roll,
  setRoll,
  rolls,
  sel,
  setSel,
  onPickRoll,
  onOpen,
  onGoExport,
  onOpenFraming,
  onOpenContactSheet,
  onGoScan,
  machine,
}) {
  const [pending, setPending] = useState(null);
  const [busy, setBusy] = useState(false);
  const [sharp, setSharp] = useState(false);
  const [chan, setChan] = useState('red');
  const [plotCh, setPlotCh] = useState('rgb');
  const [clipboard, setClipboard] = useState(null);
  const [hist, setHist] = useState(null);
  const [bounds, setBounds] = useState(false);
  const [applyPlan, setApplyPlan] = useState(null);
  // Why the frame would not render, and a nonce so Retry re-requests the same
  // URL (the browser will not refetch an identical src on its own).
  const [imgFailed, setImgFailed] = useState(null);
  const [imgNonce, setImgNonce] = useState(0);
  // Clear the failure when we navigate, or one bad frame would look like a
  // whole broken roll.
  // `sharp`, not the `scale` it derives -- scale is declared further down, and
  // naming it here reaches it in its temporal dead zone.
  useEffect(() => { setImgFailed(null); }, [roll.id, sel, sharp]);
  const settle = useRef(null);

  const frame = roll?.frames?.[sel];
  const params = pending ?? frame?.params ?? {};

  useEffect(() => {
    setSharp(false);
    clearTimeout(settle.current);
    settle.current = setTimeout(() => setSharp(true), 240);
    return () => clearTimeout(settle.current);
  }, [frame?.version, sel]);

  useEffect(() => {
    if (!roll || !frame) return undefined;
    let alive = true;
    setHist(null);
    api
      .get(api.histUrl(roll.id, sel))
      .then((h) => alive && setHist(h))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [roll?.id, sel, frame?.version]);

  const commit = useCallback(
    async (next) => {
      if (!roll) return;
      setBusy(true);
      try {
        setRoll(await api.setParams(roll.id, sel, next));
      } finally {
        setPending(null);
        setBusy(false);
      }
    },
    [roll, sel, setRoll],
  );

  const editBoundary = useCallback(
    async (body) => {
      setBusy(true);
      try {
        setRoll(await api.boundary(roll.id, body));
      } finally {
        setBusy(false);
      }
    },
    [roll, setRoll],
  );

  const APPLY_KEYS = ['density', 'red', 'green', 'blue'];

  /* Ask the backend what this would do, and show that. The reply is a plan,
     not a roll — handing it to setRoll is what used to unmount the tree. */
  const askApply = useCallback(async () => {
    setBusy(true);
    try {
      const plan = await api.planApplyToRoll(roll.id, sel, APPLY_KEYS);
      if (plan.needs_confirm) setApplyPlan(plan);
      // A backend that answered with a roll has already applied it; that is
      // not a shape this UI asks for, but it is a shape it must not misread.
      else if (plan.frames) setRoll(plan);
    } finally {
      setBusy(false);
    }
  }, [roll, sel]);

  const doApply = useCallback(async () => {
    setBusy(true);
    try {
      const r = await api.applyToRoll(roll.id, sel, APPLY_KEYS);
      if (r.frames) setRoll(r);
      setApplyPlan(null);
    } finally {
      setBusy(false);
    }
  }, [roll, sel, setRoll]);

  const undo = useCallback(async () => {
    setBusy(true);
    try {
      const r = await api.undoRoll(roll.id);
      if (r.frames) setRoll(r);
    } finally {
      setBusy(false);
    }
  }, [roll, setRoll]);

  useEffect(() => {
    if (!roll) return undefined;
    const onKey = (e) => {
      if (e.target.tagName === 'INPUT' || e.metaKey || e.ctrlKey) return;
      const step = e.shiftKey ? 1 : 0.25;
      const k = e.key;
      const bump = (d) => {
        e.preventDefault();
        commit({ ...params, [chan]: +((params[chan] || 0) + d).toFixed(2) });
      };
      if (k === 'ArrowRight' || k === 'j') setSel(Math.min(sel + 1, roll.frames.length - 1));
      else if (k === 'ArrowLeft' || k === 'k') setSel(Math.max(sel - 1, 0));
      else if (k === 'r' || k === 'R') setChan('red');
      else if (k === 'g' || k === 'G') setChan('green');
      else if (k === 'b' || k === 'B') setChan('blue');
      else if (k === 'd' || k === 'D') setChan('density');
      else if (k === '+' || k === '=') bump(step);
      else if (k === '-' || k === '_') bump(-step);
      else if (k === '0') {
        e.preventDefault();
        commit({ ...params, [chan]: 0 });
      } else if (k === 'Delete' || k === 'Backspace') {
        e.preventDefault();
        commit({ ...params, rejected: true });
      } else if (k === 'Insert') {
        e.preventDefault();
        commit({ ...params, rejected: false });
      } else if (k === 'c') setClipboard({ ...params });
      else if (k === 'v' && clipboard) commit({ ...clipboard, rejected: params.rejected });
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [roll, sel, params, chan, clipboard, commit, setSel]);

  if (!roll) {
    /* Step 2 is normally not reachable at all without a capture — the step bar
       says so and does not let you in — so this is the fallback for a roll
       that goes away underneath someone standing here. It points back at the
       step that makes one and does not restate the machine's condition, which
       step 1 and the step bar both already carry. */
    return (
      <div className="body" style={{ gridTemplateColumns: '280px minmax(0,1fr)' }}>
        <Rail side="l">
          <RailHead title="Rolls" />
          <div className="railfoot">
            <Btn variant="primary big" onClick={onGoScan}>
              ← Scan
            </Btn>
            <Btn variant="flat big" onClick={onOpen}>
              Open capture…
            </Btn>
          </div>
        </Rail>
        <div className="stage" style={{ flexDirection: 'column', gap: 14 }}>
          <span className="title">No capture open</span>
          <span className="quiet">Step 2 needs one. Scan a strip, or open a capture.</span>
        </div>
      </div>
    );
  }

  const scale = sharp ? 'display' : 'preview';
  const lowConf = roll.frames.find((f) => f.confidence === 'low');
  const val = params[chan] || 0;
  const chanDef = CHANNELS.find(([k]) => k === chan);

  return (
    <>
      <ApplySheet
        plan={applyPlan}
        busy={busy}
        onCancel={() => setApplyPlan(null)}
        onConfirm={doApply}
      />
      <div className="body" style={{ gridTemplateColumns: '280px minmax(0,1fr) 340px' }}>
        {/* ── settings rail — the same furniture Scan uses ── */}
        <Rail side="l" aria-label="Capture settings">
          <RailHead title="Roll">
            <Btn style={{ height: 24, padding: '0 8px', fontSize: 12 }} onClick={onOpen}>
              Open…
            </Btn>
          </RailHead>

          <Grp>
            <div className="rows">
              {rolls.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  className={r.id === roll.id ? 'on' : ''}
                  onClick={() => onPickRoll(r.id)}
                >
                  <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {r.name}
                  </span>
                  <span className="num" style={{ fontSize: 11, color: 'var(--faint)' }}>
                    {r.frames.length}
                  </span>
                </button>
              ))}
            </div>
          </Grp>

          <Grp title="Capture settings">
            <Field
              label="Film path"
              info={
                <>
                  Fixed when the roll was opened. A capture carries no DX packets, so the stock is
                  stated by hand and the decode path refuses to assume one.
                </>
              }
            >
              <Seg
                ariaLabel="Film path"
                value={roll.film_path || 'ColNeg'}
                options={[
                  ['ColNeg', 'Colour neg', true],
                  ['BnW', 'B&W', true],
                  ['POSITIVE', 'Positive', true],
                ]}
              />
            </Field>

            <Field
              label="Resolution"
              value="2000 × 3000"
              info={
                <>
                  <b>Base 16 only.</b> The decoder accepts <span className="num">6000</span>-word
                  lines, and the committed calibration tables were captured at base 16. Base 4 and 8
                  would need their own dark and gain references and a decoder that handles their line
                  length.
                </>
              }
            >
              <Seg
                ariaLabel="Resolution"
                value="16"
                options={[
                  ['4', 'Base 4', true],
                  ['8', 'Base 8', true],
                  ['16', 'Base 16', true],
                ]}
              />
            </Field>

            <Toggle
              on
              disabled
              info={
                <>
                  The Ansel preference path. It is a <b>stand-in</b> —{' '}
                  <span className="num">SETSHIFTS_12_PORTED = False</span> — so the tone it produces
                  is not yet Kodak's.
                </>
              }
            >
              Premium colour path
            </Toggle>

            <Toggle
              on={false}
              disabled
              info={
                <>
                  Calibrated on this unit — <span className="num">Ir 4</span>, duty{' '}
                  <span className="num">0.887</span>, clamp <span className="num">≤ 8</span> — and
                  never run. An infrared line is <span className="num">8000</span> words; the decoder
                  takes <span className="num">6000</span>.
                </>
              }
            >
              Digital ICE
            </Toggle>

            {/* This said "Typed, not read." unconditionally — including for a
                value that came off the DX board, which is the one thing this
                field exists to distinguish. `roll.dx_source` now carries the
                provenance and this reports it instead of asserting one. */}
            <Field
              label="DX"
              value={roll.dx ? DX_SOURCES[roll.dx_source]?.short || roll.dx_source || 'source unknown' : null}
              info={
                <>
                  {DX_SOURCES[roll.dx_source]?.long || (
                    <>
                      Where this DX came from was not recorded — the roll was opened
                      before provenance was tracked. Re-open the capture to resolve it.
                    </>
                  )}
                  <br />
                  <br />
                  A typed DX outranks the board's reading: captures carry no DX
                  packets, and <span className="num">tools/dx_decode.py</span> has
                  never been validated against a real roll, so a code off the board
                  is evidence rather than ground truth.
                </>
              }
            >
              <div className="inp">
                {roll.dx || '—'}
                <span className="sp" />
                <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--mute)' }}>
                  {roll.stock?.name || roll.film_path}
                </span>
              </div>
            </Field>
          </Grp>

          {/* What the open could not resolve, or resolved for you. An exposure
              triad the committed dark/gain tables are not valid for, a frame
              pitch that disagrees with the recorded speed, a DX that did not
              look up, a film path taken from the sidecar rather than chosen.
              Each of these used to be a silent default. */}
          {roll.warnings?.length ? (
            <Grp title="Notices">
              <div className="rows" style={{ padding: '9px 11px', display: 'grid', gap: 8 }}>
                {roll.warnings.map((w, i) => (
                  <span
                    key={i}
                    style={{ fontSize: 12, lineHeight: 1.45, color: 'var(--warn-ink)' }}
                  >
                    {w}
                  </span>
                ))}
              </div>
            </Grp>
          ) : null}

          <Grp title="Machine">
            <State rows={machine} />
          </Grp>
        </Rail>

        {/* ── centre ── */}
        <div className="centre">
          <div className="actbar">
            <span className="title">Frame {sel + 1}</span>
            <span className="quiet">
              of <span className="num" style={{ fontSize: 12 }}>{roll.frames.length}</span>
              {roll.stock?.name ? ` · ${roll.stock.name}` : ''}
            </span>
            {busy ? <Spinner /> : null}
            <span className="sp" />
            {params.rejected ? (
              <Chip tone="bad" dot>
                Rejected
              </Chip>
            ) : null}
            <Btn variant="flat" onClick={() => commit({ ...params, rejected: true })} disabled={params.rejected}>
              Reject <kbd>Del</kbd>
            </Btn>
            <Btn variant="primary" onClick={() => commit({ ...params, rejected: false })} disabled={!params.rejected}>
              Accept <kbd style={{ background: 'rgba(255,255,255,.22)', color: '#fff' }}>Ins</kbd>
            </Btn>
          </div>

          <main className="stage">
            {/* A frame that will not render must SAY so. Without onError the
                <img> fails silently and the stage renders empty -- which reads
                as "no image yet" when it actually means the backend refused,
                e.g. FindDmin finding no film base. Silence here sent the owner
                looking for a UI bug that was server-side. */}
            {imgFailed ? (
              <div className="stage-fail">
                <b>Frame did not render</b>
                <span className="quiet">{imgFailed}</span>
                <Btn variant="flat" onClick={() => { setImgFailed(null); setImgNonce((n) => n + 1); }}>
                  Retry
                </Btn>
              </div>
            ) : (
              <img
                key={`${roll.id}-${sel}-${frame.version}-${scale}-${imgNonce}`}
                className="photo"
                src={api.frameUrl(roll.id, sel, scale, frame.version)}
                alt={`Frame ${sel + 1}`}
                style={{ opacity: params.rejected ? 0.4 : 1 }}
                onError={() => api.frameError(roll.id, sel, scale, frame.version).then(setImgFailed)}
              />
            )}
          </main>

          <div className="editbar">
            <span className="lbl">Rotate</span>
            <Btn variant="flat" onClick={() => commit({ ...params, rotate: ((params.rotate || 0) + 270) % 360 })}>
              Left
            </Btn>
            <Btn variant="flat" onClick={() => commit({ ...params, rotate: ((params.rotate || 0) + 180) % 360 })}>
              180°
            </Btn>
            <Btn variant="flat" onClick={() => commit({ ...params, rotate: ((params.rotate || 0) + 90) % 360 })}>
              Right
            </Btn>
            <span className="lbl" style={{ marginLeft: 8 }}>
              Flip
            </span>
            <Btn variant={params.flip_h ? 'primary' : 'flat'} onClick={() => commit({ ...params, flip_h: !params.flip_h })}>
              Horizontal
            </Btn>
            <Btn variant={params.flip_v ? 'primary' : 'flat'} onClick={() => commit({ ...params, flip_v: !params.flip_v })}>
              Vertical
            </Btn>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
              <Btn disabled>Crop</Btn>
              <Info side="left">
                The render engine takes a crop rectangle, and nothing in this window can draw one. No
                marquee tool is implemented.
              </Info>
            </span>
            <span className="sp" />
            <span className="quiet" style={{ whiteSpace: 'nowrap' }}>
              {sharp ? 'half-res' : 'quarter-res'} · full quality at export
            </span>
          </div>
        </div>

        {/* ── the correction bench ── */}
        <Rail side="r" aria-label="Frame corrections">
          <RailHead title="Tone">
            <span className="itabs">
              {[
                ['rgb', 'RGB', ''],
                ['r', 'R', 'r'],
                ['g', 'G', 'g'],
                ['b', 'B', 'b'],
              ].map(([id, label, cls]) => (
                <button
                  key={id}
                  type="button"
                  className={`it ${cls}${plotCh === id ? ' on' : ''}`}
                  onClick={() => setPlotCh(id)}
                >
                  {label}
                </button>
              ))}
            </span>
          </RailHead>

          <Grp>
            <Plot hist={hist} channel={plotCh} />
            <div className="clip">
              <span>
                shadows <i>{hist ? `${hist.clipped_shadow_pct?.toFixed(2) ?? '0.00'} %` : '—'}</i>
              </span>
              <span>
                Dmin{' '}
                <i>{hist ? hist.dmin.map((v) => v.toFixed(0)).join(' · ') : '—'}</i>
              </span>
              <b>
                <span>
                  highlights <i>{hist ? `${hist.clipped_pct.toFixed(2)} %` : '—'}</i>
                </span>
              </b>
            </div>
          </Grp>

          <Grp
            title="Colour"
            info={
              <>
                The vendor's own per-frame control: density plus three colour offsets, in
                button-steps of <span className="num">75.0</span> code values, range{' '}
                <span className="num">−8…+8</span> in quarters. Zero is the roll's own scene balance,
                still live underneath — it is not replaced.
              </>
            }
          >
            <div className="chanrow">
              {CHANNELS.map(([key, label, k]) => (
                <button
                  key={key}
                  type="button"
                  className={`chan${chan === key ? ' on' : ''}`}
                  onClick={() => setChan(key)}
                >
                  {label} <span className="k">{k}</span>
                  <span className="v">{fmt(params[key] || 0)}</span>
                </button>
              ))}
            </div>

            <div className="sliderline">
              <div>
                <StepTrack
                  value={val}
                  onInput={(v) => setPending({ ...params, [chan]: v })}
                  onCommit={(v) => commit({ ...params, [chan]: v })}
                />
                <div className="ends">
                  <span>{chanDef[3]}</span>
                  <span>0</span>
                  <span>{chanDef[4]}</span>
                </div>
              </div>
              <span className="value">{fmt(val)}</span>
            </div>

            <div className="keys">
              <span>
                <kbd>R</kbd>
                <kbd>G</kbd>
                <kbd>B</kbd>
                <kbd>D</kbd>select
              </span>
              <span>
                <kbd>−</kbd>
                <kbd>+</kbd>±0.25
              </span>
              <span>
                <kbd>⇧</kbd>±1.00
              </span>
              <span>
                <kbd>0</kbd>zero
              </span>
              <span>
                <kbd>C</kbd>
                <kbd>V</kbd>copy
              </span>
            </div>

            <div style={{ display: 'flex', gap: 6 }}>
              <Btn variant="flat" style={{ flex: 1 }} onClick={() => api.resetFrame(roll.id, sel).then(setRoll)}>
                Reset frame
              </Btn>
              <Btn variant="flat" style={{ flex: 1 }} disabled={busy} onClick={askApply}>
                Apply to roll…
              </Btn>
            </div>

            {/* Undo. The backend has snapshotted every destructive edit since
                undo was written and served POST roll/<id>/undo the whole time,
                and nothing in the app had ever called it — while
                apply-to-roll's own confirmation promised "This can be undone".
                It says what it will undo, because "Undo" alone is not an
                answer to "undo what". */}
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <Btn
                variant="flat"
                style={{ flex: 1 }}
                disabled={busy || !roll.undo?.available}
                onClick={undo}
                title={roll.undo?.label ? `Undo ${roll.undo.label}` : undefined}
              >
                {roll.undo?.available ? `Undo ${roll.undo.label}` : 'Nothing to undo'}
              </Btn>
              <Info side="left">
                Every destructive edit — apply to roll, a boundary move, a
                split, a merge, a re-detect, a frame reset — is snapshotted
                first. A frame's editable state is a few ints and a dict, so a
                whole roll is a few kilobytes and the snapshot is automatic.
                <br />
                <br />
                <b>This session only.</b> The stack is in memory and is not
                written to the sidecar: undoing past a reopen, past a re-detect
                that changed the frame count, or past another process writing
                the same sidecar are not things it can honestly promise.
                {roll.undo?.depth ? (
                  <>
                    <br />
                    <br />
                    <span className="num">{roll.undo.depth}</span> step
                    {roll.undo.depth === 1 ? '' : 's'} available.
                  </>
                ) : null}
              </Info>
            </div>
          </Grp>

          <Grp title="Not available">
            {(roll.unavailable_controls || []).map((c) => (
              <div className="dead" key={c.key}>
                <span className="nm">{c.label}</span>
                <span className="sp" />
                <Info side="left">{c.reason}</Info>
              </div>
            ))}
            <div className="dead">
              <span className="nm">Tone curve</span>
              <span className="sp" />
              <Info side="left">
                The vendor's contrast is a pick from shipped FUGC lookup tables, not a curve. Drawing
                an editable curve here would be inventing an operator the machine does not have.
              </Info>
            </div>
          </Grp>

          <div className="railfoot">
            <Btn variant="primary big" onClick={onGoExport}>
              Export roll →
            </Btn>
          </div>
        </Rail>
      </div>

      {bounds ? (
        <Boundaries
          roll={roll}
          selected={sel}
          onSelect={setSel}
          onEdit={editBoundary}
          busy={busy}
          onClose={() => setBounds(false)}
        />
      ) : (
        <Filmstrip
          roll={roll}
          selected={sel}
          onSelect={setSel}
          onOpenFraming={onOpenFraming}
          onOpenContactSheet={onOpenContactSheet}
        >
          {lowConf ? (
            <div className="flag" role="status">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M12 3.5 22 20H2Z" />
                <path d="M12 10v4" />
                <circle cx="12" cy="17" r=".8" fill="currentColor" />
              </svg>
              Boundary{' '}
              <span className="num" style={{ fontSize: 12 }}>
                {lowConf.index + 1}|{lowConf.index + 2}
              </span>{' '}
              is low confidence
              <Info>
                That frame came out well off the median width for this roll. The strip is one
                continuous capture and the frames are found afterwards, so the fix is to move the
                window — not to rescan.
              </Info>
              <span className="sp" />
              <Btn onClick={() => setBounds(true)}>Adjust</Btn>
            </div>
          ) : (
            <>
              <span className="lbl">This roll</span>
              <Btn onClick={() => setBounds(true)}>Boundaries</Btn>
            </>
          )}
        </Filmstrip>
      )}
    </>
  );
}
