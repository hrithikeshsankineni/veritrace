"""SQLite audit store — persist and retrieve Trust Receipts + telemetry.

Public API
----------
AuditStore(db_path)
    .persist_receipt(receipt) -> None
    .get_receipt(request_id) -> TrustReceipt | None
    .get_usage(tenant_id) -> UsageSummary

UsageSummary — TypedDict:
  "tenant_id"       : str
  "total_queries"   : int
  "total_cost_usd"  : float
  "avg_latency_ms"  : float
  "total_tokens_est": int

The store uses a single SQLite database.  The receipts table stores the full
JSON blob of the TrustReceipt for easy retrieval and a telemetry table keeps
per-query metrics for usage aggregation.

Thread safety: each AuditStore instance creates its own connection with
check_same_thread=False, which is safe for the single-process Uvicorn worker
used here.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional, TypedDict

from veritrace.schemas import TrustReceipt

_CREATE_RECEIPTS = """
CREATE TABLE IF NOT EXISTS receipts (
    request_id  TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    receipt_json TEXT NOT NULL
);
"""

_CREATE_TELEMETRY = """
CREATE TABLE IF NOT EXISTS telemetry (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id  TEXT NOT NULL,
    tenant_id   TEXT NOT NULL,
    route       TEXT,
    confidence  TEXT,
    latency_ms  REAL,
    cost_usd    REAL,
    tokens_est  INTEGER,
    timestamp   TEXT NOT NULL
);
"""


class UsageSummary(TypedDict):
    tenant_id: str
    total_queries: int
    total_cost_usd: float
    avg_latency_ms: float
    total_tokens_est: int


class AuditStore:
    """SQLite-backed audit and telemetry store."""

    def __init__(self, db_path: str | Path = "veritrace.sqlite") -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._bootstrap()

    def _bootstrap(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(_CREATE_RECEIPTS + _CREATE_TELEMETRY)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def persist_receipt(self, receipt: TrustReceipt) -> None:
        """Persist a TrustReceipt to the audit store."""
        ts = receipt.timestamp.isoformat()
        blob = receipt.model_dump_json()

        # Estimate tokens: ~4 chars per token
        tokens_est = (len(receipt.answer) + sum(len(c.excerpt or "") for c in receipt.citations)) // 4

        cur = self._conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO receipts (request_id, tenant_id, timestamp, receipt_json) "
            "VALUES (?, ?, ?, ?)",
            (receipt.request_id, receipt.tenant, ts, blob),
        )
        cur.execute(
            "INSERT INTO telemetry (request_id, tenant_id, route, confidence, "
            "latency_ms, cost_usd, tokens_est, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                receipt.request_id,
                receipt.tenant,
                receipt.route,
                receipt.confidence,
                receipt.latency_ms,
                receipt.cost_usd,
                tokens_est,
                ts,
            ),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_receipt(self, request_id: str) -> Optional[TrustReceipt]:
        """Return a TrustReceipt by request_id, or None if not found."""
        cur = self._conn.cursor()
        row = cur.execute(
            "SELECT receipt_json FROM receipts WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if row is None:
            return None
        return TrustReceipt.model_validate_json(row["receipt_json"])

    def get_usage(self, tenant_id: str) -> UsageSummary:
        """Return aggregate usage stats for a tenant."""
        cur = self._conn.cursor()
        row = cur.execute(
            """
            SELECT
                COUNT(*)          AS total_queries,
                COALESCE(SUM(cost_usd), 0.0)    AS total_cost_usd,
                COALESCE(AVG(latency_ms), 0.0)  AS avg_latency_ms,
                COALESCE(SUM(tokens_est), 0)    AS total_tokens_est
            FROM telemetry
            WHERE tenant_id = ?
            """,
            (tenant_id,),
        ).fetchone()
        return UsageSummary(
            tenant_id=tenant_id,
            total_queries=row["total_queries"] or 0,
            total_cost_usd=float(row["total_cost_usd"] or 0.0),
            avg_latency_ms=float(row["avg_latency_ms"] or 0.0),
            total_tokens_est=int(row["total_tokens_est"] or 0),
        )

    def close(self) -> None:
        self._conn.close()
