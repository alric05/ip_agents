"""End-to-end SSE-sequence test for ``POST /chat/stream``.

Stubs the LangGraph and the Derwent JWT pre-flight so the test runs in
under a second and verifies the A2UI event ordering.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

import server as server_module


@pytest.fixture
def stub_app(monkeypatch, tmp_path):
    """Replace JWT preflight + graph + backend factory on the live FastAPI app."""

    monkeypatch.setattr(server_module, "check_derwent_jwt", lambda token: None)

    class _StubGraph:
        async def astream_events(self, payload, config, version):
            # Minimal sequence: orchestrator thinks → patent_keyword_search runs.
            yield {
                "event": "on_chat_model_start",
                "metadata": {"langgraph_node": "agent"},
                "data": {},
            }
            yield {
                "event": "on_tool_start",
                "name": "patent_keyword_search",
                "metadata": {"langgraph_node": "agent"},
                "data": {},
            }
            yield {
                "event": "on_tool_end",
                "name": "patent_keyword_search",
                "metadata": {"langgraph_node": "agent"},
                "data": {},
            }

    class _StubBackend:
        def read(self, path: str):
            return "Error: not found"

    class _StubFactory:
        _cache: dict = {}
        _sessions_dir: Path = tmp_path

    server_module.api.state.graph = _StubGraph()
    server_module.api.state.backend_factory = _StubFactory()
    server_module.api.state.sessions_dir = tmp_path
    return server_module.api


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    event_type = None
    data_buf: list[str] = []
    for raw in body.splitlines():
        line = raw.rstrip("\r")
        if not line:
            if event_type is not None:
                data_str = "\n".join(data_buf)
                try:
                    parsed = json.loads(data_str) if data_str else {}
                except json.JSONDecodeError:
                    parsed = {"_raw": data_str}
                events.append((event_type, parsed))
            event_type = None
            data_buf = []
            continue
        if line.startswith("event:"):
            event_type = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_buf.append(line[len("data:"):].lstrip())
    return events


@pytest.mark.asyncio
async def test_stream_emits_a2ui_envelope(stub_app):
    transport = httpx.ASGITransport(app=stub_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream(
            "POST",
            "/chat/stream",
            json={"message": "anything"},
            headers={"Accept": "text/event-stream"},
        ) as resp:
            assert resp.status_code == 200
            body = await resp.aread()

    events = _parse_sse(body.decode())
    types = [e[0] for e in events]

    # Sequence shape: metadata first, then 1+ stage_data events, then done.
    assert types[0] == "metadata"
    assert types[-1] == "done"
    assert "error" not in types

    # All non-control events should be stage_data.
    a2ui = [e for e in events if e[0] == "stage_data"]
    assert a2ui, "Expected at least one stage_data event"

    components = [d["stage_data"]["component"] for _, d in a2ui]
    # During scoping (default for empty backend), tool/node activity becomes
    # agentActivityBubble events.
    assert "agentActivityBubble" in components

    # Every stage_data event must carry the A2UI envelope.
    for _, payload in a2ui:
        assert payload["stage"] in {"scoping", "features", "researching", "complete"}
        assert payload["status"] in {
            "awaiting_input",
            "processing",
            "done",
            "error",
        }
        assert payload["stage_data"]["component"] in {
            "assumptionBubble",
            "plainBubble",
            "featureConfirmationBubble",
            "agentActivityBubble",
            "researchTimelineBubble",
        }

    # Activity bubble for the orchestrator's chat_model_start should carry the
    # configured node label as headerText.
    activity = [
        d["stage_data"]
        for _, d in a2ui
        if d["stage_data"]["component"] == "agentActivityBubble"
    ]
    assert any(
        b["headerText"] == "Orchestrator is planning..." for b in activity
    )
    # And the tool_start/tool_end activity bubbles carry the patent search label.
    assert any("patent" in b["text"].lower() for b in activity)
