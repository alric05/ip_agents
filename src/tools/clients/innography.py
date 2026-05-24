"""
Innography Patent Search API Client.

This module provides a complete, self-contained implementation of the Innography
patent search API client. No external dependencies on other project modules.

Configuration (via environment variables):
    INNOGRAPHY_USER_NAME: API username
    INNOGRAPHY_USER_SECRET: API secret
    INNOGRAPHY_USER_TOKEN: API token
    INNOGRAPHY_TOKEN_URL: Token endpoint URL
    INNOGRAPHY_SERVICES_URL: Services endpoint URL
"""

import base64
import hashlib
import hmac
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import requests
from langchain_core.tools import tool

# Import settings - handle both package and direct execution
try:
    from src.config.settings import get_settings
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.config.settings import get_settings

# Import schemas from same directory
from src.tools.clients.schemas import Patent, SearchResult

LOGGER = logging.getLogger("langgraph_agent.tools.innography")

# Standard fields to request from Innography API
STANDARD_PATENT_FIELDS = [
    'naturalid',
    'kindCode',
    'title',
    'dwpi_title',
    'dwpi_abstract_novelty',
    'abstract',
    'dwpi_abstract_advantage',
    'dwpi_abstract_use',
    'rawFirstClaim',
    'dwpi_abstract_detailed_description',
    'claims',
    'priorityDate',
    'assigneeStandardized',
    'inventors',
]


@dataclass
class InnographyConfig:
    """Configuration for Innography API."""
    user_name: str
    user_secret: str
    user_token: str
    token_url: str
    services_url: str
    
    @classmethod
    def from_settings(cls) -> "InnographyConfig":
        """Create config from settings."""
        settings = get_settings()
        return cls(
            user_name=settings.innography_user_name or "",
            user_secret=settings.innography_user_secret or "",
            user_token=settings.innography_user_token or "",
            token_url=settings.innography_token_url,
            services_url=settings.innography_services_url,
        )
    
    def is_configured(self) -> bool:
        """Check if all required credentials are present."""
        return bool(
            self.user_name and 
            self.user_secret and 
            self.user_token
        )


class InnographyClient:
    """
    Client for Innography patent search API.
    
    Self-contained implementation that handles authentication,
    query validation, and result parsing.
    """
    
    def __init__(self, config: Optional[InnographyConfig] = None):
        """
        Initialize the client.
        
        Args:
            config: Optional configuration. If not provided, loads from settings.
        """
        self.config = config or InnographyConfig.from_settings()
        self._access_token: Optional[str] = None
        self._session = requests.Session()
    
    def _get_token(self) -> str:
        """
        Get API access token using HMAC authentication.
        
        Returns:
            Access token string
        """
        if self._access_token:
            return self._access_token
        
        token_auth = {"email": self.config.user_token}
        request_data_json = json.dumps(token_auth)
        date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        content_md5 = base64.b64encode(
            hashlib.md5(request_data_json.encode()).digest()
        ).decode()
        
        hash_obj = hmac.new(
            self.config.user_secret.encode(),
            f"Date: {date}\nContent-MD5: {content_md5}".encode(),
            hashlib.sha1
        )
        
        auth = (
            f'hmac username="{self.config.user_name}", '
            'algorithm="hmac-sha1", headers="Date Content-MD5", '
            f'signature="{base64.b64encode(hash_obj.digest()).decode()}"'
        )
        
        headers = {
            "Content-Type": "application/json",
            "Content-MD5": content_md5,
            "Date": date,
            "Authorization": auth,
            "Accept": "application/vnd.innography+json; version=0.9",
        }
        
        try:
            response = self._session.post(
                self.config.token_url,
                json=token_auth,
                headers=headers,
                timeout=30,
            )
            response_data = response.json()
            
            if token := response_data.get("result"):
                LOGGER.info("Innography access token obtained successfully")
                self._access_token = token
                return token
            
            raise ValueError(
                f'Could not get token. Innography error: {response_data.get("message", "")}'
            )
            
        except requests.RequestException as e:
            LOGGER.error("Failed to get Innography token: %s", e)
            raise
    
    def _validate_and_fix_query(self, query: str) -> str:
        """
        Validate and fix common Innography query issues.
        
        Fixes:
        1. Spaces after commas in field lists: @(title, abstract) -> @(title,abstract)
        2. Checks for NPL syntax being used incorrectly
        3. Validates parentheses balance
        
        Args:
            query: The query to validate
            
        Returns:
            Fixed query string
        """
        query = query.strip()
        original = query

        # Fix 1: Remove spaces after commas in @() field lists
        def fix_field_spaces(match):
            fields = match.group(1)
            fixed_fields = re.sub(r'\s*,\s*', ',', fields)
            return f'@({fixed_fields})'

        query = re.sub(r'@\(([^)]+)\)', fix_field_spaces, query)

        # Fix 2: Check for NPL syntax being used (common mistake)
        npl_patterns = ['TS=', 'TI=', 'AB=', 'AK=', 'AD=', 'SO=']
        for pattern in npl_patterns:
            if pattern in query.upper():
                LOGGER.warning(
                    "Patent query contains NPL syntax '%s'. Use @(field) syntax for patent searches.",
                    pattern
                )

        # Fix 3: Warn about unbalanced parentheses
        open_count = query.count('(')
        close_count = query.count(')')
        if open_count != close_count:
            LOGGER.warning(
                "Patent query has unbalanced parentheses (open=%d, close=%d): %s",
                open_count, close_count, query[:100]
            )

        if query != original:
            LOGGER.info("Patent query fixed. Original: %s | Fixed: %s", original[:100], query[:100])

        return query
    
    def _simplify_query(self, query: str) -> str:
        """
        Simplify a complex patent query to basic terms for fallback.
        
        Args:
            query: Complex query to simplify
            
        Returns:
            Simplified query
        """
        # Remove field scoping
        clean = re.sub(r'@\([^)]+\)\s*', '', query)

        # Remove operators
        clean = re.sub(r'\b(AND|OR|NOT|NEAR(/\d+)?|ADJ(/\d+)?)\b', ' ', clean, flags=re.IGNORECASE)

        # Remove parentheses and quotes
        clean = re.sub(r'[()"]', ' ', clean)

        # Extract meaningful words
        words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9*-]{2,}\b', clean)

        # Dedupe
        seen = set()
        unique = []
        for w in words:
            if w.lower() not in seen:
                seen.add(w.lower())
                unique.append(w)

        # Take top 5 words
        key_words = unique[:5]

        if not key_words:
            return query

        return f"@(title,abstract) ({' AND '.join(key_words)})"
    
    def _build_patent_from_result(self, result: dict) -> Patent:
        """Build a Patent object from an Innography API result."""
        return Patent(
            publication_number=result.get("naturalid", "") + result.get("kindCode", ""),
            title=result.get("title"),
            dwpi_title=result.get("dwpi_title"),
            abstract=result.get("abstract"),
            dwpi_abstract_novelty=result.get("dwpi_abstract_novelty"),
            dwpi_abstract_advantage=result.get("dwpi_abstract_advantage"),
            dwpi_abstract_use=result.get("dwpi_abstract_use"),
            dwpi_abstract_detailed_description=result.get("dwpi_abstract_detailed_description"),
            claims=result.get("rawFirstClaim") or result.get("claims"),
            priority_date=result.get("priorityDate"),
            assignee=result.get("assigneeStandardized"),
            inventors=result.get("inventors", []),
        )
    
    def patent_keyword_search(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[Patent]:
        """
        Execute a patent keyword search.
        
        QUERY SYNTAX (Innography):
        
        1. FIELD SCOPING (NO SPACES in multi-field lists!):
           ✅ @(title,abstract,claims) — searches all specified fields
           ❌ @(title, abstract, claims) — SPACES CAUSE API ERRORS!
           • DWPI fields: @(dwpi_title,dwpi_novelty,dwpi_advantage)
           • Native fields: @title, @abstract, @claims, @inventor
        
        2. BOOLEAN OPERATORS:
           • AND (or space): coffee AND tea
           • OR (or |): coffee OR tea
           • NOT (or - or !): coffee NOT java
        
        3. PROXIMITY OPERATORS:
           • "phrase"~N: "blue car"~3 — terms within N words
           • NEAR/N: (coffee OR espresso) NEAR/5 (grind OR mill)
           • ADJ/N: coffee ADJ/2 container — ORDER ENFORCED
        
        Args:
            query: Innography query syntax
            max_results: Maximum number of results to return
        
        Returns:
            List of Patent objects
        """
        if not self.config.is_configured():
            raise ValueError(
                "Innography API not configured. Set INNOGRAPHY_* environment variables."
            )
        
        token = self._get_token()
        
        # Build retry queue with progressively simpler queries
        queries_to_try = [
            self._validate_and_fix_query(query),
        ]
        
        # Add simplified version
        simplified = self._simplify_query(query)
        if simplified != queries_to_try[0]:
            queries_to_try.append(simplified)
        
        # Ultra-simple fallback
        key_terms = re.findall(r'\b[a-zA-Z]{4,}\b', query)[:3]
        if key_terms:
            ultra_simple = f"@(title,abstract) ({' OR '.join(key_terms)})"
            if ultra_simple not in queries_to_try:
                queries_to_try.append(ultra_simple)
        
        last_error = None
        for attempt, query_str in enumerate(queries_to_try, 1):
            LOGGER.info("Patent query attempt %d/%d: %s", attempt, len(queries_to_try), query_str[:150])
            
            query_dict = {
                'querySequence': [{
                    'method': '',
                    'queryObject': {
                        'type': 'patent',
                        'query': f'({query_str})',
                        'sources': [],
                        'includeDwpi': True
                    },
                    'queryModifier': {
                        'fields': STANDARD_PATENT_FIELDS,
                        'sort': [['relevance', 'DESC']],
                        'group': 'patentfamily',
                        'offset': 0,
                        'limit': max_results,
                        'callback': 'pointersFunc'
                    }
                }],
                'access': {'accessToken': token}
            }
            
            try:
                response = self._session.post(
                    f"{self.config.services_url}/search",
                    json=query_dict,
                    timeout=60,
                )
                response.raise_for_status()
                
                data = response.json()
                results = data.get('results', [])
                
                if results:
                    patents = [self._build_patent_from_result(r) for r in results]
                    LOGGER.info("Patent query succeeded with %d results", len(patents))
                    return patents
                else:
                    LOGGER.info("Patent query returned 0 results on attempt %d", attempt)
                    
            except requests.RequestException as e:
                last_error = str(e)
                LOGGER.warning("Patent query attempt %d failed: %s", attempt, last_error[:200])
        
        if last_error:
            LOGGER.error("All patent query attempts failed. Last error: %s", last_error)
        
        return []
    
    def get_patent_contents(self, publication_number: str) -> Optional[Patent]:
        """
        Retrieve detailed patent information by publication number.
        
        Args:
            publication_number: Patent publication number (e.g., 'US1234567A1')
        
        Returns:
            Patent object or None if not found
        """
        if not self.config.is_configured():
            raise ValueError(
                "Innography API not configured. Set INNOGRAPHY_* environment variables."
            )
        
        token = self._get_token()
        
        # First, lookup the internal document IDs
        initial_query = {
            "ids": [publication_number],
            "idType": 1,
            'access': {"accessToken": token}
        }
        
        try:
            response = self._session.post(
                f"{self.config.services_url}/import/lookup_item_ids",
                json=initial_query,
                timeout=30,
            )
            response.raise_for_status()
            
            matches = response.json().get('matches', {})
            doc_ids = [str(v2) for v in matches.values() for v2 in v]
            
            if not doc_ids:
                LOGGER.info("No matches found for publication number: %s", publication_number)
                return None
            
            # Now fetch the patent data
            query_dict = {
                'querySequence': [{
                    'method': '',
                    'queryObject': {
                        'type': 'patent',
                        'filters': {
                            'AND': [{
                                'column': 'document',
                                'operator': 'IN',
                                'value': list(set(doc_ids)),
                            }]
                        },
                        'sources': [],
                        'includeDwpi': True
                    },
                    'queryModifier': {
                        'fields': STANDARD_PATENT_FIELDS,
                        'sort': [['relevance', 'DESC']],
                        'group': 'patentfamily',
                        'offset': 0,
                        'limit': 20,
                        'callback': 'pointersFunc'
                    }
                }],
                'access': {'accessToken': token}
            }
            
            response = self._session.post(
                f"{self.config.services_url}/search",
                json=query_dict,
                timeout=60,
            )
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            if results:
                return self._build_patent_from_result(results[0])
            
            return None
            
        except requests.RequestException as e:
            LOGGER.error("Error retrieving patent contents: %s", e)
            return None

    def get_citations_by_doc_id(
        self, 
        doc_ids: list[str], 
        citation_type: str = 'forward'
    ) -> list[dict]:
        """
        Get citations for patents by document IDs.
        
        Args:
            doc_ids: List of internal document IDs
            citation_type: Either 'forward' or 'backward'
            
        Returns:
            List of citation dictionaries
        """
        if not self.config.is_configured():
            raise ValueError(
                "Innography API not configured. Set INNOGRAPHY_* environment variables."
            )
        
        token = self._get_token()
        method = 'forward_citation' if citation_type == 'forward' else 'backward_citation'
        
        query_dict = {
            'querySequence': [
                {
                    'method': method,
                    'queryObject': {
                        'type': 'patent',
                        'query': '',
                        'filters': {
                            'AND': [{
                                'column': 'document',
                                'operator': 'IN',
                                'value': doc_ids,
                            }]
                        },
                        'sources': [],
                        'includeDwpi': False
                    },
                    'queryModifier': False
                },
                {
                    'method': '',
                    'queryObject': {
                        'type': 'patent',
                        'query': '',
                        'filters': {'AND': []},
                        'sources': [],
                        'includeDwpi': True
                    },
                    'queryModifier': {
                        'fields': [
                            'naturalid', 'kindCode', 'title', 'dwpi_title',
                            'currentAssigneeName', 'publishDate', 'relevance',
                            'priorityDate', 'expirationDate', 'status',
                            'abstract', 'dwpi_abstract_novelty'
                        ],
                        'sort': [['relevance', 'DESC']],
                        'offset': 0,
                        'limit': 100,
                        'callback': 'pointersFunc'
                    }
                }
            ],
            'access': {'accessToken': token}
        }
        
        try:
            response = self._session.post(
                f"{self.config.services_url}/search",
                json=query_dict,
                timeout=60,
            )
            response.raise_for_status()
            return response.json().get('results', [])
        except requests.RequestException as e:
            LOGGER.error("Error retrieving %s citations: %s", citation_type, e)
            return []

    def get_patent_citations(self, publication_number: str) -> dict:
        """
        Get both forward and backward citations for a patent.
        
        Forward citations: Patents that cite this patent (newer work building on this)
        Backward citations: Patents that this patent cites (prior art)
        
        Args:
            publication_number: Patent publication number (e.g., 'US8718044', 'EP3411222B1')
            
        Returns:
            Dictionary with structure:
            {
                "patent_number": str,
                "total_forward_citations": int,
                "total_backward_citations": int,
                "forward_citations": List[Dict],
                "backward_citations": List[Dict]
            }
        """
        if not self.config.is_configured():
            raise ValueError(
                "Innography API not configured. Set INNOGRAPHY_* environment variables."
            )
        
        token = self._get_token()
        
        # First, lookup the internal document IDs
        initial_query = {
            "ids": [publication_number],
            "idType": 1,
            'access': {"accessToken": token}
        }
        
        result = {
            "patent_number": publication_number,
            "total_forward_citations": 0,
            "total_backward_citations": 0,
            "forward_citations": [],
            "backward_citations": []
        }
        
        try:
            response = self._session.post(
                f"{self.config.services_url}/import/lookup_item_ids",
                json=initial_query,
                timeout=30,
            )
            response.raise_for_status()
            
            matches = response.json().get('matches', {})
            doc_ids = [str(v2) for v in matches.values() for v2 in v]
            
            if not doc_ids:
                LOGGER.info("No matches found for publication number: %s", publication_number)
                return result
            
            doc_ids = list(set(doc_ids))
            
            # Get forward citations
            forward_results = self.get_citations_by_doc_id(doc_ids, citation_type='forward')
            result["total_forward_citations"] = len(forward_results)
            
            for citation in forward_results:
                citation_dict = {
                    "publication_number": citation.get("naturalid", "") + citation.get("kindCode", ""),
                    "title": citation.get("title", ""),
                    "dwpi_title": citation.get("dwpi_title", ""),
                    "assignee": citation.get("currentAssigneeName", ""),
                    "publication_date": citation.get("publishDate", ""),
                    "priority_date": citation.get("priorityDate", ""),
                    "expiration_date": citation.get("expirationDate", ""),
                    "status": citation.get("status", ""),
                    "relevance": citation.get("relevance", ""),
                    "abstract": citation.get("abstract", ""),
                    "dwpi_novelty": citation.get("dwpi_abstract_novelty", "")
                }
                result["forward_citations"].append(citation_dict)
            
            # Get backward citations
            backward_results = self.get_citations_by_doc_id(doc_ids, citation_type='backward')
            result["total_backward_citations"] = len(backward_results)
            
            for citation in backward_results:
                citation_dict = {
                    "publication_number": citation.get("naturalid", "") + citation.get("kindCode", ""),
                    "title": citation.get("title", ""),
                    "dwpi_title": citation.get("dwpi_title", ""),
                    "assignee": citation.get("currentAssigneeName", ""),
                    "publication_date": citation.get("publishDate", ""),
                    "priority_date": citation.get("priorityDate", ""),
                    "expiration_date": citation.get("expirationDate", ""),
                    "status": citation.get("status", ""),
                    "relevance": citation.get("relevance", ""),
                    "abstract": citation.get("abstract", ""),
                    "dwpi_novelty": citation.get("dwpi_abstract_novelty", "")
                }
                result["backward_citations"].append(citation_dict)
            
            return result
            
        except requests.RequestException as e:
            LOGGER.error("Error retrieving patent citations: %s", e)
            return result


# ═══════════════════════════════════════════════════════════════════════════════
# LangChain Tool Functions
# ═══════════════════════════════════════════════════════════════════════════════

@tool
def patent_keyword_search_tool(query: str, max_results: int = 10) -> list[dict]:
    """
    Search for patents using Innography keyword search.
    
    Use this tool to find patents relevant to technical concepts or inventions.
    
    QUERY SYNTAX:
    - Field scoping: @(title,abstract,claims) term — NO SPACES in field lists!
    - Boolean: AND, OR, NOT
    - Proximity: NEAR/N, ADJ/N (e.g., (hydraulic NEAR/5 valve))
    - Quotes: "exact phrase"
    
    Example queries:
    - @(title,abstract) (hydraulic NEAR/5 valve) AND actuator
    - @(dwpi_title,dwpi_novelty) ((soft OR compliant) NEAR/5 gripper)
    
    Args:
        query: Innography query syntax string
        max_results: Maximum number of patents to return (default: 10)
    
    Returns:
        List of patent dictionaries with publication_number, title, abstract, etc.
    """
    client = InnographyClient()
    patents = client.patent_keyword_search(query, max_results)
    return [p.to_dict() for p in patents]


@tool
def get_patent_by_number(publication_number: str) -> Optional[dict]:
    """
    Retrieve detailed patent information by publication number.
    
    Use this tool to get full details of a specific patent when you know its number.
    
    Args:
        publication_number: Patent publication number (e.g., 'US1234567A1')
    
    Returns:
        Patent dictionary with full details, or None if not found
    """
    client = InnographyClient()
    patent = client.get_patent_contents(publication_number)
    return patent.to_dict() if patent else None


@tool
def get_patent_citations_tool(publication_number: str) -> dict:
    """
    Retrieve forward and backward citations for a patent.
    
    Use this tool to find:
    - Forward citations: Patents that cite this patent (newer work building on this)
    - Backward citations: Patents that this patent cites (prior art references)
    
    This is useful for:
    - Finding related newer patents in a technology space
    - Understanding the prior art landscape
    - Tracing patent lineage and technology evolution
    - Identifying key foundational patents
    
    Args:
        publication_number: Patent publication number (e.g., 'US8718044', 'EP3411222B1')
    
    Returns:
        Dictionary with:
        - patent_number: The queried patent
        - total_forward_citations: Count of citing patents
        - total_backward_citations: Count of cited patents
        - forward_citations: List of patents citing this one
        - backward_citations: List of patents cited by this one
    """
    client = InnographyClient()
    return client.get_patent_citations(publication_number)


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience Functions (non-tool versions for internal use)
# ═══════════════════════════════════════════════════════════════════════════════

def patent_keyword_search(query: str, max_results: int = 10) -> list[Patent]:
    """
    Search for patents (non-tool version).
    
    Args:
        query: Innography query syntax
        max_results: Maximum results
    
    Returns:
        List of Patent objects
    """
    client = InnographyClient()
    return client.patent_keyword_search(query, max_results)


def get_patent(publication_number: str) -> Optional[Patent]:
    """
    Get patent by number (non-tool version).
    
    Args:
        publication_number: Patent publication number
    
    Returns:
        Patent object or None
    """
    client = InnographyClient()
    return client.get_patent_contents(publication_number)


def get_patent_citations(publication_number: str) -> dict:
    """
    Get patent citations (non-tool version).
    
    Args:
        publication_number: Patent publication number
    
    Returns:
        Dictionary with forward and backward citations
    """
    client = InnographyClient()
    return client.get_patent_citations(publication_number)


def convert_patents_to_search_results(patents: list[Patent]) -> list[SearchResult]:
    """Convert Patent objects to generic SearchResult objects."""
    return [
        SearchResult(
            ref_id=p.publication_number,
            ref_type="patent",
            title=p.title or p.dwpi_title or "",
            abstract=p.abstract or p.dwpi_abstract_novelty or "",
            relevance_score=p.relevance_score or 0.0,
            source="innography",
            metadata={
                "dwpi_title": p.dwpi_title,
                "dwpi_advantage": p.dwpi_abstract_advantage,
                "priority_date": p.priority_date,
                "assignee": p.assignee,
            }
        )
        for p in patents
    ]
