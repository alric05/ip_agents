"""Tests for Tier-3 operational scorers."""

import pytest

from src.novelty_checker.evaluation.scorers.tier3.operational import (
    CostPerRunMetric,
    LatencyMetric,
    ResearchRoundsMetric,
    SearchReproducibilityMetric,
    TokenEfficiencyMetric,
    ToolErrorRateMetric,
    ToolInvocationMetric,
)


class TestCostPerRunMetric:
    def test_low_cost(self, sample_eval_trace, sample_ground_truth, tmp_session):
        metric = CostPerRunMetric(max_cost_usd=5.0)
        result = metric.score_standalone(sample_eval_trace, sample_ground_truth, tmp_session)
        # Cost is $1.25, max is $5.0, so score = 1 - 1.25/5.0 = 0.75
        assert result.score == pytest.approx(0.75)
        assert result.evidence["estimated_cost_usd"] == 1.25

    def test_high_cost(self, sample_ground_truth, tmp_session):
        trace = {"telemetry": {"token_usage": {"cumulative": {"estimated_cost_usd": 10.0}}}}
        metric = CostPerRunMetric(max_cost_usd=5.0)
        result = metric.score_standalone(trace, sample_ground_truth, tmp_session)
        assert result.score == 0.0

    def test_zero_cost(self, sample_ground_truth, tmp_session):
        trace = {"telemetry": {"token_usage": {"cumulative": {"estimated_cost_usd": 0.0}}}}
        metric = CostPerRunMetric()
        result = metric.score_standalone(trace, sample_ground_truth, tmp_session)
        assert result.score == 1.0


class TestLatencyMetric:
    def test_normal_latency(self, sample_eval_trace, sample_ground_truth, tmp_session):
        metric = LatencyMetric(max_duration_seconds=600.0)
        result = metric.score_standalone(sample_eval_trace, sample_ground_truth, tmp_session)
        # Duration 120.5s, max 600s -> score = 1 - 120.5/600 ≈ 0.7992
        assert 0.7 < result.score < 0.85
        assert result.evidence["total_duration_seconds"] == 120.5

    def test_per_stage_breakdown(self, sample_eval_trace, sample_ground_truth, tmp_session):
        metric = LatencyMetric()
        result = metric.score_standalone(sample_eval_trace, sample_ground_truth, tmp_session)
        assert "per_stage_seconds" in result.evidence
        assert "AUTONOMOUS_RESEARCH" in result.evidence["per_stage_seconds"]


class TestTokenEfficiencyMetric:
    def test_with_telemetry(self, sample_eval_trace, sample_ground_truth, tmp_session):
        metric = TokenEfficiencyMetric()
        result = metric.score_standalone(sample_eval_trace, sample_ground_truth, tmp_session)
        assert 0.0 <= result.score <= 1.0
        assert result.evidence["total_tokens"] == 50000


class TestToolErrorRateMetric:
    def test_low_error_rate(self, sample_eval_trace, sample_ground_truth, tmp_session):
        metric = ToolErrorRateMetric()
        result = metric.score_standalone(sample_eval_trace, sample_ground_truth, tmp_session)
        # 1 failure out of 20 -> error_rate = 0.05, score = 0.95
        assert result.score == pytest.approx(0.95)
        assert result.evidence["error_rate"] == pytest.approx(0.05)

    def test_no_tool_calls(self, sample_ground_truth, tmp_session):
        trace = {"telemetry": {"total_tool_calls": 0, "failed_tool_calls": 0}}
        metric = ToolErrorRateMetric()
        result = metric.score_standalone(trace, sample_ground_truth, tmp_session)
        assert result.score == 1.0
        assert result.confidence == 0.3


class TestSearchReproducibilityMetric:
    def test_all_complete(self, sample_eval_trace, sample_ground_truth, tmp_session):
        metric = SearchReproducibilityMetric()
        result = metric.score_standalone(sample_eval_trace, sample_ground_truth, tmp_session)
        assert result.score == 1.0
        assert result.evidence["complete_queries"] == 4

    def test_incomplete_args(self, sample_ground_truth, tmp_session):
        trace = {
            "telemetry": {
                "search_queries": [
                    {"tool_name": "patent_keyword_search", "args": {"query": "test"}},
                    {"tool_name": "semantic_patent_search", "args": {}},
                ]
            }
        }
        metric = SearchReproducibilityMetric()
        result = metric.score_standalone(trace, sample_ground_truth, tmp_session)
        assert result.score == 0.5

    def test_no_queries(self, sample_ground_truth, tmp_session):
        trace = {"telemetry": {"search_queries": []}}
        metric = SearchReproducibilityMetric()
        result = metric.score_standalone(trace, sample_ground_truth, tmp_session)
        assert result.score == 0.0
        assert result.failures[0]["type"] == "no_search_queries"


class TestResearchRoundsMetric:
    def test_normal_rounds(self, sample_eval_trace, sample_ground_truth, tmp_session):
        # sample_eval_trace has total_rounds=3 -> score 1.0
        metric = ResearchRoundsMetric()
        result = metric.score_standalone(sample_eval_trace, sample_ground_truth, tmp_session)
        assert result.score == 1.0
        assert result.evidence["total_rounds"] == 3

    def test_zero_rounds(self, sample_ground_truth, tmp_session):
        trace = {"telemetry": {"total_rounds": 0}}
        metric = ResearchRoundsMetric()
        result = metric.score_standalone(trace, sample_ground_truth, tmp_session)
        assert result.score == 0.0
        assert result.evidence["alert"] == "no_rounds"

    def test_one_round_premature(self, sample_ground_truth, tmp_session):
        trace = {"telemetry": {"total_rounds": 1}}
        metric = ResearchRoundsMetric()
        result = metric.score_standalone(trace, sample_ground_truth, tmp_session)
        assert result.score == 0.5
        assert result.evidence["alert"] == "premature_stop"

    def test_five_rounds_max_hit(self, sample_ground_truth, tmp_session):
        trace = {"telemetry": {"total_rounds": 5}}
        metric = ResearchRoundsMetric()
        result = metric.score_standalone(trace, sample_ground_truth, tmp_session)
        assert result.score == 0.5
        assert result.evidence["alert"] == "max_rounds_hit"


class TestToolInvocationMetric:
    def test_normal_invocations(self, sample_eval_trace, sample_ground_truth, tmp_session):
        metric = ToolInvocationMetric(max_tool_calls=200)
        result = metric.score_standalone(sample_eval_trace, sample_ground_truth, tmp_session)
        assert 0.0 <= result.score <= 1.0

    def test_fallback_to_telemetry(self, sample_ground_truth, tmp_session):
        trace = {"stage_summary": {}, "telemetry": {"total_tool_calls": 50}}
        metric = ToolInvocationMetric(max_tool_calls=200)
        result = metric.score_standalone(trace, sample_ground_truth, tmp_session)
        # 1.0 - 50/200 = 0.75
        assert result.score == pytest.approx(0.75)
        assert result.evidence["total_tool_calls"] == 50
