"""CLI runner for evaluation scorers.

Supports two modes:
- Single fixture: --session <path> --gt <path>
- Full suite: --suite <path/to/cases/>

Also provides a programmatic API for integration with DeepEval's evaluate().

Usage:
    python -m src.novelty_checker.evaluation.scorers.runner \
        --session sessions/abc123 --gt evals/golden_datasets/cases/case_001

    python -m src.novelty_checker.evaluation.scorers.runner \
        --suite evals/golden_datasets/cases/
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from src.novelty_checker.evaluation.scorers._base import NoveltyBaseMetric, ScorerResult
from src.novelty_checker.evaluation.scorers._loader import (
    build_test_case,
    load_eval_trace,
    load_ground_truth,
)
from src.novelty_checker.evaluation.scorers.profile import ScoringProfile
from src.novelty_checker.evaluation.scorers.tier1.feature_extraction import (
    FeaturePrecisionMetric,
    FeatureRecallMetric,
)
from src.novelty_checker.evaluation.scorers.tier1.prior_art_hit_rate import (
    PriorArtHitRateMetric,
)
from src.novelty_checker.evaluation.scorers.tier1.prior_art_recall import (
    PriorArtRecallMetric,
)
from src.novelty_checker.evaluation.scorers.tier1.verdict_accuracy import (
    VerdictAccuracyMetric,
)
from src.novelty_checker.evaluation.scorers.tier2.feature_coverage_accuracy import (
    FeatureCoverageAccuracyMetric,
)
from src.novelty_checker.evaluation.scorers.tier2.report_completeness import (
    ReportCompletenessMetric,
)
from src.novelty_checker.evaluation.scorers.tier2.search_strategy import (
    SearchStrategyMetric,
)
from src.novelty_checker.evaluation.scorers.tier2.triage_agreement import (
    TriageAgreementMetric,
)
from src.novelty_checker.evaluation.scorers.tier3.operational import (
    CostPerRunMetric,
    LatencyMetric,
    ResearchRoundsMetric,
    SearchReproducibilityMetric,
    TokenEfficiencyMetric,
    ToolErrorRateMetric,
    ToolInvocationMetric,
)

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scorer registry
# ---------------------------------------------------------------------------

def get_all_scorers(config: dict[str, Any] | None = None) -> list[NoveltyBaseMetric]:
    """Instantiate all available scorers with default or custom config."""
    return [
        # Tier-1
        VerdictAccuracyMetric(),
        PriorArtHitRateMetric(),
        PriorArtRecallMetric(),
        FeaturePrecisionMetric(),
        FeatureRecallMetric(),
        # Tier-2
        ReportCompletenessMetric(),
        SearchStrategyMetric(),
        TriageAgreementMetric(),
        FeatureCoverageAccuracyMetric(),
        # Tier-3
        CostPerRunMetric(),
        LatencyMetric(),
        TokenEfficiencyMetric(),
        ToolErrorRateMetric(),
        SearchReproducibilityMetric(),
        ResearchRoundsMetric(),
        ToolInvocationMetric(),
    ]


def get_tier1_scorers() -> list[NoveltyBaseMetric]:
    """Instantiate only Tier-1 (Alpha-blocking) scorers."""
    return [
        VerdictAccuracyMetric(),
        PriorArtHitRateMetric(),
        PriorArtRecallMetric(),
        FeaturePrecisionMetric(),
        FeatureRecallMetric(),
    ]


# ---------------------------------------------------------------------------
# Single fixture scoring
# ---------------------------------------------------------------------------

def score_fixture(
    session_path: Path,
    fixture_path: Path,
    scorers: list[NoveltyBaseMetric] | None = None,
) -> list[ScorerResult]:
    """Run all scorers against a single fixture.

    Args:
        session_path: Path to the agent session directory (contains
            eval_trace.json, features.md, references.md, etc.).
        fixture_path: Path to the ground truth fixture directory (contains
            gt_features.json, gt_references.json, gt_verdict.json).
        scorers: Optional list of scorer instances. Defaults to all scorers.

    Returns:
        List of ScorerResult from each scorer.
    """
    eval_trace = load_eval_trace(session_path)
    ground_truth = load_ground_truth(fixture_path)

    if scorers is None:
        scorers = get_all_scorers()

    results: list[ScorerResult] = []
    for scorer in scorers:
        try:
            result = scorer.score_standalone(
                eval_trace, ground_truth, session_path
            )
            results.append(result)
            _logger.info(
                "  %s: %.4f (%s)",
                result.metric_name,
                result.score,
                "PASS" if result.passed else "FAIL",
            )
        except Exception as exc:
            _logger.error("Scorer %s failed: %s", scorer.metric_name, exc)
            results.append(ScorerResult(
                metric_name=scorer.metric_name,
                score=0.0,
                confidence=0.0,
                passed=False,
                threshold=scorer.threshold,
                failures=[{
                    "type": "scorer_error",
                    "severity": "critical",
                    "evidence": str(exc),
                    "affected_element": scorer.metric_name,
                }],
                evidence={"error": str(exc)},
                scorer_type=scorer.scorer_type,
            ))

    return results


# ---------------------------------------------------------------------------
# Suite scoring
# ---------------------------------------------------------------------------

def score_suite(
    suite_path: Path,
    scorers: list[NoveltyBaseMetric] | None = None,
) -> ScoringProfile:
    """Run all scorers against all fixtures in a suite directory.

    Expects the suite directory structure:
        suite_path/
            case_001/
                gt_features.json, gt_references.json, gt_verdict.json
                agent_session/  (or a session_path pointer)
            case_002/
                ...

    Args:
        suite_path: Path to the suite directory containing case subdirs.
        scorers: Optional list of scorer instances.

    Returns:
        ScoringProfile with aggregated results.
    """
    all_results: dict[str, list[ScorerResult]] = {}

    case_dirs = sorted(
        d for d in suite_path.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )

    if not case_dirs:
        _logger.warning("No case directories found in %s", suite_path)
        return ScoringProfile.from_results({})

    for case_dir in case_dirs:
        case_id = case_dir.name
        _logger.info("Scoring fixture: %s", case_id)

        # Determine session path
        session_path = case_dir / "agent_session"
        if not session_path.exists():
            # Session artifacts may be directly in the case dir
            session_path = case_dir

        # Check for eval_trace.json
        if not (session_path / "eval_trace.json").exists():
            _logger.warning("No eval_trace.json in %s, skipping", session_path)
            continue

        results = score_fixture(session_path, case_dir, scorers)
        all_results[case_id] = results

    profile = ScoringProfile.from_results(all_results)

    # Write results to suite directory
    output_path = suite_path / "scoring_results.json"
    profile.to_json(output_path)

    return profile


# ---------------------------------------------------------------------------
# DeepEval integration
# ---------------------------------------------------------------------------

def build_deepeval_dataset(
    suite_path: Path,
) -> list[Any]:
    """Build DeepEval LLMTestCase objects for all fixtures in a suite.

    Returns a list of test cases that can be passed to deepeval.evaluate().
    """
    test_cases = []
    case_dirs = sorted(
        d for d in suite_path.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )

    for case_dir in case_dirs:
        session_path = case_dir / "agent_session"
        if not session_path.exists():
            session_path = case_dir
        if not (session_path / "eval_trace.json").exists():
            continue

        eval_trace = load_eval_trace(session_path)
        ground_truth = load_ground_truth(case_dir)
        tc = build_test_case(eval_trace, ground_truth, session_path, case_dir.name)
        test_cases.append(tc)

    return test_cases


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run evaluation scorers against agent sessions"
    )
    parser.add_argument(
        "--session", type=Path, help="Path to agent session directory"
    )
    parser.add_argument(
        "--gt", type=Path, help="Path to ground truth fixture directory"
    )
    parser.add_argument(
        "--suite", type=Path, help="Path to suite directory (overrides --session/--gt)"
    )
    parser.add_argument(
        "--tier1-only", action="store_true", help="Run only Tier-1 scorers"
    )
    parser.add_argument(
        "--output", type=Path, help="Output path for scoring_results.json"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    scorers = get_tier1_scorers() if args.tier1_only else get_all_scorers()

    if args.suite:
        profile = score_suite(args.suite, scorers)
        print(profile.summary_table())
        if args.output:
            profile.to_json(args.output)
    elif args.session and args.gt:
        results = score_fixture(args.session, args.gt, scorers)
        profile = ScoringProfile.from_results({"single": results})
        print(profile.summary_table())
        output = args.output or args.session / "scoring_results.json"
        profile.to_json(output)
    else:
        parser.error("Provide either --suite or both --session and --gt")
        sys.exit(1)


if __name__ == "__main__":
    main()
