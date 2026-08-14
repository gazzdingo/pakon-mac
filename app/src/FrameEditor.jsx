// One frame: the image, and everything you can do to it. Histogram and tone
// bench on the right — the same correction engine the app has always had,
// just without a rail of read-only settings and machine telemetry beside it.
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Btn, Chip, Grp, Rail, RailHead, Spinner, StepTrack } from './components';
import * as api from './api';

const CHANNELS = [
  ['red', 'R–C', 'R', 'Cyan −8', '+8 Red'],
  ['green', 'G–M', 'G', 'Magenta −8', '+8 Green'],
  ['blue', 'B–Y', 'B', 'Yellow −8', '+8 Blue'],
  ['density', 'Density', 'D', 'Darker −8', '+8 Lighter'],
];

const fmt = (v) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v || 0).toFixed(2);

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

/* ── apply to roll: the confirmation, which is the whole point of it ─────── */

function ApplySheet({ plan, busy, onCancel, onConfirm }) {
  if (!plan) return null;
  const changing = plan.frames_changing || [];
  const overwriting = plan.frames_overwriting_adjustments || [];

  return (
    <div className="scrim on" onMouseDown={(e) => e.target === e.currentTarget && !busy && onCancel()}>
      <div className="sheet">
        <div style={{ marginBottom: 14 }}>
          <span className="title">Apply to roll</span>
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
            <span className="num">{changing.length} of {(plan.frames_total ?? 1) - 1}</span>
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
          <Btn variant="flat" disabled={busy} onClick={onCancel}>Cancel</Btn>
          <Btn variant="primary" disabled={busy || !changing.length} onClick={onConfirm}>
            {busy ? 'Applying…' : `Apply to ${changing.length} frames`}
          </Btn>
        </div>
      </div>
    </div>
  );
}

/* ── screen ─────────────────────────────────────────────────────────────── */

export default function FrameEditor({ roll, setRoll, sel, setSel }) {
  const [pending, setPending] = useState(null);
  const [busy, setBusy] = useState(false);
  const [sharp, setSharp] = useState(false);
  const [chan, setChan] = useState('red');
  const [plotCh, setPlotCh] = useState('rgb');
  const [clipboard, setClipboard] = useState(null);
  const [hist, setHist] = useState(null);
  const [applyPlan, setApplyPlan] = useState(null);
  const [imgFailed, setImgFailed] = useState(null);
  const [imgNonce, setImgNonce] = useState(0);
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
    api.get(api.histUrl(roll.id, sel)).then((h) => alive && setHist(h)).catch(() => {});
    return () => { alive = false; };
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

  const APPLY_KEYS = ['density', 'red', 'green', 'blue'];

  const askApply = useCallback(async () => {
    setBusy(true);
    try {
      const plan = await api.planApplyToRoll(roll.id, sel, APPLY_KEYS);
      if (plan.needs_confirm) setApplyPlan(plan);
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
      else if (k === '0') { e.preventDefault(); commit({ ...params, [chan]: 0 }); }
      else if (k === 'Delete' || k === 'Backspace') { e.preventDefault(); commit({ ...params, rejected: true }); }
      else if (k === 'Insert') { e.preventDefault(); commit({ ...params, rejected: false }); }
      else if (k === 'c') setClipboard({ ...params });
      else if (k === 'v' && clipboard) commit({ ...clipboard, rejected: params.rejected });
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [roll, sel, params, chan, clipboard, commit, setSel]);

  if (!frame) return null;

  const scale = sharp ? 'display' : 'preview';
  const val = params[chan] || 0;
  const chanDef = CHANNELS.find(([k]) => k === chan);

  return (
    <>
      <ApplySheet plan={applyPlan} busy={busy} onCancel={() => setApplyPlan(null)} onConfirm={doApply} />
      <div className="body" style={{ gridTemplateColumns: 'minmax(0,1fr) 340px' }}>
        <div className="centre">
          <div className="actbar">
            <span className="title">Frame {sel + 1}</span>
            <span className="quiet">
              of <span className="num" style={{ fontSize: 12 }}>{roll.frames.length}</span>
              {roll.stock?.name ? ` · ${roll.stock.name}` : ''}
            </span>
            {busy ? <Spinner /> : null}
            <span className="sp" />
            {params.rejected ? <Chip tone="bad" dot>Rejected</Chip> : null}
            <Btn variant="flat" onClick={() => commit({ ...params, rejected: true })} disabled={params.rejected}>
              Reject <kbd>Del</kbd>
            </Btn>
            <Btn variant="primary" onClick={() => commit({ ...params, rejected: false })} disabled={!params.rejected}>
              Accept <kbd style={{ background: 'rgba(255,255,255,.22)', color: '#fff' }}>Ins</kbd>
            </Btn>
          </div>

          <main className="stage">
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
            <Btn variant="flat" onClick={() => commit({ ...params, rotate: ((params.rotate || 0) + 270) % 360 })}>Left</Btn>
            <Btn variant="flat" onClick={() => commit({ ...params, rotate: ((params.rotate || 0) + 180) % 360 })}>180°</Btn>
            <Btn variant="flat" onClick={() => commit({ ...params, rotate: ((params.rotate || 0) + 90) % 360 })}>Right</Btn>
            <span className="lbl" style={{ marginLeft: 8 }}>Flip</span>
            <Btn variant={params.flip_h ? 'primary' : 'flat'} onClick={() => commit({ ...params, flip_h: !params.flip_h })}>
              Horizontal
            </Btn>
            <Btn variant={params.flip_v ? 'primary' : 'flat'} onClick={() => commit({ ...params, flip_v: !params.flip_v })}>
              Vertical
            </Btn>
            <span className="sp" />
            <span className="quiet" style={{ whiteSpace: 'nowrap' }}>
              {sharp ? 'half-res' : 'quarter-res'} · full quality at export
            </span>
          </div>
        </div>

        <Rail side="r" aria-label="Frame corrections">
          <RailHead title="Tone">
            <span className="itabs">
              {[['rgb', 'RGB', ''], ['r', 'R', 'r'], ['g', 'G', 'g'], ['b', 'B', 'b']].map(([id, label, cls]) => (
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
              <span>shadows <i>{hist ? `${hist.clipped_shadow_pct?.toFixed(2) ?? '0.00'} %` : '—'}</i></span>
              <span>Dmin <i>{hist ? hist.dmin.map((v) => v.toFixed(0)).join(' · ') : '—'}</i></span>
              <span>highlights <i>{hist ? `${hist.clipped_pct.toFixed(2)} %` : '—'}</i></span>
            </div>
          </Grp>

          <Grp title="Colour">
            <div className="chanrow">
              {CHANNELS.map(([key, label, k]) => (
                <button key={key} type="button" className={`chan${chan === key ? ' on' : ''}`} onClick={() => setChan(key)}>
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

            <div style={{ display: 'flex', gap: 6 }}>
              <Btn variant="flat" style={{ flex: 1 }} onClick={() => api.resetFrame(roll.id, sel).then(setRoll)}>
                Reset frame
              </Btn>
              <Btn variant="flat" style={{ flex: 1 }} disabled={busy} onClick={askApply}>
                Apply to roll…
              </Btn>
            </div>

            <Btn
              variant="flat"
              disabled={busy || !roll.undo?.available}
              onClick={undo}
            >
              {roll.undo?.available ? `Undo ${roll.undo.label}` : 'Nothing to undo'}
            </Btn>
          </Grp>
        </Rail>
      </div>
    </>
  );
}
