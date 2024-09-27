# -*- coding: utf-8 -*-
"""
Created on Wed Dec 28 11:41:02 2022

@author: Victor
"""

import requests
import json
import pyodbc
import datetime as dt
from dotenv import dotenv_values

config = dotenv_values(".env")


servidor  = config["DBHost"]
puerto    = config["DBPort"]
basedatos = config["DBName"]
usuario   = config["DBUser"]
password  = config["DBPassword"]

cnxn = pyodbc.connect('DRIVER={SQL Server};SERVER=' + servidor + ';PORT=' + puerto + ';DATABASE=' + basedatos + ';UID=' + usuario + ';PWD=' + password + ';')
cursor = cnxn.cursor()

#HISTORICO UNA SEMANA DE RETRASO
now = dt.datetime.now() - dt.timedelta(days=7)
month_ago = now - dt.timedelta(days=45)

query = "SELECT id, Latitude, Longitude, Name FROM Area"
cursor.execute(query)
areas = cursor.fetchall()
file = open("./logs/HistoricalWeather.log", "a")
for area in areas:
    #ID LOCALIZACION
    location  = area[0]
    #ESTA URL PARA EL HISTORICO
    url = f"https://archive-api.open-meteo.com/v1/era5?latitude={area[1]}&longitude={area[2]}&start_date={month_ago.strftime('%Y-%m-%d')}&end_date={now.strftime('%Y-%m-%d')}&hourly=temperature_2m,relativehumidity_2m,surface_pressure,precipitation,snowfall,cloudcover,direct_radiation,windspeed_10m,winddirection_10m&timezone=auto"
    print(url)
    #ESTA URL PARA PREDICCIONES
    #url = f"https://api.open-meteo.com/v1/forecast?latitude=39.92&longitude=-1.13&hourly=temperature_2m,relativehumidity_2m,precipitation,snowfall,surface_pressure,cloudcover,windspeed_10m,winddirection_10m,direct_radiation&timezone=auto&start_date={month_ago.strftime('%Y-%m-%d')}&end_date={now.strftime('%Y-%m-%d')}"
    response = requests.get(url)
    data = json.loads(response.text)
    
    dates = data["hourly"]["time"]
    for i in range(0, len(dates)):
        query = "INSERT INTO HistoricalWeather ("+",".join(list(data["hourly_units"].keys())[1:])+",Area,date) VALUES("
        updates = []
        for key in list(data["hourly_units"].keys())[1:]:
            query += str(data["hourly"][key][i])+","
            cursor.execute("SELECT id FROM Dates WHERE Date = CONVERT(DATETIME, '"+dates[i]+":00', 126)")
            updates.append(f"Update HistoricalWeather set [{key}] = {str(data['hourly'][key][i])} where date =  ")
        try:
            id_date = str(cursor.fetchone()[0])
        except:
            file.write(f"{area[3]} ERROR ENCONTRAR FECHA: dates[i]\n")
            print("No se encuentra la fecha")
            continue
        #CAMBIAR EL UNO PARA OTRA LOCALIZACION DISTINTA
        query += f"{location},{id_date})"
        #si el insert falla quiere decir que habrá llave duplicada, hacemos update
        try:
            cursor.execute(query)
            cursor.commit()
        except:
            
            for update in updates:
                #cambiar localizacion tambien aqui
                update += f"{id_date} AND Area = {location}"
                print(update,data["hourly"]["direct_radiation"][i])
                cursor.execute(update)
                cursor.commit()
        print(f"fecha actualizada: {dates[i]}") 

    file.write(f"ACTUALIZACIÓN({dt.datetime.now()}): {area[3]},{month_ago} a {now}\n")
file.close()

cnxn.close()

