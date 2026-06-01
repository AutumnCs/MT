from __future__ import annotations

from schemas import POI


KEYWORDS = {
    "photo": ["拍照", "打卡", "出片", "江景", "景观", "地标", "夜景", "灯光"],
    "date": ["约会", "情侣", "浪漫", "安静", "氛围", "精致"],
    "food": ["美食", "好吃", "粤菜", "本帮菜", "点心", "正餐", "老字号", "甜品", "咖啡"],
    "culture": ["文化", "历史", "艺术", "展览", "博物馆", "美术馆", "建筑"],
    "local_feature": ["本地", "特色", "老字号", "粤菜", "本帮菜", "地方", "传统"],
    "rainy_day": ["室内", "商场", "展馆", "咖啡", "餐厅", "避雨", "雨天"],
    "quiet": ["安静", "清净", "人少", "舒适", "松弛"],
    "queue_risk": ["排队", "等位", "热门", "人多", "拥挤", "高峰"],
    "value": ["性价比", "免费", "便宜", "划算", "低成本"],
}

CATEGORY_PRIORS = {
    "coffee": {"photo": 0.55, "date": 0.65, "food": 0.55, "rainy_day": 0.75, "quiet": 0.55},
    "food": {"food": 0.85, "local_feature": 0.55, "rainy_day": 0.7},
    "museum": {"culture": 0.9, "rainy_day": 0.85, "quiet": 0.55},
    "exhibition": {"culture": 0.85, "photo": 0.65, "rainy_day": 0.85},
    "scene": {"photo": 0.75, "culture": 0.45},
    "street": {"photo": 0.65, "local_feature": 0.5, "food": 0.45},
    "shopping": {"rainy_day": 0.75, "food": 0.45},
    "park": {"quiet": 0.65, "value": 0.7},
    "night": {"photo": 0.9, "date": 0.65},
}


def _clip(value: float) -> float:
    return max(0.0, min(1.0, value))


def _joined_text(poi: POI) -> str:
    values = [
        poi.name,
        poi.category,
        poi.sub_category or "",
        poi.district or "",
        poi.business_area or "",
        poi.address,
        poi.description,
        " ".join(poi.tags),
        " ".join(poi.suitable_for),
        " ".join(poi.review_keywords),
        " ".join(poi.positive_reviews),
        " ".join(poi.negative_reviews),
    ]
    return " ".join(value for value in values if value)


def infer_review_signals(poi: POI) -> dict[str, float]:
    if poi.review_signals:
        return {key: _clip(float(value)) for key, value in poi.review_signals.items()}

    text = _joined_text(poi)
    priors = CATEGORY_PRIORS.get(poi.category, {})
    signals = {
        "photo": poi.photo_score / 5,
        "date": poi.date_score / 5,
        "food": poi.food_score / 5,
        "culture": poi.culture_score / 5,
        "local_feature": poi.local_feature_score / 5,
        "rainy_day": poi.rainy_day_score / 5,
        "quiet": 1 - poi.queue_level / 5,
        "queue_risk": poi.queue_level / 5,
        "crowd_risk": poi.queue_level / 5,
        "value": 0.85 if poi.price == 0 else 0.65 if poi.price <= 60 else 0.45,
    }

    for key, value in priors.items():
        signals[key] = max(signals.get(key, 0.0), value)

    for key, words in KEYWORDS.items():
        hits = sum(1 for word in words if word in text)
        if hits:
            signals[key] = max(signals.get(key, 0.0), min(1.0, 0.45 + hits * 0.12))

    if poi.negative_reviews:
        negative_text = " ".join(poi.negative_reviews)
        if any(word in negative_text for word in ["排队", "等位", "人多", "拥挤"]):
            signals["queue_risk"] = max(signals["queue_risk"], 0.75)
            signals["crowd_risk"] = max(signals["crowd_risk"], 0.7)
        if any(word in negative_text for word in ["贵", "偏贵", "价格"]):
            signals["value"] = min(signals["value"], 0.45)

    return {key: round(_clip(value), 4) for key, value in signals.items()}


def signal(poi: POI, key: str, fallback: float = 0.5) -> float:
    return infer_review_signals(poi).get(key, fallback)
