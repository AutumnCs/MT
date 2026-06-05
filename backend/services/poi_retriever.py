"""
POI检索服务模块
================

本模块负责从本地数据文件加载POI（兴趣点）并进行初步筛选。

主要功能：
- 从JSON文件加载POI数据
- 根据用户意图筛选城市和类别
- 返回POI对象列表

作者：美团智能路线规划团队
"""

import json
from pathlib import Path

from core.schemas import POI, ParsedIntent


# 确定POI数据文件的绝对路径
# 获取当前文件所在目录，向上两级找到backend目录，再找pois.json
POI_FILE = Path(__file__).resolve().parents[1] / "pois.json"


def load_pois() -> list:
    """
    从本地文件加载原始POI数据

    返回：
        list: JSON格式的POI原始数据列表
    """
    with POI_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def retrieve_pois(intent: ParsedIntent) -> list[POI]:
    """
    根据用户意图检索并筛选POI

    筛选规则：
        1. 优先按用户指定的城市过滤
        2. 如果有必要类别，进一步按类别筛选

    参数：
        intent: ParsedIntent，解析后的用户意图

    返回：
        list[POI]: 符合条件的POI对象列表
    """
    # 先加载所有原始POI数据
    all_pois = load_pois()
    filtered: list[POI] = []

    for poi in all_pois:
        # 城市过滤：如果意图指定了城市，只保留该城市的POI
        if poi.get("city") != intent.city:
            continue

        # 将字典转换为POI对象并添加到结果列表
        filtered.append(POI(**poi))

    if intent.required_categories:
        matched = [poi for poi in filtered if poi.category in intent.required_categories]
        if matched:
            filtered = matched

    return filtered
