"""Human-readable labels for SSE streaming events.

Shared by ``server.py`` (for ``agentActivityBubble`` headers/text) and
``research_timeline.py`` (for timeline step titles).
"""

from __future__ import annotations


NODE_LABELS: dict[str, str] = {
    "agent": "Orchestrator is planning...",
    "patent-researcher": "Patent Researcher is searching...",
    "npl-researcher": "NPL Researcher is searching...",
    "semantic-researcher": "Semantic Researcher is searching...",
    "citation-researcher": "Citation Researcher is analyzing...",
    "coverage-analyst": "Coverage Analyst is evaluating...",
    "report-writer": "Report Writer is drafting...",
    "keyword-precision-searcher": "Keyword Searcher is searching...",
    "semantic-recall-searcher": "Semantic Searcher is searching...",
    "structural-combo-searcher": "Combo Searcher is searching...",
}

TOOL_LABELS: dict[str, str] = {
    "patent_keyword_search": "Searching patents...",
    "batch_patent_search": "Running batch patent search...",
    "npl_search": "Searching academic literature...",
    "batch_npl_search": "Running batch NPL search...",
    "semantic_patent_search": "Running semantic patent search...",
    "batch_semantic_search": "Running batch semantic search...",
    "batch_unified_search": "Running unified search...",
    "batch_citation_search": "Searching citations...",
    "citation_chain_search": "Following citation chains...",
    "get_patent_details": "Fetching patent details...",
    "get_patent_citations": "Fetching patent citations...",
    "evaluate_coverage": "Evaluating feature coverage...",
    "triage_reference": "Triaging reference relevance...",
    "map_features_to_reference": "Mapping features to reference...",
    "generate_search_strategy": "Generating search strategy...",
    "build_feature_matrix": "Building feature matrix...",
    "validate_feature_matrix_format": "Validating feature matrix...",
    "aggregate_search_results": "Aggregating search results...",
    "summarize_findings_for_report": "Summarizing findings...",
    "log_search_execution": "Logging search...",
    "log_batch_search_execution": "Logging batch search...",
}

INTERNAL_TOOLS: set[str] = {
    "think_tool",
    "save_round_findings",
    "get_all_findings",
    "get_coverage_gaps",
}
