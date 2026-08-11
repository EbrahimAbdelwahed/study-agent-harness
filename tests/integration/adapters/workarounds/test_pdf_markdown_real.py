from __future__ import annotations

import csv
import importlib.metadata
import importlib.util
from hashlib import sha256
from pathlib import Path

import pytest
from packaging.requirements import Requirement

from study_agent.adapters.package_trust import PackageTrustBinding
from study_agent.adapters.workarounds import PDF_MARKDOWN_MANIFEST, PdfMarkdownExecutor
from study_agent.adapters.workarounds.worker import containment_supported
from study_agent.feedback import (
    WorkaroundApprovalReceipt,
    WorkaroundInputKind,
    WorkaroundOutputKind,
    WorkaroundReceiptStatus,
    WorkaroundTask,
)

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("pypdf") is None or not containment_supported(),
    reason="install the pdf extra on a platform with verified worker containment",
)


def _host_binding(package_name: str, expected_version: str) -> PackageTrustBinding:
    """Compose one explicit RECORD-bound graph as the embedding host would."""

    pending = [package_name]
    distributions: dict[str, importlib.metadata.Distribution] = {}
    root: Path | None = None
    while pending:
        name = pending.pop()
        try:
            distribution = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError as error:
            pytest.skip(f"host dependency {name!r} is not installed: {error}")
        key = distribution.metadata.get("Name", name).lower().replace("-", "_")
        if key in distributions:
            continue
        candidate_root = Path(str(distribution.locate_file(""))).resolve()
        if root is None:
            root = candidate_root
        elif candidate_root != root:
            pytest.skip("optional distribution graph spans multiple package roots")
        distributions[key] = distribution
        for requirement_text in distribution.requires or ():
            requirement = Requirement(requirement_text)
            if requirement.marker is not None and not requirement.marker.evaluate():
                continue
            pending.append(requirement.name)

    assert root is not None
    manifest: dict[str, tuple[str, int]] = {}
    for distribution in distributions.values():
        record = distribution.read_text("RECORD")
        if record is None:
            pytest.fail(f"{distribution.metadata.get('Name', '?')} has no RECORD")
        for row in csv.reader(record.splitlines()):
            if len(row) != 3 or not row[0] or "\\" in row[0]:
                pytest.fail("host RECORD contains an invalid path")
            relative = Path(row[0])
            if relative.is_absolute() or any(
                part in ("", ".", "..") for part in relative.parts
            ):
                pytest.fail("host RECORD contains a non-portable path")
            path = root / relative
            if not path.is_file() or path.is_symlink():
                pytest.fail(f"host RECORD file is unavailable: {row[0]}")
            value = path.read_bytes()
            manifest[relative.as_posix()] = (sha256(value).hexdigest(), len(value))
    return PackageTrustBinding.from_manifest(
        package_name, root, expected_version, manifest
    )


def _minimal_text_pdf() -> bytes:
    """Build a tiny text-bearing PDF without a second test dependency."""

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length 41 >>\nstream\nBT /F1 12 Tf 72 720 Td (Hello PDF) Tj ET\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    document = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, value in enumerate(objects, start=1):
        offsets.append(len(document))
        document.extend(f"{index} 0 obj\n".encode("ascii"))
        document.extend(value)
        document.extend(b"\nendobj\n")
    xref_offset = len(document)
    document.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    document.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    document.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(document)


def test_real_pypdf_worker_produces_deterministic_markdown(tmp_path: Path) -> None:
    pdf = _minimal_text_pdf()
    task = WorkaroundTask(
        WorkaroundInputKind.PDF,
        WorkaroundOutputKind.MARKDOWN,
        sha256(pdf).hexdigest(),
    )
    (tmp_path / "input.pdf").write_bytes(pdf)
    approval = WorkaroundApprovalReceipt(
        task.fingerprint,
        PDF_MARKDOWN_MANIFEST.identity,
        PDF_MARKDOWN_MANIFEST.version,
        PDF_MARKDOWN_MANIFEST.fingerprint,
        PDF_MARKDOWN_MANIFEST.effect_fingerprint,
        "a" * 64,
    )
    executor = PdfMarkdownExecutor(
        tmp_path,
        "input.pdf",
        "derived.md",
        task.input_fingerprint,
        approval,
        package_trust=_host_binding("pypdf", "6.14.2"),
    )
    first = executor.execute(task, PDF_MARKDOWN_MANIFEST.identity)
    second = executor.execute(task, PDF_MARKDOWN_MANIFEST.identity)
    assert first.status is WorkaroundReceiptStatus.ATTEMPTED_SUCCEEDED
    assert second.to_bytes() == first.to_bytes()
    assert (tmp_path / "derived.md").read_text(encoding="utf-8").endswith("Hello PDF\n")
