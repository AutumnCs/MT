"""
能力注册中心模块
================

功能说明：
    本模块负责管理系统支持的各项能力，支持能力发现、匹配和路由。

主要功能：
    1. 从 capabilities.json 加载能力清单
    2. 根据用户输入匹配最合适的能力
    3. 计算能力匹配置信度
    4. 支持能力路由和降级策略

能力匹配算法：
    - 基于关键词匹配和相似度计算
    - 支持别名、反例等扩展匹配
    - 使用 Sigmoid 函数归一化置信度

Author: MeituanAgent Team
"""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from core.contracts import CapabilityMatchResult


# ============================================================================
# 路径配置
# ============================================================================

# 获取当前文件所在目录的绝对路径
_HERE = Path(__file__).resolve()

# 能力清单文件路径（位于 backend 目录下）
CAPABILITIES_PATH = _HERE.parents[1] / "capabilities.json"


# ============================================================================
# 正则表达式配置
# ============================================================================

# 编译正则表达式，用于分割中英文混合文本
# 匹配规则：连续2个以上的中文字符，或连续2个以上的英文/数字/特殊字符
# 用途：从文本中提取有意义的词项
_WORD_RE = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_:+-]{2,}")


# ============================================================================
# 能力加载函数
# ============================================================================

@lru_cache(maxsize=1)
def load_capability_registry() -> dict[str, Any]:
    """
    加载能力注册中心

    说明：
        使用 LRU 缓存确保只读取一次文件，提高性能

    返回：
        {
            "version": str,  # 版本号
            "updated_at": str | None,  # 更新时间
            "capabilities": list[dict]  # 能力列表
        }
    """
    # 如果文件不存在，返回空注册中心
    if not CAPABILITIES_PATH.exists():
        return {"version": "0", "updated_at": None, "capabilities": []}

    try:
        # 读取并解析 JSON 文件
        payload = json.loads(CAPABILITIES_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            # 确保 capabilities 字段存在
            payload.setdefault("capabilities", [])
            return payload
    except json.JSONDecodeError:
        # JSON 解析失败时返回空注册中心
        pass

    return {"version": "0", "updated_at": None, "capabilities": []}


# ============================================================================
# 能力查询函数
# ============================================================================

def list_capabilities() -> list[dict[str, Any]]:
    """
    获取所有能力列表

    返回：
        能力字典列表，每个字典包含：
        - name: 能力名称
        - description: 能力描述
        - route_signals: 路由关键词
        - aliases: 别名列表
        - canonical_tags: 规范化标签
        - examples: 正例列表
        - anti_examples: 反例列表
    """
    registry = load_capability_registry()
    capabilities = registry.get("capabilities", [])
    return capabilities if isinstance(capabilities, list) else []


def get_capability(name: str) -> Optional[dict[str, Any]]:
    """
    根据名称获取单个能力

    参数：
        name: 能力名称

    返回：
        能力字典，如果不存在返回 None
    """
    cleaned = (name or "").strip()
    if not cleaned:
        return None

    # 遍历查找匹配的能力
    for capability in list_capabilities():
        if isinstance(capability, dict) and capability.get("name") == cleaned:
            return capability
    return None


# ============================================================================
# 辅助函数
# ============================================================================

def _normalize_terms(values: Any) -> list[str]:
    """
    规范化术语列表

    功能：
        - 过滤空值和重复项
        - 去除首尾空格
        - 确保返回列表中的项唯一

    参数：
        values: 任意类型的值，通常是字符串列表

    返回：
        规范化后的字符串列表
    """
    result: list[str] = []
    if not isinstance(values, list):
        return result

    for value in values:
        if isinstance(value, str):
            cleaned = value.strip()
            # 过滤空字符串并避免重复
            if cleaned and cleaned not in result:
                result.append(cleaned)
    return result


def _capability_terms(capability: dict[str, Any]) -> tuple[list[str], list[str], list[str], list[str]]:
    """
    提取能力的关键术语

    参数：
        capability: 能力字典

    返回：
        四元组 (路由信号, 规范化标签, 正例, 反例)
    """
    route_signals = _normalize_terms(capability.get("route_signals"))
    aliases = _normalize_terms(capability.get("aliases"))
    canonical_tags = _normalize_terms(capability.get("canonical_tags"))
    examples = _normalize_terms(capability.get("examples"))
    anti_examples = _normalize_terms(capability.get("anti_examples"))

    # 路由信号 = 显式信号 + 别名
    return route_signals + aliases, canonical_tags, examples, anti_examples


def _score_capability(text: str, capability: dict[str, Any]) -> CapabilityMatchResult:
    """
    计算能力匹配分数

    匹配策略：
        1. 路由信号匹配（权重 4.0）- 最高优先级
        2. 规范化标签匹配（权重 2.0）
        3. 正例部分匹配（权重 1.5）- 使用分词匹配
        4. 反例匹配（权重 -3.0）- 降低分数
        5. 名称直接匹配（权重 1.5）
        6. 描述关键词匹配（权重 0.5）
        7. 优先级加成

    参数：
        text: 用户输入文本
        capability: 能力字典

    返回：
        包含分数和匹配信息的字典
    """
    query = (text or "").strip()

    # 提取术语
    route_signals, canonical_tags, examples, anti_examples = _capability_terms(capability)
    name = str(capability.get("name") or "").strip()
    description = str(capability.get("description") or "").strip()
    priority = capability.get("priority", 0)  # 优先级（0-100）
    min_confidence = capability.get("min_confidence", 0.65)  # 最小置信度

    matched_signals: list[str] = []
    matched_examples: list[str] = []
    score = 0.0
    has_direct_match = False

    def add_match(source: str, item: str, weight: float) -> None:
        """
        添加匹配项并更新分数

        参数：
            source: 匹配来源（signal/tag/example）
            item: 匹配的项
            weight: 权重
        """
        nonlocal score, has_direct_match

        # 精确匹配
        if item in query:
            score += weight
            has_direct_match = True
            if item not in matched_signals:
                matched_signals.append(item)
        # 示例的部分token匹配（仅对正例生效，权重减半）
        elif source == "example" and any(token in query for token in _WORD_RE.findall(item)):
            score += weight * 0.5
            has_direct_match = True
            if item not in matched_examples:
                matched_examples.append(item)

    # 逐项匹配
    for item in route_signals:
        add_match("signal", item, 4.0)  # 路由信号最高权重
    for item in canonical_tags:
        add_match("tag", item, 2.0)
    for item in examples:
        add_match("example", item, 1.5)
    for item in anti_examples:
        if item in query:
            score -= 3.0  # 反例降低分数
            matched_examples.append(f"!{item}")

    # 能力名称直接匹配
    if name and name in query:
        score += 1.5
        if name not in matched_signals:
            matched_signals.append(name)

    # 描述关键词匹配
    if description:
        # 提取描述中的前3个长词项
        desc_words = [token for token in _WORD_RE.findall(description) if len(token) >= 2][:3]
        if any(token in query for token in desc_words):
            score += 0.5
            has_direct_match = True

    # 优先级加成（有直接匹配时生效）
    if has_direct_match:
        score += float(priority) / 100.0

    # Sigmoid 函数归一化置信度到 [0.01, 0.99]
    # 公式：1 / (1 + exp(-(score - 1.6)))
    # score=1.6 时 confidence≈0.5
    raw_confidence = 1.0 / (1.0 + math.exp(-(score - 1.6)))
    confidence = round(max(0.01, min(0.99, raw_confidence)), 3)

    # 如果分数低于0.5，限制置信度不超过最小置信度的80%
    if score < 0.5:
        confidence = round(min(confidence, float(min_confidence) * 0.8), 3)

    return CapabilityMatchResult(
        name=name,
        category=capability.get("category"),
        description=description,
        score=round(score, 3),
        confidence=confidence,
        matched_signals=matched_signals,
        matched_examples=matched_examples,
        priority=int(priority or 0),
        min_confidence=float(min_confidence),
        raw=capability,
    )


# ============================================================================
# 能力匹配与路由函数
# ============================================================================

def match_capabilities(text: str, limit: int | None = None) -> list[CapabilityMatchResult]:
    """
    匹配用户输入与所有能力

    参数：
        text: 用户输入文本
        limit: 返回结果数量限制，None 表示返回所有匹配结果

    返回：
        按分数降序排列的匹配结果列表
    """
    query = (text or "").strip()
    if not query:
        return []

    # 对每个能力计算匹配分数
    scored: list[CapabilityMatchResult] = []
    for capability in list_capabilities():
        if not isinstance(capability, dict):
            continue
        scored.append(_score_capability(query, capability))

    # 过滤无效结果（无分数且无匹配项）
    scored = [
        item
        for item in scored
        if item.score > 0 or item.matched_signals or item.matched_examples
    ]

    # 按多级排序：分数 -> 置信度 -> 优先级 -> 名称
    scored.sort(
        key=lambda item: (
            item.score,
            item.confidence,
            item.priority,
            item.name,
        ),
        reverse=True,
    )

    # 限制返回数量
    if limit is not None and limit >= 0:
        scored = scored[:limit]
    return scored


def route_capability(text: str, default: str = "intent_parsing") -> CapabilityMatchResult:
    """
    路由到最匹配的能力

    参数：
        text: 用户输入文本
        default: 默认能力名称（当无匹配时使用）

    返回：
        匹配到的能力信息字典
    """
    matches = match_capabilities(text, limit=1)

    # 如果有匹配且分数大于0，使用匹配结果
    if matches and matches[0].score > 0:
        return matches[0]

    # 否则使用默认能力
    fallback = get_capability(default) or {}
    return CapabilityMatchResult(
        name=fallback.get("name", default),
        category=fallback.get("category"),
        description=fallback.get("description"),
        score=0.0,
        confidence=0.0,
        matched_signals=[],
        matched_examples=[],
        priority=int(fallback.get("priority", 0) or 0),
        min_confidence=float(fallback.get("min_confidence", 0.65) or 0.65),
        raw=fallback,
    )


# ============================================================================
# 提示词生成函数
# ============================================================================

def prompt_capability_excerpt(limit: int = 5) -> str:
    """
    生成能力摘要文本（用于 Prompt 注入）

    参数：
        limit: 最多包含的能力数量

    返回：
        格式化的能力摘要字符串，每行一个能力
    """
    lines: list[str] = []
    for capability in list_capabilities()[: max(0, limit)]:
        if not isinstance(capability, dict):
            continue

        name = capability.get("name", "")
        description = capability.get("description", "")
        route_signals = _normalize_terms(capability.get("route_signals"))[:3]  # 最多3个信号
        examples = _normalize_terms(capability.get("examples"))[:1]  # 最多1个正例
        anti_examples = _normalize_terms(capability.get("anti_examples"))[:1]  # 最多1个反例

        # 格式化输出
        signal_text = " / ".join(route_signals) if route_signals else "none"
        example_text = examples[0] if examples else "none"
        anti_text = anti_examples[0] if anti_examples else "none"

        lines.append(
            f"- {name}: {description} | signals: {signal_text} | example: {example_text} | anti: {anti_text}"
        )

    return "\n".join(lines) if lines else "- none"
