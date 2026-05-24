"""End-to-end runner for the single-LLM baseline agent.

Mirrors the public surface of `run_novelty_check_e2e` in
`src/novelty_checker/eval_runner.py` so the existing evaluation harness
(checklist, trace_writer, scorers) treats baseline runs identically to
deep-agent runs. Score deltas on the golden fixtures then map directly
to "agentic-design lift."

Differences from the deep-agent runner:
- No Gate 1/Gate 2 detection or auto-confirm — the baseline has no gates.
- No clarifying-question heuristic — the baseline prompt forbids them.
- No findings backfill — the baseline has no subagents that would write
  findings out-of-band.

Usage:
    from src.novelty_checker.baseline_runner import run_baseline_e2e

    result = run_baseline_e2e(
        idea="A wearable wrist device that ...",
        max_turns=20,
    )
    print(result.final_report[:500])
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from src.novelty_checker.eval_runner import (
    EvalRunResult,
    RunPhase,
    TurnRecord,
    _AI_CONTENT_PREVIEW_LIMIT,
    _autosave_final_report,
    _collect_session_artifacts,
    _extract_model_name,
    _extract_token_usage,
    _extract_tool_call_details,
    _extract_tool_calls,
    _get_last_ai_content,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from langchain_core.language_models import BaseChatModel

_logger = logging.getLogger(__name__)

_DONE_MARKERS = ("Final Report", "## 1.", "## Executive Summary")

_DEFAULT_AUTO_PROMPT_PREFIX = (
    "Please check the novelty of this invention. Do not ask clarifying "
    "questions. Use reasonable defaults for any ambiguous aspect and "
    "proceed directly to the final report.\n\n"
    "Here is the invention:\n\n"
)


def _final_report_exists(session_path: Path) -> bool:
    report = session_path / "final_report.md"
    return report.exists() and report.stat().st_size > 100


def _detect_completion(ai_content: str, session_path: Path) -> bool:
    if any(marker in ai_content for marker in _DONE_MARKERS):
        return True
    return _final_report_exists(session_path)


def run_baseline_e2e(
    idea: str,
    *,
    model: str | BaseChatModel | None = None,
    thread_id: str | None = None,
    session_id: str | None = None,
    max_turns: int = 20,
    max_duration_seconds: float = 3600.0,
    auto_prompt_prefix: str | None = None,
    progress_callback: Callable[[int, RunPhase, None, str], None] | None = None,
) -> EvalRunResult:
    """Run the single-LLM baseline end-to-end on one disclosure.

    Creates a fresh baseline agent + session workspace, feeds the
    disclosure, and lets the LLM loop through tool calls until it
    either writes `final_report.md` or hits a turn / time cap. Returns
    the same `EvalRunResult` shape the existing checklist and trace
    writer consume.

    Args:
        idea: The invention disclosure to evaluate.
        model: LLM instance or LiteLLM identifier. Defaults to the
            project's default (`get_default_model()`).
        thread_id: Conversation thread ID. Auto-generated if None.
        session_id: Workspace ID. Auto-generated if None.
        max_turns: Safety cap on invoke() iterations.
        max_duration_seconds: Wall-clock cap for the full run.
        auto_prompt_prefix: Optional override for the disclosure prefix.
        progress_callback: Optional per-turn callback
            `(turn, phase, None, preview)`. The `phase` arg is always
            `RunPhase.AUTONOMOUS_RESEARCH` for the baseline; the gate
            slot is always None — kept for signature compatibility with
            the deep-agent progress callback.

    Returns:
        EvalRunResult with turn records, tool call details, token usage,
        and the collected session artifacts.
    """
    from src.novelty_checker.baseline_agent import SESSIONS_DIR, create_baseline_agent

    if thread_id is None:
        thread_id = f"baseline_{uuid.uuid4().hex[:12]}"

    if model is None:
        from src.config.llm import get_llm
        model = get_llm()

    prefix = auto_prompt_prefix if auto_prompt_prefix is not None else _DEFAULT_AUTO_PROMPT_PREFIX
    initial_prompt = f"{prefix}{idea}"

    agent, session_id = create_baseline_agent(model=model, session_id=session_id)
    session_path = SESSIONS_DIR / session_id

    config: dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 500,
    }

    # The baseline has no gates → phase stays in autonomous research the
    # whole way through. We still track it so TurnRecord.phase is
    # populated with the same enum the checklist/trace_writer expect.
    phase = RunPhase.AUTONOMOUS_RESEARCH

    turns: list[TurnRecord] = []
    run_start = time.monotonic()
    error: str | None = None
    result: dict[str, Any] = {}
    detected_model_name: str | None = None

    state: dict[str, Any] = {"messages": [HumanMessage(content=initial_prompt)]}
    injected: str | None = None

    for turn_num in range(1, max_turns + 1):
        elapsed = time.monotonic() - run_start
        if elapsed > max_duration_seconds:
            error = f"Exceeded max duration ({max_duration_seconds}s) after {turn_num - 1} turns"
            phase = RunPhase.ERROR
            break

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
        tool_call_details = _extract_tool_call_details(messages)
        token_usage = _extract_token_usage(messages)
        is_done = _detect_completion(ai_content, session_path)

        if detected_model_name is None:
            detected_model_name = _extract_model_name(messages)

        turns.append(TurnRecord(
            turn_number=turn_num,
            phase=phase,
            injected_message=injected,
            ai_content_preview=ai_content[:_AI_CONTENT_PREVIEW_LIMIT],
            gate_detected=None,
            tool_calls=tool_calls,
            duration_seconds=turn_duration,
            message_count=len(messages),
            timestamp=turn_timestamp,
            ai_content_full=ai_content,
            tool_call_details=tool_call_details,
            token_usage=token_usage,
            gate_event=None,
        ))

        if progress_callback:
            try:
                progress_callback(turn_num, phase, None, ai_content[:500])
            except Exception:
                pass

        _logger.info(
            "Baseline turn %d: tools=%d msgs=%d dur=%.1fs tokens=%s done=%s",
            turn_num, len(tool_call_details), len(messages), turn_duration,
            f"{token_usage.total_tokens:,}" if token_usage else "n/a",
            is_done,
        )

        if is_done:
            phase = RunPhase.COMPLETED
            break

        # The ReAct agent returned without a pending tool call AND no final
        # report yet → nudge it to keep going. This is the only continuation
        # path for the baseline.
        last = messages[-1] if messages else None
        has_pending_tool_call = (
            isinstance(last, AIMessage)
            and getattr(last, "tool_calls", None)
        )
        if has_pending_tool_call:
            # create_react_agent will resolve the pending tool call on
            # the next invoke automatically if we pass the same state back.
            state = {"messages": messages}
            injected = None
            continue

        state = {"messages": [HumanMessage(content=(
            "Continue. Do not ask questions. If you have enough coverage, "
            "synthesize and write the final report to final_report.md via "
            "the write_file tool."
        ))]}
        injected = "[auto-continue nudge]"

    else:
        error = f"Reached max_turns ({max_turns}) without completion"
        if phase != RunPhase.COMPLETED:
            phase = RunPhase.ERROR

    total_duration = time.monotonic() - run_start
    final_messages = result.get("messages", [])

    if _autosave_final_report(session_path, final_messages):
        _logger.warning(
            "final_report.md was missing or empty after run; autosaved "
            "from chat content as safety net (session=%s).",
            session_id,
        )

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


__all__ = ["run_baseline_e2e"]
