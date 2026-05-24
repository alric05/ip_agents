"""Middleware that catches Azure OpenAI content policy violations in subagents.

When Azure's content filter rejects a prompt, this middleware returns a
synthetic AIMessage instead of letting the exception crash the entire run.
The synthetic message has no tool_calls, causing the subagent to terminate
gracefully and return control to the orchestrator.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langchain.agents.middleware.types import ModelRequest, ModelResponse

_logger = logging.getLogger(__name__)

_CONTENT_POLICY_CLASS_NAMES = frozenset({
    "ContentPolicyViolationError",
    "ContentFilterFinishReasonError",
})


def _is_content_policy_violation(exc: BaseException) -> bool:
    """Check if an exception is a content policy violation via class name."""
    for cls in type(exc).__mro__:
        if cls.__name__ in _CONTENT_POLICY_CLASS_NAMES:
            return True
    # Fallback: check message for Azure content filter keywords
    msg = str(exc).lower()
    return "content_filter" in msg or "content management policy" in msg


class ContentFilterMiddleware(AgentMiddleware):
    """Catches content policy violations and returns a graceful fallback."""

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        try:
            return handler(request)
        except Exception as exc:
            if _is_content_policy_violation(exc):
                _logger.warning(
                    "Content policy violation caught in subagent model call: %s",
                    exc,
                )
                return AIMessage(
                    content=(
                        "[Content filter triggered] Azure OpenAI's content policy "
                        "filter rejected this request. The orchestrator should try "
                        "a different search approach or rephrase the query."
                    ),
                )
            raise

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        try:
            return await handler(request)
        except Exception as exc:
            if _is_content_policy_violation(exc):
                _logger.warning(
                    "Content policy violation caught in subagent model call: %s",
                    exc,
                )
                return AIMessage(
                    content=(
                        "[Content filter triggered] Azure OpenAI's content policy "
                        "filter rejected this request. The orchestrator should try "
                        "a different search approach or rephrase the query."
                    ),
                )
            raise
