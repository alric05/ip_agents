"""Report coverage verification for novelty search sessions.

Compares references found during research against what appears in the
final report, identifying any A/B-level references that were dropped.

Usage:
    # Standalone CLI
    python -m src.novelty_checker.utils.report_coverage sessions/<id>

    # Programmatic (after eval run)
    from src.novelty_checker.utils.report_coverage import (
        verify_report_coverage_from_path,
        verify_report_coverage_from_eval,
    )
    result = verify_report_coverage_from_path("sessions/<id>")
    print(result.to_markdown())

    # After eval_runner
    from src.novelty_checker.eval_runner import run_novelty_check_e2e
    eval_result = run_novelty_check_e2e(idea="...")
    coverage = verify_report_coverage_from_eval(eval_result)
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.novelty_checker.eval_runner import EvalRunResult


# =============================================================================
# Enums & Data Structures
# =============================================================================


class Severity(Enum):
    """Severity level for coverage findings."""

    CRITICAL = "CRITICAL"  # Missing A-ref
    WARNING = "WARNING"  # Missing B-ref
    INFO = "INFO"  # Missing C-ref (expected)
    UNEXPECTED = "UNEXPECTED"  # Ref in report but not in any source


@dataclass
class FoundReference:
    """A reference found during the search session."""

    ref_id: str  # Canonical (normalized) publication number
    raw_ids: set[str]  # All raw ID variants seen across sources
    triage: str  # A, B, C, or "?" if unknown
    title: str  # Best title found
    sources: set[str]  # Which data sources mention it


@dataclass
class ReportMention:
    """A reference mentioned in the final report."""

    ref_id: str  # Canonical (normalized) publication number
    raw_id: str  # Raw ID as it appears in the report
    sections: set[str]  # Which report sections mention it


@dataclass
class CoverageGap:
    """A single coverage gap finding."""

    ref_id: str
    triage: str
    severity: Severity
    title: str
    found_in_sources: set[str]
    message: str


@dataclass
class CoverageResult:
    """Complete result of report coverage verification."""

    # Counts by triage from source data
    total_found_a: int = 0
    total_found_b: int = 0
    total_found_c: int = 0
    total_in_report: int = 0

    # Detailed gaps
    missing_a_refs: list[CoverageGap] = field(default_factory=list)
    missing_b_refs: list[CoverageGap] = field(default_factory=list)
    missing_c_refs: list[CoverageGap] = field(default_factory=list)
    unexpected_refs: list[CoverageGap] = field(default_factory=list)

    # Coverage scores
    a_coverage_pct: float = 0.0
    b_coverage_pct: float = 0.0
    overall_coverage_pct: float = 0.0

    # Full reference sets for inspection
    found_references: dict[str, FoundReference] = field(default_factory=dict)
    report_mentions: dict[str, ReportMention] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        """True if all A and B refs are in the report."""
        return len(self.missing_a_refs) == 0 and len(self.missing_b_refs) == 0

    def to_markdown(self) -> str:
        """Generate a human-readable markdown verification report."""
        lines = ["# Report Coverage Verification", ""]

        # Summary table
        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| A-refs found in search | {self.total_found_a} |")
        lines.append(f"| B-refs found in search | {self.total_found_b} |")
        lines.append(f"| C-refs found in search | {self.total_found_c} |")
        lines.append(f"| Total refs in report | {self.total_in_report} |")
        lines.append(f"| A-ref coverage | {self.a_coverage_pct:.0f}% |")
        lines.append(f"| B-ref coverage | {self.b_coverage_pct:.0f}% |")
        lines.append(f"| Overall A+B coverage | {self.overall_coverage_pct:.0f}% |")
        lines.append("")

        # Verdict
        if self.is_complete:
            lines.append("## PASS -- All A and B references covered")
        else:
            lines.append("## GAPS DETECTED")
        lines.append("")

        # Missing A-refs
        if self.missing_a_refs:
            lines.append(
                f"### CRITICAL: Missing A-refs ({len(self.missing_a_refs)})"
            )
            lines.append("")
            for gap in self.missing_a_refs:
                lines.append(f"- **{gap.ref_id}** -- {gap.title[:60]}")
                lines.append(f"  Found in: {', '.join(gap.found_in_sources)}")
            lines.append("")

        # Missing B-refs
        if self.missing_b_refs:
            lines.append(
                f"### WARNING: Missing B-refs ({len(self.missing_b_refs)})"
            )
            lines.append("")
            for gap in self.missing_b_refs:
                lines.append(f"- **{gap.ref_id}** -- {gap.title[:60]}")
                lines.append(f"  Found in: {', '.join(gap.found_in_sources)}")
            lines.append("")

        # Missing C-refs
        if self.missing_c_refs:
            lines.append(
                f"### INFO: Missing C-refs ({len(self.missing_c_refs)}) -- expected"
            )
            lines.append("")
            lines.append("C-refs are peripheral and may be intentionally omitted.")
            lines.append(f"Count: {len(self.missing_c_refs)} C-refs not in report.")
            lines.append("")

        # Unexpected refs
        if self.unexpected_refs:
            lines.append(
                f"### UNEXPECTED: Refs in report not in any source "
                f"({len(self.unexpected_refs)})"
            )
            lines.append("")
            for gap in self.unexpected_refs:
                lines.append(f"- **{gap.ref_id}**")
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON output."""
        return {
            "is_complete": self.is_complete,
            "total_found_a": self.total_found_a,
            "total_found_b": self.total_found_b,
            "total_found_c": self.total_found_c,
            "total_in_report": self.total_in_report,
            "a_coverage_pct": round(self.a_coverage_pct, 1),
            "b_coverage_pct": round(self.b_coverage_pct, 1),
            "overall_coverage_pct": round(self.overall_coverage_pct, 1),
            "missing_a_refs": [g.ref_id for g in self.missing_a_refs],
            "missing_b_refs": [g.ref_id for g in self.missing_b_refs],
            "missing_c_refs": [g.ref_id for g in self.missing_c_refs],
            "unexpected_refs": [g.ref_id for g in self.unexpected_refs],
        }


# =============================================================================
# Publication Number Normalization
# =============================================================================

# Patent pattern: 2-3 letter country code + digits + optional kind code
_PATENT_PUB_RE = re.compile(
    r"^([A-Z]{2,3})"  # Country code (US, EP, CN, TWI, etc.)
    r"(\d+)"  # Number part
    r"([A-Z]\d?)?"  # Optional kind code (A, A1, B, B1, U, etc.)
    r"$"
)


def normalize_pub_number(raw: str) -> str:
    """Normalize a publication number for matching.

    Strips the trailing digit from kind codes so that variants like
    US20090071279A1 and US20090071279A match to the same canonical form.

    Non-patent identifiers (WOS, DOI) are returned as-is.
    """
    raw = raw.strip()

    # Non-patent identifiers
    if raw.startswith(("WOS:", "DOI:", "10.")):
        return raw

    m = _PATENT_PUB_RE.match(raw)
    if not m:
        return raw

    country = m.group(1)
    number = m.group(2)
    kind = m.group(3) or ""

    # Normalize kind code: keep the letter, drop trailing digit
    # US20090071279A1 -> US20090071279A
    # FR2372998B1     -> FR2372998B
    # CN215444943U    -> CN215444943U  (no trailing digit, unchanged)
    if len(kind) == 2 and kind[0].isalpha() and kind[1].isdigit():
        kind = kind[0]

    return f"{country}{number}{kind}"


# =============================================================================
# Reference Extraction Regex
# =============================================================================

# Matches patent publication numbers, WOS IDs, and DOIs in text
_PUB_NUMBER_RE = re.compile(
    r"(?<![a-zA-Z])"  # Not preceded by a letter (avoid mid-word matches)
    r"("
    r"[A-Z]{2,3}\d{5,}[A-Z]?\d?"  # Patents (US, EP, CN, JP, TWI, etc.)
    r"|WOS:\d{15}"  # Web of Science IDs
    r"|10\.\d{4,}/\S+"  # DOIs
    r")"
)


# =============================================================================
# Parsers
# =============================================================================


def parse_references_md(content: str) -> dict[str, FoundReference]:
    """Parse references.md into FoundReference dict keyed by normalized pub number.

    Handles duplicate rows by deduplicating on normalized ID (last triage wins).
    """
    refs: dict[str, FoundReference] = {}

    for line in content.split("\n"):
        line = line.strip()
        if not line.startswith("|") or "---" in line:
            continue

        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) < 6:
            continue

        raw_id = cells[0]
        # Skip header row
        if raw_id.lower() in ("ref id", "publication #", "publication number"):
            continue

        # Skip if it doesn't look like a publication number
        if not _PUB_NUMBER_RE.search(raw_id):
            continue

        norm_id = normalize_pub_number(raw_id)
        title = cells[2] if len(cells) > 2 else ""
        triage = cells[5].strip() if len(cells) > 5 else "?"

        if norm_id in refs:
            refs[norm_id].raw_ids.add(raw_id)
            refs[norm_id].triage = triage
            refs[norm_id].sources.add("references_md")
        else:
            refs[norm_id] = FoundReference(
                ref_id=norm_id,
                raw_ids={raw_id},
                triage=triage,
                title=title,
                sources={"references_md"},
            )

    return refs


def parse_accumulator_json(content: str) -> dict[str, FoundReference]:
    """Parse findings_accumulator.json or findings_auto_accumulator.json.

    Handles key name variants: ref_id, publication_number, pub_number.
    """
    refs: dict[str, FoundReference] = {}

    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return refs

    for ref_dict in data.get("all_references", []):
        raw_id = (
            ref_dict.get("ref_id")
            or ref_dict.get("publication_number")
            or ref_dict.get("pub_number")
            or ""
        )
        if not raw_id:
            continue

        norm_id = normalize_pub_number(raw_id)
        triage = ref_dict.get("triage", ref_dict.get("relevance", "?"))
        title = ref_dict.get("title", "")

        if norm_id in refs:
            refs[norm_id].raw_ids.add(raw_id)
            refs[norm_id].sources.add("accumulator_json")
        else:
            refs[norm_id] = FoundReference(
                ref_id=norm_id,
                raw_ids={raw_id},
                triage=triage,
                title=title,
                sources={"accumulator_json"},
            )

    return refs


def parse_round_findings_md(content: str, source_tag: str) -> dict[str, FoundReference]:
    """Extract references from per-round findings markdown via regex sweep.

    Triage is set to "?" since round files don't reliably indicate it;
    the triage from references.md takes precedence during merge.
    """
    refs: dict[str, FoundReference] = {}

    for match in _PUB_NUMBER_RE.finditer(content):
        raw_id = match.group(1)
        norm_id = normalize_pub_number(raw_id)

        if norm_id in refs:
            refs[norm_id].raw_ids.add(raw_id)
        else:
            refs[norm_id] = FoundReference(
                ref_id=norm_id,
                raw_ids={raw_id},
                triage="?",
                title="",
                sources={source_tag},
            )

    return refs


def _detect_report_sections(content: str) -> list[tuple[int, int, str]]:
    """Detect section ranges in the report for tagging mentions."""
    section_pattern = re.compile(r"^##\s+(\d+)\.\s+(.+)", re.MULTILINE)
    sections: list[tuple[int, int, str]] = []
    matches = list(section_pattern.finditer(content))

    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        section_num = m.group(1)
        sections.append((start, end, f"section_{section_num}"))

    return sections


def _section_at_position(pos: int, sections: list[tuple[int, int, str]]) -> str:
    """Determine which section a character position falls in."""
    for start, end, name in sections:
        if start <= pos < end:
            return name
    return "other"


def parse_report_references(report_content: str) -> dict[str, ReportMention]:
    """Extract all references mentioned in the final report.

    Scans the Feature Matrix (Section 4) and all other sections,
    tagging each mention with the section it appears in.
    """
    from src.novelty_checker.utils.feature_matrix import (
        extract_feature_matrix_from_markdown,
    )

    mentions: dict[str, ReportMention] = {}
    section_ranges = _detect_report_sections(report_content)

    # Parse Feature Matrix section specifically
    matrix_content = extract_feature_matrix_from_markdown(report_content)
    if matrix_content:
        for match in _PUB_NUMBER_RE.finditer(matrix_content):
            raw_id = match.group(1)
            norm_id = normalize_pub_number(raw_id)
            if norm_id in mentions:
                mentions[norm_id].sections.add("feature_matrix")
            else:
                mentions[norm_id] = ReportMention(
                    ref_id=norm_id,
                    raw_id=raw_id,
                    sections={"feature_matrix"},
                )

    # Full report sweep for inline mentions
    for match in _PUB_NUMBER_RE.finditer(report_content):
        raw_id = match.group(1)
        norm_id = normalize_pub_number(raw_id)
        pos = match.start()
        section = _section_at_position(pos, section_ranges)

        if norm_id in mentions:
            mentions[norm_id].sections.add(section)
        else:
            mentions[norm_id] = ReportMention(
                ref_id=norm_id,
                raw_id=raw_id,
                sections={section},
            )

    return mentions


# =============================================================================
# Core Logic
# =============================================================================


def merge_found_references(
    *sources: dict[str, FoundReference],
) -> dict[str, FoundReference]:
    """Merge references from multiple data sources.

    Sources should be passed in priority order (first = highest triage priority).
    Typically: references_md first, then accumulator_json, then round findings.
    """
    merged: dict[str, FoundReference] = {}

    for source_refs in sources:
        for norm_id, ref in source_refs.items():
            if norm_id in merged:
                existing = merged[norm_id]
                existing.raw_ids |= ref.raw_ids
                existing.sources |= ref.sources
                # Only override triage if current is unknown
                if existing.triage == "?":
                    existing.triage = ref.triage
                # Prefer longer title
                if len(ref.title) > len(existing.title):
                    existing.title = ref.title
            else:
                merged[norm_id] = FoundReference(
                    ref_id=norm_id,
                    raw_ids=set(ref.raw_ids),
                    triage=ref.triage,
                    title=ref.title,
                    sources=set(ref.sources),
                )

    return merged


def compute_coverage(
    found: dict[str, FoundReference],
    reported: dict[str, ReportMention],
) -> CoverageResult:
    """Compare found references against report mentions."""
    result = CoverageResult()
    result.found_references = found
    result.report_mentions = reported

    a_refs = {k: v for k, v in found.items() if v.triage == "A"}
    b_refs = {k: v for k, v in found.items() if v.triage == "B"}
    c_refs = {k: v for k, v in found.items() if v.triage == "C"}

    result.total_found_a = len(a_refs)
    result.total_found_b = len(b_refs)
    result.total_found_c = len(c_refs)
    result.total_in_report = len(reported)

    reported_norm_ids = set(reported.keys())

    # Check A-refs
    a_in_report = 0
    for norm_id, ref in a_refs.items():
        if norm_id in reported_norm_ids:
            a_in_report += 1
        else:
            result.missing_a_refs.append(
                CoverageGap(
                    ref_id=norm_id,
                    triage="A",
                    severity=Severity.CRITICAL,
                    title=ref.title,
                    found_in_sources=ref.sources,
                    message=f"A-level ref {norm_id} ({ref.title[:50]}) missing from report",
                )
            )

    # Check B-refs
    b_in_report = 0
    for norm_id, ref in b_refs.items():
        if norm_id in reported_norm_ids:
            b_in_report += 1
        else:
            result.missing_b_refs.append(
                CoverageGap(
                    ref_id=norm_id,
                    triage="B",
                    severity=Severity.WARNING,
                    title=ref.title,
                    found_in_sources=ref.sources,
                    message=f"B-level ref {norm_id} ({ref.title[:50]}) missing from report",
                )
            )

    # Check C-refs
    for norm_id, ref in c_refs.items():
        if norm_id not in reported_norm_ids:
            result.missing_c_refs.append(
                CoverageGap(
                    ref_id=norm_id,
                    triage="C",
                    severity=Severity.INFO,
                    title=ref.title,
                    found_in_sources=ref.sources,
                    message=f"C-level ref {norm_id} not in report (expected -- peripheral)",
                )
            )

    # Check for unexpected refs (in report but not in any source)
    found_norm_ids = set(found.keys())
    for norm_id, mention in reported.items():
        if norm_id not in found_norm_ids:
            result.unexpected_refs.append(
                CoverageGap(
                    ref_id=norm_id,
                    triage="?",
                    severity=Severity.UNEXPECTED,
                    title="",
                    found_in_sources=set(),
                    message=(
                        f"Ref {norm_id} appears in report "
                        f"(sections: {', '.join(mention.sections)}) "
                        f"but not in any search data source"
                    ),
                )
            )

    # Compute percentages
    result.a_coverage_pct = (a_in_report / len(a_refs) * 100) if a_refs else 100.0
    result.b_coverage_pct = (b_in_report / len(b_refs) * 100) if b_refs else 100.0
    ab_total = len(a_refs) + len(b_refs)
    ab_in_report = a_in_report + b_in_report
    result.overall_coverage_pct = (ab_in_report / ab_total * 100) if ab_total else 100.0

    return result


# =============================================================================
# Entry Points
# =============================================================================


def verify_report_coverage_from_path(session_path: str | Path) -> CoverageResult:
    """Verify report coverage from a session directory path.

    Args:
        session_path: Path to the session directory containing
            references.md, final_report.md, findings/, etc.

    Returns:
        CoverageResult with full analysis.
    """
    session_path = Path(session_path)
    sources: list[dict[str, FoundReference]] = []

    # Primary: references.md (highest triage priority)
    refs_md_path = session_path / "references.md"
    if refs_md_path.exists():
        sources.append(parse_references_md(refs_md_path.read_text(encoding="utf-8")))

    # Secondary: findings_accumulator.json
    accum_path = session_path / "findings_accumulator.json"
    if accum_path.exists():
        sources.append(parse_accumulator_json(accum_path.read_text(encoding="utf-8")))

    # Tertiary: findings_auto_accumulator.json
    auto_accum_path = session_path / "findings_auto_accumulator.json"
    if auto_accum_path.exists():
        sources.append(
            parse_accumulator_json(auto_accum_path.read_text(encoding="utf-8"))
        )

    # Per-round findings
    findings_dir = session_path / "findings"
    if findings_dir.exists():
        for f in sorted(findings_dir.iterdir()):
            if f.is_file() and f.suffix == ".md":
                tag = f"round_findings_{f.stem}"
                sources.append(
                    parse_round_findings_md(f.read_text(encoding="utf-8"), tag)
                )

    all_found = merge_found_references(*sources)

    # Parse final report
    report_path = session_path / "final_report.md"
    if not report_path.exists():
        result = CoverageResult()
        result.found_references = all_found
        for ref in all_found.values():
            severity = (
                Severity.CRITICAL
                if ref.triage == "A"
                else Severity.WARNING if ref.triage == "B" else Severity.INFO
            )
            gap = CoverageGap(
                ref_id=ref.ref_id,
                triage=ref.triage,
                severity=severity,
                title=ref.title,
                found_in_sources=ref.sources,
                message=f"No final_report.md found -- ref {ref.ref_id} unverifiable",
            )
            if ref.triage == "A":
                result.missing_a_refs.append(gap)
            elif ref.triage == "B":
                result.missing_b_refs.append(gap)
            else:
                result.missing_c_refs.append(gap)
        result.total_found_a = sum(1 for r in all_found.values() if r.triage == "A")
        result.total_found_b = sum(1 for r in all_found.values() if r.triage == "B")
        result.total_found_c = sum(1 for r in all_found.values() if r.triage == "C")
        return result

    report_content = report_path.read_text(encoding="utf-8")
    report_mentions = parse_report_references(report_content)

    return compute_coverage(all_found, report_mentions)


def verify_report_coverage_from_eval(eval_result: EvalRunResult) -> CoverageResult:
    """Verify report coverage from an EvalRunResult.

    Uses the artifacts dict from the eval run and falls back to
    reading from session_path for files not in artifacts.
    """
    artifacts = eval_result.artifacts
    sources: list[dict[str, FoundReference]] = []

    # Primary: references.md
    if "references.md" in artifacts:
        sources.append(parse_references_md(artifacts["references.md"]))

    # Secondary: findings_accumulator.json
    if "findings_accumulator.json" in artifacts:
        sources.append(
            parse_accumulator_json(artifacts["findings_accumulator.json"])
        )
    else:
        accum_path = eval_result.session_path / "findings_accumulator.json"
        if accum_path.exists():
            sources.append(
                parse_accumulator_json(accum_path.read_text(encoding="utf-8"))
            )

    # Tertiary: findings_auto_accumulator.json
    if "findings_auto_accumulator.json" in artifacts:
        sources.append(
            parse_accumulator_json(artifacts["findings_auto_accumulator.json"])
        )

    # Per-round findings from artifacts
    for key, content in artifacts.items():
        if key.startswith("findings/") and key.endswith(".md"):
            tag = f"round_findings_{Path(key).stem}"
            sources.append(parse_round_findings_md(content, tag))

    all_found = merge_found_references(*sources)

    # Parse report
    report_content = eval_result.final_report or ""
    if not report_content and "final_report.md" in artifacts:
        report_content = artifacts["final_report.md"]

    if not report_content:
        result = CoverageResult()
        result.found_references = all_found
        return result

    report_mentions = parse_report_references(report_content)
    return compute_coverage(all_found, report_mentions)


# =============================================================================
# CLI
# =============================================================================


def main() -> None:
    """CLI entry point for standalone verification."""
    if len(sys.argv) < 2:
        print(
            "Usage: python -m src.novelty_checker.utils.report_coverage <session_path>"
        )
        sys.exit(1)

    session_path = Path(sys.argv[1])
    if not session_path.exists():
        print(f"Error: Session path does not exist: {session_path}")
        sys.exit(1)

    result = verify_report_coverage_from_path(session_path)
    print(result.to_markdown())

    # Also print JSON summary
    print("\n---\n")
    print(json.dumps(result.to_dict(), indent=2))

    sys.exit(0 if result.is_complete else 1)


if __name__ == "__main__":
    main()
