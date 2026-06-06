"""Document parsers — normalize diverse input formats to text + metadata.

Public API
----------
parse(path) -> ParsedDocument
    Auto-detects format by file extension (.pdf, .md, .txt) and dispatches
    to the appropriate parser.

parse_markdown(path) -> ParsedDocument
parse_text(path) -> ParsedDocument
parse_pdf(path) -> ParsedDocument

A ParsedDocument is a TypedDict with keys:
  "text"     : str   — full normalized text (front matter stripped)
  "metadata" : dict  — source metadata including any YAML front matter fields

Governance metadata fields passed through when present in front matter:
  source_id, title, authority_level, effective_date, supersedes,
  superseded_by, tenant_id
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TypedDict


# ---------------------------------------------------------------------------
# Output type
# ---------------------------------------------------------------------------


class ParsedDocument(TypedDict):
    text: str
    metadata: dict


# ---------------------------------------------------------------------------
# YAML front matter helper (no yaml dependency — simple regex parser)
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(?P<fm>.*?)\n---\s*\n", re.DOTALL
)
_KV_RE = re.compile(r'^(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?P<value>.+)$')


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Extract YAML-like front matter key-value pairs.

    Returns (metadata_dict, remaining_text_without_front_matter).
    Values are coerced: quoted strings stripped, 'true'/'false' → bool.
    Only flat key:value pairs are parsed (no nested YAML).
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    fm_block = match.group("fm")
    remaining = text[match.end():]
    metadata: dict = {}

    for line in fm_block.splitlines():
        m = _KV_RE.match(line.strip())
        if not m:
            continue
        key = m.group("key")
        raw = m.group("value").strip().strip('"').strip("'")
        if raw.lower() == "true":
            value: object = True
        elif raw.lower() == "false":
            value = False
        else:
            value = raw
        metadata[key] = value

    return metadata, remaining


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def parse_markdown(path: Path) -> ParsedDocument:
    """Parse a Markdown file.

    Extracts YAML front matter metadata; returns the Markdown body as text.
    """
    raw = path.read_text(encoding="utf-8")
    metadata, body = _parse_frontmatter(raw)
    metadata.setdefault("source_id", path.stem)
    metadata.setdefault("title", path.stem.replace("_", " ").title())
    metadata["file_path"] = str(path)
    metadata["format"] = "markdown"
    return ParsedDocument(text=body.strip(), metadata=metadata)


def parse_text(path: Path) -> ParsedDocument:
    """Parse a plain-text file.

    Treats leading YAML front matter (if present) the same as Markdown.
    """
    raw = path.read_text(encoding="utf-8")
    metadata, body = _parse_frontmatter(raw)
    metadata.setdefault("source_id", path.stem)
    metadata.setdefault("title", path.stem.replace("_", " ").title())
    metadata["file_path"] = str(path)
    metadata["format"] = "text"
    return ParsedDocument(text=body.strip(), metadata=metadata)


def parse_pdf(path: Path) -> ParsedDocument:
    """Parse a PDF file using PyMuPDF (fitz).

    Concatenates all page texts. Page numbers are preserved as
    a list in metadata["pages"]. No front matter extraction for PDF.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise ImportError("PyMuPDF is required for PDF parsing. Run: pip install PyMuPDF") from exc

    doc = fitz.open(str(path))
    pages: list[str] = []
    for page in doc:
        pages.append(page.get_text())  # type: ignore[arg-type]
    doc.close()

    full_text = "\n".join(pages).strip()
    metadata: dict = {
        "source_id": path.stem,
        "title": path.stem.replace("_", " ").title(),
        "file_path": str(path),
        "format": "pdf",
        "page_count": len(pages),
    }
    return ParsedDocument(text=full_text, metadata=metadata)


# ---------------------------------------------------------------------------
# Auto-dispatch
# ---------------------------------------------------------------------------

_PARSERS = {
    ".md": parse_markdown,
    ".markdown": parse_markdown,
    ".txt": parse_text,
    ".text": parse_text,
    ".pdf": parse_pdf,
}


def parse(path: Path | str) -> ParsedDocument:
    """Parse a document at *path*, auto-detecting format by extension.

    Raises ValueError for unsupported extensions.
    """
    path = Path(path)
    ext = path.suffix.lower()
    parser = _PARSERS.get(ext)
    if parser is None:
        raise ValueError(
            f"Unsupported file extension {ext!r}. Supported: {list(_PARSERS)}"
        )
    return parser(path)
