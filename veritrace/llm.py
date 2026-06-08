"""LLM client wrapper with provider selection and mock stubs.

Provider selection (evaluated once at import time):
  MOCK_LLM=true                           → deterministic stubs, no network
  MOCK_LLM=false, OPENAI_API_KEY set      → OpenAI (gpt-5.4-mini / gpt-5.4-nano)
  MOCK_LLM=false, OPENAI_API_KEY empty,
                  GROQ_API_KEY set        → Groq  (llama-3.3-70b / llama-3.1-8b)

Embeddings:
  mock / OpenAI  → OpenAI text-embedding-3-small (or mock unit vectors)
  Groq           → local sentence-transformers all-MiniLM-L6-v2 (Groq has no embed API)

Public API
----------
complete(tier, messages, **kwargs) -> str
embed(texts) -> list[list[float]]
"""

from __future__ import annotations

import hashlib
from typing import Literal

from veritrace.config import settings

Tier = Literal["mini", "nano"]

_MOCK_EMBED_DIM = 8

# ---------------------------------------------------------------------------
# Provider detection (runs once on import)
# ---------------------------------------------------------------------------

def _detect_provider() -> str:
    if settings.mock_llm:
        return "mock"
    if settings.openai_api_key and not settings.openai_api_key.startswith("sk-MOCK"):
        return "openai"
    if settings.groq_api_key:
        return "groq"
    # No real keys — fall back to mock rather than crash
    return "mock"


_PROVIDER = _detect_provider()

_PROVIDER_LABELS = {
    "mock": "LLM provider: mock",
    "openai": f"LLM provider: openai ({settings.mini_model} / {settings.nano_model})",
    "groq": f"LLM provider: groq ({settings.groq_mini_model} / {settings.groq_nano_model})",
}
print(_PROVIDER_LABELS[_PROVIDER])

# ---------------------------------------------------------------------------
# Mock stubs
# ---------------------------------------------------------------------------

def _mock_embed(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode()).digest()
    raw = [int(b) - 128 for b in digest[:_MOCK_EMBED_DIM]]
    norm = (sum(x * x for x in raw) ** 0.5) or 1.0
    return [x / norm for x in raw]


def _mock_complete(tier: Tier, messages: list[dict]) -> str:
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

# ---------------------------------------------------------------------------
# Model name helpers
# ---------------------------------------------------------------------------

def _openai_model(tier: Tier) -> str:
    return settings.mini_model if tier == "mini" else settings.nano_model


def _groq_model(tier: Tier) -> str:
    return settings.groq_mini_model if tier == "mini" else settings.groq_nano_model

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def complete(tier: Tier, messages: list[dict], **kwargs: object) -> str:
    """Return the LLM text response for *messages* using the given tier."""
    if _PROVIDER == "mock":
        return _mock_complete(tier, messages)

    if _PROVIDER == "openai":
        import openai
        client = openai.OpenAI(api_key=settings.openai_api_key)
        # gpt-5.4-* uses max_completion_tokens; translate max_tokens if passed
        if "max_tokens" in kwargs:
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
        response = client.chat.completions.create(
            model=_openai_model(tier),
            messages=messages,  # type: ignore[arg-type]
            **kwargs,
        )
        return response.choices[0].message.content or ""

    # groq — OpenAI-compatible client
    from groq import Groq
    client = Groq(api_key=settings.groq_api_key)
    response = client.chat.completions.create(
        model=_groq_model(tier),
        messages=messages,  # type: ignore[arg-type]
        **kwargs,
    )
    return response.choices[0].message.content or ""


def embed(texts: list[str]) -> list[list[float]]:
    """Return embeddings for each text string."""
    if not texts:
        return []

    if _PROVIDER == "mock":
        return [_mock_embed(t) for t in texts]

    if _PROVIDER == "openai":
        import openai
        client = openai.OpenAI(api_key=settings.openai_api_key)
        response = client.embeddings.create(
            model=settings.embed_model,
            input=texts,
        )
        return [item.embedding for item in response.data]

    # groq — no embed API; use local sentence-transformers model
    from sentence_transformers import SentenceTransformer
    _groq_embed_model = _get_groq_embed_model()
    vecs = _groq_embed_model.encode(texts, convert_to_numpy=True)
    return [v.tolist() for v in vecs]


# Module-level cache for the local embed model (only instantiated when needed)
_groq_embed_model_cache: object = None


def _get_groq_embed_model():
    global _groq_embed_model_cache
    if _groq_embed_model_cache is None:
        from sentence_transformers import SentenceTransformer
        _groq_embed_model_cache = SentenceTransformer("all-MiniLM-L6-v2")
    return _groq_embed_model_cache
