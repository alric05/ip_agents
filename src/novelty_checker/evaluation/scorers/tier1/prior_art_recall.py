"""Prior Art Recall scorer (Tier-1, deterministic).

Measures what fraction of the SME-identified blocking references (A+B)
the agent found, using family-level patent matching.
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
    normalize_patent_number,
)

_logger = logging.getLogger(__name__)


def _load_agent_references(session_path: Path) -> list[dict[str, Any]]:
    """Load agent references from session artifacts.

    Tries findings_accumulator.json first (structured), falls back to
    references.md (markdown table).
    """
    # Try structured JSON first (agent may write either filename)
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
            _logger.debug("Could not parse accumulator JSON, trying references.md")

    # Fall back to markdown
    md_content = load_session_artifact(session_path, "references.md")
    if md_content:
        return parse_references_md(md_content)

    return []


def _extract_gt_blocking_refs(
    ground_truth: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract A+B level references from ground truth.

    Returns only references with triage_label == "A" per eval_metrics_strategy.md §2.3.
    """
    refs_data = ground_truth.get("references", {})
    if isinstance(refs_data, dict):
        refs_list = refs_data.get("references", [])
    elif isinstance(refs_data, list):
        refs_list = refs_data
    else:
        return []

    blocking = []
    for ref in refs_list:
        label = ref.get("triage_label", ref.get("triage", "")).upper().strip()
        if label == "A":
            blocking.append(ref)
    return blocking


def _find_matches(
    agent_refs: list[dict[str, Any]],
    gt_refs: list[dict[str, Any]],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Match agent references against GT references using family-level matching.

    Returns:
        (found_refs, missed_refs, extra_refs)
        - found_refs: GT refs that the agent found (with agent match info)
        - missed_refs: GT refs the agent did not find
        - extra_refs: agent refs not in GT (for precision calculation)
    """
    agent_numbers = [extract_patent_number(r) for r in agent_refs]
    gt_numbers = [extract_patent_number(r) for r in gt_refs]

    found_refs = []
    missed_refs = []
    matched_agent_indices: set[int] = set()

    for gt_idx, gt_ref in enumerate(gt_refs):
        gt_num = gt_numbers[gt_idx]
        if not gt_num:
            missed_refs.append(gt_ref)
            continue

        matched = False
        for agent_idx, agent_num in enumerate(agent_numbers):
            if not agent_num:
                continue
            if match_patent_family(agent_num, gt_num):
                found_refs.append({
                    "gt_ref": gt_ref,
                    "agent_ref": agent_refs[agent_idx],
                    "gt_number": normalize_patent_number(gt_num),
                    "agent_number": normalize_patent_number(agent_num),
                })
                matched_agent_indices.add(agent_idx)
                matched = True
                break

        if not matched:
            missed_refs.append(gt_ref)

    # Extra refs: agent found but not in GT
    extra_refs = [
        agent_refs[i]
        for i in range(len(agent_refs))
        if i not in matched_agent_indices
    ]

    return found_refs, missed_refs, extra_refs


class PriorArtRecallMetric(NoveltyBaseMetric):
    """Measures recall of SME-identified blocking references (A-level only).

    recall = |agent_refs INTERSECT gt_A_refs| / |gt_A_refs|
    precision = |agent_refs INTERSECT gt_A_refs| / |agent_refs|

    The primary score is recall. Precision is reported in evidence.

    Alpha threshold: >= 0.40 (per eval_metrics_strategy.md §2.3)
    """

    def __init__(self, threshold: float = 0.40) -> None:
        super().__init__(
            metric_name="prior_art_recall",
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
        gt_blocking = _extract_gt_blocking_refs(ground_truth)

        if not gt_blocking:
            return ScorerResult(
                metric_name="prior_art_recall",
                score=0.0,
                confidence=0.0,
                passed=True,
                threshold=self.threshold,
                failures=[],
                evidence={
                    "note": "No blocking references in ground truth",
                    "agent_ref_count": len(agent_refs),
                },
                scorer_type="deterministic",
            )

        found_refs, missed_refs, extra_refs = _find_matches(agent_refs, gt_blocking)

        recall = len(found_refs) / len(gt_blocking)
        precision = (
            len(found_refs) / len(agent_refs) if agent_refs else 0.0
        )

        # Build failures list
        failures: list[dict[str, Any]] = []
        for ref in missed_refs:
            pub_num = extract_patent_number(ref)
            triage = ref.get("triage_label", ref.get("triage", "")).upper()
            severity = "critical" if triage == "A" else "major"
            failures.append({
                "type": "missed_reference",
                "severity": severity,
                "evidence": (
                    f"GT ref {pub_num} ({triage}-level) not found in agent references"
                ),
                "affected_element": pub_num,
            })

        return ScorerResult(
            metric_name="prior_art_recall",
            score=recall,
            confidence=1.0,
            passed=recall >= self.threshold,
            threshold=self.threshold,
            failures=failures,
            evidence={
                "recall": recall,
                "precision": precision,
                "gt_blocking_count": len(gt_blocking),
                "agent_ref_count": len(agent_refs),
                "found_count": len(found_refs),
                "missed_count": len(missed_refs),
                "extra_count": len(extra_refs),
                "found_refs": [
                    {"gt": r["gt_number"], "agent": r["agent_number"]}
                    for r in found_refs
                ],
                "missed_refs": [
                    extract_patent_number(r) for r in missed_refs
                ],
            },
            scorer_type="deterministic",
        )
