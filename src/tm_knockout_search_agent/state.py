"""Structured state and artifact models for TM knockout search.

This module defines data contracts only. It does not run searches, call
external APIs, or implement the agent loop.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


SourceType = Literal["patent", "npl", "semantic", "other"]
ElementCoverage = Literal["Y", "PARTIAL", "N"]
KnockoutAssessmentLabel = Literal[
    "STRONG_KNOCKOUT",
    "POSSIBLE_KNOCKOUT",
    "WEAK",
    "NOT_KNOCKOUT",
]
FinalDecisionStatus = Literal[
    "KNOCKOUT_FOUND",
    "POSSIBLE_KNOCKOUT_FOUND",
    "NO_KNOCKOUT_FOUND",
    "INSUFFICIENT_SEARCH",
]

class WorkflowStage(str, Enum):
    """Deterministic workflow stages for TM knockout search sessions."""

    INTAKE = "INTAKE"
    AWAITING_SCOPE_CONFIRMATION = "AWAITING_SCOPE_CONFIRMATION"
    ELEMENTS_READY = "ELEMENTS_READY"
    SEARCH_PLAN_READY = "SEARCH_PLAN_READY"
    SEARCHING = "SEARCHING"
    SCREENING = "SCREENING"
    DECISION_READY = "DECISION_READY"
    REPORT_READY = "REPORT_READY"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


SessionStage = WorkflowStage


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _strip_non_empty(value: str, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be empty")
    return stripped


def _normalize_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        stripped = value.strip()
        if not stripped or stripped in seen:
            continue
        normalized.append(stripped)
        seen.add(stripped)
    return normalized


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_nice_classes(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        stripped = str(value).strip()
        if not stripped:
            continue
        if not stripped.isdigit():
            raise ValueError("Nice classes must be numeric values from 1 to 45")
        class_number = int(stripped)
        if class_number < 1 or class_number > 45:
            raise ValueError("Nice classes must be numeric values from 1 to 45")
        normalized_value = str(class_number)
        if normalized_value not in seen:
            normalized.append(normalized_value)
            seen.add(normalized_value)
    return normalized


def validate_claim_element_sequence(elements: list["ClaimElement"]) -> list["ClaimElement"]:
    """Validate claim elements are E1, E2, E3... and include a core element."""
    if not elements:
        raise ValueError("at least one claim element is required")

    expected_ids = [f"E{index}" for index in range(1, len(elements) + 1)]
    actual_ids = [element.id for element in elements]
    if actual_ids != expected_ids:
        raise ValueError(
            "claim element ids must be sequential starting at E1: "
            f"expected {expected_ids}, got {actual_ids}"
        )

    if not any(element.is_core for element in elements):
        raise ValueError("at least one core claim element is required")

    return elements


class ArtifactModel(BaseModel):
    """Base class for JSON-backed session artifacts."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    def to_json_text(self) -> str:
        """Serialize the model to pretty JSON."""
        return self.model_dump_json(indent=2, exclude_none=True)

    def write_json(self, path: str | Path) -> Path:
        """Write the model to a JSON file and return the path."""
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.to_json_text() + "\n", encoding="utf-8")
        return output_path

    @classmethod
    def read_json(cls, path: str | Path) -> Self:
        """Read and validate a model from a JSON file."""
        input_path = Path(path)
        return cls.model_validate_json(input_path.read_text(encoding="utf-8"))


class KnockoutSearchRequest(ArtifactModel):
    """Raw request and optional user-provided search constraints."""

    raw_user_input: str = Field(..., min_length=1)
    jurisdiction_constraints: list[str] = Field(default_factory=list)
    date_constraints: dict[str, str] = Field(default_factory=dict)
    source_constraints: list[SourceType] = Field(default_factory=list)
    claim_text: str | None = None
    invention_description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("raw_user_input")
    @classmethod
    def _raw_input_required(cls, value: str) -> str:
        return _strip_non_empty(value, "raw_user_input")

    @field_validator("jurisdiction_constraints", mode="after")
    @classmethod
    def _normalize_jurisdictions(cls, value: list[str]) -> list[str]:
        return _normalize_strings(value)


class SearchScope(ArtifactModel):
    """Normalized search scope for the knockout analysis."""

    normalized_technical_problem: str = Field(..., min_length=1)
    key_product_system_process: str = Field(..., min_length=1)
    must_have_elements: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @field_validator("normalized_technical_problem", "key_product_system_process")
    @classmethod
    def _scope_text_required(cls, value: str) -> str:
        return _strip_non_empty(value, "scope text")

    @field_validator("must_have_elements", "exclusions", "assumptions", mode="after")
    @classmethod
    def _normalize_lists(cls, value: list[str]) -> list[str]:
        return _normalize_strings(value)


class ClaimElement(ArtifactModel):
    """A searchable claim or invention element."""

    id: str = Field(..., pattern=r"^E[1-9][0-9]*$")
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    is_core: bool = True
    synonyms_search_terms: list[str] = Field(default_factory=list)

    @field_validator("name", "description")
    @classmethod
    def _text_required(cls, value: str) -> str:
        return _strip_non_empty(value, "claim element text")

    @field_validator("synonyms_search_terms", mode="after")
    @classmethod
    def _normalize_terms(cls, value: list[str]) -> list[str]:
        return _normalize_strings(value)


class ClaimBreakdown(ArtifactModel):
    """Validated collection of claim elements."""

    elements: list[ClaimElement] = Field(..., min_length=1)

    @field_validator("elements", mode="after")
    @classmethod
    def _validate_elements(cls, value: list[ClaimElement]) -> list[ClaimElement]:
        return validate_claim_element_sequence(value)


class SearchBudget(ArtifactModel):
    """Search budget limits used by the future workflow."""

    max_query_groups: int = Field(default=5, ge=1)
    max_queries_per_group: int = Field(default=5, ge=1)
    max_results_per_query: int = Field(default=25, ge=1)
    max_candidates_to_assess: int = Field(default=20, ge=1)


class QueryGroup(ArtifactModel):
    """A planned group of related searches."""

    id: str = Field(..., min_length=1)
    source: SourceType
    claim_element_ids: list[str] = Field(default_factory=list)
    queries: list[str] = Field(..., min_length=1)
    rationale: str = ""

    @field_validator("id")
    @classmethod
    def _id_required(cls, value: str) -> str:
        return _strip_non_empty(value, "query group id")

    @field_validator("claim_element_ids", mode="after")
    @classmethod
    def _normalize_element_ids(cls, value: list[str]) -> list[str]:
        return _normalize_strings(value)

    @field_validator("queries", mode="after")
    @classmethod
    def _normalize_queries(cls, value: list[str]) -> list[str]:
        normalized = _normalize_strings(value)
        if not normalized:
            raise ValueError("at least one query is required")
        return normalized


class SearchPlan(ArtifactModel):
    """Planned search sources, query groups, priorities, and budget."""

    target_sources: list[SourceType] = Field(..., min_length=1)
    query_groups: list[QueryGroup] = Field(default_factory=list)
    priority_order: list[str] = Field(default_factory=list)
    search_budget: SearchBudget = Field(default_factory=SearchBudget)

    @field_validator("target_sources", mode="after")
    @classmethod
    def _dedupe_sources(cls, value: list[SourceType]) -> list[SourceType]:
        return list(dict.fromkeys(value))

    @field_validator("priority_order", mode="after")
    @classmethod
    def _normalize_priorities(cls, value: list[str]) -> list[str]:
        return _normalize_strings(value)


class TrademarkSearchSource(str, Enum):
    """Search sources represented in the deterministic trademark plan."""

    COMPUMARK = "compumark"
    WEB_SEARCH = "web_search"
    COMPUMARK_INACTIVE_CONTEXTUAL = "compumark_inactive_contextual"
    LITIGATION = "litigation"


class TrademarkSearchStage(str, Enum):
    """Progressive search stages for TM knockout planning."""

    EXACT_ACTIVE = "EXACT_ACTIVE"
    SIMILAR_ACTIVE = "SIMILAR_ACTIVE"
    WEB_COMMON_LAW = "WEB_COMMON_LAW"
    INACTIVE_CONTEXTUAL = "INACTIVE_CONTEXTUAL"


class TrademarkQueryIntent(str, Enum):
    """Deterministic query intent labels."""

    EXACT = "exact"
    SIMILAR = "similar"
    WEB_COMMON_LAW = "web_common_law"
    INACTIVE_CONTEXTUAL = "inactive_contextual"


class TrademarkSearchBudget(ArtifactModel):
    """Configurable limits for deterministic TM query planning."""

    max_results_per_query: int = Field(default=25, ge=1)
    max_candidates_to_normalize: int = Field(default=100, ge=1)
    max_candidates_to_surface_in_report: int = Field(default=10, ge=1)
    include_inactive_contextual: bool = False
    include_web_search: bool = True


_REGIONAL_SYSTEM_ALIASES: dict[str, str] = {
    "EUIPO": "EUIPO",
    "EUTM": "EUIPO",
    "EU TRADE MARK": "EUIPO",
    "EU TRADEMARK": "EUIPO",
    "WIPO": "WIPO",
    "WO": "WIPO",
    "MADRID": "WIPO",
    "MADRID SYSTEM": "WIPO",
}
_AMBIGUOUS_REGIONS = frozenset({"EUROPE", "EUROPEAN UNION", "EU", "GLOBAL", "WORLDWIDE"})


class TrademarkSearchCriteria(ArtifactModel):
    """Normalized input criteria for trademark knockout query planning."""

    brand_name: str = Field(..., min_length=1)
    jurisdictions: list[str] = Field(default_factory=list)
    regional_systems: list[str] = Field(default_factory=list)
    nice_classes: list[str] = Field(default_factory=list)
    inferred_classes: list[str] = Field(default_factory=list)
    goods_services: str | None = None
    business_context: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    requires_clarification: bool = False
    clarification_reasons: list[str] = Field(default_factory=list)

    @field_validator("brand_name")
    @classmethod
    def _brand_required(cls, value: str) -> str:
        return _strip_non_empty(value, "brand_name")

    @field_validator("goods_services", "business_context", mode="after")
    @classmethod
    def _normalize_optional_text(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("nice_classes", "inferred_classes", mode="after")
    @classmethod
    def _normalize_classes(cls, value: list[str]) -> list[str]:
        return _normalize_nice_classes(value)

    @field_validator("assumptions", "clarification_reasons", mode="after")
    @classmethod
    def _normalize_text_lists(cls, value: list[str]) -> list[str]:
        return _normalize_strings(value)

    @model_validator(mode="after")
    def _normalize_jurisdictions_and_regions(self) -> "TrademarkSearchCriteria":
        jurisdictions: list[str] = []
        regional_systems: list[str] = []
        reasons = list(self.clarification_reasons)

        for value in [*self.jurisdictions, *self.regional_systems]:
            stripped = value.strip()
            if not stripped:
                continue
            key = stripped.upper()
            if key in _AMBIGUOUS_REGIONS:
                jurisdictions.append(stripped)
                reasons.append(
                    f"{stripped} is ambiguous; provide specific countries or a filing system such as EUIPO."
                )
                continue
            regional_system = _REGIONAL_SYSTEM_ALIASES.get(key)
            if regional_system:
                regional_systems.append(regional_system)
            else:
                jurisdictions.append(stripped.upper() if len(stripped) <= 3 else stripped)

        if not jurisdictions and not regional_systems:
            reasons.append("At least one jurisdiction or regional trademark system is needed.")

        if not self.goods_services and not self.nice_classes and not self.inferred_classes:
            reasons.append("Goods/services or Nice classes are needed to scope the knockout search.")

        object.__setattr__(self, "jurisdictions", _normalize_strings(jurisdictions))
        object.__setattr__(self, "regional_systems", _normalize_strings(regional_systems))
        object.__setattr__(
            self,
            "requires_clarification",
            self.requires_clarification or bool(reasons),
        )
        object.__setattr__(self, "clarification_reasons", _normalize_strings(reasons))
        return self

    @property
    def all_classes(self) -> list[str]:
        """Return explicit and inferred Nice classes in stable order."""
        return _normalize_strings([*self.nice_classes, *self.inferred_classes])


class TrademarkQueryGroup(ArtifactModel):
    """One deterministic trademark query group for a planned source/stage."""

    id: str = Field(..., min_length=1)
    stage: TrademarkSearchStage
    source: TrademarkSearchSource
    brand_name: str = Field(..., min_length=1)
    normalized_brand_name: str = Field(..., min_length=1)
    jurisdictions: list[str] = Field(default_factory=list)
    regional_systems: list[str] = Field(default_factory=list)
    classes: list[str] = Field(default_factory=list)
    inferred_classes: list[str] = Field(default_factory=list)
    goods_services: str | None = None
    query_intent: TrademarkQueryIntent
    max_results: int = Field(..., ge=1)
    required: bool = True
    notes: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @field_validator("id", "brand_name", "normalized_brand_name")
    @classmethod
    def _query_group_text_required(cls, value: str) -> str:
        return _strip_non_empty(value, "query group text")

    @field_validator("goods_services", mode="after")
    @classmethod
    def _normalize_goods_services(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("jurisdictions", "regional_systems", "notes", "assumptions", mode="after")
    @classmethod
    def _normalize_group_lists(cls, value: list[str]) -> list[str]:
        return _normalize_strings(value)

    @field_validator("classes", "inferred_classes", mode="after")
    @classmethod
    def _normalize_group_classes(cls, value: list[str]) -> list[str]:
        return _normalize_nice_classes(value)


class TrademarkFallbackStrategy(ArtifactModel):
    """Fallback behavior represented in the deterministic trademark plan."""

    exact_active_required: bool = True
    similar_active_after_exact: bool = True
    web_common_law_standard: bool = True
    inactive_contextual_policy: str = (
        "Run only when configured or when active searches are weak or no-hit."
    )
    future_extensions: list[TrademarkSearchSource] = Field(
        default_factory=lambda: [TrademarkSearchSource.LITIGATION]
    )
    notes: list[str] = Field(default_factory=list)

    @field_validator("notes", mode="after")
    @classmethod
    def _normalize_notes(cls, value: list[str]) -> list[str]:
        return _normalize_strings(value)


class TrademarkSearchPlan(ArtifactModel):
    """Structured deterministic trademark knockout search plan."""

    criteria: TrademarkSearchCriteria
    source_priority_order: list[TrademarkSearchSource]
    progressive_stages: list[TrademarkSearchStage]
    query_groups: list[TrademarkQueryGroup]
    search_budget: TrademarkSearchBudget
    fallback_strategy: TrademarkFallbackStrategy
    requires_clarification: bool = False
    clarification_reasons: list[str] = Field(default_factory=list)

    @field_validator("source_priority_order", "progressive_stages", mode="after")
    @classmethod
    def _dedupe_enum_lists(cls, value: list[Any]) -> list[Any]:
        return list(dict.fromkeys(value))

    @field_validator("clarification_reasons", mode="after")
    @classmethod
    def _normalize_plan_reasons(cls, value: list[str]) -> list[str]:
        return _normalize_strings(value)


class TrademarkCandidateSource(str, Enum):
    """Normalized source types for trademark candidates."""

    COMPUMARK = "compumark"
    WEB_COMMON_LAW = "web_common_law"


class TrademarkCandidate(ArtifactModel):
    """Normalized trademark clearance candidate from registry or web sources."""

    id: str = Field(..., min_length=1)
    source: TrademarkCandidateSource
    mark_name: str | None = None
    normalized_mark_name: str | None = None
    jurisdiction: str | None = None
    regional_system: str | None = None
    classes: list[str] = Field(default_factory=list)
    goods_services: str | None = None
    status: str | None = None
    owner: str | None = None
    application_number: str | None = None
    registration_number: str | None = None
    filing_date: str | None = None
    registration_date: str | None = None
    source_url: str | None = None
    record_id: str | None = None
    title: str | None = None
    snippet: str | None = None
    domain: str | None = None
    detected_brand_text: str | None = None
    jurisdiction_hint: str | None = None
    owner_company_hint: str | None = None
    use_context: str | None = None
    duplicate_key: str | None = None
    duplicate_of: str | None = None
    raw_source_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _candidate_id_required(cls, value: str) -> str:
        return _strip_non_empty(value, "trademark candidate id")

    @field_validator(
        "mark_name",
        "normalized_mark_name",
        "jurisdiction",
        "regional_system",
        "goods_services",
        "status",
        "owner",
        "application_number",
        "registration_number",
        "filing_date",
        "registration_date",
        "source_url",
        "record_id",
        "title",
        "snippet",
        "domain",
        "detected_brand_text",
        "jurisdiction_hint",
        "owner_company_hint",
        "use_context",
        "duplicate_key",
        "duplicate_of",
        mode="after",
    )
    @classmethod
    def _normalize_optional_candidate_text(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("classes", mode="after")
    @classmethod
    def _normalize_candidate_classes(cls, value: list[str]) -> list[str]:
        return _normalize_nice_classes(value)


class CandidateReference(ArtifactModel):
    """A stable candidate reference returned by a future search source."""

    id: str = Field(..., min_length=1)
    source: SourceType
    title: str = Field(..., min_length=1)
    publication_identifier: str | None = None
    application_identifier: str | None = None
    doi: str | None = None
    other_identifiers: dict[str, str] = Field(default_factory=dict)
    date: str | None = None
    assignee_authors: list[str] = Field(default_factory=list)
    abstract_snippet: str | None = None
    url: HttpUrl | None = None

    @field_validator("id", "title")
    @classmethod
    def _required_text(cls, value: str) -> str:
        return _strip_non_empty(value, "candidate reference text")

    @field_validator("assignee_authors", mode="after")
    @classmethod
    def _normalize_names(cls, value: list[str]) -> list[str]:
        return _normalize_strings(value)


class EvidenceSnippet(ArtifactModel):
    """Evidence text linking a candidate reference to a claim element."""

    candidate_reference_id: str = Field(..., min_length=1)
    claim_element_id: str = Field(..., pattern=r"^E[1-9][0-9]*$")
    text: str = Field(..., min_length=1)
    source_field: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("candidate_reference_id", "text")
    @classmethod
    def _required_text(cls, value: str) -> str:
        return _strip_non_empty(value, "evidence text")


class ElementMapping(ArtifactModel):
    """Coverage mapping between a candidate reference and a claim element."""

    candidate_reference_id: str = Field(..., min_length=1)
    claim_element_id: str = Field(..., pattern=r"^E[1-9][0-9]*$")
    coverage: ElementCoverage
    rationale: str = Field(..., min_length=1)

    @field_validator("candidate_reference_id", "rationale")
    @classmethod
    def _required_text(cls, value: str) -> str:
        return _strip_non_empty(value, "element mapping text")


class KnockoutAssessment(ArtifactModel):
    """Preliminary knockout assessment for one candidate reference."""

    candidate_reference_id: str = Field(..., min_length=1)
    covered_core_elements: list[str] = Field(default_factory=list)
    missing_core_elements: list[str] = Field(default_factory=list)
    score: float = Field(..., ge=0.0, le=100.0)
    label: KnockoutAssessmentLabel
    rationale: str = Field(..., min_length=1)

    @field_validator("candidate_reference_id", "rationale")
    @classmethod
    def _required_text(cls, value: str) -> str:
        return _strip_non_empty(value, "knockout assessment text")

    @field_validator("covered_core_elements", "missing_core_elements", mode="after")
    @classmethod
    def _normalize_element_ids(cls, value: list[str]) -> list[str]:
        return _normalize_strings(value)


class FinalDecision(ArtifactModel):
    """Final session-level decision artifact."""

    status: FinalDecisionStatus
    top_candidates: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("top_candidates", "limitations", mode="after")
    @classmethod
    def _normalize_lists(cls, value: list[str]) -> list[str]:
        return _normalize_strings(value)


class SessionManifest(ArtifactModel):
    """Manifest for session metadata and artifact paths."""

    session_id: str = Field(..., min_length=1)
    stage: WorkflowStage = WorkflowStage.INTAKE
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    artifact_updated_at: dict[str, datetime] = Field(default_factory=dict)
    artifact_sizes: dict[str, int] = Field(default_factory=dict)

    @field_validator("session_id")
    @classmethod
    def _session_id_required(cls, value: str) -> str:
        return _strip_non_empty(value, "session_id")

    @model_validator(mode="after")
    def _updated_not_before_created(self) -> "SessionManifest":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not be before created_at")
        return self

    def touch(self) -> "SessionManifest":
        """Return a copy with `updated_at` set to now."""
        return self.model_copy(update={"updated_at": _utc_now()})

    def with_stage(self, stage: WorkflowStage) -> "SessionManifest":
        """Return a copy with the workflow stage and timestamp updated."""
        return self.model_copy(update={"stage": stage, "updated_at": _utc_now()})

    def record_artifact(
        self,
        artifact_name: str,
        artifact_path: str | Path,
        *,
        size_bytes: int | None = None,
    ) -> "SessionManifest":
        """Return a copy with artifact metadata recorded."""
        updated_at = _utc_now()
        artifact_paths = {
            **self.artifact_paths,
            artifact_name: str(artifact_path),
        }
        artifact_updated_at = {
            **self.artifact_updated_at,
            artifact_name: updated_at,
        }
        artifact_sizes = dict(self.artifact_sizes)
        if size_bytes is not None:
            artifact_sizes[artifact_name] = size_bytes

        return self.model_copy(
            update={
                "updated_at": updated_at,
                "artifact_paths": artifact_paths,
                "artifact_updated_at": artifact_updated_at,
                "artifact_sizes": artifact_sizes,
            }
        )


class TMKnockoutState(ArtifactModel):
    """Minimal graph state shell for the future TM knockout agent."""

    messages: list[Any] = Field(default_factory=list)
    current_stage: WorkflowStage = WorkflowStage.INTAKE
    request: KnockoutSearchRequest | None = None
    scope: SearchScope | None = None
    claim_breakdown: ClaimBreakdown | None = None
    search_plan: SearchPlan | None = None
    candidates: list[CandidateReference] = Field(default_factory=list)
    evidence_snippets: list[EvidenceSnippet] = Field(default_factory=list)
    element_mappings: list[ElementMapping] = Field(default_factory=list)
    knockout_assessments: list[KnockoutAssessment] = Field(default_factory=list)
    final_decision: FinalDecision | None = None
    session_manifest: SessionManifest | None = None
    report_markdown: str | None = None


AgentState = TMKnockoutState


__all__ = [
    "AgentState",
    "ArtifactModel",
    "CandidateReference",
    "ClaimBreakdown",
    "ClaimElement",
    "ElementCoverage",
    "ElementMapping",
    "EvidenceSnippet",
    "FinalDecision",
    "FinalDecisionStatus",
    "KnockoutAssessment",
    "KnockoutAssessmentLabel",
    "KnockoutSearchRequest",
    "QueryGroup",
    "SearchBudget",
    "SearchPlan",
    "SearchScope",
    "SessionManifest",
    "SessionStage",
    "SourceType",
    "TMKnockoutState",
    "TrademarkFallbackStrategy",
    "TrademarkCandidate",
    "TrademarkCandidateSource",
    "TrademarkQueryGroup",
    "TrademarkQueryIntent",
    "TrademarkSearchBudget",
    "TrademarkSearchCriteria",
    "TrademarkSearchPlan",
    "TrademarkSearchSource",
    "TrademarkSearchStage",
    "WorkflowStage",
    "validate_claim_element_sequence",
]
