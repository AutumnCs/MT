from __future__ import annotations

import json

from .eval_runner import run_offline_evaluation


def main() -> int:
    report = run_offline_evaluation()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("pass_rate", 0.0) == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
