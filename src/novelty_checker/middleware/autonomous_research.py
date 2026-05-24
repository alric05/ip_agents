"""Middleware that enforces autonomous operation after Gate 2 confirmation.

Uses wrap_model_call to detect when the user has confirmed features (Gate 2
has been passed) and injects a strong autonomy directive into the system
prompt on every subsequent LLM call.

This prevents the agent from asking the user for input during the research
loop — all CONTINUE/STOP decisions must be made internally by the
orchestrator using think_tool.

This provides a code-level safety net — even if the prompt instructions are
missed in the long AGENTS.md document, this middleware dynamically injects
the autonomy requirement at every model call.
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

# Markers that indicate the feature matrix has been presented to the user
_FEATURE_PRESENTED_MARKERS = ("Feature Matrix", "CONFIRMATION REQUIRED", "Stage 2 Gate")

# Markers that indicate the user has confirmed features
_CONFIRMATION_MARKERS = ("confirm",)

_AUTONOMY_DIRECTIVE = (
    "## >>> AUTONOMOUS MODE ACTIVE (Post Gate 2) <<<\n\n"
    "The user has confirmed features at Gate 2. You are now in FULLY "
    "AUTONOMOUS research mode.\n\n"
    "**ABSOLUTE RULES — VIOLATION IS A CRITICAL ERROR:**\n"
    "1. Do NOT ask the user ANY questions\n"
    "2. Do NOT present intermediate results as options for the user\n"
    "3. Do NOT say 'Would you like me to...', 'Shall I...', "
    "'If you want...', or similar\n"
    "4. ALL CONTINUE/STOP decisions are YOURS ALONE — make them "
    "internally using think_tool\n"
    "5. The ONLY thing the user sees next is the FINAL REPORT\n"
    "6. Sub-agent recommendations (CONTINUE/STOP) are INTERNAL inputs "
    "to YOUR decision — do NOT relay them to the user\n\n"
    "Proceed silently through all research rounds until coverage target "
    "is met or max iterations reached, then deliver the final report."
)


class AutonomousResearchMiddleware(AgentMiddleware):
    """Code-level enforcement of autonomous operation after Gate 2.

    Checks two conditions:
    1. Has /features.md been written to disk? (features defined)
    2. Has the user confirmed features after seeing the Feature Matrix?

    If BOTH conditions are true (Gate 2 passed), injects an autonomy
    directive into the system prompt to prevent the agent from asking
    the user for any input during the research loop.
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
        """Check autonomy conditions and inject directive if needed."""
        request = self._maybe_inject_directive(request)
        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        """Async version: check autonomy conditions and inject directive."""
        request = self._maybe_inject_directive(request)
        return await handler(request)

    def _maybe_inject_directive(self, request: ModelRequest) -> ModelRequest:
        """Evaluate gate conditions and inject autonomy directive if needed.

        Returns the original request unchanged if Gate 2 not yet passed,
        or a new request with the autonomy directive appended to system message.
        """
        try:
            if self._is_post_gate2(request):
                existing = request.system_message.content if request.system_message else ""
                new_system = SystemMessage(content=existing + "\n\n" + _AUTONOMY_DIRECTIVE)
                return request.override(system_message=new_system)
        except Exception as e:
            _logger.debug(f"AutonomousResearch: skipping due to error: {e}")

        return request

    def _is_post_gate2(self, request: ModelRequest) -> bool:
        """Check if Gate 2 has been passed (features presented AND confirmed)."""
        backend = self._get_backend(request.runtime)

        # Condition 1: /features.md must exist on disk
        if not self._features_file_exists(backend):
            return False

        # Condition 2: Feature Matrix must have been presented AND confirmed
        return self._features_confirmed(request)

    def _features_file_exists(self, backend: BackendProtocol) -> bool:
        """Check if /features.md exists on the backend filesystem."""
        try:
            content = backend.read("/features.md")
            return bool(content and content.strip())
        except Exception:
            return False

    def _features_confirmed(self, request: ModelRequest) -> bool:
        """Check if Gate 2 passed: features presented + user confirmed."""
        feature_presented = False

        for msg in request.messages:
            msg_type = getattr(msg, "type", None)
            content = self._get_content(msg)

            if msg_type in ("ai", "assistant"):
                # Check if AI presented the Feature Matrix
                if any(marker in content for marker in _FEATURE_PRESENTED_MARKERS):
                    feature_presented = True

            elif msg_type == "human" and feature_presented:
                # Check if user confirmed after feature presentation
                if any(marker in content.lower() for marker in _CONFIRMATION_MARKERS):
                    return True

        return False

    @staticmethod
    def _get_content(msg: Any) -> str:
        """Extract string content from a message."""
        content = getattr(msg, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            # Handle multimodal messages (list of dicts with "text" keys)
            return " ".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
        return str(content)
