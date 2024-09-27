const { contextBridge, ipcRenderer } = require('electron');

ipcRenderer.on('destination-ready', function (evt) {
  document.getElementById('destination-state').innerHTML = "READY!"
  document.getElementById('destination-state').classList.remove("text-danger");
  document.getElementById('destination-state').classList.add("text-success")
});
ipcRenderer.on('origin-ready', function (evt) {
  document.getElementById('origin-state').innerHTML = "READY!"
  document.getElementById('origin-state').classList.remove("text-danger");
  document.getElementById('origin-state').classList.add("text-success")
});

contextBridge.exposeInMainWorld('electronAPI', {
  connectOrigin: (data) => ipcRenderer.send('connect-origin', data),
  connectDestination: (data)=> ipcRenderer.send('connect-destination',data),
  getTableColumns: (source,table) => ipcRenderer.send('get-columns',source,table),
  openSelectionWindow: (data) => ipcRenderer.send('set-up-selection-window', data)
})