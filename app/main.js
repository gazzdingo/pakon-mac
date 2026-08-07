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
const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const net = require('net');

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
  const py = process.env.PAKON_PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  backend = spawn(py, ['-u', script, '--port', String(port)], {
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
  const r = await dialog.showOpenDialog(win, {
    title: 'Open capture',
    defaultPath: path.join(repoRoot(), 'captures'),
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
  win = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1120,
    minHeight: 720,
    title: 'Pakon Scan',
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
      if (spawnedBackend && backend) backend.kill();
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

  // Two different questions. Only ask the creative-work one when there is
  // creative work to lose.
  if (unexported > 0) {
    const { response } = await dialog.showMessageBox(win, {
      type: 'warning',
      buttons: ['Quit and delete workspace', 'Quit, keep workspace this once', 'Cancel'],
      defaultId: 2,
      cancelId: 2,
      message: `${session.adjusted_frames} frame${
        session.adjusted_frames === 1 ? '' : 's'
      } adjusted, ${session.exported_frames} exported`,
      detail:
        `Quitting clears the workspace: the raw captures (${mb(
          session.workspace_bytes,
        )}) are deleted.\n\n` +
        `Your adjustments (${mb(
          session.sidecar_bytes,
        )}) are kept and re-apply if you reopen the same capture — but the ` +
        `rendered frames themselves only exist after export.`,
    });
    return ['delete', 'keep', 'cancel'][response];
  }

  if ((session.workspace_bytes || 0) > 50e6) {
    const { response } = await dialog.showMessageBox(win, {
      type: 'question',
      buttons: ['Delete workspace and quit', 'Keep workspace', 'Cancel'],
      defaultId: 0,
      cancelId: 2,
      message: `Delete ${mb(session.workspace_bytes)} of temporary scan data?`,
      detail:
        'The workspace holds raw captures and the render cache. It is ' +
        'regenerable from the capture files and is normally cleared on quit.',
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
  if (spawnedBackend && backend) backend.kill();
  app.quit();
});

app.whenReady().then(async () => {
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
