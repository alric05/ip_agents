"""Thread-aware backend factory for LangGraph Studio session isolation.

When running under LangGraph Studio, a single compiled graph serves all threads.
This factory ensures each thread gets its own FilesystemBackend rooted at a
dedicated session directory (sessions/{thread_id}/), preventing artifact leakage
between conversations.

Conforms to deepagents' BackendFactory = Callable[[ToolRuntime], BackendProtocol].

Usage:
    factory = ThreadAwareBackendFactory(sessions_dir=SESSIONS_DIR)

    # Pass as backend to create_deep_agent and middleware:
    graph = create_deep_agent(backend=factory, ...)
    middleware = FindingsPersistenceMiddleware(backend=factory, ...)
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from deepagents.backends import FilesystemBackend
from deepagents.backends.protocol import BackendProtocol

_logger = logging.getLogger(__name__)


def extract_agent_name(runtime: Any) -> str:
    """Extract the current agent name from LangGraph checkpoint_ns.

    Root graph (orchestrator): checkpoint_ns is empty -> returns "orchestrator".
    Subgraph: checkpoint_ns = "patent-researcher:abc123" -> returns "patent-researcher".

    Args:
        runtime: Runtime or ToolRuntime from a middleware hook.

    Returns:
        The agent name string.
    """
    # 1. Try runtime.config (ToolRuntime has it, Runtime doesn't)
    config = getattr(runtime, "config", None)
    if config is not None:
        ns = config.get("configurable", {}).get("checkpoint_ns", "")
        if ns:
            # Parse last segment: "parent|child:task_id" -> "child"
            return ns.split("|")[-1].split(":")[0]

    # 2. Fall back to LangGraph context variable
    try:
        from langgraph.config import get_config
        cfg = get_config()
        ns = cfg.get("configurable", {}).get("checkpoint_ns", "")
        if ns:
            return ns.split("|")[-1].split(":")[0]
    except (RuntimeError, ImportError):
        pass

    return "orchestrator"


def extract_thread_id(runtime: Any) -> str | None:
    """Extract thread_id from a ToolRuntime or via LangGraph context variable.

    ToolRuntime (received in wrap_tool_call) has .config with
    configurable.thread_id.  Runtime (received in wrap_model_call) does NOT
    have .config directly, but deepagents' internal middleware constructs an
    artificial ToolRuntime that carries config.  As a fallback, LangGraph's
    context variable is checked.

    Args:
        runtime: ToolRuntime or Runtime from a middleware hook.

    Returns:
        The thread_id string, or None if unavailable.
    """
    # 1. Try ToolRuntime.config (available in wrap_tool_call and in
    #    artificial ToolRuntime from MemoryMiddleware/SkillsMiddleware)
    config = getattr(runtime, "config", None)
    if config is not None:
        thread_id = config.get("configurable", {}).get("thread_id")
        if thread_id:
            return str(thread_id)

    # 2. Fall back to LangGraph context variable (works inside graph execution)
    try:
        from langgraph.utils.config import get_config
        cfg = get_config()
        thread_id = cfg.get("configurable", {}).get("thread_id")
        if thread_id:
            return str(thread_id)
    except (RuntimeError, ImportError):
        pass

    return None


def extract_jwt_token(runtime: Any) -> str | None:
    """Extract JWT token from a ToolRuntime or via LangGraph context variable.

    JWT tokens are stored in config["configurable"]["jwt_token"] and passed
    from the API layer. Tools can use this function to retrieve the token
    for external API authentication.

    Args:
        runtime: ToolRuntime or Runtime from a middleware hook.

    Returns:
        The JWT token string, or None if unavailable.

    Example:
        @tool
        def call_external_api(query: str) -> str:
            from langgraph.utils.config import get_config
            config = get_config()
            jwt_token = config.get("configurable", {}).get("jwt_token")
            if not jwt_token:
                return "Error: No JWT token available"

            headers = {"Authorization": f"Bearer {jwt_token}"}
            # Make API call with headers...
    """
    # 1. Try ToolRuntime.config (available in wrap_tool_call)
    config = getattr(runtime, "config", None)
    if config is not None:
        jwt_token = config.get("configurable", {}).get("jwt_token")
        if jwt_token:
            return str(jwt_token)

    # 2. Fall back to LangGraph context variable (works inside graph execution)
    try:
        from langgraph.utils.config import get_config
        cfg = get_config()
        jwt_token = cfg.get("configurable", {}).get("jwt_token")
        if jwt_token:
            return str(jwt_token)
    except (RuntimeError, ImportError):
        pass

    return None



class ThreadAwareBackendFactory:
    """Backend factory returning per-thread FilesystemBackend instances.

    Each unique thread_id gets its own session directory under sessions_dir.
    Backends are cached for the lifetime of this factory instance.

    Thread-safe via threading.Lock for the backend cache.

    Args:
        sessions_dir: Root directory for session workspaces.
        default_session_id: Fallback session ID when thread_id is unavailable.
    """

    def __init__(
        self,
        sessions_dir: Path,
        default_session_id: str = "default",
    ) -> None:
        self._sessions_dir = sessions_dir
        self._default_session_id = default_session_id
        self._cache: dict[str, FilesystemBackend] = {}
        self._lock = threading.Lock()

    def __call__(self, runtime: Any) -> BackendProtocol:
        """Resolve or create a FilesystemBackend for the current thread.

        Args:
            runtime: ToolRuntime provided by deepagents middleware hooks.

        Returns:
            A FilesystemBackend rooted at sessions/{thread_id}/.
        """
        thread_id = extract_thread_id(runtime) or self._default_session_id

        with self._lock:
            if thread_id not in self._cache:
                session_path = self._sessions_dir / thread_id
                # No eager mkdir here — FilesystemBackend.write() creates
                # parent directories automatically. Avoiding sync I/O in
                # __call__ prevents BlockingError in LangGraph's ASGI server.
                backend = FilesystemBackend(
                    root_dir=session_path,
                    virtual_mode=True,
                )
                self._cache[thread_id] = backend
                _logger.info(
                    f"Created session backend for thread '{thread_id}' "
                    f"at {session_path}"
                )
            return self._cache[thread_id]

    def get_session_path(self, thread_id: str) -> Path:
        """Get the session directory path for a given thread_id."""
        return self._sessions_dir / thread_id

    @property
    def active_threads(self) -> list[str]:
        """List thread_ids that have active backends."""
        with self._lock:
            return list(self._cache.keys())


