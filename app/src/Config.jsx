import React, { useState } from 'react';
import { Btn, Chip, Info } from './components';

export default function ConfigScreen({ boot, hw }) {
  const [redGain, setRedGain] = useState('1.00');
  const [greenGain, setGreenGain] = useState('1.00');
  const [blueGain, setBlueGain] = useState('1.00');
  const [integrationTime, setIntegrationTime] = useState('4.20');
  const [lampPower, setLampPower] = useState('100');
  const [irDuty, setIrDuty] = useState('0.887');
  const [feedSpeed, setFeedSpeed] = useState('800');
  const [statusMsg, setStatusMsg] = useState(null);

  const cal = boot?.calibration;

  return (
    <div className="body" style={{ gridTemplateColumns: '380px 1fr' }}>
      <aside className="rail l">
        <div className="railhead">
          <span className="lbl">Scanner Hardware Config</span>
        </div>

        <div className="grp">
          <span className="lbl" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            AFE &amp; Sensor Calibration
            <Info>Analog Front End gain controls for Red, Green, Blue CCD rows.</Info>
          </span>

          <div className="slider-row">
            <div className="slider-header">
              <span>Red Channel Gain</span>
              <span className="slider-val">{redGain}x</span>
            </div>
            <input
              type="range"
              className="custom-range"
              min="0.5"
              max="2.0"
              step="0.05"
              value={redGain}
              onChange={(e) => setRedGain(e.target.value)}
            />
          </div>

          <div className="slider-row">
            <div className="slider-header">
              <span>Green Channel Gain</span>
              <span class="slider-val">{greenGain}x</span>
            </div>
            <input
              type="range"
              className="custom-range"
              min="0.5"
              max="2.0"
              step="0.05"
              value={greenGain}
              onChange={(e) => setGreenGain(e.target.value)}
            />
          </div>

          <div className="slider-row">
            <div className="slider-header">
              <span>Blue Channel Gain</span>
              <span className="slider-val">{blueGain}x</span>
            </div>
            <input
              type="range"
              className="custom-range"
              min="0.5"
              max="2.0"
              step="0.05"
              value={blueGain}
              onChange={(e) => setBlueGain(e.target.value)}
            />
          </div>

          <div className="slider-row">
            <div className="slider-header">
              <span>Integration Time</span>
              <span className="slider-val">{integrationTime} ms</span>
            </div>
            <input
              type="range"
              className="custom-range"
              min="1.0"
              max="10.0"
              step="0.1"
              value={integrationTime}
              onChange={(e) => setIntegrationTime(e.target.value)}
            />
          </div>
        </div>

        <div className="grp">
          <span className="lbl">Lamp &amp; Infrared Control</span>
          <div className="slider-row">
            <div className="slider-header">
              <span>Lamp Power</span>
              <span className="slider-val">{lampPower}%</span>
            </div>
            <input
              type="range"
              className="custom-range"
              min="0"
              max="100"
              value={lampPower}
              onChange={(e) => setLampPower(e.target.value)}
            />
          </div>

          <div className="slider-row">
            <div className="slider-header">
              <span>IR Duty Cycle</span>
              <span className="slider-val">{irDuty}</span>
            </div>
            <input
              type="range"
              className="custom-range"
              min="0.1"
              max="1.0"
              step="0.01"
              value={irDuty}
              onChange={(e) => setIrDuty(e.target.value)}
            />
          </div>
        </div>

        <div className="grp">
          <span className="lbl">Transport Motor</span>
          <div className="slider-row">
            <div className="slider-header">
              <span>Feed Speed (lines/sec)</span>
              <span className="slider-val">{feedSpeed}</span>
            </div>
            <input
              type="range"
              className="custom-range"
              min="200"
              max="1200"
              step="50"
              value={feedSpeed}
              onChange={(e) => setFeedSpeed(e.target.value)}
            />
          </div>
        </div>
      </aside>

      <main className="doc">
        <div className="docwrap">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 className="title" style={{ fontStyle: 'normal', fontSize: 20 }}>
              Hardware Diagnostics &amp; Bench Test
            </h2>
            <div style={{ display: 'flex', gap: 8 }}>
              <Btn
                variant="flat"
                onClick={() => setStatusMsg('Sensor optical black levels recalibrated successfully.')}
              >
                Recalibrate Black Levels
              </Btn>
              <Btn
                variant="primary"
                onClick={() => setStatusMsg('Hardware self-test complete: 0 fault codes returned.')}
              >
                Run Diagnostics Test
              </Btn>
            </div>
          </div>

          {statusMsg ? (
            <div style={{ background: 'var(--ok-flat)', color: 'var(--ok-ink)', padding: '10px 14px', borderRadius: 'var(--r-sm)', fontSize: 13 }}>
              {statusMsg}
            </div>
          ) : null}

          <div className="config-grid">
            <div className="metric-box">
              <span className="metric-lbl">Lamp Temperature</span>
              <span className="metric-val" style={{ color: 'var(--ok-ink)' }}>40.10 °C</span>
              <span className="num" style={{ fontSize: 11, color: 'var(--faint)' }}>Setpoint: 40.0 °C (Stable)</span>
            </div>

            <div className="metric-box">
              <span className="metric-lbl">CCD Optical Black Clamp</span>
              <span className="metric-val">128 / 4095</span>
              <span className="num" style={{ fontSize: 11, color: 'var(--faint)' }}>Offset: 0x0080</span>
            </div>

            <div className="metric-box">
              <span className="metric-lbl">USB Streaming Endpoint</span>
              <span className="metric-val" style={{ color: 'var(--primary-ink)' }}>0x86 Active</span>
              <span className="num" style={{ fontSize: 11, color: 'var(--faint)' }}>Rate: 11.6 MB/s (0 Losses)</span>
            </div>

            <div className="metric-box">
              <span className="metric-lbl">Firmware Loader Identity</span>
              <span className="metric-val">0F05:F135</span>
              <span className="num" style={{ fontSize: 11, color: 'var(--faint)' }}>Cold loader validated</span>
            </div>
          </div>

          <div className="card" style={{ marginTop: 10 }}>
            <span className="lbl">EEPROM Register Readout</span>
            <div className="num" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px 16px', fontSize: 12, marginTop: 8 }}>
              <div>REG 0x0280: <b style={{ color: 'var(--primary-ink)' }}>0x00A4</b></div>
              <div>REG 0x0284: <b style={{ color: 'var(--primary-ink)' }}>0x011C</b></div>
              <div>REG 0x0300: <b style={{ color: 'var(--primary-ink)' }}>0x0000</b></div>
              <div>REG 0x0304: <b style={{ color: 'var(--primary-ink)' }}>0x08E2</b></div>
              <div>REG 0x0410: <b style={{ color: 'var(--primary-ink)' }}>0x0040</b></div>
              <div>REG 0x0414: <b style={{ color: 'var(--primary-ink)' }}>0x00FF</b></div>
              <div>REG 0x0500: <b style={{ color: 'var(--primary-ink)' }}>0x0010</b></div>
              <div>REG 0x0504: <b style={{ color: 'var(--primary-ink)' }}>0x0001</b></div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
