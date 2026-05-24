"""Data loading utilities for evaluation scorers.

Provides functions to load eval traces, ground truth fixtures, and
session artifacts into the formats scorers expect.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from deepeval.test_case import LLMTestCase

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trace & ground truth loaders
# ---------------------------------------------------------------------------

def load_eval_trace(session_path: Path) -> dict[str, Any]:
    """Load and parse eval_trace.json from a session directory."""
    trace_path = session_path / "eval_trace.json"
    with open(trace_path, encoding="utf-8") as f:
        return json.load(f)


def load_ground_truth(fixture_path: Path) -> dict[str, Any]:
    """Load and merge all ground truth files from a fixture directory."""
    gt: dict[str, Any] = {}

    for filename, key in [
        ("gt_features.json", "features"),
        ("gt_references.json", "references"),
        ("gt_verdict.json", "verdict"),
    ]:
        filepath = fixture_path / filename
        if filepath.exists():
            with open(filepath, encoding="utf-8") as f:
                gt[key] = json.load(f)
        else:
            _logger.warning("Ground truth file not found: %s", filepath)
            gt[key] = {}

    strategy_path = fixture_path / "gt_search_strategy.json"
    if strategy_path.exists():
        with open(strategy_path, encoding="utf-8") as f:
            gt["search_strategy"] = json.load(f)
    else:
        strategy_md = fixture_path / "gt_search_strategy.md"
        if strategy_md.exists():
            gt["search_strategy"] = strategy_md.read_text(encoding="utf-8")

    return gt


def load_session_artifact(session_path: Path, filename: str) -> str:
    """Read a session artifact file as text."""
    filepath = session_path / filename
    if not filepath.exists():
        _logger.debug("Session artifact not found: %s", filepath)
        return ""
    return filepath.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Markdown table parsers
# ---------------------------------------------------------------------------

def parse_features_md(content: str) -> list[dict[str, str]]:
    """Parse a markdown feature table into a list of dicts."""
    lines = content.strip().splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue
        if i + 1 < len(lines) and re.match(r"^\s*\|[\s\-:|]+\|\s*$", lines[i + 1]):
            header_idx = i
            break

    if header_idx is None:
        _logger.warning("No markdown table found in features content")
        return []

    header_line = lines[header_idx]
    headers = [
        h.strip().lower().replace(" ", "_").rstrip("?")
        for h in header_line.strip().strip("|").split("|")
    ]

    features = []
    for line in lines[header_idx + 2:]:
        line = line.strip()
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        row = dict(zip(headers, cells))
        if row.get("id") or row.get("feature_name"):
            features.append(row)

    return features


def parse_references_md(content: str) -> list[dict[str, str]]:
    """Parse a markdown reference table into a list of dicts."""
    lines = content.strip().splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue
        if i + 1 < len(lines) and re.match(r"^\s*\|[\s\-:|]+\|\s*$", lines[i + 1]):
            header_idx = i
            break

    if header_idx is None:
        _logger.warning("No markdown table found in references content")
        return []

    header_line = lines[header_idx]
    headers = [
        h.strip().lower().replace(" ", "_")
        for h in header_line.strip().strip("|").split("|")
    ]

    references = []
    for line in lines[header_idx + 2:]:
        line = line.strip()
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        row = dict(zip(headers, cells))
        if any(row.values()):
            references.append(row)

    return references


# ---------------------------------------------------------------------------
# Verdict extraction
# ---------------------------------------------------------------------------

# Strict patterns: only match clear, structured verdict declarations
_VERDICT_PATTERNS = [
    r"(?:overall\s+)?verdict\s*[:]\s*\**\s*(novel|partially[\s_-]novel|not[\s_-]novel)",
    r"(?:overall\s+)?assessment\s*[:]\s*\**\s*(novel|partially[\s_-]novel|not[\s_-]novel)",
    r"conclusion\s*[:]\s*\**\s*(novel|partially[\s_-]novel|not[\s_-]novel)",
    r"novelty\s+conclusion\s*[:]\s*\**\s*(novel|partially[\s_-]novel|not[\s_-]novel)",
    r"^\s*\**\s*(novel|partially[\s_-]novel|not[\s_-]novel)\s*\**\s*$",
    # r"overall\s+novelty\s*[:]\s*\**\s*(high|moderate|low)",
]

# Tightened heuristic patterns: require structured label format,
# not arbitrary prose mentions of "novelty risk"
_HEURISTIC_NOT_NOVEL = [
    # Explicit "not novel" declarations
    r"\bnot[\s_-]novel\b(?!\s+enough|\s+if)",
    r"\blacks?\s+novelty\b",
    r"\bno\s+novelty\b(?!\s+(?:concern|issue|gap))",
    # Structured risk labels (must be label-like format)
    r"(?:^|\n)\s*\**\s*overall\s+novelty\s+risk\s*[:]\s*\**\s*(?:very\s+)?high\b",
    r"(?:^|\n)\s*\**\s*novelty\s+risk\s*[:]\s*\**\s*(?:very\s+)?high\b",
    r"(?:^|\n)\s*\**\s*novelty\s+indication\s*[:]\s*\**\s*weak\b",
    # Strong language
    r"\bfully\s+anticipat(?:e[ds]?|ed\s+by|ory)\b",
    r"\bnovelty\s+is\s+destroyed\b",
]

_HEURISTIC_PARTIALLY_NOVEL = [
    r"\bpartial(?:ly)?[\s_-]novel\b",
    r"\blimited\s+novelty\b",
    r"\bsome\s+novelty\b",
    r"\bmarginally\s+novel\b",
    # Structured risk labels for moderate
    r"(?:^|\n)\s*\**\s*overall\s+novelty\s+risk\s*[:]\s*\**\s*(?:moderate|medium)\b",
    r"(?:^|\n)\s*\**\s*novelty\s+risk\s*[:]\s*\**\s*(?:moderate|medium)\b",
    r"(?:^|\n)\s*\**\s*novelty\s+indication\s*[:]\s*\**\s*(?:moderate|partial)\b",
]

_HEURISTIC_NOVEL = [
    r"\b(?:is|appears?|deemed|considered)\s+novel\b",
    r"\bnovelty\s+(?:is\s+)?(?:confirmed|established|clearly\s+(?:established|present))\b",
    # Structured risk labels for low
    r"(?:^|\n)\s*\**\s*overall\s+novelty\s+risk\s*[:]\s*\**\s*low\b",
    r"(?:^|\n)\s*\**\s*novelty\s+risk\s*[:]\s*\**\s*low\b",
    r"(?:^|\n)\s*\**\s*novelty\s+indication\s*[:]\s*\**\s*strong\b",
]

def derive_verdict_from_gap_analysis(report_content: str) -> str | None:
    """Derive verdict from the Feature Matrix in the agent's report.

    Parses Feature Mapping rows (e.g., "F1=Y; F2=Y1; F3=N") to determine
    per-feature coverage across all references.

    A feature is "covered" if ANY reference has Y or Y1 for it.

    Logic:
    - All core features covered -> not_novel
    - No core features covered -> novel
    - Mixed -> partially_novel

    Returns None if no feature mapping data found.
    """
    import re

    # Parse all Feature Mapping lines
    coverage = {}
    for line in report_content.split("\n"):
        if "feature mapping" not in line.lower() and not re.search(r'F\d+\s*[=:]\s*[YN]', line):
            continue
        pairs = re.findall(r'(F\d+)\s*[=:]\s*(Y1?|N)', line, re.IGNORECASE)
        for fid, val in pairs:
            if fid not in coverage:
                coverage[fid] = set()
            coverage[fid].add(val.upper())

    if not coverage:
        return None

    covered_count = 0
    not_covered_count = 0
    for fid, vals in coverage.items():
        if "Y" in vals or "Y1" in vals:
            covered_count += 1
        else:
            not_covered_count += 1

    total = covered_count + not_covered_count
    if total == 0:
        return None

    if not_covered_count == 0:
        return "not_novel"
    if covered_count == 0:
        return "novel"
    return "partially_novel"
# def derive_verdict_from_gap_analysis(report_content: str) -> str | None:
#     """Derive verdict from the gap analysis table in the agent's report.
#
#     The agent's gap analysis lists each feature with a Coverage Level
#     (STRONG / MODERATE / NONE-WEAK) and Core flag.
#
#     Logic for core features only:
#     - All STRONG/MODERATE -> not_novel
#     - All NONE/WEAK/NONE-WEAK -> novel
#     - Mixed -> partially_novel
#
#     Returns None if no gap analysis table found.
#     """
#     lines = report_content.split("\n")
#     in_gap = False
#     headers = []
#     feature_col = -1
#     coverage_col = -1
#     core_col = -1
#     coverage_levels = []
#
#     for i, line in enumerate(lines):
#         low = line.lower()
#         if "gap analysis" in low:
#             in_gap = True
#             continue
#
#         if in_gap and "|" in line:
#             cells = [c.strip() for c in line.strip().strip("|").split("|")]
#
#             # Detect header row
#             if not headers and any(
#                 "feature" in c.lower() or "coverage" in c.lower() for c in cells
#             ):
#                 headers = cells
#                 for j, h in enumerate(headers):
#                     hl = h.lower()
#                     if "coverage" in hl and "level" in hl:
#                         coverage_col = j
#                     elif "coverage" in hl and coverage_col == -1:
#                         coverage_col = j
#                     if "core" in hl:
#                         core_col = j
#                     if ("feature" in hl or j == 0) and feature_col == -1:
#                         feature_col = j
#                 continue
#
#             # Skip separator
#             if all(c.replace("-", "").replace(":", "").strip() == "" for c in cells):
#                 continue
#
#             # Data row
#             if (headers and coverage_col >= 0
#                     and len(cells) > coverage_col):
#                 cov_text = cells[coverage_col].upper()
#                 is_core = True  # Default to including all features
#                 if core_col >= 0 and len(cells) > core_col:
#                     core_text = cells[core_col].upper().strip()
#                     is_core = core_text in ("Y", "YES", "TRUE", "1", "CORE")
#                 if is_core:
#                     coverage_levels.append(cov_text)
#
#         elif in_gap and headers and "|" not in line and line.strip().startswith("#"):
#             break
#
#     if not coverage_levels:
#         return None
#
#     strong_or_moderate = sum(
#         1 for c in coverage_levels
#         if "STRONG" in c or "MODERATE" in c or "HIGH" in c or "FULL" in c
#     )
#     none_or_weak = sum(
#         1 for c in coverage_levels
#         if "NONE" in c or "WEAK" in c or "NO COVERAGE" in c or c.strip() in ("-", "N", "")
#     )
#
#     total = len(coverage_levels)
#
#     # If all core features have strong coverage -> not novel
#     if strong_or_moderate == total:
#         return "not_novel"
#     # If all core features have no/weak coverage -> novel
#     if none_or_weak == total:
#         return "novel"
#     # Mixed coverage -> partially novel
#     if strong_or_moderate > 0 and none_or_weak > 0:
#         return "partially_novel"
#     # Mostly covered (>50%) -> not novel
#     if strong_or_moderate > total / 2:
#         return "not_novel"
#     # Mostly uncovered -> novel
#     return "novel"


def extract_verdict_from_report(report_content: str) -> str | None:
    """Extract the novelty verdict from a final_report.md.

    Strategy (in priority order):
    1. Strict patterns matching explicit verdict statements
    2. Tightened heuristic patterns (only structured risk labels)
    3. Derive from gap analysis table coverage levels

    Returns:
        One of "novel", "partially_novel", "not_novel", or None if not found.
    """
    text = report_content.lower()

    # Step 1: Strict patterns
    for pattern in _VERDICT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            raw = match.group(1).strip().lower()
            # Map HIGH/MODERATE/LOW to verdict categories
            if raw == "high":
                return "novel"
            if raw == "moderate":
                return "partially_novel"
            if raw == "low":
                return "not_novel"
            normalized = raw.replace(" ", "_").replace("-", "_")
            if normalized in ("novel", "partially_novel", "not_novel"):
                return normalized

    # Step 2: Tightened heuristics (check not_novel first - most specific)
    for pattern in _HEURISTIC_NOT_NOVEL:
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            return "not_novel"

    for pattern in _HEURISTIC_PARTIALLY_NOVEL:
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            return "partially_novel"

    for pattern in _HEURISTIC_NOVEL:
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            return "novel"

    # Step 3: Derive from gap analysis table
    return derive_verdict_from_gap_analysis(report_content)


# ---------------------------------------------------------------------------
# DeepEval test case factory
# ---------------------------------------------------------------------------

def build_test_case(
    eval_trace: dict[str, Any],
    ground_truth: dict[str, Any],
    session_path: Path,
    case_id: str = "",
) -> LLMTestCase:
    """Build a DeepEval LLMTestCase carrying scorer data in additional_metadata."""
    report_content = load_session_artifact(session_path, "final_report.md")
    gt_verdict = ground_truth.get("verdict", {})
    expected = gt_verdict.get("verdict", "") if isinstance(gt_verdict, dict) else str(gt_verdict)

    return LLMTestCase(
        input=case_id or eval_trace.get("run_metadata", {}).get("session_id", "unknown"),
        actual_output=report_content[:2000] if report_content else "No report generated",
        expected_output=expected,
        additional_metadata={
            "eval_trace": eval_trace,
            "ground_truth": ground_truth,
            "session_path": str(session_path),
        },
    )