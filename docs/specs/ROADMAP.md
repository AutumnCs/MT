# Roadmap

This roadmap starts from the cleaned current system and keeps one rule in mind:
do not make the backend heavy just to look more agentic.

## 1. Retrieval Governance

- keep recall lanes bounded and configurable
- add better eval coverage for recall diversity and noise risk
- prepare an interface that can swap the local semantic bridge for real embeddings later

## 2. UGC Signal Cleanup

- separate UGC extraction from explanation text generation
- keep route planning dependent on structured UGC signals only
- cap low-confidence UGC impact in ranking and verification
- keep workflow trace rich while keeping route-level summaries compact

## 3. Workflow Trace Consistency

- standardize memory / recall / rerank / planner / verifier trace blocks
- make the trace easy to map into a future workflow UI
- keep user-facing explanations shorter than developer traces

## 4. Multi-Turn Reliability

- keep route modification patch-based
- improve route diff summaries
- verify session carry-over, memory opt-out, and conflict resolution through evals

## 5. Planner Quality

- continue tuning quota, compactness, and travel-awareness weights through policy files
- compare planning-time local matrix vs output-time map calibration
- avoid introducing non-deterministic planner loops

## 6. Tool Boundary Discipline

- new heavy IO should enter through `ToolResult` tools
- avoid leaking raw external payloads directly into prompts
- only split a new tool when it improves observability or reuse

## 7. Contract Hardening

- keep `ParsedIntent` as the shared runtime contract
- introduce a stricter contract map for API / intent / tools / response
- reduce `Any` and ad hoc dict handoffs around current-route and trace payloads
- move LLM output from "JSON extraction" toward schema-constrained structured output

## 8. File Weight Cleanup

- split only when ownership boundaries are clear
- prefer extracting typed helper modules over creating many tiny service files
- target the heaviest modules first:
  - `route_service.py`
  - `response_generator.py`
  - `intent_parser.py`
- keep orchestration in one visible place while moving:
  - route-attempt lifecycle
  - trace assembly
  - modification inheritance
  - clarification policy
  into smaller focused modules
