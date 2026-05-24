"""Middleware that enforces research loop continuation after subagent results.

Uses wrap_model_call to detect when the orchestrator has just received
subagent results (task() ToolMessages) but hasn't yet reflected or
persisted findings. When conditions are met (research active, rounds
remaining), injects a strong continuation directive into the system
prompt.

This provides a code-level safety net — even if the orchestrator's
prompt instructions about the research loop are missed or forgotten
after processing large subagent results, this middleware dynamically
injects a continuation requirement at the critical moment.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from deepagents.backends.protocol import BACKEND_TYPES, BackendProtocol

_logger = logging.getLogger(__name__)

# Tool names that indicate post-result processing has occurred
_PROCESSING_TOOLS = frozenset({
    "think_tool",
    "save_round_findings",
    "write_file",
    "edit_file",
})


class ResearchContinuationMiddleware(AgentMiddleware):
    """Code-level enforcement of research loop continuation.

    Detects when the orchestrator has received subagent results from a
    research round but hasn't yet reflected or persisted, and injects a
    continuation directive into the system prompt to prevent premature
    stopping.

    Args:
        backend: Backend instance or factory for filesystem checks.
        max_rounds: Maximum number of research rounds allowed. Default 5.
        min_rounds: Minimum rounds to guarantee before allowing stop. Default 2.
    """

    def __init__(
        self,
        *,
        backend: BACKEND_TYPES,
        max_rounds: int = 5,
        min_rounds: int = 2,
    ) -> None:
        self._backend = backend
        self._max_rounds = max_rounds
        self._min_rounds = min_rounds

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
        """Check continuation conditions and inject directive if needed."""
        request = self._maybe_inject_directive(request)
        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        """Async version: check continuation conditions and inject directive."""
        request = self._maybe_inject_directive(request)
        return await handler(request)

    # ------------------------------------------------------------------
    # Core directive logic
    # ------------------------------------------------------------------

    def _maybe_inject_directive(self, request: ModelRequest) -> ModelRequest:
        """Evaluate conditions and inject continuation directive if needed."""
        try:
            directive = self._evaluate_continuation_need(request)
            if directive:
                existing = request.system_message.content if request.system_message else ""
                new_system = SystemMessage(content=existing + "\n\n" + directive)
                return request.override(system_message=new_system)
        except Exception as e:
            _logger.debug(f"ResearchContinuation: skipping due to error: {e}")

        return request

    def _evaluate_continuation_need(self, request: ModelRequest) -> str | None:
        """Evaluate whether a continuation directive should be injected.

        Returns directive string if continuation needed, None otherwise.
        """
        backend = self._get_backend(request.runtime)

        # Precondition 1: Research must be active (features.md exists = post Gate 2)
        if not self._is_research_active(backend):
            return None

        # Precondition 2: Must have just received subagent results without processing
        if not self._has_unprocessed_task_results(request):
            return None

        # Count completed rounds (from filesystem + message history)
        completed_rounds = self._count_completed_rounds(backend, request)

        # If we've hit max rounds, don't inject continuation
        if completed_rounds >= self._max_rounds:
            return None

        # Current round = the one just received but not yet processed
        current_round = completed_rounds + 1

        return self._build_directive(current_round, completed_rounds)

    # ------------------------------------------------------------------
    # Precondition checks
    # ------------------------------------------------------------------

    def _is_research_active(self, backend: BackendProtocol) -> bool:
        """Check if research is active (features.md exists on disk)."""
        try:
            content = backend.read("/features.md")
            return bool(content and content.strip() and not content.startswith("Error"))
        except Exception:
            return False

    def _has_unprocessed_task_results(self, request: ModelRequest) -> bool:
        """Check if the most recent messages are task() results without processing.

        Walks backward from the end of message history. If 2+ task()
        ToolMessage results are found at the tail with no intervening
        think_tool / save_round_findings call, the orchestrator is about
        to skip the loop.
        """
        messages = request.messages
        if len(messages) < 2:
            return False

        # Build set of all task() tool_call_ids for lookup
        task_call_ids: set[str] = set()
        for msg in messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc.get("name") == "task":
                        tc_id = tc.get("id", "")
                        if tc_id:
                            task_call_ids.add(tc_id)

        if not task_call_ids:
            return False

        # Walk backward to check the tail pattern
        task_results_found = 0
        processing_found = False

        for msg in reversed(messages):
            msg_type = getattr(msg, "type", None)

            if msg_type == "tool":
                tool_call_id = getattr(msg, "tool_call_id", None)
                if tool_call_id and tool_call_id in task_call_ids:
                    task_results_found += 1
                # Non-task tool result: continue walking

            elif msg_type in ("ai", "assistant"):
                tool_calls = getattr(msg, "tool_calls", None) or []
                tool_names = {tc.get("name", "") for tc in tool_calls}

                if tool_names & _PROCESSING_TOOLS:
                    # Processing tool called after task results -> already handled
                    processing_found = True
                    break

                if "task" in tool_names:
                    # Reached the AIMessage that dispatched these tasks -> stop
                    break

                # Other AIMessage (text only) after task results -> model responded
                if task_results_found > 0:
                    break

            elif msg_type == "human":
                break

        return task_results_found >= 2 and not processing_found

    # ------------------------------------------------------------------
    # Round counting
    # ------------------------------------------------------------------

    def _count_completed_rounds(
        self, backend: BackendProtocol, request: ModelRequest
    ) -> int:
        """Count completed research rounds.

        Primary: probe filesystem for /findings/*_round_N.md files.
        Fallback: scan message history for processed task batches.
        """
        fs_rounds = self._count_rounds_from_filesystem(backend)
        if fs_rounds > 0:
            return fs_rounds
        return self._count_rounds_from_messages(request)

    def _count_rounds_from_filesystem(self, backend: BackendProtocol) -> int:
        """Count completed rounds from filesystem findings files.

        Probes for /findings/{prefix}_round_{N}.md for each round number.
        A unique round number found = 1 completed round.
        """
        round_numbers: set[int] = set()
        prefixes = ("patent_round_", "npl_round_", "semantic_round_", "round_")

        for round_num in range(1, self._max_rounds + 1):
            for prefix in prefixes:
                path = f"/findings/{prefix}{round_num}.md"
                try:
                    content = backend.read(path)
                    if content and content.strip() and not content.startswith("Error"):
                        round_numbers.add(round_num)
                        break  # Found at least one file for this round
                except Exception:
                    continue

        return len(round_numbers)

    def _count_rounds_from_messages(self, request: ModelRequest) -> int:
        """Count completed rounds from message history.

        A completed round = a batch of 2+ task() calls whose results
        were followed by at least one processing tool call.
        """
        messages = request.messages
        completed = 0
        in_task_batch = False
        task_results_received = False

        for msg in messages:
            msg_type = getattr(msg, "type", None)

            if msg_type in ("ai", "assistant"):
                tool_calls = getattr(msg, "tool_calls", None) or []
                task_count = sum(1 for tc in tool_calls if tc.get("name") == "task")
                tool_names = {tc.get("name", "") for tc in tool_calls}

                if task_count >= 2:
                    # New batch of task() dispatches
                    if in_task_batch and task_results_received:
                        # Previous batch led to a new batch -> count it
                        completed += 1
                    in_task_batch = True
                    task_results_received = False

                elif tool_names & _PROCESSING_TOOLS and task_results_received:
                    # Processing after task results -> round completed
                    completed += 1
                    in_task_batch = False
                    task_results_received = False

            elif msg_type == "tool" and in_task_batch:
                task_results_received = True

        return completed

    # ------------------------------------------------------------------
    # Directive construction
    # ------------------------------------------------------------------

    def _build_directive(self, current_round: int, completed_rounds: int) -> str:
        """Build the continuation directive text."""
        remaining = self._max_rounds - current_round
        min_remaining = max(0, self._min_rounds - current_round)

        parts = [
            "## >>> RESEARCH CONTINUATION REQUIRED (Auto-detected) <<<\n",
            f"**Round {current_round} of {self._max_rounds} subagent results just received.**\n",
        ]

        if current_round < self._min_rounds:
            parts.append(
                f"\n**MINIMUM {self._min_rounds} ROUNDS REQUIRED** — you have only completed "
                f"{completed_rounds} round(s). You MUST continue.\n"
            )

        parts.append(
            "\n**MANDATORY NEXT STEPS (do ALL of these IN ORDER):**\n"
            "\n"
            "1. **PERSIST** this round's findings immediately:\n"
            f"   Call `save_round_findings(round_number={current_round}, source=\"all\", ...)` "
            "with the references found by subagents.\n"
            "\n"
            "2. **REFLECT** using `think_tool` with the Coverage Analysis template:\n"
            "   - Map ALL references from this round to features\n"
            "   - Calculate per-feature coverage levels (NONE/WEAK/MODERATE/STRONG)\n"
            "   - Identify gap features still below target\n"
            "   - Check for diminishing returns\n"
            "\n"
            "3. **DECIDE** autonomously (NEVER ask the user):\n"
        )

        if current_round < self._min_rounds:
            parts.append(
                f"   - You have NOT yet reached the minimum of {self._min_rounds} rounds\n"
                f"   - You MUST continue to Round {current_round + 1} regardless of coverage\n"
            )
        else:
            parts.append(
                "   - IF coverage >= 70% AND core features STRONG -> STOP and write report\n"
                "   - ELSE IF gaps remain AND rounds remaining -> CONTINUE\n"
                "   - ELSE -> STOP and proceed with available coverage\n"
            )

        parts.append(
            "\n"
            "4. **IF CONTINUING** — dispatch the next round:\n"
            f"   - Prepare gap-filling context for Round {current_round + 1}\n"
            "   - Include ALL task() calls in a SINGLE response for parallel execution\n"
            "   - Target gap features with refined queries\n"
            "   - Include citation-researcher if A-refs or B-refs exist\n"
            f"\n**Rounds remaining: {remaining} | Min rounds left: {min_remaining}**\n"
            "\n"
            "DO NOT skip steps 1-3. DO NOT generate a final report without reflecting first.\n"
            "DO NOT ask the user anything — you are in fully autonomous mode."
        )

        return "".join(parts)
