# Route Policy Guide

This guide explains the tunable knobs in `backend/route_policy.json`.

The goal is to keep route behavior configurable without scattering magic numbers
through the codebase. Most changes should start here, then be validated through
offline eval cases.

## 1. What This Policy Controls

`route_policy.json` is not a vocabulary list and not a replacement for code.
It is a small set of behavior knobs for:

- intent confidence thresholds
- primary vs supporting category balance
- route planning weights and quotas
- route verification penalties
- explanation length defaults

The code reads these values from `backend/core/route_policy.py`.

## 2. Main Sections

### `intent_confidence`

Controls when the parser can move from understanding into the normal route flow.

Important keys:

- `city_bonus`: confidence boost when a city is recognized
- `required_category_bonus`: confidence boost per explicit required category
- `preference_bonus`: confidence boost per preference
- `avoid_bonus`: confidence boost per avoid signal
- `budget_bonus`: confidence boost when budget is present
- `time_bonus`: confidence boost when time windows are present
- `start_location_bonus`: confidence boost when a start point is present
- `pace_bonus`: confidence boost when pace is explicit
- `must_include_bonus`: confidence boost when must-include items are present
- `current_route_bonus`: additional boost for modification requests
- `mixed_signal_bonus`: bonus when multiple signal types agree
- `multi_category_bonus`: bonus when the query touches multiple categories
- `unclassified_penalty`: penalty for too many ambiguous clues
- `long_query_penalty`: penalty for long but weak queries

### `fast_gate_threshold`

Controls the fast-path cutoff.

- `default`: threshold for normal first-turn parsing
- `modify`: threshold for route modification requests

### `role`

Controls primary vs supporting category balance.

- `primary_min_strength`: minimum semantic strength for a category to become a primary goal
- `primary_min_count_with_support`: minimum count to keep a primary goal when support items exist
- `support_cap`: maximum supporting category count
- `secondary_support_cap`: maximum secondary-support count
- `primary_priority`: preferred ordering of primary categories

### `planner`

Controls route candidate generation and beam search.

- `beam_size`: beam width for planning
- `beam_candidate_limit`: candidate limit per beam round
- `distance_matrix_top_k`: top-K pool for planning-time travel awareness
- `cluster_bonus`: reward for staying within the same area cluster
- `cluster_match`: multiplier when a cluster matches the intent
- `cluster_mismatch`: multiplier when a cluster mismatches the intent
- `quota_bonus`: reward for preserving under-covered categories
- `quota_penalty`: penalty for overusing a category
- `support_decay`: decay applied to supporting categories after the primary route is formed
- `quota_miss_penalty`: penalty for missing required category quotas

### `verification`

Controls route-quality penalties during verification and critique.

- `min_gap_penalty`: penalty for missing required categories
- `cap_gap_penalty`: penalty for exceeding a category cap

### `explanation`

Controls the default length of concise route explanations.

- `max_length`: default explanation length cap

## 3. Recommended Tuning Order

Adjust a small number of knobs at a time:

1. `role.primary_min_strength`
2. `role.primary_min_count_with_support`
3. `planner.quota_bonus`
4. `planner.quota_penalty`
5. `fast_gate_threshold.default`
6. `explanation.max_length`

Use the offline eval suite after each change:

```powershell
cd G:\MeituanAgent\backend
python .\eval\eval_runner.py
```

If you want to sweep policy values more systematically:

```powershell
cd G:\MeituanAgent\backend
python .\eval\tune_route_policy.py
```

## 4. What To Watch

After tuning, check whether these behaviors got better:

- the route keeps the main user goal instead of drifting into support categories
- the route still covers at least the intended dining and culture/entertainment mix
- route modifications preserve the original request intent
- UGC and heat warnings stay soft and explainable
- route explanations stay concise unless the user asks for more detail

## 5. Code vs Policy

Do not add new hardcoded thresholds in the middle of the route pipeline if the
value is actually a tuning knob.

Prefer this order:

1. add the parameter to `route_policy.json`
2. read it through `backend/core/route_policy.py`
3. expose it in eval coverage
4. only change core logic when the algorithm itself needs to change

