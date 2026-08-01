"""Structured context models for session state, profile, and route history."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel as PydanticBaseModel, ConfigDict, Field


def _now() -> str:
    return datetime.now().isoformat()


class BaseModel(PydanticBaseModel):
    class Config:
        extra = "allow"

    if not hasattr(PydanticBaseModel, "model_dump"):
        def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            kwargs.pop("mode", None)
            return self.dict(*args, **kwargs)

    if not hasattr(PydanticBaseModel, "model_validate"):
        @classmethod
        def model_validate(cls, value: Any) -> Any:
            if isinstance(value, cls):
                return value
            return cls.parse_obj(value)


class SessionContext(BaseModel):
    """Current-turn and current-session state."""

    model_config = ConfigDict(extra="allow")

    session_id: str
    mode: str = "idle"
    city: Optional[str] = None
    current_route_version_id: Optional[str] = None
    current_route_title: Optional[str] = None
    current_route_summary: Optional[str] = None
    last_query: Optional[str] = None
    last_intent_summary: Optional[dict[str, Any]] = None
    last_task_hint: Optional[str] = None
    clarification_pending: bool = False
    updated_at: str = Field(default_factory=_now)


class BehaviorEvent(BaseModel):
    """A single user/system event captured for replay and profile projection."""

    model_config = ConfigDict(extra="allow")

    event_id: str
    session_id: str
    event_type: str
    created_at: str = Field(default_factory=_now)
    query: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    route_version_id: Optional[str] = None
    intent_summary: Optional[dict[str, Any]] = None
    diagnostics: Optional[dict[str, Any]] = None


class RouteVersionRecord(BaseModel):
    """A persisted snapshot of a route version."""

    model_config = ConfigDict(extra="allow")

    version_id: str
    session_id: str
    created_at: str = Field(default_factory=_now)
    event_type: str = "route_created"
    title: Optional[str] = None
    summary: Optional[str] = None
    query: Optional[str] = None
    intent_summary: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    route: dict[str, Any] = Field(default_factory=dict)


class UserProfile(BaseModel):
    """Longer-term user preference projection."""

    model_config = ConfigDict(extra="allow")

    session_id: str
    home_city: Optional[str] = None
    frequent_cities: list[str] = Field(default_factory=list)
    preferred_categories: list[str] = Field(default_factory=list)
    preferred_preferences: list[str] = Field(default_factory=list)
    avoid_preferences: list[str] = Field(default_factory=list)
    preferred_pace: Optional[str] = None
    preferred_transport_mode: Optional[str] = None
    budget_band: Optional[str] = None
    companion_types: list[str] = Field(default_factory=list)
    city_counts: dict[str, int] = Field(default_factory=dict)
    category_counts: dict[str, int] = Field(default_factory=dict)
    preference_counts: dict[str, int] = Field(default_factory=dict)
    avoid_counts: dict[str, int] = Field(default_factory=dict)
    behavior_counts: dict[str, int] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    updated_at: str = Field(default_factory=_now)


class ContextSnapshot(BaseModel):
    """Combined view used by API and debug tools."""

    model_config = ConfigDict(extra="allow")

    session: SessionContext
    profile: UserProfile
    recent_events: list[BehaviorEvent] = Field(default_factory=list)
    route_versions: list[RouteVersionRecord] = Field(default_factory=list)


class WorkflowStageSnapshot(BaseModel):
    """One stage in the route workflow trace."""

    model_config = ConfigDict(extra="allow")

    stage: str
    status: str = "done"
    summary: Optional[str] = None
    checks: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)


class RouteWorkflowTrace(BaseModel):
    """Unified end-to-end trace for one route request."""

    model_config = ConfigDict(extra="allow")

    trace_id: str = Field(default_factory=lambda: uuid4().hex)
    session_id: Optional[str] = None
    created_at: str = Field(default_factory=_now)
    task_hint: Optional[str] = None
    query: Optional[str] = None
    city: Optional[str] = None
    parse_source: Optional[str] = None
    intent_confidence: Optional[float] = None
    decision: str = "accept"
    selected_variant_name: Optional[str] = None
    selected_variant_source: Optional[str] = None
    alignment_score: float = 0.0
    should_replan: bool = False
    stages: list[WorkflowStageSnapshot] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    checks: list[str] = Field(default_factory=list)
    route_quality: dict[str, Any] = Field(default_factory=dict)
    route_critique: dict[str, Any] = Field(default_factory=dict)
    workflow_guard: dict[str, Any] = Field(default_factory=dict)
    coordinator: dict[str, Any] = Field(default_factory=dict)
    execution_plan: dict[str, Any] = Field(default_factory=dict)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    feedback_targets: list[str] = Field(default_factory=lambda: ["session", "profile", "route_history"])

