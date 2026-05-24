"""Structured telemetry for research session monitoring.

This module provides production-ready telemetry collection for the deep agent,
enabling debugging, performance analysis, and operational monitoring.

Key Features:
- Per-round metrics (duration, coverage %, new references)
- Tool call timing and success rates
- Per-agent LLM token usage tracking (input/output tokens)
- Agent execution tracing with timing spans
- Estimated cost calculation per agent
- Structured JSON output for analysis
- Automatic collection via middleware (via wrap_tool_call and wrap_model_call hooks)

Usage:
    from src.novelty_checker.observability.telemetry import (
        ResearchTelemetry,
        TelemetryMiddleware
    )

    telemetry = ResearchTelemetry(session_id="session-123")
    middleware = TelemetryMiddleware(telemetry)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, ToolMessage

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
    from langgraph.prebuilt.tool_node import ToolCallRequest
    from langgraph.runtime import Runtime
    from langgraph.types import Command

_logger = logging.getLogger(__name__)


# =============================================================================
# Model Pricing (per 1M tokens)
# =============================================================================

_DEFAULT_MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-5": {"input": 2.00, "output": 8.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "azure/gpt-5": {"input": 2.00, "output": 8.00},
    "azure/gpt-4o": {"input": 2.50, "output": 10.00},
}
_FALLBACK_PRICING: dict[str, float] = {"input": 3.00, "output": 12.00}


# =============================================================================
# Workflow Stage Constants
# =============================================================================

STAGE_SCOPING = "stage_1_scoping"
STAGE_FEATURES = "stage_2_features"
STAGE_RESEARCH = "stage_3_research"
STAGE_REPORT = "stage_4_report"
STAGE_UNKNOWN = "unknown"

STAGE_LABELS: dict[str, str] = {
    STAGE_SCOPING: "Stage 1 - Scoping",
    STAGE_FEATURES: "Stage 2 - Feature Definition",
    STAGE_RESEARCH: "Stage 3 - Research",
    STAGE_REPORT: "Stage 4 - Report",
    STAGE_UNKNOWN: "Unknown",
}

# Maps subagent name -> stage (orchestrator is handled separately)
_SUBAGENT_STAGE_MAP: dict[str, str] = {
    "patent-researcher": STAGE_RESEARCH,
    "npl-researcher": STAGE_RESEARCH,
    "semantic-researcher": STAGE_RESEARCH,
    "citation-researcher": STAGE_RESEARCH,
    "coverage-analyst": STAGE_RESEARCH,
    "keyword-precision-searcher": STAGE_RESEARCH,
    "semantic-recall-searcher": STAGE_RESEARCH,
    "structural-combo-searcher": STAGE_RESEARCH,
    "report-writer": STAGE_REPORT,
}

# Search tools whose arguments should be captured in telemetry
_SEARCH_TOOLS_FOR_ARG_CAPTURE: frozenset[str] = frozenset({
    "patent_keyword_search", "batch_patent_search",
    "npl_search", "batch_npl_search",
    "semantic_patent_search", "batch_semantic_search",
    "get_patent_citations", "batch_citation_search",
    "citation_chain_search", "batch_unified_search",
    # Derwent tools used by the patent-search and citation-search subagents
    "search_derwent_patents_fld", "search_derwent_citations",
    "aggregate_search_results",
})


def _load_model_pricing() -> dict[str, dict[str, float]]:
    """Load model pricing, optionally overridden via TOKEN_PRICING_JSON env var."""
    pricing_path = os.environ.get("TOKEN_PRICING_JSON")
    if pricing_path:
        try:
            with open(pricing_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            _logger.warning(f"Failed to load custom pricing from {pricing_path}: {e}")
    return dict(_DEFAULT_MODEL_PRICING)


def _estimate_cost(
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    pricing: dict[str, dict[str, float]],
) -> float:
    """Estimate cost in USD for a model call."""
    rates = pricing.get(model_name) or pricing.get(
        model_name.split("/")[-1]
    ) or _FALLBACK_PRICING
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000


# =============================================================================
# Data Classes for Telemetry Events
# =============================================================================

@dataclass
class ToolCallMetric:
    """Metrics for a single tool call."""
    tool_name: str
    timestamp: str
    duration_ms: float
    success: bool
    error: Optional[str] = None
    agent_name: Optional[str] = None
    args: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class RoundMetric:
    """Metrics for a research round."""
    round_number: int
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    new_references_count: int = 0
    total_references_count: int = 0
    coverage_percentage: float = 0.0
    tool_calls_count: int = 0
    failed_tool_calls: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class ModelCallMetric:
    """Metrics for a single LLM model call."""
    agent_name: str
    timestamp: str
    duration_ms: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    model_name: str = ""
    estimated_cost_usd: float = 0.0
    stage: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentTokenSummary:
    """Cumulative token usage for a specific agent."""
    agent_name: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    model_call_count: int = 0
    total_duration_ms: float = 0.0
    estimated_cost_usd: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StageTokenSummary:
    """Cumulative token usage for a workflow stage."""
    stage: str
    stage_label: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    model_call_count: int = 0
    total_duration_ms: float = 0.0
    estimated_cost_usd: float = 0.0
    by_agent: dict[str, AgentTokenSummary] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["by_agent"] = {n: u.to_dict() for n, u in self.by_agent.items()}
        return d


@dataclass
class ExecutionSpan:
    """Timing span for agent execution (trace-like)."""
    agent_name: str
    span_type: str  # "agent_lifecycle" or "model_call"
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


# =============================================================================
# Main Telemetry Class
# =============================================================================

class ResearchTelemetry:
    """Collect and persist structured telemetry for research sessions.

    This class tracks:
    - Tool call timing and success rates
    - Per-round progress metrics
    - Session-level statistics

    All metrics are persisted to JSON for post-analysis.
    """

    def __init__(
        self,
        session_id: str,
        output_path: Optional[Path] = None,
    ):
        """Initialize telemetry collector.

        Args:
            session_id: Unique session identifier
            output_path: Optional path to write telemetry JSON.
                If None, telemetry is collected in memory only.
        """
        self.session_id = session_id
        self.output_path = output_path
        self.start_time = datetime.now().isoformat()

        # Metrics storage
        self.tool_calls: list[ToolCallMetric] = []
        self.rounds: dict[int, RoundMetric] = {}
        self.current_round: Optional[int] = None

        # Token usage tracking (thread-safe for parallel subagents)
        self.model_calls: list[ModelCallMetric] = []
        self.agent_token_usage: dict[str, AgentTokenSummary] = {}
        self.stage_token_usage: dict[str, StageTokenSummary] = {}
        self._model_call_lock = threading.Lock()
        self._model_pricing = _load_model_pricing()

        # Execution trace spans
        self.execution_spans: list[ExecutionSpan] = []
        self._span_lock = threading.Lock()

        _logger.info(f"Telemetry initialized for session {session_id}")

    def start_round(self, round_number: int) -> None:
        """Mark the start of a research round.

        Args:
            round_number: The round number (1, 2, 3, ...)
        """
        self.current_round = round_number

        if round_number not in self.rounds:
            self.rounds[round_number] = RoundMetric(
                round_number=round_number,
                start_time=datetime.now().isoformat(),
            )
            _logger.debug(f"Round {round_number} started")

    def end_round(
        self,
        round_number: int,
        new_references_count: int = 0,
        total_references_count: int = 0,
        coverage_percentage: float = 0.0,
    ) -> None:
        """Mark the end of a research round with summary metrics.

        Args:
            round_number: The round number
            new_references_count: New references found this round
            total_references_count: Total references accumulated
            coverage_percentage: Current coverage percentage (0-100)
        """
        if round_number not in self.rounds:
            _logger.warning(f"end_round called for round {round_number} that wasn't started")
            return

        round_metric = self.rounds[round_number]
        round_metric.end_time = datetime.now().isoformat()

        # Calculate duration
        start = datetime.fromisoformat(round_metric.start_time)
        end = datetime.fromisoformat(round_metric.end_time)
        round_metric.duration_seconds = (end - start).total_seconds()

        # Update metrics
        round_metric.new_references_count = new_references_count
        round_metric.total_references_count = total_references_count
        round_metric.coverage_percentage = coverage_percentage

        _logger.info(
            f"Round {round_number} completed: "
            f"{new_references_count} new refs, "
            f"{coverage_percentage:.1f}% coverage, "
            f"{round_metric.duration_seconds:.1f}s"
        )

        # Persist to disk
        self._write_to_disk()

    def log_tool_call(
        self,
        tool_name: str,
        duration_ms: float,
        success: bool,
        error: Optional[str] = None,
        agent_name: Optional[str] = None,
        args: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log a tool call with timing and success information.

        Args:
            tool_name: Name of the tool that was called
            duration_ms: Duration in milliseconds
            success: Whether the tool call succeeded
            error: Optional error message if failed
            agent_name: Name of the agent that made this call
            args: Tool arguments (captured for search tools only)
        """
        metric = ToolCallMetric(
            tool_name=tool_name,
            timestamp=datetime.now().isoformat(),
            duration_ms=duration_ms,
            success=success,
            error=error,
            agent_name=agent_name,
            args=args,
        )

        self.tool_calls.append(metric)

        # Update round metrics if in a round
        if self.current_round and self.current_round in self.rounds:
            round_metric = self.rounds[self.current_round]
            round_metric.tool_calls_count += 1
            if not success:
                round_metric.failed_tool_calls += 1

        _logger.debug(
            f"Tool call: {tool_name} - "
            f"{'✅' if success else '❌'} {duration_ms:.0f}ms"
        )

    def log_model_call(
        self,
        agent_name: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        duration_ms: float,
        model_name: str = "",
        stage: str = "",
    ) -> None:
        """Log an LLM model call with token usage.

        Thread-safe: subagents run in parallel and share this instance.

        Args:
            agent_name: Name of the agent making the call.
            input_tokens: Number of input (prompt) tokens.
            output_tokens: Number of output (completion) tokens.
            total_tokens: Total tokens used.
            duration_ms: Duration of the model call in milliseconds.
            model_name: Model identifier (e.g. "azure/gpt-5").
            stage: Workflow stage constant (e.g. STAGE_RESEARCH).
        """
        cost = _estimate_cost(model_name, input_tokens, output_tokens, self._model_pricing)

        metric = ModelCallMetric(
            agent_name=agent_name,
            timestamp=datetime.now().isoformat(),
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            model_name=model_name,
            estimated_cost_usd=cost,
            stage=stage,
        )

        with self._model_call_lock:
            self.model_calls.append(metric)

            # Per-agent accumulation
            if agent_name not in self.agent_token_usage:
                self.agent_token_usage[agent_name] = AgentTokenSummary(agent_name=agent_name)
            usage = self.agent_token_usage[agent_name]
            usage.total_input_tokens += input_tokens
            usage.total_output_tokens += output_tokens
            usage.total_tokens += total_tokens
            usage.model_call_count += 1
            usage.total_duration_ms += duration_ms
            usage.estimated_cost_usd += cost

            # Per-stage accumulation
            if stage:
                if stage not in self.stage_token_usage:
                    self.stage_token_usage[stage] = StageTokenSummary(
                        stage=stage,
                        stage_label=STAGE_LABELS.get(stage, stage),
                    )
                stage_usage = self.stage_token_usage[stage]
                stage_usage.total_input_tokens += input_tokens
                stage_usage.total_output_tokens += output_tokens
                stage_usage.total_tokens += total_tokens
                stage_usage.model_call_count += 1
                stage_usage.total_duration_ms += duration_ms
                stage_usage.estimated_cost_usd += cost

                # Per-agent within stage
                if agent_name not in stage_usage.by_agent:
                    stage_usage.by_agent[agent_name] = AgentTokenSummary(
                        agent_name=agent_name,
                    )
                agent_in_stage = stage_usage.by_agent[agent_name]
                agent_in_stage.total_input_tokens += input_tokens
                agent_in_stage.total_output_tokens += output_tokens
                agent_in_stage.total_tokens += total_tokens
                agent_in_stage.model_call_count += 1
                agent_in_stage.total_duration_ms += duration_ms
                agent_in_stage.estimated_cost_usd += cost

        _logger.debug(
            f"Model call [{agent_name}] [{stage or 'no-stage'}]: "
            f"{input_tokens:,} in / {output_tokens:,} out "
            f"({duration_ms:.0f}ms, ${cost:.4f})"
        )

    def start_span(self, agent_name: str, span_type: str) -> ExecutionSpan:
        """Start a new execution span.

        Args:
            agent_name: Agent that owns this span.
            span_type: "agent_lifecycle" or "model_call".

        Returns:
            The created span (to be passed to end_span later).
        """
        span = ExecutionSpan(
            agent_name=agent_name,
            span_type=span_type,
            start_time=datetime.now().isoformat(),
        )
        with self._span_lock:
            self.execution_spans.append(span)
        return span

    def end_span(self, span: ExecutionSpan) -> None:
        """Mark the end of an execution span."""
        span.end_time = datetime.now().isoformat()
        start = datetime.fromisoformat(span.start_time)
        end = datetime.fromisoformat(span.end_time)
        span.duration_seconds = (end - start).total_seconds()

    def get_token_summary(self) -> dict[str, Any]:
        """Get per-agent and per-stage token breakdown and cumulative totals."""
        with self._model_call_lock:
            by_agent = {
                name: usage.to_dict()
                for name, usage in self.agent_token_usage.items()
            }
            by_stage = {
                stage: usage.to_dict()
                for stage, usage in sorted(
                    self.stage_token_usage.items(),
                    key=lambda x: x[0],
                )
            }
            cumulative_input = sum(u.total_input_tokens for u in self.agent_token_usage.values())
            cumulative_output = sum(u.total_output_tokens for u in self.agent_token_usage.values())
            cumulative_cost = sum(u.estimated_cost_usd for u in self.agent_token_usage.values())
            cumulative_calls = sum(u.model_call_count for u in self.agent_token_usage.values())

        return {
            "by_agent": by_agent,
            "by_stage": by_stage,
            "cumulative": {
                "total_input_tokens": cumulative_input,
                "total_output_tokens": cumulative_output,
                "total_tokens": cumulative_input + cumulative_output,
                "model_call_count": cumulative_calls,
                "estimated_cost_usd": cumulative_cost,
            },
        }

    def log_session_summary(self) -> None:
        """Log a human-readable session summary to the logger."""
        token_summary = self.get_token_summary()
        cumulative = token_summary["cumulative"]

        if cumulative["model_call_count"] == 0:
            return

        lines = ["", "=== SESSION TOKEN USAGE (by Stage) ==="]

        # Stage-based breakdown (sorted by stage key for consistent ordering)
        with self._model_call_lock:
            sorted_stages = sorted(
                self.stage_token_usage.items(),
                key=lambda x: x[0],
            )

        for _stage_key, stage_usage in sorted_stages:
            duration_s = stage_usage.total_duration_ms / 1000
            lines.append(
                f"  {stage_usage.stage_label:<30s} "
                f"{stage_usage.total_input_tokens:>8,} in / {stage_usage.total_output_tokens:>7,} out  "
                f"(${stage_usage.estimated_cost_usd:.3f})  "
                f"{stage_usage.model_call_count} calls, {duration_s:.1f}s"
            )
            # Per-agent breakdown within stage (indented)
            for agent_usage in sorted(
                stage_usage.by_agent.values(),
                key=lambda u: u.total_tokens,
                reverse=True,
            ):
                lines.append(
                    f"    {agent_usage.agent_name:<28s} "
                    f"{agent_usage.total_input_tokens:>8,} in / {agent_usage.total_output_tokens:>7,} out  "
                    f"(${agent_usage.estimated_cost_usd:.3f})"
                )

        # Fallback: show per-agent if no stage data available
        if not sorted_stages:
            with self._model_call_lock:
                sorted_agents = sorted(
                    self.agent_token_usage.values(),
                    key=lambda u: u.total_tokens,
                    reverse=True,
                )
            for usage in sorted_agents:
                duration_s = usage.total_duration_ms / 1000
                lines.append(
                    f"  {usage.agent_name:<25s} "
                    f"{usage.total_input_tokens:>8,} in / {usage.total_output_tokens:>7,} out  "
                    f"(${usage.estimated_cost_usd:.3f})  "
                    f"{usage.model_call_count} calls, {duration_s:.1f}s"
                )

        lines.append("  " + "-" * 75)
        lines.append(
            f"  {'TOTAL':<30s} "
            f"{cumulative['total_input_tokens']:>8,} in / {cumulative['total_output_tokens']:>7,} out  "
            f"(${cumulative['estimated_cost_usd']:.3f})  "
            f"{cumulative['model_call_count']} calls"
        )
        lines.append("=" * 42)

        _logger.info("\n".join(lines))

    def get_search_queries(self) -> list[dict[str, Any]]:
        """Get all captured search queries with their agent attribution.

        Returns:
            List of dicts with: agent_name, tool_name, args, timestamp,
            success, duration_ms.
        """
        return [
            {
                "agent_name": tc.agent_name,
                "tool_name": tc.tool_name,
                "args": tc.args,
                "timestamp": tc.timestamp,
                "success": tc.success,
                "duration_ms": tc.duration_ms,
            }
            for tc in self.tool_calls
            if tc.args is not None
        ]

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all collected telemetry.

        Returns:
            Dictionary with session summary statistics
        """
        # Close any open round that wasn't ended
        if self.current_round and self.current_round in self.rounds:
            r = self.rounds[self.current_round]
            if r.end_time is None:
                r.end_time = datetime.now().isoformat()
                start = datetime.fromisoformat(r.start_time)
                end = datetime.fromisoformat(r.end_time)
                r.duration_seconds = (end - start).total_seconds()

        total_tool_calls = len(self.tool_calls)
        failed_calls = sum(1 for tc in self.tool_calls if not tc.success)

        # Calculate average tool call duration
        if total_tool_calls > 0:
            avg_duration = sum(tc.duration_ms for tc in self.tool_calls) / total_tool_calls
        else:
            avg_duration = 0.0

        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "total_rounds": len(self.rounds),
            "total_tool_calls": total_tool_calls,
            "failed_tool_calls": failed_calls,
            "success_rate": (total_tool_calls - failed_calls) / total_tool_calls if total_tool_calls > 0 else 0.0,
            "avg_tool_duration_ms": avg_duration,
            "rounds": [r.to_dict() for r in self.rounds.values()],
            "token_usage": self.get_token_summary(),
            "search_queries": self.get_search_queries(),
        }

    def _write_to_disk(self) -> None:
        """Write telemetry to disk as JSON."""
        if not self.output_path:
            return

        # Skip sync writes when running in an async event loop (LangGraph Studio).
        # The async hooks (awrap_tool_call, etc.) handle writes via asyncio.to_thread.
        try:
            asyncio.get_running_loop()
            return  # async context — let async hooks handle the write
        except RuntimeError:
            pass  # no event loop — proceed with sync write (CLI mode)

        try:
            data = {
                "session_id": self.session_id,
                "start_time": self.start_time,
                "rounds": [r.to_dict() for r in self.rounds.values()],
                "tool_calls": [tc.to_dict() for tc in self.tool_calls],
                "model_calls": [mc.to_dict() for mc in self.model_calls],
                "token_usage": self.get_token_summary(),
                "execution_trace": [s.to_dict() for s in self.execution_spans],
                "summary": self.get_summary(),
            }

            self.output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            _logger.debug(f"Telemetry written to {self.output_path}")

        except Exception as e:
            _logger.error(f"Failed to write telemetry: {e}")


# =============================================================================
# Stage Detection Helpers
# =============================================================================

# Markers reused from AutonomousResearchMiddleware / FeatureConfirmationMiddleware
_FEATURE_PRESENTED_MARKERS = ("Feature Matrix", "CONFIRMATION REQUIRED", "Stage 2 Gate")
_CONFIRMATION_MARKERS = ("confirm",)


def _get_msg_content(msg: Any) -> str:
    """Extract string content from a message object."""
    content = getattr(msg, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content)


def _file_exists_on_backend(backend: Any, path: str) -> bool:
    """Check if a file exists on the backend filesystem.

    FilesystemBackend.read() returns an error string (not exception)
    for missing files, so we check for that.
    """
    try:
        content = backend.read(path)
        return bool(content and content.strip() and not content.startswith("Error"))
    except Exception:
        return False


def _features_confirmed_in_messages(messages: list[Any]) -> bool:
    """Check if user confirmed features after Feature Matrix was presented."""
    feature_presented = False
    for msg in messages:
        msg_type = getattr(msg, "type", None)
        content = _get_msg_content(msg)
        if msg_type in ("ai", "assistant"):
            if any(marker in content for marker in _FEATURE_PRESENTED_MARKERS):
                feature_presented = True
        elif msg_type == "human" and feature_presented:
            if any(marker in content.lower() for marker in _CONFIRMATION_MARKERS):
                return True
    return False


def _report_writer_delegated(messages: list[Any]) -> bool:
    """Check if report-writer was delegated in recent messages."""
    # Scan last 30 messages in reverse for efficiency
    for msg in reversed(messages[-30:]):
        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            continue
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            if tc.get("name") != "task":
                continue
            args = tc.get("args", {})
            subagent = str(args.get("subagent_type", "")).lower()
            desc = str(args.get("description", "")).lower()
            if "report" in subagent or "report-writer" in subagent:
                return True
    return False


def _resolve_orchestrator_stage(backend: Any, messages: list[Any]) -> str:
    """Determine which workflow stage the orchestrator is currently in.

    Heuristic (checked in priority order):
    1. /final_report.md exists OR report-writer delegated -> Stage 4 (Report)
    2. /features.md exists + user confirmed (Gate 2) -> Stage 3 (Research)
    3. /scope.md exists -> Stage 2 (Feature Definition)
    4. Otherwise -> Stage 1 (Scoping)
    """
    # Check for report phase first (highest priority)
    if _file_exists_on_backend(backend, "/final_report.md"):
        return STAGE_REPORT
    if _report_writer_delegated(messages):
        return STAGE_REPORT

    # Check for post-Gate-2 (research phase)
    if _file_exists_on_backend(backend, "/features.md"):
        if _features_confirmed_in_messages(messages):
            return STAGE_RESEARCH

        # Features file exists but not yet confirmed -> still Stage 2
        return STAGE_FEATURES

    # Check for post-scope
    if _file_exists_on_backend(backend, "/scope.md"):
        return STAGE_FEATURES

    return STAGE_SCOPING


# =============================================================================
# Telemetry Middleware
# =============================================================================

class TelemetryMiddleware(AgentMiddleware):
    """Middleware for automatic telemetry collection.

    Supports two modes:
    - **Static mode** (CLI/single-session): provide a single ``telemetry`` instance.
    - **Factory mode** (LangGraph Studio): provide a ``telemetry_factory`` callable
      that creates per-thread ``ResearchTelemetry`` instances.

    Usage:
        # Static mode
        telemetry = ResearchTelemetry(session_id="session-123")
        middleware = TelemetryMiddleware(telemetry=telemetry)

        # Factory mode (per-thread)
        middleware = TelemetryMiddleware(
            telemetry_factory=lambda tid: ResearchTelemetry(
                session_id=tid,
                output_path=sessions_dir / tid / "telemetry.json",
            )
        )
    """

    def __init__(
        self,
        telemetry: ResearchTelemetry | None = None,
        telemetry_factory: Callable[[str], ResearchTelemetry] | None = None,
        agent_name: str = "orchestrator",
        backend: Any = None,
    ):
        """Initialize middleware.

        Provide exactly one of ``telemetry`` or ``telemetry_factory``.

        Args:
            telemetry: Static telemetry instance (CLI/single-session).
            telemetry_factory: Callable that takes thread_id and returns a
                ResearchTelemetry instance. Used for per-thread isolation.
            agent_name: Logical name of the agent this middleware is attached to.
                Used to attribute token usage to the correct agent.
            backend: Optional FilesystemBackend or BackendFactory callable.
                When provided, enables stage-based token attribution.
                When None, stage detection is disabled (backward compatible).
        """
        if telemetry is None and telemetry_factory is None:
            raise ValueError("Provide either telemetry or telemetry_factory")
        self._static_telemetry = telemetry
        self._telemetry_factory = telemetry_factory
        self._agent_name = agent_name
        self._backend = backend
        self._thread_telemetry: dict[str, ResearchTelemetry] = {}
        self._lock = threading.Lock()
        # Track active agent lifecycle spans for before_agent/after_agent
        self._active_agent_spans: dict[str, ExecutionSpan] = {}
        self._spans_lock = threading.Lock()

    def _get_telemetry(self, runtime: Any) -> ResearchTelemetry:
        """Resolve the telemetry instance for the current thread.

        In static mode, always returns the same instance.
        In factory mode, creates/caches a per-thread instance.
        """
        if self._static_telemetry is not None:
            return self._static_telemetry

        from src.novelty_checker.backend_factory import extract_thread_id
        thread_id = extract_thread_id(runtime) or "__default__"
        with self._lock:
            if thread_id not in self._thread_telemetry:
                if self._telemetry_factory:
                    self._thread_telemetry[thread_id] = self._telemetry_factory(thread_id)
                else:
                    self._thread_telemetry[thread_id] = ResearchTelemetry(
                        session_id=thread_id,
                    )
            return self._thread_telemetry[thread_id]

    def _get_backend(self, runtime: Any) -> Any | None:
        """Resolve backend from instance or factory."""
        if self._backend is None:
            return None
        if callable(self._backend):
            return self._backend(runtime)
        return self._backend

    def _persist_subagent_trace(self, state: Any, runtime: Any) -> None:
        """Write subagent message history to filesystem for trace analysis.

        Skips the orchestrator (its messages are the main conversation).
        Only captures subagent conversations so internal reasoning steps,
        tool call sequences, and LLM responses are preserved.
        """
        agent_name = self._agent_name
        if agent_name == "orchestrator":
            return

        backend = self._get_backend(runtime)
        if backend is None:
            return

        messages = state.get("messages", [])
        if not messages:
            return

        trace = []
        for msg in messages:
            entry: dict[str, Any] = {
                "type": type(msg).__name__,
                "content": msg.content if hasattr(msg, "content") else str(msg),
            }
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                entry["tool_calls"] = [
                    {"name": tc.get("name"), "args": tc.get("args")}
                    for tc in msg.tool_calls
                ]
            if hasattr(msg, "tool_call_id") and msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            trace.append(entry)

        backend.write(
            f"/traces/{agent_name}_messages.json",
            json.dumps(trace, indent=2, ensure_ascii=False),
        )

    def _resolve_stage(self, request: Any) -> str:
        """Determine the current workflow stage for this model call.

        Subagents are mapped by name. For the orchestrator, uses filesystem
        artifacts and message history to detect the current stage.

        Returns:
            One of the STAGE_* constants, or empty string if detection is
            disabled (no backend provided).
        """
        agent_name = self._agent_name

        # Subagents: direct lookup by name
        if agent_name != "orchestrator":
            return _SUBAGENT_STAGE_MAP.get(agent_name, STAGE_UNKNOWN)

        # Orchestrator: needs backend for filesystem-based detection
        try:
            backend = self._get_backend(request.runtime)
        except Exception:
            backend = None
        if backend is None:
            return ""

        messages = getattr(request, "messages", [])
        return _resolve_orchestrator_stage(backend, messages)

    # -----------------------------------------------------------------
    # Agent lifecycle hooks (execution tracing)
    # -----------------------------------------------------------------

    def before_agent(
        self, state: Any, runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Record the start of an agent execution lifecycle."""
        from src.novelty_checker.backend_factory import extract_thread_id

        agent_name = self._agent_name
        telemetry = self._get_telemetry(runtime)

        thread_id = extract_thread_id(runtime) or "__default__"
        span_key = f"{thread_id}:{agent_name}"

        # Close any previous span for this agent before opening a new one.
        # Orchestrator's before_agent fires once per stage re-entry; without
        # this we leak an open span each time.
        with self._spans_lock:
            prior = self._active_agent_spans.pop(span_key, None)
        if prior is not None:
            telemetry.end_span(prior)

        span = telemetry.start_span(agent_name, "agent_lifecycle")
        with self._spans_lock:
            self._active_agent_spans[span_key] = span

        _logger.info(f"Agent '{agent_name}' started")
        return None

    async def abefore_agent(
        self, state: Any, runtime: Runtime,
    ) -> dict[str, Any] | None:
        return self.before_agent(state, runtime)

    def after_agent(
        self, state: Any, runtime: Runtime,
    ) -> dict[str, Any] | None:
        """Record end of agent execution and log summary."""
        from src.novelty_checker.backend_factory import extract_thread_id

        agent_name = self._agent_name
        telemetry = self._get_telemetry(runtime)

        thread_id = extract_thread_id(runtime) or "__default__"
        span_key = f"{thread_id}:{agent_name}"
        with self._spans_lock:
            span = self._active_agent_spans.pop(span_key, None)

        if span:
            telemetry.end_span(span)

        usage = telemetry.agent_token_usage.get(agent_name)
        if usage:
            duration_s = usage.total_duration_ms / 1000
            _logger.info(
                f"Agent '{agent_name}' completed: "
                f"{usage.model_call_count} LLM calls, "
                f"{usage.total_input_tokens:,} input / {usage.total_output_tokens:,} output tokens, "
                f"${usage.estimated_cost_usd:.3f}, {duration_s:.1f}s LLM time"
            )

        # Print full session summary when orchestrator finishes
        if agent_name == "orchestrator":
            # Close any orphaned open spans (subagents that never emitted
            # after_agent). Prevents end_time=null in the trace.
            with self._spans_lock:
                orphans = list(self._active_agent_spans.values())
                self._active_agent_spans.clear()
            for orphan in orphans:
                telemetry.end_span(orphan)
            telemetry.log_session_summary()

        # Persist subagent message history for trace analysis
        try:
            self._persist_subagent_trace(state, runtime)
        except Exception as e:
            _logger.debug(f"Failed to persist subagent trace for '{agent_name}': {e}")

        telemetry._write_to_disk()
        return None

    async def aafter_agent(
        self, state: Any, runtime: Runtime,
    ) -> dict[str, Any] | None:
        return self.after_agent(state, runtime)

    # -----------------------------------------------------------------
    # Model call hooks (token usage tracking)
    # -----------------------------------------------------------------

    def _extract_and_log_tokens(
        self,
        response: ModelCallResult,
        agent_name: str,
        duration_ms: float,
        telemetry: ResearchTelemetry,
        stage: str = "",
    ) -> None:
        """Extract usage_metadata from model response and log token metrics."""
        messages: list[Any]
        if isinstance(response, AIMessage):
            messages = [response]
        else:
            messages = getattr(response, "result", [])

        for msg in messages:
            if not isinstance(msg, AIMessage):
                continue
            usage = getattr(msg, "usage_metadata", None)
            if usage is None:
                continue

            input_tokens = usage.get("input_tokens", 0) if isinstance(usage, dict) else getattr(usage, "input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0) if isinstance(usage, dict) else getattr(usage, "output_tokens", 0)
            total_tokens = usage.get("total_tokens", 0) if isinstance(usage, dict) else getattr(usage, "total_tokens", 0)
            model_name = getattr(msg, "response_metadata", {}).get("model_name", "") if hasattr(msg, "response_metadata") else ""

            telemetry.log_model_call(
                agent_name=agent_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                duration_ms=duration_ms,
                model_name=model_name,
                stage=stage,
            )
            break  # Only log from the first AIMessage with usage

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        """Intercept LLM calls to extract token usage and timing."""
        agent_name = self._agent_name
        telemetry = self._get_telemetry(request.runtime)
        stage = self._resolve_stage(request)

        _logger.debug(f"Model call starting for agent '{agent_name}' [{stage or 'no-stage'}]")

        start = time.perf_counter()
        try:
            response = handler(request)
            duration_ms = (time.perf_counter() - start) * 1000
            self._extract_and_log_tokens(response, agent_name, duration_ms, telemetry, stage=stage)
            telemetry._write_to_disk()
            return response
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            _logger.debug(
                f"Model call failed for agent '{agent_name}' after {duration_ms:.0f}ms"
            )
            raise

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        """Async version: intercept LLM calls to extract token usage and timing."""
        agent_name = self._agent_name
        telemetry = self._get_telemetry(request.runtime)
        stage = self._resolve_stage(request)

        start = time.perf_counter()
        try:
            response = await handler(request)
            duration_ms = (time.perf_counter() - start) * 1000
            self._extract_and_log_tokens(response, agent_name, duration_ms, telemetry, stage=stage)
            await asyncio.to_thread(telemetry._write_to_disk)
            return response
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            _logger.debug(
                f"Model call failed for agent '{agent_name}' after {duration_ms:.0f}ms"
            )
            raise

    # -----------------------------------------------------------------
    # Tool call hooks (existing)
    # -----------------------------------------------------------------

    def _log_from_result(
        self,
        tool_name: str,
        result: ToolMessage | Command[Any] | Any,
        duration_ms: float,
        runtime: Any,
        agent_name: Optional[str] = None,
        args: Optional[dict[str, Any]] = None,
    ) -> None:
        """Extract success/error from tool result and log metrics.

        Args:
            tool_name: Name of the tool that was called
            result: Result returned by the tool
            duration_ms: Duration of the tool call in milliseconds
            runtime: Runtime context for thread-aware telemetry resolution
            agent_name: Name of the agent that made this call
            args: Tool arguments (captured for search tools only)
        """
        success = True
        error = None

        content = result.content if isinstance(result, ToolMessage) else str(result)
        if isinstance(content, str):
            if content.startswith("\u274c") or content.startswith("\u26a0\ufe0f"):
                success = False
                error = content[:100]
        elif isinstance(content, dict) and "error" in content:
            success = False
            error = str(content.get("error", ""))[:100]

        telemetry = self._get_telemetry(runtime)
        telemetry.log_tool_call(
            tool_name=tool_name,
            duration_ms=duration_ms,
            success=success,
            error=error,
            agent_name=agent_name,
            args=args,
        )

    def _maybe_record_round(
        self,
        tool_name: str,
        request: ToolCallRequest,
        result: ToolMessage | Command[Any],
    ) -> None:
        """Open/close a research round from any signal we can detect.

        Two paths fire a round event:

        1. ``save_round_findings`` — orchestrator path, carries
           ``round_number`` + ``references`` in args.
        2. ``write_file`` / ``edit_file`` targeting ``findings/*round_<N>.md``
           — subagent-direct path. Subagents bypass ``save_round_findings``
           and write their round markdown files directly, so the
           orchestrator never triggers (1). We extract ``N`` from the
           filename so round 2+ still shows up in telemetry.

        ``start_round`` / ``end_round`` are both idempotent, so double-
        firing from both paths on the same round is harmless.
        """
        # Skip failed tool calls either way.
        content = result.content if isinstance(result, ToolMessage) else str(result)
        if isinstance(content, str) and (
            content.startswith("\u274c") or content.startswith("\u26a0\ufe0f")
        ):
            return

        args = request.tool_call.get("args") or {}

        round_number: int | None = None
        ref_count = 0

        if tool_name == "save_round_findings":
            round_number = args.get("round_number")
            ref_count = len(args.get("references") or [])
        elif tool_name in ("write_file", "edit_file"):
            path = args.get("file_path", "") or args.get("path", "")
            match = re.search(r"round_(\d+)\.md$", path)
            if match:
                round_number = int(match.group(1))

        if not isinstance(round_number, int) or round_number <= 0:
            return

        telemetry = self._get_telemetry(request.runtime)
        telemetry.start_round(round_number)
        telemetry.end_round(
            round_number,
            new_references_count=ref_count,
            total_references_count=ref_count,
        )

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        """Log tool execution metrics via wrap_tool_call hook.

        Args:
            request: Tool call request with call dict, tool, state, and runtime.
            handler: Callable to execute the tool.

        Returns:
            Original tool result unchanged.
        """
        tool_name = request.tool_call.get("name", "unknown")
        if tool_name == "think_tool" and self._agent_name == "orchestrator":
            telemetry = self._get_telemetry(request.runtime)
            current = telemetry.current_round or 0
            if current > 0:
                telemetry.end_round(current)
            telemetry.start_round(current + 1)


        captured_args = (
            request.tool_call.get("args")
            if tool_name in _SEARCH_TOOLS_FOR_ARG_CAPTURE
            else None
        )
        start = time.perf_counter()

        try:
            result = handler(request)
            duration_ms = (time.perf_counter() - start) * 1000
            self._log_from_result(
                tool_name, result, duration_ms, request.runtime,
                agent_name=self._agent_name, args=captured_args,
            )
            self._maybe_record_round(tool_name, request, result)
            self._get_telemetry(request.runtime)._write_to_disk()
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            telemetry = self._get_telemetry(request.runtime)
            telemetry.log_tool_call(
                tool_name=tool_name,
                duration_ms=duration_ms,
                success=False,
                error=str(e)[:100],
                agent_name=self._agent_name,
                args=captured_args,
            )
            telemetry._write_to_disk()
            raise

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        """Async version: log tool execution metrics.

        Args:
            request: Tool call request with call dict, tool, state, and runtime.
            handler: Async callable to execute the tool.

        Returns:
            Original tool result unchanged.
        """
        tool_name = request.tool_call.get("name", "unknown")
        if tool_name == "think_tool" and self._agent_name == "orchestrator":
            telemetry = self._get_telemetry(request.runtime)
            current = telemetry.current_round or 0
            if current > 0:
                telemetry.end_round(current)
            telemetry.start_round(current + 1)

        captured_args = (
            request.tool_call.get("args")
            if tool_name in _SEARCH_TOOLS_FOR_ARG_CAPTURE
            else None
        )
        start = time.perf_counter()

        try:
            result = await handler(request)
            duration_ms = (time.perf_counter() - start) * 1000
            self._log_from_result(
                tool_name, result, duration_ms, request.runtime,
                agent_name=self._agent_name, args=captured_args,
            )
            self._maybe_record_round(tool_name, request, result)
            await asyncio.to_thread(self._get_telemetry(request.runtime)._write_to_disk)
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            telemetry = self._get_telemetry(request.runtime)
            telemetry.log_tool_call(
                tool_name=tool_name,
                duration_ms=duration_ms,
                success=False,
                error=str(e)[:100],
                agent_name=self._agent_name,
                args=captured_args,
            )
            await asyncio.to_thread(telemetry._write_to_disk)
            raise
