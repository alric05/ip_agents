"""CLI import and parser tests for TM knockout search."""

from __future__ import annotations

import importlib
from pathlib import Path

from src.tm_knockout_search_agent import main as cli


def test_main_module_imports_without_live_credentials() -> None:
    module = importlib.import_module("src.tm_knockout_search_agent.main")

    assert module is not None
    assert callable(module.main)
    assert callable(module.create_parser)


def test_cli_parser_supports_direct_brand_arguments() -> None:
    parser = cli.create_parser()

    args = parser.parse_args(
        [
            "--brand",
            "KLYRA",
            "--countries",
            "US, EUIPO",
            "--goods",
            "cosmetics and skincare",
            "--live-compumark",
        ]
    )

    assert args.brand == "KLYRA"
    assert args.countries == "US, EUIPO"
    assert args.goods == "cosmetics and skincare"
    assert args.include_web_search is True
    assert args.live_compumark is True


def test_cli_main_runs_without_live_api_calls(tmp_path: Path, capsys) -> None:
    exit_code = cli.main(
        [
            "--brand",
            "KLYRA",
            "--countries",
            "US, EUIPO",
            "--classes",
            "3,35",
            "--session-id",
            "cli-test",
            "--sessions-base-dir",
            str(tmp_path / "sessions"),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "tm_knockout_search_agent" in output
    assert "Live API calls: false" in output
    assert (tmp_path / "sessions" / "tm_knockout_search_agent" / "cli-test").exists()
