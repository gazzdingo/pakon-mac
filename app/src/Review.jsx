// Review + Frame editor.
//
// The image is the interface: one large preview, inspector at the side, edits
// render in place without blocking the app. There is one image per frame and
// no intermediates — changing a parameter changes the frame's version hash,
// which changes the image URL, and the backend renders it again.
//
// Two-tier render, from measurement rather than assumption: a quarter-res
// preview is ~40 ms and full quality is ~430 ms on this machine, so a drag
// runs on the preview path and settles to the sharper one when it stops.
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Button, Chip, Slider, Switch, Tooltip } from '@heroui/react';
import {
  DensityTrace,
  Filmstrip,
  KV,
  Plain,
  Rail,
  Section,
  StatusLine,
  Working,
} from './components';
import * as api from './api';

const BALANCE = [
  ['density', 'Density', 'exposure, all channels'],
  ['red', 'Red – Cyan', null],
  ['green', 'Green – Magenta', null],
  ['blue', 'Blue – Yellow', null],
];

function StepSlider({ label, hint, value, auto, onChange, onCommit, disabled, reason }) {
  const touched = Math.abs(value) > 1e-9;
  const row = (
    <div className="py-[7px]" style={{ opacity: disabled ? 0.45 : 1 }}>
      <div className="flex items-baseline gap-2 mb-[6px]">
        <span className="text-[12px] flex-1">
          {label}
          {hint ? (
            <small className="block text-[10px]" style={{ color: 'var(--mute)' }}>
              {hint}
            </small>
          ) : null}
        </span>
        {auto !== undefined ? (
          <span className="num text-[11px]" style={{ color: 'var(--mute)' }} title="auto value">
            {auto}
          </span>
        ) : null}
        <span
          className="num text-[12px] w-[48px] text-right border px-[5px] py-[2px]"
          style={{
            borderColor: touched ? 'var(--mute)' : 'var(--rule)',
            color: touched ? 'var(--ink)' : 'var(--mute)',
          }}
        >
          {disabled ? '—' : value > 0 ? `+${value}` : value}
        </span>
      </div>
      <Slider.Root
        aria-label={label}
        value={value}
        onChange={onChange}
        onChangeEnd={onCommit}
        minValue={-8}
        maxValue={8}
        step={0.25}
        isDisabled={disabled}
        className="w-full"
      >
        <Slider.Track className="h-[3px] rounded-none" style={{ background: 'var(--rule)' }}>
          <Slider.Fill className="rounded-none" style={{ background: 'var(--mute)' }} />
          <Slider.Thumb
            className="rounded-none w-[9px] h-[15px] border-0"
            style={{ background: touched ? 'var(--ink)' : 'var(--mute)' }}
          />
        </Slider.Track>
      </Slider.Root>
    </div>
  );
  return disabled && reason ? (
    <Tooltip content={<span className="max-w-[280px] block text-[11px]">{reason}</span>}>
      {row}
    </Tooltip>
  ) : (
    row
  );
}

/** The honest line-scan model: a continuous strip with boundaries found
 *  afterwards, and the user able to correct them. */
function BoundaryLane({ roll, selected, onSelect, onEdit, busy }) {
  const laneRef = useRef(null);
  const [drag, setDrag] = useState(null);

  const lo = Math.max(0, (roll.frames[Math.max(0, selected - 2)]?.a ?? 0) - 200);
  const hi = Math.min(roll.lines, (roll.frames[Math.min(roll.frames.length - 1, selected + 2)]?.b ?? roll.lines) + 200);
  const span = Math.max(1, hi - lo);
  const pct = (line) => ((line - lo) / span) * 100;

  const lineAt = useCallback(
    (clientX) => {
      const r = laneRef.current.getBoundingClientRect();
      return Math.round(lo + ((clientX - r.left) / r.width) * span);
    },
    [lo, span],
  );

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

  const visible = roll.frames.filter((f) => f.b > lo && f.a < hi);
  const lowConf = roll.frames.find((f) => f.confidence === 'low');

  return (
    <div className="px-4 pt-[10px] pb-3 border-t" style={{ borderColor: 'var(--rule)', background: 'var(--plate)' }}>
      <div className="flex items-baseline gap-3 mb-2">
        <span className="lbl" style={{ color: 'var(--ink)' }}>
          Frame boundaries on the strip
        </span>
        {lowConf ? (
          <span className="text-[11px] filament">
            ▲ frame {lowConf.index + 1} is an unusual length — check its boundaries
          </span>
        ) : null}
        <span className="num text-[10px] ml-auto" style={{ color: 'var(--mute)' }}>
          lines {lo}–{hi}
        </span>
      </div>

      <div
        ref={laneRef}
        className="relative h-[64px] border overflow-hidden select-none"
        style={{ borderColor: 'var(--rule)', background: '#161006' }}
      >
        {visible.map((f) => (
          <button
            key={f.index}
            onClick={() => onSelect(f.index)}
            className="absolute top-2 bottom-2 overflow-hidden border gate"
            style={{
              left: `${pct(f.a)}%`,
              width: `${((f.b - f.a) / span) * 100}%`,
              borderColor: f.index === selected ? 'var(--ink)' : 'transparent',
            }}
            title={`Frame ${f.index + 1}: lines ${f.a}–${f.b}`}
          >
            <img
              src={api.frameUrl(roll.id, f.index, 'thumb', f.version)}
              alt=""
              className="w-full h-full object-cover"
            />
          </button>
        ))}
        {visible.slice(0, -1).map((f) => {
          const line = drag?.index === f.index ? drag.line : f.b;
          return (
            <div
              key={`b${f.index}`}
              onMouseDown={() => setDrag({ index: f.index, line: f.b })}
              className="absolute top-0 bottom-0 w-[11px] -ml-[5px]"
              style={{ left: `${pct(line)}%`, cursor: 'col-resize' }}
              title={`Boundary ${f.index + 1} | ${f.index + 2} — drag to move`}
            >
              <span
                className="absolute top-0 bottom-0 left-[4px] w-[2px]"
                style={{
                  background: f.confidence === 'low' ? 'var(--filament)' : 'var(--ink)',
                  opacity: drag?.index === f.index ? 1 : 0.75,
                }}
              />
              <i className="absolute top-[2px] left-[8px] num text-[9px] not-italic" style={{ color: 'var(--mute)' }}>
                {f.index + 1}|{f.index + 2}
              </i>
            </div>
          );
        })}
      </div>

      <div className="flex gap-2 mt-2 items-center">
        <Plain
          className="!w-auto px-3"
          isDisabled={busy}
          onPress={() =>
            onEdit({
              op: 'split',
              index: selected,
              line: Math.round((roll.frames[selected].a + roll.frames[selected].b) / 2),
            })
          }
        >
          Split at middle
        </Plain>
        <Plain
          className="!w-auto px-3"
          isDisabled={busy || selected >= roll.frames.length - 1}
          onPress={() => onEdit({ op: 'merge', index: selected })}
        >
          Merge with next
        </Plain>
        <Plain className="!w-auto px-3" isDisabled={busy} onPress={() => onEdit({ op: 'redetect' })}>
          Re-detect all
        </Plain>
        <span className="text-[11px] ml-auto" style={{ color: 'var(--mute)' }}>
          Drag a boundary to move it — the two frames re-render on release.
        </span>
      </div>
    </div>
  );
}

export default function Review({ roll, setRoll, rolls, onPickRoll, onOpen, onGoExport }) {
  const [sel, setSel] = useState(0);
  const [pending, setPending] = useState(null); // live slider values
  const [busy, setBusy] = useState(false);
  const [sharp, setSharp] = useState(false);
  const [clip, setClip] = useState(null);
  const [hist, setHist] = useState(null);
  const settle = useRef(null);

  const frame = roll?.frames?.[sel];
  const params = pending ?? frame?.params ?? {};

  useEffect(() => {
    setSel((s) => Math.min(s, Math.max(0, (roll?.frames?.length ?? 1) - 1)));
  }, [roll?.id, roll?.frames?.length]);

  // Sharpen up after the parameters stop moving.
  useEffect(() => {
    setSharp(false);
    clearTimeout(settle.current);
    settle.current = setTimeout(() => setSharp(true), 260);
    return () => clearTimeout(settle.current);
  }, [frame?.version, sel]);

  useEffect(() => {
    if (!roll || !frame) return;
    let alive = true;
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

  // Keyboard grammar — same philosophy as the vendor's, saner keys.
  useEffect(() => {
    const onKey = (e) => {
      if (e.target.tagName === 'INPUT' || e.metaKey || e.ctrlKey) return;
      const step = e.shiftKey ? 1 : 0.25;
      const bump = (k, d) => {
        e.preventDefault();
        commit({ ...params, [k]: +((params[k] || 0) + d).toFixed(2) });
      };
      if (e.key === 'ArrowRight' || e.key === 'j') setSel((s) => Math.min(s + 1, roll.frames.length - 1));
      else if (e.key === 'ArrowLeft' || e.key === 'k') setSel((s) => Math.max(s - 1, 0));
      else if (e.key === 'r') bump('red', step);
      else if (e.key === 'R') bump('red', -step);
      else if (e.key === 'g') bump('green', step);
      else if (e.key === 'G') bump('green', -step);
      else if (e.key === 'b') bump('blue', step);
      else if (e.key === 'B') bump('blue', -step);
      else if (e.key === 'd') bump('density', step);
      else if (e.key === 'D') bump('density', -step);
      else if (e.key === '0') {
        e.preventDefault();
        api.resetFrame(roll.id, sel).then(setRoll);
      } else if (e.key === 'Backspace') {
        e.preventDefault();
        commit({ ...params, rejected: !params.rejected });
      } else if (e.key === 'c') setClip({ ...params });
      else if (e.key === 'v' && clip) commit({ ...clip, rejected: params.rejected });
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [roll, sel, params, clip, commit, setRoll]);

  if (!roll) {
    return (
      <div className="flex flex-1 min-h-0">
        <Rail>
          <Section title="Rolls in workspace">
            <p className="text-[11px]" style={{ color: 'var(--mute)' }}>
              Nothing open. A roll is one capture plus its settings.
            </p>
          </Section>
        </Rail>
        <main className="flex-1 flex flex-col" style={{ background: 'var(--void)' }}>
          <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center px-8">
            <div className="ledger text-[22px]">No roll open</div>
            <p className="text-[13px] max-w-[54ch]" style={{ color: 'var(--mute)' }}>
              Open a capture to see the roll as a set of frames. Frames are rendered from the
              capture on demand — nothing is written to disk until you export.
            </p>
            <Plain className="!w-auto px-6" onPress={onOpen}>
              Open capture…
            </Plain>
          </div>
        </main>
      </div>
    );
  }

  const adjusted = roll.frames.filter((f) => f.adjusted).length;
  const rejected = roll.frames.filter((f) => f.params?.rejected).length;
  const exported = roll.frames.filter((f) => f.exported).length;
  const scale = sharp ? 'display' : 'preview';

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="flex flex-1 min-h-0">
        {/* ── left rail ── */}
        <Rail>
          <Section title="Rolls in workspace">
            <div className="flex flex-col gap-[2px]">
              {rolls.map((r) => (
                <button
                  key={r.id}
                  onClick={() => onPickRoll(r.id)}
                  className="flex justify-between items-baseline px-2 py-[7px] text-[12px] border gate"
                  style={{
                    borderColor: r.id === roll.id ? 'var(--rule)' : 'transparent',
                    background: r.id === roll.id ? 'var(--plate2)' : 'transparent',
                  }}
                >
                  <em className="ledger not-italic">{r.name}</em>
                  <span className="num text-[11px]" style={{ color: 'var(--mute)' }}>
                    {r.frames.length} frames
                  </span>
                </button>
              ))}
            </div>
            <Plain className="mt-2" onPress={onOpen}>
              Open capture…
            </Plain>
          </Section>

          <Section title="This roll">
            <KV
              rows={[
                ['Frames', roll.frames.length],
                ['Adjusted', adjusted],
                ['Rejected', rejected],
                ['Exported', exported],
                ['Lines', roll.lines.toLocaleString()],
                ['Capture', api.fmtBytes(roll.sync?.bytes)],
              ]}
            />
            <p className="text-[11px] mt-[10px]" style={{ color: 'var(--mute)' }}>
              Settings persist with the roll — reopen the capture and every adjustment comes back.
            </p>
          </Section>

          <Section title="Selection">
            <Plain className="mb-[6px]" onPress={() => commit({ ...params, rejected: !params.rejected })}>
              {params.rejected ? 'Restore frame (⌫)' : 'Reject frame (⌫)'}
            </Plain>
            <Plain className="mb-[6px]" onPress={() => setClip({ ...params })}>
              Copy offsets (C)
            </Plain>
            <Plain
              isDisabled={!clip}
              onPress={() => clip && commit({ ...clip, rejected: params.rejected })}
            >
              Paste offsets (V)
            </Plain>
            <p className="text-[11px] mt-[10px]" style={{ color: 'var(--mute)' }}>
              Rejected frames stay in the roll, marked, and are skipped at export.
            </p>
          </Section>
        </Rail>

        {/* ── stage ── */}
        <main className="flex-1 min-w-0 flex flex-col" style={{ background: 'var(--void)' }}>
          <div className="flex items-baseline gap-[14px] px-5 pt-3 pb-1.5">
            <span className="ledger text-[19px]">{roll.name}</span>
            <span className="lbl" style={{ color: 'var(--ink)' }}>
              Frame {sel + 1} of {roll.frames.length}
            </span>
            <span className="text-[12px] ml-auto" style={{ color: 'var(--mute)' }}>
              lines {frame.a}–{frame.b} · rendered from capture + settings
            </span>
          </div>

          <div className="flex-1 min-h-0 flex items-center justify-center px-5 py-2 relative">
            <img
              key={`${roll.id}-${sel}-${frame.version}-${scale}`}
              src={api.frameUrl(roll.id, sel, scale, frame.version)}
              alt={`Frame ${sel + 1}`}
              className="stage-img border"
              style={{
                borderColor: 'var(--rule)',
                transform: params.rejected ? 'none' : 'none',
                opacity: params.rejected ? 0.45 : 1,
              }}
            />
            {params.rejected ? (
              <span className="absolute lbl px-2 py-1" style={{ background: 'var(--halt)', color: '#fff' }}>
                Rejected — skipped at export
              </span>
            ) : null}
          </div>

          <div className="flex gap-3 items-center px-5 py-2 text-[11px]" style={{ color: 'var(--mute)' }}>
            <span>
              Density <b className="num" style={{ color: 'var(--ink)' }}>{(params.density || 0) > 0 ? '+' : ''}{params.density || 0}</b>
            </span>
            <span>
              Balance{' '}
              <b className="num" style={{ color: 'var(--ink)' }}>
                R {params.red || 0} · G {params.green || 0} · B {params.blue || 0}
              </b>
            </span>
            <span>
              Rotation <b className="num" style={{ color: 'var(--ink)' }}>{params.rotate || 0}°</b>
            </span>
            <span className="ml-auto">
              {sharp ? 'half-res preview · full quality at export' : 'quarter-res while adjusting'}
            </span>
          </div>

          <BoundaryLane roll={roll} selected={sel} onSelect={setSel} onEdit={editBoundary} busy={busy} />
        </main>

        {/* ── inspector ── */}
        <Rail side="right" width={320}>
          <Section title={`Frame ${sel + 1} — adjustments`}>
            <div
              className="grid grid-cols-[1fr_auto_auto] gap-x-2 text-[9px] tracking-[0.12em] uppercase pb-1"
              style={{ color: 'var(--mute)' }}
            >
              <span>Parameter</span>
              <span className="text-right">Auto</span>
              <span className="text-right w-[48px]">Steps</span>
            </div>
            {BALANCE.map(([key, label, hint], i) => (
              <StepSlider
                key={key}
                label={label}
                hint={hint}
                value={params[key] || 0}
                auto={i === 0 ? '—' : (roll.auto_offsets?.[i - 1] ?? 0).toFixed(1)}
                onChange={(v) => setPending({ ...params, [key]: v })}
                onCommit={(v) => commit({ ...params, [key]: v })}
              />
            ))}
            <p className="text-[11px] mt-2" style={{ color: 'var(--mute)' }}>
              Auto is the roll-level scene balance. Your changes are offsets on top of it in the
              vendor's own button-step unit ({roll.units?.code_values_per_button ?? 75} code values);
              zero everything and the frame is exactly the automatic result.
            </p>
          </Section>

          {roll.unavailable_controls?.length ? (
            <Section title="Not available">
              {roll.unavailable_controls.map((c) => (
                <StepSlider key={c.key} label={c.label} value={0} disabled reason={c.reason} />
              ))}
              <p className="text-[11px] mt-1" style={{ color: 'var(--mute)' }}>
                These are drawn in the design but have no traced vendor operation behind them. They
                are shown disabled rather than faked with a curve of ours.
              </p>
            </Section>
          ) : null}

          <Section title="Geometry">
            <div className="grid grid-cols-3 gap-[6px] mb-[6px]">
              {[
                ['⟲ 90°', () => commit({ ...params, rotate: ((params.rotate || 0) + 270) % 360 })],
                ['⟳ 90°', () => commit({ ...params, rotate: ((params.rotate || 0) + 90) % 360 })],
                ['180°', () => commit({ ...params, rotate: ((params.rotate || 0) + 180) % 360 })],
              ].map(([l, fn]) => (
                <Plain key={l} onPress={fn}>
                  {l}
                </Plain>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-[6px]">
              <Plain active={params.flip_h} onPress={() => commit({ ...params, flip_h: !params.flip_h })}>
                Flip H
              </Plain>
              <Plain active={params.flip_v} onPress={() => commit({ ...params, flip_v: !params.flip_v })}>
                Flip V
              </Plain>
            </div>
          </Section>

          <Section>
            {busy ? <Working>Re-rendering frame {sel + 1}…</Working> : null}
            <Plain className="mb-[6px]" onPress={() => api.resetFrame(roll.id, sel).then(setRoll)}>
              Reset frame to auto (0)
            </Plain>
            <Plain
              className="mb-[6px]"
              onPress={async () => {
                setBusy(true);
                try {
                  setRoll(await api.applyToRoll(roll.id, sel, ['density', 'red', 'green', 'blue']));
                } finally {
                  setBusy(false);
                }
              }}
            >
              Apply offsets to whole roll
            </Plain>
            <Plain onPress={onGoExport}>Go to export →</Plain>
          </Section>

          <Section title="Frame metadata">
            <KV
              rows={[
                ['Strip position', `${frame.a}–${frame.b}`],
                ['Boundary', frame.confidence],
                ['Dmin (R·G·B)', hist ? hist.dmin.map((v) => v.toFixed(0)).join(' · ') : '…'],
                ['Clipped', hist ? `${hist.clipped_pct.toFixed(3)} %` : '…'],
                ['IR plane', roll.ir?.has_ir ? 'captured' : 'not in capture'],
              ]}
            />
            {hist ? <Histogram hist={hist.hist} /> : null}
          </Section>

          <Section title="Roll status" grow>
            <Chip.Root
              color={adjusted && !exported ? 'warning' : 'default'}
              variant="bordered"
              className="rounded-none"
            >
              <Chip.Label className="text-[10px] tracking-[0.1em] uppercase">
                {adjusted} adjusted · {exported} exported
              </Chip.Label>
            </Chip.Root>
            <p className="text-[11px] mt-2" style={{ color: 'var(--mute)' }}>
              Export writes files; until then this roll lives only in the workspace.
            </p>
          </Section>
        </Rail>
      </div>

      {/* ── bottom: the roll ── */}
      <footer className="shrink-0 border-t" style={{ borderColor: 'var(--rule)', background: 'var(--plate)' }}>
        <Filmstrip roll={roll} selected={sel} onSelect={setSel} />
        <DensityTrace trace={roll.trace} selected={sel} onSelect={setSel} />
        <StatusLine left="REVIEW">
          <span>
            {roll.name} · {roll.frames.length} frames · {rejected} rejected
          </span>
          <span style={{ marginLeft: 'auto' }}>
            settings autosaved to sidecar · capture temporary
          </span>
        </StatusLine>
      </footer>
    </div>
  );
}

function Histogram({ hist }) {
  const W = 300;
  const H = 56;
  const max = Math.max(...['r', 'g', 'b'].flatMap((c) => hist[c]));
  const path = (arr) =>
    arr.map((v, i) => `${((i / (arr.length - 1)) * W).toFixed(1)},${(H - (v / max) * H).toFixed(1)}`).join(' ');
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="w-full h-[56px] mt-3" aria-label="RGB histogram of the 14-bit source">
      {[
        ['r', 'var(--halt)'],
        ['g', 'var(--pass)'],
        ['b', '#5A7EA6'],
      ].map(([c, col]) => (
        <polyline key={c} fill="none" stroke={col} strokeWidth="1" opacity="0.85" points={path(hist[c])} />
      ))}
    </svg>
  );
}
