"""Patch-based intent repair for route quality gaps."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from core.schemas import ParsedIntent


class IntentPatch(BaseModel):
    """A constrained mutation proposed for a parsed intent."""

    model_config = ConfigDict(extra="allow")

    field: str
    op: Literal["add", "set"] = "add"
    value: Any
    source: str = "quality_report"
    reason: str = ""
    evidence: list[str] = Field(default_factory=list)


class IntentRepairAgent:
    """Deterministic repair agent that emits auditable intent patches."""

    allowed_add_fields = {"required_categories", "preferences", "soft_preferences", "avoid"}
    allowed_set_fields = {"route_strategy"}

    def build_patches(self, intent: ParsedIntent, quality: dict[str, Any]) -> list[IntentPatch]:
        gaps = {str(item) for item in quality.get("gaps", []) or []}
        missing_categories = [str(item) for item in quality.get("missing_categories", []) or [] if item]
        patches: list[IntentPatch] = []

        def add(field: str, value: str, reason: str, evidence: list[str] | None = None) -> None:
            patches.append(
                IntentPatch(
                    field=field,
                    op="add",
                    value=value,
                    reason=reason,
                    evidence=evidence or [],
                )
            )

        def set_value(field: str, value: str, reason: str, evidence: list[str] | None = None) -> None:
            patches.append(
                IntentPatch(
                    field=field,
                    op="set",
                    value=value,
                    reason=reason,
                    evidence=evidence or [],
                )
            )

        for category in missing_categories:
            add("required_categories", category, "Quality report says a required experience category is missing.", [category])

        if "missing_food_stop" in gaps:
            add("required_categories", "food", "Add a food stop to satisfy the route experience gap.", ["missing_food_stop"])
            add("preferences", "food", "Keep food visible to POI ranking after repair.", ["missing_food_stop"])
        if "missing_night_view" in gaps:
            add("required_categories", "night", "Add a night-view stop to satisfy the requested evening experience.", ["missing_night_view"])
            add("preferences", "night_view", "Keep night view visible to POI ranking after repair.", ["missing_night_view"])
        if "missing_culture_stop" in gaps:
            add("required_categories", "museum", "Add a cultural stop candidate after critique found missing culture.", ["missing_culture_stop"])
            add("required_categories", "exhibition", "Add an exhibition candidate after critique found missing culture.", ["missing_culture_stop"])
            add("preferences", "culture", "Keep culture visible to POI ranking after repair.", ["missing_culture_stop"])
        if "weak_local_feature" in gaps:
            add("preferences", "local_feature", "Strengthen local-feature matching after critique.", ["weak_local_feature"])
            add("soft_preferences", "local_feature", "Use local-feature as a soft ranking signal.", ["weak_local_feature"])
        if "weak_premium_match" in gaps:
            add("preferences", "premium", "Strengthen premium matching after critique.", ["weak_premium_match"])
        if "queue_risk_remains" in gaps:
            add("avoid", "avoid_queue", "Preserve the user-facing no-queue constraint during repair.", ["queue_risk_remains"])
            add("avoid", "avoid_crowded", "Reduce crowding risk when queue risk remains.", ["queue_risk_remains"])
        if "budget_overrun" in gaps:
            add("preferences", "value", "Prefer value options after budget overrun.", ["budget_overrun"])
            set_value("route_strategy", "compact", "Use a compact strategy to reduce extra cost and travel.", ["budget_overrun"])
        if "slow_pace_mismatch" in gaps:
            add("avoid", "avoid_far", "Reduce transfer burden for slow-pace mismatch.", ["slow_pace_mismatch"])
            set_value("route_strategy", "compact", "Use a compact strategy for a slower pace.", ["slow_pace_mismatch"])

        return self._dedupe_patches(patches)

    def apply_patches(self, intent: ParsedIntent, patches: list[IntentPatch]) -> ParsedIntent | None:
        if not patches:
            return None
        repaired = ParsedIntent(**intent.model_dump(mode="json"))
        changed = False
        for patch in patches:
            if patch.op == "add":
                if patch.field not in self.allowed_add_fields:
                    continue
                values = list(getattr(repaired, patch.field, []) or [])
                if patch.value not in values:
                    setattr(repaired, patch.field, [*values, patch.value])
                    changed = True
            elif patch.op == "set":
                if patch.field not in self.allowed_set_fields:
                    continue
                if getattr(repaired, patch.field, None) != patch.value:
                    setattr(repaired, patch.field, patch.value)
                    changed = True
        if not changed:
            return None
        repaired.repair_attempted = True
        repaired.repair_patches = [patch.model_dump(mode="json") for patch in patches]
        repaired.repair_reasons = sorted({item for patch in patches for item in patch.evidence} or {patch.reason for patch in patches})
        return repaired

    def repair(self, intent: ParsedIntent, quality: dict[str, Any]) -> ParsedIntent | None:
        patches = self.build_patches(intent, quality)
        return self.apply_patches(intent, patches)

    @staticmethod
    def _dedupe_patches(patches: list[IntentPatch]) -> list[IntentPatch]:
        seen: set[tuple[str, str, str]] = set()
        result: list[IntentPatch] = []
        for patch in patches:
            key = (patch.field, patch.op, str(patch.value))
            if key in seen:
                continue
            seen.add(key)
            result.append(patch)
        return result
