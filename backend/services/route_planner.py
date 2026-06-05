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
    if any(token in text for token in ("??", "??", "??")) and hour < 12:
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
        amap: 是否使用高德地图API

    返回：
        list[RouteStop]: 带有时间安排的路线站点列表
    """
    stops: list[RouteStop] = []
    current_time = _time_to_minutes(intent.start_time)

    for i, poi in enumerate(selected):
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
                travel_minutes = _simple_estimate_travel_time(poi, next_poi)

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
    shuffle: bool = True,
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

    # 按类别分组POI
    candidates_by_cat: dict[str, list[dict[str, Any]]] = {}
    for item in ranked_pois:
        cat = item["poi"].category
        if cat not in candidates_by_cat:
            candidates_by_cat[cat] = []
        candidates_by_cat[cat].append(item)
        if shuffle:
            random.shuffle(candidates_by_cat[cat])

    # 确保每个必要类别至少有一个POI
    selected: list[POI] = []
    used_ids = set()
    for cat in categories:
        items = candidates_by_cat.get(cat, [])
        if items:
            picked = items[0]
            selected.append(picked["poi"])
            used_ids.add(picked["poi"].id)

    # 如果没有选择任何POI，选评分最高的
    if not selected:
        selected = [ranked_pois[0]["poi"]]
        used_ids.add(selected[0].id)

    # 计算已使用时间
    total_time = sum(p.visit_duration for p in selected)
    # 简单估算交通时间
    total_travel = sum(_simple_estimate_travel_time(selected[i], selected[i + 1]) for i in range(len(selected) - 1)) if len(selected) > 1 else 0

    # 贪心添加更多POI
    while True:
        best = None
        best_score = -1.0
        last_poi = selected[-1] if selected else None

        # 遍历所有可用POI
        for item in ranked_pois:
            poi = item["poi"]
            if poi.id in used_ids:
                continue

            # 估算添加这个POI的额外交通时间
            add_travel = _simple_estimate_travel_time(last_poi, poi) if last_poi else 0
            # 总时间预估
            est_total = total_time + poi.visit_duration + total_travel + add_travel
            if est_total > max_total_time * 0.95:
                continue

            # 计算综合分数
            dist_km = _simple_estimate_distance(last_poi, poi) if last_poi else 0.0
            # 距离归一化到[0,1]（越近越好）
            dist_score = max(0.0, 1.0 - dist_km / 5.0)
            combined = weight_final * item["final_score"] + weight_dist * dist_score

            if combined > best_score:
                best_score = combined
                best = (poi, add_travel)

        if best is None:
            break

        # 添加最佳POI
        selected.append(best[0])
        used_ids.add(best[0].id)
        total_time += best[0].visit_duration
        total_travel += best[1]

    return selected


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
    # 简单估算交通时间
    total_travel = sum(_simple_estimate_travel_time(route[i], route[i + 1]) for i in range(len(route) - 1)) if len(route) > 1 else 0
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

    # 综合评分
    score = (
        0.25 * time_score
        + 0.20 * travel_score
        + 0.25 * rank_score
        + 0.15 * category_score
        + 0.10 * night_score
        + 0.05 * smooth_score
    )
    return max(0.0, score)


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
        amap: 是否使用高德地图API

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

    # 生成多种路线变体
    variants: list[_RouteOption] = []

    # 变体1：平衡版（默认权重）
    balanced_pois = _build_fallback_route(
        ranked_pois, intent, categories, weight_final=0.7, weight_dist=0.3, shuffle=False
    )
    balanced_pois = _optimize_order_by_distance(balanced_pois)
    variants.append(_RouteOption(stops=balanced_pois, name="平衡版"))

    # 变体2：偏好优先版（更看重评分）
    pref_pois = _build_fallback_route(
        ranked_pois, intent, categories, weight_final=0.9, weight_dist=0.1, shuffle=False
    )
    pref_pois = _optimize_order_by_distance(pref_pois)
    variants.append(_RouteOption(stops=pref_pois, name="偏好优先版"))

    # 变体3：紧凑版（更看重距离）
    compact_pois = _build_fallback_route(
        ranked_pois, intent, categories, weight_final=0.5, weight_dist=0.5, shuffle=False
    )
    compact_pois = _optimize_order_by_distance(compact_pois)
    variants.append(_RouteOption(stops=compact_pois, name="紧凑版"))

    # 对所有变体评分
    for opt in variants:
        opt.score = _score_route(opt.stops, intent, rank_map)

    # 选择得分最高的作为主路线
    variants.sort(key=lambda x: -x.score)

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
        amap: 是否使用高德地图API

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
