---
name: knockout-search
description: Plan and run staged trademark knockout searches.
triggers:
  - knockout
  - search
  - exact mark
  - similar mark
---

# Knockout Search Skill

Use this skill once normalized criteria are available.

## Plan

Use the deterministic query planner. Do not invent provider-specific syntax.

Planned stages:

1. Exact active marks
2. Similar active marks
3. Web/common-law search
4. Inactive/dead contextual search if configured or triggered

## Sources

- CompuMark is the primary trademark registry source.
- Web search is supplementary for common-law use, fame, owner signals,
  domain/social context, and market use.
- Litigation search is deferred to a later phase.

## Execution Rules

- Use only curated `tm_knockout_search_agent` tools.
- Do not use tools from other agents.
- Do not stop at the first strong result.
- Continue until all required planned stages complete, a required source fails,
  or a deterministic budget limit is reached.
- Record failed or unavailable sources in structured artifacts.

## Output

Produce:

- planned query groups
- completed query groups
- source status notes
- normalized candidate inputs for screening
