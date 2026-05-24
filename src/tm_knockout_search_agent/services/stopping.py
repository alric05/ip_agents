"""Deterministic stopping and completion rules for TM knockout search."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field, field_validator

from src.tm_knockout_search_agent.services.risk_assessment import SourceSearchStatus
from src.tm_knockout_search_agent.state import (
    ArtifactModel,
    TrademarkQueryGroup,
    TrademarkSearchPlan,
    TrademarkSearchSource,
    TrademarkSearchStage,
)


class StoppingDecisionType(str, Enum):
    """Machine-readable stopping decisions for the search workflow."""

    CONTINUE_SEARCHING = "CONTINUE_SEARCHING"
    COMPLETE_PLANNED_SEARCH = "COMPLETE_PLANNED_SEARCH"
    COMPLETE_NO_RELEVANT_RESULTS = "COMPLETE_NO_RELEVANT_RESULTS"
    STOP_BUDGET_EXHAUSTED = "STOP_BUDGET_EXHAUSTED"
    STOP_REQUIRED_SOURCE_FAILED = "STOP_REQUIRED_SOURCE_FAILED"


class SearchProgress(ArtifactModel):
    """Deterministic progress snapshot for stopping decisions."""

    completed_query_group_ids: list[str] = Field(default_factory=list)
    completed_stages: list[TrademarkSearchStage] = Field(default_factory=list)
    normalized_candidate_count: int = Field(default=0, ge=0)
    relevant_candidate_count: int | None = Field(default=None, ge=0)
    selected_for_deep_review_count: int = Field(default=0, ge=0)
    inactive_contextual_needed: bool = False
    source_statuses: list[SourceSearchStatus] = Field(default_factory=list)

    @field_validator("completed_query_group_ids", mode="after")
    @classmethod
    def _normalize_group_ids(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            stripped = item.strip()
            if stripped and stripped not in seen:
                normalized.append(stripped)
                seen.add(stripped)
        return normalized


class StoppingDecision(ArtifactModel):
    """Structured stop/continue decision for the search workflow."""

    decision: StoppingDecisionType
    reason: str
    explanation: str
    next_query_group_ids: list[str] = Field(default_factory=list)
    incomplete_required_query_group_ids: list[str] = Field(default_factory=list)
    failed_source_notes: list[str] = Field(default_factory=list)
    normalized_candidate_count: int = Field(default=0, ge=0)
    relevant_candidate_count: int = Field(default=0, ge=0)
    selected_for_deep_review_count: int = Field(default=0, ge=0)


def determine_stopping_decision(
    plan: TrademarkSearchPlan,
    progress: SearchProgress | dict[str, Any],
) -> StoppingDecision:
    """Return whether to continue or finalize a planned TM search."""
    progress_model = _coerce_progress(progress)
    relevant_count = _effective_relevant_count(progress_model)
    required_groups = _required_query_groups(plan, progress_model)
    incomplete_groups = [
        group
        for group in required_groups
        if not _query_group_completed(group, progress_model)
    ]
    failed_source_notes = _required_source_failure_notes(plan, progress_model)

    if failed_source_notes:
        return _decision(
            StoppingDecisionType.STOP_REQUIRED_SOURCE_FAILED,
            reason="required_source_failed",
            explanation="A required CompuMark search failed for the requested scope.",
            progress=progress_model,
            relevant_count=relevant_count,
            failed_source_notes=failed_source_notes,
            incomplete_groups=incomplete_groups,
        )

    if incomplete_groups and _budget_exhausted(plan, progress_model):
        return _decision(
            StoppingDecisionType.STOP_BUDGET_EXHAUSTED,
            reason="budget_exhausted_before_required_stages_completed",
            explanation=(
                "Search budget was exhausted before all required planned stages "
                "were completed."
            ),
            progress=progress_model,
            relevant_count=relevant_count,
            incomplete_groups=incomplete_groups,
        )

    if incomplete_groups:
        next_group = incomplete_groups[0]
        return _decision(
            StoppingDecisionType.CONTINUE_SEARCHING,
            reason="required_planned_stages_incomplete",
            explanation=(
                f"Continue with {next_group.id}; required planned search stages "
                "are not complete yet."
            ),
            progress=progress_model,
            relevant_count=relevant_count,
            incomplete_groups=incomplete_groups,
            next_query_group_ids=[next_group.id],
        )

    if relevant_count == 0:
        return _decision(
            StoppingDecisionType.COMPLETE_NO_RELEVANT_RESULTS,
            reason="all_required_stages_complete_no_relevant_candidates",
            explanation=(
                "All required planned search stages are complete and no relevant "
                "candidates were found."
            ),
            progress=progress_model,
            relevant_count=relevant_count,
        )

    return _decision(
        StoppingDecisionType.COMPLETE_PLANNED_SEARCH,
        reason="all_required_stages_complete_candidates_available",
        explanation=(
            "All required planned search stages are complete and candidate "
            "findings are available for reporting."
        ),
        progress=progress_model,
        relevant_count=relevant_count,
    )


def _coerce_progress(progress: SearchProgress | dict[str, Any]) -> SearchProgress:
    if isinstance(progress, SearchProgress):
        return progress
    return SearchProgress.model_validate(progress)


def _required_query_groups(
    plan: TrademarkSearchPlan,
    progress: SearchProgress,
) -> list[TrademarkQueryGroup]:
    required: list[TrademarkQueryGroup] = []
    for group in plan.query_groups:
        if group.required:
            required.append(group)
            continue
        if group.stage == TrademarkSearchStage.INACTIVE_CONTEXTUAL and (
            plan.search_budget.include_inactive_contextual
            or progress.inactive_contextual_needed
        ):
            required.append(group)
    return required


def _query_group_completed(
    group: TrademarkQueryGroup,
    progress: SearchProgress,
) -> bool:
    return (
        group.id in progress.completed_query_group_ids
        or group.stage in progress.completed_stages
    )


def _budget_exhausted(
    plan: TrademarkSearchPlan,
    progress: SearchProgress,
) -> bool:
    return (
        progress.normalized_candidate_count
        >= plan.search_budget.max_candidates_to_normalize
    )


def _effective_relevant_count(progress: SearchProgress) -> int:
    if progress.relevant_candidate_count is not None:
        return progress.relevant_candidate_count
    return progress.normalized_candidate_count


def _required_source_failure_notes(
    plan: TrademarkSearchPlan,
    progress: SearchProgress,
) -> list[str]:
    requested_locations = {
        *[value.upper() for value in plan.criteria.jurisdictions],
        *[value.upper() for value in plan.criteria.regional_systems],
    }
    notes: list[str] = []
    required_compumark_sources = {
        TrademarkSearchSource.COMPUMARK.value,
        TrademarkSearchSource.COMPUMARK_INACTIVE_CONTEXTUAL.value,
    }

    for status in progress.source_statuses:
        location = status.jurisdiction or status.regional_system
        location_key = location.upper() if location else ""
        source = status.source.lower()
        if (
            status.required
            and not status.succeeded
            and source in required_compumark_sources
            and (not requested_locations or not location_key or location_key in requested_locations)
        ):
            note = f"Required CompuMark search failed for {location or 'requested scope'}"
            if status.error_message:
                note = f"{note}: {status.error_message}"
            notes.append(note)
    return notes


def _decision(
    decision_type: StoppingDecisionType,
    *,
    reason: str,
    explanation: str,
    progress: SearchProgress,
    relevant_count: int,
    next_query_group_ids: list[str] | None = None,
    incomplete_groups: list[TrademarkQueryGroup] | None = None,
    failed_source_notes: list[str] | None = None,
) -> StoppingDecision:
    return StoppingDecision(
        decision=decision_type,
        reason=reason,
        explanation=explanation,
        next_query_group_ids=next_query_group_ids or [],
        incomplete_required_query_group_ids=[
            group.id for group in incomplete_groups or []
        ],
        failed_source_notes=failed_source_notes or [],
        normalized_candidate_count=progress.normalized_candidate_count,
        relevant_candidate_count=relevant_count,
        selected_for_deep_review_count=progress.selected_for_deep_review_count,
    )


__all__ = [
    "SearchProgress",
    "StoppingDecision",
    "StoppingDecisionType",
    "determine_stopping_decision",
]
