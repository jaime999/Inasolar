import pandas as pd
from datetime import timedelta
from .filtro_dias import filtro_dias
from .simulator import simulator
from .genericCode import GenericCode


def getPredictedPower(similarDays, objectiveDay):
    powerPredicted = similarDays.groupby('Hour')['Power'].mean().reset_index()

    # Se añade la potencia predicha a la fecha objetivo
    return pd.concat([objectiveDay, powerPredicted['Power']], axis=1), similarDays


def getPredictedPowerMargins(margins, objectiveDay, typeOfDays, rangeData):
    query = filtro_dias.getSimilarDaysByMargins(
        margins, objectiveDay, typeOfDays)
    # Se usa la query para obtener los días similares que cumplen las condiciones de márgenes
    similarDays = filtro_dias.getSimilarDaysByTargetDate(
        rangeData, objectiveDay, query)
    if similarDays.empty:
        raise Exception('There are no similar days for the selected margins')

    return getPredictedPower(similarDays, objectiveDay)


def getPredictedPowerPonders(ponders, objectiveDay, rangeData, num_days):
    bestDays, rangeData = filtro_dias.getSimilarDaysByPonders(
        rangeData, objectiveDay, ponders, num_days)
    # Una vez que se obtienen las mejores notas segun num_days, se filtran en el rango que se ha seleccionado
    similarDays = rangeData[rangeData['Date'].isin(bestDays['Date'].values)]

    return getPredictedPower(similarDays, objectiveDay)



def getForecastElectricityPrice(area):
    # Se obtiene la última fecha de la que se tiene precio
    priceMaxDateSql = pd.read_sql(f"""SELECT MAX(d.date) AS Date
                                     FROM [inasolar].[dbo].[ElectricityPrice] e
                                     INNER JOIN Dates d ON e.date = d.id
                                     WHERE Area = {area}""", GenericCode.engine)
    targetDate = pd.to_datetime(priceMaxDateSql['Date'][0])
    if not targetDate:
        raise Exception('No electricity price data for this area')

    startDate = (targetDate - timedelta(days=6)).date()
    startDate, targetDate = filtro_dias.parseDates(str(startDate), str(targetDate.date()))
    electricityPriceSql = pd.read_sql("""SELECT e.Price, e.Surplus, d.Date AS ElectricityDate,
                                           CONVERT(varchar(10), d.Date, 23) AS ElectricityDateWithNoHour
                                           FROM [inasolar].[dbo].ElectricityPrice e
                                           INNER JOIN Dates d ON d.id = e.date
                                           WHERE d.Date >= CONVERT(DATETIME, ?, 102) AND d.Date <= CONVERT(DATETIME, ?, 102)
                                           AND e.Area = ?""", GenericCode.engine,
                                      params=(startDate, targetDate, area))
    
    return electricityPriceSql


def getRangeData(startDate, endDate, location, demandSelected):
    rangeData = pd.read_sql(f"""SELECT d.Hour, CONVERT(varchar(10), d.Date, 23) AS Fecha, h.*, d.*,g.{demandSelected} AS Power, ho.* 
                           FROM datosGEDER2 g, HistoricalWeather h, Dates d, Holidays ho
                           WHERE g.date = d.id AND d.id = ho.date AND d.id = h.date AND
                           (d.Date >= CONVERT(DATETIME, '{startDate}', 102) AND d.Date <= CONVERT(DATETIME, '{endDate}', 102))
                           AND ho.Area = {location['Area']} AND h.Area = {location['Area']} AND
                           g.location = {location['Location']} ORDER BY Fecha, d.Hour """, GenericCode.engine)
    rangeData = filtro_dias.fixIntervalDates(rangeData)

    return rangeData


def getForecastWeather(startDate, endDate, area):
    forecastWeather = pd.read_sql(f"""SELECT d.Hour, CONVERT(varchar(10), d.Date, 23) AS Fecha, f.*, d.*, ho.* 
                           FROM ForecastWeather f, Dates d, Holidays ho
                           WHERE d.id = ho.date AND d.id = f.date
                           AND d.Date >= CONVERT(DATETIME, '{startDate}', 102)
                           AND d.Date <= CONVERT(DATETIME, '{endDate}', 102)
                           AND ho.Area = {area} AND f.Area = {area}""", GenericCode.engine)    
                           
    return filtro_dias.fixIntervalDates(forecastWeather)                     


def getPredictionCheckingFailures(simulationParameters, with_failures, final_date, current_date, locationGenerator, parameters, consumerInputsValue, generatorInputsValue,
                                  rangeDataConsumer, rangeDataGenerator, typeOfDays, similarDaysTab, numDays, forecastWeather):
    # Se inicializan las variables antes de comenzar con la simulación
    #final_date = parser.parse(final_date)
    #current_date = parser.parse(current_date)
    simulation = simulator()
    for key, value in simulationParameters.items():
        setattr(simulation, key, value)
    (FV_hours_until_failure, Eolic_hours_until_failure, Biogas_hours_until_failure, Turbine_hours_until_failure, Pump_hours_until_failure,
     general_table, next_hours) = simulation.initializeVariables(with_failures, final_date, current_date, locationGenerator['Area'], locationGenerator['Location'])
    electricityPriceSql = getForecastElectricityPrice(locationGenerator['Area'])
    maxDate = pd.to_datetime(electricityPriceSql['ElectricityDateWithNoHour']).max()
    maxElectricityPrice = electricityPriceSql[electricityPriceSql['ElectricityDateWithNoHour'] == str(maxDate.date())].reset_index(drop=True)
    totalSimilarDays = None
    while current_date < final_date:
        (FV_hours_until_failure, Eolic_hours_until_failure, Biogas_hours_until_failure, Turbine_hours_until_failure, Pump_hours_until_failure,
         next_hours) = simulation.initializeFailures(with_failures, FV_hours_until_failure, Eolic_hours_until_failure, Biogas_hours_until_failure,
                                                     Turbine_hours_until_failure, Pump_hours_until_failure, next_hours)
        # Se obtiene la previsión de cada día a simular
        objectiveDay = forecastWeather[(forecastWeather['Year'] == current_date.year) &
                                       (forecastWeather['Month'] == current_date.month) &
                                       (forecastWeather['Day'] == current_date.day)].reset_index(drop=True)
        if similarDaysTab == 'tab-margins':
            predictedDayConsumer, similarDaysConsumer = getPredictedPowerMargins(
                consumerInputsValue, objectiveDay, typeOfDays, rangeDataConsumer)
            predictedDayGenerator, similarDaysGenerator = getPredictedPowerMargins(
                generatorInputsValue, objectiveDay, typeOfDays, rangeDataGenerator)

        else:
            predictedDayConsumer, similarDaysConsumer = getPredictedPowerPonders(
                consumerInputsValue, objectiveDay, rangeDataConsumer, numDays)
            predictedDayGenerator, similarDaysGenerator = getPredictedPowerPonders(
                generatorInputsValue, objectiveDay, rangeDataGenerator, numDays)
        
        predictedDayConsumer = pd.concat(
            [predictedDayConsumer, maxElectricityPrice], axis=1)
        similarDaysConsumer = pd.concat([similarDaysConsumer, predictedDayConsumer], ignore_index=True)
        # Columna que indica el día al que pertenecen el conjunto de días similares
        similarDaysConsumer['PredictedDay'] = current_date
        try:
            general_table = pd.concat([general_table, simulation.getDailyAssignment(predictedDayConsumer, predictedDayGenerator,
                                                                                    current_date, general_table, next_hours, parameters)],
                                      ignore_index=True)
            # Cada conjuntos de días similares se añaden a esta lista para devolverlos todos y mostrarlos en una gráfica
            totalSimilarDays = pd.concat([totalSimilarDays, similarDaysConsumer])
        except Exception as e:
            print(f"Error en: {current_date}", e)
            raise Exception(e)
        current_date = current_date + timedelta(days=1)

    electricityPriceSql = electricityPriceSql.rename(columns={'ElectricityDate': 'Date'})
    return general_table, totalSimilarDays, electricityPriceSql


def getRangeSimulationForecast(simulationParameters, predictionStartDate, predictionEndDate, consumerInputsValue, generatorInputsValue, similarDaysTab,
                               similarDaysStartDate, similarDaysEndDate, locationConsumer, locationGenerator, typeOfDays, resourceAllocationParameters,
                               withFailures, numDays, demandSelected):
    predictionStartDate, predictionEndDate = filtro_dias.parseDates(
        predictionStartDate, predictionEndDate)
    similarDaysStartDate, similarDaysEndDate = filtro_dias.parseDates(
        similarDaysStartDate, similarDaysEndDate)
    rangeDataConsumer = getRangeData(
        similarDaysStartDate, similarDaysEndDate, locationConsumer, demandSelected)
    rangeDataGenerator = getRangeData(
        similarDaysStartDate, similarDaysEndDate, locationGenerator, 'Power')
    forecastWeather = getForecastWeather(
        predictionStartDate, predictionEndDate, locationConsumer['Area'])
    simulationResult, similarDays, electricityPriceSql = getPredictionCheckingFailures(simulationParameters, withFailures, predictionEndDate, predictionStartDate, locationGenerator, resourceAllocationParameters,
                                         consumerInputsValue, generatorInputsValue, rangeDataConsumer, rangeDataGenerator, typeOfDays, similarDaysTab, numDays, forecastWeather)

    return simulationResult, similarDays, forecastWeather, electricityPriceSql
