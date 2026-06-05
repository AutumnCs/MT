"""
LLM 意图解析客户端模块
======================

功能说明：
    本模块封装了 LLM（大语言模型）意图解析的调用逻辑，支持：
    - 通义千问（DashScope）
    - OpenAI
    - 本地解析回退

设计原则：
    1. 优先调用 LLM
    2. LLM 失败时自动回退到本地规则解析
    3. 支持多种 LLM 提供商
    4. 提供统一的解析接口

使用场景：
    - IntentParser 调用 LLM
    - Prompt 构建和发送
    - 响应解析和错误处理

Author: MeituanAgent Team
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional, Tuple

import httpx

from core.intent_parser import normalize_llm_intent, IntentParser
from core.schemas import IntentDraft, ParsedIntent
from core import prompt_templates


# ============================================================================
# 常量定义
# ============================================================================

# API 超时设置（秒）
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 2

# LLM 提供商
LLMProvider = str
PROVIDER_DASHSCOPE = "dashscope"
PROVIDER_OPENAI = "openai"

# 模型配置
DEFAULT_DASHSCOPE_MODEL = "qwen-plus"
DEFAULT_OPENAI_MODEL = "gpt-4"


# ============================================================================
# LLM 意图解析客户端类
# ============================================================================

class LLMIntentClient:
    """
    LLM 意图解析客户端

    功能：
        封装 LLM 调用逻辑，提供意图解析接口

    使用方法：
        client = LLMIntentClient()
        intent = client.parse_intent_with_llm("周六下午从广州塔出发，预算200，想约会")
    """

    def __init__(self):
        """初始化 LLM 客户端"""
        self._provider = self._detect_provider()
        self._parser = IntentParser()

    def _detect_provider(self) -> Optional[LLMProvider]:
        """
        检测可用的 LLM 提供商

        检测顺序：
            1. DashScope（通义千问）
            2. OpenAI

        返回：
            可用的提供商名称，或 None（如果都不可用）
        """
        # 检查 DashScope
        if os.getenv("DASHSCOPE_API_KEY"):
            return PROVIDER_DASHSCOPE

        # 检查 OpenAI
        if os.getenv("OPENAI_API_KEY"):
            return PROVIDER_OPENAI

        return None

    def parse_intent_with_llm(
        self,
        query: str,
        *,
        city: Optional[str] = None,
        task_hint: Optional[str] = None,
        original_query: Optional[str] = None,
        current_route: Any = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Optional[ParsedIntent]:
        """
        使用 LLM 解析意图

        参数：
            query: 用户输入的自然语言文本
            city: 显式指定的城市（可选）
            timeout: 请求超时时间（秒）

        返回：
            解析后的 ParsedIntent，或 None（如果解析失败）
        """
        # 如果没有可用提供商，直接返回 None
        if not self._provider:
            return None

        try:
            # 构建提示词：默认做意图抽取，修改请求走修改提示
            normalized_task = (task_hint or "intent_extraction").strip().lower()
            if normalized_task not in {"route_modification", "modify", "revise"}:
                normalized_task = "intent_extraction"
            prompts = prompt_templates.build_prompt_bundle(
                normalized_task,
                query,
                city=city,
                original_query=original_query,
                current_route=current_route,
            )

            # 调用 LLM
            if self._provider == PROVIDER_DASHSCOPE:
                response = self._call_dashscope(
                    system_prompt=prompts["system_prompt"],
                    user_prompt=prompts["user_prompt"],
                    timeout=timeout,
                )
            elif self._provider == PROVIDER_OPENAI:
                response = self._call_openai(
                    system_prompt=prompts["system_prompt"],
                    user_prompt=prompts["user_prompt"],
                    timeout=timeout,
                )
            else:
                return None

            # 解析响应
            if response:
                return self._parse_llm_response(response, query, city)

        except Exception as e:
            # 记录错误日志（如果需要）
            print(f"LLM 调用失败: {e}")

        return None

    def _call_dashscope(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: float,
    ) -> Optional[str]:
        """
        调用通义千问 API

        参数：
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            timeout: 超时时间

        返回：
            LLM 响应的文本内容，或 None
        """
        api_key = os.getenv("DASHSCOPE_API_KEY")
        model = os.getenv("DASHSCOPE_MODEL") or DEFAULT_DASHSCOPE_MODEL
        base_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "input": {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            },
            "parameters": {
                "temperature": 0.1,  # 低温度，提高确定性
                "result_format": "message",
            },
        }

        # 重试逻辑
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(
                        base_url,
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    result = response.json()

                    # 提取响应内容
                    if "output" in result and "choices" in result["output"]:
                        choices = result["output"]["choices"]
                        if choices and "message" in choices[0]:
                            return choices[0]["message"]["content"]

            except httpx.TimeoutException:
                last_error = "请求超时"
            except httpx.HTTPStatusError as e:
                last_error = f"HTTP 错误: {e.response.status_code}"
            except Exception as e:
                last_error = str(e)

            # 重试前等待
            if attempt < MAX_RETRIES - 1:
                time.sleep(1)

        return None

    def _call_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: float,
    ) -> Optional[str]:
        """
        调用 OpenAI API

        参数：
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            timeout: 超时时间

        返回：
            LLM 响应的文本内容，或 None
        """
        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
        base_url = os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,  # 低温度，提高确定性
        }

        # 重试逻辑
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(
                        base_url,
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    result = response.json()

                    # 提取响应内容
                    if "choices" in result and result["choices"]:
                        return result["choices"][0]["message"]["content"]

            except httpx.TimeoutException:
                last_error = "请求超时"
            except httpx.HTTPStatusError as e:
                last_error = f"HTTP 错误: {e.response.status_code}"
            except Exception as e:
                last_error = str(e)

            # 重试前等待
            if attempt < MAX_RETRIES - 1:
                time.sleep(1)

        return None

    def _parse_llm_response(
        self,
        response: str,
        query: str,
        city: Optional[str],
    ) -> Optional[ParsedIntent]:
        """
        解析 LLM 响应

        功能：
            1. 提取 JSON 内容
            2. 转换为 IntentDraft
            3. 归一化为 ParsedIntent

        参数：
            response: LLM 响应文本
            query: 原始查询
            city: 显式城市

        返回：
            ParsedIntent 或 None
        """
        try:
            # 尝试提取 JSON
            json_str = self._extract_json(response)
            if not json_str:
                return None

            # 解析 JSON
            draft_dict = json.loads(json_str)
            if not isinstance(draft_dict, dict):
                return None

            # 添加原始响应（用于调试）
            draft_dict["_raw_response"] = response

            # 归一化为 ParsedIntent
            return normalize_llm_intent(draft_dict, query, city)

        except json.JSONDecodeError:
            # JSON 解析失败
            return None

    def _extract_json(self, text: str) -> Optional[str]:
        """
        从文本中提取 JSON

        功能：
            处理 LLM 输出可能包含的额外文本（如思考过程）

        参数：
            text: 原始文本

        返回：
            提取的 JSON 字符串，或 None
        """
        text = text.strip()

        # 情况1：直接是 JSON
        if text.startswith("{") and text.endswith("}"):
            return text

        # 情况2：包含在代码块中
        if "```json" in text:
            parts = text.split("```json")
            if len(parts) > 1:
                json_part = parts[1].split("```")[0].strip()
                return json_part

        # 情况3：包含在反引号中
        if "`" in text:
            for part in text.split("`"):
                part = part.strip()
                if part.startswith("{") and part.endswith("}"):
                    return part

        # 情况4：查找第一个 { 到最后一个 }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace >= 0 and last_brace > first_brace:
            return text[first_brace : last_brace + 1]

        return None


# ============================================================================
# 便捷函数
# ============================================================================

def parse_intent(
    query: str,
    *,
    city: Optional[str] = None,
    use_llm: bool = True,
) -> ParsedIntent:
    """
    解析意图的统一入口

    参数：
        query: 用户输入的自然语言文本
        city: 显式指定的城市（可选）
        use_llm: 是否优先使用 LLM（默认 True）

    返回：
        ParsedIntent: 解析后的结构化意图
    """
    if use_llm:
        # 尝试 LLM 解析
        client = LLMIntentClient()
        intent = client.parse_intent_with_llm(query, city=city)
        if intent:
            return intent

    # 回退到本地规则解析
    parser = IntentParser()
    return parser.parse_intent(query, city)


_DEFAULT_LLM_CLIENT = LLMIntentClient()


def parse_intent_with_llm(
    query: str,
    city: Optional[str] = None,
    *,
    task_hint: Optional[str] = None,
    original_query: Optional[str] = None,
    current_route: Any = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Optional[ParsedIntent]:
    """Backward-compatible module-level entry point for LLM parsing."""

    return _DEFAULT_LLM_CLIENT.parse_intent_with_llm(
        query,
        city=city,
        task_hint=task_hint,
        original_query=original_query,
        current_route=current_route,
        timeout=timeout,
    )
