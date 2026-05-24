"""CompuMark trademark registry search tool for TM knockout search."""

from __future__ import annotations

import json
from typing import Annotated

from langchain_core.tools import tool

from src.tm_knockout_search_agent.services.compumark_client import (
    CompuMarkAPIError,
    CompuMarkConfigError,
    execute_compumark_search,
)


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
    text_test_mode: Annotated[
        bool | None,
        "Optional /text test mode override for obfuscated development responses",
    ] = None,
) -> str:
    """Run a CompuMark trademark registry search.

    Args:
        brand_name: Trademark or brand text to search.
        jurisdictions: Jurisdiction codes or regional systems such as US or EUIPO.
        classes: Optional Nice classes to constrain the search.
        goods_services: Optional goods/services context.
        query_intent: Deterministic planner intent.
        max_results: Maximum result count requested by the plan.
        text_test_mode: Optional /text test mode override.

    Returns:
        JSON with request metadata, source status, ids, and normalized candidates.
    """
    try:
        result = execute_compumark_search(
            brand_name=brand_name,
            jurisdictions=jurisdictions,
            classes=classes or [],
            query_intent=query_intent,
            max_results=max_results,
            text_test_mode=text_test_mode,
        ).to_dict()
        result["goods_services_context"] = goods_services
        return json.dumps(result, indent=2, sort_keys=True)
    except CompuMarkConfigError as exc:
        return _error_payload(
            error_type="configuration",
            message=str(exc),
            brand_name=brand_name,
            jurisdictions=jurisdictions,
            classes=classes or [],
            goods_services=goods_services,
            query_intent=query_intent,
            max_results=max_results,
            live_api_calls=False,
        )
    except (CompuMarkAPIError, ValueError) as exc:
        return _error_payload(
            error_type="api" if isinstance(exc, CompuMarkAPIError) else "validation",
            message=str(exc),
            brand_name=brand_name,
            jurisdictions=jurisdictions,
            classes=classes or [],
            goods_services=goods_services,
            query_intent=query_intent,
            max_results=max_results,
            live_api_calls=isinstance(exc, CompuMarkAPIError),
        )


def _error_payload(
    *,
    error_type: str,
    message: str,
    brand_name: str,
    jurisdictions: list[str],
    classes: list[str],
    goods_services: str | None,
    query_intent: str,
    max_results: int,
    live_api_calls: bool,
) -> str:
    payload = {
        "source": "compumark",
        "succeeded": False,
        "live_api_calls": live_api_calls,
        "error_type": error_type,
        "error_message": message,
        "planned_request": {
            "brand_name": brand_name,
            "jurisdictions": jurisdictions,
            "classes": classes,
            "goods_services": goods_services,
            "query_intent": query_intent,
            "max_results": max_results,
        },
        "candidates": [],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


__all__ = ["compumark_trademark_search"]
