"""Canonical semantic ontology for intent understanding.

This module merges the structured lexicon files into one runtime ontology so
intent parsing, semantic hinting, prompting, and retrieval all read the same
canonical tags.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LEXICON_DIR = ROOT / "lexicon"


@dataclass(frozen=True)
class SemanticProfile:
    kind: str
    target: str
    label: str
    aliases: tuple[str, ...]
    description: str
    boost: float = 0.0


_PROFILE_META: dict[tuple[str, str], dict[str, Any]] = {
    ("category", "food"): {"description": "eat, meal, local food, restaurant, snack", "boost": 0.15},
    ("category", "coffee"): {"description": "coffee, tea, dessert, afternoon break", "boost": 0.12},
    ("category", "museum"): {"description": "museum, history, exhibition hall, science", "boost": 0.10},
    ("category", "exhibition"): {"description": "gallery, art show, exhibition, museum-like indoor visit", "boost": 0.10},
    ("category", "night"): {"description": "night view, lights, skyline, river view", "boost": 0.10},
    ("category", "street"): {"description": "citywalk, strolling, small shops, walkable district", "boost": 0.12},
    ("category", "park"): {"description": "park, green space, outdoor walk, riverside", "boost": 0.08},
    ("category", "shopping"): {"description": "mall, shopping, retail district", "boost": 0.08},
    ("category", "library"): {"description": "library, reading, study, quiet indoor stay", "boost": 0.08},
    ("category", "scene"): {"description": "landmark, sightseeing, scenic stop, photo stop", "boost": 0.08},
    ("preference", "couple"): {"description": "date, romance, atmosphere, couple-friendly", "boost": 0.10},
    ("preference", "photo"): {"description": "photo, check-in, stylish, visual", "boost": 0.10},
    ("preference", "food"): {"description": "food-first, delicious, meal-oriented", "boost": 0.10},
    ("preference", "culture"): {"description": "culture, history, museum, art", "boost": 0.10},
    ("preference", "local_feature"): {"description": "local flavor, city character, authentic, less commercial", "boost": 0.12},
    ("preference", "night_view"): {"description": "night scene, evening vibe, skyline", "boost": 0.10},
    ("preference", "quiet"): {"description": "quiet, relaxed, less crowded, calm", "boost": 0.14},
    ("preference", "rainy_day"): {"description": "rainy day, indoor, weather-safe", "boost": 0.12},
    ("preference", "walking"): {"description": "walking, strolling, low-friction movement", "boost": 0.12},
    ("preference", "family"): {"description": "family, kids, parent-child", "boost": 0.10},
    ("preference", "coffee"): {"description": "coffee break, sitting, recharge", "boost": 0.08},
    ("preference", "friends"): {"description": "friends, hangout, casual social plan", "boost": 0.08},
    ("preference", "solo"): {"description": "solo, one-person, self-paced", "boost": 0.08},
    ("preference", "value"): {"description": "budget-friendly, value-for-money, affordable", "boost": 0.12},
    ("preference", "premium"): {"description": "premium, high-quality, refined, polished", "boost": 0.14},
    ("preference", "indoor"): {"description": "indoor-first, weather-safe, venue-heavy", "boost": 0.10},
    ("preference", "outdoor"): {"description": "outdoor, open-air, outside", "boost": 0.08},
    ("preference", "shopping"): {"description": "shopping-oriented, malls, browsing stores", "boost": 0.08},
    ("preference", "citywalk"): {"description": "citywalk, neighborhood wandering, casual exploration", "boost": 0.12},
    ("preference", "efficient"): {"description": "efficient, fast, less detour, time-saving", "boost": 0.10},
    ("preference", "compact"): {"description": "compact, sequential, low-transfer route", "boost": 0.10},
    ("preference", "relaxed"): {"description": "relaxed, easy pace, low-fatigue route", "boost": 0.12},
    ("avoid", "avoid_spicy"): {"description": "avoid spicy food", "boost": 0.10},
    ("avoid", "avoid_far"): {"description": "avoid long transfer or far distance", "boost": 0.10},
    ("avoid", "avoid_queue"): {"description": "avoid waiting lines", "boost": 0.12},
    ("avoid", "avoid_crowded"): {"description": "avoid crowd pressure or congestion", "boost": 0.10},
}

_FILE_MAP = {
    "category": "categories.json",
    "preference": "preferences.json",
    "avoid": "avoids.json",
}

_ARRAY_KEYS = {
    "category": "categories",
    "preference": "preferences",
    "avoid": "avoids",
}

_AVOID_CANONICAL = {
    "queue": "avoid_queue",
    "crowded": "avoid_crowded",
    "far": "avoid_far",
    "spicy": "avoid_spicy",
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _normalize_target(kind: str, target: str) -> str:
    text = str(target or "").strip()
    if kind == "avoid":
        return _AVOID_CANONICAL.get(text, text)
    return text


@lru_cache(maxsize=1)
def load_semantic_profiles() -> tuple[SemanticProfile, ...]:
    profiles: list[SemanticProfile] = []
    for kind, filename in _FILE_MAP.items():
        payload = _load_json(LEXICON_DIR / filename)
        for item in payload.get(_ARRAY_KEYS[kind], []) or []:
            target = _normalize_target(kind, item.get("tag"))
            if not target:
                continue
            label = str(item.get("label") or target).strip()
            aliases = tuple(str(alias).strip() for alias in item.get("aliases", []) or [] if str(alias).strip())
            meta = _PROFILE_META.get((kind, target), {})
            description = str(meta.get("description") or label)
            boost = float(meta.get("boost") or 0.0)
            profiles.append(
                SemanticProfile(
                    kind=kind,
                    target=target,
                    label=label,
                    aliases=aliases,
                    description=description,
                    boost=boost,
                )
            )
    profiles.sort(key=lambda item: (item.kind, item.target))
    return tuple(profiles)


def profiles_by_kind(kind: str) -> tuple[SemanticProfile, ...]:
    normalized = str(kind or "").strip()
    return tuple(profile for profile in load_semantic_profiles() if profile.kind == normalized)


@lru_cache(maxsize=1)
def profile_lookup() -> dict[tuple[str, str], SemanticProfile]:
    return {(profile.kind, profile.target): profile for profile in load_semantic_profiles()}


def expand_canonical_targets(kind: str, targets: list[str] | tuple[str, ...]) -> list[str]:
    lookup = profile_lookup()
    expanded: list[str] = []
    for raw_target in targets or []:
        target = _normalize_target(kind, raw_target)
        profile = lookup.get((kind, target))
        if profile is None:
            if target:
                expanded.append(target)
            continue
        expanded.extend(
            [
                profile.target,
                profile.label,
                profile.description,
                *profile.aliases[:8],
            ]
        )
    return [item for item in dict.fromkeys(str(item).strip() for item in expanded if str(item).strip())]


def prompt_semantic_ontology_excerpt() -> str:
    groups = [
        ("category", profiles_by_kind("category")),
        ("preference", profiles_by_kind("preference")),
        ("avoid", profiles_by_kind("avoid")),
    ]
    lines: list[str] = []
    for kind, profiles in groups:
        parts = [
            f"{profile.target}={profile.label}({profile.description})"
            for profile in profiles
        ]
        lines.append(f"{kind}: " + " | ".join(parts))
    return "\n".join(lines)
