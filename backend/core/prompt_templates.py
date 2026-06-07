"""
LLM 提示词模板模块
==================

功能说明：
    本模块定义了用于 LLM 调用的各类提示词模板，包括：
    - 意图提取：从自由文本中提取结构化意图
    - 路线修改：从后续编辑中提取修改要求
    - 路线解释：将完成路线转化为用户友好的说明
    - 能力路由：判断用户输入应该交给哪个能力处理

设计原则：
    1. LLM 只负责理解，不负责规划
    2. 后端负责归一化和验证
    3. 提示词是管道的第一步

输出格式：
    所有提示词都要求 LLM 输出纯 JSON，不包含任何额外解释或格式标记

Author: MeituanAgent Team
"""

from __future__ import annotations

from core import capability_registry
from core.intent_lexicon import prompt_lexicon_excerpt


# ============================================================================
# 意图提取系统提示词
# ============================================================================

INTENT_EXTRACTION_SYSTEM_PROMPT = """
你是一个城市出行路线规划的意图解析器，专门把用户的自然语言需求转换成结构化 JSON。

你的任务是"理解"和"归一化"，不是直接规划路线。

请严格只输出 JSON，不要输出任何额外解释、前后缀、代码块标记。

输出字段如下：
{
  "city": "广州或上海等城市名，无法判断可留空",
  "start_location": "起点位置，可为空",
  "start_time": "开始时间，格式建议为 HH:MM，可为空",
  "end_time": "结束时间，格式建议为 HH:MM，可为空",
  "budget": 预算金额，可为空,
  "required_categories": ["coffee", "food", "library", "exhibition"],
  "preferences": ["couple", "photo", "local_feature"],
  "avoid": ["queue", "crowded"],
  "pace": "slow | normal | fast",
  "transport_mode": "walking | metro | taxi | mixed",
  "must_include": ["必须出现的地点或类别"],
  "notes": "补充说明，可为空"
}

说明：
1. 用户明确说出的城市优先保留，例如"广州塔""外滩"这类地标可用于推断城市。
2. 偏好应尽量归一到固定标签，不要发明新标签。
3. 预算、时间、起点等能识别就填，不能识别就留空，不要编造。
4. "约会、拍照、美食、文化、本地特色、夜景、安静、雨天"等属于偏好，不是硬约束。
5. "不想排队、不要太远、避开拥挤"这类可以写进 avoid。
6. "图书馆、阅读、自习、看书"应归入 required_categories 的 library。
7. 如果用户明确表达顺序，例如"第一站先去图书馆、然后休息、晚饭、吃完后看夜景"，请把这些顺序要求保留在 notes 中。
8. 如果用户表达模糊，宁可留空，也不要强行猜一个很确定的值。

可参考的标准标签与常见同义表达：
[[LEXICON_EXCERPT]]
""".strip()


# ============================================================================
# 路线修改系统提示词
# ============================================================================

ROUTE_MODIFICATION_SYSTEM_PROMPT = """
你是一个路线修改意图解析器，负责把用户对现有路线的调整要求转换成结构化 JSON。

你的任务是理解"在原路线基础上要怎么改"，不是重新规划整条路线。

请严格只输出 JSON，不要输出任何额外解释、前后缀、代码块标记。

输出字段沿用以下结构：
{
  "city": "城市名，可留空",
  "start_location": "起点位置，可为空",
  "start_time": "开始时间，HH:MM，可为空",
  "end_time": "结束时间，HH:MM，可为空",
  "budget": 预算金额，可为空,
  "required_categories": ["coffee", "food", "library", "exhibition"],
  "preferences": ["couple", "photo", "local_feature"],
  "avoid": ["queue", "crowded"],
  "pace": "slow | normal | fast",
  "transport_mode": "walking | metro | taxi | mixed",
  "must_include": ["必须保留或新增的地点或类别"],
  "notes": "补充说明，可为空"
}

修改场景的理解原则：
1. "太远了、换近一点、别太绕" 优先理解为节奏更紧凑、交通更轻量。
2. "预算低一点、便宜点、控制成本" 优先理解为预算收紧。
3. "不要排队、别等太久、避开人多" 优先写进 avoid。
4. "拍照多一点、想更出片、加点打卡点" 优先归一到 photo。
5. "室内、避雨、雨天友好" 优先归一到 rainy_day。
6. 如果是基于原路线的微调，尽量保留原城市和核心偏好，不要无中生有地换城市。
""".strip()


# ============================================================================
# 路线解释系统提示词
# ============================================================================

ROUTE_EXPLANATION_SYSTEM_PROMPT = """
你是一个路线说明器，负责把已有路线总结成用户能快速理解的解释文本。

你不会重新决定路线，只负责说明：
- 为什么这条路线适合当前需求
- 哪些偏好被覆盖了
- 哪些风险需要注意
- 用户如果想改，应该往哪个方向改

如果信息不足，直接说明未知，不要编造。
""".strip()


# ============================================================================
# 意图提取用户模板
# ============================================================================

INTENT_EXTRACTION_USER_TEMPLATE = """
请解析下面的用户需求，并只输出结构化 JSON。

用户输入：
{query}

当前显式城市（如果前端已经选择）：
{city}
""".strip()


# ============================================================================
# 路线修改用户模板
# ============================================================================

ROUTE_MODIFICATION_USER_TEMPLATE = """
请解析下面的路线修改需求，并只输出结构化 JSON。

原始需求：
{original_query}

当前路线摘要：
{current_route}

用户修改要求：
{query}

当前显式城市（如果前端已经选择）：
{city}
""".strip()


# ============================================================================
# 路线解释用户模板
# ============================================================================

ROUTE_EXPLANATION_USER_TEMPLATE = """
请根据下面的路线信息，生成一段简短、自然、可信的路线说明。

路线摘要：
{route_summary}

系统理解：
{intent_summary}
""".strip()


# ============================================================================
# 能力路由系统提示词
# ============================================================================

CAPABILITY_ROUTER_SYSTEM_PROMPT = """
你是一个能力路由器，专门判断用户输入应该交给哪个能力处理。

你的任务是：在给定的能力注册表里选择最合适的一个能力名。

要求：
1. 只能从注册表中选择已有能力名，不能自造能力名。
2. 如果输入明显不属于任何能力，输出 `unknown`。
3. 不要展开长篇推理，只给出简短、结构化的判断结果。
4. 需要尽量利用例句和路由信号做举一反三，而不是机械匹配关键词。
5. 低置信度时优先保守，不要强行分类。

输出 JSON，字段建议如下：
{
  "capability": "intent_parsing | route_generation | route_modification | map_resolution | route_explanation | knowledge_explanation | offline_evaluation | unknown",
  "confidence": 0.0,
  "reason": "简短原因",
  "matched_signals": ["命中的提示词"],
  "unknown_clues": ["暂时没法归类的片段"]
}

注册表摘要：
[[CAPABILITY_EXCERPT]]
""".strip()


# ============================================================================
# 能力路由用户模板
# ============================================================================

CAPABILITY_ROUTER_USER_TEMPLATE = """
请判断下面这条输入应该交给哪个能力处理，并只输出 JSON。

用户输入：
{query}
""".strip()


# ============================================================================
# 辅助函数
# ============================================================================

def _format_current_route(current_route: dict | str | None) -> str:
    """
    格式化当前路线信息为可读文本

    参数：
        current_route: 路线字典或字符串

    返回：
        格式化的路线描述字符串
    """
    if not current_route:
        return ""

    # 如果是字符串，直接返回
    if isinstance(current_route, str):
        return current_route

    parts: list[str] = []

    # 提取关键信息
    for key in ("title", "summary", "route_explanation"):
        value = current_route.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(f"{key}: {value.strip()}")

    # 提取站点名称
    stops = current_route.get("stops") or []
    stop_names: list[str] = []
    if isinstance(stops, list):
        for stop in stops:
            if isinstance(stop, dict):
                poi = stop.get("poi") or {}
                if isinstance(poi, dict):
                    name = poi.get("name")
                    if isinstance(name, str) and name.strip():
                        stop_names.append(name.strip())

    # 格式化为 "站点A -> 站点B -> 站点C" 形式，最多显示6个
    if stop_names:
        parts.append("stops: " + " -> ".join(stop_names[:6]))

    return "\n".join(parts)


# ============================================================================
# Prompt 构建函数
# ============================================================================

def build_user_prompt(query: str, city: str | None = None) -> str:
    """
    构建用户提示词

    参数：
        query: 用户输入文本
        city: 显式城市（可选）

    返回：
        格式化的用户提示词
    """
    return INTENT_EXTRACTION_USER_TEMPLATE.format(query=query or "", city=city or "")


def build_intent_extraction_prompt(query: str, city: str | None = None) -> dict[str, str]:
    """
    构建意图提取提示词

    参数：
        query: 用户输入文本
        city: 显式城市（可选）

    返回：
        包含 system_prompt 和 user_prompt 的字典
    """
    # 替换占位符为实际的词典摘要
    system_prompt = INTENT_EXTRACTION_SYSTEM_PROMPT.replace(
        "[[LEXICON_EXCERPT]]",
        prompt_lexicon_excerpt(),
    )
    # 添加额外指导：当用户使用词典外的词汇时，映射到最接近的现有标签
    system_prompt += "\n\nAdditional guidance: when the user uses words outside the current lexicon, map them to the closest existing canonical tag first. If you still cannot determine a safe mapping, keep the raw phrase in notes instead of inventing a new tag."

    return {
        "system_prompt": system_prompt,
        "user_prompt": build_user_prompt(query, city),
    }


def build_route_modification_prompt(
    query: str,
    *,
    original_query: str | None = None,
    current_route: dict | str | None = None,
    city: str | None = None,
) -> dict[str, str]:
    """
    构建路线修改提示词

    参数：
        query: 修改要求文本
        original_query: 原始需求文本
        current_route: 当前路线信息
        city: 显式城市（可选）

    返回：
        包含 system_prompt 和 user_prompt 的字典
    """
    system_prompt = ROUTE_MODIFICATION_SYSTEM_PROMPT + "\n\nAdditional guidance: if the user uses new phrasing while modifying a route, still map it to the closest existing change label. When you are not sure, keep the raw wording so we can backfill the lexicon later."

    return {
        "system_prompt": system_prompt,
        "user_prompt": ROUTE_MODIFICATION_USER_TEMPLATE.format(
            original_query=original_query or "",
            current_route=_format_current_route(current_route),
            query=query or "",
            city=city or "",
        ),
    }


def build_route_explanation_prompt(
    route_summary: str,
    intent_summary: str | None = None,
) -> dict[str, str]:
    """
    构建路线解释提示词

    参数：
        route_summary: 路线摘要
        intent_summary: 意图摘要（可选）

    返回：
        包含 system_prompt 和 user_prompt 的字典
    """
    return {
        "system_prompt": ROUTE_EXPLANATION_SYSTEM_PROMPT,
        "user_prompt": ROUTE_EXPLANATION_USER_TEMPLATE.format(
            route_summary=route_summary or "",
            intent_summary=intent_summary or "",
        ),
    }


def build_capability_router_prompt(query: str) -> dict[str, str]:
    """
    构建能力路由提示词

    参数：
        query: 用户输入文本

    返回：
        包含 system_prompt 和 user_prompt 的字典
    """
    # 替换占位符为实际的能力注册表摘要
    system_prompt = CAPABILITY_ROUTER_SYSTEM_PROMPT.replace(
        "[[CAPABILITY_EXCERPT]]",
        capability_registry.prompt_capability_excerpt(),
    )
    # 添加额外指导：路由到最小且最安全的能力
    system_prompt += (
        "\n\nAdditional guidance: route to the smallest capability that can safely handle the request. "
        "If multiple capabilities seem plausible, prefer the one that changes the least amount of system state. "
        "If nothing is safe, return unknown."
    )

    return {
        "system_prompt": system_prompt,
        "user_prompt": CAPABILITY_ROUTER_USER_TEMPLATE.format(query=query or ""),
    }


def build_prompt_bundle(
    task: str,
    query: str,
    *,
    city: str | None = None,
    original_query: str | None = None,
    current_route: dict | str | None = None,
    route_summary: str | None = None,
    intent_summary: str | None = None,
) -> dict[str, str]:
    """
    根据任务类型构建提示词包

    参数：
        task: 任务类型（intent_extraction/modify/route_capability/explain）
        query: 用户输入文本
        city: 显式城市（可选）
        original_query: 原始需求（修改时使用）
        current_route: 当前路线（修改时使用）
        route_summary: 路线摘要（解释时使用）
        intent_summary: 意图摘要（解释时使用）

    返回：
        提示词包字典
    """
    normalized_task = (task or "intent_extraction").strip().lower()

    # 路线修改任务
    if normalized_task in {"modify", "route_modification", "revise"}:
        return build_route_modification_prompt(
            query,
            original_query=original_query,
            current_route=current_route,
            city=city,
        )

    # 能力路由任务
    if normalized_task in {"route_capability", "capability_router", "skill_router"}:
        return build_capability_router_prompt(query)

    # 路线解释任务
    if normalized_task in {"explain", "route_explanation", "summary"}:
        return build_route_explanation_prompt(route_summary or "", intent_summary)

    # 默认：意图提取任务
    return build_intent_extraction_prompt(query, city)


def build_intent_prompt(query: str, city: str | None = None) -> dict[str, str]:
    """
    向后兼容的意图提示词构建函数

    参数：
        query: 用户输入文本
        city: 显式城市（可选）

    返回：
        提示词包字典
    """
    return build_intent_extraction_prompt(query, city)
