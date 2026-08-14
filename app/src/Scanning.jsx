// The screen while film is moving, and immediately after. No settings here —
// only what the sensor is seeing right now and the one button that matters.
import React from 'react';
import { Btn, Chip, Spinner } from './components';
import * as api from './api';

function AfterScan({ job, open, onOpenAnyway, onDismiss }) {
  if (open && open.status === 'running')
    return (
      <div style={{ display: 'grid', gap: 8, justifyItems: 'center', width: '100%', maxWidth: 420 }}>
        <Spinner>{open.phase || 'Opening'}</Spinner>
        <div className="bar warnfill" style={{ width: '100%' }}>
          <i style={{ width: `${(open.progress || 0) * 100}%` }} />
        </div>
      </div>
    );

  if (open && (open.status === 'error' || open.error))
    return (
      <div style={{ display: 'grid', gap: 10, justifyItems: 'center', maxWidth: '52ch' }}>
        <span style={{ color: 'var(--danger-ink)', fontSize: 13 }}>Decode failed</span>
        <span className="num quiet" style={{ fontSize: 11, textAlign: 'center' }}>
          {open.error || open.message}
        </span>
        <div style={{ display: 'flex', gap: 8 }}>
          <Btn variant="primary" onClick={onOpenAnyway}>Try again</Btn>
          <Btn variant="flat" onClick={onDismiss}>Dismiss</Btn>
        </div>
      </div>
    );

  return (
    <div style={{ display: 'flex', gap: 8 }}>
      {job.path && !job.openable ? (
        <Btn variant="primary" onClick={onOpenAnyway}>Decode anyway</Btn>
      ) : null}
      <Btn variant="flat" onClick={onDismiss}>Dismiss</Btn>
    </div>
  );
}

export default function Scanning({ job, onCancel, busy, open, onOpenAnyway, onDismiss }) {
  const running = job.status === 'running';
  const w = job.window || {};
  const gate = api.GATE[w.state || 'unknown'] || api.GATE.unknown;
  const elapsed = job.elapsed ?? job.seconds ?? 0;
  const cap = job.max_seconds || 0;
  const pct = cap ? Math.min(100, (elapsed / cap) * 100) : 0;
  const lampBad = job.lamp?.ok === false;

  return (
    <main className="scanstage">
      <div className="stagehead">
        <span className="title">{running ? 'Scanning' : job.message || 'Scan ended'}</span>
        {lampBad ? <Chip tone="bad" dot>Lamp fault</Chip> : null}
        <span className="sp" />
        <span className="quiet">{gate.note}</span>
      </div>

      {(job.warnings || []).length ? (
        <div style={{ display: 'grid', gap: 6, width: '100%', maxWidth: 960 }}>
          {job.warnings.map((text) => {
            const misload = /TAIL FIRST|EMULSION DOWN/i.test(text);
            return (
              <div
                key={text}
                style={{
                  background: misload ? 'var(--danger-flat)' : 'var(--soft)',
                  color: misload ? 'var(--danger-ink)' : 'inherit',
                  borderRadius: 'var(--r-sm)',
                  padding: '9px 11px',
                  fontSize: 12,
                }}
              >
                {text}
              </div>
            );
          })}
        </div>
      ) : null}

      <div className="filmwrap" style={{ display: 'flex', flexDirection: 'column', gap: 18, alignItems: 'center' }}>
        <div style={{ display: 'grid', placeItems: 'center', gap: 10, padding: '28px 0' }}>
          <div
            className="num"
            style={{
              fontSize: 58,
              lineHeight: 1,
              letterSpacing: '-0.02em',
              userSelect: 'none',
              color:
                w.state === 'dark' ? 'var(--danger-ink)' : w.state === 'clear' ? 'var(--ok-ink)' : 'var(--foreground)',
            }}
          >
            {gate.label.toUpperCase()}
          </div>
        </div>

        <div style={{ width: '100%', maxWidth: 560 }}>
          <div className={`bar${running ? ' warnfill' : ''}`} style={{ height: 8 }}>
            <i style={{ width: `${pct}%` }} />
          </div>
          <div style={{ display: 'flex', marginTop: 6 }}>
            <span className="quiet">{api.fmtClock(elapsed)}</span>
            <span className="sp" />
            <span className="quiet">{api.fmtBytes(job.bytes)} captured</span>
          </div>
        </div>

        {running ? (
          <Btn
            variant="danger big"
            disabled={busy}
            onClick={onCancel}
            style={{ maxWidth: 260, height: 46, fontSize: 15 }}
          >
            {busy ? 'Stopping…' : 'Cancel scan'}
          </Btn>
        ) : (
          <div style={{ maxWidth: '56ch', textAlign: 'center', display: 'grid', gap: 12, justifyItems: 'center' }}>
            {job.detail ? <p className="quiet">{job.detail}</p> : null}
            <AfterScan job={job} open={open} onOpenAnyway={onOpenAnyway} onDismiss={onDismiss} />
          </div>
        )}
      </div>
    </main>
  );
}
