#!/usr/bin/env python3
"""Standalone Derwent tool test — bypasses the agent.

Reads DERWENT_JWT_TOKEN and DERWENT_API_BASE_URL from .env, patches the
LangGraph config so the tools see the JWT, and calls the Derwent tools
directly to verify:
  1. Keyword search (search_derwent_patents_fld)
  2. Citation search (search_derwent_citations)

Run:
    python scripts/test_derwent_standalone.py

Optional CLI overrides:
    python scripts/test_derwent_standalone.py --query "CTB=(UV NEAR3 fluorescence);"
    python scripts/test_derwent_standalone.py --patent "US3256182A_19660614"
    python scripts/test_derwent_standalone.py --size 5
    python scripts/test_derwent_standalone.py --skip-citations

Exit codes:
    0 — all requested calls succeeded (got results or explicit empty)
    1 — any call returned an auth/API error
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch


# Ensure we run from project root so relative imports work
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# Load .env before importing anything that reads settings
from dotenv import load_dotenv  # noqa: E402

load_dotenv(_PROJECT_ROOT / ".env")


# =============================================================================
# Helpers
# =============================================================================

def _fmt(s: str, max_len: int = 300) -> str:
    """Truncate strings for display."""
    if s is None:
        return "—"
    s = str(s).strip()
    return s[:max_len] + ("…" if len(s) > max_len else "")


def _print_header(title: str) -> None:
    print()
    print("=" * 78)
    print(f" {title}")
    print("=" * 78)


def _print_patent(i: int, p: dict) -> None:
    print(f"\n[{i}] {p.get('publication_number', 'N/A')}   "
          f"relevance={p.get('relevance_score', 0):.3f}")
    print(f"    Title:          {_fmt(p.get('title') or p.get('dwpi_title'), 200)}")
    if p.get('dwpi_title') and p.get('dwpi_title') != p.get('title'):
        print(f"    DWPI Title:     {_fmt(p.get('dwpi_title'), 200)}")
    print(f"    Priority Date:  {p.get('priority_date') or 'N/A'}")
    print(f"    Assignee:       {p.get('assignee') or 'N/A'}")
    if p.get('inventors'):
        print(f"    Inventors:      {', '.join(p['inventors'][:3])}"
              + (f" (+{len(p['inventors']) - 3} more)" if len(p['inventors']) > 3 else ""))
    if p.get('dwpi_abstract_novelty'):
        print(f"    DWPI Novelty:   {_fmt(p.get('dwpi_abstract_novelty'))}")
    elif p.get('abstract'):
        print(f"    Abstract:       {_fmt(p.get('abstract'))}")


def _print_citation(i: int, c: dict) -> None:
    print(f"  [{i}] {c.get('publication_number', 'N/A')}  |  "
          f"{_fmt(c.get('title') or c.get('dwpi_title'), 90)}")
    if c.get('assignee'):
        print(f"      Assignee: {c.get('assignee')}  |  Priority: {c.get('priority_date') or 'N/A'}")


# =============================================================================
# Test runners
# =============================================================================

def run_keyword_search(query: str, size: int) -> bool:
    """Test search_derwent_patents_fld. Returns True on success."""
    from src.tools.clients.derwent import _derwent_fld_search

    _print_header(f"TEST 1 — Keyword Search (search_derwent_patents_fld)")
    print(f"Query:       {query}")
    print(f"Size:        {size}")

    result = _derwent_fld_search(query, size=size)

    if isinstance(result, str):
        print(f"\n❌ ERROR: {result}")
        return False

    if not result:
        print("\n⚠️  No results (query is valid but returned 0 patents)")
        return True

    print(f"\n✅ Received {len(result)} patent(s):")
    for i, p in enumerate(result, 1):
        _print_patent(i, p)
    return True


def run_citation_search(patent_id: str, max_citations: int) -> bool:
    """Test search_derwent_citations. Returns True on success."""
    from src.tools.clients.derwent import _derwent_citation_search

    _print_header(f"TEST 2 — Citation Search (search_derwent_citations)")
    print(f"Patent ID:       {patent_id}")
    print(f"Max citations:   {max_citations}")

    result = _derwent_citation_search(patent_id, max_citations=max_citations)

    if isinstance(result, dict) and "error" in result:
        print(f"\n❌ ERROR: {result['error']}")
        return False

    # Handle list (multiple patents) vs dict (single patent)
    if isinstance(result, list):
        if not result:
            print("\n⚠️  Empty result list")
            return True
        result = result[0]

    print(f"\n✅ Patent: {result.get('patent_number', patent_id)}")
    print(f"   Forward citations (cite this patent):  {result.get('total_forward_citations', 0)}")
    print(f"   Backward citations (cited by it):      {result.get('total_backward_citations', 0)}")

    fwd = result.get('forward_citations', [])
    bwd = result.get('backward_citations', [])

    if fwd:
        print(f"\n   Forward citations (showing up to 5 of {len(fwd)}):")
        for i, c in enumerate(fwd[:5], 1):
            _print_citation(i, c)

    if bwd:
        print(f"\n   Backward citations (showing up to 5 of {len(bwd)}):")
        for i, c in enumerate(bwd[:5], 1):
            _print_citation(i, c)

    if not fwd and not bwd:
        print("\n   (No citations returned)")

    return True


# =============================================================================
# Main
# =============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="Standalone Derwent tool test")
    parser.add_argument(
        "--query",
        default="CTB=(polymer NEAR5 degradation);",
        help="Derwent query for the keyword search test",
    )
    parser.add_argument(
        "--patent",
        default="US3256182A_19660614",
        help="Patent ID for the citation search test",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=3,
        help="Max results for the keyword search (default: 3)",
    )
    parser.add_argument(
        "--max-citations",
        type=int,
        default=20,
        help="Max citations to retrieve (default: 20)",
    )
    parser.add_argument("--skip-keyword", action="store_true", help="Skip keyword search test")
    parser.add_argument("--skip-citations", action="store_true", help="Skip citation search test")
    args = parser.parse_args()

    # --- Preflight ---
    jwt = os.environ.get("DERWENT_JWT_TOKEN")
    if not jwt:
        print("❌ DERWENT_JWT_TOKEN not set in environment.\n"
              "   Add it to .env or export it before running this script.")
        return 1

    base_url = os.environ.get("DERWENT_API_BASE_URL", "https://api.clarivate.com")

    _print_header("Derwent Standalone Test — preflight")
    print(f"Base URL:      {base_url}")
    print(f"JWT length:    {len(jwt)} chars")
    print(f"JWT preview:   {jwt[:30]}…{jwt[-20:]}")

    # --- Patch get_config so the tools find the JWT ---
    # The tools read from get_config()["configurable"]["jwt_token"]. In production
    # this is injected by server.py; here we patch it directly.
    mock_config = {"configurable": {"jwt_token": jwt}}

    results = {}
    with patch("src.tools.clients.derwent.get_config", return_value=mock_config):
        if not args.skip_keyword:
            try:
                results["keyword"] = run_keyword_search(args.query, args.size)
            except Exception as e:
                print(f"\n❌ Keyword search raised exception: {type(e).__name__}: {e}")
                results["keyword"] = False

        if not args.skip_citations:
            try:
                results["citations"] = run_citation_search(args.patent, args.max_citations)
            except Exception as e:
                print(f"\n❌ Citation search raised exception: {type(e).__name__}: {e}")
                results["citations"] = False

    # --- Summary ---
    _print_header("Summary")
    for name, ok in results.items():
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status}  —  {name}")

    all_ok = all(results.values()) if results else False
    print()
    if all_ok:
        print("🎉 All requested tests succeeded — the JWT works with the Derwent API!")
        return 0
    else:
        print("⚠️  One or more tests failed — see errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
