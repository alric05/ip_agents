"""Mocked E2E runner tests for TM knockout search."""

from __future__ import annotations

import json
from pathlib import Path

from src.tm_knockout_search_agent.eval_runner import (
    MockEvalStatus,
    run_tm_knockout_mock_e2e,
)
from src.tm_knockout_search_agent.services.session import read_artifact


def _read_json_artifact(result, name: str) -> dict | list:
    return json.loads(Path(result.artifacts[name]).read_text(encoding="utf-8"))


def test_complete_request_high_risk_result_writes_report_and_artifacts(tmp_path: Path) -> None:
    progress: list[tuple[int, str, str]] = []

    result = run_tm_knockout_mock_e2e(
        brand_name="KLYRA",
        countries="US, EUIPO",
        goods_services="cosmetics and skincare",
        session_id="mock-high-risk",
        sessions_base_dir=tmp_path / "sessions",
        mock_compumark_results=[
            {
                "id": "cm-klyra-us",
                "mark_name": "KLYRA",
                "jurisdiction": "US",
                "classes": ["3"],
                "goods_services": "Cosmetics and skincare",
                "status": "Registered",
                "owner": "Klyra Beauty LLC",
                "registration_number": "9876543",
            }
        ],
        progress_callback=lambda step, stage, _gate, preview: progress.append(
            (step, stage, preview)
        ),
    )

    assert result.status == MockEvalStatus.COMPLETED
    assert result.final_risk_label == "HIGH"
    assert result.live_api_calls is False
    assert result.errors == []
    assert progress[0][1] == "INTAKE"
    assert "final_report" in result.artifacts
    assert Path(result.artifacts["final_report"]).exists()
    assert "Candidate ID: cm-klyra-us" in (result.final_report or "")

    for artifact_name in (
        "request",
        "search_criteria",
        "query_plan",
        "compumark_results",
        "normalized_candidates",
        "risk_assessment",
        "ranked_findings",
        "adversarial_review",
        "final_decision",
        "final_report",
    ):
        assert artifact_name in result.artifacts
        assert Path(result.artifacts[artifact_name]).exists()

    criteria = _read_json_artifact(result, "search_criteria")
    candidates = _read_json_artifact(result, "normalized_candidates")
    assessment = _read_json_artifact(result, "risk_assessment")

    assert criteria["brand_name"] == "KLYRA"
    assert criteria["jurisdictions"] == ["US"]
    assert criteria["regional_systems"] == ["EUIPO"]
    assert candidates[0]["id"] == "cm-klyra-us"
    assert assessment["overall_risk_label"] == "HIGH"


def test_complete_request_no_relevant_conflicts_is_low(tmp_path: Path) -> None:
    result = run_tm_knockout_mock_e2e(
        brand_name="KLYRA",
        countries=["US", "EUIPO"],
        classes=["3"],
        goods_services="cosmetics and skincare",
        session_id="mock-low-risk",
        sessions_base_dir=tmp_path / "sessions",
    )

    assert result.status == MockEvalStatus.COMPLETED
    assert result.final_risk_label == "LOW"
    assert result.source_failure_status == []
    assert "No knockout/material blocker identified" in (result.final_report or "")
    assert "may be shortlisted for deeper review" in (result.final_report or "")
    assert _read_json_artifact(result, "normalized_candidates") == []


def test_missing_criteria_returns_insufficient_input_without_search(tmp_path: Path) -> None:
    result = run_tm_knockout_mock_e2e(
        brand_name="KLYRA",
        session_id="mock-missing-criteria",
        sessions_base_dir=tmp_path / "sessions",
    )

    assert result.status == MockEvalStatus.INSUFFICIENT_INPUT
    assert result.final_risk_label is None
    assert result.final_report is None
    assert result.live_api_calls is False
    assert "At least one jurisdiction" in " ".join(result.clarification_reasons)
    assert "Goods/services or Nice classes" in " ".join(result.clarification_reasons)
    assert "request" in result.artifacts
    assert "search_criteria" in result.artifacts
    assert "query_plan" not in result.artifacts
    assert "normalized_candidates" not in result.artifacts


def test_source_failure_is_search_failed_and_documented(tmp_path: Path) -> None:
    result = run_tm_knockout_mock_e2e(
        brand_name="KLYRA",
        countries="US",
        classes="3",
        goods_services="cosmetics and skincare",
        session_id="mock-source-failure",
        sessions_base_dir=tmp_path / "sessions",
        mock_source_statuses=[
            {
                "source": "compumark",
                "jurisdiction": "US",
                "required": True,
                "succeeded": False,
                "error_message": "timeout",
            }
        ],
    )

    assert result.status == MockEvalStatus.COMPLETED
    assert result.final_risk_label == "SEARCH_FAILED"
    assert result.source_failure_status == [
        {
            "source": "compumark",
            "jurisdiction": "US",
            "required": True,
            "succeeded": False,
            "error_message": "timeout",
        }
    ]
    assert "CompuMark search failed for US: timeout" in (result.final_report or "")
    assert "final_report" in result.artifacts
    assert Path(result.artifacts["final_report"]).exists()

    final_decision = _read_json_artifact(result, "final_decision")
    assert final_decision["risk_label"] == "SEARCH_FAILED"
    assert final_decision["stopping_decision"] == "STOP_REQUIRED_SOURCE_FAILED"


def test_runner_can_read_written_artifacts_with_session_helpers(tmp_path: Path) -> None:
    result = run_tm_knockout_mock_e2e(
        brand_name="KLYRA",
        countries="US",
        classes="3",
        session_id="mock-artifact-read",
        sessions_base_dir=tmp_path / "sessions",
    )

    loaded_criteria = read_artifact(
        result.session_id,
        "search_criteria",
        base_dir=tmp_path / "sessions",
    )
    loaded_report = Path(result.artifacts["final_report"]).read_text(encoding="utf-8")

    assert loaded_criteria["brand_name"] == "KLYRA"
    assert loaded_report.strip() == result.final_report
