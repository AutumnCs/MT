"""Shared lightweight text normalization and Chinese tokenization helpers."""

from __future__ import annotations

import re

try:
    import jieba  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    jieba = None


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+", re.UNICODE)
_CJK_RE = re.compile(r"[\u4e00-\u9fff]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")
_CLEAN_RE = re.compile(r"[\s\W_]+", re.UNICODE)


def normalize_compact(text: str) -> str:
    return _CLEAN_RE.sub("", (text or "").lower())


def basic_tokens(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text or "") if token]


def segmented_tokens(text: str) -> list[str]:
    raw = str(text or "").strip().lower()
    if not raw:
        return []
    if jieba is None or not _CJK_RE.search(raw):
        return basic_tokens(raw)
    pieces: list[str] = []
    for part in jieba.lcut(raw, cut_all=False):
        token = _SPACE_RE.sub("", part).strip()
        if not token:
            continue
        if len(token) == 1 and _CJK_RE.search(token):
            pieces.append(token)
            continue
        pieces.append(token)
    if not pieces:
        return basic_tokens(raw)
    deduped: list[str] = []
    for token in pieces:
        if token not in deduped:
            deduped.append(token)
    return deduped


def token_set(text: str) -> set[str]:
    return set(segmented_tokens(text))
