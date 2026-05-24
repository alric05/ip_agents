"""Feature Extraction scorers (Tier-1, deterministic).

Provides separate Feature Precision and Feature Recall metrics per
eval_metrics_strategy.md §2.4 and §2.5.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.novelty_checker.evaluation.scorers._base import NoveltyBaseMetric, ScorerResult
from src.novelty_checker.evaluation.scorers._loader import (
    load_session_artifact,
    parse_features_md,
)
from src.novelty_checker.evaluation.scorers._matching import (
    compute_optimal_feature_alignment,
)

_logger = logging.getLogger(__name__)


def _load_gt_features(ground_truth: dict[str, Any]) -> list[dict[str, str]]:
    """Extract ground truth features list."""
    features_data = ground_truth.get("features", {})
    if isinstance(features_data, list):
        return features_data
    if isinstance(features_data, dict):
        return features_data.get("features", [])
    return []


def _is_core_feature(feature: dict[str, str]) -> bool:
    """Check if a feature is marked as core/essential."""
    for key in ("core", "core?", "is_core"):
        # val = feature.get(key, "").strip().upper()
        val = (feature.get(key) or "").strip().upper()
        if val in ("Y", "YES", "TRUE", "1"):
            return True
    return False


def _compute_alignment(
    session_path: Path,
    ground_truth: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> tuple[list[dict], list[dict], list[tuple[int, int, float]], float]:
    """Shared alignment logic for both precision and recall scorers.

    Returns:
        (agent_features, gt_features, matches, match_threshold)
    """
    features_content = load_session_artifact(session_path, "features.md")
    agent_features = parse_features_md(features_content)
    gt_features = _load_gt_features(ground_truth)

    match_weights = None
    match_threshold = 0.35
    if config:
        match_weights = config.get("match_weights")
        match_threshold = config.get("match_threshold", 0.35)

    matches = compute_optimal_feature_alignment(
        agent_features, gt_features, threshold=match_threshold, weights=match_weights
    )

    return agent_features, gt_features, matches, match_threshold


class FeaturePrecisionMetric(NoveltyBaseMetric):
    """Measures precision of feature extraction.

    precision = matched_agent_features / all_agent_features

    Alpha threshold: >= 0.70 (per eval_metrics_strategy.md §2.4)
    """

    def __init__(self, threshold: float = 0.70) -> None:
        super().__init__(
            metric_name="feature_precision",
            threshold=threshold,
            scorer_type="deterministic",
        )

    def _compute(
        self,
        eval_trace: dict[str, Any],
        ground_truth: dict[str, Any],
        session_path: Path,
        config: dict[str, Any] | None = None,
    ) -> ScorerResult:
        agent_features, gt_features, matches, _ = _compute_alignment(
            session_path, ground_truth, config
        )

        if not gt_features:
            return ScorerResult(
                metric_name="feature_precision",
                score=1.0,
                confidence=0.0,
                passed=True,
                threshold=self.threshold,
                failures=[],
                evidence={"note": "No features in ground truth"},
                scorer_type="deterministic",
            )

        if not agent_features:
            return ScorerResult(
                metric_name="feature_precision",
                score=0.0,
                confidence=1.0,
                passed=False,
                threshold=self.threshold,
                failures=[{
                    "type": "no_agent_features",
                    "severity": "critical",
                    "evidence": "Agent produced no features in features.md",
                    "affected_element": "features.md",
                }],
                evidence={"precision": 0.0, "gt_feature_count": len(gt_features), "agent_feature_count": 0},
                scorer_type="deterministic",
            )

        matched_agent_indices = {agent_idx for agent_idx, _, _ in matches}
        precision = len(matches) / len(agent_features)

        # Build per-match details
        match_details = []
        for agent_idx, gt_idx, match_score in matches:
            agent_name = agent_features[agent_idx].get(
                "feature_name", agent_features[agent_idx].get("name", f"Agent #{agent_idx}")
            )
            gt_name = gt_features[gt_idx].get(
                "name", gt_features[gt_idx].get("feature_name", f"GT #{gt_idx}")
            )
            match_details.append({
                "agent_feature": agent_name,
                "gt_feature": gt_name,
                "score": round(match_score, 4),
            })

        # Unmatched agent features (spurious)
        unmatched_agent = [
            agent_features[i].get(
                "feature_name", agent_features[i].get("name", f"Agent #{i}")
            )
            for i in range(len(agent_features))
            if i not in matched_agent_indices
        ]

        failures: list[dict[str, Any]] = []
        if unmatched_agent:
            failures.append({
                "type": "spurious_features",
                "severity": "minor",
                "evidence": f"{len(unmatched_agent)} agent features not in ground truth",
                "affected_element": ", ".join(unmatched_agent[:5]),
            })

        return ScorerResult(
            metric_name="feature_precision",
            score=round(precision, 4),
            confidence=1.0,
            passed=precision >= self.threshold,
            threshold=self.threshold,
            failures=failures,
            evidence={
                "precision": round(precision, 4),
                "gt_feature_count": len(gt_features),
                "agent_feature_count": len(agent_features),
                "matched_count": len(matches),
                "matched_pairs": match_details,
                "unmatched_agent_features": unmatched_agent,
            },
            scorer_type="deterministic",
        )


class FeatureRecallMetric(NoveltyBaseMetric):
    """Measures recall of feature extraction with core features weighted 2x.

    recall = (matched_non_core + 2 * matched_core) / (non_core_count + 2 * core_count)

    Alpha threshold: >= 0.60 (per eval_metrics_strategy.md §2.5)
    """

    def __init__(self, threshold: float = 0.60) -> None:
        super().__init__(
            metric_name="feature_recall",
            threshold=threshold,
            scorer_type="deterministic",
        )

    def _compute(
        self,
        eval_trace: dict[str, Any],
        ground_truth: dict[str, Any],
        session_path: Path,
        config: dict[str, Any] | None = None,
    ) -> ScorerResult:
        agent_features, gt_features, matches, _ = _compute_alignment(
            session_path, ground_truth, config
        )

        if not gt_features:
            return ScorerResult(
                metric_name="feature_recall",
                score=1.0,
                confidence=0.0,
                passed=True,
                threshold=self.threshold,
                failures=[],
                evidence={"note": "No features in ground truth"},
                scorer_type="deterministic",
            )

        if not agent_features:
            return ScorerResult(
                metric_name="feature_recall",
                score=0.0,
                confidence=1.0,
                passed=False,
                threshold=self.threshold,
                failures=[{
                    "type": "no_agent_features",
                    "severity": "critical",
                    "evidence": "Agent produced no features in features.md",
                    "affected_element": "features.md",
                }],
                evidence={"recall": 0.0, "gt_feature_count": len(gt_features), "agent_feature_count": 0},
                scorer_type="deterministic",
            )

        matched_gt_indices = {gt_idx for _, gt_idx, _ in matches}

        # Separate core and non-core GT features
        core_gt_indices = [i for i, f in enumerate(gt_features) if _is_core_feature(f)]
        non_core_gt_indices = [i for i in range(len(gt_features)) if i not in core_gt_indices]

        matched_core = sum(1 for i in core_gt_indices if i in matched_gt_indices)
        matched_non_core = sum(1 for i in non_core_gt_indices if i in matched_gt_indices)

        # Core features weighted 2x per strategy §2.5
        weighted_matched = matched_non_core + 2 * matched_core
        weighted_total = len(non_core_gt_indices) + 2 * len(core_gt_indices)
        recall = weighted_matched / weighted_total if weighted_total > 0 else 0.0

        # Build failures for missed GT features
        failures: list[dict[str, Any]] = []
        for i, gt_f in enumerate(gt_features):
            if i not in matched_gt_indices:
                name = gt_f.get("name", gt_f.get("feature_name", f"Feature #{i}"))
                is_core = _is_core_feature(gt_f)
                failures.append({
                    "type": "missed_feature",
                    "severity": "critical" if is_core else "major",
                    "evidence": f"GT feature '{name}' not matched by any agent feature",
                    "affected_element": name,
                })

        # Build per-match details
        match_details = []
        for agent_idx, gt_idx, match_score in matches:
            agent_name = agent_features[agent_idx].get(
                "feature_name", agent_features[agent_idx].get("name", f"Agent #{agent_idx}")
            )
            gt_name = gt_features[gt_idx].get(
                "name", gt_features[gt_idx].get("feature_name", f"GT #{gt_idx}")
            )
            match_details.append({
                "agent_feature": agent_name,
                "gt_feature": gt_name,
                "score": round(match_score, 4),
                "is_core": _is_core_feature(gt_features[gt_idx]),
            })

        return ScorerResult(
            metric_name="feature_recall",
            score=round(recall, 4),
            confidence=1.0,
            passed=recall >= self.threshold,
            threshold=self.threshold,
            failures=failures,
            evidence={
                "recall": round(recall, 4),
                "gt_feature_count": len(gt_features),
                "agent_feature_count": len(agent_features),
                "matched_count": len(matches),
                "core_gt_count": len(core_gt_indices),
                "matched_core": matched_core,
                "matched_non_core": matched_non_core,
                "matched_pairs": match_details,
            },
            scorer_type="deterministic",
        )
