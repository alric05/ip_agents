# ADR-001: Agent Performance Baselines & Targets

- **Status:** Proposed
- **Date:** 2026-03-16
- **Author:** Amirhossein Yousefiramandi

## Context

As the novelty-checker agent moves toward production, we need defined performance baselines to set SLA expectations, guide optimization work, and enable alerting on regressions.

### System Architecture (relevant to latency)

| Component | Detail |
|-----------|--------|
| **Orchestrator** | LangGraph deep agent with 7-layer middleware stack |
| **Subagents** | 4 concurrent per round (patent, NPL, semantic, citation researchers) |
| **LLM** | GPT-5 via Azure OpenAI (LiteLLM), 900s timeout, 3 retries |
| **Search APIs** | Innography (patents, 60s timeout), Web of Science (NPL, 60s), NGSP/Clarivate (semantic, 30s) |
| **HTTP clients** | Synchronous (`requests` library), no async |
| **Batch tools** | Sequential execution (queries run one-by-one in a loop) |
| **Tool retries** | Exponential backoff: max 3 retries, base 2s delay, capped at 30s |
| **Research iterations** | Up to 5 rounds, each with parallel subagent execution |

---

## Methodology

The targets in this ADR are **architecture-informed projections, not empirical measurements.** They should be validated against real telemetry data from pilot runs before being committed as production SLAs.

### How targets were derived

| Input | How it was used |
|-------|----------------|
| **Hard-coded API timeouts** | Innography 60s, WOS 60s, NGSP 30s — these set the upper bound (P99/hard timeout) for single API calls |
| **Retry configuration** | `retry_with_backoff(max_retries=3, base_delay=2.0)` in `src/tools/resilience.py` — worst-case retry adds 2+4+8 = 14s of pure sleep before the final attempt |
| **Sequential batch execution** | Confirmed `for q in queries` loops in `src/tools/search.py` — N queries × per-query time = total batch time |
| **Parallel subagent execution** | LangGraph runs 4 subagents concurrently — round duration = slowest subagent, not the sum |
| **LLM inference characteristics** | GPT-class models with 15–20k input tokens typically respond in 3–8s median, with 15–30s tail latency under Azure queuing and rate-limit back-pressure |
| **Middleware stack** | 7 layers execute on every model/tool call — mostly lightweight file I/O, but contributes cumulative overhead |

### What the percentiles mean

If we run a tool 100 times and sort all durations from fastest to slowest:

| Percentile | Plain English | Example (100 runs of `patent_keyword_search`) |
|-----------|---------------|------------------------------------------------|
| **P50** | The middle value — half are faster, half are slower | 50 calls finish in ≤ 3s, 50 take longer. **This is the "normal" experience.** |
| **P80** | 80% of calls finish within this time | 80 calls finish in ≤ 7s; only 20 out of 100 are slower. **This is where most users start noticing slowness.** |
| **P95** | Only 5 out of 100 calls are slower | 95 calls finish in ≤ 10s; the remaining 5 hit retries, Azure queuing, or slow API responses. **This is the standard SLA commitment — the worst experience we tolerate for the vast majority of users.** |
| **P99** | Only 1 out of 100 calls is slower | 99 calls finish in ≤ 30s; the 1 outlier likely hit multiple retries or a near-timeout API response. **This informs hard timeout settings and alerting — "something is wrong" territory.** |

**Why P95 (not P50) is the SLA target:** P50 only represents the happy path. If we promise "responses in 3s" based on P50, users will see slower responses 50% of the time and perceive the system as unreliable. P95 captures the realistic worst-case that 19 out of 20 users will experience.

**Why we also track P80:** P80 is the practical "user patience" threshold. Research shows users start perceiving lag and losing trust around this boundary. If P80 is acceptable but P95 is not, it means a small tail of outliers is dragging down perceived reliability — often fixable with targeted retry/timeout tuning rather than architectural changes.

**Why P99 matters for operations:** P99 catches the cases where retries stack up, APIs approach their hard timeouts, or Azure OpenAI is under heavy load. These outliers, while rare, can block an entire research round (since the round waits for the slowest subagent). Setting hard timeouts based on P99 prevents one stuck call from stalling the whole agent.

### Validation plan

These projections must be validated before adoption as SLAs:

1. Run 10+ end-to-end novelty checks across varied invention complexities with telemetry enabled
2. Extract per-tool and per-model `duration_ms` from `telemetry.json` output
3. Compute actual P50/P95/P99 per category and compare against targets below
4. Adjust targets based on observed data — particularly for LLM steps (Cat A) and batch tools (Cat C), which have the highest variance

---

## Measured Baselines (from 6 complete sessions, 2026-03-16)

Data extracted from 6 complete sessions (filtered by presence of `final_report.md` and >5 tool calls) using `scripts/compute_perf_baselines.py`. To reproduce: `python scripts/compute_perf_baselines.py`. 8 incomplete/test sessions were excluded.

### Category A: LLM Decision Steps (N=220, high confidence)

| Metric | Measured | Projected |
|--------|----------|-----------|
| P50 | **4.3s** | 5s |
| P80 | **13.6s** | — |
| P95 | **28.8s** | 15s |
| P99 | **1.6min** | 30s |

**Finding:** P50 projection was accurate (4.3s vs 5s). **P95 is nearly 2x worse than projected** (28.8s vs 15s). The orchestrator is the slowest agent (P50=7.3s, P95=59.2s) due to larger context windows. Subagents are faster (P50=2.7–5.9s).

| Agent | N | P50 | P80 | P95 |
|-------|---|-----|-----|-----|
| orchestrator | 47 | 7.3s | 19.7s | 59.2s |
| patent-researcher | 23 | 3.7s | 7.3s | 17.9s |
| npl-researcher | 18 | 2.7s | 8.6s | 19.7s |
| semantic-researcher | 14 | 5.9s | 12.4s | 24.5s |

### Category B: Single API Tool Calls (N=98, high confidence)

| Metric | Measured | Projected |
|--------|----------|-----------|
| P50 | **1.7s** | 3s |
| P80 | **3.1s** | — |
| P95 | **7.7s** | 10s |
| P99 | **10.2s** | 30s |

**Finding:** API calls are **faster than projected** across all percentiles. Per-tool breakdown:

| Tool | N | P50 | P95 | Max |
|------|---|-----|-----|-----|
| patent_keyword_search | 19 | 4.7s | 10.5s | 15.2s |
| npl_search | 21 | 357ms | 678ms | 688ms |
| semantic_patent_search | 11 | 1.9s | 2.7s | 2.9s |
| get_patent_details | 47 | 1.6s | 3.2s | 4.3s |

Note: `npl_search` is significantly faster than other APIs (sub-second). `patent_keyword_search` is the slowest single API call (P95=10.5s).

### Category C: Batch Tool Calls (N=7, low confidence)

| Metric | Measured | Projected |
|--------|----------|-----------|
| P50 | **6.9s** | 15s |
| P95 | **9.5s** | 45s |

**Caveat:** Only 7 observations (all `batch_semantic_search`). No `batch_unified_search` or `batch_patent_search` data yet. These numbers likely underrepresent real-world batch latency since `batch_unified_search` (which combines all 3 APIs sequentially) was not captured.

### Category D: Citation Network — No Data

No `batch_citation_search` or `citation_chain_search` calls recorded in telemetry. Projections remain unvalidated.

### Category E/F: Round & E2E Timing

The `task` tool (subagent delegation) provides a proxy for per-round subagent duration:

| Metric | N=39 | Value |
|--------|------|-------|
| P50 | | **1.6min** |
| P80 | | **2.2min** |
| P95 | | **2.8min** |
| Max | | **3.2min** |

This is slower than the projected P50 of 60s — the `task` call includes the full subagent lifecycle (multiple LLM calls + tool calls).

### Summary: Projection Accuracy

| Category | P50 Projected | P50 Measured | P95 Projected | P95 Measured | Verdict |
|----------|--------------|-------------|--------------|-------------|---------|
| A: LLM Decision | 5s | 4.3s | 15s | 28.8s | P50 accurate, **P95 underestimated 2x** |
| B: Single API Call | 3s | 1.7s | 10s | 7.7s | **Better than projected** |
| C: Batch Tool | 15s | 6.9s | 45s | 9.5s | Better, but low N (7) |
| D: Citation | 5s | — | 15s | — | No data |
| E: Round (via `task`) | 60s | 1.6min | 3min | 2.8min | **P50 was optimistic; P95 was accurate** |

---

## Decision

### 1. Use Per-Category Targets, Not a Single Global SLA

A single latency target is meaningless for an agentic system where operations range from sub-second file reads to multi-minute research rounds. We define **6 operation categories**, each with its own target.

| Cat | Category | Examples |
|-----|----------|----------|
| A | LLM Decision Steps | Orchestrator routing, `think_tool` reflection, coverage evaluation |
| B | Single API Tool Calls | `patent_keyword_search`, `npl_search`, `semantic_patent_search` |
| C | Batch/Sequential Tool Calls | `batch_unified_search`, `batch_patent_search` (N sequential HTTP calls) |
| D | Citation Network Tools | `batch_citation_search`, `citation_chain_search` (multi-hop chains) |
| E | Per-Round Completion | One full cycle: orchestrator delegates → 4 subagents run → orchestrator reflects |
| F | End-to-End Scenario | Complete novelty check: scoping → features → N research rounds → report |

### 2. Tier 1 Targets — Current Architecture

These targets are achievable **without code changes** and should be used as the initial production baseline.

| Category | P50 | P95 | P99 | Hard Timeout | Measured? |
|----------|-----|-----|-----|--------------|-----------|
| A: LLM Decision | 5s | **30s** | 1.5min | 2min | Yes (N=239) |
| B: Single API Call | 2s | 8s | 10s | 60s | Yes (N=98) |
| C: Batch (5 queries) | 7s | 10s | — | 300s | Partial (N=7) |
| C: Batch (15 queries) | 45s | 120s | 180s | 300s | Projected only |
| D: Citation (single patent) | 5s | 15s | 60s | 120s | Projected only |
| D: Citation chain (depth=2) | 30s | 90s | 180s | 300s | Projected only |
| E: Single Research Round | 1.5min | 3 min | 3.2min | 10 min | Yes (N=48) |
| F: Full Check (3 rounds) | 8 min | 15 min | 25 min | 45 min | Projected only |
| F: Full Check (5 rounds) | 12 min | 25 min | 40 min | 60 min | Projected only |

**Rationale for key numbers:**

- **Cat A (LLM):** GPT-5 with 15–20k input tokens. Azure OpenAI P50 is typically 3–5s for routing decisions, but P95 must account for service-side queuing, cold starts, and rate-limit back-pressure. The 900s timeout is a safety net for Azure outages, not a latency expectation.
- **Cat B (Single API):** Innography/WOS/NGSP typically respond in 1–5s on happy path. P99 of 30s accounts for slow responses approaching the 60s hard timeout, plus one retry cycle.
- **Cat C (Batch):** `batch_unified_search` with 15 queries runs 15 sequential HTTP calls. At ~3s each P50 = 45s. P95 accounts for 1–2 slow queries plus a retry.
- **Cat D (Citation):** `get_patent_citations` makes 3 sequential Innography calls (ID lookup + forward + backward). `citation_chain_search(depth=2)` follows N Level-1 results, each requiring 3 more calls.
- **Cat E (Round):** Bottleneck is the slowest of the 4 parallel subagents. Each subagent does 2–3 LLM calls + 1–2 batch searches.
- **Cat F (E2E):** Sum of scoping (~30s), feature definition (~60s), N research rounds, and report generation (~2 min). Assumes user confirms feature gates within 30s.

### 3. Tier 2 Targets — Optimized Architecture

Achievable after implementing the optimization roadmap below.

| Category | P50 | P95 | P99 | Key Change |
|----------|-----|-----|-----|------------|
| A: LLM Decision | 3s | 8s | 15s | Prompt compression, streaming TTFB |
| B: Single API Call | 2s | 5s | 15s | Connection pooling, persistent sessions |
| C: Batch (5 queries) | 5s | 10s | 20s | Parallel execution via ThreadPoolExecutor |
| C: Batch (15 queries) | 8s | 15s | 30s | Parallel execution via ThreadPoolExecutor |
| D: Citation chain (depth=2) | 10s | 25s | 45s | Parallel forward+backward fetches |
| E: Single Research Round | 30s | 60s | 2 min | All subagent-level optimizations |
| F: Full Check (3 rounds) | 4 min | 8 min | 12 min | All optimizations combined |

### 4. Assessment of Initially Proposed Targets

| Proposed Target | Verdict | Explanation |
|----------------|---------|-------------|
| P95 step response < 5s (read-only) | **Too aggressive** | 5s is P50 for LLM steps. P95 should be 15s due to Azure queuing variance and middleware overhead. |
| P95 agent+tool action < 15s | **Unrealistic for batch tools** | `batch_unified_search` with 15 sequential queries takes 45s P50. Achievable only for single-query tools on happy path. With batch parallelization (Tier 2), 15s P95 becomes feasible. |
| P99 tool timeout 10–20s | **Contradicts API timeouts** | Hard-coded HTTP timeouts are 30–60s. Reducing to 10–20s would require rewriting all API clients and disabling retry logic (which exists for good reason). |
| Async fallback with polling | **Requires multi-sprint rearchitecture** | All HTTP clients use synchronous `requests`. Converting to async requires new client implementations, async tool functions, and a job queue with status polling. |

---

## Optimization Roadmap

Prioritized by impact-to-effort ratio.

### P1: Parallelize batch tool execution (1–2 days)
- **What:** Add `concurrent.futures.ThreadPoolExecutor` to `batch_unified_search`, `batch_patent_search`, `batch_npl_search`, `batch_semantic_search` in `src/tools/search.py`
- **Impact:** Batch P50 drops from 45s → 8s (bounded by the slowest single call instead of the sum)
- **Risk:** Low — each query is independent; thread safety already handled by `requests.Session`

### P2: Parallelize citation tools (1–2 days)
- **What:** Run forward + backward citation fetches concurrently in `src/tools/clients/innography.py`. Parallelize Level-1 follow-ups in `citation_chain_search`.
- **Impact:** Citation chain P50 drops from 30s → 10s

### P3: Connection pooling / client singletons (1 day)
- **What:** Module-level `InnographyClient`, `WOSClient`, `NGSPClient` singletons with persistent `requests.Session`
- **Impact:** Eliminates repeated TLS handshake overhead (~200–500ms per call)

### P4: Reduce LLM timeout + add streaming (1 day)
- **What:** Lower GPT-5 timeout from 900s → 120s with 2 retries in `src/config/llm.py`. Add streaming for faster time-to-first-byte detection.
- **Impact:** Faster failure detection on stuck LLM calls; reduces P99 tail from 30s → 15s

### P5: Async HTTP clients (3–5 days, future sprint)
- **What:** Convert all 3 API clients to `httpx.AsyncClient` or `aiohttp`
- **Impact:** Foundation for true concurrent I/O and the async fallback pattern with status polling

---

## Observability & Metrics

### Currently tracked (via TelemetryMiddleware)
- Per-tool-call timing (`duration_ms`, `success`, `agent_name`)
- Per-model-call timing + token usage (`input_tokens`, `output_tokens`, `duration_ms`)
- Per-round duration and coverage percentage
- Per-agent and per-stage cost estimates

### Recommended additions

| Metric | Where to implement | Purpose |
|--------|-------------------|---------|
| SLA breach tagging | `TelemetryMiddleware.wrap_tool_call` | Compare `duration_ms` against category P95; log WARNING on breach, ERROR on hard timeout |
| Percentile computation | `ResearchTelemetry.get_summary()` | Compute P50/P95/P99 per tool name and category at end of session |
| Per-query-in-batch timing | Batch functions in `src/tools/search.py` | Track individual query durations (currently only total batch time) |
| E2E stage decomposition | `ResearchTelemetry` | Break total duration into scoping / features / research / report (partially exists via `StageTokenSummary`) |

### Key files

| File | Role |
|------|------|
| `src/novelty_checker/observability/telemetry.py` | Core telemetry — add SLA tracking, percentiles, breach alerting |
| `src/tools/search.py` | Batch tools — add parallelization, per-query timing |
| `src/config/llm.py` | LLM timeout config |
| `src/tools/resilience.py` | Retry/backoff config (directly impacts P95/P99 tail) |
| `src/tools/clients/innography.py` | Citation parallelization, connection pooling |
| `src/tools/clients/wos.py` | WOS connection pooling |
| `src/tools/clients/ngsp.py` | NGSP connection pooling |

---

## Consequences

### Positive
- Clear, defensible targets grounded in measured architectural constraints
- Two-tier approach allows incremental improvement without blocking production launch
- Per-category breakdown prevents misleading global averages
- Optimization roadmap is prioritized with concrete effort estimates

### Negative
- Tier 1 targets are significantly more conservative than initially proposed — may require stakeholder expectation management
- Tier 2 targets require engineering investment (estimated 7–11 days total across all P1–P5 items)
- No async fallback until P5 is complete (multi-sprint dependency)

### Risks
- Azure OpenAI latency is externally controlled — P95/P99 for LLM steps may vary with service load
- External API (Innography, WOS, NGSP) performance may degrade; targets assume current baseline behavior
- Targets should be validated against actual telemetry data from pilot runs before committing as SLAs
