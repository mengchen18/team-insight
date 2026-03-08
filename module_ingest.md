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

2. **Run the Pre-processor Check**: Before reading *any* file content, you MUST run the smart ingestion diffing helper to see if the file actually needs to be processed.
   ```bash
   apptainer exec <SIF> python <skill_dir>/scripts/ingest_helper.py diff <target_file> --json-dir .claude/team-insight/json
   ```
   > If this command fails (e.g., apptainer not available, SIF missing), proceed as if the output was `"action": "READ_ENTIRE_FILE"`.

   Handle the output as follows:

   - **`"action": "SKIP"`**: Instantly STOP processing this file and inform the user it was skipped (already up to date).

   - **`"action": "READ_PARTIAL"`**: The file changed but only specific slides need re-processing. Follow the **Partial Update Procedure** below.

   - **`"action": "READ_ENTIRE_FILE"`**: Proceed normally to step 3.

3. **Check for a reference template**: Look in `<skill_dir>/references/` for a file-type-specific parsing guide:
   - `.py` → `references/python.md`
   - `.R` → `references/r_script.md`
   - `.xlsx` → `references/excel.md`
   - `.pptx` → `references/pptx.md`
   - `.docx` → `references/docx.md`
   - `.csv`, `.tsv` → `references/csv.md`
   - `.rds` → `references/rds.md`

4. **Read the reference template** and follow its instructions for what to extract, how to chunk, what to ignore, and how to handle visuals.

5. **Read and analyze the file**: As Claude Code, you can directly read text files. For binary files (xlsx, pptx, docx), use available tools or libraries. Remember to only read what the pre-processor told you to read.

6. **Generate JSON v2.0**: Create a JSON file following the schema in SKILL.md.

7. **Save the JSON** to `.claude/team-insight/json/file/{original_filename}.json`.

8. **Stamp the JSON**: Run the stamp command to write raw content hashes into the JSON for future differential ingestion:
   ```bash
   apptainer exec <SIF> python <skill_dir>/scripts/ingest_helper.py stamp <target_file> --json-dir .claude/team-insight/json
   ```

9. **Ask the user**: "The JSON memory has been generated. Should I embed it into long-term memory (LanceDB)?"

10. **If yes**, run the embed/ingest command (see [module_embed.md](./module_embed.md)).

## Partial Update Procedure

When the pre-processor returns `"action": "READ_PARTIAL"`, the output includes:
- `changed_slides`: Slide numbers whose text content changed.
- `added_slides`: New slide numbers that didn't exist before.
- `deleted_slides`: Slide numbers that were removed from the file.
- `context`: Summaries of neighboring chunks for context.

Follow these steps:

1. **Read ONLY** the slides listed in `changed_slides` and `added_slides` from the file.
2. **Update existing chunks**: Find which chunks in the JSON cover those slides and update their `content` and `keywords` to reflect the new slide text. If a new slide doesn't fit an existing chunk, create a new chunk for it.
3. **Handle deletions**: For each slide in `deleted_slides`, check if any chunk was exclusively about that slide. If so, remove the chunk. If the chunk covers multiple slides, update its content to remove references to the deleted slide.
4. **Update metadata**: Update `source.last_modified` in the JSON. If the changes are significant, update `document.summary` as well.
5. **Re-run stamp**: Execute the stamp command (step 8 above) to update `_slide_hashes` and `source.hash` in the JSON.

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
