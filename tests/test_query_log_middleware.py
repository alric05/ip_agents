"""Tests for QueryLogMiddleware."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import ToolMessage

from src.novelty_checker.middleware.query_log import (
    QueryLogger,
    QueryLogMiddleware,
    _extract_feature_ids,
    _extract_query,
    _extract_result_stats,
    _extract_round,
)


class _InMemoryBackend:
    def __init__(self) -> None:
        self.files: dict[str, str] = {}

    def read(self, path: str) -> str:
        if path not in self.files:
            return f"Error: {path} not found"
        return self.files[path]

    def write(self, path: str, content: str) -> None:
        # Mirror FilesystemBackend semantics: refuse to overwrite. The middleware
        # should reach for upload_files instead, so this path should only fire
        # for the very first write of any path.
        if path in self.files:
            raise AssertionError(
                f"Backend.write should not be called to overwrite {path}"
            )
        self.files[path] = content

    def upload_files(self, files: list[tuple[str, bytes]]) -> None:
        for path, content in files:
            self.files[path] = content.decode("utf-8")


class _FakeToolCallRequest:
    def __init__(self, name: str, args: dict[str, Any] | None = None) -> None:
        self.tool_call = {"name": name, "args": args or {}}
        self.runtime = None


def _make_result(content: str, tool_call_id: str = "call-1") -> ToolMessage:
    return ToolMessage(content=content, tool_call_id=tool_call_id)


def test_arg_extraction_helpers():
    assert _extract_query({"query": "drones AND cameras"}) == "drones AND cameras"
    assert _extract_query({"queries": ["a", "b"]}) == ["a", "b"]
    assert _extract_query({}) is None

    assert _extract_feature_ids({"feature_ids": ["F1", "F2"]}) == ["F1", "F2"]
    assert _extract_feature_ids({"features": "F3"}) == ["F3"]
    assert _extract_feature_ids({}) == []

    assert _extract_round({"round_number": 2}) == 2
    assert _extract_round({"round": "3"}) == 3
    assert _extract_round({}) is None


def test_result_stats_parses_json_results_list():
    payload = json.dumps({"results": [{"a": 1}, {"a": 2}, {"a": 3}]})
    count, err = _extract_result_stats(payload)
    assert count == 3
    assert err is None


def test_result_stats_flags_error_content():
    count, err = _extract_result_stats("\u274c Search failed: upstream 500")
    assert count is None
    assert err and "Search failed" in err


def test_result_stats_plain_text_returns_none():
    count, err = _extract_result_stats("Some narrative summary of findings.")
    assert count is None
    assert err is None


def test_middleware_records_and_writes_markdown():
    backend = _InMemoryBackend()
    logger = QueryLogger(session_id="t-log")
    mw = QueryLogMiddleware(backend=backend, logger=logger)

    request = _FakeToolCallRequest(
        "patent_keyword_search",
        {"query": "imaging lens AND drone", "feature_ids": ["F1", "F2"]},
    )
    result = _make_result(json.dumps({"results": [{"id": "x"}, {"id": "y"}]}))

    def handler(_req):
        return result

    returned = mw.wrap_tool_call(request, handler)
    assert returned is result
    assert len(logger.records) == 1

    rec = logger.records[0]
    assert rec.tool_name == "patent_keyword_search"
    assert rec.query == "imaging lens AND drone"
    assert rec.feature_ids == ["F1", "F2"]
    assert rec.results_count == 2

    md = backend.files["/queries_log.md"]
    assert "# Query Log" in md
    assert "patent_keyword_search" in md
    assert "imaging lens AND drone" in md
    assert "F1, F2" in md
    assert "**Results:** 2" in md


def test_middleware_ignores_non_search_tools():
    backend = _InMemoryBackend()
    logger = QueryLogger(session_id="t-skip")
    mw = QueryLogMiddleware(backend=backend, logger=logger)

    request = _FakeToolCallRequest("write_file", {"file_path": "/x.md"})
    result = _make_result("ok")

    mw.wrap_tool_call(request, lambda _r: result)

    assert logger.records == []
    assert "/queries_log.md" not in backend.files


def test_middleware_handles_batch_query_list():
    backend = _InMemoryBackend()
    logger = QueryLogger(session_id="t-batch")
    mw = QueryLogMiddleware(backend=backend, logger=logger)

    request = _FakeToolCallRequest(
        "batch_patent_search",
        {"queries": ["q one", "q two", "q three"], "round_number": 2},
    )
    result = _make_result("Non-JSON narrative result")

    mw.wrap_tool_call(request, lambda _r: result)

    rec = logger.records[0]
    assert rec.query == ["q one", "q two", "q three"]
    assert rec.round_number == 2

    md = backend.files["/queries_log.md"]
    assert "round 2" in md
    assert "- `q one`" in md
    assert "- `q three`" in md


def test_middleware_overwrites_log_on_subsequent_calls():
    """Second-and-later calls must still update /queries_log.md.

    FilesystemBackend.write refuses to overwrite, so the middleware must route
    through upload_files (O_TRUNC).  _InMemoryBackend.write raises in this
    test harness to fail loudly if that contract ever regresses.
    """
    backend = _InMemoryBackend()
    logger = QueryLogger(session_id="t-over")
    mw = QueryLogMiddleware(backend=backend, logger=logger)

    for i, q in enumerate(["first q", "second q", "third q"]):
        req = _FakeToolCallRequest("patent_keyword_search", {"query": q})
        mw.wrap_tool_call(req, lambda _r, _i=i: _make_result(f"[{_i}]"))

    assert len(logger.records) == 3
    md = backend.files["/queries_log.md"]
    assert "first q" in md
    assert "second q" in md
    assert "third q" in md
    assert "Total queries: 3" in md


def test_middleware_requires_logger_or_factory():
    backend = _InMemoryBackend()
    try:
        QueryLogMiddleware(backend=backend)
    except ValueError:
        return
    raise AssertionError("Expected ValueError when neither logger nor factory given")


def test_factory_mode_creates_separate_loggers_per_thread():
    backend = _InMemoryBackend()
    created: list[str] = []

    def factory(tid: str) -> QueryLogger:
        created.append(tid)
        return QueryLogger(session_id=tid)

    mw = QueryLogMiddleware(backend=backend, logger_factory=factory)

    class _Runtime:
        def __init__(self, tid: str) -> None:
            self.config = {"configurable": {"thread_id": tid}}

    req_a = _FakeToolCallRequest("npl_search", {"query": "alpha"})
    req_a.runtime = _Runtime("thread-A")
    req_b = _FakeToolCallRequest("npl_search", {"query": "beta"})
    req_b.runtime = _Runtime("thread-B")

    mw.wrap_tool_call(req_a, lambda _r: _make_result("[]"))
    mw.wrap_tool_call(req_b, lambda _r: _make_result("[]"))

    assert created == ["thread-A", "thread-B"]
    assert mw._thread_loggers["thread-A"].records[0].query == "alpha"
    assert mw._thread_loggers["thread-B"].records[0].query == "beta"
