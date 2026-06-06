"""Pydantic schemas for Veritrace API and internal data.

All public-facing and internal structured data uses these models.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Inbound
# ---------------------------------------------------------------------------


class QueryRequest(BaseModel):
    """Inbound query from a client."""

    query: str = Field(..., min_length=1, description="The user's question.")
    tenant_id: str = Field(default="demo", description="Tenant scoping identifier.")
    session_id: Optional[str] = Field(
        default=None, description="Optional session ID for short-term memory."
    )


# ---------------------------------------------------------------------------
# Source / citation primitives
# ---------------------------------------------------------------------------


class Source(BaseModel):
    """A single document or chunk in the knowledge index."""

    source_id: str
    title: str
    section: Optional[str] = None
    page: Optional[int] = None
    authority_level: Optional[str] = None   # e.g. "primary", "secondary"
    effective_date: Optional[str] = None    # ISO date string
    tenant_id: str = "demo"


class Citation(BaseModel):
    """A grounded reference linking an answer claim to a source chunk."""

    source_id: str
    section: Optional[str] = None
    page: Optional[int] = None
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance score.")
    excerpt: Optional[str] = Field(
        default=None, description="Short verbatim excerpt from the source."
    )


# ---------------------------------------------------------------------------
# Sub-receipt fields
# ---------------------------------------------------------------------------


class ConflictInfo(BaseModel):
    detected: bool = False
    description: Optional[str] = None
    resolved_to: Optional[str] = None    # source_id of the authoritative doc


class RedactionInfo(BaseModel):
    applied: bool = False
    types: list[str] = Field(default_factory=list)  # e.g. ["member_id", "ssn"]


class RefusalInfo(BaseModel):
    triggered: bool = False
    reason: Optional[str] = None


class ActionInfo(BaseModel):
    """Present when the route was an action rather than a knowledge query."""

    tool: str
    parameters: dict = Field(default_factory=dict)
    verified: bool = False
    result: Optional[str] = None


# ---------------------------------------------------------------------------
# Trust Receipt — the canonical output of every query
# ---------------------------------------------------------------------------

ConfidenceLevel = Literal[
    "well-grounded", "partially-grounded", "insufficient-evidence", "abstained"
]


class TrustReceipt(BaseModel):
    """Per-response provenance record persisted to the audit store.

    Fields match §6.11 of Veritrace_System_Design.md.
    """

    request_id: str = Field(
        default_factory=lambda: f"rq_{uuid4().hex[:12]}"
    )
    tenant: str
    route: Literal["knowledge", "action", "refused", "cached"] = "knowledge"

    answer: str
    confidence: ConfidenceLevel = "well-grounded"
    citations: list[Citation] = Field(default_factory=list)

    conflict: ConflictInfo = Field(default_factory=ConflictInfo)
    redaction: RedactionInfo = Field(default_factory=RedactionInfo)
    refusal: RefusalInfo = Field(default_factory=RefusalInfo)
    action: Optional[ActionInfo] = None

    groundedness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    latency_ms: float = Field(default=0.0, ge=0.0)
    model_profile: str = "mini"
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# Assurance / Trust Score
# ---------------------------------------------------------------------------


class AttackResult(BaseModel):
    """Result for a single attack case run through the system."""

    attack_id: str
    attack_class: str   # injection | pii_extraction | out_of_scope | unanswerable | contradiction
    prompt: str
    passed: bool        # True = system defended correctly
    notes: Optional[str] = None
    receipt: Optional[TrustReceipt] = None


class AssuranceReport(BaseModel):
    """Output of a full assurance scan (task 7.x)."""

    report_id: str = Field(default_factory=lambda: f"ar_{uuid4().hex[:12]}")
    tenant: str
    trust_score: float = Field(..., ge=0.0, le=100.0)
    total_attacks: int
    passed: int
    failed: int
    per_class: dict[str, dict] = Field(default_factory=dict)
    findings: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
