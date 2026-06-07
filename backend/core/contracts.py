"""Shared structured contracts for orchestration and routing."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict


class RouteTaskHint(str, Enum):
    """Canonical task hints used by the LLM prompt router."""

    INTENT_EXTRACTION = "intent_extraction"
    ROUTE_MODIFICATION = "route_modification"
    CAPABILITY_ROUTER = "capability_router"
    ROUTE_EXPLANATION = "route_explanation"


class CapabilityMatchResult(BaseModel):
    """Structured capability-routing result."""

    model_config = ConfigDict(extra="allow")

    name: str
    category: Optional[str] = None
    description: Optional[str] = None
    score: float = 0.0
    confidence: float = 0.0
    matched_signals: list[str] = Field(default_factory=list)
    matched_examples: list[str] = Field(default_factory=list)
    priority: int = 0
    min_confidence: float = 0.65
    raw: dict[str, Any] = Field(default_factory=dict)


class ClarificationDecision(BaseModel):
    """Structured lightweight clarification request."""

    model_config = ConfigDict(extra="allow")

    question: str
    options: list[str] = Field(default_factory=list)
    reason: Optional[str] = None


class RouteDiagnostics(BaseModel):
    """Structured route-generation diagnostics for UI and debug views."""

    model_config = ConfigDict(extra="allow")

    task_hint: RouteTaskHint = RouteTaskHint.INTENT_EXTRACTION
    parse_source: str = "local"
    route_capability: Optional[CapabilityMatchResult] = None
    capability_matches: list[CapabilityMatchResult] = Field(default_factory=list)
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    clarification_reason: Optional[str] = None
    used_amap: bool = False
