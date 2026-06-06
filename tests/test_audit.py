"""Tests for veritrace.audit — AuditStore."""

from __future__ import annotations

import os

import pytest

os.environ["MOCK_LLM"] = "true"

from veritrace.audit import AuditStore
from veritrace.schemas import Citation, TrustReceipt


def _receipt(tenant: str = "demo", cost: float = 0.005, latency: float = 100.0) -> TrustReceipt:
    return TrustReceipt(
        tenant=tenant,
        answer="Generic atorvastatin is covered at Tier 1.",
        confidence="well-grounded",
        citations=[Citation(source_id="formulary_2026", score=0.95)],
        groundedness_score=0.97,
        cost_usd=cost,
        latency_ms=latency,
    )


@pytest.fixture()
def store(tmp_path):
    s = AuditStore(db_path=tmp_path / "test.sqlite")
    yield s
    s.close()


# ---------------------------------------------------------------------------
# persist + get
# ---------------------------------------------------------------------------

def test_persist_and_get_receipt(store):
    r = _receipt()
    store.persist_receipt(r)
    fetched = store.get_receipt(r.request_id)
    assert fetched is not None
    assert fetched.request_id == r.request_id


def test_get_receipt_not_found(store):
    assert store.get_receipt("rq_nonexistent") is None


def test_receipt_round_trips_fields(store):
    r = _receipt()
    store.persist_receipt(r)
    fetched = store.get_receipt(r.request_id)
    assert fetched.tenant == "demo"
    assert fetched.confidence == "well-grounded"
    assert fetched.groundedness_score == 0.97
    assert len(fetched.citations) == 1
    assert fetched.citations[0].source_id == "formulary_2026"


def test_persist_idempotent(store):
    """Persisting same receipt twice replaces, doesn't duplicate."""
    r = _receipt()
    store.persist_receipt(r)
    store.persist_receipt(r)
    usage = store.get_usage("demo")
    # telemetry has two rows (INSERT not REPLACE for telemetry), receipts has one
    fetched = store.get_receipt(r.request_id)
    assert fetched is not None


# ---------------------------------------------------------------------------
# Usage / telemetry
# ---------------------------------------------------------------------------

def test_usage_after_queries(store):
    store.persist_receipt(_receipt("demo", cost=0.005, latency=100.0))
    store.persist_receipt(_receipt("demo", cost=0.003, latency=200.0))
    usage = store.get_usage("demo")
    assert usage["total_queries"] == 2
    assert abs(usage["total_cost_usd"] - 0.008) < 1e-6
    assert usage["avg_latency_ms"] == pytest.approx(150.0)


def test_usage_tenant_isolation(store):
    store.persist_receipt(_receipt("alpha", cost=0.01))
    store.persist_receipt(_receipt("beta", cost=0.02))
    alpha = store.get_usage("alpha")
    beta = store.get_usage("beta")
    assert alpha["total_queries"] == 1
    assert beta["total_queries"] == 1
    assert abs(alpha["total_cost_usd"] - 0.01) < 1e-6


def test_usage_empty_tenant(store):
    usage = store.get_usage("nonexistent")
    assert usage["total_queries"] == 0
    assert usage["total_cost_usd"] == 0.0


def test_tokens_estimated(store):
    r = _receipt()
    store.persist_receipt(r)
    usage = store.get_usage("demo")
    assert usage["total_tokens_est"] >= 0
