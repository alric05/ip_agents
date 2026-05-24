"""Pydantic response models for the structured Novelty Checker API.

These models define the JSON contract between backend and frontend.
Every response uses the APIResponse envelope, with stage_data containing
stage-specific structured data.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# =============================================================================
# Request Models
# =============================================================================

class ChatRequest(BaseModel):
    """Request body for the /chat endpoint."""

    message: str
    thread_id: str | None = Field(
        default=None,
        description="Thread ID for conversation continuity. "
        "Omit to start a new conversation.",
    )
    jwt_token: str | None = Field(
        default=None,
        description="JWT token for user authentication. "
        "Will be passed to tools that require external API access.",
    )


# =============================================================================
# Stage-Specific Data Models
# =============================================================================

SupportedComponent = Literal[
    "assumptionBubble",
    "plainBubble",
    "featureConfirmationBubble",
    "agentActivityBubble",
    "researchTimelineBubble",
]

TimelineStepStatus = Literal[
    "not_started",
    "in_progress",
    "completed",
    "restart",
    "skipped",
    "failed",
]

TimelineContentType = Literal["markdown", "paragraph", "queryList", "chipGrid"]


class RawQuestionSpec(BaseModel):
    """A single question spec matching the frontend A2UI RawQuestionSpec interface."""

    title: str | None = Field(default=None, description="Short descriptive title, e.g. 'Target market'")
    question: str | None = Field(default=None, description="The clarifying question text")
    assumptionText: str | None = Field(default=None, description="Default assumption if user confirms")
    assumptionLabel: str | None = Field(default=None, description="Per-question label override")


class RawFeatureSpec(BaseModel):
    """A single feature spec matching the frontend A2UI RawFeatureSpec interface."""

    text: str | None = Field(default=None, description="Feature text, e.g. 'UV Sensor — Detects UV degradation'")
    isCore: bool | None = Field(default=None, description="Whether this is a core feature (pre-selects checkbox)")


class RawBubbleSpec(BaseModel):
    """stage_data for scoping and features stages, matching frontend A2UI RawBubbleSpec interface."""

    component: SupportedComponent = Field(default="assumptionBubble", description="Which bubble component to render")
    text: str | None = Field(default=None, description="Markdown text for plainBubble component")
    introText: str | None = Field(default=None, description="Lead text before questions")
    questions: list[RawQuestionSpec] = Field(default_factory=list, description="Interactive clarifying questions")
    defaultAssumptionLabel: str = Field(default="Assumption", description="Default label for assumptions")
    alternativeText: str | None = Field(default=None, description="Closing text after questions")
    additionalAssumptions: list[str] = Field(default_factory=list, description="Extra assumptions not tied to questions")
    headingText: str | None = Field(default=None, description="Heading text for feature confirmation bubble")
    useCaseLabel: str | None = Field(default=None, description="Use case section label")
    useCaseText: str | None = Field(default=None, description="Use case description text")
    featuresLabel: str | None = Field(default=None, description="Features list section label")
    coreLabel: str | None = Field(default=None, description="Core column label")
    features: list[RawFeatureSpec] = Field(default_factory=list, description="Feature items for confirmation")


class FeatureItem(BaseModel):
    """A single feature extracted from the invention."""

    id: str = Field(description="Feature identifier, e.g. 'F1', 'F2'")
    name: str = Field(description="Short name of the feature")
    description: str = Field(default="", description="Detailed description")
    keywords: list[str] = Field(default_factory=list, description="Search keywords")
    is_core: bool = Field(default=False, description="Whether this is a core feature")
    priority: Literal["P1", "P2", "P3"] = Field(
        default="P2", description="Priority level"
    )


class FeaturesData(BaseModel):
    """stage_data for the 'features' stage."""

    features: list[FeatureItem] = Field(default_factory=list)
    is_confirmation_prompt: bool = Field(
        default=True,
        description="True when the agent is asking the user to confirm features",
    )


class ResearchProgress(BaseModel):
    """Progress snapshot during the autonomous research phase."""

    current_round: int = Field(default=0, description="Current research round number")
    max_rounds: int = Field(default=5, description="Maximum research rounds")
    coverage_pct: float | None = Field(
        default=None, description="Overall coverage percentage (0-100)"
    )
    references_found: int = Field(default=0, description="Total references found so far")
    features_coverage: list[dict[str, Any]] | None = Field(
        default=None, description="Per-feature coverage status list"
    )


class ResearchingData(BaseModel):
    """stage_data for the 'researching' stage."""

    progress: ResearchProgress = Field(default_factory=ResearchProgress)


class AgentActivityBubble(BaseModel):
    """A2UI agentActivityBubble: lightweight status while the agent works."""

    component: Literal["agentActivityBubble"] = "agentActivityBubble"
    headerText: str = Field(default="Working...", description="Short header label")
    text: str = Field(default="", description="Status text describing current activity")


class TimelineStepContent(BaseModel):
    """Optional content payload attached to a research timeline step."""

    type: TimelineContentType
    text: str | None = None
    items: list[str] | None = None


class TimelineStep(BaseModel):
    """A single step in the research timeline."""

    id: str
    title: str
    status: TimelineStepStatus = "not_started"
    content: TimelineStepContent | None = None


class TimelineCompletionSection(BaseModel):
    """A section inside the completion summary."""

    title: str | None = None
    body: str | None = None


class TimelineCompletion(BaseModel):
    """Completion payload populated when research is finished."""

    title: str
    message: str
    sections: list[TimelineCompletionSection] = Field(default_factory=list)


class ResearchTimelineBubble(BaseModel):
    """A2UI researchTimelineBubble: full snapshot of research progress."""

    component: Literal["researchTimelineBubble"] = "researchTimelineBubble"
    headerText: str = Field(default="Research progress")
    steps: list[TimelineStep] = Field(default_factory=list)
    completion: TimelineCompletion | None = None


class CompletionData(BaseModel):
    """stage_data for the 'complete' stage."""

    report_markdown: str = Field(
        default="", description="Full final report in markdown format"
    )
    features: list[FeatureItem] = Field(
        default_factory=list, description="Confirmed features list"
    )
    references: list[dict[str, Any]] = Field(
        default_factory=list, description="All references found (A/B/C)"
    )
    coverage_summary: list[dict[str, Any]] = Field(
        default_factory=list, description="Per-feature coverage status"
    )
    overall_coverage_pct: float | None = Field(
        default=None, description="Final overall coverage percentage"
    )


# =============================================================================
# Unified Response Envelope
# =============================================================================

class APIResponse(BaseModel):
    """Unified response envelope for the structured Novelty Checker API.

    Every endpoint returns this envelope. The ``stage`` field tells the
    frontend what UI to render, and ``stage_data`` contains the structured
    payload for that stage.
    """

    thread_id: str = Field(description="Thread ID for conversation continuity")
    stage: Literal["scoping", "features", "researching", "complete"] = Field(
        description="Current workflow stage"
    )
    status: Literal["awaiting_input", "processing", "done", "error"] = Field(
        description="What the frontend should do next"
    )
    stage_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Stage-specific structured payload (see stage data models)",
    )
    raw_response: str = Field(
        default="",
        description="AI's raw text response (fallback for display)",
    )
    token_usage: dict[str, Any] | None = Field(
        default=None, description="Token usage breakdown"
    )
    error: str | None = Field(default=None, description="Error message if status='error'")
