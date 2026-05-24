"""Run configuration for evaluation pipeline.

Defines the RunConfig dataclass and YAML loader that replaces hardcoded
settings in run_full_eval_pipeline.py. Makes evaluation runs reproducible
and comparable by versioning all parameters in a single YAML file.

Usage:
    from src.novelty_checker.evaluation.run_config import RunConfig, load_run_config

    config = load_run_config("configs/alpha_eval.yaml")
    print(config.model)
    print(config.fixture_directory)

    # Or create programmatically
    config = RunConfig(
        config_name="quick_test",
        model="",
        fixture_directory="evals/golden_datasets/cases",
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

_logger = logging.getLogger(__name__)

_VALID_HITL_MODES = frozenset({"accept_all", "inject_ground_truth"})

_DEFAULTS = {
    "config_version": "1.0",
    "model": "azure/dpa-ai-agentic-poc",
    "max_turns": 30,
    "max_duration_seconds": 3600,
    "hitl_mode": "accept_all",
    "fixture_directory": "evals/golden_datasets/cases",
    "output_directory": "evals/results",
    "auto_scope_prompt_prefix": (
        "Please check the novelty of this invention. "
        "IMPORTANT: Do NOT ask clarifying questions during scoping. "
        "Use reasonable defaults and your best judgment for any ambiguous aspects. "
        "Proceed directly to presenting the Scope Summary for confirmation.\n\n"
        "Here is the invention:\n\n"
    ),
}


@dataclass
class FixtureFilter:
    """Optional filters for selecting a subset of fixtures.

    All fields are optional. When set, only fixtures matching ALL
    specified filters are included in the run.
    """
    domain: str | None = None
    difficulty: str | None = None
    language: str | None = None

    def is_empty(self) -> bool:
        return self.domain is None and self.difficulty is None and self.language is None

    def to_dict(self) -> dict[str, Any]:
        d = {}
        if self.domain is not None:
            d["domain"] = self.domain
        if self.difficulty is not None:
            d["difficulty"] = self.difficulty
        if self.language is not None:
            d["language"] = self.language
        return d


@dataclass
class RunConfig:
    """Configuration for an evaluation run.

    Attributes:
        config_name: Name for this configuration
        config_version: Version string for tracking changes
        model: LiteLLM model identifier
        max_turns: Safety limit for agent turns per fixture
        max_duration_seconds: Cost protection timeout per fixture
        hitl_mode: "accept_all" or "inject_ground_truth"
        fixture_directory: Path to the fixtures directory
        fixture_filter: Optional filters (domain, difficulty, language)
        output_directory: Where to write session directories and traces
        prompt_version: Tag for tracking which prompt/SKILL version is active
        auto_scope_prompt_prefix: Text prepended to disclosure when feeding
            to the agent. Controls the auto-scope instruction
        notes: Optional free-text notes about this config
    """
    config_name: str = "default"
    config_version: str = _DEFAULTS["config_version"]
    model: str = _DEFAULTS["model"]
    max_turns: int = _DEFAULTS["max_turns"]
    max_duration_seconds: int = _DEFAULTS["max_duration_seconds"]
    hitl_mode: str = _DEFAULTS["hitl_mode"]
    fixture_directory: str = _DEFAULTS["fixture_directory"]
    fixture_filter: FixtureFilter = field(default_factory=FixtureFilter)
    output_directory: str = _DEFAULTS["output_directory"]
    prompt_version: str = ""
    auto_scope_prompt_prefix: str = _DEFAULTS["auto_scope_prompt_prefix"]
    notes: str = ""

    def __post_init__(self) -> None:
        if self.hitl_mode not in _VALID_HITL_MODES:
            raise ValueError(
                f"Invalid hitl_mode: {self.hitl_mode!r}. "
                f"Must be one of: {', '.join(sorted(_VALID_HITL_MODES))}"
            )
        if self.max_turns < 1:
            raise ValueError(f"max_turns must be >= 1, got {self.max_turns}")
        if self.max_duration_seconds < 1:
            raise ValueError(
                f"max_duration_seconds must be >= 1, got {self.max_duration_seconds}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict for JSON serialization (e.g., in eval_trace.json)."""
        d = asdict(self)
        d["fixture_filter"] = self.fixture_filter.to_dict()
        return d


def load_run_config(path: str | Path) -> RunConfig:
    """Load a RunConfig from a YAML file.

    Missing fields use defaults. Extra fields are logged as warnings
    and ignored.

    Args:
        path: Path to the YAML config file.

    Returns:
        A validated RunConfig instance.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If required fields are invalid.
        yaml.YAMLError: If the file is not valid YAML.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Config file must contain a YAML mapping, got {type(raw).__name__}")

    known_keys = {
        "config_name", "config_version", "model", "max_turns",
        "max_duration_seconds", "hitl_mode", "fixture_directory",
        "fixture_filter", "output_directory", "prompt_version",
        "auto_scope_prompt_prefix", "notes",
    }
    extra_keys = set(raw.keys()) - known_keys
    if extra_keys:
        _logger.warning("Unknown keys in config %s: %s (ignored)", config_path, extra_keys)

    fixture_filter_raw = raw.pop("fixture_filter", None)
    fixture_filter = FixtureFilter()
    if isinstance(fixture_filter_raw, dict):
        fixture_filter = FixtureFilter(
            domain=fixture_filter_raw.get("domain"),
            difficulty=fixture_filter_raw.get("difficulty"),
            language=fixture_filter_raw.get("language"),
        )

    filtered_raw = {k: v for k, v in raw.items() if k in known_keys}

    config = RunConfig(
        fixture_filter=fixture_filter,
        **filtered_raw,
    )

    _logger.info(
        "Loaded config %r (model=%s, hitl_mode=%s, fixtures=%s)",
        config.config_name,
        config.model,
        config.hitl_mode,
        config.fixture_directory,
    )

    return config