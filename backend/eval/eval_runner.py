from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from services import route_service


DATA_PATH = Path(__file__).resolve().parents[1] / "eval_cases.json"


@dataclass
class CaseResult:
    case_id: str
    case_type: str
    passed: bool
    checks: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


def _load_cases() -> list[dict[str, Any]]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def _subset_check(values: list[str], expected: list[str]) -> bool:
    return set(expected).issubset(set(values))


def _has_any(values: list[str], expected: list[str]) -> bool:
    return bool(set(values).intersection(expected))


def _run_intent_case(case: dict[str, Any]) -> CaseResult:
    intent, response = route_service.plan_route(case["query"], city=case.get("expect", {}).get("city"))
    expect = case.get("expect", {})

    checks: list[bool] = []
    notes: list[str] = []

    if "city" in expect:
        ok = intent.city == expect["city"]
        checks.append(ok)
        notes.append(f"city={intent.city} expect={expect['city']}")

    if "preferences" in expect:
        ok = _subset_check(intent.preferences, expect["preferences"])
        checks.append(ok)
        notes.append(f"preferences={intent.preferences}")

    if "required_categories" in expect:
        ok = _subset_check(intent.required_categories, expect["required_categories"])
        checks.append(ok)
        notes.append(f"categories={intent.required_categories}")

    if "avoid" in expect:
        ok = _subset_check(intent.avoid, expect["avoid"])
        checks.append(ok)
        notes.append(f"avoid={intent.avoid}")

    if "pace" in expect:
        ok = intent.pace == expect["pace"]
        checks.append(ok)
        notes.append(f"pace={intent.pace}")

    if "transport_mode" in expect:
        ok = intent.transport_mode == expect["transport_mode"]
        checks.append(ok)
        notes.append(f"transport_mode={intent.transport_mode}")

    if "min_poi_count" in expect:
        ok = response.poi_count >= expect["min_poi_count"]
        checks.append(ok)
        notes.append(f"poi_count={response.poi_count}")

    if "unclassified_contains" in expect:
        ok = _subset_check(intent.unclassified_clues, expect["unclassified_contains"])
        checks.append(ok)
        notes.append(f"unclassified={intent.unclassified_clues}")

    passed = all(checks) if checks else True
    return CaseResult(
        case_id=case["id"],
        case_type="intent",
        passed=passed,
        checks=[str(item) for item in checks],
        notes=notes,
        metrics={
            "intent": intent.model_dump(),
            "response": response.model_dump(),
        },
    )


def _run_modify_case(case: dict[str, Any]) -> CaseResult:
    expect = case.get("expect", {})
    base_intent, base_response = route_service.plan_route(case["base_query"])
    modify_intent, modify_response = route_service.plan_route(
        case["modify_query"],
        city=base_intent.city,
        current_route=base_response.model_dump(),
        original_query=case["base_query"],
    )

    checks: list[bool] = []
    notes: list[str] = []

    if "avoid" in expect:
        ok = _subset_check(modify_intent.avoid, expect["avoid"])
        checks.append(ok)
        notes.append(f"avoid={modify_intent.avoid}")

    if "preferences" in expect:
        ok = _subset_check(modify_intent.preferences, expect["preferences"])
        checks.append(ok)
        notes.append(f"preferences={modify_intent.preferences}")

    if "pace" in expect:
        ok = modify_intent.pace == expect["pace"]
        checks.append(ok)
        notes.append(f"pace={modify_intent.pace}")

    if "max_total_distance_ratio" in expect:
        ratio = modify_response.total_distance / max(base_response.total_distance, 0.001)
        ok = ratio <= expect["max_total_distance_ratio"]
        checks.append(ok)
        notes.append(f"distance_ratio={ratio:.3f}")

    if "max_total_cost_ratio" in expect:
        ratio = modify_response.total_cost / max(base_response.total_cost, 1)
        ok = ratio <= expect["max_total_cost_ratio"]
        checks.append(ok)
        notes.append(f"cost_ratio={ratio:.3f}")

    if "max_total_duration_ratio" in expect:
        ratio = modify_response.total_duration / max(base_response.total_duration, 1)
        ok = ratio <= expect["max_total_duration_ratio"]
        checks.append(ok)
        notes.append(f"duration_ratio={ratio:.3f}")

    if "max_poi_count" in expect:
        ok = modify_response.poi_count <= expect["max_poi_count"]
        checks.append(ok)
        notes.append(f"poi_count={modify_response.poi_count}")

    passed = all(checks) if checks else True
    return CaseResult(
        case_id=case["id"],
        case_type="modify",
        passed=passed,
        checks=[str(item) for item in checks],
        notes=notes,
        metrics={
            "base_intent": base_intent.model_dump(),
            "base_response": base_response.model_dump(),
            "modify_intent": modify_intent.model_dump(),
            "modify_response": modify_response.model_dump(),
        },
    )


def run_offline_evaluation(
    case_ids: list[str] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    previous = os.environ.get("LLM_INTENT_DISABLE_LLM")
    os.environ["LLM_INTENT_DISABLE_LLM"] = "1"
    try:
        cases = _load_cases()
        if case_ids:
            case_set = set(case_ids)
            cases = [case for case in cases if case["id"] in case_set]
        if limit is not None:
            cases = cases[: max(0, limit)]

        results: list[CaseResult] = []
        for case in cases:
            if case.get("type") == "modify":
                results.append(_run_modify_case(case))
            else:
                results.append(_run_intent_case(case))

        passed = sum(1 for item in results if item.passed)
        total = len(results)
        return {
            "dataset": DATA_PATH.name,
            "total_cases": total,
            "passed_cases": passed,
            "pass_rate": round(passed / total, 3) if total else 0.0,
            "results": [
                {
                    "case_id": item.case_id,
                    "case_type": item.case_type,
                    "passed": item.passed,
                    "notes": item.notes,
                    "checks": item.checks,
                }
                for item in results
            ],
        }
    finally:
        if previous is None:
            os.environ.pop("LLM_INTENT_DISABLE_LLM", None)
        else:
            os.environ["LLM_INTENT_DISABLE_LLM"] = previous


if __name__ == "__main__":
    report = run_offline_evaluation()
    print(json.dumps(report, ensure_ascii=False, indent=2))
