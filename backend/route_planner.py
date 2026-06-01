from __future__ import annotations

from datetime import datetime
from math import atan2, cos, radians, sin, sqrt
from typing import Optional

import poi_ranker
import review_analyzer
from schemas import POI, ParsedIntent, RouteResponse, RouteStop

CATEGORY_LABELS = {
    "coffee": "咖啡",
    "food": "餐饮",
    "museum": "博物馆",
    "exhibition": "展览",
    "scene": "景点",
    "street": "街区",
    "shopping": "购物",
    "park": "公园",
    "night": "夜景",
}

TRANSPORT_SPEEDS = {
    "walking": 4.5,
    "taxi": 18.0,
    "metro": 12.0,
}

TRANSPORT_BASE_COST = {
    "walking": 0,
    "taxi": 8,
    "metro": 3,
}

TRANSPORT_DETOUR_FACTORS = {
    "walking": 1.35,
    "taxi": 1.45,
    "metro": 1.8,
}

PREFERENCE_LABELS = {
    "prefer_couple": "约会",
    "prefer_photo": "拍照",
    "prefer_food": "美食",
    "prefer_culture": "文化",
    "prefer_local_feature": "本地特色",
    "prefer_night_view": "夜景",
    "prefer_quiet": "安静",
    "prefer_rainy_day": "雨天",
}


def _parse_time_to_minutes(time_str: str) -> int:
    text = (time_str or "").strip()
    if not text:
        return 14 * 60

    if ":" in text:
        match = None
        import re

        match = re.search(r"(\d{1,2}):(\d{2})", text)
        if match:
            return int(match.group(1)) * 60 + int(match.group(2))

    import re

    match = re.search(r"(\d{1,2})", text)
    if not match:
        return 14 * 60

    hour = int(match.group(1))
    minute = 30 if "半" in text else 0

    if ("下午" in text or "晚上" in text or "中午" in text) and hour < 12:
        hour += 12

    return hour * 60 + minute


def _minutes_to_time(minutes: int) -> str:
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _estimate_stay_minutes(poi: POI, pace: str) -> int:
    base = float(poi.visit_duration or 90)
    factor = {"slow": 1.15, "normal": 1.0, "fast": 0.8}.get(pace, 1.0)
    adjusted = base * factor
    bounds = {
        "food": (50, 120),
        "coffee": (30, 70),
        "scene": (40, 120),
        "museum": (70, 150),
        "exhibition": (60, 120),
        "shopping": (45, 120),
        "night": (30, 70),
        "street": (30, 90),
        "park": (30, 90),
    }
    lower, upper = bounds.get(poi.category, (45, 120))
    return int(max(lower, min(upper, adjusted)))


def _calculate_distance(poi1: POI, poi2: POI) -> float:
    earth_radius_km = 6371.0
    lat1 = radians(poi1.latitude)
    lon1 = radians(poi1.longitude)
    lat2 = radians(poi2.latitude)
    lon2 = radians(poi2.longitude)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return earth_radius_km * 2 * atan2(sqrt(a), sqrt(1 - a))


def _estimate_travel(distance_km: float, mode: str) -> dict:
    detoured_distance = distance_km * TRANSPORT_DETOUR_FACTORS.get(mode, 1.35)
    speed = TRANSPORT_SPEEDS.get(mode, TRANSPORT_SPEEDS["walking"])
    duration = max(5, int(detoured_distance / max(speed, 1) * 60))
    if mode == "metro":
        duration += 12
    cost = TRANSPORT_BASE_COST.get(mode, 0)
    if mode == "taxi":
        cost = int(max(cost, detoured_distance * 2.4))
    return {
        "mode": mode,
        "distance_km": round(detoured_distance, 2),
        "duration_min": duration,
        "cost": int(cost),
    }


def _period_for_minutes(minutes: int) -> str:
    hour = (minutes % (24 * 60)) // 60
    if 6 <= hour < 10:
        return "morning"
    if 10 <= hour < 14:
        return "noon"
    if 14 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 21:
        return "evening"
    return "night"


def _category_period_score(category: str, period: str) -> float:
    scores = {
        "coffee": {"morning": 0.75, "noon": 0.75, "afternoon": 1.0, "evening": 0.65, "night": 0.35},
        "food": {"morning": 0.25, "noon": 1.0, "afternoon": 0.45, "evening": 1.0, "night": 0.65},
        "museum": {"morning": 0.85, "noon": 0.9, "afternoon": 1.0, "evening": 0.25, "night": 0.1},
        "exhibition": {"morning": 0.8, "noon": 0.9, "afternoon": 1.0, "evening": 0.35, "night": 0.1},
        "scene": {"morning": 0.8, "noon": 0.75, "afternoon": 0.9, "evening": 0.8, "night": 0.45},
        "street": {"morning": 0.55, "noon": 0.7, "afternoon": 0.95, "evening": 1.0, "night": 0.75},
        "shopping": {"morning": 0.45, "noon": 0.8, "afternoon": 0.95, "evening": 1.0, "night": 0.55},
        "park": {"morning": 0.95, "noon": 0.65, "afternoon": 0.8, "evening": 0.55, "night": 0.15},
        "night": {"morning": 0.1, "noon": 0.15, "afternoon": 0.35, "evening": 1.0, "night": 1.0},
    }
    return scores.get(category, {}).get(period, 0.65)


def _poi_time_fit(poi: POI, arrival_minutes: int) -> float:
    period = _period_for_minutes(arrival_minutes)
    if poi.best_visit_periods and period in poi.best_visit_periods:
        return 1.0
    if poi.best_visit_periods and period not in poi.best_visit_periods:
        return 0.45
    return _category_period_score(poi.category, period)


def _business_hours_warning(poi: POI, arrival_minutes: int) -> Optional[str]:
    if not poi.business_hours:
        return None
    text = poi.business_hours
    if "全天" in text or "24" in text:
        return None

    import re

    match = re.search(r"(\d{1,2}):(\d{2})\s*[-~至]\s*(\d{1,2}):(\d{2})", text)
    if not match:
        return None

    start = int(match.group(1)) * 60 + int(match.group(2))
    end = int(match.group(3)) * 60 + int(match.group(4))
    current = arrival_minutes % (24 * 60)
    if end <= start:
        end += 24 * 60
        if current < start:
            current += 24 * 60
    if not (start <= current <= end):
        return f"{poi.name} 可能不在营业时间内，建议出发前确认。"
    return None


def _available_minutes(intent: ParsedIntent) -> int:
    start = _parse_time_to_minutes(intent.start_time or "14:00")
    end = _parse_time_to_minutes(intent.end_time or "21:00")
    if end <= start:
        end += 24 * 60
    return max(120, end - start)


def _target_poi_bounds(intent: ParsedIntent) -> tuple[int, int]:
    available = _available_minutes(intent)
    if intent.pace == "slow":
        return 2, 4
    if intent.pace == "fast":
        return 3, 5
    if available <= 240:
        return 2, 3
    if available <= 420:
        return 3, 4
    return 3, 5


def _rank_lookup(ranked_results: list[dict]) -> dict[str, dict]:
    return {item["poi"].id: item for item in ranked_results}


def _poi_score(poi: POI, ranked_lookup: dict[str, dict]) -> float:
    item = ranked_lookup.get(poi.id)
    return float(item.get("final_score", 0.5)) if item else 0.5


def _dedupe_pois(pois: list[POI]) -> list[POI]:
    seen: set[str] = set()
    result: list[POI] = []
    for poi in pois:
        if poi.id in seen:
            continue
        seen.add(poi.id)
        result.append(poi)
    return result


def _coverage_labels(pois: list[POI], intent: ParsedIntent) -> tuple[list[str], list[str]]:
    requested: list[str] = []
    for attr, label in PREFERENCE_LABELS.items():
        if getattr(intent, attr):
            requested.append(label)
    if intent.avoid_queue:
        requested.append("少排队")
    for category in intent.required_categories:
        requested.append(CATEGORY_LABELS.get(category, category))

    covered: list[str] = []
    for label in dict.fromkeys(requested):
        if label == "约会" and any(review_analyzer.signal(p, "date") >= 0.7 for p in pois):
            covered.append(label)
        elif label == "拍照" and any(review_analyzer.signal(p, "photo") >= 0.7 for p in pois):
            covered.append(label)
        elif label == "美食" and any(p.category in {"food", "coffee"} or review_analyzer.signal(p, "food") >= 0.7 for p in pois):
            covered.append(label)
        elif label == "文化" and any(p.category in {"museum", "exhibition"} or review_analyzer.signal(p, "culture") >= 0.7 for p in pois):
            covered.append(label)
        elif label == "本地特色" and any(review_analyzer.signal(p, "local_feature") >= 0.7 for p in pois):
            covered.append(label)
        elif label == "夜景" and any(p.category == "night" or review_analyzer.signal(p, "photo") >= 0.75 for p in pois):
            covered.append(label)
        elif label == "安静" and any(review_analyzer.signal(p, "quiet") >= 0.65 for p in pois):
            covered.append(label)
        elif label == "雨天" and any(review_analyzer.signal(p, "rainy_day") >= 0.7 for p in pois):
            covered.append(label)
        elif label == "少排队" and all(review_analyzer.signal(p, "queue_risk") <= 0.65 for p in pois):
            covered.append(label)
        elif any(CATEGORY_LABELS.get(p.category, p.category) == label for p in pois):
            covered.append(label)

    uncovered = [label for label in dict.fromkeys(requested) if label not in covered]
    return covered, uncovered


def _route_score(
    pois: list[POI],
    ranked_lookup: dict[str, dict],
    intent: ParsedIntent,
    total_duration: int,
    total_travel: int,
    total_cost: int,
    avg_time_fit: float = 0.7,
) -> float:
    if not pois:
        return 0.0

    available = _available_minutes(intent)
    avg_poi_score = sum(_poi_score(poi, ranked_lookup) for poi in pois) / len(pois)
    covered, uncovered = _coverage_labels(pois, intent)
    coverage_score = len(covered) / max(1, len(covered) + len(uncovered))
    diversity_score = len({poi.category for poi in pois}) / len(pois)
    efficiency_score = max(0.0, 1 - total_travel / max(1, total_duration))

    if total_duration <= available:
        time_fit = max(0.35, 1 - abs(available - total_duration) / max(available, 1))
        overtime_penalty = 0.0
    else:
        time_fit = max(0.0, available / max(total_duration, 1))
        overtime_penalty = min(1.0, (total_duration - available) / 120)

    if intent.budget:
        budget_fit = 1.0 if total_cost <= intent.budget else max(0.0, intent.budget / max(total_cost, 1))
    else:
        budget_fit = 0.75

    avg_queue = sum(poi.queue_level / 5 for poi in pois) / len(pois)
    queue_penalty = avg_queue if intent.avoid_queue else avg_queue * 0.35
    value = (
        0.32 * avg_poi_score
        + 0.22 * coverage_score
        + 0.09 * time_fit
        + 0.08 * avg_time_fit
        + 0.12 * diversity_score
        + 0.10 * efficiency_score
        + 0.07 * budget_fit
        - 0.12 * queue_penalty
        - 0.10 * overtime_penalty
    )
    return max(0.0, min(1.0, value))


def _compact_order(pois: list[POI], mode: str) -> list[POI]:
    if len(pois) <= 2:
        return pois

    remaining = pois[:]
    ordered = [remaining.pop(0)]
    while remaining:
        current = ordered[-1]
        next_poi = min(
            remaining,
            key=lambda poi: _estimate_travel(_calculate_distance(current, poi), mode)["duration_min"],
        )
        ordered.append(next_poi)
        remaining.remove(next_poi)
    return ordered


def _time_aware_order(pois: list[POI], intent: ParsedIntent) -> list[POI]:
    if len(pois) <= 2:
        return pois

    start = _parse_time_to_minutes(intent.start_time or "14:00")

    def base_slot(poi: POI) -> int:
        if poi.category in {"museum", "exhibition", "scene", "park"}:
            return 0
        if poi.category == "coffee":
            return 1
        if poi.category in {"street", "shopping"}:
            return 2
        if poi.category == "food":
            return 3
        if poi.category == "night":
            return 4
        return 2

    ordered = sorted(
        pois,
        key=lambda poi: (
            base_slot(poi),
            -_poi_time_fit(poi, start + base_slot(poi) * 75),
        ),
    )
    if start >= 17 * 60:
        ordered = sorted(ordered, key=lambda poi: 0 if poi.category == "food" else base_slot(poi))
    return ordered


def _intent_slot_priority(poi: POI, intent: ParsedIntent) -> float:
    score = 0.0
    if intent.prefer_food and poi.category == "food":
        score += 1.0
    if intent.prefer_night_view and poi.category == "night":
        score += 1.0
    if intent.prefer_culture and poi.category in {"museum", "exhibition"}:
        score += 1.0
    if intent.prefer_photo:
        score += review_analyzer.signal(poi, "photo")
    if intent.prefer_couple:
        score += review_analyzer.signal(poi, "date")
    if intent.prefer_quiet:
        score += review_analyzer.signal(poi, "quiet")
    return score


def _build_variant_candidates(ranked_results: list[dict], intent: ParsedIntent) -> list[tuple[str, list[POI]]]:
    ranked_pois = [item["poi"] for item in ranked_results]
    ranked_lookup = _rank_lookup(ranked_results)
    _, max_count = _target_poi_bounds(intent)

    required_first: list[POI] = []
    for required in intent.required_categories:
        match = next((poi for poi in ranked_pois if poi.category == required), None)
        if match:
            required_first.append(match)

    balanced = _time_aware_order(_dedupe_pois(required_first + ranked_pois)[:max_count], intent)

    focused_pool = sorted(
        ranked_pois,
        key=lambda poi: (_intent_slot_priority(poi, intent), _poi_score(poi, ranked_lookup)),
        reverse=True,
    )
    preference_focused = _time_aware_order(_dedupe_pois(required_first + focused_pool + ranked_pois)[:max_count], intent)

    mode = intent.transport_mode if intent.transport_mode in {"walking", "taxi", "metro"} else "walking"
    compact_seed = _dedupe_pois(required_first + ranked_pois[: min(len(ranked_pois), max_count + 2)])
    compact = _compact_order(compact_seed[:max_count], mode)

    return [
        ("balanced", balanced),
        ("preference_focused", preference_focused),
        ("compact", compact),
    ]


def _build_stops(
    selected_pois: list[POI],
    ranked_results: list[dict],
    intent: ParsedIntent,
) -> tuple[list[RouteStop], int, int, float, int]:
    ranked_lookup = _rank_lookup(ranked_results)
    current_minutes = _parse_time_to_minutes(intent.start_time or "14:00")
    mode = intent.transport_mode if intent.transport_mode in {"walking", "taxi", "metro"} else "walking"
    stops: list[RouteStop] = []

    for index, poi in enumerate(selected_pois):
        travel_info = None
        if index > 0:
            distance = _calculate_distance(selected_pois[index - 1], poi)
            travel_info = _estimate_travel(distance, mode)
            current_minutes += travel_info["duration_min"]

        stay_minutes = _estimate_stay_minutes(poi, intent.pace)
        arrival = current_minutes
        departure = arrival + stay_minutes

        ranked_item = ranked_lookup.get(poi.id)
        reason = ranked_item["recommend_reason"] if ranked_item else "综合匹配度较高。"

        risk_alert: Optional[str] = None
        queue_risk = review_analyzer.signal(poi, "queue_risk", poi.queue_level / 5)
        time_fit = _poi_time_fit(poi, arrival)
        business_warning = _business_hours_warning(poi, arrival)
        if business_warning:
            risk_alert = business_warning
        elif queue_risk >= 0.75 and not intent.avoid_queue:
            risk_alert = "高峰时段可能需要排队，建议错峰前往。"
        elif poi.indoor_outdoor == "outdoor" and intent.prefer_rainy_day:
            risk_alert = "如果下雨，户外体验可能受影响。"
        elif time_fit < 0.4:
            risk_alert = "这个点和当前到达时段不完全匹配，建议作为备选调整。"

        stops.append(
            RouteStop(
                poi=poi,
                arrival_time=_minutes_to_time(arrival),
                departure_time=_minutes_to_time(departure),
                stay_minutes=stay_minutes,
                reason=reason,
                risk_alert=risk_alert,
                travel_from_previous=travel_info,
            )
        )
        current_minutes = departure

    total_cost = sum(stop.poi.price for stop in stops) + sum(
        (stop.travel_from_previous or {}).get("cost", 0) for stop in stops
    )
    total_duration = sum(stop.stay_minutes for stop in stops) + sum(
        (stop.travel_from_previous or {}).get("duration_min", 0) for stop in stops
    )
    total_distance = sum((stop.travel_from_previous or {}).get("distance_km", 0.0) for stop in stops)
    total_travel = sum((stop.travel_from_previous or {}).get("duration_min", 0) for stop in stops)
    return stops, int(total_cost), int(total_duration), float(total_distance), int(total_travel)


def _route_strategy(intent: ParsedIntent) -> str:
    if intent.prefer_couple:
        return "约会方案"
    if intent.prefer_photo:
        return "拍照方案"
    if intent.budget and intent.budget <= 150:
        return "高性价比方案"
    if intent.pace == "slow":
        return "轻松方案"
    return "稳妥方案"


def _build_explanation(stops: list[RouteStop], intent: ParsedIntent) -> str:
    if not stops:
        return "当前条件下没有筛选到合适的路线。可以放宽预算、时间或偏好后再试一次。"

    covered = [CATEGORY_LABELS.get(stop.poi.category, stop.poi.category) for stop in stops]
    unique = list(dict.fromkeys(covered))

    parts = [f"这条路线覆盖了 {len(unique)} 类体验：{'、'.join(unique)}。"]
    if intent.prefer_couple:
        parts.append("路线优先考虑约会氛围和停留节奏。")
    if intent.prefer_photo:
        parts.append("路线增加了更适合拍照打卡的点位。")
    if intent.prefer_food:
        parts.append("餐饮安排放在更关键的位置，方便衔接整体节奏。")
    if intent.budget:
        parts.append(f"整体会尽量控制在 {intent.budget} 元预算附近。")
    if intent.pace == "slow":
        parts.append("节奏会更松弛，不会安排得太赶。")
    if intent.prefer_rainy_day:
        parts.append("路线会更偏向室内或可避雨的点位。")

    parts.append(f"建议在 {stops[0].arrival_time} 左右开始，{stops[-1].departure_time} 左右结束。")
    return "".join(parts)


def generate_route(pois: list[POI], intent: ParsedIntent) -> RouteResponse:
    if not pois:
        return RouteResponse(
            title=f"{intent.city}路线建议",
            summary="当前条件下没有筛选到合适的站点，可以放宽预算、时间或偏好后再试一次。",
            total_cost=0,
            total_duration=0,
            total_distance=0.0,
            poi_count=0,
            covered_types=[],
            stops=[],
            route_explanation="暂时没有可执行路线。",
            strategy_type="待调整",
            generated_at=datetime.now().isoformat(),
        )

    ranked = poi_ranker.rank_pois(pois, intent, top_k=30)
    ranked_lookup = _rank_lookup(ranked)
    min_count, _ = _target_poi_bounds(intent)
    variants = []

    for variant_type, selected_pois in _build_variant_candidates(ranked, intent):
        selected_pois = _dedupe_pois(selected_pois)
        while len(selected_pois) > min_count:
            _, total_cost, total_duration, _, total_travel = _build_stops(selected_pois, ranked, intent)
            if total_duration <= _available_minutes(intent):
                break
            removable = selected_pois[1:] or selected_pois
            remove_id = min(removable, key=lambda poi: _poi_score(poi, ranked_lookup)).id
            selected_pois = [poi for poi in selected_pois if poi.id != remove_id]

        stops, total_cost, total_duration, total_distance, total_travel = _build_stops(selected_pois, ranked, intent)
        avg_time_fit = (
            sum(_poi_time_fit(stop.poi, _parse_time_to_minutes(stop.arrival_time)) for stop in stops) / len(stops)
            if stops
            else 0.0
        )
        score = _route_score(
            selected_pois,
            ranked_lookup,
            intent,
            total_duration=total_duration,
            total_travel=total_travel,
            total_cost=total_cost,
            avg_time_fit=avg_time_fit,
        )
        variants.append((score, variant_type, stops, total_cost, total_duration, total_distance, total_travel))

    variants.sort(key=lambda item: (-item[0], item[1]))
    route_score, variant_type, stops, total_cost, total_duration, total_distance, total_travel = variants[0]
    route_options = [
        {
            "strategy_type": {
                "balanced": "综合平衡",
                "preference_focused": "偏好优先",
                "compact": "少绕路",
            }.get(item[1], item[1]),
            "route_score": round(item[0], 4),
            "total_cost": item[3],
            "total_duration": item[4],
            "total_distance": round(item[5], 2),
            "poi_count": len(item[2]),
            "stops": [stop.poi.name for stop in item[2]],
        }
        for item in variants
    ]
    travel_time_ratio = total_travel / max(total_duration, 1)
    warnings: list[str] = []
    if total_duration > _available_minutes(intent):
        warnings.append("路线总时长超过用户时间窗口，建议减少站点或延长结束时间。")
    if travel_time_ratio > 0.35:
        warnings.append("转场时间占比较高，路线可能偏绕。")
    if any(stop.risk_alert for stop in stops):
        warnings.extend(stop.risk_alert for stop in stops if stop.risk_alert)
    covered_types = list(
        dict.fromkeys(CATEGORY_LABELS.get(stop.poi.category, stop.poi.category) for stop in stops)
    )

    summary = (
        f"为你安排了 {len(stops)} 个站点，总花费约 {total_cost} 元，"
        f"总时长约 {total_duration // 60} 小时 {total_duration % 60} 分钟，"
        f"总距离约 {round(total_distance, 1)} 公里。"
    )

    return RouteResponse(
        title=f"{intent.city}出发路线",
        summary=summary,
        total_cost=total_cost,
        total_duration=total_duration,
        total_distance=round(total_distance, 2),
        poi_count=len(stops),
        covered_types=covered_types,
        stops=stops,
        route_explanation=_build_explanation(stops, intent),
        strategy_type={
            "balanced": _route_strategy(intent),
            "preference_focused": f"{_route_strategy(intent)} · 偏好优先",
            "compact": f"{_route_strategy(intent)} · 少绕路",
        }.get(variant_type, _route_strategy(intent)),
        route_score=round(route_score, 4),
        travel_time_ratio=round(travel_time_ratio, 4),
        warnings=list(dict.fromkeys(warnings)),
        route_options=route_options,
        generated_at=datetime.now().isoformat(),
    )
