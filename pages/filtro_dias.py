# -*- coding: utf-8 -*-
"""
Created on Fri Feb  3 11:14:22 2023

@author: Victor
"""
import pandas as pd
import dateutil.parser as parser
import numpy as np
from datetime import datetime, timedelta
from .genericCode import GenericCode


# Funciones principales para obtener información de las fechas
# ---------------------------------------------------------------
class filtro_dias:
    def fixIntervalDates(rangeData):
        rangeData = rangeData.sort_values(by='Date')        
    
        # La columna Hour esta duplicada por comodidad, pero a la hora de dibujar el grafico da problemas, la quitamos
        # https://stackoverflow.com/questions/14984119/python-pandas-remove-duplicate-columns
        rangeData = rangeData.loc[:, ~rangeData.columns.duplicated()].copy()
        
        rangeData = filtro_dias.fixData(rangeData, ['Date', 'date', 'Area'])
        # RENOMBRAMOS Fecha por Date
        return rangeData.rename(columns={'Fecha': 'Date'})
        
    def calculatePowerDistance(objectiveDay, similarDays):
        #Se itera en las 24 horas de cada día
        for hour in range(24):
            objectiveDay_hour = objectiveDay[objectiveDay['Hour'] == hour]
            actualHour = similarDays['Hour'] == hour
            similarDays_hour = similarDays[actualHour]
            
            # Calcula la diferencia de Power en cada hora
            powerDiff = abs(objectiveDay_hour['Power'].values - similarDays_hour['Power'].values)
            
            # Añade la columna powerDiff a similarDays
            similarDays.loc[actualHour, 'PowerDiff'] = powerDiff
            
        return similarDays
    
    def getRangeAndObjectiveDay(targetDate, startDate, endDate, location):
        # PARSEAMOS LA FECHA A DATETIME
        targetDate = parser.parse(targetDate)
    
        startDate, endDate = filtro_dias.parseDates(startDate, endDate)
        day_data = pd.read_sql(f"""SELECT d.Hour, CONVERT(varchar(10), d.Date, 23) AS Fecha, h.*, d.*,g.Power, ho.*
                                   FROM datosGEDER2 g, HistoricalWeather h, Dates d, Holidays ho,Locations l
                                   WHERE l.Area = h.Area AND g.date = d.id AND d.id = ho.date AND d.id = h.date
                                   AND l.id ={location} AND ho.Area = l.Area AND g.location = {location}
                                   AND (d.Date >= CONVERT(DATETIME, '{startDate}', 102) AND d.Date <= CONVERT(DATETIME, '{endDate}', 102)
                                   OR (Year = {targetDate.year} AND Month = {targetDate.month} AND Day = {targetDate.day}))
                                   ORDER BY CONCAT(Year,'-',Month,'-',Day), d.Hour """, GenericCode.engine)
        
        rangeData = filtro_dias.fixIntervalDates(day_data)        
        objective_day = rangeData.query(
            f"Year == {targetDate.year} and Month == {targetDate.month} and Day == {targetDate.day} ")
        
        return rangeData, objective_day, targetDate
    
    
    def calculateTable(similarDaysGrouped):
        # Define las operaciones a aplicar a cada columna
        operationsSql = pd.read_sql("""SELECT * FROM SimilarDaysParameters""", GenericCode.engine)
        paramOperations = operationsSql.set_index('ParameterId')['Operation'].to_dict()
    
        # Aplica las operaciones a las columnas de SimilarDays
        return similarDaysGrouped.agg(paramOperations)
    
    
    def get_days_by_similar_meteorological_variables_margins(date="2022-10-18T21:00:00", margins={"temperature_2m": 2, "cloudcover": 50, "direct_radiation": 100,
                                                     "relativehumidity_2m": 50, "surface_pressure": 1000, "precipitation": 100,
                                                                                                  "snowfall": 100, "windspeed_10m": 50, "winddirection_10m": 360},
                                                     fecha_ini="2018-01-01", fecha_fin="2100-01-01", location={'Location': 1, 'Area': 1},
                                                     typeOfDays={'newYear': True, 'localHoliday': True,
                                                                 'nationalHoliday': True, 'festivities': True,
                                                                 'weekEnd': True, 'weekDay': True}):
        rangeDates, objective_day, targetDate = filtro_dias.getRangeAndObjectiveDay(date, fecha_ini, fecha_fin, location['Location'])
        if filtro_dias.hoursMissing(objective_day):
            return {'errorMessage': 'Hours missing in target date'}
        
        query = filtro_dias.getSimilarDaysByMargins(margins, objective_day, typeOfDays)
        
        # AÑADIMOS LOS TIPOS DE DIAS
        # Si en los días devueltos no se encuentra el target (porque los tipos de días seleccionados no concuerdan con su tipo)
        # se añade manualmente
        query += f"| (Date == '{targetDate.date()}')"
    
        similar_days = filtro_dias.getSimilarDaysByTargetDate(rangeDates, objective_day, query)
        similar_days = filtro_dias.calculatePowerDistance(objective_day, similar_days)
        
        return similar_days
    
    
    def get_days_by_similar_meteorological_variables_ponders(date = "2022-01-01T21:00:00", ponders = [0.2,0.1,0.2,0,0,0.1,0.2,0,0],
                                                         location = 1, 
                                                         initial_date = "2018-01-01", final_date = "2100-01-01",
                                                         num_days=20):

        rangeDates, objective_day, targetDate = filtro_dias.getRangeAndObjectiveDay(date, initial_date, final_date, location)
        if filtro_dias.hoursMissing(objective_day):
            return {'errorMessage': 'Hours missing in target date'}
        
        return filtro_dias.getSimilarDaysByPonders(rangeDates, objective_day, ponders, num_days)

    def getSimilarDaysByPonders(rangeData, objective_day, ponders, num_days):
        # Mismo tipo de dia
        # if type_of_holiday:
        #    day_data = day_data.query(f'type_of_holiday == "{objective_day.values[0][-1]}"')
        #Calculamos errores/distancias
        errors = []        
        
        # Se calculan las distancias de cada cada día en cada variable con respecto al día objetivo
        for hour in rangeData.values:
            #hour[0] == es una hora determinada, por ejemplo: 22
            #columnas de la 3 a la 12 corresponden con las variables meteorológicas
            try:
                errors.append(list(map(lambda x, y: abs(y-x) , hour[3:12], objective_day.values[hour[0]][3:12])))
            except Exception as e:
                return {'errorMessage': f"Error: {e}"}, None                        
        
        #Añadimos las distancias como columnas con nombre incluido
        for i in range(len(rangeData.columns[3:12])):
            rangeData[rangeData.columns[3:12][i]+'_distance'] = list(map(lambda x: x[i],errors)) #Hay que hacerlo asi porque errors es multidimensional  
       
        #Cogemos un dia entero(todas las horas) y sumamos las distancias de las diferentes variables
        
        #HAY DIAS INCOMPLETOS CUIDADO! DIAS CON MENOS HORAS PUDEN TENER MENOS DISTANCIA SUMADA Y TENER MEJOR NOTA DE LA QUE DEBERIAN
        complete_days = rangeData.groupby(by="Date")['Hour'].size()
        complete_days = complete_days[complete_days == 24].index
        rangeData = rangeData[rangeData['Date'].isin(complete_days)]
        
        #Calculamos distancias
        distance_sums = rangeData.groupby(by="Date",as_index=False).sum(numeric_only=True)
        columns_name_score = []
        # Calculamos la nota sobre 100
        for i in range(len(rangeData.columns[3:12])):
            column_name = rangeData.columns[3:12][i]+'_distance'
            columns_name_score.append('score_'+column_name)
            minimum = min(distance_sums[column_name])  # mínimo = nota 100
            maximum = max(distance_sums[column_name])  # máximo = nota 0
            # cálculo de nota alternativa (no lineal)
            # f(x)=-((100)/(500^(2))) x^(2)+100
            #distance_sums['score_temp'] = list(map(lambda x: ((-1)*((100-minimum)/pow(maximum,2))*pow(x,2))+(100-minimum) ,distance_sums['temperature_2m_distance']))
            maxScore = 100
            if minimum == maximum:
                distance_sums['score_'+column_name] = list(map(lambda x: ponders[i]*maxScore ,distance_sums[column_name].values))
            
            else:
                distance_sums['score_'+column_name] = list(map(lambda x: ponders[i]*((x*(-1*(maxScore-minimum)/maximum))+(maxScore-minimum)) ,distance_sums[column_name].values))
    
        #Sumamos todas las notas (las últimas 9 columnas)
        distance_sums['score_final'] = distance_sums[columns_name_score].sum(axis=1)
        
        #Cogemos las 20 mejores notas por defecto
        best_days = distance_sums.query("Power != 0") # quitamos dias incompletos (rellena los nulos/NaN con 0)
        best_days = best_days.sort_values(by="score_final", ascending = False)[:num_days]
    
        return best_days.loc[:, ['Date', 'score_final']], rangeData
    
    
    def getSimilarDaysByMargins(margins, objective_day, typeOfDays):
        typeOfDaysQuery = []
        for key in typeOfDays:
            if typeOfDays[key]:
                typeOfDaysQuery.append(f"{key} == True")
    
        # ITERAMOS SOBRE LOS MARGENES PARA AÑADIRLOS A LA CONSULTA
        query = ''
        # PILLAMOS LAS MEDIAS DEL DIA OBJETIVO
        objetive_day_mean = objective_day.mean(numeric_only=True)
        for key in margins.keys():
            query += f" {key} >=  {float(objetive_day_mean[key])-float(margins[key])} & {key} <=  {float(objetive_day_mean[key])+float(margins[key])} &"
    
        # AÑADIMOS LOS TIPOS DE DIAS
        # Si en los días devueltos no se encuentra el target (porque los tipos de días seleccionados no concuerdan con su tipo)
        # se añade manualmente
        query += f") & ({'' if not typeOfDaysQuery else ' | '.join(typeOfDaysQuery)})"
        
        # QUITAMOS UNA COSA FEA DEL STRING
        query = query.replace('&)', '')
        
        return query
    
    
    def getSimilarDaysByTargetDate(day_data, objective_day, query):            
        # AGRUPAMOS LOS DIAS POR FECHA Y MEDIA
        day_data2 = day_data.groupby(
            by='Date', as_index=False).mean(numeric_only=True)
    
        # QUITAMOS UNA COSA FEA DEL STRING
        query = query.replace('&)', '')
        
        # HACEMOS LA CONSULTA Y COGEMOS LAS FECHAS SIMILARES
        similar_days = day_data2.query(query)
        # COGEMOS LAS HORAS DEL DATAFRAME ORIGINAL CUYAS FECHAS COINCIDAN CON SIMILAR_DAYS
        similar_days = day_data[day_data['Date'].isin(similar_days['Date'].values)]
    
        return similar_days
    
    
    def getSimilarDaysByHours(best_days, day_data, targetDate):
        similar_days = day_data[day_data['Date'].isin(best_days['Date'].values)]
        objective_day = similar_days[similar_days['Date'] == targetDate]
        similar_days = filtro_dias.calculatePowerDistance(objective_day, similar_days)
        
        return similar_days
    
    
    def getDateInfoHistoricalWeather(date, locationData):
        # PARSEAMOS LA FECHA A DATETIME
        date = parser.parse(date)
        dateInfoByHourSql = pd.read_sql("""SELECT d.Hour, CONVERT(varchar(10), d.Date, 23) AS Date, h.*, datos.Power
                                            FROM Dates d
                                            INNER JOIN HistoricalWeather h ON d.id = h.date
                                            INNER JOIN datosGEDER2 datos ON datos.date = d.id
                                            WHERE d.Year = ? AND d.Month = ?
                                            AND d.Day = ?
                                            AND h.Area = ?
                                            AND datos.location = ?""", GenericCode.engine,
                                        params=(date.year, date.month, date.day, locationData['Area'], locationData['Location']))
        dateInfoByHourSql = filtro_dias.fixData(
            dateInfoByHourSql, ['id', 'date', 'Area', 'Hour'])
    
        return dateInfoByHourSql.groupby(by='Date', as_index=False).mean(numeric_only=True)
    
    
    def getDateInfoForecastWeather(startDate, endDate, locationData):
        # PARSEAMOS LA FECHA A DATETIME
        endDate = parser.parse(endDate) + timedelta(days=1)
        endDate = endDate.strftime("%Y-%m-%d")
        dateInfoByHourSql = pd.read_sql("""SELECT d.Hour, CONVERT(varchar(10), d.Date, 23) AS Date, h.*
                               FROM ForecastWeather h, Dates d, Holidays ho,Locations l
                               WHERE l.Area = h.Area AND d.id = ho.date AND d.id = h.date
                               AND l.id = ? AND ho.Area = l.Area
                               AND (d.Date >= CONVERT(DATETIME, ?, 102) AND d.Date < CONVERT(DATETIME, ?, 102))
                               ORDER BY CONCAT(Year,'-',Month,'-',Day), d.Hour""", GenericCode.engine,
                                        params=(locationData['Location'], startDate, endDate))
        dateInfoByHourSql = filtro_dias.fixData(
            dateInfoByHourSql, ['id', 'date', 'Area', 'Hour'])
    
        return dateInfoByHourSql.groupby(by='Date', as_index=False).mean(numeric_only=True)
    
    def calculateNormalizedScore(results, pondersLimit):
        scoreLimit = 10
        for result in results:
            # Se hace esta comprobación para evitar la división entre 0
            if pondersLimit != 0:
                # Se redondea la nota a 3 decimales para mayor precisión
                result['Score'] = GenericCode.roundNumber((result['Distance'] * scoreLimit)  / pondersLimit, 3)
                result['ScoreWR'] = GenericCode.roundNumber((result['DistanceWR'] * scoreLimit)  / pondersLimit, 3)
                
            else:
                result['Score'] = scoreLimit
                result['ScoreWR'] = scoreLimit
                    
        return results
    
    def calculateOptimizationDistances(maxValue, resultParameter, minValue, sos):
        # Se hace esta comprobación para evitar la división entre 0
        if maxValue != minValue:
            if not sos:
                # Se da una puntuación entre 0 y 1 al valor que más se acerque al mínimo
                return (maxValue - abs(resultParameter))/(maxValue - minValue)
            
            else: 
                # En caso de SoS, se da una puntuación entre 0 y 1 al que más se acerque a 50%
                return 1 - ((abs(resultParameter - 50))/50)
                    
        else:
            return 1
        
    def getScore(results, ponders):
        minValuesNoWR, minValuesWR, maxValuesNoWR, maxValuesWR = {}, {}, {}, {}
        # Se calculan los mínimos y máximos de entre todos los escenarios    
        for parameter in ponders.keys():
            minValuesNoWR[parameter] = np.inf
            minValuesWR[f'{parameter}WR'] = np.inf
            maxValuesNoWR[parameter] = 0
            maxValuesWR[f'{parameter}WR'] = 0
            if parameter != 'sosBiogas' and parameter != 'sosWaterTank':        
                for result in results:
                    # Se compara en cada escenario el valor actual máximo y mínimo, con el valor absoluto del escenario
                    # En caso de que sea necesario, se actualiza el valor
                    absParameterNoWR = abs(result[parameter])
                    absParameterWR = abs(result[f'{parameter}WR'])
                                         
                    minValuesNoWR[parameter] = min(minValuesNoWR[parameter], absParameterNoWR)
                    minValuesWR[f'{parameter}WR'] = min(minValuesWR[f'{parameter}WR'], absParameterWR)
                    maxValuesNoWR[parameter] = max(maxValuesNoWR[parameter], absParameterNoWR)
                    maxValuesWR[f'{parameter}WR'] = max(maxValuesWR[f'{parameter}WR'], absParameterWR)
                        
        pondersLimit = 0
        
        # Se calculan las distancias de todos los escenarios a el mínimo (excepto en SoS que se busca lo más cercano a 50)
        for parameter, ponder in ponders.items():
            maxValueNoWR = maxValuesNoWR[parameter]
            maxValueWR = maxValuesWR[f'{parameter}WR']
            minValueNoWR = minValuesNoWR[parameter]
            minValueWR = minValuesWR[f'{parameter}WR']
            distanceNoWR = 'Distance'
            distanceWR = 'DistanceWR'
            sos = parameter == 'sosBiogas' or parameter == 'sosWaterTank'        
            for result in results:
                # En la primera iteración se inicializa a 0 las distancias para que no de error
                if pondersLimit == 0:
                    result[distanceNoWR] = 0
                    result[distanceWR] = 0
                
                # Se calcula la distancia al mínimo de cada parámetro a evaluar
                resultNoWR = filtro_dias.calculateOptimizationDistances(maxValueNoWR, result[parameter], minValueNoWR, sos)
                resultWR = filtro_dias.calculateOptimizationDistances(maxValueWR, result[f'{parameter}WR'], minValueWR, sos)
                
                # Por último, se aplica el ponder a la distancia
                result[distanceNoWR] += resultNoWR * ponder
                result[distanceWR] += resultWR * ponder
            
            # Se suma el ponder para obtener la máxima nota que podría tener
            pondersLimit += abs(ponder)
        
        # Se normaliza la nota sobre 10         
        results = filtro_dias.calculateNormalizedScore(results, pondersLimit)
            
        return results
    
    # Functiones de apoyo para las funciones principales
    # ---------------------------------------------------------------
    
    
    def fixData(dateInfoByHourSql, unusefulColumns):
        # QUITAMOS NUBES POR LA NOCHE(son irrelevantes)
        dateInfoByHourSql.loc[dateInfoByHourSql['Hour'] < 9, 'cloudcover'] = 0
        dateInfoByHourSql.loc[dateInfoByHourSql['Hour'] > 18, 'cloudcover'] = 0
    
        # Quitamos la columnas que no nos sirven
        dateInfoByHourSql = dateInfoByHourSql.drop(unusefulColumns, axis=1)
    
        return dateInfoByHourSql
    
    
    def parseDates(startDate, endDate):
        return datetime.strptime(startDate, "%Y-%m-%d"), datetime.strptime(
            endDate, "%Y-%m-%d") + timedelta(hours=23)
    
    
    def hoursMissing(objective_day):
        return len(objective_day) != 24
    
    
    def calculateBounds(similarDays, lowQuantile, uppQuantile):
        q1 = []
        median = []
        q3 = []
        lowerfence = []
        upperfence = []
    
        for hour in range(24):
            hourData = similarDays.loc[similarDays['Hour'] == hour, 'Power']
            q1.append(GenericCode.roundNumber(np.percentile(hourData, lowQuantile))),
            median.append(GenericCode.roundNumber(np.percentile(hourData, 50))),
            q3.append(GenericCode.roundNumber(np.percentile(hourData, uppQuantile))),
            lowerfence.append(GenericCode.roundNumber(np.min(hourData))),
            upperfence.append(GenericCode.roundNumber(np.max(hourData)))
    
        return q1, median, q3, lowerfence, upperfence