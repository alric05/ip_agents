#!/usr/bin/env python3
"""Compute actual performance percentiles from session telemetry data.

Reads all sessions/*/telemetry.json files, classifies operations into
ADR categories, and outputs P50/P80/P95/P99 per category.
"""

import json
import statistics
from collections import defaultdict
from pathlib import Path

SESSIONS_DIR = Path(__file__).resolve().parent.parent / "sessions"

# Category classification
SINGLE_API_TOOLS = {
    "patent_keyword_search",
    "npl_search",
    "semantic_patent_search",
    "get_patent_details",
    "get_patent_citations",
}

BATCH_TOOLS = {
    "batch_unified_search",
    "batch_patent_search",
    "batch_npl_search",
    "batch_semantic_search",
}

CITATION_TOOLS = {
    "batch_citation_search",
    "citation_chain_search",
}

ANALYSIS_TOOLS = {
    "evaluate_coverage",
    "triage_reference",
    "map_features_to_reference",
    "generate_search_strategy",
    "build_feature_matrix",
    "validate_feature_matrix_format",
    "aggregate_search_results",
}

REFLECTION_TOOLS = {
    "think_tool",
    "save_round_findings",
}

INTERNAL_TOOLS = {
    "write_file",
    "read_file",
    "ls",
    "get_all_findings",
    "get_coverage_gaps",
    "write_todos",
}


def classify_tool(tool_name: str) -> str:
    if tool_name in SINGLE_API_TOOLS:
        return "B: Single API Call"
    if tool_name in BATCH_TOOLS:
        return "C: Batch Tool Call"
    if tool_name in CITATION_TOOLS:
        return "D: Citation Network"
    if tool_name in ANALYSIS_TOOLS:
        return "B+: Analysis Tool (LLM-backed)"
    if tool_name in REFLECTION_TOOLS:
        return "A+: Reflection/Persistence"
    if tool_name in INTERNAL_TOOLS:
        return "Internal (filesystem)"
    return f"Other ({tool_name})"


def percentile(data: list[float], p: int) -> float:
    """Compute percentile using the 'interpolation' method."""
    sorted_data = sorted(data)
    n = len(sorted_data)
    if n == 1:
        return sorted_data[0]
    k = (p / 100) * (n - 1)
    f = int(k)
    c = k - f
    if f + 1 < n:
        return sorted_data[f] + c * (sorted_data[f + 1] - sorted_data[f])
    return sorted_data[f]


def fmt_duration(ms: float) -> str:
    """Format milliseconds into human-readable duration."""
    if ms < 1000:
        return f"{ms:.0f}ms"
    s = ms / 1000
    if s < 60:
        return f"{s:.1f}s"
    m = s / 60
    return f"{m:.1f}min"


def is_complete_session(session_dir: Path, data: dict) -> tuple[bool, str]:
    """Check if a session is complete and usable for performance analysis.

    Returns (is_complete, reason).
    """
    if not (session_dir / "final_report.md").exists():
        return False, "no final_report.md"
    tool_calls = data.get("tool_calls", [])
    if len(tool_calls) <= 5:
        return False, f"only {len(tool_calls)} tool calls (report-only or minimal run)"
    return True, "complete"


def main():
    tool_durations: dict[str, list[float]] = defaultdict(list)
    model_durations: list[float] = []
    model_durations_by_agent: dict[str, list[float]] = defaultdict(list)
    per_tool_durations: dict[str, list[float]] = defaultdict(list)

    session_count = 0
    included_sessions: list[str] = []
    excluded_sessions: list[tuple[str, str]] = []
    telemetry_files = sorted(SESSIONS_DIR.glob("*/telemetry.json"))

    for tf in telemetry_files:
        try:
            data = json.loads(tf.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            excluded_sessions.append((tf.parent.name, "invalid telemetry.json"))
            continue

        session_dir = tf.parent
        complete, reason = is_complete_session(session_dir, data)
        if not complete:
            excluded_sessions.append((session_dir.name, reason))
            continue

        session_count += 1
        included_sessions.append(session_dir.name)

        # Process tool calls
        for tc in data.get("tool_calls", []):
            duration = tc.get("duration_ms")
            tool_name = tc.get("tool_name", "unknown")
            if duration is None or duration <= 0:
                continue

            category = classify_tool(tool_name)
            tool_durations[category].append(duration)
            per_tool_durations[tool_name].append(duration)

        # Process model calls
        for mc in data.get("model_calls", []):
            duration = mc.get("duration_ms")
            if duration is None or duration <= 0:
                continue

            model_durations.append(duration)
            agent = mc.get("agent_name", "unknown")
            model_durations_by_agent[agent].append(duration)

    # Print results
    print(f"# Performance Baselines — Measured from {session_count} Complete Sessions")
    print(f"Data source: {SESSIONS_DIR}")
    print()

    print("## Session Filter")
    print()
    print(f"**Included ({len(included_sessions)}):**")
    for s in included_sessions:
        print(f"- {s}")
    print()
    print(f"**Excluded ({len(excluded_sessions)}):**")
    for s, reason in excluded_sessions:
        print(f"- {s} — {reason}")
    print()

    # Category A: LLM Decision Steps
    print("## Category A: LLM Decision Steps (model_calls)")
    print()
    if model_durations:
        print(f"| Metric | Value | N={len(model_durations)} |")
        print("|--------|-------|------|")
        print(f"| P50 | {fmt_duration(percentile(model_durations, 50))} | |")
        print(f"| P80 | {fmt_duration(percentile(model_durations, 80))} | |")
        print(f"| P95 | {fmt_duration(percentile(model_durations, 95))} | |")
        print(f"| P99 | {fmt_duration(percentile(model_durations, 99))} | |")
        print(f"| Min | {fmt_duration(min(model_durations))} | |")
        print(f"| Max | {fmt_duration(max(model_durations))} | |")
        print(f"| Mean | {fmt_duration(statistics.mean(model_durations))} | |")
        print()

        # Breakdown by agent
        print("### By Agent")
        print()
        print("| Agent | N | P50 | P80 | P95 | P99 |")
        print("|-------|---|-----|-----|-----|-----|")
        for agent in sorted(model_durations_by_agent.keys()):
            durs = model_durations_by_agent[agent]
            if len(durs) >= 2:
                print(
                    f"| {agent} | {len(durs)} "
                    f"| {fmt_duration(percentile(durs, 50))} "
                    f"| {fmt_duration(percentile(durs, 80))} "
                    f"| {fmt_duration(percentile(durs, 95))} "
                    f"| {fmt_duration(percentile(durs, 99))} |"
                )
            else:
                print(f"| {agent} | {len(durs)} | {fmt_duration(durs[0])} | - | - | - |")
        print()
    else:
        print("No model call duration data found.\n")

    # Tool categories
    print("## Tool Call Categories")
    print()
    print("| Category | N | P50 | P80 | P95 | P99 | Min | Max |")
    print("|----------|---|-----|-----|-----|-----|-----|-----|")

    for category in sorted(tool_durations.keys()):
        durs = tool_durations[category]
        n = len(durs)
        if n >= 2:
            print(
                f"| {category} | {n} "
                f"| {fmt_duration(percentile(durs, 50))} "
                f"| {fmt_duration(percentile(durs, 80))} "
                f"| {fmt_duration(percentile(durs, 95))} "
                f"| {fmt_duration(percentile(durs, 99))} "
                f"| {fmt_duration(min(durs))} "
                f"| {fmt_duration(max(durs))} |"
            )
        elif n == 1:
            print(
                f"| {category} | {n} "
                f"| {fmt_duration(durs[0])} | - | - | - "
                f"| {fmt_duration(durs[0])} "
                f"| {fmt_duration(durs[0])} |"
            )
    print()

    # Per-tool breakdown (only tools with 3+ calls)
    print("## Per-Tool Breakdown (tools with 3+ calls)")
    print()
    print("| Tool | N | P50 | P80 | P95 | P99 | Min | Max |")
    print("|------|---|-----|-----|-----|-----|-----|-----|")

    for tool in sorted(per_tool_durations.keys()):
        durs = per_tool_durations[tool]
        if len(durs) < 3:
            continue
        print(
            f"| {tool} | {len(durs)} "
            f"| {fmt_duration(percentile(durs, 50))} "
            f"| {fmt_duration(percentile(durs, 80))} "
            f"| {fmt_duration(percentile(durs, 95))} "
            f"| {fmt_duration(percentile(durs, 99))} "
            f"| {fmt_duration(min(durs))} "
            f"| {fmt_duration(max(durs))} |"
        )
    print()

    # Projected vs Measured comparison
    print("## Projected vs Measured Comparison")
    print()
    print("| Category | Projected P50 | Measured P50 | Projected P95 | Measured P95 | N | Confidence |")
    print("|----------|--------------|-------------|--------------|-------------|---|------------|")

    projected = {
        "A: LLM Decision": ("5s", "15s"),
        "B: Single API Call": ("3s", "10s"),
        "C: Batch Tool Call": ("15s", "45s"),
        "D: Citation Network": ("5s", "15s"),
    }

    # Cat A from model calls
    if model_durations:
        n = len(model_durations)
        confidence = "High" if n >= 50 else "Medium" if n >= 20 else "Low"
        print(
            f"| A: LLM Decision | 5s "
            f"| {fmt_duration(percentile(model_durations, 50))} "
            f"| 15s "
            f"| {fmt_duration(percentile(model_durations, 95))} "
            f"| {n} | {confidence} |"
        )

    for category, (proj_p50, proj_p95) in projected.items():
        if category == "A: LLM Decision":
            continue
        durs = tool_durations.get(category, [])
        if durs:
            n = len(durs)
            confidence = "High" if n >= 50 else "Medium" if n >= 20 else "Low"
            print(
                f"| {category} | {proj_p50} "
                f"| {fmt_duration(percentile(durs, 50))} "
                f"| {proj_p95} "
                f"| {fmt_duration(percentile(durs, 95))} "
                f"| {n} | {confidence} |"
            )
        else:
            print(f"| {category} | {proj_p50} | No data | {proj_p95} | No data | 0 | None |")

    print()
    print(f"_Generated from {session_count} sessions, {len(telemetry_files)} telemetry files._")


if __name__ == "__main__":
    main()
