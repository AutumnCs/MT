"""Lightweight context and profile persistence for multi-turn route planning."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Optional
from uuid import uuid4

from core.context_models import (
    BehaviorEvent,
    ContextSnapshot,
    RouteVersionRecord,
    SessionContext,
    UserProfile,
)

_STORE_LOCK = Lock()
_STORE_PATH = Path(__file__).resolve().parents[2] / ".tmp" / "context_store.json"
_MAX_EVENTS_PER_SESSION = 80
_MAX_ROUTE_VERSIONS_PER_SESSION = 20
_RECENT_EVIDENCE_WINDOW = 5
_PROFILE_MIN_STABLE_COUNT = 2
_PROFILE_LOW_CONFIDENCE_STABLE_COUNT = 3
_VALID_PACE = {"fast", "normal", "slow"}
_VALID_TRANSPORT = {"walking", "metro", "taxi", "mixed"}


def _empty_store() -> dict[str, Any]:
    return {"sessions": {}}


def _load_store() -> dict[str, Any]:
    if not _STORE_PATH.exists():
        return _empty_store()
    try:
        import json

        data = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("sessions"), dict):
            return data
    except Exception:
        pass
    return _empty_store()


def _save_store(store: dict[str, Any]) -> None:
    import json

    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.write_text(
        json.dumps(store, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _ensure_session_bucket(store: dict[str, Any], session_id: str) -> dict[str, Any]:
    sessions = store.setdefault("sessions", {})
    bucket = sessions.get(session_id)
    if bucket is None:
        bucket = {
            "session": SessionContext(session_id=session_id).model_dump(mode="json"),
            "profile": UserProfile(session_id=session_id).model_dump(mode="json"),
            "events": [],
            "routes": [],
        }
        sessions[session_id] = bucket
        return bucket

    bucket.setdefault("session", SessionContext(session_id=session_id).model_dump(mode="json"))
    bucket.setdefault("profile", UserProfile(session_id=session_id).model_dump(mode="json"))
    bucket.setdefault("events", [])
    bucket.setdefault("routes", [])
    return bucket


def _top_items(counter: dict[str, int], limit: int = 5) -> list[str]:
    return [key for key, _ in Counter(counter).most_common(limit) if key]


def _stable_top_items(counter: dict[str, int], limit: int = 5, min_count: int = 2) -> list[str]:
    return [key for key, value in Counter(counter).most_common() if key and int(value) >= min_count][:limit]


def _parse_timestamp(value: Any) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _unique_preserve(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in values if item))


def _recent_values(entries: list[dict[str, Any]], key: str, limit: int = _RECENT_EVIDENCE_WINDOW) -> list[str]:
    values: list[str] = []
    for item in entries[-limit:]:
        raw_values = item.get(key) or []
        if isinstance(raw_values, list):
            values.extend(str(value).strip() for value in raw_values if str(value).strip())
        else:
            token = str(raw_values or "").strip()
            if token:
                values.append(token)
    return _unique_preserve(values)


def _evidence_confidence(event_type: str) -> float:
    if event_type in {"route_created", "route_modified", "route_favorited", "route_copied"}:
        return 0.95
    if event_type in {"clarification_answered", "preference_selected", "city_changed"}:
        return 0.82
    if event_type in {"route_rejected"}:
        return 0.72
    return 0.6


def _days_since(timestamp: Any) -> int | None:
    seconds = _parse_timestamp(timestamp)
    if seconds <= 0:
        return None
    delta = datetime.now().timestamp() - seconds
    if delta < 0:
        return 0
    return int(delta // 86400)


def _budget_band(budget: Any) -> Optional[str]:
    try:
        value = float(budget)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    if value <= 150:
        return "low"
    if value <= 300:
        return "mid"
    return "high"


def _intent_to_dict(intent: Any) -> dict[str, Any]:
    if intent is None:
        return {}
    if isinstance(intent, dict):
        return dict(intent)
    model_dump = getattr(intent, "model_dump", None)
    if callable(model_dump):
        return dict(model_dump(mode="json"))
    return {}


def _route_to_snapshot(route: Any) -> dict[str, Any]:
    if route is None:
        return {}
    if isinstance(route, dict):
        return dict(route)
    model_dump = getattr(route, "model_dump", None)
    if callable(model_dump):
        data = dict(model_dump(mode="json"))
    else:
        data = {}
    if not data:
        return data
    keys = {
        "request_id",
        "title",
        "summary",
        "city",
        "strategy",
        "generated_at",
        "plans",
        "intent_summary",
        "diagnostics",
        "clarification_needed",
        "clarification_question",
        "clarification_options",
        "clarification_reason",
        "main_stops",
        "stats",
        "covered_types",
        "trace",
        "workflow_trace",
        "route_quality",
        "route_critique",
        "workflow_guard",
    }
    return {key: data.get(key) for key in keys if key in data}


def _update_profile_from_intent(
    profile: dict[str, Any],
    intent_data: dict[str, Any],
    event_type: str,
    *,
    created_at: str,
    session_id: str,
) -> None:
    city = intent_data.get("city")
    if isinstance(city, str) and city.strip():
        city = city.strip()
        counts = profile.setdefault("city_counts", {})
        counts[city] = int(counts.get(city, 0)) + 1

    for key in ("required_categories", "preferences", "avoid", "must_include"):
        values = intent_data.get(key) or []
        if not isinstance(values, list):
            continue
        counts_key = "preference_counts" if key in {"preferences", "must_include"} else "category_counts" if key == "required_categories" else "avoid_counts"
        counts = profile.setdefault(counts_key, {})
        for item in values:
            token = str(item or "").strip()
            if not token:
                continue
            counts[token] = int(counts.get(token, 0)) + 1

    pace = intent_data.get("pace")
    if isinstance(pace, str) and pace in {"fast", "slow"}:
        behavior_counts = profile.setdefault("behavior_counts", {})
        behavior_counts[f"pace:{pace}"] = int(behavior_counts.get(f"pace:{pace}", 0)) + 1

    transport = intent_data.get("transport_mode")
    if isinstance(transport, str) and transport in {"walking", "metro", "taxi"}:
        behavior_counts = profile.setdefault("behavior_counts", {})
        behavior_counts[f"transport:{transport}"] = int(behavior_counts.get(f"transport:{transport}", 0)) + 1

    budget = _budget_band(intent_data.get("budget"))
    if budget:
        behavior_counts = profile.setdefault("behavior_counts", {})
        behavior_counts[f"budget:{budget}"] = int(behavior_counts.get(f"budget:{budget}", 0)) + 1

    preferences = intent_data.get("preferences") or []
    if isinstance(preferences, list):
        for item in preferences:
            token = str(item or "").strip()
            if token in {"couple", "family", "friends", "solo"}:
                behavior_counts = profile.setdefault("behavior_counts", {})
                behavior_counts[f"companion:{token}"] = int(behavior_counts.get(f"companion:{token}", 0)) + 1

    evidence = profile.setdefault("evidence", [])
    evidence.append(
        {
            "event_type": event_type,
            "session_id": session_id,
            "created_at": created_at,
            "source": "route_event",
            "confidence": _evidence_confidence(event_type),
            "city": city,
            "required_categories": list(intent_data.get("required_categories") or []),
            "preferences": list(intent_data.get("preferences") or []),
            "avoid": list(intent_data.get("avoid") or []),
            "must_include": list(intent_data.get("must_include") or []),
            "pace": pace,
            "transport_mode": transport,
            "budget_band": budget,
        }
    )
    del evidence[:-30]

    city_counts = profile.get("city_counts", {})
    profile["home_city"] = _top_items(city_counts, 1)[0] if city_counts else profile.get("home_city")
    profile["frequent_cities"] = _top_items(city_counts, 3)
    profile["preferred_categories"] = _top_items(profile.get("category_counts", {}), 5)
    profile["preferred_preferences"] = _top_items(profile.get("preference_counts", {}), 5)
    profile["avoid_preferences"] = _top_items(profile.get("avoid_counts", {}), 5)

    behavior_counts = profile.get("behavior_counts", {})
    profile["preferred_pace"] = None
    for pace_key in ("pace:slow", "pace:fast"):
        if int(behavior_counts.get(pace_key, 0)) >= 2:
            profile["preferred_pace"] = pace_key.split(":", 1)[1]
            break
    profile["preferred_transport_mode"] = None
    for transport_key in ("transport:walking", "transport:metro", "transport:taxi"):
        if int(behavior_counts.get(transport_key, 0)) >= 2:
            profile["preferred_transport_mode"] = transport_key.split(":", 1)[1]
            break
    profile["budget_band"] = None
    for budget_key in ("budget:low", "budget:mid", "budget:high"):
        if int(behavior_counts.get(budget_key, 0)) >= 2:
            profile["budget_band"] = budget_key.split(":", 1)[1]
            break

    companion_counts = {k: v for k, v in behavior_counts.items() if k.startswith("companion:")}
    profile["companion_types"] = _top_items(companion_counts, 3)
    profile["confidence"] = min(1.0, 0.2 + (sum(city_counts.values()) + sum(profile.get("preference_counts", {}).values())) / 20.0)
    profile["last_seen_at"] = created_at
    profile["last_event_type"] = event_type
    profile["updated_at"] = created_at


def _project_profile(profile: dict[str, Any], limit: int = 12) -> dict[str, Any]:
    evidence = list(profile.get("evidence", []) or [])
    recent_evidence = evidence[-_RECENT_EVIDENCE_WINDOW:]
    confidence = float(profile.get("confidence", 0.0) or 0.0)
    stable_min_count = _PROFILE_LOW_CONFIDENCE_STABLE_COUNT if confidence < 0.35 else _PROFILE_MIN_STABLE_COUNT

    category_counts = dict(profile.get("category_counts", {}) or {})
    preference_counts = dict(profile.get("preference_counts", {}) or {})
    avoid_counts = dict(profile.get("avoid_counts", {}) or {})

    stable_categories = _stable_top_items(category_counts, limit=limit, min_count=stable_min_count)
    stable_preferences = _stable_top_items(preference_counts, limit=limit, min_count=stable_min_count)
    stable_avoids = _stable_top_items(avoid_counts, limit=limit, min_count=stable_min_count)

    recent_cities = _recent_values(recent_evidence, "city", limit=limit)
    recent_categories = _recent_values(recent_evidence, "required_categories", limit=limit)
    recent_preferences = _recent_values(recent_evidence, "preferences", limit=limit)
    recent_avoids = _recent_values(recent_evidence, "avoid", limit=limit)

    last_seen_at = profile.get("last_seen_at")
    if not last_seen_at and recent_evidence:
        last_seen_at = recent_evidence[-1].get("created_at")
    staleness_days = _days_since(last_seen_at)
    decay_score = 0.0 if staleness_days is None else round(min(1.0, staleness_days / 30.0), 3)

    stable_signal_count = len(stable_categories) + len(stable_preferences) + len(stable_avoids)
    recent_signal_count = len(recent_categories) + len(recent_preferences) + len(recent_avoids)
    memory_strength = min(
        1.0,
        max(
            0.0,
            confidence * 0.65 + min(len(evidence), 12) / 20.0 + stable_signal_count / 12.0 - decay_score * 0.2,
        ),
    )

    pending_conflicts: list[dict[str, Any]] = []
    if profile.get("preferred_pace") and recent_evidence:
        recent_paces = [str(item.get("pace")).strip() for item in recent_evidence if str(item.get("pace") or "").strip()]
        if recent_paces and any(item != profile.get("preferred_pace") for item in recent_paces):
            pending_conflicts.append(
                {
                    "field": "pace",
                    "stable": profile.get("preferred_pace"),
                    "recent": recent_paces[-1],
                    "reason": "recent_session_differs_from_stable_profile",
                }
            )
    if profile.get("preferred_transport_mode") and recent_evidence:
        recent_transport = [str(item.get("transport_mode")).strip() for item in recent_evidence if str(item.get("transport_mode") or "").strip()]
        if recent_transport and any(item != profile.get("preferred_transport_mode") for item in recent_transport):
            pending_conflicts.append(
                {
                    "field": "transport_mode",
                    "stable": profile.get("preferred_transport_mode"),
                    "recent": recent_transport[-1],
                    "reason": "recent_session_differs_from_stable_profile",
                }
            )
    stable_preference_set = set(stable_preferences)
    stable_avoid_set = set(stable_avoids)
    recent_preference_set = set(recent_preferences)
    recent_avoid_set = set(recent_avoids)
    for token in sorted(stable_preference_set & recent_avoid_set):
        pending_conflicts.append(
            {
                "field": "preference_vs_avoid",
                "stable": token,
                "recent": token,
                "reason": "stable_preference_conflicts_with_recent_avoid",
            }
        )
    for token in sorted(stable_avoid_set & recent_preference_set):
        pending_conflicts.append(
            {
                "field": "avoid_vs_preference",
                "stable": token,
                "recent": token,
                "reason": "stable_avoid_conflicts_with_recent_preference",
            }
        )

    return {
        "session_id": profile.get("session_id"),
        "home_city": profile.get("home_city"),
        "frequent_cities": list(profile.get("frequent_cities", []) or []),
        "preferred_categories": list(profile.get("preferred_categories", []) or []),
        "preferred_preferences": list(profile.get("preferred_preferences", []) or []),
        "avoid_preferences": list(profile.get("avoid_preferences", []) or []),
        "preferred_pace": profile.get("preferred_pace"),
        "preferred_transport_mode": profile.get("preferred_transport_mode"),
        "budget_band": profile.get("budget_band"),
        "companion_types": list(profile.get("companion_types", []) or []),
        "confidence": round(confidence, 3),
        "memory_strength": round(memory_strength, 3),
        "staleness_days": staleness_days,
        "decay_score": decay_score,
        "stable_min_count": stable_min_count,
        "stable_signal_count": stable_signal_count,
        "recent_signal_count": recent_signal_count,
        "evidence_count": len(evidence),
        "recent_evidence_count": len(recent_evidence),
        "stable_categories": stable_categories,
        "stable_preferences": stable_preferences,
        "stable_avoids": stable_avoids,
        "recent_cities": recent_cities,
        "recent_categories": recent_categories,
        "recent_preferences": recent_preferences,
        "recent_avoids": recent_avoids,
        "pending_conflicts": pending_conflicts[:6],
        "last_seen_at": last_seen_at,
        "updated_at": profile.get("updated_at"),
    }


def _semantic_memory_units(projection: dict[str, Any], *, max_items: int = 8) -> dict[str, Any]:
    atomic_facts: list[str] = []
    scene_tags: list[str] = []

    home_city = str(projection.get("home_city") or "").strip()
    if home_city:
        atomic_facts.append(f"user often plans around {home_city}")
        scene_tags.append("city_preference")

    for item in projection.get("stable_categories", []) or []:
        token = str(item).strip()
        if token:
            atomic_facts.append(f"user repeatedly chooses category {token}")
            scene_tags.append("category_preference")

    for item in projection.get("stable_preferences", []) or []:
        token = str(item).strip()
        if token:
            atomic_facts.append(f"user repeatedly prefers {token}")
            scene_tags.append("style_preference")

    for item in projection.get("stable_avoids", []) or []:
        token = str(item).strip()
        if token:
            atomic_facts.append(f"user repeatedly avoids {token}")
            scene_tags.append("avoidance")

    if projection.get("preferred_pace"):
        atomic_facts.append(f"user usually prefers a {projection.get('preferred_pace')} pace")
        scene_tags.append("pace")
    if projection.get("preferred_transport_mode"):
        atomic_facts.append(f"user usually travels by {projection.get('preferred_transport_mode')}")
        scene_tags.append("transport")
    if projection.get("budget_band"):
        atomic_facts.append(f"user usually fits the {projection.get('budget_band')} budget band")
        scene_tags.append("budget")
    if projection.get("current_route_title"):
        atomic_facts.append(f"current working route is {projection.get('current_route_title')}")
        scene_tags.append("active_route")

    unique_facts = list(dict.fromkeys(item for item in atomic_facts if item))[:max_items]
    unique_tags = list(dict.fromkeys(item for item in scene_tags if item))[:max_items]
    return {
        "atomic_facts": unique_facts,
        "scene_tags": unique_tags,
        "narrative": "; ".join(unique_facts[:4]),
    }


def get_memory_projection(session_id: str, limit: int = 12) -> dict[str, Any]:
    snapshot = get_context_snapshot(session_id, limit=limit)
    session = snapshot.session.model_dump(mode="json")
    profile = snapshot.profile.model_dump(mode="json")
    projection = _project_profile(profile, limit=limit)
    projection["session_mode"] = session.get("mode")
    projection["current_route_version_id"] = session.get("current_route_version_id")
    projection["current_route_title"] = session.get("current_route_title")
    projection["current_route_summary"] = session.get("current_route_summary")
    projection["clarification_pending"] = bool(session.get("clarification_pending"))
    projection["recent_event_count"] = len(snapshot.recent_events)
    projection["route_version_count"] = len(snapshot.route_versions)
    projection["last_query"] = session.get("last_query")
    projection["last_task_hint"] = session.get("last_task_hint")
    projection["session"] = session
    projection["profile"] = profile
    projection["recent_events"] = [event.model_dump(mode="json") for event in snapshot.recent_events]
    projection["route_versions"] = [item.model_dump(mode="json") for item in snapshot.route_versions]
    projection["raw_layer"] = {
        "recent_event_count": len(snapshot.recent_events),
        "recent_event_types": [str(item.event_type) for item in snapshot.recent_events[-limit:]],
        "recent_queries": [str(item.query) for item in snapshot.recent_events[-3:] if getattr(item, "query", None)],
        "route_version_titles": [str(item.title) for item in snapshot.route_versions[-3:] if getattr(item, "title", None)],
    }
    projection["structured_layer"] = {
        "home_city": projection.get("home_city"),
        "preferred_categories": projection.get("preferred_categories", []),
        "preferred_preferences": projection.get("preferred_preferences", []),
        "avoid_preferences": projection.get("avoid_preferences", []),
        "preferred_pace": projection.get("preferred_pace"),
        "preferred_transport_mode": projection.get("preferred_transport_mode"),
        "budget_band": projection.get("budget_band"),
        "companion_types": projection.get("companion_types", []),
    }
    projection["semantic_layer"] = _semantic_memory_units(projection)
    return projection


def render_memory_context_block(projection: dict[str, Any], *, max_items: int = 4) -> str:
    """Render a compact soft-bias memory block for LLM prompts.

    This keeps the raw store separate from prompt injection while still
    surfacing stable and recent signals when they are useful.
    """

    if not projection:
        return ""

    def _take(items: Any) -> list[str]:
        values = [str(item).strip() for item in (items or []) if str(item).strip()]
        return values[:max_items]

    lines = [
        "[memory_context]",
        "soft_bias_only=true",
        f"confidence={projection.get('confidence', 0.0)}",
        f"memory_strength={projection.get('memory_strength', 0.0)}",
    ]
    if projection.get("session_mode"):
        lines.append(f"session_mode={projection.get('session_mode')}")
    if projection.get("home_city"):
        lines.append(f"home_city={projection.get('home_city')}")
    if projection.get("current_route_title"):
        lines.append(f"current_route_title={projection.get('current_route_title')}")
    if _take(projection.get("stable_categories")):
        lines.append("stable_categories=" + ",".join(_take(projection.get("stable_categories"))))
    if _take(projection.get("stable_preferences")):
        lines.append("stable_preferences=" + ",".join(_take(projection.get("stable_preferences"))))
    if _take(projection.get("stable_avoids")):
        lines.append("stable_avoids=" + ",".join(_take(projection.get("stable_avoids"))))
    if _take(projection.get("recent_categories")):
        lines.append("recent_categories=" + ",".join(_take(projection.get("recent_categories"))))
    if _take(projection.get("recent_preferences")):
        lines.append("recent_preferences=" + ",".join(_take(projection.get("recent_preferences"))))
    if _take(projection.get("recent_avoids")):
        lines.append("recent_avoids=" + ",".join(_take(projection.get("recent_avoids"))))
    if _take(projection.get("recent_cities")):
        lines.append("recent_cities=" + ",".join(_take(projection.get("recent_cities"))))
    if projection.get("current_route_summary"):
        lines.append(f"current_route_summary={projection.get('current_route_summary')}")
    semantic_layer = projection.get("semantic_layer") or {}
    atomic_facts = _take((semantic_layer or {}).get("atomic_facts"))
    if atomic_facts:
        lines.append("atomic_facts=" + " | ".join(atomic_facts))
    scene_tags = _take((semantic_layer or {}).get("scene_tags"))
    if scene_tags:
        lines.append("scene_tags=" + ",".join(scene_tags))
    if projection.get("pending_conflicts"):
        lines.append(f"pending_conflicts={len(projection.get('pending_conflicts') or [])}")
    if projection.get("decay_score") is not None:
        lines.append(f"decay_score={projection.get('decay_score')}")
    lines.append("priority=current_input_overrides_memory")
    return "\n".join(lines)


def _build_snapshot(session_id: str, store: dict[str, Any], limit: int = 12) -> ContextSnapshot:
    bucket = _ensure_session_bucket(store, session_id)
    session = SessionContext.model_validate(bucket["session"])
    profile = UserProfile.model_validate(bucket["profile"])
    events = [BehaviorEvent.model_validate(item) for item in bucket.get("events", [])[-limit:]]
    routes = [RouteVersionRecord.model_validate(item) for item in bucket.get("routes", [])[-limit:]]
    return ContextSnapshot(session=session, profile=profile, recent_events=events, route_versions=routes)


def get_context_snapshot(session_id: str, limit: int = 12) -> ContextSnapshot:
    """Return a full context snapshot for the given session."""

    with _STORE_LOCK:
        store = _load_store()
        return _build_snapshot(session_id, store, limit=limit)


def get_session_context(session_id: str) -> SessionContext:
    return get_context_snapshot(session_id).session


def get_profile(session_id: str) -> UserProfile:
    return get_context_snapshot(session_id).profile


def list_recent_events(session_id: str, limit: int = 12) -> list[BehaviorEvent]:
    return get_context_snapshot(session_id, limit=limit).recent_events


def get_current_route_version(session_id: str) -> dict[str, Any] | None:
    """Return the most recent/current route payload for a session, if any."""

    snapshot = get_context_snapshot(session_id)
    session = snapshot.session
    if session.current_route_version_id:
        for route_version in snapshot.route_versions:
            if route_version.version_id == session.current_route_version_id:
                route = dict(route_version.route or {})
                if route:
                    return route
    if snapshot.route_versions:
        route = dict(snapshot.route_versions[-1].route or {})
        if route:
            return route
    return None


def record_event(
    session_id: str,
    event_type: str,
    *,
    query: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
    intent: Any = None,
    route_version: Any = None,
    diagnostics: Any = None,
) -> ContextSnapshot:
    """Append a context event and update the lightweight profile projection."""

    payload = dict(payload or {})
    intent_data = _intent_to_dict(intent)
    route_snapshot = _route_to_snapshot(route_version)
    diagnostics_data = _intent_to_dict(diagnostics)

    with _STORE_LOCK:
        store = _load_store()
        bucket = _ensure_session_bucket(store, session_id)

        event = BehaviorEvent(
            event_id=str(uuid4()),
            session_id=session_id,
            event_type=event_type,
            query=query,
            payload=payload,
            route_version_id=route_snapshot.get("request_id") or route_snapshot.get("version_id"),
            intent_summary=intent_data or None,
            diagnostics=diagnostics_data or None,
        )
        bucket["events"].append(event.model_dump(mode="json"))
        del bucket["events"][:-_MAX_EVENTS_PER_SESSION]

        session = SessionContext.model_validate(bucket["session"])
        session.last_query = query or session.last_query
        session.last_intent_summary = intent_data or session.last_intent_summary
        session.updated_at = event.created_at

        if intent_data.get("city"):
            session.city = intent_data.get("city")

        if event_type in {"route_created", "route_modified"}:
            session.mode = "route"
            session.clarification_pending = False
        elif event_type == "clarification_requested":
            session.mode = "clarify"
            session.clarification_pending = True
        elif event_type == "clarification_answered":
            session.mode = "route"
            session.clarification_pending = False
        elif event_type in {"route_favorited", "route_copied", "route_rejected"}:
            session.mode = "route"

        if diagnostics_data.get("task_hint"):
            session.last_task_hint = str(diagnostics_data.get("task_hint"))

        bucket["session"] = session.model_dump(mode="json")

        if route_snapshot:
            version_id = route_snapshot.get("request_id") or route_snapshot.get("generated_at") or str(uuid4())
            route_record = RouteVersionRecord(
                version_id=str(version_id),
                session_id=session_id,
                event_type=event_type,
                title=route_snapshot.get("title"),
                summary=route_snapshot.get("summary"),
                query=query,
                intent_summary=intent_data,
                diagnostics=diagnostics_data,
                route=route_snapshot,
            )
            bucket["routes"].append(route_record.model_dump(mode="json"))
            del bucket["routes"][:-_MAX_ROUTE_VERSIONS_PER_SESSION]
            session.current_route_version_id = route_record.version_id
            session.current_route_title = route_record.title
            session.current_route_summary = route_record.summary
            bucket["session"] = session.model_dump(mode="json")

        profile_data = dict(bucket["profile"])
        _update_profile_from_intent(
            profile_data,
            intent_data,
            event_type,
            created_at=event.created_at,
            session_id=session_id,
        )
        bucket["profile"] = profile_data

        _save_store(store)
        return _build_snapshot(session_id, store)


def record_route_version(
    session_id: str,
    *,
    event_type: str = "route_created",
    query: Optional[str] = None,
    intent: Any = None,
    route_version: Any = None,
    diagnostics: Any = None,
) -> ContextSnapshot:
    return record_event(
        session_id,
        event_type,
        query=query,
        intent=intent,
        route_version=route_version,
        diagnostics=diagnostics,
    )


def apply_profile_bias(intent: Any, profile: Any) -> Any:
    """Bias a parsed intent with stable profile signals without overriding explicit user input."""

    if intent is None or profile is None:
        return intent

    profile_data = profile.model_dump(mode="json") if hasattr(profile, "model_dump") else dict(profile)
    projection = _project_profile(profile_data)
    confidence = float(projection.get("confidence", 0.0) or 0.0)
    stable_categories = list(projection.get("stable_categories", []) or [])
    stable_preferences = list(projection.get("stable_preferences", []) or [])
    stable_avoids = list(projection.get("stable_avoids", []) or [])

    applied: list[str] = []

    if not getattr(intent, "city", None) and profile_data.get("home_city") and confidence >= 0.25:
        intent.city = profile_data.get("home_city")
        applied.append(f"city:{intent.city}")

    current_categories = list(getattr(intent, "required_categories", []) or [])
    if not current_categories and stable_categories and confidence >= 0.4:
        intent.required_categories = list(stable_categories)
        applied.extend(f"required_category:{item}" for item in stable_categories)
    elif current_categories and stable_categories and confidence >= 0.45:
        preferred_categories = list(getattr(intent, "preferred_categories", []) or current_categories)
        for item in stable_categories:
            if item not in preferred_categories and item not in current_categories:
                preferred_categories.append(item)
                applied.append(f"soft_category:{item}")
        intent.preferred_categories = preferred_categories

    current_preferences = list(getattr(intent, "preferences", []) or [])
    soft_preferences = list(getattr(intent, "soft_preferences", []) or current_preferences)
    if not current_preferences and stable_preferences and confidence >= 0.4:
        for item in stable_preferences:
            if item not in soft_preferences:
                soft_preferences.append(item)
                applied.append(f"soft_preference:{item}")
    elif current_preferences and stable_preferences and confidence >= 0.45:
        for item in stable_preferences:
            if item not in current_preferences and item not in soft_preferences:
                soft_preferences.append(item)
                applied.append(f"soft_preference:{item}")
    intent.soft_preferences = soft_preferences

    if not getattr(intent, "avoid", None) and stable_avoids and confidence >= 0.4:
        intent.avoid = list(stable_avoids)
        applied.extend(f"avoid:{item}" for item in stable_avoids)

    profile_pace = profile_data.get("preferred_pace")
    if getattr(intent, "pace", None) in {None, "", "normal"} and profile_pace and confidence >= 0.5:
        intent.pace = profile_pace
        applied.append(f"pace:{profile_pace}")

    profile_transport = profile_data.get("preferred_transport_mode")
    if getattr(intent, "transport_mode", None) in {None, "", "mixed"} and profile_transport in {"walking", "metro", "taxi"} and confidence >= 0.5:
        intent.transport_mode = profile_transport
        applied.append(f"transport:{profile_transport}")

    profile_budget = profile_data.get("budget_band")
    if getattr(intent, "budget", None) is None and profile_budget in {"low", "mid", "high"} and confidence >= 0.55:
        # Keep it soft: only annotate derived hints instead of inventing a hard number.
        existing_notes = getattr(intent, "notes", None)
        hint = f"profile_budget_band:{profile_budget}"
        intent.notes = f"{existing_notes}; {hint}" if existing_notes else hint
        applied.append(hint)

    existing_bias = list(getattr(intent, "profile_bias", []) or [])
    if confidence > 0:
        applied.append(f"profile_confidence:{round(confidence, 2)}")
    intent.profile_bias = list(dict.fromkeys([*existing_bias, *applied]))

    try:
        from core.intent_parser import refresh_intent_derived_fields

        refresh_intent_derived_fields(intent)
    except Exception:
        try:
            intent.model_post_init(None)
        except Exception:
            pass
    return intent


def apply_session_context(intent: Any, session: Any) -> Any:
    """Merge current-session context without overriding explicit turn constraints."""

    if intent is None or session is None:
        return intent

    session_data = session.model_dump(mode="json") if hasattr(session, "model_dump") else dict(session)
    last_intent = session_data.get("last_intent_summary") or {}
    if not isinstance(last_intent, dict):
        return intent

    applied: list[str] = []

    if not getattr(intent, "city", None) and last_intent.get("city"):
        intent.city = last_intent.get("city")
        applied.append(f"session_city:{intent.city}")

    if getattr(intent, "budget", None) is None and last_intent.get("budget") is not None:
        intent.budget = last_intent.get("budget")
        applied.append(f"session_budget:{intent.budget}")

    if not getattr(intent, "start_location", None) and last_intent.get("start_location"):
        intent.start_location = last_intent.get("start_location")
        applied.append(f"session_start_location:{intent.start_location}")

    current_preferences = list(getattr(intent, "preferences", []) or [])
    current_categories = list(getattr(intent, "required_categories", []) or [])
    current_avoid = list(getattr(intent, "avoid", []) or [])
    current_must = list(getattr(intent, "must_include", []) or [])

    if not current_preferences:
        inherited = [str(item) for item in last_intent.get("preferences", []) or [] if item]
        intent.preferences = list(dict.fromkeys([*current_preferences, *inherited]))
        applied.extend(f"session_preference:{item}" for item in inherited)
    else:
        soft = list(getattr(intent, "soft_preferences", []) or current_preferences)
        for item in last_intent.get("preferences", []) or []:
            token = str(item or "").strip()
            if token and token not in current_preferences and token not in soft:
                soft.append(token)
                applied.append(f"session_soft_preference:{token}")
        intent.soft_preferences = soft

    if not current_categories:
        inherited = [str(item) for item in last_intent.get("required_categories", []) or [] if item]
        intent.required_categories = list(dict.fromkeys([*current_categories, *inherited]))
        applied.extend(f"session_category:{item}" for item in inherited)

    if not current_avoid:
        inherited = [str(item) for item in last_intent.get("avoid", []) or [] if item]
        intent.avoid = list(dict.fromkeys([*current_avoid, *inherited]))
        applied.extend(f"session_avoid:{item}" for item in inherited)

    if not current_must:
        inherited = [str(item) for item in last_intent.get("must_include", []) or [] if item]
        intent.must_include = list(dict.fromkeys([*current_must, *inherited]))
        applied.extend(f"session_must_include:{item}" for item in inherited)

    if getattr(intent, "pace", None) in {None, "", "normal"} and last_intent.get("pace") in {"fast", "slow"}:
        intent.pace = last_intent.get("pace")
        applied.append(f"session_pace:{intent.pace}")

    if getattr(intent, "transport_mode", None) in {None, "", "mixed"} and last_intent.get("transport_mode") in _VALID_TRANSPORT:
        intent.transport_mode = last_intent.get("transport_mode")
        applied.append(f"session_transport:{intent.transport_mode}")

    existing = list(getattr(intent, "context_bias", []) or [])
    intent.context_bias = list(dict.fromkeys([*existing, *applied]))

    try:
        from core.intent_parser import refresh_intent_derived_fields

        refresh_intent_derived_fields(intent)
    except Exception:
        try:
            intent.model_post_init(None)
        except Exception:
            pass
    return intent


def reset_session(session_id: str) -> None:
    with _STORE_LOCK:
        store = _load_store()
        sessions = store.setdefault("sessions", {})
        sessions.pop(session_id, None)
        _save_store(store)
