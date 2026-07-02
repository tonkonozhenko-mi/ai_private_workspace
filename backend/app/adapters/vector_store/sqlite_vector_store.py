from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from math import sqrt
from pathlib import Path
from typing import Any

from app.adapters.memory.sqlite_connection import open_sqlite
from app.core.domain.indexing import ContextSearchResult, TextChunk
from app.core.ports.vector_store import VectorStoreCorruptError

# Substrings SQLite uses when the database file itself is damaged (vs. a normal
# operational error like a missing table). We only translate these to a
# "rebuild the index" signal — everything else propagates unchanged.
_CORRUPTION_MARKERS = (
    "malformed",
    "not a database",
    "disk image",
    "file is encrypted",
    "database corruption",
)


def _raise_if_corrupt(error: sqlite3.DatabaseError) -> None:
    """Re-raise a damaged-index error as the typed ``VectorStoreCorruptError``.

    Returns without raising when the error is not corruption, so the caller can
    ``raise`` the original.
    """
    message = str(error).lower()
    if any(marker in message for marker in _CORRUPTION_MARKERS):
        raise VectorStoreCorruptError(str(error)) from error


class SQLiteVectorStore:
    """Small app-owned persistent vector store for packaged/local RAG smoke.

    This is intentionally simple: embeddings are persisted as JSON in SQLite so
    the packaged .app can retrieve chunks after backend restart without requiring
    a separate Qdrant runtime. Qdrant remains available as the advanced provider.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path).expanduser()
        # Hybrid search needs an FTS5 keyword index alongside the vectors. FTS5 is
        # compiled into most SQLite builds, but if it isn't we silently fall back
        # to vector-only search so indexing/search never break.
        self._fts_enabled = False
        self._initialize_schema()

    def upsert_chunks(
        self,
        workspace_id: str,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        embedding_dimension: int | None = None,
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        if not chunks:
            return

        now = datetime.now(UTC).isoformat()
        rows = [
            (
                workspace_id,
                chunk.id,
                chunk.source_path,
                chunk.chunk_index,
                chunk.content,
                chunk.token_estimate,
                json.dumps(chunk.metadata, sort_keys=True),
                json.dumps([float(value) for value in embedding]),
                embedding_provider or "",
                embedding_model or "",
                embedding_dimension or len(embedding),
                now,
                now,
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO workspace_vector_chunks (
                    workspace_id, chunk_id, source_path, chunk_index, content,
                    token_estimate, metadata_json, embedding_json,
                    embedding_provider, embedding_model, embedding_dimension,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id, chunk_id) DO UPDATE SET
                    source_path = excluded.source_path,
                    chunk_index = excluded.chunk_index,
                    content = excluded.content,
                    token_estimate = excluded.token_estimate,
                    metadata_json = excluded.metadata_json,
                    embedding_json = excluded.embedding_json,
                    embedding_provider = excluded.embedding_provider,
                    embedding_model = excluded.embedding_model,
                    embedding_dimension = excluded.embedding_dimension,
                    updated_at = excluded.updated_at
                """,
                rows,
            )
            if self._fts_enabled:
                # Re-index these chunks in the keyword table. FTS5 has no upsert,
                # so delete-then-insert. We index "<source_path>\n<content>" so
                # both the file path and the text are keyword-searchable.
                connection.executemany(
                    "DELETE FROM workspace_vector_chunks_fts "
                    "WHERE workspace_id = ? AND chunk_id = ?",
                    [(workspace_id, chunk.id) for chunk in chunks],
                )
                connection.executemany(
                    "INSERT INTO workspace_vector_chunks_fts "
                    "(search_text, chunk_id, workspace_id) VALUES (?, ?, ?)",
                    [
                        (f"{chunk.source_path}\n{chunk.content}", chunk.id, workspace_id)
                        for chunk in chunks
                    ],
                )

    def search(
        self,
        workspace_id: str,
        query_embedding: list[float],
        limit: int,
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        embedding_dimension: int | None = None,
        query_text: str | None = None,
    ) -> list[ContextSearchResult]:
        """Hybrid retrieval: dense (cosine) + sparse (BM25) fused with Reciprocal
        Rank Fusion.

        Pure vector search misses exact identifiers (folder/var/resource names);
        BM25 catches them. RRF merges the two rankings without needing to
        normalize their very different score scales. When ``query_text`` is absent
        or FTS5 is unavailable, this degrades to the original vector-only ranking.
        """
        if limit <= 0:
            return []

        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT chunk_id, source_path, content, metadata_json, embedding_json
                    FROM workspace_vector_chunks
                    WHERE workspace_id = ?
                      AND (? = '' OR embedding_provider = ?)
                      AND (? = '' OR embedding_model = ?)
                      AND (? IS NULL OR embedding_dimension = ?)
                    """,
                    (
                        workspace_id,
                        embedding_provider or "",
                        embedding_provider or "",
                        embedding_model or "",
                        embedding_model or "",
                        embedding_dimension,
                        embedding_dimension,
                    ),
                ).fetchall()

                # Dense ranking: cosine similarity over every candidate chunk.
                scored: list[tuple[float, sqlite3.Row]] = []
                for row in rows:
                    embedding = self._loads_embedding(row["embedding_json"])
                    scored.append((self._cosine_similarity(query_embedding, embedding), row))
                scored.sort(key=lambda item: item[0], reverse=True)

                # How wide to fuse: a generous window so BM25-only hits can surface.
                fusion_cap = max(limit * 5, 50)
                cosine_by_id = {row["chunk_id"]: (score, row) for score, row in scored}
                vector_ids = [row["chunk_id"] for _, row in scored[:fusion_cap]]

                # Sparse ranking: BM25 keyword search over path + content.
                bm25_ids = self._bm25_ids(connection, workspace_id, query_text, fusion_cap)
        except sqlite3.DatabaseError as error:
            _raise_if_corrupt(error)
            raise

        # --- Reciprocal Rank Fusion across three signals --------------------
        # 1) dense vectors, 2) BM25 keywords, 3) a path/env boost: chunks whose
        # FILE PATH contains query tokens (folder/env/component names like "dev"
        # or "<project name>") are lifted, which sharpens environment-specific questions
        # ("...in dev") where the right file lives under that path. With no BM25
        # or path hits this reproduces the plain vector order.
        k = 60
        rrf: dict[str, float] = {}
        for rank, chunk_id in enumerate(vector_ids):
            rrf[chunk_id] = rrf.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
        for rank, chunk_id in enumerate(bm25_ids):
            rrf[chunk_id] = rrf.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
        for rank, chunk_id in enumerate(
            self._path_ranked_ids(query_text, cosine_by_id, fusion_cap)
        ):
            rrf[chunk_id] = rrf.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)

        ranked_ids = sorted(rrf, key=lambda cid: rrf[cid], reverse=True)
        chosen = self._diversify(ranked_ids, cosine_by_id, limit)

        results: list[ContextSearchResult] = []
        for chunk_id in chosen:
            score, row = cosine_by_id[chunk_id]
            metadata = self._loads_metadata(row["metadata_json"])
            # Carry the chunk's embedding so downstream MMR diversification can
            # reuse it without re-embedding. Internal only — never serialized to
            # the client (the API exposes RagSource, not this metadata).
            metadata["_embedding"] = self._loads_embedding(row["embedding_json"])
            results.append(
                ContextSearchResult(
                    chunk_id=row["chunk_id"],
                    source_path=row["source_path"],
                    # Display the cosine similarity as the match score so the
                    # UI's relevance bar stays meaningful.
                    score=score,
                    content=row["content"],
                    metadata=metadata,
                )
            )
        return results

    @staticmethod
    def _path_ranked_ids(
        query_text: str | None,
        cosine_by_id: dict[str, tuple[float, sqlite3.Row]],
        limit: int,
    ) -> list[str]:
        """Rank candidates by how many query tokens match a path *segment*.

        Segment matching (split on /._-) is exact, so "dev" matches the folder
        ``dev`` but not the ``dev`` inside ``developer`` — avoiding false boosts.
        """
        tokens = SQLiteVectorStore._query_tokens(query_text)
        if not tokens:
            return []
        scored: list[tuple[int, str]] = []
        for chunk_id, (_, row) in cosine_by_id.items():
            segments = set(re.split(r"[/\\._\-]+", row["source_path"].lower()))
            hits = sum(1 for token in tokens if token in segments)
            if hits:
                scored.append((hits, chunk_id))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk_id for _, chunk_id in scored[:limit]]

    @staticmethod
    def _diversify(
        ranked_ids: list[str],
        cosine_by_id: dict[str, tuple[float, sqlite3.Row]],
        limit: int,
    ) -> list[str]:
        """Cap chunks per file so results span more files (don't let one big file
        fill the whole answer). Tops up ignoring the cap if it leaves us short,
        so we never return fewer chunks than are available."""
        max_per_file = max(2, limit // 2 + 1)
        per_file: dict[str, int] = {}
        chosen: list[str] = []
        chosen_set: set[str] = set()
        for chunk_id in ranked_ids:
            entry = cosine_by_id.get(chunk_id)
            if entry is None:
                continue
            path = entry[1]["source_path"]
            if per_file.get(path, 0) >= max_per_file:
                continue
            per_file[path] = per_file.get(path, 0) + 1
            chosen.append(chunk_id)
            chosen_set.add(chunk_id)
            if len(chosen) >= limit:
                return chosen
        for chunk_id in ranked_ids:
            if chunk_id in chosen_set or cosine_by_id.get(chunk_id) is None:
                continue
            chosen.append(chunk_id)
            if len(chosen) >= limit:
                break
        return chosen

    def _bm25_ids(
        self,
        connection: sqlite3.Connection,
        workspace_id: str,
        query_text: str | None,
        limit: int,
    ) -> list[str]:
        if not self._fts_enabled:
            return []
        match_query = self._fts_match_query(query_text)
        if not match_query:
            return []
        try:
            rows = connection.execute(
                """
                SELECT chunk_id
                FROM workspace_vector_chunks_fts
                WHERE workspace_id = ?
                  AND workspace_vector_chunks_fts MATCH ?
                ORDER BY bm25(workspace_vector_chunks_fts)
                LIMIT ?
                """,
                (workspace_id, match_query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [row["chunk_id"] for row in rows]

    @staticmethod
    def _query_tokens(query_text: str | None) -> list[str]:
        """Alphanumeric/underscore tokens from a query, lowercased, 1-char noise
        dropped and capped — shared by the BM25 query and the path boost."""
        if not query_text:
            return []
        tokens = re.findall(r"[A-Za-z0-9_]+", query_text.lower())
        return [token for token in tokens if len(token) > 1][:32]

    @staticmethod
    def _fts_match_query(query_text: str | None) -> str:
        """Turn a raw question into a safe FTS5 OR-query: tokens OR-ed (for
        recall) and quoted so user punctuation can't break FTS5 MATCH syntax."""
        tokens = SQLiteVectorStore._query_tokens(query_text)
        if not tokens:
            return ""
        return " OR ".join(f'"{token}"' for token in tokens)

    def clear_workspace(
        self,
        workspace_id: str,
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        embedding_dimension: int | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM workspace_vector_chunks WHERE workspace_id = ?",
                (workspace_id,),
            )
            if self._fts_enabled:
                connection.execute(
                    "DELETE FROM workspace_vector_chunks_fts WHERE workspace_id = ?",
                    (workspace_id,),
                )

    def delete_chunks_by_source_path(self, workspace_id: str, source_paths: list[str]) -> None:
        paths = [p for p in dict.fromkeys(source_paths) if p]
        if not paths:
            return
        placeholders = ",".join("?" for _ in paths)
        with self._connect() as connection:
            if self._fts_enabled:
                # The FTS mirror is keyed by chunk_id, so resolve the affected ids
                # first, then delete from both tables.
                rows = connection.execute(
                    f"SELECT chunk_id FROM workspace_vector_chunks "
                    f"WHERE workspace_id = ? AND source_path IN ({placeholders})",
                    (workspace_id, *paths),
                ).fetchall()
                chunk_ids = [row["chunk_id"] for row in rows]
                for chunk_id in chunk_ids:
                    connection.execute(
                        "DELETE FROM workspace_vector_chunks_fts "
                        "WHERE workspace_id = ? AND chunk_id = ?",
                        (workspace_id, chunk_id),
                    )
            connection.execute(
                f"DELETE FROM workspace_vector_chunks "
                f"WHERE workspace_id = ? AND source_path IN ({placeholders})",
                (workspace_id, *paths),
            )

    def _initialize_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workspace_vector_chunks (
                    workspace_id TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    token_estimate INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    embedding_provider TEXT NOT NULL,
                    embedding_model TEXT NOT NULL,
                    embedding_dimension INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (workspace_id, chunk_id)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_workspace_vector_chunks_workspace
                ON workspace_vector_chunks(workspace_id)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_workspace_vector_chunks_embedding
                ON workspace_vector_chunks(workspace_id, embedding_provider, embedding_model, embedding_dimension)
                """
            )
            # Keyword (BM25) index for hybrid search. We index the source_path
            # together with the chunk text so folder/file names (e.g. "dev",
            # "<project name>") are matchable lexically — exactly what pure vector search
            # misses. Guarded: if FTS5 is unavailable we stay vector-only.
            try:
                connection.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS workspace_vector_chunks_fts
                    USING fts5(
                        search_text,
                        chunk_id UNINDEXED,
                        workspace_id UNINDEXED,
                        tokenize = 'unicode61'
                    )
                    """
                )
                self._fts_enabled = True
            except sqlite3.OperationalError:
                self._fts_enabled = False

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = open_sqlite(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _loads_embedding(value: str) -> list[float]:
        loaded = json.loads(value)
        if not isinstance(loaded, list):
            return []
        return [float(item) for item in loaded]

    @staticmethod
    def _loads_metadata(value: str) -> dict[str, str]:
        loaded: Any = json.loads(value)
        if not isinstance(loaded, dict):
            return {}
        return {str(key): str(item) for key, item in loaded.items()}

    @staticmethod
    def _cosine_similarity(first: list[float], second: list[float]) -> float:
        if not first or not second:
            return 0.0
        dimensions = min(len(first), len(second))
        dot_product = sum(first[index] * second[index] for index in range(dimensions))
        first_norm = sqrt(sum(value * value for value in first))
        second_norm = sqrt(sum(value * value for value in second))
        if first_norm == 0.0 or second_norm == 0.0:
            return 0.0
        return dot_product / (first_norm * second_norm)
