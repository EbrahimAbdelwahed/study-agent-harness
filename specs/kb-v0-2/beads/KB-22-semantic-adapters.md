# KB-22: Optional vector, reranker, and model-projector adapters

Status: Proposed parent — child adapter decisions required
Risk: High
Depends On: KB-08, KB-11, KB-12, KB-16
Parent coverage: §§7, 10, 14, 16; M9

## Outcome

Embeddings, vector search, reranking, and model projection plug into existing
projection/registry/fusion seams without changing callers or weakening the
permanent lexical path.

## Child beads

- [KB-22A](KB-22A-embedding-vector-adapters.md): embedding contract and vector
  retrievers/index implementations.
- [KB-22B](KB-22B-reranker-adapter.md): bounded post-fusion reranker.
- [KB-22C](KB-22C-model-projector.md): optional model-produced handles,
  summaries, and concepts.

Each child requires its own dependency/provider/security decision and must earn
its own measured quality delta.

## Out of scope

- Hardcoding DeepSeek/OpenAI or another provider, mandatory network access, or
  replacing lexical retrieval.
