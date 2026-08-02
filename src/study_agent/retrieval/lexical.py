"""Provider-neutral bridge from KB-09B lexical indexes to KB-11 retrievers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from study_agent.ports.knowledge import LexicalIndexPort, LexicalQuery, LexicalSurface
from study_agent.ports.retrievers import (
    RetrieverCandidate,
    RetrieverCandidateList,
    RetrieverCost,
    RetrieverManifest,
    RetrieverNetwork,
    RetrieverPort,
    RetrieverQuery,
)

_SURFACE_NAMES: Final[dict[LexicalSurface, str]] = {
    LexicalSurface.PROJECTION: "lex_projection",
    LexicalSurface.TERMS: "lex_terms",
    LexicalSurface.CANONICAL: "lex_canonical",
}


@dataclass(frozen=True, slots=True)
class LexicalRetriever(RetrieverPort):
    """Expose one KB-09B surface without importing its storage adapter."""

    index: LexicalIndexPort
    surface: LexicalSurface

    def __post_init__(self) -> None:
        if not isinstance(self.surface, LexicalSurface):
            raise TypeError("surface must be LexicalSurface")

    @property
    def manifest(self) -> RetrieverManifest:
        name = _SURFACE_NAMES[self.surface]
        return RetrieverManifest(
            name=name,
            version="1",
            surface=name,
            cost=RetrieverCost.FREE,
            default_weight=1.0,
            network=RetrieverNetwork.NEVER,
        )

    def search(self, query: RetrieverQuery) -> RetrieverCandidateList:
        if not isinstance(query, RetrieverQuery):
            raise TypeError("query must be RetrieverQuery")
        if query.filters:
            raise ValueError("lexical retrievers do not support filters")
        manifest = self.manifest
        lexical_query = LexicalQuery(
            scope_id=query.scope_id,
            text=query.text,
            surface=self.surface,
            limit=query.limit,
        )
        result = self.index.search(lexical_query)
        if result.surface is not self.surface:
            raise ValueError("lexical index returned a different surface")
        if result.query_fingerprint != lexical_query.fingerprint:
            raise ValueError("lexical index returned a different query")
        if len(result.candidates) > query.limit:
            raise ValueError("lexical index returned too many candidates")
        candidates = tuple(
            RetrieverCandidate(
                unit_id=item.unit_id,
                projection_id=item.projection_id,
                rank=item.rank,
                score=item.score,
                query_fingerprint=query.fingerprint,
                retriever_identity=manifest.identity,
                manifest_fingerprint=manifest.fingerprint,
                surface=manifest.surface,
                index_version=result.index_version,
            )
            for item in result.candidates
        )
        return RetrieverCandidateList(
            query_fingerprint=query.fingerprint,
            retriever_identity=manifest.identity,
            manifest_fingerprint=manifest.fingerprint,
            surface=manifest.surface,
            index_version=result.index_version,
            candidates=candidates,
            limit=query.limit,
        )


__all__ = ["LexicalRetriever"]
