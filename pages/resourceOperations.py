from .genericCode import GenericCode
import requests
import json
import pandas as pd
from sqlalchemy import text


class ResourceOperations:
    def createResource(locationName, areaName, latitude, longitude, startDate, endDate, demandFile):
        # Se crea una conexión con el engine para iniciar una transacción
        conn = GenericCode.engine.connect()
        trans = conn.begin()
        try:
            areaId = ResourceOperations.createArea(
                conn, areaName, latitude, longitude)
            locationConsumer, locationGenerator = ResourceOperations.createLocations(
                conn, locationName, latitude, longitude, areaId)
            locationConsumerId = locationConsumer.fetchone()[0]
            locationGeneratorId = locationGenerator.fetchone()[0]
            # Se añade el histórico meteorológico asociado al area
            dates, historicalWeatherDf = ResourceOperations.setHistoricalWeatherByArea(
                conn, latitude, longitude, startDate, endDate, areaId)
            demandFile = pd.merge(
                demandFile, dates, on='Date', how='inner')
            demandFile = demandFile.drop('Date', axis=1)
            demandFile = demandFile.rename(columns={'id': 'date'})
            ResourceOperations.addAreaHolidays(
                conn, areaId, locationConsumerId, startDate, endDate, demandFile)
            ResourceOperations.addResourceDemand(
                conn, demandFile['Power'], demandFile['date'], locationConsumerId)
            ResourceOperations.addResourceGeneration(
                conn, historicalWeatherDf, locationGeneratorId)
            # Se confirma la transacción
            trans.commit()

            return locationGeneratorId

        except Exception as e:
            trans.rollback()

            raise Exception(f'There was a problem creating the resource: {e}')
            # En caso de fallo, se cancela la transacción

        finally:
            # Por último se cierra la conexión para que se libere la BBDD
            conn.close()

    def modifyResource(locationId, locationName, installedPower, dates,
                       lastStartDate, lastEndDate, demandFile, resourceInfo):
        # Se crea una conexión con el engine para iniciar una transacción
        conn = GenericCode.engine.connect()
        trans = conn.begin()
        try:
            ResourceOperations.updateResourceSelected(
                conn, locationId, locationName, installedPower)
            if demandFile is not None:
                areaId = resourceInfo['Area']
                demandStartDate = dates.min()
                demandEndDate = dates.max()
                # Si el fichero de demandas tiene fechas que no se encontraban antes en el recurso,
                # se añade la meteorología
                if (demandStartDate < lastStartDate) or (demandEndDate > lastEndDate):
                    sqlDates = ResourceOperations.modifyLocationWeatherArea(
                        conn, locationId, areaId, demandStartDate, demandEndDate)
                    # Se recuperan las ids de las fechas del fichero, y se renombra con el nombre de la columna que se encuentra en BBDD
                    demandFile = ResourceOperations.processDemandFile(
                        demandFile, sqlDates)
                    ResourceOperations.modifyAreaHolidays(
                        conn, demandFile, areaId, locationId, demandStartDate, demandEndDate)

                else:
                    sqlDates = pd.read_sql(f"""SELECT *
                                                  FROM Dates 
                                                  WHERE Date >= CONVERT(DATETIME, '{demandStartDate}', 102)
                                                  AND Date <= CONVERT(DATETIME, '{demandEndDate} 23:00:00', 102)""",
                                           GenericCode.engine)
                    demandFile = ResourceOperations.processDemandFile(
                        demandFile, sqlDates)

                ResourceOperations.modifyResourcePower(conn, locationId, demandStartDate,
                                                       demandEndDate, demandFile[['date', 'Power']])

            # Si es recurso generador, se comprueba que se está cambiando la potencia instalada, para escalar la generación
            elif resourceInfo['Type'] == 'Generator' and resourceInfo['InstalledPower'] != installedPower:
                ResourceOperations.changeInstalledPower(conn, installedPower, resourceInfo['InstalledPower'], locationId)

            # Se confirma la transacción
            trans.commit()

        except Exception as e:
            raise Exception(f'There was a problem modifying the resource: {e}')
            # En caso de fallo, se cancela la transacción
            trans.rollback()

        finally:
            # Por último se cierra la conexión para que se libere la BBDD
            conn.close()

    def changeInstalledPower(conn, newInstalledPower, oldInstalledPower, locationId):
        ratio = newInstalledPower / oldInstalledPower
        datosGederTable = 'datosGEDER2'
        resourceDemand = pd.read_sql(f"""SELECT Power, date
                                FROM {datosGederTable}
                                WHERE location = {locationId}""", GenericCode.engine)
        resourceDemand['Power'] = resourceDemand['Power'] * ratio
        tempTable = '#temp_table'
        resourceDemand.to_sql(
            tempTable, conn, if_exists='replace', index=False)
        conn.execute(text(f"""UPDATE {datosGederTable}
                                SET Power = temp.Power
                                FROM {tempTable} temp
                                WHERE location = {locationId} AND {datosGederTable}.date = temp.date
                                """))
        conn.execute(text(f"DROP TABLE {tempTable}"))
                                                                
    def processDemandFile(demandFile, sqlDates):
        demandFile = pd.merge(
            demandFile, sqlDates, on='Date', how='left')
        demandFile = demandFile.drop('Date', axis=1)

        return demandFile.rename(columns={'id': 'date'})

    def modifyLocationWeatherArea(conn, locationId, areaId, startDate, endDate):
        areaInfo = pd.read_sql(f"""SELECT Latitude, Longitude
                                FROM Area
                                WHERE id = {areaId}""",
                               GenericCode.engine).iloc[0]

        weatherArea = pd.read_sql(f"""SELECT date
                                FROM HistoricalWeather
                                WHERE Area = {areaId}""",
                                  GenericCode.engine)

        sqlDates, historicalWeatherDf = ResourceOperations.getHistoricalWeatherByArea(conn, areaInfo['Latitude'], areaInfo['Longitude'],
                                                                                      startDate, endDate, areaId)

        # Se insertan los valores meteorológicos que no se encontraban antes
        historicalWeatherDf = historicalWeatherDf[~historicalWeatherDf['date'].isin(
            weatherArea['date'])]
        historicalWeatherDf.to_sql(
            'HistoricalWeather', con=conn, if_exists='append', index=False)

        return sqlDates

    def updateResourceSelected(conn, locationId, locationName, installedPower):
        conn.execute(text("""UPDATE Locations
                            SET Name = :name, InstalledPower = :installedPower 
                            OUTPUT inserted.Area
                            WHERE id = :locationId"""),
                     parameters={'name': locationName,
                                 'installedPower': installedPower,
                                 'locationId': locationId})

    def modifyAreaHolidays(conn, demandFile, areaId, locationId, startDate, endDate):
        holidaysTable = 'Holidays'
        tempTable = '#temp_table_holidays'
        holidaysDates = pd.read_sql(f"""SELECT date FROM Holidays WHERE Area = {areaId}""",
                                    GenericCode.engine)
        holidaysToInsert = demandFile[~demandFile['date'].isin(
            holidaysDates['date'])]

        if 'Festivities' in holidaysToInsert:
            holidaysToUpdate = demandFile[demandFile['date'].isin(
                holidaysDates['date'])][['date', 'Festivities']]
            holidaysToUpdate.to_sql(
                tempTable, conn, if_exists='replace', index=False)
            conn.execute(text(f"""UPDATE {holidaysTable}
                                SET festivities = temp.Festivities
                                FROM {tempTable} temp
                                WHERE Area = {areaId} AND Holidays.date = temp.date
                                """))
            conn.execute(text(f"DROP TABLE {tempTable}"))

        ResourceOperations.addAreaHolidays(
            conn, areaId, locationId, startDate, endDate, holidaysToInsert)

    def addAreaHolidays(conn, areaId, locationId, startDate, endDate, excelFile):
        festivitiesLabel = 'Festivities'
        # Si la columna Festivities existe pero no tiene ningun valor, se elimina para rellenarla
        if festivitiesLabel in excelFile and excelFile[festivitiesLabel].isna().all():
            excelFile = excelFile.drop(festivitiesLabel, axis=1)

        if not festivitiesLabel in excelFile:
            # En caso de que no se hayan indicado los días festivos, se usan los de Aras
            sqlHolidays = pd.read_sql(f"""SELECT festivities AS {festivitiesLabel}, h.date
                                      FROM Holidays h
                                      INNER JOIN Dates d ON d.id = h.date
                                      WHERE d.Date >= CONVERT(DATETIME, '{startDate}', 102) AND d.Date <= CONVERT(DATETIME, '{endDate} 23:00:00', 102)
                                      AND Area = 1""",
                                      GenericCode.engine)
            excelFile = pd.merge(
                excelFile, sqlHolidays, on='date', how='inner')

        areaHolidays = pd.DataFrame(
            {'date': excelFile['date'], 'location': locationId, 'Area': areaId,
             'weekEnd': excelFile['DayOfWeek'] > 5, 'weekDay': excelFile['DayOfWeek'] <= 5,
             'newYear': ((excelFile['Month'] == 1) & (excelFile['Day'] == 1)), 'festivities': excelFile[festivitiesLabel]})
        areaHolidays.to_sql(
            'Holidays', con=conn, if_exists='append', index=False)

    def modifyResourcePower(conn, locationId, startDate, endDate, demandFile):
        datosGeder = 'datosGEDER2'
        powerDates = pd.read_sql(f"""SELECT ged.date
                                    FROM {datosGeder} ged
                                    INNER JOIN Dates dat ON dat.id = ged.date 
                                    WHERE location = {locationId}
                                    AND dat.Date >= CONVERT(DATETIME, '{startDate}', 102) AND dat.Date <= CONVERT(DATETIME, '{endDate} 23:00:00', 102)""",
                                 GenericCode.engine)

        # Las filas que tienen que ser actualizadas se añaden a una tabla temporal, para luego
        # actualizar la tabla desde allí
        powerDatesToUpdate = demandFile[demandFile['date'].isin(
            powerDates['date'])]
        tempTable = '#temp_table_power'
        powerDatesToUpdate.to_sql(
            tempTable, conn, if_exists='replace', index=False)
        conn.execute(text(f"""UPDATE {datosGeder}
                            SET Power = temp.Power
                            FROM {tempTable} temp
                            WHERE location = {locationId} AND datosGEDER2.date = temp.date
                            """))
        conn.execute(text(f"DROP TABLE {tempTable}"))

        demandFile.loc[:, 'location'] = locationId
        powerDatesToInsert = demandFile[~demandFile['date'].isin(
            powerDates['date'])]
        powerDatesToInsert.to_sql(
            datosGeder, conn, if_exists='append', index=False)

    def addResourceDemand(conn, resourcePower, resourceDatesId, locationId):
        resourcePowerDates = pd.DataFrame(
            {'date': resourceDatesId, 'Power': resourcePower, 'location': locationId})
        resourcePowerDates.to_sql(
            'datosGEDER2', con=conn, if_exists='append', index=False)

    def addResourceGeneration(conn, historicalWeatherDf, locationId):
        # Se hace el cálculo de la energía generada teniendo en cuenta la radiación
        genPower = historicalWeatherDf['direct_radiation'].apply(
            lambda x: -1 * min(x * 0.02515457, 20))
        # El ID de la fecha ya viene en la columna "date" al ser añadida en la tabla HistoricalWeather
        resourceGeneration = pd.DataFrame(
            {'date': historicalWeatherDf['date'], 'Power': genPower, 'location': locationId})
        resourceGeneration.to_sql(
            'datosGEDER2', con=conn, if_exists='append', index=False)

    def createArea(conn, name, latitude, longitude):
        # Se crea el nuevo area, y se recupera la ID que se ha asignado
        result = conn.execute(text("INSERT INTO Area (Name, Latitude, Longitude) OUTPUT inserted.id VALUES (:name, :latitude, :longitude)"),
                              parameters={'name': name,
                                          'latitude': latitude,
                                          'longitude': longitude})
        return result.fetchone()[0]

    def createLocations(conn, locationName, latitude, longitude, areaId):
        locationConsumer = conn.execute(text("INSERT INTO Locations (Name, Latitude, Longitude, Type, Area) OUTPUT inserted.id VALUES (:name, :latitude, :longitude, 'Consumer', :areaId)"),
                                        parameters={'name': locationName,
                                                    'latitude': latitude,
                                                    'longitude': longitude,
                                                    'areaId': areaId})

        locationGenerator = conn.execute(text("INSERT INTO Locations (Name, Latitude, Longitude, Type, Area, ResourceType, InstalledPower) OUTPUT inserted.id VALUES (:name, :latitude, :longitude, 'Generator', :areaId, 'photovoltaic', 20)"),
                                         parameters={'name': f'PV_{locationName}',
                                                     'latitude': latitude,
                                                     'longitude': longitude,
                                                     'areaId': areaId})

        return locationConsumer, locationGenerator

    def getHistoricalWeatherByArea(conn, latitude, longitude, startDate, endDate, areaId):
        url = f"https://archive-api.open-meteo.com/v1/era5?latitude={latitude}&longitude={longitude}&start_date={startDate}&end_date={endDate}&hourly=temperature_2m,relativehumidity_2m,surface_pressure,precipitation,snowfall,cloudcover,direct_radiation,windspeed_10m,winddirection_10m&timezone=auto"

        response = requests.get(url)
        data = json.loads(response.text)
        dates = data["hourly"]["time"]
        sqlDates = pd.read_sql(f"""SELECT *
                                  FROM Dates 
                                  WHERE Date >= CONVERT(DATETIME, '{startDate}', 102) AND Date <= CONVERT(DATETIME, '{endDate} 23:00:00', 102)""",
                               GenericCode.engine)
        hourWeatherList = []
        for i in range(0, len(dates)):
            hourWeatherDict = {}
            for key in list(data["hourly_units"].keys())[1:]:
                hourWeatherDict[key] = data["hourly"][key][i]

            dateSelected = sqlDates[sqlDates['Date'] == dates[i]]
            hourWeatherDict['date'] = dateSelected['id'].iloc[0]
            hourWeatherDict['Area'] = areaId
            hourWeatherList.append(hourWeatherDict)

        return sqlDates, pd.DataFrame(hourWeatherList)

    def setHistoricalWeatherByArea(conn, latitude, longitude, startDate, endDate, areaId):
        sqlDates, historicalWeatherDf = ResourceOperations.getHistoricalWeatherByArea(
            conn, latitude, longitude, startDate, endDate, areaId)
        historicalWeatherDf.to_sql(
            'HistoricalWeather', con=conn, if_exists='append', index=False)

        return sqlDates, historicalWeatherDf
