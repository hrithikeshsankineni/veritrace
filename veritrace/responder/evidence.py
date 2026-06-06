"""Evidence sufficiency evaluation.

Public API
----------
EvidenceResult — TypedDict with:
  "sufficient"      : bool
  "confidence"      : ConfidenceLevel   (from schemas)
  "abstain_reason"  : str | None
  "top_candidates"  : list[RankedResult]

check_sufficiency(query, candidates, threshold) -> EvidenceResult
    Given the re-ranked top-k candidates, decide whether evidence is
    sufficient to generate a grounded answer.

Sufficiency rules
-----------------
1. No candidates at all → abstain ("no_evidence").
2. Best candidate rerank_score < ABSTAIN_THRESHOLD → abstain ("weak_evidence").
3. Best score ≥ ABSTAIN_THRESHOLD but < PARTIAL_THRESHOLD → partial confidence.
4. Best score ≥ PARTIAL_THRESHOLD → well-grounded confidence.

Thresholds are conservative by design — in a regulated domain, a confident
wrong answer is worse than an honest abstention.
"""

from __future__ import annotations

from typing import Optional, TypedDict

from veritrace.retrieval.rerank import RankedResult
from veritrace.schemas import ConfidenceLevel

# Score thresholds (cross-encoder scores are in [0, 1] in mock mode;
# real cross-encoder scores can be outside this range, but we normalise).
ABSTAIN_THRESHOLD: float = 0.15   # below → abstain
PARTIAL_THRESHOLD: float = 0.40   # below → partially-grounded


class EvidenceResult(TypedDict):
    sufficient: bool
    confidence: ConfidenceLevel
    abstain_reason: Optional[str]
    top_candidates: list[RankedResult]


def check_sufficiency(
    query: str,
    candidates: list[RankedResult],
    abstain_threshold: float = ABSTAIN_THRESHOLD,
    partial_threshold: float = PARTIAL_THRESHOLD,
) -> EvidenceResult:
    """Evaluate whether *candidates* provide sufficient evidence to answer *query*.

    Parameters
    ----------
    query:
        The (rewritten) user query — reserved for future LLM-based sufficiency
        check but not used in the current score-threshold implementation.
    candidates:
        Re-ranked candidate list (output of rerank()).
    abstain_threshold:
        Minimum rerank_score for the top candidate to proceed.
    partial_threshold:
        Minimum rerank_score to be "well-grounded" vs "partially-grounded".

    Returns
    -------
    EvidenceResult with sufficient=True/False and a ConfidenceLevel.
    """
    _ = query  # reserved for future LLM-based check

    if not candidates:
        return EvidenceResult(
            sufficient=False,
            confidence="abstained",
            abstain_reason="no_evidence: no relevant documents found for this query",
            top_candidates=[],
        )

    best_score = candidates[0]["rerank_score"]

    if best_score < abstain_threshold:
        return EvidenceResult(
            sufficient=False,
            confidence="abstained",
            abstain_reason=(
                f"weak_evidence: best relevance score {best_score:.3f} "
                f"is below the abstention threshold {abstain_threshold:.3f}"
            ),
            top_candidates=candidates,
        )

    if best_score < partial_threshold:
        return EvidenceResult(
            sufficient=True,
            confidence="partially-grounded",
            abstain_reason=None,
            top_candidates=candidates,
        )

    return EvidenceResult(
        sufficient=True,
        confidence="well-grounded",
        abstain_reason=None,
        top_candidates=candidates,
    )
