# Specs Index

`docs/specs/` keeps only the current product and system specs that still map to
the codebase.

## Current Reading Order

1. [CURRENT_SYSTEM.md](CURRENT_SYSTEM.md): the system we actually run today.
2. [INTENT_UNDERSTANDING_SPEC.md](INTENT_UNDERSTANDING_SPEC.md): query understanding, semantic ontology, and hybrid intent retrieval shape.
3. [SCHEMA_CONTRACTS.md](SCHEMA_CONTRACTS.md): current JSON contract map across API, intent, tools, execution plan, and response.
4. [ROADMAP.md](ROADMAP.md): next optimization steps after the recent cleanup.
5. [MULTI_TURN_SPEC.md](MULTI_TURN_SPEC.md): route modification and clarification behavior.
6. [CONTEXT_SPEC.md](CONTEXT_SPEC.md): context, profile, route-version, and memory rules.

## Conventions

- Current-turn input always overrides memory.
- Heavy retrieval and enrichment should stay behind bounded tools.
- New orchestration behavior must update code, docs, and eval expectations together.
- Keep specs small and operational; remove planning drafts once they no longer describe the running system.
