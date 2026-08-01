"""Controlled coordinator for the route-planning workflow."""

from __future__ import annotations

from typing import Any

from core.schemas import ParsedIntent
from core.intent_ir import build_intent_ir
from .planning import DataRequirement, ExecutionPlan, PlanNode, ToolCallPlan, ToolSkip
from .state import CoordinatorAction, CoordinatorDecision, QualityReport, RouteState


def _dump_model(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return dict(value) if isinstance(value, dict) else {}


def _memory_opted_out(query: str) -> bool:
    text = str(query or "").lower()
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
    return any(term in text for term in opt_out_terms)


class RouteCoordinator:
    """Small workflow supervisor with a fixed action space.

    It does not rank POIs or build routes. It only checks handoffs between
    stages and records explicit decisions that can be tested and replayed.
    """

    def start(self, intent: ParsedIntent) -> RouteState:
        query = str(getattr(intent, "original_query", "") or getattr(intent, "modification_query", "") or "")
        state = RouteState(
            query=query,
            original_query=getattr(intent, "original_query", None),
            session_id=getattr(intent, "session_id", None),
            task_hint="route_modification" if getattr(intent, "current_route", None) is not None else "intent_extraction",
            city=getattr(intent, "city", None),
            parse_source=getattr(intent, "parse_source", None),
            intent_confidence=getattr(intent, "intent_confidence", None),
            intent=_dump_model(intent),
            intent_ir=build_intent_ir(intent).model_dump(mode="json"),
        )
        self.after_intent(state, intent)
        return state

    def build_execution_plan(
        self,
        state: RouteState,
        intent: ParsedIntent,
        *,
        use_map_api: bool = False,
    ) -> ExecutionPlan:
        signal_count = (
            len(getattr(intent, "required_categories", []) or [])
            + len(getattr(intent, "preferences", []) or [])
            + len(getattr(intent, "must_include", []) or [])
        )
        has_city = bool(getattr(intent, "city", None))
        needs_clarification = not has_city or signal_count == 0
        required_steps = ["intent", "clarification"] if needs_clarification else [
            "intent",
            "poi_retrieval",
            "ranking",
            "candidate_building",
            "planning",
            "validation",
            "explanation",
        ]
        optional_tools: list[ToolCallPlan] = []
        skipped_tools: list[ToolSkip] = []
        required_data: list[DataRequirement] = []
        optional_data: list[DataRequirement] = []
        skipped_data: list[ToolSkip] = []

        if needs_clarification:
            required_data.append(
                DataRequirement(
                    name="intent_schema",
                    reason="Clarification needs the parsed intent and uncertainty signals.",
                    source="intent",
                    used_by=["clarification"],
                )
            )
            skipped_tools.extend(
                [
                    ToolSkip(tool="memory_context", reason="Memory waits until the task is specific enough.", risk="medium"),
                    ToolSkip(tool="map_distance_matrix", reason="Route tools wait until the user confirms city and route preferences."),
                    ToolSkip(tool="ugc_signal", reason="UGC signals are noisy before the route intent is specific enough.", risk="medium"),
                    ToolSkip(tool="heat_signal", reason="Heat and queue checks wait until the route intent is specific enough.", risk="medium"),
                    ToolSkip(tool="weather", reason="Weather lookup waits until route generation is actually needed."),
                ]
            )
            skipped_data.extend(
                [
                    ToolSkip(tool="poi_candidates", reason="POI recall waits until city and route preference are specific enough."),
                    ToolSkip(tool="profile_memory", reason="Memory is not useful before the task is specific.", risk="medium"),
                    ToolSkip(tool="ugc_signals", reason="UGC signals are noisy before the route intent is specific enough.", risk="medium"),
                    ToolSkip(tool="heat_signals", reason="Heat and queue checks wait until the route intent is specific enough.", risk="medium"),
                ]
            )
        else:
            has_session = bool(getattr(intent, "session_id", None))
            memory_opt_out = _memory_opted_out(str(getattr(intent, "original_query", "") or state.query or ""))
            preferences = set(getattr(intent, "preferences", []) or []) | set(getattr(intent, "soft_preferences", []) or [])
            avoids = set(getattr(intent, "avoid", []) or [])
            heat_sensitive = bool(
                getattr(intent, "avoid_queue", False)
                or getattr(intent, "avoid_crowded", False)
                or getattr(intent, "prefer_quiet", False)
                or {"avoid_queue", "avoid_crowded"} & avoids
                or {"quiet", "solo"} & preferences
            )
            required_data.extend(
                [
                    DataRequirement(
                        name="intent_schema",
                        reason="Route generation needs normalized city, categories, preferences, and constraints.",
                        source="intent",
                        used_by=["retrieval", "ranking", "planning", "validation"],
                    ),
                    DataRequirement(
                        name="poi_candidates",
                        reason="Route planning requires a filtered POI candidate pool for the target city.",
                        source="local_poi",
                        used_by=["retrieval", "ranking", "candidate_building", "planning"],
                        filters={
                            "city": getattr(intent, "city", None),
                            "required_categories": list(getattr(intent, "required_categories", []) or []),
                            "preferences": list(getattr(intent, "preferences", []) or []),
                            "avoid": list(getattr(intent, "avoid", []) or []),
                        },
                        max_items=160,
                        fallback="semantic_and_quality_fallback",
                    ),
                ]
            )
            optional_data.extend(
                [
                    DataRequirement(
                        name="semantic_recall",
                        reason="Long-tail user wording can improve POI recall without sending raw text to the planner.",
                        required=False,
                        source="local_semantic_index",
                        used_by=["retrieval"],
                        max_items=90,
                        fallback="category_recall",
                    ),
                    DataRequirement(
                        name="ugc_signals",
                        reason="Selected-route UGC signals can expose queue/crowd/fit risks without sending raw reviews.",
                        required=False,
                        source="local_review_signals",
                        used_by=["validation", "explanation"],
                        max_items=8,
                        fallback="structured_poi_fields",
                    ),
                    DataRequirement(
                        name="route_distance_matrix",
                        reason="Distance and travel time improve route validation and explanation.",
                        required=False,
                        source="map_or_local",
                        used_by=["planning", "validation", "explanation"],
                        max_items=8,
                        fallback="local_haversine",
                    ),
                ]
            )
            if heat_sensitive:
                optional_data.append(
                    DataRequirement(
                        name="heat_signals",
                        reason="Queue and crowd pressure matter for this request.",
                        required=False,
                        source="realtime_heat_or_local_fields",
                        used_by=["validation", "explanation"],
                        max_items=8,
                        fallback="local_poi_fields",
                    )
                )
            else:
                skipped_data.append(ToolSkip(tool="heat_signals", reason="No explicit queue/crowd/quiet constraint was found."))
            if has_session and not memory_opt_out:
                optional_data.append(
                    DataRequirement(
                        name="profile_memory",
                        reason="Stable session/profile signals can softly bias retrieval without overriding this turn.",
                        required=False,
                        source="session_context",
                        used_by=["understanding", "retrieval", "ranking"],
                        max_items=8,
                        fallback="current_turn_only",
                    )
                )
                optional_tools.append(
                    ToolCallPlan(
                        tool="memory_context",
                        reason="Summarize usable session/profile memory for traceability and soft personalization.",
                        enabled=True,
                        priority=80,
                        used_by=["understanding", "retrieval", "ranking"],
                        max_items=8,
                        budget_units=1,
                        fallback="current_turn_only",
                    )
                )
            else:
                skipped_tools.append(
                    ToolSkip(
                        tool="memory_context",
                        reason="No session memory is available." if not has_session else "The user opted out of memory/profile usage.",
                        risk="low" if not has_session else "medium",
                    )
                )
                skipped_data.append(
                    ToolSkip(
                        tool="profile_memory",
                        reason="No session memory is available." if not has_session else "The user opted out of memory/profile usage.",
                        risk="low" if not has_session else "medium",
                    )
                )
            optional_tools.append(
                ToolCallPlan(
                    tool="map_distance_matrix",
                    reason="Calibrate travel time and distance for the selected route segments.",
                    enabled=True,
                    priority=90,
                    used_by=["planning", "validation", "explanation"],
                    max_items=8,
                    budget_units=1,
                    prefer_external=use_map_api,
                    fallback="local_haversine",
                )
            )
            optional_tools.append(
                ToolCallPlan(
                    tool="ugc_signal",
                    reason="Analyze selected POIs for compact UGC-derived fit and risk signals.",
                    enabled=True,
                    priority=60,
                    used_by=["validation", "explanation"],
                    max_items=8,
                    budget_units=1,
                    fallback="structured_poi_fields",
                )
            )
            if heat_sensitive:
                optional_tools.append(
                    ToolCallPlan(
                        tool="heat_signal",
                        reason="Check selected route POIs for queue and crowd pressure.",
                        enabled=True,
                        priority=65,
                        used_by=["validation", "explanation"],
                        max_items=8,
                        budget_units=1,
                        fallback="local_poi_fields",
                    )
                )
            else:
                skipped_tools.append(ToolSkip(tool="heat_signal", reason="No explicit queue/crowd/quiet constraint was found."))
            weather_signals = {
                "rainy_day",
                "indoor",
                "outdoor",
                "weather",
                "hot",
                "cold",
            }
            if preferences & weather_signals or getattr(intent, "start_time", None) or getattr(intent, "end_time", None):
                skipped_tools.append(ToolSkip(tool="weather", reason="Weather tool is not implemented yet; current route uses POI rainy-day and indoor metadata.", risk="medium"))
            else:
                skipped_tools.append(ToolSkip(tool="weather", reason="No explicit weather/date dependency was found."))
            skipped_data.append(ToolSkip(tool="weather_snapshot", reason="Weather tool is not implemented yet or not needed for this query.", risk="medium"))

        dag_nodes = self._build_plan_dag(required_steps, optional_tools, skipped_tools)
        plan = ExecutionPlan(
            required_steps=required_steps,
            required_data=required_data,
            optional_data=optional_data,
            skipped_data=skipped_data,
            optional_tools=optional_tools,
            skipped_tools=skipped_tools,
            dag_nodes=dag_nodes,
            tool_budget=2 if optional_tools else 0,
            max_repair_rounds=1,
            quality_gates={
                "min_alignment_score": 0.68,
                "replan_below_alignment": 0.62,
                "max_travel_ratio": 0.38,
            },
            fallback_policy={
                "map_distance_matrix": "local_haversine",
                "memory_context": "current_turn_only",
                "ugc_signal": "structured_poi_fields",
                "heat_signal": "local_poi_fields",
                "weather": "use_poi_indoor_rainy_day_metadata",
            },
            decision_basis={
                "city": getattr(intent, "city", None),
                "signal_count": signal_count,
                "use_map_api": use_map_api,
                "parse_source": getattr(intent, "parse_source", None),
            },
        )
        plan.tool_budget = sum(max(1, int(item.budget_units or 1)) for item in optional_tools)
        plan.mark_node_status("intent", "completed", source=str(getattr(intent, "parse_source", "") or "unknown"))
        state.set_execution_plan(plan)
        state.add_decision(
            CoordinatorDecision(
                stage="execution_plan",
                action=CoordinatorAction.CONTINUE if not needs_clarification else CoordinatorAction.ASK_CLARIFICATION,
                reason="Created a bounded execution plan for this route request.",
                blocking=needs_clarification,
                required_action="answer_clarification" if needs_clarification else None,
                checks=["execution_plan_created"],
                issues=["plan_waits_for_clarification"] if needs_clarification else [],
                evidence=plan.model_dump(mode="json"),
            )
        )
        return plan

    def _build_plan_dag(
        self,
        required_steps: list[str],
        optional_tools: list[ToolCallPlan],
        skipped_tools: list[ToolSkip],
    ) -> list[PlanNode]:
        nodes: list[PlanNode] = []
        step_index = {step: index for index, step in enumerate(required_steps)}
        for index, step in enumerate(required_steps):
            depends_on = [required_steps[index - 1]] if index > 0 else []
            nodes.append(
                PlanNode(
                    node_id=step,
                    kind="step",
                    label=step,
                    depends_on=depends_on,
                )
            )

        planning_anchor = "planning" if "planning" in step_index else (required_steps[-1] if required_steps else "intent")
        for tool in optional_tools:
            depends_on = ["intent"] if tool.tool == "memory_context" else [planning_anchor]
            nodes.append(
                PlanNode(
                    node_id=f"tool:{tool.tool}",
                    kind="tool",
                    label=tool.tool,
                    depends_on=depends_on,
                    status="pending" if tool.enabled else "skipped",
                    metadata={
                        "priority": tool.priority,
                        "blocking": tool.blocking,
                        "used_by": list(tool.used_by or []),
                    },
                )
            )

        for skipped in skipped_tools:
            nodes.append(
                PlanNode(
                    node_id=f"tool:{skipped.tool}",
                    kind="tool",
                    label=skipped.tool,
                    depends_on=[],
                    status="skipped",
                    metadata={"reason": skipped.reason, "risk": skipped.risk},
                )
            )

        return nodes

    def after_intent(self, state: RouteState, intent: ParsedIntent) -> CoordinatorDecision:
        issues: list[str] = []
        checks: list[str] = []
        if getattr(intent, "city", None):
            checks.append("city_present")
        else:
            issues.append("missing_city")
        signal_count = (
            len(getattr(intent, "required_categories", []) or [])
            + len(getattr(intent, "preferences", []) or [])
            + len(getattr(intent, "must_include", []) or [])
        )
        if signal_count:
            checks.append("intent_signals_present")
        else:
            issues.append("weak_intent_signals")
        if getattr(intent, "uncertain_fields", None):
            issues.append("intent_has_uncertain_fields")

        if "missing_city" in issues:
            decision = CoordinatorDecision(
                stage="understanding",
                action=CoordinatorAction.ASK_CLARIFICATION,
                reason="Intent is missing a supported city, so route generation should ask a clarifying question.",
                blocking=True,
                required_action="ask_city",
                explain_to_user=True,
                checks=checks,
                issues=issues,
                evidence={"signal_count": signal_count},
            )
        elif "weak_intent_signals" in issues:
            decision = CoordinatorDecision(
                stage="understanding",
                action=CoordinatorAction.ASK_CLARIFICATION,
                reason="The request has too few route signals; one concise clarification can reduce arbitrary planning.",
                blocking=False,
                required_action="ask_primary_preference",
                explain_to_user=True,
                checks=checks,
                issues=issues,
                evidence={"signal_count": signal_count},
            )
        else:
            decision = CoordinatorDecision(
                stage="understanding",
                action=CoordinatorAction.CONTINUE,
                reason="Intent has enough structured signals to enter retrieval.",
                checks=checks,
                issues=issues,
                evidence={"signal_count": signal_count},
            )
        state.add_decision(decision)
        return decision

    def after_retrieval(
        self,
        state: RouteState,
        *,
        candidate_count: int,
        ranked_count: int,
        recall_sources: list[str] | None = None,
    ) -> CoordinatorDecision:
        state.retrieval = {
            "candidate_count": candidate_count,
            "recall_sources": recall_sources or ["local_poi", "semantic_retrieval"],
        }
        state.ranking = {"ranked_count": ranked_count}
        checks: list[str] = []
        issues: list[str] = []
        if candidate_count > 0:
            checks.append("candidates_present")
        else:
            issues.append("no_candidates")
        if ranked_count >= 8:
            checks.append("ranking_pool_sufficient")
        elif ranked_count > 0:
            issues.append("thin_ranking_pool")
        else:
            issues.append("empty_ranking_pool")

        if "no_candidates" in issues or "empty_ranking_pool" in issues:
            action = CoordinatorAction.EXPAND_RETRIEVAL
            reason = "Retrieval did not produce a usable ranking pool; broaden recall before planning."
            blocking = True
            required_action = "relax_filters_or_expand_recall"
        elif "thin_ranking_pool" in issues:
            action = CoordinatorAction.EXPAND_RETRIEVAL
            reason = "Ranking pool is thin; planning can continue, but recall should be expanded when possible."
            blocking = False
            required_action = "add_fallback_candidates"
        else:
            action = CoordinatorAction.CONTINUE
            reason = "Retrieval and ranking produced enough candidates for route planning."
            blocking = False
            required_action = None

        decision = CoordinatorDecision(
            stage="retrieval",
            action=action,
            reason=reason,
            blocking=blocking,
            required_action=required_action,
            checks=checks,
            issues=issues,
            evidence=state.retrieval | state.ranking,
        )
        state.add_decision(decision)
        return decision

    def after_planning(
        self,
        state: RouteState,
        *,
        planned_route: dict[str, Any],
        quality: dict[str, Any],
        critique: dict[str, Any],
        route_stats: dict[str, Any],
    ) -> CoordinatorDecision:
        main_stops = list(planned_route.get("main", []) or [])
        variants = list(planned_route.get("variants", []) or [])
        state.planning = {
            "main_stop_count": len(main_stops),
            "variant_count": len(variants),
            "selected_variant_name": planned_route.get("selected_variant_name"),
            "selected_variant_source": planned_route.get("selected_variant_source"),
            "route_stats": route_stats,
        }
        report = QualityReport.from_verifier(quality, critique, route_stats)
        state.quality_report = report

        checks: list[str] = []
        issues: list[str] = []
        if main_stops:
            checks.append("main_route_present")
        else:
            issues.append("missing_main_route")
        if variants:
            checks.append("variants_present")
        else:
            issues.append("missing_variants")
        if report.alignment_score >= 0.7:
            checks.append("alignment_above_accept_threshold")
        else:
            issues.append("low_alignment_score")
        issues.extend(report.hard_issues[:5])

        if not main_stops:
            action = CoordinatorAction.REPLAN
            reason = "Planner did not produce a main route."
            blocking = True
        elif report.status == "needs_replan":
            action = CoordinatorAction.REPLAN
            reason = "Route quality report says the route needs replanning."
            blocking = False
        elif report.status == "needs_repair":
            action = CoordinatorAction.REPAIR
            reason = "Route quality report found repairable gaps."
            blocking = False
        else:
            action = CoordinatorAction.EXPLAIN
            reason = "Route passes quality checks and can move to explanation."
            blocking = False

        decision = CoordinatorDecision(
            stage="planning",
            action=action,
            reason=reason,
            blocking=blocking,
            checks=checks,
            issues=issues,
            evidence={
                "quality_status": report.status,
                "alignment_score": report.alignment_score,
                "repair_suggestions": report.repair_suggestions,
                **state.planning,
            },
        )
        state.add_decision(decision)
        return decision

    def after_explanation(self, state: RouteState, explanation: str) -> CoordinatorDecision:
        state.explanation = explanation
        issues: list[str] = []
        checks: list[str] = []
        if explanation and len(explanation.strip()) >= 12:
            checks.append("explanation_present")
        else:
            issues.append("weak_explanation")
        if state.quality_report is not None:
            checks.append("quality_report_attached")
        else:
            issues.append("missing_quality_report")

        decision = CoordinatorDecision(
            stage="explanation",
            action=CoordinatorAction.CONTINUE if not issues else CoordinatorAction.REPAIR,
            reason="Final explanation is ready." if not issues else "Explanation is too weak for a trustworthy response.",
            blocking=False,
            checks=checks,
            issues=issues,
            evidence={"explanation_length": len(explanation or "")},
        )
        state.add_decision(decision)
        return decision

    def after_clarification(self, state: RouteState, question: str) -> CoordinatorDecision:
        state.explanation = question
        decision = CoordinatorDecision(
            stage="clarification",
            action=CoordinatorAction.ASK_CLARIFICATION,
            reason="The request needs one concise user answer before route planning continues.",
            blocking=True,
            required_action="ask_user_clarification",
            explain_to_user=True,
            checks=["clarification_question_present"] if question else [],
            issues=[] if question else ["missing_clarification_question"],
            evidence={"question": question},
        )
        state.add_decision(decision)
        return decision
