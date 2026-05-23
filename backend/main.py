from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Optional

import schemas
import intent_parser
import poi_retriever
import route_planner
import constraint_checker
import response_generator

app = FastAPI(title="CityRoute Agent API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RouteRequest(BaseModel):
    query: str

class ModifyRequest(BaseModel):
    query: str
    current_route: Optional[Any] = None

@app.post("/api/route/generate", response_model=schemas.RouteResponse)
async def generate_route(request: RouteRequest):
    try:
        parsed_intent = intent_parser.parse_intent(request.query)
        pois = poi_retriever.retrieve_pois(parsed_intent)
        valid_pois = constraint_checker.filter_by_constraints(pois, parsed_intent)
        route = route_planner.generate_route(valid_pois, parsed_intent)
        response = response_generator.generate_response(route, parsed_intent)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/route/modify", response_model=schemas.RouteResponse)
async def modify_route(request: ModifyRequest):
    try:
        parsed_intent = intent_parser.parse_intent(request.query)
        if request.current_route:
            parsed_intent.current_route = request.current_route
        
        pois = poi_retriever.retrieve_pois(parsed_intent)
        valid_pois = constraint_checker.filter_by_constraints(pois, parsed_intent)
        route = route_planner.generate_route(valid_pois, parsed_intent)
        response = response_generator.generate_response(route, parsed_intent)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
