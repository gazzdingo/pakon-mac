// Config — what this machine is set to, and where each number came from.
//
// WHAT THIS SCREEN USED TO BE, because the replacement only makes sense
// against it. It was seven sliders — R/G/B channel gain, integration time,
// lamp power, IR duty cycle, transport feed speed — each bound to a useState
// and sent absolutely nowhere. Moving "Lamp Power" to 40% changed a number on
// screen and nothing else in the universe. Beside them were two enabled
// buttons that printed invented successes ("Sensor optical black levels
// recalibrated successfully.", "Hardware self-test complete: 0 fault codes
// returned."), four hard-coded metric tiles reading 40.10 °C and 11.6 MB/s
// with no scanner attached, and an eight-register "EEPROM Register Readout"
// that was typed by hand.
//
// Every one of those was a fabricated hardware reading on a screen that looked
// live. That is the most dangerous thing a scanner UI can do: this application
// drives a motor across the owner's only copy of their photographs, and its
// worth depends entirely on the user being able to believe what it says.
//
// So none of it is here. Everything below is a value the backend actually
// holds, and every one says where it came from. Nothing on this screen writes
// to the machine, and the screen says that too — because the honest answer to
// "why can I not adjust the lamp?" is not a disabled slider, it is the reason,
// and the reason is good: the exposure triad is three registers holding ONE
// setting, and the committed dark and gain tables are only valid at the value
// they were captured at.
import React from 'react';
import { Btn, Chip, Grp, Info, Rail, RailHead, State } from './components';
import * as api from './api';

/** A measured value with its provenance. `src` is where it comes from — a
 *  register, a file — never a guess. */
function Val({ label, value, src, tone, info }) {
  return (
    <div className="metric-box">
      <span className="metric-lbl">{label}</span>
      <span className="metric-val" style={tone ? { color: tone } : undefined}>
        {value ?? '—'}
      </span>
      <span className="num" style={{ fontSize: 11, color: 'var(--faint)' }}>
        {src}
        {info ? <Info side="left">{info}</Info> : null}
      </span>
    </div>
  );
}

const trip = (a) => (Array.isArray(a) ? a.join(' · ') : '—');
const n = (v, d = 1) => (typeof v === 'number' ? v.toFixed(d) : '—');

export default function ConfigScreen({ boot, hw, hwBusy, onRecheckHw, scanJob }) {
  const cal = hw?.calibration || null; // ScanConfig.from_calibration()
  const gate = hw?.gate || null;
  const lim = hw?.limits || {};
  const readme = boot?.calibration?.readme || null;
  const tables = boot?.calibration || {};
  const store = boot?.calibration_store || {};
  const vendor = boot?.vendor_data || {};
  const lamp = (scanJob?.status === 'running' ? scanJob?.lamp : hw?.lamp) || null;
  const live = scanJob?.status === 'running';

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
                      ? '0f05:f135'
                      : hw.state
                    : 'absent',
                hw?.simulated ? 'warn' : hw?.state === 'ready' ? 'good' : hw?.present ? 'warn' : 'na',
                hw?.hint || null,
              ],
              [
                'Probe',
                hw?.cached
                  ? `cached${hw?.age_s != null ? ` · ${hw.age_s}s` : ''}`
                  : hw?.probed_at
                    ? 'live'
                    : 'not probed',
                hw?.cached ? 'warn' : hw?.probed_at ? 'good' : 'na',
                <>
                  A probe is a USB round trip, so it is cached for 3 s. It is
                  refused outright while a scan owns the interface — this window
                  will not take the handle from a running scan, and will not
                  dress a stale reading as a live one.
                </>,
              ],
              [
                'Writes',
                hw?.writes_locked ? 'locked' : 'unlocked',
                hw?.writes_locked ? 'warn' : 'good',
                <>
                  <span className="num">tools/WRITES_LOCKED</span>. While it
                  exists no register write is sent and no scan can start.
                </>,
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
              [
                'Colour data',
                vendor?.ansel_root_ok ? 'found' : 'missing',
                vendor?.ansel_root_ok ? 'good' : 'bad',
              ],
            ]}
          />
        </Grp>

        <Grp title="Nothing here writes">
          <p className="quiet">
            This screen is read-only. The scanner's exposure is not adjustable
            from the application, and the reason is below rather than behind a
            greyed-out slider.
          </p>
        </Grp>
      </Rail>

      <main className="doc">
        <div className="docwrap">
          <h2 className="title" style={{ fontStyle: 'normal', fontSize: 20 }}>
            Exposure
          </h2>
          <p className="quiet">
            Three registers, one setting. <span className="num">N = trunc(4093 × 0.24)</span>{' '}
            and the <span className="num">0x91</span> rate follows from the same exposure, so
            changing one means recomputing all three — and the committed dark and gain tables
            stop being valid, because they were captured at this exposure and no other. That is
            why these are read from{' '}
            <span className="num">calibration/README.json</span> and are not settings.
          </p>
          <div className="config-grid">
            <Val
              label="FPGA integration"
              value={cal?.integration ?? '—'}
              src="0x82 index 6"
            />
            <Val label="Lamp PWM N" value={cal?.lamp_n ?? '—'} src="lamp board, N" />
            <Val
              label="Light-board line rate"
              value={cal?.line_rate_0x91 ?? '—'}
              src="register 0x91"
            />
            <Val
              label="Captured"
              value={readme?.captured || '—'}
              src={readme?.unit ? String(readme.unit).slice(0, 42) : 'calibration/README.json'}
            />
          </div>

          <h2 className="title" style={{ fontStyle: 'normal', fontSize: 20, marginTop: 6 }}>
            Analogue front end
          </h2>
          <p className="quiet">
            The real per-channel gains, as integers, at the values the committed calibration was
            taken at — not a 0.5–2.0× multiplier, which is not a thing this AFE has.
          </p>
          <div className="config-grid">
            <Val label="AFE gains R · G · B" value={trip(cal?.afe_gains)} src="AFE gain registers" />
            <Val
              label="AFE offsets R · G · B"
              value={trip(cal?.afe_offsets)}
              src="AFE offset registers"
            />
            <Val
              label="Lamp on-counts R · G · B"
              value={trip(cal?.on_counts)}
              src="light board"
            />
            <Val
              label="Lamp levels R · G · B · Ir"
              value={trip(cal?.levels)}
              src="light board"
              info={
                <>
                  The infrared level is part of the same set. It is{' '}
                  <span className="num">{cal?.levels?.[3] ?? '—'}</span> in the committed
                  calibration, and no IR capture has ever been taken on this unit — an IR line is{' '}
                  <span className="num">8000</span> words and the decoder takes{' '}
                  <span className="num">6000</span>.
                </>
              }
            />
            <Val label="Pixel offset" value={cal?.pixel_offset ?? '—'} src="FPGA" />
            <Val label="Pixel height" value={cal?.pixel_height ?? '—'} src="FPGA" />
            <Val
              label="FPGA control"
              value={cal?.fpga_ctrl != null ? `0x${Number(cal.fpga_ctrl).toString(16).padStart(4, '0').toUpperCase()}` : '—'}
              src="FPGA ctrl word"
            />
            <Val
              label="Dark / gain tables"
              value={
                tables?.['dark_2000x3.npy']?.present && tables?.['gain_2000x3.npy']?.present
                  ? 'both present'
                  : 'missing'
              }
              src={`${api.fmtBytes(
                (tables?.['dark_2000x3.npy']?.bytes || 0) + (tables?.['gain_2000x3.npy']?.bytes || 0),
              )} in calibration/`}
              tone={
                tables?.['dark_2000x3.npy']?.present ? 'var(--ok-ink)' : 'var(--danger-ink)'
              }
            />
          </div>

          <h2 className="title" style={{ fontStyle: 'normal', fontSize: 20, marginTop: 6 }}>
            Transport
          </h2>
          <p className="quiet">
            <span className="num">MotorSpeedPlus</span>, register{' '}
            <span className="num">0xA5</span>, from the recovered Windows hive. Note the
            direction: base 16 is the <b>slowest</b> — it is the highest resolution, so the film
            has to crawl.
          </p>
          <div className="config-grid">
            <Val
              label="Speed, base 16"
              value={lim?.speeds?.[16] ?? cal?.speed ?? '—'}
              src={cal?.speed_source || 'DpiBase16_35'}
            />
            <Val label="Speed, base 8" value={lim?.speeds?.[8] ?? '—'} src="DpiBase8_35 · not decodable" />
            <Val label="Speed, base 4" value={lim?.speeds?.[4] ?? '—'} src="DpiBase4_35 · not decodable" />
            <Val
              label="Register range"
              value={
                lim?.speed_min != null ? `${lim.speed_min} – ${lim.speed_max}` : '—'
              }
              src="0xA5 legal values"
            />
            <Val
              label="Scan time cap"
              value={lim?.default_seconds ? `${n(lim.default_seconds, 0)} s` : '—'}
              src={`hard ceiling ${n(lim?.hard_seconds, 0)} s`}
              info={
                <>
                  Derived from the distance the vendor bounds a run by, not guessed: a
                  36-exposure roll is <span className="num">1670</span> mm and{' '}
                  <span className="num">MotorSpeedPlus/1000</span> is mm/s. One constant cannot be
                  right for three speeds that differ by 4.4×.
                </>
              }
            />
            <Val
              label="Decodable bases"
              value={(lim?.decodable_bases || []).join(', ') || '—'}
              src="6000-word lines only"
            />
          </div>

          <h2 className="title" style={{ fontStyle: 'normal', fontSize: 20, marginTop: 6 }}>
            Roll-end classifier
          </h2>
          <p className="quiet">
            Three states, not two — clear gate, film, dark — with the levels measured from{' '}
            <span className="num">calibration/</span>. <b>Dark stops the motor</b>: the previous
            detector tested only "bright enough to be a clear gate", so a dead lamp read as film
            present and the transport kept running.
          </p>
          <div className="config-grid">
            <Val label="Dark level" value={n(gate?.dark_level)} src="measured, calibration/" />
            <Val label="Clear level" value={n(gate?.clear_level)} src="measured, calibration/" />
            <Val
              label="Dark cut (hard / soft)"
              value={gate ? `${n(gate.dark_hard)} / ${n(gate.dark_soft)}` : '—'}
              src="stops the motor"
              tone="var(--danger-ink)"
            />
            <Val label="Clear cut" value={n(gate?.clear_cut)} src="gate is empty above this" />
            <Val
              label="Valid columns"
              value={gate?.valid_columns ? `${gate.valid_columns[0]} – ${gate.valid_columns[1]}` : '—'}
              src={`${gate?.valid_count ?? '—'} of 2000 usable`}
            />
            <Val
              label="Confirm windows"
              value={gate ? `${gate.dark_confirm_lines} lines` : '—'}
              src={`roll end after ${gate?.roll_end_lines ?? '—'} clear lines`}
            />
          </div>

          <h2 className="title" style={{ fontStyle: 'normal', fontSize: 20, marginTop: 6 }}>
            Live readings
          </h2>
          <p className="quiet">
            These exist only when the machine is actually answering. With no scanner attached
            they read <span className="num">—</span>, which is the honest value; a lamp
            temperature shown beside an unplugged scanner is worse than no reading at all.
          </p>
          <div className="config-grid">
            <Val
              label="Lamp status"
              value={lamp?.status_hex || '—'}
              src={`register 0x83${live ? ' · polled by the scan' : ''}`}
              tone={lamp?.ok === false ? 'var(--danger-ink)' : undefined}
              info={
                <>
                  Fault bits <span className="num">5</span> and{' '}
                  <span className="num">6</span> abort a scan. Polled once a second while the
                  transport runs — the vendor never does this.
                </>
              }
            />
            <Val
              label="Lamp temperature"
              value={lamp?.temp_lb_c != null ? `${lamp.temp_lb_c.toFixed(2)} °C` : '—'}
              src="register 0x88, raw × 0.0625"
              info={
                <>
                  The board self-regulates to <span className="num">40.0</span> °C with the host
                  sending nothing, so a reading near 40 is the board working — but it has to be{' '}
                  <b>read</b>, not assumed, and with nothing attached the honest value is{' '}
                  <span className="num">—</span>.
                </>
              }
            />
            <Val
              label="Lamp polls"
              value={live ? (lamp?.polls ?? 0) : '—'}
              src={live ? 'this scan' : 'only during a scan'}
            />
            <Val
              label="Capture rate"
              value={scanJob?.mib_s ? `${n(scanJob.mib_s, 1)} MiB/s` : '—'}
              src={
                scanJob?.sync_breaks != null && scanJob?.status !== 'running'
                  ? `${scanJob.sync_breaks} sync breaks`
                  : 'measured on the last scan'
              }
            />
          </div>

          <div className="card" style={{ marginTop: 10 }}>
            <span className="lbl" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              This scanner's own EEPROM calibration
              <Info>
                <b>Per scanner, not per install.</b> These are this machine's own tables and
                exist nowhere else — a different F-135 needs its own read.
                <br />
                <br />
                Read once, deliberately, and never automatically: the EEPROM answers correctly
                only on the <b>first read after a power cycle</b>, so the one good read of a cycle
                is a resource that can be spent. Nothing on this screen spends it. The store is
                append-only and its saved images are read-only, so no calibration is ever deleted
                or overwritten.
              </Info>
            </span>
            {store?.have_calibration ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 6 }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <Chip tone={store.selection?.needs_attention ? 'warn' : 'ok'} dot>
                    {store.selection?.needs_attention ? 'check this' : 'saved'}
                  </Chip>
                  <span className="num" style={{ fontSize: 12 }}>
                    {store.selection?.stamp || '—'}
                  </span>
                  <span className="quiet">{store.selection?.reason || ''}</span>
                </div>
                <span className="num" style={{ fontSize: 11, color: 'var(--faint)' }}>
                  {store.selection?.reads?.length || 0} read
                  {store.selection?.reads?.length === 1 ? '' : 's'} kept · {store.store}
                </span>
              </div>
            ) : (
              <p className="quiet" style={{ marginTop: 6 }}>
                Not read yet. This is deliberate — it is never read automatically. The Scanner
                screen's Recheck reports whether a read is possible now.
              </p>
            )}
          </div>

          <p className="quiet" style={{ marginTop: 4 }}>
            Everything on this screen is a value the backend holds and can name the source of. If
            a reading is not available it says <span className="num">—</span>. Nothing here is
            computed for display, and nothing here writes to the machine.
          </p>
        </div>
      </main>
    </div>
  );
}
