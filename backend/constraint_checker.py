from __future__ import annotations

import re

from schemas import POI, ParsedIntent

SUPPORTED_CITIES = ["广州", "上海"]


def filter_by_constraints(pois: list[POI], intent: ParsedIntent) -> list[POI]:
    """Apply only hard constraints here.

    Soft preferences such as couple/photo/local-feature should be handled by
    ranking, not by hard filtering.
    """

    filtered: list[POI] = []
    category_count = max(len(intent.required_categories), 1)

    for poi in pois:
        if intent.city and poi.city != intent.city:
            continue

        if intent.budget and poi.price > max(120, intent.budget / category_count * 1.6):
            continue

        if "spicy" in intent.avoid and any(tag in ["辣", "重辣", "麻辣"] for tag in poi.tags):
            continue

        if intent.avoid_queue and poi.queue_level >= 4:
            continue

        if intent.avoid_crowded and poi.queue_level >= 4:
            continue

        filtered.append(poi)

    return filtered


def validate_intent(intent: ParsedIntent) -> tuple[bool, list[str]]:
    errors: list[str] = []

    if intent.city and intent.city not in SUPPORTED_CITIES:
        errors.append(f"不支持的城市: {intent.city}")

    if intent.budget is not None and intent.budget < 50:
        errors.append("预算过低，请设置至少 50 元")

    if intent.budget is not None and intent.budget > 5000:
        errors.append("预算过高，请设置在合理范围内")

    if intent.start_time and intent.end_time:
        start_hour = _parse_time_to_hour(intent.start_time)
        end_hour = _parse_time_to_hour(intent.end_time)
        if end_hour <= start_hour:
            errors.append("结束时间应晚于开始时间")

    if not intent.required_categories and not intent.preferred_categories:
        errors.append("请至少提供一个类别需求或偏好")

    return (len(errors) == 0, errors)


def _parse_time_to_hour(time_str: str) -> float:
    text = time_str or ""

    if ":" in text:
        match = re.search(r"(\d{1,2}):(\d{2})", text)
        if match:
            return int(match.group(1)) + int(match.group(2)) / 60

    match = re.search(r"(\d{1,2})", text)
    if not match:
        return 0.0

    hour = int(match.group(1))
    if "下午" in text or "晚上" in text or "中午" in text:
        if hour < 12:
            hour += 12
    return float(hour)
