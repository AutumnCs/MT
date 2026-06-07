from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from core.api_contracts import (
    CapabilityMatchRequest,
    CapabilityQueryRequest,
    CapabilityRouterPromptRequest,
    ContextEventRequest,
    ContextRouteVersionRequest,
    EvalRequest,
    IntentParseRequest,
    ModifyRequest,
    PromptRequest,
    RouteRequest,
)
from core import capability_registry
from core.contracts import CapabilityMatchResult
from core import intent_parser
from core import llm_intent_client
from core import map_schemas
from core import prompt_templates
from core import schemas
from core.route_context import infer_city_from_route
from eval.eval_runner import run_offline_evaluation
from services import context_service
from services import constraint_checker
from services import map_service
from services import poi_retriever
from services import response_generator
from services import route_planner
from services import route_service

app = FastAPI(title="CityRoute Agent API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/intent/parse", response_model=schemas.ParsedIntent)
async def parse_intent(request: IntentParseRequest):
    if request.llm_draft is not None:
        return intent_parser.normalize_llm_intent(request.llm_draft, request.query)
    return _parse_intent_with_optional_llm(request.query, request.city)

@app.post("/api/intent/prompt")
async def build_intent_prompt(request: PromptRequest):
    return prompt_templates.build_prompt_bundle(
        request.task,
        request.query,
        city=request.city,
        original_query=request.original_query,
        current_route=request.current_route,
        route_summary=request.route_summary,
        intent_summary=request.intent_summary,
    )


def _parse_intent_with_optional_llm(query: str, city: Optional[str] = None) -> schemas.ParsedIntent:
    parsed_intent = llm_intent_client.parse_intent_with_llm(query, city)
    if parsed_intent is not None:
        return parsed_intent
    return intent_parser.parse_intent(query, city)


def _record_context_turn(
    session_id: Optional[str],
    *,
    event_type: str,
    query: Optional[str],
    intent: Optional[schemas.ParsedIntent],
    response: Optional[schemas.RouteResponse],
) -> None:
    if not session_id:
        return
    try:
        context_service.record_event(
            session_id,
            event_type,
            query=query,
            intent=intent,
            route_version=response,
            diagnostics=getattr(response, "diagnostics", None) if response is not None else None,
        )
    except Exception:
        # Context should never block routing.
        pass

@app.post("/api/route/generate", response_model=schemas.RouteResponse)
async def generate_route(request: RouteRequest):
    try:
        context_snapshot = context_service.get_context_snapshot(request.session_id) if request.session_id else None
        profile = context_snapshot.profile if context_snapshot is not None else None
        intent, response = route_service.plan_route(
            request.query,
            preferences=request.preferences,
            city=request.city,
            profile=profile,
            context_snapshot=context_snapshot,
        )
        _record_context_turn(
            request.session_id,
            event_type="clarification_requested" if response.clarification_needed else "route_created",
            query=request.query,
            intent=intent,
            response=response,
        )
        return response
    except route_service.RoutePlanningError as err:
        raise HTTPException(status_code=err.status_code, detail=err.detail)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/route/modify", response_model=schemas.RouteResponse)
async def modify_route(request: ModifyRequest):
    try:
        inferred_city = infer_city_from_route(request.current_route)
        context_snapshot = context_service.get_context_snapshot(request.session_id) if request.session_id else None
        profile = context_snapshot.profile if context_snapshot is not None else None
        intent, response = route_service.plan_route(
            request.query,
            city=inferred_city,
            current_route=request.current_route,
            original_query=request.original_query or request.query,
            profile=profile,
            context_snapshot=context_snapshot,
        )
        _record_context_turn(
            request.session_id,
            event_type="clarification_requested" if response.clarification_needed else "route_modified",
            query=request.query,
            intent=intent,
            response=response,
        )
        return response
    except route_service.RoutePlanningError as err:
        raise HTTPException(status_code=err.status_code, detail=err.detail)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/eval/run")
async def run_evaluation(request: EvalRequest):
    report = run_offline_evaluation(
        case_ids=request.case_ids,
        limit=request.limit,
    )
    return report


@app.get("/api/context/{session_id}")
async def get_context(session_id: str, limit: int = 12):
    return context_service.get_context_snapshot(session_id, limit=limit).model_dump(mode="json")


@app.get("/api/context/{session_id}/profile")
async def get_context_profile(session_id: str):
    return context_service.get_profile(session_id).model_dump(mode="json")


@app.post("/api/context/{session_id}/event")
async def append_context_event(session_id: str, request: ContextEventRequest):
    snapshot = context_service.record_event(
        session_id,
        request.event_type,
        query=request.query,
        payload=request.payload,
        intent=request.intent,
        route_version=request.route_version,
        diagnostics=request.diagnostics,
    )
    return snapshot.model_dump(mode="json")


@app.post("/api/context/{session_id}/route-version")
async def append_route_version(session_id: str, request: ContextRouteVersionRequest):
    snapshot = context_service.record_route_version(
        session_id,
        event_type=request.event_type,
        query=request.query,
        intent=request.intent,
        route_version=request.route_version,
        diagnostics=request.diagnostics,
    )
    return snapshot.model_dump(mode="json")


@app.delete("/api/context/{session_id}")
async def reset_context(session_id: str):
    context_service.reset_session(session_id)
    return {"session_id": session_id, "reset": True}


@app.get("/api/capabilities")
async def list_capabilities():
    return capability_registry.load_capability_registry()


@app.post("/api/capabilities/query")
async def query_capability(request: CapabilityQueryRequest):
    if request.name:
        return capability_registry.get_capability(request.name) or {}
    return {"matches": capability_registry.list_capabilities()}


@app.post("/api/capabilities/match")
async def match_capabilities(request: CapabilityMatchRequest):
    matches = capability_registry.match_capabilities(request.query, request.limit)
    best = matches[0] if matches else capability_registry.route_capability(request.query)
    return {
        "query": request.query,
        "best": best.model_dump() if isinstance(best, CapabilityMatchResult) else best,
        "matches": [item.model_dump() for item in matches],
        "registry_version": capability_registry.load_capability_registry().get("version", "0"),
    }


@app.post("/api/capabilities/router-prompt")
async def capability_router_prompt(request: CapabilityRouterPromptRequest):
    return prompt_templates.build_prompt_bundle(
        "capability_router",
        request.query,
    )


@app.get("/api/map/status", response_model=map_schemas.MapStatusResponse)
async def map_status():
    return map_service.get_status()


@app.post("/api/map/geocode", response_model=map_schemas.MapApiResponse)
async def map_geocode(request: map_schemas.MapGeocodeRequest):
    return map_service.geocode(request.address, request.city)


@app.post("/api/map/reverse-geocode", response_model=map_schemas.MapApiResponse)
async def map_reverse_geocode(request: map_schemas.MapReverseGeocodeRequest):
    return map_service.reverse_geocode(request.longitude, request.latitude)


@app.post("/api/map/poi-search", response_model=map_schemas.MapApiResponse)
async def map_poi_search(request: map_schemas.MapPoiSearchRequest):
    return map_service.search_poi(
        request.keyword,
        city=request.city,
        location=request.location,
        radius=request.radius,
        types=request.types,
        limit=request.limit,
    )


@app.post("/api/map/route", response_model=map_schemas.MapApiResponse)
async def map_route(request: map_schemas.MapRouteRequest):
    origin = schemas.POI(
        id="origin",
        name="origin",
        category="custom",
        city="",
        address="",
        latitude=request.origin_latitude,
        longitude=request.origin_longitude,
    )
    destination = schemas.POI(
        id="destination",
        name="destination",
        category="custom",
        city="",
        address="",
        latitude=request.destination_latitude,
        longitude=request.destination_longitude,
    )
    result = map_service.estimate_travel_between_pois(origin, destination, request.mode)
    return {
        "provider": result.get("provider", "local"),
        "enabled": result.get("enabled", False),
        "success": result.get("success", False),
        "message": result.get("message"),
        "data": result.get("travel", {}),
    }


@app.post("/api/map/preview", response_model=map_schemas.MapApiResponse)
async def map_preview(request: map_schemas.MapPreviewRequest):
    stops: list[dict[str, Any]] = []
    for index, point in enumerate(request.points):
        if not isinstance(point, dict):
            continue
        stops.append(
            {
                "poi": {
                    "id": point.get("id", f"point-{index + 1}"),
                    "name": point.get("name", f"Point {index + 1}"),
                    "category": point.get("category", "custom"),
                    "city": point.get("city", ""),
                    "address": point.get("address", ""),
                    "latitude": point.get("latitude", 0.0),
                    "longitude": point.get("longitude", 0.0),
                },
                "arrival_time": point.get("arrival_time", ""),
                "departure_time": point.get("departure_time", ""),
                "stay_minutes": point.get("stay_minutes", 0),
                "reason": point.get("reason", ""),
                "risk_alert": point.get("risk_alert"),
                "travel_from_previous": point.get("travel_from_previous"),
            }
        )
    route = schemas.RouteResponse(
        title=request.title or "地图预览",
        summary=request.title or "地图预览",
        total_cost=0,
        total_duration=0,
        total_distance=0.0,
        poi_count=len(stops),
        covered_types=[],
        stops=[schemas.RouteStop(**item) for item in stops],
        route_explanation="",
    )
    return {
        "provider": "tdt" if map_service.is_enabled() else "local",
        "enabled": map_service.is_enabled(),
        "success": True,
        "message": None,
        "data": map_service.build_route_preview(route),
    }


if __name__ == "__main__":
    import os

    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
