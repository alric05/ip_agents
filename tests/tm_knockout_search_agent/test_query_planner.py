"""Deterministic trademark query planner tests."""

from __future__ import annotations

from src.tm_knockout_search_agent.services.query_planner import (
    normalize_brand_name,
    plan_trademark_search,
)
from src.tm_knockout_search_agent.state import (
    TrademarkQueryIntent,
    TrademarkSearchBudget,
    TrademarkSearchCriteria,
    TrademarkSearchSource,
    TrademarkSearchStage,
)


def test_brand_countries_and_goods_services_plan_exact_similar_and_web() -> None:
    plan = plan_trademark_search(
        TrademarkSearchCriteria(
            brand_name="Acme Atlas",
            jurisdictions=["US", "CA"],
            goods_services="Retail store services featuring outdoor equipment",
            assumptions=["English language web search"],
        )
    )

    assert plan.source_priority_order == [
        TrademarkSearchSource.COMPUMARK,
        TrademarkSearchSource.WEB_SEARCH,
    ]
    assert [group.stage for group in plan.query_groups] == [
        TrademarkSearchStage.EXACT_ACTIVE,
        TrademarkSearchStage.SIMILAR_ACTIVE,
        TrademarkSearchStage.WEB_COMMON_LAW,
    ]
    assert [group.query_intent for group in plan.query_groups] == [
        TrademarkQueryIntent.EXACT,
        TrademarkQueryIntent.SIMILAR,
        TrademarkQueryIntent.WEB_COMMON_LAW,
    ]
    assert all(group.brand_name == "Acme Atlas" for group in plan.query_groups)
    assert all(group.normalized_brand_name == "ACME ATLAS" for group in plan.query_groups)
    assert all(group.jurisdictions == ["US", "CA"] for group in plan.query_groups)
    assert all(
        group.goods_services == "Retail store services featuring outdoor equipment"
        for group in plan.query_groups
    )


def test_brand_countries_and_classes_only_is_accepted() -> None:
    plan = plan_trademark_search(
        {
            "brand_name": "NOVA FIELD",
            "jurisdictions": ["us"],
            "nice_classes": ["009", "35"],
        }
    )

    assert not plan.requires_clarification
    assert all(group.goods_services is None for group in plan.query_groups)
    assert all(group.classes == ["9", "35"] for group in plan.query_groups)


def test_goods_services_are_carried_and_inferred_classes_are_included() -> None:
    plan = plan_trademark_search(
        TrademarkSearchCriteria(
            brand_name="Signal Cove",
            jurisdictions=["GB"],
            goods_services="Software as a service for monitoring logistics data",
            inferred_classes=["42", "009"],
            business_context="B2B logistics analytics",
        )
    )

    assert plan.criteria.goods_services == (
        "Software as a service for monitoring logistics data"
    )
    assert plan.criteria.business_context == "B2B logistics analytics"
    assert plan.criteria.inferred_classes == ["42", "9"]
    assert all(group.classes == ["42", "9"] for group in plan.query_groups)
    assert all(group.inferred_classes == ["42", "9"] for group in plan.query_groups)


def test_euipo_is_regional_system_and_not_expanded_to_countries() -> None:
    plan = plan_trademark_search(
        TrademarkSearchCriteria(
            brand_name="Riverbyte",
            jurisdictions=["EUIPO"],
            nice_classes=["41"],
        )
    )

    assert plan.criteria.jurisdictions == []
    assert plan.criteria.regional_systems == ["EUIPO"]
    assert not plan.requires_clarification
    assert all(group.jurisdictions == [] for group in plan.query_groups)
    assert all(group.regional_systems == ["EUIPO"] for group in plan.query_groups)
    assert "DE" not in plan.model_dump_json()
    assert "FR" not in plan.model_dump_json()


def test_ambiguous_europe_requires_clarification() -> None:
    plan = plan_trademark_search(
        TrademarkSearchCriteria(
            brand_name="Bright Loom",
            jurisdictions=["Europe"],
            nice_classes=["25"],
        )
    )

    assert plan.requires_clarification
    assert plan.criteria.requires_clarification
    assert any("Europe is ambiguous" in reason for reason in plan.clarification_reasons)
    assert all(group.jurisdictions == ["Europe"] for group in plan.query_groups)


def test_search_budget_limits_are_applied() -> None:
    plan = plan_trademark_search(
        TrademarkSearchCriteria(
            brand_name="Kite & Key",
            jurisdictions=["US"],
            nice_classes=["36"],
        ),
        budget=TrademarkSearchBudget(
            max_results_per_query=7,
            max_candidates_to_normalize=30,
            max_candidates_to_surface_in_report=5,
            include_web_search=False,
        ),
    )

    assert plan.search_budget.max_results_per_query == 7
    assert plan.search_budget.max_candidates_to_normalize == 30
    assert plan.search_budget.max_candidates_to_surface_in_report == 5
    assert plan.source_priority_order == [TrademarkSearchSource.COMPUMARK]
    assert [group.max_results for group in plan.query_groups] == [7, 7]
    assert TrademarkSearchStage.WEB_COMMON_LAW not in plan.progressive_stages


def test_inactive_contextual_search_is_optional_fallback_not_primary() -> None:
    default_plan = plan_trademark_search(
        TrademarkSearchCriteria(
            brand_name="Harbor Mint",
            jurisdictions=["US"],
            nice_classes=["30"],
        )
    )
    inactive_plan = plan_trademark_search(
        TrademarkSearchCriteria(
            brand_name="Harbor Mint",
            jurisdictions=["US"],
            nice_classes=["30"],
        ),
        budget={"include_inactive_contextual": True},
    )

    assert TrademarkSearchSource.COMPUMARK_INACTIVE_CONTEXTUAL not in (
        default_plan.source_priority_order
    )
    assert all(
        group.stage != TrademarkSearchStage.INACTIVE_CONTEXTUAL
        for group in default_plan.query_groups
    )
    inactive_groups = [
        group
        for group in inactive_plan.query_groups
        if group.stage == TrademarkSearchStage.INACTIVE_CONTEXTUAL
    ]
    assert len(inactive_groups) == 1
    assert inactive_groups[0].required is False
    assert inactive_plan.source_priority_order == [
        TrademarkSearchSource.COMPUMARK,
        TrademarkSearchSource.WEB_SEARCH,
        TrademarkSearchSource.COMPUMARK_INACTIVE_CONTEXTUAL,
    ]
    assert TrademarkSearchSource.LITIGATION in inactive_plan.fallback_strategy.future_extensions
    assert all(group.source != TrademarkSearchSource.LITIGATION for group in inactive_plan.query_groups)


def test_brand_normalization_is_stable_without_query_syntax() -> None:
    assert normalize_brand_name("  Acme\u2122   Atlas \u00ae ") == "ACME ATLAS"
