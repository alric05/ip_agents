"""Stage detection and backend resolution for the structured API.

Reuses the existing ``_resolve_orchestrator_stage`` heuristic from the
telemetry module, which inspects filesystem artifacts (``/scope.md``,
``/features.md``, ``/final_report.md``) and message history.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from deepagents.backends import FilesystemBackend

from src.novelty_checker.observability.telemetry import (
    STAGE_FEATURES,
    STAGE_REPORT,
    STAGE_RESEARCH,
    STAGE_SCOPING,
    _file_exists_on_backend,
    _resolve_orchestrator_stage,
)

_logger = logging.getLogger(__name__)


# Map internal telemetry stage constants → API stage names
_STAGE_MAP: dict[str, str] = {
    STAGE_SCOPING: "scoping",
    STAGE_FEATURES: "features",
    STAGE_RESEARCH: "researching",
    STAGE_REPORT: "complete",
}


def detect_stage(backend: Any, messages: list[Any]) -> str:
    """Detect the current API stage from filesystem + messages.

    Args:
        backend: A FilesystemBackend for the current thread.
        messages: The full message history from the graph state.

    Returns:
        One of: ``"scoping"``, ``"features"``, ``"researching"``, ``"complete"``.
    """
    internal = _resolve_orchestrator_stage(backend, messages)
    return _STAGE_MAP.get(internal, "scoping")


def detect_status(stage: str, has_report: bool) -> str:
    """Determine the API status field based on current stage.

    Returns:
        One of: ``"awaiting_input"``, ``"processing"``, ``"done"``.
    """
    if stage == "complete" and has_report:
        return "done"
    if stage == "researching":
        return "processing"
    return "awaiting_input"


def get_backend_for_thread(
    backend_factory: Any,
    thread_id: str,
    sessions_dir: Path | None = None,
) -> FilesystemBackend:
    """Resolve a FilesystemBackend for a given thread_id.

    First checks the factory's internal cache. If not found, creates a
    new backend pointing to ``sessions_dir / thread_id``.

    Args:
        backend_factory: A ``ThreadAwareBackendFactory`` instance.
        thread_id: The thread ID to resolve.
        sessions_dir: Fallback root sessions directory. If None, uses
            the factory's ``_sessions_dir``.

    Returns:
        A FilesystemBackend rooted at the thread's session directory.
    """
    # Try the factory cache first (no ToolRuntime needed)
    cache = getattr(backend_factory, "_cache", {})
    if thread_id in cache:
        return cache[thread_id]

    # Create a fresh backend for reading
    root = sessions_dir or getattr(backend_factory, "_sessions_dir", None)
    if root is None:
        raise ValueError("Cannot resolve backend: no sessions_dir available")

    session_path = Path(root) / thread_id
    return FilesystemBackend(root_dir=session_path, virtual_mode=True)
