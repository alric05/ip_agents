"""Regression tests for scorer robustness fixes.

Covers two bugs that silently scored the deep agent at 0 on verdict
accuracy and report completeness for C19904:

1. `extract_verdict_from_report` used substring heuristics without word
   boundaries — "this novelty report" matched `(?:is)\\s+novel` and
   produced a false "novel" verdict.

2. `_match_section` used plain substring matching, so a header like
   "Landscape Overview (Concise)" could claim the "executive summary"
   slot via the "overview" alias.
"""

from __future__ import annotations

from pathlib import Path

from src.novelty_checker.evaluation.scorers._loader import extract_verdict_from_report
from src.novelty_checker.evaluation.scorers.tier2.report_completeness import (
    _REQUIRED_SECTIONS,
    _match_section,
)


# ---------------------------------------------------------------------------
# extract_verdict_from_report
# ---------------------------------------------------------------------------

class TestVerdictExtraction:
    """Verdict extraction regression cases."""

    def test_strict_verdict_line_not_novel(self):
        """Baseline-style explicit verdict line extracts cleanly."""
        text = "## 9. Verdict\n\n**Verdict: not novel in the searched record** [US12323091B1]."
        assert extract_verdict_from_report(text) == "not_novel"

    def test_novelty_risk_with_parenthetical_qualifier(self):
        """Deep-agent run-3 phrasing with a parenthetical before the colon."""
        text = "**Novelty risk (search-based only)**: **high prior-art density**."
        assert extract_verdict_from_report(text) == "not_novel"

    def test_high_prior_art_density_signal(self):
        """'high prior-art density' alone is a not_novel signal."""
        text = "The search surfaced high prior-art density across all core features."
        assert extract_verdict_from_report(text) == "not_novel"

    def test_novelty_risk_low(self):
        text = "Novelty risk: low based on the current search record."
        assert extract_verdict_from_report(text) == "novel"

    def test_this_novelty_report_is_not_a_verdict(self):
        """Regression: 'this novelty report' must NOT match 'is novel'.

        Bug A: missing word boundaries caused th-IS-⎵-NOVEL-ty
        to substring-match `(?:is)\\s+novel`.
        """
        text = "This novelty report covers the searched record only."
        # Should NOT return "novel" — no real verdict in this text.
        assert extract_verdict_from_report(text) != "novel"

    def test_empty_report_returns_none(self):
        assert extract_verdict_from_report("") is None

    def test_unrelated_text_returns_none(self):
        assert extract_verdict_from_report("The weather is nice today.") is None

    def test_partially_novel_moderate_risk(self):
        text = "Novelty risk: moderate — some features have partial coverage."
        assert extract_verdict_from_report(text) == "partially_novel"


# ---------------------------------------------------------------------------
# _match_section
# ---------------------------------------------------------------------------

class TestSectionMatching:
    """Section alias / canonical matching regression cases."""

    def test_landscape_overview_does_not_claim_executive_summary(self):
        """Regression for substring trap.

        Old behavior: "overview" in "landscape overview" -> executive summary.
        New behavior: whole-word match only, so no claim.
        """
        # "landscape overview" contains "overview" as a word, but "overview"
        # is not in the alias list any more (intentionally removed).
        # Assert it does not map to executive summary.
        assert _match_section("Landscape Overview (Concise)", _REQUIRED_SECTIONS) != "executive summary"

    def test_gap_analysis_table_maps_to_feature_coverage(self):
        assert _match_section("Gap Analysis Table", _REQUIRED_SECTIONS) == "feature coverage"

    def test_search_traceability_maps_to_search_strategy(self):
        assert _match_section("Search Traceability (Addendum)", _REQUIRED_SECTIONS) == "search strategy"

    def test_patent_record_maps_to_prior_art(self):
        assert _match_section("Patent Record: US12323091B1", _REQUIRED_SECTIONS) == "prior art analysis"

    def test_sources_maps_to_references(self):
        assert _match_section("Sources", _REQUIRED_SECTIONS) == "references"

    def test_novelty_risk_maps_to_risk_assessment(self):
        assert _match_section("Novelty Risk", _REQUIRED_SECTIONS) == "risk assessment"

    def test_recommendations_for_further_searching(self):
        assert (
            _match_section("Recommendations for Further Searching", _REQUIRED_SECTIONS)
            == "recommendations"
        )

    def test_canonical_header_still_matches_itself(self):
        for section in _REQUIRED_SECTIONS:
            assert _match_section(section, _REQUIRED_SECTIONS) == section

    def test_direct_substring_match_requires_word_boundary(self):
        """"scopecopy" must NOT match "scope"."""
        assert _match_section("scopecopy", _REQUIRED_SECTIONS) != "scope"

    def test_unrelated_header_returns_none(self):
        assert _match_section("Completely Unrelated Text", _REQUIRED_SECTIONS) is None


# ---------------------------------------------------------------------------
# End-to-end: rescore the deep-agent run-3 report
# ---------------------------------------------------------------------------

class TestEndToEnd:
    """Sanity check against real saved sessions (when present)."""

    def test_deep_agent_run3_has_extractable_verdict(self, tmp_path):
        """Synthetic report mirroring deep-agent run-3 phrasing."""
        synthetic = (
            "## 1. Key Finding / Executive Summary\n\n"
            "**Novelty risk (search-based only)**: **high prior-art density** "
            "for the overall integrated concept, especially due to the close "
            "recent floating PV patent family.\n"
        )
        assert extract_verdict_from_report(synthetic) == "not_novel"

    def test_synthetic_deep_agent_sections_all_match(self):
        """Synthetic headers representative of deep-agent run-3."""
        headers_to_expected = {
            "Key Finding / Executive Summary": "executive summary",
            "Scope": "scope",
            "Feature Matrix (Core Analytical Deliverable)": "feature matrix",
            "Search Traceability (Addendum)": "search strategy",
            "Patent Record: US12323091B1": "prior art analysis",
            "Gap Analysis Table": "feature coverage",
            "Novelty Risk": "risk assessment",
            "Next Steps": "recommendations",
            "Sources": "references",
        }
        for header, expected in headers_to_expected.items():
            actual = _match_section(header, _REQUIRED_SECTIONS)
            assert actual == expected, f"{header!r} -> {actual!r}, expected {expected!r}"
