from __future__ import annotations

import io
import json
import socket
import threading
from dataclasses import dataclass
from http.client import HTTPConnection
from typing import cast

import pytest

from study_agent.demo.browser import (
    BrowserSurface,
    _BrowserRequestHandler,
    _BrowserServer,
    create_server,
)


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


@dataclass
class _InMemoryBrowserServer:
    surface: BrowserSurface
    learner_entry: str = "I have ten minutes. Help me understand heart valves."


class _ResponseBuffer(io.BytesIO):
    def close(self) -> None:
        self.flush()


class _InMemoryRequest:
    def __init__(self, raw_request: bytes) -> None:
        self._request = io.BytesIO(raw_request)
        self.response = _ResponseBuffer()

    def makefile(self, mode: str, buffering: int = -1) -> io.BytesIO:
        del buffering
        if mode == "rb":
            return self._request
        if mode == "wb":
            return self.response
        raise ValueError(f"unsupported stream mode: {mode}")

    def sendall(self, data: bytes) -> None:
        self.response.write(data)


@dataclass(frozen=True)
class _Response:
    status: int
    headers: dict[str, str]
    body: bytes


def _request(
    server: _InMemoryBrowserServer,
    method: str,
    path: str,
    *,
    body: bytes = b"",
    headers: tuple[tuple[str, str], ...] = (),
) -> _Response:
    # Drive the real parser, handler, product journey, and response writer
    # without allocating a TCP socket that this execution sandbox forbids.
    request_lines = [f"{method} {path} HTTP/1.1", "Host: 127.0.0.1", "Connection: close"]
    request_lines.extend(f"{name}: {value}" for name, value in headers)
    raw_request = ("\r\n".join((*request_lines, "", ""))).encode() + body
    request = _InMemoryRequest(raw_request)
    _BrowserRequestHandler(
        cast(socket.socket, request),
        ("127.0.0.1", 0),
        cast(_BrowserServer, server),
    )

    raw_headers, response_body = request.response.getvalue().split(b"\r\n\r\n", maxsplit=1)
    status_line, *header_lines = raw_headers.split(b"\r\n")
    response_headers = {
        name.decode("ascii").lower(): value.decode("latin-1").strip()
        for name, value in (line.split(b":", maxsplit=1) for line in header_lines)
    }
    return _Response(int(status_line.split()[1]), response_headers, response_body)


def test_local_browser_journey_drives_page_state_and_free_form_entry() -> None:
    server = _InMemoryBrowserServer(BrowserSurface(_journey))

    page_response = _request(server, "GET", "/")
    assert page_response.status == 200
    assert b"Start anywhere" in page_response.body
    assert b"Context conflicts" in page_response.body

    state_response = _request(server, "GET", "/api/state")
    assert state_response.status == 200
    assert state_response.headers["content-type"] == "application/json; charset=utf-8"
    state = json.loads(state_response.body)
    assert state["status"] == "recovered"
    assert state["material"]["fixture"] == "heart-valves.md"
    assert state["evidence"]["sequence"] == 2
    assert state["conversation"]["status_trace"][0]["status"] == "completed"
    assert state["parity"] is True

    body = json.dumps({"learner_entry": "  Explain the aortic valve  "}).encode()
    entry_response = _request(
        server,
        "POST",
        "/api/entry",
        body=body,
        headers=(
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(body))),
        ),
    )
    updated = entry_response.body
    assert entry_response.status == 200
    assert json.loads(updated)["learner_entry"] == "Explain the aortic valve"

    # Equivalent payloads are byte-stable for deterministic offline checks.
    assert _request(server, "GET", "/api/state").body == updated

    invalid_response = _request(
        server,
        "POST",
        "/api/entry",
        body=b'{"learner_entry":"   "}',
        headers=(("Content-Length", str(len(b'{"learner_entry":"   "}'))),),
    )
    assert invalid_response.status == 400
    assert json.loads(invalid_response.body)["error"] == "learner_entry is invalid"

    malformed_response = _request(
        server,
        "POST",
        "/api/entry",
        body=b"{malformed",
        headers=(("Content-Length", str(len(b"{malformed"))),),
    )
    assert malformed_response.status == 400
    assert json.loads(malformed_response.body)["error"] == "learner_entry is invalid"


def test_local_browser_journey_serves_page_state_and_free_form_entry() -> None:
    try:
        server = create_server("127.0.0.1", 0, journey=_journey)
    except PermissionError as error:
        pytest.skip(f"loopback sockets unavailable in this environment: {error}")

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        host, port = cast(tuple[str, int], server.server_address)
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

    assert not server_thread.is_alive()
