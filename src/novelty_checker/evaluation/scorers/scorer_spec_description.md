# Build Domain Scorers — Detail Specification

## Context

Agent Tracing is complete. Every evaluation run now produces an `eval_trace.json` file containing enriched turn records, telemetry from all sub-agents, a functional checklist result, and an artifacts manifest. Now Issue 7 (Replay Engine) will produce these traces for every fixture in the test set.

This issue(8) takes those traces + ground truth fixtures and computes metric scores. Each scorer is an independent Python module that can run alone or as part of a full evaluation suite.

---

### Input 1: `eval_trace.json` 

This is the agent's execution record. Key sections your scorers will read:

| Section | What's In It | Which Scorers Use It |
|---------|-------------|---------------------|
| `run_metadata` | session_id, model_name, duration, final_phase | All (for metadata tagging) |
| `turns[].tool_calls[]` | Per-tool: name, args, output_preview, success flag | Search Adequacy |
| `turns[].gate_event` | What agent proposed at Gate 1 (scope) and Gate 2 (features), what was injected | Input Comprehension, Feature Recall |
| `turns[].ai_content_full` | Full AI response text per turn | Report Quality, Faithfulness |
| `stage_summary` | Per-phase: duration, tokens, tool counts | Tier-3 cost/latency |
| `telemetry.search_queries[]` | Every search query with agent_name, tool_name, args, success | Search Adequacy, Search Reproducibility |
| `telemetry.token_usage` | Per-agent and per-stage token counts + estimated cost | Tier-3 cost metrics |
| `checklist` | 11 functional checks with pass/fail | Functional compliance (already done) |
| `artifacts_manifest` | List of all session files with sizes | Format Compliance |

### Input 2: Ground Truth Fixture (from Issue 1 / Issue 7)

These are SME responses. Per the `TEST_SET_REQUIREMENTS.md`, each fixture directory contains:

```
evals/golden_datasets/cases/{case_id}/
    disclosure.md              # What was fed to the agent
    gt_features.json           # Expected features with IDs, names, CPC codes
    gt_references.json         # Expected references with triage (A/B/C) and coverage (Y/Y1/N per feature)
    gt_verdict.json            # Expected verdict (novel / partially_novel / not_novel) + confidence + per-feature risk
    gt_search_strategy.md      # CPC codes that should be searched, vocabulary families
    agent_session/             # The eval_trace.json and session artifacts
```

### Input 3: Agent Session Artifacts (from the session directory)

These are the files the agent produced during the run:

| File | What's In It | Which Scorers Use It |
|------|-------------|---------------------|
| `features.md` | Agent's feature matrix table (ID, Name, Type, Core?, Keywords, etc.) | Feature Recall/Precision |
| `references.md` | Agent's master reference list with triage labels and coverage matrix | Prior Art Recall/Precision, Triage Agreement |
| `final_report.md` | Agent's novelty assessment report  | Report Quality, Faithfulness, Verdict Accuracy |
| `scope.md` | Agent's scope confirmation (technical field, defaults, exclusions) | Input Comprehension |
| `findings_accumulator.json` | Structured JSON of all references with per-feature coverage | Coverage matrix comparison |

---

## Subtask 1: Scorer Interface

Every scorer implements this interface:

```python
@dataclass
class ScorerResult:
    metric_name: str              # e.g., "prior_art_recall"
    score: float                  # 0.0 to 1.0
    confidence: float             # 0.0 to 1.0 (how reliable is this score)
    passed: bool                  # score >= threshold
    threshold: float              # the pass/fail threshold used
    failures: list[dict]          # list of {type, severity, evidence, affected_element}
    evidence: dict                # scorer-specific details
    scorer_type: str              # "deterministic" | "llm_judge" | "human"


def score(
    eval_trace: dict,             # parsed eval_trace.json
    ground_truth: dict,           # parsed ground truth fixture
    session_path: Path,           # path to session directory (for reading artifacts)
    config: dict | None = None,   # scorer-specific configuration
) -> ScorerResult:
    ...
```

The `failures` list uses a consistent structure:

```python
{
    "type": "missed_reference",           # failure type code
    "severity": "critical",               # critical / major / minor
    "evidence": "GT ref US9924896B2 (A-level) not found in agent references",
    "affected_element": "US9924896B2",    # the specific item
}
```

Create a base class `BaseScorer` that handles loading eval_trace, loading ground truth, loading session artifacts, and producing `ScorerResult`. Individual scorers inherit from it and implement `_compute()`.

---

## Subtask 2: Tier-1 Scorers (Deterministic, Alpha-Blocking)

These must pass for Alpha. 

### 2a. Prior Art Recall Scorer

**What it measures:** Out of the patents the SME identified as blocking (A+B refs in ground truth), how many did the agent find?

**agent data:**
- `references.md` in session artifacts 
- OR `findings_accumulator.json` 
- Both contain publication numbers and triage labels

**ground truth data:**
- `gt_references.json` with `publication_number`, `triage_label` (A/B/C), and `feature_coverage` matrix

**Key implementation detail — Family-level matching:**
Need to match to patent family instead of publication number

**Computation:**
```
recall = |agent_refs INTERSECT gt_refs| / |gt_refs|     (A+B refs only)
precision = |agent_refs INTERSECT gt_refs| / |agent_refs|  (A+B refs only)
```

**Evidence to capture:** list of found refs, list of missed refs, list of extra refs (agent found but not in GT)

**Alpha threshold:** >= 0.60 recall

### 2b. Feature Extraction Scorer

**What it measures:** Out of the features the SME identified, how many did the agent find? And did the agent add spurious features?

**agent data:**
- `features.md` (markdown table with ID, Feature Name, Type, Core?, Keywords)

**ground truth:**
- `gt_features.json` with feature IDs, names, descriptions, Core flag, and CPC codes

**Key implementation detail — Hybrid matching:**

**Computation:**
```
recall = |matched_gt_features| / |all_gt_features|
precision = |matched_gt_features| / |all_agent_features|
```
For core features (Core?=Y), compute a separate core_feature_recall that is weighted higher.

**Alpha threshold:** >= 0.75 recall

### 2c. Verdict Accuracy Scorer

**What it measures:** Did the agent reach the correct novelty conclusion?

**agent data:**
- `final_report.md` 

**ground truth:**
- `gt_verdict.json` with `verdict` field

**Computation:**
- Exact match: 1.0 if agent_verdict == gt_verdict, else 0.0
- Partial credit: novel vs partially_novel = 0.5 (one step off), novel vs not_novel = 0.0 (completely wrong)

**Evidence to capture:** agent_verdict, expected_verdict, partial_score, across all fixtures build a confusion matrix

**Alpha threshold:** >= 0.80 exact match across fixture suite

### 2d. Input Comprehension Scorer

**What it measures:** Did the agent correctly understand the invention's technical field, problem statement, and key aspects?

**agent data:**
- `scope.md` — agent's scope confirmation (written at Gate 1)
- `turns[0].gate_event.agent_proposal_preview` in eval_trace (what the agent presented at scope confirmation)

**ground truth:**
- `disclosure.md` — the original invention description
- Optionally, GT annotations of expected scope understanding

**Computation method:** LLM-as-judge. Send the agent's scope output + the original disclosure to a judge LLM with a rubric:
- Did the agent correctly identify the technical field? (correct / partially_correct / incorrect)
- Did the agent capture the key problem being solved? (correct / partially_correct / incorrect)
- Did the agent correctly identify exclusions/constraints? (correct / partially_correct / incorrect)

Score = (correct=1.0, partially=0.5, incorrect=0.0) averaged across rubric items.

**Important:** For LLM-as-judge scorers, maintain a calibration set of 10+ cases with known human ratings. The judge must achieve >= 0.80 correlation with human ratings before being used.

**Alpha threshold:** >= 0.70

---

## Subtask 3: Tier-2 Scorers (Quality, Non-Blocking for Alpha)

These measure "is the output useful?" Failing doesn't block Alpha but degrades user experience.

### 3a. Report Quality Scorer

**Method:** LLM-as-judge

**What it evaluates:**
- Section completeness: does the report have Executive Summary, Feature Matrix, Search Methodology, Per-Feature Analysis, Verdict, References, Search Log?
- Readability: is the language clear and professional?
- Actionability: can a patent professional use this report as a starting point?

**Where agent data lives:** `final_report.md`

**Rubric:** Score each dimension 0-1, average for overall quality score.

### 3b. Search Strategy Adequacy Scorer

**Method:** Deterministic checklist + telemetry analysis

**What it evaluates:**
- Did agent use Boolean search (patent_keyword_search)? Check `telemetry.search_queries`
- Did agent use semantic search (semantic_patent_search)? Check telemetry
- Did agent search expected CPC/IPC codes? Compare telemetry query args against `gt_search_strategy.md`
- Did agent discover key vocabulary (synonym expansion)? Compare agent's discovered vocabulary against GT keyword families
- Did agent use citation networks? Check telemetry for citation-researcher sub-agent calls

**Computation:** Percentage of checklist items satisfied.

**data:** All in `telemetry.search_queries` array. Each entry has `agent_name`, `tool_name`, `args` (with the actual query string), `success`, `duration_ms`.

### 3c. Faithfulness / Hallucination Scorer

**Method:** LLM-as-judge

**What it evaluates:** When the agent says "Patent X discloses feature Y," is that actually true based on the patent content?

**agent data :** `final_report.md` — extract each claim that cites a reference
**Context needed:** The actual content of the cited references (from `references.md` or `findings_accumulator.json`)

**Computation:**
- Extract claim-reference pairs from the report
- For each pair, ask the judge LLM: "Does the referenced patent content support this claim?"
- hallucination_rate = unsupported_claims / total_claims
- faithfulness_score = 1.0 - hallucination_rate

**Alpha threshold:** hallucination_rate <= 0.05

### 3d. Triage Agreement Scorer

**Method:** Deterministic

**What it measures:** For references that both the agent and SME found (the intersection), did they assign the same A/B/C triage label?

**agent data:** `references.md` or `findings_accumulator.json` — each reference has a triage label
**ground truth:** `gt_references.json` — each reference has a triage label

**Computation:** Cohen's kappa on A/B/C labels for shared references. Also compute a confusion matrix.

---

## Subtask 4: Tier-3 Scorers (Operational/Cost)

These are extracted from telemetry, no ground truth needed.

### 4a. Cost Per Run

**data:** `telemetry.token_usage.cumulative.estimated_cost_usd`

**Computation:** Direct read. Also break down by agent and by stage from `telemetry.token_usage.by_agent` and `telemetry.token_usage.by_stage`.

### 4b. Latency

**data:** `run_metadata.total_duration_seconds`

**Also compute:** per-stage latency from `stage_summary.{phase}.total_duration_seconds`

### 4c. Token Efficiency

**data:** `telemetry.token_usage.cumulative`

**Computation:** total_tokens / number_of_references_found (tokens per reference). Lower is more efficient.

### 4d. Tool Error Rate

**data :** `telemetry` — `total_tool_calls` and `failed_tool_calls`

**Computation:** failed_tool_calls / total_tool_calls

### 4e. Search Reproducibility

**What it measures:** Are all search queries fully logged with args?

**data :** `telemetry.search_queries` — check that every entry has non-null `args` with a `query` field

**Computation:** entries_with_complete_args / total_entries. Should be 1.0.

---

## Subtask 5: Scoring Profile Aggregator

Takes results from all scorers and produces:

1. **Per-fixture summary:** All metric scores for one fixture
2. **Suite summary:** Aggregated scores across all fixtures (mean, median, min, per-difficulty-band)
3. **Gate check:** Does the run pass Alpha? Check all Tier-1 thresholds:
   - Prior Art Recall >= 0.60
   - Feature Recall >= 0.75
   - Verdict Accuracy >= 0.80
   - Input Comprehension >= 0.70
   - Hallucination Rate <= 0.05
4. **Export:** Write results to `scoring_results.json` in the session directory

```python
@dataclass
class ScoringProfile:
    fixture_results: dict[str, list[ScorerResult]]   # case_id -> scorer results
    suite_summary: dict[str, float]                    # metric_name -> aggregated score
    gate_result: dict[str, bool]                       # metric_name -> passed
    alpha_passed: bool                                 # all Tier-1 gates passed
```

---

## Subtask 6: Unit Tests

For each scorer, create tests using synthetic data with known expected scores:

Use `pytest` with fixtures. Each test should be independent and fast (mock LLM calls for judge-based scorers).

---
## Acceptance Criteria

- [ ] BaseScorer interface defined with ScorerResult dataclass
- [ ] All 4 Tier-1 scorers implemented and unit tested
- [ ] At least 3 Tier-2 scorers implemented (Search Adequacy, Faithfulness, Report Quality)
- [ ] All Tier-3 scorers implemented (cost, latency, token efficiency, error rate, reproducibility)
- [ ] Scoring profile aggregator producing per-fixture and suite summaries
- [ ] Alpha gate check working (pass/fail on Tier-1 thresholds)
- [ ] Each scorer can run independently: `python -m scorers.prior_art_recall --trace path/to/eval_trace.json --gt path/to/gt_references.json`
- [ ] All scorers can run as a suite: `python run_all_scorers.py --session path/to/session --gt path/to/fixture`
- [ ] Unit tests passing with synthetic data (pytest)