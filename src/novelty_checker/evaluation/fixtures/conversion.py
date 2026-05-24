import os
import sys
import pandas as pd
import yaml
import re
import json
import argparse
from pydantic import ValidationError
from typing import Optional, Literal

# Directory that contains this script — i.e. the fixtures folder itself.
_FIXTURES_DIR = os.path.dirname(os.path.abspath(__file__))

# Import schemas directly by filename so this script can be run standalone
# without triggering the full src.novelty_checker package init chain.
if _FIXTURES_DIR not in sys.path:
    sys.path.insert(0, _FIXTURES_DIR)
from schemas import CaseMetadata, GTFeatures, FeatureEntry, GTReferences, GTSearchStrategy, GTVerdict  # noqa: E402

def _is_placeholder(text) -> bool:
    """Return True if the cell contains only a template placeholder string."""
    if text is None:
        return True
    stripped = str(text).strip()
    return stripped.startswith("[") and stripped.endswith("]")


def _format_key_technical_aspects(text: str) -> str:
    """Re-renders newline-separated numbered items as a clean markdown list."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


# Fields that are already extracted into dedicated keys — anything else is
# treated as an optional/extra field and surfaced under Additional Information.
_KNOWN_PART_A_FIELDS = {
    "case id", "domain", "difficulty", "source",
    "language(optional)", "created by", "created date",
    "title", "technical field",
    "background / problem statement",
    "key technical aspects", "known constraints(optional)",
    "additional information",
}


def parse_invention_disclosure(file_path) -> dict:
    df = pd.read_excel(
        file_path,
        sheet_name="Part A  Invention Disclosure",
        header=None,
    ).reset_index(drop=True)

    header_idx = None
    for i, row in df.iterrows():
        if str(row.iloc[0]).strip() == "Field":
            header_idx = i
            break

    field_map = {}
    if header_idx is not None:
        for i in range(header_idx + 1, len(df)):
            row = df.iloc[i]
            field = _val(row.iloc[0])
            value = _val(row.iloc[1])
            if field:
                field_map[field.lower()] = value

    def get(key):
        val = field_map.get(key)
        return None if _is_placeholder(val) else val

    created_date = get("created date")
    if created_date and "00:00:00" in created_date:
        created_date = created_date.split(" ")[0]

    return {
        "case_id":               get("case id"),
        "domain":                get("domain"),
        "difficulty":            get("difficulty"),
        "difficulty_score":      None,  # to be filled in manually if desired
        "source":                get("source"),
        "language":              get("language(optional)") or "English",
        "created_by":            get("created by"),
        "created_date":          created_date,
        "title":                 get("title"),
        "technical_field":       get("technical field"),
        "problem_statement":     get("background / problem statement"),
        "key_technical_aspects": get("key technical aspects"),
        "known_constraints":     get("known constraints(optional)"),
        "additional_information": get("additional information"),
        # Any field in the sheet that isn't one of the named keys above
        "extra_fields": {
            k: v for k, v in field_map.items()
            if k not in _KNOWN_PART_A_FIELDS and v and not _is_placeholder(v)
        },
    }


def create_invention_disclosure_md(data: dict, case_id: str, output_base_dir: str = "output") -> None:
    case_dir = os.path.join(output_base_dir, case_id)
    os.makedirs(case_dir, exist_ok=True)
    output_path = os.path.join(case_dir, "disclosure.md")

    def section(heading: str, content, formatter=None) -> str:
        if not content:
            return ""
        body = formatter(content) if formatter else content.strip()
        return f"## {heading}\n\n{body}\n"

    lines = []

    title = data.get("title") or "Untitled Invention"
    lines.append(f"# {title.strip()}\n")

    lines.append(section("Technical Field",        data.get("technical_field")))
    lines.append(section("Problem Statement",      data.get("problem_statement")))
    lines.append(section("Key Technical Aspects",  data.get("key_technical_aspects"),
                          formatter=_format_key_technical_aspects))
    lines.append(section("Known Constraints",      data.get("known_constraints")))

    # Build Additional Information from the explicit field + any extra optional fields
    additional_parts = []
    if data.get("additional_information"):
        additional_parts.append(data["additional_information"].strip())
    for field_name, field_val in (data.get("extra_fields") or {}).items():
        if field_val:
            additional_parts.append(f"**{field_name.title()}:** {field_val}")
    additional_content = "\n\n".join(additional_parts) or None

    lines.append(section("Additional Information", additional_content))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(line for line in lines if line))

    print(f"✅ Invention disclosure written to: {output_path}")
    
def clean_metadata(data):
    """
    Fully cleans metadata dictionary:
    - Removes junk keys (Field, nan, empty)
    - Converts NaN -> None
    - Strips whitespace from strings
    - Recursively cleans nested dicts/lists
    """

    def is_invalid_key(key):
        return str(key).strip().lower() in ["", "nan", "none", "field"]

    def clean_value(val):
        # Handle NaN
        if pd.isna(val):
            return None

        # Clean strings
        if isinstance(val, str):
            val = val.strip()
            return val if val else None

        return val

    def recursive_clean(obj):
        # Dict case
        if isinstance(obj, dict):
            cleaned = {}
            for k, v in obj.items():

                if is_invalid_key(k):
                    continue

                key = str(k).strip()

                value = recursive_clean(v)

                cleaned[key] = value

            return cleaned

        # List case
        elif isinstance(obj, list):
            return [recursive_clean(item) for item in obj]

        # Base case
        else:
            return clean_value(obj)

    return recursive_clean(data)

def clean_dataframe(df):
    """Remove completely empty rows and columns"""
    df = df.dropna(how="all")
    df = df.dropna(axis=1, how="all")
    return df


# -------------------------------
# PART A PARSER
# -------------------------------
def parse_part_a(file_path):
    df = pd.read_excel(file_path, sheet_name="Part A  Invention Disclosure")
    df = clean_dataframe(df)
    df = df.iloc[:, :2]
    df.columns = ["Field", "Value"]
    data_dict = dict(zip(df["Field"], df["Value"]))

    def get(key, default=None):
        val = data_dict.get(key, default)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        return str(val).strip() or None

    raw_date = get("Created Date")
    if raw_date and "00:00:00" in raw_date:
        raw_date = raw_date.split(" ")[0]

    return {
        "case_id":      get("Case ID"),
        "domain":       get("Domain"),
        "difficulty":   get("Difficulty"),
        "source":       get("Source"),
        "language":     get("Language(Optional)") or "English",
        "created_by":   get("Created By"),
        "created_date": raw_date,
    }

# -------------------------------
# PART B PARSER
# -------------------------------
def find_table_start(df, keyword):
    """Find row index where a table starts based on keyword"""
    for i, row in df.iterrows():
        if row.astype(str).str.contains(keyword, case=False).any():
            return i
    return None

def extract_case_metadata(df, start_row):
    """
    Extract key-value pairs from 'Case Metadata' table.
    Keys are kept as-is to match CaseMetadata aliases (e.g. 'Collection Date').
    """
    metadata = {}
    for i in range(start_row + 1, len(df)):
        row = df.iloc[i]
        if row.isnull().all():
            break
        key = str(row.iloc[0]).strip()
        value = row.iloc[1]
        if key and key.lower() not in ("nan", "none", ""):
            metadata[key] = value
    return metadata


def extract_time_breakdown_clean(df, start_row):
    """
    Extract Stage -> Minutes mapping
    """
    time_data = {}

    # Header row (e.g., Stage | Minutes)
    header_row = df.iloc[start_row + 1]

    # Identify column indices
    stage_col = None
    minutes_col = None

    for idx, col in enumerate(header_row):
        col_str = str(col).lower()
        if "stage" in col_str:
            stage_col = idx
        elif "minute" in col_str:
            minutes_col = idx

    if stage_col is None or minutes_col is None:
        raise ValueError("Could not find Stage/Minutes columns")

    # Read actual data
    for i in range(start_row + 2, len(df)):
        row = df.iloc[i]

        if row.isnull().all():
            break

        stage = str(row.iloc[stage_col]).strip()
        minutes = row.iloc[minutes_col]

        if stage and stage.lower() != "nan":
            time_data[stage] = minutes

    return time_data


def parse_part_b(file_path):
    df = pd.read_excel(
        file_path,
        sheet_name="Part B GT Assessment- Metadata",
        header=None
    )

    df = clean_dataframe(df)

    case_metadata_start = find_table_start(df, "Case Metadata")
    time_breakdown_start = find_table_start(df, "Time Breakdown")

    case_metadata = {}
    time_breakdown = {}

    if case_metadata_start is not None:
        case_metadata = extract_case_metadata(df, case_metadata_start)

    if time_breakdown_start is not None:
        time_breakdown = extract_time_breakdown_clean(df, time_breakdown_start)

    return {
        "case_metadata": case_metadata,
        "time_breakdown": time_breakdown
    }
def create_metadata_yaml(metadata, output_base_dir=None):
    if output_base_dir is None:
        output_base_dir = _FIXTURES_DIR
    case_id = metadata.get("case_id")

    if not case_id:
        raise ValueError("Case ID is missing. Cannot create directory.")

    # Validate against schema — warns on unexpected values, does not block.
    try:
        validated = CaseMetadata.model_validate(metadata)
        data_to_write = validated.to_serializable()
    except ValidationError as exc:
        print(f"⚠️  Metadata validation warnings:\n{exc}")
        data_to_write = metadata  # fall back to raw dict

    # Create directory: output/<case_id>/
    case_dir = os.path.join(output_base_dir, case_id)
    os.makedirs(case_dir, exist_ok=True)

    # File path
    yaml_path = os.path.join(case_dir, "fixture_meta.yaml")

    # Write YAML
    with open(yaml_path, "w") as f:
        yaml.dump(data_to_write, f, sort_keys=False)

    print(f"✅ Metadata written to: {yaml_path}")
# -------------------------------
# FEATURES
# -------------------------------
def _split_to_list(value) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    return [item.strip() for item in re.split(r'[,\n]', str(value)) if item.strip()]


def _split_to_list_of_lists(value, sep_pattern: str = None) -> list[list[str]]:
    """Split a cell into a list of lists.

    Each non-empty line becomes one inner list. Within a line the splitting
    strategy depends on the content:

    - If *sep_pattern* is provided, tokens are split by that regex and returned
      as-is (no symbol stripping) — used for pin_cites and similar fields.
    - If the line contains a comma, tokens are split by comma — each
      comma-separated word on a line forms one inner list.
    - Otherwise tokens are split on 'OR' (case-insensitive) and
      non-alphanumeric/space characters are stripped — fallback for keyword
      cells that use OR-style grouping or CPC/IPC codes.

    Returns [] for None/NaN cells.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    lines = str(value).splitlines()
    result = []
    for line in lines:
        if sep_pattern is not None:
            tokens = [t.strip() for t in re.split(sep_pattern, line) if t.strip()]
        elif "," in line:
            tokens = [t.strip() for t in line.split(",") if t.strip()]
        else:
            tokens = re.split(r'\bOR\b', line, flags=re.IGNORECASE)
            tokens = [re.sub(r'[^a-zA-Z0-9 ]', '', t).strip() for t in tokens]
            tokens = [t for t in tokens if t]
        if tokens:
            result.append(tokens)
    return result


def parse_expected_key_features(file_path):
    df = pd.read_excel(
        file_path,
        sheet_name="Part B Expected Key Features",
        header=None
    )

    # Drop empty rows
    df = df.dropna(how="all").reset_index(drop=True)

    # Detect header row (contains 'id')
    header_row_idx = None
    for i, row in df.iterrows():
        row_values = [str(x).strip().lower() for x in row.tolist()]
        if "id" in row_values:
            header_row_idx = i
            break

    if header_row_idx is None:
        raise ValueError("Header row not found in 'Part B Expected Key Features' sheet")

    df.columns = df.iloc[header_row_idx]
    df = df[(header_row_idx + 1):].reset_index(drop=True)
    df.columns = [str(col).strip() for col in df.columns]

    df = df[df["ID"].notna()]
    df = df.where(pd.notna(df), None)

    # Detect whether both Name and Description columns exist
    has_name = "Name" in df.columns
    has_description = "Description" in df.columns

    features = []
    seq = 1
    for _, row in df.iterrows():
        # Use the ID column only to detect blank/sentinel rows — the actual
        # feature_id is always auto-assigned so duplicates in the sheet are avoided.
        raw_id = str(row.get("ID") or "").strip()
        if not raw_id or raw_id.lower() == "nan":
            continue

        def get(col):
            val = row.get(col)
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return None
            return str(val).strip() or None

        entry = {
            "feature_id": f"F{seq}",
            "name":        get("Name") if has_name else None,
            "description": get("Description") if has_description else get("Name"),
            "type":        get("Type"),
            "core":        get("Core?"),
            "keywords":    _split_to_list_of_lists(row.get("Keywords")),
            "related_cpc_ipc": _split_to_list(row.get("Related CPC/IPC")),
        }
        features.append(entry)
        seq += 1

    return features

def create_gt_features_json(features_dict, case_id, output_base_dir="output"):
    case_dir = os.path.join(output_base_dir, case_id)
    os.makedirs(case_dir, exist_ok=True)

    output_path = os.path.join(case_dir, "gt_features.json")

    # Validate against schema — warns on unexpected values, does not block.
    try:
        validated = GTFeatures.model_validate(features_dict)
        data_to_write = validated.to_serializable()
    except ValidationError as exc:
        print(f"⚠️  GT features validation warnings:\n{exc}")
        data_to_write = features_dict  # fall back to raw dict

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data_to_write, f, indent=2, ensure_ascii=False)

    print(f"✅ GT features written to: {output_path}")

# -------------------------------
# PART B — BLOCKING PRIOR ART
# -------------------------------

def _val(x):
    """Return None for NaN/empty, else stripped string."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip()
    return s if s and s.lower() not in ("nan", "none") else None


def _contains_cjk(text: str) -> bool:
    """Return True if *text* contains at least one CJK (Chinese/Japanese/Korean) character."""
    return any(
        '\u4e00' <= ch <= '\u9fff'   # CJK Unified Ideographs
        or '\u3400' <= ch <= '\u4dbf' # CJK Extension A
        or '\uf900' <= ch <= '\ufaff' # CJK Compatibility Ideographs
        or '\u3000' <= ch <= '\u303f' # CJK Symbols and Punctuation
        for ch in text
    )


def _parse_summary_table(df):
    """
    Parse the Reference Summary table (rows starting at the '#' header row).
    Returns a dict keyed by publication_number with summary fields.
    """
    header_row_idx = None
    for i, row in df.iterrows():
        if str(row.iloc[0]).strip() == "#":
            header_row_idx = i
            break

    if header_row_idx is None:
        return {}

    summary = {}
    for i in range(header_row_idx + 1, len(df)):
        row = df.iloc[i]

        if row.isnull().all():
            break

        seq_num = _val(row.iloc[0])
        ref_id  = _val(row.iloc[1])

        if seq_num is None or ref_id is None:
            continue

        raw_date = _val(row.iloc[7])
        priority_date = None
        if raw_date and raw_date != "YYYY-MM-DD":
            priority_date = str(raw_date)[:10]   # "2021-01-03 00:00:00" → "2021-01-03"

        raw_title = _val(row.iloc[3]) or ""
        if " | " in raw_title:
            part_a, part_b = [p.strip() for p in raw_title.split(" | ", 1)]
            # Assign by language detection so order in the cell doesn't matter
            if _contains_cjk(part_a) and not _contains_cjk(part_b):
                title_en, title_zh = part_b or None, part_a or None
            elif _contains_cjk(part_b) and not _contains_cjk(part_a):
                title_en, title_zh = part_a or None, part_b or None
            else:
                # Both or neither contain CJK — keep original order
                title_en, title_zh = part_a or None, part_b or None
        elif raw_title:
            # Single title: detect language and assign accordingly
            if _contains_cjk(raw_title):
                title_en, title_zh = None, raw_title
            else:
                title_en, title_zh = raw_title, None
        else:
            title_en, title_zh = None, None

        summary[ref_id] = {
            "seq":                int(seq_num),
            "ref_id":             f"R{seq_num}",
            "publication_number": ref_id,
            "type":               _val(row.iloc[2]),
            "title_english":      title_en,
            "title_chinese":      title_zh,
            "source_db":          _val(row.iloc[4]),
            "discovery_method":   _val(row.iloc[5]),
            "triage":             _val(row.iloc[6]),
            "priority_date":      priority_date,
            "blocking_potential": _val(row.iloc[8]),
        }

    return summary


def _parse_feature_coverage(df):
    """
    Parse the Feature Coverage sub-table (left side of Reference Details section).
    Returns an ordered list of blocks, one per reference entry:
      [ {"ref_cell": <raw id>, "features": {"F1": {verdict, notes}, ...}}, ... ]
    Each new non-empty value in the Reference ID column starts a new block,
    so duplicate IDs in the sheet each produce their own independent entry.
    """
    header_row_idx = None
    for i, row in df.iterrows():
        if str(row.iloc[0]).strip() == "Reference ID" and str(row.iloc[1]).strip() == "Feature":
            header_row_idx = i
            break

    if header_row_idx is None:
        return []

    blocks = []          # ordered list; each new ref_cell span appends a new block
    feature_seq = 1

    for i in range(header_row_idx + 1, len(df)):
        row = df.iloc[i]
        ref_cell     = _val(row.iloc[0])
        feature_cell = _val(row.iloc[1])
        verdict_cell = _val(row.iloc[2])
        notes_cell   = _val(row.iloc[3])

        if ref_cell:
            # Every new non-empty ref_cell starts a fresh block, regardless of
            # whether the same ID has appeared before.
            blocks.append({"ref_cell": ref_cell, "features": {}})
            feature_seq = 1

        if blocks and feature_cell:
            auto_fid = f"F{feature_seq}"
            blocks[-1]["features"][auto_fid] = {
                "verdict": verdict_cell,
                "notes":   notes_cell,
            }
            feature_seq += 1

    return blocks


def _parse_pin_cites_and_notes(df):
    """
    Parse the Reference Summary sub-table (right side of Reference Details section).
    Returns dict: { publication_number: {pin_cites, sme_notes} }
    """
    header_row_idx = None
    for i, row in df.iterrows():
        if str(row.iloc[5]).strip() == "Reference ID" and str(row.iloc[6]).strip() == "Pin-Cites":
            header_row_idx = i
            break

    if header_row_idx is None:
        return {}

    result = {}
    for i in range(header_row_idx + 1, len(df)):
        row = df.iloc[i]
        ref_id    = _val(row.iloc[5])
        pin_cites = _val(row.iloc[6])
        sme_notes = _val(row.iloc[7])

        if ref_id:
            result[ref_id] = {
                "pin_cites": pin_cites,
                "sme_notes": sme_notes,
            }

    return result


def parse_blocking_prior_art(file_path):
    df = pd.read_excel(
        file_path,
        sheet_name="Part B Blocking Prior Art",
        header=None,
    )
    df = df.reset_index(drop=True)

    summary_map    = _parse_summary_table(df)
    coverage_blocks = _parse_feature_coverage(df)  # ordered list, one block per ref
    pin_notes_map  = _parse_pin_cites_and_notes(df)

    # Build a reverse map for pin_notes: resolve pub numbers / R-style IDs → pub number
    ref_id_to_pub = {v["ref_id"]: pub for pub, v in summary_map.items()}

    def _resolve_pin(key):
        if key in summary_map:
            return key
        return ref_id_to_pub.get(key, key)

    pin_notes_map = {_resolve_pin(k): v for k, v in pin_notes_map.items()}

    # Match coverage blocks to summary entries by position (order of appearance).
    # This is robust to duplicate reference IDs in the coverage table.
    sorted_summaries = sorted(summary_map.items(), key=lambda x: x[1]["seq"])

    references = []
    for idx, (pub_num, summary) in enumerate(sorted_summaries):
        block = coverage_blocks[idx] if idx < len(coverage_blocks) else {}
        feature_coverage = block.get("features", {})
        pin_info = pin_notes_map.get(pub_num, {})

        references.append({
            "ref_id":               summary["ref_id"],
            "publication_number":   summary["publication_number"],
            "patent_family_number": None,
            "title_english":        summary["title_english"],
            "title_chinese":        summary["title_chinese"],
            "source_db":            summary["source_db"],
            "discovery_method":     summary["discovery_method"],
            "triage":               summary["triage"],
            "priority_date":        summary["priority_date"],
            "blocking_potential":   summary["blocking_potential"],
            "feature_coverage":     feature_coverage,
            "pin_cites":            pin_info.get("pin_cites"),
            "sme_notes":            pin_info.get("sme_notes"),
        })

    return {
        "total_references": len(references),
        "references": references,
    }


def create_gt_references_json(references_dict, case_id, output_base_dir="output"):
    case_dir = os.path.join(output_base_dir, case_id)
    os.makedirs(case_dir, exist_ok=True)

    output_path = os.path.join(case_dir, "gt_references.json")

    payload = {"case_id": case_id, **references_dict}

    try:
        validated = GTReferences.model_validate(payload)
        data_to_write = validated.to_serializable()
    except ValidationError as exc:
        print(f"⚠️  GT references validation warnings:\n{exc}")
        data_to_write = payload
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data_to_write, f, indent=2, ensure_ascii=False)

    print(f"✅ GT references written to: {output_path}")
    
# -------------------------------
# PART B — FINAL VERDICT
# -------------------------------

def _parse_overall_assessment(df) -> dict:
    header_row_idx = None
    for i, row in df.iterrows():
        if str(row.iloc[0]).strip() == "Field":
            header_row_idx = i
            break

    field_map = {}

    if header_row_idx is not None:
        for i in range(header_row_idx + 1, len(df)):
            row = df.iloc[i]
            field = _val(row.iloc[0])
            value = _val(row.iloc[1])

            if field:
                field_map[field.lower()] = value

    return {
        "verdict":               _normalise_verdict(field_map.get("overall verdict")),
        "confidence":            field_map.get("confidence"),
        "where_novelty_resides": field_map.get("where novelty resides"),
        "verdict_reasoning":     field_map.get("verdict reasoning"),
    }


def _normalise_verdict(raw: str | None) -> str | None:
    """Normalise a free-text verdict to one of: novel | not_novel | partially_novel."""
    if raw is None:
        return None
    key = raw.strip().lower().replace(" ", "_").replace("-", "_")
    # Collapse common variants to the canonical form
    if "not" in key or "no_novel" in key:
        return "not_novel"
    if "partial" in key:
        return "partially_novel"
    if "novel" in key:
        return "novel"
    # Unknown value — return snake_cased as-is so no data is lost
    return key


def _parse_per_feature_risk(df) -> list[dict]:
    """
    Extract rows from the Per-Feature Risk table (cols 6–9).
    """
    header_row_idx = None
    for i, row in df.iterrows():
        if str(row.iloc[6]).strip() == "Feature":
            header_row_idx = i
            break

    if header_row_idx is None:
        return []

    entries = []
    for i in range(header_row_idx + 1, len(df)):
        row = df.iloc[i]
        feature_id  = _val(row.iloc[6])
        risk_level  = _val(row.iloc[7])
        closest_ref = _val(row.iloc[8])
        gap_desc    = _val(row.iloc[9])

        if feature_id is None:
            continue

        # Skip rows where every field besides feature_id is empty
        if risk_level is None and closest_ref is None and gap_desc is None:
            continue

        # Split closest_reference on comma, pipe, or newline
        if closest_ref:
            refs = [r.strip() for r in re.split(r'[,|\n]+', closest_ref) if r.strip()]
        else:
            refs = []

        entries.append({
            "feature_id":        feature_id,
            "risk_level":        risk_level,
            "closest_reference": refs,
            "gap_description":   gap_desc,
        })

    return entries


def parse_final_verdict(file_path) -> dict:
    df = pd.read_excel(
        file_path,
        sheet_name="Part B Final Verdict",
        header=None,
    ).reset_index(drop=True)

    return {
        "overall":          _parse_overall_assessment(df),
        "per_feature_risk": _parse_per_feature_risk(df),
    }


def create_gt_verdict_json(verdict_dict, case_id, output_base_dir="output"):
    case_dir = os.path.join(output_base_dir, case_id)
    os.makedirs(case_dir, exist_ok=True)

    output_path = os.path.join(case_dir, "gt_verdict.json")
    payload = {"case_id": case_id, **verdict_dict}

    try:
        validated = GTVerdict.model_validate(payload)
        data_to_write = validated.to_serializable()
    except ValidationError as exc:
        print(f"⚠️  GT verdict validation warnings:\n{exc}")
        data_to_write = payload

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data_to_write, f, indent=2, ensure_ascii=False)

    print(f"✅ GT verdict written to: {output_path}")
    
# ---------------------------------------------------------------
# PART B — SEARCH STRATEGY
# ---------------------------------------------------------------

# Section header names used to detect boundaries between tables
_SECTION_HEADERS = {
    "vocabulary discovered", "overall strategy narrative",
    "expected classification codes", "databases used",
    "search queries executed",
}


def _parse_databases_used(df) -> list[str]:
    header_idx = None
    for i, row in df.iterrows():
        if str(row.iloc[0]).strip() == "Database" and str(row.iloc[1]).strip() == "Used?":
            header_idx = i
            break

    if header_idx is None:
        return []

    used = []
    for i in range(header_idx + 1, len(df)):
        row = df.iloc[i]
        db_name   = _val(row.iloc[0])
        used_flag = _val(row.iloc[1])
        notes     = _val(row.iloc[2]) if len(row) > 2 else None

        if db_name is None:
            break

        if used_flag and used_flag.upper() == "Y":
            # "Other:" rows carry the actual db name in the Notes column
            used.append(notes if db_name.lower().startswith("other") and notes else db_name)

    return used


def _parse_queries_executed(df) -> list[dict]:
    # Detect header row: must contain "Database" and at least one of "#" / "Query Text"
    header_idx = None
    for i, row in df.iterrows():
        vals = [str(v).strip() for v in row.tolist()]
        if "Database" in vals and ("Query Text" in vals or "#" in vals):
            header_idx = i
            break

    if header_idx is None:
        return []

    header_vals = [str(v).strip().lower() for v in df.iloc[header_idx].tolist()]

    def _col(name):
        try:
            return header_vals.index(name.lower())
        except ValueError:
            return None

    # Both columns are resolved independently; either or both may exist.
    hash_col       = _col("#")
    query_text_col = _col("query text")
    database_col   = _col("database") if _col("database") is not None else 1

    _rf = _col("results found")
    if _rf is None:
        _rf = _col("results")
    # Avoid treating column index 0 as falsy — use explicit None check
    results_col   = _rf if _rf is not None else ((query_text_col or hash_col or 0) + 3)
    refs_kept_col = _col("refs kept")
    rationale_col = _col("rationale")

    queries = []
    seq = 1
    for i in range(header_idx + 1, len(df)):
        row = df.iloc[i]

        def _get(col_idx):
            return _val(row.iloc[col_idx]) if col_idx is not None and col_idx < len(row) else None

        # Query text: prefer the dedicated "Query Text" column; fall back to "#" column.
        query_text = _get(query_text_col) or _get(hash_col)
        database   = _get(database_col)

        if query_text is None:
            break

        # Stop when the cell is a section header with no database value
        if database is None and query_text.lower() in _SECTION_HEADERS:
            break

        results_found = _get(results_col)
        rf = None
        if results_found is not None:
            try:
                rf = int(float(results_found))
            except (ValueError, TypeError):
                pass

        queries.append({
            "query_id":      f"Q{seq}",
            "database":      database,
            "query_text":    query_text,
            "results_found": rf,
            "refs_kept":     _get(refs_kept_col),
            "rationale":     _get(rationale_col),
        })
        seq += 1

    return queries


def _parse_vocabulary_discovered(df) -> list[dict]:
    header_idx = None
    for i, row in df.iterrows():
        if str(row.iloc[0]).strip() == "Original Term":
            header_idx = i
            break

    if header_idx is None:
        return []

    vocab = []
    seq = 1
    for i in range(header_idx + 1, len(df)):
        row = df.iloc[i]
        original_term  = _val(row.iloc[0])
        raw_synonym    = _val(row.iloc[1])
        how_discovered = _val(row.iloc[2]) if len(row) > 2 else None

        if original_term is None:
            break

        # Split synonyms on comma, semicolon, pipe, slash, or newline
        if raw_synonym:
            synonyms = [s.strip() for s in re.split(r'[,;|/\n]+', raw_synonym) if s.strip()]
        else:
            synonyms = []

        vocab.append({
            "id":                 f"V{seq}",
            "original_term":      original_term,
            "discovered_synonyms": synonyms,
            "how_discovered":     how_discovered,
        })
        seq += 1

    return vocab


def _parse_classification_codes(df) -> list[dict]:
    header_idx = None
    for i, row in df.iterrows():
        if str(row.iloc[0]).strip() == "Code" and "System" in str(row.iloc[1]):
            header_idx = i
            break

    if header_idx is None:
        return []

    codes = []
    for i in range(header_idx + 1, len(df)):
        row = df.iloc[i]
        code   = _val(row.iloc[0])
        system = _val(row.iloc[1])
        reason = _val(row.iloc[2]) if len(row) > 2 else None

        if code is None:
            break

        codes.append({"code": code, "system": system, "reason": reason})

    return codes


def _parse_overall_strategy_narrative(df) -> Optional[str]:
    header_idx = None
    for i, row in df.iterrows():
        if str(row.iloc[0]).strip().lower() == "overall strategy narrative":
            header_idx = i
            break

    if header_idx is None:
        return None

    lines = []
    for i in range(header_idx + 1, len(df)):
        text = _val(df.iloc[i].iloc[0])
        if text is None:
            continue
        if text.lower().startswith("describe your search"):
            continue
        if text.lower() in _SECTION_HEADERS or text == "Expected Classification Codes":
            break
        lines.append(text)

    return " ".join(lines) if lines else None


def parse_search_strategy(file_path) -> dict:
    df = pd.read_excel(
        file_path,
        sheet_name="Part B Search Strategy",
        header=None,
    ).reset_index(drop=True)

    return {
        "databases_used":             _parse_databases_used(df),
        "queries_executed":           _parse_queries_executed(df),
        "vocabulary_discovered":      _parse_vocabulary_discovered(df),
        "expected_cpc_ipc_codes":     _parse_classification_codes(df),
        "overall_strategy_narrative": _parse_overall_strategy_narrative(df),
    }


def create_gt_search_strategy_json(strategy_dict, case_id, output_base_dir="output"):
    case_dir = os.path.join(output_base_dir, case_id)
    os.makedirs(case_dir, exist_ok=True)

    output_path = os.path.join(case_dir, "gt_search_strategy.json")
    payload = {"case_id": case_id, **strategy_dict}

    try:
        validated = GTSearchStrategy.model_validate(payload)
        data_to_write = validated.to_serializable()
    except ValidationError as exc:
        print(f"⚠️  GT search strategy validation warnings:\n{exc}")
        data_to_write = payload

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data_to_write, f, indent=2, ensure_ascii=False)

    print(f"✅ GT search strategy written to: {output_path}")
    
    
# -------------------------------
# PART B — DIFFICULTY
# -------------------------------

def parse_part_b_difficulty(file_path) -> dict:
    """Parse the 'Part B Difficulty' sheet.

    Extracts:
      - difficulty            (Assigned difficulty band, e.g. 'Easy'/'Medium'/'Hard')
      - difficulty_score      (Your perceived difficulty 1–5, int)
      - difficulty_notes      (Free-text notes from the SME)
    """
    df = pd.read_excel(
        file_path,
        sheet_name="Part B Difficulty",
        header=None,
    ).reset_index(drop=True)

    # Locate the header row that contains 'Field'
    header_idx = None
    for i, row in df.iterrows():
        if str(row.iloc[0]).strip() == "Field":
            header_idx = i
            break

    field_map = {}
    if header_idx is not None:
        for i in range(header_idx + 1, len(df)):
            row = df.iloc[i]
            field = _val(row.iloc[0])
            value = _val(row.iloc[1])
            if field:
                field_map[field.lower()] = value

    # Parse perceived difficulty as int when possible
    raw_score = field_map.get("your perceived difficulty (1\u20135)")
    difficulty_score = None
    if raw_score is not None:
        try:
            difficulty_score = int(float(raw_score))
        except (ValueError, TypeError):
            pass

    return {
        "difficulty":       field_map.get("assigned difficulty band"),
        "difficulty_score": difficulty_score,
        "difficulty_notes": field_map.get("difficulty notes"),
    }


# -------------------------------
# MAIN PIPELINE
# -------------------------------

def process_file(file_path, output_dir=None):
    """Convert a single GT Form Excel file into its fixture files.

    Reads *file_path* and writes the following into *output_dir/<case_id>/*:
      - fixture_meta.yaml
      - disclosure.md
      - gt_features.json
      - gt_references.json
      - gt_verdict.json
      - gt_search_strategy.json

    Parameters
    ----------
    file_path : str | Path
        Path to the filled-in GT Form Excel workbook.
    output_dir : str | Path, optional
        Base directory for output. Defaults to the fixtures folder
        (the directory this script lives in).
    """
    if output_dir is None:
        output_dir = _FIXTURES_DIR

    # --- Metadata (parsed first so case_id is available) ---
    part_a = parse_part_a(file_path)
    part_b = parse_part_b(file_path)

    try:
        difficulty_data = parse_part_b_difficulty(file_path)
    except Exception:
        difficulty_data = {}

    case_metadata = part_b.get("case_metadata", {})
    time_breakdown = part_b.get("time_breakdown", {})

    final_metadata = {
        **part_a,
        **case_metadata,
        "time_breakdown": time_breakdown,
        **{k: v for k, v in difficulty_data.items() if v is not None},
    }
    # SME Name from Part B takes precedence over Created By from Part A
    sme_name = final_metadata.pop("SME Name", None)
    if sme_name:
        final_metadata["created_by"] = sme_name
    final_metadata = clean_metadata(final_metadata)
    case_id = final_metadata.get("case_id")

    # --- Invention Disclosure ---
    disclosure_data = parse_invention_disclosure(file_path)
    create_invention_disclosure_md(disclosure_data, case_id, output_dir)
    create_metadata_yaml(final_metadata, output_dir)

    # --- Expected Key Features ---
    feature_list = parse_expected_key_features(file_path)
    feature_list = clean_metadata(feature_list)
    # Exclude rows that have a feature_id but no meaningful content
    feature_list = [
        f for f in feature_list
        if f.get("name") or f.get("description")
    ]
    core_count = sum(
        1 for f in feature_list if str(f.get("core") or "").strip().upper() == "Y"
    )
    gt_features_payload = {
        "case_id": case_id,
        "total_features": len(feature_list),
        "core_feature_count": core_count,
        "features": feature_list,
    }
    create_gt_features_json(gt_features_payload, case_id, output_dir)

    # --- Blocking Prior Art ---
    references_data = parse_blocking_prior_art(file_path)
    # Restrict feature_coverage to only the features defined in gt_features
    valid_feature_ids = {f["feature_id"] for f in feature_list}
    for ref in references_data.get("references", []):
        ref["feature_coverage"] = {
            fid: v for fid, v in ref.get("feature_coverage", {}).items()
            if fid in valid_feature_ids
        }
    create_gt_references_json(references_data, case_id, output_dir)

    # --- Final Verdict ---
    verdict_data = parse_final_verdict(file_path)
    create_gt_verdict_json(verdict_data, case_id, output_dir)

    # --- Search Strategy ---
    strategy_data = parse_search_strategy(file_path)
    create_gt_search_strategy_json(strategy_data, case_id, output_dir)


def process_folder(input_folder, output_dir=None):
    """Convert all GT Form Excel files in *input_folder* into fixture directories.

    Scans *input_folder* for every ``*.xlsx`` file and calls
    :func:`process_file` on each one. Fixture directories are written to
    *output_dir/<case_id>/* (defaults to the fixtures folder).

    Parameters
    ----------
    input_folder : str | Path
        Folder that contains one or more filled-in GT Form Excel workbooks.
    output_dir : str | Path, optional
        Base directory for output. Defaults to the fixtures folder
        (the directory this script lives in).
    """
    if output_dir is None:
        output_dir = _FIXTURES_DIR

    if not os.path.isdir(input_folder):
        raise ValueError(f"Input folder not found: {input_folder}")

    xlsx_files = sorted(
        os.path.join(input_folder, f)
        for f in os.listdir(input_folder)
        if f.lower().endswith(".xlsx")
    )

    if not xlsx_files:
        print(f"⚠️  No .xlsx files found in: {input_folder}")
        return

    print(f"Found {len(xlsx_files)} file(s) to process.\n")
    errors = []
    for file_path in xlsx_files:
        print(f"📄 Processing: {os.path.basename(file_path)}")
        try:
            process_file(file_path, output_dir)
        except Exception as exc:
            print(f"❌ Failed: {exc}")
            errors.append((os.path.basename(file_path), exc))
        print()

    if errors:
        print(f"⚠️  {len(errors)} file(s) failed:")
        for name, exc in errors:
            print(f"   • {name}: {exc}")
    else:
        print(f"✅ All {len(xlsx_files)} file(s) converted successfully.")


if __name__ == "__main__":
    
    # process_file("src//novelty_checker//evaluation//fixtures//inputs//C19904 - anomaly.xlsx")
    parser = argparse.ArgumentParser(
        description="Convert GT Form Excel file(s) into fixture directories."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--file", "-f",
        metavar="EXCEL_FILE",
        help="Path to a single GT Form Excel file to convert.",
    )
    group.add_argument(
        "--folder", "-d",
        metavar="INPUT_FOLDER",
        help="Path to a folder containing GT Form Excel files to convert.",
    )
    parser.add_argument(
        "--output-dir", "-o",
        metavar="OUTPUT_DIR",
        default=None,
        help=(
            "Base directory for fixture output (default: fixtures folder "
            "next to this script)."
        ),
    )

    args = parser.parse_args()

    if args.file:
        process_file(args.file, args.output_dir)
    else:
        process_folder(args.folder, args.output_dir)