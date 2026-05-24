"""Extract structured data from AI free-form text responses.

Strategy:
1. **Primary**: Parse ``json:tag`` fenced code blocks emitted by the LLM
   (the prompts instruct it to emit these alongside natural text).
2. **Fallback**: Heuristic regex parsing for the LLM's existing patterns
   (numbered questions with defaults, markdown feature tables).
3. **Last resort**: Return data from graph state if text parsing fails.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.novelty_checker.api.schemas import (
    CompletionData,
    FeatureItem,
    RawBubbleSpec,
    RawFeatureSpec,
    RawQuestionSpec,
    ResearchingData,
    ResearchProgress,
)
from src.novelty_checker.middleware._backend_utils import strip_line_numbers

_logger = logging.getLogger(__name__)


# =============================================================================
# Primary: JSON Block Extraction
# =============================================================================

_JSON_BLOCK_RE = re.compile(
    r"```json:(\w+)\s*\n(.*?)```",
    re.DOTALL,
)


def extract_structured_blocks(text: str) -> dict[str, Any]:
    """Extract ``json:tag`` fenced blocks from AI response text.

    The prompts instruct the LLM to emit blocks like:
        ```json:questions
        [{"id": "Q1", "question": "...", "default_answer": "..."}]
        ```

    Returns:
        Dict mapping tag name -> parsed JSON value.
    """
    blocks: dict[str, Any] = {}
    for match in _JSON_BLOCK_RE.finditer(text):
        tag = match.group(1)
        raw_json = match.group(2).strip()
        try:
            blocks[tag] = json.loads(raw_json)
        except json.JSONDecodeError:
            _logger.debug("Failed to parse json:%s block", tag)
    return blocks


# =============================================================================
# Fallback: Heuristic Parsing
# =============================================================================

# Pattern: numbered question with "→ Default if confirmed:" or "-> Default if confirmed:"
_QUESTION_RE = re.compile(
    r"(\d+)\.\s*\*{0,2}(.+?)\*{0,2}\s*\n"
    r"\s*(?:→|->|→)\s*Default if confirmed:\s*(.+?)(?:\n|$)",
    re.MULTILINE,
)

# Simpler pattern: numbered question without defaults (broader catch)
_QUESTION_SIMPLE_RE = re.compile(
    r"(\d+)\.\s*\*{0,2}(.+?\?)\*{0,2}\s*$",
    re.MULTILINE,
)


def parse_clarifying_questions_heuristic(text: str) -> list[dict[str, Any]]:
    """Fallback: parse numbered questions with default answers from AI text.

    Expected pattern:
        1. **What wavelength range?**
           → Default if confirmed: 300-400nm UV range
    """
    questions: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    # Try pattern with defaults first
    for match in _QUESTION_RE.finditer(text):
        qid = f"Q{match.group(1)}"
        if qid in seen_ids:
            continue
        seen_ids.add(qid)
        questions.append({
            "id": qid,
            "question": match.group(2).strip().rstrip("?") + "?",
            "default_answer": match.group(3).strip(),
        })

    if questions:
        return questions

    # Fallback: questions without defaults
    for match in _QUESTION_SIMPLE_RE.finditer(text):
        qid = f"Q{match.group(1)}"
        if qid in seen_ids:
            continue
        seen_ids.add(qid)
        questions.append({
            "id": qid,
            "question": match.group(2).strip(),
            "default_answer": None,
        })

    return questions


# Feature table row: | F1 | Name | Description | Y/N | keyword1, keyword2 |
_FEATURE_TABLE_RE = re.compile(
    r"\|\s*(F\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(Y|N|Yes|No)\s*\|\s*(.+?)\s*\|",
    re.IGNORECASE,
)


def parse_features_from_table(text: str) -> list[dict[str, Any]]:
    """Fallback: parse features from a markdown table in AI text.

    Expected pattern:
        | F1 | UV Sensor | Detects UV degradation | Y | UV, sensor, degradation |
    """
    features: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for match in _FEATURE_TABLE_RE.finditer(text):
        fid = match.group(1).upper()
        if fid in seen_ids:
            continue
        seen_ids.add(fid)

        is_core_raw = match.group(4).strip().upper()
        is_core = is_core_raw in ("Y", "YES")

        features.append({
            "id": fid,
            "name": match.group(2).strip(),
            "description": match.group(3).strip(),
            "is_core": is_core,
            "keywords": [k.strip() for k in match.group(5).split(",") if k.strip()],
            "priority": "P1" if is_core else "P2",
        })

    return features


# =============================================================================
# Filesystem Helpers
# =============================================================================

def _read_file_safe(backend: Any, path: str) -> str | None:
    """Read a file from backend, returning None on any error."""
    try:
        content = backend.read(path)
        # FilesystemBackend returns error strings for missing files
        if isinstance(content, str) and content.startswith("Error"):
            return None
        return content
    except Exception:
        return None


def _extract_use_case_from_scope(scope_md: str | None) -> str:
    """Return the '## Confirmed Scope' body, falling back to '## Customer Idea'.

    Strips FilesystemBackend's `N\\t` line-number prefixes before matching so
    the regex works on both raw and backend-read content.
    """
    if not scope_md:
        return ""
    cleaned = strip_line_numbers(scope_md)
    for heading in ("Confirmed Scope", "Customer Idea"):
        pattern = rf"^##\s+{heading}\s*\n(.+?)(?=\n##\s|\Z)"
        m = re.search(pattern, cleaned, flags=re.DOTALL | re.MULTILINE | re.IGNORECASE)
        if m:
            body = m.group(1).strip()
            if body:
                return body
    return ""


def _read_accumulator(backend: Any) -> dict[str, Any] | None:
    """Read and parse findings_accumulator.json from backend."""
    raw = _read_file_safe(backend, "/findings_accumulator.json")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


# =============================================================================
# Unified Stage Data Builder
# =============================================================================

def build_stage_data(
    stage: str,
    ai_text: str,
    state_snapshot: dict[str, Any],
    backend: Any,
) -> dict[str, Any]:
    """Build stage_data from AI response text, graph state, and filesystem.

    Extraction priority: JSON markers → heuristic parsing → state fallback.

    Args:
        stage: Detected API stage ("scoping", "features", "researching", "complete").
        ai_text: The last AI message text.
        state_snapshot: Relevant fields from the graph state.
        backend: FilesystemBackend for reading persisted artifacts.

    Returns:
        Dict suitable for APIResponse.stage_data.
    """
    # Try structured JSON blocks first
    blocks = extract_structured_blocks(ai_text)

    if stage == "scoping":
        return _build_scoping_data(blocks, ai_text, state_snapshot, backend)
    elif stage == "features":
        return _build_features_data(blocks, ai_text, state_snapshot, backend)
    elif stage == "researching":
        return _build_researching_data(backend)
    elif stage == "complete":
        return _build_completion_data(ai_text, state_snapshot, backend)

    return {}


def _build_scoping_data(
    blocks: dict[str, Any],
    ai_text: str,
    state_snapshot: dict[str, Any],
    backend: Any,
) -> dict[str, Any]:
    """Build RawBubbleSpec from available sources (three-tier fallback).

    Priority:
    1. ``json:scoping`` block (new format with introText, title, etc.)
    2. ``json:questions`` block (legacy format with id, default_answer)
    3. Heuristic regex parsing of numbered questions
    """
    scope_summary = _read_file_safe(backend, "/scope.md") if backend else None

    # --- Tier 1: new json:scoping block ---
    scoping_block = blocks.get("scoping")
    if scoping_block and isinstance(scoping_block, dict):
        questions = []
        for q in scoping_block.get("questions", []):
            try:
                questions.append(RawQuestionSpec(**q))
            except Exception:
                _logger.debug("Skipping malformed scoping question: %s", q)

        # Prepend scopeSummary to introText if present
        scope_summary_text = scoping_block.get("scopeSummary", "")
        intro_text = scoping_block.get("introText", "")
        if scope_summary_text and intro_text:
            combined_intro = f"{scope_summary_text}\n\n{intro_text}"
        else:
            combined_intro = scope_summary_text or intro_text

        return RawBubbleSpec(
            component="assumptionBubble",
            introText=combined_intro or None,
            questions=questions,
            defaultAssumptionLabel="Assumption",
            alternativeText=scoping_block.get("alternativeText"),
            additionalAssumptions=scoping_block.get("additionalAssumptions", []),
        ).model_dump()

    # --- Tier 2: legacy json:questions block ---
    raw_questions = blocks.get("questions")

    # --- Tier 3: heuristic regex fallback ---
    if not raw_questions:
        raw_questions = parse_clarifying_questions_heuristic(ai_text)

    # If scope is confirmed and no new questions → plainBubble
    if scope_summary and not raw_questions:
        return RawBubbleSpec(
            component="plainBubble",
            text=scope_summary,
        ).model_dump()

    # Convert legacy {id, question, default_answer} → RawQuestionSpec
    questions = []
    for q in (raw_questions or []):
        try:
            # Derive a descriptive title from the question text
            q_text = q.get("question", "")
            title = _derive_title(q_text) or q.get("id", "")
            questions.append(RawQuestionSpec(
                title=title,
                question=q_text,
                assumptionText=q.get("default_answer"),
            ))
        except Exception:
            _logger.debug("Skipping malformed question: %s", q)

    return RawBubbleSpec(
        component="assumptionBubble",
        questions=questions,
        defaultAssumptionLabel="Assumption",
    ).model_dump()


def _derive_title(question_text: str) -> str:
    """Derive a short title from a question string (first 2-4 meaningful words)."""
    if not question_text:
        return ""
    # Strip leading "What/Which/Are/Is/Do/Does/How/Any" and trailing "?"
    cleaned = re.sub(r"^(what|which|are|is|do|does|how|any)\s+", "", question_text.strip(), flags=re.IGNORECASE)
    cleaned = cleaned.rstrip("?").strip()
    words = cleaned.split()
    # Take first 3 words, capitalize first letter
    title = " ".join(words[:3])
    return title[:50].strip() if title else question_text[:50].strip()


def _build_features_data(
    blocks: dict[str, Any],
    ai_text: str,
    state_snapshot: dict[str, Any],
    backend: Any,
) -> dict[str, Any]:
    """Build a featureConfirmationBubble RawBubbleSpec for the frontend A2UI widget."""
    raw_features = blocks.get("features")
    if not raw_features:
        raw_features = parse_features_from_table(ai_text)
    if not raw_features:
        raw_features = state_snapshot.get("features", [])

    feature_specs: list[RawFeatureSpec] = []
    for f in (raw_features or []):
        try:
            item = FeatureItem(**f)
        except Exception:
            _logger.debug("Skipping malformed feature: %s", f)
            continue
        text = f"{item.name} — {item.description}" if item.description else item.name
        feature_specs.append(RawFeatureSpec(text=text, isCore=item.is_core))

    scope_md = _read_file_safe(backend, "/scope.md") if backend else None
    use_case_text = _extract_use_case_from_scope(scope_md)

    return RawBubbleSpec(
        component="featureConfirmationBubble",
        headingText=(
            "I've identified the following key features of your invention. "
            "Please confirm or edit them before I begin the research:"
        ),
        useCaseLabel="Assumed use case",
        useCaseText=use_case_text or None,
        featuresLabel="Features List - Select the ones you consider core",
        coreLabel="Core",
        features=feature_specs,
    ).model_dump()


def _build_researching_data(backend: Any) -> dict[str, Any]:
    """Build ResearchingData from findings accumulator."""
    accum = _read_accumulator(backend) if backend else None

    progress = ResearchProgress(
        current_round=accum.get("current_round", 1) if accum else 0,
        max_rounds=5,
        coverage_pct=accum.get("final_coverage_pct") if accum else None,
        references_found=len(accum.get("all_references", [])) if accum else 0,
        features_coverage=accum.get("final_coverage") if accum else None,
    )

    return ResearchingData(progress=progress).model_dump()


def _build_completion_data(
    ai_text: str,
    state_snapshot: dict[str, Any],
    backend: Any,
) -> dict[str, Any]:
    """Build CompletionData from report + state + filesystem."""
    # Read final report from filesystem (most reliable source)
    report_md = _read_file_safe(backend, "/final_report.md") if backend else None

    # Fall back to AI text if report file not found
    if not report_md:
        report_md = ai_text

    # Get features from state
    raw_features = state_snapshot.get("features", [])
    features = []
    for f in raw_features:
        try:
            features.append(FeatureItem(**f))
        except Exception:
            pass

    return CompletionData(
        report_markdown=report_md or "",
        features=features,
        references=state_snapshot.get("references", []),
        coverage_summary=state_snapshot.get("coverage", []),
        overall_coverage_pct=state_snapshot.get("overall_coverage"),
    ).model_dump()
