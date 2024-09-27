import pandas as pd
from .genericCode import GenericCode

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

class ResourceAllocation:
    # FUNCIONES
    # ---------------------------------------------------------------

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


    def exportSimulation(simulationData, parametersData, fileName, rangeDates, location):
        excelColumns = [column["id"]
                        for column in ResourceAllocation.COLUMNS_SIMULATION]
        resourceAllocationDataDf = GenericCode.readJSON(simulationData)

        return ResourceAllocation.exportToExcel(parametersData, [{'SheetName': 'Simulation', 'Data': resourceAllocationDataDf[excelColumns]}],
                                                f'{fileName}.xlsx', rangeDates, location)



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
            if(row['GraphLabel'] != None):
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


    def setColumnsTable(allocationParameters, columns=[]):
        for index, row in allocationParameters.iterrows():
            columns.append(
                {'name': f'{row["Name"]}({row["Unity"].strip()})', 'id': row['IdParameter'],
                 'type': row['Type']})

        return columns

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

    # VARIABLES
    # ---------------------------------------------------------------
    COLUMNS_SUMMARY = setColumnsSummary(False)
    COLUMNS_OPTIMIZATION = setColumnsSummary(True)
    COLUMNS_SIMULATION = setColumnsTable(
        ALLOCATION_PARAMETERS_RENEWABLES_RESULT_SQL, [{'name': 'Date', 'id': 'Date'}])

    GRAPH_DATA = ALLOCATION_PARAMETERS_RENEWABLES_RESULT_SQL.dropna(
        subset=['GraphType']).sort_values(by='GraphOrder')
    COSTS_DATA = GRAPH_DATA[GRAPH_DATA['GraphType'].str.endswith('3')]
    SUNBURST_DATA = pd.read_sql(
        "SELECT * FROM AllocationParameters WHERE GraphType = 'Sunburst'", GenericCode.engine)
    COLUMNS_COSTS = setColumnsTable(COSTS_DATA)
