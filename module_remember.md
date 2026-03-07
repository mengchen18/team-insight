---
name: module_remember
description: "Instructions for saving memories from conversation context."
---

# Module: Remember from Conversation

Use this module to persist insights, decisions, and important context from the current conversation into the team's shared memory.

## Two Flows

### Flow 1: Explicit — User says "remember X"

When the user explicitly asks you to remember something (e.g. "remember that we use JWT tokens"), save it immediately:

```bash
apptainer exec --bind <project_root>:<project_root> \
  <skill_dir>/env/team-insight-avx.sif \
  python <skill_dir>/scripts/cli.py \
  --setting <skill_dir>/setting.json \
  --project-root <project_root> \
  remember "<detailed text to remember>" \
  --category "<category>" \
  --keywords "<comma, separated, tags>"
```

**Do NOT ask for permission.** Execute immediately.

### Flow 2: Summarize — User asks for a conversation summary

When the user says `/team-insight summary` or asks you to summarize what to remember:

1. **Summarize** the key insights from the conversation context (decisions made, bugs found, architecture choices, workarounds discovered)
2. **Present** a numbered list of candidate items
3. **Ask** the user to select which items to save
4. **Execute** the `remember` command for each selected item
5. **Ask**: "The JSON memories have been generated. Should I embed them into long-term memory (LanceDB)?"
6. If yes, run the `ingest` command (see [module_embed.md](./module_embed.md))

## Categories

Choose the most appropriate category:

| Category | Use for |
|---|---|
| `insight` | General learnings, observations |
| `decision` | Architectural or design decisions |
| `architecture` | System structure, patterns, component relationships |
| `bug` | Bug reports, workarounds, known issues |
| `fact` | Factual information about the system |

## Keywords

Choose 3-8 specific, searchable keywords. Examples:
- `"authentication, JWT, security, cookies"`
- `"database, migration, PostgreSQL, schema"`
- `"deployment, CI/CD, Docker, staging"`

## Output

The `remember` command creates a JSON v2.0 file in `.claude/team-insight/json/user/{username}/`. This file is committed to Git so the whole team shares it.

**Important**: The JSON file is NOT searchable via vector search until it is embedded by running `ingest`. Always offer to run ingest after generating memories.
