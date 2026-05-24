"""Deterministic trademark risk assessment tests."""

from __future__ import annotations

from src.tm_knockout_search_agent.services.risk_assessment import (
    CandidateRiskLabel,
    OverallRiskLabel,
    SourceSearchStatus,
    assess_trademark_risk,
)
from src.tm_knockout_search_agent.state import (
    TrademarkCandidate,
    TrademarkCandidateSource,
    TrademarkSearchCriteria,
)


def _criteria(
    *,
    brand_name: str = "Acme Atlas",
    jurisdictions: list[str] | None = None,
    nice_classes: list[str] | None = None,
    goods_services: str | None = "Retail store services featuring outdoor equipment",
) -> TrademarkSearchCriteria:
    return TrademarkSearchCriteria(
        brand_name=brand_name,
        jurisdictions=jurisdictions or ["US"],
        nice_classes=nice_classes or ["35"],
        goods_services=goods_services,
    )


def _registry_candidate(
    *,
    candidate_id: str = "cm-1",
    mark_name: str = "Acme Atlas",
    jurisdiction: str = "US",
    classes: list[str] | None = None,
    goods_services: str | None = "Retail store services featuring outdoor equipment",
    status: str = "Registered",
    owner: str = "Acme Outdoors LLC",
    raw_source_metadata: dict | None = None,
) -> TrademarkCandidate:
    return TrademarkCandidate(
        id=candidate_id,
        source=TrademarkCandidateSource.COMPUMARK,
        mark_name=mark_name,
        jurisdiction=jurisdiction,
        classes=classes or ["35"],
        goods_services=goods_services,
        status=status,
        owner=owner,
        raw_source_metadata=raw_source_metadata or {},
    )


def test_exact_active_same_class_same_jurisdiction_is_high() -> None:
    assessment = assess_trademark_risk(
        _criteria(),
        [_registry_candidate()],
    )

    assert assessment.overall_risk_label == OverallRiskLabel.HIGH
    assert assessment.findings[0].risk_label == CandidateRiskLabel.HIGH
    assert assessment.findings[0].score >= 70
    assert assessment.findings[0].mark_similarity_band == "identical"
    assert assessment.findings[0].goods_overlap == "same"
    assert "US" in assessment.country_notes


def test_similar_active_related_goods_same_jurisdiction_is_elevated() -> None:
    assessment = assess_trademark_risk(
        _criteria(
            nice_classes=[],
            goods_services="Outdoor backpacks and camping bags",
        ),
        [
            _registry_candidate(
                mark_name="Acme Atlass",
                classes=[],
                goods_services="Outdoor equipment and backpacks",
            )
        ],
    )

    assert assessment.findings[0].risk_label in {
        CandidateRiskLabel.HIGH,
        CandidateRiskLabel.MEDIUM,
    }
    assert assessment.overall_risk_label in {
        OverallRiskLabel.HIGH,
        OverallRiskLabel.MEDIUM,
    }
    assert assessment.findings[0].goods_overlap in {"same", "related"}


def test_compumark_raw_active_flag_marks_candidate_active() -> None:
    assessment = assess_trademark_risk(
        _criteria(brand_name="KLYRA", nice_classes=["3"], goods_services="cosmetics"),
        [
            _registry_candidate(
                mark_name="SPARKXXXX",
                classes=["3"],
                goods_services="Cosmetics",
                status="REGISXXXXX",
                raw_source_metadata={"status": {"active": True}},
            )
        ],
    )

    assert assessment.findings[0].active_status is True
    assert "active_registry_status=true" in assessment.findings[0].reasons


def test_similar_unrelated_goods_famous_owner_is_medium() -> None:
    assessment = assess_trademark_risk(
        _criteria(nice_classes=["35"]),
        [
            _registry_candidate(
                mark_name="Acme Atlass",
                classes=["9"],
                goods_services="Downloadable security software",
                raw_source_metadata={"famous_owner": True},
            )
        ],
    )

    assert assessment.overall_risk_label == OverallRiskLabel.MEDIUM
    assert assessment.findings[0].risk_label == CandidateRiskLabel.MEDIUM
    assert assessment.findings[0].goods_overlap == "unrelated"
    assert assessment.findings[0].famous_or_large_owner is True
    assert any("famous_or_large_owner" in reason for reason in assessment.findings[0].reasons)


def test_only_distant_inactive_marks_are_low_with_explanation() -> None:
    assessment = assess_trademark_risk(
        _criteria(),
        [
            _registry_candidate(
                mark_name="Distant Moon",
                classes=["3"],
                goods_services="Cosmetics",
                status="Dead",
            )
        ],
    )

    assert assessment.overall_risk_label in {
        OverallRiskLabel.LOW,
        OverallRiskLabel.MEDIUM,
    }
    assert assessment.findings[0].risk_label in {
        CandidateRiskLabel.LOW,
        CandidateRiskLabel.MEDIUM,
    }
    assert any("inactive_or_dead_record=true" in reason for reason in assessment.findings[0].reasons)
    assert "risk=" in assessment.explanation


def test_no_candidates_and_sources_succeeded_is_low() -> None:
    assessment = assess_trademark_risk(
        _criteria(),
        [],
        source_statuses=[
            SourceSearchStatus(source="compumark", jurisdiction="US", succeeded=True),
        ],
    )

    assert assessment.overall_risk_label == OverallRiskLabel.LOW
    assert assessment.findings == []
    assert assessment.missing_or_failed_source_notes == []
    assert assessment.explanation == "risk=LOW; candidates=0; required_sources_succeeded=true"


def test_required_compumark_failure_is_search_failed() -> None:
    assessment = assess_trademark_risk(
        _criteria(),
        [],
        source_statuses=[
            SourceSearchStatus(
                source="compumark",
                jurisdiction="US",
                required=True,
                succeeded=False,
                error_message="timeout",
            )
        ],
    )

    assert assessment.overall_risk_label == OverallRiskLabel.SEARCH_FAILED
    assert assessment.missing_or_failed_source_notes == [
        "CompuMark search failed for US: timeout"
    ]
    assert assessment.country_notes["US"].startswith("SEARCH_FAILED")


def test_strong_web_commercial_use_can_raise_to_medium() -> None:
    web_candidate = TrademarkCandidate(
        id="web-1",
        source=TrademarkCandidateSource.WEB_COMMON_LAW,
        title="Acme Atlas official store",
        detected_brand_text="Acme Atlas",
        jurisdiction_hint="US",
        domain="acme-atlas.example",
        snippet="Official store selling outdoor bags and services.",
        use_context="Commercial store sells outdoor equipment under Acme Atlas.",
    )

    assessment = assess_trademark_risk(_criteria(), [web_candidate])

    assert assessment.overall_risk_label == OverallRiskLabel.MEDIUM
    assert assessment.findings[0].risk_label == CandidateRiskLabel.MEDIUM
    assert assessment.findings[0].web_use_strength == "strong"
    assert assessment.findings[0].candidate_source == "web_common_law"


def test_multiple_countries_with_mixed_results_have_country_notes() -> None:
    assessment = assess_trademark_risk(
        _criteria(jurisdictions=["US", "CA"]),
        [
            _registry_candidate(candidate_id="cm-us", jurisdiction="US"),
            _registry_candidate(
                candidate_id="cm-ca",
                mark_name="Distant Moon",
                jurisdiction="CA",
                classes=["3"],
                goods_services="Cosmetics",
                status="Dead",
            ),
        ],
    )

    assert assessment.overall_risk_label == OverallRiskLabel.HIGH
    assert assessment.country_notes["US"].startswith("HIGH")
    assert assessment.country_notes["CA"].startswith(("LOW", "MEDIUM"))
    assert assessment.findings[0].candidate_id == "cm-us"
