# Context Spec

This spec defines the lightweight context and profile system for MeituanAgent.
The goal is to make multi-turn route planning, user profiling, and route replay
maintainable without adding a heavy agent framework.

## Goals

- Keep session context small and explicit.
- Turn user turns into structured events.
- Project events into a durable profile.
- Keep route versions replayable and comparable.
- Make context useful to planning, not just logging.
- Stay lightweight and easy to debug.

## What to store

### 1) Session context
Current-turn state only.

Examples:
- session id
- current mode: `idle`, `generate`, `clarify`, `modify`, `route`
- current city
- current route id
- current route title/summary
- last user query
- last task hint
- whether clarification is pending

### 2) Behavior events
Append-only event log.

Examples:
- `route_created`
- `route_modified`
- `clarification_requested`
- `clarification_answered`
- `route_favorited`
- `route_copied`
- `route_rejected`
- `city_changed`
- `preference_selected`

### 3) Route versions
Every meaningful route result should be versioned.

Each version should carry:
- version id
- query
- intent summary
- diagnostics
- route snapshot
- title and summary

### 4) User profile
Projected long-term preference state.

Examples:
- home city
- frequent cities
- preferred categories
- preferred preferences
- avoid preferences
- preferred pace
- preferred transport mode
- budget band
- companion types

### 5) Knowledge layer
Static system knowledge.

Examples:
- lexicon
- capability registry
- policy weights
- display labels
- map facts

## Write rules

- Write session state on every meaningful turn.
- Write events only when something observable happened.
- Write route versions when a route is generated or modified.
- Write profile signals only from stable evidence.
- Never let a one-off phrase dominate the profile.

## Read rules

- Read session context for the current turn.
- Read profile only as a soft bias, never as a hard override.
- Read route versions for modification and explanation.
- Read recent events for trace/debug and projection.

## Conflict rules

- Explicit current-turn input beats profile.
- Recent evidence beats old evidence.
- Repeated behavior beats single mentions.
- Session preferences beat long-term defaults.

## Decay rules

- Temporary hints should fade.
- Weak signals should lose weight over time.
- Old preferences should not block a new route style.

## What this should power

- multi-turn route modification
- lightweight clarification
- user profile projection
- route replay and rollback
- personalization for new turns
- traceable debugging

## What this should not become

- a full chat memory dump
- a heavy agent memory hub
- unbounded prompt stuffing
- a hidden black box with no versioning

## Implementation entry points

- `backend/core/context_models.py`
- `backend/services/context_service.py`
- `backend/core/api_contracts.py`
- `backend/main.py`

