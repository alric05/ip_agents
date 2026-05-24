# TM Knockout Search Agent

Initial package skeleton for the trademark knockout search agent.

The intended agent will perform first-pass trademark and brand clearance
screening for a proposed mark, target jurisdictions, and Nice classes or
goods/services. This scaffold intentionally does not contain live API calls,
full workflow logic, or LangGraph registration yet.

## Current Status

- Package imports cleanly.
- Prompt, state, skill, middleware, service, and tool placeholders are present.
- `create_knockout_search_agent()` exists as a placeholder and raises
  `NotImplementedError` when called.
- The agent is not registered in `langgraph.json`.

## Intended Package Boundaries

- Keep trademark-specific state, prompts, tools, services, and middleware under
  `src/tm_knockout_search_agent/`.
- Do not reuse patent novelty prompts, patent search tools, or novelty checker
  middleware directly.
- Add CompuMark and web/common-law integrations in later steps behind package
  local service/tool modules.
