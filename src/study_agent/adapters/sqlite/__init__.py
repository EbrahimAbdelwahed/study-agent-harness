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
from .lifecycle_observer import observe_local_repository
from .run_store import (
    RunStoreCorruptionError,
    SQLiteRunStore,
    UnsupportedSQLiteRunDatabaseError,
)

__all__ = [
    "INDEX_VERSION",
    "EventBatchError",
    "ProjectionConsistencyError",
    "RetrievalIndexIntegrityError",
    "RunStoreCorruptionError",
    "SQLiteConnectionIdentityError",
    "SQLiteConnectionIdentityGuard",
    "SQLiteEventStore",
    "SQLiteFtsRetrieval",
    "SQLiteRunStore",
    "SequenceConflictError",
    "UnsupportedSQLiteDatabaseError",
    "UnsupportedSQLiteRunDatabaseError",
    "compile_literal_query",
    "normalize_bm25_score",
    "observe_local_repository",
]
