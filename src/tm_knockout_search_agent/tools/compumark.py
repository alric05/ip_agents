"""CompuMark tool placeholders for TM knockout search.

Live CompuMark API wiring is intentionally not implemented in v1.
"""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool


@tool(parse_docstring=True)
def compumark_trademark_search(
    brand_name: Annotated[str, "Trademark or brand text to search"],
    jurisdictions: Annotated[
        list[str],
        "Jurisdiction codes or regional systems such as US, CA, EUIPO",
    ],
    classes: Annotated[list[str], "Nice classes to search"] | None = None,
    goods_services: Annotated[
        str | None,
        "Goods/services text used for search context",
    ] = None,
    query_intent: Annotated[
        str,
        "Planning intent, such as exact, similar, or inactive_contextual",
    ] = "exact",
    max_results: Annotated[int, "Maximum result count requested by the plan"] = 25,
) -> str:
    """Placeholder CompuMark trademark registry search.

    Args:
        brand_name: Trademark or brand text to search.
        jurisdictions: Jurisdiction codes or regional systems such as US or EUIPO.
        classes: Optional Nice classes to constrain the search.
        goods_services: Optional goods/services context.
        query_intent: Deterministic planner intent.
        max_results: Maximum result count requested by the plan.

    Returns:
        A deterministic placeholder message. No live API is called.
    """
    return (
        "CompuMark API integration is not configured in this repository yet. "
        "No live trademark registry search was run. "
        f"Planned request: brand={brand_name!r}, jurisdictions={jurisdictions!r}, "
        f"classes={classes or []!r}, intent={query_intent!r}, "
        f"goods_services={goods_services!r}, max_results={max_results}."
    )


__all__ = ["compumark_trademark_search"]
