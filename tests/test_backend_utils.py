"""Tests for _backend_utils.py — the shared helper that fixes the silent
accumulator-corruption bug across 5 call sites.

Includes an end-to-end test that drives a real FilesystemBackend (not a mock)
to confirm the helper recovers a round-tripped JSON file — the exact scenario
that was silently failing in production.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.novelty_checker.middleware._backend_utils import (
    read_json_from_backend,
    strip_line_numbers,
)


class TestStripLineNumbers:
    def test_strips_cat_n_style_prefix(self):
        content = "     1\t{\n     2\t  \"a\": 1\n     3\t}"
        assert strip_line_numbers(content) == '{\n  "a": 1\n}'

    def test_idempotent_on_unprefixed_content(self):
        content = '{\n  "a": 1\n}'
        assert strip_line_numbers(content) == content

    def test_empty_string(self):
        assert strip_line_numbers("") == ""

    def test_mixed_prefixed_and_unprefixed_lines(self):
        content = "     1\tfoo\nbar\n     3\tbaz"
        assert strip_line_numbers(content) == "foo\nbar\nbaz"

    def test_preserves_tabs_inside_content(self):
        # A tab that's NOT part of a line-number prefix must survive.
        content = "     1\tkey\tvalue"
        assert strip_line_numbers(content) == "key\tvalue"


class TestReadJsonFromBackend:
    def test_line_prefixed_valid_json_is_recovered(self):
        """Critical: this is the bug that was firing on every accumulator read."""
        backend = MagicMock()
        backend.read.return_value = (
            '     1\t{\n'
            '     2\t  "rounds": [],\n'
            '     3\t  "all_references": []\n'
            '     4\t}'
        )
        result = read_json_from_backend(backend, "/accum.json")
        assert result == {"rounds": [], "all_references": []}

    def test_missing_file_error_string_returns_none(self):
        backend = MagicMock()
        backend.read.return_value = "Error: File '/accum.json' not found"
        assert read_json_from_backend(backend, "/accum.json") is None

    def test_empty_content_returns_none(self):
        backend = MagicMock()
        backend.read.return_value = ""
        assert read_json_from_backend(backend, "/accum.json") is None

    def test_exception_returns_none(self):
        backend = MagicMock()
        backend.read.side_effect = RuntimeError("backend failure")
        assert read_json_from_backend(backend, "/accum.json") is None

    def test_genuinely_corrupt_json_returns_none(self):
        backend = MagicMock()
        backend.read.return_value = "     1\tthis is not json"
        assert read_json_from_backend(backend, "/accum.json") is None

    def test_non_dict_json_returns_none(self):
        backend = MagicMock()
        backend.read.return_value = "     1\t[1, 2, 3]"
        assert read_json_from_backend(backend, "/accum.json") is None

    def test_non_string_content_returns_none(self):
        backend = MagicMock()
        backend.read.return_value = None
        assert read_json_from_backend(backend, "/accum.json") is None


class TestEndToEndWithRealFilesystemBackend:
    """Drive the actual FilesystemBackend to confirm the helper fixes the
    real-world failure mode (not just the mocked version).
    """

    def test_roundtrip_through_real_backend(self):
        from deepagents.backends import FilesystemBackend

        with tempfile.TemporaryDirectory() as td:
            backend = FilesystemBackend(root_dir=Path(td))
            payload = {
                "rounds": [{"round_number": 1, "new_refs_count": 3}],
                "all_references": [{"pub": "US12345"}, {"pub": "EP6789"}],
                "total_captures": 2,
            }
            backend.write("accum.json", json.dumps(payload, indent=2))

            raw_content = backend.read("accum.json")
            # Precondition: backend.read() DOES line-prefix the output.
            # If this ever changes, the helper becomes a no-op (fine) but
            # we want a noisy signal.
            assert raw_content.startswith("     1\t"), (
                "FilesystemBackend.read() no longer line-prefixes output — "
                "_backend_utils.strip_line_numbers() may be redundant."
            )

            # The naive call that was silently failing in production:
            with pytest.raises(json.JSONDecodeError):
                json.loads(raw_content)

            # The helper recovers the real payload.
            result = read_json_from_backend(backend, "accum.json")
            assert result == payload

    def test_missing_file_through_real_backend(self):
        from deepagents.backends import FilesystemBackend

        with tempfile.TemporaryDirectory() as td:
            backend = FilesystemBackend(root_dir=Path(td))
            assert read_json_from_backend(backend, "does_not_exist.json") is None
