"""Tests for Prior Art Recall scorer."""

import json

import pytest

from src.novelty_checker.evaluation.scorers.tier1.prior_art_recall import (
    PriorArtRecallMetric,
)


class TestPriorArtRecallMetric:
    def test_all_a_refs_found(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        """Agent found all A-level references."""
        agent_refs = [
            {"publication_number": "US9924896B2", "triage_label": "A"},
            {"publication_number": "US10234567B1", "triage_label": "A"},
            {"publication_number": "EP3456789A1", "triage_label": "B"},
        ]
        write_session_artifacts(
            findings_json=json.dumps(agent_refs)
        )

        metric = PriorArtRecallMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.score == 1.0
        assert result.passed is True
        assert result.evidence["found_count"] == 2  # 2 A-refs matched

    def test_partial_recall(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        """Agent found 1 of 2 A-level references."""
        agent_refs = [
            {"publication_number": "US9924896B2", "triage_label": "A"},
            {"publication_number": "EP3456789A1", "triage_label": "B"},
        ]
        write_session_artifacts(
            findings_json=json.dumps(agent_refs)
        )

        metric = PriorArtRecallMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.score == pytest.approx(0.5)
        assert result.passed is True  # 0.5 >= 0.40 threshold
        assert result.evidence["missed_count"] == 1

    def test_no_refs_found(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        """Agent found no references."""
        write_session_artifacts(findings_json="[]")

        metric = PriorArtRecallMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.score == 0.0
        assert result.passed is False
        assert len(result.failures) == 2  # 2 missed A-refs

    def test_different_kind_codes_match(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        """Agent refs with different kind codes should still match."""
        agent_refs = [
            {"publication_number": "US 9,924,896 A1", "triage_label": "A"},
        ]
        write_session_artifacts(
            findings_json=json.dumps(agent_refs)
        )

        metric = PriorArtRecallMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.evidence["found_count"] == 1
        assert "US9924896" in result.evidence["found_refs"][0]["gt"]

    def test_no_gt_a_refs(
        self, tmp_session, sample_eval_trace, write_session_artifacts
    ):
        """When GT has no A-refs, score should be 1.0 with low confidence."""
        gt = {
            "references": {
                "references": [
                    {"publication_number": "EP3456789A1", "triage_label": "B"},
                    {"publication_number": "US11111111B2", "triage_label": "C"},
                ]
            },
            "features": [],
            "verdict": {},
        }
        write_session_artifacts(findings_json="[]")

        metric = PriorArtRecallMetric()
        result = metric.score_standalone(sample_eval_trace, gt, tmp_session)
        assert result.score == 1.0
        assert result.confidence == 0.0

    def test_failure_severity_all_critical(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        """All missed refs are A-level so should be critical."""
        write_session_artifacts(findings_json="[]")

        metric = PriorArtRecallMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        for f in result.failures:
            assert f["severity"] == "critical"

    def test_threshold_is_040(self):
        metric = PriorArtRecallMetric()
        assert metric.threshold == 0.40
