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

