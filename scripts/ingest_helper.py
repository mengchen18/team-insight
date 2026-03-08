"""
Helper script for Phase 1 Smart Ingestion.
Runs before Claude Code reads a file to check if it's already in memory.
For binary/presentation files, it extracts slides and diffs hashes.

Subcommands:
  diff   - Check if a file needs re-ingestion (SKIP / READ_PARTIAL / READ_ENTIRE_FILE)
  stamp  - Post-ingestion: write raw content hashes into the JSON for future diffs
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Optional


# ---------------------------------------------------------------------------
# Hashing helpers
# ---------------------------------------------------------------------------

def compute_chunk_hash(text: str) -> str:
    """Compute SHA-256 hash for chunk content. Must match utils.py."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file's binary contents. Must match utils.py."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# PPTX text extraction
# ---------------------------------------------------------------------------

def _extract_shape_content(shape) -> list:
    """Extract text and binary fingerprints from a single shape (recursive for groups)."""
    parts = []

    # Grouped shapes: recurse into children
    if shape.shape_type is not None and shape.shape_type == 6:  # MSO_SHAPE_TYPE.GROUP
        for child in shape.shapes:
            parts.extend(_extract_shape_content(child))
        return parts

    # Tables: extract cell text row by row
    if shape.has_table:
        for row in shape.table.rows:
            row_text = " | ".join(
                cell.text.strip() for cell in row.cells if cell.text.strip()
            )
            if row_text:
                parts.append(row_text)
        return parts

    # Images: hash the raw blob bytes
    try:
        if hasattr(shape, "image") and shape.image is not None:
            blob_hash = hashlib.sha256(shape.image.blob).hexdigest()
            parts.append(f"[image:{blob_hash}]")
    except Exception:
        pass

    # Charts: hash the underlying chart XML data
    if shape.has_chart:
        try:
            chart_xml = shape.chart._chartSpace.xml
            chart_hash = hashlib.sha256(chart_xml.encode("utf-8")).hexdigest()
            parts.append(f"[chart:{chart_hash}]")
        except Exception:
            pass

    # Text (regular shapes, text boxes, placeholders)
    if hasattr(shape, "text") and shape.text:
        parts.append(shape.text.strip())

    return parts


def extract_slide_fingerprints(pptx_path: str) -> Dict[str, str]:
    """Extract a content fingerprint per slide.

    Returns {slide_number_str: fingerprint_string}.
    The fingerprint combines text, image hashes, chart hashes, and speaker
    notes so that ANY content change (text, image swap, chart update) is
    detected by a simple string hash comparison.
    """
    from pptx import Presentation
    prs = Presentation(pptx_path)
    slides = {}
    for i, slide in enumerate(prs.slides):
        parts = []
        for shape in slide.shapes:
            parts.extend(_extract_shape_content(shape))

        # Speaker notes
        if slide.has_notes_slide:
            notes_text = slide.notes_slide.notes_text_frame.text.strip()
            if notes_text:
                parts.append(f"[notes:{notes_text}]")

        content = "\n".join(parts).strip()
        if content:
            slides[str(i + 1)] = content
    return slides


# ---------------------------------------------------------------------------
# JSON lookup
# ---------------------------------------------------------------------------

def get_existing_json_path(target_file: str, json_dir: str) -> Optional[str]:
    """Find the existing parsed JSON for this file."""
    base_name = os.path.basename(target_file)
    json_path = os.path.join(json_dir, "file", f"{base_name}.json")
    if os.path.exists(json_path):
        return json_path

    # Fallback: scan by source.file_path (handles renamed JSON files)
    file_dir = os.path.join(json_dir, "file")
    if os.path.exists(file_dir):
        for f in os.listdir(file_dir):
            if f.endswith(".json"):
                path = os.path.join(file_dir, f)
                try:
                    with open(path, "r") as jf:
                        data = json.load(jf)
                        stored = data.get("source", {}).get("file_path", "")
                        # Compare basenames to handle different absolute paths
                        if os.path.basename(stored) == base_name:
                            return path
                except Exception:
                    pass
    return None


# ---------------------------------------------------------------------------
# diff subcommand
# ---------------------------------------------------------------------------

def cmd_diff(args):
    target_file = os.path.abspath(args.file)
    json_dir = os.path.abspath(args.json_dir)

    if not os.path.exists(target_file):
        print(json.dumps({"error": f"File not found: {target_file}"}))
        sys.exit(1)

    # 1. Look up existing JSON memory
    json_path = get_existing_json_path(target_file, json_dir)
    if not json_path:
        print(json.dumps({
            "status": "new",
            "action": "READ_ENTIRE_FILE",
            "reason": "No existing JSON memory found."
        }, indent=2))
        return

    try:
        with open(json_path, "r") as f:
            existing_data = json.load(f)
    except Exception as e:
        print(json.dumps({"error": f"Failed to read JSON: {e}"}))
        sys.exit(1)

    # 2. File-level skip — prefer content hash, fall back to mtime
    stored_hash = existing_data.get("source", {}).get("hash")
    if stored_hash:
        current_hash = compute_file_hash(target_file)
        if current_hash == stored_hash:
            print(json.dumps({
                "status": "unchanged",
                "action": "SKIP",
                "reason": "File content hash unchanged."
            }, indent=2))
            return
    else:
        # mtime fallback (less reliable but better than nothing)
        memory_mtime = existing_data.get("source", {}).get("last_modified")
        if memory_mtime:
            try:
                mem_dt = datetime.fromisoformat(memory_mtime.replace("Z", "+00:00"))
                act_ts = os.path.getmtime(target_file)
                act_dt = datetime.fromtimestamp(act_ts, tz=timezone.utc)
                if act_dt <= mem_dt:
                    print(json.dumps({
                        "status": "unchanged",
                        "action": "SKIP",
                        "reason": f"File not modified since {memory_mtime} (mtime check)."
                    }, indent=2))
                    return
            except Exception:
                pass  # fall through to content check

    # 3. File is modified — attempt slide-level diff for PPTX
    ext = os.path.splitext(target_file)[1].lower()

    if ext == ".pptx":
        try:
            from pptx import Presentation  # noqa: F401
        except ImportError:
            print(json.dumps({
                "status": "modified",
                "action": "READ_ENTIRE_FILE",
                "reason": "python-pptx not installed for granular diff."
            }, indent=2))
            return

        old_slide_hashes = existing_data.get("_slide_hashes", {})
        if not old_slide_hashes:
            # No stamp data — cannot do granular diff
            print(json.dumps({
                "status": "modified",
                "action": "READ_ENTIRE_FILE",
                "reason": "No _slide_hashes in JSON (run stamp after first ingestion)."
            }, indent=2))
            return

        try:
            current_slides = extract_slide_fingerprints(target_file)
        except Exception as e:
            print(json.dumps({
                "status": "modified",
                "action": "READ_ENTIRE_FILE",
                "reason": f"Error parsing PPTX: {e}"
            }, indent=2))
            return

        # Hash current slides
        current_hashes = {k: compute_chunk_hash(v) for k, v in current_slides.items()}

        # Set-based diff
        old_keys = set(old_slide_hashes.keys())
        new_keys = set(current_hashes.keys())

        changed = sorted(
            [s for s in old_keys & new_keys if current_hashes[s] != old_slide_hashes[s]],
            key=int,
        )
        added = sorted(new_keys - old_keys, key=int)
        deleted = sorted(old_keys - new_keys, key=int)

        if not changed and not added and not deleted:
            print(json.dumps({
                "status": "unchanged",
                "action": "SKIP",
                "reason": "Binary differs but slide text hashes are identical (formatting-only change)."
            }, indent=2))
            return

        # Build context from existing chunks for the affected slides
        affected = set(int(s) for s in changed + added)
        context_summaries = []
        seen_context = set()

        for slide_num in sorted(affected):
            for neighbor in [slide_num - 1, slide_num + 1]:
                nkey = str(neighbor)
                if nkey not in old_slide_hashes:
                    continue
                if neighbor in affected or nkey in seen_context:
                    continue
                seen_context.add(nkey)
                # Find any chunk that mentions this slide
                for c in existing_data.get("chunks", []):
                    content = c.get("content", "")
                    if content:
                        preview = content[:300]
                        if len(content) > 300:
                            preview += "..."
                        context_summaries.append({
                            "near_slide": neighbor,
                            "chunk_id": c.get("chunk_id"),
                            "summary": preview,
                        })
                        break

        result = {
            "status": "modified",
            "action": "READ_PARTIAL",
            "reason": (
                f"{len(changed)} changed, {len(added)} added, "
                f"{len(deleted)} deleted slides."
            ),
            "changed_slides": [int(s) for s in changed],
            "added_slides": [int(s) for s in added],
            "deleted_slides": [int(s) for s in deleted],
        }
        if context_summaries:
            result["context"] = context_summaries

        print(json.dumps(result, indent=2))
        return

    # Fallback for non-PPTX files
    print(json.dumps({
        "status": "modified",
        "action": "READ_ENTIRE_FILE",
        "reason": "File modified. Granular diffing not supported for this file type."
    }, indent=2))


# ---------------------------------------------------------------------------
# stamp subcommand
# ---------------------------------------------------------------------------

def cmd_stamp(args):
    """Post-ingestion: write raw slide hashes + file hash into the JSON."""
    target_file = os.path.abspath(args.file)
    json_dir = os.path.abspath(args.json_dir)

    json_path = get_existing_json_path(target_file, json_dir)
    if not json_path:
        print(json.dumps({"error": "No JSON found to stamp."}))
        sys.exit(1)

    try:
        with open(json_path, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(json.dumps({"error": f"Failed to read JSON: {e}"}))
        sys.exit(1)

    # Always stamp file content hash
    data.setdefault("source", {})["hash"] = compute_file_hash(target_file)

    # Update mtime
    mtime = os.path.getmtime(target_file)
    data["source"]["last_modified"] = datetime.fromtimestamp(
        mtime, tz=timezone.utc
    ).isoformat()

    # Slide-level hashes for PPTX
    ext = os.path.splitext(target_file)[1].lower()
    if ext == ".pptx":
        try:
            slide_texts = extract_slide_fingerprints(target_file)
            data["_slide_hashes"] = {
                k: compute_chunk_hash(v) for k, v in slide_texts.items()
            }
        except Exception as e:
            print(json.dumps({
                "warning": f"Could not extract slide hashes: {e}",
                "path": json_path,
            }))
            # Still save the file hash

    with open(json_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(json.dumps({
        "status": "stamped",
        "path": json_path,
        "file_hash": data["source"]["hash"],
        "slide_hashes": len(data.get("_slide_hashes", {})),
    }, indent=2))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestion preprocessing helper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    diff_parser = subparsers.add_parser(
        "diff", help="Check if a file needs re-ingestion"
    )
    diff_parser.add_argument("file", help="Path to the target project file")
    diff_parser.add_argument(
        "--json-dir", required=True,
        help="Path to .claude/team-insight/json"
    )

    stamp_parser = subparsers.add_parser(
        "stamp", help="Write raw content hashes into the JSON after ingestion"
    )
    stamp_parser.add_argument("file", help="Path to the target project file")
    stamp_parser.add_argument(
        "--json-dir", required=True,
        help="Path to .claude/team-insight/json"
    )

    args = parser.parse_args()

    if args.command == "diff":
        cmd_diff(args)
    elif args.command == "stamp":
        cmd_stamp(args)
