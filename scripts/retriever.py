"""
Hybrid retrieval pipeline for team-insight.
Combines vector search + BM25 with RRF fusion, length normalization,
time decay, and MMR diversity filtering.

Ported from memory-plugin/src/core/retriever.ts.
"""

import math
import sys
import time
from typing import Any, Dict, List, Optional

from config import Config, RetrievalConfig
from embedder import Embedder
from store import MemoryStore
from utils import cosine_similarity


class Retriever:
    """Hybrid search retriever with configurable scoring pipeline."""

    def __init__(self, store: MemoryStore, embedder: Embedder, config: RetrievalConfig):
        self.store = store
        self.embedder = embedder
        self.config = config

    def retrieve(
        self,
        query: str,
        limit: Optional[int] = None,
        file_type: Optional[str] = None,
        author: Optional[str] = None,
    ) -> List[Dict]:
        """
        Full retrieval pipeline:
        1. Embed query
        2. Parallel vector + BM25 search
        3. RRF fusion
        4. Length normalization
        5. Time decay
        6. Hard min-score cutoff
        7. MMR diversity
        8. Return top limit results
        """
        final_limit = limit or self.config.default_limit
        candidate_pool = final_limit * 4

        # 1. Embed query
        query_vector = self.embedder.embed_query(query)

        # 2. Search
        vector_results = []
        bm25_results = []

        if self.config.mode == "hybrid":
            vector_results = self.store.vector_search(
                query_vector, candidate_pool, self.config.min_score, file_type, author
            )
            bm25_results = self.store.bm25_search(query, candidate_pool, file_type, author)
        else:
            vector_results = self.store.vector_search(
                query_vector, candidate_pool, self.config.min_score, file_type, author
            )

        # 3. RRF fusion
        fused = self._rrf_fusion(vector_results, bm25_results)

        # 4. Length normalization
        fused = self._apply_length_normalization(fused)

        # 5. Time decay
        fused = self._apply_time_decay(fused)

        # 6. Hard min-score cutoff
        fused = [r for r in fused if r.get("score", 0) >= self.config.hard_min_score]

        # Sort descending
        fused.sort(key=lambda r: r.get("score", 0), reverse=True)

        # 7. MMR diversity
        diverse = self._apply_mmr(fused, query_vector)

        # 8. Return top limit
        return diverse[:final_limit]

    def _rrf_fusion(
        self, vector_results: List[Dict], bm25_results: List[Dict]
    ) -> List[Dict]:
        """Reciprocal Rank Fusion: boost score for items found in both result sets."""
        by_id: Dict[str, Dict] = {}

        for r in vector_results:
            rid = r.get("id")
            if not rid:
                continue
            by_id[rid] = {**r, "has_vector": True, "has_bm25": False}

        for r in bm25_results:
            rid = r.get("id")
            if not rid:
                continue

            if rid in by_id:
                # Found in both → boost
                existing = by_id[rid]
                existing["has_bm25"] = True
                existing["score"] = existing["score"] + 0.15 * existing["score"]
            else:
                # BM25-only: verify it actually exists in the DB (ghost entry check)
                try:
                    exists = self.store.get_by_id(rid)
                    if not exists:
                        continue
                except Exception:
                    pass

                r["score"] = max(0.1, min(1.0, r.get("score", 0)))
                by_id[rid] = {**r, "has_vector": False, "has_bm25": True}

        return list(by_id.values())

    def _apply_length_normalization(self, results: List[Dict]) -> List[Dict]:
        """Penalize very long chunks to avoid domination by lengthy text."""
        anchor = self.config.length_norm_anchor
        for r in results:
            char_len = len(r.get("text", ""))
            ratio = max(char_len / anchor, 1.0)
            penalty = 1.0 / (1.0 + 0.5 * math.log2(ratio))
            r["score"] = r.get("score", 0) * penalty
        return results

    def _apply_time_decay(self, results: List[Dict]) -> List[Dict]:
        """Apply exponential time decay based on entry age."""
        half_life = self.config.time_decay_half_life_days
        now_ms = int(time.time() * 1000)

        for r in results:
            ts = r.get("timestamp", now_ms)
            age_days = (now_ms - ts) / (1000 * 60 * 60 * 24)
            decay = 0.5 + 0.5 * math.exp(-age_days / half_life)
            r["score"] = r.get("score", 0) * decay
        return results

    def _apply_mmr(self, results: List[Dict], query_vector: List[float]) -> List[Dict]:
        """Maximal Marginal Relevance: filter near-duplicate results."""
        if not results:
            return []

        threshold = self.config.mmr_similarity_threshold
        selected: List[Dict] = []
        selected_vectors: List[List[float]] = []

        for r in results:
            vec = r.get("vector")
            if not vec:
                selected.append(r)
                continue

            is_diverse = True
            for sv in selected_vectors:
                sim = cosine_similarity(vec, sv)
                if sim > threshold:
                    is_diverse = False
                    break

            if is_diverse:
                selected.append(r)
                selected_vectors.append(vec)

        return selected
