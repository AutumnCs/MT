"""Display label helpers for user-facing summaries.

Keep all label presentation logic in one place so UI summaries and ranking
reasons do not drift from the shared lexicon.
"""

from __future__ import annotations

from typing import Any

from core.intent_lexicon import AVOID_DISPLAY_LABELS, CATEGORY_DISPLAY_LABELS, PREFERENCE_DISPLAY_LABELS


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in values if item))


def collect_preference_labels(intent: Any) -> list[str]:
    labels: list[str] = []
    for pref_key in getattr(intent, "preferences", []) or []:
        labels.append(PREFERENCE_DISPLAY_LABELS.get(pref_key, pref_key))

    flag_map = {
        "prefer_couple": "couple",
        "prefer_photo": "photo",
        "prefer_food": "food",
        "prefer_culture": "culture",
        "prefer_local_feature": "local_feature",
        "prefer_night_view": "night_view",
        "prefer_quiet": "quiet",
        "prefer_rainy_day": "rainy_day",
        "prefer_value": "value",
        "prefer_family": "family",
        "prefer_friends": "friends",
        "prefer_solo": "solo",
        "prefer_citywalk": "citywalk",
        "prefer_indoor": "indoor",
        "prefer_outdoor": "outdoor",
        "prefer_walking": "walking",
    }
    for attr_name, label_key in flag_map.items():
        if getattr(intent, attr_name, False):
            labels.append(PREFERENCE_DISPLAY_LABELS.get(label_key, label_key))

    if getattr(intent, "prefer_efficient", False):
        labels.append(PREFERENCE_DISPLAY_LABELS.get("efficient", "efficient"))
    if getattr(intent, "prefer_compact", False):
        labels.append(PREFERENCE_DISPLAY_LABELS.get("compact", "compact"))

    if getattr(intent, "avoid_queue", False):
        labels.append(AVOID_DISPLAY_LABELS.get("avoid_queue", "avoid_queue"))
    if getattr(intent, "avoid_crowded", False):
        labels.append(AVOID_DISPLAY_LABELS.get("avoid_crowded", "avoid_crowded"))
    if getattr(intent, "avoid_far", False):
        labels.append(AVOID_DISPLAY_LABELS.get("avoid_far", "avoid_far"))
    if getattr(intent, "avoid_spicy", False):
        labels.append(AVOID_DISPLAY_LABELS.get("avoid_spicy", "avoid_spicy"))

    return _dedupe(labels)


def collect_category_labels(intent: Any) -> list[str]:
    categories = getattr(intent, "required_categories", []) or []
    return _dedupe([CATEGORY_DISPLAY_LABELS.get(category, category) for category in categories])


def build_intent_summary(intent: Any, query: str = "") -> str:
    parts: list[str] = []

    city = getattr(intent, "city", None)
    if city:
        parts.append(f"城市：{city}")

    budget = getattr(intent, "budget", None)
    if budget is not None:
        parts.append(f"预算：{budget} 元")

    start_time = getattr(intent, "start_time", None)
    end_time = getattr(intent, "end_time", None)
    if start_time or end_time:
        time_bits: list[str] = []
        if start_time:
            time_bits.append(f"开始 {start_time}")
        if end_time:
            time_bits.append(f"结束 {end_time}")
        parts.append(f"时间：{' / '.join(time_bits)}")

    start_location = getattr(intent, "start_location", None)
    if start_location:
        parts.append(f"起点：{start_location}")

    preferences = collect_preference_labels(intent)
    if preferences:
        parts.append(f"偏好：{'、'.join(preferences)}")

    categories = collect_category_labels(intent)
    if categories:
        parts.append(f"类别：{'、'.join(categories)}")

    pace = getattr(intent, "pace", "normal")
    if pace != "normal":
        pace_label = {
            "slow": "轻松",
            "fast": "紧凑",
        }.get(pace, pace)
        parts.append(f"节奏：{pace_label}")

    transport_mode = getattr(intent, "transport_mode", "walking")
    if transport_mode != "walking":
        transport_label = {
            "taxi": "打车",
            "metro": "地铁",
            "walking": "步行",
        }.get(transport_mode, transport_mode)
        parts.append(f"交通：{transport_label}")

    if not parts and query.strip():
        return f"系统已接收需求：{query.strip()}"

    return "｜".join(parts) if parts else "系统已完成意图解析。"
