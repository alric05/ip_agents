"""Trademark knockout report generation tests."""

from __future__ import annotations

from src.tm_knockout_search_agent.services.query_planner import plan_trademark_search
from src.tm_knockout_search_agent.services.report import (
    REPORT_SECTION_TITLES,
    AdversarialReview,
    generate_trademark_report,
)
from src.tm_knockout_search_agent.services.report_validator import (
    validate_trademark_report,
)
from src.tm_knockout_search_agent.services.risk_assessment import (
    SourceSearchStatus,
    assess_trademark_risk,
)
from src.tm_knockout_search_agent.state import (
    TrademarkCandidate,
    TrademarkCandidateSource,
    TrademarkSearchCriteria,
)


def _criteria() -> TrademarkSearchCriteria:
    return TrademarkSearchCriteria(
        brand_name="KLYRA",
        jurisdictions=["US"],
        regional_systems=["EUIPO"],
        nice_classes=["3"],
        goods_services="Cosmetics and skincare",
        assumptions=["English-language screening"],
    )


def _candidate(
    *,
    candidate_id: str = "cm-1",
    mark_name: str = "KLYRA",
    source: TrademarkCandidateSource = TrademarkCandidateSource.COMPUMARK,
    status: str = "Registered",
) -> TrademarkCandidate:
    return TrademarkCandidate(
        id=candidate_id,
        source=source,
        mark_name=mark_name,
        jurisdiction="US",
        classes=["3"],
        goods_services="Cosmetics and skincare",
        status=status,
        owner="Klyra Beauty LLC",
    )


def _web_candidate() -> TrademarkCandidate:
    return TrademarkCandidate(
        id="web-1",
        source=TrademarkCandidateSource.WEB_COMMON_LAW,
        title="Klyra official skincare store",
        detected_brand_text="KLYRA",
        jurisdiction_hint="US",
        domain="klyra.example",
        snippet="Official store selling skincare products.",
        use_context="Commercial skincare store using KLYRA.",
    )


def _artifacts(
    *,
    candidates: list[TrademarkCandidate] | None = None,
    source_statuses: list[SourceSearchStatus] | None = None,
) -> dict:
    criteria = _criteria()
    normalized_candidates = candidates or []
    assessment = assess_trademark_risk(
        criteria,
        normalized_candidates,
        source_statuses=source_statuses,
    )
    return {
        "request": {"brand": "KLYRA"},
        "search_criteria": criteria,
        "query_plan": plan_trademark_search(criteria),
        "normalized_candidates": normalized_candidates,
        "ranked_findings": assessment.findings,
        "risk_assessment": assessment,
        "adversarial_review": AdversarialReview(
            summary="All deterministic v1 report checks completed.",
            checks={
                "requested_scope_reviewed": True,
                "limitations_documented": True,
            },
            source_failures=assessment.missing_or_failed_source_notes,
        ),
        "source_statuses": source_statuses or [],
        "web_results": [{"title": "Klyra official skincare store"}]
        if any(candidate.source == TrademarkCandidateSource.WEB_COMMON_LAW for candidate in normalized_candidates)
        else [],
    }


def test_low_risk_no_relevant_conflicts_report_validates() -> None:
    artifacts = _artifacts()

    markdown = generate_trademark_report(artifacts)
    result = validate_trademark_report(markdown, artifacts)

    assert result.valid is True
    assert "Overall risk label: LOW" in markdown
    assert "No relevant candidate conflicts" in markdown
    for index, title in enumerate(REPORT_SECTION_TITLES, start=1):
        assert f"## {index}. {title}" in markdown
    assert "patent" not in markdown.lower()


def test_high_risk_report_with_top_candidate_validates() -> None:
    artifacts = _artifacts(candidates=[_candidate()])

    markdown = generate_trademark_report(artifacts)
    result = validate_trademark_report(markdown, artifacts)

    assert result.valid is True
    assert "Overall risk label: HIGH" in markdown
    assert "Candidate ID: cm-1" in markdown
    assert "Klyra Beauty LLC" in markdown


def test_search_failed_report_validates_when_source_failure_documented() -> None:
    failure = SourceSearchStatus(
        source="compumark",
        jurisdiction="US",
        required=True,
        succeeded=False,
        error_message="timeout",
    )
    artifacts = _artifacts(source_statuses=[failure])

    markdown = generate_trademark_report(artifacts)
    result = validate_trademark_report(markdown, artifacts)

    assert result.valid is True
    assert "Overall risk label: SEARCH_FAILED" in markdown
    assert "CompuMark search failed for US: timeout" in markdown


def test_web_common_law_observations_are_reported() -> None:
    artifacts = _artifacts(candidates=[_web_candidate()])

    markdown = generate_trademark_report(artifacts)
    result = validate_trademark_report(markdown, artifacts)

    assert result.valid is True
    assert "Web/common-law findings surfaced: 1" in markdown
    assert "domain=klyra.example" in markdown
