---
name: module_ingest
description: "Instructions for digesting project files into JSON v2.0 memory representations."
---

# Module: Ingest Files

This module is triggered when the user says `/team-insight ingest <file_path>` or `/team-insight ingest <folder_path>`. It converts project files into standardized JSON v2.0 memory files.

## Process

> [!CAUTION]
> **STRICT ZERO-MODIFICATION POLICY**: You are ONLY allowed to read project files and write the parsed outputs into the `.claude/team-insight/json/` directory. You must **NEVER** update, modify, rename, delete, or otherwise touch **any** other files in the user's project during the ingestion process.

1. **Identify the file(s)**: List files at the given path. For folders, process all supported file types.

2. **Check for a reference template**: Look in `<skill_dir>/references/` for a file-type-specific parsing guide:
   - `.py` → `references/python.md`
   - `.R` → `references/r_script.md`
   - `.xlsx` → `references/excel.md`
   - `.pptx` → `references/pptx.md`
   - `.docx` → `references/docx.md`
   - `.csv`, `.tsv` → `references/csv.md`
   - `.rds` → `references/rds.md`

3. **Read the reference template** and follow its instructions for what to extract, how to chunk, what to ignore, and how to handle visuals.

4. **Read and analyze the file**: As Claude Code, you can directly read text files. For binary files (xlsx, pptx, docx), use available tools or libraries.

5. **Generate JSON v2.0**: Create a JSON file following the schema in SKILL.md.

6. **Save the JSON** to `.claude/team-insight/json/file/{original_filename}.json`.

7. **Ask the user**: "The JSON memory has been generated. Should I embed it into long-term memory (LanceDB)?"

8. **If yes**, run the embed/ingest command (see [module_embed.md](./module_embed.md)).

## Chunking Guidelines (if no reference template exists)

| File Type | Chunking Strategy | Key Extraction |
|---|---|---|
| Scripts (`.py`, `.R`, `.sh`, `.sql`) | Per function/class/block | Purpose, dependencies, I/O |
| Data files (`.csv`, `.tsv`) | Schema + stats | Column names, types, row count |
| Spreadsheets (`.xlsx`) | Per tab | Tab name, headers, data summary |
| Presentations (`.pptx`) | Per slide | Title, text, figure descriptions |
| Documents (`.docx`, `.md`) | Per heading section | Section title, body text |

## Important

- **Focus on "why" and "how"**, not just "what". Explain the purpose and design decisions.
- **Include function signatures** for code files.
- **Skip trivial boilerplate** and auto-generated content.
- **For visuals** (charts, figures): describe them in natural language.
- **Populate relations**: `reads_from`, `writes_to`, `uses`, `implements` when applicable.
