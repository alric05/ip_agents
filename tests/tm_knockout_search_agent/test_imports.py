"""Import smoke tests for the TM knockout search agent skeleton."""

from __future__ import annotations

import importlib


MODULES = [
    "src.tm_knockout_search_agent",
    "src.tm_knockout_search_agent.prompts",
    "src.tm_knockout_search_agent.state",
    "src.tm_knockout_search_agent.deep_agent",
    "src.tm_knockout_search_agent.main",
    "src.tm_knockout_search_agent.middleware",
    "src.tm_knockout_search_agent.middleware.stage_guard",
    "src.tm_knockout_search_agent.services",
    "src.tm_knockout_search_agent.services.query_planner",
    "src.tm_knockout_search_agent.services.risk_assessment",
    "src.tm_knockout_search_agent.services.stopping",
    "src.tm_knockout_search_agent.services.workflow",
    "src.tm_knockout_search_agent.studio",
    "src.tm_knockout_search_agent.tools",
    "src.tm_knockout_search_agent.tools.adapters",
    "src.tm_knockout_search_agent.tools.compumark",
    "src.tm_knockout_search_agent.tools.registry",
    "src.tm_knockout_search_agent.tools.web_search",
]


def test_key_modules_import_cleanly() -> None:
    for module_name in MODULES:
        module = importlib.import_module(module_name)
        assert module is not None


def test_factory_is_available() -> None:
    module = importlib.import_module("src.tm_knockout_search_agent.deep_agent")

    assert callable(module.create_tm_knockout_search_agent)
    assert callable(module.create_knockout_search_agent)
    assert callable(module.check_tm_knockout)
