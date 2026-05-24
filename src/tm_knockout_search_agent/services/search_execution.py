"""Deterministic source execution helpers for TM knockout search.

This module wires planned trademark query groups to curated source clients.
CompuMark execution is supported when explicitly requested by callers; web
search remains deferred until a provider is selected.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import Field

from src.tm_knockout_search_agent.services.compumark_client import (
    CompuMarkAPIError,
    CompuMarkConfigError,
    CompuMarkSearchExecutionResult,
    execute_compumark_search,
)
from src.tm_knockout_search_agent.services.risk_assessment import SourceSearchStatus
from src.tm_knockout_search_agent.state import (
    ArtifactModel,
    TrademarkCandidate,
    TrademarkQueryGroup,
    TrademarkSearchPlan,
    TrademarkSearchSource,
    TrademarkSearchStage,
)
from src.tm_knockout_search_agent.tools.adapters import flag_duplicate_candidates


CompuMarkExecutor = Callable[..., CompuMarkSearchExecutionResult]


class SourceExecutionError(ArtifactModel):
    """Structured source execution error captured without raising to the agent."""

    query_group_id: str
    source: str
    error_type: str
    error_message: str


class TrademarkSourceExecutionResult(ArtifactModel):
    """Aggregate source execution output for a trademark search plan."""

    completed_query_group_ids: list[str] = Field(default_factory=list)
    completed_stages: list[TrademarkSearchStage] = Field(default_factory=list)
    candidates: list[TrademarkCandidate] = Field(default_factory=list)
    compumark_results: list[dict[str, Any]] = Field(default_factory=list)
    web_results: list[dict[str, Any]] = Field(default_factory=list)
    source_statuses: list[SourceSearchStatus] = Field(default_factory=list)
    errors: list[SourceExecutionError] = Field(default_factory=list)
    live_api_calls: bool = False


def execute_trademark_search_plan(
    plan: TrademarkSearchPlan,
    *,
    compumark_executor: CompuMarkExecutor = execute_compumark_search,
    max_candidates_to_normalize: int | None = None,
) -> TrademarkSourceExecutionResult:
    """Execute source-backed query groups in a trademark search plan.

    Only CompuMark groups are executed in this phase. Web/common-law query
    groups are intentionally left incomplete so stopping rules can continue to
    request that stage when web search is enabled.
    """
    max_candidates = (
        max_candidates_to_normalize
        if max_candidates_to_normalize is not None
        else plan.search_budget.max_candidates_to_normalize
    )
    completed_query_group_ids: list[str] = []
    completed_stages: list[TrademarkSearchStage] = []
    candidates: list[TrademarkCandidate] = []
    compumark_results: list[dict[str, Any]] = []
    source_statuses: list[SourceSearchStatus] = []
    errors: list[SourceExecutionError] = []
    live_api_calls = False

    for group in plan.query_groups:
        if group.source not in {
            TrademarkSearchSource.COMPUMARK,
            TrademarkSearchSource.COMPUMARK_INACTIVE_CONTEXTUAL,
        }:
            continue

        try:
            execution = compumark_executor(
                brand_name=group.brand_name,
                jurisdictions=[*group.jurisdictions, *group.regional_systems],
                classes=group.classes,
                query_intent=group.query_intent.value,
                max_results=group.max_results,
            )
            live_api_calls = live_api_calls or execution.live_api_calls
            compumark_results.append(
                {
                    "query_group_id": group.id,
                    "stage": group.stage.value,
                    **execution.to_dict(),
                }
            )
            candidates.extend(execution.candidates)
            completed_query_group_ids.append(group.id)
            if group.stage not in completed_stages:
                completed_stages.append(group.stage)
            source_statuses.extend(_statuses_for_group(group, succeeded=True))
        except (CompuMarkAPIError, CompuMarkConfigError, ValueError) as exc:
            live_api_calls = live_api_calls or isinstance(exc, CompuMarkAPIError)
            error = SourceExecutionError(
                query_group_id=group.id,
                source=group.source.value,
                error_type=_error_type(exc),
                error_message=str(exc),
            )
            errors.append(error)
            source_statuses.extend(
                _statuses_for_group(
                    group,
                    succeeded=False,
                    error_message=str(exc),
                )
            )
            compumark_results.append(
                {
                    "query_group_id": group.id,
                    "stage": group.stage.value,
                    "source": group.source.value,
                    "succeeded": False,
                    "live_api_calls": isinstance(exc, CompuMarkAPIError),
                    "error_type": error.error_type,
                    "error_message": error.error_message,
                    "candidates": [],
                }
            )

    normalized_candidates = flag_duplicate_candidates(candidates)[:max_candidates]
    return TrademarkSourceExecutionResult(
        completed_query_group_ids=_dedupe(completed_query_group_ids),
        completed_stages=completed_stages,
        candidates=normalized_candidates,
        compumark_results=compumark_results,
        source_statuses=source_statuses,
        errors=errors,
        live_api_calls=live_api_calls,
    )


def _statuses_for_group(
    group: TrademarkQueryGroup,
    *,
    succeeded: bool,
    error_message: str | None = None,
) -> list[SourceSearchStatus]:
    statuses: list[SourceSearchStatus] = []
    for jurisdiction in group.jurisdictions:
        statuses.append(
            SourceSearchStatus(
                source=group.source.value,
                jurisdiction=jurisdiction,
                required=group.required,
                succeeded=succeeded,
                error_message=error_message,
            )
        )
    for regional_system in group.regional_systems:
        statuses.append(
            SourceSearchStatus(
                source=group.source.value,
                regional_system=regional_system,
                required=group.required,
                succeeded=succeeded,
                error_message=error_message,
            )
        )
    if not statuses:
        statuses.append(
            SourceSearchStatus(
                source=group.source.value,
                required=group.required,
                succeeded=succeeded,
                error_message=error_message,
            )
        )
    return statuses


def _error_type(exc: Exception) -> str:
    if isinstance(exc, CompuMarkConfigError):
        return "configuration"
    if isinstance(exc, CompuMarkAPIError):
        return "api"
    return "validation"


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            output.append(value)
            seen.add(value)
    return output


__all__ = [
    "CompuMarkExecutor",
    "SourceExecutionError",
    "TrademarkSourceExecutionResult",
    "execute_trademark_search_plan",
]
