# TM Knockout Search Agent Implementation Map

This map documents how the existing `novelty_checker` agent is built and which
parts should be reused, copied, adapted, or avoided for
`knockout_search_agent` / `tm_knockout_search_agent`.

Scope of this document:

- Inspect existing implementation only.
- Do not implement the new agent yet.
- Do not modify `novelty_checker`.
- Do not register the new agent in `langgraph.json` yet.

Naming note: the product spec uses `tm_knockout_search_agent` as the package and
assistant id. Use that name for new code unless the product name is explicitly
changed.

## 1. Existing Novelty Checker Entry Points

### `src/novelty_checker/deep_agent.py`

Primary factory and orchestration module for the current agent.

Important pieces:

- `SESSIONS_DIR = <repo>/sessions`
- `create_session_workspace(session_id=None)`
  - Creates `sessions/<session_id>/`.
  - Clears an existing same-named session unless `reuse_session` is used higher
    up.
  - Creates `sessions/<session_id>/findings/`.
- `cleanup_old_sessions(max_age_hours=24, max_sessions=50)`
  - Deletes older session directories beyond configured retention.
- DeepAgents monkey patches
  - Raises subagent recursion limits to 500.
  - Wraps subagent `invoke` / `ainvoke` so task subgraphs do not inherit low
    default recursion limits.
- `InMemorySkillsMiddleware`
  - Reads `src/novelty_checker/skills/*/SKILL.md`.
  - Injects skill metadata into the system prompt.
  - Provides a `read_skill(name=...)` tool.
  - Avoids copying skills into session directories.
- `get_orchestrator_instructions(...)`
  - Combines prompt constants from `prompts.py`.
  - Optionally appends API structured-output instructions.
  - Always appends novelty guardrails.
  - Can strip NPL references when `ENABLE_NPL_SEARCH` is false.
- `load_subagents(...)`
  - Reads `subagents.yaml`.
  - Maps tool names to tool objects from `src.tools.registry`.
  - Adds per-subagent `ContentFilterMiddleware`.
  - Adds per-subagent `TelemetryMiddleware` and `QueryLogMiddleware` when
    sources are provided.
  - Replaces findings tools with backend-aware versions when a backend is
    supplied.
- `get_default_model(model="gpt-5")`
  - Creates a fallback `ChatLiteLLM`.
  - Most deployed paths use `src.config.llm.get_llm()` instead.
- `create_deep_agent(...)`
  - Main graph factory.
  - Supports static `FilesystemBackend` mode and thread-aware factory mode.
  - Loads `AGENTS.md` into the system prompt instead of using DeepAgents
    file-based `memory`.
  - Uses `get_all_tools()` and backend-aware findings tools.
  - Loads subagents from YAML.
  - Calls DeepAgents `_create_deep_agent(...)`.
  - Attaches a long ordered middleware stack.
- `check_novelty(...)`
  - Convenience one-shot runner.
  - Builds initial user message and invokes the graph.
- `create_novelty_checker_graph = create_deep_agent`
  - Backward-compatibility alias.

Reuse decision for TM:

- Reuse the overall factory pattern.
- Copy/adapt the session factory pattern into `src/tm_knockout_search_agent/`.
- Copy/adapt `InMemorySkillsMiddleware` unless it is first extracted to a shared
  neutral module.
- Do not import novelty prompt constants, novelty state, novelty middleware, or
  `src.tools.get_all_tools()`.
- Do not reuse the patent/NPL/semantic subagent wiring directly.

### `src/novelty_checker/main.py`

CLI entry point.

Important behavior:

- Builds an `argparse` CLI for:
  - interactive mode
  - single idea check
  - optional `--thread-id`
  - optional rich/plain output
- Performs Derwent JWT preflight via `check_derwent_jwt()`.
- Uses `src.config.llm.get_llm()`.
- Calls `create_deep_agent(..., use_backend_factory=True)` in interactive mode.
- Calls `check_novelty(..., use_backend_factory=True)` in single-check mode.
- Initializes novelty state fields such as:
  - `customer_idea`
  - `current_stage`
  - `features`
  - `references`
  - `todos`

Reuse decision for TM:

- Reuse the CLI shape.
- Replace Derwent JWT preflight with CompuMark/web-search configuration checks.
- Replace `idea` terminology with brand/search criteria terminology.
- Do not initialize novelty state fields.

### `langgraph.json`

Current graph registration:

```json
{
  "graphs": {
    "novelty_checker": "./studio.py:graph"
  },
  "env": ".env",
  "python_version": "3.12",
  "dependencies": [
    ".",
    "./src"
  ]
}
```

Reuse decision for TM:

- Do not modify this file in this step.
- Later registration should add a second graph id, likely
  `tm_knockout_search_agent`.
- Prefer pointing to a TM-specific Studio entry point, not `studio.py`, unless
  the root Studio module becomes a multi-agent dispatcher.

### `studio.py`

LangGraph Studio entry point for novelty checker.

Important behavior:

- Adds project root to `sys.path`.
- Loads `.env`.
- Creates `graph` at module import time:
  - `model=get_llm()`
  - `checkpointer=None`
  - `use_custom_state=False` for Studio schema compatibility
  - `use_backend_factory=True` for per-thread sessions
- Performs warn-only Derwent JWT preflight.
- Applies serialization/channel patches for Studio:
  - monkey-patches `langgraph_api.serde.default` around `MockValSer`
  - removes broken output/stream channels such as `files`, `todos`,
    `structured_response`, `memory_contents`

Reuse decision for TM:

- Reuse the Studio compatibility lessons.
- Create a TM-specific Studio module later.
- Keep the channel-stripping logic if DeepAgents contributes the same
  schema-hostile channels.
- Replace Derwent preflight with TM source preflight.

### `server.py`

FastAPI server for novelty checker.

Important behavior:

- Creates the novelty graph once in `lifespan`.
- Uses:
  - `use_custom_state=True`
  - `use_backend_factory=True`
  - `emit_structured_json=True`
- Exposes `app.state.graph`, `default_session_id`, `sessions_dir`, and a
  `ThreadAwareBackendFactory`.
- Includes `src.novelty_checker.api.endpoints`.
- Provides `/chat/stream` SSE endpoint with novelty-specific timeline labels,
  stages, Derwent JWT auth, and report detection.

Reuse decision for TM:

- Do not reuse directly.
- If TM needs an API in v1, make separate TM API modules or a clean multi-agent
  server layer.
- The current server is tightly coupled to novelty stages, Derwent JWT, labels,
  timeline builder, and `final_report.md` semantics.

## 2. Existing Prompt and Instruction Structure

### `src/novelty_checker/AGENTS.md`

Role and workflow memory for the novelty agent.

Main contents:

- Patent novelty/prior-art mission.
- Hard boundaries:
  - no patentability opinions
  - no internal architecture disclosure
  - no claim drafting/design-around/infringement
  - no filing/prosecution strategy
  - explicitly declines trademark search and clearance
- Stage pipeline:
  - scoping
  - feature definition
  - research loop
  - screening
  - report
- Two mandatory human confirmation gates:
  - Gate 1 scope confirmation
  - Gate 2 feature matrix confirmation
- Post-Gate-2 autonomous mode.
- Patent/NPL/semantic/citation search and report rules.

Reuse decision for TM:

- Do not reuse text.
- Important: current `AGENTS.md` explicitly declines trademark tasks, so using
  it would break the new agent.
- Reuse only the file-as-agent-memory pattern.
- Create `src/tm_knockout_search_agent/AGENTS.md` with trademark-specific scope,
  legal disclaimers, no filing advice, no final legal opinion, and no claim or
  patent novelty language.

### `src/novelty_checker/prompts.py`

Modular prompt constants.

Important constants:

- `NOVELTY_WORKFLOW_INSTRUCTIONS`
  - plan, scope, feature confirmation, research loop, report.
  - mandates file persistence to `/scope.md`, `/features.md`,
    `/findings/round_X.md`, `/references.md`, `/final_report.md`.
- `SEARCH_DELEGATION_INSTRUCTIONS`
  - coordinator pattern.
  - parallel `task()` dispatch.
  - feature context isolation.
- `PATENT_RESEARCHER_INSTRUCTIONS`
- `NPL_RESEARCHER_INSTRUCTIONS`
- `SEMANTIC_RESEARCHER_INSTRUCTIONS`
- `STRUCTURED_OUTPUT_ADDENDUM`
  - API-only JSON blocks for scoping/features UI.
- `GUARDRAILS_INSTRUCTIONS`
  - patent-novelty guardrails.

Reuse decision for TM:

- Reuse the modular-prompt structure, not the prompt text.
- Create TM equivalents such as:
  - `TM_WORKFLOW_INSTRUCTIONS`
  - `TM_SEARCH_PLANNING_INSTRUCTIONS`
  - `COMPUMARK_SEARCH_INSTRUCTIONS`
  - `WEB_COMMON_LAW_SEARCH_INSTRUCTIONS`
  - `TM_RISK_ASSESSMENT_INSTRUCTIONS`
  - `TM_ADVERSARIAL_REVIEW_INSTRUCTIONS`
  - optional `STRUCTURED_OUTPUT_ADDENDUM`
- Avoid human confirmation gates except for missing required inputs.
- Avoid feature-coverage wording, A/B/C patent triage semantics, and novelty
  verdict semantics.

### `src/novelty_checker/skills/`

Current skills:

- `scoping`
- `feature-definition`
- `parallel-search`
- `patent-search`
- `npl-search`
- `semantic-search`
- `citation-search`
- `screening`
- `report`

The skills use YAML frontmatter with `name`, `description`, and `triggers`.
`InMemorySkillsMiddleware` parses this metadata and exposes full content through
`read_skill(name=...)`.

Reuse decision for TM:

- Reuse the skills progressive-disclosure mechanism.
- Do not reuse the existing skill content.
- Create TM-specific skills, likely:
  - `intake`
  - `jurisdiction-normalization`
  - `nice-class-normalization`
  - `compumark-search`
  - `web-common-law-search`
  - `candidate-ranking`
  - `risk-assessment`
  - `adversarial-review`
  - `report`

### `src/novelty_checker/subagents.yaml`

Current subagents:

- `patent-researcher`
- `npl-researcher`
- `semantic-researcher`
- `citation-researcher`
- `coverage-analyst`
- `report-writer`
- legacy/alternate path agents:
  - `keyword-precision-searcher`
  - `semantic-recall-searcher`
  - `structural-combo-searcher`

The YAML format:

- top-level subagent name
- `description`
- `system_prompt`
- optional `model`
- `tools` list using registry names

Reuse decision for TM:

- Reuse the YAML-driven subagent pattern if TM needs subagents.
- Do not reuse existing subagents.
- V1 can be simpler than novelty checker:
  - either no subagents, or
  - focused subagents such as `compumark-searcher`, `web-common-law-searcher`,
    `risk-reviewer`, `report-writer`.
- Keep write access controlled. The novelty loader forbids `write_file` and
  `edit_file` in subagents; this is a good pattern to keep if TM subagents are
  read/search-only.

## 3. Existing State Structure

### `src/novelty_checker/state.py`

Current state types:

- Middleware/general:
  - `Todo`
  - `SkillMetadata`
- Novelty domain:
  - `Feature`
  - `Reference`
  - `CoverageStatus`
  - `VocabularyTerm`
  - `RoundFindings`
  - `FindingsAccumulator`
  - `FeatureMatrixRow`
- Legacy:
  - `Plan`
  - `SearchResult`
  - `NoveltyAssessment`
- Reducers:
  - `merge_references`
  - `merge_findings_accumulator`
  - `merge_coverage`
- Main graph state:
  - `DeepAgentState`
  - alias `AgentState = DeepAgentState`

Important `DeepAgentState` fields:

- `messages`: annotated with `add_messages`
- `todos`
- `skills_metadata`
- `loaded_skills`
- `customer_idea`
- `scope_markdown`
- `scope_confirmed`
- `features`
- `features_confirmed`
- `search_queries_log`
- `references`
- `current_search_cycle`
- `findings_accumulator`
- `coverage`
- `overall_coverage`
- `report_markdown`
- `current_stage`
- `remaining_steps`
- `is_last_step`
- legacy `plan`, `search_results`, `assessment`

Novelty-specific fields:

- `customer_idea`
- `scope_markdown`
- `scope_confirmed`
- `features`
- `features_confirmed`
- `references` as patent/NPL references
- `findings_accumulator`
- `coverage`
- `overall_coverage`
- `report_markdown`
- `current_stage` values such as `patent_search`, `npl_search`,
  `semantic_search`, `screening`
- all feature-coverage and novelty assessment types

Reuse decision for TM:

- Reuse:
  - `messages`
  - `todos`
  - `skills_metadata`
  - `loaded_skills`
  - reducer pattern for parallel state updates
- Do not reuse:
  - `Feature`
  - `Reference`
  - `CoverageStatus`
  - `FindingsAccumulator`
  - `FeatureMatrixRow`
  - novelty stage names
  - novelty assessment legacy types
- Create TM-specific state types, for example:
  - `TrademarkSearchRequest`
  - `SearchCriteria`
  - `Jurisdiction`
  - `NiceClassSelection`
  - `TrademarkSearchQuery`
  - `TrademarkRecord`
  - `WebUseRecord`
  - `KnockoutCandidate`
  - `CandidateRanking`
  - `RiskAssessment`
  - `SourceFailure`
  - `AdversarialReview`
  - `TMKnockoutState`

Recommended TM state principle:

- JSON artifacts should be the source of truth.
- State should carry enough structured data for graph continuity, but session
  artifacts should be what report generation and evaluation read.

## 4. Existing Tools

### `src/tools/registry.py`

Current shared registry is novelty/patent oriented.

Tool categories:

- `SEARCH_TOOLS`
  - `patent_keyword_search`
  - `npl_search`
  - `semantic_patent_search`
  - `get_patent_citations`
- `BATCH_SEARCH_TOOLS`
  - `batch_patent_search`
  - `batch_npl_search`
  - `batch_semantic_search`
  - `batch_unified_search`
- `LOGGING_TOOLS`
  - `log_search_execution`
  - `log_batch_search_execution`
- `ANALYSIS_TOOLS`
  - `evaluate_coverage`
  - `triage_reference`
  - `map_features_to_reference`
  - `generate_search_strategy`
  - `build_feature_matrix`
  - `validate_feature_matrix_format`
  - `aggregate_search_results`
- `REFLECTION_TOOLS`
  - `think_tool`
- `CONTENT_TOOLS`
  - `get_patent_details`
- `CITATION_TOOLS`
  - `get_patent_citations`
  - `batch_citation_search`
  - `citation_chain_search`
- `DERWENT_TOOLS`
  - `search_derwent_patents_fld`
  - `search_derwent_citations`
  - `patent_keyword_search`
- `FINDINGS_PERSISTENCE_TOOLS`
  - tools from `src.tools.findings`

Registry functions:

- `get_all_tools()`
- `get_reflection_tools()`
- `get_findings_tools()`
- `get_content_tools()`
- `get_citation_tools()`
- `get_derwent_tools()`
- `get_search_tools(include_batch=True)`
- `get_analysis_tools()`
- `get_batch_only_tools()`
- `get_tool_info()`

Reuse decision for TM:

- Do not call `src.tools.registry.get_all_tools()` from the TM agent.
- Reuse only `think_tool` if it is truly domain-neutral.
- Prefer a package-local registry:
  - `src/tm_knockout_search_agent/tools/registry.py`
  - `src/tm_knockout_search_agent/tools/compumark.py`
  - `src/tm_knockout_search_agent/tools/web_search.py`
  - optional `src/tm_knockout_search_agent/tools/analysis.py`
  - optional `src/tm_knockout_search_agent/tools/artifacts.py`

### `src/tools/search.py`

Current search tools route to patent/NPL/semantic clients:

- `patent_keyword_search`
- `npl_search`
- `semantic_patent_search`
- `get_patent_details`
- `get_patent_citations`
- `batch_citation_search`
- `citation_chain_search`
- `batch_patent_search`
- `batch_npl_search`
- `batch_semantic_search`
- `batch_unified_search`
- `log_search_execution`
- `log_batch_search_execution`

Important patterns:

- LangChain `@tool` decorators.
- Pydantic/Annotated descriptions on parameters.
- Retry wrapper via `retry_with_backoff`.
- Formatted markdown return values for the LLM.
- Batch tools for efficient multi-query searches.

Reuse decision for TM:

- Reuse the tool authoring style.
- Do not reuse patent/NPL/NGSP tools for trademark searching.
- TM search tools should return structured JSON or JSON-compatible dicts where
  possible, because the TM spec says JSON artifacts are the source of truth.
- TM CompuMark tools should probably wrap:
  - identical knockout search
  - custom/screening search
  - details retrieval
  - goods/services retrieval
  - full-text link creation, if supported

### `src/tools/analysis.py`

Current analysis tools:

- `evaluate_coverage`
- `triage_reference`
- `map_features_to_reference`
- `generate_search_strategy`
- `build_feature_matrix`
- `validate_feature_matrix_format`

These tools implement patent novelty concepts:

- feature coverage levels
- A/B/C relevance labels
- Y/Y1/N mapping
- patent/NPL feature matrix
- X-category anticipatory references

Reuse decision for TM:

- Do not reuse these tools.
- Use the pattern to build TM-specific deterministic helpers:
  - normalize mark text
  - compute mark-similarity signals
  - normalize jurisdiction/status
  - normalize goods/services text
  - rank knockout candidates
  - validate final report JSON shape
- Do not import patent `CoverageLevel` or feature-mapping semantics.

### `src/tools/findings.py`

Current explicit findings tools:

- `save_round_findings`
- `get_all_findings`
- `get_coverage_gaps`
- `summarize_findings_for_report`
- `detect_diminishing_returns`
- `create_backend_findings_tools(backend)`

Important artifact paths:

- `/scope.md`
- `/features.md`
- `/findings`
- `/findings_accumulator.json`
- `/references.md`

Important pattern:

- Provides both plain tools and backend-aware tools created with
  `StructuredTool.from_function`.
- Uses a module-level lock to serialize accumulator writes.
- Writes markdown round findings and updates JSON accumulator.
- Backend factory support lets the same tool work in static and per-thread
  sessions.

Reuse decision for TM:

- Do not reuse the concrete tools.
- Reuse the backend-aware tool factory pattern.
- Create TM artifact tools around the spec artifacts:
  - `save_search_criteria`
  - `save_query_plan`
  - `save_compumark_results`
  - `save_web_results`
  - `save_normalized_candidates`
  - `save_ranked_findings`
  - `save_risk_assessment`
  - `save_adversarial_review`
  - `save_final_report`
  - `get_tm_artifact_summary`

### `src/tools/clients/`

Current clients:

- `derwent.py`
- `derwent_auth.py`
- `wos.py`
- `ngsp.py`
- `innography.py` retained as reference
- `schemas.py` for patent/article/search-result shapes

No CompuMark client exists in the repo.

Reuse decision for TM:

- Do not add TM client code under patent client modules.
- Add a package-local TM client, likely:
  - `src/tm_knockout_search_agent/tools/clients/compumark.py`
  - `src/tm_knockout_search_agent/tools/clients/schemas.py`
- If a truly shared HTTP/auth helper emerges later, extract it deliberately.
  Do not modify shared patent clients for v1.

## 5. Existing Middleware

Middleware used by `novelty_checker.create_deep_agent()` in order:

1. `InMemorySkillsMiddleware`
2. `FindingsPersistenceMiddleware`
3. `PatentTrackingMiddleware`
4. `QueryLogMiddleware`
5. `FeatureConfirmationMiddleware`
6. `GuardrailsPromptMiddleware`
7. `AutonomousResearchMiddleware`
8. `ResearchContinuationMiddleware`
9. `CitationEnforcementMiddleware`
10. `SelfCitationGuardMiddleware`
11. `FullTextEvidenceMiddleware`
12. `ReportPersistenceMiddleware`
13. `GuardrailsOutputFilterMiddleware`
14. `TelemetryMiddleware`

Subagents receive:

- `ContentFilterMiddleware`
- optional per-subagent `TelemetryMiddleware`
- optional per-subagent `QueryLogMiddleware`

Reuse/adapt/ignore decisions:

| Middleware | Current purpose | TM decision |
|---|---|---|
| `InMemorySkillsMiddleware` | Progressive skills metadata and `read_skill` | Copy/adapt or extract shared. Useful and mostly domain-neutral. |
| `ContentFilterMiddleware` | Gracefully handles Azure content filter failures | Reuse or copy. Domain-neutral. |
| `TelemetryMiddleware` | Token/tool/stage telemetry, writes `/telemetry.json` and traces | Adapt/copy. Current stage names and search tool list are novelty-specific. |
| `QueryLogMiddleware` | Logs patent/NPL/semantic search args to `/queries_log.md` and `/queries_log.json` | Adapt/copy. Replace tracked tool names and fields with TM query criteria. |
| `ReportPersistenceMiddleware` | Forces `/final_report.md` after `/features.md` and findings exist | Adapt concept only. Current predicates and appendix/verdict text are patent-specific. |
| `FindingsPersistenceMiddleware` | Auto-captures patent/NPL/semantic/citation references | Ignore concrete implementation. Adapt concept into TM candidate/artifact persistence if useful. |
| `FeatureConfirmationMiddleware` | Blocks research until feature matrix is confirmed | Ignore. TM v1 should proceed once minimum criteria are present. |
| `AutonomousResearchMiddleware` | Enforces no user questions after Gate 2 | Mostly ignore. TM needs only "do not ask after criteria valid"; simpler prompt-level rule may suffice. |
| `ResearchContinuationMiddleware` | Forces multi-round patent research continuation after task results | Usually ignore for v1. Adapt only if TM subagents use multi-stage `task()` batches. |
| `CitationEnforcementMiddleware` | Forces citation analysis when A-refs and coverage gaps exist | Ignore. Patent-specific. |
| `PatentTrackingMiddleware` | Tracks patent lifecycle and writes patent statistics | Ignore. Patent-specific. |
| `SelfCitationGuardMiddleware` | Detects inventor self-citations in prior art | Ignore. Patent-specific. |
| `FullTextEvidenceMiddleware` | Forces `get_patent_details` before patent feature matrix grading | Ignore concrete implementation. A TM analogue may later force trademark detail/goods retrieval before final risk assessment. |
| `GuardrailsPromptMiddleware` | Injects novelty/patent scope boundaries and declines trademark requests | Do not reuse. It will block the TM agent. Rewrite TM guardrails. |
| `GuardrailsOutputFilterMiddleware` | Blocks patentability/claim/filing/competitive intel wording | Do not reuse as-is. Rewrite validators/replacements for trademark knockout boundaries. |

TM middleware shortlist for v1:

- `InMemorySkillsMiddleware` equivalent
- `ContentFilterMiddleware` equivalent
- `TMQueryLogMiddleware`
- `TMArtifactPersistenceMiddleware` or artifact tools
- `TMReportPersistenceMiddleware`
- `TMTelemetryMiddleware`
- optional `TMSourceFailureMiddleware`
- optional `TMGuardrailsPromptMiddleware`
- optional `TMGuardrailsOutputFilterMiddleware`

## 6. Existing Session and Artifact Behavior

### Session roots

Current novelty checker session roots:

- Static mode:
  - `sessions/<session_id>/`
- Factory mode:
  - `sessions/<thread_id>/`

`ThreadAwareBackendFactory` returns a `FilesystemBackend` rooted at the current
thread directory with `virtual_mode=True`. Agent-facing file paths such as
`/features.md` are relative to the session root.

TM should use a separate root:

```text
sessions/tm_knockout_search_agent/<session_id>/
```

This avoids mixing patent novelty artifacts with trademark clearance artifacts.

### Current files written by novelty checker

Common session files:

- `/scope.md`
- `/features.md`
- `/queries_log.md`
- `/queries_log.json`
- `/telemetry.json`
- `/findings/round_X.md`
- `/findings/patent_round_X.md`
- `/findings/npl_round_X.md`
- `/findings/semantic_round_X.md`
- `/findings/citations_round_X.md`
- `/findings/auto/*.json`
- `/findings_accumulator.json`
- `/findings_auto_accumulator.json`
- `/references.md`
- `/final_report.md`
- `/patent_statistics.json`
- `/patent_statistics.md`
- `/traces/<subagent>_messages.json`

Reusable patterns:

- Use `FilesystemBackend` virtual paths.
- Keep artifacts thread/session isolated.
- Keep a query log in both markdown and JSON.
- Keep telemetry per session.
- Persist important structured data before final report generation.
- Use backend-aware tools/middleware so static and factory modes behave the same.
- Use overwrite helpers where `FilesystemBackend.write()` cannot overwrite.
- Use line-number stripping helpers when reading JSON through
  `FilesystemBackend.read()`.

Patterns to change for TM:

- Make JSON the primary source of truth.
- Markdown should be generated from JSON artifacts, not used as the only source.
- Use the TM spec artifact set:

```text
manifest.json
request.json
search_criteria.json
search_criteria.md
query_plan.json
compumark_results.json
web_results.json
normalized_candidates.json
ranked_findings.json
risk_assessment.json
adversarial_review.json
final_report.md
telemetry.json
```

Recommended additional TM artifacts:

- `query_log.json`
- `query_log.md`
- `source_failures.json`
- `traces/<subagent>_messages.json` if subagents are used

## 7. Existing Test Patterns

Useful tests to imitate:

- `tests/test_parallel_search.py`
  - YAML subagent existence and validity.
  - Tool registry membership.
  - Skill file/frontmatter checks.
  - Lightweight structural tests without live APIs.
- `tests/test_state_reducers.py`
  - Reducer behavior.
  - Deduplication.
  - Merge semantics for parallel updates.
- `tests/test_query_log_middleware.py`
  - In-memory backend.
  - Query argument extraction helpers.
  - Markdown/JSON query log persistence.
  - Factory-mode per-thread loggers.
  - Overwrite behavior.
- `tests/test_backend_utils.py`
  - `FilesystemBackend.read()` line-number prefix handling.
  - Real backend round-trip tests.
- `tests/test_telemetry.py`
  - Telemetry initialization.
  - Tool call logging.
  - failure logging.
  - round/stage persistence.
- `tests/test_checkpointer.py`
  - Graph creation creates session directory and checkpointer.
  - For TM, keep this test lightweight or mock external source preflight.
- `tests/test_guardrails_middleware.py` and
  `tests/test_guardrails_risk_assessment.py`
  - Useful structure for prompt/output guardrails.
  - Do not copy expectations; current tests intentionally decline trademark.
- `tests/api/test_a2ui_schemas.py`, `tests/api/test_timeline_builder.py`,
  `tests/api/test_chat_stream_sse.py`
  - Useful only if TM gets API/UI integration in the same phase.

Tests not to imitate directly for TM v1:

- Patent prior-art scorer tests under `tests/test_scorers/`.
- Feature matrix / patent report coverage tests.
- Self-citation guard tests.
- Derwent auth/migration tests.

Recommended first TM tests:

- `tests/tm_knockout_search_agent/test_state.py`
- `tests/tm_knockout_search_agent/test_intake_normalization.py`
- `tests/tm_knockout_search_agent/test_tool_registry.py`
- `tests/tm_knockout_search_agent/test_compumark_tools.py` with mocked client
- `tests/tm_knockout_search_agent/test_query_log_middleware.py`
- `tests/tm_knockout_search_agent/test_artifact_persistence.py`
- `tests/tm_knockout_search_agent/test_report_validation.py`
- `tests/tm_knockout_search_agent/test_guardrails.py`

## 8. Recommended Implementation Strategy For TM Knockout Search Agent

### Strategy

1. Keep the new agent independent.
   - New package under `src/tm_knockout_search_agent/`.
   - No imports from `src.novelty_checker` except possibly neutral config
     modules such as `src.config.llm`.
   - No changes to `novelty_checker`.

2. Start with typed schemas and artifact contract.
   - Define request, criteria, source results, candidate, ranking, risk,
     review, and report schemas first.
   - Make artifact paths constants.
   - Make JSON writing deterministic and testable.

3. Build package-local tools.
   - Add a CompuMark client/tool layer.
   - Add web/common-law search tooling.
   - Add TM-specific normalization/ranking/risk helper tools.
   - Use a local `tools/registry.py`; do not use `src.tools.get_all_tools()`.

4. Create TM prompt files.
   - `AGENTS.md` should describe trademark knockout scope and disclaimers.
   - `prompts.py` should encode the v1 flow from the spec:
     - intake validation
     - criteria normalization
     - progressive search planning
     - CompuMark search
     - web/common-law search
     - candidate normalization/ranking
     - risk evaluation
     - adversarial review
     - report generation
   - No feature confirmation gates.

5. Add minimal middleware only.
   - Start with skills, content-filter, query log, telemetry, and report
     persistence.
   - Add source-failure enforcement if needed so `SEARCH_FAILED` cannot be
     hidden.
   - Avoid novelty guardrails and patent-specific middleware.

6. Keep subagents optional in v1.
   - The TM workflow may not need DeepAgents subagents at first.
   - If used, give subagents narrow read/search responsibilities and no direct
     report write tools.

7. Create `deep_agent.py` last.
   - Once tools/prompts/state are ready, wire the graph factory using the
     novelty factory pattern.
   - Use a TM session root:
     `sessions/tm_knockout_search_agent/<thread_id>/`.
   - Return `(graph, session_id)`.

8. Do not register until the graph can be instantiated and basic tests pass.
   - No `langgraph.json` change until implementation is ready.
   - No root `server.py` changes until API shape is defined.

### Reuse Summary

Reuse or copy/adapt:

- DeepAgents factory pattern.
- Thread-aware backend/session isolation pattern.
- In-memory skills progressive disclosure.
- Backend-aware tool factory pattern.
- Query log pattern.
- Telemetry pattern after replacing novelty stages/tools.
- Report persistence concept.
- Content filter fallback.
- Test structure for registry, skills, reducers, middleware, backend IO.

Do not reuse:

- `AGENTS.md` content.
- `prompts.py` content.
- `subagents.yaml` content.
- `state.py` domain types.
- `src.tools.registry.get_all_tools()`.
- patent/NPL/semantic/citation tools.
- feature coverage / Y/Y1/N / A/B/C patent analysis.
- novelty guardrails middleware.
- patent lifecycle/self-citation/full-text evidence middleware.
- current `server.py` and API stage detector without a TM rewrite.

## Proposed File Tree

Recommended initial package tree:

```text
src/tm_knockout_search_agent/
|-- __init__.py
|-- AGENTS.md
|-- deep_agent.py
|-- main.py
|-- prompts.py
|-- state.py
|-- subagents.yaml
|-- backend_factory.py
|-- artifacts.py
|-- schemas.py
|-- tools/
|   |-- __init__.py
|   |-- registry.py
|   |-- compumark.py
|   |-- web_search.py
|   |-- analysis.py
|   |-- artifacts.py
|   `-- clients/
|       |-- __init__.py
|       |-- compumark.py
|       `-- schemas.py
|-- middleware/
|   |-- __init__.py
|   |-- content_filter.py
|   |-- query_log.py
|   |-- artifact_persistence.py
|   |-- report_persistence.py
|   |-- source_failure.py
|   `-- guardrails.py
|-- observability/
|   |-- __init__.py
|   `-- telemetry.py
|-- skills/
|   |-- intake/
|   |   `-- SKILL.md
|   |-- jurisdiction-normalization/
|   |   `-- SKILL.md
|   |-- nice-class-normalization/
|   |   `-- SKILL.md
|   |-- compumark-search/
|   |   `-- SKILL.md
|   |-- web-common-law-search/
|   |   `-- SKILL.md
|   |-- candidate-ranking/
|   |   `-- SKILL.md
|   |-- risk-assessment/
|   |   `-- SKILL.md
|   |-- adversarial-review/
|   |   `-- SKILL.md
|   `-- report/
|       `-- SKILL.md
`-- api/
    |-- __init__.py
    |-- schemas.py
    |-- response_parser.py
    `-- stage_detector.py
```

Optional later registration files:

```text
src/tm_knockout_search_agent/studio.py
tests/tm_knockout_search_agent/
```

`src/tm_knockout_search_agent/studio.py` should only be added when the graph is
ready to register in `langgraph.json`.
