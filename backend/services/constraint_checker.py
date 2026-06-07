"""
约束检查服务模块
=================

本模块负责验证用户意图的硬约束，并筛选出符合条件的POI。

主要功能：
- 验证意图是否包含必要的硬约束（城市、时间等）
- 过滤掉用户明确不想去的类别
- 根据硬约束（如预算上限）筛选POI
- 返回验证结果和错误信息

作者：美团智能路线规划团队
"""

from core.schemas import POI, ParsedIntent


def validate_intent(intent: ParsedIntent) -> dict:
    """
    验证用户意图是否完整和合理

    验证规则：
        - 必须指定城市
        - 可用时间必须大于0

    参数：
        intent: 解析后的用户意图

    返回：
        dict: 验证结果字典，包含valid（是否有效）和errors（错误信息列表）
    """
    errors = []
    # 城市是必填项
    if not intent.city:
        errors.append("请告诉我你想去哪个城市")
    # 可用时间必须大于0
    if intent.available_time <= 0:
        errors.append("请告诉我你有多少可用时间")

    return {"valid": len(errors) == 0, "errors": errors}


def filter_pois_by_constraints(pois: list[POI], intent: ParsedIntent) -> list[POI]:
    """
    根据硬约束过滤POI

    过滤规则：
        1. 移除用户明确避免的类别
        2. 如果有预算上限，移除价格超标的POI

    参数：
        pois: POI对象列表
        intent: 用户意图

    返回：
        list[POI]: 符合硬约束的POI列表
    """
    filtered = []
    for poi in pois:
        # 检查是否在避免类别中
        if intent.avoid_categories and poi.category in intent.avoid_categories:
            continue
        # 检查是否超过预算上限
        if intent.budget_max and poi.price > intent.budget_max:
            continue
        filtered.append(poi)
    return filtered
