"""Findings persistence middleware for automatic capture of search results.

This middleware intercepts tool call results from search tools and automatically
persists the findings to the filesystem, ensuring they survive context truncation.

Phase 4 of the Findings Persistence Implementation.

The middleware:
1. Intercepts wrap_tool_call for patent, NPL, and semantic search tools
2. Extracts reference data from search results
3. Writes to /findings_auto_accumulator.json for structured persistence
4. Writes individual capture files to /findings/auto/*.json

This works in conjunction with the explicit findings tools (Phase 3) that agents
can call directly. The middleware provides a safety net for automatic persistence
even if agents forget to call the explicit save_round_findings tool.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
from datetime import datetime
from typing import TYPE_CHECKING, Any, NotRequired

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime
from typing_extensions import Annotated, TypedDict

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langgraph.prebuilt.tool_node import ToolCallRequest
    from langgraph.types import Command

    from deepagents.backends.protocol import BACKEND_TYPES, BackendProtocol

_logger = logging.getLogger(__name__)


# =============================================================================
# State Schema
# =============================================================================

class FindingsState(TypedDict, total=False):
    """State schema for FindingsPersistenceMiddleware.
    
    Tracks automatically captured findings from search tool results.
    """
    
    auto_captured_findings: NotRequired[list[dict[str, Any]]]
    """List of findings automatically captured from search tools."""
    
    capture_round: NotRequired[int]
    """Current auto-capture round number."""


# =============================================================================
# Configuration
# =============================================================================

# Search tools whose results should be captured
SEARCH_TOOLS_TO_CAPTURE = {
    # Patent search tools
    "patent_keyword_search",
    "batch_patent_search",
    # NPL search tools
    "npl_search",
    "batch_npl_search",
    # Semantic search tools
    "semantic_patent_search",
    "batch_semantic_search",
    # Citation tools
    "get_patent_citations",
    "batch_citation_search",
    "citation_chain_search",
    # Unified batch
    "batch_unified_search",
}

# File paths for auto-captured findings
AUTO_FINDINGS_DIR = "/findings/auto"
AUTO_ACCUMULATOR_FILE = "/findings_auto_accumulator.json"


# =============================================================================
# Helper Functions
# =============================================================================

def _extract_references_from_result(tool_name: str, result: Any) -> list[dict]:
    """Extract reference data from a tool result.
    
    Args:
        tool_name: Name of the tool that produced the result
        result: The raw tool result (string or dict)
        
    Returns:
        List of extracted reference dicts with normalized fields
    """
    references = []
    
    # Handle string results (most search tools return formatted text)
    if isinstance(result, str):
        # Try to parse as JSON first
        try:
            parsed = json.loads(result)
            if isinstance(parsed, list):
                references = parsed
            elif isinstance(parsed, dict) and "results" in parsed:
                references = parsed["results"]
            elif isinstance(parsed, dict) and "references" in parsed:
                references = parsed["references"]
        except json.JSONDecodeError:
            # Not JSON — for citation tools, extract pub numbers from markdown
            if "citation" in tool_name.lower():
                references = _extract_citations_from_markdown(result)
            else:
                _logger.debug(f"Tool {tool_name} returned non-JSON text, skipping auto-extraction")
                return []
    
    # Handle dict results
    elif isinstance(result, dict):
        if "results" in result:
            references = result["results"]
        elif "references" in result:
            references = result["references"]
        elif "hits" in result:
            references = result["hits"]
    
    # Handle list results
    elif isinstance(result, list):
        references = result
    
    # Normalize reference fields
    normalized = []
    for ref in references:
        if not isinstance(ref, dict):
            continue
        
        normalized_ref = {
            "publication_number": ref.get("publication_number") or ref.get("uid") or ref.get("accession_number", ""),
            "title": ref.get("title", ""),
            "source_tool": tool_name,
            "captured_at": datetime.now().isoformat(),
        }
        
        # Add optional fields if present
        if "relevance" in ref or "triage_label" in ref:
            normalized_ref["relevance"] = ref.get("relevance") or ref.get("triage_label", "")
        if "features" in ref:
            normalized_ref["features"] = ref["features"]
        # Preserve priority_date under its real name so downstream
        # middleware (SelfCitationGuard) can do family-cluster detection.
        # `date` is kept too for backward compat with older consumers.
        if "priority_date" in ref or "pub_year" in ref:
            priority = ref.get("priority_date") or ref.get("pub_year", "")
            normalized_ref["priority_date"] = priority
            normalized_ref["date"] = priority
        if "assignee" in ref or "applicant" in ref:
            # Same-applicant detection is another self-citation signal —
            # capture it even though current SelfCitationGuard doesn't use
            # it yet. Cheap insurance for future work.
            normalized_ref["assignee"] = ref.get("assignee") or ref.get("applicant", "")
        if "abstract" in ref:
            normalized_ref["abstract"] = ref["abstract"][:500]  # Truncate

        normalized.append(normalized_ref)
    
    return normalized


def _extract_citations_from_markdown(text: str) -> list[dict]:
    """Extract citation references from formatted markdown output.
    
    Citation tools return markdown with lines like:
      1. **US10234567B2**
         - Title: ...
         - Assignee: ...
         - Priority Date: ...
         - Abstract: ...
    
    Args:
        text: Formatted markdown from citation tools
        
    Returns:
        List of reference dicts extracted from the markdown
    """
    import re
    references = []
    current_ref: dict[str, str] | None = None
    
    for line in text.split("\n"):
        # Match numbered citation lines: "1. **US10234567B2**"
        pub_match = re.match(r'^\d+\.\s+\*\*([A-Z]{2}[\dA-Z]+)\*\*', line.strip())
        if pub_match:
            if current_ref:
                references.append(current_ref)
            current_ref = {
                "publication_number": pub_match.group(1),
                "source_tool": "citation_analysis",
            }
            continue
        
        if current_ref:
            stripped = line.strip()
            if stripped.startswith("- Title:"):
                current_ref["title"] = stripped[len("- Title:"):].strip()
            elif stripped.startswith("- Assignee:"):
                current_ref["assignee"] = stripped[len("- Assignee:"):].strip()
            elif stripped.startswith("- Priority Date:"):
                current_ref["priority_date"] = stripped[len("- Priority Date:"):].strip()
            elif stripped.startswith("- Abstract:"):
                current_ref["abstract"] = stripped[len("- Abstract:"):].strip()[:500]
    
    # Don't forget the last reference
    if current_ref:
        references.append(current_ref)
    
    return references


def _determine_source_type(tool_name: str) -> str:
    """Determine the source type (patent/npl/semantic/citation) from tool name."""
    if "citation" in tool_name.lower():
        return "citation"
    elif "patent" in tool_name.lower():
        return "patent"
    elif "wos" in tool_name.lower() or "npl" in tool_name.lower() or "ngsp" in tool_name.lower():
        return "npl"
    elif "semantic" in tool_name.lower() or "gist" in tool_name.lower() or "vocabulary" in tool_name.lower():
        return "semantic"
    return "other"


# =============================================================================
# Findings Persistence Middleware
# =============================================================================

class FindingsPersistenceMiddleware(AgentMiddleware):
    """Middleware for automatic persistence of search findings.
    
    This middleware intercepts tool results from search tools and automatically
    persists findings to the filesystem. This provides a safety net ensuring
    findings survive context truncation even if agents don't explicitly call
    the save_round_findings tool.
    
    The middleware writes to:
    - /findings/auto/{source}_capture_{N}.json - Raw captured data
    - /findings_auto_accumulator.json - Cumulative structured findings
    
    These auto-captured findings complement the explicit findings saved by
    agents using the save_round_findings tool.
    
    Args:
        backend: Backend instance or factory for file operations.
        enabled: Whether auto-capture is enabled. Default True.
        capture_threshold: Minimum references to trigger auto-save. Default 1.
        
    Example:
        ```python
        from novelty_checker.middleware.findings import FindingsPersistenceMiddleware
        from deepagents.backends import FilesystemBackend
        
        backend = FilesystemBackend(root_dir="./")
        middleware = FindingsPersistenceMiddleware(backend=backend)
        
        agent = create_deep_agent(middleware=[middleware])
        ```
    """
    
    state_schema = FindingsState
    
    def __init__(
        self,
        *,
        backend: BACKEND_TYPES,
        enabled: bool = True,
        capture_threshold: int = 1,
    ) -> None:
        """Initialize the findings persistence middleware.
        
        Args:
            backend: Backend instance or factory for file operations.
            enabled: Whether auto-capture is enabled. Default True.
            capture_threshold: Minimum references to trigger auto-save. Default 1.
        """
        self._backend = backend
        self._enabled = enabled
        self._capture_threshold = capture_threshold
        # Per-thread capture counters (thread-safe)
        self._capture_counts: dict[str, int] = {}
        self._counts_lock = threading.Lock()
    
    def _get_backend(self, runtime: Any) -> BackendProtocol:
        """Resolve backend from instance or factory.

        Args:
            runtime: Runtime context for factory functions.

        Returns:
            Resolved backend instance.
        """
        if callable(self._backend):
            return self._backend(runtime)
        return self._backend

    def _next_capture_id(self, runtime: Any) -> int:
        """Get next per-thread capture ID.

        Args:
            runtime: Runtime context to extract thread_id.

        Returns:
            Monotonically increasing capture ID for this thread.
        """
        from src.novelty_checker.backend_factory import extract_thread_id
        thread_id = extract_thread_id(runtime) or "__default__"
        with self._counts_lock:
            count = self._capture_counts.get(thread_id, 0) + 1
            self._capture_counts[thread_id] = count
            return count

    def _capture_from_tool_result(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        tool_result_content: str,
        runtime: Any,
    ) -> None:
        """Extract and persist findings from a tool result.

        Args:
            tool_name: Name of the tool that was called
            tool_args: Arguments passed to the tool
            tool_result_content: String content of the tool result
            runtime: Runtime context for backend resolution
        """
        # Extract references from result
        references = _extract_references_from_result(tool_name, tool_result_content)

        if len(references) < self._capture_threshold:
            _logger.debug(f"Tool {tool_name} returned {len(references)} refs, below threshold")
            return

        # Determine source type
        source_type = _determine_source_type(tool_name)

        # Build capture record
        capture_id = self._next_capture_id(runtime)
        capture_record = {
            "capture_id": capture_id,
            "timestamp": datetime.now().isoformat(),
            "tool_name": tool_name,
            "tool_args": tool_args,
            "source_type": source_type,
            "reference_count": len(references),
            "references": references,
        }

        # Persist to filesystem
        backend = self._get_backend(runtime)

        # Write individual capture file
        # (backend.write() creates parent directories automatically)
        capture_file = f"{AUTO_FINDINGS_DIR}/{source_type}_capture_{capture_id}.json"
        backend.write(capture_file, json.dumps(capture_record, indent=2))

        # Update cumulative accumulator
        self._update_accumulator(backend, capture_record)

        _logger.info(
            f"Auto-captured {len(references)} refs from {tool_name} -> {capture_file}"
        )

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        """Intercept tool results and persist findings from search tools.

        Also triggers finalize backfill when final_report.md is written.

        Args:
            request: Tool call request with call dict, tool, state, and runtime.
            handler: Callable to execute the tool.

        Returns:
            Original tool result unchanged.
        """
        # Execute the tool first
        result = handler(request)

        if not self._enabled:
            return result

        tool_name = request.tool_call.get("name", "")

        # Detect final report write -> trigger backfill
        if tool_name in ("write_file", "edit_file"):
            args = request.tool_call.get("args", {})
            path = args.get("file_path", "") or args.get("path", "")
            if "final_report" in path.lower():
                self._schedule_finalize(request)
            return result

        if tool_name not in SEARCH_TOOLS_TO_CAPTURE:
            return result

        try:
            tool_args = request.tool_call.get("args", {})
            tool_result_content = result.content if isinstance(result, ToolMessage) else str(result)
            self._capture_from_tool_result(
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result_content=tool_result_content,
                runtime=request.runtime,
            )
        except Exception as e:
            _logger.warning(f"FindingsPersistence: Failed to capture from {tool_name}: {e}")

        return result

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        """Async version: intercept tool results and persist findings.

        Also triggers finalize backfill when final_report.md is written.

        Args:
            request: Tool call request with call dict, tool, state, and runtime.
            handler: Async callable to execute the tool.

        Returns:
            Original tool result unchanged.
        """
        # Execute the tool first
        result = await handler(request)

        if not self._enabled:
            return result

        tool_name = request.tool_call.get("name", "")

        # Detect final report write -> trigger backfill.
        # Offload the sync finalize to a worker thread: finalize_session does
        # blocking filesystem I/O (Path.mkdir + open via FilesystemBackend.write),
        # which otherwise stalls the ASGI event loop under `langgraph dev`.
        if tool_name in ("write_file", "edit_file"):
            args = request.tool_call.get("args", {})
            path = args.get("file_path", "") or args.get("path", "")
            if "final_report" in path.lower():
                await asyncio.to_thread(self._schedule_finalize, request)
            return result

        if tool_name not in SEARCH_TOOLS_TO_CAPTURE:
            return result

        try:
            tool_args = request.tool_call.get("args", {})
            tool_result_content = result.content if isinstance(result, ToolMessage) else str(result)
            self._capture_from_tool_result(
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result_content=tool_result_content,
                runtime=request.runtime,
            )
        except Exception as e:
            _logger.warning(f"FindingsPersistence: Failed to capture from {tool_name}: {e}")

        return result
    
    def _update_accumulator(self, backend: BackendProtocol, capture_record: dict) -> None:
        """Update the cumulative accumulator file.
        
        Args:
            backend: Backend for file operations
            capture_record: New capture record to add
        """
        # Try to read existing accumulator. `read_json_from_backend` handles
        # the FilesystemBackend quirks (line-number prefixes, "Error: ..."
        # strings for missing files). Without it, every call here was silently
        # resetting the accumulator on disk.
        from src.novelty_checker.middleware._backend_utils import read_json_from_backend
        accumulator = read_json_from_backend(backend, AUTO_ACCUMULATOR_FILE)
        if accumulator is None:
            accumulator = {
                "version": "1.0",
                "created_at": datetime.now().isoformat(),
                "total_captures": 0,
                "total_references": 0,
                "by_source": {"patent": [], "npl": [], "semantic": [], "citation": [], "other": []},
                "all_references": [],
            }
        
        # Update accumulator
        accumulator["total_captures"] += 1
        accumulator["total_references"] += capture_record["reference_count"]
        accumulator["last_updated"] = datetime.now().isoformat()
        
        # Add to source-specific list
        source_type = capture_record["source_type"]
        if source_type not in accumulator["by_source"]:
            accumulator["by_source"][source_type] = []
        accumulator["by_source"][source_type].append({
            "capture_id": capture_record["capture_id"],
            "tool_name": capture_record["tool_name"],
            "count": capture_record["reference_count"],
            "timestamp": capture_record["timestamp"],
        })
        
        # Add references to master list (deduplicated by publication number)
        existing_pub_nums = {
            ref.get("publication_number", "") 
            for ref in accumulator["all_references"]
        }
        for ref in capture_record["references"]:
            pub_num = ref.get("publication_number", "")
            if pub_num and pub_num not in existing_pub_nums:
                accumulator["all_references"].append(ref)
                existing_pub_nums.add(pub_num)
        
        # Write updated accumulator. Swallow + log write failures so a
        # backend glitch doesn't crash the middleware mid-tool-call and
        # lose the tool result. Losing one capture write is recoverable
        # (next tool call re-reads and retries); crashing the graph is not.
        try:
            backend.write(AUTO_ACCUMULATOR_FILE, json.dumps(accumulator, indent=2))
        except Exception:
            _logger.warning(
                "FindingsPersistenceMiddleware: failed to write accumulator to %s "
                "(total_captures=%d, total_references=%d). Next capture will retry.",
                AUTO_ACCUMULATOR_FILE,
                accumulator.get("total_captures", 0),
                accumulator.get("total_references", 0),
                exc_info=True,
            )


    # ------------------------------------------------------------------
    # Session finalization (backfill from filesystem)
    # ------------------------------------------------------------------

    def _schedule_finalize(self, request: ToolCallRequest) -> None:
        """Run finalize_session if not already done for this thread."""
        from src.novelty_checker.backend_factory import extract_thread_id

        thread_id = extract_thread_id(request.runtime) or "__default__"
        finalize_key = f"_finalized_{thread_id}"

        with self._counts_lock:
            if getattr(self, finalize_key, False):
                return
            setattr(self, finalize_key, True)

        try:
            self.finalize_session(request.runtime)
        except Exception as e:  # noqa: BLE001
            _logger.warning(f"FindingsPersistence: finalize_session failed: {e}")

    def finalize_session(self, runtime: Any) -> None:
        """Backfill findings_auto_accumulator.json from filesystem.

        Because search tools are called by subagents (not the orchestrator),
        real-time wrap_tool_call capture cannot observe them. This method
        reconstructs the accumulator from findings markdown files written
        by subagents.
        """
        backend = self._get_backend(runtime)

        # Parse all findings markdown files
        # Don't break on empty rounds — subagents may skip round numbers
        # (e.g., round_1.md has no table but patent_round_2.md does)
        all_refs: list[dict[str, Any]] = []
        sources = ("patent", "semantic", "npl", "citations")
        max_rounds = 10

        for round_num in range(1, max_rounds + 1):
            for source in sources:
                path = f"/findings/{source}_round_{round_num}.md"
                refs = self._parse_findings_markdown(backend, path)
                if refs:
                    for ref in refs:
                        ref["source_type"] = source
                        ref["round_number"] = round_num
                    all_refs.extend(refs)

            # Also try generic round_N.md naming
            path = f"/findings/round_{round_num}.md"
            refs = self._parse_findings_markdown(backend, path)
            if refs:
                for ref in refs:
                    ref["source_type"] = "mixed"
                    ref["round_number"] = round_num
                all_refs.extend(refs)

        if not all_refs:
            _logger.debug("FindingsPersistence: no findings markdown files to backfill from")
            return

        # Deduplicate by publication number
        seen: set[str] = set()
        unique_refs: list[dict[str, Any]] = []
        for ref in all_refs:
            pub = ref.get("publication_number", "")
            if pub and pub not in seen:
                seen.add(pub)
                unique_refs.append(ref)

        # Build accumulator structure
        accumulator = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "total_captures": len(unique_refs),
            "total_references": len(unique_refs),
            "backfilled": True,
            "by_source": {},
            "all_references": unique_refs,
        }

        # Group by source
        for ref in unique_refs:
            src = ref.get("source_type", "other")
            if src not in accumulator["by_source"]:
                accumulator["by_source"][src] = []
            accumulator["by_source"][src].append({
                "publication_number": ref.get("publication_number", ""),
                "triage_label": ref.get("triage_label"),
                "round": ref.get("round_number"),
            })

        backend.write(AUTO_ACCUMULATOR_FILE, json.dumps(accumulator, indent=2))
        _logger.info(
            f"FindingsPersistence: backfilled {len(unique_refs)} refs "
            f"into {AUTO_ACCUMULATOR_FILE}"
        )

    @staticmethod
    def _parse_findings_markdown(
        backend: Any, path: str
    ) -> list[dict[str, Any]] | None:
        """Parse a findings markdown file and extract refs from table rows.

        Returns list of dicts with publication_number, triage_label, title.
        Returns None if file can't be read.
        """
        try:
            content = backend.read(path)
            if not content or content.startswith("Error:"):
                return None
        except Exception:
            return None

        # Patent number pattern
        pub_re = re.compile(
            r"\b([A-Z]{2}\d{5,}[A-Z]?\d?)\b"
        )

        refs: list[dict[str, Any]] = []
        for line in content.split("\n"):
            if "|" not in line:
                continue

            cells = [c.strip() for c in line.split("|")]
            cells = [c for c in cells if c]

            # Skip separator rows
            if not cells or all(set(c) <= set("-: ") for c in cells):
                continue

            # Skip header rows
            if cells and any(
                h in cells[0].lower()
                for h in ("publication", "pub", "feature", "level", "status")
            ):
                continue

            # Extract pub number from first 2 cells
            pub = None
            for cell in cells[:2]:
                match = pub_re.search(cell)
                if match:
                    pub = match.group(1)
                    break

            if not pub:
                continue

            # Triage label: standalone A/B/C in a cell
            label = None
            for cell in cells:
                stripped = cell.strip("*").strip()
                if stripped in ("A", "B", "C"):
                    label = stripped
                    break

            # Title: usually the second cell (after pub number)
            title = None
            if len(cells) >= 2:
                for cell in cells[1:3]:
                    if not pub_re.search(cell) and cell.strip("*").strip() not in ("A", "B", "C"):
                        title = cell.strip("*").strip()
                        break

            refs.append({
                "publication_number": pub,
                "triage_label": label,
                "title": title,
            })

        return refs if refs else None


# =============================================================================
# Exports
# =============================================================================

__all__ = ["FindingsPersistenceMiddleware", "FindingsState"]
