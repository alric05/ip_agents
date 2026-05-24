"""Tests for Feature Coverage Accuracy scorer."""

import pytest

from src.novelty_checker.evaluation.scorers.tier2.feature_coverage_accuracy import (
    FeatureCoverageAccuracyMetric,
)


REPORT_WITH_COVERAGE = """\
# Report

## Feature Coverage

| Reference | F1 | F2 | F3 |
|-----------|----|----|-----|
| US9924896B2 | Y | N | Y1 |
| US10234567B1 | Y | Y | N |
"""

REPORT_NO_COVERAGE = """\
# Report

## Summary
No coverage table here.
"""


class TestFeatureCoverageAccuracyMetric:
    def test_no_report(
        self, tmp_session, sample_eval_trace, sample_ground_truth
    ):
        metric = FeatureCoverageAccuracyMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.score == 0.0

    def test_no_gt_ab_refs(
        self, tmp_session, sample_eval_trace, write_session_artifacts
    ):
        gt = {
            "references": {"references": [{"publication_number": "US11111111B2", "triage_label": "C"}]},
            "features": [],
            "verdict": {},
        }
        write_session_artifacts(final_report=REPORT_WITH_COVERAGE)
        metric = FeatureCoverageAccuracyMetric()
        result = metric.score_standalone(sample_eval_trace, gt, tmp_session)
        assert result.score == 1.0
        assert result.confidence == 0.0

    def test_no_overlap(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        write_session_artifacts(final_report=REPORT_NO_COVERAGE)
        metric = FeatureCoverageAccuracyMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        # No coverage cells found
        assert result.score == 0.0


REPORT_WITH_MULTIPLE_TABLES = """\
# Report

## 4. Feature Matrix

| Publication Number | Ref Type | Relevance | F1 | F2 | F3 |
|--------------------|----------|-----------|----|----|-----|
| US9924896B2 | Patent | A | Y | N | Y1 |

## 6. Patents Record View

### Patent Record: US9924896B2

| Field | Details |
|-------|---------|
| Publication Number | US9924896B2 |
| Title | Example title |
| Assignee | Example assignee |

## 8. Landscape Overview

| Publication Number | Type | Triage | Title |
|--------------------|------|--------|-------|
| US9924896B2 | Patent | A | Example |
"""


class TestMultiTableParsing:
    """Regression: the Feature Matrix table must win over later ancillary
    tables that list the same ref with different columns (C19904 bug)."""

    def test_f1_does_not_match_f10_or_f11(
        self, tmp_session, sample_eval_trace, write_session_artifacts
    ):
        """Regression: substring matching used to make GT F10/F11 silently
        collide with agent F1 (since 'f1' in 'f10' → True). Now uses
        regex exact-F-id matching."""
        report = (
            "# R\n\n## Feature Matrix\n\n"
            "| Publication Number | F1 |\n"
            "|--------------------|----|\n"
            "| US9924896B2 | Y |\n"
        )
        gt = {
            "references": {
                "references": [
                    {
                        "publication_number": "US9924896B2",
                        "triage_label": "A",
                        # Agent has F1=Y (matches), but GT also has F10/F11
                        # which used to match F1 via substring. They must
                        # NOT match and therefore not inflate total_cells.
                        "feature_coverage": {"F1": "Y", "F10": "N", "F11": "N"},
                    }
                ]
            },
            "features": [],
            "verdict": {},
        }
        write_session_artifacts(final_report=report)
        metric = FeatureCoverageAccuracyMetric()
        result = metric.score_standalone(sample_eval_trace, gt, tmp_session)
        # Only F1 has an overlap; F10/F11 cannot match agent's F1 column.
        assert result.evidence["total_cells"] == 1
        assert result.evidence["matching_cells"] == 1

    def test_feature_matrix_wins_over_landscape_table(
        self, tmp_session, sample_eval_trace, write_session_artifacts
    ):
        gt = {
            "references": {
                "references": [
                    {
                        "publication_number": "US9924896B2",
                        "triage_label": "A",
                        "feature_coverage": {"F1": "Y", "F2": "N", "F3": "Y1"},
                    }
                ]
            },
            "features": [],
            "verdict": {},
        }
        write_session_artifacts(final_report=REPORT_WITH_MULTIPLE_TABLES)
        metric = FeatureCoverageAccuracyMetric()
        result = metric.score_standalone(sample_eval_trace, gt, tmp_session)
        # All 3 cells match GT (Y/N/Y1) — Feature Matrix table wins
        assert result.score == 1.0
        assert result.evidence["total_cells"] >= 3
        assert result.evidence["matching_cells"] >= 3
