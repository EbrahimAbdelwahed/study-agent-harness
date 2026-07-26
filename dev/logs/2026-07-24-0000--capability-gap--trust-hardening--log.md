# Log: capability-gap trust hardening

Date: 2026-07-24 00:00
Area: capability-gap

## Summary

Applied the two approved P1 findings for GAP-03 and GAP-04A. Unsupported-source
evidence is now comparison-only and cannot manufacture persistence authority;
the tracer requires an exact host-trusted limitation receipt already present in
the write context. Workaround execution now requires host-composed executor and
approval-authority ports, exact task/manifest/grant/effect bindings, and a
receipt returned by the executor. The public service no longer accepts a caller
receipt or boolean approval.

## Files Changed

- `src/study_agent/feedback/source_tracer.py`: fail closed without/mismatch of
  host limitation receipt; removed evidence receipt factory.
- `src/study_agent/feedback/workarounds.py`: closed approval DTO/codec, task and
  quality fingerprints, exact grant resolution, receipt validation.
- `src/study_agent/feedback/workaround_service.py`: injected executor and
  approval authority; no caller-authored attempted outcome.
- `src/study_agent/ports/workaround.py`: provider-neutral inward approval port.
- `tests/unit/feedback/test_source_tracer.py`: absent/forged/matching receipt
  coverage.
- `tests/unit/workarounds/test_workaround_{contracts,registry,service}.py`:
  approval, executor, forged receipt, selection, and codec coverage.

## Verification

- Focused pytest: 14 passed.
- Ruff focused source/tests: passed.
- mypy focused source: passed.
- Architecture boundary tests: passed.
- `git diff --check`: passed.

## Notes

- No outbox, SQLite, host-tool, provider, network, dependency, or concrete
  workaround implementation was changed.
- GAP-03/GAP-04A remain in progress pending parent integration and broader
  milestone gates.
