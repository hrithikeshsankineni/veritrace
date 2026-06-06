"""Chroma vector store wrapper with mandatory tenant isolation.

Every write and every query MUST carry a tenant_id.  The tenant_id is stored
as metadata and applied as a `where` filter on every query, so cross-tenant
leakage is structurally impossible at the store layer.

Public API
----------
VectorStore(collection_name, persist_directory)
    .add(chunks, embeddings)
    .query(query_embedding, tenant_id, top_k) -> list[SearchResult]
    .delete_tenant(tenant_id)
    .count(tenant_id) -> int

SearchResult TypedDict:
  "chunk_id"   : str
  "text"       : str
  "score"      : float   — cosine similarity (0–1)
  "metadata"   : dict
"""

from __future__ import annotations

from typing import Optional, TypedDict

from veritrace.config import settings
from veritrace.ingest.chunker import Chunk


class SearchResult(TypedDict):
    chunk_id: str
    text: str
    score: float
    metadata: dict


class VectorStore:
    """Chroma-backed vector store with per-tenant isolation."""

    def __init__(
        self,
        collection_name: str = "veritrace",
        persist_directory: Optional[str] = None,
    ) -> None:
        import chromadb

        persist_dir = persist_directory or settings.chroma_path
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """Add chunks with their embeddings to the store.

        Each chunk MUST have a tenant_id in its metadata.  The tenant_id is
        stored as a top-level metadata key to enable fast filtering.
        """
        if not chunks:
            return

        ids: list[str] = []
        docs: list[str] = []
        metas: list[dict] = []
        embeds: list[list[float]] = []

        for chunk, emb in zip(chunks, embeddings):
            meta = dict(chunk["metadata"])
            tenant_id = meta.get("tenant_id", settings.default_tenant)
            meta["tenant_id"] = tenant_id      # ensure top-level key
            meta["chunk_id"] = chunk["chunk_id"]
            meta["heading"] = chunk.get("heading", "")
            meta["section"] = chunk.get("section", "")

            ids.append(chunk["chunk_id"])
            docs.append(chunk["text"])
            metas.append(meta)
            embeds.append(emb)

        self._collection.add(
            ids=ids,
            documents=docs,
            metadatas=metas,
            embeddings=embeds,
        )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def query(
        self,
        query_embedding: list[float],
        tenant_id: str,
        top_k: int = 20,
    ) -> list[SearchResult]:
        """Return the top-k most similar chunks for *tenant_id* only.

        The tenant_id filter is always applied — callers cannot opt out.
        """
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, max(1, self.count(tenant_id))),
            where={"tenant_id": {"$eq": tenant_id}},
            include=["documents", "metadatas", "distances"],
        )

        results: list[SearchResult] = []
        docs = result.get("documents") or [[]]
        metas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[]]

        for doc, meta, dist in zip(docs[0], metas[0], distances[0]):
            # Chroma cosine distance ∈ [0, 2]; convert to similarity [0, 1]
            score = float(max(0.0, 1.0 - dist / 2.0))
            results.append(
                SearchResult(
                    chunk_id=meta.get("chunk_id", ""),
                    text=doc,
                    score=score,
                    metadata=dict(meta),
                )
            )

        return results

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def count(self, tenant_id: Optional[str] = None) -> int:
        """Return the number of chunks for a tenant (or total if None)."""
        if tenant_id is None:
            return self._collection.count()
        result = self._collection.get(
            where={"tenant_id": {"$eq": tenant_id}},
            include=[],
        )
        return len(result.get("ids") or [])

    def delete_tenant(self, tenant_id: str) -> None:
        """Delete all chunks belonging to *tenant_id*."""
        result = self._collection.get(
            where={"tenant_id": {"$eq": tenant_id}},
            include=[],
        )
        ids = result.get("ids") or []
        if ids:
            self._collection.delete(ids=ids)
