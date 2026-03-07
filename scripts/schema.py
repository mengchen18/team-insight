"""
JSON v2.0 schema validation using Pydantic.
Ported from memory-plugin/src/core/schema.ts.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Source(BaseModel):
    file_path: str
    file_type: str
    last_modified: Optional[str] = None
    hash: Optional[str] = None
    author: Optional[str] = None


class Document(BaseModel):
    title: str
    summary: str
    keywords: List[str] = Field(default_factory=list)


class Chunk(BaseModel):
    chunk_id: str
    chunk_title: str
    content: str
    keywords: List[str] = Field(default_factory=list)
    chunk_hash: Optional[str] = None


class Relations(BaseModel):
    reads_from: Optional[List[str]] = None
    writes_to: Optional[List[str]] = None
    implements: Optional[List[str]] = None
    uses: Optional[List[str]] = None
    references: Optional[List[str]] = None
    links_to: Optional[List[str]] = None
    author: Optional[str] = None

    model_config = {"extra": "allow"}


class MemoryDocument(BaseModel):
    version: str = "2.0"
    source: Source
    document: Document
    chunks: List[Chunk]
    relations: Optional[Relations] = Field(default_factory=Relations)


def compose_embed_text(chunk: Chunk) -> str:
    """
    Compose the text sent to the embedding API for a given chunk.
    Combines chunk_title + content + keywords for maximal semantic signal.
    """
    keywords_str = ""
    if chunk.keywords:
        keywords_str = f" Keywords: {', '.join(chunk.keywords)}"
    return f"{chunk.chunk_title}. {chunk.content}{keywords_str}".strip()
