"""Tests for veritrace.safety.redaction."""

from __future__ import annotations

import os
from unittest.mock import patch, MagicMock

import pytest

os.environ["MOCK_LLM"] = "true"

from veritrace.safety.redaction import redact, restore, RedactionContext


# ---------------------------------------------------------------------------
# Basic redaction
# ---------------------------------------------------------------------------

def test_member_id_redacted():
    text, ctx = redact("Member MBR-100042 is asking about coverage.")
    assert "MBR-100042" not in text
    assert "[MEMBER_ID_1]" in text
    assert "member_id" in ctx.types_detected


def test_member_id_short_format_redacted():
    """M-XXXXX format (shorter prefix) must also be redacted."""
    text, ctx = redact("My member ID is M-99182.")
    assert "M-99182" not in text
    assert "member_id" in ctx.types_detected
    assert ctx.applied is True


def test_member_id_short_format_never_reaches_llm():
    """M-99182 must not appear in any llm.complete call after redaction."""
    calls: list[list[dict]] = []

    def fake_complete(tier, messages, **kwargs):
        calls.append(messages)
        return "Mock answer."

    query = "My member ID is M-99182."
    redacted_q, ctx = redact(query)
    assert "M-99182" not in redacted_q, "Redact step must remove M-99182 before LLM call"

    with patch("veritrace.llm.complete", side_effect=fake_complete):
        from veritrace.retrieval.rewrite import rewrite
        rewrite(redacted_q)

    for messages in calls:
        for msg in messages:
            assert "M-99182" not in str(msg), f"Raw member ID leaked to LLM: {msg}"


def test_ssn_redacted():
    text, ctx = redact("SSN: 123-45-6789")
    assert "123-45-6789" not in text
    assert "[SSN_1]" in text
    assert "ssn" in ctx.types_detected


def test_phone_redacted():
    text, ctx = redact("Call me at 555-867-5309.")
    assert "555-867-5309" not in text
    assert "phone" in ctx.types_detected


def test_email_redacted():
    text, ctx = redact("Contact alice@example.com for info.")
    assert "alice@example.com" not in text
    assert "email" in ctx.types_detected


def test_dob_redacted_slash_format():
    text, ctx = redact("DOB: 03/14/1978")
    assert "03/14/1978" not in text
    assert "dob" in ctx.types_detected


def test_dob_redacted_iso_format():
    text, ctx = redact("Date of birth: 1978-03-14")
    assert "1978-03-14" not in text
    assert "dob" in ctx.types_detected


def test_no_pii_unchanged():
    text, ctx = redact("Is generic atorvastatin covered at Tier 1?")
    assert text == "Is generic atorvastatin covered at Tier 1?"
    assert ctx.applied is False
    assert ctx.types_detected == []


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------

def test_restore_member_id():
    original = "Member MBR-100042 is asking about coverage."
    redacted, ctx = redact(original)
    restored = restore(redacted, ctx)
    assert restored == original


def test_restore_ssn():
    original = "SSN 123-45-6789 belongs to the member."
    redacted, ctx = redact(original)
    assert "123-45-6789" not in redacted
    restored = restore(redacted, ctx)
    assert restored == original


def test_restore_multiple_types():
    original = "Member MBR-100042 SSN 123-45-6789 email alice@example.com"
    redacted, ctx = redact(original)
    assert "MBR-100042" not in redacted
    assert "123-45-6789" not in redacted
    assert "alice@example.com" not in redacted
    restored = restore(redacted, ctx)
    assert restored == original


# ---------------------------------------------------------------------------
# Applied flag
# ---------------------------------------------------------------------------

def test_applied_true_when_pii_found():
    _, ctx = redact("MBR-100042 asked a question.")
    assert ctx.applied is True


def test_applied_false_when_no_pii():
    _, ctx = redact("What is the copay for atorvastatin?")
    assert ctx.applied is False


# ---------------------------------------------------------------------------
# Mock LLM does not see raw PII (critical property)
# ---------------------------------------------------------------------------

def test_raw_pii_never_reaches_llm_complete():
    """The raw member ID must not appear in any call to llm.complete."""
    from veritrace.safety import redaction as redaction_module

    calls: list[list[dict]] = []

    def fake_complete(tier, messages, **kwargs):
        calls.append(messages)
        return "Mock answer."

    query = "What is covered for member MBR-100042?"
    redacted, ctx = redact(query)

    with patch("veritrace.llm.complete", side_effect=fake_complete):
        from veritrace.retrieval.rewrite import rewrite
        rewrite(redacted)  # passes through the nano LLM

    for messages in calls:
        for msg in messages:
            assert "MBR-100042" not in str(msg), (
                f"Raw member ID leaked to LLM in message: {msg}"
            )
