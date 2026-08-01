"""Canonical intent intermediate representation.

This module converts `ParsedIntent` into a more execution-friendly intermediate
representation so understanding and planning do not have to share the exact
same shape.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


_PARTY_TYPES = ("couple", "family", "friends", "solo")
_ATMOSPHERE_KEYS = (
    "photo",
    "local_feature",
    "night_view",
    "quiet",
    "rainy_day",
    "indoor",
    "outdoor",
    "culture",
    "premium",
    "value",
    "relaxed",
)
_MOBILITY_KEYS = ("walking", "citywalk", "efficient", "compact")
_SUPPORT_CATEGORIES = {"food", "coffee"}


class IntentIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_type: str = "route_plan"
    city: str | None = None
    goal_slots: list[str] = Field(default_factory=list)
    support_slots: list[str] = Field(default_factory=list)
    atmosphere_slots: list[str] = Field(default_factory=list)
    mobility_slots: list[str] = Field(default_factory=list)
    constraint_slots: list[str] = Field(default_factory=list)
    party_types: list[str] = Field(default_factory=list)
    primary_party_type: str | None = None
    must_include: list[str] = Field(default_factory=list)
    start_location: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    budget: float | None = None
    route_strategy: str | None = None
    parse_source: str = "local"
    confidence: float | None = None
    uncertainty: list[str] = Field(default_factory=list)
    schema_ready: bool = False


def build_intent_ir(intent: Any) -> IntentIR:
    required_categories = [str(item) for item in getattr(intent, "required_categories", []) or [] if item]
    preferences = [str(item) for item in getattr(intent, "preferences", []) or [] if item]
    avoid = [str(item) for item in getattr(intent, "avoid", []) or [] if item]
    party_types = [str(item) for item in getattr(intent, "party_types", []) or [] if item]
    if not party_types:
        party_types = [item for item in _PARTY_TYPES if item in preferences]

    goal_slots = [item for item in required_categories if item not in _SUPPORT_CATEGORIES]
    support_slots = [item for item in required_categories if item in _SUPPORT_CATEGORIES]
    if not goal_slots and required_categories:
        goal_slots = list(required_categories[:1])

    atmosphere_slots = [item for item in preferences if item in _ATMOSPHERE_KEYS]
    mobility_slots = [item for item in preferences if item in _MOBILITY_KEYS]
    if getattr(intent, "transport_mode", None):
        mobility_slots = list(dict.fromkeys([*mobility_slots, str(getattr(intent, "transport_mode"))]))

    constraint_slots = [*avoid]
    if getattr(intent, "budget", None) is not None:
        constraint_slots.append("budget_bound")
    if getattr(intent, "start_time", None) or getattr(intent, "end_time", None):
        constraint_slots.append("time_bound")
    if getattr(intent, "start_location", None):
        constraint_slots.append("start_location_bound")

    uncertainty = [str(item) for item in getattr(intent, "uncertain_fields", []) or [] if item]
    schema_ready = bool(
        getattr(intent, "city", None)
        and (required_categories or preferences or getattr(intent, "must_include", None))
    )

    confidence = getattr(intent, "intent_confidence", None)
    try:
        confidence_value = round(float(confidence), 3) if confidence is not None else None
    except (TypeError, ValueError):
        confidence_value = None

    return IntentIR(
        task_type="route_modify" if getattr(intent, "current_route", None) is not None else "route_plan",
        city=getattr(intent, "city", None),
        goal_slots=goal_slots,
        support_slots=support_slots,
        atmosphere_slots=atmosphere_slots,
        mobility_slots=mobility_slots,
        constraint_slots=list(dict.fromkeys(constraint_slots)),
        party_types=party_types,
        primary_party_type=str(getattr(intent, "primary_party_type", None) or party_types[0]) if party_types else None,
        must_include=[str(item) for item in getattr(intent, "must_include", []) or [] if item],
        start_location=getattr(intent, "start_location", None),
        start_time=getattr(intent, "start_time", None),
        end_time=getattr(intent, "end_time", None),
        budget=getattr(intent, "budget", None),
        route_strategy=getattr(intent, "route_strategy", None),
        parse_source=str(getattr(intent, "parse_source", "local") or "local"),
        confidence=confidence_value,
        uncertainty=uncertainty,
        schema_ready=schema_ready,
    )
