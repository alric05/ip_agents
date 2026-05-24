"""Tests for report coverage verification."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.novelty_checker.utils.report_coverage import (
    CoverageGap,
    CoverageResult,
    FoundReference,
    ReportMention,
    Severity,
    compute_coverage,
    merge_found_references,
    normalize_pub_number,
    parse_accumulator_json,
    parse_references_md,
    parse_report_references,
    parse_round_findings_md,
    verify_report_coverage_from_path,
)


# =============================================================================
# normalize_pub_number
# =============================================================================


class TestNormalizePubNumber:
    def test_strips_kind_code_digit(self):
        assert normalize_pub_number("US20090071279A1") == "US20090071279A"

    def test_keeps_single_letter_kind(self):
        assert normalize_pub_number("US20090071279A") == "US20090071279A"

    def test_utility_model_unchanged(self):
        assert normalize_pub_number("CN215444943U") == "CN215444943U"

    def test_b1_to_b(self):
        assert normalize_pub_number("FR2372998B1") == "FR2372998B"

    def test_c1_to_c(self):
        assert normalize_pub_number("CN103472657C1") == "CN103472657C"

    def test_wos_id_unchanged(self):
        assert normalize_pub_number("WOS:000358027000010") == "WOS:000358027000010"

    def test_doi_unchanged(self):
        assert normalize_pub_number("10.1021/acs.analchem.2c01234") == "10.1021/acs.analchem.2c01234"

    def test_matching_variants(self):
        assert normalize_pub_number("US20090071279A1") == normalize_pub_number(
            "US20090071279A"
        )

    def test_twi_prefix(self):
        assert normalize_pub_number("TWI260905B") == "TWI260905B"

    def test_de_utility_model(self):
        assert normalize_pub_number("DE202015008913U1") == "DE202015008913U"

    def test_wo_patent(self):
        assert normalize_pub_number("WO2023131717A1") == "WO2023131717A"

    def test_ep_patent(self):
        assert normalize_pub_number("EP4127808A2") == "EP4127808A"

    def test_strips_whitespace(self):
        assert normalize_pub_number("  US4754660A  ") == "US4754660A"

    def test_no_kind_code(self):
        # Some old patents may have no kind code
        assert normalize_pub_number("US4754660") == "US4754660"


# =============================================================================
# parse_references_md
# =============================================================================


class TestParseReferencesMd:
    def test_parses_real_format(self):
        content = """# Running Reference List (deduplicated)

| Ref ID | Type | Title | Year/Priority | Source | Triage | Notes |
|---|---|---|---|---|---|---|
| US4754660A | Patent | Reduction gear for windscreen wiper drive | 1983-04-28 | Innography | A | Dual-worm |
| WOS:000358027000010 | NPL | Dual-Mode Variable Stiffness Actuator | 2015 | WoS | B | Two-stage worm |
"""
        refs = parse_references_md(content)
        assert "US4754660A" in refs
        assert refs["US4754660A"].triage == "A"
        assert refs["US4754660A"].title == "Reduction gear for windscreen wiper drive"
        assert "references_md" in refs["US4754660A"].sources
        assert "WOS:000358027000010" in refs
        assert refs["WOS:000358027000010"].triage == "B"

    def test_deduplicates_rows(self):
        content = """| Ref ID | Type | Title | Year | Source | Triage | Notes |
|---|---|---|---|---|---|---|
| US4754660A | Patent | First entry | 1983 | Innography | B | old |
| US4754660A | Patent | Second entry | 1983 | Innography | A | new |
"""
        refs = parse_references_md(content)
        assert len(refs) == 1
        assert refs["US4754660A"].triage == "A"  # Last wins

    def test_skips_separator_rows(self):
        content = """| Ref ID | Type | Title | Year | Source | Triage | Notes |
|---|---|---|---|---|---|---|
| US4754660A | Patent | Test | 1983 | Innography | A | test |
"""
        refs = parse_references_md(content)
        assert len(refs) == 1

    def test_skips_header_row(self):
        content = """| Ref ID | Type | Title | Year | Source | Triage | Notes |
|---|---|---|---|---|---|---|
| US4754660A | Patent | Test | 1983 | Innography | A | test |
"""
        refs = parse_references_md(content)
        assert "Ref ID" not in refs
        assert len(refs) == 1

    def test_empty_content(self):
        refs = parse_references_md("")
        assert len(refs) == 0

    def test_normalizes_kind_codes(self):
        content = """| Ref ID | Type | Title | Year | Source | Triage | Notes |
|---|---|---|---|---|---|---|
| FR2372998B1 | Patent | Test | 1976 | Citation | B | test |
"""
        refs = parse_references_md(content)
        assert "FR2372998B" in refs


# =============================================================================
# parse_accumulator_json
# =============================================================================


class TestParseAccumulatorJson:
    def test_parses_real_format(self):
        content = json.dumps(
            {
                "rounds": [],
                "all_references": [
                    {
                        "ref_id": "FR2372998B1",
                        "type": "patent",
                        "title": "Gear transmission",
                        "triage": "A",
                    },
                    {
                        "ref_id": "US20090071279A1",
                        "type": "patent",
                        "title": "Adjustment drive",
                        "triage": "C",
                    },
                ],
                "final_coverage": [],
            }
        )
        refs = parse_accumulator_json(content)
        assert "FR2372998B" in refs  # Normalized
        assert "US20090071279A" in refs  # Normalized

    def test_handles_publication_number_key(self):
        content = json.dumps(
            {
                "all_references": [
                    {"publication_number": "US4754660A", "title": "Test", "triage": "A"}
                ]
            }
        )
        refs = parse_accumulator_json(content)
        assert "US4754660A" in refs

    def test_handles_pub_number_key(self):
        content = json.dumps(
            {
                "all_references": [
                    {"pub_number": "CN215444943U", "title": "Test", "relevance": "A"}
                ]
            }
        )
        refs = parse_accumulator_json(content)
        assert "CN215444943U" in refs
        assert refs["CN215444943U"].triage == "A"

    def test_invalid_json(self):
        refs = parse_accumulator_json("not valid json {{{")
        assert len(refs) == 0

    def test_empty_references(self):
        refs = parse_accumulator_json(json.dumps({"all_references": []}))
        assert len(refs) == 0


# =============================================================================
# parse_round_findings_md
# =============================================================================


class TestParseRoundFindingsMd:
    def test_extracts_inline_refs(self):
        content = """# Research Round 1 Findings

- US5387162A -- Planetary worm type gear system -- (B)
- JPH0658612U -- Antenna drive -- (B)
- KR960023921A -- Mode switching device -- (C)
"""
        refs = parse_round_findings_md(content, "round_1")
        assert "US5387162A" in refs
        assert "JPH0658612U" in refs
        assert "KR960023921A" in refs
        assert refs["US5387162A"].triage == "?"  # Round files don't set triage

    def test_extracts_from_tables(self):
        content = """| US4754660A | Patent | Reduction gear | A |
| CN215444943U | Patent | Bidirectional gear box | A |
"""
        refs = parse_round_findings_md(content, "patent_round_2")
        assert "US4754660A" in refs
        assert "CN215444943U" in refs

    def test_extracts_wos_ids(self):
        content = """- WOS:000358027000010 (2015) -- Two-stage worm gear"""
        refs = parse_round_findings_md(content, "npl_round_1")
        assert "WOS:000358027000010" in refs

    def test_source_tag_preserved(self):
        content = "Found US4754660A during search."
        refs = parse_round_findings_md(content, "my_tag")
        assert "my_tag" in refs["US4754660A"].sources


# =============================================================================
# parse_report_references
# =============================================================================


class TestParseReportReferences:
    def test_extracts_feature_matrix_refs(self):
        report = """## 4. Feature Matrix (Prior Art Mapping)

| Publication Number | Ref Type | Short Description | Relevance |
|---|---|---|---|
| US4754660A | Patent | Wiper drive reduction gear | A |
| CN215444943U | Patent | Bidirectional output gear box | A |

## 5. Key Prior Art
"""
        mentions = parse_report_references(report)
        assert "US4754660A" in mentions
        assert "feature_matrix" in mentions["US4754660A"].sections
        assert "CN215444943U" in mentions

    def test_extracts_inline_refs(self):
        report = """## 5. Key Prior Art

1) **US4754660A** -- Reduction gear for windscreen wiper drive
"""
        mentions = parse_report_references(report)
        assert "US4754660A" in mentions
        assert "section_5" in mentions["US4754660A"].sections

    def test_tags_correct_sections(self):
        report = """## 1. Executive Summary

Ref US4754660A is important.

## 4. Feature Matrix

| US4754660A | Patent | Test | A |

## 8. Novelty Assessment

Mentions US4754660A again.
"""
        mentions = parse_report_references(report)
        assert "US4754660A" in mentions
        sections = mentions["US4754660A"].sections
        assert "section_1" in sections
        assert "feature_matrix" in sections
        assert "section_8" in sections


# =============================================================================
# merge_found_references
# =============================================================================


class TestMergeFoundReferences:
    def test_references_md_triage_takes_priority(self):
        from_refs_md = {
            "FR2372998B": FoundReference(
                "FR2372998B", {"FR2372998B1"}, "B", "Test", {"references_md"}
            )
        }
        from_accum = {
            "FR2372998B": FoundReference(
                "FR2372998B", {"FR2372998B1"}, "A", "Test", {"accumulator_json"}
            )
        }
        # references_md passed first = higher priority
        merged = merge_found_references(from_refs_md, from_accum)
        assert merged["FR2372998B"].triage == "B"  # references_md wins
        assert "references_md" in merged["FR2372998B"].sources
        assert "accumulator_json" in merged["FR2372998B"].sources

    def test_unknown_triage_overridden(self):
        from_round = {
            "US4754660A": FoundReference(
                "US4754660A", {"US4754660A"}, "?", "", {"round_1"}
            )
        }
        from_accum = {
            "US4754660A": FoundReference(
                "US4754660A", {"US4754660A"}, "A", "Title", {"accumulator_json"}
            )
        }
        merged = merge_found_references(from_round, from_accum)
        assert merged["US4754660A"].triage == "A"

    def test_merges_raw_ids(self):
        source1 = {
            "US20090071279A": FoundReference(
                "US20090071279A", {"US20090071279A"}, "A", "", {"references_md"}
            )
        }
        source2 = {
            "US20090071279A": FoundReference(
                "US20090071279A", {"US20090071279A1"}, "A", "", {"accumulator_json"}
            )
        }
        merged = merge_found_references(source1, source2)
        assert "US20090071279A" in merged["US20090071279A"].raw_ids
        assert "US20090071279A1" in merged["US20090071279A"].raw_ids

    def test_prefers_longer_title(self):
        source1 = {
            "US4754660A": FoundReference(
                "US4754660A", {"US4754660A"}, "A", "Short", {"references_md"}
            )
        }
        source2 = {
            "US4754660A": FoundReference(
                "US4754660A", {"US4754660A"}, "?", "A much longer title here", {"round"}
            )
        }
        merged = merge_found_references(source1, source2)
        assert merged["US4754660A"].title == "A much longer title here"


# =============================================================================
# compute_coverage
# =============================================================================


class TestComputeCoverage:
    def test_all_covered(self):
        found = {
            "US4754660A": FoundReference(
                "US4754660A", {"US4754660A"}, "A", "Wiper drive", {"references_md"}
            ),
            "WOS:000358027000010": FoundReference(
                "WOS:000358027000010",
                {"WOS:000358027000010"},
                "B",
                "NPL ref",
                {"references_md"},
            ),
        }
        reported = {
            "US4754660A": ReportMention(
                "US4754660A", "US4754660A", {"feature_matrix"}
            ),
            "WOS:000358027000010": ReportMention(
                "WOS:000358027000010", "WOS:000358027000010", {"section_6"}
            ),
        }
        result = compute_coverage(found, reported)
        assert result.is_complete
        assert result.a_coverage_pct == 100.0
        assert result.b_coverage_pct == 100.0
        assert result.overall_coverage_pct == 100.0
        assert len(result.missing_a_refs) == 0
        assert len(result.missing_b_refs) == 0

    def test_missing_a_ref(self):
        found = {
            "US4754660A": FoundReference(
                "US4754660A", {"US4754660A"}, "A", "Wiper drive", {"references_md"}
            ),
        }
        reported: dict[str, ReportMention] = {}
        result = compute_coverage(found, reported)
        assert not result.is_complete
        assert len(result.missing_a_refs) == 1
        assert result.missing_a_refs[0].severity == Severity.CRITICAL
        assert result.a_coverage_pct == 0.0

    def test_missing_b_ref(self):
        found = {
            "US5387162A": FoundReference(
                "US5387162A", {"US5387162A"}, "B", "Worm gear", {"references_md"}
            ),
        }
        reported: dict[str, ReportMention] = {}
        result = compute_coverage(found, reported)
        assert not result.is_complete
        assert len(result.missing_b_refs) == 1
        assert result.missing_b_refs[0].severity == Severity.WARNING

    def test_missing_c_ref_is_info(self):
        found = {
            "US4987791A": FoundReference(
                "US4987791A", {"US4987791A"}, "C", "Single worm", {"references_md"}
            ),
        }
        reported: dict[str, ReportMention] = {}
        result = compute_coverage(found, reported)
        assert result.is_complete  # C-refs don't affect completeness
        assert len(result.missing_c_refs) == 1
        assert result.missing_c_refs[0].severity == Severity.INFO

    def test_unexpected_ref_in_report(self):
        found: dict[str, FoundReference] = {}
        reported = {
            "US9999999A": ReportMention(
                "US9999999A", "US9999999A", {"section_5"}
            ),
        }
        result = compute_coverage(found, reported)
        assert len(result.unexpected_refs) == 1
        assert result.unexpected_refs[0].severity == Severity.UNEXPECTED

    def test_no_ab_refs_is_complete(self):
        found = {
            "US4987791A": FoundReference(
                "US4987791A", {"US4987791A"}, "C", "Test", {"references_md"}
            ),
        }
        reported: dict[str, ReportMention] = {}
        result = compute_coverage(found, reported)
        assert result.is_complete  # No A/B refs = nothing to miss

    def test_empty_inputs(self):
        result = compute_coverage({}, {})
        assert result.is_complete
        assert result.a_coverage_pct == 100.0
        assert result.b_coverage_pct == 100.0


# =============================================================================
# CoverageResult output
# =============================================================================


class TestCoverageResultOutput:
    def test_to_markdown_pass(self):
        result = CoverageResult(
            total_found_a=5,
            total_found_b=10,
            total_in_report=15,
            a_coverage_pct=100.0,
            b_coverage_pct=100.0,
            overall_coverage_pct=100.0,
        )
        md = result.to_markdown()
        assert "PASS" in md
        assert "All A and B references covered" in md

    def test_to_markdown_gaps(self):
        result = CoverageResult(
            total_found_a=5,
            missing_a_refs=[
                CoverageGap(
                    "US4754660A", "A", Severity.CRITICAL, "Test",
                    {"references_md"}, "missing",
                )
            ],
        )
        md = result.to_markdown()
        assert "GAPS DETECTED" in md
        assert "CRITICAL" in md
        assert "US4754660A" in md

    def test_to_dict(self):
        result = CoverageResult(
            total_found_a=3,
            total_found_b=5,
            a_coverage_pct=66.7,
            b_coverage_pct=80.0,
            overall_coverage_pct=75.0,
            missing_a_refs=[
                CoverageGap("US4754660A", "A", Severity.CRITICAL, "", set(), "")
            ],
        )
        d = result.to_dict()
        assert d["is_complete"] is False
        assert d["total_found_a"] == 3
        assert d["missing_a_refs"] == ["US4754660A"]


# =============================================================================
# End-to-end with real session data
# =============================================================================


class TestEndToEndWithRealSession:
    @pytest.fixture
    def session_path(self):
        p = Path("sessions/d0a73b55-07ae-405d-a4dd-f142e8acfec6")
        if not p.exists():
            pytest.skip("Real session data not available")
        return p

    def test_real_session_coverage(self, session_path: Path):
        result = verify_report_coverage_from_path(session_path)

        # Basic sanity: should find some references
        assert result.total_found_a > 0
        assert result.total_found_b > 0

        # The real report includes most A-refs
        assert result.a_coverage_pct > 50

        # Markdown output should be valid
        md = result.to_markdown()
        assert "Report Coverage Verification" in md

        # Dict output should be valid
        d = result.to_dict()
        assert "is_complete" in d
        assert "a_coverage_pct" in d

    def test_real_session_has_report(self, session_path: Path):
        assert (session_path / "final_report.md").exists()
        assert (session_path / "references.md").exists()
