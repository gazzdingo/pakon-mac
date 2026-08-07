// Electron main process. Spawns the Python backend as a sidecar and loads the UI.
// The backend owns decode / session orchestration; the shell is presentation only.
const { app, BrowserWindow, dialog } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

const PORT = 8135;
let backend = null;
let win = null;
let spawnedBackend = false;

function repoRoot() {
  // packaged: resources/ ; dev: ../ (repo root)
  return app.isPackaged ? path.join(process.resourcesPath) : path.join(__dirname, '..');
}

function startBackend() {
  const script = path.join(repoRoot(), 'tools', 'pakon_ui.py');
  const py = process.platform === 'win32' ? 'python' : 'python3';
  backend = spawn(py, ['-u', script], {
    cwd: repoRoot(),
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
  });
  spawnedBackend = true;
  backend.stdout.on('data', d => console.log('[backend]', d.toString().trim()));
  backend.stderr.on('data', d => console.error('[backend]', d.toString().trim()));
  backend.on('exit', code => {
    if (code) console.error('backend exited', code);
  });
}

function waitForBackend(tries = 60) {
  return new Promise((resolve, reject) => {
    const probe = () => {
      http.get({ host: '127.0.0.1', port: PORT, path: '/api/status', timeout: 500 }, res => {
        res.resume();
        resolve();
      }).on('error', () => {
        if (--tries <= 0) return reject(new Error('backend did not start'));
        setTimeout(probe, 250);
      });
    };
    probe();
  });
}

function backendAlive() {
  return new Promise(resolve => {
    http.get({ host: '127.0.0.1', port: PORT, path: '/api/status', timeout: 400 }, res => {
      res.resume();
      resolve(true);
    }).on('error', () => resolve(false));
  });
}

async function createWindow() {
  win = new BrowserWindow({
    width: 1380,
    height: 900,
    minWidth: 1040,
    minHeight: 680,
    title: 'Pakon Scan',
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    backgroundColor: '#12141a',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
    },
  });
  try {
    await waitForBackend();
    win.loadURL(`http://127.0.0.1:${PORT}/`);
  } catch (e) {
    dialog.showErrorBox(
      'Backend failed to start',
      'Could not start the Python backend.\n\n'
        + 'Need Python 3 with numpy (and pyusb for live USB status).\n\n'
        + e.message,
    );
    app.quit();
  }
}

app.whenReady().then(async () => {
  if (await backendAlive()) {
    console.log('reusing backend already listening on', PORT);
  } else {
    startBackend();
  }
  createWindow();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
app.on('before-quit', () => {
  if (spawnedBackend && backend) backend.kill();
});
