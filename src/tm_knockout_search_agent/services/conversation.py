"""Conversational LLM helpers for TM knockout search.

The LLM handles intake extraction and narrative analysis. Source execution and
artifact generation remain in deterministic services so live API behavior stays
auditable and testable.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import Field, field_validator, model_validator

from src.tm_knockout_search_agent import prompts
from src.tm_knockout_search_agent.state import ArtifactModel


class ConversationalIntakeResult(ArtifactModel):
    """Structured criteria extracted from a user message by the LLM."""

    brand_name: str | None = None
    countries: list[str] = Field(default_factory=list)
    classes: list[str] = Field(default_factory=list)
    goods_services: str | None = None
    business_context: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    clarification_question: str | None = None
    ready_for_search: bool = False
    reasoning: str | None = None
    language: str = "English"

    @field_validator("countries", "classes", "assumptions", "missing_fields", mode="after")
    @classmethod
    def _strip_lists(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            stripped = item.strip()
            if stripped and stripped not in seen:
                normalized.append(stripped)
                seen.add(stripped)
        return normalized

    @model_validator(mode="after")
    def _derive_readiness(self) -> "ConversationalIntakeResult":
        missing = list(self.missing_fields)
        if not self.brand_name:
            missing.append("brand")
        if not self.countries:
            missing.append("countries or regional trademark systems")
        if not self.classes:
            missing.append("Nice classes")

        if any(value.strip().upper() == "EUROPE" for value in self.countries):
            missing.append("Europe is ambiguous; specify EUIPO or countries")

        missing = _dedupe(missing)
        object.__setattr__(self, "missing_fields", missing)
        object.__setattr__(self, "ready_for_search", not missing)
        if missing and not self.clarification_question:
            object.__setattr__(
                self,
                "clarification_question",
                _clarification_question(missing),
            )
        return self


class ConversationalAnalysisResult(ArtifactModel):
    """LLM-authored final analysis grounded in structured artifacts."""

    final_response: str = Field(..., min_length=1)
    overall_risk_label: str | None = None
    shortlist_recommendation: str | None = None
    caveats: list[str] = Field(default_factory=list)


def extract_tm_search_criteria_from_message(
    message: str,
    *,
    llm: Any | None = None,
) -> ConversationalIntakeResult:
    """Use an LLM to extract TM knockout criteria from natural language."""
    active_llm = llm or _default_llm()
    response = active_llm.invoke(
        [
            _system_message(INTAKE_SYSTEM_PROMPT),
            _human_message(
                "Extract criteria from this user message and return JSON only.\n\n"
                f"User message:\n{message}"
            ),
        ]
    )
    payload = _loads_json_object(_message_content_to_text(response.content))
    return ConversationalIntakeResult.model_validate(payload)


def analyze_tm_knockout_result(
    result: dict[str, Any],
    *,
    llm: Any | None = None,
) -> ConversationalAnalysisResult:
    """Use an LLM to produce the final conversational report from artifacts."""
    active_llm = llm or _default_llm()
    response = active_llm.invoke(
        [
            _system_message(ANALYSIS_SYSTEM_PROMPT),
            _human_message(
                "Analyze these TM knockout artifacts and return JSON only.\n\n"
                f"{json.dumps(_analysis_payload(result), indent=2, sort_keys=True)}"
            ),
        ]
    )
    payload = _loads_json_object(_message_content_to_text(response.content))
    return ConversationalAnalysisResult.model_validate(payload)


def _analysis_payload(result: dict[str, Any]) -> dict[str, Any]:
    source_execution = result.get("source_execution") or {}
    risk = result.get("risk_assessment") or {}
    return {
        "criteria": result.get("criteria"),
        "search_plan": result.get("search_plan"),
        "source_execution": {
            "completed_query_group_ids": source_execution.get("completed_query_group_ids"),
            "completed_stages": source_execution.get("completed_stages"),
            "compumark_results": _compact_compumark_results(
                source_execution.get("compumark_results") or []
            ),
            "web_results": source_execution.get("web_results"),
            "errors": source_execution.get("errors"),
            "live_api_calls": source_execution.get("live_api_calls"),
        },
        "risk_assessment": {
            "overall_risk_label": risk.get("overall_risk_label"),
            "explanation": risk.get("explanation"),
            "country_notes": risk.get("country_notes"),
            "findings": risk.get("findings", [])[:10],
            "missing_or_failed_source_notes": risk.get("missing_or_failed_source_notes"),
        },
        "stopping_decision": result.get("stopping_decision"),
        "deterministic_report": result.get("report_markdown"),
        "fixed_disclaimer": prompts.FIXED_DISCLAIMER,
    }


def _compact_compumark_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in results:
        compact.append(
            {
                "query_group_id": item.get("query_group_id"),
                "stage": item.get("stage"),
                "succeeded": item.get("succeeded"),
                "counts": item.get("counts"),
                "selected_ids": item.get("selected_ids"),
                "raw_trademark_count": item.get("raw_trademark_count"),
                "candidates": [
                    {
                        key: candidate.get(key)
                        for key in [
                            "id",
                            "mark_name",
                            "jurisdiction",
                            "classes",
                            "goods_services",
                            "status",
                            "owner",
                            "application_number",
                            "registration_number",
                        ]
                    }
                    for candidate in item.get("candidates", [])[:10]
                    if isinstance(candidate, dict)
                ],
            }
        )
    return compact


def _loads_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("LLM response must be a JSON object")
    return value


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
        ).strip()
    return str(content)


def _default_llm() -> Any:
    from src.config.llm import get_llm

    return get_llm()


def _system_message(content: str) -> Any:
    from langchain_core.messages import SystemMessage

    return SystemMessage(content=content)


def _human_message(content: str) -> Any:
    from langchain_core.messages import HumanMessage

    return HumanMessage(content=content)


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            output.append(value)
            seen.add(value)
    return output


def _clarification_question(missing: list[str]) -> str:
    if any("Europe is ambiguous" in value for value in missing):
        return "Do you mean EUIPO, or specific European countries?"
    return (
        "Please provide the missing trademark search criteria: "
        f"{', '.join(missing)}."
    )


INTAKE_SYSTEM_PROMPT = """You are the intake layer for tm_knockout_search_agent.

Extract structured criteria for first-pass trademark knockout screening.
Return JSON only with these keys:
- brand_name: string or null
- countries: list of CompuMark/WIPO ST.3-style registration office codes or
  regional systems ready for search
- classes: list of Nice class numbers as strings
- goods_services: string or null
- business_context: string or null
- assumptions: list of strings
- missing_fields: list of strings
- clarification_question: string or null
- ready_for_search: boolean
- reasoning: short string
- language: output language, default English

Rules:
- Required: one brand, countries/regional systems, and Nice classes.
- For clear country names, use your own trademark office knowledge to return
  the appropriate registration office code, for example France -> FR,
  United States -> US, Germany -> DE, United Kingdom -> GB.
- Preserve valid user-provided codes.
- If the user says Europe, mark it missing/ambiguous and ask whether EUIPO or
  specific countries are intended.
- If the user says EUIPO or European Union, treat it as EUIPO.
- If you are not confident about a jurisdiction/system code, ask for
  clarification instead of guessing.
- Do not invent missing criteria.
- Support one brand only in v1.
"""


ANALYSIS_SYSTEM_PROMPT = f"""You are the final analysis layer for tm_knockout_search_agent.

Use only the provided structured artifacts. CompuMark is the primary registry
source. Web/common-law search may be a deterministic placeholder; do not claim
live web search unless artifacts explicitly show it.

Return JSON only:
- final_response: markdown trademark knockout clearance report
- overall_risk_label: LOW, MEDIUM, HIGH, or SEARCH_FAILED
- shortlist_recommendation: short string
- caveats: list of strings

The report must include: executive summary, search criteria, sources searched,
overall risk, strongest findings, country/system notes, web/common-law
observations, limitations, recommendation for deeper review, and this fixed
disclaimer:
{prompts.FIXED_DISCLAIMER}
"""


__all__ = [
    "ConversationalAnalysisResult",
    "ConversationalIntakeResult",
    "analyze_tm_knockout_result",
    "extract_tm_search_criteria_from_message",
]
