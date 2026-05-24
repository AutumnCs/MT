"""Intent parsing boundary.

The preferred flow is:
1. An LLM turns user text into structured JSON matching ``LLMIntentDraft``.
2. This module normalizes that JSON and applies only fallback heuristics.
3. Hard constraints are preserved for validation and feasibility checks.

This file should not become a semantic rule dump. Soft preferences should be
kept lightweight and pushed downstream to ranking / planning.
"""

from __future__ import annotations

import re
from typing import Optional

from schemas import LLMIntentDraft, ParsedIntent

SUPPORTED_CITIES = ["广州", "上海"]

CITY_LANDMARKS = {
    "广州": ["广州塔", "花城广场", "海心沙", "珠江新城", "白云山", "上下九", "北京路"],
    "上海": ["外滩", "豫园", "东方明珠", "武康路", "思南路", "陆家嘴", "新天地", "南京路"],
}

CATEGORY_HINTS = {
    "coffee": ["咖啡", "咖啡店", "下午茶"],
    "food": ["吃饭", "晚饭", "午饭", "美食", "餐厅", "火锅", "小吃", "甜品", "本帮菜", "粤菜"],
    "museum": ["博物馆", "展馆"],
    "exhibition": ["看展", "展览", "美术馆", "艺术馆"],
    "scene": ["景点", "观光", "游览"],
    "street": ["街道", "老街", "马路", "散步"],
    "shopping": ["购物", "逛街", "商场"],
    "park": ["公园", "散步", "绿地"],
    "night": ["夜景", "看夜景", "夜游"],
}

SOFT_PREFERENCE_HINTS = {
    "couple": ["约会", "浪漫", "情侣"],
    "photo": ["拍照", "打卡", "出片", "摄影"],
    "food": ["吃货", "美食", "好吃的"],
    "culture": ["文化", "历史", "博物馆", "艺术"],
    "local_feature": ["本地特色", "老字号", "本帮菜", "地方特色"],
    "night_view": ["夜景", "晚上", "夜晚", "灯光"],
    "quiet": ["安静", "轻松", "休闲", "不吵"],
    "rainy_day": ["雨天", "下雨", "室内", "避雨"],
}

UI_PREFERENCE_ALIASES = {
    "约会": "couple",
    "拍照": "photo",
    "不想排队": "queue",
    "性价比": "value",
    "轻松路线": "relaxed",
    "美食": "food",
    "文艺": "culture",
    "夜景": "night_view",
    "本地特色": "local_feature",
    "安静": "quiet",
    "雨天": "rainy_day",
}

AVOID_HINTS = {
    "spicy": ["不要辣", "不吃辣", "忌辣"],
    "far": ["太远", "近一点", "别太远"],
    "queue": ["不想排队", "别排太久", "不想等位"],
    "crowded": ["人少", "不拥挤", "避开人多", "清净"],
}

TRANSPORT_HINTS = {
    "metro": ["地铁", "地铁优先"],
    "taxi": ["打车", "出租车"],
    "walking": ["步行", "走路"],
}

HARD_CONSTRAINT_FLAGS = {
    "city",
    "start_location",
    "budget",
    "start_time",
    "end_time",
    "required_categories",
    "avoid_queue",
    "avoid_crowded",
    "max_distance",
}


def _contains_any(text: str, keywords: list[str] | tuple[str, ...]) -> bool:
    return any(keyword and keyword in text for keyword in keywords)


def _add_unique(values: list[str], additions: list[str]) -> None:
    for item in additions:
        if item not in values:
            values.append(item)


def _parse_hour_token(token: str) -> Optional[int]:
    token = (token or "").strip()
    if not token:
        return None
    if token.isdigit():
        return int(token)

    chinese_map = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
        "十一": 11,
        "十二": 12,
    }
    if token in chinese_map:
        return chinese_map[token]
    if token == "十":
        return 10
    if len(token) == 2 and token[0] == "十" and token[1] in chinese_map:
        return 10 + chinese_map[token[1]]
    if len(token) == 2 and token[1] == "十" and token[0] in chinese_map:
        return chinese_map[token[0]] * 10
    if len(token) == 3 and token[1] == "十" and token[0] in chinese_map and token[2] in chinese_map:
        return chinese_map[token[0]] * 10 + chinese_map[token[2]]
    return None


def _infer_city_from_landmark(text: str) -> Optional[str]:
    for city, landmarks in CITY_LANDMARKS.items():
        if _contains_any(text, landmarks):
            return city
    return None


def _infer_city_from_text(text: str) -> Optional[str]:
    for city in SUPPORTED_CITIES:
        if city in text:
            return city
    return _infer_city_from_landmark(text)


def _parse_budget(text: str) -> Optional[int]:
    match = re.search(r"预算\s*(\d+)", text)
    if match:
        return int(match.group(1))

    if _contains_any(text, ["低预算", "省钱", "便宜"]):
        return 100
    if _contains_any(text, ["中等预算", "预算中等"]):
        return 200

    return None


def _parse_distance(text: str) -> Optional[float]:
    match = re.search(r"(\d+)\s*公里", text)
    if match:
        return float(match.group(1))
    return None


def _normalize_time(text: str, *, is_end: bool = False) -> Optional[str]:
    raw = text.strip()
    if not raw:
        return None

    colon_match = re.search(r"(\d{1,2})[:：](\d{2})", raw)
    if colon_match:
        return f"{int(colon_match.group(1)):02d}:{int(colon_match.group(2)):02d}"

    match = re.search(
        r"(上午|中午|下午|晚上)?\s*([0-9一二两三四五六七八九十]{1,3})点(?:([0-9一二两三四五六七八九十]{1,2})分|半|30)?",
        raw,
    )
    if not match:
        return None

    period = match.group(1) or ""
    hour = _parse_hour_token(match.group(2))
    if hour is None:
        return None

    minute_text = match.group(3) or ""
    if "半" in raw or "30" in raw:
        minute = 30
    elif minute_text:
        minute = _parse_hour_token(minute_text) or 0
    else:
        minute = 0

    if period in {"下午", "晚上"} and hour < 12:
        hour += 12
    elif period == "中午" and hour < 11:
        hour += 12

    return f"{hour:02d}:{minute:02d}"


def _parse_start_time(text: str) -> Optional[str]:
    patterns = [
        r"((?:上午|中午|下午|晚上)?\s*[0-9一二两三四五六七八九十]{1,3}点(?:[0-9一二两三四五六七八九十]{1,2}分|半|30)?)(?!前)",
        r"(\d{1,2}[:：]\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _normalize_time(match.group(1))
    return None


def _parse_end_time(text: str) -> Optional[str]:
    patterns = [
        r"((?:上午|中午|下午|晚上)?\s*[0-9一二两三四五六七八九十]{1,3}点(?:[0-9一二两三四五六七八九十]{1,2}分|半|30)?前)",
        r"(\d{1,2}[:：]\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            raw = match.group(1)
            normalized = _normalize_time(raw, is_end=True)
            if normalized:
                return normalized
    return None


def _parse_pace(text: str) -> str:
    if _contains_any(text, ["轻松", "慢慢逛", "不赶", "悠闲", "松弛"]):
        return "slow"
    if _contains_any(text, ["紧凑", "高效", "多打卡", "半日", "赶时间"]):
        return "fast"
    return "normal"


def _parse_transport_mode(text: str) -> str:
    for mode, keywords in TRANSPORT_HINTS.items():
        if _contains_any(text, keywords):
            return mode
    return "walking"


def _collect_preferences(text: str, intent: ParsedIntent) -> None:
    for pref_key, keywords in SOFT_PREFERENCE_HINTS.items():
        if _contains_any(text, keywords):
            setattr(intent, f"prefer_{pref_key}", True)
            if pref_key not in intent.preferences:
                intent.preferences.append(pref_key)
            _add_unique(intent.intent_tags, keywords)


def _collect_categories(text: str, intent: ParsedIntent) -> None:
    for category, keywords in CATEGORY_HINTS.items():
        if _contains_any(text, keywords):
            if category not in intent.required_categories:
                intent.required_categories.append(category)

    if intent.required_categories:
        intent.preferred_categories = intent.required_categories.copy()


def _collect_avoid(text: str, intent: ParsedIntent) -> None:
    for avoid_key, keywords in AVOID_HINTS.items():
        if _contains_any(text, keywords):
            if avoid_key not in intent.avoid:
                intent.avoid.append(avoid_key)
            if avoid_key == "queue":
                intent.avoid_queue = True
            elif avoid_key == "crowded":
                intent.avoid_crowded = True


def apply_ui_preferences(intent: ParsedIntent, labels: list[str] | tuple[str, ...]) -> ParsedIntent:
    """Merge frontend preference chips into the soft-preference layer."""

    for raw_label in labels:
        label = (raw_label or "").strip()
        if not label:
            continue

        pref_key = UI_PREFERENCE_ALIASES.get(label)
        if not pref_key:
            continue

        if pref_key not in intent.preferences:
            intent.preferences.append(pref_key)

        if pref_key == "couple":
            intent.prefer_couple = True
        elif pref_key == "photo":
            intent.prefer_photo = True
        elif pref_key == "food":
            intent.prefer_food = True
        elif pref_key == "culture":
            intent.prefer_culture = True
        elif pref_key == "local_feature":
            intent.prefer_local_feature = True
        elif pref_key == "night_view":
            intent.prefer_night_view = True
        elif pref_key == "quiet":
            intent.prefer_quiet = True
        elif pref_key == "rainy_day":
            intent.prefer_rainy_day = True
        elif pref_key == "queue":
            intent.avoid_queue = True
        elif pref_key == "relaxed":
            intent.pace = "slow"

        _add_unique(intent.intent_tags, [label, pref_key])

    intent.soft_preferences = intent.preferences.copy()
    _mark_hard_constraints(intent)
    return intent


def _mark_hard_constraints(intent: ParsedIntent) -> None:
    flags = set()
    if intent.city:
        flags.add("city")
    if intent.start_location:
        flags.add("start_location")
    if intent.budget is not None:
        flags.add("budget")
    if intent.start_time:
        flags.add("start_time")
    if intent.end_time:
        flags.add("end_time")
    if intent.required_categories:
        flags.add("required_categories")
    if intent.avoid_queue:
        flags.add("avoid_queue")
    if intent.avoid_crowded:
        flags.add("avoid_crowded")
    if intent.max_distance is not None:
        flags.add("max_distance")
    intent.hard_constraints = sorted(flags)


def normalize_llm_intent(draft: LLMIntentDraft, query: str = "") -> ParsedIntent:
    """Normalize an LLM intent draft into the runtime intent model."""

    intent = ParsedIntent(parse_source="llm", llm_payload=draft.dict())

    inferred_city = draft.city or _infer_city_from_text(query) or "广州"
    if inferred_city not in SUPPORTED_CITIES:
        inferred_city = "广州"
    intent.city = inferred_city

    intent.start_location = draft.start_location
    intent.start_time = draft.start_time
    intent.end_time = draft.end_time
    intent.budget = draft.budget
    intent.required_categories = list(dict.fromkeys(draft.required_categories))
    intent.preferred_categories = intent.required_categories.copy()
    intent.preferences = list(dict.fromkeys(draft.preferences))
    intent.soft_preferences = intent.preferences.copy()
    intent.avoid = list(dict.fromkeys(draft.avoid))
    intent.pace = draft.pace or "normal"
    intent.transport_mode = draft.transport_mode or "walking"
    intent.must_include = list(dict.fromkeys(draft.must_include))

    intent.prefer_couple = "couple" in intent.preferences
    intent.prefer_photo = "photo" in intent.preferences
    intent.prefer_food = "food" in intent.preferences
    intent.prefer_culture = "culture" in intent.preferences
    intent.prefer_local_feature = "local_feature" in intent.preferences
    intent.prefer_night_view = "night_view" in intent.preferences
    intent.prefer_quiet = "quiet" in intent.preferences
    intent.prefer_rainy_day = "rainy_day" in intent.preferences
    intent.avoid_queue = "queue" in intent.avoid
    intent.avoid_crowded = "crowded" in intent.avoid

    if intent.preferences:
        _add_unique(intent.intent_tags, intent.preferences)
    if intent.avoid:
        _add_unique(intent.intent_tags, [f"avoid:{item}" for item in intent.avoid])

    _mark_hard_constraints(intent)
    return intent


def parse_intent(query: str, city: str | None = None) -> ParsedIntent:
    """Fallback parser used when no LLM JSON is available yet."""

    text = query or ""
    intent = ParsedIntent(parse_source="fallback")

    if city and city in SUPPORTED_CITIES:
        intent.city = city
    else:
        inferred_city = _infer_city_from_text(text)
        intent.city = inferred_city or "广州"

    start_loc_match = re.search(r"(?:从|由|自)?([^,。；;]{1,30}?)(?:出发|开始|附近|周边)", text)
    if start_loc_match:
        intent.start_location = start_loc_match.group(1).strip()

    intent.start_time = _parse_start_time(text)
    intent.end_time = _parse_end_time(text)
    intent.budget = _parse_budget(text)
    intent.max_distance = _parse_distance(text)
    intent.pace = _parse_pace(text)
    intent.transport_mode = _parse_transport_mode(text)

    _collect_categories(text, intent)
    _collect_preferences(text, intent)
    _collect_avoid(text, intent)

    if intent.required_categories:
        intent.preferred_categories = intent.required_categories.copy()

    intent.soft_preferences = intent.preferences.copy()
    if "relaxed" in intent.preferences:
        intent.pace = "slow"
    _mark_hard_constraints(intent)

    return intent
