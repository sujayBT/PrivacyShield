// Preload script — runs in renderer process with access to Node.js APIs
// Exposes a safe, controlled API to the React app via contextBridge

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  getVersion:   ()    => ipcRenderer.invoke('app:version'),
  quit:         ()    => ipcRenderer.invoke('app:quit'),
  showWindow:   ()    => ipcRenderer.invoke('app:show'),
  openExternal: (url) => ipcRenderer.invoke('open:external', url),
  isElectron:   true,
});
