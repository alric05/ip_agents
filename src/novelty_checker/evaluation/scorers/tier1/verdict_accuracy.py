"""Verdict Accuracy scorer (Tier-1, deterministic).

Measures whether the agent reached the correct novelty conclusion
by comparing its verdict against the ground truth.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.novelty_checker.evaluation.scorers._base import NoveltyBaseMetric, ScorerResult
from src.novelty_checker.evaluation.scorers._loader import (
    extract_verdict_from_report,
    load_session_artifact,
)

_logger = logging.getLogger(__name__)

def _compute_verdict_score(agent_verdict: str, gt_verdict: str) -> tuple[float, str]:
    """Compute score and match type for a verdict comparison.

    Exact match only — no partial credit per eval_metrics_strategy.md §2.1.

    Returns:
        (score, match_type) where match_type is "exact" or "mismatch".
    """
    if agent_verdict == gt_verdict:
        return 1.0, "exact"
    return 0.0, "mismatch"


class VerdictAccuracyMetric(NoveltyBaseMetric):
    """Measures whether the agent's novelty verdict matches ground truth.

    Supports exact match (1.0) and partial credit (0.5 for one-step-off).

    Alpha threshold: >= 0.70
    """

    def __init__(self, threshold: float = 0.70) -> None:
        super().__init__(
            metric_name="verdict_accuracy",
            threshold=threshold,
            scorer_type="deterministic",
        )

    def _compute(
        self,
        eval_trace: dict[str, Any],
        ground_truth: dict[str, Any],
        session_path: Path,
        config: dict[str, Any] | None = None,
    ) -> ScorerResult:
        # Extract agent verdict from final_report.md
        report_content = load_session_artifact(session_path, "final_report.md")
        agent_verdict = extract_verdict_from_report(report_content)

        # Extract GT verdict
        gt_verdict_data = ground_truth.get("verdict", {})
        # gt_verdict = (
        #     gt_verdict_data.get("verdict", "")
        #     if isinstance(gt_verdict_data, dict)
        #     else str(gt_verdict_data)
        # )
        if isinstance(gt_verdict_data, dict):
            overall = gt_verdict_data.get("overall", {})
            if isinstance(overall, dict):
                gt_verdict = overall.get("verdict", "")
            else:
                gt_verdict = gt_verdict_data.get("verdict", "")
        else:
            gt_verdict = str(gt_verdict_data)
        gt_verdict = gt_verdict.strip().lower().replace(" ", "_").replace("-", "_")

        failures: list[dict[str, Any]] = []

        if agent_verdict is None:
            score = 0.0
            match_type = "extraction_failed"
            failures.append({
                "type": "verdict_extraction_failed",
                "severity": "critical",
                "evidence": "Could not extract verdict from final_report.md",
                "affected_element": "final_report.md",
            })
        elif not gt_verdict:
            score = 0.0
            match_type = "no_ground_truth"
            failures.append({
                "type": "missing_ground_truth",
                "severity": "critical",
                "evidence": "No verdict found in ground truth fixture",
                "affected_element": "gt_verdict.json",
            })
        else:
            score, match_type = _compute_verdict_score(agent_verdict, gt_verdict)
            if match_type == "mismatch":
                failures.append({
                    "type": "verdict_mismatch",
                    "severity": "critical",
                    "evidence": f"Agent verdict '{agent_verdict}' != GT verdict '{gt_verdict}'",
                    "affected_element": gt_verdict,
                })

        return ScorerResult(
            metric_name="verdict_accuracy",
            score=score,
            confidence=1.0 if agent_verdict is not None and gt_verdict else 0.0,
            passed=score >= self.threshold,
            threshold=self.threshold,
            failures=failures,
            evidence={
                "agent_verdict": agent_verdict,
                "expected_verdict": gt_verdict,
                "match_type": match_type,
                "score": score,
            },
            scorer_type="deterministic",
        )