"""Middleware that enforces `write_file('/final_report.md', ...)` at wrap-up.

Companion to `ResearchContinuationMiddleware`. That one guards the
research loop; this one guards the post-research synthesis step —
specifically the one where the orchestrator is prone to emitting the
full 11-section report as chat content without persisting it to disk.

Observed failure mode (C19904, session 20260415_082308_00fc3c78):
the LLM produced a 30K-char well-formatted report as its final chat
message and never called `write_file('/final_report.md', ...)`. Scorers
then saw an empty artifact and `report_section_completeness` scored 0.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from deepagents.backends.protocol import BACKEND_TYPES, BackendProtocol

_logger = logging.getLogger(__name__)

# Tool-call names a later AIMessage may carry that indicate the report
# has either just been persisted or is being persisted — once one of
# these fires for /final_report.md we stop injecting.
_WRITE_TOOLS = frozenset({"write_file", "edit_file"})

_FINAL_REPORT_PATH = "/final_report.md"

# Markers that signal the LLM is producing (or about to produce) the
# final report as chat content. Kept in sync with eval_runner._DONE_MARKERS.
_REPORT_CONTENT_MARKERS = (
    "Final Report",
    "## 1.",
    "## Executive Summary",
    "Key Finding / Executive Summary",
)


class ReportPersistenceMiddleware(AgentMiddleware):
    """Force the orchestrator to call write_file('/final_report.md', ...).

    Fires when:
      1. features.md exists on disk (post Gate 2 — research has started), AND
      2. at least one findings file exists on disk (a round has completed), AND
      3. final_report.md does NOT yet exist on disk, AND
      4. no prior write_file/edit_file call in the conversation targeted
         `/final_report.md` (so we don't re-nudge after the fact).

    When all four hold, the middleware appends a hard directive to the
    system message: "Your NEXT action MUST be write_file('/final_report.md',
    <full 11-section report>). Do not emit the report as chat content
    before the file is persisted."

    This complements `_autosave_final_report` in eval_runner (that's the
    runtime safety net); this middleware fixes the underlying behavior
    so the autosave only fires when something has genuinely gone wrong.
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
            if self._should_inject(request):
                directive = self._build_directive()
                existing = request.system_message.content if request.system_message else ""
                new_system = SystemMessage(content=existing + "\n\n" + directive)
                return request.override(system_message=new_system)
        except Exception:
            _logger.warning(
                "ReportPersistenceMiddleware: injection skipped due to unexpected error. "
                "backend=%r final_report_path=%s",
                type(self._backend).__name__,
                _FINAL_REPORT_PATH,
                exc_info=True,
            )
        return request

    def _should_inject(self, request: ModelRequest) -> bool:
        backend = self._get_backend(request.runtime)

        if not self._file_is_nonempty(backend, "/features.md"):
            return False
        if not self._any_findings_exist(backend):
            return False
        if self._file_is_nonempty(backend, _FINAL_REPORT_PATH):
            return False
        if self._report_write_already_issued(request):
            return False
        return True

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

    def _any_findings_exist(self, backend: "BackendProtocol") -> bool:
        probes = (
            "/findings/round_1.md",
            "/findings/patent_round_1.md",
            "/findings/npl_round_1.md",
            "/findings/semantic_round_1.md",
            "/findings_accumulator.json",
            "/findings_auto_accumulator.json",
            "/references.md",
        )
        for path in probes:
            if self._file_is_nonempty(backend, path):
                return True
        return False

    # --- message-history probe --------------------------------------------

    @staticmethod
    def _report_write_already_issued(request: ModelRequest) -> bool:
        """True if any prior AIMessage called write_file on final_report.md."""
        for msg in request.messages:
            tool_calls = getattr(msg, "tool_calls", None)
            if not tool_calls:
                continue
            for tc in tool_calls:
                if tc.get("name") not in _WRITE_TOOLS:
                    continue
                args = tc.get("args", {}) or {}
                path = (
                    args.get("file_path")
                    or args.get("path")
                    or args.get("filename")
                    or ""
                )
                if isinstance(path, str) and "final_report" in path.lower():
                    return True
        return False

    # --- directive ---------------------------------------------------------

    @staticmethod
    def _build_directive() -> str:
        return (
            "## >>> FINAL REPORT PERSISTENCE REQUIRED (Auto-detected) <<<\n"
            "\n"
            "Research has produced findings and `/features.md` is in place, but "
            "`/final_report.md` does NOT yet exist on disk. The evaluation "
            "harness reads this file directly — chat-only report text is NOT "
            "scored.\n"
            "\n"
            "**MANDATORY NEXT ACTION (before you output the report as chat):**\n"
            "\n"
            "Call `write_file` with these arguments:\n"
            "```\n"
            "write_file(\n"
            "    file_path=\"/final_report.md\",\n"
            "    content=<the complete report as a single markdown string>,\n"
            ")\n"
            "```\n"
            "\n"
            "Requirements for the content:\n"
            "- Your standard 11-section report from the `report` skill (Key "
            "Finding/Executive Summary, Scope, Feature Plan, Feature Matrix, "
            "Peripherally Related References, Patents Record View, NPL Record "
            "View, Transactional Search Summary, Landscape Overview, Search "
            "Traceability, Next Steps).\n"
            "- **MANDATORY APPENDIX** — after section 11, append these four H2 "
            "headers EXACTLY (the evaluation scorers key off the literal text):\n"
            "  - `## Novelty Assessment` — feature-by-feature novelty synthesis. "
            "End the section with a line in this EXACT format (one of the three "
            "literal tokens, no other phrasing — the scorer matches on it):\n"
            "    ```\n"
            "    **Verdict: not_novel**\n"
            "    ```\n"
            "    (or `**Verdict: novel**` or `**Verdict: partially_novel**`).\n"
            "    **VERDICT RULE**: pick `not_novel` whenever every core feature has "
            "at least ONE independent earlier reference with Y or Y1 coverage — "
            "partial (Y1) coverage counts as anticipated. Pick `partially_novel` "
            "ONLY when at least one core feature is genuinely `novel` (no Y/Y1 from "
            "any independent earlier ref). Do NOT default to `partially_novel` as a "
            "cautious middle just because a match is weak. See the full decision "
            "rule in the `report` skill under `Verdict decision rule`.\n"
            "  - `## Risk Assessment` — Low/Medium/High aggregate risk + top 3 "
            "anticipating refs (2-3 sentences).\n"
            "  - `## Limitations` — bulleted list of databases/dates/languages "
            "not covered + known coverage gaps.\n"
            "  - `## Verdict` — single-line restatement of the verdict in the "
            "same exact format above, plus one paragraph of rationale.\n"
            "- Every non-trivial claim cited with a publication number / DOI in "
            "brackets.\n"
            "- **FEATURE MATRIX FULL-TEXT RULE**: before assigning any Y / Y1 / "
            "N cell for an A- or B-rated reference in Section 4 (Feature Matrix), "
            "call `get_patent_details(publication_number=<pub>)` to fetch the "
            "full claims and DWPI detailed description. The short abstract + "
            "first-claim snippet you saw during search is NOT sufficient — "
            "feature-limitation language is routinely buried in later claims "
            "and the detailed description. Mark `N` only when absence is "
            "confirmed in the full-text payload. See the `report` skill's "
            "'Before filling Y / Y1 / N cells' block for the worked example.\n"
            "- Do NOT emit the report text as a chat message before the "
            "`write_file` call completes. The write_file call must come FIRST.\n"
            "\n"
            "After `write_file` returns successfully, THEN output the full report "
            "content in your chat response so the user can read it inline.\n"
        )
