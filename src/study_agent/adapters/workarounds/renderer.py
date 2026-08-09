"""Deterministic, intentionally lossy PDF text rendering."""

from __future__ import annotations

import unicodedata

MAX_PDF_MARKDOWN_OUTPUT_BYTES = 4 * 1024 * 1024
FIXED_PDF_WARNING = (
    "> Warning: This Markdown was mechanically extracted from a PDF. OCR was "
    "not performed; layout, tables, images, equations, and reading order may "
    "be incomplete."
)


def normalize_page_text(value: str) -> str:
    """Normalize extracted text without inventing visual structure."""

    normalized = unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
    # Keep only text, tabs, and line breaks.  This also makes parser-version
    # oddities such as NUL separators deterministic without making a claim
    # about PDF layout.
    normalized = "".join(
        character
        for character in normalized
        if character in {"\n", "\t"} or not unicodedata.category(character).startswith("C")
    )
    lines = [line.rstrip() for line in normalized.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def canonical_pdf_markdown(page_texts: tuple[str, ...] | list[str]) -> bytes:
    """Render page text into stable UTF-8 Markdown and enforce output bounds."""

    pages = tuple(normalize_page_text(text) for text in page_texts)
    if not pages or not any(page for page in pages):
        raise ValueError("pdf contains no extractable text")
    sections = [FIXED_PDF_WARNING, "# PDF document"]
    for index, page in enumerate(pages, start=1):
        sections.extend((f"## Page {index}", page))
    output = ("\n\n".join(sections) + "\n").encode("utf-8")
    if len(output) > MAX_PDF_MARKDOWN_OUTPUT_BYTES:
        raise ValueError("pdf markdown output exceeds the limit")
    return output


__all__ = [
    "FIXED_PDF_WARNING",
    "MAX_PDF_MARKDOWN_OUTPUT_BYTES",
    "canonical_pdf_markdown",
    "normalize_page_text",
]
