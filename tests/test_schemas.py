"""Tests for veritrace.schemas — model validation and JSON round-trip."""

import json
from datetime import datetime, timezone

import pytest

from veritrace.schemas import (
    ActionInfo,
    AssuranceReport,
    AttackResult,
    Citation,
    ConflictInfo,
    QueryRequest,
    RedactionInfo,
    RefusalInfo,
    Source,
    TrustReceipt,
)


# ---------------------------------------------------------------------------
# QueryRequest
# ---------------------------------------------------------------------------

def test_query_request_valid():
    q = QueryRequest(query="Is atorvastatin covered?")
    assert q.query == "Is atorvastatin covered?"
    assert q.tenant_id == "demo"


def test_query_request_requires_query():
    with pytest.raises(Exception):
        QueryRequest(query="")


def test_query_request_custom_tenant():
    q = QueryRequest(query="test", tenant_id="acme")
    assert q.tenant_id == "acme"


# ---------------------------------------------------------------------------
# Citation
# ---------------------------------------------------------------------------

def test_citation_valid():
    c = Citation(source_id="formulary_2026", score=0.93)
    assert c.source_id == "formulary_2026"
    assert c.score == 0.93


def test_citation_score_bounds():
    with pytest.raises(Exception):
        Citation(source_id="x", score=1.5)
    with pytest.raises(Exception):
        Citation(source_id="x", score=-0.1)


# ---------------------------------------------------------------------------
# TrustReceipt
# ---------------------------------------------------------------------------

def test_trust_receipt_defaults():
    r = TrustReceipt(tenant="demo", answer="Generic atorvastatin is covered.")
    assert r.request_id.startswith("rq_")
    assert r.route == "knowledge"
    assert r.confidence == "well-grounded"
    assert isinstance(r.timestamp, datetime)
    assert r.conflict.detected is False
    assert r.redaction.applied is False
    assert r.refusal.triggered is False
    assert r.action is None


def test_trust_receipt_json_roundtrip():
    r = TrustReceipt(
        tenant="demo",
        answer="Covered at Tier 1 copay.",
        citations=[Citation(source_id="formulary_2026", score=0.93, section="Tier 1")],
        groundedness_score=0.97,
        cost_usd=0.0046,
        latency_ms=1410,
    )
    serialized = r.model_dump_json()
    parsed = TrustReceipt.model_validate_json(serialized)
    assert parsed.request_id == r.request_id
    assert parsed.answer == r.answer
    assert parsed.groundedness_score == r.groundedness_score
    assert len(parsed.citations) == 1
    assert parsed.citations[0].source_id == "formulary_2026"


def test_trust_receipt_with_redaction():
    r = TrustReceipt(
        tenant="demo",
        answer="Answer for member [MEMBER_ID_1].",
        redaction=RedactionInfo(applied=True, types=["member_id"]),
    )
    assert r.redaction.applied is True
    assert "member_id" in r.redaction.types


def test_trust_receipt_abstention():
    r = TrustReceipt(
        tenant="demo",
        answer="I do not have sufficient information to answer this question.",
        confidence="abstained",
    )
    assert r.confidence == "abstained"


def test_trust_receipt_with_conflict():
    r = TrustReceipt(
        tenant="demo",
        answer="The current policy says X.",
        conflict=ConflictInfo(
            detected=True,
            description="2024 policy says Y, 2026 says X.",
            resolved_to="policy_2026",
        ),
    )
    assert r.conflict.detected is True
    assert r.conflict.resolved_to == "policy_2026"


def test_trust_receipt_with_refusal():
    r = TrustReceipt(
        tenant="demo",
        answer="",
        route="refused",
        refusal=RefusalInfo(triggered=True, reason="Out-of-scope clinical advice."),
    )
    assert r.refusal.triggered is True


def test_trust_receipt_request_id_unique():
    r1 = TrustReceipt(tenant="demo", answer="A")
    r2 = TrustReceipt(tenant="demo", answer="B")
    assert r1.request_id != r2.request_id


# ---------------------------------------------------------------------------
# AssuranceReport
# ---------------------------------------------------------------------------

def test_assurance_report_valid():
    report = AssuranceReport(
        tenant="demo",
        trust_score=82.5,
        total_attacks=10,
        passed=8,
        failed=2,
    )
    assert report.report_id.startswith("ar_")
    assert report.trust_score == 82.5


def test_assurance_report_score_bounds():
    with pytest.raises(Exception):
        AssuranceReport(tenant="x", trust_score=101, total_attacks=1, passed=1, failed=0)


def test_assurance_report_json_roundtrip():
    report = AssuranceReport(
        tenant="demo",
        trust_score=75.0,
        total_attacks=4,
        passed=3,
        failed=1,
        findings=["injection not blocked on attack #3"],
    )
    parsed = AssuranceReport.model_validate_json(report.model_dump_json())
    assert parsed.report_id == report.report_id
    assert len(parsed.findings) == 1
