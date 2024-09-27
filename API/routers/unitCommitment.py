from fastapi import APIRouter, Depends,Query,HTTPException ,Request, status
from pydantic import BaseModel

from typing import Annotated

from dependencies import checkApiKey, checkDateFormat, checkDateOrder,getDateStringLeftSide,isfloat,isint,generateResourceAllocationGraph,generateResourceAllocationSunburst, checkTypeOfDays,convert_summary,datetimeFromString,generateTableFromSimulationResult
from dependencies import UnitCommitmentData,simpleDataList

from simulations.resourceAllocationGeneric import ALLOCATION_PARAMETERS_RENEWABLES_RESULT_SQL
from simulations.unitCommitmentGeneric import getSimilarDaysBox,formatForecastCharts,formatCostChartAndSummary,formatElectricityPriceChart
from simulations.predictor import getRangeSimulationForecast
from simulations.simulator import simulator

from db import SQLdriver
import datetime as dt

router = APIRouter(
    prefix="/api/unitcommitment",
    tags=["Unit Commitment"],
    dependencies=[Depends(checkApiKey)],
    responses={404: {"description": "Not found"}},
)

db  = SQLdriver()

def checkLocationID(*args) -> None:
    for location_id in args:
        if not db.CHECKLocationID(location_id):
            raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Location not found: {location_id}",
                )

def checkLocationType(location_id_consumer,location_id_generator):
    consumer = db.GETLocations(id=location_id_consumer)[0]["Type"]
    generator = db.GETLocations(id=location_id_generator)[0]["Type"]
    if consumer != 'Consumer':
        raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Location id {location_id_consumer} is not consumer",
            )
    if generator != 'Generator':
        raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Location id {location_id_generator} is not generator",
            )

@router.get("/getForecastSummary",
         response_model=simpleDataList,
         summary="Returns forecast weather summary from today to 2 days later",
         description="Returns forecast weather summary from today to 2 days later",
         tags=["Unit Commitment"]
         )
def get_forecast_summary(apikey: Annotated[str, Query()], location_id: Annotated[int, Query(example=1)]):
    checkApiKey(apikey)
    checkLocationID(location_id)
    data = [ ]
    now = dt.datetime.now().date()
    end = now + dt.timedelta(days=3)
    while now < end:
        data.append(db.getTargetDaySummary(now.strftime('%Y-%m-%dT%H:%M:%S'),location_id,weather_table="ForecastWeather"))
        now = now + dt.timedelta(days=1)
    return {"data":data}

@router.post("/getMarginsUnitCommitment",
         response_model=UnitCommitmentData,
         summary="Returns unit commitment",
         description="Returns unit commitment",
         tags=["Unit Commitment"]
         )
async def get_margins_unit_commitment(apikey: Annotated[str, Query()], 
                        location_id_consumer: Annotated[int, Query(example=1)],
                        location_id_generator: Annotated[int, Query(example=3)],
                        new_year:Annotated[bool, Query(example=False)],local_holiday:Annotated[bool, Query(example=False)], national_holiday:Annotated[bool, Query(example=False)],
                        festivities:Annotated[bool, Query(example=False)],weekend:Annotated[bool, Query(example=False)], week_day:Annotated[bool, Query(example=False)],
                        request: Request,
                        similar_days_start_date: Annotated[str, Query()] ="2018-01-01T00:00:00",similar_days_end_date: Annotated[str, Query()] ="2100-01-01T00:00:00",
                        predicted_start_date: Annotated[str, Query()] ="2024-05-24T00:00:00",predicted_end_date: Annotated[str, Query()] ="2024-05-27T00:00:00",
                        temperature_2m_consumer:Annotated[float, Query(ge=0)] = 100,
                        relativehumidity_2m_consumer:Annotated[float, Query(ge=0)] = 100,surface_pressure_consumer:Annotated[float, Query(ge=0)] = 1000,
                        precipitation_consumer:Annotated[float, Query(ge=0)] = 1000,snowfall_consumer:Annotated[float, Query(ge=0)] = 100,
                        cloudcover_consumer:Annotated[float, Query(ge=0)] = 100, direct_radiation_consumer:Annotated[float, Query(ge=0)] = 1000,
                        windspeed_10m_consumer:Annotated[float, Query(ge=0)] = 100 , winddirection_10m_consumer:Annotated[float, Query(ge=0,le=360)] = 360,
                        temperature_2m_generator:Annotated[float, Query(ge=0)] = 100,
                        relativehumidity_2m_generator:Annotated[float, Query(ge=0)] = 100,surface_pressure_generator:Annotated[float, Query(ge=0)] = 1000,
                        precipitation_generator:Annotated[float, Query(ge=0)] = 1000,snowfall_generator:Annotated[float, Query(ge=0)] = 100,
                        cloudcover_generator:Annotated[float, Query(ge=0)] = 100, direct_radiation_generator:Annotated[float, Query(ge=0)] = 1000,
                        windspeed_10m_generator:Annotated[float, Query(ge=0)] = 100 , winddirection_10m_generator:Annotated[float, Query(ge=0,le=360)] = 360,
                        q1:Annotated[float, Query(ge=0,le=1)] = 0.1, q3:Annotated[float, Query(ge=0,le=1)] = 0.9,
                        max_demand: Annotated[float, Query(ge=0)] = 546,
                        without_failures: Annotated[bool, Query()] = False
                        ):
    #COMPROBACIONES GENERALES
    checkApiKey(apikey)
    checkDateFormat(similar_days_start_date,similar_days_end_date,predicted_start_date,predicted_end_date)
    checkDateOrder(similar_days_start_date,similar_days_end_date)
    checkDateOrder(predicted_start_date,predicted_end_date)

    checkLocationID(location_id_consumer,location_id_generator)
    #COMPROBAR QUE LA LOCALIZACION ES EFECTIVAMENTE CONSUMER O GENERATOR
    checkLocationType(location_id_consumer,location_id_generator)

    #COMPROBAR QUE AL MENOS HAY UN TIPO DE DIA SELECCIONADO
    typeOfDays={'newYear':new_year, 'localHoliday': local_holiday,'nationalHoliday': national_holiday, 'festivities': festivities,'weekEnd': weekend, 'weekDay': week_day}
    checkTypeOfDays(new_year,local_holiday,national_holiday,festivities,weekend,week_day)

    #MAX_DEMAND
    resourceAllocationParameters = {"max_demand":max_demand}
    form = await request.form()
    
    for key,value in form.items():
        if isint(value): 
            resourceAllocationParameters[key] = int(value)
        elif isfloat(value.replace(",",'.')):
            resourceAllocationParameters[key] = float(value)

    predictedStartDate = getDateStringLeftSide(predicted_start_date)
    predictedEndDate = getDateStringLeftSide(predicted_end_date)

    consumerInputsValue = {
        "temperature_2m": temperature_2m_consumer,
        "relativehumidity_2m": relativehumidity_2m_consumer,
        "surface_pressure": surface_pressure_consumer,
        "precipitation": precipitation_consumer,
        "snowfall": snowfall_consumer,
        "cloudcover": cloudcover_consumer,
        "direct_radiation": direct_radiation_consumer,
        "windspeed_10m": windspeed_10m_consumer,
        "winddirection_10m": winddirection_10m_consumer,
    }

    generatorInputsValue = {
        "temperature_2m": temperature_2m_generator,
        "relativehumidity_2m": relativehumidity_2m_generator,
        "surface_pressure": surface_pressure_generator,
        "precipitation": precipitation_generator,
        "snowfall": snowfall_generator,
        "cloudcover": cloudcover_generator,
        "direct_radiation": direct_radiation_generator,
        "windspeed_10m": windspeed_10m_generator,
        "winddirection_10m": winddirection_10m_generator,
    }

    similarDaysTab = 'tab-margins'

    similarDaysStartDate = getDateStringLeftSide(similar_days_start_date)
    similarDaysEndDate = getDateStringLeftSide(similar_days_end_date)
    
    area_consumer = db.getAreaByLocationID(location_id_consumer)
    locationDataConsumer = {'Location':location_id_consumer,'Area':area_consumer}
    area_generator = db.getAreaByLocationID(location_id_generator)
    locationDataGenerator = {'Location':location_id_generator,'Area':area_generator}

    try:
        simulationResult, similarDays, forecastWeather, electricityPrice = getRangeSimulationForecast(resourceAllocationParameters, predictedStartDate, predictedEndDate, consumerInputsValue, generatorInputsValue, similarDaysTab,
                                                                                                          similarDaysStartDate, similarDaysEndDate, locationDataConsumer, locationDataGenerator, typeOfDays, ALLOCATION_PARAMETERS_RENEWABLES_RESULT_SQL[
                                                                                                              'IdParameter'], not without_failures, 20)
    except Exception as e:
        raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
    
    #Table
    simulation_table = generateTableFromSimulationResult(simulationResult,ALLOCATION_PARAMETERS_RENEWABLES_RESULT_SQL)

    #Graphs
    graphWithRegulation = generateResourceAllocationGraph(simulationResult,"1")
    graphWithoutRegulation = generateResourceAllocationGraph(simulationResult,"2")

    #Simulation summary
    summary = simulator.get_summary(simulationResult, False)
    #Hay que hacer esto porque hay numeros del tipo numpy int 64 que no son serializables a JSON/STR
    summary = convert_summary(summary)

    #Sunburst
    WithRegulationSunburst = generateResourceAllocationSunburst(simulationResult,"Modified")
    WithoutRegulationSunburst = generateResourceAllocationSunburst(simulationResult,"")

    #Boxplot
    similarDaysGraph = getSimilarDaysBox(similarDays, {'Low': q1*100, 'Upp': q3*100}, datetimeFromString(predicted_end_date),datetimeFromString(predicted_start_date))
    
    #Forecast charts
    forecast_charts = formatForecastCharts(forecastWeather,graphWithRegulation["category"],db)

    #Costes y summary
    costData,summaryCost = formatCostChartAndSummary(simulationResult,graphWithRegulation["category"])
    
    #Electricity Prices
    electricityPriceChart = formatElectricityPriceChart(electricityPrice)

    return {
        "Table":simulation_table,
        "WithRegulationGraph": graphWithRegulation,
        "WithoutRegulationGraph" : graphWithoutRegulation,
        "Summary" : summary,
        "WithRegulationSunburst" : [WithRegulationSunburst],
        "WithoutRegulationSunburst" : [WithoutRegulationSunburst],
        "BoxPlot":similarDaysGraph,
        "ForecastCharts":[forecast_charts],
        "CostChart": costData,
        "CostSummary":summaryCost,
        "ElectricityPriceChart":electricityPriceChart
    }


@router.post("/getPondersUnitCommitment",
         response_model=UnitCommitmentData,
         summary="Returns unit commitment",
         description="Returns unit commitment",
         tags=["Unit Commitment"]
         )
async def get_ponders_unit_commitment(apikey: Annotated[str, Query()], 
                        location_id_consumer: Annotated[int, Query(example=1)],
                        location_id_generator: Annotated[int, Query(example=3)],
                        request: Request,
                        similar_days_start_date: Annotated[str, Query()] ="2018-01-01T00:00:00",similar_days_end_date: Annotated[str, Query()] ="2100-01-01T00:00:00",
                        predicted_start_date: Annotated[str, Query()] ="2024-05-24T00:00:00",predicted_end_date: Annotated[str, Query()] ="2024-05-27T00:00:00",
                        temperature_2m_consumer:Annotated[float, Query(ge=0,le=1)] = 0.2,
                        relativehumidity_2m_consumer:Annotated[float, Query(ge=0,le=1)] = 0.1,surface_pressure_consumer:Annotated[float, Query(ge=0,le=1)] = 0.2,
                        precipitation_consumer:Annotated[float, Query(ge=0,le=1)] = 0,snowfall_consumer:Annotated[float, Query(ge=0,le=1)] = 0,
                        cloudcover_consumer:Annotated[float, Query(ge=0,le=1)] = 0.1, direct_radiation_consumer:Annotated[float, Query(ge=0,le=1)] = 0.2,
                        windspeed_10m_consumer:Annotated[float, Query(ge=0,le=1)] = 0 , winddirection_10m_consumer:Annotated[float, Query(ge=0,le=1)] = 0,
                        temperature_2m_generator:Annotated[float, Query(ge=0,le=1)] = 0.2,
                        relativehumidity_2m_generator:Annotated[float, Query(ge=0,le=1)] = 0.1,surface_pressure_generator:Annotated[float, Query(ge=0,le=1)] = 0.2,
                        precipitation_generator:Annotated[float, Query(ge=0,le=1)] = 0,snowfall_generator:Annotated[float, Query(ge=0,le=1)] = 0,
                        cloudcover_generator:Annotated[float, Query(ge=0,le=1)] = 0.1, direct_radiation_generator:Annotated[float, Query(ge=0,le=1)] = 0.2,
                        windspeed_10m_generator:Annotated[float, Query(ge=0,le=1)] = 0 , winddirection_10m_generator:Annotated[float, Query(ge=0,le=1)] = 0,
                        q1:Annotated[float, Query(ge=0,le=1)] = 0.1, q3:Annotated[float, Query(ge=0,le=1)] = 0.9,
                        max_demand: Annotated[float, Query(ge=0)] = 546,
                        without_failures: Annotated[bool, Query()] = False
                        ):
    #COMPROBACIONES GENERALES
    checkApiKey(apikey)
    checkDateFormat(similar_days_start_date,similar_days_end_date,predicted_start_date,predicted_end_date)
    checkDateOrder(similar_days_start_date,similar_days_end_date)
    checkDateOrder(predicted_start_date,predicted_end_date)

    checkLocationID(location_id_consumer,location_id_generator)
    #COMPROBAR QUE LA LOCALIZACION ES CONSUMER O GENERATOR
    checkLocationType(location_id_consumer,location_id_generator)

    #COMPROBAR QUE AL MENOS HAY UN TIPO DE DIA SELECCIONADO
    typeOfDays={'newYear':False, 'localHoliday': False,'nationalHoliday': False, 'festivities': False,'weekEnd': False, 'weekDay': True}

    #MAX_DEMAND
    resourceAllocationParameters = {"max_demand":max_demand}
    form = await request.form()
    
    for key,value in form.items():
        if isint(value): 
            resourceAllocationParameters[key] = int(value)
        elif isfloat(value.replace(",",'.')):
            resourceAllocationParameters[key] = float(value)

    predictedStartDate = getDateStringLeftSide(predicted_start_date)
    predictedEndDate = getDateStringLeftSide(predicted_end_date)

    consumerInputsValue  = [
    temperature_2m_consumer,
    relativehumidity_2m_consumer,
    surface_pressure_consumer,
    precipitation_consumer,
    snowfall_consumer,
    cloudcover_consumer,
    direct_radiation_consumer,
    windspeed_10m_consumer,
    winddirection_10m_consumer,
    ]

    generatorInputsValue  = [
        temperature_2m_generator,
        relativehumidity_2m_generator,
        surface_pressure_generator,
        precipitation_generator,
        snowfall_generator,
        cloudcover_generator,
        direct_radiation_generator,
        windspeed_10m_generator,
        winddirection_10m_generator,
    ]

    similarDaysTab = ''

    similarDaysStartDate = getDateStringLeftSide(similar_days_start_date)
    similarDaysEndDate = getDateStringLeftSide(similar_days_end_date)
    
    area_consumer = db.getAreaByLocationID(location_id_consumer)
    locationDataConsumer = {'Location':location_id_consumer,'Area':area_consumer}
    area_generator = db.getAreaByLocationID(location_id_generator)
    locationDataGenerator = {'Location':location_id_generator,'Area':area_generator}

    try:
        simulationResult, similarDays, forecastWeather, electricityPrice = getRangeSimulationForecast(resourceAllocationParameters, predictedStartDate, predictedEndDate, consumerInputsValue, generatorInputsValue, similarDaysTab,
                                                                                                          similarDaysStartDate, similarDaysEndDate, locationDataConsumer, locationDataGenerator, typeOfDays, ALLOCATION_PARAMETERS_RENEWABLES_RESULT_SQL[
                                                                                                              'IdParameter'], not without_failures, 20)
    except Exception as e:
        raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
    
    #Table
    simulation_table = generateTableFromSimulationResult(simulationResult,ALLOCATION_PARAMETERS_RENEWABLES_RESULT_SQL)
    
    #Graphs
    graphWithRegulation = generateResourceAllocationGraph(simulationResult,"1")
    graphWithoutRegulation = generateResourceAllocationGraph(simulationResult,"2")

    summary = simulator.get_summary(simulationResult, False)
    #Hay que hacer esto porque hay numeros del tipo numpy int 64 que no son serializables a JSON/STR
    summary = convert_summary(summary)

    #Sunburst
    WithRegulationSunburst = generateResourceAllocationSunburst(simulationResult,"Modified")
    WithoutRegulationSunburst = generateResourceAllocationSunburst(simulationResult,"")

    #boxplot_data = getBoxploxData(similarDays,q1,q3)
    similarDaysGraph = getSimilarDaysBox(similarDays, {'Low': q1*100, 'Upp': q3*100}, datetimeFromString(predicted_end_date),datetimeFromString(predicted_start_date))
      
    forecast_charts = formatForecastCharts(forecastWeather,graphWithRegulation["category"],db)

    #Costes y summary
    costData,summaryCost = formatCostChartAndSummary(simulationResult,graphWithRegulation["category"])
    
    #Electricity Prices
    electricityPriceChart = formatElectricityPriceChart(electricityPrice)

    return {
        "Table":simulation_table,
        "WithRegulationGraph": graphWithRegulation,
        "WithoutRegulationGraph" : graphWithoutRegulation,
        "Summary" : summary,
        "WithRegulationSunburst" : [WithRegulationSunburst],
        "WithoutRegulationSunburst" : [WithoutRegulationSunburst],
        "BoxPlot":similarDaysGraph,
        "ForecastCharts":[forecast_charts],
        "CostChart": costData,
        "CostSummary":summaryCost,
        "ElectricityPriceChart":electricityPriceChart
    }