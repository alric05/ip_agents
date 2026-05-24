# Evaluation Trace Schema Specification

## 1. Purpose

This document defines the JSON schema for a complete evaluation trace produced by the novelty assessment evaluation framework. It serves as the contract between three components: the eval runner (produces traces), the domain scorers (consume traces), and the evaluation dashboard (visualizes traces).

Every evaluation run produces one trace file. The trace contains everything needed to: compute all Tier-1, Tier-2, and Tier-3 evaluation metrics; localize failures to specific pipeline stages; reconstruct how the agent reached its conclusions; and run the functional compliance checklist.

---

## 2. Design Principles

**Built on what already exists.** The trace schema extends EvalRunResult and telemetry.json already produced by the codebase. It enriches and unifies them into a single queryable format.

**No external dependencies.** Traces are JSON files stored alongside session artifacts. We don't have any dependency on external platforms like Langsmith

**Reusable across projects.** The schema has a generic layer (works for any LangGraph agent) and a project-specific layer (novelty checker stages, tools, checklists). A new project uses the generic layer and defines its own project layer.

**Truncation with access to full data.** Large tool outputs (search results) are truncated in the trace for efficiency. Full outputs remain available in session artifacts (findings/ directory).

---

## 3. Schema Overview

```
EvaluationTrace
  |-- run_metadata          # Who, when, what model, what config
  |-- turns[]               # Per-turn records (core data)
  |     |-- turn_metadata   # Turn number, phase, duration, timestamp
  |     |-- tool_calls[]    # Full tool call details (args + output)
  |     |-- token_usage     # Input/output/total tokens for this turn
  |     |-- gate_event      # HITL gate detected and response injected
  |-- stage_summary         # Per-stage aggregated metrics
  |-- telemetry             # Parsed telemetry.json data
  |-- checklist             # Functional compliance results
  |-- artifacts_manifest    # List of session files produced
```

---

## 4. Detailed Schema

### 4.1 Top-Level Structure

```json
{
  "schema_version": "1.0",
  "trace_type": "novelty_checker",

  "run_metadata": { },
  "turns": [ ],
  "stage_summary": { },
  "telemetry": { },
  "checklist": { },
  "artifacts_manifest": [ ]
}
```

**schema_version** (string): Schema version for forward compatibility. Consumers check this before parsing.

**trace_type** (string): Identifies the project. "novelty_checker" for this agent. Consumers use this to load the correct checklist rules and stage definitions.

---

### 4.2 Run Metadata

```json
"run_metadata": {
  "run_id": "eval_a1b2c3d4e5f6",
  "session_id": "20260306_143022_8ef2b1a3",
  "thread_id": "eval_a1b2c3d4e5f6",
  "model_name": "gpt-5",
  "model_provider": "azure_openai",
  "model_deployment": "gpt-5",
  "prompt_version": "AGENTS.md@abc1234",
  "start_time": "2026-03-06T14:30:22Z",
  "end_time": "2026-03-06T15:12:45Z",
  "total_duration_seconds": 2543.0,
  "total_turns": 18,
  "final_phase": "COMPLETED",
  "error": null,
  "fixture_id": "TST-GEAR-001",
  "run_config": {
    "max_turns": 30,
    "max_duration_seconds": 3600,
    "auto_scope_prompt": "default",
    "hitl_mode": "accept_all"
  }
}
```

**Source:** Most fields come directly from EvalRunResult. model_name and model_provider are extracted from the LLM config at run start (see implementation note below). prompt_version is the Git SHA of AGENTS.md. fixture_id comes from the input fixture metadata.

**Where to get model_name:** At the start of `run_novelty_check_e2e()`, read `AZURE_OPENAI_DEPLOYMENT_NAME` from `src/config/settings.py` (via `get_settings()`). Store it alongside the EvalRunResult so the trace writer can include it. Currently EvalRunResult does not have a model_name field, this is a small addition to the dataclass:

```python
@dataclass
class EvalRunResult:
    # ... existing fields ...
    model_name: str | None = None  # captured at run start
```

In `run_novelty_check_e2e()`, after creating the model:

```python
from src.config.settings import get_settings
settings = get_settings()
model_name = settings.azure_openai_deployment_name or "unknown"
```

---

### 4.3 Turns (Per-Turn Records)

This is the core of the trace. Each turn represents one agent.invoke() call.

```json
"turns": [
  {
    "turn_number": 1,
    "phase": "INITIAL",
    "timestamp": "2026-03-06T14:30:22Z",
    "duration_seconds": 12.3,

    "injected_message": null,
    "ai_content_preview": "I will analyze this invention disclosure...",
    "ai_content_full": "I will analyze this invention disclosure for novelty...",

    "gate_event": null,

    "tool_calls": [
      {
        "tool_call_id": "call_abc123",
        "name": "write_todos",
        "args": {
          "todos": [
            {"content": "Scope the invention", "status": "in_progress"},
            {"content": "Define features", "status": "pending"}
          ]
        },
        "output_preview": "Updated todo list to [{content: Scope the...",
        "output_size_chars": 342,
        "success": true,
        "error": null,
        "duration_ms": 45.2
      }
    ],

    "token_usage": {
      "input_tokens": 4523,
      "output_tokens": 892,
      "total_tokens": 5415
    },

    "message_count": 5
  },
  {
    "turn_number": 7,
    "phase": "AUTONOMOUS_RESEARCH",
    "timestamp": "2026-03-06T14:45:10Z",
    "duration_seconds": 89.5,

    "injected_message": "[auto-continue nudge]",
    "ai_content_preview": "I will now delegate parallel searches to...",
    "ai_content_full": "I will now delegate parallel searches to the three sub-agents...",

    "gate_event": null,

    "tool_calls": [
      {
        "tool_call_id": "call_def456",
        "name": "task",
        "args": {
          "description": "Execute patent keyword searches...",
          "subagent_type": "patent-researcher"
        },
        "output_preview": "## Patent Search Results for F1...",
        "output_size_chars": 15234,
        "success": true,
        "error": null,
        "duration_ms": 45200.0
      },
      {
        "tool_call_id": "call_ghi789",
        "name": "task",
        "args": {
          "description": "Execute NPL academic literature searches...",
          "subagent_type": "npl-researcher"
        },
        "output_preview": "## NPL Search Results...",
        "output_size_chars": 8921,
        "success": true,
        "error": null,
        "duration_ms": 32100.0
      },
      {
        "tool_call_id": "call_jkl012",
        "name": "task",
        "args": {
          "description": "Execute semantic searches...",
          "subagent_type": "semantic-researcher"
        },
        "output_preview": "## Semantic Search Results...",
        "output_size_chars": 6543,
        "success": true,
        "error": null,
        "duration_ms": 28500.0
      }
    ],

    "token_usage": {
      "input_tokens": 45230,
      "output_tokens": 3210,
      "total_tokens": 48440
    },

    "message_count": 42
  }
]
```

**Key design decisions:**

**timestamp:** Wall-clock time when the turn started, captured as `datetime.now().isoformat()` at the top of each iteration in the eval_runner loop, before `agent.invoke()` is called. The timestamp enables: correlating with telemetry.json entries, computing time-to-first-valuable-result, and post-hoc reconstruction of the run timeline.

**ai_content_full vs ai_content_preview:** The preview is the first 500 characters (same as current TurnRecord). The full content is the complete AI response for that turn. Scorers that need to analyze agent reasoning (e.g., Input Comprehension scorer) use ai_content_full. The dashboard uses ai_content_preview for the summary view.

**tool_calls.args:** The complete input arguments as passed to the tool. For patent_keyword_search, this includes the query string, field syntax, filters. For task(), this includes the description and subagent_type. This is the data needed for failure localization i.e. "what query did the agent send?"

**tool_calls.output_preview:** First 1000 characters of the tool output. Full outputs for search tools can be 10,000+ characters. The full output is available in session artifacts (findings/ directory). The preview is enough for quick inspection in the dashboard.

**tool_calls.output_size_chars:** Total character count of the full output. This lets you detect unusually large or empty responses without storing the full content.

**tool_calls.duration_ms:** Duration of the tool call in milliseconds. For task() calls (sub-agent delegations), this includes the entire sub-agent execution. Source: TelemetryMiddleware.

**token_usage:** Extracted from AIMessage.response_metadata after each invoke(). Azure OpenAI returns this as "usage": {"prompt_tokens": N, "completion_tokens": N, "total_tokens": N}. If unavailable (model does not report), set to null. Note: these token counts are for the orchestrator LLM only. Sub-agent token usage (inside task() calls) may or may not be included in the orchestrator's response_metadata. This depends on how the DeepAgents framework reports sub-agent consumption. Verify empirically on the first evaluation run and document the finding.

**Where to get tool_calls data:** After each agent.invoke(), walk the returned messages list. AIMessage objects have .tool_calls (list of dicts with "id", "name", "args"). ToolMessage objects (matched by .tool_call_id) have .content (the output). Pair them up to build the ToolCallRecord.

---

### 4.4 Gate Events

When a HITL gate is detected, the turn includes a gate_event:

```json
"gate_event": {
  "gate_name": "scope",
  "agent_proposal_preview": "## Scope Summary\n\nTitle: Dual-worm gear...",
  "response_injected": "confirm",
  "confirmation_mode": "accept_all"
}
```

For the "inject_ground_truth" mode, the response would contain the ground truth features instead of "confirm".

Gate events are only captured when the eval_runner detects a gate during automated evaluation. In normal product usage (not evaluation), gate events are not recorded in this format, the user responds directly through the UI.

---

### 4.5 Stage Summary

Computed by grouping turns by phase and aggregating. This is derived data, not directly captured, the eval runner computes it after the run completes.

```json
"stage_summary": {
  "INITIAL": {
    "turns": [1, 2, 3],
    "total_duration_seconds": 45.2,
    "total_input_tokens": 12500,
    "total_output_tokens": 3200,
    "tool_calls_by_name": {
      "write_todos": 2,
      "think_tool": 1
    }
  },
  "AWAITING_SCOPE_CONFIRM": {
    "turns": [4],
    "total_duration_seconds": 8.1,
    "total_input_tokens": 5000,
    "total_output_tokens": 1200,
    "tool_calls_by_name": {}
  },
  "AUTONOMOUS_RESEARCH": {
    "turns": [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
    "total_duration_seconds": 2100.5,
    "total_input_tokens": 325000,
    "total_output_tokens": 45000,
    "tool_calls_by_name": {
      "task": 9,
      "think_tool": 3,
      "save_round_findings": 3,
      "evaluate_coverage": 3,
      "triage_reference": 12,
      "map_features_to_reference": 8
    }
  },
  "COMPLETED": {
    "turns": [16, 17, 18],
    "total_duration_seconds": 120.3,
    "total_input_tokens": 85000,
    "total_output_tokens": 15000,
    "tool_calls_by_name": {
      "build_feature_matrix": 1,
      "write_todos": 1
    }
  }
}
```

**Why this matters for scorers:** The Prior Art Recall scorer only needs data from the AUTONOMOUS_RESEARCH stage. The Input Comprehension scorer only needs INITIAL stage data. The stage summary lets scorers quickly find the relevant turns without scanning the entire trace.

**How to compute:** Group turns by their "phase" field. Sum duration_seconds, input_tokens (from token_usage, skip if null), output_tokens. Count tool_calls by name across all turns in that phase.

---

### 4.6 Telemetry

Parsed from telemetry.json written by TelemetryMiddleware. This data is already being captured,it just needs to be parsed and included in the unified trace.

```json
"telemetry": {
  "session_id": "20260306_143022_8ef2b1a3",
  "total_rounds": 3,
  "total_tool_calls": 47,
  "failed_tool_calls": 2,
  "success_rate": 0.957,
  "avg_tool_duration_ms": 1234.5,
  "rounds": [
    {
      "round_number": 1,
      "start_time": "2026-03-06T14:40:00Z",
      "end_time": "2026-03-06T14:48:30Z",
      "duration_seconds": 510.0,
      "new_references_count": 12,
      "total_references_count": 12,
      "coverage_percentage": 35.0,
      "tool_calls_count": 15,
      "failed_tool_calls": 1
    },
    {
      "round_number": 2,
      "start_time": "2026-03-06T14:48:35Z",
      "end_time": "2026-03-06T14:55:20Z",
      "duration_seconds": 405.0,
      "new_references_count": 7,
      "total_references_count": 19,
      "coverage_percentage": 55.0,
      "tool_calls_count": 12,
      "failed_tool_calls": 0
    },
    {
      "round_number": 3,
      "start_time": "2026-03-06T14:55:25Z",
      "end_time": "2026-03-06T15:02:10Z",
      "duration_seconds": 405.0,
      "new_references_count": 3,
      "total_references_count": 22,
      "coverage_percentage": 72.0,
      "tool_calls_count": 10,
      "failed_tool_calls": 1
    }
  ]
}
```

**Source:** telemetry.json in the session directory, already written by TelemetryMiddleware. The eval runner reads this file after the run completes and parses it into this structure.

---

### 4.7 Functional Checklist

Results from the compliance checklist that validates whether the agent did everything it was supposed to.

```json
"checklist": {
  "passed": false,
  "checks": {
    "patent_search_called": true,
    "semantic_search_called": true,
    "npl_search_called": true,
    "min_search_queries": true,
    "think_tool_used": true,
    "coverage_evaluated": true,
    "findings_persisted": true,
    "scope_artifact_exists": true,
    "features_artifact_exists": true,
    "report_generated": true,
    "run_completed_without_error": false
  },
  "details": {
    "patent_search_called": "patent_keyword_search called 5 times, batch_patent_search called 2 times",
    "semantic_search_called": "semantic_patent_search called 3 times",
    "npl_search_called": "npl_search called 3 times",
    "min_search_queries": "11 total search tool calls (minimum: 3)",
    "think_tool_used": "think_tool called 3 times during AUTONOMOUS_RESEARCH",
    "coverage_evaluated": "evaluate_coverage called 3 times",
    "findings_persisted": "save_round_findings called 3 times",
    "scope_artifact_exists": "scope.md exists (1,234 bytes)",
    "features_artifact_exists": "features.md exists (2,567 bytes)",
    "report_generated": "final_report.md exists (15,432 bytes)",
    "run_completed_without_error": "FAILED: Run ended in ERROR phase - exceeded max duration"
  }
}
```

**Check definitions:**

| Check | Rule | Data Source |
|-------|------|-------------|
| patent_search_called | patent_keyword_search OR batch_patent_search called >= 1 time | turns[].tool_calls[].name |
| semantic_search_called | semantic_patent_search OR batch_semantic_search called >= 1 time | turns[].tool_calls[].name |
| npl_search_called | npl_search OR batch_npl_search called >= 1 time | turns[].tool_calls[].name |
| min_search_queries | Total search tool calls >= 3 | turns[].tool_calls[].name |
| think_tool_used | think_tool called >= 1 time during AUTONOMOUS_RESEARCH | turns[phase=AUTONOMOUS_RESEARCH].tool_calls[].name |
| coverage_evaluated | evaluate_coverage called >= 1 time | turns[].tool_calls[].name |
| findings_persisted | save_round_findings called >= 1 time | turns[].tool_calls[].name |
| scope_artifact_exists | scope.md exists and is non-empty | artifacts_manifest |
| features_artifact_exists | features.md exists and is non-empty | artifacts_manifest |
| report_generated | final_report.md exists and is non-empty | artifacts_manifest |
| run_completed_without_error | final_phase == "COMPLETED" | run_metadata.final_phase |


---

### 4.8 Artifacts Manifest

List of session files produced, with sizes. The actual file contents are in the session directory, not in the trace.

```json
"artifacts_manifest": [
  {"filename": "scope.md", "size_bytes": 1234, "exists": true},
  {"filename": "features.md", "size_bytes": 2567, "exists": true},
  {"filename": "references.md", "size_bytes": 4521, "exists": true},
  {"filename": "final_report.md", "size_bytes": 15432, "exists": true},
  {"filename": "telemetry.json", "size_bytes": 3456, "exists": true},
  {"filename": "findings_auto_accumulator.json", "size_bytes": 8901, "exists": true},
  {"filename": "findings/patent_round_1.md", "size_bytes": 5678, "exists": true},
  {"filename": "findings/npl_round_1.md", "size_bytes": 3456, "exists": true},
  {"filename": "findings/semantic_round_1.md", "size_bytes": 2345, "exists": true},
  {"filename": "findings/patent_round_2.md", "size_bytes": 4567, "exists": true},
  {"filename": "findings/npl_round_2.md", "size_bytes": 2345, "exists": true},
  {"filename": "findings/semantic_round_2.md", "size_bytes": 1890, "exists": true}
]
```

---

## 5. How Scorers Use the Trace

Each scorer reads specific parts of the trace. This mapping ensures scorers and the trace schema stay in sync.

| Scorer | Trace Fields Used                                                                                                                        |
|--------|------------------------------------------------------------------------------------------------------------------------------------------|
| Prior Art Recall  | turns[phase=AUTONOMOUS_RESEARCH].tool_calls (task() outputs contain found patents), artifacts_manifest (references.md, findings/)        |
| Feature Extraction | turns[phase=INITIAL].ai_content_full (agent's extracted features), artifacts_manifest (features.md)                                      |
| Verdict Accuracy  | artifacts_manifest (final_report.md -> extract verdict from report)                                                                      |
| Input Comprehension  | turns[phase=INITIAL].ai_content_full, turns[].gate_event (scope proposal)                                                                |
| Report Quality  | artifacts_manifest (final_report.md)                                                                                                     |
| Section Completeness | artifacts_manifest (final_report.md -> parse for 11 section headers)                                                                     |
| Faithfulness  | artifacts_manifest (final_report.md, findings/) -> compare report claims to source data                                                  |
| Search Strategy Adequacy | checklist.checks (patent_search_called, semantic_search_called, npl_search_called), stage_summary.AUTONOMOUS_RESEARCH.tool_calls_by_name |
| Triage Accuracy  | artifacts_manifest (references.md -> extract agent triage labels)                                                                        |
| Coverage Accuracy  | artifacts_manifest (final_report.md feature matrix -> extract Y/Y1/N cells)                                                              |
| Error Communication  | telemetry.failed_tool_calls (were there errors?) + artifacts_manifest (final_report.md -> scan for limitation language)                  |
| Cost  | turns[].token_usage (sum all input + output tokens), run_metadata.model_name (for pricing lookup)                                        |
| E2E Latency  | run_metadata.total_duration_seconds                                                                                                      |
| Stage Latency  | stage_summary (per-stage total_duration_seconds)                                                                                         |
| Time to First Result  | telemetry.rounds[0].end_time - run_metadata.start_time                                                                                   |
| Tool Invocations  | stage_summary.*.tool_calls_by_name (sum across stages)                                                                                   |
| Error Rate  | telemetry.failed_tool_calls / telemetry.total_tool_calls                                                                                 |
| Research Rounds  | telemetry.total_rounds                                                                                                                   |

### 5.1 Computable Signals (Not Metrics, But Useful for Debugging)

Beyond the defined metrics, the trace supports detecting these patterns:

**Retry detection:** When a tool call fails and the same tool is called again with similar args in a subsequent turn, that's a retry. Detect by scanning `turns[].tool_calls` for consecutive entries where `name` matches, the first has `success: false`, and the second has similar `args`. Useful for validating that the agent's retry logic is working.

**Query diversity:** Compare `args` across all search-type tool calls in AUTONOMOUS_RESEARCH. High similarity between queries (same keywords, same fields) indicates low search diversity. Computed from `turns[].tool_calls[].args` where name is a search tool.

**Vocabulary expansion:** Check whether terms appearing in semantic search outputs (from earlier turns) show up in keyword search args (in later turns). Indicates the agent is learning from semantic results. Computed by comparing `output_preview` of semantic tools with `args` of keyword tools across turns.

**Context window pressure:** Sum `turns[].token_usage.input_tokens` across all turns. If the cumulative input tokens approach the model's context limit (400K for GPT-5.2), the agent may be experiencing context pressure. Alert if any single turn's input_tokens exceeds 70% of the model's limit.

---


## 6. Generic vs Project-Specific

For reuse across projects, the schema separates generic and project-specific elements:

**Generic (works for any LangGraph agent):**
- run_metadata (all fields)
- turns structure (turn_number, phase, timestamp, duration, tool_calls, token_usage, message_count)
- tool_calls structure (name, args, output_preview, success, error, duration_ms)
- stage_summary structure (grouping by phase, aggregating tokens and tool calls)
- artifacts_manifest structure
- checklist structure (passed, checks dict, details dict)

**Project-specific (novelty assessment only):**
- Phase names (INITIAL, AWAITING_SCOPE_CONFIRM, AUTONOMOUS_RESEARCH, COMPLETED)
- Gate detection logic (Scope Summary, Feature Matrix markers)
- Checklist rules (patent_search_called, semantic_search_called, etc.)
- trace_type value ("novelty_checker")
- Artifact filenames (scope.md, features.md, findings/, etc.)

A new project would define its own phase names, gate markers, checklist rules, and artifact expectations while keeping the trace structure identical.

---

## 7. Tracing Tool Decision

**Decision:** We decided to use custom JSON traces (this schema) and not LangSmith cloud or Langfuse.

**Rationale:**
- LangSmith cloud sends all data (invention disclosures, patent search results, agent reasoning) to GCP us-central-1. This is a data residency concern for us.
- Self-hosted LangSmith requires Enterprise plan (significant cost).
- Self-hosted Langfuse is a viable future option if visualization is needed, but adds infrastructure overhead for Alpha release.
- The custom approach builds on existing code (EvalRunResult + TelemetryMiddleware), requires no external dependencies, keeps all data on Clarivate infrastructure, and produces traces in a format directly consumable by our scorers and dashboard.


---
