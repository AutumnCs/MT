"""Semantic intent helpers for long-tail user language.

This module provides a lightweight semantic bridge between free-form user
language and the project's structured intent schema. It intentionally avoids
heavy dependencies so the system stays easy to run locally while still being
more robust than a pure keyword matcher.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from core.semantic_ontology import (
    SemanticProfile,
    expand_canonical_targets,
    load_semantic_profiles,
    profiles_by_kind,
    prompt_semantic_ontology_excerpt,
)
from core.text_tokenizer import normalize_compact, token_set


_CATEGORY_PROFILES: list[SemanticProfile] = list(profiles_by_kind("category"))
_PREFERENCE_PROFILES: list[SemanticProfile] = list(profiles_by_kind("preference"))
_AVOID_PROFILES: list[SemanticProfile] = list(profiles_by_kind("avoid"))
_ALL_PROFILES = list(load_semantic_profiles())

_PREFERENCE_FLAG_MAP = {
    "couple": "prefer_couple",
    "photo": "prefer_photo",
    "food": "prefer_food",
    "culture": "prefer_culture",
    "local_feature": "prefer_local_feature",
    "night_view": "prefer_night_view",
    "quiet": "prefer_quiet",
    "rainy_day": "prefer_rainy_day",
    "walking": "prefer_walking",
    "family": "prefer_family",
    "friends": "prefer_friends",
    "solo": "prefer_solo",
    "value": "prefer_value",
    "premium": "prefer_premium",
    "indoor": "prefer_indoor",
    "outdoor": "prefer_outdoor",
    "citywalk": "prefer_citywalk",
    "efficient": "prefer_efficient",
    "compact": "prefer_compact",
}

_AVOID_FLAG_MAP = {
    "avoid_spicy": "avoid_spicy",
    "avoid_far": "avoid_far",
    "avoid_queue": "avoid_queue",
    "avoid_crowded": "avoid_crowded",
}

_VALUE_NEGATION_MARKERS = (
    "不要便宜",
    "别便宜",
    "不想便宜",
    "不要太便宜",
    "不要给我太便宜",
    "不要便宜路线",
    "别给我便宜",
    "不走便宜",
    "不要省钱",
    "不省钱",
)


def _normalize_text(text: str) -> str:
    return normalize_compact(text)


def _tokenize(text: str) -> set[str]:
    return token_set(text)


def _ngrams(text: str, size: int = 2) -> set[str]:
    normalized = _normalize_text(text)
    if len(normalized) <= size:
        return {normalized} if normalized else set()
    return {normalized[index : index + size] for index in range(len(normalized) - size + 1)}


def _profile_surface(profile: SemanticProfile) -> str:
    return " ".join([profile.label, profile.description, *profile.aliases])


def _keyword_hit_score(query: str, aliases: tuple[str, ...]) -> float:
    if not query or not aliases:
        return 0.0
    normalized_query = _normalize_text(query)
    best = 0.0
    for alias in aliases:
        alias_text = _normalize_text(alias)
        if not alias_text:
            continue
        if alias_text in normalized_query:
            return 1.0
        if normalized_query in alias_text:
            best = max(best, 0.82)
    return best


def _has_value_negation(query: str) -> bool:
    normalized = _normalize_text(query)
    return any(_normalize_text(marker) in normalized for marker in _VALUE_NEGATION_MARKERS)


def semantic_similarity(query: str, anchor: str) -> float:
    """Return a lightweight semantic similarity score in [0, 1]."""

    query = (query or "").strip()
    anchor = (anchor or "").strip()
    if not query or not anchor:
        return 0.0

    normalized_query = _normalize_text(query)
    normalized_anchor = _normalize_text(anchor)
    if not normalized_query or not normalized_anchor:
        return 0.0

    if normalized_query in normalized_anchor or normalized_anchor in normalized_query:
        return 1.0

    query_tokens = _tokenize(query)
    anchor_tokens = _tokenize(anchor)
    token_union = len(query_tokens | anchor_tokens) or 1
    token_score = len(query_tokens & anchor_tokens) / token_union

    query_grams = _ngrams(query, 2)
    anchor_grams = _ngrams(anchor, 2)
    gram_union = len(query_grams | anchor_grams) or 1
    gram_score = len(query_grams & anchor_grams) / gram_union

    return max(0.0, min(1.0, 0.28 * token_score + 0.72 * gram_score))


def _profile_score(query: str, profile: SemanticProfile) -> float:
    surface = " ".join([profile.label, *profile.aliases])
    alias_score = _keyword_hit_score(query, profile.aliases)
    semantic_score = semantic_similarity(query, surface)
    return max(alias_score, semantic_score) + profile.boost


@lru_cache(maxsize=256)
def infer_semantic_hints(query: str, limit: int = 6) -> tuple[dict[str, Any], ...]:
    """Infer long-tail semantic hints for a query."""

    text = (query or "").strip()
    if not text:
        return tuple()

    scored = []
    value_negated = _has_value_negation(text)
    for profile in _ALL_PROFILES:
        if value_negated and profile.kind == "preference" and profile.target == "value":
            continue
        score = _profile_score(text, profile)
        if score <= 0.0:
            continue
        scored.append(
            {
                "kind": profile.kind,
                "target": profile.target,
                "label": profile.label,
                "score": round(min(score, 1.0), 3),
                "surface": _profile_surface(profile),
            }
        )

    scored.sort(key=lambda item: (-item["score"], item["kind"], item["target"]))
    return tuple(scored[:limit])


def build_semantic_query_surface(intent: Any, query: str = "") -> str:
    """Create a richer query surface for retrieval and reranking."""

    pieces: list[str] = [query or ""]
    for attr in ("city", "start_location", "notes"):
        value = getattr(intent, attr, None)
        if value:
            pieces.append(str(value))

    list_fields = (
        "required_categories",
        "preferred_categories",
        "preferences",
        "party_types",
        "avoid",
        "must_include",
        "unclassified_clues",
        "intent_tags",
    )
    for field_name in list_fields:
        values = getattr(intent, field_name, []) or []
        if values:
            pieces.append(" ".join(str(item) for item in values if item))

    pieces.extend(expand_canonical_targets("category", list(getattr(intent, "required_categories", []) or [])))
    pieces.extend(expand_canonical_targets("category", list(getattr(intent, "preferred_categories", []) or [])))
    pieces.extend(expand_canonical_targets("preference", list(getattr(intent, "preferences", []) or [])))
    pieces.extend(expand_canonical_targets("avoid", list(getattr(intent, "avoid", []) or [])))

    for profile in infer_semantic_hints(query or getattr(intent, "original_query", "") or ""):
        pieces.append(f"{profile['kind']}:{profile['target']}:{profile['label']}")

    return " ".join(piece for piece in pieces if piece).strip()


def prompt_semantic_profile_excerpt() -> str:
    """Return compact canonical semantic dimensions for LLM scoring prompts."""
    return prompt_semantic_ontology_excerpt()


def apply_semantic_hints(intent: Any, query: str) -> Any:
    """Mutate an intent in-place using semantic hints without overriding explicit user input."""

    text = (query or "").strip()
    if not text or intent is None:
        return intent

    # Keep a wider semantic window here so competing intent signals
    # like "景点" vs "公园" are both available to downstream role ranking.
    hints = list(infer_semantic_hints(text, limit=50))
    if not hints:
        return intent

    categories = list(getattr(intent, "required_categories", []) or [])
    preferences = list(getattr(intent, "preferences", []) or [])
    avoid = list(getattr(intent, "avoid", []) or [])
    semantic_hints = list(getattr(intent, "semantic_hints", []) or [])
    semantic_scores = dict(getattr(intent, "semantic_scores", {}) or {})
    semantic_evidence = dict(getattr(intent, "semantic_evidence", {}) or {})

    def _append_unique(values: list[str], value: str) -> bool:
        if value in values:
            return False
        values.append(value)
        return True

    for hint in hints:
        target = str(hint["target"])
        kind = str(hint["kind"])
        score = float(hint["score"])
        if kind == "category" and score >= 0.55:
            _append_unique(categories, target)
        elif kind == "preference" and score >= 0.50:
            _append_unique(preferences, target)
        elif kind == "avoid" and score >= 0.55:
            _append_unique(avoid, target)
        if score > semantic_scores.get(target, 0.0):
            semantic_scores[target] = round(score, 3)
            semantic_evidence[target] = str(hint.get("label") or hint.get("surface") or target)

    if _has_value_negation(text):
        preferences = [item for item in preferences if item != "value"]

    if any(item["target"] == "quiet" and item["score"] >= 0.7 for item in hints):
        if getattr(intent, "pace", "normal") == "normal":
            intent.pace = "slow"
    if any(item["target"] == "efficient" and item["score"] >= 0.7 for item in hints):
        if getattr(intent, "pace", "normal") == "normal":
            intent.pace = "fast"

    intent.required_categories = list(dict.fromkeys(categories))
    intent.preferences = list(dict.fromkeys(preferences))
    intent.avoid = list(dict.fromkeys(avoid))
    party_types = [item for item in ("couple", "family", "friends", "solo") if item in intent.preferences]
    intent.party_types = list(dict.fromkeys([*(getattr(intent, "party_types", []) or []), *party_types]))
    if not getattr(intent, "primary_party_type", None) and intent.party_types:
        intent.primary_party_type = str(intent.party_types[0])
    intent.semantic_scores = dict(sorted(semantic_scores.items(), key=lambda item: (-item[1], item[0])))
    intent.semantic_evidence = semantic_evidence
    semantic_hints.extend(hints)
    intent.semantic_hints = list(dict.fromkeys(tuple(f"{item['kind']}:{item['target']}" for item in semantic_hints)))

    for target, attr_name in _PREFERENCE_FLAG_MAP.items():
        setattr(intent, attr_name, target in intent.preferences)
    for target, attr_name in _AVOID_FLAG_MAP.items():
        setattr(intent, attr_name, target in intent.avoid)

    intent.soft_preferences = list(dict.fromkeys([*(getattr(intent, "soft_preferences", []) or []), *intent.preferences]))
    intent.preferred_categories = list(
        dict.fromkeys([*(getattr(intent, "preferred_categories", []) or []), *intent.required_categories])
    )
    intent.intent_tags = list(
        dict.fromkeys(
            [
                *(getattr(intent, "intent_tags", []) or []),
                *intent.required_categories,
                *intent.preferences,
                *intent.avoid,
                *intent.semantic_hints,
            ]
        )
    )
    intent.recognized_signals = list(
        dict.fromkeys([*(getattr(intent, "recognized_signals", []) or []), *intent.intent_tags, *intent.semantic_hints])
    )
    return intent
