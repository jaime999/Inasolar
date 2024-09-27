from fastapi import APIRouter, Depends, HTTPException,Query,status
from pydantic import BaseModel

from typing import Annotated

from dependencies import checkApiKey, checkDateFormat,Cache,chartData, checkDateOrder

from db import SQLdriver


router = APIRouter(
    prefix="/api/web-inasolargraphs",
    tags=["Inasolar Graphs"],
    dependencies=[Depends(checkApiKey)],
    responses={404: {"description": "Not found"}},
)

db  = SQLdriver()
cache = Cache()

def checkTable(table):
    if db.CHECKTableIsAvailable(table):
        return True
    else:
        raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"La tabla '{table}' no existe",
            )
    
def checkColumn(table,column):
    if checkTable(table):
        if db.CHECKColumnIsAvailable(table,column):
            return True
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"La columna '{column}' no existe en la tabla '{table}'",
            )
    
def checkLocationID(location_id):
    if db.CHECKLocationID(location_id):
        return True
    else:
        raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe la localizacion con id '{location_id}'",
            )

class TableDescription(BaseModel):
    TableId: str
    TableName: str

class TableDescriptionResults(BaseModel):
    data: list[TableDescription]
@router.get("/getTableDescriptions",
         response_model = TableDescriptionResults,
         summary="Returns the tables from which data can be shown.",
         description="Returns TableId(real name), TableName(name to the user)",

         )
async def get_table_descriptions(apikey: Annotated[str, Query()]):
    checkApiKey(apikey)
    descriptions = db.GETTableDescriptions()
    return {"data":descriptions}


class ColumnDescription(BaseModel):
    nombre_dato: str | None = None
    nombre_alternativo: str | None = None
    descripcion: str | None = None
    unidad: str | None = None
    defaultMargin: float | None = None
    defaultPonder: float | None = None
    tabla: str | None = None

class ColumnDescriptionResults(BaseModel):
    data: list[ColumnDescription]
@router.get("/getColumnDescriptions",
         response_model = ColumnDescriptionResults,
         summary="Returns information about columns that are available for display.",
         description="Returns information about columns that are available for display.",
         tags=["Inasolar Graphs"]
         )
async def get_column_descriptions(apikey: Annotated[str, Query()],table_id: Annotated[str, Query()] = None):
    checkApiKey(apikey)
    if table_id is not None:
        checkTable(table_id)
    descriptions = db.GETColumnDescriptions(table_id)
    return {"data":descriptions}


@router.get("/getData",
         response_model = chartData,
         summary="Returns the weather history of an area given a range of dates",
         description="Returns the weather history of an area with all the information, identifier, name, latitude, longitude, type of location, area identifier and resource type, Installed power if type is 'Generator'",
         tags=["Inasolar Graphs"]
         )
async def getData(apikey: Annotated[str, Query()], start_date: Annotated[str, Query()] ="2022-01-01T00:00:00",end_date: Annotated[str, Query()] = "2022-01-01T01:00:00", 
                                location_id: Annotated[int, Query()] = 1,table_1: Annotated[str, Query()]="HistoricalWeather",table_2: Annotated[str, Query()]="datosGEDER2",
                                column_1: Annotated[str, Query()]="temperature_2m",column_2: Annotated[str, Query()]="Power"):
    checkApiKey(apikey)
    checkLocationID(location_id)
    checkDateFormat(start_date,end_date)
    checkDateOrder(start_date,end_date)
    if checkTable(table_1) and checkTable(table_2):
        if checkColumn(table_1,column_1) and checkColumn(table_2,column_2):
            #si esta en cache
            result = cache.getCachedResult("getData"+"".join(str([start_date,end_date,location_id,table_1,table_2,column_1,column_2])))
            if result is not None:
                return {"data":result[0], "category":result[1]}
            
            result, dates = db.getGenericData(start_date,end_date,location_id,table_1,table_2,column_1,column_2)
            cache.setResult("getData"+"".join(str([start_date,end_date,location_id,table_1,table_2,column_1,column_2])),[result,dates])
            return {"data":result, "category":dates}
    return {"data":[], "category":[]}