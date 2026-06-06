"""Embedding helper — wraps llm.embed for use by the index layer.

Public API
----------
embed_chunks(chunks) -> list[list[float]]
    Embed a list of Chunk dicts, returning one vector per chunk.

embed_query(text) -> list[float]
    Embed a single query string.
"""

from __future__ import annotations

from veritrace.ingest.chunker import Chunk
from veritrace.llm import embed


def embed_chunks(chunks: list[Chunk]) -> list[list[float]]:
    """Return one embedding vector per chunk (in order)."""
    texts = [c["text"] for c in chunks]
    return embed(texts)


def embed_query(text: str) -> list[float]:
    """Return the embedding vector for a single query string."""
    result = embed([text])
    return result[0]
