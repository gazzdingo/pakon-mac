// The one dialog between deciding to scan and film moving. Roll name, film
// type, quality — nothing about transport speed or the lamp, which are the
// backend's own calibrated defaults and not a decision this screen offers.
import React, { useEffect, useState } from 'react';
import { Btn, Seg } from './components';
import { blockedReason } from './api';

export default function ScanModal({ open, onClose, hw, hwBusy, scanJob, onRecheckHw, onStart }) {
  const [name, setName] = useState('');
  const [film, setFilm] = useState('ColNeg');
  const [base, setBase] = useState(16);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (open) {
      setName('');
      setFilm('ColNeg');
      setBase(16);
      setBusy(false);
      setErr(null);
    }
  }, [open]);

  if (!open) return null;

  const bases = hw?.limits?.decodable_bases?.length ? hw.limits.decodable_bases.map(Number) : [16];
  const speeds = hw?.limits?.speeds || {};
  const speed = speeds[base] ?? hw?.calibration?.speed ?? 5917;
  const blocked = blockedReason(hw, scanJob);

  return (
    <div className="scrim on" onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <div className="sheet">
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
          <span className="title" style={{ fontSize: 17 }}>Scan a roll</span>
        </div>

        <div className="field" style={{ marginBottom: 14 }}>
          <span className="lbl">Roll name</span>
          <input
            className="inp"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="2026-08-13 A"
            autoFocus
          />
        </div>

        <div className="field" style={{ marginBottom: 14 }}>
          <span className="lbl">Film</span>
          <Seg
            ariaLabel="Film"
            value={film}
            onChange={setFilm}
            options={[
              ['ColNeg', 'Colour neg'],
              ['BnW', 'B&W'],
              ['POSITIVE', 'Positive', true],
            ]}
          />
        </div>

        <div className="field" style={{ marginBottom: 16 }}>
          <span className="lbl">Quality</span>
          <Seg
            ariaLabel="Quality"
            value={String(base)}
            onChange={(v) => setBase(Number(v))}
            options={bases.map((b) => [String(b), `Base ${b}`])}
          />
          {bases.length > 1 ? (
            <span className="quiet" style={{ marginTop: 6, textAlign: 'center' }}>
              Faster ↔ sharper. Base 16 is calibrated for the best colour.
            </span>
          ) : null}
        </div>

        {err ? (
          <div
            style={{
              background: 'var(--danger-flat)',
              color: 'var(--danger-ink)',
              borderRadius: 'var(--r-sm)',
              padding: '9px 11px',
              marginBottom: 14,
              fontSize: 12,
            }}
          >
            {err}
          </div>
        ) : null}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', alignItems: 'center' }}>
          {blocked ? (
            <span className="quiet" style={{ marginRight: 'auto', fontSize: 12.5 }}>{blocked.title}</span>
          ) : null}
          <Btn variant="flat" disabled={busy} onClick={onClose}>
            Cancel
          </Btn>
          {blocked ? (
            <Btn
              variant="primary"
              disabled={hwBusy || blocked.fix !== 'recheck'}
              onClick={onRecheckHw}
            >
              {hwBusy ? 'Checking…' : 'Recheck scanner'}
            </Btn>
          ) : (
            <Btn
              variant="primary"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setErr(null);
                try {
                  await onStart({
                    base,
                    speed,
                    max_seconds: hw?.limits?.default_seconds ?? 360,
                    name: name.trim(),
                    film_path: film,
                    dx: undefined,
                    lamp_refresh: hw?.limits?.lamp_refresh_s ?? 20,
                    lamp_refresh_mode: 'full',
                  });
                  onClose();
                } catch (e) {
                  setErr(String(e.message || e));
                  setBusy(false);
                }
              }}
            >
              {busy ? 'Starting…' : 'Start scan'}
            </Btn>
          )}
        </div>
      </div>
    </div>
  );
}
