"""
路线规划服务模块
=================

本模块负责生成完整的出行路线，是系统的核心服务之一。

主要功能：
- 从候选POI中选择并组合成路线
- 计算POI之间的路线距离和时间
- 安排POI的时间和顺序
- 提供多种路线变体（平衡、偏好、紧凑）
- 评分路线并选择最优方案

作者：美团智能路线规划团队
"""

from __future__ import annotations

import math
import random
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from core.schemas import POI, ParsedIntent, RouteStop
from services import map_service


# 每公里的默认步行时间（分钟）
DEFAULT_WALKING_TIME_PER_KM = 12
BEAM_SIZE = 8
BEAM_CANDIDATE_LIMIT = 30


def _time_to_minutes(value: str | int | None) -> int:
    if value is None:
        return 14 * 60
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return 14 * 60
    import re

    match = re.search(r"(\d{1,2}):(\d{2})", text)
    if match:
        return int(match.group(1)) * 60 + int(match.group(2))
    match = re.search(r"(\d{1,2})", text)
    if not match:
        return 14 * 60
    hour = int(match.group(1))
    if any(token in text for token in ("下午", "晚上", "中午")) and hour < 12:
        hour += 12
    return hour * 60


@dataclass
class _RouteOption:
    """
    路线选项数据类

    用于存储一种路线变体的信息，包括：
    - stops: 路线中的POI列表
    - name: 路线名称（如"平衡版"）
    - score: 路线得分
    """

    stops: list[POI]
    name: str
    score: float = 0.0


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    使用Haversine公式计算两点之间的地面距离（公里）

    参数：
        lat1, lon1: 第一点的经纬度
        lat2, lon2: 第二点的经纬度

    返回：
        float: 两点之间的距离（公里）
    """
    # 地球半径（公里）
    R = 6371.0
    # 角度转弧度
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    # 计算Haversine公式
    a = (math.sin(delta_phi / 2) ** 2) + (
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _simple_estimate_distance(poi_a: POI, poi_b: POI) -> float:
    """
    使用Haversine公式简单估算两点之间的距离（公里）

    参数：
        poi_a: 第一个POI
        poi_b: 第二个POI

    返回：
        float: 两点之间的距离（公里）
    """
    return _haversine_distance(poi_a.lat, poi_a.lng, poi_b.lat, poi_b.lng)


def _simple_estimate_travel_time(poi_a: POI, poi_b: POI) -> int:
    """
    简单估算两点之间的步行时间（分钟）

    基于距离和默认步行速度计算

    参数：
        poi_a: 第一个POI
        poi_b: 第二个POI

    返回：
        int: 估算的步行时间（分钟）
    """
    dist = _simple_estimate_distance(poi_a, poi_b)
    return int(round(dist * DEFAULT_WALKING_TIME_PER_KM))


def _estimate_travel_time(poi_a: POI, poi_b: POI, intent: ParsedIntent) -> int:
    dist = _simple_estimate_distance(poi_a, poi_b)
    mode = str(getattr(intent, "transport_mode", "mixed") or "mixed")
    if mode == "walking":
        return int(round(dist * 14))
    if mode == "metro":
        return int(round(dist * 7 + 12))
    if mode == "taxi":
        return int(round(dist * 4 + 8))
    if dist <= 1.2:
        return int(round(dist * 12))
    return int(round(min(dist * 7 + 12, dist * 4 + 10)))


def _transport_distance_score(dist_km: float, intent: ParsedIntent) -> float:
    mode = str(getattr(intent, "transport_mode", "mixed") or "mixed")
    if mode == "walking":
        return max(0.0, 1.0 - dist_km / 2.5)
    if mode == "metro":
        return max(0.0, 1.0 - max(dist_km - 1.0, 0.0) / 8.0)
    if mode == "taxi":
        return max(0.0, 1.0 - max(dist_km - 2.0, 0.0) / 10.0)
    return max(0.0, 1.0 - dist_km / 5.0)


def _parse_clock_minutes(value: str | None) -> int | None:
    if not value:
        return None
    import re

    match = re.search(r"(\d{1,2}):(\d{2})", str(value))
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour == 24 and minute == 0:
        return 24 * 60
    if hour > 24 or minute >= 60:
        return None
    return hour * 60 + minute


def _business_window(poi: POI) -> tuple[int, int] | None:
    text = str(getattr(poi, "business_hours", "") or "").strip()
    if not text:
        return None
    import re

    match = re.search(r"(\d{1,2}:\d{2})\s*[-~至]\s*(\d{1,2}:\d{2})", text)
    if not match:
        return None
    start = _parse_clock_minutes(match.group(1))
    end = _parse_clock_minutes(match.group(2))
    if start is None or end is None:
        return None
    if end <= start:
        end += 24 * 60
    return start, end


def _open_score(poi: POI, arrival_min: int, departure_min: int) -> float:
    window = _business_window(poi)
    if window is None:
        return 0.75
    start, end = window
    arrival = arrival_min % (24 * 60)
    departure = departure_min % (24 * 60)
    if departure < arrival:
        departure += 24 * 60
    if arrival < start and start - arrival <= 60:
        return 0.65
    if arrival >= start and departure <= end:
        return 1.0
    if arrival >= start and arrival < end:
        return 0.55
    return 0.05


def _visit_schedule(route: list[POI], intent: ParsedIntent) -> list[tuple[POI, int, int]]:
    schedule: list[tuple[POI, int, int]] = []
    current = _time_to_minutes(intent.start_time)
    for index, poi in enumerate(route):
        end = current + int(poi.visit_duration or 0)
        schedule.append((poi, current, end))
        if index < len(route) - 1:
            current = end + _estimate_travel_time(poi, route[index + 1], intent)
    return schedule


def _route_travel_time(route: list[POI], intent: ParsedIntent) -> int:
    return sum(_estimate_travel_time(route[i], route[i + 1], intent) for i in range(len(route) - 1)) if len(route) > 1 else 0


def _route_cost(route: list[POI]) -> float:
    return sum(float(getattr(poi, "price", 0.0) or 0.0) for poi in route)


def _budget_fit_score(route: list[POI], intent: ParsedIntent) -> float:
    budget = getattr(intent, "budget", None)
    if not budget:
        return 0.8
    total = _route_cost(route)
    if total <= float(budget):
        return 1.0
    return max(0.0, 1.0 - (total - float(budget)) / max(float(budget), 1.0))


def _poi_area_cluster(poi: POI) -> str:
    return str(getattr(poi, "area_cluster", None) or getattr(poi, "business_area", None) or getattr(poi, "district", None) or "")


def _poi_matches_text(poi: POI, text: str) -> bool:
    return _poi_text_match_score(poi, text, include_area=True) > 0


def _poi_text_match_score(poi: POI, text: str, *, include_area: bool = True) -> int:
    needle = str(text or "").strip().lower()
    if not needle:
        return 0

    weighted_fields = [
        (poi.name or "", 100),
        (poi.address or "", 80),
        (" ".join(poi.tags or []), 70),
        (" ".join(poi.review_keywords or []), 50),
        (poi.district or "", 20),
    ]
    if include_area:
        weighted_fields.extend(
            [
                (poi.business_area or "", 30),
                (poi.area_label or "", 30),
            ]
        )

    best = 0
    for value, weight in weighted_fields:
        haystack = value.lower()
        if needle and needle in haystack:
            best = max(best, weight)
    return best


def _route_cluster_score(route: list[POI]) -> float:
    clusters = [_poi_area_cluster(poi) for poi in route if _poi_area_cluster(poi)]
    if not clusters:
        return 0.6
    return max(clusters.count(cluster) for cluster in set(clusters)) / max(len(clusters), 1)


def _choose_anchor_cluster(ranked_pois: list[dict[str, Any]], categories: list[str]) -> str:
    target_categories = set(categories)
    if not target_categories:
        return ""

    clusters: dict[str, dict[str, Any]] = {}
    for item in ranked_pois:
        poi = item["poi"]
        cluster = _poi_area_cluster(poi)
        if not cluster or poi.category not in target_categories:
            continue
        bucket = clusters.setdefault(cluster, {"categories": set(), "score": 0.0, "count": 0})
        bucket["categories"].add(poi.category)
        bucket["score"] += float(item.get("final_score", 0.0) or 0.0)
        bucket["count"] += 1

    if not clusters:
        return ""

    def sort_key(item: tuple[str, dict[str, Any]]) -> tuple[int, float, int]:
        _, bucket = item
        coverage = len(bucket["categories"])
        avg_score = bucket["score"] / max(int(bucket["count"]), 1)
        return coverage, avg_score, int(bucket["count"])

    return max(clusters.items(), key=sort_key)[0]


def _mandatory_pois(ranked_pois: list[dict[str, Any]], intent: ParsedIntent) -> list[POI]:
    anchors: list[POI] = []
    used_ids: set[str] = set()

    def add_matches(text: str | None, *, include_area: bool = True) -> None:
        if not text:
            return
        best_item = None
        best_score = 0
        for item in ranked_pois:
            poi = item["poi"]
            if poi.id in used_ids:
                continue
            score = _poi_text_match_score(poi, text, include_area=include_area)
            if score > best_score:
                best_score = score
                best_item = poi
        if best_item is not None and best_score > 0:
            anchors.append(best_item)
            used_ids.add(best_item.id)

    add_matches(getattr(intent, "start_location", None), include_area=False)
    for item in getattr(intent, "must_include", []) or []:
        add_matches(item)
    return anchors


def _build_route_stops(selected: list[POI], intent: ParsedIntent, amap: bool = False) -> list[RouteStop]:
    """
    构建带有时序的路线站点列表

    流程：
        1. 计算POI之间的路线
        2. 安排开始时间
        3. 为每个站点分配时间

    参数：
        selected: 选择的POI列表
        intent: 用户意图
        amap: 是否使用外部地图服务

    返回：
        list[RouteStop]: 带有时间安排的路线站点列表
    """
    stops: list[RouteStop] = []
    current_time = _time_to_minutes(intent.start_time)

    def earliest_arrival(poi: POI) -> int | None:
        stages = getattr(intent, "ordered_stages", []) or []
        has_dinner = any(isinstance(stage, dict) and stage.get("kind") == "food" and "晚" in str(stage.get("label", "")) for stage in stages)
        has_night = any(isinstance(stage, dict) and stage.get("kind") == "night" for stage in stages)
        if has_dinner and poi.category == "food":
            return 17 * 60 + 30
        if has_night and poi.category == "night":
            return 18 * 60
        return None

    for i, poi in enumerate(selected):
        floor = earliest_arrival(poi)
        if floor is not None and current_time < floor:
            current_time = floor
        next_poi = selected[i + 1] if i < len(selected) - 1 else None
        travel_dist = 0.0
        travel_minutes = 0

        if next_poi:
            if amap:
                route = map_service.get_route(poi, next_poi)
                travel_dist = route.distance_km
                travel_minutes = route.duration_min
            else:
                travel_dist = _simple_estimate_distance(poi, next_poi)
                travel_minutes = _estimate_travel_time(poi, next_poi, intent)

        # 计算结束时间 = 当前时间 + 游览时间
        end_time = current_time + poi.visit_duration

        stops.append(
            RouteStop(
                poi_id=poi.id,
                poi=poi,
                start_time=current_time,
                end_time=end_time,
                travel_to_next_min=travel_minutes,
                travel_to_next_km=travel_dist,
                note="",
            )
        )
        # 更新当前时间 = 结束时间 + 下一站的交通时间
        current_time = end_time + travel_minutes

    return stops


def _build_fallback_route(
    ranked_pois: list[dict[str, Any]],
    intent: ParsedIntent,
    categories: list[str],
    weight_final: float = 0.8,
    weight_dist: float = 0.2,
    max_total_time: int | None = None,
    max_stops: int | None = None,
    shuffle: bool = True,
    exclude_ids: set[str] | None = None,
) -> list[POI]:
    """
    构建备选路线（贪心算法 + 距离优化）

    核心逻辑：
        - 确保每个必要类别至少有一个POI
        - 贪心选择下一个最佳POI（综合考虑分数和距离）
        - 不超过可用时间限制

    参数：
        ranked_pois: 评分后的POI列表
        intent: 用户意图
        categories: 必要的类别列表
        weight_final: 最终分数权重
        weight_dist: 距离权重
        max_total_time: 最大总时间限制
        shuffle: 是否打乱顺序

    返回：
        list[POI]: 选择的POI列表
    """
    if not ranked_pois:
        return []
    if max_total_time is None:
        max_total_time = intent.available_time
    exclude_ids = exclude_ids or set()
    ranked_pois = [item for item in ranked_pois if item["poi"].id not in exclude_ids]
    if not ranked_pois:
        return []

    # 按类别分组POI
    candidates_by_cat: dict[str, list[dict[str, Any]]] = {}
    for item in ranked_pois:
        cat = item["poi"].category
        if cat not in candidates_by_cat:
            candidates_by_cat[cat] = []
        candidates_by_cat[cat].append(item)
        if shuffle:
            random.shuffle(candidates_by_cat[cat])

    # 先放入起点/必去点匹配到的POI，避免硬约束只停留在解析结果中。
    selected: list[POI] = _mandatory_pois(ranked_pois, intent)
    used_ids = {poi.id for poi in selected}
    if selected and not _has_first_food_then_university(intent):
        anchor_cluster = _poi_area_cluster(selected[0])
    else:
        anchor_cluster = _choose_anchor_cluster(ranked_pois, categories)

    if _has_first_food_then_university(intent):
        target_categories = ("food", "scene", "street", "park")
        for target_category in target_categories:
            for item in ranked_pois:
                poi = item["poi"]
                if poi.id in used_ids or poi.category != target_category:
                    continue
                area_text = " ".join(
                    str(value or "")
                    for value in (
                        poi.name,
                        poi.address,
                        getattr(poi, "business_area", ""),
                        getattr(poi, "area_label", ""),
                    )
                )
                if "大学城" not in area_text:
                    continue
                selected.append(poi)
                used_ids.add(poi.id)
                break

    for cat in categories:
        if max_stops is not None and len(selected) >= max_stops:
            break
        items = candidates_by_cat.get(cat, [])
        if items:
            available_items = [item for item in items if item["poi"].id not in used_ids]
            if not available_items:
                continue
            same_cluster = [item for item in available_items if anchor_cluster and _poi_area_cluster(item["poi"]) == anchor_cluster]
            picked = same_cluster[0] if same_cluster else available_items[0]
            selected.append(picked["poi"])
            used_ids.add(picked["poi"].id)
            if not anchor_cluster:
                anchor_cluster = _poi_area_cluster(picked["poi"])

    # 如果没有选择任何POI，选评分最高的
    if not selected:
        selected = [ranked_pois[0]["poi"]]
        used_ids.add(selected[0].id)

    def route_state_score(route: list[POI]) -> float:
        if not route:
            return 0.0
        score = _score_route(route, intent, {item["poi"].id: item for item in ranked_pois})
        avg_item_score = sum(float(rank_map.get(p.id, {}).get("final_score", 0.0) or 0.0) for p in route) / max(len(route), 1)
        return 0.65 * score + 0.35 * avg_item_score

    rank_map = {item["poi"].id: item for item in ranked_pois}
    beam: list[list[POI]] = [selected]
    pool = ranked_pois[:BEAM_CANDIDATE_LIMIT]

    while True:
        expanded: list[list[POI]] = []
        for route in beam:
            if max_stops is not None and len(route) >= max_stops:
                expanded.append(route)
                continue
            current_total = sum(int(p.visit_duration or 0) for p in route) + _route_travel_time(route, intent)
            route_ids = {poi.id for poi in route}
            last_poi = route[-1] if route else None
            added = False
            for item in pool:
                poi = item["poi"]
                if poi.id in route_ids:
                    continue
                add_travel = _estimate_travel_time(last_poi, poi, intent) if last_poi else 0
                est_total = current_total + add_travel + int(poi.visit_duration or 0)
                if est_total > max_total_time * 0.96:
                    continue
                candidate = [*route, poi]
                if getattr(intent, "budget", None) and _route_cost(candidate) > float(intent.budget) * 1.08:
                    continue
                dist_km = _simple_estimate_distance(last_poi, poi) if last_poi else 0.0
                dist_score = _transport_distance_score(dist_km, intent)
                cluster_score = 1.0 if anchor_cluster and _poi_area_cluster(poi) == anchor_cluster else 0.55
                item_score = weight_final * float(item["final_score"]) + weight_dist * dist_score + 0.08 * cluster_score
                if item_score <= 0:
                    continue
                expanded.append(candidate)
                added = True
            if not added:
                expanded.append(route)

        unique: dict[tuple[str, ...], list[POI]] = {}
        for route in expanded:
            key = tuple(p.id for p in route)
            unique.setdefault(key, route)
        next_beam = sorted(unique.values(), key=route_state_score, reverse=True)[:BEAM_SIZE]
        if {tuple(p.id for p in route) for route in next_beam} == {tuple(p.id for p in route) for route in beam}:
            break
        beam = next_beam

    best_route = max(beam, key=route_state_score)
    return _ensure_explicit_stage_coverage(
        best_route,
        ranked_pois,
        intent,
        max_total_time=max_total_time,
        max_stops=max_stops,
    )


def _max_stops_for_intent(intent: ParsedIntent) -> int | None:
    """Return a narrow stop cap for explicit route modification requests."""

    if getattr(intent, "current_route", None) is None:
        return None

    text = str(getattr(intent, "modification_query", "") or "")
    if any(token in text for token in ("少一点站点", "少点站点", "少一点站", "少点站", "少一点点", "少一点", "少点")):
        return 2
    if any(token in text for token in ("预算低一点", "预算低", "控制在", "低一点", "省钱")):
        return 2
    if any(token in text for token in ("近一点", "更近", "别太远", "太远了", "不要太远")):
        return 2
    return None


def _route_key(route: list[POI]) -> tuple[str, ...]:
    return tuple(poi.id for poi in route)


def _route_overlap(route: list[POI], other: list[POI]) -> float:
    if not route or not other:
        return 0.0
    route_ids = {poi.id for poi in route}
    other_ids = {poi.id for poi in other}
    return len(route_ids & other_ids) / max(min(len(route_ids), len(other_ids)), 1)


def _current_route_poi_ids(intent: ParsedIntent) -> set[str]:
    current_route = getattr(intent, "current_route", None)
    if not isinstance(current_route, dict):
        return set()
    stops = current_route.get("stops") or current_route.get("main_stops") or []
    if not isinstance(stops, list):
        return set()

    ids: set[str] = set()
    for stop in stops:
        if not isinstance(stop, dict):
            continue
        poi = stop.get("poi") if isinstance(stop.get("poi"), dict) else {}
        poi_id = stop.get("poi_id") or poi.get("id")
        if poi_id:
            ids.add(str(poi_id))
    return ids


def _modification_exclude_ids(intent: ParsedIntent) -> set[str]:
    text = str(getattr(intent, "modification_query", "") or "")
    if not text:
        return set()
    current_ids = _current_route_poi_ids(intent)
    if not current_ids:
        return set()
    if any(token in text for token in ("换", "替换", "不要这个", "去掉", "删掉", "不想去", "重新")):
        return current_ids
    return set()


def _has_first_food_then_university(intent: ParsedIntent) -> bool:
    stages = getattr(intent, "ordered_stages", []) or []
    if not isinstance(stages, list):
        return False
    first_food_index = None
    university_index = None
    for index, stage in enumerate(stages):
        if not isinstance(stage, dict):
            continue
        if stage.get("kind") == "food" and stage.get("position") == "first" and first_food_index is None:
            first_food_index = index
        if stage.get("kind") == "university_area" and university_index is None:
            university_index = index
    return first_food_index is not None and university_index is not None and first_food_index < university_index


def _explicit_stage_categories(intent: ParsedIntent) -> set[str]:
    """Categories explicitly requested as route stages should not disappear in beam search."""

    categories = {
        str(category)
        for category in (getattr(intent, "required_categories", []) or [])
        if category in {"library", "food", "night"}
    }
    stage_to_category = {"library": "library", "food": "food", "night": "night"}
    for stage in getattr(intent, "ordered_stages", []) or []:
        if not isinstance(stage, dict):
            continue
        category = stage_to_category.get(str(stage.get("kind") or ""))
        if category:
            categories.add(category)
    return categories


def _matches_soft_stage(poi: POI, intent: ParsedIntent) -> bool:
    for stage in getattr(intent, "ordered_stages", []) or []:
        if not isinstance(stage, dict):
            continue
        if str(stage.get("kind") or "") in {"library", "food", "night"}:
            continue
        if _stage_match_score(poi, stage) >= 0.75:
            return True
    return False


def _ensure_explicit_stage_coverage(
    route: list[POI],
    ranked_pois: list[dict[str, Any]],
    intent: ParsedIntent,
    *,
    max_total_time: int,
    max_stops: int | None = None,
) -> list[POI]:
    required = _explicit_stage_categories(intent)
    if not route or not required:
        return route

    present = {poi.category for poi in route}
    missing = [category for category in required if category not in present]
    if not missing:
        return route

    rank_map = {item["poi"].id: item for item in ranked_pois}
    updated = list(route)
    used_ids = {poi.id for poi in updated}

    for category in missing:
        candidates = [
            item["poi"]
            for item in ranked_pois
            if item["poi"].category == category and item["poi"].id not in used_ids
        ]
        if not candidates:
            continue

        anchor_cluster = _choose_anchor_cluster([{"poi": poi} for poi in updated], list(required))
        same_cluster = [poi for poi in candidates if anchor_cluster and _poi_area_cluster(poi) == anchor_cluster]
        picked = same_cluster[0] if same_cluster else candidates[0]

        candidate_route = [*updated, picked]
        can_append = max_stops is None or len(candidate_route) <= max_stops
        fits_time = (
            sum(int(poi.visit_duration or 0) for poi in candidate_route)
            + _route_travel_time(candidate_route, intent)
            <= max_total_time * 0.98
        )
        fits_budget = not getattr(intent, "budget", None) or _route_cost(candidate_route) <= float(intent.budget) * 1.08

        if can_append and fits_time and fits_budget:
            updated.append(picked)
            used_ids.add(picked.id)
            continue

        replaceable = [
            index
            for index, poi in enumerate(updated)
            if poi.category not in required and not _matches_soft_stage(poi, intent)
        ]
        if not replaceable:
            replaceable = [index for index, poi in enumerate(updated) if poi.category not in required]
        if not replaceable:
            continue

        replace_index = min(
            replaceable,
            key=lambda index: float(rank_map.get(updated[index].id, {}).get("final_score", 0.0) or 0.0),
        )
        used_ids.discard(updated[replace_index].id)
        updated[replace_index] = picked
        used_ids.add(picked.id)

    return updated


def _make_variant_distinct(
    base_route: list[POI],
    existing_routes: list[list[POI]],
    ranked_pois: list[dict[str, Any]],
    intent: ParsedIntent,
    categories: list[str],
    *,
    name: str,
    weight_final: float,
    weight_dist: float,
    max_stops: int | None,
) -> _RouteOption:
    route = base_route
    existing_ids = {poi.id for existing in existing_routes for poi in existing}

    if any(_route_key(route) == _route_key(existing) for existing in existing_routes) or any(
        _route_overlap(route, existing) >= 0.82 for existing in existing_routes
    ):
        alternative = _build_fallback_route(
            ranked_pois,
            intent,
            categories,
            weight_final=weight_final,
            weight_dist=weight_dist,
            max_stops=max_stops,
            shuffle=False,
            exclude_ids=existing_ids,
        )
        if alternative:
            route = alternative

    return _RouteOption(stops=route, name=name)


def _optimize_order_by_distance(pois: list[POI]) -> list[POI]:
    """
    使用最近邻贪心算法优化POI顺序

    核心逻辑：每次选择距离当前位置最近的POI

    参数：
        pois: POI列表

    返回：
        list[POI]: 优化后的POI列表
    """
    if len(pois) <= 1:
        return pois

    remaining = list(pois)
    # 从第一个POI开始
    result = [remaining.pop(0)]

    while remaining:
        last = result[-1]
        # 找到距离最近的下一个POI
        next_poi = min(remaining, key=lambda p: _simple_estimate_distance(last, p))
        result.append(next_poi)
        remaining.remove(next_poi)

    return result


def _stage_match_score(poi: POI, stage_kind: str) -> float:
    category = str(getattr(poi, "category", "") or "")
    area_text = " ".join(
        str(value or "")
        for value in (
            getattr(poi, "name", ""),
            getattr(poi, "address", ""),
            getattr(poi, "business_area", ""),
            getattr(poi, "area_label", ""),
            " ".join(getattr(poi, "tags", []) or []),
        )
    )
    if stage_kind == "library":
        return 1.0 if category == "library" or "图书馆" in (poi.name or "") else 0.0
    if stage_kind == "food":
        return 1.0 if category == "food" else 0.0
    if stage_kind == "night":
        return 1.0 if category == "night" else 0.0
    if stage_kind == "quiet_rest":
        if category in {"park", "scene", "coffee"}:
            return 0.85
        quiet_signal = getattr(poi, "review_signals", {}).get("quiet", 0.0) if isinstance(getattr(poi, "review_signals", None), dict) else 0.0
        if float(quiet_signal or 0.0) >= 0.45:
            return 0.75
        return 0.0
    if stage_kind == "university_area":
        if "大学城" in area_text or "小洲" in area_text or "岭南印象" in area_text or "广东科学中心" in area_text:
            return 0.65 if category == "food" else 1.0
        return 0.0
    if stage_kind == "play":
        if category in {"street", "scene", "park", "museum", "exhibition"}:
            return 0.9
        return 0.0
    return 0.0


def _apply_ordered_stages(route: list[POI], intent: ParsedIntent) -> list[POI]:
    stages = getattr(intent, "ordered_stages", []) or []
    if not route or not stages or not isinstance(stages, list):
        return route

    remaining = list(route)
    ordered: list[POI] = []
    last_items: list[POI] = []
    explicit_categories = {"library": "library", "food": "food", "night": "night"}
    stage_categories = {
        explicit_categories[str(stage.get("kind"))]
        for stage in stages
        if isinstance(stage, dict) and str(stage.get("kind")) in explicit_categories
    }

    has_later_university_stage = any(isinstance(stage, dict) and stage.get("kind") == "university_area" for stage in stages)

    for stage in stages:
        if not isinstance(stage, dict):
            continue
        kind = str(stage.get("kind") or "")
        if not kind:
            continue
        best = None
        best_score = 0.0
        for poi in remaining:
            score = _stage_match_score(poi, kind)
            if ordered:
                previous = ordered[-1]
                previous_area = _poi_area_cluster(previous)
                current_area = _poi_area_cluster(poi)
                if previous_area and current_area and previous_area == current_area:
                    score += 0.45
                distance_km = _simple_estimate_distance(previous, poi)
                score += 0.35 * _transport_distance_score(distance_km, intent)
            if kind == "food" and stage.get("position") == "first" and has_later_university_stage:
                poi_area = " ".join(
                    str(value or "")
                    for value in (
                        getattr(poi, "name", ""),
                        getattr(poi, "address", ""),
                        getattr(poi, "business_area", ""),
                        getattr(poi, "area_label", ""),
                    )
                )
                if "大学城" in poi_area:
                    score *= 0.15
            if score > best_score:
                best = poi
                best_score = score
        if best is None:
            continue
        remaining.remove(best)
        if stage.get("position") == "last":
            last_items.append(best)
        else:
            ordered.append(best)

    # Keep flexible filler stops, but do not add duplicate explicit stages like two dinners or three night-view stops.
    filtered_remaining = [poi for poi in remaining if getattr(poi, "category", "") not in stage_categories]
    max_len = max(len(stages), 1) + 1
    matched_stage_count = len(ordered) + len(last_items)
    if matched_stage_count >= len([stage for stage in stages if isinstance(stage, dict)]):
        middle_capacity = 0
    else:
        middle_capacity = max(max_len - matched_stage_count, 0)
    if last_items and ordered and getattr(ordered[-1], "category", "") == "food":
        return [*ordered[:-1], *filtered_remaining[:middle_capacity], ordered[-1], *last_items]
    return [*ordered, *filtered_remaining[:middle_capacity], *last_items]


def _score_route(route: list[POI], intent: ParsedIntent, rank_map: dict[str, dict[str, Any]]) -> float:
    """
    为一条路线打分

    评分维度：
        - 路线时长适配度
        - 总交通时间（越少越好）
        - POI平均排名（越靠前越好）
        - 类别覆盖度
        - 夜景POI是否放在晚上
        - 时间平滑度（POI游览时间是否均匀）

    参数：
        route: POI列表
        intent: 用户意图
        rank_map: POI ID到排名信息的映射

    返回：
        float: 路线得分
    """
    if not route:
        return 0.0

    total_visit = sum(p.visit_duration for p in route)
    total_travel = _route_travel_time(route, intent)
    total_time = total_visit + total_travel

    # 1. 路线时长适配度（越接近可用时间越好）
    if total_time > intent.available_time:
        time_score = max(0.2, 1 - (total_time - intent.available_time) / 60)
    else:
        ratio = total_time / intent.available_time
        time_score = min(1.0, ratio * 1.2)

    # 2. 交通效率（交通时间占比越低越好）
    travel_ratio = total_travel / max(total_time, 1)
    travel_score = max(0.3, 1 - travel_ratio * 2)

    # 3. POI平均排名（排名越靠前越好）
    ranks = [rank_map[p.id]["rank"] for p in route if p.id in rank_map]
    avg_rank = sum(ranks) / len(ranks) if ranks else 10
    rank_score = max(0.3, 1 - (avg_rank - 1) / 20)

    # 4. 类别覆盖（POI类别多样性）
    categories = {p.category for p in route}
    category_score = min(1.0, len(categories) / 4)

    # 5. 夜景POI放晚上（如果有夜景偏好）
    night_score = 0.5
    if intent.prefer_night_view:
        night_pois = [p for p in route if p.category == "night"]
        if night_pois:
            last_poi = route[-1]
            if any(np.id == last_poi.id for np in night_pois):
                night_score = 1.0
            else:
                night_score = 0.6

    # 6. 时间平滑度（POI游览时间差异不要太大）
    durations = [p.visit_duration for p in route]
    max_dur = max(durations) if durations else 1
    min_dur = min(durations) if durations else 0
    smooth_score = 1.0 - (max_dur - min_dur) / max(max_dur, 60)
    smooth_score = max(0.3, smooth_score)
    cluster_score = _route_cluster_score(route)
    budget_score = _budget_fit_score(route, intent)
    schedule = _visit_schedule(route, intent)
    open_score = sum(_open_score(poi, start, end) for poi, start, end in schedule) / max(len(schedule), 1)

    # 综合评分
    score = (
        0.18 * time_score
        + 0.18 * travel_score
        + 0.20 * rank_score
        + 0.13 * category_score
        + 0.08 * night_score
        + 0.04 * smooth_score
        + 0.05 * cluster_score
        + 0.07 * budget_score
        + 0.07 * open_score
    )
    return max(0.0, score)


def _required_category_coverage(route: list[POI], intent: ParsedIntent) -> float:
    required = set(getattr(intent, "required_categories", []) or [])
    if not required:
        return 1.0
    present = {poi.category for poi in route}
    return len(required & present) / max(len(required), 1)


def _must_include_coverage(route: list[POI], intent: ParsedIntent) -> float:
    required_terms = [str(item).strip() for item in getattr(intent, "must_include", []) or [] if str(item).strip()]
    if not required_terms:
        return 1.0

    matched = 0
    for term in required_terms:
        for poi in route:
            text = " ".join(
                str(value or "")
                for value in (
                    getattr(poi, "name", ""),
                    getattr(poi, "address", ""),
                    getattr(poi, "business_area", ""),
                    getattr(poi, "area_label", ""),
                    " ".join(getattr(poi, "tags", []) or []),
                )
            )
            if term in text:
                matched += 1
                break
    return matched / max(len(required_terms), 1)


def plan_route(
    ranked_pois: list[dict[str, Any]],
    intent: ParsedIntent,
    amap: bool = False,
) -> dict[str, Any]:
    """
    路线规划主函数

    流程：
        1. 准备POI排名映射
        2. 生成多种路线变体
        3. 优化路线顺序
        4. 评分并选择最优路线
        5. 构建最终的时间安排

    参数：
        ranked_pois: 评分后的POI列表
        intent: 用户意图
        amap: 是否使用外部地图服务

    返回：
        dict: 包含主路线、备选路线和其他信息的字典
    """
    if not ranked_pois:
        return {"main": [], "variants": []}

    # 准备POI ID到排名信息的映射
    rank_map: dict[str, dict[str, Any]] = {item["poi"].id: item for item in ranked_pois}
    # 确定必要类别
    categories = intent.required_categories or [
        item["poi"].category for item in ranked_pois[:5]
    ]
    max_stops = _max_stops_for_intent(intent)
    modification_exclude_ids = _modification_exclude_ids(intent)

    # 生成多种路线变体
    variants: list[_RouteOption] = []

    # 变体1：平衡版（默认权重）
    balanced_pois = _build_fallback_route(
        ranked_pois,
        intent,
        categories,
        weight_final=0.7,
        weight_dist=0.3,
        max_stops=max_stops,
        shuffle=False,
        exclude_ids=modification_exclude_ids,
    )
    variants.append(_RouteOption(stops=balanced_pois, name="平衡版"))

    # 变体2：偏好优先版（更看重评分）
    pref_pois = _build_fallback_route(
        ranked_pois,
        intent,
        categories,
        weight_final=0.95,
        weight_dist=0.05,
        max_stops=max_stops,
        shuffle=False,
        exclude_ids=modification_exclude_ids,
    )
    variants.append(
        _make_variant_distinct(
            pref_pois,
            [variant.stops for variant in variants],
            ranked_pois,
            intent,
            categories,
            name="偏好优先版",
            weight_final=0.95,
            weight_dist=0.05,
            max_stops=max_stops,
        )
    )

    # 变体3：紧凑版（更看重距离）
    compact_max_stops = max_stops or min(max(len(balanced_pois) - 1, 2), 3)
    compact_pois = _build_fallback_route(
        ranked_pois,
        intent,
        categories,
        weight_final=0.35,
        weight_dist=0.65,
        max_stops=compact_max_stops,
        shuffle=False,
        exclude_ids=modification_exclude_ids,
    )
    variants.append(
        _make_variant_distinct(
            compact_pois,
            [variant.stops for variant in variants],
            ranked_pois,
            intent,
            categories,
            name="紧凑少走版",
            weight_final=0.35,
            weight_dist=0.65,
            max_stops=compact_max_stops,
        )
    )

    # 对所有变体评分
    for opt in variants:
        opt.stops = _apply_ordered_stages(opt.stops, intent)
        opt.score = _score_route(opt.stops, intent, rank_map)

    # 选择得分最高的作为主路线
    variants.sort(
        key=lambda x: (_must_include_coverage(x.stops, intent), _required_category_coverage(x.stops, intent), x.score),
        reverse=True,
    )

    # 构建最终的时间安排
    main_stops = _build_route_stops(variants[0].stops, intent, amap=amap)

    # 准备变体列表
    variant_list = []
    for opt in variants[1:]:
        stops = _build_route_stops(opt.stops, intent, amap=amap)
        variant_list.append({"name": opt.name, "stops": stops})

    return {
        "main": main_stops,
        "variants": variant_list,
        "selected_poi_ids": [s.poi_id for s in main_stops],
        "area_clusters": list(dict.fromkeys(_poi_area_cluster(s.poi) for s in main_stops if _poi_area_cluster(s.poi))),
        "stats": {
            "total_visit_min": sum(s.poi.visit_duration for s in main_stops),
            "total_travel_min": sum(s.travel_to_next_min for s in main_stops),
            "total_km": sum(s.travel_to_next_km for s in main_stops),
        },
    }


def reorder_route(stops: list[RouteStop], intent: ParsedIntent) -> list[RouteStop]:
    """
    重排路线顺序（用于用户调整后的重新规划）

    参数：
        stops: 当前的路线站点列表
        intent: 用户意图

    返回：
        list[RouteStop]: 重排后的路线站点列表
    """
    if len(stops) <= 1:
        return stops

    # 优化顺序
    pois = [s.poi for s in stops]
    ordered = _optimize_order_by_distance(pois)

    # 重建时间安排
    return _build_route_stops(ordered, intent, amap=False)


def modify_route(
    current_stops: list[RouteStop],
    intent: ParsedIntent,
    remove_ids: list[str] | None = None,
    add_pois: list[POI] | None = None,
    amap: bool = False,
) -> list[RouteStop]:
    """
    修改路线（删除或添加POI）

    参数：
        current_stops: 当前路线站点列表
        intent: 用户意图
        remove_ids: 要删除的POI ID列表
        add_pois: 要添加的POI列表
        amap: 是否使用外部地图服务

    返回：
        list[RouteStop]: 修改后的路线站点列表
    """
    remove_ids = remove_ids or []
    add_pois = add_pois or []

    # 先删除指定POI
    new_pois = [s.poi for s in current_stops if s.poi_id not in remove_ids]
    # 再添加新POI
    new_pois.extend(add_pois)

    # 优化顺序
    ordered = _optimize_order_by_distance(new_pois)
    # 重建时间安排
    return _build_route_stops(ordered, intent, amap=amap)
