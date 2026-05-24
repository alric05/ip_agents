"""Command-line entry point for the TM knockout search agent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from src.tm_knockout_search_agent.deep_agent import (
    TM_KNOCKOUT_AGENT_NAME,
    check_tm_knockout,
)


def create_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    parser = argparse.ArgumentParser(
        description="First-pass trademark knockout screening",
    )
    parser.add_argument("--interactive", action="store_true", help="Prompt for inputs")
    parser.add_argument("--brand", help="Proposed brand name")
    parser.add_argument(
        "--countries",
        help='Comma-separated countries or regional systems, e.g. "US, EUIPO"',
    )
    parser.add_argument("--classes", help='Comma-separated Nice classes, e.g. "3,35"')
    parser.add_argument("--goods", help="Goods/services description")
    parser.add_argument("--business-context", help="Optional business context")
    parser.add_argument("--model", help="Model identifier to store in run metadata")
    parser.add_argument("--thread-id", help="Optional thread id")
    parser.add_argument("--session-id", help="Optional deterministic session id")
    parser.add_argument("--language", default="English", help="Output language")
    parser.add_argument("--max-results-per-query", type=int, default=25)
    parser.add_argument("--max-candidates-to-normalize", type=int, default=100)
    parser.add_argument("--max-candidates-to-surface-in-report", type=int, default=10)
    parser.add_argument(
        "--include-web-search",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include web/common-law search in the deterministic plan",
    )
    parser.add_argument(
        "--include-inactive-contextual",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include inactive/dead contextual search in the deterministic plan",
    )
    parser.add_argument(
        "--sessions-base-dir",
        default="sessions",
        help="Base directory for session artifacts",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full machine-readable JSON output",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI."""
    parser = create_parser()
    args = parser.parse_args(argv)
    if args.interactive:
        _fill_interactive_args(args)
    if not args.brand:
        parser.error("--brand is required unless --interactive supplies it")
    if not args.countries:
        parser.error("--countries is required unless --interactive supplies it")
    if not args.classes and not args.goods:
        parser.error("provide --classes and/or --goods")

    result = check_tm_knockout(
        brand=args.brand,
        countries=args.countries,
        classes=args.classes,
        goods=args.goods,
        business_context=args.business_context,
        model=args.model,
        thread_id=args.thread_id,
        session_id=args.session_id,
        max_results_per_query=args.max_results_per_query,
        max_candidates_to_normalize=args.max_candidates_to_normalize,
        max_candidates_to_surface_in_report=args.max_candidates_to_surface_in_report,
        include_web_search=args.include_web_search,
        include_inactive_contextual=args.include_inactive_contextual,
        language=args.language,
        sessions_base_dir=Path(args.sessions_base_dir),
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(_format_summary(result))
    return 0


def _fill_interactive_args(args: argparse.Namespace) -> None:
    if not args.brand:
        args.brand = input("Brand name: ").strip()
    if not args.countries:
        args.countries = input("Countries or regional systems: ").strip()
    if not args.classes:
        args.classes = input("Nice classes (optional): ").strip() or None
    if not args.goods:
        args.goods = input("Goods/services (optional): ").strip() or None


def _format_summary(result: dict) -> str:
    risk = result["risk_assessment"]["overall_risk_label"]
    stop = result["stopping_decision"]["decision"]
    session_id = result["session_id"]
    groups = result["search_plan"]["query_groups"]
    next_groups = result["stopping_decision"].get("next_query_group_ids", [])
    lines = [
        f"{TM_KNOCKOUT_AGENT_NAME}",
        f"Session: {session_id}",
        f"Overall risk: {risk}",
        f"Stopping decision: {stop}",
        f"Planned query groups: {len(groups)}",
        f"Next query groups: {', '.join(next_groups) if next_groups else 'None'}",
        "Live API calls: false",
    ]
    if result.get("report_markdown"):
        lines.append("")
        lines.append(result["report_markdown"])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["create_parser", "main"]
