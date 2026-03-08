"""
Helper script for Phase 1 Smart Ingestion.
Runs before Claude Code reads a file to check if it's already in memory.
For binary/presentation files, it extracts slides and diffs hashes.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Optional


def compute_chunk_hash(text: str) -> str:
    """Compute SHA-256 hash for chunk content. Must match utils.py"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_existing_json_path(target_file: str, json_dir: str) -> Optional[str]:
    """Find the existing parsed JSON for this file."""
    base_name = os.path.basename(target_file)
    json_path = os.path.join(json_dir, "file", f"{base_name}.json")
    if os.path.exists(json_path):
        return json_path
    
    # Try searching for a match if the name convention changed slightly
    file_dir = os.path.join(json_dir, "file")
    if os.path.exists(file_dir):
        for f in os.listdir(file_dir):
            if f.endswith(".json"):
                path = os.path.join(file_dir, f)
                try:
                    with open(path, "r") as jf:
                        data = json.load(jf)
                        if data.get("source", {}).get("file_path") == target_file:
                            return path
                except Exception:
                    pass
    return None


def cmd_diff(args):
    target_file = os.path.abspath(args.file)
    json_dir = os.path.abspath(args.json_dir)

    if not os.path.exists(target_file):
        print(json.dumps({"error": f"File not found: {target_file}"}))
        sys.exit(1)

    # 1. Check if we have an existing JSON memory
    json_path = get_existing_json_path(target_file, json_dir)
    if not json_path:
        print(json.dumps({
            "status": "new",
            "reason": "No existing JSON memory found.",
            "action": "READ_ENTIRE_FILE"
        }, indent=2))
        return

    # 2. Check File-Level Modification Time
    try:
        with open(json_path, "r") as f:
            existing_data = json.load(f)
    except Exception as e:
        print(json.dumps({"error": f"Failed to read JSON: {e}"}))
        sys.exit(1)

    actual_mtime_ts = os.path.getmtime(target_file)
    # Convert to ISO format matching our schema
    from datetime import datetime, timezone
    actual_mtime = datetime.fromtimestamp(actual_mtime_ts, tz=timezone.utc).isoformat()
    
    # Simple string comparison (assumes both are standard ISO format)
    # In practice, comparing timestamps robustly is better done via parsing
    memory_mtime = existing_data.get("source", {}).get("last_modified")

    # If the file hasn't been modified on disk since the JSON was created
    # We can perform a fast-skip
    if memory_mtime:
        try:
            mem_dt = datetime.fromisoformat(memory_mtime.replace('Z', '+00:00'))
            act_dt = datetime.fromisoformat(actual_mtime.replace('Z', '+00:00'))
            if act_dt <= mem_dt:
                print(json.dumps({
                    "status": "unchanged",
                    "reason": f"File not modified since {memory_mtime}.",
                    "action": "SKIP"
                }, indent=2))
                return
        except Exception:
            pass

    # 3. File is modified. Can we do chunk-level diffing?
    ext = os.path.splitext(target_file)[1].lower()
    
    if ext == ".pptx":
        try:
            from pptx import Presentation
        except ImportError:
            print(json.dumps({
                "status": "modified",
                "reason": "File modified. python-pptx not installed for granular diff.",
                "action": "READ_ENTIRE_FILE"
            }, indent=2))
            return
            
        # Parse existing chunks to build a map
        old_chunks = {}
        for c in existing_data.get("chunks", []):
            cid = c.get("chunk_id")
            old_chunks[cid] = c

        try:
            prs = Presentation(target_file)
            changed_slides = []
            
            # Extract text and hash per slide
            for i, slide in enumerate(prs.slides):
                slide_num = i + 1
                chunk_id = f"slide_{slide_num}"
                
                # Simple text extraction from shapes
                text_runs = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text:
                        text_runs.append(shape.text.strip())
                slide_content = "\\n".join(text_runs).strip()
                
                # We skip completely empty slides
                if not slide_content:
                    continue
                    
                new_hash = compute_chunk_hash(slide_content)
                old_chunk = old_chunks.get(chunk_id)
                
                # Check if slide changed or is new
                if not old_chunk or old_chunk.get("chunk_hash") != new_hash:
                    changed_slides.append({
                        "chunk_id": chunk_id,
                        "slide_number": slide_num,
                        "content_preview": slide_content[:200]
                    })
            
            if not changed_slides:
                 # It's possible the file was modified without text changes (e.g., formatting/metadata)
                 print(json.dumps({
                     "status": "unchanged",
                     "reason": "PPTX file has newer timestamp, but text content hashes are identical.",
                     "action": "SKIP"
                 }, indent=2))
                 return

            # Assemble surrounding context for the changed slides
            requested_chunks = []
            context_chunks = []
            
            # To minimize tokens, we just grab adjacent context from old memory
            for cs in changed_slides:
                requested_chunks.append(cs["chunk_id"])
                
                curr_slide_num = int(cs['slide_number'])
                prev_id = f"slide_{curr_slide_num - 1}"
                next_id = f"slide_{curr_slide_num + 1}"
                
                if prev_id in old_chunks and prev_id not in requested_chunks:
                    context_chunks.append({
                        "chunk_id": prev_id,
                        "summary": str(old_chunks[prev_id].get("content", ""))[:300] + "..."
                    })
                if next_id in old_chunks and next_id not in requested_chunks:
                    context_chunks.append({
                        "chunk_id": next_id,
                        "summary": str(old_chunks[next_id].get("content", ""))[:300] + "..."
                    })

            print(json.dumps({
                "status": "modified",
                "reason": f"Found {len(changed_slides)} modified slides.",
                "action": "READ_PARTIAL",
                "chunks_to_process": requested_chunks,
                "context": context_chunks
            }, indent=2))
            return
            
        except Exception as e:
             print(json.dumps({
                "status": "modified",
                "reason": f"Error parsing PPTX: {e}",
                "action": "READ_ENTIRE_FILE"
            }, indent=2))
             return

    # Fallback for text files (code, md, etc) where semantic chunking is done by LLM
    print(json.dumps({
        "status": "modified",
        "reason": "File modified. Granular text diffing not supported.",
        "action": "READ_ENTIRE_FILE"
    }, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestion preprocessing helper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    diff_parser = subparsers.add_parser("diff")
    diff_parser.add_argument("file", help="Path to the target project file")
    diff_parser.add_argument("--json-dir", required=True, help="Path to .claude/team-insight/json")
    
    args = parser.parse_args()
    
    if args.command == "diff":
        cmd_diff(args)
