# Evaluation Metrics & Strategy

**Version:** 1.0

---

## 1. Overview

This document defines all evaluation metrics for the Novelty Assessment agent, organized into three tiers: 
Tier-1 (release gating), Tier-2 (quality tracking), and Tier-3 (operational). Each metric has a definition, computation method, data source, target threshold, and internal/external classification.

The metrics are designed to be computed from the evaluation trace (defined in eval_trace_schema.md) and ground truth fixtures (defined in TEST_SET_REQUIREMENTS.md).

The threshold currently defined here are initial estimated targets and are subject to change after we run the evaluation on the initial set of fixtures and analyze the results. The thresholds will be finalized before the Alpha gate decision.

---

## 2. Tier-1: Release Gating Metrics

These metrics must pass for Alpha release. 

### 2.1. Novelty Verdict Accuracy

| Field | Value |
|-------|-------|
| Definition | Fraction of cases where agent's final verdict matches expert verdict |
| Computation | Exact match: novel/partial/not_novel. Average across all fixtures |
| Data Source | Trace: artifacts_manifest (final_report.md). Ground truth: gt_verdict.json |
| Threshold | >=70% |
| Tag | External |
| Method | Deterministic |

### 2.2. Prior Art Hit Rate 

| Field | Value |
|-------|-------|
| Definition | Fraction of cases where agent found at least 1 blocking (A-level) reference |
| Computation | For each fixture: 1 if any agent reference matches any ground truth A-ref, 0 otherwise. Average across fixtures |
| Data Source | Trace: artifacts_manifest (references.md). Ground truth: gt_references.json (triage_label="A") |
| Threshold | >=75% |
| Tag | External |
| Method | Deterministic |

### 2.3. Prior Art Recall 

| Field | Value                                                            |
|-------|------------------------------------------------------------------|
| Definition | Fraction of known blocking references found by the agent         |
| Computation | agent_A_refs x gt_A_refs / gt_A_refs, averaged across fixtures   |
| Data Source | Same as Prior Art Hit Rate                                       |
| Threshold | >=40%                                     |
| Tag | External                                                         |
| Method | Deterministic |

### 2.4. Feature Precision

| Field | Value                                                                              |
|-------|------------------------------------------------------------------------------------|
| Definition | From features the agent extracted, what fraction are correct                       |
| Computation | Hybrid matching(keyword + embeddings). matched_agent_features / all_agent_features |
| Data Source | Trace: artifacts_manifest (features.md). Ground truth: gt_features.json            |
| Threshold | >=70%                                                                              |
| Tag | Internal                                                                           |
| Method | Deterministic                                                                      |

### 2.5. Feature Recall

| Field | Value                                                                                                       |
|-------|-------------------------------------------------------------------------------------------------------------|
| Definition | From features the expert identified, what fraction did the agent find                                       |
| Computation | Same matching as above. matched_agent_features / all_expert_features. Core features (is_core=Y) weighted 2x |
| Data Source | Same as Feature Precision                                                                                   |
| Threshold | >60%                                                                                                        |
| Tag | Internal                                                                                                    |
| Method | Deterministic                                                                       |

---

## 3. Tier-2: Quality Tracking Metrics

Monitored but do not block Alpha release.

### 3.1. Report Section Completeness

| Field | Value |
|-------|-------|
| Definition | Fraction of 11 required report sections present in final report |
| Computation | Parse final_report.md for section headers. sections_found / 11 |
| Data Source | Trace: artifacts_manifest (final_report.md) |
| Target | Track, aim for 100% |
| Tag | Internal |
| Method | Deterministic  |

### 3.2. Report Quality (Readability & Actionability)

| Field | Value |
|-------|-------|
| Definition | Can a patent professional act on this report? |
| Computation | LLM-as-judge score 1-5. Criteria: readability, actionability, organization, sufficient detail |
| Data Source | Trace: artifacts_manifest (final_report.md) |
| Target | Track, aim for >=3.5/5 |
| Tag | Internal |
| Method | LLM-as-judge |

### 3.3. Faithfulness / Hallucination Rate

| Field | Value |
|-------|-------|
| Definition | Fraction of report claims that are supported by cited patent content |
| Computation | LLM-as-judge |
| Data Source | Trace: artifacts_manifest (final_report.md) |
| Target | Track, aim for >=85% |
| Tag | Internal |
| Method | LLM-as-judge  |

### 3.4. Search Strategy Adequacy

| Field | Value                                                                                                                                                                                     |
|-------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Definition | Did the agent use all required search approaches?                                                                                                                                         |
| Computation | Checklist: patent search (+1), semantic search (+1), >=3 queries (+1), think_tool used (+1), coverage evaluated (+1), findings persisted (+1), >=2 rounds (+1). Score = checks_passed / 8 |
| Data Source | Trace: eval_trace.json                                                                                                                                                                    |
| Target | Track, aim for >=7/8                                                                                                                                                                      |
| Tag | Internal                                                                                                                                                                                  |
| Method | Deterministic (checklist)                                                                                                                                                                 |

### 3.5. Triage Accuracy

| Field | Value |
|-------|-------|
| Definition | Agreement between agent and expert on A/B/C relevance labels |
| Computation | Cohen's kappa on A/B/C labels for shared references. Also compute A-ref F1 score |
| Data Source | Trace: artifacts_manifest (references.md). Ground truth: gt_references.json |
| Target | Track, aim for kappa >=0.6 |
| Tag | Internal |
| Method | Deterministic  |

### 3.6. Feature Coverage Accuracy

| Field | Value |
|-------|-------|
| Definition | Cell-level accuracy of Y/Y1/N feature-reference mapping |
| Computation | For shared A/B refs, exact match on Y/Y1/N per feature. matching_cells / total_cells |
| Data Source | Trace: artifacts_manifest (final_report.md feature matrix). Ground truth: gt_references.json (feature_coverage) |
| Target | Track, aim for >=75% |
| Tag | Internal |
| Method | Deterministic  |

### 3.7. HITL Checkpoint Quality

| Field | Value |
|-------|-------|
| Definition | Was the agent's scope understanding correct before user confirmation? |
| Computation | LLM-as-judge comparing agent scope proposal against expert expected scope. Score: correct / partially correct / incorrect |
| Data Source | Trace: turns[].gate_event (scope proposal), artifacts_manifest (scope.md) |
| Target | Track |
| Tag | Internal |
| Method | LLM-as-judge |

### 3.8. Edits Required

| Field | Value |
|-------|-------|
| Definition | Number of corrections an SME would make to agent output |
| Computation | Manual count from Mode 2 review forms: wrong triage + wrong coverage + missed refs + hallucinated facts |
| Data Source | SME Mode 2 Review Forms (not from trace) |
| Target | Track, aim for decreasing trend |
| Tag | Internal |
| Method | Manual annotation |

---

## 4. Tier-3: Operational Metrics

Cost and performance tracking.

### 4.1. Token Cost Per Run

| Field | Value                                                           |
|-------|-----------------------------------------------------------------|
| Definition | Total LLM token cost for one assessment                         |
| Computation | Sum turns[].token_usage (input + output tokens) * model pricing |
| Data Source | eval_trace.json                                                 |
| Target | Track, alert if >2x baseline                                    |
| Tag | Internal                                                        |
| Method | Deterministic                                                   |

### 4.2. End-to-End Latency

| Field | Value                                                     |
|-------|-----------------------------------------------------------|
| Definition | Wall-clock time for complete assessment                   |
| Computation | run_metadata.total_duration_seconds. Report p50, p90, p99 |
| Data Source | Trace: eval_trace.json                                    |
| Target | Track. (Time saving against manual assessment)            |
| Tag | External (reframed as "time savings")                     |
| Method | Deterministic                                             |

### 4.3. Per-Stage Latency

| Field | Value |
|-------|-------|
| Definition | Time spent in each pipeline stage |
| Computation | From stage_summary: duration per stage |
| Data Source | Trace: eval_trace.json  |
| Target | Track |
| Tag | Internal |
| Method | Deterministic |

### 4.4. Tool Invocation Counts

| Field | Value                                      |
|-------|--------------------------------------------|
| Definition | Number of tool calls per run, by tool name |
| Computation | Sum stage_summary.*.tool_calls_by_name     |
| Data Source | Trace: eval_trace.json                     |
| Target | Track, alert if >3x baseline               |
| Tag | Internal                                   |
| Method | Deterministic                              |

### 4.5. Error and Retry Rate

| Field | Value |
|-------|-------|
| Definition | Fraction of tool calls that fail |
| Computation | failed_tool_calls / total_tool_calls |
| Data Source | Trace: eval_trace.json  |
| Target | Track, aim for <=5% |
| Tag | Internal |
| Method | Deterministic |

### 4.6. Research Rounds Count

| Field | Value |
|-------|-------|
| Definition | Number of research loop iterations |
| Computation | eval_trace.json.total_rounds |
| Data Source | Trace: eval_trace.json  |
| Target | Track, expected 2-5. Alert if 1 (premature stop) or 5 (max hit) |
| Tag | Internal |
| Method | Deterministic |

---

## 5. Metric-to-Stage Mapping

|                          | Input Comprehension | HITL Confirm | Search/Research | Report Generation | End-to-End |
|--------------------------|:--:|:--:|:--:|:--:|:--:|
| 2.1 Verdict Accuracy     | | | | | X |
| 2.2 X Hit Rate           | | | X | | X |
| 2.3 X Recall Rate        | | | X | | X |
| 2.4 Feature Precision    | X | | | | |
| 2.5 Feature Recall       | X | | | | |
| 3.1 Section Completeness | | | | X | |
| 3.2 Report Quality       | | | | X | |
| 3.3 Faithfulness         | | | | X | |
| 3.4 Search Adequacy      | | | X | | |
| 3.5 Triage Accuracy      | | | X | | |
| 3.6 Coverage Accuracy    | | | X | X | |
| 3.7 HITL Quality         | X | X | | | |
| 3.8 Edits Required       | | | | | X |
| 4.1 Token Cost           | X | X | X | X | X |
| 4.2 E2E Latency          | | | | | X |
| 4.3 Stage Latency        | X | X | X | X | |
| 4.4 Tool Invocations     | | | X | X | |
| 4.5 Error Rate           | | | X | | |
| 4.6 Research Rounds      | | | X | | |

Failure localization insight: if 2.1 (verdict) is wrong but 2.2 (hit rate) is high, the problem is in report generation. If 2.2 is low but 3.4 (search adequacy) is high, the problem is in the search tools, not the agent's strategy.

---

## 6. External Benchmark Set

For now, these below metrics are chosen for external benchmarking, but we can reevaluate once we have the initial evaluation results

| Metric           | Importance                      | Our Target | 
|------------------|---------------------------------|-----------|
| Verdict Accuracy | Does it gets the right answer?  |  | 
| Prior Art Recall | Does it find what matters?      |  | 
| Time Savings     | How much time does it save?     |  |
| Faithfulness     | Can the user trust the details? |       |
  

---

## 7. Alpha Gate Criteria

### Gate Decision Matrix

| Metric                   | Threshold | Blocks Release? |
|--------------------------|-----------|:--:|
|  X Hit Rate           | >=60% | Yes |
|  Error Rate           | <=10% | Yes |
|  Search Adequacy      | >=5/8 | No |
| Verdict Accuracy     | >=60% | Yes |
|  X Hit Rate           | >=70% | Yes |
|  Section Completeness | 100% | Yes |
| Run count                | >=20 fixtures | Yes |
|  Feature Precision    | >=70% | Yes |
|  Feature Recall       | >=65% | Yes |


### Escalation Process

1. DS team identifies which metric failed and at which stage (using metric-to-stage mapping)
2. DS team opens the trace for failing fixtures and localizes the root cause
3. DS team proposes a fix (prompt change, tool improvement, model swap) with estimated impact
4. Fix is implemented and evaluation re-run
5. If metric still fails after 2 fix attempts, escalate to product lead for scope/threshold discussion

Tier-2 failures do not block release but are documented in the Alpha gate report as known limitations.

---

## 8. Summary Statistics

| Category | Count                                       |
|----------|---------------------------------------------|
| Total metrics | 19                                          |
| Tier-1 (gating) | 5                                           |
| Tier-2 (quality) | 8                                           |
| Tier-3 (operational) | 6                                           |
| External metrics | 4                                           |
| Internal metrics | 15                                          |
| Deterministic | 14                                          |
| LLM-as-judge | 3                       |
| Manual annotation | 1                                    |
