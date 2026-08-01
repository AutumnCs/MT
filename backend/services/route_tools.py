"""Deterministic tools used by the route-planning workflow."""

from __future__ import annotations

import math
from typing import Any

from agent.tool_layer import ToolRegistry, ToolResult
from core.schemas import ParsedIntent, POI, RouteStop
from services import context_service, map_service, review_analyzer


def _haversine_distance(poi_a: POI, poi_b: POI) -> float:
    lat1 = math.radians(float(getattr(poi_a, "lat", 0.0) or 0.0))
    lat2 = math.radians(float(getattr(poi_b, "lat", 0.0) or 0.0))
    delta_lat = lat2 - lat1
    delta_lng = math.radians(float(getattr(poi_b, "lng", 0.0) or 0.0) - float(getattr(poi_a, "lng", 0.0) or 0.0))
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lng / 2) ** 2
    return 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _local_segment(origin: POI, destination: POI, mode: str) -> dict[str, Any]:
    distance_km = round(_haversine_distance(origin, destination), 2)
    if mode == "walking":
        duration_min = int(round(distance_km * 14))
    elif mode == "metro":
        duration_min = int(round(distance_km * 7 + 12))
    elif mode == "taxi":
        duration_min = int(round(distance_km * 4 + 8))
    else:
        duration_min = int(round(distance_km * 12 if distance_km <= 1.2 else min(distance_km * 7 + 12, distance_km * 4 + 10)))
    return {
        "provider": "local",
        "mode": mode,
        "distance_km": distance_km,
        "duration_min": max(1, duration_min),
        "source": "local_haversine",
        "polyline": [],
    }


def _stops_from_route(planned_route: dict[str, Any]) -> list[RouteStop]:
    return list(planned_route.get("main", []) or [])


def _poi_id(poi: POI) -> str:
    return str(getattr(poi, "id", "") or getattr(poi, "name", "") or "")


def _dump_model(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any, limit: int | None = None) -> list[Any]:
    items = list(value or []) if isinstance(value, (list, tuple, set)) else []
    return items[:limit] if limit is not None else items


def _context_opted_out(intent: ParsedIntent) -> bool:
    query = str(getattr(intent, "original_query", "") or getattr(intent, "modification_query", "") or "").lower()
    opt_out_terms = [
        "\u4e0d\u7528\u53c2\u8003",
        "\u4e0d\u8981\u53c2\u8003",
        "\u4e0d\u7528\u770b\u6211\u4e4b\u524d",
        "\u4e0d\u770b\u6211\u4e4b\u524d",
        "\u5ffd\u7565\u6211\u7684\u504f\u597d",
        "\u4e0d\u53c2\u8003\u6211\u7684\u504f\u597d",
        "ignore my preferences",
        "ignore my history",
        "ignore history",
    ]
    return any(term in query for term in opt_out_terms)


def memory_context_tool(
    *,
    intent: ParsedIntent,
    session_id: str | None = None,
    max_items: int | None = 8,
    phase: str = "pre_plan",
) -> ToolResult:
    """Summarize usable profile/session memory without leaking raw history."""

    resolved_session_id = session_id or getattr(intent, "session_id", None)
    if not resolved_session_id:
        return ToolResult(
            tool="memory_context",
            status="skipped",
            confidence=1.0,
            noise_risk="low",
            used_by=["understanding", "retrieval", "ranking"],
            metadata={"reason": "no_session_id", "phase": phase},
        )

    if _context_opted_out(intent):
        return ToolResult(
            tool="memory_context",
            status="skipped",
            confidence=1.0,
            noise_risk="low",
            used_by=["understanding", "retrieval", "ranking"],
            metadata={"reason": "user_opted_out_of_memory", "session_id": resolved_session_id, "phase": phase},
        )

    limit = max(1, int(max_items or 8))
    projection = context_service.get_memory_projection(str(resolved_session_id), limit=limit)
    session = _dump_model(projection.get("session"))
    profile = _dump_model(projection.get("profile"))
    recent_events = [_dump_model(item) for item in projection.get("recent_events", []) or []]
    route_versions = [_dump_model(item) for item in projection.get("route_versions", []) or []]
    event_types: dict[str, int] = {}
    for event in recent_events:
        event_type = str(event.get("event_type") or "unknown")
        event_types[event_type] = event_types.get(event_type, 0) + 1

    applied_profile_bias = _list(getattr(intent, "profile_bias", []), limit=8)
    applied_context_bias = _list(getattr(intent, "context_bias", []), limit=8)
    confidence = float(projection.get("confidence", 0.0) or 0.0)
    usable_signal_count = int(projection.get("stable_signal_count", 0) or 0) + int(projection.get("recent_signal_count", 0) or 0)
    if usable_signal_count == 0 and not recent_events and not route_versions:
        return ToolResult(
            tool="memory_context",
            status="skipped",
            confidence=0.9,
            noise_risk="low",
            used_by=["understanding", "retrieval", "ranking"],
            metadata={"reason": "no_usable_memory", "session_id": resolved_session_id, "phase": phase},
        )

    return ToolResult(
        tool="memory_context",
        status="ok",
        confidence=round(min(0.92, max(0.35, confidence + 0.1)), 2),
        payload={
            "session_id": resolved_session_id,
            "phase": phase,
            "projection": {
                **projection,
                "event_types": event_types,
                "applied_profile_bias": applied_profile_bias,
                "applied_context_bias": applied_context_bias,
            },
            "session_mode": session.get("mode"),
            "current_route_version_id": session.get("current_route_version_id"),
            "current_route_title": session.get("current_route_title"),
            "current_route_summary": session.get("current_route_summary"),
            "profile_confidence": confidence,
            "stable_signal_count": projection.get("stable_signal_count", 0),
            "recent_signal_count": projection.get("recent_signal_count", 0),
            "recent_event_count": projection.get("recent_event_count", len(recent_events)),
            "memory_strength": projection.get("memory_strength", 0.0),
            "decay_score": projection.get("decay_score", 0.0),
            "staleness_days": projection.get("staleness_days"),
            "home_city": projection.get("home_city"),
            "stable_categories": projection.get("stable_categories", []),
            "stable_preferences": projection.get("stable_preferences", []),
            "stable_avoids": projection.get("stable_avoids", []),
            "recent_categories": projection.get("recent_categories", []),
            "recent_preferences": projection.get("recent_preferences", []),
            "recent_avoids": projection.get("recent_avoids", []),
            "pending_conflicts": projection.get("pending_conflicts", []),
            "preferred_categories": projection.get("preferred_categories", []),
            "preferred_preferences": projection.get("preferred_preferences", []),
            "avoid_preferences": projection.get("avoid_preferences", []),
            "preferred_pace": projection.get("preferred_pace"),
            "preferred_transport_mode": projection.get("preferred_transport_mode"),
            "budget_band": projection.get("budget_band"),
            "route_version_count": projection.get("route_version_count", len(route_versions)),
            "prompt_block": context_service.render_memory_context_block(projection),
        },
        evidence=[
            f"{projection.get('stable_signal_count', 0)} stable profile signals",
            f"{projection.get('recent_event_count', len(recent_events))} recent session events",
            f"{projection.get('route_version_count', len(route_versions))} route versions available",
            f"{len(projection.get('pending_conflicts', []) or [])} pending memory conflicts",
        ],
        noise_risk="medium" if confidence < 0.45 else "low",
        used_by=["understanding", "retrieval", "ranking"],
        metadata={"session_id": resolved_session_id, "phase": phase},
    )


def map_distance_matrix_tool(
    *,
    intent: ParsedIntent,
    planned_route: dict[str, Any],
    mode: str = "walking",
    prefer_external: bool = False,
    max_items: int | None = 8,
    phase: str = "final",
) -> ToolResult:
    """Build a small travel matrix for consecutive route segments."""

    stops = _stops_from_route(planned_route)
    if len(stops) < 2:
        return ToolResult(
            tool="map_distance_matrix",
            status="skipped",
            confidence=1.0,
            noise_risk="low",
            used_by=["planning", "validation", "explanation"],
            metadata={"reason": "route_has_fewer_than_two_stops", "phase": phase},
        )

    segment_limit = max(1, int(max_items or 8) - 1)
    segments: list[dict[str, Any]] = []
    fallback_count = 0
    external_count = 0
    for index, (origin_stop, destination_stop) in enumerate(zip(stops, stops[1:])):
        if index >= segment_limit:
            break
        origin = origin_stop.poi
        destination = destination_stop.poi
        segment: dict[str, Any]
        if prefer_external:
            estimate = map_service.estimate_travel_between_pois(origin, destination, mode=mode)
            segment = dict(estimate.get("data", {}) or {})
            if segment.get("source") == "tdt_drive" or segment.get("provider") == "tdt":
                external_count += 1
            else:
                fallback_count += 1
        else:
            segment = _local_segment(origin, destination, mode)
            fallback_count += 1
        segment.update(
            {
                "from_poi_id": _poi_id(origin),
                "to_poi_id": _poi_id(destination),
                "from_name": getattr(origin, "name", ""),
                "to_name": getattr(destination, "name", ""),
                "index": index,
            }
        )
        segments.append(segment)

    total_distance = round(sum(float(item.get("distance_km", 0.0) or 0.0) for item in segments), 2)
    total_duration = int(sum(int(item.get("duration_min", 0) or 0) for item in segments))
    provider = "tdt" if external_count else "local"
    status = "ok" if external_count else "fallback"
    return ToolResult(
        tool="map_distance_matrix",
        status=status,
        confidence=0.9 if external_count else 0.72,
        payload={
            "mode": mode,
            "provider": provider,
            "phase": phase,
            "segment_count": len(segments),
            "segments": segments,
            "total_distance_km": total_distance,
            "total_duration_min": total_duration,
        },
        evidence=[
            f"{len(segments)} consecutive route segments calibrated",
            "external map route used" if external_count else "local fallback distance used",
        ],
        noise_risk="low",
        used_by=["planning", "validation", "explanation"],
        fallback_used=fallback_count > 0,
        metadata={
            "city": getattr(intent, "city", None),
            "prefer_external": prefer_external,
            "fallback_segments": fallback_count,
            "external_segments": external_count,
        },
    )


_UGC_ASPECTS = (
    "queue_risk",
    "crowd_risk",
    "quiet",
    "photo",
    "food",
    "culture",
    "local_feature",
    "rainy_day",
)


def _ugc_warnings(signals: dict[str, float]) -> list[str]:
    warnings: list[str] = []
    if signals.get("queue_risk", 0.0) >= 0.72:
        warnings.append("queue_risk_high")
    if signals.get("crowd_risk", 0.0) >= 0.72:
        warnings.append("crowd_risk_high")
    if signals.get("quiet", 1.0) <= 0.32:
        warnings.append("quiet_signal_low")
    return warnings


def _ugc_evidence_keywords(poi: POI, limit: int = 5) -> list[str]:
    keywords = _list(getattr(poi, "review_keywords", []) or [], limit=limit)
    if keywords:
        return [str(item) for item in keywords]
    tags = _list(getattr(poi, "tags", []) or [], limit=limit)
    return [str(item) for item in tags]


def _ugc_explanation_hints(
    aspect_summary: dict[str, float],
    warning_counts: dict[str, int],
    analyzed_count: int,
) -> list[str]:
    hints: list[str] = []
    if float(aspect_summary.get("quiet", 0.0) or 0.0) >= 0.68:
        hints.append("整体偏安静，适合放松型路线。")
    if float(aspect_summary.get("photo", 0.0) or 0.0) >= 0.68:
        hints.append("拍照相关信号较强，适合打卡或出片。")
    if float(aspect_summary.get("local_feature", 0.0) or 0.0) >= 0.68:
        hints.append("本地特色信号较强，路线城市感更明确。")
    if float(aspect_summary.get("food", 0.0) or 0.0) >= 0.68:
        hints.append("餐饮体验信号较强，吃饭相关站点更稳。")
    if int(warning_counts.get("queue_risk_high", 0) or 0) >= max(1, analyzed_count // 2):
        hints.append("多站点存在排队风险，建议预留缓冲时间。")
    if int(warning_counts.get("crowd_risk_high", 0) or 0) >= max(1, analyzed_count // 2):
        hints.append("多站点存在拥挤风险，高峰时段体验可能下降。")
    return hints[:3]


def ugc_signal_tool(
    *,
    intent: ParsedIntent,
    planned_route: dict[str, Any],
    max_items: int | None = 8,
    phase: str = "final",
) -> ToolResult:
    """Extract compact UGC-derived signals for selected route stops."""

    stops = _stops_from_route(planned_route)
    if not stops:
        return ToolResult(
            tool="ugc_signal",
            status="skipped",
            confidence=1.0,
            noise_risk="low",
            used_by=["validation", "explanation"],
            metadata={"reason": "route_has_no_stops", "phase": phase},
        )

    limit = max(1, int(max_items or 8))
    items: list[dict[str, Any]] = []
    aggregate: dict[str, list[float]] = {aspect: [] for aspect in _UGC_ASPECTS}
    explicit_signal_count = 0
    for stop in stops[:limit]:
        poi = stop.poi
        raw_signals = getattr(poi, "review_signals", None) or {}
        if isinstance(raw_signals, dict):
            explicit_signal_count += len([key for key in _UGC_ASPECTS if key in raw_signals])
        signals = {aspect: round(float(review_analyzer.signal(poi, aspect)), 2) for aspect in _UGC_ASPECTS}
        for aspect, value in signals.items():
            aggregate[aspect].append(value)
        items.append(
            {
                "poi_id": _poi_id(poi),
                "name": getattr(poi, "name", ""),
                "category": getattr(poi, "category", None),
                "signals": signals,
                "warnings": _ugc_warnings(signals),
                "evidence_keywords": _ugc_evidence_keywords(poi),
                "has_ugc_summary": bool(getattr(poi, "ugc_summary", None)),
            }
        )

    aspect_summary = {
        aspect: round(sum(values) / len(values), 2)
        for aspect, values in aggregate.items()
        if values
    }
    warning_counts: dict[str, int] = {}
    total_warning_count = 0
    for item in items:
        for warning in item.get("warnings", []) or []:
            warning_counts[warning] = warning_counts.get(warning, 0) + 1
            total_warning_count += 1

    confidence = 0.9 if explicit_signal_count >= len(items) * len(_UGC_ASPECTS) else 0.78 if explicit_signal_count else 0.58
    warning_ratio = total_warning_count / max(len(items), 1)
    if explicit_signal_count == 0:
        noise_risk = "high"
    elif warning_ratio <= 0.35:
        noise_risk = "low"
    elif warning_ratio <= 0.7:
        noise_risk = "medium"
    else:
        noise_risk = "high"
    signal_quality = round(max(0.0, min(1.0, confidence - warning_ratio * 0.1)), 2)
    keyword_fallback_count = max(0, len(items) * len(_UGC_ASPECTS) - explicit_signal_count)
    explanation_hints = _ugc_explanation_hints(aspect_summary, warning_counts, len(items))
    return ToolResult(
        tool="ugc_signal",
        status="ok",
        confidence=confidence,
        payload={
            "phase": phase,
            "poi_count": len(stops),
            "analyzed_count": len(items),
            "aspect_summary": aspect_summary,
            "warning_counts": warning_counts,
            "warning_ratio": round(warning_ratio, 2),
            "explanation_hints": explanation_hints,
            "keyword_fallback_count": keyword_fallback_count,
            "items": items,
            "explicit_signal_count": explicit_signal_count,
            "signal_quality": signal_quality,
        },
        evidence=[
            f"{len(items)} selected route stops analyzed",
            "structured review_signals used" if explicit_signal_count else "keyword fallback used",
        ],
        noise_risk=noise_risk,
        used_by=["validation", "explanation"],
        fallback_used=explicit_signal_count == 0,
        metadata={
            "city": getattr(intent, "city", None),
            "phase": phase,
            "aspects": list(_UGC_ASPECTS),
        },
    )


def _crowd_level_score(value: Any) -> float:
    text = str(value or "").strip().lower()
    if text in {"low", "quiet", "small", "few"}:
        return 0.25
    if text in {"high", "crowded", "busy", "hot"}:
        return 0.85
    if text in {"medium", "normal", "moderate"}:
        return 0.55
    try:
        return max(0.0, min(1.0, float(value) / 5.0))
    except (TypeError, ValueError):
        return 0.55


def _heat_item(stop: RouteStop) -> dict[str, Any]:
    poi = stop.poi
    queue_level = int(getattr(poi, "queue_level", 3) or 3)
    queue_score = max(0.0, min(1.0, queue_level / 5.0))
    crowd_score = _crowd_level_score(getattr(poi, "crowd_level", "medium"))
    ugc_queue = float(review_analyzer.signal(poi, "queue_risk", queue_score))
    ugc_crowd = float(review_analyzer.signal(poi, "crowd_risk", crowd_score))
    heat_score = round(max(queue_score, crowd_score, ugc_queue, ugc_crowd), 2)
    risks: list[str] = []
    if queue_score >= 0.72 or ugc_queue >= 0.72:
        risks.append("queue_risk_high")
    if crowd_score >= 0.72 or ugc_crowd >= 0.72:
        risks.append("crowd_risk_high")
    return {
        "poi_id": _poi_id(poi),
        "name": getattr(poi, "name", ""),
        "category": getattr(poi, "category", None),
        "queue_level": queue_level,
        "crowd_level": getattr(poi, "crowd_level", None),
        "queue_score": round(max(queue_score, ugc_queue), 2),
        "crowd_score": round(max(crowd_score, ugc_crowd), 2),
        "heat_score": heat_score,
        "risks": risks,
    }


def heat_signal_tool(
    *,
    intent: ParsedIntent,
    planned_route: dict[str, Any],
    max_items: int | None = 8,
    phase: str = "final",
) -> ToolResult:
    """Expose queue/crowd pressure as a bounded structured signal."""

    stops = _stops_from_route(planned_route)
    if not stops:
        return ToolResult(
            tool="heat_signal",
            status="skipped",
            confidence=1.0,
            noise_risk="low",
            used_by=["validation", "explanation"],
            metadata={"reason": "route_has_no_stops", "phase": phase},
        )

    limit = max(1, int(max_items or 8))
    items = [_heat_item(stop) for stop in stops[:limit]]
    high_queue_count = sum(1 for item in items if "queue_risk_high" in item.get("risks", []))
    high_crowd_count = sum(1 for item in items if "crowd_risk_high" in item.get("risks", []))
    max_heat_score = max((float(item.get("heat_score", 0.0) or 0.0) for item in items), default=0.0)
    average_heat_score = round(
        sum(float(item.get("heat_score", 0.0) or 0.0) for item in items) / max(len(items), 1),
        2,
    )
    constraint_sensitive = bool(
        getattr(intent, "avoid_queue", False)
        or getattr(intent, "avoid_crowded", False)
        or getattr(intent, "prefer_quiet", False)
        or "quiet" in set(getattr(intent, "preferences", []) or [])
    )
    status = "ok" if constraint_sensitive or max_heat_score >= 0.72 else "fallback"
    return ToolResult(
        tool="heat_signal",
        status=status,
        confidence=0.72,
        payload={
            "phase": phase,
            "provider": "local_poi_fields",
            "analyzed_count": len(items),
            "high_queue_count": high_queue_count,
            "high_crowd_count": high_crowd_count,
            "max_heat_score": round(max_heat_score, 2),
            "average_heat_score": average_heat_score,
            "items": items,
        },
        evidence=[
            f"{len(items)} selected route stops checked for queue/crowd pressure",
            "local POI queue_level/crowd_level and review signals used",
        ],
        noise_risk="medium",
        used_by=["validation", "explanation"],
        fallback_used=True,
        metadata={
            "city": getattr(intent, "city", None),
            "phase": phase,
            "constraint_sensitive": constraint_sensitive,
        },
    )


def _copy_stop_with_updates(stop: RouteStop, updates: dict[str, Any]) -> RouteStop:
    if hasattr(stop, "model_copy"):
        return stop.model_copy(update=updates)
    copied = RouteStop(**stop.model_dump()) if hasattr(stop, "model_dump") else stop
    for key, value in updates.items():
        setattr(copied, key, value)
    return copied


def apply_distance_matrix(planned_route: dict[str, Any], result: ToolResult) -> dict[str, Any]:
    """Apply consecutive segment estimates back onto the main route stops."""

    if result.tool != "map_distance_matrix" or result.status not in {"ok", "fallback"}:
        return planned_route
    segments = list((result.payload or {}).get("segments", []) or [])
    if not segments:
        return planned_route
    stops = _stops_from_route(planned_route)
    if not stops:
        return planned_route
    by_index = {int(item.get("index", -1)): item for item in segments}
    updated_stops: list[RouteStop] = []
    for index, stop in enumerate(stops):
        segment = by_index.get(index)
        if segment is None:
            updated_stops.append(stop)
            continue
        updates = {
            "travel_to_next_min": int(segment.get("duration_min", 0) or 0),
            "travel_to_next_km": float(segment.get("distance_km", 0.0) or 0.0),
            "transport_to_next": {
                "mode": segment.get("mode") or result.payload.get("mode"),
                "provider": segment.get("provider") or result.payload.get("provider"),
                "duration_min": int(segment.get("duration_min", 0) or 0),
                "distance_km": float(segment.get("distance_km", 0.0) or 0.0),
                "source": segment.get("source"),
            },
        }
        updated_stops.append(_copy_stop_with_updates(stop, updates))

    updated = dict(planned_route)
    updated["main"] = updated_stops
    updated["selected_poi_ids"] = [stop.poi.id for stop in updated_stops]
    updated["stats"] = {
        **dict(updated.get("stats", {}) or {}),
        "total_travel_min": int(sum(int(getattr(stop, "travel_to_next_min", 0) or 0) for stop in updated_stops)),
        "total_km": round(float(sum(float(getattr(stop, "travel_to_next_km", 0.0) or 0.0) for stop in updated_stops)), 2),
    }
    updated.setdefault("tool_enrichment", {})
    updated["tool_enrichment"]["map_distance_matrix"] = result.model_dump(mode="json")
    return updated


def apply_ugc_signals(planned_route: dict[str, Any], result: ToolResult) -> dict[str, Any]:
    """Attach compact UGC observations to route-level enrichment."""

    if result.tool != "ugc_signal" or result.status != "ok":
        return planned_route
    updated = dict(planned_route)
    updated.setdefault("tool_enrichment", {})
    updated["tool_enrichment"]["ugc_signal"] = result.model_dump(mode="json")
    updated["ugc_signal_summary"] = {
        "aspect_summary": (result.payload or {}).get("aspect_summary", {}),
        "warning_counts": (result.payload or {}).get("warning_counts", {}),
        "analyzed_count": (result.payload or {}).get("analyzed_count", 0),
        "explicit_signal_count": (result.payload or {}).get("explicit_signal_count", 0),
        "keyword_fallback_count": (result.payload or {}).get("keyword_fallback_count", 0),
        "confidence": result.confidence,
        "noise_risk": result.noise_risk,
        "signal_quality": (result.payload or {}).get("signal_quality", 0.0),
        "warning_ratio": (result.payload or {}).get("warning_ratio", 0.0),
        "explanation_hints": (result.payload or {}).get("explanation_hints", []),
    }
    return updated


def apply_heat_signals(planned_route: dict[str, Any], result: ToolResult) -> dict[str, Any]:
    """Attach compact heat observations to route-level enrichment."""

    if result.tool != "heat_signal" or result.status not in {"ok", "fallback"}:
        return planned_route
    updated = dict(planned_route)
    updated.setdefault("tool_enrichment", {})
    updated["tool_enrichment"]["heat_signal"] = result.model_dump(mode="json")
    updated["heat_signal_summary"] = {
        "provider": (result.payload or {}).get("provider"),
        "analyzed_count": (result.payload or {}).get("analyzed_count", 0),
        "high_queue_count": (result.payload or {}).get("high_queue_count", 0),
        "high_crowd_count": (result.payload or {}).get("high_crowd_count", 0),
        "max_heat_score": (result.payload or {}).get("max_heat_score", 0.0),
        "average_heat_score": (result.payload or {}).get("average_heat_score", 0.0),
    }
    return updated


ROUTE_TOOL_REGISTRY = ToolRegistry()
ROUTE_TOOL_REGISTRY.register("memory_context", memory_context_tool)
ROUTE_TOOL_REGISTRY.register("map_distance_matrix", map_distance_matrix_tool)
ROUTE_TOOL_REGISTRY.register("ugc_signal", ugc_signal_tool)
ROUTE_TOOL_REGISTRY.register("heat_signal", heat_signal_tool)
