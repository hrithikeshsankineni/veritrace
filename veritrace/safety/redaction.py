"""PII/PHI redaction firewall.

Sensitive values are replaced with typed placeholders BEFORE any model call
and restored from the placeholder map at the output edge.

Public API
----------
RedactionContext — carries the placeholder map for a request lifecycle.

redact(text) -> (redacted_text, context)
    Replace PII/PHI in *text* with placeholders; return both.

restore(text, context) -> str
    Substitute placeholders back with original values.

RedactionInfo (from schemas) is populated by the caller with context.applied
and context.types for inclusion in the Trust Receipt.

Detected types (regex layer)
-----------------------------
- member_id  : MBR-XXXXXX or M-XXXXX format (any prefix of 1+ letters followed by - and 4+ digits)
- ssn        : NNN-NN-NNNN
- phone      : (NNN) NNN-NNNN or NNN-NNN-NNNN
- email      : standard email addresses
- dob        : MM/DD/YYYY or YYYY-MM-DD that look like birth dates
- credit_card: NNNN-NNNN-NNNN-NNNN

Note: This is a regex-first layer. For a production deployment a dedicated
NER-based model (e.g. Microsoft Presidio) would be added as a second layer.
The module is designed to be swapped without changing the public API.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Tuple


# ---------------------------------------------------------------------------
# Patterns — ordered so more specific patterns run first
# ---------------------------------------------------------------------------

@dataclass
class _Pattern:
    name: str
    regex: re.Pattern


_PATTERNS: list[_Pattern] = [
    _Pattern("member_id",   re.compile(r"\b[A-Z]{1,4}-\d{4,}\b")),
    _Pattern("ssn",         re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    _Pattern("credit_card", re.compile(r"\b\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}\b")),
    _Pattern("phone",       re.compile(
        r"\b(?:\(\d{3}\)\s?|\d{3}[-.])\d{3}[-. ]\d{4}\b"
    )),
    _Pattern("email",       re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    )),
    _Pattern("dob",         re.compile(
        r"\b(?:0[1-9]|1[0-2])/(?:0[1-9]|[12]\d|3[01])/(?:19|20)\d{2}\b"
        r"|\b(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])\b"
    )),
]


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

@dataclass
class RedactionContext:
    """Holds the placeholder→value map for one request lifecycle."""
    _map: dict[str, str] = field(default_factory=dict)
    types_detected: list[str] = field(default_factory=list)
    applied: bool = False

    def record(self, placeholder: str, original: str, pii_type: str) -> None:
        self._map[placeholder] = original
        if pii_type not in self.types_detected:
            self.types_detected.append(pii_type)

    def restore(self, text: str) -> str:
        for placeholder, original in self._map.items():
            text = text.replace(placeholder, original)
        return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def redact(text: str) -> Tuple[str, RedactionContext]:
    """Detect and replace PII/PHI in *text* with typed placeholders.

    Returns (redacted_text, context) where context carries the map needed
    for restoring values at the output edge.
    """
    ctx = RedactionContext()
    counters: dict[str, int] = {}

    for pattern in _PATTERNS:
        matches = list(pattern.regex.finditer(text))
        for match in matches:
            original = match.group()
            n = counters.get(pattern.name, 0) + 1
            counters[pattern.name] = n
            placeholder = f"[{pattern.name.upper()}_{n}]"
            if original not in ctx._map.values():  # deduplicate same value
                ctx.record(placeholder, original, pattern.name)
            else:
                # Find existing placeholder for this value
                for ph, val in ctx._map.items():
                    if val == original:
                        placeholder = ph
                        break
            text = text.replace(original, placeholder, 1)

    ctx.applied = bool(ctx._map)
    return text, ctx


def restore(text: str, context: RedactionContext) -> str:
    """Restore placeholders in *text* using *context*'s map."""
    return context.restore(text)
