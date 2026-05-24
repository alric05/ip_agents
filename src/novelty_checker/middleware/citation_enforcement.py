"""Middleware that enforces citation analysis when conditions are met.

Uses wrap_model_call to inject actionable directives into the system prompt
when A-refs exist, coverage gaps remain, and citation-researcher hasn't
been delegated yet in the current round.

This provides a code-level safety net for citation analysis — even if the
orchestrator's prompt instructions are missed or skipped, this middleware
ensures the LLM is reminded to include citation-researcher in its parallel
delegation when conditions warrant it.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage

from src.novelty_checker.middleware._backend_utils import strip_line_numbers

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from deepagents.backends.protocol import BACKEND_TYPES, BackendProtocol

_logger = logging.getLogger(__name__)


class CitationEnforcementMiddleware(AgentMiddleware):
    """Code-level enforcement of citation analysis delegation.

    Evaluates citation trigger conditions (A-refs exist + gaps remain)
    in Python code rather than relying on prompt instructions. When conditions
    are met and citation-researcher hasn't been delegated, injects a specific
    directive into the system prompt with pre-computed A-ref numbers and
    gap features.
    """

    def __init__(self, *, backend: BACKEND_TYPES) -> None:
        self._backend = backend

    def _get_backend(self, runtime: Any) -> BackendProtocol:
        """Resolve backend from instance or factory."""
        if callable(self._backend):
            return self._backend(runtime)
        return self._backend

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        """Check citation conditions and inject directive if needed."""
        request = self._maybe_inject_directive(request)
        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        """Async version: check citation conditions and inject directive."""
        request = self._maybe_inject_directive(request)
        return await handler(request)

    def _maybe_inject_directive(self, request: ModelRequest) -> ModelRequest:
        """Evaluate conditions and inject citation directive if needed.

        Returns the original request unchanged if no directive needed,
        or a new request with the directive appended to the system message.
        """
        try:
            directive = self._evaluate_citation_need(request)
            if directive:
                existing = request.system_message.content if request.system_message else ""
                new_system = SystemMessage(content=existing + "\n\n" + directive)
                return request.override(system_message=new_system)
        except Exception:
            _logger.warning(
                "CitationEnforcementMiddleware: injection skipped due to unexpected error.",
                exc_info=True,
            )

        return request

    def _evaluate_citation_need(self, request: ModelRequest) -> str | None:
        """Evaluate whether citation analysis should be triggered.

        Returns directive string if citation needed, None otherwise.
        """
        backend = self._get_backend(request.runtime)

        accumulator = self._read_accumulator(backend)
        if accumulator is None:
            return None

        # Q1: Are there A-refs?
        a_refs = self._find_a_refs(accumulator)
        if not a_refs:
            return None

        # Q2: Are there coverage gaps?
        gap_features = self._find_gap_features(accumulator)

        # Q3: Is this Round 2+?
        round_number = len(accumulator.get("rounds", []))

        if not (gap_features or round_number >= 2):
            return None

        # Check if citation-researcher was already delegated
        if self._citation_already_delegated(request):
            return None

        # Build directive
        ref_list = ", ".join(a_refs[:5])
        gap_list = ", ".join(
            f"{g.get('feature_id', '?')} ({g.get('level', 'unknown')})"
            for g in gap_features[:5]
        )

        return (
            "## >>> CITATION ANALYSIS REQUIRED (Auto-detected) <<<\n\n"
            f"A-refs available: {ref_list}\n"
            f"Features below STRONG: {gap_list or 'N/A (Round 2+ — worth exploring anyway)'}\n"
            f"Current round: {round_number + 1}\n\n"
            "**ACTION**: Include citation-researcher in your parallel delegation with:\n"
            f"- Publication numbers: {ref_list}\n"
            f"- Gap features to focus on: {gap_list or 'all features'}\n\n"
            "Citation networks discover patents using DIFFERENT VOCABULARY "
            "invisible to keyword searches."
        )

    def _read_accumulator(self, backend: BackendProtocol) -> dict | None:
        """Read findings_accumulator.json from filesystem.

        Missing-file reads are silent (expected early in a run). A read that
        returns content but fails to parse as JSON is logged at WARNING so
        corrupt-accumulator incidents aren't invisible.
        """
        for path in ("/findings_accumulator.json", "/findings_auto_accumulator.json"):
            try:
                content = backend.read(path)
            except Exception:
                continue
            # FilesystemBackend.read() returns "Error: File '...' not found"
            # as a STRING for missing files — treat as missing, not corrupt.
            if not content or content.startswith("Error"):
                continue
            # FilesystemBackend.read() prepends "<N>\t" line-number prefixes to
            # every line, so json.loads() on the raw output always fails.
            try:
                return json.loads(strip_line_numbers(content))
            except json.JSONDecodeError:
                # File exists with content that doesn't parse even after
                # stripping prefixes — a real incident (truncated write, disk
                # corruption, race). Citation enforcement skipped this turn.
                _logger.warning(
                    "CitationEnforcementMiddleware: %s exists but is not valid JSON "
                    "(len=%d). Citation delegation will not be auto-enforced this turn.",
                    path,
                    len(content),
                )
                continue
        return None

    def _find_a_refs(self, accumulator: dict) -> list[str]:
        """Extract A-ref publication numbers from accumulator."""
        a_refs = []
        for ref in accumulator.get("all_references", []):
            label = (ref.get("triage_label") or ref.get("relevance") or "").upper()
            if label == "A":
                pub = ref.get("ref_id") or ref.get("publication_number")
                if pub:
                    a_refs.append(pub)
        return a_refs

    def _find_gap_features(self, accumulator: dict) -> list[dict]:
        """Find features below STRONG coverage."""
        gaps = []
        for cov in accumulator.get("final_coverage", []):
            level = (cov.get("level") or "").lower()
            if level not in ("strong", "saturated"):
                gaps.append(cov)
        return gaps

    def _citation_already_delegated(self, request: ModelRequest) -> bool:
        """Check if citation-researcher was already delegated this round.

        Looks for recent task() calls that reference citation-researcher
        in the message history.
        """
        for msg in reversed(request.messages[-20:]):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc.get("name") == "task":
                        args = tc.get("args", {})
                        subagent = str(args.get("subagent_type", "")).lower()
                        desc = str(args.get("description", "")).lower()
                        if "citation" in subagent or "citation" in desc:
                            return True
        return False
