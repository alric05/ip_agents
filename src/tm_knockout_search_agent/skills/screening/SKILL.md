---
name: screening
description: Screen and rank candidate trademark conflicts.
triggers:
  - screening
  - risk
  - candidate
  - conflict
---

# Screening Skill

Use this skill after candidates have been normalized.

## Evaluate

Consider:

- Mark similarity
- Goods/services relatedness
- Jurisdiction or regional system overlap
- Active versus inactive status
- Owner fame or large-company ownership
- Web/common-law market presence
- Source reliability and source failures

## Risk Labels

Use only:

- LOW
- MEDIUM
- HIGH
- SEARCH_FAILED

## Rules

- Do not overstate weak web evidence.
- Do not treat inactive/dead records the same as active records.
- A strong active registry conflict should outrank weak web context.
- Strong commercial web use can raise concern when registry evidence is not
  conclusive.
- Famous or large-owner signals can raise concern even when classes or goods
  context is weaker.

## Output

Produce ranked candidate findings with:

- candidate id
- display name
- source
- risk label
- score or ranking rationale
- country/system relevance
- concise machine-readable reasons
