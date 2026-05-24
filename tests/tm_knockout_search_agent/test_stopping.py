"""Deterministic stopping rule tests for TM knockout search."""

from __future__ import annotations

from src.tm_knockout_search_agent.services.query_planner import plan_trademark_search
from src.tm_knockout_search_agent.services.risk_assessment import SourceSearchStatus
from src.tm_knockout_search_agent.services.stopping import (
    SearchProgress,
    StoppingDecisionType,
    determine_stopping_decision,
)
from src.tm_knockout_search_agent.state import (
    TrademarkSearchBudget,
    TrademarkSearchCriteria,
    TrademarkSearchStage,
)


def _plan(*, include_inactive_contextual: bool = False, max_candidates: int = 100):
    return plan_trademark_search(
        TrademarkSearchCriteria(
            brand_name="Acme Atlas",
            jurisdictions=["US"],
            nice_classes=["35"],
            goods_services="Retail store services featuring outdoor equipment",
        ),
        budget=TrademarkSearchBudget(
            max_candidates_to_normalize=max_candidates,
            include_inactive_contextual=include_inactive_contextual,
        ),
    )


def test_exact_complete_but_similar_not_complete_continues() -> None:
    plan = _plan()

    decision = determine_stopping_decision(
        plan,
        SearchProgress(completed_query_group_ids=["QG-EXACT-ACTIVE-1"]),
    )

    assert decision.decision == StoppingDecisionType.CONTINUE_SEARCHING
    assert decision.reason == "required_planned_stages_incomplete"
    assert decision.next_query_group_ids == ["QG-SIMILAR-ACTIVE-1"]
    assert "QG-SIMILAR-ACTIVE-1" in decision.incomplete_required_query_group_ids


def test_high_risk_result_does_not_stop_before_web_search_complete() -> None:
    plan = _plan()

    decision = determine_stopping_decision(
        plan,
        SearchProgress(
            completed_query_group_ids=[
                "QG-EXACT-ACTIVE-1",
                "QG-SIMILAR-ACTIVE-1",
            ],
            normalized_candidate_count=3,
            relevant_candidate_count=1,
            selected_for_deep_review_count=1,
        ),
    )

    assert decision.decision == StoppingDecisionType.CONTINUE_SEARCHING
    assert decision.next_query_group_ids == ["QG-WEB-COMMON-LAW-1"]
    assert "required planned search stages" in decision.explanation


def test_all_required_stages_complete_with_candidates_completes_planned_search() -> None:
    plan = _plan()

    decision = determine_stopping_decision(
        plan,
        SearchProgress(
            completed_stages=[
                TrademarkSearchStage.EXACT_ACTIVE,
                TrademarkSearchStage.SIMILAR_ACTIVE,
                TrademarkSearchStage.WEB_COMMON_LAW,
            ],
            normalized_candidate_count=5,
            relevant_candidate_count=2,
            selected_for_deep_review_count=2,
        ),
    )

    assert decision.decision == StoppingDecisionType.COMPLETE_PLANNED_SEARCH
    assert decision.reason == "all_required_stages_complete_candidates_available"
    assert decision.relevant_candidate_count == 2


def test_all_required_stages_complete_with_no_candidates_completes_no_results() -> None:
    plan = _plan()

    decision = determine_stopping_decision(
        plan,
        SearchProgress(
            completed_stages=[
                TrademarkSearchStage.EXACT_ACTIVE,
                TrademarkSearchStage.SIMILAR_ACTIVE,
                TrademarkSearchStage.WEB_COMMON_LAW,
            ],
            normalized_candidate_count=0,
            relevant_candidate_count=0,
        ),
    )

    assert decision.decision == StoppingDecisionType.COMPLETE_NO_RELEVANT_RESULTS
    assert decision.reason == "all_required_stages_complete_no_relevant_candidates"


def test_required_compumark_source_failed_stops() -> None:
    plan = _plan()

    decision = determine_stopping_decision(
        plan,
        SearchProgress(
            source_statuses=[
                SourceSearchStatus(
                    source="compumark",
                    jurisdiction="US",
                    required=True,
                    succeeded=False,
                    error_message="timeout",
                )
            ]
        ),
    )

    assert decision.decision == StoppingDecisionType.STOP_REQUIRED_SOURCE_FAILED
    assert decision.reason == "required_source_failed"
    assert decision.failed_source_notes == [
        "Required CompuMark search failed for US: timeout"
    ]


def test_budget_exhausted_before_all_stages_complete_stops() -> None:
    plan = _plan(max_candidates=2)

    decision = determine_stopping_decision(
        plan,
        SearchProgress(
            completed_query_group_ids=["QG-EXACT-ACTIVE-1"],
            normalized_candidate_count=2,
            relevant_candidate_count=2,
            selected_for_deep_review_count=1,
        ),
    )

    assert decision.decision == StoppingDecisionType.STOP_BUDGET_EXHAUSTED
    assert decision.reason == "budget_exhausted_before_required_stages_completed"
    assert "QG-SIMILAR-ACTIVE-1" in decision.incomplete_required_query_group_ids


def test_inactive_contextual_is_skipped_when_not_configured_and_active_succeeded() -> None:
    plan = _plan(include_inactive_contextual=False)

    decision = determine_stopping_decision(
        plan,
        SearchProgress(
            completed_stages=[
                TrademarkSearchStage.EXACT_ACTIVE,
                TrademarkSearchStage.SIMILAR_ACTIVE,
                TrademarkSearchStage.WEB_COMMON_LAW,
            ],
            normalized_candidate_count=1,
            relevant_candidate_count=1,
        ),
    )

    assert decision.decision == StoppingDecisionType.COMPLETE_PLANNED_SEARCH
    assert decision.next_query_group_ids == []
    assert all("INACTIVE" not in group_id for group_id in decision.incomplete_required_query_group_ids)


def test_inactive_contextual_is_required_when_configured() -> None:
    plan = _plan(include_inactive_contextual=True)

    before_inactive = determine_stopping_decision(
        plan,
        SearchProgress(
            completed_stages=[
                TrademarkSearchStage.EXACT_ACTIVE,
                TrademarkSearchStage.SIMILAR_ACTIVE,
                TrademarkSearchStage.WEB_COMMON_LAW,
            ],
            normalized_candidate_count=1,
            relevant_candidate_count=1,
        ),
    )
    after_inactive = determine_stopping_decision(
        plan,
        SearchProgress(
            completed_stages=[
                TrademarkSearchStage.EXACT_ACTIVE,
                TrademarkSearchStage.SIMILAR_ACTIVE,
                TrademarkSearchStage.WEB_COMMON_LAW,
                TrademarkSearchStage.INACTIVE_CONTEXTUAL,
            ],
            normalized_candidate_count=1,
            relevant_candidate_count=1,
        ),
    )

    assert before_inactive.decision == StoppingDecisionType.CONTINUE_SEARCHING
    assert before_inactive.next_query_group_ids == ["QG-INACTIVE-CONTEXTUAL-1"]
    assert after_inactive.decision == StoppingDecisionType.COMPLETE_PLANNED_SEARCH
