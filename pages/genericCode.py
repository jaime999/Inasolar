from sqlalchemy import create_engine
from dash import html, dcc, callback, Output, Input, State, ctx, dash_table
from importlib import reload
from datetime import datetime
from queue import Queue
import pandas as pd
import urllib
import dash_bootstrap_components as dbc
import logging
import io
import dash_loading_spinners as dls
import base64
import plotly.graph_objects as go
from plotly.subplots import make_subplots

class GenericCode:
    # FUNCIONES
    # ---------------------------------------------------------------
    def removePlotlyLogo():
        return {'displaylogo': False}
    
    def generateGraph(graphData, graphParameters, graphId, rangeDate, title, secondaryY, xData='Date', roundDigits='%{y:.2f}'):
        fig = go.Figure(make_subplots(specs=[[{"secondary_y": True}]]))
        # En graphParameters se encuentran los datos de cada trace a añadir
        for index, graphParameter in graphParameters.iterrows():
            fig.add_trace(go.Scatter(
                x=graphData[xData], y=graphData[graphParameter['IdParameter']],
                name=graphParameter['GraphLabel'],
                mode='lines',
                hovertemplate=roundDigits + ' %s' % graphParameter['GraphHover'],
                line=dict(color=graphParameter['GraphColor'])
            ), secondary_y = graphParameter['SecondaryY'])
        
        fig.update_xaxes(nticks=7, rangeslider_visible=True,
                         rangeselector=GenericCode.getGraphRangeSelector(
                             'resourceAllocation'),
                         tickformatstops=GenericCode.getGraphTickFormatStops(),
                         range=rangeDate, uirevision='time')
        fig.update_layout(title=title,
                          yaxis_title=graphParameters.iloc[0]['GraphTitle'],
                          xaxis_title='Date',
                          hovermode='x unified')
        if secondaryY:        
            fig.update_layout(yaxis2=dict(title=graphParameters.iloc[1]['GraphTitle']))

        return dcc.Graph(id=graphId, figure=fig, config=GenericCode.removePlotlyLogo())
    
    def createModal(modalTitle, modalId):
        return dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle(modalTitle)),
                dbc.ModalBody(id=f'{modalId}InfoBody'),
                dbc.ModalFooter(
                    dbc.Button(
                        'Close', id=f'{modalId}CloseCardInfo', className='ms-auto', n_clicks=0
                    )
                )
            ],
            id=f'{modalId}CardInfo',
            size='lg',
            is_open=False,
        )

    def reloadLogger():
        return reload(logging)
    
    def getLocationSqlQuery(resourceType):
        locationsSqlText = 'SELECT * FROM Locations'
        if resourceType:
            locationsSqlText += f" WHERE Type = '{resourceType}'"
            
        locationsDropdownSql = pd.read_sql(locationsSqlText, GenericCode.engine)
        locationsDropdownDf = pd.DataFrame(locationsDropdownSql,
                                           columns=locationsDropdownSql.columns)
            
        return locationsDropdownDf
    
    def setDropdownOptions(dropdownDf):
        dropdownOptions = []
        for index, row in dropdownDf.iterrows():
            dropdownOptions.append({'label': row['Name'],
                                             'value': row['id']})
            
        return dropdownOptions

    def updateLocationsDropdown(resourceType=None):
        locationsDropdownDf = GenericCode.getLocationSqlQuery(resourceType)
        return GenericCode.setDropdownOptions(locationsDropdownDf)

    def selectDB(server, database, user, password):
        params = urllib.parse.quote_plus(
            'DRIVER={ODBC Driver 18 for SQL Server};SERVER='+server+';DATABASE='+database+';UID='
            +user+';PWD=' + password+';TrustServerCertificate=yes;MARS_Connection=Yes')

        return create_engine("mssql+pyodbc:///?odbc_connect=%s" % params)

    def selectDatabaseModal(server, database, user, password):
        # Código HTML del modal para seleccionar la base de datos
        return html.Div(
            [
                dbc.Button("Select Database", color="primary",
                           id="openDB", className="me-1"),
                dbc.Modal(
                    [
                        dbc.ModalHeader(dbc.ModalTitle("Select Database")),
                        dbc.ModalBody([
                            dbc.Row([
                                dbc.Col("Server"),
                                dbc.Col(
                                    dbc.Input(id="server", placeholder="Indicate IP address", type="text", value=server))
                            ], align="center", style={'padding-bottom': '8px'}),
                            dbc.Row([
                                dbc.Col("Database"),
                                dbc.Col(
                                    dbc.Input(id="database", placeholder="Indicate database", type="text", value=database))
                            ], align="center", style={'padding-bottom': '8px'}),
                            dbc.Row([
                                dbc.Col("User"),
                                dbc.Col(
                                    dbc.Input(id="user", placeholder="Indicate user", type="text", value=user)),
                            ], align="center", style={'padding-bottom': '8px'}),
                            dbc.Row([
                                dbc.Col("Password"),
                                dbc.Col(
                                    dbc.Input(id="password", placeholder="Indicate password", type="password", value=password)),
                            ], align="center")
                        ]),
                        dbc.ModalFooter(
                            dbc.Button(
                                "Connect", id="connectDB", className="ms-auto", n_clicks=0
                            )
                        )
                    ],
                    id="modalDB",
                    is_open=False,
                ),
            ]
        )

    def getInfoButton(buttonId, download=False, href=''):
        infoButton = {
            "border": None,
            "border-radius": "50%",
            "fontSize": 16,
            "height": 30,
            "width": 30
        }

        if download:
            return dbc.Button(id=buttonId, href=href, external_link=True, className="fas fa-info", color="info",
                              outline=True, style=infoButton, target="_blank")

        return dbc.Button(id=buttonId, className="fas fa-info", color="info", outline=True, style=infoButton)

    def getActionButton(actionId, resultId, actionIcon, popOverText='Export'):
        return [dbc.Button(id=f'{actionId}-button-{resultId}', className=f'fa-solid {actionIcon}'),
                dbc.Popover(
                    popOverText,
                    target=f'{actionId}-button-{resultId}',
                    body=True,
                    trigger="hover",
                    placement='top'
                )]

    def selectResource(locationId, resourceType, infoButtonId='openLocationInfo',
                       info=['Location', 'Latitude', 'Longitude', 'Type', 'Area'], modalId='modalInfo'):
        modal = dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle('Resource information')),
                dbc.ModalBody([
                    dbc.Row([
                        dbc.Col('Resource: '),
                        dbc.Col(id=f'info{info[0]}', style={
                                'font-weight': 'bold'})
                    ], align='center', style={'padding-bottom': '8px'}),
                    dbc.Row([
                        dbc.Col('Latitude: '),
                        dbc.Col(id=f'info{info[1]}', style={
                                'font-weight': 'bold'})
                    ], align='center', style={'padding-bottom': '8px'}),
                    dbc.Row([
                        dbc.Col('Longitude: '),
                        dbc.Col(id=f'info{info[2]}', style={
                                'font-weight': 'bold'}),
                    ], align='center', style={'padding-bottom': '8px'}),
                    dbc.Row([
                        dbc.Col('Type: '),
                        dbc.Col(id=f'info{info[3]}', style={
                                'font-weight': 'bold'}),
                    ], align='center', style={'padding-bottom': '8px'}),
                    dbc.Row([
                        dbc.Col('Area: '),
                        dbc.Col(id=f'info{info[4]}', style={
                                'font-weight': 'bold'}),
                    ], align='center')
                ]),
                dbc.ModalFooter(
                    dbc.Button(
                        'Close', id='closeLocationInfo', className='ms-auto', n_clicks=0
                    )
                ),
            ],
            id=modalId,
            is_open=False,
        )

        resources = GenericCode.updateLocationsDropdown(resourceType)

        return dbc.Row([
            dbc.Col('Select resource', width='auto',
                    style={'padding-right': '0'}),
            dbc.Col(dcc.Dropdown(id=locationId,
                    options=resources, value=resources[0]['value'], clearable=False), width=5),
            dbc.Col(GenericCode.getInfoButton(infoButtonId),
                    style={'padding': 0}),
            modal
        ], align='center')
    
    def getLocationRow(resourceType):
        return [
            dbc.Col(GenericCode.selectResource(
                'locationsDropdown', resourceType)),
            dbc.Col(
                dbc.Row([
                    dbc.Col(GenericCode.selectDatabaseModal(
                        GenericCode.server, GenericCode.database, GenericCode.user,
                        GenericCode.password)),
                    dbc.Col(dbc.Nav([dbc.NavLink(href='/private', class_name='fa-solid fa-arrow-left',
                                                 style={'font-size': '20px', 'padding-right': '4px'})]), width='auto')
                ], align='center')
            ),
            dcc.Store(id='locationData', data={'Location': 1, 'Area': 1, 'Latitude': '39,92', 'Longitude': '-1.13',
                                               'Type': 'Consumer', 'AreaName': 'Aras de los Olmos'}),
            dcc.Store(id='newResource')
        ]

    def selectLocation(resourceType=None):
        return dbc.Row(GenericCode.getLocationRow(resourceType),
                       className='page-header-row generation-location')

    def getLocationLabel(locationOptions, locationValue):
        return [option['label'] for option in locationOptions if option['value'] == locationValue][0]

    def getHeader():
        return dbc.Row([
            dbc.Col(
                html.A(
                    html.Img(src=r'assets/logoInasolar.png',
                             style={'height': '130px',
                                    'width': '636px'},
                             alt='Inasolar Project',
                             title='Inasolar Project'),
                    href='https://inasolar.webs.upv.es/'
                ), width='auto'
            ),
            dbc.Col(
                dbc.Row([
                    dbc.Col(
                        html.A(
                            html.Img(src=r'assets/logoGeder.jpg',
                                     style={'height': '130px',
                                            'width': '196px'},
                                     alt='Geder Group',
                                     title='Geder Group'),
                            href='https://geder.es/'
                        ), width='auto'
                    ),
                    dbc.Col(
                        html.A(
                            html.Img(src=r'assets/logoUpv.png',
                                     alt='Universitat Politècnica de València',
                                     title='Universitat Politècnica de València'),
                            href='http://www.upv.es/'
                        ), width='auto'
                    ),
                ], justify='center', align='center')
            )
        ], align='center')
    
    def writeExcelData(writer, excelDataList, output, excelTitle, rangeDates, location):
        for excelData in excelDataList:
            excelData['Data'].to_excel(writer, sheet_name=excelData['SheetName'], index=False)

        dates = pd.DataFrame(rangeDates, index=[0])
        dates.to_excel(writer, sheet_name='Dates', index=False)
        loc = pd.DataFrame({'Location': location}, index=[0])
        loc.to_excel(writer, sheet_name='Location', index=False)            
        
        # Close the Pandas Excel writer and output the Excel file.
        writer.close()
        # extract the bytes from the BytesIO object
        data = output.getvalue()

        return dcc.send_bytes(data, excelTitle)

    def exportDataToExcel(excelData, sheetName, excelTitle, rangeDates, location):
        output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        
        return GenericCode.writeExcelData(writer, [{'SheetName': sheetName, 'Data': excelData}], output, excelTitle,
                                          rangeDates, location)

    def getHeaderOfListGroupItem(headerName, infoButton, className=''):
        return dbc.Row([
            dbc.Col(
                html.H5(headerName, className=f'card-title {className}'), width='auto'),
            dbc.Col(GenericCode.getInfoButton(infoButton), width='auto')
        ], justify='between', className='py-3')
    
    def createResultsCard(resultType, headerName, listGroupItemId=''):
        header = html.H4(headerName, className='m-4')
        resultType.insert(0, header)
        
        return dbc.Row([dbc.Col(dbc.ListGroupItem(resultType, id=listGroupItemId), width=12)], class_name='py-3', align='center')
        
    def createRange(rangeId, minDateAllowed):
        return [dbc.Col('Range', width='auto',
                        class_name='no-padding-right font-weight-bold'),
                dbc.Col(
            dcc.DatePickerRange(
                id=rangeId,
                min_date_allowed=minDateAllowed,
                display_format='YYYY/MM/DD'
            ), width="auto")
        ]

    def createResultTabs(resultId, cardBodyContent=[], auxTabs=[]):
        tableActionsRow = []
        if resultId == 'resourceAllocation':
            tableActionImport = dcc.Upload(GenericCode.getActionButton('import', resultId, 'fa-file-import', 'Import Optimization'),
                                                                       id='upload-file')
            importButton = dbc.Col(tableActionImport, width='auto')
            tableActionsRow.append(importButton)
            cardBodyContent.append(html.Div(id=f'{resultId}-rank'))                    
        
        tableActionExport = GenericCode.getActionButton('export', resultId, 'fa-file-export', 'Export')
        tableActionExport.append(dcc.Download(id=f'export-csv-{resultId}'))
        exportButton = dbc.Col(tableActionExport, width='auto',
                               style={'display':'none'}, id=f'{resultId}-exportCol')
        tableActionsRow.append(exportButton)
        
        tableActions = dbc.Row(tableActionsRow, justify='end', id=f'csv-row-{resultId}',className='mb-4')
        
        cardBodyContent.append(tableActions)
        cardBodyContent.append(dls.Grid([html.Div([dcc.Graph(id=f'{resultId}OptimizationGraph', figure={'data': []},
                                                             style={'display': 'none'}), ],
                                                  id=f'{resultId}-result-tabs-content'),
                                         dcc.Store(id={'type':'storeData', 'key':f'{resultId}Data'}, data={}),
                                         dash_table.DataTable(
                                             id=f'{resultId}Datatable'
                                             )
                                         ], color="#b3c2d6", debounce=100))
        tabs = [
            dbc.Tab(label='Graph', tab_id=f'{resultId}-tab-graph'),
            dbc.Tab(label='Table', tab_id=f'{resultId}-tab-table')
        ]
        tabs.append(auxTabs)
        
        
        return dbc.Card([
            dbc.CardHeader(
                dbc.Tabs(tabs,
                    id=f'{resultId}-result-data-tabs'
                )
            ),
            dbc.CardBody(cardBodyContent, class_name='card-result')
        ], id=f'{resultId}-result-card', class_name='mb-3')

    def roundNumber(value, digitsRounded = 2):
        if isinstance(value, (int, float)):
            return round(float(value), digitsRounded)
        return value

    def getGraphRangeSelector(pageId):
        if pageId == 'resourceAllocation':
            return dict(
                buttons=list([
                    dict(count=1, label="1d",
                         step="day", stepmode="backward"),
                    dict(count=7, label="1w",
                         step="day", stepmode="backward"),
                    dict(count=14, label="2w", step="day",
                         stepmode="backward"),
                    dict(count=1, label="1m", step="month",
                         stepmode="backward"),
                    dict(step="all")
                ])
            )

        return dict(
            buttons=list([
                dict(count=1, label="1d",
                     step="day", stepmode="backward"),
                dict(count=7, label="1w",
                     step="day", stepmode="backward"),
                dict(count=1, label="1m", step="month",
                     stepmode="backward"),
                dict(count=6, label="6m", step="month",
                     stepmode="backward"),
                dict(count=1, label="1y", step="year",
                     stepmode="backward"),
                dict(step="all")
            ])
        )

    def getGraphTickFormatStops():
        return [
            dict(dtickrange=[None, 1000],
                 value="%H:%M:%S.%L<br> %d %b (%a) %Y"),
            dict(dtickrange=[1000, 60000],
                 value="%H:%M:%S<br> %d %b (%a) %Y"),
            dict(dtickrange=[60000, 3600000],
                 value="%H:%M<br> %d %b (%a) %Y"),
            dict(dtickrange=[3600000, 86400000],
                 value="%H:%M<br> %d %b (%a) %Y"),
            dict(dtickrange=[86400000, 604800000],
                 value="%d %b (%a)<br> %Y"),
            dict(dtickrange=[604800000, "M1"],
                 value="%d %b (%a)<br> %Y"),
            dict(dtickrange=["M1", "M12"],
                 value="%d %b (%a)<br> %Y"),
            dict(dtickrange=["M12", None], value="%Y")
        ]

    def getAndParseDate(dateSql):
        maxDateAllowedSql = pd.read_sql(dateSql, GenericCode.engine)
        maxDateAllowed = datetime.strptime(
            str(maxDateAllowedSql['Date'].iloc[0]), '%Y-%m-%d %H:%M:%S')

        return maxDateAllowed.date()

    def generateParametersWithValue(parametersId, parametersValue):
        return {inputID['key']: inputValue for inputID, inputValue in zip(
            parametersId, parametersValue)}

    def getColumnColor(columnId, backgroundColor, color, ifKey='column_id'):
        return {
            'if': {ifKey: columnId},
            'backgroundColor': backgroundColor,
            'color': color
        }

    def changeLocationData(location):
        areaIdSql = pd.read_sql(
            f"SELECT l.*, a.Name AS AreaName FROM Locations l INNER JOIN Area a on l.Area = a.id WHERE l.id={location}", GenericCode.engine)
        areaFirstRow = areaIdSql.iloc[0]

        return {'Location': areaFirstRow['id'], 'Area': areaFirstRow['Area'], 'Latitude': areaFirstRow['Latitude'],
                'Longitude': areaFirstRow['Longitude'], 'Type': areaFirstRow['Type'], 'AreaName': areaFirstRow['AreaName'],
                'LocationName': areaFirstRow['Name']}

    def getLabelFromDropdown(dpOptions, dpValue):
        dpLabel = [x['label'] for x in dpOptions if x['value'] == dpValue]

        return dpLabel[0]

    def convertDate(date):
        date = pd.to_datetime(date)

        return date.dt.strftime('%Y-%m-%d %H:%M')

    def readJSON(dataToConvert):
        return pd.read_json(io.StringIO(dataToConvert), orient='split')

    def convertToJSON(dataToConvert):
        return dataToConvert.to_json(orient='split', date_format='iso')
    
    def waitQueueToBeEmpty():
        while not GenericCode.progress_queue.empty():
            pass
        
    def parseContents(importedFile, sheet_name=None):
        try:
            # Se filtra el contenido y se decodifica para obtener el Dataframe
            content_type, content_string = importedFile.split(',')
            decoded = base64.b64decode(content_string)        
            
            return pd.read_excel(io.BytesIO(decoded), sheet_name)
        
        except Exception as e:
            raise Exception(f'Excel file is not correct, check the format. ({e})')
            
    def getMaxDemand(location, demandSelected):
        return int(pd.read_sql(f'SELECT MAX({demandSelected}) FROM datosGEDER2 WHERE location = {location}', GenericCode.engine).iloc[0].iloc[0])

    # VARIABLES
    # ---------------------------------------------------------------
    server = "158.42.22.107"
    database = "inasolar"
    user = "GEDER"
    password = "GEDER"
    engine = selectDB(server, database, user, password)
    progress_queue = Queue(1)
    executingOptimization = False
    stopOptimization = False
    MAX_DEMAND = None

    # Callbacks genéricos
    # --------------------------------------------------------------
    @callback(
        Output('locationsDropdown', 'options'),
        Input('url', 'pathname'),
        Input('newResource', 'data'),
        State('locationsDropdown', 'options'))
    def updateLocationsStore(pageUrl, newResource, lastLocations):
        if ((ctx.triggered_id == 'newResource' and newResource) or
            (not ctx.triggered_id and ('resourceallocation' in pageUrl.lower() or 'unitcommitment' in pageUrl.lower()))):
            return GenericCode.updateLocationsDropdown('Consumer')
        
        elif not ctx.triggered_id and ('inasolargraphs' in pageUrl.lower() or 'similardays' in pageUrl.lower()):
            return GenericCode.updateLocationsDropdown()
                
        return lastLocations
                
    @callback(
        Output('locationData', 'data'),
        Input('locationsDropdown', 'value')
    )
    def changingLocation(location):
        return GenericCode.changeLocationData(location)

    @callback(
        Output("modalDB", "is_open"),
        [Input("openDB", "n_clicks"), Input("connectDB", "n_clicks")],
        [State("modalDB", "is_open"), State("server", "value"), State(
            "database", "value"), State("user", "value"), State("password", "value")],
    )
    def open_DB_modal(openDB, connectDB, is_open, server, database, user, password):

        if openDB:
            return not is_open

        if connectDB:
            GenericCode.engine = GenericCode.selectDB(
                server, database, user, password)
            return False

        return is_open

    @callback(
        Output("modalInfo", "is_open"),
        Output("infoLocation", "children"),
        Output("infoLatitude", "children"),
        Output("infoLongitude", "children"),
        Output("infoType", "children"),
        Output("infoArea", "children"),
        Input("openLocationInfo", "n_clicks"),
        State("locationData", 'data'),
        Input("closeLocationInfo", "n_clicks"),
        prevent_initial_call=True
    )
    def open_info_modal(openLocationInfo, locationData, closeLocationInfo):
        if ctx.triggered_id == 'openLocationInfo':
            return True, locationData['LocationName'], locationData['Latitude'], locationData['Longitude'], locationData['Type'], locationData['AreaName']

        return False, '', '', '', '', ''
