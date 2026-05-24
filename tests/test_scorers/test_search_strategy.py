"""Tests for Search Strategy Adequacy scorer."""

import pytest

from src.novelty_checker.evaluation.scorers.tier2.search_strategy import (
    SearchStrategyMetric,
    _extract_cpc_codes,
)


class TestExtractCpcCodes:
    def test_basic_codes(self):
        text = "Search CPC codes: H02N2/18, H04W84/18, H01G11/00"
        codes = _extract_cpc_codes(text)
        assert "H02N2/18" in codes
        assert "H04W84/18" in codes

    def test_no_codes(self):
        codes = _extract_cpc_codes("No classification codes here")
        assert len(codes) == 0


class TestSearchStrategyMetric:
    def test_full_strategy(self, sample_eval_trace, sample_ground_truth, tmp_session):
        """Sample trace has keyword search, semantic search, 4 queries, citation researcher."""
        metric = SearchStrategyMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.evidence["checklist"]["patent_search"] is True
        assert result.evidence["checklist"]["semantic_search"] is True
        assert result.evidence["checklist"]["min_queries"] is True  # 4 >= 3
        assert result.evidence["total"] == 8

    def test_no_search_queries(self, sample_ground_truth, tmp_session):
        trace = {"telemetry": {"search_queries": [], "total_rounds": 0}, "stage_summary": {}, "checklist": {}}
        metric = SearchStrategyMetric()
        result = metric.score_standalone(trace, sample_ground_truth, tmp_session)
        assert result.score == 0.0
        assert result.confidence == 0.3

    def test_partial_strategy(self, sample_ground_truth, tmp_session):
        trace = {
            "telemetry": {
                "search_queries": [
                    {"tool_name": "patent_keyword_search", "args": {"query": "test"}},
                ],
                "total_rounds": 0,
            },
            "stage_summary": {},
            "checklist": {},
        }
        metric = SearchStrategyMetric()
        result = metric.score_standalone(trace, sample_ground_truth, tmp_session)
        # Only patent_search passes (1 of 8)
        assert result.score == pytest.approx(1 / 8, abs=0.01)

    def test_checklist_has_8_items(self, sample_eval_trace, sample_ground_truth, tmp_session):
        metric = SearchStrategyMetric()
        result = metric.score_standalone(
            sample_eval_trace, sample_ground_truth, tmp_session
        )
        assert result.evidence["total"] == 8
        assert len(result.evidence["checklist"]) == 8

    def test_think_tool_from_stage_summary(self, sample_ground_truth, tmp_session):
        trace = {
            "telemetry": {"search_queries": [], "total_rounds": 3},
            "stage_summary": {
                "AUTONOMOUS_RESEARCH": {
                    "tool_calls_by_name": {"think_tool": 2, "evaluate_coverage": 1, "save_round_findings": 3}
                }
            },
            "checklist": {},
        }
        metric = SearchStrategyMetric()
        result = metric.score_standalone(trace, sample_ground_truth, tmp_session)
        assert result.evidence["checklist"]["think_tool_used"] is True
        assert result.evidence["checklist"]["coverage_evaluated"] is True
        assert result.evidence["checklist"]["findings_persisted"] is True
        assert result.evidence["checklist"]["min_rounds"] is True

    def test_threshold_is_0625(self):
        metric = SearchStrategyMetric()
        assert metric.threshold == 0.625
