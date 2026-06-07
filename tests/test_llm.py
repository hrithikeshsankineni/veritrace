"""Tests for veritrace.config and veritrace.llm in MOCK_LLM mode."""

import os

import pytest

# Force mock mode before importing the module
os.environ["MOCK_LLM"] = "true"


from veritrace.config import Settings  # noqa: E402
from veritrace.llm import complete, embed  # noqa: E402


def test_settings_mock_default():
    s = Settings()
    assert s.mock_llm is True


def test_settings_model_names():
    s = Settings()
    assert s.mini_model
    assert s.nano_model
    assert s.embed_model


def test_complete_mini_returns_string():
    messages = [{"role": "user", "content": "What is covered?"}]
    result = complete("mini", messages)
    assert isinstance(result, str)
    assert len(result) > 0


def test_complete_nano_returns_string():
    messages = [{"role": "user", "content": "Rewrite this query."}]
    result = complete("nano", messages)
    assert isinstance(result, str)


def test_complete_is_deterministic():
    messages = [{"role": "user", "content": "Test determinism"}]
    assert complete("mini", messages) == complete("mini", messages)


def test_complete_differs_by_tier():
    messages = [{"role": "user", "content": "Same question"}]
    assert complete("mini", messages) != complete("nano", messages)


def test_complete_differs_by_content():
    msg_a = [{"role": "user", "content": "Question A"}]
    msg_b = [{"role": "user", "content": "Question B"}]
    assert complete("mini", msg_a) != complete("mini", msg_b)


def test_embed_returns_list_of_floats():
    result = embed(["hello world"])
    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], list)
    assert all(isinstance(x, float) for x in result[0])


def test_embed_multiple_texts():
    result = embed(["text one", "text two", "text three"])
    assert len(result) == 3


def test_embed_is_deterministic():
    assert embed(["deterministic"]) == embed(["deterministic"])


def test_embed_differs_by_content():
    a = embed(["apple"])[0]
    b = embed(["orange"])[0]
    assert a != b


def test_embed_empty_returns_empty():
    assert embed([]) == []


def test_embed_unit_norm_approx():
    vec = embed(["normalize me"])[0]
    norm_sq = sum(x * x for x in vec)
    assert abs(norm_sq - 1.0) < 1e-6


def test_provider_selection_groq_when_no_openai_key():
    """When OPENAI_API_KEY is empty and GROQ_API_KEY is set, provider resolves to groq."""
    from veritrace.llm import _detect_provider
    from veritrace.config import Settings
    import veritrace.llm as llm_module

    groq_settings = Settings(mock_llm=False, openai_api_key="", groq_api_key="gsk_test")
    original = llm_module.settings
    try:
        llm_module.settings = groq_settings
        provider = _detect_provider()
        assert provider == "groq"
    finally:
        llm_module.settings = original
