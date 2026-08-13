from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

from study_agent.adapters.workarounds import (
    MAX_PDF_MARKDOWN_OUTPUT_BYTES,
    canonical_pdf_markdown,
    worker,
)
from study_agent.adapters.workarounds.renderer import FIXED_PDF_WARNING, normalize_page_text


def test_renderer_normalizes_text_and_keeps_fixed_visible_loss_warning() -> None:
    assert normalize_page_text("  e\u0301\r\n\x00line\r\n\t\n") == "  é\nline"
    rendered = canonical_pdf_markdown(("  e\u0301\r\n\x00line", "\nsecond\n"))
    assert rendered.decode("utf-8") == (
        f"{FIXED_PDF_WARNING}\n\n# PDF document\n\n## Page 1\n\n  é\nline"
        "\n\n## Page 2\n\nsecond\n"
    )
    assert b"OCR was not performed" in rendered
    assert b"\x00" not in rendered


@pytest.mark.parametrize("pages", [(), ("\n\t",), ("", "\x00\r\n")])
def test_renderer_rejects_empty_and_image_only_documents(pages: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="no extractable text"):
        canonical_pdf_markdown(pages)


def test_renderer_enforces_output_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    renderer = importlib.import_module("study_agent.adapters.workarounds.renderer")
    monkeypatch.setattr(renderer, "MAX_PDF_MARKDOWN_OUTPUT_BYTES", 64)
    with pytest.raises(ValueError, match="output exceeds the limit"):
        renderer.canonical_pdf_markdown(("x" * 128,))
    assert MAX_PDF_MARKDOWN_OUTPUT_BYTES > 64


def test_worker_imports_without_optional_parser_and_has_no_in_process_fallback() -> None:
    assert "pypdf" not in sys.modules
    reloaded = importlib.reload(worker)
    assert reloaded.PdfWorkerError is worker.PdfWorkerError
    assert "pypdf" not in sys.modules


def test_worker_fails_closed_when_containment_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker, "containment_supported", lambda: False)
    with pytest.raises(worker.PdfWorkerError, match="resource_containment_unavailable"):
        worker.parse_in_worker(b"%PDF-1.7\nfixture", timeout_seconds=1)
    assert "pypdf" not in sys.modules


def test_worker_does_not_claim_unverified_darwin_containment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    assert worker.containment_supported() is False


def test_workaround_adapter_has_no_network_model_shell_or_dynamic_plugin_imports() -> None:
    root = Path(__file__).parents[4] / "src" / "study_agent" / "adapters" / "workarounds"
    forbidden = {
        "httpx",
        "requests",
        "openai",
        "subprocess",
        "socket",
        "study_agent.model",
        "study_agent.capabilities",
        "study_agent.playbooks",
    }
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.append(node.module)
        assert not any(
            name in forbidden or any(name.startswith(f"{item}.") for item in forbidden)
            for name in imported
        ), path

    worker_tree = ast.parse((root / "worker.py").read_text(encoding="utf-8"))
    top_level_imports = [
        node for node in worker_tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    top_level_pypdf = [
        node
        for node in top_level_imports
        if (
            any(alias.name.startswith("pypdf") for alias in node.names)
            if isinstance(node, ast.Import)
            else (node.module or "").startswith("pypdf")
        )
    ]
    assert top_level_pypdf == []
    entry = next(
        node
        for node in ast.walk(worker_tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_worker_entry"
    )
    limit_calls = [
        node
        for node in ast.walk(entry)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "apply_resource_limits"
    ]
    pypdf_imports = [
        node
        for node in ast.walk(entry)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "importlib"
        and node.func.attr == "import_module"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "pypdf"
    ]
    assert len(limit_calls) == 1
    assert len(pypdf_imports) == 1
    source = (root / "worker.py").read_text(encoding="utf-8")
    assert source.index("apply_resource_limits()") < source.index('import_module("pypdf")')
