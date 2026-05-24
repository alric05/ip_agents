# Novelty Checker Multi-Agent System
# A LangGraph-based system inspired by deepagents design patterns
# for checking if a customer's idea is novel.
#
# This implementation uses a custom deep agent pattern with:
# - TodoListMiddleware for planning (replaces separate planner agent)
# - SkillsMiddleware for progressive skill disclosure
# - SubAgentMiddleware for hierarchical task delegation
# - Session-isolated storage to prevent cross-run interference

from src.novelty_checker.deep_agent import (
    create_deep_agent,
    create_novelty_checker_graph,  # Legacy alias
    check_novelty,
    create_session_workspace,
    cleanup_old_sessions,
    SESSIONS_DIR,
    BASE_DIR,
)
from src.novelty_checker.eval_runner import (
    run_novelty_check_e2e,
    EvalRunResult,
    RunPhase,
    GateType,
)
from src.novelty_checker.state import DeepAgentState, AgentState
from src.novelty_checker.utils.report_coverage import (
    CoverageResult,
    verify_report_coverage_from_path,
)

__all__ = [
    "create_deep_agent",
    "create_novelty_checker_graph",
    "check_novelty",
    "create_session_workspace",
    "cleanup_old_sessions",
    "SESSIONS_DIR",
    "BASE_DIR",
    "run_novelty_check_e2e",
    "EvalRunResult",
    "RunPhase",
    "GateType",
    "DeepAgentState",
    "AgentState",
    "CoverageResult",
    "verify_report_coverage_from_path",
]
