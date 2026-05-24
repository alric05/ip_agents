# Running the Single-LLM Baseline

The baseline agent is a plain ReAct LLM with direct access to the same tool registry as the deep agent — no middleware, no subagents, no gates. It exists to measure how much of the deep agent's end-to-end quality comes from orchestration vs. what a single LLM with tools could do on its own.

Both agents are scored by the same evaluation harness so score deltas on the golden fixtures map directly to agentic-design lift.

---

## 1. Prerequisites

### Environment variables (`.env` at repo root)

| Variable | Purpose |
|---|---|
| `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` | LLM backend |
| `DERWENT_API_BASE_URL`, `DERWENT_JWT_TOKEN` | Patent search (Derwent) |
| `CLARIVATE_NGSP_API_KEY` | Semantic search (NGSP) |
| `WOS_API_KEY` | NPL search (Web of Science) — optional |

The Derwent JWT expires periodically. If you see `HTTP 419` or `500` errors in the logs, refresh `DERWENT_JWT_TOKEN` and re-run.

### Python env

```bash
source .venv/bin/activate   # project virtualenv (Python 3.12)
```

---

## 2. Single-case run (fastest loop)

Run the baseline on one golden fixture and get a scorer report back:

```bash
python run_baseline_pipeline.py --case C19904 --max-turns 30
```

- `--case` — any subdirectory of `evals/golden_datasets/cases/`. Must contain `disclosure.md`, `gt_features.json`, `gt_references.json`, `gt_verdict.json`.
- `--max-turns` — safety cap on invoke iterations. Baseline typically finishes in 1-3 turns.
- `--max-duration-seconds` — wall-clock cap (default 3600).

The script does four steps in order:

1. Loads the disclosure from `evals/golden_datasets/cases/<case>/disclosure.md`.
2. Runs the baseline via `run_baseline_e2e` — creates a fresh session directory under `sessions/<id>/` and writes `scope.md`, `features.md`, `references.md`, `findings/round_X.md`, and `final_report.md` via the `write_file` tool.
3. Runs the functional checklist and writes `eval_trace.json` into the session directory.
4. Scores the session against the ground truth via `score_fixture`, prints a metrics table.

Artifacts land at `sessions/<session_id>/`.

### Deep-agent equivalent

```bash
python run_deepagent_pipeline.py --case C19904 --max-turns 40
```

Same output shape — use this for head-to-head comparison. Deep agent takes longer (5-15 minutes) because of the multi-subagent research loop.

---

## 3. Batch run across all golden fixtures

```bash
python -m src.novelty_checker.evaluation.batch_runner \
    --config src/novelty_checker/evaluation/configs/alpha_eval.yaml \
    --runner baseline
```

- `--runner baseline` — run the single-LLM baseline. Omit or set `deepagent` to run the full multi-agent pipeline.
- `--fixture <CASE_ID>` — run only one fixture.
- `--resume` — skip fixtures whose `eval_trace.json` already exists in the output directory.
- `--dry-run` — list fixtures without running.

Results land at `<output_directory>/<case>/` per the config. A `batch_summary.json` rolls up all fixtures.

### Scoring an entire suite

```bash
python -m src.novelty_checker.evaluation.scorers.runner \
    --suite evals/golden_datasets/cases/ -v
```

Writes `scoring_results.json` into the suite directory with aggregated tier-1/2/3 metrics.

### Scoring one session manually

```bash
python -m src.novelty_checker.evaluation.scorers.runner \
    --session sessions/<session_id> \
    --gt evals/golden_datasets/cases/<case_id> -v
```

Useful when you want to re-score a session after updating a scorer.

---

## 4. What you'll see in the metrics table

16 scorers across three tiers (from `get_all_scorers()`):

| Tier | Metric | What it measures |
|---|---|---|
| 1 | verdict_accuracy | Did the agent reach the right novel/partially_novel/not_novel verdict? |
| 1 | prior_art_hit_rate | Fraction of agent refs that overlap ground-truth refs |
| 1 | prior_art_recall | Fraction of ground-truth refs the agent found |
| 1 | feature_precision / feature_recall | Feature-extraction quality |
| 2 | report_section_completeness | Does `final_report.md` have all required sections? |
| 2 | search_strategy_adequacy | Did the agent issue enough diverse search queries? |
| 2 | triage_agreement | A/B/C label agreement with ground truth |
| 2 | feature_coverage_accuracy | Per-feature coverage-level agreement with GT |
| 3 | cost/latency/tokens/tool_errors | Operational cost metrics |
| 3 | search_reproducibility | Are the search queries logged reproducibly? |
| 3 | research_rounds | Did the agent run enough research iterations? |
| 3 | tool_invocations | Enough tool diversity? |

---

## 5. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `HTTP 419` / `500` on Derwent searches | JWT expired or Clarivate dev-snapshot outage | Refresh `DERWENT_JWT_TOKEN`; retry |
| `final_report.md` missing after deep-agent run | Orchestrator forgot `write_file` | Covered by `ReportPersistenceMiddleware` + `_autosave_final_report` safety net in `eval_runner` — should self-recover |
| `verdict_accuracy = 0` with `expected_verdict=''` | GT fixture schema mismatch | The scorer handles both `{"overall": {"verdict": ...}}` and `{"verdict": ...}` since [r1]; if you see this, check your fixture json |
| `report_section_completeness` stuck at 0.7-0.9 | Agent uses non-canonical section headings | Either add the heading as an alias in `report_completeness.py:_SECTION_ALIASES` or tighten the agent prompt |
| Baseline takes 4+ minutes | LLM is iterating inside a single ReAct turn with many tool calls | Normal; raise `--max-duration-seconds` if it hits the cap |

---

## 6. Comparing baseline vs deep agent

Typical workflow for measuring lift:

```bash
# 1. Refresh Derwent JWT in .env
# 2. Run both agents back-to-back on the same fixture
python run_baseline_pipeline.py   --case C19904 --max-turns 30 | tee logs/baseline_C19904.log
python run_deepagent_pipeline.py --case C19904 --max-turns 40 | tee logs/deepagent_C19904.log

# 3. Diff the metrics tables at the bottom of each log
```

Expect the deep agent to win on `search_strategy_adequacy`, `research_rounds`, `feature_coverage_accuracy`, and `search_reproducibility`. Expect the baseline to win on `cost_per_run`, `latency`, and `token_efficiency`. The "orchestration lift" is the gap on Tier-1 + Tier-2 metrics at roughly equal prior-art discovery.

---

## 7. File map

| Path | Role |
|---|---|
| [run_baseline_pipeline.py](../run_baseline_pipeline.py) | Single-case runner for baseline |
| [run_deepagent_pipeline.py](../run_deepagent_pipeline.py) | Single-case runner for deep agent |
| [src/novelty_checker/baseline_agent.py](../src/novelty_checker/baseline_agent.py) | `create_baseline_agent()` |
| [src/novelty_checker/baseline_prompt.py](../src/novelty_checker/baseline_prompt.py) | Consolidated system prompt for baseline |
| [src/novelty_checker/baseline_runner.py](../src/novelty_checker/baseline_runner.py) | `run_baseline_e2e()` |
| [src/novelty_checker/evaluation/batch_runner.py](../src/novelty_checker/evaluation/batch_runner.py) | Multi-fixture batch runner (`--runner {baseline,deepagent}`) |
| [src/novelty_checker/evaluation/scorers/runner.py](../src/novelty_checker/evaluation/scorers/runner.py) | Scorer CLI (`--session` / `--suite`) |
| [evals/golden_datasets/cases/](../evals/golden_datasets/cases/) | Ground-truth fixtures |
| [sessions/](../sessions/) | Per-run output directories (gitignored) |
