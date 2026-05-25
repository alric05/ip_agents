"""Tests for the LLM-directed CompuMark conversational flow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage

from src.tm_knockout_search_agent.services.compumark_client import CompuMarkAPIError
from src.tm_knockout_search_agent.services.llm_compumark_flow import (
    run_llm_compumark_knockout_flow,
)


class SequentialLLM:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = [AIMessage(content=json.dumps(response)) for response in responses]
        self.prompts: list[Any] = []

    def invoke(self, messages):
        self.prompts.append(messages)
        if not self.responses:
            raise AssertionError("No fake LLM responses left.")
        return self.responses.pop(0)


class FakeCompuMarkClient:
    def __init__(self, *, fail_first_count: bool = False) -> None:
        self.fail_first_count = fail_first_count
        self.count_calls: list[dict[str, Any]] = []
        self.search_calls: list[dict[str, Any]] = []
        self.text_calls: list[list[str]] = []

    def count(self, payload):
        self.count_calls.append(dict(payload))
        if self.fail_first_count and len(self.count_calls) == 1:
            raise CompuMarkAPIError("registrationOfficeCodes - invalid code France")
        return {"counts": {"FR": 1}}

    def search(self, payload):
        self.search_calls.append(dict(payload))
        return {"ids": {"FR": ["FR-LLAMALUSH-1"]}}

    def retrieve_text(self, ids, *, test=None):
        self.text_calls.append(list(ids))
        return {
            "trademarks": [
                {
                    "id": "FR-LLAMALUSH-1",
                    "registrationOfficeCode": "FR",
                    "wordMarkSpecification": {
                        "markVerbalElementText": "LLAMALUSH"
                    },
                    "status": {
                        "cmNormalisedStatus": "REGISTERED",
                        "application": {
                            "applicationNumber": "123",
                            "applicationDate": "20200101",
                        },
                        "registration": {
                            "registrationNumber": "456",
                            "registrationDate": "20210101",
                        },
                    },
                    "goodsServices": {
                        "intClassDescriptions": [
                            {
                                "intClassNumber": "003",
                                "intGoodsServicesDescription": "Cosmetics",
                            }
                        ]
                    },
                    "applicants": [{"applicantName": "Llamalush SAS"}],
                }
            ]
        }


def _intake_response() -> dict[str, Any]:
    return {
        "brand_name": "LLAMALUSH",
        "countries": ["FR"],
        "classes": ["3"],
        "goods_services": "cosmetics",
        "business_context": None,
        "assumptions": [],
        "missing_fields": [],
        "clarification_question": None,
        "ready_for_search": True,
        "reasoning": "All required fields are present.",
        "language": "English",
    }


def _question_response() -> dict[str, Any]:
    return {
        "search_level": "EXACT_ACTIVE",
        "question": "Find active exact LLAMALUSH marks in FR for Nice class 3.",
        "is_valid": True,
        "validation_notes": None,
        "assumptions": [],
    }


def _payload_response(office_code: str = "FR") -> dict[str, Any]:
    return {
        "search_level": "EXACT_ACTIVE",
        "payload": {
            "registrationOfficeCodes": [office_code],
            "limitWOresultsToDesignated": False,
            "searchFields": [
                {
                    "name": "EXACT_WORD_MARK_SPECIFICATION",
                    "operator": "EQUALS",
                    "value": "LLAMALUSH",
                },
                {"name": "INT_CLASS_NUMBER", "operator": "EQUALS", "value": "3"},
            ],
            "queryOptions": {
                "activeOnly": True,
                "phonetics": False,
                "plurals": False,
                "crossReferences": False,
                "japanesePhonetics": False,
                "centralEuropeanPhonetics": False,
            },
        },
        "is_valid": True,
        "rationale": "Exact active search.",
        "warnings": [],
    }


def _analysis_response() -> dict[str, Any]:
    return {
        "final_response": "# Trademark Knockout Clearance Report\n\nOverall risk: HIGH",
        "overall_risk_label": "HIGH",
        "most_problematic_candidates": [
            {"id": "FR-LLAMALUSH-1", "reason": "Exact active Class 3 match in FR."}
        ],
        "conclusions": "Exact active conflict surfaced.",
        "caveats": ["Preliminary screening only."],
    }


def test_llm_compumark_flow_writes_artifacts_and_fetches_content(tmp_path: Path) -> None:
    llm = SequentialLLM(
        [
            _intake_response(),
            _question_response(),
            _payload_response(),
            _analysis_response(),
        ]
    )
    client = FakeCompuMarkClient()

    result = run_llm_compumark_knockout_flow(
        message="Check LLAMALUSH in France class 3.",
        session_id="llm-flow-success",
        sessions_base_dir=str(tmp_path / "sessions"),
        search_levels=["EXACT_ACTIVE"],
        llm=llm,
        client=client,
    )

    assert result["status"] == "COMPLETED"
    assert result["risk_assessment"]["overall_risk_label"] == "HIGH"
    assert result["normalized_candidates"][0]["mark_name"] == "LLAMALUSH"
    assert client.count_calls[0]["registrationOfficeCodes"] == ["FR"]
    assert client.search_calls[0]["searchFields"][0]["name"] == (
        "EXACT_WORD_MARK_SPECIFICATION"
    )
    assert client.text_calls == [["FR-LLAMALUSH-1"]]
    assert (
        tmp_path
        / "sessions"
        / "tm_knockout_search_agent"
        / "llm-flow-success"
        / "final_report.md"
    ).exists()
    assert (
        tmp_path
        / "sessions"
        / "tm_knockout_search_agent"
        / "llm-flow-success"
        / "query_plan.json"
    ).exists()


def test_llm_compumark_flow_returns_missing_input_without_api(tmp_path: Path) -> None:
    llm = SequentialLLM(
        [
            {
                "brand_name": "LLAMALUSH",
                "countries": ["FR"],
                "classes": [],
                "goods_services": "cosmetics",
                "business_context": None,
                "assumptions": [],
                "missing_fields": [],
                "clarification_question": None,
                "ready_for_search": False,
                "reasoning": "Missing Nice class.",
                "language": "English",
            }
        ]
    )
    client = FakeCompuMarkClient()

    result = run_llm_compumark_knockout_flow(
        message="Check LLAMALUSH in France.",
        sessions_base_dir=str(tmp_path / "sessions"),
        llm=llm,
        client=client,
    )

    assert result["status"] == "NEEDS_INPUT"
    assert "Nice classes" in result["missing_fields"]
    assert client.count_calls == []


def test_llm_compumark_flow_retries_payload_after_api_error(tmp_path: Path) -> None:
    llm = SequentialLLM(
        [
            _intake_response(),
            _question_response(),
            _payload_response("France"),
            _payload_response("FR"),
            _analysis_response(),
        ]
    )
    client = FakeCompuMarkClient(fail_first_count=True)

    result = run_llm_compumark_knockout_flow(
        message="Check LLAMALUSH in France class 3.",
        session_id="llm-flow-retry",
        sessions_base_dir=str(tmp_path / "sessions"),
        search_levels=["EXACT_ACTIVE"],
        max_payload_retries=1,
        llm=llm,
        client=client,
    )

    correction_prompt = "\n".join(str(message.content) for message in llm.prompts[3])
    assert "previous API call failed" in correction_prompt
    assert "invalid code France" in correction_prompt
    assert len(client.count_calls) == 2
    assert client.count_calls[1]["registrationOfficeCodes"] == ["FR"]
    assert result["status"] == "COMPLETED"
