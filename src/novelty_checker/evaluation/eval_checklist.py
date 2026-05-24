"""Functional checklist for novelty checker evaluation runs.

Validates that a completed evaluation run meets minimum tool usage
and artifact requirements. Catches known failure modes like "agent
planned searches but never executed them" or "agent skipped semantic
search entirely."

when the orchestrator delegates search to sub-agents via the `task` tool, search tool calls
only appear in telemetry (sub-agent traces), not in the orchestrator's
TurnRecords. The checklist checks both sources.

Usage:
    from src.novelty_checker.evaluation.eval_checklist import run_functional_checklist

    result = run_novelty_check_e2e(idea="...")
    checklist = run_functional_checklist(result)

    if not checklist.passed:
        print("Checklist FAILED:")
        for check_name, passed in checklist.checks.items():
            if not passed:
                print(f"  FAIL: {check_name} - {checklist.details[check_name]}")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Search tool name sets (from agent tool registry)
# ---------------------------------------------------------------------------

_PATENT_SEARCH_TOOLS = frozenset({
    "patent_keyword_search",
    "batch_patent_search",
    # Raw Derwent tools — exposed in get_all_tools() and reachable by the
    # single-LLM baseline when it picks the low-level entrypoint instead
    # of the keyword/batch wrappers.
    "search_derwent_patents_fld",
    "search_derwent_citations",
})

_SEMANTIC_SEARCH_TOOLS = frozenset({
    "semantic_patent_search",
    "batch_semantic_search",
})

_NPL_SEARCH_TOOLS = frozenset({
    "npl_search",
    "batch_npl_search",
})

_ALL_SEARCH_TOOLS = _PATENT_SEARCH_TOOLS | _SEMANTIC_SEARCH_TOOLS | _NPL_SEARCH_TOOLS

# The unified batch tool wraps patent + npl + semantic in one call.
# We classify it by inspecting its args to determine which search
# types were included, but for the "any search happened" checks
# we treat it as covering all three.
_UNIFIED_SEARCH_TOOLS = frozenset({
    "batch_unified_search",
})

# Sub-agent types that correspond to search activity
_SEARCH_SUBAGENT_TYPES = frozenset({
    "patent-researcher",
    "npl-researcher",
    "semantic-researcher",
    "keyword-precision-searcher",
    "semantic-recall-searcher",
    "structural-combo-searcher",
    "citation-researcher",
})

_MIN_SEARCH_QUERIES = 3


# ---------------------------------------------------------------------------
# Result data class
# ---------------------------------------------------------------------------

@dataclass
class ChecklistResult:
    """Result from running the functional checklist.

    Attributes:
        passed: True if ALL checks passed.
        checks: Dict of check_name -> bool (True = passed).
        details: Dict of check_name -> human-readable explanation.
    """
    passed: bool
    checks: dict[str, bool]
    details: dict[str, str]

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Telemetry helpers
# ---------------------------------------------------------------------------

def _load_telemetry(session_path: Path | None) -> dict[str, Any] | None:
    """Load telemetry.json from session directory.

    Args:
        session_path: Path to session directory, or None.

    Returns:
        Parsed telemetry dict, or None if unavailable.
    """
    if session_path is None:
        return None

    telemetry_path = session_path / "telemetry.json"
    if not telemetry_path.exists():
        _logger.debug("No telemetry.json at %s", telemetry_path)
        return None

    try:
        with open(telemetry_path, encoding="utf-8") as f:
            raw = json.load(f)
        return raw.get("summary", raw)
    except Exception as exc:
        _logger.warning("Failed to parse telemetry.json: %s", exc)
        return None


def _count_telemetry_search_calls(
    telemetry: dict[str, Any],
    tool_names: frozenset[str],
) -> dict[str, int]:
    """Count search tool calls from telemetry search_queries.

    The telemetry search_queries array contains entries like:
        {"agent_name": "patent-researcher", "tool_name": "patent_keyword_search", ...}

    Args:
        telemetry: Parsed telemetry summary dict.
        tool_names: Set of tool names to look for.

    Returns:
        Dict of tool_name -> count.
    """
    counts: dict[str, int] = {}
    for entry in telemetry.get("search_queries", []):
        name = entry.get("tool_name", "")
        if name in tool_names:
            counts[name] = counts.get(name, 0) + 1
    return counts


def _count_telemetry_all_tool_calls(
    telemetry: dict[str, Any],
    tool_names: frozenset[str],
) -> dict[str, int]:
    """Count tool calls across all agents from telemetry token_usage.

    For tools like evaluate_coverage that may be called by sub-agents
    but don't appear in search_queries, we check the per-agent tool
    call details if available, or fall back to search_queries.

    Args:
        telemetry: Parsed telemetry summary dict.
        tool_names: Set of tool names to look for.

    Returns:
        Dict of tool_name -> count.
    """
    # search_queries captures all search-type tool calls
    return _count_telemetry_search_calls(telemetry, tool_names)


def _count_task_delegations(
    turns: list[Any],
    subagent_types: frozenset[str],
) -> dict[str, int]:
    """Count `task` tool calls by subagent_type from orchestrator turns.

    When the orchestrator delegates to sub-agents via the `task` tool,
    the args contain `subagent_type` identifying which sub-agent ran.

    Args:
        turns: List of TurnRecord objects.
        subagent_types: Set of sub-agent type names to look for.

    Returns:
        Dict of subagent_type -> count.
    """
    counts: dict[str, int] = {}
    for turn in turns:
        if hasattr(turn, "tool_call_details") and turn.tool_call_details:
            for tc in turn.tool_call_details:
                name = tc.name if hasattr(tc, "name") else ""
                if name == "task":
                    args = tc.args if hasattr(tc, "args") else {}
                    subagent_type = args.get("subagent_type", "")
                    if subagent_type in subagent_types:
                        counts[subagent_type] = counts.get(subagent_type, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Internal helpers (orchestrator-level)
# ---------------------------------------------------------------------------

def _count_tool_calls_by_name(
    turns: list[Any],
    tool_names: frozenset[str],
    phase_filter: str | None = None,
) -> dict[str, int]:
    """Count occurrences of specific tool names across orchestrator turns.

    Uses tool_call_details if available (enriched TurnRecord),
    falls back to tool_calls (list of strings) for backward compat.

    Args:
        turns: List of TurnRecord objects.
        tool_names: Set of tool names to look for.
        phase_filter: If set, only count turns in this RunPhase name.

    Returns:
        Dict of tool_name -> count.
    """
    counts: dict[str, int] = {}
    for turn in turns:
        if phase_filter and turn.phase.name != phase_filter:
            continue

        if hasattr(turn, "tool_call_details") and turn.tool_call_details:
            for tc in turn.tool_call_details:
                name = tc.name if hasattr(tc, "name") else ""
                if name in tool_names:
                    counts[name] = counts.get(name, 0) + 1
        else:
            for name in turn.tool_calls:
                if name in tool_names:
                    counts[name] = counts.get(name, 0) + 1

    return counts


def _total_tool_calls(turns: list[Any], tool_names: frozenset[str]) -> int:
    """Count total tool calls matching any of the given names."""
    counts = _count_tool_calls_by_name(turns, tool_names)
    return sum(counts.values())


def _format_counts(counts: dict[str, int], source: str = "") -> str:
    """Format tool call counts into a readable string."""
    if not counts:
        return "not called"
    parts = [
        f"{name} called {count} time{'s' if count > 1 else ''}"
        for name, count in sorted(counts.items())
    ]
    result = ", ".join(parts)
    if source:
        result += f" (via {source})"
    return result


# ---------------------------------------------------------------------------
# Individual check functions (with telemetry fallback)
# ---------------------------------------------------------------------------

def _check_patent_search(
    turns: list[Any],
    telemetry: dict[str, Any] | None,
) -> tuple[bool, str]:
    """Check: patent keyword search was called at least once.

    First checks orchestrator turns. If not found there (sub-agent
    delegation pattern), falls back to telemetry search_queries.
    """
    # Check orchestrator level
    counts = _count_tool_calls_by_name(turns, _PATENT_SEARCH_TOOLS)
    if sum(counts.values()) > 0:
        return True, _format_counts(counts, source="orchestrator")

    # Fallback: check telemetry for sub-agent calls
    if telemetry is not None:
        tel_counts = _count_telemetry_search_calls(telemetry, _PATENT_SEARCH_TOOLS)
        if sum(tel_counts.values()) > 0:
            return True, _format_counts(tel_counts, source="sub-agents")

    return False, (
        "FAILED: No patent search tool was called "
        "(expected patent_keyword_search or batch_patent_search "
        "at orchestrator or sub-agent level)"
    )


def _check_semantic_search(
    turns: list[Any],
    telemetry: dict[str, Any] | None,
) -> tuple[bool, str]:
    """Check: semantic search was called at least once."""
    counts = _count_tool_calls_by_name(turns, _SEMANTIC_SEARCH_TOOLS)
    if sum(counts.values()) > 0:
        return True, _format_counts(counts, source="orchestrator")

    if telemetry is not None:
        tel_counts = _count_telemetry_search_calls(telemetry, _SEMANTIC_SEARCH_TOOLS)
        if sum(tel_counts.values()) > 0:
            return True, _format_counts(tel_counts, source="sub-agents")

    return False, (
        "FAILED: No semantic search tool was called "
        "(expected semantic_patent_search or batch_semantic_search "
        "at orchestrator or sub-agent level)"
    )


def _check_npl_search(
    turns: list[Any],
    telemetry: dict[str, Any] | None,
) -> tuple[bool, str]:
    """Check: NPL search was called at least once."""
    counts = _count_tool_calls_by_name(turns, _NPL_SEARCH_TOOLS)
    if sum(counts.values()) > 0:
        return True, _format_counts(counts, source="orchestrator")

    if telemetry is not None:
        tel_counts = _count_telemetry_search_calls(telemetry, _NPL_SEARCH_TOOLS)
        if sum(tel_counts.values()) > 0:
            return True, _format_counts(tel_counts, source="sub-agents")

    return False, (
        "FAILED: No NPL search tool was called "
        "(expected npl_search or batch_npl_search "
        "at orchestrator or sub-agent level)"
    )


def _check_min_search_queries(
    turns: list[Any],
    telemetry: dict[str, Any] | None,
) -> tuple[bool, str]:
    """Check: at least N total search tool calls were made."""
    # Orchestrator level
    orch_total = _total_tool_calls(turns, _ALL_SEARCH_TOOLS)
    if orch_total >= _MIN_SEARCH_QUERIES:
        return True, (
            f"{orch_total} total search tool calls at orchestrator level "
            f"(minimum: {_MIN_SEARCH_QUERIES})"
        )

    # Telemetry level (sub-agents)
    if telemetry is not None:
        tel_counts = _count_telemetry_search_calls(
            telemetry, _ALL_SEARCH_TOOLS | _UNIFIED_SEARCH_TOOLS
        )
        tel_total = sum(tel_counts.values())
        combined = orch_total + tel_total
        if combined >= _MIN_SEARCH_QUERIES:
            return True, (
                f"{combined} total search tool calls "
                f"(orchestrator: {orch_total}, sub-agents: {tel_total}, "
                f"minimum: {_MIN_SEARCH_QUERIES})"
            )

    # Both failed
    tel_total = 0
    if telemetry is not None:
        tel_counts = _count_telemetry_search_calls(
            telemetry, _ALL_SEARCH_TOOLS | _UNIFIED_SEARCH_TOOLS
        )
        tel_total = sum(tel_counts.values())
    combined = orch_total + tel_total
    return False, (
        f"FAILED: Only {combined} search tool calls "
        f"(orchestrator: {orch_total}, sub-agents: {tel_total}, "
        f"minimum: {_MIN_SEARCH_QUERIES})"
    )


def _check_think_tool(turns: list[Any]) -> tuple[bool, str]:
    """Check: think_tool was called at least once during AUTONOMOUS_RESEARCH.

    think_tool is called by the orchestrator, so no telemetry fallback needed.
    """
    counts = _count_tool_calls_by_name(
        turns,
        frozenset({"think_tool"}),
        phase_filter="AUTONOMOUS_RESEARCH",
    )
    total = sum(counts.values())
    if total > 0:
        return True, (
            f"think_tool called {total} time{'s' if total > 1 else ''} "
            f"during AUTONOMOUS_RESEARCH"
        )
    return False, (
        "FAILED: think_tool was not called during AUTONOMOUS_RESEARCH "
        "(agent may have skipped reflection)"
    )


def _check_coverage_evaluated(
    turns: list[Any],
    telemetry: dict[str, Any] | None,
) -> tuple[bool, str]:
    """Check: evaluate_coverage was called at least once.

    May be called by orchestrator or by sub-agents. Also accepts
    think_tool reflections that contain coverage analysis as a proxy
    (the agent uses think_tool for coverage assessment in the
    multi-agent architecture).
    """
    # Check orchestrator for evaluate_coverage
    counts = _count_tool_calls_by_name(turns, frozenset({"evaluate_coverage"}))
    total = sum(counts.values())
    if total > 0:
        return True, f"evaluate_coverage called {total} time{'s' if total > 1 else ''}"

    # Check telemetry for sub-agent evaluate_coverage calls
    if telemetry is not None:
        tel_counts = _count_telemetry_search_calls(
            telemetry, frozenset({"evaluate_coverage"})
        )
        tel_total = sum(tel_counts.values())
        if tel_total > 0:
            return True, (
                f"evaluate_coverage called {tel_total} time{'s' if tel_total > 1 else ''} "
                f"(via sub-agents)"
            )

    # Proxy check: think_tool with coverage analysis content
    # In the multi-agent architecture, the orchestrator uses think_tool
    # to perform coverage analysis instead of calling evaluate_coverage
    think_counts = _count_tool_calls_by_name(
        turns,
        frozenset({"think_tool"}),
        phase_filter="AUTONOMOUS_RESEARCH",
    )
    think_total = sum(think_counts.values())
    if think_total > 0:
        # Verify at least one think_tool call contains coverage analysis
        for turn in turns:
            if turn.phase.name != "AUTONOMOUS_RESEARCH":
                continue
            if hasattr(turn, "tool_call_details") and turn.tool_call_details:
                for tc in turn.tool_call_details:
                    if tc.name != "think_tool":
                        continue
                    args = tc.args if hasattr(tc, "args") else {}
                    reflection = args.get("reflection", "")
                    coverage_keywords = [
                        "coverage analysis",
                        "Coverage Analysis",
                        "coverage level",
                        "Coverage Level",
                        "STRONG",
                        "MODERATE",
                        "WEAK",
                        "NONE",
                        "SATURATED",
                        "coverage summary",
                        "Coverage Summary",
                    ]
                    if any(kw in reflection for kw in coverage_keywords):
                        return True, (
                            f"Coverage assessed via think_tool reflection "
                            f"({think_total} think_tool calls found with "
                            f"coverage analysis content)"
                        )

    return False, (
        "FAILED: evaluate_coverage was not called and no think_tool "
        "reflection with coverage analysis was found "
        "(agent may not have assessed coverage before stopping)"
    )


def _check_findings_persisted(turns: list[Any]) -> tuple[bool, str]:
    """Check: save_round_findings was called at least once."""
    counts = _count_tool_calls_by_name(turns, frozenset({"save_round_findings"}))
    total = sum(counts.values())
    if total > 0:
        return True, f"save_round_findings called {total} time{'s' if total > 1 else ''}"
    return False, (
        "FAILED: save_round_findings was not called "
        "(findings may not be persisted to disk)"
    )


def _check_scope_artifact(artifacts: dict[str, str]) -> tuple[bool, str]:
    """Check: scope.md exists and is non-empty."""
    content = artifacts.get("scope.md", "")
    if content and not content.startswith("[Error"):
        size = len(content.encode("utf-8"))
        return True, f"scope.md exists ({size:,} bytes)"
    return False, "FAILED: scope.md is missing or empty"


def _check_features_artifact(artifacts: dict[str, str]) -> tuple[bool, str]:
    """Check: features.md exists and is non-empty."""
    content = artifacts.get("features.md", "")
    if content and not content.startswith("[Error"):
        size = len(content.encode("utf-8"))
        return True, f"features.md exists ({size:,} bytes)"
    return False, "FAILED: features.md is missing or empty"


def _check_report_generated(artifacts: dict[str, str]) -> tuple[bool, str]:
    """Check: final_report.md exists and is non-empty."""
    content = artifacts.get("final_report.md", "")
    if content and not content.startswith("[Error"):
        size = len(content.encode("utf-8"))
        return True, f"final_report.md exists ({size:,} bytes)"
    return False, "FAILED: final_report.md is missing or empty"


def _check_run_completed(final_phase_name: str) -> tuple[bool, str]:
    """Check: run completed without error."""
    if final_phase_name == "COMPLETED":
        return True, "Run completed successfully"
    return False, f"FAILED: Run ended in {final_phase_name} phase"


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def run_functional_checklist(
    result: Any,
    telemetry: dict[str, Any] | None = None,
) -> ChecklistResult:
    """Run the functional checklist against a completed evaluation run.

    Validates that the agent called required tools, produced required
    artifacts, and completed without error.

    Supports the multi-agent architecture where the orchestrator
    delegates search to sub-agents via the `task` tool. When search
    tool calls are not found at the orchestrator level, the checklist
    falls back to checking telemetry data (sub-agent tool calls).

    Args:
        result: An EvalRunResult (or compatible object) with:
            - turns: list of TurnRecord
            - artifacts: dict of filename -> content
            - final_phase: RunPhase with .name attribute
            - session_path: Path to session directory (optional)
        telemetry: Optional pre-parsed telemetry dict. If not provided,
            attempts to load from result.session_path / telemetry.json.

    Returns:
        ChecklistResult with pass/fail for each check and details.
    """
    turns = result.turns
    artifacts = result.artifacts
    final_phase_name = result.final_phase.name

    # Load telemetry if not provided
    if telemetry is None:
        session_path = getattr(result, "session_path", None)
        telemetry = _load_telemetry(session_path)

    checks: dict[str, bool] = {}
    details: dict[str, str] = {}

    # Tool usage checks (with telemetry fallback for search tools)
    checks["patent_search_called"], details["patent_search_called"] = (
        _check_patent_search(turns, telemetry)
    )
    checks["semantic_search_called"], details["semantic_search_called"] = (
        _check_semantic_search(turns, telemetry)
    )
    checks["npl_search_called"], details["npl_search_called"] = (
        _check_npl_search(turns, telemetry)
    )
    checks["min_search_queries"], details["min_search_queries"] = (
        _check_min_search_queries(turns, telemetry)
    )
    checks["think_tool_used"], details["think_tool_used"] = (
        _check_think_tool(turns)
    )
    checks["coverage_evaluated"], details["coverage_evaluated"] = (
        _check_coverage_evaluated(turns, telemetry)
    )
    checks["findings_persisted"], details["findings_persisted"] = (
        _check_findings_persisted(turns)
    )

    # Artifact checks
    checks["scope_artifact_exists"], details["scope_artifact_exists"] = (
        _check_scope_artifact(artifacts)
    )
    checks["features_artifact_exists"], details["features_artifact_exists"] = (
        _check_features_artifact(artifacts)
    )
    checks["report_generated"], details["report_generated"] = (
        _check_report_generated(artifacts)
    )

    # Completion check
    checks["run_completed_without_error"], details["run_completed_without_error"] = (
        _check_run_completed(final_phase_name)
    )

    passed = all(checks.values())

    checklist_result = ChecklistResult(
        passed=passed,
        checks=checks,
        details=details,
    )

    # Log summary
    failed_checks = [name for name, ok in checks.items() if not ok]
    if passed:
        _logger.info("Functional checklist: ALL 11 checks PASSED")
    else:
        _logger.warning(
            "Functional checklist: %d of 11 checks FAILED: %s",
            len(failed_checks),
            ", ".join(failed_checks),
        )

    return checklist_result