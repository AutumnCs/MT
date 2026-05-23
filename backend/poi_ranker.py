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
    all_tags = " ".join(poi.tags + poi.suitable_for + [poi.category, poi.sub_category or ""])

    for keyword in intent.intent_tags:
        if keyword and keyword in all_tags:
            score += 0.12

    if intent.prefer_couple:
        score += (poi.date_score / 5) * 0.20
    if intent.prefer_photo:
        score += (poi.photo_score / 5) * 0.18
    if intent.prefer_food:
        score += (poi.food_score / 5) * 0.18
    if intent.prefer_culture:
        score += (poi.culture_score / 5) * 0.18
    if intent.prefer_local_feature:
        score += (poi.local_feature_score / 5) * 0.18
    if intent.prefer_rainy_day:
        score += (poi.rainy_day_score / 5) * 0.12

    return _clip(score)


def _semantic_score(poi: POI, intent: ParsedIntent) -> float:
    values = []
    if intent.prefer_photo:
        values.append(poi.photo_score / 5)
    if intent.prefer_couple:
        values.append(poi.date_score / 5)
    if intent.prefer_food:
        values.append(poi.food_score / 5)
    if intent.prefer_culture:
        values.append(poi.culture_score / 5)
    if intent.prefer_local_feature:
        values.append(poi.local_feature_score / 5)
    if intent.prefer_rainy_day:
        values.append(poi.rainy_day_score / 5)

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
    queue_score = poi.queue_level / 5
    return queue_score if intent.avoid_queue else queue_score * 0.4


def _crowd_penalty(poi: POI, intent: ParsedIntent) -> float:
    crowd_score = poi.queue_level / 5
    return crowd_score if (intent.avoid_crowded or intent.prefer_quiet) else crowd_score * 0.4


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
    )
    return _clip(value)


def _generate_recommend_reason(poi: POI, intent: ParsedIntent, scores: dict[str, float]) -> str:
    reasons: list[str] = []
    label = CATEGORY_LABELS.get(poi.category, poi.category)

    if scores["category_match_score"] >= 0.95:
        reasons.append(f"很好匹配你想要的{label}需求")
    if intent.prefer_photo and poi.photo_score >= 4:
        reasons.append("拍照表现好，出片概率高")
    if intent.prefer_couple and poi.date_score >= 4:
        reasons.append("约会氛围不错")
    if intent.prefer_food and poi.food_score >= 4:
        reasons.append("美食体验突出")
    if intent.prefer_culture and poi.culture_score >= 4:
        reasons.append("文化体验更强")
    if intent.prefer_local_feature and poi.local_feature_score >= 4:
        reasons.append("本地特色比较明显")
    if scores["budget_score"] >= 0.85:
        reasons.append("预算适配度高")
    if scores["queue_penalty"] >= 0.7:
        reasons.append("但高峰时段可能需要排队")

    if not reasons:
        reasons.append("综合评分稳定，适合作为路线中的一站")

    return "，".join(reasons) + "。"


def rank_pois(pois: list[POI], intent: ParsedIntent, top_k: int = 30) -> list[dict]:
    if not pois:
        return []

    scored = []
    for poi in pois:
        scores = {
            "preference_match_score": _preference_match_score(poi, intent),
            "semantic_score": _semantic_score(poi, intent),
            "rating_score": _rating_score(poi),
            "category_match_score": _category_match_score(poi, intent),
            "budget_score": _budget_score(poi, intent),
            "time_suitability_score": _time_suitability_score(poi, intent),
            "queue_penalty": _queue_penalty(poi, intent),
            "crowd_penalty": _crowd_penalty(poi, intent),
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
