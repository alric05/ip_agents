"""Tests for Verdict Accuracy scorer."""

import pytest

from src.novelty_checker.evaluation.scorers._loader import extract_verdict_from_report
from src.novelty_checker.evaluation.scorers.tier1.verdict_accuracy import (
    VerdictAccuracyMetric,
    _compute_verdict_score,
)


class TestComputeVerdictScore:
    def test_exact_match(self):
        score, match_type = _compute_verdict_score("novel", "novel")
        assert score == 1.0
        assert match_type == "exact"

    def test_one_step_off_is_mismatch(self):
        score, match_type = _compute_verdict_score("novel", "partially_novel")
        assert score == 0.0
        assert match_type == "mismatch"

    def test_two_steps_off_is_mismatch(self):
        score, match_type = _compute_verdict_score("novel", "not_novel")
        assert score == 0.0
        assert match_type == "mismatch"

    def test_symmetric(self):
        s1, _ = _compute_verdict_score("not_novel", "partially_novel")
        s2, _ = _compute_verdict_score("partially_novel", "not_novel")
        assert s1 == s2 == 0.0

    def test_unknown_verdict(self):
        score, match_type = _compute_verdict_score("unknown", "novel")
        assert score == 0.0
        assert match_type == "mismatch"


class TestExtractVerdictFromReport:
    def test_verdict_colon_format(self):
        report = "# Report\n\nVerdict: Novel\n\nSome text"
        assert extract_verdict_from_report(report) == "novel"

    def test_not_novel_format(self):
        report = "## Overall Assessment: not novel\n"
        assert extract_verdict_from_report(report) == "not_novel"

    def test_partially_novel_bold(self):
        report = "The conclusion is **partially novel** based on analysis."
        assert extract_verdict_from_report(report) == "partially_novel"

    def test_no_verdict_found(self):
        report = "This report has no clear verdict."
        assert extract_verdict_from_report(report) is None

    def test_conclusion_format(self):
        report = "# Conclusion\nConclusion: not_novel\nEnd."
        assert extract_verdict_from_report(report) == "not_novel"

    def test_heuristic_anticipatory(self):
        report = "US12323091B1 appears to **fully anticipate** EFVP as scoped."
        assert extract_verdict_from_report(report) == "not_novel"

    def test_heuristic_blocking_risk(self):
        report = "## Executive Summary\nNovelty risk: **Very High** (blocking risk)."
        assert extract_verdict_from_report(report) == "not_novel"

    def test_heuristic_not_novel_as_scoped(self):
        report = "The invention is not novel as scoped due to prior art."
        assert extract_verdict_from_report(report) == "not_novel"

    def test_heuristic_lacks_novelty(self):
        report = "Overall, the disclosure lacks novelty given the prior art."
        assert extract_verdict_from_report(report) == "not_novel"

    def test_heuristic_limited_novelty(self):
        report = "The invention shows limited novelty in its core aspects."
        assert extract_verdict_from_report(report) == "partially_novel"

    def test_heuristic_is_novel(self):
        report = "Based on exhaustive search, the invention is novel."
        assert extract_verdict_from_report(report) == "novel"

    def test_strict_takes_precedence_over_heuristic(self):
        """When both strict and heuristic match, strict wins."""
        report = "Verdict: novel\nBut there is blocking risk from prior art."
        assert extract_verdict_from_report(report) == "novel"


class TestVerdictAccuracyMetric:
    def test_exact_match(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        write_session_artifacts(
            final_report="## Verdict\nVerdict: partially_novel\n"
        )
        metric = VerdictAccuracyMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.score == 1.0
        assert result.passed is True
        assert result.evidence["match_type"] == "exact"

    def test_one_step_off_is_zero(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        write_session_artifacts(
            final_report="## Verdict\nVerdict: novel\n"
        )
        metric = VerdictAccuracyMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.score == 0.0
        assert result.passed is False
        assert result.evidence["match_type"] == "mismatch"

    def test_no_report(
        self, tmp_session, sample_eval_trace, sample_ground_truth
    ):
        # No final_report.md written
        metric = VerdictAccuracyMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.score == 0.0
        assert len(result.failures) > 0
        assert result.failures[0]["type"] == "verdict_extraction_failed"

    def test_threshold_is_070(self):
        metric = VerdictAccuracyMetric()
        assert metric.threshold == 0.70
