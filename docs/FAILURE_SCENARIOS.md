# Agent Failure Scenarios & Vulnerability Guide

This document describes probable failure scenarios the Novelty Checker agent may encounter in production, along with their symptoms, root causes, mitigations, and recommended actions.

---

## Table of Contents

1. [Azure OpenAI Content Policy Violation](#1-azure-openai-content-policy-violation)
2. [Network & API Failures](#2-network--api-failures)
3. [Search Query Syntax Errors](#3-search-query-syntax-errors)
4. [Missing or Invalid API Credentials](#4-missing-or-invalid-api-credentials)
5. [FilesystemBackend Limitations](#5-filesystembackend-limitations)
6. [Session & Thread Isolation Failures](#6-session--thread-isolation-failures)
7. [Subagent Communication Issues](#7-subagent-communication-issues)
8. [LLM Response Validation](#8-llm-response-validation)
9. [Recursion Limit Exceeded](#9-recursion-limit-exceeded)
10. [Evaluation Runner Failures](#10-evaluation-runner-failures)

---

## 1. Azure OpenAI Content Policy Violation

**Symptom**: Agent run crashes with `litellm.exceptions.ContentPolicyViolationError`. The error message reads: *"The response was filtered due to the prompt triggering Azure OpenAI's content management policy."*

**Root Cause**: Azure OpenAI's built-in content filter rejects the prompt sent by a subagent (e.g., patent-researcher, npl-researcher). This typically happens when the user's invention description or a search query contains terms that Azure classifies as sensitive. The subagent's model call fails, and the exception propagates through the middleware chain and crashes the entire run.

**Mitigation**: `ContentFilterMiddleware` (`src/novelty_checker/middleware/content_filter.py`) wraps every subagent's model call. When a content policy violation is detected, it returns a synthetic `AIMessage` with no tool calls, causing the subagent to terminate gracefully and return control to the orchestrator. The orchestrator can then retry with a different subagent or search strategy.

**Action Required**:
- If this occurs frequently for specific types of inventions, adjust the content filter severity in the Azure Portal for the deployment (Azure OpenAI Studio > Content Filters).
- Review the invention description for unnecessarily sensitive language.
- The orchestrator will automatically attempt alternative search strategies when a subagent returns a content filter message.

---

## 2. Network & API Failures

### 2a. API Timeouts

**Symptom**: Searches take longer than expected and eventually return empty results or error messages. Logs show `requests.exceptions.ReadTimeout` or `requests.exceptions.ConnectionError`.

**Root Cause**: External API endpoints (Innography, Web of Science, NGSP) are slow or unreachable.

**Timeout configuration**:

| API Client | Operation | Timeout |
|------------|-----------|---------|
| Innography | Token acquisition | 30s |
| Innography | Patent search | 60s |
| Innography | Document ID lookup | 30s |
| Innography | Patent content fetch | 60s |
| Innography | Citation retrieval | 60s |
| Azure OpenAI (GPT-5) | LLM call | 900s (15 min) |
| Azure OpenAI (other) | LLM call | 600s (10 min) |

**Mitigation**: All search tools use `@retry_with_backoff` decorator (`src/tools/resilience.py`) with 3 retries and exponential backoff (2s base, 30s max). On exhaustion, tools return descriptive error strings to the agent rather than raising exceptions.

**Action Required**: Check external API status. If timeouts persist, consider increasing timeout values via the respective client configuration.

### 2b. Rate Limiting (HTTP 429)

**Symptom**: Repeated retries in logs, temporary search failures.

**Root Cause**: Too many requests to WOS or NGSP APIs within a short window.

**Mitigation**: HTTP clients for WOS (`src/tools/clients/wos.py`) and NGSP (`src/tools/clients/ngsp.py`) use `urllib3.Retry` with automatic retry on HTTP 429, 500, 502, 503, 504. Configured with 0.5s backoff factor and up to 4 total retries.

**Action Required**: If rate limiting is frequent, reduce `MAX_CONCURRENT_RESEARCH_UNITS` in `src/novelty_checker/deep_agent.py` to lower parallel search pressure.

### 2c. Server Errors (5xx)

**Symptom**: Search results missing or incomplete. Logs show HTTP 500/502/503/504 errors.

**Root Cause**: Upstream API server issues.

**Mitigation**: Same retry mechanism as rate limiting (automatic retry with backoff). After retries are exhausted, the search tool returns an error string and the agent continues with available results.

**Action Required**: Monitor and report to the API provider if persistent.

---

## 3. Search Query Syntax Errors

### 3a. Innography (@-syntax Errors)

**Symptom**: Patent searches return no results or produce API errors. Logs may show "auto-fixed query" warnings.

**Root Cause**: The LLM generates queries with syntax issues:
- Spaces after commas in field lists: `@(title, abstract)` instead of `@(title,abstract)`
- Unbalanced parentheses
- Using NPL syntax (e.g., `TS=`) in patent queries

**Mitigation**: The Innography client (`src/tools/clients/innography.py`) applies auto-corrections:
1. Removes spaces after commas in `@()` field lists
2. Logs warnings for unbalanced parentheses
3. Detects NPL syntax misuse and warns
4. Multi-attempt fallback: tries original query, then simplified, then ultra-simple

**Action Required**: Review prompt instructions in `src/novelty_checker/prompts.py` if LLM consistently generates bad syntax. The subagent system prompts in `src/novelty_checker/subagents.yaml` contain query syntax guidelines.

### 3b. Web of Science Syntax Errors

**Symptom**: NPL searches fail or return no results. Logs may show query rejection from WOS API.

**Root Cause**: The LLM generates forbidden query patterns:
- Missing field tag (queries must start with `TS=`, `TI=`, or `AB=`)
- `AND` operator used inside `NEAR` clauses (crashes the WOS API)
- Wildcards with fewer than 3 characters before the wildcard symbol

**Mitigation**: Forbidden patterns are documented in tool docstrings. The LLM is instructed to avoid these patterns via subagent system prompts. Unlike Innography, these are NOT auto-corrected.

**Action Required**: If WOS queries fail repeatedly, review and strengthen the NPL researcher prompt in `src/novelty_checker/subagents.yaml`.

---

## 4. Missing or Invalid API Credentials

**Symptom**: Agent fails at startup or returns "client not configured" errors. Specific error: `ValueError: Innography API credentials not configured`.

**Root Cause**: Required environment variables are not set in `.env`:
- `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME` (LLM)
- `INNOGRAPHY_USERNAME`, `INNOGRAPHY_PASSWORD` (patent search)
- `WOS_API_KEY` (NPL search)

**Mitigation**: Each API client has an `is_configured()` check that verifies credentials before making API calls. Missing credentials produce clear error messages.

**Action Required**: Ensure all required environment variables are set in the `.env` file. See `src/config/settings.py` for the full list of configuration fields.

---

## 5. FilesystemBackend Limitations

**Symptom**: Silent data loss or unexpected behavior when middleware reads/writes session state. JSON parse errors in logs.

**Root Cause**: The `deepagents` `FilesystemBackend` has API limitations:
- **No `exists()` method**: Cannot check if a file exists — must use try/except on `read()`
- **`read()` returns error string**: For missing files, `read()` returns an error string (not an exception). Wrapping `json.loads(backend.read(...))` without try/except causes `json.JSONDecodeError`.
- **No `mkdir()` method**: `write()` creates parent directories automatically.

**Mitigation**: All middleware consistently use try/except around `backend.read()` calls and `json.loads()` parsing. Default values are returned on failure.

**Action Required**: When writing new middleware or tools that use the backend, always:
```python
try:
    content = backend.read("/some_file.json")
    data = json.loads(content)
except (Exception, json.JSONDecodeError):
    data = default_value
```

---

## 6. Session & Thread Isolation Failures

### 6a. Thread ID Extraction Failure

**Symptom**: Multiple concurrent sessions in LangGraph Studio produce interleaved or corrupted results. Findings from one session appear in another.

**Root Cause**: `ThreadAwareBackendFactory` (`src/novelty_checker/backend_factory.py`) extracts `thread_id` from `ToolRuntime.config["configurable"]["thread_id"]`. If this extraction fails, all threads fall back to a shared default session directory, causing cross-session data leakage.

**Mitigation**: The factory uses a `threading.Lock` to guard the backend cache and falls back to `default_session_id` when thread_id is unavailable.

**Action Required**: Ensure LangGraph Studio always provides a `thread_id` in the configurable. If isolation issues are observed, check backend factory logs for "using default session" warnings.

### 6b. Graph Caching in LangGraph Dev Server

**Symptom**: Code changes to the agent have no effect after restarting via `langgraph dev`.

**Root Cause**: The LangGraph dev server caches the compiled graph on first load. Subsequent code edits are not picked up until the server is fully restarted.

**Mitigation**: None (this is a LangGraph platform behavior).

**Action Required**: After making code changes, fully restart the `langgraph dev` server.

---

## 7. Subagent Communication Issues

### 7a. Orchestrator Cannot See Subagent Tool Calls

**Symptom**: Middleware that tracks tool calls (e.g., findings persistence, patent tracking) misses tool calls made by subagents.

**Root Cause**: Orchestrator-level middleware only wraps the orchestrator's own tool calls. Subagent tool calls execute in a separate graph and are invisible to the orchestrator middleware chain.

**Mitigation**: Filesystem backfill — subagents write their findings to the filesystem, and the orchestrator middleware reads those files to reconstruct what happened. See `FindingsPersistenceMiddleware` (`src/novelty_checker/middleware/findings.py`).

**Action Required**: When adding new tracking middleware, be aware that subagent activity must be tracked via filesystem artifacts, not middleware interception.

### 7b. Subagents Bypass save_round_findings

**Symptom**: Findings accumulator is incomplete or missing entries that appear in the session's findings directory.

**Root Cause**: Subagents write findings as markdown files directly via `write_file`, bypassing the `save_round_findings` tool. The backfill mechanism must parse these markdown files to reconstruct the findings.

**Mitigation**: `FindingsPersistenceMiddleware` scans the findings directory and parses markdown files during backfill.

**Action Required**: No action needed unless the markdown format changes — in that case, update the backfill parser.

### 7c. Module-Level Locks Required

**Symptom**: Race conditions when multiple subagents attempt concurrent write operations.

**Root Cause**: Shared locks defined inside closures (e.g., tool factory functions) create separate lock instances per factory call, providing no actual synchronization.

**Mitigation**: All shared locks are defined at module level to ensure a single lock instance across all tool factory invocations.

**Action Required**: When adding new shared resources, always define locks at module level.

---

## 8. LLM Response Validation

**Symptom**: Patent reference data has missing fields. Key lookups fail silently.

**Root Cause**: The LLM returns reference dictionaries with inconsistent keys. For example, a patent publication number might appear as `publication_number`, `ref_id`, or `pub_number` depending on the LLM's response.

**Mitigation**: Code that reads reference data checks multiple key variants:
```python
pub_num = ref.get("publication_number") or ref.get("ref_id") or ref.get("pub_number")
```

**Action Required**: When adding new fields that the LLM is expected to provide, always check multiple plausible key names.

---

## 9. Recursion Limit Exceeded

**Symptom**: Subagent crashes with `RecursionError` or silently stops after a fixed number of steps without completing its research.

**Root Cause**: LangGraph Studio sends `recursion_limit=100` in the run config, which propagates to subagents. Patent researchers often need 5-10 search iterations with reflection, exceeding this limit.

**Mitigation**: Monkey-patch in `src/novelty_checker/deep_agent.py` wraps every subagent graph with `.with_config({"recursion_limit": 500})`, overriding the inherited limit.

**Action Required**: If subagents still hit the limit (e.g., with very complex multi-round research), increase the value in `_create_agent_with_recursion_limit()`.

---

## 10. Evaluation Runner Failures

### 10a. Max Duration Timeout

**Symptom**: Evaluation run terminates with `phase = RunPhase.ERROR` and a timeout message.

**Root Cause**: The evaluation run exceeded `max_duration_seconds` (configurable per eval run).

**Mitigation**: `eval_runner.py` checks elapsed time against the max duration after each agent turn. When exceeded, the run is terminated gracefully with phase set to ERROR.

**Action Required**: Increase `max_duration_seconds` for complex inventions, or reduce the research scope.

### 10b. Max Turns Exceeded

**Symptom**: Evaluation run terminates with phase set to ERROR and a message about max turns.

**Root Cause**: The agent did not reach a COMPLETED state within the allowed number of turns.

**Mitigation**: `eval_runner.py` enforces a turn limit and terminates gracefully.

**Action Required**: Investigate why the agent is not converging. Common causes: the agent is stuck in a research loop, or the invention scope is too broad.

### 10c. Agent Invocation Exception

**Symptom**: Evaluation run terminates with an unhandled exception logged with full traceback.

**Root Cause**: An unexpected error during `agent.invoke()` that is not caught by any middleware.

**Mitigation**: `eval_runner.py` wraps `agent.invoke()` in try/except, logs the full traceback, sets phase to ERROR, and breaks the loop.

**Action Required**: Review the logged traceback and address the root cause. Common causes: API credential expiry, model deployment changes, or new unhandled exception types.

---

## Summary Table

| # | Scenario | Severity | Auto-Recovery | Code Location |
|---|----------|----------|---------------|---------------|
| 1 | Content policy violation | High | Yes (middleware) | `src/novelty_checker/middleware/content_filter.py` |
| 2a | API timeouts | Medium | Yes (retry) | `src/tools/resilience.py` |
| 2b | Rate limiting (429) | Low | Yes (retry) | `src/tools/clients/wos.py`, `ngsp.py` |
| 2c | Server errors (5xx) | Medium | Yes (retry) | `src/tools/clients/wos.py`, `ngsp.py` |
| 3a | Innography syntax errors | Low | Yes (auto-fix) | `src/tools/clients/innography.py` |
| 3b | WOS syntax errors | Medium | No | `src/novelty_checker/subagents.yaml` (prompt) |
| 4 | Missing API credentials | Critical | No | `src/config/settings.py` |
| 5 | FilesystemBackend quirks | Low | Yes (try/except) | All middleware files |
| 6a | Thread isolation failure | High | Partial (fallback) | `src/novelty_checker/backend_factory.py` |
| 6b | Graph caching | Low | No (restart) | LangGraph platform |
| 7a | Invisible subagent calls | Medium | Yes (backfill) | `src/novelty_checker/middleware/findings.py` |
| 7b | Findings bypass | Low | Yes (backfill) | `src/novelty_checker/middleware/findings.py` |
| 7c | Lock scope issues | High | Yes (module-level) | Various tool modules |
| 8 | Inconsistent LLM keys | Low | Yes (multi-key check) | Various middleware |
| 9 | Recursion limit | High | Yes (monkey-patch) | `src/novelty_checker/deep_agent.py` |
| 10a | Eval timeout | Medium | Yes (graceful stop) | `src/novelty_checker/eval_runner.py` |
| 10b | Max turns exceeded | Medium | Yes (graceful stop) | `src/novelty_checker/eval_runner.py` |
| 10c | Unhandled exception | High | Yes (try/except) | `src/novelty_checker/eval_runner.py` |
