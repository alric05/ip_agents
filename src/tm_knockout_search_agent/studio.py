"""LangGraph Studio entry point for the TM knockout search agent.

This module exposes the Studio-registered graph. It supports structured
deterministic input and a conversational path: LLM intake, deterministic source
execution, then LLM-authored analysis grounded in artifacts.
"""

import json
from typing import Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.tm_knockout_search_agent.deep_agent import (
    TM_KNOCKOUT_AGENT_NAME,
    check_tm_knockout,
)
from src.tm_knockout_search_agent.services.conversation import (
    analyze_tm_knockout_result,
    extract_tm_search_criteria_from_message,
)
from src.tm_knockout_search_agent.services.llm_compumark_flow import (
    run_llm_compumark_knockout_flow,
)
from src.tm_knockout_search_agent.services.session import (
    write_artifact,
    write_final_report,
)


class TMKnockoutGraphState(TypedDict, total=False):
    """Studio-friendly state for structured TM knockout invocations."""

    brand: str
    brand_name: str
    countries: str | list[str]
    jurisdictions: str | list[str]
    classes: str | list[str]
    nice_classes: str | list[str]
    goods: str
    goods_services: str
    input_message: str
    conversational: bool
    business_context: str
    assumptions: list[str]
    candidates: list[dict[str, Any]]
    source_statuses: list[dict[str, Any]]
    completed_query_group_ids: list[str]
    completed_stages: list[str]
    model: str
    thread_id: str
    session_id: str
    sessions_base_dir: str
    max_results_per_query: int
    max_content_ids: int
    max_candidates_to_normalize: int
    max_candidates_to_surface_in_report: int
    include_web_search: bool
    include_inactive_contextual: bool
    live_compumark: bool
    use_llm: bool
    language: str
    result: dict[str, Any]
    messages: list[Any]


def _config_thread_id(config: RunnableConfig | None) -> str | None:
    configurable = (config or {}).get("configurable", {})
    thread_id = configurable.get("thread_id")
    return str(thread_id) if thread_id else None


def _result_message(result: dict[str, Any]) -> AIMessage:
    if result.get("llm_response"):
        return AIMessage(content=str(result["llm_response"]))

    if result.get("status") == "NEEDS_INPUT":
        return AIMessage(content=str(result["message"]))

    risk_label = result.get("risk_assessment", {}).get("overall_risk_label", "UNKNOWN")
    stopping = result.get("stopping_decision", {}).get("decision", "UNKNOWN")
    report_markdown = result.get("report_markdown")
    if report_markdown:
        return AIMessage(content=report_markdown)

    return AIMessage(
        content=(
            "TM knockout screening prepared. "
            f"Overall risk: {risk_label}. Stopping decision: {stopping}."
        )
    )


def _missing_input_result(
    error: Exception | str,
    *,
    missing_fields: list[str] | None = None,
) -> dict[str, Any]:
    required_fields = [
        "brand",
        "countries or jurisdictions",
        "classes and/or goods",
    ]
    return {
        "agent_name": TM_KNOCKOUT_AGENT_NAME,
        "status": "NEEDS_INPUT",
        "message": (
            "Please provide one proposed brand, countries or regional systems, "
            "and Nice classes and/or goods/services."
        ),
        "error": str(error),
        "required_fields": required_fields,
        "missing_fields": missing_fields or required_fields,
        "live_api_calls": False,
    }


def _preflight_missing_input_result(
    state: TMKnockoutGraphState,
) -> dict[str, Any] | None:
    missing_fields: list[str] = []
    if not (state.get("brand") or state.get("brand_name")):
        missing_fields.append("brand")
    if not (state.get("countries") or state.get("jurisdictions")):
        missing_fields.append("countries or jurisdictions")
    if not (
        state.get("classes")
        or state.get("nice_classes")
        or state.get("goods")
        or state.get("goods_services")
    ):
        missing_fields.append("classes and/or goods")

    if not missing_fields:
        return None
    return _missing_input_result(
        "missing required TM knockout search criteria",
        missing_fields=missing_fields,
    )


def _run_tm_knockout_screen(
    state: TMKnockoutGraphState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    thread_id = state.get("thread_id") or _config_thread_id(config)
    conversation_message = _conversation_message_from_state(state)
    if conversation_message and (
        state.get("conversational") or not _has_structured_criteria(state)
    ):
        result = _run_conversational_tm_knockout(
            state,
            conversation_message=conversation_message,
            thread_id=thread_id,
        )
        messages = [*state.get("messages", []), _result_message(result)]
        return {"result": result, "messages": messages}

    result = _preflight_missing_input_result(state)

    if result is None:
        try:
            result = check_tm_knockout(
                brand=state.get("brand") or state.get("brand_name"),
                countries=state.get("countries") or state.get("jurisdictions"),
                classes=state.get("classes") or state.get("nice_classes"),
                goods=state.get("goods") or state.get("goods_services"),
                business_context=state.get("business_context"),
                assumptions=state.get("assumptions"),
                candidates=state.get("candidates"),
                source_statuses=state.get("source_statuses"),
                completed_query_group_ids=state.get("completed_query_group_ids"),
                completed_stages=state.get("completed_stages"),
                model=state.get("model"),
                thread_id=thread_id,
                session_id=state.get("session_id") or thread_id,
                max_results_per_query=state.get("max_results_per_query", 25),
                max_candidates_to_normalize=state.get("max_candidates_to_normalize", 100),
                max_candidates_to_surface_in_report=state.get(
                    "max_candidates_to_surface_in_report",
                    10,
                ),
                include_web_search=state.get("include_web_search", True),
                include_inactive_contextual=state.get("include_inactive_contextual", False),
                live_compumark=state.get("live_compumark", False),
                language=state.get("language", "English"),
                sessions_base_dir=state.get("sessions_base_dir", "sessions"),
            )
        except ValueError as exc:
            result = _missing_input_result(exc)

    if state.get("use_llm") and result.get("status") != "NEEDS_INPUT":
        result = _attach_llm_review(result, state)

    messages = [*state.get("messages", []), _result_message(result)]
    return {"result": result, "messages": messages}


def _run_conversational_tm_knockout(
    state: TMKnockoutGraphState,
    *,
    conversation_message: str,
    thread_id: str | None,
) -> dict[str, Any]:
    """Run the LLM intake -> LLM payload -> CompuMark -> LLM analysis path."""
    try:
        return run_llm_compumark_knockout_flow(
            message=conversation_message,
            session_id=state.get("session_id") or thread_id,
            thread_id=thread_id,
            sessions_base_dir=state.get("sessions_base_dir", "sessions"),
            max_content_ids=state.get(
                "max_content_ids",
                state.get("max_results_per_query", 50),
            ),
        )
    except Exception as exc:
        return {
            "agent_name": TM_KNOCKOUT_AGENT_NAME,
            "status": "LLM_COMPUMARK_FLOW_FAILED",
            "message": "The conversational CompuMark workflow failed before completion.",
            "error": str(exc),
            "live_llm_call": False,
            "live_llm_call_attempted": True,
            "live_api_calls": False,
        }


def _run_legacy_conversational_tm_knockout(
    state: TMKnockoutGraphState,
    *,
    conversation_message: str,
    thread_id: str | None,
) -> dict[str, Any]:
    """Run the earlier LLM intake -> deterministic source -> LLM analysis path."""
    try:
        intake = extract_tm_search_criteria_from_message(conversation_message)
    except Exception as exc:
        return {
            "agent_name": TM_KNOCKOUT_AGENT_NAME,
            "status": "LLM_INTAKE_FAILED",
            "message": "I could not reliably extract trademark search criteria from that message.",
            "error": str(exc),
            "live_llm_call": False,
            "live_llm_call_attempted": True,
            "live_api_calls": False,
        }

    if not intake.ready_for_search:
        return {
            "agent_name": TM_KNOCKOUT_AGENT_NAME,
            "status": "NEEDS_INPUT",
            "message": intake.clarification_question,
            "conversation_intake": intake.model_dump(mode="json"),
            "missing_fields": intake.missing_fields,
            "live_llm_call": True,
            "live_api_calls": False,
        }

    result = check_tm_knockout(
        brand=intake.brand_name,
        countries=intake.countries,
        classes=intake.classes,
        goods=intake.goods_services,
        business_context=intake.business_context,
        assumptions=intake.assumptions,
        model=state.get("model"),
        thread_id=thread_id,
        session_id=state.get("session_id") or thread_id,
        max_results_per_query=state.get("max_results_per_query", 5),
        max_candidates_to_normalize=state.get("max_candidates_to_normalize", 100),
        max_candidates_to_surface_in_report=state.get(
            "max_candidates_to_surface_in_report",
            10,
        ),
        include_web_search=state.get("include_web_search", True),
        include_inactive_contextual=state.get("include_inactive_contextual", False),
        live_compumark=state.get("live_compumark", True),
        language=intake.language or state.get("language", "English"),
        sessions_base_dir=state.get("sessions_base_dir", "sessions"),
    )
    result = {
        **result,
        "conversation_intake": intake.model_dump(mode="json"),
        "conversational_agent": True,
        "live_llm_call": True,
        "live_llm_call_attempted": True,
    }

    try:
        analysis = analyze_tm_knockout_result(result)
        deterministic_report = result.get("report_markdown")
        result = {
            **result,
            "deterministic_report_markdown": deterministic_report,
            "report_markdown": analysis.final_response,
            "llm_response": analysis.final_response,
            "llm_analysis": analysis.model_dump(mode="json"),
            "live_llm_call": True,
        }
        _write_conversational_artifacts(
            result,
            intake,
            analysis,
            base_dir=state.get("sessions_base_dir", "sessions"),
        )
    except Exception as exc:
        result = {
            **result,
            "llm_error": str(exc),
            "llm_response": None,
            "live_llm_call": False,
            "live_llm_call_attempted": True,
        }
    return result


def _write_conversational_artifacts(
    result: dict[str, Any],
    intake: Any,
    analysis: Any,
    *,
    base_dir: str,
) -> None:
    session_id = result.get("session_id")
    if not session_id:
        return
    write_artifact(
        str(session_id),
        "llm_review",
        {
            "mode": "conversational",
            "intake": intake.model_dump(mode="json"),
            "analysis": analysis.model_dump(mode="json"),
            "live_llm_call": True,
        },
        base_dir=base_dir,
    )
    write_final_report(str(session_id), analysis.final_response, base_dir=base_dir)


def _has_structured_criteria(state: TMKnockoutGraphState) -> bool:
    return bool(
        (state.get("brand") or state.get("brand_name"))
        and (state.get("countries") or state.get("jurisdictions"))
        and (
            state.get("classes")
            or state.get("nice_classes")
            or state.get("goods")
            or state.get("goods_services")
        )
    )


def _conversation_message_from_state(state: TMKnockoutGraphState) -> str | None:
    if state.get("input_message"):
        return str(state["input_message"]).strip() or None

    for message in reversed(state.get("messages", [])):
        role = _message_role(message)
        if role not in {"human", "user"}:
            continue
        content = _message_content(message)
        if content:
            return content
    return None


def _message_role(message: Any) -> str | None:
    if isinstance(message, dict):
        value = message.get("role") or message.get("type")
        return str(value).lower() if value else None
    value = getattr(message, "type", None) or getattr(message, "role", None)
    return str(value).lower() if value else None


def _message_content(message: Any) -> str | None:
    if isinstance(message, dict):
        content = message.get("content")
    else:
        content = getattr(message, "content", None)
    text = _message_content_to_text(content).strip() if content is not None else ""
    return text or None


def _attach_llm_review(
    result: dict[str, Any],
    state: TMKnockoutGraphState,
) -> dict[str, Any]:
    """Attach one real LLM review for smoke testing when explicitly requested."""
    from src.config.llm import get_active_backend_info, get_llm
    from src.tm_knockout_search_agent.services.session import write_artifact

    review_payload = _llm_review_payload(result)
    try:
        llm = get_llm()
        response = llm.invoke(
            [
                SystemMessage(content=_LLM_SMOKE_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        "Review these deterministic TM knockout artifacts and "
                        "produce a concise user-facing response.\n\n"
                        f"{json.dumps(review_payload, indent=2, sort_keys=True)}"
                    )
                ),
            ]
        )
        content = _message_content_to_text(response.content)
        backend_info = get_active_backend_info()
        llm_review = {
            "live_llm_call": True,
            "model": backend_info.get("model"),
            "provider": backend_info.get("provider"),
            "response": content,
        }
        result = {
            **result,
            "llm_response": content,
            "llm_backend": {
                "provider": backend_info.get("provider"),
                "model": backend_info.get("model"),
                "api_version": backend_info.get("api_version"),
            },
            "live_llm_call": True,
        }
        session_id = result.get("session_id")
        if session_id:
            write_artifact(
                str(session_id),
                "llm_review",
                llm_review,
                base_dir=state.get("sessions_base_dir", "sessions"),
            )
        return result
    except Exception as exc:
        session_id = result.get("session_id")
        if session_id:
            write_artifact(
                str(session_id),
                "llm_review",
                {
                    "live_llm_call": False,
                    "live_llm_call_attempted": True,
                    "error": str(exc),
                },
                base_dir=state.get("sessions_base_dir", "sessions"),
            )
        return {
            **result,
            "llm_response": None,
            "llm_error": str(exc),
            "live_llm_call": False,
            "live_llm_call_attempted": True,
        }


def _llm_review_payload(result: dict[str, Any]) -> dict[str, Any]:
    risk = result.get("risk_assessment", {})
    plan = result.get("search_plan", {})
    return {
        "agent_name": result.get("agent_name"),
        "session_id": result.get("session_id"),
        "criteria": result.get("criteria"),
        "risk_assessment": {
            "overall_risk_label": risk.get("overall_risk_label"),
            "explanation": risk.get("explanation"),
            "country_notes": risk.get("country_notes"),
            "top_findings": risk.get("findings", [])[:3],
            "source_failures": risk.get("missing_or_failed_source_notes", []),
        },
        "search_plan": {
            "source_priority_order": plan.get("source_priority_order"),
            "progressive_stages": plan.get("progressive_stages"),
            "query_groups": [
                {
                    "id": group.get("id"),
                    "stage": group.get("stage"),
                    "source": group.get("source"),
                    "required": group.get("required"),
                }
                for group in plan.get("query_groups", [])
            ],
        },
        "stopping_decision": result.get("stopping_decision"),
        "live_api_calls": result.get("live_api_calls"),
    }


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
        ).strip()
    return str(content)


_LLM_SMOKE_SYSTEM_PROMPT = """You are the tm_knockout_search_agent orchestrator.

Use only the structured artifacts provided by the local deterministic workflow.
Do not claim that live CompuMark, web, or legal research was performed unless
the artifacts explicitly say so. Keep the response concise, practical, and
trademark-focused. Include the overall risk label, any missing source context,
and whether the brand can be shortlisted for deeper review.
"""


def create_tm_knockout_search_graph() -> CompiledStateGraph:
    """Create the minimal LangGraph wrapper used by Studio."""
    workflow = StateGraph(TMKnockoutGraphState)
    workflow.add_node("tm_knockout_screen", _run_tm_knockout_screen)
    workflow.add_edge(START, "tm_knockout_screen")
    workflow.add_edge("tm_knockout_screen", END)
    return workflow.compile()


graph = create_tm_knockout_search_graph()


__all__ = [
    "TMKnockoutGraphState",
    "create_tm_knockout_search_graph",
    "graph",
]
