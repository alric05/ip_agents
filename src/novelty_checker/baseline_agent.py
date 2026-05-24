"""Single-LLM baseline agent for the Novelty Checker.

This is the naive counterpart to `create_deep_agent()`: one LLM, the full
tool registry, and a consolidated system prompt. No middleware, no
subagents, no gates — used to measure how much end-to-end quality comes
from orchestration vs a plain tool-calling loop on the same task.

The agent is evaluated with the same eval harness (checklist, trace
writer, scorers) as the deep agent so score deltas on the golden
fixtures map directly to "agentic-design lift."
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.tools import tool
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from src.novelty_checker.baseline_prompt import BASELINE_SYSTEM_PROMPT
from src.novelty_checker.deep_agent import (
    SESSIONS_DIR,
    cleanup_old_sessions,
    create_session_workspace,
    get_default_model,
)
from src.tools.registry import get_all_tools

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


def _make_write_file_tool(session_path: Path):
    """Build a session-scoped write_file / read_file / list_files triplet.

    The LLM writes artifacts (scope.md, features.md, references.md,
    final_report.md, findings/round_X.md) into the session workspace via
    these tools. Paths are resolved relative to session_path; attempts to
    escape the workspace are rejected.
    """
    # Resolve once so macOS /var <-> /private/var symlinks don't trip up
    # relative_to() later.
    root = session_path.resolve()

    @tool
    def write_file(path: str, content: str) -> str:
        """Write text content to a file in the session workspace.

        Args:
            path: Path relative to the session directory. Leading slashes
                are treated as relative. Use paths like "scope.md",
                "features.md", "references.md", "final_report.md",
                or "findings/round_1.md".
            content: Full text content to write. Overwrites any existing
                file at this path.

        Returns:
            Confirmation string with the absolute path written.
        """
        rel = path.lstrip("/").lstrip("\\")
        target = (root / rel).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            return f"ERROR: path {path!r} escapes the session workspace"

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content):,} chars to {target}"

    @tool
    def read_file(path: str) -> str:
        """Read a file from the session workspace.

        Args:
            path: Path relative to the session directory.

        Returns:
            File contents, or an error message if the file is missing.
        """
        rel = path.lstrip("/").lstrip("\\")
        target = (root / rel).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            return f"ERROR: path {path!r} escapes the session workspace"
        if not target.exists():
            return f"ERROR: file not found: {path}"
        return target.read_text(encoding="utf-8")

    @tool
    def list_files(subdir: str = "") -> str:
        """List files currently in the session workspace.

        Args:
            subdir: Optional subdirectory (e.g. "findings"). Defaults to
                the session root.

        Returns:
            Newline-separated file paths relative to the session root.
        """
        rel = subdir.lstrip("/").lstrip("\\")
        target = (root / rel).resolve() if rel else root
        try:
            target.relative_to(root)
        except ValueError:
            return f"ERROR: path {subdir!r} escapes the session workspace"
        if not target.exists():
            return ""
        entries = []
        for p in sorted(target.rglob("*")):
            if p.is_file():
                entries.append(str(p.relative_to(root)))
        return "\n".join(entries)

    return [write_file, read_file, list_files]


def create_baseline_agent(
    model: str | BaseChatModel | None = None,
    session_id: str | None = None,
) -> tuple[CompiledStateGraph, str]:
    """Create the single-LLM baseline agent.

    Wraps `langgraph.prebuilt.create_react_agent` with:
    - the full tool registry from `src.tools.registry.get_all_tools()`
    - a session-scoped `write_file` / `read_file` / `list_files` tool
      triplet so the LLM can produce the scorer-required artifacts
    - the consolidated `BASELINE_SYSTEM_PROMPT`

    Returns a shape-compatible tuple with `create_deep_agent()` so the
    baseline runner can drop in wherever the deep agent is used.

    Args:
        model: LLM instance or LiteLLM model identifier. Defaults to
            `get_default_model()` — same default as the deep agent.
        session_id: Optional workspace ID. If None, a fresh session
            directory is created under `sessions/`.

    Returns:
        (compiled graph, session_id) — the session_id points at
        `sessions/<session_id>/` where artifacts will be written.
    """
    if model is None:
        model = get_default_model()

    try:
        cleanup_old_sessions(max_age_hours=24, max_sessions=50)
    except Exception:
        pass

    session_path, session_id = create_session_workspace(session_id)

    tools = list(get_all_tools()) + _make_write_file_tool(session_path)

    graph = create_react_agent(
        model,
        tools=tools,
        prompt=BASELINE_SYSTEM_PROMPT,
        name="novelty_baseline",
    )

    return graph, session_id


__all__ = ["create_baseline_agent", "SESSIONS_DIR"]
