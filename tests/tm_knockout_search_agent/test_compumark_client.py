"""CompuMark client tests for TM knockout search."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from src.tm_knockout_search_agent.services.compumark_client import (
    CompuMarkAPIError,
    CompuMarkClient,
    CompuMarkConfig,
    CompuMarkConfigError,
    build_compumark_search_requests,
    normalize_registration_office_codes,
)


def test_normalizes_user_jurisdictions_to_compumark_office_codes() -> None:
    assert normalize_registration_office_codes(["US", "EUIPO", "European Union", "uk"]) == [
        "US",
        "EM",
        "GB",
    ]


def test_builds_exact_active_search_request() -> None:
    request = build_compumark_search_requests(
        brand_name="KLYRA",
        jurisdictions=["US", "EUIPO"],
        classes=["3"],
        query_intent="exact",
    )[0]

    assert request["registrationOfficeCodes"] == ["US", "EM"]
    assert request["searchFields"] == [
        {
            "name": "EXACT_WORD_MARK_SPECIFICATION",
            "operator": "EQUALS",
            "value": "KLYRA",
        },
        {"name": "INT_CLASS_NUMBER", "operator": "EQUALS", "value": "3"},
    ]
    assert request["queryOptions"]["activeOnly"] is True
    assert request["queryOptions"]["plurals"] is False
    assert request["queryOptions"]["crossReferences"] is False


def test_builds_similar_active_requests_per_class() -> None:
    requests = build_compumark_search_requests(
        brand_name="KLYRA",
        jurisdictions=["US"],
        classes=["3", "35"],
        query_intent="similar",
    )

    assert len(requests) == 2
    assert requests[0]["searchFields"][0] == {
        "name": "WORD_MARK_SPECIFICATION",
        "operator": "CONTAINS",
        "value": "KLYRA",
    }
    assert requests[0]["searchFields"][1]["value"] == "3"
    assert requests[1]["searchFields"][1]["value"] == "35"
    assert requests[0]["queryOptions"]["activeOnly"] is True
    assert requests[0]["queryOptions"]["plurals"] is True
    assert requests[0]["queryOptions"]["crossReferences"] is True


def test_builds_inactive_contextual_request_with_active_only_false() -> None:
    request = build_compumark_search_requests(
        brand_name="KLYRA",
        jurisdictions=["US"],
        classes=[],
        query_intent="inactive_contextual",
    )[0]

    assert request["queryOptions"]["activeOnly"] is False
    assert request["searchFields"] == [
        {
            "name": "WORD_MARK_SPECIFICATION",
            "operator": "CONTAINS",
            "value": "KLYRA",
        }
    ]


def test_config_from_env_requires_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COMPUMARK_API_KEY", raising=False)

    with pytest.raises(CompuMarkConfigError, match="COMPUMARK_API_KEY"):
        CompuMarkConfig.from_env(env_file=tmp_path / ".env")


def test_config_from_env_loads_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COMPUMARK_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "COMPUMARK_API_KEY=test-key\nCOMPUMARK_TIMEOUT_SECONDS=5\n",
        encoding="utf-8",
    )

    config = CompuMarkConfig.from_env(env_file=env_file)

    assert config.api_key == "test-key"
    assert config.timeout_seconds == 5.0


def test_execute_search_uses_count_search_text_and_normalizes_candidates() -> None:
    calls: list[tuple[str, Mapping[str, Any]]] = []

    def transport(
        url: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: float,
    ) -> Mapping[str, Any]:
        calls.append((url, payload))
        assert headers["X-ApiKey"] == "test-key"
        assert timeout == 5.0
        if url.endswith("/count"):
            return {"counts": {"US": 1, "EM": 2}}
        if url.endswith("/search"):
            return {"ids": {"US": ["US-KLYRA-1"], "EM": ["EM-KLYRA-1", "EM-KLYRA-2"]}}
        if url.endswith("/text"):
            assert payload == {"ids": ["US-KLYRA-1", "EM-KLYRA-1"], "test": True}
            return {
                "trademarks": [
                    {
                        "id": "US-KLYRA-1",
                        "registrationOfficeCode": "US",
                        "wordMarkSpecification": {"markVerbalElementText": "KLYRA"},
                        "status": {
                            "cmNormalisedStatus": "REGISTERED",
                            "application": {
                                "applicationNumber": "98765432",
                                "applicationDate": "20200102",
                            },
                            "registration": {
                                "registrationNumber": "7654321",
                                "registrationDate": "20210304",
                            },
                        },
                        "goodsServices": {
                            "intClassDescriptions": [
                                {
                                    "intClassNumber": "003",
                                    "intGoodsServicesDescription": "Cosmetics and skincare",
                                }
                            ]
                        },
                        "applicants": [{"applicantName": "Klyra Beauty LLC"}],
                    }
                ]
            }
        raise AssertionError(f"Unexpected URL {url}")

    client = CompuMarkClient(
        CompuMarkConfig(api_key="test-key", timeout_seconds=5.0),
        transport=transport,
    )

    result = client.execute_search(
        brand_name="KLYRA",
        jurisdictions=["US", "EUIPO"],
        classes=["3"],
        query_intent="exact",
        max_results=2,
        text_test_mode=True,
    )

    assert [url.rsplit("/", 1)[-1] for url, _payload in calls] == ["count", "search", "text"]
    assert result.counts == {"US": 1, "EM": 2}
    assert result.selected_ids == ["US-KLYRA-1", "EM-KLYRA-1"]
    assert result.truncated is True
    assert result.candidates[0].id == "US-KLYRA-1"
    assert result.candidates[0].mark_name == "KLYRA"
    assert result.candidates[0].classes == ["3"]
    assert result.candidates[0].owner == "Klyra Beauty LLC"
    assert result.candidates[0].registration_number == "7654321"


def test_transport_api_error_is_preserved() -> None:
    def transport(
        url: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: float,
    ) -> Mapping[str, Any]:
        raise CompuMarkAPIError("boom")

    client = CompuMarkClient(CompuMarkConfig(api_key="test-key"), transport=transport)

    with pytest.raises(CompuMarkAPIError, match="boom"):
        client.count({"registrationOfficeCodes": ["US"], "searchFields": []})
