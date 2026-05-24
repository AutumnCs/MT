"""Prompt templates for the LLM intent parsing layer.

This module is intentionally separate from the hard-rule parser.
The LLM should produce a structured draft, and the backend will normalize
and validate it afterwards.
"""

from __future__ import annotations

SYSTEM_PROMPT = """
你是一个城市出行路线规划的意图解析器，专门把用户的自然语言需求转换成结构化 JSON。

你的任务是“理解”和“归一化”，不是直接规划路线。

请严格只输出 JSON，不要输出任何额外解释、前后缀、代码块标记。

输出字段如下：
{
  "city": "广州或上海等城市名，无法判断可留空",
  "start_location": "起点位置，可为空",
  "start_time": "开始时间，格式建议为 HH:MM，可为空",
  "end_time": "结束时间，格式建议为 HH:MM，可为空",
  "budget": 预算金额，可为空,
  "required_categories": ["coffee", "food", "exhibition"],
  "preferences": ["couple", "photo", "local_feature"],
  "avoid": ["queue", "crowded"],
  "pace": "slow | normal | fast",
  "transport_mode": "walking | metro | taxi | mixed",
  "must_include": ["必须出现的地点或类别"],
  "notes": "补充说明，可为空"
}

说明：
1. 用户明确说出的城市优先保留，例如“广州塔”“外滩”这类地标可用于推断城市。
2. 偏好应尽量归一到固定标签，不要发明新标签。
3. 预算、时间、起点等能识别就填，不能识别就留空，不要编造。
4. “约会、拍照、美食、文化、本地特色、夜景、安静、雨天”等属于偏好，不是硬约束。
5. “不想排队、不要太远、避开拥挤”这类可以写进 avoid。
6. 如果用户表达模糊，宁可留空，也不要强行猜一个很确定的值。
""".strip()

USER_PROMPT_TEMPLATE = """
请解析下面的用户需求，并只输出结构化 JSON。

用户输入：
{query}

当前显式城市（如果前端已经选择）：
{city}
""".strip()


def build_user_prompt(query: str, city: str | None = None) -> str:
    """Build a single user prompt for the LLM intent parser."""

    return USER_PROMPT_TEMPLATE.format(query=query or "", city=city or "")


def build_intent_prompt(query: str, city: str | None = None) -> dict[str, str]:
    """Return both system and user prompts for LLM intent parsing."""

    return {
        "system_prompt": SYSTEM_PROMPT,
        "user_prompt": build_user_prompt(query, city),
    }
