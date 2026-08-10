# Independent browser-sandbox review

Date: 2026-08-10 CEST
Commit: `3248e0e` (`test: make browser journey sandbox-safe`)
Parent: `e595593`
Bead: `study-agent-harness-integration-browser-sandbox-test-s9fa`

## Verdict

**FAIL — the replacement test is green and sandbox-safe, but it does not fully
prove the public browser contract and leaves a fail-closed framing gap
uncovered.** No production files were changed by this review.

## Scope and diff

`git diff --stat 3248e0e^ 3248e0e` reports one changed file:
`tests/integration/demo/TUT08/test_browser_surface.py` (117 insertions, 55
deletions). The new test uses the real `BaseHTTPRequestHandler`,
`BrowserSurface`, journey callback, parser, and response writer over an
in-memory request/response transport, so it does not allocate a TCP socket.

## Verification

The first unsandboxed `uv` attempts could not read the shared cache:
`error: failed to open file /Users/ebrahimabdelwahed/.cache/uv/sdists-v9/.git:
Operation not permitted`. Re-running the same offline commands with approved
read access to that existing cache produced these results:

| Exact command | Result |
| --- | --- |
| `uv run --frozen --offline --python 3.13 --extra dev pytest -q tests/unit/demo tests/integration/demo/TUT08` | **PASS** — 13 passed in 0.55s |
| `uv run --frozen --offline --python 3.13 --extra dev pytest -q tests/integration/demo/TUT08` | **PASS** — 2 passed in 0.33s |
| `uv run --frozen --offline --python 3.13 --extra dev ruff check src/study_agent/demo tests/unit/demo tests/integration/demo/TUT08` | **PASS** — all checks passed |
| `uv run --frozen --offline --python 3.13 --extra dev ruff check .` | **PASS** — all checks passed |
| `uv run --frozen --offline --python 3.13 --extra dev mypy --strict src/study_agent/demo/browser.py tests/integration/demo/TUT08/test_browser_surface.py` | **PASS** — no issues in 2 source files |
| `uv run --frozen --offline --python 3.13 --extra dev mypy` | **PASS** — no issues in 572 source files |
| `git diff --check 3248e0e^ 3248e0e` | **PASS** |

The required temporary artifact was written to
`/private/tmp/browser-sandbox-independent-test-20260810.md`; `test -s
/private/tmp/browser-sandbox-independent-test-20260810.md` passes after the
artifact is populated with this report.

## Handler probes

The exact inline probe used the test's in-memory transport and called the real
handler. Results:

| Probe | Status |
| --- | ---: |
| Empty `POST /api/entry`, `Content-Length: 0` | 400 |
| Invalid JSON | 400 |
| Incomplete JSON body | 400 |
| Declared length shorter than supplied JSON | 400 |
| Declared length `999`, supplied complete shorter JSON | **200** |
| Unsupported `GET /api/nope` | 404 |
| `GET /health` | 200 |
| `GET /api/state` | 200 |

For health, state, and all adversarial responses, the emitted
`Content-Length` equaled the captured body byte count; JSON responses had
`Content-Type: application/json; charset=utf-8` and `Cache-Control: no-store`.

A second inline probe replaced `socket.socket` with a constructor that raises,
then drove `GET /api/state` through the real handler. It returned 200, invoked
the journey exactly once, and emitted a correctly framed response. This is
evidence that the new test path performs no TCP construction or bind while the
handler, journey, and response writer execute.

## Findings

### 1. Overlong `Content-Length` is accepted (high residual risk)

`_BrowserRequestHandler.do_POST` reads `self.rfile.read(length)` but never
checks that the number of bytes read equals the declared length. The probe with
`Content-Length: 999` and a complete shorter JSON body therefore returned 200
and updated the in-memory learner entry. A peer that closes a short body can
reach the same path on a real stream. If the browser endpoint is required to be
fail-closed on malformed request framing, this should return 400; the new test
does not pin that contract. This behavior is in unchanged production code, so
it is a residual risk rather than a regression introduced by `3248e0e`.

The probe called “fragmented” above was an incomplete body in one in-memory
buffer, not a true TCP segmentation test. The replacement test likewise does
not exercise a real stream split across reads.

### 2. The integration test bypasses the public composition seam (architecture concern)

The prior test exercised `create_server("127.0.0.1", 0)`, a serving thread, and
`HTTPConnection`. The new test imports private `_BrowserRequestHandler` and
`_BrowserServer`, constructs a private-shaped `_InMemoryBrowserServer`, and
uses `cast` to satisfy the handler's private server type. Those names are not
in `study_agent.demo.browser.__all__`. This is acceptable as a narrowly scoped
sandbox workaround only if the private handler construction is deliberately
treated as the tested interface; as a durable architecture choice it is a
regression because the integration test no longer verifies `create_server`,
server construction, or the public localhost boundary.

The production boundary itself remains fail-closed in this commit (source is
unchanged). A runtime probe temporarily replaced `_BrowserServer.server_bind`
and `.server_activate` to avoid the sandbox bind, then called `create_server`
with `127.0.0.1`, `localhost`, `0.0.0.0`, `::1`, `192.168.1.1`, `127.0.0.2`, and
the empty string. Only the first two were accepted; every other host raised
`ValueError("browser server must bind to localhost")` before bind.

## Residual risk

- The focused and full static/test gates are green, but no test in this commit
  covers short-read versus declared `Content-Length` equality.
- The sandbox-safe test provides strong handler-level coverage but not public
  server creation, loopback binding, serving-loop lifecycle, or real HTTP
  connection framing.
- Beads status was not inspected because the required `br ... show` command
  was blocked by `Operation not permitted` while opening the external
  `.beads/.write.lock`; the bead was not closed.
- Agent Mail startup identified `QuietBirch`, but inbox and thread service
  access returned HTTP 404 from the configured local MCP endpoint. Completion
  coordination was attempted separately after commit.
