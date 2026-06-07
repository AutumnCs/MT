"""Clean POI ranking implementation backed by a tunable policy file."""

from __future__ import annotations

from typing import Iterable

from core.intent_lexicon import CATEGORY_DISPLAY_LABELS
from core.schemas import POI, ParsedIntent
from . import review_analyzer
from .poi_ranker_policy import RANKER_POLICY


FINAL_WEIGHTS = RANKER_POLICY["final_weights"]
RATING_POLICY = RANKER_POLICY["rating"]
CATEGORY_POLICY = RANKER_POLICY["category_match"]
BUDGET_POLICY = RANKER_POLICY["budget"]
PREFERENCE_POLICY = RANKER_POLICY["preference"]
SEMANTIC_POLICY = RANKER_POLICY["semantic"]
TIME_POLICY = RANKER_POLICY["time"]
PENALTY_POLICY = RANKER_POLICY["penalty"]
REASON_POLICY = RANKER_POLICY["reason"]


def _clip(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _has_preference(intent: ParsedIntent, key: str, attr_name: str | None = None) -> bool:
    if attr_name and getattr(intent, attr_name, False):
        return True
    return key in getattr(intent, "preferences", []) or key in getattr(intent, "soft_preferences", [])


def _contains_any(texts: list[str], terms: Iterable[str]) -> bool:
    for text in texts:
        for term in terms:
            if term in text:
                return True
    return False


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


def _modification_penalty(poi: POI, intent: ParsedIntent) -> float:
    if getattr(intent, "current_route", None) is None:
        return 0.0

    text = str(getattr(intent, "modification_query", "") or "")
    current_ids = _current_route_poi_ids(intent)
    penalty = 0.0

    asks_replace = any(token in text for token in ("换", "替换", "不要这个", "去掉", "删掉", "重新", "不想去"))
    if asks_replace and poi.id in current_ids:
        penalty += 0.28

    if getattr(intent, "avoid_queue", False) and (poi.queue_level or 0) >= 3:
        penalty += 0.18
    if getattr(intent, "avoid_crowded", False) and (poi.queue_level or 0) >= 3:
        penalty += 0.14
    if "avoid_far" in getattr(intent, "avoid", []):
        if poi.id in current_ids and asks_replace:
            penalty += 0.10
    if getattr(intent, "budget", None):
        expected = float(intent.budget) / max(len(intent.required_categories), 1)
        if float(poi.price or 0.0) > expected:
            penalty += 0.12

    return _clip(penalty, 0.0, 0.55)


def _text_blob(poi: POI) -> str:
    parts: list[str] = [
        poi.name or "",
        poi.category or "",
        poi.sub_category or "",
        poi.description or "",
        " ".join(poi.tags),
        " ".join(poi.suitable_for),
        " ".join(poi.review_keywords),
    ]
    return " ".join(part for part in parts if part).lower()


def _rating_score(poi: POI) -> float:
    rating = float(poi.rating if poi.rating is not None else RATING_POLICY["baseline"])
    return _clip((rating - float(RATING_POLICY["baseline"])) / float(RATING_POLICY["scale"]))


def _category_match_score(poi: POI, intent: ParsedIntent) -> float:
    preferred = intent.preferred_categories or intent.required_categories
    if not preferred:
        return float(CATEGORY_POLICY["default"])
    return float(CATEGORY_POLICY["perfect"]) if poi.category in preferred else float(CATEGORY_POLICY["mismatch"])


def _budget_score(poi: POI, intent: ParsedIntent) -> float:
    budget = intent.budget
    if not budget:
        return float(BUDGET_POLICY["default"])
    if float(poi.price or 0.0) <= 0:
        return float(BUDGET_POLICY["free"])

    expected = float(budget) / max(len(intent.required_categories), 1)
    diff_ratio = abs(float(poi.price) - expected) / max(expected, 1.0)
    return _clip(1.0 - diff_ratio, 0.1, 1.0)


def _preference_match_score(poi: POI, intent: ParsedIntent) -> float:
    score = float(PREFERENCE_POLICY["base"])
    all_tags = " ".join(
        [
            *(poi.tags or []),
            *(poi.suitable_for or []),
            *(poi.review_keywords or []),
            poi.category or "",
            poi.sub_category or "",
            poi.business_area or "",
            poi.description or "",
        ]
    )

    for keyword in intent.intent_tags:
        if keyword and keyword in all_tags:
            score += float(PREFERENCE_POLICY["intent_tag_bonus"])

    if _has_preference(intent, "couple", "prefer_couple"):
        score += review_analyzer.signal(poi, "date") * float(PREFERENCE_POLICY["date_signal_weight"])
    if _has_preference(intent, "photo", "prefer_photo"):
        score += review_analyzer.signal(poi, "photo") * float(PREFERENCE_POLICY["photo_signal_weight"])
    if _has_preference(intent, "food", "prefer_food"):
        score += review_analyzer.signal(poi, "food") * float(PREFERENCE_POLICY["food_signal_weight"])
    if _has_preference(intent, "culture", "prefer_culture"):
        score += review_analyzer.signal(poi, "culture") * float(PREFERENCE_POLICY["culture_signal_weight"])
    if _has_preference(intent, "local_feature", "prefer_local_feature"):
        score += review_analyzer.signal(poi, "local_feature") * float(PREFERENCE_POLICY["local_feature_signal_weight"])
    if _has_preference(intent, "rainy_day", "prefer_rainy_day"):
        score += review_analyzer.signal(poi, "rainy_day") * float(PREFERENCE_POLICY["rainy_day_signal_weight"])
    if _has_preference(intent, "night_view", "prefer_night_view"):
        score += (
            float(SEMANTIC_POLICY["night_view_match"])
            if poi.category == TIME_POLICY["night_category"]
            else review_analyzer.signal(poi, "photo")
        ) * float(PREFERENCE_POLICY["night_view_weight"])
    if _has_preference(intent, "quiet", "prefer_quiet"):
        score += review_analyzer.signal(poi, "quiet") * float(PREFERENCE_POLICY["quiet_signal_weight"])
    if _has_preference(intent, "family", "prefer_family"):
        family_terms = tuple(PREFERENCE_POLICY["family_terms"])
        score += (
            float(PREFERENCE_POLICY["family_match_bonus"])
            if _contains_any(poi.suitable_for + poi.tags, family_terms)
            else float(PREFERENCE_POLICY["family_fallback_bonus"])
        )
    if _has_preference(intent, "friends", "prefer_friends"):
        friends_terms = tuple(PREFERENCE_POLICY["friends_terms"])
        score += (
            float(PREFERENCE_POLICY["friends_match_bonus"])
            if _contains_any(poi.suitable_for + poi.tags, friends_terms)
            else float(PREFERENCE_POLICY["friends_fallback_bonus"])
        )
    if _has_preference(intent, "solo", "prefer_solo"):
        score += float(PREFERENCE_POLICY["solo_bonus"]) if (poi.queue_level or 0) <= int(PREFERENCE_POLICY["solo_queue_threshold"]) else 0.0
    if _has_preference(intent, "value", "prefer_value"):
        score += (
            float(PREFERENCE_POLICY["value_match_bonus"])
            if float(poi.price or 0.0) == 0 or float(poi.price or 0.0) <= float(PREFERENCE_POLICY["value_price_threshold"])
            else float(PREFERENCE_POLICY["value_fallback_bonus"])
        )
    if _has_preference(intent, "indoor", "prefer_indoor"):
        score += float(PREFERENCE_POLICY["indoor_match_bonus"]) if poi.indoor_outdoor == "indoor" else float(PREFERENCE_POLICY["indoor_fallback_bonus"])
    if _has_preference(intent, "outdoor", "prefer_outdoor"):
        score += float(PREFERENCE_POLICY["outdoor_match_bonus"]) if poi.indoor_outdoor == "outdoor" else float(PREFERENCE_POLICY["outdoor_fallback_bonus"])
    if _has_preference(intent, "citywalk", "prefer_citywalk"):
        score += (
            float(PREFERENCE_POLICY["citywalk_match_bonus"])
            if poi.category in set(PREFERENCE_POLICY["citywalk_categories"])
            else float(PREFERENCE_POLICY["citywalk_fallback_bonus"])
        )
    if _has_preference(intent, "efficient", "prefer_efficient"):
        score += (
            float(PREFERENCE_POLICY["efficient_match_bonus"])
            if (poi.visit_duration or 0) <= int(PREFERENCE_POLICY["efficient_duration_threshold"])
            else float(PREFERENCE_POLICY["efficient_fallback_bonus"])
        )
    if _has_preference(intent, "compact", "prefer_compact"):
        score += (
            float(PREFERENCE_POLICY["compact_match_bonus"])
            if (poi.visit_duration or 0) <= int(PREFERENCE_POLICY["compact_duration_threshold"])
            else float(PREFERENCE_POLICY["compact_fallback_bonus"])
        )

    return _clip(score)


def _semantic_score(poi: POI, intent: ParsedIntent) -> float:
    values: list[float] = []
    if _has_preference(intent, "photo", "prefer_photo"):
        values.append(review_analyzer.signal(poi, "photo"))
    if _has_preference(intent, "couple", "prefer_couple"):
        values.append(review_analyzer.signal(poi, "date"))
    if _has_preference(intent, "food", "prefer_food"):
        values.append(review_analyzer.signal(poi, "food"))
    if _has_preference(intent, "culture", "prefer_culture"):
        values.append(review_analyzer.signal(poi, "culture"))
    if _has_preference(intent, "local_feature", "prefer_local_feature"):
        values.append(review_analyzer.signal(poi, "local_feature"))
    if _has_preference(intent, "rainy_day", "prefer_rainy_day"):
        values.append(review_analyzer.signal(poi, "rainy_day"))
    if _has_preference(intent, "night_view", "prefer_night_view"):
        values.append(
            float(SEMANTIC_POLICY["night_view_match"])
            if poi.category == TIME_POLICY["night_category"]
            else review_analyzer.signal(poi, "photo")
        )
    if _has_preference(intent, "quiet", "prefer_quiet"):
        values.append(review_analyzer.signal(poi, "quiet"))
    if _has_preference(intent, "family", "prefer_family"):
        values.append(
            float(SEMANTIC_POLICY["family_match"])
            if _contains_any(poi.suitable_for + poi.tags, PREFERENCE_POLICY["family_terms"])
            else float(SEMANTIC_POLICY["family_fallback"])
        )
    if _has_preference(intent, "friends", "prefer_friends"):
        values.append(
            float(SEMANTIC_POLICY["friends_match"])
            if _contains_any(poi.suitable_for + poi.tags, PREFERENCE_POLICY["friends_terms"])
            else float(SEMANTIC_POLICY["friends_fallback"])
        )
    if _has_preference(intent, "solo", "prefer_solo"):
        values.append(float(SEMANTIC_POLICY["solo_match"]) if (poi.queue_level or 0) <= int(PREFERENCE_POLICY["solo_queue_threshold"]) else float(SEMANTIC_POLICY["solo_fallback"]))
    if _has_preference(intent, "value", "prefer_value"):
        values.append(
            float(SEMANTIC_POLICY["value_match"])
            if float(poi.price or 0.0) == 0 or float(poi.price or 0.0) <= float(PREFERENCE_POLICY["value_price_threshold"])
            else float(SEMANTIC_POLICY["value_fallback"])
        )
    if _has_preference(intent, "indoor", "prefer_indoor"):
        values.append(float(SEMANTIC_POLICY["indoor_match"]) if poi.indoor_outdoor == "indoor" else float(SEMANTIC_POLICY["indoor_fallback"]))
    if _has_preference(intent, "outdoor", "prefer_outdoor"):
        values.append(float(SEMANTIC_POLICY["outdoor_match"]) if poi.indoor_outdoor == "outdoor" else float(SEMANTIC_POLICY["outdoor_fallback"]))
    if _has_preference(intent, "citywalk", "prefer_citywalk"):
        values.append(float(SEMANTIC_POLICY["citywalk_match"]) if poi.category in set(PREFERENCE_POLICY["citywalk_categories"]) else float(SEMANTIC_POLICY["citywalk_fallback"]))
    if _has_preference(intent, "efficient", "prefer_efficient"):
        values.append(float(SEMANTIC_POLICY["efficient_match"]) if (poi.visit_duration or 0) <= int(PREFERENCE_POLICY["efficient_duration_threshold"]) else float(SEMANTIC_POLICY["efficient_fallback"]))
    if _has_preference(intent, "compact", "prefer_compact"):
        values.append(float(SEMANTIC_POLICY["compact_match"]) if (poi.visit_duration or 0) <= int(PREFERENCE_POLICY["compact_duration_threshold"]) else float(SEMANTIC_POLICY["compact_fallback"]))

    if not values:
        return float(SEMANTIC_POLICY["default"])
    return _clip(sum(values) / len(values))


def _time_suitability_score(poi: POI, intent: ParsedIntent) -> float:
    if intent.prefer_night_view and poi.category == TIME_POLICY["night_category"]:
        return 1.0

    duration = int(poi.visit_duration or 0)
    if intent.pace == "fast":
        if duration <= int(TIME_POLICY["fast_short"]):
            return float(TIME_POLICY["fast_scores"]["short"])
        if duration <= int(TIME_POLICY["fast_medium"]):
            return float(TIME_POLICY["fast_scores"]["medium"])
        return float(TIME_POLICY["fast_scores"]["long"])

    if intent.pace == "slow":
        return float(TIME_POLICY["slow_score"]) if duration >= int(TIME_POLICY["slow_min_duration"]) else float(TIME_POLICY["slow_fallback_score"])

    return float(TIME_POLICY["default"])


def _queue_penalty(poi: POI, intent: ParsedIntent) -> float:
    queue_score = review_analyzer.signal(poi, "queue_risk", (poi.queue_level or 0) / 5.0)
    penalty = queue_score * float(PENALTY_POLICY["queue_multiplier"])
    if intent.avoid_queue:
        penalty *= float(PENALTY_POLICY["queue_avoid_multiplier"])
    return _clip(penalty)


def _crowd_penalty(poi: POI, intent: ParsedIntent) -> float:
    crowd_score = review_analyzer.signal(poi, "crowd_risk", (poi.queue_level or 0) / 5.0)
    penalty = crowd_score * float(PENALTY_POLICY["crowd_multiplier"])
    if intent.avoid_crowded or intent.prefer_quiet:
        penalty *= float(PENALTY_POLICY["crowd_avoid_multiplier"])
    return _clip(penalty)


def _price_penalty(poi: POI, intent: ParsedIntent) -> float:
    if not intent.budget:
        return 0.0
    expected = float(intent.budget) / max(len(intent.required_categories), 1)
    if float(poi.price or 0.0) > expected * float(PENALTY_POLICY["price_threshold_multiplier"]):
        return min(
            float(PENALTY_POLICY["price_penalty_cap"]),
            (float(poi.price or 0.0) - expected * float(PENALTY_POLICY["price_threshold_multiplier"])) / max(expected, 1.0),
        )
    return 0.0


def _calculate_final_score(scores: dict[str, float]) -> float:
    value = (
        float(FINAL_WEIGHTS["preference_match_score"]) * scores["preference_match_score"]
        + float(FINAL_WEIGHTS["semantic_score"]) * scores["semantic_score"]
        + float(FINAL_WEIGHTS["category_match_score"]) * scores["category_match_score"]
        + float(FINAL_WEIGHTS["rating_score"]) * scores["rating_score"]
        + float(FINAL_WEIGHTS["budget_score"]) * scores["budget_score"]
        + float(FINAL_WEIGHTS["time_suitability_score"]) * scores["time_suitability_score"]
        - float(FINAL_WEIGHTS["queue_penalty"]) * scores["queue_penalty"]
        - float(FINAL_WEIGHTS["crowd_penalty"]) * scores["crowd_penalty"]
        - float(FINAL_WEIGHTS["price_penalty"]) * scores["price_penalty"]
    )
    return _clip(value)


def _generate_recommend_reason(poi: POI, intent: ParsedIntent, scores: dict[str, float]) -> str:
    reasons: list[str] = []
    label = CATEGORY_DISPLAY_LABELS.get(poi.category, poi.category)

    if scores["category_match_score"] >= float(REASON_POLICY["category_match_threshold"]):
        reasons.append(f"匹配你想要的{label}体验")
    if intent.prefer_photo and (poi.photo_score or 0) >= 4:
        reasons.append("拍照打卡表现好")
    if intent.prefer_couple and (poi.date_score or 0) >= 4:
        reasons.append("约会氛围较合适")
    if intent.prefer_food and (poi.food_score or 0) >= 4:
        reasons.append("美食体验分较高")
    if intent.prefer_culture and (poi.culture_score or 0) >= 4:
        reasons.append("文化内容更丰富")
    if intent.prefer_local_feature and (poi.local_feature_score or 0) >= 4:
        reasons.append("本地特色比较明显")
    if intent.prefer_night_view and poi.category == TIME_POLICY["night_category"]:
        reasons.append("适合安排夜景")
    if intent.prefer_quiet and (poi.queue_level or 0) <= 2:
        reasons.append("排队和拥挤风险较低")
    if scores["budget_score"] >= float(REASON_POLICY["budget_match_threshold"]):
        reasons.append("预算匹配度较高")
    if float(poi.price or 0.0) == 0:
        reasons.append("免费或低成本")
    if scores["queue_penalty"] >= float(REASON_POLICY["queue_risk_threshold"]):
        reasons.append("高峰期可能需要排队")

    if not reasons:
        reasons.append("综合评分和路线衔接都比较稳")

    return "；".join(reasons) + "。"


def rank_pois(pois: list[POI], intent: ParsedIntent, top_k: int = 30) -> list[dict]:
    if not pois:
        return []

    city_filtered = [p for p in pois if p.city == intent.city] if intent.city else pois
    if not city_filtered:
        return []

    scored: list[dict] = []
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
            "modification_penalty": _modification_penalty(poi, intent),
        }
        final_score = _calculate_final_score(scores)
        final_score = _clip(final_score - scores["modification_penalty"])
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
