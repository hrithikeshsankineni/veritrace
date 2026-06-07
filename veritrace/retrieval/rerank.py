"""Cross-encoder re-ranker — precision second stage.

Uses the local sentence-transformers cross-encoder
`cross-encoder/ms-marco-MiniLM-L-6-v2` to score (query, passage) pairs and
return the top-k results sorted by cross-encoder score.

The cross-encoder model is loaded lazily and cached in a module-level
variable to avoid repeated disk reads.

In MOCK_LLM mode the cross-encoder is NOT loaded (avoids network/disk at
test time); instead a deterministic hash-based score is assigned so that
re-ranking still changes the order.

Public API
----------
rerank(query, candidates, top_k) -> list[RankedResult]
    Returns up to *top_k* results from *candidates*, sorted by cross-encoder
    score descending.  Each result has the same fields as SearchResult plus
    a "rerank_score" float.
"""

from __future__ import annotations

import hashlib
import re
from typing import TypedDict

from veritrace.config import settings
from veritrace.index.store import SearchResult

# Common domain words that appear in nearly every query AND every chunk —
# excluding them lets the overlap score reflect topic-specific relevance.
_MOCK_STOP: frozenset = frozenset([
    "covered", "coverage", "member", "members", "health", "plan", "plans",
    "under", "about", "medical", "dental", "their", "cosmetic",
])

_CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_encoder = None  # module-level cache


class RankedResult(TypedDict):
    chunk_id: str
    text: str
    score: float          # original vector similarity score
    rerank_score: float   # cross-encoder score (higher = more relevant)
    metadata: dict


def _get_encoder():
    global _encoder
    if _encoder is None:
        from sentence_transformers import CrossEncoder
        _encoder = CrossEncoder(_CROSS_ENCODER_MODEL)
    return _encoder


def _mock_score(query: str, text: str) -> float:
    """Deterministic mock cross-encoder score for testing.

    Uses keyword overlap (7+ char words, minus common domain stop-words) as
    the primary relevance signal so that queries about topics absent from the
    KB reliably score below the abstention threshold.  A small hash-based
    tiebreaker (≤0.14) preserves deterministic ordering when overlap is equal
    but keeps no-overlap scores strictly below the 0.15 abstain threshold.
    Falls back to the raw hash score when the query has no significant keywords
    (no filtering possible), so short queries never get unfairly penalised.
    """
    digest = hashlib.sha256(f"{query}:{text}".encode()).digest()
    hash_score = int(digest[0]) / 255.0

    q_words = {w for w in re.findall(r"\b\w{7,}\b", query.lower()) if w not in _MOCK_STOP}
    if not q_words:
        # No topic-specific keywords — use raw hash score (unchanged behaviour)
        return hash_score

    t_words = {w for w in re.findall(r"\b\w{7,}\b", text.lower()) if w not in _MOCK_STOP}
    overlap = len(q_words & t_words) / len(q_words)
    # 85 % overlap weight + up to 0.14 hash tiebreaker.
    # No-overlap → max 0.14 < ABSTAIN_THRESHOLD (0.15) → always abstains.
    return overlap * 0.85 + hash_score * 0.14


def rerank(
    query: str,
    candidates: list[SearchResult],
    top_k: int | None = None,
) -> list[RankedResult]:
    """Score *candidates* with the cross-encoder and return the top-k.

    Parameters
    ----------
    query:
        The (optionally rewritten) user query.
    candidates:
        Wide candidate set from the retrieval step.
    top_k:
        How many results to return (default: settings.retrieval_top_k_final).

    Returns
    -------
    List of RankedResult, sorted by rerank_score descending.
    """
    k = top_k if top_k is not None else settings.retrieval_top_k_final

    if not candidates:
        return []

    if settings.mock_llm:
        scores = [_mock_score(query, c["text"]) for c in candidates]
    else:
        encoder = _get_encoder()
        pairs = [(query, c["text"]) for c in candidates]
        raw_scores = encoder.predict(pairs)
        scores = [float(s) for s in raw_scores]

    ranked: list[RankedResult] = []
    for candidate, score in zip(candidates, scores):
        ranked.append(
            RankedResult(
                chunk_id=candidate["chunk_id"],
                text=candidate["text"],
                score=candidate["score"],
                rerank_score=score,
                metadata=candidate["metadata"],
            )
        )

    ranked.sort(key=lambda r: r["rerank_score"], reverse=True)
    return ranked[:k]
