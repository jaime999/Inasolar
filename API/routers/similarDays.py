from fastapi import APIRouter, Depends, HTTPException,Query,status
from pydantic import BaseModel

from typing import Annotated

from dependencies import checkApiKey, checkDateFormat, checkDateOrder,getDateStringLeftSide,getBoxploxData,checkTypeOfDays,simpleDataList

from db import SQLdriver
from simulations.filtro_dias import filtro_dias as fd
from simulations.genericCode import GenericCode

from numpy import unique
from pandas import DataFrame, concat, merge

router = APIRouter(
    prefix="/api/similardays",
    tags=["Similar Days"],
    dependencies=[Depends(checkApiKey)],
    responses={404: {"description": "Not found"}},
)

db  = SQLdriver()
filtro_dias = fd()

def checkLocationID(location_id):
    if db.CHECKLocationID(location_id):
        return True
    else:
        raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe la localizacion con id '{location_id}'",
            )

def  parseGraphicData(selected_dates: list,result : DataFrame):
    data = []
    for date in selected_dates:
        day = {"name":date}
        day["data"] = result.loc[result['Date'] == date]["Power"].to_list()
        data.append(day)
    return data

def getTableData(result,target_date,bestDays=None,ponders=False):
    
    similarDaysGrouped = result.groupby(by='Date', as_index=False)
    similarDaysTable = filtro_dias.calculateTable(similarDaysGrouped)

    rowToMove = similarDaysTable.loc[similarDaysTable['Date'] == target_date]
    similarDaysTable = concat(
                [rowToMove, similarDaysTable[similarDaysTable['Date'] != target_date]]).reset_index(drop=True)

    ordered_cols = ['Date']
    
    ordered_cols.append('Power')
    if ponders == 'tab-ponders':
        similarDaysTable = merge(similarDaysTable, bestDays, on='Date', how='left')
        ordered_cols.append('score_final')

    for index, row in GenericCode.SIMILAR_DAYS_RESULT_COLUMNS_SQL.iterrows():
                ordered_cols.append(row['nombre_dato'])
    for index, row in GenericCode.HISTORICAL_WEATHER_COLUMNS_SQL.iterrows():
            ordered_cols.append(row['nombre_dato'])
            
    similarDaysTable = similarDaysTable[ordered_cols]

    #Ponemos los nombres alternativos
    for column in ordered_cols:
        try:
            similarDaysTable.rename(columns={column:db.getColumnAlternativeName(column)},inplace=True)
        except:
            if column == 'score_final':
                similarDaysTable.rename(columns={column: 'Score'},inplace=True)
            continue

    similarDaysTable = similarDaysTable.to_dict("tight")

    response = {'data':similarDaysTable["data"],
                'category':similarDaysTable["columns"]}
    
    return response

class TargetDaySummaryData(BaseModel):
    data: dict
    category: dict
@router.get("/getTargetDateData",
         response_model=TargetDaySummaryData,
         summary="Returns target date info",
         description="Returns target date info",
         tags=["Similar Days"]
         )
def get_target_data(apikey: Annotated[str, Query()], target_date: Annotated[str, Query(example="2022-01-01T00:00:00")] , location_id: Annotated[int, Query(example=1)]):
    checkApiKey(apikey); checkLocationID(location_id)

    if checkDateFormat(target_date) :
        data,category = db.getTargetDaySummary(target_date,location_id)

    return {"data":data,"category":category}

@router.get("/getMarginsPondersInfo",
         response_model=simpleDataList,
         summary="Returns margin and ponders data",
         description="Returns margin and ponders data",
         tags=["Similar Days"]
         )
def get_ponders_margins(apikey: Annotated[str, Query()]):
    checkApiKey(apikey)
    column_descriptions = db.GETColumnDescriptions("HistoricalWeather")
    return {"data":column_descriptions}

class chartData(BaseModel):
    data: list
    category: list

class SimilarDaysGraphicsData(BaseModel):
    lineChart: chartData
    boxPlot: chartData
    table: chartData

@router.get("/getMarginsGraphicsData",
         response_model=SimilarDaysGraphicsData,
         summary="Returns margins graphic data",
         description="Returns margins graphic data",
         tags=["Similar Days"]
         )
def get_similar_margins(apikey: Annotated[str, Query()], target_date: Annotated[str, Query(example="2022-01-01T00:00:00")] ,location_id:Annotated[int, Query(example= 1)],
                        new_year:Annotated[bool, Query(example=False)],local_holiday:Annotated[bool, Query(example=False)], national_holiday:Annotated[bool, Query(example=False)],
                        festivities:Annotated[bool, Query(example=False)],weekend:Annotated[bool, Query(example=False)], week_day:Annotated[bool, Query(example=False)] ,
                        start_date: Annotated[str, Query()] ="2018-01-01T00:00:00",end_date: Annotated[str, Query()] ="2100-01-01T00:00:00", 
                        temperature_2m:Annotated[float, Query(ge=0)] = 100,
                        relativehumidity_2m:Annotated[float, Query(ge=0)] = 100,surface_pressure:Annotated[float, Query(ge=0)] = 1000,
                        precipitation:Annotated[float, Query(ge=0)] = 1000,snowfall:Annotated[float, Query(ge=0)] = 100,
                        cloudcover:Annotated[float, Query(ge=0)] = 100, direct_radiation:Annotated[float, Query(ge=0)] = 1000,
                        windspeed_10m:Annotated[float, Query(ge=0)] = 100 , winddirection_10m:Annotated[float, Query(ge=0,le=360)] = 360,
                        q1:Annotated[float, Query(ge=0,le=1)] = 0.1, q3:Annotated[float, Query(ge=0,le=1)] = 0.9
                        ):

    checkApiKey(apikey)
    checkDateFormat(target_date,start_date,end_date)
    checkDateOrder(start_date,end_date)

    margins={"temperature_2m": temperature_2m, "cloudcover": cloudcover, "direct_radiation": direct_radiation,
                            "relativehumidity_2m":relativehumidity_2m, "surface_pressure": surface_pressure, "precipitation": precipitation,
                                "snowfall": snowfall, "windspeed_10m": windspeed_10m, "winddirection_10m": winddirection_10m}
    
    #COMPROBAMOS Y PREPARAMOS LOS TIPOS DE DÍAS
    typeOfDays={'newYear':new_year, 'localHoliday': local_holiday,'nationalHoliday': national_holiday, 'festivities': festivities,'weekEnd': weekend, 'weekDay': week_day}
    
    #Comprobamos que al menos 1 es True porque sino, no encuentra días similares
    checkTypeOfDays(new_year,local_holiday,national_holiday,festivities,weekend,week_day)
    
    checkLocationID(location_id)

    area = db.getAreaByLocationID(location_id)
    location = {"Location":location_id,"Area":area}
    result = filtro_dias.get_days_by_similar_meteorological_variables_margins(
                date=target_date,margins= margins,fecha_ini= getDateStringLeftSide(start_date), fecha_fin=getDateStringLeftSide(end_date),
                 location= location,typeOfDays=typeOfDays)
    
    if 'errorMessage' in result:
        raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["errorMessage"],
            )

    boxplot_data = getBoxploxData(result,q1,q3)
    selected_dates = unique(result["Date"])

    similarDaysTable = getTableData(result,target_date)
    
    chart_data = parseGraphicData(selected_dates,result)

    response = {"lineChart":{"data":chart_data,"category":range(0,24)},
                "boxPlot": {"data":boxplot_data,"category":range(0,24)},
                  "table": similarDaysTable }
    return response

@router.get("/getPondersGraphicsData",
         response_model=SimilarDaysGraphicsData,
         summary="Returns ponders graphic data",
         description="Returns ponders graphic data",
         tags=["Similar Days"]
         )
def get_similar_ponders(apikey: Annotated[str, Query()], target_date: Annotated[str, Query(example="2022-01-01T00:00:00")],location_id:Annotated[int, Query(example= 1)] ,
                        start_date: Annotated[str, Query()] ="2018-01-01T00:00:00",
                        end_date: Annotated[str, Query()] ="2100-01-01T00:00:00",
                        temperature_2m:Annotated[float, Query(ge=0,le=1)] = 0.2,
                        relativehumidity_2m:Annotated[float, Query(ge=0,le=1)] = 0.1,surface_pressure:Annotated[float, Query(ge=0,le=1)] = 0.2,
                        precipitation:Annotated[float, Query(ge=0,le=1)] = 0,snowfall:Annotated[float, Query(ge=0,le=1)] = 0,
                        cloudcover:Annotated[float, Query(ge=0,le=1)] = 0.1, direct_radiation:Annotated[float, Query(ge=0,le=1)] = 0.2,
                        windspeed_10m:Annotated[float, Query(ge=0,le=1)] = 0 , winddirection_10m:Annotated[float, Query(ge=0,le=1)] = 0,
                        number_of_days: Annotated[int, Query(ge=1)] = 20, q1:Annotated[float, Query(ge=0,le=1)] = 0.1, q3:Annotated[float, Query(ge=0,le=1)] = 0.9
                        ):
    checkApiKey(apikey)
    checkDateFormat(target_date,start_date,end_date)
    checkDateOrder(start_date,end_date)

    ponders=[temperature_2m, relativehumidity_2m, surface_pressure,
                            precipitation, snowfall, cloudcover,
                                direct_radiation, windspeed_10m, winddirection_10m]

    checkLocationID(location_id)

    results = filtro_dias.get_days_by_similar_meteorological_variables_ponders(
                target_date, ponders,location_id, getDateStringLeftSide(start_date), getDateStringLeftSide(end_date), number_of_days)
    
    if len(results)==1:
        raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=results["errorMessage"],
            )
    best_days = results[0]
    day_data = results[1]

    result = fd.getSimilarDaysByHours(best_days, day_data, getDateStringLeftSide(target_date))
    
    boxplot_data = getBoxploxData(result,q1,q3)

    similarDaysTable = getTableData(result,target_date,bestDays=best_days,ponders='tab-ponders')

    selected_dates = unique(result["Date"])
    response = {"lineChart":{"data":parseGraphicData(selected_dates,result),"category":range(0,24)},
                "boxPlot": {"data":boxplot_data,"category":range(0,24)},
                "table": similarDaysTable}
    
    return response