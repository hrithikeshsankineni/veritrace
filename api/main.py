"""Veritrace FastAPI application — fully wired.

Endpoints:
  GET  /health                  — liveness probe
  POST /v1/query                — full pipeline: guardrails→redact→agent→gate→audit
  GET  /v1/receipts/{id}        — retrieve a sealed Trust Receipt
  GET  /v1/sources              — list indexed sources for a tenant
  GET  /v1/usage                — aggregate usage for a tenant
  POST /v1/assure               — run Assurance Engine scan → Trust Score + report

Startup lifecycle:
  - Seeds synthetic corpus if data/synthetic/ is empty.
  - Ingests all .md files in data/synthetic/ into the shared Chroma store
    for the default tenant.
  - Creates a singleton AuditStore.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from veritrace.assurance.attacks import generate_attacks
from veritrace.assurance.runner import run_attacks
from veritrace.assurance.score import compute_score
from veritrace.audit import AuditStore
from veritrace.config import settings
from veritrace.index.embeddings import embed_chunks
from veritrace.index.store import VectorStore
from veritrace.ingest.chunker import chunk as chunk_doc
from veritrace.ingest.parsers import parse
from veritrace.responder.agent import answer
from veritrace.safety.guardrails import check_input
from veritrace.safety.output_gate import check_output
from veritrace.safety.redaction import redact, restore
from veritrace.cache import cache_put, get_cached
from veritrace.memory import add_turn, get_history
from veritrace.schemas import QueryRequest, RedactionInfo, RefusalInfo, TrustReceipt

# ---------------------------------------------------------------------------
# Module-level singletons (initialised in lifespan)
# ---------------------------------------------------------------------------

_store: Optional[VectorStore] = None
_audit: Optional[AuditStore] = None

_DATA_DIR = Path(__file__).parent.parent / "data" / "synthetic"
_CHROMA_DIR = Path(settings.chroma_path)


def _ingest_corpus(store: VectorStore, tenant_id: str = settings.default_tenant) -> int:
    """Ingest all .md documents from data/synthetic/ for *tenant_id*.

    Returns number of chunks added.
    """
    md_files = sorted(_DATA_DIR.glob("*.md"))
    total = 0
    for md_file in md_files:
        doc = parse(md_file)
        # Override tenant_id to match the deployment tenant
        doc["metadata"]["tenant_id"] = tenant_id
        chunks = chunk_doc(doc)
        if not chunks:
            continue
        vecs = embed_chunks(chunks)
        store.add(chunks, vecs)
        total += len(chunks)
    return total


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _store, _audit

    # Seed data if missing
    if not _DATA_DIR.exists() or not list(_DATA_DIR.glob("*.md")):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from data.seed import seed
        seed()

    # Create store and ingest
    _store = VectorStore(collection_name="veritrace", persist_directory=str(_CHROMA_DIR))
    if _store.count(settings.default_tenant) == 0:
        n = _ingest_corpus(_store, settings.default_tenant)
        print(f"[startup] Ingested {n} chunks for tenant '{settings.default_tenant}'")
    else:
        print(f"[startup] Corpus already ingested ({_store.count(settings.default_tenant)} chunks).")

    # Create audit store
    _audit = AuditStore(db_path=settings.sqlite_path)

    yield

    # Cleanup
    if _audit:
        _audit.close()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Veritrace",
    description=(
        "An API-first platform that answers questions over a private knowledge base "
        "and proves the answers are safe."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", tags=["ops"])
def health() -> dict:
    """Liveness probe."""
    return {
        "status": "ok",
        "mock_llm": settings.mock_llm,
        "corpus_chunks": _store.count(settings.default_tenant) if _store else 0,
    }


# ---------------------------------------------------------------------------
# Query — full pipeline
# ---------------------------------------------------------------------------

@app.post("/v1/query", response_model=TrustReceipt, tags=["query"])
def query(request: QueryRequest) -> TrustReceipt:
    """Run the full Veritrace pipeline and return a Trust Receipt.

    Pipeline: input guardrails → PII redaction → responder agent →
    output gate → PII restore → persist to audit store.
    """
    if _store is None or _audit is None:
        raise HTTPException(status_code=503, detail="Service not ready.")

    t0 = time.time()
    tenant_id = request.tenant_id
    raw_query = request.query

    # 1. Input guardrails
    guard = check_input(raw_query)
    if not guard["allowed"]:
        receipt = TrustReceipt(
            tenant=tenant_id,
            route="refused",
            answer=guard["blocked_reason"] or "Request blocked.",
            confidence="abstained",
            refusal=RefusalInfo(triggered=True, reason=guard["blocked_reason"]),
            latency_ms=round((time.time() - t0) * 1000, 1),
        )
        _audit.persist_receipt(receipt)
        return receipt

    # 2. Semantic cache check (embed the raw query for similarity lookup)
    from veritrace.index.embeddings import embed_query
    query_embedding = embed_query(raw_query)
    cached = get_cached(tenant_id, query_embedding)
    if cached is not None:
        cached_hit = cached.model_copy(update={"route": "cached"})
        _audit.persist_receipt(cached_hit)
        return cached_hit

    # 3. PII/PHI redaction
    redacted_query, redact_ctx = redact(raw_query)

    # 4. Responder agent
    receipt = answer(redacted_query, tenant_id, _store, start_time=t0,
                     session_id=request.session_id)

    # 5. Output gate
    gate = check_output(receipt.answer, redacted_query, [])
    if not gate["passed"]:
        receipt = TrustReceipt(
            tenant=tenant_id,
            route="refused",
            answer=gate["reason"] or "Output blocked.",
            confidence="abstained",
            refusal=RefusalInfo(triggered=True, reason=gate["reason"]),
            latency_ms=round((time.time() - t0) * 1000, 1),
        )
        _audit.persist_receipt(receipt)
        return receipt

    # 6. Restore PII placeholders in answer
    if redact_ctx.applied:
        receipt = receipt.model_copy(
            update={
                "answer": restore(receipt.answer, redact_ctx),
                "redaction": RedactionInfo(
                    applied=True, types=redact_ctx.types_detected
                ),
            }
        )

    # 7. Store in semantic cache (only cache non-abstained, non-refused answers)
    if receipt.confidence not in ("abstained",) and receipt.route != "refused":
        cache_put(tenant_id, raw_query, query_embedding, receipt)

    # 8. Update session memory
    if request.session_id:
        add_turn(request.session_id, "user", raw_query)
        add_turn(request.session_id, "assistant", receipt.answer)

    # 9. Persist and return
    _audit.persist_receipt(receipt)
    return receipt


# ---------------------------------------------------------------------------
# Chat — multi-turn conversation with session memory
# ---------------------------------------------------------------------------

@app.post("/v1/chat", response_model=TrustReceipt, tags=["query"])
def chat(request: QueryRequest) -> TrustReceipt:
    """Multi-turn chat endpoint.  Same pipeline as /v1/query but automatically
    manages session memory when *session_id* is provided.

    The conversation history is injected into the generation prompt so the
    model can answer follow-up questions that refer to prior turns.
    Pass the same *session_id* across calls to maintain context.
    """
    # Delegate to /v1/query — session_id handling is already wired there
    return query(request)


# ---------------------------------------------------------------------------
# Receipts
# ---------------------------------------------------------------------------

@app.get("/v1/receipts/{receipt_id}", response_model=TrustReceipt, tags=["audit"])
def get_receipt(receipt_id: str) -> TrustReceipt:
    """Retrieve a sealed Trust Receipt by ID."""
    if _audit is None:
        raise HTTPException(status_code=503, detail="Service not ready.")
    receipt = _audit.get_receipt(receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail=f"Receipt {receipt_id!r} not found.")
    return receipt


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

@app.get("/v1/sources", tags=["sources"])
def list_sources(tenant_id: str = settings.default_tenant) -> dict:
    """List indexed source IDs for a tenant."""
    if _store is None:
        return {"tenant_id": tenant_id, "sources": [], "chunk_count": 0}
    count = _store.count(tenant_id)
    return {"tenant_id": tenant_id, "chunk_count": count}


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------

@app.get("/v1/usage", tags=["ops"])
def usage(tenant_id: str = settings.default_tenant) -> dict:
    """Return aggregate usage stats for a tenant."""
    if _audit is None:
        return {"tenant_id": tenant_id, "total_queries": 0, "total_cost_usd": 0.0}
    return dict(_audit.get_usage(tenant_id))


# ---------------------------------------------------------------------------
# Assurance Engine
# ---------------------------------------------------------------------------

@app.get("/v1/tools", tags=["tools"])
def list_tools() -> list[dict]:
    """List available MCP tool definitions (name, description, parameters)."""
    from veritrace.tools.mcp_server import list_tools as _list_tools
    return _list_tools()


@app.post("/v1/assure", tags=["assurance"])
def assure(tenant_id: str = settings.default_tenant) -> dict:
    """Run the Assurance Engine scan and return a Trust Score + report.

    Generates the full attack set for *tenant_id*, runs each case through
    the pipeline, and returns an AssuranceReport with Trust Score (0–100).
    """
    if _store is None:
        raise HTTPException(status_code=503, detail="Service not ready.")

    attacks = generate_attacks(tenant_id)
    results = run_attacks(attacks, tenant_id, _store)
    report = compute_score(results, tenant_id)
    return report.model_dump(mode="json")
