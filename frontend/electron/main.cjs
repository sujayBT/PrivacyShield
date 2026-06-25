// Electron Main Process — PrivacyShield Desktop App
// Phase 15: Wraps the React frontend in a native window,
//           spawns the FastAPI backend, and adds system tray support.

const { app, BrowserWindow, Tray, Menu, Notification, nativeImage, ipcMain, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

// ── Config ────────────────────────────────────────────────────────────────────
const DEV_MODE = process.env.NODE_ENV !== 'production';
const FRONTEND_URL = DEV_MODE ? 'http://localhost:5173' : `file://${path.join(__dirname, '../dist/index.html')}`;
const BACKEND_PORT = 8000;
const BACKEND_URL = `http://localhost:${BACKEND_PORT}`;

let mainWindow = null;
let tray = null;
let backendProc = null;
let isQuitting = false;

// ── Backend startup ───────────────────────────────────────────────────────────
function startBackend() {
  if (DEV_MODE) {
    console.log('[Electron] DEV mode — backend should already be running via uvicorn');
    return;
  }

  // Production: run bundled backend.exe (PyInstaller output)
  const backendExe = path.join(process.resourcesPath, 'backend', 'backend.exe');
  if (!fs.existsSync(backendExe)) {
    console.warn('[Electron] backend.exe not found at:', backendExe);
    return;
  }

  backendProc = spawn(backendExe, [], {
    cwd: path.join(process.resourcesPath, 'backend'),
    stdio: 'ignore',
    detached: false,
  });

  backendProc.on('error', (err) => console.error('[Backend] Error:', err));
  backendProc.on('exit', (code) => console.log('[Backend] Exited with code:', code));
  console.log('[Backend] Started (PID:', backendProc.pid, ')');
}

function stopBackend() {
  if (backendProc) {
    backendProc.kill();
    backendProc = null;
    console.log('[Backend] Stopped.');
  }
}

// ── Tray icon helpers ─────────────────────────────────────────────────────────
function getTrayIcon() {
  // Use app icon if available, else a blank 16x16
  const iconPath = path.join(__dirname, 'assets', 'tray-icon.png');
  if (fs.existsSync(iconPath)) return nativeImage.createFromPath(iconPath);

  // Fallback: create a tiny green square programmatically
  return nativeImage.createFromDataURL(
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAHElEQVQ4T2Nk+A+EGSgkRowYNYBhNAiGQjAAAGsABgHb1X4AAAAASUVORK5CYII='
  );
}

function buildTrayMenu() {
  return Menu.buildFromTemplate([
    {
      label: '🛡️ PrivacyShield',
      enabled: false,
    },
    { type: 'separator' },
    {
      label: 'Open App',
      click: () => showWindow(),
    },
    {
      label: 'Open API Docs',
      click: () => shell.openExternal(`${BACKEND_URL}/docs`),
    },
    { type: 'separator' },
    {
      label: 'Quit PrivacyShield',
      click: () => {
        isQuitting = true;
        app.quit();
      },
    },
  ]);
}

// ── Window ────────────────────────────────────────────────────────────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'PrivacyShield',
    backgroundColor: '#0f1117',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    show: false, // Don't show until ready-to-show
  });

  mainWindow.loadURL(FRONTEND_URL);

  // Show when ready (avoids white flash)
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    if (DEV_MODE) mainWindow.webContents.openDevTools({ mode: 'detach' });
  });

  // Minimize to tray on close (Phase 14-A)
  mainWindow.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault();
      mainWindow.hide();

      // Show "still running" notification once
      if (Notification.isSupported()) {
        new Notification({
          title: '🛡️ PrivacyShield is still running',
          body: 'Monitoring your folders in the background. Right-click the tray icon to exit.',
          silent: true,
        }).show();
      }
    }
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

function showWindow() {
  if (!mainWindow) {
    createWindow();
  } else {
    mainWindow.show();
    mainWindow.focus();
  }
}

// ── Tray ──────────────────────────────────────────────────────────────────────
function createTray() {
  tray = new Tray(getTrayIcon());
  tray.setToolTip('PrivacyShield — Privacy Protection Running');
  tray.setContextMenu(buildTrayMenu());

  // Left-click on tray opens the app
  tray.on('click', () => showWindow());
  tray.on('double-click', () => showWindow());
}

// ── App lifecycle ─────────────────────────────────────────────────────────────
app.whenReady().then(() => {
  startBackend();

  // Wait a moment for backend to boot before opening window
  const delay = DEV_MODE ? 0 : 3000;
  setTimeout(() => {
    createWindow();
    createTray();
  }, delay);

  app.on('activate', () => {
    if (!mainWindow) createWindow();
  });
});

app.on('window-all-closed', (e) => {
  // Don't quit on macOS or when minimized to tray
  if (!isQuitting) e.preventDefault();
});

app.on('before-quit', () => {
  isQuitting = true;
  stopBackend();
});

// ── IPC handlers ──────────────────────────────────────────────────────────────
ipcMain.handle('app:version', () => app.getVersion());
ipcMain.handle('app:quit', () => { isQuitting = true; app.quit(); });
ipcMain.handle('app:show', () => showWindow());
ipcMain.handle('open:external', (_, url) => shell.openExternal(url));
