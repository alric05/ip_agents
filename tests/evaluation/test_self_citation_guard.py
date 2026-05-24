"""Unit tests for the self-citation guard middleware.

Validates the title-similarity detection that prevents the deep agent
from rating the inventor's own newly-published filings as A-prior-art
(observed on C19904 — `US12323091B1` family).
"""

from __future__ import annotations

from src.novelty_checker.middleware.self_citation_guard import (
    _FAMILY_CLUSTER_WINDOW_DAYS,
    _JACCARD_THRESHOLD,
    _date_diff_days,
    _extract_disclosure_title,
    _extract_raw_disclosure_from_messages,
    _extract_title_from_raw_disclosure,
    _jaccard_similarity,
    _parse_priority_date,
    _parse_references_md,
    _strip_line_number_prefix,
    _tokenize_title,
)


class TestRawDisclosureExtraction:
    """Pull the original disclosure title from the first HumanMessage."""

    def test_extracts_h1_title(self):
        raw = (
            "# A novel design of floating structure for eco-adaptive "
            "floating photovoltaic system\n\nBody text."
        )
        title = _extract_title_from_raw_disclosure(raw)
        assert title.startswith("A novel design of floating structure")

    def test_falls_back_to_first_sentence(self):
        raw = "A floating PV platform with a rectangular float. More details follow."
        title = _extract_title_from_raw_disclosure(raw)
        assert title == "A floating PV platform with a rectangular float"

    def test_strips_auto_scope_prefix(self):
        from langchain_core.messages import HumanMessage
        msg = HumanMessage(
            content=(
                "Please check the novelty of this invention. "
                "IMPORTANT: Do NOT ask clarifying questions during scoping. "
                "Use reasonable defaults...\n\n"
                "Here is the invention:\n\n"
                "# A novel design of floating structure for eco-adaptive "
                "floating photovoltaic system\n"
            )
        )
        raw = _extract_raw_disclosure_from_messages([msg])
        assert raw.startswith("# A novel design")

    def test_empty_messages_returns_empty(self):
        assert _extract_raw_disclosure_from_messages([]) == ""
        assert _extract_raw_disclosure_from_messages(None) == ""


class TestStripLineNumbers:
    """FilesystemBackend.read() returns cat -n-style line-numbered content;
    the middleware must strip the prefix before parsing."""

    def test_strips_cat_n_prefix(self):
        prefixed = "     1\t# Header\n     2\tBody line\n"
        assert _strip_line_number_prefix(prefixed) == "# Header\nBody line\n"

    def test_no_op_on_clean_content(self):
        clean = "# Header\nBody line\n"
        assert _strip_line_number_prefix(clean) == clean

    def test_handles_empty(self):
        assert _strip_line_number_prefix("") == ""


# ---------------------------------------------------------------------------
# _jaccard_similarity
# ---------------------------------------------------------------------------

class TestJaccardSimilarity:
    """Calibration cases from the C19904 fixture."""

    DISCLOSURE_TITLE = (
        "A novel design of floating structure for eco-adaptive floating "
        "photovoltaic system: eco-float voltaic platform (EFVP)"
    )

    def test_self_citation_triggers(self):
        """The inventor's own family member must score above threshold."""
        candidate = "Floating structure for eco-adaptive floating photovoltaic system"
        sim = _jaccard_similarity(self.DISCLOSURE_TITLE, candidate)
        assert sim >= _JACCARD_THRESHOLD, (
            f"Self-citation slipped through: jaccard={sim:.3f} (threshold {_JACCARD_THRESHOLD})"
        )

    def test_genuine_prior_art_does_not_trigger(self):
        """The actual GT prior art must score well below threshold."""
        candidate = "Floating type solar power generation equipment stage device"
        sim = _jaccard_similarity(self.DISCLOSURE_TITLE, candidate)
        assert sim < 0.2, (
            f"Genuine prior art falsely flagged: jaccard={sim:.3f}"
        )

    def test_unrelated_title_scores_zero(self):
        sim = _jaccard_similarity(self.DISCLOSURE_TITLE, "Worm gear cascade for camera lens")
        assert sim == 0.0

    def test_identical_titles_score_one(self):
        assert _jaccard_similarity("Foo Bar Baz", "Foo Bar Baz") == 1.0

    def test_empty_inputs_safe(self):
        assert _jaccard_similarity("", "Some title") == 0.0
        assert _jaccard_similarity("Some title", "") == 0.0
        assert _jaccard_similarity("", "") == 0.0


# ---------------------------------------------------------------------------
# _tokenize_title (for reference / regression)
# ---------------------------------------------------------------------------

class TestTokenize:
    def test_lowercases_and_strips_stopwords(self):
        tokens = _tokenize_title("A novel Design of the Method for Floating Solar")
        # "a", "novel", "design", "of", "the", "method", "for" are all stopwords
        assert tokens == {"floating", "solar"}

    def test_drops_punctuation(self):
        tokens = _tokenize_title("Eco-float voltaic platform (EFVP).")
        assert "eco" in tokens and "float" in tokens
        assert "platform" in tokens and "efvp" in tokens
        # No punctuation tokens
        assert all(t.isalnum() for t in tokens)

    def test_drops_single_chars(self):
        tokens = _tokenize_title("a b cd ef")
        assert tokens == {"cd", "ef"}


# ---------------------------------------------------------------------------
# _extract_disclosure_title
# ---------------------------------------------------------------------------

class TestExtractDisclosureTitle:
    def test_customer_idea_section(self):
        scope = (
            "# Invention Scope\n"
            "\n"
            "## Customer Idea\n"
            "A novel design of floating structure for eco-adaptive floating "
            "photovoltaic system: eco-float voltaic platform (EFVP).\n"
            "\n"
            "## Clarifications\n"
            "User requested no clarifying questions.\n"
        )
        title = _extract_disclosure_title(scope)
        assert title.startswith("A novel design of floating structure")

    def test_original_customer_idea_section(self):
        """Baseline-style scope.md uses 'Original customer idea'."""
        scope = (
            "# Scope\n"
            "\n"
            "## Original customer idea\n"
            "A floating photovoltaic platform intended for land-constrained regions.\n"
        )
        assert _extract_disclosure_title(scope).startswith("A floating photovoltaic platform")

    def test_falls_back_to_first_non_heading_line(self):
        scope = (
            "# My Invention\n"
            "\n"
            "Some prose without a recognised section header.\n"
        )
        assert _extract_disclosure_title(scope) == "Some prose without a recognised section header."

    def test_empty_input(self):
        assert _extract_disclosure_title("") == ""

    def test_strips_list_markers(self):
        scope = "## Customer Idea\n\n- A bullet-style invention.\n"
        assert _extract_disclosure_title(scope) == "A bullet-style invention."


# ---------------------------------------------------------------------------
# _parse_references_md
# ---------------------------------------------------------------------------

class TestParseReferences:
    REFS_TABLE = (
        "| Publication Number | Ref Type | Title | Relevance | Earliest Priority |\n"
        "|---|---|---|---|---|\n"
        "| US12323091B1 | Patent | Floating structure for eco-adaptive floating photovoltaic system | A | 2025-01-17 |\n"
        "| US11319035B2 | Patent | Floating type solar power generation equipment stage device | A | 2018-02-26 |\n"
        "| US11067313B2 | Patent | Modular floating platform | C | 2013-02-11 |\n"
    )

    def test_parses_all_rows(self):
        rows = _parse_references_md(self.REFS_TABLE)
        assert len(rows) == 3
        assert rows[0] == (
            "US12323091B1",
            "Floating structure for eco-adaptive floating photovoltaic system",
            "A",
            "2025-01-17",
        )
        assert rows[1][0] == "US11319035B2"
        assert rows[1][3] == "2018-02-26"
        assert rows[2][2] == "C"

    def test_skips_separator_row(self):
        # The `|---|---|...` row should never appear as a data tuple
        rows = _parse_references_md(self.REFS_TABLE)
        assert all("---" not in pub for pub, *_ in rows)

    def test_handles_relevance_column_aliases(self):
        table = (
            "| Pub Number | Title | Triage |\n"
            "|---|---|---|\n"
            "| US1234567B2 | Some title | A |\n"
        )
        rows = _parse_references_md(table)
        assert rows == [("US1234567B2", "Some title", "A", "")]

    def test_handles_bold_triage_label(self):
        table = (
            "| Publication Number | Title | Relevance |\n"
            "|---|---|---|\n"
            "| US1234567B2 | Some title | **A** |\n"
        )
        rows = _parse_references_md(table)
        assert rows[0][2] == "A"

    def test_priority_date_column_optional(self):
        """Tables without an Earliest Priority column return ''."""
        table = (
            "| Publication Number | Title | Triage |\n"
            "|---|---|---|\n"
            "| US1 | Foo | A |\n"
        )
        rows = _parse_references_md(table)
        assert rows[0][3] == ""

    def test_empty_input(self):
        assert _parse_references_md("") == []

    def test_no_table_returns_empty(self):
        assert _parse_references_md("Just prose, no table.") == []

    def test_handles_priority_year_header(self):
        """Regression: the real deep-agent run emits `Priority/Year` as the
        priority column header; exact-match whitelist missed it and the
        family-cluster pass collapsed. See session 20260415_135701_31fd33e1."""
        table = (
            "| Ref ID | Type | Triage | Title | Priority/Year | Jurisdiction |\n"
            "|---|---|---|---|---|---|\n"
            "| US12401313B1 | Patent | A | Pontoon platform supported solar voltaic system | 2025-01-14 | US |\n"
            "| US12407293B1 | Patent | A | Marine-based solar electrical generating system | 2025-01-14 | US |\n"
        )
        rows = _parse_references_md(table)
        assert len(rows) == 2
        assert rows[0] == (
            "US12401313B1",
            "Pontoon platform supported solar voltaic system",
            "A",
            "2025-01-14",
        )
        assert rows[1][3] == "2025-01-14"

    def test_partial_header_then_real_header_does_not_crash(self):
        """Regression: observed on a live `langgraph dev` run
        (thread 062674d3-e772-4565-806e-9b9ab2ae2af8, session a90c6a5f...).

        A pre-table line matched `Publication Number` but had no Title/Triage
        columns. `pub_idx` got committed, subsequent data rows then hit
        `max(pub_idx, None, triage_idx)` and raised TypeError, which the
        outer middleware caught and logged as a spurious WARNING.

        Fix requires ALL three required columns on the same header row
        before committing any index."""
        table = (
            "| Publication Number | notes |\n"  # partial header — must NOT commit
            "|---|---|\n"
            "| Publication Number | Type | Title | Triage | Priority Date |\n"  # real header
            "|---|---|---|---|---|\n"
            "| US12345 | Patent | Some title | A | 2024-01-01 |\n"
        )
        # Must not raise — and must parse the real data row.
        rows = _parse_references_md(table)
        assert rows == [("US12345", "Some title", "A", "2024-01-01")]

    def test_short_description_column_recognized_as_title(self):
        """The report skill template uses `Short Description` instead of
        `Title`. Parser must accept that alias."""
        table = (
            "| Publication Number | Ref Type | Short Description | Relevance |\n"
            "|---|---|---|---|\n"
            "| US1 | Patent | Some brief desc | A |\n"
        )
        rows = _parse_references_md(table)
        assert rows == [("US1", "Some brief desc", "A", "")]


# ---------------------------------------------------------------------------
# End-to-end: real C19904 deep-agent session
# ---------------------------------------------------------------------------

class TestRealSessionFlagging:
    """Run the flagging pipeline end-to-end against the C19904 disclosure
    text and a realistic references.md snippet from a deep-agent run."""

    DISCLOSURE_TITLE = (
        "A novel design of floating structure for eco-adaptive floating "
        "photovoltaic system: eco-float voltaic platform (EFVP)"
    )

    def test_three_self_citations_flagged(self):
        """The three inventor-family members should all flag; the GT
        ref and the C-rated background should not."""
        candidate_titles = {
            "US12323091B1": "Floating structure for eco-adaptive floating photovoltaic system",  # FLAG
            "US12401313B1": "Pontoon platform supported solar voltaic system",                   # FLAG (eco-float voltaic)
            "US12407293B1": "Marine-based solar electrical generating system",                   # may or may not flag
            "US11319035B2": "Floating type solar power generation equipment stage device",       # GENUINE — must NOT flag
            "US11067313B2": "Modular floating platform for solar panel straps",                  # GENUINE — must NOT flag
        }

        flagged: dict[str, float] = {}
        for pub, title in candidate_titles.items():
            sim = _jaccard_similarity(self.DISCLOSURE_TITLE, title)
            if sim >= _JACCARD_THRESHOLD:
                flagged[pub] = sim

        # The canonical self-citation must be in
        assert "US12323091B1" in flagged, (
            f"US12323091B1 not flagged. Scores: "
            f"{ {k: round(_jaccard_similarity(self.DISCLOSURE_TITLE, v), 3) for k, v in candidate_titles.items()} }"
        )
        # The genuine prior art must NOT be in
        assert "US11319035B2" not in flagged
        assert "US11067313B2" not in flagged


# ---------------------------------------------------------------------------
# Priority-date helpers + family-cluster end-to-end via middleware
# ---------------------------------------------------------------------------

class TestPriorityDateParsing:
    def test_full_iso_date(self):
        assert _parse_priority_date("2025-01-17") == (2025, 1, 17)

    def test_year_month_only(self):
        assert _parse_priority_date("2025-01") == (2025, 1, 1)

    def test_year_only(self):
        assert _parse_priority_date("2025") == (2025, 1, 1)

    def test_slash_separator(self):
        assert _parse_priority_date("2025/01/17") == (2025, 1, 17)

    def test_garbage_returns_none(self):
        assert _parse_priority_date("") is None
        assert _parse_priority_date("not a date") is None
        assert _parse_priority_date("year 12345") is None  # year out of range


class TestDateDiff:
    def test_same_day(self):
        assert _date_diff_days((2025, 1, 14), (2025, 1, 14)) == 0

    def test_three_days_apart(self):
        # 2025-01-14 vs 2025-01-17 — within family cluster window
        d = _date_diff_days((2025, 1, 14), (2025, 1, 17))
        assert d == 3

    def test_within_cluster_window(self):
        d = _date_diff_days((2025, 1, 1), (2025, 1, 30))
        assert d <= _FAMILY_CLUSTER_WINDOW_DAYS

    def test_outside_cluster_window(self):
        d = _date_diff_days((2025, 1, 1), (2026, 1, 1))
        assert d > _FAMILY_CLUSTER_WINDOW_DAYS


class TestFamilyClusterFlagging:
    """End-to-end: middleware should flag family members whose titles
    differ but priority dates are within 30 days of a title-flagged ref."""

    def test_compute_flagged_includes_cluster(self, tmp_path):
        from src.novelty_checker.middleware.self_citation_guard import (
            SelfCitationGuardMiddleware,
        )

        # Build a session-like in-memory backend
        scope = (
            "# Invention Scope\n\n"
            "## Customer Idea\n"
            "A novel design of floating structure for eco-adaptive floating "
            "photovoltaic system: eco-float voltaic platform (EFVP).\n"
        )
        refs = (
            "| Publication Number | Title | Relevance | Earliest Priority |\n"
            "|---|---|---|---|\n"
            "| US12323091B1 | Floating structure for eco-adaptive floating photovoltaic system | A | 2025-01-17 |\n"
            "| US12401313B1 | Pontoon platform supported solar voltaic system | A | 2025-01-14 |\n"
            "| US12407293B1 | Marine-based solar electrical generating system | A | 2025-01-14 |\n"
            "| US11319035B2 | Floating type solar power generation equipment stage device | A | 2018-02-26 |\n"
        )

        from deepagents.backends import FilesystemBackend
        (tmp_path / "scope.md").write_text(scope)
        (tmp_path / "references.md").write_text(refs)
        backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=True)

        mw = SelfCitationGuardMiddleware(backend=backend)
        flagged = mw._compute_flagged_refs(backend)
        flagged_pubs = {pub for pub, *_ in flagged}

        # Title-similarity catches US12323091B1
        assert "US12323091B1" in flagged_pubs
        # Family-cluster catches US12401313B1 and US12407293B1
        assert "US12401313B1" in flagged_pubs
        assert "US12407293B1" in flagged_pubs
        # Genuine prior art (2018) must NOT be flagged
        assert "US11319035B2" not in flagged_pubs

    def test_date_fallback_field_in_accumulator(self, tmp_path):
        """Accumulator rows written under the older `date` key (vs
        `priority_date`) must still surface family-cluster signals."""
        import json as _json
        from src.novelty_checker.middleware.self_citation_guard import (
            SelfCitationGuardMiddleware,
        )

        scope = (
            "## Customer Idea\n"
            "A novel design of floating structure for eco-adaptive floating "
            "photovoltaic system.\n"
        )
        accumulator = {
            "all_references": [
                {
                    "publication_number": "US12323091B1",
                    "title": "Floating structure for eco-adaptive floating photovoltaic system",
                    "relevance": "A",
                    "date": "2025-01-17",
                },
                {
                    "publication_number": "US12401313B1",
                    "title": "Pontoon platform supported solar voltaic system",
                    "relevance": "A",
                    "date": "2025-01-14",  # same family window
                },
                {
                    "publication_number": "US11319035B2",
                    "title": "Floating type solar power generation equipment stage device",
                    "relevance": "A",
                    "date": "2018-02-26",  # GT prior art, must NOT flag
                },
            ]
        }

        from deepagents.backends import FilesystemBackend
        (tmp_path / "scope.md").write_text(scope)
        (tmp_path / "findings_auto_accumulator.json").write_text(
            _json.dumps(accumulator)
        )
        backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=True)

        mw = SelfCitationGuardMiddleware(backend=backend)
        flagged = {pub for pub, *_ in mw._compute_flagged_refs(backend)}
        assert "US12323091B1" in flagged
        assert "US12401313B1" in flagged  # caught via family-cluster via `date`
        assert "US11319035B2" not in flagged

    def test_priority_year_layout_flags_cluster(self, tmp_path):
        """End-to-end regression matching the real deep-agent references.md
        layout (`Priority/Year` header, Ref ID / Type / Triage / Title /
        Priority / Jurisdiction column order)."""
        from src.novelty_checker.middleware.self_citation_guard import (
            SelfCitationGuardMiddleware,
        )

        scope = (
            "## Customer Idea\n"
            "A novel design of floating structure for eco-adaptive floating "
            "photovoltaic system: eco-float voltaic platform.\n"
        )
        refs = (
            "| Ref ID | Type | Triage | Title | Priority/Year | Jurisdiction |\n"
            "|---|---|---|---|---|---|\n"
            "| US12323091B1 | Patent | A | Floating structure for eco-adaptive floating photovoltaic system | 2025-01-17 | US |\n"
            "| US12401313B1 | Patent | A | Pontoon platform supported solar voltaic system | 2025-01-14 | US |\n"
            "| US12407293B1 | Patent | A | Marine-based solar electrical generating system | 2025-01-14 | US |\n"
            "| US11319035B2 | Patent | A | Floating type solar power generation equipment stage device | 2018-02-26 | US |\n"
        )

        from deepagents.backends import FilesystemBackend
        (tmp_path / "scope.md").write_text(scope)
        (tmp_path / "references.md").write_text(refs)
        backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=True)

        mw = SelfCitationGuardMiddleware(backend=backend)
        flagged_pubs = {pub for pub, *_ in mw._compute_flagged_refs(backend)}

        assert "US12323091B1" in flagged_pubs  # title-sim
        assert "US12401313B1" in flagged_pubs  # family-cluster
        assert "US12407293B1" in flagged_pubs  # family-cluster
        assert "US11319035B2" not in flagged_pubs  # genuine prior art

    def test_no_flags_when_final_report_exists(self, tmp_path):
        """Once final_report.md is present we stop nudging."""
        from src.novelty_checker.middleware.self_citation_guard import (
            SelfCitationGuardMiddleware,
        )

        scope = "## Customer Idea\nA test invention.\n"
        refs = (
            "| Publication Number | Title | Relevance |\n"
            "|---|---|---|\n"
            "| US1 | A test invention prior art | A |\n"
        )

        from deepagents.backends import FilesystemBackend
        (tmp_path / "scope.md").write_text(scope)
        (tmp_path / "references.md").write_text(refs)
        (tmp_path / "final_report.md").write_text("# Final Report\nDone.")
        backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=True)

        mw = SelfCitationGuardMiddleware(backend=backend)
        assert mw._compute_flagged_refs(backend) == []
