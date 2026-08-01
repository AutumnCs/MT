# Muse

Muse is a local-life route-planning system for turning a natural-language
outing request into an executable, explainable, and editable city route.

It is designed for requests such as:

- "Plan a relaxed half-day date route with coffee and night views."
- "Give me a family-friendly rainy-day route with low walking pressure."
- "Keep the current route, but make it cheaper and less crowded."

## What This Project Is

Muse is not a free-form chat agent that improvises an itinerary from one large
prompt. The project is built as a controlled planning workflow:

```text
user query
  -> intent understanding
  -> RouteCoordinator / ExecutionPlan
  -> optional memory/context projection
  -> POI retrieval / filtering / rerank
  -> candidate building and route planning
  -> bounded map / heat / UGC tools
  -> validation / workflow guard / repair
  -> explanation and workflow trace
```

LLM usage is intentionally narrow:

- language understanding
- clarification when the request is ambiguous
- bounded repair assistance
- final explanation phrasing

Planning, constraints, ranking, route assembly, and most debugging signals stay
deterministic and observable in backend services.

## Core Capabilities

- Structured intent parsing for city, party, pace, budget, categories, and avoid rules
- Controlled orchestration through `RouteCoordinator` and a bounded execution DAG
- Hybrid POI retrieval with category/text/BM25/vector lanes
- Ranking with query-alignment-aware scoring
- Route planning with validation, patch-based repair, and workflow guardrails
- Compact tool observations for memory, map distance, heat, and UGC signals
- Response traces for eval, debugging, and future route-workspace UI

## Repository Map

- `backend/`: FastAPI route-planning backend
- `lib/`: Flutter client and route workspace UI
- `docs/`: architecture notes, setup guides, and current system specs

Recommended reading order:

1. [backend/README.md](backend/README.md)
2. [backend/services/README.md](backend/services/README.md)
3. [docs/specs/CURRENT_SYSTEM.md](docs/specs/CURRENT_SYSTEM.md)
4. [docs/specs/INTENT_UNDERSTANDING_SPEC.md](docs/specs/INTENT_UNDERSTANDING_SPEC.md)
5. [docs/architecture/AGENT_COORDINATOR_SPEC.md](docs/architecture/AGENT_COORDINATOR_SPEC.md)

## Run Locally

Backend:

```powershell
cd G:\MeituanAgent\backend
python -m pip install -r requirements.txt
python main.py
```

Frontend:

```powershell
cd G:\MeituanAgent
flutter pub get
flutter run -d windows
```

More setup and command examples:

- [docs/setup/QUICKSTART.md](docs/setup/QUICKSTART.md)
- [docs/setup/COMMANDS.md](docs/setup/COMMANDS.md)

## Offline Eval

```powershell
cd G:\MeituanAgent\backend
python -m eval.eval_runner
```

The regression suite covers intent parsing, route modification, workflow trace,
memory behavior, route persistence, quality constraints, tool scheduling,
failure boundaries, and intent repair.

## Current Engineering Direction

The current codebase is moving toward a schema-driven planning system rather
than a prompt-heavy prototype. The important boundaries are:

- intent understanding and execution do not share one flat schema
- tools are bounded, auditable, and fallback-aware
- retrieval is hybrid but still dependency-light by default
- route planning remains workflow-constrained rather than open-ended ReAct

If docs disagree with code, trust this order:

1. current code
2. offline evals
3. backend docs
4. older reports or archived notes
