"""
响应生成服务模块
=================

本模块负责将内部数据结构转换为统一的API响应格式，并生成自然语言解释。

主要功能：
- 标准化API响应格式
- 生成路线说明文本
- 生成POI推荐理由
- 格式化各种统计信息

作者：美团智能路线规划团队
"""

from core.contracts import ClarificationDecision, RouteDiagnostics, RouteTaskHint
from core.schemas import ParsedIntent, RouteResponse, RouteStop


def generate_response(
    intent: ParsedIntent,
    ranked_pois: list[dict],
    planned_route: dict,
    explanation: str | None = None,
    diagnostics: RouteDiagnostics | None = None,
) -> RouteResponse:
    """
    生成标准的路线规划响应

    参数：
        intent: 用户意图
        ranked_pois: 评分后的POI列表
        planned_route: 路线规划结果
        explanation: 自然语言解释文本（可选）

    返回：
        RouteResponse: 标准化的响应对象
    """
    main_stops = planned_route.get("main", [])
    variants = planned_route.get("variants", [])
    stats = planned_route.get("stats", {})

    return RouteResponse(
        intent=intent,
        main_stops=main_stops,
        variants=variants,
        ranked_pois=ranked_pois,
        explanation=explanation or "",
        stats=stats,
        diagnostics=diagnostics,
    )


def generate_clarification_response(
    intent: ParsedIntent,
    question: str | ClarificationDecision,
    options: list[str] | None = None,
    *,
    reason: str | None = None,
    diagnostics: RouteDiagnostics | None = None,
) -> RouteResponse:
    """Generate a lightweight clarification response."""

    if isinstance(question, ClarificationDecision):
        decision = question
        question = decision.question
        options = list(decision.options)
        reason = reason or decision.reason

    summary = reason or "当前需求还不够明确，先补一个最关键的问题再继续。"
    return RouteResponse(
        intent=intent,
        main_stops=[],
        variants=[],
        ranked_pois=[],
        explanation=summary,
        summary=str(question),
        title="需要补充一点信息",
        diagnostics=diagnostics
        or RouteDiagnostics(
            task_hint=RouteTaskHint.ROUTE_MODIFICATION if getattr(intent, "current_route", None) is not None else RouteTaskHint.INTENT_EXTRACTION,
            parse_source=getattr(intent, "parse_source", "local"),
            clarification_needed=True,
            clarification_question=str(question),
            clarification_reason=reason or summary,
        ),
        clarification_needed=True,
        clarification_question=str(question),
        clarification_options=list(options or []),
        clarification_reason=reason or summary,
        stats={},
    )


def generate_route_explanation(intent: ParsedIntent, stops: list[RouteStop]) -> str:
    """
    生成路线的自然语言说明

    参数：
        intent: 用户意图
        stops: 路线站点列表

    返回：
        str: 自然语言说明文本
    """
    if not stops:
        return "没有找到合适的路线"

    # 统计信息
    total_visit = sum(s.poi.visit_duration for s in stops)
    total_travel = sum(s.travel_to_next_min for s in stops)
    total_cost = sum(s.poi.price for s in stops)

    lines = []
    lines.append(f"为你规划了一条{len(stops)}站的路线")
    lines.append(f"总游览时间：{total_visit}分钟，交通时间：{total_travel}分钟")
    if total_cost > 0:
        lines.append(f"预计花费：约{total_cost}元")

    return "，".join(lines) + "。"
