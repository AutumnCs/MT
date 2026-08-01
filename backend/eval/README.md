# backend/eval

`eval/` holds the offline regression and quality gate tools.

## Files

| File | Purpose |
|---|---|
| `eval_runner.py` | run the evaluation cases |
| `check_quality.py` | one-shot quality check |
| `watch_quality.py` | watch files and rerun checks |

## What this layer should do

- Protect the project from accidental regressions.
- Keep new lexicon, prompt, or policy changes measurable.
- Make the output of routing and profile changes observable.

## Current report shape

`eval_runner.py` now returns a richer report instead of a simple pass/fail result.

Top-level fields:

- `dataset`
- `total_cases`
- `passed_cases`
- `pass_rate`
- `results`
- `summary`

`summary` is used as a compact dashboard for engineering review:

- `intent_cases`
- `modify_cases`
- `passed_intent_cases`
- `passed_modify_cases`
- `pass_rate_by_type`
- `avg_checks_per_case`
- `avg_latency_ms`
- `avg_recall_lane_count`
- `avg_rerank_output_count`
- `avg_query_alignment_score`
- `retrieval_backend_counts`
- `dense_backend_counts`
- `failed_case_ids`

This makes the offline evaluation layer useful for:

- comparing intent parsing and modification quality separately
- spotting regressions by case id
- checking whether retrieval and rerank upgrades are actually active
- tracking whether a change improves quality or only shifts it around

## Where the report goes

When you run `python backend/eval/eval_runner.py`, the report is also written to:

- `.tmp/eval_report.json`

That file is meant for local inspection and diffing between runs, not for manual editing.

