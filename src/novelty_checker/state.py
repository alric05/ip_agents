"""State definitions for the Novelty Checker Deep Agent system.

This module defines the shared state that flows through the agent,
following the deepagents state management patterns with middleware support.
"""

from typing import Annotated, Literal, NotRequired, TypedDict
from langgraph.graph.message import add_messages, AnyMessage


# =============================================================================
# Middleware State Types
# =============================================================================

class Todo(TypedDict):
    """A single todo item for planning."""
    
    content: str
    """Description of the task."""
    
    status: Literal["pending", "in_progress", "completed"]
    """Current status of the todo."""
    
    activeForm: NotRequired[str]
    """Optional: Current step being worked on (for in_progress items)."""


class SkillMetadata(TypedDict):
    """Metadata about an available skill."""
    
    name: str
    """Unique skill name."""
    
    description: str
    """Short description of when to use this skill."""
    
    path: str
    """Path to the SKILL.md file."""


# =============================================================================
# Feature & Search Types (from ARCHITECTURE.md)
# =============================================================================

class Feature(TypedDict):
    """A feature extracted from the invention for search."""
    
    id: str
    """Feature identifier (F1, F2, etc.)."""
    
    name: str
    """Short name of the feature."""
    
    description: str
    """Detailed description of the feature."""
    
    keywords: list[str]
    """Search keywords for this feature."""
    
    is_core: bool
    """Whether this is a core feature (must have STRONG coverage)."""
    
    priority: Literal["P1", "P2", "P3"]
    """Priority level for search."""


class Reference(TypedDict):
    """A reference (patent or NPL) found during search."""
    
    ref_id: str
    """Unique identifier (patent number, DOI, etc.).
    
    For patents: Publication number (e.g., US10234567B2, JP2007171504A)
    For NPL: WOS ID (e.g., WOS:000299510600010) or DOI
    """
    
    title: str
    """Title of the reference."""
    
    source: Literal["innography", "wos", "ngsp"]
    """Source database."""
    
    ref_type: NotRequired[Literal["patent", "npl"]]
    """Type of reference: patent or non-patent literature."""
    
    ref_type_display: NotRequired[Literal["Patent", "Research Paper"]]
    """Human-readable type for Feature Matrix display."""
    
    triage_label: NotRequired[Literal["A", "B", "C"]]
    """Triage label: A=High, B=Medium, C=Low relevance."""
    
    feature_coverage: NotRequired[dict[str, Literal["Y", "Y1", "N"]]]
    """Per-feature coverage mapping for Feature Matrix.
    
    Keys are feature IDs (F1, F2, etc.)
    Values are: Y (disclosed), Y1 (partial), N (absent)
    """
    
    feature_mapping: NotRequired[dict[str, Literal["Y", "Y1", "N"]]]
    """Mapping of features disclosed: Y=yes, Y1=partial, N=no.
    
    DEPRECATED: Use feature_coverage instead.
    """
    
    priority_date: NotRequired[str]
    """Earliest priority date for patents (YYYY-MM-DD format)."""
    
    pub_year: NotRequired[str]
    """Publication year for NPL (YYYY format)."""
    
    jurisdiction: NotRequired[str]
    """Jurisdiction/venue: country code for patents, journal name for NPL."""
    
    aspects_covered: NotRequired[str]
    """Which aspects of the invention this reference covers."""
    
    comments: NotRequired[str]
    """Additional comments about this reference."""
    
    pin_cites: NotRequired[str]
    """Pin-cites: claim numbers, paragraphs, figures, sections."""
    
    x_category: NotRequired[bool]
    """True if ALL core features are Y (anticipatory reference)."""
    
    abstract: NotRequired[str]
    """Abstract or summary of the reference."""
    
    url: NotRequired[str]
    """URL to the reference."""
    
    discovery_method: NotRequired[Literal[
        "keyword",            # Found via patent_keyword_search / batch_patent_search
        "semantic",           # Found via semantic_patent_search / batch_semantic_search
        "npl",                # Found via npl_search / batch_npl_search
        "citation_forward",   # Found as a forward citation of an A-ref
        "citation_backward",  # Found as a backward citation of an A-ref
    ]]
    """How this reference was discovered."""
    
    source_patent: NotRequired[str]
    """The A-ref publication number whose citations led to discovering this reference.
    Only set when discovery_method is citation_forward or citation_backward."""


class CoverageStatus(TypedDict):
    """Coverage status for a feature."""
    
    feature_id: str
    """Feature identifier."""
    
    level: Literal["none", "weak", "moderate", "strong", "saturated"]
    """Coverage level achieved."""
    
    a_refs: int
    """Number of A-label references."""
    
    b_refs: int
    """Number of B-label references."""
    
    c_refs: int
    """Number of C-label references."""


# =============================================================================
# Findings Persistence Types (Phase 2 - Structured Findings Schema)
# =============================================================================

class VocabularyTerm(TypedDict):
    """A vocabulary term discovered during semantic search."""
    
    term: str
    """The discovered term (e.g., "photoluminescence")."""
    
    source_ref: NotRequired[str]
    """Reference where this term was found (e.g., US1234567)."""
    
    relevance: NotRequired[str]
    """How this term relates to the invention (e.g., "Synonym for fluorescence")."""
    
    discovered_in_round: NotRequired[int]
    """Which research round discovered this term."""


class RoundFindings(TypedDict):
    """Findings from a single research round.
    
    This structure captures all findings from one iteration of the
    research loop, enabling persistence and recall across turns.
    """
    
    round_number: int
    """Research round number (1, 2, 3, ...)."""
    
    timestamp: NotRequired[str]
    """ISO 8601 timestamp when round completed."""
    
    # Search results by source
    patent_findings: NotRequired[list[Reference]]
    """References found by patent-researcher (Innography)."""
    
    npl_findings: NotRequired[list[Reference]]
    """References found by npl-researcher (Web of Science)."""
    
    semantic_findings: NotRequired[list[Reference]]
    """References found by semantic-researcher (NGSP)."""
    
    # Coverage snapshot
    coverage_snapshot: NotRequired[list[CoverageStatus]]
    """Coverage status per feature after this round."""
    
    overall_coverage_pct: NotRequired[float]
    """Overall coverage percentage (0-100) after this round."""
    
    # Vocabulary discovery (from semantic search)
    vocabulary_discovered: NotRequired[list[VocabularyTerm]]
    """New vocabulary terms discovered in this round."""
    
    # Metrics for diminishing returns detection
    new_refs_count: NotRequired[int]
    """Number of NEW (non-duplicate) references found this round."""
    
    duplicate_refs_count: NotRequired[int]
    """Number of duplicate references skipped this round."""
    
    # Gap analysis
    gap_features: NotRequired[list[str]]
    """Feature IDs that still have coverage gaps after this round."""
    
    recommended_queries: NotRequired[dict[str, str]]
    """Recommended gap-filling queries for next round.
    
    Keys: "patent", "npl", "semantic"
    Values: Suggested query strings
    """


class FindingsAccumulator(TypedDict):
    """Accumulated findings across all research rounds.
    
    This is the master structure for persisting all research findings.
    It enables the agent to recall prior work even after context truncation.
    
    Persisted to: /findings_accumulator.json
    """
    
    # Invention context
    scope_markdown: NotRequired[str]
    """Confirmed scope from Gate 1."""
    
    features: NotRequired[list[Feature]]
    """Confirmed features from Gate 2."""
    
    # Research rounds
    rounds: list[RoundFindings]
    """Findings from each completed research round."""
    
    current_round: NotRequired[int]
    """Current round number (for tracking progress)."""
    
    # Master reference list (deduplicated)
    all_references: NotRequired[list[Reference]]
    """Deduplicated master list of ALL references found."""
    
    # Aggregated vocabulary
    all_vocabulary: NotRequired[list[VocabularyTerm]]
    """All vocabulary terms discovered across all rounds."""
    
    # Final coverage status
    final_coverage: NotRequired[list[CoverageStatus]]
    """Latest coverage status per feature."""
    
    final_coverage_pct: NotRequired[float]
    """Final overall coverage percentage."""
    
    # Stop signals
    stop_reason: NotRequired[Literal[
        "coverage_met",
        "max_iterations",
        "diminishing_returns",
        "query_exhaustion",
        "feature_saturation",
        "user_stopped"
    ]]
    """Why the research loop stopped."""
    
    # Metadata
    started_at: NotRequired[str]
    """ISO 8601 timestamp when research started."""
    
    completed_at: NotRequired[str]
    """ISO 8601 timestamp when research completed."""


class FeatureMatrixRow(TypedDict):
    """Single row in the Feature Matrix (Section 4 of final report).
    
    Each row represents ONE unique reference (patent or NPL) with its
    coverage mapped to each feature. The Publication Number is the
    PRIMARY IDENTIFIER linking to the Patents/NPL Record View.
    
    ⚠️ CRITICAL: Use publication numbers, NOT query IDs!
    ✅ Correct: US10234567B2, JP2007171504A, WOS:000299510600010
    ❌ Wrong: K1.1, NQP-1.2, S1.1 (these are query IDs)
    """
    
    publication_number: str
    """Primary identifier: patent publication number or NPL ID.
    
    Patents: US10234567B2, JP2007171504A, CN106054342A, EP1234567A1
    NPL: WOS:000299510600010, DOI:10.1021/acs.analchem.2c01234
    """
    
    ref_type: Literal["Patent", "Research Paper"]
    """Type of reference for display."""
    
    short_description: str
    """Brief title/description (40-60 chars)."""
    
    relevance: Literal["A", "B"]
    """Triage label (only A and B refs appear in Feature Matrix)."""
    
    earliest_priority: str
    """Earliest priority date (patents: YYYY-MM-DD) or pub year (NPL: YYYY)."""
    
    jurisdiction: str
    """Country code for patents (US, EP, CN, JP, KR) or journal name for NPL."""
    
    feature_coverage: dict[str, Literal["Y", "Y1", "N"]]
    """Mapping of feature ID to coverage: Y=disclosed, Y1=partial, N=absent."""
    
    aspects_covered: str
    """Which aspects this reference covers (concise summary)."""
    
    comments: str
    """Additional comments including pin-cites."""
    
    x_category: bool
    """True if ALL core features have Y coverage (anticipatory reference)."""


# =============================================================================
# Legacy Types (for backward compatibility)
# =============================================================================

class Plan(TypedDict):
    """A structured plan created by the planner agent."""
    
    search_queries: list[str]
    """List of search queries to execute for novelty checking."""
    
    areas_to_investigate: list[str]
    """Key areas/domains to investigate for prior art."""
    
    reasoning: str
    """The planner's reasoning for this plan."""


class SearchResult(TypedDict):
    """A single search result from the search agent."""
    
    query: str
    """The query that was searched."""
    
    findings: str
    """Summary of what was found."""
    
    relevant_prior_art: list[str]
    """List of relevant prior art or similar ideas found."""
    
    novelty_indicators: str
    """Indicators about novelty (novel aspects vs. existing concepts)."""


class NoveltyAssessment(TypedDict):
    """Final novelty assessment from the orchestrator."""
    
    is_novel: bool
    """Whether the idea is considered novel."""
    
    novelty_score: float
    """Score from 0-1 indicating degree of novelty."""
    
    novel_aspects: list[str]
    """Aspects of the idea that appear novel."""
    
    existing_prior_art: list[str]
    """Similar existing ideas or prior art found."""
    
    recommendations: list[str]
    """Recommendations for the customer."""
    
    summary: str
    """Executive summary of the novelty assessment."""


# =============================================================================
# State Reducer Functions (Phase 0)
# =============================================================================

def merge_references(existing: list[Reference], new: list[Reference]) -> list[Reference]:
    """Merge reference lists, deduplicating by ref_id.

    When parallel subagents find the same reference via different methods,
    this ensures it appears only once with combined discovery methods.

    Args:
        existing: Current references in state
        new: New references to add

    Returns:
        Merged list with duplicates removed (based on ref_id)
    """
    if not existing:
        return new
    if not new:
        return existing

    # Build lookup by ref_id
    seen = {ref["ref_id"]: ref for ref in existing}

    for ref in new:
        ref_id = ref["ref_id"]
        if ref_id in seen:
            # Merge discovery methods
            existing_ref = seen[ref_id]
            existing_methods = set(existing_ref.get("discovery_method", "").split(","))
            new_method = ref.get("discovery_method", "")
            if new_method:
                existing_methods.add(new_method)
                existing_ref["discovery_method"] = ",".join(sorted(existing_methods))
        else:
            seen[ref_id] = ref

    return list(seen.values())


def merge_findings_accumulator(
    existing: FindingsAccumulator | None,
    new: FindingsAccumulator | None
) -> FindingsAccumulator:
    """Merge findings accumulators, appending rounds and deduplicating references.

    This reducer handles updates from parallel subagents that each add findings
    to the accumulator. Rounds are appended chronologically, and references are
    deduplicated across all rounds.

    Args:
        existing: Current accumulator in state (may be None initially)
        new: New accumulator data to merge

    Returns:
        Merged accumulator with all rounds and deduplicated references
    """
    if existing is None and new is None:
        return {}
    if existing is None:
        return new
    if new is None:
        return existing

    # Merge rounds (append chronologically)
    merged_rounds = existing.get("rounds", []) + new.get("rounds", [])

    # Merge references (deduplicate)
    merged_refs = merge_references(
        existing.get("all_references", []),
        new.get("all_references", [])
    )

    # Merge vocabulary (deduplicate by term)
    existing_vocab = {v["term"]: v for v in existing.get("all_vocabulary", [])}
    for vocab in new.get("all_vocabulary", []):
        existing_vocab[vocab["term"]] = vocab
    merged_vocab = list(existing_vocab.values())

    return {
        "scope_markdown": new.get("scope_markdown", existing.get("scope_markdown", "")),
        "features": new.get("features", existing.get("features", [])),
        "rounds": merged_rounds,
        "all_references": merged_refs,
        "all_vocabulary": merged_vocab,
        "final_coverage": new.get("final_coverage", existing.get("final_coverage", [])),
        "stop_reason": new.get("stop_reason", existing.get("stop_reason")),
        "current_round": max(
            new.get("current_round", 0),
            existing.get("current_round", 0)
        ),
    }


def merge_coverage(existing: list[CoverageStatus], new: list[CoverageStatus]) -> list[CoverageStatus]:
    """Merge coverage status lists, taking latest status per feature.

    Args:
        existing: Current coverage status
        new: New coverage status

    Returns:
        Merged coverage with latest status per feature_id
    """
    if not existing:
        return new
    if not new:
        return existing

    # Build lookup by feature_id, new values override
    coverage_map = {c["feature_id"]: c for c in existing}
    coverage_map.update({c["feature_id"]: c for c in new})

    return list(coverage_map.values())


# =============================================================================
# Main Agent State
# =============================================================================

class DeepAgentState(TypedDict):
    """The unified state for the novelty checker deep agent.
    
    This state combines:
    - Middleware state (todos, skills)
    - Novelty assessment state (scope, features, references)
    - Search state (queries, results, coverage)
    """
    
    # -------------------------------------------------------------------------
    # Core Message History
    # -------------------------------------------------------------------------
    messages: Annotated[list[AnyMessage], add_messages]
    """The conversation message history."""
    
    # -------------------------------------------------------------------------
    # Middleware State (from TodoListMiddleware, SkillsMiddleware)
    # -------------------------------------------------------------------------
    todos: NotRequired[list[Todo]]
    """Current todo list for tracking progress."""
    
    skills_metadata: NotRequired[list[SkillMetadata]]
    """Available skills metadata."""
    
    loaded_skills: NotRequired[dict[str, str]]
    """Skills that have been fully loaded (name -> content)."""
    
    # -------------------------------------------------------------------------
    # Stage 1: Scoping
    # -------------------------------------------------------------------------
    customer_idea: NotRequired[str]
    """The customer's invention description."""
    
    scope_markdown: NotRequired[str]
    """Confirmed scope in markdown format."""
    
    scope_confirmed: NotRequired[bool]
    """Whether the scope has been confirmed by user."""
    
    # -------------------------------------------------------------------------
    # Stage 2: Feature Definition
    # -------------------------------------------------------------------------
    features: NotRequired[list[Feature]]
    """Extracted features from the invention."""
    
    features_confirmed: NotRequired[bool]
    """Whether the features have been confirmed by user."""
    
    # -------------------------------------------------------------------------
    # Stages 3-4: Search
    # -------------------------------------------------------------------------
    search_queries_log: NotRequired[list[dict]]
    """Log of all search queries executed."""

    # ✅ Phase 0: Add reducer for safe parallel updates
    references: Annotated[
        list[Reference],
        merge_references
    ]
    """All references found (deduplicated by ref_id with merged discovery methods)."""

    current_search_cycle: NotRequired[int]
    """Current search cycle (for adaptive loop)."""

    # -------------------------------------------------------------------------
    # Findings Persistence (Phase 2)
    # -------------------------------------------------------------------------
    # ✅ Phase 0: Add reducer for safe parallel updates
    findings_accumulator: Annotated[
        FindingsAccumulator,
        merge_findings_accumulator
    ]
    """Persistent findings across research rounds.

    This accumulator stores all findings from the research loop,
    enabling recall even after context truncation in long sessions.
    Also persisted to /findings_accumulator.json via FilesystemBackend.
    Reducer ensures parallel subagent updates are merged correctly.
    """

    # -------------------------------------------------------------------------
    # Stage 5: Screening
    # -------------------------------------------------------------------------
    # ✅ Phase 0: Add reducer for safe parallel updates
    coverage: Annotated[
        list[CoverageStatus],
        merge_coverage
    ]
    """Coverage status per feature (latest status per feature_id)."""
    
    overall_coverage: NotRequired[float]
    """Overall coverage percentage (0-100)."""
    
    # -------------------------------------------------------------------------
    # Stage 6: Report
    # -------------------------------------------------------------------------
    report_markdown: NotRequired[str]
    """Final novelty report in markdown format."""
    
    # -------------------------------------------------------------------------
    # Pipeline Control
    # -------------------------------------------------------------------------
    current_stage: NotRequired[Literal[
        "scoping", "feature_definition", "patent_search",
        "npl_search", "semantic_search", "screening", "report", "complete"
    ]]
    """Current stage in the novelty assessment pipeline."""
    
    remaining_steps: NotRequired[int]
    """Number of remaining steps for the agent (required by LangGraph ReAct)."""
    
    is_last_step: NotRequired[bool]
    """Whether this is the last step (required by LangGraph ReAct)."""
    
    # -------------------------------------------------------------------------
    # Legacy Fields (for backward compatibility)
    # -------------------------------------------------------------------------
    plan: NotRequired[Plan]
    """Legacy: The plan created by the planner agent."""
    
    search_results: NotRequired[list[SearchResult]]
    """Legacy: Results from the search agent."""
    
    assessment: NotRequired[NoveltyAssessment]
    """Legacy: The final novelty assessment."""


# Alias for backward compatibility
AgentState = DeepAgentState
