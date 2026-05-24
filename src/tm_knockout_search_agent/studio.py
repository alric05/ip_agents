"""LangGraph Studio entry point for the TM knockout search agent.

This module exposes a minimal compiled graph for Studio registration. The v1
graph is intentionally deterministic: it wraps the local factory/services and
does not call live trademark or web APIs.
"""

from typing import Any, TypedDict

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.tm_knockout_search_agent.deep_agent import (
    TM_KNOCKOUT_AGENT_NAME,
    check_tm_knockout,
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
    max_candidates_to_normalize: int
    max_candidates_to_surface_in_report: int
    include_web_search: bool
    include_inactive_contextual: bool
    language: str
    result: dict[str, Any]
    messages: list[Any]


def _config_thread_id(config: RunnableConfig | None) -> str | None:
    configurable = (config or {}).get("configurable", {})
    thread_id = configurable.get("thread_id")
    return str(thread_id) if thread_id else None


def _result_message(result: dict[str, Any]) -> AIMessage:
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


def _missing_input_result(error: Exception) -> dict[str, Any]:
    return {
        "agent_name": TM_KNOCKOUT_AGENT_NAME,
        "status": "NEEDS_INPUT",
        "message": (
            "Please provide one proposed brand, countries or regional systems, "
            "and Nice classes and/or goods/services."
        ),
        "error": str(error),
        "required_fields": [
            "brand",
            "countries or jurisdictions",
            "classes and/or goods",
        ],
        "live_api_calls": False,
    }


def _run_tm_knockout_screen(
    state: TMKnockoutGraphState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    thread_id = state.get("thread_id") or _config_thread_id(config)

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
            language=state.get("language", "English"),
            sessions_base_dir=state.get("sessions_base_dir", "sessions"),
        )
    except ValueError as exc:
        result = _missing_input_result(exc)

    messages = [*state.get("messages", []), _result_message(result)]
    return {"result": result, "messages": messages}


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
