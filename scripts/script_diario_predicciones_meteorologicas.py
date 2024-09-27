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


now = dt.datetime.now() + dt.timedelta(days=3)
month_ago = now - dt.timedelta(days=31)

query = "SELECT id, Latitude, Longitude, Name FROM Area"
cursor.execute(query)
areas = cursor.fetchall()
file = open("./logs/ForecastWeather.log", "a")

for area in areas:

    #ID LOCALIZACION
    location  = area[0]

    #url = "https://archive-api.open-meteo.com/v1/era5?latitude=39.92&longitude=-1.13&start_date=2020-09-05&end_date=2022-12-20&hourly=temperature_2m,relativehumidity_2m,surface_pressure,precipitation,snowfall,cloudcover,direct_radiation,windspeed_10m,winddirection_10m&timezone=auto"
    url = f"https://api.open-meteo.com/v1/forecast?latitude={area[1]}&longitude={area[2]}&hourly=temperature_2m,relativehumidity_2m,precipitation,snowfall,surface_pressure,cloudcover,windspeed_10m,winddirection_10m,direct_radiation&timezone=auto&start_date={month_ago.strftime('%Y-%m-%d')}&end_date={now.strftime('%Y-%m-%d')}"
    response = requests.get(url)
    data = json.loads(response.text)
    
    dates = data["hourly"]["time"]
    for i in range(0, len(dates)):
        query = "INSERT INTO ForecastWeather ("+",".join(list(data["hourly_units"].keys())[1:])+",Area,date) VALUES("
        updates = []
        for key in list(data["hourly_units"].keys())[1:]:
            query += str(data["hourly"][key][i])+","
            cursor.execute("SELECT id FROM Dates WHERE Date = CONVERT(DATETIME, '"+dates[i]+":00', 126)")
            #si no hay datos de la hora
            if data['hourly'][key][i] is None:
                continue
    
            updates.append(f"Update ForecastWeather set [{key}] = {str(data['hourly'][key][i])} where date =  ")
        try:
            id_date = str(cursor.fetchone()[0])
        except:
            file.write(f"{area[3]} ERROR ENCONTRAR FECHA: dates[i]\n")
            print("No se encuentra la fecha")
            continue
        #CAMBIAR EL UNO PARA OTRA LOCALIZACION DISTINTA
        query += f"{location},"+id_date+")"
        #si el insert falla quiere decir que habrá llave duplicada, hacemos update
        try:
            cursor.execute(query)
            cursor.commit()
        except Exception as e:
            #print(e)
            for update in updates:
                update += id_date
                print(update, url)
                try:
                    #A veces hay errores en los datos y hay direct radiations de +100000
                    #https://api.open-meteo.com/v1/forecast?latitude=39.91999816894531&longitude=-1.1299999952316284&hourly=temperature_2m,relativehumidity_2m,precipitation,snowfall,surface_pressure,cloudcover,windspeed_10m,winddirection_10m,direct_radiation&timezone=auto&start_date=2023-05-10&end_date=2023-06-10
                    cursor.execute(update)
                except:
                    continue
                cursor.commit()
        print(f"fecha actualizada: {dates[i]}") 
    file.write(f"ACTUALIZACIÓN: {area[3]} actualizada desde {month_ago} a {now}\n")
file.close()

cnxn.close()

