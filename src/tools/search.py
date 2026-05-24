"""Search tools for the Novelty Checker deep agent.

This module provides individual and batch search tools. Patent search and
citation tools route through the Derwent client (src.tools.clients.derwent);
NPL search uses Web of Science; semantic search uses NGSP. The Innography
client is no longer wired into any tool — kept in the codebase as reference
only (see docs/DERWENT_MIGRATION_CHANGES.md).
"""

import logging
from typing import Optional, Annotated
from dataclasses import dataclass, field

from langchain_core.tools import tool

# Import resilience patterns (Phase 1)
from src.tools.resilience import retry_with_backoff

# Import the API clients still in use
CLIENTS_AVAILABLE = False
Patent = None
Article = None
WOSClient = None
NGSPClient = None

try:
    from src.tools.clients.schemas import Patent, Article
    from src.tools.clients.wos import WOSClient
    from src.tools.clients.ngsp import NGSPClient

    CLIENTS_AVAILABLE = True
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"API clients not available: {e}")

LOGGER = logging.getLogger("src.tools.search")


# =============================================================================
# Result Data Classes
# =============================================================================

@dataclass
class SearchHit:
    """Unified search result format."""
    ref_id: str
    ref_type: str  # "patent" or "npl"
    title: str
    abstract: str
    source: str  # "derwent", "wos", "ngsp"
    query_id: str
    relevance_score: float = 0.0
    priority_date: Optional[str] = None
    assignee: Optional[str] = None
    authors: list[str] = field(default_factory=list)
    journal: Optional[str] = None
    doi: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "ref_id": self.ref_id,
            "ref_type": self.ref_type,
            "title": self.title,
            "abstract": self.abstract[:500] if self.abstract else "",
            "source": self.source,
            "query_id": self.query_id,
            "relevance_score": self.relevance_score,
            "priority_date": self.priority_date,
            "assignee": self.assignee,
            "authors": self.authors,
            "journal": self.journal,
            "doi": self.doi,
        }


@dataclass
class BatchSearchResult:
    """Result of a batch search operation."""
    query_id: str
    query_text: str
    source: str
    result_count: int
    hits: list[SearchHit]
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "query_text": self.query_text,
            "source": self.source,
            "result_count": self.result_count,
            "hits": [h.to_dict() for h in self.hits],
            "error": self.error,
        }


# =============================================================================
# Individual Search Tools
# =============================================================================

@tool
@retry_with_backoff(max_retries=3, base_delay=2.0)
def patent_keyword_search(
    query: Annotated[str, "Derwent query using field tag syntax (e.g., 'CTB=(terms);')"],
    feature_id: Annotated[str, "Feature ID this search is for (e.g., 'F1', 'F2')"] = "",
    max_results: Annotated[int, "Maximum number of patents to return"] = 10,
) -> str:
    """Search patent databases using Derwent keyword syntax.

    CRITICAL SYNTAX RULES:
    1. Every query must begin with a field tag: CTB=, ALL=, ti=, ab=, nov=, etc.
    2. Every query should end with a semicolon ;
    3. Every concept group must be enclosed in parentheses
    4. Proximity: NEAR/NEARn (either order), ADJ/ADJn (order preserved), SAME (same paragraph)
    5. Truncation: * (0+ chars), ? (1 char)

    Example queries:
    - CTB=(polymer NEAR5 fluorescence);
    - ALL=((UV OR ultraviolet) AND degradation);
    - CTB=((hydraulic NEAR3 valve) SAME (orifice OR control));

    Args:
        query: Derwent query syntax
        feature_id: Which feature this search targets
        max_results: Max patents to return

    Returns:
        Formatted search results with patent details
    """
    try:
        from src.tools.clients.derwent import _derwent_fld_search
        patents = _derwent_fld_search(query, size=max_results)
    except ImportError:
        return f"""[MOCK] Patent search for {feature_id}: "{query}"

⚠️ Derwent API client not available. Ensure JWT token is configured.

This is a simulated result. In production, real patents would be returned."""

    if isinstance(patents, str):
        # Error string returned
        return patents

    if not patents:
        return f"No patents found for query: {query}"

    result_lines = [
        f"## Patent Search Results for {feature_id or 'General'}",
        f"**Query**: `{query}`",
        f"**Results**: {len(patents)} patents",
        "",
    ]

    for i, p in enumerate(patents, 1):
        result_lines.append(f"### {i}. {p.get('publication_number', 'N/A')}")
        result_lines.append(f"- **Title**: {p.get('dwpi_title') or p.get('title') or 'N/A'}")
        result_lines.append(f"- **Priority Date**: {p.get('priority_date') or 'N/A'}")
        result_lines.append(f"- **Assignee**: {p.get('assignee') or 'N/A'}")
        abstract = p.get('abstract') or ''
        if abstract:
            result_lines.append(f"- **Abstract**: {abstract[:300]}...")
        result_lines.append("")

    return "\n".join(result_lines)


@tool
@retry_with_backoff(max_retries=3, base_delay=2.0)
def npl_search(
    query: Annotated[str, "Web of Science query using TS=/TI=/AB= syntax"],
    feature_id: Annotated[str, "Feature ID this search is for"] = "",
    max_results: Annotated[int, "Maximum number of articles to return"] = 10,
    from_year: Annotated[Optional[int], "Filter by start year"] = None,
    to_year: Annotated[Optional[int], "Filter by end year"] = None,
) -> str:
    """Search academic literature using Web of Science syntax.
    
    CRITICAL SYNTAX RULES:
    1. MUST start with field tag: TS=, TI=, or AB=
    2. NEVER use AND inside NEAR clauses! Use OR instead.
    3. Wildcards need 3+ chars before: oxid* OK, ox* FAILS
    
    SAFE PATTERNS:
    - TS=((term1 OR term2) AND term3) — AND without NEAR
    - TS=((term1 OR term2) NEAR/5 term3) — OR inside NEAR
    - TS=(term1 NEAR/5 term2) AND TS=(term3) — AND at top level
    
    FORBIDDEN (WILL CRASH):
    - TS=((A AND B) NEAR/5 C) — AND inside NEAR!
    
    Args:
        query: Web of Science query syntax
        feature_id: Which feature this search targets
        max_results: Max articles to return
        from_year: Optional start year filter
        to_year: Optional end year filter
        
    Returns:
        Formatted search results with article details
    """
    if not CLIENTS_AVAILABLE:
        return f"""[MOCK] NPL search for {feature_id}: "{query}"

⚠️ API clients not available. Install dependencies and configure:
- WOS_API_KEY

This is a simulated result. In production, real articles would be returned."""

    try:
        client = WOSClient()
        articles = client.npl_search(query, max_results, from_year, to_year)
        
        if not articles:
            return f"No articles found for query: {query}"
        
        result_lines = [
            f"## NPL Search Results for {feature_id or 'General'}",
            f"**Query**: `{query}`",
            f"**Results**: {len(articles)} articles",
            "",
        ]
        
        for i, a in enumerate(articles, 1):
            result_lines.append(f"### {i}. {a.wos_number}")
            result_lines.append(f"- **Title**: {a.title or 'N/A'}")
            result_lines.append(f"- **Year**: {a.publication_year or 'N/A'}")
            result_lines.append(f"- **Journal**: {a.journal or 'N/A'}")
            result_lines.append(f"- **DOI**: {a.doi or 'N/A'}")
            if a.abstract:
                result_lines.append(f"- **Abstract**: {a.abstract[:300]}...")
            result_lines.append("")
        
        return "\n".join(result_lines)
        
    except Exception as e:
        LOGGER.error("NPL search failed: %s", e)
        return f"NPL search error: {str(e)}"


@tool
@retry_with_backoff(max_retries=3, base_delay=2.0)
def semantic_patent_search(
    query: Annotated[str, "Natural language description of the concept (NO Boolean operators!)"],
    feature_id: Annotated[str, "Feature ID this search is for"] = "",
    max_results: Annotated[int, "Maximum number of patents to return"] = 20,
) -> str:
    """Search patents using semantic/AI-powered similarity.
    
    IMPORTANT: Use plain English, NOT Boolean operators!
    
    GOOD queries:
    - "UV fluorescence detection for polymer degradation"
    - "Compliant robotic gripper using auxetic metamaterials"
    - "Machine learning system for predicting battery failure"
    
    BAD queries:
    - "polymer AND fluorescence AND UV" — Don't use Boolean!
    
    Args:
        query: Natural language description (1-3 sentences ideal)
        feature_id: Which feature this search targets
        max_results: Max patents to return
        
    Returns:
        Formatted search results with relevance scores
    """
    if not CLIENTS_AVAILABLE:
        return f"""[MOCK] Semantic search for {feature_id}: "{query}"

⚠️ API clients not available. Install dependencies and configure NGSP.

This is a simulated result. In production, semantic matches would be returned."""

    try:
        client = NGSPClient()
        patents = client.semantic_search(query, max_results)
        
        if not patents:
            return f"No semantic matches found for: {query}"
        
        result_lines = [
            f"## Semantic Search Results for {feature_id or 'General'}",
            f"**Query**: \"{query}\"",
            f"**Results**: {len(patents)} patents",
            "",
        ]
        
        for i, p in enumerate(patents, 1):
            score = p.relevance_score or 0.0
            result_lines.append(f"### {i}. {p.publication_number} (Score: {score:.2f})")
            result_lines.append(f"- **Title**: {p.title or 'N/A'}")
            result_lines.append(f"- **Priority Date**: {p.priority_date or 'N/A'}")
            if p.abstract:
                result_lines.append(f"- **Abstract**: {p.abstract[:300]}...")
            result_lines.append("")
        
        return "\n".join(result_lines)
        
    except Exception as e:
        LOGGER.error("Semantic search failed: %s", e)
        return f"Semantic search error: {str(e)}"


# =============================================================================
# Content Retrieval Tools
# =============================================================================

@tool
def get_patent_details(
    publication_number: Annotated[str, "Patent publication number, e.g. 'US10234567B2', 'EP3411222B1'"],
) -> str:
    """Retrieve FULL patent details by publication number via Derwent.

    Use this tool to look up the complete content of a specific patent when
    you already know its publication number. Returns:
    - Title (original + DWPI-enhanced)
    - Full abstract
    - DWPI Novelty (what's new about this patent)
    - DWPI Advantage (technical benefits)
    - Claims text
    - Priority date, assignee, inventors

    Common use cases:
    - After search_derwent_citations returns a promising citation, fetch its full content
    - When building the Patents Record View and need complete bibliographic data
    - When you need to verify feature coverage against a patent's actual claims

    Note: This is a LOOKUP tool, not a SEARCH tool. You must already have the
    publication number. For finding patents by topic, use search_derwent_patents_fld
    or semantic_patent_search instead.
    """
    try:
        from src.tools.clients.derwent import _derwent_fld_search
        # Request full claims (`cl`) and DWPI detailed description (`dtd`)
        # in addition to the defaults. These are omitted from landscape
        # searches to keep payloads small, but Feature Matrix grading on
        # A/B refs needs them — first-claim-only (`cl1`) buries key
        # limitation language in unrelated claims.
        _FULL_DETAIL_FIELDS = "pn,ki,ti,tid,ab,nov,adv,use,cl,cl1,dtd,prd,co,in,rank"
        results = _derwent_fld_search(
            f"pn=({publication_number})",
            return_fields=_FULL_DETAIL_FIELDS,
            size=1,
        )
    except ImportError:
        return f"""[MOCK] Patent details for: {publication_number}

⚠️ Derwent API client not available. Ensure JWT token is configured.

This is a simulated result. In production, real patent details would be returned."""

    if isinstance(results, str):
        return results

    if not results:
        return f"No patent found for publication number: {publication_number}"

    p = results[0]
    lines = [f"# Patent Details: {p.get('publication_number', publication_number)}", ""]

    if p.get('title'):
        lines.append(f"**Title:** {p['title']}")
    if p.get('dwpi_title'):
        lines.append(f"**DWPI Title:** {p['dwpi_title']}")
    if p.get('priority_date'):
        lines.append(f"**Priority Date:** {p['priority_date']}")
    if p.get('assignee'):
        lines.append(f"**Assignee:** {p['assignee']}")
    if p.get('inventors'):
        lines.append(f"**Inventors:** {', '.join(p['inventors'])}")
    lines.append("")

    if p.get('abstract'):
        lines.append(f"## Abstract\n{p['abstract']}")
    if p.get('dwpi_abstract_novelty'):
        lines.append(f"\n## DWPI Novelty\n{p['dwpi_abstract_novelty']}")
    if p.get('dwpi_abstract_advantage'):
        lines.append(f"\n## DWPI Advantage\n{p['dwpi_abstract_advantage']}")
    if p.get('dwpi_abstract_use'):
        lines.append(f"\n## DWPI Use\n{p['dwpi_abstract_use']}")
    if p.get('claims'):
        lines.append(f"\n## Claims (first 8000 chars)\n{p['claims'][:8000]}")
    if p.get('dwpi_abstract_detailed_description'):
        lines.append(
            f"\n## DWPI Description (first 5000 chars)\n"
            f"{p['dwpi_abstract_detailed_description'][:5000]}"
        )

    return "\n".join(lines)


@tool
@retry_with_backoff(max_retries=3, base_delay=2.0)
def get_patent_citations(
    publication_number: Annotated[str, "Patent publication number (e.g., 'US8718044', 'EP3411222B1')"],
) -> str:
    """Retrieve forward and backward citations for a patent via Derwent.

    This tool finds:
    - Forward citations: Patents that cite this patent (newer work building on this)
    - Backward citations: Patents that this patent cites (prior art references)

    Use cases:
    - Finding related newer patents in a technology space
    - Understanding the prior art landscape
    - Tracing patent lineage and technology evolution
    - Identifying key foundational patents
    - Expanding search to related patents from citation networks

    Args:
        publication_number: Patent publication number (e.g., 'US8718044', 'EP3411222B1')

    Returns:
        Formatted citation information including counts and details
    """
    try:
        from src.tools.clients.derwent import _derwent_citation_search
        citations = _derwent_citation_search(publication_number)
    except ImportError:
        return f"""[MOCK] Patent citations for: {publication_number}

⚠️ Derwent API client not available. Ensure JWT token is configured.

This is a simulated result. In production, real citations would be returned."""

    if isinstance(citations, dict) and "error" in citations:
        return f"Patent citations error: {citations['error']}"

    # Handle list result (shouldn't happen for single patent, but be safe)
    if isinstance(citations, list):
        citations = citations[0] if citations else {}

    result_lines = [
        f"## Patent Citations for {publication_number}",
        "",
        f"**Forward Citations (citing this patent)**: {citations.get('total_forward_citations', 0)}",
        f"**Backward Citations (cited by this patent)**: {citations.get('total_backward_citations', 0)}",
        "",
    ]

    if citations.get('forward_citations'):
        result_lines.append("### Forward Citations (Newer Patents Citing This)")
        for i, c in enumerate(citations['forward_citations'][:20], 1):
            result_lines.append(f"{i}. **{c['publication_number']}**")
            result_lines.append(f"   - Title: {c.get('title') or c.get('dwpi_title') or 'N/A'}")
            result_lines.append(f"   - Assignee: {c.get('assignee', 'N/A')}")
            result_lines.append(f"   - Priority Date: {c.get('priority_date', 'N/A')}")
            abstract = c.get('dwpi_novelty') or c.get('abstract') or ''
            if abstract:
                truncated = abstract[:300] + ('...' if len(abstract) > 300 else '')
                result_lines.append(f"   - Abstract: {truncated}")
        result_lines.append("")

    if citations.get('backward_citations'):
        result_lines.append("### Backward Citations (Prior Art Cited)")
        for i, c in enumerate(citations['backward_citations'][:20], 1):
            result_lines.append(f"{i}. **{c['publication_number']}**")
            result_lines.append(f"   - Title: {c.get('title') or c.get('dwpi_title') or 'N/A'}")
            result_lines.append(f"   - Assignee: {c.get('assignee', 'N/A')}")
            result_lines.append(f"   - Priority Date: {c.get('priority_date', 'N/A')}")
            abstract = c.get('dwpi_novelty') or c.get('abstract') or ''
            if abstract:
                truncated = abstract[:300] + ('...' if len(abstract) > 300 else '')
                result_lines.append(f"   - Abstract: {truncated}")
        result_lines.append("")

    return "\n".join(result_lines)


@tool
@retry_with_backoff(max_retries=3, base_delay=2.0)
def batch_citation_search(
    publication_numbers: Annotated[list[str], "Patent numbers to analyze, e.g. ['US10234567B2', 'EP9876543A1']"],
    max_citations_per_patent: Annotated[int, "Max citations to return per patent"] = 20,
    directions: Annotated[list[str], "Citation directions: 'forward', 'backward', or both"] = ["forward", "backward"],
) -> str:
    """Analyze citation networks for multiple patents in one call.

    More efficient than calling get_patent_citations multiple times.
    Deduplicates citations found across multiple seed patents.

    Use after finding A-level references to discover related prior art
    in their citation networks.

    Args:
        publication_numbers: List of patent publication numbers to analyze
        max_citations_per_patent: Maximum citations to return per seed patent
        directions: Which citation directions to include

    Returns:
        Consolidated, deduplicated citation summary across all seed patents
    """
    try:
        from src.tools.clients.derwent import _derwent_citation_search
    except ImportError:
        return f"""[MOCK] Batch citation search for: {publication_numbers}

⚠️ Derwent API client not available. Ensure JWT token is configured.

This is a simulated result. In production, real citations would be returned."""

    all_forward: dict[str, dict] = {}  # pub_number -> citation dict (deduplicated)
    all_backward: dict[str, dict] = {}
    per_patent_stats: list[str] = []
    errors: list[str] = []

    for pub_num in publication_numbers:
        try:
            citations = _derwent_citation_search(pub_num, max_citations=max_citations_per_patent)

            if isinstance(citations, dict) and "error" in citations:
                errors.append(f"- {pub_num}: {citations['error']}")
                continue

            # Handle list result for single patent
            if isinstance(citations, list):
                citations = citations[0] if citations else {}

            fwd_count = 0
            bwd_count = 0

            if "forward" in directions:
                for c in citations.get("forward_citations", [])[:max_citations_per_patent]:
                    key = c.get("publication_number", "")
                    if key and key not in all_forward:
                        c["seed_patents"] = [pub_num]
                        all_forward[key] = c
                        fwd_count += 1
                    elif key and key in all_forward:
                        all_forward[key].setdefault("seed_patents", []).append(pub_num)

            if "backward" in directions:
                for c in citations.get("backward_citations", [])[:max_citations_per_patent]:
                    key = c.get("publication_number", "")
                    if key and key not in all_backward:
                        c["seed_patents"] = [pub_num]
                        all_backward[key] = c
                        bwd_count += 1
                    elif key and key in all_backward:
                        all_backward[key].setdefault("seed_patents", []).append(pub_num)

            per_patent_stats.append(
                f"- **{pub_num}**: {citations.get('total_forward_citations', 0)} forward, "
                f"{citations.get('total_backward_citations', 0)} backward "
                f"(kept {fwd_count} new fwd, {bwd_count} new bwd)"
            )
        except Exception as e:
            LOGGER.error("Batch citation error for %s: %s", pub_num, e)
            errors.append(f"- {pub_num}: {str(e)}")

    # Build consolidated output
    result_lines = [
        "## Batch Citation Analysis",
        "",
        f"**Seed patents analyzed**: {len(publication_numbers)}",
        f"**Unique forward citations**: {len(all_forward)}",
        f"**Unique backward citations**: {len(all_backward)}",
        "",
        "### Per-Patent Breakdown",
    ]
    result_lines.extend(per_patent_stats)

    if errors:
        result_lines.append("")
        result_lines.append("### Errors")
        result_lines.extend(errors)

    if all_forward and "forward" in directions:
        result_lines.append("")
        result_lines.append("### Unique Forward Citations (Newer Patents)")
        # Sort by number of seed patents that share this citation (most connected first)
        sorted_fwd = sorted(all_forward.values(), key=lambda x: len(x.get("seed_patents", [])), reverse=True)
        for i, c in enumerate(sorted_fwd[:50], 1):
            seeds = c.get("seed_patents", [])
            result_lines.append(f"{i}. **{c['publication_number']}**")
            result_lines.append(f"   - Title: {c.get('title') or c.get('dwpi_title') or 'N/A'}")
            result_lines.append(f"   - Assignee: {c.get('assignee', 'N/A')}")
            result_lines.append(f"   - Priority Date: {c.get('priority_date', 'N/A')}")
            if len(seeds) > 1:
                result_lines.append(f"   - ⭐ Found via {len(seeds)} seed patents: {', '.join(seeds)}")
            abstract = c.get("dwpi_novelty") or c.get("abstract") or ""
            if abstract:
                truncated = abstract[:300] + ("..." if len(abstract) > 300 else "")
                result_lines.append(f"   - Abstract: {truncated}")

    if all_backward and "backward" in directions:
        result_lines.append("")
        result_lines.append("### Unique Backward Citations (Prior Art)")
        sorted_bwd = sorted(all_backward.values(), key=lambda x: len(x.get("seed_patents", [])), reverse=True)
        for i, c in enumerate(sorted_bwd[:50], 1):
            seeds = c.get("seed_patents", [])
            result_lines.append(f"{i}. **{c['publication_number']}**")
            result_lines.append(f"   - Title: {c.get('title') or c.get('dwpi_title') or 'N/A'}")
            result_lines.append(f"   - Assignee: {c.get('assignee', 'N/A')}")
            result_lines.append(f"   - Priority Date: {c.get('priority_date', 'N/A')}")
            if len(seeds) > 1:
                result_lines.append(f"   - ⭐ Found via {len(seeds)} seed patents: {', '.join(seeds)}")
            abstract = c.get("dwpi_novelty") or c.get("abstract") or ""
            if abstract:
                truncated = abstract[:300] + ("..." if len(abstract) > 300 else "")
                result_lines.append(f"   - Abstract: {truncated}")

    result_lines.append("")
    return "\n".join(result_lines)


@tool
def citation_chain_search(
    seed_patent: Annotated[str, "Starting patent publication number (e.g., 'US10234567B2')"],
    max_depth: Annotated[int, "How many citation levels to explore (1 or 2)"] = 2,
    max_per_level: Annotated[int, "Max citations to follow per level"] = 5,
    feature_keywords: Annotated[list[str], "Keywords to filter relevant citations by title/abstract"] = [],
) -> str:
    """Explore multi-hop citation chains starting from a seed patent.

    Level 1: Direct forward/backward citations of the seed patent.
    Level 2: Citations of the most relevant Level 1 citations.

    Uses feature_keywords to filter which Level 1 citations to follow
    deeper, preventing combinatorial explosion.

    Best used when:
    - 1st-order citation analysis found promising leads
    - You want to discover 2nd-order prior art (citations-of-citations)
    - Keyword searches are exhausted but coverage gaps remain

    Args:
        seed_patent: Starting patent publication number
        max_depth: How many levels deep to go (1 = direct only, 2 = citations of citations)
        max_per_level: Max citations to follow at each level
        feature_keywords: Keywords to score/filter citation relevance by title/abstract

    Returns:
        Tree-structured summary showing the citation chain with relevance scores
    """
    try:
        from src.tools.clients.derwent import _derwent_citation_search
    except ImportError:
        return f"""[MOCK] Citation chain search for: {seed_patent}

⚠️ Derwent API client not available. Ensure JWT token is configured.

This is a simulated result. In production, real citation chains would be returned."""

    # Clamp depth
    max_depth = min(max(max_depth, 1), 2)
    keywords_lower = [kw.lower() for kw in feature_keywords]

    result_lines = [
        f"## Citation Chain Analysis for {seed_patent}",
        f"**Depth**: {max_depth} | **Max per level**: {max_per_level} | **Keywords**: {', '.join(feature_keywords) or 'none'}",
        "",
    ]

    def _keyword_score(citation: dict) -> int:
        """Score a citation by how many feature keywords appear in its title/abstract."""
        if not keywords_lower:
            return 0
        text = (
            (citation.get("title") or "") + " " +
            (citation.get("dwpi_title") or "") + " " +
            (citation.get("abstract") or "") + " " +
            (citation.get("dwpi_novelty") or "")
        ).lower()
        return sum(1 for kw in keywords_lower if kw in text)

    def _format_citation(citation: dict, indent: str, idx: int, score: int) -> list[str]:
        """Format a single citation for display."""
        lines = []
        title = citation.get("title") or citation.get("dwpi_title") or "N/A"
        pub_num = citation.get("publication_number", "?")
        lines.append(f"{indent}{idx}. **{pub_num}** (keyword score: {score})")
        lines.append(f"{indent}   - Title: {title}")
        lines.append(f"{indent}   - Assignee: {citation.get('assignee', 'N/A')}")
        lines.append(f"{indent}   - Priority Date: {citation.get('priority_date', 'N/A')}")
        abstract = citation.get("dwpi_novelty") or citation.get("abstract") or ""
        if abstract:
            truncated = abstract[:200] + ("..." if len(abstract) > 200 else "")
            lines.append(f"{indent}   - Abstract: {truncated}")
        return lines

    try:
        # Level 1: Direct citations of seed patent
        level1_citations = _derwent_citation_search(seed_patent)
        if isinstance(level1_citations, dict) and "error" in level1_citations:
            return f"Citation chain search error: {level1_citations['error']}"
        if isinstance(level1_citations, list):
            level1_citations = level1_citations[0] if level1_citations else {}

        fwd_citations = level1_citations.get("forward_citations", [])
        bwd_citations = level1_citations.get("backward_citations", [])

        # Score and sort by keyword relevance
        scored_fwd = [(c, _keyword_score(c)) for c in fwd_citations]
        scored_bwd = [(c, _keyword_score(c)) for c in bwd_citations]
        scored_fwd.sort(key=lambda x: x[1], reverse=True)
        scored_bwd.sort(key=lambda x: x[1], reverse=True)

        top_fwd = scored_fwd[:max_per_level]
        top_bwd = scored_bwd[:max_per_level]

        result_lines.append(f"### Level 1: Direct Citations of {seed_patent}")
        result_lines.append(f"Total: {len(fwd_citations)} forward, {len(bwd_citations)} backward")
        result_lines.append("")

        # Forward Level 1
        if top_fwd:
            result_lines.append("#### Forward Citations (top by keyword relevance)")
            for i, (c, score) in enumerate(top_fwd, 1):
                result_lines.extend(_format_citation(c, "", i, score))
            result_lines.append("")

        # Backward Level 1
        if top_bwd:
            result_lines.append("#### Backward Citations (top by keyword relevance)")
            for i, (c, score) in enumerate(top_bwd, 1):
                result_lines.extend(_format_citation(c, "", i, score))
            result_lines.append("")

        # Level 2: Citations of the best Level 1 citations
        if max_depth >= 2:
            # Pick the most relevant Level 1 citations to follow deeper
            # Combine forward + backward, take top N by score
            all_level1 = top_fwd + top_bwd
            all_level1.sort(key=lambda x: x[1], reverse=True)
            level1_to_follow = [
                (c, score) for c, score in all_level1[:max_per_level]
                if score > 0 or not keywords_lower  # Follow all if no keywords given
            ]

            if level1_to_follow:
                result_lines.append(f"### Level 2: Citations-of-Citations ({len(level1_to_follow)} Level 1 patents explored)")
                result_lines.append("")

                seen_level2: set[str] = set()  # Deduplicate across Level 2

                for c, l1_score in level1_to_follow:
                    l1_pub = c.get("publication_number", "?")
                    try:
                        l2_citations = _derwent_citation_search(l1_pub)
                        if isinstance(l2_citations, dict) and "error" in l2_citations:
                            continue
                        if isinstance(l2_citations, list):
                            l2_citations = l2_citations[0] if l2_citations else {}
                        l2_fwd = l2_citations.get("forward_citations", [])
                        l2_bwd = l2_citations.get("backward_citations", [])

                        # Score and pick top from Level 2
                        scored_l2 = [(c2, _keyword_score(c2)) for c2 in l2_fwd + l2_bwd]
                        scored_l2.sort(key=lambda x: x[1], reverse=True)
                        top_l2 = [
                            (c2, s) for c2, s in scored_l2[:max_per_level]
                            if c2.get("publication_number", "") not in seen_level2
                            and c2.get("publication_number", "") != seed_patent
                        ]

                        if top_l2:
                            result_lines.append(f"#### Via {l1_pub} (L1 score: {l1_score})")
                            for j, (c2, s2) in enumerate(top_l2, 1):
                                pub2 = c2.get("publication_number", "")
                                seen_level2.add(pub2)
                                result_lines.extend(_format_citation(c2, "  ", j, s2))
                            result_lines.append("")

                    except Exception as e:
                        LOGGER.warning("Level 2 citation lookup failed for %s: %s", l1_pub, e)

                if not seen_level2:
                    result_lines.append("*No additional relevant citations found at Level 2.*")
                    result_lines.append("")
            else:
                result_lines.append("### Level 2: Skipped")
                result_lines.append("*No Level 1 citations matched feature keywords — nothing to follow deeper.*")
                result_lines.append("")

        return "\n".join(result_lines)

    except Exception as e:
        LOGGER.error("Citation chain search failed for %s: %s", seed_patent, e)
        return f"Citation chain search error: {str(e)}"


# =============================================================================
# Batch Search Tools
# =============================================================================

@tool
@retry_with_backoff(max_retries=3, base_delay=2.0)
def batch_patent_search(
    queries: Annotated[list[dict], "List of query dicts with query_id, query_text, feature_ids"],
    max_results_per_query: Annotated[int, "Max results per query"] = 10,
) -> str:
    """Execute multiple patent keyword searches in batch via Derwent.

    More efficient than calling patent_keyword_search multiple times.

    Query format:
    [
        {"query_id": "K1.1", "query_text": "CTB=(term NEAR5 term);", "feature_ids": ["F1"]},
        {"query_id": "K1.2", "query_text": "ALL=(term AND term);", "feature_ids": ["F1", "F2"]},
    ]

    Args:
        queries: List of query dictionaries
        max_results_per_query: Max patents per query

    Returns:
        Consolidated results from all queries
    """
    try:
        from src.tools.clients.derwent import _derwent_fld_search
    except ImportError:
        return "[MOCK] Batch patent search: Derwent API client not available."

    all_results = []
    seen_patents = set()

    for q in queries:
        query_id = q.get("query_id", "unknown")
        query_text = q.get("query_text", "")
        feature_ids = q.get("feature_ids", [])

        try:
            patents = _derwent_fld_search(query_text, size=max_results_per_query)

            if isinstance(patents, str):
                all_results.append(f"- {query_id}: ERROR - {patents[:50]}")
                continue

            new_count = 0
            for p in patents:
                pub_num = p.get("publication_number", "")
                if pub_num and pub_num not in seen_patents:
                    seen_patents.add(pub_num)
                    new_count += 1

            all_results.append(f"- {query_id}: {len(patents)} results ({new_count} new)")

        except Exception as e:
            all_results.append(f"- {query_id}: ERROR - {str(e)[:50]}")
    
    summary = [
        "## Batch Patent Search Results",
        f"**Total Queries**: {len(queries)}",
        f"**Unique Patents Found**: {len(seen_patents)}",
        "",
        "### Per-Query Results",
    ]
    summary.extend(all_results)
    
    # Gentle think_tool reminder
    summary.append("")
    summary.append("---")
    summary.append("💡 *Tip: Use think_tool to reflect on these results before your next action.*")
    
    return "\n".join(summary)


@tool
@retry_with_backoff(max_retries=3, base_delay=2.0)
def batch_npl_search(
    queries: Annotated[list[dict], "List of query dicts with query_id, query_text, feature_ids"],
    max_results_per_query: Annotated[int, "Max results per query"] = 10,
    from_year: Annotated[Optional[int], "Filter by start year"] = None,
    to_year: Annotated[Optional[int], "Filter by end year"] = None,
) -> str:
    """Execute multiple NPL searches in batch.
    
    Query format:
    [
        {"query_id": "NQP-1.1", "query_text": "TS=(term1 AND term2)", "feature_ids": ["F1"]},
        {"query_id": "NQP-1.2", "query_text": "TI=(term) AND AB=(term)", "feature_ids": ["F2"]},
    ]
    
    Args:
        queries: List of query dictionaries
        max_results_per_query: Max articles per query
        from_year: Optional start year filter
        to_year: Optional end year filter
        
    Returns:
        Consolidated results from all queries
    """
    all_results = []
    seen_articles = set()
    
    for q in queries:
        query_id = q.get("query_id", "unknown")
        query_text = q.get("query_text", "")
        
        if not CLIENTS_AVAILABLE:
            all_results.append(f"- {query_id}: [MOCK] 0 results (API not configured)")
            continue
        
        try:
            client = WOSClient()
            articles = client.npl_search(query_text, max_results_per_query, from_year, to_year)
            
            new_count = 0
            for a in articles:
                if a.wos_number not in seen_articles:
                    seen_articles.add(a.wos_number)
                    new_count += 1
            
            all_results.append(f"- {query_id}: {len(articles)} results ({new_count} new)")
            
        except Exception as e:
            all_results.append(f"- {query_id}: ERROR - {str(e)[:50]}")
    
    summary = [
        "## Batch NPL Search Results",
        f"**Total Queries**: {len(queries)}",
        f"**Unique Articles Found**: {len(seen_articles)}",
        "",
        "### Per-Query Results",
    ]
    summary.extend(all_results)
    
    # Gentle think_tool reminder
    summary.append("")
    summary.append("---")
    summary.append("💡 *Tip: Use think_tool to reflect on these results before your next action.*")
    
    return "\n".join(summary)


@tool
@retry_with_backoff(max_retries=3, base_delay=2.0)
def batch_semantic_search(
    queries: Annotated[list[dict], "List of query dicts with query_id, query_text, feature_ids"],
    max_results_per_query: Annotated[int, "Max results per query"] = 20,
) -> str:
    """Execute multiple semantic searches in batch.
    
    ⭐ SEMANTIC SEARCH IS ESSENTIAL! Include 3-5 per cycle!
    
    Query format:
    [
        {"query_id": "S1.1", "query_text": "UV fluorescence for polymer detection", "feature_ids": ["F1"]},
        {"query_id": "S1.2", "query_text": "Inline quality control for plastic pellets", "feature_ids": ["F2"]},
    ]
    
    Args:
        queries: List of query dictionaries (natural language, NO Boolean!)
        max_results_per_query: Max patents per query
        
    Returns:
        Consolidated results from all queries
    """
    all_results = []
    seen_patents = set()
    
    for q in queries:
        query_id = q.get("query_id", "unknown")
        query_text = q.get("query_text", "")
        
        if not CLIENTS_AVAILABLE:
            all_results.append(f"- {query_id}: [MOCK] 0 results (API not configured)")
            continue
        
        try:
            client = NGSPClient()
            patents = client.semantic_search(query_text, max_results_per_query)
            
            new_count = 0
            for p in patents:
                if p.publication_number not in seen_patents:
                    seen_patents.add(p.publication_number)
                    new_count += 1
            
            all_results.append(f"- {query_id}: {len(patents)} results ({new_count} new)")
            
        except Exception as e:
            all_results.append(f"- {query_id}: ERROR - {str(e)[:50]}")
    
    summary = [
        "## Batch Semantic Search Results",
        f"**Total Queries**: {len(queries)}",
        f"**Unique Patents Found**: {len(seen_patents)}",
        "",
        "### Per-Query Results",
    ]
    summary.extend(all_results)
    
    # Gentle think_tool reminder
    summary.append("")
    summary.append("---")
    summary.append("💡 *Tip: Use think_tool to reflect on these results before your next action.*")
    
    return "\n".join(summary)


@tool
def batch_unified_search(
    patent_queries: Annotated[list[dict], "Patent keyword queries with @(field) syntax"] = [],
    npl_queries: Annotated[list[dict], "NPL queries with TS=/TI=/AB= syntax"] = [],
    semantic_queries: Annotated[list[dict], "Semantic queries in natural language"] = [],
    max_results_per_query: Annotated[int, "Max results per query"] = 10,
    from_year: Annotated[Optional[int], "NPL start year filter"] = None,
    to_year: Annotated[Optional[int], "NPL end year filter"] = None,
) -> str:
    """Execute patent, NPL, and semantic searches in a single batch.
    
    MOST EFFICIENT! Use this instead of separate batch calls.
    
    ⭐ ALWAYS include semantic_queries! Minimum 3-5 per cycle!
    
    Query formats:
    - patent_queries: [{"query_id": "K1.1", "query_text": "CTB=(terms);", "feature_ids": ["F1"]}]
    - npl_queries: [{"query_id": "NQP-1.1", "query_text": "TS=(...)", "feature_ids": ["F1"]}]
    - semantic_queries: [{"query_id": "S1.1", "query_text": "Natural language...", "feature_ids": ["F1"]}]
    
    Args:
        patent_queries: Innography keyword queries
        npl_queries: Web of Science queries
        semantic_queries: Natural language semantic queries
        max_results_per_query: Max results per query
        from_year: NPL start year
        to_year: NPL end year
        
    Returns:
        Consolidated results from all search types
    """
    # Ensure we have lists even if None is passed
    patent_queries = patent_queries if patent_queries is not None else []
    npl_queries = npl_queries if npl_queries is not None else []
    semantic_queries = semantic_queries if semantic_queries is not None else []
    
    results = ["# Unified Batch Search Results", ""]
    
    # Patent searches
    if patent_queries:
        results.append("## Patent Keyword Searches")
        seen = set()
        for q in patent_queries:
            query_id = q.get("query_id", "unknown")
            query_text = q.get("query_text", "")
            
            try:
                from src.tools.clients.derwent import _derwent_fld_search
                patents = _derwent_fld_search(query_text, size=max_results_per_query)
                if isinstance(patents, str):
                    results.append(f"- {query_id}: ERROR - {patents[:50]}")
                    continue
                new_count = sum(1 for p in patents if p.get("publication_number", "") not in seen)
                seen.update(p.get("publication_number", "") for p in patents)
                results.append(f"- {query_id}: {len(patents)} results ({new_count} new)")
            except Exception as e:
                results.append(f"- {query_id}: ERROR - {str(e)[:50]}")

        results.append(f"\n**Total unique patents**: {len(seen)}\n")
    
    # NPL searches
    from src.config.settings import is_npl_enabled
    if npl_queries and not is_npl_enabled():
        results.append("## NPL Searches\n*NPL search is disabled (enable_npl_search=False)*\n")
        npl_queries = []
    if npl_queries:
        results.append("## NPL Searches")
        seen = set()
        for q in npl_queries:
            query_id = q.get("query_id", "unknown")
            query_text = q.get("query_text", "")
            
            if not CLIENTS_AVAILABLE:
                results.append(f"- {query_id}: [MOCK] (API not configured)")
                continue
            
            try:
                client = WOSClient()
                articles = client.npl_search(query_text, max_results_per_query, from_year, to_year)
                new_count = sum(1 for a in articles if a.wos_number not in seen)
                seen.update(a.wos_number for a in articles)
                results.append(f"- {query_id}: {len(articles)} results ({new_count} new)")
            except Exception as e:
                results.append(f"- {query_id}: ERROR - {str(e)[:50]}")
        
        results.append(f"\n**Total unique articles**: {len(seen)}\n")
    
    # Semantic searches
    if semantic_queries:
        results.append("## Semantic Searches")
        seen = set()
        for q in semantic_queries:
            query_id = q.get("query_id", "unknown")
            query_text = q.get("query_text", "")
            
            if not CLIENTS_AVAILABLE:
                results.append(f"- {query_id}: [MOCK] (API not configured)")
                continue
            
            try:
                client = NGSPClient()
                patents = client.semantic_search(query_text, max_results_per_query)
                new_count = sum(1 for p in patents if p.publication_number not in seen)
                seen.update(p.publication_number for p in patents)
                results.append(f"- {query_id}: {len(patents)} results ({new_count} new)")
            except Exception as e:
                results.append(f"- {query_id}: ERROR - {str(e)[:50]}")
        
        results.append(f"\n**Total unique patents (semantic)**: {len(seen)}\n")
    
    # Summary
    results.append("---")
    results.append("## Summary")
    results.append(f"- Patent queries executed: {len(patent_queries)}")
    results.append(f"- NPL queries executed: {len(npl_queries)}")
    results.append(f"- Semantic queries executed: {len(semantic_queries)}")
    
    if not semantic_queries:
        results.append("\n⚠️ **WARNING**: No semantic queries included! Add 3-5 for better coverage.")
    
    # Gentle think_tool reminder
    results.append("")
    results.append("---")
    results.append("💡 *Tip: Use think_tool to reflect on these results before your next action.*")
    
    return "\n".join(results)


# =============================================================================
# Search Logging Tool
# =============================================================================

@tool
def log_search_execution(
    query_id: Annotated[str, "Unique query ID (e.g., K1.1, NQP-1.2, S1.1)"],
    query_text: Annotated[str, "The actual query string executed"],
    source: Annotated[str, "Source database: 'derwent', 'wos', or 'ngsp'"],
    query_type: Annotated[str, "Type: 'keyword', 'npl', or 'semantic'"],
    results_returned: Annotated[int, "Number of results returned by the query"],
    feature_ids: Annotated[list[str], "Feature IDs this query targeted"] = [],
) -> str:
    """Log a search query execution for statistics tracking.

    IMPORTANT: Call this tool after each search to track statistics.
    The orchestrator uses this log to report:
    - Total documents searched
    - Documents by source
    - Query counts

    Example:
        After running a patent search that returned 25 results:
        log_search_execution(
            query_id="K1.1",
            query_text="CTB=(polymer NEAR5 UV);",
            source="derwent",
            query_type="keyword",
            results_returned=25,
            feature_ids=["F1", "F2"]
        )
    
    Args:
        query_id: Unique identifier for this query
        query_text: The query string
        source: Database source
        query_type: Type of search
        results_returned: Number of results
        feature_ids: Features targeted
        
    Returns:
        Confirmation message with logged data
    """
    from datetime import datetime
    
    log_entry = {
        "query_id": query_id,
        "query_text": query_text,
        "source": source,
        "query_type": query_type,
        "results_returned": results_returned,
        "feature_ids": feature_ids,
        "timestamp": datetime.now().isoformat(),
    }
    
    return f"""✅ Search logged:
- Query ID: {query_id}
- Source: {source} ({query_type})
- Results: {results_returned}
- Features: {', '.join(feature_ids) if feature_ids else 'N/A'}

**NOTE**: This log entry will be added to search_queries_log in state for final statistics."""


@tool
def log_batch_search_execution(
    searches: Annotated[list[dict], "List of search log entries with query_id, source, query_type, results_returned"],
) -> str:
    """Log multiple search executions at once.
    
    More efficient than calling log_search_execution multiple times.
    Call this after batch_unified_search or similar batch operations.
    
    Each entry should have:
    - query_id: str
    - query_text: str  
    - source: str (derwent/wos/ngsp)
    - query_type: str (keyword/npl/semantic)
    - results_returned: int
    - feature_ids: list[str] (optional)

    Example:
        log_batch_search_execution(searches=[
            {"query_id": "K1.1", "source": "derwent", "query_type": "keyword", "results_returned": 15, "feature_ids": ["F1"]},
            {"query_id": "NQP-1.1", "source": "wos", "query_type": "npl", "results_returned": 8, "feature_ids": ["F1"]},
            {"query_id": "S1.1", "source": "ngsp", "query_type": "semantic", "results_returned": 20, "feature_ids": ["F1", "F2"]},
        ])
    
    Args:
        searches: List of search log entries
        
    Returns:
        Summary of logged searches
    """
    from datetime import datetime
    
    timestamp = datetime.now().isoformat()
    
    total_patents = 0
    total_npl = 0
    
    lines = ["✅ Batch search logged:", ""]
    
    for entry in searches:
        query_id = entry.get("query_id", "unknown")
        source = entry.get("source", "unknown")
        query_type = entry.get("query_type", "keyword")
        results = entry.get("results_returned", 0)
        
        if source in ("derwent", "innography", "ngsp") or query_type in ("keyword", "semantic"):
            total_patents += results
        elif source == "wos" or query_type == "npl":
            total_npl += results
        
        lines.append(f"- {query_id}: {results} results ({source}/{query_type})")
    
    lines.extend([
        "",
        f"**Total logged**: {len(searches)} queries",
        f"**Patents searched**: {total_patents}",
        f"**NPL searched**: {total_npl}",
        "",
        "These entries will be added to search_queries_log for final statistics.",
    ])
    
    return "\n".join(lines)
