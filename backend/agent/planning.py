"""Execution planning contracts for the controlled route agent."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class ToolCallPlan(BaseModel):
    """One optional tool the coordinator allows for the current request."""

    model_config = ConfigDict(extra="allow")

    tool: str
    reason: str = ""
    enabled: bool = True
    blocking: bool = False
    priority: int = 50
    used_by: list[str] = Field(default_factory=list)
    max_items: Optional[int] = None
    budget_units: int = 1
    prefer_external: bool = False
    fallback: str = "local"


class ToolSkip(BaseModel):
    """Auditable reason for not invoking an optional tool."""

    model_config = ConfigDict(extra="allow")

    tool: str
    reason: str
    risk: str = "low"


class DataRequirement(BaseModel):
    """One typed data need for the current route request."""

    model_config = ConfigDict(extra="allow")

    name: str
    reason: str = ""
    required: bool = True
    source: str = "local"
    used_by: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    max_items: Optional[int] = None
    fallback: str = "skip"


class PlanNode(BaseModel):
    """One execution-graph node for the bounded workflow plan."""

    model_config = ConfigDict(extra="allow")

    node_id: str
    kind: str = "step"
    label: str
    depends_on: list[str] = Field(default_factory=list)
    status: str = "pending"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionPlan(BaseModel):
    """Bounded plan for a route-planning request.

    The plan is intentionally small and replayable. It tells the pipeline which
    deterministic steps must run and which optional tools are allowed, skipped,
    or budget-limited for this request.
    """

    model_config = ConfigDict(extra="allow")

    plan_id: str = Field(default_factory=lambda: uuid4().hex)
    strategy: str = "fixed_pipeline_with_optional_tools"
    required_steps: list[str] = Field(default_factory=list)
    required_data: list[DataRequirement] = Field(default_factory=list)
    optional_data: list[DataRequirement] = Field(default_factory=list)
    skipped_data: list[ToolSkip] = Field(default_factory=list)
    optional_tools: list[ToolCallPlan] = Field(default_factory=list)
    skipped_tools: list[ToolSkip] = Field(default_factory=list)
    dag_mode: str = "bounded_dag"
    dag_nodes: list[PlanNode] = Field(default_factory=list)
    tool_budget: int = 2
    max_repair_rounds: int = 1
    quality_gates: dict[str, Any] = Field(default_factory=dict)
    fallback_policy: dict[str, Any] = Field(default_factory=dict)
    decision_basis: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now)

    def enabled_tool(self, tool_name: str) -> ToolCallPlan | None:
        for item in self.optional_tools:
            if item.tool == tool_name and item.enabled:
                return item
        return None

    def enabled_tool_names(self) -> list[str]:
        return [item.tool for item in self.optional_tools if item.enabled]

    def skipped_tool_names(self) -> list[str]:
        return [item.tool for item in self.skipped_tools]

    def node(self, node_id: str) -> PlanNode | None:
        for item in self.dag_nodes:
            if item.node_id == node_id:
                return item
        return None

    def mark_node_status(self, node_id: str, status: str, **metadata: Any) -> None:
        item = self.node(node_id)
        if item is None:
            return
        item.status = status
        if metadata:
            item.metadata = {**dict(item.metadata or {}), **metadata}

    def ready_nodes(self) -> list[PlanNode]:
        ready: list[PlanNode] = []
        for item in self.dag_nodes:
            if item.status != "pending":
                continue
            if all((self.node(dep) and self.node(dep).status == "completed") for dep in item.depends_on):
                ready.append(item)
        return ready

    def status_summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for item in self.dag_nodes:
            counts[item.status] = counts.get(item.status, 0) + 1
        return {
            "mode": self.dag_mode,
            "node_count": len(self.dag_nodes),
            "status_counts": counts,
            "ready_nodes": [item.node_id for item in self.ready_nodes()],
        }
