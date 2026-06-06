"""Tests for veritrace.ingest.chunker."""

from __future__ import annotations

from typing import Optional

import pytest

from veritrace.ingest.chunker import chunk, Chunk
from veritrace.ingest.parsers import ParsedDocument


def _doc(text: str, meta: Optional[dict] = None) -> ParsedDocument:
    m = {"source_id": "test_doc", "tenant_id": "demo"}
    if meta:
        m.update(meta)
    return ParsedDocument(text=text, metadata=m)


# ---------------------------------------------------------------------------
# Basic splitting
# ---------------------------------------------------------------------------

def test_chunk_returns_list():
    doc = _doc("# Heading\n\nSome text.")
    result = chunk(doc)
    assert isinstance(result, list)
    assert len(result) >= 1


def test_chunks_split_on_heading():
    doc = _doc("# Section A\n\nContent A.\n\n# Section B\n\nContent B.")
    result = chunk(doc)
    texts = [c["text"] for c in result]
    assert any("Content A" in t for t in texts)
    assert any("Content B" in t for t in texts)


def test_chunks_split_on_subheading():
    doc = _doc("# Top\n\n## Sub One\n\nText one.\n\n## Sub Two\n\nText two.")
    result = chunk(doc)
    assert len(result) >= 2
    headings = {c["heading"] for c in result}
    assert "Sub One" in headings
    assert "Sub Two" in headings


def test_section_carries_h1():
    doc = _doc("# Main Section\n\n## Subsection\n\nDetail text.")
    result = chunk(doc)
    sub_chunks = [c for c in result if c["heading"] == "Subsection"]
    assert sub_chunks
    assert sub_chunks[0]["section"] == "Main Section"


def test_preamble_before_first_heading():
    doc = _doc("Preamble text.\n\n# Heading\n\nBody.")
    result = chunk(doc)
    texts = " ".join(c["text"] for c in result)
    assert "Preamble text" in texts


# ---------------------------------------------------------------------------
# Metadata inheritance
# ---------------------------------------------------------------------------

def test_chunks_inherit_metadata():
    doc = _doc(
        "# Policy\n\nDetails.",
        meta={"source_id": "policy_2026", "authority_level": "primary", "tenant_id": "acme"},
    )
    result = chunk(doc)
    for c in result:
        assert c["metadata"]["source_id"] == "policy_2026"
        assert c["metadata"]["authority_level"] == "primary"
        assert c["metadata"]["tenant_id"] == "acme"


def test_chunk_metadata_is_copy():
    """Mutating a chunk's metadata must not affect other chunks."""
    doc = _doc("# A\n\nFirst.\n\n# B\n\nSecond.")
    result = chunk(doc)
    assert len(result) >= 2
    result[0]["metadata"]["injected"] = True
    assert "injected" not in result[1]["metadata"]


# ---------------------------------------------------------------------------
# chunk_id stability (determinism)
# ---------------------------------------------------------------------------

def test_chunk_ids_are_stable():
    doc = _doc("# Heading\n\nSome content.")
    first = [c["chunk_id"] for c in chunk(doc)]
    second = [c["chunk_id"] for c in chunk(doc)]
    assert first == second


def test_chunk_ids_differ_by_content():
    doc_a = _doc("# A\n\nContent A.")
    doc_b = _doc("# A\n\nContent B.")
    ids_a = {c["chunk_id"] for c in chunk(doc_a)}
    ids_b = {c["chunk_id"] for c in chunk(doc_b)}
    assert ids_a != ids_b


def test_chunk_ids_differ_by_source():
    doc_a = _doc("Same text.", meta={"source_id": "source_a"})
    doc_b = _doc("Same text.", meta={"source_id": "source_b"})
    ids_a = {c["chunk_id"] for c in chunk(doc_a)}
    ids_b = {c["chunk_id"] for c in chunk(doc_b)}
    assert ids_a != ids_b


# ---------------------------------------------------------------------------
# Max chars splitting
# ---------------------------------------------------------------------------

def test_large_section_splits_on_paragraphs():
    long_body = "\n\n".join(f"Paragraph {i}. " + "x" * 100 for i in range(10))
    doc = _doc(f"# Big Section\n\n{long_body}")
    result = chunk(doc, max_chars=300)
    assert len(result) > 1
    for c in result:
        assert len(c["text"]) <= 400  # allow reasonable overage for single paras


def test_empty_doc():
    doc = _doc("")
    result = chunk(doc)
    assert len(result) == 1
    assert result[0]["chunk_id"]


# ---------------------------------------------------------------------------
# Real formulary
# ---------------------------------------------------------------------------

def test_real_formulary_chunks():
    from data.seed import seed, SYNTHETIC_DIR
    from veritrace.ingest.parsers import parse_markdown

    seed()
    path = SYNTHETIC_DIR / "formulary_2026.md"
    if path.exists():
        doc = parse_markdown(path)
        result = chunk(doc)
        assert len(result) >= 3  # at least a few sections
        # Every chunk should have source_id
        for c in result:
            assert c["metadata"]["source_id"] == "formulary_2026"
