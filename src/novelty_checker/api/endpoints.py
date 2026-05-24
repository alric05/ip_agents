"""FastAPI router with structured endpoints for the Novelty Checker API.

Every response uses the :class:`APIResponse` envelope so the frontend
always knows what stage the agent is in and what structured data to render.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import AIMessage, HumanMessage

from src.novelty_checker.api.response_parser import (
    _read_file_safe,
    _read_accumulator,
    build_stage_data,
)
from src.novelty_checker.api.schemas import APIResponse, ChatRequest
from src.novelty_checker.api.stage_detector import (
    detect_stage,
    detect_status,
    get_backend_for_thread,
)
from src.novelty_checker.api.telemetry_reader import read_token_usage, thread_exists
from src.novelty_checker.observability.telemetry import _file_exists_on_backend
from src.tools.clients.derwent_auth import DerwentAuthError, check_derwent_jwt

_logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Helpers
# =============================================================================

def _get_graph(request: Request):
    """Get the compiled graph from app state."""
    return request.app.state.graph


def _get_backend_factory(request: Request):
    """Get the ThreadAwareBackendFactory from app state."""
    return request.app.state.backend_factory


def _get_sessions_dir(request: Request):
    """Get the sessions directory from app state."""
    return request.app.state.sessions_dir


def _extract_last_ai_text(messages: list) -> str:
    """Extract text content from the last AI message."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            content = msg.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, str):
                        parts.append(item)
                    elif isinstance(item, dict) and isinstance(item.get("text"), str):
                        parts.append(item["text"])
                return "".join(parts)
    return ""


def _build_state_snapshot(result: dict) -> dict:
    """Extract relevant fields from graph invoke result for stage data building."""
    return {
        "features": result.get("features", []),
        "references": result.get("references", []),
        "coverage": result.get("coverage", []),
        "scope_markdown": result.get("scope_markdown"),
        "overall_coverage": result.get("overall_coverage"),
    }


# =============================================================================
# POST /chat — Synchronous structured response
# =============================================================================

@router.post("/chat", response_model=APIResponse)
async def structured_chat(req: ChatRequest, request: Request):
    """Synchronous chat returning a structured APIResponse envelope.

    For interactive stages (scoping, features) this returns quickly.
    For the research phase this blocks until the report is ready (5-15 min).
    """
    thread_id = req.thread_id or str(uuid.uuid4())

    # Extract JWT token from Authorization header (standard) or fallback to body
    jwt_token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        jwt_token = auth_header[7:]  # Remove "Bearer " prefix
    elif req.jwt_token:
        jwt_token = req.jwt_token  # Fallback to body parameter

    # Pre-flight: fail the request fast with 401 when the Derwent JWT is
    # missing/expired, instead of starting a multi-minute run that silently
    # collapses every GT-dependent metric to 0.00.
    try:
        check_derwent_jwt(jwt_token)
    except DerwentAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    config = {
        "configurable": {
            "thread_id": thread_id,
            "jwt_token": jwt_token,  # Per-thread JWT token for external API calls
        },
        "recursion_limit": 500,
    }
    graph = _get_graph(request)
    backend_factory = _get_backend_factory(request)
    sessions_dir = _get_sessions_dir(request)

    try:
        # 1. Invoke the agent
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=req.message)]},
            config=config,
        )

        # 2. Extract AI response text
        messages = result.get("messages", [])
        ai_text = _extract_last_ai_text(messages)

        # 3. Resolve backend for this thread
        backend = get_backend_for_thread(backend_factory, thread_id, sessions_dir)

        # 4. Detect stage
        stage = detect_stage(backend, messages)

        # 5. Detect status
        has_report = _file_exists_on_backend(backend, "/final_report.md")
        status = detect_status(stage, has_report)

        # 6. Build structured stage_data
        state_snapshot = _build_state_snapshot(result)
        stage_data = build_stage_data(stage, ai_text, state_snapshot, backend)

        # 7. Read token usage
        token_usage = read_token_usage(sessions_dir, thread_id)

        return APIResponse(
            thread_id=thread_id,
            stage=stage,
            status=status,
            stage_data=stage_data,
            raw_response=ai_text,
            token_usage=token_usage,
        )

    except Exception as e:
        _logger.exception("Error in POST /chat")
        return APIResponse(
            thread_id=thread_id,
            stage="scoping",
            status="error",
            stage_data={},
            raw_response="",
            error=str(e),
        )


# =============================================================================
# GET /threads/{thread_id}/state — Read current state without invoking
# =============================================================================

@router.get("/threads/{thread_id}/state", response_model=APIResponse)
async def get_thread_state(thread_id: str, request: Request):
    """Read the current structured state of a thread without invoking the agent.

    Useful for:
    - Polling research progress if the /chat call timed out
    - Reconnecting to an in-progress session
    - Checking if the report is ready
    """
    sessions_dir = _get_sessions_dir(request)
    backend_factory = _get_backend_factory(request)

    if not thread_exists(sessions_dir, thread_id):
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    backend = get_backend_for_thread(backend_factory, thread_id, sessions_dir)

    # Read filesystem artifacts
    report_md = _read_file_safe(backend, "/final_report.md")
    features_md = _read_file_safe(backend, "/features.md")
    scope_md = _read_file_safe(backend, "/scope.md")
    accum = _read_accumulator(backend)

    # Determine stage from artifacts (simplified — no message history available)
    if report_md:
        stage = "complete"
        status = "done"
    elif features_md and accum and accum.get("rounds"):
        stage = "researching"
        status = "processing"
    elif features_md or scope_md:
        stage = "features" if features_md or scope_md else "scoping"
        status = "awaiting_input"
    else:
        stage = "scoping"
        status = "awaiting_input"

    # Build stage_data from filesystem artifacts
    state_snapshot = {
        "features": accum.get("features", []) if accum else [],
        "references": accum.get("all_references", []) if accum else [],
        "coverage": accum.get("final_coverage", []) if accum else [],
        "scope_markdown": scope_md,
        "overall_coverage": accum.get("final_coverage_pct") if accum else None,
    }
    stage_data = build_stage_data(stage, "", state_snapshot, backend)

    token_usage = read_token_usage(sessions_dir, thread_id)

    return APIResponse(
        thread_id=thread_id,
        stage=stage,
        status=status,
        stage_data=stage_data,
        raw_response="",
        token_usage=token_usage,
    )


# =============================================================================
# GET /threads/{thread_id}/report — Download final report
# =============================================================================

@router.get("/threads/{thread_id}/report")
async def get_report(thread_id: str, request: Request):
    """Return the final report markdown.

    Returns 404 if the report is not ready yet.
    """
    sessions_dir = _get_sessions_dir(request)
    backend_factory = _get_backend_factory(request)

    if not thread_exists(sessions_dir, thread_id):
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    backend = get_backend_for_thread(backend_factory, thread_id, sessions_dir)
    report = _read_file_safe(backend, "/final_report.md")

    if not report:
        raise HTTPException(status_code=404, detail="Report not ready yet")

    return {"thread_id": thread_id, "report_markdown": report}


# =============================================================================
# GET /threads/{thread_id}/token-usage — Token usage breakdown
# =============================================================================

@router.get("/threads/{thread_id}/token-usage")
async def get_token_usage(thread_id: str, request: Request):
    """Get token usage breakdown for a specific thread."""
    sessions_dir = _get_sessions_dir(request)

    if not thread_exists(sessions_dir, thread_id):
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    token_usage = read_token_usage(sessions_dir, thread_id)
    if token_usage is None:
        return {"by_stage": {}, "by_agent": {}, "cumulative": {}}
    return token_usage


# =============================================================================
# GET /health
# =============================================================================

@router.get("/health")
async def health():
    return {"ok": True}
