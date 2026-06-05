"""
数据模型定义模块
================

功能说明：
    本模块定义了系统的核心数据模型，使用 Pydantic 进行数据验证和序列化。

模型分类：
    - 基础数据模型：POI（兴趣点）、RouteStop（路线站点）
    - 请求模型：RouteRequest、IntentModification
    - 响应模型：RouteResponse、RoutePlan
    - 内部模型：ParsedIntent、IntentDraft

使用场景：
    - FastAPI 请求/响应验证
    - 数据序列化与反序列化
    - 内部模块间的数据传递

Author: MeituanAgent Team
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict

from core.contracts import RouteDiagnostics


# ============================================================================
# 枚举定义
# ============================================================================

class RouteStrategy(str, Enum):
    """
    路线规划策略枚举

    说明：
        定义不同的路线规划策略，影响路线生成的方式

    枚举值：
        - balanced: 综合平衡策略
        - preference_focused: 偏好优先策略
        - compact: 紧凑路线策略
    """

    BALANCED = "balanced"  # 综合平衡策略
    PREFERENCE_FOCUSED = "preference_focused"  # 偏好优先策略
    COMPACT = "compact"  # 紧凑路线策略


class RoutePace(str, Enum):
    """
    路线节奏枚举

    说明：
        定义用户的活动节奏偏好

    枚举值：
        - fast: 快节奏（速战速决）
        - normal: 正常节奏
        - slow: 慢节奏（休闲放松）
    """

    FAST = "fast"  # 快节奏
    NORMAL = "normal"  # 正常节奏
    SLOW = "slow"  # 慢节奏


# ============================================================================
# 偏好词典
# ============================================================================

# 定义偏好关键词，用于意图解析和验证
PREFERENCE_KEYWORDS: Dict[str, List[str]] = {
    "couple": ["约会", "情侣", "浪漫", "二人世界"],
    "photo": ["拍照", "打卡", "出片", "网红"],
    "food": ["美食", "吃货", "探店", "好吃的"],
    "culture": ["文化", "历史", "古迹", "人文"],
    "local_feature": ["本地特色", "小众", "地道", "特色"],
    "night_view": ["夜景", "看夜景", "夜游"],
    "quiet": ["安静", "清净", "放松", "休闲"],
    "rainy_day": ["雨天", "下雨", "室内"],
    "walking": ["走路", "步行", "citywalk"],
}


# ============================================================================
# 基础数据模型
# ============================================================================

class POI(BaseModel):
    model_config = ConfigDict(extra="allow")

    """
    兴趣点（Point of Interest）数据模型

    说明：
        表示一个可供访问的地点，包含位置、类别、评价等多维度信息

    字段说明：
        - id: 唯一标识符
        - name: 地点名称
        - category: 主类别（coffee/food/exhibition/night/street/park）
        - sub_category: 子类别
        - description: 地点描述
        - address: 地址
        - city: 所在城市
        - district: 所在行政区
        - longitude/latitude: 经纬度坐标
        - rating: 综合评分（0-5）
        - price_level: 价格等级（1-5）
        - budget_per_person: 人均消费
        - visit_duration: 建议游览时长（分钟）
        - business_hours: 营业时间
        - photo_score: 拍照指数（0-10）
        - date_score: 约会指数（0-10）
        - food_score: 美食指数（0-10）
        - culture_score: 文化指数（0-10）
        - local_feature_score: 本地特色指数（0-10）
        - rainy_day_score: 雨天适配指数（0-10）
        - indoor_outdoor: 室内/室外标识
        - crowd_level: 人流等级（low/medium/high）
        - queue_level: 排队等级（low/medium/high）
    """

    id: str  # 唯一标识符
    name: str  # 地点名称
    category: str  # 主类别
    sub_category: Optional[str] = None  # 子类别
    description: Optional[str] = None  # 地点描述
    address: Optional[str] = None  # 地址
    business_area: Optional[str] = None  # 商圈
    provider: str = "manual"  # 数据来源，默认本地手工/聚合
    provider_poi_id: Optional[str] = None  # 外部平台 POI ID，如高德 POI ID
    adcode: Optional[str] = None  # 行政区编码，便于和地图平台对齐
    source_updated_at: Optional[str] = None  # 数据源最后更新时间
    geocoded_confidence: float = 0.0  # 地理编码置信度，0~1
    tags: List[str] = Field(default_factory=list)  # 标签
    suitable_for: List[str] = Field(default_factory=list)  # 适合人群
    review_keywords: List[str] = Field(default_factory=list)  # 评论关键词
    positive_reviews: List[str] = Field(default_factory=list)  # 正面评论
    negative_reviews: List[str] = Field(default_factory=list)  # 负面评论
    review_signals: Dict[str, float] = Field(default_factory=dict)  # 评论信号
    best_visit_periods: List[str] = Field(default_factory=list)  # 最佳访问时段
    city: str = "上海"  # 所在城市
    district: Optional[str] = None  # 所在行政区
    longitude: float = 0.0  # 经度
    latitude: float = 0.0  # 纬度
    rating: float = 4.0  # 评分（0-5）
    price: float = 0.0  # 价格/人均消费（元）
    price_level: int = 2  # 价格等级（1-5）
    budget_per_person: float = 50.0  # 人均消费（元）
    visit_duration: int = 60  # 建议游览时长（分钟）
    business_hours: Optional[str] = None  # 营业时间
    photo_score: float = 5.0  # 拍照指数（0-10）
    date_score: float = 5.0  # 约会指数（0-10）
    food_score: float = 5.0  # 美食指数（0-10）
    culture_score: float = 5.0  # 文化指数（0-10）
    local_feature_score: float = 5.0  # 本地特色指数（0-10）
    rainy_day_score: float = 5.0  # 雨天适配指数（0-10）
    indoor_outdoor: str = "outdoor"  # 室内/室外
    crowd_level: str = "medium"  # 人流等级（low/medium/high）
    queue_level: int = 3  # 排队等级（1-5，越高越容易排队）

    @property
    def lat(self) -> float:
        return self.latitude

    @property
    def lng(self) -> float:
        return self.longitude

    def category_label(self) -> str:
        """
        获取类别的中文标签

        返回：
            类别对应的中文名称
        """
        labels = {
            "coffee": "咖啡茶饮",
            "food": "餐饮美食",
            "exhibition": "展览场馆",
            "night": "夜景地标",
            "street": "街区漫步",
            "park": "公园绿地",
        }
        return labels.get(self.category, self.category)


class RouteStop(BaseModel):
    model_config = ConfigDict(extra="allow")

    """
    路线站点数据模型

    说明：
        表示路线中的一个站点，包含 POI 信息和到达/离开时间

    字段说明：
        - poi: 关联的兴趣点
        - arrival_time: 预计到达时间
        - departure_time: 预计离开时间
        - stay_duration: 实际停留时长（分钟）
        - transport_to_next: 到下一站的交通信息
        - stop_reason: 选择该站点的理由
    """

    poi: POI  # 关联的兴趣点
    arrival_time: Optional[str] = None  # 预计到达时间
    departure_time: Optional[str] = None  # 预计离开时间
    stay_duration: int = 60  # 实际停留时长（分钟）
    transport_to_next: Optional[Dict[str, Any]] = None  # 到下一站的交通信息
    stop_reason: Optional[str] = None  # 选择该站点的理由


# ============================================================================
# 请求模型
# ============================================================================

class RouteRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    """
    路线生成请求

    说明：
        用户发起路线生成请求时的数据格式

    字段说明：
        - query: 用户的自然语言需求
        - preferences: 额外偏好标签列表
        - city: 显式指定的城市（可选，前端选择优先）
    """

    query: str  # 用户需求文本
    preferences: Optional[List[str]] = None  # 额外偏好
    city: Optional[str] = None  # 显式城市


class IntentModification(BaseModel):
    model_config = ConfigDict(extra="allow")

    """
    意图修改请求

    说明：
        用户对已有路线进行修改时的数据格式

    字段说明：
        - modify_query: 修改要求文本
        - base_route: 原路线信息（用于上下文）
    """

    modify_query: str  # 修改要求
    base_route: Optional[Dict[str, Any]] = None  # 原路线


# ============================================================================
# 响应模型
# ============================================================================

class RoutePlan(BaseModel):
    model_config = ConfigDict(extra="allow")

    """
    单条路线方案

    说明：
        表示一条完整的路线，包含多个站点和统计信息

    字段说明：
        - strategy: 规划策略类型
        - stops: 路线站点列表
        - total_duration: 总时长（分钟）
        - total_cost: 总花费（元）
            - total_distance: 总距离（公里）
            - route_explanation: 路线说明
            - risk_alerts: 风险提示列表
    """

    strategy: str = "balanced"  # 规划策略
    stops: List[RouteStop] = Field(default_factory=list)  # 路线站点
    total_duration: int = 0  # 总时长（分钟）
    total_cost: float = 0.0  # 总花费（元）
    total_distance: float = 0.0  # 总距离（公里）
    route_explanation: Optional[str] = None  # 路线说明
    risk_alerts: List[str] = Field(default_factory=list)  # 风险提示


class RouteResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    """
    路线生成响应

    说明：
        路线生成 API 的最终响应格式

    字段说明：
        - request_id: 请求唯一标识
        - title: 路线标题
        - summary: 路线摘要
        - city: 路线所在城市
        - strategy: 使用的规划策略
        - generated_at: 生成时间
        - plans: 候选路线方案列表
        - intent_summary: 意图摘要
        - diagnostics: 路线诊断信息
    """

    request_id: Optional[str] = None  # 请求标识
    title: str = "城市漫游"  # 路线标题
    summary: Optional[str] = None  # 路线摘要
    city: str = "上海"  # 城市
    strategy: str = "balanced"  # 策略
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())  # 生成时间
    plans: List[RoutePlan] = Field(default_factory=list)  # 路线方案
    intent_summary: Optional[Dict[str, Any]] = None  # 意图摘要
    diagnostics: Optional[RouteDiagnostics] = None  # 路线诊断信息
    clarification_needed: bool = False  # 是否需要继续澄清
    clarification_question: Optional[str] = None  # 澄清问题
    clarification_options: List[str] = Field(default_factory=list)  # 澄清选项
    clarification_reason: Optional[str] = None  # 澄清原因

    @property
    def main_stops(self) -> List[Any]:
        extra = getattr(self, "model_extra", None) or {}
        return list(extra.get("main_stops") or extra.get("stops") or [])

    @property
    def poi_count(self) -> int:
        return len(self.main_stops)

    @property
    def total_cost(self) -> float:
        extra = getattr(self, "model_extra", None) or {}
        stats = extra.get("stats") or {}
        if isinstance(stats, dict):
            for key in ("total_cost", "cost"):
                if key in stats:
                    try:
                        return float(stats[key])
                    except (TypeError, ValueError):
                        pass
        total = 0.0
        for stop in self.main_stops:
            poi = getattr(stop, "poi", None)
            if poi is None and isinstance(stop, dict):
                poi = stop.get("poi")
            total += float(getattr(poi, "price", 0.0) or 0.0)
        return total

    @property
    def total_duration(self) -> int:
        extra = getattr(self, "model_extra", None) or {}
        stats = extra.get("stats") or {}
        if isinstance(stats, dict):
            for key in ("total_duration", "total_visit_min"):
                if key in stats:
                    try:
                        return int(stats[key])
                    except (TypeError, ValueError):
                        pass
        return int(sum(float(getattr(stop.poi, "visit_duration", 0) or 0) for stop in self.main_stops))

    @property
    def total_distance(self) -> float:
        extra = getattr(self, "model_extra", None) or {}
        stats = extra.get("stats") or {}
        if isinstance(stats, dict):
            for key in ("total_distance", "total_km"):
                if key in stats:
                    try:
                        return float(stats[key])
                    except (TypeError, ValueError):
                        pass
        return 0.0

    @property
    def covered_types(self) -> List[str]:
        extra = getattr(self, "model_extra", None) or {}
        value = extra.get("covered_types")
        if isinstance(value, list):
            return [str(item) for item in value if item]
        return []

    @property
    def route_explanation(self) -> str:
        return str(self.summary or "")



# ============================================================================
# 内部模型
# ============================================================================

class ParsedIntent(BaseModel):
    model_config = ConfigDict(extra="allow")

    """
    解析后的用户意图

    说明：
        意图解析器的输出格式，包含结构化的用户需求

    字段说明：
        - city: 目标城市
        - start_location: 起点位置
        - start_time: 开始时间
        - end_time: 结束时间
        - budget: 预算
        - required_categories: 必要类别列表
        - preferences: 偏好列表
        - avoid: 避雷列表
        - pace: 活动节奏
        - transport_mode: 交通方式
        - must_include: 必须包含的项目
        - notes: 补充说明
    """

    city: Optional[str] = None  # 城市
    start_location: Optional[str] = None  # 起点
    start_time: Optional[str] = None  # 开始时间
    end_time: Optional[str] = None  # 结束时间
    budget: Optional[float] = None  # 预算
    required_categories: List[str] = Field(default_factory=list)  # 必要类别
    preferred_categories: List[str] = Field(default_factory=list)  # 兼容旧字段名
    preferences: List[str] = Field(default_factory=list)  # 偏好
    avoid: List[str] = Field(default_factory=list)  # 避雷
    pace: str = "normal"  # 节奏
    transport_mode: str = "mixed"  # 交通方式
    must_include: List[str] = Field(default_factory=list)  # 必须包含
    notes: Optional[str] = None  # 补充说明

    # 向后兼容：现有打分/筛选逻辑仍然依赖这些布尔字段
    prefer_couple: bool = False
    prefer_photo: bool = False
    prefer_food: bool = False
    prefer_culture: bool = False
    prefer_local_feature: bool = False
    prefer_night_view: bool = False
    prefer_quiet: bool = False
    prefer_rainy_day: bool = False
    prefer_walking: bool = False
    prefer_family: bool = False
    prefer_friends: bool = False
    prefer_solo: bool = False
    prefer_value: bool = False
    prefer_indoor: bool = False
    prefer_outdoor: bool = False
    prefer_citywalk: bool = False
    prefer_efficient: bool = False
    prefer_compact: bool = False
    avoid_spicy: bool = False
    avoid_far: bool = False
    avoid_queue: bool = False
    avoid_crowded: bool = False
    intent_tags: List[str] = Field(default_factory=list)
    soft_preferences: List[str] = Field(default_factory=list)
    recognized_signals: List[str] = Field(default_factory=list)
    unclassified_clues: List[str] = Field(default_factory=list)
    hard_constraints: List[str] = Field(default_factory=list)
    parse_source: str = "local"
    current_route: Optional[Any] = None

    def model_post_init(self, __context: Any) -> None:
        """Keep legacy boolean flags in sync with the list-based schema."""

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

        for key, field_name in preference_flags.items():
            if key in self.preferences:
                setattr(self, field_name, True)

        for key, field_name in avoid_flags.items():
            if key in self.avoid:
                setattr(self, field_name, True)

        if not self.soft_preferences:
            self.soft_preferences = list(self.preferences)

        if not self.preferred_categories:
            self.preferred_categories = list(self.required_categories)

        if not self.intent_tags:
            self.intent_tags = list(
                dict.fromkeys(
                    [*self.required_categories, *self.preferences, *self.avoid, *self.must_include]
                )
            )

        if not self.recognized_signals:
            self.recognized_signals = list(self.intent_tags)

        if not self.hard_constraints:
            constraints: list[str] = []
            if self.city:
                constraints.append(f"city:{self.city}")
            if self.budget is not None:
                constraints.append(f"budget:{self.budget}")
            if self.start_time:
                constraints.append(f"start_time:{self.start_time}")
            if self.end_time:
                constraints.append(f"end_time:{self.end_time}")
            if self.start_location:
                constraints.append(f"start_location:{self.start_location}")
            self.hard_constraints = constraints

    @property
    def available_time(self) -> int:
        """Return the usable planning window in minutes."""

        def _to_minutes(value: Optional[str]) -> Optional[int]:
            if not value:
                return None
            text = str(value).strip()
            if not text:
                return None
            import re

            match = re.search(r"(\d{1,2}):(\d{2})", text)
            if match:
                return int(match.group(1)) * 60 + int(match.group(2))
            match = re.search(r"(\d{1,2})", text)
            if not match:
                return None
            hour = int(match.group(1))
            if any(token in text for token in ("下午", "晚上", "中午")) and hour < 12:
                hour += 12
            return hour * 60

        start = _to_minutes(self.start_time)
        end = _to_minutes(self.end_time)
        if start is None and end is None:
            return 8 * 60
        if start is None:
            return max(120, int(end or (8 * 60)))
        if end is None:
            return 8 * 60
        if end <= start:
            end += 24 * 60
        return max(120, end - start)

    @property
    def budget_max(self) -> Optional[float]:
        return self.budget

    @property
    def avoid_categories(self) -> List[str]:
        return [item for item in self.avoid if item in {"food", "coffee", "museum", "exhibition", "scene", "street", "park", "night", "shopping"}]


class IntentDraft(BaseModel):
    model_config = ConfigDict(extra="allow")

    """
    LLM 意图解析的中间结果

    说明：
        LLM 直接输出的原始解析结果，在使用前需要经过归一化处理

    字段说明：
        - city: 城市
        - start_location: 起点
        - start_time: 开始时间
        - end_time: 结束时间
        - budget: 预算
        - required_categories: 必要类别
        - preferences: 偏好
        - avoid: 避雷
        - pace: 节奏
        - transport_mode: 交通方式
        - must_include: 必须包含
        - notes: 补充说明
        - raw_response: LLM 原始响应（用于调试）
    """

    city: Optional[str] = None
    start_location: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    budget: Optional[Any] = None
    required_categories: List[str] = Field(default_factory=list)
    preferences: List[str] = Field(default_factory=list)
    avoid: List[str] = Field(default_factory=list)
    pace: Optional[str] = None
    transport_mode: Optional[str] = None
    must_include: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    raw_response: Optional[str] = None  # 原始响应


# 向后兼容：主流程里仍然引用这个旧名称
LLMIntentDraft = IntentDraft
