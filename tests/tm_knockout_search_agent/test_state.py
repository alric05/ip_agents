"""State and artifact model tests for the TM knockout search agent."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.tm_knockout_search_agent.services.session import (
    build_artifact_paths,
    create_session_manifest,
)
from src.tm_knockout_search_agent.state import (
    CandidateReference,
    ClaimBreakdown,
    ClaimElement,
    ElementMapping,
    EvidenceSnippet,
    FinalDecision,
    KnockoutAssessment,
    KnockoutSearchRequest,
    QueryGroup,
    SearchPlan,
    SearchScope,
    SessionManifest,
    TMKnockoutState,
    WorkflowStage,
)


def _element(
    element_id: str,
    *,
    is_core: bool = True,
    name: str = "sensor",
) -> ClaimElement:
    return ClaimElement(
        id=element_id,
        name=name,
        description=f"{name} element",
        is_core=is_core,
        synonyms_search_terms=[" detector ", "detector", ""],
    )


def test_request_scope_breakdown_and_plan_normalize_lists() -> None:
    request = KnockoutSearchRequest(
        raw_user_input=" Find knockout prior art ",
        jurisdiction_constraints=["US", " EP ", "US", ""],
        source_constraints=["patent", "npl"],
        claim_text="A sensor system claim.",
    )
    scope = SearchScope(
        normalized_technical_problem="detecting leaks",
        key_product_system_process="leak detection sensor",
        must_have_elements=["sensor", " alert ", "sensor", ""],
        exclusions=["marketing pages", "marketing pages"],
        assumptions=["English-language sources", ""],
    )
    breakdown = ClaimBreakdown(
        elements=[
            _element("E1", name="sensor"),
            _element("E2", is_core=False, name="alert"),
        ]
    )
    plan = SearchPlan(
        target_sources=["patent", "npl", "patent"],
        query_groups=[
            QueryGroup(
                id=" G1 ",
                source="patent",
                claim_element_ids=["E1", "E1", ""],
                queries=["leak detector alert", " leak detector alert ", ""],
            )
        ],
        priority_order=["G1", "G1", ""],
    )

    assert request.raw_user_input == "Find knockout prior art"
    assert request.jurisdiction_constraints == ["US", "EP"]
    assert scope.must_have_elements == ["sensor", "alert"]
    assert scope.exclusions == ["marketing pages"]
    assert breakdown.elements[0].synonyms_search_terms == ["detector"]
    assert plan.target_sources == ["patent", "npl"]
    assert plan.query_groups[0].id == "G1"
    assert plan.query_groups[0].claim_element_ids == ["E1"]
    assert plan.query_groups[0].queries == ["leak detector alert"]


def test_claim_element_ids_must_be_sequential() -> None:
    with pytest.raises(ValidationError, match="sequential starting at E1"):
        ClaimBreakdown(elements=[_element("E1"), _element("E3")])


def test_claim_breakdown_requires_core_element() -> None:
    with pytest.raises(ValidationError, match="core claim element"):
        ClaimBreakdown(
            elements=[
                _element("E1", is_core=False),
                _element("E2", is_core=False),
            ]
        )


def test_candidate_reference_requires_stable_id() -> None:
    with pytest.raises(ValidationError):
        CandidateReference(id=" ", source="patent", title="Example patent")

    candidate = CandidateReference(
        id="US-123",
        source="patent",
        title=" Example patent ",
        assignee_authors=[" Inventor A ", "Inventor A", ""],
        url="https://example.com/patent/US-123",
    )

    assert candidate.id == "US-123"
    assert candidate.title == "Example patent"
    assert candidate.assignee_authors == ["Inventor A"]


def test_evidence_mapping_and_assessment_validation() -> None:
    evidence = EvidenceSnippet(
        candidate_reference_id="US-123",
        claim_element_id="E1",
        text="The reference discloses a leak detector.",
        source_field="abstract",
        confidence=0.8,
    )
    mapping = ElementMapping(
        candidate_reference_id="US-123",
        claim_element_id="E1",
        coverage="PARTIAL",
        rationale="The sensor is present, but the alert path is incomplete.",
    )
    assessment = KnockoutAssessment(
        candidate_reference_id="US-123",
        covered_core_elements=["E1", "E1", ""],
        missing_core_elements=["E2"],
        score=65,
        label="POSSIBLE_KNOCKOUT",
        rationale="One core element appears covered.",
    )

    assert evidence.confidence == 0.8
    assert mapping.coverage == "PARTIAL"
    assert assessment.covered_core_elements == ["E1"]

    with pytest.raises(ValidationError):
        EvidenceSnippet(
            candidate_reference_id="US-123",
            claim_element_id="E1",
            text="snippet",
            confidence=1.01,
        )

    with pytest.raises(ValidationError):
        KnockoutAssessment(
            candidate_reference_id="US-123",
            score=101,
            label="STRONG_KNOCKOUT",
            rationale="Too high.",
        )


def test_final_decision_json_round_trip(tmp_path: Path) -> None:
    decision = FinalDecision(
        status="POSSIBLE_KNOCKOUT_FOUND",
        top_candidates=["US-123", "US-123", ""],
        limitations=["No full text reviewed", "No full text reviewed", ""],
    )
    path = tmp_path / "final_decision.json"

    written_path = decision.write_json(path)
    loaded = FinalDecision.read_json(written_path)

    assert loaded == decision
    assert loaded.top_candidates == ["US-123"]
    assert loaded.limitations == ["No full text reviewed"]


def test_session_manifest_helpers(tmp_path: Path) -> None:
    session_dir = tmp_path / "session"
    paths = build_artifact_paths(session_dir)
    manifest = create_session_manifest(
        session_dir,
        session_id="session-1",
        stage=WorkflowStage.SEARCH_PLAN_READY,
    )

    assert Path(paths["request"]).name == "request.json"
    assert manifest.session_id == "session-1"
    assert manifest.stage == WorkflowStage.SEARCH_PLAN_READY
    assert manifest.artifact_paths["manifest"].endswith("manifest.json")

    touched = manifest.touch()
    assert touched.updated_at >= manifest.updated_at

    manifest_path = manifest.write_json(tmp_path / "manifest.json")
    loaded = SessionManifest.read_json(manifest_path)
    assert loaded.session_id == "session-1"


def test_tm_knockout_state_holds_artifacts(tmp_path: Path) -> None:
    request = KnockoutSearchRequest(raw_user_input="Find knockout prior art")
    breakdown = ClaimBreakdown(elements=[_element("E1")])
    manifest = create_session_manifest(tmp_path, session_id="session-1")

    state = TMKnockoutState(
        request=request,
        claim_breakdown=breakdown,
        session_manifest=manifest,
    )

    assert state.current_stage == WorkflowStage.INTAKE
    assert state.request == request
    assert state.claim_breakdown == breakdown
    assert state.session_manifest == manifest
