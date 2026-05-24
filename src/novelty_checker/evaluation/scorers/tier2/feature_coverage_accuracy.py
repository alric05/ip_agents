"""Feature Coverage Accuracy scorer (Tier-2, deterministic).

Compares per-feature coverage conclusions between agent and SME.

Instead of requiring shared references (which rarely overlap), this scorer
asks: "Does the agent correctly identify which features have prior art
coverage and which don't?"

GT coverage is derived from gt_references.json: if ANY A/B reference has
verdict Y or Y1 for a feature, that feature is "covered".

Agent coverage is extracted from the gap analysis table in final_report.md,
where STRONG/MODERATE = covered and NONE/WEAK = not covered. Falls back
to Feature Mapping rows (F1=Y; F2=N format) if no gap analysis table found.

Features are matched first by ID (F1=F1), then by semantic similarity
using hybrid_feature_score from _matching.py.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from src.novelty_checker.evaluation.scorers._base import NoveltyBaseMetric, ScorerResult
from src.novelty_checker.evaluation.scorers._loader import (
    load_session_artifact,
)
from src.novelty_checker.evaluation.scorers._matching import (
    hybrid_feature_score,
)

_logger = logging.getLogger(__name__)


def _extract_gt_feature_coverage(ground_truth: dict[str, Any]) -> dict[str, str]:
    """Derive per-feature coverage from GT references.

    A feature is "covered" if ANY A/B reference has verdict Y or Y1 for it.
    Returns {feature_id: "covered" or "not_covered"}.
    """
    refs_data = ground_truth.get("references", {})
    if isinstance(refs_data, dict):
        refs_list = refs_data.get("references", [])
    elif isinstance(refs_data, list):
        refs_list = refs_data
    else:
        return {}

    all_features = set()
    for ref in refs_list:
        triage = ref.get("triage_label", ref.get("triage", "")).upper().strip()
        if triage not in ("A", "B"):
            continue
        fc = ref.get("feature_coverage", {})
        for fid in fc:
            all_features.add(fid)

    coverage = {}
    for fid in all_features:
        covered = False
        for ref in refs_list:
            triage = ref.get("triage_label", ref.get("triage", "")).upper().strip()
            if triage not in ("A", "B"):
                continue
            fc = ref.get("feature_coverage", {})
            val = fc.get(fid, {})
            if isinstance(val, dict):
                verdict = (val.get("verdict") or "N").upper().strip()
            else:
                verdict = str(val).upper().strip()
            if verdict in ("Y", "Y1", "YES", "FULL", "PARTIAL", "PARTIALLY"):
                covered = True
                break
        coverage[fid] = "covered" if covered else "not_covered"

    return coverage


def _extract_agent_feature_coverage_gap_table(report_content: str) -> list[dict[str, str]]:
    """Extract per-feature coverage from the gap analysis table.

    Looks for a table with columns including Feature and Coverage Level.
    Returns list of dicts with keys: feature_id, name, coverage, raw_level.
    """
    results = []
    lines = report_content.split("\n")
    in_gap = False
    headers = []
    coverage_col = -1
    feature_col = -1

    for i, line in enumerate(lines):
        low = line.lower()
        if "gap analysis" in low:
            in_gap = True
            continue

        if in_gap and "|" in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]

            if not headers and any(
                "feature" in c.lower() or "coverage" in c.lower() for c in cells
            ):
                headers = cells
                for j, h in enumerate(headers):
                    hl = h.lower()
                    if "coverage" in hl:
                        coverage_col = j
                    if "feature" in hl or j == 0:
                        feature_col = j
                continue

            if all(
                c.replace("-", "").replace(":", "").strip() == "" for c in cells
            ):
                continue

            if (
                headers
                and coverage_col >= 0
                and len(cells) > max(feature_col, coverage_col)
            ):
                feat_text = cells[feature_col]
                cov_text = cells[coverage_col].upper()

                fid_match = re.match(r"(F\d+)\b", feat_text)
                fid = fid_match.group(1) if fid_match else ""
                name = re.sub(r"^F\d+\s*", "", feat_text).strip()

                if "STRONG" in cov_text or "MODERATE" in cov_text or "HIGH" in cov_text:
                    cov = "covered"
                else:
                    cov = "not_covered"

                results.append({
                    "feature_id": fid,
                    "name": name,
                    "coverage": cov,
                    "raw_level": cells[coverage_col].strip(),
                })

        elif in_gap and headers and "|" not in line and line.strip().startswith("#"):
            break

    return results


def _extract_agent_feature_coverage_mapping(report_content: str) -> list[dict[str, str]]:
    """Extract per-feature coverage from Feature Mapping rows.

    Parses lines like "Feature Mapping | F1=Y; F2=Y1; F3=N" and aggregates
    across all references. A feature is "covered" if ANY reference has Y or Y1.
    """
    coverage = {}
    for line in report_content.split("\n"):
        if "feature mapping" not in line.lower() and not re.search(r'F\d+\s*[=:]\s*[YN]', line):
            continue
        pairs = re.findall(r'(F\d+)\s*[=:]\s*(Y1?|N)', line, re.IGNORECASE)
        for fid, val in pairs:
            if fid not in coverage:
                coverage[fid] = set()
            coverage[fid].add(val.upper())

    results = []
    for fid in sorted(coverage):
        vals = coverage[fid]
        if "Y" in vals or "Y1" in vals:
            cov = "covered"
        else:
            cov = "not_covered"
        results.append({
            "feature_id": fid,
            "name": "",
            "coverage": cov,
            "raw_level": str(vals),
        })

    return results


def _extract_agent_feature_coverage(report_content: str) -> list[dict[str, str]]:
    """Extract agent feature coverage, trying gap table first then mapping rows."""
    results = _extract_agent_feature_coverage_gap_table(report_content)
    if results:
        return results
    return _extract_agent_feature_coverage_mapping(report_content)


class FeatureCoverageAccuracyMetric(NoveltyBaseMetric):
    """Feature-level coverage accuracy.

    Compares whether agent and SME agree on which features have prior art
    coverage. Does not require shared references.

    Score = matching features / total GT features.
    Target: >= 0.60
    """

    def __init__(self, threshold: float = 0.60) -> None:
        super().__init__(
            metric_name="feature_coverage_accuracy",
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
        report_content = load_session_artifact(session_path, "final_report.md")
        if not report_content:
            return ScorerResult(
                metric_name="feature_coverage_accuracy",
                score=0.0,
                confidence=0.0,
                passed=False,
                threshold=self.threshold,
                failures=[{
                    "type": "no_report",
                    "severity": "critical",
                    "evidence": "final_report.md not found",
                    "affected_element": "final_report.md",
                }],
                evidence={},
                scorer_type="deterministic",
            )

        gt_coverage = _extract_gt_feature_coverage(ground_truth)
        agent_features = _extract_agent_feature_coverage(report_content)

        if not gt_coverage:
            return ScorerResult(
                metric_name="feature_coverage_accuracy",
                score=0.0,
                confidence=0.0,
                passed=False,
                threshold=self.threshold,
                failures=[],
                evidence={"note": "No feature coverage data in ground truth"},
                scorer_type="deterministic",
            )

        if not agent_features:
            return ScorerResult(
                metric_name="feature_coverage_accuracy",
                score=0.0,
                confidence=0.3,
                passed=False,
                threshold=self.threshold,
                failures=[{
                    "type": "no_gap_analysis",
                    "severity": "major",
                    "evidence": "No gap analysis table or feature mapping found in agent report",
                    "affected_element": "final_report.md",
                }],
                evidence={
                    "gt_features_with_coverage": len(gt_coverage),
                },
                scorer_type="deterministic",
            )

        # Match GT features to agent features
        comparisons = []
        matched_gt = set()
        matched_agent = set()

        # First pass: match by feature ID (F1=F1, F2=F2)
        for gt_fid, gt_cov in gt_coverage.items():
            for j, af in enumerate(agent_features):
                if j in matched_agent:
                    continue
                if af["feature_id"] and af["feature_id"] == gt_fid:
                    comparisons.append({
                        "gt_feature": gt_fid,
                        "agent_feature": af["feature_id"] + " " + af["name"],
                        "gt_coverage": gt_cov,
                        "agent_coverage": af["coverage"],
                        "agent_raw_level": af["raw_level"],
                        "match": gt_cov == af["coverage"],
                        "match_method": "feature_id",
                    })
                    matched_gt.add(gt_fid)
                    matched_agent.add(j)
                    break

        # Second pass: semantic matching for unmatched GT features
        if len(matched_gt) < len(gt_coverage):
            gt_features_data = ground_truth.get("features", {})
            if isinstance(gt_features_data, dict):
                gt_feat_list = gt_features_data.get("features", [])
            elif isinstance(gt_features_data, list):
                gt_feat_list = gt_features_data
            else:
                gt_feat_list = []

            gt_feat_by_id = {}
            for f in gt_feat_list:
                fid = f.get("feature_id") or f.get("id") or ""
                gt_feat_by_id[fid] = f

            unmatched_agent = [
                (j, af) for j, af in enumerate(agent_features) if j not in matched_agent
            ]
            for gt_fid in gt_coverage:
                if gt_fid in matched_gt:
                    continue
                gt_feat = gt_feat_by_id.get(gt_fid, {"name": gt_fid})
                best_score = 0
                best_agent = None
                best_idx = -1
                for j, af in unmatched_agent:
                    agent_feat_dict = {"name": af["name"], "feature_name": af["name"]}
                    score = hybrid_feature_score(agent_feat_dict, gt_feat)
                    if score > best_score:
                        best_score = score
                        best_agent = af
                        best_idx = j

                if best_agent and best_score >= 0.25:
                    comparisons.append({
                        "gt_feature": gt_fid,
                        "agent_feature": best_agent["feature_id"] + " " + best_agent["name"],
                        "gt_coverage": gt_coverage[gt_fid],
                        "agent_coverage": best_agent["coverage"],
                        "agent_raw_level": best_agent["raw_level"],
                        "match": gt_coverage[gt_fid] == best_agent["coverage"],
                        "match_method": "semantic",
                        "match_score": round(best_score, 3),
                    })
                    matched_gt.add(gt_fid)
                    unmatched_agent = [(j2, af2) for j2, af2 in unmatched_agent if j2 != best_idx]
                else:
                    comparisons.append({
                        "gt_feature": gt_fid,
                        "agent_feature": None,
                        "gt_coverage": gt_coverage[gt_fid],
                        "agent_coverage": "unknown",
                        "match": False,
                        "match_method": "unmatched",
                    })

        total = len(comparisons)
        matching = sum(1 for c in comparisons if c["match"])
        score = matching / total if total > 0 else 0.0

        failures = []
        mismatches = [c for c in comparisons if not c["match"]]
        if mismatches:
            failures.append({
                "type": "coverage_mismatch",
                "severity": "minor",
                "evidence": (
                    f"{len(mismatches)} of {total} features have different "
                    f"coverage conclusions"
                ),
                "affected_element": "feature_coverage",
            })

        return ScorerResult(
            metric_name="feature_coverage_accuracy",
            score=round(score, 4),
            confidence=min(1.0, total / 5.0),
            passed=score >= self.threshold,
            threshold=self.threshold,
            failures=failures,
            evidence={
                "total_features": total,
                "matching_features": matching,
                "accuracy": round(score, 4),
                "comparisons": comparisons,
                "gt_coverage": gt_coverage,
                "agent_features_found": len(agent_features),
            },
            scorer_type="deterministic",
        )