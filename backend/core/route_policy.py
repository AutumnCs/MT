"""Centralized route-planning policy knobs.

Keep the project tunable by putting semantic thresholds, role rules and
planner weights in one place. These values are intentionally data-friendly:
they can be calibrated against the offline eval set without touching code.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = ROOT / "route_policy.json"

CATEGORY_TARGETS = {
    "food",
    "coffee",
    "museum",
    "exhibition",
    "night",
    "street",
    "park",
    "shopping",
    "library",
    "scene",
}

EXPERIENCE_CATEGORIES = {"scene", "museum", "exhibition", "park", "street", "night", "shopping", "library"}
SUPPORT_CATEGORIES = {"food", "coffee"}

DEFAULT_POLICY: dict[str, Any] = {
    "intent_confidence": {
        "city_bonus": 0.16,
        "required_category_bonus": 0.08,
        "preference_bonus": 0.07,
        "avoid_bonus": 0.09,
        "budget_bonus": 0.07,
        "time_bonus": 0.07,
        "start_location_bonus": 0.06,
        "pace_bonus": 0.06,
        "must_include_bonus": 0.08,
        "current_route_bonus": 0.12,
        "mixed_signal_bonus": 0.08,
        "multi_category_bonus": 0.05,
        "unclassified_penalty": 0.04,
        "long_query_penalty": 0.12,
    },
    "fast_gate_threshold": {
        "default": 0.56,
        "modify": 0.54,
    },
    "role": {
        "primary_min_strength": 0.45,
        "primary_min_count_with_support": 2,
        "support_cap": 1,
        "secondary_support_cap": 1,
        "primary_priority": [
            "scene",
            "museum",
            "exhibition",
            "night",
            "street",
            "park",
            "shopping",
            "library",
            "food",
            "coffee"
        ],
    },
    "planner": {
        "beam_size": 6,
        "beam_candidate_limit": 24,
        "distance_matrix_top_k": 28,
        "cluster_bonus": 0.08,
        "cluster_match": 1.0,
        "cluster_mismatch": 0.55,
        "quota_bonus": 0.18,
        "quota_penalty": 0.45,
        "support_decay": 0.05,
        "quota_miss_penalty": 0.05,
    },
    "retrieval": {
        "semantic_similarity_threshold": 0.46,
        "vector_threshold": 0.025,
        "vector_limit": 90,
        "backend": {
            "lexical_weight": 0.72,
            "dense_weight": 1.0,
            "hash_vector_dim": 384,
            "enable_faiss": True,
            "bm25_k1": 1.5,
            "bm25_b": 0.75,
        },
        "lane_caps": {
            "must_include": 24,
            "category": 72,
            "bm25": 72,
            "text_signal": 56,
            "semantic_similarity": 72,
            "vector": 72,
            "start_location": 18,
        },
        "fallback_min_selected": 40,
        "noise": {
            "max_semantic_term_count_for_low_noise": 6,
            "max_text_signal_share_for_low_noise": 0.55,
            "min_lane_count_for_diversity": 3,
            "max_lane_overlap_ratio_for_low_noise": 0.65,
        },
    },
    "verification": {
        "min_gap_penalty": 0.08,
        "cap_gap_penalty": 0.08,
    },
    "explanation": {
        "max_length": 80,
    },
}


def _deep_update(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_update(dict(result[key]), value)
        else:
            result[key] = value
    return result


def load_route_policy() -> dict[str, Any]:
    path = Path(os.getenv("ROUTE_POLICY_PATH") or DEFAULT_POLICY_PATH)
    if not path.exists():
        return dict(DEFAULT_POLICY)
    try:
        override = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_POLICY)
    if not isinstance(override, dict):
        return dict(DEFAULT_POLICY)
    return _deep_update(dict(DEFAULT_POLICY), override)


ROUTE_POLICY = load_route_policy()
