"""Structured state shared by route workflow stages.

The coordinator is intentionally narrow: it records what happened and decides
whether the pipeline should continue, clarify, repair, or fail. Planning,
retrieval, ranking, and explanation stay in their own services.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .planning import ExecutionPlan
from .tool_layer import ToolResult


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class CoordinatorAction(str, Enum):
    CONTINUE = "continue"
    ASK_CLARIFICATION = "ask_clarification"
    EXPAND_RETRIEVAL = "expand_retrieval"
    RERANK = "rerank"
    REPLAN = "replan"
    REPAIR = "repair"
    EXPLAIN = "explain"
    FAIL_WITH_REASON = "fail_with_reason"


class CoordinatorDecision(BaseModel):
    """One controlled coordinator decision."""

    model_config = ConfigDict(extra="allow")

    stage: str
    action: CoordinatorAction = CoordinatorAction.CONTINUE
    reason: str = ""
    blocking: bool = False
    required_action: Optional[str] = None
    explain_to_user: bool = False
    checks: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now)


class QualityReport(BaseModel):
    """Normalized route-quality report used by the coordinator and trace."""

    model_config = ConfigDict(extra="allow")

    status: str = "unknown"
    alignment_score: float = 0.0
    hard_issues: list[str] = Field(default_factory=list)
    soft_warnings: list[str] = Field(default_factory=list)
    repair_suggestions: list[str] = Field(default_factory=list)
    route_stats: dict[str, Any] = Field(default_factory=dict)
    source: str = "route_verifier"

    @classmethod
    def from_verifier(
        cls,
        quality: dict[str, Any] | None,
        critique: dict[str, Any] | None = None,
        route_stats: dict[str, Any] | None = None,
    ) -> "QualityReport":
        quality = quality or {}
        critique = critique or {}
        score = float(quality.get("alignment_score", 0.0) or 0.0)
        gaps = [str(item) for item in critique.get("critical_gaps", quality.get("gaps", [])) or []]
        warnings = [str(item) for item in critique.get("warnings", quality.get("warnings", [])) or []]
        if critique.get("decision") == "replan" or score < 0.62:
            status = "needs_replan"
        elif critique.get("decision") == "repair" or gaps:
            status = "needs_repair"
        elif warnings:
            status = "pass_with_warning"
        else:
            status = "pass"
        return cls(
            status=status,
            alignment_score=score,
            hard_issues=gaps,
            soft_warnings=warnings,
            repair_suggestions=[str(item) for item in critique.get("recommendations", []) or []],
            route_stats=route_stats or {},
        )


class RouteState(BaseModel):
    """End-to-end state snapshot for one route request."""

    model_config = ConfigDict(extra="allow")

    request_id: str = Field(default_factory=lambda: uuid4().hex)
    query: str = ""
    original_query: Optional[str] = None
    session_id: Optional[str] = None
    task_hint: str = "intent_extraction"
    city: Optional[str] = None
    parse_source: Optional[str] = None
    intent_confidence: Optional[float] = None
    intent: dict[str, Any] = Field(default_factory=dict)
    retrieval: dict[str, Any] = Field(default_factory=dict)
    ranking: dict[str, Any] = Field(default_factory=dict)
    planning: dict[str, Any] = Field(default_factory=dict)
    execution_plan: Optional[ExecutionPlan] = None
    tool_results: list[ToolResult] = Field(default_factory=list)
    quality_report: Optional[QualityReport] = None
    explanation: Optional[str] = None
    decision_log: list[CoordinatorDecision] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)

    def add_decision(self, decision: CoordinatorDecision) -> None:
        self.decision_log.append(decision)
        self.updated_at = _now()

    def add_error(self, message: str) -> None:
        if message:
            self.errors.append(message)
            self.updated_at = _now()

    def set_execution_plan(self, plan: ExecutionPlan) -> None:
        self.execution_plan = plan
        self.updated_at = _now()

    def add_tool_result(self, result: ToolResult) -> None:
        self.tool_results.append(result)
        self.updated_at = _now()

    def to_trace_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
