from pandas import read_sql
from .genericCode import GenericCode
from pandas import DataFrame, to_datetime, to_timedelta
from fastapi import HTTPException , status
from .filtro_dias import filtro_dias
from datetime import timedelta

ELECTRICITY_PRICE_PARAMETERS = read_sql(
    """SELECT *
       FROM [inasolar].[dbo].[descripcionDatos]
       WHERE Tabla = 'ElectricityPrice'""", GenericCode.engine)

UNIT_COMMITMENT_PARAMETERS = read_sql(
    """SELECT *
       FROM [inasolar].[dbo].[UnitCommitment]
       ORDER BY GraphPosition""", GenericCode.engine)

HISTORICAL_WEATHER_COLUMNS_SQL = read_sql(
    """SELECT nombre_dato, nombre_alternativo, unidad, defaultMargin, defaultPonder
               FROM descripcionDatos
               WHERE Tabla = 'HistoricalWeather'""", GenericCode.engine)

COSTS_PARAMETERS = read_sql(
    """SELECT IdParameter,Name,Unity
               FROM AllocationParameters
               WHERE GraphType='Line3' order BY GraphOrder ASC""", GenericCode.engine)

def formatGraphData(graphParameters, paramTable, secondaryY) -> DataFrame:
    formatedGraphData = []
    for index, graphParameter in graphParameters.iterrows():
        # Si es el segundo parámetro, se coloca a la derecha del eje Y
        parameterSecondaryY = 0
        if secondaryY:
            parameterSecondaryY = index % 2
        # Se obtienen las carácterísticas del parámetro (nombre, unidad...)
        actualParam = paramTable[paramTable['nombre_dato']
                                 == graphParameter['IdParameter']].iloc[0]
        paramUnit = graphParameter['Unity'].strip()
        formatedGraphData.append({'IdParameter': graphParameter['IdParameter'],
                                  'GraphLabel': actualParam['nombre_alternativo'],
                                  'GraphHover': paramUnit,
                                  'GraphTitle': f'{actualParam["nombre_alternativo"]} ({paramUnit})',
                                  'GraphColor': graphParameter['Color'],
                                  'SecondaryY': parameterSecondaryY})

    return DataFrame(formatedGraphData)

def getForecastWeatherVariablesGraph():
    # Se recuperan las variables que correspondan con la gráfica de predicción
    forecastingWeather = UNIT_COMMITMENT_PARAMETERS[UNIT_COMMITMENT_PARAMETERS['GraphId'] == 'Forecasting']
    # Con la columna "GraphPosition" se conoce las series que van en cada gráfica
    columns = []
    for index, unitCommitmentGraphs in forecastingWeather.groupby('GraphPosition'):
        # Se buscan las IDs de los parámetros meteorológicos
        unitCommitmentGraphs = formatGraphData(
            unitCommitmentGraphs, HISTORICAL_WEATHER_COLUMNS_SQL, True)
        columns.append(unitCommitmentGraphs["IdParameter"].to_list())

    return columns

def getSimilarDaysBox(similarDays, quantiles, dtEndDate, dtStartDate):
    similarDays['PredictedDay'] = to_datetime(
        similarDays['PredictedDay'])
    currentDate = dtStartDate.date()
    # Añadir una nueva columna donde se encuentre la fecha que se está prediciendo con la hora
    similarDays['PredictedDayWithHour'] = similarDays['PredictedDay'] + \
        to_timedelta(similarDays['Hour'], unit='h')
    similarDays['PredictedDayWithHour'] = GenericCode.convertDate(
        similarDays['PredictedDayWithHour'])
    current_day_data = {"q1":[],"median":[],"q3":[],"min":[],"max":[]}

    while currentDate <= to_datetime(dtEndDate).date():
        strCurrentDate = str(currentDate)
        actualSimilarDays = similarDays[similarDays['PredictedDay']
                                        == strCurrentDate]
        
        q1,median,q3,minimum,maximum = filtro_dias.calculateBounds(
            actualSimilarDays, quantiles['Low'], quantiles['Upp'])
        #.append no sirve
        current_day_data["q1"]     += q1
        current_day_data["median"] += median
        current_day_data["q3"]     += q3
        current_day_data["min"]    += minimum
        current_day_data["max"]    += maximum

        currentDate += timedelta(days=1)

    #comprobamos que tengan todas la misma longitud
    if not (len(current_day_data["q1"]) == len(current_day_data["median"]) ==len(current_day_data["q3"]) ==len(current_day_data["min"]) == len(current_day_data["max"])):
        raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No similar days found",
            )
    
    #Es mejor devolver current_day_data pero para no cambiar el formato que establecimos en la segunda app hay que hacer lo siguiente
    response = {"data":[],"category":[]}
    currentDate = dtStartDate
    for i in range(0,len(current_day_data["q1"])):
        current_hour = {
            "q1": current_day_data["q1"][i],
            "median": current_day_data["median"][i],
            "q3": current_day_data["q3"][i],
            "min": current_day_data["min"][i],
            "max": current_day_data["max"][i],
        }
        response["data"].append(current_hour)
        response["category"].append(currentDate.strftime('%Y-%m-%dT%H:%M:%S'))
        currentDate = currentDate + timedelta(hours=1)

    return response

def formatForecastCharts(forecastWeather,category,db):
    #Tablas weather forecast
    weatherVariables = getForecastWeatherVariablesGraph()
    
    forecast_charts = []
    for pair in weatherVariables:
        chart_data = {
            "data": [{"name": db.getColumnAlternativeName(pair[0]), "data":forecastWeather.to_dict("list")[pair[0]]},
                     {"name": db.getColumnAlternativeName(pair[1]), "data":forecastWeather.to_dict("list")[pair[1]]}],
            "category": category
        }
        if len(chart_data["category"]) == len(chart_data["data"][0]["data"]) == len(chart_data["data"][1]["data"]):
            forecast_charts.append(chart_data)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str("Fallo al generar las graficas del forecast"),
            )
    return forecast_charts

def formatCostChartAndSummary(simulationResult,category):
    costData = {"data":[],"category":category}
    summaryCost = {"data":[],"category":[]}
    simulationResultAux = simulationResult.copy().to_dict("list")
    for key, value in COSTS_PARAMETERS.iterrows():
        costData["data"].append({"name":value["Name"],"data":simulationResultAux[value["IdParameter"]]})
        summaryCost["data"].append(sum(simulationResultAux[value["IdParameter"]]))
        summaryCost["category"].append(value["Name"] + " " + value["Unity"])
    return costData, summaryCost

def formatElectricityPriceChart(electricityPrice):
    # Se divide entre 1000 ya que el valor que se obtiene de la red eléctrica es en Mwh, que no nos sirve
    electricityPriceChart = {"data":[],"category":[]}
    for index, row in ELECTRICITY_PRICE_PARAMETERS.iterrows():
        priceParam = row['nombre_dato']
        data = {"name":(priceParam if row['nombre_dato'] != 'Price' else 'Electricity') + " Price", "data":(electricityPrice[priceParam] / 1000).to_list()}
        electricityPriceChart["data"].append(data)

    electricityPriceChart["category"] = list(x.strftime('%Y-%m-%dT%H:%M:%S') for x in electricityPrice["Date"].tolist())
    return electricityPriceChart