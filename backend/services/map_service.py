"""
地图服务模块
=============

本模块负责与高德地图API交互，提供路线规划、地理编码等功能。

主要功能：
- 调用高德地图步行路线API
- 计算POI之间的距离和时间
- 提供优雅的降级方案（当API不可用时）
- 缓存常用路线以提高性能

作者：美团智能路线规划团队
"""

import os
import time
from functools import lru_cache

import httpx
from core.map_schemas import RouteInfo
from core.schemas import POI


# 获取高德地图 API Key，兼容旧变量名与当前文档名
AMAP_KEY = os.getenv("AMAP_KEY") or os.getenv("AMAP_WEB_KEY", "")
# 高德地图 API 基础地址
AMAP_BASE_URL = os.getenv("AMAP_WEB_BASE_URL", "https://restapi.amap.com")
# 超时时间
AMAP_TIMEOUT_SECONDS = float(os.getenv("AMAP_WEB_TIMEOUT_SECONDS", "10"))
# 高德地图步行路线API端点
AMAP_WALKING_URL = "https://restapi.amap.com/v3/direction/walking"


def _parse_amap_response(raw: dict) -> RouteInfo:
    """
    解析高德地图API响应

    参数：
        raw: 高德地图API返回的原始JSON

    返回：
        RouteInfo: 解析后的路线信息对象
    """
    try:
        route = raw.get("route", {})
        paths = route.get("paths", [])
        if not paths:
            return RouteInfo(distance_km=0.0, duration_min=0, steps=[])
        path = paths[0]
        distance = int(path.get("distance", 0))
        duration = int(path.get("duration", 0))
        return RouteInfo(
            distance_km=round(distance / 1000.0, 2),
            duration_min=round(duration / 60.0),
            steps=[],
        )
    except Exception:
        return RouteInfo(distance_km=0.0, duration_min=0, steps=[])


@lru_cache(maxsize=200)
def get_route(origin: POI, destination: POI) -> RouteInfo:
    """
    获取两个POI之间的步行路线

    流程：
        1. 检查是否有API Key
        2. 调用高德地图API
        3. 解析响应
        4. 如果失败，返回降级估算

    参数：
        origin: 起点POI
        destination: 终点POI

    返回：
        RouteInfo: 路线信息
    """
    if not AMAP_KEY:
        return _fallback_estimate(origin, destination)

    origin_loc = f"{origin.lng},{origin.lat}"
    dest_loc = f"{destination.lng},{destination.lat}"

    try:
        # 调用高德地图API
        resp = httpx.get(
            AMAP_WALKING_URL.replace("https://restapi.amap.com", AMAP_BASE_URL.rstrip("/")),
            params={
                "key": AMAP_KEY,
                "origin": origin_loc,
                "destination": dest_loc,
            },
            timeout=AMAP_TIMEOUT_SECONDS,
        )
        data = resp.json()
        return _parse_amap_response(data)
    except Exception:
        return _fallback_estimate(origin, destination)


def _fallback_estimate(origin: POI, destination: POI) -> RouteInfo:
    """
    降级方案：使用Haversine公式估算距离和时间

    当高德地图API不可用时使用

    参数：
        origin: 起点POI
        destination: 终点POI

    返回：
        RouteInfo: 估算的路线信息
    """
    # 导入需要的函数，避免循环导入
    import math

    def haversine(lat1, lon1, lat2, lon2):
        R = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = (math.sin(delta_phi / 2) ** 2) + (
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    dist_km = haversine(origin.lat, origin.lng, destination.lat, destination.lng)
    # 按每公里12分钟估算步行时间
    duration_min = int(round(dist_km * 12))
    return RouteInfo(distance_km=round(dist_km, 2), duration_min=duration_min, steps=[])
