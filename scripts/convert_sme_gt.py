"""Convert SME CSV ground truth files into scorer-compatible JSON fixtures.

Reads the semi-structured CSVs exported from the GT Form Template and
produces the fixture files expected by the evaluation scorers:

    disclosure.md, gt_features.json, gt_references.json,
    gt_verdict.json, gt_search_strategy.md, metadata.json

Usage:
    python scripts/convert_sme_gt.py \
        --input-dir SME_cases/ \
        --case-id C19904 \
        --output-dir evals/golden_datasets/cases/C19904
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
from pathlib import Path

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CSV reading helpers
# ---------------------------------------------------------------------------

def _read_csv(path: Path) -> list[list[str]]:
    """Read a CSV file and return all rows as list of lists."""
    raw_bytes = path.read_bytes()
    # Try UTF-8 first, fall back to Windows-1252 (common for Excel exports)
    try:
        raw = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raw = raw_bytes.decode("cp1252", errors="replace")
    # Clean up non-breaking spaces and other oddities from spreadsheet exports
    raw = raw.replace("\xa0", " ").replace("\u2013", "-").replace("\u2019", "'")
    raw = raw.replace("\ufffd", "-")  # replacement chars from mixed encodings
    return list(csv.reader(raw.splitlines()))


def _find_file(input_dir: Path, case_id: str, part_name: str) -> Path | None:
    """Find a CSV file matching case_id and part_name substring."""
    for p in input_dir.iterdir():
        if p.suffix == ".csv" and case_id in p.name and part_name in p.name:
            return p
    return None


# ---------------------------------------------------------------------------
# Part A: Invention Disclosure -> disclosure.md
# ---------------------------------------------------------------------------

def convert_disclosure(rows: list[list[str]]) -> str:
    """Convert Part A CSV into disclosure.md content."""
    fields: dict[str, str] = {}
    for row in rows:
        if len(row) >= 2 and row[0].strip():
            fields[row[0].strip()] = row[1].strip()

    parts = []
    title = fields.get("Title", "")
    if title:
        parts.append(f"# {title}\n")

    tech_field = fields.get("Technical Field", "")
    if tech_field:
        parts.append(f"## Technical Field\n\n{tech_field}\n")

    background = fields.get("Background / Problem Statement", "")
    if background:
        parts.append(f"## Background / Problem Statement\n\n{background}\n")

    aspects = fields.get("Key Technical Aspects", "")
    if aspects:
        parts.append(f"## Key Technical Aspects\n\n{aspects}\n")

    awareness = fields.get("Inventor's Prior Art Awareness(Optional)", "")
    if awareness and not awareness.startswith("["):
        parts.append(f"## Inventor's Prior Art Awareness\n\n{awareness}\n")

    constraints = fields.get("Known Constraints(Optional)", "")
    if constraints and not constraints.startswith("["):
        parts.append(f"## Known Constraints\n\n{constraints}\n")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Part B: Expected Key Features -> gt_features.json
# ---------------------------------------------------------------------------

_CPC_PATTERN = re.compile(
    r"[A-HY]\d{2}[A-Z]?\s*\d{0,4}(?:/\d{1,6})?"
)


def _split_cpc_codes(raw: str) -> list[str]:
    """Extract individual CPC/IPC codes from a possibly-concatenated string.

    Spreadsheet export may strip newlines, producing e.g.
    'B63B 35/00B63B 2035B63B 2035/4453F24S20/70Y02E10/50'
    """
    return [m.strip() for m in _CPC_PATTERN.findall(raw) if m.strip()]


def _split_keywords(raw: str) -> str:
    """Re-insert newlines between keyword groups that got concatenated.

    Detects transitions like '...WATER+SOLAR+...' and inserts newlines.
    """
    if not raw:
        return ""
    # Insert newline before uppercase keyword groups that follow
    # a closing wildcard/word boundary without whitespace
    cleaned = re.sub(
        r"([+?])\s*([A-Z_\"(])",
        r"\1\n\2",
        raw,
    )
    return cleaned


def convert_features(rows: list[list[str]]) -> list[dict]:
    """Convert Part B Expected Key Features CSV into feature dicts.

    Handles multi-line cells where continuation rows have an empty ID column.
    """
    # Find the header row (row with "ID" in first column)
    header_idx = None
    for i, row in enumerate(rows):
        if row and row[0].strip().upper() == "ID":
            header_idx = i
            break

    if header_idx is None:
        _logger.warning("No header row found in features CSV")
        return []

    headers = [h.strip() for h in rows[header_idx]]
    features: list[dict] = []
    current_feature: dict | None = None

    for row in rows[header_idx + 1:]:
        if not row or all(c.strip() == "" for c in row):
            continue

        # Pad row to match header length
        while len(row) < len(headers):
            row.append("")

        row_id = row[0].strip()

        if row_id:
            # New feature row
            if current_feature is not None:
                features.append(current_feature)
            current_feature = {}
            for h, val in zip(headers, row):
                current_feature[h.strip()] = val.strip()
        elif current_feature is not None:
            # Continuation row — append non-empty cells to previous feature
            for h, val in zip(headers, row):
                val = val.strip()
                if val:
                    key = h.strip()
                    existing = current_feature.get(key, "")
                    if existing:
                        current_feature[key] = existing + "\n" + val
                    else:
                        current_feature[key] = val

    if current_feature is not None:
        features.append(current_feature)

    # Normalize to scorer-expected format
    normalized: list[dict] = []
    for f in features:
        cpc_raw = f.get("Related CPC/IPC", "")
        cpc_list = _split_cpc_codes(cpc_raw)

        # Split concatenated keywords (newlines may have been stripped)
        keywords_raw = f.get("Keywords", "")
        keywords = _split_keywords(keywords_raw)

        normalized.append({
            "id": f.get("ID", ""),
            "name": f.get("Name", ""),
            "description": f.get("Description", ""),
            "core": f.get("Core?", "N").strip().upper() or "N",
            "keywords": keywords,
            "type": f.get("Type", ""),
            "related_cpc": cpc_list,
        })

    return normalized


# ---------------------------------------------------------------------------
# Part B: Blocking Prior Art -> gt_references.json
# ---------------------------------------------------------------------------

def convert_references(rows: list[list[str]]) -> dict:
    """Convert Part B Blocking Prior Art CSV into references dict.

    Parses three sections:
    1. Reference Summary table
    2. Feature Coverage matrix
    3. Reference Details (pin-cites)
    """
    # --- Section 1: Reference Summary ---
    summary_header_idx = None
    for i, row in enumerate(rows):
        if row and row[0].strip() == "#" and len(row) >= 3 and "Ref ID" in row[1]:
            summary_header_idx = i
            break

    refs_by_id: dict[str, dict] = {}
    if summary_header_idx is not None:
        for row in rows[summary_header_idx + 1:]:
            # Stop at empty row (section separator) or next section header
            if not row or all(c.strip() == "" for c in row):
                break
            first_cell = row[0].strip()
            # Stop at known section headers
            if first_cell in ("Reference Details", "Feature Coverage"):
                break

            while len(row) < 9:
                row.append("")

            ref_id = row[1].strip()
            if not ref_id:
                continue

            priority = row[7].strip()
            triage = row[6].strip()

            # Skip template placeholder rows (no triage = unfilled row)
            if not triage:
                continue

            refs_by_id[ref_id] = {
                "publication_number": ref_id,
                "type": row[2].strip() or "Patent",
                "title": row[3].strip(),
                "source_db": row[4].strip(),
                "discovery_method": row[5].strip(),
                "triage_label": triage,
                "priority_date": priority.replace("/", "-") if priority else "",
                "blocking_potential": row[8].strip(),
                "feature_coverage": {},
                "pin_cites": "",
                "sme_notes": "",
            }

    # --- Section 2: Feature Coverage ---
    coverage_header_idx = None
    for i, row in enumerate(rows):
        if (
            row
            and len(row) >= 3
            and row[0].strip() == "Reference ID"
            and row[1].strip() == "Feature"
            and row[2].strip() == "Coverage"
        ):
            coverage_header_idx = i
            break

    if coverage_header_idx is not None:
        current_ref_id = None
        for row in rows[coverage_header_idx + 1:]:
            if not row or all(c.strip() == "" for c in row[:4]):
                continue

            while len(row) < 4:
                row.append("")

            rid = row[0].strip()
            feature = row[1].strip()
            coverage = row[2].strip()

            if rid:
                current_ref_id = rid
            if current_ref_id and feature and coverage:
                if current_ref_id in refs_by_id:
                    refs_by_id[current_ref_id]["feature_coverage"][feature] = coverage

    # --- Section 3: Pin-cites (from Reference Details sub-table) ---
    details_header_idx = None
    for i, row in enumerate(rows):
        if (
            row
            and len(row) >= 2
            and row[0].strip() == "Reference ID"
            and "Pin-Cites" in row[1]
        ):
            # This is in the right side of the Feature Coverage table
            # The actual structure has it at columns 5-7
            details_header_idx = i
            break

    # Also look for pin-cites in the wider rows (columns 5+)
    if coverage_header_idx is not None:
        for row in rows[coverage_header_idx + 1:]:
            if len(row) >= 7:
                pin_ref_id = row[5].strip() if len(row) > 5 else ""
                pin_cites = row[6].strip() if len(row) > 6 else ""
                sme_notes = row[7].strip() if len(row) > 7 else ""

                if pin_ref_id and pin_ref_id in refs_by_id:
                    if pin_cites:
                        refs_by_id[pin_ref_id]["pin_cites"] = pin_cites
                    if sme_notes:
                        refs_by_id[pin_ref_id]["sme_notes"] = sme_notes

    references = list(refs_by_id.values())
    return {"references": references}


# ---------------------------------------------------------------------------
# Part B: Final Verdict -> gt_verdict.json
# ---------------------------------------------------------------------------

_VERDICT_MAP = {
    "novel": "novel",
    "partially novel": "partially_novel",
    "partially_novel": "partially_novel",
    "not novel": "not_novel",
    "not_novel": "not_novel",
}


def convert_verdict(rows: list[list[str]]) -> dict:
    """Convert Part B Final Verdict CSV into verdict dict."""
    # Parse left side: Overall Assessment (Field, Value in columns 0-1)
    verdict_data: dict[str, str] = {}
    for row in rows:
        if len(row) >= 2 and row[0].strip():
            key = row[0].strip()
            val = row[1].strip()
            if key in ("Overall verdict", "Confidence", "Where novelty resides"):
                verdict_data[key] = val

    # Parse right side: Per-Feature Risk (columns 6-9)
    per_feature_risk: list[dict] = []
    for row in rows:
        if len(row) >= 10:
            feature = row[6].strip()
            risk_level = row[7].strip()
            closest_ref = row[8].strip()
            gap_desc = row[9].strip() if len(row) > 9 else ""

            if feature and re.match(r"^F\d+$", feature) and risk_level:
                entry: dict[str, str] = {
                    "feature": feature,
                    "risk_level": risk_level,
                    "closest_reference": closest_ref,
                }
                if gap_desc:
                    entry["gap_description"] = gap_desc
                per_feature_risk.append(entry)

    raw_verdict = verdict_data.get("Overall verdict", "").lower().strip()
    normalized = _VERDICT_MAP.get(raw_verdict, raw_verdict.replace(" ", "_"))

    result: dict = {
        "verdict": normalized,
        "confidence": verdict_data.get("Confidence", ""),
    }
    where = verdict_data.get("Where novelty resides", "")
    if where:
        result["where_novelty_resides"] = where
    if per_feature_risk:
        result["per_feature_risk"] = per_feature_risk

    return result


# ---------------------------------------------------------------------------
# Part B: Search Strategy -> gt_search_strategy.md
# ---------------------------------------------------------------------------

def convert_search_strategy(rows: list[list[str]]) -> str:
    """Convert Part B Search Strategy CSV into gt_search_strategy.md."""
    sections: list[str] = []

    # --- Databases Used ---
    db_header_idx = None
    for i, row in enumerate(rows):
        if row and row[0].strip() == "Database":
            db_header_idx = i
            break

    if db_header_idx is not None:
        dbs: list[str] = []
        for row in rows[db_header_idx + 1:]:
            if not row or not row[0].strip():
                break
            name = row[0].strip()
            used = row[1].strip().upper() if len(row) > 1 else ""
            notes = row[2].strip() if len(row) > 2 else ""
            if used == "Y":
                entry = name
                if notes:
                    entry += f" ({notes})"
                dbs.append(entry)
        if dbs:
            sections.append("## Databases Used\n\n" + "\n".join(f"- {d}" for d in dbs))

    # --- Search Queries ---
    query_header_idx = None
    for i, row in enumerate(rows):
        if row and row[0].strip() == "#" and len(row) >= 2 and "Database" in row[1]:
            query_header_idx = i
            break

    if query_header_idx is not None:
        queries: list[str] = []
        for row in rows[query_header_idx + 1:]:
            if not row or all(c.strip() == "" for c in row[:3]):
                # Check if this is a section break
                if not row or row[0].strip() == "":
                    continue
                break
            query_text = row[0].strip()
            db = row[1].strip() if len(row) > 1 else ""
            if query_text:
                queries.append(f"- `{query_text}` ({db})" if db else f"- `{query_text}`")
        if queries:
            sections.append("## Search Queries\n\n" + "\n".join(queries))

    # --- Vocabulary Discovered ---
    vocab_header_idx = None
    for i, row in enumerate(rows):
        if row and row[0].strip() == "Original Term":
            vocab_header_idx = i
            break

    if vocab_header_idx is not None:
        vocab_lines: list[str] = []
        for row in rows[vocab_header_idx + 1:]:
            if not row or all(c.strip() == "" for c in row[:2]):
                continue
            original = row[0].strip()
            synonym = row[1].strip() if len(row) > 1 else ""
            how = row[2].strip() if len(row) > 2 else ""
            if original and synonym:
                entry = f"- **{original}**: {synonym}"
                if how:
                    entry += f" _(discovered via {how})_"
                vocab_lines.append(entry)
        if vocab_lines:
            sections.append("## Vocabulary Discovered\n\n" + "\n".join(vocab_lines))

    # --- Expected CPC Codes ---
    cpc_header_idx = None
    for i, row in enumerate(rows):
        if row and row[0].strip() == "Code" and len(row) >= 2:
            cpc_header_idx = i
            break

    if cpc_header_idx is not None:
        codes: list[str] = []
        for row in rows[cpc_header_idx + 1:]:
            if not row or not row[0].strip():
                break
            code = row[0].strip()
            system = row[1].strip() if len(row) > 1 else ""
            why = row[2].strip() if len(row) > 2 else ""
            entry = f"- {code} ({system})"
            if why:
                entry += f" — {why}"
            codes.append(entry)
        if codes:
            sections.append("## Expected Classification Codes\n\nCPC codes: " +
                            ", ".join(row[0].strip() for row in rows[cpc_header_idx + 1:]
                                      if row and row[0].strip()) +
                            "\n\n" + "\n".join(codes))

    return "\n\n".join(sections) + "\n"


# ---------------------------------------------------------------------------
# Part B: Metadata + Difficulty -> metadata.json
# ---------------------------------------------------------------------------

def convert_metadata(
    meta_rows: list[list[str]],
    diff_rows: list[list[str]],
    disclosure_rows: list[list[str]],
) -> dict:
    """Convert Part B Metadata and Difficulty CSVs into metadata dict."""
    # Parse metadata
    meta: dict[str, str] = {}
    for row in meta_rows:
        if len(row) >= 2 and row[0].strip():
            meta[row[0].strip()] = row[1].strip()

    # Parse time breakdown (columns 4-5)
    time_breakdown: dict[str, int] = {}
    for row in meta_rows:
        if len(row) >= 6:
            stage = row[4].strip()
            minutes = row[5].strip()
            if stage and minutes and stage != "Stage" and stage != "Total":
                try:
                    time_breakdown[stage.lower().replace(" ", "_").replace(
                        "(", "").replace(")", "").replace(
                        "understanding_the_invention", "scoping"
                    )] = int(minutes)
                except ValueError:
                    pass

    # Parse difficulty
    diff: dict[str, str] = {}
    for row in diff_rows:
        if len(row) >= 2 and row[0].strip():
            diff[row[0].strip()] = row[1].strip()

    # Parse disclosure for case info
    disc: dict[str, str] = {}
    for row in disclosure_rows:
        if len(row) >= 2 and row[0].strip():
            disc[row[0].strip()] = row[1].strip()

    total_time = 0
    try:
        total_time = int(meta.get("Total Time (minutes)", "0"))
    except ValueError:
        pass

    difficulty_score = 0
    # The dash between 1-5 may be en-dash, em-dash, or regular dash
    for row in diff_rows:
        if len(row) >= 2 and "perceived difficulty" in row[0].lower():
            val = row[1].strip()
            try:
                difficulty_score = int(val)
                break
            except ValueError:
                pass

    return {
        "case_id": disc.get("Case ID", ""),
        "domain": disc.get("Domain", ""),
        "title": disc.get("Title", ""),
        "difficulty_band": diff.get("Assigned difficulty band", ""),
        "difficulty_score": difficulty_score,
        "difficulty_notes": diff.get("Difficulty notes", ""),
        "sme_name": meta.get("SME Name", ""),
        "collection_date": meta.get("Collection Date", ""),
        "total_time_minutes": total_time,
        "time_breakdown": time_breakdown,
    }


# ---------------------------------------------------------------------------
# Main conversion pipeline
# ---------------------------------------------------------------------------

def convert_case(input_dir: Path, case_id: str, output_dir: Path) -> None:
    """Convert all SME CSV files for a case into scorer fixtures."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Locate files
    file_map = {
        "disclosure": "Part A",
        "features": "Expected Key Features",
        "references": "Blocking Prior Art",
        "verdict": "Final Verdict",
        "search_strategy": "Search Strategy",
        "metadata": "Metadata",
        "difficulty": "Difficulty",
    }

    csv_data: dict[str, list[list[str]]] = {}
    for key, part_name in file_map.items():
        path = _find_file(input_dir, case_id, part_name)
        if path is None:
            _logger.warning("Missing CSV for %s (looking for '%s' in %s)", key, part_name, input_dir)
            csv_data[key] = []
        else:
            csv_data[key] = _read_csv(path)
            _logger.info("Loaded %s: %s (%d rows)", key, path.name, len(csv_data[key]))

    # Convert each part
    # 1. disclosure.md
    disclosure_content = convert_disclosure(csv_data["disclosure"])
    (output_dir / "disclosure.md").write_text(disclosure_content, encoding="utf-8")
    _logger.info("Wrote disclosure.md")

    # 2. gt_features.json
    features = convert_features(csv_data["features"])
    (output_dir / "gt_features.json").write_text(
        json.dumps(features, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _logger.info("Wrote gt_features.json (%d features)", len(features))

    # 3. gt_references.json
    references = convert_references(csv_data["references"])
    (output_dir / "gt_references.json").write_text(
        json.dumps(references, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    ref_count = len(references.get("references", []))
    _logger.info("Wrote gt_references.json (%d references)", ref_count)

    # 4. gt_verdict.json
    verdict = convert_verdict(csv_data["verdict"])
    (output_dir / "gt_verdict.json").write_text(
        json.dumps(verdict, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _logger.info("Wrote gt_verdict.json (verdict=%s)", verdict.get("verdict"))

    # 5. gt_search_strategy.md
    strategy = convert_search_strategy(csv_data["search_strategy"])
    (output_dir / "gt_search_strategy.md").write_text(strategy, encoding="utf-8")
    _logger.info("Wrote gt_search_strategy.md")

    # 6. metadata.json
    metadata = convert_metadata(
        csv_data["metadata"], csv_data["difficulty"], csv_data["disclosure"]
    )
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _logger.info("Wrote metadata.json")

    print(f"\nConversion complete for {case_id}:")
    print(f"  Output: {output_dir}")
    print(f"  Features: {len(features)}")
    print(f"  References: {ref_count}")
    print(f"  Verdict: {verdict.get('verdict')}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert SME CSV ground truth to scorer JSON fixtures",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing SME CSV files",
    )
    parser.add_argument(
        "--case-id",
        type=str,
        required=True,
        help="Case ID to convert (e.g., C19904)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output directory for fixture files",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not args.input_dir.is_dir():
        _logger.error("Input directory does not exist: %s", args.input_dir)
        sys.exit(1)

    convert_case(args.input_dir, args.case_id, args.output_dir)


if __name__ == "__main__":
    main()
