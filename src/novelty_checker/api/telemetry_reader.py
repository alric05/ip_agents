"""Safe concurrent-read utility for telemetry.json files.

Reads the token_usage section from per-thread telemetry files written by
TelemetryMiddleware. Designed to be called from FastAPI request handlers
while the middleware may be writing concurrently.

Concurrent-write safety:
    TelemetryMiddleware._write_to_disk() uses json.dump() directly (no
    atomic rename), so a concurrent read could catch partial JSON.  We
    mitigate this by wrapping json.loads(read_text()) in a try/except —
    returning None on parse failure.  The SSE loop fires token_usage on
    every on_chat_model_end, so one failed read is harmless; the next
    model call triggers a fresh read.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

_EMPTY_USAGE: dict[str, Any] = {
    "by_stage": {},
    "by_agent": {},
    "cumulative": {},
}


def read_token_usage(sessions_dir: Path, thread_id: str) -> dict[str, Any] | None:
    """Read token_usage from a thread's telemetry.json.

    Args:
        sessions_dir: Root sessions directory (e.g. ``<project>/sessions``).
        thread_id: LangGraph thread ID.

    Returns:
        Dict with ``by_stage``, ``by_agent``, ``cumulative`` keys, or
        ``None`` if the file is missing or unparseable.
    """
    telemetry_path = sessions_dir / thread_id / "telemetry.json"

    if not telemetry_path.is_file():
        return None

    try:
        raw = telemetry_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        _logger.debug("Failed to read telemetry for thread %s: %s", thread_id, exc)
        return None

    token_usage = data.get("token_usage")
    if not isinstance(token_usage, dict):
        return None

    # Normalize: ensure all three top-level keys are present
    return {
        "by_stage": token_usage.get("by_stage", {}),
        "by_agent": token_usage.get("by_agent", {}),
        "cumulative": token_usage.get("cumulative", {}),
    }


def thread_exists(sessions_dir: Path, thread_id: str) -> bool:
    """Check whether a thread's session directory exists.

    Args:
        sessions_dir: Root sessions directory.
        thread_id: LangGraph thread ID.

    Returns:
        True if the session directory for *thread_id* exists on disk.
    """
    return (sessions_dir / thread_id).is_dir()
