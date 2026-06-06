"""Veritrace FastAPI application.

Endpoints:
  GET  /health           — liveness probe
  POST /v1/query         — main query endpoint (stub until Phase 3-5 wired)
  GET  /v1/receipts/{id} — retrieve a sealed Trust Receipt (stub)
  GET  /v1/usage         — aggregate usage (stub)
  GET  /v1/sources       — list indexed sources (stub)
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from veritrace.schemas import QueryRequest, TrustReceipt

app = FastAPI(
    title="Veritrace",
    description=(
        "An API-first platform that answers questions over a private knowledge base "
        "and proves the answers are safe."
    ),
    version="0.1.0",
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health", tags=["ops"])
def health() -> dict:
    """Liveness probe — returns ok."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Query — stub (wired fully in task 5.2)
# ---------------------------------------------------------------------------


@app.post("/v1/query", response_model=TrustReceipt, tags=["query"])
def query(request: QueryRequest) -> TrustReceipt:
    """Answer a query and return a Trust Receipt.

    This endpoint is a stub that returns a placeholder receipt.
    It will be fully wired after Phase 3–5 modules are implemented.
    """
    return TrustReceipt(
        tenant=request.tenant_id,
        answer=(
            "[stub] This endpoint is not yet fully wired. "
            f"Received query: {request.query!r}"
        ),
        confidence="insufficient-evidence",
        route="knowledge",
    )


# ---------------------------------------------------------------------------
# Receipts
# ---------------------------------------------------------------------------


@app.get("/v1/receipts/{receipt_id}", response_model=TrustReceipt, tags=["audit"])
def get_receipt(receipt_id: str) -> TrustReceipt:
    """Retrieve a sealed Trust Receipt by ID (stub)."""
    raise HTTPException(status_code=404, detail=f"Receipt {receipt_id!r} not found (stub).")


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


@app.get("/v1/sources", tags=["sources"])
def list_sources(tenant_id: str = "demo") -> dict:
    """List indexed sources for a tenant (stub)."""
    return {"tenant_id": tenant_id, "sources": []}


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------


@app.get("/v1/usage", tags=["ops"])
def usage(tenant_id: str = "demo") -> dict:
    """Return aggregate usage for a tenant (stub)."""
    return {"tenant_id": tenant_id, "total_queries": 0, "total_cost_usd": 0.0}
