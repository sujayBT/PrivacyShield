/**
 * preload.js — Electron Preload Script
 * Exposes safe IPC APIs to the renderer (React frontend).
 */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Get the backend port assigned at startup
  getBackendPort: () => ipcRenderer.invoke('get-backend-port'),
  getBackendPortSync: () => ipcRenderer.sendSync('get-backend-port-sync'),

  // Fetch desktop window/screen sources for capture
  getSources: () => ipcRenderer.invoke('get-sources'),

  // Trigger the updater
  checkForUpdates: () => ipcRenderer.invoke('check-for-updates'),

  // App info
  getVersion: () => ipcRenderer.invoke('get-version'),

  // Listen for backend status events
  onBackendStatus: (cb) => ipcRenderer.on('backend-status', (_e, status) => cb(status)),
});
