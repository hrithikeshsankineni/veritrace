"""Tests for assurance runner, score, and /v1/assure endpoint."""

from __future__ import annotations

import os

import pytest

os.environ["MOCK_LLM"] = "true"

from veritrace.assurance.attacks import generate_attacks
from veritrace.assurance.runner import run_attacks
from veritrace.assurance.score import compute_score
from veritrace.index.store import VectorStore
from veritrace.index.embeddings import embed_chunks
from veritrace.ingest.chunker import Chunk
import hashlib


def _chunk(text: str, tenant: str = "demo") -> Chunk:
    cid = hashlib.sha256(f"src:{text}".encode()).hexdigest()[:16]
    return Chunk(chunk_id=cid, text=text, heading="", section="",
                 metadata={"source_id": "formulary_2026", "tenant_id": tenant})


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    d = tmp_path_factory.mktemp("chroma")
    s = VectorStore(collection_name="assure_test", persist_directory=str(d))
    chunks = [
        _chunk("Generic atorvastatin is covered at Tier 1 with a $10 copay.", "demo"),
        _chunk("Prior authorization is required for specialty biologics.", "demo"),
        _chunk("The annual deductible is $500 per year.", "demo"),
        _chunk("Cosmetic procedures are excluded from coverage.", "demo"),
    ]
    s.add(chunks, embed_chunks(chunks))
    return s


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def test_run_attacks_returns_results(store):
    attacks = generate_attacks("demo")
    results = run_attacks(attacks, "demo", store)
    assert len(results) == len(attacks)


def test_run_attacks_have_required_fields(store):
    attacks = generate_attacks("demo")[:3]
    results = run_attacks(attacks, "demo", store)
    for r in results:
        assert r.attack_id
        assert r.attack_class
        assert r.prompt
        assert isinstance(r.passed, bool)
        assert r.receipt is not None


def test_injection_attacks_blocked(store):
    """Injection attacks must be blocked (passed=True means defense succeeded)."""
    attacks = [a for a in generate_attacks("demo") if a["attack_class"] == "injection"]
    results = run_attacks(attacks, "demo", store)
    for r in results:
        assert r.passed is True, f"Injection not blocked: {r.attack_id} — {r.notes}"


def test_out_of_scope_blocked(store):
    attacks = [a for a in generate_attacks("demo") if a["attack_class"] == "out_of_scope"]
    results = run_attacks(attacks, "demo", store)
    for r in results:
        assert r.passed is True, f"Out-of-scope not blocked: {r.attack_id}"


# ---------------------------------------------------------------------------
# Score
# ---------------------------------------------------------------------------

def test_compute_score_returns_report(store):
    attacks = generate_attacks("demo")
    results = run_attacks(attacks, "demo", store)
    report = compute_score(results, "demo")
    assert report.tenant == "demo"
    assert 0.0 <= report.trust_score <= 100.0
    assert report.total_attacks == len(attacks)
    assert report.passed + report.failed == report.total_attacks


def test_score_empty_results():
    report = compute_score([], "demo")
    assert report.trust_score == 0.0
    assert report.total_attacks == 0


def test_per_class_present(store):
    attacks = generate_attacks("demo")
    results = run_attacks(attacks, "demo", store)
    report = compute_score(results, "demo")
    expected_classes = {"injection", "pii_extraction", "out_of_scope", "unanswerable", "contradiction"}
    assert set(report.per_class.keys()) == expected_classes


def test_per_class_scores_in_range(store):
    attacks = generate_attacks("demo")
    results = run_attacks(attacks, "demo", store)
    report = compute_score(results, "demo")
    for cls, data in report.per_class.items():
        assert 0.0 <= data["score"] <= 100.0


def test_findings_list_has_failures(store):
    attacks = generate_attacks("demo")
    results = run_attacks(attacks, "demo", store)
    report = compute_score(results, "demo")
    # findings should be a list (may be empty if all pass)
    assert isinstance(report.findings, list)


# ---------------------------------------------------------------------------
# /v1/assure endpoint
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture(scope="module")
def api_client():
    with TestClient(app) as c:
        yield c


def test_assure_endpoint_returns_report(api_client):
    response = api_client.post("/v1/assure?tenant_id=demo")
    assert response.status_code == 200
    data = response.json()
    assert "trust_score" in data
    assert "total_attacks" in data
    assert "per_class" in data
    assert 0.0 <= data["trust_score"] <= 100.0


def test_assure_endpoint_in_openapi(api_client):
    spec = api_client.get("/openapi.json").json()
    assert "/v1/assure" in spec["paths"]
