// A scanner the software has never seen sets itself up the moment the app
// can see it — no button, no screen to open first. The only things that
// ever need a person: film left in the gate, or two scanners on one
// computer with nothing on the wire to tell them apart.
import React, { useEffect, useRef, useState } from 'react';
import { Btn } from './components';
import * as api from './api';

export function useCalibrationSetup(boot) {
  const setup = boot?.calibration_store?.setup;
  const [job, setJob] = useState(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current || !setup?.automatic) return;
    started.current = true;
    api
      .calibrationRun({})
      .then((r) => (r?.id ? api.pollJob(r.id, setJob) : setJob(r)))
      .catch((e) => setJob({ state: 'failed', headline: String(e.message || e) }));
  }, [setup?.automatic]);

  const retry = () => {
    started.current = false;
    setJob(null);
  };

  return { setup, job, retry };
}

const NEEDS_ATTENTION = new Set(['film-in-gate', 'ambiguous', 'unreachable', 'failed']);

export default function CalibrationBanner({ boot, setup, job, retry }) {
  const state = job?.state || setup?.state;
  if (!setup || !NEEDS_ATTENTION.has(state)) return null;
  const meta = api.SETUP[state] || {};
  const headline = job?.headline || job?.message || setup?.headline || meta.label;
  const units = boot?.calibration_store?.units?.units;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        flexWrap: 'wrap',
        padding: '9px 18px',
        background: meta.tone === 'bad' ? 'var(--danger-flat)' : 'var(--warn-flat)',
        color: meta.tone === 'bad' ? 'var(--danger-ink)' : 'var(--warn-ink)',
        fontSize: 12.5,
        flex: 'none',
      }}
    >
      <span style={{ flex: 1, minWidth: 0 }}>{headline}</span>

      {state === 'film-in-gate' ? (
        <Btn variant="flat" style={{ height: 26, padding: '0 10px', fontSize: 12 }} onClick={retry}>
          I've taken the film out
        </Btn>
      ) : null}

      {state === 'ambiguous' && units ? (
        <div style={{ display: 'flex', gap: 6 }}>
          {Object.keys(units).map((srl) => (
            <Btn
              key={srl}
              variant="flat"
              style={{ height: 26, padding: '0 10px', fontSize: 12 }}
              onClick={() => api.calibrationSelect({ serial: Number(srl) }).then(() => window.location.reload())}
            >
              Scanner {srl}
            </Btn>
          ))}
        </div>
      ) : null}
    </div>
  );
}
