---
name: digest_excel
description: Instructions for parsing and digesting Excel workbooks (.xlsx, .xls) into ccmem JSON v2.0 memory files.
---

# Digesting Excel Workbooks

You are an expert data analyst and business intelligence specialist tasked with extracting knowledge, structure, and insights from Excel workbooks.

When the user asks you to digest an Excel file, you must analyze its contents and generate a standardized JSON summary according to the ccmem v2.0 schema, then save it to `.claude/ccmem/json/`.

## Process

1. **Analyze the Workbook**: Understand the overall purpose of the workbook. List the available sheets.
2. **Analyze Sheets**: For each meaningful sheet, determine its purpose, structure (table format, pivot table, report layout), and key data points.
3. **Determine Chunks**: Break the file down logically. Good chunks for Excel include:
   - **Workbook Overview**: The general purpose and list of sheets.
   - **Sheet Summaries (per sheet)**: Description of the sheet's contents, key columns (if tabular), or key metrics (if a report/dashboard).
   - **Formulas/Logic**: If complex formulas or macros are apparent and important, document their logic.
4. **Extract Knowledge**: Summarize what business questions this workbook answers or what process it supports.
5. **Determine Keywords**: Select highly relevant keywords for the document as a whole, and specific keywords for each chunk.
6. **Format as JSON**: Construct the JSON object strictly matching the v2.0 schema (see below).
7. **Save**: Save the resulting JSON file to `.claude/ccmem/json/{original_filename}.json`.

## Guidelines for Excel

*   **Focus on Meta-Data and Structure**: Do not store all cell values. Focus on the *meaning* of the data and how it's organized.
*   **Sheet Context**: Clearly identify which sheet a piece of information belongs to within your chunks.
*   **Business Logic**: Pay attention to calculated fields or sum totals that represent important business metrics.

## JSON v2.0 Schema Reference

Your output MUST be a valid JSON object matching this structure:

```json
{
  "version": "2.0",
  "source": {
    "file_path": "reports/Q3_Financials.xlsx", 
    "file_type": "excel",
    "last_modified": "YYYY-MM-DDThh:mm:ssZ"
  },
  "document": {
    "title": "A descriptive title for the workbook",
    "summary": "A 1-3 paragraph summary of what this workbook contains and its business value.",
    "keywords": ["finance", "report", "q3"]
  },
  "chunks": [
    {
      "chunk_id": "chunk_overview",
      "chunk_title": "Workbook Structure",
      "content": "Contains 3 sheets: 'Summary', 'Raw Data', 'Charts'. Built to track departmental spend...",
      "keywords": ["structure", "sheets"]
    },
    {
      "chunk_id": "chunk_sheet_summary",
      "chunk_title": "Sheet: Summary",
      "content": "A high-level rollup of spend by department. Key metrics include 'Total Budget', 'Actual Spend', 'Variance'...",
      "keywords": ["summary", "budget", "variance"]
    }
  ],
  "relations": {
    "uses": ["data/spend_export.csv"]
  }
}
```
