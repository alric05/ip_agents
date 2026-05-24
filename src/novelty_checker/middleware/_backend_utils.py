"""Shared utilities for reading backend files safely.

`FilesystemBackend.read()` has two gotchas that silently break naive callers:

1. **Line-number prefixes.** Output is formatted like `"     1\\t{\\n     2\\t  ..."`
   — `cat -n`-style. Raw `json.loads()` fails on the leading `"     1\\t"`.
2. **Error strings.** Missing files return `"Error: File '...' not found"` as a
   normal string (not an exception). Raw `json.loads()` fails with
   `JSONDecodeError` on any of these.

Both gotchas have been handled ad-hoc in ~8 places and silently swallowed in
~5 others — so the accumulator has been invisibly resetting to empty on every
live read, and callers that depend on mid-run accumulated state (citation
enforcement, diminishing-returns detection) have been flying blind.

Use `read_json_from_backend()` for every `json.loads(backend.read(...))` site.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from deepagents.backends.protocol import BackendProtocol

_LINE_NUMBER_PREFIX_RE = re.compile(r"^\s*\d+\t")


def strip_line_numbers(content: str) -> str:
    """Remove `cat -n`-style line-number prefixes that FilesystemBackend.read()
    prepends to every line.

    Idempotent on content that doesn't have the prefix.
    """
    return "\n".join(
        _LINE_NUMBER_PREFIX_RE.sub("", line) for line in content.split("\n")
    )


def read_json_from_backend(
    backend: "BackendProtocol",
    path: str,
) -> dict[str, Any] | None:
    """Read and parse a JSON file from a backend that line-prefixes content.

    Returns None for:
      - backend exceptions
      - empty content
      - "Error: ..." strings (missing file, read failure)
      - content that doesn't parse as JSON after stripping line prefixes

    Returns the parsed dict on success.

    Callers decide what a None return means — typically "treat as if the file
    doesn't exist and use a default value", but for enforcement middleware
    that specifically wants to distinguish "missing" vs "corrupt" the caller
    can probe the backend's content directly.
    """
    try:
        content = backend.read(path)
    except Exception:
        return None
    if not content or not isinstance(content, str) or content.startswith("Error"):
        return None
    try:
        result = json.loads(strip_line_numbers(content))
    except (json.JSONDecodeError, ValueError):
        return None
    if isinstance(result, dict):
        return result
    return None
