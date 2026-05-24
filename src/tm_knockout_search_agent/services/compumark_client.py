"""CompuMark API client helpers for TM knockout search.

The client is intentionally small and injectable. Unit tests can provide a
transport callable, while live runs use the CompuMark Search API described by
the local Swagger subset.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import requests

from src.tm_knockout_search_agent.state import TrademarkCandidate


DEFAULT_COMPUMARK_BASE_URL = "https://api.clarivate.com/compumark-content/api/v1"
DEFAULT_COMPUMARK_TIMEOUT_SECONDS = 30.0
DEFAULT_COMPUMARK_TEXT_BATCH_SIZE = 100

CompuMarkTransport = Callable[
    [str, Mapping[str, Any], Mapping[str, str], float],
    Mapping[str, Any],
]


class CompuMarkConfigError(RuntimeError):
    """Raised when required CompuMark configuration is missing or invalid."""


class CompuMarkAPIError(RuntimeError):
    """Raised when the CompuMark API call fails or returns invalid JSON."""


@dataclass(frozen=True)
class CompuMarkConfig:
    """Runtime configuration for CompuMark Search API calls."""

    api_key: str
    base_url: str = DEFAULT_COMPUMARK_BASE_URL
    timeout_seconds: float = DEFAULT_COMPUMARK_TIMEOUT_SECONDS
    text_test_mode: bool = False

    @classmethod
    def from_env(cls, *, env_file: str | Path | None = None) -> "CompuMarkConfig":
        """Load CompuMark settings from environment variables and .env."""
        if env_file is None:
            env_file = Path(__file__).resolve().parents[3] / ".env"
        load_dotenv(env_file)

        api_key = (os.environ.get("COMPUMARK_API_KEY") or "").strip()
        if not api_key:
            raise CompuMarkConfigError("Set COMPUMARK_API_KEY to enable CompuMark search.")

        base_url = (
            os.environ.get("COMPUMARK_BASE_URL") or DEFAULT_COMPUMARK_BASE_URL
        ).strip()
        timeout_raw = (
            os.environ.get("COMPUMARK_TIMEOUT_SECONDS")
            or str(DEFAULT_COMPUMARK_TIMEOUT_SECONDS)
        ).strip()
        text_test_mode = _env_truthy(os.environ.get("COMPUMARK_TEXT_TEST_MODE"))

        try:
            timeout_seconds = float(timeout_raw)
        except ValueError as exc:
            raise CompuMarkConfigError(
                "COMPUMARK_TIMEOUT_SECONDS must be a number."
            ) from exc
        if timeout_seconds <= 0:
            raise CompuMarkConfigError("COMPUMARK_TIMEOUT_SECONDS must be positive.")

        return cls(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            timeout_seconds=timeout_seconds,
            text_test_mode=text_test_mode,
        )


@dataclass(frozen=True)
class CompuMarkSearchExecutionResult:
    """Normalized result returned by a CompuMark search execution."""

    requests: list[dict[str, Any]]
    counts: dict[str, int]
    ids_by_office: dict[str, list[str]]
    selected_ids: list[str]
    candidates: list[TrademarkCandidate]
    raw_trademark_count: int
    truncated: bool
    live_api_calls: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize the execution result to primitive JSON-friendly values."""
        return {
            "source": "compumark",
            "succeeded": True,
            "live_api_calls": self.live_api_calls,
            "requests": self.requests,
            "counts": self.counts,
            "ids_by_office": self.ids_by_office,
            "selected_ids": self.selected_ids,
            "candidates": [
                candidate.model_dump(mode="json", exclude_none=True)
                for candidate in self.candidates
            ],
            "raw_trademark_count": self.raw_trademark_count,
            "truncated": self.truncated,
        }


class CompuMarkClient:
    """Small client for the CompuMark Search API subset."""

    def __init__(
        self,
        config: CompuMarkConfig | None = None,
        *,
        transport: CompuMarkTransport | None = None,
    ) -> None:
        self.config = config or CompuMarkConfig.from_env()
        self._transport = transport or self._requests_transport

    @property
    def headers(self) -> dict[str, str]:
        """Return HTTP headers required by the CompuMark API."""
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-ApiKey": self.config.api_key,
        }

    def count(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Call POST /count."""
        return dict(self._post_json("/count", payload))

    def search(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Call POST /search."""
        return dict(self._post_json("/search", payload))

    def retrieve_text(
        self,
        ids: Sequence[str],
        *,
        test: bool | None = None,
    ) -> dict[str, Any]:
        """Call POST /text for a list of trademark GUIDs."""
        payload = {
            "ids": [str(value) for value in ids if str(value).strip()],
            "test": self.config.text_test_mode if test is None else bool(test),
        }
        if not payload["ids"]:
            return {"trademarks": []}
        return dict(self._post_json("/text", payload))

    def execute_search(
        self,
        *,
        brand_name: str,
        jurisdictions: Sequence[str],
        classes: Sequence[str] | None = None,
        query_intent: str = "exact",
        max_results: int = 25,
        text_test_mode: bool | None = None,
    ) -> CompuMarkSearchExecutionResult:
        """Run count/search/text and normalize returned trademark records."""
        requests_payloads = build_compumark_search_requests(
            brand_name=brand_name,
            jurisdictions=jurisdictions,
            classes=classes,
            query_intent=query_intent,
        )
        if max_results < 1:
            raise ValueError("max_results must be at least 1")

        counts: dict[str, int] = {}
        ids_by_office: dict[str, list[str]] = {}

        for payload in requests_payloads:
            count_response = self.count(payload)
            _merge_counts(counts, count_response.get("counts", {}))

            search_response = self.search(payload)
            _merge_ids(ids_by_office, search_response.get("ids", {}))

        all_ids = _dedupe_preserve_order(
            trademark_id
            for office_ids in ids_by_office.values()
            for trademark_id in office_ids
        )
        selected_ids = all_ids[:max_results]
        truncated = len(all_ids) > len(selected_ids)

        raw_trademarks: list[dict[str, Any]] = []
        for batch in _chunks(selected_ids, DEFAULT_COMPUMARK_TEXT_BATCH_SIZE):
            text_response = self.retrieve_text(batch, test=text_test_mode)
            raw_trademarks.extend(
                item
                for item in text_response.get("trademarks", [])
                if isinstance(item, Mapping)
            )

        from src.tm_knockout_search_agent.tools.adapters import (
            flag_duplicate_candidates,
            normalize_compumark_trademark_record,
        )

        candidates = flag_duplicate_candidates(
            [normalize_compumark_trademark_record(raw) for raw in raw_trademarks]
        )

        return CompuMarkSearchExecutionResult(
            requests=requests_payloads,
            counts=counts,
            ids_by_office=ids_by_office,
            selected_ids=selected_ids,
            candidates=candidates,
            raw_trademark_count=len(raw_trademarks),
            truncated=truncated,
        )

    def _post_json(
        self,
        path: str,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        return self._transport(
            url,
            payload,
            self.headers,
            self.config.timeout_seconds,
        )

    @staticmethod
    def _requests_transport(
        url: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        response = requests.post(
            url,
            json=dict(payload),
            headers=dict(headers),
            timeout=timeout_seconds,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            body = response.text[:1000]
            raise CompuMarkAPIError(
                f"CompuMark API request failed with HTTP {response.status_code}: {body}"
            ) from exc
        try:
            value = response.json()
        except ValueError as exc:
            raise CompuMarkAPIError("CompuMark API returned invalid JSON.") from exc
        if not isinstance(value, Mapping):
            raise CompuMarkAPIError("CompuMark API returned a non-object JSON response.")
        return value


def build_compumark_search_requests(
    *,
    brand_name: str,
    jurisdictions: Sequence[str],
    classes: Sequence[str] | None = None,
    query_intent: str = "exact",
) -> list[dict[str, Any]]:
    """Build Swagger-compatible CompuMark /count and /search payloads."""
    brand = brand_name.strip()
    if not brand:
        raise ValueError("brand_name is required")

    office_codes = normalize_registration_office_codes(jurisdictions)
    if not office_codes:
        raise ValueError("At least one jurisdiction or regional system is required")

    normalized_classes = _normalize_nice_classes(classes or [])
    class_values = normalized_classes or [None]
    active_only = query_intent != "inactive_contextual"
    similar_search = query_intent in {"similar", "inactive_contextual"}

    requests_payloads: list[dict[str, Any]] = []
    for class_value in class_values:
        search_fields = [
            {
                "name": (
                    "WORD_MARK_SPECIFICATION"
                    if similar_search
                    else "EXACT_WORD_MARK_SPECIFICATION"
                ),
                "operator": "CONTAINS" if similar_search else "EQUALS",
                "value": brand,
            }
        ]
        if class_value:
            search_fields.append(
                {
                    "name": "INT_CLASS_NUMBER",
                    "operator": "EQUALS",
                    "value": class_value,
                }
            )

        requests_payloads.append(
            {
                "registrationOfficeCodes": office_codes,
                "limitWOresultsToDesignated": "WO" in office_codes and len(office_codes) > 1,
                "searchFields": search_fields,
                "queryOptions": {
                    "activeOnly": active_only,
                    "plurals": similar_search,
                    "crossReferences": similar_search and any(
                        code in {"US", "XS", "CA"} for code in office_codes
                    ),
                    "japanesePhonetics": similar_search and "JP" in office_codes,
                    "centralEuropeanPhonetics": similar_search
                    and any(code in {"HU", "CZ", "PL"} for code in office_codes),
                },
            }
        )
    return requests_payloads


def execute_compumark_search(
    *,
    brand_name: str,
    jurisdictions: Sequence[str],
    classes: Sequence[str] | None = None,
    query_intent: str = "exact",
    max_results: int = 25,
    client: CompuMarkClient | None = None,
    text_test_mode: bool | None = None,
) -> CompuMarkSearchExecutionResult:
    """Convenience wrapper used by the LangChain tool."""
    active_client = client or CompuMarkClient()
    return active_client.execute_search(
        brand_name=brand_name,
        jurisdictions=jurisdictions,
        classes=classes,
        query_intent=query_intent,
        max_results=max_results,
        text_test_mode=text_test_mode,
    )


def normalize_registration_office_codes(values: Sequence[str]) -> list[str]:
    """Normalize user-facing jurisdiction names to CompuMark office codes."""
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = str(raw_value).strip()
        if not value:
            continue
        key = value.upper()
        office = _OFFICE_CODE_ALIASES.get(key, key if len(key) <= 3 else value)
        if office not in seen:
            normalized.append(office)
            seen.add(office)
    return normalized


def _env_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _normalize_nice_classes(values: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        stripped = str(value).strip()
        if not stripped:
            continue
        if not stripped.isdigit():
            raise ValueError("Nice classes must be numeric values from 1 to 45")
        number = int(stripped)
        if number < 1 or number > 45:
            raise ValueError("Nice classes must be numeric values from 1 to 45")
        normalized_value = str(number)
        if normalized_value not in seen:
            normalized.append(normalized_value)
            seen.add(normalized_value)
    return normalized


def _merge_counts(target: dict[str, int], counts: Any) -> None:
    if not isinstance(counts, Mapping):
        return
    for office, value in counts.items():
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        target[str(office)] = target.get(str(office), 0) + count


def _merge_ids(target: dict[str, list[str]], ids: Any) -> None:
    if not isinstance(ids, Mapping):
        return
    for office, values in ids.items():
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
            continue
        bucket = target.setdefault(str(office), [])
        for value in values:
            trademark_id = str(value).strip()
            if trademark_id and trademark_id not in bucket:
                bucket.append(trademark_id)


def _dedupe_preserve_order(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            output.append(text)
            seen.add(text)
    return output


def _chunks(values: Sequence[str], size: int) -> list[list[str]]:
    return [list(values[index : index + size]) for index in range(0, len(values), size)]


_OFFICE_CODE_ALIASES: dict[str, str] = {
    "EUIPO": "EM",
    "EUROPEAN UNION": "EM",
    "EUTM": "EM",
    "EU TRADE MARK": "EM",
    "EU TRADEMARK": "EM",
    "EM": "EM",
    "WIPO": "WO",
    "MADRID": "WO",
    "MADRID SYSTEM": "WO",
    "WO": "WO",
    "UNITED STATES": "US",
    "USA": "US",
    "U.S.": "US",
    "US": "US",
    "UNITED KINGDOM": "GB",
    "UK": "GB",
}


__all__ = [
    "CompuMarkAPIError",
    "CompuMarkClient",
    "CompuMarkConfig",
    "CompuMarkConfigError",
    "CompuMarkSearchExecutionResult",
    "DEFAULT_COMPUMARK_BASE_URL",
    "build_compumark_search_requests",
    "execute_compumark_search",
    "normalize_registration_office_codes",
]
