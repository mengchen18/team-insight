---
name: team-insight
description: "How to read and write memories from the project's shared LanceDB knowledge base. Use this skill WHENEVER the user mentions saving an insight, remembering a decision, or asks questions about past context, architectural choices, or undocumented team knowledge, even if they don't explicitly mention 'memory'. Also use when you lack context about the project."
---

# Team Insight Memory Skill

You are equipped with a shared LanceDB-backed memory system called **team-insight**. This memory system spans across the entire team and persists beyond this conversation.

All scripts run inside a portable Singularity/Apptainer SIF container bundled with this skill.

## Quick Reference

**Locate this skill folder.** If this file is at `.claude/skills/team-insight/SKILL.md`, then:
- **SIF**: `.claude/skills/team-insight/env/team-insight-avx.sif`
- **Scripts**: `.claude/skills/team-insight/scripts/cli.py`
- **Setting**: `.claude/skills/team-insight/setting.json`

```bash
# Auto-detect bind mounts for any paths (handles external drives, NFS, etc.)
# Usage: BINDS=$(apptainer_binds path1 path2 ...)
apptainer_binds() {
  local seen="" binds=""
  for path in "$@"; do
    local mp
    mp=$(stat --format="%m" "$path" 2>/dev/null) || continue
    [[ "$mp" == "/" ]] && continue          # root fs is always accessible
    [[ " $seen " == *" $mp "* ]] && continue  # deduplicate
    seen="$seen $mp"
    binds="${binds:+$binds,}$mp:$mp"
  done
  echo "$binds"
}

# Generic command pattern:
SKILL_DIR=".claude/skills/team-insight"
SIF="$SKILL_DIR/env/team-insight-avx.sif"
BINDS=$(apptainer_binds "<project_root>" "$SIF")
apptainer exec ${BINDS:+--bind "$BINDS"} "$SIF" \
  python "$SKILL_DIR/scripts/cli.py" \
  --setting "$SKILL_DIR/setting.json" \
  --project-root <project_root> \
  <command> [args]
```

## Modules

To determine which module to use, match the user's intent or your current context to the specific triggers below.

### 1. Retrieve Memory → [module_retrieve.md](./module_retrieve.md)
**WHEN TO USE**:
- You lack context about a specific architectural choice, standard, or codebase pattern.
- The user asks a question about past decisions, project history, or documented team knowledge.
- You are starting a new task and need to check if there are existing conventions to follow.

**ACTION**: Search the shared LanceDB. **Always do this first** before answering if you lack context.

```bash
BINDS=$(apptainer_binds "$ROOT" "$SIF"); apptainer exec ${BINDS:+--bind "$BINDS"} "$SIF" python "$CLI" --setting "$SET" --project-root "$ROOT" search "your query" --limit 5
```

### 2. Remember from Conversation → [module_remember.md](./module_remember.md)
**WHEN TO USE**:
- The user explicitly says "remember this", "save this insight", or "document this decision".
- The user asks you to summarize the current conversation for future reference.
- You both arrived at a significant architectural decision or solved a complex bug that the team should know about.

**ACTION**: Extract insights from the conversation context and save them to JSON. Do NOT ask for permission if the user explicitly commanded it.

```bash
BINDS=$(apptainer_binds "$ROOT" "$SIF"); apptainer exec ${BINDS:+--bind "$BINDS"} "$SIF" python "$CLI" --setting "$SET" --project-root "$ROOT" remember "your text" --category insight --keywords "tag1, tag2"
```

### 3. Ingest Files → [module_ingest.md](./module_ingest.md)
**WHEN TO USE**:
- The user explicitly types the command `/team-insight ingest <path>`.
- The user asks you to "read this file into memory" or "digest this folder".

**ACTION**: Convert raw project files (code, PDFs, spreadsheets) into standardized JSON v2.0 memory files. *Note: this step is strictly read-only.*

### 4. Embed into LanceDB → [module_embed.md](./module_embed.md)
**WHEN TO USE**:
- You just successfully completed Module 2 (Remember) or Module 3 (Ingest), and the user answered "yes" when you asked if you should embed the JSON into long-term memory.
- The user explicitly asks to "update the database", "run embed", or "sync memories".

**ACTION**: Embed the generated local `.json` files into the LanceDB vector database to make them searchable.

```bash
BINDS=$(apptainer_binds "$ROOT" "$SIF"); apptainer exec ${BINDS:+--bind "$BINDS"} "$SIF" python "$CLI" --setting "$SET" --project-root "$ROOT" ingest
```

## Memory Organization

All data lives in `.claude/team-insight/`:
- **`json/user/{username}/`**: Conversation memories per user
- **`json/file/`**: Ingested file JSONs
- **`db/`**: LanceDB vector database

## JSON v2.0 Schema

Every memory is stored as a JSON file following this schema:

```json
{
  "version": "2.0",
  "source": {
    "file_path": "relative/path/to/source",
    "file_type": "python",
    "last_modified": "2024-03-05T14:30:00Z",
    "author": "username"
  },
  "document": {
    "title": "Descriptive title",
    "summary": "1-3 paragraph summary",
    "keywords": ["keyword1", "keyword2"]
  },
  "chunks": [
    {
      "chunk_id": "chunk_1",
      "chunk_title": "Section Name",
      "content": "Detailed content for this chunk",
      "keywords": ["specific", "tags"]
    }
  ],
  "relations": {
    "reads_from": ["path/to/input"],
    "writes_to": ["path/to/output"]
  }
}
```

## Important Rules

1. **Never write to Claude's internal MEMORY.md.** Always use the scripts above.
2. If the user asks you to remember something, execute the `remember` script immediately. Do not ask for permission.
3. If you lack context on a subject, execute the `search` script before answering. Do not ask for permission.
4. After generating JSON files (via ingest or remember), ask the user: *"The JSON memory has been generated. Should I embed it into long-term memory (LanceDB)?"* (Skip asking if running headlessly).
5. When ingesting files, check `references/` for file-type-specific parsing instructions.
6. **CRITICAL INGESTION SAFETY RULE**: When ingesting files, you operate in a **STRICTLY READ-ONLY** capacity for the project's codebase. The ONLY files you are permitted to create or modify are the JSON outputs in `.claude/team-insight/json/`. You must **NEVER** modify, update, delete, refactor, or touch any project files under ANY circumstances. This is paramount because ingestion may run headlessly with `--dangerously-skip-permissions`.
