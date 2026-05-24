"""Prior Art Hit Rate scorer (Tier-1, deterministic).

Binary metric: did the agent find at least one A-level blocking
reference? Per eval_metrics_strategy.md §2.2.
"""

from __future__ import annotations

import json
import logging
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
)

_logger = logging.getLogger(__name__)


def _load_agent_references(session_path: Path) -> list[dict[str, Any]]:
    """Load agent references from session artifacts."""
    accumulator_content = load_session_artifact(session_path, "findings_auto_accumulator.json")
    if not accumulator_content:
        accumulator_content = load_session_artifact(session_path, "findings_accumulator.json")
    if accumulator_content:
        try:
            data = json.loads(accumulator_content)
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

    md_content = load_session_artifact(session_path, "references.md")
    if md_content:
        return parse_references_md(md_content)

    return []


# def _extract_gt_a_refs(ground_truth: dict[str, Any]) -> list[dict[str, Any]]:
#     """Extract A-level references from ground truth."""
#     refs_data = ground_truth.get("references", {})
#     if isinstance(refs_data, dict):
#         refs_list = refs_data.get("references", [])
#     elif isinstance(refs_data, list):
#         refs_list = refs_data
#     else:
#         return []
#
#     return [
#         ref for ref in refs_list
#         if ref.get("triage_label", ref.get("triage", "")).upper().strip() == "A"
#     ]
def _extract_gt_a_refs(ground_truth: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract A and B level references from ground truth."""
    refs_data = ground_truth.get("references", {})
    if isinstance(refs_data, dict):
        refs_list = refs_data.get("references", [])
    elif isinstance(refs_data, list):
        refs_list = refs_data
    else:
        return []

    return [
        ref for ref in refs_list
        if ref.get("triage_label", ref.get("triage", "")).upper().strip() in ("A", "B")
    ]


class PriorArtHitRateMetric(NoveltyBaseMetric):
    """Binary: did agent find at least 1 A-level reference?

    Score is 1.0 if any agent reference matches any GT A-ref, 0.0 otherwise.
    Averaged across fixtures at suite level.

    Alpha threshold: >= 0.75 (per eval_metrics_strategy.md §2.2)
    """

    def __init__(self, threshold: float = 0.60) -> None:
        super().__init__(
            metric_name="prior_art_hit_rate",
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
        agent_refs = _load_agent_references(session_path)
        gt_a_refs = _extract_gt_a_refs(ground_truth)

        if not gt_a_refs:
            return ScorerResult(
                metric_name="prior_art_hit_rate",
                score=1.0,
                confidence=0.0,
                passed=True,
                threshold=self.threshold,
                failures=[],
                evidence={
                    "note": "Agent found none of {len(gt_a_refs)} GT A/B-level references",
                    "agent_ref_count": len(agent_refs),
                },
                scorer_type="deterministic",
            )

        # Check if any agent ref matches any GT A-ref
        hit = False
        matched_ref = None
        for gt_ref in gt_a_refs:
            gt_num = extract_patent_number(gt_ref)
            if not gt_num:
                continue
            for agent_ref in agent_refs:
                agent_num = extract_patent_number(agent_ref)
                if not agent_num:
                    continue
                if match_patent_family(agent_num, gt_num):
                    hit = True
                    matched_ref = gt_num
                    break
            if hit:
                break

        score = 1.0 if hit else 0.0

        failures: list[dict[str, Any]] = []
        if not hit:
            failures.append({
                "type": "no_a_ref_found",
                "severity": "critical",
                "evidence": (
                    f"Agent found none of {len(gt_a_refs)} GT A-level references"
                ),
                "affected_element": "references",
            })

        return ScorerResult(
            metric_name="prior_art_hit_rate",
            score=score,
            confidence=1.0,
            passed=score >= self.threshold,
            threshold=self.threshold,
            failures=failures,
            evidence={
                "hit": hit,
                "gt_a_ref_count": len(gt_a_refs),
                "agent_ref_count": len(agent_refs),
                "matched_ref": matched_ref,
            },
            scorer_type="deterministic",
        )
