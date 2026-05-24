"""Builders and normalization helpers for A2UI bubbles.

The frontend normalizes input defensively, but we still aim to send
fully valid payloads. These helpers centralize that logic.
"""

from __future__ import annotations

from typing import Any

from src.novelty_checker.api.schemas import (
    AgentActivityBubble,
    SupportedComponent,
)

_VALID_COMPONENTS: set[str] = {
    "assumptionBubble",
    "plainBubble",
    "featureConfirmationBubble",
    "agentActivityBubble",
    "researchTimelineBubble",
}

_VALID_STEP_STATUSES: set[str] = {
    "not_started",
    "in_progress",
    "completed",
    "restart",
    "skipped",
    "failed",
}

_VALID_CONTENT_TYPES: set[str] = {"markdown", "paragraph", "queryList", "chipGrid"}

_DEFAULT_LABELS: dict[str, str] = {
    "defaultAssumptionLabel": "Assumption",
    "useCaseLabel": "Assumed use case",
    "featuresLabel": "Features List - Select the ones you consider core",
    "coreLabel": "Core",
}


def build_activity_bubble(header_text: str, text: str) -> dict[str, Any]:
    """Construct a normalized agentActivityBubble payload."""
    return AgentActivityBubble(
        headerText=header_text or "Working...",
        text=text or "",
    ).model_dump()


def normalize_component(comp: str | None) -> SupportedComponent:
    """Return ``comp`` if valid, else fall back to ``assumptionBubble``."""
    if isinstance(comp, str) and comp in _VALID_COMPONENTS:
        return comp  # type: ignore[return-value]
    return "assumptionBubble"


def normalize_step(step: dict[str, Any], idx: int) -> dict[str, Any] | None:
    """Normalize a single timeline step. Returns ``None`` for unsalvageable input."""
    if not isinstance(step, dict):
        return None
    title = step.get("title")
    if not isinstance(title, str) or not title.strip():
        return None

    step_id = step.get("id")
    if not isinstance(step_id, str) or not step_id.strip():
        step_id = f"step-{idx}"

    status = step.get("status")
    if status not in _VALID_STEP_STATUSES:
        status = "not_started"

    out: dict[str, Any] = {"id": step_id, "title": title, "status": status}

    content = step.get("content")
    if isinstance(content, dict) and content.get("type") in _VALID_CONTENT_TYPES:
        out["content"] = {
            "type": content["type"],
            "text": content.get("text"),
            "items": content.get("items"),
        }

    return out


def normalize_labels_in_bubble(spec: dict[str, Any]) -> dict[str, Any]:
    """Apply default labels to bubble fields when missing.

    Mutates and returns the same dict for convenience.
    """
    for key, default in _DEFAULT_LABELS.items():
        if not spec.get(key):
            spec[key] = default
    return spec
