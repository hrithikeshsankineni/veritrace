"""Output gate — groundedness check and domain refusal.

Public API
----------
OutputGateResult — TypedDict:
  "passed"     : bool
  "reason"     : str | None
  "gate_type"  : str | None  ("groundedness" | "domain_refusal" | None)

check_output(answer, query, candidates) -> OutputGateResult
    Run both checks in order:
    1. Domain refusal — is the answer individualized clinical advice?
    2. Groundedness gate — does the answer contain claims beyond the chunks?

    Returns passed=True only if both checks pass.

Design
------
- Domain refusal uses keyword patterns (fast, no LLM) — catches the clearest
  out-of-bounds responses before spending a model call on the judge.
- Groundedness judge uses a mini-tier binary LLM call ("yes" / "no").
  In mock mode: answer is considered grounded if it references any word from
  the source chunks (conservative but deterministic for testing).
"""

from __future__ import annotations

import re
from typing import Optional, TypedDict

from veritrace.retrieval.rerank import RankedResult

# ---------------------------------------------------------------------------
# Domain refusal patterns
# ---------------------------------------------------------------------------

_CLINICAL_ADVICE_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\byou\s+should\s+(?:take|stop|start|increase|decrease|switch)\s+\w+",
        r"\brecommend\s+(?:you|that\s+you)\s+(?:take|stop|start)",
        r"\bI\s+advise\s+you\s+to\b",
        r"\bas\s+your\s+(?:doctor|physician|clinician|nurse|pharmacist)\b",
        r"\bmedical\s+advice\b",
        r"\bdiagnos(?:is|e|ed)\b",
        r"\btreat(?:ment|ing|ed)\s+your\b",
        r"\bprescribe\b",
    ]
]

_CLINICAL_REFUSAL = (
    "This response has been blocked because it contains individualized clinical advice. "
    "Please consult a licensed healthcare provider for personal medical guidance."
)

_ESCALATE_SUFFIX = " Contact Member Services or your healthcare provider for personalized assistance."


def _check_domain_refusal(answer: str) -> Optional[str]:
    """Return a refusal reason if clinical advice patterns are detected."""
    for pattern in _CLINICAL_ADVICE_PATTERNS:
        if pattern.search(answer):
            return _CLINICAL_REFUSAL
    return None


# ---------------------------------------------------------------------------
# Groundedness judge
# ---------------------------------------------------------------------------

_JUDGE_PROMPT = """\
You are a groundedness judge for a health-plan assistant.
Given the retrieved passages and the generated answer, determine whether
EVERY factual claim in the answer is directly supported by the passages.

Answer with exactly one word: "yes" (all claims supported) or "no" (any claim unsupported).

Passages:
{passages}

Answer: {answer}"""


def _check_groundedness_mock(answer: str, candidates: list[RankedResult]) -> bool:
    """Mock groundedness check: pass if the answer overlaps with any chunk text."""
    if not candidates:
        # No chunks → abstain answer — allow it through (it's already safe)
        return True
    answer_words = set(re.findall(r"\b\w{4,}\b", answer.lower()))
    for c in candidates:
        chunk_words = set(re.findall(r"\b\w{4,}\b", c["text"].lower()))
        if answer_words & chunk_words:
            return True
    return False


def _check_groundedness_llm(answer: str, candidates: list[RankedResult]) -> bool:
    """LLM-based groundedness judge (mini tier, binary)."""
    from veritrace.llm import complete

    passages = "\n\n".join(
        f"[{i+1}] {c['text'][:300]}" for i, c in enumerate(candidates)
    )
    result = complete(
        "mini",
        [{"role": "user", "content": _JUDGE_PROMPT.format(passages=passages, answer=answer)}],
        max_tokens=5,
    ).strip().lower()
    return "no" not in result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class OutputGateResult(TypedDict):
    passed: bool
    reason: Optional[str]
    gate_type: Optional[str]


def check_output(
    answer: str,
    query: str,
    candidates: list[RankedResult],
) -> OutputGateResult:
    """Check an answer before sending it to the user.

    Parameters
    ----------
    answer:
        The generated answer text.
    query:
        The original user query (reserved for future use).
    candidates:
        The top-k re-ranked candidates used to generate the answer.

    Returns
    -------
    OutputGateResult with passed=True if both checks pass.
    """
    from veritrace.config import settings

    _ = query  # reserved

    # 1. Domain refusal (fast, no LLM)
    refusal_reason = _check_domain_refusal(answer)
    if refusal_reason:
        return OutputGateResult(
            passed=False,
            reason=refusal_reason + _ESCALATE_SUFFIX,
            gate_type="domain_refusal",
        )

    # 2. Groundedness gate
    if settings.mock_llm:
        grounded = _check_groundedness_mock(answer, candidates)
    else:
        grounded = _check_groundedness_llm(answer, candidates)

    if not grounded:
        return OutputGateResult(
            passed=False,
            reason=(
                "Answer blocked: contains claims not supported by the source documents. "
                "Please rephrase your question or contact Member Services."
            ),
            gate_type="groundedness",
        )

    return OutputGateResult(passed=True, reason=None, gate_type=None)
