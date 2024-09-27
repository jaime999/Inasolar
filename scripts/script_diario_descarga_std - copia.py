import requests
import datetime as dt
import sys
import os


url = "http://88.28.221.196:8005"
now = dt.datetime.now()
file = open("logs/std.log","a")

try:
    request = requests.get(url, timeout=15)
except Exception as e:
    file.write(f"{now.strftime('%Y-%m-%d')}: ERROR, web no disponible\n")
    file.close()
    sys.exit(0)
    
if request.status_code < 300:
    #hay que comprobar si el mes anterior esta completo.
    #Porque la web puede dejar de funcionar el dia 28 y volver a funcionar el dia 3 y no tendriamos el mes anterior
    ultimo_dia_mes_anterior = dt.date(now.year, now.month, 1) - dt.timedelta(days=1)

    # Convertir la fecha a un formato de cadena de caracteres que coincida con el formato de los nombres de los archivos en la lista.
    nombre_archivo = ultimo_dia_mes_anterior.strftime("%Y-%m-%d") + ".STD"

    # Buscar si hay un archivo en la lista que coincide con la cadena de caracteres generada en el paso anterior.
    if nombre_archivo not in os.listdir("stds/"):
        url = f"http://88.28.221.196:8005/{ultimo_dia_mes_anterior.year}/M_{ultimo_dia_mes_anterior.strftime('%m')}/DATA/{ultimo_dia_mes_anterior.strftime('%Y-M%m')}.STD"
        print("Descargando mes anterior...")
        request = requests.get(url, allow_redirects=True)
        print("Descarganda completada")
        open(f"stds/{now.strftime('%Y-%m-%d')}.STD", 'wb').write(request.content)
        
    url = f"http://88.28.221.196:8005/{now.year}/M_{now.strftime('%m')}/DATA/{now.strftime('%Y-M%m')}.STD"
    print("Descargando...")
    request = requests.get(url, allow_redirects=True)
    print("Descarganda completada")
    open(f"stds/{now.strftime('%Y-%m-%d')}.STD", 'wb').write(request.content)
    file.write(f"{now.strftime('%Y-%m-%d')}: {now.strftime('%Y-M%m')}.STD Descargado correctamente\n")
else:
    file.write(f"{now.strftime('%Y-%m-%d')}: ERROR, web no disponible\n")

file.close()
