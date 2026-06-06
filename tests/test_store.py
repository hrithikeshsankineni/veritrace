"""Tests for veritrace.index.embeddings and veritrace.index.store."""

from __future__ import annotations

import os

import pytest

os.environ["MOCK_LLM"] = "true"

from veritrace.ingest.chunker import Chunk
from veritrace.index.embeddings import embed_chunks, embed_query
from veritrace.index.store import VectorStore


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

def _make_chunk(text: str, tenant_id: str = "demo", source_id: str = "src") -> Chunk:
    import hashlib
    cid = hashlib.sha256(f"{source_id}:{text}".encode()).hexdigest()[:16]
    return Chunk(
        chunk_id=cid,
        text=text,
        heading="",
        section="",
        metadata={"source_id": source_id, "tenant_id": tenant_id},
    )


def test_embed_chunks_returns_vectors():
    chunks = [_make_chunk("hello world"), _make_chunk("foo bar")]
    vecs = embed_chunks(chunks)
    assert len(vecs) == 2
    assert all(isinstance(v, list) and len(v) > 0 for v in vecs)


def test_embed_query_returns_vector():
    vec = embed_query("Is atorvastatin covered?")
    assert isinstance(vec, list)
    assert len(vec) > 0


def test_embed_query_is_deterministic():
    assert embed_query("test") == embed_query("test")


# ---------------------------------------------------------------------------
# VectorStore — basic add + query
# ---------------------------------------------------------------------------

@pytest.fixture()
def store(tmp_path):
    return VectorStore(collection_name="test_col", persist_directory=str(tmp_path / "chroma"))


def test_store_add_and_count(store):
    chunks = [_make_chunk("Atorvastatin is a Tier 1 drug.", "demo")]
    vecs = embed_chunks(chunks)
    store.add(chunks, vecs)
    assert store.count("demo") == 1


def test_store_query_returns_results(store):
    chunks = [_make_chunk("Generic atorvastatin Tier 1 copay $10.", "demo")]
    vecs = embed_chunks(chunks)
    store.add(chunks, vecs)

    q = embed_query("atorvastatin copay")
    results = store.query(q, tenant_id="demo", top_k=5)
    assert len(results) >= 1
    assert "text" in results[0]
    assert "score" in results[0]
    assert 0.0 <= results[0]["score"] <= 1.0


# ---------------------------------------------------------------------------
# Tenant isolation — the critical property
# ---------------------------------------------------------------------------

def test_tenant_isolation(store):
    """Chunks from tenant A must not appear in tenant B query results."""
    chunk_a = _make_chunk("Atorvastatin covered Tier 1 $10.", "tenant_a", "formulary_a")
    chunk_b = _make_chunk("Rosuvastatin covered Tier 2 $30.", "tenant_b", "formulary_b")

    vecs_a = embed_chunks([chunk_a])
    vecs_b = embed_chunks([chunk_b])
    store.add([chunk_a], vecs_a)
    store.add([chunk_b], vecs_b)

    assert store.count("tenant_a") == 1
    assert store.count("tenant_b") == 1

    # Query as tenant_a — must only see tenant_a's chunk
    q = embed_query("atorvastatin")
    results_a = store.query(q, tenant_id="tenant_a", top_k=10)
    assert all(r["metadata"]["tenant_id"] == "tenant_a" for r in results_a)

    # Query as tenant_b — must only see tenant_b's chunk
    results_b = store.query(q, tenant_id="tenant_b", top_k=10)
    assert all(r["metadata"]["tenant_id"] == "tenant_b" for r in results_b)


def test_delete_tenant_removes_chunks(store):
    chunks = [_make_chunk("text", "tenant_x")]
    store.add(chunks, embed_chunks(chunks))
    assert store.count("tenant_x") == 1
    store.delete_tenant("tenant_x")
    assert store.count("tenant_x") == 0


def test_metadata_passthrough(store):
    chunk = _make_chunk("policy text", "demo")
    chunk["metadata"]["authority_level"] = "primary"
    chunk["metadata"]["effective_date"] = "2026-01-01"
    store.add([chunk], embed_chunks([chunk]))

    q = embed_query("policy")
    results = store.query(q, "demo", top_k=5)
    assert results
    assert results[0]["metadata"]["authority_level"] == "primary"
    assert results[0]["metadata"]["effective_date"] == "2026-01-01"
