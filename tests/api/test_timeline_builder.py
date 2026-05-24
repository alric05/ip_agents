"""ResearchTimelineBuilder behavior tests."""

from __future__ import annotations

from src.novelty_checker.api.research_timeline import ResearchTimelineBuilder


def _statuses(snapshot: dict) -> dict[str, str]:
    return {s["id"]: s["status"] for s in snapshot["steps"]}


class TestInitialSnapshot:
    def test_all_steps_not_started(self):
        b = ResearchTimelineBuilder()
        snap = b.initial_snapshot()
        assert snap["component"] == "researchTimelineBubble"
        assert snap["completion"] is None
        assert all(v == "not_started" for v in _statuses(snap).values())

    def test_initial_primes_dedupe(self):
        """The first node-start that wouldn't change state must dedupe to None."""
        b = ResearchTimelineBuilder()
        b.initial_snapshot()
        # No state change since no node has started yet — but if we manually
        # mark a step in_progress and then trigger a no-op start, the second
        # call should dedupe.
        first = b.on_node_start("agent")
        assert first is not None
        assert _statuses(first)["plan"] == "in_progress"
        second = b.on_node_start("agent")
        assert second is None


class TestNodeAndToolTransitions:
    def test_node_start_marks_in_progress(self):
        b = ResearchTimelineBuilder()
        snap = b.on_node_start("patent-researcher")
        assert _statuses(snap)["patent-search"] == "in_progress"

    def test_unknown_node_returns_none(self):
        b = ResearchTimelineBuilder()
        assert b.on_node_start("unknown-node") is None

    def test_unknown_tool_from_unknown_node_returns_none(self):
        b = ResearchTimelineBuilder()
        assert b.on_tool_start("unknown-node", "weird_tool") is None

    def test_unknown_tool_from_known_node_falls_back_to_node_step(self):
        """Unmapped tool fired by a known node still advances that node's step.

        The server filters INTERNAL_TOOLS before calling the builder, so this
        fallback only matters for legitimate-but-unmapped tools.
        """
        b = ResearchTimelineBuilder()
        snap = b.on_tool_start("patent-researcher", "some_new_tool")
        assert _statuses(snap)["patent-search"] == "in_progress"

    def test_tool_start_then_end(self):
        b = ResearchTimelineBuilder()
        s1 = b.on_tool_start("npl-researcher", "npl_search")
        assert _statuses(s1)["npl-search"] == "in_progress"
        s2 = b.on_tool_end("npl-researcher", "npl_search")
        assert _statuses(s2)["npl-search"] == "completed"

    def test_dedupe_no_change_returns_none(self):
        b = ResearchTimelineBuilder()
        b.on_tool_start("npl-researcher", "npl_search")
        # Same tool starting again while already in_progress — no state change
        assert b.on_tool_start("npl-researcher", "npl_search") is None

    def test_completed_then_started_again(self):
        b = ResearchTimelineBuilder()
        b.on_tool_end("citation-researcher", "batch_citation_search")
        # Now status is completed; re-starting bumps back to in_progress
        snap = b.on_tool_start("citation-researcher", "batch_citation_search")
        assert _statuses(snap)["citation-search"] == "in_progress"


class TestFinalize:
    def test_finalize_promotes_pending_steps(self):
        b = ResearchTimelineBuilder()
        b.on_tool_start("patent-researcher", "patent_keyword_search")
        snap = b.finalize(backend=None, ai_text="A summary.")
        assert all(v == "completed" for v in _statuses(snap).values())
        assert snap["completion"]["title"] == "Research Complete"
        assert any(
            sec.get("title") == "Summary"
            for sec in snap["completion"]["sections"]
        )

    def test_finalize_with_backend_includes_report(self):
        class FakeBackend:
            def read(self, path: str):
                if path == "/final_report.md":
                    return "# Report\nBody"
                if path == "/findings_accumulator.json":
                    return '{"final_coverage_pct": 80.5, "all_references": [1,2,3]}'
                return "Error: not found"

        b = ResearchTimelineBuilder()
        snap = b.finalize(backend=FakeBackend(), ai_text="ignored")
        sections = snap["completion"]["sections"]
        titles = [s.get("title") for s in sections]
        assert "Coverage summary" in titles
        assert "Final report" in titles
        report_section = next(s for s in sections if s["title"] == "Final report")
        assert "Body" in report_section["body"]


class TestEndToEndSequence:
    def test_full_research_flow(self):
        """Drive a synthetic event sequence covering multiple steps."""
        b = ResearchTimelineBuilder()
        b.initial_snapshot()

        events = [
            ("node", "agent"),
            ("tool_start", "agent", "generate_search_strategy"),
            ("tool_end", "agent", "generate_search_strategy"),
            ("node", "patent-researcher"),
            ("tool_start", "patent-researcher", "batch_patent_search"),
            ("tool_end", "patent-researcher", "batch_patent_search"),
            ("node", "coverage-analyst"),
            ("tool_end", "coverage-analyst", "evaluate_coverage"),
            ("node", "report-writer"),
            ("tool_end", "report-writer", "summarize_findings_for_report"),
        ]

        snapshots: list[dict] = []
        for ev in events:
            if ev[0] == "node":
                s = b.on_node_start(ev[1])
            elif ev[0] == "tool_start":
                s = b.on_tool_start(ev[1], ev[2])
            else:
                s = b.on_tool_end(ev[1], ev[2])
            if s is not None:
                snapshots.append(s)

        # Each transition should produce a snapshot.
        assert len(snapshots) >= 5

        final = b.finalize(backend=None, ai_text="Done.")
        assert _statuses(final) == {
            "plan": "completed",
            "patent-search": "completed",
            "npl-search": "completed",
            "semantic-search": "completed",
            "citation-search": "completed",
            "coverage-eval": "completed",
            "report-write": "completed",
        }
