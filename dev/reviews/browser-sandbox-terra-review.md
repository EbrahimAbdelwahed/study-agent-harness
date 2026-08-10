# Terra review: browser sandbox fix

Commit under review: `3248e0e` (`test: make browser journey sandbox-safe`)
Parent: `e595593`
Reviewer: QuietMaple
Bead: `study-agent-harness-integration-browser-sandbox-review-qsjn`

## Verdict

CHANGES REQUESTED

## Findings

### P1 — The integration test deletes the real-server contract

The prior test created the public `create_server("127.0.0.1", 0)`, started
`serve_forever` on a thread, and drove it through `http.client.HTTPConnection`.
The replacement at `tests/integration/demo/TUT08/test_browser_surface.py:92-136`
constructs `_BrowserRequestHandler` directly with an in-memory object cast to
`socket.socket` and a dataclass cast to `_BrowserServer`. It therefore never
executes `create_server`, `ThreadingHTTPServer` binding, `serve_forever`,
shutdown/close, or a kernel TCP read/write path.

Deletion test: make valid loopback construction or server lifecycle fail; the
replacement integration test still passes. The current production guard is
unchanged and the unit test still rejects `0.0.0.0`, but no test now proves that
the valid loopback browser can actually start and serve requests. This matters
to the stated browser contract even though the current sandbox cannot bind a
socket: a passing in-memory test cannot distinguish a sandbox restriction from
a broken production server.

Required follow-up: retain this in-memory test for the sandbox-safe parser and
payload coverage, and retain a real-socket integration test for environments
that permit loopback binding, skipping only the known `PermissionError` at
server construction. Alternatively, introduce an explicit transport seam and
test both the production socket adapter and the deterministic driver.

### P2 — The new integration test couples itself to private implementation seams

The test imports `_BrowserRequestHandler` and `_BrowserServer`, neither of
which is in `browser.py`'s public `__all__`. A harmless internal rename or a
change in `BaseHTTPRequestHandler` setup will break the test even when the
public browser surface remains compatible. Conversely, the private cast hides
whether the fake transport still satisfies the socket behavior the handler
actually relies on. This is brittle module/interface coupling, not a stable
browser contract.

Required follow-up: place the in-memory driver behind a deliberate test-only
factory/adapter or exercise a public `create_server` seam; keep private symbol
imports out of the integration-level contract test.

## Coverage assessment

- The replacement does exercise the real request parser, handler dispatch,
  product journey, JSON response writer, response headers, state update, and
  blank-entry rejection. The focused suite reports six passing tests.
- The invalid-input case remains semantic JSON validation, but malformed HTTP
  framing, partial socket reads, and connection lifecycle behavior are no
  longer covered by this integration test. Those cases were not broad in the
  old test either; the material regression is the complete loss of the valid
  socket/server path.
- Production remains loopback-only/fail-closed in the reviewed source:
  `_require_local_host` rejects non-`127.0.0.1`/`localhost` hosts, and no
  production browser code changed in `3248e0e`. The new test simply provides
  weaker evidence for that property.

## Verification

- `python -m pytest -q tests/integration/demo/TUT08/test_browser_surface.py tests/unit/demo/test_browser.py` — **6 passed**.
- `python -m ruff check tests/integration/demo/TUT08/test_browser_surface.py` — **passed**.
- `PYTHONPATH=src python -c '... create_server("127.0.0.1", 0) ...'` — expected sandbox `PermissionError: [Errno 1] Operation not permitted`; this confirms the environmental trigger, not production correctness.
- `mypy` probe was unavailable in this environment (`No module named mypy`).

## Residual risks

- A future production regression in valid loopback binding, server startup, or
  TCP response behavior can pass the replacement integration test.
- Agent Mail inbox/endpoint access returned HTTP 404 after the required agent
  start, so coordination delivery must be retried separately.
