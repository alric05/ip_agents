"""Schema and normalization tests for A2UI bubbles."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.novelty_checker.api.a2ui_bubbles import (
    build_activity_bubble,
    normalize_component,
    normalize_labels_in_bubble,
    normalize_step,
)
from src.novelty_checker.api.schemas import (
    AgentActivityBubble,
    ResearchTimelineBubble,
    TimelineCompletion,
    TimelineCompletionSection,
    TimelineStep,
    TimelineStepContent,
)


class TestAgentActivityBubble:
    def test_round_trip(self):
        b = AgentActivityBubble(headerText="H", text="T")
        d = b.model_dump()
        assert d == {"component": "agentActivityBubble", "headerText": "H", "text": "T"}

    def test_default_text(self):
        b = AgentActivityBubble(headerText="H")
        assert b.text == ""


class TestResearchTimelineBubble:
    def test_minimal_round_trip(self):
        bubble = ResearchTimelineBubble(
            headerText="Research progress",
            steps=[TimelineStep(id="plan", title="Plan")],
        )
        d = bubble.model_dump()
        assert d["component"] == "researchTimelineBubble"
        assert d["steps"][0]["status"] == "not_started"
        assert d["completion"] is None

    def test_with_completion(self):
        bubble = ResearchTimelineBubble(
            headerText="X",
            steps=[],
            completion=TimelineCompletion(
                title="Done",
                message="Ready.",
                sections=[TimelineCompletionSection(title="A", body="B")],
            ),
        )
        d = bubble.model_dump()
        assert d["completion"]["title"] == "Done"
        assert d["completion"]["sections"][0]["body"] == "B"

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            TimelineStep(id="x", title="X", status="banana")  # type: ignore[arg-type]

    def test_invalid_content_type_rejected(self):
        with pytest.raises(ValidationError):
            TimelineStepContent(type="html")  # type: ignore[arg-type]


class TestNormalizeComponent:
    def test_valid_passthrough(self):
        assert normalize_component("featureConfirmationBubble") == "featureConfirmationBubble"

    def test_invalid_falls_back(self):
        assert normalize_component("widgetBubble") == "assumptionBubble"
        assert normalize_component(None) == "assumptionBubble"
        assert normalize_component("") == "assumptionBubble"


class TestNormalizeStep:
    def test_missing_id_filled(self):
        out = normalize_step({"title": "Plan"}, idx=3)
        assert out == {"id": "step-3", "title": "Plan", "status": "not_started"}

    def test_missing_status_defaults(self):
        out = normalize_step({"id": "x", "title": "X", "status": "weird"}, idx=0)
        assert out is not None
        assert out["status"] == "not_started"

    def test_missing_title_dropped(self):
        assert normalize_step({"id": "x"}, idx=0) is None
        assert normalize_step({"id": "x", "title": "  "}, idx=0) is None

    def test_unknown_content_type_dropped(self):
        out = normalize_step(
            {"id": "x", "title": "X", "content": {"type": "html", "text": "h"}},
            idx=0,
        )
        assert out is not None
        assert "content" not in out

    def test_known_content_type_kept(self):
        out = normalize_step(
            {"id": "x", "title": "X", "content": {"type": "markdown", "text": "**A**"}},
            idx=0,
        )
        assert out is not None
        assert out["content"]["type"] == "markdown"


class TestNormalizeLabels:
    def test_defaults_applied(self):
        spec = {"component": "featureConfirmationBubble"}
        normalize_labels_in_bubble(spec)
        assert spec["defaultAssumptionLabel"] == "Assumption"
        assert spec["useCaseLabel"] == "Assumed use case"
        assert spec["featuresLabel"] == "Features List - Select the ones you consider core"
        assert spec["coreLabel"] == "Core"

    def test_existing_labels_preserved(self):
        spec = {"defaultAssumptionLabel": "Premise", "coreLabel": "Primary"}
        normalize_labels_in_bubble(spec)
        assert spec["defaultAssumptionLabel"] == "Premise"
        assert spec["coreLabel"] == "Primary"


class TestActivityBuilder:
    def test_basic(self):
        d = build_activity_bubble("Header", "Some text")
        assert d == {
            "component": "agentActivityBubble",
            "headerText": "Header",
            "text": "Some text",
        }

    def test_empty_header_falls_back(self):
        d = build_activity_bubble("", "x")
        assert d["headerText"] == "Working..."

    def test_empty_text_kept_empty(self):
        d = build_activity_bubble("h", "")
        assert d["text"] == ""
