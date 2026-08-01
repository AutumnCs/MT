"""Tool-layer contracts shared by route workflow tools."""

from __future__ import annotations

from datetime import datetime
from time import perf_counter
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class ToolResult(BaseModel):
    """Normalized output from a route workflow tool."""

    model_config = ConfigDict(extra="allow")

    tool: str
    status: str = "ok"
    confidence: float = 0.0
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    noise_risk: str = "unknown"
    used_by: list[str] = Field(default_factory=list)
    latency_ms: int = 0
    fallback_used: bool = False
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now)


class ToolRegistry:
    """Tiny synchronous registry for deterministic route tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., ToolResult]] = {}

    def register(self, name: str, fn: Callable[..., ToolResult]) -> None:
        self._tools[name] = fn

    def has(self, name: str) -> bool:
        return name in self._tools

    def run(self, name: str, **kwargs: Any) -> ToolResult:
        fn = self._tools.get(name)
        if fn is None:
            return ToolResult(
                tool=name,
                status="skipped",
                confidence=0.0,
                error="tool_not_registered",
                noise_risk="low",
                metadata={"reason": "No implementation is registered for this tool."},
            )
        started = perf_counter()
        try:
            result = fn(**kwargs)
        except Exception as exc:  # defensive tool boundary
            return ToolResult(
                tool=name,
                status="failed",
                confidence=0.0,
                error=str(exc),
                noise_risk="medium",
                latency_ms=int((perf_counter() - started) * 1000),
                metadata={"exception_type": exc.__class__.__name__},
            )
        if result.latency_ms <= 0:
            result.latency_ms = int((perf_counter() - started) * 1000)
        return result
