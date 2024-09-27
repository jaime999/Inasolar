import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
import dash_leaflet as dl
from dateutil.parser import parse
from dash import html, callback, Output, Input, State, ALL, ctx, dcc, dash_table, clientside_callback
from .simulator import simulator
from .filtro_dias import filtro_dias
from dateutil.relativedelta import relativedelta
from .genericCode import GenericCode
from .resourceAllocationGeneric import (ResourceAllocation, ALLOCATION_PARAMETERS_RENEWABLES_RESULT_SQL,
                                        ALLOCATION_PARAMETERS_OPTIMIZATION_SQL, ALLOCATION_PARAMETERS_SUMMARY_SQL,
                                        OPTIMIZATION_PARAMETERS_SUMMARY_SQL, generateLabelAndInput)
from .resourceOperations import ResourceOperations
from datetime import date

# Funciones para iniciar Dash
# ---------------------------------------------------------------
PAGE_TITLE = 'Resource Allocation'
dash.register_page(__name__, title=PAGE_TITLE)


# FUNCIONES
# ---------------------------------------------------------------
def getRangeAndDemandCard(area):
    return ResourceAllocation.getRangeAndDemandParametersRow('resourceAllocation', date.today(), True)


def getOptimizationData(summary):
    # Se cambia el nombre de las claves de la fila de regulación, y se fusionan ambas filas
    # para que quede todo en una sola. También se añaden los valores de los recursos
    # utilizados en cada simulación (posición 2 de la lista)
    newSummary = []
    for index, scenario in enumerate(summary):
        regulationRow = {key + 'WR': value for key,
                         value in scenario[1].items()}
        newScenario = {**scenario[0], **scenario[2]}
        newScenario.update(regulationRow)
        newScenario['Scenario'] = f'Scenario {index}'
        newSummary.append(newScenario)

    return newSummary


def generatePonderParameter(rowParameter):
    parameterName = rowParameter["Name"]
    # Si el parámetro es jerárquico, se coloca delante el nombre principal
    if rowParameter['GraphLabel'] != None:
        parameterName = f'{rowParameter["GraphLabel"]} {parameterName}'

    return dbc.Col(
        dbc.Row([
            dbc.Col(generateLabelAndInput(parameterName, rowParameter['IdParameter'],
                    rowParameter['DefaultValue'], 'optimization-ponders', minValue=-1))
        ], align="center"), width=3, class_name='pb-3'
    )


def createOptimizationPonders():
    # Para diferenciar los valores que tienen que aparecer se utiliza la columna "DefaultValue",
    # que indica los ponders por defecto de cada variable
    optimizationPonders = ALLOCATION_PARAMETERS_OPTIMIZATION_SQL[
        ALLOCATION_PARAMETERS_OPTIMIZATION_SQL['DefaultValue'].notnull()]

    return dbc.ListGroupItem(html.Div([GenericCode.getHeaderOfListGroupItem('Ponders', 'optimizationPondersInfo'),
                                       dbc.Row([generatePonderParameter(row)
                                                for index, row in optimizationPonders.iterrows()], align='center'),
                                       dbc.Row(dbc.Col(dbc.Button('Rank', id={'type': 'optimization', 'key': 'rank'}),
                                                       width='auto'), justify='center')]), className='mb-4')


def createOptimizationTable(optimizationData):
    # Se ha tenido que fijar el ancho de las columnas manualmente, ya que al fijar los headers
    # para que aparezcan al usar el scroll, el nombre de las columnas no se fija automáticamente
    return dash_table.DataTable(
        id='resourceAllocationDatatable',
        data=optimizationData,
        columns=ResourceAllocation.COLUMNS_OPTIMIZATION,
        sort_action='native',
        style_table={'overflowX': 'auto', 'min-width': '100%',
                     'overflowY': 'auto', 'height': '50vh'},
        style_cell={'minWidth': '100px', 'height': 'auto'},
        fixed_rows={'headers': True},
        page_action='none',
        style_header={
            'border': '1px solid green'},
        style_cell_conditional=[
            {
                'if': {
                    'column_id': ['gridSummaryWR', 'surplusSummary', 'surplusSummaryWR',
                                  'balance', 'energyCostRenewables', 'loleCon', 'loleSin',
                                  'lolpCon', 'loleConWR', 'lolpConWR', 'sosWaterTank', 'sosWaterTankWR']
                },
                'width': '150px',
            },
            {
                'if': {
                    'column_id': ['energyCostRenewablesWR', 'interchangeCount', 'loleSin',
                                  'balanceWR', 'loleSinWR', 'lolpSinWR', 'lolpSin']
                },
                'width': '200px',
            },
            {
                'if': {
                    'column_id': ['numberFailuresWR', 'numberFailures', 'interchangeCountWR', 'energyInterchange',
                                  'energyInterchangeWR']
                },
                'width': '250px',
            },
            {
                'if': {
                    'column_id': ['energyNotUsedWR', 'energyNotUsed']
                },
                'width': '300px',
            },
            {
                'if': {
                    'column_id': ['lossLoad', 'lossLoadWR']
                },
                'width': '400px',
            },
        ],
        style_data_conditional=[
            GenericCode.getColumnColor(
                'photovoltaic', '#dbe40e', 'black', 'column_type'),
            GenericCode.getColumnColor(
                'windPower', '#308e37', 'black', 'column_type'),
            GenericCode.getColumnColor(
                'biogas', '#ff8c16', 'black', 'column_type'),
            GenericCode.getColumnColor(
                'hydraulic', '#0d66e8', 'black', 'column_type'),
            GenericCode.getColumnColor('Score', 'rgb(204, 255, 189)', 'black', 'column_type')],
        style_header_conditional=[
            GenericCode.getColumnColor('Score', 'rgb(176, 255, 153)', 'black', 'column_type')],
        merge_duplicate_headers=True)


def updateOptimizationColumnDropdown():
    optimizationDropdownOptions = []
    for index, row in ALLOCATION_PARAMETERS_OPTIMIZATION_SQL.iterrows():
        rowLabel = ''
        if row['GraphLabel'] != None:
            rowLabel = f"{row['GraphLabel']}: "

        optimizationDropdownOptions.append({'label': f"{rowLabel}{row['Name']} ({row['Unity']})",
                                            'value': row['IdParameter']})

    return optimizationDropdownOptions


def getCircleLimits(optimizationData, optimizationDataWR, maxRangeIndex, minRangeIndex, maxRangeIndexWR, minRangeIndexWR):
    maxNoWR = optimizationData.iloc[maxRangeIndex]
    maxWR = optimizationDataWR.iloc[maxRangeIndexWR]
    minNoWR = optimizationData.iloc[minRangeIndex]
    minWR = optimizationDataWR.iloc[minRangeIndexWR]
    # Comprobamos la diferencia entre el máximo sin regulación y con regulación
    if maxNoWR > maxWR:
        differenceWR = maxNoWR - maxWR
        differenceNoWR = 0

    else:
        differenceWR = 0
        differenceNoWR = maxWR - maxNoWR

    # Calculamos el mínimo y el máximo de los datos, para obtener la escala de la gráfica
    minimum = min(minNoWR, minWR)
    maximum = max(maxNoWR, maxWR)

    difference = maximum - minimum

    # Se calcula el límite superior y el límite inferior del círculo, teniendo en cuenta la escala
    # (se ha utilizado como caso base que la escala sea de 0 a 20, y que el diámetro sea de 21 a 19 en el eje Y)
    upperDifference = difference*21/20
    lowerDifference = difference*19/20
    # En caso de que tanto el mínimo como el máximo sean 0, se pone un valor por defecto para que los límites
    # no sean ambos 0
    if difference == 0:
        upperDifference = 0.1
        lowerDifference = -0.1

    # Se crean los círculos, situados en X en el índice donde se encuentra el máximo, y en Y se ajusta para que
    # tenga en cuenta si los máximos no tienen el mismo valor
    shapeValueMax = [dict(type="circle",
                          xref="x", yref="y",
                          x0=maxRangeIndex-0.5, y0=minimum+upperDifference-differenceNoWR,
                          x1=maxRangeIndex+0.5, y1=minimum+lowerDifference-differenceNoWR,
                          line=dict(color="RebeccaPurple"))]

    shapeValueMaxWR = [dict(type="circle",
                            xref="x", yref="y",
                            x0=maxRangeIndexWR-0.5, y0=minimum+upperDifference-differenceWR,
                            x1=maxRangeIndexWR+0.5, y1=minimum+lowerDifference-differenceWR,
                            line=dict(color="RebeccaPurple"))]

    # Comprobamos la diferencia entre el mínimo sin regulación y con regulación
    if minNoWR < minWR:
        differenceWR = minWR - minNoWR
        differenceNoWR = 0

    else:
        differenceWR = 0
        differenceNoWR = minNoWR - minWR

    # Se crean los círculos, situados en X en el índice donde se encuentra el mínimo, y en Y se ajusta para que
    # tenga en cuenta si los mínimos no tienen el mismo valor
    shapeValueMin = [dict(type="circle",
                          xref="x", yref="y",
                          x0=minRangeIndex-0.5, y0=maximum-lowerDifference+differenceNoWR,
                          x1=minRangeIndex+0.5, y1=maximum-upperDifference+differenceNoWR,
                          line=dict(color="RebeccaPurple"))]

    shapeValueMinWR = [dict(type="circle",
                            xref="x", yref="y",
                            x0=minRangeIndexWR-0.5, y0=maximum-lowerDifference+differenceWR,
                            x1=minRangeIndexWR+0.5, y1=maximum-upperDifference+differenceWR,
                            line=dict(color="RebeccaPurple"))]

    return shapeValueMax, shapeValueMaxWR, shapeValueMin, shapeValueMinWR


def generateOptimizationGraph(optimizationData, dpValue='', optimizationLabel='', optimizationTitle=''):
    fig = go.Figure()
    maxRangeIndex = optimizationData[dpValue].idxmax()
    minRangeIndex = optimizationData[dpValue].idxmin()
    maxRangeIndexWR = optimizationData[f'{dpValue}WR'].idxmax()
    minRangeIndexWR = optimizationData[f'{dpValue}WR'].idxmin()
    if not optimizationData.empty:
        variableInfo = ALLOCATION_PARAMETERS_SUMMARY_SQL.loc[
            ALLOCATION_PARAMETERS_SUMMARY_SQL['IdParameter'] == dpValue].iloc[0]
        fig.add_trace(go.Scatter(x=optimizationData['Scenario'],
                                 y=optimizationData[dpValue],
                                 name='Without regulation',
                                 hovertemplate='%{y:.2f}' +
                                 ' %s' % variableInfo['Unity'],
                                 hoverinfo='text',
                                 mode='markers'))
        fig.add_trace(go.Scatter(x=optimizationData['Scenario'],
                                 y=optimizationData[f'{dpValue}WR'],
                                 name='With regulation (WR)',
                                 hovertemplate='%{y:.2f}' +
                                 ' %s' % variableInfo['Unity'],
                                 hoverinfo='text',
                                 mode='markers'))

    fig.update_xaxes(nticks=20, rangeslider_visible=True,
                     range=[-1, 19], type='category')

    # Se crean los círculos que van a aparecer al pulsar en cada uno de los botones
    shapeValueMax, shapeValueMaxWR, shapeValueMin, shapeValueMinWR = getCircleLimits(optimizationData[dpValue], optimizationData[f'{dpValue}WR'],
                                                                                     maxRangeIndex, minRangeIndex, maxRangeIndexWR, minRangeIndexWR)

    fig.update_layout(
        title=f'Optimization: {optimizationTitle}', yaxis_title=f'<b>{optimizationLabel}</b>', xaxis_title='Scenarios',
        hovermode='x unified',
        updatemenus=[
            dict(
                type="buttons",
                direction="left",
                x=0.57,
                y=1.18,
                buttons=[
                    dict(label="Max",
                         method="relayout",
                         args=[{"xaxis.range": [maxRangeIndex - 10, maxRangeIndex + 10],
                                "shapes": shapeValueMax}]),
                    dict(label="Max WR",
                         method="relayout",
                         args=[{"xaxis.range": [maxRangeIndexWR - 10, maxRangeIndexWR + 10],
                                "shapes": shapeValueMaxWR}]),
                    dict(label="Min",
                         method="relayout",
                         args=[{"xaxis.range": [minRangeIndex - 10, minRangeIndex + 10],
                                "shapes": shapeValueMin}]),
                    dict(label="Min WR",
                         method="relayout",
                         args=[{"xaxis.range": [minRangeIndexWR - 10, minRangeIndexWR + 10],
                                "shapes": shapeValueMinWR}]),

                ],
            )
        ])

    return fig


def getFixedOptimizationPonders(optimizationPondersId, optimizationPondersValue):
    optimizationPonders = GenericCode.generateParametersWithValue(
        optimizationPondersId, optimizationPondersValue)

    # Se obtienen solo los pesos cuyo valor sea distinto de 0, ya que el resto la distancia siempre sería 0
    return {parameterId: parameterValue for parameterId, parameterValue in optimizationPonders.items()
            if parameterValue != 0}


def updateScenariosDropdown(resourceAllocationDataOptimization):
    scenariosDropdownOptions = []
    for index, row in enumerate(resourceAllocationDataOptimization):
        scenariosDropdownOptions.append({'label': row['Scenario'],
                                         'value': index})

    return scenariosDropdownOptions


def importParameters(excelParameters, renewableParametersId):
    # Se obtienen en una lista las ids de los parámetros
    renewableParametersKeys = [parameter['key']
                               for parameter in renewableParametersId]
    withoutFailures = False
    importValues = {}
    idParameter = ''
    # Iterar sobre columnas y luego sobre las filas, ya que al importar un Excel, el valor de un parámetro
    # se encuentra justo debajo
    for columnName, columnRow in excelParameters.items():
        for index, value in columnRow.items():
            # En caso de que se haya escrito algo en "idParameter", significa que se ha encontrado un ID,
            # por lo que se sabe que en la siguiente fila de la columna estará el valor correspondiente
            if idParameter != '':
                if idParameter != 'withoutFailures':
                    importValues[idParameter] = value

                else:
                    withoutFailures = value

                idParameter = ''

            elif value in renewableParametersKeys:
                idParameter = value

            elif value == 'withoutFailures':
                idParameter = 'withoutFailures'

    return importValues, withoutFailures


def exportToExcel(parametersSheetData, restSheets, fileName, rangeDates):
    writer, output = ResourceAllocation.exportParametersToExcel(
        parametersSheetData)

    return GenericCode.writeExcelData(writer, restSheets, output, fileName, rangeDates)


def getFieldByElement(row, fieldType):
    # Se comprueba qué tipo de elemento es cada fila del modal
    element = row['Element']
    # Dependiendo del modal o botón pulsado (creación o modificación), tendrá un ID u otro
    elementId = {'type': f'resource{fieldType}Locations',
                 'key': row['ParameterId']}
    if element == 'Dropdown':
        value = row['DropdownColumn']
        label = row['DropdownLabel']
        # Si ambos valores son  iguales, las opciones del dropdown no se recuperan completos de una tabla,
        # si no buscando los valores distintos de una columna
        if label == value:
            dpOptionsSql = pd.read_sql(
                f"""SELECT DISTINCT({label}) as label, {label} as value
                   FROM {row['TableName']}""", GenericCode.engine)

        else:
            dpOptionsSql = pd.read_sql(
                f"""SELECT {label} as label, {value} as value
                  FROM {row['TableName']}""", GenericCode.engine)

        return dcc.Dropdown(
            id=elementId,
            options=dpOptionsSql.to_dict('records'),
            value=-1, clearable=False)

    if element == 'Input':
        inputType = row['InputType']
        if inputType == 'number':
            return dbc.Input(id=elementId,
                             type=inputType, min=row['MinValue'], max=row['MaxValue'])

        return dbc.Input(id=elementId,
                         type=inputType, minLength=row['MinValue'], maxLength=row['MaxValue'])

    if element == 'Checkbox':
        return dbc.Checkbox(
            id=elementId,
            value=False,
        )

    downloadDemandLayout = GenericCode.getActionButton(
        'export', f'downloadDemandLayout{fieldType}', 'fa-file-export', 'Download Layout')
    downloadDemandLayout.append(dcc.Download(
        id=f'export-csv-downloadDemandLayout{fieldType}'))

    # Se añade apartado para indicar si se ha cargado correctamente el fichero con las demandas
    addDemandRow = dbc.Row([
        dbc.Col(downloadDemandLayout),
        dbc.Col(
            dcc.Upload(GenericCode.getActionButton('import', 'addDemand', 'fa-file-import', 'Import Demand'),
                       id=f'upload-file-addDemand-{fieldType}')
        )
    ])

    return addDemandRow


def getResourceLabelAndInput(resourceCreationElementsSql, fieldType):
    fields = []
    # Se recuperan los parámetros necesarios para crear un recurso, y se ordena por orden de aparición
    for index, row in resourceCreationElementsSql.sort_values(by='Order').iterrows():
        field = getFieldByElement(row, fieldType)
        fields.append(
            dbc.Col(
                dbc.Row([
                    dbc.Col(row['ParameterName'], width=6),
                    dbc.Col(field, width=6)
                ], align='center'), width=12, className='px-4 pb-4'))

    return fields


def createModalElements(modalName):
    modalHeader = dbc.ModalHeader(dbc.ModalTitle(f'{modalName} Resource'))
    modalAlert = dbc.Alert(
        id=f'{modalName.lower()}ResourceAlert', is_open=False, duration=5000)
    modalFooter = dbc.ModalFooter(
        dbc.Button(
            modalName, id=f'confirm{modalName}ResourceButton', className='ms-auto'
        )
    )
    modalOpen = dbc.Button(
        f'{modalName} Resource', className='mt-auto', id=f'{modalName.lower()}ResourceButton')

    return modalHeader, modalAlert, modalFooter, modalOpen


def createResourceButton(createResourceElements):
    # El mapa se inicializa en Valencia
    initialPos = [39.4, -0.37]
    modalName = 'Create'
    createResourceFields = getResourceLabelAndInput(
        createResourceElements, modalName)
    createResourceFields.append(
        dbc.Col(dbc.Row(id=f'loadFileMessage{modalName}', justify='center'), width=12))
    modalHeader, modalAlert, modalFooter, modalOpen = createModalElements(
        modalName)
    modal = dbc.Modal(
        [
            modalHeader,
            dbc.ModalBody([
                dbc.Row([
                        dbc.Col(
                            dl.Map([dl.TileLayer(),
                                    dl.Marker(id='resourceMarker', position=initialPos)], center=initialPos,
                                   zoom=6, className='map', id=f'{modalName.lower()}ResourceMap'), width=6
                        ),
                        dbc.Col(dbc.Row(createResourceFields),
                                width=6)
                        ], className='py-4'),
                dbc.Row(modalAlert)
            ], className='px-4'),
            modalFooter,
            dcc.Store(id='newResourceGeneratorId')
        ],
        id=f'modal{modalName}Resource',
        is_open=False,
        size='xl'
    )

    return dbc.Col([modalOpen, modal], width='auto')


def modifyResourceButton(modifyResourceElements):
    modalName = 'Modify'
    modalHeader, modalAlert, modalFooter, modalOpen = createModalElements(
        modalName)
    modal = dbc.Modal(
        [
            modalHeader,
            dbc.ModalBody([
                dbc.Row([dbc.Col([dbc.Row(getResourceLabelAndInput(modifyResourceElements, 'Modify')),
                                  dbc.Row([
                                      dbc.Col('Power dates', width=6),
                                      dbc.Col(
                                          id=f'{modalName.lower()}ResourcesRangeDatesLabel', width=6),
                                      dcc.Store(
                                          id=f'{modalName.lower()}ResourcesRangeDates'),
                                      dcc.Store(
                                          id='modifyResourcesSelectedResource')
                                  ], className='px-2 pb-4'),
                                  dbc.Row(dbc.Col(width='auto'), id=f'loadFileMessage{modalName}', justify='end')])
                         ], className='py-4'),
                dbc.Row(modalAlert)
            ], className='px-4'),
            modalFooter,
        ],
        id=f'modal{modalName}Resource',
        is_open=False
    )

    return dbc.Col([modalOpen, modal], width='auto')


def createResourceAllocationHeader():
    resourceCreationElementsSql = pd.read_sql(
        """SELECT *
           FROM ResourceCreation""", GenericCode.engine)
    createResourceElements = resourceCreationElementsSql.loc[(resourceCreationElementsSql['Button'] == 'Create') |
                                                             (resourceCreationElementsSql['Button'] == 'ALL')]
    modifyResourceElements = resourceCreationElementsSql.loc[(resourceCreationElementsSql['Button'] == 'Modify') |
                                                             (resourceCreationElementsSql['Button'] == 'ALL')]

    headerRow = GenericCode.getLocationRow('Consumer')
    headerRow.insert(1, createResourceButton(createResourceElements))
    headerRow.insert(2, modifyResourceButton(modifyResourceElements))

    return dbc.Row(headerRow, className='page-header-row generation-location')


def getResourceInfo(resourceId):
    resourceInfo = pd.read_sql(
        f"""SELECT Name, InstalledPower, Type, Area
           FROM Locations
           WHERE id = {resourceId}""", GenericCode.engine).iloc[0]

    resourceDates = pd.read_sql(
        f"""SELECT MAX(d2.Date) AS MaxDate, MIN(d2.Date) AS MinDate
            FROM datosGEDER2 d1
            INNER JOIN Dates d2 ON d2.id = d1.date
            WHERE location = {resourceId} AND Power IS NOT NULL""", GenericCode.engine).iloc[0]

    return resourceInfo, resourceDates


def checkDemandFileContent(demandFile, createResource):
    if demandFile is not None and demandFile != '':
        try:
            GenericCode.parseContents(demandFile, 0)
    
            return 'Excel loaded succesfully'
    
        except Exception as e:
            return f'There was an error loading the demand file: {e}'
        
    if createResource:
        return 'You must load the demand for the new resource'
    
    return ''


# VARIABLES
# ---------------------------------------------------------------
allocationParametersRenewablesFieldSql = pd.read_sql(
    """SELECT a.*
       FROM [inasolar].[dbo].[AllocationParameters] a
       INNER JOIN RenewableEnergiesInfo r ON a.Type = r.IdType
       WHERE a.DefaultValue IS NOT NULL
       ORDER BY ParametersOrder""", GenericCode.engine)
allocationParametersSummarySql = pd.read_sql(
    """SELECT *
       FROM [inasolar].[dbo].[AllocationParameters] a
	   WHERE GraphType = 'Summary'
       ORDER BY ParametersOrder""", GenericCode.engine)

# HTML
# ---------------------------------------------------------------
cardBodyContent = [dcc.Interval(id="optimization-interval", n_intervals=0, interval=500,
                                disabled=True),
                   dbc.Progress(class_name='my-4', id="optimization-progress", value=-1, animated=True, striped=True,
                                style={'display': 'none'})]

resultTabs = GenericCode.createResultTabs(
    'resourceAllocation', cardBodyContent)

layout = html.Div([
    html.H2(PAGE_TITLE),
    createResourceAllocationHeader(),
    ResourceAllocation.createParametersTabs('resourceAllocation'),
    getRangeAndDemandCard(1),
    resultTabs
], id='resourceAllocation-container', className='py-3')


# CALLBACKS
# ---------------------------------------------------------------
@callback(
    Output({'type': 'resourceModifyLocations', 'key': ALL}, 'value'),
    Output('modifyResourcesRangeDates', 'data'),
    Output('upload-file-addDemand-Modify', 'contents'),
    Output('modifyResourcesSelectedResource', 'data'),
    Input({'type': 'resourceModifyLocations', 'key': 'SelectResource'}, 'value'),
    State({'type': 'resourceModifyLocations', 'key': ALL}, 'value'),
    State('upload-file-addDemand-Modify', 'contents'),
    State('modifyResourcesRangeDates', 'data'),
    Input('createResourceAlert', 'color'),
    State('newResourceGeneratorId', 'data'),
    prevent_initial_call=True
)
def updateResourceInfo(resourceSelected, oldData, oldDemandFile, oldRangeDates, createResourceState, resourceGeneratorId):
    if ctx.triggered_id == 'createResourceAlert':
        if createResourceState == 'success':
            resourceSelected = resourceGeneratorId
            
        else:
            return oldData, oldRangeDates, oldDemandFile, None        
    
    resourceInfoSql, resourceDatesSql = getResourceInfo(resourceSelected)
    oldData[0] = resourceSelected
    oldData[-1] = resourceInfoSql['InstalledPower']
    oldData[-2] = resourceInfoSql['Name']
    resourceStore = {'Type': resourceInfoSql['Type'], 'InstalledPower': resourceInfoSql['InstalledPower'],
                     'Area': resourceInfoSql['Area']}

    return (oldData, {'MinDate': resourceDatesSql['MinDate'].date(), 'MaxDate': resourceDatesSql['MaxDate'].date()},
            '', resourceStore)


@callback(
    Output('modifyResourcesRangeDatesLabel', 'children'),
    Input('modifyResourcesRangeDates', 'data'),
    prevent_initial_call=True
)
def showModifyResourceRangeDates(rangeDates):
    minDateLabel = 'MinDate'
    maxDateLabel = 'MaxDate'
    if (minDateLabel in rangeDates) and (maxDateLabel in rangeDates):
        return f'{rangeDates[minDateLabel]} - {rangeDates[maxDateLabel]}'

    return ''


@callback(
    Output('modifyResourceAlert', 'children'),
    Output('modifyResourceAlert', 'is_open'),
    Output('modifyResourceAlert', 'color'),
    Input('confirmModifyResourceButton', 'n_clicks'),
    State({'type': 'resourceModifyLocations', 'key': ALL}, 'value'),
    State({'type': 'resourceModifyLocations', 'key': ALL}, 'id'),
    State('modifyResourcesRangeDates', 'data'),
    State('upload-file-addDemand-Modify', 'contents'),
    State('modifyResourcesSelectedResource', 'data'),
    prevent_initial_call=True
)
def modifyResource(confirmModifyResourceButton, modifyResourceValues, modifyResourceIds,
                   rangeDates, demandFile, resourceInfo):
    if confirmModifyResourceButton:
        modifyResourceParams = GenericCode.generateParametersWithValue(
            modifyResourceIds, modifyResourceValues)
        try:
            parseFile, dates = None, None
            if demandFile is not None and demandFile != '':
                # Se busca la información de la demanda en la primera hoja
                parseFile = GenericCode.parseContents(demandFile, 0)
                dates = parseFile['Date'].dt.strftime('%Y-%m-%d')
                
            ResourceOperations.modifyResource(modifyResourceParams['SelectResource'], modifyResourceParams['ResourceName'],
                                              modifyResourceParams['InstalledPower'], dates,
                                              rangeDates['MinDate'], rangeDates['MaxDate'], parseFile, resourceInfo)

            return 'Resource modified succesfully', True, 'success'
        
        except Exception as e:
            return str(e), True, 'danger'

    return '', False, ''


@callback(
    Output('createResourceAlert', 'children'),
    Output('createResourceAlert', 'is_open'),
    Output('createResourceAlert', 'color'),
    Output('newResourceGeneratorId', 'data'),
    Input('confirmCreateResourceButton', 'n_clicks'),
    State({'type': 'resourceCreateLocations', 'key': ALL}, 'value'),
    State({'type': 'resourceCreateLocations', 'key': ALL}, 'id'),
    State('upload-file-addDemand-Create', 'contents'),
    prevent_initial_call=True
)
def createResource(confirmCreateResourceButton, createResourceValues, createResourceIds, demandFile):
    if confirmCreateResourceButton:
        createResourceParams = GenericCode.generateParametersWithValue(
            createResourceIds, createResourceValues)
        try:
                # Se busca la información de la demanda en la primera hoja
            parseFile = GenericCode.parseContents(demandFile, 0)
            dates = parseFile['Date'].dt.strftime('%Y-%m-%d')
            locationGeneratorId = ResourceOperations.createResource(createResourceParams['ResourceName'], createResourceParams['AreaName'],
                                              createResourceParams['Latitude'], createResourceParams['Longitude'],
                                              dates.min(), dates.max(), parseFile)
            
            return 'Resource created succesfully', True, 'success', locationGeneratorId
        
        except Exception as e:
            return str(e), True, 'danger', ''

    return '', False, '', ''


@callback(
    Output('export-csv-downloadDemandLayoutCreate', 'data'),
    Input('export-button-downloadDemandLayoutCreate', 'n_clicks'),
    prevent_initial_call=True
)
def downloadDemandLayoutCreateModal(downloadDemandLayout):
    if downloadDemandLayout:
        return dcc.send_file('assets/resourceDemandLayout.xlsx')
    
@callback(
    Output('export-csv-downloadDemandLayoutModify', 'data'),
    Input('export-button-downloadDemandLayoutModify', 'n_clicks'),
    prevent_initial_call=True
)
def downloadDemandLayoutModifyModal(downloadDemandLayout):
    if downloadDemandLayout:
        return dcc.send_file('assets/resourceDemandLayout.xlsx')


@callback(
    Output('loadFileMessageCreate', 'children'),
    Input('upload-file-addDemand-Create', 'contents'),
)
def loadCreateResourceFileDemand(demandFile):
    return checkDemandFileContent(demandFile, True)


@callback(
    Output('loadFileMessageModify', 'children'),
    Input('upload-file-addDemand-Modify', 'contents'),
)
def loadModifyResourceFileDemand(demandFile):
    return checkDemandFileContent(demandFile, False)


@callback(
    Output('confirmCreateResourceButton', 'disabled'),
    Input({'type': 'resourceCreateLocations', 'key': ALL}, 'value'),
    Input('loadFileMessageCreate', 'children'),
)
def disableCreateResourceButton(createResourceParams, demandFileMessage):
    return (any(type(resourceParam) == type(None) or str(resourceParam).strip() == '' for resourceParam in createResourceParams) or
            demandFileMessage != 'Excel loaded succesfully')


@callback(
    Output('confirmModifyResourceButton', 'disabled'),
    Input({'type': 'resourceModifyLocations', 'key': 'ResourceName'}, 'value'),
    Input({'type': 'resourceModifyLocations', 'key': 'SelectResource'}, 'value')
)
def disableModifyResourceButton(resourceName, resourceSelected):
    return (type(resourceSelected) == type(None)) or (str(resourceName).strip() == '')

@callback(
    Output({'type': 'resourceModifyLocations', 'key': 'InstalledPower'}, 'disabled'),
    Input('modifyResourcesSelectedResource', 'data'),
    prevent_initial_call=True
)
def disableInstalledPower(selectedResource):
    return selectedResource['Type'] == 'Consumer'

@callback(
    Output('resourceMarker', 'position'),
    Input({'type': 'resourceCreateLocations', 'key': 'Latitude'}, 'value'),
    Input({'type': 'resourceCreateLocations', 'key': 'Longitude'}, 'value'),
    State('resourceMarker', 'position'),
    prevent_initial_call=True
)
def updateMarkerCoordinates(latitude, longitude, oldMarkerPosition):
    if not ResourceAllocation.emptyOrOutOfBounds(latitude, -180) and not ResourceAllocation.emptyOrOutOfBounds(longitude, -180):
        return [latitude, longitude]

    return oldMarkerPosition


@callback(
    Output({'type': 'resourceCreateLocations', 'key': 'Latitude'}, 'value'),
    Output({'type': 'resourceCreateLocations', 'key': 'Longitude'}, 'value'),
    Input('createResourceMap', 'clickData'),
    prevent_initial_call=True
)
def updateInputsCoordinates(clickData):
    pos = clickData['latlng']

    return pos['lat'], pos['lng']


@callback(
    Output('modalCreateResource', 'is_open'),
    Input('createResourceButton', 'n_clicks'),
    Input('createResourceAlert', 'color'),
    prevent_initial_call=True
)
def openCreateResourceModal(createResource, createResourceState):
    if ((ctx.triggered_id == 'createResourceButton' and createResource)
        or (ctx.triggered_id == 'createResourceAlert' and createResourceState != 'success')):
        return True

    return False


@callback(
    Output('modalModifyResource', 'is_open'),
    Input('modifyResourceButton', 'n_clicks'),
    Input('createResourceAlert', 'color'),
    prevent_initial_call=True
)
def openModifyResourceModal(modifyResource, createResourceState):
    if ((ctx.triggered_id == 'modifyResourceButton' and modifyResource)
        or (ctx.triggered_id == 'createResourceAlert' and createResourceState == 'success')):
        return True

    return False


@callback(
    Output('resourceAllocationIntervalDatePicker', 'max_date_allowed'),
    Output('resourceAllocationIntervalDatePicker', 'min_date_allowed'),
    Input('locationData', 'data')
)
def updateMaxDatesAllowed(locationData):
    maxDateAllowed, minDateAllowed = ResourceAllocation.setMaxDateAllowedAndDisabledDays(
        locationData['Area'])

    return maxDateAllowed, minDateAllowed


@callback(
    Output('resourceAllocationIntervalDatePicker', 'start_date'),
    Output('resourceAllocationIntervalDatePicker', 'end_date'),
    Input('resourceAllocationIntervalDatePicker', 'max_date_allowed'),
    Input({'type': 'storeData', 'key': 'resourceAllocationData'}, 'data'),
    State('resourceAllocationIntervalDatePicker', 'start_date'),
    State('resourceAllocationIntervalDatePicker', 'end_date'),
    prevent_initial_call=True
)
def updateDates(maxDateAllowed, resourceAllocationData, lastMaxDateAllowed, lastMinDateAllowed):
    # Se comprueba si se ha cambiado las fechas al cambiar la ubicación
    if ctx.triggered_id == 'resourceAllocationIntervalDatePicker':
        maxDateAllowedParsed = parse(maxDateAllowed).date()

        return maxDateAllowedParsed - relativedelta(months=1), maxDateAllowedParsed

    # Se comprueba si se ha actualizado los datos de los resultados
    if len(resourceAllocationData) > 0:
        dates = resourceAllocationData['Dates']

        return dates['StartDate'], dates['EndDate']

    return lastMaxDateAllowed, lastMinDateAllowed


@callback(
    Output('locationsDropdown', 'value'),
    Input({'type': 'storeData', 'key': 'resourceAllocationData'}, 'data'),
    State('locationsDropdown', 'options'),
    State('locationsDropdown', 'value'),
    prevent_initial_call=True
)
def importLocation(resourceAllocationData, locationsOptions, lastLocation):
    # Se comprueba si se ha actualizado los datos de los resultados
    if len(resourceAllocationData) > 0:
        locationValue = next((location['value'] for location in locationsOptions if location.get(
            'label') == resourceAllocationData['Location']), None)

        return locationValue

    return lastLocation


# Al copiar datos de un escenario, se va al inicio de la página
clientside_callback(
    """
    function(n_clicks) { 
        if (n_clicks > 0) {
            window.scrollTo(0, 200);
            return 'container'
        }                            
    }
    """,
    Output('resourceAllocation-result-card', 'key'),
    Input({'type': 'scenario-dropdown', 'key': 'copyDataButton'}, 'n_clicks'),
    prevent_initial_call=True
)


@callback(
    Output('export-csv-resourceAllocation', 'data'),
    Input('export-button-resourceAllocation', 'n_clicks'),
    State({'type': 'storeData', 'key': 'resourceAllocationData'}, 'data'),
    State('resourceAllocation-result-data-tabs', 'key'),
    State('resourceAllocationDatatable', 'data'),
    State('resourceAllocationDatatable', 'columns'),
    State({'type': 'optimization-ponders', 'key': ALL}, 'id'),
    State({'type': 'optimization-ponders', 'key': ALL}, 'value'),
    State({'type': 'renewable-parameters', 'key': ALL, 'renewable': ALL,
          'cardType': ALL, 'scenarioUpdated': ALL, 'importChange': ALL}, 'id'),
    [State('locationsDropdown', 'value'), State(
        'locationsDropdown', 'options')]
)
def exportData(csvFile, resourceAllocationData, tabLastKey, resourceAllocationDatatable, optimizationColumns, optimizationPondersId, optimizationPondersValue,
               renewableParametersId, locationValue, locationOptions):
    if ctx.triggered_id == 'export-button-resourceAllocation':
        fileName, parametersData, rangeDates = ResourceAllocation.initializeExportParameters(
            resourceAllocationData, renewableParametersId)
        if tabLastKey == 'resourceAllocationSimulateButton':
            return ResourceAllocation.exportSimulation(resourceAllocationData['Simulation'], parametersData, f'resourceAllocationSimulation{fileName}',
                                                       rangeDates, resourceAllocationData['Location'])

        if tabLastKey == 'resourceAllocationOptimizeButton' or tabLastKey == 'resourceAllocationLastOptimizationButton':
            excelColumns = [column["id"] for column in optimizationColumns]
            optimizationPonders = None
            resourceAllocationDataDf = pd.DataFrame(
                resourceAllocationDatatable)
            # Si se ha calculado la nota, añadir los ponders al CSV
            if 'Score' in excelColumns:
                optimizationPondersList = [getFixedOptimizationPonders(
                    optimizationPondersId, optimizationPondersValue)]
                optimizationPonders = pd.DataFrame(optimizationPondersList)
                return ResourceAllocation.exportToExcel(parametersData, [{'SheetName': 'Optimization', 'Data': resourceAllocationDataDf[excelColumns]},
                                                                         {'SheetName': 'Ponders', 'Data': optimizationPonders}],
                                                        f'resourceAllocationOptimization{fileName}.xlsx', rangeDates, resourceAllocationData['Location'])

            return ResourceAllocation.exportToExcel(parametersData, [{'SheetName': 'Optimization', 'Data': resourceAllocationDataDf[excelColumns]}],
                                                    f'resourceAllocationOptimization{fileName}.xlsx', rangeDates, resourceAllocationData['Location'])

    return None


@callback(
    Output('resourceAllocation-container', 'key'),
    [Input('url', 'pathname')],
)
def stopOptimizationOnReload(pathname):
    # Detecta el cambio en la URL al recargar la página
    if pathname == '/web-resourceallocation':
        GenericCode.stopOptimization = True
        return ''


@callback(
    Output('newResource', 'data'),
    Input('createResourceAlert', 'color'),
    Input('modifyResourceAlert', 'color'),
    prevent_initial_call=True
)
def updateLocationsStore(createResourceState, modifyResourceState):
    # En caso de que se haya añadido o modificado un recurso, también se actualizan las ubicaciones
    if ctx.triggered_id == 'createResourceAlert':
        return createResourceState == 'success'

    elif ctx.triggered_id == 'modifyResourceAlert':
        return modifyResourceState == 'success'

    return False


@callback(
    Output({'type': 'resourceModifyLocations',
           'key': 'SelectResource'}, 'options'),
    Input('newResource', 'data'),
    Input('locationsDropdown', 'options'),
    State({'type': 'resourceModifyLocations',
          'key': 'SelectResource'}, 'options'),
    prevent_initial_call=True
)
def updateLocationsModifyResource(newResource, locationOptions, oldResourceOptions):
    # En caso de que se haya creado un nuevo recurso, se actualizan las ubicaciones del modal de modificación de recursos
    if (ctx.triggered_id == 'newResource' and newResource) or ctx.triggered_id == 'locationsDropdown':
        return GenericCode.updateLocationsDropdown()

    return oldResourceOptions


@callback(
    Output('resourceAllocationOptimizationGraph', 'figure'),
    Input({'type': 'optimization-dropdown', 'key': ALL}, 'value'),
    State({'type': 'optimization-dropdown', 'key': ALL}, 'options'),
    State({'type': 'storeData', 'key': 'resourceAllocationData'}, 'data'),
    [State('locationsDropdown', 'value'), State(
        'locationsDropdown', 'options')]
)
def updateGraph(optimizationVariableValue, optimizationVariableOptions,
                resourceAllocationData, locationValue, locationOptions):
    titleLabel = GenericCode.getLocationLabel(locationOptions, locationValue)
    if len(optimizationVariableValue) == 0:
        return go.Figure()

    else:
        dpValue = optimizationVariableValue[0]
        optimizationResult = pd.DataFrame(
            resourceAllocationData['Optimization'])

        return generateOptimizationGraph(optimizationResult, dpValue,
                                         GenericCode.getLabelFromDropdown(optimizationVariableOptions[0],
                                                                          dpValue), titleLabel)


@callback(
    Output('resourceAllocationSimulateButton', 'disabled'),
    Output('resourceAllocationOptimizeButton', 'disabled'),
    Input({'type': 'renewable-parameters', 'key': ALL, 'renewable': ALL,
          'cardType': ALL, 'scenarioUpdated': ALL, 'importChange': ALL}, 'value'),
)
def disableSimulateButton(renewableParametersValue):
    disableButton = ResourceAllocation.disableButton(renewableParametersValue)
    return disableButton, disableButton


@callback(
    Output('resourceAllocationLastOptimizationButton', 'disabled'),
    Input({'type': 'storeData', 'key': 'resourceAllocationData'}, 'data'),
)
def disableLastOptimizationButton(resourceAllocationData):
    return not 'Optimization' in resourceAllocationData


@callback(
    Output({'type': 'optimization', 'key': 'rank'}, 'disabled'),
    Input({'type': 'optimization-ponders', 'key': ALL}, 'value'),
)
def disableRankButton(optimizationPonders):
    return ResourceAllocation.disableButton(optimizationPonders, -1)


@callback(
    Output('resourceAllocation-result-tabs-content', 'children'),
    Output('resourceAllocation-rank', 'children'),
    Output('resourceAllocation-exportCol', 'style'),
    Input('resourceAllocation-result-data-tabs', 'active_tab'),
    Input({'type': 'storeData', 'key': 'resourceAllocationData'}, 'data'),
    State('resourceAllocation-result-data-tabs', 'key'),
    State('resourceAllocationIntervalDatePicker', 'start_date'),
    State('resourceAllocationIntervalDatePicker', 'end_date'),
    prevent_initial_call=True
)
def showActiveTabData(resultTab, resourceAllocationData, tabLastKey, startDate, endDate):
    csvNotDisplayed = {'display': 'none'}
    if len(resourceAllocationData) > 0:
        if len(resourceAllocationData['alertMessage']) > 0:
            return dbc.Alert(resourceAllocationData['alertMessage'], color='danger'), [], csvNotDisplayed

        tabGraph, tabTable, summaryHeader = ResourceAllocation.initializeTabValues(
            'resourceAllocation', resourceAllocationData['Location'])
        if tabLastKey == 'resourceAllocationSimulateButton':
            dates = resourceAllocationData['Dates']
            rangeDate = ResourceAllocation.generateRangeData(
                dates['StartDate'], dates['EndDate'])
            tabChildren, csvNotDisplayed = ResourceAllocation.getSimulationInfo(resourceAllocationData['Location'], resourceAllocationData,
                                                                                resultTab, tabGraph, tabTable, summaryHeader, rangeDate,
                                                                                csvNotDisplayed, 'resourceAllocation')

            return tabChildren, [], csvNotDisplayed

        if tabLastKey == 'resourceAllocationOptimizeButton' or tabLastKey == 'resourceAllocationLastOptimizationButton':
            # Dropdown para copiar los datos de un escenario a los parámetros
            scenarioSelector = dbc.Row([dbc.Col('Select scenario: ', width='auto', class_name='no-padding-right'), dbc.Col(dcc.Dropdown(
                id={'type': 'scenario-dropdown', 'key': 'scenarioKey'}, options=updateScenariosDropdown(resourceAllocationData['Optimization']),
                value=-1, clearable=False), width=3), dbc.Col(dbc.Button(
                    'Copy Data', className='mt-auto', id={'type': 'scenario-dropdown', 'key': 'copyDataButton'}), width='auto')], align='center', className='m-4')
            if resultTab == tabGraph:
                columnSelector = dbc.Row([dbc.Col('Select variable: ', width='auto', class_name='no-padding-right'), dbc.Col(dcc.Dropdown(
                    id={'type': 'optimization-dropdown', 'key': 'optimizationKey'}, options=updateOptimizationColumnDropdown(), value='gridSummary', clearable=False),
                    width=4)], align='center', className='mx-4')
                figOptimization = dcc.Graph(
                    id='resourceAllocationOptimizationGraph', figure={'data': []},)

                return [columnSelector, figOptimization, scenarioSelector], [], csvNotDisplayed

            if resultTab == tabTable:
                optimizationPonders = createOptimizationPonders()

                summaryTable = createOptimizationTable(
                    resourceAllocationData['Optimization'])

                return [summaryHeader, summaryTable, scenarioSelector], optimizationPonders, {}

    return [], [], csvNotDisplayed


@callback(
    Output("optimization-progress", "value"),
    Output("optimization-progress", "label"),
    Output('optimization-interval', 'disabled'),
    Output('optimization-progress', 'style'),
    Input('resourceAllocationOptimizeButton', 'n_clicks'),
    Input('resourceAllocationSimulateButton', 'n_clicks'),
    Input('resourceAllocationLastOptimizationButton', 'n_clicks'),
    Input("optimization-interval", "n_intervals"),
    State("optimization-progress", "value")
)
def progress_bar_update(optimizationPressed, simulationPressed, lastOptimizationPressed, n, oldProgress):
    # Cuando se pulsa en "Optimizar", se muestra la barra de progreso y se empieza a actualizar
    if ctx.triggered_id == 'resourceAllocationOptimizeButton':
        return 0, '', False, {}

    # Si es -1, no está optimizando, por lo que se oculta la barra y se deja de actualizar
    # Si es 100, ha terminado la optimización, por lo que ocurre lo mismo
    if oldProgress == -1 or oldProgress == 100 or ctx.triggered_id == 'resourceAllocationSimulateButton' or ctx.triggered_id == 'resourceAllocationLastOptimizationButton':
        return -1, '', True, {'display': 'none'}

    # Se comprueba que la cola no esté vacía y se recupera el valor.
    # En caso de que lo esté se devuelve el valor anterior de la barra
    if not GenericCode.progress_queue.empty():
        progress_bar_val = GenericCode.progress_queue.get()
    else:
        progress_bar_val = oldProgress

    # Se muestra la barra con el valor en caso de que sea < 5 (para que quepa el texto)
    return (progress_bar_val, f"{progress_bar_val} %" if progress_bar_val >= 5 else "", False, {})


@callback(
    Output('upload-file', 'contents'),
    Input('import-button-resourceAllocation', 'n_clicks'),
    prevent_initial_call=True
)
def resetUploadContent(importFile):
    if importFile:
        return None


@callback(
    Output({'type': 'storeData', 'key': 'resourceAllocationData'}, 'data'),
    Output('resourceAllocation-result-data-tabs', 'key'),
    Input('resourceAllocationSimulateButton', 'n_clicks'),
    Input('resourceAllocationOptimizeButton', 'n_clicks'),
    Input('resourceAllocationLastOptimizationButton', 'n_clicks'),
    Input('upload-file', 'contents'),
    State('selectDemand', 'value'),
    State({'type': 'renewable-parameters', 'key': ALL, 'renewable': ALL,
          'cardType': ALL, 'scenarioUpdated': ALL, 'importChange': ALL}, 'id'),
    State({'type': 'renewable-parameters', 'key': ALL, 'renewable': ALL,
          'cardType': ALL, 'scenarioUpdated': ALL, 'importChange': ALL}, 'value'),
    State('resourceAllocationIntervalDatePicker', 'start_date'),
    State('resourceAllocationIntervalDatePicker', 'end_date'),
    State({'type': 'storeData', 'key': 'resourceAllocationData'}, 'data'),
    State('locationData', 'data'),
    [State('locationsDropdown', 'value'), State(
        'locationsDropdown', 'options')],
    State('checkboxWithoutFailures', 'value'),
    State('resourceAllocation-result-data-tabs', 'key'),
    prevent_initial_call=True
)
def simulateAssignment(simulateButton, optimizeButton, lastOptimization, importedFile, demandSelected, renewableParametersId,
                       renewableParametersValue, startDate, endDate, resourceAllocationData, locationData,
                       locationValue, locationOptions, withoutFailures, tabLastKey):
    optimizeButtonId = 'resourceAllocationOptimizeButton'
    simulateButtonId = 'resourceAllocationSimulateButton'
    lastOptimizationButtonId = 'resourceAllocationLastOptimizationButton'
    if resourceAllocationData is None:
        resourceAllocationData = {'alertMessage': ''}
            
    else:
        resourceAllocationData['alertMessage'] = ''
        
    if ctx.triggered_id == optimizeButtonId or ctx.triggered_id == simulateButtonId or ctx.triggered_id == lastOptimizationButtonId:
        GenericCode.stopOptimization = True
            
        # Mediante esta función, asociamos cada ID de cada input a su valor
        resourceParameters = GenericCode.generateParametersWithValue(
            renewableParametersId, renewableParametersValue)

        alertValue, alertMessage = ResourceAllocation.setSimulationRestrictions(
            resourceParameters)
        resourceAllocationData['alertMessage'] = alertMessage
        if alertValue:
            return resourceAllocationData, None

        simulation = simulator()
        for key, value in resourceParameters.items():
            setattr(simulation, key, value)

        resourceAllocationData = ResourceAllocation.getResultStoreData(resourceAllocationData, resourceParameters,
                                                                       withoutFailures, startDate, endDate, locationValue, locationOptions)
        if ctx.triggered_id == simulateButtonId:
            simulationResult = simulation.range_simulation(
                startDate, endDate, locationData, ALLOCATION_PARAMETERS_RENEWABLES_RESULT_SQL['IdParameter'],
                demandSelected, not withoutFailures)

            # Se convierte el dataframe a JSON para poder almacenarlo en el Store
            resourceAllocationData['Simulation'] = GenericCode.convertToJSON(
                simulationResult)
            return resourceAllocationData, simulateButtonId

        if ctx.triggered_id == optimizeButtonId:
            while GenericCode.executingOptimization:
                pass

            summary = simulation.optimizeParameters(OPTIMIZATION_PARAMETERS_SUMMARY_SQL, resourceParameters, demandSelected,
                                                    startDate, endDate, locationData, ALLOCATION_PARAMETERS_RENEWABLES_RESULT_SQL[
                                                        'IdParameter'],
                                                    not withoutFailures)
            optimizationDataList = getOptimizationData(summary)

            resourceAllocationData['Optimization'] = optimizationDataList
            return resourceAllocationData, optimizeButtonId

        if ctx.triggered_id == lastOptimizationButtonId:
            return resourceAllocationData, lastOptimizationButtonId

    if importedFile is not None:
        try:
            parseFile = GenericCode.parseContents(importedFile)
            excelParameters = parseFile['Parameters']
            optimizationList = parseFile['Optimization'].to_dict(
                orient='records')
            resourceAllocationData['Optimization'] = optimizationList
            resourceAllocationData['Parameters'], resourceAllocationData['Failures'] = importParameters(
                excelParameters, renewableParametersId)
            resourceAllocationData['Dates'] = parseFile['Dates'].to_dict(orient='records')[
                0]
            # Hay que hacer esto, ya que se encuentra dentro de la hoja "Location", en la columna "Location"
            resourceAllocationData['Location'] = parseFile['Location']['Location'][0]
        except Exception as e:
            resourceAllocationData['alertMessage'] = str(e)

        return resourceAllocationData, optimizeButtonId

    return resourceAllocationData, tabLastKey


@callback(
    Output('resourceAllocationDatatable', 'data'),
    Output('resourceAllocationDatatable', 'columns'),
    Input({'type': 'optimization', 'key': 'rank'}, 'n_clicks'),
    State({'type': 'optimization-ponders', 'key': ALL}, 'id'),
    State({'type': 'optimization-ponders', 'key': ALL}, 'value'),
    State('resourceAllocationDatatable', 'data'),
    State('resourceAllocationDatatable', 'columns'),
    prevent_initial_call=True
)
def getTableRanking(rankOptimization, optimizationPondersId, optimizationPondersValue, oldData, oldColumns):
    if rankOptimization:

        result = filtro_dias.getScore(oldData, getFixedOptimizationPonders(
            optimizationPondersId, optimizationPondersValue))
        columns = oldColumns

        # Solo se vuelven a calcular las columnas de la tabla la primera que se pulsa en "Rank"
        if rankOptimization == 1:
            columns = ResourceAllocation.setColumnsSummary(True, True)

        return result, columns

    return oldData, oldColumns
