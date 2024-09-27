from fastapi import HTTPException, status
import dotenv
import re
import inspect
from pandas import DataFrame
from simulations.resourceAllocationGeneric import ResourceAllocation
import numpy as np
import datetime as dt
from pydantic import BaseModel

#Formato para las graficas
class chartData(BaseModel):
    data: list[dict]
    category: list

#Formato para las tablas
class tableData(BaseModel):
    data: list
    category : list

#Formato de unit commitment
class UnitCommitmentData(BaseModel):
    Table: tableData
    WithRegulationGraph: chartData
    WithoutRegulationGraph: chartData
    Summary: list[dict]
    WithRegulationSunburst: list[dict]
    WithoutRegulationSunburst: list[dict]
    BoxPlot: chartData
    ForecastCharts: list
    CostChart: chartData
    CostSummary: tableData
    ElectricityPriceChart: chartData

#Formato del summary del dia objetivo
class simpleDataList(BaseModel):
    data: list


def getAPIKEY():
    key = dotenv.dotenv_values()["API_KEY"]
    return key

def checkApiKey(apikey):
    if apikey != getAPIKEY():
        raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            )
    
def checkDateFormat(*args):
    FECHA_REGEX = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$'
    for date in args:
        if re.match(FECHA_REGEX, date) :
            if int(date.split("-")[0]) > 1752 and int(date.split("-")[0]) <= 9999:
                return True
            else:
                raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Available date range is from year 1753 to year 9999: {date}",
            )
        raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid date format: {date}",
            )
def checkDateOrder(date_start,date_end):
    if date_start >= date_end:
        raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The start date cannot be later than the end date."
            )

def getDateStringLeftSide(date):
    return date.split("T")[0]

def datetimeFromString(date: str) -> dt.datetime:
    return dt.datetime.strptime(date,"%Y-%m-%dT%H:%M:%S")

def getClassAttributes(clase):
    '''
    Dada una clase de PyDantic te devuelve una lista con los attributos
    '''
    #https://stackoverflow.com/questions/9058305/getting-attributes-of-a-class
    atributos_sin_filtart = inspect.getmembers(clase, lambda a:not(inspect.isroutine(a)))
    lista_atributos_limpia = [atributo[1] for atributo in atributos_sin_filtart if atributo[0] == 'model_fields'][0]
    return list(lista_atributos_limpia.keys())

def isfloat(x):
    try:
        a = float(x)
    except (TypeError, ValueError):
        return False
    else:
        return True

def isint(x):
    try:
        a = float(x)
        b = int(a)
    except (TypeError, ValueError):
        return False
    else:
        return a == b
    
def checkTypeOfDays(new_year,local_holiday,national_holiday,festivities,weekend,week_day): 
    if not (new_year or local_holiday or national_holiday or festivities or weekend or week_day):
            raise HTTPException(
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
                detail="At least one 'type of day' must be true"
            )
    
def convert_summary(summary):
    for element in summary:
        for dato in element:
            if isinstance(element[dato], np.int64):
                element[dato] = int(element[dato])
    return summary
    
def getBoxploxData(result: DataFrame, q1: float, q3: float):
    data = []
    for i in range(0,24):
        current_hour_data = {}
        hour_data = result.query(f'Hour == {i}') 
        current_hour_data["max"] = current_hour_data["upper fence"] = hour_data['Power'].max()
        current_hour_data["min"] = current_hour_data["lower fence"] = hour_data['Power'].min()
        current_hour_data["median"] = hour_data['Power'].median()
        current_hour_data["q1"] = hour_data['Power'].quantile(q1)
        current_hour_data["q3"] = hour_data['Power'].quantile(q3)
        data.append(current_hour_data)
    return data

def parseSimulationData(data):
    return data.apply(lambda x: x.replace(" ","T") + ":00").to_list()

def generateResourceAllocationGraph(simulation_result, graph_number):
    graphWithRegulation = {"data":[],"category":[]}
    potDem = ResourceAllocation.GRAPH_DATA.loc[ResourceAllocation.GRAPH_DATA['IdParameter']== 'PotDem'].iloc[0]

    graphDataFilter = ResourceAllocation.GRAPH_DATA[ResourceAllocation.GRAPH_DATA['GraphType'].str.endswith(graph_number)]
    for index, graphParameter in graphDataFilter.iterrows():
        parameter = graphParameter['IdParameter']
        label = graphParameter['GraphLabel']
        graphWithRegulation["data"].append({"Name":label,"data":simulation_result[parameter].to_list()})
    graphWithRegulation["data"].append({"Name":potDem["GraphLabel"],"data":simulation_result["PotDem"].to_list()})

    #Formateamos la fecha
    graphWithRegulation["category"] = parseSimulationData(simulation_result['Date'])
    return graphWithRegulation

def generateResourceAllocationSunburst(simulation_result,modified):
    parents = {}
    sunburstIds, sunburstLabels, sunburstParents, sunburstValues, sunburstPattern, sunburstColors = [], [], [], [], [], []
    total = 0
    for colName, row in ResourceAllocation.SUNBURST_DATA.iterrows():
            paramId = row['IdParameter']
            sunburstIds.append(paramId)
            sunburstLabels.append(row['GraphLabel'])
            sunburstValues.append(
                float(abs(simulation_result[paramId + modified].sum())))
            # Si el parámetro es el principal (padre) no se indica parent, en caso contrario, el padre al que pertenece
            # el hijo vendrá indicado en el ID después de un guión
            if row['ParameterType'] == 'sunburstChildData':
                sunburstParents.append(paramId.split('-')[1]) 
            else:
                parents[paramId] = {"name":sunburstLabels[-1],"total":sunburstValues[-1],"color":row['GraphColor'],"categories":[],"data":[],"y":0}
                sunburstParents.append('')
                total += sunburstValues[-1]
            #sunburstColors.append(row['GraphColor'])
            #sunburstPattern.append(
            #    "/" if 'Surplus' in paramId else ("." if 'PotBombeo2' in paramId else ""))
    
    for i in range(0,len(sunburstParents)):
        if sunburstParents[i] != '':
            parents[sunburstParents[i]]["categories"].append(sunburstLabels[i])
            parents[sunburstParents[i]]["data"].append(sunburstValues[i]/total * 100)
        else:
            parents[sunburstIds[i]]["y"] = parents[sunburstIds[i]]["total"] / total * 100

    return parents

def generateTableFromSimulationResult(simulation_result: DataFrame, allocationParameters):
    
    simulation_result_list = simulation_result.to_dict(orient="list")
    length_of_simulation = len(simulation_result_list["Date"])
    
    data = [[] for i in range(0,length_of_simulation)]
    category = []
    #seteamos las columnas y sus nombres
    columns = [{'name': 'Date', 'id': 'Date'}]
    for index, row in allocationParameters.iterrows():
            columns.append(
                {'name': f'{row["Name"]}({row["Unity"].strip()})', 'id': row['IdParameter']})

    for column in columns:
        for i in range(0,length_of_simulation):      
            data[i].append(simulation_result_list[column["id"]][i])
        category.append(column["name"])

    return {"data":data,"category":category}


class Cache:
    def __init__(self,max_len=100) -> None:
        self.cache = {}
        self.max_len = max_len
        self.current_len = 0


    def setResult(self, key, result):
        self.cache[key] = result
        self.current_len += 1
        
    def getCachedResult(self, key):
        if key in self.cache:
            return self.cache[key]
        return None