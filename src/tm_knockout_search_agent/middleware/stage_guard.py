"""Deterministic artifact-aware workflow stage guard.

This module is intentionally not LangGraph middleware yet. It is a small
workflow guard that future middleware can call without relying on LLM output.
"""

from __future__ import annotations

from pathlib import Path

from src.tm_knockout_search_agent.services.session import (
    DEFAULT_SESSIONS_BASE_DIR,
    artifact_path,
    create_session,
    load_session_manifest,
)
from src.tm_knockout_search_agent.services.workflow import (
    required_artifacts_for_stage,
    transition_or_raise,
)
from src.tm_knockout_search_agent.state import SessionManifest, WorkflowStage


class StageGuardError(ValueError):
    """Raised when required artifacts are missing for a workflow stage."""

    def __init__(
        self,
        stage: WorkflowStage,
        missing_artifacts: list[str],
    ) -> None:
        self.stage = stage
        self.missing_artifacts = missing_artifacts
        missing = ", ".join(missing_artifacts)
        super().__init__(
            f"cannot enter {stage.value}; missing required artifacts: {missing}"
        )


def missing_required_artifacts(
    session_id: str,
    stage: WorkflowStage | str,
    *,
    base_dir: str | Path = DEFAULT_SESSIONS_BASE_DIR,
) -> list[str]:
    """Return missing artifacts required before entering a stage."""
    return [
        artifact_name
        for artifact_name in required_artifacts_for_stage(stage)
        if not artifact_path(session_id, artifact_name, base_dir=base_dir).exists()
    ]


def assert_required_artifacts(
    session_id: str,
    stage: WorkflowStage | str,
    *,
    base_dir: str | Path = DEFAULT_SESSIONS_BASE_DIR,
) -> None:
    """Raise StageGuardError if stage-required artifacts are missing."""
    target_stage = WorkflowStage(stage)
    missing = missing_required_artifacts(
        session_id,
        target_stage,
        base_dir=base_dir,
    )
    if missing:
        raise StageGuardError(target_stage, missing)


def guard_transition(
    session_id: str,
    current: WorkflowStage | str,
    next_stage: WorkflowStage | str,
    *,
    base_dir: str | Path = DEFAULT_SESSIONS_BASE_DIR,
) -> WorkflowStage:
    """Validate static transition rules and required session artifacts."""
    target_stage = transition_or_raise(current, next_stage)
    assert_required_artifacts(session_id, target_stage, base_dir=base_dir)
    return target_stage


def update_session_stage(
    session_id: str,
    next_stage: WorkflowStage | str,
    *,
    base_dir: str | Path = DEFAULT_SESSIONS_BASE_DIR,
) -> SessionManifest:
    """Update the manifest stage after deterministic guard checks pass."""
    manifest = load_session_manifest(session_id, base_dir=base_dir) or create_session(
        session_id=session_id,
        base_dir=base_dir,
    )
    target_stage = guard_transition(
        session_id,
        manifest.stage,
        next_stage,
        base_dir=base_dir,
    )
    updated_manifest = manifest.with_stage(target_stage)
    updated_manifest.write_json(updated_manifest.artifact_paths["manifest"])
    return updated_manifest


__all__ = [
    "StageGuardError",
    "assert_required_artifacts",
    "guard_transition",
    "missing_required_artifacts",
    "update_session_stage",
]
