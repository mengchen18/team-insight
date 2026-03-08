---
name: module_retrieve
description: "Instructions for searching the team's shared LanceDB memory."
---

# Module: Retrieve Memory

Use this module whenever you need context about the project that isn't in the current conversation. Search the shared memory **proactively** — don't wait for the user to ask.

## When to Search

- You lack context about a project decision, architecture, or pattern
- The user asks about past work, history, or team knowledge
- You're about to modify code and want to check for documented gotchas
- The user asks a question you can't fully answer from the current context

## How to Search

```bash
apptainer exec <SIF> python <skill_dir>/scripts/cli.py \
  --setting <skill_dir>/setting.json \
  --project-root <project_root> \
  search "<your natural language query>" \
  --limit 5
```

### Options

| Flag | Default | Description |
|---|---|---|
| `--limit` | 5 | Number of results to return |
| `--type` | (all) | Filter by file type (e.g. `python`, `r_script`, `conversation_memory`) |
| `--author` | (all) | Filter by author username |

## Interpreting Results

Each result includes:
- **Score** (0.0–1.0): Higher is more relevant
- **Chunk title**: The semantic section name
- **File path**: Where the original data lives
- **Author**: Who created this memory
- **Text**: The actual content

## Tips

- Use natural language queries, not keywords
- Try multiple queries with different phrasing if the first attempt returns poor results
- If searching for a specific file or concept, include its name in the query
- Results with scores below 0.35 are filtered out automatically
