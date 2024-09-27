import datetime as dt
import pyodbc
from dotenv import dotenv_values

config = dotenv_values(".env")

def closeConnection(connection, cursor):
    cursor.close()
    connection.close()

    return None

def executeSQLServerQuery(connectionData, query):
    #connectionDataStructure ['id', 'DBHost', 'DBName', 'DBPort', 'DBUser', 'DBPassword']
    SERVER   = connectionData["DBHost"]
    DATABASE = connectionData["DBName"]
    PORT     = connectionData["DBPort"]
    USERNAME = connectionData["DBUser"]
    PASSWORD = connectionData["DBPassword"]

    try:
        conn = pyodbc.connect('DRIVER={SQL Server};SERVER=' + SERVER + ';PORT=' + str(PORT) + ';DATABASE=' + DATABASE + ';UID=' + USERNAME + ';PWD=' + PASSWORD + ';',timeout=5)
        cursor = conn.cursor()
        #cursor.execute(f"SELECT COLUMN_NAME FROM information_schema.columns WHERE table_name = '{table}' AND DATA_TYPE = 'datetime'")
        cursor.execute(query)
        if query.startswith("INSERT") or query.startswith("UPDATE"):
            cursor.commit()
            result = []
        else:
            result = cursor.fetchall()
        closeConnection(conn,cursor)
    except Exception as e:
        closeConnection(conn,cursor)
        raise e
    return result

def main():
    connectionData = {}
    connectionData["DBHost"] = config["DBHostLabder"]
    connectionData["DBName"] = config["DBNameLabder"]
    connectionData["DBPort"] = config["DBPortLabder"]
    connectionData["DBUser"] = config["DBUserLabder"]
    connectionData["DBPassword"] = config["DBPasswordLabder"]
    connectionDataInasolar = {}
    connectionDataInasolar["DBHost"] = config["DBHost"]
    connectionDataInasolar["DBName"] = config["DBName"]
    connectionDataInasolar["DBPort"] = config["DBPort"]
    connectionDataInasolar["DBUser"] = config["DBUser"]
    connectionDataInasolar["DBPassword"] = config["DBPassword"]

    results = executeSQLServerQuery(connectionData,"SELECT * FROM Weather")
    data_to_insert = []
    for result in results:
        if (result[0].minute >= 58 or result[0].minute <= 2):
            if result[0].minute >= 58:
                result[0] = result[0] + dt.timedelta(hours=1)
                                    
            result[0] = result[0].replace(minute = 0)
            result[0] = result[0].replace(second = 0)

            fecha_en_string = result[0].strftime("%Y-%m-%dT%H:%M:%S")
            query_id_fecha = f"SELECT id FROM DATES WHERE date = CAST('{fecha_en_string}' AS DATETIME)"
            try:
                id_fecha = executeSQLServerQuery(connectionDataInasolar,query_id_fecha)[0][0]
            except:
                print(query_id_fecha)
                break

            data_to_insert.append([id_fecha, result[8]])

    for row in data_to_insert:
        query = f"UPDATE HistoricalWeather SET windspeed_10m = {row[1]} where Area = 3 AND date = {row[0]} "
        try:
            executeSQLServerQuery(connectionDataInasolar,query)
        except Exception as e:
            print(e)
            print(query)
            continue

if __name__ == '__main__':
    main()
