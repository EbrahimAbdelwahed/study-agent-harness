# Slice 06: OpenAI reference tutor host

## Outcome

A bounded external host uses GPT-5.6 to read tutor snapshots and choose trusted
capabilities while all authority and study behavior remain in existing seams.

## Contract

- OpenAI Responses support is an optional technical model adapter.
- The agent loop has a maximum step budget and explicit interruption behavior.
- Uploaded files become host-bound snapshots before the agent may propose a
  role or ingestion action.
- A deterministic scripted host exercises the same path offline.
- API keys remain environment-only; subscription mode is documented separately.
