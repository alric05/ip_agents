"""Tool adapter tests for TM knockout search."""

from __future__ import annotations

from src.tm_knockout_search_agent.state import TrademarkCandidateSource
from src.tm_knockout_search_agent.tools.adapters import (
    flag_duplicate_candidates,
    normalize_compumark_result,
    normalize_web_common_law_result,
)


def test_mock_compumark_result_maps_to_trademark_candidate() -> None:
    candidate = normalize_compumark_result(
        {
            "markName": "Acme Atlas",
            "jurisdiction": "US",
            "niceClasses": ["035", "9"],
            "goodsServices": "Retail store services featuring outdoor equipment",
            "status": "Registered",
            "owner": "Acme Outdoors LLC",
            "applicationNumber": "88776655",
            "registrationNumber": "6123456",
            "filingDate": "2020-01-02",
            "registrationDate": "2021-03-04",
            "recordUrl": "https://example.test/trademarks/6123456",
            "recordId": "cm-1",
        }
    )

    assert candidate.id == "cm-1"
    assert candidate.source == TrademarkCandidateSource.COMPUMARK
    assert candidate.mark_name == "Acme Atlas"
    assert candidate.normalized_mark_name == "ACME ATLAS"
    assert candidate.jurisdiction == "US"
    assert candidate.classes == ["35", "9"]
    assert candidate.goods_services == "Retail store services featuring outdoor equipment"
    assert candidate.status == "Registered"
    assert candidate.owner == "Acme Outdoors LLC"
    assert candidate.application_number == "88776655"
    assert candidate.registration_number == "6123456"
    assert candidate.duplicate_key == "registration:6123456"
    assert candidate.raw_source_metadata["recordId"] == "cm-1"


def test_mock_web_result_maps_to_trademark_candidate() -> None:
    candidate = normalize_web_common_law_result(
        {
            "title": "Acme Atlas outdoor gear",
            "url": "https://acme.example/atlas",
            "snippet": "Acme Atlas sells packs and tents in Oregon.",
            "domain": "acme.example",
            "detectedBrandText": "Acme Atlas",
            "jurisdictionHint": "US",
            "ownerCompanyHint": "Acme Outdoors LLC",
            "useContext": "Retail sale of outdoor gear",
        }
    )

    assert candidate.source == TrademarkCandidateSource.WEB_COMMON_LAW
    assert candidate.id.startswith("web-")
    assert candidate.title == "Acme Atlas outdoor gear"
    assert candidate.source_url == "https://acme.example/atlas"
    assert candidate.snippet == "Acme Atlas sells packs and tents in Oregon."
    assert candidate.domain == "acme.example"
    assert candidate.detected_brand_text == "Acme Atlas"
    assert candidate.normalized_mark_name == "ACME ATLAS"
    assert candidate.jurisdiction_hint == "US"
    assert candidate.owner_company_hint == "Acme Outdoors LLC"
    assert candidate.use_context == "Retail sale of outdoor gear"
    assert candidate.raw_source_metadata["domain"] == "acme.example"


def test_missing_optional_fields_do_not_crash_normalization() -> None:
    compumark_candidate = normalize_compumark_result({"mark": "Loft Loop"})
    web_candidate = normalize_web_common_law_result({"title": "Loft Loop bags"})

    assert compumark_candidate.mark_name == "Loft Loop"
    assert compumark_candidate.jurisdiction is None
    assert compumark_candidate.classes == []
    assert compumark_candidate.owner is None
    assert compumark_candidate.duplicate_key is not None
    assert web_candidate.title == "Loft Loop bags"
    assert web_candidate.detected_brand_text is None
    assert web_candidate.duplicate_key is not None


def test_duplicate_compumark_records_detect_by_registration_number() -> None:
    first = normalize_compumark_result(
        {
            "mark": "Acme Atlas",
            "jurisdiction": "US",
            "owner": "Acme Outdoors LLC",
            "registrationNumber": "6123456",
            "recordId": "cm-1",
        }
    )
    second = normalize_compumark_result(
        {
            "mark": "ACME ATLAS",
            "jurisdiction": "US",
            "owner": "Acme Outdoors LLC",
            "registrationNumber": "6123456",
            "recordId": "cm-2",
        }
    )

    flagged = flag_duplicate_candidates([first, second])

    assert flagged[0].duplicate_of is None
    assert flagged[1].duplicate_of == "cm-1"
    assert flagged[0].duplicate_key == flagged[1].duplicate_key


def test_duplicate_compumark_records_detect_by_application_number() -> None:
    first = normalize_compumark_result(
        {
            "mark": "Acme Atlas",
            "jurisdiction": "US",
            "owner": "Acme Outdoors LLC",
            "applicationNumber": "88776655",
            "recordId": "cm-1",
        }
    )
    second = normalize_compumark_result(
        {
            "mark": "Acme Atlas",
            "jurisdiction": "CA",
            "owner": "Different Owner",
            "applicationNumber": "88776655",
            "recordId": "cm-2",
        }
    )

    flagged = flag_duplicate_candidates([first, second])

    assert flagged[1].duplicate_of == "cm-1"
    assert flagged[1].duplicate_key == "application:88776655"


def test_duplicate_compumark_records_detect_by_mark_jurisdiction_owner() -> None:
    first = normalize_compumark_result(
        {
            "mark": "Acme Atlas",
            "jurisdiction": "US",
            "owner": "Acme Outdoors LLC",
            "recordId": "cm-1",
        }
    )
    second = normalize_compumark_result(
        {
            "mark": "ACME ATLAS",
            "jurisdiction": "US",
            "owner": "Acme Outdoors LLC",
            "recordId": "cm-2",
        }
    )

    flagged = flag_duplicate_candidates([first, second])

    assert flagged[1].duplicate_of == "cm-1"
    assert flagged[0].duplicate_key.startswith("identity:")
