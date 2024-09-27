# -*- coding: utf-8 -*-
"""
Created on Mon Feb  6 09:44:27 2023

@author: VPASMUO
"""

import pyodbc

servidor="158.42.22.107"
puerto="1433"
basedatos="inasolar"
usuario="GEDER"
password="GEDER"

cnxn = pyodbc.connect('DRIVER={SQL Server};SERVER=' + servidor + ';PORT=' + puerto + ';DATABASE=' + basedatos + ';UID=' + usuario + ';PWD=' + password + ';')
cnxn.autocommit = True
cursor = cnxn.cursor()
cursor.execute("BACKUP DATABASE [inasolar] TO  DISK = N'C:\Program Files\Microsoft SQL Server\MSSQL15.MSSQLSERVER\MSSQL\Backup\inasolar.bak' WITH  RETAINDAYS = 30, NOFORMAT, NOINIT,  NAME = N'inasolar-Full Database Backup', SKIP, NOREWIND, NOUNLOAD, COMPRESSION,  STATS = 10")

