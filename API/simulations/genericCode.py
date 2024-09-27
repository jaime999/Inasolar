from sqlalchemy import create_engine
from importlib import reload
from datetime import datetime
import pandas as pd
import urllib
import logging

class GenericCode:
    # FUNCIONES
    # ---------------------------------------------------------------
    
    def reloadLogger():
        return reload(logging)

    def selectDB(server, database, user, password):
        params = urllib.parse.quote_plus(
            'DRIVER={SQL Server};SERVER='+server+';DATABASE='+database+';UID='+user+';PWD=' + password)

        return create_engine("mssql+pyodbc:///?odbc_connect=%s" % params)     

    def formatDataTable(column):
        if isinstance(column, (int, float)):        
            return round(float(column), 2)
        return column

    def convertDate(date):
        date = pd.to_datetime(date)
        return date.dt.strftime('%Y-%m-%d %H:%M')
    
    def getAndParseDate(dateSql):
        maxDateAllowedSql = pd.read_sql(dateSql, GenericCode.engine)
        maxDateAllowed = datetime.strptime(
            str(maxDateAllowedSql['Date'].iloc[0]), '%Y-%m-%d %H:%M:%S')

        return maxDateAllowed.date()

    def generateParametersWithValue(parametersId, parametersValue):
        return {inputID['key']: inputValue for inputID, inputValue in zip(
            parametersId, parametersValue)}

    
    def getWeatherDateRanges(area):
        minHistoricalDate = pd.read_sql(f"select min(d.date) as DateMin from HistoricalWeather h, Dates d where d.id = h.date and h.Area = {area}",GenericCode.engine)
        maxForecastDate = pd.read_sql(f"select max(d.date) as DateMax from ForecastWeather f, Dates d where d.id = f.date and f.Area = {area}", GenericCode.engine)
                
        minDateAllowed = datetime.strptime(str(minHistoricalDate.iloc[0]['DateMin']), '%Y-%m-%d %H:%M:%S').date()
        maxDateAllowed = datetime.strptime(str(maxForecastDate.iloc[0]['DateMax']), '%Y-%m-%d %H:%M:%S').date()
        return minDateAllowed, maxDateAllowed
    
    def getPowerDateRange(area):
        powerRange = f"""select min(d.date) as DateMin, max(d.date) as DateMax from  Dates d, datosGEDER2 g, Locations l 
                            where d.id = g.date and l.Area = {area} and g.location = l.id  and l.Type = 'Consumer' """
        datesParsed = powerRange.iloc[0]
        maxDateAllowed = datetime.strptime(str(datesParsed['DateMax']), '%Y-%m-%d %H:%M:%S').date()
        minDateAllowed = datetime.strptime(str(datesParsed['DateMin']), '%Y-%m-%d %H:%M:%S').date()
        
        return minDateAllowed, maxDateAllowed

                            
    def getGenerationRange(area):
        generationRange = f"""select min(d.date) as DateMin, max(d.date) as DateMax from  Dates d, datosGEDER2 g, Locations l 
                            where d.id = g.date and l.Area = {area} and g.location = l.id  and l.Type = 'Generator' """
        datesParsed = generationRange.iloc[0]
        maxDateAllowed = datetime.strptime(str(datesParsed['DateMax']), '%Y-%m-%d %H:%M:%S').date()
        minDateAllowed = datetime.strptime(str(datesParsed['DateMin']), '%Y-%m-%d %H:%M:%S').date()
        
        return minDateAllowed, maxDateAllowed

    def convertToJSON(dataToConvert):
        return dataToConvert.to_json(orient='split', date_format='iso')
    
    def roundNumber(value, digitsRounded = 2):
        if isinstance(value, (int, float)):
            return round(float(value), digitsRounded)
        return value

    # VARIABLES
    # ---------------------------------------------------------------
    server = "158.42.22.107"
    database = "inasolar"
    user = "GEDER"
    password = "GEDER"
    engine = selectDB(server, database, user, password)
    MAX_DEMAND = int(pd.read_sql('SELECT MAX(Power) FROM datosGEDER2', engine).iloc[0].iloc[0])

    SIMILAR_DAYS_RESULT_COLUMNS_SQL = pd.read_sql(
    """SELECT nombre_dato, nombre_alternativo, unidad
       FROM descripcionDatos
       WHERE Tabla = 'SimilarDays'
       ORDER BY [Order] DESC""", engine)
    HISTORICAL_WEATHER_COLUMNS_SQL = pd.read_sql(
    """SELECT nombre_dato, nombre_alternativo, unidad, defaultMargin, defaultPonder
               FROM descripcionDatos
               WHERE Tabla = 'HistoricalWeather'""", engine)

