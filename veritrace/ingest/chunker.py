"""Structure-aware, hierarchical, deterministic chunker.

Public API
----------
chunk(doc, max_chars) -> list[Chunk]
    Split a ParsedDocument into Chunk objects.

A Chunk is a TypedDict with:
  "chunk_id"   : str   — stable SHA-256 hash of (source_id + text)
  "text"       : str   — chunk body text
  "heading"    : str   — nearest ancestor heading (empty string if none)
  "section"    : str   — top-level section heading
  "metadata"   : dict  — all governance metadata from the parent document

Strategy
--------
1. Split on Markdown headings (# / ## / ### / ####) to respect document structure.
2. If a section exceeds *max_chars*, further split on blank-line paragraph
   boundaries, carrying the heading context into each sub-chunk.
3. Every chunk inherits the full parent metadata (source_id, authority_level,
   effective_date, tenant_id, …) so tenant-scoped retrieval works at chunk level.
4. chunk_id = SHA-256(source_id + text) — deterministic across runs.

This is deliberately minimal: no ML, no sliding window, no sentence splitting.
The structure split is sufficient for the policy/formulary documents in the
synthetic corpus and is fully deterministic.
"""

from __future__ import annotations

import hashlib
import re
from typing import TypedDict

from veritrace.ingest.parsers import ParsedDocument

_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
_MAX_CHARS_DEFAULT = 800


class Chunk(TypedDict):
    chunk_id: str
    text: str
    heading: str        # nearest heading (h1–h4)
    section: str        # top-level (h1) section
    metadata: dict


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_chunk_id(source_id: str, text: str) -> str:
    return hashlib.sha256(f"{source_id}:{text}".encode()).hexdigest()[:16]


def _split_by_paragraphs(text: str, max_chars: int) -> list[str]:
    """Split *text* into blocks of at most *max_chars* on blank-line boundaries."""
    paragraphs = re.split(r"\n{2,}", text)
    blocks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if current_len + len(para) + 2 > max_chars and current:
            blocks.append("\n\n".join(current))
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len += len(para) + 2

    if current:
        blocks.append("\n\n".join(current))

    return blocks


def _split_heading_sections(text: str) -> list[tuple[str, str, str]]:
    """Split *text* into (h1_section, nearest_heading, body) tuples.

    Returns one tuple per heading section. Text before the first heading
    is returned as ("", "", preamble_text).
    """
    sections: list[tuple[str, str, str]] = []
    parts = _HEADING_RE.split(text)
    # _HEADING_RE.split gives: [pre, level, title, body, level, title, body, ...]
    # pre is the text before the first heading (index 0)
    # Then triples: (level_str, title, body)

    preamble = parts[0].strip()
    if preamble:
        sections.append(("", "", preamble))

    current_h1 = ""
    i = 1
    while i < len(parts) - 2:
        level_str = parts[i]       # e.g. "##"
        title = parts[i + 1].strip()
        body = parts[i + 2].strip()
        level = len(level_str)
        if level == 1:
            current_h1 = title
        heading = title
        sections.append((current_h1, heading, body))
        i += 3

    return sections


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def chunk(doc: ParsedDocument, max_chars: int = _MAX_CHARS_DEFAULT) -> list[Chunk]:
    """Split *doc* into structure-aware chunks.

    Parameters
    ----------
    doc:
        A ParsedDocument from veritrace.ingest.parsers.
    max_chars:
        Soft maximum characters per chunk. Sections larger than this are
        further split on paragraph boundaries.

    Returns
    -------
    List of Chunk dicts, each with chunk_id, text, heading, section, metadata.
    """
    source_id = doc["metadata"].get("source_id", "unknown")
    text = doc["text"]
    metadata = doc["metadata"]

    heading_sections = _split_heading_sections(text)
    chunks: list[Chunk] = []

    for section_h1, heading, body in heading_sections:
        if not body:
            # Heading with no body: include heading text as a small chunk
            body = heading

        if len(body) <= max_chars:
            blocks = [body]
        else:
            blocks = _split_by_paragraphs(body, max_chars)
            if not blocks:
                blocks = [body]

        for block in blocks:
            block = block.strip()
            if not block:
                continue
            cid = _make_chunk_id(source_id, block)
            chunks.append(
                Chunk(
                    chunk_id=cid,
                    text=block,
                    heading=heading,
                    section=section_h1,
                    metadata=dict(metadata),  # shallow copy — don't mutate parent
                )
            )

    # Edge case: empty doc → one empty chunk so callers don't break
    if not chunks:
        chunks.append(
            Chunk(
                chunk_id=_make_chunk_id(source_id, ""),
                text="",
                heading="",
                section="",
                metadata=dict(metadata),
            )
        )

    return chunks
