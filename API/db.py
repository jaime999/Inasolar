import pymssql
import datetime as dt
from fastapi import HTTPException,status
from dependencies import Cache
import sys

class SQLdriver:

    def __init__(self) -> None:
        #self.connect()
        self.cache = Cache()

    def connect(self,as_dict=True):
        self.conn = pymssql.connect("158.42.22.107", "GEDER", "GEDER", "inasolar")
        self.cursor = self.conn.cursor(as_dict=as_dict)
        
    def disconnect(self):
        self.cursor.close()
        self.conn.close()
        
    def SQLSelect(self, query,params=None,as_dict=True):
        self.connect(as_dict=as_dict)

        if params is None:
            self.cursor.execute(query)
        else:
            self.cursor.execute(query,params)
        result = self.cursor.fetchall()
        self.disconnect()
        return result
        

    def CHECKTableIsAvailable(self,tablename):
        #Si esta en cache
        result = self.cache.getCachedResult("ExistsTable"+tablename)
        if result is not None:
            return result
        
        #Si no esta en cache
        available_tables = self.GETTableDescriptions()
        for i in available_tables:
            if i["TableId"] == tablename:
                self.cache.setResult("ExistsTable"+tablename, True)
                return True
        self.cache.setResult("ExistsTable"+tablename, False)
        return False
    
    def CHECKColumnIsAvailable(self,tablename,columname):
        #Si esta en cache
        result = self.cache.getCachedResult("ExistsColumn"+tablename+columname)
        if result is not None:
            return result 

        available_columns = self.GETColumnDescriptions(tablename)
        
        for i in available_columns:
            if i["nombre_dato"] == columname:
                self.cache.setResult("ExistsColumn"+tablename+columname, True)
                return True
        self.cache.setResult("ExistsColumn"+tablename+columname, False)
        return False
    
    def makeGenericQuery(self,column_1,table_1,start_date,end_date,location_id,area=None):

        query = f"""SELECT {column_1} ,d.date FROM {table_1} a, Dates d WHERE d.id = a.date 
                                 AND d.Date >= CAST('{start_date}' AS DATETIME) AND d.Date <= CAST('{end_date}' AS DATETIME)"""
        if table_1 != 'datosGEDER2':
            query +=  f" AND Area = {area}"
        else: 
            query +=  f" AND a.location = {location_id}"
        query += " ORDER BY d.Date ASC"
        return query
    
    def getColumnAlternativeName(self,column):
        #Si esta en cache
        result = self.cache.getCachedResult("ColumnAlternativeName"+column)
        if result is not None:
            return result
        
        column_info = self.SQLSelect(f"SELECT d.nombre_alternativo,unidad FROM descripcionDatos d WHERE d.nombre_dato = '{column}'")
        self.cache.setResult("ColumnAlternativeName",f"{column_info[0]['nombre_alternativo']} ({column_info[0]['unidad'].strip()})")
        return f"{column_info[0]['nombre_alternativo']} ({column_info[0]['unidad'].strip()})"

    def CHECKLocationID(self, location_id):
        #Si esta en cache
        result = self.cache.getCachedResult("Location"+str(location_id))
        if result is not None:
            return result
        
        locations = self.GETLocations()
        for i in locations:
            if i["id"] == location_id:
                self.cache.setResult("Location"+str(location_id),True)
                return True
        self.cache.setResult("Location"+str(location_id),False)
        return False
    
    def GETLocations(self, id :int = None ):
        #Si esta en cache
        result = self.cache.getCachedResult("Locations"+str(id))
        if result is not None:
            return result
        
        if id is None:
            result = self.SQLSelect("SELECT *,(SELECT max(Power) FROM datosGEDER2 g where g.location=l.id) as MaxDemand FROM Locations l")
        else:
            result = self.SQLSelect(f"SELECT *,(SELECT max(Power) FROM datosGEDER2 g WHERE g.location = {id}) as MaxDemand FROM Locations WHERE id = {id}")
            
        self.cache.setResult("Locations"+str(id),result)
        return result
    
    def GETAreas(self):
        #Si esta en cache
        result = self.cache.getCachedResult("Areas")
        if result is not None:
            return result
        
        result = self.SQLSelect("SELECT * FROM Area")
        self.cache.setResult("AREAS",result)
        return result
    
    def GETTableDescriptions(self):
        #Si esta en cache
        result = self.cache.getCachedResult("TableDescriptions")
        if result is not None:
            return result
        
        result = self.SQLSelect("SELECT TableId,TableName FROM TableDescriptions")
        self.cache.setResult("TableDescriptions",result)
        return result
    
    def GETColumnDescriptions(self,table_name):
        #Si esta en cache
        result = self.cache.getCachedResult("ColumnDescriptions"+str(table_name))
        if result is not None:
            return result
        
        columns = ["nombre_dato","nombre_alternativo","descripcion","unidad","defaultMargin","defaultPonder","tabla"]
        if table_name is None:
            result = self.SQLSelect(f"SELECT {', '.join(columns)} FROM DescripcionDatos")
        else:
            result = self.SQLSelect(f"SELECT {', '.join(columns)} FROM DescripcionDatos WHERE tabla=%s",(table_name))
        self.cache.setResult("ColumnDescriptions"+str(table_name),result)
        return result
    
    def GETElectricityPrice(self,start_date, end_date):
        result = self.SQLSelect(f"""SELECT Price, Surplus, d.Date as date FROM ElectricityPrice e, Dates d 
                                WHERE e.date = d.id AND d.date >= CAST('{start_date}' as datetime) AND d.date <= CAST('{end_date}' as datetime) """)
        return result

    def GETHistoricalWeather(self,start_date, end_date, area):
        historical_columns = ["h.id","temperature_2m","relativehumidity_2m","surface_pressure","precipitation","snowfall","cloudcover","direct_radiation","windspeed_10m","winddirection_10m"]
        result = self.SQLSelect(f"""SELECT {', h.'.join(historical_columns)}, d.Date as date 
                                FROM HistoricalWeather h, Dates d 
                                WHERE h.date = d.id AND d.date >= CAST('{start_date}' as datetime) AND d.date <= CAST('{end_date}' as datetime) 
                                AND h.area = %s""",(area))
        

        return result

    def GETElectricData(self,start_date, end_date, location):
        result = self.SQLSelect(f"""SELECT g.*,d.Date FROM datosGEDER2 g, Dates d 
                                WHERE g.date = d.id AND d.date >= CAST('{start_date}' as datetime) AND d.date <= CAST('{end_date}' as datetime) 
                                AND g.location = %s""",(location))
        return result
        
    def GETHolidayData(self,target_date,location_id):
        result = self.SQLSelect(f"""SELECT h.* FROM Holidays h, Dates d 
                                WHERE h.date = d.id AND d.date = CAST('{target_date}' as datetime)
                                AND h.location = %s""",(location_id))
        return result
    
    def getAreaByLocationID(self, location_id):
        #Si esta en cache
        result = self.cache.getCachedResult("LocationArea"+str(location_id))
        if result is not None:
            return result
        
        locations = self.GETLocations()
        for i in locations:
            if i["id"] == location_id:
                self.cache.setResult("LocationArea"+str(location_id),i["Area"])
                return i["Area"]
        self.cache.setResult("LocationArea"+str(location_id),None)

        return None

    def getGenericData(self,start_date,end_date,location_id,table_1,table_2,column_1,column_2):

        area = None
        if table_1 != 'datosGEDER2' or table_2 != 'datosGEDER2':
            area = self.getAreaByLocationID(location_id)

        dates = self.SQLSelect("SELECT Date FROM Dates where Date >= CAST(%s AS DATETIME) AND Date <= CAST(%s AS DATETIME) ORDER BY DATE ASC",(start_date,end_date),as_dict=False)
    
        dates = [date[0] for date in dates]

        query = self.makeGenericQuery(column_1,table_1,start_date,end_date,location_id,area=area,) 
        result1 = self.SQLSelect(query,as_dict=False)
        result1 = [item for sublist in result1 for item in sublist]

        query = self.makeGenericQuery(column_2,table_2,start_date,end_date,location_id,area=area,)
        result2 = self.SQLSelect(query,as_dict=False)
        result2 = [item for sublist in result2 for item in sublist]
        
        pointer = 0
        pointer1 = 1
        pointer2 = 1
        result1_aux = []
        result2_aux = []
        while pointer < len(dates):
            if len(result1) >= pointer1 and result1[pointer1] == dates[pointer]:
                result1_aux.append(result1[pointer1-1])
                pointer1 += 2
            else:
                result1_aux.append(None)
            if len(result2) >= pointer2 and result2[pointer2] == dates[pointer]:
                result2_aux.append(result2[pointer2-1])
                pointer2 += 2
            else:
                result2_aux.append(None)
            pointer += 1
        column_1_alternative_name = self.getColumnAlternativeName(column_1)
        column_2_alternative_name = self.getColumnAlternativeName(column_2)
    
        return [{"name":column_1_alternative_name,"data":result1_aux},{"name":column_2_alternative_name,"data":result2_aux}], dates
   
    def getTargetDaySummary(self,date,location_id, weather_table="HistoricalWeather"):
        TYPE_OF_DAYS = {'newYear': 'New Year',
                'localHoliday': 'Local Holiday',
                'nationalHoliday': 'National Holiday',
                'festivities': 'Festivities',
                'weekEnd': 'Weekend',
                'weekDay': 'Week Day'}
        column_descriptions = self.GETColumnDescriptions("HistoricalWeather")
        area = self.getAreaByLocationID(location_id)
        date = dt.datetime.strptime(date, '%Y-%m-%dT%H:%M:%S').date()

        data = {"Date":date.strftime("%Y-%m-%d")}

        query = f"""SELECT h.type_of_holiday as type, h.newYear, h.localHoliday,h.nationalHoliday,h.festivities,h.weekEnd,weekDay 
        FROM Holidays h, Dates d WHERE d.id=h.date AND h.Location = %d AND d.Date = CAST(%s as datetime)"""
        result = self.SQLSelect(query,(location_id,date.strftime('%Y-%m-%dT%H:%M:%S')))
        if len(result) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No holiday data from target day",
            )
        category = {
                'new_year': result[0]["newYear"],
                'local_holiday': result[0]["localHoliday"],
                'national_holiday': result[0]["nationalHoliday"],
                'festivities': result[0]["festivities"],
                'weekend': result[0]["weekEnd"],
                'week_day': result[0]["weekDay"]
        }
        data["TypeOfDay"] =  result[0]["type"]
        if weather_table == 'HistoricalWeather':
            query = f"SELECT AVG(g.Power) as avg, count(*) as hours FROM datosGEDER2 g, Dates d WHERE d.id=g.date AND g.Location = %d AND d.Year = %d AND d.Month = %d AND d.Day = %d"
            result = self.SQLSelect(query,(location_id,date.year,date.month,date.day))
            data["Power(kW)"] = result[0]["avg"]
            if result[0]["hours"] != 24:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Hours missing in target day",
                )

        for column in column_descriptions:
            query = f"SELECT AVG(h.{column['nombre_dato']}) as avg FROM {weather_table} h, Dates d WHERE d.id=h.date AND h.Area = {area} AND d.Year = {date.year} AND d.Month = {date.month} AND d.Day = {date.day}"
            result = self.SQLSelect(query)
            data[column['nombre_alternativo'] + f"({column['unidad'].strip()})"]= result[0]["avg"]
        return data,category