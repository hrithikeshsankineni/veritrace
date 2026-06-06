"""OpenAI client wrapper with mock stubs.

Public API
----------
complete(tier, messages, **kwargs) -> str
    Call the LLM at the given tier ("mini" | "nano") and return the text of
    the first choice.  When MOCK_LLM=true returns a deterministic stub.

embed(texts) -> list[list[float]]
    Embed a list of strings with text-embedding-3-small.
    When MOCK_LLM=true returns deterministic unit vectors (dim=8).

Both functions raise on unrecoverable errors; callers should handle them.
"""

from __future__ import annotations

import hashlib
from typing import Literal

from veritrace.config import settings

Tier = Literal["mini", "nano"]

# Mock embedding dimensionality — small enough for fast tests
_MOCK_EMBED_DIM = 8


def _mock_embed(text: str) -> list[float]:
    """Return a deterministic unit vector derived from the text hash."""
    digest = hashlib.sha256(text.encode()).digest()
    raw = [int(b) - 128 for b in digest[:_MOCK_EMBED_DIM]]
    norm = (sum(x * x for x in raw) ** 0.5) or 1.0
    return [x / norm for x in raw]


def _mock_complete(tier: Tier, messages: list[dict]) -> str:
    """Return a deterministic stub response based on the last user message."""
    last = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user"),
        "default",
    )
    digest = hashlib.sha256(f"{tier}:{last}".encode()).hexdigest()[:8]
    return (
        f"[MOCK:{tier}] This is a deterministic stub response. "
        f"Query hash: {digest}. "
        "Based on the provided context, the answer is grounded in the source documents."
    )


def _tier_model(tier: Tier) -> str:
    return settings.mini_model if tier == "mini" else settings.nano_model


def complete(tier: Tier, messages: list[dict], **kwargs: object) -> str:
    """Return the LLM text response for *messages* using the given tier.

    Parameters
    ----------
    tier:
        "mini" -> settings.mini_model; "nano" -> settings.nano_model.
    messages:
        OpenAI-format message list, e.g. [{"role": "user", "content": "..."}].
    **kwargs:
        Forwarded to openai.chat.completions.create (e.g. temperature, max_tokens).
        Ignored in mock mode.
    """
    if settings.mock_llm:
        return _mock_complete(tier, messages)

    import openai  # deferred import — not needed in mock mode

    client = openai.OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=_tier_model(tier),
        messages=messages,  # type: ignore[arg-type]
        **kwargs,
    )
    return response.choices[0].message.content or ""


def embed(texts: list[str]) -> list[list[float]]:
    """Return embeddings for each text string.

    Parameters
    ----------
    texts:
        Non-empty list of strings to embed.

    Returns
    -------
    list of float lists, one per input text.
    """
    if not texts:
        return []

    if settings.mock_llm:
        return [_mock_embed(t) for t in texts]

    import openai  # deferred import

    client = openai.OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(
        model=settings.embed_model,
        input=texts,
    )
    return [item.embedding for item in response.data]
