"""Adapters for normalizing trademark search results.

These adapters are intentionally source-shape tolerant and evaluation-free:
they preserve raw metadata, normalize stable candidate fields, and mark likely
duplicates without deciding legal risk.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Any

from src.tm_knockout_search_agent.state import (
    TrademarkCandidate,
    TrademarkCandidateSource,
)


def normalize_candidate_text(value: Any) -> str | None:
    """Return a trimmed string or None for missing/empty values."""
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    stripped = str(value).strip()
    return stripped or None


def normalize_mark_name(value: Any) -> str | None:
    """Normalize a mark name for matching and duplicate detection."""
    text = normalize_candidate_text(value)
    if text is None:
        return None
    text = re.sub(r"[\u2122\u00ae\u2120]", "", text)
    text = re.sub(r"[^A-Za-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().upper() or None


def normalize_classes(value: Any) -> list[str]:
    """Normalize class values from list/string forms."""
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = re.split(r"[,;/|]+", value)
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        raw_values = [str(item) for item in value]
    else:
        raw_values = [str(value)]

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_values:
        stripped = item.strip()
        if not stripped:
            continue
        match = re.search(r"\d{1,3}", stripped)
        if not match:
            continue
        class_number = int(match.group(0))
        if class_number < 1 or class_number > 45:
            continue
        normalized_value = str(class_number)
        if normalized_value not in seen:
            normalized.append(normalized_value)
            seen.add(normalized_value)
    return normalized


def _first_present(raw: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        value = raw.get(key)
        if normalize_candidate_text(value) is not None:
            return value
    return None


def _stable_hash(parts: Sequence[Any]) -> str:
    joined = "|".join(normalize_candidate_text(part) or "" for part in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]


def build_duplicate_key(candidate: TrademarkCandidate) -> str:
    """Build a duplicate key without legal evaluation."""
    if candidate.registration_number:
        return f"registration:{candidate.registration_number.upper()}"
    if candidate.application_number:
        return f"application:{candidate.application_number.upper()}"

    parts = [
        candidate.normalized_mark_name,
        candidate.jurisdiction or candidate.regional_system or candidate.jurisdiction_hint,
        candidate.owner or candidate.owner_company_hint,
    ]
    return "identity:" + _stable_hash(parts)


def _candidate_id_from_duplicate_key(prefix: str, duplicate_key: str) -> str:
    return f"{prefix}-{_stable_hash([duplicate_key])}"


def normalize_compumark_result(raw: Mapping[str, Any]) -> TrademarkCandidate:
    """Normalize a mocked/future CompuMark trademark result."""
    mark_name = normalize_candidate_text(
        _first_present(raw, ["mark_name", "markName", "mark", "trademarkName", "name"])
    )
    jurisdiction = normalize_candidate_text(
        _first_present(raw, ["jurisdiction", "country", "office", "countryCode"])
    )
    owner = normalize_candidate_text(
        _first_present(raw, ["owner", "applicant", "holder", "ownerName"])
    )
    application_number = normalize_candidate_text(
        _first_present(raw, ["application_number", "applicationNumber", "serialNumber"])
    )
    registration_number = normalize_candidate_text(
        _first_present(raw, ["registration_number", "registrationNumber", "regNumber"])
    )
    record_id = normalize_candidate_text(_first_present(raw, ["record_id", "recordId", "id"]))

    duplicate_basis = registration_number or application_number or _stable_hash(
        [mark_name, jurisdiction, owner]
    )
    candidate_id = normalize_candidate_text(record_id) or f"compumark-{duplicate_basis}"
    candidate = TrademarkCandidate(
        id=candidate_id,
        source=TrademarkCandidateSource.COMPUMARK,
        mark_name=mark_name,
        normalized_mark_name=normalize_mark_name(mark_name),
        jurisdiction=jurisdiction,
        classes=normalize_classes(_first_present(raw, ["classes", "nice_classes", "niceClasses"])),
        goods_services=normalize_candidate_text(
            _first_present(raw, ["goods_services", "goodsServices", "goodsAndServices"])
        ),
        status=normalize_candidate_text(_first_present(raw, ["status", "markStatus"])),
        owner=owner,
        application_number=application_number,
        registration_number=registration_number,
        filing_date=normalize_candidate_text(_first_present(raw, ["filing_date", "filingDate"])),
        registration_date=normalize_candidate_text(
            _first_present(raw, ["registration_date", "registrationDate"])
        ),
        source_url=normalize_candidate_text(_first_present(raw, ["source_url", "url", "recordUrl"])),
        record_id=record_id,
        raw_source_metadata=dict(raw),
    )
    return candidate.model_copy(
        update={"duplicate_key": build_duplicate_key(candidate)}
    )


def normalize_web_common_law_result(raw: Mapping[str, Any]) -> TrademarkCandidate:
    """Normalize a mocked/future web/common-law result."""
    title = normalize_candidate_text(_first_present(raw, ["title", "name"]))
    url = normalize_candidate_text(_first_present(raw, ["url", "link", "source_url"]))
    detected_brand = normalize_candidate_text(
        _first_present(raw, ["detected_brand_text", "detectedBrandText", "brand", "mark"])
    )
    jurisdiction_hint = normalize_candidate_text(
        _first_present(raw, ["jurisdiction_hint", "jurisdictionHint", "jurisdiction", "country"])
    )
    owner_hint = normalize_candidate_text(
        _first_present(raw, ["owner_company_hint", "ownerCompanyHint", "owner", "company"])
    )
    duplicate_basis = _stable_hash([detected_brand or title, url, owner_hint])
    candidate = TrademarkCandidate(
        id=f"web-{duplicate_basis}",
        source=TrademarkCandidateSource.WEB_COMMON_LAW,
        mark_name=detected_brand,
        normalized_mark_name=normalize_mark_name(detected_brand),
        title=title,
        source_url=url,
        snippet=normalize_candidate_text(_first_present(raw, ["snippet", "description", "summary"])),
        domain=normalize_candidate_text(_first_present(raw, ["domain", "host"])),
        detected_brand_text=detected_brand,
        jurisdiction_hint=jurisdiction_hint,
        owner_company_hint=owner_hint,
        use_context=normalize_candidate_text(_first_present(raw, ["use_context", "useContext", "context"])),
        raw_source_metadata=dict(raw),
    )
    return candidate.model_copy(
        update={"duplicate_key": build_duplicate_key(candidate)}
    )


def flag_duplicate_candidates(
    candidates: Sequence[TrademarkCandidate],
) -> list[TrademarkCandidate]:
    """Return candidates with duplicate_of set for repeated duplicate keys."""
    first_by_key: dict[str, TrademarkCandidate] = {}
    normalized: list[TrademarkCandidate] = []

    for candidate in candidates:
        duplicate_key = candidate.duplicate_key or build_duplicate_key(candidate)
        candidate_with_key = candidate.model_copy(update={"duplicate_key": duplicate_key})
        first = first_by_key.get(duplicate_key)
        if first is None:
            first_by_key[duplicate_key] = candidate_with_key
            normalized.append(candidate_with_key)
        else:
            normalized.append(
                candidate_with_key.model_copy(update={"duplicate_of": first.id})
            )

    return normalized


__all__ = [
    "build_duplicate_key",
    "flag_duplicate_candidates",
    "normalize_candidate_text",
    "normalize_classes",
    "normalize_compumark_result",
    "normalize_mark_name",
    "normalize_web_common_law_result",
]
