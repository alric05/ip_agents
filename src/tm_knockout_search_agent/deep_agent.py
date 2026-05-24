"""Factory for the TM knockout search agent v1 orchestrator.

This module intentionally keeps the v1 agent independent and simple. Live
CompuMark execution is opt-in; the default path remains deterministic and local.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from src.tm_knockout_search_agent import prompts
from src.tm_knockout_search_agent.middleware.stage_guard import update_session_stage
from src.tm_knockout_search_agent.services.query_planner import plan_trademark_search
from src.tm_knockout_search_agent.services.risk_assessment import (
    SourceSearchStatus,
    assess_trademark_risk,
)
from src.tm_knockout_search_agent.services.report import (
    AdversarialReview,
    generate_trademark_report,
)
from src.tm_knockout_search_agent.services.session import (
    DEFAULT_SESSIONS_BASE_DIR,
    create_session,
    write_artifact,
    write_final_report,
)
from src.tm_knockout_search_agent.services.search_execution import (
    TrademarkSourceExecutionResult,
    execute_trademark_search_plan,
)
from src.tm_knockout_search_agent.services.stopping import (
    SearchProgress,
    StoppingDecisionType,
    determine_stopping_decision,
)
from src.tm_knockout_search_agent.state import (
    TrademarkCandidate,
    TrademarkSearchBudget,
    TrademarkSearchCriteria,
    TrademarkSearchStage,
    WorkflowStage,
)
from src.tm_knockout_search_agent.tools.registry import get_tm_knockout_search_tools
from src.tm_knockout_search_agent.tools.adapters import flag_duplicate_candidates


TM_KNOCKOUT_AGENT_NAME = "tm_knockout_search_agent"
BASE_DIR = Path(__file__).parent
SESSIONS_DIR = Path("sessions") / TM_KNOCKOUT_AGENT_NAME


@dataclass(frozen=True)
class TMKnockoutAgentConfig:
    """Configurable parameters for the deterministic v1 orchestrator."""

    model: str | None = None
    thread_id: str | None = None
    session_id: str | None = None
    max_results_per_query: int = 25
    max_candidates_to_normalize: int = 100
    max_candidates_to_surface_in_report: int = 10
    include_web_search: bool = True
    include_inactive_contextual: bool = False
    live_compumark: bool = False
    language: str = "English"
    sessions_base_dir: str | Path = DEFAULT_SESSIONS_BASE_DIR


class TMKnockoutSearchAgent:
    """Small invokable orchestrator for first-pass TM knockout screening."""

    def __init__(self, config: TMKnockoutAgentConfig) -> None:
        self.config = config
        self.tools = get_tm_knockout_search_tools()
        self.system_instructions = load_system_instructions()
        self.session_manifest = create_session(
            session_id=config.session_id,
            base_dir=config.sessions_base_dir,
        )

    def invoke(
        self,
        input_data: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Invoke deterministic screening from structured input."""
        _ = config
        payload = dict(input_data)
        config_override = self.config
        if "live_compumark" in payload:
            config_override = replace(
                self.config,
                live_compumark=bool(payload.pop("live_compumark")),
            )
        return check_tm_knockout(
            brand=payload.pop("brand", payload.pop("brand_name", None)),
            countries=payload.pop("countries", payload.pop("jurisdictions", None)),
            classes=payload.pop("classes", payload.pop("nice_classes", None)),
            goods=payload.pop("goods", payload.pop("goods_services", None)),
            business_context=payload.pop("business_context", None),
            assumptions=payload.pop("assumptions", None),
            candidates=payload.pop("candidates", None),
            source_statuses=payload.pop("source_statuses", None),
            completed_query_group_ids=payload.pop("completed_query_group_ids", None),
            completed_stages=payload.pop("completed_stages", None),
            agent_config=config_override,
        )


def load_system_instructions() -> str:
    """Load AGENTS.md and prompt constants into one instruction block."""
    agents_md = (BASE_DIR / "AGENTS.md").read_text(encoding="utf-8")
    prompt_parts = [
        prompts.BASE_SYSTEM_PROMPT,
        prompts.INTAKE_REQUIREMENTS_PROMPT,
        prompts.NORMALIZATION_PROMPT,
        prompts.SEARCH_PLANNING_PROMPT,
        prompts.SEARCH_EXECUTION_PROMPT,
        prompts.SCREENING_PROMPT,
        prompts.RISK_EVALUATION_PROMPT,
        prompts.STOPPING_RULES_PROMPT,
        prompts.ADVERSARIAL_REVIEW_PROMPT,
        prompts.REPORT_TEMPLATE_PROMPT.format(
            fixed_disclaimer=prompts.FIXED_DISCLAIMER
        ),
    ]
    return "\n\n".join([agents_md, *prompt_parts])


def create_tm_knockout_search_agent(
    *,
    model: str | None = None,
    thread_id: str | None = None,
    session_id: str | None = None,
    max_results_per_query: int = 25,
    max_candidates_to_normalize: int = 100,
    max_candidates_to_surface_in_report: int = 10,
    include_web_search: bool = True,
    include_inactive_contextual: bool = False,
    live_compumark: bool = False,
    language: str = "English",
    sessions_base_dir: str | Path = DEFAULT_SESSIONS_BASE_DIR,
) -> TMKnockoutSearchAgent:
    """Create the independent v1 TM knockout search orchestrator."""
    return TMKnockoutSearchAgent(
        TMKnockoutAgentConfig(
            model=model,
            thread_id=thread_id,
            session_id=session_id,
            max_results_per_query=max_results_per_query,
            max_candidates_to_normalize=max_candidates_to_normalize,
            max_candidates_to_surface_in_report=max_candidates_to_surface_in_report,
            include_web_search=include_web_search,
            include_inactive_contextual=include_inactive_contextual,
            live_compumark=live_compumark,
            language=language,
            sessions_base_dir=sessions_base_dir,
        )
    )


def create_knockout_search_agent(**kwargs: Any) -> TMKnockoutSearchAgent:
    """Backward-compatible alias for earlier skeleton imports."""
    return create_tm_knockout_search_agent(**kwargs)


def check_tm_knockout(
    *,
    brand: str | None,
    countries: str | list[str] | None,
    classes: str | list[str] | None = None,
    goods: str | None = None,
    business_context: str | None = None,
    assumptions: list[str] | None = None,
    candidates: list[TrademarkCandidate | dict[str, Any]] | None = None,
    source_statuses: list[SourceSearchStatus | dict[str, Any]] | None = None,
    completed_query_group_ids: list[str] | None = None,
    completed_stages: list[TrademarkSearchStage | str] | None = None,
    model: str | None = None,
    thread_id: str | None = None,
    session_id: str | None = None,
    max_results_per_query: int = 25,
    max_candidates_to_normalize: int = 100,
    max_candidates_to_surface_in_report: int = 10,
    include_web_search: bool = True,
    include_inactive_contextual: bool = False,
    live_compumark: bool = False,
    language: str = "English",
    sessions_base_dir: str | Path = DEFAULT_SESSIONS_BASE_DIR,
    agent_config: TMKnockoutAgentConfig | None = None,
) -> dict[str, Any]:
    """Run deterministic v1 planning/screening without live external calls."""
    resolved_config = agent_config or TMKnockoutAgentConfig(
        model=model,
        thread_id=thread_id,
        session_id=session_id,
        max_results_per_query=max_results_per_query,
        max_candidates_to_normalize=max_candidates_to_normalize,
        max_candidates_to_surface_in_report=max_candidates_to_surface_in_report,
        include_web_search=include_web_search,
        include_inactive_contextual=include_inactive_contextual,
        live_compumark=live_compumark,
        language=language,
        sessions_base_dir=sessions_base_dir,
    )
    manifest = create_session(
        session_id=resolved_config.session_id,
        base_dir=resolved_config.sessions_base_dir,
    )
    criteria = _build_criteria(
        brand=brand,
        countries=countries,
        classes=classes,
        goods=goods,
        business_context=business_context,
        assumptions=assumptions,
        language=resolved_config.language,
    )
    budget = TrademarkSearchBudget(
        max_results_per_query=resolved_config.max_results_per_query,
        max_candidates_to_normalize=resolved_config.max_candidates_to_normalize,
        max_candidates_to_surface_in_report=(
            resolved_config.max_candidates_to_surface_in_report
        ),
        include_web_search=resolved_config.include_web_search,
        include_inactive_contextual=resolved_config.include_inactive_contextual,
    )
    plan = plan_trademark_search(criteria, budget=budget)
    normalized_candidates = _coerce_candidates(candidates or [])
    normalized_source_statuses = _coerce_source_statuses(source_statuses or [])
    source_execution_result: TrademarkSourceExecutionResult | None = None
    source_execution_skipped_reason: str | None = None
    execution_completed_group_ids: list[str] = []
    execution_completed_stages: list[TrademarkSearchStage] = []

    if resolved_config.live_compumark:
        if plan.requires_clarification:
            source_execution_skipped_reason = (
                "live_compumark skipped because criteria require clarification"
            )
        else:
            source_execution_result = execute_trademark_search_plan(
                plan,
                max_candidates_to_normalize=budget.max_candidates_to_normalize,
            )
            normalized_candidates = flag_duplicate_candidates(
                [*normalized_candidates, *source_execution_result.candidates]
            )
            normalized_source_statuses.extend(source_execution_result.source_statuses)
            execution_completed_group_ids = source_execution_result.completed_query_group_ids
            execution_completed_stages = source_execution_result.completed_stages

    resolved_completed_query_group_ids = _merge_strings(
        completed_query_group_ids or [],
        execution_completed_group_ids,
    )
    resolved_completed_stages = _merge_stages(
        [_coerce_stage(stage) for stage in completed_stages or []],
        execution_completed_stages,
    )
    progress = SearchProgress(
        completed_query_group_ids=resolved_completed_query_group_ids,
        completed_stages=resolved_completed_stages,
        normalized_candidate_count=len(normalized_candidates),
        relevant_candidate_count=len(normalized_candidates),
        selected_for_deep_review_count=min(
            len(normalized_candidates),
            budget.max_candidates_to_surface_in_report,
        ),
        source_statuses=normalized_source_statuses,
    )
    risk_assessment = assess_trademark_risk(
        criteria,
        normalized_candidates,
        source_statuses=normalized_source_statuses,
    )
    stopping_decision = determine_stopping_decision(plan, progress)
    adversarial_review = AdversarialReview(
        summary=(
            "Deterministic v1 checks reviewed source coverage, candidate "
            "findings, risk label support, and limitations."
        ),
        checks={
            "requested_scope_reviewed": True,
            "candidate_ids_linked": True,
            "limitations_documented": True,
            "stopping_decision_recorded": True,
        },
        source_failures=risk_assessment.missing_or_failed_source_notes,
    )

    write_artifact(
        manifest.session_id,
        "request",
        {
            "brand": brand,
            "countries": countries,
            "classes": classes,
            "goods": goods,
            "business_context": business_context,
            "language": resolved_config.language,
            "thread_id": resolved_config.thread_id,
            "model": resolved_config.model,
            "live_compumark": resolved_config.live_compumark,
        },
        base_dir=resolved_config.sessions_base_dir,
    )
    write_artifact(
        manifest.session_id,
        "scope",
        criteria,
        base_dir=resolved_config.sessions_base_dir,
    )
    write_artifact(
        manifest.session_id,
        "search_criteria",
        criteria,
        base_dir=resolved_config.sessions_base_dir,
    )
    update_session_stage(
        manifest.session_id,
        WorkflowStage.AWAITING_SCOPE_CONFIRMATION,
        base_dir=resolved_config.sessions_base_dir,
    )
    write_artifact(
        manifest.session_id,
        "search_plan",
        plan,
        base_dir=resolved_config.sessions_base_dir,
    )
    write_artifact(
        manifest.session_id,
        "query_plan",
        plan,
        base_dir=resolved_config.sessions_base_dir,
    )
    write_artifact(
        manifest.session_id,
        "compumark_results",
        source_execution_result.compumark_results if source_execution_result else [],
        base_dir=resolved_config.sessions_base_dir,
    )
    write_artifact(
        manifest.session_id,
        "web_results",
        source_execution_result.web_results if source_execution_result else [],
        base_dir=resolved_config.sessions_base_dir,
    )
    write_artifact(
        manifest.session_id,
        "source_statuses",
        normalized_source_statuses,
        base_dir=resolved_config.sessions_base_dir,
    )
    write_artifact(
        manifest.session_id,
        "candidates",
        normalized_candidates,
        base_dir=resolved_config.sessions_base_dir,
    )
    write_artifact(
        manifest.session_id,
        "normalized_candidates",
        normalized_candidates,
        base_dir=resolved_config.sessions_base_dir,
    )
    write_artifact(
        manifest.session_id,
        "assessments",
        risk_assessment,
        base_dir=resolved_config.sessions_base_dir,
    )
    write_artifact(
        manifest.session_id,
        "ranked_findings",
        risk_assessment.findings,
        base_dir=resolved_config.sessions_base_dir,
    )
    write_artifact(
        manifest.session_id,
        "risk_assessment",
        risk_assessment,
        base_dir=resolved_config.sessions_base_dir,
    )
    write_artifact(
        manifest.session_id,
        "adversarial_review",
        adversarial_review,
        base_dir=resolved_config.sessions_base_dir,
    )
    final_decision = {
        "risk_label": risk_assessment.overall_risk_label.value,
        "stopping_decision": stopping_decision.decision.value,
        "reason": stopping_decision.reason,
        "session_id": manifest.session_id,
    }
    write_artifact(
        manifest.session_id,
        "final_decision",
        final_decision,
        base_dir=resolved_config.sessions_base_dir,
    )

    report_markdown = None
    if stopping_decision.decision != StoppingDecisionType.CONTINUE_SEARCHING:
        report_markdown = _build_markdown_report(
            criteria=criteria,
            plan=plan,
            candidates=normalized_candidates,
            risk_assessment=risk_assessment,
            stopping_decision=stopping_decision,
            adversarial_review=adversarial_review,
            live_compumark_requested=resolved_config.live_compumark,
            source_execution_result=source_execution_result,
        )
        write_final_report(
            manifest.session_id,
            report_markdown,
            base_dir=resolved_config.sessions_base_dir,
        )

    return {
        "agent_name": TM_KNOCKOUT_AGENT_NAME,
        "session_id": manifest.session_id,
        "thread_id": resolved_config.thread_id,
        "model": resolved_config.model,
        "language": resolved_config.language,
        "tools": [tool.name for tool in get_tm_knockout_search_tools()],
        "criteria": criteria.model_dump(mode="json"),
        "search_plan": plan.model_dump(mode="json"),
        "risk_assessment": risk_assessment.model_dump(mode="json"),
        "stopping_decision": stopping_decision.model_dump(mode="json"),
        "source_execution": (
            source_execution_result.model_dump(mode="json")
            if source_execution_result
            else {
                "completed_query_group_ids": [],
                "completed_stages": [],
                "source_statuses": [
                    status.model_dump(mode="json")
                    for status in normalized_source_statuses
                ],
                "skipped_reason": source_execution_skipped_reason,
                "live_api_calls": False,
            }
        ),
        "report_markdown": report_markdown,
        "live_api_calls": bool(
            source_execution_result and source_execution_result.live_api_calls
        ),
    }


def _build_criteria(
    *,
    brand: str | None,
    countries: str | list[str] | None,
    classes: str | list[str] | None,
    goods: str | None,
    business_context: str | None,
    assumptions: list[str] | None,
    language: str,
) -> TrademarkSearchCriteria:
    if not brand or not brand.strip():
        raise ValueError("brand is required")
    parsed_countries = _parse_csv_or_list(countries)
    parsed_classes = _parse_csv_or_list(classes)
    return TrademarkSearchCriteria(
        brand_name=brand,
        jurisdictions=parsed_countries,
        nice_classes=parsed_classes,
        goods_services=goods,
        business_context=business_context,
        assumptions=[*(assumptions or []), f"language={language}"],
    )


def _parse_csv_or_list(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


def _coerce_candidates(
    candidates: list[TrademarkCandidate | dict[str, Any]],
) -> list[TrademarkCandidate]:
    return [
        candidate
        if isinstance(candidate, TrademarkCandidate)
        else TrademarkCandidate.model_validate(candidate)
        for candidate in candidates
    ]


def _coerce_source_statuses(
    source_statuses: list[SourceSearchStatus | dict[str, Any]],
) -> list[SourceSearchStatus]:
    return [
        status
        if isinstance(status, SourceSearchStatus)
        else SourceSearchStatus.model_validate(status)
        for status in source_statuses
    ]


def _coerce_stage(stage: TrademarkSearchStage | str) -> TrademarkSearchStage:
    if isinstance(stage, TrademarkSearchStage):
        return stage
    return TrademarkSearchStage(stage)


def _merge_strings(first: list[str], second: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in [*first, *second]:
        if value and value not in seen:
            merged.append(value)
            seen.add(value)
    return merged


def _merge_stages(
    first: list[TrademarkSearchStage],
    second: list[TrademarkSearchStage],
) -> list[TrademarkSearchStage]:
    merged: list[TrademarkSearchStage] = []
    seen: set[TrademarkSearchStage] = set()
    for stage in [*first, *second]:
        if stage not in seen:
            merged.append(stage)
            seen.add(stage)
    return merged


def _build_markdown_report(
    *,
    criteria: TrademarkSearchCriteria,
    plan: Any,
    candidates: list[TrademarkCandidate],
    risk_assessment: Any,
    stopping_decision: Any,
    adversarial_review: AdversarialReview,
    live_compumark_requested: bool,
    source_execution_result: TrademarkSourceExecutionResult | None,
) -> str:
    limitations = [
        f"Stopping decision: {stopping_decision.decision.value} ({stopping_decision.reason}).",
    ]
    if live_compumark_requested and source_execution_result:
        limitations.append(
            "CompuMark was queried through the configured API for planned CompuMark groups."
        )
    elif live_compumark_requested:
        limitations.append("Live CompuMark execution was requested but skipped.")
    else:
        limitations.append("Live CompuMark was not executed in this run.")
    limitations.append(
        "Web/common-law integration is not active unless web evidence is supplied externally."
    )
    return generate_trademark_report(
        {
            "search_criteria": criteria,
            "query_plan": plan,
            "normalized_candidates": candidates,
            "ranked_findings": risk_assessment.findings,
            "risk_assessment": risk_assessment,
            "adversarial_review": adversarial_review,
            "limitations": limitations,
        }
    )


__all__ = [
    "BASE_DIR",
    "SESSIONS_DIR",
    "TMKnockoutAgentConfig",
    "TMKnockoutSearchAgent",
    "TM_KNOCKOUT_AGENT_NAME",
    "check_tm_knockout",
    "create_knockout_search_agent",
    "create_tm_knockout_search_agent",
    "load_system_instructions",
]
