from fastapi import FastAPI,Query
from db import SQLdriver
from pydantic import BaseModel

from typing import Annotated

from dependencies import checkApiKey, Cache
from routers import webInasolarGraphs,similarDays,resourceAllocation,unitCommitment


db  = SQLdriver()
cache = Cache()

tags_metadata = [
    {
        "name": "Geographical data",
        "description": "Operations to get geographical data. There are two types of instances: Areas and Locations. An area can contain multiple locations, and a location can be both a consumer and a generator of energy",
    },
    {
        "name": "Inasolar Graphs",
        "description": "first app",
    },
    {
        "name": "Similar Days",
        "description": "second app",
    },
    {
        "name": "Resource Allocation",
        "description": "third app",
    },
    {
        "name": "Unit Commitment",
        "description": "fourth app"
    }
    
]

app = FastAPI(
        title="INASOLAR API",
        version =  "3.1",
        openapi_tags=tags_metadata,
        openapi_url="/api/openapi.json",
        docs_url="/api/docs"
    )


app.include_router(webInasolarGraphs.router)
app.include_router(similarDays.router)
app.include_router(resourceAllocation.router)
app.include_router(unitCommitment.router)
    
class Area(BaseModel):
    id: int
    Name: str
    Latitude: float | None = None
    Longitude: float | None = None

class ResultAreas(BaseModel):
    data: list[Area]
    
@app.get("/api/areas",
         response_model = ResultAreas,
         summary="Get all areas in the database",
         description="Get all areas in the database. Within an area, there can be several locations.",
         tags=["Geographical data"]
         )
def read_areas(apikey: Annotated[str, Query()]):
    checkApiKey(apikey)
    result = cache.getCachedResult("Areas")
    if result is not None:
        return {"data":result}
    else:
        areas = db.GETAreas() 
        cache.setResult("Areas",areas)
        return {"data":areas}

class Location(BaseModel):
    id: int
    Name: str
    Latitude: str | None = None
    Longitude: str | None = None
    Type: str 
    Area: int 
    ResourceType: str | None = None 
    InstalledPower: int |  None = None
    MaxDemand: int | float | None = None 

class ResultLocations(BaseModel):
    data: list[Location]
@app.get("/api/locations",
         response_model = ResultLocations,
         summary="Get all locations in the database",
         description="Get all locations with all the information, identifier, name, latitude, longitude, type of location, area identifier and resource type, Installed power if type is 'Generator'",
         tags=["Geographical data"]
         )
def read_locations(apikey: Annotated[str, Query()]):
    checkApiKey(apikey) 
    locations = db.GETLocations() 
    return {"data":locations}



