"""Helpers for extracting route context from serialized route payloads."""

from __future__ import annotations

from typing import Any, Optional

from core.intent_lexicon import INTENT_LEXICON


CITY_ALIASES: dict[str, list[str]] = {
    "广州": list(INTENT_LEXICON.get("city_guangzhou", []) or []),
    "上海": list(INTENT_LEXICON.get("city_shanghai", []) or []),
}


def infer_city_from_route(current_route: Any) -> Optional[str]:
    if not current_route:
        return None

    chunks: list[str] = []
    if isinstance(current_route, dict):
        for key in ("city", "title", "summary", "explanation", "route_explanation", "original_query"):
            value = current_route.get(key)
            if isinstance(value, str) and value.strip():
                chunks.append(value.strip())
        for stop in current_route.get("stops", []) or []:
            if isinstance(stop, dict):
                poi = stop.get("poi", {})
                if isinstance(poi, dict):
                    for key in ("city", "name", "district", "address"):
                        value = poi.get(key)
                        if isinstance(value, str) and value.strip():
                            chunks.append(value.strip())
    else:
        chunks.append(str(current_route))

    combined = " ".join(chunks)
    for city, aliases in CITY_ALIASES.items():
        if city in combined:
            return city
        if any(alias and alias in combined for alias in aliases):
            return city
    return None
