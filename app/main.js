// Electron main process. Spawns the Python backend as a sidecar and loads the UI.
// The backend owns decode and (later) hardware; the shell is presentation only.
const { app, BrowserWindow, dialog } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

const PORT = 8135;
let backend = null;
let win = null;

function repoRoot() {
  // packaged: resources/tools ; dev: ../tools
  return app.isPackaged ? path.join(process.resourcesPath) : path.join(__dirname, '..');
}

function startBackend() {
  const script = path.join(repoRoot(), 'tools', 'pakon_ui.py');
  const py = process.platform === 'win32' ? 'python' : 'python3';
  backend = spawn(py, [script], { cwd: repoRoot(), stdio: ['ignore', 'pipe', 'pipe'] });
  backend.stderr.on('data', d => console.error('[backend]', d.toString().trim()));
  backend.on('exit', code => { if (code) console.error('backend exited', code); });
}

function waitForBackend(tries = 40) {
  return new Promise((resolve, reject) => {
    const probe = () => {
      http.get({ host: '127.0.0.1', port: PORT, path: '/files', timeout: 500 }, res => {
        res.resume(); resolve();
      }).on('error', () => {
        if (--tries <= 0) return reject(new Error('backend did not start'));
        setTimeout(probe, 250);
      });
    };
    probe();
  });
}

async function createWindow() {
  win = new BrowserWindow({
    width: 1280, height: 820, minWidth: 1000, minHeight: 640,
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    backgroundColor: '#14161a',
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true }
  });
  try {
    await waitForBackend();
    win.loadURL(`http://127.0.0.1:${PORT}/`);
  } catch (e) {
    dialog.showErrorBox('Backend failed to start',
      'Could not start the Python backend.\n\nPython 3 with numpy is required.\n\n' + e.message);
    app.quit();
  }
}

// Reuse a backend that is already listening (e.g. started by hand for dev)
// instead of spawning a second one and failing on EADDRINUSE.
function backendAlive() {
  return new Promise(resolve => {
    http.get({ host: '127.0.0.1', port: PORT, path: '/files', timeout: 400 }, res => {
      res.resume(); resolve(true);
    }).on('error', () => resolve(false));
  });
}

app.whenReady().then(async () => {
  if (await backendAlive()) {
    console.log('reusing backend already listening on', PORT);
  } else {
    startBackend();
  }
  createWindow();
});
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
app.on('before-quit', () => { if (backend) backend.kill(); });
