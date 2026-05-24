"""Middleware that passively tracks patents through the pipeline.

Intercepts tool calls to record lifecycle checkpoint events for every patent
flowing through the system.  At session end, cross-references all checkpoints,
computes a loss funnel, and writes ``/patent_statistics.json`` and
``/patent_statistics.md`` to the session workspace.

This is a **passive observer** — it never modifies tool results or model
requests.  It follows the same dual-mode pattern as ``TelemetryMiddleware``:

- **Static mode** (CLI): provide a single ``PatentTracker`` instance.
- **Factory mode** (LangGraph Studio): provide a ``tracker_factory`` callable
  that creates per-thread ``PatentTracker`` instances.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

from src.novelty_checker.middleware.findings import (
    SEARCH_TOOLS_TO_CAPTURE,
    _determine_source_type,
    _extract_references_from_result,
)
from src.novelty_checker.observability.patent_tracker import (
    PatentCheckpoint,
    PatentTracker,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langgraph.prebuilt.tool_node import ToolCallRequest
    from langgraph.types import Command

    from deepagents.backends.protocol import BACKEND_TYPES, BackendProtocol

_logger = logging.getLogger(__name__)

# Tools that trigger the PERSISTED checkpoint
_PERSIST_TOOLS = {"save_round_findings"}

# Tools that trigger the TRIAGED checkpoint
_TRIAGE_TOOLS = {"triage_reference"}

# Tools that trigger the FEATURE_MAPPED checkpoint
_FEATURE_MAP_TOOLS = {"map_features_to_reference"}

# Tools that signal report finalization is imminent.
# Intentionally empty: finalize only when `final_report.md` is written, so the
# backfill sees the report, references.md, and feature matrix in final form.
_FINALIZE_SIGNAL_TOOLS: set[str] = set()

# File paths used during backfill
_FINDINGS_DIR = "/findings"
_AUTO_ACCUMULATOR_PATH = "/findings_auto_accumulator.json"
_FINDINGS_ACCUMULATOR_PATH = "/findings_accumulator.json"
_FINAL_REPORT_PATH = "/final_report.md"
_REFERENCES_MD_PATH = "/references.md"
_STATS_JSON_PATH = "/patent_statistics.json"
_STATS_MD_PATH = "/patent_statistics.md"


class PatentTrackingMiddleware(AgentMiddleware):
    """Passive middleware that tracks patent lifecycle checkpoints.

    Intercepts ``wrap_tool_call`` to record:

    - **DISCOVERED** — search tool returns references
    - **PERSISTED** — ``save_round_findings`` called successfully
    - **TRIAGED** — ``triage_reference`` assigns A/B/C label
    - **FEATURE_MAPPED** — ``map_features_to_reference`` called
    - **REPORTED** — backfilled at session end from the final report

    At session end (triggered when ``summarize_findings_for_report`` or
    ``write_file`` for ``/final_report.md`` is detected), ``finalize_session``
    runs a backfill pass and writes statistics files.

    Args:
        backend: Backend instance or factory for reading accumulator files.
        tracker: Static ``PatentTracker`` instance (CLI mode).
        tracker_factory: Callable ``(thread_id) -> PatentTracker`` (Studio mode).
    """

    def __init__(
        self,
        *,
        backend: BACKEND_TYPES,
        tracker: PatentTracker | None = None,
        tracker_factory: Callable[[str], PatentTracker] | None = None,
    ) -> None:
        if tracker is None and tracker_factory is None:
            raise ValueError("Provide either tracker or tracker_factory")
        self._backend = backend
        self._static_tracker = tracker
        self._tracker_factory = tracker_factory
        self._thread_trackers: dict[str, PatentTracker] = {}
        self._finalized: set[str] = set()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Resolver helpers
    # ------------------------------------------------------------------

    def _get_backend(self, runtime: Any) -> BackendProtocol:
        if callable(self._backend):
            return self._backend(runtime)
        return self._backend

    def _get_tracker(self, runtime: Any) -> PatentTracker:
        if self._static_tracker is not None:
            return self._static_tracker

        from src.novelty_checker.backend_factory import extract_thread_id

        thread_id = extract_thread_id(runtime) or "__default__"
        with self._lock:
            if thread_id not in self._thread_trackers:
                if self._tracker_factory:
                    self._thread_trackers[thread_id] = self._tracker_factory(
                        thread_id
                    )
                else:
                    self._thread_trackers[thread_id] = PatentTracker(
                        session_id=thread_id
                    )
            return self._thread_trackers[thread_id]

    # ------------------------------------------------------------------
    # Middleware hooks
    # ------------------------------------------------------------------

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        result = handler(request)
        self._process(request, result)
        return result

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        result = await handler(request)
        await asyncio.to_thread(self._process, request, result)
        return result

    # ------------------------------------------------------------------
    # Checkpoint dispatch
    # ------------------------------------------------------------------

    def _process(
        self,
        request: ToolCallRequest,
        result: ToolMessage | Command[Any],
    ) -> None:
        """Route a completed tool call to the appropriate checkpoint recorder."""
        tool_name = request.tool_call.get("name", "")
        try:
            if tool_name in SEARCH_TOOLS_TO_CAPTURE:
                self._record_discovered(tool_name, result, request)

            elif tool_name in _PERSIST_TOOLS:
                self._record_persisted(request, result)

            elif tool_name in _TRIAGE_TOOLS:
                self._record_triaged(request, result)

            elif tool_name in _FEATURE_MAP_TOOLS:
                self._record_feature_mapped(request)

            elif tool_name in _FINALIZE_SIGNAL_TOOLS:
                self._schedule_finalize(request)

            # Detect write_file to /final_report.md as alternative finalize trigger
            elif tool_name in ("write_file", "edit_file"):
                args = request.tool_call.get("args", {})
                # deepagents uses "file_path" as the arg name
                path = args.get("file_path", "") or args.get("path", "")
                if "final_report" in path.lower():
                    self._schedule_finalize(request)

        except Exception as e:  # noqa: BLE001
            _logger.debug(f"PatentTracking: error processing {tool_name}: {e}")

    # ------------------------------------------------------------------
    # Checkpoint recorders
    # ------------------------------------------------------------------

    def _record_discovered(
        self,
        tool_name: str,
        result: ToolMessage | Command[Any],
        request: ToolCallRequest,
    ) -> None:
        """DISCOVERED: extract refs from search tool result."""
        content = result.content if isinstance(result, ToolMessage) else str(result)
        references = _extract_references_from_result(tool_name, content)
        if not references:
            return

        tracker = self._get_tracker(request.runtime)
        source_type = _determine_source_type(tool_name)

        # Track total evaluated (ALL refs, even without pub_number)
        tracker.record_evaluated(len(references), source_type)

        for ref in references:
            pub = ref.get("publication_number", "")
            if pub:
                tracker.record(
                    pub,
                    PatentCheckpoint.DISCOVERED,
                    tool_name,
                    source_type=source_type,
                    title=ref.get("title", ""),
                )

    def _record_persisted(
        self,
        request: ToolCallRequest,
        result: ToolMessage | Command[Any],
    ) -> None:
        """PERSISTED: parse references from save_round_findings args."""
        content = result.content if isinstance(result, ToolMessage) else str(result)
        # Only record if the tool succeeded
        if not content or content.startswith("\u274c"):
            return

        args = request.tool_call.get("args", {})
        references = args.get("references", [])
        round_number = args.get("round_number")
        call_source = args.get("source", "") or args.get("source_type", "")
        tracker = self._get_tracker(request.runtime)

        for ref in references:
            pub = ""
            ref_source = ""
            if isinstance(ref, dict):
                pub = ref.get("publication_number", "") or ref.get("ref_id", "")
                ref_source = (
                    ref.get("source_tool", "")
                    or ref.get("source", "")
                    or ref.get("source_type", "")
                )
            if not pub:
                continue

            source_type = _determine_source_type(ref_source or call_source)

            # Ensure every persisted ref is also marked DISCOVERED — subagents
            # that bypass search_tool wrapping don't emit a discovery event.
            tracker.record(
                pub,
                PatentCheckpoint.DISCOVERED,
                "save_round_findings",
                source_type=source_type,
                round_number=round_number,
                title=ref.get("title", "") if isinstance(ref, dict) else "",
            )
            tracker.record(
                pub,
                PatentCheckpoint.PERSISTED,
                "save_round_findings",
                source_type=source_type,
                round_number=round_number,
            )

    def _record_triaged(
        self,
        request: ToolCallRequest,
        result: ToolMessage | Command[Any],
    ) -> None:
        """TRIAGED: extract ref_id and label from triage_reference."""
        args = request.tool_call.get("args", {})
        ref_id = args.get("ref_id", "") or args.get("publication_number", "")
        if not ref_id:
            return

        # Parse label from result text
        content = result.content if isinstance(result, ToolMessage) else str(result)
        label = self._extract_triage_label(content)

        tracker = self._get_tracker(request.runtime)
        tracker.record(
            ref_id,
            PatentCheckpoint.TRIAGED,
            "triage_reference",
            triage_label=label,
        )

    def _record_feature_mapped(self, request: ToolCallRequest) -> None:
        """FEATURE_MAPPED: extract ref_id from map_features_to_reference."""
        args = request.tool_call.get("args", {})
        ref_id = args.get("ref_id", "") or args.get("publication_number", "")
        if not ref_id:
            return

        tracker = self._get_tracker(request.runtime)
        tracker.record(
            ref_id,
            PatentCheckpoint.FEATURE_MAPPED,
            "map_features_to_reference",
        )

    # ------------------------------------------------------------------
    # Session finalization
    # ------------------------------------------------------------------

    def _schedule_finalize(self, request: ToolCallRequest) -> None:
        """Run finalize_session if not already done for this thread."""
        from src.novelty_checker.backend_factory import extract_thread_id

        thread_id = extract_thread_id(request.runtime) or "__default__"
        if thread_id in self._finalized:
            return
        self._finalized.add(thread_id)

        try:
            self.finalize_session(request.runtime)
        except Exception as e:  # noqa: BLE001
            _logger.warning(f"PatentTracking: finalize_session failed: {e}")

    def finalize_session(self, runtime: Any) -> None:
        """Backfill checkpoints from filesystem and write statistics.

        Because search tools and ``save_round_findings`` are called by
        **subagents** (not the orchestrator), real-time ``wrap_tool_call``
        capture cannot observe them.  This method reconstructs the full
        funnel from filesystem artifacts written by the subagents.
        """
        tracker = self._get_tracker(runtime)
        backend = self._get_backend(runtime)

        # PRIMARY: parse findings markdown files (written directly by subagents)
        self._backfill_from_findings_files(backend, tracker)
        # SECONDARY: accumulator (if save_round_findings populated it)
        self._backfill_from_accumulator(backend, tracker)
        # Also try the auto-accumulator (written by FindingsPersistenceMiddleware)
        self._backfill_persisted(backend, tracker)
        # FEATURE_MAPPED is emitted by references.md, not by a per-ref tool call
        self._backfill_feature_mapped_from_references(backend, tracker)
        self._backfill_reported(backend, tracker)

        # Write statistics files
        stats_json = tracker.generate_statistics()
        stats_md = tracker.generate_statistics_markdown()

        try:
            backend.write(_STATS_JSON_PATH, json.dumps(stats_json, indent=2))
            backend.write(_STATS_MD_PATH, stats_md)
            _logger.info("Patent statistics written to session workspace")
        except Exception as e:  # noqa: BLE001
            _logger.warning(f"PatentTracking: failed to write stats: {e}")

    # ------------------------------------------------------------------
    # Backfill helpers
    # ------------------------------------------------------------------

    def _backfill_from_findings_files(
        self, backend: BackendProtocol, tracker: PatentTracker
    ) -> None:
        """Backfill all checkpoints from findings markdown files.

        Subagents write findings markdown directly via ``write_file``,
        bypassing ``save_round_findings``.  This parses the markdown
        tables to reconstruct DISCOVERED/PERSISTED/TRIAGED/FEATURE_MAPPED.
        """
        _SOURCES = ("patent", "semantic", "npl")
        _MAX_ROUNDS = 10

        source_eval_counts: dict[str, int] = {}

        # Scan every possible round — don't early-break on the first empty one.
        # A single run may skip round 1 (e.g., start from round 2 on resume,
        # or split work across non-contiguous round numbers).
        for round_num in range(1, _MAX_ROUNDS + 1):
            for source in _SOURCES:
                path = f"{_FINDINGS_DIR}/{source}_round_{round_num}.md"
                refs = self._parse_findings_markdown(backend, path)
                if refs is None:
                    continue
                source_eval_counts[source] = (
                    source_eval_counts.get(source, 0) + len(refs)
                )
                self._record_findings_refs(tracker, refs, source, round_num)

            # Citation files use different naming
            path = f"{_FINDINGS_DIR}/citations_round_{round_num}.md"
            refs = self._parse_findings_markdown(backend, path)
            if refs is not None:
                source_eval_counts["citation"] = (
                    source_eval_counts.get("citation", 0) + len(refs)
                )
                self._record_findings_refs(tracker, refs, "citation", round_num)

        # Record total evaluated per source (lower bound — only includes
        # refs that survived into findings files, not all search results)
        for source, count in source_eval_counts.items():
            tracker.record_evaluated(count, source)

        _logger.info(
            "Backfilled from findings files: %s",
            {k: v for k, v in source_eval_counts.items()},
        )

    def _record_findings_refs(
        self,
        tracker: PatentTracker,
        refs: list[dict[str, Any]],
        source: str,
        round_num: int,
    ) -> None:
        """Record DISCOVERED/PERSISTED/TRIAGED/FEATURE_MAPPED for parsed refs."""
        tool_label = f"{source}_round_{round_num}"
        for ref in refs:
            pub = ref["pub_number"]

            tracker.record(
                pub,
                PatentCheckpoint.DISCOVERED,
                tool_label,
                source_type=source,
                round_number=round_num,
            )
            tracker.record(
                pub,
                PatentCheckpoint.PERSISTED,
                tool_label,
                source_type=source,
                round_number=round_num,
            )

            label = ref.get("triage_label")
            if label:
                tracker.record(
                    pub,
                    PatentCheckpoint.TRIAGED,
                    tool_label,
                    triage_label=label,
                )

            if ref.get("has_features"):
                tracker.record(
                    pub,
                    PatentCheckpoint.FEATURE_MAPPED,
                    tool_label,
                )

    def _parse_findings_markdown(
        self, backend: BackendProtocol, path: str
    ) -> list[dict[str, Any]] | None:
        """Parse a findings markdown file and extract ref data from table rows.

        Returns a list of dicts with keys ``pub_number``, ``triage_label``,
        ``has_features``.  Returns ``None`` if the file can't be read.
        """
        try:
            content = backend.read(path)
            # FilesystemBackend.read() returns error string for missing files
            if not content or content.startswith("Error:"):
                return None
        except Exception:
            return None

        refs: list[dict[str, Any]] = []
        for line in content.split("\n"):
            if "|" not in line:
                continue

            cells = [c.strip() for c in line.split("|")]
            cells = [c for c in cells if c]

            # Skip separator rows (all dashes/colons)
            if not cells or all(set(c) <= set("-: ") for c in cells):
                continue

            # Extract pub number from the first 2 cells
            pub = None
            for cell in cells[:2]:
                pubs = self._extract_pub_numbers_from_text(cell)
                if pubs:
                    pub = pubs[0]
                    break

            if not pub:
                continue

            # Triage label: standalone A/B/C in a cell (strip markdown bold **…**)
            label = None
            for cell in cells:
                stripped = cell.strip("*").strip()
                if stripped in ("A", "B", "C"):
                    label = stripped
                    break

            # Feature mapping heuristic: either
            #   - "F1: Y" / "F2 Y" style inline annotations, or
            #   - "Y / N" slash patterns, or
            #   - 3+ standalone Y/N/Y1/N1 cells in the table row (references.md layout)
            yn_cell_count = sum(
                1 for c in cells if re.fullmatch(r"[YN]\d?", c.strip("* ").upper())
            )
            has_features = bool(
                re.search(r"F[1-9]\s*[:\s;]\s*[YN]", line, re.IGNORECASE)
                or re.search(r"[YN]\d?\s*/\s*[YN]", line)
                or yn_cell_count >= 3
            )

            refs.append({
                "pub_number": pub,
                "triage_label": label,
                "has_features": has_features,
            })

        return refs if refs else None

    def _backfill_from_accumulator(
        self, backend: BackendProtocol, tracker: PatentTracker
    ) -> None:
        """Secondary backfill from the accumulator JSON file(s).

        Unions refs across ``/findings_accumulator.json`` (written by
        ``save_round_findings``) and ``/findings_auto_accumulator.json``
        (written by ``FindingsPersistenceMiddleware`` from markdown).
        Either file alone can be empty depending on whether the
        orchestrator called ``save_round_findings`` with a full payload
        or whether subagents bypassed it — reading both covers the gap.
        """
        refs: list[dict[str, Any]] = []
        seen_pubs: set[str] = set()
        for path in (_FINDINGS_ACCUMULATOR_PATH, _AUTO_ACCUMULATOR_PATH):
            try:
                content = backend.read(path)
                data = json.loads(content)
            except Exception:
                continue
            for ref in data.get("all_references", []):
                pub = ref.get("publication_number", "") or ref.get("ref_id", "")
                if not pub or pub in seen_pubs:
                    continue
                seen_pubs.add(pub)
                refs.append(ref)

        if not refs:
            return

        # Record total_evaluated (all refs in accumulator)
        source_counts: dict[str, int] = {}
        for ref in refs:
            src = _determine_source_type(
                ref.get("source_tool", "") or ref.get("source", "")
            )
            source_counts[src] = source_counts.get(src, 0) + 1
        for src, count in source_counts.items():
            tracker.record_evaluated(count, src)

        for ref in refs:
            pub = (
                ref.get("publication_number", "")
                or ref.get("ref_id", "")
            )
            if not pub:
                continue

            title = ref.get("title", "")
            source_type = _determine_source_type(
                ref.get("source_tool", "") or ref.get("source", "")
            )

            # DISCOVERED — every ref with a pub number was discovered
            tracker.record(
                pub,
                PatentCheckpoint.DISCOVERED,
                "accumulator_backfill",
                source_type=source_type,
                title=title,
            )

            # PERSISTED — present in accumulator means it was saved
            tracker.record(
                pub,
                PatentCheckpoint.PERSISTED,
                "accumulator_backfill",
                source_type=source_type,
            )

            # TRIAGED — check multiple possible field names
            label = (
                ref.get("triage_label")
                or ref.get("triage")
                or ref.get("relevance")
            )
            if label:
                tracker.record(
                    pub,
                    PatentCheckpoint.TRIAGED,
                    "accumulator_backfill",
                    triage_label=str(label),
                )

            # FEATURE_MAPPED — check multiple possible field names
            coverage = (
                ref.get("feature_coverage")
                or ref.get("feature_mapping")
                or ref.get("features")
            )
            if coverage:
                tracker.record(
                    pub,
                    PatentCheckpoint.FEATURE_MAPPED,
                    "accumulator_backfill",
                )

    def _backfill_persisted(
        self, backend: BackendProtocol, tracker: PatentTracker
    ) -> None:
        """Mark patents in the auto-accumulator as PERSISTED (fallback)."""
        # `read_json_from_backend` handles FilesystemBackend's line-number
        # prefixes + "Error: ..." strings for missing files. The naive
        # `json.loads(content)` always failed and silently returned early.
        from src.novelty_checker.middleware._backend_utils import read_json_from_backend
        data = read_json_from_backend(backend, _AUTO_ACCUMULATOR_PATH)
        if data is None:
            return

        for ref in data.get("all_references", []):
            pub = ref.get("publication_number", "")
            if pub:
                tracker.record(
                    pub,
                    PatentCheckpoint.PERSISTED,
                    "auto_accumulator_backfill",
                    source_type=ref.get("source_tool", ""),
                )

    def _backfill_feature_mapped_from_references(
        self, backend: BackendProtocol, tracker: PatentTracker
    ) -> None:
        """Backfill checkpoints from the feature-coverage artefacts.

        Two files may carry the signal, and a single run can produce
        either, both, or neither in varying shapes:

        1. ``/references.md`` — sometimes a full F1..Fn matrix, sometimes
           a triage-only table (``| Ref | Type | Title | Triage | ... |``
           with no feature columns).
        2. The Feature Matrix section of ``/final_report.md`` — canonical
           source of feature coverage when ``build_feature_matrix`` output
           is spliced directly into the report.

        We union both sources keyed by publication number:

        - `final_report.md`'s Feature Matrix is the authoritative source
          for FEATURE_MAPPED (it always has Y/N/Y1 cells when present).
        - `references.md` contributes TRIAGED labels that may be absent
          from the matrix.
        - `tracker.record()` is idempotent by ``(pub, checkpoint)``, so
          recording the same checkpoint from both sources is safe.
        """
        rows_by_pub: dict[str, dict[str, Any]] = {}

        # Source 1: references.md (may be triage-only or full matrix).
        refs_from_file = self._parse_findings_markdown(backend, _REFERENCES_MD_PATH)
        for ref in refs_from_file or []:
            rows_by_pub[ref["pub_number"]] = dict(ref)

        # Source 2: Feature Matrix section of final_report.md (authoritative
        # for has_features). Merge into any existing entry so triage labels
        # from references.md are preserved.
        try:
            report = backend.read(_FINAL_REPORT_PATH)
        except Exception:
            report = ""
        if report and not report.startswith("Error:"):
            try:
                from src.novelty_checker.utils.feature_matrix import (
                    extract_feature_matrix_from_markdown,
                )
                matrix_section = extract_feature_matrix_from_markdown(report)
            except ImportError:
                matrix_section = None
            if matrix_section:
                for ref in self._parse_table_rows(matrix_section):
                    pub = ref["pub_number"]
                    merged = rows_by_pub.get(pub, {})
                    merged["pub_number"] = pub
                    # Matrix wins for has_features; references.md wins for
                    # triage_label if the matrix row didn't carry one.
                    merged["has_features"] = (
                        ref.get("has_features") or merged.get("has_features", False)
                    )
                    merged["triage_label"] = (
                        merged.get("triage_label") or ref.get("triage_label")
                    )
                    merged["title"] = merged.get("title") or ref.get("title", "")
                    rows_by_pub[pub] = merged

        if not rows_by_pub:
            return

        for pub, ref in rows_by_pub.items():
            tracker.record(
                pub,
                PatentCheckpoint.DISCOVERED,
                "feature_matrix_backfill",
                source_type="patent",
                title=ref.get("title", ""),
            )
            tracker.record(
                pub,
                PatentCheckpoint.PERSISTED,
                "feature_matrix_backfill",
                source_type="patent",
            )
            if ref.get("triage_label"):
                tracker.record(
                    pub,
                    PatentCheckpoint.TRIAGED,
                    "feature_matrix_backfill",
                    triage_label=ref["triage_label"],
                )
            if ref.get("has_features"):
                tracker.record(
                    pub,
                    PatentCheckpoint.FEATURE_MAPPED,
                    "feature_matrix_backfill",
                )

    def _parse_table_rows(self, content: str) -> list[dict[str, Any]]:
        """Parse a markdown table blob into row dicts matching _parse_findings_markdown.

        Shared helper so the feature-matrix fallback can reuse the same row
        extraction logic as the file-level parser (pub number + triage label +
        Y/N feature cell detection).
        """
        refs: list[dict[str, Any]] = []
        for line in content.split("\n"):
            if "|" not in line:
                continue
            cells = [c.strip() for c in line.split("|")]
            cells = [c for c in cells if c]
            if not cells or all(set(c) <= set("-: ") for c in cells):
                continue

            pub = None
            for cell in cells[:2]:
                pubs = self._extract_pub_numbers_from_text(cell)
                if pubs:
                    pub = pubs[0]
                    break
            if not pub:
                continue

            label = None
            for cell in cells:
                stripped = cell.strip("*").strip()
                if stripped in ("A", "B", "C"):
                    label = stripped
                    break

            yn_cell_count = sum(
                1 for c in cells if re.fullmatch(r"[YN]\d?", c.strip("* ").upper())
            )
            has_features = bool(
                re.search(r"F[1-9]\s*[:\s;]\s*[YN]", line, re.IGNORECASE)
                or re.search(r"[YN]\d?\s*/\s*[YN]", line)
                or yn_cell_count >= 3
            )
            refs.append({
                "pub_number": pub,
                "triage_label": label,
                "has_features": has_features,
            })
        return refs

    def _backfill_reported(
        self, backend: BackendProtocol, tracker: PatentTracker
    ) -> None:
        """Scan final report's Feature Matrix for REPORTED patents."""
        try:
            report = backend.read(_FINAL_REPORT_PATH)
        except Exception:
            return

        if not report:
            return

        # Use the utility to extract the Feature Matrix section
        try:
            from src.novelty_checker.utils.feature_matrix import (
                extract_feature_matrix_from_markdown,
            )

            matrix_section = extract_feature_matrix_from_markdown(report)
        except ImportError:
            matrix_section = None

        # Prefer row-structured extraction over regex-on-text: the regex
        # would also match pubs that appear in Comments/X-category cells
        # or inline prose, inflating REPORTED beyond refs that actually
        # have their own matrix row. Fall back to the regex only when the
        # section can't be isolated (prose report, unexpected layout).
        if matrix_section:
            pub_numbers = [r["pub_number"] for r in self._parse_table_rows(matrix_section)]
        else:
            pub_numbers = self._extract_pub_numbers_from_text(report)

        for pub in pub_numbers:
            tracker.record(
                pub,
                PatentCheckpoint.REPORTED,
                "final_report_backfill",
            )

    @staticmethod
    def _extract_pub_numbers_from_text(text: str) -> list[str]:
        """Extract patent/NPL publication numbers from markdown text.

        Matches patterns like US10234567B2, EP1234567A1, CN112345678A,
        JP2007171504A, JPH10213845A, TWI836372B, WOS:000299510600010, DOIs.
        """
        patterns = [
            # Standard 2-letter country code patents
            r"\b(?:US|EP|CN|KR|WO|DE|FR|GB|AU|CA|NL|SE|CH|AT|IT)\d{6,}[A-Z]?\d*\b",
            # Japanese patents with era prefixes (JPH, JPS, JPB) or plain JP
            r"\bJP[HSBA]?\d{6,}[A-Z]?\d*\b",
            # Taiwan patents (TWI, TWM) or plain TW
            r"\bTW[IM]?\d{5,}[A-Z]?\d*\b",
            # Web of Science (numeric or alphanumeric IDs)
            r"\bWOS:[A-Z0-9]{10,}\b",
            # DOIs
            r"\b10\.\d{4,}/[^\s|]+",
        ]
        found: list[str] = []
        for pattern in patterns:
            found.extend(re.findall(pattern, text, re.IGNORECASE))
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for pub in found:
            normalised = pub.upper().strip()
            if normalised not in seen:
                seen.add(normalised)
                unique.append(normalised)
        return unique

    @staticmethod
    def _extract_triage_label(text: str) -> str:
        """Extract A/B/C triage label from triage_reference result text."""
        # Look for patterns like "**Label**: A", "Relevance: B", "Triage: C"
        # The keyword may be wrapped in markdown bold (**...**)
        match = re.search(
            r"\*{0,2}(?:label|relevance|triage(?:\s+label)?)\*{0,2}"
            r"[:\s]+\*{0,2}\s*([ABC])\b",
            text,
            re.IGNORECASE,
        )
        return match.group(1).upper() if match else "unknown"


# =============================================================================
# Exports
# =============================================================================

__all__ = ["PatentTrackingMiddleware"]
