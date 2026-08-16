// The one dialog between deciding to scan and film moving. Roll name, film
// type, quality — nothing about transport speed or the lamp, which are the
// backend's own calibrated defaults and not a decision this screen offers.
//
// Positioning the film by hand lives here too, for a specific reason: it is
// needed most exactly when nothing else on this screen works yet -- the gate
// step of first-time calibration (`calib_wizard.py duty-bw`) has been known
// to report the transport clear with film plainly loaded, and jogging a small
// amount is how an operator gets it onto a sensor the classifier can see.
// That is a *pre-calibration* problem, so the jog buttons deliberately do not
// share `blockedReason`'s "no calibration" refusal -- only the subset of its
// checks that are about who currently owns the USB interface.
import React, { useEffect, useState } from 'react';
import { Btn, Chip, Seg } from './components';
import { blockedReason, jogMotor } from './api';

/** A single press = one short, bounded pulse -- not press-and-hold. 350ms is
 *  in the middle of a deliberately small range: at the transport's slowest
 *  legal speed (the jog's own default, 1000 -> 1.0 mm/s, see
 *  pakon_scan.speed_mm_per_s) that is ~0.35mm of film per press, confirmed
 *  against real hardware (a 0.3s pulse moved the film onto the entry sensor;
 *  the same pulse in reverse moved it back off). The backend re-clamps this
 *  regardless (`JOG_MAX_SECONDS` = 5s), so a bug here can make a press do
 *  less than intended but never more. */
const JOG_PULSE_SECONDS = 0.35;

/** Why the transport may not be jogged, independent of whether the *scan
 *  itself* is blocked. Mirrors tools/pakon_app.py's `jog_refusal` /
 *  `motor_jog`'s own checks (which are re-applied server-side regardless of
 *  what this returns) -- present, not mid-scan, not simulated, not another
 *  process's, not already jogging. Deliberately excludes `blockedReason`'s
 *  "no calibration" case. */
function jogBlockedReason(hw, scanJob) {
  if (!hw) return 'Checking…';
  if (scanJob?.status === 'running') return 'Scanning';
  if (hw.foreign_scan) return 'Scanning elsewhere';
  if (hw.jog?.active) return 'Already jogging';
  if (hw.state === 'loading_firmware') return 'Loading firmware…';
  if (!hw.present) return 'No scanner found';
  if (hw.simulated) return 'Simulated scanner — no motor to move';
  if (hw.state !== 'ready') return hw.hint || 'Not answering';
  return null;
}

function SenseChip({ sense }) {
  if (!sense) return null;
  if (sense.error) return <Chip tone="warn">Sensors: {sense.error}</Chip>;
  if (sense.present === true) {
    const where = sense.at_entry && sense.at_exit ? ' (entry + exit)'
      : sense.at_entry ? ' (entry)' : sense.at_exit ? ' (exit)' : '';
    return <Chip tone="ok" dot>Film at sensor{where}</Chip>;
  }
  if (sense.present === false) return <Chip tone="info">Transport clear</Chip>;
  return <Chip tone="">Sensors: no reading — try another pulse</Chip>;
}

function PositionFilm({ hw, scanJob }) {
  const [jogging, setJogging] = useState(null); // 'forward' | 'reverse' | null
  const [sense, setSense] = useState(null);
  const [err, setErr] = useState(null);

  const blocked = jogBlockedReason(hw, scanJob);
  const off = Boolean(blocked) || jogging != null;

  const jog = async (direction) => {
    setErr(null);
    setJogging(direction);
    try {
      const r = await jogMotor({ direction, seconds: JOG_PULSE_SECONDS });
      setSense(r.film_sense || null);
      if (!r.ok && r.error) setErr(r.error);
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setJogging(null);
    }
  };

  return (
    <div className="field" style={{ marginBottom: 16 }}>
      <span className="lbl">Position film</span>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <Btn variant="flat" disabled={off} onClick={() => jog('reverse')}>
          {jogging === 'reverse' ? 'Rewinding…' : '◀ Rewind'}
        </Btn>
        <Btn variant="flat" disabled={off} onClick={() => jog('forward')}>
          {jogging === 'forward' ? 'Advancing…' : 'Advance ▶'}
        </Btn>
        <SenseChip sense={sense} />
        {blocked && !jogging ? <span className="quiet" style={{ fontSize: 12 }}>{blocked}</span> : null}
      </div>
      {err ? (
        <span className="quiet" style={{ color: 'var(--danger-ink)', fontSize: 11.5, marginTop: 4 }}>
          {err}
        </span>
      ) : null}
      <span className="quiet" style={{ marginTop: 6, fontSize: 11.5 }}>
        Each press moves the film a short, fixed amount (~0.35mm) and shows what the film sensors
        see right after — useful when the gate reads "clear" but film is loaded.
      </span>
    </div>
  );
}

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

        <PositionFilm hw={hw} scanJob={scanJob} />

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
                    // Base 4/8 have no calibration of their own, so the
                    // backend always warns on them; that warning is the
                    // "not calibrated" caption already shown above, not a
                    // second confirmation to ask for here.
                    force: base !== 16,
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
