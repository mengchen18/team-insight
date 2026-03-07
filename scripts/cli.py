#!/usr/bin/env python3
"""
CLI entry point for team-insight memory system.

Subcommands:
  search   - Query the LanceDB memory
  remember - Save an insight to memory
  ingest   - Embed JSON files into LanceDB

Usage (via SIF):
  apptainer exec team-insight-avx.sif python cli.py search "query" --limit 5
  apptainer exec team-insight-avx.sif python cli.py remember "text" --category insight
  apptainer exec team-insight-avx.sif python cli.py ingest
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Optional

# Ensure scripts/ directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import load_config, resolve_username, Config
from embedder import Embedder
from schema import MemoryDocument, compose_embed_text
from store import MemoryStore
from retriever import Retriever


# =============================================================================
# Search
# =============================================================================

def cmd_search(args):
    """Search the shared memory."""
    config = load_config(setting_path=args.setting, project_root=args.project_root)
    _validate_api_keys(config)

    store = MemoryStore(config.lancedb)
    embedder = Embedder(config.embedding)
    retriever = Retriever(store, embedder, config.retrieval)

    results = retriever.retrieve(
        query=args.query,
        limit=args.limit,
        file_type=args.type,
        author=args.author,
    )

    if not results:
        print("No relevant memories found.")
        return

    output_lines = []
    for i, r in enumerate(results):
        score = r.get("score", 0)
        chunk_title = r.get("chunk_title", "Untitled")
        file_path = r.get("file_path", "unknown")
        doc_title = r.get("doc_title", "")
        doc_summary = r.get("doc_summary", "")
        author = r.get("author", "unknown")
        text = r.get("text", "")

        block = (
            f"**[{i + 1}] {chunk_title}** (score: {score:.3f})\n"
            f"📁 `{file_path}`\n"
            f"📄 {doc_title} — {doc_summary}\n"
            f"👤 {author}\n\n"
            f"{text}\n"
        )
        output_lines.append(block)

    print("\n---\n".join(output_lines))


# =============================================================================
# Remember
# =============================================================================

def cmd_remember(args):
    """Save a memory from conversation."""
    config = load_config(setting_path=args.setting, project_root=args.project_root)
    author = resolve_username(config)
    keywords = [k.strip() for k in args.keywords.split(",")] if args.keywords else []

    timestamp = datetime.now(timezone.utc).isoformat()
    mem_id = uuid.uuid4().hex[:8]
    category = args.category
    text = args.text

    filename = f"{timestamp.split('T')[0]}_{category}_{mem_id}.json"

    # Determine output directory
    output_dir = os.path.join(config.json_dir, "user", author)
    os.makedirs(output_dir, exist_ok=True)

    doc = {
        "version": "2.0",
        "source": {
            "file_path": f"_memories/{author}/{filename}",
            "file_type": "conversation_memory",
            "last_modified": timestamp,
            "author": author,
        },
        "document": {
            "title": f"{category.capitalize()}: {text[:80]}",
            "summary": text,
            "keywords": keywords,
        },
        "chunks": [
            {
                "chunk_id": "memory_1",
                "chunk_title": category.capitalize(),
                "content": text,
                "keywords": keywords,
            }
        ],
        "relations": {},
    }

    file_path = os.path.join(output_dir, filename)
    with open(file_path, "w") as f:
        json.dump(doc, f, indent=2)

    print(f"Memory saved to JSON file at `{file_path}`.")
    print("Note: Run `ingest` to embed this memory and make it searchable by the team.")


# =============================================================================
# Ingest
# =============================================================================

def cmd_ingest(args):
    """Embed JSON files into LanceDB."""
    config = load_config(setting_path=args.setting, project_root=args.project_root)
    _validate_api_keys(config)

    json_dir = args.json_dir or config.json_dir
    if not os.path.isdir(json_dir):
        print(f"JSON directory does not exist: {json_dir}", file=sys.stderr)
        sys.exit(1)

    store = MemoryStore(config.lancedb)
    embedder = Embedder(config.embedding)

    # Collect all JSON files
    json_files = []
    for root, dirs, files in os.walk(json_dir):
        for f in files:
            if f.endswith(".json"):
                json_files.append(os.path.join(root, f))

    print(f"[Ingest] Found {len(json_files)} JSON files in {json_dir}")

    stats = {"new": 0, "updated": 0, "skipped": 0, "deleted": 0, "chunks": 0}
    to_embed = []
    disk_paths = set()
    default_author = resolve_username(config)

    for jf in json_files:
        try:
            file_hash = MemoryStore.compute_file_hash(jf)

            with open(jf, "r") as f:
                raw = json.load(f)

            # Validate schema
            try:
                doc = MemoryDocument.model_validate(raw)
            except Exception as e:
                print(f"[Ingest] Invalid JSON schema in {jf}: {e}", file=sys.stderr)
                continue

            file_path = doc.source.file_path
            disk_paths.add(file_path)

            if not store.needs_update(file_path, file_hash):
                stats["skipped"] += 1
                continue

            existing_hash = store.get_existing_hash(file_path)
            if existing_hash is None:
                stats["new"] += 1
            else:
                stats["updated"] += 1

            existing_chunks = store.get_chunk_hashes(file_path)
            active_chunk_ids = set()
            stale_row_ids = []

            for chunk in doc.chunks:
                chunk_text = compose_embed_text(chunk)
                chunk_hash = MemoryStore.compute_chunk_hash(chunk_text)
                chunk.chunk_hash = chunk_hash
                active_chunk_ids.add(chunk.chunk_id)

                if existing_chunks.get(chunk.chunk_id) == chunk_hash:
                    # Skip chunk, it hasn't changed
                    continue

                # Mark old version for deletion before re-adding
                if chunk.chunk_id in existing_chunks:
                    stale_row_ids.append(
                        MemoryStore.compute_row_id(file_path, chunk.chunk_id)
                    )

                to_embed.append(
                    {
                        "doc": doc,
                        "chunk": chunk,
                        "file_path": file_path,
                        "file_hash": file_hash,
                    }
                )

            # Cleanup orphaned chunks (removed from file) + stale chunks (content changed)
            orphans = [
                MemoryStore.compute_row_id(file_path, cid)
                for cid in existing_chunks.keys()
                if cid not in active_chunk_ids
            ]
            to_delete = orphans + stale_row_ids
            if to_delete:
                store.delete_chunks(to_delete)

        except Exception as e:
            print(f"[Ingest] Error processing {jf}: {e}", file=sys.stderr)

    if to_embed:
        print(f"[Ingest] Embedding {len(to_embed)} chunks...")
        embed_texts = [compose_embed_text(item["chunk"]) for item in to_embed]

        vectors = embedder.embed_texts(embed_texts)
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        rows = []
        for i, item in enumerate(to_embed):
            doc = item["doc"]
            chunk = item["chunk"]
            entry_author = doc.source.author or default_author

            rows.append(
                {
                    "id": MemoryStore.compute_row_id(item["file_path"], chunk.chunk_id),
                    "file_path": item["file_path"],
                    "file_type": doc.source.file_type,
                    "chunk_id": chunk.chunk_id,
                    "chunk_title": chunk.chunk_title,
                    "text": chunk.content,
                    "vector": vectors[i],
                    "doc_title": doc.document.title,
                    "doc_summary": doc.document.summary,
                    "metadata": json.dumps(
                        {
                            "keywords": chunk.keywords,
                            "doc_keywords": doc.document.keywords,
                            "relations": doc.relations.model_dump() if doc.relations else {},
                            "chunk_hash": chunk.chunk_hash,
                        }
                    ),
                    "source_hash": item["file_hash"],
                    "author": entry_author,
                    "timestamp": now_ms,
                }
            )

        store.upsert_chunks(rows)
        stats["chunks"] = len(rows)
        store.create_fts_index()

    # Cleanup orphans: entries in DB whose JSON files no longer exist on disk
    db_paths = store.get_all_file_paths()
    for db_path in db_paths:
        existing_hash = store.get_existing_hash(db_path)
        if existing_hash and db_path not in disk_paths:
            store.delete_by_file_path(db_path)
            stats["deleted"] += 1
            print(f"[Ingest] Cleaned up orphaned entry: {db_path}")

    print(
        f"[Ingest] Done! {stats['new']} new, {stats['updated']} updated, "
        f"{stats['skipped']} unchanged, {stats['deleted']} cleaned up. "
        f"Total chunks embedded: {stats['chunks']}"
    )


# =============================================================================
# Helpers
# =============================================================================

def _validate_api_keys(config: Config):
    if not config.embedding.api_keys:
        print(
            "No API keys configured. Set the appropriate environment variable "
            "(e.g. EMBEDDING_API_KEY) or configure api_keys in setting.json.",
            file=sys.stderr,
        )
        sys.exit(1)


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        prog="team-insight",
        description="Team-Insight: shared LanceDB memory system for Claude Code",
    )
    parser.add_argument(
        "--setting",
        help="Path to setting.json file",
        default=None,
    )
    parser.add_argument(
        "--project-root",
        help="Project root directory (defaults to cwd)",
        default=None,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # -- search --
    sp_search = subparsers.add_parser("search", help="Search the shared memory")
    sp_search.add_argument("query", help="Search query text")
    sp_search.add_argument("--limit", type=int, default=5, help="Number of results")
    sp_search.add_argument("--type", help="Filter by file type")
    sp_search.add_argument("--author", help="Filter by author")

    # -- remember --
    sp_remember = subparsers.add_parser("remember", help="Save a memory")
    sp_remember.add_argument("text", help="Text to remember")
    sp_remember.add_argument(
        "--category",
        default="insight",
        help="Category: insight, decision, architecture, bug, fact",
    )
    sp_remember.add_argument("--keywords", help="Comma-separated keywords")

    # -- ingest --
    sp_ingest = subparsers.add_parser("ingest", help="Embed JSON files into LanceDB")
    sp_ingest.add_argument("--json-dir", help="Override JSON directory path")

    args = parser.parse_args()

    if args.command == "search":
        cmd_search(args)
    elif args.command == "remember":
        cmd_remember(args)
    elif args.command == "ingest":
        cmd_ingest(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
