# Policy

This directory holds tunable policy files that should be changed without touching
the ranking code.

## `poi_ranker_weights.json`

Controls the POI ranking baseline:

- final score weights
- score normalization thresholds
- risk penalty multipliers

Recommended tuning order:

1. Adjust the final score weights first.
2. Only then adjust the internal score thresholds if the route feels too loose or too strict.
3. Use `backend/eval/check_quality.py` after every change.

## Rule of thumb

- Raise `preference_match_score` and `semantic_score` if routes are technically valid
  but do not feel like the user asked.
- Raise `rating_score`, `budget_score`, or `time_suitability_score` if routes feel
  too noisy or too risky.
- Increase penalty multipliers only when queue/crowd issues are consistently ignored.

