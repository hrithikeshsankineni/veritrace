"""Tests for the eval harness structure (mock mode)."""

from __future__ import annotations

import json
import os
os.environ["MOCK_LLM"] = "true"

from pathlib import Path

GOLDEN_FILE = Path(__file__).parent.parent / "evals" / "golden.jsonl"


def _load_golden():
    cases = []
    with open(GOLDEN_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def test_golden_file_exists():
    assert GOLDEN_FILE.exists()


def test_golden_has_40_cases():
    cases = _load_golden()
    assert len(cases) == 40


def test_golden_required_fields():
    required = {"id", "category", "query", "expected_behavior"}
    for case in _load_golden():
        assert required.issubset(case.keys()), f"Case {case.get('id')} missing fields"


def test_golden_ids_unique():
    cases = _load_golden()
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids))


def test_golden_categories_cover_all_dimensions():
    cases = _load_golden()
    cats = {c["category"] for c in cases}
    expected_cats = {
        "grounded_answer", "abstention", "conflict_resolution",
        "injection_block", "pii_protection", "out_of_scope", "domain_refusal",
    }
    assert expected_cats.issubset(cats)


def test_golden_expected_behaviors_valid():
    valid = {
        "answer", "abstain", "blocked", "refused_or_abstained",
        "blocked_or_redacted", "answer_with_redaction", "abstain_or_answer",
    }
    for case in _load_golden():
        assert case["expected_behavior"] in valid, \
            f"Case {case['id']} has invalid expected_behavior: {case['expected_behavior']}"


def test_behavior_matches_helper():
    from evals.__main__ import _behavior_matches
    assert _behavior_matches("answer", "answer")
    assert _behavior_matches("blocked", "refused")
    assert _behavior_matches("abstain", "abstained")
    assert _behavior_matches("refused_or_abstained", "blocked")
    assert not _behavior_matches("answer", "abstained")
    assert not _behavior_matches("blocked", "answer")


def test_load_golden_helper():
    cases = _load_golden()
    assert all(isinstance(c, dict) for c in cases)


def test_runner_runs_single_case_mock(tmp_path):
    """Smoke-test: run one case in mock mode — should not crash."""
    from veritrace.index.store import VectorStore
    from veritrace.index.embeddings import embed_chunks
    from veritrace.ingest.chunker import Chunk
    import hashlib

    def _chunk(text, source_id):
        cid = hashlib.sha256(f"{source_id}:{text}".encode()).hexdigest()[:16]
        return Chunk(chunk_id=cid, text=text, heading="", section="",
                     metadata={"source_id": source_id, "tenant_id": "demo",
                                "effective_date": "2026-01-01"})

    store = VectorStore(collection_name="eval_smoke", persist_directory=str(tmp_path))
    chunks = [
        _chunk("Generic atorvastatin is covered at Tier 1 with a $10 copay.", "formulary_2026"),
        _chunk("The annual deductible is $500.", "coverage_policy"),
    ]
    store.add(chunks, embed_chunks(chunks))

    from evals.__main__ import _run_case
    case = {
        "id": "smoke_01",
        "category": "grounded_answer",
        "query": "Is atorvastatin covered?",
        "expected_behavior": "answer",
        "expected_keywords": [],
        "must_not_contain": [],
        "notes": "smoke test",
    }
    result = _run_case(case, store, "demo")
    assert "passed" in result
    assert "actual_behavior" in result
    assert "answer" in result
