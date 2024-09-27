# -*- coding: utf-8 -*-
"""
Created on Fri Dec 16 12:20:50 2022

@author: VPASMUO
https://www.esios.ree.es/es/mercados-y-precios?date=17-12-2022
"""
import dateutil.parser
import datetime as dt
import json
import requests
import pyodbc
from dotenv import dotenv_values

config = dotenv_values(".env")


def escribir_todo_en_csv(datos, nombre_archivo, columnas, delimitador):
    csv = open(nombre_archivo, "w")
    cabecera = ''
    for nombre_columna in columnas:
        cabecera += nombre_columna +delimitador
    csv.write(cabecera+"\n")
    for key in datos.keys():
        linea = key+delimitador+str(datos[key])
        csv.write(linea+'\n')
    csv.close()
    
def insert_all_db(precios):
    global config
    servidor  = config["DBHost"]
    puerto    = config["DBPort"]
    basedatos = config["DBName"]
    usuario   = config["DBUser"]
    password  = config["DBPassword"]
    
    cnxn = pyodbc.connect('DRIVER={SQL Server};SERVER=' + servidor + ';PORT=' + puerto + ';DATABASE=' + basedatos + ';UID=' + usuario + ';PWD=' + password + ';')
    cursor = cnxn.cursor()
    for key in precios.keys():
        cursor.execute("SELECT id FROM Dates WHERE Date = CONVERT(DATETIME, '"+key.replace(' ','T')+":00', 126)")
        id_date = str(cursor.fetchone()[0])
        query = f'INSERT INTO ElectricityPrice(price, date, Area) VALUES ({precios[key]},{id_date},1)'
        try:
            cursor.execute(query)
        except:
            query = f'UPDATE ElectricityPrice set price = {precios[key]} where date = {id_date}'
            cursor.execute(query)
        cursor.commit()
        print(f"Precio actualizado: {precios[key]} , {key}")
    cnxn.close()
try:
    #AÑO MINIMO 2014
    #FECHAS PARA EL SCRIPT DIARIO CAMBIAR PARA EL HISTORICO
    fecha_ini = dt.datetime.now() - dt.timedelta(days=7)
    #fecha_ini = (dt.datetime().today()) - dt.timedelta(days=7)
    fecha_fin = dt.datetime.now() + dt.timedelta(days=1)
    #formato fecha api
    #print(fecha_ini.strftime("%Y-%m-%dT%H:%M"))

    precios = {}
    while fecha_ini < fecha_fin:
        #LA SOLICITUD API SOLO PERMITE ALREDEDOR DE 700 HORAS POR LO QUE LO HACEMOS DE 15 EN 15 DIAS
        fecha_aux = fecha_ini + dt.timedelta(days=15)
        #DOCUMENTACION API EN https://www.ree.es/es/apidatos
        url = "https://apidatos.ree.es/es/datos/mercados/precios-mercados-tiempo-real?start_date="+fecha_ini.strftime("%Y-%m-%dT%H:%M")+"&end_date="+fecha_aux.strftime("%Y-%m-%dT%H:%M")+"&time_trunc=hour"
        #HAY 2 PRECIOS PVPC Y MERCADO SPOT, COGEMOS SPOT
        datos = json.loads(requests.get(url).text)
        
        #TRY NECESARIO, A PARTIR DEL 06/2021 SE AÑADE PVPC
        try:
            datos_mercados_spot = datos['included'][1]['attributes']['values']
        except:
             datos_mercados_spot = datos['included'][0]['attributes']['values']
        
        for datos in datos_mercados_spot:
            fecha = dateutil.parser.isoparse(datos['datetime'])
            precios[fecha.strftime("%Y-%m-%d %H:%M")] = datos['value'] 

        #print(precios)
        fecha_ini = fecha_aux
    #escribir_todo_en_csv(precios, "historico-precios.csv", ['fecha','precio(euros/MWh)'], ';')  
    insert_all_db(precios)
    log = open("./logs/ElectricityPrices.txt","a")
    log.write(f"{fecha_fin.strftime('%Y-%m-%d')}: Precios de consumo actualizados correctamente\n")
    log.close()
except Exception as e:
    log = open("./logs/ElectricityPrices.txt","a")
    log.write(f"{fecha_fin.strftime('%Y-%m-%d')}: Error al actualizar precios de consumo: {e}\n")
    log.close()
    
