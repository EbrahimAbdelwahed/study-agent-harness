from __future__ import annotations

import base64
from hashlib import sha256
from pathlib import Path

import pytest

from study_agent.adapters.package_trust import PackageTrustBinding
from study_agent.adapters.workarounds import (
    PDF_MARKDOWN_EXECUTOR_FINGERPRINT,
    PDF_MARKDOWN_LIMITATION_FINGERPRINT,
    PDF_MARKDOWN_MANIFEST,
    PdfMarkdownExecutor,
)
from study_agent.feedback import (
    WorkaroundApprovalReceipt,
    WorkaroundInputKind,
    WorkaroundOutputKind,
    WorkaroundReceiptStatus,
    WorkaroundTask,
)


def _task(pdf: bytes) -> WorkaroundTask:
    return WorkaroundTask(
        WorkaroundInputKind.PDF,
        WorkaroundOutputKind.MARKDOWN,
        sha256(pdf).hexdigest(),
    )


def _package_trust(tmp_path: Path) -> PackageTrustBinding:
    root = (tmp_path / "pypdf-site").resolve()
    package = root / "pypdf"
    dist = root / "pypdf-6.14.2.dist-info"
    package.mkdir(parents=True, exist_ok=True)
    dist.mkdir(exist_ok=True)
    files = {
        "pypdf/__init__.py": b"__version__ = '6.14.2'\n",
        "pypdf-6.14.2.dist-info/METADATA": (
            b"Metadata-Version: 2.3\nName: pypdf\nVersion: 6.14.2\n"
        ),
        "pypdf-6.14.2.dist-info/WHEEL": (
            b"Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\n"
        ),
    }
    for relative, value in files.items():
        path = root / relative
        path.write_bytes(value)
    record_rows = [
        f"{relative},sha256={base64.urlsafe_b64encode(sha256(value).digest()).decode().rstrip('=')},{len(value)}"
        for relative, value in files.items()
    ]
    record_rows.append("pypdf-6.14.2.dist-info/RECORD,,")
    (dist / "RECORD").write_text("\n".join(record_rows) + "\n", encoding="utf-8")
    manifest = {
        relative: (
            sha256((root / relative).read_bytes()).hexdigest(),
            (root / relative).stat().st_size,
        )
        for relative in (*files, "pypdf-6.14.2.dist-info/RECORD")
    }
    return PackageTrustBinding.from_manifest("pypdf", root, "6.14.2", manifest)


def test_bound_executor_publishes_deterministic_output_without_paths_in_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf = b"%PDF-1.7\nfixture"
    task = _task(pdf)
    approval = WorkaroundApprovalReceipt(
        task.fingerprint,
        PDF_MARKDOWN_MANIFEST.identity,
        PDF_MARKDOWN_MANIFEST.version,
        PDF_MARKDOWN_MANIFEST.fingerprint,
        PDF_MARKDOWN_MANIFEST.effect_fingerprint,
        "a" * 64,
    )
    (tmp_path / "input.pdf").write_bytes(pdf)
    output = b"> Warning: fixture\n\n# PDF document\n\n## Page 1\n\nHello\n"
    monkeypatch.setattr(
        "study_agent.adapters.workarounds.pdf_markdown.parse_in_worker",
        lambda content, timeout, **_: output,
    )

    receipt = PdfMarkdownExecutor(
        tmp_path,
        "input.pdf",
        "derived.md",
        task.input_fingerprint,
        approval,
        package_trust=_package_trust(tmp_path),
    ).execute(task, PDF_MARKDOWN_MANIFEST.identity)

    assert receipt.status is WorkaroundReceiptStatus.ATTEMPTED_SUCCEEDED
    assert receipt.output_fingerprint == sha256(output).hexdigest()
    assert receipt.limitation_fingerprint == PDF_MARKDOWN_LIMITATION_FINGERPRINT
    assert receipt.executor_fingerprint == PDF_MARKDOWN_EXECUTOR_FINGERPRINT
    assert (tmp_path / "derived.md").read_bytes() == output


def test_failed_parser_does_not_create_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf = b"%PDF-1.7\nfixture"
    task = _task(pdf)
    approval = WorkaroundApprovalReceipt(
        task.fingerprint,
        PDF_MARKDOWN_MANIFEST.identity,
        PDF_MARKDOWN_MANIFEST.version,
        PDF_MARKDOWN_MANIFEST.fingerprint,
        PDF_MARKDOWN_MANIFEST.effect_fingerprint,
        "b" * 64,
    )
    (tmp_path / "input.pdf").write_bytes(pdf)
    def fail_parser(content: bytes, timeout: float) -> bytes:
        raise RuntimeError("timeout")

    monkeypatch.setattr(
        "study_agent.adapters.workarounds.pdf_markdown.parse_in_worker", fail_parser
    )

    receipt = PdfMarkdownExecutor(
        tmp_path,
        "input.pdf",
        "derived.md",
        task.input_fingerprint,
        approval,
    ).execute(task, PDF_MARKDOWN_MANIFEST.identity)

    assert receipt.status is WorkaroundReceiptStatus.ATTEMPTED_FAILED
    assert receipt.output_fingerprint is None
    assert not (tmp_path / "derived.md").exists()
