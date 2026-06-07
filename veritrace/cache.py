"""Semantic cache — short-circuit repeat / near-duplicate queries.

Public API
----------
SemanticCache
    In-process cache keyed by (tenant_id, query_embedding).
    A query hits the cache if its cosine similarity to a stored embedding
    exceeds SIMILARITY_THRESHOLD.

get(tenant_id, embedding) -> TrustReceipt | None
    Return cached receipt if a similar query exists, else None.

put(tenant_id, query, embedding, receipt) -> None
    Store a receipt against its embedding.

Cache design
------------
- Similarity threshold: 0.92 (conservative — only true near-duplicates hit)
- Max entries per tenant: 256 (LRU eviction)
- In-process only (cleared on restart) — sufficient for demo
- Thread-safe via lock
- In mock mode the mock embeddings are 8-dim so similarity is still
  computed correctly; thresholds are the same.
"""

from __future__ import annotations

import math
import threading
from collections import OrderedDict
from typing import Optional

from veritrace.schemas import TrustReceipt

SIMILARITY_THRESHOLD: float = 0.92
MAX_ENTRIES_PER_TENANT: int = 256


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two unit-ish vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticCache:
    """Thread-safe in-process semantic cache."""

    def __init__(
        self,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
        max_entries: int = MAX_ENTRIES_PER_TENANT,
    ) -> None:
        self._lock = threading.Lock()
        # tenant_id → OrderedDict of (query_text → (embedding, receipt))
        self._store: dict[str, OrderedDict] = {}
        self._threshold = similarity_threshold
        self._max_entries = max_entries

    def get(
        self, tenant_id: str, embedding: list[float]
    ) -> Optional[TrustReceipt]:
        """Return a cached receipt if a similar query exists, else None."""
        with self._lock:
            tenant_store = self._store.get(tenant_id)
            if not tenant_store:
                return None
            best_score = 0.0
            best_receipt: Optional[TrustReceipt] = None
            for _query, (stored_emb, stored_receipt) in tenant_store.items():
                score = _cosine(embedding, stored_emb)
                if score > best_score:
                    best_score = score
                    best_receipt = stored_receipt
            if best_score >= self._threshold:
                return best_receipt
            return None

    def put(
        self,
        tenant_id: str,
        query: str,
        embedding: list[float],
        receipt: TrustReceipt,
    ) -> None:
        """Store a receipt. Evicts oldest entry if over capacity."""
        with self._lock:
            if tenant_id not in self._store:
                self._store[tenant_id] = OrderedDict()
            store = self._store[tenant_id]
            store[query] = (embedding, receipt)
            store.move_to_end(query)
            while len(store) > self._max_entries:
                store.popitem(last=False)

    def size(self, tenant_id: str) -> int:
        with self._lock:
            return len(self._store.get(tenant_id, {}))

    def clear(self, tenant_id: Optional[str] = None) -> None:
        with self._lock:
            if tenant_id:
                self._store.pop(tenant_id, None)
            else:
                self._store.clear()


# Module-level singleton used by the API
_cache = SemanticCache()


def get_cached(tenant_id: str, embedding: list[float]) -> Optional[TrustReceipt]:
    return _cache.get(tenant_id, embedding)


def cache_put(
    tenant_id: str, query: str, embedding: list[float], receipt: TrustReceipt
) -> None:
    _cache.put(tenant_id, query, embedding, receipt)
