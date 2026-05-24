from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import constraint_checker
import intent_parser
import poi_retriever
import prompt_templates
import response_generator
import route_planner
import schemas

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
    preferences: Optional[list[str]] = None
    city: Optional[str] = None


class ModifyRequest(BaseModel):
    query: str
    original_query: Optional[str] = None
    current_route: Optional[Any] = None


class IntentParseRequest(BaseModel):
    query: str = ""
    city: Optional[str] = None
    llm_draft: Optional[schemas.LLMIntentDraft] = None


SUPPORTED_CITIES = ["广州", "上海"]
CITY_HINTS = {
    "广州": ["广州", "广州塔", "花城广场", "海心沙", "珠江新城", "白云山", "北京路", "上下九"],
    "上海": ["上海", "外滩", "豫园", "武康路", "思南路", "陆家嘴", "南京路", "新天地"],
}


@app.post("/api/intent/parse", response_model=schemas.ParsedIntent)
async def parse_intent(request: IntentParseRequest):
    if request.llm_draft is not None:
        return intent_parser.normalize_llm_intent(request.llm_draft, request.query)
    return intent_parser.parse_intent(request.query, request.city)

@app.post("/api/intent/prompt")
async def build_intent_prompt(request: IntentParseRequest):
    return prompt_templates.build_intent_prompt(request.query, request.city)


def _infer_city_from_route(current_route: Any) -> Optional[str]:
    if not current_route:
        return None

    parts: list[str] = []
    if isinstance(current_route, dict):
        for key in ("title", "summary", "route_explanation", "original_query"):
            value = current_route.get(key)
            if isinstance(value, str):
                parts.append(value)
        for stop in current_route.get("stops", []) or []:
            if isinstance(stop, dict):
                poi = stop.get("poi", {})
                if isinstance(poi, dict):
                    for key in ("city", "name", "district", "address"):
                        value = poi.get(key)
                        if isinstance(value, str):
                            parts.append(value)
    else:
        text = str(current_route)
        parts.append(text)

    combined = " ".join(parts)
    for city, hints in CITY_HINTS.items():
        if any(hint in combined for hint in hints):
            return city
    return None


@app.post("/api/route/generate", response_model=schemas.RouteResponse)
async def generate_route(request: RouteRequest):
    try:
        parsed_intent = intent_parser.parse_intent(request.query, request.city)
        if request.preferences:
            intent_parser.apply_ui_preferences(parsed_intent, request.preferences)
        valid, errors = constraint_checker.validate_intent(parsed_intent)
        if not valid:
            raise HTTPException(status_code=422, detail={"errors": errors})

        pois = poi_retriever.retrieve_pois(parsed_intent)
        valid_pois = constraint_checker.filter_by_constraints(pois, parsed_intent)
        route = route_planner.generate_route(valid_pois, parsed_intent)
        response = response_generator.generate_response(route, parsed_intent)
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/route/modify", response_model=schemas.RouteResponse)
async def modify_route(request: ModifyRequest):
    try:
        inferred_city = _infer_city_from_route(request.current_route)
        parsed_intent = intent_parser.parse_intent(request.query, inferred_city)
        parsed_intent.current_route = request.current_route

        valid, errors = constraint_checker.validate_intent(parsed_intent)
        if not valid:
            raise HTTPException(status_code=422, detail={"errors": errors})

        pois = poi_retriever.retrieve_pois(parsed_intent)
        valid_pois = constraint_checker.filter_by_constraints(pois, parsed_intent)
        route = route_planner.generate_route(valid_pois, parsed_intent)
        response = response_generator.generate_response(route, parsed_intent)
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
