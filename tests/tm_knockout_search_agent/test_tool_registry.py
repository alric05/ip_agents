"""Tool registry tests for TM knockout search."""

from __future__ import annotations

import json

import pytest

import src.tm_knockout_search_agent.tools.compumark as compumark_module
from src.tm_knockout_search_agent.services.compumark_client import CompuMarkConfigError
from src.tm_knockout_search_agent.tools.registry import (
    get_tm_knockout_search_tool_names,
    get_tm_knockout_search_tools,
)


def test_registry_exposes_only_trademark_relevant_tools() -> None:
    tools = get_tm_knockout_search_tools()
    names = [tool.name for tool in tools]

    assert names == [
        "compumark_trademark_search",
        "web_common_law_search",
    ]
    assert get_tm_knockout_search_tool_names() == names


def test_registry_does_not_expose_patent_or_novelty_tools() -> None:
    forbidden_tool_names = {
        "semantic_patent_search",
        "patent_keyword_search",
        "get_patent_citations",
        "npl_search",
        "evaluate_coverage",
        "triage_reference",
        "generate_search_strategy",
        "build_feature_matrix",
    }

    assert forbidden_tool_names.isdisjoint(set(get_tm_knockout_search_tool_names()))


def test_compumark_tool_returns_structured_result_without_live_call_when_mocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeExecutionResult:
        def to_dict(self) -> dict[str, object]:
            return {
                "source": "compumark",
                "succeeded": True,
                "live_api_calls": True,
                "requests": [],
                "counts": {"US": 1},
                "ids_by_office": {"US": ["cm-1"]},
                "selected_ids": ["cm-1"],
                "candidates": [{"id": "cm-1", "source": "compumark", "mark_name": "Acme Atlas"}],
                "raw_trademark_count": 1,
                "truncated": False,
            }

    captured: dict[str, object] = {}

    def fake_execute_compumark_search(**kwargs: object) -> FakeExecutionResult:
        captured.update(kwargs)
        return FakeExecutionResult()

    monkeypatch.setattr(
        compumark_module,
        "execute_compumark_search",
        fake_execute_compumark_search,
    )
    tools_by_name = {tool.name: tool for tool in get_tm_knockout_search_tools()}

    compumark_output = tools_by_name["compumark_trademark_search"].invoke(
        {
            "brand_name": "Acme Atlas",
            "jurisdictions": ["US"],
            "classes": ["35"],
            "goods_services": "Retail services",
            "query_intent": "exact",
            "max_results": 5,
        }
    )

    payload = json.loads(compumark_output)

    assert captured["brand_name"] == "Acme Atlas"
    assert captured["jurisdictions"] == ["US"]
    assert captured["classes"] == ["35"]
    assert captured["query_intent"] == "exact"
    assert payload["succeeded"] is True
    assert payload["candidates"][0]["id"] == "cm-1"
    assert payload["goods_services_context"] == "Retail services"


def test_compumark_tool_reports_missing_configuration_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_execute_compumark_search(**kwargs: object) -> object:
        raise CompuMarkConfigError("Set COMPUMARK_API_KEY to enable CompuMark search.")

    monkeypatch.setattr(
        compumark_module,
        "execute_compumark_search",
        fake_execute_compumark_search,
    )
    tools_by_name = {tool.name: tool for tool in get_tm_knockout_search_tools()}

    output = tools_by_name["compumark_trademark_search"].invoke(
        {
            "brand_name": "Acme Atlas",
            "jurisdictions": ["US"],
            "classes": ["35"],
            "goods_services": "Retail services",
            "query_intent": "exact",
            "max_results": 5,
        }
    )

    payload = json.loads(output)

    assert payload["succeeded"] is False
    assert payload["live_api_calls"] is False
    assert payload["error_type"] == "configuration"
    assert "COMPUMARK_API_KEY" in payload["error_message"]


def test_web_placeholder_does_not_claim_live_api_execution() -> None:
    tools_by_name = {tool.name: tool for tool in get_tm_knockout_search_tools()}

    web_output = tools_by_name["web_common_law_search"].invoke(
        {
            "brand_name": "Acme Atlas",
            "jurisdictions": ["US"],
            "goods_services": "Retail services",
            "max_results": 5,
        }
    )

    assert "not configured" in web_output
    assert "No live web search was run" in web_output
