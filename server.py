import json
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

# Ensure project root is on sys.path (same as studio.py)
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

load_dotenv(project_root / ".env")

from src.config.llm import get_llm, get_active_backend_info
from src.novelty_checker.deep_agent import create_deep_agent, SESSIONS_DIR
from src.novelty_checker.api.endpoints import router as structured_router
from src.novelty_checker.api.schemas import ChatRequest
from src.novelty_checker.api.response_parser import build_stage_data
from src.novelty_checker.api.stage_detector import detect_stage, get_backend_for_thread
from src.novelty_checker.api.labels import NODE_LABELS, TOOL_LABELS, INTERNAL_TOOLS
from src.novelty_checker.api.a2ui_bubbles import build_activity_bubble
from src.novelty_checker.api.research_timeline import ResearchTimelineBuilder
from src.tools.clients.derwent_auth import DerwentAuthError, check_derwent_jwt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the agent graph once at startup."""
    logger.info("Creating novelty checker graph...")
    backend_info = get_active_backend_info()
    logger.info(f"LLM backend: {backend_info['provider']} - {backend_info['model']}")

    graph, session_id = create_deep_agent(
        model=get_llm(),
        checkpointer=None,           # MemorySaver auto-created internally
        use_custom_state=True,       # Full state reducers for production
        use_backend_factory=True,    # Per-thread session isolation
        emit_structured_json=True,   # LLM emits json:questions/json:features blocks
    )
    app.state.graph = graph
    app.state.default_session_id = session_id
    app.state.sessions_dir = SESSIONS_DIR

    # Expose the backend factory so endpoints can resolve per-thread backends.
    from src.novelty_checker.backend_factory import ThreadAwareBackendFactory
    app.state.backend_factory = ThreadAwareBackendFactory(
        sessions_dir=SESSIONS_DIR,
        default_session_id=session_id,
    )

    logger.info(f"Graph ready (default session: {session_id})")
    yield
    logger.info("Shutting down server...")


api = FastAPI(
    title="Novelty Checker API",
    version="2.0.0",
    lifespan=lifespan,
)

allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
api.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in allowed_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the structured API router (POST /chat, GET /threads/*, GET /health)
api.include_router(structured_router)


@api.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    """SSE streaming chat — streams events as the agent runs."""
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

    async def event_generator():
        try:
            yield _sse_event("metadata", {"thread_id": thread_id})

            full_ai_text: list[str] = []
            last_activity_node: str | None = None
            timeline = ResearchTimelineBuilder()
            timeline_initialized = False

            def _backend():
                return get_backend_for_thread(
                    api.state.backend_factory, thread_id, api.state.sessions_dir,
                )

            def _current_stage() -> str:
                try:
                    return detect_stage(_backend(), [])
                except Exception:
                    return "scoping"

            async for event in api.state.graph.astream_events(
                {"messages": [HumanMessage(content=req.message)]},
                config=config,
                version="v2",
            ):
                event_type = event.get("event", "")
                if event_type not in {
                    "on_chat_model_stream",
                    "on_llm_stream",
                    "on_chat_model_end",
                    "on_llm_end",
                    "on_chat_model_start",
                    "on_tool_start",
                    "on_tool_end",
                }:
                    continue

                metadata = event.get("metadata", {})
                node_name = (
                    metadata.get("langgraph_node", "unknown")
                    if isinstance(metadata, dict)
                    else "unknown"
                )
                stage = _current_stage()

                # Accumulate AI text for the terminal bubble; do NOT stream tokens.
                data = event.get("data", {})
                chunk = data.get("chunk") if isinstance(data, dict) else None
                output = data.get("output") if isinstance(data, dict) else None
                chunk_text = _extract_text_from_model_chunk(chunk)
                if (
                    not chunk_text
                    and event_type in {"on_chat_model_end", "on_llm_end"}
                ):
                    chunk_text = _extract_text_from_model_chunk(output)
                if chunk_text:
                    full_ai_text.append(chunk_text)

                # Emit the timeline shell once we hit the researching stage.
                if stage == "researching" and not timeline_initialized:
                    timeline_initialized = True
                    yield _emit_stage_data(
                        "researching", "processing", timeline.initial_snapshot()
                    )

                # ---- on_chat_model_start: agent/subagent thinking ----
                if event_type == "on_chat_model_start":
                    if node_name not in NODE_LABELS or node_name == last_activity_node:
                        continue
                    last_activity_node = node_name
                    if stage == "researching":
                        snap = timeline.on_node_start(node_name)
                        if snap:
                            yield _emit_stage_data(
                                "researching", "processing", snap
                            )
                    else:
                        yield _emit_stage_data(
                            stage,
                            "processing",
                            build_activity_bubble(
                                NODE_LABELS[node_name], "Thinking..."
                            ),
                        )
                    continue

                # ---- on_tool_start ----
                if event_type == "on_tool_start":
                    tool_name = event.get("name", "")
                    if not tool_name or tool_name in INTERNAL_TOOLS:
                        continue
                    if stage == "researching":
                        snap = timeline.on_tool_start(node_name, tool_name)
                        if snap:
                            yield _emit_stage_data(
                                "researching", "processing", snap
                            )
                    else:
                        header = NODE_LABELS.get(node_name, node_name)
                        text = TOOL_LABELS.get(tool_name, f"Running {tool_name}...")
                        yield _emit_stage_data(
                            stage,
                            "processing",
                            build_activity_bubble(header, text),
                        )
                    continue

                # ---- on_tool_end ----
                if event_type == "on_tool_end":
                    tool_name = event.get("name", "")
                    if not tool_name or tool_name in INTERNAL_TOOLS:
                        continue
                    if stage == "researching":
                        snap = timeline.on_tool_end(node_name, tool_name)
                        if snap:
                            yield _emit_stage_data(
                                "researching", "processing", snap
                            )
                    else:
                        header = NODE_LABELS.get(node_name, node_name)
                        label = TOOL_LABELS.get(tool_name, tool_name)
                        yield _emit_stage_data(
                            stage,
                            "processing",
                            build_activity_bubble(
                                header, f"{label.rstrip('.')} - done"
                            ),
                        )
                    continue

            # ---- terminal bubble after stream completes ----
            try:
                ai_text = "".join(full_ai_text)
                backend = _backend()
                stage = detect_stage(backend, [])

                if stage == "complete":
                    bubble = timeline.finalize(backend, ai_text)
                    status = "done"
                elif stage == "researching":
                    bubble = timeline.snapshot()
                    status = "processing"
                elif stage == "features":
                    bubble = build_stage_data("features", ai_text, {}, backend)
                    status = "awaiting_input"
                else:  # scoping
                    bubble = build_stage_data("scoping", ai_text, {}, backend)
                    # plainBubble (scope confirmed, no questions) is informational;
                    # assumptionBubble waits for user input.
                    status = (
                        "done"
                        if bubble.get("component") == "plainBubble"
                        else "awaiting_input"
                    )

                yield _emit_stage_data(stage, status, bubble)
            except Exception:
                logger.debug(
                    "Could not build terminal stage_data for stream", exc_info=True
                )

            yield _sse_event("done", {"thread_id": thread_id})
        except Exception as e:
            logger.exception("Error in /chat/stream")
            yield _sse_event("error", {"detail": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_event(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event string."""
    payload = json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"


def _emit_stage_data(stage: str, status: str, bubble: dict) -> str:
    """Format a ``stage_data`` SSE event with the A2UI envelope."""
    return _sse_event("stage_data", {
        "stage": stage,
        "status": status,
        "stage_data": bubble,
    })


def _extract_text_from_chunk(content) -> str:
    """Extract plain text from LangChain/LangGraph message chunk content."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def _extract_text_from_model_chunk(chunk) -> str:
    """Extract text from a model stream chunk payload."""
    if chunk is None:
        return ""

    if isinstance(chunk, tuple):
        for item in chunk:
            text = _extract_text_from_model_chunk(item)
            if text:
                return text
        return ""

    if isinstance(chunk, list):
        parts: list[str] = []
        for item in chunk:
            text = _extract_text_from_model_chunk(item)
            if text:
                parts.append(text)
        return "".join(parts)

    if isinstance(chunk, dict):
        direct = _extract_text_from_chunk(chunk.get("content"))
        if direct:
            return direct

        for key in ("text", "output", "message", "messages", "generation"):
            if key in chunk:
                nested = _extract_text_from_model_chunk(chunk[key])
                if nested:
                    return nested
        return ""

    content = getattr(chunk, "content", None)
    text = _extract_text_from_chunk(content)
    if text:
        return text

    if hasattr(chunk, "text"):
        text_attr = getattr(chunk, "text")
        if isinstance(text_attr, str):
            return text_attr

    if hasattr(chunk, "message"):
        nested = _extract_text_from_model_chunk(getattr(chunk, "message"))
        if nested:
            return nested

    if hasattr(chunk, "messages"):
        nested = _extract_text_from_model_chunk(getattr(chunk, "messages"))
        if nested:
            return nested

    return ""


