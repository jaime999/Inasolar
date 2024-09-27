const sql = require('mssql')
const sqlite3 = require('sqlite3').verbose();

class Migrator{
  //Constructor
  constructor() {
    // Initialize an object to store database connections.
    this.connectionList = {};

    // Create a connection to a remote database named "inasolar" with the specified parameters.
    this.createConnection("inasolar", "158.42.22.107", 1433, "inasolar", "GEDER", "GEDER");

    // Create a new instance of a local SQLite3 database named 'migrator.db'.
    const db = new sqlite3.Database('migrator.db');
    // Add the local database to the list of connections under the name "local."
    this.connectionList["local"] = db;

    // Attempt to connect to the remote database "inasolar" and take an action if the connection is successful.
    this.try_connection("inasolar").then((e) => {
      if (e) {
        // If the connection is successful, call the "updateLocalDB" function to perform a local update.
        this.updateLocalDB();
      }
    });

    // Commented out to prevent execution at this time. You can uncomment this line if necessary.
    // this.getAllTablenames("inasolar");
  }

  /**
   * Check if an identifier exists in the connection list.
   * @param {string} identifier - Identifier of the connection to check.
   * @return {boolean} - Returns true if the identifier exists, or false if it does not.
   */
  checkIdentifier(identifier) {
    // Check if the specified identifier exists in the connection list.
    if (identifier in this.connectionList) {
      return true; // Return true if the identifier exists.
    }
    // Return false if the identifier does not exist in the connection list.
    return false;
  }

  /**
 * Get the list of connections.
  * @return {Object} - Returns the connection list as an object.
  */
  get connections() {
    // Return the connectionList object, which contains a list of connections.
    return this.connectionList;
  }

  /**
   * Add or register a connection pool to the connectionList.
   * @param {string} identifier - Identifier for the connection.
   * @param {string} server - Server address.
   * @param {number} port - Server port (default is 1433).
   * @param {string} database - Database name.
   * @param {string} username - Database username.
   * @param {string} password - Database password.
   * @return {boolean} - Returns true if the connection is successfully registered, or false if it fails.
   */
  async createConnection(identifier, server, port = 1433, database, username, password) {
    // Create a new connection pool with the provided parameters.
    const pool = new sql.ConnectionPool({
      user: username,
      password: password,
      server: server,
      database: database,
      port: port,

      pool: {
        max: 100,
        min: 0,
        // acquire promises are rejected after this many milliseconds
        // if a resource cannot be acquired
        acquireTimeoutMillis: 300000000,

        // create operations are cancelled after this many milliseconds
        // if a resource cannot be acquired
        createTimeoutMillis: 300000000,

        // destroy operations are awaited for at most this many milliseconds
        // new resources will be created after this timeout
        destroyTimeoutMillis: 300000000,

        // free resouces are destroyed after this many milliseconds
        idleTimeoutMillis: 300000000,

        // how often to check for idle resources to destroy
        reapIntervalMillis: 1000,

        // how long to idle after failed create before trying again
        createRetryIntervalMillis: 200,
      },
      options: {
        encrypt: false,
      }
    })

    // Add the connection pool to the connectionList under the specified identifier.
    this.connectionList[identifier] = pool;

    try {
      // Attempt to connect to the database.
      await pool.connect();

      // If the connection attempt is not successful, remove the connection from the list and return false.
      if (!this.try_connection(identifier)) {
        delete this.connectionList[identifier];
        return false;
      }
      
      this.registerConnection(server, port, database, username, password)
      return true; // Return true if the connection is successfully registered.
    } catch (error) {
      // If an error occurs during the connection attempt, remove the connection from the list and return false.
      delete this.connectionList[identifier];
      return false;
    }
  }
  
  /**
   * Add connection data to local db for scheluded data task.
   * @param {string} server - Server address.
   * @param {number} port - Server port (default is 1433).
   * @param {string} database - Database name.
   * @param {string} username - Database username.
   * @param {string} password - Database password.
   * @return {boolean} - Returns true if the connection is successfully registered, or false if it fails.
   */
  async registerConnection(server, port , database, username, password){
      if(this.checkIdentifier("local")){
        let db = this.connectionList["local"];
        import('egoroof-blowfish').then((module) => {
          // Now we can use Blowfish here
          const { Blowfish } = module;
          let bf = new Blowfish('superkeygeder')
          let pass = bf.encode(password)

          if(port == ''){
            port = 1433
          }
          //ELIMINAR
          let insertQuery = `INSERT INTO CONNECTIONS(DBHost,DBName,DBPort,DBUser,DBPassword) VALUES('${server}','${database}',${port},'${username}','${pass}') 
          ON CONFLICT DO UPDATE SET 
            DBHost=excluded.DBHost,
            DBName=excluded.DBName,
            DBPort=excluded.DBPort,
            DBUser=excluded.DBUser,
            DBPassword=excluded.DBPassword
          `
          db.run(insertQuery)

          this.executeQuery("inasolar", `INSERT INTO CONNECTIONS(DBHost,DBName,DBPort,DBUser,DBPassword) VALUES('${server}','${database}',${port},'${username}','${pass}')`).catch( (e)=>{
            console.log("Ya esta registrada la conexion")
          })
          return true
        }).catch((error) => {
          console.error(error);
        });
      }
      return false
  }

  /**
   * Attempt to establish a connection with the database associated with the given identifier.
   * @param {string} identifier - Identifier of the connection to be attempted.
   * @return {boolean} - Returns true if the connection is successfully established, or false if it fails.
   */
  async try_connection(identifier) {
    if (this.checkIdentifier(identifier)) {
      try {
        // Attempt to connect to the database associated with the provided identifier.
        await this.connectionList[identifier].connect();
        console.error("Successfully connected to", this.connectionList[identifier].config.database);
        return true; // Return true if the connection is successfully established.
      } catch (err) {
        console.error("Failed to connect to", this.connectionList[identifier].config.database);
        return false; // Return false if there is an error while establishing the connection.
      }
    }
  }

  /**
   * Close a registered database connection.
   * @param {string} identifier - Identifier of the connection to be closed.
   * @return {boolean} - Returns true if the disconnection is successful, or false if it fails.
   */
  async closeConnection(identifier) {
    if (this.checkIdentifier(identifier)) {
      // Delete the connection associated with the provided identifier from the connectionList.
      delete this.connectionList[identifier];
      return true; // Return true if the disconnection is successful.
    }
    return false; // Return false if the specified connection doesn't exist in the connectionList.
  }

  /**
   * Update or Create the local database (Requires connections to 'local' and 'inasolar' databases).
   */
  async updateLocalDB() {
    // Check if a 'local' database connection exists.
    if (this.checkIdentifier("local")) {
      // Create or update tables in the local database.
      await this.createLocalTables();

      // Check if a 'inasolar' database connection exists.
      if (this.checkIdentifier("inasolar")) {
        // Update data related to areas and locations in the local database.
        this.updateAreas();
        this.updateLocations();

        // Uncomment this line to update dates if needed.
        // this.updateDates();
      }
    }
    return false
  }

  /**
   * Retrieve areas from the 'inasolar' database and copy the data into our local database.
   */
  async updateAreas() {
    // Define a SQL query to retrieve areas from the 'inasolar' database.
    let query = "SELECT * FROM Area";
    // Execute the query and store the results in the 'areas' variable.
    let areas = await this.executeQuery("inasolar", query);
    // Get a reference to the local database.
    let db = this.connectionList["local"];
    // Clear existing data in the 'Area' table in the local database.
    await db.exec("DELETE FROM Area");
    
    // Iterate through the retrieved areas and insert them into the local database.
    areas.forEach((element) => {
      query = `INSERT INTO Area(id, Name, Latitude, Longitude) VALUES (
        ${element.id}, '${element.Name}', ${element.Latitude}, ${element.Longitude}
      )`;
      // Execute the insertion query in the local database.
      db.serialize(function() {
        db.exec("BEGIN");
        db.exec(query);
        db.exec("COMMIT");
      });
    });
  }

  /**
   * Retrieve locations from the 'inasolar' database and copy the data into our local database.
   */
  async updateLocations() {
    // Define a SQL query to retrieve locations from the 'inasolar' database.
    let query = "SELECT * FROM Locations";
    // Execute the query and store the results in the 'locations' variable.
    let locations = await this.executeQuery("inasolar", query);
    // Get a reference to the local database.
    let db = this.connectionList["local"];
    // Clear existing data in the 'Locations' table in the local database.
    await db.exec("DELETE FROM Locations");
    
    // Iterate through the retrieved locations and insert them into the local database.
    locations.forEach((element) => {
      query = `INSERT INTO Locations(id, Name, Latitude, Longitude, Type, Area) VALUES (
        ${element.id}, '${element.Name}', ${element.Latitude.replace(",", ".")}, ${element.Longitude.replace(",", ".")}, '${element.Type}', ${element.Area}
      )`;
      // Execute the insertion query in the local database.
      db.serialize(function() {
        db.exec("BEGIN");
        db.exec(query);
        db.exec("COMMIT");
      });
    });
  }

  /**
   * Get Dates from inasolar and then we copy data into our local Db
   */
  async updateDates(){
    console.log("Updating Dates...")
    let db = this.connectionList["local"];
    await db.run("DELETE FROM Dates");
    let query = "SELECT id,Date FROM Dates";
    let dates = await this.executeQuery("inasolar",query);
    dates.forEach((element) =>{
      query = `INSERT INTO Dates(id,Date) VALUES(
        ${element.id}, '${this.convertirFecha(element.Date)}'
      )`
      db.exec(query);
    })
  }

  /**
   * Convert a date string into a specific date and time format.
   * @param {string} fechaString - Date string to be converted.
   * @returns {string} - Returns the formatted date string in the desired format.
   */
  convertirFecha(fechaString) {
    // Create a Date object from the input date string.
    let fecha = new Date(fechaString);

    // Extract date components.
    let year = fecha.getFullYear();
    let month = String(fecha.getMonth() + 1).padStart(2, '0'); // Months are zero-based.
    let day = String(fecha.getDate()).padStart(2, '0');
    let hours = String(fecha.getHours()).padStart(2, '0');
    let minutes = String(fecha.getMinutes()).padStart(2, '0');
    let seconds = String(fecha.getSeconds()).padStart(2, '0');

    // Format the date into the desired format.
    let fechaFormateada = `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;

    return fechaFormateada;
  }

  /**
   * Execute a SQL query using a specified connection identifier.
   * @param {string} identifier - Identifier of the connection to use.
   * @param {string} query - The SQL query to execute.
   * @return {Array} - An array containing the result of the query.
   */
  async executeQuery(identifier, query) {
    try {
      // Get the specified database connection from the connectionList.
      const db = this.connectionList[identifier];
      
      // Connect to the database.
      await db.connect();
      
      // Execute the SQL query and store the result.
      const result = await db.query(query);
      
      // Commented out because it appeared to cause issues.
      // Close the database connection.
      // await db.close();
      
      // Return the recordset (result) of the query.
      return result.recordset;
    } catch (err) {
      // If an error occurs during query execution, throw the error for handling.
      throw err;
    }
  }

  /**
   * Get the names of all tables from a specified database connection.
   * @param {string} identifier - Identifier of the connection to use.
   * @return {Array} - An array containing the table names retrieved from the database.
   */
  async getAllTablenames(identifier) {
    if (this.checkIdentifier(identifier)) {
      // Define a SQL query to retrieve table names from the database.
      let query = "SELECT table_name FROM information_schema.tables ORDER BY table_name ASC;";
      
      try {
        // Execute the query and store the result.
        let result = await this.executeQuery(identifier, query);
        if (result) {
          // Uncomment this line to display the result for debugging.
          // console.dir(result);
          return result; // Return the array of table names.
        } else {
          console.log("No tables found."); // Log a message if no tables are found.
          return undefined; // Return undefined when no tables are found.
        }
      } catch (err) {
        console.error("Error in getAllTableNames:", err); // Log an error message if an error occurs.
        return undefined; // Return undefined in case of an error.
      }
    }
    return undefined; 
  }

  /**
   * Get the details of all columns from a specified table in a database connection.
   * @param {string} identifier - Identifier of the connection to use.
   * @param {string} table - Name of the table for which column details are retrieved.
   * @return {Array} - An array containing the column details of the specified table.
   */
  async getAllTableColumns(identifier, table) {
    if (this.checkIdentifier(identifier)) {
      // Define a SQL query to retrieve column details of the specified table.
      let query = `SELECT COLUMN_NAME, IS_NULLABLE, DATA_TYPE FROM information_schema.columns WHERE table_name = '${table}'`;
      
      try {
        // Execute the query and store the result.
        let result = await this.executeQuery(identifier, query);
        if (result) {
          // Uncomment this line to display the result for debugging.
          // console.dir(result);
          return result; // Return the array containing column details.
        } else {
          console.log("No tables found."); // Log a message if no tables are found.
          return undefined; // Return undefined when no tables are found.
        }
      } catch (err) {
        console.error("Error in getAllTableColumns:", err); // Log an error message if an error occurs.
        return undefined; // Return undefined in case of an error.
      }
    }
  }

  /**
   * Get details of all datetime columns from a specified table in a database connection.
   * @param {string} identifier - Identifier of the connection to use.
   * @param {string} table - Name of the table for which datetime column details are retrieved.
   * @return {Array} - An array containing the datetime column details of the specified table.
   */
  async getTableDateColumns(identifier, table) {
    if (this.checkIdentifier(identifier)) {
      // Define a SQL query to retrieve datetime column details of the specified table.
      let query = `SELECT COLUMN_NAME, IS_NULLABLE, DATA_TYPE FROM information_schema.columns WHERE table_name = '${table}' AND DATA_TYPE = 'datetime'`;
      
      try {
        // Execute the query and store the result.
        let result = await this.executeQuery(identifier, query);
        if (result) {
          // Uncomment this line to display the result for debugging.
          // console.dir(result);
          return result; // Return the array containing datetime column details.
        } else {
          console.log("No tables found."); // Log a message if no tables are found.
          return undefined; // Return undefined when no tables are found.
        }
      } catch (err) {
        console.error("Error in getTableDateColumns:", err); // Log an error message if an error occurs.
        return undefined; // Return undefined in case of an error.
      }
    }
  }

  /**
   * Retrieve the first 'n' rows from a specified table in a database connection.
   * @param {string} identifier - Identifier of the connection to use.
   * @param {string} table - Name of the table from which data is retrieved.
   * @param {number} numberOfRows - Number of rows to retrieve (default is 10).
   * @return {Array} - An array containing the result of the query, limited to the specified number of rows.
   */
  async getSampleData(identifier, table, numberOfRows = 10) {
    // Construct a SQL query to retrieve the first 'n' rows from the specified table.
    let query = `SELECT TOP ${numberOfRows} * FROM ${table}`;
    
    // Execute the query and store the result.
    let result = await this.executeQuery(identifier, query);

    return result; // Return the array containing the limited result set.
  }

 /**
   * Get the location IDs from the local database based on the location name.
   * @param {string} name - Name of the location to search for.
   * @return {Promise<Array>} - A promise that resolves with an array containing the result of the query.
   */
  async getIdByLocationName(name) {


    if(this.checkIdentifier("inasolar")){
      //let db = this.connectionList["local"];

      return new Promise((resolve, reject) => {
        this.executeQuery("inasolar",`SELECT id FROM Locations WHERE Name = '${name}'`).then((rows)=>{
          resolve(rows)
        }).catch((err)=>{
          reject(err)
        })
      });
    }else{
      return undefined
    }
    /* eliminar
    // Get a reference to the local database.
    let db = this.connectionList["local"];

    // Return a promise for executing the query to find the location ID by name.
    return new Promise((resolve, reject) => {
      // Execute the SQL query to retrieve location IDs based on the provided name.
      db.all(`SELECT id FROM Locations WHERE Name = '${name}'`, (err, rows) => {
        if (err) {
          reject(err); // Reject the promise if an error occurs.
        } else {
          resolve(rows); // Resolve the promise with the array of results.
        }
      });
    });*/
  }

  /**
   * Retrieve all locations from the local database.
   * @return {Promise<Array>} - A promise that resolves with an array containing the result of the query.
   */
  async getLocalLocations() {
    // Get a reference to the local database.
    let db = this.connectionList["local"];

    // Return a promise for executing the query to retrieve all locations.
    return new Promise((resolve, reject) => {
      // Execute the SQL query to retrieve all locations from the local database.
      db.all(`SELECT * FROM Locations`, (err, rows) => {
        if (err) {
          reject(err); // Reject the promise if an error occurs.
        } else {
          resolve(rows); // Resolve the promise with the array of results.
        }
      });
    });
  }

 /**
   * Retrieve all areas from the local database.
   * @return {Promise<Array>} - A promise that resolves with an array containing the result of the query.
   */
  async getLocalAreas() {
    // Get a reference to the local database.
    let db = this.connectionList["local"];

    // Return a promise for executing the query to retrieve all areas.
    return new Promise((resolve, reject) => {
      // Execute the SQL query to retrieve all areas from the local database.
      db.all(`SELECT * FROM Area`, (err, rows) => {
        if (err) {
          reject(err); // Reject the promise if an error occurs.
        } else {
          resolve(rows); // Resolve the promise with the array of results.
        }
      });
    });
  }

  /**
   * Retrieve coordinates of an area by its name from the local database.
   * @param {string} locationName - Name of the area for which coordinates are to be retrieved.
   * @return {Promise<Array>} - A promise that resolves with an array containing the result of the query.
   */
  async getAreaCoordinatesByName(locationName) {
    // Get a reference to the local database.
    let db = this.connectionList["local"];

    // Return a promise for executing the query to retrieve area coordinates by name.
    return new Promise((resolve, reject) => {
      // Execute the SQL query to retrieve area coordinates based on the provided name.
      db.all(`SELECT * FROM Area WHERE name = '${locationName}'`, (err, rows) => {
        if (err) {
          reject(err); // Reject the promise if an error occurs.
        } else {
          resolve(rows); // Resolve the promise with the array of results.
        }
      });
    });
  }


  /**
 * Get the ID of a date from the 'Dates' table in the 'inasolar' database based on a date string.
 * @param {string} dateString - Date in string format (example: '2021-02-01 00:00:00').
 * @return {Promise<Array>} - A promise that resolves with an array containing the result of the query.
 */
  async getDateIdFromInasolar(dateString) {
    // Define a regular expression to match the expected date string format.
    const regex = /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})$/;
    
    try {
      // Check if the date string matches the expected format and the connection is to the 'inasolar' database.
      if (regex.test(dateString) && this.connectionList["destination"].config.database === "inasolar") {
        // Construct a SQL query to retrieve the ID of the specified date from the 'Dates' table.
        const query = `SELECT id FROM Dates WHERE Date = CAST('${dateString}' AS datetime)`;
        
        // Execute the query and store the result.
        let result = await this.executeQuery("destination", query);
        
        return result; // Return a promise that resolves with the array of results.
      }
    } catch (error) {
      console.log("Error in function:", error, dateString); // Log an error message if an error occurs.
      return undefined; // Return undefined in case of an error.
    }
  }

  /**
   * Insert a new location into the 'Locations' table in the 'inasolar' database.
   * @param {Object} data - Location data to be inserted.
   * @return {boolean} - True if the insertion is successful, false otherwise.
   */
  async insertNewLocationInInasolar(data) {
    // Check if the 'inasolar' connection is available.
    if (this.checkIdentifier("inasolar")) {
      // Construct a SQL query to insert the provided location data into the 'Locations' table.
      const query = `INSERT INTO Locations(Name, Latitude, Longitude, Type, Area) VALUES('${data.Name}', ${data.Latitude}, ${data.Longitude}, '${data.Type}', ${data.Area})`;

      try {
        // Execute the insertion query.
        await this.executeQuery("inasolar", query);
        
        // Update the list of locations in the 'inasolar' database.
        await this.updateLocations();
        
        return true; // Return true once the operation is successfully completed.
      } catch (error) {
        console.error("Error:", error); // Log an error message if an error occurs during the insertion.
        return false; // Return false in case of an error.
      }
    }
    return false;
    
  }

  async newColumn(data){
    if (this.checkIdentifier(data.columnSource)) {
      const query = `ALTER TABLE ${data.columnTable} ADD [${data.columnName}] ${data.columnDatatype}`;
      try {
        // Execute the insertion query.
        await this.executeQuery(data.columnSource, query).then((e)=>{
          // To show this new column in webpage
          if(this.connectionList["destination"].config.database == 'inasolar'){
            let insert = "INSERT INTO descripcionDatos (nombre_dato,nombre_alternativo,descripcion,unidad,tabla)"
            insert += ` VALUES ('${data.columnName}','${data.columnAlternativeName}', '${data.columnDescription}', '${data.columnUnit}','${data.columnTable}')`
            this.executeQuery("destination",insert)
            return true
          }
          
        });
        
        return true; // Return true once the operation is successfully completed.
      } catch (error) {
        console.error("Error:", error); // Log an error message if an error occurs during the insertion.
        return false; // Return false in case of an error.
      }

    }
    return false
  }

  async getLocalConnectionIdByDBname(dbname){
    if(this.checkIdentifier("inasolar")){
      //let db = this.connectionList["local"];

      return new Promise((resolve, reject) => {
        this.executeQuery("inasolar",`SELECT id FROM CONNECTIONS WHERE DBName = '${dbname}'`).then((rows)=>{
          resolve(rows[0])
        }).catch((err)=>{
          reject(err)
        })
        /*
        db.all(`SELECT id FROM CONNECTIONS WHERE DBName = '${dbname}'`, (err, rows) => {
          if (err) {
            reject(err); // Reject the promise if an error occurs.
          } else {
            resolve(rows[0]); // Resolve the promise with the array of results.
          }
        });*/

      });
    }else{
      return undefined
    }
    
  }

  async newDataImportTask(data){
    if(this.checkIdentifier("local")){
      // Necesitamos coger los ID de las conexiones para interrelacionarlas y de la localizacion
      // Id destino 
      this.getLocalConnectionIdByDBname(this.connectionList["destination"].config.database).then((destinationID)=>{
        data["DESTINATION_DB_ID"] = destinationID.id
        // Id origen
        this.getLocalConnectionIdByDBname(this.connectionList["origin"].config.database).then((originID)=>{
          data["ORIGIN_DB_ID"] = originID.id
          // Id Localizacion
          this.getIdByLocationName(data.location).then((locationID)=>{
            //ignoramos las restricciones de las fecha que tienen columna propia
            let restrictions = data.restrictions.slice(2,).join('$')
            let originColumn = data["ORIGIN_COLUMN"].split(" ").slice(0, -1).join(" ") //Quitamos el datatype que aqui no hace falta
            let destinationColumn = data["DESTINATION_COLUMN"].split(" ").slice(0, -1).join(" ")//Quitamos el datatype que aqui no hace falta
            //console.log(restrictions)
            //Una vez tenemos los Identificadores podemos añadir la tarea de importacion de datos en la bases de datos local
            let query = `INSERT INTO CORRELATIONS(DBOrigin,DBDestination,TableOrigin,TableDestination,ColumnOrigin,ColumnDestination,StartDate,EndDate,
              LastUpdate,Coefficient, Restrictions, Location, Frecuency) VALUES(${data["ORIGIN_DB_ID"]},${data["DESTINATION_DB_ID"]},'${data["ORIGIN_TABLE"]}',
              '${data["DESTINATION_TABLE"]}','${originColumn}','${destinationColumn}','${data["restrictions"][0][2]} 00:00:00',
              '${data["restrictions"][1][2]} 00:00:00', datetime('now'),${data.coefficient},'${restrictions}',${locationID[0].id},'${data["frecuency"]}')`
            
            let db = this.connectionList["local"];

            //para inasolar
            let query2 = `INSERT INTO CORRELATIONS(DBOrigin,DBDestination,TableOrigin,TableDestination,ColumnOrigin,ColumnDestination,StartDate,EndDate,
              LastUpdate,Coefficient, Restrictions, Location, Frecuency) VALUES(${data["ORIGIN_DB_ID"]},${data["DESTINATION_DB_ID"]},'${data["ORIGIN_TABLE"]}',
              '${data["DESTINATION_TABLE"]}','${originColumn}','${destinationColumn}','${data["restrictions"][0][2]} 00:00:00',
              '${data["restrictions"][1][2]} 00:00:00', GETDATE(),${data.coefficient},'${restrictions}',${locationID[0].id},'${data["frecuency"]}')`
            //si falla update
              this.executeQuery("inasolar",query2).catch((e)=>{
              query2 = `UPDATE CORRELATIONS SET DBOrigin = ${data["ORIGIN_DB_ID"]}, DBDestination = ${data["DESTINATION_DB_ID"]},
              TableOrigin = '${data["ORIGIN_TABLE"]}',TableDestination = '${data["DESTINATION_TABLE"]}',ColumnOrigin = '${originColumn}',
              ColumnDestination ='${destinationColumn}' ,StartDate = '${data["restrictions"][0][2]} 00:00:00',EndDate = '${data["restrictions"][1][2]} 00:00:00',
                LastUpdate = GETDATE(),Coefficient = ${data.coefficient}, Restrictions = '${restrictions}', Location = ${locationID[0].id}, Frecuency = '${data["frecuency"]}'
                WHERE DBOrigin = ${data["ORIGIN_DB_ID"]} and DBDestination = ${data["DESTINATION_DB_ID"]} and
                TableOrigin = '${data["ORIGIN_TABLE"]}' and TableDestination = '${data["DESTINATION_TABLE"]}' and ColumnOrigin = '${originColumn}' and
                ColumnDestination ='${destinationColumn}'`
                this.executeQuery("inasolar",query2).catch((e)=>{console.log(e)})
            })

            try{
              db.run(query)
              return true
            }catch(err){
              return false
            }
          }).catch((error)=>{
            console.log("No se encuentra el ID de la localizacion",error)
          })
        }).catch((error)=>{
          console.log("No se encuentra el ID de la DB Origen",error)
        })
      }).catch((error)=>{
        console.log("No se encuentra el ID de la DB Destino",error)
      })
      
    }else{
      return false
    }
  }

  /**
   * Get locations of localDB
   * @return {Array} The result of teh query.
   */
  /* No se usa nunca, devuelve un objeto raro y solo funciona con callbacks
  async getLocalLocations(){
    let db = this.connectionList["local"];
    let result = await db.all("SELECT * FROM Locations", (err, rows)=>{bueno = rows})
    console.log("HOLa",bueno)
    return result

  }
  */
  /**
   * Create local tables
   */
  async createLocalTables(){
    let db = this.connectionList["local"]

    db.run(`CREATE TABLE IF NOT EXISTS Area (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              Name VARCHAR(75),
              Latitude REAL,
              Longitude REAL);`)

    db.run(`CREATE TABLE IF NOT EXISTS Locations (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              Name VARCHAR(100) NOT NULL UNIQUE,
              Latitude REAL NOT NULL,
              Longitude REAL NOT NULL,
              Type VARCHAR(10),
              Area INTEGER,
              FOREIGN KEY(Area) REFERENCES Area(id) ON UPDATE CASCADE);`)
              
    db.run(`CREATE TABLE IF NOT EXISTS Dates (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              Date DATETIME NOT NULL);`)

              db.run(`CREATE TABLE IF NOT EXISTS CONNECTIONS (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                DBHost VARCHAR(255),
                DBName VARCHAR(255),
                DBPort INTEGER,
                DBUser VARCHAR(255),
                DBPassword VARCHAR(255),
                UNIQUE(DBHost, DBName)
            )`);

              db.run(`CREATE TABLE IF NOT EXISTS CORRELATIONS (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                DBOrigin INTEGER,
                DBDestination INTEGER,
                TableOrigin VARCHAR(255),
                TableDestination VARCHAR(255),
                ColumnOrigin VARCHAR(255),
                ColumnDestination VARCHAR(255),
                StartDate DATETIME,
                EndDate DATETIME,
                LastUpdate DATETIME,
                Coefficient REAL,
                Restrictions VARCHAR(255),
                Location INTEGER,
                Frecuency VARCHAR(255),
                UNIQUE(DBDestination, TableDestination,ColumnDestination,Location) ON CONFLICT REPLACE,
                FOREIGN KEY(DBOrigin) REFERENCES CONNECTIONS(id) ON UPDATE CASCADE,
                FOREIGN KEY(DBDestination) REFERENCES CONNECTIONS(id) ON UPDATE CASCADE,
                FOREIGN KEY(Location) REFERENCES Locations(id) ON UPDATE CASCADE
                )`);
              
              

  }
  async getDateIdFromInasolar(dateString) {
    // Define a regular expression to match the expected date string format.
    const regex = /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})$/;
    
    try {
      // Check if the date string matches the expected format and the connection is to the 'inasolar' database.
      if (regex.test(dateString)) {
        // Construct a SQL query to retrieve the ID of the specified date from the 'Dates' table.
        const query = `SELECT id FROM Dates WHERE Date = CAST('${dateString}' AS datetime)`;
        
        // Execute the query and store the result.
        let result = await this.executeQuery("inasolar", query);
        
        return result; // Return a promise that resolves with the array of results.
      }
    } catch (error) {
      console.log("Error in function:", error, dateString); // Log an error message if an error occurs.
      return undefined; // Return undefined in case of an error.
    }
  }

}
module.exports = Migrator;


//migrator = new Migrator()

//migrator.getDateIdFromInasolar("2023-10-25 00:00:00").then((e)=>{console.log(e.length)})


