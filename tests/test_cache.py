"""Tests for semantic cache."""

from __future__ import annotations

import os
os.environ["MOCK_LLM"] = "true"

import math
from veritrace.cache import SemanticCache, SIMILARITY_THRESHOLD
from veritrace.schemas import TrustReceipt


def _unit(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


def _receipt(answer: str = "test answer") -> TrustReceipt:
    return TrustReceipt(tenant="demo", answer=answer, confidence="well-grounded")


# ---------------------------------------------------------------------------
# Cache unit tests
# ---------------------------------------------------------------------------

def test_empty_cache_returns_none():
    c = SemanticCache()
    assert c.get("demo", _unit([1, 0, 0, 0])) is None


def test_exact_hit():
    c = SemanticCache()
    emb = _unit([1.0, 0.5, 0.0, 0.0])
    r = _receipt("exact answer")
    c.put("demo", "q1", emb, r)
    result = c.get("demo", emb)
    assert result is not None
    assert result.answer == "exact answer"


def test_similar_query_hits():
    c = SemanticCache()
    emb1 = _unit([1.0, 0.0, 0.01, 0.0])
    emb2 = _unit([1.0, 0.0, 0.02, 0.0])  # very close
    r = _receipt("similar answer")
    c.put("demo", "q1", emb1, r)
    result = c.get("demo", emb2)
    assert result is not None


def test_dissimilar_query_misses():
    c = SemanticCache()
    emb1 = _unit([1.0, 0.0, 0.0, 0.0])
    emb2 = _unit([0.0, 1.0, 0.0, 0.0])  # orthogonal — similarity = 0
    r = _receipt()
    c.put("demo", "q1", emb1, r)
    result = c.get("demo", emb2)
    assert result is None


def test_tenant_isolation():
    c = SemanticCache()
    emb = _unit([1.0, 0.0, 0.0, 0.0])
    c.put("tenant_a", "q", emb, _receipt("A answer"))
    assert c.get("tenant_b", emb) is None


def test_lru_eviction():
    c = SemanticCache(max_entries=2)
    e1 = _unit([1.0, 0.0, 0.0, 0.0])
    e2 = _unit([0.0, 1.0, 0.0, 0.0])
    e3 = _unit([0.0, 0.0, 1.0, 0.0])
    c.put("demo", "q1", e1, _receipt("first"))
    c.put("demo", "q2", e2, _receipt("second"))
    c.put("demo", "q3", e3, _receipt("third"))  # should evict q1
    assert c.size("demo") == 2
    assert c.get("demo", e1) is None   # evicted


def test_clear_tenant():
    c = SemanticCache()
    emb = _unit([1.0, 0.0, 0.0, 0.0])
    c.put("demo", "q", emb, _receipt())
    c.clear("demo")
    assert c.get("demo", emb) is None


# ---------------------------------------------------------------------------
# /v1/query cache integration
# ---------------------------------------------------------------------------

import pytest
from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_second_identical_query_returns_cached(client):
    q = {"query": "Is generic atorvastatin covered?", "tenant_id": "demo"}
    r1 = client.post("/v1/query", json=q)
    r2 = client.post("/v1/query", json=q)
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Second response should be from cache (route = "cached")
    assert r2.json()["route"] == "cached"


def test_cached_response_faster(client):
    import time
    q = {"query": "What is the annual deductible?", "tenant_id": "demo"}
    client.post("/v1/query", json=q)  # warm cache
    t0 = time.time()
    r = client.post("/v1/query", json=q)
    elapsed = (time.time() - t0) * 1000
    assert r.json()["route"] == "cached"
    assert elapsed < 500   # cache hit should be fast
