"""
Web of Science (WOS) NPL Search API Client.

This module provides a complete, self-contained implementation of the Web of Science
API client for non-patent literature (NPL) searches.

Configuration (via environment variables):
    WOS_API_KEY: Web of Science API key
    WOS_ENDPOINT: WOS API endpoint URL (default: https://wos-api.clarivate.com/api/wos)
"""

import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

import requests
from langchain_core.tools import tool
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Import settings - handle both package and direct execution
try:
    from src.config.settings import get_settings
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.config.settings import get_settings

# Import schemas from same directory
from src.tools.clients.schemas import Article, DateBoundaries, SearchResult, Sorting

LOGGER = logging.getLogger("langgraph_agent.tools.wos")

# Valid Web of Science field tags
WOS_FIELD_TAGS = ['TS', 'TI', 'AB', 'AK', 'AD', 'SO', 'DO', 'AU', 'UT', 'OG', 'SU', 'IS', 'PY']
WOS_FIELD_PATTERN = re.compile(r'^\s*(' + '|'.join(WOS_FIELD_TAGS) + r')\s*=', re.IGNORECASE)


def _mount_retry_session() -> requests.Session:
    """Create a session with retry logic."""
    retry = Retry(
        total=4,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False,
        backoff_jitter=1,
        backoff_max=2,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


@dataclass
class WOSConfig:
    """Configuration for Web of Science API."""
    api_key: str
    endpoint: str
    
    @classmethod
    def from_settings(cls) -> "WOSConfig":
        """Create config from settings."""
        settings = get_settings()
        return cls(
            api_key=settings.wos_api_key or "",
            endpoint=settings.wos_endpoint,
        )
    
    def is_configured(self) -> bool:
        """Check if API key is present."""
        return bool(self.api_key)


class WOSClient:
    """
    Client for Web of Science API.
    
    Self-contained implementation with query validation and result parsing.
    """
    
    def __init__(self, config: Optional[WOSConfig] = None):
        """
        Initialize the client.
        
        Args:
            config: Optional configuration. If not provided, loads from settings.
        """
        self.config = config or WOSConfig.from_settings()
        self._session = _mount_retry_session()
        self._headers = {
            "Content-Type": "application/json",
            "X-ApiKey": self.config.api_key,
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Query Validation and Fixing
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _validate_and_fix_wildcards(self, query: str) -> str:
        """
        Validate and fix wildcard usage according to WoS rules.
        
        WoS Wildcard Rules:
        - * (asterisk): Any group of characters, including none
        - ? (question mark): Exactly ONE character
        - $ (dollar sign): ZERO or ONE character
        - Minimum 3 characters before right-hand wildcard
        - Minimum 3 characters after left-hand wildcard
        """
        if not query:
            return query

        original = query

        # Fix wildcards after only 1-2 alphanumeric characters
        def fix_short_right_wildcard(match):
            prefix = match.group(1) if match.lastindex >= 1 else ""
            LOGGER.warning("Removing wildcard from short term (need 3+ chars before */?/$)")
            return prefix

        query = re.sub(r'(?<![a-zA-Z0-9])([a-zA-Z0-9]{1,2})([*?$])', fix_short_right_wildcard, query)

        # Fix wildcards followed by only 1-2 characters
        def fix_short_left_wildcard(match):
            suffix = match.group(1) if match.lastindex >= 1 else ""
            LOGGER.warning("Removing wildcard from short term (need 3+ chars after *)")
            return suffix

        query = re.sub(r'([*])([a-zA-Z0-9]{1,2})(?![a-zA-Z0-9])', fix_short_left_wildcard, query)

        # Remove wildcards after forbidden characters
        def remove_wildcard_after_special(match):
            special_char = match.group(1)
            return special_char

        query = re.sub(r'([/@#.,:;!])([*?$])', remove_wildcard_after_special, query)

        if query != original:
            LOGGER.info("Fixed wildcard issues: '%s' -> '%s'", original[:100], query[:100])

        return query
    
    def _fix_and_in_near_conflict(self, query: str) -> str:
        """
        Fix (A AND B) NEAR/N patterns by converting AND to OR.
        
        Web of Science doesn't support AND inside NEAR clauses.
        """
        try:
            result = query

            # Fix left groups: (... AND ...) NEAR/N
            def fix_left_group(m):
                group = m.group(1)
                space = m.group(2) if m.lastindex >= 2 else ''
                near = m.group(3) if m.lastindex >= 3 else m.group(2)
                fixed = re.sub(r'\bAND\b', 'OR', group, flags=re.IGNORECASE)
                return f"{fixed}{space}{near}"

            pattern_left = r'(\([^()]+\bAND\b[^()]+\))(\s*)(NEAR\s*/\s*\d+)'
            result = re.sub(pattern_left, fix_left_group, result, flags=re.IGNORECASE)

            # Fix right groups: NEAR/N (... AND ...)
            def fix_right_group(m):
                near = m.group(1)
                space = m.group(2) if m.lastindex >= 2 else ''
                group = m.group(3) if m.lastindex >= 3 else m.group(2)
                fixed = re.sub(r'\bAND\b', 'OR', group, flags=re.IGNORECASE)
                return f"{near}{space}{fixed}"

            pattern_right = r'(NEAR\s*/\s*\d+)(\s*)(\([^()]+\bAND\b[^()]+\))'
            result = re.sub(pattern_right, fix_right_group, result, flags=re.IGNORECASE)

            if result != query:
                LOGGER.info("Fixed AND-in-NEAR conflict: '%s' -> '%s'", query[:100], result[:100])

            return result
        except Exception as e:
            LOGGER.warning("Error fixing AND-in-NEAR: %s", e)
            return query
    
    def _validate_and_fix_query(self, query: str) -> str:
        """Apply all query validation and fixing."""
        query = self._validate_and_fix_wildcards(query)
        query = self._fix_and_in_near_conflict(query)
        return query
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Result Parsing
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _parse_title_from_record(self, record: dict[str, Any]) -> Optional[str]:
        """Extract title from WOS record."""
        titles_section = (
            record.get("static_data", {})
            .get("summary", {})
            .get("titles", {})
            .get("title", [])
        )
        
        if isinstance(titles_section, list):
            for title in titles_section:
                if isinstance(title, dict) and title.get("type") == "item":
                    return title.get("content")
        elif isinstance(titles_section, dict) and titles_section.get("type") == "item":
            return titles_section.get("content")
        
        return None
    
    def _parse_publication_year_from_record(self, record: dict[str, Any]) -> Optional[int]:
        """Extract publication year from WOS record."""
        year = (
            record.get("static_data", {})
            .get("summary", {})
            .get("pub_info", {})
            .get("pubyear")
        )
        return int(year) if year else None
    
    def _parse_citations_from_record(self, record: dict[str, Any]) -> Optional[int]:
        """Extract citation count from WOS record."""
        citations_section = (
            record.get("dynamic_data", {})
            .get("citation_related", {})
            .get("tc_list", {})
            .get("silo_tc", [])
        )
        
        if isinstance(citations_section, list):
            for citation in citations_section:
                if isinstance(citation, dict) and citation.get("coll_id") == "WOK":
                    count = citation.get("local_count")
                    return int(count) if count else None
        
        return None
    
    def _parse_abstract_from_record(self, record: dict[str, Any]) -> Optional[str]:
        """Extract abstract from WOS record."""
        fullrecord_metadata = record.get("static_data", {}).get("fullrecord_metadata", {})
        
        if "abstracts" not in fullrecord_metadata:
            return None
        
        abstract_paragraphs = (
            fullrecord_metadata.get("abstracts", {})
            .get("abstract", {})
            .get("abstract_text", {})
            .get("p", None)
        )
        
        if isinstance(abstract_paragraphs, list):
            return "\n".join(str(p) for p in abstract_paragraphs)
        elif abstract_paragraphs:
            return str(abstract_paragraphs)
        
        return None
    
    def _parse_authors_from_record(self, record: dict[str, Any]) -> list[str]:
        """Extract authors from WOS record."""
        names = (
            record.get("static_data", {})
            .get("summary", {})
            .get("names", {})
            .get("name", [])
        )
        
        authors = []
        if isinstance(names, list):
            for name in names:
                if isinstance(name, dict) and name.get("role") == "author":
                    full_name = name.get("full_name", name.get("display_name", ""))
                    if full_name:
                        authors.append(full_name)
        elif isinstance(names, dict) and names.get("role") == "author":
            full_name = names.get("full_name", names.get("display_name", ""))
            if full_name:
                authors.append(full_name)
        
        return authors[:10]  # Limit to first 10 authors
    
    def _parse_journal_from_record(self, record: dict[str, Any]) -> Optional[str]:
        """Extract journal name from WOS record."""
        source = (
            record.get("static_data", {})
            .get("summary", {})
            .get("publishers", {})
            .get("publisher", {})
            .get("names", {})
            .get("name", {})
        )
        
        if isinstance(source, dict):
            return source.get("full_name")
        
        return None
    
    def _parse_doi_from_record(self, record: dict[str, Any]) -> Optional[str]:
        """Extract DOI from WOS record."""
        identifiers = (
            record.get("static_data", {})
            .get("item", {})
            .get("ids", {})
        )
        return identifiers.get("doi") if isinstance(identifiers, dict) else None
    
    def _build_article_from_record(self, record: dict[str, Any]) -> Article:
        """Build an Article object from a WOS API record."""
        return Article(
            wos_number=record.get("UID", "UNKNOWN"),
            title=self._parse_title_from_record(record),
            publication_year=self._parse_publication_year_from_record(record),
            cited_by=self._parse_citations_from_record(record),
            abstract=self._parse_abstract_from_record(record),
            authors=self._parse_authors_from_record(record),
            journal=self._parse_journal_from_record(record),
            doi=self._parse_doi_from_record(record),
        )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # API Methods
    # ═══════════════════════════════════════════════════════════════════════════
    
    def npl_search(
        self,
        query: str,
        max_results: int = 10,
        from_year: Optional[int] = None,
        to_year: Optional[int] = None,
        sorting: Sorting = Sorting.CITATIONS,
    ) -> list[Article]:
        """
        Execute an NPL search.
        
        WOS QUERY SYNTAX:
        
        1. FIELD TAGS (TAG=value):
           • TS= Topic (title, abstract, keywords)
           • TI= Title only
           • AB= Abstract only
           • AU= Author
           • SO= Source/Journal
           • PY= Publication Year
           • DO= DOI
        
        2. BOOLEAN OPERATORS:
           • AND: both terms required
           • OR: either term
           • NOT: exclude term
           • NEAR/N: terms within N words (NO AND inside NEAR groups!)
        
        3. WILDCARDS:
           • * (asterisk): any characters (need 3+ chars before)
           • ? (question): single character
           • $ (dollar): zero or one character
        
        Examples:
            TS=(polymer degradation) AND TI=(UV fluorescence)
            TI=(machine learning) AND PY=(2020-2024)
        
        Args:
            query: WOS query syntax
            max_results: Maximum number of results to return
            from_year: Optional start year filter
            to_year: Optional end year filter
            sorting: Sort order (citations, relevance, or date)
        
        Returns:
            List of Article objects
        """
        if not self.config.is_configured():
            raise ValueError("WOS API not configured. Set WOS_API_KEY environment variable.")
        
        # Validate and fix the query
        query = self._validate_and_fix_query(query)
        
        # Determine sort field
        if sorting == Sorting.CITATIONS:
            sort_field = "TC+D"  # Times cited, descending
        elif sorting == Sorting.RELEVANCE:
            sort_field = "RS+D"  # Relevance score, descending
        else:
            sort_field = "PY+D"  # Publication year, descending
        
        # Build request parameters
        params: dict[str, Any] = {
            "databaseId": "WOS",
            "optionView": "FR",  # Full record
            "usrQuery": query,
            "sortField": sort_field,
            "count": max_results,
        }
        
        # Add date filter if provided
        if from_year or to_year:
            from datetime import datetime
            current_year = datetime.now().year
            # WOS database may not have current year data yet, use previous year as safe max
            safe_max_year = min(to_year or current_year, current_year - 1) if to_year else current_year - 1
            # WOS API requires YYYY-MM-DD format with + separator
            min_date = date(from_year or 1900, 1, 1).strftime("%Y-%m-%d")
            max_date = date(safe_max_year, 12, 31).strftime("%Y-%m-%d")
            params["publishTimeSpan"] = f"{min_date}+{max_date}"
        
        LOGGER.info("Executing WOS search: %s", query[:100])
        
        try:
            response = self._session.get(
                f"{self.config.endpoint}/",
                headers=self._headers,
                params=params,
                timeout=60,
            )
            
            if response.status_code != 200:
                LOGGER.error("WOS API error: %s", response.text[:500])
                raise RuntimeError(f"WOS API error: {response.status_code}")
            
            data = response.json()
            records_section = data.get("Data", {}).get("Records", {}).get("records", {})
            
            articles = []
            if records_section:
                records = records_section.get("REC", [])
                # Handle single result case
                if isinstance(records, dict):
                    records = [records]
                
                for record in records:
                    articles.append(self._build_article_from_record(record))
            
            # Log remaining quota
            remaining_quota = response.headers.get("X-REC-AmtPerYear-Remaining", "unknown")
            LOGGER.info("WOS search returned %d results. Remaining quota: %s", len(articles), remaining_quota)
            
            return articles
            
        except requests.RequestException as e:
            LOGGER.error("WOS search failed: %s", e)
            raise
    
    def get_article_info(self, wos_number: str) -> Optional[Article]:
        """
        Retrieve detailed information for a specific article.
        
        Args:
            wos_number: WOS article ID (e.g., 'WOS:000123456789')
        
        Returns:
            Article object or None if not found
        """
        if not self.config.is_configured():
            raise ValueError("WOS API not configured. Set WOS_API_KEY environment variable.")
        
        try:
            response = self._session.get(
                f"{self.config.endpoint}/id/{wos_number}",
                headers=self._headers,
                params={
                    "databaseId": "WOS",
                    "optionView": "FR",
                },
                timeout=30,
            )
            
            if response.status_code != 200:
                LOGGER.error("WOS API error: %s", response.text[:500])
                return None
            
            data = response.json()
            records_section = data.get("Data", {}).get("Records", {}).get("records", {})
            
            if not records_section:
                return None
            
            records = records_section.get("REC", [])
            if isinstance(records, dict):
                records = [records]
            
            if records:
                return self._build_article_from_record(records[0])
            
            return None
            
        except requests.RequestException as e:
            LOGGER.error("Error retrieving article info: %s", e)
            return None


# ═══════════════════════════════════════════════════════════════════════════════
# LangChain Tool Functions
# ═══════════════════════════════════════════════════════════════════════════════

@tool
def npl_search_tool(
    query: str,
    max_results: int = 10,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
) -> list[dict]:
    """
    Search for scientific articles (non-patent literature) using Web of Science.
    
    Use this tool to find relevant academic papers, journal articles, and conference proceedings.
    
    QUERY SYNTAX:
    - Field tags: TS=(topic), TI=(title), AB=(abstract), AU=(author), PY=(year)
    - Boolean: AND, OR, NOT
    - Proximity: NEAR/N (e.g., polymer NEAR/5 degradation)
    - Wildcards: * (any chars, need 3+ before), ? (single char)
    
    Example queries:
    - TS=(polymer degradation) AND TI=(UV fluorescence)
    - TI=(machine learning) AND PY=(2020-2024)
    - TS=(soft robotic gripper) AND AU=(Smith)
    
    IMPORTANT: Do NOT use (A AND B) inside NEAR groups - use (A OR B) instead.
    
    Args:
        query: WOS query syntax string
        max_results: Maximum number of articles to return (default: 10)
        from_year: Filter by start publication year (optional)
        to_year: Filter by end publication year (optional)
    
    Returns:
        List of article dictionaries with wos_number, title, abstract, etc.
    """
    client = WOSClient()
    articles = client.npl_search(query, max_results, from_year, to_year)
    return [a.to_dict() for a in articles]


@tool
def get_article_by_wos_number(wos_number: str) -> Optional[dict]:
    """
    Retrieve detailed article information by WOS number.
    
    Use this tool to get full details of a specific article when you know its WOS ID.
    
    Args:
        wos_number: WOS article ID (e.g., 'WOS:000123456789')
    
    Returns:
        Article dictionary with full details, or None if not found
    """
    client = WOSClient()
    article = client.get_article_info(wos_number)
    return article.to_dict() if article else None


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience Functions (non-tool versions for internal use)
# ═══════════════════════════════════════════════════════════════════════════════

def npl_search(
    query: str,
    max_results: int = 10,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
) -> list[Article]:
    """
    Search for NPL articles (non-tool version).
    
    Args:
        query: WOS query syntax
        max_results: Maximum results
        from_year: Optional start year
        to_year: Optional end year
    
    Returns:
        List of Article objects
    """
    client = WOSClient()
    return client.npl_search(query, max_results, from_year, to_year)


def get_article(wos_number: str) -> Optional[Article]:
    """
    Get article by WOS number (non-tool version).
    
    Args:
        wos_number: WOS article ID
    
    Returns:
        Article object or None
    """
    client = WOSClient()
    return client.get_article_info(wos_number)


def convert_articles_to_search_results(articles: list[Article]) -> list[SearchResult]:
    """Convert Article objects to generic SearchResult objects."""
    return [
        SearchResult(
            ref_id=a.wos_number,
            ref_type="npl",
            title=a.title or "",
            abstract=a.abstract or "",
            relevance_score=0.0,
            source="wos",
            metadata={
                "publication_year": a.publication_year,
                "cited_by": a.cited_by,
                "journal": a.journal,
                "authors": a.authors,
                "doi": a.doi,
            }
        )
        for a in articles
    ]
