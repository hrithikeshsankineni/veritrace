"""Tests for api/main.py FastAPI skeleton."""

import os

import pytest
from fastapi.testclient import TestClient

os.environ["MOCK_LLM"] = "true"

from api.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_query_stub_returns_trust_receipt():
    response = client.post(
        "/v1/query",
        json={"query": "Is atorvastatin covered?", "tenant_id": "demo"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "request_id" in data
    assert data["request_id"].startswith("rq_")
    assert "answer" in data
    assert data["tenant"] == "demo"
    assert "confidence" in data
    assert "timestamp" in data


def test_query_stub_missing_query():
    response = client.post("/v1/query", json={})
    assert response.status_code == 422  # validation error


def test_receipt_not_found():
    response = client.get("/v1/receipts/rq_nonexistent")
    assert response.status_code == 404


def test_sources_stub():
    response = client.get("/v1/sources?tenant_id=demo")
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "demo"
    assert isinstance(data["sources"], list)


def test_usage_stub():
    response = client.get("/v1/usage?tenant_id=demo")
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "demo"


def test_openapi_docs_available():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert spec["info"]["title"] == "Veritrace"
    # Key endpoints present in spec
    paths = spec["paths"]
    assert "/health" in paths
    assert "/v1/query" in paths
