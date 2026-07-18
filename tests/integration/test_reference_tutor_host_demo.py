from __future__ import annotations

from examples.reference_tutor_host import run_reference_demo


def test_reference_demo_runs_the_same_offline_host_trace_for_both_adapters() -> None:
    result = run_reference_demo()

    assert result["discovered_capabilities"] == ("explain_concept",)
    assert result["scripted_statuses"] == ("completed", "suspended", "completed")
    assert result["recorded_statuses"] == result["scripted_statuses"]
    assert result["parity"] is True
    assert result["recorded_request_count"] == 3
    assert result["evidence_refresh_sequence"] == 2
    assert result["gateway_trace"] == (
        "start:completed",
        "start:suspended",
        "resume:completed",
    )


def test_reference_demo_captures_only_a_safe_markdown_descriptor() -> None:
    result = run_reference_demo()
    descriptor = result["captured_file"]

    assert isinstance(descriptor, dict)
    assert descriptor["media_type"] == "text/markdown"
    assert descriptor["display_name"] == "Lesson notes"
    assert "/" not in descriptor["id"]
    assert "original_filename" not in descriptor
    assert "content" not in descriptor
