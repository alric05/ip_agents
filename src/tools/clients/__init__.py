"""API clients for external search services.

This module provides low-level clients for:
- Derwent (Patent keyword + citation search, via src.tools.clients.derwent)
- Web of Science (NPL search)
- NGSP (Semantic patent search)

The Innography client lives in `innography.py` for reference only — it is
no longer imported or re-exported from this package.
"""

from src.tools.clients.schemas import (
    Article,
    DateBoundaries,
    Patent,
    SearchResult,
    Sorting,
)
from src.tools.clients.wos import (
    WOSClient,
    WOSConfig,
    npl_search_tool,
    get_article_by_wos_number,
    npl_search,
    get_article,
    convert_articles_to_search_results,
)
from src.tools.clients.ngsp import (
    NGSPClient,
    NGSPConfig,
    semantic_patent_search_tool,
    semantic_search,
    convert_ngsp_to_search_results,
)

__all__ = [
    # Schemas
    "Article",
    "DateBoundaries",
    "Patent",
    "SearchResult",
    "Sorting",
    # WOS
    "WOSClient",
    "WOSConfig",
    "npl_search_tool",
    "get_article_by_wos_number",
    "npl_search",
    "get_article",
    "convert_articles_to_search_results",
    # NGSP
    "NGSPClient",
    "NGSPConfig",
    "semantic_patent_search_tool",
    "semantic_search",
    "convert_ngsp_to_search_results",
]
