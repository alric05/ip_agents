"""Deep Agent graph for the Novelty Checker system.

This module creates a deep agent using the deepagents library:
- MemoryMiddleware loads AGENTS.md as system prompt
- TodoListMiddleware for planning via write_todos
- SkillsMiddleware for progressive skill disclosure
- SubAgentMiddleware for hierarchical task delegation

The agent uses create_deep_agent() from deepagents, matching the
patterns in deepagents/examples/deep_research/.

Key Features (Phase 1 - Iterative Research Loop):
- Modular prompts imported from prompts.py
- Iterative "Search → Reflect → Decide" loop
- Coverage-based adaptive stopping
- Structured reflection templates with think_tool
- Session-isolated storage to prevent cross-run interference
"""

import asyncio
import logging
import shutil
import sys
import uuid
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any

# Suppress Pydantic serialization warnings from LangGraph/LangChain message types
# These are benign warnings about message type unions that don't affect functionality
warnings.filterwarnings(
    "ignore",
    message="Pydantic serializer warnings:",
    category=UserWarning,
    module="pydantic",
)

import yaml
from langchain.agents.middleware.types import AgentMiddleware, ModelRequest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.types import Checkpointer

# LiteLLM for unified LLM access (supports 100+ providers)
from langchain_litellm import ChatLiteLLM

# Import deepagents framework (installed via pip)
from deepagents import create_deep_agent as _create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.middleware._utils import append_to_system_message
from deepagents.middleware.skills import (
    SkillMetadata,
    SkillsState,
    _parse_skill_metadata,
)

# ---------------------------------------------------------------------------
# Monkey-patch: raise subagent recursion_limit from Studio's default (100)
# ---------------------------------------------------------------------------
# LangGraph Studio sends recursion_limit=100 in run config, which propagates
# to subagents via var_child_runnable_config. Subagents created with
# create_agent() (not create_deep_agent()) don't get .with_config(), so they
# inherit the parent's 100 — too low for patent-researcher doing 5-10 searches
# with think_tool reflection.
#
# Fix: wrap every subagent graph with .with_config({"recursion_limit": 500}).
# In ensure_config() merge order (defaults → parent_ctx → self.config → passed),
# the binding config overrides the inherited 100.
import deepagents.middleware.subagents as _subagents_mod

_original_create_agent = _subagents_mod.create_agent


def _create_agent_with_recursion_limit(*args: Any, **kwargs: Any) -> Any:
    """Wrap create_agent to apply higher recursion_limit for subagents."""
    graph = _original_create_agent(*args, **kwargs)
    return graph.with_config({"recursion_limit": 500})


_subagents_mod.create_agent = _create_agent_with_recursion_limit

# ---------------------------------------------------------------------------
# Monkey-patch: ensure _build_task_tool passes recursion_limit to subagent invoke
# ---------------------------------------------------------------------------
# _build_task_tool's task()/atask() closures call subagent.invoke(state) WITHOUT
# passing config, so subagents fall back to LangGraph's default recursion_limit=25.
# Fix: wrap each subagent graph's invoke/ainvoke to inject recursion_limit=500.
_original_build_task_tool = _subagents_mod._build_task_tool


def _patched_build_task_tool(subagents: list, *args: Any, **kwargs: Any) -> Any:
    """Wrap _build_task_tool so subagent invoke() gets recursion_limit=500."""
    for spec in subagents:
        graph = spec["runnable"]
        if getattr(graph, "_recursion_patched", False):
            continue

        _orig_invoke = graph.invoke
        _orig_ainvoke = graph.ainvoke

        def _make_invoke(orig):  # noqa: E301
            def _patched(state, config=None, **kw):
                config = config or {}
                if isinstance(config, dict):
                    config.setdefault("recursion_limit", 500)
                return orig(state, config=config, **kw)
            return _patched

        def _make_ainvoke(orig):  # noqa: E301
            async def _patched(state, config=None, **kw):
                config = config or {}
                if isinstance(config, dict):
                    config.setdefault("recursion_limit", 500)
                return await orig(state, config=config, **kw)
            return _patched

        graph.invoke = _make_invoke(_orig_invoke)
        graph.ainvoke = _make_ainvoke(_orig_ainvoke)
        graph._recursion_patched = True  # type: ignore[attr-defined]

    return _original_build_task_tool(subagents, *args, **kwargs)


_subagents_mod._build_task_tool = _patched_build_task_tool

# Import custom middleware (Phase 4)
from src.novelty_checker.middleware.content_filter import ContentFilterMiddleware
from src.novelty_checker.middleware.findings import FindingsPersistenceMiddleware

# Import citation enforcement middleware (Phase 3)
from src.novelty_checker.middleware.citation_enforcement import CitationEnforcementMiddleware
from src.novelty_checker.middleware.full_text_evidence import FullTextEvidenceMiddleware
from src.novelty_checker.middleware.report_persistence import ReportPersistenceMiddleware
from src.novelty_checker.middleware.self_citation_guard import SelfCitationGuardMiddleware

# Import feature confirmation gate middleware
from src.novelty_checker.middleware.feature_confirmation import FeatureConfirmationMiddleware

# Import autonomous research enforcement middleware
from src.novelty_checker.middleware.autonomous_research import AutonomousResearchMiddleware

# Import research continuation enforcement middleware
from src.novelty_checker.middleware.research_continuation import ResearchContinuationMiddleware

# Import patent lifecycle tracking middleware
from src.novelty_checker.middleware.patent_tracking import PatentTrackingMiddleware
from src.novelty_checker.observability.patent_tracker import PatentTracker

# Import query-log middleware (writes /queries_log.md artifact)
from src.novelty_checker.middleware.query_log import (
    QueryLogMiddleware,
    QueryLogger,
)

# Import telemetry (Phase 2)
from src.novelty_checker.observability.telemetry import (
    ResearchTelemetry,
    TelemetryMiddleware,
)

# Import thread-aware backend factory for LangGraph Studio
from src.novelty_checker.backend_factory import ThreadAwareBackendFactory
from src.novelty_checker.guardrails import (
    GuardrailsOutputFilterMiddleware,
    GuardrailsPromptMiddleware,
)

# Import modular prompts (following Deep Research Agent pattern)
from src.novelty_checker.prompts import (
    NOVELTY_WORKFLOW_INSTRUCTIONS,
    SEARCH_DELEGATION_INSTRUCTIONS,
    PATENT_RESEARCHER_INSTRUCTIONS,
    NPL_RESEARCHER_INSTRUCTIONS,
    SEMANTIC_RESEARCHER_INSTRUCTIONS,
    STRUCTURED_OUTPUT_ADDENDUM,
    GUARDRAILS_INSTRUCTIONS,
)

# Import tools from unified tools module
from src.tools import (
    get_all_tools,
    get_search_tools,
    get_analysis_tools,
    get_batch_only_tools,
)
from src.tools.registry import get_reflection_tools, get_content_tools, get_citation_tools, get_derwent_tools
from src.config.settings import is_npl_enabled


# =============================================================================
# Logging Configuration
# =============================================================================

_logger = logging.getLogger(__name__)


# =============================================================================
# Module Constants
# =============================================================================

BASE_DIR = Path(__file__).parent
SESSIONS_DIR = Path(__file__).parent.parent.parent / "sessions"

# Research loop limits (configurable)
MAX_CONCURRENT_RESEARCH_UNITS = 4  # Max parallel subagents per round (patent + npl + semantic + citation in Round 2+)
MAX_RESEARCH_ITERATIONS = 5        # Max research loop iterations


# =============================================================================
# Session Management
# =============================================================================

def create_session_workspace(session_id: str | None = None) -> tuple[Path, str]:
    """Create an isolated workspace for a new agent session.
    
    Each session gets its own directory for session-specific outputs only.
    Read-only files (AGENTS.md, skills/) are NOT copied - they're referenced
    directly from the base directory using absolute paths.
    
    Args:
        session_id: Optional custom session ID. If None, generates a UUID.
        
    Returns:
        Tuple of (session_path, session_id)
    """
    if session_id is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = f"{timestamp}_{uuid.uuid4().hex[:8]}"
    
    session_path = SESSIONS_DIR / session_id
    
    # Create fresh session directory
    if session_path.exists():
        shutil.rmtree(session_path)
    session_path.mkdir(parents=True, exist_ok=True)
    
    # Create empty findings directory for this session's outputs
    # This is the ONLY thing that needs to be session-specific
    (session_path / "findings").mkdir(exist_ok=True)
    
    return session_path, session_id


def cleanup_old_sessions(max_age_hours: int = 24, max_sessions: int = 50) -> int:
    """Clean up old session directories.
    
    Args:
        max_age_hours: Remove sessions older than this many hours.
        max_sessions: Maximum number of sessions to keep regardless of age.
        
    Returns:
        Number of sessions cleaned up.
    """
    if not SESSIONS_DIR.exists():
        return 0
    
    sessions = sorted(
        SESSIONS_DIR.iterdir(),
        key=lambda p: p.stat().st_mtime if p.is_dir() else 0,
        reverse=True,  # Newest first
    )
    
    cleaned = 0
    now = datetime.now()
    
    for i, session in enumerate(sessions):
        if not session.is_dir():
            continue
        
        # Keep the newest max_sessions
        if i < max_sessions:
            # Check age only for sessions beyond the count
            continue
        
        # Remove old sessions
        try:
            mtime = datetime.fromtimestamp(session.stat().st_mtime)
            age_hours = (now - mtime).total_seconds() / 3600
            if age_hours > max_age_hours:
                shutil.rmtree(session)
                cleaned += 1
        except (OSError, ValueError):
            pass
    
    return cleaned


# =============================================================================
# Combined Orchestrator Instructions
# =============================================================================

def _strip_npl_references(text: str) -> str:
    """Remove NPL-specific delegation references from prompt text.

    Two-pass approach:
      Pass 1 — Remove multi-line ``task()`` blocks that target ``npl-researcher``.
      Pass 2 — Remove individual lines matching actionable NPL patterns while
               preserving harmless generic mentions.
    """
    import re

    # --- Pass 1: Remove multi-line task() blocks targeting npl-researcher ---
    # Matches task(\n  ...\n  subagent_type="npl-researcher"\n)
    text = re.sub(
        r'task\(\s*\n(?:[^\)]*\n)*?\s*subagent_type\s*=\s*["\']npl-researcher["\']\s*\n\)',
        "",
        text,
    )
    # Also single-line: task(description="...", subagent_type="npl-researcher")
    text = re.sub(
        r'task\([^)]*subagent_type\s*=\s*["\']npl-researcher["\'][^)]*\)',
        "",
        text,
    )

    # --- Pass 2: Line-by-line filtering ---
    # Exact keyword patterns that indicate actionable NPL references
    _NPL_EXACT = {
        "npl-researcher",
        "npl_search",
        "batch_npl_search",
        "npl_queries",
    }
    # Broader patterns (case-insensitive substring matches)
    _NPL_ACTION_PATTERNS = [
        "execute npl",
        "npl keyword search",
        "npl gap-filling",
        "npl academic literature",
        "npl search results",
        "npl record view",
        "npl search findings",
        "suggested npl query",
        "web of science",
        "task(npl",
        "npl patterns",
        "npl focus",
        '"query_type": "npl"',
        "patent + npl + semantic",
        "patent, npl, and semantic",
        "patent and npl searches",
        "patent/npl/semantic",
        "patent, npl, or semantic",
        "patents/npl record view",
        "continue for each npl",
        "npl has wos id",
        "npl databases",
        "npl keyword",
        "npl (web of science)",
        "npl focused",
        "npl refs",
        "npl record view",
        "patent and npl",
        "patent, npl,",
        "npl + keyword",
        "[z] npl",
    ]

    filtered = []
    for line in text.split("\n"):
        lower = line.lower().strip()

        # Check exact keywords
        if any(kw in lower for kw in _NPL_EXACT):
            continue

        # Check action patterns
        if any(pat in lower for pat in _NPL_ACTION_PATTERNS):
            continue

        # Strip lines that are just "- NPL: ..." (actionable bullet points)
        if re.match(r"^\s*[-│•]\s*NPL\b", line):
            continue

        # Strip table rows or lines where "NPL" appears as a column value or type
        # (e.g., "| WOS:000... | NPL | WoS |" or "| NPL Refs |")
        if re.search(r"\|\s*NPL\s*\|", line):
            continue

        filtered.append(line)

    return "\n".join(filtered)


class InMemorySkillsMiddleware(AgentMiddleware):
    """Load skills from source directory into memory (no files written to session dirs).

    Progressive disclosure: only metadata in prompt, full content via read_skill tool.
    Skills are read from the source directory on first use and cached in memory.
    """

    state_schema = SkillsState

    def __init__(
        self,
        skills_source_dir: Path,
        exclude: set[str] | None = None,
    ):
        self._skills_source_dir = skills_source_dir
        self._exclude = exclude or set()
        # name -> (metadata, full_content)
        self._skills_cache: dict[str, tuple[SkillMetadata, str]] = {}
        self._loaded = False
        self.tools = [self._create_read_skill_tool()]

    def _load_skills(self) -> None:
        """Read and parse SKILL.md files from source directory into memory."""
        if self._loaded:
            return

        if not self._skills_source_dir.exists():
            self._loaded = True
            return

        for skill_subdir in sorted(self._skills_source_dir.iterdir()):
            if not skill_subdir.is_dir() or skill_subdir.name in self._exclude:
                continue
            skill_md = skill_subdir / "SKILL.md"
            if skill_md.exists():
                try:
                    content = skill_md.read_text(encoding="utf-8")
                    metadata = _parse_skill_metadata(
                        content,
                        f"/skills/{skill_subdir.name}/SKILL.md",
                        skill_subdir.name,
                    )
                    if metadata:
                        # Override path to direct agent to use read_skill tool
                        metadata["path"] = f'read_skill(name="{metadata["name"]}")'
                        self._skills_cache[metadata["name"]] = (metadata, content)
                except Exception as e:
                    _logger.warning(f"Failed to load skill {skill_subdir.name}: {e}")

        self._loaded = True
        _logger.info(f"Loaded {len(self._skills_cache)} skills into memory")

    def _create_read_skill_tool(self) -> Any:
        """Create a tool that reads full skill content from memory."""
        middleware = self

        @tool
        def read_skill(name: str) -> str:
            """Read the full instructions for a skill by name.

            Use this to access detailed workflows, best practices, and examples
            for a specific skill listed in the Skills System section.

            Args:
                name: The skill name (e.g. "patent-search", "scoping")

            Returns:
                Full SKILL.md content with instructions and examples.
            """
            middleware._load_skills()
            if name in middleware._skills_cache:
                return middleware._skills_cache[name][1]
            available = ", ".join(sorted(middleware._skills_cache.keys()))
            return f"Skill '{name}' not found. Available skills: {available}"

        return read_skill

    async def abefore_agent(
        self, state: Any, runtime: Runtime, config: RunnableConfig,
    ) -> dict[str, Any] | None:
        """Load skills metadata into state (once per session)."""
        if "skills_metadata" in state:
            return None
        await asyncio.to_thread(self._load_skills)
        metadata_list = [m for m, _ in self._skills_cache.values()]
        return {"skills_metadata": metadata_list}

    def modify_request(self, request: ModelRequest) -> ModelRequest:
        """Inject skills metadata into the system prompt."""
        skills_metadata = request.state.get("skills_metadata", [])
        if not skills_metadata:
            return request

        lines = []
        for skill in skills_metadata:
            lines.append(f"- **{skill['name']}**: {skill['description']}")
            lines.append(f'  -> Use `read_skill(name="{skill["name"]}")` for full instructions')
        skills_list = "\n".join(lines)

        skills_section = f"""

## Skills System

You have access to a skills library with specialized workflows and domain knowledge.

**Available Skills:**

{skills_list}

**How to Use Skills (Progressive Disclosure):**

1. Check if a skill matches the current task
2. Call `read_skill(name="skill-name")` to read full instructions
3. Follow the skill's step-by-step workflow
"""
        new_system_message = append_to_system_message(
            request.system_message, skills_section,
        )
        return request.override(system_message=new_system_message)


def get_orchestrator_instructions(
    max_concurrent_research_units: int = MAX_CONCURRENT_RESEARCH_UNITS,
    max_research_iterations: int = MAX_RESEARCH_ITERATIONS,
    emit_structured_json: bool = False,
    npl_enabled: bool = True,
) -> str:
    """Build combined orchestrator instructions from modular prompts.

    This follows the pattern from deepagents/examples/deep_research/agent.py
    where workflow + delegation instructions are combined for the orchestrator.

    Args:
        max_concurrent_research_units: Max parallel subagents per round
        max_research_iterations: Max research loop iterations
        emit_structured_json: If True, append STRUCTURED_OUTPUT_ADDENDUM so the
            LLM emits machine-readable JSON blocks alongside natural text.
            Used by the API server for frontend integration.
            Default False keeps output clean for Studio/UI.
        npl_enabled: If False, strip NPL/Web-of-Science delegation references
            from the orchestrator prompts so the LLM does not attempt to
            delegate to a non-existent npl-researcher subagent.

    Returns:
        Combined instructions string for the orchestrator agent.
    """
    instructions = (
        NOVELTY_WORKFLOW_INSTRUCTIONS.format(
            max_research_iterations=max_research_iterations,
        )
        + "\n\n"
        + "=" * 80
        + "\n\n"
        + SEARCH_DELEGATION_INSTRUCTIONS.format(
            max_concurrent_research_units=max_concurrent_research_units,
            max_research_iterations=max_research_iterations,
        )
    )

    if emit_structured_json:
        instructions += "\n\n" + "=" * 80 + "\n" + STRUCTURED_OUTPUT_ADDENDUM

    # Append safety guardrails (always active, all 12 guardrails)
    instructions += GUARDRAILS_INSTRUCTIONS

    if not npl_enabled:
        instructions = _strip_npl_references(instructions)

    return instructions


# =============================================================================
# Subagent Loading (from subagents.yaml)
# =============================================================================

def load_subagents(
    config_path: Path | None = None,
    backend: Any = None,
    telemetry_source: TelemetryMiddleware | None = None,
    query_log_source: QueryLogMiddleware | None = None,
) -> list[dict]:
    """Load subagent definitions from YAML and wire up tools.

    This follows the pattern from deepagents/examples/content-builder-agent/.

    Args:
        config_path: Path to subagents.yaml. Defaults to BASE_DIR/subagents.yaml.
        backend: Optional FilesystemBackend or BackendFactory. When provided,
            findings tools are replaced with backend-aware versions that
            resolve the backend from ToolRuntime (supporting per-thread
            session isolation).
        telemetry_source: Optional TelemetryMiddleware from the orchestrator.
            When provided, a per-subagent TelemetryMiddleware is created for
            each subagent (sharing the same underlying ResearchTelemetry) so
            that LLM token usage is attributed to the correct agent.

    Returns:
        List of subagent specifications for SubAgentMiddleware.
    """
    if config_path is None:
        config_path = BASE_DIR / "subagents.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"subagents.yaml not found at {config_path}")

    # Map tool names to actual tool objects
    search_tools = {t.name: t for t in get_search_tools()}
    analysis_tools = {t.name: t for t in get_analysis_tools()}
    reflection_tools = {t.name: t for t in get_reflection_tools()}
    content_tools = {t.name: t for t in get_content_tools()}
    citation_tools = {t.name: t for t in get_citation_tools()}
    derwent_tools = {t.name: t for t in get_derwent_tools()}

    # Import findings tools (Phase 3)
    from src.tools.findings import get_findings_tools
    findings_tools = {t.name: t for t in get_findings_tools()}

    available_tools = {
        **search_tools,
        **analysis_tools,
        **reflection_tools,
        **content_tools,
        **citation_tools,
        **derwent_tools,
        **findings_tools,
    }

    # Override plain findings tools with backend-aware versions
    if backend is not None:
        from src.tools.findings import create_backend_findings_tools
        backend_tools = {t.name: t for t in create_backend_findings_tools(backend)}
        available_tools.update(backend_tools)
    
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    subagents = []
    for name, spec in config.items():
        subagent = {
            "name": name,
            "description": spec["description"],
            "system_prompt": spec["system_prompt"],
        }
        if "model" in spec:
            subagent["model"] = spec["model"]
        if "tools" in spec:
            # Wire up tool objects from names
            subagent["tools"] = [
                available_tools[t] for t in spec["tools"]
                if t in available_tools
            ]
            # Report persistence is an orchestrator-only responsibility.
            # Fail fast if any subagent's tool list leaks write access.
            _FORBIDDEN_SUBAGENT_TOOLS = {"write_file", "edit_file"}
            leaked = [t.name for t in subagent["tools"] if t.name in _FORBIDDEN_SUBAGENT_TOOLS]
            if leaked:
                raise ValueError(
                    f"Subagent {name!r} has forbidden tools {leaked}. "
                    "Report persistence must remain orchestrator-only."
                )
        content_filter = ContentFilterMiddleware()
        if telemetry_source is not None:
            # Create a per-subagent TelemetryMiddleware that shares the
            # underlying ResearchTelemetry but has the correct agent_name
            subagent["middleware"] = [
                content_filter,
                TelemetryMiddleware(
                    telemetry=telemetry_source._static_telemetry,
                    telemetry_factory=telemetry_source._telemetry_factory,
                    agent_name=name,
                    backend=backend,
                ),
            ]
        else:
            subagent["middleware"] = [content_filter]
        if query_log_source is not None:
            # Subagents call the search tools — orchestrator-level middleware
            # never sees those tool calls, so we attach a sibling QueryLogMiddleware
            # here that shares the same QueryLogger / logger_factory.
            subagent["middleware"].append(
                QueryLogMiddleware(
                    backend=backend,
                    logger=query_log_source._static_logger,
                    logger_factory=query_log_source._logger_factory,
                )
            )
        subagents.append(subagent)
    
    return subagents


# =============================================================================
# Deep Agent Factory (using deepagents library)
# =============================================================================

def get_default_model(model: str = "gpt-5") -> BaseChatModel:
    """Get the default LLM for the agent using LiteLLM.
    
    LiteLLM provides a unified interface for 100+ LLM providers.
    Model format: "provider/model" or just "model" for OpenAI.
    
    Examples:
        - "gpt-5" or "openai/gpt-5" — OpenAI GPT-5
        - "gpt-4o" — OpenAI GPT-4o
        - "anthropic/claude-sonnet-4-5-20250929" — Claude Sonnet 4.5
        - "gemini/gemini-2.0-flash" — Google Gemini
        - "bedrock/anthropic.claude-v3" — AWS Bedrock
    
    Args:
        model: Model identifier. Defaults to "gpt-5".
        
    Returns:
        A configured ChatLiteLLM instance.
    """
    return ChatLiteLLM(
        model=model,
        temperature=0,
        max_tokens=20000,
        max_retries=3,
    )


def create_deep_agent(
    model: str | BaseChatModel | None = None,
    checkpointer: Checkpointer | None = None,
    use_custom_state: bool = False,
    max_concurrent_research_units: int = MAX_CONCURRENT_RESEARCH_UNITS,
    max_research_iterations: int = MAX_RESEARCH_ITERATIONS,
    session_id: str | None = None,
    reuse_session: bool = False,
    use_backend_factory: bool = False,
    emit_structured_json: bool = False,
) -> tuple[CompiledStateGraph, str]:
    """Create the novelty checker deep agent using deepagents framework.
    
    This follows the pattern from deepagents/examples/deep_research/.
    
    The agent is configured with:
    - memory=["./AGENTS.md"] — Base system prompt from file
    - system_prompt — Additional orchestrator instructions from prompts.py
    - skills=["./skills/"] — SKILL.md files for progressive disclosure
    - tools — Search and analysis tools from tools registry
    - subagents — Loaded from subagents.yaml with researcher prompts
    - backend=FilesystemBackend — Session-isolated for file operations
    
    Key Feature: Session Isolation
    - Each run gets its own workspace directory (sessions/<session_id>/)
    - Prevents cross-run interference from previous artifacts
    - Session directories contain copies of AGENTS.md and skills/
    
    Key Feature: Iterative Research Loop
    - After Gate 2 (Feature Confirmation), enters research loop
    - Delegates to patent/NPL/semantic researchers in parallel
    - Uses think_tool for reflection after each round
    - Continues until coverage target met or max iterations
    
    Args:
        model: The language model to use. Defaults to GPT-5.
            Can be a string like "openai:gpt-4o" or a model instance.
        checkpointer: Optional checkpointer for conversation persistence.
        use_custom_state: If True, use DeepAgentState as context_schema.
            This enables custom state fields (features, references, coverage, etc.)
            Default is False to use deepagents' built-in state management.
        max_concurrent_research_units: Max parallel subagents per research round.
            Default is 3 (patent + NPL + semantic in parallel).
        max_research_iterations: Max research loop iterations before stopping.
            Default is 5.
        session_id: Optional custom session ID for workspace isolation.
            If None, generates a unique session ID based on timestamp + UUID.
        reuse_session: If True and session_id is provided, reuse existing session
            without clearing it. Default False creates fresh session.
        use_backend_factory: If True, use a ThreadAwareBackendFactory that creates
            per-thread session directories. This is required for LangGraph Studio
            where a single graph serves multiple concurrent threads. Default False
            uses a static FilesystemBackend (CLI/API mode).
        emit_structured_json: If True, append structured output instructions so
            the LLM emits machine-readable JSON blocks (json:questions,
            json:features) alongside natural text. Used by the API server for
            frontend integration. Default False for Studio/UI compatibility.

    Returns:
        Tuple of (compiled StateGraph, session_id) - the session_id can be used
        to access the session workspace at sessions/<session_id>/.
    """
    if model is None:
        model = get_default_model()

    # Clean up old sessions periodically (non-blocking)
    try:
        cleanup_old_sessions(max_age_hours=24, max_sessions=50)
    except Exception:
        pass  # Don't fail if cleanup has issues

    # ✅ Phase 0: Default to MemorySaver if no checkpointer provided
    # When running under LangGraph API (langgraph dev), the platform provides
    # its own checkpointer, so we must NOT attach one ourselves.
    # Detect LangGraph API environment by checking for LANGGRAPH_API env var
    # or the presence of langgraph_runtime_inmem in the call stack.
    import os as _os
    _running_under_langgraph_api = _os.environ.get("LANGGRAPH_API") or any(
        "langgraph_api" in (f.filename or "") or "langgraph_runtime" in (f.filename or "")
        for f in __import__("traceback").extract_stack()
    )
    if _running_under_langgraph_api:
        checkpointer = None
        _logger.info("Running under LangGraph API — skipping custom checkpointer")
    elif checkpointer is None:
        checkpointer = MemorySaver()
        _logger.info("✅ Checkpointer created (MemorySaver)")

    # Get tools from registry
    tools = get_all_tools()

    # Optionally use custom state schema
    context_schema = None
    if use_custom_state:
        from src.novelty_checker.state import DeepAgentState
        context_schema = DeepAgentState

    # Build orchestrator instructions from modular prompts
    # (Following Deep Research Agent pattern from deepagents/examples/deep_research/)
    _npl_enabled = is_npl_enabled()
    orchestrator_instructions = get_orchestrator_instructions(
        max_concurrent_research_units=max_concurrent_research_units,
        max_research_iterations=max_research_iterations,
        emit_structured_json=emit_structured_json,
        npl_enabled=_npl_enabled,
    )

    # =========================================================================
    # Backend & middleware creation — two modes:
    #   Factory mode (LangGraph Studio): per-thread session directories
    #   Static mode  (CLI/API):          single session directory
    # =========================================================================

    if use_backend_factory:
        # --- Factory mode: per-thread session isolation ---
        # Each thread_id gets its own session directory under SESSIONS_DIR.
        # The factory is a callable satisfying BackendFactory = Callable[[ToolRuntime], BackendProtocol].
        if session_id is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = f"studio_{timestamp}_{uuid.uuid4().hex[:8]}"

        backend_factory = ThreadAwareBackendFactory(
            sessions_dir=SESSIONS_DIR,
            default_session_id=session_id,
        )
        backend = backend_factory  # callable — deepagents resolves per tool call

        findings_middleware = FindingsPersistenceMiddleware(
            backend=backend_factory,
            enabled=True,
            capture_threshold=1,
        )

        def _make_telemetry(thread_id: str) -> ResearchTelemetry:
            t_path = SESSIONS_DIR / thread_id / "telemetry.json"
            return ResearchTelemetry(session_id=thread_id, output_path=t_path)

        telemetry_middleware = TelemetryMiddleware(
            telemetry_factory=_make_telemetry,
            backend=backend_factory,
        )

        patent_tracking_middleware = PatentTrackingMiddleware(
            backend=backend_factory,
            tracker_factory=lambda tid: PatentTracker(session_id=tid),
        )

        query_log_middleware = QueryLogMiddleware(
            backend=backend_factory,
            logger_factory=lambda tid: QueryLogger(session_id=tid),
        )

        feature_gate_middleware = FeatureConfirmationMiddleware(backend=backend_factory)
        autonomy_middleware = AutonomousResearchMiddleware(backend=backend_factory)
        continuation_middleware = ResearchContinuationMiddleware(
            backend=backend_factory,
            max_rounds=max_research_iterations,
            min_rounds=2,
        )
        citation_middleware = CitationEnforcementMiddleware(backend=backend_factory)
        report_persistence_middleware = ReportPersistenceMiddleware(backend=backend_factory)
        self_citation_guard_middleware = SelfCitationGuardMiddleware(backend=backend_factory)
        full_text_evidence_middleware = FullTextEvidenceMiddleware(backend=backend_factory)

        # Guardrails middleware (behavioural pre-processing + hard output filter)
        guardrails_prompt_mw = GuardrailsPromptMiddleware(backend=backend_factory)
        guardrails_output_mw = GuardrailsOutputFilterMiddleware()

        _logger.info(
            f"Factory mode: per-thread sessions under {SESSIONS_DIR}, "
            f"default={session_id}"
        )

    else:
        # --- Static mode: single session directory ---
        # Create session-isolated workspace
        # This ensures each run has a clean slate without artifacts from previous runs
        if reuse_session and session_id:
            session_path = SESSIONS_DIR / session_id
            if not session_path.exists():
                session_path, session_id = create_session_workspace(session_id)
        else:
            session_path, session_id = create_session_workspace(session_id)

        # Create FilesystemBackend for persistence pointing to SESSION workspace
        # virtual_mode=True ensures paths like "/scope.md" are relative to session_path
        backend = FilesystemBackend(
            root_dir=session_path,
            virtual_mode=True,
        )

        # Create FindingsPersistenceMiddleware (Phase 4)
        # This automatically captures search tool results to prevent findings loss
        findings_middleware = FindingsPersistenceMiddleware(
            backend=backend,
            enabled=True,
            capture_threshold=1,  # Capture even single-reference results
        )

        # ✅ Phase 2: Create telemetry middleware for observability
        # Tracks tool calls, success rates, and session metrics
        telemetry_path = session_path / "telemetry.json"
        telemetry = ResearchTelemetry(
            session_id=session_id,
            output_path=telemetry_path,
        )
        telemetry_middleware = TelemetryMiddleware(telemetry=telemetry, backend=backend)
        _logger.info(f"Telemetry enabled: {telemetry_path}")

        # Patent lifecycle tracking middleware (passive observer)
        patent_tracking_middleware = PatentTrackingMiddleware(
            backend=backend,
            tracker=PatentTracker(session_id=session_id),
        )

        # Query-log middleware (writes /queries_log.md after each search call)
        query_log_middleware = QueryLogMiddleware(
            backend=backend,
            logger=QueryLogger(session_id=session_id),
        )

        # Feature confirmation gate middleware
        # Enforces Gate 2: blocks research if features defined but not confirmed by user
        feature_gate_middleware = FeatureConfirmationMiddleware(backend=backend)

        # Autonomous research enforcement middleware
        # Enforces autonomous operation after Gate 2: prevents agent from asking user
        autonomy_middleware = AutonomousResearchMiddleware(backend=backend)

        # Research continuation enforcement middleware
        # Detects when orchestrator receives subagent results but doesn't iterate
        continuation_middleware = ResearchContinuationMiddleware(
            backend=backend,
            max_rounds=max_research_iterations,
            min_rounds=2,
        )

        # Phase 3: Create citation enforcement middleware
        # Reads findings accumulator to detect A-refs + coverage gaps,
        # injects directive into system prompt when citation-researcher should be delegated
        citation_middleware = CitationEnforcementMiddleware(backend=backend)
        report_persistence_middleware = ReportPersistenceMiddleware(backend=backend)
        self_citation_guard_middleware = SelfCitationGuardMiddleware(backend=backend)
        full_text_evidence_middleware = FullTextEvidenceMiddleware(backend=backend)

        # Guardrails middleware (behavioural pre-processing + hard output filter)
        guardrails_prompt_mw = GuardrailsPromptMiddleware(backend=backend)
        guardrails_output_mw = GuardrailsOutputFilterMiddleware()

        _logger.info(f"Static mode: session {session_id} at {session_path}")

    # Replace plain findings tools with backend-aware versions on the orchestrator
    from src.tools.findings import create_backend_findings_tools
    backend_findings_tools = create_backend_findings_tools(backend)
    backend_tool_names = {t.name for t in backend_findings_tools}
    tools = [t for t in tools if t.name not in backend_tool_names] + backend_findings_tools

    # Load subagents from YAML — pass backend so subagents also get
    # backend-aware findings tools (save_round_findings, detect_diminishing_returns)
    # Pass telemetry_source so each subagent gets its own TelemetryMiddleware
    # with the correct agent_name (sharing the same ResearchTelemetry instance)
    subagents = load_subagents(
        backend=backend,
        telemetry_source=telemetry_middleware,
        query_log_source=query_log_middleware,
    )

    if not _npl_enabled:
        subagents = [s for s in subagents if s["name"] != "npl-researcher"]
        _logger.info("NPL search disabled — npl-researcher subagent excluded")

    # =========================================================================
    # Load AGENTS.md content directly (Windows path compatibility fix)
    # =========================================================================
    # The deepagents MemoryMiddleware uses FilesystemBackend.download_files()
    # which fails on Windows absolute paths when virtual_mode=True (the backend
    # rejects paths outside its session root directory). Instead of passing
    # file paths to memory=[], we pre-load the content and include it in the
    # system_prompt. This approach also works cross-platform.
    agents_md_path = BASE_DIR / "AGENTS.md"
    try:
        agents_md_content = agents_md_path.read_text(encoding="utf-8")
        _logger.info(f"Loaded AGENTS.md ({len(agents_md_content)} chars) from {agents_md_path}")
    except FileNotFoundError:
        _logger.warning(f"AGENTS.md not found at {agents_md_path}, using empty content")
        agents_md_content = ""

    # Strip NPL delegation references from AGENTS.md when disabled
    if not _npl_enabled:
        agents_md_content = _strip_npl_references(agents_md_content)

    # Combine AGENTS.md + orchestrator instructions into system prompt
    # Skills are loaded adaptively by InMemorySkillsMiddleware (injected via modify_request)
    combined_system_prompt = f"""<agent_memory>
{agents_md_content}
</agent_memory>
{orchestrator_instructions}"""

    # In-memory skills middleware: reads SKILL.md files from source directory,
    # caches in memory, provides read_skill tool for on-demand access.
    # No files are written to session directories.
    exclude_skills = set() if _npl_enabled else {"npl-search"}
    in_memory_skills_middleware = InMemorySkillsMiddleware(
        skills_source_dir=BASE_DIR / "skills",
        exclude=exclude_skills,
    )

    # Create the deep agent using deepagents framework
    graph = _create_deep_agent(
        model=model,
        memory=[],                         # Skip MemoryMiddleware file loading (content pre-loaded above)
        system_prompt=combined_system_prompt,  # AGENTS.md + orchestrator instructions combined
        skills=None,                       # We handle skills entirely via InMemorySkillsMiddleware
        tools=tools,                      # Search and analysis tools
        subagents=subagents,              # From subagents.yaml
        backend=backend,                  # FilesystemBackend or factory for session-isolated persistence
        middleware=[
            in_memory_skills_middleware,    # 1: Progressive skills (in-memory, no disk writes)
            findings_middleware,            # 2: Auto-capture findings to filesystem
            patent_tracking_middleware,     # 3: Track patent lifecycle (passive observer)
            query_log_middleware,           # 4: Write /queries_log.md artifact (passive observer)
            feature_gate_middleware,        # 5: Enforce feature confirmation gate
            guardrails_prompt_mw,          # 6: Behavioral guardrails (pre-processing)
            autonomy_middleware,            # 7: Enforce autonomous mode post-Gate-2
            continuation_middleware,        # 8: Enforce research loop continuation
            citation_middleware,            # 9: Read findings, inject citation directives
            self_citation_guard_middleware, # 10: Demote inventor's-own filings before report wrap-up
            full_text_evidence_middleware,  # 11: Force get_patent_details on A/B refs before Feature Matrix
            report_persistence_middleware,  # 12: Force write_file('/final_report.md') before wrap-up
            guardrails_output_mw,          # 13: Hard output filter (post-processing)
            telemetry_middleware,           # 14: Track metrics (outermost)
        ],
        checkpointer=checkpointer,
        context_schema=context_schema,
    )

    return graph, session_id


# =============================================================================
# Convenience Functions
# =============================================================================

def check_novelty(
    idea: str,
    model: str | BaseChatModel | None = None,
    thread_id: str = "default",
    session_id: str | None = None,
    use_backend_factory: bool = False,
) -> dict:
    """Check the novelty of an idea using the deep agent.

    Args:
        idea: The customer's invention idea to evaluate
        model: Optional language model override
        thread_id: Thread ID for conversation persistence
        session_id: Optional session ID for workspace isolation.
            If None, creates a new session for this novelty check.
        use_backend_factory: If True, use per-thread backend factory (same as
            LangGraph Studio). Default False for backward compatibility.

    Returns:
        Dict containing:
        - result: The final state from the agent
        - session_id: The session ID (for accessing workspace at sessions/<session_id>/)
    """
    agent, session_id = create_deep_agent(
        model=model, session_id=session_id, use_backend_factory=use_backend_factory
    )
    
    initial_state = {
        "messages": [HumanMessage(content=f"""Please check the novelty of this invention:

{idea}

Start by scoping the invention and creating a plan using write_todos.""")],
    }
    
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 500}

    result = agent.invoke(initial_state, config=config)
    
    return {"result": result, "session_id": session_id}


# =============================================================================
# Legacy Compatibility
# =============================================================================

# Keep the old function name for backward compatibility
create_novelty_checker_graph = create_deep_agent


# =============================================================================
# Legacy: Inline subagent specs (kept for reference, now in subagents.yaml)
# =============================================================================
# See subagents.yaml for the externalized definitions.
