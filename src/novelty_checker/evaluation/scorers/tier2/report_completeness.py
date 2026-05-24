"""Report Section Completeness scorer (Tier-2, deterministic).

Checks whether all required sections are present in the final report.
Per eval_metrics_strategy.md §3.1.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from src.novelty_checker.evaluation.scorers._base import NoveltyBaseMetric, ScorerResult
from src.novelty_checker.evaluation.scorers._loader import load_session_artifact

_logger = logging.getLogger(__name__)

# Required report sections (11 per strategy doc)
_REQUIRED_SECTIONS = [
    "executive summary",
    "scope",
    "feature matrix",
    "search strategy",
    "prior art analysis",
    "feature coverage",
    "novelty assessment",
    "risk assessment",
    "recommendations",
    "limitations",
    "references",
]

# Alternative names that map to the same required section.
#
# Kept expansive so the scorer tolerates reasonable naming variation.
# Every agent we've run produces at least some non-canonical headings,
# and the scorer's job is to verify the INFORMATION is present in the
# session — not to enforce a specific section title.
_SECTION_ALIASES = {
    # Executive summary
    "summary": "executive summary",
    "key finding": "executive summary",
    "key findings": "executive summary",
    # Scope
    "invention scope": "scope",
    "scope summary": "scope",
    "feature plan": "scope",
    # Feature matrix
    "features": "feature matrix",
    "key features": "feature matrix",
    "feature table": "feature matrix",
    "feature matrix (core analytical deliverable)": "feature matrix",
    # Search strategy
    "search methodology": "search strategy",
    "search approach": "search strategy",
    "search log": "search strategy",
    "search traceability": "search strategy",
    "transactional search summary": "search strategy",
    # Prior art analysis
    "prior art": "prior art analysis",
    "prior art found": "prior art analysis",
    "prior art findings": "prior art analysis",
    "prior art summary": "prior art analysis",
    "patent record": "prior art analysis",
    "patents record view": "prior art analysis",
    "non-patent": "prior art analysis",
    "non-patent / other technical record view": "prior art analysis",
    "results list": "prior art analysis",
    # Feature coverage
    "coverage analysis": "feature coverage",
    "coverage matrix": "feature coverage",
    "feature coverage analysis": "feature coverage",
    "feature-reference coverage": "feature coverage",
    "gap analysis": "feature coverage",
    "gap analysis table": "feature coverage",
    # Novelty assessment
    "novelty conclusion": "novelty assessment",
    "verdict": "novelty assessment",
    "overall assessment": "novelty assessment",
    "triage results": "novelty assessment",
    # Risk assessment
    "risk analysis": "risk assessment",
    "blocking risk": "risk assessment",
    "blocking risk analysis": "risk assessment",
    "blocking potential": "risk assessment",
    "novelty risk": "risk assessment",
    # Recommendations
    "next steps": "recommendations",
    "action items": "recommendations",
    "recommendations for further searching": "recommendations",
    "recommendations for further search": "recommendations",
    # Limitations
    "known limitations": "limitations",
    "caveats": "limitations",
    # References
    "bibliography": "references",
    "cited references": "references",
    "reference list": "references",
    "sources": "references",
    "source list": "references",
    # Landscape / overview — intentionally not aliased to executive summary
    # (it's a supplementary section, not the executive summary itself).
}


def _extract_section_headers(report_content: str) -> list[str]:
    """Extract markdown section headers (## or #) from report content."""
    headers = []
    for line in report_content.split("\n"):
        match = re.match(r"^#{1,3}\s+(.+)", line.strip())
        if match:
            header = match.group(1).strip().lower()
            # Strip numbering like "1. " or "1) "
            header = re.sub(r"^\d+[\.\)]\s*", "", header)
            # Strip bold markers
            header = header.replace("**", "").strip()
            headers.append(header)
    return headers


def _match_section(header: str, required_sections: list[str]) -> str | None:
    """Match a header to a required section, using exact match then aliases.

    Uses word-boundary regex rather than plain substring to avoid
    false positives like "Landscape Overview" claiming the
    "executive summary" slot via the "overview" alias. The whole alias
    phrase (or required section name) must appear as a complete token
    in the header.
    """
    header_lower = header.lower().strip()

    # Direct match on required section names
    for section in required_sections:
        if re.search(rf"\b{re.escape(section)}\b", header_lower):
            return section

    # Longest alias first so e.g. "gap analysis table" wins over "gap analysis"
    # when both would match — more specific mapping takes precedence.
    for alias, canonical in sorted(
        _SECTION_ALIASES.items(), key=lambda kv: -len(kv[0])
    ):
        if re.search(rf"\b{re.escape(alias)}\b", header_lower):
            return canonical

    return None


class ReportCompletenessMetric(NoveltyBaseMetric):
    """Checks if all 11 required report sections are present.

    Score = sections_found / 11.
    Alpha gate threshold: 1.0 (100%) per eval_metrics_strategy.md §3.1.
    """

    def __init__(self, threshold: float = 1.0) -> None:
        super().__init__(
            metric_name="report_section_completeness",
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
                metric_name="report_section_completeness",
                score=0.0,
                confidence=1.0,
                passed=False,
                threshold=self.threshold,
                failures=[{
                    "type": "no_report",
                    "severity": "critical",
                    "evidence": "final_report.md not found or empty",
                    "affected_element": "final_report.md",
                }],
                evidence={"sections_found": 0, "sections_required": len(_REQUIRED_SECTIONS)},
                scorer_type="deterministic",
            )

        headers = _extract_section_headers(report_content)
        found_sections: dict[str, str] = {}  # required_section -> matched_header

        for header in headers:
            matched = _match_section(header, _REQUIRED_SECTIONS)
            if matched and matched not in found_sections:
                found_sections[matched] = header

        # Fallback: the "references" section content may live in a sibling
        # `references.md` artifact instead of an inline section. The
        # scorer's job is to verify the information is present in the
        # session, not to enforce a specific file layout.
        if "references" not in found_sections:
            refs_path = session_path / "references.md"
            if refs_path.exists() and refs_path.stat().st_size > 100:
                found_sections["references"] = "(references.md artifact)"

        missing = [s for s in _REQUIRED_SECTIONS if s not in found_sections]
        score = len(found_sections) / len(_REQUIRED_SECTIONS)

        failures = [
            {
                "type": "missing_section",
                "severity": "major",
                "evidence": f"Required section '{section}' not found in report",
                "affected_element": section,
            }
            for section in missing
        ]

        return ScorerResult(
            metric_name="report_section_completeness",
            score=round(score, 4),
            confidence=1.0,
            passed=score >= self.threshold,
            threshold=self.threshold,
            failures=failures,
            evidence={
                "sections_found": len(found_sections),
                "sections_required": len(_REQUIRED_SECTIONS),
                "found_sections": found_sections,
                "missing_sections": missing,
                "all_headers": headers,
            },
            scorer_type="deterministic",
        )
