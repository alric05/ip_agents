"""Post-processing middleware that filters LLM output through guardrails-ai validators.

Intercepts the LLM response in wrap_model_call / awrap_model_call, runs it
through a Guard pipeline of custom validators, and replaces or sanitizes
the response if any validator fails.

Critical-risk guardrails (1, 3, 4, 10, 11): Full response replacement with
canned safe message. No tool_calls — agent re-engages user.

Architecture disclosure (2): Sanitizes protected names via fix, preserves
tool_calls so the agent continues functioning normally.

Follows the pattern established by ContentFilterMiddleware (content_filter.py).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from guardrails import Guard
from guardrails.errors import ValidationError
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage

from src.novelty_checker.guardrails.replacement_messages import (
    CLAIM_DRAFTING_REPLACEMENT,
    COMPETITIVE_INTEL_REPLACEMENT,
    FILING_ADVICE_REPLACEMENT,
    PATENTABILITY_REPLACEMENT,
    VERDICT_REFRAMING_REPLACEMENT,
)
from src.novelty_checker.guardrails.validators import (
    BlockArchitectureDisclosure,
    BlockClaimDraftingDesignAround,
    BlockCompetitiveIntelAnalysis,
    BlockFilingAdvice,
    BlockPatentabilityOpinion,
    BlockVerdictReframing,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langchain.agents.middleware.types import ModelRequest, ModelResponse

_logger = logging.getLogger(__name__)

# Map validator rail names to their replacement messages
_REPLACEMENT_MAP: dict[str, str] = {
    "block-patentability-opinion": PATENTABILITY_REPLACEMENT,
    "block-claim-drafting": CLAIM_DRAFTING_REPLACEMENT,
    "block-filing-advice": FILING_ADVICE_REPLACEMENT,
    "block-competitive-intel": COMPETITIVE_INTEL_REPLACEMENT,
    "block-verdict-reframing": VERDICT_REFRAMING_REPLACEMENT,
}

# Default replacement when we can't determine which validator failed
_DEFAULT_REPLACEMENT = (
    "I'm not able to assist with that request. My scope is limited to "
    "novelty and prior art search. Please consult a patent attorney for "
    "legal guidance."
)


class GuardrailsOutputFilterMiddleware(AgentMiddleware):
    """Post-processing output filter using guardrails-ai validators.

    Runs the LLM response through a Guard pipeline. On validation failure:
    - fix validators: returns sanitized text, preserves tool_calls
    - exception validators: returns canned replacement, strips tool_calls
    """

    def __init__(self) -> None:
        # Build the Guard pipeline.
        # Order: fix validators first (sanitize names), then exception validators
        # (scan the cleaned text). This prevents a tool name from triggering
        # an exception validator before the fix validator can redact it.
        self._guard = Guard().use(
            BlockArchitectureDisclosure(on_fail="fix"),
            BlockPatentabilityOpinion(on_fail="exception"),
            BlockClaimDraftingDesignAround(on_fail="exception"),
            BlockFilingAdvice(on_fail="exception"),
            BlockCompetitiveIntelAnalysis(on_fail="exception"),
            BlockVerdictReframing(on_fail="exception"),
        )

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        response = handler(request)
        return self._apply_guardrails(response)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        response = await handler(request)
        return self._apply_guardrails(response)

    def _apply_guardrails(self, response: Any) -> Any:
        """Run guardrails validation on the LLM response.

        Returns the original response if clean, sanitized version if
        architecture names found, or full replacement if critical violation.
        """
        content = self._extract_content(response)
        if not content:
            return response

        try:
            result = self._guard.validate(content)
            # Validation passed (possibly after fixes)
            validated = result.validated_output if result.validated_output else content
            if validated != content:
                # Architecture names were sanitized — return fixed version
                _logger.info("Guardrails: architecture names sanitized in output")
                return self._replace_content(response, validated, preserve_tools=True)
            return response

        except ValidationError as exc:
            # A critical validator triggered — full replacement
            replacement = self._get_replacement_for_error(exc)
            _logger.warning(
                "Guardrails: critical violation detected, replacing response. "
                "Error: %s",
                exc,
            )
            return AIMessage(content=replacement)

        except Exception as exc:
            # Unexpected error in guardrails — log but don't block
            _logger.error(
                "Guardrails: unexpected error during validation, passing through: %s",
                exc,
            )
            return response

    def _extract_content(self, response: Any) -> str | None:
        """Extract string content from AIMessage or ModelResponse."""
        if isinstance(response, AIMessage):
            content = response.content
        elif hasattr(response, "content"):
            content = response.content
        else:
            return None

        if isinstance(content, str) and content.strip():
            return content
        return None

    def _replace_content(
        self, response: Any, new_content: str, *, preserve_tools: bool = False
    ) -> Any:
        """Return a new AIMessage with replaced content.

        If preserve_tools is True, carries over tool_calls from the original.
        """
        if isinstance(response, AIMessage):
            kwargs: dict[str, Any] = {"content": new_content}
            if preserve_tools and hasattr(response, "tool_calls") and response.tool_calls:
                kwargs["tool_calls"] = response.tool_calls
            if hasattr(response, "id") and response.id:
                kwargs["id"] = response.id
            return AIMessage(**kwargs)

        # For other response types, return a plain AIMessage
        return AIMessage(content=new_content)

    def _get_replacement_for_error(self, exc: ValidationError) -> str:
        """Determine the appropriate replacement message from the error."""
        error_str = str(exc).lower()
        for rail_name, replacement in _REPLACEMENT_MAP.items():
            # Check if the rail name appears in the error
            if rail_name.replace("-", " ") in error_str or rail_name in error_str:
                return replacement

        # Fallback: check for keyword hints in the error message
        if "patentab" in error_str:
            return PATENTABILITY_REPLACEMENT
        if "claim" in error_str or "design-around" in error_str:
            return CLAIM_DRAFTING_REPLACEMENT
        if "filing" in error_str or "prosecution" in error_str:
            return FILING_ADVICE_REPLACEMENT
        if "competitive" in error_str:
            return COMPETITIVE_INTEL_REPLACEMENT
        if "reframe" in error_str or "verdict" in error_str:
            return VERDICT_REFRAMING_REPLACEMENT

        return _DEFAULT_REPLACEMENT
