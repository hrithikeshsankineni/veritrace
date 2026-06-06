"""Tests for veritrace.ingest.parsers."""

from pathlib import Path

import pytest

from veritrace.ingest.parsers import parse, parse_markdown, parse_text, parse_pdf


# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------

def test_markdown_parses_frontmatter(tmp_path):
    f = tmp_path / "test.md"
    f.write_text(
        '---\nsource_id: test_doc\ntitle: Test Document\nauthority_level: primary\n---\n\n# Heading\n\nBody text.',
        encoding="utf-8",
    )
    doc = parse_markdown(f)
    assert doc["metadata"]["source_id"] == "test_doc"
    assert doc["metadata"]["title"] == "Test Document"
    assert doc["metadata"]["authority_level"] == "primary"
    assert "# Heading" in doc["text"]
    assert "source_id:" not in doc["text"]


def test_markdown_without_frontmatter(tmp_path):
    f = tmp_path / "plain.md"
    f.write_text("# Just a heading\n\nSome content.", encoding="utf-8")
    doc = parse_markdown(f)
    assert "# Just a heading" in doc["text"]
    assert doc["metadata"]["source_id"] == "plain"


def test_markdown_format_tag(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("hello", encoding="utf-8")
    doc = parse_markdown(f)
    assert doc["metadata"]["format"] == "markdown"


def test_markdown_real_formulary():
    """Parse the actual seeded formulary — confirms real file works."""
    from data.seed import seed, SYNTHETIC_DIR
    seed()
    path = SYNTHETIC_DIR / "formulary_2026.md"
    if path.exists():
        doc = parse_markdown(path)
        assert doc["metadata"]["source_id"] == "formulary_2026"
        assert doc["metadata"]["authority_level"] == "primary"
        assert "Atorvastatin" in doc["text"]


# ---------------------------------------------------------------------------
# Plain text parser
# ---------------------------------------------------------------------------

def test_text_parses_frontmatter(tmp_path):
    f = tmp_path / "doc.txt"
    f.write_text(
        '---\nsource_id: txt_doc\ntenant_id: acme\n---\n\nSome plain text.',
        encoding="utf-8",
    )
    doc = parse_text(f)
    assert doc["metadata"]["source_id"] == "txt_doc"
    assert doc["metadata"]["tenant_id"] == "acme"
    assert doc["text"] == "Some plain text."


def test_text_format_tag(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("content", encoding="utf-8")
    assert parse_text(f)["metadata"]["format"] == "text"


# ---------------------------------------------------------------------------
# Auto-dispatch (parse)
# ---------------------------------------------------------------------------

def test_auto_dispatch_md(tmp_path):
    f = tmp_path / "file.md"
    f.write_text("hello", encoding="utf-8")
    assert parse(f)["metadata"]["format"] == "markdown"


def test_auto_dispatch_txt(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("hello", encoding="utf-8")
    assert parse(f)["metadata"]["format"] == "text"


def test_unsupported_extension(tmp_path):
    f = tmp_path / "file.docx"
    f.write_text("data", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        parse(f)


# ---------------------------------------------------------------------------
# Metadata governance fields passed through
# ---------------------------------------------------------------------------

def test_governance_metadata_passthrough(tmp_path):
    f = tmp_path / "policy.md"
    f.write_text(
        '---\nsource_id: pol\neffective_date: "2026-01-01"\nsupersedes: old_pol\n---\n\nPolicy text.',
        encoding="utf-8",
    )
    doc = parse_markdown(f)
    assert doc["metadata"]["effective_date"] == "2026-01-01"
    assert doc["metadata"]["supersedes"] == "old_pol"
