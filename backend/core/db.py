from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None
_vector_registered = False

EMBEDDING_DIM = 1536

_INIT_SQL = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS analyses (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    content     TEXT NOT NULL,
    message_type TEXT NOT NULL DEFAULT 'general',
    model       TEXT NOT NULL,
    alignment   REAL NOT NULL DEFAULT 0,
    divergence  REAL NOT NULL DEFAULT 0,
    persona_count INT NOT NULL DEFAULT 0,
    summary     JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    result      JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    embedding   vector({EMBEDDING_DIM})
);

CREATE INDEX IF NOT EXISTS analyses_created_idx ON analyses (created_at DESC);
CREATE INDEX IF NOT EXISTS analyses_embedding_idx ON analyses USING hnsw (embedding vector_cosine_ops);
"""


async def _get_raw_pool() -> asyncpg.Pool:
    """Get or create the connection pool WITHOUT registering pgvector codec."""
    global _pool
    if _pool is None:
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("DATABASE_URL is not set")
        _pool = await asyncpg.create_pool(
            database_url,
            min_size=1,
            max_size=5,
            statement_cache_size=0,
        )
    return _pool


async def get_pool() -> asyncpg.Pool:
    """Get the connection pool with pgvector codec registered."""
    pool = await _get_raw_pool()
    await _ensure_vector_registered(pool)
    return pool


async def _ensure_vector_registered(pool: asyncpg.Pool) -> None:
    global _vector_registered
    if _vector_registered:
        return
    from pgvector.asyncpg import register_vector
    async with pool.acquire() as conn:
        await register_vector(conn)
    _vector_registered = True


async def init_db() -> None:
    # 1. Get pool without vector codec (extension may not exist yet)
    pool = await _get_raw_pool()
    # 2. Create extension + table
    async with pool.acquire() as conn:
        await conn.execute(_INIT_SQL)
    # 3. Now that the extension exists, register the codec
    await _ensure_vector_registered(pool)
    logger.info("Database initialized (analyses table + pgvector ready)")


async def close_db() -> None:
    global _pool, _vector_registered
    if _pool is not None:
        await _pool.close()
        _pool = None
        _vector_registered = False


async def _conn_with_vector(pool: asyncpg.Pool) -> asyncpg.Connection:
    """Acquire a connection with pgvector codec registered."""
    from pgvector.asyncpg import register_vector
    conn = await pool.acquire()
    await register_vector(conn)
    return conn


async def save_analysis(
    *,
    content: str,
    message_type: str,
    model: str,
    summary: dict[str, Any],
    result: dict[str, Any],
    embedding: list[float] | None = None,
) -> str:
    """Save an analysis result and return its UUID."""
    pool = await get_pool()
    analysis_id = str(uuid.uuid4())

    alignment = float(summary.get("alignment_score", 0))
    divergence = float(summary.get("divergence_score", 0))
    persona_count = len(result.get("personas", []))

    async with pool.acquire() as conn:
        from pgvector.asyncpg import register_vector
        await register_vector(conn)
        await conn.execute(
            """
            INSERT INTO analyses (id, content, message_type, model, alignment, divergence, persona_count, summary, result, embedding)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, $10)
            """,
            uuid.UUID(analysis_id),
            content,
            message_type,
            model,
            alignment,
            divergence,
            persona_count,
            json.dumps(summary),
            json.dumps(result),
            _to_pgvector(embedding),
        )
    return analysis_id


def _to_pgvector(embedding: list[float] | None):
    if embedding is None:
        return None
    import numpy as np
    return np.array(embedding, dtype=np.float32)


async def get_analysis(analysis_id: str) -> dict[str, Any] | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, created_at, content, message_type, model, alignment, divergence, persona_count, result FROM analyses WHERE id = $1",
            uuid.UUID(analysis_id),
        )
    if row is None:
        return None
    return _row_to_dict(row)


async def list_analyses(limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, created_at, content, message_type, model, alignment, divergence, persona_count
            FROM analyses
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
    return [_row_to_history_item(r) for r in rows]


async def search_analyses(embedding: list[float], limit: int = 10) -> list[dict[str, Any]]:
    """Find the most semantically similar past analyses using pgvector cosine distance."""
    pool = await get_pool()
    import numpy as np
    vec = np.array(embedding, dtype=np.float32)

    async with pool.acquire() as conn:
        from pgvector.asyncpg import register_vector
        await register_vector(conn)
        rows = await conn.fetch(
            """
            SELECT id, created_at, content, message_type, model, alignment, divergence, persona_count,
                   1 - (embedding <=> $1) AS similarity
            FROM analyses
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1
            LIMIT $2
            """,
            vec,
            limit,
        )
    results = []
    for r in rows:
        item = _row_to_history_item(r)
        item["similarity"] = round(float(r["similarity"]), 4)
        results.append(item)
    return results


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "created_at": row["created_at"].isoformat(),
        "content": row["content"],
        "message_type": row["message_type"],
        "model": row["model"],
        "alignment": row["alignment"],
        "divergence": row["divergence"],
        "persona_count": row["persona_count"],
        "result": json.loads(row["result"]) if isinstance(row["result"], str) else row["result"],
    }


async def text_search_analyses(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Full-text search fallback using ILIKE when vector search is unavailable."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, created_at, content, message_type, model, alignment, divergence, persona_count
            FROM analyses
            WHERE content ILIKE '%' || $1 || '%'
            ORDER BY created_at DESC
            LIMIT $2
            """,
            query,
            limit,
        )
    return [_row_to_history_item(r) for r in rows]


async def delete_all_analyses() -> int:
    """Delete all analyses and return the count of deleted rows."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM analyses")
    return int(result.split()[-1])


def _row_to_history_item(row: asyncpg.Record) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "created_at": row["created_at"].isoformat(),
        "content": row["content"][:120],
        "message_type": row["message_type"],
        "model": row["model"],
        "alignment": row["alignment"],
        "divergence": row["divergence"],
        "persona_count": row["persona_count"],
    }
