from dash import dcc, html, ctx, callback
from datetime import date, timedelta
from plotly.subplots import make_subplots
from dash.dependencies import Input, Output, State
import pandas as pd
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
import dash_loading_spinners as dls
import time
import io
import dash
from .genericCode import GenericCode


# Funciones para iniciar Dash
# ---------------------------------------------------------------
PAGE_TITLE = 'Inasolar Graphs'
dash.register_page(__name__, title=PAGE_TITLE)


# Variables de inicio
# ---------------------------------------------------------------

dataY1 = pd.read_sql(
    "SELECT h.*, d.Date FROM [HistoricalWeather] h INNER JOIN Dates d ON h.date = d.id WHERE Area=1", GenericCode.engine)
dataY1['Date'] = pd.to_datetime(dataY1['Date'], format='%d/%m/%Y %H:%M')
dataY2 = pd.read_sql(
    "SELECT h.*, d.Date FROM datosGEDER2 h INNER JOIN Dates d ON h.date = d.id WHERE location=1 ORDER BY d.date DESC", GenericCode.engine)


# Funciones globales a utilizar
# ---------------------------------------------------------------

def updateDatosDropdown(tableName, notNullColumns):
    dropdownOptions = []
    dropdownOptionsSql = pd.read_sql(
        f"SELECT * FROM descripcionDatos WHERE Tabla = '{tableName}' ORDER BY nombre_alternativo", GenericCode.engine)
    dropdownOptionsSql = dropdownOptionsSql.loc[dropdownOptionsSql['nombre_dato'].isin(notNullColumns)]

    for index, row in dropdownOptionsSql.iterrows():
        nombreAlternativo = row['nombre_alternativo']
        if nombreAlternativo == 'Power':
            nombreAlternativo += ' (>0 for consumption, <0 for production)'
        dropdownOptions.append({'label': nombreAlternativo,
                                'value': row['nombre_dato']})

    dpValue = ''
    if tableName == 'datosGEDER2':
        dpValue = 'Power'
        
    elif tableName == 'HistoricalWeather':
        dpValue = 'temperature_2m'
        
    elif len(dropdownOptions) > 0:
        dpValue = dropdownOptions[0].get('value')        
        
    return dropdownOptions, dpValue


def updateDbDropdown():
    dbDropdownOptions = []
    dbDropdownSql = pd.read_sql(
        "SELECT * FROM TableDescriptions", GenericCode.engine)

    for index, row in dbDropdownSql.iterrows():
        dbDropdownOptions.append({'label': row['TableName'],
                                  'value': row['TableId']})

    return dbDropdownOptions


def updateYAxis(nombreDato, dbName, secondaryY, yData, fig, filterDate):
    descripcionDatosSql = pd.read_sql(
        f"SELECT * FROM descripcionDatos WHERE nombre_dato = '{nombreDato}'", GenericCode.engine)
    axisTitle = ''
    if len(descripcionDatosSql) > 0:
        YValueName = descripcionDatosSql['nombre_alternativo'].iloc[0]
        YValueUnit = descripcionDatosSql['unidad'].iloc[0].strip()
        axisTitle = f'<b>{YValueName} ({YValueUnit})</b>'
        fig.add_trace(
            go.Scatter(x=filterDate, y=yData[nombreDato],
                       name=YValueName, hovertemplate='%{y:.2f}' + ' %s' % YValueUnit),
            secondary_y=secondaryY,
        )
    
    if secondaryY:
        fig.update_layout(yaxis2_title=axisTitle)
    else:
        fig.update_layout(yaxis_title=axisTitle)


def dateTimeCorrect(startDate, endDate, startHour, endHour):
    if startDate is None or endDate is None:
        return False

    try:
        time.strptime(startHour, '%H:%M')
        time.strptime(endHour, '%H:%M')
        return True
    except ValueError:
        return False


def filterDropdownByValue(value, dropdownOptions):
    return next((item for item in dropdownOptions if item["value"] == value), None).get('value')


# Código HTML que se encuentra en la página
# ---------------------------------------------------------------
graphActionsRow = GenericCode.getActionButton('export', 'inasolarGraphs', 'fa-file-export')
graphActionsRow.append(dcc.Download(id='export-csv-inasolarGraphs'))

layout = html.Div([
    html.H2(PAGE_TITLE),
    GenericCode.selectLocation(),
    dbc.Row([
        dbc.Col(
            dbc.Card(
                [
                    dbc.CardHeader(
                        dbc.Tabs(
                            [
                                dbc.Tab(label="Primary Y Axis", tab_id="primaryYAxis", label_style={
                                    "color": "blue", "font-weight": "bold"}),
                            ],
                            id="card-tabs1",
                            active_tab="tab-1",
                        ), class_name='no-padding-top'
                    ),
                    dbc.CardBody(dbc.Row([
                        dbc.Col(dcc.Dropdown(id="dbDropdown1", options=updateDbDropdown(),
                                             value="HistoricalWeather", clearable=False), width=4),
                        dbc.Col(dls.Beat(dcc.Dropdown(id="dropdown1Data", clearable=False),
                                         color="#b3c2d6"), width=8)
                    ])),
                ], class_name='height-total')
        ),
        dbc.Col(
            dbc.Card(
                [
                    dbc.CardHeader(
                        dbc.Tabs(
                            [
                                dbc.Tab(label="Secondary Y Axis", tab_id="secondaryYAxis", label_style={
                                    "color": "red", "font-weight": "bold"}),
                            ],
                            id="card-tabs2",
                            active_tab="tab-1",
                        ), class_name='no-padding-top'
                    ),
                    dbc.CardBody(dbc.Row([
                        dbc.Col(dcc.Dropdown(
                            id="dbDropdown2", options=updateDbDropdown(), value="datosGEDER2", clearable=False), width=4),
                        dbc.Col([dls.Beat(dbc.Row([dcc.Dropdown(id="dropdown2Data")]),
                                          color="#b3c2d6"),
                                 dbc.Row([dbc.Checkbox(id="inverse-axis",
                                                       label="Inverse Axis",
                                                       value=False,
                                                       )], class_name='pt-1 inverse-axis')], width=8)
                    ]), className='pb-0'),
                ])
        )
    ]),
    dbc.Row([
        dbc.Col(
            dbc.Row([
                dbc.Col("Start date", width="auto", class_name='no-padding-right'),
                dbc.Col(dcc.DatePickerSingle(
                    id='startDate',
                    min_date_allowed=date(2019, 1, 1),
                    date=date.today() - timedelta(days=365*2),
                    display_format='YYYY/MM/DD',
                    className='pt-0'
                ), width="auto", class_name='no-padding-right'),
                dbc.Col(dbc.Input(id="startHour", placeholder="Hour (HH:MM)",
                        value="00:00", type="text", debounce=True), width=3),
                dbc.Col(dbc.Button("Reset", id="resetStartDate",
                        className="ms-auto", n_clicks=0))
            ], align="center")
        ),
        dbc.Col(
            dbc.Row([
                dbc.Col(
                    dbc.Row([
                        dbc.Col("End date", class_name='no-padding-right', width="auto"),
                        dbc.Col(dcc.DatePickerSingle(
                            id='endDate',
                            min_date_allowed=date(2019, 1, 1),
                            date=date.today(),
                            display_format='YYYY/MM/DD'), className='no-padding-right', width="auto"),
                        dbc.Col(dbc.Input(id="endHour", placeholder="Hora (HH:MM)",
                                value="23:00", type="text", debounce=True), width=3),
                        dbc.Col(dbc.Button("Reset", id="resetEndDate",
                                className="ms-auto", n_clicks=0), width='auto'),
                    ], align='center')
                ),
                dbc.Col(
                    dbc.Row(graphActionsRow),
                    width='auto', class_name='csv-export')
            ], align="center")
        ),
    ], class_name='mt-3'),
    dbc.Row([
        dbc.Col(html.Div(id='output-container-date-picker-single', className='color-red'),
                width={"size": "auto", "offset": 4})
    ], align="center", class_name='mt-3'),
    dbc.Row([dls.Grid(dcc.Graph(id="graphInasolarGraphs"), color="#b3c2d6", debounce=100)])
], className='py-3')


# Callbacks de la página
# ---------------------------------------------------------------

@callback(
    Output('export-csv-inasolarGraphs', 'data'),
    Input('export-button-inasolarGraphs', 'n_clicks'),
    State('dropdown1Data', 'value'),
    State('dropdown2Data', 'value'),
    [State('locationsDropdown', 'value'), State(
        'locationsDropdown', 'options')],
    [State('startDate', 'date'), State('endDate', 'date')],
    [State('startHour', 'value'), State('endHour', 'value')]
)
def exportDataToExcel(csvFile, dato1, dato2, locationValue, locationOptions, startDate, endDate, startHour, endHour):
    if csvFile:
        # Creamos un dataframe con los valores que se encuentran en la gráfica
        completeStartDate = f"{startDate} {startHour}"
        completeEndDate = f"{endDate} {endHour}"

        dataY1Filter = dataY1.loc[
            dataY1['Date'].between(
                pd.to_datetime(completeStartDate), pd.to_datetime(
                    completeEndDate)
            )
        ]

        dataY2Filter = dataY2.loc[
            dataY2['Date'].between(
                pd.to_datetime(completeStartDate), pd.to_datetime(
                    completeEndDate)
            )
        ]

        output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')

        sheet1 = pd.DataFrame(
            {'Date': dataY1Filter['Date'], dato1: dataY1Filter[dato1]})
        sheet2 = pd.DataFrame(
            {'Date': dataY2Filter['Date'], dato2: dataY2Filter[dato2]})

        # Write each dataframe to a different worksheet.
        sheet1.to_excel(writer, sheet_name='Primary Y Axis', index=False)
        sheet2.to_excel(writer, sheet_name='Secondary Y Axis', index=False)

        # Close the Pandas Excel writer and output the Excel file.
        writer.close()
        data = output.getvalue()

        # Se obtiene la localización de donde se están cogiendo los datos
        locationLabel = GenericCode.getLocationLabel(
            locationOptions, locationValue)

        return dcc.send_bytes(data, f"inasolarGraphs_{locationLabel}_{startDate}_{endDate}.xlsx")


@callback(
    Output("startDate", "date"),
    Output("startHour", "value"),
    Input("resetStartDate", "n_clicks"),
    prevent_initial_call=True
)
def resetStartDate(resetStartDate):
    if resetStartDate:
        return date(2019, 1, 1), "00:00"


@callback(
    Output("endDate", "date"),
    Output("endHour", "value"),
    Input("resetEndDate", "n_clicks"),
    prevent_initial_call=True
)
def resetEndDate(resetEndDate):
    if resetEndDate:
        return date.today(), "23:00"


@callback(
    Output('dropdown1Data', 'options'),
    Output('dropdown1Data', 'value'),
    Input('dbDropdown1', 'value'),
    Input('locationData', 'data')
)
def updateDropdown1(dbDropdown1, locationData):
    global dataY1

    areaSql = pd.read_sql(
        f"SELECT Area FROM TableDescriptions WHERE TableId='{dbDropdown1}'", GenericCode.engine)

    if areaSql['Area'].iloc[0]:
        dataY1 = pd.read_sql(
            f"""SELECT h.*, d.Date
                FROM {dbDropdown1} h
                INNER JOIN Dates d ON h.date = d.id
                WHERE Area={locationData['Area']}
                ORDER BY d.date DESC""", GenericCode.engine)

    else:
        dataY1 = pd.read_sql(
            f"""SELECT h.*, d.Date
                FROM {dbDropdown1} h
                INNER JOIN Dates d ON h.date = d.id
                WHERE location={locationData['Location']}
                ORDER BY d.date DESC""", GenericCode.engine)
    
    notNullColumns = dataY1.dropna(axis=1, how='all').columns
    dropdown1DataOptions, dropdown1DataValue = updateDatosDropdown(dbDropdown1, notNullColumns)
    dataY1['Date'] = pd.to_datetime(dataY1['Date'], format='%d/%m/%Y %H:%M')
    
    return dropdown1DataOptions, dropdown1DataValue


@callback(
    Output('dropdown2Data', 'options'),
    Output('dropdown2Data', 'value'),
    Input('dbDropdown2', 'value'),
    Input('locationData', 'data')
)
def updateDropdown2(dbDropdown2, locationData):
    global dataY2

    areaSql = pd.read_sql(
        f"SELECT Area FROM TableDescriptions WHERE TableId='{dbDropdown2}'", GenericCode.engine)

    if areaSql['Area'].iloc[0]:
        dataY2 = pd.read_sql(
            f"""SELECT h.*, d.Date
                FROM {dbDropdown2} h
                INNER JOIN Dates d ON h.date = d.id
                WHERE Area={locationData['Area']}
                ORDER BY d.date DESC""", GenericCode.engine)

    else:
        dataY2 = pd.read_sql(
            f"""SELECT h.*, d.Date
                FROM {dbDropdown2} h
                INNER JOIN Dates d ON h.date = d.id 
                WHERE location={locationData['Location']}
                ORDER BY d.date DESC""", GenericCode.engine)

    notNullColumns = dataY2.dropna(axis=1, how='all').columns
    dropdown2DataOptions, dropdown2DataValue = updateDatosDropdown(dbDropdown2, notNullColumns)        
    dataY2['Date'] = pd.to_datetime(dataY2['Date'], format='%d/%m/%Y %H:%M')
    
    return dropdown2DataOptions, dropdown2DataValue


@callback(
    Output('output-container-date-picker-single', 'children'),
    [Input('startDate', 'date'), Input('endDate', 'date'), Input(
        'startHour', 'value'), Input('endHour', 'value')],
    prevent_initial_call=True
)
def checkDates(startDate, endDate, startHour, endHour):
    if not dateTimeCorrect(startDate, endDate, startHour, endHour):
        return 'Date format is not correct'
    if startDate > endDate:
        return 'Start date can not be higher than end date'


@callback(
    Output('graphInasolarGraphs', 'figure'),
    Output('graphInasolarGraphs', 'config'),
    Input('locationData', 'data'),
    Input('dropdown1Data', 'value'),
    Input('dropdown2Data', 'value'),
    Input('startDate', 'date'),
    Input('endDate', 'date'),
    Input('startHour', 'value'),
    Input('endHour', 'value'),
    Input('inverse-axis', 'value'),
    [State('dbDropdown1', 'value'), State(
        'dbDropdown2', 'value'), State('graphInasolarGraphs', 'figure')],
)
def display_(location, dato1, dato2, startDate, endDate, startHour, endHour, inverseAxis, db1, db2, existing_state):
    global dataY1
    global dataY2

    config = {'displaylogo': False}

    if ctx.triggered_id == 'locationData':
        updateDropdown1(db1, location)
        updateDropdown2(db2, location)

    if not dateTimeCorrect(startDate, endDate, startHour, endHour):
        return { 'data': [], 'layout': {}, 'frames': [],}, config

    completeStartDate = f"{startDate} {startHour}"
    completeEndDate = f"{endDate} {endHour}"

    dataY1Filter = dataY1.loc[
        dataY1['Date'].between(
            pd.to_datetime(completeStartDate), pd.to_datetime(completeEndDate)
        )
    ]

    dataY2Filter = dataY2.loc[
        dataY2['Date'].between(
            pd.to_datetime(completeStartDate), pd.to_datetime(completeEndDate)
        )
    ]        

    filterDateY1 = dataY1Filter['Date']
    filterDateY2 = dataY2Filter['Date']

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    updateYAxis(dato1, db1, False, dataY1Filter, fig, filterDateY1)
    if dato2 is None:
        fig['layout']['yaxis2']['showgrid'] = False

    else:
        if inverseAxis:
            # Reverse the second y-axis
            dataY2Filter[dato2] = dataY2Filter[dato2] * -1

        updateYAxis(dato2, db2, True, dataY2Filter, fig, filterDateY2)

    if dato1 is None:
        fig['layout']['yaxis']['showgrid'] = False

    # # Set x-axis
    fig.update_xaxes(title_text="Date", nticks=8, rangeslider_visible=True,
                     rangeselector=GenericCode.getGraphRangeSelector('inasolarGraphs'),
                     tickformatstops=GenericCode.getGraphTickFormatStops(),
                     uirevision='time')

    fig.update_layout(uirevision=True, hovermode="x unified")

    return fig, config
