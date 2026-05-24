"""Stateful builder for ``researchTimelineBubble`` snapshots.

The A2UI spec mandates full snapshots (not deltas) on every relevant
transition during long-running research. This builder maintains the
ordered step list, advances statuses based on LangGraph node/tool
events, and emits a fresh snapshot only when state actually changed.

Step taxonomy is server-derived — the LLM has no role in producing
``researchTimelineBubble`` payloads.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from src.novelty_checker.api.response_parser import (
    _read_accumulator,
    _read_file_safe,
)


@dataclass
class _StepDef:
    id: str
    title: str
    nodes: tuple[str, ...]
    tools: tuple[str, ...]
    status: str = "not_started"


_DEFAULT_STEPS: list[_StepDef] = [
    _StepDef(
        id="plan",
        title="Planning research strategy",
        nodes=("agent",),
        tools=("generate_search_strategy",),
    ),
    _StepDef(
        id="patent-search",
        title="Patent keyword search",
        nodes=("patent-researcher", "keyword-precision-searcher"),
        tools=("patent_keyword_search", "batch_patent_search"),
    ),
    _StepDef(
        id="npl-search",
        title="Academic literature search",
        nodes=("npl-researcher",),
        tools=("npl_search", "batch_npl_search"),
    ),
    _StepDef(
        id="semantic-search",
        title="Semantic search",
        nodes=("semantic-researcher", "semantic-recall-searcher"),
        tools=(
            "semantic_patent_search",
            "batch_semantic_search",
            "batch_unified_search",
        ),
    ),
    _StepDef(
        id="citation-search",
        title="Citation analysis",
        nodes=("citation-researcher",),
        tools=(
            "batch_citation_search",
            "citation_chain_search",
            "get_patent_citations",
        ),
    ),
    _StepDef(
        id="coverage-eval",
        title="Coverage evaluation",
        nodes=("coverage-analyst",),
        tools=("evaluate_coverage",),
    ),
    _StepDef(
        id="report-write",
        title="Drafting report",
        nodes=("report-writer",),
        tools=("summarize_findings_for_report",),
    ),
]


def _build_step_lookups(
    steps: list[_StepDef],
) -> tuple[dict[str, str], dict[str, str]]:
    by_node: dict[str, str] = {}
    by_tool: dict[str, str] = {}
    for step in steps:
        for node in step.nodes:
            by_node[node] = step.id
        for tool in step.tools:
            by_tool[tool] = step.id
    return by_node, by_tool


@dataclass
class ResearchTimelineBuilder:
    """Stateful per-stream builder for ``researchTimelineBubble`` snapshots."""

    header_text: str = "Research progress"
    steps: list[_StepDef] = field(
        default_factory=lambda: [_StepDef(**s.__dict__) for s in _DEFAULT_STEPS]
    )
    _last_signature: str | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self._step_for_node, self._step_for_tool = _build_step_lookups(self.steps)
        self._steps_by_id = {s.id: s for s in self.steps}

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def on_node_start(self, node_name: str) -> dict[str, Any] | None:
        step_id = self._step_for_node.get(node_name)
        if step_id is None:
            return None
        return self._set_status(step_id, "in_progress")

    def on_tool_start(
        self, node_name: str, tool_name: str
    ) -> dict[str, Any] | None:
        step_id = self._step_for_tool.get(tool_name) or self._step_for_node.get(
            node_name
        )
        if step_id is None:
            return None
        return self._set_status(step_id, "in_progress")

    def on_tool_end(
        self, node_name: str, tool_name: str
    ) -> dict[str, Any] | None:
        step_id = self._step_for_tool.get(tool_name) or self._step_for_node.get(
            node_name
        )
        if step_id is None:
            return None
        return self._set_status(step_id, "completed")

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        """Return the current full snapshot (always fresh)."""
        return {
            "component": "researchTimelineBubble",
            "headerText": self.header_text,
            "steps": [
                {"id": s.id, "title": s.title, "status": s.status}
                for s in self.steps
            ],
            "completion": None,
        }

    def initial_snapshot(self) -> dict[str, Any]:
        """First snapshot the client should receive (all steps not_started).

        Also primes the dedupe signature so a duplicate snapshot won't be
        emitted by the next event handler.
        """
        snap = self.snapshot()
        self._last_signature = self._signature()
        return snap

    def finalize(self, backend: Any, ai_text: str) -> dict[str, Any]:
        """Promote any in-progress step to completed and populate ``completion``."""
        for step in self.steps:
            if step.status in ("not_started", "in_progress"):
                step.status = "completed"

        accum = _read_accumulator(backend) if backend else None
        report_md = _read_file_safe(backend, "/final_report.md") if backend else None

        completion: dict[str, Any] = {
            "title": "Research Complete",
            "message": "Your novelty assessment report is ready.",
            "sections": [],
        }

        if accum:
            coverage_pct = accum.get("final_coverage_pct")
            ref_count = len(accum.get("all_references", []) or [])
            if coverage_pct is not None or ref_count:
                summary_parts = []
                if coverage_pct is not None:
                    summary_parts.append(f"Overall coverage: {coverage_pct:.1f}%")
                if ref_count:
                    summary_parts.append(f"References found: {ref_count}")
                completion["sections"].append(
                    {
                        "title": "Coverage summary",
                        "body": " · ".join(summary_parts),
                    }
                )

        if report_md:
            completion["sections"].append(
                {
                    "title": "Final report",
                    "body": report_md,
                }
            )
        elif ai_text:
            completion["sections"].append(
                {"title": "Summary", "body": ai_text}
            )

        snap = self.snapshot()
        snap["completion"] = completion
        self._last_signature = self._signature()
        return snap

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _set_status(self, step_id: str, new_status: str) -> dict[str, Any] | None:
        step = self._steps_by_id.get(step_id)
        if step is None:
            return None
        if step.status == new_status:
            return None
        step.status = new_status
        sig = self._signature()
        if sig == self._last_signature:
            return None
        self._last_signature = sig
        return self.snapshot()

    def _signature(self) -> str:
        return json.dumps([(s.id, s.status) for s in self.steps])
