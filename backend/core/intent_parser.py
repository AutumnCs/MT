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
    "category_food": ["吃饭", "美食", "餐厅", "饭店", "午餐", "晚餐", "早餐", "小吃", "本帮菜", "粤菜", "川菜", "湘菜", "火锅", "烧烤", "素食"],
    "category_exhibition": ["展览", "博物馆", "美术馆", "画廊", "看展", "艺术展", "书店"],
    "category_night": ["夜景", "夜生活", "看夜景", "夜游", "酒吧", "清吧", "夜场"],
    "category_street": ["逛街", "购物", "商业街", "步行街", "老街", "弄堂", "小巷", "散步", "citywalk"],
    "category_park": ["公园", "户外", "绿地", "江边", "河边", "湖边", "爬山", "徒步"],
    "category_shopping": ["商场", "购物", "逛商场", "商圈", "mall"],
    "category_museum": ["博物馆", "展馆", "纪念馆", "陈列馆"],
    "category_scene": ["景点", "风景", "打卡点", "观景", "景区"],
}

_PREFERENCE_FALLBACK_KEYWORDS = {
    "prefer_couple": ["约会", "情侣", "浪漫", "二人世界", "烛光晚餐", "甜蜜"],
    "prefer_photo": ["拍照", "打卡", "出片", "好看", "上镜", "氛围感", "网红"],
    "prefer_food": ["美食", "吃饭", "吃点好的", "好吃", "探店", "简餐", "咖啡", "下午茶"],
    "prefer_culture": ["文化", "历史", "古迹", "博物馆", "人文", "艺术", "看展"],
    "prefer_local_feature": ["本地特色", "接地气", "本地味", "烟火气", "老字号", "地道", "不太商业"],
    "prefer_night_view": ["夜景", "夜游", "看夜景", "灯光秀", "夜生活"],
    "prefer_quiet": ["安静", "清净", "轻松", "松弛", "不吵", "人少", "慢慢逛"],
    "prefer_rainy_day": ["雨天", "下雨", "避雨", "室内优先", "室内", "躲雨"],
    "prefer_walking": ["步行", "散步", "citywalk", "逛逛", "溜达", "走路"],
    "prefer_family": ["亲子", "带娃", "小朋友", "孩子", "家庭", "一家人"],
    "prefer_friends": ["朋友", "闺蜜", "同学", "聚会", "朋友局"],
    "prefer_solo": ["一个人", "独自", "solo", "独行"],
    "prefer_value": ["性价比", "划算", "实惠", "便宜", "预算友好", "省钱"],
    "prefer_indoor": ["室内", "室内优先", "避雨", "不淋雨", "馆内", "店内"],
    "prefer_outdoor": ["室外", "户外", "露天", "外面", "室外优先"],
    "prefer_citywalk": ["citywalk", "city walk", "城市漫步", "慢逛", "闲逛", "逛逛"],
    "prefer_efficient": ["高效", "尽快", "快一点", "省时间", "效率", "不折腾"],
    "prefer_compact": ["紧凑", "少绕路", "少转场", "不绕", "顺路", "串起来"],
}

_AVOID_FALLBACK_KEYWORDS = {
    "avoid_spicy": ["不要辣", "不吃辣", "少辣", "清淡"],
    "avoid_far": ["别太远", "不要太远", "近一点", "更近", "不要跑太远"],
    "avoid_queue": ["不想排队", "不要排队", "少排队", "排队太久"],
    "avoid_crowded": ["人多", "拥挤", "别太挤", "避开人多", "别太拥挤"],
}


def _keywords_with_fallback(lexicon_key: str, fallback_map: dict[str, list[str]]) -> list[str]:
    keywords = list(INTENT_LEXICON.get(lexicon_key, []) or [])
    if keywords:
        return keywords
    return list(fallback_map.get(lexicon_key, []))


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

        # 11. 保留未能稳定归类的线索，方便后续扩词典与回归
        unclassified_clues = _extract_unclassified_clues(
            query,
            [*categories, *preferences, *avoid, *must_include, city or "", start_location or ""],
        )

        return ParsedIntent(
            city=city,
            start_location=start_location,
            start_time=start_time,
            end_time=end_time,
            budget=budget,
            required_categories=categories,
            preferences=preferences,
            avoid=avoid,
            pace=pace,
            transport_mode=transport_mode,
            must_include=must_include,
            unclassified_clues=unclassified_clues,
            notes=None,
        )

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

        # 解析开始时间
        time_patterns = [
            # 下午2点 -> 14:00
            (r"下午(\d{1,2})[点时]", lambda m: f"{int(m.group(1)) + 12:02d}:00"),
            # 晚上7点 -> 19:00
            (r"晚上(\d{1,2})[点时]", lambda m: f"{int(m.group(1)) + 12:02d}:00"),
            # 早上9点 -> 09:00
            (r"早上(\d{1,2})[点时]", lambda m: f"{int(m.group(1)):02d}:00"),
            # 中午12点 -> 12:00
            (r"中午(\d{1,2})[点时]", lambda m: f"{int(m.group(1)):02d}:00"),
            # HH:MM 格式
            (r"(\d{1,2}):(\d{2})", lambda m: f"{int(m.group(1)):02d}:{m.group(2)}"),
            # X点Y分
            (r"(\d{1,2})点(\d{1,2})分", lambda m: f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"),
        ]

        for pattern, extractor in time_patterns:
            match = re.search(pattern, query)
            if match:
                start_time = extractor(match)
                break

        # 解析结束时间（如果有明确说明）
        # 例如："晚上9点前结束"
        end_pattern = r"(晚上|下午|早上|中午)?(\d{1,2})[点时](?:前|以前|内|结束)?"
        end_match = re.search(end_pattern, query)
        if end_match:
            hour = int(end_match.group(2))
            if end_match.group(1) in ["晚上", "下午"] and hour < 12:
                hour += 12
            end_time = f"{hour:02d}:00"

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
            r"(?:预算|花费|花销|消费|预算为|预算是)?\s*(\d+(?:\.\d+)?)\s*(?:元|块钱|块|人民币)?",
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
            "prefer_friends": "friends",
            "prefer_solo": "solo",
            "prefer_value": "value",
            "prefer_indoor": "indoor",
            "prefer_outdoor": "outdoor",
            "prefer_citywalk": "citywalk",
            "prefer_efficient": "efficient",
            "prefer_compact": "compact",
        }

        for lexicon_key, preference in preference_map.items():
            keywords = _keywords_with_fallback(lexicon_key, _PREFERENCE_FALLBACK_KEYWORDS)
            for keyword in keywords:
                if keyword in query:
                    if preference not in preferences:
                        preferences.append(preference)
                    break

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
            "avoid_spicy": "spicy",
            "avoid_far": "far",
            "avoid_queue": "queue",
            "avoid_crowded": "crowded",
        }

        for lexicon_key, avoid_item in avoid_map.items():
            keywords = _keywords_with_fallback(lexicon_key, _AVOID_FALLBACK_KEYWORDS)
            for keyword in keywords:
                if keyword in query:
                    if avoid_item not in avoid_list:
                        avoid_list.append(avoid_item)
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
        if key in getattr(intent, "avoid", []):
            setattr(intent, field_name, True)

    intent.soft_preferences = list(
        dict.fromkeys([*(getattr(intent, "soft_preferences", []) or []), *(getattr(intent, "preferences", []) or [])])
    )
    intent.preferred_categories = list(
        dict.fromkeys(
            [*(getattr(intent, "preferred_categories", []) or []), *(getattr(intent, "required_categories", []) or [])]
        )
    )
    intent.intent_tags = list(
        dict.fromkeys(
            [
                *(getattr(intent, "required_categories", []) or []),
                *(getattr(intent, "preferences", []) or []),
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
    pref_keys = list(intent.preferences)
    avoid_keys = list(intent.avoid)

    def add_pref(key: str) -> None:
        if key not in pref_keys:
            pref_keys.append(key)

    def add_avoid(key: str) -> None:
        if key not in avoid_keys:
            avoid_keys.append(key)

    if any(token in text for token in ("太远", "别太远", "近一点", "更近")):
        add_avoid("avoid_far")
    if any(token in text for token in ("不想排队", "不要排队", "少排队", "排队太久")):
        add_avoid("avoid_queue")
    if any(token in text for token in ("人多", "拥挤", "别太挤", "避开人多")):
        add_avoid("avoid_crowded")
    if any(token in text for token in ("不吃辣", "不要辣", "清淡", "少辣")):
        add_avoid("avoid_spicy")

    if any(token in text for token in ("轻松", "别太赶", "慢一点", "慢慢", "松弛")):
        add_pref("relaxed")
    if any(token in text for token in ("高效", "快一点", "尽快", "紧凑")):
        add_pref("efficient")
    if any(token in text for token in ("拍照", "出片", "打卡", "好看")):
        add_pref("photo")
    if any(token in text for token in ("美食", "吃饭", "吃点好的", "好吃")):
        add_pref("food")
    if any(token in text for token in ("文艺", "展览", "看展", "博物馆")):
        add_pref("culture")
    if any(token in text for token in ("夜景", "夜游", "晚上逛")):
        add_pref("night_view")
    if any(token in text for token in ("本地特色", "小众", "地道", "接地气")):
        add_pref("local_feature")
    if any(token in text for token in ("雨天", "下雨", "室内", "避雨")):
        add_pref("rainy_day")
        add_pref("indoor")
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

    intent.preferences = list(dict.fromkeys(pref_keys))
    intent.avoid = list(dict.fromkeys(avoid_keys))

    if "室内" in text or "下雨" in text or "雨天" in text:
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

    # 如果 LLM 返回为空，使用本地解析
    if not draft or not isinstance(draft, dict):
        return parser.parse_intent(query or "", explicit_city)

    # 归一化城市
    city = draft.get("city") or explicit_city
    if city:
        for supported in SUPPORTED_CITIES:
            if supported in str(city):
                city = supported
                break
    else:
        city = None

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

    # 归一化避雷
    avoid = draft.get("avoid") or []
    if isinstance(avoid, list):
        avoid = [str(a).strip() for a in avoid if a]
    else:
        avoid = []

    # 归一化类别
    categories = draft.get("required_categories") or []
    if isinstance(categories, list):
        categories = [str(c).strip() for c in categories if c]
    else:
        categories = []

    # 归一化节奏
    pace = draft.get("pace") or "normal"
    if pace not in ["fast", "normal", "slow"]:
        pace = "normal"

    # 归一化交通方式
    transport = draft.get("transport_mode") or "mixed"
    if transport not in ["walking", "metro", "taxi", "mixed"]:
        transport = "mixed"

    must_include = draft.get("must_include") or []
    if not isinstance(must_include, list):
        must_include = []
    else:
        must_include = [str(item).strip() for item in must_include if item]

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

    return ParsedIntent(
        city=city,
        start_location=draft.get("start_location") or parser._extract_start_location(query or ""),
        start_time=draft.get("start_time"),
        end_time=draft.get("end_time"),
        budget=budget,
        required_categories=categories,
        preferences=preferences,
        avoid=avoid,
        pace=pace,
        transport_mode=transport,
        must_include=must_include,
        unclassified_clues=unclassified_clues,
        notes=draft.get("notes"),
    )
