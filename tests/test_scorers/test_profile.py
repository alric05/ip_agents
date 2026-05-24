"""Tests for ScoringProfile aggregator."""

import json

import pytest

from src.novelty_checker.evaluation.scorers._base import ScorerResult
from src.novelty_checker.evaluation.scorers.profile import ScoringProfile


def _make_result(metric_name: str, score: float, threshold: float = 0.5) -> ScorerResult:
    return ScorerResult(
        metric_name=metric_name,
        score=score,
        confidence=1.0,
        passed=score >= threshold,
        threshold=threshold,
        failures=[],
        evidence={},
        scorer_type="deterministic",
    )


def _make_all_gate_results(overrides: dict[str, float] | None = None) -> list[ScorerResult]:
    """Create ScorerResults for all alpha gate metrics with passing scores."""
    defaults = {
        "prior_art_hit_rate": 0.80,
        "prior_art_recall": 0.60,
        "verdict_accuracy": 0.70,
        "feature_precision": 0.80,
        "feature_recall": 0.75,
        "tool_error_rate": 0.95,
        "report_section_completeness": 1.0,
    }
    if overrides:
        defaults.update(overrides)
    return [_make_result(name, score) for name, score in defaults.items()]


class TestScoringProfile:
    def test_alpha_all_pass(self):
        results = {"case_001": _make_all_gate_results()}
        profile = ScoringProfile.from_results(results)
        assert profile.alpha_passed is True

    def test_alpha_fails_one_gate(self):
        results = {
            "case_001": _make_all_gate_results({"prior_art_recall": 0.20}),
        }
        profile = ScoringProfile.from_results(results)
        assert profile.alpha_passed is False
        assert profile.gate_result["prior_art_recall"] is False

    def test_alpha_fails_hit_rate(self):
        results = {
            "case_001": _make_all_gate_results({"prior_art_hit_rate": 0.0}),
        }
        profile = ScoringProfile.from_results(results)
        assert profile.alpha_passed is False
        assert profile.gate_result["prior_art_hit_rate"] is False

    def test_alpha_fails_error_rate(self):
        results = {
            "case_001": _make_all_gate_results({"tool_error_rate": 0.80}),
        }
        profile = ScoringProfile.from_results(results)
        assert profile.alpha_passed is False
        assert profile.gate_result["tool_error_rate"] is False

    def test_alpha_fails_report_completeness(self):
        results = {
            "case_001": _make_all_gate_results({"report_section_completeness": 0.9}),
        }
        profile = ScoringProfile.from_results(results)
        assert profile.alpha_passed is False

    def test_suite_summary_averages(self):
        results = {
            "case_001": [_make_result("prior_art_recall", 0.80)],
            "case_002": [_make_result("prior_art_recall", 0.60)],
        }
        profile = ScoringProfile.from_results(results)
        assert profile.suite_summary["prior_art_recall"] == pytest.approx(0.70)

    def test_to_json(self, tmp_path):
        results = {"case_001": _make_all_gate_results()}
        profile = ScoringProfile.from_results(results)
        path = tmp_path / "results.json"
        profile.to_json(path)
        assert path.exists()

        data = json.loads(path.read_text())
        assert "suite_summary" in data
        assert data["alpha_passed"] is True

    def test_summary_table(self):
        results = {
            "case_001": [
                _make_result("prior_art_recall", 0.80, 0.40),
                _make_result("verdict_accuracy", 0.50, 0.60),
            ],
        }
        profile = ScoringProfile.from_results(results)
        table = profile.summary_table()
        assert "prior_art_recall" in table
        assert "FAIL" in table

    def test_empty_results(self):
        profile = ScoringProfile.from_results({})
        assert profile.alpha_passed is False
        assert profile.suite_summary == {}

    def test_missing_gate_metric(self):
        """If a gate metric wasn't computed, gate fails."""
        results = {
            "case_001": [
                _make_result("verdict_accuracy", 0.90, 0.60),
                # Missing all other gate metrics
            ],
        }
        profile = ScoringProfile.from_results(results)
        assert profile.alpha_passed is False
