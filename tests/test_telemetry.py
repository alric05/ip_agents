"""Tests for telemetry functionality (Phase 2)."""

import json
import tempfile
from pathlib import Path

from src.novelty_checker.observability.telemetry import (
    ResearchTelemetry,
    TelemetryMiddleware,
    ToolCallMetric,
    RoundMetric,
)


def test_telemetry_initialization():
    """Test that telemetry initializes correctly."""
    telemetry = ResearchTelemetry(session_id="test-session")

    assert telemetry.session_id == "test-session"
    assert telemetry.output_path is None
    assert len(telemetry.tool_calls) == 0
    assert len(telemetry.rounds) == 0
    print("✅ test_telemetry_initialization passed")


def test_tool_call_logging():
    """Test that tool calls are logged correctly."""
    telemetry = ResearchTelemetry(session_id="test-session")

    telemetry.log_tool_call(
        tool_name="patent_keyword_search",
        duration_ms=1500.0,
        success=True,
        error=None,
    )

    assert len(telemetry.tool_calls) == 1
    metric = telemetry.tool_calls[0]
    assert metric.tool_name == "patent_keyword_search"
    assert metric.duration_ms == 1500.0
    assert metric.success is True
    assert metric.error is None
    print("✅ test_tool_call_logging passed")


def test_failed_tool_call_logging():
    """Test that failed tool calls are logged with errors."""
    telemetry = ResearchTelemetry(session_id="test-session")

    telemetry.log_tool_call(
        tool_name="patent_keyword_search",
        duration_ms=500.0,
        success=False,
        error="API timeout",
    )

    assert len(telemetry.tool_calls) == 1
    metric = telemetry.tool_calls[0]
    assert metric.success is False
    assert metric.error == "API timeout"
    print("✅ test_failed_tool_call_logging passed")


def test_round_tracking():
    """Test that research rounds are tracked correctly."""
    telemetry = ResearchTelemetry(session_id="test-session")

    telemetry.start_round(1)
    assert 1 in telemetry.rounds
    assert telemetry.current_round == 1

    telemetry.end_round(
        round_number=1,
        new_references_count=5,
        total_references_count=5,
        coverage_percentage=25.0,
    )

    round_metric = telemetry.rounds[1]
    assert round_metric.round_number == 1
    assert round_metric.new_references_count == 5
    assert round_metric.total_references_count == 5
    assert round_metric.coverage_percentage == 25.0
    assert round_metric.end_time is not None
    assert round_metric.duration_seconds is not None
    print("✅ test_round_tracking passed")


def test_round_tool_call_counts():
    """Test that tool calls are counted per round."""
    telemetry = ResearchTelemetry(session_id="test-session")

    telemetry.start_round(1)

    # Successful call
    telemetry.log_tool_call("tool1", 100.0, success=True)
    # Failed call
    telemetry.log_tool_call("tool2", 200.0, success=False, error="Error")
    # Another successful call
    telemetry.log_tool_call("tool3", 150.0, success=True)

    round_metric = telemetry.rounds[1]
    assert round_metric.tool_calls_count == 3
    assert round_metric.failed_tool_calls == 1
    print("✅ test_round_tool_call_counts passed")


def test_telemetry_persistence():
    """Test that telemetry is persisted to JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "telemetry.json"

        telemetry = ResearchTelemetry(
            session_id="test-session",
            output_path=output_path,
        )

        telemetry.start_round(1)
        telemetry.log_tool_call("tool1", 100.0, success=True)
        telemetry.end_round(1, new_references_count=3)

        # File should be created
        assert output_path.exists()

        # Verify content
        with open(output_path, 'r') as f:
            data = json.load(f)

        assert data["session_id"] == "test-session"
        assert len(data["rounds"]) == 1
        assert len(data["tool_calls"]) == 1
        assert "summary" in data
        print("✅ test_telemetry_persistence passed")


def test_telemetry_summary():
    """Test that summary statistics are calculated correctly."""
    telemetry = ResearchTelemetry(session_id="test-session")

    telemetry.start_round(1)
    telemetry.log_tool_call("tool1", 100.0, success=True)
    telemetry.log_tool_call("tool2", 200.0, success=False, error="Err")
    telemetry.log_tool_call("tool3", 150.0, success=True)
    telemetry.end_round(1, new_references_count=5)

    summary = telemetry.get_summary()

    assert summary["session_id"] == "test-session"
    assert summary["total_rounds"] == 1
    assert summary["total_tool_calls"] == 3
    assert summary["failed_tool_calls"] == 1
    assert summary["success_rate"] == 2/3  # 2 successful out of 3
    assert summary["avg_tool_duration_ms"] == 150.0  # (100+200+150)/3
    print("✅ test_telemetry_summary passed")


def test_middleware_logs_successful_calls():
    """Test that middleware logs successful tool calls via _log_from_result."""
    telemetry = ResearchTelemetry(session_id="test-session")
    middleware = TelemetryMiddleware(telemetry)

    # Use _log_from_result directly (the core logic called by wrap_tool_call)
    middleware._log_from_result(
        tool_name="patent_keyword_search",
        result="Found 5 patents",
        duration_ms=1200.0,
        runtime=None,
    )

    assert len(telemetry.tool_calls) == 1
    metric = telemetry.tool_calls[0]
    assert metric.tool_name == "patent_keyword_search"
    assert metric.success is True
    print("✅ test_middleware_logs_successful_calls passed")


def test_middleware_detects_failures():
    """Test that middleware detects failed tool calls via _log_from_result."""
    telemetry = ResearchTelemetry(session_id="test-session")
    middleware = TelemetryMiddleware(telemetry)

    # Use _log_from_result with a failure marker (starts with ❌)
    middleware._log_from_result(
        tool_name="patent_keyword_search",
        result="❌ API timeout after 60s",
        duration_ms=500.0,
        runtime=None,
    )

    assert len(telemetry.tool_calls) == 1
    metric = telemetry.tool_calls[0]
    assert metric.success is False
    assert "API timeout" in metric.error
    print("✅ test_middleware_detects_failures passed")


if __name__ == "__main__":
    # Run all tests
    test_telemetry_initialization()
    test_tool_call_logging()
    test_failed_tool_call_logging()
    test_round_tracking()
    test_round_tool_call_counts()
    test_telemetry_persistence()
    test_telemetry_summary()
    test_middleware_logs_successful_calls()
    test_middleware_detects_failures()

    print("\n🎉 All telemetry tests passed!")
