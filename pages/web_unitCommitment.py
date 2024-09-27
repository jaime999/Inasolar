import dash_bootstrap_components as dbc
import dash_loading_spinners as dls
import pandas as pd
import plotly.graph_objects as go
from dash import html, callback, Output, Input, State, ALL, dcc, register_page, ctx
from .filtro_dias import filtro_dias
from .predictor import getRangeSimulationForecast
from .genericCode import GenericCode
from .resourceAllocationGeneric import ResourceAllocation, ALLOCATION_PARAMETERS_RENEWABLES_RESULT_SQL
from .similarDaysGeneric import SimilarDays, HISTORICAL_WEATHER_COLUMNS_SQL, POWER_SQL
from datetime import date, timedelta


# Funciones para iniciar Dash
# ---------------------------------------------------------------
PAGE_TITLE = 'Unit Commitment'
register_page(__name__, title=PAGE_TITLE)


# FUNCIONES
# ---------------------------------------------------------------
def getMaxDateAllowed(area):
    maxDateAllowedCode = f"""SELECT MAX(d.date) AS Date
                                	 FROM [inasolar].[dbo].[ForecastWeather] f
                                	 INNER JOIN Dates d ON f.date = d.id
                                  	 WHERE Area={area}"""
    maxDateAllowed = GenericCode.getAndParseDate(maxDateAllowedCode)

    return maxDateAllowed


def getResourceAllocationCard(area):
    return ResourceAllocation.getRangeAndDemandParametersRow('unitCommitment', date.today())


def formatGraphData(graphParameters, paramTable, secondaryY):
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

    return pd.DataFrame(formatedGraphData)


def getElectricityPriceGraph(electricityPriceGraphData):
    # Se recuperan las variables que correspondan con la gráfica de precio eléctrico
    electricityPriceVariables = UNIT_COMMITMENT_PARAMETERS[
        UNIT_COMMITMENT_PARAMETERS['GraphId'] == 'ElectricityPrice']
    # Con la columna "GraphPosition" se conoce las series que van en cada gráfica
    unitCommitmentGraphs = formatGraphData(
        electricityPriceVariables, ELECTRICITY_PRICE_PARAMETERS, False)
    # Por defecto no seleccionamos rango del slider, ya que se puede cambiar con el selector
    rangeDate = [None, None]
    electricityPriceGraphData['Date'] = GenericCode.convertDate(
        electricityPriceGraphData['Date'])

    return GenericCode.generateGraph(electricityPriceGraphData, unitCommitmentGraphs,
                                     {'type': 'resultGraphs2',
                                         'key': 'electricityPrice'},
                                     rangeDate, 'Electricity Price', False, 'Date', '%{y:.4f}')


def getSimilarDaysBox(similarDays, quantiles, dates, dtStartDate, rangeDate):
    similarDays = GenericCode.readJSON(similarDays)
    similarDays['PredictedDay'] = pd.to_datetime(
        similarDays['PredictedDay'])
    fig = go.Figure()
    currentDate = dtStartDate
    # Añadir una nueva columna donde se encuentre la fecha que se está prediciendo con la hora
    similarDays['PredictedDayWithHour'] = similarDays['PredictedDay'] + \
        pd.to_timedelta(similarDays['Hour'], unit='h')
    similarDays['PredictedDayWithHour'] = GenericCode.convertDate(
        similarDays['PredictedDayWithHour'])
    while currentDate <= pd.to_datetime(dates['EndDate']):
        strCurrentDate = str(currentDate.date())
        actualSimilarDays = similarDays[similarDays['PredictedDay']
                                        == strCurrentDate]
        q1, median, q3, lowerfence, upperfence = filtro_dias.calculateBounds(
            actualSimilarDays, quantiles['Low'], quantiles['Upp'])
        fig.add_trace(go.Box(name=f'Demand forecast box plot {strCurrentDate}', q1=q1,
                             median=median,
                             q3=q3,
                             lowerfence=lowerfence,
                             upperfence=upperfence,
                             x=actualSimilarDays['PredictedDayWithHour'],
                             hovertemplate='Date: %{x}<br>' +
                             'Q1: %{q1}' + ' %s<br>' % POWER_SQL["unidad"].iloc[0] +
                             'Median: %{median}' + ' %s<br>' % POWER_SQL["unidad"].iloc[0] +
                             'Q3: %{q3}' + ' %s<br>' % POWER_SQL["unidad"].iloc[0] +
                             'Lower fence: %{lowerfence}' + ' %s<br>' % POWER_SQL["unidad"].iloc[0] +
                             'Upper fence: %{upperfence}' + ' %s' % POWER_SQL["unidad"].iloc[0]))
        # Se muestra la línea de la potencia predicha por cada hora
        fig.add_trace(go.Scatter(
            x=actualSimilarDays['PredictedDayWithHour'], y=actualSimilarDays[actualSimilarDays['Date']
                                                                             == strCurrentDate]['Power'],
            mode='lines', name=strCurrentDate,
            hovertemplate='Date: %{x}<br>Power: <b>%{y:.2f}' +
            ' %s</b>' % POWER_SQL["unidad"].iloc[0]
        ))
        currentDate += timedelta(days=1)

    fig.update_xaxes(nticks=7, rangeslider_visible=True,
                     tickformatstops=GenericCode.getGraphTickFormatStops(),
                     range=rangeDate, uirevision='time')

    fig.update_layout(yaxis_title='Power (kW)', xaxis_title='Date',
                      title=f'Demand interval forecast: {quantiles["Low"]}%-{quantiles["Upp"]}%')

    return (dcc.Graph(id={'type': 'resultGraphs', 'key': 'graphSimilarDaysUnitCommitment'},
                      figure=fig, config=GenericCode.removePlotlyLogo()),
            dbc.Alert(
                f"Total days: {len(similarDays.groupby('Date'))}", color="info"))


def getForecastWeatherVariablesGraph(forecastWeather, dates):
    weatherVariables = []
    forecastWeather['Date'] = forecastWeather['Date'] + \
        pd.to_timedelta(forecastWeather['Hour'], unit='h')
    forecastWeather['Date'] = GenericCode.convertDate(
        forecastWeather['Date'])
    # Se recuperan las variables que correspondan con la gráfica de predicción
    forecastingWeather = UNIT_COMMITMENT_PARAMETERS[UNIT_COMMITMENT_PARAMETERS['GraphId'] == 'Forecasting']
    # Con la columna "GraphPosition" se conoce las series que van en cada gráfica
    for index, unitCommitmentGraphs in forecastingWeather.groupby('GraphPosition'):
        # Se buscan las IDs de los parámetros meteorológicos
        unitCommitmentGraphs = formatGraphData(
            unitCommitmentGraphs, HISTORICAL_WEATHER_COLUMNS_SQL, True)
        dtStartDate = pd.to_datetime(dates['StartDate']).date()
        rangeDate = [dtStartDate +
                     timedelta(days=1), dtStartDate+timedelta(days=2)]
        weatherVariables.append(GenericCode.generateGraph(forecastWeather, unitCommitmentGraphs,
                                                          {'type': 'resultGraphs',
                                                              'key': f'weatherVariablesGraph{index}'},
                                                          rangeDate, '', True, 'Date'))

    return weatherVariables


def createElectricityPriceRange(maxDateAllowed):
    minDateAllowed = pd.to_datetime(maxDateAllowed) - timedelta(days=6)

    return dbc.Row(GenericCode.createRange({'type': 'resultRanges', 'key': 'electricityPriceIntervalDatePicker'}, minDateAllowed),
                   align='center', justify='center', className='pt-4 mt-4')


# VARIABLES
# ---------------------------------------------------------------
UNIT_COMMITMENT_PARAMETERS = pd.read_sql(
    """SELECT *
       FROM [inasolar].[dbo].[UnitCommitment]
       ORDER BY GraphPosition""", GenericCode.engine)
ELECTRICITY_PRICE_PARAMETERS = pd.read_sql(
    """SELECT *
       FROM [inasolar].[dbo].[descripcionDatos]
       WHERE Tabla = 'ElectricityPrice'""", GenericCode.engine)

# HTML
# ---------------------------------------------------------------
generationResource = dbc.Row([
    dbc.Col(GenericCode.selectResource(
        'generationLocation', 'Generator', 'openLocationInfoGenerator',
        ['LocationGenerator', 'LatitudeGenerator', 'LongitudeGenerator', 'TypeGenerator', 'AreaGenerator'], 'modalInfoGenerator'), width=6),
    dcc.Store(id='locationDataGenerator', data={'Location': 3, 'Area': 1, 'Latitude': '39.9261', 'Longitude': '-1.136',
                                                'Type': 'Generator', 'AreaName': 'Aras de los Olmos'})
], className='generation-location')

resultTabs = GenericCode.createResultTabs('unitCommitment')
targetDate = dbc.Row([
    dbc.Col(SimilarDays.getTargetDateTable('unitCommitment'), width=12)
], align='center', justify='center')
rangeRow = SimilarDays.createRangeAndSetDays(
    1, 'unitCommitmentSimilarDaysIntervalDatePicker')

quantilesRow = dbc.Row([
    dbc.Col(SimilarDays.generateQuantiles('Low. quantile(%)', 'lowQuantile', 10), width='auto', class_name='pt-3'
            ),
    dbc.Col(SimilarDays.generateQuantiles('Upp. quantile(%)', 'uppQuantile', 90), width='auto', class_name='pt-3')])
rangeRow.append(quantilesRow)

datesCard = dls.Grid(dbc.ListGroupItem(SimilarDays.getDatesCard(
    rangeRow, 'unitCommitment', targetDate)), color="#b3c2d6", debounce=100)

searchTabs = dbc.Card([
    SimilarDays.getHeaderSearchTabs(),
    dbc.CardBody(html.Div([dbc.CardGroup(
        [
            dbc.Card(
                 dbc.ListGroup(
                     [
                         datesCard,
                         dls.Grid([html.Div(SimilarDays.generateMarginsCard('Consumer', 'weather'), id='search-tabs-content'),
                                   html.Div(SimilarDays.generateMarginsCard('Generator', 'generator'), id='search-tabs-content-generator')],
                                  color="#b3c2d6", debounce=100)
                     ]
                 ), color='success', outline=True
                 )
        ]
    )]), className='p-0')
], class_name='mb-4')

modal = GenericCode.createModal('Information', 'similarDays')

layout = html.Div([
    html.H2(PAGE_TITLE),
    GenericCode.selectLocation('Consumer'),
    generationResource,
    searchTabs,
    ResourceAllocation.createParametersTabs('unitCommitment'),
    getResourceAllocationCard(1),
    resultTabs,
    modal
], id='unitCommitment-container', className='py-3')


# CALLBACKS
# ---------------------------------------------------------------
@callback(
    Output({'type': 'unitCommitmentResultCard', 'key': ALL}, 'children'),
    Input({'type': 'unitCommitmentResultCard', 'key': ALL}, 'children'),
    State({'type': 'storeData', 'key': 'unitCommitmentData'}, 'data'),
)
def addElectricityPriceInfo(resultCard, unitCommitmentData):
    # Además de la información obtenida de ResourceAllocation, también se quiere añadir en el grupo de precios
    # el precio de la electricidad
    costInfo = resultCard[0]
    electricityPrice = GenericCode.readJSON(
        unitCommitmentData['ElectricityPrice'])
    electricityPriceRange = createElectricityPriceRange(
        max(electricityPrice['ElectricityDateWithNoHour']))
    electricityPriceGraph = getElectricityPriceGraph(electricityPrice)
    
    costInfo.append(electricityPriceRange)
    costInfo.append(electricityPriceGraph)

    return [costInfo]


@callback(
    Output({'type': 'resultRanges', 'key': ALL}, 'start_date'),
    Output({'type': 'resultRanges', 'key': ALL}, 'end_date'),
    Output({'type': 'resultRanges', 'key': ALL}, 'max_date_allowed'),
    Input({'type': 'resultRanges', 'key': ALL}, 'min_date_allowed')
)
def updateElectricityPriceDates(minDateAllowed):
    # Por defecto se pueden seleccionar los últimos 7 días (contando el actual), pero la fecha de inicio es hace 2
    maxDateAllowed = pd.to_datetime(
        minDateAllowed[0]).date() + timedelta(days=6)
    startDate = maxDateAllowed - timedelta(days=2)

    # Se devuelven listas porque hay que usar ALL al no existir este elemento al cargar la página
    return [startDate], [maxDateAllowed], [maxDateAllowed]


@callback(
    Output({'type': 'resultGraphs2', 'key': ALL}, 'figure'),
    Input({'type': 'resultRanges', 'key': ALL}, 'start_date'),
    Input({'type': 'resultRanges', 'key': ALL}, 'end_date'),
    State({'type': 'storeData', 'key': 'unitCommitmentData'}, 'data'),
    State({'type': 'resultGraphs2', 'key': ALL}, 'figure')
)
def updateElectricityPriceGraph(startDate, endDate, unitCommitmentData, actualFigure):
    electricityPrice = GenericCode.readJSON(
        unitCommitmentData['ElectricityPrice'])
    newElectricityPrice = electricityPrice[(electricityPrice['ElectricityDateWithNoHour'] >= startDate[0]) &
                                           (electricityPrice['ElectricityDateWithNoHour'] <= endDate[0])]
    # Se recupera la info de las gráficas (se usa el índice ya que se ha usado ALL),
    # y se accede a cada serie individualmente, actualizando con los nuevos valores de X e Y
    actualFigure = actualFigure[0]
    for index, figureData in enumerate(actualFigure['data']):
        figureData['x'] = newElectricityPrice['Date']
        figureData['y'] = newElectricityPrice[ELECTRICITY_PRICE_PARAMETERS['nombre_dato'].iloc[index]]

    # Se devuelven listas porque hay que usar ALL al no existir este elemento al cargar la página
    return [actualFigure]


@callback(
    Output('unitCommitmentIntervalDatePicker', 'start_date'),
    Output('unitCommitmentIntervalDatePicker', 'end_date'),
    Output('unitCommitmentIntervalDatePicker', 'max_date_allowed'),
    Output('unitCommitmentSimilarDaysIntervalDatePicker', 'start_date'),
    Output('unitCommitmentSimilarDaysIntervalDatePicker', 'end_date'),
    Output('unitCommitmentSimilarDaysIntervalDatePicker', 'max_date_allowed'),
    Input('locationData', 'data')
)
def updateDates(locationData):
    maxDateAllowedResourceAllocation = getMaxDateAllowed(locationData['Area'])
    maxDateAllowedSimilarDays, disabledDays = SimilarDays.setMaxDateAllowedAndDisabledDays(
        locationData['Location'])

    return (date.today(), maxDateAllowedResourceAllocation, maxDateAllowedResourceAllocation, maxDateAllowedSimilarDays - timedelta(days=365),
            maxDateAllowedSimilarDays, maxDateAllowedSimilarDays)


@callback(
    Output('export-csv-unitCommitment', 'data'),
    Input('export-button-unitCommitment', 'n_clicks'),
    State({'type': 'storeData', 'key': 'unitCommitmentData'}, 'data'),
    State({'type': 'renewable-parameters', 'key': ALL, 'renewable': ALL, 'cardType': ALL,
           'scenarioUpdated': ALL, 'importChange': ALL}, 'id')
)
def exportData(csvFile, unitCommitmentData, renewableParametersId):
    if ctx.triggered_id == 'export-button-unitCommitment':
        fileName, parametersData, rangeDates = ResourceAllocation.initializeExportParameters(
            unitCommitmentData, renewableParametersId)

        return ResourceAllocation.exportSimulation(unitCommitmentData['Simulation'], parametersData, f'unitCommitmentSimulation{fileName}',
                                                   rangeDates, unitCommitmentData['Location'])

    return None


@callback(
    Output('generationLocation', 'options'),
    Output('generationLocation', 'value'),
    Input('locationData', 'data')
)
def updateGeneratorOptions(location):
    locationsDropdownSql = GenericCode.getLocationSqlQuery('Generator')
    locationsArea = locationsDropdownSql[locationsDropdownSql['Area']
                                         == location['Area']]
    dropdownOptions = GenericCode.setDropdownOptions(locationsArea)

    return dropdownOptions, dropdownOptions[0]['value']


@callback(
    Output('search-tabs-content-generator', 'children'),
    Input('search-data-tabs', 'active_tab')
)
def changeSearchData(activeTab):
    if activeTab == 'tab-margins':
        return SimilarDays.generateMarginsCard('Generator', 'generator')

    else:
        return SimilarDays.generatePondersCard('Generator', 'generator')


@callback(
    Output('unitCommitment-targetDate', 'data'),
    Input('unitCommitmentIntervalDatePicker', 'start_date'),
    Input('unitCommitmentIntervalDatePicker', 'end_date'),
    Input('locationData', 'data')
)
def getTargetDateInfo(startDate, endDate, locationData):
    # if targetDate is not None:
    dateInfo = filtro_dias.getDateInfoForecastWeather(
        startDate, endDate, locationData).map(GenericCode.roundNumber)

    return dateInfo.to_dict('records')


# Se crea un callback por cada parámetro para activar y desactivar el input
# en el card del generador
def updateInput(checkBoxValue, activeTab):
    if activeTab == 'tab-margins':
        return not checkBoxValue


for index, row in HISTORICAL_WEATHER_COLUMNS_SQL.iterrows():
    callback(
        Output({'type': 'generator-input',
               'key': row['nombre_dato']}, 'disabled'),
        Input({'type': 'generator-checkbox',
              'key': row['nombre_dato']}, 'value'),
        Input('search-data-tabs', 'active_tab')
    )(updateInput)


@callback(
    Output('unitCommitmentSimulateButton', 'disabled'),
    Input({'type': 'weather-input', 'key': ALL}, 'disabled'),
    Input({'type': 'weather-input', 'key': ALL}, 'value'),
    Input({'type': 'generator-input', 'key': ALL}, 'disabled'),
    Input({'type': 'generator-input', 'key': ALL}, 'value'),
    Input({'type': 'renewable-parameters', 'key': ALL, 'renewable': ALL, 'cardType': ALL,
           'scenarioUpdated': ALL, 'importChange': ALL}, 'value'),
    Input('num-days', 'value'),
    Input({'type': 'unitCommitmentTypeOfDayCheckbox', 'key': ALL}, 'value'),
)
def disableSearchButton(consumerInputsDisabled, consumerInputsValues, generatorInputsDisabled,
                        generatorInputsValues, renewableParametersValue, numDays, typeOfDays):
    return ((type(numDays) == type(None) or float(numDays) <= 0) or ResourceAllocation.disableButton(renewableParametersValue)
            or (not any(typeOfDays)) or SimilarDays.disableButton(consumerInputsValues, consumerInputsDisabled)
            or SimilarDays.disableButton(generatorInputsValues, generatorInputsDisabled))


@callback(
    Output('locationDataGenerator', 'data'),
    Input('generationLocation', 'value')
)
def changingLocation(location):
    return GenericCode.changeLocationData(location)


@callback(
    Output("modalInfoGenerator", "is_open"),
    Output("infoLocationGenerator", "children"),
    Output("infoLatitudeGenerator", "children"),
    Output("infoLongitudeGenerator", "children"),
    Output("infoTypeGenerator", "children"),
    Output("infoAreaGenerator", "children"),
    Input("openLocationInfoGenerator", "n_clicks"),
    State("locationDataGenerator", 'data'),
    Input("closeLocationInfo", "n_clicks"),
    prevent_initial_call=True
)
def open_info_modal(openLocationInfo, locationDataGenerator, closeLocationInfo):
    if ctx.triggered_id == 'openLocationInfoGenerator':
        return (True, locationDataGenerator['LocationName'], locationDataGenerator['Latitude'], locationDataGenerator['Longitude'],
                locationDataGenerator['Type'], locationDataGenerator['AreaName'])

    return False, '', '', '', '', ''


@callback(
    Output('unitCommitment-result-tabs-content', 'children'),
    Output('unitCommitment-exportCol', 'style'),
    Input('unitCommitment-result-data-tabs', 'active_tab'),
    Input({'type': 'storeData', 'key': 'unitCommitmentData'}, 'data'),
    prevent_initial_call=True
)
def showActiveTabData(resultTab, unitCommitmentData):
    csvNotDisplayed = {'display': 'none'}
    if len(unitCommitmentData) == 0:
        return [], csvNotDisplayed

    if len(unitCommitmentData['alertMessage']) > 0:
        return dbc.Alert(unitCommitmentData['alertMessage'], color='danger'), csvNotDisplayed

    tabGraph, tabTable, summaryHeader = ResourceAllocation.initializeTabValues(
        'unitCommitment', unitCommitmentData['Location'])
    dates = unitCommitmentData['Dates']
    dtStartDate = pd.to_datetime(dates['StartDate'])
    rangeDate = [dtStartDate+timedelta(days=1), dtStartDate+timedelta(days=2)]
    simulationInfo, csvNotDisplayed = ResourceAllocation.getSimulationInfo(unitCommitmentData['Location'], unitCommitmentData, resultTab, tabGraph, tabTable, summaryHeader, rangeDate,
                                                                           csvNotDisplayed, 'unitCommitment')

    if resultTab == 'unitCommitment-tab-graph':
        similarDaysGraph, days = getSimilarDaysBox(
            unitCommitmentData['SimilarDays'], unitCommitmentData['Quantiles'], dates, dtStartDate, rangeDate)
        similarDaysResultCard = GenericCode.createResultsCard(
            [similarDaysGraph, days], 'Similar Days')
        weatherVariables = getForecastWeatherVariablesGraph(
            GenericCode.readJSON(unitCommitmentData['Forecast']), dates)
        weatherVariablesResultCard = GenericCode.createResultsCard(
            weatherVariables, 'Forecasting')
        # Se inserta el diagrama box-whisker y las variables meteorológicas de predicción
        # justo después de la tabla de Summary, y antes de la gráfica de costes
        simulationInfo.insert(2, similarDaysResultCard)
        # Se añade el grupo donde se encuentra cada gráfica de las variables meteorológicas
        # a la lista donde se encuentran las gráficas, etc. de la simulación
        simulationInfo.insert(3, weatherVariablesResultCard)

    return simulationInfo, csvNotDisplayed


@callback(
    Output({'type': 'storeData', 'key': 'unitCommitmentData'}, 'data'),
    Input('unitCommitmentSimulateButton', 'n_clicks'),
    State('search-data-tabs', 'active_tab'),
    State({'type': 'renewable-parameters', 'key': ALL, 'renewable': ALL, 'cardType': ALL,
           'scenarioUpdated': ALL, 'importChange': ALL}, 'id'),
    State({'type': 'renewable-parameters', 'key': ALL, 'renewable': ALL, 'cardType': ALL,
           'scenarioUpdated': ALL, 'importChange': ALL}, 'value'),
    State('unitCommitmentIntervalDatePicker', 'start_date'),
    State('unitCommitmentIntervalDatePicker', 'end_date'),
    State('unitCommitmentSimilarDaysIntervalDatePicker', 'start_date'),
    State('unitCommitmentSimilarDaysIntervalDatePicker', 'end_date'),
    State('locationData', 'data'),
    State('locationDataGenerator', 'data'),
    State({'type': 'weather-input', 'key': ALL}, 'value'),
    State({'type': 'weather-input', 'key': ALL}, 'id'),
    State({'type': 'weather-input', 'key': ALL}, 'disabled'),
    State({'type': 'generator-input', 'key': ALL}, 'value'),
    State({'type': 'generator-input', 'key': ALL}, 'id'),
    State({'type': 'generator-input', 'key': ALL}, 'disabled'),
    State({'type': 'unitCommitmentTypeOfDayCheckbox', 'key': ALL}, 'value'),
    State('num-days', 'value'),
    State({'type': 'storeData', 'key': 'unitCommitmentData'}, 'data'),
    State('checkboxWithoutFailures', 'value'),
    [State('locationsDropdown', 'value'), State(
        'locationsDropdown', 'options')],
    State('lowQuantile', 'value'),
    State('uppQuantile', 'value'),
    State('selectDemand', 'value'),
    prevent_initial_call=True
)
def simulateAssignment(simulateButton, similarDaysTab, renewableParametersId, renewableParametersValue, predictedStartDate, predictedEndDate, similarDaysStartDate,
                       similarDaysEndDate, locationDataConsumer, locationDataGenerator, consumerInputsValue, consumerInputsId, consumerInputsDisabled,
                       generatorInputsValue, generatorInputsId, generatorInputsDisabled, typeOfDaysValue, numDays, unitCommitmentData, withoutFailures,
                       locationValue, locationOptions, lowQuantile, uppQuantile, demandSelected):
    unitCommitmentData['alertMessage'] = ''
    if ctx.triggered_id == 'unitCommitmentSimulateButton':
        # Mediante esta función, asociamos cada ID de cada input a su valor
        resourceAllocationParameters = GenericCode.generateParametersWithValue(
            renewableParametersId, renewableParametersValue)
        # Se calcula que tipo de día está marcado
        typeOfDays = SimilarDays.getTypeOfDays(typeOfDaysValue)
        alertValue, alertMessage = ResourceAllocation.setSimulationRestrictions(
            resourceAllocationParameters)
        unitCommitmentData['alertMessage'] = alertMessage
        if alertValue:
            return unitCommitmentData

        if similarDaysTab == 'tab-margins':
            # Mediante esta función, asociamos cada ID de cada input a su valor, y eliminamos las que no tengan valor
            consumerInputsValue = SimilarDays.getMargins(
                consumerInputsId, consumerInputsValue, consumerInputsDisabled)
            generatorInputsValue = SimilarDays.getMargins(
                generatorInputsId, generatorInputsValue, generatorInputsDisabled)
        try:
            simulationResult, similarDays, forecastWeather, electricityPrice = getRangeSimulationForecast(resourceAllocationParameters, predictedStartDate, predictedEndDate, consumerInputsValue, generatorInputsValue, similarDaysTab,
                                                                                                          similarDaysStartDate, similarDaysEndDate, locationDataConsumer, locationDataGenerator, typeOfDays, ALLOCATION_PARAMETERS_RENEWABLES_RESULT_SQL[
                                                                                                              'IdParameter'], not withoutFailures, numDays, demandSelected)
            # Se divide entre 1000 ya que el valor que se obtiene de la red eléctrica es en Mwh, que no nos sirve
            for index, row in ELECTRICITY_PRICE_PARAMETERS.iterrows():
                priceParam = row['nombre_dato']
                electricityPrice[priceParam] = electricityPrice[priceParam] / 1000
        except Exception as e:
            unitCommitmentData['alertMessage'] = str(e)
            return unitCommitmentData

        # Se almacena la información de la simulación en el Store
        unitCommitmentData = ResourceAllocation.getResultStoreData(unitCommitmentData, resourceAllocationParameters, withoutFailures, predictedStartDate,
                                                                   predictedEndDate, locationValue, locationOptions)
        # Se convierte el dataframe a JSON para poder almacenarlo en el Store
        unitCommitmentData['Simulation'] = GenericCode.convertToJSON(
            simulationResult)
        unitCommitmentData['SimilarDays'] = GenericCode.convertToJSON(
            similarDays)
        unitCommitmentData['Forecast'] = GenericCode.convertToJSON(
            forecastWeather)
        unitCommitmentData['ElectricityPrice'] = GenericCode.convertToJSON(
            electricityPrice)
        unitCommitmentData['Quantiles'] = {
            'Low': lowQuantile, 'Upp': uppQuantile}

        return unitCommitmentData

    return {}
