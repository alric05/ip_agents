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


def test_tm_langgraph_entrypoint_handles_brand_only_without_live_calls() -> None:
    module = importlib.import_module("src.tm_knockout_search_agent.studio")

    result_state = module.graph.invoke({"brand": "KLYRA"})

    assert result_state["result"]["status"] == "NEEDS_INPUT"
    assert result_state["result"]["missing_fields"] == [
        "countries or jurisdictions",
        "classes and/or goods",
    ]
    assert result_state["result"]["live_api_calls"] is False


def test_tm_langgraph_entrypoint_can_attach_mocked_llm_review(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from langchain_core.messages import AIMessage

    class FakeLLM:
        def invoke(self, messages):
            assert "deterministic TM knockout artifacts" in messages[-1].content
            return AIMessage(content="Mock LLM review: LOW risk.")

    import src.config.llm as llm_config

    monkeypatch.setattr(llm_config, "get_llm", lambda: FakeLLM())
    monkeypatch.setattr(
        llm_config,
        "get_active_backend_info",
        lambda: {
            "provider": "fake",
            "model": "fake-model",
            "api_version": "test",
        },
    )

    module = importlib.import_module("src.tm_knockout_search_agent.studio")
    result_state = module.graph.invoke(
        {
            "brand": "KLYRA",
            "countries": "US",
            "goods": "cosmetics and skincare",
            "completed_stages": [
                "EXACT_ACTIVE",
                "SIMILAR_ACTIVE",
                "WEB_COMMON_LAW",
            ],
            "session_id": "mock-llm-review",
            "sessions_base_dir": str(tmp_path / "sessions"),
            "use_llm": True,
        }
    )

    assert result_state["result"]["llm_response"] == "Mock LLM review: LOW risk."
    assert result_state["result"]["live_llm_call"] is True
    assert (
        tmp_path
        / "sessions"
        / "tm_knockout_search_agent"
        / "mock-llm-review"
        / "llm_review.json"
    ).exists()


def test_tm_langgraph_entrypoint_records_mocked_llm_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class FailingLLM:
        def invoke(self, messages):
            raise RuntimeError("private endpoint required")

    import src.config.llm as llm_config

    monkeypatch.setattr(llm_config, "get_llm", lambda: FailingLLM())
    monkeypatch.setattr(
        llm_config,
        "get_active_backend_info",
        lambda: {
            "provider": "fake",
            "model": "fake-model",
            "api_version": "test",
        },
    )

    module = importlib.import_module("src.tm_knockout_search_agent.studio")
    result_state = module.graph.invoke(
        {
            "brand": "KLYRA",
            "countries": "US",
            "goods": "cosmetics and skincare",
            "completed_stages": [
                "EXACT_ACTIVE",
                "SIMILAR_ACTIVE",
                "WEB_COMMON_LAW",
            ],
            "session_id": "mock-llm-error",
            "sessions_base_dir": str(tmp_path / "sessions"),
            "use_llm": True,
        }
    )

    assert result_state["result"]["live_llm_call"] is False
    assert result_state["result"]["live_llm_call_attempted"] is True
    assert "private endpoint required" in result_state["result"]["llm_error"]
    assert (
        tmp_path
        / "sessions"
        / "tm_knockout_search_agent"
        / "mock-llm-error"
        / "llm_review.json"
    ).exists()
