"""Centralized tuning knobs for POI ranking.

This module loads optional overrides from ``backend/policy/poi_ranker_weights.json``.
If the file is missing or invalid, the built-in defaults are used.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict


DEFAULT_RANKER_POLICY: Dict[str, Any] = {
    "version": "1.0",
    "final_weights": {
        "preference_match_score": 0.25,
        "semantic_score": 0.20,
        "category_match_score": 0.15,
        "rating_score": 0.15,
        "budget_score": 0.10,
        "time_suitability_score": 0.10,
        "queue_penalty": 0.15,
        "crowd_penalty": 0.10,
        "price_penalty": 0.05,
    },
    "rating": {
        "baseline": 3.8,
        "scale": 1.1,
        "default": 0.5,
    },
    "category_match": {
        "default": 0.6,
        "mismatch": 0.25,
        "perfect": 1.0,
    },
    "budget": {
        "default": 0.7,
        "free": 0.9,
    },
    "preference": {
        "base": 0.4,
        "intent_tag_bonus": 0.12,
        "date_signal_weight": 0.20,
        "photo_signal_weight": 0.18,
        "food_signal_weight": 0.18,
        "culture_signal_weight": 0.18,
        "local_feature_signal_weight": 0.18,
        "rainy_day_signal_weight": 0.12,
        "night_view_weight": 0.15,
        "quiet_signal_weight": 0.10,
        "family_match_bonus": 0.08,
        "family_fallback_bonus": 0.03,
        "friends_match_bonus": 0.04,
        "friends_fallback_bonus": 0.02,
        "solo_bonus": 0.04,
        "value_match_bonus": 0.06,
        "value_fallback_bonus": 0.02,
        "indoor_match_bonus": 0.07,
        "indoor_fallback_bonus": 0.02,
        "outdoor_match_bonus": 0.07,
        "outdoor_fallback_bonus": 0.02,
        "citywalk_match_bonus": 0.05,
        "citywalk_fallback_bonus": 0.02,
        "efficient_match_bonus": 0.04,
        "efficient_fallback_bonus": 0.01,
        "compact_match_bonus": 0.05,
        "compact_fallback_bonus": 0.0,
        "solo_queue_threshold": 3,
        "value_price_threshold": 60,
        "efficient_duration_threshold": 60,
        "compact_duration_threshold": 75,
        "citywalk_categories": ["street", "park", "night", "shopping"],
        "family_terms": ["亲子", "家庭", "孩子", "小朋友"],
        "friends_terms": ["朋友", "闺蜜", "同学", "聚会"],
    },
    "semantic": {
        "default": 0.5,
        "family_match": 0.8,
        "family_fallback": 0.3,
        "friends_match": 0.7,
        "friends_fallback": 0.3,
        "solo_match": 0.7,
        "solo_fallback": 0.4,
        "value_match": 0.8,
        "value_fallback": 0.45,
        "indoor_match": 0.85,
        "indoor_fallback": 0.4,
        "outdoor_match": 0.85,
        "outdoor_fallback": 0.4,
        "citywalk_match": 0.8,
        "citywalk_fallback": 0.35,
        "efficient_match": 0.75,
        "efficient_fallback": 0.4,
        "compact_match": 0.75,
        "compact_fallback": 0.35,
        "night_view_match": 0.9,
    },
    "time": {
        "default": 0.7,
        "night_category": "night",
        "fast_short": 60,
        "fast_medium": 90,
        "fast_scores": {"short": 1.0, "medium": 0.7, "long": 0.4},
        "slow_min_duration": 45,
        "slow_score": 0.8,
        "slow_fallback_score": 0.6,
    },
    "penalty": {
        "queue_multiplier": 1.0,
        "queue_avoid_multiplier": 1.5,
        "crowd_multiplier": 1.0,
        "crowd_avoid_multiplier": 1.3,
        "price_threshold_multiplier": 1.5,
        "price_penalty_cap": 0.3,
    },
    "reason": {
        "category_match_threshold": 0.95,
        "budget_match_threshold": 0.85,
        "queue_risk_threshold": 0.7,
    },
}

_POLICY_PATH = Path(__file__).resolve().parents[1] / "policy" / "poi_ranker_weights.json"


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_ranker_policy() -> Dict[str, Any]:
    if not _POLICY_PATH.exists():
        return deepcopy(DEFAULT_RANKER_POLICY)
    try:
        raw = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return deepcopy(DEFAULT_RANKER_POLICY)
        return _deep_merge(DEFAULT_RANKER_POLICY, raw)
    except Exception:
        return deepcopy(DEFAULT_RANKER_POLICY)


RANKER_POLICY = load_ranker_policy()

