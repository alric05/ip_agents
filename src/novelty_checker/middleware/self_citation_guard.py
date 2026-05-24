"""Middleware that flags candidate prior art that looks like the inventor's own filings.

Companion to `CitationEnforcementMiddleware` and `ReportPersistenceMiddleware`.
Targets a recurring failure mode observed on C19904 and similar fixtures:
the search returns the inventor's own newly-published patent family, and the
agent uncritically rates them as A-level prior art. Result: `prior_art_hit_rate`
collapses to 0 because none of the GT (genuine) prior art is surfaced as A-refs.

Detection signal: title-similarity (Jaccard on stop-word-stripped tokens)
between the candidate ref's title and the disclosure title from `/scope.md`.
The disclosure has no priority date or applicant we can use yet, so title
overlap is the one signal available — and it is enough for the canonical
case (Jaccard ≈ 0.56 for a true self-citation vs ≈ 0.06 for genuine prior
art with the same domain vocabulary).

Fires when:
1. `/scope.md` exists (post Gate 1), AND
2. `/references.md` exists with at least one A/B-rated row, AND
3. `/final_report.md` does NOT yet exist (we still have time to fix triage), AND
4. At least one A/B ref's title has Jaccard ≥ `_JACCARD_THRESHOLD` against
   the disclosure title.

Effect: appends a directive to the system prompt listing the flagged refs
and instructing the agent to reclassify them to C in `/references.md`
before writing `/final_report.md`. Once either the offending refs drop to
C or `/final_report.md` is written, the middleware goes silent.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from deepagents.backends.protocol import BACKEND_TYPES, BackendProtocol

_logger = logging.getLogger(__name__)

# Tokens that contribute no information about which invention this is.
# Kept short and conservative — anything that legitimately matters in a
# patent title (geometry, mechanism, application, material) is NOT here.
_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the",
    "of", "for", "with", "and", "or", "in", "on", "to", "as", "at", "by",
    "is", "are", "be",
    "novel", "design", "invention",
    "system", "method", "apparatus", "device", "means", "module", "unit",
    "type", "model", "structure", "kind",
})

# Threshold above which we consider two titles to be "the same invention."
# Empirically calibrated against C19904: the self-cited family scores ~0.56,
# the closest genuine prior art scores ~0.06.
_JACCARD_THRESHOLD = 0.50


# ---------------------------------------------------------------------------
# Pure-function helpers (kept top-level for unit-testability)
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# `FilesystemBackend.read()` returns content prefixed with `cat -n`-style
# line numbers: "     1\t<line content>\n     2\t...". Strip them so our
# parsers see the original markdown.
_LINE_NUMBER_PREFIX_RE = re.compile(r"^\s*\d+\t")


def _strip_line_number_prefix(content: str) -> str:
    """Remove `cat -n`-style line-number prefixes from each line.

    No-op if a line does not match the prefix shape, so this is safe
    against inputs that were never prefixed (e.g. file contents read
    via `Path.read_text()`).
    """
    if not content:
        return content
    out_lines = []
    for line in content.split("\n"):
        out_lines.append(_LINE_NUMBER_PREFIX_RE.sub("", line))
    return "\n".join(out_lines)


def _tokenize_title(title: str) -> set[str]:
    """Lowercase, strip punctuation, drop stopwords, dedupe to a set."""
    if not title:
        return set()
    tokens = _TOKEN_RE.findall(title.lower())
    return {t for t in tokens if t not in _STOPWORDS and len(t) > 1}


def _jaccard_similarity(title_a: str, title_b: str) -> float:
    """Strict Jaccard over stop-word-stripped, lowercased token sets.

    Works well when both sides are actual titles (5-10 content tokens).
    For this to give a useful signal the disclosure should be a short
    title (e.g. the raw disclosure's H1) — NOT a scope.md prose paragraph
    (too many tokens → union dominates → similarity collapses below
    threshold for real self-citations). See `_extract_title_from_raw_disclosure`.
    """
    a = _tokenize_title(title_a)
    b = _tokenize_title(title_b)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


_TITLE_SECTION_HEADERS = (
    "## customer idea",
    "## original customer idea",
    "## invention scope",
    "## scope",
    "## confirmed scope",
)


def _extract_disclosure_title(scope_md: str) -> str:
    """Extract the invention title / one-line summary from scope.md.

    Strategy:
      1. Look for a section whose H2 matches one of the known title-bearing
         headers, and return the first non-empty, non-blank line beneath it.
      2. Fall back to the first non-heading, non-blank line in the file.
      3. Return "" if nothing usable found.
    """
    if not scope_md:
        return ""

    lines = scope_md.splitlines()
    n = len(lines)

    # Pass 1: section-anchored
    for i, line in enumerate(lines):
        if line.strip().lower() in _TITLE_SECTION_HEADERS:
            for j in range(i + 1, n):
                candidate = lines[j].strip()
                if not candidate:
                    continue
                if candidate.startswith("#"):
                    break  # next section started without content
                return candidate.lstrip("- *").strip()

    # Pass 2: first non-heading, non-blank line
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#"):
            return s.lstrip("- *").strip()

    return ""


_AUTO_SCOPE_STRIP_RE = re.compile(
    r"^.*?here\s+is\s+the\s+invention\s*:?\s*",
    re.IGNORECASE | re.DOTALL,
)


def _extract_raw_disclosure_from_messages(messages: Any) -> str:
    """Pull the raw disclosure text from the first HumanMessage.

    The eval runner prepends a boilerplate auto-scope prefix; strip it
    so the disclosure itself is what survives. Robust to both the deep
    agent runner's prefix ("Please check the novelty of this invention.
    ... Here is the invention:\n\n<actual disclosure>") and the baseline
    runner's variant.
    """
    if not messages:
        return ""
    try:
        for msg in messages:
            msg_type = getattr(msg, "type", None)
            if msg_type != "human":
                continue
            content = getattr(msg, "content", "")
            if isinstance(content, list):
                content = " ".join(
                    item.get("text", "") if isinstance(item, dict) else str(item)
                    for item in content
                )
            if not isinstance(content, str) or not content.strip():
                continue
            return _AUTO_SCOPE_STRIP_RE.sub("", content, count=1).strip()
    except Exception:
        return ""
    return ""


def _extract_title_from_raw_disclosure(raw: str) -> str:
    """First H1 heading or first non-blank line of the raw disclosure.

    Real SME disclosures usually start with `# A novel design of ...` or
    a similar titled line. Fall back to the first sentence if no heading.
    """
    if not raw:
        return ""
    # First H1 heading
    for line in raw.splitlines():
        s = line.strip()
        if s.startswith("# ") and not s.startswith("## "):
            return s[2:].strip()
    # Fall back: first non-blank, non-heading line
    for line in raw.splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            # Truncate to first sentence to avoid pulling in a wall of text
            for term in (". ", "\n"):
                if term in s:
                    s = s.split(term, 1)[0].strip()
                    break
            return s
    return ""


# A references.md row example:
# | US12323091B1 | Patent | Floating structure for ... | A | 2025-01-17 | US | Y | Y | ...
def _parse_references_md(refs_md: str) -> list[tuple[str, str, str, str]]:
    """Parse the markdown table in references.md.

    Returns a list of (publication_number, title, triage_label, priority_date)
    tuples, one per row. priority_date is the raw text from the
    "Earliest Priority" column (or "" if not present). Header and
    separator lines are skipped. Robust to whitespace and missing
    trailing pipes.
    """
    rows: list[tuple[str, str, str, str]] = []
    if not refs_md:
        return rows

    pub_idx: int | None = None
    title_idx: int | None = None
    triage_idx: int | None = None
    priority_idx: int | None = None  # optional

    # Header-detection gate: only commit to indices once ALL three required
    # columns (pub/title/triage) are located on the same header row. If a
    # partial header appears first (e.g. a pre-table line with just
    # "Publication Number"), we reset and keep scanning.
    for raw in refs_md.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        # Strip outer pipes, split on internal pipes
        cells = [c.strip() for c in line.strip("|").split("|")]

        # Detect header row by content
        lowered = [c.lower() for c in cells]
        if pub_idx is None or title_idx is None or triage_idx is None:
            # Try to locate all three on this line. Accept common variants
            # including the "Short Description" column name the report
            # skill uses in some templates.
            pub_idx = title_idx = triage_idx = None
            priority_idx = None
            for i, c in enumerate(lowered):
                if c in ("publication number", "pub number", "pub. number", "ref id"):
                    pub_idx = i
                elif c in ("title", "short description", "description"):
                    title_idx = i
                elif c in ("relevance", "triage", "triage label", "label"):
                    triage_idx = i
                elif priority_idx is None and (
                    "priorit" in c
                    or c in ("year", "filing year", "earliest year", "filing date")
                ):
                    priority_idx = i
            if pub_idx is not None and title_idx is not None and triage_idx is not None:
                continue  # header located, start parsing data rows next iter
            # Header incomplete on this line — reset and keep scanning.
            pub_idx = title_idx = triage_idx = priority_idx = None
            continue

        # Skip the markdown separator row (---)
        if all(set(c) <= set("-:") for c in cells if c):
            continue

        # Defensive: if somehow any required idx is None here, skip the row
        # rather than crash (the outer middleware's try/except catches it,
        # but that surfaces as a spurious WARNING).
        if pub_idx is None or title_idx is None or triage_idx is None:
            continue
        if max(pub_idx, title_idx, triage_idx) >= len(cells):
            continue

        pub = cells[pub_idx]
        title = cells[title_idx]
        triage = cells[triage_idx].upper().replace("*", "").strip()
        priority = (
            cells[priority_idx]
            if priority_idx is not None and priority_idx < len(cells)
            else ""
        )
        if pub and title:
            rows.append((pub, title, triage, priority))

    return rows


_PRIORITY_DATE_RE = re.compile(r"\b(\d{4})(?:[-/](\d{1,2})(?:[-/](\d{1,2}))?)?\b")


def _parse_priority_date(raw: str) -> tuple[int, int, int] | None:
    """Parse a priority-date cell into (year, month, day).

    Accepts "2025", "2025-01", "2025-01-17", "2025/01/17". Missing
    month/day default to 1 so two refs with only a year can still
    cluster. Returns None if no year is found.
    """
    if not raw:
        return None
    m = _PRIORITY_DATE_RE.search(raw)
    if not m:
        return None
    year = int(m.group(1))
    if not (1900 <= year <= 2100):
        return None
    month = int(m.group(2)) if m.group(2) else 1
    day = int(m.group(3)) if m.group(3) else 1
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return (year, month, day)


def _date_diff_days(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    """Approximate day-count distance between two (y, m, d) tuples.
    Uses 30-day months / 365-day years — close enough for "within N days"
    family-clustering checks; we never need calendar-exact arithmetic."""
    days_a = a[0] * 365 + a[1] * 30 + a[2]
    days_b = b[0] * 365 + b[1] * 30 + b[2]
    return abs(days_a - days_b)


# Refs with priority dates within this window of an already-flagged ref
# are likely from the same patent family (same applicant filing a cluster
# of related patents on the same day or nearby days).
_FAMILY_CLUSTER_WINDOW_DAYS = 30

# Disclosure-title candidates longer than this (in content tokens) are
# rejected as non-title prose. A 30-token paragraph compared against a
# 5-token patent title has a huge union that drags Jaccard below
# threshold for real self-citations.
_MAX_DISCLOSURE_TITLE_TOKENS = 15


def _parse_findings_accumulator(content: str) -> list[tuple[str, str, str, str]]:
    """Parse `findings_auto_accumulator.json` into reference rows.

    Returns the same shape as `_parse_references_md`:
    (publication_number, title, triage_label, priority_date).
    Used as a fallback when /references.md is absent (the deep agent
    sometimes embeds references inline in the report instead of writing
    a separate file). Priority date is rarely captured by the
    accumulator, so most rows return "" for it — that just means the
    family-cluster signal won't fire for accumulator-only sessions.
    """
    rows: list[tuple[str, str, str, str]] = []
    if not content:
        return rows
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return rows

    if isinstance(data, dict):
        refs = data.get("all_references") or data.get("references") or []
    elif isinstance(data, list):
        refs = data
    else:
        return rows

    for ref in refs:
        if not isinstance(ref, dict):
            continue
        pub = (
            ref.get("publication_number")
            or ref.get("pub_number")
            or ref.get("ref_id")
            or ""
        )
        title = ref.get("title") or ref.get("dwpi_title") or ""
        triage = (
            ref.get("triage_label")
            or ref.get("triage")
            or ref.get("relevance")
            or ""
        )
        triage = str(triage).upper().strip()
        priority = (
            ref.get("earliest_priority")
            or ref.get("priority_date")
            or ref.get("priority")
            # `date` is the historical normalization name used by
            # FindingsPersistenceMiddleware — kept for backward compat
            # against older sessions written before priority_date was
            # preserved as-is.
            or ref.get("date")
            or ""
        )
        if pub and title:
            rows.append((str(pub), str(title), triage, str(priority)))
    return rows


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class SelfCitationGuardMiddleware(AgentMiddleware):
    """Code-level enforcement that the inventor's own filings aren't rated as prior art.

    Args:
        backend: Backend instance or factory for filesystem access.
        jaccard_threshold: Title-similarity cutoff above which a candidate
            ref is flagged. Default 0.50 (validated against C19904).
    """

    def __init__(
        self,
        *,
        backend: "BACKEND_TYPES",
        jaccard_threshold: float = _JACCARD_THRESHOLD,
    ) -> None:
        self._backend = backend
        self._jaccard_threshold = jaccard_threshold

    # ------------------------------------------------------------------
    # AgentMiddleware hooks
    # ------------------------------------------------------------------

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: "Callable[[ModelRequest], ModelResponse]",
    ) -> ModelCallResult:
        request = self._maybe_inject_directive(request)
        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: "Callable[[ModelRequest], Awaitable[ModelResponse]]",
    ) -> ModelCallResult:
        request = self._maybe_inject_directive(request)
        return await handler(request)

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def _get_backend(self, runtime: Any) -> "BackendProtocol":
        if callable(self._backend):
            return self._backend(runtime)
        return self._backend

    def _maybe_inject_directive(self, request: ModelRequest) -> ModelRequest:
        try:
            backend = self._get_backend(request.runtime)
            raw_disclosure = _extract_raw_disclosure_from_messages(request.messages)
            flagged = self._compute_flagged_refs(backend, raw_disclosure)
            if flagged:
                disclosure_title = flagged[0][3]
                directive = self._build_directive(disclosure_title, flagged)
                existing = request.system_message.content if request.system_message else ""
                new_system = SystemMessage(content=existing + "\n\n" + directive)
                return request.override(system_message=new_system)
        except Exception:
            _logger.warning(
                "SelfCitationGuardMiddleware: injection skipped due to unexpected error.",
                exc_info=True,
            )
        return request

    # ------------------------------------------------------------------
    # Filesystem probes + flagging logic (split out for testability)
    # ------------------------------------------------------------------

    def _compute_flagged_refs(
        self,
        backend: "BackendProtocol",
        raw_disclosure_text: str = "",
    ) -> list[tuple[str, str, float, str, str]]:
        """Return the list of (pub_number, title, jaccard, disclosure_title, reason)
        for every A/B ref that looks like a self-citation.

        Two flagging signals:
          1. Title similarity ≥ jaccard_threshold against disclosure title.
          2. Priority date within ±30 days of an already-title-flagged ref
             (catches family members with different titles but same filing date).

        Returns [] if any precondition fails (final_report exists, no scope,
        no refs, no flags).
        """
        # Precondition: final_report missing (we still have time)
        if self._file_is_nonempty(backend, "/final_report.md"):
            return []

        # Build the disclosure title from whatever sources are available.
        # Priority: original human message (most stable; agent can't rewrite it)
        # then scope.md. Only KEEP candidates short enough to give useful
        # Jaccard signal — a 30-token prose paragraph dilutes the union
        # so much that real self-citations score below threshold.
        disclosure_candidates: list[str] = []
        raw_title = _extract_title_from_raw_disclosure(raw_disclosure_text)
        if raw_title and len(_tokenize_title(raw_title)) <= _MAX_DISCLOSURE_TITLE_TOKENS:
            disclosure_candidates.append(raw_title)

        scope_md = self._safe_read(backend, "/scope.md")
        if scope_md.strip():
            scope_title = _extract_disclosure_title(scope_md)
            if scope_title and len(_tokenize_title(scope_title)) <= _MAX_DISCLOSURE_TITLE_TOKENS:
                disclosure_candidates.append(scope_title)

        if not disclosure_candidates:
            rows = self._collect_reference_rows(backend)
            ab_count = sum(1 for r in rows if r[2] in ("A", "B"))
            if ab_count > 0:
                _logger.warning(
                    "SelfCitationGuard: skipping self-citation check — could not extract "
                    "disclosure title from raw message or /scope.md, but %d A/B ref(s) exist. "
                    "Self-citations may go undetected this round. "
                    "raw_disclosure_len=%d scope_md_len=%d",
                    ab_count,
                    len(raw_disclosure_text or ""),
                    len(scope_md),
                )
            return []
        disclosure_title = disclosure_candidates[0]

        rows = self._collect_reference_rows(backend)
        if not rows:
            return []

        # Pass 1: title-similarity flags (max similarity across candidates)
        title_flagged: list[tuple[str, str, float, str, str]] = []
        ab_rows: list[tuple[str, str, str, str]] = [
            r for r in rows if r[2] in ("A", "B")
        ]
        for pub, title, _triage, priority in ab_rows:
            best_sim = 0.0
            best_source = disclosure_title
            for candidate in disclosure_candidates:
                sim = _jaccard_similarity(candidate, title)
                if sim > best_sim:
                    best_sim = sim
                    best_source = candidate
            if best_sim >= self._jaccard_threshold:
                title_flagged.append(
                    (pub, title, best_sim, best_source, f"title-similarity {best_sim:.2f}")
                )

        # Pass 2: priority-date cluster around any title-flagged ref
        seen = {p for p, *_ in title_flagged}
        cluster_flagged: list[tuple[str, str, float, str, str]] = []
        anchor_dates: list[tuple[int, int, int]] = []
        for pub, _t, _sim, _dt, _r in title_flagged:
            for row_pub, _, _, raw_date in ab_rows:
                if row_pub == pub:
                    parsed = _parse_priority_date(raw_date)
                    if parsed is not None:
                        anchor_dates.append(parsed)
                    break

        if anchor_dates:
            for pub, title, _triage, raw_date in ab_rows:
                if pub in seen:
                    continue
                parsed = _parse_priority_date(raw_date)
                if parsed is None:
                    continue
                for anchor in anchor_dates:
                    if _date_diff_days(parsed, anchor) <= _FAMILY_CLUSTER_WINDOW_DAYS:
                        sim = _jaccard_similarity(disclosure_title, title)
                        cluster_flagged.append(
                            (
                                pub,
                                title,
                                sim,
                                disclosure_title,
                                (
                                    f"family-cluster (priority {raw_date} within "
                                    f"{_FAMILY_CLUSTER_WINDOW_DAYS} days of flagged refs)"
                                ),
                            )
                        )
                        seen.add(pub)
                        break

        return title_flagged + cluster_flagged

    def _collect_reference_rows(
        self, backend: "BackendProtocol"
    ) -> list[tuple[str, str, str, str]]:
        """Collect (pub, title, triage, priority) rows from any available source.

        Sources merged, with this precedence:
          - Title comes from `findings_auto_accumulator.json` when possible
            (raw search-API title; the agent can't rewrite it to dodge the
            self-citation check).
          - Triage label comes from `/references.md` when possible
            (the agent's latest classification is the authoritative one).
          - Priority date comes from `/references.md` (accumulator rarely
            captures it).
          - Any ref that appears only in one source keeps whatever fields
            that source provides.
        """
        # Start with accumulator rows keyed by pub number — authoritative titles
        acc_by_pub: dict[str, tuple[str, str, str, str]] = {}
        for path in ("/findings_auto_accumulator.json", "/findings_accumulator.json"):
            content = self._safe_read(backend, path)
            if not content.strip():
                continue
            for pub, title, triage, priority in _parse_findings_accumulator(content):
                if pub not in acc_by_pub:
                    acc_by_pub[pub] = (pub, title, triage, priority)

        # Overlay /references.md: prefer its triage + priority date, keep acc title
        md_by_pub: dict[str, tuple[str, str, str, str]] = {}
        refs_md = self._safe_read(backend, "/references.md")
        if refs_md.strip():
            for pub, md_title, md_triage, md_priority in _parse_references_md(refs_md):
                md_by_pub[pub] = (pub, md_title, md_triage, md_priority)

        all_pubs = set(acc_by_pub) | set(md_by_pub)
        merged: list[tuple[str, str, str, str]] = []
        for pub in all_pubs:
            acc = acc_by_pub.get(pub)
            md = md_by_pub.get(pub)
            if acc and md:
                title = acc[1] or md[1]          # accumulator title wins
                triage = md[2] or acc[2]         # md triage wins (agent's latest call)
                priority = md[3] or acc[3]       # md priority wins (has dates)
                merged.append((pub, title, triage, priority))
            elif acc:
                merged.append(acc)
            else:
                merged.append(md)  # type: ignore[arg-type]

        return merged

    @staticmethod
    def _safe_read(backend: "BackendProtocol", path: str) -> str:
        try:
            content = backend.read(path)
        except Exception:
            return ""
        if not isinstance(content, str):
            return ""
        if content.startswith("Error"):
            return ""
        return _strip_line_number_prefix(content)

    @staticmethod
    def _file_is_nonempty(backend: "BackendProtocol", path: str) -> bool:
        content = SelfCitationGuardMiddleware._safe_read(backend, path)
        return bool(content.strip())

    # ------------------------------------------------------------------
    # Directive
    # ------------------------------------------------------------------

    @staticmethod
    def _build_directive(
        disclosure_title: str,
        flagged: list[tuple[str, str, float, str, str]],
    ) -> str:
        bullets = "\n".join(
            f"  - **{pub}** — \"{title}\" — {reason}"
            for pub, title, _sim, _disc, reason in flagged
        )
        return (
            "## >>> SELF-CITATION GUARD (Auto-detected) <<<\n"
            "\n"
            f"Disclosure title: \"{disclosure_title}\"\n"
            "\n"
            "The following A/B-rated references look like the inventor's "
            "own later filings — flagged either by close title match to the "
            f"disclosure (Jaccard ≥ {_JACCARD_THRESHOLD:.2f}) or by sharing a "
            f"priority date within {_FAMILY_CLUSTER_WINDOW_DAYS} days of a "
            "title-flagged ref (likely same patent family):\n"
            "\n"
            f"{bullets}\n"
            "\n"
            "These should NOT be treated as prior art. Before writing "
            "`/final_report.md` you MUST:\n"
            "\n"
            "1. Reclassify each flagged reference to triage `C` in "
            "`/references.md` via `edit_file` (or rewrite the row).\n"
            "2. Remove them from the prior-art Feature Matrix and the "
            "Novelty Assessment — they should not contribute to anticipation.\n"
            "3. Re-rank the remaining A/B references and surface the next "
            "most-relevant genuine prior art if your A-list is now thin.\n"
            "\n"
            "If you have positive evidence that a flagged reference is "
            "genuinely independent (different applicant, earlier filing date "
            "than the disclosure), keep it but add a one-line justification in "
            "`/references.md` explaining why.\n"
        )
