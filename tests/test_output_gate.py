"""Tests for veritrace.safety.output_gate."""

from __future__ import annotations

import os

import pytest

os.environ["MOCK_LLM"] = "true"

from veritrace.retrieval.rerank import RankedResult
from veritrace.safety.output_gate import check_output


def _result(text: str) -> RankedResult:
    return RankedResult(
        chunk_id="abc",
        text=text,
        score=0.8,
        rerank_score=0.7,
        metadata={"source_id": "formulary_2026", "tenant_id": "demo"},
    )


# ---------------------------------------------------------------------------
# Domain refusal
# ---------------------------------------------------------------------------

def test_clinical_advice_blocked():
    answer = "You should take atorvastatin 80mg instead of 40mg."
    result = check_output(answer, "drug advice", [_result("Atorvastatin coverage.")])
    assert result["passed"] is False
    assert result["gate_type"] == "domain_refusal"
    assert result["reason"] is not None


def test_prescribe_blocked():
    answer = "I prescribe you 10mg of atorvastatin daily."
    result = check_output(answer, "query", [_result("Atorvastatin Tier 1.")])
    assert result["passed"] is False
    assert result["gate_type"] == "domain_refusal"


def test_recommend_you_take_blocked():
    answer = "I recommend you take this medication twice daily."
    result = check_output(answer, "query", [_result("Medication coverage.")])
    assert result["passed"] is False
    assert result["gate_type"] == "domain_refusal"


# ---------------------------------------------------------------------------
# Grounded answers pass
# ---------------------------------------------------------------------------

def test_grounded_answer_passes():
    chunk_text = "Generic atorvastatin is covered at Tier 1 with a $10 copay."
    answer = "Generic atorvastatin covered under Tier 1, copay is $10."
    result = check_output(answer, "atorvastatin copay", [_result(chunk_text)])
    assert result["passed"] is True
    assert result["gate_type"] is None


def test_abstain_answer_passes():
    answer = "I do not have sufficient information in the available sources."
    result = check_output(answer, "query", [])
    assert result["passed"] is True


# ---------------------------------------------------------------------------
# Ungrounded answer blocked (mock: no word overlap)
# ---------------------------------------------------------------------------

def test_ungrounded_answer_blocked():
    """Answer about completely different topic from source chunks."""
    chunk_text = "Prior authorization is required for specialty biologics."
    answer = "The weather in Paris is sunny with a high of 75 degrees."
    result = check_output(answer, "query", [_result(chunk_text)])
    assert result["passed"] is False
    assert result["gate_type"] == "groundedness"


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

def test_passed_has_no_reason():
    chunk = "Coverage includes Tier 1 drugs with a standard copay."
    answer = "Coverage includes Tier 1 drugs."
    result = check_output(answer, "coverage", [_result(chunk)])
    if result["passed"]:
        assert result["reason"] is None
        assert result["gate_type"] is None


def test_blocked_has_reason():
    answer = "You should take this medication every morning."
    result = check_output(answer, "q", [_result("Drug coverage.")])
    assert result["reason"] is not None
