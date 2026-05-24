"""Unified trace writer for evaluation runs.

Combines enriched EvalRunResult + parsed telemetry.json + checklist result
into a single eval_trace.json file following the trace schema spec
(eval_trace_schema_.md).

The eval_trace.json is the single file that scorers, dashboard, and CI
all consume. It unifies three data sources:
    1. EvalRunResult (turn records with tool calls, tokens, gate events)
    2. telemetry.json (sub-agent tool timing, search queries, round metrics)
    3. ChecklistResult (11 functional compliance checks)

Usage:
    from src.novelty_checker.eval_runner import run_novelty_check_e2e
    from src.novelty_checker.evaluation.eval_checklist import run_functional_checklist
    from src.novelty_checker.evaluation.trace_writer import write_eval_trace

    result = run_novelty_check_e2e(idea="...")
    checklist = run_functional_checklist(result)
    trace = write_eval_trace(result, checklist)

    # trace is also written to: sessions/{session_id}/eval_trace.json
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

_SCHEMA_VERSION = "1.1"
_TRACE_TYPE = "novelty_checker"

# Session files to include in the artifacts manifest
_MANIFEST_FILES = [
    "scope.md",
    "features.md",
    "references.md",
    "final_report.md",
    "telemetry.json",
    "findings_accumulator.json",
    "findings_auto_accumulator.json",
    "patent_statistics.md",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_run_metadata(result: Any) -> dict[str, Any]:
    """Build the run_metadata section from EvalRunResult.

    Args:
        result: EvalRunResult with session info, timing, and phase.

    Returns:
        Dict matching the run_metadata schema.
    """
    # Calculate start/end times from turn timestamps if available
    start_time = None
    end_time = None
    if result.turns:
        first_turn = result.turns[0]
        if hasattr(first_turn, "timestamp") and first_turn.timestamp:
            start_time = first_turn.timestamp
        last_turn = result.turns[-1]
        if hasattr(last_turn, "timestamp") and last_turn.timestamp:
            end_time = last_turn.timestamp

    return {
        "run_id": result.thread_id,
        "session_id": result.session_id,
        "thread_id": result.thread_id,
        "model_name": getattr(result, "model_name", None),
        "model_provider": "azure_openai",
        "model_deployment": os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "unknown"),
        "prompt_version": None,
        "start_time": start_time,
        "end_time": end_time,
        "total_duration_seconds": result.total_duration_seconds,
        "total_turns": result.total_turns,
        "final_phase": result.final_phase.name,
        "error": result.error,
        "fixture_id": None,
        "run_config": {
            "max_turns": 30,
            "max_duration_seconds": 3600,
            "auto_scope_prompt": "default",
            "hitl_mode": "accept_all",
        },
    }


def _build_turn(turn: Any) -> dict[str, Any]:
    """Convert a TurnRecord into a trace-schema-compatible dict.

    Handles both enriched TurnRecords (with tool_call_details, token_usage)
    and original TurnRecords (with only tool_calls as list of strings).

    Args:
        turn: A TurnRecord object.

    Returns:
        Dict matching the turns[] schema.
    """
    # Tool calls: prefer enriched details, fall back to names-only
    tool_calls_out = []
    if hasattr(turn, "tool_call_details") and turn.tool_call_details:
        for tc in turn.tool_call_details:
            tool_calls_out.append({
                "tool_call_id": tc.tool_call_id,
                "name": tc.name,
                "args": tc.args,
                "output_preview": tc.output_preview,
                "output_size_chars": tc.output_size_chars,
                "success": tc.success,
                "error": tc.error,
                "duration_ms": tc.duration_ms,
            })
    else:
        for name in turn.tool_calls:
            tool_calls_out.append({
                "tool_call_id": None,
                "name": name,
                "args": {},
                "output_preview": "",
                "output_size_chars": 0,
                "success": True,
                "error": None,
                "duration_ms": None,
            })

    # Token usage
    token_usage_out = None
    if hasattr(turn, "token_usage") and turn.token_usage is not None:
        token_usage_out = {
            "input_tokens": turn.token_usage.input_tokens,
            "output_tokens": turn.token_usage.output_tokens,
            "total_tokens": turn.token_usage.total_tokens,
        }

    return {
        "turn_number": turn.turn_number,
        "phase": turn.phase.name,
        "timestamp": getattr(turn, "timestamp", None),
        "duration_seconds": turn.duration_seconds,
        "injected_message": turn.injected_message,
        "ai_content_preview": turn.ai_content_preview,
        "ai_content_full": getattr(turn, "ai_content_full", None),
        "gate_event": getattr(turn, "gate_event", None),
        "tool_calls": tool_calls_out,
        "token_usage": token_usage_out,
        "message_count": turn.message_count,
    }


def _build_stage_summary(turns: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute per-stage aggregated metrics from turn dicts.

    Groups turns by phase and sums duration, tokens, and tool calls.

    Args:
        turns: List of turn dicts (already converted by _build_turn).

    Returns:
        Dict of phase_name -> stage summary.

    Note: This stage summary only reflects orchestrator-level data. telemetry section has more detailed per-agent-per-stage breakdown
    """
    stages: dict[str, dict[str, Any]] = {}

    for turn in turns:
        phase = turn["phase"]
        if phase not in stages:
            stages[phase] = {
                "turns": [],
                "total_duration_seconds": 0.0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "tool_calls_by_name": defaultdict(int),
            }

        stage = stages[phase]
        stage["turns"].append(turn["turn_number"])
        stage["total_duration_seconds"] += turn["duration_seconds"]

        # Sum tokens (skip if None)
        if turn["token_usage"]:
            stage["total_input_tokens"] += turn["token_usage"].get("input_tokens", 0)
            stage["total_output_tokens"] += turn["token_usage"].get("output_tokens", 0)

        # Count tool calls by name
        for tc in turn["tool_calls"]:
            name = tc.get("name", "unknown")
            if name:
                stage["tool_calls_by_name"][name] += 1

    # Convert defaultdicts to regular dicts for JSON serialization
    for phase, stage in stages.items():
        stage["tool_calls_by_name"] = dict(stage["tool_calls_by_name"])
        stage["total_duration_seconds"] = round(stage["total_duration_seconds"], 2)

    return stages


def _parse_telemetry(session_path: Path) -> dict[str, Any] | None:
    """Parse telemetry.json from the session directory.

    Reads the file written by TelemetryMiddleware and extracts the
    summary section which contains rounds, tool calls, token usage,
    and search queries.

    Args:
        session_path: Path to the session directory.

    Returns:
        Parsed telemetry summary dict, or None if file doesn't exist.
    """
    telemetry_path = session_path / "telemetry.json"
    if not telemetry_path.exists():
        _logger.debug("No telemetry.json found at %s", telemetry_path)
        return None

    try:
        with open(telemetry_path, encoding="utf-8") as f:
            raw = json.load(f)

        # TelemetryMiddleware writes a "summary" key with the structured data
        summary = raw.get("summary", raw)

        return {
            "session_id": summary.get("session_id", ""),
            "total_rounds": summary.get("total_rounds", 0),
            "total_tool_calls": summary.get("total_tool_calls", 0),
            "failed_tool_calls": summary.get("failed_tool_calls", 0),
            "success_rate": summary.get("success_rate", 0.0),
            "avg_tool_duration_ms": summary.get("avg_tool_duration_ms", 0.0),
            "rounds": summary.get("rounds", []),
            "token_usage": summary.get("token_usage", {}),
            "search_queries": summary.get("search_queries", []),
        }
    except Exception as exc:
        _logger.warning("Failed to parse telemetry.json: %s", exc)
        return None


def _build_artifacts_manifest(session_path: Path) -> list[dict[str, Any]]:
    """List session files with sizes for the artifacts manifest.

    Scans for known artifact files and the findings/ directory.

    Args:
        session_path: Path to the session directory.

    Returns:
        List of dicts with filename, size_bytes, exists.
    """
    manifest = []

    # Check known files
    for filename in _MANIFEST_FILES:
        filepath = session_path / filename
        exists = filepath.exists()
        size_bytes = filepath.stat().st_size if exists else 0
        manifest.append({
            "filename": filename,
            "size_bytes": size_bytes,
            "exists": exists,
        })

    # Check findings directory
    findings_dir = session_path / "findings"
    if findings_dir.exists():
        for f in sorted(findings_dir.iterdir()):
            if f.is_file() and f.suffix in (".md", ".json"):
                manifest.append({
                    "filename": f"findings/{f.name}",
                    "size_bytes": f.stat().st_size,
                    "exists": True,
                })

    # Check traces directory (sub-agent traces from telemetry)
    traces_dir = session_path / "traces"
    if traces_dir.exists():
        for f in sorted(traces_dir.iterdir()):
            if f.is_file():
                manifest.append({
                    "filename": f"traces/{f.name}",
                    "size_bytes": f.stat().st_size,
                    "exists": True,
                })

    return manifest


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def write_eval_trace(
    result: Any,
    checklist: Any,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Build unified evaluation trace and write to session directory.

    Combines three data sources into a single eval_trace.json:
    1. EvalRunResult (enriched turn records from eval_runner.py)
    2. telemetry.json (sub-agent tool timing from TelemetryMiddleware)
    3. ChecklistResult (functional compliance from eval_checklist.py)

    Args:
        result: EvalRunResult from run_novelty_check_e2e().
        checklist: ChecklistResult from run_functional_checklist().
        output_path: Optional override for the output file path.
            Defaults to sessions/{session_id}/eval_trace.json.

    Returns:
        The complete trace dict (also written to disk).
    """
    session_path = result.session_path

    # Build each section
    run_metadata = _build_run_metadata(result)
    turns = [_build_turn(turn) for turn in result.turns]
    stage_summary = _build_stage_summary(turns)
    telemetry = _parse_telemetry(session_path)
    artifacts_manifest = _build_artifacts_manifest(session_path)

    # Build checklist section
    checklist_section = None
    if checklist is not None:
        checklist_section = {
            "passed": checklist.passed,
            "checks": checklist.checks,
            "details": checklist.details,
        }

    # Assemble the complete trace
    trace = {
        "schema_version": _SCHEMA_VERSION,
        "trace_type": _TRACE_TYPE,
        "run_metadata": run_metadata,
        "turns": turns,
        "stage_summary": stage_summary,
        "telemetry": telemetry,
        "checklist": checklist_section,
        "artifacts_manifest": artifacts_manifest,
    }

    # Write to disk
    if output_path is None:
        output_path = session_path / "eval_trace.json"

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(trace, f, indent=2, ensure_ascii=False, default=str)
        _logger.info("Eval trace written to %s (%d bytes)", output_path, output_path.stat().st_size)
    except Exception as exc:
        _logger.error("Failed to write eval trace to %s: %s", output_path, exc)

    # Also write checklist separately for quick access
    if checklist_section is not None:
        checklist_path = session_path / "eval_checklist.json"
        try:
            with open(checklist_path, "w", encoding="utf-8") as f:
                json.dump(checklist_section, f, indent=2, ensure_ascii=False)
            _logger.debug("Checklist written to %s", checklist_path)
        except Exception as exc:
            _logger.warning("Failed to write checklist to %s: %s", checklist_path, exc)

    return trace