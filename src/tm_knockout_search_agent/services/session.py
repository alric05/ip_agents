"""Deterministic session artifact helpers for TM knockout search.

These helpers are filesystem-only utilities. They do not call external APIs or
run the agent loop.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, TypeAdapter

from src.tm_knockout_search_agent.state import SessionManifest, WorkflowStage


AGENT_SESSION_NAMESPACE = "tm_knockout_search_agent"
DEFAULT_SESSIONS_BASE_DIR = Path("sessions")
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

DEFAULT_ARTIFACT_FILENAMES: dict[str, str] = {
    "manifest": "manifest.json",
    "request": "request.json",
    "scope": "scope.json",
    "search_criteria": "search_criteria.json",
    "claim_elements": "claim_elements.json",
    "search_plan": "search_plan.json",
    "query_plan": "query_plan.json",
    "candidates": "candidates.json",
    "compumark_results": "compumark_results.json",
    "web_results": "web_results.json",
    "normalized_candidates": "normalized_candidates.json",
    "ranked_findings": "ranked_findings.json",
    "source_statuses": "source_statuses.json",
    "assessments": "assessments.json",
    "risk_assessment": "risk_assessment.json",
    "adversarial_review": "adversarial_review.json",
    "llm_review": "llm_review.json",
    "final_decision": "final_decision.json",
    "final_report": "final_report.md",
}
WRITABLE_ARTIFACTS = frozenset(DEFAULT_ARTIFACT_FILENAMES) - {"manifest"}
TEXT_ARTIFACTS = frozenset({"final_report"})


def _validate_session_id(session_id: str) -> str:
    normalized = session_id.strip()
    if not normalized:
        raise ValueError("session_id must not be empty")
    if not _SESSION_ID_RE.fullmatch(normalized):
        raise ValueError(
            "session_id may only contain letters, numbers, '.', '_', and '-'"
        )
    return normalized


def _validate_artifact_name(artifact_name: str, *, writable: bool = False) -> str:
    if artifact_name not in DEFAULT_ARTIFACT_FILENAMES:
        supported = ", ".join(sorted(DEFAULT_ARTIFACT_FILENAMES))
        raise ValueError(f"unsupported artifact {artifact_name!r}; expected one of {supported}")
    if writable and artifact_name == "manifest":
        raise ValueError("use create_session() to create or update manifest.json")
    return artifact_name


def sessions_root(base_dir: str | Path = DEFAULT_SESSIONS_BASE_DIR) -> Path:
    """Return the namespaced sessions root for this agent."""
    return Path(base_dir) / AGENT_SESSION_NAMESPACE


def session_dir_for(
    session_id: str,
    *,
    base_dir: str | Path = DEFAULT_SESSIONS_BASE_DIR,
) -> Path:
    """Return the deterministic directory for a session id."""
    return sessions_root(base_dir) / _validate_session_id(session_id)


def build_artifact_paths(session_dir: str | Path) -> dict[str, str]:
    """Build default artifact paths for a session directory."""
    root = Path(session_dir)
    return {
        name: str(root / filename)
        for name, filename in DEFAULT_ARTIFACT_FILENAMES.items()
    }


def create_session_manifest(
    session_dir: str | Path,
    *,
    session_id: str | None = None,
    stage: WorkflowStage = WorkflowStage.INTAKE,
) -> SessionManifest:
    """Create an in-memory session manifest with default artifact paths."""
    resolved_session_id = _validate_session_id(session_id or str(uuid4()))
    root = Path(session_dir)
    return SessionManifest(
        session_id=resolved_session_id,
        stage=stage,
        artifact_paths=build_artifact_paths(root),
    )


def create_session(
    *,
    session_id: str | None = None,
    base_dir: str | Path = DEFAULT_SESSIONS_BASE_DIR,
    stage: WorkflowStage = WorkflowStage.INTAKE,
) -> SessionManifest:
    """Create a session directory and manifest.

    If `session_id` is omitted, a new UUID-based id is generated. If a provided
    session already has a manifest, the existing manifest is returned.
    """
    resolved_session_id = _validate_session_id(session_id or str(uuid4()))
    session_dir = session_dir_for(resolved_session_id, base_dir=base_dir)
    session_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = Path(build_artifact_paths(session_dir)["manifest"])
    if manifest_path.exists():
        return SessionManifest.read_json(manifest_path)

    manifest = create_session_manifest(
        session_dir,
        session_id=resolved_session_id,
        stage=stage,
    )
    manifest.write_json(manifest_path)
    return manifest


def load_session_manifest(
    session_id: str,
    *,
    base_dir: str | Path = DEFAULT_SESSIONS_BASE_DIR,
) -> SessionManifest | None:
    """Load a session manifest, returning None if it does not exist."""
    manifest_path = artifact_path(session_id, "manifest", base_dir=base_dir)
    if not manifest_path.exists():
        return None
    return SessionManifest.read_json(manifest_path)


def artifact_path(
    session_id: str,
    artifact_name: str,
    *,
    base_dir: str | Path = DEFAULT_SESSIONS_BASE_DIR,
) -> Path:
    """Return the deterministic path for an artifact in a session."""
    _validate_artifact_name(artifact_name)
    return session_dir_for(session_id, base_dir=base_dir) / DEFAULT_ARTIFACT_FILENAMES[artifact_name]


def _json_ready(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    return value


def _write_manifest(manifest: SessionManifest) -> Path:
    manifest_path = Path(manifest.artifact_paths["manifest"])
    return manifest.write_json(manifest_path)


def _ensure_manifest(
    session_id: str,
    *,
    base_dir: str | Path,
) -> SessionManifest:
    return load_session_manifest(session_id, base_dir=base_dir) or create_session(
        session_id=session_id,
        base_dir=base_dir,
    )


def write_artifact(
    session_id: str,
    artifact_name: str,
    artifact: Any,
    *,
    base_dir: str | Path = DEFAULT_SESSIONS_BASE_DIR,
) -> Path:
    """Write a structured artifact and update the session manifest."""
    _validate_artifact_name(artifact_name, writable=True)
    manifest = _ensure_manifest(session_id, base_dir=base_dir)
    path = artifact_path(session_id, artifact_name, base_dir=base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    if artifact_name in TEXT_ARTIFACTS:
        path.write_text(str(artifact), encoding="utf-8")
    else:
        path.write_text(
            json.dumps(_json_ready(artifact), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    updated_manifest = manifest.record_artifact(
        artifact_name,
        path,
        size_bytes=path.stat().st_size,
    )
    _write_manifest(updated_manifest)
    return path


def read_artifact(
    session_id: str,
    artifact_name: str,
    *,
    base_dir: str | Path = DEFAULT_SESSIONS_BASE_DIR,
    model: Any | None = None,
) -> Any | None:
    """Read an artifact, returning None when the artifact is missing."""
    _validate_artifact_name(artifact_name)
    path = artifact_path(session_id, artifact_name, base_dir=base_dir)
    if not path.exists():
        return None

    if artifact_name in TEXT_ARTIFACTS:
        return path.read_text(encoding="utf-8")

    raw = path.read_text(encoding="utf-8")
    if model is None:
        return json.loads(raw)
    return TypeAdapter(model).validate_json(raw)


def write_final_report(
    session_id: str,
    markdown: str,
    *,
    base_dir: str | Path = DEFAULT_SESSIONS_BASE_DIR,
) -> Path:
    """Write the final Markdown report artifact."""
    return write_artifact(
        session_id,
        "final_report",
        markdown,
        base_dir=base_dir,
    )


def read_final_report(
    session_id: str,
    *,
    base_dir: str | Path = DEFAULT_SESSIONS_BASE_DIR,
) -> str | None:
    """Read the final Markdown report artifact, returning None if missing."""
    report = read_artifact(session_id, "final_report", base_dir=base_dir)
    if report is None:
        return None
    return str(report)


__all__ = [
    "AGENT_SESSION_NAMESPACE",
    "DEFAULT_ARTIFACT_FILENAMES",
    "DEFAULT_SESSIONS_BASE_DIR",
    "TEXT_ARTIFACTS",
    "WRITABLE_ARTIFACTS",
    "artifact_path",
    "build_artifact_paths",
    "create_session",
    "create_session_manifest",
    "load_session_manifest",
    "read_artifact",
    "read_final_report",
    "session_dir_for",
    "sessions_root",
    "write_artifact",
    "write_final_report",
]
