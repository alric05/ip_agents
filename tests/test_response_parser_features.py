"""Tests for the features-stage output of `build_stage_data`.

Covers the contract defined in the A2UI documentation: the backend must emit
a `featureConfirmationBubble` RawBubbleSpec with `useCaseText` populated from
`/scope.md` so the frontend's "Assumed use case" block renders non-empty.
"""

from __future__ import annotations

from src.novelty_checker.api.response_parser import (
    _extract_use_case_from_scope,
    build_stage_data,
)


class _FakeBackend:
    """Minimal backend stub matching FilesystemBackend.read() error-string contract."""

    def __init__(self, files: dict[str, str]) -> None:
        self._files = files

    def read(self, path: str) -> str:
        if path in self._files:
            return self._files[path]
        return f"Error: file not found: {path}"


_CONFIRMED_SCOPE_BODY = (
    "Novelty assessment focused on a smartphone camera lens actuation "
    "transmission using two worm gears in one cascaded system."
)
_CUSTOMER_IDEA_BODY = (
    "Conventional digital still cameras can accommodate thicker lens systems, "
    "but smartphones require more compact arrangements."
)
_SCOPE_FULL = (
    "# Invention Scope\n\n"
    "## Customer Idea\n"
    f"{_CUSTOMER_IDEA_BODY}\n\n"
    "## Clarifications\n"
    "1. Adapter gear type: assumed single spur gear.\n\n"
    "## Confirmed Scope\n"
    f"{_CONFIRMED_SCOPE_BODY}\n"
)
_SCOPE_CUSTOMER_ONLY = (
    "# Invention Scope\n\n"
    "## Customer Idea\n"
    f"{_CUSTOMER_IDEA_BODY}\n"
)


# --------------------------------------------------------------------------- #
# _extract_use_case_from_scope                                                #
# --------------------------------------------------------------------------- #

def test_extract_prefers_confirmed_scope_over_customer_idea():
    assert _extract_use_case_from_scope(_SCOPE_FULL) == _CONFIRMED_SCOPE_BODY


def test_extract_falls_back_to_customer_idea():
    assert _extract_use_case_from_scope(_SCOPE_CUSTOMER_ONLY) == _CUSTOMER_IDEA_BODY


def test_extract_returns_empty_on_none():
    assert _extract_use_case_from_scope(None) == ""


def test_extract_returns_empty_on_missing_sections():
    assert _extract_use_case_from_scope("# Invention Scope\n\nNo sections here.") == ""


def test_extract_handles_filesystem_backend_line_number_prefixes():
    """FilesystemBackend.read() prepends `     N\\t` to every line."""
    prefixed = (
        "     1\t# Invention Scope\n"
        "     2\t\n"
        "     3\t## Confirmed Scope\n"
        f"     4\t{_CONFIRMED_SCOPE_BODY}\n"
    )
    assert _extract_use_case_from_scope(prefixed) == _CONFIRMED_SCOPE_BODY


# --------------------------------------------------------------------------- #
# build_stage_data(stage="features", ...)                                     #
# --------------------------------------------------------------------------- #

_SAMPLE_FEATURES = [
    {
        "id": "F1",
        "name": "UV Sensor",
        "description": "Detects UV degradation",
        "is_core": True,
    },
    {
        "id": "F2",
        "name": "Worm Gear Cascade",
        "description": "Two worm gears with adapter spur",
        "is_core": False,
    },
]


def _ai_text_with_features_block() -> str:
    import json as _json
    return (
        "Here are the features I identified.\n\n"
        "```json:features\n"
        + _json.dumps(_SAMPLE_FEATURES)
        + "\n```\n"
    )


def test_features_stage_emits_feature_confirmation_bubble_with_use_case():
    backend = _FakeBackend({"/scope.md": _SCOPE_FULL})
    result = build_stage_data("features", _ai_text_with_features_block(), {}, backend)

    assert result["component"] == "featureConfirmationBubble"
    assert result["useCaseLabel"] == "Assumed use case"
    assert result["useCaseText"] == _CONFIRMED_SCOPE_BODY
    assert result["featuresLabel"] == "Features List - Select the ones you consider core"
    assert result["coreLabel"] == "Core"
    assert result["headingText"].startswith("I've identified the following key features")


def test_features_stage_falls_back_to_customer_idea():
    backend = _FakeBackend({"/scope.md": _SCOPE_CUSTOMER_ONLY})
    result = build_stage_data("features", _ai_text_with_features_block(), {}, backend)

    assert result["useCaseText"] == _CUSTOMER_IDEA_BODY


def test_features_stage_use_case_none_when_scope_missing():
    backend = _FakeBackend({})  # /scope.md absent → error string → None
    result = build_stage_data("features", _ai_text_with_features_block(), {}, backend)

    assert result["component"] == "featureConfirmationBubble"
    assert result["useCaseText"] is None
    assert result["useCaseLabel"] == "Assumed use case"


def test_features_stage_maps_feature_items_to_raw_feature_specs():
    backend = _FakeBackend({"/scope.md": _SCOPE_FULL})
    result = build_stage_data("features", _ai_text_with_features_block(), {}, backend)

    features = result["features"]
    assert len(features) == 2
    assert features[0]["text"] == "UV Sensor — Detects UV degradation"
    assert features[0]["isCore"] is True
    assert features[1]["text"] == "Worm Gear Cascade — Two worm gears with adapter spur"
    assert features[1]["isCore"] is False


def test_features_stage_reads_features_from_state_fallback():
    backend = _FakeBackend({"/scope.md": _SCOPE_FULL})
    state = {"features": _SAMPLE_FEATURES}
    result = build_stage_data("features", "no json block here", state, backend)

    assert len(result["features"]) == 2
    assert result["features"][0]["text"] == "UV Sensor — Detects UV degradation"


def test_features_stage_feature_without_description_uses_name_only():
    backend = _FakeBackend({"/scope.md": _SCOPE_FULL})
    state = {
        "features": [
            {"id": "F1", "name": "Bare Feature", "description": "", "is_core": True}
        ]
    }
    result = build_stage_data("features", "", state, backend)

    assert result["features"][0]["text"] == "Bare Feature"
    assert result["features"][0]["isCore"] is True
