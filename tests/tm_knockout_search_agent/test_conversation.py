"""Conversational LLM helper tests for TM knockout search."""

from __future__ import annotations

from langchain_core.messages import AIMessage

from src.tm_knockout_search_agent.services.conversation import (
    INTAKE_SYSTEM_PROMPT,
    analyze_tm_knockout_result,
    extract_tm_search_criteria_from_message,
)


class FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return AIMessage(content=self.response)


def test_extracts_complete_criteria_from_message() -> None:
    llm = FakeLLM(
        """
        {
          "brand_name": "KLYRA",
          "countries": ["US", "EUIPO"],
          "classes": ["3"],
          "goods_services": "cosmetics and skincare",
          "business_context": null,
          "assumptions": [],
          "missing_fields": [],
          "clarification_question": null,
          "ready_for_search": true,
          "reasoning": "All required fields are present.",
          "language": "English"
        }
        """
    )

    result = extract_tm_search_criteria_from_message(
        "Please check KLYRA in the US and EUIPO for class 3 cosmetics.",
        llm=llm,
    )

    assert result.ready_for_search is True
    assert result.brand_name == "KLYRA"
    assert result.countries == ["US", "EUIPO"]
    assert result.classes == ["3"]
    assert result.goods_services == "cosmetics and skincare"


def test_intake_prompt_asks_llm_to_emit_registration_office_codes() -> None:
    assert "ST.3" in INTAKE_SYSTEM_PROMPT
    assert "France -> FR" in INTAKE_SYSTEM_PROMPT
    assert "ask for\n  clarification instead of guessing" in INTAKE_SYSTEM_PROMPT


def test_extracts_llm_supplied_country_code_for_france() -> None:
    result = extract_tm_search_criteria_from_message(
        "Please check LLAMALUSH in France for class 3 cosmetics.",
        llm=FakeLLM(
            """
            {
              "brand_name": "LLAMALUSH",
              "countries": ["FR"],
              "classes": ["3"],
              "goods_services": "cosmetics",
              "business_context": null,
              "assumptions": ["France interpreted as FR by LLM intake."],
              "missing_fields": [],
              "clarification_question": null,
              "ready_for_search": true,
              "reasoning": "All required fields are present.",
              "language": "English"
            }
            """
        ),
    )

    assert result.ready_for_search is True
    assert result.countries == ["FR"]


def test_missing_criteria_gets_clarification_question() -> None:
    result = extract_tm_search_criteria_from_message(
        "Please check KLYRA.",
        llm=FakeLLM(
            """
            {
              "brand_name": "KLYRA",
              "countries": [],
              "classes": [],
              "goods_services": null,
              "business_context": null,
              "assumptions": [],
              "missing_fields": [],
              "clarification_question": null,
              "ready_for_search": false,
              "reasoning": "Missing countries and classes.",
              "language": "English"
            }
            """
        ),
    )

    assert result.ready_for_search is False
    assert "countries or regional trademark systems" in result.missing_fields
    assert "Nice classes" in result.missing_fields
    assert result.clarification_question is not None


def test_ambiguous_europe_requires_clarification() -> None:
    result = extract_tm_search_criteria_from_message(
        "Check KLYRA in Europe for class 3 cosmetics.",
        llm=FakeLLM(
            """
            {
              "brand_name": "KLYRA",
              "countries": ["Europe"],
              "classes": ["3"],
              "goods_services": "cosmetics",
              "business_context": null,
              "assumptions": [],
              "missing_fields": [],
              "clarification_question": null,
              "ready_for_search": true,
              "reasoning": "Europe is ambiguous.",
              "language": "English"
            }
            """
        ),
    )

    assert result.ready_for_search is False
    assert any("Europe is ambiguous" in item for item in result.missing_fields)
    assert result.clarification_question == (
        "Do you mean EUIPO, or specific European countries?"
    )


def test_analyzes_structured_result_into_markdown_response() -> None:
    analysis = analyze_tm_knockout_result(
        {
            "criteria": {"brand_name": "KLYRA"},
            "risk_assessment": {
                "overall_risk_label": "MEDIUM",
                "findings": [],
            },
            "source_execution": {"live_api_calls": True},
            "report_markdown": "# Deterministic report",
        },
        llm=FakeLLM(
            """
            {
              "final_response": "# Trademark Knockout Clearance Report\\n\\nOverall risk: MEDIUM",
              "overall_risk_label": "MEDIUM",
              "shortlist_recommendation": "Proceed only with deeper review.",
              "caveats": ["Preliminary screening only."]
            }
            """
        ),
    )

    assert "Overall risk: MEDIUM" in analysis.final_response
    assert analysis.overall_risk_label == "MEDIUM"
