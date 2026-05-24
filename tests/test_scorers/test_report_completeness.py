"""Tests for Report Section Completeness scorer."""

import pytest

from src.novelty_checker.evaluation.scorers.tier2.report_completeness import (
    ReportCompletenessMetric,
)


FULL_REPORT = """\
# Novelty Assessment Report

## Executive Summary
The invention is partially novel.

## Scope
The invention relates to piezoelectric energy harvesting.

## Feature Matrix
| ID | Feature | Core |
|----|---------|------|
| F1 | Energy harvesting | Y |

## Search Strategy
We searched patent and semantic databases.

## Prior Art Analysis
US9924896B2 is a relevant reference.

## Feature Coverage
| Ref | F1 | F2 |
|-----|----|----|
| US9924896B2 | Y | N |

## Novelty Assessment
The invention is partially novel.

## Risk Assessment
Medium risk of blocking prior art.

## Recommendations
Consider amending claims to focus on novel aspects.

## Limitations
Search was limited to English-language patents.

## References
1. US9924896B2 - Energy harvesting sensor system
"""

PARTIAL_REPORT = """\
# Novelty Assessment Report

## Executive Summary
The invention is partially novel.

## Prior Art Analysis
US9924896B2 is relevant.

## Verdict
Partially novel.
"""


class TestReportCompletenessMetric:
    def test_full_report(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        write_session_artifacts(final_report=FULL_REPORT)
        metric = ReportCompletenessMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.score == 1.0
        assert result.passed is True
        assert result.evidence["sections_found"] == 11
        assert result.evidence["missing_sections"] == []

    def test_partial_report(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        write_session_artifacts(final_report=PARTIAL_REPORT)
        metric = ReportCompletenessMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.score < 1.0
        assert result.passed is False
        assert len(result.evidence["missing_sections"]) > 0

    def test_no_report(
        self, tmp_session, sample_eval_trace, sample_ground_truth
    ):
        metric = ReportCompletenessMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.score == 0.0
        assert result.failures[0]["type"] == "no_report"

    def test_alias_matching(
        self, tmp_session, sample_eval_trace, sample_ground_truth, write_session_artifacts
    ):
        """Section aliases like 'Summary' should match 'Executive Summary'."""
        report = "## Summary\nSome text\n## Prior Art Findings\nMore text\n"
        write_session_artifacts(final_report=report)
        metric = ReportCompletenessMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        found = result.evidence["found_sections"]
        assert "executive summary" in found
        assert "prior art analysis" in found
