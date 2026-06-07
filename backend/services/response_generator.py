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
        warnings=_warnings(main_stops, intent),
        trace={
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
    return RouteResponse(
        intent=intent,
        main_stops=[],
        variants=[],
        ranked_pois=[],
        explanation=summary,
        summary=str(question),
        title="需要补充一点信息",
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
