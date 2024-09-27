import pyodbc
import datetime as dt
from dotenv import dotenv_values

class SQLServerConnection():
    def __init__(self) -> None:
        self.config = dotenv_values(".env")
        self.dbhost = self.config["DBHost"]
        self.port   = self.config["DBPort"]
        self.dbname = self.config["DBName"]
        self.dbuser = self.config["DBUser"]
        self.dbpass = self.config["DBPassword"]
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
    


def main():
    global inasolarConnection
    #fecha a partir de la cual no hay datos (redondeada)
    now = dt.datetime.now()
    start_date = dt.datetime(year=now.year,month=now.month,day=now.day) - dt.timedelta(days=30)
    end_date = dt.datetime(year=now.year,month=now.month,day=now.day)

    #Consultamos los datos meteorologico
    meteo_query = f"SELECT  h.direct_radiation, d.id from Dates d, HistoricalWeather h where h.Area = 1 and h.date = d.id and d.date >=CAST('{start_date.strftime('%Y-%m-%dT%H:%M:%S')}' as datetime) order by d.date asc" 
    print(meteo_query)
    meteo_data = inasolarConnection.query(meteo_query)

    #Consultamos los ids de los generadores
    locations_query = "SELECT id from Locations where Area = 1 and type='Generator'"
    location_data = inasolarConnection.query(locations_query)

    current_hour_index = 0
    #rellenamos genracion a partir de 2023
    while start_date < end_date and  current_hour_index < len(meteo_data):
        direct_radiation = -1 * min(meteo_data[current_hour_index][0] * 0.02515457,20) 
        print(start_date,direct_radiation)
        for farm in location_data:
            id_farm = farm[0]
            insert_query = f"INSERT INTO datosGEDER2(date,Power,Demanda,location) VALUES ({meteo_data[current_hour_index][1]},{direct_radiation},{direct_radiation},{id_farm})"
            try:
                inasolarConnection.query(insert_query)
            except:
                update_query = f"UPDATE datosGEDER2 set Power = {direct_radiation}, Demanda ={direct_radiation} where location ={id_farm} and date={meteo_data[current_hour_index][1]}"
                inasolarConnection.query(update_query)
        start_date = start_date + dt.timedelta(hours=1)
        current_hour_index += 1
        
if __name__ == '__main__':
    global inasolarConnection
    inasolarConnection = SQLServerConnection() 
    main()
    inasolarConnection.disconnect()
