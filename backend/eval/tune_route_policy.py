"""Offline tuner for the route policy.

Usage:
    python eval/tune_route_policy.py

The script tries a small grid of policy values against the offline eval set and
prints the best-scoring policy. It does not modify your working policy unless
you explicitly save the emitted JSON.
"""

from __future__ import annotations

import copy
import itertools
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "route_policy.json"
EVAL_RUNNER = ROOT / "eval" / "eval_runner.py"


def _load_policy() -> dict[str, Any]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _run_eval(policy: dict[str, Any]) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(policy, handle, ensure_ascii=False, indent=2)
        temp_path = handle.name

    env = os.environ.copy()
    env["ROUTE_POLICY_PATH"] = temp_path
    result = subprocess.run(
        [sys.executable, str(EVAL_RUNNER)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        Path(temp_path).unlink(missing_ok=True)
    except Exception:
        pass

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "eval failed")
    return json.loads(result.stdout)


def main() -> int:
    base_policy = _load_policy()
    candidates = {
        "role.primary_min_strength": [0.40, 0.45, 0.50],
        "role.primary_min_count_with_support": [2],
        "planner.quota_bonus": [0.14, 0.18, 0.22],
        "planner.quota_penalty": [0.35, 0.45, 0.55],
    }

    keys = list(candidates)
    best: tuple[float, dict[str, Any], dict[str, Any]] | None = None
    total = 0

    for values in itertools.product(*[candidates[key] for key in keys]):
        total += 1
        policy = copy.deepcopy(base_policy)
        for key, value in zip(keys, values, strict=True):
            head, tail = key.split(".", 1)
            policy.setdefault(head, {})
            policy[head][tail] = value
        try:
            report = _run_eval(policy)
        except Exception as exc:  # noqa: BLE001
            print(f"[skip] {dict(zip(keys, values, strict=True))}: {exc}")
            continue
        score = float(report.get("pass_rate", 0.0)) + float(report.get("passed_cases", 0)) / 1000.0
        if best is None or score > best[0]:
            best = (score, policy, report)
        print(f"[trial {total}] pass_rate={report.get('pass_rate')} passed={report.get('passed_cases')}")

    if best is None:
        print("No valid policy candidate found.")
        return 1

    _, best_policy, best_report = best
    print("\nBest policy:")
    print(json.dumps(best_policy, ensure_ascii=False, indent=2))
    print("\nBest report:")
    print(json.dumps(best_report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
