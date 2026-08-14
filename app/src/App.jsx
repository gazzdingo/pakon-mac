// The Console — shell.
//
// ONE PAGE. Tabs across the top, one per open roll, the way a browser holds
// tabs — because a roll is not a step in a wizard, it is a thing you have
// open, and you can have several. A tab that is still scanning goes on
// scanning while you look at another one; the job lives here, above every
// screen, for exactly that reason.
//
// Under the tabs: a toolbar naming the active roll, then whichever of four
// things is true for it — nothing yet, scanning now, its contact sheet, or
// one frame being edited. No settings live outside a modal: Scan a roll opens
// one, Export opens another, and neither explains itself.
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { FilmBand, Spinner, useTheme } from './components';
import TabStrip from './TabStrip';
import Toolbar from './Toolbar';
import Empty from './Empty';
import Scanning from './Scanning';
import ContactSheet from './ContactSheet';
import FrameEditor from './FrameEditor';
import ScanModal from './ScanModal';
import ExportModal from './ExportModal';
import Boundaries from './Boundaries';
import { OpenDialog, CleanupDialog } from './Dialogs';
import CalibrationBanner, { useCalibrationSetup } from './CalibrationSetup';
import * as api from './api';

export default function App() {
  const [ready, setReady] = useState(false);
  const [fatal, setFatal] = useState(null);
  const [dark, setDark] = useTheme();

  const [boot, setBoot] = useState(null);
  const [rolls, setRolls] = useState([]);
  const [roll, setRoll] = useState(null);
  const [sel, setSel] = useState(0);
  // 'new' (the in-flight scan), a roll id, or null (nothing open).
  const [activeTab, setActiveTab] = useState(null);
  const [view, setView] = useState('contact'); // 'contact' | 'editor'

  const [scanModalOpen, setScanModalOpen] = useState(false);
  const [openDlgOpen, setOpenDlgOpen] = useState(false);
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [boundsOpen, setBoundsOpen] = useState(false);
  const [boundsBusy, setBoundsBusy] = useState(false);
  const [cleanup, setCleanup] = useState(null);

  const [exportJob, setExportJob] = useState(null);
  const [exporting, setExporting] = useState(false);
  const [collision, setCollision] = useState(null);
  const [exportCfg, setExportCfg] = useState({
    format: 'jpeg',
    colour: 'srgb',
    template: '{roll}_{frame:02}_{stock}',
    dest: '~/Pictures/Film',
    subfolder: true,
  });

  const [hw, setHw] = useState(null);
  const [hwBusy, setHwBusy] = useState(false);
  const [scanJob, setScanJob] = useState(null);
  const [stopping, setStopping] = useState(false);
  const [calState, setCalState] = useState(null);
  const [autoOpen, setAutoOpen] = useState(null);
  // scan job ids whose capture this window has already tried to open, so a
  // poll that re-delivers a finished job cannot decode it twice.
  const opened = useRef(new Set());

  const selectTab = useCallback(
    (id) => {
      setActiveTab(id);
      setView('contact');
      setBoundsOpen(false);
      if (id === 'new' || id == null) {
        setRoll(null);
        return;
      }
      const r = rolls.find((x) => x.id === id);
      if (r) setRoll(r);
      else api.roll(id).then(setRoll);
    },
    [rolls],
  );

  useEffect(() => {
    (async () => {
      try {
        await api.initApi();
        const b = await api.bootstrap();
        setBoot(b);
        if (b.hardware?.scan_job) {
          setScanJob({ id: b.hardware.scan_job, kind: 'scan', status: 'running', phase: 'scanning' });
        }
        setHw(b.hardware || null);
        const rs = await api.rolls();
        setRolls(rs);
        if (b.hardware?.scan_job) {
          setActiveTab('new');
        } else if (rs.length) {
          setRoll(rs[0]);
          setActiveTab(rs[0].id);
        }
        setReady(true);
        // Leftovers a previous session should have cleared.
        const stale = b.workspace.rolls.filter((r) => !rs.some((x) => x.id === r.id));
        const staleCaps = b.workspace.captures || [];
        if (stale.length || staleCaps.length)
          setCleanup({ ...b.workspace, rolls: stale, captures: staleCaps });
      } catch (e) {
        setFatal(String(e.message || e));
      }
    })();
  }, []);

  /* The machine, polled. Fast while a scan runs; slowly otherwise. Also how a
     scan already in flight (started elsewhere, or before a relaunch) is
     adopted — the ephemeral 'new' tab picks it up on the next tab-strip
     render via `scanJob`, without this needing to touch `activeTab`. */
  const adopt = useCallback((h) => {
    setHw(h);
    if (h?.scan_job) {
      setScanJob((cur) =>
        cur && cur.id === h.scan_job && cur.status === 'running'
          ? cur
          : { id: h.scan_job, kind: 'scan', status: 'running', phase: 'scanning' });
    }
  }, []);

  useEffect(() => {
    if (!ready) return undefined;
    const scanning = scanJob?.status === 'running';
    let alive = true;
    let fails = 0;
    const t = setInterval(() => {
      api.hardware().then((h) => {
        if (!alive) return;
        fails = 0;
        adopt(h);
      }).catch((e) => {
        if (!alive || ++fails < 2) return;
        setHw((cur) => ({
          ...(cur || {}),
          present: false,
          state: 'unreachable',
          lamp: null,
          simulated: null,
          cached: true,
          hint: `The backend stopped answering the hardware probe: ${e.message || e}`,
        }));
      });
    }, scanning ? 4000 : 15000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [ready, scanJob?.status, adopt]);

  const recheckHw = useCallback(async () => {
    setHwBusy(true);
    api.calibration().then(setCalState).catch(() => {});
    try {
      adopt(await api.hardware(true));
    } catch (e) {
      setHw((cur) => ({ ...(cur || {}), present: false, state: 'unreachable', lamp: null, simulated: null, hint: String(e.message || e) }));
    } finally {
      setHwBusy(false);
    }
  }, [adopt]);

  /* The scan itself, polled hard. */
  useEffect(() => {
    if (scanJob?.status !== 'running') return undefined;
    const id = scanJob.id;
    let alive = true;
    let fails = 0;
    const t = setInterval(async () => {
      try {
        const j = await api.job(id);
        if (!alive) return;
        fails = 0;
        setScanJob(j);
        if (j.status !== 'running') {
          api.bootstrap().then((b) => { setBoot(b); setHw(b.hardware || null); }).catch(() => {});
        }
      } catch (e) {
        if (!alive || ++fails < 8) return;
        setScanJob((cur) =>
          cur && cur.id === id && cur.status === 'running'
            ? { ...cur, status: 'error', phase: 'lost', cancellable: false, openable: false,
                message: 'Lost contact with the scan',
                detail: `The backend stopped answering for this job: ${e.message || e}.` }
            : cur);
      }
    }, 500);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [scanJob?.status, scanJob?.id]);

  const startScan = useCallback(async (body) => {
    const r = await api.startScan(body);
    opened.current.delete(r.id);
    setScanJob({ id: r.id, status: 'running', kind: 'scan', phase: 'starting',
                 max_seconds: r.max_seconds, path: r.path,
                 open_with: { film_path: body.film_path, dx: body.dx, name: body.name } });
    setActiveTab('new');
    setRoll(null);
    return r;
  }, []);

  /* Scan → decode → contact sheet, with nobody picking a file. */
  useEffect(() => {
    if (!scanJob || scanJob.status === 'running') return;
    if (opened.current.has(scanJob.id)) return;
    opened.current.add(scanJob.id);
    if (!scanJob.openable || !scanJob.path) return;

    let alive = true;
    (async () => {
      const w = scanJob.open_with || {};
      setAutoOpen({ status: 'running', phase: 'opening', progress: 0, message: 'decoding the capture' });
      try {
        const { id } = await api.openCapture({
          path: scanJob.path,
          name: w.name || undefined,
          film_path: w.film_path || undefined,
          dx: w.dx || undefined,
        });
        const final = await api.pollJob(id, (j) => alive && setAutoOpen(j), 300);
        if (!alive) return;
        if (final.status === 'error') return setAutoOpen(final);
        const rs = await api.rolls();
        if (!alive) return;
        setRolls(rs);
        const newRoll = rs.find((r) => r.id === final.roll) || rs[0] || null;
        setRoll(newRoll);
        setSel(0);
        setAutoOpen(null);
        // The scan's own tab is gone now — the roll has a real one.
        setScanJob(null);
        setActiveTab(newRoll ? newRoll.id : null);
        setView('contact');
        api.bootstrap().then(setBoot).catch(() => {});
      } catch (e) {
        if (alive) setAutoOpen({ status: 'error', error: String(e.message || e) });
      }
    })();
    return () => { alive = false; };
  }, [scanJob]);

  const cancelScan = useCallback(async () => {
    if (!scanJob?.id) return;
    try {
      await api.cancelScan(scanJob.id);
    } catch { /* the panic button is the fallback */ }
  }, [scanJob?.id]);

  const stopScanner = useCallback(async () => {
    try {
      const r = await api.stopScanner();
      api.hardware().then(setHw).catch(() => {});
      return r;
    } catch (e) {
      return { error: `The backend did not answer the stop: ${e.message || e}` };
    }
  }, []);

  const dismissScan = useCallback(() => {
    setAutoOpen(null);
    setScanJob((cur) => (cur && cur.status === 'running' ? cur : null));
    setActiveTab((cur) => (cur === 'new' ? (rolls.length ? rolls[0].id : null) : cur));
  }, [rolls]);

  const openScanResult = useCallback(() => {
    if (!scanJob?.path) return;
    opened.current.delete(scanJob.id);
    setScanJob((cur) => (cur ? { ...cur, openable: true } : cur));
  }, [scanJob?.id, scanJob?.path]);

  useEffect(() => {
    setSel((s) => Math.min(s, Math.max(0, (roll?.frames?.length ?? 1) - 1)));
  }, [roll?.id, roll?.frames?.length]);

  const updateRoll = useCallback((r) => {
    setRoll(r);
    setRolls((rs) => rs.map((x) => (x.id === r.id ? r : x)));
  }, []);

  const closeTab = useCallback(async (id) => {
    try { await api.closeRoll(id); } catch { /* best effort */ }
    setRolls((rs) => {
      const remaining = rs.filter((r) => r.id !== id);
      if (activeTab === id) {
        const next = remaining.length ? remaining[0].id : (scanJob ? 'new' : null);
        selectTab(next);
      }
      return remaining;
    });
  }, [activeTab, scanJob, selectTab]);

  /* Runs the export from here so it survives being navigated away from —
     the modal can be closed mid-export and the job keeps going. `frames` is
     the modal's own selection, not derived from the roll. */
  const runExport = useCallback(
    async (frames, onExist) => {
      if (!roll) return;
      const cfg = exportCfg;
      const format = cfg.colour === 'linear' ? 'tiff' : cfg.format;
      const body = { roll: roll.id, frames, format, colour: cfg.colour, template: cfg.template, dest: cfg.dest, subfolder: cfg.subfolder };
      if (!onExist) {
        try {
          const plan = await api.planExport(body);
          if (plan.needs_confirm) return setCollision(plan);
        } catch (e) {
          console.error('export plan failed', e);
        }
      }
      setCollision(null);
      setExporting(true);
      setExportJob(null);
      try {
        const { id } = await api.exportRoll({ ...body, ...(onExist ? { on_exist: onExist } : {}) });
        const final = await api.pollJob(id, setExportJob, 350);
        setExportJob(final);
        if (final.needs_confirm && final.plan) setCollision(final.plan);
        updateRoll(await api.roll(roll.id));
      } catch (e) {
        setExportJob({ status: 'error', error: String(e.message || e) });
      } finally {
        setExporting(false);
      }
    },
    [roll, exportCfg, updateRoll],
  );

  const editBoundary = useCallback(async (body) => {
    if (!roll) return;
    setBoundsBusy(true);
    try {
      updateRoll(await api.boundary(roll.id, body));
    } finally {
      setBoundsBusy(false);
    }
  }, [roll, updateRoll]);

  const openedFromScan = scanJob != null;

  // Self-calibration: starts itself the moment `boot` names a scanner that
  // needs it — not gated behind any screen, so it fires whether or not
  // anyone ever looks at this window.
  const cal = useCalibrationSetup(boot);

  if (fatal)
    return (
      <div className="app" style={{ display: 'grid', placeItems: 'center' }}>
        <div style={{ maxWidth: '58ch' }}>
          <div className="title" style={{ color: 'var(--danger-ink)', marginBottom: 8 }}>Cannot reach the backend</div>
          <p className="num" style={{ fontSize: 12, color: 'var(--mute)' }}>{fatal}</p>
        </div>
      </div>
    );

  if (!ready)
    return (
      <div className="app" style={{ display: 'grid', placeItems: 'center' }}>
        <Spinner>Starting</Spinner>
      </div>
    );

  return (
    <div className="app">
      <TabStrip
        rolls={rolls}
        activeTab={activeTab}
        onSelect={selectTab}
        onClose={closeTab}
        scanning={openedFromScan}
        onNewScan={() => setScanModalOpen(true)}
      />
      <Toolbar
        roll={activeTab === 'new' ? null : roll}
        view={view}
        setView={setView}
        onExport={() => setExportModalOpen(true)}
        onFixFrames={() => setBoundsOpen((v) => !v)}
        dark={dark}
        setDark={setDark}
      />
      <CalibrationBanner boot={boot} setup={cal.setup} job={cal.job} retry={cal.retry} />

      <div className="body" style={{ gridTemplateColumns: '1fr' }}>
        {activeTab === 'new' && scanJob ? (
          <Scanning
            job={scanJob}
            busy={stopping}
            open={autoOpen}
            onOpenAnyway={openScanResult}
            onDismiss={dismissScan}
            onCancel={() => { setStopping(true); cancelScan(); }}
          />
        ) : roll ? (
          view === 'contact' ? (
            <ContactSheet roll={roll} onSelectFrame={(i) => { setSel(i); setView('editor'); }} />
          ) : (
            <FrameEditor roll={roll} setRoll={updateRoll} sel={sel} setSel={setSel} />
          )
        ) : (
          <Empty onScan={() => setScanModalOpen(true)} onOpen={() => setOpenDlgOpen(true)} />
        )}
      </div>

      {roll && boundsOpen ? (
        <Boundaries
          roll={roll}
          selected={sel}
          onSelect={setSel}
          onEdit={editBoundary}
          busy={boundsBusy}
          onClose={() => setBoundsOpen(false)}
        />
      ) : roll && view === 'editor' ? (
        <FilmBand roll={roll} selected={sel} onSelect={setSel} />
      ) : null}

      <ScanModal
        open={scanModalOpen}
        onClose={() => setScanModalOpen(false)}
        hw={hw}
        hwBusy={hwBusy}
        scanJob={scanJob}
        onRecheckHw={recheckHw}
        onStart={startScan}
      />

      <ExportModal
        open={exportModalOpen}
        onClose={() => setExportModalOpen(false)}
        roll={roll}
        cfg={exportCfg}
        setCfg={setExportCfg}
        job={exportJob}
        running={exporting}
        collision={collision}
        onRun={runExport}
        onCancelCollision={() => setCollision(null)}
      />

      <OpenDialog
        open={openDlgOpen}
        onClose={() => setOpenDlgOpen(false)}
        captures={boot?.captures}
        onOpened={async (id) => {
          const rs = await api.rolls();
          setRolls(rs);
          const opened_ = rs.find((r) => r.id === id) || rs[0] || null;
          setRoll(opened_);
          setSel(0);
          setActiveTab(opened_ ? opened_.id : null);
          setView('contact');
          api.bootstrap().then(setBoot).catch(() => {});
        }}
      />

      {cleanup ? (
        <CleanupDialog
          state={cleanup}
          onDone={() => {
            setCleanup(null);
            api.bootstrap().then(setBoot).catch(() => {});
          }}
        />
      ) : null}
    </div>
  );
}
