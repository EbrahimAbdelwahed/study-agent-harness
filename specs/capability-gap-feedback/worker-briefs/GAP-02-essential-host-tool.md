# Worker Brief: GAP-02 essential agent-facing host report tracer

## Assignment and Status

After the essential GAP-01 registry is green, expose only the local reporting
surface. This does not complete GAP-02 rate/nonblocking/workaround policy and
must not be marked Done.

## Allowed Files

- `src/study_agent/feedback/host_tool.py`.
- `src/study_agent/feedback/__init__.py`: additive exports.
- `src/study_agent/ports/capability_gap.py`: additive sink protocol.
- `tests/unit/feedback/test_capability_gap_host_tool.py`.
- `tests/integration/test_capability_gap_tracer.py`.
- `tests/architecture/test_capability_gap_boundaries.py`: additive gates.

## Exact Public Contract

- `WorkaroundSuggestionKind`: `none`, `retry_later`, `use_supported_format`,
  `manual_entry`, `use_existing_capability`. It is a suggestion only and is not
  persisted by the essential GAP-01 subset.
- `CapabilityGapProposal(category, requested_operation_kind,
  safe_target_kind, impact_kind, workaround_suggestion_kind=none)`: frozen,
  closed enum fields only; strict exact canonical JSON codec for the agent tool.
- `CapabilityGapHostContext(harness_version, contract_identity,
  contract_major, correlation_id, idempotency_fingerprint, observed_at,
  limitation_receipt=None)`: trusted host-only, never accepted from proposal or
  serialized into portable evidence.
- `FeatureGapSink.record(observation, write_context) ->
  CapabilityGapCompactView`.
- `CapabilityGapHostToolManifest`: exact identity
  `report_capability_gap@1.0.0`, description and strict proposal JSON schema;
  no handler/execution/provider metadata.
- `CapabilityGapHostTool.report(proposal, context) ->
  CapabilityGapReportResult`. It maps proposal+trusted context to GAP-01 values
  and calls the sink exactly once. It performs no model/network/tool/capability
  call and never catches `BaseException`.
- `CapabilityGapReportResult(report_id, gap_key, occurrence_count,
  disposition, local_only=True)`: exact fields, no detail/identity/receipt/text.
  Valid successful local writes only; validation/store errors raise a bounded
  typed `CapabilityGapHostToolError`. Nonblocking orchestration policy is
  explicitly deferred to the embedding host.

Attempted workaround outcomes and execution receipts are deferred; proposal
cannot express attempted success/failure. No grant is created and suggestion is
never executed.

## Essential Proof

An agent proposes unsupported PDF table preservation using only closed values;
trusted host supplies a verified limitation receipt; tool records locally;
exact retry deduplicates; a distinct trusted report increments; SQLite restart
returns count two. Hostile dictionaries with text/path/filename/secret/command,
ids/error/grants/priority/severity/outcomes/external targets fail before sink.
Seven StudyTools and capability discovery remain byte-identical.

## Stop Conditions

Stop rather than add StudyTool/capability registration, execution, workaround
receipt, rate limiting, outbox/export, UI/CLI, network, Flywheel/devkit/GitHub,
or automatic improvement. Do not mark GAP-02 Done.
