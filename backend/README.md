# Backend Overview

`backend/` is the main implementation area for the route-planning engine.
Keep the structure small and explicit. Do not add a new layer unless it has a
clear contract and will stay useful.

## Directory map

- `core/` - request/response contracts, intent parsing, lexicon, capability
  routing, context models, display labels, and shared schemas.
- `services/` - POI retrieval, ranking, route planning, map integration,
  response generation, context persistence, and orchestration.
- `policy/` - tunable weights and other strategy config.
- `lexicon/` - structured semantic vocabulary and aliases.
- `eval/` - offline regression and quality checks.
- `tools/` - sync, validation, and maintenance scripts.

## Current execution path

1. LLM-first intent extraction.
2. Capability routing and clarification if needed.
3. Intent biasing with lightweight profile/context.
4. POI retrieval and filtering.
5. Ranking and route planning.
6. Map alignment and preview.
7. Response generation and context logging.

## If you are coding now

Start with:

- `core/README.md`
- `services/README.md`
- `docs/specs/CONTEXT_SPEC.md`
- `docs/specs/MEMORY_SPEC.md`

## Common debug entry points

- `intent_parser.py` - intent extraction is wrong.
- `llm_intent_client.py` - LLM JSON is invalid or missing.
- `capability_registry.py` - capability routing is off.
- `context_service.py` - session/profile state is stale.
- `route_planner.py` - route shape is bad.
- `map_service.py` - map data or preview is wrong.
- `response_generator.py` - output payload is incomplete.

