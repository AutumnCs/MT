from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("LLM_INTENT_DISABLE_LLM", "1")

from agent import IntentRepairAgent
from services import context_service, route_service


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


def _prepare_seed_context(case: dict[str, Any]) -> tuple[str | None, Any, Any, bool]:
    seed = case.get("seed_context") or {}
    session_id = str(seed.get("session_id") or case.get("session_id") or "").strip()
    if not session_id:
        return None, None, None, False

    cleanup = bool(seed.get("cleanup", True))
    if seed:
        context_service.reset_session(session_id)
        for event in seed.get("events", []) or []:
            if not isinstance(event, dict):
                continue
            context_service.record_event(
                session_id,
                str(event.get("event_type") or "route_created"),
                query=event.get("query"),
                payload=event.get("payload") if isinstance(event.get("payload"), dict) else None,
                intent=event.get("intent") if isinstance(event.get("intent"), dict) else None,
                route_version=event.get("route_version") if isinstance(event.get("route_version"), dict) else None,
                diagnostics=event.get("diagnostics") if isinstance(event.get("diagnostics"), dict) else None,
            )
    snapshot = context_service.get_context_snapshot(session_id)
    return session_id, snapshot, snapshot.profile, cleanup


def _subset_check(values: list[str], expected: list[str]) -> bool:
    def normalize(value: str) -> str:
        return {
            "spicy": "avoid_spicy",
            "far": "avoid_far",
            "queue": "avoid_queue",
            "crowded": "avoid_crowded",
        }.get(value, value)

    return {normalize(item) for item in expected}.issubset({normalize(item) for item in values})


def _has_any(values: list[str], expected: list[str]) -> bool:
    return bool(set(values).intersection(expected))


def _route_category_counts(response) -> dict[str, int]:
    counts: dict[str, int] = {}
    for stop in getattr(response, "main_stops", []) or []:
        poi = getattr(stop, "poi", None)
        if poi is None:
            continue
        category = getattr(poi, "category", None)
        if category:
            key = str(category)
            counts[key] = counts.get(key, 0) + 1
    return counts


def _route_poi_ids(response) -> list[str]:
    ids: list[str] = []
    for stop in getattr(response, "main_stops", []) or []:
        poi = getattr(stop, "poi", None)
        poi_id = getattr(poi, "id", None)
        if poi_id:
            ids.append(str(poi_id))
    return ids


def _scheduled_stop_count(response) -> int:
    count = 0
    for stop in getattr(response, "main_stops", []) or []:
        if getattr(stop, "arrival_time", None) and getattr(stop, "departure_time", None):
            count += 1
    return count


def _category_group_satisfied(category_counts: dict[str, int], categories: list[str]) -> bool:
    return sum(category_counts.get(str(category), 0) for category in categories) > 0


def _response_payload(response) -> dict[str, Any]:
    if hasattr(response, "model_dump"):
        return response.model_dump(mode="json")
    return dict(response) if isinstance(response, dict) else {}


def _response_trace(response) -> dict[str, Any]:
    payload = _response_payload(response)
    trace = payload.get("trace") or {}
    return trace if isinstance(trace, dict) else {}


def _response_explanation(response) -> str:
    payload = _response_payload(response)
    explanation = payload.get("explanation") or payload.get("route_explanation") or payload.get("summary") or ""
    return str(explanation)


def _response_warnings(response) -> list[str]:
    payload = _response_payload(response)
    warnings = payload.get("warnings") or _workflow_trace(response).get("warnings") or []
    return [str(item) for item in warnings if item is not None]


def _workflow_trace(response) -> dict[str, Any]:
    payload = _response_payload(response)
    trace = _response_trace(response)
    workflow = trace.get("workflow_trace") or payload.get("workflow_trace") or {}
    return workflow if isinstance(workflow, dict) else {}


def _coordinator_trace(response) -> dict[str, Any]:
    trace = _response_trace(response)
    workflow = _workflow_trace(response)
    coordinator = trace.get("coordinator") or workflow.get("coordinator") or {}
    return coordinator if isinstance(coordinator, dict) else {}


def _coordinator_decisions(response) -> list[dict[str, Any]]:
    coordinator = _coordinator_trace(response)
    decisions = coordinator.get("decision_log") or []
    return [item for item in decisions if isinstance(item, dict)]


def _workflow_stage_names(response) -> list[str]:
    workflow = _workflow_trace(response)
    stages = workflow.get("stages") or []
    return [str(item.get("stage")) for item in stages if isinstance(item, dict) and item.get("stage")]


def _route_quality(response) -> dict[str, Any]:
    trace = _response_trace(response)
    quality = trace.get("route_quality") or _workflow_trace(response).get("route_quality") or {}
    return quality if isinstance(quality, dict) else {}


def _coordinator_quality(response) -> dict[str, Any]:
    quality = _coordinator_trace(response).get("quality_report") or {}
    return quality if isinstance(quality, dict) else {}


def _execution_plan(response) -> dict[str, Any]:
    trace = _response_trace(response)
    workflow = _workflow_trace(response)
    coordinator = _coordinator_trace(response)
    plan = trace.get("execution_plan") or workflow.get("execution_plan") or coordinator.get("execution_plan") or {}
    return plan if isinstance(plan, dict) else {}


def _tool_results(response) -> list[dict[str, Any]]:
    trace = _response_trace(response)
    workflow = _workflow_trace(response)
    coordinator = _coordinator_trace(response)
    results = trace.get("tool_results") or workflow.get("tool_results") or coordinator.get("tool_results") or []
    return [item for item in results if isinstance(item, dict)]


def _enabled_tool_names(response) -> list[str]:
    plan = _execution_plan(response)
    tools = plan.get("optional_tools") or []
    return [str(item.get("tool")) for item in tools if isinstance(item, dict) and item.get("enabled")]


def _skipped_tool_names(response) -> list[str]:
    plan = _execution_plan(response)
    tools = plan.get("skipped_tools") or []
    return [str(item.get("tool")) for item in tools if isinstance(item, dict) and item.get("tool")]


def _required_data_names(response) -> list[str]:
    plan = _execution_plan(response)
    data = plan.get("required_data") or []
    return [str(item.get("name")) for item in data if isinstance(item, dict) and item.get("name")]


def _optional_data_names(response) -> list[str]:
    plan = _execution_plan(response)
    data = plan.get("optional_data") or []
    return [str(item.get("name")) for item in data if isinstance(item, dict) and item.get("name")]


def _skipped_data_names(response) -> list[str]:
    plan = _execution_plan(response)
    data = plan.get("skipped_data") or []
    return [str(item.get("tool")) for item in data if isinstance(item, dict) and item.get("tool")]


def _run_workflow_case(case: dict[str, Any]) -> CaseResult:
    expect = case.get("expect", {})
    seeded_session_id, context_snapshot, profile, cleanup_context = _prepare_seed_context(case)
    context_after_route = None
    started = perf_counter()
    try:
        intent, response = route_service.plan_route(
            case["query"],
            city=case.get("city") or expect.get("city"),
            profile=profile,
            context_snapshot=context_snapshot,
        )
        if seeded_session_id and any(
            key in expect
            for key in (
                "min_route_version_count",
                "current_route_version_matches_response",
                "current_route_title_matches_response",
                "current_route_summary_matches_response",
            )
        ):
            context_service.record_event(
                seeded_session_id,
                "route_created",
                query=case["query"],
                intent=intent,
                route_version=response,
            )
            context_after_route = context_service.get_context_snapshot(seeded_session_id)
    finally:
        elapsed_ms = int((perf_counter() - started) * 1000)
        if seeded_session_id and cleanup_context:
            context_service.reset_session(seeded_session_id)
    trace = _response_trace(response)
    coordinator = _coordinator_trace(response)
    decisions = _coordinator_decisions(response)
    stage_names = _workflow_stage_names(response)
    actions = [str(item.get("action")) for item in decisions]
    decision_stages = [str(item.get("stage")) for item in decisions]
    execution_plan = _execution_plan(response)
    tool_results = _tool_results(response)
    tool_names = [str(item.get("tool")) for item in tool_results]

    checks: list[bool] = []
    notes: list[str] = []

    if "max_latency_ms" in expect:
        ok = elapsed_ms <= int(expect["max_latency_ms"])
        checks.append(ok)
        notes.append(f"latency_ms={elapsed_ms}")

    if "max_explanation_length" in expect:
        explanation = _response_explanation(response)
        ok = len(explanation) <= int(expect["max_explanation_length"])
        checks.append(ok)
        notes.append(f"explanation_length={len(explanation)}")

    if "warnings_include" in expect:
        warnings = _response_warnings(response)
        required = [str(item) for item in expect["warnings_include"]]
        ok = set(required).issubset(set(warnings))
        checks.append(ok)
        notes.append(f"warnings={warnings}")

    if "route_quality_warnings_include" in expect:
        warnings = [str(item) for item in (_route_quality(response).get("warnings") or [])]
        required = [str(item) for item in expect["route_quality_warnings_include"]]
        ok = set(required).issubset(set(warnings))
        checks.append(ok)
        notes.append(f"route_quality_warnings={warnings}")

    if "route_quality_gaps_include" in expect:
        gaps = [str(item) for item in (_route_quality(response).get("gaps") or [])]
        required = [str(item) for item in expect["route_quality_gaps_include"]]
        ok = set(required).issubset(set(gaps))
        checks.append(ok)
        notes.append(f"route_quality_gaps={gaps}")

    if "intent_session_id" in expect:
        actual = getattr(intent, "session_id", None)
        ok = actual == expect["intent_session_id"]
        checks.append(ok)
        notes.append(f"intent_session_id={actual}")

    if "clarification_needed" in expect:
        ok = bool(getattr(response, "clarification_needed", False)) == bool(expect["clarification_needed"])
        checks.append(ok)
        notes.append(f"clarification_needed={getattr(response, 'clarification_needed', False)}")

    if "min_decision_count" in expect:
        ok = len(decisions) >= int(expect["min_decision_count"])
        checks.append(ok)
        notes.append(f"decision_count={len(decisions)}")

    if "required_workflow_stages" in expect:
        required = [str(item) for item in expect["required_workflow_stages"]]
        ok = set(required).issubset(set(stage_names))
        checks.append(ok)
        notes.append(f"workflow_stages={stage_names}")

    if "coordinator_actions_include" in expect:
        required = [str(item) for item in expect["coordinator_actions_include"]]
        ok = set(required).issubset(set(actions))
        checks.append(ok)
        notes.append(f"coordinator_actions={actions}")

    if "coordinator_stages_include" in expect:
        required = [str(item) for item in expect["coordinator_stages_include"]]
        ok = set(required).issubset(set(decision_stages))
        checks.append(ok)
        notes.append(f"coordinator_stages={decision_stages}")

    if "min_candidate_count" in expect:
        candidate_count = int(trace.get("candidate_count") or (coordinator.get("retrieval") or {}).get("candidate_count") or 0)
        ok = candidate_count >= int(expect["min_candidate_count"])
        checks.append(ok)
        notes.append(f"candidate_count={candidate_count}")

    if "min_ranked_count" in expect:
        ranked_count = int(trace.get("ranking_candidate_count") or (coordinator.get("ranking") or {}).get("ranked_count") or 0)
        ok = ranked_count >= int(expect["min_ranked_count"])
        checks.append(ok)
        notes.append(f"ranked_count={ranked_count}")

    if "min_poi_count" in expect:
        ok = int(getattr(response, "poi_count", 0) or 0) >= int(expect["min_poi_count"])
        checks.append(ok)
        notes.append(f"poi_count={getattr(response, 'poi_count', 0)}")

    category_counts = _route_category_counts(response)
    if "category_min_counts" in expect:
        min_counts = expect["category_min_counts"]
        ok = all(category_counts.get(str(category), 0) >= int(count) for category, count in min_counts.items())
        checks.append(ok)
        notes.append(f"category_counts={category_counts}")

    if "category_groups_include" in expect:
        groups = expect["category_groups_include"]
        ok = all(_category_group_satisfied(category_counts, list(categories or [])) for categories in groups.values())
        checks.append(ok)
        notes.append(f"category_groups={groups}; category_counts={category_counts}")

    if expect.get("require_complete_timing"):
        scheduled_count = _scheduled_stop_count(response)
        ok = scheduled_count >= int(getattr(response, "poi_count", 0) or 0)
        checks.append(ok)
        notes.append(f"scheduled_stop_count={scheduled_count}")

    if "quality_status_in" in expect:
        quality_status = str((_coordinator_quality(response) or {}).get("status") or "")
        ok = quality_status in {str(item) for item in expect["quality_status_in"]}
        checks.append(ok)
        notes.append(f"quality_status={quality_status}")

    if "required_plan_steps" in expect:
        required = [str(item) for item in expect["required_plan_steps"]]
        actual = [str(item) for item in execution_plan.get("required_steps", []) or []]
        ok = set(required).issubset(set(actual))
        checks.append(ok)
        notes.append(f"plan_steps={actual}")

    if "enabled_tools_include" in expect:
        required = [str(item) for item in expect["enabled_tools_include"]]
        actual = _enabled_tool_names(response)
        ok = set(required).issubset(set(actual))
        checks.append(ok)
        notes.append(f"enabled_tools={actual}")

    if "skipped_tools_include" in expect:
        required = [str(item) for item in expect["skipped_tools_include"]]
        actual = _skipped_tool_names(response)
        ok = set(required).issubset(set(actual))
        checks.append(ok)
        notes.append(f"skipped_tools={actual}")

    if "required_data_include" in expect:
        required = [str(item) for item in expect["required_data_include"]]
        actual = _required_data_names(response)
        ok = set(required).issubset(set(actual))
        checks.append(ok)
        notes.append(f"required_data={actual}")

    if "optional_data_include" in expect:
        required = [str(item) for item in expect["optional_data_include"]]
        actual = _optional_data_names(response)
        ok = set(required).issubset(set(actual))
        checks.append(ok)
        notes.append(f"optional_data={actual}")

    if "skipped_data_include" in expect:
        required = [str(item) for item in expect["skipped_data_include"]]
        actual = _skipped_data_names(response)
        ok = set(required).issubset(set(actual))
        checks.append(ok)
        notes.append(f"skipped_data={actual}")

    if "tool_results_include" in expect:
        required = [str(item) for item in expect["tool_results_include"]]
        ok = set(required).issubset(set(tool_names))
        checks.append(ok)
        notes.append(f"tool_results={tool_names}")

    if "tool_results_absent" in expect:
        disallowed = {str(item) for item in expect["tool_results_absent"]}
        ok = not disallowed.intersection(set(tool_names))
        checks.append(ok)
        notes.append(f"tool_results_absent_intersection={sorted(disallowed.intersection(set(tool_names)))}")

    if "tool_status_in" in expect:
        allowed_by_tool = {str(name): {str(status) for status in statuses} for name, statuses in expect["tool_status_in"].items()}
        ok = True
        for tool_name, allowed in allowed_by_tool.items():
            statuses = {str(item.get("status")) for item in tool_results if str(item.get("tool")) == tool_name}
            if not statuses or not statuses.intersection(allowed):
                ok = False
        checks.append(ok)
        notes.append(f"tool_statuses={[(item.get('tool'), item.get('status')) for item in tool_results]}")

    if "min_recall_lane_count" in expect:
        recall_results = [item for item in tool_results if item.get("tool") == "poi_recall"]
        lane_count = 0
        if recall_results:
            lane_count = int((recall_results[0].get("payload") or {}).get("recall_lane_count") or 0)
        ok = lane_count >= int(expect["min_recall_lane_count"])
        checks.append(ok)
        notes.append(f"recall_lane_count={lane_count}")

    if "recall_active_lanes_include" in expect:
        recall_results = [item for item in tool_results if item.get("tool") == "poi_recall"]
        active_lanes: list[str] = []
        if recall_results:
            active_lanes = [str(item) for item in ((recall_results[0].get("payload") or {}).get("active_lanes") or []) if item]
        required = {str(item) for item in expect["recall_active_lanes_include"]}
        ok = required.issubset(set(active_lanes))
        checks.append(ok)
        notes.append(f"recall_active_lanes={active_lanes}")

    if "retrieval_backend_in" in expect:
        recall_results = [item for item in tool_results if item.get("tool") == "poi_recall"]
        backend = ""
        if recall_results:
            payload = recall_results[0].get("payload") or {}
            backend = str(payload.get("hybrid_backend") or "")
        ok = backend in {str(item) for item in expect["retrieval_backend_in"]}
        checks.append(ok)
        notes.append(f"retrieval_backend={backend}")

    if "dense_backend_in" in expect:
        recall_results = [item for item in tool_results if item.get("tool") == "poi_recall"]
        backend = ""
        if recall_results:
            payload = recall_results[0].get("payload") or {}
            backend = str(payload.get("dense_backend") or "")
        ok = backend in {str(item) for item in expect["dense_backend_in"]}
        checks.append(ok)
        notes.append(f"dense_backend={backend}")

    if "recall_noise_risk_in" in expect:
        recall_results = [item for item in tool_results if item.get("tool") == "poi_recall"]
        noise_risk = ""
        if recall_results:
            noise_risk = str((recall_results[0].get("payload") or {}).get("noise_risk") or "")
        ok = noise_risk in {str(item) for item in expect["recall_noise_risk_in"]}
        checks.append(ok)
        notes.append(f"recall_noise_risk={noise_risk}")

    if "max_recall_text_signal_share" in expect:
        recall_results = [item for item in tool_results if item.get("tool") == "poi_recall"]
        text_signal_share = 0.0
        if recall_results:
            text_signal_share = float((recall_results[0].get("payload") or {}).get("text_signal_share") or 0.0)
        ok = text_signal_share <= float(expect["max_recall_text_signal_share"])
        checks.append(ok)
        notes.append(f"text_signal_share={text_signal_share}")

    if "min_poi_rerank_output_count" in expect:
        rerank_results = [item for item in tool_results if item.get("tool") == "poi_rerank"]
        output_count = 0
        if rerank_results:
            output_count = int((rerank_results[0].get("payload") or {}).get("output_count") or 0)
        ok = output_count >= int(expect["min_poi_rerank_output_count"])
        checks.append(ok)
        notes.append(f"poi_rerank_output_count={output_count}")

    if "min_query_alignment_score" in expect:
        rerank_results = [item for item in tool_results if item.get("tool") == "poi_rerank"]
        query_alignment_score = 0.0
        if rerank_results:
            breakdown = (rerank_results[0].get("payload") or {}).get("top_score_breakdown_avg") or {}
            if isinstance(breakdown, dict):
                try:
                    query_alignment_score = float(breakdown.get("query_alignment_score") or 0.0)
                except (TypeError, ValueError):
                    query_alignment_score = 0.0
        ok = query_alignment_score >= float(expect["min_query_alignment_score"])
        checks.append(ok)
        notes.append(f"query_alignment_score={query_alignment_score}")

    if "min_ugc_analyzed_count" in expect:
        ugc_results = [item for item in tool_results if item.get("tool") == "ugc_signal"]
        analyzed_count = 0
        if ugc_results:
            analyzed_count = int((ugc_results[0].get("payload") or {}).get("analyzed_count") or 0)
        ok = analyzed_count >= int(expect["min_ugc_analyzed_count"])
        checks.append(ok)
        notes.append(f"ugc_analyzed_count={analyzed_count}")

    if "min_ugc_confidence" in expect:
        ugc_results = [item for item in tool_results if item.get("tool") == "ugc_signal"]
        confidence = 0.0
        if ugc_results:
            confidence = float(ugc_results[0].get("confidence") or 0.0)
        ok = confidence >= float(expect["min_ugc_confidence"])
        checks.append(ok)
        notes.append(f"ugc_confidence={confidence}")

    if "ugc_noise_risk_in" in expect:
        ugc_results = [item for item in tool_results if item.get("tool") == "ugc_signal"]
        noise_risk = ""
        if ugc_results:
            noise_risk = str(ugc_results[0].get("noise_risk") or "")
        ok = noise_risk in {str(item) for item in expect["ugc_noise_risk_in"]}
        checks.append(ok)
        notes.append(f"ugc_noise_risk={noise_risk}")

    if "max_ugc_keyword_fallback_count" in expect:
        ugc_results = [item for item in tool_results if item.get("tool") == "ugc_signal"]
        fallback_count = 0
        if ugc_results:
            fallback_count = int((ugc_results[0].get("payload") or {}).get("keyword_fallback_count") or 0)
        ok = fallback_count <= int(expect["max_ugc_keyword_fallback_count"])
        checks.append(ok)
        notes.append(f"ugc_keyword_fallback_count={fallback_count}")

    if "min_ugc_explanation_hint_count" in expect:
        ugc_results = [item for item in tool_results if item.get("tool") == "ugc_signal"]
        hint_count = 0
        if ugc_results:
            hint_count = len(list((ugc_results[0].get("payload") or {}).get("explanation_hints") or []))
        ok = hint_count >= int(expect["min_ugc_explanation_hint_count"])
        checks.append(ok)
        notes.append(f"ugc_explanation_hint_count={hint_count}")

    if "min_heat_signal_analyzed_count" in expect:
        heat_results = [item for item in tool_results if item.get("tool") == "heat_signal"]
        analyzed_count = 0
        if heat_results:
            analyzed_count = int((heat_results[0].get("payload") or {}).get("analyzed_count") or 0)
        ok = analyzed_count >= int(expect["min_heat_signal_analyzed_count"])
        checks.append(ok)
        notes.append(f"heat_signal_analyzed_count={analyzed_count}")

    if "max_heat_signal_high_queue_count" in expect:
        heat_results = [item for item in tool_results if item.get("tool") == "heat_signal"]
        high_queue_count = 0
        if heat_results:
            high_queue_count = int((heat_results[0].get("payload") or {}).get("high_queue_count") or 0)
        ok = high_queue_count <= int(expect["max_heat_signal_high_queue_count"])
        checks.append(ok)
        notes.append(f"heat_signal_high_queue_count={high_queue_count}")

    if "min_planning_matrix_pair_count" in expect:
        matrix = trace.get("planning_distance_matrix") or {}
        pair_count = int(matrix.get("pair_count") or 0) if isinstance(matrix, dict) else 0
        ok = pair_count >= int(expect["min_planning_matrix_pair_count"])
        checks.append(ok)
        notes.append(f"planning_matrix_pair_count={pair_count}")

    if "planning_matrix_source" in expect:
        matrix = trace.get("planning_distance_matrix") or {}
        source = str(matrix.get("source") or "") if isinstance(matrix, dict) else ""
        ok = source == str(expect["planning_matrix_source"])
        checks.append(ok)
        notes.append(f"planning_matrix_source={source}")

    if "min_route_attempt_count" in expect:
        attempts = trace.get("route_attempts") or _workflow_trace(response).get("route_attempts") or []
        attempt_count = len(attempts) if isinstance(attempts, list) else 0
        ok = attempt_count >= int(expect["min_route_attempt_count"])
        checks.append(ok)
        notes.append(f"route_attempt_count={attempt_count}")

    if "accepted_route_attempt_required" in expect:
        attempts = trace.get("route_attempts") or _workflow_trace(response).get("route_attempts") or []
        accepted = [item for item in attempts if isinstance(item, dict) and item.get("accepted")]
        ok = bool(accepted) == bool(expect["accepted_route_attempt_required"])
        checks.append(ok)
        notes.append(f"accepted_route_attempts={[item.get('phase') for item in accepted]}")

    if "min_memory_recent_event_count" in expect:
        memory_results = [item for item in tool_results if item.get("tool") == "memory_context"]
        recent_event_count = 0
        if memory_results:
            recent_event_count = int((memory_results[0].get("payload") or {}).get("recent_event_count") or 0)
        ok = recent_event_count >= int(expect["min_memory_recent_event_count"])
        checks.append(ok)
        notes.append(f"memory_recent_event_count={recent_event_count}")

    if "min_profile_bias_count" in expect:
        profile_bias = list(getattr(intent, "profile_bias", []) or [])
        ok = len(profile_bias) >= int(expect["min_profile_bias_count"])
        checks.append(ok)
        notes.append(f"profile_bias={profile_bias}")

    if "intent_profile_bias_absent" in expect:
        profile_bias = list(getattr(intent, "profile_bias", []) or [])
        ok = bool(profile_bias) is not bool(expect["intent_profile_bias_absent"])
        checks.append(ok)
        notes.append(f"profile_bias={profile_bias}")

    if "intent_context_bias_absent" in expect:
        context_bias = list(getattr(intent, "context_bias", []) or [])
        ok = bool(context_bias) is not bool(expect["intent_context_bias_absent"])
        checks.append(ok)
        notes.append(f"context_bias={context_bias}")

    if "min_repair_patch_count" in expect:
        repair_patches = trace.get("repair_patches") or []
        ok = len(repair_patches) >= int(expect["min_repair_patch_count"])
        checks.append(ok)
        notes.append(f"repair_patch_count={len(repair_patches)}")

    if "min_route_version_count" in expect:
        route_versions = []
        if context_after_route is not None:
            route_versions = list(getattr(context_after_route, "route_versions", []) or [])
        ok = len(route_versions) >= int(expect["min_route_version_count"])
        checks.append(ok)
        notes.append(f"route_version_count={len(route_versions)}")

    if "current_route_version_matches_response" in expect:
        session = getattr(context_after_route, "session", None)
        expected_version_id = getattr(response, "request_id", None) or getattr(response, "generated_at", None)
        actual_version_id = getattr(session, "current_route_version_id", None) if session is not None else None
        ok = actual_version_id == expected_version_id
        checks.append(ok)
        notes.append(f"current_route_version_id={actual_version_id}")

    if "current_route_title_matches_response" in expect:
        session = getattr(context_after_route, "session", None)
        actual_title = getattr(session, "current_route_title", None) if session is not None else None
        expected_title = getattr(response, "title", None)
        ok = actual_title == expected_title
        checks.append(ok)
        notes.append(f"current_route_title={actual_title}")

    if "current_route_summary_matches_response" in expect:
        session = getattr(context_after_route, "session", None)
        actual_summary = getattr(session, "current_route_summary", None) if session is not None else None
        expected_summary = getattr(response, "summary", None)
        ok = actual_summary == expected_summary
        checks.append(ok)
        notes.append(f"current_route_summary={actual_summary}")

    passed = all(checks) if checks else True
    return CaseResult(
        case_id=case["id"],
        case_type="workflow",
        passed=passed,
        checks=[str(item) for item in checks],
        notes=notes,
        metrics={
            "intent": intent.model_dump(),
            "trace": trace,
            "coordinator": coordinator,
            "execution_plan": execution_plan,
            "tool_results": tool_results,
            "latency_ms": elapsed_ms,
        },
    )


def _run_route_quality_case(case: dict[str, Any]) -> CaseResult:
    expect = case.get("expect", {})
    started = perf_counter()
    intent, response = route_service.plan_route(case["query"], city=case.get("city") or expect.get("city"))
    elapsed_ms = int((perf_counter() - started) * 1000)
    quality = _route_quality(response)
    trace = _response_trace(response)

    checks: list[bool] = []
    notes: list[str] = []

    if "max_latency_ms" in expect:
        ok = elapsed_ms <= int(expect["max_latency_ms"])
        checks.append(ok)
        notes.append(f"latency_ms={elapsed_ms}")

    if "min_alignment_score" in expect:
        score = float(quality.get("alignment_score", 0.0) or 0.0)
        ok = score >= float(expect["min_alignment_score"])
        checks.append(ok)
        notes.append(f"alignment_score={score}")

    if "max_travel_ratio" in expect:
        ratio = float(quality.get("travel_ratio", trace.get("travel_time_ratio", 0.0)) or 0.0)
        ok = ratio <= float(expect["max_travel_ratio"])
        checks.append(ok)
        notes.append(f"travel_ratio={ratio}")

    if "min_poi_count" in expect:
        ok = response.poi_count >= int(expect["min_poi_count"])
        checks.append(ok)
        notes.append(f"poi_count={response.poi_count}")

    category_counts = _route_category_counts(response)
    if "category_min_counts" in expect:
        min_counts = expect["category_min_counts"]
        ok = all(category_counts.get(category, 0) >= count for category, count in min_counts.items())
        checks.append(ok)
        notes.append(f"category_counts={category_counts}")

    if "category_groups_include" in expect:
        groups = expect["category_groups_include"]
        ok = all(_category_group_satisfied(category_counts, list(categories or [])) for categories in groups.values())
        checks.append(ok)
        notes.append(f"category_groups={groups}; category_counts={category_counts}")

    if expect.get("require_complete_timing"):
        scheduled_count = _scheduled_stop_count(response)
        ok = scheduled_count >= int(getattr(response, "poi_count", 0) or 0)
        checks.append(ok)
        notes.append(f"scheduled_stop_count={scheduled_count}")

    if "max_warning_count" in expect:
        warning_count = len(getattr(response, "warnings", []) or [])
        ok = warning_count <= int(expect["max_warning_count"])
        checks.append(ok)
        notes.append(f"warning_count={warning_count}")

    passed = all(checks) if checks else True
    return CaseResult(
        case_id=case["id"],
        case_type="route_quality",
        passed=passed,
        checks=[str(item) for item in checks],
        notes=notes,
        metrics={
            "intent": intent.model_dump(),
            "quality": quality,
            "response": response.model_dump(),
            "latency_ms": elapsed_ms,
        },
    )


def _run_failure_case(case: dict[str, Any]) -> CaseResult:
    expect = case.get("expect", {})
    checks: list[bool] = []
    notes: list[str] = []
    try:
        _, response = route_service.plan_route(case["query"], city=case.get("city") or expect.get("city"))
        if "clarification_needed" in expect:
            ok = bool(getattr(response, "clarification_needed", False)) == bool(expect["clarification_needed"])
            checks.append(ok)
            notes.append(f"clarification_needed={getattr(response, 'clarification_needed', False)}")
        else:
            checks.append(False)
            notes.append("expected_error_but_route_returned")
    except route_service.RoutePlanningError as err:
        if "status_code" in expect:
            ok = int(err.status_code) == int(expect["status_code"])
            checks.append(ok)
            notes.append(f"status_code={err.status_code}")
        if "detail_contains" in expect:
            detail = str(err.detail)
            ok = str(expect["detail_contains"]) in detail
            checks.append(ok)
            notes.append(f"detail={detail}")

    passed = all(checks) if checks else True
    return CaseResult(
        case_id=case["id"],
        case_type="failure",
        passed=passed,
        checks=[str(item) for item in checks],
        notes=notes,
    )


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

    category_counts = _route_category_counts(response)
    if "category_min_counts" in expect:
        min_counts = expect["category_min_counts"]
        ok = all(category_counts.get(category, 0) >= count for category, count in min_counts.items())
        checks.append(ok)
        notes.append(f"category_counts={category_counts}")

    if "category_max_counts" in expect:
        max_counts = expect["category_max_counts"]
        ok = all(category_counts.get(category, 0) <= count for category, count in max_counts.items())
        checks.append(ok)
        notes.append(f"category_counts={category_counts}")

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
    modify_started = perf_counter()
    modify_intent, modify_response = route_service.plan_route(
        case["modify_query"],
        city=base_intent.city,
        current_route=base_response.model_dump(),
        original_query=case["base_query"],
    )
    modify_latency_ms = int((perf_counter() - modify_started) * 1000)

    checks: list[bool] = []
    notes: list[str] = []

    if "max_latency_ms" in expect:
        ok = modify_latency_ms <= int(expect["max_latency_ms"])
        checks.append(ok)
        notes.append(f"latency_ms={modify_latency_ms}")

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

    if "min_poi_count" in expect:
        ok = modify_response.poi_count >= int(expect["min_poi_count"])
        checks.append(ok)
        notes.append(f"poi_count={modify_response.poi_count}")

    category_counts = _route_category_counts(modify_response)
    if "category_min_counts" in expect:
        min_counts = expect["category_min_counts"]
        ok = all(category_counts.get(category, 0) >= count for category, count in min_counts.items())
        checks.append(ok)
        notes.append(f"category_counts={category_counts}")

    if "category_max_counts" in expect:
        max_counts = expect["category_max_counts"]
        ok = all(category_counts.get(category, 0) <= count for category, count in max_counts.items())
        checks.append(ok)
        notes.append(f"category_counts={category_counts}")

    if "category_groups_include" in expect:
        groups = expect["category_groups_include"]
        ok = all(_category_group_satisfied(category_counts, list(categories or [])) for categories in groups.values())
        checks.append(ok)
        notes.append(f"category_groups={groups}; category_counts={category_counts}")

    if expect.get("require_complete_timing"):
        scheduled_count = _scheduled_stop_count(modify_response)
        ok = scheduled_count >= int(getattr(modify_response, "poi_count", 0) or 0)
        checks.append(ok)
        notes.append(f"scheduled_stop_count={scheduled_count}")

    if "min_changed_poi_count" in expect:
        base_ids = set(_route_poi_ids(base_response))
        modify_ids = set(_route_poi_ids(modify_response))
        changed_count = len(base_ids.symmetric_difference(modify_ids))
        ok = changed_count >= int(expect["min_changed_poi_count"])
        checks.append(ok)
        notes.append(f"changed_poi_count={changed_count}")

    modification = _response_trace(modify_response).get("modification") or {}
    route_delta = modification.get("route_delta") if isinstance(modification, dict) else {}
    if isinstance(route_delta, dict) and route_delta:
        delta_summary = str(route_delta.get("summary") or "")
        delta_previous_count = int(route_delta.get("previous_count") or 0)
        delta_changed_count = int(route_delta.get("changed_count") or 0)
        notes.append(f"route_delta={route_delta}")
        if "min_route_delta_previous_count" in expect:
            ok = delta_previous_count >= int(expect["min_route_delta_previous_count"])
            checks.append(ok)
            notes.append(f"route_delta_previous_count={delta_previous_count}")
        if "min_changed_poi_count" in expect:
            ok = delta_changed_count >= int(expect["min_changed_poi_count"])
            checks.append(ok)
            notes.append(f"route_delta_changed_count={delta_changed_count}")
        if "require_route_delta_summary" in expect:
            ok = bool(delta_summary.strip())
            checks.append(ok)
            notes.append(f"route_delta_summary={delta_summary}")

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
            "modify_latency_ms": modify_latency_ms,
        },
    )


def _run_intent_repair_case(case: dict[str, Any]) -> CaseResult:
    expect = case.get("expect", {})
    intent, _ = route_service.plan_route(case["query"], city=case.get("city") or expect.get("city"))
    quality = {
        "gaps": case.get("quality_gaps", []),
        "missing_categories": case.get("missing_categories", []),
    }
    agent = IntentRepairAgent()
    patches = agent.build_patches(intent, quality)
    repaired = agent.apply_patches(intent, patches)
    repaired_dump = repaired.model_dump(mode="json") if repaired is not None and hasattr(repaired, "model_dump") else {}
    patch_dump = [patch.model_dump(mode="json") for patch in patches]
    patch_fields = [str(item.get("field")) for item in patch_dump]
    patch_values = [str(item.get("value")) for item in patch_dump]

    checks: list[bool] = []
    notes: list[str] = []

    if "min_patch_count" in expect:
        ok = len(patches) >= int(expect["min_patch_count"])
        checks.append(ok)
        notes.append(f"patch_count={len(patches)}")

    if "patch_fields_include" in expect:
        required = [str(item) for item in expect["patch_fields_include"]]
        ok = set(required).issubset(set(patch_fields))
        checks.append(ok)
        notes.append(f"patch_fields={patch_fields}")

    if "patch_values_include" in expect:
        required = [str(item) for item in expect["patch_values_include"]]
        ok = set(required).issubset(set(patch_values))
        checks.append(ok)
        notes.append(f"patch_values={patch_values}")

    if "disallowed_patch_fields_absent" in expect:
        disallowed = {str(item) for item in expect["disallowed_patch_fields_absent"]}
        ok = not disallowed.intersection(patch_fields)
        checks.append(ok)
        notes.append(f"disallowed_intersection={sorted(disallowed.intersection(patch_fields))}")

    if "repaired_preferences_include" in expect:
        actual = [str(item) for item in repaired_dump.get("preferences", []) or []]
        ok = set(str(item) for item in expect["repaired_preferences_include"]).issubset(set(actual))
        checks.append(ok)
        notes.append(f"repaired_preferences={actual}")

    if "repaired_avoid_include" in expect:
        actual = [str(item) for item in repaired_dump.get("avoid", []) or []]
        ok = set(str(item) for item in expect["repaired_avoid_include"]).issubset(set(actual))
        checks.append(ok)
        notes.append(f"repaired_avoid={actual}")

    if "route_strategy" in expect:
        ok = repaired_dump.get("route_strategy") == expect["route_strategy"]
        checks.append(ok)
        notes.append(f"route_strategy={repaired_dump.get('route_strategy')}")

    passed = all(checks) if checks else True
    return CaseResult(
        case_id=case["id"],
        case_type="intent_repair",
        passed=passed,
        checks=[str(item) for item in checks],
        notes=notes,
        metrics={
            "quality": quality,
            "patches": patch_dump,
            "repaired_intent": repaired_dump,
        },
    )


def _tool_payload(tool_result: dict[str, Any], tool_name: str) -> dict[str, Any]:
    if str(tool_result.get("tool") or "") != tool_name:
        return {}
    payload = tool_result.get("payload") or {}
    return payload if isinstance(payload, dict) else {}


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
            elif case.get("type") == "workflow":
                results.append(_run_workflow_case(case))
            elif case.get("type") == "route_quality":
                results.append(_run_route_quality_case(case))
            elif case.get("type") == "failure":
                results.append(_run_failure_case(case))
            elif case.get("type") == "intent_repair":
                results.append(_run_intent_repair_case(case))
            else:
                results.append(_run_intent_case(case))

        passed = sum(1 for item in results if item.passed)
        total = len(results)
        type_counts: dict[str, int] = {}
        type_passed: dict[str, int] = {}
        total_checks = 0
        total_latency_ms = 0
        latency_case_count = 0
        recall_lane_total = 0
        recall_lane_case_count = 0
        rerank_output_total = 0
        rerank_case_count = 0
        query_alignment_total = 0.0
        query_alignment_case_count = 0
        retrieval_backend_counts: dict[str, int] = {}
        dense_backend_counts: dict[str, int] = {}
        rerank_backend_counts: dict[str, int] = {}
        failed_case_ids: list[str] = []
        for item in results:
            type_counts[item.case_type] = type_counts.get(item.case_type, 0) + 1
            if item.passed:
                type_passed[item.case_type] = type_passed.get(item.case_type, 0) + 1
            else:
                failed_case_ids.append(item.case_id)
            total_checks += len(item.checks)
            latency = item.metrics.get("latency_ms")
            if isinstance(latency, (int, float)):
                total_latency_ms += int(latency)
                latency_case_count += 1
            tool_results = item.metrics.get("tool_results") if isinstance(item.metrics, dict) else []
            if isinstance(tool_results, list):
                for tool_result in tool_results:
                    if not isinstance(tool_result, dict):
                        continue
                    if str(tool_result.get("tool") or "") == "poi_recall":
                        payload = _tool_payload(tool_result, "poi_recall")
                        lane_count = payload.get("recall_lane_count")
                        if isinstance(lane_count, (int, float)):
                            recall_lane_total += int(lane_count)
                            recall_lane_case_count += 1
                        retrieval_backend = str(payload.get("hybrid_backend") or "")
                        dense_backend = str(payload.get("dense_backend") or "")
                        if retrieval_backend:
                            retrieval_backend_counts[retrieval_backend] = retrieval_backend_counts.get(retrieval_backend, 0) + 1
                        if dense_backend:
                            dense_backend_counts[dense_backend] = dense_backend_counts.get(dense_backend, 0) + 1
                    if str(tool_result.get("tool") or "") == "poi_rerank":
                        payload = _tool_payload(tool_result, "poi_rerank")
                        output_count = payload.get("output_count")
                        if isinstance(output_count, (int, float)):
                            rerank_output_total += int(output_count)
                            rerank_case_count += 1
                        rerank_backend = str(payload.get("rerank_backend") or "")
                        if rerank_backend:
                            rerank_backend_counts[rerank_backend] = rerank_backend_counts.get(rerank_backend, 0) + 1
                        breakdown_avg = payload.get("top_score_breakdown_avg") or {}
                        if isinstance(breakdown_avg, dict):
                            try:
                                query_alignment_total += float(breakdown_avg.get("query_alignment_score") or 0.0)
                                query_alignment_case_count += 1
                            except (TypeError, ValueError):
                                pass

        pass_rate_by_type = {
            case_type: round(type_passed.get(case_type, 0) / count, 3) if count else 0.0
            for case_type, count in type_counts.items()
        }

        def _avg(total_value: float, count: int) -> float:
            return round(total_value / count, 3) if count else 0.0

        return {
            "dataset": DATA_PATH.name,
            "total_cases": total,
            "passed_cases": passed,
            "pass_rate": round(passed / total, 3) if total else 0.0,
            "summary": {
                "intent_cases": type_counts.get("intent", 0),
                "modify_cases": type_counts.get("modify", 0),
                "workflow_cases": type_counts.get("workflow", 0),
                "route_quality_cases": type_counts.get("route_quality", 0),
                "failure_cases": type_counts.get("failure", 0),
                "intent_repair_cases": type_counts.get("intent_repair", 0),
                "passed_intent_cases": type_passed.get("intent", 0),
                "passed_modify_cases": type_passed.get("modify", 0),
                "passed_workflow_cases": type_passed.get("workflow", 0),
                "passed_route_quality_cases": type_passed.get("route_quality", 0),
                "passed_failure_cases": type_passed.get("failure", 0),
                "passed_intent_repair_cases": type_passed.get("intent_repair", 0),
                "pass_rate_by_type": pass_rate_by_type,
                "avg_checks_per_case": round(total_checks / total, 3) if total else 0.0,
                "avg_latency_ms": _avg(total_latency_ms, latency_case_count),
                "avg_recall_lane_count": _avg(recall_lane_total, recall_lane_case_count),
                "avg_rerank_output_count": _avg(rerank_output_total, rerank_case_count),
                "avg_query_alignment_score": _avg(query_alignment_total, query_alignment_case_count),
                "retrieval_backend_counts": retrieval_backend_counts,
                "dense_backend_counts": dense_backend_counts,
                "rerank_backend_counts": rerank_backend_counts,
                "failed_case_ids": failed_case_ids,
            },
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
    output_path = REPO_ROOT / ".tmp" / "eval_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
