"""Middleware that enforces feature confirmation (Gate 2) before research.

Uses wrap_model_call to detect when features have been defined (via
/features.md on disk) but the user has NOT confirmed them yet. If the
agent tries to proceed to research without confirmation, injects a
stop directive into the system prompt.

This provides a code-level safety net — even if the orchestrator's prompt
instructions are missed, this middleware blocks premature research starts.
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


class FeatureConfirmationMiddleware(AgentMiddleware):
    """Code-level enforcement of feature confirmation gate (Gate 2).

    Checks two conditions:
    1. Has /features.md been written to disk? (features defined)
    2. Has the user confirmed after seeing the Feature Matrix?

    If features exist but no confirmation follows, injects a stop directive
    into the system prompt to prevent the agent from starting research.
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
        """Check feature gate and inject directive if needed."""
        request = self._maybe_inject_directive(request)
        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        """Async version: check feature gate and inject directive."""
        request = self._maybe_inject_directive(request)
        return await handler(request)

    def _maybe_inject_directive(self, request: ModelRequest) -> ModelRequest:
        """Evaluate gate conditions and inject stop directive if needed.

        Returns the original request unchanged if no directive needed,
        or a new request with the directive appended to the system message.
        """
        try:
            directive = self._evaluate_feature_gate(request)
            if directive:
                existing = request.system_message.content if request.system_message else ""
                new_system = SystemMessage(content=existing + "\n\n" + directive)
                return request.override(system_message=new_system)
        except Exception as e:
            _logger.debug(f"FeatureConfirmation: skipping due to error: {e}")

        return request

    def _evaluate_feature_gate(self, request: ModelRequest) -> str | None:
        """Evaluate whether feature confirmation is missing.

        Returns directive string if features exist but aren't confirmed,
        None otherwise.
        """
        backend = self._get_backend(request.runtime)

        # Step 1: Does /features.md exist on disk?
        if not self._features_file_exists(backend):
            return None  # Features not written yet — nothing to enforce

        # Step 2: Scan message history for the gate sequence
        feature_presented = False
        feature_confirmed = False

        for msg in request.messages:
            msg_type = getattr(msg, "type", None)
            content = self._get_content(msg)

            if msg_type in ("ai", "assistant"):
                # Check if AI presented the Feature Matrix
                if any(marker in content for marker in _FEATURE_PRESENTED_MARKERS):
                    feature_presented = True
                    # Reset confirmation flag — need fresh confirm after this presentation
                    feature_confirmed = False

            elif msg_type == "human" and feature_presented:
                # Check if user confirmed after feature presentation
                if any(marker in content.lower() for marker in _CONFIRMATION_MARKERS):
                    feature_confirmed = True

        # If features have been presented and confirmed, no directive needed
        if feature_confirmed:
            return None

        # If features file exists but not presented yet, the agent should
        # present them — inject directive
        # If features presented but not confirmed, also inject directive
        return (
            "## >>> FEATURE CONFIRMATION REQUIRED (Auto-detected) <<<\n\n"
            "You have defined features but the user has NOT confirmed them.\n"
            "⛔ STOP: You MUST present the Feature Matrix as a markdown table "
            "and wait for user confirmation BEFORE proceeding to research.\n\n"
            "DO NOT call task(). DO NOT delegate to any search sub-agents.\n"
            "DO NOT enter the Research Loop.\n\n"
            "Present the Feature Matrix now and ask the user to confirm."
        )

    def _features_file_exists(self, backend: BackendProtocol) -> bool:
        """Check if /features.md exists on the backend filesystem."""
        try:
            content = backend.read("/features.md")
            return bool(content and content.strip())
        except Exception:
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
