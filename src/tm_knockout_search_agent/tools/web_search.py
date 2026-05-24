"""Web/common-law search tool placeholders for TM knockout search."""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool


@tool(parse_docstring=True)
def web_common_law_search(
    brand_name: Annotated[str, "Trademark or brand text to search on the web"],
    jurisdictions: Annotated[
        list[str],
        "Jurisdiction hints or regional systems for common-law context",
    ],
    goods_services: Annotated[
        str | None,
        "Goods/services or business context for commercial-use signals",
    ] = None,
    max_results: Annotated[int, "Maximum result count requested by the plan"] = 10,
) -> str:
    """Placeholder web/common-law trademark search.

    Args:
        brand_name: Trademark or brand text to search on the web.
        jurisdictions: Jurisdiction hints or regional systems.
        goods_services: Optional goods/services or business context.
        max_results: Maximum result count requested by the plan.

    Returns:
        A deterministic placeholder message. No live web search is called.
    """
    return (
        "Web/common-law search integration is not configured in this repository yet. "
        "No live web search was run. "
        f"Planned request: brand={brand_name!r}, jurisdictions={jurisdictions!r}, "
        f"goods_services={goods_services!r}, max_results={max_results}."
    )


__all__ = ["web_common_law_search"]
