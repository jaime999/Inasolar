const { contextBridge, ipcRenderer } = require('electron');

ipcRenderer.on('set-import-tables', function (emt, data) {
  let tr = document.getElementById('data-row').children
  tr[0].innerHTML = data.ORIGIN_TABLE
  tr[1].innerHTML = data.ORIGIN_COLUMN
  tr[2].innerHTML = data.DESTINATION_TABLE
  tr[3].innerHTML = data.DESTINATION_COLUMN
  
  document.getElementById("origin-tablename").innerHTML = data.ORIGIN_TABLE + " sample data"
  document.getElementById("destination-tablename").innerHTML = data.DESTINATION_TABLE + " sample data"
});

ipcRenderer.on('set-origin-column-names', function (emt, data) {
  let originColumnsRow = document.getElementById("origin-columns")
  let columnSelect     = document.getElementById("column-select")
  data.forEach((value)=>{
    let th = document.createElement("th")
    th.innerHTML = value.COLUMN_NAME

    let option = document.createElement("option")
    option.text = value.COLUMN_NAME
    option.value = value.COLUMN_NAME

    originColumnsRow.appendChild(th)
    columnSelect.appendChild(option)
  })
});

ipcRenderer.on('set-sample', function (emt, data, source) {
  if(source == "origin"){
    var sampleTable = document.getElementById("origin-sample-data")
  }else{
    var sampleTable = document.getElementById("destination-sample-data")
  }
  data.forEach((row)=>{
    let tr = document.createElement("tr")
    for (let key of Object.keys(row)){
      let td = document.createElement("td")
      if(typeof row[key] == 'object' && row[key] != null){
        td.innerHTML = convertirFecha(row[key])
      }else{
        td.innerHTML = row[key]
      }
      tr.appendChild(td)
    }
    sampleTable.appendChild(tr)
  })
})

function convertirFecha(fechaString) {
  // Crea un objeto de fecha a partir de la cadena
  let fecha = new Date(fechaString);

  // Obtiene los componentes de la fecha
  let year    = fecha.getFullYear();
  let month   = String(fecha.getMonth() + 1).padStart(2, '0'); // Los meses comienzan desde 0
  let day     = String(fecha.getDate()).padStart(2, '0');
  let hours   = String(fecha.getHours()).padStart(2, '0');
  let minutes = String(fecha.getMinutes()).padStart(2, '0');
  let seconds = String(fecha.getSeconds()).padStart(2, '0');

  // Formatea la fecha en el formato deseado
  let fechaFormateada = `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;

  return fechaFormateada;
}

ipcRenderer.on('set-destination-column-names', function (emt, data) {
  let originColumnsRow = document.getElementById("destination-columns")
  data.forEach((value)=>{
    let th = document.createElement("th")
    th.innerHTML = value.COLUMN_NAME
    originColumnsRow.appendChild(th)
  })
});

ipcRenderer.on('set-locations', function(emt, data){
  let select = document.getElementById("location-select")
  select.innerHTML = ''
  data.forEach((location) =>{
    let option = document.createElement("option")
    option.innerHTML = location.Name
    option.value     = location.Name
    option.selected  = true 
    select.appendChild(option)
  })

})

ipcRenderer.on('set-areas', function(emt, data){
  let select = document.getElementById("areas-select")
  let latitudeInput = document.getElementById("latitude-input")
  let longitudeInput = document.getElementById("longitude-input")
  data.forEach((area) =>{
    let option = document.createElement("option")
    option.innerHTML = area.Name
    option.value     = area.id
    latitudeInput.value = parseFloat(area.Latitude).toFixed(3)
    longitudeInput.value = parseFloat(area.Longitude).toFixed(3)
    option.selected = true
    select.appendChild(option)
  })

})
ipcRenderer.on('set-coordinates', function(emt, coordinates){
  let latitudeInput = document.getElementById("latitude-input")
  let longitudeInput = document.getElementById("longitude-input")
  latitudeInput.value = parseFloat(coordinates[0].Latitude).toFixed(3)
  longitudeInput.value = parseFloat(coordinates[0].Longitude).toFixed(3)

})


function removeOptions(selectElement) {
  var i, L = selectElement.options.length - 1;
  for(i = L; i >= 0; i--) {
     selectElement.remove(i);
  }
}

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

  if(document.getElementById("floatingSelectDestinationColumn").disabled == false && document.getElementById("floatingSelectOriginColumn").disabled == false){
    document.getElementById("addCorrelationButton").disabled = false
  }
  
});

const operationCount = {count: 0,limit: 0}

ipcRenderer.on('set-progress-limit', function (emt,limit) {
  operationCount.limit = limit
  operationCount.count = 0
  let progressBar = document.getElementById("progress-bar")
  progressBar.innerHTML = '0/'+limit
  progressBar.style.width = "0%"

})

ipcRenderer.on('update-progress', function (emt) {
  operationCount.count++;
  let progressBar = document.getElementById("progress-bar")
  progressBar.innerHTML = operationCount.count+'/'+operationCount.limit
  progressBar.style.width = (operationCount.count/operationCount.limit) * 100 +"%"
})
  
ipcRenderer.on('schedule-data', function (emt, schedule){
  if(schedule){
    document.getElementById("schedule-data-button").hidden= false
    document.getElementById("import-data-button").hidden = true

    document.getElementById("frecuency1").hidden = false
    document.getElementById("frecuency-select").hidden = false
  }else{
    document.getElementById("schedule-data-button").hidden= true
    document.getElementById("import-data-button").hidden = false

    document.getElementById("frecuency1").hidden = true
    document.getElementById("frecuency-select").hidden = true
  }

})

contextBridge.exposeInMainWorld('electronAPI', {
  getTableColumns: (source,table) => ipcRenderer.send('get-columns',source,table),
  openImportWindow: (data) => ipcRenderer.send('set-up-import-window', data),
  openSelectionWindow: (data) => ipcRenderer.send('set-up-selection-window', data),
  importData: (data) => ipcRenderer.send('import-data', data),
  scheludeDataImport: (data) => ipcRenderer.send('schelude-data-import',data),
  getCoordinates: (locationName) => ipcRenderer.send('get-coordinates', locationName),
  newLocation: (locationData)=> ipcRenderer.send('new-location',locationData)
})