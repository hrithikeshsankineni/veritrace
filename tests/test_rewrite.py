"""Tests for veritrace.retrieval.rewrite."""

from __future__ import annotations

import os

os.environ["MOCK_LLM"] = "true"

from veritrace.retrieval.rewrite import rewrite


def test_rewrite_returns_string():
    result = rewrite("Is atorvastatin covered?")
    assert isinstance(result, str)
    assert len(result) > 0


def test_rewrite_is_deterministic():
    q = "what's the copay for generic statins?"
    assert rewrite(q) == rewrite(q)


def test_rewrite_non_empty_input():
    result = rewrite("um, like, does my plan cover, you know, the generic version of lipitor?")
    assert isinstance(result, str)
    assert len(result) > 0


def test_rewrite_empty_passthrough():
    assert rewrite("") == ""


def test_rewrite_whitespace_passthrough():
    assert rewrite("   ") == ""


def test_rewrite_different_inputs_differ():
    r1 = rewrite("What is the copay for atorvastatin?")
    r2 = rewrite("Does prior authorization apply to biologics?")
    assert r1 != r2
