---
name: module_embed
description: "Instructions for embedding JSON files into LanceDB (long-term memory)."
---

# Module: Embed into LanceDB

This module embeds JSON v2.0 files into the LanceDB vector database, making them searchable via vector and full-text search.

## When to Run

- After generating new JSON files via `remember` or `ingest`
- As a nightly batch job (cron)
- When the user explicitly asks to update the long-term memory

## Command

```bash
apptainer exec --bind <project_root>:<project_root> \
  <skill_dir>/env/team-insight-avx.sif \
  python <skill_dir>/scripts/cli.py \
  --setting <skill_dir>/setting.json \
  --project-root <project_root> \
  ingest
```

### Options

| Flag | Default | Description |
|---|---|---|
| `--json-dir` | (from setting.json) | Override the JSON directory to scan |

## What It Does

1. **Scans** the JSON directory for all `.json` files
2. **Validates** each file against the v2.0 schema
3. **Diffs** by comparing SHA-256 hashes — skips unchanged files
4. **Embeds** new/updated chunks using the configured embedding provider
5. **Upserts** vectors into LanceDB
6. **Creates** a full-text search (FTS) index on the `text` column
7. **Cleans up** orphaned entries (JSON files that were deleted from disk)

## File Locking

The ingest command uses an exclusive file lock (`db/.lock`) to prevent concurrent writes from multiple users. If another process is writing, it will wait until the lock is released.

## Expected Output

```
[Ingest] Found 12 JSON files in .claude/team-insight/json
[Ingest] Embedding 8 chunks...
[Ingest] Done! 3 new, 1 updated, 8 unchanged, 0 cleaned up. Total chunks embedded: 8
```

## Automation (Cron)

For automatic nightly embedding:

```bash
0 2 * * * apptainer exec --bind /project:/project /path/to/team-insight-avx.sif python /path/to/cli.py --setting /path/to/setting.json --project-root /project ingest 2>&1 >> /var/log/team-insight.log
```
