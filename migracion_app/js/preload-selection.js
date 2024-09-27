const { contextBridge, ipcRenderer } = require('electron');

ipcRenderer.on('destination-tables', function (emt, data) {
  let select = document.getElementById('floatingSelectDestinationTable')
  for (let table of Object.keys(data)){
    let option = document.createElement("option");
    option.text = table;
    option.value = table;
    select.add(option);
  }
});
ipcRenderer.on('origin-tables', function (emt, data) {
  let select = document.getElementById('floatingSelectOriginTable')
  for (let table of Object.keys(data)){
    let option = document.createElement("option");
    option.text = table;
    option.value = table;
    select.add(option);
  }
});

ipcRenderer.on('set-columns', function (emt,source,data) {
  if(source == "origin"){
    var element = document.getElementById("floatingSelectOriginColumn")
  }else{
    var element = document.getElementById("floatingSelectDestinationColumn")
  }
  element.disabled = false;
  removeOptions(element)

  data.forEach(column => {
    let option = document.createElement("option");
    option.text = column.COLUMN_NAME + " ("+column.DATA_TYPE+")";
    option.value = column.COLUMN_NAME + " ("+column.DATA_TYPE+")";
    element.add(option);
  });

  
});
function removeOptions(selectElement) {
  var i, L = selectElement.options.length - 1;
  for(i = L; i >= 0; i--) {
     selectElement.remove(i);
  }
}

ipcRenderer.on('set-db-names', function(emt,origindb,destinationdb){
  document.getElementById("origin-dbname").innerHTML = origindb
  document.getElementById("destination-dbname").innerHTML = destinationdb

})

contextBridge.exposeInMainWorld('electronAPI', {
  getTableColumns: (source,table) => ipcRenderer.send('get-columns',source,table),
  openImportWindow: (data,schedule) => ipcRenderer.send('set-up-import-window', data,schedule),
  openSelectionWindow: (data) => ipcRenderer.send('set-up-selection-window', data),
  newColumn: (columnData) => ipcRenderer.send('new-column',columnData)
})