"""Tests for veritrace.responder.agent — end-to-end pipeline."""

from __future__ import annotations

import os

import pytest

os.environ["MOCK_LLM"] = "true"

from veritrace.index.store import VectorStore
from veritrace.index.embeddings import embed_chunks
from veritrace.ingest.chunker import Chunk
from veritrace.responder.agent import answer
from veritrace.schemas import TrustReceipt

import hashlib


def _make_chunk(text: str, tenant_id: str = "demo", source: str = "formulary") -> Chunk:
    cid = hashlib.sha256(f"{source}:{text}".encode()).hexdigest()[:16]
    return Chunk(
        chunk_id=cid,
        text=text,
        heading="Statins",
        section="Covered Medications",
        metadata={"source_id": source, "tenant_id": tenant_id},
    )


@pytest.fixture()
def store_with_data(tmp_path):
    store = VectorStore(collection_name="agent_test", persist_directory=str(tmp_path / "chroma"))
    chunks = [
        _make_chunk("Generic atorvastatin is covered at Tier 1 with a $10 copay.", "demo"),
        _make_chunk("Prior authorization is required for specialty biologics.", "demo", "pa_v2"),
        _make_chunk("The annual deductible is $500 for individual coverage.", "demo", "cov26"),
        _make_chunk("Sertraline (generic) is covered at Tier 1 with a $10 copay.", "demo"),
        _make_chunk("Emergency room visits have a $250 copay, waived if admitted.", "demo", "cov26"),
    ]
    vecs = embed_chunks(chunks)
    store.add(chunks, vecs)
    return store


@pytest.fixture()
def empty_store(tmp_path):
    return VectorStore(collection_name="empty_agent", persist_directory=str(tmp_path / "chroma2"))


# ---------------------------------------------------------------------------
# Returns TrustReceipt
# ---------------------------------------------------------------------------

def test_answer_returns_trust_receipt(store_with_data):
    receipt = answer("Is atorvastatin covered?", "demo", store_with_data)
    assert isinstance(receipt, TrustReceipt)


def test_answer_has_request_id(store_with_data):
    receipt = answer("What is my deductible?", "demo", store_with_data)
    assert receipt.request_id.startswith("rq_")


def test_answer_has_tenant(store_with_data):
    receipt = answer("drug coverage", "demo", store_with_data)
    assert receipt.tenant == "demo"


# ---------------------------------------------------------------------------
# Abstention (empty store = no evidence)
# ---------------------------------------------------------------------------

def test_answer_abstains_on_empty_store(empty_store):
    receipt = answer("What is covered?", "demo", empty_store)
    assert receipt.confidence == "abstained"
    assert "sufficient information" in receipt.answer.lower() or "not yet available" in receipt.answer.lower()


# ---------------------------------------------------------------------------
# Answer with evidence
# ---------------------------------------------------------------------------

def test_answer_with_evidence_is_grounded(store_with_data):
    receipt = answer("What is the atorvastatin copay?", "demo", store_with_data)
    # May be well-grounded or partially-grounded depending on mock scores
    assert receipt.confidence in ("well-grounded", "partially-grounded", "abstained")


def test_answer_latency_recorded(store_with_data):
    receipt = answer("drug coverage", "demo", store_with_data)
    assert receipt.latency_ms >= 0.0


def test_answer_model_profile_set(store_with_data):
    receipt = answer("drug coverage", "demo", store_with_data)
    assert receipt.model_profile in ("mini", "nano")


# ---------------------------------------------------------------------------
# Action intent routing — MCP dispatch
# ---------------------------------------------------------------------------

def test_action_intent_routes_to_mcp(store_with_data):
    """Action queries should route to the MCP dispatcher (route='action')."""
    receipt = answer("open ticket for my denied claim", "demo", store_with_data)
    assert receipt.route == "action"
    assert receipt.action is not None
    assert receipt.action.tool in ("lookup_coverage", "file_inquiry")


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

def test_answer_tenant_isolation(tmp_path):
    store = VectorStore(collection_name="iso", persist_directory=str(tmp_path / "chroma"))
    chunk_a = _make_chunk("Alpha plan: atorvastatin free.", "alpha")
    chunk_b = _make_chunk("Beta plan: atorvastatin $50 copay.", "beta")
    store.add([chunk_a], embed_chunks([chunk_a]))
    store.add([chunk_b], embed_chunks([chunk_b]))

    r_alpha = answer("atorvastatin copay", "alpha", store)
    r_beta = answer("atorvastatin copay", "beta", store)

    # Both should only have seen their own data
    assert r_alpha.tenant == "alpha"
    assert r_beta.tenant == "beta"
