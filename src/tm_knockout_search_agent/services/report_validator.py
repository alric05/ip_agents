"""Validation for TM knockout Markdown reports and source artifacts."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from pydantic import Field, ValidationError

from src.tm_knockout_search_agent import prompts
from src.tm_knockout_search_agent.services.report import (
    REPORT_SECTION_TITLES,
    TrademarkReportArtifacts,
    build_report_artifacts,
    source_failure_notes,
)
from src.tm_knockout_search_agent.services.risk_assessment import OverallRiskLabel
from src.tm_knockout_search_agent.state import ArtifactModel


BANNED_REPORT_TERMS = [
    r"\bpatents?\b",
    r"\bprior art\b",
    r"\bnovelty\b",
    r"\binventions?\b",
    r"\bclaim elements?\b",
    r"\bnpl\b",
    r"\bcitations?\b",
]


class ReportValidationIssue(ArtifactModel):
    """One deterministic report validation issue."""

    code: str
    message: str
    severity: str = "error"


class ReportValidationResult(ArtifactModel):
    """Validation result for a report and its source artifacts."""

    valid: bool
    issues: list[ReportValidationIssue] = Field(default_factory=list)


def validate_trademark_report(
    markdown: str,
    artifacts: TrademarkReportArtifacts | Mapping[str, Any],
) -> ReportValidationResult:
    """Validate the v1 Markdown report against structured source artifacts."""
    issues: list[ReportValidationIssue] = []
    sections = extract_report_sections(markdown)

    _check_required_sections(sections, issues)
    _check_disclaimer(sections, issues)
    _check_banned_terms(markdown, issues)

    data = _try_build_artifacts(artifacts, issues)
    if data is not None:
        _check_risk_label(markdown, data, issues)
        _check_search_criteria(data, issues)
        _check_candidate_references(data, issues)
        _check_source_failures(markdown, data, issues)

    return ReportValidationResult(valid=not issues, issues=issues)


def extract_report_sections(markdown: str) -> dict[str, str]:
    """Extract v1 report section bodies keyed by lowercase section title."""
    pattern = re.compile(
        r"^##\s+(?P<number>\d+)\.\s+(?P<title>.+?)\s*$",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(markdown))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        title = match.group("title").strip().lower()
        sections[title] = markdown[body_start:body_end].strip()
    return sections


def _try_build_artifacts(
    artifacts: TrademarkReportArtifacts | Mapping[str, Any],
    issues: list[ReportValidationIssue],
) -> TrademarkReportArtifacts | None:
    if isinstance(artifacts, Mapping):
        if not any(key in artifacts and artifacts[key] is not None for key in ("search_criteria", "criteria", "scope")):
            issues.append(
                _issue(
                    "missing_search_criteria",
                    "Report data must include search_criteria with brand, countries/systems, and classes or goods/services.",
                )
            )
        if not any(key in artifacts and artifacts[key] is not None for key in ("risk_assessment", "assessments")):
            issues.append(
                _issue(
                    "missing_risk_assessment",
                    "Report data must include risk_assessment.",
                )
            )

    try:
        return build_report_artifacts(artifacts)
    except (TypeError, ValueError, ValidationError) as exc:
        issues.append(
            _issue(
                "invalid_report_data",
                f"Report data failed structured validation: {exc}",
            )
        )
        return None


def _check_required_sections(
    sections: dict[str, str],
    issues: list[ReportValidationIssue],
) -> None:
    for title in REPORT_SECTION_TITLES:
        key = title.lower()
        if key not in sections:
            issues.append(_issue("missing_section", f"Missing required section: {title}"))
        elif not sections[key].strip():
            issues.append(_issue("empty_section", f"Required section is empty: {title}"))


def _check_disclaimer(
    sections: dict[str, str],
    issues: list[ReportValidationIssue],
) -> None:
    disclaimer = sections.get("fixed disclaimer", "")
    if not disclaimer:
        issues.append(
            _issue(
                "missing_disclaimer",
                "Fixed disclaimer section must exist and contain text.",
            )
        )
        return
    if prompts.FIXED_DISCLAIMER not in disclaimer:
        issues.append(
            _issue(
                "unexpected_disclaimer",
                "Fixed disclaimer section does not match the configured disclaimer text.",
            )
        )


def _check_banned_terms(
    markdown: str,
    issues: list[ReportValidationIssue],
) -> None:
    for pattern in BANNED_REPORT_TERMS:
        if re.search(pattern, markdown, flags=re.IGNORECASE):
            issues.append(
                _issue(
                    "banned_terminology",
                    f"Report contains non-trademark terminology matching {pattern!r}.",
                )
            )


def _check_risk_label(
    markdown: str,
    data: TrademarkReportArtifacts,
    issues: list[ReportValidationIssue],
) -> None:
    risk_label = data.risk_assessment.overall_risk_label.value
    allowed = {label.value for label in OverallRiskLabel}
    if risk_label not in allowed:
        issues.append(
            _issue(
                "invalid_risk_label",
                f"Overall risk label must be one of {sorted(allowed)}.",
            )
        )
    if risk_label not in markdown:
        issues.append(
            _issue(
                "risk_label_missing_from_report",
                "Overall risk label from JSON artifacts must appear in the Markdown report.",
            )
        )


def _check_search_criteria(
    data: TrademarkReportArtifacts,
    issues: list[ReportValidationIssue],
) -> None:
    criteria = data.search_criteria
    if not criteria.brand_name.strip():
        issues.append(_issue("missing_brand_name", "Search criteria must include a brand name."))

    if not [*criteria.jurisdictions, *criteria.regional_systems]:
        issues.append(
            _issue(
                "missing_countries_or_systems",
                "Search criteria must include countries or regional systems.",
            )
        )

    if not criteria.all_classes and not criteria.goods_services:
        issues.append(
            _issue(
                "missing_classes_or_goods_services",
                "Search criteria must include Nice classes or goods/services.",
            )
        )


def _check_candidate_references(
    data: TrademarkReportArtifacts,
    issues: list[ReportValidationIssue],
) -> None:
    known_ids = data.candidate_ids
    for finding in data.ranked_findings:
        if finding.candidate_id not in known_ids:
            issues.append(
                _issue(
                    "unknown_candidate_id",
                    f"Ranked finding references unknown candidate id: {finding.candidate_id}",
                )
            )


def _check_source_failures(
    markdown: str,
    data: TrademarkReportArtifacts,
    issues: list[ReportValidationIssue],
) -> None:
    for note in source_failure_notes(data):
        if note not in markdown:
            issues.append(
                _issue(
                    "source_failure_not_documented",
                    f"Source failure note is missing from the report: {note}",
                )
            )


def _issue(code: str, message: str) -> ReportValidationIssue:
    return ReportValidationIssue(code=code, message=message)


__all__ = [
    "BANNED_REPORT_TERMS",
    "ReportValidationIssue",
    "ReportValidationResult",
    "extract_report_sections",
    "validate_trademark_report",
]
