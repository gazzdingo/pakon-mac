// Electron main process for Pakon Scan.
//
// Owns: the window, native dialogs, the Python backend lifecycle, and the
// storage contract at quit time. The backend (tools/pakon_app.py) owns decode
// and rendering; the renderer is presentation only and never sees a full-res
// buffer — it asks the backend for a JPEG of a frame at a named scale.
//
// The quit path implements design/housekeeping.html state B: unexported
// creative work and "delete 700 MB of temp data" are different questions and
// are asked as different questions.
const { app, BrowserWindow, dialog, ipcMain, shell, Menu } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const net = require('net');

app.setName('Pakon Mac');
if (process.platform === 'darwin' && !app.isPackaged) {
  app.dock.setIcon(path.join(__dirname, 'src', 'icons', 'icon_512x512.png'));
}
let backend = null;
let win = null;
let backendPort = 0;
let spawnedBackend = false;
let quitConfirmed = false;

function repoRoot() {
  return app.isPackaged ? process.resourcesPath : path.join(__dirname, '..');
}

function freePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.on('error', reject);
    srv.listen(0, '127.0.0.1', () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

function api(pathname, { method = 'GET', body = null, timeout = 15000 } = {}) {
  return new Promise((resolve, reject) => {
    const payload = body ? Buffer.from(JSON.stringify(body)) : null;
    const req = http.request(
      {
        host: '127.0.0.1',
        port: backendPort,
        path: pathname,
        method,
        timeout,
        headers: payload
          ? { 'Content-Type': 'application/json', 'Content-Length': payload.length }
          : {},
      },
      (res) => {
        const chunks = [];
        res.on('data', (c) => chunks.push(c));
        res.on('end', () => {
          const text = Buffer.concat(chunks).toString();
          try {
            resolve(JSON.parse(text || '{}'));
          } catch {
            resolve({ raw: text });
          }
        });
      },
    );
    req.on('error', reject);
    req.on('timeout', () => req.destroy(new Error('backend timeout')));
    if (payload) req.write(payload);
    req.end();
  });
}

function startBackend(port) {
  const script = path.join(repoRoot(), 'tools', 'pakon_app.py');
  const py = process.env.PAKON_PYTHON || 'python';
  // --watch-parent: the backend exits when this process does, however this
  // process ends. Belt to the braces below — those handlers cannot run if we
  // are SIGKILLed, and a backend that outlives its window keeps its scan child
  // alive with it, still driving the transport.
  backend = spawn(py, ['-u', script, '--port', String(port), '--watch-parent'], {
    cwd: repoRoot(),
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
  });
  spawnedBackend = true;
  backend.stdout.on('data', (d) => process.stdout.write(`[backend] ${d}`));
  backend.stderr.on('data', (d) => process.stderr.write(`[backend] ${d}`));
  backend.on('exit', (code) => {
    backend = null;
    if (code && !quitConfirmed) console.error('backend exited', code);
  });
}

/** Stop the backend, from anywhere, more than once, safely.
 *
 * SIGTERM first, because the backend's own handler closes the scan child's
 * control pipe and that is what stops the transport. SIGKILL only if it is
 * still there, and never as the first move: a killed backend cannot stop
 * anything.
 */
function killBackend() {
  if (!spawnedBackend || !backend) return;
  const proc = backend;
  try {
    proc.kill('SIGTERM');
  } catch {
    /* already gone */
  }
  setTimeout(() => {
    try {
      if (!proc.killed && proc.exitCode === null) proc.kill('SIGKILL');
    } catch {
      /* already gone */
    }
  }, 2500).unref?.();
}

function waitForBackend(tries = 120) {
  return new Promise((resolve, reject) => {
    const probe = () => {
      http
        .get(
          { host: '127.0.0.1', port: backendPort, path: '/api/app/health', timeout: 800 },
          (res) => {
            res.resume();
            resolve();
          },
        )
        .on('error', () => {
          if (--tries <= 0) return reject(new Error('backend did not start'));
          setTimeout(probe, 250);
        });
    };
    probe();
  });
}

// ------------------------------------------------------------------ IPC

ipcMain.handle('backend-port', () => backendPort);

ipcMain.handle('open-capture', async () => {
  // Ask the backend where captures live rather than assuming
  // `repoRoot()/captures` — when packaged that is inside the .app bundle,
  // which is exactly where captures must never be.
  let defaultPath = null;
  try {
    const p = await api('/api/app/paths', { timeout: 3000 });
    defaultPath = p.captures || p.legacy_captures || null;
  } catch {
    /* fall through to the OS default rather than pointing into the bundle */
  }
  const r = await dialog.showOpenDialog(win, {
    title: 'Open capture',
    ...(defaultPath ? { defaultPath } : {}),
    filters: [
      { name: 'Pakon capture', extensions: ['bin'] },
      { name: 'All files', extensions: ['*'] },
    ],
    properties: ['openFile'],
  });
  return r.canceled || !r.filePaths.length ? null : r.filePaths[0];
});

ipcMain.handle('choose-folder', async (_e, current) => {
  const r = await dialog.showOpenDialog(win, {
    title: 'Export destination',
    defaultPath: current || app.getPath('pictures'),
    properties: ['openDirectory', 'createDirectory'],
  });
  return r.canceled || !r.filePaths.length ? null : r.filePaths[0];
});

ipcMain.handle('reveal', async (_e, p) => {
  if (p) shell.showItemInFolder(p);
});

ipcMain.handle('open-path', async (_e, p) => {
  if (p) await shell.openPath(p);
});

// ---------------------------------------------------------------- window

async function createWindow() {
  const template = [
    ...(process.platform === 'darwin' ? [{
      label: app.name,
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' }
      ]
    }] : []),
    {
      label: 'File',
      submenu: [
        {
          label: 'New Scan',
          accelerator: 'CmdOrCtrl+N',
          click: () => { if (win) win.webContents.send('menu-new-scan'); }
        },
        {
          label: 'Import .bin...',
          accelerator: 'CmdOrCtrl+O',
          click: () => { if (win) win.webContents.send('menu-import-bin'); }
        },
        { type: 'separator' },
        process.platform === 'darwin' ? { role: 'close' } : { role: 'quit' }
      ]
    },
    { role: 'editMenu' },
    { role: 'viewMenu' },
    { role: 'windowMenu' }
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));

  win = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1120,
    minHeight: 720,
    title: 'Pakon Mac',
    icon: path.join(repoRoot(), 'app', 'src', 'icons', 'icon_512x512.png'),
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    backgroundColor: '#0B0B0B',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.once('ready-to-show', () => win.show());

  // Renderer console goes to the terminal — otherwise a broken screen is
  // silent unless someone opens devtools.
  win.webContents.on('console-message', (_e, level, message, line, source) => {
    if (level >= 2) console.error(`[renderer] ${message} (${source}:${line})`);
  });

  const devUrl = process.env.PAKON_DEV_SERVER;
  if (devUrl) await win.loadURL(devUrl);
  else await win.loadFile(path.join(__dirname, 'dist', 'index.html'));

  // PAKON_SHOT=/path/to.png writes a page capture and exits. Captures the
  // page, not the screen, so it works headless and without screen-recording
  // permission.
  if (process.env.PAKON_SHOT) {
    const wait = Number(process.env.PAKON_SHOT_DELAY || 3500);
    setTimeout(async () => {
      try {
        const img = await win.webContents.capturePage();
        require('fs').writeFileSync(process.env.PAKON_SHOT, img.toPNG());
        console.log('captured', process.env.PAKON_SHOT);
      } catch (e) {
        console.error('capture failed', e);
      }
      quitConfirmed = true;
      killBackend();
      app.exit(0);
    }, wait);
  }
}

// ------------------------------------------------------------ quit contract

async function confirmQuit() {
  let session = null;
  try {
    session = await api('/api/app/session', { timeout: 4000 });
  } catch {
    return 'delete';
  }
  const mb = (n) => `${((n || 0) / 1e6).toFixed(1)} MB`;
  const unexported = (session.adjusted_frames || 0) - (session.exported_frames || 0);

  /* This dialog used to get both halves of its own sentence wrong. It said
     "the raw captures (X MB) are deleted", where X was dir_size(WORKSPACE) --
     a directory that holds rgb14.npy and roll.json and no captures at all --
     and the captures were not deleted either, because purge() only ever
     walked the workspace. So the figure described the wrong thing and the
     claim was false about the right one.
     Both are true now. The backend measures the render cache and the raw
     captures separately, purge(all) removes both, and this names them
     separately because they are not equally replaceable: the render cache is
     rebuilt on demand, and a capture is film that has already gone past the
     sensor once. */
  const caps = session.capture_bytes || 0;
  const ws = session.workspace_bytes || 0;
  const total = session.temp_bytes ?? ws + caps;
  const nCaps = session.captures || 0;
  const what =
    `${mb(total)} of temporary data is deleted:\n\n` +
    `  • ${nCaps} raw capture${nCaps === 1 ? '' : 's'} (${mb(caps)}). A scan is not ` +
    `repeatable — the film passes the sensor once — so these cannot be remade ` +
    `without running the roll through again.\n` +
    `  • the render cache (${mb(ws)}), which is rebuilt from a capture on demand.`;

  // Two different questions. Only ask the creative-work one when there is
  // creative work to lose.
  if (unexported > 0) {
    const { response } = await dialog.showMessageBox(win, {
      type: 'warning',
      buttons: ['Quit and delete', 'Quit, keep this once', 'Cancel'],
      defaultId: 2,
      cancelId: 2,
      message: `${session.adjusted_frames} frame${
        session.adjusted_frames === 1 ? '' : 's'
      } adjusted, ${session.exported_frames} exported`,
      detail:
        `${what}\n\n` +
        `Your adjustments (${mb(
          session.sidecar_bytes,
        )}) are kept and re-apply if you reopen the same capture — but they are ` +
        `adjustments to a capture, so deleting the captures leaves nothing for them ` +
        `to re-apply to. The rendered frames themselves only exist after export.`,
    });
    return ['delete', 'keep', 'cancel'][response];
  }

  if (total > 50e6) {
    const { response } = await dialog.showMessageBox(win, {
      type: 'question',
      // Deleting is not the safe default when there are captures to lose.
      buttons: ['Delete and quit', 'Quit, keep this once', 'Cancel'],
      defaultId: nCaps ? 1 : 0,
      cancelId: 2,
      message: `Delete ${mb(total)} of temporary scan data?`,
      detail: what,
    });
    return ['delete', 'keep', 'cancel'][response];
  }
  return 'delete';
}

app.on('before-quit', async (e) => {
  if (quitConfirmed || !backendPort) return;
  e.preventDefault();
  let choice = 'keep';
  try {
    choice = await confirmQuit();
  } catch {
    choice = 'keep';
  }
  if (choice === 'cancel') return;
  if (choice === 'delete') {
    try {
      await api('/api/app/workspace/purge', { method: 'POST', body: { all: true } });
    } catch {
      /* a failed cleanup must never block quitting */
    }
  }
  quitConfirmed = true;
  killBackend();
  app.quit();
});

/* ── the backend must not outlive this process ──────────────────────────────
 *
 * `before-quit` covers the polite path only, and it is the path that was
 * already covered. Everything below is the impolite ones — a renderer crash
 * taking the app down, an uncaught throw in the main process, the user
 * force-quitting, a terminal Ctrl-C in development. Each of them used to leave
 * a Python backend running, and if a scan was in flight that backend's child
 * kept driving film with nothing on screen to stop it.
 *
 * These handlers cannot cover SIGKILL — nothing can. That is what the
 * backend's own `--watch-parent` is for, and it is why the backend and the app
 * now both refuse to open the scanner while `~/.pakon-scan-in-flight.json`
 * names a live owner. */
app.on('will-quit', killBackend);
app.on('quit', killBackend);
process.on('exit', killBackend);
for (const sig of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
  process.on(sig, () => {
    quitConfirmed = true;
    killBackend();
    app.exit(0);
  });
}
process.on('uncaughtException', (err) => {
  console.error('main process threw', err);
  quitConfirmed = true;
  killBackend();
  app.exit(1);
});

/* One window, one backend. Without this, launching the app again while it is
 * already running gives a second backend whose supervisor believes it is idle
 * — the exact case the in-flight marker now refuses.
 *
 * The lock is taken before anything is started, and a loser exits without
 * spawning a backend at all, so there is no window in which two exist. */
const primary = app.requestSingleInstanceLock();
if (!primary) {
  app.exit(0);
}

app.on('second-instance', () => {
  if (!win) return;
  if (win.isMinimized()) win.restore();
  win.focus();
});

if (primary) app.whenReady().then(async () => {
  // PAKON_BACKEND_PORT attaches to a backend that is already running, which
  // keeps opened rolls alive across UI restarts while developing.
  if (process.env.PAKON_BACKEND_PORT) {
    backendPort = Number(process.env.PAKON_BACKEND_PORT);
  } else {
    backendPort = await freePort();
    startBackend(backendPort);
  }
  try {
    await waitForBackend();
  } catch (err) {
    dialog.showErrorBox(
      'Backend failed to start',
      `Could not start the Python backend (tools/pakon_app.py).\n\n` +
        `Needs Python 3 with numpy and Pillow.\n\n${err.message}`,
    );
    app.exit(1);
    return;
  }
  createWindow();
});

app.on('window-all-closed', () => app.quit());
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
