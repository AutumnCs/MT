# Backend Overview

`backend/` is the FastAPI route-planning backend for MeituanAgent. Its job is to
turn natural-language travel intent into executable, explainable, and editable
city routes.

## Current Shape

The backend is not a free-form travel agent. It is a controlled route-planning
pipeline with explicit orchestration and a bounded execution DAG:

```text
Intent parsing
  -> RouteCoordinator
  -> ExecutionPlan / DAG
  -> memory/context tool when available
  -> POI retrieval / ranking
  -> route planning
  -> optional route tools through Tool Layer
  -> validation and workflow guard
  -> patch-based repair if useful
  -> explanation and response trace
```

LLM parsing is used for language understanding when available. Route decisions,
constraints, repair, and final response structure stay in deterministic backend
services.

## Intent Recognition

The current intent layer is not a retrieval-style RAG module. It is a bounded
parse cascade:

```text
user query
  -> local rule/semantic parse
  -> fast-gate confidence check
  -> LLM parse when needed
  -> local normalization + semantic score merge
  -> clarification / guard checks
```

In practice:

- local parsing handles lexicon matches, time/budget extraction, and lightweight semantic hints
- simple high-confidence requests can stop at `local_fast_gate`
- ambiguous or compositional requests go through `llm+local`
- if LLM parsing fails, the backend falls back to `local_fallback`
- semantic understanding now reads a unified ontology layer so prompts, hint inference, and recall expansion share the same canonical tags
- route modification now inherits the original intent goal before inheriting route coverage, which keeps additive requests like breakfast/coffee from bloating the route

The output is always normalized into the same `ParsedIntent` schema, including
categories, preferences, avoid flags, uncertainty fields, semantic scores, hard
constraints, and confidence.

For the fuller design note, see `docs/specs/INTENT_UNDERSTANDING_SPEC.md`.
The runtime trace now also includes an execution-oriented `IntentIR` view so
language understanding and downstream execution do not have to share one flat
schema.

## Key Modules

- `agent/`: coordinator state, execution plan, tool result contracts, and patch-based intent repair.
- `core/`: shared schemas, intent parser, prompt templates, capability registry, and diagnostics contracts.
- `services/`: POI retrieval, ranking, route planning, validation, response generation, context, maps, and route tools.
- `eval/`: offline regression runner and evaluation cases.
- `policy/`: configurable route and ranking policy. See `ROUTE_POLICY_GUIDE.md` for tuning notes.
- `tools/`: data maintenance scripts.

## Workflow Trace

Every route response can include `workflow_trace` and `trace` data. The current
trace records:

- input and intent understanding
- intent trace with parse path, confidence, uncertainty, semantic top scores, and memory/profile bias usage
- `execution_plan`
- memory projection summary such as stable/recent signal counts, decay, route-memory strength, and pending conflicts
- retrieval counts and selected POIs
- planning-time local distance matrix summary
- route attempt summaries for initial/repair runs and adoption decisions
- tool observations such as `poi_recall`, `constraint_filter`, `poi_rerank`, `map_distance_matrix`, `memory_context`, `heat_signal`, and `ugc_signal`
- planning result and route stats
- route critique and guardrail checks
- coordinator decisions
- explanation summary

This trace is meant for debugging, evals, and future workflow UI. User-facing
copy should stay concise.

## Tool Layer

Tools are bounded and auditable. A tool returns a normalized `ToolResult` with
status, confidence, payload, evidence, noise risk, latency, and fallback state.

The coordinator now emits a lightweight execution DAG inside `execution_plan`:

- deterministic steps such as `intent`, `poi_retrieval`, `ranking`, `planning`, `validation`, `explanation`
- tool nodes such as `tool:memory_context`, `tool:map_distance_matrix`, `tool:ugc_signal`, `tool:heat_signal`
- explicit dependencies and per-node runtime status for trace/debug use

This is intentionally not a free-form agent loop. Replanning still happens only
at bounded coordinator checkpoints.

Current implemented route/tool observations:

- `poi_recall`: reports recall lanes, raw/selected candidate counts, retrieval backend metadata, and fallback state.
- `poi_rerank`: reports rerank input/output counts, top-score span, average score breakdown, and top recommendation reasons.
  The breakdown now includes query-alignment so ranking can better reflect the
  original user request without relying on a heavyweight external reranker.
- `constraint_filter`: reports constraint filtering pressure before ranking.
- `memory_context`: summarizes usable session/profile signals when a session exists and the user has not opted out.
  It now exposes a compact raw/structured/semantic projection, conflict count,
  freshness metadata, and a bounded prompt block for LLM-side understanding.
- `planning_distance_matrix`: summarizes the bounded top-K local matrix used by route scoring and scheduling.
- `map_distance_matrix`: calibrates consecutive route segment travel time and distance; falls back to local haversine estimates when external maps are not enabled.
- `heat_signal`: checks selected route POIs for queue and crowd pressure when the request is sensitive to waiting or congestion.
- `ugc_signal`: extracts compact selected-route review signals such as queue/crowd/quiet/photo/food fit without passing raw reviews through planning. The route layer now keeps structured summaries and short explanation hints separate from raw per-stop debug payloads.

Future data tools should follow the same contract:

- `PoiRecallTool`
- `WeatherTool`

## Repair

Intent repair is patch-based through `IntentRepairAgent`. It can only adjust
allowed soft planning fields such as categories, preferences, avoid flags, and
route strategy. It must not rewrite city, budget, time windows, or hard
constraints that were not in the user request.

## Evaluation

Run the offline regression suite after backend changes:

```powershell
cd G:\MeituanAgent\backend
python -m eval.eval_runner
```

Current suite: 49 cases, covering intent parsing, route modification, workflow
trace, memory opt-out/session behavior, route version persistence, route
delta summaries, session route autofill, route quality, heat/queue tooling,
failure boundaries, intent repair, and acceptance checks for sub-10-second
planning, at least three POIs, dining plus culture/entertainment coverage, and
complete stop timing.

## Retrieval Architecture

POI retrieval now uses a lightweight hybrid stack:

- rule/category lanes
- direct text-signal lane
- BM25 lexical lane
- dense hash-vector lane
- optional FAISS acceleration when installed

This keeps the default project dependency-light while making the retrieval
boundary ready for stronger dense models later. If we adopt `bge-m3`,
`bge-reranker-v2-m3`, or Milvus/Faiss in a larger deployment, the main route
workflow does not need to be rewritten.
