"""Middleware that logs every search query to a markdown and a JSON file.

Passive observer that intercepts ``wrap_tool_call`` for the search-tool set
already tracked by :mod:`src.novelty_checker.observability.telemetry`, and
writes two artifacts to the session workspace after each call:

- ``/queries_log.md``  — human-readable log with one section per query.
- ``/queries_log.json`` — structured JSON suitable for programmatic consumption,
  containing ``session_id``, ``started_at``, ``total_queries``, and a
  ``queries`` array with fields: ``index``, ``timestamp``, ``tool_name``,
  ``subagent``, ``query``, ``feature_ids``, ``round_number``,
  ``results_count``, and ``error``.

Both files are fully rewritten (not appended) after every search call because
``FilesystemBackend`` exposes no append primitive and session files are small.

Follows the same dual-mode pattern as ``PatentTrackingMiddleware``:

- **Static mode** (CLI): provide a single ``QueryLogger`` instance.
- **Factory mode** (LangGraph Studio): provide a ``logger_factory`` callable
  that creates per-thread ``QueryLogger`` instances.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

from src.novelty_checker.observability.telemetry import (
    _SEARCH_TOOLS_FOR_ARG_CAPTURE,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langgraph.prebuilt.tool_node import ToolCallRequest
    from langgraph.types import Command

    from deepagents.backends.protocol import BACKEND_TYPES, BackendProtocol

_logger = logging.getLogger(__name__)

_QUERIES_LOG_PATH = "/queries_log.md"
_QUERIES_LOG_JSON_PATH = "/queries_log.json"

# Argument keys that may carry the query text, in priority order.
_QUERY_ARG_KEYS = ("query", "queries", "search_query", "q")

# Argument keys that may carry a round number.
_ROUND_ARG_KEYS = ("round_number", "round")

# Argument keys that may carry feature ids.
_FEATURE_ARG_KEYS = ("feature_ids", "features")


@dataclass
class QueryRecord:
    """One row in the query log."""

    timestamp: str
    tool_name: str
    subagent: str
    query: Any  # str or list[str]
    feature_ids: list[str] = field(default_factory=list)
    round_number: int | None = None
    results_count: int | None = None
    error: str | None = None


class QueryLogger:
    """Per-thread accumulator for search-query records."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.records: list[QueryRecord] = []

    def add(self, record: QueryRecord) -> None:
        self.records.append(record)
        
    def render_json(self) -> str:
        records = [
            {
                "index": idx,
                "timestamp": rec.timestamp,
                "tool_name": rec.tool_name,
                "subagent": rec.subagent,
                "query": rec.query,
                "feature_ids": rec.feature_ids,
                "round_number": rec.round_number,
                "results_count": rec.results_count,
                "error": rec.error,
            }
            for idx, rec in enumerate(self.records, start=1)
        ]
        payload = {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "total_queries": len(self.records),
            "queries": records,
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def render_markdown(self) -> str:
        lines: list[str] = [
            "# Query Log",
            "",
            f"_Session: `{self.session_id}`_",
            f"_Started: {self.started_at}_",
            f"_Total queries: {len(self.records)}_",
            "",
        ]
        if not self.records:
            lines.append("_No search queries recorded yet._")
            lines.append("")
            return "\n".join(lines)

        for idx, rec in enumerate(self.records, start=1):
            header_bits = [f"#{idx}", rec.tool_name]
            if rec.round_number is not None:
                header_bits.append(f"round {rec.round_number}")
            if rec.subagent and rec.subagent != "orchestrator":
                header_bits.append(rec.subagent)
            lines.append(f"## {' — '.join(header_bits)}")
            lines.append(f"- **At:** {rec.timestamp}")
            lines.append(f"- **Tool:** `{rec.tool_name}`")
            if rec.subagent:
                lines.append(f"- **Agent:** {rec.subagent}")
            if isinstance(rec.query, list):
                lines.append("- **Queries:**")
                for q in rec.query:
                    lines.append(f"  - `{q}`")
            elif rec.query is not None:
                lines.append(f"- **Query:** `{rec.query}`")
            else:
                lines.append("- **Query:** _(not present in args)_")
            if rec.feature_ids:
                lines.append(
                    "- **Features:** " + ", ".join(str(f) for f in rec.feature_ids)
                )
            if rec.results_count is not None:
                lines.append(f"- **Results:** {rec.results_count}")
            if rec.error:
                lines.append(f"- **Error:** {rec.error}")
            lines.append("")

        return "\n".join(lines)


class QueryLogMiddleware(AgentMiddleware):
    """Passive middleware that writes ``/queries_log.md`` after each search call.

    Args:
        backend: Backend instance or factory used to write the markdown artifact.
        logger: Static ``QueryLogger`` instance (CLI mode).
        logger_factory: Callable ``(thread_id) -> QueryLogger`` (Studio mode).
    """

    def __init__(
        self,
        *,
        backend: BACKEND_TYPES,
        logger: QueryLogger | None = None,
        logger_factory: Callable[[str], QueryLogger] | None = None,
    ) -> None:
        if logger is None and logger_factory is None:
            raise ValueError("Provide either logger or logger_factory")
        self._backend = backend
        self._static_logger = logger
        self._logger_factory = logger_factory
        self._thread_loggers: dict[str, QueryLogger] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Resolver helpers
    # ------------------------------------------------------------------

    def _get_backend(self, runtime: Any) -> BackendProtocol:
        if callable(self._backend):
            return self._backend(runtime)
        return self._backend

    def _get_logger(self, runtime: Any) -> QueryLogger:
        if self._static_logger is not None:
            return self._static_logger

        from src.novelty_checker.backend_factory import extract_thread_id

        thread_id = extract_thread_id(runtime) or "__default__"
        with self._lock:
            if thread_id not in self._thread_loggers:
                if self._logger_factory is not None:
                    self._thread_loggers[thread_id] = self._logger_factory(thread_id)
                else:
                    self._thread_loggers[thread_id] = QueryLogger(
                        session_id=thread_id
                    )
            return self._thread_loggers[thread_id]

    # ------------------------------------------------------------------
    # Middleware hooks
    # ------------------------------------------------------------------

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        result = handler(request)
        self._process(request, result)
        return result

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        result = await handler(request)
        await asyncio.to_thread(self._process, request, result)
        return result

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def _process(
        self,
        request: ToolCallRequest,
        result: ToolMessage | Command[Any],
    ) -> None:
        tool_name = request.tool_call.get("name", "")
        if tool_name not in _SEARCH_TOOLS_FOR_ARG_CAPTURE:
            return

        try:
            record = self._build_record(request, result)
        except Exception as e:  # noqa: BLE001
            _logger.debug(f"QueryLog: failed to build record for {tool_name}: {e}")
            return

        try:
            logger = self._get_logger(request.runtime)
            logger.add(record)
            backend = self._get_backend(request.runtime)
            _overwrite(backend, _QUERIES_LOG_PATH, logger.render_markdown())
            _overwrite(backend, _QUERIES_LOG_JSON_PATH, logger.render_json())
        except Exception as e:  # noqa: BLE001
            _logger.warning(f"QueryLog: failed to persist query for {tool_name}: {e}")

    # ------------------------------------------------------------------
    # Record building
    # ------------------------------------------------------------------

    def _build_record(
        self,
        request: ToolCallRequest,
        result: ToolMessage | Command[Any],
    ) -> QueryRecord:
        from src.novelty_checker.backend_factory import extract_agent_name

        tool_name = request.tool_call.get("name", "")
        args: dict[str, Any] = request.tool_call.get("args", {}) or {}

        query = _extract_query(args)
        feature_ids = _extract_feature_ids(args)
        round_number = _extract_round(args)
        subagent = extract_agent_name(request.runtime) if request.runtime else ""

        content = result.content if isinstance(result, ToolMessage) else str(result)
        results_count, error = _extract_result_stats(content)

        return QueryRecord(
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            tool_name=tool_name,
            subagent=subagent,
            query=query,
            feature_ids=feature_ids,
            round_number=round_number,
            results_count=results_count,
            error=error,
        )


# ----------------------------------------------------------------------
# Arg / result parsing helpers
# ----------------------------------------------------------------------


def _extract_query(args: dict[str, Any]) -> Any:
    for key in _QUERY_ARG_KEYS:
        if key in args and args[key] not in (None, "", []):
            return args[key]
    return None


def _extract_feature_ids(args: dict[str, Any]) -> list[str]:
    for key in _FEATURE_ARG_KEYS:
        val = args.get(key)
        if isinstance(val, (list, tuple)):
            return [str(v) for v in val]
        if isinstance(val, str) and val:
            return [val]
    return []


def _extract_round(args: dict[str, Any]) -> int | None:
    for key in _ROUND_ARG_KEYS:
        val = args.get(key)
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
    return None


def _overwrite(backend: Any, path: str, content: str) -> None:
    """Write ``content`` to ``path``, replacing any existing file.

    ``FilesystemBackend.write`` refuses to overwrite and silently returns a
    ``WriteResult(error=...)`` if the file already exists.  Since the query
    log is rewritten after every search call, we use ``upload_files`` which
    opens with ``O_TRUNC`` and overwrites cleanly.  Falls back to ``write``
    if the backend doesn't expose ``upload_files``.
    """
    upload = getattr(backend, "upload_files", None)
    if callable(upload):
        upload([(path, content.encode("utf-8"))])
        return
    backend.write(path, content)


def _extract_result_stats(content: Any) -> tuple[int | None, str | None]:
    """Best-effort parse of results_count and error string from tool content."""
    if content is None:
        return None, None

    text = content if isinstance(content, str) else str(content)
    stripped = text.strip()

    if stripped.startswith("\u274c") or stripped.lower().startswith("error"):
        collapsed = " | ".join(line for line in stripped.splitlines() if line.strip())
        return None, collapsed[:2000]

    if stripped.startswith("{") or stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
        except (ValueError, TypeError):
            parsed = None
        if isinstance(parsed, dict):
            for key in ("results_count", "count", "total"):
                if isinstance(parsed.get(key), int):
                    return parsed[key], None
            results = parsed.get("results")
            if isinstance(results, list):
                return len(results), None
        elif isinstance(parsed, list):
            return len(parsed), None

    return None, None
