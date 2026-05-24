"""Tests for PatentTrackingMiddleware backfill wiring.

Covers the observability fixes that make `patent_statistics.json` reflect
reality after runs where subagents bypass `save_round_findings`:
 - `summarize_findings_for_report` no longer triggers finalize early.
 - `references.md` Y/N feature matrix populates FEATURE_MAPPED.
 - `save_round_findings` refs carry their source through to stats.
 - Accumulator backfill reads both `/findings_accumulator.json` and
   `/findings_auto_accumulator.json`.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from src.novelty_checker.middleware import patent_tracking as pt_module
from src.novelty_checker.middleware.patent_tracking import (
    PatentTrackingMiddleware,
    _FINALIZE_SIGNAL_TOOLS,
)
from src.novelty_checker.observability.patent_tracker import (
    PatentCheckpoint,
    PatentTracker,
)


class _InMemoryBackend:
    """Minimal backend stub: dict-backed read/write matching FilesystemBackend shape."""

    def __init__(self, files: dict[str, str] | None = None) -> None:
        self._files: dict[str, str] = dict(files or {})

    def read(self, path: str) -> str:
        if path not in self._files:
            return f"Error: {path} not found"
        return self._files[path]

    def write(self, path: str, content: str) -> None:
        self._files[path] = content

    def exists(self, path: str) -> bool:
        return path in self._files


class _FakeToolCallRequest:
    def __init__(self, name: str, args: dict[str, Any] | None = None) -> None:
        self.tool_call = {"name": name, "args": args or {}}
        self.runtime = None


def _make_middleware(backend: _InMemoryBackend, tracker: PatentTracker):
    return PatentTrackingMiddleware(backend=backend, tracker=tracker)


def test_summarize_findings_no_longer_triggers_finalize():
    """Removing summarize_findings_for_report from _FINALIZE_SIGNAL_TOOLS
    prevents finalize from running before the final report exists."""
    assert "summarize_findings_for_report" not in _FINALIZE_SIGNAL_TOOLS


def test_references_md_feature_matrix_populates_feature_mapped():
    """The references.md format used in production (pipe-separated Y/N/Y1 cells)
    must emit FEATURE_MAPPED for each row."""
    references_md = (
        "| Ref ID | Type | Title | Triage | F1 | F2 | F3 | F4 | F5 |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        "| US11796036B2 | Patent | Actuator | A | N | Y | N | Y | N |\n"
        "| US20240345459A1 | Patent | Lens barrel unit | A | N | Y | Y | Y1 | N |\n"
        "| US6707194B2 | Patent | Motor device | A | N | Y | Y | Y | N |\n"
    )
    backend = _InMemoryBackend({"/references.md": references_md})
    tracker = PatentTracker(session_id="t-feature-mapped")
    mw = _make_middleware(backend, tracker)

    mw._backfill_feature_mapped_from_references(backend, tracker)

    stats = tracker.generate_statistics()
    assert stats["summary"]["total_feature_mapped"] == 3


def test_record_persisted_derives_source_from_refs():
    """Refs with a `source_tool` hint should land under the correct
    funnel bucket, not `Other`."""
    tracker = PatentTracker(session_id="t-source")
    mw = PatentTrackingMiddleware(
        backend=_InMemoryBackend(),
        tracker=tracker,
    )
    request = _FakeToolCallRequest(
        "save_round_findings",
        args={
            "round_number": 1,
            # No top-level source: force the source to come from each ref.
            "references": [
                {"publication_number": "US1111111A", "source_tool": "patent_keyword_search"},
                {"publication_number": "US2222222A", "source_tool": "npl_search"},
            ],
        },
    )

    class _Result:
        content = "OK"

    mw._record_persisted(request, _Result())

    stats = tracker.generate_statistics()
    by_source = stats["by_source"]
    assert by_source.get("patent", {}).get("persisted", 0) == 1
    assert by_source.get("npl", {}).get("persisted", 0) == 1
    # No refs should be bucketed under "other"
    assert by_source.get("other", {}).get("persisted", 0) == 0


def test_record_persisted_also_records_discovered():
    """save_round_findings should also emit DISCOVERED for each ref so the
    funnel doesn't show negative loss (persisted > discovered)."""
    tracker = PatentTracker(session_id="t-discovered-from-persist")
    mw = PatentTrackingMiddleware(
        backend=_InMemoryBackend(),
        tracker=tracker,
    )
    request = _FakeToolCallRequest(
        "save_round_findings",
        args={
            "round_number": 1,
            "source": "patent",
            "references": [{"publication_number": "US3333333A"}],
        },
    )

    class _Result:
        content = "OK"

    mw._record_persisted(request, _Result())
    stats = tracker.generate_statistics()
    assert stats["summary"]["total_discovered"] == 1
    assert stats["summary"]["total_persisted"] == 1


def test_backfill_from_accumulator_unions_both_files():
    """When the orchestrator-accumulator is empty but the auto-accumulator
    has refs (subagent bypass case), the backfill should still pick them up."""
    empty_accum = json.dumps({"rounds": [], "all_references": [], "final_coverage": []})
    auto_accum = json.dumps({
        "version": "1.0",
        "backfilled": True,
        "all_references": [
            {"publication_number": "JP2007171504A", "source_tool": "patent_keyword_search",
             "triage_label": "A"},
            {"publication_number": "WO2021072824A1", "source_tool": "patent_keyword_search",
             "triage_label": "B"},
        ],
    })
    backend = _InMemoryBackend({
        "/findings_accumulator.json": empty_accum,
        "/findings_auto_accumulator.json": auto_accum,
    })
    tracker = PatentTracker(session_id="t-accum-union")
    mw = _make_middleware(backend, tracker)

    mw._backfill_from_accumulator(backend, tracker)

    stats = tracker.generate_statistics()
    assert stats["summary"]["total_persisted"] == 2
    assert stats["summary"]["total_discovered"] == 2


def test_parse_findings_markdown_detects_pipe_yn_columns():
    """The has_features heuristic should treat rows with 3+ standalone Y/N/Y1
    cells as feature-mapped — that's the shape of references.md rows."""
    md = (
        "| Ref | Triage | F1 | F2 | F3 |\n"
        "|---|---|---|---|---|\n"
        "| US9999999A | A | Y | N | Y1 |\n"
    )
    backend = _InMemoryBackend({"/x.md": md})
    mw = PatentTrackingMiddleware(
        backend=backend,
        tracker=PatentTracker(session_id="t-parse"),
    )
    refs = mw._parse_findings_markdown(backend, "/x.md")
    assert refs is not None
    assert refs[0]["pub_number"] == "US9999999A"
    assert refs[0]["has_features"] is True


def test_findings_backfill_scans_non_contiguous_rounds():
    """When a run writes round_2 files but skips round_1, the backfill must
    still pick up round 2 — it should NOT early-break on the first empty
    round number."""
    patent_round_2 = (
        "| Publication # | Title | Relevance |\n"
        "|---|---|---|\n"
        "| US7777777B2 | Example | A |\n"
        "| US8888888A1 | Example 2 | B |\n"
    )
    backend = _InMemoryBackend({
        "/findings/patent_round_2.md": patent_round_2,
    })
    tracker = PatentTracker(session_id="t-skip-round")
    mw = PatentTrackingMiddleware(backend=backend, tracker=tracker)

    mw._backfill_from_findings_files(backend, tracker)

    stats = tracker.generate_statistics()
    # Both round-2 patents should be discovered even though round 1 is empty.
    assert stats["summary"]["total_discovered"] == 2
    assert stats["summary"]["total_persisted"] == 2


def test_source_attribution_prefers_concrete_over_other():
    """When one DISCOVERED event carries an empty source_type and a later
    DISCOVERED event carries a concrete one (e.g. from findings backfill),
    the concrete source must win. Regression for the 'Other' bucket
    bloat seen when save_round_findings fires without a source field."""
    tracker = PatentTracker(session_id="t-source-priority")

    # Order-matters simulation: first event has no source (the way
    # save_round_findings fired in session 6388c079), second has 'semantic'
    # (the way findings-markdown backfill fires).
    tracker.record(
        "US1111111A", PatentCheckpoint.DISCOVERED, "save_round_findings",
        source_type="",
    )
    tracker.record(
        "US1111111A", PatentCheckpoint.DISCOVERED, "semantic_round_1_backfill",
        source_type="semantic",
    )

    stats = tracker.generate_statistics()
    assert stats["by_source"].get("semantic", {}).get("discovered", 0) == 1
    assert stats["by_source"].get("other", {}).get("discovered", 0) == 0


def test_reported_backfill_excludes_comments_cell_mentions():
    """Publications mentioned inside a matrix row's Comments/X-category
    cell (but without their own row) must NOT inflate REPORTED. Regression
    for the +7 'negative loss' feature_mapped→reported anomaly."""
    # Two real rows; US9999999A is mentioned only in the Comments cell of
    # the first row — not a row of its own.
    final_report = (
        "## 4. Feature Matrix (Core Analytical Deliverable)\n"
        "\n"
        "| Pub | Type | Desc | Relevance | Priority | Juris | F1 | F2 | F3 "
        "| Comments | X-category |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| US1000001A | Patent | First | A | 2020 | US | Y | N | Y1 "
        "| cites US9999999A | N |\n"
        "| US1000002A | Patent | Second | B | 2019 | US | Y | Y | N "
        "| no related refs | N |\n"
        "\n"
        "## 5. Peripherally Related\n"
    )
    backend = _InMemoryBackend({"/final_report.md": final_report})
    tracker = PatentTracker(session_id="t-reported-rows-only")
    mw = PatentTrackingMiddleware(backend=backend, tracker=tracker)

    mw._backfill_reported(backend, tracker)

    stats = tracker.generate_statistics()
    # Only the two row-headed refs, not the Comments-mentioned US9999999A.
    assert stats["summary"]["total_reported"] == 2


def test_round_telemetry_fires_on_subagent_findings_write():
    """Subagents write findings markdown via write_file, bypassing
    save_round_findings. The round-telemetry hook must still detect
    round 2 from the file path pattern so telemetry.rounds isn't
    stuck at 1."""
    from unittest.mock import MagicMock
    from src.novelty_checker.observability.telemetry import (
        ResearchTelemetry,
        TelemetryMiddleware,
    )

    telemetry = ResearchTelemetry(session_id="t-round-writefile")
    mw = TelemetryMiddleware(telemetry=telemetry)

    # Simulate a write_file to /findings/patent_round_2.md
    request = MagicMock()
    request.tool_call = {
        "name": "write_file",
        "args": {"file_path": "/findings/patent_round_2.md"},
    }
    request.runtime = None

    class _Result:
        content = "File written."

    mw._maybe_record_round("write_file", request, _Result())

    assert 2 in telemetry.rounds
    assert telemetry.rounds[2].round_number == 2


def test_triage_only_references_still_feature_maps_from_report():
    """When ``/references.md`` is a triage-only table (no F columns) but
    ``/final_report.md`` carries the real Feature Matrix, FEATURE_MAPPED
    must still populate. Regression for the bug seen in session ad46c91b."""
    references_md = (  # Triage-only shape — columns differ from a full matrix.
        "| Ref ID | Type | Title | Triage | Priority/Year | Notes |\n"
        "|---|---|---|---|---|---|\n"
        "| US7377195B2 | Patent | Power take-off | A | 1999 | notes |\n"
        "| US4615230A | Patent | Two worms | A | 1983 | notes |\n"
        "| US12591165B2 | Patent | Camera module | A | 2019 | notes |\n"
    )
    final_report = (
        "## 4. Feature Matrix (Core Analytical Deliverable)\n"
        "\n"
        "| Publication Number | Ref Type | Short Description | Relevance "
        "| Earliest Priority | Jurisdiction | F1 | F2 | F3 | F4 | F5 | F6 | "
        "Comments |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| US7377195B2 | Patent | Power take-off | A | 1999-10-15 | US "
        "| Y | Y1 | Y1 | N | N | Y | notes |\n"
        "| US4615230A | Patent | Two worms | A | 1983-05-16 | US "
        "| Y | Y | Y1 | N | N | N | notes |\n"
        "| US12591165B2 | Patent | Camera module | A | 2019-08-05 | US "
        "| N | N | Y | Y | Y | Y1 | notes |\n"
        "\n"
        "## 5. Peripherally Related\n"
    )
    backend = _InMemoryBackend({
        "/references.md": references_md,
        "/final_report.md": final_report,
    })
    tracker = PatentTracker(session_id="t-triage-only-plus-report")
    mw = PatentTrackingMiddleware(backend=backend, tracker=tracker)

    mw._backfill_feature_mapped_from_references(backend, tracker)

    stats = tracker.generate_statistics()
    # All three refs must feature-map (signal comes from final_report matrix)…
    assert stats["summary"]["total_feature_mapped"] == 3
    # …and retain their triage labels from references.md.
    assert stats["summary"]["total_triaged"] == 3
    assert stats["by_triage_level"].get("A", {}).get("count", 0) == 3


def test_feature_mapped_backfill_falls_back_to_final_report():
    """When there's no /references.md, the feature-matrix backfill must fall
    back to scanning the Feature Matrix section of /final_report.md — that's
    the shape of runs where build_feature_matrix output goes straight into
    the report without an intermediate file."""
    final_report = (
        "## 3. Feature Plan\n"
        "some preamble\n"
        "\n"
        "## 4. Feature Matrix (Core Analytical Deliverable)\n"
        "\n"
        "| Publication Number | Ref Type | Short Description | Relevance "
        "| Earliest Priority | Jurisdiction | F1 | F2 | F3 | F4 | F5 | F6 | "
        "Comments |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| US6118553A | Patent | Scanner drive | A | 1998-01-28 | US "
        "| Y | Y | Y | N | N | Y1 | notes |\n"
        "| US12044551B2 | Patent | Absolute encoder | A | 2020-03-31 | US "
        "| Y | Y | Y | N | N | Y1 | more notes |\n"
        "\n"
        "## 5. Peripherally Related\n"
        "Nothing here.\n"
    )
    backend = _InMemoryBackend({"/final_report.md": final_report})
    tracker = PatentTracker(session_id="t-report-fallback")
    mw = PatentTrackingMiddleware(backend=backend, tracker=tracker)

    mw._backfill_feature_mapped_from_references(backend, tracker)

    stats = tracker.generate_statistics()
    assert stats["summary"]["total_feature_mapped"] == 2
    assert stats["summary"]["total_triaged"] == 2
    # Source should be attributed as patent, not "other"
    assert stats["by_source"].get("patent", {}).get("feature_mapped", 0) == 2
    assert stats["by_source"].get("other", {}).get("feature_mapped", 0) == 0
