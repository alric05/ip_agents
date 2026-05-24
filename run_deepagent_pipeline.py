"""Run the deep agent against a golden fixture and score it.

Mirror of `run_baseline_pipeline.py` that calls `run_novelty_check_e2e`
(the full multi-agent deep agent) instead of `run_baseline_e2e`. Used for
head-to-head comparison: running both scripts on the same fixture under
the same JWT on the same day yields two scored session directories that
diff directly to agentic-design lift.

Usage:
    python run_deepagent_pipeline.py                      # defaults to C19904
    python run_deepagent_pipeline.py --case C19904        # explicit case
    python run_deepagent_pipeline.py --case C19904 --max-turns 40
"""

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from src.novelty_checker.eval_runner import run_novelty_check_e2e
from src.novelty_checker.evaluation.eval_checklist import run_functional_checklist
from src.novelty_checker.evaluation.scorers.runner import get_all_scorers, score_fixture
from src.novelty_checker.evaluation.trace_writer import write_eval_trace

_GOLDEN_DIR = Path(__file__).parent / "evals" / "golden_datasets" / "cases"


def _load_disclosure(case_id: str) -> tuple[str, Path]:
    case_dir = _GOLDEN_DIR / case_id
    disclosure_path = case_dir / "disclosure.md"
    if not disclosure_path.exists():
        raise FileNotFoundError(f"No disclosure.md at {disclosure_path}")
    return disclosure_path.read_text(encoding="utf-8").strip(), case_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", default="C19904", help="Case ID under evals/golden_datasets/cases/")
    parser.add_argument("--max-turns", type=int, default=40, help="Max invoke() iterations")
    parser.add_argument("--max-duration-seconds", type=float, default=3600.0)
    args = parser.parse_args()

    idea, case_dir = _load_disclosure(args.case)
    print(f"Loaded disclosure for case {args.case} ({len(idea):,} chars)")
    print(f"Ground truth directory: {case_dir}")
    print()

    # --- Step 1: run the deep agent ---
    print("Step 1: Running deep agent...")
    result = run_novelty_check_e2e(
        idea=idea,
        max_turns=args.max_turns,
        max_duration_seconds=args.max_duration_seconds,
    )
    print(f"  Phase:     {result.final_phase.name}")
    print(f"  Turns:     {result.total_turns}")
    print(f"  Duration:  {result.total_duration_seconds:.1f}s")
    print(f"  Model:     {result.model_name}")
    print(f"  Error:     {result.error}")
    print(f"  Session:   {result.session_path}")

    total_tool_calls = sum(len(t.tool_call_details) for t in result.turns)
    total_tokens = sum(
        t.token_usage.total_tokens for t in result.turns if t.token_usage
    )
    print(f"  Tool calls: {total_tool_calls}")
    print(f"  Tokens:     {total_tokens:,}")
    print()

    # --- Step 2: functional checklist ---
    print("Step 2: Running functional checklist...")
    checklist = run_functional_checklist(result)
    print(f"  Overall: {'PASSED' if checklist.passed else 'FAILED'}")
    for name, passed in checklist.checks.items():
        status = "PASS" if passed else "FAIL"
        print(f"    [{status}] {name}: {checklist.details[name]}")
    print()

    # --- Step 3: write eval_trace.json ---
    print("Step 3: Writing eval_trace.json...")
    trace = write_eval_trace(result, checklist)
    trace_path = result.session_path / "eval_trace.json"
    print(f"  Written to: {trace_path}")
    print(f"  File size:  {trace_path.stat().st_size:,} bytes")
    print()

    # --- Step 4: score against ground truth ---
    print("Step 4: Scoring against ground truth...")
    scorer_results = score_fixture(
        session_path=result.session_path,
        fixture_path=case_dir,
        scorers=get_all_scorers(),
    )

    print()
    print("=" * 72)
    print(f"METRICS FOR DEEP-AGENT RUN ({args.case}, model={result.model_name})")
    print("=" * 72)
    for r in scorer_results:
        pass_mark = "PASS" if r.passed else "FAIL"
        thresh = f"(thr={r.threshold:.2f})" if r.threshold is not None else ""
        print(f"  [{pass_mark}] {r.metric_name:40s}  score={r.score:.4f}  {thresh}")
    print("=" * 72)
    print()
    print(f"Session: {result.session_path}")
    print(f"Trace:   {trace_path}")


if __name__ == "__main__":
    main()
