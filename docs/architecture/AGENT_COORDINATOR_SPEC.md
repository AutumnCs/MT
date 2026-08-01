# Agent Coordinator Spec

This document defines the next orchestration layer for Muse. The goal is not to
make the system more free-form. The goal is to make the route workflow easier to
inspect, test, repair, and extend.

## 1. Positioning

The coordinator is a controlled workflow supervisor.

It does not:

- plan routes
- rank POIs
- call map APIs directly
- generate final user-facing prose
- replace deterministic checks

It does:

- keep one `RouteState` for the request
- check whether each stage produced the needed output
- decide whether the workflow should continue, clarify, expand retrieval, repair, replan, explain, or fail
- write a structured `decision_log`
- expose its decisions in `workflow_trace`

## 2. Recommended Chain

The chain should stay short enough to understand:

```text
Input
 -> Understand intent
 -> Coordinate
 -> Retrieve POI
 -> Rank POI
 -> Run RouteAttempt
      -> plan route
      -> run bounded route tools
      -> verify route
 -> Coordinate
 -> Repair/Replan if needed
 -> Explain
 -> Coordinate
 -> Response
```

This is deliberately not a free multi-agent loop. The route domain is constraint-heavy,
so the main path should remain deterministic and replayable.

The recommended runtime shape is:

- controlled coordinator decisions
- bounded execution DAG for dependency and parallel-readiness tracking
- optional repair/replan checkpoints

That gives us execution structure without turning the system into an open-ended
agent loop.

## 3. Module Boundaries

Use these boundaries to avoid local complexity leaking across the system:

| Layer | Responsibility | Should not do |
| --- | --- | --- |
| Intent | Natural language to strict schema | Route planning |
| Retrieval | Candidate POI recall | Final ranking or route order |
| Ranking | Score candidate POIs | Explain the whole workflow |
| Planning | Build route variants | Guess missing user intent |
| Verification | Quality and constraint checks | Mutate intent silently |
| Coordinator | Decide next workflow action | Rank or plan |
| Explanation | User-facing explanation | Hide quality failures |
| Context/Memory | Soft bias and session continuity | Override hard constraints |

## 4. RouteState

`RouteState` is the shared snapshot for one request:

```text
request_id
query / original_query / session_id
task_hint
intent
retrieval
ranking
planning
execution_plan
tool_results
quality_report
explanation
decision_log
errors
```

Every stage should update only its own section. The coordinator reads the whole
state but writes only `decision_log`, high-level errors, and normalized quality
status.

## 5. Coordinator Actions

The allowed action set is intentionally small:

```text
continue
ask_clarification
expand_retrieval
rerank
replan
repair
explain
fail_with_reason
```

Any new action must explain why the current action set is insufficient and add
eval coverage.

## 6. Patch-Based Intent Repair

Intent repair should never rewrite the whole parsed intent. It must emit a small
list of `IntentPatch` objects and pass a validator before the route is rerun.

Allowed patch fields:

```text
required_categories
preferences
soft_preferences
avoid
route_strategy
```

Disallowed repair fields:

```text
city
budget
start_time
end_time
hard constraints not present in the user query
```

Every patch should carry:

```text
field
op
value
source
reason
evidence
```

This keeps future LLM-based repair possible without allowing the model to invent
new user intent.

## 7. Knowledge Index and RAG

RAG can help, but it should not become an unbounded prompt dump.

Recommended indexed material:

- POI facts
- canonical category labels
- alias/lexicon entries
- route policy notes
- UGC aspect signals
- map/provider capability notes

Do not retrieve:

- full noisy review text for every request
- large docs that do not affect the current route decision
- stale examples that conflict with current policy
- internal implementation notes for user-facing generation

Retrieval should return compact, typed evidence:

```json
{
  "source": "ugc_signal",
  "poi_id": "gz-food-001",
  "aspect": "queue_risk",
  "score": 0.72,
  "confidence": 0.63,
  "evidence": ["周末排队久", "饭点等位"]
}
```

Noise control rules:

- prefer structured signals over raw text
- cap retrieved evidence per POI and per aspect
- downweight low-confidence evidence
- keep unrelated knowledge out of the intent prompt
- log retrieved evidence IDs in trace

## 8. UGC as Weak Signals

Common UGC rarely contains full route-planning information. Treat it as an
experience signal layer, not a route feasibility layer.

Initial aspects:

```text
queue_risk
photo
quiet
food_quality
date
family
local_feature
price_value
```

Low-confidence UGC should only slightly affect ranking. It should not become a
hard constraint.

## 9. Memory and Multi-Turn State

Memory has three levels:

| Level | Use | Constraint |
| --- | --- | --- |
| Current route | Modify and compare current result | Strong context for modification |
| Session profile | Repeated short-term preferences | Soft bias only |
| Long-term profile | Stable user preferences | Must be user-visible and resettable |

Memory must not silently override the current query. The current query wins over
session memory, and hard constraints win over soft profile bias.

## 10. Tool Contracts

A capability becomes a tool only when its input/output contract is stable.

Current logical tools:

```text
intent.parse
poi.retrieve
poi.rank
route.plan
route.verify
route.repair
poi.recall
constraint.filter
memory.context
ugc.signal
map.distance_matrix
map.preview
route.explain
eval.run
```

Each tool should expose:

- input schema
- output schema
- failure mode
- fallback behavior
- trace fields

Implemented tool result shape:

```json
{
  "tool": "map_distance_matrix",
  "status": "ok | fallback | skipped | failed",
  "confidence": 0.72,
  "payload": {},
  "evidence": [],
  "noise_risk": "low",
  "used_by": ["planning", "validation", "explanation"],
  "latency_ms": 0,
  "fallback_used": false
}
```

Tools should never pass raw noisy text into route planning. They should return
typed observations that can be inspected and tested.

## 11. ExecutionPlan

The coordinator now creates a bounded `ExecutionPlan` before route generation.
The plan is not a free-form agent plan; it is an auditable control object.

```text
required_steps
optional_tools
skipped_tools
tool_budget
max_repair_rounds
quality_gates
fallback_policy
decision_basis
```

Rules:

- required steps keep the main pipeline deterministic
- optional tools must have a registered implementation before execution
- skipped tools must include a reason
- map distance can use external providers only when the plan allows it
- every tool observation is stored in `RouteState.tool_results`

Current implemented route observations include:

- `poi_recall`: records recall lanes, raw/selected counts, and fallback state.
- `constraint_filter`: records filtering pressure and selected candidate count.
- `memory_context`: summarizes session/profile signals when a session exists and the user has not opted out.
- `planning_distance_matrix`: records the local top-K candidate travel matrix used by beam search, route scoring, and scheduling.
- `map_distance_matrix`: calibrates consecutive route segments and falls back to local haversine estimates when external maps are not enabled.
- `heat_signal`: checks selected route POIs for queue and crowd pressure when waiting/crowding matters.
- `ugc_signal`: analyzes selected route POIs for compact review-derived fit/risk signals.

`memory_context`, `heat_signal`, and `ugc_signal` are weak-signal tools. They must remain
traceable and bounded; neither should silently override hard user constraints.

## 12. Workflow Visibility

The user-facing UI should stay concise. The debug/diagnostic trace can be rich.

User-facing explanation:

- why this route matches the request
- major warnings
- what changed after modification

Debug trace:

- parsed intent
- recall counts and sources
- ranking top-k
- route variants
- verifier result
- coordinator decisions
- execution plan
- tool results
- map data source
- latency by stage

## 13. Evaluation Requirements

Coordinator changes must be covered by workflow evals:

- should clarify when the request is too broad
- should continue when intent has enough signals
- should expand retrieval when candidates are empty or too thin
- should repair/replan when quality is low
- should explain only after route quality is attached
- should expose execution plan stages
- should expose tool result observations
- should record skipped optional tools and their reasons
- should keep intent repair patch-based and avoid hard-constraint mutation

This keeps the agent from becoming a hidden source of arbitrary behavior.

## 14. Current Implementation Step

The implementation is intentionally conservative:

- add `backend/agent/state.py`
- add `backend/agent/coordinator.py`
- add `backend/agent/planning.py`
- add `backend/agent/tool_layer.py`
- add `backend/agent/intent_repair.py`
- add `backend/services/route_tools.py`
- attach coordinator decisions to `planned_route["coordinator"]`
- attach `execution_plan` and `tool_results` to route trace
- run `map_distance_matrix`, `memory_context`, `heat_signal`, and `ugc_signal` as bounded optional tools
- expose POI recall and constraint filtering as tool observations
- wrap initial and repair planning in `RouteAttempt`, so both paths share retrieval, tool execution, validation, and guardrail handling
- expose compact `route_attempts` summaries for adoption/rejection decisions
- expose coordinator in `workflow_trace`
- keep core route candidate generation deterministic

This creates observability before adding more autonomy.
