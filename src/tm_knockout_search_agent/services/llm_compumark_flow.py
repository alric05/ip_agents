"""LLM-directed CompuMark workflow for conversational TM knockout search.

This module keeps transport deterministic, but lets LLM nodes own the search
question, CompuMark payload drafting, payload correction after API errors, and
candidate analysis.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import re
from typing import Any, Literal

from pydantic import Field, field_validator

from src.tm_knockout_search_agent import prompts
from src.tm_knockout_search_agent.services.compumark_client import (
    CompuMarkAPIError,
    CompuMarkClient,
)
from src.tm_knockout_search_agent.services.conversation import (
    ConversationalIntakeResult,
    extract_tm_search_criteria_from_message,
)
from src.tm_knockout_search_agent.services.session import (
    create_session,
    session_dir_for,
    write_artifact,
    write_final_report,
)
from src.tm_knockout_search_agent.state import ArtifactModel
from src.tm_knockout_search_agent.tools.adapters import (
    flag_duplicate_candidates,
    normalize_compumark_trademark_record,
)


RiskLabel = Literal["LOW", "MEDIUM", "HIGH", "SEARCH_FAILED"]


class CompuMarkQuestionDraft(ArtifactModel):
    """LLM-authored natural-language search question."""

    search_level: str
    question: str = Field(..., min_length=1)
    is_valid: bool
    validation_notes: str | None = None
    assumptions: list[str] = Field(default_factory=list)


class CompuMarkPayloadDraft(ArtifactModel):
    """LLM-authored CompuMark payload draft."""

    search_level: str
    payload: dict[str, Any] = Field(default_factory=dict)
    is_valid: bool
    rationale: str | None = None
    warnings: list[str] = Field(default_factory=list)

    @field_validator("payload", mode="after")
    @classmethod
    def _payload_must_be_object(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("payload must be a JSON object")
        return value


class CompuMarkExecutionAttempt(ArtifactModel):
    """One payload execution attempt."""

    search_level: str
    attempt_number: int
    payload: dict[str, Any]
    succeeded: bool
    error: str | None = None
    count_response: dict[str, Any] | None = None
    search_response: dict[str, Any] | None = None
    selected_ids: list[str] = Field(default_factory=list)
    raw_trademark_count: int = 0


class CompuMarkContentAnalysis(ArtifactModel):
    """LLM analysis over CompuMark content records."""

    final_response: str = Field(..., min_length=1)
    overall_risk_label: RiskLabel
    most_problematic_candidates: list[dict[str, Any]] = Field(default_factory=list)
    conclusions: str | None = None
    caveats: list[str] = Field(default_factory=list)


def draft_compumark_search_question(
    intake: ConversationalIntakeResult,
    *,
    search_level: str,
    llm: Any | None = None,
) -> CompuMarkQuestionDraft:
    """Ask an LLM to turn validated criteria into a search question."""
    active_llm = llm or _default_llm()
    response = active_llm.invoke(
        [
            _system_message(QUESTION_SYSTEM_PROMPT),
            _human_message(
                "Create one CompuMark search question and validate it.\n\n"
                f"Search level: {search_level}\n"
                f"Criteria JSON:\n{json.dumps(intake.model_dump(mode='json'), indent=2)}"
            ),
        ]
    )
    return CompuMarkQuestionDraft.model_validate(
        _loads_json_object(_message_content_to_text(response.content))
    )


def draft_compumark_payload(
    *,
    intake: ConversationalIntakeResult,
    question: CompuMarkQuestionDraft,
    previous_error: str | None = None,
    previous_payload: Mapping[str, Any] | None = None,
    llm: Any | None = None,
) -> CompuMarkPayloadDraft:
    """Ask an LLM client node to write or correct a CompuMark payload."""
    active_llm = llm or _default_llm()
    correction_context = ""
    if previous_error:
        correction_context = (
            "\nThe previous API call failed. Correct the payload and return a "
            "new payload only.\n"
            f"Previous payload:\n{json.dumps(dict(previous_payload or {}), indent=2)}\n"
            f"API error:\n{previous_error}\n"
        )
    response = active_llm.invoke(
        [
            _system_message(COMPUMARK_PAYLOAD_SYSTEM_PROMPT),
            _human_message(
                "Write a CompuMark /count and /search payload for this question.\n"
                f"{correction_context}\n"
                f"Question JSON:\n{json.dumps(question.model_dump(mode='json'), indent=2)}\n"
                f"Validated criteria JSON:\n{json.dumps(intake.model_dump(mode='json'), indent=2)}"
            ),
        ]
    )
    draft = CompuMarkPayloadDraft.model_validate(
        _loads_json_object(_message_content_to_text(response.content))
    )
    _validate_compumark_payload(draft.payload)
    return draft


def analyze_compumark_content(
    *,
    intake: ConversationalIntakeResult,
    questions: Sequence[CompuMarkQuestionDraft],
    attempts: Sequence[CompuMarkExecutionAttempt],
    raw_trademarks: Sequence[Mapping[str, Any]],
    candidates: Sequence[Any],
    llm: Any | None = None,
) -> CompuMarkContentAnalysis:
    """Ask an LLM to analyze returned CompuMark content records."""
    active_llm = llm or _default_llm()
    response = active_llm.invoke(
        [
            _system_message(CONTENT_ANALYSIS_SYSTEM_PROMPT),
            _human_message(
                "Analyze the CompuMark content and return JSON only.\n\n"
                f"{json.dumps(_analysis_input(intake, questions, attempts, raw_trademarks, candidates), indent=2, sort_keys=True)}"
            ),
        ]
    )
    return CompuMarkContentAnalysis.model_validate(
        _loads_json_object(_message_content_to_text(response.content))
    )


def run_llm_compumark_knockout_flow(
    *,
    message: str,
    session_id: str | None = None,
    thread_id: str | None = None,
    sessions_base_dir: str = "sessions",
    search_levels: Sequence[str] | None = None,
    max_content_ids: int = 50,
    max_payload_retries: int = 1,
    llm: Any | None = None,
    client: CompuMarkClient | None = None,
) -> dict[str, Any]:
    """Run the requested LLM-directed CompuMark flow end to end."""
    active_llm = llm or _default_llm()
    intake = extract_tm_search_criteria_from_message(message, llm=active_llm)
    if not intake.ready_for_search:
        return {
            "agent_name": "tm_knockout_search_agent",
            "status": "NEEDS_INPUT",
            "message": intake.clarification_question,
            "conversation_intake": intake.model_dump(mode="json"),
            "missing_fields": intake.missing_fields,
            "live_llm_call": True,
            "live_api_calls": False,
        }

    manifest = create_session(session_id=session_id or thread_id, base_dir=sessions_base_dir)
    resolved_session_id = manifest.session_id
    levels = list(search_levels or ["EXACT_ACTIVE", "SIMILAR_ACTIVE"])
    max_ids = max(1, min(int(max_content_ids), 50))
    active_client = client or CompuMarkClient()

    questions: list[CompuMarkQuestionDraft] = []
    payload_drafts: list[dict[str, Any]] = []
    attempts: list[CompuMarkExecutionAttempt] = []
    raw_trademarks: list[Mapping[str, Any]] = []
    source_errors: list[dict[str, Any]] = []

    for level in levels:
        question = draft_compumark_search_question(
            intake,
            search_level=level,
            llm=active_llm,
        )
        questions.append(question)
        if not question.is_valid:
            source_errors.append(
                {
                    "search_level": level,
                    "error_type": "invalid_question",
                    "error_message": question.validation_notes or "Question was invalid.",
                }
            )
            continue

        previous_error: str | None = None
        previous_payload: Mapping[str, Any] | None = None
        for attempt_number in range(1, max_payload_retries + 2):
            try:
                payload_draft = draft_compumark_payload(
                    intake=intake,
                    question=question,
                    previous_error=previous_error,
                    previous_payload=previous_payload,
                    llm=active_llm,
                )
                payload_drafts.append(payload_draft.model_dump(mode="json"))
                if not payload_draft.is_valid:
                    raise ValueError(payload_draft.rationale or "Payload was invalid.")

                selected_so_far = sum(
                    len(attempt.selected_ids)
                    for attempt in attempts
                    if attempt.succeeded
                )
                execution, level_trademarks = _execute_compumark_payload(
                    active_client,
                    payload_draft.payload,
                    search_level=level,
                    attempt_number=attempt_number,
                    max_ids=max(0, max_ids - selected_so_far),
                )
                attempts.append(execution)
                raw_trademarks.extend(level_trademarks)
                break
            except (CompuMarkAPIError, ValueError) as exc:
                previous_error = str(exc)
                previous_payload = previous_payload or (
                    payload_drafts[-1]["payload"] if payload_drafts else {}
                )
                attempts.append(
                    CompuMarkExecutionAttempt(
                        search_level=level,
                        attempt_number=attempt_number,
                        payload=dict(previous_payload or {}),
                        succeeded=False,
                        error=previous_error,
                    )
                )
                if attempt_number > max_payload_retries:
                    source_errors.append(
                        {
                            "search_level": level,
                            "error_type": "api",
                            "error_message": previous_error,
                        }
                    )

    candidates = flag_duplicate_candidates(
        [
            normalize_compumark_trademark_record(raw)
            for raw in raw_trademarks
            if isinstance(raw, Mapping)
        ]
    )
    analysis = analyze_compumark_content(
        intake=intake,
        questions=questions,
        attempts=attempts,
        raw_trademarks=raw_trademarks,
        candidates=candidates,
        llm=active_llm,
    )

    status = "COMPLETED" if not source_errors else "SEARCH_FAILED"
    result = {
        "agent_name": "tm_knockout_search_agent",
        "status": status,
        "input_message": message,
        "session_id": resolved_session_id,
        "session_path": str(session_dir_for(resolved_session_id, base_dir=sessions_base_dir)),
        "thread_id": thread_id,
        "conversation_intake": intake.model_dump(mode="json"),
        "llm_search_questions": [
            question.model_dump(mode="json") for question in questions
        ],
        "llm_payload_drafts": payload_drafts,
        "compumark_attempts": [
            attempt.model_dump(mode="json", exclude_none=True) for attempt in attempts
        ],
        "compumark_raw_trademarks": [dict(raw) for raw in raw_trademarks],
        "normalized_candidates": [
            candidate.model_dump(mode="json", exclude_none=True)
            for candidate in candidates
        ],
        "source_errors": source_errors,
        "risk_assessment": {
            "overall_risk_label": (
                "SEARCH_FAILED" if source_errors else analysis.overall_risk_label
            ),
            "findings": analysis.most_problematic_candidates,
            "missing_or_failed_source_notes": [
                item["error_message"] for item in source_errors
            ],
            "explanation": analysis.conclusions,
        },
        "llm_analysis": analysis.model_dump(mode="json"),
        "report_markdown": analysis.final_response,
        "llm_response": analysis.final_response,
        "live_llm_call": True,
        "live_llm_call_attempted": True,
        "live_api_calls": bool(attempts),
    }

    _write_flow_artifacts(result, sessions_base_dir=sessions_base_dir)
    return result


def _execute_compumark_payload(
    client: CompuMarkClient,
    payload: Mapping[str, Any],
    *,
    search_level: str,
    attempt_number: int,
    max_ids: int,
) -> tuple[CompuMarkExecutionAttempt, list[Mapping[str, Any]]]:
    count_response = client.count(payload)
    search_response = client.search(payload)
    selected_ids = _flatten_ids(search_response.get("ids"))[:max_ids]
    text_response = client.retrieve_text(selected_ids) if selected_ids else {"trademarks": []}
    raw_trademarks = [
        item
        for item in text_response.get("trademarks", [])
        if isinstance(item, Mapping)
    ]
    return (
        CompuMarkExecutionAttempt(
            search_level=search_level,
            attempt_number=attempt_number,
            payload=dict(payload),
            succeeded=True,
            count_response=dict(count_response),
            search_response=dict(search_response),
            selected_ids=selected_ids,
            raw_trademark_count=len(raw_trademarks),
        ),
        raw_trademarks,
    )


def _write_flow_artifacts(result: Mapping[str, Any], *, sessions_base_dir: str) -> None:
    session_id = str(result["session_id"])
    write_artifact(
        session_id,
        "request",
        {
            "raw_user_input": result.get("input_message"),
            "thread_id": result.get("thread_id"),
        },
        base_dir=sessions_base_dir,
    )
    write_artifact(
        session_id,
        "search_criteria",
        result.get("conversation_intake", {}),
        base_dir=sessions_base_dir,
    )
    write_artifact(
        session_id,
        "query_plan",
        {
            "mode": "llm_directed_compumark",
            "questions": result.get("llm_search_questions", []),
            "payload_drafts": result.get("llm_payload_drafts", []),
        },
        base_dir=sessions_base_dir,
    )
    write_artifact(
        session_id,
        "compumark_results",
        {
            "attempts": result.get("compumark_attempts", []),
            "raw_trademarks": result.get("compumark_raw_trademarks", []),
            "source_errors": result.get("source_errors", []),
        },
        base_dir=sessions_base_dir,
    )
    write_artifact(
        session_id,
        "normalized_candidates",
        result.get("normalized_candidates", []),
        base_dir=sessions_base_dir,
    )
    write_artifact(
        session_id,
        "risk_assessment",
        result.get("risk_assessment", {}),
        base_dir=sessions_base_dir,
    )
    write_artifact(
        session_id,
        "llm_review",
        {
            "mode": "llm_directed_compumark",
            "analysis": result.get("llm_analysis", {}),
        },
        base_dir=sessions_base_dir,
    )
    write_final_report(
        session_id,
        str(result.get("report_markdown") or ""),
        base_dir=sessions_base_dir,
    )


def _analysis_input(
    intake: ConversationalIntakeResult,
    questions: Sequence[CompuMarkQuestionDraft],
    attempts: Sequence[CompuMarkExecutionAttempt],
    raw_trademarks: Sequence[Mapping[str, Any]],
    candidates: Sequence[Any],
) -> dict[str, Any]:
    return {
        "criteria": intake.model_dump(mode="json"),
        "questions": [question.model_dump(mode="json") for question in questions],
        "attempts": [
            attempt.model_dump(mode="json", exclude_none=True) for attempt in attempts
        ],
        "raw_trademark_count": len(raw_trademarks),
        "candidates": [
            candidate.model_dump(mode="json", exclude_none=True)
            for candidate in candidates
        ][:50],
        "fixed_disclaimer": prompts.FIXED_DISCLAIMER,
    }


def _validate_compumark_payload(payload: Mapping[str, Any]) -> None:
    if not isinstance(payload.get("registrationOfficeCodes"), list):
        raise ValueError("payload.registrationOfficeCodes must be a list")
    if not payload["registrationOfficeCodes"]:
        raise ValueError("payload.registrationOfficeCodes must not be empty")
    if not isinstance(payload.get("searchFields"), list):
        raise ValueError("payload.searchFields must be a list")
    if not payload["searchFields"]:
        raise ValueError("payload.searchFields must not be empty")
    if not isinstance(payload.get("queryOptions"), Mapping):
        raise ValueError("payload.queryOptions must be an object")
    for field in payload["searchFields"]:
        if not isinstance(field, Mapping):
            raise ValueError("each searchFields item must be an object")
        if field.get("name") not in _ALLOWED_SEARCH_FIELDS:
            raise ValueError(f"unsupported CompuMark search field: {field.get('name')}")
        if field.get("operator") not in _ALLOWED_OPERATORS:
            raise ValueError(f"unsupported CompuMark search operator: {field.get('operator')}")
        if str(field.get("value") or "").strip() == "":
            raise ValueError("search field values must not be empty")


def _flatten_ids(ids_by_office: Any) -> list[str]:
    if not isinstance(ids_by_office, Mapping):
        return []
    ids: list[str] = []
    seen: set[str] = set()
    for values in ids_by_office.values():
        if isinstance(values, str) or not isinstance(values, Sequence):
            continue
        for value in values:
            trademark_id = str(value).strip()
            if trademark_id and trademark_id not in seen:
                ids.append(trademark_id)
                seen.add(trademark_id)
    return ids


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


QUESTION_SYSTEM_PROMPT = """You are the search-question node for tm_knockout_search_agent.

Turn validated trademark criteria into one clear natural-language question for
CompuMark search. Return JSON only:
- search_level: the provided search level
- question: the natural-language question
- is_valid: boolean
- validation_notes: string or null
- assumptions: list of strings

Validity rules:
- The question must include one mark, at least one country/registration office
  code or regional system, and at least one Nice class.
- Use the provided search level, such as EXACT_ACTIVE or SIMILAR_ACTIVE.
- Do not invent missing criteria.
"""


COMPUMARK_PAYLOAD_SYSTEM_PROMPT = """You are the CompuMark client node for tm_knockout_search_agent.

Your job is to write one JSON payload that can be used for both CompuMark
POST /count and POST /search. Return JSON only:
- search_level: string
- payload: object
- is_valid: boolean
- rationale: string or null
- warnings: list of strings

Allowed payload shape:
{
  "registrationOfficeCodes": ["US", "FR", "EM"],
  "limitWOresultsToDesignated": false,
  "searchFields": [
    {"name": "EXACT_WORD_MARK_SPECIFICATION", "operator": "EQUALS", "value": "MARK"},
    {"name": "INT_CLASS_NUMBER", "operator": "EQUALS", "value": "3"}
  ],
  "queryOptions": {
    "activeOnly": true,
    "phonetics": false,
    "plurals": false,
    "crossReferences": false,
    "japanesePhonetics": false,
    "centralEuropeanPhonetics": false
  }
}

Search level guidance:
- EXACT_ACTIVE: activeOnly true; use EXACT_WORD_MARK_SPECIFICATION/EQUALS for
  the mark; include INT_CLASS_NUMBER/EQUALS for each requested class.
- SIMILAR_ACTIVE: activeOnly true; use WORD_MARK_SPECIFICATION/CONTAINS or
  PHONETIC_WORD_MARK_SPECIFICATION/CONTAINS for the mark; include class fields;
  phonetics/plurals/crossReferences may be true when useful.
- Use your own knowledge for registration office codes. Examples: France is FR,
  United States is US, EUIPO is EM. If uncertain, mark is_valid false.
- Do not include unsupported endpoints, API keys, URLs, or natural-language
  explanations inside the payload.
"""


CONTENT_ANALYSIS_SYSTEM_PROMPT = f"""You are the CompuMark content analysis node for tm_knockout_search_agent.

Analyze the returned CompuMark content records for first-pass trademark
knockout screening. Return JSON only:
- final_response: concise markdown report
- overall_risk_label: LOW, MEDIUM, HIGH, or SEARCH_FAILED
- most_problematic_candidates: list of candidate summaries with ids/reasons
- conclusions: short machine-readable summary
- caveats: list of strings

Focus on mark similarity, active status, jurisdiction overlap, Nice class
overlap, goods/services relatedness, owner signals, and source failures. Do not
claim live web search was performed. Include this disclaimer in the report:
{prompts.FIXED_DISCLAIMER}
"""


_ALLOWED_SEARCH_FIELDS = {
    "WORD_MARK_SPECIFICATION",
    "EXACT_WORD_MARK_SPECIFICATION",
    "APPLICATION_NUMBER",
    "APPLICATION_DATE",
    "REGISTRATION_NUMBER",
    "REGISTRATION_DATE",
    "INT_CLASS_NUMBER",
    "INT_GOODS_SERVICES_DESCRIPTION",
    "APPLICANT_NAME",
    "EXACT_APPLICANT_NAME",
    "REPRESENTATIVE_OR_CORRESPONDENT_NAME",
    "PHONETIC_WORD_MARK_SPECIFICATION",
    "DESIGNER_NAME",
}
_ALLOWED_OPERATORS = {
    "GREATER_THAN_EQUALS",
    "CONTAINS",
    "GREATER_THAN",
    "ENDS_WITH",
    "LESS_THAN_EQUALS",
    "BEGINS_WITH",
    "LESS_THAN",
    "EQUALS",
}


__all__ = [
    "CompuMarkContentAnalysis",
    "CompuMarkExecutionAttempt",
    "CompuMarkPayloadDraft",
    "CompuMarkQuestionDraft",
    "analyze_compumark_content",
    "draft_compumark_payload",
    "draft_compumark_search_question",
    "run_llm_compumark_knockout_flow",
]
