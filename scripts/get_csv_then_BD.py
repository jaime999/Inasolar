
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 30 10:39:46 2023

@author: VPASMUO
"""

import pandas as pd
import pyodbc
import datetime as dt
import numpy as np
import requests
from dotenv import dotenv_values

config = dotenv_values(".env")

url = "http://158.42.21.68:8080/"

#listamos ficheros
csvs = requests.get(url).text
now = dt.datetime.now()
ultimo_dia_mes_anterior = dt.date(now.year, now.month, 1) - dt.timedelta(days=1)
past_month_csv = ultimo_dia_mes_anterior.strftime("%Y-%m-%d") + ".std.csv"

file_to_download = csvs.split('href="')[-1].split('"')[0]

csvs_to_process = [file_to_download]

file = requests.get(url+file_to_download, allow_redirects=True)
open(f"csvs/{file_to_download}", 'wb').write(file.content)
if csvs.find(past_month_csv) > 0:
    past_month_file = requests.get(url+past_month_csv, allow_redirects=True)
    open(f"csvs/{past_month_csv}", 'wb').write(past_month_file.content)
    csvs_to_process.append(past_month_csv)

#IMPORTANTE NO EJECUTAR SIN TENER EN CUENTA EL ID DE LA LOCALIZACION

locations = [1,38]
servidor  = config["DBHost"]
puerto    = config["DBPort"]
basedatos = config["DBName"]
usuario   = config["DBUser"]
password  = config["DBPassword"]

cnxn = pyodbc.connect('DRIVER={SQL Server};SERVER=' + servidor + ';PORT=' + puerto + ';DATABASE=' + basedatos + ';UID=' + usuario + ';PWD=' + password + ';')
cursor = cnxn.cursor()

for csv in csvs_to_process:
    for location in locations:
        excel1 = pd.read_csv(f"csvs/{csv}", delimiter = ";", encoding='latin-1')
        excel = excel1.astype(object).replace(np.nan, 'NULL')#LOS NOT A NUMBER LOS REEMPLAZOMOS POR NULL
        columns = excel.columns.values
        #limpiamos el nombre de las columnas, quitamos tildes,unidades, puntos 
        #y ponemos mayúsculas la primera letra de todas las palabaras
        columns_aux = map(lambda x : x.replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u').replace('.','').replace('+','Positivo').replace("Factor cresta (I)","FactorCrestaCorriente").replace("Factor cresta (V)","FactorCrestaTension").replace("F.P. L1 -","FPL1Negativo").replace("FPL1 -","FPL1Negativo").split('(')[0].title(), columns)
        #formateamos las III, quitamos espacios, guiones y mas cosas LO SIENTO POR ESTA MONSTRUOSIDAD
        columns_aux = map(lambda x : x.replace('Iii','III').replace('Ii','II').replace('-','').replace(' ','').replace('De','').replace('/D','').replace('Thd','THD').replace('Fp','FP').replace('Con','').replace('manda','Demanda').replace('tador', 'Contador').replace('Pactiva','PActiva').replace('Pcapacitiva','PCapacitiva').replace("KaA","KaCorriente").replace("KaV","KaTension").replace("KdA","KdCorriente").replace("KdV","KdTension").replace("aparente","Aparente").replace("inductiva","Inductiva").replace("VNeutro","TensionNeutro").replace("ATHD","THDCorriente").replace("VTHD","THDTension").replace("TensionNeutroTHD","THDTensionNeutro").replace("ANeutroTHD","THDCorrienteNeutro").replace("Factorcrestatension","FactorCrestaTension").replace("Factorcrestacorriente","FactorCrestaCorriente").replace("Maximo","Max").replace("Freq","Frecuencia"),list(columns_aux))
        columns_aux = list(columns_aux)

        #cogemos el nombre de las columnas
        cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = N'datosGEDER2'") 
        cols_db = list(map(lambda x : x[0],cursor.fetchall()))[1:] #quitamos id

        #No muy eficiente pero funciona y además es raro ejecutar esto
        #Aqui comprobamos las columnas que debemos insertar, es decir, las columnas que no esten en la BD pero si en el excel no se insertan
        columns_insert_index =[]
        for j in range(len(columns)):
            if columns_aux[j] in cols_db:
                columns_insert_index.append(j)
            else:
                print(columns_aux[j])
        for i in excel.values:
            #date = parser.parse(str(i[0])) ESTO NO FUNCIONA BIEN CON ENERO
            #LO HACEMOS MANUAL PORQUE LA FECHA ES RARA. Por ejemplo: 5/01/23
            dayy = str(i[0]).split(' ')[0].split('/')
            date = dt.datetime(year=int(dayy[2])+2000, month = int(dayy[1]), day=int(dayy[0]), hour = int(str(i[0]).split(' ')[1].split(':')[0] ))

            #pillar id fecha
            query = f"SELECT id FROM DATES where date = cast('{str(date).replace(' ','T')}' as datetime)"
            cursor.execute(query)
            try:
                id_date = cursor.fetchall()[0][0]
            except:
                continue
            query = 'INSERT INTO datosGEDER2 ('
            values = ''
            repeated_columns = []
            for j in columns_insert_index:
                if columns_aux[j] not in repeated_columns:
                    query += columns_aux[j] + ', '
                    values += str(i[j]).replace(',', '.')+ " , "
                    repeated_columns.append(columns_aux[j])
                    
            query += ' date, location) VALUES ('+values+str(id_date)+','+str(location)+')'
            try:
                cursor.execute(query)
                cursor.commit()
                print(f"{i[0]} Completado")
            except Exception as e:
                query = 'Update datosGEDER2 SET '
                repeated_columns = []
                for j in columns_insert_index:
                    if columns_aux[j] not in repeated_columns:
                        query += '['+columns_aux[j] +'] = '
                        query += str(i[j]).replace(',', '.')+ " , "
                        repeated_columns.append(columns_aux[j])
                query += f'WHERE date = {id_date} AND location = {location}'
                cursor.execute(query.replace(', WHERE','WHERE'))
                cursor.commit()
                print(f"{i[0]} UPDATED")
            #print(query)
        if location == 38:    
            cursor.execute(f"update datosGEDER2 set [Power] = [PActivaIII] * 0.01 where [Power] is null and location = {location}")
        else:
            cursor.execute(f"update datosGEDER2 set [Power] = [PActivaIII] where [Power] is null and location = {location}")

        cursor.commit()
cnxn.close()
