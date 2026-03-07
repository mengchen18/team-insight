"""
Shared utility functions for team-insight.
"""

import hashlib
import math
import os
from typing import List, Optional


def compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file's contents."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_row_id(file_path: str, chunk_id: str) -> str:
    """Compute deterministic row ID from file_path + chunk_id."""
    return hashlib.sha256(f"{file_path}::{chunk_id}".encode()).hexdigest()


def compute_chunk_hash(text: str) -> str:
    """Compute SHA-256 hash for chunk content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or len(a) == 0:
        return 0.0

    dot = sum(ai * bi for ai, bi in zip(a, b))
    norm_a = math.sqrt(sum(ai * ai for ai in a))
    norm_b = math.sqrt(sum(bi * bi for bi in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Smart chunking (for embedding context-length fallback)
# ---------------------------------------------------------------------------

EMBEDDING_CONTEXT_LIMITS = {
    "text-embedding-3-small": 8192,
    "text-embedding-3-large": 8192,
    "text-embedding-004": 8192,
    "gemini-embedding-001": 2048,
    "nomic-embed-text": 8192,
    "embed-english-v3.0": 512,
    "embed-multilingual-v3.0": 512,
    "voyage-3": 32000,
    "voyage-3-lite": 32000,
}


def smart_chunk(text: str, model: Optional[str] = None) -> List[str]:
    """
    Split text into chunks adapted to model context limits.
    Uses conservative char limits (70% of reported limit).
    """
    if model:
        # Try exact match first, then strip provider prefix (e.g. "openai/text-embedding-3-small")
        limit = EMBEDDING_CONTEXT_LIMITS.get(model)
        if limit is None:
            bare_model = model.rsplit("/", 1)[-1] if "/" in model else model
            limit = EMBEDDING_CONTEXT_LIMITS.get(bare_model, 8192)
    else:
        limit = 8192
    max_chunk = max(1000, int(limit * 0.7))
    overlap = max(0, int(limit * 0.05))
    min_chunk = max(100, int(limit * 0.1))

    if not text or not text.strip():
        return []

    if len(text) <= max_chunk:
        return [text.strip()]

    chunks = []
    pos = 0
    max_guard = max(4, len(text) // max(1, max_chunk - overlap) + 5)
    guard = 0

    while pos < len(text) and guard < max_guard:
        guard += 1
        remaining = len(text) - pos

        if remaining <= max_chunk:
            chunk = text[pos:].strip()
            if chunk:
                chunks.append(chunk)
            break

        end = min(pos + max_chunk, len(text))

        # Try to split on sentence boundary
        split_pos = end
        for i in range(end - 1, max(pos + min_chunk, pos) - 1, -1):
            if text[i] in ".!?":
                split_pos = i + 1
                break
        else:
            # Try newline
            for i in range(end - 1, max(pos + min_chunk, pos) - 1, -1):
                if text[i] == "\n":
                    split_pos = i + 1
                    break

        chunk = text[pos:split_pos].strip()
        if chunk:
            chunks.append(chunk)

        if split_pos >= len(text):
            break

        pos = max(split_pos - overlap, pos + 1)

    return chunks
