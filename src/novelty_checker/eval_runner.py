"""End-to-end auto-approval runner for the Novelty Checker agent.

Runs the full novelty check pipeline without human interaction by
automatically confirming at Gate 1 (Scope) and Gate 2 (Features).
Intended for testing and evaluation.

Updates from original:
- Added ToolCallRecord dataclass (full tool call details with args + output)
- Added TokenUsage dataclass (per-turn token counts)
- Added _extract_tool_call_details() replacing _extract_tool_calls()
- Added _extract_token_usage() for per-turn token tracking
- Added _extract_model_name() for automatic model detection
- Updated TurnRecord with: timestamp, ai_content_full, tool_call_details,
  token_usage, gate_event (backward compatible - old fields preserved)
- Updated EvalRunResult with model_name field

Usage:
    from src.novelty_checker.eval_runner import run_novelty_check_e2e, RunPhase

    result = run_novelty_check_e2e(
        idea="A dual-worm gear transmission for smartphone cameras...",
        max_turns=25,
        progress_callback=lambda turn, phase, gate, preview: print(
            f"[Turn {turn}] {phase.name} | {preview[:80]}..."
        ),
    )

    if result.final_phase == RunPhase.COMPLETED:
        print(result.final_report[:500])
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

if TYPE_CHECKING:
    from collections.abc import Callable

    from langchain_core.language_models import BaseChatModel

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gate markers (mirrored from middleware constants)
# ---------------------------------------------------------------------------
_GATE1_MARKERS = ("Scope Summary",)
_GATE2_MARKERS = ("Feature Matrix", "CONFIRMATION REQUIRED", "Stage 2 Gate")
_DONE_MARKERS = ("Final Report", "## 1.", "## Executive Summary")

# Minimum bytes for a chat-extracted final report to be considered a real
# synthesis (not just a short acknowledgement). The real deep-agent report
# runs ~30K chars; 2K is a conservative floor.
_MIN_AUTOSAVED_REPORT_BYTES = 2000


def _autosave_final_report(session_path: "Path", messages: list[BaseMessage]) -> bool:
    """Safety net: persist a chat-only final report to final_report.md.

    The deep agent sometimes produces the full 11-section report as chat
    content but forgets to call write_file('/final_report.md', ...). The
    file-based scorers then see an empty session artifact and score 0 for
    report_section_completeness. This helper runs after the main loop:
    if final_report.md is missing/tiny and the last AIMessage contains
    DONE markers plus substantial content, write that content to the
    expected path so scoring still works.

    Returns True if a rescue write happened, False otherwise. Callers
    should log a warning when True so the orchestration miss is visible.
    """
    report_path = session_path / "final_report.md"
    if report_path.exists() and report_path.stat().st_size >= _MIN_AUTOSAVED_REPORT_BYTES:
        return False

    for msg in reversed(messages):
        if not isinstance(msg, AIMessage):
            continue
        content = msg.content
        if isinstance(content, list):
            content = " ".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
        if not isinstance(content, str) or len(content) < _MIN_AUTOSAVED_REPORT_BYTES:
            continue
        if not any(marker in content for marker in _DONE_MARKERS):
            continue
        report_path.write_text(content, encoding="utf-8")
        return True

    return False

_DEFAULT_AUTO_SCOPE_PREFIX = (
    "Please check the novelty of this invention. "
    "IMPORTANT: Do NOT ask clarifying questions during scoping. "
    "Use reasonable defaults and your best judgment for any ambiguous aspects. "
    "Proceed directly to presenting the Scope Summary for confirmation.\n\n"
    "Here is the invention:\n\n"
)

# Truncation limits
_AI_CONTENT_PREVIEW_LIMIT = 500
_TOOL_OUTPUT_PREVIEW_LIMIT = 1000


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class GateType(Enum):
    """Which confirmation gate was detected."""
    SCOPE = auto()
    FEATURES = auto()


class RunPhase(Enum):
    """Current phase of the end-to-end run."""
    INITIAL = auto()
    AWAITING_SCOPE_CONFIRM = auto()
    AWAITING_FEATURE_CONFIRM = auto()
    AUTONOMOUS_RESEARCH = auto()
    COMPLETED = auto()
    ERROR = auto()


# ---------------------------------------------------------------------------
# Enriched data classes for trace capture
# ---------------------------------------------------------------------------

@dataclass
class ToolCallRecord:
    """Enriched record of a single tool call with args and output.

    Captures the full tool call details needed for failure localization:
    what was asked (args), what came back (output_preview), and whether
    it succeeded.
    """
    tool_call_id: str
    name: str
    args: dict[str, Any]
    output_preview: str
    output_size_chars: int
    success: bool
    error: str | None = None
    duration_ms: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TokenUsage:
    """Token usage for a single LLM call.

    Extracted from AIMessage.response_metadata["token_usage"].
    Azure OpenAI via LiteLLM returns: prompt_tokens, completion_tokens,
    total_tokens.
    """
    input_tokens: int
    output_tokens: int
    total_tokens: int

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------

@dataclass
class TurnRecord:
    """Record of a single invoke() turn.
    """
    turn_number: int
    phase: RunPhase
    injected_message: str | None
    ai_content_preview: str
    gate_detected: GateType | None
    tool_calls: list[str]
    duration_seconds: float
    message_count: int
    timestamp: str | None = None                  # ISO wall-clock time
    ai_content_full: str | None = None            # Full AI response
    tool_call_details: list[ToolCallRecord] = field(default_factory=list)
    token_usage: TokenUsage | None = None
    gate_event: dict[str, Any] | None = None      # Gate proposal + response


@dataclass
class EvalRunResult:
    """Comprehensive result from an end-to-end evaluation run."""
    session_id: str
    session_path: Path
    thread_id: str
    total_turns: int
    total_duration_seconds: float
    final_phase: RunPhase
    turns: list[TurnRecord]
    messages: list[BaseMessage]
    final_report: str | None
    artifacts: dict[str, str]
    error: str | None = None
    coverage_result: Any | None = None
    model_name: str | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_last_ai_content(messages: list[BaseMessage]) -> str:
    """Extract string content of the last AIMessage."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            content = msg.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return " ".join(
                    item.get("text", "") if isinstance(item, dict) else str(item)
                    for item in content
                )
    return ""


def _detect_gate(ai_content: str, phase: RunPhase) -> GateType | None:
    """Detect which gate the AI is presenting, if any."""
    if phase == RunPhase.AUTONOMOUS_RESEARCH:
        return None
    if any(marker in ai_content for marker in _GATE2_MARKERS):
        return GateType.FEATURES
    if phase in (RunPhase.INITIAL, RunPhase.AWAITING_SCOPE_CONFIRM):
        if any(marker in ai_content for marker in _GATE1_MARKERS):
            return GateType.SCOPE
    return None


def _detect_completion(ai_content: str, session_path: Path) -> bool:
    """Detect if the agent has delivered the final report."""
    if any(marker in ai_content for marker in _DONE_MARKERS):
        return True
    report_path = session_path / "final_report.md"
    if report_path.exists() and report_path.stat().st_size > 100:
        return True
    return False


def _is_clarifying_question(ai_content: str) -> bool:
    """Heuristic: detect if the AI is asking a clarifying question."""
    lower = ai_content.lower()
    indicators = (
        "could you", "can you", "would you", "please clarify",
        "please provide", "what is", "what are", "how does",
        "could you elaborate", "more details", "more information",
    )
    has_question = "?" in ai_content
    has_indicator = any(ind in lower for ind in indicators)
    has_gate = any(m in ai_content for m in (*_GATE1_MARKERS, *_GATE2_MARKERS))
    return has_question and has_indicator and not has_gate


def _extract_tool_calls(messages: list[BaseMessage]) -> list[str]:
    """Extract tool call names from recent AI messages.
    """
    names: list[str] = []
    for msg in messages[-15:]:
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                name = tc.get("name", "")
                if name:
                    names.append(name)
    return names


# ---------------------------------------------------------------------------
# extraction functions
# ---------------------------------------------------------------------------

def _extract_tool_call_details(messages: list[BaseMessage]) -> list[ToolCallRecord]:
    """Extract full tool call details by pairing AIMessage.tool_calls with ToolMessages.

    Walks the message list, finds AIMessage objects that have tool_calls,
    then finds the matching ToolMessage for each tool call (by tool_call_id).
    Builds a ToolCallRecord with the full args and output preview.

    Args:
        messages: The messages returned from agent.invoke()

    Returns:
        List of ToolCallRecord with full details
    """
    # Build a lookup of tool_call_id -> ToolMessage content
    tool_outputs: dict[str, str] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage):
            tc_id = getattr(msg, "tool_call_id", None)
            if tc_id:
                content = msg.content
                if isinstance(content, str):
                    tool_outputs[tc_id] = content
                elif isinstance(content, (dict, list)):
                    tool_outputs[tc_id] = json.dumps(content, ensure_ascii=False)
                else:
                    tool_outputs[tc_id] = str(content)

    # Walk AIMessages and build ToolCallRecords
    records: list[ToolCallRecord] = []
    for msg in messages:
        if not isinstance(msg, AIMessage):
            continue
        if not hasattr(msg, "tool_calls") or not msg.tool_calls:
            continue

        for tc in msg.tool_calls:
            tc_id = tc.get("id", "")
            tc_name = tc.get("name", "unknown")
            tc_args = tc.get("args", {})

            # Find matching output
            output_full = tool_outputs.get(tc_id, "")
            output_preview = output_full[:_TOOL_OUTPUT_PREVIEW_LIMIT]
            output_size = len(output_full)

            # Determine success/error
            success = True
            error = None
            if isinstance(output_full, str) and output_full:
                lower_output = output_full[:300].lower()
                if output_full.startswith("\u274c") or output_full.startswith("\u26a0\ufe0f"):
                    success = False
                    error = output_full[:200]
                elif "error" in lower_output and (
                    "failed" in lower_output
                    or "exception" in lower_output
                    or "400" in lower_output
                    or "500" in lower_output
                    or "timeout" in lower_output
                ):
                    success = False
                    error = output_full[:200]

            records.append(ToolCallRecord(
                tool_call_id=tc_id,
                name=tc_name,
                args=tc_args,
                output_preview=output_preview,
                output_size_chars=output_size,
                success=success,
                error=error,
            ))

    return records


def _extract_token_usage(messages: list[BaseMessage]) -> TokenUsage | None:
    """Extract token usage from the last AIMessage's response_metadata.

    Azure OpenAI via LiteLLM format:
        AIMessage.response_metadata["token_usage"] = {
            "prompt_tokens": N,
            "completion_tokens": N,
            "total_tokens": N,
        }

    Returns:
        TokenUsage if available, None otherwise.
    """
    for msg in reversed(messages):
        if not isinstance(msg, AIMessage):
            continue
        meta = getattr(msg, "response_metadata", None)
        if not meta:
            continue

        usage = meta.get("token_usage") or meta.get("usage")
        if not usage:
            continue

        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)

        if total_tokens == 0 and input_tokens == 0 and output_tokens == 0:
            continue

        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

    return None


def _extract_model_name(messages: list[BaseMessage]) -> str | None:
    """Extract model name from the last AIMessage's response_metadata.

    Azure OpenAI via LiteLLM format:
        AIMessage.response_metadata["model"] = "azure/gpt-5.2"

    Returns:
        Model name string if available, None otherwise.
    """
    for msg in reversed(messages):
        if not isinstance(msg, AIMessage):
            continue
        meta = getattr(msg, "response_metadata", None)
        if not meta:
            continue
        model = meta.get("model") or meta.get("model_name")
        if model:
            return str(model)
    return None


def _collect_session_artifacts(session_path: Path) -> dict[str, str]:
    """Read key session files from the workspace."""
    artifacts: dict[str, str] = {}
    for filename in (
        "scope.md", "features.md", "final_report.md",
        "references.md", "telemetry.json",
        "findings_accumulator.json", "findings_auto_accumulator.json",
    ):
        filepath = session_path / filename
        if filepath.exists():
            try:
                artifacts[filename] = filepath.read_text(encoding="utf-8")
            except Exception as exc:
                artifacts[filename] = f"[Error reading: {exc}]"

    findings_dir = session_path / "findings"
    if findings_dir.exists():
        for f in sorted(findings_dir.iterdir()):
            if f.is_file() and f.suffix in (".md", ".json"):
                key = f"findings/{f.name}"
                try:
                    artifacts[key] = f.read_text(encoding="utf-8")
                except Exception as exc:
                    artifacts[key] = f"[Error reading: {exc}]"

    return artifacts


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_novelty_check_e2e(
    idea: str,
    *,
    model: str | BaseChatModel | None = None,
    thread_id: str | None = None,
    session_id: str | None = None,
    max_turns: int = 30,
    max_duration_seconds: float = 3600.0,
    auto_scope_prompt: str | None = None,
    progress_callback: Callable[[int, RunPhase, GateType | None, str], None] | None = None,
) -> EvalRunResult:
    """Run a complete novelty check end-to-end with automatic gate approval.

    Creates the agent, sends the initial idea, and loops through the
    multi-turn conversation, automatically confirming at Gate 1 (Scope)
    and Gate 2 (Features). After Gate 2 the agent runs autonomously
    through the research loop until it delivers the final report.

    Args:
        idea: The invention description to evaluate.
        model: LLM model identifier or instance. Defaults to project LLM config.
        thread_id: Thread ID for the conversation. Auto-generated if None.
        session_id: Session ID for the workspace. Auto-generated if None.
        max_turns: Maximum number of invoke() calls before stopping.
        max_duration_seconds: Maximum wall-clock time for the entire run.
        auto_scope_prompt: Optional custom prefix for the initial prompt.
        progress_callback: Optional callback ``(turn, phase, gate, preview)``
            invoked after each turn.

    Returns:
        EvalRunResult with full message history, session artifacts, and
        the final report content.
    """
    from src.novelty_checker.deep_agent import SESSIONS_DIR, create_deep_agent
    from src.tools.clients.derwent_auth import check_derwent_jwt

    # Pre-flight: fail fast on dead/expired JWT. A mid-run 401 otherwise
    # silently collapses every GT-dependent metric to 0.00 with no alert.
    check_derwent_jwt()

    if thread_id is None:
        thread_id = f"eval_{uuid.uuid4().hex[:12]}"

    if model is None:
        from src.config.llm import get_llm
        model = get_llm()

    prefix = auto_scope_prompt if auto_scope_prompt is not None else _DEFAULT_AUTO_SCOPE_PREFIX
    initial_prompt = f"{prefix}{idea}"

    agent, session_id = create_deep_agent(model=model, session_id=session_id)
    session_path = SESSIONS_DIR / session_id

    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 500,
    }

    phase = RunPhase.INITIAL
    turns: list[TurnRecord] = []
    run_start = time.monotonic()
    error: str | None = None
    result: dict[str, Any] = {}
    detected_model_name: str | None = None

    # First turn: send the idea
    state: dict[str, Any] = {"messages": [HumanMessage(content=initial_prompt)]}
    injected: str | None = None

    for turn_num in range(1, max_turns + 1):
        elapsed = time.monotonic() - run_start
        if elapsed > max_duration_seconds:
            error = f"Exceeded max duration ({max_duration_seconds}s) after {turn_num - 1} turns"
            phase = RunPhase.ERROR
            break

        # Capture timestamp before invoke
        turn_timestamp = datetime.now().isoformat()
        turn_start = time.monotonic()

        try:
            result = asyncio.run(agent.ainvoke(state, config=config))
        except Exception as exc:
            error = f"agent.ainvoke() failed on turn {turn_num}: {exc}"
            _logger.error(error, exc_info=True)
            phase = RunPhase.ERROR
            break
        turn_duration = time.monotonic() - turn_start

        messages = result.get("messages", [])
        ai_content = _get_last_ai_content(messages)
        tool_calls = _extract_tool_calls(messages)
        gate = _detect_gate(ai_content, phase)
        is_done = _detect_completion(ai_content, session_path)

        #  extraction
        tool_call_details = _extract_tool_call_details(messages)
        token_usage = _extract_token_usage(messages)

        # Capture model name from first successful response
        if detected_model_name is None:
            detected_model_name = _extract_model_name(messages)

        # Build gate event if a gate was detected
        gate_event = None
        if gate is not None:
            gate_event = {
                "gate_name": gate.name.lower(),
                "agent_proposal_preview": ai_content[:1000],
                "response_injected": "confirm",
                "confirmation_mode": "accept_all",
            }

        turns.append(TurnRecord(
            turn_number=turn_num,
            phase=phase,
            injected_message=injected,
            ai_content_preview=ai_content[:_AI_CONTENT_PREVIEW_LIMIT],
            gate_detected=gate,
            tool_calls=tool_calls,
            duration_seconds=turn_duration,
            message_count=len(messages),

            timestamp=turn_timestamp,
            ai_content_full=ai_content,
            tool_call_details=tool_call_details,
            token_usage=token_usage,
            gate_event=gate_event,
        ))

        if progress_callback:
            try:
                progress_callback(turn_num, phase, gate, ai_content[:500])
            except Exception:
                pass

        _logger.info(
            "Turn %d: phase=%s gate=%s done=%s msgs=%d dur=%.1fs tokens=%s",
            turn_num, phase.name, gate, is_done, len(messages), turn_duration,
            f"{token_usage.total_tokens:,}" if token_usage else "n/a",
        )

        # --- phase transitions ---
        if is_done:
            phase = RunPhase.COMPLETED
            break

        if gate == GateType.SCOPE:
            phase = RunPhase.AWAITING_SCOPE_CONFIRM
            state = {"messages": [HumanMessage(content="confirm")]}
            injected = "confirm"
            _logger.info("Gate 1 (Scope) detected -> auto-confirming")
            continue

        if gate == GateType.FEATURES:
            phase = RunPhase.AUTONOMOUS_RESEARCH
            state = {"messages": [HumanMessage(content="confirm")]}
            injected = "confirm"
            _logger.info("Gate 2 (Features) detected -> auto-confirming, entering autonomous mode")
            continue

        if phase == RunPhase.AUTONOMOUS_RESEARCH:
            state = {"messages": [HumanMessage(content=(
                "Continue with the research. Do not ask me any questions. "
                "Proceed autonomously through the research loop and deliver "
                "the final report when ready."
            ))]}
            injected = "[auto-continue nudge]"
            continue

        if _is_clarifying_question(ai_content):
            state = {"messages": [HumanMessage(content=(
                "Please proceed with reasonable defaults. Use your best "
                "judgment for any ambiguous aspects. Do not ask further "
                "clarifying questions."
            ))]}
            injected = "[auto-default for clarifying question]"
            _logger.info("Clarifying question detected -> sending default answer")
            continue

        state = {"messages": [HumanMessage(content="Please continue with the novelty assessment workflow.")]}
        injected = "[auto-continue]"

    else:
        error = f"Reached max_turns ({max_turns}) without completion"
        if phase != RunPhase.COMPLETED:
            phase = RunPhase.ERROR

    total_duration = time.monotonic() - run_start
    final_messages = result.get("messages", [])

    # Safety net: if final_report.md is missing but the agent produced
    # report-like content in chat, persist it. Known orchestration gap:
    # the LLM emits the full 11-section report as chat text without
    # calling write_file('/final_report.md', ...).
    if _autosave_final_report(session_path, final_messages):
        _logger.warning(
            "final_report.md was missing or empty after run; autosaved "
            "from chat content as safety net (session=%s). This indicates "
            "the orchestrator skipped write_file('/final_report.md', ...).",
            session_id,
        )

    # Backfill findings_auto_accumulator.json from findings/*.md
    # (search tools run inside subagents, so middleware can't capture them
    # in real-time — we parse the filesystem after the run completes)
    try:
        from deepagents.backends import FilesystemBackend
        from src.novelty_checker.middleware.findings import FindingsPersistenceMiddleware

        _backfill_backend = FilesystemBackend(
            root_dir=str(session_path), virtual_mode=True
        )
        _backfill_mw = FindingsPersistenceMiddleware(
            backend=_backfill_backend, enabled=True
        )

        class _BackfillRuntime:
            config = {"configurable": {"thread_id": thread_id}}

        _backfill_mw.finalize_session(_BackfillRuntime())
    except Exception as exc:
        _logger.warning("Findings backfill failed: %s", exc)

    artifacts = _collect_session_artifacts(session_path)
    final_report = artifacts.get("final_report.md")

    return EvalRunResult(
        session_id=session_id,
        session_path=session_path,
        thread_id=thread_id,
        total_turns=len(turns),
        total_duration_seconds=total_duration,
        final_phase=phase,
        turns=turns,
        messages=final_messages,
        final_report=final_report,
        artifacts=artifacts,
        error=error,
        model_name=detected_model_name,
    )