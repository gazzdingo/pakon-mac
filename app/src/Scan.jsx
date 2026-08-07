// Scan — design/variants/console-scan.html.
//
// Same furniture as Review: settings rail left, machine rail right, the strip
// in the middle, the roll along the floor.
//
// Honesty note that shapes this screen: driving the transport is not wired.
// The design's primary action is "Scan strip"; a button that cannot scan is
// worse than no button, so the primary action here opens a capture using
// these settings — which is what the settings genuinely feed — and "Scan
// strip" sits disabled beside it with the reason behind an Info.
//
// There is also no Preview button, and there cannot be one: a transport
// scanner feeds forwards, once. "Preview" in this app is a render quality,
// not a scan pass.
import React from 'react';
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
  State,
  Toggle,
} from './components';
import * as api from './api';

const PERFS = Array.from({ length: 48 }, (_, i) => i);

export default function Scan({ roll, rolls, sel, setSel, boot, machine, onOpen, onPickRoll }) {
  const cal = boot?.calibration?.readme;
  const cfg = cal?.config;
  const sync = roll?.sync;

  // The strip picture shows the frames around the selection, real thumbnails.
  const window6 = roll
    ? roll.frames.slice(Math.max(0, Math.min(sel - 2, roll.frames.length - 6)), Math.max(6, Math.min(sel + 4, roll.frames.length)))
    : [];

  return (
    <>
      <div className="body" style={{ gridTemplateColumns: '296px minmax(0,1fr) 292px' }}>
        {/* ── every parameter, visible before you commit ── */}
        <Rail side="l" aria-label="Capture settings">
          <RailHead title="Capture settings" />

          <Grp>
            <Field
              label="Film path"
              info={
                <>
                  No default. A capture carries no DX packets, so the stock is stated by hand and the
                  decode path refuses to assume colour negative.
                </>
              }
            >
              <Seg
                ariaLabel="Film path"
                value={roll?.film_path || 'ColNeg'}
                options={[
                  ['ColNeg', 'Colour neg'],
                  ['BnW', 'B&W'],
                  ['POSITIVE', 'Positive'],
                ]}
                onChange={() => onOpen()}
              />
            </Field>

            <Field
              label="DX"
              info={
                <>
                  Typed, not read. Captures carry no DX packets, and{' '}
                  <span className="num">tools/dx_decode.py</span> has never been validated against a
                  real roll.
                </>
              }
            >
              <div className="inp">
                {roll?.dx || '—'}
                <span className="sp" />
                <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--mute)' }}>
                  {roll?.stock?.name || roll?.film_path || 'not set'}
                </span>
              </div>
            </Field>
          </Grp>

          <Grp>
            <Field
              label="Resolution"
              value="2000 × 3000"
              info={
                <>
                  <b>Base 16 only.</b> The decoder accepts <span className="num">6000</span>-word
                  lines, and the committed calibration was captured at{' '}
                  <span className="num">{cfg?.dpi_base || 'DpiBase16_35'}</span>. Base 4 and 8 need
                  their own dark and gain references and a decoder that handles their line length.
                </>
              }
            >
              <Seg
                ariaLabel="Resolution"
                value="16"
                options={[
                  ['4', 'Base 4', true],
                  ['8', 'Base 8', true],
                  ['16', 'Base 16'],
                ]}
              />
            </Field>

            <Toggle
              on
              disabled
              info={
                <>
                  The Ansel preference path. It is a <b>stand-in</b> —{' '}
                  <span className="num">SETSHIFTS_12_PORTED = False</span> — so its tone is not yet
                  Kodak's, and it cannot be switched off from here.
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
                  never run. A four-channel line is <span className="num">8000</span> words; the
                  decoder takes <span className="num">6000</span>.
                </>
              }
            >
              Digital ICE
            </Toggle>
          </Grp>

          <div className="railfoot">
            <Btn variant="primary big" onClick={onOpen}>
              Open capture…
            </Btn>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Btn variant="flat big" disabled style={{ height: 34 }}>
                Scan strip
              </Btn>
              <Info side="left">
                <b>Not wired.</b> Capture over EP <span className="num">0x86</span> is proven in{' '}
                <span className="num">tools/pakon_session.py</span> —{' '}
                <span className="num">11.6 MB/s</span>, zero losses over a{' '}
                <span className="num">60 s</span> run — and nothing connects it to this window.
                <br />
                <br />
                There is no pre-scan preview either, and there cannot be: the transport feeds
                forwards, once.
              </Info>
            </div>
          </div>
        </Rail>

        {/* ── the strip ── */}
        <main className="scanstage">
          <div className="stagehead">
            <span className="title">{roll ? roll.name : 'No roll open'}</span>
            <Chip tone="warn" dot>
              Transport not wired
            </Chip>
            <span className="sp" />
            <span className="quiet">Frames are found in the capture, not framed before it.</span>
          </div>

          <div className="filmwrap">
            <div className="film" role="img" aria-label="The strip as captured">
              <div className="perf t">
                {PERFS.map((i) => (
                  <i key={i} />
                ))}
              </div>
              <div className="perf b">
                {PERFS.map((i) => (
                  <i key={i} />
                ))}
              </div>
              <div className="frames">
                {(window6.length ? window6 : PERFS.slice(0, 6)).map((f, i) =>
                  roll ? (
                    <span key={f.index} onClick={() => setSel(f.index)} style={{ cursor: 'pointer' }}>
                      <img src={api.frameUrl(roll.id, f.index, 'thumb', f.version)} alt="" loading="lazy" />
                      <b>{f.index + 1}</b>
                    </span>
                  ) : (
                    <span key={i} className="pending" />
                  ),
                )}
              </div>
            </div>
          </div>

          <div className="telem">
            <div>
              <span className="lbl">Lines</span>
              <b>{roll ? roll.lines.toLocaleString() : '—'}</b>
            </div>
            <div>
              <span className="lbl">Size</span>
              <b>{api.fmtBytes(sync?.bytes)}</b>
            </div>
            <div>
              <span className="lbl">Sync losses</span>
              <b>{sync ? sync.losses : '—'}</b>
            </div>
            <div>
              <span className="lbl">Clean</span>
              <b>{sync ? `${sync.pct_clean} %` : '—'}</b>
            </div>
            <div>
              <span className="lbl">Frames</span>
              <b>{roll ? roll.frames.length : '—'}</b>
            </div>
          </div>
        </main>

        {/* ── the machine, always answerable ── */}
        <Rail side="r" aria-label="Machine state">
          <RailHead title="Machine" />

          <Grp title="Read now">
            <State rows={machine.read} />
          </Grp>

          <Grp title="Not wired">
            <State rows={machine.unwired} />
          </Grp>

          <Grp title="Calibration reference">
            <State
              rows={[
                ['Dark', cal ? `${cal.dark_source.lines.toLocaleString()} lines` : '—', cal ? 'good' : ''],
                ['Bright', cal ? `${cal.bright_source.lines.toLocaleString()} lines` : '—', cal ? 'good' : ''],
                ['Lamp PWM', cfg?.lamp_pwm_N ?? '—'],
                [
                  'Bright mean',
                  cal ? cal.bright_source.means[1].toFixed(0) : '—',
                  '',
                  <>
                    Deliberately near <span className="num">50 000</span>, not the vendor's{' '}
                    <span className="num">64 000</span> target, so no channel clips.
                  </>,
                ],
                ['Captured', cal?.captured ?? '—'],
              ]}
            />
          </Grp>
        </Rail>
      </div>

      {roll ? (
        <Filmstrip roll={roll} selected={sel} onSelect={setSel}>
          <span className="lbl">This roll</span>
        </Filmstrip>
      ) : null}
    </>
  );
}
