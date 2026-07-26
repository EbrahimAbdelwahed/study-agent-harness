# Feature Spec: Knowledge Base v0.2 — Retrieval Architecture

Status: Proposed
Owner: Ebrahim
Date: 2026-07-26
Parent spec: `docs/specs/oss-study-agent-harness-v0-1.md`
Extends: `docs/specs/oss-harness-v0-1-immutable-text-ingestion.md`, `docs/specs/oss-harness-v0-1-lexical-retrieval-and-citations.md`
Bead decomposition: [`../../specs/kb-v0-2/README.md`](../../specs/kb-v0-2/README.md)

---

## 1. Goal

Define the knowledge base of the study agent harness: how heterogeneous study material enters it,
how it is represented and indexed, how an agent retrieves over it, and how every returned claim
resolves to immutable verifiable source.

The design target is a harness that is **source-agnostic, model-agnostic, and agent-agnostic**. No
document dialect, no embedding provider, no reranker, no agent framework, and no tutoring workflow
may appear in the domain model. All of them are adapters behind ports.

## 2. Non-goals

- Tutoring behavior, scheduling, spaced repetition, session policy. The KB answers "what does the
  corpus say and where exactly." It never decides what to teach.
- UI, HTTP surface, MCP wire format, or any agent SDK binding. Primitives here are typed function
  contracts; transport is separate work.
- A planner or synthesis step inside the KB. Orchestration belongs to the calling agent.
- PDF→Markdown conversion internals and audio transcription internals. Both are external versioned
  tools; the KB consumes their output and records which version produced it.
- Image generation, figure layout, print output.

## 3. Principles

**P1 — One uniform retrievable unit.** Every indexable thing in the corpus — a passage, a section, a
whole-document card, a figure, an exam item, a table — is the same row shape (§5). A new source type
adds a connector, never a new retrieval path, index, scorer, or result type.

**P2 — Canonical content is immutable and content-addressed.** Original bytes are never modified or
deleted. The append-only event stream is the only authority. Every index, tree, and projection is a
rebuildable read model.

**P3 — Citations resolve to a byte-stable substrate, never to model output.** A citation addresses a
span of a frozen normalized-text artifact, or a content-addressed blob. Model-derived text can lead a
reader to a citation; it can never *be* one.

**P4 — Index the normalized projection; cite the canonical text.** What gets indexed is a normalized
projection of a unit (§7). What gets quoted and verified is the canonical span. Separating the search
handle from the evidence is the single highest-leverage decision in this design.

**P5 — The lexical trunk is never optional; everything semantic is an adapter.** The KB must be fully
usable with zero network, zero keys, zero model calls. Vector search, reranking, captioning, and OCR
are capability-gated. Their absence degrades result quality, never correctness or availability.

**P6 — Retrievers are registered, not enumerated.** Fusion consumes whatever retrievers are present
(§10). Adding a retriever is configuration, not a code change in any caller.

**P7 — Prefer a structural key to a semantic guess.** Where a structural identifier exists (heading
path, page number, content hash, authored anchor, declared correspondence), use it. Similarity may
*rank* within a structurally valid candidate set; it may not *establish* an association a structural
key could have established.

**P8 — Ingestion decisions are reviewable and permanent.** Any uncertain ingest-time decision
(a figure's placement, a unit boundary, a correspondence) is recorded with confidence and is
correctable by an event. Re-running an extractor with a newer model must never silently discard a
human correction.

**P9 — Incremental by content hash.** Unit identity is content-derived, so re-ingestion diffs at unit
level and only changed units are re-indexed and re-embedded (§11).

## 4. Layers

```
CANONICAL   (immutable, event-authorized, citable)
  BlobStore          original bytes by sha256: PDF, md, txt, transcript, image, audio
  Substrate          frozen normalized-text artifact per source revision, + page_map
  SourceRevision     (source_id, revision_id), manifest, class/role/trust, supersession
  FigureBlob         content-addressed image bytes + extraction provenance

PROJECTED   (rebuildable from events; not authoritative)
  DocumentTree       document → chapter → section → passage, typed regions
  RetrievableUnit    the uniform row (§5)
  UnitLinks          parent/child, anchored figures, item↔unit, prerequisite
  ScopeMembership    named bundles of sources

DERIVED     (model or tool output; cache-keyed; deletable; non-citable)
  IndexProjection    normalized search handle per unit (§7)
  FigureCard         visual kind, role, depicts, description
  FigureLabels       in-image text (OCR or vision)
  FigureSurrogate    text rendering of an essential figure
  ConceptLabels      unit ↔ concept assignments
  Embedding          vectors over any projection

OPERATIONAL (discardable)
  FTS5 indexes, vector index, sync state, caches, run checkpoints
```

### 4.1 Substrate

PDFs have no stable character offsets, so the locally converted Markdown is the citation substrate.
Derived mechanically, then **frozen and content-addressed with the tool that produced it**:

```
substrate_id  = sha256(normalized_text_bytes)
substrate_meta = { source_blob_sha256, converter_name, converter_version,
                   normalization_version, produced_at, page_map }
```

`page_map` is an ordered list of `(char_offset, page_number)` breakpoints so any span reports a
human-verifiable page hint without the page being part of citation identity.

Re-converting produces a **new substrate and revision**. The old one is retained while any citation,
anchor, or artifact references it. Garbage collection is manual and event-recorded.

### 4.2 Supersession

A new revision of a `source_id` supersedes earlier ones; default retrieval excludes superseded
revisions while their citations still resolve, so past answers stay verifiable. Cross-source
succession (a new textbook edition under a new file) is an explicit `source.superseded_by@1` event.
Citation migration across editions is never automatic: the KB reports "superseded, successor exists"
and the agent decides.

**There is no recency scoring.** Staleness in a study corpus is edition supersession — structural,
not a scoring heuristic. A ten-year-old anatomy chapter is not stale.

## 5. The retrievable unit

The spine of the architecture. One shape for everything indexable, so a new source type never adds a
retrieval path.

```python
@dataclass(frozen=True, slots=True)
class RetrievableUnit:
    unit_id: UnitId                  # content-derived (§5.3)
    source_id: SourceId
    revision_id: RevisionId

    unit_kind: UnitKind              # passage | section | document_card | figure
                                     # | exam_item | table | emphasis | definition
    granularity: int                 # 0 document, 1 chapter, 2 section, 3 passage, 4 fragment
    structural_path: tuple[str, ...] # authored anchors or derived slugs, root → self

    canonical_ref: CanonicalRef      # TextSpan(substrate_id, start, end) | BlobRef(sha256)
    index_projection: ProjectionRef  # derived; what is actually indexed (§7)

    meta: UnitMeta                   # source_class, role, trust, review_status,
                                     # flags, ordinal, page_hint, language
    links: UnitLinks                 # parent, children, figures, items, prerequisites
    signal: UnitSignal               # rarity, length, structural weight, retrieval frequency
```

`canonical_text` is never stored on the unit. It is loaded from the substrate on demand and
checksum-verified, which is what keeps the index discardable and prevents a tampered index from
producing unsupported citations.

### 5.1 Unit kinds

All kinds share the row shape. `unit_kind` and `granularity` drive ranking priors, expansion
behavior, and filters — never separate code paths.

| Kind | Granularity | Canonical ref | Notes |
|---|---|---|---|
| `document_card` | 0 | span of the document's front region | Navigational; the "what is this source about" unit |
| `section` | 1–2 | span of the whole section | Coarse retrieval target; parent for expansion |
| `passage` | 3 | span within a section | Default evidence unit |
| `definition`, `emphasis`, `table` | 4 | span of the region | Typed fragments (§8.3) |
| `figure` | 4 | image blob | Anchored into a text unit (§9) |
| `exam_item` | 4 | span of the item | Typed assessment record (§9.6) |

### 5.2 The granularity ladder

A single input yields units at several granularities, deliberately. This is the transferable form of
both multi-level code chunking (a file emitting file-level *and* function-level records) and
message-level promotion inside a long thread: **coarse units win topical queries, fine units win
specific-term queries, and fusion decides.**

Fine units are not emitted exhaustively. A fragment is promoted to its own unit only if it clears a
signal gate (§8.4), which keeps the index from filling with low-information rows.

### 5.3 Identity

Content-derived, consistent with v0.1:

| Id | Derivation |
|---|---|
| `revision_id` | `(source_id, source_blob_sha256, substrate_id, ingest_policy_version)` |
| `unit_id` | `(revision_id, structural_path, unit_kind, granularity, canonical_ref, unitizer_version)` |
| `figure_id` | `sha256(image_bytes)` — identity is the image itself |
| `anchor_id` | `(figure_id, revision_id, unit_id, char_offset, anchor_policy_version)` |
| `projection_id` | `(unit_id, projector_name, projector_version, model_id?)` |
| `artifact_id` | `(kind, input_hash, model_id, prompt_version)` |

Content-hash figure identity means duplicate figures across editions, lectures, and handouts collapse
into one record with several anchors, for free.

## 6. Connectors

The only ingestion extension point. A connector declares what a source is, how to read it, and how to
emit units — nothing else in the stack changes when one is added.

```python
class SourceConnector(Protocol):
    name: str
    version: str
    def declares(self) -> ConnectorManifest: ...
        # accepted media types, source_class, default role/trust,
        # capabilities required (none | ocr | vision | model),
        # "good at answering" hints for the corpus manifest (§12)
    def substrate(self, blob: Blob) -> SubstrateProduction: ...
        # frozen normalized text + page_map, or BlobRef for non-text
    def units(self, substrate: Substrate, tree: DocumentTree) -> Iterable[UnitDraft]: ...
    def conformance(self, substrate: Substrate) -> ConformanceReport: ...
```

Baseline connectors: `markdown_document`, `pdf_document`, `study_material`, `exam_bank`,
`plain_notes`. A connector may be pure-Python and model-free; requiring a model is declared, and the
connector is skipped with a recorded reason when that capability is absent.

**Document dialects live in connector profiles, never in the domain model.** A profile declares how
one authoring convention maps onto generic unit kinds — which markup means "instructor emphasis",
which means "summary", which inline markers set uncertainty flags. Appendix A is one such profile.

### 6.1 Conformance, not rejection

Connectors report findings at `error` / `warning` / `info` and **never block ingestion**. A
non-conformant document ingests with weaker structural guarantees (falling back to window chunking)
and its findings are recorded on the revision. A corpus that rejects imperfect documents is a corpus
nobody uses. `doctor` aggregates conformance per scope, which is how dialect drift gets noticed.

## 7. Index projections

The core retrieval decision, and the one thing to get right.

**What is indexed is not the canonical text.** Each unit has a normalized projection: a consistent,
vocabulary-regularized handle, whatever the unit's source or shape. Canonical text remains what is
quoted, cited, and verified.

```python
@dataclass(frozen=True, slots=True)
class IndexProjection:
    unit_id: UnitId
    handle: str                     # one-line searchable statement of what this unit answers
    summary: str | None             # 1–3 sentences
    key_terms: tuple[str, ...]      # rare/technical tokens — lexically extracted, no model
    aliases: tuple[str, ...]        # synonyms, abbreviations, Latin ↔ vernacular
    covers: tuple[str, ...]         # concept labels
    structural_context: str         # ancestor heading path, rendered
    projector_name: str
    projector_version: str
    model_id: str | None            # None ⇒ produced offline
```

Why this beats indexing raw text: raw passages vary wildly in information density and phrasing, short
passages beat long ones on cosine similarity for the wrong reasons, and a passage's meaning often
depends on structure the passage itself doesn't contain. A normalized projection removes all three
problems at once, and it does so *independently of whether a vector index exists* — BM25 over
regularized handles and alias lists already recovers much of the paraphrase recall that embeddings
are usually bought for.

### 7.1 Projectors, in cost order

Every unit gets a projection. Which projector produced it is recorded, and quality degrades
gracefully:

| Projector | Cost | `handle` source |
|---|---|---|
| `structural` | free, offline | The unit's own heading, plus ancestor path. Requires descriptive headings. |
| `lexical` | free, offline | Adds `key_terms` by corpus IDF and `aliases` from a per-scope term dictionary. |
| `authored` | free | The document declares the handle explicitly (a summary line, a recap title). |
| `model` | paid, optional | LLM produces `handle`, `summary`, `covers` from the unit plus its ancestors. |

**A descriptive heading is a zero-cost handle.** This is why the authoring guidance in Appendix A
insists on standalone descriptive headings and self-contained sections: it makes the free projector
competitive with the paid one. It is authoring-time normalization substituting for index-time
distillation.

`key_terms` extraction is purely lexical — corpus-wide IDF, no model — and it is what makes rare
technical tokens (Latin structure names, enzyme names, flag-like identifiers) reliably findable. This
is the cheapest large win in the design.

### 7.2 Projection is versioned and invalidatable

`projection_id` includes projector version and model id, so upgrading a projector invalidates and
regenerates projections without touching canonical state or unit identity. Units are stable across
projector churn; that separation is what makes the derived layer safely disposable.

## 8. Structure and unitization

### 8.1 Document tree

Derived deterministically from the substrate, no model:

```python
@dataclass(frozen=True, slots=True)
class TreeNode:
    node_id: NodeId
    parent_id: NodeId | None
    path: tuple[str, ...]           # authored anchors preferred; derived slugs otherwise
    heading_text: str
    region_kind: RegionKind         # body | emphasis | summary | table | code | figure_ref | item
    span: tuple[int, int]
    flags: frozenset[str]           # uncertainty markers declared by the connector profile
```

The tree gives outline browsing, coarse retrieval targets, post-rank expansion, and figure
inheritance. None of it requires a model, which is why it lands early (§13, M2).

### 8.2 Unitization rules

1. A unit never crosses a tree-node boundary. This is the substantive change from v0.1, where a
   1,200-character window could span two sections.
2. A section under the size cap yields one `passage` unit plus one `section` unit (the ladder, §5.2).
3. An oversized section is window-split **inside** the node, at paragraph boundaries, each window
   inheriting the node's path and flags.
4. Tables, emphasis regions, and code fences are **atomic and never split**. Splitting a table
   destroys the row–header association that makes it useful.
5. Structure-poor input falls back to pure 1,200-character windows — the v0.1 behavior, preserved
   exactly as the universal floor.

Changing unitization bumps `unitizer_version` and therefore every `unit_id`. Migration is a reindex
plus a best-effort citation remap that **reports** unmigrated citations rather than guessing. Doing
this once, early, is far cheaper than later.

### 8.3 Typed fragments

A connector profile maps its dialect onto generic fragment kinds: `emphasis` (marked instructor
stress), `summary` (recap/bullet digest), `table`, `definition`, `figure_ref`, `item`. Fragments are
independently retrievable units, and uncertainty markers set `flags` on their containing unit.

**Flags must reach the agent in every evidence row.** A tutor generating a flashcard from a passage
flagged as unverified or as transcribed-from-degraded-audio, without knowing it is flagged, is
precisely the failure the flag system exists to prevent.

### 8.4 Fragment promotion gate

Fine-grained units are emitted only when they carry signal, so the index does not fill with
low-information rows. A fragment is promoted when it clears a weighted threshold over:

- contains at least one high-IDF term relative to the scope corpus;
- meets a minimum length;
- sits inside a structurally weighted region (emphasis, summary, definition, table);
- is referenced by an exam item or a figure anchor.

Thresholds are per-scope configuration with defaults, and the gate is evaluated with no model calls.

## 9. Figures

Figures carry a large share of the information in visual disciplines and are the hardest thing in
this KB to retrieve reliably. The design is shaped by measured failure, described in §9.7.

### 9.1 Figures are units

A figure is a `RetrievableUnit` with `canonical_ref = BlobRef(sha256)` and one or more anchors into
text units. Nothing about figure retrieval is a separate subsystem: same row, same fusion, same
evidence shape.

```python
@dataclass(frozen=True, slots=True)
class FigureAnchor:
    anchor_id: AnchorId
    revision_id: RevisionId
    unit_id: UnitId                 # host text unit
    char_offset: int
    anchor_kind: str                # exact | generated | derived
    confidence: float               # 1.0 for exact and generated
    method: str                     # authored | marker | page_geometry | caption_match | human
    policy_version: str
```

| Anchor kind | When | Confidence |
|---|---|---|
| `exact` | The document places the figure at a known offset (an authored embed) | 1.0, no inference |
| `generated` | The figure is rendered from a canonical marker in the text; the marker's position *is* the anchor | 1.0 |
| `derived` | Inferred from a PDF's page geometry: bbox → char offset via `page_map`, plus nearest preceding heading on the page. Caption proximity is a tiebreak, not the primary signal | computed from geometric agreement, never from a similarity score |

Only `derived` anchors carry uncertainty, and they are the only ones eligible for review (§9.5).

### 9.2 Retrieve text, inherit figures

Default figure retrieval is **inheritance**: text retrieval returns units, and each evidence row
carries the figures anchored to that unit and its ancestors, ordered by anchor confidence and document
order. No figure-specific scoring is involved. Section retrieval is reliable — headings, prose, and
BM25 all work well — so relevance is decided once, structurally, at ingestion, where it can be
reviewed and permanently corrected, rather than re-decided stochastically per query.

Direct figure search exists and is secondary (§12, `figures()`): it queries the figure lexical surface,
then **re-attaches each candidate to its anchor unit and filters out figures whose host unit is
irrelevant to the query.** That filter is the mechanism that suppresses plausible-but-wrong matches.
When a figure is scored, its score blends its own lexical score with its host unit's — a thin figure
on an obviously relevant section should rank; a rich figure on an irrelevant section should not.

### 9.3 In-image label text is the highest-yield signal

Figures in these disciplines are covered in printed labels: Latin structure names, enzyme names,
pathway intermediates. These are exactly the rare high-IDF tokens that BM25 ranks best and that
embeddings blur together. `FigureLabels` (Tesseract offline, or a vision model for quality) feeds the
figure projection's `key_terms`, and it is the largest single precision gain available in figure
retrieval.

### 9.4 Derived figure artifacts

All optional, cache-keyed, non-citable as fact.

- **FigureCard** — `visual_kind` (diagram / micrograph / radiograph / chart / chemical structure /
  photo / schema), `role`, `depicts[]`, `description`. Feeds `handle` and `covers`.
- **FigureLabels** — in-image text (§9.3).
- **FigureSurrogate** — a structured text rendering of an `essential` figure, so a text-only retriever
  can reach content that exists only in the diagram. A claim traced to a surrogate cites the
  **figure**, with the surrogate attached as clearly-labeled derived context.
- **Figure text embeddings** — over card, labels, and caption. Direct image-embedding similarity search
  is deliberately deprioritized: it is the technique whose inconsistency motivated this design, and it
  would have to earn ranking weight against the anchor and figure evals (§14) before being trusted.

`role: essential | illustrative | decorative` gates surrogate production: `essential` means the figure
carries information absent from the prose. A wrong `decorative` call silently hides content, so §16
raises whether cheap structural signals (size class, presence of OCR labels, formal caption, adjacency
to an emphasis region) predict `essential` well enough to avoid a vision-model dependency for that
specific call.

### 9.5 Review is canonical and permanent

`figure.anchor_reviewed@1` records `confirm`, `re_anchor(unit_id, offset)`, or `reject`. Review state
survives re-extraction with a newer extractor or model (P8): re-running produces *provisional* anchors
that must be reconciled against reviewed ones — a reviewed anchor wins, a rejected figure stays
rejected, a re-anchored figure keeps its human placement. The review queue is prioritized by expected
value: low-confidence `derived` anchors on frequently-retrieved host units. The KB exposes the queue;
who works it is not the KB's concern.

### 9.6 Exam items

Exam questions are not prose and must not be unitized as prose. An `exam_item` unit carries stem,
options, answer, rationale, `item_kind` (mcq / open / true-false / matching / image-based), referenced
figures, and derived links to the units that teach the tested concept. Those links are explicitly
derived: a wrong link degrades a practice set, it never corrupts a citation. Items are the
highest-value retrieval target for a tutor ("find questions testing this section").

### 9.7 Why this shape — measured failure

A prior system embedded a *semantic signature* per figure (caption regex + surrounding page text +
a vision caption) and matched it by cosine against a *block embedding* (section title + first three
sentences). Measured on correctly-aligned inputs: max similarity 0.77–0.84, mean ≈0.55, threshold
hand-tuned between 0.5 and 0.7. Four distinct failures, only one of them a tuning problem:

1. **Both sides were proxies.** A guess about the image compared against a guess about the section;
   errors compound multiplicatively.
2. **Positional anchoring was approximate** — images assigned by y-coordinate against LLM-inferred
   block boundaries, then walked backward to the nearest ancestor. A wrong anchor cannot be repaired
   by better ranking downstream.
3. **Cross-document matching produced confident errors.** Figures matched to the wrong lecture at
   similarity 0.56; establishing the correct correspondence *structurally* first raised it to 0.77.
   The fix was structural, not a threshold.
4. **Per-query re-decision.** Relevance was recomputed at match time with nothing persisted, so every
   correction was discarded on the next run. Nothing accumulated.

Hence P7, P8, §9.1 (structural anchors with confidence), §9.2 (inherit, don't search), and §9.8.

### 9.8 Cross-document anchoring requires a declared key

A figure from source A may be anchored into a unit of source B **only** with an explicit recorded
correspondence between A and B (an edition mapping, or a confirmed lecture/chapter correspondence
declared in both documents' metadata, or a human alignment event). Absent that key, cross-document
figure injection is rejected at ingestion.

This costs recall — figures that could be usefully reused stay put — and it buys the elimination of a
class of confidently wrong results the reader cannot detect. In a study context that trade is
strongly favorable.

## 10. Retrieval

### 10.1 Retriever registry

Retrievers are registered, each declaring name, surface, cost, required capability, and default fusion
weight (P6). Fusion consumes whatever is registered:

| Retriever | Surface | Capability | Notes |
|---|---|---|---|
| `lex_projection` | handle + summary + covers + structural context | none | Primary trunk list |
| `lex_terms` | `key_terms` + aliases | none | Rare-token and exact-identifier matches |
| `lex_canonical` | canonical text | none | Catches phrasing absent from the projection |
| `lex_figure` | figure labels + caption + card | none (OCR improves it) | |
| `lex_items` | stem + options + rationale | none | Present only with an exam bank |
| `link_graph` | units linked to already-matching units | none | Cheap non-model structural recall |
| `vec_projection` | projection embeddings | embeddings | Optional adapter |
| `vec_canonical` | canonical-text embeddings | embeddings | Optional adapter |
| `vec_figure` | figure text embeddings | embeddings | Optional adapter |

Only `lex_projection` is required for a functioning KB. Everything else is additive. Query compilation
keeps v0.1 discipline: literal-only compilation, source text and query strings remain untrusted data,
injection strings are indexed and returned verbatim without affecting SQL or control flow.

`link_graph` deserves emphasis: retrieving the neighbors of confirmed matches is a real retriever, it
requires no model, and in a structured study corpus (prerequisites, item↔unit links, figure anchors,
parent/child) it recovers material that no term or vector match would reach.

### 10.2 Pipeline

```
query + scope + filters
   │
   ├─ registered retrievers, in parallel, each returning a ranked list
   │
   ├─ RRF fusion:  score(d) = Σ_l  w_l / (60 + rank_l(d))
   │
   ├─ collapse the granularity ladder: fine units fold into their coarse
   │  ancestor when both matched; the best-scoring granularity represents the group
   │
   ├─ dedupe: unit → section → source
   ├─ diversity cap: max per source, max per section
   ├─ (optional) rerank → top k
   ├─ post-rank context expansion: parent heading path, ±1 sibling, containing section
   ├─ figure attachment by inheritance (§9.2)
   └─→ EvidencePacket
```

Notes on each stage that isn't self-evident:

- **RRF with k=60**, per-list weights defaulting to 1.0. The smoothing constant makes consensus across
  retrievers beat a single strong vote. With only two lexical lists it barely changes ranking; it is
  built anyway because it is the seam where every future retriever plugs in without touching a caller.
  That is its purpose, not immediate ranking gain.
- **Ladder collapse is specific to this design.** Because one input emits units at several
  granularities (§5.2), the same content can occupy several fused slots. Collapsing to the
  best-scoring representative is what makes the ladder a recall gain instead of a duplication problem.
- **Diversity capping matters more here than in a message corpus.** A study corpus is a few large
  documents rather than many small threads, so without a per-source cap one chapter monopolizes the
  top 20.
- **Expansion is strictly post-rank.** Expanding before ranking dilutes the signal that produced the
  hit. Rows carry the narrow cited span and the wider reading context separately: cite narrow, read
  wide.

### 10.3 Ranking priors

- **BM25 supplies term rarity natively**; no separate IDF stage.
- **Source-class prior**, per-scope configurable, replacing recency: reference material ≥ derived study
  material ≥ personal notes for factual queries. A playbook may invert it (a query about what the
  instructor emphasized should prefer the lecture-derived material). The KB supplies the default and
  reports which prior applied.
- **Review-status prior**: confirmed outranks unreviewed at equal relevance.
- **Uncertainty penalty**: flagged units are demoted slightly and **always** flagged, never silently
  dropped.
- **No recency scoring** (§4.2).

### 10.4 Evidence row

```python
@dataclass(frozen=True, slots=True)
class EvidenceRow:
    citation: Citation                     # exact, verifiable (§13)
    text: str                              # canonical span, loaded and checksum-verified
    expanded_text: str | None              # post-rank context, clearly separated
    unit_kind: UnitKind
    granularity: int
    structural_path: tuple[str, ...]
    source_class: str
    role: str
    trust: str
    review_status: str
    flags: frozenset[str]
    figures: tuple[FigureAttachment, ...]
    retriever_provenance: tuple[str, ...]  # which retrievers produced this candidate
    scores: Mapping[str, float]            # per-retriever, fused, rerank
    revision_status: str                   # current | superseded
    projection_provenance: str             # which projector produced the matched handle
    derived_content: tuple[str, ...]       # names of derived artifacts included in this row
```

`retriever_provenance` and `projection_provenance` are load-bearing, not diagnostic. A playbook
generating flashcards may legitimately restrict itself to lexically-confirmed evidence, or refuse to
build a card from a model-projected handle it cannot verify. It cannot do either unless the KB reports
how each row was found.

## 11. Incremental maintenance

Re-ingesting a 500-page textbook or a regenerated study document must not re-embed the corpus.

- Unit identity is content-derived (§5.3), so a new revision diffs against the previous one at unit
  level: unchanged units keep their `unit_id`, their projections, and their embeddings.
- Sync state lives in the same SQLite database as the indexes, so index state and content state cannot
  disagree after a crash.
- Only added or changed units are projected, embedded, and indexed. Removed units are unindexed; their
  citations still resolve against the superseded revision.
- Projector or embedding-model upgrades invalidate projections by `projection_id` without touching
  unit identity, so the reprocessing scope is exactly the affected derived layer.
- `derived.artifact_invalidated@1` records every invalidation, so a rebuild is replayable.

This is what makes a regenerate-often producer affordable: a study document rewritten with two changed
sections costs two units of work, not a full reindex.

## 12. Agent-facing primitives

Narrow, typed, model-free, individually cheap. The KB ships **no planner and no synthesis step** — the
agent, governed by skills and playbooks, is the orchestrator.

| Primitive | Signature | Returns |
|---|---|---|
| `manifest` | `(scope?)` | Corpus capability description: scopes, sources, classes, unit and figure counts, projector coverage, registered retrievers, available adapters, per-source "good at answering" hints, conformance summary |
| `search` | `(query, scope, k, filters, mode=lexical\|fused)` | `EvidencePacket` — the full pipeline |
| `search_lexical` | `(query, scope, k)` | Raw BM25 rows: no fusion, no adapters, no keys, no network |
| `outline` | `(source_id \| scope, depth)` | Document tree with headings, region kinds, figure counts |
| `unit` | `(unit_id, with_children=False)` | Unit text, flags, anchored figures, neighbors |
| `expand` | `(citation \| unit_id, direction=parent\|siblings\|window, budget_chars)` | Wider canonical text with its own citation |
| `resolve` | `(citation)` | Verified exact text or image bytes, or explicit failure |
| `figures` | `(scope, near=unit_id\|query, kind, role, k)` | Figure units with anchors, cards, labels, host unit |
| `items` | `(scope, filters, k)` | Exam items |
| `concepts` | `(scope, concept?\|unit_id?)` | Concept ↔ unit map: where a topic is taught, what a source covers |
| `lineage` | `(citation \| source_id \| figure_id)` | Provenance chain to original bytes |

`manifest` is what an agent reads *before* fanning out — a compact machine-readable description of
what is indexed and what each source is good for, exposed as data instead of baked into a planning
prompt. It is the difference between an agent that plans over the corpus and one that guesses.

`concepts` is navigational rather than evidential: it answers "where is this taught" and "what does
this source cover" without returning evidence, which is a distinct and frequently-needed question.

`search_lexical` is the permanent escape hatch — works with no adapters, no keys, no network, no
projections beyond the free `structural` projector.

**Scopes** are named bundles of sources (a course, an exam, a topic). A source belongs to many scopes
without duplication, and scope defaults are applied per course. Unscoped search over a whole corpus
degrades exactly the way a shared undifferentiated index degrades.

## 13. Citations and verification

```python
TextCitation   = (source_id, revision_id, unit_id, substrate_id, start, end, quoted_checksum)
FigureCitation = (figure_id, blob_sha256, anchor_id?, origin_page?)
DerivedRef     = (artifact_id, kind, projector_or_model, version, subject_citation)
```

`DerivedRef` is deliberately not called a citation: it always carries the canonical citation it
describes, and agent-facing text including derived content must label it as such.

Verification is mechanical and offline:

1. Load the substrate by `substrate_id`; recompute sha256; compare.
2. Slice `[start, end)`; recompute the quoted checksum; compare.
3. Assert the span lies within its declared unit.
4. Figures: load blob by `blob_sha256`; recompute; compare. `origin_page` is a human-checkable hint,
   never identity.
5. Report `revision_status`, and whether a successor exists if superseded.

Any mismatch is an explicit failure, never a silent fallback. A tampered or stale index cannot produce
a citation the canonical bytes do not support.

## 14. Degradation and evaluation

| Missing | Effect |
|---|---|
| Network / keys | Full lexical retrieval, hierarchy, figure inheritance, citations, verification. No new derived artifacts. |
| Model projector | `structural` + `lexical` projections only; paraphrase recall drops, exact-term recall unaffected. |
| Vector adapters | Fewer fused lists; paraphrase recall drops further. |
| Reranker | Fused RRF order is final; precision@5 drops modestly. |
| Vision adapter | No figure cards or surrogates; figures still retrievable by caption and inheritance. |
| OCR | No in-image label search — largest single loss in figure precision. |
| Authored anchors | Unit identity derived from heading text; citations orphan on heading rewordings. |
| All derived artifacts | KB fully functional at reduced quality; artifacts regenerate on demand. |

Evaluation sets, release-blocking given §9.7's history of plausible-but-wrong results at thresholds
that looked reasonable:

- **Retrieval eval** — fixed queries with expected `(source, revision, unit)` targets, including
  `insufficient` cases; run per registered-retriever combination so each adapter's contribution is
  measured rather than assumed.
- **Projection eval** — the same queries against `structural`, `lexical`, and `model` projectors, to
  quantify what the paid projector actually buys over the free one.
- **Figure anchor eval** — ≥100 hand-labeled figures with correct host sections; reports anchor
  precision and recall by `anchor_kind` and confidence bucket. **Anchor precision, not similarity
  score, is the metric that governs figure work.**
- **Figure retrieval eval** — expected figures per query, in inheritance and direct mode.
- **Citation integrity eval** — corruption, tampering, out-of-unit spans, superseded revisions,
  post-reconversion resolution.
- **Incrementality eval** — change two sections of a large document; assert only affected units are
  reprojected, re-embedded, and reindexed.
- **Replay eval** — delete every projection and index, replay events, assert byte-identical
  reconstruction.

## 15. Implementation sequence

Each milestone is independently useful and leaves the KB shippable.

**M1 — Substrate and provenance.** Frozen content-addressed substrate with `page_map`, converter and
normalization versioning, `source.substrate_produced@1`. Everything downstream depends on stable
citations. *No models.*

**M2 — Tree, units, ladder.** `TreeNode` and `RetrievableUnit` projections; unitization rules §8.2;
`section` + `passage` granularities; typed fragments and the promotion gate; `unitizer_version` bump;
citation remap reporting; replay test. *No models.* Largest structural gain per unit of cost.

**M3 — Projections, free tier.** `IndexProjection` with the `structural` and `lexical` projectors,
corpus IDF for `key_terms`, per-scope alias dictionaries. Index `lex_projection`, `lex_terms`,
`lex_canonical`. **This is where retrieval quality visibly changes, with zero model dependency.**

**M4 — Connectors and conformance.** `SourceConnector` protocol, baseline connectors, conformance
reporting, `doctor` aggregation. Port the study-material profile (Appendix A) and backfill an existing
semester to read real conformance numbers.

**M5 — Fusion, expansion, primitives.** Retriever registry, RRF, ladder collapse, dedupe, diversity
caps, post-rank expansion, `link_graph`, and the full primitive set including `manifest` and
`concepts`. **At the end of M5 the offline baseline is complete and materially better than today, with
no model anywhere in the KB.**

**M6 — Incremental maintenance.** Unit-level diffing, sync state colocated with indexes, invalidation
events. Deliberately before the expensive derived layer, so that layer is affordable when it lands.

**M7 — Figures, structural half.** Figure units, content-hash identity, `exact` and `generated`
anchors, `derived` anchors from page geometry with computed confidence, duplicate merging, review
events and queue, inheritance attachment, `figures()` over caption text. *Still no models.*

**M8 — Figure derived layer.** OCR labels first (largest precision gain, offline-capable), then figure
cards, then surrogates for `essential` figures. Measure against the figure evals before and after each
addition.

**M9 — Semantic adapters.** `vec_projection`, `vec_canonical`, `vec_figure` (sqlite-vec, brute force);
then the reranker; then the `model` projector. All plug into the M5 registry with no caller changes.
Direct image embeddings only if M8 evals show a residual gap text-side signals cannot close.

M1–M6 require no model at all. M7 is structural. M8–M9 are independently droppable adapters, which is
the property that keeps the KB honest about what it does offline.

## 16. Tradeoffs and risks

- **Indexing projections rather than raw text adds a derived layer to the hot path.** Mitigated by
  making the free projectors genuinely competitive (which is why authoring guidance matters) and by
  keeping `lex_canonical` registered so raw phrasing is never unreachable.
- **The granularity ladder multiplies index rows.** Bounded by the promotion gate (§8.4) and made
  coherent by ladder collapse (§10.2). Without both, it is duplication rather than recall.
- **Unitization changes invalidate every `unit_id`.** Handled by immutable revisions plus a
  best-effort remap that reports failures. Doing it once in M2 is much cheaper than later.
- **RRF adds machinery before it adds ranking value.** Bought knowingly as an extension seam.
- **Content-hash figure identity merges visually identical figures with different intents.** Accepted:
  multiple anchors express the different placements, and merging prevents double-counting.
- **The cross-document anchoring prohibition costs recall.** Accepted deliberately (§9.8): undetectable
  wrong placement is worse than a missing figure.
- **Derived-layer cost concentrates in vision and OCR.** Mitigated by M6 landing first, by lazy
  generation prioritized by retrieval frequency, and by the KB being useful with zero derived
  artifacts.
- **Promoted study material makes model-produced text citable.** Accepted deliberately (Appendix A.4),
  mitigated by lineage, visible review status, uncertainty flags in every row, and source-class priors.
  The alternative — citing raw transcripts — is worse on every axis: noisier, less stable, less
  readable as evidence.
- **SQLite over Postgres/pgvector.** At this corpus scale FTS5 and brute-force vectors are ample, and a
  required database daemon would cost the zero-setup offline property that determines whether an OSS
  study tool gets installed at all. Revisit on measured evidence, not anticipated scale.

## 17. Open questions

1. **Substrate garbage collection.** Proposal: never automatic; an explicit operator command that
   refuses while any citation, anchor, or artifact references the substrate.
2. **Cross-edition citation migration.** Manual in v0.2. Whether a semi-automatic aligner (structural
   heading match plus human confirmation) earns its cost depends on how often editions change
   mid-course.
3. **Alias dictionaries.** Per-scope synonym lists (Latin ↔ vernacular, abbreviation expansions) are
   the cheapest paraphrase-recall mechanism available offline. Open: authored by hand, mined from the
   corpus, or seeded from an external terminology source?
4. **`essential` figure classification.** Model-derived but consequential (§9.4). Worth measuring
   whether structural signals suffice, since a wrong `decorative` call silently hides content.
5. **Personal notes and self-containment.** Notes are written for their author and will fail
   self-containment routinely. Leaning toward ingesting them as-is with weaker guarantees, since
   normalizing them would introduce derived text with no promotion event.
6. **Should `summary` fragments be marked as flashcard-preferred?** They are the natural input.
   Leaning toward exposing the fragment kind and staying silent on its use, to keep pedagogy out of
   the KB.

---

## Appendix A — Connector profile: derived study material

One connector profile, included to show how a real dialect maps onto the generic model. Nothing here
is part of the domain model; a different producer supplies a different profile and the KB is unchanged.

### A.1 Position

Lecture audio and its transcript are **canonical-but-unindexed**: stored in the blob store as lineage,
never retrievable. The retrievable artifact is the study material produced from the transcript, which
enters through the same connector path as any other document. This removes an index-time distillation
stage, a timestamp/speaker-turn segmentation fallback, and any source-class branch in the unitizer.

### A.2 Declared metadata

Front matter supplies what the connector cannot infer: course, stable lesson id (the structural key for
correspondence, per P7), title, date, instructor, language, conformance level, review status,
uncertainty marker counts (computed mechanically from the body, never asked of a model), and lineage —
transcript hash, audio hash, pipeline version, model ids, produced-at.

### A.3 Dialect mapping

| Dialect construct | Generic mapping |
|---|---|
| `H1` | document root; `document_card` unit |
| `H2` / `H3` | `section` nodes; `H3` preferred leaf |
| Instructor-emphasis callout | `emphasis` fragment |
| Recap bullet block | `summary` fragment |
| Pipe table / aggregated appendix | `table` fragment, atomic |
| Figure comment + embed | `figure_ref`, `exact` anchor |
| Chemical-structure markers | `figure_ref`, `generated` anchor |
| Inline uncertainty markers | `flags` on the containing unit |
| Colour/highlight spans | stripped for indexing, preserved in the substrate |

### A.4 Authoring requirements the profile enforces

These exist because they make the **free** projector competitive with the paid one (§7.1) — this is the
whole reason authoring-time normalization is worth constraining:

1. **Descriptive standalone headings.** Meaningful in a result list with no context; minimum three
   content words. Positional titles (`Block 7`, `Part 2`) are a violation.
2. **Self-contained sections.** Name the subject in the first sentence; no reading-order
   cross-references ("as mentioned above"). One concept per leaf.
3. **Stable authored anchors** on every section, carried forward across regenerations when the topic is
   unchanged, so rewording a heading does not orphan citations into it.
4. **Fixed island grammar** so fragments parse deterministically, with proper value escaping in figure
   comments.
5. **Never author figure metadata.** Figure identity and anchors are owned by the KB, keyed by image
   content hash. A document's figure comment is a *mirror* of the KB record, so a malformed or stale
   comment degrades that document's rendering and never the KB's figure data.

### A.5 Promotion

`study_material.promoted@1` is the explicit, loud act by which model-produced text becomes a canonical
citable source — the sole exception to the derived-layer rule. It records lineage, conformance
findings, uncertainty counts, and review status. Consequences: citations bottom out at the study
material and are byte-stable; `lineage()` walks back to transcript and audio for drill-down; review
status and uncertainty flags ride along in every evidence row, so a confirmed document and an
unreviewed one with three unverified markers never look identical to a tutor.
