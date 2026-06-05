# backend/core

`core/` holds the smallest stable contracts and shared logic.

## Files

| File | Purpose |
|---|---|
| `api_contracts.py` | FastAPI request contracts |
| `contracts.py` | shared orchestration contracts and diagnostics |
| `context_models.py` | session state, behavior events, profile, route versions |
| `schemas.py` | POI, route, intent, and response schemas |
| `intent_parser.py` | structured intent extraction and normalization |
| `llm_intent_client.py` | LLM JSON extraction |
| `prompt_templates.py` | prompts for extraction, routing, modification, explanation |
| `intent_lexicon.py` | semantic vocabulary and aliases |
| `capability_registry.py` | capability registry and routing scores |
| `display_labels.py` | labels shown to users |
| `route_context.py` | route-level context inference |
| `map_schemas.py` | map API request/response models |

## What this layer should do

- Turn user language into structured intent.
- Keep capability boundaries explicit.
- Keep shared contracts small and reusable.
- Keep context data structured enough for profile projection.

## When to look here first

- Intent classification is wrong.
- A shared contract changed and broke downstream modules.
- Capability routing or diagnostics look inconsistent.
- Context/session models need a new field.

