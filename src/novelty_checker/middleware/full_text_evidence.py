"""Middleware that forces `get_patent_details` fetches before the Feature
Matrix is finalised.

Companion to `ReportPersistenceMiddleware`. That one guards the WRITE of
`/final_report.md`; this one guards the DATA QUALITY of its Section 4
(Feature Matrix). Observed failure mode (C19904, multiple sessions):

  The agent lists 15-36 A/B refs in `/references.md`, but never calls
  `get_patent_details(publication_number=<pub>)` before filling the
  Y / Y1 / N cells. It grades from the short abstract + first-claim
  snippet returned by landscape search, missing feature-limitation
  language buried in later claims and the DWPI detailed description.
  Concrete example: US11319035B2 full claims include "a plurality of
  floats... arranged in a row in a vertical direction" — exactly F3
  (four-pontoon retention) — but the agent marks F3=N because that text
  is in `cl`, not `cl1`, and the landscape payload omits `cl`.

The prompt mandate for this fetch (in report skill §4 and the
`ReportPersistenceMiddleware` directive) has empirically failed to
trigger the call on live runs (0 fetches observed across several
sessions). This middleware is the hard guard.

Fires when:
  1. `/features.md` exists (research has started), AND
  2. `/references.md` exists with ≥3 A- or B-rated rows, AND
  3. `/final_report.md` does NOT yet exist, AND
  4. Fewer `get_patent_details` tool calls appear in conversation
     history than half the A/B ref count (rounded up).

Action: append a blocking directive to the system prompt that names the
specific publication numbers still missing a fetch, and forbids writing
`/final_report.md` until each one has been fetched.
"""

from __future__ import annotations

import logging
import math
import re
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from deepagents.backends.protocol import BACKEND_TYPES, BackendProtocol

_logger = logging.getLogger(__name__)

_FINAL_REPORT_PATH = "/final_report.md"
_REFERENCES_PATH = "/references.md"
_FEATURES_PATH = "/features.md"

# How much of the A/B ref set must be fetched before the directive goes
# silent. 0.5 = half the refs. We don't require 100% because (a) some
# pubs may error out of Derwent and the agent should still be able to
# write the report, and (b) the agent may batch-fetch the most critical
# refs and gracefully proceed.
_FETCH_COVERAGE_THRESHOLD = 0.5

# Parse `| US11319035B2 | ... | A | ... |` style rows.
_REF_ROW_RE = re.compile(
    r"^\s*\|\s*([A-Z]{2}\d{5,}[A-Z0-9]*)\s*\|",
    re.MULTILINE,
)

# Strip the `cat -n`-style line-number prefix the filesystem backend
# prepends to read() output.
_LINE_NUMBER_PREFIX_RE = re.compile(r"^\s*\d+\t")


class FullTextEvidenceMiddleware(AgentMiddleware):
    """Force `get_patent_details(<pub>)` on each A/B ref before report write.

    See module docstring for the failure mode this targets.
    """

    def __init__(self, *, backend: "BACKEND_TYPES") -> None:
        self._backend = backend

    # ------------------------------------------------------------------
    # AgentMiddleware hooks
    # ------------------------------------------------------------------

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: "Callable[[ModelRequest], ModelResponse]",
    ) -> ModelCallResult:
        request = self._maybe_inject_directive(request)
        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: "Callable[[ModelRequest], Awaitable[ModelResponse]]",
    ) -> ModelCallResult:
        request = self._maybe_inject_directive(request)
        return await handler(request)

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def _get_backend(self, runtime: Any) -> "BackendProtocol":
        if callable(self._backend):
            return self._backend(runtime)
        return self._backend

    def _maybe_inject_directive(self, request: ModelRequest) -> ModelRequest:
        try:
            missing = self._compute_missing_fetches(request)
            if not missing:
                return request
            directive = self._build_directive(missing)
            existing = request.system_message.content if request.system_message else ""
            new_system = SystemMessage(content=existing + "\n\n" + directive)
            return request.override(system_message=new_system)
        except Exception:  # pragma: no cover — safety net
            _logger.warning(
                "FullTextEvidenceMiddleware: injection skipped due to unexpected error. "
                "backend=%r references_path=%s final_report_path=%s",
                type(self._backend).__name__,
                _REFERENCES_PATH,
                _FINAL_REPORT_PATH,
                exc_info=True,
            )
        return request

    # ------------------------------------------------------------------
    # Filesystem + message probes (split for testability)
    # ------------------------------------------------------------------

    def _compute_missing_fetches(self, request: ModelRequest) -> list[str]:
        """Return A/B pubs still needing a `get_patent_details` call.

        Returns an empty list when no injection is warranted (either the
        preconditions aren't met, the threshold is already satisfied, or
        there is no `/references.md` to read).
        """
        backend = self._get_backend(request.runtime)

        if not self._file_is_nonempty(backend, _FEATURES_PATH):
            return []
        if self._file_is_nonempty(backend, _FINAL_REPORT_PATH):
            return []

        ab_pubs = self._extract_ab_pubs(backend)
        if len(ab_pubs) < 3:
            # Too few A/B refs to be worth the guard. Fall through —
            # this middleware is for substantive runs.
            return []

        fetched = self._fetched_pubs_from_history(request)
        missing = [p for p in ab_pubs if p not in fetched]

        needed = math.ceil(len(ab_pubs) * _FETCH_COVERAGE_THRESHOLD)
        already = len(ab_pubs) - len(missing)
        if already >= needed:
            return []

        return missing

    # --- filesystem probes -------------------------------------------------

    @staticmethod
    def _file_is_nonempty(backend: "BackendProtocol", path: str) -> bool:
        try:
            content = backend.read(path)
        except Exception:
            return False
        if not isinstance(content, str):
            return False
        return bool(content.strip()) and not content.startswith("Error")

    @classmethod
    def _extract_ab_pubs(cls, backend: "BackendProtocol") -> list[str]:
        """Parse `/references.md` and return publication numbers whose
        triage column is A or B. Preserves order of appearance and
        deduplicates."""
        try:
            raw = backend.read(_REFERENCES_PATH)
        except Exception:
            return []
        if not isinstance(raw, str) or not raw.strip():
            return []

        # Strip the `cat -n` prefix before parsing.
        cleaned_lines = []
        for line in raw.splitlines():
            cleaned_lines.append(_LINE_NUMBER_PREFIX_RE.sub("", line))
        cleaned = "\n".join(cleaned_lines)

        seen: set[str] = set()
        pubs: list[str] = []
        triage_idx: int | None = None
        pub_idx: int | None = None

        for line in cleaned.splitlines():
            s = line.strip()
            if not s.startswith("|"):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            lowered = [c.lower() for c in cells]

            # Header detection (first table-like row we see).
            if pub_idx is None:
                for i, c in enumerate(lowered):
                    if c in ("publication number", "pub number", "pub. number", "ref id"):
                        pub_idx = i
                    elif c in ("relevance", "triage", "triage label", "label"):
                        triage_idx = i
                if pub_idx is not None and triage_idx is not None:
                    continue  # done with header
                continue

            if all(set(c) <= set("-:") for c in cells if c):
                # markdown separator
                continue
            if pub_idx >= len(cells) or (triage_idx is not None and triage_idx >= len(cells)):
                continue

            pub = cells[pub_idx]
            triage = (
                cells[triage_idx].upper().replace("*", "").strip()
                if triage_idx is not None else ""
            )
            if triage not in ("A", "B"):
                continue
            if not pub or pub in seen:
                continue
            seen.add(pub)
            pubs.append(pub)
        return pubs

    # --- message-history probe --------------------------------------------

    @staticmethod
    def _fetched_pubs_from_history(request: ModelRequest) -> set[str]:
        """Collect every publication number passed to `get_patent_details`
        in any prior AI message's tool_calls."""
        fetched: set[str] = set()
        for msg in request.messages:
            tool_calls = getattr(msg, "tool_calls", None)
            if not tool_calls:
                continue
            for tc in tool_calls:
                if tc.get("name") != "get_patent_details":
                    continue
                args = tc.get("args", {}) or {}
                pub = (
                    args.get("publication_number")
                    or args.get("pub_number")
                    or args.get("pn")
                    or ""
                )
                if isinstance(pub, str) and pub.strip():
                    fetched.add(pub.strip())
        return fetched

    # ------------------------------------------------------------------
    # Directive
    # ------------------------------------------------------------------

    @staticmethod
    def _build_directive(missing_pubs: list[str]) -> str:
        listed = "\n".join(f"  - {p}" for p in missing_pubs[:20])
        more = "" if len(missing_pubs) <= 20 else (
            f"\n  ...and {len(missing_pubs) - 20} more in /references.md."
        )
        return (
            "## >>> FULL-TEXT EVIDENCE GUARD (Auto-detected) <<<\n"
            "\n"
            f"{len(missing_pubs)} A- or B-rated reference(s) in "
            "`/references.md` still have NO `get_patent_details` call in "
            "this conversation. The short abstract + first-claim snippet "
            "from landscape search is NOT sufficient evidence to grade "
            "the Feature Matrix — feature-limitation language is "
            "routinely buried in later claims and the DWPI detailed "
            "description, both of which landscape queries omit. Writing "
            "`/final_report.md` before fetching full text for these "
            "refs produces silently-wrong Y / Y1 / N cells (observed on "
            "C19904: US11319035B2 F3 marked N when the full claims say "
            '"a plurality of floats arranged in a row in a vertical '
            'direction" — clearly the four-pontoon feature).\n'
            "\n"
            "**MANDATORY NEXT ACTIONS — do these BEFORE any `write_file` "
            "call targeting `/final_report.md`:**\n"
            "\n"
            "1. For each publication number listed below, call:\n"
            "   ```\n"
            "   get_patent_details(publication_number=<pub>)\n"
            "   ```\n"
            "2. Read the returned full claims (`## Claims`) and DWPI "
            "detailed description (`## DWPI Description`).\n"
            "3. Re-grade that ref's Y / Y1 / N cells in your Feature "
            "Matrix against that fuller content. When in doubt between "
            "Y1 and N, prefer Y1. Mark N only when the full text does "
            "not disclose the feature — not merely because the abstract "
            "didn't mention it.\n"
            "4. After at least half of these refs have been fetched, "
            "this directive goes silent and you may write "
            "`/final_report.md`.\n"
            "\n"
            "Publication numbers still missing a fetch:\n"
            f"{listed}{more}\n"
            "\n"
            "Do NOT write `/final_report.md` before fulfilling the "
            "fetch requirement. The evaluation harness will flag "
            "feature_coverage_accuracy failures when this is skipped.\n"
        )
