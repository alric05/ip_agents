# Evaluation Pipeline - How to Run

## Prerequisites

- Python 3.11+ with venv activated
- Azure OpenAI credentials in `.env`
- All commands run from the **repo root** (`dw-rnd-unified-agent/`)

## Step 1: Convert SME Excel Files to Fixtures

Place SME Ground Truth Excel files in `src/novelty_checker/evaluation/fixtures/inputs/`.

```bash
python -m src.novelty_checker.evaluation.fixtures.conversion \
    --folder src/novelty_checker/evaluation/fixtures/inputs/ \
    --output-dir src/novelty_checker/evaluation/fixtures/
```

After conversion, make sure the output files are named properly (this should be a conversion.py fix in fixture folder)
rename output files to match expected format:

```bash
for dir in src/novelty_checker/evaluation/fixtures/*/; do
    [ -f "$dir/metadata.yaml" ] && mv "$dir/metadata.yaml" "$dir/fixture_meta.yaml"
    [ -f "$dir/invention_disclosure.md" ] && mv "$dir/invention_disclosure.md" "$dir/disclosure.md"
done
```

Normalize verdict values (again should be fixed by the fixture conversion script):

```bash
python -c "
import json
from pathlib import Path
for d in sorted(Path('src/novelty_checker/evaluation/fixtures').iterdir()):
    vf = d / 'gt_verdict.json'
    if not vf.exists(): continue
    data = json.load(open(vf))
    v = data.get('overall',{}).get('verdict','')
    n = v.lower().strip().replace(' ','_')
    if v != n:
        data['overall']['verdict'] = n
        json.dump(data, open(vf,'w'), indent=2)
        print(f'{d.name}: {v!r} -> {n!r}')
"
```

## Step 2: Verify Fixtures Load Correctly

```bash
python -c "
from src.novelty_checker.evaluation.fixture_loader import discover_fixtures
cases = discover_fixtures('src/novelty_checker/evaluation/fixtures/')
print(f'Loaded {len(cases)} fixtures')
for c in cases:
    print(f'  {c.case_id} ({c.meta.difficulty}) disclosure={len(c.disclosure_text)} chars')
"
```

All fixtures should load. Validation warnings are informational and do not block the run.

## Step 3: Configure the Run

Edit `src/novelty_checker/evaluation/configs/alpha_eval.yaml`:

```yaml
config_name: alpha_gate_eval_v1
config_version: "1.0"
model: azure/dpa-ai-agentic-poc
max_turns: 30
max_duration_seconds: 3600
hitl_mode: accept_all
fixture_directory: src/novelty_checker/evaluation/fixtures
output_directory: src/novelty_checker/evaluation/results
```

## Step 4: Dry Run

Verify all fixtures are discovered without running the agent:

```bash
python -m src.novelty_checker.evaluation.batch_runner \
    --config src/novelty_checker/evaluation/configs/alpha_eval.yaml \
    --dry-run
```

## Step 5: Run a Single Fixture (Smoke Test)

Pick a small fixture to verify everything works:

```bash
python -m src.novelty_checker.evaluation.batch_runner \
    --config src/novelty_checker/evaluation/configs/alpha_eval.yaml \
    --fixture C35782
```

This takes 10-20 minutes and costs ~$8. Check the output:

```bash
# Find the session directory
cat src/novelty_checker/evaluation/results/batch_summary.json | python -m json.tool | grep session_id
```

## Step 6: Run Full Batch

```bash
python -m src.novelty_checker.evaluation.batch_runner \
    --config src/novelty_checker/evaluation/configs/alpha_eval.yaml
```

This runs all fixtures sequentially. Expect 10-20 minutes per fixture. If it crashes partway, restart with `--resume` to skip completed fixtures.

Results are written to `src/novelty_checker/evaluation/results/batch_summary.json`.

## Step 7: Run Scorers

After the batch completes, run all scorers across all sessions:

```bash
python -m src.novelty_checker.evaluation.run_all_scorers
```

This reads `batch_summary.json`, finds each fixture's session, runs all 16 metrics, and produces an aggregated scoring profile.

Results are written to `src/novelty_checker/evaluation/results/scoring_results.json`.

To score a single fixture manually:

```bash
python -m src.novelty_checker.evaluation.scorers.runner \
    --session sessions/<SESSION_ID> \
    --gt src/novelty_checker/evaluation/fixtures/<CASE_ID> \
    -v
```

## Step 8: Generate Report

```bash
python -m src.novelty_checker.evaluation.generate_alpha_report
```

Report is written to `src/novelty_checker/evaluation/results/alpha_gate_report.md`.

## Output Files

| File | Description |
|------|-------------|
| `results/batch_summary.json` | Per-fixture run status, duration, cost, session IDs |
| `results/scoring_results.json` | All metric scores, gate pass/fail, per-fixture breakdown |
| `results/alpha_gate_report.md` | Human-readable evaluation report |
| `sessions/<SESSION_ID>/` | Agent output (eval_trace.json, final_report.md, etc.) |

## Troubleshooting

**ModuleNotFoundError: No module named 'src'**
Run from the repo root, not from inside a subdirectory.

**Fixture not found / 0 fixtures loaded**
Check that fixture directories have `fixture_meta.yaml` (not `metadata.yaml`) and `disclosure.md` (not `invention_disclosure.md`).

**Scorer crashes with 'NoneType' object has no attribute 'strip'**
Some ground truth features have None for the name field. This is a known bug being fixed in `_matching.py`.

**Azure content filter error**
Some invention disclosures trigger Azure's content filter. Note the case ID and skip it. The batch runner will continue to the next fixture.

**batch_summary.json gets overwritten**
Each batch run overwrites the previous batch_summary.json. Back up results before starting a new run if needed.