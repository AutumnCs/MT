"""Candidate building for route planning.

This module keeps POI recall, constraint filtering, and ranking in one
observable boundary before route optimization starts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.tool_layer import ToolResult
from core.schemas import POI, ParsedIntent
from services import constraint_checker, model_backends, poi_ranker, poi_retriever


@dataclass
class CandidateBuildResult:
    """POI candidates and trace observations used by route planning."""

    recalled_pois: list[POI] = field(default_factory=list)
    filtered_pois: list[POI] = field(default_factory=list)
    ranked_pois: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    recall_trace: dict[str, Any] = field(default_factory=dict)
    filter_trace: dict[str, Any] = field(default_factory=dict)

    @property
    def recall_sources(self) -> list[str]:
        sources = list(self.recall_trace.get("recall_sources", []) or [])
        if self.filter_trace:
            sources.append("constraint_filter")
        return list(dict.fromkeys(str(item) for item in sources if item))

    def to_trace_dict(self) -> dict[str, Any]:
        return {
            "recalled_count": len(self.recalled_pois),
            "filtered_count": len(self.filtered_pois),
            "ranked_count": len(self.ranked_pois),
            "recall_trace": self.recall_trace,
            "filter_trace": self.filter_trace,
            "recall_sources": self.recall_sources,
        }


def _ids(pois: list[POI], limit: int = 30) -> list[str]:
    return [str(getattr(poi, "id", "")) for poi in pois[:limit] if getattr(poi, "id", None)]


def _ranking_trace(ranked: list[dict[str, Any]], filtered_count: int, top_k: int) -> dict[str, Any]:
    rerank_backend = model_backends.rerank_backend_info()
    top_items = list(ranked[: min(8, len(ranked))])
    final_scores = [float(item.get("final_score", 0.0) or 0.0) for item in ranked]
    reasons = [str(item.get("recommend_reason") or "") for item in top_items if item.get("recommend_reason")]
    breakdown_keys = [
        "preference_match_score",
        "semantic_score",
        "query_alignment_score",
        "category_match_score",
        "rating_score",
        "budget_score",
        "time_suitability_score",
        "queue_penalty",
        "crowd_penalty",
        "price_penalty",
        "modification_penalty",
    ]
    breakdown_avg: dict[str, float] = {}
    for key in breakdown_keys:
        values = [float((item.get("score_breakdown") or {}).get(key, 0.0) or 0.0) for item in top_items]
        if values:
            breakdown_avg[key] = round(sum(values) / len(values), 4)
    score_span = 0.0
    if final_scores:
        score_span = round(max(final_scores) - min(final_scores[: min(len(final_scores), top_k)]), 4)
    return {
        "source": "poi_rerank",
        "input_count": filtered_count,
        "output_count": len(ranked),
        "top_k": top_k,
        "selected_poi_ids": [str(getattr(item.get("poi"), "id", "")) for item in top_items if item.get("poi") is not None],
        "top_final_score": round(max(final_scores), 4) if final_scores else 0.0,
        "score_span": score_span,
        "top_score_breakdown_avg": breakdown_avg,
        "top_reasons": reasons[:5],
        "rerank_backend": rerank_backend.get("backend"),
        "rerank_model": rerank_backend.get("model"),
        "rerank_active": bool(rerank_backend.get("active")),
    }


def build_candidates(intent: ParsedIntent, *, top_k: int) -> CandidateBuildResult:
    recalled, recall_trace = poi_retriever.retrieve_pois_with_trace(intent)
    recall_status = "ok" if recalled else "empty"
    recall_result = ToolResult(
        tool="poi_recall",
        status=recall_status,
        confidence=0.82 if recalled else 0.0,
        payload=recall_trace,
        evidence=[
            f"{recall_trace.get('selected_count', 0)} POIs selected from recall",
            f"{recall_trace.get('recall_lane_count', 0)} active recall lanes",
        ],
        noise_risk="low",
        used_by=["retrieval", "ranking", "candidate_building"],
        fallback_used=bool(recall_trace.get("used_city_fallback") or recall_trace.get("fallback_expanded")),
        metadata={
            "city": getattr(intent, "city", None),
            "top_k": top_k,
        },
    )

    if not recalled:
        return CandidateBuildResult(
            recalled_pois=[],
            filtered_pois=[],
            ranked_pois=[],
            tool_results=[recall_result],
            recall_trace=recall_trace,
        )

    filtered = constraint_checker.filter_pois_by_constraints(recalled, intent)
    removed_count = max(0, len(recalled) - len(filtered))
    filter_trace = {
        "source": "constraint_filter",
        "input_count": len(recalled),
        "output_count": len(filtered),
        "removed_count": removed_count,
        "avoid": list(getattr(intent, "avoid", []) or []),
        "budget": getattr(intent, "budget", None),
        "selected_poi_ids": _ids(filtered),
    }
    filter_result = ToolResult(
        tool="constraint_filter",
        status="ok" if filtered else "empty",
        confidence=0.9 if filtered else 0.0,
        payload=filter_trace,
        evidence=[f"{removed_count} POIs removed by hard constraints"],
        noise_risk="low",
        used_by=["retrieval", "ranking", "candidate_building"],
        fallback_used=False,
        metadata={"city": getattr(intent, "city", None)},
    )

    ranked = poi_ranker.rank_pois(filtered, intent, top_k=top_k) if filtered else []
    ranking_trace = _ranking_trace(ranked, len(filtered), top_k) if ranked else {
        "source": "poi_rerank",
        "input_count": len(filtered),
        "output_count": 0,
        "top_k": top_k,
        "selected_poi_ids": [],
    }
    ranking_result = ToolResult(
        tool="poi_rerank",
        status="ok" if ranked else "empty",
        confidence=0.88 if ranked else 0.0,
        payload=ranking_trace,
        evidence=[
            f"{ranking_trace.get('output_count', 0)} POIs kept after rerank",
            f"top_final_score={ranking_trace.get('top_final_score', 0.0)}",
        ],
        noise_risk=str(recall_trace.get("noise_risk") or "low"),
        used_by=["ranking", "candidate_building", "planning"],
        fallback_used=False,
        metadata={"city": getattr(intent, "city", None), "top_k": top_k},
    )
    return CandidateBuildResult(
        recalled_pois=recalled,
        filtered_pois=filtered,
        ranked_pois=ranked,
        tool_results=[recall_result, filter_result, ranking_result],
        recall_trace=recall_trace,
        filter_trace=filter_trace,
    )
