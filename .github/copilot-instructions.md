# Copilot Instructions — Novelty Checker (LangGraph Deep Agent)

## Architecture Overview

This is a **multi-agent novelty/prior-art search system** built on [LangGraph](https://langchain-ai.github.io/langgraph/) + the [deepagents](https://github.com/langchain-ai/deepagents) framework. An orchestrator agent delegates parallel research tasks to specialized sub-agents (patent, NPL, semantic) that query external databases, then iterates until coverage targets are met.

**Key structural decisions:**
- `src/novelty_checker/AGENTS.md` is the orchestrator's system prompt, loaded at runtime by `MemoryMiddleware` — edit it to change agent behaviour, not Python code.
- `src/novelty_checker/subagents.yaml` defines sub-agent names, system prompts, and tool bindings. Adding a researcher means adding a YAML block + wiring tools.
- `src/novelty_checker/skills/*/SKILL.md` files are progressively disclosed to the agent via `SkillsMiddleware` — one per pipeline stage.
- `src/novelty_checker/prompts.py` holds modular prompt templates (`NOVELTY_WORKFLOW_INSTRUCTIONS`, `SEARCH_DELEGATION_INSTRUCTIONS`, etc.) combined at graph-build time in `deep_agent.py:get_orchestrator_instructions()`.

## Project Layout

| Path | Purpose |
|------|---------|
| `studio.py` | LangGraph Studio entry point — exposes `graph` for `langgraph dev` |
| `src/novelty_checker/deep_agent.py` | Agent factory (`create_deep_agent`), session management, subagent loader |
| `src/novelty_checker/state.py` | All TypedDicts: `Feature`, `Reference`, `CoverageStatus`, `RoundFindings` |
| `src/tools/registry.py` | Tool categories (`SEARCH_TOOLS`, `ANALYSIS_TOOLS`, etc.) and `get_all_tools()` |
| `src/tools/search.py` | `@tool`-decorated search functions wrapping API clients |
| `src/tools/clients/{innography,wos,ngsp}.py` | HTTP clients for Innography (patents), Web of Science (NPL), NGSP (semantic) |
| `src/config/llm.py` | LLM factory — Azure OpenAI via LiteLLM (`get_llm()`) |
| `src/config/settings.py` | Pydantic `Settings` model reading `.env` |
| `deep-agents-ui/` | Next.js 16 + Tailwind frontend (App Router) connecting to LangGraph API on `:2024` |
| `sessions/<id>/` | Per-run isolated workspace with `scope.md`, `features.md`, `findings/` |

## Running the System

```bash
# Backend (LangGraph dev server on :2024)
source .venv/bin/activate && langgraph dev

# Frontend (Next.js on :3000) — in a second terminal
cd deep-agents-ui && npm run dev
```

In the UI, set **Deployment URL** = `http://127.0.0.1:2024` and **Assistant ID** = `novelty_checker` (from `langgraph.json`).

To kill a stuck backend: `kill -9 $(lsof -t -i:2024)`

## Adding / Modifying Tools

1. Create a `@tool`-decorated function in the appropriate `src/tools/*.py` file.
2. Register it in `src/tools/registry.py` under the right category list (e.g., `SEARCH_TOOLS`).
3. If a sub-agent needs the tool, add its name to the `tools:` list in `subagents.yaml`.
4. Tool names in YAML must exactly match the Python function name.

## Adding a Sub-Agent

Add a block in `src/novelty_checker/subagents.yaml`:
```yaml
citation-researcher:
  description: "One-line description"
  system_prompt: |
    Detailed instructions…
  tools:
    - get_patent_citations
    - batch_citation_search
```
`load_subagents()` in `deep_agent.py` auto-wires tools by name from the registry.

## State & Type Conventions

- All shared types live in `src/novelty_checker/state.py` as `TypedDict` subclasses.
- Use `NotRequired` for optional fields; `Literal` for enums (e.g., triage labels `"A" | "B" | "C"`).
- `Reference.feature_coverage` maps feature IDs → `"Y" | "Y1" | "N"` (the older `feature_mapping` is deprecated).
- `Reference.discovery_method` tracks provenance: `"keyword"`, `"semantic"`, `"npl"`, `"citation_forward"`, `"citation_backward"`.

## Testing

```bash
source .venv/bin/activate
pytest                                    # all tests
pytest tests/test_search_phase.py -k "test_patent_search"  # specific
pytest --cov=src --cov-report=html        # coverage
```

Tests use `pytest` with `asyncio_mode = "auto"` (see `pyproject.toml`).

## Environment & Configuration

All secrets go in `.env` at project root (loaded by `python-dotenv`). Required vars:
- `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME`
- `INNOGRAPHY_USER_NAME`, `INNOGRAPHY_USER_SECRET`, `INNOGRAPHY_USER_TOKEN`
- `WOS_API_KEY`, `CLARIVATE_NGSP_API_KEY`

Validate with: `python -c "from src.config.settings import get_settings; print(get_settings())"`

## Frontend Conventions (deep-agents-ui)

- Next.js 16 App Router with Turbopack (`npm run dev` uses `--turbopack`).
- UI components in `src/components/ui/` (Radix + shadcn pattern via `components.json`).
- LangGraph SDK client created in `src/providers/ClientProvider.tsx`; chat state in `src/providers/ChatProvider.tsx` → `useChat` hook.
- Config (deployment URL, assistant ID) stored in `localStorage` via `src/lib/config.ts`.

## Key Patterns to Preserve

- **Findings persistence**: The `FindingsPersistenceMiddleware` auto-captures search results. Explicit `save_round_findings` / `get_all_findings` tools also exist as a safety net. Both paths write to the session's `findings/` directory.
- **Session isolation**: Every agent run creates `sessions/<timestamp>_<uuid>/`. Read-only files (`AGENTS.md`, `skills/`) are referenced by absolute path, not copied.
- **Iterative research loop**: The core loop is Recall → Delegate → Receive → Persist → Cite-check → Reflect → Decide. This is defined in `AGENTS.md` and `prompts.py`, not in graph edges.
