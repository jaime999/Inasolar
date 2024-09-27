import numpy as np
import blowfish
import datetime as dt
import pyodbc

class SQLServerConnection():
    def __init__(self, host,port,dbname,dbuser,dbpass) -> None:
        self.dbhost = host
        self.port = port
        self.dbname = dbname
        self.dbuser = dbuser
        self.dbpass = dbpass
        self.datetimeCols = {}
        self.connect()

    def connect(self):
        self.conn = pyodbc.connect('DRIVER={SQL Server};SERVER=' + self.dbhost + ';PORT=' + str( self.port) + ';DATABASE=' + self.dbname + ';UID=' + self.dbuser + ';PWD=' + self.dbpass + ';',timeout=5)
        self.cursor = self.conn.cursor()
        
    def disconnect(self):
        self.cursor.close()
        self.conn.close()

    def query(self, query):
        self.cursor.execute(query)
        if query.startswith("INSERT") or query.startswith("UPDATE"):
            self.cursor.commit()
            result = []
        else:
            result = self.cursor.fetchall()
        return result
    
    def getDatetimeColumnsFromTablename(self, tableName):
        query = f"SELECT COLUMN_NAME FROM information_schema.columns WHERE table_name = '{tableName}' AND DATA_TYPE = 'datetime'"
        self.datetimeCols[tableName] =  self.query(query)
        return self.datetimeCols[tableName]
    
def getTasks():
    global inasolarConnection
    result = inasolarConnection.query("SELECT * FROM CORRELATIONS")
    return result

def getConnectionData(id=None):
    global inasolarConnection
    
    query = "SELECT * FROM CONNECTIONS"

    if id is not None:
        query += " WHERE id = " + str(id)

    result = inasolarConnection.query(query)

    return result

def decodePass(passw):
    cipher = blowfish.Cipher(b"superkeygeder")
    uint8 = np.uint8(passw.split(","))
    data_decrypted = b"".join(cipher.decrypt_ecb(uint8))
    #si la contraseña no es múltiplo de 8 bytes pone al final bytes no printeables, 32 < en la tabla ascii
    for i in range(0,len(data_decrypted)):
        if data_decrypted[i] < 32:
            break
    return(str(data_decrypted[:i],encoding="utf-8"))

def formatDateTime(date):
    return date.strftime('%Y-%m-%dT%H:%M:%S')

def main():
    global inasolarConnection
    tasks = getTasks()
    for task in tasks:
        DBDestinationData = getConnectionData(id = task[2])[0]
        if DBDestinationData[2] == "inasolar": #solo si el destino es inasolar, por si acaso
            #Conectamos con origen
            DBOriginData = getConnectionData(id = task[1])[0]
            DBOrigin = SQLServerConnection(host=DBOriginData[1],port=DBOriginData[3],dbname=DBOriginData[2],dbuser=DBOriginData[4],dbpass=decodePass(DBOriginData[5]))
            
            #Conectamos con el destino
            DBDestination = SQLServerConnection(host=DBDestinationData[1],port=DBDestinationData[3],dbname=DBDestinationData[2],dbuser=DBDestinationData[4],dbpass=decodePass(DBDestinationData[5]))
            
            #necesitamos la columna fecha del origen
            originTable = task[3]
            originColumn = task[5]
            originDatetimeColumn  = DBOrigin.getDatetimeColumnsFromTablename(originTable)[0][0] #cogemos la primera solo

            destinationTable = task[4]
            destinationColumn = task[6]

            location = task[12]

            #Una vez la tenemos, cogemos los datos que sean mayores a la fecha de la última update
            lastUpdate = task[9]    
            startDate = task[7]
            endDate = task[8]
            coefficient = round(task[10],6)

            #Añadimos a la fecha la letra 'T' para que no haya problemas con SQLSERVER
            originQuery = f"""SELECT [{originColumn}],[{originDatetimeColumn}] FROM {originTable} WHERE {originDatetimeColumn} >= CAST('{formatDateTime(lastUpdate)}' as datetime) 
                AND {originDatetimeColumn} >= CAST('{formatDateTime(startDate)}' as datetime) AND {originDatetimeColumn} <= CAST('{formatDateTime(endDate)}' as datetime)"""

            dataToImport = DBOrigin.query(originQuery)
            print(len(dataToImport))

            dataToInsert = []
            for row in dataToImport:
                data = row[0]
                date = row[1]
                #Si los minutos son 58,59,00,01,02 redondeamos a minuto 0
                if (date.minute >= 58 or date.minute <= 2) and lastUpdate <= date:
                    #Si minuto >= 58 sumamos una hora y luego truncamos minutos y segundos
                    if date.minute >= 58:
                        date = date + dt.timedelta(hours=1)

                    #Hacemos hora exacta
                    date = date.replace(minute = 0)
                    date = date.replace(second = 0)

                    #necesitamos el Id de la fecha para INASOLAR
                    query = f"SELECT id FROM DATES WHERE date = CAST('{date.strftime('%Y-%m-%dT%H:%M:%S')}' AS DATETIME)"
                    try:
                        inasolar_date_id = inasolarConnection.query(query)[0][0]
                    except Exception as e:
                        print(e)
                        continue
                    
                    #si el dato a insertar no es un string, multiplicamos por el coeficiente
                    if not str(data).isalpha():
                        data = data * coefficient

                    
                    try:
                        insert = f"INSERT INTO {destinationTable}([{destinationColumn}], location, date) VALUES ({data},{location},{inasolar_date_id})"
                        DBDestination.query(insert)
                        updatedAt = date
                        #print("INSERT: ",insert)
                    except Exception as error:
                        update = f"UPDATE {destinationTable} set [{destinationColumn}] = {data} WHERE location = {location} and date = {inasolar_date_id}"
                        DBDestination.query(update)
                        #print("UPDATE: ",update)
                        updatedAt = date

                        
                    dataToInsert.append([data,date,inasolar_date_id])
            lastUpdate = updatedAt.strftime('%Y-%m-%dT%H:%M:%S')

            print(len(dataToInsert),inasolar_date_id,dataToInsert[0])
            #registrar last update
            inasolarConnection.query(f"UPDATE CORRELATIONS SET LastUpdate = CAST('{lastUpdate}' as datetime) where id = {task[0]}")
            print(f"UPDATE CORRELATIONS SET LastUpdate = CAST('{lastUpdate}' as datetime) where id = {task[0]}")
            #Cerramos conexiones
            DBOrigin.disconnect()
            DBDestination.disconnect()

if __name__ == '__main__':
    global inasolarConnection
    inasolarConnection = SQLServerConnection("158.42.22.107",1433,"inasolar","GEDER","GEDER") 
    main()
    inasolarConnection.disconnect()