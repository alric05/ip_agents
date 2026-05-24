"""Workflow stage tests for the TM knockout search agent."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.tm_knockout_search_agent.middleware.stage_guard import (
    StageGuardError,
    guard_transition,
    missing_required_artifacts,
    update_session_stage,
)
from src.tm_knockout_search_agent.services.session import (
    create_session,
    load_session_manifest,
    write_artifact,
    write_final_report,
)
from src.tm_knockout_search_agent.services.workflow import (
    WorkflowTransitionError,
    can_transition,
    required_artifacts_for_stage,
    transition_or_raise,
)
from src.tm_knockout_search_agent.state import (
    CandidateReference,
    ClaimElement,
    FinalDecision,
    KnockoutAssessment,
    KnockoutSearchRequest,
    QueryGroup,
    SearchPlan,
    SearchScope,
    WorkflowStage,
)


def _write_request_and_scope(base_dir: Path, session_id: str = "session-a") -> None:
    write_artifact(
        session_id,
        "request",
        KnockoutSearchRequest(raw_user_input="Find trademark knockout conflicts"),
        base_dir=base_dir,
    )
    write_artifact(
        session_id,
        "scope",
        SearchScope(
            normalized_technical_problem="trademark knockout search",
            key_product_system_process="proposed mark clearance",
            must_have_elements=["similar mark", "related goods"],
        ),
        base_dir=base_dir,
    )


def _write_claim_elements(base_dir: Path, session_id: str = "session-a") -> None:
    write_artifact(
        session_id,
        "claim_elements",
        [
            ClaimElement(
                id="E1",
                name="similar mark",
                description="The candidate mark resembles the proposed mark.",
                is_core=True,
            )
        ],
        base_dir=base_dir,
    )


def _write_search_plan(base_dir: Path, session_id: str = "session-a") -> None:
    write_artifact(
        session_id,
        "search_plan",
        SearchPlan(
            target_sources=["other"],
            query_groups=[
                QueryGroup(
                    id="G1",
                    source="other",
                    claim_element_ids=["E1"],
                    queries=["similar mark related goods"],
                )
            ],
        ),
        base_dir=base_dir,
    )


def _write_candidates(base_dir: Path, session_id: str = "session-a") -> None:
    write_artifact(
        session_id,
        "candidates",
        [
            CandidateReference(
                id="tm-candidate-1",
                source="other",
                title="Similar mark candidate",
            )
        ],
        base_dir=base_dir,
    )


def _write_assessments(base_dir: Path, session_id: str = "session-a") -> None:
    write_artifact(
        session_id,
        "assessments",
        [
            KnockoutAssessment(
                candidate_reference_id="tm-candidate-1",
                covered_core_elements=["E1"],
                score=90,
                label="STRONG_KNOCKOUT",
                rationale="The core mark similarity element is covered.",
            )
        ],
        base_dir=base_dir,
    )


def _write_final_decision(base_dir: Path, session_id: str = "session-a") -> None:
    write_artifact(
        session_id,
        "final_decision",
        FinalDecision(
            status="KNOCKOUT_FOUND",
            top_candidates=["tm-candidate-1"],
            limitations=["Unit-test artifact only"],
        ),
        base_dir=base_dir,
    )


def test_static_transition_rules_are_deterministic() -> None:
    assert can_transition(
        WorkflowStage.INTAKE,
        WorkflowStage.AWAITING_SCOPE_CONFIRMATION,
    )
    assert can_transition(WorkflowStage.SCREENING, WorkflowStage.SEARCHING)
    assert can_transition(WorkflowStage.SCREENING, WorkflowStage.DECISION_READY)
    assert can_transition(WorkflowStage.REPORT_READY, WorkflowStage.ERROR)
    assert not can_transition(WorkflowStage.INTAKE, WorkflowStage.SEARCHING)

    assert transition_or_raise(
        WorkflowStage.SEARCH_PLAN_READY,
        WorkflowStage.SEARCHING,
    ) == WorkflowStage.SEARCHING

    with pytest.raises(WorkflowTransitionError, match="cannot transition"):
        transition_or_raise(WorkflowStage.INTAKE, WorkflowStage.COMPLETED)


def test_required_artifacts_for_stage_are_explicit() -> None:
    assert required_artifacts_for_stage(WorkflowStage.INTAKE) == []
    assert {
        "claim_elements",
        "search_plan",
    }.issubset(required_artifacts_for_stage(WorkflowStage.SEARCHING))
    assert "assessments" in required_artifacts_for_stage(WorkflowStage.DECISION_READY)
    assert "final_decision" in required_artifacts_for_stage(WorkflowStage.REPORT_READY)
    assert "final_report" in required_artifacts_for_stage(WorkflowStage.COMPLETED)


def test_stage_guard_blocks_searching_without_elements_and_plan(tmp_path: Path) -> None:
    base_dir = tmp_path / "sessions"
    create_session(
        session_id="session-a",
        base_dir=base_dir,
        stage=WorkflowStage.SEARCH_PLAN_READY,
    )

    with pytest.raises(StageGuardError) as exc_info:
        guard_transition(
            "session-a",
            WorkflowStage.SEARCH_PLAN_READY,
            WorkflowStage.SEARCHING,
            base_dir=base_dir,
        )

    assert {"claim_elements", "search_plan"}.issubset(
        set(exc_info.value.missing_artifacts)
    )


def test_stage_guard_allows_searching_when_required_artifacts_exist(
    tmp_path: Path,
) -> None:
    base_dir = tmp_path / "sessions"
    create_session(
        session_id="session-a",
        base_dir=base_dir,
        stage=WorkflowStage.SEARCH_PLAN_READY,
    )
    _write_request_and_scope(base_dir)
    _write_claim_elements(base_dir)
    _write_search_plan(base_dir)

    target = guard_transition(
        "session-a",
        WorkflowStage.SEARCH_PLAN_READY,
        WorkflowStage.SEARCHING,
        base_dir=base_dir,
    )

    assert target == WorkflowStage.SEARCHING
    assert missing_required_artifacts(
        "session-a",
        WorkflowStage.SEARCHING,
        base_dir=base_dir,
    ) == []


def test_stage_guard_blocks_decision_report_and_completion_without_artifacts(
    tmp_path: Path,
) -> None:
    base_dir = tmp_path / "sessions"
    create_session(
        session_id="session-a",
        base_dir=base_dir,
        stage=WorkflowStage.SCREENING,
    )
    _write_request_and_scope(base_dir)
    _write_claim_elements(base_dir)
    _write_search_plan(base_dir)
    _write_candidates(base_dir)

    with pytest.raises(StageGuardError) as decision_error:
        guard_transition(
            "session-a",
            WorkflowStage.SCREENING,
            WorkflowStage.DECISION_READY,
            base_dir=base_dir,
        )
    assert decision_error.value.missing_artifacts == ["assessments"]

    _write_assessments(base_dir)
    with pytest.raises(StageGuardError) as report_error:
        guard_transition(
            "session-a",
            WorkflowStage.DECISION_READY,
            WorkflowStage.REPORT_READY,
            base_dir=base_dir,
        )
    assert report_error.value.missing_artifacts == ["final_decision"]

    _write_final_decision(base_dir)
    with pytest.raises(StageGuardError) as completed_error:
        guard_transition(
            "session-a",
            WorkflowStage.REPORT_READY,
            WorkflowStage.COMPLETED,
            base_dir=base_dir,
        )
    assert completed_error.value.missing_artifacts == ["final_report"]


def test_update_session_stage_writes_manifest_after_guard_passes(tmp_path: Path) -> None:
    base_dir = tmp_path / "sessions"
    create_session(session_id="session-a", base_dir=base_dir)
    _write_request_and_scope(base_dir)

    updated = update_session_stage(
        "session-a",
        WorkflowStage.AWAITING_SCOPE_CONFIRMATION,
        base_dir=base_dir,
    )
    loaded = load_session_manifest("session-a", base_dir=base_dir)

    assert updated.stage == WorkflowStage.AWAITING_SCOPE_CONFIRMATION
    assert loaded is not None
    assert loaded.stage == WorkflowStage.AWAITING_SCOPE_CONFIRMATION


def test_completed_stage_requires_final_report(tmp_path: Path) -> None:
    base_dir = tmp_path / "sessions"
    create_session(
        session_id="session-a",
        base_dir=base_dir,
        stage=WorkflowStage.REPORT_READY,
    )
    _write_request_and_scope(base_dir)
    _write_claim_elements(base_dir)
    _write_search_plan(base_dir)
    _write_candidates(base_dir)
    _write_assessments(base_dir)
    _write_final_decision(base_dir)
    write_final_report("session-a", "# Final report\n", base_dir=base_dir)

    updated = update_session_stage(
        "session-a",
        WorkflowStage.COMPLETED,
        base_dir=base_dir,
    )

    assert updated.stage == WorkflowStage.COMPLETED
