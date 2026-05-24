"""Fixture loader for evaluation test cases.

Reads fixture directories following the canonical schema (fixture_schema.md)
and returns structured FixtureCase objects that the replay engine and scorers
consume.

Each fixture directory contains:
    fixture_meta.yaml       - Case metadata
    disclosure.md           - Invention text fed to the agent
    gt_features.json        - Expected features (ground truth)
    gt_references.json      - Expected references with triage and coverage
    gt_verdict.json         - Expected verdict and per-feature risk
    gt_search_strategy.json - Expected search codes and vocabulary (optional)

Usage:
    from src.novelty_checker.evaluation.fixture_loader import (
        load_fixture, discover_fixtures, FixtureCase,
    )

    # Load a single fixture
    case = load_fixture("evaluation/fixtures/TST-GEAR-001")

    # Discover all fixtures in a directory
    cases = discover_fixtures("evaluation/fixtures")

    # Discover with filters
    from src.novelty_checker.evaluation.run_config import FixtureFilter
    cases = discover_fixtures(
        "evaluation/fixtures",
        fixture_filter=FixtureFilter(difficulty="medium"),
    )
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_logger = logging.getLogger(__name__)


@dataclass
class FixtureMeta:
    """Case-level metadata from fixture_meta.yaml."""
    case_id: str
    domain: str = ""
    difficulty: str = ""
    language: str = "EN"
    source: str = ""
    created_by: str = ""
    created_date: str = ""
    template_version: str = ""
    notes: str = ""


@dataclass
class FixtureCase:
    """A complete evaluation fixture.

    Contains both the input (disclosure text for the agent) and the
    ground truth (expected features, references, verdict) for scorers.

    Attributes:
        meta: Case metadata (ID, domain, difficulty, etc.)
        disclosure_text: The invention description fed to the agent.
        gt_features: Expected features from gt_features.json.
        gt_references: Expected references from gt_references.json.
        gt_verdict: Expected verdict from gt_verdict.json.
        gt_search_strategy: Expected search strategy from gt_search_strategy.json (optional).
        fixture_path: Path to the fixture directory on disk.
    """
    meta: FixtureMeta
    disclosure_text: str
    gt_features: dict[str, Any] | None = None
    gt_references: dict[str, Any] | None = None
    gt_verdict: dict[str, Any] | None = None
    gt_search_strategy: dict[str, Any] | None = None
    fixture_path: Path | None = None

    @property
    def case_id(self) -> str:
        return self.meta.case_id


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read and parse a YAML file."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {path}, got {type(data).__name__}")
    return data


def _read_json(path: Path) -> dict[str, Any]:
    """Read and parse a JSON file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}, got {type(data).__name__}")
    return data


def _read_text(path: Path) -> str:
    """Read a text file and return its content stripped of leading/trailing whitespace."""
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def _parse_meta(raw: dict[str, Any]) -> FixtureMeta:
    """Parse fixture_meta.yaml content into a FixtureMeta dataclass."""
    case_id = raw.get("case_id", "")
    if not case_id:
        raise ValueError("fixture_meta.yaml missing required field: case_id")

    return FixtureMeta(
        case_id=str(case_id),
        domain=str(raw.get("domain", "")),
        difficulty=str(raw.get("difficulty", "")),
        language=str(raw.get("language", "EN")),
        source=str(raw.get("source", "")),
        created_by=str(raw.get("created_by", "")),
        created_date=str(raw.get("created_date", "")),
        template_version=str(raw.get("template_version", "")),
        notes=str(raw.get("notes", "")),
    )


def _validate_disclosure(text: str, case_id: str) -> list[str]:
    """Check disclosure text for common problems.

    Returns a list of warning strings (empty if all checks pass).
    """
    warnings = []

    if not text:
        warnings.append("disclosure.md is empty")
        return warnings

    if len(text) < 50:
        warnings.append(
            f"disclosure.md is very short ({len(text)} chars) - "
            "may not contain enough detail for the agent"
        )

    patent_pattern = re.compile(
        r"\b(US|EP|WO|CN|JP|KR|DE|GB|FR)\d{7,}[A-Z]?\d?\b",
        re.IGNORECASE,
    )
    matches = patent_pattern.findall(text)
    if matches:
        warnings.append(
            f"disclosure.md may contain patent numbers: {matches[:5]} - "
            "this could leak ground truth to the agent"
        )

    return warnings


def _validate_features(data: dict[str, Any], case_id: str) -> list[str]:
    """Validate gt_features.json content."""
    warnings = []
    features = data.get("features", [])

    if not features:
        warnings.append("gt_features.json has no features")
        return warnings

    if len(features) < 3:
        warnings.append(f"gt_features.json has only {len(features)} features (minimum 3 recommended)")

    ids_seen = set()
    has_core = False
    for feat in features:
        fid = feat.get("feature_id", "")
        if fid in ids_seen:
            warnings.append(f"Duplicate feature_id: {fid}")
        ids_seen.add(fid)
        if feat.get("core", False):
            has_core = True
        if not feat.get("name"):
            warnings.append(f"Feature {fid} has no name")

    if not has_core:
        warnings.append("No features marked as core=true")

    return warnings


def _validate_references(data: dict[str, Any], feature_ids: set[str], case_id: str) -> list[str]:
    """Validate gt_references.json content."""
    warnings = []
    refs = data.get("references", [])

    if not refs:
        warnings.append("gt_references.json has no references")
        return warnings

    has_a_ref = any(
        r.get("triage_label", r.get("triage", "")).upper().strip() == "A"
        for r in refs
    )
    if not has_a_ref:
        warnings.append("gt_references.json has no A-level reference")

    for ref in refs:
        rid = ref.get("ref_id", "?")
        if not ref.get("patent_family_id"):
            warnings.append(f"Reference {rid} missing patent_family_id (needed for family-level matching)")

        coverage = ref.get("feature_coverage", {})
        for fid in coverage:
            if fid not in feature_ids:
                warnings.append(
                    f"Reference {rid} has coverage for unknown feature {fid} "
                    f"(not in gt_features.json)"
                )
            val = coverage[fid]
            # if val not in ("Y", "Y1", "N"):
            #     warnings.append(f"Reference {rid} feature {fid} has invalid coverage value: {val!r}")
            if isinstance(val, dict):
                inner = val.get("verdict", "")
                if inner not in ("Y", "Y1", "N"):
                    warnings.append(f"Reference {rid} feature {fid} has invalid coverage verdict: {inner!r}")
            elif val not in ("Y", "Y1", "N"):
                warnings.append(f"Reference {rid} feature {fid} has invalid coverage value: {val!r}")

    return warnings


def _validate_verdict(data: dict[str, Any], feature_ids: set[str], case_id: str) -> list[str]:
    """Validate gt_verdict.json content."""
    warnings = []
    overall = data.get("overall", {})
    verdict = overall.get("verdict", "")

    valid_verdicts = {"novel", "partially_novel", "not_novel"}
    if verdict not in valid_verdicts:
        warnings.append(f"Invalid verdict: {verdict!r} (expected one of {valid_verdicts})")

    per_feature = data.get("per_feature_risk", [])
    pfr_ids = {item.get("feature_id") for item in per_feature}
    missing = feature_ids - pfr_ids
    if missing:
        warnings.append(f"per_feature_risk missing entries for features: {missing}")

    return warnings


def load_fixture(
    fixture_dir: str | Path,
    validate: bool = True,
) -> FixtureCase:
    """Load a single fixture from a directory.

    Args:
        fixture_dir: Path to the fixture directory (e.g., "fixtures/TST-GEAR-001").
        validate: If True, run validation checks and log warnings.

    Returns:
        A populated FixtureCase.

    Raises:
        FileNotFoundError: If required files are missing.
        ValueError: If required files cannot be parsed.
    """
    fixture_path = Path(fixture_dir)
    if not fixture_path.is_dir():
        raise FileNotFoundError(f"Fixture directory not found: {fixture_path}")

    # Required files
    meta_path = fixture_path / "fixture_meta.yaml"
    disclosure_path = fixture_path / "disclosure.md"

    if not meta_path.exists():
        raise FileNotFoundError(f"Missing required file: {meta_path}")
    if not disclosure_path.exists():
        raise FileNotFoundError(f"Missing required file: {disclosure_path}")

    meta = _parse_meta(_read_yaml(meta_path))
    disclosure_text = _read_text(disclosure_path)

    # Ground truth files (required for scoring but fixture can load without them)
    gt_features = None
    gt_references = None
    gt_verdict = None
    gt_search_strategy = None

    gt_features_path = fixture_path / "gt_features.json"
    gt_references_path = fixture_path / "gt_references.json"
    gt_verdict_path = fixture_path / "gt_verdict.json"
    gt_search_strategy_path = fixture_path / "gt_search_strategy.json"

    if gt_features_path.exists():
        gt_features = _read_json(gt_features_path)
    else:
        _logger.warning("No gt_features.json in %s", fixture_path.name)

    if gt_references_path.exists():
        gt_references = _read_json(gt_references_path)
    else:
        _logger.warning("No gt_references.json in %s", fixture_path.name)

    if gt_verdict_path.exists():
        gt_verdict = _read_json(gt_verdict_path)
    else:
        _logger.warning("No gt_verdict.json in %s", fixture_path.name)

    if gt_search_strategy_path.exists():
        gt_search_strategy = _read_json(gt_search_strategy_path)

    # Validation
    if validate:
        all_warnings = []
        all_warnings.extend(_validate_disclosure(disclosure_text, meta.case_id))

        if gt_features is not None:
            all_warnings.extend(_validate_features(gt_features, meta.case_id))

        feature_ids = set()
        if gt_features is not None:
            feature_ids = {f.get("feature_id", "") for f in gt_features.get("features", [])}

        if gt_references is not None:
            all_warnings.extend(_validate_references(gt_references, feature_ids, meta.case_id))

        if gt_verdict is not None:
            all_warnings.extend(_validate_verdict(gt_verdict, feature_ids, meta.case_id))

        if all_warnings:
            _logger.warning(
                "Fixture %s has %d validation warning(s):\n  %s",
                meta.case_id,
                len(all_warnings),
                "\n  ".join(all_warnings),
            )
        else:
            _logger.debug("Fixture %s passed all validation checks", meta.case_id)

    case = FixtureCase(
        meta=meta,
        disclosure_text=disclosure_text,
        gt_features=gt_features,
        gt_references=gt_references,
        gt_verdict=gt_verdict,
        gt_search_strategy=gt_search_strategy,
        fixture_path=fixture_path,
    )

    _logger.info(
        "Loaded fixture %s (domain=%s, difficulty=%s, disclosure=%d chars)",
        meta.case_id,
        meta.domain,
        meta.difficulty,
        len(disclosure_text),
    )

    return case


def discover_fixtures(
    fixtures_dir: str | Path,
    fixture_filter: Any | None = None,
) -> list[FixtureCase]:
    """Discover and load all fixtures in a directory.

    Scans for subdirectories containing fixture_meta.yaml,
    loads each one, and optionally filters by domain/difficulty/language.

    Args:
        fixtures_dir: Path to the directory containing fixture subdirectories.
        fixture_filter: Optional FixtureFilter (from run_config) to select
            a subset. If None, all fixtures are returned.

    Returns:
        List of loaded FixtureCase objects, sorted by case_id.
    """
    fixtures_path = Path(fixtures_dir)
    if not fixtures_path.is_dir():
        raise FileNotFoundError(f"Fixtures directory not found: {fixtures_path}")

    cases = []
    skipped = 0

    for child in sorted(fixtures_path.iterdir()):
        if not child.is_dir():
            continue
        meta_file = child / "fixture_meta.yaml"
        if not meta_file.exists():
            continue

        try:
            case = load_fixture(child)
        except Exception as exc:
            _logger.error("Failed to load fixture from %s: %s", child.name, exc)
            skipped += 1
            continue

        # Apply filters
        if fixture_filter is not None and not _matches_filter(case, fixture_filter):
            _logger.debug(
                "Fixture %s excluded by filter (domain=%s, difficulty=%s, language=%s)",
                case.case_id, case.meta.domain, case.meta.difficulty, case.meta.language,
            )
            continue

        cases.append(case)

    _logger.info(
        "Discovered %d fixtures in %s (skipped %d due to errors)",
        len(cases),
        fixtures_path,
        skipped,
    )

    return cases


def _matches_filter(case: FixtureCase, fixture_filter: Any) -> bool:
    """Check if a fixture matches the given filter criteria.


    """
    filter_domain = getattr(fixture_filter, "domain", None)
    filter_difficulty = getattr(fixture_filter, "difficulty", None)
    filter_language = getattr(fixture_filter, "language", None)

    if filter_domain is not None and case.meta.domain != filter_domain:
        return False
    if filter_difficulty is not None and case.meta.difficulty != filter_difficulty:
        return False
    if filter_language is not None and case.meta.language != filter_language:
        return False

    return True