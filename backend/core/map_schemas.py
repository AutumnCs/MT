"""
地图服务数据模型模块
====================

功能说明：
    本模块定义了地图服务相关的数据模型，用于 API 请求/响应验证。

支持的地图能力：
    - 地理编码（地址 → 坐标）
    - 逆地理编码（坐标 → 地址）
    - POI 搜索
    - 路线规划
    - 地图预览

地图服务提供商：
    - 高德地图（AMap）- 当前默认
    - 未来可扩展支持其他地图服务

Author: MeituanAgent Team
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================================
# 地图状态与配置模型
# ============================================================================

class MapStatusResponse(BaseModel):
    """
    地图服务状态响应

    说明：
        返回当前地图服务的配置和可用性状态

    字段说明：
        - provider: 地图服务提供商（默认：高德地图）
        - enabled: 服务是否启用
        - has_key: 是否已配置 API Key
        - base_url: API 基础地址
        - supported_modes: 支持的出行方式
        - note: 额外说明
    """

    provider: str = "amap"  # 地图提供商
    enabled: bool = False  # 服务是否启用
    has_key: bool = False  # 是否已配置 API Key
    base_url: str = "https://restapi.amap.com"  # 高德地图 API 地址
    supported_modes: List[str] = Field(
        default_factory=lambda: ["walking", "driving"]
    )  # 支持的出行方式：walking=步行, driving=驾车
    note: Optional[str] = None  # 额外说明


# ============================================================================
# 地理编码相关模型
# ============================================================================

class MapGeocodeRequest(BaseModel):
    """
    地理编码请求

    功能：
        将文字地址转换为地理坐标

    字段说明：
        - address: 要转换的地址（必填）
        - city: 所在城市（可选，用于提高精度）
    """

    address: str  # 地址文本
    city: Optional[str] = None  # 城市名称，用于提高匹配精度


class MapReverseGeocodeRequest(BaseModel):
    """
    逆地理编码请求

    功能：
        将地理坐标转换为文字地址

    字段说明：
        - longitude: 经度
        - latitude: 纬度
    """

    longitude: float  # 经度
    latitude: float  # 纬度


# ============================================================================
# POI 搜索相关模型
# ============================================================================

class MapPoiSearchRequest(BaseModel):
    """
    POI 搜索请求

    功能：
        根据关键词搜索附近的兴趣点

    字段说明：
        - keyword: 搜索关键词
        - city: 搜索城市（可选）
        - location: 中心点坐标，格式 "longitude,latitude"（可选）
        - radius: 搜索半径，单位米（默认1000米）
        - types: POI 类型过滤（可选）
        - limit: 返回结果数量限制（默认10）
    """

    keyword: str  # 搜索关键词
    city: Optional[str] = None  # 搜索城市
    location: Optional[str] = None  # 中心点坐标，格式 "经度,纬度"
    radius: int = 1000  # 搜索半径（米）
    types: Optional[str] = None  # POI 类型编码
    limit: int = 10  # 返回结果数量限制


# ============================================================================
# 路线规划相关模型
# ============================================================================

class MapRouteRequest(BaseModel):
    """
    路线规划请求

    功能：
        计算两个或多个点之间的路线

    字段说明：
        - origin_longitude: 起点经度
        - origin_latitude: 起点纬度
        - destination_longitude: 终点经度
        - destination_latitude: 终点纬度
        - mode: 出行方式（walking/driving）
        - strategy: 路线策略（可选，如：速度优先/费用优先）
        - waypoints: 途经点列表（可选）
    """

    origin_longitude: float  # 起点经度
    origin_latitude: float  # 起点纬度
    destination_longitude: float  # 终点经度
    destination_latitude: float  # 终点纬度
    mode: str = "walking"  # 出行方式：walking=步行, driving=驾车
    strategy: Optional[str] = None  # 路线策略
    waypoints: List[str] = Field(default_factory=list)  # 途经点列表


# ============================================================================
# 地图预览相关模型
# ============================================================================

class MapPreviewRequest(BaseModel):
    """
    地图预览请求

    功能：
        生成包含多个点的路线预览

    字段说明：
        - points: 路线点列表，每个点包含 longitude, latitude 等信息
        - mode: 出行方式
        - title: 预览标题（可选）
    """

    points: List[Dict[str, Any]] = Field(
        default_factory=list
    )  # 路线点列表，格式：[{"longitude": 121.0, "latitude": 31.0, "name": "景点A"}, ...]
    mode: str = "walking"  # 出行方式
    title: Optional[str] = None  # 预览标题


# ============================================================================
# API 响应模型
# ============================================================================

class RouteInfo(BaseModel):
    """Simple route estimate used by the map service fallback path."""

    distance_km: float = 0.0
    duration_min: int = 0
    steps: List[Dict[str, Any]] = Field(default_factory=list)


class MapApiResponse(BaseModel):
    """
    地图 API 通用响应

    说明：
        所有地图 API 调用的统一响应格式

    字段说明：
        - provider: 地图提供商
        - enabled: 服务是否启用
        - success: 请求是否成功
        - message: 错误信息（失败时）
        - data: 响应数据
    """

    provider: str = "amap"  # 地图提供商
    enabled: bool = False  # 服务是否启用
    success: bool = False  # 请求是否成功
    message: Optional[str] = None  # 错误信息
    data: Dict[str, Any] = Field(default_factory=dict)  # 响应数据
