import requests
import json
import pyodbc
import datetime as dt
from dotenv import dotenv_values

config = dotenv_values(".env")

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
        cursor.execute("SELECT id FROM Dates WHERE Date = CONVERT(DATETIME, '"+key+"', 126)")
        id_date = str(cursor.fetchone()[0])
        query = f'INSERT INTO ElectricityPrice(surplus_price, date, Area) VALUES ({precios[key]},{id_date},1)'
        try:
            cursor.execute(query)
        except:
            query = f'UPDATE ElectricityPrice set surplus_price = {precios[key]} where date = {id_date} and Area = 1'
            cursor.execute(query)
        cursor.commit()
        print(f"Precio actualizado: {precios[key]} , {key}")
    cnxn.close()
try:
    #esto es necesario para que funcione la request
    header = {"X-Api-Key": "request_your_personal_token_sending_email_to_consultasios@ree.es", "Accept": "application/json; application/vnd.esios-api-v1+json",
              "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"}

    fecha_ini = dt.datetime.now() - dt.timedelta(days=14)
    fecha_fin = dt.datetime.now() 

    precios = {}

    while fecha_ini < fecha_fin:
        fecha_aux = fecha_ini + dt.timedelta(days=15)
        url = "https://api.esios.ree.es/indicators/1739?start_date="+fecha_ini.strftime("%Y-%m-%dT%H:%M")+"&end_date="+fecha_aux.strftime("%Y-%m-%dT%H:%M")+"&geo_ids=&geo_agg=sum&time_trunc=hour&locale=es"
        datos = json.loads(requests.get(url, headers=header).text)
        for dato in datos["indicator"]["values"]:
            #precios[fecha.strftime("%Y-%m-%d %H:%M")] = datos['value'] 
            fecha_parseada = dt.datetime.strptime(dato["datetime"].split(".")[0], "%Y-%m-%dT%H:%M:%S")  
            precios[fecha_parseada.strftime("%Y-%m-%dT%H:%M:%S")] = dato["value"]   
        fecha_ini = fecha_aux
        
    print(precios)
    insert_all_db(precios)
    log = open("./logs/ElectricityPrices.txt","a")
    log.write(f"{fecha_fin.strftime('%Y-%m-%d')}: Precios de excedente actualizados correctamente\n")
    log.close()
except Exception as e:
    log = open("./logs/ElectricityPrices.txt","a")
    log.write(f"{fecha_fin.strftime('%Y-%m-%d')}: Error al actualizar precios exdente: {e}\n")
    log.close()   
