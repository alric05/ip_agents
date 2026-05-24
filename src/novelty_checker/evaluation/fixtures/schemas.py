"""
Pydantic models / schemas for each ground-truth fixture file produced by conversion.py:

  • metadata.yaml          → CaseMetadata
  • gt_features.json       → GTFeatures / FeatureEntry
  • gt_references.json     → GTReferences / ReferenceEntry / FeatureCoverageEntry
  • gt_verdict.json        → GTVerdict / OverallAssessment / PerFeatureRiskEntry
  • gt_search_strategy.json → GTSearchStrategy / QueryEntry / VocabularyEntry / ClassificationCodeEntry
"""

from __future__ import annotations

import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# metadata.yaml schema
# ---------------------------------------------------------------------------

class CaseMetadata(BaseModel):
    """Schema for metadata.yaml.

    Merges Part A invention-disclosure fields, Part B case-metadata fields, Part B Difficulty fields,
    and the time-breakdown table.

    extra="allow" lets any additional Part-B case-metadata keys (e.g. custom
    SME fields) pass through without breaking validation.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    # --- Part A fields ---
    case_id: str
    domain: Optional[str] = None
    difficulty: Optional[str] = Field(
        None, description="Expected: 'Easy', 'Medium', or 'Hard'."
    )
    difficulty_score: Optional[int] = Field(None, description="Numeric difficulty score (1–5, SME perceived).")
    difficulty_notes: Optional[str] = Field(None, description="SME free-text notes on difficulty.")
    source: Optional[str] = None
    language: Optional[str] = "English"
    created_by: Optional[str] = None
    created_date: Optional[datetime.date] = None

    # --- Part B Case Metadata fields (aliases match the Excel row labels) ---
    collection_date: Optional[datetime.date] = Field(None, alias="Collection Date")
    total_time_minutes: Optional[float] = Field(None, alias="Total Time (minutes)")

    # --- Part B Time Breakdown table ---
    time_breakdown: Optional[dict[str, Optional[float]]] = None

    def to_serializable(self) -> dict:
        """Return a plain dict ready for yaml.dump, using original key names."""
        data = self.model_dump(by_alias=True)
        # Serialize date fields as ISO strings for YAML compatibility
        for key in ("created_date", "Collection Date"):
            if isinstance(data.get(key), datetime.date):
                data[key] = data[key].isoformat()
        return data

# ---------------------------------------------------------------------------
# gt_features.json schema
# ---------------------------------------------------------------------------

class FeatureEntry(BaseModel):
    """A single expected key feature.

    - ``name`` and ``description`` are both kept when the Excel sheet provides
      both; if only one column exists, the other is None.
    - ``keywords`` and ``related_cpc_ipc`` are always lists (may be empty).
    - ``core`` is expected to be 'Y' or 'N'.
    """

    model_config = ConfigDict(populate_by_name=True)

    feature_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = Field(None, description="E.g. 'Functional', 'Structural', 'Material'.")
    core: Optional[str] = Field(None, description="'Y' if this is a core feature, 'N' otherwise.")
    keywords: list[list[str]] = Field(default_factory=list)
    related_cpc_ipc: list[str]= Field(default_factory=list)


class GTFeatures(BaseModel):
    """Schema for gt_features.json.

    Example structure::

        {
          "case_id": "TST-Mechanical-1120",
          "total_features": 6,
          "core_feature_count": 3,
          "features": [
            {
              "feature_id": "F1",
              "name": "...",
              "description": "...",
              "type": "Functional",
              "core": "Y",
              "keywords": ["heat", "transfer"],
              "related_cpc_ipc": ["F28D"]
            },
            ...
          ]
        }
    """

    case_id: str
    total_features: int
    core_feature_count: int
    features: list[FeatureEntry]

    def to_serializable(self) -> dict:
        """Return a plain dict ready for json.dump."""
        return self.model_dump()


# ---------------------------------------------------------------------------
# gt_references.json schema
# ---------------------------------------------------------------------------

class FeatureCoverageEntry(BaseModel):
    """Coverage verdict and SME notes for a single feature within a reference.

    Example JSON::

        "F1": { "verdict": "Y",  "notes": "Claim 3 discloses the full mechanism." }
        "F2": { "verdict": "Y1", "notes": "Partially covered in paragraph [0042]." }
    """

    verdict: Optional[Literal["Y", "Y1", "N"]] = Field(
        None,
        description="Y = fully disclosed, Y1 = partially disclosed, N = not present."
    )
    notes: Optional[str] = Field(
        None,
        description="Pin-cite or brief justification for the verdict."
    )


class ReferenceEntry(BaseModel):
    """A single prior-art reference assessed by the SME."""

    model_config = ConfigDict(populate_by_name=True)

    ref_id: str = Field(description="Sequential reference identifier, e.g. 'R1', 'R2'.")
    publication_number: Optional[str] = Field(
        None,
        description="Original reference ID as it appears in the form (patent number, DOI, WOS ID, etc.)."
    )
    title_english: Optional[str] = Field(None, description="English title of the reference.")
    title_chinese: Optional[str] = Field(None, description="Chinese title of the reference, if present.")
    source_db: Optional[str] = Field(
        None,
        description="Source database, e.g. 'Innography', 'WOS', 'NGSP', 'Other'."
    )
    discovery_method: Optional[Literal[
        "keyword",
        "semantic",
        "citation",
        "manual",
    ]] = Field(None, description="How the reference was first discovered.")
    triage: Optional[Literal["A", "B", "C"]] = Field(
        None,
        description="Triage label: A = high relevance, B = medium, C = low."
    )
    priority_date: Optional[str] = Field(
        None,
        description="Earliest priority date in YYYY-MM-DD format (patents only)."
    )
    blocking_potential: Optional[str] = Field(
        None,
        description="SME assessment of how likely this reference blocks novelty."
    )
    feature_coverage: Optional[dict[str, FeatureCoverageEntry]] = Field(
        default_factory=dict,
        description=(
            "Per-feature coverage mapping. Keys are feature IDs (F1, F2, …). "
            "Each value contains a verdict (Y / Y1 / N) and optional notes."
        )
    )
    pin_cites: Optional[str] = Field(
        None,
        description="Specific claims, paragraphs, figures, or sections that are relevant. Each inner list groups items from a single line; commas within a line separate individual entries."
    )
    sme_notes: Optional[str] = Field(
        None,
        description="Free-text notes from the SME about this reference."
    )


class GTReferences(BaseModel):
    """Schema for gt_references.json.

    Example structure::

        {
          "case_id": "TST-Mechanical-1120",
          "total_references": 3,
          "references": [
            {
              "ref_id": "R1",
              "publication_number": "US10234567B2",
              "title": "...",
              "source_db": "Innography",
              "discovery_method": "keyword",
              "triage": "A",
              "priority_date": "2018-06-01",
              "blocking_potential": "High",
              "feature_coverage": {
                "F1": { "verdict": "Y",  "notes": "Claim 1." },
                "F2": { "verdict": "Y1", "notes": "Paragraph [0042]." }
              },
              "pin_cites": "Claims 1-3, Fig. 4",
              "sme_notes": "Strong anticipatory reference."
            }
          ]
        }
    """

    case_id: str
    total_references: int
    references: list[ReferenceEntry]

    def to_serializable(self) -> dict:
        """Return a plain dict ready for json.dump."""
        return self.model_dump()

# ---------------------------------------------------------------------------
# gt_verdict.json schema
# ---------------------------------------------------------------------------

class OverallAssessment(BaseModel):
    verdict: Optional[str] = Field(
        None,
        description="Overall novelty verdict, e.g. 'novel', 'not novel', 'partially novel'."
    )
    confidence: Optional[str] = Field(
        None,
        description="SME confidence level, e.g. 'High', 'Medium', 'Low'."
    )
    where_novelty_resides: Optional[str] = Field(
        None,
        description="Free-text description of where, if anywhere, novelty resides."
    )
    verdict_reasoning: Optional[str] = Field(
        None,
        description="SME reasoning behind the overall verdict."
    )


class PerFeatureRiskEntry(BaseModel):
    feature_id: str = Field(description="Feature identifier, e.g. 'F1', 'F2'.")
    risk_level: Optional[str] = Field(
        None,
        description="Risk level for this feature, e.g. 'High', 'Medium', 'Low'."
    )
    closest_reference: list[str] = Field(
        default_factory=list,
        description="List of publication numbers most closely anticipating this feature."
    )
    gap_description: Optional[str] = Field(
        None,
        description="Description of the gap between the feature and the closest reference(s)."
    )


class GTVerdict(BaseModel):
    """Schema for gt_verdict.json."""

    model_config = ConfigDict(populate_by_name=True)

    case_id: str
    overall: OverallAssessment
    per_feature_risk: list[PerFeatureRiskEntry]

    def to_serializable(self) -> dict:
        return self.model_dump()

# ---------------------------------------------------------------------------
# gt_search_strategy.json schema
# ---------------------------------------------------------------------------

class QueryEntry(BaseModel):
    query_id: str = Field(description="Sequential query identifier, e.g. 'Q1', 'Q2'.")
    database: Optional[str] = Field(None, description="Database the query was run in, e.g. 'Orbit', 'Innography'.")
    query_text: Optional[str] = Field(None, description="Full query string as entered.")
    results_found: Optional[int] = Field(None, description="Number of results returned by the database.")


class VocabularyEntry(BaseModel):
    id: str = Field(description="Sequential vocabulary identifier, e.g. 'V1', 'V2'.")
    original_term: Optional[str] = Field(None, description="The base concept term used in the search.")
    discovered_synonyms: list[str] = Field(default_factory=list, description="Synonyms or alternate expressions found during search.")
    how_discovered: Optional[str] = Field(None, description="How the synonym was found, e.g. 'keyword', 'semantic'.")


class ClassificationCodeEntry(BaseModel):
    code: Optional[str] = Field(None, description="CPC or IPC classification code, e.g. 'B63B 35'.")
    system: Optional[str] = Field(None, description="Classification system, e.g. 'CPC', 'IPC', 'IPC/CPC'.")
    reason: Optional[str] = Field(None, description="Why this code is relevant to the search.")


class GTSearchStrategy(BaseModel):
    """Schema for gt_search_strategy.json."""

    model_config = ConfigDict(populate_by_name=True)

    case_id: str
    databases_used: list[str] = Field(
        default_factory=list,
        description="List of database names that were actively used (Used? == 'Y')."
    )
    queries_executed: list[QueryEntry] = Field(default_factory=list)
    vocabulary_discovered: list[VocabularyEntry] = Field(default_factory=list)
    expected_cpc_ipc_codes: list[ClassificationCodeEntry] = Field(default_factory=list)
    overall_strategy_narrative: Optional[str] = Field(
        None,
        description="Free-text description of the overall search approach."
    )

    def to_serializable(self) -> dict:
        return self.model_dump()