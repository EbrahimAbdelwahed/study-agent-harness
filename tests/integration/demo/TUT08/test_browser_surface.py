from __future__ import annotations

import json
import threading
from http.client import HTTPConnection

from study_agent.demo.browser import create_server


def _journey(entry: str) -> dict[str, object]:
    return {
        "learner_entry": entry,
        "status": "recovered",
        "status_trace": ({"step": 1, "status": "completed", "detail": "Grounded"},),
        "source_state": {"fixture": "heart-valves.md", "evidence": ("A fact",)},
        "evidence_refresh_sequence": 2,
        "discovered_capabilities": ("explain_concept",),
        "parity": True,
    }


def test_local_browser_journey_serves_page_state_and_free_form_entry() -> None:
    server = create_server("127.0.0.1", 0, journey=_journey)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        host, port = server.server_address
        connection = HTTPConnection(host, port, timeout=2)
        connection.request("GET", "/")
        page_response = connection.getresponse()
        page = page_response.read()
        assert page_response.status == 200
        assert b"Start anywhere" in page
        assert b"Context conflicts" in page
        connection.close()

        connection = HTTPConnection(host, port, timeout=2)
        connection.request("GET", "/api/state")
        state_response = connection.getresponse()
        state_response.read()
        assert state_response.status == 200
        assert state_response.getheader("Content-Type") == "application/json; charset=utf-8"
        connection.close()

        body = json.dumps({"learner_entry": "  Explain the aortic valve  "}).encode()
        connection = HTTPConnection(host, port, timeout=2)
        connection.request(
            "POST",
            "/api/entry",
            body=body,
            headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
        )
        entry_response = connection.getresponse()
        updated = entry_response.read()
        assert entry_response.status == 200
        assert json.loads(updated)["learner_entry"] == "Explain the aortic valve"
        connection.close()

        # Equivalent payloads are byte-stable for deterministic offline checks.
        connection = HTTPConnection(host, port, timeout=2)
        connection.request("GET", "/api/state")
        assert connection.getresponse().read() == updated
        connection.close()

        connection = HTTPConnection(host, port, timeout=2)
        connection.request("POST", "/api/entry", body=b'{"learner_entry":"   "}')
        invalid_response = connection.getresponse()
        assert invalid_response.status == 400
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)
