"""
LanceDB storage layer with file-locking for multi-user safety.
Ported from memory-plugin/src/core/store.ts.
"""

import fcntl
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Set

import lancedb

from config import LanceDBConfig
from utils import compute_file_hash, compute_row_id


def _escape(val: str) -> str:
    """Escape single quotes for LanceDB SQL-like filter expressions."""
    return val.replace("'", "''")


class FileLock:
    """Simple file-based lock using fcntl.flock() for multi-user safety."""

    def __init__(self, lock_path: str):
        self.lock_path = lock_path
        self._fd = None

    def acquire(self):
        os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)
        fd = open(self.lock_path, "w")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("[Store] Database is locked by another process. Waiting...", file=sys.stderr)
            fcntl.flock(fd, fcntl.LOCK_EX)  # blocking wait
        except Exception:
            fd.close()
            raise
        self._fd = fd
        self._fd.write(str(os.getpid()))
        self._fd.flush()

    def release(self):
        if self._fd:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            self._fd.close()
            self._fd = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()


class MemoryStore:
    """LanceDB-backed memory store with hybrid search support."""

    def __init__(self, config: LanceDBConfig):
        self.db_path = config.path
        self.table_name = config.table_name
        self._lock = FileLock(os.path.join(self.db_path, ".lock"))
        self._db = None
        self._table = None

    def _connect(self):
        """Establish connection to LanceDB."""
        os.makedirs(self.db_path, exist_ok=True)
        self._db = lancedb.connect(self.db_path)

    def _get_table(self):
        """Get or open the memories table."""
        if self._db is None:
            self._connect()

        names = self._db.table_names()
        if self.table_name not in names:
            raise RuntimeError(
                f"Table '{self.table_name}' does not exist. Run ingest first."
            )

        self._table = self._db.open_table(self.table_name)
        return self._table

    # -------------------------------------------------------------------------
    # Write operations (require file lock)
    # -------------------------------------------------------------------------

    def upsert_chunks(self, rows: List[Dict[str, Any]]):
        """Insert rows into the table. Creates the table if it doesn't exist."""
        if not rows:
            return

        with self._lock:
            if self._db is None:
                self._connect()

            names = self._db.table_names()
            if self.table_name not in names:
                self._db.create_table(self.table_name, rows)
            else:
                table = self._db.open_table(self.table_name)
                table.add(rows)

    def delete_by_file_path(self, file_path: str):
        """Delete all rows matching a file_path."""
        with self._lock:
            try:
                table = self._get_table()
                table.delete(f"file_path = '{_escape(file_path)}'")
            except Exception:
                pass

    def create_fts_index(self):
        """Create full-text search index on the 'text' column."""
        with self._lock:
            try:
                table = self._get_table()
                table.create_fts_index("text", replace=True)
                print("[Store] FTS index created on 'text' column", file=sys.stderr)
            except Exception as e:
                print(f"[Store] Could not create FTS index: {e}", file=sys.stderr)

    # -------------------------------------------------------------------------
    # Read operations (no lock needed)
    # -------------------------------------------------------------------------

    def get_existing_hash(self, file_path: str) -> Optional[str]:
        """Get the source_hash for a file_path, or None if not found."""
        try:
            table = self._get_table()
            results = (
                table.search()
                .where(f"file_path = '{_escape(file_path)}'", prefilter=True)
                .limit(1)
                .to_list()
            )
            if results:
                return results[0].get("source_hash")
            return None
        except Exception:
            return None

    def get_chunk_hashes(self, file_path: str) -> Dict[str, str]:
        """Get a mapping of chunk_id -> chunk_hash for a specific file."""
        try:
            table = self._get_table()
            results = (
                table.search()
                .where(f"file_path = '{_escape(file_path)}'", prefilter=True)
                .select(["chunk_id", "metadata"])
                .limit(100000)
                .to_list()
            )

            chunk_hashes = {}
            for r in results:
                try:
                    meta = json.loads(r.get("metadata", "{}"))
                    chunk_hash = meta.get("chunk_hash")
                    if chunk_hash:
                        chunk_hashes[r["chunk_id"]] = chunk_hash
                except Exception:
                    pass
            return chunk_hashes
        except Exception:
            return {}

    def delete_chunks(self, row_ids: List[str]):
        """Delete specific chunks by their row IDs."""
        if not row_ids:
            return
        
        with self._lock:
            try:
                table = self._get_table()
                # LanceDB supports IN clauses for deletion in recent versions
                # Filter by exact match if only 1, otherwise use IN
                if len(row_ids) == 1:
                    table.delete(f"id = '{_escape(row_ids[0])}'")
                else:
                    id_list = ", ".join(f"'{_escape(rid)}'" for rid in row_ids)
                    table.delete(f"id IN ({id_list})")
            except Exception as e:
                print(f"[Store] Error deleting chunks: {e}", file=sys.stderr)

    def needs_update(self, file_path: str, current_hash: str) -> bool:
        """Check if a file needs re-embedding based on hash comparison."""
        existing = self.get_existing_hash(file_path)
        return existing != current_hash

    def get_all_file_paths(self) -> Set[str]:
        """Get all unique file_paths in the database."""
        try:
            table = self._get_table()
            results = table.search().select(["file_path"]).limit(100000).to_list()
            return {r["file_path"] for r in results}
        except Exception:
            return set()

    def get_by_id(self, row_id: str) -> Optional[Dict]:
        """Get a single row by ID."""
        try:
            table = self._get_table()
            results = (
                table.search()
                .where(f"id = '{_escape(row_id)}'", prefilter=True)
                .limit(1)
                .to_list()
            )
            return results[0] if results else None
        except Exception:
            return None

    def vector_search(
        self,
        query_vector: List[float],
        limit: int = 5,
        min_score: float = 0.3,
        file_type: Optional[str] = None,
        author: Optional[str] = None,
    ) -> List[Dict]:
        """
        Vector similarity search.
        Returns results with a 'score' field converted from cosine distance.
        """
        try:
            table = self._get_table()
            query = table.search(query_vector).limit(limit)

            filters = []
            if file_type:
                filters.append(f"file_type = '{_escape(file_type)}'")
            if author:
                filters.append(f"author = '{_escape(author)}'")
            if filters:
                query = query.where(" AND ".join(filters))

            results = query.to_list()

            scored = []
            for r in results:
                # _distance is cosine distance in [0, 2] for normalized vectors;
                # convert to similarity score in [0, 1]
                dist = r.get("_distance", 0) or 0
                score = max(0.0, 1.0 - dist / 2.0)
                if score >= min_score:
                    r["score"] = score
                    scored.append(r)

            return scored
        except Exception as e:
            print(f"[Store] Vector search failed: {e}", file=sys.stderr)
            return []

    def bm25_search(
        self,
        query_text: str,
        limit: int = 5,
        file_type: Optional[str] = None,
        author: Optional[str] = None,
    ) -> List[Dict]:
        """
        Full-text (BM25) search on the 'text' column.
        Requires FTS index to have been created.
        """
        try:
            table = self._get_table()
            query = table.search(query_text, query_type="fts").limit(limit)

            filters = []
            if file_type:
                filters.append(f"file_type = '{_escape(file_type)}'")
            if author:
                filters.append(f"author = '{_escape(author)}'")
            if filters:
                query = query.where(" AND ".join(filters))

            results = query.to_list()

            # Normalize BM25 scores to [0, 1] range relative to batch max
            for r in results:
                r["_raw_bm25"] = r.get("score", r.get("_score", 0))
            max_bm25 = max((r["_raw_bm25"] for r in results), default=1.0) or 1.0
            for r in results:
                r["score"] = r["_raw_bm25"] / max_bm25

            return results
        except Exception as e:
            print(
                f"[Store] BM25 search failed (needs FTS index): {e}", file=sys.stderr
            )
            return []

    @staticmethod
    def compute_file_hash(file_path: str) -> str:
        return compute_file_hash(file_path)

    @staticmethod
    def compute_row_id(file_path: str, chunk_id: str) -> str:
        return compute_row_id(file_path, chunk_id)

    @staticmethod
    def compute_chunk_hash(text: str) -> str:
        from utils import compute_chunk_hash as _util_hash
        return _util_hash(text)
