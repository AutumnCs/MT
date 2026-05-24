from __future__ import annotations

from datetime import datetime
from math import fabs
from typing import Optional

import poi_ranker
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
    lat_diff = fabs(poi1.latitude - poi2.latitude)
    lon_diff = fabs(poi1.longitude - poi2.longitude)
    return lat_diff * 111 + lon_diff * 85


def _estimate_travel(distance_km: float, mode: str) -> dict:
    speed = TRANSPORT_SPEEDS.get(mode, TRANSPORT_SPEEDS["walking"])
    duration = max(5, int(distance_km / max(speed, 1) * 60))
    cost = TRANSPORT_BASE_COST.get(mode, 0)
    if mode == "taxi":
        cost = int(max(cost, distance_km * 2))
    return {
        "mode": mode,
        "distance_km": round(distance_km, 2),
        "duration_min": duration,
        "cost": int(cost),
    }


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


def _select_route_pois(ranked_results: list[dict], intent: ParsedIntent) -> list[POI]:
    max_pois = 4 if intent.pace == "slow" else 3
    selected: list[POI] = []
    used_categories: set[str] = set()

    for required in intent.required_categories[:2]:
        for item in ranked_results:
            poi = item["poi"]
            if poi.category == required and poi.id not in {p.id for p in selected}:
                selected.append(poi)
                used_categories.add(poi.category)
                break

    for item in ranked_results:
        if len(selected) >= max_pois:
            break
        poi = item["poi"]
        if poi.id in {p.id for p in selected}:
            continue
        if poi.category not in used_categories or len(selected) < 2:
            selected.append(poi)
            used_categories.add(poi.category)

    return selected[:max_pois]


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
    selected_pois = _select_route_pois(ranked, intent)

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

        ranked_item = next((item for item in ranked if item["poi"].id == poi.id), None)
        reason = ranked_item["recommend_reason"] if ranked_item else "综合匹配度较高。"

        risk_alert: Optional[str] = None
        if poi.queue_level >= 4 and not intent.avoid_queue:
            risk_alert = "高峰时段可能需要排队，建议错峰前往。"
        elif poi.indoor_outdoor == "outdoor" and intent.prefer_rainy_day:
            risk_alert = "如果下雨，户外体验可能受影响。"

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
        strategy_type=_route_strategy(intent),
        generated_at=datetime.now().isoformat(),
    )
