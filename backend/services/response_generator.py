"""
响应生成服务模块
=================

本模块负责将内部数据结构转换为统一的API响应格式，并生成自然语言解释。

主要功能：
- 标准化API响应格式
- 生成路线说明文本
- 生成POI推荐理由
- 格式化各种统计信息

作者：美团智能路线规划团队
"""

from core.contracts import ClarificationDecision, RouteDiagnostics, RouteTaskHint
from core.display_labels import build_intent_summary, collect_preference_labels
from core.intent_ir import build_intent_ir
from core.route_policy import ROUTE_POLICY
from core.schemas import ParsedIntent, RouteResponse, RouteStop


_CATEGORY_LABELS = {
    "coffee": "咖啡",
    "food": "餐饮",
    "library": "图书馆",
    "museum": "博物馆",
    "exhibition": "展览",
    "scene": "景观",
    "street": "街区",
    "shopping": "购物",
    "park": "公园",
    "night": "夜景",
}


def _intent_trace_summary(intent: ParsedIntent) -> dict:
    intent_ir = build_intent_ir(intent).model_dump(mode="json")
    parse_source = str(getattr(intent, "parse_source", "local") or "local")
    llm_payload = getattr(intent, "llm_payload", None)
    semantic_scores = dict(getattr(intent, "semantic_scores", {}) or {})
    sorted_scores = sorted(
        (
            {"label": str(label), "score": round(float(score), 3)}
            for label, score in semantic_scores.items()
            if label
        ),
        key=lambda item: item["score"],
        reverse=True,
    )
    required_categories = [str(item) for item in getattr(intent, "required_categories", []) or [] if item]
    preferences = [str(item) for item in getattr(intent, "preferences", []) or [] if item]
    avoid = [str(item) for item in getattr(intent, "avoid", []) or [] if item]
    uncertain_fields = [str(item) for item in getattr(intent, "uncertain_fields", []) or [] if item]
    recognized_signals = [str(item) for item in getattr(intent, "recognized_signals", []) or [] if item]
    unclassified_clues = [str(item) for item in getattr(intent, "unclassified_clues", []) or [] if item]
    context_bias = [str(item) for item in getattr(intent, "context_bias", []) or [] if item]
    profile_bias = [str(item) for item in getattr(intent, "profile_bias", []) or [] if item]
    hard_constraints = [str(item) for item in getattr(intent, "hard_constraints", []) or [] if item]
    semantic_hints = [str(item) for item in getattr(intent, "semantic_hints", []) or [] if item]
    confidence = getattr(intent, "intent_confidence", None)
    try:
        confidence_value = round(float(confidence), 3) if confidence is not None else None
    except (TypeError, ValueError):
        confidence_value = None

    path = "local_rule_parse"
    if parse_source == "local_fast_gate":
        path = "local_semantic_fast_gate"
    elif parse_source == "local_fallback":
        path = "llm_failed_then_local_fallback"
    elif parse_source == "llm+local":
        path = "llm_parse_with_local_normalization"

    schema_checks = {
        "city_present": bool(getattr(intent, "city", None)),
        "time_window_present": bool(getattr(intent, "start_time", None) or getattr(intent, "end_time", None)),
        "budget_present": getattr(intent, "budget", None) is not None,
        "constraints_ready": bool(required_categories or preferences or avoid or getattr(intent, "must_include", [])),
        "clarification_recommended": bool(getattr(intent, "needs_clarification", False) or uncertain_fields),
    }

    return {
        "intent_ir": intent_ir,
        "parse_source": parse_source,
        "path": path,
        "confidence": confidence_value,
        "schema_checks": schema_checks,
        "llm_used": bool(llm_payload),
        "memory_bias_used": bool(context_bias or profile_bias),
        "current_route_bound": bool(getattr(intent, "current_route", None) is not None),
        "required_categories": required_categories,
        "preferences": preferences,
        "avoid": avoid,
        "must_include": [str(item) for item in getattr(intent, "must_include", []) or [] if item],
        "hard_constraints": hard_constraints,
        "uncertain_fields": uncertain_fields,
        "recognized_signals": recognized_signals[:8],
        "semantic_hints": semantic_hints[:6],
        "top_semantic_scores": sorted_scores[:6],
        "unclassified_clues": unclassified_clues[:6],
        "context_bias": context_bias[:6],
        "profile_bias": profile_bias[:6],
    }


def _minutes_to_time(value: int | float | str | None) -> str:
    try:
        minutes = int(float(value))
    except (TypeError, ValueError):
        return ""
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _stop_extra(stop: RouteStop, key: str, default=None):
    extra = getattr(stop, "model_extra", None) or {}
    if key in extra:
        return extra.get(key)
    return getattr(stop, key, default)


def _rain_sensitive(intent: ParsedIntent) -> bool:
    preferences = set(getattr(intent, "preferences", []) or [])
    categories = set(getattr(intent, "required_categories", []) or [])
    return bool({"rainy_day", "indoor"} & preferences or "indoor" in categories)


def _poi_area(poi) -> str:
    return str(
        getattr(poi, "area_label", None)
        or getattr(poi, "business_area", None)
        or getattr(poi, "area_cluster", None)
        or getattr(poi, "district", None)
        or ""
    )


def _poi_has_text(poi, terms: tuple[str, ...]) -> bool:
    values = [
        getattr(poi, "name", "") or "",
        getattr(poi, "description", "") or "",
        " ".join(getattr(poi, "tags", []) or []),
        " ".join(getattr(poi, "review_keywords", []) or []),
        " ".join(getattr(poi, "suitable_for", []) or []),
    ]
    blob = " ".join(values)
    return any(term in blob for term in terms)


def _intent_match_reasons(stop: RouteStop, intent: ParsedIntent, rank_info: dict | None) -> list[str]:
    poi = stop.poi
    reasons: list[str] = []
    preferences = set(getattr(intent, "preferences", []) or []) | set(getattr(intent, "soft_preferences", []) or [])
    avoid = set(getattr(intent, "avoid", []) or [])
    category = getattr(poi, "category", "") or ""
    category_label = _CATEGORY_LABELS.get(category, category or "目的地")

    if category in set(getattr(intent, "required_categories", []) or []):
        reasons.append(f"它正好补上了你需要的{category_label}体验")
    if "coffee" in preferences or getattr(intent, "prefer_coffee", False):
        if category == "coffee":
            reasons.append("适合作为轻量开场，停留时间不长，也方便后续转场")
    if "food" in preferences or getattr(intent, "prefer_food", False):
        if category == "food" or float(getattr(poi, "food_score", 0) or 0) >= 4:
            reasons.append("餐饮体验分较高，能满足你对吃饭/美食的要求")
    if "photo" in preferences or getattr(intent, "prefer_photo", False):
        if float(getattr(poi, "photo_score", 0) or 0) >= 4:
            reasons.append("拍照表现更强，适合打卡和出片")
    if "culture" in preferences or getattr(intent, "prefer_culture", False):
        if category in {"museum", "exhibition"} or float(getattr(poi, "culture_score", 0) or 0) >= 4:
            reasons.append("文化内容更明确，不只是单纯路过")
    if "local_feature" in preferences or getattr(intent, "prefer_local_feature", False):
        if float(getattr(poi, "local_feature_score", 0) or 0) >= 4 or _poi_has_text(poi, ("老字号", "本地", "地道", "烟火气")):
            reasons.append("本地特色更明显，符合你想要的城市感")
    if "quiet" in preferences or getattr(intent, "prefer_quiet", False):
        if int(getattr(poi, "queue_level", 3) or 3) <= 2 or _poi_has_text(poi, ("安静", "清净", "清闲", "松弛", "人少")):
            reasons.append("排队和拥挤风险较低，更贴近清闲、放松的诉求")
    if "night_view" in preferences or getattr(intent, "prefer_night_view", False):
        if category == "night" or _poi_has_text(poi, ("夜景", "江景", "灯光", "观景")):
            reasons.append("更适合看景或夜景，放进路线能强化观赏性")
    if "rainy_day" in preferences or "indoor" in preferences or getattr(intent, "prefer_rainy_day", False):
        if getattr(poi, "indoor_outdoor", "") == "indoor" or float(getattr(poi, "rainy_day_score", 0) or 0) >= 4:
            reasons.append("室内或雨天适配度更高，天气变化时更稳")
    if "value" in preferences or getattr(intent, "prefer_value", False) or getattr(intent, "budget", None):
        budget = float(getattr(intent, "budget", 0) or 0)
        price = float(getattr(poi, "price", 0) or 0)
        if price <= 0:
            reasons.append("成本很低，能帮你控制预算")
        elif budget and price <= budget / max(len(getattr(intent, "required_categories", []) or []), 1):
            reasons.append("人均价格在预算内，性价比更稳")
    if "avoid_queue" in avoid and int(getattr(poi, "queue_level", 3) or 3) <= 2:
        reasons.append("排队等级较低，符合你“不想排队”的限制")
    if "avoid_crowded" in avoid and int(getattr(poi, "queue_level", 3) or 3) <= 2:
        reasons.append("热度压力相对小，能避开太拥挤的体验")

    if rank_info:
        recommend_reason = str(rank_info.get("recommend_reason") or "").strip("。")
        if recommend_reason and recommend_reason not in "；".join(reasons):
            reasons.append(recommend_reason)

    return list(dict.fromkeys(reason for reason in reasons if reason))[:3]


def _order_reason(stop: RouteStop, index: int, total: int, intent: ParsedIntent, previous_stop: RouteStop | None) -> str:
    poi = stop.poi
    category = getattr(poi, "category", "") or ""
    visit_duration = int(getattr(poi, "visit_duration", 0) or 0)

    if index == 0:
        if category == "library":
            return "把它放在第1站，是因为你明确说第一站先去图书馆；这里适合下午先安静停留，再接后面的休息、晚饭和夜景"
        if category == "coffee":
            return f"把它放在第1站，是因为{visit_duration}分钟左右就能完成，适合先调整节奏，再进入后面的主行程"
        if getattr(intent, "start_location", None):
            return "把它放在第1站，是因为它更适合作为从起点出发后的第一处落脚点"
        return "把它放在第1站，是为了先安排一个负担较低、容易进入状态的点"

    prev_travel_min = int(_stop_extra(previous_stop, "travel_to_next_min", 0) or 0) if previous_stop is not None else 0
    prev_travel_km = float(_stop_extra(previous_stop, "travel_to_next_km", 0.0) or 0.0) if previous_stop is not None else 0.0
    current_area = _poi_area(poi)
    previous_area = _poi_area(previous_stop.poi) if previous_stop is not None else ""

    if index == total - 1:
        if category == "food":
            return "把它放在最后，是因为餐饮更适合作为路线收尾，前面逛完后再用餐体验更自然"
        if category == "night":
            return "把它放在最后，是因为夜景类地点越晚观赏性越强，时间顺序更合适"

    if previous_area and current_area and previous_area == current_area:
        return f"它和上一站同在{current_area}一带，放在这里可以减少绕路和重复转场"
    if prev_travel_min > 0 and prev_travel_min <= 15:
        return f"从上一站过来约{prev_travel_min}分钟、{prev_travel_km:.1f}公里，转场压力比较小"
    if prev_travel_min > 0:
        return f"虽然需要约{prev_travel_min}分钟转场，但它补足了路线中缺少的体验类型"
    return "放在这里是为了让路线类型更完整，同时保持前后站点衔接"


def _build_stop_reason(
    stop: RouteStop,
    index: int,
    total: int,
    intent: ParsedIntent,
    rank_info: dict | None,
    previous_stop: RouteStop | None,
) -> str:
    explicit_reason = (_stop_extra(stop, "note", "") or getattr(stop, "stop_reason", None) or "").strip()
    if explicit_reason and "匹配当前路线偏好" not in explicit_reason:
        return explicit_reason

    match_reasons = _intent_match_reasons(stop, intent, rank_info)
    order_reason = _order_reason(stop, index, total, intent, previous_stop)
    if match_reasons:
        return f"{match_reasons[0]}；{order_reason}。"
    return f"{_CATEGORY_LABELS.get(getattr(stop.poi, 'category', ''), '这个点')}与本次需求的综合得分较高；{order_reason}。"


def _normalize_stop(
    stop: RouteStop,
    index: int,
    intent: ParsedIntent,
    *,
    total: int,
    rank_info: dict | None = None,
    previous_stop: RouteStop | None = None,
) -> dict:
    start = _stop_extra(stop, "start_time")
    end = _stop_extra(stop, "end_time")
    travel_min = int(_stop_extra(stop, "travel_to_next_min", 0) or 0)
    travel_km = float(_stop_extra(stop, "travel_to_next_km", 0.0) or 0.0)
    reason = _build_stop_reason(stop, index, total, intent, rank_info, previous_stop)

    return {
        "poi": stop.poi.model_dump(mode="json") if hasattr(stop.poi, "model_dump") else stop.poi,
        "arrival_time": _minutes_to_time(start),
        "departure_time": _minutes_to_time(end),
        "stay_minutes": int(getattr(stop.poi, "visit_duration", 0) or 0),
        "reason": reason,
        "risk_alert": _risk_alert(stop, intent),
        "travel_from_previous": None,
        "travel_to_next": {
            "mode": getattr(intent, "transport_mode", None) or "mixed",
            "distance_km": round(travel_km, 2),
            "duration_min": travel_min,
            "cost": 0,
            "source": "local",
        },
    }


def _attach_previous_travel(stops: list[dict]) -> list[dict]:
    for index in range(1, len(stops)):
        stops[index]["travel_from_previous"] = stops[index - 1].get("travel_to_next")
    for item in stops:
        item.pop("travel_to_next", None)
    return stops


def _risk_alert(stop: RouteStop, intent: ParsedIntent) -> str | None:
    poi = stop.poi
    alerts: list[str] = []
    if (getattr(poi, "queue_level", 0) or 0) >= 4:
        alerts.append("高峰期可能排队")
    if _rain_sensitive(intent) and getattr(poi, "indoor_outdoor", "") == "outdoor" and (getattr(poi, "rainy_day_score", 0) or 0) <= 2:
        alerts.append("雨天体验会下降")
    price = float(getattr(poi, "price", 0.0) or 0.0)
    if price >= 120:
        alerts.append("人均价格偏高")
    return "；".join(alerts) if alerts else None


def _route_stats(stops: list[RouteStop]) -> dict:
    total_cost = int(sum(float(getattr(stop.poi, "price", 0.0) or 0.0) for stop in stops))
    total_duration = int(sum(int(getattr(stop.poi, "visit_duration", 0) or 0) for stop in stops))
    total_travel = int(sum(int(_stop_extra(stop, "travel_to_next_min", 0) or 0) for stop in stops))
    total_distance = float(sum(float(_stop_extra(stop, "travel_to_next_km", 0.0) or 0.0) for stop in stops))
    covered_types = list(dict.fromkeys(getattr(stop.poi, "category", "") for stop in stops if getattr(stop.poi, "category", "")))
    area_clusters = list(
        dict.fromkeys(
            str(getattr(stop.poi, "area_cluster", "") or getattr(stop.poi, "business_area", "") or "")
            for stop in stops
            if getattr(stop.poi, "area_cluster", None) or getattr(stop.poi, "business_area", None)
        )
    )
    return {
        "total_cost": total_cost,
        "total_duration": total_duration,
        "total_travel": total_travel,
        "total_distance": round(total_distance, 2),
        "poi_count": len(stops),
        "covered_types": covered_types,
        "area_clusters": area_clusters,
    }


def _normalize_route_stops(stops: list[RouteStop], intent: ParsedIntent, rank_by_poi_id: dict[str, dict]) -> list[dict]:
    return _attach_previous_travel(
        [
            _normalize_stop(
                stop,
                index,
                intent,
                total=len(stops),
                rank_info=rank_by_poi_id.get(str(getattr(stop.poi, "id", ""))),
                previous_stop=stops[index - 1] if index > 0 else None,
            )
            for index, stop in enumerate(stops)
        ]
    )


def _build_map_preview_for_stops(stops: list[RouteStop], explanation: str = "") -> dict:
    try:
        from services import map_service

        return map_service.build_route_preview(
            {
                "title": "城市路线",
                "summary": explanation,
                "main_stops": stops,
            }
        )
    except Exception:
        return {}


def _route_options(
    main_stops: list[RouteStop],
    variants: list[dict],
    intent: ParsedIntent,
    rank_by_poi_id: dict[str, dict],
    explanation: str = "",
) -> list[dict]:
    options: list[dict] = []

    def add_option(name: str, stops: list[RouteStop], score: float) -> None:
        stats = _route_stats(stops)
        normalized_stops = _normalize_route_stops(stops, intent, rank_by_poi_id)
        options.append(
            {
                "strategy_type": name,
                "route_score": round(score, 3),
                "total_cost": stats["total_cost"],
                "total_duration": stats["total_duration"] + stats["total_travel"],
                "total_distance": stats["total_distance"],
                "poi_count": stats["poi_count"],
                "stops": [getattr(stop.poi, "name", "") for stop in stops],
                "route_stops": normalized_stops,
                "covered_types": stats["covered_types"],
                "map_preview": _build_map_preview_for_stops(stops, explanation),
            }
        )

    add_option("推荐方案", main_stops, 1.0)
    for index, variant in enumerate(variants):
        stops = list(variant.get("stops") or [])
        name = str(variant.get("name") or f"备选方案{index + 1}")
        add_option(name, stops, max(0.6, 0.92 - index * 0.08))
    return options


def _current_route_poi_ids(current_route) -> list[str]:
    if not isinstance(current_route, dict):
        return []
    stops = current_route.get("stops") or current_route.get("main_stops") or []
    if not isinstance(stops, list):
        return []

    ids: list[str] = []
    for stop in stops:
        if not isinstance(stop, dict):
            continue
        poi = stop.get("poi") if isinstance(stop.get("poi"), dict) else {}
        poi_id = stop.get("poi_id") or poi.get("id")
        if poi_id:
            ids.append(str(poi_id))
    return ids


def _modification_trace(intent: ParsedIntent, planned_route: dict) -> dict:
    current_ids = _current_route_poi_ids(getattr(intent, "current_route", None))
    selected_ids = [str(item) for item in planned_route.get("selected_poi_ids", []) if item]
    if not current_ids:
        return {
            "is_modification": getattr(intent, "current_route", None) is not None,
            "modification_query": getattr(intent, "modification_query", "") or "",
        }

    current_set = set(current_ids)
    selected_set = set(selected_ids)
    return {
        "is_modification": True,
        "modification_query": getattr(intent, "modification_query", "") or "",
        "previous_poi_ids": current_ids,
        "added_poi_ids": [item for item in selected_ids if item not in current_set],
        "removed_poi_ids": [item for item in current_ids if item not in selected_set],
        "kept_poi_ids": [item for item in selected_ids if item in current_set],
        "changed": current_ids != selected_ids,
    }


def _warnings(stops: list[RouteStop], intent: ParsedIntent) -> list[str]:
    result: list[str] = []
    if len(stops) < 3:
        result.append("当前可用候选点较少，路线站点数未达到 3 个。")
    if any((getattr(stop.poi, "queue_level", 0) or 0) >= 4 for stop in stops):
        result.append("部分站点在热门时段可能排队，建议保留时间缓冲。")
    if _rain_sensitive(intent) and any(getattr(stop.poi, "indoor_outdoor", "") == "outdoor" for stop in stops):
        result.append("路线包含户外点，雨天建议改成室内优先。")
    return result


def _workflow_stages(workflow_trace: dict[str, object], explanation: str) -> list[dict[str, str]]:
    stages: list[dict[str, str]] = [{"stage": "input"}]
    coordinator = workflow_trace.get("coordinator") if isinstance(workflow_trace, dict) else {}
    if not isinstance(coordinator, dict):
        coordinator = {}
    decisions = coordinator.get("decision_log") or []
    if decisions:
        stages.append({"stage": "understanding"})
    if coordinator.get("execution_plan"):
        stages.append({"stage": "execution_plan"})
    if coordinator.get("retrieval"):
        stages.append({"stage": "retrieval"})
    if workflow_trace.get("memory"):
        stages.append({"stage": "memory"})
    if coordinator.get("tool_results"):
        stages.append({"stage": "tools"})
    if coordinator.get("planning"):
        stages.append({"stage": "planning"})
    if coordinator.get("quality_report") or coordinator.get("route_quality"):
        stages.append({"stage": "critique"})
    if coordinator.get("quality_report"):
        stages.append({"stage": "guard"})
    if decisions:
        stages.append({"stage": "coordination"})
    if explanation:
        stages.append({"stage": "explain"})
    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in stages:
        stage = str(item.get("stage") or "")
        if stage and stage not in seen:
            seen.add(stage)
            unique.append(item)
    return unique


def _tool_payload(tool_result: object) -> dict:
    if hasattr(tool_result, "model_dump"):
        data = tool_result.model_dump(mode="json")
    elif isinstance(tool_result, dict):
        data = dict(tool_result)
    else:
        return {}
    payload = data.get("payload")
    return payload if isinstance(payload, dict) else {}


def _memory_trace_summary(tool_results: list[object]) -> dict:
    for item in tool_results:
        data = item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item) if isinstance(item, dict) else {}
        if str(data.get("tool") or "") != "memory_context":
            continue
        payload = _tool_payload(data)
        stable_categories = list(payload.get("stable_categories") or [])[:4]
        stable_preferences = list(payload.get("stable_preferences") or [])[:4]
        stable_avoids = list(payload.get("stable_avoids") or [])[:4]
        recent_categories = list(payload.get("recent_categories") or [])[:3]
        recent_preferences = list(payload.get("recent_preferences") or [])[:3]
        recent_avoids = list(payload.get("recent_avoids") or [])[:3]
        pending_conflicts = list(payload.get("pending_conflicts") or [])[:3]
        prompt_block = str(payload.get("prompt_block") or "")
        return {
            "status": data.get("status", "unknown"),
            "confidence": data.get("confidence", 0.0),
            "session_id": payload.get("session_id"),
            "phase": payload.get("phase"),
            "memory_strength": payload.get("memory_strength", 0.0),
            "profile_confidence": payload.get("profile_confidence", 0.0),
            "stable_signal_count": payload.get("stable_signal_count", 0),
            "recent_signal_count": payload.get("recent_signal_count", 0),
            "decay_score": payload.get("decay_score", 0.0),
            "staleness_days": payload.get("staleness_days"),
            "home_city": payload.get("home_city"),
            "stable_categories": stable_categories,
            "stable_preferences": stable_preferences,
            "stable_avoids": stable_avoids,
            "recent_categories": recent_categories,
            "recent_preferences": recent_preferences,
            "recent_avoids": recent_avoids,
            "pending_conflicts": pending_conflicts,
            "pending_conflict_count": len(list(payload.get("pending_conflicts") or [])),
            "route_version_count": payload.get("route_version_count", 0),
            "prompt_block_lines": len([line for line in prompt_block.splitlines() if line.strip()]),
            "noise_risk": data.get("noise_risk", "unknown"),
            "used_by": list(data.get("used_by") or []),
        }
    return {}


def _retrieval_trace_summary(tool_results: list[object]) -> dict:
    summary = {
        "recall": {},
        "filter": {},
        "rerank": {},
    }
    for item in tool_results:
        data = item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item) if isinstance(item, dict) else {}
        tool = str(data.get("tool") or "")
        payload = _tool_payload(data)
        if tool == "poi_recall":
            summary["recall"] = {
                "status": data.get("status", "unknown"),
                "confidence": data.get("confidence", 0.0),
                "noise_risk": payload.get("noise_risk", data.get("noise_risk", "unknown")),
                "hybrid_backend": payload.get("hybrid_backend"),
                "lexical_backend": payload.get("lexical_backend"),
                "dense_backend": payload.get("dense_backend"),
                "faiss_enabled": payload.get("faiss_enabled", False),
                "vector_dim": payload.get("vector_dim"),
                "active_lanes": list(payload.get("active_lanes") or []),
                "recall_lane_count": payload.get("recall_lane_count", 0),
                "raw_candidate_count": payload.get("raw_candidate_count", 0),
                "selected_count": payload.get("selected_count", 0),
                "text_signal_share": payload.get("text_signal_share", 0.0),
                "lane_overlap_ratio": payload.get("lane_overlap_ratio", 0.0),
                "used_city_fallback": payload.get("used_city_fallback", False),
                "fallback_expanded": payload.get("fallback_expanded", False),
            }
        elif tool == "constraint_filter":
            summary["filter"] = {
                "status": data.get("status", "unknown"),
                "input_count": payload.get("input_count", 0),
                "output_count": payload.get("output_count", 0),
                "removed_count": payload.get("removed_count", 0),
                "budget": payload.get("budget"),
                "avoid": list(payload.get("avoid") or []),
            }
        elif tool == "poi_rerank":
            summary["rerank"] = {
                "status": data.get("status", "unknown"),
                "confidence": data.get("confidence", 0.0),
                "rerank_backend": payload.get("rerank_backend"),
                "rerank_model": payload.get("rerank_model"),
                "rerank_active": payload.get("rerank_active", False),
                "input_count": payload.get("input_count", 0),
                "output_count": payload.get("output_count", 0),
                "top_k": payload.get("top_k", 0),
                "top_final_score": payload.get("top_final_score", 0.0),
                "score_span": payload.get("score_span", 0.0),
                "top_reasons": list(payload.get("top_reasons") or [])[:3],
                "top_score_breakdown_avg": dict(payload.get("top_score_breakdown_avg") or {}),
            }
    return summary


def _tool_trace_summary(tool_results: list[object]) -> dict:
    summary = {
        "memory": {},
        "map": {},
        "heat": {},
        "ugc": {},
    }
    memory = _memory_trace_summary(tool_results)
    if memory:
        summary["memory"] = memory
    for item in tool_results:
        data = item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item) if isinstance(item, dict) else {}
        tool = str(data.get("tool") or "")
        payload = _tool_payload(data)
        if tool == "map_distance_matrix":
            summary["map"] = {
                "status": data.get("status", "unknown"),
                "confidence": data.get("confidence", 0.0),
                "provider": payload.get("provider"),
                "mode": payload.get("mode"),
                "segment_count": payload.get("segment_count", len(payload.get("segments") or [])),
                "total_distance_km": payload.get("total_distance_km", 0.0),
                "total_duration_min": payload.get("total_duration_min", 0),
                "fallback_segments": payload.get("fallback_segment_count", 0),
            }
        elif tool == "heat_signal":
            summary["heat"] = {
                "status": data.get("status", "unknown"),
                "confidence": data.get("confidence", 0.0),
                "analyzed_count": payload.get("analyzed_count", 0),
                "high_queue_count": payload.get("high_queue_count", 0),
                "high_crowd_count": payload.get("high_crowd_count", 0),
                "max_heat_score": payload.get("max_heat_score", 0.0),
                "average_heat_score": payload.get("average_heat_score", 0.0),
            }
        elif tool == "ugc_signal":
            summary["ugc"] = {
                "status": data.get("status", "unknown"),
                "confidence": data.get("confidence", 0.0),
                "noise_risk": data.get("noise_risk", "unknown"),
                "analyzed_count": payload.get("analyzed_count", 0),
                "explicit_signal_count": payload.get("explicit_signal_count", 0),
                "keyword_fallback_count": payload.get("keyword_fallback_count", 0),
                "signal_quality": payload.get("signal_quality", 0.0),
                "warning_ratio": payload.get("warning_ratio", 0.0),
                "warning_counts": dict(payload.get("warning_counts") or {}),
                "explanation_hints": list(payload.get("explanation_hints") or [])[:3],
                "aspect_summary": dict(payload.get("aspect_summary") or {}),
            }
    return summary


def _build_workflow_trace(planned_route: dict, explanation: str, intent: ParsedIntent | None = None) -> dict:
    coordinator = dict(planned_route.get("coordinator", {}) or {})
    if not coordinator:
        coordinator = {
            "execution_plan": planned_route.get("execution_plan", {}),
            "tool_results": planned_route.get("tool_results", []),
            "route_attempts": planned_route.get("route_attempts", []),
        }
    coordinator.setdefault("route_attempts", planned_route.get("route_attempts", []))
    coordinator.setdefault("execution_plan", planned_route.get("execution_plan", {}))
    coordinator.setdefault("tool_results", planned_route.get("tool_results", []))
    coordinator.setdefault("route_quality", planned_route.get("route_quality", {}))
    coordinator.setdefault("quality_report", planned_route.get("quality_report", {}))
    tool_results = list(coordinator.get("tool_results", []) or [])
    tool_summary = _tool_trace_summary(tool_results)
    retrieval = _retrieval_trace_summary(tool_results)
    workflow = {
        "coordinator": coordinator,
        "execution_plan": coordinator.get("execution_plan", {}),
        "tool_results": tool_results,
        "intent": _intent_trace_summary(intent) if intent is not None else {},
        "intent_ir": build_intent_ir(intent).model_dump(mode="json") if intent is not None else {},
        "memory": tool_summary.get("memory", {}),
        "retrieval": retrieval,
        "tools": {
            "map": tool_summary.get("map", {}),
            "heat": tool_summary.get("heat", {}),
            "ugc": tool_summary.get("ugc", {}),
        },
        "route_attempts": coordinator.get("route_attempts", []),
        "route_quality": coordinator.get("route_quality", {}),
        "quality_report": coordinator.get("quality_report", {}),
        "stages": [],
        "explanation": explanation,
    }
    workflow["stages"] = _workflow_stages(workflow, explanation)
    return workflow


def generate_response(
    intent: ParsedIntent,
    ranked_pois: list[dict],
    planned_route: dict,
    explanation: str | None = None,
    diagnostics: RouteDiagnostics | None = None,
) -> RouteResponse:
    """
    生成标准的路线规划响应

    参数：
        intent: 用户意图
        ranked_pois: 评分后的POI列表
        planned_route: 路线规划结果
        explanation: 自然语言解释文本（可选）

    返回：
        RouteResponse: 标准化的响应对象
    """
    main_stops = planned_route.get("main", [])
    variants = planned_route.get("variants", [])
    stats = planned_route.get("stats", {})
    route_stats = _route_stats(main_stops)
    selected_poi_ids = planned_route.get("selected_poi_ids", [])
    modification_trace = _modification_trace(intent, planned_route)
    rank_by_poi_id = {
        str(item.get("poi").id): item
        for item in ranked_pois
        if item.get("poi") is not None and getattr(item.get("poi"), "id", None)
    }
    normalized_stops = _normalize_route_stops(main_stops, intent, rank_by_poi_id)
    intent_summary = build_intent_summary(intent, getattr(intent, "original_query", "") or "")
    route_options = _route_options(main_stops, variants, intent, rank_by_poi_id, explanation or "")
    map_preview = _build_map_preview_for_stops(main_stops, explanation or "")
    workflow_trace = _build_workflow_trace(planned_route, explanation or "", intent)
    route_quality = dict(planned_route.get("route_quality", {}) or {})
    quality_warnings = [str(item) for item in route_quality.get("warnings", []) or []]
    warnings = list(dict.fromkeys([*_warnings(main_stops, intent), *quality_warnings]))

    return RouteResponse(
        title="城市路线",
        summary=explanation or "",
        original_query=getattr(intent, "original_query", None),
        intent_summary=intent_summary,
        parse_source=getattr(intent, "parse_source", "local"),
        applied_preferences=collect_preference_labels(intent),
        intent=intent,
        main_stops=main_stops,
        stops=normalized_stops,
        variants=variants,
        ranked_pois=ranked_pois,
        explanation=explanation or "",
        route_explanation=explanation or "",
        stats=stats,
        total_cost=route_stats["total_cost"],
        total_duration=route_stats["total_duration"] + route_stats["total_travel"],
        total_distance=route_stats["total_distance"],
        poi_count=route_stats["poi_count"],
        covered_types=route_stats["covered_types"],
        map_preview=map_preview,
        route_options=route_options,
        strategy_type=route_options[0]["strategy_type"] if route_options else None,
        route_score=route_options[0]["route_score"] if route_options else None,
        travel_time_ratio=round(route_stats["total_travel"] / max(route_stats["total_duration"] + route_stats["total_travel"], 1), 3),
        warnings=warnings,
        workflow_trace=workflow_trace,
        trace={
            "intent_trace": _intent_trace_summary(intent),
            "intent_ir": build_intent_ir(intent).model_dump(mode="json"),
            "parse_source": getattr(intent, "parse_source", "local"),
            "recognized_signals": getattr(intent, "recognized_signals", []),
            "unclassified_clues": getattr(intent, "unclassified_clues", []),
            "hard_constraints": getattr(intent, "hard_constraints", []),
            "preferences": getattr(intent, "preferences", []),
            "soft_preferences": getattr(intent, "soft_preferences", []),
            "context_bias": getattr(intent, "context_bias", []),
            "profile_bias": getattr(intent, "profile_bias", []),
            "avoid": getattr(intent, "avoid", []),
            "required_categories": getattr(intent, "required_categories", []),
            "ordered_stages": getattr(intent, "ordered_stages", []),
            "candidate_count": len(ranked_pois),
            "ranking_candidate_count": len(ranked_pois),
            "selected_poi_ids": selected_poi_ids,
            "modification": modification_trace,
            "area_clusters": planned_route.get("area_clusters", route_stats.get("area_clusters", [])),
            "route_stats": route_stats,
            "map_provider": map_preview.get("provider") if isinstance(map_preview, dict) else "local",
            "map_enabled": bool(map_preview.get("enabled")) if isinstance(map_preview, dict) else False,
            "planning_distance_matrix": planned_route.get("planning_distance_matrix", {}),
            "route_quality": route_quality,
        },
        diagnostics=diagnostics,
    )


def generate_clarification_response(
    intent: ParsedIntent,
    question: str | ClarificationDecision,
    options: list[str] | None = None,
    *,
    reason: str | None = None,
    diagnostics: RouteDiagnostics | None = None,
) -> RouteResponse:
    """Generate a lightweight clarification response."""

    if isinstance(question, ClarificationDecision):
        decision = question
        question = decision.question
        options = list(decision.options)
        reason = reason or decision.reason

    summary = reason or "当前需求还不够明确，先补一个最关键的问题再继续。"
    workflow_trace = {
        "coordinator": {
            "decision_log": [
                {
                    "stage": "understanding",
                    "action": "ask_clarification",
                    "reason": summary,
                },
                {
                    "stage": "execution_plan",
                    "action": "ask_clarification",
                    "reason": summary,
                },
                {
                    "stage": "clarification",
                    "action": "ask_clarification",
                    "reason": summary,
                },
            ],
            "execution_plan": {
                "required_steps": ["intent", "clarification"],
                "required_data": [{"name": "intent_schema"}],
                "optional_data": [],
                "skipped_tools": [
                    {"tool": "map_distance_matrix", "reason": "Clarification first."},
                    {"tool": "ugc_signal", "reason": "Clarification first."},
                    {"tool": "weather", "reason": "Clarification first."},
                ],
                "skipped_data": [
                    {"tool": "poi_candidates", "reason": "Clarification first."},
                    {"tool": "profile_memory", "reason": "Clarification first."},
                    {"tool": "ugc_signals", "reason": "Clarification first."},
                ],
            },
        },
        "execution_plan": {
            "required_steps": ["intent", "clarification"],
            "required_data": [{"name": "intent_schema"}],
            "optional_data": [],
            "skipped_tools": [
                {"tool": "map_distance_matrix", "reason": "Clarification first."},
                {"tool": "ugc_signal", "reason": "Clarification first."},
                {"tool": "weather", "reason": "Clarification first."},
            ],
            "skipped_data": [
                {"tool": "poi_candidates", "reason": "Clarification first."},
                {"tool": "profile_memory", "reason": "Clarification first."},
                {"tool": "ugc_signals", "reason": "Clarification first."},
            ],
        },
        "stages": [
            {"stage": "input"},
            {"stage": "understanding"},
            {"stage": "execution_plan"},
            {"stage": "clarification"},
        ],
    }
    return RouteResponse(
        intent=intent,
        main_stops=[],
        variants=[],
        ranked_pois=[],
        explanation=summary,
        summary=str(question),
        title="需要补充一点信息",
        workflow_trace=workflow_trace,
        diagnostics=diagnostics
        or RouteDiagnostics(
            task_hint=RouteTaskHint.ROUTE_MODIFICATION if getattr(intent, "current_route", None) is not None else RouteTaskHint.INTENT_EXTRACTION,
            parse_source=getattr(intent, "parse_source", "local"),
            clarification_needed=True,
            clarification_question=str(question),
            clarification_reason=reason or summary,
        ),
        clarification_needed=True,
        clarification_question=str(question),
        clarification_options=list(options or []),
        clarification_reason=reason or summary,
        stats={},
    )


def generate_route_explanation(intent: ParsedIntent, stops: list[RouteStop]) -> str:
    """
    生成路线的自然语言说明

    参数：
        intent: 用户意图
        stops: 路线站点列表

    返回：
        str: 自然语言说明文本
    """
    if not stops:
        return "没有找到合适的路线"

    # 统计信息
    total_visit = sum(s.poi.visit_duration for s in stops)
    total_travel = sum(s.travel_to_next_min for s in stops)
    total_cost = sum(s.poi.price for s in stops)

    lines = []
    lines.append(f"为你规划了一条{len(stops)}站的路线")
    lines.append(f"总游览时间：{total_visit}分钟，交通时间：{total_travel}分钟")
    if total_cost > 0:
        lines.append(f"预计花费：约{total_cost}元")

    return "，".join(lines) + "。"


def maybe_truncate_route_explanation(explanation: str, query: str | None = None, *, max_length: int | None = None) -> str:
    """Keep the default route explanation concise."""

    text = (explanation or "").strip()
    if not text:
        return ""
    if max_length is None:
        max_length = int((ROUTE_POLICY.get("explanation") or {}).get("max_length", 80) or 80)
    if len(text) <= max_length:
        return text
    if max_length <= 1:
        return text[:max_length]
    return text[: max_length - 1].rstrip("，,；;。 ") + "…"
