"""
POI检索服务模块
================

本模块负责从本地数据文件加载POI（兴趣点）并进行初步筛选。

主要功能：
- 从JSON文件加载POI数据
- 根据用户意图筛选城市和类别
- 返回POI对象列表

作者：美团智能路线规划团队
"""

import json
from pathlib import Path
from typing import Any

from core.schemas import POI, ParsedIntent


# 确定POI数据文件的绝对路径
# 获取当前文件所在目录，向上两级找到backend目录，再找pois.json
POI_FILE = Path(__file__).resolve().parents[1] / "pois.json"
DEFAULT_RECALL_LIMIT = 160
_POI_CACHE: list[POI] | None = None


def load_pois() -> list:
    """
    从本地文件加载原始POI数据

    返回：
        list: JSON格式的POI原始数据列表
    """
    with POI_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_poi_objects() -> list[POI]:
    global _POI_CACHE
    if _POI_CACHE is None:
        _POI_CACHE = [POI(**item) for item in load_pois()]
    return list(_POI_CACHE)


def _matches_text(poi: POI, text: str) -> bool:
    needle = str(text or "").strip().lower()
    if not needle:
        return False
    fields = [
        poi.name or "",
        poi.address or "",
        poi.business_area or "",
        poi.area_label or "",
        poi.district or "",
        " ".join(poi.tags or []),
        " ".join(poi.review_keywords or []),
    ]
    haystack = " ".join(item for item in fields if item).lower()
    return needle in haystack or any(part and part in haystack for part in needle.split())


def _text_blob(poi: POI) -> str:
    fields = [
        poi.name or "",
        poi.category or "",
        poi.sub_category or "",
        poi.description or "",
        poi.address or "",
        poi.business_area or "",
        poi.area_label or "",
        poi.district or "",
        " ".join(poi.tags or []),
        " ".join(poi.suitable_for or []),
        " ".join(poi.review_keywords or []),
        " ".join(getattr(poi, "positive_reviews", []) or []),
        " ".join(getattr(poi, "negative_reviews", []) or []),
    ]
    return " ".join(item for item in fields if item).lower()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _recall_score(poi: POI, intent: ParsedIntent) -> float:
    text = _text_blob(poi)
    score = 0.0

    required_categories = set(getattr(intent, "required_categories", []) or [])
    preferred_categories = set(getattr(intent, "preferred_categories", []) or [])
    soft_preferences = set(getattr(intent, "soft_preferences", []) or [])
    preferences = set(getattr(intent, "preferences", []) or [])
    avoids = set(getattr(intent, "avoid", []) or [])
    clues = [str(item).strip().lower() for item in getattr(intent, "unclassified_clues", []) or [] if item]
    must_include = [str(item).strip() for item in getattr(intent, "must_include", []) or [] if item]

    if poi.category in required_categories:
        score += 5.0
    if poi.category in preferred_categories:
        score += 2.0

    intent_terms = [
        *required_categories,
        *preferred_categories,
        *preferences,
        *soft_preferences,
        *clues,
        *must_include,
    ]
    for term in intent_terms:
        token = str(term or "").strip().lower()
        if token and token in text:
            score += 1.4

    if getattr(intent, "prefer_indoor", False) and poi.indoor_outdoor == "indoor":
        score += 2.0
    if getattr(intent, "prefer_outdoor", False) and poi.indoor_outdoor == "outdoor":
        score += 1.5
    if getattr(intent, "prefer_quiet", False) and int(getattr(poi, "queue_level", 3) or 3) <= 2:
        score += 1.2
    if getattr(intent, "prefer_value", False) and _safe_float(getattr(poi, "price", 0)) <= 60:
        score += 1.4
    if getattr(intent, "avoid_queue", False) and int(getattr(poi, "queue_level", 3) or 3) >= 4:
        score -= 2.2
    if "avoid_crowded" in avoids and int(getattr(poi, "queue_level", 3) or 3) >= 4:
        score -= 1.5

    budget = getattr(intent, "budget", None)
    if budget is not None:
        expected = _safe_float(budget) / max(len(required_categories), 1)
        price = _safe_float(getattr(poi, "price", 0))
        if price <= expected:
            score += 1.2
        elif price > expected * 1.8:
            score -= 1.2

    start_location = getattr(intent, "start_location", None)
    if start_location and _matches_text(poi, str(start_location)):
        score += 3.0
    if any(_matches_text(poi, item) for item in must_include):
        score += 10.0

    score += max(0.0, min((_safe_float(getattr(poi, "rating", 4.0)) - 3.8) / 1.2, 1.0))
    return score


def _sort_and_limit(candidates: list[POI], intent: ParsedIntent, limit: int) -> list[POI]:
    unique = {poi.id: poi for poi in candidates}
    return sorted(unique.values(), key=lambda poi: (-_recall_score(poi, intent), poi.id))[:limit]


def retrieve_pois(intent: ParsedIntent, limit: int = DEFAULT_RECALL_LIMIT) -> list[POI]:
    """
    根据用户意图检索并筛选POI

    筛选规则：
        1. 优先按用户指定的城市过滤
        2. 如果有必要类别，进一步按类别筛选

    参数：
        intent: ParsedIntent，解析后的用户意图

    返回：
        list[POI]: 符合条件的POI对象列表
    """
    all_pois = _load_poi_objects()
    city_pois = [poi for poi in all_pois if not intent.city or poi.city == intent.city]
    if not city_pois:
        return []

    must_include_matches: list[POI] = []
    for poi in city_pois:
        if any(_matches_text(poi, item) for item in intent.must_include):
            must_include_matches.append(poi)

    recall_sets: list[POI] = []
    category_keys = set(getattr(intent, "required_categories", []) or []) | set(getattr(intent, "preferred_categories", []) or [])
    if category_keys:
        recall_sets.extend([poi for poi in city_pois if poi.category in category_keys])

    semantic_terms = [
        *(getattr(intent, "preferences", []) or []),
        *(getattr(intent, "soft_preferences", []) or []),
        *(getattr(intent, "unclassified_clues", []) or []),
        *(getattr(intent, "must_include", []) or []),
    ]
    if semantic_terms:
        recall_sets.extend(
            [
                poi
                for poi in city_pois
                if any(str(term).strip().lower() and str(term).strip().lower() in _text_blob(poi) for term in semantic_terms)
            ]
        )

    if getattr(intent, "start_location", None):
        recall_sets.extend([poi for poi in city_pois if _matches_text(poi, str(intent.start_location))])

    recall_sets.extend(must_include_matches)

    if not recall_sets:
        recall_sets = list(city_pois)

    filtered = _sort_and_limit(recall_sets, intent, limit)

    if len(filtered) < min(limit, 40):
        by_id = {poi.id: poi for poi in filtered}
        for poi in _sort_and_limit(city_pois, intent, limit):
            by_id.setdefault(poi.id, poi)
            if len(by_id) >= limit:
                break
        filtered = list(by_id.values())

    if must_include_matches:
        by_id = {poi.id: poi for poi in filtered}
        for poi in must_include_matches:
            by_id.setdefault(poi.id, poi)
        filtered = _sort_and_limit(list(by_id.values()), intent, limit)

    return filtered
