# backend/lexicon

`lexicon/` stores structured vocabulary and aliases used for intent
normalization.

## Files

| File | Purpose |
|---|---|
| `cities.json` | city aliases and city landmarks |
| `categories.json` | category synonyms and route labels |
| `preferences.json` | preference synonyms |
| `avoids.json` | avoid/negation expressions |
| `transports.json` | transport expressions |
| `display_labels.json` | display-layer label mapping |

## What this layer should do

- Help the model and parser map user phrases to stable tags.
- Keep common expressions in one place.
- Keep long-tail or uncertain phrases out of the capability registry.

## Maintenance rule

- Only add high-confidence, repeatable expressions.
- If something is still fuzzy, keep it out of the core tags and review it in
  regression cases first.

