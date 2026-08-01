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
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    import httpx
except ModuleNotFoundError:
    httpx = None

from core.intent_parser import normalize_llm_intent, IntentParser
from core.schemas import IntentDraft, ParsedIntent
from core import prompt_templates


# ============================================================================
# 常量定义
# ============================================================================

# API 超时设置（秒）。路线生成有 <10s 的体验目标，意图解析不能无限等模型。
DEFAULT_TIMEOUT = 6.0
MAX_RETRIES = 1

# LLM 提供商
LLMProvider = str
PROVIDER_DASHSCOPE = "dashscope"
PROVIDER_OPENAI = "openai"

# 模型配置
DEFAULT_DASHSCOPE_MODEL = "qwen-turbo"
DEFAULT_OPENAI_MODEL = "gpt-4"


def _json_response_format() -> dict[str, str]:
    return {"type": "json_object"}


def _load_env_file() -> None:
    """Load local .env values without requiring python-dotenv."""

    candidates = [
        Path(__file__).resolve().parents[1] / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        except OSError:
            continue


_load_env_file()

try:
    DEFAULT_TIMEOUT = float(os.getenv("LLM_INTENT_TIMEOUT", str(DEFAULT_TIMEOUT)))
except ValueError:
    DEFAULT_TIMEOUT = 6.0
try:
    MAX_RETRIES = max(1, int(os.getenv("LLM_INTENT_MAX_RETRIES", str(MAX_RETRIES))))
except ValueError:
    MAX_RETRIES = 1


def _post_json_with_urllib(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    result = json.loads(body)
    return result if isinstance(result, dict) else {}


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
        if os.getenv("LLM_INTENT_DISABLE_LLM") == "1":
            return None

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
        memory_context: Optional[str] = None,
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
                memory_context=memory_context,
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
        if not api_key:
            return None
        model = os.getenv("DASHSCOPE_MODEL") or DEFAULT_DASHSCOPE_MODEL
        base_url = os.getenv("DASHSCOPE_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

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
            "temperature": 0.1,
        }
        if os.getenv("LLM_INTENT_JSON_RESPONSE", "1") != "0":
            payload["response_format"] = _json_response_format()

        # 重试逻辑
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                if httpx is not None:
                    with httpx.Client(timeout=timeout) as client:
                        response = client.post(
                            base_url,
                            headers=headers,
                            json=payload,
                        )
                        response.raise_for_status()
                        result = response.json()
                else:
                    result = _post_json_with_urllib(base_url, headers, payload, timeout)

                if "choices" in result and result["choices"]:
                    message = result["choices"][0].get("message") or {}
                    content = message.get("content")
                    if content:
                        return content
                if "output" in result and "choices" in result["output"]:
                    choices = result["output"]["choices"]
                    if choices and "message" in choices[0]:
                        return choices[0]["message"]["content"]

            except TimeoutError:
                last_error = "请求超时"
            except urllib.error.HTTPError as e:
                last_error = f"HTTP 错误: {e.code}"
            except urllib.error.URLError as e:
                last_error = f"网络错误: {e.reason}"
            except Exception as e:
                if httpx is not None and e.__class__.__name__ == "TimeoutException":
                    last_error = "请求超时"
                elif httpx is not None and e.__class__.__name__ == "HTTPStatusError":
                    response = getattr(e, "response", None)
                    last_error = f"HTTP 错误: {getattr(response, 'status_code', 'unknown')}"
                else:
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
        if not api_key:
            return None
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
        if os.getenv("LLM_INTENT_JSON_RESPONSE", "1") != "0":
            payload["response_format"] = _json_response_format()
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                if httpx is not None:
                    with httpx.Client(timeout=timeout) as client:
                        response = client.post(
                            base_url,
                            headers=headers,
                            json=payload,
                        )
                        response.raise_for_status()
                        result = response.json()
                else:
                    result = _post_json_with_urllib(base_url, headers, payload, timeout)

                # 提取响应内容
                if "choices" in result and result["choices"]:
                    return result["choices"][0]["message"]["content"]

            except TimeoutError:
                last_error = "请求超时"
            except urllib.error.HTTPError as e:
                last_error = f"HTTP 错误: {e.code}"
            except urllib.error.URLError as e:
                last_error = f"网络错误: {e.reason}"
            except Exception as e:
                if httpx is not None and e.__class__.__name__ == "TimeoutException":
                    last_error = "请求超时"
                elif httpx is not None and e.__class__.__name__ == "HTTPStatusError":
                    response = getattr(e, "response", None)
                    last_error = f"HTTP 错误: {getattr(response, 'status_code', 'unknown')}"
                else:
                    last_error = str(e)

            # 重试前等待
            if attempt < MAX_RETRIES - 1:
                time.sleep(1)

        return None

    def _call_openai_legacy_removed(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: float,
    ) -> Optional[str]:
        api_key = os.getenv("OPENAI_API_KEY")
        if httpx is None:
            return None
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
            try:
                validated_draft = IntentDraft.model_validate(draft_dict)
                draft_payload = validated_draft.model_dump(mode="json")
            except Exception:
                draft_payload = draft_dict
            return normalize_llm_intent(draft_payload, query, city)

        except (json.JSONDecodeError, TypeError, ValueError) as e:
            if os.getenv("LLM_INTENT_DEBUG") == "1":
                print(f"LLM JSON 解析失败: {e}; response_head={response[:500]!r}")
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
        if text.startswith("{"):
            try:
                obj, end = json.JSONDecoder().raw_decode(text)
                if isinstance(obj, dict):
                    return text[:end]
            except json.JSONDecodeError:
                pass

        # 情况2：包含在代码块中
        if "```json" in text:
            parts = text.split("```json")
            if len(parts) > 1:
                json_part = parts[1].split("```")[0].strip()
                try:
                    obj, end = json.JSONDecoder().raw_decode(json_part)
                    if isinstance(obj, dict):
                        return json_part[:end]
                except json.JSONDecodeError:
                    pass

        # 情况3：包含在反引号中
        if "`" in text:
            for part in text.split("`"):
                part = part.strip()
                if not part.startswith("{"):
                    continue
                try:
                    obj, end = json.JSONDecoder().raw_decode(part)
                    if isinstance(obj, dict):
                        return part[:end]
                except json.JSONDecodeError:
                    continue

        # 情况4：从每个左大括号开始，寻找第一个可解析的 JSON 对象
        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char != "{":
                continue
            try:
                obj, end = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return text[index : index + end]

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
    memory_context: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Optional[ParsedIntent]:
    """Backward-compatible module-level entry point for LLM parsing."""

    return _DEFAULT_LLM_CLIENT.parse_intent_with_llm(
        query,
        city=city,
        task_hint=task_hint,
        original_query=original_query,
        current_route=current_route,
        memory_context=memory_context,
        timeout=timeout,
    )
