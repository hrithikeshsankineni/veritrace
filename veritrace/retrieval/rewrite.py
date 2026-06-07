"""Query rewrite — expand and clean a user query for retrieval.

Public API
----------
rewrite(query) -> str
    Returns a semantically equivalent but retrieval-optimised version of
    *query*.  Uses the nano LLM tier.  In mock mode returns a deterministic
    rewrite stub.

The rewrite step improves recall by:
- Expanding abbreviations and informal phrasing
- Adding domain terminology that anchors retrieval
- Removing conversational filler

If the LLM returns an empty response or fails, the original query is returned
unchanged (graceful degradation).
"""

from __future__ import annotations

from veritrace.llm import complete

_SYSTEM_PROMPT = """\
You are a query optimiser for a health-plan knowledge-base search engine.
Rewrite the user's question to maximise retrieval precision and recall.
Rules:
1. Keep the original intent exactly — do not change what is being asked.
2. Expand abbreviations (e.g. "PA" → "prior authorization").
3. Add relevant domain synonyms where helpful.
4. Remove filler words ("um", "like", "just wondering").
5. Output ONLY the rewritten query — no explanation, no prefix."""


def rewrite(query: str) -> str:
    """Return a retrieval-optimised rewrite of *query* (nano tier).

    In mock mode returns the query unchanged so that mock embedding/rerank
    scores reflect the original query keywords (no real LLM available).
    """
    from veritrace.config import settings

    query = query.strip()
    if not query:
        return query

    if settings.mock_llm:
        return query  # pass-through — no real model to call

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]

    try:
        result = complete("nano", messages, max_tokens=128)
        result = result.strip()
        return result if result else query
    except Exception:
        # Degrade gracefully — retrieval still works with the original query
        return query
