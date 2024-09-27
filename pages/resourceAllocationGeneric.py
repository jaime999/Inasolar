import pandas as pd
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import io
from plotly.subplots import make_subplots
from .genericCode import GenericCode
from .simulator import simulator
from datetime import datetime, timedelta
from dash import dash_table, callback, Output, Input, State, ctx, dcc, html, ALL
from dateutil import parser


# VARIABLES
# ---------------------------------------------------------------
ALLOCATION_PARAMETERS_RENEWABLES_FIELD_SQL = pd.read_sql(
    """SELECT a.*
           FROM [inasolar].[dbo].[AllocationParameters] a
           LEFT JOIN RenewableEnergiesInfo r ON a.Type = r.IdType
           WHERE a.DefaultValue IS NOT NULL
           ORDER BY ParametersOrder""", GenericCode.engine)
ALLOCATION_PARAMETERS_SUMMARY_SQL = pd.read_sql(
    """SELECT *
           FROM [inasolar].[dbo].[AllocationParameters] a
    	   WHERE GraphType = 'Summary'
           ORDER BY ParametersOrder""", GenericCode.engine)
ALLOCATION_PARAMETERS_OPTIMIZATION_SQL = ALLOCATION_PARAMETERS_SUMMARY_SQL[
    ALLOCATION_PARAMETERS_SUMMARY_SQL['ParameterType'] == 'optimizationData']
ALLOCATION_PARAMETERS_RENEWABLES_RESULT_SQL = pd.read_sql(
    """SELECT a.*
           FROM [inasolar].[dbo].[AllocationParameters] a
           LEFT JOIN RenewableEnergiesInfo r ON a.Type = r.IdType
    	   WHERE a.DefaultValue IS NULL AND a.ColumnWidth IS NOT NULL AND (GraphType IS NULL OR GraphType != 'Summary')
           ORDER BY ParametersOrder""", GenericCode.engine)
OPTIMIZATION_PARAMETERS_SUMMARY_SQL = pd.read_sql(
    """SELECT *
           FROM [inasolar].[dbo].[OptimizationParameters]
           ORDER BY ParametersOrder""", GenericCode.engine)


def generateLabelAndInput(labelName, parameterId, inputValue, parameterType, importChange=False, renewableType=None,
                          disabledValue=False, cardType=None, optimizationParameters=False, minValue=0):
    maxValue = None
    step = 'any'
    if parameterId == 'performance' or parameterType == 'optimization-ponders':
        maxValue = 1
        step = 0.001

    elif parameterId == 'biogas_generation_percentage':
        maxValue = 200

    inputId = {'type': parameterType,
               'key': parameterId, 'importChange': importChange}

    if renewableType is not None:
        inputId['renewable'] = renewableType

    if cardType is not None:
        # Si se encuentra en los parámetros de los tamaños de los renovables se indica en cual,
        # y se indica si se utiliza en los escenarios
        inputId['cardType'] = cardType
        inputId['scenarioUpdated'] = optimizationParameters
        # El caso del volumen inicial de biogas es especial, por lo que se tiene que actualizar a mano
        if parameterId == 'gas_initial_volume':
            inputId['scenarioUpdated'] = False

    return dbc.Row([
        dbc.Col(labelName, width=8),
        dbc.Col(
            dbc.Input(inputId, type='number',
                      value=inputValue, min=minValue, max=maxValue, step=step, disabled=disabledValue),
            width=4, className='px-1'
        )
    ], class_name='pb-3', align='center')


def generateParameter(renewableType, className, cardType, optimizationParameters={}):
    renewableTypeColumn = pd.read_sql(
        f"""SELECT Type, Acronym
               FROM [inasolar].[dbo].[RenewableEnergiesInfo]
               WHERE IdType='{renewableType}'""", GenericCode.engine).iloc[0]
    parameter_df = ALLOCATION_PARAMETERS_RENEWABLES_FIELD_SQL[
        (ALLOCATION_PARAMETERS_RENEWABLES_FIELD_SQL['Type'] == renewableType) &
        (ALLOCATION_PARAMETERS_RENEWABLES_FIELD_SQL['ParameterType'] == cardType)]

    return ResourceAllocation.getTabsParameters(parameter_df, f"{renewableTypeColumn['Type']} ({renewableTypeColumn['Acronym']})",
                                                renewableType, cardType, className, optimizationParameters)


class ResourceAllocation:
    # FUNCIONES
    # ---------------------------------------------------------------
    def generateButton(pageId):
        return dbc.Button('Align Graphs', id={'type': 'resultButton', 'key': 'alignGraphs', 'page': pageId})

    def initializeExportParameters(storeData, renewableParametersId):
        rangeDates = storeData['Dates']
        startDate, endDate = rangeDates["StartDate"], rangeDates["EndDate"]
        fileName = f'_{storeData["Location"]}_{startDate}_{endDate}'

        # Se obtienen los valores correspondientes con cada renovable
        photovoltaicParameters, windPowerParameters, biogasParameters, hydraulicParameters, resourceParameters = ResourceAllocation.generateRenewablesSizes(
            renewableParametersId, storeData['Parameters'])

        withoutFailures = {'Title': 'Failures', 'Data': pd.DataFrame(
            [{'withoutFailures': storeData['Failures']}])}

        parametersData = [photovoltaicParameters, windPowerParameters, biogasParameters, hydraulicParameters,
                          resourceParameters, withoutFailures]

        return fileName, parametersData, rangeDates

    def exportToExcel(parametersSheetData, restSheets, fileName, rangeDates, location):
        writer, output = ResourceAllocation.exportParametersToExcel(
            parametersSheetData)

        return GenericCode.writeExcelData(writer, restSheets, output, fileName, rangeDates, location)

    def exportSimulation(simulationData, parametersData, fileName, rangeDates, location):
        excelColumns = [column["id"]
                        for column in ResourceAllocation.COLUMNS_SIMULATION]
        resourceAllocationDataDf = GenericCode.readJSON(simulationData)

        return ResourceAllocation.exportToExcel(parametersData, [{'SheetName': 'Simulation', 'Data': resourceAllocationDataDf[excelColumns]}],
                                                f'{fileName}.xlsx', rangeDates, location)

    def initializeTabValues(pageId, location):
        tabGraph = f'{pageId}-tab-graph'
        tabTable = f'{pageId}-tab-table'
        # Se crea el título de Summary, con la URL donde se encuentra la información
        summaryHeader = ResourceAllocation.getTableTitle(f'Summary {location}', 'summary-info', True,
                                                         'https://drive.google.com/file/d/1UO5uSWbf2El5o08WRlNi9FebmbZtGPQ_/view?usp=share_link')

        return tabGraph, tabTable, summaryHeader

    def getSimulationInfo(locationLabel, storeData, resultTab, tabGraph, tabTable, summaryHeader, rangeDate, csvNotDisplayed, pageId):
        titleLabel = f'Simulation: {locationLabel}'
        simulationResult = GenericCode.readJSON(
            storeData['Simulation'])
        # Se convierte la fecha porque al deserializar se modifica el formato
        simulationResult['Date'] = GenericCode.convertDate(
            simulationResult['Date'])
        summary = simulator.get_summary(simulationResult, False)
        summaryTable = ResourceAllocation.createSummaryTable(summary, 'Total')
        tableTotalCostHeader = ResourceAllocation.getTableTitle(f'Summary total cost - {locationLabel}',
                                                                'summaryTotalCost-info', False, '')
        tableParcialCostHeader = ResourceAllocation.getTableTitle(f'Summary parcial cost - {locationLabel}',
                                                                  'summaryParcialCost-info', False, '')
        if resultTab == tabGraph:            
            if rangeDate:
                simulationResultParcial = simulationResult[(pd.to_datetime(simulationResult['Date']) >= rangeDate[0]) &
                                                           (pd.to_datetime(simulationResult['Date']) <= rangeDate[1])]
                
            else:
                simulationResultParcial = simulationResult

            summaryParcial = simulator.get_summary(simulationResultParcial, False)
            summaryTableParcial = ResourceAllocation.createSummaryTable(
                summaryParcial, 'Parcial')
            potDem = ResourceAllocation.GRAPH_DATA.loc[ResourceAllocation.GRAPH_DATA['IdParameter']
                                                       == 'PotDem'].iloc[0]
            alignGraphsButton = ResourceAllocation.generateButton(pageId)
            figRegulation = ResourceAllocation.generateGraph(
                '1', ResourceAllocation.GRAPH_DATA, potDem, simulationResult, rangeDate, titleLabel)
            figNoRegulation = ResourceAllocation.generateGraph(
                '2', ResourceAllocation.GRAPH_DATA, potDem, simulationResult, rangeDate, titleLabel)
            sunburstRegulationParcial = ResourceAllocation.generateSunburstGraph(
                simulationResultParcial, 'Modified', 'With Regulation', 'Parcial')
            sunburstNoRegulationParcial = ResourceAllocation.generateSunburstGraph(
                simulationResultParcial, '', 'Without Regulation', 'Parcial')
            sunburstRegulation = ResourceAllocation.generateSunburstGraph(
                simulationResult, 'Modified', 'With Regulation', 'Total')
            sunburstNoRegulation = ResourceAllocation.generateSunburstGraph(
                simulationResult, '', 'Without Regulation', 'Total')
            figCost = ResourceAllocation.generateCostGraph(
                simulationResult, rangeDate, ResourceAllocation.COSTS_DATA)
            tableCost = ResourceAllocation.createCostTable(
                simulationResult, 'Total')
            tableCostParcial = ResourceAllocation.createCostTable(
                simulationResultParcial, 'Parcial')
            simulationResultCard = GenericCode.createResultsCard(
                [figRegulation, figNoRegulation], 'Simulation')
            parcialResultCard = GenericCode.createResultsCard([summaryHeader, summaryTableParcial,
                                                               sunburstRegulationParcial, sunburstNoRegulationParcial], 'Parcial Results')
            totalResultCard = GenericCode.createResultsCard([summaryHeader, summaryTable,
                                                             sunburstRegulation, sunburstNoRegulation], 'Total Results')
            costResultCard = GenericCode.createResultsCard([figCost, tableTotalCostHeader, tableCost, tableParcialCostHeader, tableCostParcial],
                                                           'Prices', {'type': f'{pageId}ResultCard', 'key': 'costData'})

            return [alignGraphsButton, simulationResultCard, parcialResultCard, totalResultCard, costResultCard], csvNotDisplayed

        if resultTab == tabTable:
            return [dbc.Label(titleLabel, class_name='label-table font-weight-bold', size=14),
                    ResourceAllocation.createSimulationTable(simulationResult),
                    summaryHeader, summaryTable], []

        return [dbc.Alert('Unexpected error', color='danger')], csvNotDisplayed

    def createCostTable(simulationResult, typeTable):
        costData = ResourceAllocation.getTableCostsData(simulationResult)

        return dash_table.DataTable(
            id={'type': f'summary{typeTable}',
                'key': 'resourceAllocationCostDataTable'},
            data=costData,
            columns=ResourceAllocation.COLUMNS_COSTS,
            style_table={'overflowX': 'auto', 'min-width': '100%'},
            style_cell={'textAlign': 'left', 'maxWidth': '100%'},
            style_header={
                'border': '1px solid green', 'maxWidth': '100%'})

    def getResultStoreData(storeData, parameters, withoutFailures, startDate, endDate, locationValue, locationOptions):
        storeData['Parameters'] = parameters
        storeData['Failures'] = withoutFailures
        storeData['Dates'] = {
            'StartDate': startDate, 'EndDate': endDate}
        # Se obtiene la localización de donde se están cogiendo los datos
        storeData['Location'] = GenericCode.getLocationLabel(
            locationOptions, locationValue)

        return storeData

    def setSimulationRestrictions(parameters):
        if parameters['initial_lower_tank_volume'] > parameters['lower_tank_volume']:
            return True, 'Lower tank volume must be higher than initial lower tank volume'

        if parameters['initial_upper_tank_volume'] > parameters['upper_tank_volume']:
            return True, 'Upper tank volume must be higher than initial upper tank volume'

        if (parameters['initial_upper_tank_volume'] +
            parameters['initial_lower_tank_volume']) > min(parameters['upper_tank_volume'],
                                                           parameters['lower_tank_volume']):
            return True, '''The sum of initial upper tank volume and initial lower tank volume,
                                   must be lower than the minimum value of upper tank volume and lower tank volume'''

        return False, ''

    def setMaxDateAllowed(area):
        maxDateAllowedCode = f"""SELECT MAX(d.date) AS Date
                                	 FROM [inasolar].[dbo].[ForecastWeather] f
                                	 INNER JOIN Dates d ON f.date = d.id
                                  	 WHERE Area={area}"""
        return GenericCode.getAndParseDate(maxDateAllowedCode)

    def setColumnsSummary(optimize=False, ranking=False):
        tableColumns = []
        summaryColumns = ALLOCATION_PARAMETERS_SUMMARY_SQL
        tableNameHeaderAux = ''
        tableNameHeaderMainWR = ''
        WRColumnsAux = []
        newHeader = False
        if not optimize:
            tableColumns.append(
                {'name': ['', 'Simulation'], 'id': 'Simulation'})

        else:
            tableColumns = [
                {'name': ['Scenario', 'Scenario'], 'id': 'Scenario'}]
            for index, row in OPTIMIZATION_PARAMETERS_SUMMARY_SQL.iterrows():
                tableColumns.append(
                    {'name': ['', f'{row["Name"]}({row["Unity"].strip()})'], 'id': row['IdParameter'],
                     'type': row['Type']})

            if ranking:
                tableColumns.extend([{'name': ['', 'Score'], 'id': 'Score', 'type': 'Score'},
                                     {'name': ['', 'Score WR'], 'id': 'ScoreWR', 'type': 'Score'}])

            summaryColumns = ALLOCATION_PARAMETERS_OPTIMIZATION_SQL

        for index, row in summaryColumns.iterrows():
            tableNameHeaderMain = ''
            tableNameHeaderSub = row['Name']
            if (row['GraphLabel'] != None):
                tableNameHeaderMain = f'{row["GraphLabel"]}({row["Unity"].strip()})'

            else:
                tableNameHeaderSub += f'({row["Unity"].strip()})'

            # Se comprueba que el header de la tabla ha cambiado, para añadir los de con regulación
            if tableNameHeaderAux != '' and tableNameHeaderMain != tableNameHeaderAux:
                newHeader = True

            tableNameHeaderAux = tableNameHeaderMain

            # Se añade las columnas de con regulación directamente, cuando hay un header superior, para
            # que salgan consecutivas
            if newHeader:
                tableColumns.extend(WRColumnsAux)
                WRColumnsAux.clear()
                newHeader = False

            tableColumns.append(
                {'name': [tableNameHeaderMain, tableNameHeaderSub], 'id': row['IdParameter']})

            if optimize:
                tableNameHeaderSubWR = row['Name']
                # Si hay header superior, se añade en una lista aparte para añadirlos a las columnas directamente,
                # en caso contrario se ponen de forma consecutiva las columnas sin y con regulación
                if tableNameHeaderMain != '':
                    tableNameHeaderMainWR = f'{row["GraphLabel"]} WR({row["Unity"].strip()})'
                    WRColumnsAux.append({'name': [
                                        tableNameHeaderMainWR, tableNameHeaderSubWR], 'id': f'{row["IdParameter"]}WR'})

                else:
                    tableNameHeaderSubWR += f' WR({row["Unity"].strip()})'
                    tableColumns.append(
                        {'name': ['', tableNameHeaderSubWR], 'id': f'{row["IdParameter"]}WR'})

        return tableColumns

    def createSummaryTable(summary, typeTable):
        return dash_table.DataTable(
            id={'type': f'summary{typeTable}',
                'key': 'resourceAllocationSummaryDataTable'},
            data=summary,
            columns=ResourceAllocation.COLUMNS_SUMMARY,
            style_table={'overflowX': 'auto',
                         'min-width': '100%', 'margin-bottom': '5%'},
            style_cell={'textAlign': 'left', 'maxWidth': '100%'},
            style_header={
                'border': '1px solid green', 'maxWidth': '100%'},
            style_data_conditional=[
                GenericCode.getColumnColor('Simulation', 'rgb(199,199,199)', 'black')],
            merge_duplicate_headers=True)

    def numOfDays(date1, date2):
      # check which date is greater to avoid days output in -ve number
        if date2 > date1:
            return (date2-date1).days
        else:
            return (date1-date2).days

    def generateRangeData(startDate, endDate):
        startDateDt = datetime.strptime(startDate, '%Y-%m-%d')
        endDateDt = datetime.strptime(endDate, '%Y-%m-%d')
        rangeDaysDifference = ResourceAllocation.numOfDays(
            startDateDt, endDateDt)
        if rangeDaysDifference > 7:
            return [datetime.strptime(
                endDate, '%Y-%m-%d')-timedelta(days=7), endDate]

        return None

    def setColumnsTable(allocationParameters, columns=[]):
        for index, row in allocationParameters.iterrows():
            columns.append(
                {'name': f'{row["Name"]}({row["Unity"].strip()})', 'id': row['IdParameter'],
                 'type': row['Type']})

        return columns

    def createSimulationTable(simulationResult):
        # Se recuperan las columnas que se deben de redondear a dígitos distintos a 2
        electricityPrice = simulationResult[['ElectricityGridPrice', 'ElectricitySurplusPrice']].map(
            lambda x: GenericCode.roundNumber(x, digitsRounded=8))
        # Se eliminan del dataframe original las columnas con distinto redondeo para añadirlas posteriormente
        simulationResult = simulationResult.drop(['ElectricityGridPrice', 'ElectricitySurplusPrice'], axis=1).map(
            GenericCode.roundNumber)

        return dash_table.DataTable(
            id='resourceAllocationDatatable',
            data=pd.concat([simulationResult, electricityPrice],
                           axis=1).to_dict('records'),
            columns=ResourceAllocation.COLUMNS_SIMULATION,
            sort_action='native',
            page_action='none',
            style_table={'overflowX': 'auto', 'min-width': '100%',
                         'overflowY': 'auto', 'height': '50vh'},
            style_cell={'textAlign': 'left', 'maxWidth': '100%'},
            style_header={
                'border': '1px solid green', 'maxWidth': '100%'},
            style_cell_conditional=ResourceAllocation.COLUMNS_SIMULATION_COLUMN_WIDTH,
            style_data_conditional=[
                GenericCode.getColumnColor(
                    'photovoltaic', '#dbe40e', 'black', 'column_type'),
                GenericCode.getColumnColor(
                    'windPower', '#308e37', 'black', 'column_type'),
                GenericCode.getColumnColor(
                    'biogas', '#ff8c16', 'black', 'column_type'),
                GenericCode.getColumnColor('hydraulic', '#0d66e8', 'black', 'column_type')],
            style_header_conditional=[
                GenericCode.getColumnColor(
                    'photovoltaic', '#dbe40e', 'black', 'column_type'),
                GenericCode.getColumnColor(
                    'windPower', '#308e37', 'black', 'column_type'),
                GenericCode.getColumnColor(
                    'biogas', '#ff8c16', 'black', 'column_type'),
                GenericCode.getColumnColor('hydraulic', '#0d66e8', 'black', 'column_type')],
            fixed_columns={'headers': True, 'data': 1},
            fixed_rows={'headers': True},
            virtualization=True)

    def getParameterCard(cardType, optimizationParameters={}):
        photovoltaicParameters = generateParameter(
            'photovoltaic', 'color-pv', cardType, optimizationParameters)
        eolicParameters = generateParameter(
            'windPower', 'color-w', cardType, optimizationParameters)
        biogasParameters = generateParameter(
            'biogas', 'color-bg', cardType, optimizationParameters)
        hydraulicParameters = generateParameter(
            'hydraulic', 'color-h', cardType, optimizationParameters)
        modal = GenericCode.createModal('Information', 'resourceAllocation')

        renewablesSizesCard = [
            ResourceAllocation.getParametersRow(
                photovoltaicParameters, eolicParameters),
            ResourceAllocation.getParametersRow(
                biogasParameters, hydraulicParameters),
            modal]

        if cardType == 'reliabilityData':
            # Se añade checkbox para que el usuario indique si quiere que haya fallos
            withoutFailuresCheckBox = dbc.Row([
                dbc.Col(dbc.Checkbox(
                    id="checkboxWithoutFailures",
                    label="Without Failures",
                    value=False,
                    label_class_name="mb-auto"
                ), className='m-4', width='auto'),
                dbc.Col(GenericCode.getInfoButton('openWithoutFailuresInfo'),
                        style={'padding': 0})], align='center')

            renewablesSizesCard.append(withoutFailuresCheckBox)

        return dbc.Card(renewablesSizesCard)

    def getTabsParameters(parameter_df, headerName, renewableType, cardType, className='', optimizationParameters={}):
        cols = []
        for index, row in parameter_df.iterrows():
            parameterId = row['IdParameter']
            cols.append(dbc.Col(
                generateLabelAndInput(
                    f"{row['Name']}({row['Unity']})", parameterId, row['DefaultValue'], 'renewable-parameters', row['ImportChange'],
                    renewableType, row['Disabled'], cardType, parameterId in optimizationParameters.values()), width=6)
            )

        return dbc.Row([GenericCode.getHeaderOfListGroupItem(f"{headerName}",
                                                             f"{renewableType}OpenInfo", className),
                        dbc.Row(cols, align='center')
                        ], align='center')

    def getParametersRow(parameter1, parameter2):
        return dbc.Row([dbc.Col(dbc.ListGroupItem(parameter1, class_name='no-padding-right height-total'),
                                class_name='no-padding-right', width=6),
                        dbc.Col(dbc.ListGroupItem(parameter2, class_name='no-padding-right height-total'),
                                class_name='no-padding-left', width=6)])

    def getRangeAndDemandParametersRow(cardId, minDateAllowed, optimize=False):
        optimizeCol = dbc.Col(width='auto')
        lastOptimizationCol = dbc.Col(width='auto')
        if optimize:
            popOverText = '''The technical data of the scenarios generated by optimizing the proposed solution are displayed  on the "Table" tab.
                             Loading time: 20 sec. by day aprox.'''
            optimizeCol = dbc.Col([dbc.Button('Optimize', className='mt-auto', id=f'{cardId}OptimizeButton'),
                                   dbc.Popover(
                popOverText,
                target=f'{cardId}OptimizeButton',
                body=True,
                trigger="hover",
            )],
                width='auto')
            lastOptimizationCol = dbc.Col(dbc.Button('Last Optimization', className='mt-auto', id=f'{cardId}LastOptimizationButton'),
                                          width='auto')

        selectDemandRow = ResourceAllocation.getSelectDemandRow()

        return dbc.Row([dbc.Col(dbc.ListGroupItem([
            selectDemandRow,
            dbc.Row([
                dbc.Col(generateLabelAndInput(
                    'Max demand(kW)', 'max_demand', GenericCode.MAX_DEMAND, 'renewable-parameters', True,
                    'resource', cardType='resource'), width=4, class_name='pt-3'
                ),
                dbc.Col(
                    dbc.Row(GenericCode.createRange(f'{cardId}IntervalDatePicker', minDateAllowed),
                            class_name='py-3', align='center'
                            ),
                    width='auto', class_name='padding-left'),
                dbc.Col(
                    dbc.Button(
                        'Simulate', className='mt-auto', id=f'{cardId}SimulateButton'
                    ), width='auto'
                ),
                optimizeCol,
                lastOptimizationCol
            ], align='center')]
        ), width=12)], class_name='py-3', align='center')

    def getSelectDemandRow():
        # Solo se pueden seleccionar estas tres opciones
        demandDataSql = pd.read_sql(
            """SELECT nombre_dato AS id, CONCAT(nombre_alternativo, ' (', TRIM(unidad), ')') AS Name
                FROM descripcionDatos
                WHERE Tabla = 'datosGEDER2'
                AND (nombre_dato = 'Power' OR nombre_dato = 'MaxDemandaPActivaIIIT1' OR nombre_dato = 'MaxDemandaPActivaMaxIIIT1')""", GenericCode.engine)

        return dbc.Row([
            dbc.Col(
                dbc.Row([
                    dbc.Col('Select demand', width=4),
                    dbc.Col(
                        dcc.Dropdown(id='selectDemand',
                                     options=GenericCode.setDropdownOptions(demandDataSql), value='Power', clearable=False), width=8, className='px-0'
                    )
                ], align='center'), width=4
            )
        ], className='pt-4')

    def disableButton(renewableParametersValue, valueToDisable=0):
        # Se comprueba que haya valor en los inputs y que sea positivo
        if any(ResourceAllocation.emptyOrOutOfBounds(num, valueToDisable) for num in renewableParametersValue):
            return True

        return False

    def emptyOrOutOfBounds(num, valueToDisable=0):
        return type(num) == type(None) or float(num) < valueToDisable

    def generateGraph(numGraph, graphData, potDem, simulationResult, rangeDate, titleLabel):
        fig = go.Figure(make_subplots(specs=[[{"secondary_y": True}]]))
        # Filtrar los datos para que recupere los datos de la primera gráfica o la segunda
        graphDataFilter = graphData[graphData['GraphType'].str.endswith(
            numGraph)]
        for index, graphParameter in graphDataFilter.iterrows():
            parameter = graphParameter['IdParameter']
            parameterUnit = graphParameter['Unity'].strip()
            lineStyle = dict(color=graphParameter['GraphColor'], width=0)
            visible = True
            secondary_y = False
            if graphParameter['Disabled']:
                visible = 'legendonly'
                secondary_y = True

            # Comprobramos que tipo de línea queremos que se muestre para cada parámetro
            if graphParameter['GraphType'].startswith('Area'):
                stackGroup = 'one'
                fill = None
                if parameter.startswith('PotBombeo2'):
                    stackGroup = None
                    fill = 'tozeroy'

                fig.add_trace(go.Scatter(
                    x=simulationResult['Date'], y=simulationResult[parameter],
                    name=graphParameter['GraphLabel'],
                    hoverinfo='x+y',
                    mode='lines',
                    line=lineStyle,
                    stackgroup=stackGroup,
                    fill=fill,
                    hovertemplate='%{y:.2f}' + ' %s' % parameterUnit,
                    line_shape='hv',
                    visible=visible
                ), secondary_y=secondary_y)

            else:
                if graphParameter['GraphType'] == 'Dash':
                    lineStyle['dash'] = 'dot'

                lineStyle['width'] = 3

                fig.add_trace(go.Scatter(
                    x=simulationResult['Date'], y=simulationResult[parameter],
                    name=graphParameter['GraphLabel'],
                    mode='lines',
                    line_shape='hv',
                    line=lineStyle,
                    hovertemplate='%{y:.2f}' + ' %s' % parameterUnit,
                    visible=visible
                ), secondary_y=secondary_y)

        fig.add_trace(go.Scatter(
            x=simulationResult['Date'], y=simulationResult['PotDem'],
            name=potDem['GraphLabel'],
            mode='lines',
            line_shape='hv',
            line={'width': 5, 'dash': '10px,5px',
                  'color': potDem['GraphColor']},
            hovertemplate='%{y:.2f}' + ' %s' % potDem['Unity']
        ))

        fig.update_xaxes(nticks=7, rangeslider_visible=True,
                         rangeselector=GenericCode.getGraphRangeSelector(
                             'resourceAllocation'),
                         tickformatstops=GenericCode.getGraphTickFormatStops(),
                         range=rangeDate, uirevision='time')

        if numGraph == '1':
            titleLabel += ' - With Regulation'
        else:
            titleLabel += ' - Without Regulation'

        fig.update_layout(title=titleLabel,
                          yaxis_title='Power (kW)',
                          yaxis2=dict(title='SoS: State of Storage (%)',
                                      overlaying='y', side='right', showgrid=False),
                          xaxis_title='Date',
                          hovermode='x unified',
                          uirevision='time')

        return dcc.Graph(id={'type': 'resultGraphs', 'key': f'graphResourceAllocation{numGraph}'}, figure=fig, config={'displaylogo': False})

    def generateCostGraph(simulationResult, rangeDate, costsData):
        formatedGraphData = []
        # Filtrar los datos para que recupere los datos de la primera gráfica o la segunda
        for index, graphParameter in costsData.iterrows():
            parameterUnit = graphParameter['Unity'].strip()
            formatedGraphData.append({'IdParameter': graphParameter['IdParameter'],
                                      'GraphLabel': graphParameter['GraphLabel'],
                                      'GraphHover': parameterUnit,
                                      'GraphTitle': 'Cost (€)',
                                      'GraphColor': graphParameter['GraphColor'],
                                      'SecondaryY': False})

        return GenericCode.generateGraph(simulationResult, pd.DataFrame(formatedGraphData), {'type': 'resultGraphs', 'key': 'costResourceAllocation'},
                                         rangeDate, 'Cost comparison', False)

    def getTableTitle(labelTitle, infoButton, download, href):
        return dbc.Row([
            dbc.Col(
                dbc.Label(labelTitle, class_name='label-table font-weight-bold', size=14), width='auto'),
            dbc.Col(GenericCode.getInfoButton(
                infoButton, download, href), width='auto')
        ], justify='between', className='py-3')

    def getDataTab(parameterCard):
        return dbc.Card(dbc.CardBody(html.Div([dbc.CardGroup(
            [parameterCard]
        )]), className='p-0'))

    def createParametersTabs(resultId):
        technicalDataTab = ResourceAllocation.getDataTab(
            ResourceAllocation.getParameterCard('technicalData', OPTIMIZATION_PARAMETERS_SUMMARY_SQL['IdParameter'].to_dict()))
        economicalDataTab = ResourceAllocation.getDataTab(
            ResourceAllocation.getParameterCard('economicalData'))
        reliabilityDataTab = ResourceAllocation.getDataTab(
            ResourceAllocation.getParameterCard('reliabilityData'))

        return dbc.Tabs([
            dbc.Tab(technicalDataTab, label='Technical Data',
                    tab_id=f'{resultId}-tab-technical'),
            dbc.Tab(economicalDataTab, label='Economical Data',
                    tab_id=f'{resultId}-tab-economical'),
            dbc.Tab(reliabilityDataTab, label='Reliability',
                    tab_id=f'{resultId}-tab-reliability')
        ], className='card-header')

    def setMaxDateAllowedAndDisabledDays(area):
        datesAllowedCode = f"""SELECT MIN(MaxDate) AS DateMax, MAX(MinDate) AS DateMin
                                 FROM (SELECT MAX(dat.Date) AS MaxDate, MIN(dat.Date) AS MinDate
                                    FROM Dates dat
                                    INNER JOIN datosGEDER2 datos ON datos.Date = dat.id
                                    INNER JOIN Locations l ON datos.location = l.id
                                    WHERE l.Type = 'Generator' AND l.Area = {area} AND Power IS NOT NULL
                                    UNION
                                    SELECT MAX(dat.Date) AS MaxDate, MIN(dat.Date) AS MinDate
                                    FROM Dates dat
                                    INNER JOIN datosGEDER2 datos ON datos.Date = dat.id
                                    INNER JOIN HistoricalWeather h ON h.date = dat.id
                                    WHERE h.Area = {area} AND Power IS NOT NULL) AS Dates"""
        datesAllowedSql = pd.read_sql(datesAllowedCode, GenericCode.engine)
        datesParsed = datesAllowedSql.iloc[0]
        maxDateAllowed = datetime.strptime(
            str(datesParsed['DateMax']), '%Y-%m-%d %H:%M:%S').date()
        minDateAllowed = datetime.strptime(
            str(datesParsed['DateMin']), '%Y-%m-%d %H:%M:%S').date()

        return maxDateAllowed, minDateAllowed

    def generateRenewablesSizes(renewableParametersId, resourceAllocationDataParameters):
        photovoltaicSizes = {}
        windPowerSizes = {}
        biogasSizes = {}
        hydraulicSizes = {}
        resourceSizes = {}

        # Asignamos a cada renovable sus valores
        for parameter in renewableParametersId:
            renewable = parameter.get('renewable', None)
            parameterId = parameter['key']
            if renewable == 'photovoltaic':
                photovoltaicSizes[parameterId] = resourceAllocationDataParameters[parameterId]
            elif renewable == 'windPower':
                windPowerSizes[parameterId] = resourceAllocationDataParameters[parameterId]
            elif renewable == 'biogas':
                biogasSizes[parameterId] = resourceAllocationDataParameters[parameterId]
            elif renewable == 'hydraulic':
                hydraulicSizes[parameterId] = resourceAllocationDataParameters[parameterId]
            elif renewable == 'resource':
                resourceSizes[parameterId] = resourceAllocationDataParameters[parameterId]

        photovoltaicParameters = {'Title': 'Photovoltaic',
                                  'Data': pd.DataFrame([photovoltaicSizes])}
        windPowerParameters = {'Title': 'Wind Power',
                               'Data': pd.DataFrame([windPowerSizes])}
        biogasParameters = {'Title': 'Biogas',
                            'Data': pd.DataFrame([biogasSizes])}
        hydraulicParameters = {'Title': 'Hydraulic',
                               'Data': pd.DataFrame([hydraulicSizes])}
        resourceParameters = {'Title': 'Resource',
                              'Data': pd.DataFrame([resourceSizes])}

        return photovoltaicParameters, windPowerParameters, biogasParameters, hydraulicParameters, resourceParameters

    def getColumnsWidth(columnsParameters):
        columnsWidth = []
        for index, row in columnsParameters.iterrows():
            columnWidth = row['ColumnWidth']
            columnParameter = row['IdParameter']

            # Buscamos la posición de la lista que contiene el 'ColumnWidth' específico
            pos = next((index for index, columnWidth in enumerate(
                columnsWidth) if columnWidth['width'] == columnWidth), None)

            if pos is not None:
                columnsWidth[pos]['if']['column_id'].append(columnParameter)
            else:
                columnsWidth.append(
                    {'if': {'column_id': [columnParameter]}, 'width': columnWidth})

        return columnsWidth

    def exportParametersToExcel(parametersSheetData):
        output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        parametersSheetName = 'Parameters'
        # La hoja de parámetros se va separando según las renovables existentes
        parametersSheetData[0]['Data'].to_excel(
            writer, sheet_name=parametersSheetName, startrow=1, index=False)
        worksheet = writer.sheets[parametersSheetName]
        worksheet.write(0, 0, parametersSheetData[0]['Title'])
        # El primer diccionario de la lista se pone directamente en la hoja, ya que es lo que
        # hace que se cree la hoja
        for sheet2Info in parametersSheetData[1:]:
            writer.sheets[parametersSheetName].write(
                writer.sheets[parametersSheetName].dim_rowmax + 2, 0, sheet2Info['Title'])
            sheet2Info['Data'].to_excel(writer, sheet_name=parametersSheetName,
                                        startrow=writer.sheets[parametersSheetName].dim_rowmax + 1, index=False)

        return writer, output

    def createAnnotationLegend(fig, x, y, text, fontSize):
        fig.add_annotation(dict(x=x,
                                y=y,
                                showarrow=False,
                                text=text,
                                textangle=0,
                                yanchor='top',
                                xanchor='left',
                                xref="paper",
                                yref="paper",
                                font=dict(size=fontSize)))

        return fig

    def createShapeLegend(fig, x0, x1, y0, y1, fillcolor, lineWidth, textLabel):
        fig.add_shape(
            type="rect",
            x0=x0,
            x1=x1,
            y0=y0,
            y1=y1,
            line_width=lineWidth,
            fillcolor=fillcolor,
            label=dict(text=textLabel))

        return fig

    def createSunburstLegend(fig, sunburstParents, sunburstLabels, sunburstColors):
        # Se colocan los valores de posición manualmente, ya que no existe función nativa para añadir
        # la leyenda. (En algunas pantallas puede solaparse con el gráfico)
        fig = ResourceAllocation.createAnnotationLegend(
            fig, 0.75, 1, 'Resource type', 16)
        fig = ResourceAllocation.createShapeLegend(
            fig, 0.75, 1, 0.89, 0.89, None, 3, None)
        pos = 0
        for i, m in enumerate(sunburstParents):
            if m == '':
                fig = ResourceAllocation.createAnnotationLegend(
                    fig, 0.8, 0.85-(pos/10), sunburstLabels[i], 11)
                fig = ResourceAllocation.createShapeLegend(fig, 0.75, 0.775, 0.815-(pos/10), 0.85-(pos/10),
                                                           sunburstColors[i], None, None)
                pos = pos + 0.75

        fig = ResourceAllocation.createAnnotationLegend(
            fig, 0.75, 0.4, 'Resource use', 16)
        fig = ResourceAllocation.createShapeLegend(
            fig, 0.75, 1, 0.3, 0.3, None, 3, None)

        fig = ResourceAllocation.createAnnotationLegend(
            fig, 0.8, 0.25, 'Surplus', 11)
        fig = ResourceAllocation.createShapeLegend(
            fig, 0.75, 0.775, 0.215, 0.25, None, None, '///')

        fig = ResourceAllocation.createAnnotationLegend(
            fig, 0.8, 0.175, 'Pump', 11)
        fig = ResourceAllocation.createShapeLegend(
            fig, 0.75, 0.775, 0.14, 0.175, None, None, '....')

        fig = ResourceAllocation.createAnnotationLegend(
            fig, 0.8, 0.1, 'Load', 11)
        fig = ResourceAllocation.createShapeLegend(
            fig, 0.75, 0.775, 0.065, 0.1, None, None, None)

        return fig

    def generateSunburstGraph(simulationResult, modified, graphTitle, typeGraph):
        # Se añaden los parámetros que se utilizan en el sunburst
        sunburstIds, sunburstLabels, sunburstParents, sunburstValues, sunburstPattern, sunburstColors = [], [], [], [], [], []
        for colName, row in ResourceAllocation.SUNBURST_DATA.iterrows():
            paramId = row['IdParameter']
            sunburstIds.append(paramId)
            sunburstLabels.append(row['GraphLabel'])
            sunburstValues.append(
                abs(simulationResult[paramId + modified].sum()))
            # Si el parámetro es el principal (padre) no se indica parent, en caso contrario, el padre al que pertenece
            # el hijo vendrá indicado en el ID después de un guión
            sunburstParents.append(paramId.split(
                '-')[1] if row['ParameterType'] == 'sunburstChildData' else '')
            sunburstColors.append(row['GraphColor'])
            sunburstPattern.append(
                "/" if 'Surplus' in paramId else ("." if 'PotBombeo2' in paramId else ""))

        fig = go.Figure(go.Sunburst(
            ids=sunburstIds,
            labels=sunburstLabels,
            parents=sunburstParents,
            values=sunburstValues,
            branchvalues='total',
            marker=dict(
                        pattern=dict(
                            shape=sunburstPattern, solidity=0.9
                        ),
                        colors=sunburstColors
                        ),
            hovertemplate='<b>%{label} %{parent}</b><br>%{value:.2f} kWh',
            name='Renewables usage'
        ))

        fig = ResourceAllocation.createSunburstLegend(
            fig, sunburstParents, sunburstLabels, sunburstColors)

        # Update the traces to show labels and percentages
        fig.update_traces(textinfo='label+percent parent')
        fig.update_layout(title=f'Renewable Percentage - {graphTitle}')

        return dcc.Graph(id={'type': f'sunburstGraph{typeGraph}', 'key': f'resourceAllocationSunburstRenewablesSum{modified}'}, figure=fig, config={'displaylogo': False},
                         className='resourceAllocationSunburstGraph')

    def searchNewMaxDemand(locationData, demandSelected):
        GenericCode.MAX_DEMAND = GenericCode.getMaxDemand(
            locationData['Location'], demandSelected)

        return GenericCode.MAX_DEMAND

    def copyScenarioParameters(parametersIds, parameter, paramsCard, scenarioValue):
        # Se busca la posición que corresponde con el parámetro actual en la lista de IDs, que es la misma que la posición
        # en la lista de valores
        paramIndex = next((indice for indice, paramDict in enumerate(
            parametersIds) if paramDict.get('key') == parameter), None)
        if paramIndex != None:
            paramsCard[paramIndex] = scenarioValue

        return paramsCard

    def getParcialSummary(simulationResult, rangeDate):
        simulationResultParcial = simulationResult[(simulationResult['Date'] >= parser.parse(rangeDate[0]))
                                                       & (simulationResult['Date'] <= parser.parse(rangeDate[1]))]

        return simulationResultParcial, simulator.get_summary(simulationResultParcial, False)

    def getSunburstData(simulationResultParcial):
        sunburstValues, sunburstValuesModified = [], []
        for colName, row in ResourceAllocation.SUNBURST_DATA.iterrows():
            paramId = row['IdParameter']
            sunburstValues.append(
                abs(simulationResultParcial[paramId].sum()))
            sunburstValuesModified.append(
                abs(simulationResultParcial[f'{paramId}Modified'].sum()))

        return sunburstValues, sunburstValuesModified

    def getTableCostsData(simulationResult):
        costData = pd.DataFrame(
            simulationResult[ResourceAllocation.COSTS_DATA['IdParameter']].sum()).T
        costData = costData.map(
            GenericCode.roundNumber).to_dict('records')
        
        return costData

    # VARIABLES
    # ---------------------------------------------------------------
    COLUMNS_SUMMARY = setColumnsSummary(False)
    COLUMNS_OPTIMIZATION = setColumnsSummary(True)
    COLUMNS_SIMULATION = setColumnsTable(
        ALLOCATION_PARAMETERS_RENEWABLES_RESULT_SQL, [{'name': 'Date', 'id': 'Date'}])
    COLUMNS_SIMULATION_COLUMN_WIDTH = getColumnsWidth(
        ALLOCATION_PARAMETERS_RENEWABLES_RESULT_SQL)
    GRAPH_DATA = ALLOCATION_PARAMETERS_RENEWABLES_RESULT_SQL.dropna(
        subset=['GraphType']).sort_values(by='GraphOrder')
    COSTS_DATA = GRAPH_DATA[GRAPH_DATA['GraphType'].str.endswith('3')]
    SUNBURST_DATA = pd.read_sql(
        "SELECT * FROM AllocationParameters WHERE GraphType = 'Sunburst'", GenericCode.engine)
    COLUMNS_COSTS = setColumnsTable(COSTS_DATA)

    # CALLBACKS
    # ---------------------------------------------------------------
    @callback(
        Output('selectDemand', 'disabled'),
        Input('locationData', 'data'),
    )
    def disableSelectDemandDropdown(locationData):
        # Solo se puede seleccionar demanda en Aras
        return locationData['Location'] != 1

    @callback(
        Output('selectDemand', 'value'),
        Input('locationData', 'data'),
        State('selectDemand', 'value')
    )
    def changeSelectDemandDropdown(locationData, oldDemand):
        # Solo se puede seleccionar demanda en Aras, en el resto de ubicaciones será Power
        if locationData['Location'] != 1:
            return 'Power'

        return oldDemand

    @callback(
        Output({'type': 'renewable-parameters', 'key': ALL, 'renewable': ALL, 'cardType': ALL,
                'scenarioUpdated': ALL, 'importChange': True}, 'value'),
        State({'type': 'renewable-parameters', 'key': ALL, 'renewable': ALL, 'cardType': ALL,
               'scenarioUpdated': ALL, 'importChange': True}, 'id'),
        State({'type': 'renewable-parameters', 'key': ALL, 'renewable': ALL, 'cardType': ALL,
               'scenarioUpdated': ALL, 'importChange': True}, 'value'),
        Input({'type': 'storeData', 'key': ALL}, 'data'),
        Input({'type': ALL, 'key': 'copyDataButton'}, 'n_clicks'),
        Input('locationData', 'data'),
        Input('selectDemand', 'value'),
        State({'type': ALL, 'key': 'scenarioKey'}, 'value'),
        State({'type': 'renewable-parameters', 'key': ALL, 'renewable': ALL, 'cardType': 'technicalData',
               'scenarioUpdated': True, 'importChange': ALL}, 'id'),
        prevent_initial_call=True
    )
    def importRenewableParameters(parametersIds, oldData, resourceAllocationData, copyDataButton,
                                  locationData, demandSelected, scenarioSelected, scenarioUpdatedIds):
        if ctx.triggered_id == 'locationData' or ctx.triggered_id == 'selectDemand':
            maxDemandPos = next((i for i, param in enumerate(
                parametersIds) if param['key'] == 'max_demand'), None)
            oldData[maxDemandPos] = ResourceAllocation.searchNewMaxDemand(
                locationData, demandSelected)

            return oldData

        if not ctx.triggered_id:
            return oldData

        if ctx.triggered_id['key'] == 'resourceAllocationData' and resourceAllocationData and 'Parameters' in resourceAllocationData[0]:
            for parameter, value in resourceAllocationData[0]['Parameters'].items():
                oldData = ResourceAllocation.copyScenarioParameters(
                    parametersIds, parameter, oldData, value)

            return oldData

        # Se comprueba si se ha pulsado en el botón de copiar escenario
        if len(copyDataButton) > 0 and copyDataButton[0]:
            # Se recupera el valor del escenario seleccionado, que corresponde con el índice almacenado en el Store
            scenarioData = resourceAllocationData[0]['Optimization'][scenarioSelected[0]]
            # Se copian todos los valores que pueden variar en los escenarios
            for scenarioParameterId in scenarioUpdatedIds:
                paramId = scenarioParameterId['key']
                oldData = ResourceAllocation.copyScenarioParameters(
                    parametersIds, paramId, oldData, scenarioData[paramId])

        return oldData

    @callback(
        Output({'type': 'resultGraphs', 'key': ALL}, 'figure'),
        Output({'type': 'sunburstGraphParcial', 'key': ALL}, 'figure'),
        Output({'type': 'summaryParcial', 'key': ALL}, 'data'),
        Input({'type': 'resultButton', 'key': ALL, 'page': ALL}, 'n_clicks'),
        State({'type': 'resultGraphs', 'key': ALL}, 'figure'),
        State({'type': 'storeData', 'key': ALL}, 'data'),
        State({'type': 'sunburstGraphParcial', 'key': ALL}, 'figure'),
        State({'type': 'summaryParcial', 'key': ALL}, 'data'),
        prevent_initial_call=True
    )
    def alignGraphs(alignGraph, actualFigures, storeData, oldSunburstGraph, oldSummary):
        if alignGraph:
            targetFigureXAxis = actualFigures[0]['layout']['xaxis']
            rangeDate = targetFigureXAxis['range']
            for figure in actualFigures:
                figure['layout']['xaxis'] = targetFigureXAxis

            if ctx.triggered_id['page'] == 'resourceAllocation':
                simulationResult = GenericCode.readJSON(
                    storeData[0]['Simulation'])

            else:
                simulationResult = GenericCode.readJSON(
                    storeData[1]['Simulation'])

            simulationResultParcial, summaryParcial = ResourceAllocation.getParcialSummary(
                simulationResult, rangeDate)
            sunburstValues, sunburstValuesModified = ResourceAllocation.getSunburstData(
                simulationResultParcial)
            oldSunburstGraph[0]['data'][0]['values'] = sunburstValuesModified
            oldSunburstGraph[1]['data'][0]['values'] = sunburstValues
            costData = ResourceAllocation.getTableCostsData(simulationResultParcial)
            
        return actualFigures, oldSunburstGraph, [summaryParcial, costData]

    @callback(
        Output('resourceAllocationCardInfo', 'is_open'),
        Output('resourceAllocationInfoBody', 'children'),
        Input('photovoltaicOpenInfo', 'n_clicks'),
        Input('windPowerOpenInfo', 'n_clicks'),
        Input('biogasOpenInfo', 'n_clicks'),
        Input('hydraulicOpenInfo', 'n_clicks'),
        Input('openWithoutFailuresInfo', 'n_clicks'),
        Input('resourceAllocationCloseCardInfo', 'n_clicks'),
        prevent_initial_call=True
    )
    def openCardInfoModal(photovoltaicOpenInfo, windPowerOpenInfo, biogasOpenInfo, hydraulicOpenInfo,
                          openWithoutFailuresInfo, resourceAllocationCloseCardInfo):
        if ctx.triggered_id == 'photovoltaicOpenInfo' and photovoltaicOpenInfo:
            listInfo = dcc.Markdown('''
                                    * **Total power** of the photovoltaic plant
                                    ''')
            return True, listInfo

        if ctx.triggered_id == 'windPowerOpenInfo' and windPowerOpenInfo:
            listInfo = dcc.Markdown('''
                                    * **Total power** of the wind power plant can be selected
                                    * **Min wind speed** for the generator to run
                                    * **Max wind speed** needed for the generator to run at max power
                                    * When wind reach **stop speed**, generator stops
                                    ''')
            return True, listInfo

        if ctx.triggered_id == 'biogasOpenInfo' and biogasOpenInfo:
            listInfo = dcc.Markdown('''
                                    * The simulation can start with an **initial gas** storage
                                    * The **min regulation power** allowed in the generator can be selected
                                    ''')
            return True, listInfo

        if ctx.triggered_id == 'hydraulicOpenInfo' and hydraulicOpenInfo:
            listInfo = dcc.Markdown('''
                                    * In this scenario, **two closed tanks** are considered with no posibilities for
                                      extern filling or emptying
                                    * The sum of the initial upper tank volume (iutv) and the initial lower tank volume (iltv)
                                      must be more or equal than the min volume between the lower tank (ltv) and
                                      the upper tank (utv):                                  
                                      **iutv+iltv >= min(ltv,utv)**
                                    * The **hydraulic jump** is the height difference between both tanks
                                    * The **performance** of the turbine and the pump can be selected                                
                                    ''')
            return True, listInfo

        if ctx.triggered_id == 'openWithoutFailuresInfo' and openWithoutFailuresInfo:
            listInfo = dcc.Markdown(
                '* Select if simulation or optimization **without failures** is required')
            return True, listInfo

        return False, ''

    @callback(
        Output({'type': 'renewable-parameters', 'key': 'generator_min_power', 'renewable': 'biogas', 'cardType': 'technicalData',
                'scenarioUpdated': False, 'importChange': False}, 'value'),
        Input({'type': 'renewable-parameters', 'key': 'generator_max_power',
              'renewable': 'biogas', 'cardType': 'technicalData', 'scenarioUpdated': True, 'importChange': True}, 'value'),
        State({'type': 'renewable-parameters', 'key': 'generator_min_power', 'renewable': 'biogas',
               'cardType': 'technicalData', 'scenarioUpdated': False, 'importChange': False}, 'value'),
    )
    def getBiogasMinPower(biogasMaxPower, oldValue):
        if not ResourceAllocation.emptyOrOutOfBounds(biogasMaxPower):
            return simulator.getBiogasMinPower(biogasMaxPower)

        return oldValue

    @callback(
        Output({'type': 'renewable-parameters', 'key': 'gas_initial_volume', 'renewable': 'biogas',
                'cardType': 'technicalData', 'scenarioUpdated': False, 'importChange': False}, 'value'),
        Input({'type': 'renewable-parameters', 'key': 'digester_volume',
              'renewable': 'biogas', 'cardType': 'technicalData', 'scenarioUpdated': True, 'importChange': True}, 'value'),
        Input({'type': 'scenario-dropdown', 'key': ALL}, 'n_clicks'),
        State({'type': 'scenario-dropdown', 'key': ALL}, 'value'),
        Input({'type': 'storeData', 'key': ALL}, 'data'),
        State({'type': 'renewable-parameters', 'key': 'gas_initial_volume', 'renewable': 'biogas',
               'cardType': 'technicalData', 'scenarioUpdated': False, 'importChange': False}, 'value'),
        prevent_initial_call=True
    )
    def getBiogasGasInitialVolume(digesterVolume, copyDataButton, scenarioSelected, storeData, oldValue):
        if not ctx.triggered_id:
            return oldValue

        else:
            storeData = storeData[0]

        # Esta comprobación sirve para saber si se ha importado los parámetros de un Excel, o copiando un escenario de la Optimización
        if ctx.triggered_id['type'] == 'storeData':
            # Se comprueba si se ha pulsado en Importar y luego se ha cerrado la ventana emergente
            if 'Parameters' in storeData:
                return storeData['Parameters']['gas_initial_volume']

            else:
                return oldValue

        # Con esta comprobación se comprueba si se ha pulsado en copiar datos de un escenario
        if ctx.triggered_id['type'] == 'scenario-dropdown':
            # Se comprueba si se ha cambiado de pestaña y se ha reseteado el selector de escenarios, en cuyo caso
            # no habría que actualizar el valor
            if scenarioSelected[0] < 0:
                return oldValue

            # gas_initial_volume se calcula de forma individual al resto de parámetros, ya que también puede cambiar
            # al cambiar el digestor, y no puede haber Outputs duplicados
            scenarioData = storeData['Optimization'][scenarioSelected[0]]
            return scenarioData['gas_initial_volume']

        if not ResourceAllocation.emptyOrOutOfBounds(digesterVolume):
            return simulator.getBiogasGasInitialVolume(digesterVolume)

        return oldValue

    @callback(
        Output({'type': 'renewable-parameters', 'key': 'pv_installation_cost', 'renewable': 'photovoltaic',
                'cardType': 'economicalData', 'scenarioUpdated': False, 'importChange': False}, 'value'),
        Input({'type': 'renewable-parameters', 'key': 'photovoltaic_power',
              'renewable': 'photovoltaic', 'cardType': 'technicalData', 'scenarioUpdated': True, 'importChange': True}, 'value'),
        Input({'type': 'renewable-parameters', 'key': 'pv_kw_installation_cost', 'renewable': 'photovoltaic',
               'cardType': 'economicalData', 'scenarioUpdated': False, 'importChange': True}, 'value'),
        State({'type': 'renewable-parameters', 'key': 'pv_installation_cost', 'renewable': 'photovoltaic',
               'cardType': 'economicalData', 'scenarioUpdated': False, 'importChange': False}, 'value')
    )
    def getPvInstallationCost(pvPower, kwInstallationCost, oldValue):
        if not ResourceAllocation.emptyOrOutOfBounds(pvPower) and not ResourceAllocation.emptyOrOutOfBounds(kwInstallationCost):
            return simulator.getInstallationCost(pvPower, kwInstallationCost)

        return oldValue

    @callback(
        Output({'type': 'renewable-parameters', 'key': 'eol_installation_cost', 'renewable': 'windPower',
                'cardType': 'economicalData', 'scenarioUpdated': False, 'importChange': False}, 'value'),
        Input({'type': 'renewable-parameters', 'key': 'wind_turbine_power',
              'renewable': 'windPower', 'cardType': 'technicalData', 'scenarioUpdated': True, 'importChange': True}, 'value'),
        Input({'type': 'renewable-parameters', 'key': 'eol_kw_installation_cost', 'renewable': 'windPower',
               'cardType': 'economicalData', 'scenarioUpdated': False, 'importChange': True}, 'value'),
        State({'type': 'renewable-parameters', 'key': 'eol_installation_cost',
              'renewable': 'windPower', 'cardType': 'economicalData', 'scenarioUpdated': False, 'importChange': False}, 'value')
    )
    def getWindPowerInstallationCost(windPower, kwInstallationCost, oldValue):
        if not ResourceAllocation.emptyOrOutOfBounds(windPower) and not ResourceAllocation.emptyOrOutOfBounds(kwInstallationCost):
            return simulator.getWindPowerInstallationCost(windPower, kwInstallationCost)

        return oldValue

    @callback(
        Output({'type': 'renewable-parameters', 'key': 'bio_installation_cost',
               'renewable': 'biogas', 'cardType': 'economicalData', 'scenarioUpdated': False, 'importChange': False}, 'value'),
        Input({'type': 'renewable-parameters', 'key': 'generator_max_power',
              'renewable': 'biogas', 'cardType': 'technicalData', 'scenarioUpdated': True, 'importChange': True}, 'value'),
        Input({'type': 'renewable-parameters', 'key': 'bio_kw_installation_cost',
              'renewable': 'biogas', 'cardType': 'economicalData', 'scenarioUpdated': False, 'importChange': True}, 'value'),
        State({'type': 'renewable-parameters', 'key': 'bio_installation_cost',
              'renewable': 'biogas', 'cardType': 'economicalData', 'scenarioUpdated': False, 'importChange': False}, 'value')
    )
    def getBiogasInstallationCost(bioPower, kwInstallationCost, oldValue):
        if not ResourceAllocation.emptyOrOutOfBounds(bioPower) and not ResourceAllocation.emptyOrOutOfBounds(kwInstallationCost):
            return simulator.getInstallationCost(bioPower, kwInstallationCost)

        return oldValue

    @callback(
        Output({'type': 'renewable-parameters', 'key': 'hydraulic_installation_cost', 'renewable': 'hydraulic',
                'cardType': 'economicalData', 'scenarioUpdated': False, 'importChange': False}, 'value'),
        Input({'type': 'renewable-parameters', 'key': 'turbine_power',
              'renewable': 'hydraulic', 'cardType': 'technicalData', 'scenarioUpdated': True, 'importChange': True}, 'value'),
        Input({'type': 'renewable-parameters', 'key': 'pump_power',
              'renewable': 'hydraulic', 'cardType': 'technicalData', 'scenarioUpdated': True, 'importChange': True}, 'value'),
        Input({'type': 'renewable-parameters', 'key': 'hydraulic_kw_installation_cost', 'renewable': 'hydraulic',
               'cardType': 'economicalData', 'scenarioUpdated': False, 'importChange': True}, 'value'),
        Input({'type': 'renewable-parameters', 'key': 'upper_tank_volume',
              'renewable': 'hydraulic', 'cardType': 'technicalData', 'scenarioUpdated': True, 'importChange': True}, 'value'),
        Input({'type': 'renewable-parameters', 'key': 'lower_tank_volume',
              'renewable': 'hydraulic', 'cardType': 'technicalData', 'scenarioUpdated': True, 'importChange': True}, 'value'),
        Input({'type': 'renewable-parameters', 'key': 'hydraulic_deposit_installation_cost', 'renewable': 'hydraulic',
               'cardType': 'economicalData', 'scenarioUpdated': False, 'importChange': True}, 'value'),
        State({'type': 'renewable-parameters', 'key': 'hydraulic_installation_cost', 'renewable': 'hydraulic',
               'cardType': 'economicalData', 'scenarioUpdated': False, 'importChange': False}, 'value')
    )
    def getHydraulicInstallationCost(turbinePower, pumpPower, kWInstallationCost,
                                     upperTankVolume, lowerTankVolume, depositInstallationCost, oldValue):
        if (not ResourceAllocation.emptyOrOutOfBounds(turbinePower) and not ResourceAllocation.emptyOrOutOfBounds(pumpPower) and
            not ResourceAllocation.emptyOrOutOfBounds(kWInstallationCost) and not ResourceAllocation.emptyOrOutOfBounds(upperTankVolume) and
                not ResourceAllocation.emptyOrOutOfBounds(lowerTankVolume) and not ResourceAllocation.emptyOrOutOfBounds(depositInstallationCost)):
            return simulator.getHydraulicInstallationCost(turbinePower, pumpPower, kWInstallationCost,
                                                          upperTankVolume, lowerTankVolume, depositInstallationCost)

        return oldValue
