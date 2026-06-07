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


def _current_route_intent(current_route: Any = None) -> dict[str, Any]:
    if current_route is None:
        return {}
    if isinstance(current_route, dict):
        value = current_route.get("intent") or {}
        if isinstance(value, dict) and value:
            return value
        stops = current_route.get("stops") or current_route.get("main_stops") or []
        categories: list[str] = []
        if isinstance(stops, list):
            for stop in stops:
                if not isinstance(stop, dict):
                    continue
                poi = stop.get("poi") if isinstance(stop.get("poi"), dict) else {}
                category = poi.get("category")
                if category:
                    categories.append(str(category))
        return {"required_categories": list(dict.fromkeys(categories))} if categories else {}
    value = getattr(current_route, "intent", None)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value if isinstance(value, dict) else {}


def _inherit_current_route_intent(intent: ParsedIntent, current_route: Any = None) -> ParsedIntent:
    base = _current_route_intent(current_route)
    if not base:
        return intent

    modification_text = str(getattr(intent, "modification_query", "") or getattr(intent, "original_query", "") or "")
    replaces_route_type = bool(
        getattr(intent, "required_categories", [])
        and any(token in modification_text for token in ("改成", "换成", "只要", "只想", "不要原来", "重新安排"))
    )

    for field_name in ("preferences", "required_categories", "avoid", "must_include"):
        if field_name == "required_categories" and replaces_route_type:
            continue
        inherited = [str(item) for item in base.get(field_name, []) or [] if item]
        current = [str(item) for item in getattr(intent, field_name, []) or [] if item]
        setattr(intent, field_name, list(dict.fromkeys([*inherited, *current])))

    if getattr(intent, "pace", "normal") == "normal" and base.get("pace") in {"fast", "slow"}:
        intent.pace = str(base["pace"])
    if not getattr(intent, "transport_mode", None) or intent.transport_mode == "mixed":
        inherited_transport = base.get("transport_mode")
        if inherited_transport in {"walking", "metro", "taxi", "mixed"}:
            intent.transport_mode = inherited_transport
    return intent_parser.refresh_intent_derived_fields(intent)


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


def _apply_ordered_query_hints(intent: ParsedIntent, query: str) -> ParsedIntent:
    text = str(query or "")
    stages: list[dict[str, str]] = []
    has_sequence_signal = any(
        token in text
        for token in ("第一站", "先去", "首先", "然后", "接着", "晚饭", "晚餐", "吃完后", "饭后", "最后", "收尾")
    )

    def add_stage(kind: str, label: str) -> None:
        if not any(stage.get("kind") == kind for stage in stages):
            stages.append({"kind": kind, "label": label})

    if "图书馆" in text or "看书" in text or "自习" in text:
        if "library" not in intent.required_categories:
            intent.required_categories.append("library")
        add_stage("library", "图书馆")

    if any(token in text for token in ("清闲", "清净", "安静", "休息", "坐坐", "放松")):
        if "quiet" not in intent.preferences:
            intent.preferences.append("quiet")
        add_stage("quiet_rest", "清闲休息")

    first_food = any(token in text for token in ("先去吃饭", "先吃饭", "第一站吃饭", "首先吃饭"))
    final_food = "最后" in text and any(token in text for token in ("吃饭", "吃饭玩", "吃点"))
    if first_food:
        if "food" not in intent.required_categories:
            intent.required_categories.append("food")
        stages.append({"kind": "food", "label": "先吃饭", "position": "first"})

    if "大学城" in text or "广州大学城" in text:
        if "大学城" not in intent.must_include:
            intent.must_include.append("大学城")
        if "street" not in intent.required_categories:
            intent.required_categories.append("street")
        add_stage("university_area", "大学城")

    if any(token in text for token in ("晚饭", "晚餐", "吃饭", "餐厅")) and not first_food:
        if "food" not in intent.required_categories:
            intent.required_categories.append("food")
        add_stage("food", "晚饭")
    elif final_food:
        if "food" not in intent.required_categories:
            intent.required_categories.append("food")
        stages.append({"kind": "food", "label": "最后吃饭"})

    if any(token in text for token in ("玩", "游玩", "逛玩")):
        if "street" not in intent.required_categories:
            intent.required_categories.append("street")
        stages.append({"kind": "play", "label": "玩", "position": "last" if "最后" in text else ""})

    if "广州塔" in text and "广州塔" not in intent.must_include:
        intent.must_include.append("广州塔")

    if "夜景" in text or "看夜景" in text or "欣赏夜景" in text:
        if "night" not in intent.required_categories:
            intent.required_categories.append("night")
        if "night_view" not in intent.preferences:
            intent.preferences.append("night_view")
        add_stage("night", "夜景")

    if any(token in text for token in ("第一站", "先去", "首先")) and stages:
        stages[0]["position"] = "first"
    if any(token in text for token in ("吃完后", "饭后", "最后", "收尾")) and any(stage["kind"] == "night" for stage in stages):
        for stage in stages:
            if stage["kind"] == "night":
                stage["position"] = "last"

    if has_sequence_signal and len(stages) >= 2:
        intent.ordered_stages = stages
        intent.hard_constraints = list(
            dict.fromkeys([*(getattr(intent, "hard_constraints", []) or []), "ordered_stages"])
        )
    return intent_parser.refresh_intent_derived_fields(intent)


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
        parsed_intent.modification_query = query
        parsed_intent = _inherit_current_route_intent(parsed_intent, current_route)
    intent_parser.apply_modification_hints(parsed_intent, query, current_route=current_route)
    parsed_intent = _apply_ordered_query_hints(parsed_intent, query)
    return parsed_intent


def plan_route_from_intent(
    intent: ParsedIntent,
    use_map_api: bool = False,
    use_amap: bool | None = None,
) -> RouteResponse:
    """Complete route planning from a parsed intent."""
    if use_amap is not None:
        use_map_api = use_amap

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

    ranked = poi_ranker.rank_pois(pois, intent, top_k=60)
    planned = route_planner.plan_route(ranked, intent, amap=use_map_api)
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
        used_amap=use_map_api,
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
    use_map_api: bool = False,
    use_amap: bool | None = None,
    profile: Any = None,
    context_snapshot: Any = None,
) -> tuple[ParsedIntent, RouteResponse]:
    if use_amap is not None:
        use_map_api = use_amap
    inferred_city = city or infer_city_from_route(current_route)
    intent = _parse_intent(
        query,
        city=inferred_city,
        preferences=preferences,
        current_route=current_route,
        original_query=original_query,
    )
    intent.original_query = original_query or query
    if context_snapshot is not None and current_route is None:
        try:
            from services import context_service

            session = getattr(context_snapshot, "session", None)
            intent = context_service.apply_session_context(intent, session)
        except Exception:
            pass
    if profile is not None:
        try:
            from services import context_service

            intent = context_service.apply_profile_bias(intent, profile)
        except Exception:
            pass
    response = plan_route_from_intent(intent, use_map_api=use_map_api)
    return intent, response
