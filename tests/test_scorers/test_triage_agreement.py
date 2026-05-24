"""Tests for Triage Agreement scorer."""

import json

import pytest

from src.novelty_checker.evaluation.scorers.tier2.triage_agreement import (
    TriageAgreementMetric,
    _compute_cohens_kappa,
)


class TestCohensKappa:
    def test_perfect_agreement(self):
        labels_a = ["A", "B", "C", "A", "B"]
        labels_b = ["A", "B", "C", "A", "B"]
        assert _compute_cohens_kappa(labels_a, labels_b) == 1.0

    def test_no_agreement(self):
        labels_a = ["A", "A", "A"]
        labels_b = ["B", "B", "B"]
        kappa = _compute_cohens_kappa(labels_a, labels_b)
        assert kappa <= 0.0  # no better than chance

    def test_partial_agreement(self):
        labels_a = ["A", "B", "C", "A"]
        labels_b = ["A", "B", "B", "C"]
        kappa = _compute_cohens_kappa(labels_a, labels_b)
        assert 0.0 < kappa < 1.0

    def test_empty_lists(self):
        assert _compute_cohens_kappa([], []) == 0.0


class TestTriageAgreementMetric:
    def test_perfect_agreement(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        agent_refs = [
            {"publication_number": "US9924896B2", "triage_label": "A"},
            {"publication_number": "US10234567B1", "triage_label": "A"},
            {"publication_number": "EP3456789A1", "triage_label": "B"},
        ]
        write_session_artifacts(findings_json=json.dumps(agent_refs))

        metric = TriageAgreementMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.evidence["agreement_rate"] == 1.0
        assert result.evidence["cohens_kappa"] == 1.0
        assert result.evidence["a_ref_f1"] == 1.0
        assert result.evidence["a_ref_precision"] == 1.0
        assert result.evidence["a_ref_recall"] == 1.0

    def test_no_shared_refs(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        agent_refs = [
            {"publication_number": "US99999999B2", "triage_label": "A"},
        ]
        write_session_artifacts(findings_json=json.dumps(agent_refs))

        metric = TriageAgreementMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.score == 0.0
        assert result.confidence == 0.0

    def test_disagreement(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        # Agent assigns different triage labels
        agent_refs = [
            {"publication_number": "US9924896B2", "triage_label": "C"},  # GT says A
            {"publication_number": "US10234567B1", "triage_label": "C"},  # GT says A
            {"publication_number": "EP3456789A1", "triage_label": "C"},   # GT says B
        ]
        write_session_artifacts(findings_json=json.dumps(agent_refs))

        metric = TriageAgreementMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.evidence["agreement_rate"] == 0.0
        assert len(result.failures) > 0

    def test_label_key_variant(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        """Agent uses 'label' instead of 'triage_label' — should still work."""
        agent_refs = [
            {"ref_id": "US9924896B2", "label": "A"},
            {"ref_id": "US10234567B1", "label": "A"},
        ]
        write_session_artifacts(findings_json=json.dumps(agent_refs))

        metric = TriageAgreementMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.evidence["shared_count"] == 2
        assert result.evidence["agreement_rate"] == 1.0
