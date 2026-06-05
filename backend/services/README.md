# backend/services

`services/` owns the real route-planning work.

## Files

| File | Purpose |
|---|---|
| `route_service.py` | top-level orchestration for parse, route, modify, clarify |
| `context_service.py` | lightweight session store, profile projection, route version logging |
| `constraint_checker.py` | intent and POI constraint validation |
| `poi_retriever.py` | candidate retrieval from the POI dataset |
| `poi_ranker.py` | ranking entrypoint |
| `poi_ranker_policy.py` | ranking weight loading |
| `ranker_engine.py` | scoring implementation |
| `review_analyzer.py` | review/description signal analysis |
| `route_planner.py` | assemble candidate POIs into routes |
| `response_generator.py` | final route/clarification payload generation |
| `map_service.py` | map provider wrapper and local fallback |
| `amap_client.py` | Amap HTTP client |

## What this layer should do

- Filter and rank POIs.
- Build executable route plans.
- Align route plans with map facts.
- Produce UI-ready, editable, explainable results.
- Persist only lightweight context signals, never raw noise.

## When to look here first

- The route is too long or too short.
- Ranking feels off.
- POI filtering is too strict.
- Map preview or route alignment looks wrong.
- Multi-turn modification does not carry context correctly.

