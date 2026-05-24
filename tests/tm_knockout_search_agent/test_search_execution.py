"""Source execution tests for TM knockout search."""

from __future__ import annotations

from src.tm_knockout_search_agent.services.compumark_client import (
    CompuMarkAPIError,
    CompuMarkSearchExecutionResult,
)
from src.tm_knockout_search_agent.services.query_planner import plan_trademark_search
from src.tm_knockout_search_agent.services.search_execution import (
    execute_trademark_search_plan,
)
from src.tm_knockout_search_agent.state import (
    TrademarkCandidate,
    TrademarkCandidateSource,
    TrademarkSearchBudget,
    TrademarkSearchCriteria,
    TrademarkSearchStage,
)


def _criteria() -> TrademarkSearchCriteria:
    return TrademarkSearchCriteria(
        brand_name="KLYRA",
        jurisdictions=["US"],
        regional_systems=["EUIPO"],
        nice_classes=["3"],
        goods_services="cosmetics and skincare",
    )


def _candidate(candidate_id: str, jurisdiction: str = "US") -> TrademarkCandidate:
    return TrademarkCandidate(
        id=candidate_id,
        source=TrademarkCandidateSource.COMPUMARK,
        mark_name="KLYRA",
        jurisdiction=jurisdiction,
        classes=["3"],
        goods_services="Cosmetics and skincare",
        status="Registered",
        owner="Klyra Beauty LLC",
    )


def test_executes_compumark_query_groups_and_collects_candidates() -> None:
    plan = plan_trademark_search(
        _criteria(),
        budget=TrademarkSearchBudget(include_web_search=True),
    )
    calls: list[dict] = []

    def executor(**kwargs):
        calls.append(kwargs)
        return CompuMarkSearchExecutionResult(
            requests=[{"registrationOfficeCodes": ["US", "EM"]}],
            counts={"US": 1},
            ids_by_office={"US": ["cm-1"]},
            selected_ids=["cm-1"],
            candidates=[_candidate(f"cm-{len(calls)}")],
            raw_trademark_count=1,
            truncated=False,
            live_api_calls=True,
        )

    result = execute_trademark_search_plan(plan, compumark_executor=executor)

    assert [call["query_intent"] for call in calls] == ["exact", "similar"]
    assert result.completed_query_group_ids == [
        "QG-EXACT-ACTIVE-1",
        "QG-SIMILAR-ACTIVE-1",
    ]
    assert result.completed_stages == [
        TrademarkSearchStage.EXACT_ACTIVE,
        TrademarkSearchStage.SIMILAR_ACTIVE,
    ]
    assert len(result.candidates) == 2
    assert result.compumark_results[0]["succeeded"] is True
    assert result.live_api_calls is True
    assert {status.regional_system for status in result.source_statuses} >= {"EUIPO"}
    assert {status.jurisdiction for status in result.source_statuses} >= {"US"}


def test_web_groups_are_not_marked_complete_by_compumark_execution() -> None:
    plan = plan_trademark_search(
        _criteria(),
        budget=TrademarkSearchBudget(include_web_search=True),
    )

    def executor(**kwargs):
        return CompuMarkSearchExecutionResult(
            requests=[],
            counts={},
            ids_by_office={},
            selected_ids=[],
            candidates=[],
            raw_trademark_count=0,
            truncated=False,
            live_api_calls=True,
        )

    result = execute_trademark_search_plan(plan, compumark_executor=executor)

    assert TrademarkSearchStage.WEB_COMMON_LAW not in result.completed_stages
    assert "QG-WEB-COMMON-LAW-1" not in result.completed_query_group_ids


def test_required_compumark_failure_creates_failed_source_status() -> None:
    plan = plan_trademark_search(
        _criteria(),
        budget=TrademarkSearchBudget(include_web_search=False),
    )

    def executor(**kwargs):
        raise CompuMarkAPIError("service unavailable")

    result = execute_trademark_search_plan(plan, compumark_executor=executor)

    assert result.completed_query_group_ids == []
    assert result.live_api_calls is True
    assert result.errors[0].error_type == "api"
    assert result.source_statuses[0].succeeded is False
    assert result.source_statuses[0].required is True
    assert result.compumark_results[0]["succeeded"] is False


def test_candidate_normalization_budget_is_applied() -> None:
    plan = plan_trademark_search(
        _criteria(),
        budget=TrademarkSearchBudget(include_web_search=False),
    )

    def executor(**kwargs):
        return CompuMarkSearchExecutionResult(
            requests=[],
            counts={},
            ids_by_office={},
            selected_ids=[],
            candidates=[_candidate("cm-1"), _candidate("cm-2")],
            raw_trademark_count=2,
            truncated=False,
            live_api_calls=True,
        )

    result = execute_trademark_search_plan(
        plan,
        compumark_executor=executor,
        max_candidates_to_normalize=1,
    )

    assert [candidate.id for candidate in result.candidates] == ["cm-1"]
