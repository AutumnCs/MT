from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

import prompt_templates
import intent_parser
import schemas


ENV_PATHS = [
    Path(__file__).resolve().with_name(".env"),
    Path(__file__).resolve().parents[1] / ".env",
    Path(__file__).resolve().parents[3] / "poi" / "config" / ".env",
]


def load_local_env() -> None:
    for path in ENV_PATHS:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            cleaned = line.strip()
            if not cleaned or cleaned.startswith("#") or "=" not in cleaned:
                continue
            key, value = cleaned.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _extract_json(text: str) -> Optional[dict[str, Any]]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()

    try:
        payload = json.loads(cleaned)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                payload = json.loads(cleaned[start : end + 1])
                return payload if isinstance(payload, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def _post_json(url: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    timeout = int(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _chat_payload(query: str, city: str | None, model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt_templates.SYSTEM_PROMPT},
            {"role": "user", "content": prompt_templates.build_user_prompt(query, city)},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }


def _call_chat_completion(query: str, city: str | None) -> Optional[dict[str, Any]]:
    if os.getenv("LLM_INTENT_DISABLE_LLM") == "1":
        return None

    dashscope_key = os.getenv("DASHSCOPE_API_KEY")
    if dashscope_key:
        model = os.getenv("DASHSCOPE_MODEL", "qwen-plus")
        try:
            response = _post_json(
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                dashscope_key,
                _chat_payload(query, city, model),
            )
            content = response["choices"][0]["message"]["content"]
            return _extract_json(content)
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            KeyError,
            json.JSONDecodeError,
        ):
            return None

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        try:
            response = _post_json(
                "https://api.openai.com/v1/chat/completions",
                openai_key,
                _chat_payload(query, city, model),
            )
            content = response["choices"][0]["message"]["content"]
            return _extract_json(content)
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            KeyError,
            json.JSONDecodeError,
        ):
            return None

    return None


def parse_intent_with_llm(query: str, city: str | None = None) -> Optional[schemas.ParsedIntent]:
    load_local_env()
    payload = _call_chat_completion(query or "", city)
    if not isinstance(payload, dict):
        return None

    try:
        draft = schemas.LLMIntentDraft(**payload)
    except Exception:
        return None

    return intent_parser.normalize_llm_intent(draft, query or "")
