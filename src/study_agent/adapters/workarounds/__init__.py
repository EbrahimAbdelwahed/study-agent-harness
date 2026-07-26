"""Host-authorized, optional local workaround adapters.

The package itself is dependency-free.  The PDF parser is imported only by
the short-lived worker process in :mod:`pdf_markdown` after its resource
limits have been installed.
"""

from .manifest import (
    PDF_MARKDOWN_EXECUTOR_FINGERPRINT,
    PDF_MARKDOWN_LIMITATION_FINGERPRINT,
    PDF_MARKDOWN_MANIFEST,
    PDF_MARKDOWN_PARSER_IDENTITY,
    PDF_MARKDOWN_RENDERER_POLICY_VERSION,
    PdfMarkdownManifest,
)
from .pdf_markdown import (
    MAX_PDF_BYTES,
    MAX_PDF_MARKDOWN_OUTPUT_BYTES,
    MAX_PDF_PAGES,
    PDF_MAGIC,
    PdfMarkdownBinding,
    PdfMarkdownExecutionError,
    PdfMarkdownExecutor,
    PdfMarkdownFilesystemError,
    bind_pdf_markdown_executor,
    canonical_pdf_markdown,
    pdf_markdown_provenance_bytes,
)

__all__ = [
    "MAX_PDF_BYTES",
    "MAX_PDF_MARKDOWN_OUTPUT_BYTES",
    "MAX_PDF_PAGES",
    "PDF_MAGIC",
    "PDF_MARKDOWN_EXECUTOR_FINGERPRINT",
    "PDF_MARKDOWN_LIMITATION_FINGERPRINT",
    "PDF_MARKDOWN_MANIFEST",
    "PDF_MARKDOWN_PARSER_IDENTITY",
    "PDF_MARKDOWN_RENDERER_POLICY_VERSION",
    "PdfMarkdownBinding",
    "PdfMarkdownExecutionError",
    "PdfMarkdownExecutor",
    "PdfMarkdownFilesystemError",
    "PdfMarkdownManifest",
    "bind_pdf_markdown_executor",
    "canonical_pdf_markdown",
    "pdf_markdown_provenance_bytes",
]
