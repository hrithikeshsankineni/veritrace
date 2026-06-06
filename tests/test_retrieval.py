"""Tests for veritrace.retrieval.retrieve and veritrace.retrieval.rerank."""

from __future__ import annotations

import os

import pytest

os.environ["MOCK_LLM"] = "true"

from veritrace.index.store import VectorStore, SearchResult
from veritrace.index.embeddings import embed_chunks
from veritrace.ingest.chunker import Chunk
from veritrace.retrieval.retrieve import retrieve
from veritrace.retrieval.rerank import rerank, RankedResult

import hashlib


def _make_chunk(text: str, tenant_id: str = "demo", source: str = "doc") -> Chunk:
    cid = hashlib.sha256(f"{source}:{text}".encode()).hexdigest()[:16]
    return Chunk(
        chunk_id=cid,
        text=text,
        heading="",
        section="",
        metadata={"source_id": source, "tenant_id": tenant_id},
    )


@pytest.fixture()
def populated_store(tmp_path):
    store = VectorStore(collection_name="test", persist_directory=str(tmp_path / "chroma"))
    chunks = [
        _make_chunk("Atorvastatin generic is covered at Tier 1 copay $10.", "demo", "form26"),
        _make_chunk("Prior authorization is required for specialty biologics.", "demo", "pa_v2"),
        _make_chunk("The out-of-pocket maximum is $7500 per year.", "demo", "cov26"),
        _make_chunk("Rosuvastatin is covered at Tier 1.", "demo", "form26"),
        _make_chunk("Member services FAQ: file claims within 30 days.", "demo", "faq"),
    ]
    vecs = embed_chunks(chunks)
    store.add(chunks, vecs)
    return store


# ---------------------------------------------------------------------------
# retrieve
# ---------------------------------------------------------------------------

def test_retrieve_returns_results(populated_store):
    results = retrieve("atorvastatin copay", "demo", populated_store)
    assert isinstance(results, list)
    assert len(results) > 0


def test_retrieve_tenant_scoped(tmp_path):
    store = VectorStore(collection_name="iso_test", persist_directory=str(tmp_path / "chroma"))
    chunk_a = _make_chunk("Formulary drug A.", "alpha")
    chunk_b = _make_chunk("Formulary drug B.", "beta")
    store.add([chunk_a], embed_chunks([chunk_a]))
    store.add([chunk_b], embed_chunks([chunk_b]))

    results = retrieve("formulary drug", "alpha", store)
    assert all(r["metadata"]["tenant_id"] == "alpha" for r in results)

    results = retrieve("formulary drug", "beta", store)
    assert all(r["metadata"]["tenant_id"] == "beta" for r in results)


def test_retrieve_respects_top_k(populated_store):
    results = retrieve("drug", "demo", populated_store, top_k=2)
    assert len(results) <= 2


def test_retrieve_returns_scores(populated_store):
    results = retrieve("atorvastatin", "demo", populated_store)
    for r in results:
        assert 0.0 <= r["score"] <= 1.0


# ---------------------------------------------------------------------------
# rerank
# ---------------------------------------------------------------------------

def _make_sr(text: str, score: float = 0.5, tenant_id: str = "demo") -> SearchResult:
    return SearchResult(
        chunk_id=hashlib.sha256(text.encode()).hexdigest()[:8],
        text=text,
        score=score,
        metadata={"tenant_id": tenant_id},
    )


def test_rerank_returns_ranked_results():
    candidates = [
        _make_sr("Generic atorvastatin Tier 1 $10 copay."),
        _make_sr("Prior authorization for biologics."),
        _make_sr("Out-of-pocket maximum $7500."),
    ]
    results = rerank("atorvastatin copay", candidates, top_k=3)
    assert len(results) == 3
    assert all("rerank_score" in r for r in results)


def test_rerank_sorted_descending():
    candidates = [_make_sr(f"text_{i}") for i in range(5)]
    results = rerank("query", candidates, top_k=5)
    scores = [r["rerank_score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_rerank_top_k_respected():
    candidates = [_make_sr(f"chunk_{i}") for i in range(10)]
    results = rerank("query", candidates, top_k=3)
    assert len(results) == 3


def test_rerank_empty_input():
    assert rerank("query", []) == []


def test_rerank_preserves_metadata():
    c = _make_sr("Policy text.", 0.8, "acme")
    c["metadata"]["authority_level"] = "primary"
    results = rerank("query", [c])
    assert results[0]["metadata"]["authority_level"] == "primary"


def test_rerank_is_deterministic():
    candidates = [_make_sr(f"doc {i}") for i in range(4)]
    r1 = [r["rerank_score"] for r in rerank("test query", candidates)]
    r2 = [r["rerank_score"] for r in rerank("test query", candidates)]
    assert r1 == r2
