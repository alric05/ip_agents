"""Deterministic trademark screening and risk assessment.

This module is deliberately small and rule-based. It does not call an LLM,
CompuMark, web search, or any other external API.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from enum import Enum
import re
from typing import Literal

from pydantic import Field, field_validator

from src.tm_knockout_search_agent.state import (
    ArtifactModel,
    TrademarkCandidate,
    TrademarkCandidateSource,
    TrademarkSearchCriteria,
)
from src.tm_knockout_search_agent.tools.adapters import normalize_mark_name


class OverallRiskLabel(str, Enum):
    """Allowed overall risk labels for TM knockout screening."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    SEARCH_FAILED = "SEARCH_FAILED"


class CandidateRiskLabel(str, Enum):
    """Candidate-level deterministic risk labels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


GoodsOverlap = Literal["same", "related", "unrelated", "unknown"]
MarkSimilarityBand = Literal["identical", "high", "similar", "weak", "none"]
WebUseStrength = Literal["none", "weak", "moderate", "strong"]
SourceReliability = Literal["low", "medium", "high"]


class CandidateAnalysis(ArtifactModel):
    """Optional deterministic overrides supplied by upstream screening."""

    candidate_id: str
    mark_similarity_score: float | None = Field(default=None, ge=0, le=100)
    goods_overlap: GoodsOverlap | None = None
    jurisdiction_overlap: bool | None = None
    active: bool | None = None
    famous_or_large_owner: bool = False
    web_use_strength: WebUseStrength | None = None
    source_reliability: SourceReliability | None = None
    notes: list[str] = Field(default_factory=list)

    @field_validator("notes", mode="after")
    @classmethod
    def _normalize_notes(cls, value: list[str]) -> list[str]:
        return [note.strip() for note in value if note.strip()]


class SourceSearchStatus(ArtifactModel):
    """Status for a source/search slice used by deterministic screening."""

    source: str
    jurisdiction: str | None = None
    regional_system: str | None = None
    required: bool = True
    succeeded: bool = True
    error_message: str | None = None


class CandidateFinding(ArtifactModel):
    """Ranked candidate-level finding from deterministic screening."""

    candidate_id: str
    candidate_source: str
    display_name: str
    jurisdiction: str | None = None
    regional_system: str | None = None
    jurisdiction_hint: str | None = None
    risk_label: CandidateRiskLabel
    score: int = Field(..., ge=0, le=100)
    mark_similarity_score: int = Field(..., ge=0, le=100)
    mark_similarity_band: MarkSimilarityBand
    goods_overlap: GoodsOverlap
    jurisdiction_overlap: bool
    active_status: bool
    famous_or_large_owner: bool
    web_use_strength: WebUseStrength
    source_reliability: SourceReliability
    reasons: list[str] = Field(default_factory=list)


class TrademarkRiskAssessment(ArtifactModel):
    """Overall deterministic trademark screening output."""

    overall_risk_label: OverallRiskLabel
    findings: list[CandidateFinding] = Field(default_factory=list)
    explanation: str
    country_notes: dict[str, str] = Field(default_factory=dict)
    missing_or_failed_source_notes: list[str] = Field(default_factory=list)


_ACTIVE_STATUS_TERMS = (
    "active",
    "registered",
    "pending",
    "published",
    "filed",
    "allowed",
    "live",
)
_INACTIVE_STATUS_TERMS = (
    "dead",
    "inactive",
    "expired",
    "abandoned",
    "cancelled",
    "canceled",
    "withdrawn",
)
_FAMOUS_METADATA_KEYS = (
    "famous_owner",
    "is_famous_owner",
    "large_owner",
    "global_brand",
    "owner_fame",
    "fame",
    "market_presence",
)
_WEB_STRONG_TERMS = (
    "official",
    "store",
    "shop",
    "sells",
    "sale",
    "services",
    "available",
    "commerce",
    "commercial",
    "company",
    "brand",
)
_TOKEN_STOPWORDS = {
    "and",
    "or",
    "the",
    "a",
    "an",
    "of",
    "for",
    "to",
    "in",
    "with",
    "featuring",
    "goods",
    "services",
    "service",
    "products",
    "product",
}


def assess_trademark_risk(
    criteria: TrademarkSearchCriteria,
    candidates: list[TrademarkCandidate],
    *,
    candidate_analyses: list[CandidateAnalysis] | None = None,
    source_statuses: list[SourceSearchStatus] | None = None,
) -> TrademarkRiskAssessment:
    """Assess deterministic trademark screening risk for normalized candidates."""
    failed_notes = _failed_source_notes(criteria, source_statuses or [])
    analyses_by_candidate_id = {
        analysis.candidate_id: analysis for analysis in candidate_analyses or []
    }
    findings = sorted(
        [
            _assess_candidate(
                criteria,
                candidate,
                analyses_by_candidate_id.get(candidate.id),
            )
            for candidate in candidates
        ],
        key=lambda finding: (-finding.score, finding.candidate_id),
    )
    country_notes = _build_country_notes(criteria, findings, failed_notes)

    if failed_notes:
        overall = OverallRiskLabel.SEARCH_FAILED
    elif any(finding.risk_label == CandidateRiskLabel.HIGH for finding in findings):
        overall = OverallRiskLabel.HIGH
    elif any(finding.risk_label == CandidateRiskLabel.MEDIUM for finding in findings):
        overall = OverallRiskLabel.MEDIUM
    else:
        overall = OverallRiskLabel.LOW

    explanation = _build_explanation(overall, findings, failed_notes)
    return TrademarkRiskAssessment(
        overall_risk_label=overall,
        findings=findings,
        explanation=explanation,
        country_notes=country_notes,
        missing_or_failed_source_notes=failed_notes,
    )


def _assess_candidate(
    criteria: TrademarkSearchCriteria,
    candidate: TrademarkCandidate,
    analysis: CandidateAnalysis | None,
) -> CandidateFinding:
    mark_score = _mark_similarity_score(criteria.brand_name, candidate, analysis)
    mark_band = _mark_similarity_band(mark_score)
    goods_overlap = analysis.goods_overlap if analysis and analysis.goods_overlap else _goods_overlap(criteria, candidate)
    jurisdiction_overlap = (
        analysis.jurisdiction_overlap
        if analysis and analysis.jurisdiction_overlap is not None
        else _jurisdiction_overlap(criteria, candidate)
    )
    active = (
        analysis.active
        if analysis and analysis.active is not None
        else _is_active_candidate(candidate)
    )
    inactive = _is_inactive_candidate(candidate)
    famous = (analysis.famous_or_large_owner if analysis else False) or _has_famous_owner_signal(candidate)
    web_strength = (
        analysis.web_use_strength
        if analysis and analysis.web_use_strength
        else _web_use_strength(candidate)
    )
    reliability = (
        analysis.source_reliability
        if analysis and analysis.source_reliability
        else _source_reliability(candidate)
    )

    score = _candidate_score(
        mark_score=mark_score,
        goods_overlap=goods_overlap,
        jurisdiction_overlap=jurisdiction_overlap,
        active=active,
        famous=famous,
        web_strength=web_strength,
        reliability=reliability,
    )
    risk_label = _candidate_risk_label(
        score=score,
        mark_score=mark_score,
        goods_overlap=goods_overlap,
        jurisdiction_overlap=jurisdiction_overlap,
        active=active,
        inactive=inactive,
        famous=famous,
        web_strength=web_strength,
        source=candidate.source,
    )
    reasons = _candidate_reasons(
        mark_band=mark_band,
        goods_overlap=goods_overlap,
        jurisdiction_overlap=jurisdiction_overlap,
        active=active,
        inactive=inactive,
        famous=famous,
        web_strength=web_strength,
        reliability=reliability,
        analysis=analysis,
    )

    return CandidateFinding(
        candidate_id=candidate.id,
        candidate_source=candidate.source.value,
        display_name=_candidate_display_name(candidate),
        jurisdiction=candidate.jurisdiction,
        regional_system=candidate.regional_system,
        jurisdiction_hint=candidate.jurisdiction_hint,
        risk_label=risk_label,
        score=score,
        mark_similarity_score=mark_score,
        mark_similarity_band=mark_band,
        goods_overlap=goods_overlap,
        jurisdiction_overlap=jurisdiction_overlap,
        active_status=active,
        famous_or_large_owner=famous,
        web_use_strength=web_strength,
        source_reliability=reliability,
        reasons=reasons,
    )


def _mark_similarity_score(
    brand_name: str,
    candidate: TrademarkCandidate,
    analysis: CandidateAnalysis | None,
) -> int:
    if analysis and analysis.mark_similarity_score is not None:
        return int(round(analysis.mark_similarity_score))

    target = normalize_mark_name(brand_name) or ""
    candidate_text = (
        candidate.normalized_mark_name
        or normalize_mark_name(candidate.mark_name)
        or normalize_mark_name(candidate.detected_brand_text)
        or normalize_mark_name(candidate.title)
        or ""
    )
    if not target or not candidate_text:
        return 0
    if target == candidate_text:
        return 100
    if target in candidate_text or candidate_text in target:
        shorter = min(len(target), len(candidate_text))
        longer = max(len(target), len(candidate_text))
        if longer and shorter / longer >= 0.5:
            return 85

    sequence_score = SequenceMatcher(None, target, candidate_text).ratio() * 100
    target_tokens = set(target.split())
    candidate_tokens = set(candidate_text.split())
    token_score = 0.0
    if target_tokens and candidate_tokens:
        token_score = len(target_tokens & candidate_tokens) / max(len(target_tokens), 1) * 80
    return int(round(max(sequence_score, token_score)))


def _mark_similarity_band(mark_score: int) -> MarkSimilarityBand:
    if mark_score >= 95:
        return "identical"
    if mark_score >= 80:
        return "high"
    if mark_score >= 60:
        return "similar"
    if mark_score > 0:
        return "weak"
    return "none"


def _goods_overlap(
    criteria: TrademarkSearchCriteria,
    candidate: TrademarkCandidate,
) -> GoodsOverlap:
    requested_classes = set(criteria.all_classes)
    candidate_classes = set(candidate.classes)
    if requested_classes and candidate_classes:
        return "same" if requested_classes & candidate_classes else "unrelated"

    if not criteria.goods_services or not candidate.goods_services:
        return "unknown"

    requested_tokens = _meaningful_tokens(criteria.goods_services)
    candidate_tokens = _meaningful_tokens(candidate.goods_services)
    if not requested_tokens or not candidate_tokens:
        return "unknown"
    overlap = requested_tokens & candidate_tokens
    if len(overlap) >= 2:
        return "same"
    if overlap:
        return "related"
    return "unrelated"


def _meaningful_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 2 and token not in _TOKEN_STOPWORDS
    }


def _jurisdiction_overlap(
    criteria: TrademarkSearchCriteria,
    candidate: TrademarkCandidate,
) -> bool:
    requested_jurisdictions = {value.upper() for value in criteria.jurisdictions}
    requested_regions = {value.upper() for value in criteria.regional_systems}
    candidate_values = {
        value.upper()
        for value in [
            candidate.jurisdiction,
            candidate.regional_system,
            candidate.jurisdiction_hint,
        ]
        if value
    }
    return bool(
        (requested_jurisdictions | requested_regions)
        and candidate_values
        and candidate_values & (requested_jurisdictions | requested_regions)
    )


def _is_active_candidate(candidate: TrademarkCandidate) -> bool:
    if candidate.source == TrademarkCandidateSource.WEB_COMMON_LAW:
        return False
    status = (candidate.status or "").lower()
    return any(term in status for term in _ACTIVE_STATUS_TERMS) and not any(
        term in status for term in _INACTIVE_STATUS_TERMS
    )


def _is_inactive_candidate(candidate: TrademarkCandidate) -> bool:
    status = (candidate.status or "").lower()
    return any(term in status for term in _INACTIVE_STATUS_TERMS)


def _has_famous_owner_signal(candidate: TrademarkCandidate) -> bool:
    for key in _FAMOUS_METADATA_KEYS:
        value = candidate.raw_source_metadata.get(key)
        if isinstance(value, bool) and value:
            return True
        if isinstance(value, str) and value.strip().lower() in {
            "famous",
            "large",
            "strong",
            "global",
            "high",
            "yes",
            "true",
        }:
            return True
    return False


def _web_use_strength(candidate: TrademarkCandidate) -> WebUseStrength:
    if candidate.source != TrademarkCandidateSource.WEB_COMMON_LAW:
        return "none"
    raw_strength = candidate.raw_source_metadata.get("commercial_use_strength")
    if isinstance(raw_strength, str) and raw_strength.strip().lower() in {
        "none",
        "weak",
        "moderate",
        "strong",
    }:
        return raw_strength.strip().lower()  # type: ignore[return-value]

    text = " ".join(
        part
        for part in [candidate.title, candidate.snippet, candidate.use_context, candidate.domain]
        if part
    ).lower()
    if any(term in text for term in _WEB_STRONG_TERMS):
        return "strong"
    if text.strip():
        return "moderate"
    return "weak"


def _source_reliability(candidate: TrademarkCandidate) -> SourceReliability:
    if candidate.source == TrademarkCandidateSource.COMPUMARK:
        return "high"
    return "medium"


def _candidate_score(
    *,
    mark_score: int,
    goods_overlap: GoodsOverlap,
    jurisdiction_overlap: bool,
    active: bool,
    famous: bool,
    web_strength: WebUseStrength,
    reliability: SourceReliability,
) -> int:
    score = 0
    if mark_score >= 95:
        score += 40
    elif mark_score >= 80:
        score += 32
    elif mark_score >= 60:
        score += 24
    elif mark_score > 0:
        score += 10

    if active:
        score += 20
    if goods_overlap == "same":
        score += 20
    elif goods_overlap == "related":
        score += 12
    elif goods_overlap == "unknown":
        score += 5
    if jurisdiction_overlap:
        score += 15
    if famous:
        score += 10
    if web_strength == "strong":
        score += 15
    elif web_strength == "moderate":
        score += 8
    if reliability == "high":
        score += 5
    elif reliability == "medium":
        score += 3

    return min(score, 100)


def _candidate_risk_label(
    *,
    score: int,
    mark_score: int,
    goods_overlap: GoodsOverlap,
    jurisdiction_overlap: bool,
    active: bool,
    inactive: bool,
    famous: bool,
    web_strength: WebUseStrength,
    source: TrademarkCandidateSource,
) -> CandidateRiskLabel:
    if (
        score >= 70
        and active
        and mark_score >= 75
        and goods_overlap in {"same", "related"}
        and jurisdiction_overlap
    ):
        return CandidateRiskLabel.HIGH
    if (
        source == TrademarkCandidateSource.WEB_COMMON_LAW
        and web_strength == "strong"
        and mark_score >= 75
        and jurisdiction_overlap
    ):
        return CandidateRiskLabel.MEDIUM
    if inactive and mark_score >= 60 and (
        goods_overlap in {"same", "related"} or jurisdiction_overlap
    ):
        return CandidateRiskLabel.MEDIUM
    if famous and mark_score >= 55:
        return CandidateRiskLabel.MEDIUM
    if score >= 45:
        return CandidateRiskLabel.MEDIUM
    return CandidateRiskLabel.LOW


def _candidate_reasons(
    *,
    mark_band: MarkSimilarityBand,
    goods_overlap: GoodsOverlap,
    jurisdiction_overlap: bool,
    active: bool,
    inactive: bool,
    famous: bool,
    web_strength: WebUseStrength,
    reliability: SourceReliability,
    analysis: CandidateAnalysis | None,
) -> list[str]:
    reasons = [
        f"mark_similarity={mark_band}",
        f"goods_overlap={goods_overlap}",
        f"jurisdiction_overlap={str(jurisdiction_overlap).lower()}",
        f"source_reliability={reliability}",
    ]
    if active:
        reasons.append("active_registry_status=true")
    if inactive:
        reasons.append("inactive_or_dead_record=true")
    if famous:
        reasons.append("famous_or_large_owner_signal=true")
    if web_strength != "none":
        reasons.append(f"web_use_strength={web_strength}")
    if analysis and analysis.notes:
        reasons.extend([f"analysis_note={note}" for note in analysis.notes])
    return reasons


def _candidate_display_name(candidate: TrademarkCandidate) -> str:
    return (
        candidate.mark_name
        or candidate.detected_brand_text
        or candidate.title
        or candidate.registration_number
        or candidate.application_number
        or candidate.id
    )


def _failed_source_notes(
    criteria: TrademarkSearchCriteria,
    source_statuses: list[SourceSearchStatus],
) -> list[str]:
    requested = {
        *[value.upper() for value in criteria.jurisdictions],
        *[value.upper() for value in criteria.regional_systems],
    }
    failed_notes: list[str] = []
    for status in source_statuses:
        source = status.source.lower()
        location = status.jurisdiction or status.regional_system
        location_key = location.upper() if location else ""
        if (
            status.required
            and not status.succeeded
            and source == "compumark"
            and (not requested or not location_key or location_key in requested)
        ):
            detail = f"CompuMark search failed for {location or 'requested scope'}"
            if status.error_message:
                detail = f"{detail}: {status.error_message}"
            failed_notes.append(detail)
    return failed_notes


def _build_country_notes(
    criteria: TrademarkSearchCriteria,
    findings: list[CandidateFinding],
    failed_notes: list[str],
) -> dict[str, str]:
    requested_locations = [*criteria.jurisdictions, *criteria.regional_systems]
    notes: dict[str, str] = {}
    for location in requested_locations:
        location_key = location.upper()
        location_findings = [
            finding for finding in findings if _finding_mentions_location(finding, location_key)
        ]
        if any(location_key in note.upper() for note in failed_notes):
            notes[location] = "SEARCH_FAILED: required CompuMark search failed."
        elif location_findings:
            top = location_findings[0]
            notes[location] = (
                f"{top.risk_label.value}: top candidate {top.display_name} "
                f"scored {top.score}."
            )
        else:
            notes[location] = "LOW: no candidate conflicts found for this location."
    return notes


def _finding_mentions_location(finding: CandidateFinding, location_key: str) -> bool:
    values = [
        finding.jurisdiction,
        finding.regional_system,
        finding.jurisdiction_hint,
    ]
    return any(value and value.upper() == location_key for value in values)


def _build_explanation(
    overall: OverallRiskLabel,
    findings: list[CandidateFinding],
    failed_notes: list[str],
) -> str:
    if overall == OverallRiskLabel.SEARCH_FAILED:
        return f"risk=SEARCH_FAILED; failed_sources={len(failed_notes)}"
    if not findings:
        return "risk=LOW; candidates=0; required_sources_succeeded=true"
    top = findings[0]
    return (
        f"risk={overall.value}; candidates={len(findings)}; "
        f"top_candidate_id={top.candidate_id}; top_score={top.score}; "
        f"top_label={top.risk_label.value}"
    )


__all__ = [
    "CandidateAnalysis",
    "CandidateFinding",
    "CandidateRiskLabel",
    "OverallRiskLabel",
    "SourceSearchStatus",
    "TrademarkRiskAssessment",
    "assess_trademark_risk",
]
