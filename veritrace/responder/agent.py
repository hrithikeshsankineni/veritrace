"""Responder agent — orchestrates the full query pipeline.

Public API
----------
answer(query, tenant_id, store, start_time) -> TrustReceipt
    Run the complete pipeline for a knowledge query and return a TrustReceipt.

Pipeline
--------
1. Intent routing: classify query as "knowledge" or "action".
   Action intents are stubbed (returns a not-yet-implemented notice).
2. Query rewrite (nano tier).
3. Wide retrieval (top-20, tenant-scoped).
4. Cross-encoder re-rank (top-4).
5. Evidence sufficiency check.
6. Grounded generation (mini tier) OR calibrated abstention.
7. Seal into TrustReceipt.

The caller is responsible for safety (guardrails + redaction + output gate)
which wrap this agent in the API layer.
"""

from __future__ import annotations

import time
from typing import Optional

from veritrace.config import settings
from veritrace.index.store import VectorStore
from veritrace.responder.conflict import detect_and_resolve
from veritrace.responder.evidence import check_sufficiency
from veritrace.responder.generate import generate
from veritrace.retrieval.rerank import rerank
from veritrace.retrieval.retrieve import retrieve
from veritrace.retrieval.rewrite import rewrite
from veritrace.schemas import ConflictInfo, TrustReceipt

_ACTION_KEYWORDS = frozenset(
    ["open ticket", "file claim", "submit", "create ticket", "update", "cancel", "change"]
)

_ABSTAIN_TEXT = (
    "I do not have sufficient information in the available sources to answer this question. "
    "Please contact Member Services for further assistance."
)


def _classify_intent(query: str) -> str:
    """Simple keyword-based intent classifier.

    Returns "action" if the query requests a state-changing operation,
    otherwise "knowledge".  The nano LLM is used when not in mock mode.
    """
    if settings.mock_llm:
        lower = query.lower()
        if any(kw in lower for kw in _ACTION_KEYWORDS):
            return "action"
        return "knowledge"

    from veritrace.llm import complete

    prompt = (
        "Classify this query as exactly one word: 'knowledge' or 'action'.\n"
        "- 'knowledge': asking for information or an explanation.\n"
        "- 'action': requesting a state-changing operation (file, submit, create, update, cancel).\n"
        f"Query: {query}"
    )
    result = complete(
        "nano",
        [{"role": "user", "content": prompt}],
        max_tokens=5,
    ).strip().lower()
    return "action" if "action" in result else "knowledge"


def answer(
    query: str,
    tenant_id: str,
    store: VectorStore,
    start_time: Optional[float] = None,
    session_id: Optional[str] = None,
) -> TrustReceipt:
    """Run the responder pipeline and return a TrustReceipt.

    Parameters
    ----------
    query:
        Raw user query (safety preprocessing is applied by the API layer).
    tenant_id:
        Tenant scope for retrieval.
    store:
        Shared VectorStore instance.
    start_time:
        Unix timestamp when the request was received (for latency tracking).
    """
    t0 = start_time or time.time()

    # 1. Intent routing
    intent = _classify_intent(query)

    if intent == "action":
        latency_ms = (time.time() - t0) * 1000
        return TrustReceipt(
            tenant=tenant_id,
            route="knowledge",  # keeps schema valid; action route TBD
            answer=(
                "Action requests are not yet available in this version. "
                "Please contact Member Services to complete this request."
            ),
            confidence="insufficient-evidence",
            latency_ms=round(latency_ms, 1),
            model_profile="nano",
        )

    # 2. Query rewrite
    rewritten = rewrite(query)

    # 3. Wide retrieval
    candidates_wide = retrieve(
        rewritten, tenant_id, store, top_k=settings.retrieval_top_k_wide
    )

    # 4. Re-rank to top-k final
    candidates_ranked = rerank(
        rewritten, candidates_wide, top_k=settings.retrieval_top_k_final
    )

    # 5. Conflict detection and resolution
    conflict_result = detect_and_resolve(candidates_ranked)
    candidates_clean = conflict_result["filtered"]

    # 6. Evidence sufficiency
    ev = check_sufficiency(rewritten, candidates_clean)

    # 7a. Abstain
    if not ev["sufficient"]:
        latency_ms = (time.time() - t0) * 1000
        return TrustReceipt(
            tenant=tenant_id,
            route="knowledge",
            answer=_ABSTAIN_TEXT,
            confidence="abstained",
            conflict=ConflictInfo(
                detected=conflict_result["detected"],
                description=conflict_result["description"],
                resolved_to=conflict_result["resolved_to"],
            ),
            latency_ms=round(latency_ms, 1),
            model_profile="mini",
        )

    # 7b. Generate (inject conversation history if session provided)
    history: list[dict] = []
    if session_id:
        from veritrace.memory import get_history
        history = get_history(session_id)
    gen = generate(rewritten, ev["top_candidates"], history=history or None)

    latency_ms = (time.time() - t0) * 1000

    # 8. Seal receipt
    return TrustReceipt(
        tenant=tenant_id,
        route="knowledge",
        answer=gen["answer"],
        confidence=ev["confidence"],
        citations=gen["citations"],
        conflict=ConflictInfo(
            detected=conflict_result["detected"],
            description=conflict_result["description"],
            resolved_to=conflict_result["resolved_to"],
        ),
        groundedness_score=gen["groundedness_score"],
        latency_ms=round(latency_ms, 1),
        model_profile="mini",
    )
