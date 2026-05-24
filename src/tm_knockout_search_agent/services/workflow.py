"""Deterministic workflow stage rules for TM knockout search."""

from __future__ import annotations

from src.tm_knockout_search_agent.state import WorkflowStage


class WorkflowTransitionError(ValueError):
    """Raised when a workflow transition is not allowed."""


ALLOWED_TRANSITIONS: dict[WorkflowStage, frozenset[WorkflowStage]] = {
    WorkflowStage.INTAKE: frozenset({WorkflowStage.AWAITING_SCOPE_CONFIRMATION}),
    WorkflowStage.AWAITING_SCOPE_CONFIRMATION: frozenset(
        {WorkflowStage.ELEMENTS_READY}
    ),
    WorkflowStage.ELEMENTS_READY: frozenset({WorkflowStage.SEARCH_PLAN_READY}),
    WorkflowStage.SEARCH_PLAN_READY: frozenset({WorkflowStage.SEARCHING}),
    WorkflowStage.SEARCHING: frozenset({WorkflowStage.SCREENING}),
    WorkflowStage.SCREENING: frozenset(
        {WorkflowStage.SEARCHING, WorkflowStage.DECISION_READY}
    ),
    WorkflowStage.DECISION_READY: frozenset({WorkflowStage.REPORT_READY}),
    WorkflowStage.REPORT_READY: frozenset({WorkflowStage.COMPLETED}),
    WorkflowStage.COMPLETED: frozenset(),
    WorkflowStage.ERROR: frozenset(),
}

REQUIRED_ARTIFACTS_BY_STAGE: dict[WorkflowStage, tuple[str, ...]] = {
    WorkflowStage.INTAKE: (),
    WorkflowStage.AWAITING_SCOPE_CONFIRMATION: ("request", "scope"),
    WorkflowStage.ELEMENTS_READY: ("request", "scope", "claim_elements"),
    WorkflowStage.SEARCH_PLAN_READY: (
        "request",
        "scope",
        "claim_elements",
        "search_plan",
    ),
    WorkflowStage.SEARCHING: (
        "request",
        "scope",
        "claim_elements",
        "search_plan",
    ),
    WorkflowStage.SCREENING: (
        "request",
        "scope",
        "claim_elements",
        "search_plan",
        "candidates",
    ),
    WorkflowStage.DECISION_READY: (
        "request",
        "scope",
        "claim_elements",
        "search_plan",
        "candidates",
        "assessments",
    ),
    WorkflowStage.REPORT_READY: (
        "request",
        "scope",
        "claim_elements",
        "search_plan",
        "candidates",
        "assessments",
        "final_decision",
    ),
    WorkflowStage.COMPLETED: (
        "request",
        "scope",
        "claim_elements",
        "search_plan",
        "candidates",
        "assessments",
        "final_decision",
        "final_report",
    ),
    WorkflowStage.ERROR: (),
}


def normalize_stage(stage: WorkflowStage | str) -> WorkflowStage:
    """Normalize string or enum stage input to WorkflowStage."""
    if isinstance(stage, WorkflowStage):
        return stage
    return WorkflowStage(stage)


def can_transition(
    current: WorkflowStage | str,
    next_stage: WorkflowStage | str,
) -> bool:
    """Return whether a stage transition is allowed by static rules."""
    current_stage = normalize_stage(current)
    target_stage = normalize_stage(next_stage)
    if current_stage == target_stage:
        return True
    if target_stage == WorkflowStage.ERROR:
        return True
    return target_stage in ALLOWED_TRANSITIONS[current_stage]


def transition_or_raise(
    current: WorkflowStage | str,
    next_stage: WorkflowStage | str,
) -> WorkflowStage:
    """Return the next stage or raise if the transition is impossible."""
    current_stage = normalize_stage(current)
    target_stage = normalize_stage(next_stage)
    if not can_transition(current_stage, target_stage):
        raise WorkflowTransitionError(
            f"cannot transition from {current_stage.value} to {target_stage.value}"
        )
    return target_stage


def required_artifacts_for_stage(stage: WorkflowStage | str) -> list[str]:
    """Return artifact names required before entering a stage."""
    return list(REQUIRED_ARTIFACTS_BY_STAGE[normalize_stage(stage)])


__all__ = [
    "ALLOWED_TRANSITIONS",
    "REQUIRED_ARTIFACTS_BY_STAGE",
    "WorkflowTransitionError",
    "can_transition",
    "normalize_stage",
    "required_artifacts_for_stage",
    "transition_or_raise",
]
