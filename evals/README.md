# Evaluation Results

## How to Run

### Step 1: Run the agent to produce session artifacts

```bash
python3 -c "
from src.novelty_checker.eval_runner import run_novelty_check_e2e
from src.novelty_checker.evaluation.trace_writer import write_eval_trace
from src.novelty_checker.evaluation.eval_checklist import run_functional_checklist
from pathlib import Path

idea = Path('evals/golden_datasets/cases/C19904/disclosure.md').read_text()
print('Starting eval run...')
result = run_novelty_check_e2e(idea=idea, max_turns=40)
print(f'Session: {result.session_path}')
print(f'Phase: {result.final_phase}')
print(f'Turns: {len(result.turns)}')
print(f'Error: {result.error}')

# Generate eval_trace.json
checklist = run_functional_checklist(result)
trace = write_eval_trace(result, checklist)
print(f'eval_trace.json written')
print(f'Checklist passed: {checklist.passed}')
"
```

This runs the agent end-to-end on the C19904 disclosure with automatic gate approval, then generates the eval trace. The session artifacts (scope.md, features.md, references.md, final_report.md, telemetry.json, eval_trace.json) are written to `sessions/<SESSION_ID>/`.

### Step 2: Score the session output against ground truth

```bash
python -m src.novelty_checker.evaluation.scorers.runner \
    --session sessions/<SESSION_ID> \
    --gt evals/golden_datasets/cases/C19904 -v
```

Replace `<SESSION_ID>` with the session path printed in Step 1.

To filter the output to just the scores:

```bash
python -m src.novelty_checker.evaluation.scorers.runner \
    --session sessions/<SESSION_ID> \
    --gt evals/golden_datasets/cases/C19904 -v 2>&1 | grep -E "^(INFO:|ERROR:)" | head -20
```

### Score an entire suite at once

```bash
python -m src.novelty_checker.evaluation.scorers.runner \
    --suite evals/golden_datasets/cases/ -v
```

---

## Latest Results

**Case:** C19904 (Eco-Float Voltaic Platform)
**Session:** `20260327_162206_6b166109`
**Date:** 2026-03-27
**Alpha Gate:** FAILED (3 of 7 gates failed)
**Artifacts:** [evals/runs/C19904/run_20260327/](runs/C19904/run_20260327/) | **GT:** [evals/golden_datasets/cases/C19904/](golden_datasets/cases/C19904/)

**Reproduce these scores:**
```bash
python -m src.novelty_checker.evaluation.scorers.runner \
    --session evals/runs/C19904/run_20260327 \
    --gt evals/golden_datasets/cases/C19904 -v
```

### Scoring Summary

| Metric | Score | Gate | Status |
|--------|------:|------|:------:|
| **Tier-1 (Alpha-Blocking)** | | | |
| verdict_accuracy | 0.0000 | >= 0.60 | FAIL |
| prior_art_hit_rate | 1.0000 | >= 0.60 | PASS |
| prior_art_recall | 1.0000 | >= 0.40 | PASS |
| feature_precision | 0.8333 | >= 0.70 | PASS |
| feature_recall | 0.5000 | >= 0.65 | FAIL |
| tool_error_rate | 1.0000 | >= 0.90 | PASS |
| report_section_completeness | 0.7273 | >= 1.00 | FAIL |
| **Tier-2 (Quality Tracking)** | | | |
| search_strategy_adequacy | 0.7500 | --- | --- |
| triage_agreement | 0.5000 | --- | --- |
| feature_coverage_accuracy | 0.0000 | --- | --- |
| **Tier-3 (Operational)** | | | |
| cost_per_run | 0.0000 | --- | --- |
| latency | 0.7424 | --- | --- |
| token_efficiency | 0.0000 | --- | --- |
| search_reproducibility | 0.8871 | --- | --- |
| research_rounds | 0.0000 | --- | --- |
| tool_invocations | 0.8100 | --- | --- |

### Gate Failures Analysis

| Failed Gate | Score | Threshold | Root Cause |
|-------------|------:|-----------|------------|
| verdict_accuracy | 0.00 | >= 0.60 | Agent concluded "moderate novelty" instead of GT "not_novel". Likely due to missing key blocking references. |
| feature_recall | 0.50 | >= 0.65 | Agent matched 50% of GT features. Core features weighted 2x — missing core features hurt recall more. |
| report_section_completeness | 0.73 | >= 1.00 | 8 of 11 required sections present. Missing: scope, feature matrix, search strategy. |

---

## Previous Runs

### Run 2026-03-26 (Session: `20260326_221532_cb95fa53`) | [Artifacts](runs/C19904/run_20260326/)

**Reproduce these scores:**
```bash
python -m src.novelty_checker.evaluation.scorers.runner \
    --session evals/runs/C19904/run_20260326 \
    --gt evals/golden_datasets/cases/C19904 -v
```

| Metric | Score | Status |
|--------|------:|:------:|
| verdict_accuracy | 1.0000 | PASS |
| prior_art_hit_rate | 1.0000 | PASS |
| prior_art_recall | 1.0000 | PASS |
| feature_precision | 0.5000 | FAIL |
| feature_recall | 0.3125 | FAIL |
| tool_error_rate | 1.0000 | PASS |
| report_section_completeness | 0.5455 | FAIL |
| search_strategy_adequacy | 0.3750 | --- |
| triage_agreement | 0.5000 | --- |
| latency | 0.7986 | --- |
| search_reproducibility | 0.9000 | --- |
| tool_invocations | 0.5050 | --- |

**Notes:** Verdict and prior art scores were perfect. Feature extraction and report completeness need improvement.

---

## Session Artifacts

Full session artifacts for each run are committed under `evals/runs/`. These are the agent outputs that produced the scores above. You can inspect any artifact to understand why a metric scored the way it did.

```
evals/runs/C19904/
    run_20260326/           # Session 20260326_221532_cb95fa53
    run_20260327/           # Session 20260327_162206_6b166109
        (both have the same structure below)
```

### What each artifact is and which scorer uses it

| Artifact | What it contains | Scored by |
|----------|-----------------|-----------|
| `scope.md` | Agent's scoped invention description | (not scored directly) |
| `features.md` | Agent's extracted feature matrix | `feature_precision`, `feature_recall` |
| `references.md` | Agent's found prior art with triage labels | `prior_art_hit_rate`, `prior_art_recall`, `triage_agreement` |
| `final_report.md` | Agent's novelty verdict + full analysis | `verdict_accuracy`, `report_section_completeness`, `feature_coverage_accuracy` |
| `findings/` | Per-round search results written by subagents | Used to backfill `findings_auto_accumulator.json` |
| `findings_auto_accumulator.json` | All discovered references (structured JSON) | Fallback source for `prior_art_recall`, `prior_art_hit_rate` |
| `telemetry.json` | Every tool call with timing and success/fail | `search_strategy_adequacy`, `cost_per_run`, `tool_error_rate`, `search_reproducibility`, `research_rounds`, `tool_invocations` |
| `eval_trace.json` | Unified trace combining turns + telemetry + checklist | Entry point for all scorers |
| `scoring_results.json` | Full scorer output with scores, evidence, failures | Final results (same data as the tables above) |

### How scores connect to artifacts

To understand why a score is low, open the corresponding artifact:

- **verdict_accuracy = 0.0?** Read `final_report.md` and compare the agent's conclusion against `gt_verdict.json`
- **prior_art_recall = 0.0?** Compare patent numbers in `references.md` against `gt_references.json` (A-level refs)
- **feature_recall = 0.5?** Compare `features.md` rows against `gt_features.json` entries
- **report_section_completeness = 0.73?** Check which `## Section` headers exist in `final_report.md` (needs 11)
- **search_strategy_adequacy = 0.375?** Check `telemetry.json` for which tool types were called

### Ground truth (what the agent is scored against)

Located in `evals/golden_datasets/cases/C19904/`:

| GT File | What it contains | Used by scorers |
|---------|-----------------|-----------------|
| `disclosure.md` | Invention description (input to the agent) | (not scored, this is the input) |
| `gt_features.json` | SME-defined features with core flag | `feature_precision`, `feature_recall` |
| `gt_references.json` | SME-identified blocking refs with A/B/C triage | `prior_art_hit_rate`, `prior_art_recall`, `triage_agreement`, `feature_coverage_accuracy` |
| `gt_verdict.json` | SME verdict (novel/partially_novel/not_novel) | `verdict_accuracy` |
| `gt_search_strategy.md` | Expected CPC codes and search approach | `search_strategy_adequacy` |
| `metadata.json` | SME name, time spent, difficulty | (context only) |

## Metric Definitions

See [scorers/README.md](../src/novelty_checker/evaluation/scorers/README.md) for full metric definitions, thresholds, and architecture.

## Ground Truth Fixtures

See [golden_datasets/cases/](golden_datasets/cases/) for GT files per case. Generated from SME CSV exports via `scripts/convert_sme_gt.py`.
