"""Tests for short-term session memory and /v1/chat endpoint."""

from __future__ import annotations

import os
os.environ["MOCK_LLM"] = "true"

from veritrace.memory import SessionMemory, add_turn, get_history, clear_session


# ---------------------------------------------------------------------------
# SessionMemory unit tests
# ---------------------------------------------------------------------------

def test_empty_session_returns_empty():
    m = SessionMemory()
    assert m.get_history("nonexistent") == []


def test_add_and_get_turn():
    m = SessionMemory()
    m.add_turn("s1", "user", "Hello")
    history = m.get_history("s1")
    assert len(history) == 1
    assert history[0] == {"role": "user", "content": "Hello"}


def test_multiple_turns_ordered():
    m = SessionMemory()
    m.add_turn("s2", "user", "Q1")
    m.add_turn("s2", "assistant", "A1")
    m.add_turn("s2", "user", "Q2")
    history = m.get_history("s2")
    assert len(history) == 3
    assert history[0]["content"] == "Q1"
    assert history[2]["content"] == "Q2"


def test_window_trimmed():
    m = SessionMemory(max_turns=2)
    for i in range(5):
        m.add_turn("s3", "user", f"Q{i}")
        m.add_turn("s3", "assistant", f"A{i}")
    history = m.get_history("s3")
    assert len(history) == 4  # max_turns * 2


def test_clear_session():
    m = SessionMemory()
    m.add_turn("s4", "user", "Hello")
    m.clear_session("s4")
    assert m.get_history("s4") == []


def test_sessions_are_isolated():
    m = SessionMemory()
    m.add_turn("sa", "user", "Session A")
    m.add_turn("sb", "user", "Session B")
    assert m.get_history("sa")[0]["content"] == "Session A"
    assert m.get_history("sb")[0]["content"] == "Session B"


def test_module_level_functions():
    add_turn("mod_test", "user", "test message")
    history = get_history("mod_test")
    assert any(m["content"] == "test message" for m in history)
    clear_session("mod_test")
    assert get_history("mod_test") == []


# ---------------------------------------------------------------------------
# /v1/chat endpoint
# ---------------------------------------------------------------------------

import pytest
from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_chat_endpoint_returns_receipt(client):
    resp = client.post("/v1/chat", json={"query": "Is atorvastatin covered?",
                                          "tenant_id": "demo"})
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "confidence" in data


def test_chat_endpoint_in_openapi(client):
    spec = client.get("/openapi.json").json()
    assert "/v1/chat" in spec["paths"]


def test_chat_with_session_id(client):
    session = "test_session_001"
    resp = client.post("/v1/chat", json={"query": "What is my atorvastatin copay?",
                                          "tenant_id": "demo",
                                          "session_id": session})
    assert resp.status_code == 200


def test_chat_followup_uses_session(client):
    """Two calls with same session_id — second should not crash and returns receipt."""
    session = "test_session_002"
    client.post("/v1/chat", json={"query": "Is atorvastatin covered?",
                                   "tenant_id": "demo", "session_id": session})
    resp = client.post("/v1/chat", json={"query": "What tier is it?",
                                          "tenant_id": "demo", "session_id": session})
    assert resp.status_code == 200
    assert "answer" in resp.json()
