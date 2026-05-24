"""Tests for Prior Art Hit Rate scorer."""

import json

import pytest

from src.novelty_checker.evaluation.scorers.tier1.prior_art_hit_rate import (
    PriorArtHitRateMetric,
)


class TestPriorArtHitRateMetric:
    def test_hit_found(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        agent_refs = [
            {"publication_number": "US9924896B2", "triage_label": "A"},
        ]
        write_session_artifacts(findings_json=json.dumps(agent_refs))

        metric = PriorArtHitRateMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.score == 1.0
        assert result.passed is True
        assert result.evidence["hit"] is True

    def test_no_hit(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        agent_refs = [
            {"publication_number": "US99999999B2", "triage_label": "C"},
        ]
        write_session_artifacts(findings_json=json.dumps(agent_refs))

        metric = PriorArtHitRateMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.score == 0.0
        assert result.passed is False
        assert result.evidence["hit"] is False
        assert result.failures[0]["type"] == "no_a_ref_found"

    def test_no_agent_refs(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        write_session_artifacts(findings_json="[]")

        metric = PriorArtHitRateMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.score == 0.0

    def test_no_gt_a_refs(
        self, tmp_session, sample_eval_trace, write_session_artifacts
    ):
        gt = {
            "references": {
                "references": [
                    {"publication_number": "EP3456789A1", "triage_label": "B"},
                ]
            },
            "features": [],
            "verdict": {},
        }
        write_session_artifacts(findings_json="[]")

        metric = PriorArtHitRateMetric()
        result = metric.score_standalone(sample_eval_trace, gt, tmp_session)
        assert result.score == 1.0
        assert result.confidence == 0.0

    def test_b_ref_does_not_count(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        """Only finding B-level refs doesn't count as a hit."""
        agent_refs = [
            {"publication_number": "EP3456789A1", "triage_label": "B"},
            {"publication_number": "WO2020/123456A1", "triage_label": "B"},
        ]
        write_session_artifacts(findings_json=json.dumps(agent_refs))

        metric = PriorArtHitRateMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.score == 0.0
        assert result.evidence["hit"] is False
