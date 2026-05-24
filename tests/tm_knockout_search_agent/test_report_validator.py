"""Trademark knockout report validation tests."""

from __future__ import annotations

from src.tm_knockout_search_agent.services.query_planner import plan_trademark_search
from src.tm_knockout_search_agent.services.report import (
    AdversarialReview,
    generate_trademark_report,
)
from src.tm_knockout_search_agent.services.report_validator import (
    validate_trademark_report,
)
from src.tm_knockout_search_agent.services.risk_assessment import (
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
        nice_classes=["3"],
        goods_services="Cosmetics and skincare",
    )


def _candidate(candidate_id: str = "cm-1") -> TrademarkCandidate:
    return TrademarkCandidate(
        id=candidate_id,
        source=TrademarkCandidateSource.COMPUMARK,
        mark_name="KLYRA",
        jurisdiction="US",
        classes=["3"],
        goods_services="Cosmetics and skincare",
        status="Registered",
        owner="Klyra Beauty LLC",
    )


def _valid_artifacts() -> dict:
    criteria = _criteria()
    candidates = [_candidate()]
    assessment = assess_trademark_risk(criteria, candidates)
    return {
        "search_criteria": criteria,
        "query_plan": plan_trademark_search(criteria),
        "normalized_candidates": candidates,
        "ranked_findings": assessment.findings,
        "risk_assessment": assessment,
        "adversarial_review": AdversarialReview(
            summary="All deterministic v1 report checks completed.",
            checks={"candidate_ids_linked": True},
        ),
    }


def _issue_codes(markdown: str, artifacts: dict) -> set[str]:
    result = validate_trademark_report(markdown, artifacts)
    assert result.valid is False
    return {issue.code for issue in result.issues}


def test_missing_disclaimer_fails_validation() -> None:
    artifacts = _valid_artifacts()
    markdown = generate_trademark_report(artifacts)
    markdown_without_disclaimer = markdown.split("## 11. Fixed disclaimer")[0]

    codes = _issue_codes(markdown_without_disclaimer, artifacts)

    assert "missing_section" in codes
    assert "missing_disclaimer" in codes


def test_unknown_candidate_id_in_report_data_fails_validation() -> None:
    artifacts = _valid_artifacts()
    artifacts["ranked_findings"] = [
        artifacts["ranked_findings"][0].model_copy(update={"candidate_id": "cm-missing"})
    ]
    markdown = generate_trademark_report(artifacts)

    codes = _issue_codes(markdown, artifacts)

    assert "unknown_candidate_id" in codes


def test_missing_search_criteria_fails_validation() -> None:
    artifacts = _valid_artifacts()
    markdown = generate_trademark_report(artifacts)
    invalid_artifacts = {
        "risk_assessment": artifacts["risk_assessment"],
        "normalized_candidates": artifacts["normalized_candidates"],
        "ranked_findings": artifacts["ranked_findings"],
    }

    codes = _issue_codes(markdown, invalid_artifacts)

    assert "missing_search_criteria" in codes
    assert "invalid_report_data" in codes


def test_search_criteria_without_scope_fails_validation() -> None:
    criteria = TrademarkSearchCriteria(
        brand_name="KLYRA",
        jurisdictions=[],
        nice_classes=[],
    )
    assessment = assess_trademark_risk(criteria, [])
    artifacts = {
        "search_criteria": criteria,
        "query_plan": plan_trademark_search(criteria),
        "normalized_candidates": [],
        "risk_assessment": assessment,
    }
    markdown = generate_trademark_report(artifacts)

    codes = _issue_codes(markdown, artifacts)

    assert "missing_countries_or_systems" in codes
    assert "missing_classes_or_goods_services" in codes
