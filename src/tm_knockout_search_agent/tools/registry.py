"""Trademark-specific tool registry for TM knockout search."""

from __future__ import annotations

from langchain_core.tools import BaseTool

from src.tm_knockout_search_agent.tools.compumark import compumark_trademark_search
from src.tm_knockout_search_agent.tools.web_search import web_common_law_search


TM_KNOCKOUT_SEARCH_TOOLS: list[BaseTool] = [
    compumark_trademark_search,
    web_common_law_search,
]


def get_tm_knockout_search_tools() -> list[BaseTool]:
    """Return v1 tools relevant to trademark knockout searching only."""
    return TM_KNOCKOUT_SEARCH_TOOLS.copy()


def get_tm_knockout_search_tool_names() -> list[str]:
    """Return registered v1 trademark tool names."""
    return [tool.name for tool in get_tm_knockout_search_tools()]


__all__ = [
    "TM_KNOCKOUT_SEARCH_TOOLS",
    "get_tm_knockout_search_tool_names",
    "get_tm_knockout_search_tools",
]
