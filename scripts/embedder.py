"""
Multi-provider embedding layer for team-insight.

Supports: openai, gemini, cohere, voyage, openai-compatible.
Dispatches based on setting.json -> embedding.provider.
"""

import time
import sys
from typing import List, Optional

from config import EmbeddingConfig
from utils import smart_chunk


class Embedder:
    """
    Unified embedding interface across multiple providers.
    All providers expose the same API: embed_texts() and embed_query().
    """

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.provider = config.provider
        self.model = config.model
        self.dimensions = config.dimensions
        self.batch_size = config.batch_size
        self._key_index = 0

        if not config.api_keys:
            raise ValueError(
                "No API keys configured. Set the appropriate environment variable "
                "(e.g. EMBEDDING_API_KEY) "
                "or configure api_keys in setting.json."
            )

    def _rotate_key(self):
        """Rotate to next key on rate limit."""
        if len(self.config.api_keys) > 1:
            self._key_index = (self._key_index + 1) % len(self.config.api_keys)
            print(f"[Embedder] Rate limited. Rotating to key index {self._key_index}", file=sys.stderr)

    # -------------------------------------------------------------------------
    # Provider-specific embedding
    # -------------------------------------------------------------------------

    def _embed_openai(self, texts: List[str], api_key: str) -> List[List[float]]:
        """Embed using OpenAI or OpenAI-compatible API."""
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=self.config.base_url)
        response = client.embeddings.create(
            input=texts,
            model=self.model,
            dimensions=self.dimensions,
        )
        sorted_data = sorted(response.data, key=lambda d: d.index)
        return [d.embedding for d in sorted_data]

    def _embed_gemini(self, texts: List[str], api_key: str) -> List[List[float]]:
        """Embed using Google Generative AI (google-genai)."""
        from google import genai

        client = genai.Client(api_key=api_key)
        result = client.models.embed_content(
            model=self.model,
            contents=texts,
        )
        return [e.values for e in result.embeddings]

    def _embed_cohere(self, texts: List[str], api_key: str) -> List[List[float]]:
        """Embed using Cohere."""
        import cohere

        client = cohere.Client(api_key=api_key)
        response = client.embed(
            texts=texts,
            model=self.model,
            input_type="search_document",
        )
        return [list(e) for e in response.embeddings]

    def _embed_cohere_query(self, texts: List[str], api_key: str) -> List[List[float]]:
        """Embed using Cohere with query input type."""
        import cohere

        client = cohere.Client(api_key=api_key)
        response = client.embed(
            texts=texts,
            model=self.model,
            input_type="search_query",
        )
        return [list(e) for e in response.embeddings]

    def _embed_voyage(self, texts: List[str], api_key: str) -> List[List[float]]:
        """Embed using Voyage AI."""
        import voyageai

        client = voyageai.Client(api_key=api_key)
        result = client.embed(
            texts=texts,
            model=self.model,
            input_type="document",
        )
        return result.embeddings

    def _embed_voyage_query(self, texts: List[str], api_key: str) -> List[List[float]]:
        """Embed using Voyage AI with query input type."""
        import voyageai

        client = voyageai.Client(api_key=api_key)
        result = client.embed(
            texts=texts,
            model=self.model,
            input_type="query",
        )
        return result.embeddings

    # -------------------------------------------------------------------------
    # Core embedding logic
    # -------------------------------------------------------------------------

    def _embed_batch_with_retry(
        self, texts: List[str], is_query: bool = False, max_retries: int = 3,
        _allow_auto_chunk: bool = True,
    ) -> List[List[float]]:
        """Embed a batch with retry and key rotation on rate limit."""
        for attempt in range(max_retries):
            api_key = self.config.api_keys[self._key_index]
            try:
                if self.provider in ("openai", "openai-compatible"):
                    return self._embed_openai(texts, api_key)
                elif self.provider == "gemini":
                    return self._embed_gemini(texts, api_key)
                elif self.provider == "cohere":
                    if is_query:
                        return self._embed_cohere_query(texts, api_key)
                    return self._embed_cohere(texts, api_key)
                elif self.provider == "voyage":
                    if is_query:
                        return self._embed_voyage_query(texts, api_key)
                    return self._embed_voyage(texts, api_key)
                else:
                    raise ValueError(f"Unknown embedding provider: {self.provider}")

            except Exception as e:
                err_str = str(e).lower()
                status = getattr(e, "status_code", None) or getattr(e, "status", None)

                # Rate limit
                if status == 429 or "rate" in err_str or "quota" in err_str:
                    print(f"[Embedder] Rate limit hit (attempt {attempt + 1})", file=sys.stderr)
                    self._rotate_key()
                    time.sleep(2 * (attempt + 1))
                    continue

                # Context length exceeded -> auto-chunk fallback (only once)
                if _allow_auto_chunk and "context" in err_str and ("length" in err_str or "limit" in err_str or "too long" in err_str):
                    print("[Embedder] Context length exceeded, falling back to auto-chunking...", file=sys.stderr)
                    return self._auto_chunk_embed(texts, is_query)

                raise

        raise RuntimeError("Max retries exceeded for embedding")

    def _auto_chunk_embed(self, texts: List[str], is_query: bool = False) -> List[List[float]]:
        """Split oversized texts into chunks, embed each, average the vectors."""
        results = []
        for text in texts:
            chunks = smart_chunk(text, self.model)
            if not chunks:
                raise ValueError("Failed to chunk document")

            print(f"[Embedder] Split document into {len(chunks)} semantic chunks", file=sys.stderr)
            part_vectors = self._embed_batch_with_retry(
                chunks, is_query, max_retries=1, _allow_auto_chunk=False,
            )

            # Average the vectors
            dims = len(part_vectors[0])
            merged = [0.0] * dims
            for vec in part_vectors:
                for i in range(dims):
                    merged[i] += vec[i]
            for i in range(dims):
                merged[i] /= len(part_vectors)

            results.append(merged)
        return results

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts (passage/document mode). Handles batching."""
        if not texts:
            return []

        results = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            vectors = self._embed_batch_with_retry(batch, is_query=False)
            results.extend(vectors)
        return results

    def embed_query(self, query: str) -> List[float]:
        """Embed a single query text (uses query input type for providers that support it)."""
        result = self._embed_batch_with_retry([query], is_query=True)
        return result[0]
