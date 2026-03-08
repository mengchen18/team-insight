---
name: digest_python
description: Instructions for parsing and digesting Python scripts into ccmem JSON v2.0 memory files.
---

# Digesting Python Scripts

You are an expert at analyzing Python code and extracting long-term knowledge, architectural decisions, and reusable components.

When the user asks you to digest a Python file (`.py`), you must analyze its contents and generate a standardized JSON summary according to the ccmem v2.0 schema, then save it to `.claude/team-insight/json/`.

## Process

1. **Analyze the Module**: Read the Python file to understand its purpose, classes, functions, and key logic.
2. **Identify Chunks**: Break the file down into logical chunks. Good chunks for Python include:
   - Module-level docstrings and global configurations
   - Individual major Classes, including their primary methods
   - Standalone utility functions
   - Complex algorithmic blocks within large functions
3. **Extract Knowledge**: For each chunk, extract the core logic, parameters, return types, and any noticeable "gotchas", hacks, or important decisions.
4. **Determine Keywords**: Select 3-8 highly relevant keywords for the document as a whole, and 2-5 specific keywords for each chunk.
5. **Format as JSON**: Construct the JSON object strictly matching the v2.0 schema (see below).
6. **Save**: Save the resulting JSON file to `.claude/team-insight/json/{original_filename}.json`.

## Guidelines for Python

*   **Focus on the "Why" and "How"**: Don't just paste the code. Explain what the code does, why it's written that way, and how it fits into the broader system (if apparent).
*   **Signatures**: For classes and functions, include the signature (arguments, types) in the chunk `content`.
*   **Dependencies**: Note important external libraries used by the script.
*   **Dependencies**: Note important external libraries used by the script.
*   **Ignore**: Skip trivial boilerplate, standard library imports (unless crucial to logic), and auto-generated code.

## JSON v2.0 Schema Reference

Your output MUST be a valid JSON object matching this structure:

```json
{
  "version": "2.0",
  "source": {
    "file_path": "path/to/script.py", 
    "file_type": "python",
    "last_modified": "YYYY-MM-DDThh:mm:ssZ"
  },
  "document": {
    "title": "A descriptive title for the module",
    "summary": "A 1-3 paragraph summary of the entire module's purpose and functionality.",
    "keywords": ["python", "api", "database", "async"]
  },
  "chunks": [
    {
      "chunk_id": "chunk_1",
      "chunk_title": "Class: DatabaseManager",
      "content": "Detailed explanation of the DatabaseManager class, its connection string handling, and retry logic. Examples of how it's used.",
      "keywords": ["database", "connection", "retry"]
    },
    {
      "chunk_id": "chunk_2",
      "chunk_title": "Function: process_batch",
      "content": "Explanation of the `process_batch(items: list) -> int` function...",
      "keywords": ["batch", "processing"]
    }
  ],
  "relations": {
    "links_to": ["path/to/config.py"], 
    "implements": ["BaseManager"],
    "uses": ["psycopg2", "pydantic"]
  }
}
```

*Note: You can omit fields in `relations` if they don't apply. Ensure `file_path` matches the actual file being discussed, relative to the project root.*
