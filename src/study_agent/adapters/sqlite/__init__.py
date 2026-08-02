"""SQLite persistence adapters."""

from .event_store import (
    EventBatchError,
    ProjectionConsistencyError,
    SequenceConflictError,
    SQLiteConnectionIdentityError,
    SQLiteConnectionIdentityGuard,
    SQLiteEventStore,
    UnsupportedSQLiteDatabaseError,
)
from .fts_retrieval import (
    INDEX_VERSION,
    RetrievalIndexIntegrityError,
    SQLiteFtsRetrieval,
    compile_literal_query,
    normalize_bm25_score,
)
from .lexical_surfaces import (
    LEXICAL_INDEX_VERSION,
    LEXICAL_SCHEMA_VERSION,
    LexicalIndexIntegrityError,
    SQLiteLexicalCapabilityError,
    SQLiteLexicalSurfaces,
)
from .lifecycle_observer import observe_local_repository
from .literal_query import (
    MEDICAL_TRIGRAM_QUERY_POLICY,
    UNICODE61_QUERY_POLICY,
    compile_medical_trigram_query,
)
from .namespaced_run_store import NamespacedSQLiteRunStore
from .run_store import (
    RunStoreCorruptionError,
    SQLiteRunStore,
    UnsupportedSQLiteRunDatabaseError,
)

__all__ = [
    "INDEX_VERSION",
    "LEXICAL_INDEX_VERSION",
    "LEXICAL_SCHEMA_VERSION",
    "MEDICAL_TRIGRAM_QUERY_POLICY",
    "UNICODE61_QUERY_POLICY",
    "EventBatchError",
    "LexicalIndexIntegrityError",
    "NamespacedSQLiteRunStore",
    "ProjectionConsistencyError",
    "RetrievalIndexIntegrityError",
    "RunStoreCorruptionError",
    "SQLiteConnectionIdentityError",
    "SQLiteConnectionIdentityGuard",
    "SQLiteEventStore",
    "SQLiteFtsRetrieval",
    "SQLiteLexicalCapabilityError",
    "SQLiteLexicalSurfaces",
    "SQLiteRunStore",
    "SequenceConflictError",
    "UnsupportedSQLiteDatabaseError",
    "UnsupportedSQLiteRunDatabaseError",
    "compile_literal_query",
    "compile_medical_trigram_query",
    "normalize_bm25_score",
    "observe_local_repository",
]
