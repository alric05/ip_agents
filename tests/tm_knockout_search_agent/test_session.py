"""Session management tests for the TM knockout search agent."""

from __future__ import annotations

from pathlib import Path

from src.tm_knockout_search_agent.services.session import (
    AGENT_SESSION_NAMESPACE,
    artifact_path,
    create_session,
    load_session_manifest,
    read_artifact,
    read_final_report,
    session_dir_for,
    sessions_root,
    write_artifact,
    write_final_report,
)
from src.tm_knockout_search_agent.state import (
    CandidateReference,
    ClaimElement,
    KnockoutSearchRequest,
)


def test_create_session_writes_namespaced_manifest(tmp_path: Path) -> None:
    base_dir = tmp_path / "sessions"

    manifest = create_session(session_id="session-a", base_dir=base_dir)

    expected_session_dir = base_dir / AGENT_SESSION_NAMESPACE / "session-a"
    assert sessions_root(base_dir) == base_dir / AGENT_SESSION_NAMESPACE
    assert session_dir_for("session-a", base_dir=base_dir) == expected_session_dir
    assert expected_session_dir.exists()
    assert (expected_session_dir / "manifest.json").exists()
    assert not (base_dir / "session-a").exists()
    assert manifest.session_id == "session-a"
    assert manifest.artifact_paths["request"].endswith("request.json")
    assert manifest.artifact_paths["claim_elements"].endswith("claim_elements.json")


def test_create_session_generates_id_when_missing(tmp_path: Path) -> None:
    manifest = create_session(base_dir=tmp_path / "sessions")

    assert manifest.session_id
    assert session_dir_for(manifest.session_id, base_dir=tmp_path / "sessions").exists()


def test_write_and_read_structured_artifacts(tmp_path: Path) -> None:
    base_dir = tmp_path / "sessions"
    create_session(session_id="session-a", base_dir=base_dir)
    request = KnockoutSearchRequest(
        raw_user_input="Find trademark knockout risks",
        jurisdiction_constraints=["US"],
    )
    elements = [
        ClaimElement(
            id="E1",
            name="mark similarity",
            description="The proposed mark is close to an existing mark.",
            is_core=True,
        )
    ]

    request_path = write_artifact("session-a", "request", request, base_dir=base_dir)
    elements_path = write_artifact(
        "session-a",
        "claim_elements",
        elements,
        base_dir=base_dir,
    )

    loaded_request = read_artifact(
        "session-a",
        "request",
        base_dir=base_dir,
        model=KnockoutSearchRequest,
    )
    loaded_elements = read_artifact(
        "session-a",
        "claim_elements",
        base_dir=base_dir,
        model=list[ClaimElement],
    )

    assert request_path == artifact_path("session-a", "request", base_dir=base_dir)
    assert elements_path.name == "claim_elements.json"
    assert loaded_request == request
    assert loaded_elements == elements


def test_manifest_updates_when_artifacts_are_written(tmp_path: Path) -> None:
    base_dir = tmp_path / "sessions"
    initial_manifest = create_session(session_id="session-a", base_dir=base_dir)
    report = "# Final report\n\nNo knockout found in this unit test."

    report_path = write_final_report("session-a", report, base_dir=base_dir)
    updated_manifest = load_session_manifest("session-a", base_dir=base_dir)

    assert updated_manifest is not None
    assert updated_manifest.updated_at >= initial_manifest.updated_at
    assert updated_manifest.artifact_paths["final_report"] == str(report_path)
    assert "final_report" in updated_manifest.artifact_updated_at
    assert updated_manifest.artifact_sizes["final_report"] == report_path.stat().st_size
    assert read_final_report("session-a", base_dir=base_dir) == report


def test_missing_artifact_returns_none(tmp_path: Path) -> None:
    base_dir = tmp_path / "sessions"
    create_session(session_id="session-a", base_dir=base_dir)

    assert read_artifact("session-a", "scope", base_dir=base_dir) is None
    assert read_artifact("missing-session", "request", base_dir=base_dir) is None
    assert read_final_report("session-a", base_dir=base_dir) is None


def test_two_sessions_do_not_collide(tmp_path: Path) -> None:
    base_dir = tmp_path / "sessions"
    first = CandidateReference(
        id="tm-1",
        source="other",
        title="First candidate",
    )
    second = CandidateReference(
        id="tm-2",
        source="other",
        title="Second candidate",
    )

    write_artifact("session-a", "candidates", [first], base_dir=base_dir)
    write_artifact("session-b", "candidates", [second], base_dir=base_dir)

    first_path = artifact_path("session-a", "candidates", base_dir=base_dir)
    second_path = artifact_path("session-b", "candidates", base_dir=base_dir)
    first_loaded = read_artifact(
        "session-a",
        "candidates",
        base_dir=base_dir,
        model=list[CandidateReference],
    )
    second_loaded = read_artifact(
        "session-b",
        "candidates",
        base_dir=base_dir,
        model=list[CandidateReference],
    )

    assert first_path != second_path
    assert first_loaded == [first]
    assert second_loaded == [second]
    assert first_path.parent.name == "session-a"
    assert second_path.parent.name == "session-b"
