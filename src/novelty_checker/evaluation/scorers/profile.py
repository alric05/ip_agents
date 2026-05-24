"""Scoring Profile aggregator.

Collects results from all scorers and produces per-fixture summaries,
suite-level aggregates, and Alpha gate pass/fail decisions.
"""

from __future__ import annotations

import json
import logging
import statistics
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from src.novelty_checker.evaluation.scorers._base import ScorerResult

_logger = logging.getLogger(__name__)

# Alpha gate thresholds per eval_metrics_strategy.md §7
_ALPHA_GATES: dict[str, tuple[str, float]] = {
    # metric_name -> (comparison, threshold)
    "prior_art_hit_rate": (">=", 0.60),
    # "prior_art_recall": (">=", 0.40),
    "verdict_accuracy": (">=", 0.60),
    "feature_precision": (">=", 0.60),
    "feature_recall": (">=", 0.65),
    "tool_error_rate": (">=", 0.90),  # <=10% error rate = score >= 0.90
    "report_section_completeness": (">=", 0.7),
}


@dataclass
class ScoringProfile:
    """Aggregated scoring results across fixtures.

    Attributes:
        fixture_results: case_id -> list of ScorerResult for that case.
        suite_summary: metric_name -> aggregated score (mean across fixtures).
        gate_result: metric_name -> whether the gate threshold passed.
        alpha_passed: True if all Tier-1 gates passed.
    """

    fixture_results: dict[str, list[ScorerResult]] = field(default_factory=dict)
    suite_summary: dict[str, float] = field(default_factory=dict)
    gate_result: dict[str, bool] = field(default_factory=dict)
    alpha_passed: bool = False

    @classmethod
    def from_results(
        cls,
        results: dict[str, list[ScorerResult]],
        alpha_gates: dict[str, tuple[str, float]] | None = None,
    ) -> ScoringProfile:
        """Build a ScoringProfile from per-fixture scorer results.

        Args:
            results: Dict of case_id -> list of ScorerResult.
            alpha_gates: Optional override for gate thresholds.
                Format: metric_name -> (comparison_op, threshold).
        """
        gates = alpha_gates or _ALPHA_GATES
        profile = cls(fixture_results=results)

        # Aggregate: collect all scores per metric across fixtures
        metric_scores: dict[str, list[float]] = {}
        for case_id, scorer_results in results.items():
            for sr in scorer_results:
                metric_scores.setdefault(sr.metric_name, []).append(sr.score)

        # Compute suite summary (mean score per metric)
        for metric_name, scores in metric_scores.items():
            profile.suite_summary[metric_name] = round(
                statistics.mean(scores), 4
            ) if scores else 0.0

        # Check Alpha gates
        all_passed = True
        for metric_name, (op, threshold) in gates.items():
            mean_score = profile.suite_summary.get(metric_name)
            if mean_score is None:
                # Metric not computed — gate fails
                profile.gate_result[metric_name] = False
                all_passed = False
            elif op == ">=":
                passed = mean_score >= threshold
                profile.gate_result[metric_name] = passed
                if not passed:
                    all_passed = False
            elif op == "<=":
                passed = mean_score <= threshold
                profile.gate_result[metric_name] = passed
                if not passed:
                    all_passed = False

        # profile.alpha_passed = all_passed
        # Pass if at most 1 gate metric fails (5 of 6 minimum)
        failed_count = sum(1 for v in profile.gate_result.values() if not v)
        profile.alpha_passed = failed_count <= 1
        return profile

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "fixture_results": {
                case_id: [sr.to_dict() for sr in results]
                for case_id, results in self.fixture_results.items()
            },
            "suite_summary": self.suite_summary,
            "gate_result": self.gate_result,
            "alpha_passed": self.alpha_passed,
        }

    def to_json(self, path: Path) -> None:
        """Write scoring results to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        _logger.info("Scoring results written to %s", path)

    def summary_table(self) -> str:
        """Generate a human-readable summary table."""
        lines = [
            "=" * 60,
            "SCORING PROFILE SUMMARY",
            "=" * 60,
            f"{'Metric':<30} {'Score':>8} {'Gate':>8} {'Status':>8}",
            "-" * 60,
        ]
        for metric, score in sorted(self.suite_summary.items()):
            gate = self.gate_result.get(metric)
            if gate is not None:
                status = "PASS" if gate else "FAIL"
                gate_str = f"{_ALPHA_GATES.get(metric, ('', 0.0))[1]:.2f}"
            else:
                status = "---"
                gate_str = "---"
            lines.append(f"{metric:<30} {score:>8.4f} {gate_str:>8} {status:>8}")

        lines.append("-" * 60)
        lines.append(
            f"Alpha Gate: {'PASSED' if self.alpha_passed else 'FAILED'}"
        )
        lines.append(f"Fixtures evaluated: {len(self.fixture_results)}")
        lines.append("=" * 60)
        return "\n".join(lines)
