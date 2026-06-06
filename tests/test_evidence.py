"""Tests for veritrace.responder.evidence."""

from __future__ import annotations

import pytest

from veritrace.retrieval.rerank import RankedResult
from veritrace.responder.evidence import check_sufficiency, ABSTAIN_THRESHOLD, PARTIAL_THRESHOLD


def _result(text: str, rerank_score: float) -> RankedResult:
    return RankedResult(
        chunk_id="abc123",
        text=text,
        score=0.5,
        rerank_score=rerank_score,
        metadata={"tenant_id": "demo"},
    )


# ---------------------------------------------------------------------------
# Abstention cases
# ---------------------------------------------------------------------------

def test_no_candidates_abstains():
    result = check_sufficiency("What is covered?", [])
    assert result["sufficient"] is False
    assert result["confidence"] == "abstained"
    assert "no_evidence" in (result["abstain_reason"] or "")


def test_weak_evidence_abstains():
    candidates = [_result("Some text", rerank_score=ABSTAIN_THRESHOLD - 0.01)]
    result = check_sufficiency("What is covered?", candidates)
    assert result["sufficient"] is False
    assert result["confidence"] == "abstained"
    assert "weak_evidence" in (result["abstain_reason"] or "")


# ---------------------------------------------------------------------------
# Sufficient evidence
# ---------------------------------------------------------------------------

def test_well_grounded_sufficient():
    candidates = [_result("Atorvastatin Tier 1 $10.", rerank_score=PARTIAL_THRESHOLD + 0.1)]
    result = check_sufficiency("What is the copay?", candidates)
    assert result["sufficient"] is True
    assert result["confidence"] == "well-grounded"
    assert result["abstain_reason"] is None


def test_partially_grounded_sufficient():
    score = (ABSTAIN_THRESHOLD + PARTIAL_THRESHOLD) / 2
    candidates = [_result("Some relevant text.", rerank_score=score)]
    result = check_sufficiency("Some query", candidates)
    assert result["sufficient"] is True
    assert result["confidence"] == "partially-grounded"


# ---------------------------------------------------------------------------
# Threshold boundary
# ---------------------------------------------------------------------------

def test_at_abstain_threshold_proceeds():
    """Score exactly at abstain threshold is NOT abstained (>= check)."""
    candidates = [_result("Text", rerank_score=ABSTAIN_THRESHOLD)]
    result = check_sufficiency("query", candidates)
    assert result["sufficient"] is True


def test_just_below_abstain_threshold_abstains():
    candidates = [_result("Text", rerank_score=ABSTAIN_THRESHOLD - 0.001)]
    result = check_sufficiency("query", candidates)
    assert result["sufficient"] is False


# ---------------------------------------------------------------------------
# Top candidates passthrough
# ---------------------------------------------------------------------------

def test_top_candidates_returned():
    candidates = [_result(f"chunk {i}", rerank_score=0.6) for i in range(4)]
    result = check_sufficiency("query", candidates)
    assert result["top_candidates"] == candidates


def test_empty_top_candidates_on_abstain():
    result = check_sufficiency("query", [])
    assert result["top_candidates"] == []
