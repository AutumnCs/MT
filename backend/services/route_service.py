"""Route service entrypoint for the route-planning pipeline.

The production path is LLM-first. Local parsing is only used when the test
harness explicitly disables LLM parsing via `LLM_INTENT_DISABLE_LLM=1`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any, Optional

from agent import ExecutionPlan, IntentRepairAgent, RouteCoordinator, ToolResult
from core import capability_registry, intent_parser, llm_intent_client
from core.contracts import ClarificationDecision, RouteDiagnostics, RouteTaskHint
from core.intent_lexicon import INTENT_LEXICON
from core.route_policy import CATEGORY_TARGETS, EXPERIENCE_CATEGORIES, ROUTE_POLICY, SUPPORT_CATEGORIES
from core.route_context import infer_city_from_route
from core.schemas import ParsedIntent, RouteResponse
from services import candidate_builder, constraint_checker, map_service, response_generator, route_planner, route_tools, route_verifier, workflow_guard

_COORDINATOR = RouteCoordinator()
_INTENT_REPAIR_AGENT = IntentRepairAgent()


class RoutePlanningError(Exception):
    def __init__(self, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail


@dataclass
class RouteAttempt:
    """One complete retrieval -> planning -> validation attempt."""

    intent: ParsedIntent
    pois: list[Any]
    ranked: list[dict[str, Any]]
    planned: dict[str, Any]
    quality: dict[str, Any]
    critique: dict[str, Any]
    guardrail: dict[str, Any]
    tool_results: list[ToolResult] = field(default_factory=list)

    @property
    def route_stats(self) -> dict[str, Any]:
        return _route_stats(self.planned.get("main", []))


def _task_hint(current_route: Any = None) -> str:
    return RouteTaskHint.ROUTE_MODIFICATION.value if current_route is not None else RouteTaskHint.INTENT_EXTRACTION.value


def _env_enabled(name: str, default: str = "1") -> bool:
    return str(os.getenv(name, default)).strip().lower() not in {"0", "false", "no", "off"}


def _context_opted_out(query: str) -> bool:
    text = str(query or "").lower()
    opt_out_terms = [
        "\u4e0d\u7528\u53c2\u8003",
        "\u4e0d\u8981\u53c2\u8003",
        "\u4e0d\u7528\u770b\u6211\u4e4b\u524d",
        "\u4e0d\u770b\u6211\u4e4b\u524d",
        "\u5ffd\u7565\u6211\u7684\u504f\u597d",
        "\u4e0d\u53c2\u8003\u6211\u7684\u504f\u597d",
        "ignore my preferences",
        "ignore my history",
        "ignore history",
    ]
    return any(term in text for term in opt_out_terms)


def _intent_confidence(intent: ParsedIntent, query: str, current_route: Any = None) -> float:
    """Estimate whether the local semantic bridge is confident enough to skip LLM."""

    weights = ROUTE_POLICY["intent_confidence"]
    score = 0.0
    if getattr(intent, "city", None):
        score += float(weights["city_bonus"])
    score += min(0.24, float(weights["required_category_bonus"]) * len(getattr(intent, "required_categories", []) or []))
    score += min(0.24, float(weights["preference_bonus"]) * len(getattr(intent, "preferences", []) or []))
    score += min(0.18, float(weights["avoid_bonus"]) * len(getattr(intent, "avoid", []) or []))
    if getattr(intent, "budget", None) is not None:
        score += float(weights["budget_bonus"])
    if getattr(intent, "start_time", None) or getattr(intent, "end_time", None):
        score += float(weights["time_bonus"])
    if getattr(intent, "start_location", None):
        score += float(weights["start_location_bonus"])
    if getattr(intent, "pace", "normal") != "normal":
        score += float(weights["pace_bonus"])
    if getattr(intent, "must_include", None):
        score += float(weights["must_include_bonus"])
    if current_route is not None:
        score += float(weights["current_route_bonus"])
    if getattr(intent, "required_categories", None) and getattr(intent, "preferences", None):
        score += float(weights["mixed_signal_bonus"])
    if len(getattr(intent, "preferences", []) or []) >= 3:
        score += float(weights["mixed_signal_bonus"])
    if len(getattr(intent, "required_categories", []) or []) >= 2:
        score += float(weights["multi_category_bonus"])

    unresolved = len(getattr(intent, "unclassified_clues", []) or [])
    score -= min(0.18, unresolved * float(weights["unclassified_penalty"]))

    text = str(query or "").strip()
    if len(text) > 48 and len(getattr(intent, "required_categories", []) or []) + len(getattr(intent, "preferences", []) or []) <= 1:
        score -= float(weights["long_query_penalty"])

    return max(0.0, min(1.0, score))


def _fast_gate_threshold(current_route: Any = None) -> float:
    raw = os.getenv("LLM_INTENT_FAST_GATE_THRESHOLD")
    if raw:
        try:
            return max(0.0, min(1.0, float(raw)))
        except ValueError:
            pass
    return float(ROUTE_POLICY["fast_gate_threshold"]["modify" if current_route is not None else "default"])


def _current_route_intent(current_route: Any = None) -> dict[str, Any]:
    if current_route is None:
        return {}
    if isinstance(current_route, dict):
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
        value = current_route.get("intent") or {}
        if isinstance(value, dict) and value:
            existing_required = [str(item) for item in value.get("required_categories", []) or [] if item]
            if existing_required:
                merged = dict(value)
                if categories:
                    merged["covered_categories"] = list(dict.fromkeys(categories))
                return merged
            if categories:
                merged = dict(value)
                merged["required_categories"] = list(dict.fromkeys(categories))
                return merged
            return value
        return {"required_categories": list(dict.fromkeys(categories))} if categories else {}
    value = getattr(current_route, "intent", None)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value if isinstance(value, dict) else {}


def _inherit_current_route_intent(
    intent: ParsedIntent,
    current_route: Any = None,
    *,
    route_autofilled: bool = False,
) -> ParsedIntent:
    base = _current_route_intent(current_route)
    if not base:
        return intent

    if not getattr(intent, "city", None) and base.get("city"):
        intent.city = str(base.get("city"))

    modification_text = str(getattr(intent, "modification_query", "") or getattr(intent, "original_query", "") or "")
    replaces_route_type = bool(
        getattr(intent, "required_categories", [])
        and any(token in modification_text for token in ("鏀规垚", "鎹㈡垚", "鍙", "鍙兂", "涓嶈鍘熸潵", "閲嶆柊瀹夋帓"))
    )

    for field_name in ("preferences", "required_categories", "avoid", "must_include"):
        if field_name == "required_categories" and replaces_route_type:
            continue
        inherited = [str(item) for item in base.get(field_name, []) or [] if item]
        current = [str(item) for item in getattr(intent, field_name, []) or [] if item]
        setattr(intent, field_name, list(dict.fromkeys([*inherited, *current])))

    inherited_min_counts = base.get("category_min_counts") if isinstance(base, dict) else None
    if isinstance(inherited_min_counts, dict):
        current_min_counts = dict(getattr(intent, "category_min_counts", {}) or {})
        for category, value in inherited_min_counts.items():
            try:
                current_min_counts[str(category)] = max(int(current_min_counts.get(str(category), 0) or 0), int(value))
            except (TypeError, ValueError):
                continue
        intent.category_min_counts = current_min_counts

    inherited_caps = base.get("category_caps") if isinstance(base, dict) else None
    if isinstance(inherited_caps, dict):
        current_caps = dict(getattr(intent, "category_caps", {}) or {})
        for category, value in inherited_caps.items():
            try:
                value_int = int(value)
            except (TypeError, ValueError):
                continue
            category = str(category)
            current = current_caps.get(category)
            if current is None:
                current_caps[category] = value_int
            else:
                try:
                    current_caps[category] = min(int(current), value_int)
                except (TypeError, ValueError):
                    current_caps[category] = value_int
        intent.category_caps = current_caps

    current_required = [str(item) for item in getattr(intent, "required_categories", []) or [] if item]
    base_required = [str(item) for item in base.get("required_categories", []) or [] if item]
    base_required = _support_category_trimmed_base_required(base_required, modification_text)
    if base_required and not replaces_route_type and not _has_explicit_category_request(modification_text):
        intent.required_categories = list(dict.fromkeys(base_required))
        current_required = list(intent.required_categories)
    if base_required and len(current_required) > len(base_required) + 2:
        semantic_scores = {
            str(category): float(score)
            for category, score in (getattr(intent, "semantic_scores", {}) or {}).items()
            if category
        }
        top_score = max((float(score) for score in semantic_scores.values()), default=0.0)
        threshold = max(0.9, top_score - 0.04)
        narrowed: list[str] = []
        for category in base_required:
            if category not in narrowed:
                narrowed.append(category)
        for category, score in sorted(semantic_scores.items(), key=lambda item: item[1], reverse=True):
            if category not in CATEGORY_TARGETS:
                continue
            if category in narrowed:
                continue
            if score >= threshold:
                narrowed.append(category)
        if narrowed:
            intent.required_categories = narrowed

    if route_autofilled and base_required:
        semantic_scores = {
            str(category): float(score)
            for category, score in (getattr(intent, "semantic_scores", {}) or {}).items()
            if category
        }
        extras = [
            category
            for category, _ in sorted(semantic_scores.items(), key=lambda item: item[1], reverse=True)
            if category in CATEGORY_TARGETS and category not in base_required
        ]
        if extras:
            intent.required_categories = list(dict.fromkeys([*base_required, extras[0]]))
            current_preferences = [str(item) for item in getattr(intent, "preferences", []) or [] if item]
            if extras[0] not in current_preferences:
                intent.preferences = list(dict.fromkeys([*current_preferences, extras[0]]))

    if getattr(intent, "pace", "normal") == "normal" and base.get("pace") in {"fast", "slow"}:
        intent.pace = str(base["pace"])
    if not getattr(intent, "transport_mode", None) or intent.transport_mode == "mixed":
        inherited_transport = base.get("transport_mode")
        if inherited_transport in {"walking", "metro", "taxi", "mixed"}:
            intent.transport_mode = inherited_transport
    intent = intent_parser.refresh_intent_derived_fields(intent)
    if not getattr(intent, "route_strategy", None) and base.get("route_strategy"):
        intent.route_strategy = str(base["route_strategy"])
    return intent


def _looks_like_route_modification(query: str) -> bool:
    text = str(query or "").lower()
    modification_terms = (
        "鏀规垚",
        "鎹㈡垚",
        "淇敼",
        "璋冩暣",
        "鍔犱笂",
        "鍔犱釜",
        "鍐嶅姞",
        "椤轰究",
        "涓嶈鍘熸潵",
        "閲嶆柊瀹夋帓",
        "鏇挎崲",
        "鍒犳帀",
        "鍘绘帀",
        "鍑忓皯",
        "鎹㈡帀",
        "淇濇寔",
        "别排队",
        "别太贵",
        "别太远",
        "less walking",
        "more food",
        "add",
        "change",
        "modify",
        "replace",
        "remove",
        "replan",
    )
    return any(term in text for term in modification_terms)


def _has_explicit_category_request(query: str) -> bool:
    text = str(query or "").strip().lower()
    if not text:
        return False
    category_keys = (
        "category_coffee",
        "category_food",
        "category_library",
        "category_exhibition",
        "category_night",
        "category_street",
        "category_park",
        "category_shopping",
        "category_museum",
        "category_scene",
    )
    for key in category_keys:
        for alias in INTENT_LEXICON.get(key, []) or []:
            token = str(alias or "").strip().lower()
            if token and token in text:
                return True
    return False


def _has_explicit_category_request_in_group(query: str, categories: set[str]) -> bool:
    text = str(query or "").strip().lower()
    if not text or not categories:
        return False
    for category in categories:
        lexicon_key = f"category_{category}"
        for alias in INTENT_LEXICON.get(lexicon_key, []) or []:
            token = str(alias or "").strip().lower()
            if token and token in text:
                return True
    return False


def _support_category_trimmed_base_required(
    base_required: list[str],
    modification_text: str,
) -> list[str]:
    categories = [str(item) for item in base_required if item]
    if len(categories) <= 2:
        return categories
    if _has_explicit_category_request_in_group(modification_text, EXPERIENCE_CATEGORIES):
        return categories
    if not _has_explicit_category_request_in_group(modification_text, SUPPORT_CATEGORIES):
        return categories

    experience = [category for category in categories if category in EXPERIENCE_CATEGORIES]
    support = [category for category in categories if category in SUPPORT_CATEGORIES]
    other = [category for category in categories if category not in EXPERIENCE_CATEGORIES and category not in SUPPORT_CATEGORIES]
    if len(experience) <= 2:
        return categories

    # Adding a support stop such as breakfast/coffee should preserve the route's
    # main experience skeleton without inheriting every old experience stop.
    trimmed = [*experience[:2], *support[:1], *other]
    return list(dict.fromkeys(trimmed))


def _apply_route_autofill_clamp(intent: ParsedIntent, current_route: Any = None) -> ParsedIntent:
    base = _current_route_intent(current_route)
    base_required = [str(item) for item in base.get("required_categories", []) or [] if item]
    if not base_required:
        return intent

    semantic_scores = {
        str(category): float(score)
        for category, score in (getattr(intent, "semantic_scores", {}) or {}).items()
        if category
    }
    extras = [
        category
        for category, _ in sorted(semantic_scores.items(), key=lambda item: item[1], reverse=True)
        if category in CATEGORY_TARGETS and category not in base_required
    ]
    narrowed = list(dict.fromkeys(base_required))
    if extras:
        narrowed.append(extras[0])
    intent.required_categories = narrowed

    base_prefs = [str(item) for item in base.get("preferences", []) or [] if item]
    current_prefs = [str(item) for item in getattr(intent, "preferences", []) or [] if item]
    merged_prefs = list(dict.fromkeys([*base_prefs, *current_prefs]))
    if extras and extras[0] not in merged_prefs:
        merged_prefs.append(extras[0])
    intent.preferences = merged_prefs
    return intent


def _current_route_from_context_snapshot(context_snapshot: Any) -> Any:
    if context_snapshot is None:
        return None

    session = getattr(context_snapshot, "session", None)
    route_versions = list(getattr(context_snapshot, "route_versions", []) or [])
    if not route_versions:
        return None

    current_version_id = getattr(session, "current_route_version_id", None) if session is not None else None
    if current_version_id:
        for route_version in route_versions:
            version_id = getattr(route_version, "version_id", None)
            if version_id == current_version_id:
                route = getattr(route_version, "route", None)
                if isinstance(route, dict) and route:
                    return route
                model_dump = getattr(route_version, "model_dump", None)
                if callable(model_dump):
                    dumped = dict(model_dump(mode="json"))
                    route = dumped.get("route")
                    if isinstance(route, dict) and route:
                        return route

    latest = route_versions[-1]
    route = getattr(latest, "route", None)
    if isinstance(route, dict) and route:
        return route
    model_dump = getattr(latest, "model_dump", None)
    if callable(model_dump):
        dumped = dict(model_dump(mode="json"))
        route = dumped.get("route")
        if isinstance(route, dict) and route:
            return route
    return None


def _infer_route_strategy(query: str, current_route: Any = None, intent: ParsedIntent | None = None) -> str:
    text = str(query or "")
    base_strategy = str(getattr(intent, "route_strategy", "") or "").lower()
    if base_strategy in {"fast", "compact"}:
        return base_strategy

    current_strategy = ""
    if isinstance(current_route, dict):
        current_intent = current_route.get("intent") or {}
        if isinstance(current_intent, dict):
            current_strategy = str(current_intent.get("route_strategy") or "").lower()
    if current_strategy in {"fast", "compact"}:
        return current_strategy

    fast_markers = (
        "快一点",
        "快点",
        "尽快",
        "省时间",
        "高效",
        "效率高",
        "别太累",
        "少点站",
        "少一点站",
        "少折腾",
        "简单点",
        "快一些",
    )
    compact_markers = (
        "紧凑",
        "少绕路",
        "少转场",
        "少走",
        "更近",
        "别太远",
        "顺路",
    )
    if any(token in text for token in fast_markers):
        return "fast"
    if any(token in text for token in compact_markers):
        return "compact"
    if intent is not None and current_route is None:
        preferences = set(str(item) for item in (getattr(intent, "preferences", []) or []))
        avoids = set(str(item) for item in (getattr(intent, "avoid", []) or []))
        required_categories = [str(item) for item in (getattr(intent, "required_categories", []) or []) if item]
        compact_bias = {"indoor", "rainy_day", "quiet", "relaxed"} & preferences
        if compact_bias and ("avoid_queue" in avoids or len(required_categories) <= 2):
            return "compact"
    return "balanced"


def _route_stats(stops: list[Any]) -> dict[str, Any]:
    return {
        "total_cost": int(sum(float(getattr(stop.poi, "price", 0.0) or 0.0) for stop in stops)),
        "total_duration": int(sum(int(getattr(stop.poi, "visit_duration", 0) or 0) for stop in stops)),
        "total_travel": int(sum(int(getattr(stop, "travel_to_next_min", 0) or 0) for stop in stops)),
        "total_distance": round(float(sum(float(getattr(stop, "travel_to_next_km", 0.0) or 0.0) for stop in stops)), 2),
    }


def _route_signal_context(planned: dict[str, Any]) -> dict[str, Any]:
    return {
        "ugc_signal_summary": dict(planned.get("ugc_signal_summary", {}) or {}),
        "heat_signal_summary": dict(planned.get("heat_signal_summary", {}) or {}),
    }


def _tool_travel_mode(intent: ParsedIntent) -> str:
    mode = str(getattr(intent, "transport_mode", "") or "").lower()
    if mode in {"walking", "metro", "taxi"}:
        return mode
    if "walking" in set(getattr(intent, "preferences", []) or []):
        return "walking"
    return "mixed"


def _run_plan_tools(
    intent: ParsedIntent,
    planned: dict[str, Any],
    execution_plan: ExecutionPlan,
    *,
    phase: str,
) -> tuple[dict[str, Any], list[ToolResult]]:
    results: list[ToolResult] = []
    map_plan = execution_plan.enabled_tool("map_distance_matrix")
    if map_plan is not None:
        result = route_tools.ROUTE_TOOL_REGISTRY.run(
            "map_distance_matrix",
            intent=intent,
            planned_route=planned,
            mode=_tool_travel_mode(intent),
            prefer_external=bool(map_plan.prefer_external),
            max_items=map_plan.max_items,
            phase=phase,
        )
        results.append(result)
        execution_plan.mark_node_status(
            "tool:map_distance_matrix",
            "completed" if result.status not in {"failed", "skipped"} else result.status,
            tool_status=result.status,
            fallback_used=bool(result.fallback_used),
        )
        planned = route_tools.apply_distance_matrix(planned, result)
    heat_plan = execution_plan.enabled_tool("heat_signal")
    if heat_plan is not None:
        result = route_tools.ROUTE_TOOL_REGISTRY.run(
            "heat_signal",
            intent=intent,
            planned_route=planned,
            max_items=heat_plan.max_items,
            phase=phase,
        )
        results.append(result)
        execution_plan.mark_node_status(
            "tool:heat_signal",
            "completed" if result.status not in {"failed", "skipped"} else result.status,
            tool_status=result.status,
            fallback_used=bool(result.fallback_used),
        )
        planned = route_tools.apply_heat_signals(planned, result)
    ugc_plan = execution_plan.enabled_tool("ugc_signal")
    if ugc_plan is not None:
        result = route_tools.ROUTE_TOOL_REGISTRY.run(
            "ugc_signal",
            intent=intent,
            planned_route=planned,
            max_items=ugc_plan.max_items,
            phase=phase,
        )
        results.append(result)
        execution_plan.mark_node_status(
            "tool:ugc_signal",
            "completed" if result.status not in {"failed", "skipped"} else result.status,
            tool_status=result.status,
            fallback_used=bool(result.fallback_used),
        )
        planned = route_tools.apply_ugc_signals(planned, result)
    return planned, results


def _run_pre_plan_tools(
    intent: ParsedIntent,
    execution_plan: ExecutionPlan,
) -> list[ToolResult]:
    results: list[ToolResult] = []
    memory_plan = execution_plan.enabled_tool("memory_context")
    if memory_plan is not None:
        result = route_tools.ROUTE_TOOL_REGISTRY.run(
                "memory_context",
                intent=intent,
                session_id=getattr(intent, "session_id", None),
                max_items=memory_plan.max_items,
                phase="pre_plan",
        )
        results.append(result)
        execution_plan.mark_node_status(
            "tool:memory_context",
            "completed" if result.status not in {"failed", "skipped"} else result.status,
            tool_status=result.status,
            fallback_used=bool(result.fallback_used),
        )
    return results


def _repair_intent_from_quality(intent: ParsedIntent, quality: dict[str, Any]) -> ParsedIntent | None:
    repaired = _INTENT_REPAIR_AGENT.repair(intent, quality)
    if repaired is None:
        return None
    return intent_parser.refresh_intent_derived_fields(repaired)


def _is_quality_better(new_quality: dict[str, Any], old_quality: dict[str, Any]) -> bool:
    old_score = float(old_quality.get("alignment_score", 0.0) or 0.0)
    new_score = float(new_quality.get("alignment_score", 0.0) or 0.0)
    old_gaps = len(old_quality.get("gaps", []) or [])
    new_gaps = len(new_quality.get("gaps", []) or [])
    if new_gaps < old_gaps:
        return True
    return new_score >= old_score + 0.04


def _ranking_limit(intent: ParsedIntent) -> int:
    strategy = str(getattr(intent, "route_strategy", "") or "balanced").lower()
    category_count = len(getattr(intent, "required_categories", []) or [])
    if strategy == "fast":
        return max(32, min(44, 30 + category_count * 4))
    if strategy == "compact":
        return max(36, min(48, 34 + category_count * 4))
    return max(42, min(54, 38 + category_count * 4))




def _plan_ranked_route(
    intent: ParsedIntent,
    use_map_api: bool,
) -> tuple[list[Any], list[dict[str, Any]], dict[str, Any], dict[str, Any], list[ToolResult]]:
    candidates = candidate_builder.build_candidates(intent, top_k=_ranking_limit(intent))
    if not candidates.recalled_pois:
        raise RoutePlanningError(404, "没有找到当前城市下可用的 POI，请换个城市或放宽条件。")

    pois = candidates.filtered_pois
    if not pois:
        raise RoutePlanningError(404, "没有找到满足当前约束的 POI，请放宽预算、距离或避让条件。")

    ranked = candidates.ranked_pois
    planned = route_planner.plan_route(ranked, intent, amap=use_map_api)
    planned["candidate_count"] = len(pois)
    planned["raw_candidate_count"] = len(candidates.recalled_pois)
    planned["ranking_candidate_count"] = len(ranked)
    planned["recall_sources"] = candidates.recall_sources
    planned["candidate_builder"] = candidates.to_trace_dict()
    quality = route_verifier.evaluate_route_alignment(
        intent,
        planned.get("main", []),
        _route_stats(planned.get("main", [])),
        _route_signal_context(planned),
    )
    return pois, ranked, planned, quality, candidates.tool_results


def _select_best_output_route(intent: ParsedIntent, planned: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Choose the best route variant after planning, using the output-side critic."""

    main_stops = list(planned.get("main", []) or [])
    signal_context = _route_signal_context(planned)
    main_quality = route_verifier.evaluate_route_alignment(intent, main_stops, _route_stats(main_stops), signal_context)
    best_name = str(planned.get("selected_variant_name") or "主方案")
    best_stops = main_stops
    best_quality = main_quality
    best_source = "main"

    for variant in planned.get("variants", []) or []:
        if not isinstance(variant, dict):
            continue
        variant_name = str(variant.get("name") or "候选方案")
        variant_stops = list(variant.get("stops", []) or [])
        if not variant_stops:
            continue
        variant_quality = route_verifier.evaluate_route_alignment(
            intent,
            variant_stops,
            _route_stats(variant_stops),
            signal_context,
        )
        if _is_quality_better(variant_quality, best_quality):
            best_name = variant_name
            best_stops = variant_stops
            best_quality = variant_quality
            best_source = "variant"

    if best_stops is main_stops:
        selected = dict(planned)
        selected["selected_variant_name"] = best_name
        selected["selected_variant_quality"] = best_quality
        selected["output_critic"] = route_verifier.critique_route(
            intent,
            best_stops,
            _route_stats(best_stops),
            signal_context,
        )
        return selected, best_quality

    selected = dict(planned)
    selected["main"] = best_stops
    selected["selected_poi_ids"] = [s.poi_id for s in best_stops]
    selected["area_clusters"] = list(dict.fromkeys(route_planner._poi_area_cluster(s.poi) for s in best_stops if route_planner._poi_area_cluster(s.poi)))
    selected["stats"] = {
        "total_visit_min": sum(s.poi.visit_duration for s in best_stops),
        "total_travel_min": sum(s.travel_to_next_min for s in best_stops),
        "total_km": sum(s.travel_to_next_km for s in best_stops),
    }
    selected["selected_variant_name"] = best_name
    selected["selected_variant_source"] = best_source
    selected["selected_variant_quality"] = best_quality
    selected["output_critic"] = route_verifier.critique_route(
        intent,
        best_stops,
        _route_stats(best_stops),
        signal_context,
    )
    return selected, best_quality


def _validate_planned_route(intent: ParsedIntent, planned: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    stops = planned.get("main", [])
    stats = _route_stats(stops)
    signal_context = _route_signal_context(planned)
    quality = route_verifier.evaluate_route_alignment(intent, stops, stats, signal_context)
    critique = route_verifier.critique_route(intent, stops, stats, signal_context)
    planned["output_critic"] = critique
    guardrail = workflow_guard.validate_route_workflow(
        intent,
        planned,
        quality,
        critique,
        diagnostics=None,
    )
    planned["workflow_guard"] = guardrail
    return quality, critique, guardrail


def _run_route_attempt(
    intent: ParsedIntent,
    *,
    use_map_api: bool,
    execution_plan: ExecutionPlan,
    phase: str,
) -> RouteAttempt:
    pois, ranked, planned, _, candidate_tool_results = _plan_ranked_route(intent, use_map_api)
    planned, _ = _select_best_output_route(intent, planned)
    planned, plan_tool_results = _run_plan_tools(intent, planned, execution_plan, phase=phase)
    quality, critique, guardrail = _validate_planned_route(intent, planned)
    planned["route_quality"] = quality
    planned["route_critic"] = critique
    planned["route_guard"] = guardrail
    return RouteAttempt(
        intent=intent,
        pois=pois,
        ranked=ranked,
        planned=planned,
        quality=quality,
        critique=critique,
        guardrail=guardrail,
        tool_results=[*candidate_tool_results, *plan_tool_results],
    )


def _route_attempt_trace(
    attempt: RouteAttempt,
    *,
    phase: str,
    accepted: bool,
    reason: str,
) -> dict[str, Any]:
    quality = attempt.quality or {}
    critique = attempt.critique or {}
    return {
        "phase": phase,
        "accepted": accepted,
        "reason": reason,
        "candidate_count": len(attempt.pois),
        "ranked_count": len(attempt.ranked),
        "main_stop_count": len(attempt.planned.get("main", []) or []),
        "variant_count": len(attempt.planned.get("variants", []) or []),
        "alignment_score": quality.get("alignment_score"),
        "quality_status": quality.get("status"),
        "quality_gaps": list(quality.get("gaps", []) or []),
        "critique_decision": critique.get("decision"),
        "selected_variant_name": attempt.planned.get("selected_variant_name"),
        "selected_variant_source": attempt.planned.get("selected_variant_source"),
        "repair_attempted": bool(getattr(attempt.intent, "repair_attempted", False)),
        "repair_patch_count": len(getattr(attempt.intent, "repair_patches", []) or []),
        "tool_results": [
            {
                "tool": result.tool,
                "status": result.status,
                "fallback_used": result.fallback_used,
            }
            for result in attempt.tool_results
        ],
        "planning_distance_matrix": attempt.planned.get("planning_distance_matrix", {}),
        "heat_signal_summary": attempt.planned.get("heat_signal_summary", {}),
    }


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
                options=["缇庨涓轰富", "鎷嶇収涓轰富", "杞绘澗閫涜"],
                reason="当前需求太宽泛，先确认主偏好可以让路线更准。",
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


def _add_unique(values: list[str], value: str) -> list[str]:
    return list(dict.fromkeys([*values, value]))


_EXPERIENCE_CATEGORIES = {"scene", "museum", "exhibition", "park", "street", "night", "shopping", "library"}
_SUPPORT_CATEGORIES = {"food", "coffee"}


def _derive_category_roles(intent: ParsedIntent) -> ParsedIntent:
    """Infer route composition roles from semantic strength, not phrase templates."""

    scores = dict(getattr(intent, "semantic_scores", {}) or {})
    raw_categories = list(
        dict.fromkeys(
            [
                *(getattr(intent, "primary_categories", []) or []),
                *(getattr(intent, "secondary_categories", []) or []),
                *(getattr(intent, "required_categories", []) or []),
                *(getattr(intent, "preferred_categories", []) or []),
            ]
        )
    )
    categories = [cat for cat in raw_categories if cat in CATEGORY_TARGETS]
    if not categories:
        return intent

    def _strength(category: str) -> float:
        score = float(scores.get(category, 0.0) or 0.0)
        if category in getattr(intent, "required_categories", []):
            score += 0.12
        if category in getattr(intent, "preferences", []):
            score += 0.04
        return score

    priority_order = list(ROUTE_POLICY["role"].get("primary_priority", []))

    def _priority_bonus(category: str) -> float:
        if category not in priority_order:
            return 0.0
        index = priority_order.index(category)
        return max(0.0, (len(priority_order) - index) / max(len(priority_order), 1)) * 0.05

    ranked = sorted(categories, key=lambda category: (-_strength(category) - _priority_bonus(category), category))
    primary_threshold = float(ROUTE_POLICY["role"]["primary_min_strength"])
    llm_primary = [cat for cat in getattr(intent, "primary_categories", []) or [] if cat in categories]
    llm_secondary = [
        cat for cat in getattr(intent, "secondary_categories", []) or [] if cat in categories and cat not in llm_primary
    ]
    primary_candidates = [cat for cat in ranked if cat in EXPERIENCE_CATEGORIES and _strength(cat) >= primary_threshold]
    support_candidates = [cat for cat in ranked if cat in SUPPORT_CATEGORIES]
    if not primary_candidates:
        primary_candidates = [cat for cat in ranked if cat in EXPERIENCE_CATEGORIES][:1] or ranked[:1]
    primary = list(dict.fromkeys([*llm_primary, *primary_candidates]))[:2]
    if any(cat in EXPERIENCE_CATEGORIES for cat in primary_candidates):
        primary = [cat for cat in primary if cat in EXPERIENCE_CATEGORIES] + [
            cat for cat in primary if cat not in EXPERIENCE_CATEGORIES
        ]
        primary = primary[:2]
    if not primary:
        primary = primary_candidates[:2]

    side = list(dict.fromkeys([*llm_secondary, *[cat for cat in ranked if cat not in primary]]))

    caps = dict(getattr(intent, "category_caps", {}) or {})
    min_counts = dict(getattr(intent, "category_min_counts", {}) or {})
    if primary and support_candidates and any(cat in EXPERIENCE_CATEGORIES for cat in primary):
        for support in support_candidates:
            caps[support] = min(int(caps.get(support, ROUTE_POLICY["role"]["support_cap"]) or ROUTE_POLICY["role"]["support_cap"]), ROUTE_POLICY["role"]["support_cap"])
    if primary and any(cat in SUPPORT_CATEGORIES for cat in categories) and any(cat in EXPERIENCE_CATEGORIES for cat in primary):
        strongest = primary[0]
        min_counts[strongest] = max(
            int(min_counts.get(strongest, 0) or 0),
            int(ROUTE_POLICY["role"]["primary_min_count_with_support"]),
        )

    intent.primary_categories = primary
    intent.side_categories = side
    intent.category_caps = caps
    intent.category_min_counts = min_counts
    return intent


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

    if any(token in text for token in ("娓呴棽", "娓呭噣", "瀹夐潤", "浼戞伅", "鍧愬潗", "鏀炬澗")):
        if "quiet" not in intent.preferences:
            intent.preferences.append("quiet")
        add_stage("quiet_rest", "娓呴棽浼戞伅")

    first_food = any(token in text for token in ("先去吃饭", "先吃饭", "第一站吃饭", "首先吃饭", "先喝早茶", "先去早茶", "第一站早茶"))
    final_food = "最后" in text and any(token in text for token in ("吃饭", "吃饭玩", "吃点", "早茶", "饮茶"))
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

    if any(token in text for token in ("鏅氶キ", "鏅氶", "鍚冮キ", "椁愬巺", "鏃╄尪", "楗尪", "鐐瑰績")) and not first_food:
        if "food" not in intent.required_categories:
            intent.required_categories.append("food")
        add_stage("food", "鏃╄尪/椁愰ギ" if any(token in text for token in ("鏃╄尪", "楗尪", "鐐瑰績")) else "鏅氶キ")
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
        add_stage("night", "澶滄櫙")

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
    intent = _derive_category_roles(intent)
    return intent_parser.refresh_intent_derived_fields(intent)


def _parse_intent(
    query: str,
    *,
    city: str | None = None,
    preferences: list[str] | None = None,
    current_route: Any = None,
    original_query: str | None = None,
    route_autofilled: bool = False,
    memory_context: str | None = None,
) -> ParsedIntent:
    hint = _task_hint(current_route)
    local_intent = intent_parser.parse_intent(query, city)
    local_confidence = _intent_confidence(local_intent, query, current_route)

    if os.getenv("LLM_INTENT_DISABLE_LLM") == "1":
        parsed_intent = local_intent
        parsed_intent.parse_source = "local"
        parsed_intent.intent_confidence = local_confidence
    elif _env_enabled("LLM_INTENT_FAST_GATE", "1") and os.getenv("LLM_INTENT_FORCE") != "1" and local_confidence >= _fast_gate_threshold(current_route):
        parsed_intent = local_intent
        parsed_intent.parse_source = "local_fast_gate"
        parsed_intent.intent_confidence = local_confidence
    else:
        parsed_intent = llm_intent_client.parse_intent_with_llm(
            query,
            city,
            task_hint=hint,
            original_query=original_query,
            current_route=current_route,
            memory_context=memory_context,
        )
        if parsed_intent is None:
            parsed_intent = local_intent
            parsed_intent.parse_source = "local_fallback"
            parsed_intent.intent_confidence = local_confidence
        elif getattr(parsed_intent, "intent_confidence", None) is None:
            parsed_intent.intent_confidence = max(local_confidence, 0.65)

    if preferences:
        intent_parser.apply_ui_preferences(parsed_intent, preferences)
    if current_route is not None:
        parsed_intent.current_route = current_route
        parsed_intent.modification_query = query
        parsed_intent = _inherit_current_route_intent(
            parsed_intent,
            current_route,
            route_autofilled=route_autofilled,
        )
    intent_parser.apply_modification_hints(parsed_intent, query, current_route=current_route)
    parsed_intent = _apply_ordered_query_hints(parsed_intent, query)
    parsed_intent.route_strategy = _infer_route_strategy(query, current_route, parsed_intent)
    if route_autofilled and current_route is not None:
        parsed_intent = _apply_route_autofill_clamp(parsed_intent, current_route)
    return parsed_intent


def parse_intent_only(
    query: str,
    *,
    city: str | None = None,
    preferences: list[str] | None = None,
    current_route: Any = None,
    original_query: str | None = None,
) -> ParsedIntent:
    """Parse intent through the same cascade used by route generation."""

    intent = _parse_intent(
        query,
        city=city,
        preferences=preferences,
        current_route=current_route,
        original_query=original_query,
    )
    intent.original_query = original_query or query
    return intent


def plan_route_from_intent(
    intent: ParsedIntent,
    use_map_api: bool = False,
    use_amap: bool | None = None,
) -> RouteResponse:
    """Complete route planning from a parsed intent."""
    if use_amap is not None:
        use_map_api = use_amap

    route_state = _COORDINATOR.start(intent)
    execution_plan = _COORDINATOR.build_execution_plan(route_state, intent, use_map_api=use_map_api)
    clarification = _need_clarification(intent, getattr(intent, "original_query", "") or "", getattr(intent, "current_route", None))
    if clarification:
        execution_plan.mark_node_status("clarification", "completed", reason=clarification.reason)
        _COORDINATOR.after_clarification(route_state, clarification.question)
        diagnostics = RouteDiagnostics(
            task_hint=RouteTaskHint.ROUTE_MODIFICATION if getattr(intent, "current_route", None) is not None else RouteTaskHint.INTENT_EXTRACTION,
            parse_source=getattr(intent, "parse_source", "local"),
            clarification_needed=True,
            clarification_question=clarification.question,
            clarification_reason=clarification.reason,
            coordinator=route_state.to_trace_dict(),
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
        for error in check["errors"]:
            route_state.add_error(str(error))
        raise RoutePlanningError(422, "?".join(check["errors"]))

    for result in _run_pre_plan_tools(intent, execution_plan):
        route_state.add_tool_result(result)

    attempt = _run_route_attempt(
        intent,
        use_map_api=use_map_api,
        execution_plan=execution_plan,
        phase="initial",
    )
    route_attempts = [
        _route_attempt_trace(
            attempt,
            phase="initial",
            accepted=True,
            reason="initial_route",
        )
    ]
    for result in attempt.tool_results:
        route_state.add_tool_result(result)
    execution_plan.mark_node_status(
        "poi_retrieval",
        "completed",
        candidate_count=len(attempt.pois),
        recall_sources=list(attempt.planned.get("recall_sources", []) or []),
    )
    execution_plan.mark_node_status(
        "ranking",
        "completed",
        ranked_count=len(attempt.ranked),
    )
    execution_plan.mark_node_status(
        "candidate_building",
        "completed",
        selected_count=len(attempt.ranked),
    )
    _COORDINATOR.after_retrieval(
        route_state,
        candidate_count=len(attempt.pois),
        ranked_count=len(attempt.ranked),
        recall_sources=list(attempt.planned.get("recall_sources", []) or []),
    )
    execution_plan.mark_node_status(
        "planning",
        "completed",
        main_stop_count=len(attempt.planned.get("main", []) or []),
        variant_count=len(attempt.planned.get("variants", []) or []),
    )
    execution_plan.mark_node_status(
        "validation",
        "completed",
        quality_status=str((attempt.quality or {}).get("status") or ""),
        alignment_score=float((attempt.quality or {}).get("alignment_score", 0.0) or 0.0),
    )
    _COORDINATOR.after_planning(
        route_state,
        planned_route=attempt.planned,
        quality=attempt.quality,
        critique=attempt.critique,
        route_stats=attempt.route_stats,
    )
    repaired_intent = _repair_intent_from_quality(intent, attempt.quality)
    if repaired_intent is not None:
        try:
            repaired_attempt = _run_route_attempt(
                repaired_intent,
                use_map_api=use_map_api,
                execution_plan=execution_plan,
                phase="repair",
            )
            for result in repaired_attempt.tool_results:
                route_state.add_tool_result(result)
            if _is_quality_better(repaired_attempt.quality, attempt.quality):
                route_attempts[0]["accepted"] = False
                route_attempts[0]["reason"] = "superseded_by_repair"
                route_attempts.append(
                    _route_attempt_trace(
                        repaired_attempt,
                        phase="repair",
                        accepted=True,
                        reason="quality_improved",
                    )
                )
                intent = repaired_intent
                route_state.intent = intent.model_dump(mode="json")
                route_state.city = getattr(intent, "city", None)
                route_state.parse_source = getattr(intent, "parse_source", None)
                route_state.intent_confidence = getattr(intent, "intent_confidence", None)
                attempt = repaired_attempt
                _COORDINATOR.after_planning(
                    route_state,
                    planned_route=attempt.planned,
                    quality=attempt.quality,
                    critique=attempt.critique,
                        route_stats=attempt.route_stats,
                    )
            else:
                route_attempts.append(
                    _route_attempt_trace(
                        repaired_attempt,
                        phase="repair",
                        accepted=False,
                        reason="quality_not_better",
                    )
                )
        except RoutePlanningError:
            pass

    planned = attempt.planned
    ranked = attempt.ranked
    planned["route_attempts"] = route_attempts
    explanation = response_generator.generate_route_explanation(intent, planned.get("main", []))
    explanation = response_generator.maybe_truncate_route_explanation(
        explanation,
        getattr(intent, "original_query", "") or getattr(intent, "modification_query", "") or query,
    )
    execution_plan.mark_node_status(
        "explanation",
        "completed",
        explanation_length=len(str(explanation or "").strip()),
    )
    _COORDINATOR.after_explanation(route_state, explanation)
    planned["execution_plan"] = {
        **execution_plan.model_dump(mode="json"),
        "dag_status_summary": execution_plan.status_summary(),
    }
    planned["tool_results"] = [result.model_dump(mode="json") for result in route_state.tool_results]
    planned["coordinator"] = route_state.to_trace_dict()
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
    diagnostics.map_status = map_service.get_status().model_dump(mode="json")
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
    route_autofilled = False
    route_context = current_route
    if route_context is None and context_snapshot is not None and _looks_like_route_modification(query):
        route_context = _current_route_from_context_snapshot(context_snapshot)
        route_autofilled = route_context is not None
    inferred_city = city or infer_city_from_route(route_context)
    memory_context = None
    if context_snapshot is not None and not _context_opted_out(original_query or query):
        try:
            from services import context_service

            session = getattr(context_snapshot, "session", None)
            session_id = getattr(session, "session_id", None) if session is not None else None
            if session_id:
                memory_context = context_service.render_memory_context_block(
                    context_service.get_memory_projection(str(session_id), limit=6)
                )
        except Exception:
            memory_context = None
    intent = _parse_intent(
        query,
        city=inferred_city,
        preferences=preferences,
        current_route=route_context,
        original_query=original_query,
        route_autofilled=route_autofilled,
        memory_context=memory_context,
    )
    intent.original_query = original_query or query
    context_opted_out = _context_opted_out(intent.original_query or query)
    if context_snapshot is not None and route_context is None:
        try:
            from services import context_service

            session = getattr(context_snapshot, "session", None)
            if session is not None:
                intent.session_id = getattr(session, "session_id", None)
            if not context_opted_out:
                intent = context_service.apply_session_context(intent, session)
        except Exception:
            pass
    elif context_snapshot is not None:
        try:
            session = getattr(context_snapshot, "session", None)
            if session is not None:
                intent.session_id = getattr(session, "session_id", None)
        except Exception:
            pass
    if profile is not None and not context_opted_out:
        try:
            from services import context_service

            intent = context_service.apply_profile_bias(intent, profile)
        except Exception:
            pass
    response = plan_route_from_intent(intent, use_map_api=use_map_api)
    return intent, response
