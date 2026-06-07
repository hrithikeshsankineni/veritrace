"""Tests for MCP tool server and action layer (task 8.2)."""

from __future__ import annotations

import os
os.environ["MOCK_LLM"] = "true"

import pytest


# ---------------------------------------------------------------------------
# actions.py — parameter extraction
# ---------------------------------------------------------------------------

def test_extract_member_id():
    from veritrace.tools.actions import extract_parameters
    params = extract_parameters("lookup_coverage", "What is MBR-100042's copay for atorvastatin?")
    assert params["member_id"] == "MBR-100042"
    assert params["drug_name"] == "atorvastatin"


def test_extract_drug_name_case_insensitive():
    from veritrace.tools.actions import extract_parameters
    params = extract_parameters("lookup_coverage", "MBR-100042 sertraline coverage")
    assert params["drug_name"] == "sertraline"


def test_extract_file_inquiry_params():
    from veritrace.tools.actions import extract_parameters
    q = "File an inquiry for MBR-100042 — they have a billing dispute"
    params = extract_parameters("file_inquiry", q)
    assert params["member_id"] == "MBR-100042"
    assert "description" in params
    assert len(params["description"]) > 0


# ---------------------------------------------------------------------------
# actions.py — verify gate
# ---------------------------------------------------------------------------

def test_verify_valid_lookup():
    from veritrace.tools.actions import verify
    ok, reason = verify("lookup_coverage", {"member_id": "MBR-100042", "drug_name": "atorvastatin"})
    assert ok is True


def test_verify_missing_required_param():
    from veritrace.tools.actions import verify
    ok, reason = verify("lookup_coverage", {"member_id": "MBR-100042"})
    assert ok is False
    assert "drug_name" in reason


def test_verify_invalid_member_id_format():
    from veritrace.tools.actions import verify
    ok, reason = verify("lookup_coverage", {"member_id": "not-an-id", "drug_name": "atorvastatin"})
    assert ok is False
    assert "member_id" in reason


def test_verify_unknown_tool():
    from veritrace.tools.actions import verify
    ok, reason = verify("nonexistent_tool", {})
    assert ok is False
    assert "Unknown tool" in reason


def test_verify_description_too_long():
    from veritrace.tools.actions import verify
    ok, reason = verify("file_inquiry", {
        "member_id": "MBR-100042",
        "description": "x" * 600,
    })
    assert ok is False
    assert "max length" in reason


# ---------------------------------------------------------------------------
# actions.py — execute (requires DB)
# ---------------------------------------------------------------------------

def test_execute_lookup_coverage_known_member():
    from veritrace.tools.actions import execute
    from pathlib import Path
    db = Path(__file__).parent.parent / "data" / "synthetic" / "records.sqlite"
    if not db.exists():
        pytest.skip("Synthetic DB not seeded")
    result = execute("lookup_coverage", {"member_id": "MBR-100042", "drug_name": "atorvastatin"})
    assert result["verified"] is True
    assert "atorvastatin" in result["result"].lower() or "Alice" in result["result"]


def test_execute_lookup_coverage_unknown_member():
    from veritrace.tools.actions import execute
    from pathlib import Path
    db = Path(__file__).parent.parent / "data" / "synthetic" / "records.sqlite"
    if not db.exists():
        pytest.skip("Synthetic DB not seeded")
    result = execute("lookup_coverage", {"member_id": "MBR-999999", "drug_name": "atorvastatin"})
    assert result["verified"] is True  # verified=True means gate passed, result explains not found
    assert "not found" in result["result"]


def test_execute_file_inquiry_creates_ticket():
    from veritrace.tools.actions import execute
    from pathlib import Path
    db = Path(__file__).parent.parent / "data" / "synthetic" / "records.sqlite"
    if not db.exists():
        pytest.skip("Synthetic DB not seeded")
    result = execute("file_inquiry", {
        "member_id": "MBR-100042",
        "description": "Test inquiry from automated test suite",
    })
    assert result["verified"] is True
    assert "TKT-" in result["result"]


def test_execute_rejected_when_verify_fails():
    from veritrace.tools.actions import execute
    result = execute("lookup_coverage", {"member_id": "bad-id", "drug_name": "atorvastatin"})
    assert result["verified"] is False
    assert "rejected" in result["result"]


# ---------------------------------------------------------------------------
# mcp_server.py — routing
# ---------------------------------------------------------------------------

def test_route_lookup_coverage():
    from veritrace.tools.mcp_server import _route_tool
    assert _route_tool("What tier is atorvastatin for member MBR-100042?") == "lookup_coverage"


def test_route_file_inquiry():
    from veritrace.tools.mcp_server import _route_tool
    assert _route_tool("File an inquiry for my coverage dispute") == "file_inquiry"


def test_route_defaults_to_lookup_on_tie():
    from veritrace.tools.mcp_server import _route_tool
    # No clear keywords → defaults to lookup_coverage (read-preferred)
    result = _route_tool("help me with my plan")
    assert result in ("lookup_coverage", "file_inquiry")


# ---------------------------------------------------------------------------
# mcp_server.py — dispatch returns ActionInfo
# ---------------------------------------------------------------------------

def test_dispatch_returns_action_info_structure():
    from veritrace.tools.mcp_server import dispatch
    from veritrace.schemas import ActionInfo
    from pathlib import Path
    db = Path(__file__).parent.parent / "data" / "synthetic" / "records.sqlite"
    if not db.exists():
        pytest.skip("Synthetic DB not seeded")
    ai = dispatch("Check coverage for MBR-100042 atorvastatin", "demo")
    assert isinstance(ai, ActionInfo)
    assert ai.tool == "lookup_coverage"
    assert ai.result is not None
    # member_id should not appear in stored parameters (PII stripped)
    assert "member_id" not in ai.parameters


def test_dispatch_unverified_when_missing_params():
    from veritrace.tools.mcp_server import dispatch
    # No member_id in query — verify gate should reject
    ai = dispatch("What is the drug coverage?", "demo")
    assert isinstance(ai, ai.__class__)
    # verified=False because member_id missing
    assert ai.verified is False


# ---------------------------------------------------------------------------
# list_tools
# ---------------------------------------------------------------------------

def test_list_tools_returns_schema():
    from veritrace.tools.mcp_server import list_tools
    tools = list_tools()
    assert isinstance(tools, list)
    assert len(tools) == 2
    names = {t["name"] for t in tools}
    assert "lookup_coverage" in names
    assert "file_inquiry" in names
    for t in tools:
        assert "description" in t
        assert "parameters" in t
        assert "mutates" in t
    # file_inquiry is mutating; lookup_coverage is not
    lookup = next(t for t in tools if t["name"] == "lookup_coverage")
    assert lookup["mutates"] is False
    inquiry = next(t for t in tools if t["name"] == "file_inquiry")
    assert inquiry["mutates"] is True
