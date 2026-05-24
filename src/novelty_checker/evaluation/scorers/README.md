# Evaluation Scorers

Deterministic and (future) LLM-judge metrics that score agent runs against SME ground truth.
Built on the [DeepEval](https://github.com/confident-ai/deepeval) framework with a custom bridge layer.

---

## End-to-End Evaluation Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: Create Ground Truth (one-time, per case)                   │
│                                                                     │
│  SME fills GT Form Template (Google Sheets CSV)                     │
│      ↓ scripts/convert_sme_gt.py                                    │
│  evals/golden_datasets/cases/{CASE_ID}/                             │
│      ├─ disclosure.md          ← invention description (agent input)│
│      ├─ gt_features.json       ← expected features                  │
│      ├─ gt_references.json     ← expected refs with A/B/C triage    │
│      ├─ gt_verdict.json        ← expected verdict                   │
│      ├─ gt_search_strategy.md  ← expected CPC codes + queries       │
│      └─ metadata.json          ← SME name, time, difficulty         │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 2: Run the Agent (eval_runner.py)                             │
│                                                                     │
│  run_novelty_check_e2e(disclosure_text)                             │
│      ↓ multi-turn loop with auto gate approval:                     │
│          Turn 1 → agent scopes the invention                        │
│          Gate 1 → "confirm" injected (scope accepted)               │
│          Turn 2 → agent defines features                            │
│          Gate 2 → "confirm" injected (features accepted)            │
│          Turns 3+ → autonomous research (search, triage, report)    │
│          Completion → final report detected                         │
│      ↓                                                              │
│  sessions/{SESSION_ID}/                                             │
│      ├─ scope.md               ← agent's scope understanding       │
│      ├─ features.md            ← agent's feature matrix             │
│      ├─ references.md          ← agent's found prior art            │
│      ├─ final_report.md        ← agent's novelty verdict + report   │
│      ├─ telemetry.json         ← tool calls, tokens, timing         │
│      ├─ findings_accumulator.json  ← structured findings            │
│      └─ findings/              ← per-round search results           │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 3: Generate Eval Trace (trace_writer.py)                      │
│                                                                     │
│  write_eval_trace(eval_result, session_path)                        │
│      ↓ combines:                                                    │
│          EvalRunResult (turns, messages, gate events)                │
│        + telemetry.json (search queries, token usage)               │
│        + eval_checklist (11 functional checks)                      │
│        + artifacts manifest (file listing)                          │
│      ↓                                                              │
│  sessions/{SESSION_ID}/eval_trace.json (schema v1.1)                │
│      ├─ run_metadata    (session_id, duration, model, phase)        │
│      ├─ turns[]         (per-turn: AI text, tool calls, tokens)     │
│      ├─ stage_summary   (per-phase: duration, token totals)         │
│      ├─ telemetry       (search_queries, token_usage, tool_calls)   │
│      ├─ checklist       (11 pass/fail functional checks)            │
│      └─ artifacts_manifest  (files list with sizes)                 │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 4: Score (scorers/runner.py)                                  │
│                                                                     │
│  score_fixture(session_path, fixture_path)                          │
│      ↓ loads eval_trace.json + gt_*.json + session artifacts        │
│      ↓ runs 10 scorers (Tier-1 + Tier-2 + Tier-3)                  │
│      ↓ each returns ScorerResult                                    │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 5: Aggregate + Alpha Gate (scorers/profile.py)                │
│                                                                     │
│  ScoringProfile.from_results(all_results)                           │
│      ↓ suite_summary: mean score per metric across all fixtures     │
│      ↓ gate_result: each Tier-1 metric vs threshold                 │
│      ↓ alpha_passed: ALL three Tier-1 gates must pass               │
│      ↓                                                              │
│  scoring_results.json + summary_table()                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Quick-Start Commands

```bash
# 1. Convert SME ground truth (one-time per case)
python scripts/convert_sme_gt.py --input-dir SME_cases/ --case-id C19904 \
    --output-dir evals/golden_datasets/cases/C19904

# 2. Run agent on disclosure (produces session artifacts + eval_trace)
python -c "
from src.novelty_checker.eval_runner import run_novelty_check_e2e
from pathlib import Path
result = run_novelty_check_e2e(
    idea=Path('evals/golden_datasets/cases/C19904/disclosure.md').read_text(),
    max_turns=40,
)
print(f'Session: {result.session_path}')
"

# 3. Score against ground truth
python -m src.novelty_checker.evaluation.scorers.runner \
    --session sessions/<SESSION_ID> \
    --gt evals/golden_datasets/cases/C19904 -v
```

---

## Installation

```bash
pip install -e ".[eval]"
```

This installs `deepeval` and `sentence-transformers` (used for semantic feature matching).

---

## Directory Structure

```
scorers/
    _base.py             # ScorerResult dataclass + NoveltyBaseMetric (DeepEval bridge)
    _loader.py           # Load eval traces, ground truth, session artifacts, markdown parsers
    _matching.py         # Patent normalization + 5 feature similarity strategies
    profile.py           # ScoringProfile aggregator + Alpha gate checker
    runner.py            # CLI entry point + programmatic API
    tier1/               # Alpha-blocking scorers (5 metrics)
        verdict_accuracy.py
        prior_art_hit_rate.py
        prior_art_recall.py
        feature_extraction.py  # FeaturePrecisionMetric + FeatureRecallMetric
    tier2/               # Quality scorers (non-blocking, 4 metrics)
        report_completeness.py
        search_strategy.py
        triage_agreement.py
        feature_coverage_accuracy.py
    tier3/               # Operational metrics (from telemetry, no GT needed, 7 metrics)
        operational.py   # CostPerRun, Latency, TokenEfficiency, ToolErrorRate,
                         # SearchReproducibility, ResearchRounds, ToolInvocations
```

---

## Architecture

### Data Flow

```
eval_trace.json + gt_*.json + session artifacts
        |
        v
   +-----------+       +-----------+       +-----------+
   |  Tier-1   |       |  Tier-2   |       |  Tier-3   |
   |  Scorers  |       |  Scorers  |       |  Scorers  |
   +-----------+       +-----------+       +-----------+
        |                    |                    |
        v                    v                    v
                    ScorerResult (per metric)
                             |
                             v
                      ScoringProfile
                    (aggregate + gate check)
                             |
                             v
                    scoring_results.json
```

### Key Classes

**`ScorerResult`** (`_base.py`) - Output of every scorer:

```python
@dataclass
class ScorerResult:
    metric_name: str        # e.g., "prior_art_recall"
    score: float            # 0.0 to 1.0
    confidence: float       # how reliable the score is
    passed: bool            # score >= threshold
    threshold: float        # the pass/fail cutoff
    failures: list[dict]    # [{type, severity, evidence, affected_element}]
    evidence: dict          # scorer-specific debug info
    scorer_type: str        # "deterministic" | "llm_judge" | "human"
```

**`NoveltyBaseMetric`** (`_base.py`) - Base class for all scorers. Extends DeepEval's `BaseMetric` so scorers work in both contexts:

- **Standalone**: `scorer.score_standalone(eval_trace, ground_truth, session_path)` -> `ScorerResult`
- **DeepEval pipeline**: `scorer.measure(test_case)` -> `float` (extracts data from `test_case.additional_metadata`)

Every scorer subclass implements one method: `_compute()` -> `ScorerResult`.

**`ScoringProfile`** (`profile.py`) - Aggregates results across fixtures, computes suite-level means, and checks Alpha gate thresholds.

---

## Scorers Reference

### Tier-1: Alpha-Blocking

| Scorer | What It Measures | Threshold | Data Sources |
|--------|-----------------|-----------|--------------|
| `VerdictAccuracyMetric` | Exact match of agent verdict vs GT (novel/partial/not_novel). No partial credit. | >= 0.70 | `final_report.md`, `gt_verdict.json` |
| `PriorArtHitRateMetric` | Binary: did agent find at least 1 A-level reference? | >= 0.75 | `references.md` or `findings_accumulator.json`, `gt_references.json` |
| `PriorArtRecallMetric` | Fraction of GT A-level refs found by agent. Family-level matching. | >= 0.40 | `references.md` or `findings_accumulator.json`, `gt_references.json` |
| `FeaturePrecisionMetric` | Fraction of agent features that match GT. 5-strategy hybrid matching. | >= 0.70 | `features.md`, `gt_features.json` |
| `FeatureRecallMetric` | Fraction of GT features found by agent. Core features weighted 2x. | >= 0.60 | `features.md`, `gt_features.json` |

### Tier-2: Quality (Non-Blocking)

| Scorer | What It Measures | Target | Data Sources |
|--------|-----------------|--------|--------------|
| `ReportCompletenessMetric` | Fraction of 11 required report sections present | 100% | `final_report.md` |
| `SearchStrategyMetric` | 8-item checklist: patent search, semantic search, >=3 queries, think_tool, coverage evaluated, findings persisted, >=2 rounds, CPC coverage | >= 5/8 | `eval_trace.json`, `gt_search_strategy.md` |
| `TriageAgreementMetric` | Cohen's kappa on A/B/C triage labels + A-ref F1 score | kappa >= 0.6 | `references.md`, `gt_references.json` |
| `FeatureCoverageAccuracyMetric` | Cell-level Y/Y1/N accuracy of feature-reference coverage matrix | >= 75% | `final_report.md`, `gt_references.json` |

### Tier-3: Operational (No GT Needed)

| Scorer | What It Measures | Data Source |
|--------|-----------------|-------------|
| `CostPerRunMetric` | Estimated USD cost | `telemetry.token_usage` |
| `LatencyMetric` | Total + per-stage duration | `run_metadata`, `stage_summary` |
| `TokenEfficiencyMetric` | Tokens per reference found | `telemetry.token_usage` |
| `ToolErrorRateMetric` | Failed / total tool calls | `telemetry` |
| `SearchReproducibilityMetric` | Fraction of search queries with complete args | `telemetry.search_queries` |
| `ResearchRoundsMetric` | Number of research loop iterations (expected 2-5) | `telemetry.total_rounds` |
| `ToolInvocationMetric` | Total tool calls per run | `stage_summary.tool_calls_by_name` |

---

## GT File → Scorer Mapping

Each ground truth file feeds specific scorers. Here's what gets compared and how:

| GT File | Scorer | Agent Artifact | Comparison Method |
|---------|--------|----------------|-------------------|
| `gt_verdict.json` | `VerdictAccuracyMetric` | `final_report.md` | Regex/heuristic extracts agent verdict; exact match only (1.0 or 0.0) |
| `gt_references.json` | `PriorArtHitRateMetric` | `findings_accumulator.json` or `references.md` | Binary: did agent find >=1 A-level ref? Family-level matching. |
| `gt_references.json` | `PriorArtRecallMetric` | `findings_accumulator.json` or `references.md` | A-level refs only. `recall = \|found ∩ GT_A\| / \|GT_A\|` |
| `gt_references.json` | `TriageAgreementMetric` | `findings_accumulator.json` or `references.md` | Cohen's kappa on A/B/C labels + A-ref F1 score |
| `gt_references.json` | `FeatureCoverageAccuracyMetric` | `final_report.md` | Cell-level Y/Y1/N accuracy for shared A/B refs |
| `gt_features.json` | `FeaturePrecisionMetric` | `features.md` | 5-strategy hybrid matching. `precision = matched / agent_count` |
| `gt_features.json` | `FeatureRecallMetric` | `features.md` | 5-strategy hybrid matching. Core features 2x weighted. |
| `gt_search_strategy.md` | `SearchStrategyMetric` | `eval_trace.json` | 8-item checklist: patent, semantic, >=3 queries, think_tool, coverage, findings, >=2 rounds, CPC |
| _(none needed)_ | `ReportCompletenessMetric` | `final_report.md` | Parse for 11 required section headers |
| _(none needed)_ | Tier-3 metrics (7) | `eval_trace.json` | Cost, latency, efficiency, error rate, reproducibility, rounds, invocations |

---

## Usage

### CLI

```bash
# Score a single fixture
python -m src.novelty_checker.evaluation.scorers.runner \
    --session sessions/abc123 \
    --gt evals/golden_datasets/cases/case_001

# Score an entire suite
python -m src.novelty_checker.evaluation.scorers.runner \
    --suite evals/golden_datasets/cases/

# Tier-1 only (faster)
python -m src.novelty_checker.evaluation.scorers.runner \
    --suite evals/golden_datasets/cases/ --tier1-only

# Verbose output
python -m src.novelty_checker.evaluation.scorers.runner \
    --session sessions/abc123 --gt evals/golden_datasets/cases/case_001 -v
```

Output: prints a summary table and writes `scoring_results.json`.

### Programmatic (Standalone)

```python
from pathlib import Path
from src.novelty_checker.evaluation.scorers.runner import score_fixture, score_suite
from src.novelty_checker.evaluation.scorers.tier1.prior_art_recall import PriorArtRecallMetric

# Run all scorers on one fixture
results = score_fixture(
    session_path=Path("sessions/abc123"),
    fixture_path=Path("evals/golden_datasets/cases/case_001"),
)
for r in results:
    print(f"{r.metric_name}: {r.score:.2f} ({'PASS' if r.passed else 'FAIL'})")

# Run a single scorer
metric = PriorArtRecallMetric()
result = metric.score_standalone(eval_trace, ground_truth, session_path)
print(result.evidence)  # {recall, precision, found_refs, missed_refs, ...}

# Run a full suite with aggregation
profile = score_suite(Path("evals/golden_datasets/cases/"))
print(profile.summary_table())
print(f"Alpha gate: {'PASSED' if profile.alpha_passed else 'FAILED'}")
profile.to_json(Path("scoring_results.json"))
```

### DeepEval Integration

```python
from deepeval import evaluate
from deepeval.dataset import EvaluationDataset
from src.novelty_checker.evaluation.scorers.runner import (
    build_deepeval_dataset,
    get_all_scorers,
)

# Build test cases from a fixture suite
test_cases = build_deepeval_dataset(Path("evals/golden_datasets/cases/"))
dataset = EvaluationDataset(test_cases=test_cases)

# Run with DeepEval's evaluate()
results = evaluate(dataset, metrics=get_all_scorers())
```

---

## Feature Matching Details

`FeaturePrecisionMetric` and `FeatureRecallMetric` both use `_matching.py` to compare agent-extracted features against ground truth. Since features can appear in any order and counts may differ, the matching pipeline:

1. **Builds comparison text** from each feature dict: `feature_name + " " + description` (tries multiple key names)
2. **Computes all pairwise similarity scores** (N agent × M ground truth) using 5 strategies with configurable weights:
   - **Jaccard** (0.20): word-token set overlap (`|A∩B| / |A∪B|`) after stopword removal
   - **Bigram Dice** (0.20): character bigram overlap (`2×|intersection| / (|A|+|B|)`)
   - **LCS ratio** (0.15): longest common subsequence length / max(len_a, len_b)
   - **Levenshtein** (0.15): `1 - edit_distance / max_len`
   - **Embedding cosine** (0.30): sentence-transformer semantic similarity (`all-MiniLM-L6-v2`)
3. **Greedy 1:1 alignment**: sort pairs by score descending, greedily assign highest first, no feature matched twice
4. **Minimum threshold** (default 0.35): pairs below this are not considered matches

Then each metric uses the alignment differently:
- **Precision** = `matched_count / agent_feature_count`
- **Recall** = `(matched_non_core + 2 × matched_core) / (non_core_count + 2 × core_count)` — core features (is_core=Y) weighted 2x per strategy §2.5

If `sentence-transformers` is not installed, embedding is skipped and weights auto-rebalance to the 4 lexical strategies (0.30 / 0.30 / 0.20 / 0.20).

---

## Input Data

### eval_trace.json (from `trace_writer.py`)

Produced by the agent tracing pipeline. Key sections scorers read:
- `run_metadata` - session ID, duration, model name
- `telemetry.search_queries[]` - every search with tool name, args, success
- `telemetry.token_usage` - cumulative and per-agent token counts
- `stage_summary` - per-phase duration and tool counts
- `artifacts_manifest` - list of session files

### Ground Truth Fixtures

Generated by `scripts/convert_sme_gt.py` from SME CSV exports (7-part form: disclosure, features, references, verdict, search strategy, metadata, difficulty).

```
evals/golden_datasets/cases/{case_id}/
    disclosure.md          # invention description — input fed to the agent
    gt_features.json       # expected features (id, name, description, core, type, keywords, related_cpc)
    gt_references.json     # expected references with A/B/C triage, feature coverage matrix, pin-cites
    gt_verdict.json        # expected verdict (novel/partially_novel/not_novel) + per-feature risk
    gt_search_strategy.md  # expected databases, queries, vocabulary, CPC codes
    metadata.json          # SME name, collection date, time breakdown, difficulty band
    agent_session/         # eval_trace.json + session artifacts (after agent run)
```

**gt_features.json** structure:
```json
[
  {"id": "F1", "name": "Feature name", "description": "...", "core": "Y",
   "type": "structural", "keywords": "kw1, kw2", "related_cpc": "B63B35/44"}
]
```

**gt_references.json** structure:
```json
{
  "references": [
    {"publication_number": "US9924896B2", "type": "patent", "title": "...",
     "triage_label": "A", "blocking_potential": "high",
     "feature_coverage": {"F1": "Y", "F2": "N", "F3": "Y1"},
     "pin_cites": "col. 5, lines 10-20", "sme_notes": "..."}
  ]
}
```

**gt_verdict.json** structure:
```json
{
  "verdict": "not_novel",
  "confidence": "high",
  "where_novelty_resides": "combination of F7 + F9",
  "per_feature_risk": [
    {"feature": "F1", "risk_level": "high", "closest_reference": "US9924896B2"}
  ]
}
```

### Session Artifacts (agent output)

| File | Used By |
|------|---------|
| `features.md` | FeatureExtractionMetric |
| `references.md` | PriorArtRecallMetric, TriageAgreementMetric |
| `final_report.md` | VerdictAccuracyMetric |
| `findings_accumulator.json` | PriorArtRecallMetric (fallback), TriageAgreementMetric |

---

## Alpha Gate

The scoring profile checks gate thresholds (per `eval_metrics_strategy.md` §7) to determine if the agent passes the Alpha release gate:

| Metric | Threshold | Blocks? |
|--------|-----------|:-------:|
| Prior Art Hit Rate | >= 0.60 | Yes |
| Prior Art Recall | >= 0.40 | Yes |
| Verdict Accuracy | >= 0.60 | Yes |
| Feature Precision | >= 0.70 | Yes |
| Feature Recall | >= 0.65 | Yes |
| Tool Error Rate | >= 0.90 (≤10% errors) | Yes |
| Report Section Completeness | >= 1.00 (100%) | Yes |

All seven must pass for `alpha_passed = True`.

---

## Tests

```bash
# Run all scorer tests
pytest tests/test_scorers/ -v

# Run specific test file
pytest tests/test_scorers/test_matching.py -v
```

Test files:
- `test_matching.py` - patent normalization, all 5 similarity strategies, alignment
- `test_verdict_accuracy.py` - verdict extraction, exact match
- `test_prior_art_hit_rate.py` - binary hit detection, A-ref only
- `test_prior_art_recall.py` - A-ref recall, normalization, severity
- `test_feature_extraction.py` - precision and recall separately, core 2x weighting
- `test_report_completeness.py` - section header parsing, alias matching
- `test_search_strategy.py` - 8-item checklist evaluation
- `test_triage_agreement.py` - Cohen's kappa, A-ref F1, confusion matrix
- `test_feature_coverage_accuracy.py` - Y/Y1/N cell matching
- `test_operational.py` - all 7 Tier-3 metrics
- `test_profile.py` - aggregation, 7-gate checking, JSON export

---

## Adding a New Scorer

1. Create a file in the appropriate tier directory
2. Subclass `NoveltyBaseMetric`
3. Implement `_compute()` returning a `ScorerResult`
4. Register it in `runner.py` `get_all_scorers()`

```python
from src.novelty_checker.evaluation.scorers._base import NoveltyBaseMetric, ScorerResult

class MyNewMetric(NoveltyBaseMetric):
    def __init__(self):
        super().__init__(
            metric_name="my_new_metric",
            threshold=0.70,
            scorer_type="deterministic",
        )

    def _compute(self, eval_trace, ground_truth, session_path, config=None):
        # Your scoring logic here
        score = ...
        return ScorerResult(
            metric_name="my_new_metric",
            score=score,
            confidence=1.0,
            passed=score >= self.threshold,
            threshold=self.threshold,
            evidence={"details": "..."},
        )
```
