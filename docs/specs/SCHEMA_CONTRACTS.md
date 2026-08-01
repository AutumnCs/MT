# Schema Contracts

This file defines the current JSON contract map for Muse.

The goal is not to make every field globally frozen forever. The goal is to
make module boundaries explicit enough that:

- intent understanding
- retrieval and ranking
- route planning
- tool enrichment
- workflow coordination
- response generation

can evolve without drifting into undocumented `dict[str, Any]` handoffs.

## System Position

Muse is not a pure LLM chain.

It is also not a free autonomous multi-agent system.

The current system is best described as:

```text
workflow-constrained agent system
with structured schemas, bounded tools,
deterministic planning, and selective LLM use
```

That means schemas are first-class runtime contracts, not just type hints.

## Contract Layers

### 1. API Request Layer

Used by FastAPI request handlers.

Primary files:

- `backend/core/api_contracts.py`
- `backend/main.py`

Current rule:

- API request models now use `extra="forbid"` so unknown top-level request
  fields fail fast instead of being silently ignored.

Representative contracts:

- `RouteRequest`
- `ModifyRequest`
- `IntentParseRequest`
- `PromptRequest`
- `ContextEventRequest`
- `ContextRouteVersionRequest`

## 2. Intent Layer

### 2.1 LLM Draft

File:

- `backend/core/schemas.py` -> `IntentDraft`

Purpose:

- tolerant intermediate object for LLM extraction output
- may include provider quirks or partially filled fields

Key fields:

- `city`
- `start_location`
- `start_time`
- `end_time`
- `budget`
- `required_categories`
- `preferences`
- `party_types`
- `primary_party_type`
- `avoid`
- `primary_categories`
- `secondary_categories`
- `must_include`
- `semantic_scores`
- `semantic_evidence`
- `intent_confidence`

Notes:

- This layer is intentionally more tolerant than the final parsed intent.
- It should move gradually toward provider-level structured output.

### 2.2 Parsed Intent

File:

- `backend/core/schemas.py` -> `ParsedIntent`

Purpose:

- canonical runtime intent object shared by the rest of the backend

Key fields:

- hard route inputs:
  - `city`
  - `start_location`
  - `start_time`
  - `end_time`
  - `budget`
  - `transport_mode`
  - `must_include`
- semantic route targets:
  - `required_categories`
  - `preferred_categories`
  - `primary_categories`
  - `secondary_categories`
  - `side_categories`
- user style / route style:
  - `preferences`
  - `soft_preferences`
  - `party_types`
  - `primary_party_type`
  - `pace`
  - `route_strategy`
- constraints / governance:
  - `avoid`
  - `category_caps`
  - `category_min_counts`
  - `hard_constraints`
  - `uncertain_fields`
  - `needs_clarification`
- semantic trace:
  - `semantic_hints`
  - `semantic_scores`
  - `semantic_evidence`
  - `recognized_signals`
  - `intent_tags`
  - `unclassified_clues`
- workflow linkage:
  - `parse_source`
  - `intent_confidence`
  - `current_route`
  - `session_id`
  - `llm_payload`

Rule:

- all downstream modules should prefer `ParsedIntent` over raw LLM output

### 2.3 Intent IR

File:

- `backend/core/intent_ir.py`

Purpose:

- bridge between language understanding and execution control
- keep execution semantics stable even when parsing fields evolve

Main fields:

- `task_type`
- `goal_slots`
- `support_slots`
- `atmosphere_slots`
- `mobility_slots`
- `constraint_slots`
- `party_types`
- `primary_party_type`
- `must_include`
- `route_strategy`
- `confidence`
- `uncertainty`

Rule:

- `ParsedIntent` is the canonical parsed object
- `IntentIR` is the canonical execution-facing abstraction
- retrieval / ranking / planning diagnostics should increasingly read from
  `IntentIR` rather than re-deriving semantics ad hoc

## 3. Planning / Coordination Layer

Files:

- `backend/agent/planning.py`
- `backend/agent/state.py`
- `backend/agent/coordinator.py`

### 3.1 ExecutionPlan

Purpose:

- bounded execution contract for one request

Main fields:

- `required_steps`
- `required_data`
- `optional_data`
- `skipped_data`
- `optional_tools`
- `skipped_tools`
- `dag_mode`
- `dag_nodes`
- `quality_gates`
- `fallback_policy`
- `decision_basis`

### 3.2 PlanNode

Purpose:

- lightweight execution DAG node

Main fields:

- `node_id`
- `kind`
- `label`
- `depends_on`
- `status`
- `metadata`

Rule:

- the DAG is for controlled execution tracking and dependency visibility
- it is not a license to create an unbounded agent loop

### 3.3 RouteState

Purpose:

- full workflow snapshot for one request

Main fields:

- `intent`
- `retrieval`
- `ranking`
- `planning`
- `execution_plan`
- `tool_results`
- `quality_report`
- `explanation`
- `decision_log`

## 4. Tool Layer

File:

- `backend/agent/tool_layer.py`

### ToolResult

Purpose:

- normalized output contract for bounded tools

Main fields:

- `tool`
- `status`
- `confidence`
- `payload`
- `evidence`
- `noise_risk`
- `used_by`
- `latency_ms`
- `fallback_used`
- `error`
- `metadata`

Rule:

- route tools should communicate via `ToolResult`, not raw external payloads

## 5. Route Response Layer

File:

- `backend/core/schemas.py` -> `RouteResponse`

Purpose:

- stable product/API output

Main fields:

- user-facing:
  - `title`
  - `summary`
  - `main_stops`
  - `stops`
  - `variants`
  - `route_explanation`
  - `warnings`
- product/runtime:
  - `intent`
  - `intent_summary`
  - `parse_source`
  - `stats`
  - `total_cost`
  - `total_duration`
  - `total_distance`
  - `poi_count`
- debug / observability:
  - `workflow_trace`
  - `trace`
  - `diagnostics`

Rule:

- `RouteResponse` should remain readable for product use while exposing enough
  structured trace for eval and debugging

## 6. Where Contracts Are Still Soft

These boundaries still need tightening:

- `current_route`
- `route_version`
- some `diagnostics` payloads
- some context event payloads
- some `dict[str, Any]` trace blocks

Those are the right next targets for contract hardening.

## 7. LLM JSON Status

Current state:

- prompt-level JSON instruction
- provider request now prefers `response_format={"type":"json_object"}`
- local JSON extraction fallback still exists
- normalized output still flows through `normalize_llm_intent()`

This is good enough for development, but the target state should be:

```text
provider structured output
-> validated IntentDraft
-> normalized ParsedIntent
```

instead of:

```text
text response
-> extract JSON
-> normalize
```

## 8. MCP Status

The current project does not use MCP in its runtime workflow.

Instead it uses:

- local `ToolRegistry`
- local `ToolResult`
- local `ExecutionPlan`
- local execution DAG

This is acceptable for the current phase because it keeps the system:

- simpler
- easier to debug
- easier to replay

If the project later needs ecosystem interoperability, the migration path should
be:

1. make all tools fully schema-explicit
2. standardize tool input/output/error contracts
3. only then consider MCP transport and server boundaries

## 9. Near-Term Contract Priorities

1. introduce an explicit `IntentIR` contract between parsing and execution
2. tighten `current_route` / `route_version` typing
3. convert major trace blocks from ad hoc dicts into typed models
4. upgrade LLM extraction to schema-constrained structured output
5. define a stable tool input schema for each route tool
