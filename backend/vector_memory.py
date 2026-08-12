"""Vector memory adapters for semantic memory.

The local backend keeps the project runnable without external services. The
Postgres adapter is production-oriented: it uses pgvector when configured and
stores tenant/user metadata to keep memories isolated.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Protocol


_TOKEN_RE = re.compile(r"[\w\u0600-\u06ff]+", re.UNICODE)


def _embedding(text: str, dimensions: int = 64) -> list[float]:
    """Deterministic hashed bag-of-words embedding for local tests and fallback.

    Replace this function with an embedding API/model in production. The adapter
    interface stays the same, so the database layer does not need to change.
    """
    vector = [0.0] * dimensions
    for token in _TOKEN_RE.findall(text.casefold()):
        index = hash(token) % dimensions
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


class VectorMemoryBackend(Protocol):
    name: str

    def upsert(self, *, memory_id: str, content: str, user_id: str, metadata: dict[str, Any]) -> None: ...

    def search(self, *, query: str, user_id: str, limit: int) -> list[str]: ...


@dataclass
class _LocalVectorRecord:
    memory_id: str
    content: str
    user_id: str
    metadata: dict[str, Any]
    vector: list[float]


class LocalVectorBackend:
    """Dependency-free vector backend used by tests and local development."""

    name = "local-hashed-vector"

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions
        self._records: dict[str, _LocalVectorRecord] = {}

    def upsert(self, *, memory_id: str, content: str, user_id: str, metadata: dict[str, Any]) -> None:
        self._records[memory_id] = _LocalVectorRecord(
            memory_id=memory_id,
            content=content,
            user_id=user_id,
            metadata=dict(metadata),
            vector=_embedding(content, self.dimensions),
        )

    def search(self, *, query: str, user_id: str, limit: int) -> list[str]:
        query_vector = _embedding(query, self.dimensions)
        candidates = [record for record in self._records.values() if record.user_id == user_id]
        candidates.sort(key=lambda record: _cosine(query_vector, record.vector), reverse=True)
        return [record.memory_id for record in candidates[:limit]]


class PostgresVectorBackend:
    """PostgreSQL + pgvector adapter.

    Required production setup:
      1. Install ``psycopg[binary]`` and enable the pgvector extension.
      2. Set ``DATABASE_URL``.
      3. Call ``ensure_schema()`` once during deployment.

    The embedding function is intentionally injected so a hosted embedding model
    can be selected without coupling the memory layer to one vendor.
    """

    name = "postgres-pgvector"

    def __init__(self, dsn: str, dimensions: int = 64, embedding_fn=_embedding) -> None:
        self.dsn = dsn
        self.dimensions = dimensions
        self.embedding_fn = embedding_fn
        try:
            import psycopg  # type: ignore
        except ImportError as exc:  # pragma: no cover - only used in deployments
            raise RuntimeError("Install psycopg[binary] to use PostgresVectorBackend") from exc
        self._psycopg = psycopg

    def _connect(self):
        return self._psycopg.connect(self.dsn)

    def ensure_schema(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS omni_semantic_memory (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        content TEXT NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        embedding vector({self.dimensions}) NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS omni_semantic_memory_user_idx "
                    "ON omni_semantic_memory(user_id)"
                )
            connection.commit()

    def upsert(self, *, memory_id: str, content: str, user_id: str, metadata: dict[str, Any]) -> None:
        vector = self.embedding_fn(content, self.dimensions)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO omni_semantic_memory (id, user_id, content, metadata, embedding)
                    VALUES (%s, %s, %s, %s::jsonb, %s::vector)
                    ON CONFLICT (id) DO UPDATE SET
                        content = EXCLUDED.content,
                        metadata = EXCLUDED.metadata,
                        embedding = EXCLUDED.embedding
                    """,
                    (memory_id, user_id, content, _json(metadata), str(vector)),
                )
            connection.commit()

    def search(self, *, query: str, user_id: str, limit: int) -> list[str]:
        vector = self.embedding_fn(query, self.dimensions)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id FROM omni_semantic_memory
                    WHERE user_id = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (user_id, str(vector), limit),
                )
                return [row[0] for row in cursor.fetchall()]


def _json(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)
