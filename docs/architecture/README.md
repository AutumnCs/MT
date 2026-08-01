# Architecture Docs

These docs explain why the system is split the way it is, and where future
agentic behavior is allowed to live.

## Current Docs

- [AGENT_COORDINATOR_SPEC.md](AGENT_COORDINATOR_SPEC.md): controlled coordinator, `RouteState`, `ExecutionPlan`, tool observations, RAG noise control, memory boundaries, and patch-based repair.
- [AGENT_HARNESS_SPEC.md](AGENT_HARNESS_SPEC.md): earlier harness and tool-contract thinking. Keep as background; prefer the coordinator spec for current implementation.
- [SKILL_SPEC.md](SKILL_SPEC.md): skill governance and capability boundaries. Keep as background for future toolization.
- [FLUTTER_STRUCTURE.md](FLUTTER_STRUCTURE.md): Flutter route workspace structure.

## Current Architecture

```text
Intent parsing
  -> RouteCoordinator builds ExecutionPlan
  -> optional memory context tool when a session exists
  -> POI retrieval / ranking / candidate building
  -> route planning
  -> optional map/UGC tools through Tool Layer
  -> validation
  -> patch-based repair when quality gaps are repairable
  -> explanation and workflow trace
```

The main route flow remains deterministic and replayable. Dynamic behavior is
allowed through bounded tools, explicit budgets, fallback policy, and typed
observations.

## Source Of Truth

When docs disagree, use this order:

1. Current code and evals.
2. [AGENT_COORDINATOR_SPEC.md](AGENT_COORDINATOR_SPEC.md).
3. Product specs in `docs/specs/`.
4. Older reports and background docs.
