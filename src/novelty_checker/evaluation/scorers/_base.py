"""Base classes for evaluation scorers.

Bridges DeepEval's BaseMetric interface with the project's ScorerResult
dataclass, allowing scorers to work both standalone and within DeepEval's
evaluate() pipeline.
"""

from __future__ import annotations

import json
import logging
from abc import abstractmethod
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

_logger = logging.getLogger(__name__)


@dataclass
class ScorerResult:
    """Result from a single scorer evaluation.

    Attributes:
        metric_name: Machine-readable metric identifier (e.g., "prior_art_recall").
        score: Normalized score between 0.0 and 1.0.
        confidence: How reliable this score is (0.0 to 1.0).
        passed: Whether the score meets or exceeds the threshold.
        threshold: The pass/fail threshold used.
        failures: List of failure dicts with {type, severity, evidence, affected_element}.
        evidence: Scorer-specific details for debugging and reporting.
        scorer_type: One of "deterministic", "llm_judge", or "human".
    """

    metric_name: str
    score: float
    confidence: float
    passed: bool
    threshold: float
    failures: list[dict] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)
    scorer_type: str = "deterministic"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NoveltyBaseMetric(BaseMetric):
    """Base class for all novelty checker evaluation metrics.

    Subclasses implement ``_compute()`` which returns a ``ScorerResult``.
    The ``measure()`` method (DeepEval contract) delegates to ``_compute()``
    and maps the result onto DeepEval's expected attributes.

    Scorers can also be used standalone via ``score_standalone()``.
    """

    def __init__(
        self,
        metric_name: str,
        threshold: float,
        scorer_type: str = "deterministic",
    ) -> None:
        self.metric_name = metric_name
        self.threshold = threshold
        self.scorer_type = scorer_type
        self.scorer_result: ScorerResult | None = None

        # DeepEval BaseMetric attributes
        self.score: float | None = None
        self.reason: str | None = None
        self.success: bool | None = None

    @property
    def __name__(self) -> str:  # type: ignore[override]
        return self.metric_name

    # ------------------------------------------------------------------
    # Abstract: subclasses implement this
    # ------------------------------------------------------------------

    @abstractmethod
    def _compute(
        self,
        eval_trace: dict[str, Any],
        ground_truth: dict[str, Any],
        session_path: Path,
        config: dict[str, Any] | None = None,
    ) -> ScorerResult:
        """Compute the metric score.

        Args:
            eval_trace: Parsed eval_trace.json.
            ground_truth: Merged ground truth fixture data.
            session_path: Path to the agent session directory.
            config: Optional scorer-specific configuration overrides.

        Returns:
            A ScorerResult with the computed score and evidence.
        """
        ...

    # ------------------------------------------------------------------
    # DeepEval contract
    # ------------------------------------------------------------------

    def measure(self, test_case: LLMTestCase) -> float:
        """DeepEval-compatible measure method.

        Extracts eval_trace, ground_truth, and session_path from
        ``test_case.additional_metadata`` and delegates to ``_compute()``.
        """
        metadata = test_case.additional_metadata or {}
        eval_trace = metadata.get("eval_trace", {})
        ground_truth = metadata.get("ground_truth", {})
        session_path = Path(metadata.get("session_path", "."))
        config = metadata.get("scorer_config")

        self.scorer_result = self._compute(
            eval_trace, ground_truth, session_path, config
        )

        # Map to DeepEval attributes
        self.score = self.scorer_result.score
        self.success = self.scorer_result.passed
        self.reason = json.dumps(self.scorer_result.evidence, indent=2, default=str)
        return self.score

    def is_successful(self) -> bool:
        return self.success if self.success is not None else False

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        """Async variant — delegates to sync measure for deterministic scorers."""
        return self.measure(test_case)

    # ------------------------------------------------------------------
    # Standalone API (no DeepEval dependency needed)
    # ------------------------------------------------------------------

    def score_standalone(
        self,
        eval_trace: dict[str, Any],
        ground_truth: dict[str, Any],
        session_path: Path,
        config: dict[str, Any] | None = None,
    ) -> ScorerResult:
        """Run the scorer directly without a DeepEval test case.

        This is the preferred API for the CLI runner and custom pipelines.
        """
        self.scorer_result = self._compute(
            eval_trace, ground_truth, session_path, config
        )
        self.score = self.scorer_result.score
        self.success = self.scorer_result.passed
        return self.scorer_result
