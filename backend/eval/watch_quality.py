from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Iterable

from .eval_runner import run_offline_evaluation


WATCH_PATTERNS = (
    "intent_lexicon.py",
    "intent_parser.py",
    "route_service.py",
    "prompt_templates.py",
    "eval_runner.py",
    "eval_cases.json",
    "schemas.py",
    "lexicon/*.json",
)


def _iter_watch_files(root: Path) -> Iterable[Path]:
    for pattern in WATCH_PATTERNS:
        yield from root.glob(pattern)


def _snapshot(root: Path) -> dict[str, float]:
    state: dict[str, float] = {}
    for path in _iter_watch_files(root):
        if path.is_file():
            state[str(path)] = path.stat().st_mtime
    return state


def _run_once() -> None:
    report = run_offline_evaluation()
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch backend quality and rerun offline evaluation.")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds.")
    parser.add_argument("--once", action="store_true", help="Run one evaluation and exit.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]

    if args.once:
        _run_once()
        return 0

    print("Watching backend quality files...")
    previous = _snapshot(root)
    _run_once()

    while True:
        time.sleep(max(0.5, args.interval))
        current = _snapshot(root)
        if current != previous:
            changed = sorted(set(current) ^ set(previous))
            if changed:
                print("\nDetected changes:")
                for item in changed:
                    print(f"- {Path(item).relative_to(root)}")
            previous = current
            _run_once()


if __name__ == "__main__":
    raise SystemExit(main())
