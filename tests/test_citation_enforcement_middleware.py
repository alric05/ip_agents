"""Regression tests for CitationEnforcementMiddleware accumulator handling.

The middleware reads /findings_accumulator.json from a backend that returns
"Error: File '...' not found" as a STRING (not an exception) for missing
files. We must treat those error-strings as missing, not as corrupt JSON —
otherwise a WARN fires 28+ times per run on every early turn.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from src.novelty_checker.middleware.citation_enforcement import (
    CitationEnforcementMiddleware,
)


def _make_backend(responses: dict[str, str]) -> MagicMock:
    """Fake backend whose read() returns the string mapped to each path."""
    backend = MagicMock()
    backend.read.side_effect = lambda path: responses.get(
        path, f"Error: File '{path}' not found"
    )
    return backend


class TestReadAccumulatorMissingFile:
    def test_error_string_is_silent_and_returns_none(self, caplog):
        """Backend's 'Error: File ... not found' must not trigger WARNING."""
        backend = _make_backend({})  # every path returns "Error: ... not found"
        mw = CitationEnforcementMiddleware(backend=backend)

        with caplog.at_level(logging.WARNING, logger="src.novelty_checker.middleware.citation_enforcement"):
            result = mw._read_accumulator(backend)

        assert result is None
        # The critical assertion: no WARNING was logged for the missing file.
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert not warnings, (
            f"Expected no WARNING on missing accumulator, got {len(warnings)}: "
            f"{[r.message for r in warnings]}"
        )

    def test_empty_content_is_silent(self, caplog):
        backend = _make_backend({
            "/findings_accumulator.json": "",
            "/findings_auto_accumulator.json": "",
        })
        mw = CitationEnforcementMiddleware(backend=backend)

        with caplog.at_level(logging.WARNING):
            result = mw._read_accumulator(backend)

        assert result is None
        assert not [r for r in caplog.records if r.levelno == logging.WARNING]

    def test_valid_json_returns_parsed_dict(self):
        backend = _make_backend({
            "/findings_accumulator.json": '{"rounds": [], "all_references": []}',
        })
        mw = CitationEnforcementMiddleware(backend=backend)

        result = mw._read_accumulator(backend)

        assert result == {"rounds": [], "all_references": []}

    def test_truly_corrupt_json_logs_warning(self, caplog):
        """The WARNING must still fire for genuinely non-JSON content."""
        backend = _make_backend({
            "/findings_accumulator.json": "this-is-not-json-and-not-an-error-string",
            "/findings_auto_accumulator.json": "{also broken",
        })
        mw = CitationEnforcementMiddleware(backend=backend)

        with caplog.at_level(logging.WARNING, logger="src.novelty_checker.middleware.citation_enforcement"):
            result = mw._read_accumulator(backend)

        assert result is None
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 2
        assert "not valid JSON" in warnings[0].message

    def test_falls_through_to_second_path(self):
        """If first accumulator is missing, second path is tried."""
        backend = _make_backend({
            "/findings_auto_accumulator.json": '{"all_references": [{"a": 1}]}',
        })
        mw = CitationEnforcementMiddleware(backend=backend)

        result = mw._read_accumulator(backend)

        assert result == {"all_references": [{"a": 1}]}
