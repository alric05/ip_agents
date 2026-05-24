"""Run baseline and deep-agent pipelines on ALL fixtures and collect scoring results.

Iterates over all 22 fixture cases, runs both the single-LLM baseline and the
multi-agent deep agent on each, scores against ground truth, and writes a
consolidated JSON report for downstream comparison/visualization.

Output:
    evals/results/all_cases_scores.json  — per-case, per-runner scoring results
    evals/results/baseline/              — per-case session dirs
    evals/results/deepagent/             — per-case session dirs

Usage:
    python run_all_cases_pipeline.py                     # run both runners on all cases
    python run_all_cases_pipeline.py --runner baseline   # only baseline
    python run_all_cases_pipeline.py --runner deepagent  # only deep agent
    python run_all_cases_pipeline.py --cases C19904 C11309  # subset of cases
    python run_all_cases_pipeline.py --max-turns 30
    python run_all_cases_pipeline.py --resume            # skip already-completed cases
    python run_all_cases_pipeline.py --parallel 4        # run 4 cases concurrently
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from src.novelty_checker.evaluation.fixture_loader import (
    discover_fixtures,
    FixtureCase,
)
from src.novelty_checker.evaluation.scorers._base import ScorerResult
from src.novelty_checker.evaluation.scorers.runner import get_all_scorers, score_fixture
from src.novelty_checker.evaluation.eval_checklist import run_functional_checklist
from src.novelty_checker.evaluation.trace_writer import write_eval_trace

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
_logger = logging.getLogger(__name__)

_FIXTURES_DIR = Path(__file__).parent / "src" / "novelty_checker" / "evaluation" / "fixtures"
_OUTPUT_DIR = Path(__file__).parent / "evals" / "results"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CaseResult:
    """Scoring result for a single case under a specific runner."""
    case_id: str
    runner: str
    difficulty: str
    domain: str
    status: str  # "completed" | "failed" | "skipped"
    scores: dict[str, float] = field(default_factory=dict)
    passed: dict[str, bool] = field(default_factory=dict)
    thresholds: dict[str, float] = field(default_factory=dict)
    duration_seconds: float = 0.0
    total_turns: int = 0
    total_tokens: int = 0
    error: str | None = None
    session_path: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AllCasesReport:
    """Consolidated report across all cases and runners."""
    generated_at: str
    total_cases: int
    runners: list[str]
    results: list[CaseResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["results"] = [r.to_dict() for r in self.results]
        return d


# ---------------------------------------------------------------------------
# Pipeline logic
# ---------------------------------------------------------------------------

def _run_single_case(
    case: FixtureCase,
    runner: str,
    max_turns: int,
    max_duration_seconds: float,
) -> CaseResult:
    """Run a single case through one runner and return scored results."""
    case_id = case.case_id
    difficulty = case.meta.difficulty or "Unknown"
    domain = case.meta.domain or ""
    result_entry = CaseResult(
        case_id=case_id,
        runner=runner,
        difficulty=difficulty,
        domain=domain,
        status="failed",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    start = time.perf_counter()

    try:
        if runner == "baseline":
            from src.novelty_checker.baseline_runner import run_baseline_e2e
            result = run_baseline_e2e(
                idea=case.disclosure_text,
                max_turns=max_turns,
                max_duration_seconds=max_duration_seconds,
            )
        elif runner == "deepagent":
            from src.novelty_checker.eval_runner import run_novelty_check_e2e
            result = run_novelty_check_e2e(
                idea=case.disclosure_text,
                max_turns=max_turns,
                max_duration_seconds=max_duration_seconds,
            )
        else:
            raise ValueError(f"Unknown runner: {runner!r}")

        result_entry.total_turns = result.total_turns
        result_entry.session_path = str(result.session_path)
        result_entry.total_tokens = sum(
            t.token_usage.total_tokens for t in result.turns if t.token_usage
        )

        # Run checklist + trace
        checklist = run_functional_checklist(result)
        write_eval_trace(result, checklist)

        # Score against ground truth
        scorers = get_all_scorers()
        scorer_results = score_fixture(
            session_path=result.session_path,
            fixture_path=case.fixture_path,
            scorers=scorers,
        )

        for sr in scorer_results:
            result_entry.scores[sr.metric_name] = sr.score
            result_entry.passed[sr.metric_name] = sr.passed
            result_entry.thresholds[sr.metric_name] = sr.threshold

        result_entry.status = "completed"
        result_entry.error = result.error

    except Exception as exc:
        _logger.error("Case %s/%s failed: %s", case_id, runner, exc)
        result_entry.error = str(exc)
        result_entry.status = "failed"

    result_entry.duration_seconds = round(time.perf_counter() - start, 1)
    return result_entry


def _is_already_completed(report_path: Path, case_id: str, runner: str) -> bool:
    """Check if a case/runner combo already exists in the saved report."""
    if not report_path.exists():
        return False
    try:
        with open(report_path, encoding="utf-8") as f:
            data = json.load(f)
        for r in data.get("results", []):
            if r["case_id"] == case_id and r["runner"] == runner and r["status"] == "completed":
                return True
    except Exception:
        pass
    return False


def _save_report(report: AllCasesReport, output_path: Path) -> None:
    """Incrementally save the report to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2)


def run_all_cases(
    runners: list[str],
    case_ids: list[str] | None = None,
    max_turns: int = 30,
    max_duration_seconds: float = 3600.0,
    resume: bool = False,
    parallel: int = 1,
) -> Path:
    """Run pipelines on all fixtures and produce consolidated report.

    Args:
        runners: List of runners to evaluate ("baseline", "deepagent").
        case_ids: Optional subset of case IDs. None = all discovered fixtures.
        max_turns: Maximum agent turns per case.
        max_duration_seconds: Maximum wall-clock time per case.
        resume: If True, skip cases already in the output report.
        parallel: Number of concurrent workers (1 = sequential).

    Returns:
        Path to the consolidated scores JSON file.
    """
    output_path = _OUTPUT_DIR / "all_cases_scores.json"

    # Discover fixtures
    cases = discover_fixtures(str(_FIXTURES_DIR))
    if case_ids:
        cases = [c for c in cases if c.case_id in case_ids]

    _logger.info("Discovered %d fixtures to evaluate", len(cases))

    report = AllCasesReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_cases=len(cases),
        runners=runners,
    )

    # Load existing results if resuming
    if resume and output_path.exists():
        try:
            with open(output_path, encoding="utf-8") as f:
                existing = json.load(f)
            for r in existing.get("results", []):
                report.results.append(CaseResult(**r))
        except Exception:
            pass

    # Build work items (skip already-completed if resuming)
    work_items: list[tuple[FixtureCase, str]] = []
    for case in cases:
        for runner in runners:
            if resume and _is_already_completed(output_path, case.case_id, runner):
                _logger.info("SKIP %s/%s (already completed)", case.case_id, runner)
                continue
            work_items.append((case, runner))

    total_runs = len(work_items)
    _logger.info("Running %d case/runner combos (parallel=%d)", total_runs, parallel)

    if parallel <= 1:
        # Sequential execution
        for idx, (case, runner) in enumerate(work_items, 1):
            _logger.info(
                "[%d/%d] Running %s/%s (difficulty=%s)...",
                idx, total_runs, case.case_id, runner, case.meta.difficulty,
            )
            case_result = _run_single_case(case, runner, max_turns, max_duration_seconds)
            report.results.append(case_result)

            status_icon = "OK" if case_result.status == "completed" else "FAIL"
            _logger.info(
                "[%d/%d]  -> %s in %.1fs (%d turns, %d tokens)",
                idx, total_runs, status_icon, case_result.duration_seconds,
                case_result.total_turns, case_result.total_tokens,
            )
            _save_report(report, output_path)
    else:
        # Parallel execution with bounded concurrency
        _logger.info("Starting parallel execution with %d workers...", parallel)
        with ProcessPoolExecutor(max_workers=parallel) as executor:
            future_to_info = {
                executor.submit(
                    _run_single_case, case, runner, max_turns, max_duration_seconds
                ): (case.case_id, runner)
                for case, runner in work_items
            }

            for idx, future in enumerate(as_completed(future_to_info), 1):
                case_id, runner = future_to_info[future]
                try:
                    case_result = future.result()
                    report.results.append(case_result)
                    status_icon = "OK" if case_result.status == "completed" else "FAIL"
                    _logger.info(
                        "[%d/%d] %s/%s -> %s in %.1fs (%d turns, %d tokens)",
                        idx, total_runs, case_id, runner, status_icon,
                        case_result.duration_seconds, case_result.total_turns,
                        case_result.total_tokens,
                    )
                except Exception as exc:
                    _logger.error("[%d/%d] %s/%s process error: %s", idx, total_runs, case_id, runner, exc)
                    report.results.append(CaseResult(
                        case_id=case_id, runner=runner, difficulty="Unknown",
                        domain="", status="failed", error=str(exc),
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    ))

                # Save after each completion
                _save_report(report, output_path)

    # Final save with updated timestamp
    report.generated_at = datetime.now(timezone.utc).isoformat()
    _save_report(report, output_path)
    _logger.info("Report saved to %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--runner",
        choices=["baseline", "deepagent", "both"],
        default="both",
        help="Which runner(s) to evaluate (default: both)",
    )
    parser.add_argument(
        "--cases",
        nargs="*",
        default=None,
        help="Optional subset of case IDs to run (default: all 22)",
    )
    parser.add_argument("--max-turns", type=int, default=30)
    parser.add_argument("--max-duration-seconds", type=float, default=3600.0)
    parser.add_argument("--resume", action="store_true", help="Skip already-completed cases")
    parser.add_argument(
        "--parallel", type=int, default=1,
        help="Number of concurrent workers (default: 1 = sequential). "
             "Recommended: 3-4 to stay within API rate limits.",
    )
    args = parser.parse_args()

    runners = ["baseline", "deepagent"] if args.runner == "both" else [args.runner]

    output_path = run_all_cases(
        runners=runners,
        case_ids=args.cases,
        max_turns=args.max_turns,
        max_duration_seconds=args.max_duration_seconds,
        resume=args.resume,
        parallel=args.parallel,
    )

    print(f"\nAll cases scored. Report: {output_path}")


if __name__ == "__main__":
    main()
