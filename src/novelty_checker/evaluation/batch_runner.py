"""Batch evaluation runner and CLI for the novelty checker evaluation pipeline.

Discovers fixtures, runs each through the full pipeline (eval_runner,
checklist, trace_writer), handles per-run errors without stopping the
batch, and produces a batch summary.

Usage:
    # Run all fixtures with a config
    python -m src.novelty_checker.evaluation.batch_runner --config configs/alpha_eval.yaml

    # Run a single fixture (for debugging)
    python -m src.novelty_checker.evaluation.batch_runner --config configs/alpha_eval.yaml --fixture TST-GEAR-001

    # Dry run (list fixtures without running)
    python -m src.novelty_checker.evaluation.batch_runner --config configs/alpha_eval.yaml --dry-run

    # Resume a partial batch (skip already-completed fixtures)
    python -m src.novelty_checker.evaluation.batch_runner --config configs/alpha_eval.yaml --resume
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)


@dataclass
class FixtureRunStatus:
    """Status of a single fixture run within a batch."""
    case_id: str
    status: str                          # "completed" | "failed" | "skipped"
    duration_seconds: float = 0.0
    estimated_cost_usd: float = 0.0
    checklist_passed: bool = False
    total_turns: int = 0
    final_phase: str = ""
    error: str | None = None
    session_id: str = ""
    eval_trace_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BatchSummary:
    """Summary of a complete batch evaluation run."""
    config_name: str
    config_version: str
    model: str
    hitl_mode: str
    start_time: str
    end_time: str
    total_duration_seconds: float
    total_fixtures: int
    completed: int
    failed: int
    skipped: int
    total_estimated_cost_usd: float
    checklist_pass_rate: float
    fixture_results: list[FixtureRunStatus] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["fixture_results"] = [fr.to_dict() for fr in self.fixture_results]
        return d


def _extract_cost_from_telemetry(session_path: Path) -> float:
    """Read estimated cost from telemetry.json if available."""
    telemetry_path = session_path / "telemetry.json"
    if not telemetry_path.exists():
        return 0.0
    try:
        with open(telemetry_path, encoding="utf-8") as f:
            data = json.load(f)
        summary = data.get("summary", data)
        token_usage = summary.get("token_usage", {})
        cumulative = token_usage.get("cumulative", {})
        return cumulative.get("estimated_cost_usd", 0.0)
    except Exception:
        return 0.0


def _fixture_already_completed(output_dir: Path, case_id: str) -> bool:
    """Check if a fixture has already been run (eval_trace.json exists)."""
    # Look for any session directory containing this case_id's trace
    if not output_dir.exists():
        return False
    for session_dir in output_dir.iterdir():
        if not session_dir.is_dir():
            continue
        trace_path = session_dir / "eval_trace.json"
        if trace_path.exists():
            try:
                with open(trace_path, encoding="utf-8") as f:
                    trace = json.load(f)
                meta = trace.get("run_metadata", {})
                run_config = meta.get("run_config", {})
                if run_config.get("fixture_case_id") == case_id:
                    return True
            except Exception:
                continue
    return False


def run_single_fixture(
    case: Any,
    config: Any,
    output_dir: Path,
    progress_callback: Any | None = None,
    runner: str = "deepagent",
) -> FixtureRunStatus:
    """Run the full evaluation pipeline on a single fixture.

    Calls eval_runner -> checklist -> trace_writer for one fixture.
    Catches all exceptions and returns a FixtureRunStatus (never raises).

    Args:
        case: A FixtureCase from the fixture_loader.
        config: A RunConfig with run parameters.
        output_dir: Base output directory for this batch.
        progress_callback: Optional callback for eval_runner progress.
        runner: Which agent to evaluate — "deepagent" (default) runs the
            full deep agent via `run_novelty_check_e2e`; "baseline" runs
            the single-LLM ReAct baseline via `run_baseline_e2e` for
            head-to-head comparison on the same fixtures.

    Returns:
        FixtureRunStatus with the outcome.
    """
    case_id = case.case_id
    status = FixtureRunStatus(case_id=case_id, status="failed")
    start_time = time.perf_counter()

    try:
        # Import here to avoid circular imports and to fail gracefully
        # if the agent code is not available (e.g., during unit testing)
        from src.novelty_checker.evaluation.eval_checklist import run_functional_checklist
        from src.novelty_checker.evaluation.trace_writer import write_eval_trace

        if runner == "baseline":
            from src.novelty_checker.baseline_runner import run_baseline_e2e as _run_e2e
            _runner_kwargs: dict[str, Any] = {
                "auto_prompt_prefix": config.auto_scope_prompt_prefix,
            }
        elif runner == "deepagent":
            from src.novelty_checker.eval_runner import run_novelty_check_e2e as _run_e2e
            _runner_kwargs = {}
        else:
            raise ValueError(f"Unknown runner: {runner!r} (expected 'deepagent' or 'baseline')")

        _logger.info(
            "Starting fixture %s (runner=%s, difficulty=%s)",
            case_id, runner, case.meta.difficulty,
        )

        idea = case.disclosure_text if runner == "baseline" else (
            config.auto_scope_prompt_prefix + case.disclosure_text
        )

        result = _run_e2e(
            idea=idea,
            max_turns=config.max_turns,
            progress_callback=progress_callback,
            **_runner_kwargs,
        )

        status.session_id = result.session_id
        status.total_turns = result.total_turns
        status.final_phase = result.final_phase.name
        status.error = result.error

        # Run the checklist
        checklist = run_functional_checklist(result)
        status.checklist_passed = checklist.passed

        # Write the trace (embed run config + fixture info)
        trace_path = write_eval_trace(result, checklist)
        if trace_path:
            status.eval_trace_path = str(trace_path)

        # Extract cost from telemetry
        status.estimated_cost_usd = _extract_cost_from_telemetry(result.session_path)

        # Copy ground truth into session directory for scorers
        _copy_ground_truth(case, result.session_path)

        elapsed = time.perf_counter() - start_time
        status.duration_seconds = round(elapsed, 1)

        if result.error:
            status.status = "failed"
            _logger.warning(
                "Fixture %s FAILED in %.1fs: %s",
                case_id, elapsed, result.error,
            )
        else:
            status.status = "completed"
            _logger.info(
                "Fixture %s COMPLETED in %.1fs ($%.2f, checklist=%s)",
                case_id, elapsed, status.estimated_cost_usd,
                "PASS" if checklist.passed else "FAIL",
            )

    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        status.duration_seconds = round(elapsed, 1)
        status.status = "failed"
        status.error = f"{type(exc).__name__}: {exc}"
        _logger.error(
            "Fixture %s CRASHED after %.1fs: %s",
            case_id, elapsed, exc,
            exc_info=True,
        )

    return status


def _copy_ground_truth(case: Any, session_path: Path) -> None:
    """Copy ground truth files into the session directory for scorer access.

    Creates a ground_truth/ subdirectory in the session with copies of
    the gt_*.json files so scorers can find them alongside the trace.
    """
    gt_dir = session_path / "ground_truth"
    gt_dir.mkdir(exist_ok=True)

    if case.gt_features is not None:
        _write_json(gt_dir / "gt_features.json", case.gt_features)
    if case.gt_references is not None:
        _write_json(gt_dir / "gt_references.json", case.gt_references)
    if case.gt_verdict is not None:
        _write_json(gt_dir / "gt_verdict.json", case.gt_verdict)
    if case.gt_search_strategy is not None:
        _write_json(gt_dir / "gt_search_strategy.json", case.gt_search_strategy)

    # Also copy fixture metadata
    if case.meta is not None:
        meta_dict = {
            "case_id": case.meta.case_id,
            "domain": case.meta.domain,
            "difficulty": case.meta.difficulty,
            "language": case.meta.language,
            "source": case.meta.source,
        }
        _write_json(gt_dir / "fixture_meta.json", meta_dict)


def _write_json(path: Path, data: Any) -> None:
    """Write JSON data to a file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def run_batch(
    config: Any,
    cases: list[Any],
    resume: bool = False,
    runner: str = "deepagent",
) -> BatchSummary:
    """Run the full evaluation pipeline on a batch of fixtures.

    Args:
        config: A RunConfig with run parameters.
        cases: List of FixtureCase objects to evaluate.
        resume: If True, skip fixtures that already have eval_trace.json.
        runner: "deepagent" (default) or "baseline" — selects which
            agent to evaluate. See `run_single_fixture` for details.

    Returns:
        BatchSummary with per-fixture results.
    """
    output_dir = Path(config.output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)

    batch_start = time.perf_counter()
    batch_start_iso = datetime.now().isoformat()

    fixture_results: list[FixtureRunStatus] = []

    for i, case in enumerate(cases, 1):
        _logger.info(
            "--- Fixture %d/%d: %s ---",
            i, len(cases), case.case_id,
        )

        # Resume: skip if already completed
        if resume and _fixture_already_completed(output_dir, case.case_id):
            _logger.info("Skipping %s (already completed, --resume mode)", case.case_id)
            fixture_results.append(FixtureRunStatus(
                case_id=case.case_id,
                status="skipped",
            ))
            continue

        # Run the fixture
        result = run_single_fixture(case, config, output_dir, runner=runner)
        fixture_results.append(result)

    batch_end = time.perf_counter()
    batch_end_iso = datetime.now().isoformat()
    total_duration = round(batch_end - batch_start, 1)

    completed = sum(1 for r in fixture_results if r.status == "completed")
    failed = sum(1 for r in fixture_results if r.status == "failed")
    skipped = sum(1 for r in fixture_results if r.status == "skipped")
    total_cost = sum(r.estimated_cost_usd for r in fixture_results)

    completed_with_checklist = [r for r in fixture_results if r.status == "completed"]
    checklist_pass_count = sum(1 for r in completed_with_checklist if r.checklist_passed)
    checklist_pass_rate = (
        checklist_pass_count / len(completed_with_checklist)
        if completed_with_checklist else 0.0
    )

    summary = BatchSummary(
        config_name=config.config_name,
        config_version=config.config_version,
        model=config.model,
        hitl_mode=config.hitl_mode,
        start_time=batch_start_iso,
        end_time=batch_end_iso,
        total_duration_seconds=total_duration,
        total_fixtures=len(cases),
        completed=completed,
        failed=failed,
        skipped=skipped,
        total_estimated_cost_usd=round(total_cost, 2),
        checklist_pass_rate=round(checklist_pass_rate, 3),
        fixture_results=fixture_results,
    )

    # Write batch summary
    summary_path = output_dir / "batch_summary.json"
    _write_json(summary_path, summary.to_dict())
    _logger.info("Batch summary written to %s", summary_path)

    return summary


def _print_summary(summary: BatchSummary) -> None:
    """Print a human-readable batch summary to stdout."""
    print()
    print("=" * 60)
    print(f"BATCH EVALUATION COMPLETE: {summary.config_name}")
    print("=" * 60)
    print(f"  Model:      {summary.model}")
    print(f"  HITL mode:  {summary.hitl_mode}")
    print(f"  Duration:   {summary.total_duration_seconds:.1f}s")
    print(f"  Cost:       ${summary.total_estimated_cost_usd:.2f}")
    print()
    print(f"  Fixtures:   {summary.total_fixtures}")
    print(f"  Completed:  {summary.completed}")
    print(f"  Failed:     {summary.failed}")
    print(f"  Skipped:    {summary.skipped}")
    print(f"  Checklist:  {summary.checklist_pass_rate*100:.0f}% pass rate")
    print()

    if summary.fixture_results:
        print("  Per-fixture results:")
        for r in summary.fixture_results:
            icon = {"completed": "PASS", "failed": "FAIL", "skipped": "SKIP"}.get(r.status, "????")
            cost_str = f"${r.estimated_cost_usd:.2f}" if r.estimated_cost_usd else ""
            time_str = f"{r.duration_seconds:.0f}s" if r.duration_seconds else ""
            checklist_str = ""
            if r.status == "completed":
                checklist_str = "checklist=PASS" if r.checklist_passed else "checklist=FAIL"

            parts = [p for p in [time_str, cost_str, checklist_str] if p]
            detail = f" ({', '.join(parts)})" if parts else ""

            print(f"    [{icon}] {r.case_id}{detail}")
            if r.error:
                print(f"           Error: {r.error[:100]}")
    print()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run the novelty checker evaluation pipeline on fixture files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s --config configs/alpha_eval.yaml\n"
            "  %(prog)s --config configs/alpha_eval.yaml --fixture TST-GEAR-001\n"
            "  %(prog)s --config configs/alpha_eval.yaml --dry-run\n"
            "  %(prog)s --config configs/alpha_eval.yaml --resume\n"
        ),
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Path to the YAML run configuration file.",
    )
    parser.add_argument(
        "--fixture",
        default=None,
        help="Run only this fixture (by case_id). Useful for debugging.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover and list fixtures without running them.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip fixtures that already have eval_trace.json in the output directory.",
    )
    parser.add_argument(
        "--runner",
        choices=("deepagent", "baseline"),
        default="deepagent",
        help=(
            "Which agent to evaluate: 'deepagent' (default) runs the "
            "full multi-agent deep agent; 'baseline' runs the "
            "single-LLM ReAct baseline for head-to-head comparison."
        ),
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging.",
    )

    args = parser.parse_args()

    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Load config
    from src.novelty_checker.evaluation.run_config import load_run_config
    config = load_run_config(args.config)

    # Discover fixtures
    from src.novelty_checker.evaluation.fixture_loader import discover_fixtures
    cases = discover_fixtures(
        config.fixture_directory,
        fixture_filter=config.fixture_filter,
    )

    if not cases:
        _logger.error("No fixtures found in %s", config.fixture_directory)
        sys.exit(1)

    # Filter to single fixture if specified
    if args.fixture:
        cases = [c for c in cases if c.case_id == args.fixture]
        if not cases:
            _logger.error("Fixture %s not found", args.fixture)
            sys.exit(1)

    # Dry run: just list fixtures
    if args.dry_run:
        print(f"Config: {config.config_name} (model={config.model}, hitl={config.hitl_mode})")
        print(f"Fixtures directory: {config.fixture_directory}")
        print(f"Found {len(cases)} fixtures:")
        for c in cases:
            gt_status = []
            if c.gt_features is not None:
                gt_status.append(f"{c.gt_features.get('total_features', 0)} features")
            if c.gt_references is not None:
                gt_status.append(f"{c.gt_references.get('total_references', 0)} refs")
            if c.gt_verdict is not None:
                gt_status.append(f"verdict={c.gt_verdict.get('overall', {}).get('verdict', '?')}")
            gt_str = ", ".join(gt_status) if gt_status else "no ground truth"
            print(f"  {c.case_id} (domain={c.meta.domain}, difficulty={c.meta.difficulty}) [{gt_str}]")
        return

    # Run batch
    _logger.info(
        "Starting batch: %d fixtures, runner=%s, model=%s, hitl=%s",
        len(cases), args.runner, config.model, config.hitl_mode,
    )

    summary = run_batch(config, cases, resume=args.resume, runner=args.runner)
    _print_summary(summary)

    # Exit with non-zero if any fixtures failed
    if summary.failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()