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

from core import semantic_intent
from core.route_policy import ROUTE_POLICY
from core.schemas import POI, ParsedIntent
from services import semantic_retriever


# 确定POI数据文件的绝对路径
# 获取当前文件所在目录，向上两级找到backend目录，再找pois.json
POI_FILE = Path(__file__).resolve().parents[1] / "pois.json"
DEFAULT_RECALL_LIMIT = 160
_POI_CACHE: list[POI] | None = None
RETRIEVAL_POLICY = ROUTE_POLICY.get("retrieval", {})
LANE_CAPS = dict(RETRIEVAL_POLICY.get("lane_caps", {}) or {})
NOISE_POLICY = dict(RETRIEVAL_POLICY.get("noise", {}) or {})


def _clip(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


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


def _recall_score(
    poi: POI,
    intent: ParsedIntent,
    semantic_query: str = "",
    vector_scores: dict[str, float] | None = None,
) -> float:
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
    if "premium" in preferences or getattr(intent, "prefer_premium", False):
        if _safe_float(getattr(poi, "price", 0)) >= 120:
            score += 2.2
        if _safe_float(getattr(poi, "rating", 0)) >= 4.6:
            score += 1.2
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

    if semantic_query:
        semantic_score = semantic_intent.semantic_similarity(semantic_query, text)
        score += semantic_score * 4.2
    if vector_scores:
        score += float(vector_scores.get(poi.id, 0.0) or 0.0) * 8.0

    score += max(0.0, min((_safe_float(getattr(poi, "rating", 4.0)) - 3.8) / 1.2, 1.0))
    return score


def _sort_and_limit(
    candidates: list[POI],
    intent: ParsedIntent,
    limit: int,
    semantic_query: str = "",
    vector_scores: dict[str, float] | None = None,
) -> list[POI]:
    unique = {poi.id: poi for poi in candidates}
    return sorted(
        unique.values(),
        key=lambda poi: (-_recall_score(poi, intent, semantic_query, vector_scores), poi.id),
    )[:limit]


def _lane_cap(name: str, default: int) -> int:
    try:
        return max(1, int(LANE_CAPS.get(name, default) or default))
    except (TypeError, ValueError):
        return default


def _cap_lane(
    name: str,
    pois: list[POI],
    intent: ParsedIntent,
    semantic_query: str,
    vector_scores: dict[str, float],
) -> list[POI]:
    if not pois:
        return []
    cap = _lane_cap(name, len(pois))
    return _sort_and_limit(pois, intent, cap, semantic_query, vector_scores)


def _noise_risk(
    lane_counts: dict[str, int],
    selected_count: int,
    semantic_terms: list[str],
    raw_candidate_count: int,
) -> str:
    active_lane_count = len([count for count in lane_counts.values() if count > 0])
    text_signal_count = int(lane_counts.get("text_signal", 0) or 0)
    text_signal_share = text_signal_count / max(raw_candidate_count, 1)
    overlap_ratio = 1.0 - (raw_candidate_count / max(sum(lane_counts.values()), 1))

    if active_lane_count <= 1:
        return "high"
    if len([item for item in semantic_terms if item]) > int(NOISE_POLICY.get("max_semantic_term_count_for_low_noise", 6) or 6):
        return "medium"
    if text_signal_share > float(NOISE_POLICY.get("max_text_signal_share_for_low_noise", 0.55) or 0.55):
        return "medium"
    if active_lane_count < int(NOISE_POLICY.get("min_lane_count_for_diversity", 3) or 3):
        return "medium"
    if overlap_ratio > float(NOISE_POLICY.get("max_lane_overlap_ratio_for_low_noise", 0.65) or 0.65):
        return "medium"
    if selected_count < min(DEFAULT_RECALL_LIMIT, int(RETRIEVAL_POLICY.get("fallback_min_selected", 40) or 40)) // 2:
        return "medium"
    return "low"


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

    semantic_query = semantic_intent.build_semantic_query_surface(intent, getattr(intent, "original_query", "") or "")
    vector_query = semantic_retriever.intent_query(intent, semantic_query)
    vector_scores = semantic_retriever.hybrid_score_pois(city_pois, vector_query)

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

    semantic_threshold = float(RETRIEVAL_POLICY.get("semantic_similarity_threshold", 0.46) or 0.46)
    vector_limit = int(RETRIEVAL_POLICY.get("vector_limit", 90) or 90)
    vector_threshold = float(RETRIEVAL_POLICY.get("vector_threshold", 0.025) or 0.025)

    semantic_candidates = [
        poi
        for poi in city_pois
        if semantic_intent.semantic_similarity(semantic_query, _text_blob(poi)) >= semantic_threshold
    ]
    recall_sets.extend(semantic_candidates)
    recall_sets.extend([poi for poi, _ in semantic_retriever.top_lexical_pois(city_pois, vector_query, limit=vector_limit, threshold=0.0)])
    recall_sets.extend([poi for poi, _ in semantic_retriever.top_pois(city_pois, vector_query, limit=vector_limit, threshold=vector_threshold)])

    if getattr(intent, "start_location", None):
        recall_sets.extend([poi for poi in city_pois if _matches_text(poi, str(intent.start_location))])

    recall_sets.extend(must_include_matches)

    if not recall_sets:
        recall_sets = list(city_pois)

    filtered = _sort_and_limit(recall_sets, intent, limit, semantic_query, vector_scores)

    if len(filtered) < min(limit, 40):
        by_id = {poi.id: poi for poi in filtered}
        for poi in _sort_and_limit(city_pois, intent, limit, semantic_query, vector_scores):
            by_id.setdefault(poi.id, poi)
            if len(by_id) >= limit:
                break
        filtered = list(by_id.values())

    if must_include_matches:
        by_id = {poi.id: poi for poi in filtered}
        for poi in must_include_matches:
            by_id.setdefault(poi.id, poi)
        filtered = _sort_and_limit(list(by_id.values()), intent, limit, semantic_query, vector_scores)

    return filtered


def retrieve_pois_with_trace(intent: ParsedIntent, limit: int = DEFAULT_RECALL_LIMIT) -> tuple[list[POI], dict[str, Any]]:
    """Retrieve POIs and return compact recall diagnostics.

    This mirrors the production recall behavior while exposing lane-level counts
    for the coordinator, workflow trace, and evals.
    """

    all_pois = _load_poi_objects()
    city_pois = [poi for poi in all_pois if not intent.city or poi.city == intent.city]
    if not city_pois:
        return [], {
            "source": "poi_recall",
            "city": getattr(intent, "city", None),
            "total_poi_count": len(all_pois),
            "city_poi_count": 0,
            "recall_lanes": {},
            "fallback_expanded": False,
            "selected_count": 0,
            "selected_poi_ids": [],
        }

    semantic_query = semantic_intent.build_semantic_query_surface(intent, getattr(intent, "original_query", "") or "")
    vector_query = semantic_retriever.intent_query(intent, semantic_query)
    vector_scores = semantic_retriever.hybrid_score_pois(city_pois, vector_query)
    semantic_threshold = float(RETRIEVAL_POLICY.get("semantic_similarity_threshold", 0.46) or 0.46)
    vector_limit = int(RETRIEVAL_POLICY.get("vector_limit", 90) or 90)
    vector_threshold = float(RETRIEVAL_POLICY.get("vector_threshold", 0.025) or 0.025)
    retrieval_backend = semantic_retriever.runtime_info(city_pois)

    lanes: dict[str, list[POI]] = {}

    def add_lane(name: str, pois: list[POI]) -> None:
        if pois:
            lanes.setdefault(name, []).extend(pois)

    must_include_matches = [
        poi
        for poi in city_pois
        if any(_matches_text(poi, item) for item in getattr(intent, "must_include", []) or [])
    ]
    add_lane("must_include", must_include_matches)

    category_keys = set(getattr(intent, "required_categories", []) or []) | set(getattr(intent, "preferred_categories", []) or [])
    if category_keys:
        add_lane("category", [poi for poi in city_pois if poi.category in category_keys])

    semantic_terms = [
        *(getattr(intent, "preferences", []) or []),
        *(getattr(intent, "soft_preferences", []) or []),
        *(getattr(intent, "unclassified_clues", []) or []),
        *(getattr(intent, "must_include", []) or []),
    ]
    if semantic_terms:
        add_lane(
            "text_signal",
            [
                poi
                for poi in city_pois
                if any(str(term).strip().lower() and str(term).strip().lower() in _text_blob(poi) for term in semantic_terms)
            ],
        )

    add_lane("bm25", [poi for poi, _ in semantic_retriever.top_lexical_pois(city_pois, vector_query, limit=vector_limit, threshold=0.0)])
    add_lane(
        "semantic_similarity",
        [
            poi
            for poi in city_pois
            if semantic_intent.semantic_similarity(semantic_query, _text_blob(poi)) >= semantic_threshold
        ],
    )
    add_lane("vector", [poi for poi, _ in semantic_retriever.top_pois(city_pois, vector_query, limit=vector_limit, threshold=vector_threshold)])

    if getattr(intent, "start_location", None):
        add_lane("start_location", [poi for poi in city_pois if _matches_text(poi, str(intent.start_location))])

    lane_raw_counts = {name: len({poi.id for poi in pois}) for name, pois in lanes.items()}
    lane_capped = {
        name: _cap_lane(name, pois, intent, semantic_query, vector_scores)
        for name, pois in lanes.items()
    }
    lane_counts = {name: len({poi.id for poi in pois}) for name, pois in lane_capped.items()}
    recall_sets = [poi for pois in lane_capped.values() for poi in pois]
    used_city_fallback = False
    if not recall_sets:
        recall_sets = list(city_pois)
        used_city_fallback = True

    filtered = _sort_and_limit(recall_sets, intent, limit, semantic_query, vector_scores)
    fallback_expanded = False
    if len(filtered) < min(limit, 40):
        fallback_expanded = True
        by_id = {poi.id: poi for poi in filtered}
        for poi in _sort_and_limit(city_pois, intent, limit, semantic_query, vector_scores):
            by_id.setdefault(poi.id, poi)
            if len(by_id) >= limit:
                break
        filtered = list(by_id.values())

    if must_include_matches:
        by_id = {poi.id: poi for poi in filtered}
        for poi in must_include_matches:
            by_id.setdefault(poi.id, poi)
        filtered = _sort_and_limit(list(by_id.values()), intent, limit, semantic_query, vector_scores)

    raw_candidate_count = len({poi.id for poi in recall_sets})
    lane_total = sum(lane_counts.values())
    lane_overlap_ratio = round(1.0 - (raw_candidate_count / max(lane_total, 1)), 3)
    active_lanes = [name for name, count in lane_counts.items() if count > 0]
    text_signal_share = round(float(lane_counts.get("text_signal", 0) or 0) / max(raw_candidate_count, 1), 3)
    retrieval_noise_risk = _noise_risk(lane_counts, len(filtered), semantic_terms, raw_candidate_count)
    trace = {
        "source": "poi_recall",
        "city": getattr(intent, "city", None),
        "total_poi_count": len(all_pois),
        "city_poi_count": len(city_pois),
        "recall_lanes": lane_counts,
        "recall_lane_raw_counts": lane_raw_counts,
        "recall_lane_count": len([count for count in lane_counts.values() if count > 0]),
        "active_lanes": active_lanes,
        "lane_caps": {name: _lane_cap(name, count or 1) for name, count in lane_raw_counts.items()},
        "lane_overlap_ratio": lane_overlap_ratio,
        "text_signal_share": text_signal_share,
        "category_keys": sorted(str(item) for item in category_keys),
        "semantic_term_count": len([item for item in semantic_terms if item]),
        "semantic_similarity_threshold": semantic_threshold,
        "vector_threshold": vector_threshold,
        "vector_limit": vector_limit,
        "retrieval_backend": retrieval_backend,
        "hybrid_backend": retrieval_backend.get("hybrid_backend"),
        "lexical_backend": retrieval_backend.get("lexical_backend"),
        "dense_backend": retrieval_backend.get("dense_backend"),
        "faiss_enabled": bool(retrieval_backend.get("faiss_enabled")),
        "vector_dim": retrieval_backend.get("vector_dim"),
        "used_city_fallback": used_city_fallback,
        "fallback_expanded": fallback_expanded,
        "raw_candidate_count": raw_candidate_count,
        "selected_count": len(filtered),
        "selected_poi_ids": [poi.id for poi in filtered[:30]],
        "noise_risk": retrieval_noise_risk,
        "recall_sources": [
            "local_poi",
            *[f"lane:{name}" for name, count in lane_counts.items() if count > 0],
            str(retrieval_backend.get("hybrid_backend") or ""),
            str(retrieval_backend.get("dense_backend") or ""),
            "city_fallback" if used_city_fallback else "",
            "quality_fallback" if fallback_expanded else "",
        ],
    }
    trace["recall_sources"] = [item for item in trace["recall_sources"] if item]
    return filtered, trace
