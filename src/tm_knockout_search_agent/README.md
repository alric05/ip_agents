# TM Knockout Search Agent

Initial implementation for the trademark knockout search agent.

The intended agent will perform first-pass trademark and brand clearance
screening for a proposed mark, target jurisdictions, and Nice classes or
goods/services. This v1 implementation intentionally does not contain live
CompuMark or web API calls.

## Current Status

- Package imports cleanly.
- Prompt, state, skill, middleware, service, and tool modules are present.
- `create_tm_knockout_search_agent()` returns a deterministic invokable object.
- `check_tm_knockout()` runs local planning, risk, stopping, session, and report
  helpers without live external calls.
- The assistant is registered in `langgraph.json` as
  `tm_knockout_search_agent`.

## Intended Package Boundaries

- Keep trademark-specific state, prompts, tools, services, and middleware under
  `src/tm_knockout_search_agent/`.
- Do not reuse patent novelty prompts, patent search tools, or novelty checker
  middleware directly.
- Add CompuMark and web/common-law integrations in later steps behind package
  local service/tool modules.
