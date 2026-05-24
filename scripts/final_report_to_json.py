"""Convert final_report.md from a session folder into a structured JSON file.

Parses all 11 sections of the novelty-checker final report and writes
``final_report.json`` alongside the source markdown in the same folder.

Usage:
    # Direct path to any markdown file
    python scripts/final_report_to_json.py --file sessions/20260413_145045_8f93bab1/final_report.md

    # Auto-pick the most-recent session that has a final_report.md
    python scripts/final_report_to_json.py --latest

    # Write to a custom output path
    python scripts/final_report_to_json.py --file /any/path/report.md --output /tmp/report.json
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------

def _parse_md_table(lines: list[str]) -> list[dict[str, str]]:
    """Parse a GFM-style pipe table into a list of dicts (header → cell value)."""
    rows = [l for l in lines if l.strip().startswith("|")]
    if len(rows) < 2:
        return []
    headers = [h.strip() for h in rows[0].strip().strip("|").split("|")]
    records: list[dict[str, str]] = []
    for row in rows[2:]:  # skip separator line
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        # pad / trim to match header count
        cells += [""] * (len(headers) - len(cells))
        records.append(dict(zip(headers, cells[: len(headers)])))
    return records


def _strip_md_bold(text: str) -> str:
    return re.sub(r"\*\*(.*?)\*\*", r"\1", text)


def _join_lines(lines: list[str]) -> str:
    """Join non-blank lines with '; ' as separator."""
    return "; ".join(line.strip() for line in lines if line.strip())


def _section_lines(text: str, heading: str) -> list[str]:
    """Return lines belonging to a top-level '# N.' section by its heading keyword."""
    pattern = re.compile(r"^#\s+\d+\.", re.MULTILINE)
    sections = pattern.split(text)
    titles = pattern.findall(text)
    for title, body in zip(titles, sections[1:]):
        full = (title + body).strip()
        if heading.lower() in full.lower():
            return full.splitlines()
    return []


def _subsection_text(lines: list[str], heading: str) -> list[str]:
    """Return lines under a '## heading' subsection."""
    result: list[str] = []
    inside = False
    for line in lines:
        if re.match(r"^##\s+" + re.escape(heading), line, re.IGNORECASE):
            inside = True
            continue
        if inside:
            if re.match(r"^##\s+", line):
                break
            result.append(line)
    return result


# ---------------------------------------------------------------------------
# Per-section parsers
# ---------------------------------------------------------------------------

def _parse_section1(lines: list[str]) -> dict[str, Any]:
    """Key Finding / Executive Summary."""
    result: dict[str, Any] = {}

    # Coverage snapshot paragraph (text after Key Finding heading, before the table)
    snapshot_lines: list[str] = []
    in_snapshot = False
    for line in lines:
        if re.match(r"^##\s+Key Finding", line, re.IGNORECASE):
            in_snapshot = True
            continue
        if in_snapshot:
            if re.match(r"^##\s+", line):
                break
            snapshot_lines.append(line)
    result["coverage_snapshot"] = _join_lines(snapshot_lines)

    # Gap Analysis Table
    gap_lines = _subsection_text(lines, "Gap Analysis Table")
    result["gap_analysis"] = _parse_md_table(gap_lines)

    # Technology Trends
    trend_lines = _subsection_text(lines, "Technology Trends")
    result["technology_trends"] = _join_lines(trend_lines)

    # Novelty Risk
    risk_lines = _subsection_text(lines, "Novelty Risk")
    result["novelty_risk"] = _join_lines(risk_lines)

    return result


def _parse_section2(lines: list[str]) -> list[dict[str, str]]:
    """Scope — single table."""
    return _parse_md_table(lines)


def _parse_section3(lines: list[str]) -> list[dict[str, str]]:
    """Feature Plan — single table."""
    return _parse_md_table(lines)


def _parse_section4(lines: list[str]) -> dict[str, Any]:
    """Feature Matrix."""
    legend_match = re.search(r"\*\*Legend:\*\*(.*)", "\n".join(lines))
    legend = legend_match.group(1).strip() if legend_match else ""
    xcat_match = re.search(r"\*\*X-category key:\*\*(.*)", "\n".join(lines))
    xcat = xcat_match.group(1).strip() if xcat_match else ""
    return {
        "legend": legend,
        "x_category_key": xcat,
        "references": _parse_md_table(lines),
    }


def _parse_section5(lines: list[str]) -> list[dict[str, str]]:
    """C-level references table."""
    return _parse_md_table(lines)


def _parse_section6(lines: list[str]) -> list[dict[str, str]]:
    """Patents Record View — one table per patent, keyed by ## heading."""
    records: list[dict[str, str]] = []
    current_pub: str | None = None
    current_lines: list[str] = []

    def _flush() -> None:
        if current_pub and current_lines:
            rows = _parse_md_table(current_lines)
            rec: dict[str, str] = {"publication_number": current_pub}
            for r in rows:
                field = r.get("Field", "").strip()
                value = r.get("Details", "").strip()
                if field:
                    key = re.sub(r"\s+", "_", field.lower().strip("()"))
                    rec[key] = value
            records.append(rec)

    for line in lines:
        m = re.match(r"^##\s+(.*)", line)
        if m:
            _flush()
            current_pub = m.group(1).strip()
            current_lines = []
        elif current_pub is not None:
            current_lines.append(line)
    _flush()
    return records


def _parse_section7(lines: list[str]) -> dict[str, Any]:
    """NPL Record View — mostly free text."""
    body = _join_lines(lines[1:])  # skip section heading line
    return {"notes": body}


def _parse_section8(lines: list[str]) -> list[dict[str, str]]:
    """Transactional Search Summary — table."""
    return _parse_md_table(lines)


def _parse_section9(lines: list[str]) -> dict[str, Any]:
    """Landscape Overview."""
    return {
        "dominant_themes": _join_lines(_subsection_text(lines, "Dominant Themes")),
        "notable_assignees": _join_lines(_subsection_text(lines, "Notable Assignees")),
        "density_indicators": _join_lines(_subsection_text(lines, "Density Indicators")),
    }


def _parse_section10(lines: list[str]) -> dict[str, Any]:
    """Search Traceability."""
    results_list_lines = _subsection_text(lines, "10.1 Results List")
    search_log_lines = _subsection_text(lines, "10.2 Search Log")
    return {
        "results_list": _join_lines(results_list_lines),
        "search_log": _parse_md_table(search_log_lines),
    }


def _parse_section11(lines: list[str]) -> dict[str, Any]:
    """Next Steps."""
    qa_lines = _subsection_text(lines, "Search Quality")
    # Numbered next-steps bullets (everything before the ## subsection)
    steps: list[str] = []
    for line in lines:
        if re.match(r"^##\s+", line):
            break
        m = re.match(r"^\d+\.\s+\*\*(.*?)\*\*(.*)", line)
        if m:
            steps.append(f"{m.group(1)}: {m.group(2).strip()}")
        elif re.match(r"^\d+\.\s+", line):
            steps.append(line.strip())
    return {
        "recommended_next_steps": steps,
        "search_quality_notes": _join_lines(qa_lines),
    }


# ---------------------------------------------------------------------------
# Top-level parser
# ---------------------------------------------------------------------------

SECTION_MAP = {
    "key finding": ("executive_summary", _parse_section1),
    "scope": ("scope", _parse_section2),
    "feature plan": ("feature_plan", _parse_section3),
    "feature matrix": ("feature_matrix", _parse_section4),
    "peripherally related": ("c_level_references", _parse_section5),
    "patents record view": ("patents_record_view", _parse_section6),
    "npl record view": ("npl_record_view", _parse_section7),
    "transactional search summary": ("search_summary", _parse_section8),
    "landscape overview": ("landscape_overview", _parse_section9),
    "search traceability": ("search_traceability", _parse_section10),
    "next steps": ("next_steps", _parse_section11),
}


def parse_final_report(md_path: Path) -> dict[str, Any]:
    text = md_path.read_text(encoding="utf-8")

    report: dict[str, Any] = {
        "source_file": str(md_path),
        "session_id": md_path.parent.name,
    }

    for keyword, (key, parser_fn) in SECTION_MAP.items():
        lines = _section_lines(text, keyword)
        if not lines:
            _logger.warning("Section '%s' not found in report.", keyword)
            report[key] = None
            continue
        try:
            report[key] = parser_fn(lines)
        except Exception as exc:  # pragma: no cover
            _logger.error("Failed to parse section '%s': %s", keyword, exc)
            report[key] = {"parse_error": str(exc)}

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _find_latest_md(sessions_root: Path) -> Path | None:
    candidates = sorted(
        (s / "final_report.md" for s in sessions_root.iterdir() if (s / "final_report.md").exists()),
        key=lambda p: p.parent.name,
        reverse=True,
    )
    return candidates[0] if candidates else None


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description="Convert any final_report.md → JSON")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", type=Path, help="Direct path to the .md file to convert")
    group.add_argument(
        "--latest",
        action="store_true",
        help="Auto-pick the most recent session under sessions/",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path (default: same folder as the .md file, with .json extension)",
    )
    args = parser.parse_args(argv)

    # Resolve markdown file path
    if args.latest:
        sessions_root = Path(__file__).parent.parent / "sessions"
        md_path = _find_latest_md(sessions_root)
        if md_path is None:
            _logger.error("No session with final_report.md found under %s", sessions_root)
            return 1
        _logger.info("Using latest session: %s", md_path.parent)
    else:
        md_path = args.file.expanduser().resolve()

    if not md_path.exists():
        _logger.error("File not found: %s", md_path)
        return 1

    out_path: Path = args.output or md_path.with_suffix(".json")

    _logger.info("Parsing %s …", md_path)
    data = parse_final_report(md_path)

    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    _logger.info("Written → %s", out_path)
    print(f"JSON saved to: {out_path.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
