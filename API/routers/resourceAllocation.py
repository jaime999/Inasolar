from fastapi import APIRouter, Depends,Query, Request,BackgroundTasks
from pydantic import BaseModel

from typing import Annotated

from dependencies import checkApiKey, checkDateFormat, checkDateOrder,getDateStringLeftSide,getClassAttributes,isfloat,isint,parseSimulationData,generateResourceAllocationGraph,generateResourceAllocationSunburst,convert_summary,generateTableFromSimulationResult,tableData

from simulations.simulator import simulator
from simulations.resourceAllocationGeneric import ALLOCATION_PARAMETERS_RENEWABLES_RESULT_SQL, ResourceAllocation,OPTIMIZATION_PARAMETERS_SUMMARY_SQL

from db import SQLdriver

import copy

from numpy import int64

router = APIRouter(
    prefix="/api/resourceallocation",
    tags=["Resource Allocation"],
    dependencies=[Depends(checkApiKey)],
    responses={404: {"description": "Not found"}},
)

db  = SQLdriver()

router.lock = False
router.simulations = []
router.totalLengthScenarios = 0
router.optimization_running = False

def getInputDataInfo():
    atributos = getClassAttributes(inputDataInfo)
    query = "SELECT " + ",".join(atributos) + " FROM AllocationParameters WHERE  DefaultValue IS NOT NULL AND GraphType is NULL Order by Type,ParameterType,ParametersOrder"
    return db.SQLSelect(query)

class inputDataInfo(BaseModel):
    IdParameter: str | None
    Name: str | None
    Unity: str | None
    Type: str | None
    DefaultValue: float | None
    ParametersOrder: int | None
    Description: str | None
    ParameterType: str | None
    Disabled: bool | None

class inputDataInfoResult(BaseModel):
    data : list[inputDataInfo]


@router.get("/inputDataInfo",
         response_model=inputDataInfoResult,
         summary="Returns info required to the inputs",
         description="Returns info required to the inputs, ordered by Type, ParameterType and ParametersOrder",
         tags=["Resource Allocation"]
         )
def input_data_info(apikey: Annotated[str, Query()]):
    checkApiKey(apikey)
    inputInfo = getInputDataInfo()
    return {"data":inputInfo}

#AQUI EMPIEZA LA 

class simulationData(BaseModel):
    Table: tableData
    WithRegulationGraph:list
    WithoutRegulationGraph:list
    Summary:list
    WithRegulationSunburst:list
    WithoutRegulationSunburst:list
    CostsGraph:list

class simulationResult(BaseModel):
    data : simulationData

@router.post("/simulation",
         response_model=simulationResult,
         summary="Returns simulation result",
         description="Returns simulation result",
         tags=["Resource Allocation"]
         )

async def get_simulation(apikey: Annotated[str, Query()],location_id: Annotated[int, Query(example=1)],
                         start_date: Annotated[str, Query(example="2022-01-01T00:00:00")],
                         end_date: Annotated[str, Query(example="2022-01-02T00:00:00")],
                         request: Request,
                         max_demand: Annotated[float, Query()] = 546,
                         without_failures: Annotated[bool, Query()] = False
                         ):
    checkApiKey(apikey);checkDateFormat(start_date,end_date);db.CHECKLocationID(location_id)
    checkDateOrder(start_date,end_date)

    form = await request.form()
    my_simulator = simulator()

    setattr(my_simulator,"max_demand",max_demand)
    
    for key,value in form.items():
        if isint(value): 
            setattr(my_simulator,key,int(value))
        elif isfloat(value.replace(",",'.')):
            setattr(my_simulator,key,float(value))

    area = db.getAreaByLocationID(location_id)
    
    location = {'Location':location_id,'Area':area}

    simulation_result = my_simulator.range_simulation(start_day=getDateStringLeftSide(start_date),end_day=getDateStringLeftSide(end_date),location=location,
                                                      parameters=ALLOCATION_PARAMETERS_RENEWABLES_RESULT_SQL['IdParameter'],with_failures=not without_failures)
    
    #Tabla
    simulation_table = generateTableFromSimulationResult(simulation_result,ALLOCATION_PARAMETERS_RENEWABLES_RESULT_SQL)

    #Graficas
    graphWithRegulation = generateResourceAllocationGraph(simulation_result,"1")
    graphWithoutRegulation = generateResourceAllocationGraph(simulation_result,"2")
    
    summary = simulator.get_summary(simulation_result, False)

    summary = convert_summary(summary)

    #Sunburst
    WithRegulationSunburst = generateResourceAllocationSunburst(simulation_result,"Modified")
    WithoutRegulationSunburst = generateResourceAllocationSunburst(simulation_result,"")

    #Cost graph
    costGraph = {"data":[],"category":parseSimulationData(simulation_result["Date"])}
    # Filtrar los datos para que recupere los datos de la primera gráfica o la segunda
    for index, graphParameter in ResourceAllocation.COSTS_DATA.iterrows():
        costGraph["data"].append({"name":graphParameter['GraphLabel'],"data":simulation_result[graphParameter['IdParameter']].to_list()})

    #simulation_json = GenericCode.convertToJSON(simulation_result)
    #simulation_result[['Date','Hour']].to_dict(orient='list')]
    return {"data":
            {
                "Table":simulation_table,
                "WithRegulationGraph":[graphWithRegulation],
                "WithoutRegulationGraph":[graphWithoutRegulation],
                "Summary":summary,
                "WithRegulationSunburst":[WithRegulationSunburst],
                "WithoutRegulationSunburst":[WithoutRegulationSunburst],
                "CostsGraph":[costGraph]               
            }
            }

def optimizeMutex(scenario,scenarioParameters,start_day,end_day,location,simulationParameters,with_failures,my_simulator_copy):
    #print(scenario)
    for combination in scenario:
                my_simulator_copy.setSimulatorParametersAPI(
                    scenarioParameters, combination, OPTIMIZATION_PARAMETERS_SUMMARY_SQL)
                simulationResult = my_simulator_copy.range_simulation(
                    start_day, end_day, location, simulationParameters, with_failures)
                summary = simulator.get_summary(simulationResult, True)
            
                summary.append(
                    my_simulator_copy.addResourceParameters(OPTIMIZATION_PARAMETERS_SUMMARY_SQL['IdParameter']))
                #print(summary)
                router.simulations.append(summary)

def getOptimizationData(summary):
    # Se cambia el nombre de las claves de la fila de regulación, y se fusionan ambas filas
    # para que quede todo en una sola. También se añaden los valores de los recursos
    # utilizados en cada simulación (posición 2 de la lista)
    newSummary = []
    for index, scenario in enumerate(summary):
        regulationRow = {key + 'WR': value for key,
                         value in scenario[1].items()}
        newScenario = {**scenario[0], **scenario[2]}
        newScenario.update(regulationRow)
        newScenario['Scenario'] = f'Scenario {index}'
        newSummary.append(newScenario)

    return newSummary

class nada(BaseModel):
    data: list | float

@router.post("/optimize",
         response_model=nada,
         summary="Optimize simulation",
         description="Optimize simulation result",
         tags=["Resource Allocation"]
         )
async def optimize(background_tasks: BackgroundTasks,
                    apikey: Annotated[str, Query()],location_id: Annotated[int, Query(example=1)],
                    start_date: Annotated[str, Query(example="2022-01-01T00:00:00")],
                    end_date: Annotated[str, Query(example="2022-01-02T00:00:00")],
                    request: Request,
                    max_demand: Annotated[float, Query()] = 546,
                    without_failures: Annotated[bool, Query()] = False
                    ):
    checkApiKey(apikey);checkDateFormat(start_date,end_date);db.CHECKLocationID(location_id)
    checkDateOrder(start_date,end_date)
    #Checkeamos que no haya una optimizacion rulando
    if router.optimization_running and router.totalLengthScenarios != len(router.simulations) :
        return {"data":["Currently, there is an optimization running."]}
    
    #Esperamos al formulario
    form = await request.form()
    my_simulator = simulator()

    #Seteamos max demand
    setattr(my_simulator,"max_demand",max_demand)
    
    for key,value in form.items():
        if isint(value): 
            setattr(my_simulator,key,int(value))
            form[key] = int(value)
        elif isfloat(value.replace(",",'.')):
            setattr(my_simulator,key,float(value))
            form[key] = float(value)

    area = db.getAreaByLocationID(location_id)
    
    location = {'Location':location_id,'Area':area}
    
    #simulations = my_simulator.optimizeParametersAPI(OPTIMIZATION_PARAMETERS_SUMMARY_SQL,dict(form),start_day=getDateStringLeftSide(start_date),end_day=getDateStringLeftSide(end_date),location=location,
    #                                                simulationParameters = ALLOCATION_PARAMETERS_RENEWABLES_RESULT_SQL['IdParameter'],with_failures = not without_failures,original = original_simulator_copy)
    start_day = getDateStringLeftSide(start_date)
    end_day = getDateStringLeftSide(end_date)
    simulationParameters = ALLOCATION_PARAMETERS_RENEWABLES_RESULT_SQL['IdParameter']
    with_failures = not without_failures

    scenariosIntervals,totalLengthScenarios= my_simulator.getScenariosAPI(dict(form))
    router.simulations = []
    router.totalLengthScenarios = totalLengthScenarios
    router.optimization_running = True
    for scenario in scenariosIntervals:
        my_simulator_copy = copy.deepcopy(my_simulator)
        scenarioParameters = scenario[0].keys()
        background_tasks.add_task(optimizeMutex,scenario, scenarioParameters, start_day, end_day, location, simulationParameters, with_failures, my_simulator_copy)

    #background_tasks.add_task(mutex)
    return {"data": ["OK"]}

class status(BaseModel):
    progress : float | int
    data: list

@router.get("/optimizationStatus",
         response_model=status,
         summary="Optimize simulation",
         description="Optimize simulation result",
         tags=["Resource Allocation"]
         )
def getStatus(apikey: Annotated[str, Query()]):
    checkApiKey(apikey)
    if  router.totalLengthScenarios != 0:
        progress = len(router.simulations) / router.totalLengthScenarios * 100
    else:
        progress = 0

    parsed_results = []

    if progress == 100:
        router.optimization_running = False
        result = getOptimizationData(router.simulations) 
        
        columns = ResourceAllocation.setColumnsSummary(True)
        columns_dict = {}
        for column in columns:
            columns_dict[column["id"]] = column["name"][1]
        
        #parseamos los np.int64 y cambiamos nombre a las columnas
        for i in range(0,len(result)):
            scenario = {}
            for key, value in result[i].items():
                scenario[key] =  value

                if isinstance(value,int64):
                    scenario[key] =  int(value)

                if key in columns_dict:
                    scenario[columns_dict[key]] = scenario[key]
                    del scenario[key]

            parsed_results.append(scenario)
        
    return{"progress":progress,"data":parsed_results}