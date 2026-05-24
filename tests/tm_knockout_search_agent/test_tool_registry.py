"""Tool registry tests for TM knockout search."""

from __future__ import annotations

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


def test_placeholder_tools_do_not_claim_live_api_execution() -> None:
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
    web_output = tools_by_name["web_common_law_search"].invoke(
        {
            "brand_name": "Acme Atlas",
            "jurisdictions": ["US"],
            "goods_services": "Retail services",
            "max_results": 5,
        }
    )

    assert "not configured" in compumark_output
    assert "No live trademark registry search was run" in compumark_output
    assert "not configured" in web_output
    assert "No live web search was run" in web_output
