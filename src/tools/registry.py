"""Tool registry for the Novelty Checker deep agent.

Provides organized access to all tools, allowing the agent to be configured
with different tool sets based on the task.
"""

from langchain_core.tools import BaseTool

from .search import (
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
)

from .clients.derwent import (
    search_derwent_patents_fld,
    search_derwent_citations,
)

from .analysis import (
    evaluate_coverage,
    triage_reference,
    map_features_to_reference,
    generate_search_strategy,
    build_feature_matrix,
    validate_feature_matrix_format,
)

from .aggregation import aggregate_search_results

from .reflection import think_tool

from src.config.settings import is_npl_enabled

NPL_TOOL_NAMES = {"npl_search", "batch_npl_search"}

from .findings import (
    save_round_findings,
    get_all_findings,
    get_coverage_gaps,
    summarize_findings_for_report,
    FINDINGS_TOOLS,
)


# =============================================================================
# Tool Categories
# =============================================================================

SEARCH_TOOLS: list[BaseTool] = [
    patent_keyword_search,
    npl_search,
    semantic_patent_search,
    get_patent_citations,
]

BATCH_SEARCH_TOOLS: list[BaseTool] = [
    batch_patent_search,
    batch_npl_search,
    batch_semantic_search,
    batch_unified_search,
    # batch_citation_search is owned by CITATION_TOOLS (keeps citation-specific
    # tools together and prevents duplication in get_all_tools()).
]

LOGGING_TOOLS: list[BaseTool] = [
    log_search_execution,
    log_batch_search_execution,
]

ANALYSIS_TOOLS: list[BaseTool] = [
    evaluate_coverage,
    triage_reference,
    map_features_to_reference,
    generate_search_strategy,
    build_feature_matrix,
    validate_feature_matrix_format,
    aggregate_search_results,
]

REFLECTION_TOOLS: list[BaseTool] = [
    think_tool,
]

CONTENT_TOOLS: list[BaseTool] = [
    get_patent_details,
]

CITATION_TOOLS: list[BaseTool] = [
    get_patent_citations,
    batch_citation_search,
    citation_chain_search,
]

DERWENT_TOOLS: list[BaseTool] = [
    search_derwent_patents_fld,
    search_derwent_citations,
    # `patent_keyword_search` is a higher-level wrapper that routes through
    # `_derwent_fld_search` under the hood. Listed here (not only in
    # SEARCH_TOOLS) so that `get_all_tools()` — which consumes DERWENT_TOOLS
    # but not SEARCH_TOOLS post-migration — still exposes it to the orchestrator.
    patent_keyword_search,
]

FINDINGS_PERSISTENCE_TOOLS: list[BaseTool] = FINDINGS_TOOLS


# =============================================================================
# Registry Functions
# =============================================================================

def get_all_tools() -> list[BaseTool]:
    """Get all available tools for the novelty checker agent.

    Derwent is the sole patent search provider — Innography fallback path
    was removed. All search.py wrappers (patent_keyword_search,
    get_patent_details, get_patent_citations, batch_patent_search,
    batch_citation_search, citation_chain_search) now route through Derwent
    internally.

    Returns:
        Complete list of all tools (NPL tools excluded when enable_npl_search=False)
    """
    tools = (
        DERWENT_TOOLS                # Derwent patent search
        + BATCH_SEARCH_TOOLS
        + CONTENT_TOOLS
        + CITATION_TOOLS
        + LOGGING_TOOLS
        + ANALYSIS_TOOLS
        + REFLECTION_TOOLS
        + FINDINGS_PERSISTENCE_TOOLS
    )
    if not is_npl_enabled():
        tools = [t for t in tools if t.name not in NPL_TOOL_NAMES]
    return tools


def get_reflection_tools() -> list[BaseTool]:
    """Get reflection tools for strategic thinking.
    
    Returns:
        List of reflection tools (think_tool)
    """
    return REFLECTION_TOOLS


def get_findings_tools() -> list[BaseTool]:
    """Get findings persistence tools.
    
    Returns:
        List of tools for saving/retrieving findings
    """
    return FINDINGS_PERSISTENCE_TOOLS


def get_content_tools() -> list[BaseTool]:
    """Get content retrieval tools (look up patents/articles by number).
    
    Returns:
        List of content retrieval tools
    """
    return CONTENT_TOOLS.copy()


def get_citation_tools() -> list[BaseTool]:
    """Get citation analysis tools.
    
    Returns:
        List of citation retrieval and batch citation tools
    """
    return CITATION_TOOLS.copy()


def get_derwent_tools() -> list[BaseTool]:
    """Get Clarivate Derwent patent search tools.

    Returns:
        List of Derwent patent search tools (requires JWT authentication)
    """
    return DERWENT_TOOLS.copy()


def get_search_tools(include_batch: bool = True) -> list[BaseTool]:
    """Get search-related tools.

    Args:
        include_batch: If True, include batch search tools

    Returns:
        List of search tools (NPL tools excluded when enable_npl_search=False)
    """
    if include_batch:
        tools = SEARCH_TOOLS + BATCH_SEARCH_TOOLS
    else:
        tools = SEARCH_TOOLS.copy()
    if not is_npl_enabled():
        tools = [t for t in tools if t.name not in NPL_TOOL_NAMES]
    return tools


def get_analysis_tools() -> list[BaseTool]:
    """Get analysis-related tools.
    
    Returns:
        List of analysis tools
    """
    return ANALYSIS_TOOLS.copy()



def get_batch_only_tools() -> list[BaseTool]:
    """Get batch-optimized tool set (recommended for efficiency).
    
    Using batch_unified_search is more efficient than individual searches.
    
    Returns:
        Batch search + analysis tools
    """
    return [batch_unified_search] + ANALYSIS_TOOLS


# =============================================================================
# Tool Info
# =============================================================================

def get_tool_info() -> dict:
    """Get information about all available tools.
    
    Returns:
        Dictionary with tool names, descriptions, and categories
    """
    return {
        "search": {
            "individual": [
                {
                    "name": "patent_keyword_search",
                    "description": "Search Innography with @(field) syntax",
                    "use_case": "Single targeted patent search",
                },
                {
                    "name": "npl_search",
                    "description": "Search Web of Science with TS=/TI=/AB= syntax",
                    "use_case": "Single targeted academic literature search",
                },
                {
                    "name": "semantic_patent_search",
                    "description": "AI-powered semantic patent search",
                    "use_case": "Conceptual search with natural language",
                },
            ],
            "batch": [
                {
                    "name": "batch_patent_search",
                    "description": "Multiple patent searches in one call",
                    "use_case": "Execute multiple keyword queries efficiently",
                },
                {
                    "name": "batch_npl_search",
                    "description": "Multiple NPL searches in one call",
                    "use_case": "Execute multiple academic queries efficiently",
                },
                {
                    "name": "batch_semantic_search",
                    "description": "Multiple semantic searches in one call",
                    "use_case": "Execute multiple conceptual queries efficiently",
                },
                {
                    "name": "batch_unified_search",
                    "description": "All search types in one call (RECOMMENDED)",
                    "use_case": "Most efficient - patent + NPL + semantic together",
                },
            ],
        },
        "analysis": [
            {
                "name": "evaluate_coverage",
                "description": "Evaluate coverage gaps per feature",
                "use_case": "Decide if more searching needed (adaptive loop)",
            },
            {
                "name": "triage_reference",
                "description": "Quick A/B/C relevance assessment",
                "use_case": "Fast initial screening of results",
            },
            {
                "name": "map_features_to_reference",
                "description": "Detailed Y/Y1/N feature mapping",
                "use_case": "Full analysis for report inclusion",
            },
            {
                "name": "generate_search_strategy",
                "description": "Suggest next search approaches",
                "use_case": "Avoid repetitive searches, find new angles",
            },
        ],
    }


def print_tool_guide():
    """Print a guide to using the tools effectively."""
    guide = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                    NOVELTY CHECKER TOOL GUIDE                                ║
╚══════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────┐
│ SEARCH STRATEGY                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. START with batch_unified_search for efficiency                           │
│ 2. ALWAYS include 3-5 semantic queries per cycle                            │
│ 3. Use individual tools only for follow-up/targeted searches                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ ADAPTIVE LOOP                                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Run searches → 2. Triage results → 3. Map features → 4. Evaluate coverage│
│                                                                             │
│ If WEAK/NONE coverage → use generate_search_strategy → loop back to step 1 │
│ If STRONG/SATURATED → proceed to report generation                          │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ QUERY SYNTAX QUICK REFERENCE                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│ PATENT (Derwent):                                                           │
│   CTB=(term1 NEAR5 term2);                                                 │
│   Every query ends with semicolon ;                                         │
│                                                                             │
│ NPL (Web of Science):                                                       │
│   TS=((term1 OR term2) NEAR/5 term3)                                       │
│   NEVER use AND inside NEAR!                                                │
│                                                                             │
│ SEMANTIC (NGSP):                                                            │
│   Plain English description - NO Boolean operators                          │
└─────────────────────────────────────────────────────────────────────────────┘
"""
    print(guide)
