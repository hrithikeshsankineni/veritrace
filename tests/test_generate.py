"""Tests for veritrace.responder.generate."""

from __future__ import annotations

import os

import pytest

os.environ["MOCK_LLM"] = "true"

from veritrace.retrieval.rerank import RankedResult
from veritrace.responder.generate import generate, GenerationResult


def _result(text: str, source_id: str = "formulary_2026", rerank_score: float = 0.7) -> RankedResult:
    return RankedResult(
        chunk_id="abc",
        text=text,
        score=0.8,
        rerank_score=rerank_score,
        metadata={"source_id": source_id, "tenant_id": "demo", "heading": "Statins"},
    )


# ---------------------------------------------------------------------------
# Basic
# ---------------------------------------------------------------------------

def test_generate_returns_result():
    result = generate("What is the copay for atorvastatin?", [_result("Atorvastatin Tier 1 $10.")])
    assert isinstance(result, dict)
    assert "answer" in result
    assert "citations" in result
    assert "groundedness_score" in result


def test_generate_answer_is_non_empty():
    result = generate("Is atorvastatin covered?", [_result("Atorvastatin covered Tier 1.")])
    assert len(result["answer"]) > 0


def test_generate_no_candidates_abstains():
    result = generate("What is covered?", [])
    assert "sufficient information" in result["answer"].lower()
    assert result["citations"] == []
    assert result["groundedness_score"] == 0.0


def test_generate_citations_have_source_id():
    result = generate("drug coverage", [_result("Covered drug.", "formulary_2026")])
    # Mock always cites [1] from the first candidate
    if result["citations"]:
        assert result["citations"][0].source_id == "formulary_2026"


def test_generate_groundedness_score_in_range():
    result = generate("query", [_result("text", rerank_score=0.8)])
    assert 0.0 <= result["groundedness_score"] <= 1.0


def test_generate_is_deterministic():
    candidates = [_result("Same text.")]
    r1 = generate("Same query", candidates)
    r2 = generate("Same query", candidates)
    assert r1["answer"] == r2["answer"]


def test_generate_multiple_candidates():
    candidates = [
        _result("Drug A is Tier 1.", "formulary_2026", 0.9),
        _result("Drug B is Tier 2.", "formulary_2026", 0.6),
    ]
    result = generate("drug tiers", candidates)
    assert result["answer"]
    assert isinstance(result["citations"], list)
