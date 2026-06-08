"""Input guardrails — injection blocking and topic/scope classification.

Public API
----------
GuardResult — TypedDict:
  "allowed"         : bool
  "block_category"  : str | None  ("injection" | "off_scope" | None)
  "blocked_reason"  : str | None

check_input(query) -> GuardResult
    Run injection pattern check + topic/scope check.
    Returns allowed=True if both pass; otherwise allowed=False with reason.

Two layers
----------
1. Regex injection patterns (fast, no LLM) — blocks attempts to override
   system prompts, exfiltrate instructions, or inject new instructions.
2. Topic/scope check (nano LLM) — classifies whether the query is within
   the health-plan knowledge-base scope. In mock mode uses a keyword list.
"""

from __future__ import annotations

import re
from typing import Optional, TypedDict

# ---------------------------------------------------------------------------
# Layer 1 — injection pattern block
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"disregard\s+(all\s+)?previous",
        r"forget\s+(all\s+)?previous\s+instructions",
        r"you\s+are\s+now\s+(?:a\s+)?(?:different|new|another)\s+(?:AI|assistant|model)",
        r"system\s+prompt\s*:",
        r"<\s*system\s*>",
        r"\[INST\]",
        r"jailbreak",
        r"DAN\s+mode",
        r"pretend\s+you\s+(have\s+no|are\s+not)",
        r"reveal\s+(your\s+)?(system\s+)?prompt",
        r"print\s+(your\s+)?(system\s+)?instructions",
        r"what\s+are\s+your\s+instructions",
        # PII extraction patterns
        r"\bssn\b",
        r"social\s+security\s+number",
        r"list\s+(all|every)\s+(?:member|patient)",
        r"what\s+(?:medications?|drugs?|prescriptions?)\s+is\s+(?:member|patient)\b",
    ]
]


def _check_injection(query: str) -> Optional[str]:
    """Return a reason string if injection is detected, else None."""
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(query):
            return f"Input blocked: detected injection pattern matching '{pattern.pattern[:60]}'"
    return None


# ---------------------------------------------------------------------------
# Layer 2 — topic/scope check
# ---------------------------------------------------------------------------

# Keywords that are clearly in scope for health-plan member services
_IN_SCOPE_KEYWORDS = frozenset([
    "coverage", "covered", "copay", "deductible", "formulary", "prescription",
    "medication", "drug", "plan", "benefit", "claim", "network", "provider",
    "prior authorization", "specialist", "referral", "insurance", "member",
    "pharmacy", "in-network", "out-of-network", "appeal", "denial", "premium",
    "urgent care", "emergency", "hospital", "lab", "mental health", "therapy",
    "parity", "tier", "generic", "brand", "specialty", "atorvastatin",
    "sertraline", "deductible", "out-of-pocket", "preventive",
])

# Keywords that are clearly out of scope
_OUT_OF_SCOPE_KEYWORDS = frozenset([
    "bitcoin", "crypto", "stock market", "recipe", "cooking", "game",
    "movie", "music", "sports", "weather", "politics", "election",
    "celebrity", "social media", "dating", "travel", "hotel",
    "write code", "write a script", "write me a", "python script", "scrape",
    "coding tutorial", "hack", "malware", "exploit",
    "medical advice", "individualized", "diagnose me", "treat my",
    "poem", "story", "fiction", "essay", "debate",
])

_SCOPE_PROMPT = """\
You are a scope classifier for a health-plan member-services knowledge base.
Answer with exactly one word: "in_scope" or "out_of_scope".
- "in_scope": the query is about health insurance, drug coverage, medical benefits, claims, or the health plan.
- "out_of_scope": the query has nothing to do with health insurance or benefits.
Query: {query}"""


def _check_scope_mock(query: str) -> bool:
    """Return True (in scope) or False (out of scope) — keyword heuristic."""
    lower = query.lower()
    if any(kw in lower for kw in _OUT_OF_SCOPE_KEYWORDS):
        return False
    # If it mentions any in-scope keyword it's in scope; otherwise borderline → allow
    return True


def _check_scope_llm(query: str) -> bool:
    """Return True (in scope) or False (out of scope).

    Uses keyword shortcuts first to avoid an LLM call on clear cases:
    - Clearly out-of-scope keywords → False immediately
    - Clearly in-scope keywords → True immediately
    - Ambiguous → nano LLM classification
    """
    lower = query.lower()
    if any(kw in lower for kw in _OUT_OF_SCOPE_KEYWORDS):
        return False
    if any(kw in lower for kw in _IN_SCOPE_KEYWORDS):
        return True

    # Genuinely ambiguous — call the LLM
    from veritrace.llm import complete
    result = complete(
        "nano",
        [{"role": "user", "content": _SCOPE_PROMPT.format(query=query)}],
        max_tokens=5,
    ).strip().lower()
    return "out_of_scope" not in result


class GuardResult(TypedDict):
    allowed: bool
    block_category: Optional[str]
    blocked_reason: Optional[str]


def check_input(query: str) -> GuardResult:
    """Check a query against injection patterns and topic scope.

    Returns GuardResult with allowed=True if the query passes both layers.
    """
    from veritrace.config import settings

    # 1. Injection check (always regex, fast)
    injection_reason = _check_injection(query)
    if injection_reason:
        return GuardResult(
            allowed=False,
            block_category="injection",
            blocked_reason=injection_reason,
        )

    # 2. Scope check
    if settings.mock_llm:
        in_scope = _check_scope_mock(query)
    else:
        in_scope = _check_scope_llm(query)

    if not in_scope:
        return GuardResult(
            allowed=False,
            block_category="off_scope",
            blocked_reason=(
                "Input blocked: query is outside the scope of this health-plan "
                "knowledge base. Please ask about your coverage, benefits, or claims."
            ),
        )

    return GuardResult(allowed=True, block_category=None, blocked_reason=None)
