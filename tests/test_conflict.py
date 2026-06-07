"""Tests for conflict detection and resolution."""

from __future__ import annotations

import pytest

from veritrace.responder.conflict import detect_and_resolve, _source_family


def _cand(source_id: str, effective_date: str = "", supersedes: str = "",
          text: str = "some text", score: float = 0.9):
    meta = {"source_id": source_id, "tenant_id": "demo"}
    if effective_date:
        meta["effective_date"] = effective_date
    if supersedes:
        meta["supersedes"] = supersedes
    return {
        "chunk_id": f"cid_{source_id}",
        "text": text,
        "score": score,
        "rerank_score": score,
        "metadata": meta,
    }


# ---------------------------------------------------------------------------
# Source family helper
# ---------------------------------------------------------------------------

def test_family_strips_year():
    assert _source_family("formulary_2024") == "formulary"


def test_family_strips_version():
    assert _source_family("policy_prior_auth_v1") == "policy_prior_auth"


def test_family_no_suffix():
    assert _source_family("coverage_policy") == "coverage_policy"


# ---------------------------------------------------------------------------
# No conflict
# ---------------------------------------------------------------------------

def test_no_conflict_single_candidate():
    result = detect_and_resolve([_cand("formulary_2026")])
    assert result["detected"] is False
    assert len(result["filtered"]) == 1


def test_no_conflict_different_families():
    result = detect_and_resolve([
        _cand("formulary_2026", "2026-01-01"),
        _cand("coverage_policy_2026", "2026-01-01"),
    ])
    assert result["detected"] is False
    assert len(result["filtered"]) == 2


# ---------------------------------------------------------------------------
# Conflict via effective_date
# ---------------------------------------------------------------------------

def test_conflict_detected_by_date():
    result = detect_and_resolve([
        _cand("formulary_2024", "2024-01-01"),
        _cand("formulary_2026", "2026-01-01"),
    ])
    assert result["detected"] is True


def test_newer_wins_by_date():
    result = detect_and_resolve([
        _cand("formulary_2024", "2024-01-01"),
        _cand("formulary_2026", "2026-01-01"),
    ])
    assert result["resolved_to"] == "formulary_2026"


def test_superseded_removed_from_filtered():
    result = detect_and_resolve([
        _cand("formulary_2024", "2024-01-01"),
        _cand("formulary_2026", "2026-01-01"),
    ])
    source_ids = [c["metadata"]["source_id"] for c in result["filtered"]]
    assert "formulary_2024" not in source_ids
    assert "formulary_2026" in source_ids


# ---------------------------------------------------------------------------
# Conflict via explicit supersedes link
# ---------------------------------------------------------------------------

def test_conflict_detected_by_supersedes():
    result = detect_and_resolve([
        _cand("policy_v1"),
        _cand("policy_v2", supersedes="policy_v1"),
    ])
    assert result["detected"] is True
    assert result["resolved_to"] == "policy_v2"


def test_supersedes_loser_removed():
    result = detect_and_resolve([
        _cand("policy_v1"),
        _cand("policy_v2", supersedes="policy_v1"),
    ])
    source_ids = [c["metadata"]["source_id"] for c in result["filtered"]]
    assert "policy_v1" not in source_ids


# ---------------------------------------------------------------------------
# Description populated
# ---------------------------------------------------------------------------

def test_description_present_on_conflict():
    result = detect_and_resolve([
        _cand("formulary_2024", "2024-01-01"),
        _cand("formulary_2026", "2026-01-01"),
    ])
    assert result["description"] is not None
    assert "superseded" in result["description"].lower()


def test_no_description_on_no_conflict():
    result = detect_and_resolve([_cand("formulary_2026")])
    assert result["description"] is None


# ---------------------------------------------------------------------------
# Integration: agent emits ConflictInfo in receipt
# ---------------------------------------------------------------------------

import os
os.environ["MOCK_LLM"] = "true"

import hashlib
from veritrace.index.store import VectorStore
from veritrace.index.embeddings import embed_chunks
from veritrace.ingest.chunker import Chunk


def _chunk(text: str, source_id: str, effective_date: str = "",
           supersedes: str = "", tenant: str = "demo") -> Chunk:
    cid = hashlib.sha256(f"{source_id}:{text}".encode()).hexdigest()[:16]
    meta = {"source_id": source_id, "tenant_id": tenant}
    if effective_date:
        meta["effective_date"] = effective_date
    if supersedes:
        meta["supersedes"] = supersedes
    return Chunk(chunk_id=cid, text=text, heading="Statins", section="Cardiovascular",
                 metadata=meta)


@pytest.fixture(scope="module")
def conflict_store(tmp_path_factory):
    d = tmp_path_factory.mktemp("conflict_chroma")
    s = VectorStore(collection_name="conflict_test", persist_directory=str(d))
    chunks = [
        _chunk("Atorvastatin is Tier 2 with a $30 copay.", "formulary_2024", "2024-01-01"),
        _chunk("Atorvastatin is Tier 1 with a $10 copay.", "formulary_2026", "2026-01-01",
               supersedes="formulary_2024"),
        _chunk("The annual deductible is $500.", "coverage_policy", "2026-01-01"),
    ]
    s.add(chunks, embed_chunks(chunks))
    return s


def test_agent_receipt_has_conflict_info(conflict_store):
    from veritrace.responder.agent import answer
    import time
    receipt = answer("atorvastatin copay tier", "demo", conflict_store, start_time=time.time())
    assert receipt.conflict.detected is True
    assert receipt.conflict.resolved_to == "formulary_2026"


def test_agent_receipt_answer_uses_current_doc(conflict_store):
    from veritrace.responder.agent import answer
    import time
    receipt = answer("atorvastatin copay tier", "demo", conflict_store, start_time=time.time())
    # Should NOT mention the outdated $30 price from 2024 doc
    # (the 2024 doc should be filtered out before generation)
    assert receipt.conflict.resolved_to == "formulary_2026"
