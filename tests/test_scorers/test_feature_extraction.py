"""Tests for Feature Precision and Feature Recall scorers."""

import pytest

from src.novelty_checker.evaluation.scorers._loader import parse_features_md
from src.novelty_checker.evaluation.scorers.tier1.feature_extraction import (
    FeaturePrecisionMetric,
    FeatureRecallMetric,
)


FEATURES_MD_ALL_MATCH = """\
# Feature Matrix

| ID | Feature Name | Type | Core? | Keywords |
|----|-------------|------|-------|----------|
| F1 | Piezoelectric energy harvesting module | Hardware | Y | piezo, energy, vibration |
| F2 | Wireless sensor node with adaptive duty cycling | Software | Y | IoT, sensor, duty cycle |
| F3 | Energy storage supercapacitor array | Hardware | N | supercapacitor, energy, storage |
| F4 | Low-power wake-up receiver | Hardware | N | wake-up, radio, low-power |
"""

FEATURES_MD_PARTIAL = """\
# Feature Matrix

| ID | Feature Name | Type | Core? | Keywords |
|----|-------------|------|-------|----------|
| F1 | Piezoelectric energy harvesting module | Hardware | Y | piezo, energy |
| F5 | Machine learning anomaly detection | Software | N | ML, anomaly |
"""


class TestParseFeaturesmd:
    def test_parses_table(self):
        features = parse_features_md(FEATURES_MD_ALL_MATCH)
        assert len(features) == 4
        assert features[0]["id"] == "F1"
        assert features[0]["feature_name"] == "Piezoelectric energy harvesting module"

    def test_no_table(self):
        features = parse_features_md("No table here\nJust text")
        assert features == []

    def test_empty_content(self):
        features = parse_features_md("")
        assert features == []


class TestFeaturePrecisionMetric:
    def test_all_features_matched(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        write_session_artifacts(features_md=FEATURES_MD_ALL_MATCH)
        metric = FeaturePrecisionMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.evidence["precision"] == 1.0
        assert result.passed is True

    def test_spurious_features_lower_precision(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        """Agent has 6 features (4 matching + 2 spurious). Precision = 4/6."""
        more_md = """\
# Feature Matrix

| ID | Feature Name | Type | Core? | Keywords |
|----|-------------|------|-------|----------|
| F1 | Piezoelectric energy harvesting module | Hardware | Y | piezo, energy, vibration |
| F2 | Wireless sensor node with adaptive duty cycling | Software | Y | IoT, sensor, duty cycle |
| F3 | Energy storage supercapacitor array | Hardware | N | supercapacitor, energy, storage |
| F4 | Low-power wake-up receiver | Hardware | N | wake-up, radio, low-power |
| F5 | Blockchain-based data integrity verification | Software | N | blockchain, hash, ledger |
| F6 | Quantum-resistant encryption module | Software | N | quantum, encryption, post-quantum |
"""
        write_session_artifacts(features_md=more_md)
        metric = FeaturePrecisionMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.evidence["precision"] == pytest.approx(4 / 6, abs=0.01)
        assert result.evidence["matched_count"] == 4
        assert len(result.evidence["unmatched_agent_features"]) == 2

    def test_no_agent_features(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        write_session_artifacts(features_md="# Features\nNo table here.")
        metric = FeaturePrecisionMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.score == 0.0
        assert result.passed is False

    def test_no_gt_features(
        self, tmp_session, sample_eval_trace, write_session_artifacts
    ):
        write_session_artifacts(features_md=FEATURES_MD_ALL_MATCH)
        gt = {"features": [], "references": {}, "verdict": {}}
        metric = FeaturePrecisionMetric()
        result = metric.score_standalone(sample_eval_trace, gt, tmp_session)
        assert result.score == 1.0
        assert result.confidence == 0.0

    def test_threshold_is_070(self):
        metric = FeaturePrecisionMetric()
        assert metric.threshold == 0.70


class TestFeatureRecallMetric:
    def test_all_features_matched(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        write_session_artifacts(features_md=FEATURES_MD_ALL_MATCH)
        metric = FeatureRecallMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.evidence["recall"] == 1.0
        assert result.passed is True

    def test_partial_recall(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        write_session_artifacts(features_md=FEATURES_MD_PARTIAL)
        metric = FeatureRecallMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        # Only F1 matches. F1 is core (weight 2), F2 is core (weight 2), F3+F4 non-core (weight 1 each)
        # Weighted total = 2+2+1+1 = 6, matched = 2 (F1 core), recall = 2/6 ≈ 0.333
        assert result.evidence["recall"] < 0.5
        assert result.passed is False

    def test_core_features_weighted_2x(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        """Matching only core features gives better recall due to 2x weighting."""
        core_only_md = """\
# Feature Matrix

| ID | Feature Name | Type | Core? | Keywords |
|----|-------------|------|-------|----------|
| F1 | Piezoelectric energy harvesting module | Hardware | Y | piezo, energy, vibration |
| F2 | Wireless sensor node with adaptive duty cycling | Software | Y | IoT, sensor, duty cycle |
"""
        write_session_artifacts(features_md=core_only_md)
        metric = FeatureRecallMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        # Matched: 2 core (weight 2 each) = 4. Total: 2 core (4) + 2 non-core (2) = 6
        # Recall = 4/6 ≈ 0.667
        assert result.evidence["recall"] == pytest.approx(4 / 6, abs=0.01)
        assert result.evidence["matched_core"] == 2
        assert result.evidence["core_gt_count"] == 2

    def test_no_agent_features(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        write_session_artifacts(features_md="# Features\nNo table here.")
        metric = FeatureRecallMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.score == 0.0
        assert result.passed is False

    def test_different_order_same_features(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        """Agent features in reversed order should produce identical scores."""
        reversed_md = """\
# Feature Matrix

| ID | Feature Name | Type | Core? | Keywords |
|----|-------------|------|-------|----------|
| F4 | Low-power wake-up receiver | Hardware | N | wake-up, radio, low-power |
| F3 | Energy storage supercapacitor array | Hardware | N | supercapacitor, energy, storage |
| F2 | Wireless sensor node with adaptive duty cycling | Software | Y | IoT, sensor, duty cycle |
| F1 | Piezoelectric energy harvesting module | Hardware | Y | piezo, energy, vibration |
"""
        write_session_artifacts(features_md=reversed_md)
        metric = FeatureRecallMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.evidence["recall"] == 1.0
        assert result.evidence["matched_count"] == 4

    def test_agent_fewer_features_than_gt(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        """Agent has 2 correct features (1 core F1, 1 non-core F3), GT has 4."""
        fewer_md = """\
# Feature Matrix

| ID | Feature Name | Type | Core? | Keywords |
|----|-------------|------|-------|----------|
| F1 | Piezoelectric energy harvesting module | Hardware | Y | piezo, energy, vibration |
| F3 | Energy storage supercapacitor array | Hardware | N | supercapacitor, energy, storage |
"""
        write_session_artifacts(features_md=fewer_md)
        metric = FeatureRecallMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        # Matched: 1 core (2) + 1 non-core (1) = 3. Total = 6. Recall = 3/6 = 0.5
        assert result.evidence["recall"] == pytest.approx(0.5)
        assert result.evidence["matched_count"] == 2
        assert len(result.failures) == 2  # 2 missed GT features

    def test_threshold_is_060(self):
        metric = FeatureRecallMetric()
        assert metric.threshold == 0.60
