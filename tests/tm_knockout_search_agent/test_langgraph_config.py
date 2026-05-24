"""LangGraph registration smoke tests for the TM knockout assistant."""

from __future__ import annotations

import importlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_langgraph_json_registers_tm_assistant_without_changing_novelty_checker() -> None:
    config = json.loads((REPO_ROOT / "langgraph.json").read_text(encoding="utf-8"))

    assert config["graphs"]["novelty_checker"] == "./studio.py:graph"
    assert (
        config["graphs"]["tm_knockout_search_agent"]
        == "./src/tm_knockout_search_agent/studio.py:graph"
    )


def test_tm_langgraph_entrypoint_imports_and_invokes(tmp_path: Path) -> None:
    module = importlib.import_module("src.tm_knockout_search_agent.studio")

    assert callable(module.create_tm_knockout_search_graph)
    assert callable(module.graph.invoke)

    result_state = module.graph.invoke(
        {
            "brand": "KLYRA",
            "countries": "US, EUIPO",
            "classes": "3",
            "completed_stages": [
                "EXACT_ACTIVE",
                "SIMILAR_ACTIVE",
                "WEB_COMMON_LAW",
            ],
            "session_id": "langgraph-smoke",
            "sessions_base_dir": str(tmp_path / "sessions"),
        }
    )

    assert result_state["result"]["agent_name"] == "tm_knockout_search_agent"
    assert result_state["result"]["live_api_calls"] is False
    assert result_state["result"]["criteria"]["brand_name"] == "KLYRA"


def test_tm_langgraph_entrypoint_handles_missing_input_without_live_calls() -> None:
    module = importlib.import_module("src.tm_knockout_search_agent.studio")

    result_state = module.graph.invoke({})

    assert result_state["result"]["status"] == "NEEDS_INPUT"
    assert result_state["result"]["live_api_calls"] is False
