"""Mocked end-to-end runner for the TM knockout search agent.

The runner exercises the deterministic v1 workflow with supplied mock source
outputs. It does not call CompuMark, web search, LangGraph, or an LLM.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import Field

from src.tm_knockout_search_agent.services.query_planner import plan_trademark_search
from src.tm_knockout_search_agent.services.report import (
    AdversarialReview,
    generate_trademark_report,
)
from src.tm_knockout_search_agent.services.report_validator import (
    validate_trademark_report,
)
from src.tm_knockout_search_agent.services.risk_assessment import (
    SourceSearchStatus,
    assess_trademark_risk,
)
from src.tm_knockout_search_agent.services.session import (
    DEFAULT_SESSIONS_BASE_DIR,
    artifact_path,
    create_session,
    read_final_report,
    session_dir_for,
    write_artifact,
    write_final_report,
)
from src.tm_knockout_search_agent.services.stopping import (
    SearchProgress,
    determine_stopping_decision,
)
from src.tm_knockout_search_agent.state import (
    ArtifactModel,
    TrademarkCandidate,
    TrademarkSearchBudget,
    TrademarkSearchCriteria,
)
from src.tm_knockout_search_agent.tools.adapters import (
    flag_duplicate_candidates,
    normalize_compumark_result,
    normalize_web_common_law_result,
)


ProgressCallback = Callable[[int, str, None, str], None]


class MockEvalStatus(str, Enum):
    """Machine-readable mocked runner completion status."""

    COMPLETED = "COMPLETED"
    INSUFFICIENT_INPUT = "INSUFFICIENT_INPUT"
    ERROR = "ERROR"


class MockEvalRunResult(ArtifactModel):
    """Result returned by the mocked TM knockout E2E runner."""

    status: MockEvalStatus
    final_risk_label: str | None = None
    final_report: str | None = None
    session_id: str
    session_path: str
    artifacts: dict[str, str] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    source_failure_status: list[dict[str, Any]] = Field(default_factory=list)
    clarification_reasons: list[str] = Field(default_factory=list)
    live_api_calls: bool = False
    steps_completed: int = 0


def run_tm_knockout_mock_e2e(
    *,
    brand_name: str | None,
    countries: str | list[str] | None = None,
    regional_systems: str | list[str] | None = None,
    classes: str | list[str] | None = None,
    goods_services: str | None = None,
    business_context: str | None = None,
    session_id: str | None = None,
    thread_id: str | None = None,
    max_steps: int | None = None,
    max_turns: int | None = None,
    progress_callback: ProgressCallback | None = None,
    mock_compumark_results: list[Mapping[str, Any]] | None = None,
    mock_web_results: list[Mapping[str, Any]] | None = None,
    mock_source_statuses: list[SourceSearchStatus | Mapping[str, Any]] | None = None,
    max_results_per_query: int = 25,
    max_candidates_to_normalize: int = 100,
    max_candidates_to_surface_in_report: int = 10,
    include_web_search: bool = True,
    include_inactive_contextual: bool = False,
    sessions_base_dir: str | Path = DEFAULT_SESSIONS_BASE_DIR,
) -> MockEvalRunResult:
    """Run a complete mocked trademark knockout screening workflow."""
    step_limit = max_steps if max_steps is not None else max_turns
    step_limit = step_limit or 20
    step_counter = _StepCounter(step_limit, progress_callback)
    errors: list[str] = []

    manifest = create_session(session_id=session_id, base_dir=sessions_base_dir)
    session_path = session_dir_for(manifest.session_id, base_dir=sessions_base_dir)

    try:
        step_counter.tick("INTAKE", "Writing request artifact")
        request_payload = {
            "brand_name": brand_name,
            "countries": countries,
            "regional_systems": regional_systems,
            "classes": classes,
            "goods_services": goods_services,
            "business_context": business_context,
            "thread_id": thread_id,
            "mocked": True,
        }
        write_artifact(
            manifest.session_id,
            "request",
            request_payload,
            base_dir=sessions_base_dir,
        )

        step_counter.tick("NORMALIZE", "Creating search criteria")
        criteria = _build_criteria(
            brand_name=brand_name,
            countries=countries,
            regional_systems=regional_systems,
            classes=classes,
            goods_services=goods_services,
            business_context=business_context,
        )
        write_artifact(
            manifest.session_id,
            "search_criteria",
            criteria,
            base_dir=sessions_base_dir,
        )
        write_artifact(
            manifest.session_id,
            "scope",
            criteria,
            base_dir=sessions_base_dir,
        )

        if criteria.requires_clarification:
            final_decision = {
                "status": MockEvalStatus.INSUFFICIENT_INPUT.value,
                "risk_label": None,
                "clarification_reasons": criteria.clarification_reasons,
                "live_api_calls": False,
            }
            write_artifact(
                manifest.session_id,
                "final_decision",
                final_decision,
                base_dir=sessions_base_dir,
            )
            return MockEvalRunResult(
                status=MockEvalStatus.INSUFFICIENT_INPUT,
                session_id=manifest.session_id,
                session_path=str(session_path),
                artifacts=_existing_artifacts(manifest.session_id, base_dir=sessions_base_dir),
                clarification_reasons=criteria.clarification_reasons,
                live_api_calls=False,
                steps_completed=step_counter.steps_completed,
            )

        step_counter.tick("PLAN", "Creating query plan")
        budget = TrademarkSearchBudget(
            max_results_per_query=max_results_per_query,
            max_candidates_to_normalize=max_candidates_to_normalize,
            max_candidates_to_surface_in_report=max_candidates_to_surface_in_report,
            include_inactive_contextual=include_inactive_contextual,
            include_web_search=include_web_search,
        )
        query_plan = plan_trademark_search(criteria, budget=budget)
        write_artifact(
            manifest.session_id,
            "query_plan",
            query_plan,
            base_dir=sessions_base_dir,
        )
        write_artifact(
            manifest.session_id,
            "search_plan",
            query_plan,
            base_dir=sessions_base_dir,
        )

        step_counter.tick("MOCK_SEARCH", "Normalizing mocked source results")
        compumark_results = list(mock_compumark_results or [])
        web_results = list(mock_web_results or [])
        normalized_candidates = flag_duplicate_candidates(
            [
                *[normalize_compumark_result(result) for result in compumark_results],
                *[normalize_web_common_law_result(result) for result in web_results],
            ]
        )
        write_artifact(
            manifest.session_id,
            "compumark_results",
            compumark_results,
            base_dir=sessions_base_dir,
        )
        write_artifact(
            manifest.session_id,
            "web_results",
            web_results,
            base_dir=sessions_base_dir,
        )
        write_artifact(
            manifest.session_id,
            "normalized_candidates",
            normalized_candidates,
            base_dir=sessions_base_dir,
        )
        write_artifact(
            manifest.session_id,
            "candidates",
            normalized_candidates,
            base_dir=sessions_base_dir,
        )

        step_counter.tick("SOURCE_STATUS", "Recording mocked source statuses")
        source_statuses = _source_statuses(
            criteria=criteria,
            include_web_search=include_web_search,
            mock_source_statuses=mock_source_statuses,
        )
        write_artifact(
            manifest.session_id,
            "source_statuses",
            source_statuses,
            base_dir=sessions_base_dir,
        )

        step_counter.tick("ASSESS", "Generating risk assessment")
        risk_assessment = assess_trademark_risk(
            criteria,
            normalized_candidates,
            source_statuses=source_statuses,
        )
        write_artifact(
            manifest.session_id,
            "risk_assessment",
            risk_assessment,
            base_dir=sessions_base_dir,
        )
        write_artifact(
            manifest.session_id,
            "assessments",
            risk_assessment,
            base_dir=sessions_base_dir,
        )
        write_artifact(
            manifest.session_id,
            "ranked_findings",
            risk_assessment.findings,
            base_dir=sessions_base_dir,
        )

        step_counter.tick("STOPPING", "Evaluating completion")
        progress = SearchProgress(
            completed_query_group_ids=[
                group.id for group in query_plan.query_groups if group.required
            ],
            normalized_candidate_count=len(normalized_candidates),
            relevant_candidate_count=len(risk_assessment.findings),
            selected_for_deep_review_count=min(
                len(risk_assessment.findings),
                max_candidates_to_surface_in_report,
            ),
            source_statuses=source_statuses,
        )
        stopping_decision = determine_stopping_decision(query_plan, progress)
        final_decision = {
            "status": MockEvalStatus.COMPLETED.value,
            "risk_label": risk_assessment.overall_risk_label.value,
            "stopping_decision": stopping_decision.decision.value,
            "reason": stopping_decision.reason,
            "live_api_calls": False,
        }
        write_artifact(
            manifest.session_id,
            "final_decision",
            final_decision,
            base_dir=sessions_base_dir,
        )

        step_counter.tick("REVIEW", "Writing adversarial review")
        source_failures = risk_assessment.missing_or_failed_source_notes
        adversarial_review = AdversarialReview(
            summary=(
                "Mocked E2E review confirmed requested scope, source status, "
                "candidate links, risk support, and report limitations."
            ),
            checks={
                "request_accepted": True,
                "search_criteria_created": True,
                "query_plan_created": True,
                "candidates_normalized": True,
                "risk_assessment_generated": True,
            },
            source_failures=source_failures,
        )
        write_artifact(
            manifest.session_id,
            "adversarial_review",
            adversarial_review,
            base_dir=sessions_base_dir,
        )

        step_counter.tick("REPORT", "Generating final report")
        report = generate_trademark_report(
            {
                "request": request_payload,
                "search_criteria": criteria,
                "query_plan": query_plan,
                "compumark_results": compumark_results,
                "web_results": web_results,
                "normalized_candidates": normalized_candidates,
                "ranked_findings": risk_assessment.findings,
                "risk_assessment": risk_assessment,
                "adversarial_review": adversarial_review,
                "source_statuses": source_statuses,
                "recommendation": _recommendation_for_eval(
                    risk_assessment.overall_risk_label.value
                ),
            }
        )
        validation = validate_trademark_report(
            report,
            {
                "search_criteria": criteria,
                "query_plan": query_plan,
                "normalized_candidates": normalized_candidates,
                "ranked_findings": risk_assessment.findings,
                "risk_assessment": risk_assessment,
                "adversarial_review": adversarial_review,
                "source_statuses": source_statuses,
            },
        )
        if not validation.valid:
            errors.extend(issue.message for issue in validation.issues)
        write_final_report(manifest.session_id, report, base_dir=sessions_base_dir)

        return MockEvalRunResult(
            status=MockEvalStatus.COMPLETED if not errors else MockEvalStatus.ERROR,
            final_risk_label=risk_assessment.overall_risk_label.value,
            final_report=read_final_report(
                manifest.session_id,
                base_dir=sessions_base_dir,
            ),
            session_id=manifest.session_id,
            session_path=str(session_path),
            artifacts=_existing_artifacts(manifest.session_id, base_dir=sessions_base_dir),
            errors=errors,
            source_failure_status=[
                status.model_dump(mode="json", exclude_none=True)
                for status in source_statuses
                if not status.succeeded
            ],
            live_api_calls=False,
            steps_completed=step_counter.steps_completed,
        )
    except Exception as exc:
        errors.append(str(exc))
        return MockEvalRunResult(
            status=MockEvalStatus.ERROR,
            session_id=manifest.session_id,
            session_path=str(session_path),
            artifacts=_existing_artifacts(manifest.session_id, base_dir=sessions_base_dir),
            errors=errors,
            live_api_calls=False,
            steps_completed=step_counter.steps_completed,
        )


class _StepCounter:
    def __init__(
        self,
        max_steps: int,
        progress_callback: ProgressCallback | None,
    ) -> None:
        self.max_steps = max_steps
        self.progress_callback = progress_callback
        self.steps_completed = 0

    def tick(self, stage: str, preview: str) -> None:
        if self.steps_completed >= self.max_steps:
            raise RuntimeError(f"Exceeded max steps ({self.max_steps})")
        self.steps_completed += 1
        if self.progress_callback is not None:
            self.progress_callback(self.steps_completed, stage, None, preview)


def _build_criteria(
    *,
    brand_name: str | None,
    countries: str | list[str] | None,
    regional_systems: str | list[str] | None,
    classes: str | list[str] | None,
    goods_services: str | None,
    business_context: str | None,
) -> TrademarkSearchCriteria:
    return TrademarkSearchCriteria(
        brand_name=(brand_name or "").strip() or "UNSPECIFIED",
        jurisdictions=_parse_csv_or_list(countries),
        regional_systems=_parse_csv_or_list(regional_systems),
        nice_classes=_parse_csv_or_list(classes),
        goods_services=goods_services,
        business_context=business_context,
        assumptions=["mocked_e2e=true"],
        requires_clarification=not bool(brand_name and brand_name.strip()),
        clarification_reasons=(
            ["Brand name is required."]
            if not bool(brand_name and brand_name.strip())
            else []
        ),
    )


def _parse_csv_or_list(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


def _source_statuses(
    *,
    criteria: TrademarkSearchCriteria,
    include_web_search: bool,
    mock_source_statuses: list[SourceSearchStatus | Mapping[str, Any]] | None,
) -> list[SourceSearchStatus]:
    if mock_source_statuses is not None:
        return [
            status
            if isinstance(status, SourceSearchStatus)
            else SourceSearchStatus.model_validate(status)
            for status in mock_source_statuses
        ]

    statuses: list[SourceSearchStatus] = []
    for jurisdiction in criteria.jurisdictions:
        statuses.append(
            SourceSearchStatus(
                source="compumark",
                jurisdiction=jurisdiction,
                required=True,
                succeeded=True,
            )
        )
    for regional_system in criteria.regional_systems:
        statuses.append(
            SourceSearchStatus(
                source="compumark",
                regional_system=regional_system,
                required=True,
                succeeded=True,
            )
        )
    if include_web_search:
        statuses.append(
            SourceSearchStatus(
                source="web_common_law",
                required=True,
                succeeded=True,
            )
        )
    return statuses


def _recommendation_for_eval(risk_label: str) -> str:
    if risk_label == "LOW":
        return (
            "No knockout/material blocker identified in the mocked artifacts; "
            "the brand may be shortlisted for deeper review subject to limitations."
        )
    if risk_label == "SEARCH_FAILED":
        return (
            "Do not rely on this mocked screening until required source failures "
            "are resolved."
        )
    if risk_label == "HIGH":
        return (
            "Do not shortlist without focused review of the strongest surfaced "
            "candidate conflicts."
        )
    return "Shortlist only with caution and deeper review of surfaced concerns."


def _existing_artifacts(
    session_id: str,
    *,
    base_dir: str | Path,
) -> dict[str, str]:
    artifact_names = [
        "request",
        "scope",
        "search_criteria",
        "query_plan",
        "search_plan",
        "compumark_results",
        "web_results",
        "normalized_candidates",
        "candidates",
        "source_statuses",
        "risk_assessment",
        "assessments",
        "ranked_findings",
        "adversarial_review",
        "final_decision",
        "final_report",
    ]
    paths: dict[str, str] = {}
    for artifact_name in artifact_names:
        path = artifact_path(session_id, artifact_name, base_dir=base_dir)
        if path.exists():
            paths[artifact_name] = str(path)
    return paths


__all__ = [
    "MockEvalRunResult",
    "MockEvalStatus",
    "ProgressCallback",
    "run_tm_knockout_mock_e2e",
]
