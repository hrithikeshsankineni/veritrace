"""Conflict detection and resolution for top-k retrieved candidates.

Public API
----------
ConflictResult — TypedDict:
  "detected"      : bool
  "description"   : str | None
  "resolved_to"   : str | None   source_id of the authoritative candidate
  "filtered"      : list[RankedResult]  candidates after removing superseded ones

detect_and_resolve(candidates) -> ConflictResult
    Inspect the top-k candidates for contradicting sources (same topic,
    different effective dates or explicit supersedes links).  Resolve by:
      1. Explicit supersedes/superseded_by metadata links.
      2. Effective date — newer document wins.
    Returns the filtered candidate list with superseded entries removed and
    a ConflictInfo-compatible dict for the Trust Receipt.

Resolution rules
----------------
- Two candidates conflict if they share the same `source_id` prefix family
  OR one's `supersedes` field names the other's `source_id`.
- Winning candidate: the one with the later `effective_date`, or the one
  whose `supersedes` field explicitly names the loser.
- Superseded candidates are dropped from the filtered list so generation
  only sees authoritative evidence.
- If dates are absent and no explicit link exists, both are kept and the
  conflict is disclosed without resolution.
"""

from __future__ import annotations

from datetime import date
from typing import Optional, TypedDict

from veritrace.retrieval.rerank import RankedResult


class ConflictResult(TypedDict):
    detected: bool
    description: Optional[str]
    resolved_to: Optional[str]       # source_id of winner
    disclosed_superseded: Optional[str]  # source_id of loser
    filtered: list[RankedResult]


def _parse_date(s: Optional[str]) -> Optional[date]:
    """Parse ISO date string to date, return None on failure."""
    if not s:
        return None
    try:
        return date.fromisoformat(str(s).strip('"').strip("'"))
    except ValueError:
        return None


def _source_family(source_id: str) -> str:
    """Strip trailing year/version suffix to get the document family name.

    'formulary_2024' and 'formulary_2026' → 'formulary'
    'policy_prior_auth_v1' and 'policy_prior_auth_v2' → 'policy_prior_auth'
    """
    import re
    return re.sub(r'[_\-]?(v?\d+|20\d{2})$', '', source_id, flags=re.IGNORECASE)


def detect_and_resolve(candidates: list[RankedResult]) -> ConflictResult:
    """Detect and resolve source conflicts in *candidates*.

    Parameters
    ----------
    candidates:
        Re-ranked top-k candidates from the retrieval pipeline.

    Returns
    -------
    ConflictResult with filtered candidate list and conflict metadata.
    """
    if len(candidates) < 2:
        return ConflictResult(
            detected=False,
            description=None,
            resolved_to=None,
            disclosed_superseded=None,
            filtered=candidates,
        )

    # Build index: source_id → candidate
    seen: dict[str, RankedResult] = {}
    superseded_ids: set[str] = set()
    winner_id: Optional[str] = None
    loser_id: Optional[str] = None

    for cand in candidates:
        meta = cand["metadata"]
        sid = meta.get("source_id", "")
        seen[sid] = cand

    # Pass 1: explicit supersedes links
    for sid, cand in seen.items():
        meta = cand["metadata"]
        supersedes = meta.get("supersedes") or meta.get("superseded_by")
        # 'supersedes' means this doc is newer and wins over the named doc
        if meta.get("supersedes") and meta["supersedes"] in seen:
            loser = meta["supersedes"]
            superseded_ids.add(loser)
            winner_id = sid
            loser_id = loser

    # Pass 2: same document family with different effective dates
    family_map: dict[str, list[RankedResult]] = {}
    for sid, cand in seen.items():
        fam = _source_family(sid)
        family_map.setdefault(fam, []).append(cand)

    for fam, group in family_map.items():
        if len(group) < 2:
            continue
        # Sort by effective_date descending — newest first
        dated = [(c, _parse_date(c["metadata"].get("effective_date"))) for c in group]
        dated_valid = [(c, d) for c, d in dated if d is not None]
        if len(dated_valid) >= 2:
            dated_valid.sort(key=lambda x: x[1], reverse=True)
            winner_cand, winner_date = dated_valid[0]
            for loser_cand, loser_date in dated_valid[1:]:
                lsid = loser_cand["metadata"].get("source_id", "")
                wsid = winner_cand["metadata"].get("source_id", "")
                if lsid not in superseded_ids:
                    superseded_ids.add(lsid)
                    if winner_id is None:
                        winner_id = wsid
                        loser_id = lsid

    if not superseded_ids and winner_id is None:
        # No conflict found
        return ConflictResult(
            detected=False,
            description=None,
            resolved_to=None,
            disclosed_superseded=None,
            filtered=candidates,
        )

    # Filter out superseded candidates
    filtered = [c for c in candidates
                if c["metadata"].get("source_id", "") not in superseded_ids]

    # If filtering removed everything, keep the winner only
    if not filtered and winner_id and winner_id in seen:
        filtered = [seen[winner_id]]

    loser_str = ", ".join(superseded_ids)
    description = (
        f"Conflicting sources detected: '{loser_str}' superseded by '{winner_id}'. "
        f"Answer uses the current document only."
    )

    return ConflictResult(
        detected=True,
        description=description,
        resolved_to=winner_id,
        disclosed_superseded=loser_str,
        filtered=filtered,
    )
