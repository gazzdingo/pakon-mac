// One frame: the image, and everything you can do to it. Histogram and tone
// bench on the right — the same correction engine the app has always had,
// just without a rail of read-only settings and machine telemetry beside it.
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AdjustmentSlider, Btn, Chip, Grp, Rail, RailHead, Spinner } from './components';
import * as api from './api';

/* ── the plot: histogram of the 14-bit source, with the roll's own levels ──
   handles (shadows / midtones / highlights) draggable right on the curve —
   and nothing invented: the curve is the real 14-bit source, the handles are
   the same density/highlights/shadows params the sliders below edit. */

function Plot({ hist, channel, params, setPending, commit }) {
  const W = 1000;
  const H = 620;
  const TRACK_H = 40;
  const PLOT_H = H - TRACK_H;

  const svgRef = useRef(null);
  const dragRef = useRef(null);
  const [hoverHandle, setHoverHandle] = useState(null);

  const path = useMemo(() => {
    if (!hist) return null;
    const ch = ['r', 'g', 'b'];
    const max = Math.max(1, ...ch.flatMap((c) => hist.hist[c]));
    const line = (arr) =>
      arr
        .map((v, i) => `${((i / (arr.length - 1)) * W).toFixed(1)},${(PLOT_H - (v / max) * PLOT_H).toFixed(1)}`)
        .join(' ');
    const sum = hist.hist.r.map((_, i) => hist.hist.r[i] + hist.hist.g[i] + hist.hist.b[i]);
    const smax = Math.max(1, ...sum);
    const area =
      sum
        .map((v, i) => `${((i / (sum.length - 1)) * W).toFixed(1)},${(PLOT_H - (v / smax) * PLOT_H).toFixed(1)}`)
        .join(' ') + ` ${W},${PLOT_H} 0,${PLOT_H}`;
    return { line, area };
  }, [hist, PLOT_H]);

  if (!hist || !path) return <div className="plotbox" />;

  const shown = channel === 'rgb' ? ['r', 'g', 'b'] : [channel];
  const col = { r: 'var(--chR)', g: 'var(--chG)', b: 'var(--chB)' };

  const densityShift = (params?.density || 0) * 20;
  const contrastScale = params?.contrast !== undefined ? params.contrast / 100 : 1;
  const transform = `translate(${W / 2}, 0) scale(${contrastScale}, 1) translate(${-W / 2 + densityShift}, 0)`;

  const shadowsVal = params?.shadows || 0;
  const densityVal = params?.density || 0;
  const highlightsVal = params?.highlights || 0;

  const shadowsX = 50 + (shadowsVal / 100) * 200;
  const densityX = W / 2 + (densityVal / 8) * 300;
  const highlightsX = (W - 50) + (highlightsVal / 100) * 200;

  const handlePointerDown = (e, handleType) => {
    if (!svgRef.current) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    let startVal = 0;
    if (handleType === 'shadows') startVal = shadowsVal;
    if (handleType === 'midtones') startVal = densityVal;
    if (handleType === 'highlights') startVal = highlightsVal;
    dragRef.current = { activeZone: handleType, startX: e.clientX, startVal };
  };

  const handlePointerMove = (e) => {
    if (!dragRef.current || !params) return;
    const { activeZone, startX, startVal } = dragRef.current;
    const rect = svgRef.current.getBoundingClientRect();
    const ratio = W / rect.width;
    const deltaX = (e.clientX - startX) * ratio;
    const p = { ...params };
    if (activeZone === 'shadows') {
      p.shadows = Math.max(-100, Math.min(100, startVal + (deltaX / 200) * 100));
      setPending(p);
    } else if (activeZone === 'midtones') {
      p.density = Math.max(-8, Math.min(8, startVal + (deltaX / 300) * 8));
      setPending(p);
    } else if (activeZone === 'highlights') {
      p.highlights = Math.max(-100, Math.min(100, startVal + (deltaX / 200) * 100));
      setPending(p);
    }
  };

  const handlePointerUp = () => {
    if (!dragRef.current) return;
    commit(params);
    dragRef.current = null;
  };

  const TriangleHandle = ({ x, color, type }) => (
    <g
      transform={`translate(${x}, ${PLOT_H})`}
      style={{ cursor: 'ew-resize' }}
      onMouseEnter={() => setHoverHandle(type)}
      onMouseLeave={() => setHoverHandle(null)}
      onPointerDown={(e) => handlePointerDown(e, type)}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
    >
      <rect x="-40" y="0" width="80" height={TRACK_H} fill="transparent" />
      <polygon
        points="-12,30 12,30 0,6"
        fill={hoverHandle === type || dragRef.current?.activeZone === type ? 'var(--primary-flat)' : color}
        stroke="var(--mass)"
        strokeWidth="2"
      />
    </g>
  );

  return (
    <svg
      ref={svgRef}
      className="plotbox"
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      role="img"
      aria-label="RGB histogram"
      style={{ touchAction: 'none' }}
    >
      <g stroke="var(--grid)" strokeWidth="1" vectorEffect="non-scaling-stroke">
        <path d={`M250,0V${PLOT_H}M500,0V${PLOT_H}M750,0V${PLOT_H}M0,155H${W}M0,310H${W}M0,465H${W}`} />
      </g>

      <g transform={transform} style={{ transition: dragRef.current ? 'none' : 'transform 0.1s ease-out' }}>
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
      </g>

      <rect x="0" y={PLOT_H} width={W} height={TRACK_H} fill="var(--content2)" opacity="0.6" />
      <line x1="0" y1={PLOT_H + TRACK_H / 2} x2={W} y2={PLOT_H + TRACK_H / 2} stroke="var(--soft)" strokeWidth="4" />
      <line x1={shadowsX} y1={PLOT_H + TRACK_H / 2} x2={highlightsX} y2={PLOT_H + TRACK_H / 2} stroke="var(--primary-flat)" strokeWidth="4" />

      <TriangleHandle x={shadowsX} color="#222" type="shadows" />
      <TriangleHandle x={densityX} color="#888" type="midtones" />
      <TriangleHandle x={highlightsX} color="#eee" type="highlights" />
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

  // A live approximation of the backend's render, so a slider drag previews
  // instantly instead of waiting on a round trip. Brightness/contrast/
  // saturation map straight to CSS filters; exposure and R/G/B are
  // backend-only, so they're approximated as a colour matrix from how far
  // the pending value has moved from what's already committed.
  const b = params.brightness !== undefined ? params.brightness : 100;
  const c = params.contrast !== undefined ? params.contrast : 100;
  const s = params.saturation !== undefined ? params.saturation : 100;

  const dDelta = (params.density !== undefined ? params.density : 0) - (frame.params.density || 0);
  const rDelta = (params.red !== undefined ? params.red : 0) - (frame.params.red || 0);
  const gDelta = (params.green !== undefined ? params.green : 0) - (frame.params.green || 0);
  const bDelta = (params.blue !== undefined ? params.blue : 0) - (frame.params.blue || 0);

  const densityMultiplier = 1 + dDelta * 0.12;
  const rOffset = rDelta * 0.04;
  const gOffset = gDelta * 0.04;
  const bOffset = bDelta * 0.04;

  const hasSvgFilter = dDelta !== 0 || rDelta !== 0 || gDelta !== 0 || bDelta !== 0;
  const filterStyle = `${hasSvgFilter ? `url(#live-color-adjust-${sel}) ` : ''}brightness(${b}%) contrast(${c}%) saturate(${s}%)`;

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
            {hasSvgFilter && (
              <svg width="0" height="0" style={{ position: 'absolute' }}>
                <filter id={`live-color-adjust-${sel}`}>
                  <feColorMatrix
                    type="matrix"
                    values={`
                      ${densityMultiplier} 0 0 0 ${rOffset}
                      0 ${densityMultiplier} 0 0 ${gOffset}
                      0 0 ${densityMultiplier} 0 ${bOffset}
                      0 0 0 1 0
                    `}
                  />
                </filter>
              </svg>
            )}
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
                key={`${roll.id}-${sel}-${scale}-${imgNonce}`}
                className="photo"
                src={api.frameUrl(roll.id, sel, scale, frame.version)}
                alt={`Frame ${sel + 1}`}
                style={{ opacity: params.rejected ? 0.4 : 1, filter: filterStyle }}
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
            <Plot hist={hist} channel={plotCh} params={params} setPending={setPending} commit={commit} />
            <div className="clip" style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--mute)' }}>
              <span>Shadows <b>{hist ? `${hist.clipped_shadow_pct?.toFixed(2) ?? '0.00'}%` : '—'}</b></span>
              <span>Dmin <b>{hist ? hist.dmin.map((v) => v.toFixed(0)).join('·') : '—'}</b></span>
              <span>Highlights <b>{hist ? `${hist.clipped_pct.toFixed(2)}%` : '—'}</b></span>
            </div>
          </Grp>

          <Grp title="Adjustments">
            <AdjustmentSlider label="Exposure" min={-8} max={8} step={0.25} value={params.density !== undefined ? params.density : 0} zeroValue={0} onInput={(v) => setPending({ ...params, density: v })} onCommit={(v) => commit({ ...params, density: v })} />
            <AdjustmentSlider label="Red" min={-8} max={8} step={0.25} value={params.red !== undefined ? params.red : 0} zeroValue={0} onInput={(v) => setPending({ ...params, red: v })} onCommit={(v) => commit({ ...params, red: v })} />
            <AdjustmentSlider label="Green" min={-8} max={8} step={0.25} value={params.green !== undefined ? params.green : 0} zeroValue={0} onInput={(v) => setPending({ ...params, green: v })} onCommit={(v) => commit({ ...params, green: v })} />
            <AdjustmentSlider label="Blue" min={-8} max={8} step={0.25} value={params.blue !== undefined ? params.blue : 0} zeroValue={0} onInput={(v) => setPending({ ...params, blue: v })} onCommit={(v) => commit({ ...params, blue: v })} />

            <div style={{ height: 1, background: 'var(--soft)', margin: '8px 0' }} />

            <AdjustmentSlider label="Brightness" min={0} max={200} value={params.brightness !== undefined ? params.brightness : 100} zeroValue={100} onInput={(v) => setPending({ ...params, brightness: v })} onCommit={(v) => commit({ ...params, brightness: v })} />
            <AdjustmentSlider label="Contrast" min={0} max={200} value={params.contrast !== undefined ? params.contrast : 100} zeroValue={100} onInput={(v) => setPending({ ...params, contrast: v })} onCommit={(v) => commit({ ...params, contrast: v })} />
            <AdjustmentSlider label="Saturation" min={0} max={200} value={params.saturation !== undefined ? params.saturation : 100} zeroValue={100} onInput={(v) => setPending({ ...params, saturation: v })} onCommit={(v) => commit({ ...params, saturation: v })} />
            <AdjustmentSlider label="Highlights" min={-100} max={100} value={params.highlights !== undefined ? params.highlights : 0} zeroValue={0} onInput={(v) => setPending({ ...params, highlights: v })} onCommit={(v) => commit({ ...params, highlights: v })} />
            <AdjustmentSlider label="Shadows" min={-100} max={100} value={params.shadows !== undefined ? params.shadows : 0} zeroValue={0} onInput={(v) => setPending({ ...params, shadows: v })} onCommit={(v) => commit({ ...params, shadows: v })} />
            <AdjustmentSlider label="Sharpening" min={0} max={100} value={params.sharpening !== undefined ? params.sharpening : 0} zeroValue={0} onInput={(v) => setPending({ ...params, sharpening: v })} onCommit={(v) => commit({ ...params, sharpening: v })} />

            <div style={{ display: 'flex', gap: 6, marginTop: 12 }}>
              <Btn variant="flat" style={{ flex: 1 }} onClick={() => api.resetFrame(roll.id, sel).then(setRoll)}>
                Reset frame
              </Btn>
              <Btn variant="flat" style={{ flex: 1 }} disabled={busy} onClick={askApply}>
                Apply to roll…
              </Btn>
            </div>

            <Btn
              variant="flat"
              style={{ marginTop: 6 }}
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
