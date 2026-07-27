"""Literal-only FTS5 query compilers shared by SQLite lexical adapters."""

from __future__ import annotations

import sqlite3
from contextlib import closing

from study_agent.knowledge.lexical import tokenize

UNICODE61_QUERY_POLICY = "unicode61-v1"
MEDICAL_TRIGRAM_QUERY_POLICY = "medical-trigram-v1"


def _fts_tokens(
    connection: sqlite3.Connection,
    text: str,
    *,
    table_name: str,
    tokenize_ddl: str,
) -> tuple[str, ...]:
    """Tokenize through the exact SQLite tokenizer used by an FTS surface."""

    connection.execute(
        f"CREATE VIRTUAL TABLE temp.{table_name} USING fts5(text, tokenize={tokenize_ddl})"
    )
    vocab_name = f"{table_name}_vocab"
    connection.execute(
        f"CREATE VIRTUAL TABLE temp.{vocab_name} USING fts5vocab({table_name}, 'instance')"
    )
    connection.execute(f"INSERT INTO {table_name}(text) VALUES (?)", (text,))
    rows = connection.execute(
        f"SELECT term FROM {vocab_name} ORDER BY doc, offset"
    ).fetchall()
    return tuple(str(row[0]) for row in rows)


def _quote_tokens(tokens: tuple[str, ...], *, joiner: str = " AND ") -> str | None:
    if not tokens:
        return None
    return joiner.join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)


def compile_unicode61_query(text: str) -> str | None:
    """Preserve v0.1 unicode61 literal compilation byte-for-byte."""

    with closing(sqlite3.connect(":memory:")) as connection:
        return compile_unicode61_query_on(connection, text)


def compile_unicode61_query_on(connection: sqlite3.Connection, text: str) -> str | None:
    return _quote_tokens(
        _fts_tokens(
            connection,
            text,
            table_name="retrieval_query_tokens",
            tokenize_ddl="'unicode61'",
        )
    )


def compile_medical_trigram_query(text: str) -> str | None:
    """Compile a KB-09A token stream to quoted trigram literals.

    The medical tokenizer runs before quoting, so words such as ``OR`` and
    punctuation can never become FTS operators.  The trigram tokenizer on the
    target table then provides the intentional substring semantics.
    """

    return _quote_tokens(tokenize(text))


def compile_query(
    text: str,
    policy: str,
    *,
    connection: sqlite3.Connection | None = None,
) -> str | None:
    """Dispatch a versioned policy while keeping the v0.1 owner explicit."""

    if policy == UNICODE61_QUERY_POLICY:
        if connection is None:
            return compile_unicode61_query(text)
        return compile_unicode61_query_on(connection, text)
    if policy == MEDICAL_TRIGRAM_QUERY_POLICY:
        return compile_medical_trigram_query(text)
    raise ValueError(f"unsupported literal query policy: {policy}")


__all__ = [
    "MEDICAL_TRIGRAM_QUERY_POLICY",
    "UNICODE61_QUERY_POLICY",
    "compile_medical_trigram_query",
    "compile_query",
    "compile_unicode61_query",
    "compile_unicode61_query_on",
]
