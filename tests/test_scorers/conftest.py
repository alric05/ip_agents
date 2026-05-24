"""Shared fixtures for scorer unit tests.

Provides synthetic eval traces, ground truth data, and temporary
session directories with known expected scores.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def tmp_session(tmp_path: Path) -> Path:
    """Create a minimal session directory with standard artifacts."""
    session = tmp_path / "session"
    session.mkdir()
    return session


@pytest.fixture
def sample_eval_trace() -> dict:
    """A minimal eval_trace.json dict."""
    return {
        "schema_version": "1.1",
        "trace_type": "novelty_checker",
        "run_metadata": {
            "session_id": "test-session-001",
            "total_duration_seconds": 120.5,
            "final_phase": "COMPLETED",
            "model_name": "gpt-4o",
        },
        "turns": [],
        "stage_summary": {
            "INITIAL": {"total_duration_seconds": 5.0},
            "AUTONOMOUS_RESEARCH": {"total_duration_seconds": 100.0},
            "COMPLETED": {"total_duration_seconds": 15.5},
        },
        "telemetry": {
            "total_rounds": 3,
            "total_tool_calls": 20,
            "failed_tool_calls": 1,
            "success_rate": 0.95,
            "token_usage": {
                "cumulative": {
                    "total_tokens": 50000,
                    "estimated_cost_usd": 1.25,
                },
                "by_agent": {},
                "by_stage": {},
            },
            "search_queries": [
                {
                    "agent_name": "patent-researcher",
                    "tool_name": "patent_keyword_search",
                    "args": {"query": "wireless sensor network energy harvesting"},
                    "success": True,
                },
                {
                    "agent_name": "semantic-researcher",
                    "tool_name": "semantic_patent_search",
                    "args": {"query": "IoT power management piezoelectric"},
                    "success": True,
                },
                {
                    "agent_name": "patent-researcher",
                    "tool_name": "batch_patent_search",
                    "args": {"queries": ["H04W energy", "H02N piezo"]},
                    "success": True,
                },
                {
                    "agent_name": "citation-researcher",
                    "tool_name": "patent_keyword_search",
                    "args": {"query": "US9924896 citations"},
                    "success": True,
                },
            ],
        },
        "checklist": {"passed": True, "checks": {}, "details": {}},
        "artifacts_manifest": [
            {"filename": "references.md", "exists": True, "size_bytes": 5000},
            {"filename": "features.md", "exists": True, "size_bytes": 3000},
            {"filename": "final_report.md", "exists": True, "size_bytes": 10000},
        ],
    }


@pytest.fixture
def sample_ground_truth() -> dict:
    """Ground truth fixture with features, references, and verdict."""
    return {
        "features": [
            {"id": "F1", "name": "Piezoelectric energy harvesting module", "description": "Converts mechanical vibrations to electrical energy", "core": "Y"},
            {"id": "F2", "name": "Wireless sensor node with adaptive duty cycling", "description": "IoT sensor node adjusts transmission rate based on energy budget", "core": "Y"},
            {"id": "F3", "name": "Energy storage supercapacitor array", "description": "Multiple supercapacitors in parallel for buffering harvested energy", "core": "N"},
            {"id": "F4", "name": "Low-power wake-up receiver", "description": "Ultra-low power radio for on-demand wake-up of sensor node", "core": "N"},
        ],
        "references": {
            "references": [
                {"publication_number": "US9924896B2", "triage_label": "A", "title": "Energy harvesting sensor system"},
                {"publication_number": "US10234567B1", "triage_label": "A", "title": "Piezoelectric power management"},
                {"publication_number": "EP3456789A1", "triage_label": "B", "title": "Wireless sensor duty cycling"},
                {"publication_number": "WO2020123456A1", "triage_label": "B", "title": "Supercapacitor array for IoT"},
                {"publication_number": "US11111111B2", "triage_label": "C", "title": "Generic sensor network"},
            ]
        },
        "verdict": {
            "verdict": "partially_novel",
            "confidence": 0.7,
        },
        "search_strategy": "CPC codes: H02N2/18, H04W84/18, H01G11/00\nKeyword families: piezoelectric, energy harvesting, duty cycling",
    }


@pytest.fixture
def write_session_artifacts(tmp_session: Path) -> callable:
    """Factory fixture to write session artifacts."""

    def _write(
        final_report: str = "",
        features_md: str = "",
        references_md: str = "",
        findings_json: str = "",
        eval_trace: dict | None = None,
    ) -> Path:
        if final_report:
            (tmp_session / "final_report.md").write_text(final_report, encoding="utf-8")
        if features_md:
            (tmp_session / "features.md").write_text(features_md, encoding="utf-8")
        if references_md:
            (tmp_session / "references.md").write_text(references_md, encoding="utf-8")
        if findings_json:
            (tmp_session / "findings_accumulator.json").write_text(findings_json, encoding="utf-8")
        if eval_trace:
            (tmp_session / "eval_trace.json").write_text(
                json.dumps(eval_trace, indent=2), encoding="utf-8"
            )
        return tmp_session

    return _write
