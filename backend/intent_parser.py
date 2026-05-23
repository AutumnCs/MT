import re

from schemas import ParsedIntent


CITIES = ["广州", "上海", "深圳", "北京", "杭州", "成都", "苏州", "南京"]

LANDMARK_CITY_HINTS = {
    "广州塔": "广州",
    "花城广场": "广州",
    "海心沙": "广州",
    "珠江新城": "广州",
    "外滩": "上海",
    "武康路": "上海",
    "豫园": "上海",
    "东方明珠": "上海",
}

CATEGORY_KEYWORDS = {
    "coffee": ["咖啡", "咖啡店", "下午茶"],
    "food": ["吃饭", "晚饭", "午饭", "美食", "餐厅", "火锅", "小吃", "甜品", "本帮菜", "粤菜"],
    "museum": ["博物馆", "展馆"],
    "exhibition": ["看展", "展览", "美术馆", "艺术展"],
    "scene": ["景点", "外滩", "豫园", "广州塔", "东方明珠"],
    "street": ["街区", "老街", "武康路", "思南路", "永庆坊", "东山口"],
    "shopping": ["购物", "逛街", "商场", "买东西"],
    "park": ["公园", "散步", "江边", "绿地"],
    "night": ["夜景", "夜游", "晚上看景", "夜生活"],
}

PREFERENCE_KEYWORDS = {
    "couple": ["约会", "浪漫", "情侣"],
    "photo": ["拍照", "打卡", "出片", "摄影"],
    "food": ["吃货", "美食", "好吃的"],
    "culture": ["文化", "历史", "博物馆", "艺术"],
    "local_feature": ["本地特色", "老字号", "本帮菜", "广府特色", "上海特色"],
    "night_view": ["夜景", "灯光", "夜晚"],
    "quiet": ["安静", "轻松", "休闲", "不吵"],
    "rainy_day": ["雨天", "下雨", "室内", "避雨"],
}

AVOID_KEYWORDS = {
    "spicy": ["不要辣", "不吃辣", "忌辣"],
    "far": ["太远", "近一点", "别太绕"],
    "queue": ["不想排队", "别排太久", "不想等位"],
    "crowded": ["人少", "不拥挤", "避开人多"],
}


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _matched_keywords(text: str, keywords: list[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword in text]


def _parse_budget(text: str) -> int | None:
    budget_match = re.search(r"预算\s*(\d+)", text)
    if budget_match:
        return int(budget_match.group(1))

    if _contains_any(text, ["低预算", "省钱", "便宜一点"]):
        return 100
    if _contains_any(text, ["中等预算", "预算一般"]):
        return 200
    return None


def _parse_pace(text: str) -> str:
    if _contains_any(text, ["轻松", "慢慢逛", "不赶", "悠闲", "不想太累"]):
        return "slow"
    if _contains_any(text, ["紧凑", "高效", "多打卡", "赶时间", "半日内"]):
        return "fast"
    return "normal"


def _parse_start_time(text: str) -> str | None:
    patterns = [
        r"((?:上午|中午|下午|晚上)?\s*\d{1,2}(?:点半|点|:\d{2}))",
        r"((?:上午|中午|下午|晚上)?\s*[一二三四五六七八九十两]\s*点半?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).replace(" ", "")
    return None


def _parse_end_time(text: str) -> str | None:
    match = re.search(r"(晚上?\s*\d{1,2}\s*点(?:前|之前)|\d{1,2}\s*点前)", text)
    if match:
        return match.group(1).replace(" ", "")
    return None


def parse_intent(query: str) -> ParsedIntent:
    intent = ParsedIntent()

    for city in CITIES:
        if city in query:
            intent.city = city
            break

    start_loc_match = re.search(r"从(.+?)(?:出发|开始)", query)
    if start_loc_match:
        intent.start_location = start_loc_match.group(1).strip()

    if intent.city == "广州":
        for landmark, city in LANDMARK_CITY_HINTS.items():
            if landmark in query or (intent.start_location and landmark in intent.start_location):
                intent.city = city
                break

    intent.start_time = _parse_start_time(query)
    intent.end_time = _parse_end_time(query)
    intent.budget = _parse_budget(query)
    intent.pace = _parse_pace(query)

    distance_match = re.search(r"(\d+)\s*公里", query)
    if distance_match:
        intent.max_distance = float(distance_match.group(1))

    for category, keywords in CATEGORY_KEYWORDS.items():
        if _contains_any(query, keywords) and category not in intent.required_categories:
            intent.required_categories.append(category)

    if intent.required_categories:
        intent.preferred_categories = intent.required_categories.copy()

    for pref_key, keywords in PREFERENCE_KEYWORDS.items():
        if _contains_any(query, keywords):
            setattr(intent, f"prefer_{pref_key}", True)
            for item in _matched_keywords(query, keywords):
                if item not in intent.intent_tags:
                    intent.intent_tags.append(item)

    for avoid_key, keywords in AVOID_KEYWORDS.items():
        if _contains_any(query, keywords):
            intent.avoid.append(avoid_key)
            if avoid_key == "queue":
                intent.avoid_queue = True
            if avoid_key == "crowded":
                intent.avoid_crowded = True

    if intent.prefer_couple:
        intent.preferences.append("date")
    if intent.prefer_photo:
        intent.preferences.append("photo")
    if intent.prefer_food:
        intent.preferences.append("food")

    return intent
