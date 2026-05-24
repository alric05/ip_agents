"""Triage Agreement scorer (Tier-2, deterministic).

Measures agreement between agent and SME on A/B/C triage labels
for shared references, using Cohen's kappa.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

from src.novelty_checker.evaluation.scorers._base import NoveltyBaseMetric, ScorerResult
from src.novelty_checker.evaluation.scorers._loader import (
    load_session_artifact,
    parse_references_md,
)
from src.novelty_checker.evaluation.scorers._matching import (
    extract_patent_number,
    match_patent_family,
    normalize_patent_number,
)

_logger = logging.getLogger(__name__)

_TRIAGE_LABELS = ("A", "B", "C")


def _compute_cohens_kappa(
    labels_a: list[str], labels_b: list[str]
) -> float:
    """Compute Cohen's kappa for two raters on the same items.

    Args:
        labels_a: First rater's labels.
        labels_b: Second rater's labels (same length as labels_a).

    Returns:
        Cohen's kappa coefficient in [-1, 1]. Returns 0.0 if undefined.
    """
    n = len(labels_a)
    if n == 0:
        return 0.0
    if n != len(labels_b):
        raise ValueError("Label lists must have the same length")

    # Observed agreement
    agree = sum(1 for a, b in zip(labels_a, labels_b) if a == b)
    p_o = agree / n

    # Expected agreement by chance
    all_labels = set(labels_a) | set(labels_b)
    count_a = Counter(labels_a)
    count_b = Counter(labels_b)
    p_e = sum((count_a[label] / n) * (count_b[label] / n) for label in all_labels)

    if p_e == 1.0:
        return 1.0 if p_o == 1.0 else 0.0

    return (p_o - p_e) / (1.0 - p_e)


def _build_confusion_matrix(
    agent_labels: list[str], gt_labels: list[str]
) -> dict[str, dict[str, int]]:
    """Build a confusion matrix for A/B/C labels.

    Returns dict[gt_label][agent_label] = count.
    """
    matrix: dict[str, dict[str, int]] = {
        gt: {ag: 0 for ag in _TRIAGE_LABELS} for gt in _TRIAGE_LABELS
    }
    for gt_l, ag_l in zip(gt_labels, agent_labels):
        if gt_l in matrix and ag_l in matrix[gt_l]:
            matrix[gt_l][ag_l] += 1
    return matrix


def _load_agent_refs_with_triage(session_path: Path) -> list[dict[str, Any]]:
    """Load agent references with triage labels.

    Prefers references.md (which always has triage labels from the agent's
    curated list) over the accumulator (which may lack triage metadata).
    """
    # Prefer references.md — it has triage labels
    md_content = load_session_artifact(session_path, "references.md")
    if md_content:
        refs = parse_references_md(md_content)
        if refs:
            return refs

    # Fall back to accumulator JSON
    content = load_session_artifact(session_path, "findings_auto_accumulator.json")
    if not content:
        content = load_session_artifact(session_path, "findings_accumulator.json")
    if content:
        try:
            data = json.loads(content)
            if isinstance(data, list) and data:
                return data
            if isinstance(data, dict):
                refs = (
                    data.get("all_references")
                    or data.get("references")
                    or data.get("findings")
                    or []
                )
                if isinstance(refs, list) and refs:
                    return refs
        except (json.JSONDecodeError, TypeError):
            pass

    return []


def _get_triage_label(ref: dict[str, Any]) -> str:
    """Extract and normalize triage label from a reference."""
    for key in ("triage_label", "triage", "label", "relevance", "category"):
        # val = ref.get(key, "").strip().upper()
        val = (ref.get(key) or "").strip().upper()
        if val in _TRIAGE_LABELS:
            return val
    return ""


class TriageAgreementMetric(NoveltyBaseMetric):
    """Measures agreement on A/B/C triage labels for shared references.

    Uses Cohen's kappa, normalized from [-1, 1] to [0, 1].
    Also reports raw agreement rate and confusion matrix.
    """

    def __init__(self, threshold: float = 0.50) -> None:
        super().__init__(
            metric_name="triage_agreement",
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
        agent_refs = _load_agent_refs_with_triage(session_path)

        # Load GT refs
        refs_data = ground_truth.get("references", {})
        if isinstance(refs_data, dict):
            gt_refs = refs_data.get("references", [])
        elif isinstance(refs_data, list):
            gt_refs = refs_data
        else:
            gt_refs = []

        # Find shared references and collect triage labels
        agent_labels: list[str] = []
        gt_labels: list[str] = []
        shared_refs: list[dict] = []

        for gt_ref in gt_refs:
            gt_num = extract_patent_number(gt_ref)
            gt_triage = _get_triage_label(gt_ref)
            if not gt_num or not gt_triage:
                continue

            for agent_ref in agent_refs:
                agent_num = extract_patent_number(agent_ref)
                if not agent_num:
                    continue
                if match_patent_family(agent_num, gt_num):
                    agent_triage = _get_triage_label(agent_ref)
                    if agent_triage:
                        gt_labels.append(gt_triage)
                        agent_labels.append(agent_triage)
                        shared_refs.append({
                            "patent": normalize_patent_number(gt_num),
                            "gt_triage": gt_triage,
                            "agent_triage": agent_triage,
                            "agree": gt_triage == agent_triage,
                        })
                    break

        if not shared_refs:
            return ScorerResult(
                metric_name="triage_agreement",
                score=0.0,
                confidence=0.0,
                passed=False,
                threshold=self.threshold,
                failures=[{
                    "type": "no_shared_references",
                    "severity": "major",
                    "evidence": "No shared references with triage labels found",
                    "affected_element": "references",
                }],
                evidence={
                    "shared_count": 0,
                    "agent_ref_count": len(agent_refs),
                    "gt_ref_count": len(gt_refs),
                },
                scorer_type="deterministic",
            )

        # Compute metrics
        kappa = _compute_cohens_kappa(agent_labels, gt_labels)
        agreement_rate = sum(1 for r in shared_refs if r["agree"]) / len(shared_refs)
        confusion = _build_confusion_matrix(agent_labels, gt_labels)

        # Normalize kappa from [-1, 1] to [0, 1]
        score = (kappa + 1.0) / 2.0

        # A-ref F1 score (per eval_metrics_strategy.md §3.5)
        # Count GT A-refs among shared refs
        gt_a_in_shared = [r for r in shared_refs if r["gt_triage"] == "A"]
        agent_a_in_shared = [r for r in shared_refs if r["agent_triage"] == "A"]
        correct_a = [r for r in shared_refs if r["gt_triage"] == "A" and r["agent_triage"] == "A"]

        a_precision = len(correct_a) / len(agent_a_in_shared) if agent_a_in_shared else 0.0
        a_recall = len(correct_a) / len(gt_a_in_shared) if gt_a_in_shared else 0.0
        a_f1 = (
            2 * a_precision * a_recall / (a_precision + a_recall)
            if (a_precision + a_recall) > 0
            else 0.0
        )

        failures = []
        disagreements = [r for r in shared_refs if not r["agree"]]
        if disagreements:
            failures.append({
                "type": "triage_disagreement",
                "severity": "minor",
                "evidence": (
                    f"{len(disagreements)} of {len(shared_refs)} shared refs "
                    f"have different triage labels"
                ),
                "affected_element": "triage_labels",
            })

        return ScorerResult(
            metric_name="triage_agreement",
            score=round(score, 4),
            confidence=min(1.0, len(shared_refs) / 5.0),
            passed=score >= self.threshold,
            threshold=self.threshold,
            failures=failures,
            evidence={
                "cohens_kappa": round(kappa, 4),
                "normalized_score": round(score, 4),
                "agreement_rate": round(agreement_rate, 4),
                "a_ref_f1": round(a_f1, 4),
                "a_ref_precision": round(a_precision, 4),
                "a_ref_recall": round(a_recall, 4),
                "shared_count": len(shared_refs),
                "confusion_matrix": confusion,
                "shared_refs": shared_refs,
            },
            scorer_type="deterministic",
        )
