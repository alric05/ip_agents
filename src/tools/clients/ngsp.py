"""
NGSP Semantic Search API Client.

This module provides a complete, self-contained implementation of the Clarivate
NGSP API for semantic (natural language) patent searches.

Unlike keyword search, NGSP uses AI/ML to find patents based on conceptual
similarity rather than exact keyword matches.

Configuration (via environment variables):
    CLARIVATE_NGSP_API_KEY: NGSP API key (optional, uses internal endpoint)
    NGSP_TOKEN: Bearer token for authentication (optional)
"""

import json
import logging
from dataclasses import dataclass
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
from src.tools.clients.schemas import Patent, SearchResult

LOGGER = logging.getLogger("langgraph_agent.tools.ngsp")

# Default NGSP endpoint (internal Clarivate endpoint)
NGSP_DEFAULT_ENDPOINT = "https://ngsp-ai-search-dev-snapshot-us-west-2.dev.ds.aws.clarivate.net"


def _build_retry_session(retries: int = 3, backoff_factor: float = 0.5) -> requests.Session:
    """Create a session with retry logic."""
    session = requests.Session()
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST", "PUT", "PATCH", "DELETE"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


@dataclass
class NGSPConfig:
    """Configuration for NGSP API."""
    api_key: Optional[str]
    endpoint: str
    bearer_token: Optional[str]
    timeout_seconds: int = 30
    
    @classmethod
    def from_settings(cls) -> "NGSPConfig":
        """Create config from settings."""
        settings = get_settings()
        import os
        return cls(
            api_key=settings.clarivate_ngsp_api_key,
            endpoint=os.environ.get("NGSP_ENDPOINT", NGSP_DEFAULT_ENDPOINT),
            bearer_token=os.environ.get("NGSP_TOKEN"),
        )
    
    def is_configured(self) -> bool:
        """Check if API is accessible (internal endpoint doesn't require key)."""
        # NGSP internal endpoint doesn't require API key
        return True


class NGSPClient:
    """
    Client for NGSP semantic search API.
    
    NGSP provides AI-powered semantic patent search that understands
    the meaning and context of queries, not just keywords.
    """
    
    def __init__(self, config: Optional[NGSPConfig] = None):
        """
        Initialize the client.
        
        Args:
            config: Optional configuration. If not provided, loads from settings.
        """
        self.config = config or NGSPConfig.from_settings()
        self._session = _build_retry_session()
    
    def _build_headers(self) -> dict[str, str]:
        """Build request headers."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        
        if self.config.bearer_token:
            headers["Authorization"] = f"Bearer {self.config.bearer_token}"
        
        if self.config.api_key:
            headers["X-ApiKey"] = self.config.api_key
        
        return headers
    
    def _build_patent_from_hit(self, hit: dict) -> Patent:
        """Build a Patent object from an NGSP search hit."""
        publication_num = hit.get('id', '').split('_')[0]
        
        # Extract content from snippets
        snippets = hit.get('snippets', [])
        abstract = ""
        title = ""
        claims = ""
        
        for snippet in snippets:
            src = snippet.get('src', '')
            text = snippet.get('text', '')
            
            if src == 'abstract':
                abstract = text
            elif src == 'title':
                title = text
            elif src == 'claims':
                claims = text
        
        return Patent(
            publication_number=publication_num,
            title=title or None,
            abstract=abstract or None,
            claims=claims or None,
            relevance_score=hit.get('score', 0.0),
        )
    
    def semantic_search(
        self,
        query: str,
        max_results: int = 20,
    ) -> list[Patent]:
        """
        Execute a semantic patent search.
        
        Unlike keyword search, semantic search understands:
        - Conceptual meaning (not just exact words)
        - Synonyms and related terms
        - Technical context
        - Invention descriptions in natural language
        
        BEST PRACTICES:
        - Use plain English descriptions of the invention
        - Include technical details and use cases
        - Describe the problem being solved
        - Mention key components and how they interact
        
        Example queries:
        - "UV fluorescence detection for polymer degradation in recycled materials"
        - "Robotic gripper using soft materials for delicate fruit handling"
        - "Machine learning system for predicting battery failure in electric vehicles"
        
        Args:
            query: Natural language description (NO Boolean operators!)
            max_results: Maximum number of results to return
        
        Returns:
            List of Patent objects with relevance scores
        """
        if not self.config.is_configured():
            raise ValueError("NGSP API not configured.")
        
        # Normalize whitespace (handle non-breaking spaces from copy/paste)
        clean_query = query.replace("\u00A0", " ").strip()
        
        url = f"{self.config.endpoint.rstrip('/')}/api/search"
        headers = self._build_headers()
        payload = {"q": clean_query}
        
        LOGGER.info("Executing NGSP semantic search: %s", clean_query[:100])
        
        try:
            response = self._session.post(
                url,
                data=json.dumps(payload, ensure_ascii=False),
                headers=headers,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            
            # Parse response
            try:
                data = response.json()
            except json.JSONDecodeError:
                raise RuntimeError(
                    f"Expected JSON but got: {response.headers.get('Content-Type')} | "
                    f"Body: {response.text[:500]}"
                )
            
            # Extract patents from hits
            hits = data.get('hits', [])
            patents = [self._build_patent_from_hit(hit) for hit in hits[:max_results]]
            
            LOGGER.info("NGSP search returned %d results", len(patents))
            return patents
            
        except requests.RequestException as e:
            LOGGER.error("NGSP search failed: %s", e)
            raise


# ═══════════════════════════════════════════════════════════════════════════════
# LangChain Tool Functions
# ═══════════════════════════════════════════════════════════════════════════════

@tool
def semantic_patent_search_tool(query: str, max_results: int = 20) -> list[dict]:
    """
    Search for patents using semantic/AI-powered search.
    
    Use this tool when you want to find patents based on conceptual meaning
    rather than exact keywords. Good for:
    - Natural language invention descriptions
    - Finding conceptually similar patents
    - Exploring related technologies
    
    IMPORTANT: Use plain English, NO Boolean operators (AND, OR, NOT).
    
    Example queries:
    - "UV fluorescence detection for polymer degradation in recycled materials"
    - "Robotic gripper using soft materials for delicate fruit handling"
    - "Machine learning system for predicting battery failure"
    
    Args:
        query: Natural language description of the technology/invention
        max_results: Maximum number of patents to return (default: 20)
    
    Returns:
        List of patent dictionaries with relevance scores
    """
    client = NGSPClient()
    patents = client.semantic_search(query, max_results)
    return [p.to_dict() for p in patents]


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience Functions (non-tool versions for internal use)
# ═══════════════════════════════════════════════════════════════════════════════

def semantic_search(query: str, max_results: int = 20) -> list[Patent]:
    """
    Execute semantic patent search (non-tool version).
    
    Args:
        query: Natural language query
        max_results: Maximum results
    
    Returns:
        List of Patent objects with relevance scores
    """
    client = NGSPClient()
    return client.semantic_search(query, max_results)


def convert_ngsp_to_search_results(patents: list[Patent]) -> list[SearchResult]:
    """Convert NGSP Patent objects to generic SearchResult objects."""
    return [
        SearchResult(
            ref_id=p.publication_number,
            ref_type="patent",
            title=p.title or "",
            abstract=p.abstract or "",
            relevance_score=p.relevance_score or 0.0,
            source="ngsp",
            metadata={
                "claims": p.claims,
            }
        )
        for p in patents
    ]
