"""Deterministic trademark query planner.

The planner creates structured query groups only. It does not call CompuMark,
web search, litigation, or any other live service, and it deliberately avoids
provider-specific query syntax in v1.
"""

from __future__ import annotations

import re
from typing import Any

from src.tm_knockout_search_agent.state import (
    TrademarkFallbackStrategy,
    TrademarkQueryGroup,
    TrademarkQueryIntent,
    TrademarkSearchBudget,
    TrademarkSearchCriteria,
    TrademarkSearchPlan,
    TrademarkSearchSource,
    TrademarkSearchStage,
)


def normalize_brand_name(brand_name: str) -> str:
    """Normalize a mark for stable planning metadata."""
    normalized = brand_name.strip()
    normalized = re.sub(r"[\u2122\u00ae\u2120]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip().upper()


def _coerce_criteria(criteria: TrademarkSearchCriteria | dict[str, Any]) -> TrademarkSearchCriteria:
    if isinstance(criteria, TrademarkSearchCriteria):
        return criteria
    return TrademarkSearchCriteria.model_validate(criteria)


def _coerce_budget(
    budget: TrademarkSearchBudget | dict[str, Any] | None,
) -> TrademarkSearchBudget:
    if budget is None:
        return TrademarkSearchBudget()
    if isinstance(budget, TrademarkSearchBudget):
        return budget
    return TrademarkSearchBudget.model_validate(budget)


def _source_priority_order(
    budget: TrademarkSearchBudget,
) -> list[TrademarkSearchSource]:
    sources = [TrademarkSearchSource.COMPUMARK]
    if budget.include_web_search:
        sources.append(TrademarkSearchSource.WEB_SEARCH)
    if budget.include_inactive_contextual:
        sources.append(TrademarkSearchSource.COMPUMARK_INACTIVE_CONTEXTUAL)
    return sources


def _progressive_stages(
    budget: TrademarkSearchBudget,
) -> list[TrademarkSearchStage]:
    stages = [
        TrademarkSearchStage.EXACT_ACTIVE,
        TrademarkSearchStage.SIMILAR_ACTIVE,
    ]
    if budget.include_web_search:
        stages.append(TrademarkSearchStage.WEB_COMMON_LAW)
    if budget.include_inactive_contextual:
        stages.append(TrademarkSearchStage.INACTIVE_CONTEXTUAL)
    return stages


def _query_group(
    *,
    group_id: str,
    stage: TrademarkSearchStage,
    source: TrademarkSearchSource,
    intent: TrademarkQueryIntent,
    criteria: TrademarkSearchCriteria,
    budget: TrademarkSearchBudget,
    required: bool,
    notes: list[str],
) -> TrademarkQueryGroup:
    return TrademarkQueryGroup(
        id=group_id,
        stage=stage,
        source=source,
        brand_name=criteria.brand_name,
        normalized_brand_name=normalize_brand_name(criteria.brand_name),
        jurisdictions=criteria.jurisdictions,
        regional_systems=criteria.regional_systems,
        classes=criteria.all_classes,
        inferred_classes=criteria.inferred_classes,
        goods_services=criteria.goods_services,
        query_intent=intent,
        max_results=budget.max_results_per_query,
        required=required,
        notes=notes,
        assumptions=criteria.assumptions,
    )


def plan_trademark_search(
    criteria: TrademarkSearchCriteria | dict[str, Any],
    *,
    budget: TrademarkSearchBudget | dict[str, Any] | None = None,
) -> TrademarkSearchPlan:
    """Create a deterministic trademark knockout search plan."""
    normalized_criteria = _coerce_criteria(criteria)
    search_budget = _coerce_budget(budget)

    query_groups = [
        _query_group(
            group_id="QG-EXACT-ACTIVE-1",
            stage=TrademarkSearchStage.EXACT_ACTIVE,
            source=TrademarkSearchSource.COMPUMARK,
            intent=TrademarkQueryIntent.EXACT,
            criteria=normalized_criteria,
            budget=search_budget,
            required=True,
            notes=[
                "Exact active register search is always first in v1.",
                "No provider-specific syntax is generated at planning time.",
            ],
        ),
        _query_group(
            group_id="QG-SIMILAR-ACTIVE-1",
            stage=TrademarkSearchStage.SIMILAR_ACTIVE,
            source=TrademarkSearchSource.COMPUMARK,
            intent=TrademarkQueryIntent.SIMILAR,
            criteria=normalized_criteria,
            budget=search_budget,
            required=True,
            notes=[
                "Similarity active search follows exact search.",
                "Similarity expansion is handled by future search tooling.",
            ],
        ),
    ]

    if search_budget.include_web_search:
        query_groups.append(
            _query_group(
                group_id="QG-WEB-COMMON-LAW-1",
                stage=TrademarkSearchStage.WEB_COMMON_LAW,
                source=TrademarkSearchSource.WEB_SEARCH,
                intent=TrademarkQueryIntent.WEB_COMMON_LAW,
                criteria=normalized_criteria,
                budget=search_budget,
                required=True,
                notes=[
                    "Common-law web search is standard in v1.",
                    "Search execution is deferred to future tooling.",
                ],
            )
        )

    if search_budget.include_inactive_contextual:
        query_groups.append(
            _query_group(
                group_id="QG-INACTIVE-CONTEXTUAL-1",
                stage=TrademarkSearchStage.INACTIVE_CONTEXTUAL,
                source=TrademarkSearchSource.COMPUMARK_INACTIVE_CONTEXTUAL,
                intent=TrademarkQueryIntent.INACTIVE_CONTEXTUAL,
                criteria=normalized_criteria,
                budget=search_budget,
                required=False,
                notes=[
                    "Inactive/dead records are contextual only in v1.",
                    "Use after active searches are weak, no-hit, or ambiguous.",
                ],
            )
        )

    fallback_strategy = TrademarkFallbackStrategy(
        web_common_law_standard=search_budget.include_web_search,
        notes=[
            "Always run exact active search.",
            "Run similar active search after exact active search.",
            "Run web/common-law search when enabled in the budget.",
            "Litigation remains a future extension and is not active in v1.",
        ],
    )

    return TrademarkSearchPlan(
        criteria=normalized_criteria,
        source_priority_order=_source_priority_order(search_budget),
        progressive_stages=_progressive_stages(search_budget),
        query_groups=query_groups,
        search_budget=search_budget,
        fallback_strategy=fallback_strategy,
        requires_clarification=normalized_criteria.requires_clarification,
        clarification_reasons=normalized_criteria.clarification_reasons,
    )


__all__ = [
    "normalize_brand_name",
    "plan_trademark_search",
]
