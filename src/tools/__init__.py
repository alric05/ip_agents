"""
Unified Tools Module for LangGraph Agent.

This module provides all tools for the novelty checker agent:

1. API Clients (low-level):
   - Innography (Patent keyword search)
   - Web of Science (NPL search)
   - NGSP (Semantic patent search)

2. Search Tools (LangChain @tool decorated):
   - Individual search tools
   - Batch search tools for multi-query execution

3. Analysis Tools:
   - Coverage evaluation
   - Feature matrix building
   - Reference triage

Usage:
    from tools import get_all_tools
    tools = get_all_tools()
    
    # Or import specific tools:
    from tools import batch_patent_search, evaluate_coverage
"""

# ═══════════════════════════════════════════════════════════════════════════════
# Clients (low-level API wrappers)
# ═══════════════════════════════════════════════════════════════════════════════
from src.tools.clients import (
    # Schemas
    Article,
    DateBoundaries,
    Patent,
    SearchResult,
    Sorting,
    # WOS
    WOSClient,
    WOSConfig,
    npl_search_tool,
    get_article_by_wos_number,
    get_article,
    convert_articles_to_search_results,
    # NGSP
    NGSPClient,
    NGSPConfig,
    semantic_patent_search_tool,
    semantic_search,
    convert_ngsp_to_search_results,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Search Tools (individual and batch)
# ═══════════════════════════════════════════════════════════════════════════════
from src.tools.search import (
    patent_keyword_search,
    npl_search,
    semantic_patent_search,
    get_patent_details,
    get_patent_citations,
    batch_patent_search,
    batch_npl_search,
    batch_semantic_search,
    batch_unified_search,
    batch_citation_search,
    citation_chain_search,
    log_search_execution,
    log_batch_search_execution,
    SearchHit,
    BatchSearchResult,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Analysis Tools
# ═══════════════════════════════════════════════════════════════════════════════
from src.tools.analysis import (
    evaluate_coverage,
    triage_reference,
    map_features_to_reference,
    generate_search_strategy,
    build_feature_matrix,
    validate_feature_matrix_format,
    CoverageLevel,
    FeatureCoverage,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Aggregation
# ═══════════════════════════════════════════════════════════════════════════════
from src.tools.aggregation import aggregate_search_results

# ═══════════════════════════════════════════════════════════════════════════════
# Reflection (Strategic Thinking)
# ═══════════════════════════════════════════════════════════════════════════════
from src.tools.reflection import think_tool

# ═══════════════════════════════════════════════════════════════════════════════
# Findings Persistence (Phase 3)
# ═══════════════════════════════════════════════════════════════════════════════
from src.tools.findings import (
    save_round_findings,
    get_all_findings,
    get_coverage_gaps,
    summarize_findings_for_report,
    get_findings_tools,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Registry (tool sets)
# ═══════════════════════════════════════════════════════════════════════════════
from src.tools.registry import (
    get_all_tools,
    get_search_tools,
    get_analysis_tools,
    get_batch_only_tools,
    get_content_tools,
    get_citation_tools,
    get_tool_info,
    print_tool_guide,
    get_findings_tools,
)


__all__ = [
    # Schemas
    "Patent",
    "Article", 
    "SearchResult",
    "DateBoundaries",
    "Sorting",
    # Clients
    "WOSClient",
    "WOSConfig",
    "NGSPClient",
    "NGSPConfig",
    # Individual search tools
    "patent_keyword_search",
    "npl_search",
    "semantic_patent_search",
    "get_patent_details",
    "get_patent_citations",
    "npl_search_tool",
    "semantic_patent_search_tool",
    # Batch search tools
    "batch_patent_search",
    "batch_npl_search",
    "batch_semantic_search",
    "batch_unified_search",
    "batch_citation_search",
    "citation_chain_search",
    # Logging tools
    "log_search_execution",
    "log_batch_search_execution",
    # Analysis tools
    "evaluate_coverage",
    "triage_reference",
    "map_features_to_reference",
    "generate_search_strategy",
    "build_feature_matrix",
    "validate_feature_matrix_format",
    "aggregate_search_results",
    # Reflection tools
    "think_tool",
    # Findings persistence tools (Phase 3)
    "save_round_findings",
    "get_all_findings",
    "get_coverage_gaps",
    "summarize_findings_for_report",
    "get_findings_tools",
    # Data classes
    "SearchHit",
    "BatchSearchResult",
    "CoverageLevel",
    "FeatureCoverage",
    # Helper functions
    "get_article",
    "get_article_by_wos_number",
    "convert_articles_to_search_results",
    "convert_ngsp_to_search_results",
    "semantic_search",
    # Registry
    "get_all_tools",
    "get_search_tools",
    "get_analysis_tools",
    "get_batch_only_tools",
    "get_content_tools",
    "get_citation_tools",
    "get_tool_info",
    "print_tool_guide",
    "get_findings_tools",
]
