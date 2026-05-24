"""Trademark-specific tools for the TM knockout search agent."""

from src.tm_knockout_search_agent.tools.adapters import (
    build_duplicate_key,
    flag_duplicate_candidates,
    normalize_compumark_result,
    normalize_compumark_trademark_record,
    normalize_web_common_law_result,
)
from src.tm_knockout_search_agent.tools.compumark import compumark_trademark_search
from src.tm_knockout_search_agent.tools.registry import (
    get_tm_knockout_search_tool_names,
    get_tm_knockout_search_tools,
)
from src.tm_knockout_search_agent.tools.web_search import web_common_law_search

__all__ = [
    "build_duplicate_key",
    "compumark_trademark_search",
    "flag_duplicate_candidates",
    "get_tm_knockout_search_tool_names",
    "get_tm_knockout_search_tools",
    "normalize_compumark_result",
    "normalize_compumark_trademark_record",
    "normalize_web_common_law_result",
    "web_common_law_search",
]
