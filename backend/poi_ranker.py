from __future__ import annotations

import review_analyzer
from schemas import POI, ParsedIntent


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


def _clip(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _rating_score(poi: POI) -> float:
    return _clip((poi.rating - 3.8) / 1.1)


def _category_match_score(poi: POI, intent: ParsedIntent) -> float:
    preferred = intent.preferred_categories or intent.required_categories
    if not preferred:
        return 0.6
    return 1.0 if poi.category in preferred else 0.25


def _budget_score(poi: POI, intent: ParsedIntent) -> float:
    budget = intent.budget
    if not budget:
        return 0.7

    if poi.price == 0:
        return 0.9

    expected = budget / max(len(intent.required_categories), 1)
    diff_ratio = abs(poi.price - expected) / max(expected, 1)
    return _clip(1 - diff_ratio, 0.1, 1.0)


def _preference_match_score(poi: POI, intent: ParsedIntent) -> float:
    score = 0.4
    all_tags = " ".join(
        poi.tags
        + poi.suitable_for
        + poi.review_keywords
        + [poi.category, poi.sub_category or "", poi.business_area or "", poi.description]
    )

    for keyword in intent.intent_tags:
        if keyword and keyword in all_tags:
            score += 0.12

    if intent.prefer_couple:
        score += review_analyzer.signal(poi, "date") * 0.20
    if intent.prefer_photo:
        score += review_analyzer.signal(poi, "photo") * 0.18
    if intent.prefer_food:
        score += review_analyzer.signal(poi, "food") * 0.18
    if intent.prefer_culture:
        score += review_analyzer.signal(poi, "culture") * 0.18
    if intent.prefer_local_feature:
        score += review_analyzer.signal(poi, "local_feature") * 0.18
    if intent.prefer_rainy_day:
        score += review_analyzer.signal(poi, "rainy_day") * 0.12
    if intent.prefer_night_view:
        score += (0.9 if poi.category == "night" else review_analyzer.signal(poi, "photo")) * 0.15
    if intent.prefer_quiet:
        score += review_analyzer.signal(poi, "quiet") * 0.10

    return _clip(score)


def _semantic_score(poi: POI, intent: ParsedIntent) -> float:
    values = []
    if intent.prefer_photo:
        values.append(review_analyzer.signal(poi, "photo"))
    if intent.prefer_couple:
        values.append(review_analyzer.signal(poi, "date"))
    if intent.prefer_food:
        values.append(review_analyzer.signal(poi, "food"))
    if intent.prefer_culture:
        values.append(review_analyzer.signal(poi, "culture"))
    if intent.prefer_local_feature:
        values.append(review_analyzer.signal(poi, "local_feature"))
    if intent.prefer_rainy_day:
        values.append(review_analyzer.signal(poi, "rainy_day"))
    if intent.prefer_night_view:
        values.append(0.9 if poi.category == "night" else review_analyzer.signal(poi, "photo"))
    if intent.prefer_quiet:
        values.append(review_analyzer.signal(poi, "quiet"))

    if not values:
        return 0.5
    return _clip(sum(values) / len(values))


def _time_suitability_score(poi: POI, intent: ParsedIntent) -> float:
    if intent.prefer_night_view and poi.category == "night":
        return 1.0

    if intent.pace == "fast":
        if poi.visit_duration <= 60:
            return 1.0
        if poi.visit_duration <= 90:
            return 0.7
        return 0.4

    if intent.pace == "slow":
        return 0.8 if poi.visit_duration >= 45 else 0.6

    return 0.7


def _queue_penalty(poi: POI, intent: ParsedIntent) -> float:
    queue_score = review_analyzer.signal(poi, "queue_risk", poi.queue_level / 5)
    penalty = queue_score
    if intent.avoid_queue:
        penalty *= 1.5
    return _clip(penalty)


def _crowd_penalty(poi: POI, intent: ParsedIntent) -> float:
    crowd_score = review_analyzer.signal(poi, "crowd_risk", poi.queue_level / 5)
    penalty = crowd_score
    if intent.avoid_crowded or intent.prefer_quiet:
        penalty *= 1.3
    return _clip(penalty)


def _price_penalty(poi: POI, intent: ParsedIntent) -> float:
    if not intent.budget:
        return 0.0
    expected = intent.budget / max(len(intent.required_categories), 1)
    if poi.price > expected * 1.5:
        return min(0.3, (poi.price - expected * 1.5) / expected)
    return 0.0


def _calculate_final_score(scores: dict[str, float]) -> float:
    value = (
        0.25 * scores["preference_match_score"]
        + 0.20 * scores["semantic_score"]
        + 0.15 * scores["category_match_score"]
        + 0.15 * scores["rating_score"]
        + 0.10 * scores["budget_score"]
        + 0.10 * scores["time_suitability_score"]
        - 0.15 * scores["queue_penalty"]
        - 0.10 * scores["crowd_penalty"]
        - 0.05 * scores["price_penalty"]
    )
    return _clip(value)


def _generate_recommend_reason(poi: POI, intent: ParsedIntent, scores: dict[str, float]) -> str:
    reasons: list[str] = []
    label = CATEGORY_LABELS.get(poi.category, poi.category)

    if scores["category_match_score"] >= 0.95:
        reasons.append(f"匹配你想要的{label}体验")
    if intent.prefer_photo and poi.photo_score >= 4:
        reasons.append("拍照打卡表现好")
    if intent.prefer_couple and poi.date_score >= 4:
        reasons.append("约会氛围较合适")
    if intent.prefer_food and poi.food_score >= 4:
        reasons.append("美食体验分较高")
    if intent.prefer_culture and poi.culture_score >= 4:
        reasons.append("文化内容更丰富")
    if intent.prefer_local_feature and poi.local_feature_score >= 4:
        reasons.append("本地特色比较明显")
    if intent.prefer_night_view and poi.category == "night":
        reasons.append("适合安排夜景")
    if intent.prefer_quiet and poi.queue_level <= 2:
        reasons.append("排队和拥挤风险较低")
    if scores["budget_score"] >= 0.85:
        reasons.append("预算匹配度较高")
    if poi.price == 0:
        reasons.append("免费或低成本")
    if scores["queue_penalty"] >= 0.7:
        reasons.append("但高峰期可能需要排队")

    if not reasons:
        reasons.append("综合评分和路线衔接都比较稳")

    return "，".join(reasons) + "。"


def rank_pois(pois: list[POI], intent: ParsedIntent, top_k: int = 30) -> list[dict]:
    if not pois:
        return []

    city_filtered = [p for p in pois if p.city == intent.city] if intent.city else pois
    if not city_filtered:
        return []

    scored = []
    for poi in city_filtered:
        scores = {
            "preference_match_score": _preference_match_score(poi, intent),
            "semantic_score": _semantic_score(poi, intent),
            "rating_score": _rating_score(poi),
            "category_match_score": _category_match_score(poi, intent),
            "budget_score": _budget_score(poi, intent),
            "time_suitability_score": _time_suitability_score(poi, intent),
            "queue_penalty": _queue_penalty(poi, intent),
            "crowd_penalty": _crowd_penalty(poi, intent),
            "price_penalty": _price_penalty(poi, intent),
        }
        final_score = _calculate_final_score(scores)
        scored.append(
            {
                "poi": poi,
                "final_score": round(final_score, 4),
                "score_breakdown": {k: round(v, 4) for k, v in scores.items()},
                "rank": 0,
                "recommend_reason": _generate_recommend_reason(poi, intent, scores),
            }
        )

    scored.sort(key=lambda item: (-item["final_score"], item["poi"].id))
    for index, item in enumerate(scored[:top_k], start=1):
        item["rank"] = index
    return scored[:top_k]
