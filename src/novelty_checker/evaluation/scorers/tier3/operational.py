"""Tier-3 operational scorers (deterministic, telemetry-based).

These extract cost, latency, and efficiency metrics directly from
the eval trace telemetry. No ground truth needed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.novelty_checker.evaluation.scorers._base import NoveltyBaseMetric, ScorerResult


class CostPerRunMetric(NoveltyBaseMetric):
    """Extracts estimated cost from telemetry token usage.

    Score is normalized: 1.0 - (cost / max_acceptable_cost), clamped to [0, 1].
    """

    def __init__(self, threshold: float = 0.5, max_cost_usd: float = 15.0) -> None:
        super().__init__(
            metric_name="cost_per_run",
            threshold=threshold,
            scorer_type="deterministic",
        )
        self.max_cost_usd = max_cost_usd

    def _compute(
        self,
        eval_trace: dict[str, Any],
        ground_truth: dict[str, Any],
        session_path: Path,
        config: dict[str, Any] | None = None,
    ) -> ScorerResult:
        max_cost = (config or {}).get("max_cost_usd", self.max_cost_usd)

        telemetry = eval_trace.get("telemetry") or {}
        token_usage = telemetry.get("token_usage", {})
        cumulative = token_usage.get("cumulative", {})
        cost = cumulative.get("estimated_cost_usd", 0.0)

        score = max(0.0, min(1.0, 1.0 - cost / max_cost)) if max_cost > 0 else 0.0

        # Per-agent breakdown
        by_agent = token_usage.get("by_agent", {})
        by_stage = token_usage.get("by_stage", {})

        return ScorerResult(
            metric_name="cost_per_run",
            score=round(score, 4),
            confidence=1.0 if cost > 0 else 0.5,
            passed=score >= self.threshold,
            threshold=self.threshold,
            failures=[],
            evidence={
                "estimated_cost_usd": cost,
                "max_acceptable_usd": max_cost,
                "total_tokens": cumulative.get("total_tokens", 0),
                "by_agent": by_agent,
                "by_stage": by_stage,
            },
            scorer_type="deterministic",
        )


class LatencyMetric(NoveltyBaseMetric):
    """Extracts total and per-stage latency from run metadata.

    Score is normalized: 1.0 - (duration / max_duration), clamped to [0, 1].
    """

    def __init__(self, threshold: float = 0.5, max_duration_seconds: float = 3600.0) -> None:
        super().__init__(
            metric_name="latency",
            threshold=threshold,
            scorer_type="deterministic",
        )
        self.max_duration_seconds = max_duration_seconds

    def _compute(
        self,
        eval_trace: dict[str, Any],
        ground_truth: dict[str, Any],
        session_path: Path,
        config: dict[str, Any] | None = None,
    ) -> ScorerResult:
        max_dur = (config or {}).get("max_duration_seconds", self.max_duration_seconds)

        run_meta = eval_trace.get("run_metadata", {})
        total_duration = run_meta.get("total_duration_seconds", 0.0)

        score = max(0.0, min(1.0, 1.0 - total_duration / max_dur)) if max_dur > 0 else 0.0

        # Per-stage breakdown
        stage_summary = eval_trace.get("stage_summary", {})
        per_stage = {
            phase: stage.get("total_duration_seconds", 0.0)
            for phase, stage in stage_summary.items()
        }

        return ScorerResult(
            metric_name="latency",
            score=round(score, 4),
            confidence=1.0 if total_duration > 0 else 0.5,
            passed=score >= self.threshold,
            threshold=self.threshold,
            failures=[],
            evidence={
                "total_duration_seconds": total_duration,
                "max_duration_seconds": max_dur,
                "per_stage_seconds": per_stage,
            },
            scorer_type="deterministic",
        )


class TokenEfficiencyMetric(NoveltyBaseMetric):
    """Measures tokens per reference found. Lower is more efficient.

    Score is normalized: 1.0 - (tokens_per_ref / max_tokens_per_ref), clamped to [0, 1].
    """

    def __init__(
        self, threshold: float = 0.3, max_tokens_per_ref: float = 250000.0
    ) -> None:
        super().__init__(
            metric_name="token_efficiency",
            threshold=threshold,
            scorer_type="deterministic",
        )
        self.max_tokens_per_ref = max_tokens_per_ref

    def _compute(
        self,
        eval_trace: dict[str, Any],
        ground_truth: dict[str, Any],
        session_path: Path,
        config: dict[str, Any] | None = None,
    ) -> ScorerResult:
        max_tpr = (config or {}).get("max_tokens_per_ref", self.max_tokens_per_ref)

        telemetry = eval_trace.get("telemetry") or {}
        cumulative = telemetry.get("token_usage", {}).get("cumulative", {})
        total_tokens = cumulative.get("total_tokens", 0)

        # Count references found from artifacts manifest
        manifest = eval_trace.get("artifacts_manifest", [])
        has_refs = any(
            a.get("filename") == "references.md" and a.get("exists")
            for a in manifest
        )

        # Estimate ref count from telemetry or default
        ref_count = telemetry.get("total_references_found", 0)
        if ref_count == 0 and has_refs:
            ref_count = max(1, telemetry.get("total_tool_calls", 0) // 10)

        tokens_per_ref = total_tokens / ref_count if ref_count > 0 else float(total_tokens)

        score = max(0.0, min(1.0, 1.0 - tokens_per_ref / max_tpr)) if max_tpr > 0 else 0.0

        return ScorerResult(
            metric_name="token_efficiency",
            score=round(score, 4),
            confidence=0.8 if ref_count > 0 else 0.3,
            passed=score >= self.threshold,
            threshold=self.threshold,
            failures=[],
            evidence={
                "total_tokens": total_tokens,
                "references_found": ref_count,
                "tokens_per_reference": round(tokens_per_ref, 1),
                "max_tokens_per_ref": max_tpr,
            },
            scorer_type="deterministic",
        )


class ToolErrorRateMetric(NoveltyBaseMetric):
    """Measures the fraction of tool calls that failed.

    Score = 1.0 - error_rate (lower error rate = higher score).
    """

    def __init__(self, threshold: float = 0.95) -> None:
        super().__init__(
            metric_name="tool_error_rate",
            threshold=threshold,
            scorer_type="deterministic",
        )

    def _compute(
        self,
        eval_trace: dict[str, Any],
        ground_truth: dict[str, Any],
        session_path: Path,
        config: dict[str, Any] | None = None,
    ) -> ScorerResult:
        telemetry = eval_trace.get("telemetry") or {}
        total_calls = telemetry.get("total_tool_calls", 0)
        failed_calls = telemetry.get("failed_tool_calls", 0)

        if total_calls == 0:
            error_rate = 0.0
            score = 1.0
            confidence = 0.3
        else:
            error_rate = failed_calls / total_calls
            score = 1.0 - error_rate
            confidence = 1.0

        return ScorerResult(
            metric_name="tool_error_rate",
            score=round(score, 4),
            confidence=confidence,
            passed=score >= self.threshold,
            threshold=self.threshold,
            failures=[],
            evidence={
                "total_tool_calls": total_calls,
                "failed_tool_calls": failed_calls,
                "error_rate": round(error_rate, 4),
                "success_rate": telemetry.get("success_rate", 0.0),
            },
            scorer_type="deterministic",
        )


class SearchReproducibilityMetric(NoveltyBaseMetric):
    """Measures whether all search queries are fully logged with args.

    Score = entries_with_complete_args / total_entries. Should be 1.0.
    """

    def __init__(self, threshold: float = 1.0) -> None:
        super().__init__(
            metric_name="search_reproducibility",
            threshold=threshold,
            scorer_type="deterministic",
        )

    def _compute(
        self,
        eval_trace: dict[str, Any],
        ground_truth: dict[str, Any],
        session_path: Path,
        config: dict[str, Any] | None = None,
    ) -> ScorerResult:
        telemetry = eval_trace.get("telemetry") or {}
        search_queries = telemetry.get("search_queries", [])

        if not search_queries:
            return ScorerResult(
                metric_name="search_reproducibility",
                score=0.0,
                confidence=0.3,
                passed=False,
                threshold=self.threshold,
                failures=[{
                    "type": "no_search_queries",
                    "severity": "major",
                    "evidence": "No search queries found in telemetry",
                    "affected_element": "telemetry.search_queries",
                }],
                evidence={"total_queries": 0, "complete_queries": 0},
                scorer_type="deterministic",
            )

        complete = 0
        incomplete_queries: list[dict] = []
        for i, entry in enumerate(search_queries):
            args = entry.get("args")
            # args can be dict, list, or None depending on tool type
            if isinstance(args, dict):
                has_query = bool(
                    args.get("query") or args.get("queries")
                    or args.get("search_query") or args.get("search_queries")
                    # Batch unified search uses these keys
                    or args.get("semantic_queries")
                    or args.get("keyword_queries")
                    or args.get("patent_queries")
                    or args.get("npl_queries")
                    # Citation/detail lookups have publication_numbers
                    or args.get("publication_numbers")
                    or args.get("patent_number")
                )
            elif isinstance(args, list) and args:
                # Batch tools may store args as a list of query dicts/strings
                has_query = True
            else:
                has_query = False
            if has_query:
                complete += 1
            else:
                incomplete_queries.append({
                    "index": i,
                    "tool_name": entry.get("tool_name", "unknown"),
                    "agent_name": entry.get("agent_name", "unknown"),
                })

        total = len(search_queries)
        score = complete / total

        failures = []
        if incomplete_queries:
            failures.append({
                "type": "incomplete_search_args",
                "severity": "minor",
                "evidence": f"{len(incomplete_queries)} search queries missing args",
                "affected_element": "telemetry.search_queries",
            })

        return ScorerResult(
            metric_name="search_reproducibility",
            score=round(score, 4),
            confidence=1.0,
            passed=score >= self.threshold,
            threshold=self.threshold,
            failures=failures,
            evidence={
                "total_queries": total,
                "complete_queries": complete,
                "incomplete_count": len(incomplete_queries),
                "incomplete_details": incomplete_queries[:10],
            },
            scorer_type="deterministic",
        )


class ResearchRoundsMetric(NoveltyBaseMetric):
    """Tracks number of research loop iterations.

    Score: 1.0 if rounds in [2,4], 0.5 if rounds == 1 or 5, 0.0 if rounds == 0.
    Per eval_metrics_strategy.md §4.6: expected 2-5, alert if 1 or >=5.
    """

    def __init__(self, threshold: float = 0.5) -> None:
        super().__init__(
            metric_name="research_rounds",
            threshold=threshold,
            scorer_type="deterministic",
        )

    def _compute(
        self,
        eval_trace: dict[str, Any],
        ground_truth: dict[str, Any],
        session_path: Path,
        config: dict[str, Any] | None = None,
    ) -> ScorerResult:
        telemetry = eval_trace.get("telemetry") or {}
        total_rounds = telemetry.get("total_rounds", 0)

        if total_rounds == 0:
            score = 0.0
            alert = "no_rounds"
        elif total_rounds == 1:
            score = 0.5
            alert = "premature_stop"
        elif 2 <= total_rounds <= 4:
            score = 1.0
            alert = None
        elif total_rounds == 5:
            score = 0.5
            alert = "max_rounds_hit"
        else:
            score = 0.5
            alert = "exceeded_expected"

        failures: list[dict[str, Any]] = []
        if alert:
            failures.append({
                "type": f"research_rounds_{alert}",
                "severity": "major" if total_rounds == 0 else "minor",
                "evidence": f"Agent completed {total_rounds} research round(s)",
                "affected_element": "research_rounds",
            })

        return ScorerResult(
            metric_name="research_rounds",
            score=score,
            confidence=1.0 if total_rounds > 0 else 0.3,
            passed=score >= self.threshold,
            threshold=self.threshold,
            failures=failures,
            evidence={
                "total_rounds": total_rounds,
                "alert": alert,
            },
            scorer_type="deterministic",
        )


class ToolInvocationMetric(NoveltyBaseMetric):
    """Tracks total tool invocations per run.

    Score normalized: 1.0 - total / max_expected, clamped to [0, 1].
    Per eval_metrics_strategy.md §4.4: track, alert if >3x baseline.
    """

    def __init__(self, threshold: float = 0.3, max_tool_calls: int = 200) -> None:
        super().__init__(
            metric_name="tool_invocations",
            threshold=threshold,
            scorer_type="deterministic",
        )
        self.max_tool_calls = max_tool_calls

    def _compute(
        self,
        eval_trace: dict[str, Any],
        ground_truth: dict[str, Any],
        session_path: Path,
        config: dict[str, Any] | None = None,
    ) -> ScorerResult:
        max_calls = (config or {}).get("max_tool_calls", self.max_tool_calls)

        # Aggregate tool_calls_by_name across all stages
        tool_counts: dict[str, int] = {}
        stage_summary = eval_trace.get("stage_summary", {})
        for _phase, stage in stage_summary.items():
            if isinstance(stage, dict):
                for tool_name, count in stage.get("tool_calls_by_name", {}).items():
                    tool_counts[tool_name] = tool_counts.get(tool_name, 0) + count

        total_calls = sum(tool_counts.values())

        # Fallback to telemetry
        if total_calls == 0:
            telemetry = eval_trace.get("telemetry") or {}
            total_calls = telemetry.get("total_tool_calls", 0)

        score = max(0.0, min(1.0, 1.0 - total_calls / max_calls)) if max_calls > 0 else 0.0

        return ScorerResult(
            metric_name="tool_invocations",
            score=round(score, 4),
            confidence=1.0 if total_calls > 0 else 0.3,
            passed=score >= self.threshold,
            threshold=self.threshold,
            failures=[],
            evidence={
                "total_tool_calls": total_calls,
                "max_expected": max_calls,
                "tool_counts_by_name": tool_counts,
            },
            scorer_type="deterministic",
        )
