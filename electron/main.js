'use strict';

/**
 * main.js — PrivacyShield Desktop (Electron)
 * Fixes:
 *  - Real logo shown in splash (logo_v7_final → icon.png)
 *  - Backend startup timeout increased to 4 minutes (torch loads slowly)
 *  - Status messages show step-by-step progress
 *  - Desktop/taskbar icon uses icon.ico (logo_v7)
 *  - X button → minimize to system tray (NOT quit)
 */

/**
 * ── PORT STRATEGY (remember when building EXE updates) ──────────────────────
 *
 * Dev mode  : Vite frontend → http://localhost:5173
 *             Backend       → http://127.0.0.1:<findFreePort from 8000>
 *             BACKEND_PORT env is set in child process env, NOT window.env.
 *
 * EXE / Prod: findFreePort() picks a free port at runtime (may NOT be 8000).
 *             Frontend is served BY the backend on that same port.
 *             mainWindow loads  → http://127.0.0.1:<backendPort>
 *             BACKEND_PORT env  → passed to backend.exe via spawn() args & env.
 *             notify.py reads   → os.environ["BACKEND_PORT"] to build alert URLs.
 *
 * When building a new EXE:
 *  - Do NOT hardcode 8000 anywhere in Python or JS code.
 *  - notify.py uses sys.frozen + BACKEND_PORT env to resolve frontend URL.
 *  - api/index.js reads port via electronAPI.getBackendPortSync() (IPC).
 * ─────────────────────────────────────────────────────────────────────────────
 */

const {
  app, BrowserWindow, ipcMain, dialog, shell,
  Menu, Tray, nativeImage, desktopCapturer
} = require('electron');
const path      = require('path');
const net       = require('net');
const fs        = require('fs');
const { spawn, execFile } = require('child_process');

// ── Dev / Prod ────────────────────────────────────────────────────────────────
const IS_DEV = !app.isPackaged;

// ── Resource paths ────────────────────────────────────────────────────────────
const RESOURCES   = IS_DEV ? path.join(__dirname, '..') : process.resourcesPath;
const BACKEND_DIR = IS_DEV ? null : path.join(RESOURCES, 'backend');
const BACKEND_EXE = BACKEND_DIR ? path.join(BACKEND_DIR, 'backend.exe') : null;
const UPDATER_EXE = path.join(RESOURCES, 'updater.exe');
const VERSION_FILE= path.join(RESOURCES, 'version.json');

const ICON_ICO = IS_DEV
  ? path.join(__dirname, 'assets', 'icon.ico')
  : path.join(RESOURCES, 'icon.ico');

const ICON_PNG = IS_DEV
  ? path.join(__dirname, 'assets', 'icon.png')
  : path.join(__dirname, 'assets', 'icon.png');   // bundled in asar

const TRAY_PNG = IS_DEV
  ? path.join(__dirname, 'assets', 'tray16.png')
  : path.join(RESOURCES, 'tray16.png');

const PYTHON_EXE = IS_DEV
  ? path.join(__dirname, '..', 'tf_env', 'Scripts', 'python.exe')
  : null;

const USER_DATA = app.getPath('userData');

// ── State ─────────────────────────────────────────────────────────────────────
let mainWindow  = null;
let tray        = null;
let backendProc = null;
let backendPort = 8000;
let splashWin   = null;
let isQuitting  = false;

// ── Helpers ───────────────────────────────────────────────────────────────────
function findFreePort(start = 8000) {
  return new Promise((resolve) => {
    const srv = net.createServer();
    srv.listen(start, '127.0.0.1', () => {
      const port = srv.address().port;
      srv.close(() => resolve(port));
    });
    srv.on('error', () => resolve(findFreePort(start + 1)));
  });
}

// Increased retries to 240 × 1s = 4 minutes (torch/transformers need time)
function waitForPort(port, retries = 240, delayMs = 1000) {
  return new Promise((resolve, reject) => {
    const attempt = (n) => {
      if (n <= 0) { reject(new Error('Backend did not start in time.')); return; }
      const sock = net.createConnection({ host: '127.0.0.1', port }, () => {
        sock.destroy(); resolve();
      });
      sock.on('error',   () => setTimeout(() => attempt(n - 1), delayMs));
      sock.setTimeout(900, () => { sock.destroy(); setTimeout(() => attempt(n - 1), 100); });
    };
    attempt(retries);
  });
}

function killBackend() {
  if (backendProc && !backendProc.killed) {
    try { backendProc.kill('SIGTERM'); } catch (_) {}
    backendProc = null;
  }
}

// ── Start backend ─────────────────────────────────────────────────────────────
function startBackend(port) {
  ['uploads', 'reports', 'screenshots'].forEach(d =>
    fs.mkdirSync(path.join(USER_DATA, d), { recursive: true })
  );

  const env = {
    ...process.env,
    PRIVACY_DATA_DIR:    USER_DATA,
    BACKEND_PORT:        String(port),
    ELECTRON_RESOURCES:  IS_DEV
      ? path.join(__dirname, '..', 'frontend', 'dist')
      : process.resourcesPath,
  };

  if (IS_DEV) {
    backendProc = spawn(PYTHON_EXE, [
      '-m', 'uvicorn', 'backend.main:app',
      '--host', '127.0.0.1',
      '--port', String(port),
      '--no-access-log',
    ], { cwd: path.join(__dirname, '..'), env, windowsHide: true });
  } else {
    backendProc = spawn(BACKEND_EXE, [
      '--host', '127.0.0.1',
      '--port', String(port),
    ], { cwd: BACKEND_DIR, env, windowsHide: true });
  }

  backendProc.stdout?.on('data', d => console.log('[BE]', d.toString().trim()));
  backendProc.stderr?.on('data', d => console.error('[BE]', d.toString().trim()));
  backendProc.on('exit', code => console.warn(`[BE] exited: ${code}`));
}

// ── Splash ────────────────────────────────────────────────────────────────────
function createSplash() {
  splashWin = new BrowserWindow({
    width: 500, height: 320,
    frame: false, transparent: true,
    alwaysOnTop: true, skipTaskbar: true,
    icon: ICON_ICO,
    webPreferences: { nodeIntegration: false },
  });

  // Encode logo as base64 for inline use in the splash HTML
  let logoBase64 = '';
  try {
    const logoPath = path.join(__dirname, 'assets', 'icon.png');
    logoBase64 = fs.readFileSync(logoPath).toString('base64');
  } catch (_) {}

  const logoImg = logoBase64
    ? `<img src="data:image/png;base64,${logoBase64}" style="width:72px;height:72px;border-radius:16px;margin-bottom:14px;box-shadow:0 0 24px rgba(59,130,246,0.5)" />`
    : `<div style="font-size:52px;margin-bottom:14px">🛡️</div>`;

  const html = `<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
    *{margin:0;padding:0;box-sizing:border-box}
    body{
      background:linear-gradient(135deg,#0a0a0f 0%,#111118 60%,#0e0e16 100%);
      border-radius:18px;border:1px solid rgba(59,130,246,0.25);
      display:flex;flex-direction:column;align-items:center;justify-content:center;
      height:100vh;font-family:'Segoe UI',sans-serif;color:#e2e8f0;
      overflow:hidden;
    }
    h1{font-size:26px;font-weight:700;color:#f0f0f2;margin-bottom:4px;letter-spacing:-0.5px}
    .sub{font-size:12px;color:#4b4b68;margin-bottom:28px;letter-spacing:0.05em;text-transform:uppercase}
    .bar-wrap{width:340px;height:3px;background:#1a1a24;border-radius:4px;overflow:hidden;margin-bottom:14px}
    .bar{height:100%;width:0%;background:linear-gradient(90deg,#3b82f6,#8b5cf6,#06b6d4);
      border-radius:4px;animation:load 8s cubic-bezier(0.4,0,0.2,1) forwards}
    @keyframes load{0%{width:0%} 30%{width:35%} 60%{width:60%} 85%{width:80%} 100%{width:92%}}
    .status{font-size:11.5px;color:#3b82f6;letter-spacing:0.02em;transition:opacity 0.3s}
    .step{margin-top:6px;font-size:10px;color:#2a2a40}
  </style></head><body>
    ${logoImg}
    <h1>PrivacyShield</h1>
    <div class="sub">Privacy Exposure Analysis Platform</div>
    <div class="bar-wrap"><div class="bar"></div></div>
    <div class="status" id="st">Initializing...</div>
    <div class="step" id="step"></div>
  </body></html>`;

  splashWin.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
}

function updateSplash(msg, step = '') {
  if (!splashWin || splashWin.isDestroyed()) return;
  splashWin.webContents
    .executeJavaScript(`
      document.getElementById('st').textContent=${JSON.stringify(msg)};
      document.getElementById('step').textContent=${JSON.stringify(step)};
    `)
    .catch(() => {});
}

// ── System Tray ───────────────────────────────────────────────────────────────
function createTray() {
  let icon;
  try {
    icon = nativeImage.createFromPath(TRAY_PNG);
    if (icon.isEmpty()) throw new Error('empty');
  } catch (_) {
    icon = nativeImage.createFromDataURL(
      'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAIklEQVQ4T2NkYGD4z8BAAIxCoAIYBaMGjBowasCgMwAABiQAAX9V4UoAAAAASUVORK5CYII='
    );
  }

  tray = new Tray(icon);
  tray.setToolTip('PrivacyShield — Privacy Exposure Tool');

  const buildMenu = () => Menu.buildFromTemplate([
    {
      label: 'Open PrivacyShield',
      click: () => { if (mainWindow) { mainWindow.show(); mainWindow.focus(); } }
    },
    { type: 'separator' },
    { label: 'Check for Updates', click: () => launchUpdater() },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => { isQuitting = true; killBackend(); app.quit(); }
    },
  ]);

  tray.setContextMenu(buildMenu());
  tray.on('click', () => {
    if (!mainWindow) return;
    if (mainWindow.isVisible()) { mainWindow.hide(); }
    else { mainWindow.show(); mainWindow.focus(); }
  });
}

// ── Main window ───────────────────────────────────────────────────────────────
function createMainWindow(port) {
  mainWindow = new BrowserWindow({
    width: 1340, height: 840,
    minWidth: 960, minHeight: 640,
    show: false,
    icon: ICON_ICO,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    backgroundColor: '#0e0e10',
    title: 'PrivacyShield',
  });

  const url = IS_DEV
    ? 'http://localhost:5173'
    : `http://127.0.0.1:${port}`;

  mainWindow.loadURL(url);

  if (IS_DEV) mainWindow.webContents.openDevTools({ mode: 'undocked' });

  mainWindow.once('ready-to-show', () => {
    if (splashWin && !splashWin.isDestroyed()) splashWin.close();
    mainWindow.show();
    mainWindow.focus();
  });

  mainWindow.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault();
      mainWindow.hide();
      if (!createMainWindow._trayNotified) {
        createMainWindow._trayNotified = true;
        tray && tray.displayBalloon({
          iconType: 'info',
          title: 'PrivacyShield is still running',
          content: 'Right-click the tray icon to Quit.',
        });
      }
    }
  });

  mainWindow.on('closed', () => { mainWindow = null; });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http')) shell.openExternal(url);
    return { action: 'deny' };
  });
}

// ── Updater ───────────────────────────────────────────────────────────────────
function launchUpdater() {
  if (!fs.existsSync(UPDATER_EXE)) {
    dialog.showMessageBox(mainWindow, {
      type: 'info', title: 'Update Check',
      message: IS_DEV
        ? 'Updater not available in development mode.'
        : 'Updater not found.',
    });
    return;
  }
  execFile(UPDATER_EXE, (err) => {
    if (err) dialog.showErrorBox('Updater Error', String(err));
  });
}

// ── IPC ───────────────────────────────────────────────────────────────────────
ipcMain.handle('get-backend-port',  () => backendPort);
ipcMain.on('get-backend-port-sync', (event) => {
  event.returnValue = backendPort;
});
ipcMain.handle('get-sources', async () => {
  const [windows, screens] = await Promise.all([
    desktopCapturer.getSources({
      types: ['window'],
      thumbnailSize: { width: 320, height: 180 },
      fetchWindowIcons: true,
    }),
    desktopCapturer.getSources({
      types: ['screen'],
      thumbnailSize: { width: 320, height: 180 },
    }),
  ]);

  const BROWSER_KEYWORDS = ['chrome', 'edge', 'firefox', 'brave', 'opera', 'vivaldi', 'chromium'];

  const classify = (name) => {
    const lower = (name || '').toLowerCase();
    if (BROWSER_KEYWORDS.some(k => lower.includes(k))) return 'browser';
    return 'window';
  };

  const mapSource = (source, type) => ({
    id: source.id,
    name: source.name,
    type: type,
    thumbnail: source.thumbnail?.toDataURL() || null,
    appIcon: source.appIcon?.toDataURL() || null,
  });

  return [
    ...screens.map(s => mapSource(s, 'screen')),
    ...windows
      .filter(w => w.name && w.name.trim().length > 0)
      .map(w => mapSource(w, classify(w.name))),
  ];
});
ipcMain.handle('get-version', () => {
  try { return JSON.parse(fs.readFileSync(VERSION_FILE, 'utf-8')).version; }
  catch { return '1.1.0'; }
});
ipcMain.handle('check-for-updates', () => launchUpdater());

// ── App lifecycle ─────────────────────────────────────────────────────────────
app.whenReady().then(async () => {
  Menu.setApplicationMenu(null);
  createSplash();

  try {
    // Step 1 — find port
    updateSplash('Finding available port...', 'Step 1/4 — Network setup');
    backendPort = await findFreePort(8000);

    // Step 2 — launch backend
    updateSplash(`Starting backend services...`, 'Step 2/4 — Loading AI models & backend');
    startBackend(backendPort);

    // Step 3 — wait for backend (up to 4 minutes for torch/spaCy)
    updateSplash(`Loading backend on port ${backendPort}...`, 'Step 3/4 — AI models loading (may take 1-2 min on first run)');
    
    // Update status message every 15s to reassure user it's still working
    const statusTimer = setInterval(() => {
      const msgs = [
        'Loading AI detection models...',
        'Initializing spaCy NLP engine...',
        'Loading PyTorch/BART classifier...',
        'Setting up database...',
        'Starting FastAPI server...',
        'Almost ready...',
      ];
      const idx = Math.floor(Date.now() / 15000) % msgs.length;
      updateSplash(msgs[idx], 'Step 3/4 — Please wait, first launch takes longer');
    }, 15000);

    await waitForPort(backendPort, 240, 1000);
    clearInterval(statusTimer);

    // Step 4 — load UI
    updateSplash('Loading interface...', 'Step 4/4 — Starting frontend');
    createTray();
    createMainWindow(backendPort);

  } catch (err) {
    if (splashWin && !splashWin.isDestroyed()) splashWin.close();
    dialog.showErrorBox(
      'PrivacyShield — Startup Error',
      `Failed to start backend:\n\n${err.message}\n\nPlease restart the application.`
    );
    app.quit();
  }
});

app.on('window-all-closed', (e) => {
  if (!isQuitting) return;
  killBackend();
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  isQuitting = true;
  killBackend();
});

app.on('activate', () => {
  if (mainWindow) { mainWindow.show(); mainWindow.focus(); }
});
