"""Agent factory tests for TM knockout search."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import src.tm_knockout_search_agent.deep_agent as deep_agent_module
from src.tm_knockout_search_agent.services.risk_assessment import SourceSearchStatus
from src.tm_knockout_search_agent.services.search_execution import (
    TrademarkSourceExecutionResult,
)
from src.tm_knockout_search_agent.deep_agent import (
    TMKnockoutSearchAgent,
    check_tm_knockout,
    create_knockout_search_agent,
    create_tm_knockout_search_agent,
)
from src.tm_knockout_search_agent.state import TrademarkSearchStage


def _candidate() -> dict:
    return {
        "id": "cm-1",
        "source": "compumark",
        "mark_name": "KLYRA",
        "jurisdiction": "US",
        "classes": ["3"],
        "goods_services": "Cosmetics and skincare",
        "status": "Registered",
        "owner": "Klyra Beauty LLC",
    }


def test_create_tm_knockout_search_agent_returns_invokable_object(tmp_path: Path) -> None:
    agent = create_tm_knockout_search_agent(
        session_id="factory-test",
        sessions_base_dir=tmp_path / "sessions",
        model="test-model",
        include_web_search=True,
    )

    assert isinstance(agent, TMKnockoutSearchAgent)
    assert callable(agent.invoke)
    assert [tool.name for tool in agent.tools] == [
        "compumark_trademark_search",
        "web_common_law_search",
    ]
    assert "TM Knockout Search Agent" in agent.system_instructions


def test_backward_compatible_factory_alias(tmp_path: Path) -> None:
    agent = create_knockout_search_agent(
        session_id="factory-alias-test",
        sessions_base_dir=tmp_path / "sessions",
    )

    assert isinstance(agent, TMKnockoutSearchAgent)


def test_agent_invoke_runs_deterministic_check_without_live_api(tmp_path: Path) -> None:
    agent = create_tm_knockout_search_agent(
        session_id="invoke-test",
        sessions_base_dir=tmp_path / "sessions",
    )

    result = agent.invoke(
        {
            "brand": "KLYRA",
            "countries": "US, EUIPO",
            "classes": "3,35",
            "candidates": [_candidate()],
            "completed_stages": [
                TrademarkSearchStage.EXACT_ACTIVE,
                TrademarkSearchStage.SIMILAR_ACTIVE,
                TrademarkSearchStage.WEB_COMMON_LAW,
            ],
        }
    )

    assert result["session_id"] == "invoke-test"
    assert result["live_api_calls"] is False
    assert result["risk_assessment"]["overall_risk_label"] == "HIGH"
    assert result["stopping_decision"]["decision"] == "COMPLETE_PLANNED_SEARCH"
    assert result["report_markdown"] is not None
    assert (tmp_path / "sessions" / "tm_knockout_search_agent" / "invoke-test").exists()


def test_check_tm_knockout_can_be_called_with_mocked_candidates(tmp_path: Path) -> None:
    result = check_tm_knockout(
        brand="KLYRA",
        countries="US, EUIPO",
        goods="cosmetics and skincare",
        candidates=[_candidate()],
        completed_stages=[
            "EXACT_ACTIVE",
            "SIMILAR_ACTIVE",
            "WEB_COMMON_LAW",
        ],
        session_id="check-test",
        sessions_base_dir=tmp_path / "sessions",
    )

    assert result["tools"] == [
        "compumark_trademark_search",
        "web_common_law_search",
    ]
    assert result["criteria"]["brand_name"] == "KLYRA"
    assert result["criteria"]["jurisdictions"] == ["US"]
    assert result["criteria"]["regional_systems"] == ["EUIPO"]
    assert result["live_api_calls"] is False


def test_check_tm_knockout_can_run_opt_in_compumark_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_execute_trademark_search_plan(*args, **kwargs):
        return TrademarkSourceExecutionResult(
            completed_query_group_ids=[
                "QG-EXACT-ACTIVE-1",
                "QG-SIMILAR-ACTIVE-1",
            ],
            completed_stages=[
                TrademarkSearchStage.EXACT_ACTIVE,
                TrademarkSearchStage.SIMILAR_ACTIVE,
            ],
            candidates=[_candidate()],
            compumark_results=[
                {
                    "query_group_id": "QG-EXACT-ACTIVE-1",
                    "source": "compumark",
                    "succeeded": True,
                    "live_api_calls": True,
                    "candidates": [_candidate()],
                }
            ],
            source_statuses=[
                SourceSearchStatus(source="compumark", jurisdiction="US", succeeded=True)
            ],
            live_api_calls=True,
        )

    monkeypatch.setattr(
        deep_agent_module,
        "execute_trademark_search_plan",
        fake_execute_trademark_search_plan,
    )

    result = check_tm_knockout(
        brand="KLYRA",
        countries="US",
        goods="cosmetics and skincare",
        session_id="live-compumark-check-test",
        sessions_base_dir=tmp_path / "sessions",
        include_web_search=False,
        live_compumark=True,
    )

    session_dir = (
        tmp_path
        / "sessions"
        / "tm_knockout_search_agent"
        / "live-compumark-check-test"
    )
    assert result["live_api_calls"] is True
    assert result["risk_assessment"]["overall_risk_label"] == "HIGH"
    assert result["stopping_decision"]["decision"] == "COMPLETE_PLANNED_SEARCH"
    assert result["report_markdown"] is not None
    assert (session_dir / "compumark_results.json").exists()
    assert (session_dir / "source_statuses.json").exists()


def test_novelty_checker_state_import_still_works() -> None:
    module = importlib.import_module("src.novelty_checker.state")

    assert module is not None
