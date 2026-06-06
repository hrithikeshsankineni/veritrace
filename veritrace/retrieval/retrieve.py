"""Wide-candidate retrieval — tenant-filtered vector search.

Public API
----------
retrieve(query, tenant_id, store, top_k) -> list[SearchResult]
    Embed the query and return the top-k most similar chunks for the tenant.
    The tenant_id filter is enforced at the store layer (see index/store.py).
"""

from __future__ import annotations

from veritrace.config import settings
from veritrace.index.embeddings import embed_query
from veritrace.index.store import SearchResult, VectorStore


def retrieve(
    query: str,
    tenant_id: str,
    store: VectorStore,
    top_k: int | None = None,
) -> list[SearchResult]:
    """Return up to *top_k* tenant-scoped candidates for *query*.

    Parameters
    ----------
    query:
        Already-rewritten query string.
    tenant_id:
        Tenant scope; passed through to the store's mandatory filter.
    store:
        A VectorStore instance (shared by the application).
    top_k:
        Number of candidates to retrieve (default: settings.retrieval_top_k_wide).
    """
    k = top_k if top_k is not None else settings.retrieval_top_k_wide
    query_vec = embed_query(query)
    return store.query(query_vec, tenant_id=tenant_id, top_k=k)
