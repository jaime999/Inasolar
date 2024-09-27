import dash_bootstrap_components as dbc
import dash_loading_spinners as dls
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from dash import dcc, html, ALL, dash_table, ctx, callback, clientside_callback, register_page
from dash.dependencies import Input, Output, State
from datetime import timedelta, date
from .genericCode import GenericCode
from .similarDaysGeneric import SimilarDays, TYPE_OF_DAYS, POWER_SQL
from .filtro_dias import filtro_dias


# Funciones para iniciar Dash
# ---------------------------------------------------------------
PAGE_TITLE = 'Similar Days'
register_page(__name__, title=PAGE_TITLE)


# FUNCIONES
# ---------------------------------------------------------------
def generateGraphButtons(label, args):
    return [
        dict(
            method='restyle',
            label=label,
            args=args
        )
    ]


def setTargetTableSimilarDays():
    columns = [{'name': 'Power(kW)', 'id': 'Power'}]

    return SimilarDays.getTargetDateTable('similarDays', columns)


def setResultTableSimilarDays(similarDaysTable, ponders):
    columns = [{'name': 'Power(kW)', 'id': 'Power'}]
    if ponders:
        columns.append({'name': 'Score', 'id': 'score_final'})

    for index, row in SIMILAR_DAYS_RESULT_COLUMNS_SQL.iterrows():
        columns.append(
            {'name': f"{row['nombre_alternativo']}({row['unidad'].strip()})", 'id': row['nombre_dato']})

    return dash_table.DataTable(
        id='similarDays-resultTable',
        data=similarDaysTable.map(
            GenericCode.roundNumber).to_dict('records'),
        sort_action='native',
        columns=SimilarDays.setColumnsTable(columns),
        page_current=0,
        page_size=10,
        page_action='native',
        style_table={'overflowX': 'auto', 'min-width': '100%'},
        style_cell={'textAlign': 'left'},
        style_header={'border': '1px solid green'},
        style_data_conditional=[
            GenericCode.getColumnColor('Power','rgb(30, 30, 30)','white'),
            GenericCode.getColumnColor('score_final','rgb(204, 255, 189)','black')],
        style_header_conditional=[
            GenericCode.getColumnColor('Power','rgb(30, 30, 30)','white'),
            GenericCode.getColumnColor('score_final','rgb(176, 255, 153)','black'),
            GenericCode.getColumnColor('Date','rgb(255, 142, 142)','black')],
        fixed_columns={'headers': True, 'data': 1}
    )               


# VARIABLES
# ---------------------------------------------------------------
SIMILAR_DAYS_RESULT_COLUMNS_SQL = pd.read_sql(
    """SELECT nombre_dato, nombre_alternativo, unidad
       FROM descripcionDatos
       WHERE Tabla = 'SimilarDays'
       ORDER BY [Order] DESC""", GenericCode.engine)
maxDateAllowed, daysWithPowerNull = SimilarDays.setMaxDateAllowedAndDisabledDays(1)
similarDays = None


# HTML
# ---------------------------------------------------------------
targetDate = dbc.Row([
    dbc.Col(html.Div([dbc.Row([
            dbc.Col('Target Date', width='auto',
                    class_name='no-padding-right font-weight-bold'),
            dbc.Col(
                dcc.DatePickerSingle(
                    id='target-date-picker',
                    min_date_allowed=date(2019, 1, 1),
                    max_date_allowed=maxDateAllowed,
                    date=maxDateAllowed,
                    disabled_days=daysWithPowerNull,
                    display_format='YYYY/MM/DD',
                ), width='auto')], align='center', justify='center'),
        dbc.Row([
                dbc.Col(id='output-container-target-date',
                        class_name='color-red no-padding-left',
                        width='auto'),
                ], align='center', justify='center', class_name='mt-3')
    ]), width=3),
    dbc.Col(setTargetTableSimilarDays(), width=9)
], align='center', justify='center')

# Se crea el componente de rango de fechas en GenericCode, y se le añade
# el checkbox de días anteriores
rangeRow = SimilarDays.createRangeAndSetDays(1, 'similarDaysIntervalDatePicker')
rangeRow.append(dbc.Col(dbc.Checkbox(
    id="checkbox-target-date",
    label="Past Days",
    value=False,
    label_class_name="mb-auto"
)))
datesCard = dls.Grid(dbc.ListGroupItem(SimilarDays.getDatesCard(
    rangeRow, 'similarDays', targetDate)), color="#b3c2d6", debounce=100)

searchButton = dbc.ListGroupItem(
    dbc.Row([
        dbc.Col(SimilarDays.generateQuantiles('Low. quantile(%)', 'lowQuantile', 10), width=3, class_name='pt-3'
                ),
        dbc.Col(SimilarDays.generateQuantiles('Upp. quantile(%)', 'uppQuantile', 90), width=3, class_name='pt-3'
                ),
        dbc.Col(
            dbc.Button(
                'Search', className='mt-auto', id='similarDaysSearchButton'
            ), width='auto'
        )
    ], className='searchRowSimilarDays', align='center')
)

resultTabs = GenericCode.createResultTabs('similarDays')

modal = GenericCode.createModal('Information', 'similarDays')

searchTabs = dbc.Card([
    SimilarDays.getHeaderSearchTabs(),
    dbc.CardBody(html.Div([dbc.CardGroup(
        [
            dbc.Card(
                 dbc.ListGroup(
                     [
                           datesCard,
                           dls.Grid(html.Div(SimilarDays.generateMarginsCard(), id='search-tabs-content'),
                                    color="#b3c2d6", debounce=100),
                           searchButton
                           ],
                 ), color='success', outline=True
                 )
        ]
    )]), className='p-0')
], class_name='mb-4')


layout = html.Div([
    html.H2(PAGE_TITLE),
    GenericCode.selectLocation(),
    searchTabs,
    resultTabs,
    modal
], id='similarDays-container', className='py-3')


# CALLBACKS
# ---------------------------------------------------------------
@callback(
    Output('output-container-target-date', 'children'),
    Output('output-container-target-date', 'class_name'),
    Output({'type': 'similarDaysTypeOfDayCheckbox', 'key': ALL}, 'value'),
    [Input('target-date-picker', 'date'), State('target-date-picker', 'min_date_allowed'),
     State('target-date-picker', 'max_date_allowed'), State('target-date-picker', 'disabled_days')],
    Input('locationData', 'data'),
)
def checkTargetDateConditions(targetDate, minDateAllowed, maxDateAllowed, disabledDays, locationData):
    # Se seleccionan los checkbox de tipos de días correspondientes al tipo de día seleccionado,
    # por defecto están a False
    typeOfDaysCheckbox = [False for item in TYPE_OF_DAYS]

    # Si la fecha es incorrecta, se deshabilita el botón de búsqueda
    if targetDate is None:
        return 'Date format is not correct or is not allowed', 'color-red', typeOfDaysCheckbox
    if targetDate < minDateAllowed:
        return 'Target date is lower than min date allowed', 'color-red', typeOfDaysCheckbox
    if targetDate > maxDateAllowed:
        return 'Target date is higher than max date allowed', 'color-red', typeOfDaysCheckbox
    if targetDate in disabledDays:
        return 'There is no power in that target date', 'color-red', typeOfDaysCheckbox

    # Se comprueba el tipo de día que es y se muestra por pantalla
    typeOfDaysSql = pd.read_sql(
        f"""SELECT {', '.join(TYPE_OF_DAYS.keys())}
            FROM Holidays h
            INNER JOIN Dates d on d.id = h.date
            WHERE d.Date = CONVERT(DATETIME, '{targetDate}', 102) AND Area = {locationData['Area']}""", GenericCode.engine)

    targetTypeOfDay = []
    typeOfDaysCheckbox = []

    for colName, colData in typeOfDaysSql.items():
        if colData.item():
            targetTypeOfDay.append(colName)
            typeOfDaysCheckbox.append(True)

        else:
            typeOfDaysCheckbox.append(False)

    targetTypeOfDayLabel = [TYPE_OF_DAYS[item]
                            for item in targetTypeOfDay if item in TYPE_OF_DAYS]

    return ", ".join(targetTypeOfDayLabel), 'color-blue', typeOfDaysCheckbox


@callback(
    Output('export-csv-similarDays', 'data'),
    Input('export-button-similarDays', 'n_clicks'),
    State({'type': 'storeData', 'key': 'similarDaysData'}, 'data'),
)
def exportData(csvFile, similarDaysData):
    if csvFile:
        return GenericCode.exportDataToExcel(similarDays, 'Similar Days', 'similarDays.xlsx', similarDaysData['Dates'], similarDaysData['Location'])
    
    return None


@callback(
    Output('similarDays-targetDate', 'data'),
    Input('target-date-picker', 'date'),
    Input('locationData', 'data')
)
def getTargetDateInfo(targetDate, locationData):
    if targetDate is not None:
        dateInfo = filtro_dias.getDateInfoHistoricalWeather(targetDate, locationData).map(GenericCode.roundNumber)

        return dateInfo.to_dict('records')


@callback(
    Output('target-date-picker', 'date'),
    Output('target-date-picker', 'max_date_allowed'),
    Output('target-date-picker', 'disabled_days'),
    Output('similarDaysIntervalDatePicker', 'start_date'),
    Output('similarDaysIntervalDatePicker', 'end_date'),
    Output('similarDaysIntervalDatePicker', 'max_date_allowed'),
    Input('checkbox-target-date', 'value'),
    Input('target-date-picker', 'date'),
    Input('locationData', 'data'),
    State('similarDaysIntervalDatePicker', 'max_date_allowed'),
    State('target-date-picker', 'disabled_days'),
    State('similarDaysIntervalDatePicker', 'start_date'),
)
def updateDates(pastDays, targetDate, location, oldMaxDateAllowed, oldDisabledDays, oldStartDate):
    maxDateAllowed, disabledDays = SimilarDays.setMaxDateAllowedAndDisabledDays(
        location['Location'])

    if ctx.triggered_id != 'locationData' and pastDays:
        return targetDate, maxDateAllowed, disabledDays, oldStartDate, targetDate, targetDate

    if ctx.triggered_id == 'locationData':
        return maxDateAllowed, maxDateAllowed, disabledDays, maxDateAllowed - timedelta(days=365), maxDateAllowed, maxDateAllowed

    return targetDate, maxDateAllowed, disabledDays, oldStartDate, targetDate, maxDateAllowed


@callback(
    Output('similarDaysSearchButton', 'disabled'),
    Input({'type': 'weather-input', 'key': ALL}, 'disabled'),
    Input({'type': 'weather-input', 'key': ALL}, 'value'),
    Input('num-days', 'value'),
    Input('output-container-target-date', 'class_name'),
    Input({'type': 'similarDaysTypeOfDayCheckbox', 'key': ALL}, 'value'),
)
def disableSearchButton(inputsDisabled, inputsValue, numDays, targetDateClass, typesOfDay):
    # Si hay un fallo en la target date, se deshabilita el botón
    return (targetDateClass == 'color-red' or (type(numDays) == type(None) or float(numDays) < 0)
        or (not any(typesOfDay))
        or SimilarDays.disableButton(inputsValue, inputsDisabled))
    

# Al hacer click en buscar, se va al final de la página
clientside_callback(
    """
    function(n_clicks) { 
        if (n_clicks > 0) {
            window.scrollTo(0, 800);
            return 'container'
        }                            
    }
    """,
    Output('similarDays-container', 'key'),
    Input('similarDaysSearchButton', 'n_clicks'),
    prevent_initial_call=True
)


@callback(
    Output('similarDays-result-tabs-content', 'children'),
    Output('similarDays-exportCol', 'style'),
    Output({'type': 'storeData', 'key': 'similarDaysData'}, 'data'),
    [Input('similarDaysSearchButton', 'n_clicks')],
    State({'type': 'weather-input', 'key': ALL}, 'value'),
    State({'type': 'weather-input', 'key': ALL}, 'id'),
    State({'type': 'weather-input', 'key': ALL}, 'disabled'),
    State({'type': 'similarDaysTypeOfDayCheckbox', 'key': ALL}, 'value'),
    State('target-date-picker', 'date'),
    State('similarDaysIntervalDatePicker', 'start_date'),
    State('similarDaysIntervalDatePicker', 'end_date'),
    State('num-days', 'value'),
    State('locationData', 'data'),
    State('search-data-tabs', 'active_tab'),
    Input('similarDays-result-data-tabs', 'active_tab'),
    State('lowQuantile', 'value'),
    State('uppQuantile', 'value'),
    [State('locationsDropdown', 'value'), State(
        'locationsDropdown', 'options')],
    prevent_initial_call=True
)
def searchSimilarDays(searchButton, inputsValue, inputsId, inputsDisabled, typeOfDaysValue, targetDate,
                      startDate, endDate, numDays, location, searchTab, resultTab,
                      lowQuantile, uppQuantile, locationValue, locationOptions):

    csvNotDisplayed = {'display': 'none'}
    similarDaysData = {}
    if searchButton:
        typeOfDays = SimilarDays.getTypeOfDays(typeOfDaysValue)

        global similarDays
        bestDays = None
        searchTabSelected = 'Margins'
        if searchTab == 'tab-margins':
            # Mediante esta función, asociamos cada ID de cada input a su valor, y eliminamos las que no tengan valor
            margins = SimilarDays.getMargins(inputsId, inputsValue, inputsDisabled)
            similarDays = filtro_dias.get_days_by_similar_meteorological_variables_margins(
                targetDate, margins, startDate, endDate, location, typeOfDays)

            if 'errorMessage' in similarDays:
                return dbc.Alert(similarDays['errorMessage'], color='danger'), csvNotDisplayed, similarDaysData

        if searchTab == 'tab-ponders':
            bestDays, dayData = filtro_dias.get_days_by_similar_meteorological_variables_ponders(
                targetDate, inputsValue, location['Location'], startDate, endDate, numDays)

            if 'errorMessage' in bestDays:
                return dbc.Alert(bestDays['errorMessage'], color='danger'), csvNotDisplayed, similarDaysData

            similarDays = filtro_dias.getSimilarDaysByHours(bestDays, dayData, targetDate)
            searchTabSelected = 'Ponders'

        # Se obtiene la localización de donde se están cogiendo los datos
        locationLabel = GenericCode.getLocationLabel(
            locationOptions, locationValue)
        
        similarDaysData['Dates'] = {'StartDate': startDate, 'EndDate': endDate}
        similarDaysData['Location'] = locationLabel

        if resultTab == 'similarDays-tab-graph':
            date_object = date.fromisoformat(targetDate)
            date_string = date_object.strftime('%Y-%m-%d')

            fig = go.Figure()
            fig = px.line(similarDays, x='Hour', y='Power', color='Date',
                          hover_data=['Date'], title=f'{searchTabSelected}: {locationLabel}')
            fig.for_each_trace(
                lambda trace: trace.update(
                    line=dict(width=8)) if trace.name == date_string else ()
            )

            fig.update_traces(
                hovertemplate='Date: %{customdata[0]|%Y-%m-%d (%a)}<br>Hour: %{x}<br>Power: <b>%{y:.2f}' +
                ' %s</b>' % POWER_SQL["unidad"].iloc[0],
                selector=dict(type='scatter'))

            # Se añaden los botones para mostrar u ocultar todas las fechas
            fig.update_layout(yaxis_title='Power (kW)',
                              updatemenus=[
                                  dict(
                                      type='buttons',
                                      direction='right',
                                      x=0.7,
                                      y=1.1,
                                      showactive=False,
                                      buttons=generateGraphButtons(
                                          'Show all traces', [{'visible': True}]) + generateGraphButtons(
                                          'Hide all traces', [{'visible': 'legendonly'}])
                                  )
                              ])

            targetDayPower = similarDays[similarDays['Date']
                                         == targetDate]['Power']
            fig2 = go.Figure()
            q1, median, q3, lowerfence, upperfence = filtro_dias.calculateBounds(
                similarDays, lowQuantile, uppQuantile)
            fig2.add_trace(go.Box(name='Demand forecast box plot', q1=q1,
                                  median=median,
                                  q3=q3,
                                  lowerfence=lowerfence,
                                  upperfence=upperfence,
                                  hovertemplate='Hour: %{x}<br>' +
                                  'Q1: %{q1}' + ' %s<br>' % POWER_SQL["unidad"].iloc[0] +
                                  'Median: %{median}' + ' %s<br>' % POWER_SQL["unidad"].iloc[0] +
                                  'Q3: %{q3}' + ' %s<br>' % POWER_SQL["unidad"].iloc[0] +
                                  'Lower fence: %{lowerfence}' + ' %s<br>' % POWER_SQL["unidad"].iloc[0] +
                                  'Upper fence: %{upperfence}' + ' %s' % POWER_SQL["unidad"].iloc[0]))
            fig2.add_trace(go.Scatter(
                x=similarDays['Hour'], y=targetDayPower,
                mode='lines', name=targetDate,
                hovertemplate='Hour: %{x}<br>Power: <b>%{y:.2f}' +
                ' %s</b>' % POWER_SQL["unidad"].iloc[0]
            ))

            fig2.update_layout(yaxis_title='Power (kW)', xaxis_title='Hour',
                               title=f'Demand interval forecast: {lowQuantile}%-{uppQuantile}%')

            config = {'displaylogo': False}

            return [dcc.Graph(id="graphSimilarDays",
                              figure=fig, config=config),
                    dcc.Graph(id="boxSimilarDays", figure=fig2, config=config),
                    dbc.Alert(
                        f"Total days: {len(similarDays.groupby('Date'))}", color="info")
                    ], {}, similarDaysData

        if resultTab == 'similarDays-tab-table':
            similarDaysGrouped = similarDays.groupby(by='Date', as_index=False)
            similarDaysTable = filtro_dias.calculateTable(similarDaysGrouped)

            rowToMove = similarDaysTable.loc[similarDaysTable['Date'] == targetDate]
            similarDaysTable = pd.concat(
                [rowToMove, similarDaysTable[similarDaysTable['Date'] != targetDate]]).reset_index(drop=True)

            if searchTab == 'tab-ponders':
                # Combinar dataframes para obtener la nota de cada día
                similarDaysTable = pd.merge(
                    similarDaysTable, bestDays, on='Date', how='left')

            return [dbc.Label(f'{searchTabSelected}: {locationLabel}',
                              class_name='label-table font-weight-bold', size=14),
                    setResultTableSimilarDays(
                        similarDaysTable, searchTab == 'tab-ponders'),
                    dbc.Alert(
                        f"Total days: {len(similarDaysGrouped)}", color="info", class_name='mt-3')
                    ], {}, similarDaysData

    return [], csvNotDisplayed, similarDaysData
