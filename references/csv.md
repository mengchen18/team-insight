---
name: digest_csv
description: Instructions for parsing and digesting CSV/TSV data files into ccmem JSON v2.0 memory files.
---

# Digesting CSV/TSV Files

You are an expert data analyst tasked with extracting knowledge, structure, and insights from tabular data files (CSV, TSV).

When the user asks you to digest a CSV or TSV file, you must analyze its contents and generate a standardized JSON summary according to the ccmem v2.0 schema, then save it to `.claude/team-insight/json/`.

## Process

1. **Analyze the Structure**: Read the header row and a sample of the data (e.g., the first 5-10 rows) to understand the dataset's contents.
2. **Identify Columns**: Determine the data types, meaning, and potential usage of each column.
3. **Determine Chunks**: Break the file down logically. Good chunks for tabular data include:
   - **Schema Definition**: A list of all columns, their inferred types, and a brief description of what they represent.
   - **Data Characteristics**: High-level observations about the data (e.g., "Contains user demographics spanning 2020-2023").
   - **Potential Issues**: Any obvious data quality issues observed in the sample (e.g., missing values, inconsistent formatting).
4. **Extract Knowledge**: Summarize the purpose of the dataset and how it might be used in the project.
5. **Determine Keywords**: Select highly relevant keywords for the document as a whole, and specific keywords for each chunk.
6. **Format as JSON**: Construct the JSON object strictly matching the v2.0 schema (see below).
7. **Save**: Save the resulting JSON file to `.claude/team-insight/json/{original_filename}.json`.

## Guidelines for Tabular Data

*   **Focus on Meta-Data**: Do not attempt to store the entire CSV content in the JSON. Store *information about the data*.
*   **Sample Data**: You may include a small 2-3 row sample in a chunk if it helps illustrate the data format, but limit its size.
*   **Schema is King**: Detailed column descriptions are the most valuable part of this digestion.

## JSON v2.0 Schema Reference

Your output MUST be a valid JSON object matching this structure:

```json
{
  "version": "2.0",
  "source": {
    "file_path": "data/users.csv", 
    "file_type": "csv",
    "last_modified": "YYYY-MM-DDThh:mm:ssZ"
  },
  "document": {
    "title": "A descriptive title for the dataset",
    "summary": "A 1-2 paragraph summary of what this dataset contains and its purpose.",
    "keywords": ["dataset", "users", "demographics"]
  },
  "chunks": [
    {
      "chunk_id": "chunk_schema",
      "chunk_title": "Column Definitions",
      "content": "Detailed explanation of columns: 'id' (int, primary key), 'name' (string), 'created_at' (timestamp), etc.",
      "keywords": ["schema", "columns"]
    },
    {
      "chunk_id": "chunk_characteristics",
      "chunk_title": "Data Characteristics & Sample",
      "content": "Explanation of data range, observed formats, and a tiny sample for context...",
      "keywords": ["sample", "format"]
    }
  ],
  "relations": {
    "generated_by": ["scripts/extract_users.py"]
  }
}
```
