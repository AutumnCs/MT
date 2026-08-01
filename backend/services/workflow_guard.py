"""Workflow guardrails for route planning.

This module keeps the handoff between interpretation, planning, critique and
explanation explicit so the agent cannot silently skip a stage.
"""

from __future__ import annotations

from typing import Any

from core.schemas import ParsedIntent


def _has_items(value: Any) -> bool:
    return bool(value)


def validate_route_workflow(
    intent: ParsedIntent,
    planned_route: dict[str, Any],
    route_quality: dict[str, Any] | None = None,
    route_critique: dict[str, Any] | None = None,
    diagnostics: Any = None,
) -> dict[str, Any]:
    """Return a compact guardrail report for the route workflow."""

    route_quality = route_quality or {}
    route_critique = route_critique or {}
    issues: list[str] = []
    checks: list[str] = []

    clarification_needed = bool(getattr(diagnostics, "clarification_needed", False))
    if clarification_needed:
        checks.append("clarification_requested")
        if _has_items(planned_route.get("main")):
            issues.append("clarification_requested_but_route_generated")
    else:
        checks.append("route_generation_allowed")

    main_stops = planned_route.get("main") or []
    variants = planned_route.get("variants") or []
    selected_variant_name = planned_route.get("selected_variant_name")
    selected_variant_source = planned_route.get("selected_variant_source")

    if _has_items(main_stops):
        checks.append("main_route_present")
    else:
        issues.append("missing_main_route")

    if _has_items(variants):
        checks.append("candidate_variants_present")
    else:
        issues.append("missing_candidate_variants")

    if selected_variant_name:
        checks.append("selected_variant_named")
    else:
        issues.append("missing_selected_variant_name")

    if route_quality:
        checks.append("route_quality_reported")
        score = float(route_quality.get("alignment_score", 0.0) or 0.0)
        if score < 0.55 and not route_critique.get("should_replan"):
            issues.append("low_alignment_without_replan")
        if route_critique and abs(float(route_critique.get("alignment_score", score) or score) - score) > 1e-6:
            issues.append("quality_and_critique_score_mismatch")
    else:
        issues.append("missing_route_quality")

    if route_critique:
        checks.append("route_critique_reported")
        if route_critique.get("decision") in {"repair", "replan"}:
            checks.append("critique_requests_fix")
        if route_critique.get("should_replan") and selected_variant_source == "main":
            issues.append("should_replan_but_main_kept")
    else:
        issues.append("missing_route_critique")

    expected_confidence = getattr(intent, "intent_confidence", None)
    if expected_confidence is not None:
        checks.append("intent_confidence_available")

    return {
        "ok": not issues,
        "stage": "clarification" if clarification_needed else "planning",
        "checks": checks,
        "issues": issues,
        "selected_variant_name": selected_variant_name,
        "selected_variant_source": selected_variant_source,
        "should_replan": bool(route_critique.get("should_replan", False)),
        "alignment_score": float(route_quality.get("alignment_score", 0.0) or 0.0),
    }
