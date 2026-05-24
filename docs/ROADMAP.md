# Novelty Checker — Architecture & Roadmap

> Consolidated from: `CODE_REVIEW.md`, `IMPROVEMENT_ROADMAP.md`, `CITATION_INTEGRATION_PLAN.md`, `FINDINGS_PERSISTENCE_PLAN.md`
>
> Last updated: February 12, 2026

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│              ORCHESTRATOR (Parent Agent)                 │
│  - Plans research strategy                              │
│  - Delegates to specialized subagents in parallel       │
│  - Aggregates findings                                  │
│  - Reflects on coverage using think_tool                │
│  - Decides whether to continue or stop                  │
└─────────────────────────────────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         │                │                │
┌────────▼─────┐  ┌──────▼──────┐  ┌─────▼──────────┐
│patent-       │  │npl-         │  │semantic-       │
│researcher    │  │researcher   │  │researcher      │
│(Innography)  │  │(WoS)        │  │(NGSP)          │
└──────────────┘  └─────────────┘  └────────────────┘
                          │
         ┌────────────────┼────────────────┐
         │                                 │
┌────────▼──────────┐         ┌───────────▼─────────┐
│citation-researcher│         │coverage-analyst     │
└───────────────────┘         └─────────────────────┘
                          │
                ┌─────────▼──────────┐
                │report-writer       │
                └────────────────────┘
```

| Component | File | Purpose |
|-----------|------|---------|
| Orchestrator | `src/novelty_checker/deep_agent.py` | Agent creation, session isolation, research loop |
| State Schema | `src/novelty_checker/state.py` | `DeepAgentState` with reducers for safe parallel updates |
| Prompts | `src/novelty_checker/prompts.py` | Modular orchestration instructions |
| Subagents | `src/novelty_checker/subagents.yaml` | Specialized researcher configs with tools |
| Middleware | `src/novelty_checker/middleware/` | Findings auto-capture, feature gates, citation enforcement, telemetry |
| Search Tools | `src/tools/search.py` | Patent, NPL, semantic search |
| Findings Tools | `src/tools/findings.py` | Persistence and retrieval of research findings |

---

## Architecture Strengths

**Triple-Redundancy Persistence** — Three layers ensure findings are never lost:
1. Explicit tools (`save_round_findings`)
2. Middleware auto-capture (`FindingsPersistenceMiddleware`)
3. State accumulator (`findings_accumulator` with merge reducer)

**Mandatory Reflection** — Every subagent must call `think_tool` after each search, forcing structured decision-making (ReAct pattern).

**Vocabulary Feedback Loop** — Semantic search discovers synonyms (e.g., "photoluminescence" for "UV fluorescence") that feed back into keyword searches in later rounds.

**Adaptive Citation Analysis** — Orchestrator conditionally delegates to `citation-researcher` when A-level references exist and core features still need coverage.

**Session Isolation** — `ThreadAwareBackendFactory` gives each LangGraph Studio thread its own workspace, preventing artifact leakage between conversations.

---

## Completed Work

### Findings Persistence ✅

Five-phase implementation: prompt-based guidance, TypedDict schemas (`RoundFindings`, `FindingsAccumulator`), explicit tools (`save_round_findings`, `get_all_findings`, `get_coverage_gaps`), auto-capture middleware (`FindingsPersistenceMiddleware`), and mandatory RECALL step before each research round. Findings survive context truncation in long sessions.

### Checkpointing & State Reducers ✅

Default `MemorySaver` checkpointer for crash recovery. State reducers (`merge_references`, `merge_findings_accumulator`, `merge_coverage`) enable safe parallel subagent updates with reference deduplication.

### Resilience & Retry Logic ✅

`retry_with_backoff` decorator applied to all search tools (3 retries, exponential backoff). HTTP clients have timeout management. `save_round_findings` writes directly to filesystem.

### Telemetry & Observability ✅

`ResearchTelemetry` tracks per-round metrics (duration, coverage, new refs, tool calls). `TelemetryMiddleware` auto-captures timing. Session telemetry written to `telemetry.json`.

### Parallel Search Diversification ✅

Three parallel search paths after feature confirmation: keyword-precision, semantic-recall, structural-combo. Results aggregated via `aggregate_search_results()` with deduplication and diversity scoring.

### Think Tool & Hard Limits ✅

`think_tool` forces explicit reflection after each search. Hard tool-call budgets per subagent type (5-10 searches). Stopping criteria: core features at STRONG, diminishing returns, budget exhausted.

---

## Pending — High Priority

### Citation Tool Integration

**Status:** Not started | **Effort:** ~8 hours across 8 phases

`get_patent_citations` is implemented but partially wired. `get_patent_by_number` is implemented but completely disconnected from the agent pipeline.

#### Identified Gaps

| # | Gap | Priority |
|---|-----|----------|
| G1 | No abstract in citation results — agents can't triage | High |
| G2 | No `batch_citation_search` tool — sequential only | High |
| G3 | No citation-search `SKILL.md` for progressive disclosure | Medium |
| G4 | `FindingsPersistenceMiddleware` doesn't capture citation results | Medium |
| G5 | No provenance tracking (keyword vs citation discovery) | Medium |
| G6 | No multi-hop citation chaining (only 1-level deep) | Low |
| G7 | citation-researcher lacks triage/feature-mapping tools | High |
| G8 | No automatic Phase B trigger guardrail | Medium |
| G9 | `get_patent_by_number` not in tool registry — invisible to agents | **Critical** |
| G10 | citation-researcher can't fetch full patent content for triage | **Critical** |
| G11 | report-writer can't look up missing bibliographic details | High |

#### Implementation Phases

| Phase | Goal | Fixes | Effort |
|-------|------|-------|--------|
| 0 | Wire `get_patent_by_number` into pipeline | G9, G10, G11 | Small — just wiring |
| 1 | Enrich citation data with abstracts | G1 | Small |
| 2 | Batch citation tool | G2 | Medium |
| 3 | Give citation-researcher analysis tools | G7 | Small |
| 4 | Citation search `SKILL.md` | G3 | Small |
| 5 | Findings persistence for citations | G4 | Medium |
| 6 | Provenance tracking | G5 | Medium |
| 7 | Multi-hop citation chains | G6 | Medium-Large |
| 8 | Orchestrator guardrail for Phase B | G8 | Small |

**Recommended order:** Phase 0 first (unblocks everything), then 1→3→8 (Sprint 1), 2→4 (Sprint 2), 5→6 (Sprint 3), 7 last.

#### Success Metrics

| Metric | Before | Target |
|--------|--------|--------|
| Subagents that can call `get_patent_by_number` | 0 | 3 |
| Sessions where citation analysis triggered | ~20% | >80% |
| Citation-sourced refs with proper triage | 0% | 100% |
| Time to analyze 5 A-ref citation networks | 25 sequential calls | 1 batch call |

### Citation Consolidation System

**Status:** Not started | **Effort:** 3-5 days

Implement unified citation numbering (`[1]`, `[2]`, `[3]`...) across Feature Matrix and report. Currently references use raw IDs which causes inconsistency. Changes needed in `AGENTS.md`, `skills/report/SKILL.md`, and Feature Matrix format.

---

## Pending — Medium Priority

### Structured Delegation Strategy

**Status:** Partial | Add explicit delegation examples to `AGENTS.md`: sequential stages (not parallel features), parallelization rules (1 researcher per type, not per feature), concrete `task()` patterns, iteration limits per stage.

### Concurrent Sub-Agent Limits

**Status:** Partial | Document max 3 parallel subagents in `AGENTS.md`. Define which stages run in parallel vs sequential. Prevent feature-specific parallelization anti-pattern.

---

## Future Backlog

| Improvement | Priority | Notes |
|-------------|----------|-------|
| Configurable N search paths | Low | YAML config for path count |
| Async parallel execution | Low | Current sequential is fine for MVP |
| Path-specific coverage targets | Medium | Each path contributes to coverage |
| Dynamic skill loading per path | Low | Nice-to-have |
| Google Patents integration | Low | Web content fetching pattern |
| arXiv/preprint search | Low | For bleeding-edge research areas |
| Cross-session vector DB | Low | Was scaffolded then removed — revisit if needed |
| Context management tuning | Low | Available via deepagents `ContextManagementMiddleware` |

---

## Code Review Score: 8.5/10

**Reviewed:** February 6, 2026 | **Reviewer:** Claude Sonnet 4.5

**Strong:** Hierarchical decomposition, iterative planning, triple persistence, vocabulary feedback loop.

**Addressed since review:** Checkpointing ✅, state reducers ✅, retry logic ✅, telemetry ✅.

**Remaining:** Citation integration (this roadmap), delegation strategy, cross-session learning.
