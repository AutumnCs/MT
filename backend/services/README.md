# backend/services

`services/` turns a structured route intent into route candidates, selected
plans, validation results, explanations, and traceable responses.

## Files

| File | Purpose |
|---|---|
| `route_service.py` | Main route workflow orchestration and `RouteAttempt` execution wrapper. |
| `poi_retriever.py` | Local POI candidate recall. |
| `semantic_retriever.py` | Hybrid semantic retrieval: BM25 lexical recall, dense hash-vector recall, optional FAISS acceleration, and future external model hook. |
| `ranker_engine.py` | Multi-factor POI ranking engine with query-aware semantic alignment. |
| `poi_ranker.py` | Ranking compatibility entrypoint. |
| `poi_ranker_policy.py` | Ranking weights and policy helpers. |
| `route_planner.py` | Beam search route composition, ordering, variants, and planning-time local distance matrix. |
| `route_verifier.py` | Route-quality verifier and output-side critic. |
| `workflow_guard.py` | Handoff guard between understanding, planning, critique, and explanation. |
| `route_tools.py` | Deterministic tool implementations such as `memory_context`, `map_distance_matrix`, `heat_signal`, and `ugc_signal`. |
| `response_generator.py` | Route response, explanation, and workflow trace generation. |
| `context_service.py` | Session context, profile, and route-version memory. |
| `map_service.py` | Map capability wrapper and local fallback. |
| `tianditu_client.py` | Tianditu HTTP client. |
| `amap_client.py` | AMap data maintenance helper client. |
| `constraint_checker.py` | Basic intent and POI constraint checks. |
| `review_analyzer.py` | Review/description signal analysis. |

## Design Goals

- Do not jump from LLM output directly to final routes.
- Retrieve, rank, plan, validate, and explain in separate stages.
- Keep initial planning and repair planning on the same `RouteAttempt` path.
- Keep route tools bounded and observable through `ToolResult`.
- Keep memory as a compact projection of session, route history, and durable preferences rather than a raw chat dump.
- Expose `workflow_trace` with `execution_plan`, explicit memory summary, recall/rerank observations, planning distance matrix, memory/UGC/heat/map tool observations, planning, critique, guard, and coordinator stages.
- Keep enrichment signals compact at the route layer: UGC and heat should enter planning/verification as structured summaries, while detailed per-stop debug payloads remain in tool results.
- Keep route modification incremental and tied to the current route.
- Keep repair patch-based instead of silently rewriting intent.

## Why `services/` Looks Heavy

This folder is heavier than some agent demos because Muse keeps more logic on
the deterministic side:

- recall and rerank are explicit
- route planning is explicit
- verification and critique are explicit
- response trace is explicit
- memory and tool enrichment are explicit

That makes the system more controllable, but it also means the orchestration and
domain logic are less hidden inside prompts.

The current file weight is partly a growth artifact, not a desired endpoint.
The main targets for future slimming are:

- `route_service.py`
- `response_generator.py`
- `intent_parser.py`

The rule is to split by ownership boundary, not just by line count.

## Debugging Guide

| Problem | Start With |
|---|---|
| Too few POIs recalled | `poi_retriever.py`, `semantic_retriever.py` |
| Recall feels noisy or rerank looks unstable | `poi_retriever.py`, `candidate_builder.py`, `ranker_engine.py` |
| Ranking feels wrong | `ranker_engine.py`, `poi_ranker_policy.py` |
| Route order feels wrong | `route_planner.py`, `route_tools.py` |
| Modification loses constraints | `route_service.py`, `agent/intent_repair.py` |
| Explanation mismatches result | `response_generator.py`, `route_verifier.py` |
| Map preview or travel time looks wrong | `map_service.py`, `route_tools.py` |
| Memory or profile seems over-applied | `context_service.py`, `route_tools.py`, `agent/coordinator.py` |
| Memory conflicts or stale profile signals look suspicious | `context_service.py`, `route_tools.py`, `response_generator.py` |
| Queue or crowd constraints are unclear | `route_tools.py`, `agent/coordinator.py`, `route_verifier.py` |
| UGC signals look noisy | `review_analyzer.py`, `route_tools.py`, `pois.json` |

Run `python -m eval.eval_runner` before and after meaningful service changes.

## Retrieval Upgrade Notes

The current retrieval stack is intentionally two-speed:

- default mode: pure-Python hybrid retrieval with BM25 + dense hash vectors
- stronger mode: same interface, but can use optional FAISS acceleration and
  later external embedding/rerank backends

This keeps local development simple while preserving a clean path toward
`bge-m3`, `bge-reranker-v2-m3`, Faiss, or Milvus-style production upgrades.

The ranking layer is also query-aware: it fuses intent features, queue/crowd
penalties, and retrieval-side alignment so long-tail requests can be handled
without pushing the whole system into a heavyweight neural reranker path.
