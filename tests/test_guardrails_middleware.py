"""Integration tests for guardrails middleware.

Tests GuardrailsOutputFilterMiddleware and GuardrailsPromptMiddleware
using mocked handlers and backend state.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, NonCallableMagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.novelty_checker.guardrails.output_filter_middleware import (
    GuardrailsOutputFilterMiddleware,
)
from src.novelty_checker.guardrails.prompt_middleware import (
    GuardrailsPromptMiddleware,
)
from src.novelty_checker.guardrails.replacement_messages import (
    CLAIM_DRAFTING_REPLACEMENT,
    COMPETITIVE_INTEL_REPLACEMENT,
    FILING_ADVICE_REPLACEMENT,
    PATENTABILITY_REPLACEMENT,
    VERDICT_REFRAMING_REPLACEMENT,
)


# ============================================================================
# Helpers
# ============================================================================

def _make_request(
    messages: list | None = None,
    system_content: str = "You are a helpful assistant.",
    features_exist: bool = False,
) -> MagicMock:
    """Create a mock ModelRequest."""
    request = MagicMock()
    request.messages = messages or []
    request.system_message = SystemMessage(content=system_content)
    request.runtime = MagicMock()

    # Mock override to return a new request with updated system message
    def _override(system_message=None, **kwargs):
        new_req = MagicMock()
        new_req.messages = request.messages
        new_req.system_message = system_message or request.system_message
        new_req.runtime = request.runtime
        new_req.override = _override
        return new_req
    request.override = _override

    return request


def _make_backend(features_content: str | None = None) -> NonCallableMagicMock:
    """Create a mock backend.

    Uses NonCallableMagicMock so _get_backend() treats it as a static
    backend (not a factory callable).
    """
    backend = NonCallableMagicMock()

    def _read(path: str) -> str:
        if path == "/features.md" and features_content is not None:
            return features_content
        raise FileNotFoundError(f"File not found: {path}")

    backend.read = _read
    return backend


# ============================================================================
# GuardrailsOutputFilterMiddleware Tests
# ============================================================================

class TestOutputFilterMiddleware:
    def setup_method(self):
        self.middleware = GuardrailsOutputFilterMiddleware()

    def test_clean_response_passes_through(self):
        """Clean response should pass through unchanged."""
        response = AIMessage(content="Found 10 references covering 4 features.")
        handler = MagicMock(return_value=response)
        request = _make_request()

        result = self.middleware.wrap_model_call(request, handler)

        handler.assert_called_once()
        assert result.content == response.content

    def test_patentability_opinion_replaced(self):
        """Patentability opinion should be replaced with canned message."""
        response = AIMessage(content="Based on my analysis, this invention is patentable.")
        handler = MagicMock(return_value=response)
        request = _make_request()

        result = self.middleware.wrap_model_call(request, handler)

        assert result.content == PATENTABILITY_REPLACEMENT

    def test_claim_drafting_replaced(self):
        """Claim drafting should be replaced."""
        response = AIMessage(content="Here is a draft claim for your invention: Claim 1: A method...")
        handler = MagicMock(return_value=response)
        request = _make_request()

        result = self.middleware.wrap_model_call(request, handler)

        assert result.content == CLAIM_DRAFTING_REPLACEMENT

    def test_filing_advice_replaced(self):
        """Filing advice should be replaced."""
        response = AIMessage(content="You should file a patent application immediately.")
        handler = MagicMock(return_value=response)
        request = _make_request()

        result = self.middleware.wrap_model_call(request, handler)

        assert result.content == FILING_ADVICE_REPLACEMENT

    def test_competitive_intel_replaced(self):
        """Competitive intelligence should be replaced."""
        response = AIMessage(content="The competitive landscape shows Company X leads.")
        handler = MagicMock(return_value=response)
        request = _make_request()

        result = self.middleware.wrap_model_call(request, handler)

        assert result.content == COMPETITIVE_INTEL_REPLACEMENT

    def test_verdict_reframing_replaced(self):
        """Verdict reframing offer should be replaced."""
        response = AIMessage(content="I can craft a credible novelty angle for your pitch.")
        handler = MagicMock(return_value=response)
        request = _make_request()

        result = self.middleware.wrap_model_call(request, handler)

        assert result.content == VERDICT_REFRAMING_REPLACEMENT

    def test_architecture_names_sanitized(self):
        """Architecture names should be redacted, not fully replaced."""
        response = AIMessage(
            content="I searched Innography and Web of Science for prior art.",
            tool_calls=[{"name": "some_tool", "args": {}, "id": "tc1"}],
        )
        handler = MagicMock(return_value=response)
        request = _make_request()

        result = self.middleware.wrap_model_call(request, handler)

        assert "Innography" not in result.content
        assert "Web of Science" not in result.content
        assert "patent database" in result.content
        assert "academic literature database" in result.content

    def test_empty_response_passes_through(self):
        """Empty response should pass through."""
        response = AIMessage(content="")
        handler = MagicMock(return_value=response)
        request = _make_request()

        result = self.middleware.wrap_model_call(request, handler)

        assert result.content == ""

    def test_filing_date_bibliographic_passes(self):
        """Filing date in bibliographic context should not trigger."""
        response = AIMessage(
            content="US10000001 has a filing date of 2020-01-15 and priority date of 2019-03-20."
        )
        handler = MagicMock(return_value=response)
        request = _make_request()

        result = self.middleware.wrap_model_call(request, handler)

        assert result.content == response.content


# ============================================================================
# GuardrailsPromptMiddleware Tests
# ============================================================================

class TestPromptMiddleware:
    def test_scope_boundary_always_injected(self):
        """Scope boundary directive should always be injected."""
        backend = _make_backend()
        middleware = GuardrailsPromptMiddleware(backend=backend)
        request = _make_request(messages=[HumanMessage(content="Tell me a joke.")])
        handler = MagicMock(return_value=AIMessage(content="ok"))

        middleware.wrap_model_call(request, handler)

        # The handler should receive a request with the scope directive
        called_request = handler.call_args[0][0]
        assert "SCOPE BOUNDARY" in called_request.system_message.content

    def test_contradiction_check_when_features_exist_and_modification(self):
        """Should inject contradiction directive when features exist and user modifies."""
        backend = _make_backend(features_content="| F1 | Feature One | ... |")
        middleware = GuardrailsPromptMiddleware(backend=backend)
        request = _make_request(
            messages=[HumanMessage(content="Please add feature for wireless charging.")]
        )
        handler = MagicMock(return_value=AIMessage(content="ok"))

        middleware.wrap_model_call(request, handler)

        called_request = handler.call_args[0][0]
        assert "CONTRADICTION CHECK" in called_request.system_message.content

    def test_no_contradiction_check_without_features(self):
        """Should NOT inject contradiction directive when no features exist."""
        backend = _make_backend()  # No features file
        middleware = GuardrailsPromptMiddleware(backend=backend)
        request = _make_request(
            messages=[HumanMessage(content="Please add feature for wireless charging.")]
        )
        handler = MagicMock(return_value=AIMessage(content="ok"))

        middleware.wrap_model_call(request, handler)

        called_request = handler.call_args[0][0]
        assert "CONTRADICTION CHECK" not in called_request.system_message.content

    def test_rebuild_confirmation_on_rejection(self):
        """Should inject rebuild directive when user rejects features."""
        backend = _make_backend(features_content="| F1 | Feature One |")
        middleware = GuardrailsPromptMiddleware(backend=backend)
        request = _make_request(
            messages=[
                AIMessage(content="Here is your Feature Matrix with CONFIRMATION REQUIRED:"),
                HumanMessage(content="These are all wrong, start over."),
            ]
        )
        handler = MagicMock(return_value=AIMessage(content="ok"))

        middleware.wrap_model_call(request, handler)

        called_request = handler.call_args[0][0]
        assert "FEATURE REBUILD" in called_request.system_message.content

    def test_multi_question_detection(self):
        """Should inject multi-question directive for mixed-domain requests."""
        backend = _make_backend()
        middleware = GuardrailsPromptMiddleware(backend=backend)
        request = _make_request(
            messages=[
                HumanMessage(
                    content="Can you do a novelty search and also a freedom-to-operate analysis?"
                )
            ]
        )
        handler = MagicMock(return_value=AIMessage(content="ok"))

        middleware.wrap_model_call(request, handler)

        called_request = handler.call_args[0][0]
        assert "MULTI-DOMAIN REQUEST" in called_request.system_message.content

    def test_unsolicited_concepts_pre_gate2(self):
        """Should inject unsolicited concepts directive before Gate 2."""
        backend = _make_backend()  # No features = pre-Gate-2
        middleware = GuardrailsPromptMiddleware(backend=backend)
        request = _make_request(
            messages=[HumanMessage(content="Here are my features.")]
        )
        handler = MagicMock(return_value=AIMessage(content="ok"))

        middleware.wrap_model_call(request, handler)

        called_request = handler.call_args[0][0]
        assert "UNSOLICITED CONCEPTS" in called_request.system_message.content

    def test_no_unsolicited_concepts_post_gate2(self):
        """Should NOT inject unsolicited concepts directive after Gate 2."""
        backend = _make_backend(features_content="| F1 | Feature One |")
        middleware = GuardrailsPromptMiddleware(backend=backend)
        request = _make_request(
            messages=[
                AIMessage(content="Here is your Feature Matrix with CONFIRMATION REQUIRED:"),
                HumanMessage(content="I confirm these features."),
                HumanMessage(content="Search for more references."),
            ]
        )
        handler = MagicMock(return_value=AIMessage(content="ok"))

        middleware.wrap_model_call(request, handler)

        called_request = handler.call_args[0][0]
        assert "UNSOLICITED CONCEPTS" not in called_request.system_message.content

    def test_triage_dispute_detection(self):
        """Should inject evidence-based triage directive when user disputes labels."""
        backend = _make_backend()
        middleware = GuardrailsPromptMiddleware(backend=backend)
        request = _make_request(
            messages=[
                HumanMessage(content="That reference is irrelevant, please downgrade it.")
            ]
        )
        handler = MagicMock(return_value=AIMessage(content="ok"))

        middleware.wrap_model_call(request, handler)

        called_request = handler.call_args[0][0]
        assert "EVIDENCE-BASED TRIAGE" in called_request.system_message.content

    def test_no_triage_directive_for_normal_message(self):
        """Should NOT inject triage directive for normal messages."""
        backend = _make_backend()
        middleware = GuardrailsPromptMiddleware(backend=backend)
        request = _make_request(
            messages=[HumanMessage(content="Please continue with the search.")]
        )
        handler = MagicMock(return_value=AIMessage(content="ok"))

        middleware.wrap_model_call(request, handler)

        called_request = handler.call_args[0][0]
        assert "EVIDENCE-BASED TRIAGE" not in called_request.system_message.content
