const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('desktop', {
  platform: process.platform,
  loadArchives: () => ipcRenderer.invoke('archive:load'),
  saveArchives: (archives) => ipcRenderer.invoke('archive:save', archives),
  exportArchives: (payload) => ipcRenderer.invoke('archive:export', payload),
  importArchives: () => ipcRenderer.invoke('archive:import'),
  exportReport: (payload) => ipcRenderer.invoke('report:export', payload),
})
