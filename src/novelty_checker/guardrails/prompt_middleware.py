"""Pre-processing middleware that injects guardrail directives into the system prompt.

Handles behavioral guardrails (5, 6, 7, 8, 9, 12) by conditionally injecting
context-aware directives before the LLM generates a response.

Follows the same pattern as FeatureConfirmationMiddleware, AutonomousResearchMiddleware,
and CitationEnforcementMiddleware: reads backend state and message history, then
injects directives via request.override(system_message=...).
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

# --- Guardrail #5: Scope boundary (always injected) ---
_SCOPE_BOUNDARY_DIRECTIVE = (
    "## >>> SCOPE BOUNDARY (Guardrail Active) <<<\n\n"
    "You MUST decline ALL requests outside novelty/prior-art search scope.\n"
    "Decline with a brief explanation for: Freedom-to-Operate (FTO), trademark "
    "clearance, copyright analysis, code generation, API scripting, personal "
    "conversation, general knowledge questions, and any non-IP tasks.\n"
    "Respond: 'My scope is limited to novelty and prior art search. "
    "I'm not able to assist with [requested task].'"
)

# --- Guardrail #6: Feature contradiction check ---
_FEATURE_MODIFICATION_KEYWORDS = (
    "add feature", "new feature", "change feature", "modify feature",
    "replace feature", "update feature", "remove feature", "add a feature",
    "include feature", "additional feature",
    "add f1", "add f2", "add f3", "add f4", "add f5", "add f6", "add f7",
    "add f8", "add f9", "add f10",
    "edit:", "edit feature",
)

_CONTRADICTION_CHECK_DIRECTIVE = (
    "## >>> FEATURE CONTRADICTION CHECK (Guardrail Active) <<<\n\n"
    "The user is requesting feature modifications. Before accepting:\n"
    "1. Cross-check the proposed change against ALL existing features and exclusions\n"
    "2. If the new feature contradicts an existing feature, FLAG it to the user\n"
    "3. Ask for clarification before making the change\n"
    "Do NOT silently add a feature that conflicts with existing ones."
)

# --- Guardrail #7: Feature rebuild confirmation ---
_FEATURE_REJECTION_KEYWORDS = (
    "reject", "wrong", "start over", "redo", "all wrong",
    "none of these", "completely wrong", "not right", "try again",
    "scrap", "these are wrong", "not what i",
)

_FEATURE_PRESENTED_MARKERS = ("Feature Matrix", "CONFIRMATION REQUIRED", "Stage 2 Gate")

_REBUILD_CONFIRMATION_DIRECTIVE = (
    "## >>> FEATURE REBUILD REQUIRES SPECIFICS (Guardrail Active) <<<\n\n"
    "The user appears to have rejected the feature matrix without specifying "
    "which features are wrong. Do NOT rebuild the entire matrix from assumptions.\n"
    "Instead, ask: 'Which specific features would you like to change, "
    "and what should they be?'"
)

# --- Guardrail #8: Multi-question explicit decline ---
_OUT_OF_SCOPE_KEYWORDS = (
    "freedom to operate", "freedom-to-operate", "fto",
    "patentability", "patentable",
    "trademark", "trade mark",
    "copyright",
    "infringement",
    "claim draft", "draft claim", "design around", "design-around",
    "file a patent", "filing strategy",
)

_MULTI_QUESTION_DIRECTIVE = (
    "## >>> MULTI-DOMAIN REQUEST DETECTED (Guardrail Active) <<<\n\n"
    "The user's message contains requests spanning multiple domains "
    "(novelty + non-novelty items). You MUST:\n"
    "1. Explicitly DECLINE each non-novelty part with a brief explanation\n"
    "2. Then proceed with the novelty-related parts\n"
    "Do NOT partially accept or silently ignore non-novelty requests."
)

# --- Guardrail #9: No unsolicited concepts (pre-Gate-2 only) ---
_UNSOLICITED_CONCEPTS_DIRECTIVE = (
    "## >>> NO UNSOLICITED CONCEPTS (Guardrail Active) <<<\n\n"
    "During feature definition (before Gate 2), do NOT generate your own "
    "missing concepts or features. If you identify a potentially relevant "
    "concept, ASK the user: 'I notice [concept] might be relevant. "
    "Would you like to include it?'"
)

# --- Guardrail #12: Evidence-based triage ---
_TRIAGE_DISPUTE_KEYWORDS = (
    "outdated", "irrelevant", "not relevant", "wrong label",
    "wrong triage", "should be b", "should be c", "downgrade",
    "not applicable", "doesn't apply", "too old", "not related",
    "change the triage", "change the label", "reclassify",
)

_EVIDENCE_BASED_TRIAGE_DIRECTIVE = (
    "## >>> EVIDENCE-BASED TRIAGE ONLY (Guardrail Active) <<<\n\n"
    "The user is disputing a reference triage label. Do NOT change the "
    "label based solely on the user's claim.\n"
    "1. Note the user's disagreement\n"
    "2. Re-examine the actual reference text against the features\n"
    "3. Only change the label if the reference text supports the change\n"
    "4. Explain your reasoning based on the evidence"
)


class GuardrailsPromptMiddleware(AgentMiddleware):
    """Pre-processing middleware for behavioral guardrails.

    Injects context-aware directives into the system prompt based on
    message history and backend state analysis.

    Guardrails covered:
    - #5: Hard scope boundary (always active)
    - #6: Feature contradiction check (when features exist + modification requested)
    - #7: Feature rebuild confirmation (when user rejects without specifics)
    - #8: Multi-question decline (when multi-domain request detected)
    - #9: No unsolicited concepts (pre-Gate-2 only)
    - #12: Evidence-based triage (when user disputes triage label)
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
        request = self._inject_directives(request)
        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        request = self._inject_directives(request)
        return await handler(request)

    def _inject_directives(self, request: ModelRequest) -> ModelRequest:
        """Evaluate all behavioral guardrail conditions and inject directives."""
        directives: list[str] = []

        try:
            backend = self._get_backend(request.runtime)
            latest_human = self._get_latest_human_message(request)
            latest_human_lower = latest_human.lower() if latest_human else ""
            features_exist = self._features_file_exists(backend)
            is_post_gate2 = features_exist and self._features_confirmed(request)

            # Guardrail #5: Scope boundary (always active)
            directives.append(_SCOPE_BOUNDARY_DIRECTIVE)

            # Guardrail #6: Feature contradiction check
            if features_exist and latest_human_lower and any(
                kw in latest_human_lower for kw in _FEATURE_MODIFICATION_KEYWORDS
            ):
                directives.append(_CONTRADICTION_CHECK_DIRECTIVE)

            # Guardrail #7: Feature rebuild confirmation
            if self._user_rejected_features(request, latest_human_lower):
                directives.append(_REBUILD_CONFIRMATION_DIRECTIVE)

            # Guardrail #8: Multi-question decline
            if latest_human_lower and self._has_out_of_scope_items(latest_human_lower):
                directives.append(_MULTI_QUESTION_DIRECTIVE)

            # Guardrail #9: No unsolicited concepts (pre-Gate-2 only)
            if not is_post_gate2:
                directives.append(_UNSOLICITED_CONCEPTS_DIRECTIVE)

            # Guardrail #12: Evidence-based triage
            if latest_human_lower and any(
                kw in latest_human_lower for kw in _TRIAGE_DISPUTE_KEYWORDS
            ):
                directives.append(_EVIDENCE_BASED_TRIAGE_DIRECTIVE)

        except Exception as e:
            _logger.debug(f"GuardrailsPrompt: error evaluating conditions: {e}")
            # On error, still inject the scope boundary (always-on)
            directives = [_SCOPE_BOUNDARY_DIRECTIVE]

        if directives:
            combined = "\n\n".join(directives)
            existing = request.system_message.content if request.system_message else ""
            if isinstance(existing, list):
                existing = "\n".join(
                    block if isinstance(block, str) else block.get("text", "")
                    for block in existing
                )
            new_system = SystemMessage(content=existing + "\n\n" + combined)
            return request.override(system_message=new_system)

        return request

    def _get_latest_human_message(self, request: ModelRequest) -> str | None:
        """Extract text from the most recent HumanMessage."""
        for msg in reversed(request.messages):
            if getattr(msg, "type", None) == "human":
                return self._get_content(msg)
        return None

    def _features_file_exists(self, backend: BackendProtocol) -> bool:
        """Check if /features.md exists on the backend."""
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
                if any(marker in content for marker in _FEATURE_PRESENTED_MARKERS):
                    feature_presented = True
            elif msg_type == "human" and feature_presented:
                if "confirm" in content.lower():
                    return True
        return False

    def _user_rejected_features(
        self, request: ModelRequest, latest_human_lower: str
    ) -> bool:
        """Check if user rejected features without specifying which ones."""
        if not latest_human_lower:
            return False

        # Must contain rejection language
        has_rejection = any(kw in latest_human_lower for kw in _FEATURE_REJECTION_KEYWORDS)
        if not has_rejection:
            return False

        # Check if the agent recently presented a Feature Matrix
        for msg in reversed(request.messages):
            msg_type = getattr(msg, "type", None)
            if msg_type in ("ai", "assistant"):
                content = self._get_content(msg)
                if any(marker in content for marker in _FEATURE_PRESENTED_MARKERS):
                    return True
                break  # Only check the most recent AI message

        return False

    def _has_out_of_scope_items(self, text: str) -> bool:
        """Check if user message contains out-of-scope domain keywords."""
        return any(kw in text for kw in _OUT_OF_SCOPE_KEYWORDS)

    @staticmethod
    def _get_content(msg: Any) -> str:
        """Extract string content from a message."""
        content = getattr(msg, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
        return str(content)
