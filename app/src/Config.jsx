// Config — what this machine is set to.
// Cleaned up to show only actionable, human-readable machine health.

import React from 'react';
import { Btn, Chip, Grp, Info, Rail, RailHead, Seg, State, Toggle } from './components';
import * as api from './api';

/* ── the film transport ─────────────────────────────────────────────────── */

/** Why the transport cannot be jogged right now, in the shape blockedReason()
 *  uses in Scan.jsx — but deliberately not that function. Two of its refusals
 *  are about making a capture and would be untrue here. tools/WRITES_LOCKED
 *  guards anything that "WRITES, ERASES, PROGRAMS or MODE-SWITCHES", and a jog
 *  does none of those: it sets one volatile speed register and issues a run
 *  command, and nothing it touches survives a power cycle — which is the whole
 *  argument tools/spin_motor.py makes for existing. And calibration is what a
 *  scan's exposure needs, not what the motor board at 0x44 needs.
 *
 *  What is left is the set that is genuinely about who is holding the USB
 *  interface, because that is the only thing a jog can collide with. */
function jogBlocked(hw, scanJob) {
  if (!hw) return 'The machine has not been probed yet.';
  if (scanJob?.status === 'running')
    return 'A scan is running. It owns the transport and is already moving film.';
  if (hw.foreign_scan)
    return (
      hw.hint ||
      `Another process (pid ${hw.foreign_scan.pid}) is scanning and owns the USB interface.`
    );
  if (hw.state === 'unreachable')
    return hw.hint || 'The hardware probe stopped answering.';
  if (!hw.present) return 'Nothing at 0f05:f135 on USB.';
  if (hw.state === 'loading_firmware')
    return 'Firmware is loading. That loader owns the USB interface until it finishes.';
  if (hw.state === 'needs_firmware')
    return 'No firmware loaded — the motor board at 0x44 does not answer until it is.';
  if (hw.state !== 'ready') return hw.hint || `The scanner is ${hw.state}.`;
  /* A jog started somewhere else — another window on the same backend. It
     holds the USB interface for as long as it runs, and the backend refuses a
     second one; saying so here is better than a button that only ever fails. */
  if (hw.jog?.active)
    return `The transport is already jogging ${hw.jog.direction}. It stops on its own.`;
  return null;
}

const SHORT = [1, 3, 5];
const LONG = [15, 30, 60];

/** Reverse / Forward, for respooling a roll or repositioning it in the gate.
 *
 *  The backend runs tools/spin_motor.py as a subprocess and answers when the
 *  transport has stopped, so the button is busy for exactly as long as the film
 *  is moving and the result on screen is what happened, not what was asked for.
 */
function FilmTransport({ hw, scanJob }) {
  const [long, setLong] = React.useState(false);
  const [seconds, setSeconds] = React.useState(SHORT[0]);
  const [busy, setBusy] = React.useState(null);
  const [note, setNote] = React.useState(null);

  const blocked = jogBlocked(hw, scanJob);

  /* A simulated scanner is replaying a capture file. There is no motor, so
     there is no control — the same rule the rest of this app follows for
     things that cannot do anything, rather than a button that would only ever
     be refused. */
  if (hw?.simulated) return null;

  const choose = (on) => {
    setLong(on);
    setSeconds(on ? LONG[0] : SHORT[0]);
    setNote(null);
  };

  const run = async (direction) => {
    setBusy(direction);
    setNote(null);
    try {
      const r = await api.jogMotor({ direction, seconds, long });
      setNote({
        tone: 'ok',
        text: `Ran ${direction} for ${r.seconds ?? seconds} s at speed ${r.speed}. Transport stopped.`,
      });
    } catch (e) {
      // The backend's own words — a refusal names who is holding the interface,
      // a failure carries spin_motor.py's last line. Neither is guessed here.
      setNote({ tone: 'bad', text: String(e.message || e) });
    } finally {
      setBusy(null);
    }
  };

  const opts = (long ? LONG : SHORT).map((v) => [
    String(v),
    `${v} s`,
    !!busy || !!blocked,
  ]);

  return (
    <div className="card" style={{ marginTop: 12 }}>
      <span className="lbl" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        Film transport
        <Info>
          Three packets to board <b>0x44</b> (AD_MOTOR, the PICM_PLUS):{' '}
          <span className="num">02 05 44 02 A5 &lt;lo&gt; &lt;hi&gt;</span> sets the speed
          register and moves nothing, then <span className="num">04 03 44 00 A0</span> runs
          forward, <span className="num">A1</span> reverse,{' '}
          <span className="num">A2</span> stops. Decoded from
          FN_bDriveMotorAdvanceFilm and written up in
          docs/12-command-protocol.md §5(b). The stop is sent from a{' '}
          <span className="num">finally:</span> block in tools/spin_motor.py, so
          it goes out on a clean finish, on a USB error, and if the backend has
          to terminate the run.
        </Info>
        <span className="sp" />
        <Chip tone="warn" dot>
          Film moves
        </Chip>
      </span>

      <p className="quiet" style={{ fontSize: 12, marginBottom: 12, lineHeight: 1.5 }}>
        Respool a roll, or reposition it in the gate. The lamp stays off and
        nothing is captured — this only turns the transport, for as long as you
        ask and no longer.
      </p>

      {/* Our own jog is reported by the buttons, not as a refusal — the poll
          sees it and would otherwise paint this red mid-run. */}
      {blocked && !busy ? (
        <p style={{ fontSize: 12, color: 'var(--danger-ink)', marginBottom: 12 }}>
          {blocked}
        </p>
      ) : null}

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <Btn
          variant="flat"
          disabled={!!blocked || !!busy}
          onClick={() => run('reverse')}
        >
          {busy === 'reverse' ? `Reversing… ${seconds} s` : '◀ Reverse'}
        </Btn>
        <Btn
          variant="flat"
          disabled={!!blocked || !!busy}
          onClick={() => run('forward')}
        >
          {busy === 'forward' ? `Forward… ${seconds} s` : 'Forward ▶'}
        </Btn>

        <Seg
          options={opts}
          value={String(seconds)}
          onChange={(v) => setSeconds(Number(v))}
          ariaLabel="How long to run the transport"
        />

        <Toggle on={long} disabled={!!busy} onChange={choose}>
          Respool run
          <Info side="left">
            Five seconds is the cap by default because a short jog is for
            nudging film in the gate, where a runaway is pure downside.
            Respooling a whole roll is a different job with a real reason to run
            longer, so the longer cap is a choice you make rather than a default
            quietly raised on your behalf — the same two tiers as{' '}
            <span className="num">--long</span> in tools/spin_motor.py. The stop
            still goes out on every exit path. Watch the machine.
          </Info>
        </Toggle>
      </div>

      {note ? (
        <p
          style={{
            fontSize: 12,
            marginTop: 12,
            color: note.tone === 'bad' ? 'var(--danger-ink)' : 'var(--ok-ink)',
          }}
        >
          {note.text}
        </p>
      ) : null}
    </div>
  );
}

export default function ConfigScreen({ boot, hw, hwBusy, onRecheckHw, scanJob }) {
  const tables = boot?.calibration || {};
  const store = boot?.calibration_store || {};
  const vendor = boot?.vendor_data || {};
  const lamp = (scanJob?.status === 'running' ? scanJob?.lamp : hw?.lamp) || null;

  return (
    <div className="body" style={{ gridTemplateColumns: '320px minmax(0,1fr)' }}>
      <Rail side="l" aria-label="Machine">
        <RailHead title="Machine">
          <Btn
            style={{ height: 24, padding: '0 8px', fontSize: 12 }}
            disabled={hwBusy}
            onClick={onRecheckHw}
          >
            {hwBusy ? 'Checking…' : 'Recheck'}
          </Btn>
        </RailHead>

        <Grp>
          <State
            rows={[
              [
                'Scanner',
                hw?.simulated
                  ? 'simulated'
                  : hw?.present
                    ? hw.state === 'ready'
                      ? 'ready'
                      : hw.state === 'loading_firmware'
                        ? 'loading firmware…'
                        : hw.state === 'needs_firmware'
                          ? 'no firmware'
                          : hw.state
                    : 'absent',
                hw?.simulated ? 'warn' : hw?.state === 'ready' ? 'good' : hw?.present ? 'warn' : 'na',
              ],
              [
                'Probe',
                hw?.cached ? 'cached' : hw?.probed_at ? 'live' : 'not probed',
                hw?.cached ? 'warn' : hw?.probed_at ? 'good' : 'na',
              ],
              [
                'Exposure tables',
                tables?.present ? 'loaded' : 'missing',
                tables?.present ? 'good' : 'bad',
              ],
              [
                'Unit EEPROM',
                store?.have_calibration ? 'saved' : 'not read',
                store?.have_calibration ? 'good' : 'warn',
              ],
            ]}
          />
          {hw?.hint ? (
            <p className="quiet" style={{ fontSize: 12, marginTop: 8 }}>
              {hw.hint}
            </p>
          ) : null}
        </Grp>
      </Rail>

      <main className="doc">
        <div className="docwrap">
          <h2 className="title" style={{ fontStyle: 'normal', fontSize: 20 }}>
            Scanner Health
          </h2>
          
          <div className="card" style={{ marginTop: 12 }}>
            <State
              rows={[
                [
                  'Lamp status',
                  lamp?.ok === false ? 'Fault detected' : (lamp ? 'OK' : 'Unknown'),
                  lamp?.ok === false ? 'bad' : (lamp ? 'good' : 'na')
                ],
                [
                  'Lamp temperature',
                  lamp?.temp_lb_c != null ? `${lamp.temp_lb_c.toFixed(1)} °C` : '—',
                  lamp?.temp_lb_c != null ? (lamp.temp_lb_c > 45 ? 'warn' : 'good') : 'na'
                ],
                [
                  'Calibration status',
                  store?.have_calibration ? (store.selection?.needs_attention ? 'Needs attention' : 'Saved') : 'Not read',
                  store?.have_calibration ? (store.selection?.needs_attention ? 'warn' : 'good') : 'na'
                ],
                [
                  'Colour data',
                  vendor?.ansel_root_ok ? 'Found' : 'Missing',
                  vendor?.ansel_root_ok ? 'good' : 'bad'
                ]
              ]}
            />
          </div>

          <FilmTransport hw={hw} scanJob={scanJob} />

          <p className="quiet" style={{ marginTop: 24, fontSize: 13, lineHeight: 1.5 }}>
            Hardware settings (such as exposure values and motor speed) are locked while the scanner is in operation. The backend manages all analogue front-end registers dynamically to ensure optimal and consistent image quality.
          </p>
        </div>
      </main>
    </div>
  );
}
