"""Patent lifecycle tracking for loss detection and session statistics.

Tracks every patent through five pipeline checkpoints:
  DISCOVERED → PERSISTED → TRIAGED → FEATURE_MAPPED → REPORTED

At session end, compares checkpoints to compute a loss funnel and
generates ``patent_statistics.json`` + ``patent_statistics.md`` in the
session workspace.

This is an **internal QA artifact** — it does not appear in the
client-facing 11-section novelty report.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# =============================================================================
# Checkpoint Enum
# =============================================================================

class PatentCheckpoint(str, Enum):
    """Lifecycle checkpoints for a patent in the novelty search pipeline."""

    DISCOVERED = "discovered"
    """Patent returned by a search tool (auto-extracted from result)."""

    PERSISTED = "persisted"
    """Patent written to findings files (round file or accumulator)."""

    TRIAGED = "triaged"
    """Patent assigned A/B/C relevance label."""

    FEATURE_MAPPED = "feature_mapped"
    """Patent has Y/Y1/N feature coverage mapping."""

    REPORTED = "reported"
    """Patent appears in the final report's Feature Matrix (Section 4)."""


# Ordered list for funnel calculations
_CHECKPOINT_ORDER = [
    PatentCheckpoint.DISCOVERED,
    PatentCheckpoint.PERSISTED,
    PatentCheckpoint.TRIAGED,
    PatentCheckpoint.FEATURE_MAPPED,
    PatentCheckpoint.REPORTED,
]


# =============================================================================
# Patent Event
# =============================================================================

@dataclass
class PatentEvent:
    """A single checkpoint event recorded for a patent."""

    checkpoint: PatentCheckpoint
    timestamp: str
    source_tool: str
    round_number: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Patent Tracker
# =============================================================================

class PatentTracker:
    """Track individual patents through the discovery-to-report pipeline.

    Thread-safe. Patents are keyed by normalised publication number.

    Args:
        session_id: Identifier for the current session.
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.start_time = datetime.now().isoformat()
        self._patents: dict[str, list[PatentEvent]] = {}
        self._total_evaluated: dict[str, int] = {}  # source_type -> count
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        pub_number: str,
        checkpoint: PatentCheckpoint,
        source_tool: str,
        round_number: int | None = None,
        **metadata: Any,
    ) -> None:
        """Record a checkpoint event for a patent.

        Args:
            pub_number: Publication number (normalised internally).
            checkpoint: Which lifecycle checkpoint was reached.
            source_tool: Tool that triggered this event.
            round_number: Research round (if known).
            **metadata: Additional key-value pairs (triage_label, source_type, …).
        """
        key = self._normalise(pub_number)
        if not key:
            return

        event = PatentEvent(
            checkpoint=checkpoint,
            timestamp=datetime.now().isoformat(),
            source_tool=source_tool,
            round_number=round_number,
            metadata=dict(metadata),
        )

        with self._lock:
            self._patents.setdefault(key, []).append(event)

    def record_evaluated(self, count: int, source_type: str) -> None:
        """Record total references seen from a search tool (including irrelevant).

        Unlike :meth:`record` which only tracks refs with publication numbers,
        this counts ALL references extracted from tool results — giving
        visibility into how many patents/NPLs the LLM evaluated in total.

        Args:
            count: Number of references extracted from the tool result.
            source_type: Category (``patent``, ``npl``, ``semantic``, ``citation``).
        """
        with self._lock:
            self._total_evaluated[source_type] = (
                self._total_evaluated.get(source_type, 0) + count
            )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_all_patents(self) -> dict[str, list[PatentEvent]]:
        """Return a copy of every tracked patent and its events."""
        with self._lock:
            return {k: list(v) for k, v in self._patents.items()}

    def get_latest_checkpoint(self, pub_number: str) -> PatentCheckpoint | None:
        """Return the most advanced checkpoint reached by *pub_number*."""
        key = self._normalise(pub_number)
        with self._lock:
            events = self._patents.get(key)
        if not events:
            return None
        return max(
            (e.checkpoint for e in events),
            key=lambda c: _CHECKPOINT_ORDER.index(c),
        )

    # ------------------------------------------------------------------
    # Funnel & Loss Analysis
    # ------------------------------------------------------------------

    def get_funnel(self) -> dict[str, int]:
        """Count of unique patents that reached each checkpoint.

        Returns:
            Mapping of checkpoint name → count.  Counts are cumulative
            (a patent that reached TRIAGED also counts under DISCOVERED
            and PERSISTED).
        """
        with self._lock:
            snapshot = {k: list(v) for k, v in self._patents.items()}

        counts: dict[str, int] = {cp.value: 0 for cp in _CHECKPOINT_ORDER}
        for events in snapshot.values():
            reached = {e.checkpoint for e in events}
            for cp in _CHECKPOINT_ORDER:
                if cp in reached:
                    counts[cp.value] += 1
        return counts

    def get_losses(self) -> dict[str, list[dict[str, Any]]]:
        """Identify patents lost at each stage transition.

        Returns:
            Mapping of ``"{from}_not_{to}"`` → list of patent detail dicts.
            Each dict includes ``triage_label`` when available (from the
            TRIAGED event) regardless of which transition the loss occurs at.
        """
        with self._lock:
            snapshot = {k: list(v) for k, v in self._patents.items()}

        losses: dict[str, list[dict[str, Any]]] = {}
        for i in range(len(_CHECKPOINT_ORDER) - 1):
            from_cp = _CHECKPOINT_ORDER[i]
            to_cp = _CHECKPOINT_ORDER[i + 1]
            key = f"{from_cp.value}_not_{to_cp.value}"
            lost: list[dict[str, Any]] = []
            for pub, events in snapshot.items():
                reached = {e.checkpoint for e in events}
                if from_cp in reached and to_cp not in reached:
                    first_event = next(
                        (e for e in events if e.checkpoint == from_cp), None
                    )
                    # Also look up the triage label from the TRIAGED event
                    triaged_event = next(
                        (e for e in events if e.checkpoint == PatentCheckpoint.TRIAGED),
                        None,
                    )
                    triage_label = (
                        triaged_event.metadata.get("triage_label", "unknown")
                        if triaged_event
                        else "unknown"
                    )
                    lost.append({
                        "pub_number": pub,
                        "source_tool": first_event.source_tool if first_event else "",
                        "round": first_event.round_number if first_event else None,
                        "triage_label": triage_label,
                        "metadata": first_event.metadata if first_event else {},
                    })
            losses[key] = lost
        return losses

    # ------------------------------------------------------------------
    # Statistics Generation
    # ------------------------------------------------------------------

    def generate_statistics(self) -> dict[str, Any]:
        """Comprehensive end-of-session statistics as a JSON-serialisable dict."""
        funnel = self.get_funnel()
        losses = self.get_losses()

        with self._lock:
            snapshot = {k: list(v) for k, v in self._patents.items()}

        # --- Summary ---
        discovered = funnel.get("discovered", 0)
        reported = funnel.get("reported", 0)
        retention = (reported / discovered * 100) if discovered else 0.0

        summary = {
            "total_discovered": discovered,
            "total_persisted": funnel.get("persisted", 0),
            "total_triaged": funnel.get("triaged", 0),
            "total_feature_mapped": funnel.get("feature_mapped", 0),
            "total_reported": reported,
            "overall_retention_pct": round(retention, 1),
        }

        # --- Funnel transitions ---
        funnel_transitions: dict[str, dict[str, Any]] = {}
        for i in range(len(_CHECKPOINT_ORDER) - 1):
            from_cp = _CHECKPOINT_ORDER[i]
            to_cp = _CHECKPOINT_ORDER[i + 1]
            before = funnel.get(from_cp.value, 0)
            after = funnel.get(to_cp.value, 0)
            lost = before - after
            funnel_transitions[f"{from_cp.value}_to_{to_cp.value}"] = {
                "before": before,
                "after": after,
                "lost": lost,
                "loss_pct": round(lost / before * 100, 1) if before else 0.0,
            }

        # --- By source ---
        by_source = self._compute_by_source(snapshot)

        # --- By round ---
        by_round = self._compute_by_round(snapshot)

        # --- By triage level ---
        by_triage = self._compute_by_triage(snapshot)

        # --- Lost patents ---
        lost_patents: dict[str, list[dict[str, Any]]] = {}
        for transition_key, patents in losses.items():
            if patents:
                lost_patents[transition_key] = patents

        # --- Total evaluated (all refs seen, including irrelevant) ---
        with self._lock:
            total_evaluated = {
                "total": sum(self._total_evaluated.values()),
                "by_source": dict(self._total_evaluated),
            }

        return {
            "session_id": self.session_id,
            "generated_at": datetime.now().isoformat(),
            "start_time": self.start_time,
            "summary": summary,
            "total_evaluated": total_evaluated,
            "funnel": funnel_transitions,
            "by_source": by_source,
            "by_round": by_round,
            "by_triage_level": by_triage,
            "lost_patents": lost_patents,
        }

    def generate_statistics_markdown(self) -> str:
        """Human-readable markdown report of session statistics."""
        stats = self.generate_statistics()
        s = stats["summary"]
        lines: list[str] = []

        lines.append("# Patent Tracking Statistics")
        lines.append("")
        lines.append(f"**Session**: {stats['session_id']}")
        lines.append(f"**Generated**: {stats['generated_at']}")
        lines.append("")

        # --- Funnel ---
        lines.append("## Funnel Summary")
        lines.append("")
        lines.append("| Stage | Count | Loss | Loss % |")
        lines.append("|-------|-------|------|--------|")
        lines.append(f"| Discovered | {s['total_discovered']} | - | - |")

        prev_count = s["total_discovered"]
        for stage_key in ("persisted", "triaged", "feature_mapped", "reported"):
            count = s[f"total_{stage_key}"]
            lost = prev_count - count
            pct = round(lost / prev_count * 100, 1) if prev_count else 0.0
            label = stage_key.replace("_", " ").title()
            lines.append(f"| {label} | {count} | {lost} | {pct}% |")
            prev_count = count

        retention = s["overall_retention_pct"]
        lines.append("")
        lines.append(
            f"**Overall Retention**: {s['total_reported']}/{s['total_discovered']}"
            f" = {retention}%"
        )
        lines.append("")

        # --- Total Evaluated ---
        te = stats.get("total_evaluated", {})
        if te.get("total", 0) > 0:
            lines.append("## Total References Evaluated")
            lines.append("")
            lines.append(
                "_All references returned by search tools, "
                "including irrelevant ones not tracked through the pipeline._"
            )
            lines.append("")
            lines.append("| Source | Count |")
            lines.append("|--------|-------|")
            for src, count in sorted(te.get("by_source", {}).items()):
                lines.append(f"| {src.title()} | {count} |")
            lines.append(f"| **Total** | **{te['total']}** |")
            lines.append("")
            lines.append(
                f"Of these, {s['total_discovered']} had valid publication numbers "
                f"and were tracked through the pipeline."
            )
            lines.append("")

        # --- By source ---
        by_source = stats.get("by_source", {})
        if by_source:
            lines.append("## By Source")
            lines.append("")
            lines.append(
                "| Source | Discovered | Persisted | Triaged | Mapped | Reported |"
            )
            lines.append("|--------|-----------|-----------|---------|--------|----------|")
            for src, counts in by_source.items():
                lines.append(
                    f"| {src.title()} "
                    f"| {counts.get('discovered', 0)} "
                    f"| {counts.get('persisted', 0)} "
                    f"| {counts.get('triaged', 0)} "
                    f"| {counts.get('feature_mapped', 0)} "
                    f"| {counts.get('reported', 0)} |"
                )
            lines.append("")

        # --- By round ---
        by_round = stats.get("by_round", {})
        if by_round:
            lines.append("## By Round")
            lines.append("")
            lines.append("| Round | Discovered | New Unique |")
            lines.append("|-------|-----------|------------|")
            for rnd, counts in sorted(by_round.items(), key=lambda x: int(x[0])):
                lines.append(
                    f"| {rnd} "
                    f"| {counts.get('discovered', 0)} "
                    f"| {counts.get('new_unique', 0)} |"
                )
            lines.append("")

        # --- By triage level ---
        by_triage = stats.get("by_triage_level", {})
        if by_triage:
            lines.append("## By Triage Level")
            lines.append("")
            lines.append("| Label | Count | Feature Mapped | Reported |")
            lines.append("|-------|-------|---------------|----------|")
            for label in ("A", "B", "C", "unknown"):
                counts = by_triage.get(label, {})
                if not counts:
                    continue
                lines.append(
                    f"| {label} "
                    f"| {counts.get('count', 0)} "
                    f"| {counts.get('feature_mapped', 0)} "
                    f"| {counts.get('reported', 0)} |"
                )
            lines.append("")

        # --- Lost patents detail ---
        lost = stats.get("lost_patents", {})
        if any(lost.values()):
            lines.append("## Lost Patents Detail")
            lines.append("")
            _transition_labels = {
                "discovered_not_persisted": (
                    "Discovered but NOT Persisted",
                    "Extracted from search results but not written to findings files.",
                ),
                "persisted_not_triaged": (
                    "Persisted but NOT Triaged",
                    "Saved to disk but never assigned A/B/C label.",
                ),
                "triaged_not_feature_mapped": (
                    "Triaged but NOT Feature-Mapped",
                    "Labelled but no Y/Y1/N feature coverage assigned. "
                    "Expected for C-level refs.",
                ),
                "feature_mapped_not_reported": (
                    "Feature-Mapped but NOT Reported",
                    "Had feature mappings but omitted from the final report.",
                ),
            }
            for key, patents in lost.items():
                if not patents:
                    continue
                title, desc = _transition_labels.get(key, (key, ""))
                lines.append(f"### {title} ({len(patents)})")
                lines.append("")
                lines.append(f"_{desc}_")
                lines.append("")
                lines.append("| Publication # | Source Tool | Round |")
                lines.append("|--------------|------------|-------|")
                for p in patents[:50]:  # cap at 50 rows
                    lines.append(
                        f"| {p['pub_number']} "
                        f"| {p.get('source_tool', '')} "
                        f"| {p.get('round', '-')} |"
                    )
                if len(patents) > 50:
                    lines.append(f"| ... and {len(patents) - 50} more | | |")
                lines.append("")

        # --- Quality metrics ---
        lines.append("## Quality Metrics")
        lines.append("")
        a_stats = by_triage.get("A", {})
        b_stats = by_triage.get("B", {})
        a_count = a_stats.get("count", 0)
        a_reported = a_stats.get("reported", 0)
        b_count = b_stats.get("count", 0)
        b_reported = b_stats.get("reported", 0)
        a_ret = round(a_reported / a_count * 100, 1) if a_count else 0.0
        b_ret = round(b_reported / b_count * 100, 1) if b_count else 0.0

        lines.append(f"- **A-ref retention**: {a_reported}/{a_count} = {a_ret}%")
        lines.append(f"- **B-ref retention**: {b_reported}/{b_count} = {b_ret}%")

        # Unexplained losses = A/B refs that were feature-mapped but not reported
        unexplained = 0
        for p in lost.get("feature_mapped_not_reported", []):
            if p.get("triage_label") in ("A", "B"):
                unexplained += 1
        lines.append(
            f"- **Unexplained A/B losses** (feature-mapped but not reported): "
            f"{unexplained}"
        )
        lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise(pub_number: str) -> str:
        """Normalise a publication number for deduplication.

        Strips whitespace and converts to upper case so that
        ``us10234567b2`` and ``US10234567B2`` resolve to the same key.
        """
        return re.sub(r"\s+", "", pub_number).upper() if pub_number else ""

    def _compute_by_source(
        self, snapshot: dict[str, list[PatentEvent]]
    ) -> dict[str, dict[str, int]]:
        """Breakdown by source type (patent/npl/semantic/citation).

        A single ref may have multiple DISCOVERED events (e.g. from live
        tool capture *and* findings-markdown backfill). Prefer the most
        specific source_type across all of them — "other" / "" only wins
        when no other event has a concrete source. This prevents a
        `save_round_findings` call with missing source info from pinning
        an otherwise-classifiable ref to the Other bucket.
        """
        sources: dict[str, dict[str, int]] = {}
        for pub, events in snapshot.items():
            reached = {e.checkpoint for e in events}
            disc_events = [
                e for e in events if e.checkpoint == PatentCheckpoint.DISCOVERED
            ]
            source = "other"
            for e in disc_events:
                candidate = (e.metadata.get("source_type") or "").strip().lower()
                if candidate and candidate != "other":
                    source = candidate
                    break
            if source not in sources:
                sources[source] = {cp.value: 0 for cp in _CHECKPOINT_ORDER}
            for cp in _CHECKPOINT_ORDER:
                if cp in reached:
                    sources[source][cp.value] += 1
        return sources

    def _compute_by_round(
        self, snapshot: dict[str, list[PatentEvent]]
    ) -> dict[str, dict[str, int]]:
        """Breakdown by research round."""
        rounds: dict[int, dict[str, int]] = {}
        seen: set[str] = set()
        # Sort events by round
        round_events: list[tuple[int, str]] = []
        for pub, events in snapshot.items():
            disc_event = next(
                (e for e in events if e.checkpoint == PatentCheckpoint.DISCOVERED),
                None,
            )
            if disc_event and disc_event.round_number is not None:
                round_events.append((disc_event.round_number, pub))

        round_events.sort(key=lambda x: x[0])
        for rnd, pub in round_events:
            if rnd not in rounds:
                rounds[rnd] = {"discovered": 0, "new_unique": 0}
            rounds[rnd]["discovered"] += 1
            if pub not in seen:
                rounds[rnd]["new_unique"] += 1
                seen.add(pub)

        return {str(k): v for k, v in sorted(rounds.items())}

    def _compute_by_triage(
        self, snapshot: dict[str, list[PatentEvent]]
    ) -> dict[str, dict[str, int]]:
        """Breakdown by triage label (A/B/C/unknown)."""
        triage: dict[str, dict[str, int]] = {}
        for pub, events in snapshot.items():
            reached = {e.checkpoint for e in events}
            # Find triage label from TRIAGED event metadata
            triaged_event = next(
                (e for e in events if e.checkpoint == PatentCheckpoint.TRIAGED),
                None,
            )
            label = (
                triaged_event.metadata.get("triage_label", "unknown")
                if triaged_event
                else "unknown"
            )
            if label not in triage:
                triage[label] = {"count": 0, "feature_mapped": 0, "reported": 0}
            triage[label]["count"] += 1
            if PatentCheckpoint.FEATURE_MAPPED in reached:
                triage[label]["feature_mapped"] += 1
            if PatentCheckpoint.REPORTED in reached:
                triage[label]["reported"] += 1
        return triage


# =============================================================================
# Exports
# =============================================================================

__all__ = ["PatentCheckpoint", "PatentEvent", "PatentTracker"]
