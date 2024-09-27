const { app, BrowserWindow, ipcMain } = require('electron')
const path = require('node:path')
const Migrator = require('./db.js')


var migrator = new Migrator()

function handleOriginConnection(event, data){
  const webContents = event.sender
  const win = BrowserWindow.fromWebContents(webContents)
  console.log("INTENTO CONEXION RECIBIDO EN IPCMAIN ORIGEN")
  console.log(data)
  migrator.createConnection(data.source, data.host, data.port, data.dbname,data.dbusername,data.dbpassword).then((result)=>{
    if(result){
      win.webContents.send('origin-ready');
      checkTwoConnection().then((result) =>{
        if(result){
          createSelectionWindow()
          win.close()
        }
      })
    }
  })
}

function handleDestinationConnection(event, data){
  const webContents = event.sender
  const win = BrowserWindow.fromWebContents(webContents)
  console.log("INTENTO CONEXION RECIBIDO EN IPCMAIN DESTINO")
  console.log(data)
  migrator.createConnection(data.source, data.host, data.port, data.dbname,data.dbusername,data.dbpassword).then((result)=>{
    if(result){
      win.webContents.send('destination-ready');
      checkTwoConnection().then((result) =>{
        if(result){
          createSelectionWindow()
          win.close()
        }
      })

    }
  })
  
}

async function checkTwoConnection(){

  let origin = await migrator.try_connection("origin")
  let destination = await migrator.try_connection("destination")
  if(origin & destination){
    return true
  }
  return false

}

async function getTableColumns(event,source,table){
  const webContents = event.sender
  const win = BrowserWindow.fromWebContents(webContents)
  let columns = await migrator.getAllTableColumns(source,table)
  win.webContents.send("set-columns",source,columns)
}

const createWindow = () => {
    const mainWindow  = new BrowserWindow({
      width: 1000,
      height: 1000,
      webPreferences: {
        preload: path.join(__dirname, 'js/preload.js')
      },
    })

    mainWindow.loadFile('index.html')
    mainWindow.removeMenu()
    //mainWindow.webContents.openDevTools()
  }


function setUpSelection(emt){
  const webContents = emt.sender
  const win = BrowserWindow.fromWebContents(webContents)
  createSelectionWindow()
  win.close()

}

const createSelectionWindow = async () => {
  const mainWindow  = new BrowserWindow({
    width: 1000,
    height: 1000,
    webPreferences: {
      preload: path.join(__dirname, 'js/preload-selection.js')
    },
  })

  mainWindow.loadFile('selection.html')
  mainWindow.removeMenu()
  //mainWindow.webContents.openDevTools()
  mainWindow.webContents.send("set-db-names",migrator.connectionList["origin"].config.database,migrator.connectionList["destination"].config.database)
  let originData = await migrator.getAllTablenames("origin").then((e) => {
    const data = {};
    e.forEach(table => {
      data[table.table_name] = [];
    });
    return data;
  }).catch((err) => {
    console.error(err);
    return {}; // Devuelve un objeto vacío en caso de error
  });

  let destinationData = await migrator.getAllTablenames("destination").then((e) => {
    const data = {};
    e.forEach(table => {
      data[table.table_name] = [];
    });
    return data;
  }).catch((err) => {
    console.error(err);
    return {}; // Devuelve un objeto vacío en caso de error
  });

  mainWindow.webContents.send("destination-tables", destinationData)
  mainWindow.webContents.send("origin-tables", originData)

}

function setUpImport(emt,data,schedule){
  const webContents = emt.sender
  const win = BrowserWindow.fromWebContents(webContents)
  //console.log(data)
  createImportWindow(data,schedule)
  win.close()
}

const createImportWindow = (data,schedule) => {
  const mainWindow  = new BrowserWindow({
    width: 1000,
    height: 1000,
    webPreferences: {
      preload: path.join(__dirname, 'js/preload-import.js')
    },
  })

  mainWindow.loadFile('import.html')
  mainWindow.removeMenu()
  //mainWindow.webContents.openDevTools()
  
  mainWindow.webContents.send("schedule-data",schedule)
  
  mainWindow.webContents.send("set-import-tables",data)

  //getting origin column names
  migrator.getAllTableColumns("origin",data.ORIGIN_TABLE).then((result)=>{
    mainWindow.webContents.send("set-origin-column-names",result)
  })

  migrator.getAllTableColumns("destination",data.DESTINATION_TABLE).then((result)=>{
    mainWindow.webContents.send("set-destination-column-names",result)
  })

  migrator.getSampleData("origin",data.ORIGIN_TABLE).then((result)=>{
    mainWindow.webContents.send("set-sample", result,"origin")
  })

  migrator.getSampleData("destination",data.DESTINATION_TABLE).then((result)=>{
    mainWindow.webContents.send("set-sample", result,"destination")
  })

  /*ESTO NO ESTA FUNCIONANDO
  migrator.getLocalLocations().then((result)=>{
    console.dir(result)
    mainWindow.webContents.send("set-locations",result)
  })
  */
 //Probamos asi. Esto es para rellenar la lista de localizaciones
  migrator.getLocalLocations().then((rows)=>{
    mainWindow.webContents.send("set-locations",rows)
  }) 

  migrator.getLocalAreas().then((rows)=>{
    mainWindow.webContents.send("set-areas",rows)
  }) 

  
}

function importData(emt, data){
  const webContents = emt.sender
  const win = BrowserWindow.fromWebContents(webContents)
  migrator.getIdByLocationName(data.location).then((idLocation)=>{
    var locationId = idLocation
    migrator.getTableDateColumns("origin",data.ORIGIN_TABLE).then((result)=>{
      console.log(data)
      const datetimeColumn = result[0].COLUMN_NAME //suponemos que es la primera
      const destinationDatatype = (data.DESTINATION_COLUMN).split(" ").slice(-1)[0]
      const originDatatype = (data.ORIGIN_COLUMN).split(" ").slice(-1)[0]
      const originColumn = data.ORIGIN_COLUMN.split(" ").slice(0, -1).join(" ")
      const destinationColumn = data.DESTINATION_COLUMN.split(" ").slice(0, -1).join(" ")
  
      const parsed = parseRestrictions(data.restrictions,datetimeColumn)
      const query = `SELECT [${datetimeColumn}],[${originColumn}] FROM ${data.ORIGIN_TABLE} WHERE ${parsed}`
      console.log(query)
      //Cogemos los datos del origen
      migrator.executeQuery("origin",query).then((result)=>{
        let rowsToInsert = []
        console.log(result.length)
        //AQUI SE HACE LA SELECCION DE FECHA DE MOMENTO HORAS EXACTAS
        result.forEach((row)=>{
          //cogemos la fecha y comprobamos si es una hora exacta
          let fecha = new Date(row[datetimeColumn])
          let hours = fecha.getHours();
          let minutes = fecha.getMinutes();
          //REDONDEAMOS A HORA EXACTA SI MINUTO >= 58 O MINUTO <=2
          if(minutes <= 2 || minutes >=58){
            let fecha_parseada = convertirFecha(row[datetimeColumn])
            if(minutes <= 2){
              row[datetimeColumn] = fecha_parseada.split(" ")[0] + " " +fecha_parseada.split(" ")[1].split(":")[0] + ":00:00"
            }else{
              row[datetimeColumn] = fecha_parseada.split(" ")[0] + " " + String(parseInt(fecha_parseada.split(" ")[1].split(":")[0])+1).padStart(2, '0') + ":00:00"
            }
            //Multiplicamos por el coeficiente seleccionado por el usuario
            if(originDatatype == '(float)' || originDatatype == '(int)'|| originDatatype == '(real)'){
              row[originColumn] = row[originColumn] * data.coefficient
            }
            //Parseamos el data a float o int
            if((destinationDatatype == '(float)' ||destinationDatatype == '(real)') && !isNaN(parseFloat(row[originColumn]))){
              row[originColumn] = parseFloat(row[originColumn])
            }else if(destinationDatatype == '(int)' && !isNaN(parseInt(row[originColumn]))){
              row[originColumn] = parseInt(row[originColumn])
            }
            rowsToInsert.push(row)
          }
        })
        console.log(rowsToInsert.length)
        //actualizamos la barra de progreso
        win.webContents.send('set-progress-limit',rowsToInsert.length)
        rowsToInsert.forEach((row)=>{
          row[datetimeColumn] = convertirFecha(row[datetimeColumn])

          migrator.getDateIdFromInasolar(row[datetimeColumn]).then((id)=>{
            //si existe la fecha en inasolar
            if (id.length >0 ){
              let insert = `INSERT INTO ${data.DESTINATION_TABLE}(${destinationColumn},date,location) VALUES(${row[originColumn]},${id[0].id},${locationId[0].id})`
              migrator.executeQuery("destination",insert).then(()=>{
                win.webContents.send('update-progress')
              }).catch((errorInsert)=>{
                let update = `UPDATE ${data.DESTINATION_TABLE} SET ${destinationColumn} = ${row[originColumn]} WHERE date = ${id[0].id} AND location = ${locationId[0].id}`
                //console.log(update)
                migrator.executeQuery("destination",update).then(()=>{
                  win.webContents.send('update-progress')
                })
              })
            //si no existe fecha la creamos
            }else{
              fecha = new Date(row[datetimeColumn])
              let insertDate = `INSERT INTO Dates(Date, Hour,Day,Month,DayOfWeek,YearDay,Year) VALUES(CAST('${row[datetimeColumn].replace(' ','T')}' as datetime), ${fecha.getHours()}, ${fecha.getDate()}, ${fecha.getMonth()}, ${fecha.getDay()+1}, NULL, ${fecha.getFullYear()})`
              
              migrator.executeQuery("destination",insertDate).then(()=>{
                migrator.getDateIdFromInasolar(row[datetimeColumn]).then((id)=>{
                  let insert = `INSERT INTO ${data.DESTINATION_TABLE}(${destinationColumn},date,location) VALUES(${row[originColumn]},${id[0].id},${locationId[0].id})`
                  migrator.executeQuery("destination",insert).then(()=>{
                    win.webContents.send('update-progress')
                  }).catch((errorInsert)=>{
                    let update = `UPDATE ${data.DESTINATION_TABLE} SET ${destinationColumn} = ${row[originColumn]} WHERE date = ${id[0].id} AND location = ${locationId[0].id}`
                    migrator.executeQuery("destination",update).then(()=>{
                      win.webContents.send('update-progress')
                    })
                  })
                }).catch((error)=>{
                  //win.webContents.send('update-progress')
                  console.log(insertDate,)
                  return undefined
                })              
                //AQUI TERMINA LO NUIEVO
              }).catch((error)=>{
                console.log(row[datetimeColumn],error)

                return undefined
              })
            
            }
          }).catch((error)=>{
            //win.webContents.send('update-progress')
            console.log(row[datetimeColumn])
            return undefined
          })
        })
      })  
    })
  })
  
}

function convertirFecha(fechaString) {
  // Crea un objeto de fecha a partir de la cadena
  let fecha = new Date(fechaString);

  // Obtiene los componentes de la fecha
  let year = fecha.getFullYear();
  let month = String(fecha.getMonth() + 1).padStart(2, '0'); // Los meses comienzan desde 0
  let day = String(fecha.getDate()).padStart(2, '0');
  let hours = String(fecha.getHours()).padStart(2, '0');
  let minutes = String(fecha.getMinutes()).padStart(2, '0');

  // Formatea la fecha en el formato deseado
  let fechaFormateada = `${year}-${month}-${day} ${hours}:${minutes}:00`;

  return fechaFormateada;
}

function parseRestrictions(restrictionList, datetimeColumn){
  try{
    let restrictions = []
    for(let restriction of restrictionList){
      if(restriction[0] == 'start_date' || restriction[0] == 'end_date'){
        restrictions.push(datetimeColumn +" "+restriction[1]+" CAST('"+migrator.convertirFecha(restriction[2]).replace(" ","T")+"' AS DATETIME)")
      }else{
        let value = parseFloat(restriction[2])
        //si es NaN es un string
        if(isNaN(value)){
          restrictions.push("["+restriction[0]+"] "+restriction[1]+" '"+restriction[2]+"'")
        }else{
          restrictions.push("["+restriction[0]+"] "+restriction[1]+" "+value+"")
        }
      }
    }
    return restrictions.join(" AND ")
  }catch(err){
    return err
  }
  
}

function getCoordinates(emt, locationName){
  const webContents = emt.sender
  const win = BrowserWindow.fromWebContents(webContents)
  migrator.getAreaCoordinatesByName(locationName).then((coordinates)=>{
    win.webContents.send('set-coordinates',coordinates)
  })
}

function newLocation(emt,locationData){
  const webContents = emt.sender
  const win = BrowserWindow.fromWebContents(webContents)
  migrator.insertNewLocationInInasolar(locationData).then((result)=>{
    if(result){
      migrator.getLocalLocations().then((rows)=>{
        win.webContents.send("set-locations",rows)
      }) 
    }
  })
  console.log(locationData)
}

function newColumn(emt, columnData){
  const webContents = emt.sender
  const win = BrowserWindow.fromWebContents(webContents)
  migrator.newColumn(columnData).then((result)=>{
    if(result){
      migrator.getAllTableColumns(columnData.columnSource,columnData.columnTable).then((columns)=>{
        win.webContents.send("set-columns",columnData.columnSource,columns)
      })
    }
  })
  
}

//ME HE QUEDADO AQUÍ
function scheduleDataImport(emt, data){
  const webContents = emt.sender
  const win = BrowserWindow.fromWebContents(webContents)
  //console.log(data)
  migrator.newDataImportTask(data).then(()=>{
    importData(emt, data)

    console.log("importando datos...")
  })
}

app.whenReady().then(() => {
    ipcMain.on('connect-origin', handleOriginConnection)
    ipcMain.on('connect-destination',handleDestinationConnection)
    ipcMain.on('get-columns',getTableColumns)
    ipcMain.on('set-up-import-window',setUpImport)
    ipcMain.on('set-up-selection-window',setUpSelection)
    ipcMain.on('import-data',importData)
    ipcMain.on('get-coordinates',getCoordinates)
    ipcMain.on('new-location', newLocation)
    ipcMain.on('new-column',newColumn)
    ipcMain.on('schelude-data-import',scheduleDataImport)
    createWindow()
})

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit()
  })