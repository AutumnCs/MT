"""
意图解析器模块
==============

功能说明：
    本模块负责将用户的自然语言需求解析为结构化的意图数据。

解析策略：
    1. 优先使用 LLM 解析（如果可用）
    2. LLM 失败时回退到本地规则解析
    3. 支持城市识别、时间解析、预算解析、偏好识别等

主要功能：
    - parse_intent: 主解析入口
    - normalize_llm_intent: LLM 结果归一化
    - parse_time: 时间解析
    - parse_budget: 预算解析
    - extract_preferences: 偏好提取

使用场景：
    - FastAPI 路由处理
    - 用户意图理解
    - 路线规划前置处理

Author: MeituanAgent Team
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from core.intent_lexicon import INTENT_LEXICON, prompt_lexicon_excerpt
from core.semantic_intent import apply_semantic_hints
from core.schemas import ParsedIntent


# ============================================================================
# 常量定义
# ============================================================================

# 支持的城市列表
SUPPORTED_CITIES = ["广州", "上海"]

# 默认城市
DEFAULT_CITY = "上海"

# 预算范围限制
MIN_BUDGET = 50
MAX_BUDGET = 5000

_CATEGORY_FALLBACK_KEYWORDS = {
    "category_coffee": ["咖啡", "咖啡店", "下午茶", "茶饮", "甜品", "蛋糕", "瑞幸", "喜茶"],
    "category_food": ["吃饭", "美食", "餐厅", "饭店", "午餐", "晚餐", "早餐", "小吃", "本地小吃", "吃点东西", "吃点", "本帮菜", "粤菜", "川菜", "湘菜", "火锅", "烧烤", "素食"],
    "category_library": ["图书馆", "图书", "书馆", "阅读", "自习", "看书"],
    "category_exhibition": ["展览", "博物馆", "美术馆", "画廊", "看展", "艺术展", "书店"],
    "category_night": ["夜景", "夜生活", "看夜景", "夜游", "江景", "灯光", "酒吧", "清吧", "夜场"],
    "category_street": ["逛街", "购物", "商业街", "步行街", "老街", "弄堂", "小巷", "散步", "citywalk", "逛逛", "随便逛逛", "小店", "玩", "游玩", "逛玩"],
    "category_park": ["公园", "户外", "绿地", "江边", "河边", "湖边", "滨江", "爬山", "徒步"],
    "category_shopping": ["商场", "购物", "逛商场", "商圈", "mall"],
    "category_museum": ["博物馆", "展馆", "纪念馆", "陈列馆"],
    "category_scene": ["景点", "风景", "景色", "看风景", "欣赏景色", "江景", "观景", "打卡点", "景区", "玩", "游玩"],
}

_PREFERENCE_FALLBACK_KEYWORDS = {
    "prefer_couple": ["约会", "情侣", "浪漫", "二人世界", "烛光晚餐", "甜蜜"],
    "prefer_photo": ["拍照", "打卡", "出片", "好看", "上镜", "氛围感", "网红"],
    "prefer_food": ["美食", "吃饭", "吃点好的", "吃点东西", "吃点", "好吃", "小吃", "本地小吃", "本帮菜", "粤式点心", "正餐", "探店", "简餐", "咖啡", "下午茶"],
    "prefer_culture": ["文化", "历史", "古迹", "博物馆", "人文", "艺术", "看展"],
    "prefer_local_feature": ["本地特色", "接地气", "本地味", "烟火气", "老字号", "地道", "本帮菜", "粤式点心", "不太商业", "不要太商业", "别太商业"],
    "prefer_night_view": ["夜景", "夜游", "看夜景", "灯光秀", "夜生活"],
    "prefer_quiet": ["安静", "清净", "清闲", "轻松", "松弛", "不吵", "人少", "慢慢逛", "坐坐", "发呆"],
    "prefer_rainy_day": ["雨天", "下雨", "避雨", "室内优先", "室内", "躲雨"],
    "prefer_walking": ["步行", "散步", "citywalk", "逛逛", "溜达", "走路"],
    "prefer_family": ["亲子", "带娃", "小朋友", "孩子", "家庭", "一家人"],
    "prefer_coffee": ["咖啡", "咖啡店", "喝杯咖啡", "下午茶"],
    "prefer_friends": ["朋友", "闺蜜", "同学", "聚会", "朋友局"],
    "prefer_solo": ["一个人", "独自", "solo", "独行"],
    "prefer_value": ["性价比", "划算", "实惠", "便宜", "预算友好", "省钱"],
    "prefer_premium": ["顶奢", "高端", "精致", "贵一点", "吃好点", "品质感", "仪式感", "不要便宜路线", "不要太便宜"],
    "prefer_indoor": ["室内", "室内优先", "避雨", "不淋雨", "馆内", "店内"],
    "prefer_outdoor": ["室外", "户外", "露天", "外面", "室外优先"],
    "prefer_shopping": ["购物", "商场", "逛商场", "商圈", "逛小店", "小店"],
    "prefer_citywalk": ["citywalk", "city walk", "城市漫步", "慢逛", "闲逛", "逛逛"],
    "prefer_efficient": ["高效", "尽快", "快一点", "省时间", "效率", "不折腾"],
    "prefer_compact": ["紧凑", "少绕路", "少转场", "不绕", "顺路", "串起来"],
}

_AVOID_FALLBACK_KEYWORDS = {
    "avoid_spicy": ["不要辣", "不吃辣", "少辣", "清淡"],
    "avoid_far": ["别太远", "不要太远", "近一点", "更近", "不要跑太远"],
    "avoid_queue": ["不想排队", "不要排队", "少排队", "排队太久", "不想排太久队", "不想排太久"],
    "avoid_crowded": ["人多", "拥挤", "别太挤", "避开人多", "别太拥挤"],
}


def _normalize_avoid_key(value: str) -> str:
    mapping = {
        "spicy": "avoid_spicy",
        "far": "avoid_far",
        "queue": "avoid_queue",
        "crowded": "avoid_crowded",
    }
    return mapping.get(value, value)


def _parse_chinese_number(num_text: str) -> Optional[int]:
    if not num_text:
        return None
    digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    units = {"十": 10, "百": 100, "千": 1000}
    total = 0
    number = 0
    has_value = False
    for char in num_text:
        if char in digits:
            number = digits[char]
            has_value = True
        elif char in units:
            total += (number or 1) * units[char]
            number = 0
            has_value = True
        else:
            return None
    return total + number if has_value else None


def _keywords_with_fallback(lexicon_key: str, fallback_map: dict[str, list[str]]) -> list[str]:
    keywords = list(INTENT_LEXICON.get(lexicon_key, []) or [])
    if keywords:
        return keywords
    return list(fallback_map.get(lexicon_key, []))


_NEGATION_PREFIXES = ("不要", "别", "不想", "不太想", "不用", "无需", "不需要", "拒绝")


def _is_negated_keyword(query: str, keyword: str, window_size: int = 6) -> bool:
    """Return whether a matched keyword is locally negated in the user query."""

    if not query or not keyword:
        return False
    start = query.find(keyword)
    while start >= 0:
        prefix = query[max(0, start - window_size) : start]
        if any(marker in prefix for marker in _NEGATION_PREFIXES):
            return True
        start = query.find(keyword, start + len(keyword))
    return False


def _has_positive_keyword(query: str, keyword: str) -> bool:
    return keyword in query and not _is_negated_keyword(query, keyword)


def _rejects_value_route(query: str) -> bool:
    normalized = (query or "").replace(" ", "")
    markers = (
        "不要便宜",
        "别便宜",
        "不想便宜",
        "不要太便宜",
        "不要给我太便宜",
        "不要便宜路线",
        "别给我便宜",
        "不走便宜",
        "不要省钱",
        "不省钱",
    )
    return any(marker in normalized for marker in markers)


_SCORE_CATEGORY_TAGS = {
    "food",
    "coffee",
    "library",
    "exhibition",
    "museum",
    "night",
    "street",
    "park",
    "shopping",
    "scene",
}
_SCORE_PREFERENCE_TAGS = {
    "couple",
    "photo",
    "food",
    "culture",
    "local_feature",
    "night_view",
    "quiet",
    "rainy_day",
    "walking",
    "family",
    "friends",
    "solo",
    "value",
    "premium",
    "indoor",
    "outdoor",
    "shopping",
    "citywalk",
    "efficient",
    "compact",
    "relaxed",
}
_SCORE_AVOID_TAGS = {"avoid_spicy", "avoid_far", "avoid_queue", "avoid_crowded"}


def _normalize_score_tag(raw_key: str) -> str:
    key = str(raw_key or "").strip()
    if not key:
        return ""
    mapped = _PREFERENCE_LABEL_TO_KEY.get(key, key)
    mapped = _normalize_avoid_key(mapped)
    if mapped.startswith("prefer_"):
        mapped = mapped.removeprefix("prefer_")
    if mapped.startswith("category_"):
        mapped = mapped.removeprefix("category_")
    return mapped


def _coerce_semantic_scores(raw_scores: Any) -> dict[str, float]:
    if not isinstance(raw_scores, dict):
        return {}
    scores: dict[str, float] = {}
    for raw_key, raw_value in raw_scores.items():
        key = _normalize_score_tag(str(raw_key))
        if key not in _SCORE_CATEGORY_TAGS and key not in _SCORE_PREFERENCE_TAGS and key not in _SCORE_AVOID_TAGS:
            continue
        try:
            score = float(raw_value)
        except (TypeError, ValueError):
            continue
        if score > 1.0 and score <= 100.0:
            score = score / 100.0
        scores[key] = max(0.0, min(1.0, score))
    return scores


def _coerce_semantic_evidence(raw_evidence: Any) -> dict[str, str]:
    if not isinstance(raw_evidence, dict):
        return {}
    evidence: dict[str, str] = {}
    for raw_key, raw_value in raw_evidence.items():
        key = _normalize_score_tag(str(raw_key))
        if not key:
            continue
        text = str(raw_value or "").strip()
        if text:
            evidence[key] = text[:80]
    return evidence


def _apply_semantic_scores_to_fields(
    *,
    categories: list[str],
    preferences: list[str],
    avoid: list[str],
    scores: dict[str, float],
    query: str,
) -> tuple[list[str], list[str], list[str]]:
    if not scores:
        return categories, preferences, avoid

    for tag, score in scores.items():
        if tag in _SCORE_CATEGORY_TAGS and score >= 0.75 and tag not in categories:
            categories.append(tag)
        if tag in _SCORE_PREFERENCE_TAGS and score >= 0.65 and tag not in preferences:
            preferences.append(tag)
        if tag in _SCORE_AVOID_TAGS and score >= 0.70 and tag not in avoid:
            avoid.append(tag)

    premium_score = scores.get("premium", 0.0)
    value_score = scores.get("value", 0.0)
    if _rejects_value_route(query) or (premium_score >= 0.70 and value_score < 0.62):
        preferences = [item for item in preferences if item != "value"]

    return list(dict.fromkeys(categories)), list(dict.fromkeys(preferences)), list(dict.fromkeys(avoid))


def _derive_party_types(preferences: list[str]) -> list[str]:
    return [item for item in ("couple", "family", "friends", "solo") if item in (preferences or [])]


def _extract_quantity_constraints(query: str) -> tuple[dict[str, int], dict[str, int]]:
    """Extract light quantity constraints from user wording."""

    text = (query or "").strip()
    if not text:
        return {}, {}

    min_counts: dict[str, int] = {}
    max_counts: dict[str, int] = {}

    scene_min_tokens = (
        "多看几个景点",
        "多看点景点",
        "多看些景点",
        "几个景点",
        "多逛几个景点",
        "多去几个景点",
        "多看几个地点",
    )
    if any(token in text for token in scene_min_tokens):
        min_counts["scene"] = max(min_counts.get("scene", 0), 2)

    food_min_tokens = (
        "顺便喝个早茶",
        "顺便喝早茶",
        "加个早茶",
        "喝个早茶",
        "去吃个早茶",
        "带个早茶",
    )
    if any(token in text for token in food_min_tokens):
        min_counts["food"] = max(min_counts.get("food", 0), 1)

    food_cap_tokens = (
        "别安排太多饭店",
        "不要太多饭店",
        "少安排饭店",
        "别太多饭店",
        "少安排餐饮",
        "别安排太多餐厅",
        "别太多餐厅",
        "少点饭店",
    )
    if any(token in text for token in food_cap_tokens):
        max_counts["food"] = 1

    return min_counts, max_counts


def _extract_unclassified_clues(query: str, known_terms: list[str]) -> list[str]:
    """Keep lightweight residual clues so long-tail phrasing is not lost."""

    text = (query or "").strip()
    if not text:
        return []

    clues: list[str] = []
    normalized_known = {term.strip().lower() for term in known_terms if term}
    ascii_phrases = []
    for match in re.finditer(r"[A-Za-z]+(?:\s*[A-Za-z]+)*(?:\s*感)?", text):
        phrase = match.group(0).strip()
        if phrase:
            ascii_phrases.append(phrase)

    for phrase in ascii_phrases:
        if phrase.lower() not in normalized_known and phrase not in clues:
            clues.append(phrase)

    for token in ("vibe感", "vibe", "松弛感", "氛围感", "citywalk感"):
        if token in text and token not in clues:
            clues.append(token)

    return clues


# ============================================================================
# 意图解析器类
# ============================================================================

class IntentParser:
    """
    意图解析器类

    功能：
        将自然语言解析为结构化意图

    使用方法：
        parser = IntentParser()
        intent = parser.parse_intent("周六下午从广州塔出发，预算200，想约会")
    """

    def __init__(self):
        """初始化意图解析器"""
        self.lexicon = INTENT_LEXICON

    def parse_intent(
        self,
        query: str,
        explicit_city: Optional[str] = None,
    ) -> ParsedIntent:
        """
        解析用户输入为主意图

        参数：
            query: 用户输入的自然语言文本
            explicit_city: 显式指定的城市（来自前端）

        返回：
            ParsedIntent: 解析后的结构化意图
        """
        query = query or ""

        # 1. 解析城市（显式 > 地标反推 > 默认）
        city = self._parse_city(query, explicit_city)

        # 2. 解析时间
        start_time, end_time = self._parse_time(query)

        # 3. 解析预算
        budget = self._parse_budget(query)

        # 4. 解析起点
        start_location = self._extract_start_location(query)

        # 5. 解析类别
        categories = self._extract_categories(query)

        # 6. 解析偏好
        preferences = self._extract_preferences(query)

        # 7. 解析避雷项
        avoid = self._extract_avoid(query)

        # 8. 解析节奏
        pace = self._extract_pace(query)

        # 9. 解析交通方式
        transport_mode = self._extract_transport_mode(query)

        # 10. 提取必须包含的项目
        must_include = self._extract_must_include(query)
        if start_location:
            must_include = [item for item in must_include if item not in start_location and start_location not in item]

        category_min_counts, category_caps = _extract_quantity_constraints(query)

        # 11. 保留未能稳定归类的线索，方便后续扩词典与回归
        unclassified_clues = _extract_unclassified_clues(
            query,
            [*categories, *preferences, *avoid, *must_include, city or "", start_location or ""],
        )

        intent = ParsedIntent(
            city=city,
            start_location=start_location,
            start_time=start_time,
            end_time=end_time,
            budget=budget,
            required_categories=categories,
            preferences=preferences,
            party_types=_derive_party_types(preferences),
            primary_party_type=_derive_party_types(preferences)[0] if _derive_party_types(preferences) else None,
            avoid=avoid,
            pace=pace,
            transport_mode=transport_mode,
            must_include=must_include,
            category_min_counts=category_min_counts,
            category_caps=category_caps,
            unclassified_clues=unclassified_clues,
            notes=None,
        )
        apply_semantic_hints(intent, query)
        return intent

    def _parse_city(
        self,
        query: str,
        explicit_city: Optional[str] = None,
    ) -> Optional[str]:
        """
        解析城市

        优先级：
            1. explicit_city（前端显式选择）
            2. 查询文本中的城市名/地标

        参数：
            query: 用户查询文本
            explicit_city: 前端显式选择的城市

        返回：
            城市名称或 None
        """
        # 优先使用显式城市
        if explicit_city:
            for city in SUPPORTED_CITIES:
                if city in explicit_city:
                    return city

        # 从查询文本中识别城市
        query_lower = query.lower()

        # 检查直接城市名
        for city in SUPPORTED_CITIES:
            if city in query:
                return city

        # 检查地标
        guangzhou_landmarks = self.lexicon.get("city_guangzhou", [])
        shanghai_landmarks = self.lexicon.get("city_shanghai", [])

        for landmark in guangzhou_landmarks:
            if landmark in query:
                return "广州"

        for landmark in shanghai_landmarks:
            if landmark in query:
                return "上海"

        return None

    def _parse_time(self, query: str) -> tuple[Optional[str], Optional[str]]:
        """
        解析时间

        支持的格式：
            - 周六下午两点
            - 14:00
            - 下午2点
            - 晚上7点

        参数：
            query: 用户查询文本

        返回：
            (开始时间, 结束时间) 元组
        """
        start_time = None
        end_time = None

        def _hour(match: re.Match, group: int = 1) -> int:
            raw = match.group(group)
            if raw.isdigit():
                return int(raw)
            parsed = _parse_chinese_number(raw)
            return int(parsed or 0)

        def _format_hour(hour: int, period: str | None = None) -> str:
            if period in {"下午", "晚上"} and hour < 12:
                hour += 12
            return f"{hour:02d}:00"

        # 解析开始时间
        time_patterns = [
            # X点Y分
            (r"(\d{1,2}|[零〇一二两三四五六七八九十]{1,3})点(\d{1,2}|[零〇一二两三四五六七八九十]{1,3})分", lambda m: f"{_hour(m, 1):02d}:{_hour(m, 2):02d}"),
            # 下午2点 -> 14:00
            (r"(下午|晚上|早上|中午)(\d{1,2}|[零〇一二两三四五六七八九十]{1,3})[点时]", lambda m: _format_hour(_hour(m, 2), m.group(1))),
            # 2点 -> 02:00；中文数字需要有“下午/晚上”等时段词，避免“人多一点”误识别。
            (r"(\d{1,2})[点时]", lambda m: _format_hour(_hour(m))),
            # HH:MM 格式
            (r"(\d{1,2}):(\d{2})", lambda m: f"{int(m.group(1)):02d}:{m.group(2)}"),
        ]

        for pattern, extractor in time_patterns:
            match = re.search(pattern, query)
            if match:
                start_time = extractor(match)
                break

        # 解析结束时间（如果有明确说明）
        # 例如："晚上9点前结束"
        end_pattern = r"(晚上|下午|早上|中午)?(\d{1,2}|[零〇一二两三四五六七八九十]{1,3})[点时](?:前|以前|之前|结束)"
        end_match = re.search(end_pattern, query)
        if end_match:
            hour = _hour(end_match, 2)
            end_time = _format_hour(hour, end_match.group(1))

        return start_time, end_time

    def _parse_budget(self, query: str) -> Optional[float]:
        """
        ????

        ??????
            - ??200
            - ?? 200 ?
            - 200?
            - ???
            - ?????

        ???
            ????????????????????????
            ??????/??????????????????

        ???
            query: ??????

        ???
            ????? None
        """
        text = query or ""
        if not text:
            return None

        normalized = text.replace("人民币", "元").replace("块钱", "块")

        def _clean_amount(value: float) -> Optional[float]:
            if value <= 0:
                return None
            if value > MAX_BUDGET:
                return None
            return float(value)

        def _parse_chinese_number(num_text: str) -> Optional[float]:
            if not num_text:
                return None
            digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
            units = {"十": 10, "百": 100, "千": 1000, "万": 10000}
            total = 0
            section = 0
            number = 0
            has_value = False
            for char in num_text:
                if char in digits:
                    number = digits[char]
                    has_value = True
                elif char in units:
                    unit = units[char]
                    has_value = True
                    if unit == 10000:
                        section = (section + number) * unit
                        total += section
                        section = 0
                    else:
                        section += (number or 1) * unit
                    number = 0
                else:
                    return None
            return float(total + section + number) if has_value else None

        digit_patterns = [
            r"(?:预算|花费|花销|消费|预算为|预算是)\s*(\d+(?:\.\d+)?)\s*(?:元|块钱|块|人民币)?",
            r"(\d+(?:\.\d+)?)\s*(?:元|块钱|块|人民币)",
        ]
        for pattern in digit_patterns:
            match = re.search(pattern, normalized)
            if match:
                amount = _clean_amount(float(match.group(1)))
                if amount is not None:
                    return amount

        chinese_pattern = r"([零〇一二两三四五六七八九十百千万]+)\s*(?:元|块钱|块|人民币)"
        chinese_match = re.search(chinese_pattern, normalized)
        if chinese_match:
            amount = _parse_chinese_number(chinese_match.group(1))
            amount = _clean_amount(amount) if amount is not None else None
            if amount is not None:
                return amount

        return None

    def _extract_start_location(self, query: str) -> Optional[str]:
        """
        提取起点位置

        参数：
            query: 用户查询文本

        返回：
            起点位置字符串或 None
        """
        # 匹配 "从XXX出发" 模式
        pattern = r"从(.+?)(?:出发|开始)"
        match = re.search(pattern, query)
        if match:
            return match.group(1).strip()

        return None

    def _extract_categories(self, query: str) -> List[str]:
        """
        提取类别

        参数：
            query: 用户查询文本

        返回：
            类别列表
        """
        categories = []
        category_map = {
            "category_coffee": "coffee",
            "category_food": "food",
            "category_library": "library",
            "category_exhibition": "exhibition",
            "category_night": "night",
            "category_street": "street",
            "category_park": "park",
            "category_shopping": "shopping",
            "category_museum": "museum",
            "category_scene": "scene",
        }

        for lexicon_key, category in category_map.items():
            keywords = _keywords_with_fallback(lexicon_key, _CATEGORY_FALLBACK_KEYWORDS)
            for keyword in keywords:
                if keyword in query:
                    if category not in categories:
                        categories.append(category)
                    break

        return categories

    def _extract_preferences(self, query: str) -> List[str]:
        """
        提取偏好

        参数：
            query: 用户查询文本

        返回：
            偏好列表
        """
        preferences = []
        preference_map = {
            "prefer_couple": "couple",
            "prefer_photo": "photo",
            "prefer_food": "food",
            "prefer_culture": "culture",
            "prefer_local_feature": "local_feature",
            "prefer_night_view": "night_view",
            "prefer_quiet": "quiet",
            "prefer_rainy_day": "rainy_day",
            "prefer_walking": "walking",
            "prefer_family": "family",
            "prefer_coffee": "coffee",
            "prefer_friends": "friends",
            "prefer_solo": "solo",
            "prefer_value": "value",
            "prefer_premium": "premium",
            "prefer_indoor": "indoor",
            "prefer_outdoor": "outdoor",
            "prefer_shopping": "shopping",
            "prefer_citywalk": "citywalk",
            "prefer_efficient": "efficient",
            "prefer_compact": "compact",
        }

        for lexicon_key, preference in preference_map.items():
            keywords = _keywords_with_fallback(lexicon_key, _PREFERENCE_FALLBACK_KEYWORDS)
            for keyword in keywords:
                matched = _has_positive_keyword(query, keyword) if preference == "value" else keyword in query
                if matched:
                    if preference not in preferences:
                        preferences.append(preference)
                    break

        if _rejects_value_route(query):
            preferences = [item for item in preferences if item != "value"]

        return preferences

    def _extract_avoid(self, query: str) -> List[str]:
        """
        提取避雷项

        参数：
            query: 用户查询文本

        返回：
            避雷项列表
        """
        avoid_list = []
        avoid_map = {
            "avoid_spicy": "avoid_spicy",
            "avoid_far": "avoid_far",
            "avoid_queue": "avoid_queue",
            "avoid_crowded": "avoid_crowded",
        }

        for lexicon_key, avoid_item in avoid_map.items():
            keywords = _keywords_with_fallback(lexicon_key, _AVOID_FALLBACK_KEYWORDS)
            for keyword in keywords:
                if keyword in query:
                    normalized = _normalize_avoid_key(avoid_item)
                    if normalized not in avoid_list:
                        avoid_list.append(normalized)
                    break

        return avoid_list

    def _extract_pace(self, query: str) -> str:
        """
        提取活动节奏

        参数：
            query: 用户查询文本

        返回：
            节奏类型：fast/normal/slow
        """
        # 检查快节奏关键词
        for keyword in self.lexicon.get("pace_fast", []):
            if keyword in query:
                return "fast"

        # 检查慢节奏关键词
        for keyword in self.lexicon.get("pace_slow", []):
            if keyword in query:
                return "slow"

        return "normal"

    def _extract_transport_mode(self, query: str) -> str:
        """
        提取交通方式偏好

        参数：
            query: 用户查询文本

        返回：
            交通方式：walking/metro/taxi/mixed
        """
        if "地铁" in query or "metro" in query.lower():
            return "metro"
        elif "打车" in query or "出租车" in query:
            return "taxi"
        elif "步行" in query or "走路" in query:
            return "walking"

        return "mixed"

    def _extract_must_include(self, query: str) -> List[str]:
        """
        提取必须包含的项目

        参数：
            query: 用户查询文本

        返回：
            必须包含的项目列表
        """
        # 目前主要是地标
        must_include = []
        guangzhou_landmarks = self.lexicon.get("city_guangzhou", [])
        shanghai_landmarks = self.lexicon.get("city_shanghai", [])

        for landmark in guangzhou_landmarks + shanghai_landmarks:
            if landmark in query and len(landmark) >= 3:  # 只保留较长的地标
                must_include.append(landmark)

        return must_include


# ============================================================================
# 模块级兼容入口
# ============================================================================

_PREFERENCE_LABEL_TO_KEY: Dict[str, str] = {
    "约会": "couple",
    "拍照": "photo",
    "出片": "photo",
    "打卡": "photo",
    "不想排队": "avoid_queue",
    "不要排队": "avoid_queue",
    "性价比": "value",
    "高端": "premium",
    "高端精致": "premium",
    "顶奢": "premium",
    "轻松路线": "relaxed",
    "轻松": "relaxed",
    "美食": "food",
    "文艺": "culture",
    "夜景": "night_view",
    "本地特色": "local_feature",
    "安静": "quiet",
    "雨天": "rainy_day",
    "咖啡": "coffee",
    "博物馆": "museum",
    "展览": "exhibition",
    "景点": "scene",
    "街区": "street",
    "购物": "shopping",
    "公园": "park",
    "亲子": "family",
    "朋友": "friends",
    "独行": "solo",
    "citywalk": "citywalk",
    "步行": "walking",
    "室内": "indoor",
    "室外": "outdoor",
    "高效": "efficient",
    "紧凑": "compact",
}

_AVOID_LABELS = {
    "avoid_spicy",
    "avoid_far",
    "avoid_queue",
    "avoid_crowded",
}


def parse_intent(query: str, explicit_city: Optional[str] = None) -> ParsedIntent:
    """Backward-compatible module-level parser."""

    return IntentParser().parse_intent(query, explicit_city)


def refresh_intent_derived_fields(intent: ParsedIntent) -> ParsedIntent:
    """Recompute legacy flags and derived fields from the current list schema."""

    preference_flags = {
        "couple": "prefer_couple",
        "photo": "prefer_photo",
        "food": "prefer_food",
        "culture": "prefer_culture",
        "local_feature": "prefer_local_feature",
        "night_view": "prefer_night_view",
        "quiet": "prefer_quiet",
        "rainy_day": "prefer_rainy_day",
        "walking": "prefer_walking",
        "family": "prefer_family",
        "friends": "prefer_friends",
        "solo": "prefer_solo",
        "value": "prefer_value",
        "premium": "prefer_premium",
        "indoor": "prefer_indoor",
        "outdoor": "prefer_outdoor",
        "citywalk": "prefer_citywalk",
        "efficient": "prefer_efficient",
        "compact": "prefer_compact",
    }
    avoid_flags = {
        "avoid_spicy": "avoid_spicy",
        "avoid_far": "avoid_far",
        "avoid_queue": "avoid_queue",
        "avoid_crowded": "avoid_crowded",
    }

    for field_name in preference_flags.values():
        setattr(intent, field_name, False)
    for field_name in avoid_flags.values():
        setattr(intent, field_name, False)

    for key, field_name in preference_flags.items():
        if key in getattr(intent, "preferences", []):
            setattr(intent, field_name, True)

    for key, field_name in avoid_flags.items():
            if key in [_normalize_avoid_key(item) for item in getattr(intent, "avoid", [])]:
                setattr(intent, field_name, True)

    party_types = _derive_party_types(list(getattr(intent, "preferences", []) or []))
    existing_party_types = [str(item) for item in getattr(intent, "party_types", []) or [] if item]
    intent.party_types = list(dict.fromkeys([*existing_party_types, *party_types]))
    if intent.party_types:
        intent.primary_party_type = str(getattr(intent, "primary_party_type", None) or intent.party_types[0])
    else:
        intent.primary_party_type = None

    category_from_preferences = {
        "food": "food",
        "coffee": "coffee",
        "culture": "exhibition",
        "night_view": "night",
        "citywalk": "street",
        "walking": "street",
        "shopping": "shopping",
        "family": "museum",
        "coffee": "coffee",
    }
    required_categories = list(getattr(intent, "required_categories", []) or [])
    for preference in getattr(intent, "preferences", []) or []:
        category = category_from_preferences.get(preference)
        if category and category not in required_categories:
            required_categories.append(category)
    intent.required_categories = required_categories

    intent.avoid = list(dict.fromkeys(_normalize_avoid_key(item) for item in getattr(intent, "avoid", []) or []))

    intent.soft_preferences = list(
        dict.fromkeys([*(getattr(intent, "soft_preferences", []) or []), *(getattr(intent, "preferences", []) or [])])
    )
    intent.preferred_categories = list(
        dict.fromkeys(
            [
                *(getattr(intent, "preferred_categories", []) or []),
                *(getattr(intent, "primary_categories", []) or []),
                *(getattr(intent, "secondary_categories", []) or []),
                *(getattr(intent, "required_categories", []) or []),
            ]
        )
    )
    intent.intent_tags = list(
        dict.fromkeys(
            [
                *(getattr(intent, "primary_categories", []) or []),
                *(getattr(intent, "secondary_categories", []) or []),
                *(getattr(intent, "required_categories", []) or []),
                *(getattr(intent, "preferences", []) or []),
                *(getattr(intent, "party_types", []) or []),
                *(getattr(intent, "avoid", []) or []),
                *(getattr(intent, "must_include", []) or []),
            ]
        )
    )
    intent.recognized_signals = list(
        dict.fromkeys([*(getattr(intent, "recognized_signals", []) or []), *intent.intent_tags])
    )

    constraints: list[str] = []
    if getattr(intent, "city", None):
        constraints.append(f"city:{intent.city}")
    if getattr(intent, "budget", None) is not None:
        constraints.append(f"budget:{intent.budget}")
    if getattr(intent, "start_time", None):
        constraints.append(f"start_time:{intent.start_time}")
    if getattr(intent, "end_time", None):
        constraints.append(f"end_time:{intent.end_time}")
    if getattr(intent, "start_location", None):
        constraints.append(f"start_location:{intent.start_location}")
    intent.hard_constraints = constraints
    return intent


def apply_ui_preferences(intent: ParsedIntent, preferences: List[str]) -> ParsedIntent:
    """Merge UI preference chips into the parsed intent."""

    if not preferences:
        return intent

    pref_keys = list(intent.preferences)
    avoid_keys = list(intent.avoid)

    for raw_label in preferences:
        label = str(raw_label or "").strip()
        if not label:
            continue
        key = _PREFERENCE_LABEL_TO_KEY.get(label, label)
        if key in _AVOID_LABELS:
            if key not in avoid_keys:
                avoid_keys.append(key)
            continue
        if key not in pref_keys:
            pref_keys.append(key)

    intent.preferences = pref_keys
    intent.avoid = avoid_keys
    quantity_min_counts, quantity_caps = _extract_quantity_constraints(text)
    for category, minimum in quantity_min_counts.items():
        intent.category_min_counts[category] = max(int(intent.category_min_counts.get(category, 0) or 0), minimum)
    for category, maximum in quantity_caps.items():
        current = intent.category_caps.get(category)
        if current is None:
            intent.category_caps[category] = maximum
        else:
            intent.category_caps[category] = min(int(current or maximum), maximum)

    return refresh_intent_derived_fields(intent)


def apply_modification_hints(
    intent: ParsedIntent,
    query: str,
    *,
    current_route: Any = None,
) -> ParsedIntent:
    """Apply lightweight modification hints from free-form text."""

    text = (query or "").strip()
    if not text:
        return intent

    lowered = text.lower()
    if current_route is not None:
        intent.modification_query = text
    pref_keys = list(intent.preferences)
    avoid_keys = list(intent.avoid)
    category_keys = list(intent.required_categories)

    def add_pref(key: str) -> None:
        if key not in pref_keys:
            pref_keys.append(key)

    def add_avoid(key: str) -> None:
        normalized = _normalize_avoid_key(key)
        if normalized not in avoid_keys:
            avoid_keys.append(normalized)

    def add_category(key: str) -> None:
        if key not in category_keys:
            category_keys.append(key)

    if any(token in text for token in ("太远", "别太远", "近一点", "更近")):
        add_avoid("avoid_far")
    if any(token in text for token in ("不想排队", "不要排队", "别排队", "少排队", "不排队", "排队太久", "别排太久", "不想排太久", "少排太久")):
        add_avoid("avoid_queue")
    if any(token in text for token in ("人多", "拥挤", "别太挤", "避开人多")):
        add_avoid("avoid_crowded")
    if any(token in text for token in ("不吃辣", "不要辣", "清淡", "少辣")):
        add_avoid("avoid_spicy")

    if any(token in text for token in ("轻松", "别太赶", "不要太赶", "不太赶", "慢一点", "慢慢", "松弛", "性价比", "预算友好", "不要太绕", "别太绕", "随便逛逛", "别太累", "不想太累")):
        add_pref("relaxed")
    if any(token in text for token in ("高效", "快一点", "尽快", "紧凑")):
        add_pref("efficient")
    if any(token in text for token in ("拍照", "出片", "打卡", "好看")):
        add_pref("photo")
    if any(token in text for token in ("美食", "吃饭", "吃点好的", "吃点东西", "吃点", "好吃", "小吃", "本地小吃", "本帮菜", "粤式点心", "早茶", "饮茶", "点心", "正餐", "简餐")):
        add_pref("food")
    if any(token in text for token in ("顶奢", "高端", "精致", "贵一点", "吃好点", "品质感", "仪式感", "不要便宜", "不要太便宜")):
        add_pref("premium")
        pref_keys[:] = [item for item in pref_keys if item != "value"]
    if any(token in text for token in ("文艺", "展览", "看展", "博物馆")):
        add_pref("culture")
    if any(token in text for token in ("咖啡", "咖啡店", "喝杯咖啡", "下午茶")):
        add_pref("coffee")
    if any(token in text for token in ("夜景", "夜游", "晚上逛")):
        add_pref("night_view")
    if any(token in text for token in ("本地特色", "小众", "地道", "接地气")):
        add_pref("local_feature")
    if any(token in text for token in ("购物", "商场", "逛商场", "商圈", "逛小店", "小店")):
        add_pref("shopping")
        add_category("shopping")
    if any(token in text for token in ("博物馆", "展馆", "纪念馆", "陈列馆")):
        add_category("museum")
    if any(token in text for token in ("咖啡", "咖啡店", "喝杯咖啡", "下午茶")):
        add_category("coffee")
    if any(token in text for token in ("早茶", "饮茶", "点心", "粤式点心")):
        add_category("food")
    if any(token in text for token in ("逛逛", "随便逛逛", "citywalk", "城市漫步", "老街", "小店", "玩", "游玩", "逛玩")):
        add_category("street")
    if any(token in text for token in ("大学城", "广州大学城", "小洲村", "岭南印象园", "广东科学中心")):
        if "大学城" not in intent.must_include:
            intent.must_include.append("大学城")
        add_category("street")
    if any(token in text for token in ("雨天", "下雨", "室内", "避雨")):
        add_pref("rainy_day")
        add_pref("indoor")
        if any(token in text for token in ("别太赶", "不要太赶", "不太赶", "安静", "清净", "轻松")):
            add_pref("quiet")
    if any(token in text for token in ("亲子", "带娃", "小朋友")):
        add_pref("family")
    if any(token in text for token in ("约会", "情侣")):
        add_pref("couple")
    if any(token in text for token in ("朋友", "闺蜜", "同学")):
        add_pref("friends")
    if any(token in text for token in ("一个人", "独自", "solo")):
        add_pref("solo")
    if any(token in text for token in ("citywalk", "散步", "逛逛", "溜达")):
        add_pref("citywalk")
        add_pref("walking")

    if _rejects_value_route(text):
        pref_keys = [item for item in pref_keys if item != "value"]

    intent.preferences = list(dict.fromkeys(pref_keys))
    intent.avoid = list(dict.fromkeys(_normalize_avoid_key(item) for item in avoid_keys))
    intent.required_categories = list(dict.fromkeys(category_keys))

    if any(token in text for token in ("尽快", "快一点", "高效", "速战速决", "半天内搞定")):
        intent.pace = "fast"
    elif any(token in text for token in ("别太赶", "不要太赶", "不太赶", "别太累", "不想太累", "慢一点", "慢慢", "随便逛逛", "不要太绕", "别太绕")):
        intent.pace = "slow"
    elif "室内" in text or "下雨" in text or "雨天" in text:
        intent.pace = intent.pace if intent.pace in {"fast", "normal", "slow"} else "normal"
    if any(token in text for token in ("打车", "出租", "车", "开车")):
        intent.transport_mode = "taxi"
    elif any(token in text for token in ("地铁", "metro")):
        intent.transport_mode = "metro"
    elif any(token in text for token in ("走路", "步行", "walking")):
        intent.transport_mode = "walking"

    return refresh_intent_derived_fields(intent)


# ============================================================================
# 归一化函数
# ============================================================================

def normalize_llm_intent(
    draft: Dict[str, Any],
    query: Optional[str] = None,
    explicit_city: Optional[str] = None,
) -> ParsedIntent:
    """
    归一化 LLM 解析结果

    功能：
        1. 转换数据类型
        2. 验证字段值
        3. 填充默认值
        4. 处理遗漏字段

    参数：
        draft: LLM 返回的原始字典
        query: 原始查询文本（用于补充）
        explicit_city: 显式城市

    返回：
        归一化后的 ParsedIntent
    """
    # 创建解析器
    parser = IntentParser()
    local_intent = parser.parse_intent(query or "", explicit_city)

    # 如果 LLM 返回为空，使用本地解析
    if not draft or not isinstance(draft, dict):
        return parser.parse_intent(query or "", explicit_city)

    # 归一化城市
    city = draft.get("city") or local_intent.city or explicit_city
    if city:
        for supported in SUPPORTED_CITIES:
            if supported in str(city):
                city = supported
                break
    else:
        city = local_intent.city or None

    # 归一化预算
    budget = draft.get("budget")
    if budget is not None:
        try:
            budget = float(budget)
            if budget <= 0 or budget > MAX_BUDGET:
                budget = None
        except (ValueError, TypeError):
            budget = None

    # 归一化偏好
    preferences = draft.get("preferences") or []
    if isinstance(preferences, list):
        preferences = [str(p).strip() for p in preferences if p]
    else:
        preferences = []
    preferences = list(dict.fromkeys([*preferences, *local_intent.preferences]))
    if _rejects_value_route(query or ""):
        preferences = [item for item in preferences if item != "value"]

    # 归一化避雷
    avoid = draft.get("avoid") or []
    if isinstance(avoid, list):
        avoid = [_normalize_avoid_key(str(a).strip()) for a in avoid if a]
    else:
        avoid = []
    avoid = list(dict.fromkeys([*avoid, *local_intent.avoid]))

    # 归一化类别
    categories = draft.get("required_categories") or []
    if isinstance(categories, list):
        categories = [str(c).strip() for c in categories if c]
    else:
        categories = []
    categories = list(dict.fromkeys([*categories, *local_intent.required_categories]))

    primary_categories = draft.get("primary_categories") or []
    if isinstance(primary_categories, list):
        primary_categories = [str(c).strip() for c in primary_categories if c]
    else:
        primary_categories = []

    secondary_categories = draft.get("secondary_categories") or []
    if isinstance(secondary_categories, list):
        secondary_categories = [str(c).strip() for c in secondary_categories if c]
    else:
        secondary_categories = []

    goal_summary = draft.get("goal_summary")
    if goal_summary is not None:
        goal_summary = str(goal_summary).strip() or None

    uncertain_fields = draft.get("uncertain_fields") or []
    if isinstance(uncertain_fields, list):
        uncertain_fields = [str(item).strip() for item in uncertain_fields if item]
    else:
        uncertain_fields = []

    needs_clarification = draft.get("needs_clarification")
    if isinstance(needs_clarification, str):
        needs_clarification = needs_clarification.strip().lower() in {"1", "true", "yes", "y", "on"}
    elif needs_clarification is None:
        needs_clarification = False
    else:
        needs_clarification = bool(needs_clarification)

    preferred_categories = list(dict.fromkeys([*categories, *primary_categories, *secondary_categories, *local_intent.preferred_categories]))

    semantic_scores = _coerce_semantic_scores(draft.get("semantic_scores"))
    semantic_evidence = _coerce_semantic_evidence(draft.get("semantic_evidence"))
    categories, preferences, avoid = _apply_semantic_scores_to_fields(
        categories=categories,
        preferences=preferences,
        avoid=avoid,
        scores=semantic_scores,
        query=query or "",
    )

    intent_confidence = draft.get("intent_confidence")
    try:
        intent_confidence = float(intent_confidence) if intent_confidence is not None else None
        if intent_confidence is not None:
            intent_confidence = max(0.0, min(1.0, intent_confidence / 100.0 if intent_confidence > 1.0 else intent_confidence))
    except (TypeError, ValueError):
        intent_confidence = None

    # 归一化节奏
    pace = draft.get("pace") or local_intent.pace or "normal"
    if pace not in ["fast", "normal", "slow"]:
        pace = local_intent.pace if local_intent.pace in ["fast", "normal", "slow"] else "normal"

    # 归一化交通方式
    transport = draft.get("transport_mode") or local_intent.transport_mode or "mixed"
    if transport not in ["walking", "metro", "taxi", "mixed"]:
        transport = local_intent.transport_mode if local_intent.transport_mode in ["walking", "metro", "taxi", "mixed"] else "mixed"

    category_min_counts = dict(getattr(local_intent, "category_min_counts", {}) or {})
    draft_category_min_counts = draft.get("category_min_counts") or {}
    if isinstance(draft_category_min_counts, dict):
        for key, value in draft_category_min_counts.items():
            try:
                category_min_counts[str(key)] = max(int(category_min_counts.get(str(key), 0) or 0), int(value))
            except (TypeError, ValueError):
                continue

    category_caps = dict(getattr(local_intent, "category_caps", {}) or {})
    draft_category_caps = draft.get("category_caps") or {}
    if isinstance(draft_category_caps, dict):
        for key, value in draft_category_caps.items():
            try:
                value_int = int(value)
            except (TypeError, ValueError):
                continue
            key = str(key)
            current = category_caps.get(key)
            if current is None:
                category_caps[key] = value_int
            else:
                try:
                    category_caps[key] = min(int(current), value_int)
                except (TypeError, ValueError):
                    category_caps[key] = value_int

    must_include = draft.get("must_include") or []
    if not isinstance(must_include, list):
        must_include = []
    else:
        must_include = [str(item).strip() for item in must_include if item]
    must_include = list(dict.fromkeys([*must_include, *local_intent.must_include]))

    draft_unclassified = draft.get("unclassified_clues") or []
    if isinstance(draft_unclassified, list):
        draft_unclassified = [str(item).strip() for item in draft_unclassified if item]
    else:
        draft_unclassified = []

    auto_unclassified = _extract_unclassified_clues(
        query or "",
        [*categories, *preferences, *avoid, *must_include, str(city or ""), str(draft.get("start_location") or "")],
    )
    unclassified_clues = list(dict.fromkeys([*draft_unclassified, *auto_unclassified]))

    parsed_intent = ParsedIntent(
        city=city,
        start_location=draft.get("start_location") or local_intent.start_location,
        start_time=draft.get("start_time") or local_intent.start_time,
        end_time=draft.get("end_time") or local_intent.end_time,
        budget=budget if budget is not None else local_intent.budget,
        required_categories=categories,
        preferred_categories=preferred_categories,
        primary_categories=primary_categories,
        secondary_categories=secondary_categories,
        preferences=preferences,
        party_types=list(dict.fromkeys([*(draft.get("party_types") or []), *_derive_party_types(preferences), *(getattr(local_intent, "party_types", []) or [])])),
        primary_party_type=draft.get("primary_party_type") or getattr(local_intent, "primary_party_type", None),
        avoid=avoid,
        pace=pace,
        transport_mode=transport,
        must_include=must_include,
        category_min_counts=category_min_counts,
        category_caps=category_caps,
        goal_summary=goal_summary,
        uncertain_fields=uncertain_fields,
        needs_clarification=needs_clarification,
        unclassified_clues=unclassified_clues,
        semantic_scores=semantic_scores,
        semantic_evidence=semantic_evidence,
        intent_confidence=intent_confidence,
        notes=draft.get("notes") or local_intent.notes,
        parse_source="llm+local",
        llm_payload=draft,
    )
    apply_semantic_hints(parsed_intent, query or "")
    return refresh_intent_derived_fields(parsed_intent)
