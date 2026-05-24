"""
Data Schemas for LangGraph Agent Tools.

Self-contained schema definitions for search results.
These are local to the langgraph_agent module to avoid external dependencies.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


@dataclass
class Patent:
    """Patent search result."""
    publication_number: str
    title: Optional[str] = None
    abstract: Optional[str] = None
    claims: Optional[str] = None
    dwpi_title: Optional[str] = None
    dwpi_abstract_novelty: Optional[str] = None
    dwpi_abstract_advantage: Optional[str] = None
    dwpi_abstract_use: Optional[str] = None
    dwpi_abstract_detailed_description: Optional[str] = None
    priority_date: Optional[str] = None
    assignee: Optional[str] = None
    inventors: list[str] = field(default_factory=list)
    relevance_score: Optional[float] = None
    
    def __str__(self) -> str:
        """Format patent for display."""
        parts = [
            "\n#############",
            f"Patent number: ```{self.publication_number}```"
        ]
        if self.title:
            parts.append(f"Title: ```{self.title}```")
        if self.dwpi_title:
            parts.append(f"DWPI Title: ```{self.dwpi_title}```")
        if self.abstract:
            parts.append(f"Abstract: ```{self.abstract}```")
        if self.dwpi_abstract_novelty:
            parts.append(f"DWPI Novelty: ```{self.dwpi_abstract_novelty}```")
        if self.dwpi_abstract_advantage:
            parts.append(f"DWPI Advantage: ```{self.dwpi_abstract_advantage}```")
        if self.dwpi_abstract_use:
            parts.append(f"DWPI Use: ```{self.dwpi_abstract_use}```")
        if self.claims:
            parts.append(f"Claims: ```{self.claims}```")
        if self.dwpi_abstract_detailed_description:
            parts.append(f"DWPI Description: ```{self.dwpi_abstract_detailed_description}```")
        parts.append("#############\n")
        return "\n".join(parts)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "publication_number": self.publication_number,
            "title": self.title,
            "abstract": self.abstract,
            "claims": self.claims,
            "dwpi_title": self.dwpi_title,
            "dwpi_abstract_novelty": self.dwpi_abstract_novelty,
            "dwpi_abstract_advantage": self.dwpi_abstract_advantage,
            "dwpi_abstract_use": self.dwpi_abstract_use,
            "dwpi_abstract_detailed_description": self.dwpi_abstract_detailed_description,
            "priority_date": self.priority_date,
            "assignee": self.assignee,
            "inventors": self.inventors,
            "relevance_score": self.relevance_score,
        }


@dataclass
class Article:
    """NPL (Non-Patent Literature) search result from Web of Science."""
    wos_number: str
    title: Optional[str] = None
    publication_year: Optional[int] = None
    cited_by: Optional[int] = None
    abstract: Optional[str] = None
    authors: list[str] = field(default_factory=list)
    journal: Optional[str] = None
    doi: Optional[str] = None
    
    def __str__(self) -> str:
        """Format article for display."""
        parts = [
            "\n#############",
            f"Article number: ```{self.wos_number}```"
        ]
        if self.title:
            parts.append(f"Title: ```{self.title}```")
        if self.publication_year:
            parts.append(f"Publication year: ```{self.publication_year}```")
        if self.cited_by is not None:
            parts.append(f"Cited by: ```{self.cited_by}```")
        if self.journal:
            parts.append(f"Journal: ```{self.journal}```")
        if self.authors:
            parts.append(f"Authors: ```{', '.join(self.authors[:5])}```")
        if self.abstract:
            parts.append(f"Abstract: ```{self.abstract}```")
        parts.append("#############\n")
        return "\n".join(parts)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "wos_number": self.wos_number,
            "title": self.title,
            "publication_year": self.publication_year,
            "cited_by": self.cited_by,
            "abstract": self.abstract,
            "authors": self.authors,
            "journal": self.journal,
            "doi": self.doi,
        }


class Sorting(str, Enum):
    """Sorting options for WOS search."""
    CITATIONS = "citations"
    RELEVANCE = "relevance"
    DATE = "date"


@dataclass  
class DateBoundaries:
    """Date range for search filtering."""
    from_year: Optional[int] = None
    to_year: Optional[int] = None
    min_date: Optional[str] = None  # Format: YYYY-MM-DD
    max_date: Optional[str] = None  # Format: YYYY-MM-DD
    
    @property
    def publish_time_span_str(self) -> str:
        """Get date range string for WOS API (format: YYYY-MM-DD+YYYY-MM-DD)."""
        if self.min_date and self.max_date:
            return f"{self.min_date}+{self.max_date}"
        elif self.from_year and self.to_year:
            return f"{self.from_year}-01-01+{self.to_year}-12-31"
        return ""


@dataclass
class SearchResult:
    """Generic search result container."""
    ref_id: str
    ref_type: str  # "patent" or "npl"
    title: str
    abstract: str = ""
    relevance_score: float = 0.0
    source: str = ""  # "innography", "wos", "ngsp"
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "ref_id": self.ref_id,
            "ref_type": self.ref_type,
            "title": self.title,
            "abstract": self.abstract,
            "relevance_score": self.relevance_score,
            "source": self.source,
            "metadata": self.metadata,
        }
