"""Search Strategy Adequacy scorer (Tier-2, deterministic).

Evaluates whether the agent used a comprehensive search strategy
using an 8-item checklist per eval_metrics_strategy.md §3.4.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from src.novelty_checker.evaluation.scorers._base import NoveltyBaseMetric, ScorerResult

_logger = logging.getLogger(__name__)


def _extract_cpc_codes(text: str) -> set[str]:
    """Extract CPC/IPC classification codes from text.

    Matches patterns like A61K, H04L65/00, G06F3/01, etc.
    """
    pattern = r"\b([A-H]\d{2}[A-Z]?\d{0,4}(?:/\d{1,6})?)\b"
    return {m.upper() for m in re.findall(pattern, text)}


def _extract_query_texts(args: dict) -> list[str]:
    """Extract all query text strings from single or batch tool args."""
    texts: list[str] = []
    for key in ("query", "search_query"):
        val = args.get(key, "")
        if isinstance(val, str) and val.strip():
            texts.append(val.strip())
    for key in ("queries",):
        val = args.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item.strip():
                    texts.append(item.strip())
    for key in ("semantic_queries", "keyword_queries", "patent_queries", "npl_queries"):
        val = args.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    qt = item.get("query_text", "")
                    if isinstance(qt, str) and qt.strip():
                        texts.append(qt.strip())
    return texts


def _get_tool_calls_from_trace(eval_trace: dict) -> dict[str, int]:
    """Aggregate tool_calls_by_name across all stages."""
    counts: dict[str, int] = {}
    stage_summary = eval_trace.get("stage_summary", {})
    for _phase, stage in stage_summary.items():
        if isinstance(stage, dict):
            for tool_name, count in stage.get("tool_calls_by_name", {}).items():
                counts[tool_name] = counts.get(tool_name, 0) + count
    return counts


def _check_patent_search(search_queries: list[dict]) -> bool:
    """Check if agent used patent keyword search."""
    patent_tools = {"patent_keyword_search", "batch_patent_search", "batch_unified_search"}
    return any(q.get("tool_name") in patent_tools for q in search_queries)


def _check_semantic_search(search_queries: list[dict]) -> bool:
    """Check if agent used semantic patent search."""
    semantic_tools = {"semantic_patent_search", "batch_semantic_search", "batch_unified_search"}
    return any(q.get("tool_name") in semantic_tools for q in search_queries)


def _check_min_queries(search_queries: list[dict]) -> bool:
    """Check if agent ran at least 3 search queries."""
    return len(search_queries) >= 3


def _check_think_tool(eval_trace: dict) -> bool:
    """Check if agent used think_tool during research."""
    tool_counts = _get_tool_calls_from_trace(eval_trace)
    if tool_counts.get("think_tool", 0) >= 1:
        return True
    # Fallback: check checklist
    checklist = eval_trace.get("checklist", {})
    checks = checklist.get("checks", {})
    return bool(checks.get("think_tool_used"))


def _check_coverage_evaluated(eval_trace: dict) -> bool:
    """Check if agent evaluated coverage."""
    tool_counts = _get_tool_calls_from_trace(eval_trace)
    if tool_counts.get("evaluate_coverage", 0) >= 1:
        return True
    checklist = eval_trace.get("checklist", {})
    checks = checklist.get("checks", {})
    return bool(checks.get("coverage_evaluated"))


def _check_findings_persisted(eval_trace: dict) -> bool:
    """Check if agent persisted findings."""
    tool_counts = _get_tool_calls_from_trace(eval_trace)
    if tool_counts.get("save_round_findings", 0) >= 1:
        return True
    checklist = eval_trace.get("checklist", {})
    checks = checklist.get("checks", {})
    return bool(checks.get("findings_persisted"))


def _check_min_rounds(eval_trace: dict) -> bool:
    """Check if agent completed at least 2 research rounds."""
    telemetry = eval_trace.get("telemetry") or {}
    return telemetry.get("total_rounds", 0) >= 2


def _check_cpc_coverage(
    search_queries: list[dict], gt_search_strategy: str
) -> tuple[bool, set[str], set[str]]:
    """Check if agent searched expected CPC codes.

    Returns (passed, searched_cpcs, expected_cpcs).
    """
    expected_cpcs = _extract_cpc_codes(gt_search_strategy)
    if not expected_cpcs:
        return True, set(), set()

    searched_cpcs: set[str] = set()
    for q in search_queries:
        args = q.get("args") or {}
        if not isinstance(args, dict):
            continue
        for text in _extract_query_texts(args):
            searched_cpcs |= _extract_cpc_codes(text)
        for key in ("cpc_codes", "classification"):
            val = args.get(key, "")
            if isinstance(val, str):
                searched_cpcs |= _extract_cpc_codes(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        searched_cpcs |= _extract_cpc_codes(item)

    # Check if at least half of expected codes were searched (prefix match)
    matched = set()
    for expected in expected_cpcs:
        prefix = expected[:4]
        for searched in searched_cpcs:
            if searched.startswith(prefix):
                matched.add(expected)
                break

    passed = len(matched) >= len(expected_cpcs) * 0.5 if expected_cpcs else True
    return passed, searched_cpcs, expected_cpcs


class SearchStrategyMetric(NoveltyBaseMetric):
    """Evaluates comprehensiveness of agent's search strategy.

    8-item checklist per eval_metrics_strategy.md §3.4:
    1. Used patent keyword search
    2. Used semantic search
    3. Ran at least 3 search queries
    4. Used think_tool
    5. Evaluated coverage
    6. Persisted findings
    7. Completed at least 2 research rounds
    8. Searched expected CPC codes

    Score = fraction of checklist items satisfied.
    Target: >= 5/8 (0.625)
    """

    def __init__(self, threshold: float = 0.625) -> None:
        super().__init__(
            metric_name="search_strategy_adequacy",
            threshold=threshold,
            scorer_type="deterministic",
        )

    def _compute(
        self,
        eval_trace: dict[str, Any],
        ground_truth: dict[str, Any],
        session_path: Path,
        config: dict[str, Any] | None = None,
    ) -> ScorerResult:
        telemetry = eval_trace.get("telemetry") or {}
        search_queries = telemetry.get("search_queries", [])
        # gt_strategy = ground_truth.get("search_strategy", "")
        gt_strategy_raw = ground_truth.get("search_strategy", "")
        if isinstance(gt_strategy_raw, dict):
            gt_strategy = gt_strategy_raw.get("overall_strategy_narrative") or ""
            for code_entry in gt_strategy_raw.get("expected_cpc_ipc_codes", []):
                code = code_entry.get("code", "") if isinstance(code_entry, dict) else str(code_entry)
                gt_strategy += " " + code
        else:
            gt_strategy = str(gt_strategy_raw) if gt_strategy_raw else ""

        checklist: dict[str, bool] = {}
        details: dict[str, str] = {}

        # 1. Patent search
        checklist["patent_search"] = _check_patent_search(search_queries)
        details["patent_search"] = (
            "Used patent keyword search" if checklist["patent_search"]
            else "No patent keyword search found"
        )

        # 2. Semantic search
        checklist["semantic_search"] = _check_semantic_search(search_queries)
        details["semantic_search"] = (
            "Used semantic search" if checklist["semantic_search"]
            else "No semantic search found"
        )

        # 3. Min queries
        checklist["min_queries"] = _check_min_queries(search_queries)
        details["min_queries"] = (
            f"{len(search_queries)} search queries (minimum: 3)"
            if checklist["min_queries"]
            else f"Only {len(search_queries)} search queries (minimum: 3)"
        )

        # 4. Think tool
        checklist["think_tool_used"] = _check_think_tool(eval_trace)
        details["think_tool_used"] = (
            "think_tool was used" if checklist["think_tool_used"]
            else "think_tool was not used"
        )

        # 5. Coverage evaluated
        checklist["coverage_evaluated"] = _check_coverage_evaluated(eval_trace)
        details["coverage_evaluated"] = (
            "Coverage was evaluated" if checklist["coverage_evaluated"]
            else "Coverage was not evaluated"
        )

        # 6. Findings persisted
        checklist["findings_persisted"] = _check_findings_persisted(eval_trace)
        details["findings_persisted"] = (
            "Findings were persisted" if checklist["findings_persisted"]
            else "Findings were not persisted"
        )

        # 7. Min rounds
        checklist["min_rounds"] = _check_min_rounds(eval_trace)
        total_rounds = telemetry.get("total_rounds", 0)
        details["min_rounds"] = (
            f"{total_rounds} research rounds (minimum: 2)"
            if checklist["min_rounds"]
            else f"Only {total_rounds} research round(s) (minimum: 2)"
        )

        # 8. CPC coverage
        cpc_ok, searched, expected = _check_cpc_coverage(search_queries, gt_strategy)
        checklist["cpc_coverage"] = cpc_ok
        details["cpc_coverage"] = (
            f"Searched {len(searched)} CPC codes, expected {len(expected)}"
        )

        satisfied = sum(1 for v in checklist.values() if v)
        total = len(checklist)
        score = satisfied / total if total > 0 else 0.0

        failures = [
            {
                "type": "missing_search_strategy",
                "severity": "major",
                "evidence": details[name],
                "affected_element": name,
            }
            for name, passed in checklist.items()
            if not passed
        ]

        return ScorerResult(
            metric_name="search_strategy_adequacy",
            score=round(score, 4),
            confidence=1.0 if search_queries else 0.3,
            passed=score >= self.threshold,
            threshold=self.threshold,
            failures=failures,
            evidence={
                "checklist": checklist,
                "details": details,
                "satisfied": satisfied,
                "total": total,
                "total_search_queries": len(search_queries),
                "searched_cpc_codes": sorted(searched),
                "expected_cpc_codes": sorted(expected),
            },
            scorer_type="deterministic",
        )
