# Intent Understanding

This spec describes the target shape of Muse intent understanding after the
recent cleanup. It is intentionally practical: the goal is not a huge generic
agent brain, but a robust query-understanding layer that supports route
planning, route modification, and tool orchestration.

## Design Position

We do not treat intent understanding as one prompt or one classifier.

We treat it as a bounded query-understanding stack:

```text
user query
  -> normalization and tokenization
  -> slot extraction
  -> semantic scoring
  -> intent schema normalization
  -> hybrid retrieval query build
  -> route/planning/tool decisions
```

This is closer to search-style query understanding than to a free-form ReAct
loop.

## What We Learned From Public References

There is no public Meituan "official route-planning lexicon" we can directly
reuse. The public Meituan search and NLP material points to a consistent method:

- NER is a base signal for query understanding, recall, and intent recognition.
- query rewriting is a first-class signal, not a cosmetic post-process.
- category and attribute understanding should be structured, not hidden in one
  opaque embedding.
- knowledge-graph style taxonomy and attribute systems matter for downstream
  recall and ranking.

For our project, that means:

- keep a canonical category/preference/avoid ontology
- separate hard constraints from soft semantic hints
- use embeddings as one recall signal, not the only source of truth
- let structured intent drive tool and planner behavior

## Runtime Layers

### 1. Lexical / Slot Layer

Purpose:

- city, time, budget, start location, transport, hard avoid constraints
- direct category and preference hits
- explicit route modification phrases such as add/remove/replace/relax

Implementation:

- `backend/core/intent_parser.py`
- `backend/core/text_tokenizer.py`
- `backend/core/intent_lexicon.py`

This layer should stay deterministic and cheap.

### 2. Semantic Ontology Layer

Purpose:

- unify prompt vocabulary, parsing vocabulary, and retrieval vocabulary
- map long-tail language into canonical tags
- keep category semantics separate from atmosphere or constraint semantics

Implementation:

- `backend/core/semantic_ontology.py`
- `backend/core/semantic_intent.py`
- `backend/lexicon/categories.json`
- `backend/lexicon/preferences.json`
- `backend/lexicon/avoids.json`

This layer gives us canonical tags such as `food`, `scene`, `quiet`,
`avoid_queue`, `indoor`, and their aliases.

### 3. LLM Extraction Layer

Purpose:

- parse compositional or ambiguous requests
- score semantic hypotheses
- emit uncertainty and clarification fields

Implementation:

- `backend/core/llm_intent_client.py`
- `backend/core/prompt_templates.py`

Rules:

- LLM output must always normalize into `ParsedIntent`
- LLM does not directly decide route selection
- when local parsing is confident enough, we fast-gate and skip the LLM

### 4. Hybrid Retrieval Query Layer

Purpose:

- turn intent into a retrieval surface for POI recall and rerank
- reduce dependence on exact wording
- avoid one noisy recall lane dominating the candidate pool

Implementation:

- `backend/services/semantic_retriever.py`
- `backend/services/poi_retriever.py`

Current lanes:

- category / exact lexical
- text-signal match
- semantic similarity
- lightweight vector-style score
- must-include
- start-location bias

## Modification Understanding Rules

Route modification is not the same as first-turn planning.

We now keep these rules:

- inherit the user's original intent when available
- do not blindly inherit every category covered by the current route
- adding a support stop such as breakfast or coffee should preserve a compact
  route skeleton instead of exploding route breadth
- current-turn request overrides memory and older route assumptions

This keeps incremental planning controllable and avoids route bloat.

## Why We Are Not Doing "All Data First, Then LLM"

That pattern is simple but weak for our use case:

- wastes context and retrieval cost
- cannot branch cleanly by intent
- performs badly in route modification and multi-turn refinement
- makes noise control harder

Instead, we use a thin planning/orchestration layer and bounded tool calls,
driven by structured intent.

## Noise Control Principles

To keep generalization without making the system too heavy:

- ontology tags stay small and canonical
- semantic scores are merged into structured fields, not dumped as raw text
- retrieval lanes have caps and thresholds
- UGC signals stay summarized and tool-bounded
- memory is a soft bias, not a hidden prompt dump

## Next Up

1. Split semantic understanding into explicit slots:
   `goal`, `category`, `atmosphere`, `constraint`, `mobility`, `time`.
2. Add synonym mining / phrase expansion from eval failures and curated logs.
3. Add a lightweight confusion set for category collisions such as
   `scene` vs `street`, `culture` vs `museum`, `food` vs `coffee`.
4. Add offline diagnostics for parse path, semantic top hits, and retrieval lane
   contribution by case.
