"""Findings persistence tools for the Novelty Checker deep agent.

This module provides tools for persisting and retrieving research findings
across conversation turns, preventing memory loss due to context truncation.

Phase 3 of the Findings Persistence Implementation:
- save_round_findings: Persist findings from a research round
- get_all_findings: Recall all accumulated findings
- get_coverage_gaps: Identify features needing more research

These tools work with the FilesystemBackend to write/read findings files,
ensuring findings survive even in very long research sessions.
"""

import json
import logging
import threading
from datetime import datetime
from typing import Any, Literal, Optional

from langchain_core.tools import tool

# Phase 1: Import backend protocol for direct writes
try:
    from deepagents.backends.protocol import BackendProtocol
except ImportError:
    BackendProtocol = None  # Fallback for testing without deepagents

_logger = logging.getLogger(__name__)

# Module-level lock for JSON accumulator writes. Must be shared across ALL
# calls to create_backend_findings_tools() so concurrent subagents serialise
# their read-modify-write operations on findings_accumulator.json.
_accumulator_lock = threading.Lock()


# =============================================================================
# File Paths (relative to FilesystemBackend root)
# =============================================================================

SCOPE_FILE = "/scope.md"
FEATURES_FILE = "/features.md"
FINDINGS_DIR = "/findings"
ACCUMULATOR_FILE = "/findings_accumulator.json"
REFERENCES_FILE = "/references.md"


# =============================================================================
# Helper Functions
# =============================================================================

def _format_references_table(references: list[dict]) -> str:
    """Format references as a markdown table."""
    if not references:
        return "*No references found*"
    
    lines = [
        "| Publication # | Title | Relevance | Features | Priority/Year |",
        "|--------------|-------|-----------|----------|---------------|",
    ]
    
    for ref in references:
        pub_num = ref.get("publication_number", ref.get("ref_id", "N/A"))
        title = ref.get("title", "N/A")[:50]  # Truncate long titles
        relevance = ref.get("relevance", ref.get("triage_label", "?"))
        features = ", ".join(ref.get("features", []))
        date = ref.get("priority_date", ref.get("pub_year", "N/A"))
        lines.append(f"| {pub_num} | {title} | {relevance} | {features} | {date} |")
    
    return "\n".join(lines)


def _format_coverage_table(coverage: dict[str, dict]) -> str:
    """Format coverage status as a markdown table."""
    if not coverage:
        return "*No coverage data*"
    
    lines = [
        "| Feature | Level | A-Refs | B-Refs | Target Met? |",
        "|---------|-------|--------|--------|-------------|",
    ]
    
    for feature_id, status in coverage.items():
        level = status.get("level", "none").upper()
        a_refs = status.get("a_refs", 0)
        b_refs = status.get("b_refs", 0)
        is_core = status.get("is_core", False)
        target = "STRONG" if is_core else "MODERATE"
        
        # Determine if target met
        level_order = {"none": 0, "weak": 1, "moderate": 2, "strong": 3, "saturated": 4}
        target_order = {"MODERATE": 2, "STRONG": 3}
        met = "✅" if level_order.get(level.lower(), 0) >= target_order.get(target, 2) else "❌"
        
        core_marker = " (Core)" if is_core else ""
        lines.append(f"| {feature_id}{core_marker} | {level} | {a_refs} | {b_refs} | {met} |")
    
    return "\n".join(lines)


def _format_vocabulary_list(vocabulary: list[dict] | list[str]) -> str:
    """Format vocabulary terms as a markdown list."""
    if not vocabulary:
        return "*No vocabulary discovered*"
    
    lines = []
    for item in vocabulary:
        if isinstance(item, dict):
            term = item.get("term", str(item))
            source = item.get("source_ref", "")
            relevance = item.get("relevance", "")
            source_str = f" (from {source})" if source else ""
            relevance_str = f" — {relevance}" if relevance else ""
            lines.append(f"- **{term}**{source_str}{relevance_str}")
        else:
            lines.append(f"- {item}")
    
    return "\n".join(lines)


# =============================================================================
# Findings Persistence Tools
# =============================================================================

@tool(parse_docstring=True)
def save_round_findings(
    round_number: int,
    source: Literal["patent", "npl", "semantic", "citation", "all"],
    references: list[dict] | None = None,
    coverage_update: dict[str, dict] | None = None,
    vocabulary: list[dict] | None = None,
    gap_features: list[str] | None = None,
    recommended_queries: dict[str, str | list[str]] | None = None,
    citation_analysis: dict[str, Any] | None = None,
    backend: Any = None,  # Phase 1: Injected by deepagents runtime (Any type for JSON schema compatibility)
) -> str:
    """Save findings from a research round to persistent storage.
    
    This tool ensures findings survive context truncation by writing
    structured data to the filesystem. Call this AFTER each search
    to preserve your work.
    
    Args:
        round_number: The research round number (1, 2, 3, ...)
        source: Source of findings - "patent", "npl", "semantic", "citation", or "all" for combined
        references: Optional list of reference dicts with publication_number, title, relevance, features, priority_date
        coverage_update: Optional coverage status per feature as dict of feature_id to status dict
        vocabulary: Optional list of discovered vocabulary term dicts
        gap_features: Optional list of feature IDs still needing coverage
        recommended_queries: Optional dict of suggested queries for next round by search type (string or list of strings)
        citation_analysis: Optional dict with citation-specific metadata including a_refs_analyzed, forward_relevant, backward_relevant, seed_patents
    
    Returns:
        Confirmation message with the file path where findings were saved
    
    Example:
        save_round_findings(
            round_number=1,
            source="patent",
            references=[
                {"publication_number": "US10234567B2", "title": "Flow valve", 
                 "relevance": "A", "features": ["F1", "F3"], "priority_date": "2020-01-15"}
            ],
            coverage_update={
                "F1": {"level": "strong", "a_refs": 1, "b_refs": 2, "is_core": True},
                "F2": {"level": "weak", "a_refs": 0, "b_refs": 1, "is_core": True}
            },
            gap_features=["F2"],
            recommended_queries={"patent": "@(dwpi_novelty) flow control"}
        )
    """
    timestamp = datetime.now().isoformat()
    
    # Handle optional references
    refs_count = len(references) if references else 0
    refs_table = _format_references_table(references) if references else "*No references provided this round*"
    
    # Handle optional coverage
    coverage_table = _format_coverage_table(coverage_update) if coverage_update else "*No coverage update provided*"
    
    # Build the findings markdown
    findings_md = f"""# Research Round {round_number} - {source.upper()} Findings

**Timestamp**: {timestamp}
**Source**: {source}

## References Found ({refs_count} total)

{refs_table}

## Coverage Status After This Round

{coverage_table}

"""
    
    # Add vocabulary section if provided (semantic search)
    if vocabulary:
        findings_md += f"""## Vocabulary Discovered

{_format_vocabulary_list(vocabulary)}

"""
    
    # Add gap analysis if provided
    if gap_features:
        findings_md += f"""## Features Still Needing Coverage

{', '.join(gap_features)}

"""
    
    # Add recommended queries if provided
    if recommended_queries:
        findings_md += """## Recommended Queries for Next Round

"""
        for search_type, query in recommended_queries.items():
            # Handle both single string and list of strings
            if isinstance(query, list):
                findings_md += f"### {search_type.upper()}\n"
                for i, q in enumerate(query, 1):
                    findings_md += f"{i}. `{q}`\n"
                findings_md += "\n"
            else:
                findings_md += f"- **{search_type}**: `{query}`\n"
    
    # Add citation analysis section if provided
    if citation_analysis:
        a_refs_analyzed = citation_analysis.get("a_refs_analyzed", 0)
        forward_relevant = citation_analysis.get("forward_relevant", 0)
        backward_relevant = citation_analysis.get("backward_relevant", 0)
        seed_patents = citation_analysis.get("seed_patents", [])
        total_scanned = citation_analysis.get("total_scanned", 0)
        
        findings_md += f"""## Citation Analysis Results

- **A-refs analyzed**: {a_refs_analyzed}
- **Seed patents**: {', '.join(seed_patents) if seed_patents else 'N/A'}
- **Total citations scanned**: {total_scanned}
- **Forward citations relevant**: {forward_relevant}
- **Backward citations relevant**: {backward_relevant}
- **New references from citations**: {forward_relevant + backward_relevant}

"""
    
    # Determine file path
    if source == "all":
        file_path = f"{FINDINGS_DIR}/round_{round_number}.md"
    elif source == "citation":
        file_path = f"{FINDINGS_DIR}/citations_round_{round_number}.md"
    else:
        file_path = f"{FINDINGS_DIR}/{source}_round_{round_number}.md"

    # Phase 1: Write directly to backend (no extra agent step needed)
    if backend is None:
        _logger.warning("Backend not available - returning content for manual save")
        return f"""⚠️ Backend not available. Findings prepared but not saved.

**To save these findings manually, call write_file with:**
- Path: `{file_path}`
- Content: (see below)

---
{findings_md}
---"""

    # Write directly to filesystem via backend
    try:
        # Ensure findings directory exists
        backend.mkdir(FINDINGS_DIR)

        # Write findings file
        backend.write(file_path, findings_md)

        _logger.info(f"✅ Findings saved to {file_path}")

        return f"""✅ Findings saved to `{file_path}`

**Summary:**
- **Round**: {round_number}
- **Source**: {source}
- **References**: {refs_count}
- **Coverage updates**: {len(coverage_update) if coverage_update else 0} features
- **Vocabulary terms**: {len(vocabulary) if vocabulary else 0}

💡 **Next**: Call `get_all_findings()` to recall this data in the next round."""

    except Exception as e:
        _logger.error(f"Failed to save findings: {e}")
        return f"❌ Failed to save findings to {file_path}: {e}"


@tool(parse_docstring=True)
def get_all_findings() -> str:
    """Retrieve all accumulated findings from previous research rounds.
    
    Use this tool at the START of each research round to recall what has
    been found so far. This prevents:
    - Duplicate searches for already-covered features
    - Forgetting A/B references found in earlier rounds
    - Losing vocabulary discoveries from semantic search
    
    Returns:
        Markdown summary of all accumulated findings including:
        - Invention scope summary
        - Features being searched
        - References by round (with publication numbers)
        - Current coverage status per feature
        - Discovered vocabulary terms
        - Identified gaps needing more research
    
    Note:
        This tool reads from the filesystem. If no findings exist yet,
        it returns instructions to start fresh.
    
    Example usage in orchestrator:
        # At start of round 2:
        findings = get_all_findings()
        # Now you know what was found in round 1 and can target gaps
    """
    # Note: In actual use, this reads from files via FilesystemBackend
    # For now, return instructions for the agent to use read_file
    
    return f"""📚 **To recall all previous findings, read these files:**

1. **Scope**: `read_file("{SCOPE_FILE}")`
   - Original invention description
   - Confirmed scope from Gate 1

2. **Features**: `read_file("{FEATURES_FILE}")`
   - Feature definitions (F1, F2, etc.)
   - Core vs non-core designation

3. **Round Findings**: `read_file("{FINDINGS_DIR}/round_*.md")`
   - References found per round
   - Coverage snapshots
   - Vocabulary discovered

4. **Master Reference List**: `read_file("{REFERENCES_FILE}")`
   - Deduplicated list of ALL references
   - Feature coverage mapping

5. **Structured Accumulator**: `read_file("{ACCUMULATOR_FILE}")`
   - JSON format for programmatic access
   - Complete history with timestamps

💡 **Quick Check**: Use `ls("{FINDINGS_DIR}")` to see which rounds have been saved.

⚠️ **If files don't exist**: This is round 1 - start fresh by searching and saving findings!"""


@tool(parse_docstring=True)
def get_coverage_gaps() -> str:
    """Identify features that still need more references to reach target coverage.
    
    Analyzes the current findings to determine which features have
    insufficient coverage and suggests targeted search strategies.
    
    Coverage Targets:
    - Core features (is_core=True): MUST reach STRONG (1+ A-ref AND 2+ B-refs)
    - Non-core features: Should reach MODERATE (2+ B-refs OR 1 A-ref)
    - Overall target: 70% of features at STRONG or better
    
    Returns:
        Analysis of coverage gaps including:
        - Features below target with current levels
        - What's needed to reach target (e.g., "needs 1 more A-ref")
        - Suggested query strategies per gap feature
    
    Example output:
        ## Coverage Gap Analysis
        
        ### Core Features Below STRONG
        - F2 (WEAK): Has 0 A-refs, 1 B-ref. Needs: 1 A-ref + 1 B-ref
          Suggestion: Try semantic search with mechanism description
        
        ### Non-Core Features Below MODERATE  
        - F5 (NONE): Has 0 refs. Needs: 1 A-ref OR 2 B-refs
          Suggestion: Broaden keyword terms
    
    Note:
        This tool analyzes the current state. First call get_all_findings()
        to ensure you have the latest data, then call this for gap analysis.
    """
    return f"""🔍 **To analyze coverage gaps:**

1. First, read current coverage from findings:
   ```
   read_file("{ACCUMULATOR_FILE}")
   ```
   
2. Or manually check the latest round's coverage table:
   ```
   ls("{FINDINGS_DIR}")
   read_file("{FINDINGS_DIR}/round_N.md")  # N = latest round
   ```

3. Then analyze using this template:

---

## Coverage Gap Analysis Template

### Current Status
| Feature | Core? | Current Level | Target | Gap? |
|---------|-------|---------------|--------|------|
| F1 | Y | [level] | STRONG | [YES/NO] |
| F2 | Y | [level] | STRONG | [YES/NO] |
| ... | | | | |

### Core Features Below STRONG (Priority!)
For each core feature not at STRONG:
- **[Feature ID]** ([level]): Has X A-refs, Y B-refs
  - **Needs**: [what's missing to reach STRONG]
  - **Suggested Patent Query**: `@(dwpi_title,dwpi_abstract) [terms]`
  - **Suggested NPL Query**: `TS=([terms])`
  - **Suggested Semantic Gist**: "[natural language description]"

### Non-Core Features Below MODERATE
For each non-core feature not at MODERATE:
- **[Feature ID]** ([level]): Has X A-refs, Y B-refs
  - **Needs**: [what's missing to reach MODERATE]
  - **Suggested Query**: [approach]

### Recommendation
[CONTINUE searching / STOP - coverage sufficient]

---

💡 **Use think_tool** after analyzing gaps to record your decision!"""


@tool(parse_docstring=True)
def summarize_findings_for_report() -> str:
    """Generate a summary of all findings suitable for the final report.
    
    Use this tool when transitioning from research to report synthesis.
    It provides a consolidated view of all findings in the format needed
    for the 11-section novelty report.
    
    Returns:
        Structured summary including:
        - Total references found (A, B, C breakdown)
        - Coverage achieved per feature
        - Key findings highlights
        - References for Feature Matrix (Section 4)
        - X-category references (anticipatory)
    
    Note:
        Call this BEFORE writing the final report to ensure all findings
        from all rounds are included.
    """
    return f"""📝 **To summarize findings for the final report:**

1. **Read ALL findings files:**
   ```
   read_file("{SCOPE_FILE}")
   read_file("{FEATURES_FILE}")
   read_file("{REFERENCES_FILE}")
   read_file("{ACCUMULATOR_FILE}")
   ```

2. **Generate summary using this template:**

---

## Findings Summary for Report

### Search Statistics
- Total research rounds: [N]
- Total references screened: [X]
- A-level references: [count]
- B-level references: [count]
- C-level references: [count]
- X-category (anticipatory): [count]

### Coverage Achieved
| Feature | Final Level | A-Refs | B-Refs | Target Met? |
|---------|-------------|--------|--------|-------------|
| F1 | STRONG | 2 | 4 | ✅ |
| ... | | | | |

**Overall Coverage**: [X]% at STRONG or better
**Target**: 70%
**Status**: [MET / NOT MET]

### Key Findings
1. [Most significant A-ref and what it teaches]
2. [Second most significant finding]
3. [Notable gap or novel aspect identified]

### Feature Matrix Data (Section 4)
[Table of all A and B refs with feature coverage mapping]

### X-Category References
[List any refs where ALL core features have Y coverage]

---

💡 **Now use write_file to save the final report to `/final_report.md`**"""


@tool(parse_docstring=True)
def detect_diminishing_returns(
    threshold: int = 2,
    lookback_rounds: int = 2,
    backend: Any = None,  # Phase 2: Injected by runtime (Any type for JSON schema compatibility)
) -> str:
    """Automatically detect diminishing returns in research progress.

    Analyzes recent research rounds to check if new reference discovery
    is declining below the threshold, indicating searches are yielding
    diminishing results.

    This tool removes the burden of manual tracking from the agent,
    providing automated recommendations on whether to continue or stop.

    Args:
        threshold: Minimum new refs per round to continue (default 2)
        lookback_rounds: Number of recent rounds to analyze (default 2)
        backend: FilesystemBackend injected by deepagents runtime

    Returns:
        Assessment with recommendation to CONTINUE or STOP, including:
        - Recent round statistics
        - Average new references per round
        - Threshold comparison
        - Actionable recommendation

    Example:
        detect_diminishing_returns(threshold=3, lookback_rounds=2)
        # Returns: "⚠️ DIMINISHING RETURNS DETECTED - Recommend STOP"
        #   if last 2 rounds found < 3 new refs each
    """
    try:
        # Load findings accumulator from filesystem
        if backend is None:
            return """ℹ️ Backend not available - cannot access findings accumulator.

**To manually check diminishing returns:**
1. Read `/findings_accumulator.json`
2. Check `rounds` array for `new_refs_count` in last {lookback_rounds} rounds
3. If all rounds have < {threshold} new refs → STOP
4. Otherwise → CONTINUE"""

        # `read_json_from_backend` handles FilesystemBackend.read() quirks
        # (line-number prefixes + "Error: ..." string on missing file). Without
        # it, this tool returned "no round data available" on every call,
        # so diminishing-returns detection never fired after round 1.
        from src.novelty_checker.middleware._backend_utils import read_json_from_backend
        accumulator_data = read_json_from_backend(backend, ACCUMULATOR_FILE)

        if not accumulator_data or "rounds" not in accumulator_data:
            return """ℹ️ No round data available for diminishing returns analysis.

**Possible reasons:**
- First research round (no history yet)
- Findings accumulator not yet created
- No rounds saved with `save_round_findings()`

**Recommendation:** CONTINUE with current round."""

        rounds = accumulator_data["rounds"]

        if len(rounds) < lookback_rounds:
            return f"""ℹ️ Not enough rounds for analysis.

**Current rounds:** {len(rounds)}
**Required:** {lookback_rounds}

**Recommendation:** CONTINUE - need more data to detect trends."""

        # Analyze last N rounds
        recent_rounds = rounds[-lookback_rounds:]
        recent_new_refs = [r.get("new_refs_count", 0) for r in recent_rounds]

        # Check if all recent rounds below threshold
        if all(count < threshold for count in recent_new_refs):
            avg_new_refs = sum(recent_new_refs) / len(recent_new_refs)

            round_details = "\n".join(
                f"- Round {r['round_number']}: {r.get('new_refs_count', 0)} new refs"
                for r in recent_rounds
            )

            return f"""⚠️ **DIMINISHING RETURNS DETECTED**

**Last {lookback_rounds} rounds:**
{round_details}

**Average new refs:** {avg_new_refs:.1f} refs/round
**Threshold:** {threshold} refs/round

**Analysis:**
All recent rounds found fewer than {threshold} new references, indicating
that continued searching is unlikely to yield significant new prior art.

**Recommendation:** STOP - Searches are yielding diminishing results.

💡 **Next steps:**
1. Review current coverage with `get_coverage_gaps()`
2. If coverage targets met → proceed to report writing
3. If gaps remain → consider citation analysis on A-refs instead of more searches"""

        else:
            avg_new_refs = sum(recent_new_refs) / len(recent_new_refs)

            return f"""✅ **Progress Healthy - CONTINUE**

**Last {lookback_rounds} rounds:** {recent_new_refs} new refs
**Average:** {avg_new_refs:.1f} refs/round
**Threshold:** {threshold} refs/round

**Analysis:**
Recent rounds are still finding new references at an acceptable rate.
Continued searching is likely to improve coverage.

**Recommendation:** CONTINUE with next research round.

💡 **Tip:** Call this tool after each round to monitor progress automatically."""

    except Exception as e:
        _logger.error(f"Error in detect_diminishing_returns: {e}")
        return f"❌ Error detecting diminishing returns: {e}"


# =============================================================================
# Tool List for Registry
# =============================================================================

FINDINGS_TOOLS = [
    save_round_findings,
    get_all_findings,
    get_coverage_gaps,
    summarize_findings_for_report,
    detect_diminishing_returns,  # Phase 2: Auto-detection
]


def get_findings_tools() -> list:
    """Get all findings persistence tools.

    Returns:
        List of findings persistence tools
    """
    return FINDINGS_TOOLS


# =============================================================================
# Backend-Aware Tool Factory (deepagents ToolRuntime pattern)
# =============================================================================

def create_backend_findings_tools(backend: Any) -> list:
    """Create findings tools with proper backend injection via ToolRuntime.

    The deepagents framework auto-injects ``ToolRuntime`` as a parameter
    when tools are built with ``StructuredTool.from_function()``.  This
    factory creates versions of ``save_round_findings`` and
    ``detect_diminishing_returns`` that resolve the backend from the
    runtime context — supporting both static instances and callable
    factories (for per-thread session isolation).

    Args:
        backend: ``FilesystemBackend`` instance or
            ``BackendFactory`` callable (``Callable[[ToolRuntime], BackendProtocol]``).

    Returns:
        List of backend-aware ``BaseTool`` instances.
    """
    from langchain.tools import ToolRuntime
    from langchain_core.tools import BaseTool, StructuredTool
    from typing import Annotated

    def _resolve_backend(runtime: Any):
        if callable(backend):
            return backend(runtime)
        return backend

    # -----------------------------------------------------------------
    # save_round_findings (backend-aware)
    # -----------------------------------------------------------------

    def _save_round_findings(
        runtime: ToolRuntime,
        round_number: Annotated[int, "The research round number (1, 2, 3, ...)"],
        source: Annotated[str, "Source of findings: patent, npl, semantic, citation, or all"],
        references: Annotated[Optional[list[dict]], "List of reference dicts"] = None,
        coverage_update: Annotated[Optional[dict[str, dict]], "Coverage status per feature"] = None,
        vocabulary: Annotated[Optional[list[dict]], "Discovered vocabulary terms"] = None,
        gap_features: Annotated[Optional[list[str]], "Feature IDs still needing coverage"] = None,
        recommended_queries: Annotated[Optional[dict], "Suggested queries for next round"] = None,
        citation_analysis: Annotated[Optional[dict], "Citation-specific metadata"] = None,
    ) -> str:
        """Save findings from a research round to persistent storage."""
        resolved = _resolve_backend(runtime)
        timestamp = datetime.now().isoformat()

        refs_count = len(references) if references else 0
        refs_table = _format_references_table(references) if references else "*No references provided this round*"
        coverage_table = _format_coverage_table(coverage_update) if coverage_update else "*No coverage update provided*"

        findings_md = f"""# Research Round {round_number} - {source.upper()} Findings

**Timestamp**: {timestamp}
**Source**: {source}

## References Found ({refs_count} total)

{refs_table}

## Coverage Status After This Round

{coverage_table}

"""
        if vocabulary:
            findings_md += f"## Vocabulary Discovered\n\n{_format_vocabulary_list(vocabulary)}\n\n"

        if gap_features:
            findings_md += f"## Features Still Needing Coverage\n\n{', '.join(gap_features)}\n\n"

        if recommended_queries:
            findings_md += "## Recommended Queries for Next Round\n\n"
            for search_type, query in recommended_queries.items():
                if isinstance(query, list):
                    findings_md += f"### {search_type.upper()}\n"
                    for i, q in enumerate(query, 1):
                        findings_md += f"{i}. `{q}`\n"
                    findings_md += "\n"
                else:
                    findings_md += f"- **{search_type}**: `{query}`\n"

        if citation_analysis:
            a_refs_analyzed = citation_analysis.get("a_refs_analyzed", 0)
            forward_relevant = citation_analysis.get("forward_relevant", 0)
            backward_relevant = citation_analysis.get("backward_relevant", 0)
            seed_patents = citation_analysis.get("seed_patents", [])
            total_scanned = citation_analysis.get("total_scanned", 0)
            findings_md += f"""## Citation Analysis Results

- **A-refs analyzed**: {a_refs_analyzed}
- **Seed patents**: {', '.join(seed_patents) if seed_patents else 'N/A'}
- **Total citations scanned**: {total_scanned}
- **Forward citations relevant**: {forward_relevant}
- **Backward citations relevant**: {backward_relevant}
- **New references from citations**: {forward_relevant + backward_relevant}

"""

        if source == "all":
            file_path = f"{FINDINGS_DIR}/round_{round_number}.md"
        elif source == "citation":
            file_path = f"{FINDINGS_DIR}/citations_round_{round_number}.md"
        else:
            file_path = f"{FINDINGS_DIR}/{source}_round_{round_number}.md"

        try:
            resolved.write(file_path, findings_md)
            _logger.info(f"Findings saved to {file_path}")

            # --- Update JSON accumulator (feeds detect_diminishing_returns + CitationEnforcement) ---
            # Lock prevents concurrent subagents from overwriting each other's data
            with _accumulator_lock:
                try:
                    # Use the shared helper — strips FilesystemBackend's
                    # "<N>\t" line-number prefixes and handles "Error: ..."
                    # strings for missing files. Without it, every round
                    # silently reset accumulator to {}, wiping prior rounds.
                    from src.novelty_checker.middleware._backend_utils import (
                        read_json_from_backend,
                    )
                    accumulator = read_json_from_backend(resolved, ACCUMULATOR_FILE) or {}
                    if "rounds" not in accumulator:
                        accumulator = {"rounds": [], "all_references": [], "final_coverage": []}

                    accumulator["rounds"].append({
                        "round_number": round_number,
                        "source": source,
                        "timestamp": timestamp,
                        "new_refs_count": refs_count,
                    })

                    existing_pubs = {
                        (r.get("publication_number", "") or r.get("ref_id", "")
                         or r.get("pub_number", ""))
                        for r in accumulator.get("all_references", [])
                    }
                    for ref in (references or []):
                        pub = (ref.get("publication_number", "")
                               or ref.get("ref_id", "")
                               or ref.get("pub_number", ""))
                        if pub and pub not in existing_pubs:
                            accumulator["all_references"].append(ref)
                            existing_pubs.add(pub)

                    if coverage_update:
                        accumulator["final_coverage"] = [
                            {"feature_id": fid, "level": info.get("level", ""), **info}
                            for fid, info in coverage_update.items()
                        ]

                    resolved.write(ACCUMULATOR_FILE, json.dumps(accumulator, indent=2))
                except Exception as acc_err:
                    _logger.warning(f"Failed to update accumulator: {acc_err}")

            return f"""✅ Findings saved to `{file_path}`

**Summary:**
- **Round**: {round_number}
- **Source**: {source}
- **References**: {refs_count}
- **Coverage updates**: {len(coverage_update) if coverage_update else 0} features
- **Vocabulary terms**: {len(vocabulary) if vocabulary else 0}

💡 **Next**: Call `get_all_findings()` to recall this data in the next round."""
        except Exception as e:
            _logger.error(f"Failed to save findings: {e}")
            return f"❌ Failed to save findings to {file_path}: {e}"

    # -----------------------------------------------------------------
    # detect_diminishing_returns (backend-aware)
    # -----------------------------------------------------------------

    def _detect_diminishing_returns(
        runtime: ToolRuntime,
        threshold: Annotated[int, "Minimum new refs per round to continue"] = 2,
        lookback_rounds: Annotated[int, "Number of recent rounds to analyze"] = 2,
    ) -> str:
        """Detect diminishing returns in research progress."""
        resolved = _resolve_backend(runtime)

        try:
            accumulator_data = None
            try:
                content = resolved.read(ACCUMULATOR_FILE)
                accumulator_data = json.loads(content)
            except Exception:
                pass  # File doesn't exist yet — expected on round 1

            if not accumulator_data or "rounds" not in accumulator_data:
                return """ℹ️ No round data available for diminishing returns analysis.

**Possible reasons:**
- First research round (no history yet)
- Findings accumulator not yet created
- No rounds saved with `save_round_findings()`

**Recommendation:** CONTINUE with current round."""

            rounds = accumulator_data["rounds"]
            if len(rounds) < lookback_rounds:
                return f"""ℹ️ Not enough rounds for analysis.

**Current rounds:** {len(rounds)}
**Required:** {lookback_rounds}

**Recommendation:** CONTINUE - need more data to detect trends."""

            recent_rounds = rounds[-lookback_rounds:]
            recent_new_refs = [r.get("new_refs_count", 0) for r in recent_rounds]

            if all(count < threshold for count in recent_new_refs):
                avg_new_refs = sum(recent_new_refs) / len(recent_new_refs)
                round_details = "\n".join(
                    f"- Round {r['round_number']}: {r.get('new_refs_count', 0)} new refs"
                    for r in recent_rounds
                )
                return f"""⚠️ **DIMINISHING RETURNS DETECTED**

**Last {lookback_rounds} rounds:**
{round_details}

**Average new refs:** {avg_new_refs:.1f} refs/round
**Threshold:** {threshold} refs/round

**Recommendation:** STOP - Searches are yielding diminishing results.

💡 **Next steps:**
1. Review current coverage with `get_coverage_gaps()`
2. If coverage targets met → proceed to report writing
3. If gaps remain → consider citation analysis on A-refs instead"""
            else:
                avg_new_refs = sum(recent_new_refs) / len(recent_new_refs)
                return f"""✅ **Progress Healthy - CONTINUE**

**Last {lookback_rounds} rounds:** {recent_new_refs} new refs
**Average:** {avg_new_refs:.1f} refs/round
**Threshold:** {threshold} refs/round

**Recommendation:** CONTINUE with next research round."""

        except Exception as e:
            _logger.error(f"Error in detect_diminishing_returns: {e}")
            return f"❌ Error detecting diminishing returns: {e}"

    # -----------------------------------------------------------------
    # Build and return StructuredTool instances
    # -----------------------------------------------------------------

    save_tool = StructuredTool.from_function(
        name="save_round_findings",
        func=_save_round_findings,
        description=(
            "Save findings from a research round to persistent storage. "
            "Ensures findings survive context truncation by writing structured "
            "data to the filesystem."
        ),
    )

    detect_tool = StructuredTool.from_function(
        name="detect_diminishing_returns",
        func=_detect_diminishing_returns,
        description=(
            "Detect diminishing returns in research progress by analyzing "
            "recent rounds. Returns a recommendation to CONTINUE or STOP."
        ),
    )

    return [save_tool, detect_tool]
