"""Deterministic Markdown report generation for TM knockout screening.

JSON artifacts are the source of truth. This module formats those artifacts
into a concise v1 Markdown report without calling external APIs or an LLM.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import Field, TypeAdapter, field_validator

from src.tm_knockout_search_agent import prompts
from src.tm_knockout_search_agent.services.risk_assessment import (
    CandidateFinding,
    OverallRiskLabel,
    SourceSearchStatus,
    TrademarkRiskAssessment,
)
from src.tm_knockout_search_agent.state import (
    ArtifactModel,
    TrademarkCandidate,
    TrademarkSearchCriteria,
    TrademarkSearchPlan,
)


REPORT_SECTION_TITLES = [
    "Executive summary",
    "Search criteria",
    "Sources searched",
    "Overall risk evaluation",
    "Most relevant findings",
    "Country / regional notes",
    "Web and common-law observations",
    "Adversarial review summary",
    "Limitations",
    "Recommendation for deeper review",
    "Fixed disclaimer",
]


class AdversarialReview(ArtifactModel):
    """Structured adversarial review summary for the final report."""

    summary: str = "No adversarial review artifact was provided."
    checks: dict[str, bool] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    source_failures: list[str] = Field(default_factory=list)

    @field_validator("summary")
    @classmethod
    def _summary_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("adversarial review summary must not be empty")
        return stripped

    @field_validator("issues", "source_failures", mode="after")
    @classmethod
    def _normalize_lists(cls, value: list[str]) -> list[str]:
        return _dedupe_text(value)


class TrademarkReportArtifacts(ArtifactModel):
    """Structured source artifacts consumed by the Markdown report."""

    request: dict[str, Any] = Field(default_factory=dict)
    search_criteria: TrademarkSearchCriteria
    query_plan: TrademarkSearchPlan | None = None
    compumark_results: list[dict[str, Any]] = Field(default_factory=list)
    web_results: list[dict[str, Any]] = Field(default_factory=list)
    normalized_candidates: list[TrademarkCandidate] = Field(default_factory=list)
    ranked_findings: list[CandidateFinding] = Field(default_factory=list)
    risk_assessment: TrademarkRiskAssessment
    adversarial_review: AdversarialReview = Field(default_factory=AdversarialReview)
    source_statuses: list[SourceSearchStatus] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    recommendation: str | None = None

    @field_validator("limitations", mode="after")
    @classmethod
    def _normalize_limitations(cls, value: list[str]) -> list[str]:
        return _dedupe_text(value)

    @property
    def candidate_ids(self) -> set[str]:
        """Return known normalized candidate ids."""
        return {candidate.id for candidate in self.normalized_candidates}


def build_report_artifacts(
    artifacts: TrademarkReportArtifacts | Mapping[str, Any],
) -> TrademarkReportArtifacts:
    """Normalize report artifact aliases into the report data contract."""
    if isinstance(artifacts, TrademarkReportArtifacts):
        return artifacts

    search_criteria = _first_present(
        artifacts,
        "search_criteria",
        "criteria",
        "scope",
    )
    query_plan = _first_present(artifacts, "query_plan", "search_plan")
    risk_assessment = _first_present(
        artifacts,
        "risk_assessment",
        "assessments",
    )
    normalized_candidates = _coerce_list(
        _first_present(
            artifacts,
            "normalized_candidates",
            "candidates",
        )
        or [],
        TrademarkCandidate,
    )
    normalized_risk = _coerce_model(risk_assessment, TrademarkRiskAssessment)
    ranked_findings = _coerce_list(
        _first_present(artifacts, "ranked_findings") or normalized_risk.findings,
        CandidateFinding,
    )
    adversarial_review = _first_present(artifacts, "adversarial_review") or {}

    return TrademarkReportArtifacts(
        request=dict(_first_present(artifacts, "request") or {}),
        search_criteria=_coerce_model(search_criteria, TrademarkSearchCriteria),
        query_plan=(
            _coerce_model(query_plan, TrademarkSearchPlan)
            if query_plan is not None
            else None
        ),
        compumark_results=list(_first_present(artifacts, "compumark_results") or []),
        web_results=list(_first_present(artifacts, "web_results") or []),
        normalized_candidates=normalized_candidates,
        ranked_findings=ranked_findings,
        risk_assessment=normalized_risk,
        adversarial_review=_coerce_model(adversarial_review, AdversarialReview),
        source_statuses=_coerce_list(
            _first_present(artifacts, "source_statuses") or [],
            SourceSearchStatus,
        ),
        limitations=list(_first_present(artifacts, "limitations") or []),
        recommendation=_first_present(artifacts, "recommendation"),
    )


def generate_trademark_report(
    artifacts: TrademarkReportArtifacts | Mapping[str, Any],
    *,
    max_findings: int = 5,
) -> str:
    """Generate the v1 trademark knockout Markdown report."""
    data = build_report_artifacts(artifacts)
    sections = [
        _section("1. Executive summary", _executive_summary(data)),
        _section("2. Search criteria", _search_criteria(data)),
        _section("3. Sources searched", _sources_searched(data)),
        _section("4. Overall risk evaluation", _risk_evaluation(data)),
        _section("5. Most relevant findings", _most_relevant_findings(data, max_findings)),
        _section("6. Country / regional notes", _country_notes(data)),
        _section("7. Web and common-law observations", _web_observations(data)),
        _section("8. Adversarial review summary", _adversarial_review(data)),
        _section("9. Limitations", _limitations(data)),
        _section("10. Recommendation for deeper review", _recommendation(data)),
        _section("11. Fixed disclaimer", prompts.FIXED_DISCLAIMER),
    ]
    return "# Trademark Knockout Clearance Report\n\n" + "\n\n".join(sections) + "\n"


def source_failure_notes(data: TrademarkReportArtifacts) -> list[str]:
    """Return deduplicated source failure notes that must appear in the report."""
    notes = [
        *data.risk_assessment.missing_or_failed_source_notes,
        *data.adversarial_review.source_failures,
    ]
    for status in data.source_statuses:
        if status.succeeded:
            continue
        scope = status.jurisdiction or status.regional_system or "requested scope"
        source_name = _source_display_name(status.source)
        message = status.error_message or "unspecified source failure"
        notes.append(f"{source_name} search failed for {scope}: {message}")
    return _dedupe_text(notes)


def _first_present(artifacts: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in artifacts and artifacts[key] is not None:
            return artifacts[key]
    return None


def _coerce_model(value: Any, model: type[ArtifactModel]) -> Any:
    if isinstance(value, model):
        return value
    return model.model_validate(value)


def _coerce_list(value: Any, model: type[ArtifactModel]) -> list[Any]:
    return TypeAdapter(list[model]).validate_python(value)


def _dedupe_text(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        stripped = str(value).strip()
        if not stripped or stripped in seen:
            continue
        normalized.append(stripped)
        seen.add(stripped)
    return normalized


def _section(title: str, body: str) -> str:
    return f"## {title}\n\n{body.strip()}"


def _locations(criteria: TrademarkSearchCriteria) -> list[str]:
    return [*criteria.jurisdictions, *criteria.regional_systems]


def _format_list(values: list[str], *, empty: str = "Not provided") -> str:
    return ", ".join(values) if values else empty


def _format_bool(value: bool) -> str:
    return "yes" if value else "no"


def _executive_summary(data: TrademarkReportArtifacts) -> str:
    risk_label = data.risk_assessment.overall_risk_label.value
    return "\n".join(
        [
            f"- Proposed brand: {data.search_criteria.brand_name}",
            f"- Overall risk label: {risk_label}",
            f"- Strongest findings surfaced: {len(data.ranked_findings)}",
            f"- Source failure notes: {len(source_failure_notes(data))}",
            f"- Summary: {data.risk_assessment.explanation}",
        ]
    )


def _search_criteria(data: TrademarkReportArtifacts) -> str:
    criteria = data.search_criteria
    goods = criteria.goods_services or "Limited goods/services context"
    assumptions = _format_list(criteria.assumptions, empty="None documented")
    clarification = (
        _format_list(criteria.clarification_reasons, empty="None")
        if criteria.requires_clarification
        else "None"
    )
    return "\n".join(
        [
            f"- Brand name: {criteria.brand_name}",
            f"- Countries/systems: {_format_list(_locations(criteria))}",
            f"- Nice classes: {_format_list(criteria.all_classes)}",
            f"- Goods/services: {goods}",
            f"- Business context: {criteria.business_context or 'Not provided'}",
            f"- Assumptions: {assumptions}",
            f"- Clarification flags: {clarification}",
        ]
    )


def _sources_searched(data: TrademarkReportArtifacts) -> str:
    lines: list[str] = []
    if data.query_plan is None:
        lines.append("- Query plan artifact: Not provided")
    else:
        for group in data.query_plan.query_groups:
            required = "required" if group.required else "optional"
            locations = _format_list([*group.jurisdictions, *group.regional_systems])
            lines.append(
                "- "
                f"{group.stage.value}: {group.source.value}; "
                f"intent={group.query_intent.value}; {required}; "
                f"scope={locations}; max_results={group.max_results}"
            )

    failures = source_failure_notes(data)
    if failures:
        lines.append("- Source failures documented:")
        lines.extend(f"  - {note}" for note in failures)
    else:
        lines.append("- Source failures documented: none")
    return "\n".join(lines)


def _risk_evaluation(data: TrademarkReportArtifacts) -> str:
    risk_label = data.risk_assessment.overall_risk_label.value
    return "\n".join(
        [
            f"- Overall risk label: {risk_label}",
            f"- Explanation: {data.risk_assessment.explanation}",
            f"- Candidate findings reviewed: {len(data.ranked_findings)}",
            f"- Required source failures: {_format_bool(bool(source_failure_notes(data)))}",
        ]
    )


def _most_relevant_findings(
    data: TrademarkReportArtifacts,
    max_findings: int,
) -> str:
    if not data.ranked_findings:
        return "- No relevant candidate conflicts were surfaced in the supplied artifacts."

    candidates_by_id = {candidate.id: candidate for candidate in data.normalized_candidates}
    lines: list[str] = []
    for finding in data.ranked_findings[:max_findings]:
        candidate = candidates_by_id.get(finding.candidate_id)
        owner = candidate.owner or candidate.owner_company_hint if candidate else None
        status = candidate.status if candidate else None
        classes = candidate.classes if candidate else []
        location = (
            finding.jurisdiction
            or finding.regional_system
            or finding.jurisdiction_hint
            or "unspecified"
        )
        reasons = _format_list(finding.reasons, empty="No reasons supplied")
        lines.append(
            "- "
            f"Candidate ID: {finding.candidate_id}; "
            f"risk={finding.risk_label.value}; score={finding.score}; "
            f"name={finding.display_name}; source={finding.candidate_source}; "
            f"location={location}; status={status or 'not provided'}; "
            f"owner={owner or 'not provided'}; classes={_format_list(classes)}; "
            f"reasons={reasons}"
        )
    return "\n".join(lines)


def _country_notes(data: TrademarkReportArtifacts) -> str:
    if not data.risk_assessment.country_notes:
        return "- No country or regional differences were identified in the supplied artifacts."
    return "\n".join(
        f"- {location}: {note}"
        for location, note in sorted(data.risk_assessment.country_notes.items())
    )


def _web_observations(data: TrademarkReportArtifacts) -> str:
    web_findings = [
        finding
        for finding in data.ranked_findings
        if finding.candidate_source == "web_common_law"
    ]
    lines = [
        f"- Web result artifacts supplied: {len(data.web_results)}",
        f"- Web/common-law findings surfaced: {len(web_findings)}",
    ]
    if not web_findings:
        lines.append("- No strong web/common-law observations were surfaced.")
        return "\n".join(lines)

    candidates_by_id = {candidate.id: candidate for candidate in data.normalized_candidates}
    for finding in web_findings[:3]:
        candidate = candidates_by_id.get(finding.candidate_id)
        domain = candidate.domain if candidate else None
        context = candidate.use_context or candidate.snippet if candidate else None
        lines.append(
            "- "
            f"Candidate ID: {finding.candidate_id}; "
            f"strength={finding.web_use_strength}; "
            f"domain={domain or 'not provided'}; "
            f"context={context or 'not provided'}"
        )
    return "\n".join(lines)


def _adversarial_review(data: TrademarkReportArtifacts) -> str:
    lines = [f"- Summary: {data.adversarial_review.summary}"]
    if data.adversarial_review.checks:
        for check_name, passed in sorted(data.adversarial_review.checks.items()):
            lines.append(f"- {check_name}: {'pass' if passed else 'review'}")
    if data.adversarial_review.issues:
        lines.append("- Issues:")
        lines.extend(f"  - {issue}" for issue in data.adversarial_review.issues)
    else:
        lines.append("- Issues: none documented")
    return "\n".join(lines)


def _limitations(data: TrademarkReportArtifacts) -> str:
    defaults = [
        "This v1 report is generated from structured JSON artifacts.",
        "The report does not independently verify source records beyond the supplied artifacts.",
        "Local legal standards and marketplace conditions require professional review.",
    ]
    if data.risk_assessment.overall_risk_label == OverallRiskLabel.SEARCH_FAILED:
        defaults.append("Required source failure prevents reliable screening.")
    limitations = _dedupe_text([*defaults, *data.limitations, *source_failure_notes(data)])
    return "\n".join(f"- {limitation}" for limitation in limitations)


def _recommendation(data: TrademarkReportArtifacts) -> str:
    if data.recommendation:
        return f"- {data.recommendation}"

    risk_label = data.risk_assessment.overall_risk_label
    if risk_label == OverallRiskLabel.SEARCH_FAILED:
        text = (
            "Do not rely on this screening result until required source failures "
            "are resolved and the report is regenerated."
        )
    elif risk_label == OverallRiskLabel.HIGH:
        text = (
            "Do not shortlist without focused trademark professional review of "
            "the strongest conflicts."
        )
    elif risk_label == OverallRiskLabel.MEDIUM:
        text = (
            "Shortlist only with caution and prioritize deeper review of the "
            "medium-risk findings and marketplace context."
        )
    else:
        text = (
            "The brand may be shortlisted for deeper review subject to the "
            "limitations and source coverage documented above."
        )
    return f"- {text}"


def _source_display_name(source: str) -> str:
    normalized = source.strip().lower()
    if normalized == "compumark":
        return "CompuMark"
    if normalized in {"web_search", "web_common_law"}:
        return "Web/common-law"
    return source.strip() or "Unknown source"


__all__ = [
    "AdversarialReview",
    "REPORT_SECTION_TITLES",
    "TrademarkReportArtifacts",
    "build_report_artifacts",
    "generate_trademark_report",
    "source_failure_notes",
]
