"""HTTP request contracts shared by the FastAPI surface."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from core import schemas

class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RouteRequest(APIModel):
    query: str
    preferences: Optional[list[str]] = None
    city: Optional[str] = None
    session_id: Optional[str] = None


class ModifyRequest(APIModel):
    query: str
    original_query: Optional[str] = None
    current_route: Optional[Any] = None
    session_id: Optional[str] = None


class IntentParseRequest(APIModel):
    query: str = ""
    city: Optional[str] = None
    llm_draft: Optional[schemas.LLMIntentDraft] = None
    session_id: Optional[str] = None


class PromptRequest(APIModel):
    task: str = "intent_extraction"
    query: str = ""
    city: Optional[str] = None
    original_query: Optional[str] = None
    current_route: Optional[Any] = None
    route_summary: Optional[str] = None
    intent_summary: Optional[str] = None
    session_id: Optional[str] = None


class EvalRequest(APIModel):
    case_ids: Optional[list[str]] = None
    limit: Optional[int] = None


class CapabilityQueryRequest(APIModel):
    name: Optional[str] = None


class CapabilityMatchRequest(APIModel):
    query: str = ""
    limit: Optional[int] = None


class CapabilityRouterPromptRequest(APIModel):
    query: str = ""


class ContextEventRequest(APIModel):
    event_type: str
    query: Optional[str] = None
    payload: Optional[dict[str, Any]] = None
    intent: Optional[dict[str, Any]] = None
    route_version: Optional[dict[str, Any]] = None
    diagnostics: Optional[dict[str, Any]] = None


class ContextRouteVersionRequest(APIModel):
    query: Optional[str] = None
    event_type: str = "route_created"
    intent: Optional[dict[str, Any]] = None
    route_version: Optional[dict[str, Any]] = None
    diagnostics: Optional[dict[str, Any]] = None
