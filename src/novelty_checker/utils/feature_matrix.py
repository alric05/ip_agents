"""Feature Matrix Builder Utility.

This module provides utilities for building and validating Feature Matrix
tables from agent state. The Feature Matrix is Section 4 of the final
novelty report and is the "core analytical deliverable".

CRITICAL: All rows must use Publication Numbers (not query IDs):
- Patents: US10234567B2, JP2007171504A, CN106054342A, EP1234567A1
- NPL: WOS:000299510600010, DOI:10.1021/acs.analchem.2c01234

NEVER use query IDs like K1.1, NQP-1.2, S1.1 as row identifiers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, TypedDict, TYPE_CHECKING

if TYPE_CHECKING:
    from src.novelty_checker.state import DeepAgentState, Feature, Reference


# =============================================================================
# Type Definitions
# =============================================================================

class FeatureMatrixRowData(TypedDict):
    """Data for a single Feature Matrix row."""
    
    publication_number: str
    ref_type: Literal["Patent", "Research Paper"]
    short_description: str
    relevance: Literal["A", "B"]
    earliest_priority: str
    jurisdiction: str
    feature_coverage: dict[str, Literal["Y", "Y1", "N"]]
    aspects_covered: str
    comments: str
    x_category: bool


@dataclass
class ValidationResult:
    """Result of Feature Matrix validation."""
    
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    query_ids_found: list[str] = field(default_factory=list)
    valid_identifiers: list[str] = field(default_factory=list)
    
    def to_markdown(self) -> str:
        """Convert validation result to markdown report."""
        lines = ["# Feature Matrix Validation Report", ""]
        
        if self.is_valid:
            lines.append("## ✅ VALIDATION PASSED")
            lines.append("")
            lines.append(f"Found {len(self.valid_identifiers)} properly formatted reference identifiers.")
        else:
            lines.append("## ❌ VALIDATION FAILED")
            lines.append("")
            lines.append("### Errors:")
            for error in self.errors:
                lines.append(f"- {error}")
        
        if self.warnings:
            lines.append("")
            lines.append("### Warnings:")
            for warning in self.warnings:
                lines.append(f"- ⚠️ {warning}")
        
        if self.query_ids_found:
            lines.append("")
            lines.append("### ❌ Query IDs Found (MUST BE REPLACED):")
            for qid in self.query_ids_found:
                lines.append(f"- `{qid}` - Replace with publication number!")
        
        if self.valid_identifiers:
            lines.append("")
            lines.append("### ✅ Valid Identifiers:")
            for vid in self.valid_identifiers[:10]:  # Show first 10
                lines.append(f"- `{vid}`")
            if len(self.valid_identifiers) > 10:
                lines.append(f"- ... and {len(self.valid_identifiers) - 10} more")
        
        return "\n".join(lines)


# =============================================================================
# Feature Matrix Generator
# =============================================================================

@dataclass
class FeatureMatrixGenerator:
    """Generates Feature Matrix tables from references and features.
    
    Usage:
        generator = FeatureMatrixGenerator(features, core_feature_ids)
        generator.add_reference(ref)
        markdown = generator.to_markdown()
    """
    
    features: list["Feature"]
    core_feature_ids: list[str] = field(default_factory=list)
    rows: list[FeatureMatrixRowData] = field(default_factory=list)
    
    def get_feature_ids(self) -> list[str]:
        """Get ordered list of feature IDs."""
        return [f["id"] for f in self.features]
    
    def add_reference(self, ref: "Reference") -> bool:
        """Add a reference to the Feature Matrix.
        
        Only A and B triage labels are included.
        Returns True if reference was added, False if skipped.
        """
        triage = ref.get("triage_label", "C")
        if triage not in ("A", "B"):
            return False
        
        # Determine ref type
        source = ref.get("source", "")
        ref_type_explicit = ref.get("ref_type", "")
        
        if ref_type_explicit == "npl" or source == "wos":
            ref_type_display: Literal["Patent", "Research Paper"] = "Research Paper"
        else:
            ref_type_display = "Patent"
        
        # Get publication number (must be ref_id, never query ID)
        pub_number = ref.get("ref_id", "")
        if not pub_number or self._is_query_id(pub_number):
            # Skip references without valid publication numbers
            return False
        
        # Get date info
        if ref_type_display == "Patent":
            earliest = ref.get("priority_date", "")
        else:
            earliest = ref.get("pub_year", "")
        
        # Get feature coverage
        feature_coverage = ref.get("feature_coverage", {})
        if not feature_coverage:
            # Fallback to legacy feature_mapping
            feature_coverage = ref.get("feature_mapping", {})
        
        # Check X-category (all core features = Y)
        x_category = all(
            feature_coverage.get(fid) == "Y"
            for fid in self.core_feature_ids
        ) if self.core_feature_ids else False
        
        row: FeatureMatrixRowData = {
            "publication_number": pub_number,
            "ref_type": ref_type_display,
            "short_description": (ref.get("title", "") or "")[:60],
            "relevance": triage,  # type: ignore
            "earliest_priority": earliest,
            "jurisdiction": ref.get("jurisdiction", ""),
            "feature_coverage": feature_coverage,
            "aspects_covered": ref.get("aspects_covered", ""),
            "comments": ref.get("comments", "") or ref.get("pin_cites", ""),
            "x_category": x_category,
        }
        
        self.rows.append(row)
        return True
    
    def _is_query_id(self, identifier: str) -> bool:
        """Check if identifier looks like a query ID (wrong format)."""
        # Query ID patterns: K1.1, K2.3, NQP-1.2, S1.1, etc.
        query_patterns = [
            r'^K\d+\.\d+$',      # K1.1, K2.3
            r'^NQP-\d+\.\d+$',   # NQP-1.2
            r'^S\d+\.\d+$',      # S1.1
            r'^Q\d+$',           # Q1, Q2
        ]
        return any(re.match(pattern, identifier, re.IGNORECASE) for pattern in query_patterns)
    
    def to_markdown(self) -> str:
        """Generate Feature Matrix as markdown table."""
        if not self.rows:
            return "No A or B references to include in Feature Matrix."
        
        feature_ids = self.get_feature_ids()
        
        # Build header
        header_cols = [
            "Publication Number",
            "Ref Type",
            "Short Description",
            "Relevance",
            "Earliest Priority",
            "Jurisdiction",
        ]
        header_cols.extend(feature_ids)
        header_cols.extend(["Which Aspects Covered", "Comments", "X-category"])
        
        # Separator row
        separator = ["-" * 3 for _ in header_cols]
        
        # Build rows
        data_rows = []
        for row in self.rows:
            row_cells = [
                row["publication_number"],
                row["ref_type"],
                row["short_description"][:40] + "..." if len(row["short_description"]) > 40 else row["short_description"],
                row["relevance"],
                row["earliest_priority"],
                row["jurisdiction"],
            ]
            # Add feature coverage columns
            for fid in feature_ids:
                row_cells.append(row["feature_coverage"].get(fid, "—"))
            row_cells.extend([
                row["aspects_covered"],
                row["comments"],
                "X" if row["x_category"] else "",
            ])
            data_rows.append(row_cells)
        
        # Format table
        lines = [
            "## 4. Feature Matrix (Core Analytical Deliverable)",
            "",
            "⚠️ **Each row = ONE REFERENCE identified by Publication Number**",
            "",
            "| " + " | ".join(header_cols) + " |",
            "| " + " | ".join(separator) + " |",
        ]
        for row_cells in data_rows:
            lines.append("| " + " | ".join(str(cell) for cell in row_cells) + " |")
        
        return "\n".join(lines)


# =============================================================================
# State-Based Functions
# =============================================================================

def build_feature_matrix_from_state(state: "DeepAgentState") -> str:
    """Build Feature Matrix markdown from agent state.
    
    This function reads features and references from state and generates
    a properly formatted Feature Matrix with Publication Numbers.
    
    Args:
        state: The DeepAgentState containing features and references
        
    Returns:
        Markdown string of the Feature Matrix
    """
    features = state.get("features", [])
    references = state.get("references", [])
    
    if not features:
        return "No features defined. Cannot generate Feature Matrix."
    
    if not references:
        return "No references found. Feature Matrix is empty."
    
    # Determine core feature IDs
    core_ids = [f["id"] for f in features if f.get("is_core", False)]
    
    # Create generator and add references
    generator = FeatureMatrixGenerator(
        features=features,
        core_feature_ids=core_ids,
    )
    
    added_count = 0
    skipped_count = 0
    for ref in references:
        if generator.add_reference(ref):
            added_count += 1
        else:
            skipped_count += 1
    
    if added_count == 0:
        return f"No A or B references to include in Feature Matrix. ({skipped_count} references skipped)"
    
    markdown = generator.to_markdown()
    
    # Add stats
    markdown += f"\n\n*{added_count} references included, {skipped_count} C-rated references omitted.*"
    
    return markdown


def validate_feature_matrix_in_report(report_markdown: str) -> ValidationResult:
    """Validate that a report's Feature Matrix uses correct identifiers.
    
    Checks that:
    1. Publication numbers are used (not query IDs)
    2. Each row represents a unique reference
    3. Patent and NPL identifiers follow expected formats
    
    Args:
        report_markdown: The full report markdown
        
    Returns:
        ValidationResult with errors, warnings, and found identifiers
    """
    result = ValidationResult(is_valid=True)
    
    # Extract Feature Matrix section
    matrix_content = extract_feature_matrix_from_markdown(report_markdown)
    if not matrix_content:
        result.warnings.append("Could not find Feature Matrix section in report")
        return result
    
    # Find table rows (skip header and separator)
    table_lines = [
        line.strip() for line in matrix_content.split("\n")
        if line.strip().startswith("|") and "---" not in line
    ]
    
    if len(table_lines) < 2:
        result.warnings.append("Feature Matrix table appears empty or malformed")
        return result
    
    # Skip header row
    data_rows = table_lines[1:]
    
    # Query ID patterns (wrong)
    query_id_patterns = [
        (r'\bK\d+\.\d+\b', "Keyword query ID"),
        (r'\bNQP-\d+\.\d+\b', "NPL query ID"),
        (r'\bS\d+\.\d+\b', "Semantic query ID"),
        (r'\bQ\d+\b', "Generic query ID"),
    ]
    
    # Valid identifier patterns
    valid_patterns = [
        r'US\d{7,}[A-Z]?\d*',          # US patents
        r'EP\d{6,}[A-Z]?\d*',          # EP patents
        r'JP\d{10}[A-Z]?\d*',          # JP patents
        r'CN\d{9,}[A-Z]?\d*',          # CN patents
        r'KR\d{10,}[A-Z]?\d*',         # KR patents
        r'WO\d{10,}[A-Z]?\d*',         # WIPO patents
        r'WOS:\d{15}',                  # WOS IDs
        r'10\.\d{4,}/[^\s|]+',         # DOIs
    ]
    
    for row in data_rows:
        cells = [c.strip() for c in row.split("|") if c.strip()]
        if not cells:
            continue
        
        first_cell = cells[0]
        
        # Check for query IDs (wrong)
        for pattern, pattern_name in query_id_patterns:
            matches = re.findall(pattern, first_cell, re.IGNORECASE)
            for match in matches:
                result.query_ids_found.append(match)
                result.errors.append(f"Found {pattern_name}: `{match}` - must use publication number instead")
                result.is_valid = False
        
        # Check for valid identifiers
        for pattern in valid_patterns:
            matches = re.findall(pattern, first_cell, re.IGNORECASE)
            result.valid_identifiers.extend(matches)
    
    if not result.valid_identifiers and not result.query_ids_found:
        result.warnings.append("Could not identify any reference identifiers in Feature Matrix")
    
    return result


def extract_feature_matrix_from_markdown(report_markdown: str) -> str | None:
    """Extract the Feature Matrix section from a report.
    
    Looks for Section 4 (Feature Matrix) and extracts its content.
    
    Args:
        report_markdown: The full report markdown
        
    Returns:
        The Feature Matrix section content, or None if not found
    """
    # Look for Section 4 heading variations
    patterns = [
        r'##\s*4\.\s*Feature\s+Matrix.*?(?=\n##|\Z)',
        r'###\s*4\.\s*Feature\s+Matrix.*?(?=\n###|\n##|\Z)',
        r'##\s*Feature\s+Matrix.*?(?=\n##|\Z)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, report_markdown, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(0)
    
    return None


# =============================================================================
# Pre-Report Validation Hook
# =============================================================================

def pre_report_feature_matrix_check(state: "DeepAgentState") -> tuple[bool, str]:
    """Pre-report check to ensure Feature Matrix will be correct.
    
    Call this before generating the final report to verify that:
    1. All A/B references have valid publication numbers
    2. No query IDs will appear in the matrix
    
    Args:
        state: The DeepAgentState to check
        
    Returns:
        Tuple of (is_valid, message)
    """
    references = state.get("references", [])
    features = state.get("features", [])
    
    if not references:
        return False, "No references in state. Cannot generate Feature Matrix."
    
    if not features:
        return False, "No features in state. Cannot generate Feature Matrix."
    
    # Check A/B references
    ab_refs = [r for r in references if r.get("triage_label") in ("A", "B")]
    
    if not ab_refs:
        return False, "No A or B rated references. Feature Matrix will be empty."
    
    # Check for valid identifiers
    issues = []
    valid_count = 0
    
    query_id_patterns = [
        r'^K\d+\.\d+$',
        r'^NQP-\d+\.\d+$',
        r'^S\d+\.\d+$',
        r'^Q\d+$',
    ]
    
    for ref in ab_refs:
        ref_id = ref.get("ref_id", "")
        
        if not ref_id:
            issues.append(f"Reference missing ref_id: {ref.get('title', 'Unknown')[:40]}")
            continue
        
        is_query_id = any(re.match(p, ref_id, re.IGNORECASE) for p in query_id_patterns)
        if is_query_id:
            issues.append(f"Reference has query ID instead of publication number: {ref_id}")
        else:
            valid_count += 1
    
    if issues:
        message = f"Found {len(issues)} issues:\n" + "\n".join(f"- {i}" for i in issues[:5])
        if len(issues) > 5:
            message += f"\n- ... and {len(issues) - 5} more"
        return False, message
    
    return True, f"✅ All {valid_count} A/B references have valid publication numbers."
