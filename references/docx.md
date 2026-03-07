---
name: digest_docx
description: Instructions for parsing and digesting Word documents (.docx, .doc) into ccmem JSON v2.0 memory files.
---

# Digesting Word Documents

You are an expert analyst tasked with extracting knowledge, key points, and structure from text-heavy Word documents.

When the user asks you to digest a Word document, you must analyze its text and generate a standardized JSON summary according to the ccmem v2.0 schema, then save it to `.claude/ccmem/json/`.

## Process

1. **Analyze the Document**: Read the document to understand its core topic, arguments, and conclusions. Pay attention to headings and structure.
2. **Determine Chunks**: Break the file down logically. Good chunks for Word documents include:
   - **Executive Summary/Abstract**: The high-level overview of the document.
   - **Major Sections**: Create a chunk for each major heading or distinct topic covered in the text.
   - **Key Entities/Decisions**: Specific names, dates, requirements, or decisions outlined in the text.
3. **Extract Knowledge**: Summarize the content of each chunk clearly and concisely. Avoid simply repeating the text word-for-word; synthesize the meaning.
4. **Determine Keywords**: Select highly relevant keywords for the document as a whole, and specific keywords for each chunk. Include names of projects, people, or specific technologies mentioned.
5. **Format as JSON**: Construct the JSON object strictly matching the v2.0 schema (see below).
6. **Save**: Save the resulting JSON file to `.claude/ccmem/json/{original_filename}.json`.

## Guidelines for Word Documents

*   **Synthesis**: Provide synthesized summaries of sections rather than raw text dumps.
*   **Structure**: Use the document's original headings to guide your chunking strategy.
*   **Actionable Info**: Highlight any action items, requirements, or final conclusions.

## JSON v2.0 Schema Reference

Your output MUST be a valid JSON object matching this structure:

```json
{
  "version": "2.0",
  "source": {
    "file_path": "docs/Project_Proposal.docx", 
    "file_type": "docx",
    "last_modified": "YYYY-MM-DDThh:mm:ssZ"
  },
  "document": {
    "title": "A descriptive title for the document",
    "summary": "A 1-3 paragraph summary of the document's overall message and purpose.",
    "keywords": ["proposal", "project-x", "requirements"]
  },
  "chunks": [
    {
      "chunk_id": "chunk_exec_summary",
      "chunk_title": "Executive Summary",
      "content": "The proposal outlines a plan to migrate the legacy database to PostgreSQL by Q4...",
      "keywords": ["summary", "migration", "postgresql"]
    },
    {
      "chunk_id": "chunk_requirements",
      "chunk_title": "Section: Technical Requirements",
      "content": "Details the hardware and software needs for the migration. Key requirements include...",
      "keywords": ["requirements", "hardware", "software"]
    }
  ],
  "relations": {
    "references": ["docs/Architecture.pdf"]
  }
}
```
