"""Route service entrypoint for the route-planning pipeline.

The production path is LLM-first. Local parsing is only used when the test
harness explicitly disables LLM parsing via `LLM_INTENT_DISABLE_LLM=1`.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from core import capability_registry, intent_parser, llm_intent_client
from core.contracts import ClarificationDecision, RouteDiagnostics, RouteTaskHint
from core.route_context import infer_city_from_route
from core.schemas import ParsedIntent, RouteResponse
from services import constraint_checker, poi_ranker, poi_retriever, response_generator, route_planner


class RoutePlanningError(Exception):
    def __init__(self, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail


def _task_hint(current_route: Any = None) -> str:
    return RouteTaskHint.ROUTE_MODIFICATION.value if current_route is not None else RouteTaskHint.INTENT_EXTRACTION.value


def _need_clarification(intent: ParsedIntent, query: str, current_route: Any = None) -> ClarificationDecision | None:
    text = (query or "").strip()
    strong_signals = len(intent.preferences) + len(intent.required_categories) + len(intent.must_include)
    if intent.budget is not None:
        strong_signals += 1
    if intent.start_time or intent.end_time:
        strong_signals += 1
    if intent.start_location:
        strong_signals += 1

    vague_markers = ("随便", "看看", "逛逛", "安排一下", "推荐一下", "帮我搞", "差不多就行", "都可以", "无所谓", "不知道")
    is_vague = any(marker in text for marker in vague_markers)

    if current_route is None:
        if strong_signals == 0 and (len(text) <= 20 or is_vague):
            return ClarificationDecision(
                question="你更想先偏向哪种路线？",
                options=["美食为主", "拍照为主", "轻松逛街"],
                reason="当前需求太宽泛，先确认主偏好可以让路线更准。",
            )
        if strong_signals == 1 and is_vague:
            return ClarificationDecision(
                question="你更在意哪一个？",
                options=["更近一点", "少排队一点", "预算更低"],
                reason="当前需求信息较少，补一个最关键的约束会更稳。",
            )
        return None

    if strong_signals == 0 and (len(text) <= 18 or is_vague):
        return ClarificationDecision(
            question="你更想往哪个方向调整？",
            options=["更近一点", "更便宜一点", "少排队一点"],
            reason="修改需求还比较泛，先确认一个调整方向。",
        )
    if strong_signals == 1 and is_vague:
        return ClarificationDecision(
            question="你更想优先改什么？",
            options=["更轻松", "更省钱", "更少排队"],
            reason="当前修改目标不够明确，先补一个优先级。",
        )
    return None


def _parse_intent(
    query: str,
    *,
    city: str | None = None,
    preferences: list[str] | None = None,
    current_route: Any = None,
    original_query: str | None = None,
) -> ParsedIntent:
    hint = _task_hint(current_route)
    parsed_intent = llm_intent_client.parse_intent_with_llm(
        query,
        city,
        task_hint=hint,
        original_query=original_query,
        current_route=current_route,
    )
    if parsed_intent is None and os.getenv("LLM_INTENT_DISABLE_LLM") == "1":
        parsed_intent = intent_parser.parse_intent(query, city)
    if parsed_intent is None:
        raise RoutePlanningError(503, "LLM ????????????")

    if preferences:
        intent_parser.apply_ui_preferences(parsed_intent, preferences)
    if current_route is not None:
        parsed_intent.current_route = current_route
    intent_parser.apply_modification_hints(parsed_intent, query, current_route=current_route)
    return parsed_intent


def plan_route_from_intent(intent: ParsedIntent, use_amap: bool = False) -> RouteResponse:
    """Complete route planning from a parsed intent."""

    clarification = _need_clarification(intent, getattr(intent, "original_query", "") or "", getattr(intent, "current_route", None))
    if clarification:
        diagnostics = RouteDiagnostics(
            task_hint=RouteTaskHint.ROUTE_MODIFICATION if getattr(intent, "current_route", None) is not None else RouteTaskHint.INTENT_EXTRACTION,
            parse_source=getattr(intent, "parse_source", "local"),
            clarification_needed=True,
            clarification_question=clarification.question,
            clarification_reason=clarification.reason,
        )
        return response_generator.generate_clarification_response(
            intent,
            clarification.question,
            clarification.options,
            reason=clarification.reason,
            diagnostics=diagnostics,
        )

    check = constraint_checker.validate_intent(intent)
    if not check["valid"]:
        raise RoutePlanningError(422, "?".join(check["errors"]))

    pois = poi_retriever.retrieve_pois(intent)
    if not pois:
        raise RoutePlanningError(404, "???????????? POI??????????????????")

    pois = constraint_checker.filter_pois_by_constraints(pois, intent)
    if not pois:
        raise RoutePlanningError(404, "??????????????????????????????")

    ranked = poi_ranker.rank_pois(pois, intent)
    planned = route_planner.plan_route(ranked, intent, amap=use_amap)
    explanation = response_generator.generate_route_explanation(intent, planned.get("main", []))
    query_text = getattr(intent, "original_query", "") or ""
    capability_matches = capability_registry.match_capabilities(query_text, limit=3)
    route_capability = capability_registry.route_capability(query_text)
    diagnostics = RouteDiagnostics(
        task_hint=RouteTaskHint.ROUTE_MODIFICATION if getattr(intent, "current_route", None) is not None else RouteTaskHint.INTENT_EXTRACTION,
        parse_source=getattr(intent, "parse_source", "local"),
        route_capability=route_capability,
        capability_matches=capability_matches,
        clarification_needed=False,
        used_amap=use_amap,
    )
    return response_generator.generate_response(
        intent=intent,
        ranked_pois=ranked,
        planned_route=planned,
        explanation=explanation,
        diagnostics=diagnostics,
    )


def plan_route(
    query: str,
    *,
    city: str | None = None,
    preferences: list[str] | None = None,
    current_route: Any = None,
    original_query: str | None = None,
    use_amap: bool = False,
    profile: Any = None,
) -> tuple[ParsedIntent, RouteResponse]:
    inferred_city = city or infer_city_from_route(current_route)
    intent = _parse_intent(
        query,
        city=inferred_city,
        preferences=preferences,
        current_route=current_route,
        original_query=original_query,
    )
    intent.original_query = original_query or query
    if profile is not None:
        try:
            from services import context_service

            intent = context_service.apply_profile_bias(intent, profile)
        except Exception:
            pass
    response = plan_route_from_intent(intent, use_amap=use_amap)
    return intent, response
