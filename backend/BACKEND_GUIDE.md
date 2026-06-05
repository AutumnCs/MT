# Backend Guide

This guide answers one question: when something breaks, where should you look
first?

## File groups

| Area | What it owns |
|---|---|
| `backend/core/` | contracts, intent parsing, context models, lexicon, capability routing |
| `backend/services/` | POI retrieval, ranking, route planning, context storage, response generation, map integration |
| `backend/policy/` | adjustable strategy weights |
| `backend/lexicon/` | structured vocabulary and aliases |
| `backend/eval/` | offline checks and regression reports |
| `backend/tools/` | maintenance scripts |

## Most common problems

| Problem | First file to check |
|---|---|
| Intent parsing is wrong | `backend/core/intent_parser.py` |
| LLM JSON is bad or missing | `backend/core/llm_intent_client.py` |
| Capability routing is off | `backend/core/capability_registry.py` |
| Session/profile state is stale | `backend/services/context_service.py` |
| Route shape is unreasonable | `backend/services/route_planner.py` |
| POI retrieval is weak | `backend/services/poi_retriever.py` |
| Ranking looks off | `backend/services/poi_ranker.py` |
| Map preview is wrong | `backend/services/map_service.py` |
| Response payload is incomplete | `backend/services/response_generator.py` |

## Current design rules

- Production path is LLM-first.
- Local rules are mainly for fallback, regression, and validation.
- Multi-turn edits use state + patch, not a heavy agent loop.
- Context and profile should be structured, replayable, and decaying.
- `context_service.py` should never block route generation.

