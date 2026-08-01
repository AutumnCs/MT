# Current System

This file describes the system as it exists now, not an aspirational multi-agent
 design.

## Positioning

Muse is a controlled route-planning system for local-life and short-trip
planning. The product input is natural language, but the execution path stays
structured and observable.

## End-To-End Flow

```text
user query
  -> intent parsing
  -> RouteCoordinator
  -> ExecutionPlan
  -> memory_context when session signals are usable
  -> POI recall
  -> constraint filter
  -> POI rerank
  -> route planning
  -> optional map / heat / UGC tools
  -> route verification + workflow guard
  -> patch-based repair when quality gaps are repairable
  -> explanation + workflow_trace
```

## Intent Layer

Intent recognition is currently a controlled parse cascade, not a retrieval-led
RAG flow:

- local parser for category, preference, time, budget, and avoid extraction
- unified semantic ontology plus lightweight semantic bridge for hint completion, score merging, and recall-query expansion
- optional LLM parse for ambiguous or compositional requests
- normalized `ParsedIntent` output with uncertainty and confidence fields
- clarification and workflow guard before expensive planning starts

The runtime parse path is visible through `parse_source` values such as
`local`, `local_fast_gate`, `llm+local`, and `local_fallback`.

See also `INTENT_UNDERSTANDING_SPEC.md` for the current target shape of the
semantic ontology, slot extraction, and hybrid retrieval-query layer.

The runtime trace now also carries an `IntentIR` view: a compact execution-side
projection of user goals, support needs, atmosphere, mobility, constraints, and
party composition.

## Core Boundaries

- `core/`: schemas, parsing, prompt contracts, policy.
- `agent/`: coordinator state, execution plan, tool/result contracts, repair agent.
- `services/`: recall, ranking, planning, tools, verification, context, explanation.
- `eval/`: offline regression and policy-tuning helpers.

## Retrieval Shape

The backend uses hybrid recall, but keeps it lightweight:

- lexical/category recall
- direct text-signal recall
- BM25 lexical recall
- semantic similarity recall
- dense hash-vector recall through `semantic_retriever`
- must-include and start-location lanes
- bounded fallback expansion

When FAISS is available, the dense lane can be accelerated without changing the
rest of the planning workflow. The current interface is also structured so a
future BGE/Faiss or Milvus-backed deployment can replace the local dense layer
without rewriting `poi_retriever.py` or the coordinator.

Recall is now governed by lane caps, thresholds, overlap diagnostics, and
noise-risk fields instead of one opaque candidate list.

## Ranking Shape

Ranking is deterministic and policy-driven. The current factors include:

- preference match
- semantic fit
- category match
- rating
- budget fit
- time suitability
- queue / crowd / price penalties
- modification penalty for incremental edits

`poi_rerank` now exposes structured trace information so we can inspect why the
top items won.

## Memory Shape

Memory is layered and bounded:

- raw layer: recent events, queries, route versions
- structured layer: stable city/category/preference/profile fields
- semantic layer: atomic facts, scene tags, narrative summary

Memory remains a soft bias. Current-turn constraints always win.

## UGC And Tool Signals

UGC, heat, map, and memory all enter the runtime as bounded tool observations.

- route planning and verification read compact structured summaries
- short explanation hints may be exposed for response generation
- full per-stop debug payloads stay inside tool results and workflow trace

This keeps noisy text-like evidence away from the main planning path.

## What This System Is Not

- not a free-form ReAct agent
- not a heavy multi-agent graph for every request
- not a raw-chat-memory dump
- not an unbounded RAG pipeline

The design goal is reliability, explainability, and maintainable evolution.
