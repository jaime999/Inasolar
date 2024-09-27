import dash_bootstrap_components as dbc
import pandas as pd
import dash_loading_spinners as dls
from .genericCode import GenericCode
from datetime import datetime
from dash import callback, Output, Input, html, dash_table, ctx, dcc

# VARIABLES
# ---------------------------------------------------------------
TYPE_OF_DAYS = {'newYear': 'New Year',
                'localHoliday': 'Local Holiday',
                'nationalHoliday': 'National Holiday',
                'festivities': 'Festivities',
                'weekEnd': 'Weekend',
                'weekDay': 'Week Day'}
HISTORICAL_WEATHER_COLUMNS_SQL = pd.read_sql(
    """SELECT nombre_dato, nombre_alternativo, unidad, defaultMargin, defaultPonder
               FROM descripcionDatos
               WHERE Tabla = 'HistoricalWeather'""", GenericCode.engine)
POWER_SQL = pd.read_sql(
    "SELECT * FROM descripcionDatos WHERE Tabla = 'datosGEDER2' AND nombre_dato = 'Power'", GenericCode.engine)

def generateCheckParameter(row, ponder, idType):
    nombreDato = row['nombre_dato']

    checkBox = dbc.Checkbox(
        id={
            'type': f'{idType}-checkbox',
            'key': nombreDato
        },
        label=f"{row['nombre_alternativo']}({row['unidad'].strip()})",
        label_style={'opacity': 1}
    )

    if nombreDato == 'direct_radiation':
        checkBox.value = True

    inputParameter = dbc.Input(id={'type': f'{idType}-input', 'key': row['nombre_dato']}, type="number",
                               value=f"{row['defaultMargin']}", min=0)
    if ponder:
        inputParameter.value = row['defaultPonder']
        inputParameter.max = 1
        inputParameter.step = 0.1
        checkBox.input_class_name = 'no-display'
        checkBox.disabled = True
        checkBox.label = row['nombre_alternativo']

    return dbc.Col(
        dbc.Row([
            dbc.Col(checkBox, width=8),
            dbc.Col(inputParameter, width=4)
        ], align="center"), width=3, class_name='pb-3'
    )


class SimilarDays:
    # FUNCIONES
    # ---------------------------------------------------------------
    def setMaxDateAllowedAndDisabledDays(location):
        # Se comprueba la fecha más alta que tiene datos de potencia, histórico meteorológico, y
        # se encuentra la última hora del día (23)
        maxDateAllowedCode = f"""SELECT max(dat.Date) Date FROM Dates dat
                                 INNER JOIN datosGEDER2 datos on datos.Date = dat.id
                                 INNER JOIN HistoricalWeather h on h.date = dat.id
                                 WHERE datos.location={location} AND Power is not NULL AND Hour = 23"""
        maxDateAllowedSql = pd.read_sql(maxDateAllowedCode, GenericCode.engine)
        maxDateAllowed = datetime.strptime(
            str(maxDateAllowedSql['Date'].iloc[0]), '%Y-%m-%d %H:%M:%S')
        daysWithPowerNullSql = pd.read_sql(
            f"""SELECT dates.[id]
              ,dates.[Date]
              FROM [Dates] dates
              LEFT JOIN datosGEDER2 datos on datos.Date=dates.id
              WHERE location={location} AND datos.Power IS NULL AND dates.Date < ({maxDateAllowedCode})
              order by dates.Date""", GenericCode.engine)
        daysWithPowerNullSql['DatesPower'] = pd.to_datetime(
            daysWithPowerNullSql['Date'], format='%d/%m/%Y %H:%M')
        daysWithPowerNull = daysWithPowerNullSql['DatesPower'].dt.strftime(
            '%Y-%m-%d').unique()

        return maxDateAllowed.date(), daysWithPowerNull

    def createRangeAndSetDays(area, rangeId):
        return GenericCode.createRange(rangeId, datetime(2019, 1, 1))

    def generateMarginsCard(resourceType='Consumer', idType='weather'):
        return dbc.ListGroupItem(html.Div([GenericCode.getHeaderOfListGroupItem(f'Margins - {resourceType}', 'historicalWeatherOpenInfo'),
                                           dbc.Row([generateCheckParameter(row, False, idType)
                                                    for index, row in HISTORICAL_WEATHER_COLUMNS_SQL.iterrows()], align='center')]))

    def generatePondersCard(resourceType='Consumer', idType='weather'):
        return dbc.ListGroupItem(html.Div([GenericCode.getHeaderOfListGroupItem(f'Ponders - {resourceType}', 'historicalWeatherOpenInfo'),
                                           dbc.Row([generateCheckParameter(row, True, idType)
                                                    for index, row in HISTORICAL_WEATHER_COLUMNS_SQL.iterrows()], align='center')]))

    def generateTypeOfDay(pageId):
        cols = []

        for key in TYPE_OF_DAYS:
            cols.append(
                dbc.Col(dbc.Checkbox(
                    id={
                        'type': f'{pageId}TypeOfDayCheckbox',
                                'key': key
                    },
                    label=TYPE_OF_DAYS[key],
                    value=key == 'weekDay'
                ), width=6)
            )

        return cols

    def getTypeOfDays(typeOfDaysValue):
        return {key: typeOfDaysValue[index]
                for index, key in enumerate(TYPE_OF_DAYS)}

    def getDatesCard(rangeRow, pageId, targetDate=None):
        rangeAndTypeDays = dbc.Row([
            dbc.Col(dbc.Row(rangeRow, align="center", justify="center"), width=5),
            dbc.Col(dbc.Row([
                dbc.Col('Num Days', width='auto',
                        class_name='no-padding-right font-weight-bold'),
                dbc.Col(
                    dbc.Input(id='num-days', type="number", value=20, min=0), width=6)
            ], align="center"), width=2),
            dbc.Col(dbc.Row([
                dbc.Col('Type of Day', width='auto',
                        class_name='font-weight-bold'),
                dbc.Col(dbc.Row(SimilarDays.generateTypeOfDay(pageId)),
                        class_name='pt-3')
            ], align='center'), width=5),
        ], className='pt-4', align='center')

        return [GenericCode.getHeaderOfListGroupItem('Dates', 'datesOpenInfo'), targetDate, rangeAndTypeDays]

    def getHeaderSearchTabs():
        return dbc.CardHeader(
            dbc.Tabs([
                dbc.Tab(label='Margins', tab_id='tab-margins'),
                dbc.Tab(label='Ponders', tab_id='tab-ponders')
            ],
                id='search-data-tabs'
            )
        )

    def setColumnsTable(columns):
        columns.insert(0, {'name': 'Date', 'id': 'Date'})

        for index, row in HISTORICAL_WEATHER_COLUMNS_SQL.iterrows():
            columns.append(
                {'name': f"{row['nombre_alternativo']}({row['unidad'].strip()})", 'id': row['nombre_dato']})

        return columns

    def getTargetDateTable(tableId, columns=[]):
        return dls.Propagate(html.Div(dash_table.DataTable(
            id=f'{tableId}-targetDate',
            columns=SimilarDays.setColumnsTable(columns),
            style_table={'overflowX': 'auto', 'min-width': '100%'},
            style_cell={'textAlign': 'left'},
            style_header={'border': '1px solid green'},
            style_data_conditional=[
                GenericCode.getColumnColor('Power', 'rgb(30, 30, 30)', 'white')
            ],
            style_header_conditional=[
                GenericCode.getColumnColor(
                    'Power', 'rgb(30, 30, 30)', 'white'),
                GenericCode.getColumnColor(
                    'Date', 'rgb(255, 142, 142)', 'black')
            ],
            fixed_columns={'headers': True, 'data': 1}
        ),), color='#b3c2d6', debounce=100)

    def disableButton(inputsValue, inputsDisabled):
        if any(type(num) == type(None) or float(num) < 0 for num in inputsValue):
            return True

        # Se comprueba si hay algún parámetro meteorológico seleccionado, en caso negativo se deshabilita la búsqueda
        return all(inputsDisabled)

    def getMargins(consumerInputsId, consumerInputsValue, consumerInputsDisabled):
        return {inputID['key']: inputValue for inputID, inputValue, inputDisabled in zip(
            consumerInputsId, consumerInputsValue, consumerInputsDisabled) if inputValue is not None and not inputDisabled}

    def generateQuantiles(labelName, inputId, defaultValue):
        return dbc.Row([
            dbc.Col(
                dbc.Row([labelName], justify='end'), width=7),
            dbc.Col(
                dbc.Input(id=inputId, type='number',
                          value=defaultValue, min=0, max=100, step=1),
                width=5, className='quantiles'
            )
        ], class_name='pb-3', align='center')

    # HTML
    # ---------------------------------------------------------------

    # CALLBACKS
    # ---------------------------------------------------------------

    @callback(
        Output('search-tabs-content', 'children'),
        Output('num-days', 'disabled'),
        Input('search-data-tabs', 'active_tab')
    )
    def changeSearchData(activeTab):
        if activeTab == 'tab-margins':
            return SimilarDays.generateMarginsCard(), True

        else:
            return SimilarDays.generatePondersCard(), False

    # Se crea un callback por cada parámetro para activar y desactivar el input
    def updateInput(checkBoxValue, activeTab):
        if activeTab == 'tab-margins':
            return not checkBoxValue

    for index, row in HISTORICAL_WEATHER_COLUMNS_SQL.iterrows():
        callback(
            Output({'type': 'weather-input',
                   'key': row['nombre_dato']}, 'disabled'),
            Input({'type': 'weather-checkbox',
                  'key': row['nombre_dato']}, 'value'),
            Input('search-data-tabs', 'active_tab')
        )(updateInput)

    @callback(
        Output('similarDaysCardInfo', 'is_open'),
        Output('similarDaysInfoBody', 'children'),
        Input('datesOpenInfo', 'n_clicks'),
        Input('historicalWeatherOpenInfo', 'n_clicks'),
        Input('similarDaysCloseCardInfo', 'n_clicks'),
        Input('search-data-tabs', 'active_tab'),
        prevent_initial_call=True
    )
    def opensimilarDaysCardInfoModal(datesOpenInfo, historicalWeatherOpenInfo, similarDaysCloseCardInfo, activeTab):
        if ctx.triggered_id == 'datesOpenInfo' and datesOpenInfo:
            listInfo = dcc.Markdown('''
                                    * **Target date** is the reference day to search for similar days
                                    * If **power** is positive, resource is consumer, if **power** is negative, resource is producer
                                    * In the **range** date picker you can select the **range** where the search is going to be performed
                                    * If **Past Days** is selected, search will be performed in dates before **target date**
                                    * If **Ponders** is selected, **Num Days** represents the days with the best score
                                      that are going to be showed
                                    * You can select the **type of days** you want to search
                                    ''')
            return True, listInfo

        if ctx.triggered_id == 'historicalWeatherOpenInfo' and historicalWeatherOpenInfo:
            listInfo = None
            if activeTab == 'tab-margins':
                listInfo = dcc.Markdown('''
                                        * If a parameter is disabled, the value from that parameter is not **taken into consideration**
                                        * When a parameter is selected, the search is performed searching for the days **plus and minus**
                                          the value selected for that parameter, taking **target date** as reference
                                        * The parameters used in the search are the **mean** for each day
                                        ''')

            if activeTab == 'tab-ponders':
                listInfo = dcc.Markdown('''
                                        * Each parameter is the **weight** given to that weather parameter in the comparison
                                        * The app calculate the difference between each day inside the **range** and the **target day**,
                                          giving to each day a **score**, being 100 the most similar day, and 0 the most different
                                        * The result returned is the number of days specified in the **Num Days**
                                          parameter with the **best score**
                                        ''')
            return True, listInfo

        return False, ''
