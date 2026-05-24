"""Clarivate Derwent Patent Search API tool with JWT authentication.

This tool searches for patents using Clarivate's Derwent database.
"""

import html
import logging
import re
from typing import Annotated
import json

import httpx
from langchain_core.tools import tool
from langgraph.utils.config import get_config

from src.config.settings import get_settings

_logger = logging.getLogger(__name__)

# Query translator will be initialized lazily to avoid circular imports
_query_translator = None


def _get_query_translator():
    """Get or initialize the query translator (lazy loading)."""
    global _query_translator
    if _query_translator is None:
        from src.novelty_checker.utils import QueryTranslator
        _query_translator = QueryTranslator()
        _logger.debug("QueryTranslator initialized with %d field mappings", len(_query_translator.field_mappings))
    return _query_translator


# =============================================================================
# Response cleanup helpers
# =============================================================================
# Derwent returns text fields wrapped in XML namespace markup (tsip:paragraph,
# tsip:abstractTsxm, tsip:claimTsxm, tsxm:p, etc.) and joins multi-value fields
# with trailing comma padding ("BASF AG,,,,"). These helpers normalize the raw
# field values into plain strings that match the Innography Patent contract.

_XML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_EMPTY_DWPI_MARKERS = frozenset({"none given.", "none given", "n/a", ""})


def _clean_text(value: str | None) -> str:
    """Strip XML/HTML tags, decode entities, collapse whitespace, trim.

    Returns "" for empty / None / DWPI 'None given.' placeholder inputs.
    """
    if not value:
        return ""
    text = _XML_TAG_RE.sub("", str(value))
    text = html.unescape(text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    if text.lower() in _EMPTY_DWPI_MARKERS:
        return ""
    return text


def _clean_single(value: str | None) -> str:
    """Clean a single-valued field like assignee.

    Strips XML, collapses whitespace, and removes trailing comma padding
    that Derwent uses for multi-slot joins (e.g., 'BASF AG,,,,').
    """
    text = _clean_text(value)
    # Remove trailing commas and any whitespace between them
    return re.sub(r"[\s,]+$", "", text)


def _clean_list(value: str | None, sep: str = ",") -> list[str]:
    """Split a joined list value, clean each item, drop empties.

    Used for inventor names like 'Boonman  Rob,,,,' which should yield
    ['Boonman Rob'] (whitespace collapsed, empty slots dropped).
    """
    if not value:
        return []
    parts = [_clean_text(p) for p in str(value).split(sep)]
    return [p for p in parts if p]


def _extract_best(
    fields: list[dict],
    name: str,
    prefer_form: str | None = None,
    lang: str = "en",
) -> str:
    """Pick the best raw value for a field from Derwent's multi-form response.

    Derwent returns many fields (e.g. `ab`, `cl1`) in multiple forms and
    languages (orig/docdb/dwpi/native × en/fr/de/…). The naive "first match"
    strategy in _extract_field_value picks arbitrarily — often a French abstract
    when English is available.

    Preference order (first match wins):
      1. `prefer_form` AND matching `lang` (or no lang on the field)
      2. `prefer_form` (any language)
      3. Matching `lang` (any form)
      4. First match by name (fallback — preserves old behaviour)

    Args:
        fields: The raw `field` list from a Derwent response item
        name: Field name to extract (e.g. "ab", "nov", "tid")
        prefer_form: Preferred `form` attribute (e.g. "dwpi", "orig")
        lang: Preferred `lang` attribute (default "en")

    Returns:
        Raw string value (not yet cleaned — call _clean_text on the result).
        Returns "" if no field with this name exists.
    """
    matches = [f for f in fields if f.get("name") == name]
    if not matches:
        return ""

    # Tier 1: preferred form + matching language (or lang missing)
    if prefer_form:
        for f in matches:
            if f.get("form") == prefer_form and f.get("lang") in (lang, None):
                return str(f.get("value") or "")

    # Tier 2: preferred form (any language)
    if prefer_form:
        for f in matches:
            if f.get("form") == prefer_form:
                return str(f.get("value") or "")

    # Tier 3: matching language (any form)
    for f in matches:
        if f.get("lang") == lang:
            return str(f.get("value") or "")

    # Tier 4: first match (fallback)
    return str(matches[0].get("value") or "")


def _get_derwent_api_url() -> str:
    """Get Derwent API base URL from settings.
    
    Returns:
        Base API URL
    """
    settings = get_settings()
    return settings.derwent_api_base_url


def _extract_field_value(fields: list[dict], field_name: str, form: str = None) -> str:
    """Extract field value from Derwent field array.
    
    Args:
        fields: List of field dictionaries
        field_name: Name of the field to extract
        form: Optional form filter (e.g., 'orig', 'dwpi')
        
    Returns:
        Field value as string, or empty string if not found
    """
    for field in fields:
        if field.get("name") == field_name:
            # If form is specified, match it; otherwise take first match
            if form is None or field.get("form") == form:
                value = field.get("value", "")
                return str(value) if value else ""
    return ""


def _format_derwent_fld_response(data: dict) -> list[dict]:
    """Format Derwent FLD API response to structured patent list.

    Applies the response cleanup layer (Phase C): strips XML namespace markup,
    prefers English language + appropriate DWPI/orig forms, normalizes
    trailing comma padding and empty DWPI markers.

    Args:
        data: JSON response from Derwent API with body array

    Returns:
        List of patent dictionaries with cleaned, mapped fields matching
        the Innography Patent contract.
    """
    try:
        body = data.get("body", [])

        if not body:
            _logger.warning("No results in Derwent FLD response body")
            return []

        patents = []
        for item in body:
            fields = item.get("field", [])

            # Extract relevance score from rank field (convert string to float)
            rank_str = item.get("rank", "0")
            try:
                relevance_score = float(rank_str)
            except (ValueError, TypeError):
                relevance_score = 0.0

            # Extract + clean all mapped fields
            patent = {
                "publication_number":                 _clean_text(_extract_best(fields, "pn")),
                "title":                              _clean_text(_extract_best(fields, "ti",  prefer_form="orig")),
                "dwpi_title":                         _clean_text(_extract_best(fields, "tid", prefer_form="dwpi")),
                "abstract":                           _clean_text(_extract_best(fields, "ab",  prefer_form="orig")),
                "dwpi_abstract_novelty":              _clean_text(_extract_best(fields, "nov", prefer_form="dwpi")),
                "dwpi_abstract_advantage":            _clean_text(_extract_best(fields, "adv", prefer_form="dwpi")),
                "dwpi_abstract_use":                  _clean_text(_extract_best(fields, "use", prefer_form="dwpi")),
                "dwpi_abstract_detailed_description": _clean_text(_extract_best(fields, "dtd", prefer_form="dwpi")),
                "claims":                             _clean_text(_extract_best(fields, "cl1") or _extract_best(fields, "cl")),
                "priority_date":                      _clean_text(_extract_best(fields, "prd")),
                "assignee":                           _clean_single(_extract_best(fields, "co")),
                "inventors":                          _clean_list(_extract_best(fields, "in")),
                "relevance_score":                    relevance_score,
            }

            patents.append(patent)

        _logger.info(f"Formatted {len(patents)} patents from Derwent FLD response")
        return patents

    except Exception as e:
        _logger.exception("Error formatting Derwent FLD response")
        return []


# =============================================================================
# Reusable API helpers (non-tool, callable from search.py)
# =============================================================================

# Default fields requested for FLD search. Trimmed (Phase D) to drop:
#   - `dtd` (DWPI detailed description) — large, rarely referenced, net noise
#   - `cl`  (full claims) — `cl1` (first claim) is sufficient for feature-matrix
#          / triage use cases; full claims can be requested explicitly when
#          needed by passing a custom return_fields.
_DEFAULT_RETURN_FIELDS = "pn,ki,ti,tid,ab,nov,adv,use,cl1,prd,co,in,rank"


def _get_jwt_token() -> str | None:
    """Extract JWT token for the Derwent API.

    Resolution order:
      1. LangGraph runtime config `configurable.jwt_token` — set by server.py
         when a request includes `Authorization: Bearer <JWT>`. This is the
         production/frontend path.
      2. `DERWENT_JWT_TOKEN` env var — fallback for local dev
         (`langgraph dev` / LangGraph Studio / CLI / scripts), where no HTTP
         request layer injects the token into runtime config.

    Tests that patch `get_config` will still see the patched value (it takes
    priority over the env var).
    """
    try:
        config = get_config()
        token = config.get("configurable", {}).get("jwt_token")
        if token:
            return str(token)
    except (RuntimeError, ImportError):
        pass

    import os
    return os.environ.get("DERWENT_JWT_TOKEN") or None


def _derwent_fld_search(
    query: str,
    collections: str = "derwentmatlat",
    return_fields: str = _DEFAULT_RETURN_FIELDS,
    size: int = 20,
) -> list[dict] | str:
    """Core Derwent FLD search logic (no @tool decorator).

    Returns list[dict] on success or an error string on failure.
    """
    jwt_token = _get_jwt_token()
    if not jwt_token:
        _logger.warning("No JWT token available for Derwent API call")
        return "Error: Authentication required. Please provide a JWT token in the Authorization header."

    # Translate query from Derwent UI syntax to T3 FLD syntax (DRD-72/251/275).
    # Falls back to the raw query on translator failure so a broken mapping
    # never blocks a search — the API will simply reject a bad query with 400.
    try:
        translator = _get_query_translator()
        translated_query = translator.translate(query)
        _logger.info("Query translation: %r -> %r", query, translated_query)
    except Exception as e:
        _logger.warning("Query translation failed (%s); using original query.", e)
        translated_query = query

    base_url = _get_derwent_api_url()
    api_url = f"{base_url}/ip/patents/derwent/search-by-query-internal"

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    params = {
        "query": translated_query,
        "collections": collections,
        "size": str(size),
        "search-on-datatype": "fld_dwpi",
        "return-fields": return_fields,
    }

    request_body = {"params": [params]}

    try:
        with httpx.Client(timeout=60.0) as client:
            _logger.info("Calling Derwent FLD API with translated query: %s", translated_query)
            response = client.post(api_url, headers=headers, json=request_body)
            response.raise_for_status()
            data = response.json()
            _logger.info(f"Derwent FLD API call successful (status: {response.status_code})")
            return _format_derwent_fld_response(data)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            _logger.error("JWT token authentication failed for Derwent API")
            return "Error: Invalid or expired authentication token."
        elif e.response.status_code == 403:
            _logger.error("JWT token lacks permissions for Derwent API")
            return "Error: Insufficient permissions to access Derwent database."
        elif e.response.status_code == 429:
            _logger.error("Rate limit exceeded for Derwent API")
            return "Error: Rate limit exceeded. Please try again later."
        else:
            _logger.error(f"Derwent FLD API request failed: {e}")
            error_detail = ""
            try:
                error_data = e.response.json()
                error_detail = error_data.get("message", str(e))
            except Exception:
                error_detail = e.response.text[:200] if e.response.text else str(e)
            return f"Error: API request failed with status {e.response.status_code}: {error_detail}"

    except httpx.TimeoutException:
        _logger.error("Derwent FLD API request timed out")
        return "Error: Request timed out. The Derwent API is not responding."
    except httpx.NetworkError as e:
        _logger.error(f"Network error calling Derwent FLD API: {e}")
        return f"Error: Network error - unable to reach the Derwent API. {str(e)}"
    except Exception as e:
        _logger.exception("Unexpected error calling Derwent FLD API")
        return f"Error: Unexpected error - {str(e)}"


# Derwent's internal id format is publication_number + 8-digit publication date,
# e.g. ``US8718044B220140506`` or ``US3256182A_19660614``. Both with and without
# an underscore separator are accepted by the citations endpoint; what matters
# is the trailing 8-digit date suffix. Bare pub numbers (``US8718044B2``) are
# silently rejected — the endpoint responds with an empty body.
_RESOLVED_ID_RE = re.compile(r"\d{8}$")


def _looks_like_resolved_id(patent_id: str) -> bool:
    """True if the input already looks like a Derwent internal id (trailing date)."""
    return bool(_RESOLVED_ID_RE.search(patent_id.strip()))


def _resolve_patent_ids(
    patent_ids: str,
    collections: str = "derwentmatlat",
) -> tuple[str, list[str]]:
    """Expand bare publication numbers to Derwent's internal id format.

    The citation endpoint (``search-by-ids-internal``) keys on the internal id
    (``pn+pd``), not on the bare pub number returned by other tools. This
    helper does one batched FLD lookup to resolve any bare ids into the
    concatenated format.

    Args:
        patent_ids: Comma-separated list, mix of bare pub numbers and already-
            resolved ids allowed.
        collections: Collections to search (default ``derwentmatlat``).

    Returns:
        ``(resolved_comma_separated, unresolved_list)``. If ``unresolved_list``
        is non-empty, those inputs could not be found in Derwent and should be
        surfaced as errors by the caller.
    """
    inputs = [p.strip() for p in patent_ids.split(",") if p.strip()]
    resolved: list[str] = []
    to_resolve: list[str] = []
    for pid in inputs:
        if _looks_like_resolved_id(pid):
            resolved.append(pid)
        else:
            to_resolve.append(pid)

    if not to_resolve:
        return ",".join(resolved), []

    jwt_token = _get_jwt_token()
    if not jwt_token:
        return ",".join(resolved), to_resolve

    base_url = _get_derwent_api_url()
    api_url = f"{base_url}/ip/patents/derwent/search-by-query-internal"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    # Derwent doesn't support OR inside a single PN=(); clause — each patent
    # needs its own PN=() group joined with an explicit OR.
    query = " OR ".join(f"PN=({pid})" for pid in to_resolve) + ";"
    request_body = {
        "params": [{
            "query": query,
            "collections": collections,
            "size": str(len(to_resolve)),
            "search-on-datatype": "fld_dwpi",
            "return-fields": "pn,pd",
        }]
    }

    pub_to_id: dict[str, str] = {}
    try:
        with httpx.Client(timeout=30.0) as client:
            _logger.info(f"Resolving {len(to_resolve)} bare patent id(s) via FLD lookup")
            response = client.post(api_url, headers=headers, json=request_body)
            response.raise_for_status()
            data = response.json()
            for item in data.get("body", []):
                item_id = item.get("id", "")
                pn = _clean_text(_extract_best(item.get("field", []), "pn"))
                if pn and item_id:
                    pub_to_id[pn] = item_id
    except Exception as e:  # noqa: BLE001
        _logger.warning(f"Derwent id resolution failed: {e}")
        return ",".join(resolved), to_resolve

    unresolved: list[str] = []
    for pid in to_resolve:
        full_id = pub_to_id.get(pid)
        if full_id:
            resolved.append(full_id)
        else:
            unresolved.append(pid)

    return ",".join(resolved), unresolved


def _derwent_citation_search(
    patent_ids: str,
    max_citations: int = 100,
    collections: str = "derwentmatlat",
) -> dict | list[dict]:
    """Core Derwent citation search logic (no @tool decorator).

    Accepts either bare publication numbers (``US8718044B2``) or already-
    resolved Derwent ids (``US8718044B220140506``). Bare numbers are
    auto-resolved via an FLD lookup before hitting the citations endpoint.

    Returns dict/list[dict] on success or a dict with 'error' key on failure.
    """
    jwt_token = _get_jwt_token()
    if not jwt_token:
        _logger.warning("No JWT token available for Derwent citation search")
        return {"error": "Authentication required. Please provide a JWT token in the Authorization header."}

    resolved_ids, unresolved = _resolve_patent_ids(patent_ids, collections)
    if not resolved_ids:
        return {
            "error": (
                f"Could not resolve any of the supplied patent ids to Derwent "
                f"internal ids: {unresolved}"
            )
        }
    if unresolved:
        _logger.warning(
            f"Derwent citation search skipping {len(unresolved)} unresolvable "
            f"pub number(s): {unresolved}"
        )

    base_url = _get_derwent_api_url()
    api_url = f"{base_url}/ip/patents/derwent/search-by-ids-internal"

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
    }

    patent_ids = resolved_ids
    num_patents = len([p.strip() for p in patent_ids.split(',') if p.strip()])

    params = {
        "ids": patent_ids,
        "collections": collections,
        "size": num_patents,
        "return-fields": "pn,ki,tid,ti,nov,pd,prd,ceed,caid,re,ab,adv,pa,co,an,in,cl,cl1,id,dcipct,dcipfct",
        "filter": f"expand:citations@1;1;{max_citations}",
        "search-on-datatype": "fld_dwpi",
        "response-id-validation": False,
        "return-body": "true",
        "return-documents": "true",
        "return-listref": "false",
        "dwpi-basic": True,
    }

    request_body = {"params": [params]}

    try:
        with httpx.Client(timeout=60.0) as client:
            _logger.info(f"Calling Derwent API for patent citations: {patent_ids[:100]}...")
            response = client.post(api_url, headers=headers, json=request_body)
            response.raise_for_status()
            data = response.json()
            _logger.info(f"Derwent citation search successful (status: {response.status_code})")
            return _format_citation_response_json(data, patent_ids)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            _logger.error("JWT token authentication failed for Derwent API")
            return {"error": "Invalid or expired authentication token."}
        elif e.response.status_code == 403:
            _logger.error("JWT token lacks permissions for Derwent API")
            return {"error": "Insufficient permissions to access Derwent database."}
        elif e.response.status_code == 429:
            _logger.error("Rate limit exceeded for Derwent API")
            return {"error": "Rate limit exceeded. Please try again later."}
        else:
            _logger.error(f"Derwent API request failed: {e}")
            error_detail = e.response.text[:200] if e.response.text else str(e)
            return {"error": f"API request failed with status {e.response.status_code}: {error_detail}"}

    except httpx.TimeoutException:
        _logger.error("Derwent API request timed out")
        return {"error": "Request timed out. The Derwent API is not responding."}
    except httpx.NetworkError as e:
        _logger.error(f"Network error calling Derwent API: {e}")
        return {"error": f"Network error - unable to reach the Derwent API. {str(e)}"}
    except Exception as e:
        _logger.exception("Unexpected error calling Derwent citation API")
        return {"error": f"Unexpected error - {str(e)}"}


# =============================================================================
# @tool wrappers (thin wrappers calling the helpers above)
# =============================================================================

@tool
def search_derwent_patents_fld(
    query: Annotated[str, "Derwent query with field tags. Broad: 'CTB=(terms);' DWPI-specific: 'NOV=(terms);', 'TID=(terms);' Broadest: 'ALL=(terms);'"],
    collections: Annotated[str, "Database collections to search"] = "derwentmatlat",
    return_fields: Annotated[str, "Comma-separated field list"] = _DEFAULT_RETURN_FIELDS,
    size: Annotated[int, "Number of results per page"] = 20,
) -> list[dict]:
    """Full-text search for patents in Clarivate Derwent database using query syntax.

    Field tags for queries (choose based on precision):
    - CTB=(terms); — Title+Abstract+Claims (DWPI+original). Default for novelty search.
    - ALL=(terms); — All text fields including description. Broadest.
    - TID=(terms); — Derwent enhanced title. High precision.
    - NOV=(terms); — DWPI Novelty section. What is NEW — highest value for novelty.
    - ADV=(terms); — DWPI Advantage section. Technical benefits.
    - USE=(terms); — DWPI Use section. Applications.
    - ABD=(terms); — Full Derwent abstract (NOV+USE+ADV).
    - TI=(terms); — Original title. AB=(terms); — Original abstract.
    - CL1=(terms); — First claim. IC=(code); — IPC classification.
    - PN=(number); — Patent number lookup.

    Operators: AND, OR, NOT, NEAR, NEARn, ADJ, ADJn, SAME
    Truncation: * (0+ chars), ? (1 char). End queries with ;

    Args:
        query: Derwent query string with field tags
        collections: Database collections to search (default: derwentmatlat)
        return_fields: Fields to return
        size: Number of results to return (default: 20)

    Returns:
        List of patent dicts with: publication_number, title, dwpi_title, abstract,
        dwpi_abstract_novelty, dwpi_abstract_advantage, dwpi_abstract_use,
        dwpi_abstract_detailed_description, claims, priority_date, assignee,
        inventors, relevance_score
    """
    return _derwent_fld_search(query, collections, return_fields, size)


@tool
def search_derwent_citations(
    patent_ids: Annotated[str, "Comma-separated patent IDs to retrieve with citations (e.g., 'US3256182A_19660614, US3256223A_19660614')"],
    max_citations: Annotated[int, "Maximum citations to retrieve per patent (forward + backward)"] = 100,
    collections: Annotated[str, "Database collections"] = "derwentmatlat",
) -> dict | list[dict]:
    """Search for patents and retrieve their forward and backward citations from Derwent.

    Args:
        patent_ids: Comma-separated patent publication numbers
        max_citations: Maximum number of citations to retrieve per patent (default: 100)
        collections: Database collections to search (default: derwentmatlat)

    Returns:
        Dictionary (single patent) or list of dictionaries (multiple patents) with:
        - patent_number, total_forward_citations, total_backward_citations,
        - forward_citations, backward_citations
    """
    return _derwent_citation_search(patent_ids, max_citations, collections)


def _format_citation_response_json(data: dict, patent_ids: str) -> dict | list[dict]:
    """Format Derwent citation API response matching Innography structure.
    
    Args:
        data: JSON response from Derwent API with citation data
        patent_ids: Original patent IDs queried
        
    Returns:
        Dictionary or list of dictionaries with structured patent and citation information
    """
    
    try:
        body = data.get("body", [])
        
        if not body:
            return {"error": f"No data found for patent IDs: {patent_ids}"}
        
        # Group by main patent ID
        patent_groups = {}
        
        for item in body:
            ref_value = item.get("ref_value", "")
            item_id = item.get("id", "")
            ref_id = item.get("ref_id", "")
            
            if not ref_value:
                # This is a main patent (no ref_value)
                if item_id not in patent_groups:
                    patent_groups[item_id] = {
                        "main": item,
                        "forward": [],
                        "backward": []
                    }
            else:
                # This is a citation - associate with the patent it references
                if ref_value == "forward-citation":
                    if ref_id not in patent_groups:
                        patent_groups[ref_id] = {"main": None, "forward": [], "backward": []}
                    patent_groups[ref_id]["forward"].append(item)
                elif ref_value == "backward-citation":
                    if ref_id not in patent_groups:
                        patent_groups[ref_id] = {"main": None, "forward": [], "backward": []}
                    patent_groups[ref_id]["backward"].append(item)
        
        # Build result for each patent matching Innography structure
        results = []
        for patent_id, group in patent_groups.items():
            if group["main"]:
                # Extract main patent publication number
                main_patent_fields = _extract_patent_fields(group["main"])
                patent_number = main_patent_fields.get("publication_number", patent_id)
                
                # Build result matching Innography structure
                result = {
                    "patent_number": patent_number,
                    "total_forward_citations": len(group["forward"]),
                    "total_backward_citations": len(group["backward"]),
                    "forward_citations": [],
                    "backward_citations": []
                }
                
                # Format forward citations
                for citation in group["forward"]:
                    citation_dict = _extract_citation_fields(citation)
                    result["forward_citations"].append(citation_dict)
                
                # Format backward citations
                for citation in group["backward"]:
                    citation_dict = _extract_citation_fields(citation)
                    result["backward_citations"].append(citation_dict)
                
                results.append(result)
        
        # If only one patent requested, return single object; otherwise array
        patent_list = [p.strip() for p in patent_ids.split(',') if p.strip()]
        if len(patent_list) == 1 and len(results) == 1:
            return results[0]
        else:
            return results
    
    except Exception as e:
        _logger.exception("Error formatting Derwent citation response")
        return {"error": f"Formatting error: {str(e)}"}


def _extract_patent_fields(patent_item: dict) -> dict:
    """Extract patent fields from Derwent field array structure.

    Applies response cleanup (Phase C): XML-stripped, whitespace-collapsed,
    trailing-comma-trimmed values.

    Args:
        patent_item: Patent object with 'field' array

    Returns:
        Dictionary with mapped, cleaned field names
    """
    fields = patent_item.get("field", [])

    _logger.debug(f"Patent item keys: {patent_item.keys()}, field count: {len(fields)}")

    # Raw numeric fields (need type conversion, not text cleanup)
    backward_count = _extract_best(fields, "dcipct")
    forward_count = _extract_best(fields, "dcipfct")
    try:
        backward_citation_count = int(backward_count) if backward_count else 0
    except (ValueError, TypeError):
        backward_citation_count = 0
    try:
        forward_citation_count = int(forward_count) if forward_count else 0
    except (ValueError, TypeError):
        forward_citation_count = 0

    relevance_val = _extract_best(fields, "re")
    try:
        relevance = float(relevance_val) if relevance_val else None
    except (ValueError, TypeError):
        relevance = None

    # Build the result dict with cleaned field mappings
    publication_number = _clean_text(_extract_best(fields, "pn"))
    return {
        "publication_number":              publication_number or None,
        "title":                           _clean_text(_extract_best(fields, "ti",  prefer_form="orig")),
        "dwpi_title":                      _clean_text(_extract_best(fields, "tid", prefer_form="dwpi")),
        "current_assignee_name":           _clean_single(_extract_best(fields, "co")),
        "derwent_current_assignee_name":   _clean_single(_extract_best(fields, "pa")),
        "publish_date":                    _clean_text(_extract_best(fields, "pd")),
        "priority_date":                   _clean_text(_extract_best(fields, "prd")),
        "expiration_date":                 _clean_text(_extract_best(fields, "ceed")),
        "status":                          _clean_text(_extract_best(fields, "caid")),
        "relevance":                       relevance,
        "dwpi_abstract_novelty":           _clean_text(_extract_best(fields, "nov", prefer_form="dwpi")),
        "abstract":                        _clean_text(_extract_best(fields, "ab",  prefer_form="orig")),
        "backward_citation_count":         backward_citation_count,
        "forward_citation_count":          forward_citation_count,
        "inventor":                        _clean_single(_extract_best(fields, "in")),
    }


def _extract_citation_fields(citation_item: dict) -> dict:
    """Extract citation fields matching Innography structure.

    Applies response cleanup (Phase C): XML-stripped, whitespace-collapsed,
    trailing-comma-trimmed values.

    Args:
        citation_item: Citation patent object with 'field' array

    Returns:
        Dictionary with cleaned citation fields matching Innography format
    """
    fields = citation_item.get("field", [])
    document_id = citation_item.get("id", "")

    field_names = [f.get("name") for f in fields if f.get("name")]
    _logger.debug(f"Citation ID: {document_id}, {len(fields)} fields: {field_names}")

    # Publication number: try `pn` field, fall back to document ID
    publication_number = _clean_text(_extract_best(fields, "pn"))
    if not publication_number and document_id:
        publication_number = _clean_text(document_id)
        _logger.debug(f"Using document ID as pn: {publication_number}")

    return {
        "publication_number": publication_number,
        "title":              _clean_text(_extract_best(fields, "ti",  prefer_form="orig")),
        "dwpi_title":         _clean_text(_extract_best(fields, "tid", prefer_form="dwpi")),
        "assignee":           _clean_single(_extract_best(fields, "co")),
        "derwent_assignee":   _clean_single(_extract_best(fields, "pa")),
        "publication_date":   _clean_text(_extract_best(fields, "pd")),
        "priority_date":      _clean_text(_extract_best(fields, "prd")),
        "expiration_date":    _clean_text(_extract_best(fields, "ceed")),
        "status":             _clean_text(_extract_best(fields, "caid")),
        "relevance":          _clean_text(_extract_best(fields, "re")),
        "abstract":           _clean_text(_extract_best(fields, "ab",  prefer_form="orig")),
        "dwpi_novelty":       _clean_text(_extract_best(fields, "nov", prefer_form="dwpi")),
    }
