"""
评论分析服务模块
=================

本模块负责从POI的文本数据（标签、评论关键词、描述等）中提取特征信号。

主要功能：
- 提取POI的各种特征信号（拍照、约会、美食、文化、本地特色、雨天、安静、排队风险、拥挤风险等）
- 基于关键词匹配进行简单的情感/特征分析
- 提供规范化的信号值（0-1之间）

作者：美团智能路线规划团队
"""

from core.schemas import POI


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _explicit_signal(poi: POI, kind: str) -> float | None:
    signals = getattr(poi, "review_signals", None) or {}
    if not isinstance(signals, dict):
        return None
    value = signals.get(kind)
    if value is None:
        return None
    try:
        return _clamp(float(value))
    except (TypeError, ValueError):
        return None


def signal(poi: POI, kind: str, default: float = 0.5) -> float:
    """
    提取POI的某个特征信号值

    支持的信号类型：
        - photo: 拍照打卡特征
        - date: 约会特征
        - food: 美食特征
        - culture: 文化特征
        - local_feature: 本地特色特征
        - rainy_day: 雨天适合特征
        - quiet: 安静特征
        - queue_risk: 排队风险
        - crowd_risk: 拥挤风险

    参数：
        poi: POI对象
        kind: 信号类型
        default: 默认值

    返回：
        float: 信号值（0-1之间）
    """
    explicit = _explicit_signal(poi, kind)
    if explicit is not None:
        return explicit

    text = " ".join([
        poi.name or "",
        poi.category or "",
        poi.sub_category or "",
        poi.description or "",
        " ".join(poi.tags),
        " ".join(poi.suitable_for),
        " ".join(poi.review_keywords),
        " ".join(getattr(poi, "positive_reviews", []) or []),
        " ".join(getattr(poi, "neutral_reviews", []) or []),
        " ".join(getattr(poi, "negative_reviews", []) or []),
    ]).lower()

    score = default

    # 拍照打卡特征
    if kind == "photo":
        if poi.photo_score is not None:
            score = poi.photo_score / 5.0
        else:
            pos = {"拍", "照", "打卡", "出片", "网红", "摄影", "取景"}
            neg = {"不好拍", "拍不出"}
            score = _count_keywords(text, pos, neg)

    # 约会特征
    elif kind == "date":
        if poi.date_score is not None:
            score = poi.date_score / 5.0
        else:
            pos = {"约会", "情侣", "浪漫", "氛围", "有情调", "约会圣地"}
            neg = {}
            score = _count_keywords(text, pos, neg)

    # 美食特征
    elif kind == "food":
        if poi.food_score is not None:
            score = poi.food_score / 5.0
        else:
            pos = {"好吃", "美食", "餐厅", "吃", "咖啡", "甜点", "必吃", "推荐菜"}
            neg = {"不好吃", "难吃"}
            score = _count_keywords(text, pos, neg)

    # 文化特征
    elif kind == "culture":
        if poi.culture_score is not None:
            score = poi.culture_score / 5.0
        else:
            pos = {"文化", "历史", "博物馆", "展览", "艺术", "人文", "科普"}
            neg = {}
            score = _count_keywords(text, pos, neg)

    # 本地特色特征
    elif kind == "local_feature":
        if poi.local_feature_score is not None:
            score = poi.local_feature_score / 5.0
        else:
            pos = {"本地", "特色", "地道", "老", "传统", "老字号", "烟火气"}
            neg = {}
            score = _count_keywords(text, pos, neg)

    # 雨天适合特征
    elif kind == "rainy_day":
        pos = {"室内", "躲雨", "避雨", "下雨", "雨天", "不受天气", "商场", "博物馆"}
        neg = {"露天", "户外", "晒太阳", "下雨别来"}
        score = _count_keywords(text, pos, neg)

    # 安静特征
    elif kind == "quiet":
        pos = {"安静", "清净", "人少", "幽静", "发呆", "放松", "惬意"}
        neg = {"吵", "闹", "人多", "拥挤", "喧嚣"}
        score = _count_keywords(text, pos, neg)

    # 排队风险
    elif kind == "queue_risk":
        pos = {"排队", "人多", "爆满", "等位", "网红", "热门", "打卡"}
        neg = {"不用排队", "人少", "清静", "冷门"}
        base = poi.queue_level / 5.0 if poi.queue_level is not None else 0.5
        kw = _count_keywords(text, pos, neg)
        score = (base + kw) / 2.0

    # 拥挤风险
    elif kind == "crowd_risk":
        pos = {"人多", "拥挤", "爆满", "热闹", "网红", "热门"}
        neg = {"人少", "清静", "冷门", "空旷"}
        base = poi.queue_level / 5.0 if poi.queue_level is not None else 0.5
        kw = _count_keywords(text, pos, neg)
        score = (base + kw) / 2.0

    return _clamp(score)


def _count_keywords(text: str, pos: set[str], neg: set[str]) -> float:
    """
    统计文本中正面和负面关键词的数量

    参数：
        text: 待分析的文本
        pos: 正面关键词集合
        neg: 负面关键词集合

    返回：
        float: 得分（0-1之间）
    """
    score = 0.5
    # 统计正面关键词
    for w in pos:
        if w in text:
            score += 0.15
    # 统计负面关键词
    for w in neg:
        if w in text:
            score -= 0.15
    return _clamp(score)
