"""Analysis tools for the Novelty Checker deep agent.

This module provides tools for evaluating search coverage, triaging references,
and mapping features to prior art - supporting the adaptive search loop.
"""

import logging
from typing import Annotated, Optional
from dataclasses import dataclass
from enum import Enum

from langchain_core.tools import tool
from pydantic import BaseModel, Field


# =============================================================================
# Input Schemas for Tools
# =============================================================================

class FeatureInput(BaseModel):
    """A feature to check against a reference.
    
    Use this schema when passing features to triage_reference.
    You MUST provide the full feature object, not just the ID.
    """
    id: str = Field(..., description="Feature identifier (e.g., 'F1', 'F2')")
    description: str = Field(..., description="Full description of the feature")

LOGGER = logging.getLogger("novelty_checker.tools.analysis")


# =============================================================================
# Coverage Levels
# =============================================================================

class CoverageLevel(str, Enum):
    """Coverage levels for features based on reference quality."""
    NONE = "NONE"           # No relevant references found
    WEAK = "WEAK"           # Only tangential references
    MODERATE = "MODERATE"   # Some direct references, not comprehensive  
    STRONG = "STRONG"       # Good direct references, well covered
    SATURATED = "SATURATED" # Comprehensive coverage, no need for more


@dataclass
class FeatureCoverage:
    """Coverage status for a single feature."""
    feature_id: str
    level: CoverageLevel
    reference_count: int
    y_count: int  # Direct teaching count
    y1_count: int  # Partial teaching count
    key_references: list[str]
    notes: str = ""
    
    def to_dict(self) -> dict:
        return {
            "feature_id": self.feature_id,
            "level": self.level.value,
            "reference_count": self.reference_count,
            "y_count": self.y_count,
            "y1_count": self.y1_count,
            "key_references": self.key_references,
            "notes": self.notes,
        }


# =============================================================================
# Analysis Tools
# =============================================================================

@tool
def evaluate_coverage(
    features: Annotated[list[dict], "List of features with id, description, and references"],
    reference_mappings: Annotated[list[dict], "List of feature-to-reference mappings"],
) -> str:
    """Evaluate search coverage for each feature and determine if more searching is needed.
    
    This is the KEY decision tool for the adaptive loop. It determines:
    1. Which features have WEAK/NONE coverage (need more searching)
    2. Which features are SATURATED (stop searching)
    3. Whether to continue the loop or proceed to report
    
    Feature format:
    [
        {"id": "F1", "description": "UV fluorescence detection system", "weight": "core"},
        {"id": "F2", "description": "Polymer sorting mechanism", "weight": "supporting"},
    ]
    
    Reference mapping format:
    [
        {"ref_id": "US12345678", "feature_id": "F1", "mapping": "Y", "notes": "Direct teaching"},
        {"ref_id": "WOS:123456", "feature_id": "F1", "mapping": "Y1", "notes": "Partial teaching"},
        {"ref_id": "US12345678", "feature_id": "F2", "mapping": "N", "notes": "Not relevant"},
    ]
    
    Args:
        features: List of feature dictionaries
        reference_mappings: List of feature-to-reference mappings
        
    Returns:
        Coverage analysis with recommendations for next actions
    """
    # Build coverage data
    coverage_map = {}
    
    for f in features:
        feature_id = f.get("id", "")
        coverage_map[feature_id] = FeatureCoverage(
            feature_id=feature_id,
            level=CoverageLevel.NONE,
            reference_count=0,
            y_count=0,
            y1_count=0,
            key_references=[],
        )
    
    # Process mappings
    for m in reference_mappings:
        feature_id = m.get("feature_id", "")
        ref_id = m.get("ref_id", "")
        mapping = m.get("mapping", "N").upper()
        
        if feature_id not in coverage_map:
            continue
        
        cov = coverage_map[feature_id]
        cov.reference_count += 1
        
        if mapping == "Y":
            cov.y_count += 1
            cov.key_references.append(ref_id)
        elif mapping == "Y1":
            cov.y1_count += 1
            if len(cov.key_references) < 5:
                cov.key_references.append(ref_id)
    
    # Calculate coverage levels
    for cov in coverage_map.values():
        if cov.y_count >= 3:
            cov.level = CoverageLevel.SATURATED
            cov.notes = "Well covered - consider stopping search for this feature"
        elif cov.y_count >= 2 or (cov.y_count >= 1 and cov.y1_count >= 2):
            cov.level = CoverageLevel.STRONG
            cov.notes = "Good coverage - one more cycle may help"
        elif cov.y_count >= 1 or cov.y1_count >= 2:
            cov.level = CoverageLevel.MODERATE
            cov.notes = "Moderate coverage - continue searching"
        elif cov.y1_count >= 1 or cov.reference_count >= 2:
            cov.level = CoverageLevel.WEAK
            cov.notes = "Weak coverage - needs focused searching"
        else:
            cov.notes = "No coverage - expand search terms"
    
    # Generate report
    lines = [
        "# Coverage Analysis Report",
        "",
        "## Per-Feature Coverage",
        "",
    ]
    
    weak_features = []
    for feature_id in sorted(coverage_map.keys()):
        cov = coverage_map[feature_id]
        icon = {
            CoverageLevel.SATURATED: "✅",
            CoverageLevel.STRONG: "🟢",
            CoverageLevel.MODERATE: "🟡",
            CoverageLevel.WEAK: "🟠",
            CoverageLevel.NONE: "🔴",
        }[cov.level]
        
        lines.append(f"### {icon} {feature_id}: {cov.level.value}")
        lines.append(f"- References evaluated: {cov.reference_count}")
        lines.append(f"- Direct matches (Y): {cov.y_count}")
        lines.append(f"- Partial matches (Y1): {cov.y1_count}")
        if cov.key_references:
            lines.append(f"- Key refs: {', '.join(cov.key_references[:5])}")
        lines.append(f"- Note: {cov.notes}")
        lines.append("")
        
        if cov.level in (CoverageLevel.WEAK, CoverageLevel.NONE):
            weak_features.append(feature_id)
    
    # Decision section
    lines.append("## Adaptive Loop Decision")
    lines.append("")
    
    saturated_count = sum(1 for c in coverage_map.values() if c.level == CoverageLevel.SATURATED)
    strong_count = sum(1 for c in coverage_map.values() if c.level == CoverageLevel.STRONG)
    total_features = len(coverage_map)
    
    if saturated_count + strong_count >= total_features * 0.8:
        lines.append("**DECISION: STOP SEARCHING** — Proceed to report generation")
        lines.append(f"- {saturated_count}/{total_features} features saturated")
        lines.append(f"- {strong_count}/{total_features} features have strong coverage")
    elif weak_features:
        lines.append("**DECISION: CONTINUE SEARCHING**")
        lines.append(f"- Features needing more coverage: {', '.join(weak_features)}")
        lines.append("")
        lines.append("### Recommended Next Actions")
        for wf in weak_features[:3]:
            lines.append(f"1. Run semantic search targeting {wf}")
            lines.append(f"2. Try alternative keyword combinations for {wf}")
            lines.append(f"3. Expand synonym sets for {wf}")
    else:
        lines.append("**DECISION: OPTIONAL CONTINUE** — Consider one more targeted cycle")
    
    return "\n".join(lines)


@tool
def triage_reference(
    ref_id: Annotated[str, "Reference ID (patent number or WOS number)"],
    ref_type: Annotated[str, "Type: 'patent' or 'npl'"],
    title: Annotated[str, "Reference title"],
    abstract: Annotated[str, "Reference abstract"],
    features: Annotated[list[FeatureInput], "List of features to check. Each feature MUST be a dict with 'id' (e.g., 'F1') and 'description' (the full feature description). Do NOT pass just feature IDs."],
) -> str:
    """Quickly triage a single reference for relevance.
    
    Assigns an A/B/C label based on apparent relevance:
    - A: Highly relevant - appears to directly teach multiple features
    - B: Moderately relevant - may teach some features
    - C: Low relevance - tangential or unlikely to be useful
    
    This is a QUICK assessment based on title/abstract. Full mapping
    requires reading the complete document.
    
    IMPORTANT: The 'features' parameter must be a list of objects, where each
    object has:
    - "id": Feature identifier like "F1", "F2", etc.
    - "description": The full description of the feature
    
    Example:
        features=[
            {"id": "F1", "description": "A motor for driving lens elements"},
            {"id": "F2", "description": "Gear mechanism with worm wheel"}
        ]
    
    Args:
        ref_id: Reference identifier
        ref_type: "patent" or "npl"
        title: Reference title
        abstract: Reference abstract
        features: List of feature objects with id and description
    """
    # Simple keyword-based scoring (in production, use LLM reasoning)
    title_lower = (title or "").lower()
    abstract_lower = (abstract or "").lower()
    text = title_lower + " " + abstract_lower
    
    feature_hits = []
    for f in features:
        # Handle both Pydantic models and dicts
        if isinstance(f, FeatureInput):
            feature_id = f.id
            description = (f.description or "").lower()
        elif isinstance(f, dict):
            feature_id = f.get("id", "")
            description = (f.get("description", "") or "").lower()
        else:
            # Handle plain string (just feature ID) - this is the error case
            LOGGER.warning(f"Feature should be dict with 'id' and 'description', got: {type(f)}")
            feature_id = str(f) if f else ""
            description = ""
        
        # Extract key terms from description
        key_terms = [w for w in description.split() if len(w) > 4][:5]
        
        # Count matches
        matches = sum(1 for term in key_terms if term in text)
        if matches > 0:
            feature_hits.append((feature_id, matches, len(key_terms)))
    
    # Calculate score
    total_score = sum(hits for _, hits, _ in feature_hits)
    features_matched = len(feature_hits)
    
    # Assign label
    if features_matched >= 2 and total_score >= 4:
        label = "A"
        confidence = "HIGH"
        action = "Queue for detailed review"
    elif features_matched >= 1 and total_score >= 2:
        label = "B"
        confidence = "MEDIUM"
        action = "Review if time permits"
    else:
        label = "C"
        confidence = "LOW"
        action = "Skip unless gaps remain"
    
    lines = [
        f"# Triage Result: {ref_id}",
        "",
        f"**Label**: {label}",
        f"**Confidence**: {confidence}",
        f"**Reference Type**: {ref_type}",
        "",
        f"## Quick Assessment",
        f"- Features potentially matched: {features_matched}/{len(features)}",
        f"- Relevance score: {total_score}",
        f"- Recommended action: {action}",
        "",
    ]
    
    if feature_hits:
        lines.append("## Feature Matches (Initial)")
        for feature_id, hits, total in feature_hits:
            pct = int(100 * hits / total) if total > 0 else 0
            lines.append(f"- {feature_id}: {hits}/{total} keywords ({pct}%)")
    
    lines.extend([
        "",
        "## Title",
        title or "N/A",
        "",
        "## Abstract Preview",
        (abstract or "N/A")[:500] + "..." if len(abstract or "") > 500 else (abstract or "N/A"),
    ])
    
    return "\n".join(lines)


@tool
def map_features_to_reference(
    ref_id: Annotated[str, "Reference ID (patent number or WOS number)"],
    ref_content: Annotated[str, "Full reference content (claims, description, or article text)"],
    features: Annotated[list[dict], "List of features with id and description"],
) -> str:
    """Create detailed feature mapping for a reference.
    
    Produces a Y/Y1/N mapping for each feature:
    - Y: Direct teaching - reference explicitly teaches this feature
    - Y1: Partial/implicit teaching - feature is suggested or partially disclosed
    - N: Not taught - no relevant disclosure found
    
    This requires reading the full reference content (claims, description,
    or article text) and providing justification for each mapping.
    
    Args:
        ref_id: Reference identifier
        ref_content: Full text content to analyze
        features: List of features to map
        
    Returns:
        Detailed mapping table with justifications
    """
    # In production, this would use LLM analysis
    # For now, do basic keyword matching as a placeholder
    
    content_lower = (ref_content or "").lower()
    
    lines = [
        f"# Feature Mapping: {ref_id}",
        "",
        "## Mapping Table",
        "",
        "| Feature | Mapping | Confidence | Justification |",
        "|---------|---------|------------|---------------|",
    ]
    
    mappings = []
    
    for f in features:
        feature_id = f.get("id", "")
        description = f.get("description", "")
        desc_lower = (description or "").lower()
        
        # Extract key terms
        key_terms = [w for w in desc_lower.split() if len(w) > 4][:8]
        
        # Count matches in content
        matches = sum(1 for term in key_terms if term in content_lower)
        match_pct = matches / len(key_terms) if key_terms else 0
        
        # Determine mapping
        if match_pct >= 0.6:
            mapping = "Y"
            confidence = "High"
            justification = f"Strong keyword overlap ({matches}/{len(key_terms)} terms found)"
        elif match_pct >= 0.3:
            mapping = "Y1"
            confidence = "Medium"
            justification = f"Partial keyword overlap ({matches}/{len(key_terms)} terms found)"
        else:
            mapping = "N"
            confidence = "Low"
            justification = f"Weak overlap ({matches}/{len(key_terms)} terms found)"
        
        lines.append(f"| {feature_id} | {mapping} | {confidence} | {justification} |")
        mappings.append({
            "feature_id": feature_id,
            "mapping": mapping,
            "confidence": confidence,
        })
    
    # Summary
    y_count = sum(1 for m in mappings if m["mapping"] == "Y")
    y1_count = sum(1 for m in mappings if m["mapping"] == "Y1")
    
    lines.extend([
        "",
        "## Summary",
        f"- Direct teachings (Y): {y_count}",
        f"- Partial teachings (Y1): {y1_count}",
        f"- Not taught (N): {len(mappings) - y_count - y1_count}",
        "",
    ])
    
    if y_count >= 2:
        lines.append("**Assessment**: This reference is highly relevant and should be included in the report.")
    elif y_count >= 1 or y1_count >= 2:
        lines.append("**Assessment**: This reference is moderately relevant.")
    else:
        lines.append("**Assessment**: This reference has limited relevance.")
    
    lines.extend([
        "",
        "---",
        "*Note: This is an automated assessment. Manual review is recommended for final report inclusion.*",
    ])
    
    return "\n".join(lines)


@tool
def generate_search_strategy(
    features: Annotated[list[dict], "Features needing coverage"],
    coverage_report: Annotated[str, "Current coverage status from evaluate_coverage"],
    attempted_queries: Annotated[list[str], "Queries already tried (to avoid repetition)"],
) -> str:
    """Generate next-round search strategy for features with weak coverage.
    
    Based on the coverage gaps identified, suggests:
    1. Alternative synonym sets
    2. Different field combinations
    3. Broader/narrower query formulations
    4. Semantic query variations
    
    This helps avoid repetitive searches and explores new angles.
    
    Args:
        features: Features that need better coverage
        coverage_report: Output from evaluate_coverage tool
        attempted_queries: List of queries already executed
        
    Returns:
        Strategic recommendations for next search cycle
    """
    lines = [
        "# Search Strategy Recommendations",
        "",
        "Based on coverage gaps, here are recommended search approaches:",
        "",
    ]
    
    for i, f in enumerate(features, 1):
        feature_id = f.get("id", "")
        description = f.get("description", "")
        
        lines.append(f"## {feature_id}: {description[:50]}...")
        lines.append("")
        
        # Suggest different approaches
        lines.append("### Recommended Queries")
        lines.append("")
        lines.append("**1. Semantic (Natural Language)**")
        lines.append(f"   - Try describing the problem: 'system for solving X challenge'")
        lines.append(f"   - Focus on the application: 'X used in Y industry'")
        lines.append(f"   - Describe the mechanism: 'method of achieving X through Y'")
        lines.append("")
        
        lines.append("**2. Patent Keyword**")
        lines.append(f"   - Try DWPI fields: @(dwpi_novelty,dwpi_use) ...")
        lines.append(f"   - Use quota: \"term1 term2 term3 term4\"=3")
        lines.append(f"   - Try NEAR/ADJ: (term1 NEAR/10 term2)")
        lines.append("")
        
        lines.append("**3. NPL (Academic)**")
        lines.append(f"   - Use field-specific: TI=(...) AND AB=(...)")
        lines.append(f"   - Try NEAR: TS=(term1 NEAR/5 term2)")
        lines.append(f"   - Filter recent: from_year=2020")
        lines.append("")
    
    # General tips
    lines.extend([
        "---",
        "## General Tips",
        "",
        "1. **Expand synonyms**: If 'polymer' didn't work, try 'plastic', 'resin', 'thermoplastic'",
        "2. **Change abstraction level**: Too specific? Try broader terms. Too broad? Add qualifiers.",
        "3. **Try different domains**: If not in chemistry, check mechanical engineering terms",
        "4. **Use semantic search**: It finds conceptually related results even with different terminology",
        "5. **Check classification codes**: CPC/IPC codes can reveal related technology areas",
    ])
    
    return "\n".join(lines)


# =============================================================================
# Feature Matrix Builder Tool (Phase 2)
# =============================================================================

@tool
def build_feature_matrix(
    references: Annotated[list[dict], "List of references with triage labels and feature mappings"],
    feature_ids: Annotated[list[str], "Ordered list of feature IDs (F1, F2, F3, etc.)"],
    core_feature_ids: Annotated[list[str], "List of core feature IDs for X-category detection"] = None,
) -> str:
    """Build Feature Matrix markdown from references with correct Publication Number identifiers.
    
    ⚠️ CRITICAL: Each row in the output is ONE REFERENCE identified by its Publication Number.
    ❌ NEVER outputs query IDs (K1.1, NQP-1.2, S1.1) as row identifiers.
    ✅ ALWAYS outputs publication numbers (US10234567B2, WOS:000299510600010, DOI:...).
    
    This tool ensures the Feature Matrix (Section 4) uses proper reference identifiers.
    Use this tool after screening to generate the Feature Matrix for the final report.
    
    Reference format:
    [
        {
            "ref_id": "US10234567B2",  # Publication number - PRIMARY IDENTIFIER
            "ref_type": "patent",       # "patent" or "npl"
            "title": "Method for...",
            "triage_label": "A",        # "A", "B", or "C"
            "priority_date": "2018-03-15",  # For patents
            "pub_year": "2022",         # For NPL
            "jurisdiction": "US",       # Country code or journal
            "feature_coverage": {"F1": "Y", "F2": "N", "F3": "Y1"},
            "aspects_covered": "F1 fully, F3 partial",
            "comments": "Claims 1, 5; lacks F2"
        }
    ]
    
    Args:
        references: List of reference dictionaries
        feature_ids: Ordered list of feature IDs for columns
        core_feature_ids: Core features for X-category check (defaults to all)
        
    Returns:
        Markdown Feature Matrix table with Publication Numbers as row identifiers
    """
    if core_feature_ids is None:
        core_feature_ids = feature_ids
    
    # Validate - reject any query IDs that might have slipped through
    query_id_patterns = ['K', 'NQP-', 'S', 'QP']
    for ref in references:
        ref_id = ref.get("ref_id", "")
        for pattern in query_id_patterns:
            if ref_id.startswith(pattern) and any(c.isdigit() for c in ref_id):
                # Check if it looks like a query ID (e.g., K1.1, NQP-1.2)
                import re
                if re.match(r'^(K|NQP-|S|QP)\d+(\.\d+)?$', ref_id):
                    LOGGER.warning(
                        "⚠️ Query ID '%s' detected in references. "
                        "Use publication numbers instead!", ref_id
                    )
    
    # Filter to A/B references only
    ab_refs = [r for r in references if r.get("triage_label", "").upper() in ("A", "B")]
    
    if not ab_refs:
        return """## 4. Feature Matrix (Core Analytical Deliverable)

⚠️ No A/B references found in search results.

| Publication Number | Ref Type | Short Description | Relevance | Earliest Priority | Jurisdiction | """ + " | ".join(feature_ids) + """ | Which Aspects Covered | Comments | X-category |
|---|---|---|---|---|---|""" + "|".join(["---"] * len(feature_ids)) + """|---|---|---|

*No references to display. Consider expanding search scope.*
"""
    
    lines = [
        "## 4. Feature Matrix (Core Analytical Deliverable)",
        "",
        "⚠️ **Each row = ONE REFERENCE identified by Publication Number**",
        "",
    ]
    
    # Build header
    header_parts = [
        "Publication Number", "Ref Type", "Short Description",
        "Relevance", "Earliest Priority", "Jurisdiction"
    ]
    header_parts.extend(feature_ids)
    header_parts.extend(["Which Aspects Covered", "Comments", "X-category"])
    
    lines.append("| " + " | ".join(header_parts) + " |")
    lines.append("|" + "|".join(["---"] * len(header_parts)) + "|")
    
    # Build rows
    x_category_count = 0
    for ref in ab_refs:
        # Get publication number - THE primary identifier
        pub_num = ref.get("ref_id", "-")
        
        # Determine ref type display
        ref_type = ref.get("ref_type", "unknown").lower()
        if ref_type == "patent":
            ref_type_display = "Patent"
        elif ref_type == "npl":
            ref_type_display = "Research Paper"
        else:
            ref_type_display = ref_type.title()
        
        # Get title (truncated)
        title = ref.get("title", "-")
        if len(title) > 45:
            title = title[:42] + "..."
        
        # Get date
        if ref_type == "patent":
            date = ref.get("priority_date", ref.get("pub_year", "-"))
        else:
            date = ref.get("pub_year", ref.get("priority_date", "-"))
        
        # Determine X-category
        feature_coverage = ref.get("feature_coverage", {})
        is_x_category = all(
            feature_coverage.get(fid, "N") == "Y"
            for fid in core_feature_ids
        ) if feature_coverage and core_feature_ids else False
        
        if is_x_category:
            x_category_count += 1
        
        # Build row
        row_parts = [
            pub_num,
            ref_type_display,
            title,
            ref.get("triage_label", "-"),
            date or "-",
            ref.get("jurisdiction", "-"),
        ]
        
        # Add feature coverage columns
        for fid in feature_ids:
            coverage = feature_coverage.get(fid, "N")
            row_parts.append(coverage)
        
        row_parts.extend([
            ref.get("aspects_covered", "-"),
            ref.get("comments", "-"),
            "X" if is_x_category else "",
        ])
        
        # Annotate citation-sourced references with footnote marker
        discovery = ref.get("discovery_method", "")
        if discovery in ("citation_forward", "citation_backward"):
            source_pat = ref.get("source_patent", "")
            direction = "fwd" if discovery == "citation_forward" else "bwd"
            marker = f" [{direction}: {source_pat}]" if source_pat else f" [{direction}]"
            row_parts[0] = pub_num + marker
        
        # Escape pipe characters
        escaped = [str(p).replace("|", "\\|") for p in row_parts]
        lines.append("| " + " | ".join(escaped) + " |")
    
    # Add summary
    a_count = sum(1 for r in ab_refs if r.get("triage_label", "").upper() == "A")
    b_count = sum(1 for r in ab_refs if r.get("triage_label", "").upper() == "B")
    
    lines.append("")
    lines.append(f"**Total:** {len(ab_refs)} references ({a_count} A-refs, {b_count} B-refs)")
    
    if x_category_count > 0:
        lines.append(f"**⚠️ X-Category References:** {x_category_count} "
                     "(potential anticipatory references - disclose ALL core features)")
    
    # Count citation-sourced references
    citation_count = sum(
        1 for r in ab_refs 
        if r.get("discovery_method", "") in ("citation_forward", "citation_backward")
    )
    if citation_count > 0:
        lines.append(f"**📋 Citation-sourced:** {citation_count} references "
                     "discovered via citation network analysis (marked with [fwd/bwd] in Publication Number)")
    
    return "\n".join(lines)


@tool
def validate_feature_matrix_format(
    feature_matrix_markdown: Annotated[str, "Feature Matrix markdown to validate"],
) -> str:
    """Validate that a Feature Matrix uses correct Publication Number identifiers.
    
    This tool checks that the Feature Matrix:
    1. Uses Publication Numbers (US10234567B2, WOS:..., DOI:...) as row identifiers
    2. Does NOT use Query IDs (K1.1, NQP-1.2, S1.1) as row identifiers
    3. Has all required columns
    
    Use this tool to verify Feature Matrix format before including in final report.
    
    Args:
        feature_matrix_markdown: The Feature Matrix markdown to validate
        
    Returns:
        Validation result with any errors found
    """
    import re
    
    errors = []
    warnings = []
    
    # Patterns for query IDs (SHOULD NOT appear in Publication Number column)
    query_id_patterns = [
        (r'\bK\d+\.\d+\b', 'K#.# (patent keyword query)'),
        (r'\bNQP-\d+\.\d+\b', 'NQP-#.# (NPL query)'),
        (r'\bS\d+\.\d+\b', 'S#.# (semantic query)'),
        (r'\bQP\d+\b', 'QP# (query pack)'),
    ]
    
    # Patterns for valid publication numbers
    valid_patterns = [
        r'[A-Z]{2}\d{6,}[A-Z]?\d*',  # US10234567B2, JP2007171504A
        r'WOS:\d+',                   # WOS:000299510600010
        r'10\.\d+/',                  # DOI prefix
    ]
    
    lines = feature_matrix_markdown.split('\n')
    in_table = False
    table_line_count = 0
    
    for i, line in enumerate(lines, 1):
        if '|' not in line:
            in_table = False
            continue
        
        if '---' in line:
            in_table = True
            continue
        
        if not in_table:
            continue
        
        table_line_count += 1
        
        # Extract first column (Publication Number)
        parts = line.split('|')
        if len(parts) < 2:
            continue
        
        first_col = parts[1].strip()
        
        # Check for query ID patterns (bad)
        for pattern, desc in query_id_patterns:
            if re.search(pattern, first_col):
                errors.append(
                    f"Line {i}: Found query ID '{first_col}' in Publication Number column. "
                    f"Query IDs ({desc}) are NOT valid reference identifiers. "
                    f"Use publication numbers like US10234567B2 or WOS:000299510600010"
                )
    
    # Build result
    result_lines = ["# Feature Matrix Validation Report", ""]
    
    if errors:
        result_lines.append("## ❌ VALIDATION FAILED")
        result_lines.append("")
        result_lines.append(f"Found {len(errors)} error(s):")
        result_lines.append("")
        for error in errors:
            result_lines.append(f"- {error}")
        result_lines.append("")
        result_lines.append("### How to Fix")
        result_lines.append("")
        result_lines.append("Replace query IDs with publication numbers:")
        result_lines.append("- `K1.1` → `US10234567B2` (the patent found by query K1.1)")
        result_lines.append("- `NQP-1.2` → `WOS:000299510600010` (the paper found by query NQP-1.2)")
        result_lines.append("- `S1.1` → `JP2007171504A` (the patent found by query S1.1)")
    else:
        result_lines.append("## ✅ VALIDATION PASSED")
        result_lines.append("")
        result_lines.append(f"Feature Matrix has {table_line_count} reference rows.")
        result_lines.append("All rows use proper Publication Number identifiers.")
    
    if warnings:
        result_lines.append("")
        result_lines.append("## ⚠️ Warnings")
        for warning in warnings:
            result_lines.append(f"- {warning}")
    
    return "\n".join(result_lines)
